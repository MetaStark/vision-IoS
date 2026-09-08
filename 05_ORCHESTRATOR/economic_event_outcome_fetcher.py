#!/usr/bin/env python3
"""
Economic Event Outcome Fetcher - CEO-DIR-2026-META-ANALYSIS Phase 1
====================================================================

Purpose: Fetch actual outcomes for economic calendar events from FRED API
         and update fhq_calendar.calendar_events to enable LVI computation.

Directive: CEO-DIR-2026-META-ANALYSIS Phase 1 - Learning Loop Recovery
Authority: ADR-013 (Database as Truth), ADR-011 (Fortress Evidence)

Data Flow:
1. Query events where event_timestamp < NOW() AND actual_value IS NULL
2. Map event_type_code to FRED series ID
3. Fetch latest observation from FRED API
4. Update calendar_events.actual_value with lineage proof
5. Compute surprise score
6. Forward to hypothesis evaluation for LVI

FRED Series Mappings:
- US_CLAIMS (DOL) -> ICSA (Initial Jobless Claims, weekly, Thursday 8:30 ET)
- US_CPI (BLS) -> CPIAUCSL (CPI All Urban Consumers, monthly)
- US_NFP (BLS) -> PAYEMS (Total Nonfarm Payrolls, monthly)
- US_RETAIL (CENSUS) -> RSAFS (Advance Retail Sales, monthly)
- US_PPI (BLS) -> PPIACO (PPI All Commodities, monthly)
- US_GDP (BEA) -> GDP (Gross Domestic Product, quarterly)
- US_PCE (BEA) -> PCEPI (PCE Price Index, monthly)
- US_FOMC (FED) -> DFEDTARU (Fed Funds Target Rate Upper)

Author: STIG (EC-003)
Date: 2026-01-23
Contract: EC-003_2026_PRODUCTION
"""

import os
import sys
import json
import hashlib
import logging
import requests
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple, Any
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('EconomicEventOutcomeFetcher')

# Database connection
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# FRED API configuration
FRED_BASE_URL = 'https://api.stlouisfed.org/fred/series/observations'
FRED_API_KEY = os.getenv('FRED_API_KEY', '')

# Event type to FRED series mapping
# Each entry: (fred_series_id, value_transform, release_delay_hours)
FRED_SERIES_MAP = {
    # Weekly releases
    'US_CLAIMS': {
        'series_id': 'ICSA',
        'transform': lambda x: x / 1000,  # FRED reports in thousands, we store in thousands
        'release_delay_hours': 0.5,  # Available ~30 min after release time
        'unit': 'thousands',
        'description': 'Initial Jobless Claims'
    },

    # Monthly releases - Prices
    'US_CPI': {
        'series_id': 'CPIAUCSL',
        'transform': lambda x: x,  # Index value
        'release_delay_hours': 1,
        'unit': 'index',
        'description': 'Consumer Price Index'
    },
    'US_PPI': {
        'series_id': 'PPIACO',
        'transform': lambda x: x,
        'release_delay_hours': 1,
        'unit': 'index',
        'description': 'Producer Price Index'
    },
    'US_PCE': {
        'series_id': 'PCEPI',
        'transform': lambda x: x,
        'release_delay_hours': 1,
        'unit': 'index',
        'description': 'PCE Price Index'
    },

    # Monthly releases - Employment
    'US_NFP': {
        'series_id': 'PAYEMS',
        'transform': lambda x: x,  # In thousands
        'release_delay_hours': 1,
        'unit': 'thousands',
        'description': 'Nonfarm Payrolls'
    },

    # Monthly releases - Activity
    'US_RETAIL': {
        'series_id': 'RSAFS',
        'transform': lambda x: x,  # Millions of dollars
        'release_delay_hours': 1,
        'unit': 'millions_usd',
        'description': 'Advance Retail Sales'
    },

    # Quarterly releases
    'US_GDP': {
        'series_id': 'GDP',
        'transform': lambda x: x,  # Billions of dollars
        'release_delay_hours': 1,
        'unit': 'billions_usd',
        'description': 'Gross Domestic Product'
    },

    # Policy rates
    'US_FOMC': {
        'series_id': 'DFEDTARU',
        'transform': lambda x: x,  # Percentage
        'release_delay_hours': 0.5,
        'unit': 'percent',
        'description': 'Federal Funds Target Rate Upper'
    },
}

