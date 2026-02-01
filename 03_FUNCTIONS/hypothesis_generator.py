#!/usr/bin/env python3
"""
Hypothesis Generator for IoS-016
CEO-DIR-2026-023 Order 5 - Populate hypothesis_ledger

Generates pre-event hypotheses for upcoming calendar events.
Links events to asset impacts and expected market reactions.
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 54322,
    'database': 'postgres',
    'user': 'postgres'
}

# Event type to asset mapping
EVENT_ASSET_MAP = {
    'US_FOMC': ['SPY', 'QQQ', 'TLT', 'GLD', 'XLF'],
    'US_CPI': ['SPY', 'QQQ', 'TLT', 'GLD'],
    'US_NFP': ['SPY', 'QQQ', 'XLF'],
    'US_CLAIMS': ['SPY', 'XLF'],
    'US_RETAIL': ['SPY', 'XLF', 'HD'],
    'US_ISM_MFG': ['SPY', 'QQQ', 'XLE'],
    'US_ISM_SVC': ['SPY', 'QQQ'],
    'US_GDP': ['SPY', 'QQQ', 'TLT'],
    'BOJ_RATE': ['SPY', 'QQQ'],
    'ECB_RATE': ['SPY', 'QQQ', 'XLF'],
    'PBOC_RATE': ['SPY', 'QQQ'],
}

# Event type to hypothesis template
HYPOTHESIS_TEMPLATES = {
    'US_FOMC': "FOMC decision expected at {consensus}. If hawkish surprise, expect risk-off. If dovish, expect risk-on rally.",
    'US_CPI': "CPI consensus {consensus}%. Higher than expected = hawkish Fed narrative, bearish equities. Lower = bullish.",
    'US_NFP': "NFP consensus {consensus}K. Strong jobs = rate hike concerns. Weak = growth concerns. Goldilocks optimal.",
    'US_CLAIMS': "Jobless claims consensus {consensus}. Higher = labor market weakness, mixed for equities.",
    'US_RETAIL': "Retail sales consensus {consensus}%. Strong = consumer resilience, bullish retail sector.",
    'US_ISM_MFG': "ISM Manufacturing consensus {consensus}. Above 50 = expansion. Below 50 = contraction risk.",
    'US_ISM_SVC': "ISM Services consensus {consensus}. Services sector health indicator for broad economy.",
    'US_GDP': "GDP growth consensus {consensus}%. Above consensus = bullish. Below = growth scare.",
    'BOJ_RATE': "BOJ rate decision. Any tightening signal impacts global carry trades.",
    'ECB_RATE': "ECB rate decision expected {consensus}%. Hawkish surprise = Euro strength, equity weakness.",
    'PBOC_RATE': "PBOC LPR decision. Cuts signal stimulus, supporting global risk appetite.",
}


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def get_upcoming_events(conn, hours_ahead: int = 168) -> List[Dict]:
    """Get calendar events in the next N hours without hypotheses."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT ce.event_id, ce.event_type_code, ce.event_timestamp,
               ce.consensus_estimate, ce.actual_value
        FROM fhq_calendar.calendar_events ce
        LEFT JOIN fhq_learning.hypothesis_ledger hl ON ce.event_id = hl.event_id
        WHERE ce.event_timestamp > NOW()
          AND ce.event_timestamp < NOW() + INTERVAL '%s hours'
          AND hl.hypothesis_id IS NULL
        ORDER BY ce.event_timestamp
    """, (hours_ahead,))

    return cur.fetchall()


def get_past_events_without_hypotheses(conn, hours_back: int = 168) -> List[Dict]:
    """Get past calendar events without hypotheses (for backfill)."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT ce.event_id, ce.event_type_code, ce.event_timestamp,
               ce.consensus_estimate, ce.actual_value
        FROM fhq_calendar.calendar_events ce
        LEFT JOIN fhq_learning.hypothesis_ledger hl ON ce.event_id = hl.event_id
        WHERE ce.event_timestamp > NOW() - INTERVAL '%s hours'
          AND ce.event_timestamp <= NOW()
          AND hl.hypothesis_id IS NULL
        ORDER BY ce.event_timestamp
    """, (hours_back,))

    return cur.fetchall()


def generate_hypothesis(event: Dict) -> Dict:
    """Generate hypothesis for a calendar event."""
    event_type = event['event_type_code']
    consensus = event['consensus_estimate'] or 'N/A'

    # Get template
    template = HYPOTHESIS_TEMPLATES.get(
        event_type,
        f"Economic event {event_type} with consensus {consensus}. Monitor for surprise impact."
    )

    # Generate hypothesis text
    hypothesis_text = template.format(consensus=consensus)

    # Get affected assets
    assets = EVENT_ASSET_MAP.get(event_type, ['SPY'])

    # Determine expected direction based on event type
    # Default to NEUTRAL as we're pre-event
    expected_direction = 'NEUTRAL'
    expected_magnitude = 'MEDIUM'

    # Calculate confidence based on consensus availability
    confidence = 0.3 if consensus != 'N/A' else 0.2

    return {
        'event_id': event['event_id'],
        'hypothesis_text': hypothesis_text,
        'expected_direction': expected_direction,
        'expected_magnitude': expected_magnitude,
        'confidence_pre_event': confidence,
        'rationale': f"Pre-event hypothesis for {event_type}. Consensus: {consensus}.",
        'asset_symbols': assets,
        'immutable_after': event['event_timestamp'],
        'created_before_event': event['event_timestamp'] > datetime.now(timezone.utc)
    }


def insert_hypothesis(conn, hypothesis: Dict) -> Optional[str]:
    """Insert hypothesis into database."""
    cur = conn.cursor()

    # Generate evidence hash
    evidence_str = json.dumps({
        'event_id': str(hypothesis['event_id']),
        'hypothesis_text': hypothesis['hypothesis_text'],
        'created_at': datetime.now(timezone.utc).isoformat()
    }, sort_keys=True)
    evidence_hash = hashlib.sha256(evidence_str.encode()).hexdigest()[:16]

    try:
        cur.execute("""
            INSERT INTO fhq_learning.hypothesis_ledger (
                event_id,
                hypothesis_text,
                expected_direction,
                expected_magnitude,
                confidence_pre_event,
                rationale,
                asset_symbols,
                created_at,
                created_by,
                created_before_event,
                immutable_after,
                evidence_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING hypothesis_id
        """, (
            hypothesis['event_id'],
            hypothesis['hypothesis_text'],
            hypothesis['expected_direction'],
            hypothesis['expected_magnitude'],
            hypothesis['confidence_pre_event'],
            hypothesis['rationale'],
            hypothesis['asset_symbols'],
            datetime.now(timezone.utc),
            'STIG',
            hypothesis['created_before_event'],
            hypothesis['immutable_after'],
            evidence_hash
        ))

        hypothesis_id = cur.fetchone()[0]
        conn.commit()
        return str(hypothesis_id)

    except Exception as e:
        logger.error(f"Failed to insert hypothesis: {e}")
        conn.rollback()
        return None


def main():
    """Main entry point."""
    logger.info("Starting Hypothesis Generator...")

    conn = get_connection()

    # Get upcoming events
    upcoming = get_upcoming_events(conn, hours_ahead=168)
    logger.info(f"Found {len(upcoming)} upcoming events without hypotheses")

    # Get past events for backfill
    past = get_past_events_without_hypotheses(conn, hours_back=168)
    logger.info(f"Found {len(past)} past events without hypotheses (backfill)")

    all_events = past + upcoming

    hypotheses_created = 0

    for event in all_events:
        hypothesis = generate_hypothesis(event)
        hypothesis_id = insert_hypothesis(conn, hypothesis)

        if hypothesis_id:
            hypotheses_created += 1
            logger.info(f"Created hypothesis {hypothesis_id} for {event['event_type_code']} @ {event['event_timestamp']}")

    # Generate evidence
    script_dir = os.path.dirname(os.path.abspath(__file__))
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    evidence = {
        'directive': 'CEO-DIR-2026-023-ORDER-5',
        'evidence_type': 'HYPOTHESIS_GENERATION',
        'computed_at': datetime.now(timezone.utc).isoformat(),
        'computed_by': 'STIG',
        'ec_contract': 'EC-003',
        'events_processed': len(all_events),
        'hypotheses_created': hypotheses_created,
        'upcoming_events': len(upcoming),
        'backfilled_events': len(past)
    }

    evidence_path = os.path.join(script_dir, 'evidence', f'HYPOTHESIS_GENERATION_{timestamp}.json')
    with open(evidence_path, 'w') as f:
        json.dump(evidence, f, indent=2)

    logger.info(f"Evidence saved to: {evidence_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("HYPOTHESIS GENERATION SUMMARY")
    print("=" * 60)
    print(f"Events processed:     {len(all_events)}")
    print(f"Hypotheses created:   {hypotheses_created}")
    print(f"Upcoming events:      {len(upcoming)}")
    print(f"Backfilled events:    {len(past)}")
    print("=" * 60)

    conn.close()
    return evidence


if __name__ == '__main__':
    main()
