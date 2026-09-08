#!/usr/bin/env python3
"""
LVI Calculator - Learning Velocity Index (Canonical Definition C Wrapper)
CEO-DIR-2026-SYSTEM-PRODUCTIONALIZATION-028 Directive 1.3

Purpose: Wrapper for canonical SQL-based LVI computation.
DECOMMISSIONED: Decision pack counting logic (split-brain fix).

New Canonical Definition:
  - Event = Forecast with Brier squared_error < 0.25 (skill above random)
  - Settlement Gate = Event must have terminalized outcome
  - Source: fhq_governance.compute_lvi_canonical()

Deprecated: CEO-DIR-2026-023 decision_pack counting logic.
Effective: 2026-02-16 15:00:00 UTC
"""

import os
import sys
import json
import logging
import hashlib
import argparse
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[LVI_DAEMON] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/lvi_calculator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

DAEMON_NAME = 'lvi_calculator'
CYCLE_INTERVAL_SECONDS = 86400  # 24h


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def compute_lvi(conn) -> dict:
    """
    Compute Learning Velocity Index using Canonical Definition C.

    DEPRECATED: This function now wraps fhq_governance.lvi_system_aggregate()
    instead of implementing decision_pack counting logic.

    Canonical Definition C:
    - Event = Forecast with Brier squared_error < 0.25
    - Settlement Gate = Event must have terminalized outcome
    - Formula: Σ(Learning_Event × Regime_Weight × Decay) / Σ(Decay)

    Returns:
        dict with LVI components and final score from canonical SQL
    """
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Call canonical SQL function (Definition C with settlement gate enabled)
    cur.execute("""
        SELECT * FROM fhq_governance.lvi_system_aggregate(
            p_window_days := 30,
            p_settlement_gate := TRUE
        )
    """)
    result = cur.fetchone()

    if not result:
        logger.warning("Canonical LVI function returned no results")
        return {
            'lvi_score': 0.0,
            'learning_events_counted': 0,
            'total_events_in_window': 0,
            'settlement_gate_active': True,
            'eligible_events_in_settlement': 0,
            'computed_at': datetime.now(timezone.utc).isoformat(),
            'computation_method': 'lvi_canonical_definition_c',
            'definition': 'C'
        }

    # Build return dict from canonical SQL result
    return {
        'lvi_score': round(float(result['lvi_value']), 4),
        'learning_events_counted': int(result['learning_events_counted']),
        'total_events_in_window': int(result['total_events_in_window']),
        'settlement_gate_active': bool(result['settlement_gate_active']),
        'eligible_events_in_settlement': int(result['eligible_events_in_settlement']),
        'regime_at_computation': result['regime_at_computation'],
        'regime_weight': round(float(result['regime_weight']), 4),
        'window_start': result['window_start'].isoformat() if result['window_start'] else None,
        'window_end': result['window_end'].isoformat() if result['window_end'] else None,
        'evidence_hash': result['evidence_hash'],
        'computed_at': datetime.now(timezone.utc).isoformat(),
        'computation_method': 'lvi_canonical_definition_c',
        'definition': 'C',
        'formula': 'LVI = Σ(Learning_Event × Regime_Weight × Decay) / Σ(Decay) [Canonical Definition C]'
    }


def get_current_regime(conn) -> tuple:
    """Get current market regime and confidence from fhq_meta.regime_state."""
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT current_regime, regime_confidence
            FROM fhq_meta.regime_state
            ORDER BY last_updated_at DESC LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            return row['current_regime'], float(row['regime_confidence'])
    except Exception as e:
        logger.warning(f"Could not fetch regime: {e}")
    return 'NEUTRAL', 0.5


