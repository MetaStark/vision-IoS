#!/usr/bin/env python3
"""
IoS-016 Calendar Event Scheduler - CEO-DIR-2026-064 Order 2

Purpose: Wire IoS-016 into Orchestrator as a temporal control surface.
         Time becomes a first-class control signal.

Directive: CEO-DIR-2026-064 - Canonical Source Provider Alignment & Calendar-Orchestrator Integration
Authority Chain: ADR-001 → ADR-004 → ADR-007 → ADR-013 → ADR-016 → ADR-018

Orchestrator Responsibilities (Read-Only Authority):
1. Read upcoming events from IoS-016
2. Schedule time-based triggers using event date + time
3. At event time: trigger outcome ingestion from approved APIs
4. Post-event: verify outcome vs consensus, compute surprise, store with lineage
5. Forward knowledge only to ACI (no execution authority)

Constraints:
- No trading
- No signal generation
- No regime overrides
- This is knowledge plumbing, not strategy

Author: STIG
Date: 2026-01-17
Contract: EC-003_2026_PRODUCTION
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('IoS016CalendarScheduler')

# Database connection
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


class CalendarEventScheduler:
    """
    Temporal control surface for IoS-016 Economic Calendar.

    CEO-DIR-2026-064 Compliance:
    - Reads events, does not generate them
    - Triggers ingestion, does not execute trades
    - Forwards knowledge to ACI, no execution authority
    """

    def __init__(self):
        self.conn = None

    def connect(self):
        """Establish database connection."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Database connection established")

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    # =========================================================================
    # SECTION 1: Event Reading (Orchestrator → IoS-016)
    # =========================================================================

    def get_upcoming_events(self, hours_ahead: int = 24) -> List[Dict]:
        """
        Read upcoming events from IoS-016 calendar.

        Returns events scheduled within the next N hours.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    event_id,
                    event_type_code,
                    event_timestamp,
                    consensus_estimate,
                    previous_value,
                    source_provider,
                    lineage_status
                FROM fhq_calendar.calendar_events
                WHERE is_canonical = true
                  AND event_timestamp > NOW()
                  AND event_timestamp <= NOW() + INTERVAL '%s hours'
                  AND actual_value IS NULL  -- Not yet realized
                ORDER BY event_timestamp ASC
            """, (hours_ahead,))
            events = cur.fetchall()
            logger.info(f"Found {len(events)} upcoming events in next {hours_ahead} hours")
            return [dict(e) for e in events]

    def get_events_due_for_verification(self, hours_past: int = 4) -> List[Dict]:
        """
        Get events that have passed and need outcome verification.

        Returns events where:
        - Event timestamp has passed
        - Actual value is still NULL (not yet ingested)
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    event_id,
                    event_type_code,
                    event_timestamp,
                    consensus_estimate,
                    previous_value,
                    source_provider
                FROM fhq_calendar.calendar_events
                WHERE is_canonical = true
                  AND event_timestamp < NOW()
                  AND event_timestamp > NOW() - INTERVAL '%s hours'
                  AND actual_value IS NULL
                ORDER BY event_timestamp ASC
            """, (hours_past,))
            events = cur.fetchall()
            logger.info(f"Found {len(events)} events due for verification")
            return [dict(e) for e in events]

    # =========================================================================
    # SECTION 2: Time-Based Trigger Scheduling
    # =========================================================================

    def get_next_scheduled_event(self) -> Optional[Dict]:
        """Get the next event that needs attention."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    event_id,
                    event_type_code,
                    event_timestamp,
                    consensus_estimate,
                    source_provider,
                    EXTRACT(EPOCH FROM (event_timestamp - NOW())) / 60 as minutes_until
                FROM fhq_calendar.calendar_events
                WHERE is_canonical = true
                  AND event_timestamp > NOW()
                  AND actual_value IS NULL
                ORDER BY event_timestamp ASC
                LIMIT 1
            """)
            event = cur.fetchone()
            return dict(event) if event else None

    def should_trigger_pre_event_alert(self, event: Dict,
                                        alert_minutes_before: int = 30) -> bool:
        """Check if we should trigger a pre-event alert."""
        if not event:
            return False
        minutes_until = event.get('minutes_until', 999999)
        return 0 < minutes_until <= alert_minutes_before

    # =========================================================================
    # SECTION 3: Outcome Ingestion (Post-Event)
    # =========================================================================

    def record_event_outcome(self, event_id: str, actual_value: Decimal,
                              api_source: str, api_response_hash: str) -> bool:
        """
        Record the actual outcome of an economic event.

        This is called AFTER the event occurs, with data fetched from
        an approved API source.

        Returns True if successful, False otherwise.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                # First, record the lineage proof
                cur.execute("""
                    INSERT INTO fhq_calendar.data_lineage_proof (
                        lineage_id, event_id, source_code, api_request_timestamp,
                        api_response_hash, extracted_value, verified_by, verified_at
                    ) VALUES (
                        gen_random_uuid(), %s, %s, NOW(), %s, %s, 'ORCHESTRATOR', NOW()
                    )
                    ON CONFLICT (event_id) DO UPDATE SET
                        api_response_hash = EXCLUDED.api_response_hash,
                        extracted_value = EXCLUDED.extracted_value,
                        verified_at = NOW()
                """, (event_id, api_source, api_response_hash, actual_value))

                # Then update the calendar event with the actual value
                cur.execute("""
                    UPDATE fhq_calendar.calendar_events
                    SET actual_value = %s,
                        lineage_status = 'VERIFIED',
                        updated_at = NOW()
                    WHERE event_id = %s
                    RETURNING event_id, event_type_code, consensus_estimate, actual_value
                """, (actual_value, event_id))

                result = cur.fetchone()
                self.conn.commit()

                if result:
                    logger.info(f"Recorded outcome for {result['event_type_code']}: "
                               f"consensus={result['consensus_estimate']}, "
                               f"actual={result['actual_value']}")
                    return True

            except Exception as e:
                self.conn.rollback()
                logger.error(f"Failed to record event outcome: {e}")

        return False

    # =========================================================================
    # SECTION 4: Surprise Computation
    # =========================================================================

    def compute_surprise_score(self, event_id: str) -> Optional[Decimal]:
        """
        Compute surprise score for an event.

        Surprise = (actual - consensus) / historical_std

        Normalized by event type to allow cross-asset comparison.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    ce.event_id,
                    ce.event_type_code,
                    ce.consensus_estimate,
                    ce.actual_value,
                    etr.surprise_normalization_unit
                FROM fhq_calendar.calendar_events ce
                LEFT JOIN fhq_calendar.event_type_registry etr
                    ON ce.event_type_code = etr.event_type_code
                WHERE ce.event_id = %s
            """, (event_id,))

            event = cur.fetchone()
            if not event or event['actual_value'] is None or event['consensus_estimate'] is None:
                return None

            actual = Decimal(str(event['actual_value']))
            consensus = Decimal(str(event['consensus_estimate']))

            # Simple surprise calculation (actual - consensus)
            # Normalization would use historical_std from event_type_registry
            raw_surprise = actual - consensus

            # Store the computed surprise
            cur.execute("""
                UPDATE fhq_calendar.calendar_events
                SET surprise_score = %s, updated_at = NOW()
                WHERE event_id = %s
            """, (raw_surprise, event_id))
            self.conn.commit()

            return raw_surprise

    # =========================================================================
    # SECTION 5: Knowledge Handoff to ACI
    # =========================================================================

    def forward_to_aci(self, event_id: str) -> bool:
        """
        Forward verified event knowledge to ACI learning system.

        This is knowledge plumbing - we're informing ACI about what happened,
        not telling it what to do.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get the verified event with surprise score
            cur.execute("""
                SELECT
                    event_id,
                    event_type_code,
                    event_timestamp,
                    consensus_estimate,
                    actual_value,
                    surprise_score,
                    lineage_status
                FROM fhq_calendar.calendar_events
                WHERE event_id = %s
                  AND lineage_status = 'VERIFIED'
            """, (event_id,))

            event = cur.fetchone()
            if not event:
                logger.warning(f"Cannot forward unverified event {event_id} to ACI")
                return False

            # Log the knowledge handoff
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_id, action_type, action_target, action_target_type,
                    initiated_by, initiated_at, decision, decision_rationale
                ) VALUES (
                    gen_random_uuid(),
                    'CALENDAR_KNOWLEDGE_HANDOFF',
                    %s,
                    'EVENT',
                    'ORCHESTRATOR',
                    NOW(),
                    'FORWARDED_TO_ACI',
                    %s
                )
            """, (
                str(event['event_id']),
                f"IoS-016 event {event['event_type_code']} at {event['event_timestamp']}: "
                f"consensus={event['consensus_estimate']}, actual={event['actual_value']}, "
                f"surprise={event['surprise_score']}. Forwarded for learning integration."
            ))
            self.conn.commit()

            logger.info(f"Forwarded {event['event_type_code']} to ACI: "
                       f"surprise={event['surprise_score']}")
            return True

    # =========================================================================
    # SECTION 6: Full Scheduler Cycle
    # =========================================================================

    def run_scheduler_cycle(self) -> Dict:
        """
        Run one complete scheduler cycle.

        Flow:
        1. Check for events due for verification
        2. (Would fetch actual values from APIs - placeholder)
        3. Compute surprise scores
        4. Forward verified events to ACI
        5. Return status
        """
        results = {
            'cycle_timestamp': datetime.now(timezone.utc).isoformat(),
            'events_checked': 0,
            'events_verified': 0,
            'events_forwarded': 0,
            'upcoming_events': []
        }

        # Step 1: Get events due for verification
        due_events = self.get_events_due_for_verification(hours_past=24)
        results['events_checked'] = len(due_events)

        # Step 2: For each event, we would fetch actual value from API
        # (Placeholder - actual API integration in calendar_drift_detector.py)
        for event in due_events:
            logger.info(f"Event {event['event_type_code']} at {event['event_timestamp']} "
                       f"needs outcome verification from {event['source_provider']}")

        # Step 3: Compute surprise for any events that have actual values
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT event_id
                FROM fhq_calendar.calendar_events
                WHERE actual_value IS NOT NULL
                  AND surprise_score IS NULL
                  AND lineage_status = 'VERIFIED'
            """)
            for row in cur.fetchall():
                surprise = self.compute_surprise_score(row['event_id'])
                if surprise is not None:
                    results['events_verified'] += 1

        # Step 4: Forward verified events to ACI
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT event_id
                FROM fhq_calendar.calendar_events
                WHERE lineage_status = 'VERIFIED'
                  AND surprise_score IS NOT NULL
                  AND event_id NOT IN (
                      SELECT action_target::uuid
                      FROM fhq_governance.governance_actions_log
                      WHERE action_type = 'CALENDAR_KNOWLEDGE_HANDOFF'
                  )
            """)
            for row in cur.fetchall():
                if self.forward_to_aci(row['event_id']):
                    results['events_forwarded'] += 1

        # Step 5: Get upcoming events for status
        upcoming = self.get_upcoming_events(hours_ahead=48)
        results['upcoming_events'] = [
            {
                'event_type': e['event_type_code'],
                'timestamp': e['event_timestamp'].isoformat() if e['event_timestamp'] else None,
                'consensus': str(e['consensus_estimate']) if e['consensus_estimate'] else None
            }
            for e in upcoming[:5]  # Top 5
        ]

        return results

    def get_scheduler_status(self) -> Dict:
        """
        Get current scheduler status for orchestrator integration.

        Returns a summary of:
        - Next scheduled event
        - Events pending verification
        - Recent knowledge handoffs
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Next event
            next_event = self.get_next_scheduled_event()

            # Events pending verification
            cur.execute("""
                SELECT COUNT(*) as count
                FROM fhq_calendar.calendar_events
                WHERE is_canonical = true
                  AND event_timestamp < NOW()
                  AND actual_value IS NULL
            """)
            pending_count = cur.fetchone()['count']

            # Recent handoffs
            cur.execute("""
                SELECT COUNT(*) as count
                FROM fhq_governance.governance_actions_log
                WHERE action_type = 'CALENDAR_KNOWLEDGE_HANDOFF'
                  AND initiated_at > NOW() - INTERVAL '24 hours'
            """)
            handoff_count = cur.fetchone()['count']

            return {
                'status': 'ACTIVE',
                'next_event': {
                    'type': next_event['event_type_code'] if next_event else None,
                    'timestamp': next_event['event_timestamp'].isoformat() if next_event and next_event['event_timestamp'] else None,
                    'minutes_until': round(next_event['minutes_until'], 1) if next_event else None
                } if next_event else None,
                'pending_verification': pending_count,
                'handoffs_last_24h': handoff_count
            }


def main():
    """Main entry point for scheduler."""
    scheduler = CalendarEventScheduler()

    try:
        scheduler.connect()

        # Run one scheduler cycle
        results = scheduler.run_scheduler_cycle()

        # Print results
        print(json.dumps(results, indent=2, default=str))

        # Get status
        status = scheduler.get_scheduler_status()
        print("\nScheduler Status:")
        print(json.dumps(status, indent=2, default=str))

    except Exception as e:
        logger.error(f"Scheduler cycle failed: {e}")
        raise
    finally:
        scheduler.disconnect()


if __name__ == '__main__':
    main()
