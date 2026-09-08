#!/usr/bin/env python3
"""
Economic Outcome Daemon - Continuous Calendar Event Monitoring
==============================================================

Purpose: Continuously monitor calendar events and automatically fetch outcomes
         from FRED API as soon as they become available.

Directive: CEO-DIR-2026-META-ANALYSIS Phase 1 - Learning Loop Recovery
Authority: ADR-013 (Database as Truth), ADR-011 (Fortress Evidence)

Operation:
- Runs continuously as a daemon
- Checks calendar every 5 minutes for events needing outcomes
- Fetches from FRED as soon as data is available (typically 30-60 min after release)
- Evaluates hypotheses and enables LVI computation
- Registers heartbeat for monitoring

Usage:
    python economic_outcome_daemon.py              # Run daemon
    python economic_outcome_daemon.py --once       # Single cycle (for testing)
    python economic_outcome_daemon.py --status     # Check status

Author: STIG (EC-003)
Date: 2026-01-23
Contract: EC-003_2026_PRODUCTION
"""

import os
import sys
import json
import time
import signal
import hashlib
import logging
import argparse
import requests
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple, Any
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('economic_outcome_daemon.log')
    ]
)
logger = logging.getLogger('EconomicOutcomeDaemon')

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

# Daemon configuration
DAEMON_NAME = 'economic_outcome_daemon'
CHECK_INTERVAL_SECONDS = 300  # 5 minutes
HEARTBEAT_INTERVAL_SECONDS = 600  # 10 minutes
MAX_LOOKBACK_HOURS = 168  # 7 days

# Event type to FRED series mapping with timing metadata
FRED_SERIES_MAP = {
    'US_CLAIMS': {
        'series_id': 'ICSA',
        'transform': lambda x: x / 1000,  # FRED in units, we store in thousands
        'release_delay_minutes': 30,  # Available ~30 min after 8:30 ET release
        'check_frequency_minutes': 10,  # Check every 10 min after event time
        'unit': 'thousands',
        'description': 'Initial Jobless Claims (Weekly, Thursday 8:30 ET)'
    },
    'US_CPI': {
        'series_id': 'CPIAUCSL',
        'transform': lambda x: x,
        'release_delay_minutes': 60,
        'check_frequency_minutes': 15,
        'unit': 'index',
        'description': 'Consumer Price Index (Monthly)'
    },
    'US_PPI': {
        'series_id': 'PPIACO',
        'transform': lambda x: x,
        'release_delay_minutes': 60,
        'check_frequency_minutes': 15,
        'unit': 'index',
        'description': 'Producer Price Index (Monthly)'
    },
    'US_PCE': {
        'series_id': 'PCEPI',
        'transform': lambda x: x,
        'release_delay_minutes': 60,
        'check_frequency_minutes': 15,
        'unit': 'index',
        'description': 'PCE Price Index (Monthly)'
    },
    'US_NFP': {
        'series_id': 'PAYEMS',
        'transform': lambda x: x,
        'release_delay_minutes': 45,
        'check_frequency_minutes': 10,
        'unit': 'thousands',
        'description': 'Nonfarm Payrolls (Monthly, First Friday 8:30 ET)'
    },
    'US_RETAIL': {
        'series_id': 'RSAFS',
        'transform': lambda x: x,
        'release_delay_minutes': 60,
        'check_frequency_minutes': 15,
        'unit': 'millions_usd',
        'description': 'Advance Retail Sales (Monthly)'
    },
    'US_GDP': {
        'series_id': 'GDP',
        'transform': lambda x: x,
        'release_delay_minutes': 60,
        'check_frequency_minutes': 15,
        'unit': 'billions_usd',
        'description': 'Gross Domestic Product (Quarterly)'
    },
    'US_FOMC': {
        'series_id': 'DFEDTARU',
        'transform': lambda x: x,
        'release_delay_minutes': 15,  # Fed releases immediately
        'check_frequency_minutes': 5,
        'unit': 'percent',
        'description': 'Federal Funds Target Rate Upper'
    },
}