def store_lvi(conn, lvi_data: dict) -> Optional[str]:
    """
    Store LVI snapshot using canonical SQL function.

    DEPRECATED: No longer uses decision_pack counting logic.
    Uses fhq_governance.populate_lvi_canonical_all() instead.

    Returns:
        lvi_id if stored successfully, None otherwise
    """
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Call canonical SQL function to populate lvi_canonical
        cur.execute("""
            SELECT fhq_governance.populate_lvi_canonical_all(
                p_window_days := 30,
                p_settlement_gate := TRUE
            ) as inserted_count
        """)
        result = cur.fetchone()

        if result and result['inserted_count'] > 0:
            # Fetch the newly inserted record
            cur.execute("""
                SELECT lvi_id, evidence_hash
                FROM fhq_governance.lvi_canonical
                WHERE asset_id = 'ALL'
                ORDER BY computed_at DESC
                LIMIT 1
            """)
            record = cur.fetchone()
            if record:
                conn.commit()
                logger.info(f"Stored LVI via canonical function: lvi_id={record['lvi_id']}, hash={record['evidence_hash'][:16]}...")
                return str(record['lvi_id'])

        conn.commit()
        logger.info("LVI canonical population completed (no new record returned)")
        return None

    except Exception as e:
        logger.error(f"Failed to store LVI: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return None


def generate_evidence(lvi_data: dict) -> dict:
    """Generate evidence bundle for LVI computation (Canonical Definition C)."""
    evidence = {
        'directive': 'CEO-DIR-2026-SYSTEM-PRODUCTIONALIZATION-028',
        'evidence_type': 'LVI_COMPUTATION_CANONICAL',
        'computed_at': lvi_data['computed_at'],
        'computed_by': 'STIG',
        'ec_contract': 'EC-003',
        'definition': 'C',
        'lvi_data': lvi_data,
        'interpretation': {
            'score': lvi_data['lvi_score'],
            'grade': get_lvi_grade(lvi_data['lvi_score']),
            'bottleneck': identify_bottleneck(lvi_data)
        }
    }

    # Add hash
    evidence_str = json.dumps(lvi_data, sort_keys=True)
    evidence['evidence_hash'] = hashlib.sha256(evidence_str.encode()).hexdigest()[:16]

    return evidence


def get_lvi_grade(score: float) -> str:
    """Get letter grade for LVI score."""
    if score >= 0.8:
        return 'A'
    elif score >= 0.6:
        return 'B'
    elif score >= 0.4:
        return 'C'
    elif score >= 0.2:
        return 'D'
    else:
        return 'F'


def identify_bottleneck(lvi_data: dict) -> str:
    """Identify primary bottleneck limiting LVI (Canonical Definition C)."""
    if lvi_data['learning_events_counted'] == 0:
        return 'No Brier-skilled forecasts in settlement layer - check settlement daemon'
    if lvi_data['eligible_events_in_settlement'] == 0:
        return 'Settlement gate blocking all events - outcomes not terminalized'
    if lvi_data['total_events_in_window'] < 5:
        return 'Insufficient sample size - need more Brier-skilled forecasts'
    return 'No critical bottleneck'


def heartbeat(conn, status: str, details: dict = None):
    """Update daemon heartbeat in daemon_health."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_monitoring.daemon_health (daemon_name, status, last_heartbeat, metadata)
                VALUES (%s, %s, NOW(), %s)
                ON CONFLICT (daemon_name)
                DO UPDATE SET status = EXCLUDED.status,
                              last_heartbeat = NOW(),
                              metadata = EXCLUDED.metadata,
                              updated_at = NOW()
            """, (DAEMON_NAME, status, json.dumps(details) if details else None))
            conn.commit()
    except Exception as e:
        logger.warning(f"Heartbeat failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass


def run_cycle() -> dict:
    """Run one LVI computation cycle. Returns evidence dict."""
    conn = get_connection()
    try:
        # Compute LVI
        lvi_data = compute_lvi(conn)
        grade = get_lvi_grade(lvi_data['lvi_score'])
        bottleneck = identify_bottleneck(lvi_data)
        logger.info(f"LVI computed: {lvi_data['lvi_score']:.4f} ({grade})")
        logger.info(f"  Learning Events: {lvi_data['learning_events_counted']} | "
                     f"Total Events: {lvi_data['total_events_in_window']} | "
                     f"Settlement Gate: {lvi_data['settlement_gate_active']}")
        logger.info(f"  Regime: {lvi_data['regime_at_computation']} (weight: {lvi_data['regime_weight']})")
        logger.info(f"  Bottleneck: {bottleneck}")

        # Store in database
        lvi_id = store_lvi(conn, lvi_data)

        # Generate evidence
        evidence = generate_evidence(lvi_data)

        # Save evidence file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence_path = os.path.join(script_dir, 'evidence', f'LVI_CANONICAL_C_{timestamp}.json')
        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2)
        logger.info(f"Evidence: {evidence_path}")

        # Heartbeat
        heartbeat(conn, 'HEALTHY', {
            'lvi_score': lvi_data['lvi_score'],
            'grade': grade,
            'bottleneck': bottleneck,
            'definition': 'C',
            'learning_events_counted': lvi_data['learning_events_counted'],
            'total_events_in_window': lvi_data['total_events_in_window'],
            'settlement_gate_active': lvi_data['settlement_gate_active'],
            'eligible_events_in_settlement': lvi_data['eligible_events_in_settlement']
        })

        return evidence

    except Exception as e:
        logger.error(f"LVI computation failed: {e}")
        try:
            heartbeat(conn, 'DEGRADED', {'error': str(e)})
        except Exception:
            pass
        raise
    finally:
        conn.close()


def main():
    """Main entry point for LVI Calculator Daemon (Canonical Definition C)."""
    parser = argparse.ArgumentParser(description='LVI Calculator Daemon - Canonical Definition C')
    parser.add_argument('--once', action='store_true',
                        help='Run a single computation then exit')
    parser.add_argument('--interval', type=int, default=CYCLE_INTERVAL_SECONDS,
                        help=f'Cycle interval in seconds (default: {CYCLE_INTERVAL_SECONDS})')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("LVI CALCULATOR DAEMON - CANONICAL DEFINITION C")
    logger.info("CEO-DIR-2026-SYSTEM-PRODUCTIONALIZATION-028")
    logger.info(f"  mode={'once' if args.once else 'continuous'}")
    logger.info(f"  interval={args.interval}s")
    logger.info("  Definition: C (Brier-skilled + Settlement Gate)")
    logger.info("=" * 60)

    if args.once:
        evidence = run_cycle()
        lvi = evidence['lvi_data']
        print(f"\nLVI: {lvi['lvi_score']:.4f} ({get_lvi_grade(lvi['lvi_score'])}) | "
              f"Events: {lvi['learning_events_counted']}/{lvi['total_events_in_window']} | "
              f"Settlement Gate: {'ACTIVE' if lvi['settlement_gate_active'] else 'INACTIVE'}")
        return

    # Continuous daemon loop
    while True:
        try:
            run_cycle()
        except Exception as e:
            logger.error(f"Cycle failed: {e}")
        logger.info(f"Next cycle in {args.interval}s")
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