# Alternative source for ISM (not on FRED, would need ISM direct or other source)
# 'US_ISM_MFG': ISM Manufacturing PMI - requires ISM subscription
# 'US_ISM_SVC': ISM Services PMI - requires ISM subscription


class EconomicEventOutcomeFetcher:
    """
    Fetches actual outcomes for economic calendar events.

    CEO-DIR-2026-META-ANALYSIS Compliance:
    - Fetches ONLY from approved API sources (FRED)
    - Records full lineage proof for each fetch
    - Computes surprise scores for learning loop
    - Updates hypothesis evaluation for LVI
    """

    def __init__(self):
        self.conn = None
        self.api_key = FRED_API_KEY
        self.results = {
            'run_id': f"OUTCOME-FETCH-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            'started_at': datetime.now(timezone.utc).isoformat(),
            'events_checked': 0,
            'events_updated': 0,
            'events_skipped': 0,
            'errors': []
        }

    def connect(self):
        """Establish database connection."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Database connection established")

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def validate_api_key(self) -> bool:
        """Validate FRED API key is configured."""
        if not self.api_key:
            logger.error("FRED_API_KEY not configured. Set environment variable.")
            self.results['errors'].append({
                'type': 'CONFIG_ERROR',
                'message': 'FRED_API_KEY not set'
            })
            return False
        return True

    def get_events_needing_outcome(self, hours_lookback: int = 72) -> List[Dict]:
        """
        Get calendar events that have passed but don't have actual values.

        Only returns events where:
        - event_timestamp < NOW()
        - actual_value IS NULL
        - event_type_code is in our FRED mapping
        - Event occurred within lookback window
        """
        supported_types = tuple(FRED_SERIES_MAP.keys())

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    event_id,
                    event_type_code,
                    event_timestamp,
                    consensus_estimate,
                    previous_value,
                    source_provider,
                    is_canonical
                FROM fhq_calendar.calendar_events
                WHERE is_canonical = true
                  AND event_timestamp < NOW()
                  AND event_timestamp > NOW() - INTERVAL '%s hours'
                  AND actual_value IS NULL
                  AND event_type_code IN %s
                ORDER BY event_timestamp DESC
            """, (hours_lookback, supported_types))

            events = cur.fetchall()
            logger.info(f"Found {len(events)} events needing outcome fetch")
            return [dict(e) for e in events]

    def fetch_fred_observation(self, series_id: str,
                                observation_date: datetime) -> Optional[Tuple[Decimal, str, Dict]]:
        """
        Fetch observation from FRED API for a specific date.

        Returns: (value, response_hash, metadata) or None if failed

        FRED API returns observations sorted by date. We fetch recent observations
        and find the one matching or closest to our target date.
        """
        # Format dates for FRED API
        # Look back 7 days to ensure we capture the release
        start_date = (observation_date - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = (observation_date + timedelta(days=1)).strftime('%Y-%m-%d')

        params = {
            'series_id': series_id,
            'api_key': self.api_key,
            'file_type': 'json',
            'observation_start': start_date,
            'observation_end': end_date,
            'sort_order': 'desc',
            'limit': 5
        }

        try:
            logger.info(f"Fetching FRED series {series_id} for {observation_date.date()}")
            response = requests.get(FRED_BASE_URL, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Create response hash for lineage
            response_hash = hashlib.sha256(
                json.dumps(data, sort_keys=True).encode()
            ).hexdigest()[:16]

            observations = data.get('observations', [])
            if not observations:
                logger.warning(f"No observations found for {series_id}")
                return None

            # Get the most recent observation
            # FRED releases data with a date that matches the reference period
            latest = observations[0]
            value_str = latest.get('value', '.')

            # FRED uses '.' for missing values
            if value_str == '.':
                logger.warning(f"Missing value marker for {series_id}")
                return None

            try:
                value = Decimal(value_str)
            except (InvalidOperation, ValueError) as e:
                logger.error(f"Invalid value '{value_str}' for {series_id}: {e}")
                return None

            metadata = {
                'fred_series_id': series_id,
                'observation_date': latest.get('date'),
                'realtime_start': latest.get('realtime_start'),
                'realtime_end': latest.get('realtime_end'),
                'fetch_timestamp': datetime.now(timezone.utc).isoformat(),
                'observations_returned': len(observations)
            }

            logger.info(f"FRED {series_id}: value={value}, date={latest.get('date')}")
            return (value, response_hash, metadata)

        except requests.exceptions.RequestException as e:
            logger.error(f"FRED API request failed for {series_id}: {e}")
            return None
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"FRED API response parse error for {series_id}: {e}")
            return None

    def update_event_outcome(self, event_id: str, actual_value: Decimal,
                              api_source: str, response_hash: str,
                              metadata: Dict) -> bool:
        """
        Update calendar event with actual outcome and lineage proof.

        Steps:
        1. Record lineage proof in data_lineage_proof
        2. Update calendar_events.actual_value
        3. Set lineage_status to VERIFIED
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                # Step 1: Record lineage proof
                cur.execute("""
                    INSERT INTO fhq_calendar.data_lineage_proof (
                        lineage_id,
                        event_id,
                        source_code,
                        api_request_timestamp,
                        api_response_hash,
                        extracted_value,
                        extraction_path,
                        verified_by,
                        verified_at
                    ) VALUES (
                        gen_random_uuid(),
                        %s,
                        %s,
                        NOW(),
                        %s,
                        %s,
                        %s,
                        'EconomicEventOutcomeFetcher',
                        NOW()
                    )
                    ON CONFLICT (event_id) DO UPDATE SET
                        api_response_hash = EXCLUDED.api_response_hash,
                        extracted_value = EXCLUDED.extracted_value,
                        extraction_path = EXCLUDED.extraction_path,
                        verified_at = NOW()
                """, (
                    event_id,
                    api_source,
                    response_hash,
                    str(actual_value),
                    json.dumps(metadata)  # Store metadata in extraction_path as JSON
                ))

                # Step 2: Update calendar event
                cur.execute("""
                    UPDATE fhq_calendar.calendar_events
                    SET
                        actual_value = %s,
                        lineage_status = 'VERIFIED',
                        updated_at = NOW()
                    WHERE event_id = %s
                    RETURNING event_id, event_type_code, consensus_estimate, actual_value
                """, (str(actual_value), event_id))

                result = cur.fetchone()
                self.conn.commit()

                if result:
                    logger.info(
                        f"Updated {result['event_type_code']}: "
                        f"consensus={result['consensus_estimate']}, "
                        f"actual={result['actual_value']}"
                    )
                    return True

            except Exception as e:
                self.conn.rollback()
                logger.error(f"Failed to update event {event_id}: {e}")
                self.results['errors'].append({
                    'type': 'DB_UPDATE_ERROR',
                    'event_id': str(event_id),
                    'message': str(e)
                })

        return False

    def compute_surprise_score(self, event_id: str) -> Optional[Decimal]:
        """
        Compute and store surprise score for an event.

        Surprise = (actual - consensus) for simple metrics
        Could be normalized by historical std for cross-event comparison.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    event_id,
                    event_type_code,
                    consensus_estimate,
                    actual_value
                FROM fhq_calendar.calendar_events
                WHERE event_id = %s
            """, (event_id,))

            event = cur.fetchone()
            if not event:
                return None

            if event['actual_value'] is None or event['consensus_estimate'] is None:
                logger.warning(f"Cannot compute surprise for {event_id}: missing values")
                return None

            try:
                actual = Decimal(str(event['actual_value']))
                consensus = Decimal(str(event['consensus_estimate']))

                # Simple surprise: actual - consensus
                surprise = actual - consensus

                # Update the event with surprise score
                cur.execute("""
                    UPDATE fhq_calendar.calendar_events
                    SET surprise_score = %s, updated_at = NOW()
                    WHERE event_id = %s
                """, (str(surprise), event_id))
                self.conn.commit()

                logger.info(
                    f"Surprise for {event['event_type_code']}: "
                    f"{actual} - {consensus} = {surprise}"
                )
                return surprise

            except (InvalidOperation, ValueError) as e:
                logger.error(f"Surprise calculation error for {event_id}: {e}")
                return None

    def evaluate_hypothesis(self, event_id: str) -> bool:
        """
        Check if there's a hypothesis for this event and trigger evaluation.

        This enables the learning loop:
        - Event occurs -> outcome fetched -> hypothesis evaluated -> LVI updated
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check for hypothesis linked to this event
            cur.execute("""
                SELECT
                    h.hypothesis_id,
                    h.expected_direction,
                    h.confidence_pre_event,
                    ce.actual_value,
                    ce.consensus_estimate,
                    ce.surprise_score,
                    ce.event_timestamp
                FROM fhq_learning.hypothesis_ledger h
                JOIN fhq_calendar.calendar_events ce ON h.event_id = ce.event_id
                WHERE h.event_id = %s
            """, (event_id,))

            hypothesis = cur.fetchone()
            if not hypothesis:
                logger.info(f"No hypothesis found for event {event_id}")
                return False

            # Determine if hypothesis was correct based on direction
            surprise = hypothesis['surprise_score']
            expected_dir = hypothesis['expected_direction']
            actual_val = hypothesis['actual_value']
            consensus_val = hypothesis['consensus_estimate']
            event_time = hypothesis['event_timestamp']

            if surprise is None:
                logger.warning(f"Cannot evaluate hypothesis - no surprise score")
                return False

            surprise_val = Decimal(str(surprise))

            # Map direction to constraint values: BULLISH, BEARISH, NEUTRAL
            actual_direction = 'BULLISH' if surprise_val > 0 else ('BEARISH' if surprise_val < 0 else 'NEUTRAL')

            # Map expected direction (may be in different format)
            expected_mapped = expected_dir.upper()
            if expected_mapped in ('UP', 'POSITIVE'):
                expected_mapped = 'BULLISH'
            elif expected_mapped in ('DOWN', 'NEGATIVE'):
                expected_mapped = 'BEARISH'
            else:
                expected_mapped = 'NEUTRAL'

            is_correct = (actual_direction == expected_mapped)

            # Compute evaluation hours
            eval_hours = (datetime.now(timezone.utc) - event_time.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            within_24h = eval_hours <= 24

            # Determine learning verdict: VALIDATED, WEAKENED, FALSIFIED
            if is_correct:
                verdict = 'VALIDATED'
                rationale = f"Expected {expected_dir} ({expected_mapped}), actual was {actual_direction}. Surprise: {surprise_val}"
            else:
                verdict = 'FALSIFIED'
                rationale = f"Expected {expected_dir} ({expected_mapped}), but actual was {actual_direction}. Surprise: {surprise_val}"

            # Check if outcome already exists for this hypothesis
            cur.execute("""
                SELECT outcome_id FROM fhq_learning.expectation_outcome_ledger
                WHERE hypothesis_id = %s
            """, (str(hypothesis['hypothesis_id']),))
            existing = cur.fetchone()

            if existing:
                # Update existing record
                cur.execute("""
                    UPDATE fhq_learning.expectation_outcome_ledger
                    SET
                        actual_direction = %s,
                        actual_value = %s,
                        consensus_value = %s,
                        surprise_score = %s,
                        learning_verdict = %s,
                        verdict_rationale = %s,
                        recorded_at = NOW(),
                        evaluation_hours = %s,
                        evidence_hash = %s
                    WHERE hypothesis_id = %s
                """, (
                    actual_direction,
                    str(actual_val) if actual_val else None,
                    str(consensus_val) if consensus_val else None,
                    str(surprise_val),
                    verdict,
                    rationale,
                    round(eval_hours, 2),
                    hashlib.sha256(f"{hypothesis['hypothesis_id']}-{actual_direction}-{surprise_val}".encode()).hexdigest()[:16],
                    str(hypothesis['hypothesis_id'])
                ))
            else:
                # Insert new record
                cur.execute("""
                    INSERT INTO fhq_learning.expectation_outcome_ledger (
                        outcome_id,
                        hypothesis_id,
                        actual_direction,
                        actual_value,
                        consensus_value,
                        surprise_score,
                        learning_verdict,
                        verdict_rationale,
                        recorded_at,
                        recorded_by,
                        recorded_within_24h,
                        evaluation_hours,
                        evidence_hash
                    ) VALUES (
                        gen_random_uuid(),
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        NOW(),
                        'EconomicEventOutcomeFetcher',
                        %s,
                        %s,
                        %s
                    )
                """, (
                    str(hypothesis['hypothesis_id']),
                    actual_direction,
                    str(actual_val) if actual_val else None,
                    str(consensus_val) if consensus_val else None,
                    str(surprise_val),
                    verdict,
                    rationale,
                    within_24h,
                    round(eval_hours, 2),
                    hashlib.sha256(f"{hypothesis['hypothesis_id']}-{actual_direction}-{surprise_val}".encode()).hexdigest()[:16]
                ))
            self.conn.commit()

            logger.info(
                f"Hypothesis evaluated: expected={expected_dir}, "
                f"actual={actual_direction}, verdict={verdict}"
            )
            return True

    def log_governance_action(self, events_updated: int):
        """Log this fetch run as a governance action."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_id,
                    action_type,
                    action_target,
                    action_target_type,
                    initiated_by,
                    initiated_at,
                    decision,
                    decision_rationale,
                    metadata
                ) VALUES (
                    gen_random_uuid(),
                    'ECONOMIC_OUTCOME_FETCH',
                    %s,
                    'CALENDAR_EVENTS',
                    'EconomicEventOutcomeFetcher',
                    NOW(),
                    'EXECUTED',
                    %s,
                    %s
                )
            """, (
                self.results['run_id'],
                f"Fetched {events_updated} economic event outcomes from FRED API. "
                f"CEO-DIR-2026-META-ANALYSIS Phase 1 - Learning Loop Recovery.",
                json.dumps(self.results)
            ))
            self.conn.commit()

    def run_fetch_cycle(self, hours_lookback: int = 72) -> Dict:
        """
        Run complete fetch cycle for all pending events.

        Flow:
        1. Get events needing outcomes
        2. For each event, fetch from FRED
        3. Update event with actual value
        4. Compute surprise score
        5. Evaluate any linked hypotheses
        6. Log governance action
        """
        if not self.validate_api_key():
            self.results['status'] = 'FAILED_NO_API_KEY'
            return self.results

        # Get events needing outcomes
        events = self.get_events_needing_outcome(hours_lookback)
        self.results['events_checked'] = len(events)

        for event in events:
            event_type = event['event_type_code']
            event_id = str(event['event_id'])
            event_time = event['event_timestamp']

            # Check if we have a FRED mapping
            if event_type not in FRED_SERIES_MAP:
                logger.info(f"No FRED mapping for {event_type}, skipping")
                self.results['events_skipped'] += 1
                continue

            mapping = FRED_SERIES_MAP[event_type]
            series_id = mapping['series_id']

            # Check release delay
            release_delay = mapping.get('release_delay_hours', 1)
            if datetime.now(timezone.utc) < event_time.replace(tzinfo=timezone.utc) + timedelta(hours=release_delay):
                logger.info(f"Event {event_type} too recent, waiting for release delay")
                self.results['events_skipped'] += 1
                continue

            # Fetch from FRED
            fred_result = self.fetch_fred_observation(series_id, event_time)
            if not fred_result:
                self.results['errors'].append({
                    'type': 'FETCH_ERROR',
                    'event_id': event_id,
                    'event_type': event_type,
                    'message': f'Failed to fetch {series_id} from FRED'
                })
                continue

            value, response_hash, metadata = fred_result

            # Apply transform if needed
            transform = mapping.get('transform')
            if transform:
                value = Decimal(str(transform(float(value))))

            # Update event
            if self.update_event_outcome(event_id, value, 'FRED', response_hash, metadata):
                self.results['events_updated'] += 1

                # Compute surprise
                self.compute_surprise_score(event_id)

                # Evaluate hypothesis if exists
                self.evaluate_hypothesis(event_id)

        # Log governance action
        if self.results['events_updated'] > 0:
            self.log_governance_action(self.results['events_updated'])

        self.results['completed_at'] = datetime.now(timezone.utc).isoformat()
        self.results['status'] = 'COMPLETED'

        return self.results

    def get_fetch_status(self) -> Dict:
        """Get current status of outcome fetching."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Events pending fetch
            cur.execute("""
                SELECT COUNT(*) as pending
                FROM fhq_calendar.calendar_events
                WHERE is_canonical = true
                  AND event_timestamp < NOW()
                  AND event_timestamp > NOW() - INTERVAL '72 hours'
                  AND actual_value IS NULL
            """)
            pending = cur.fetchone()['pending']

            # Events with outcomes
            cur.execute("""
                SELECT COUNT(*) as with_outcomes
                FROM fhq_calendar.calendar_events
                WHERE is_canonical = true
                  AND actual_value IS NOT NULL
                  AND lineage_status = 'VERIFIED'
            """)
            with_outcomes = cur.fetchone()['with_outcomes']

            # Recent fetches
            cur.execute("""
                SELECT COUNT(*) as recent_fetches
                FROM fhq_governance.governance_actions_log
                WHERE action_type = 'ECONOMIC_OUTCOME_FETCH'
                  AND initiated_at > NOW() - INTERVAL '24 hours'
            """)
            recent_fetches = cur.fetchone()['recent_fetches']

            return {
                'status': 'ACTIVE' if self.api_key else 'NO_API_KEY',
                'events_pending_fetch': pending,
                'events_with_verified_outcomes': with_outcomes,
                'fetches_last_24h': recent_fetches,
                'supported_event_types': list(FRED_SERIES_MAP.keys())
            }


def main():
    """Main entry point for outcome fetcher."""
    fetcher = EconomicEventOutcomeFetcher()

    try:
        fetcher.connect()

        # Check status first
        status = fetcher.get_fetch_status()
        print("=== Outcome Fetcher Status ===")
        print(json.dumps(status, indent=2))

        if not FRED_API_KEY:
            print("\n[ERROR] FRED_API_KEY not set!")
            print("Get free key at: https://fred.stlouisfed.org/docs/api/api_key.html")
            print("Then: export FRED_API_KEY=your_key_here")
            return

        # Run fetch cycle
        print("\n=== Running Fetch Cycle ===")
        results = fetcher.run_fetch_cycle(hours_lookback=72)

        print("\n=== Fetch Results ===")
        print(json.dumps(results, indent=2, default=str))

    except Exception as e:
        logger.error(f"Outcome fetcher failed: {e}")
        raise
    finally:
        fetcher.disconnect()


if __name__ == '__main__':
    main()