class EconomicOutcomeDaemon:
    """
    Continuous daemon for fetching economic event outcomes.

    Monitors the calendar and automatically fetches outcomes from FRED
    as soon as they become available after each event.
    """

    def __init__(self):
        self.conn = None
        self.running = False
        self.last_heartbeat = None
        self.cycle_count = 0
        self.total_fetched = 0
        self.api_key = FRED_API_KEY

    def connect(self):
        """Establish database connection."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Database connection established")

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def reconnect(self):
        """Reconnect to database if connection lost."""
        try:
            if self.conn:
                self.conn.close()
        except:
            pass
        self.connect()

    def validate_api_key(self) -> bool:
        """Validate FRED API key is configured."""
        if not self.api_key:
            logger.error("FRED_API_KEY not configured!")
            return False
        return True

    # =========================================================================
    # HEARTBEAT & MONITORING
    # =========================================================================

    def register_heartbeat(self):
        """Register daemon heartbeat for monitoring."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE fhq_governance.agent_heartbeats
                    SET
                        last_heartbeat = NOW(),
                        current_task = %s,
                        events_processed = %s,
                        health_score = 1.0,
                        liveness_basis = %s,
                        liveness_metadata = %s
                    WHERE component = 'EVIDENCE'

                """, (
                    f"Cycle {self.cycle_count}: Monitoring calendar events",
                    self.total_fetched,
                    f"Economic Outcome Daemon: {self.total_fetched} outcomes fetched in {self.cycle_count} cycles",
                    json.dumps({
                        'daemon_name': DAEMON_NAME,
                        'cycle_count': self.cycle_count,
                        'total_fetched': self.total_fetched,
                        'check_interval_sec': CHECK_INTERVAL_SECONDS,
                        'last_cycle': datetime.now(timezone.utc).isoformat()
                    })
                ))
                self.conn.commit()
                self.last_heartbeat = datetime.now(timezone.utc)
                logger.debug("Heartbeat registered")
        except Exception as e:
            logger.warning(f"Failed to register heartbeat: {e}")

    # =========================================================================
    # CALENDAR MONITORING
    # =========================================================================

    def get_events_ready_for_fetch(self) -> List[Dict]:
        """
        Get calendar events that are ready for outcome fetching.

        An event is ready when:
        - event_timestamp has passed
        - Release delay has elapsed (data should be available)
        - actual_value is still NULL
        - Event type has FRED mapping
        """
        supported_types = tuple(FRED_SERIES_MAP.keys())

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get events that have passed and need outcomes
            cur.execute("""
                SELECT
                    event_id,
                    event_type_code,
                    event_timestamp,
                    consensus_estimate,
                    previous_value,
                    source_provider,
                    EXTRACT(EPOCH FROM (NOW() - event_timestamp)) / 60 as minutes_since_event
                FROM fhq_calendar.calendar_events
                WHERE is_canonical = true
                  AND event_timestamp < NOW()
                  AND event_timestamp > NOW() - INTERVAL '%s hours'
                  AND actual_value IS NULL
                  AND event_type_code IN %s
                ORDER BY event_timestamp DESC
            """, (MAX_LOOKBACK_HOURS, supported_types))

            events = cur.fetchall()

            # Filter by release delay
            ready_events = []
            for event in events:
                event_type = event['event_type_code']
                mapping = FRED_SERIES_MAP[event_type]
                release_delay = mapping.get('release_delay_minutes', 60)

                if event['minutes_since_event'] >= release_delay:
                    ready_events.append(dict(event))
                else:
                    logger.debug(
                        f"{event_type}: {event['minutes_since_event']:.0f} min since event, "
                        f"waiting for {release_delay} min release delay"
                    )

            return ready_events

    def get_upcoming_events(self, hours_ahead: int = 24) -> List[Dict]:
        """Get upcoming events for status display."""
        supported_types = tuple(FRED_SERIES_MAP.keys())

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    event_type_code,
                    event_timestamp,
                    consensus_estimate,
                    EXTRACT(EPOCH FROM (event_timestamp - NOW())) / 60 as minutes_until
                FROM fhq_calendar.calendar_events
                WHERE is_canonical = true
                  AND event_timestamp > NOW()
                  AND event_timestamp < NOW() + INTERVAL '%s hours'
                  AND event_type_code IN %s
                ORDER BY event_timestamp ASC
            """, (hours_ahead, supported_types))

            return [dict(e) for e in cur.fetchall()]

    # =========================================================================
    # FRED API FETCHING
    # =========================================================================

    def fetch_from_fred(self, series_id: str,
                        observation_date: datetime) -> Optional[Tuple[Decimal, str, Dict]]:
        """
        Fetch latest observation from FRED API.

        Returns: (value, response_hash, metadata) or None
        """
        start_date = (observation_date - timedelta(days=14)).strftime('%Y-%m-%d')
        end_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime('%Y-%m-%d')

        params = {
            'series_id': series_id,
            'api_key': self.api_key,
            'file_type': 'json',
            'observation_start': start_date,
            'observation_end': end_date,
            'sort_order': 'desc',
            'limit': 10
        }

        try:
            response = requests.get(FRED_BASE_URL, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            response_hash = hashlib.sha256(
                json.dumps(data, sort_keys=True).encode()
            ).hexdigest()[:16]

            observations = data.get('observations', [])
            if not observations:
                logger.warning(f"No observations for {series_id}")
                return None

            # Get latest non-missing observation
            for obs in observations:
                value_str = obs.get('value', '.')
                if value_str != '.':
                    try:
                        value = Decimal(value_str)
                        metadata = {
                            'fred_series_id': series_id,
                            'observation_date': obs.get('date'),
                            'realtime_start': obs.get('realtime_start'),
                            'realtime_end': obs.get('realtime_end'),
                            'fetch_timestamp': datetime.now(timezone.utc).isoformat()
                        }
                        logger.info(f"FRED {series_id}: {value} (date: {obs.get('date')})")
                        return (value, response_hash, metadata)
                    except (InvalidOperation, ValueError):
                        continue

            logger.warning(f"No valid values for {series_id}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"FRED API error for {series_id}: {e}")
            return None

    # =========================================================================
    # OUTCOME RECORDING
    # =========================================================================

    def record_outcome(self, event: Dict, value: Decimal,
                       response_hash: str, metadata: Dict) -> bool:
        """Record outcome in database with full lineage."""
        event_id = str(event['event_id'])
        event_type = event['event_type_code']

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                # Apply transform if needed
                mapping = FRED_SERIES_MAP[event_type]
                transform = mapping.get('transform')
                if transform:
                    value = Decimal(str(transform(float(value))))

                # Record lineage proof
                cur.execute("""
                    INSERT INTO fhq_calendar.data_lineage_proof (
                        lineage_id, event_id, source_code,
                        api_request_timestamp, api_response_hash,
                        extracted_value, extraction_path,
                        verified_by, verified_at
                    ) VALUES (
                        gen_random_uuid(), %s, 'FRED',
                        NOW(), %s, %s, %s,
                        'EconomicOutcomeDaemon', NOW()
                    )
                    ON CONFLICT (event_id) DO UPDATE SET
                        api_response_hash = EXCLUDED.api_response_hash,
                        extracted_value = EXCLUDED.extracted_value,
                        verified_at = NOW()
                """, (event_id, response_hash, str(value), json.dumps(metadata)))

                # Update calendar event
                cur.execute("""
                    UPDATE fhq_calendar.calendar_events
                    SET actual_value = %s,
                        lineage_status = 'VERIFIED',
                        updated_at = NOW()
                    WHERE event_id = %s
                    RETURNING consensus_estimate
                """, (str(value), event_id))

                result = cur.fetchone()
                consensus = result['consensus_estimate'] if result else None

                # Compute surprise score
                if consensus:
                    try:
                        surprise = value - Decimal(str(consensus))
                        cur.execute("""
                            UPDATE fhq_calendar.calendar_events
                            SET surprise_score = %s
                            WHERE event_id = %s
                        """, (str(surprise), event_id))
                    except:
                        pass

                self.conn.commit()
                logger.info(f"Recorded {event_type}: actual={value}, consensus={consensus}")
                return True

            except Exception as e:
                self.conn.rollback()
                logger.error(f"Failed to record outcome: {e}")
                return False

    def evaluate_hypothesis(self, event_id: str) -> bool:
        """Evaluate hypothesis for event if one exists."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check for linked hypothesis
            cur.execute("""
                SELECT
                    h.hypothesis_id,
                    h.expected_direction,
                    ce.actual_value,
                    ce.consensus_estimate,
                    ce.surprise_score,
                    ce.event_timestamp
                FROM fhq_learning.hypothesis_ledger h
                JOIN fhq_calendar.calendar_events ce ON h.event_id = ce.event_id
                WHERE h.event_id = %s
            """, (event_id,))

            hyp = cur.fetchone()
            if not hyp:
                return False

            surprise = hyp['surprise_score']
            if surprise is None:
                return False

            surprise_val = Decimal(str(surprise))

            # Map to constraint values
            actual_dir = 'BULLISH' if surprise_val > 0 else ('BEARISH' if surprise_val < 0 else 'NEUTRAL')
            expected = hyp['expected_direction'].upper()
            if expected in ('UP', 'POSITIVE'):
                expected = 'BULLISH'
            elif expected in ('DOWN', 'NEGATIVE'):
                expected = 'BEARISH'
            else:
                expected = 'NEUTRAL'

            is_correct = (actual_dir == expected)
            verdict = 'VALIDATED' if is_correct else 'FALSIFIED'

            eval_hours = (datetime.now(timezone.utc) -
                         hyp['event_timestamp'].replace(tzinfo=timezone.utc)).total_seconds() / 3600

            # Check if outcome exists
            cur.execute("""
                SELECT outcome_id FROM fhq_learning.expectation_outcome_ledger
                WHERE hypothesis_id = %s
            """, (str(hyp['hypothesis_id']),))

            existing = cur.fetchone()

            if existing:
                cur.execute("""
                    UPDATE fhq_learning.expectation_outcome_ledger
                    SET actual_direction = %s,
                        actual_value = %s,
                        consensus_value = %s,
                        surprise_score = %s,
                        learning_verdict = %s,
                        verdict_rationale = %s,
                        recorded_at = NOW(),
                        evaluation_hours = %s
                    WHERE hypothesis_id = %s
                """, (
                    actual_dir,
                    str(hyp['actual_value']) if hyp['actual_value'] else None,
                    str(hyp['consensus_estimate']) if hyp['consensus_estimate'] else None,
                    str(surprise_val),
                    verdict,
                    f"Auto-evaluated by daemon. Expected {expected}, actual {actual_dir}.",
                    round(eval_hours, 2),
                    str(hyp['hypothesis_id'])
                ))
            else:
                cur.execute("""
                    INSERT INTO fhq_learning.expectation_outcome_ledger (
                        outcome_id, hypothesis_id, actual_direction,
                        actual_value, consensus_value, surprise_score,
                        learning_verdict, verdict_rationale,
                        recorded_at, recorded_by, recorded_within_24h,
                        evaluation_hours, evidence_hash
                    ) VALUES (
                        gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s,
                        NOW(), 'EconomicOutcomeDaemon', %s, %s, %s
                    )
                """, (
                    str(hyp['hypothesis_id']),
                    actual_dir,
                    str(hyp['actual_value']) if hyp['actual_value'] else None,
                    str(hyp['consensus_estimate']) if hyp['consensus_estimate'] else None,
                    str(surprise_val),
                    verdict,
                    f"Auto-evaluated by daemon. Expected {expected}, actual {actual_dir}.",
                    eval_hours <= 24,
                    round(eval_hours, 2),
                    hashlib.sha256(f"{hyp['hypothesis_id']}-{verdict}".encode()).hexdigest()[:16]
                ))

            self.conn.commit()
            logger.info(f"Hypothesis evaluated: {verdict} (expected {expected}, actual {actual_dir})")
            return True

    # =========================================================================
    # MAIN DAEMON LOOP
    # =========================================================================

    def run_cycle(self) -> Dict:
        """Run one fetch cycle."""
        self.cycle_count += 1
        cycle_start = datetime.now(timezone.utc)

        results = {
            'cycle': self.cycle_count,
            'timestamp': cycle_start.isoformat(),
            'events_checked': 0,
            'events_fetched': 0,
            'hypotheses_evaluated': 0,
            'errors': []
        }

        try:
            # Get events ready for fetching
            events = self.get_events_ready_for_fetch()
            results['events_checked'] = len(events)

            for event in events:
                event_type = event['event_type_code']
                event_id = str(event['event_id'])

                mapping = FRED_SERIES_MAP[event_type]
                series_id = mapping['series_id']

                # Fetch from FRED
                fred_result = self.fetch_from_fred(series_id, event['event_timestamp'])
                if not fred_result:
                    continue

                value, response_hash, metadata = fred_result

                # Record outcome
                if self.record_outcome(event, value, response_hash, metadata):
                    results['events_fetched'] += 1
                    self.total_fetched += 1

                    # Evaluate hypothesis
                    if self.evaluate_hypothesis(event_id):
                        results['hypotheses_evaluated'] += 1

            # Register heartbeat periodically
            if (not self.last_heartbeat or
                (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds() > HEARTBEAT_INTERVAL_SECONDS):
                self.register_heartbeat()

        except Exception as e:
            logger.error(f"Cycle error: {e}")
            results['errors'].append(str(e))
            # Try to reconnect
            try:
                self.reconnect()
            except:
                pass

        return results

    def run_daemon(self):
        """Run continuous daemon loop."""
        logger.info("=" * 60)
        logger.info("Economic Outcome Daemon Starting")
        logger.info(f"Check interval: {CHECK_INTERVAL_SECONDS} seconds")
        logger.info(f"Supported events: {list(FRED_SERIES_MAP.keys())}")
        logger.info("=" * 60)

        if not self.validate_api_key():
            logger.error("Cannot start daemon without FRED_API_KEY")
            return

        self.running = True

        # Setup signal handlers
        def handle_signal(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        while self.running:
            try:
                # Run fetch cycle
                results = self.run_cycle()

                # Log results
                if results['events_fetched'] > 0:
                    logger.info(
                        f"Cycle {results['cycle']}: "
                        f"Fetched {results['events_fetched']}/{results['events_checked']} events, "
                        f"Evaluated {results['hypotheses_evaluated']} hypotheses"
                    )
                else:
                    logger.debug(f"Cycle {results['cycle']}: No events ready for fetch")

                # Show upcoming events periodically
                if self.cycle_count % 12 == 1:  # Every hour
                    upcoming = self.get_upcoming_events(24)
                    if upcoming:
                        logger.info("Upcoming events (next 24h):")
                        for evt in upcoming[:5]:
                            logger.info(
                                f"  {evt['event_type_code']}: "
                                f"{evt['minutes_until']:.0f} min "
                                f"(consensus: {evt['consensus_estimate']})"
                            )

                # Sleep until next cycle
                time.sleep(CHECK_INTERVAL_SECONDS)

            except Exception as e:
                logger.error(f"Daemon error: {e}")
                time.sleep(60)  # Wait a minute before retrying

        logger.info("Daemon stopped")

    def get_status(self) -> Dict:
        """Get daemon status."""
        upcoming = self.get_upcoming_events(48)
        ready = self.get_events_ready_for_fetch()

        return {
            'daemon_name': DAEMON_NAME,
            'status': 'ACTIVE' if self.api_key else 'NO_API_KEY',
            'cycle_count': self.cycle_count,
            'total_fetched': self.total_fetched,
            'check_interval_seconds': CHECK_INTERVAL_SECONDS,
            'events_ready_for_fetch': len(ready),
            'ready_events': [
                {'type': e['event_type_code'],
                 'minutes_since': round(e['minutes_since_event'])}
                for e in ready
            ],
            'upcoming_events_24h': len(upcoming),
            'next_events': [
                {'type': e['event_type_code'],
                 'minutes_until': round(e['minutes_until']),
                 'consensus': e['consensus_estimate']}
                for e in upcoming[:5]
            ],
            'supported_event_types': list(FRED_SERIES_MAP.keys())
        }


def main():
    parser = argparse.ArgumentParser(description='Economic Outcome Daemon')
    parser.add_argument('--once', action='store_true', help='Run single cycle')
    parser.add_argument('--status', action='store_true', help='Show status')
    args = parser.parse_args()

    daemon = EconomicOutcomeDaemon()

    try:
        daemon.connect()

        if args.status:
            status = daemon.get_status()
            print(json.dumps(status, indent=2, default=str))
        elif args.once:
            results = daemon.run_cycle()
            print(json.dumps(results, indent=2, default=str))
        else:
            daemon.run_daemon()

    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        daemon.disconnect()


if __name__ == '__main__':
    main()
