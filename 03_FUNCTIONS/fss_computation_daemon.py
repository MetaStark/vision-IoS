#!/usr/bin/env python3
"""
FSS Computation Daemon - FjordHQ Skill Score
CEO-DIR-2026-023 Order C

Purpose: Compute FSS = 1 - (Brier / Brier_ref) for all assets.
Calls existing SQL function compute_fss() and logs to fss_computation_log.
Also runs backfill_fss() to populate forecast_skill_metrics.brier_skill_score.

Skill Damper Tiers (from MASTERMAP):
  FREEZE: FSS < 0.4 → Capital locked
  LOW:    FSS 0.4-0.6
  MEDIUM: FSS 0.6-0.7
  HIGH:   FSS > 0.8
"""

import os
import sys
import json
import logging
import argparse
import time
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DAEMON_NAME = 'fss_computation_daemon'
CYCLE_INTERVAL_SECONDS = 21600  # 6h

logging.basicConfig(
    level=logging.INFO,
    format='[FSS_DAEMON] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/fss_computation_daemon.log'),
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


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def compute_fss(conn, baseline_method='NAIVE') -> list:
    """Call compute_fss() SQL function and return results."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT asset_id, brier_actual, brier_ref, fss_value,
               sample_size, baseline_method, computed_for_period,
               evidence_hash
        FROM fhq_research.compute_fss(
            p_baseline_method := %s
        )
        WHERE fss_value IS NOT NULL
    """, (baseline_method,))
    return cur.fetchall()


def log_fss_results(conn, results: list, baseline_method: str) -> int:
    """Log FSS computation results to fss_computation_log."""
    if not results:
        return 0

    cur = conn.cursor()
    logged = 0
    for row in results:
        period = row.get('computed_for_period')
        # Parse daterange — format is [start,end)
        period_start = None
        period_end = None
        if period:
            period_str = str(period)
            # psycopg2 returns DateRange or string
            if hasattr(period, 'lower'):
                period_start = period.lower
                period_end = period.upper
            else:
                # Parse string format [2026-01-01,2026-02-05)
                cleaned = period_str.strip('[]() ')
                parts = cleaned.split(',')
                if len(parts) == 2:
                    period_start = parts[0].strip()
                    period_end = parts[1].strip()

        cur.execute("""
            INSERT INTO fhq_research.fss_computation_log (
                asset_id, brier_actual, brier_ref, fss_value,
                baseline_method, period_start, period_end,
                sample_size, evidence_hash, computed_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            row['asset_id'],
            row['brier_actual'],
            row['brier_ref'],
            row['fss_value'],
            baseline_method,
            period_start,
            period_end,
            row['sample_size'],
            row['evidence_hash'],
            'fss_computation_daemon'
        ))
        logged += 1

    conn.commit()
    return logged


def run_backfill(conn) -> int:
    """Run backfill_fss() to populate forecast_skill_metrics.brier_skill_score."""
    cur = conn.cursor()
    cur.execute("SELECT fhq_research.backfill_fss('NAIVE')")
    result = cur.fetchone()
    conn.commit()
    return result[0] if result else 0


def get_skill_damper_tier(fss: float) -> str:
    """Map FSS to skill damper tier per MASTERMAP."""
    if fss >= 0.8:
        return 'HIGH'
    elif fss >= 0.7:
        return 'MEDIUM'
    elif fss >= 0.4:
        return 'LOW'
    else:
        return 'FREEZE'


def heartbeat(conn, status: str, details: dict = None):
    """Update daemon heartbeat."""
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
            """, (DAEMON_NAME, status, json.dumps(details, default=decimal_default) if details else None))
            conn.commit()
    except Exception as e:
        logger.warning(f"Heartbeat failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass


def run_cycle() -> dict:
    """Run one FSS computation cycle."""
    conn = get_connection()
    try:
        logger.info("=" * 60)
        logger.info("FSS COMPUTATION DAEMON — Cycle Start")
        logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        logger.info("=" * 60)

        # 1. Compute FSS for all assets
        results = compute_fss(conn, 'NAIVE')
        logger.info(f"compute_fss() returned {len(results)} assets with valid FSS")

        if not results:
            logger.warning("No FSS results — insufficient data or no Brier scores")
            heartbeat(conn, 'DEGRADED', {'reason': 'NO_FSS_RESULTS'})
            return {'status': 'NO_DATA', 'assets': 0}

        # 2. Log results
        logged = log_fss_results(conn, results, 'NAIVE')
        logger.info(f"Logged {logged} FSS entries to fss_computation_log")

        # 3. Run backfill to update forecast_skill_metrics
        try:
            backfilled = run_backfill(conn)
            logger.info(f"Backfilled {backfilled} forecast_skill_metrics rows")
        except Exception as e:
            logger.warning(f"Backfill failed (non-fatal): {e}")
            conn.rollback()
            backfilled = 0

        # 4. Compute system-level summary
        fss_values = [float(r['fss_value']) for r in results if r['fss_value'] is not None]
        avg_fss = sum(fss_values) / len(fss_values) if fss_values else 0.0
        min_fss = min(fss_values) if fss_values else 0.0
        max_fss = max(fss_values) if fss_values else 0.0
        system_tier = get_skill_damper_tier(avg_fss)

        logger.info(f"System FSS: avg={avg_fss:.4f} min={min_fss:.4f} max={max_fss:.4f}")
        logger.info(f"Skill Damper Tier: {system_tier}")

        # Per-asset detail
        for r in results:
            fss = float(r['fss_value'])
            tier = get_skill_damper_tier(fss)
            logger.info(f"  {r['asset_id']:12s} FSS={fss:.4f} Brier={float(r['brier_actual']):.4f} "
                        f"ref={float(r['brier_ref']):.4f} n={r['sample_size']} tier={tier}")

        # 5. Evidence file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence = {
            'daemon': DAEMON_NAME,
            'directive': 'CEO-DIR-2026-023-ORDER-C',
            'evidence_type': 'FSS_COMPUTATION',
            'computed_at': datetime.now(timezone.utc).isoformat(),
            'system_fss': round(avg_fss, 4),
            'system_tier': system_tier,
            'asset_count': len(results),
            'logged': logged,
            'backfilled': backfilled,
            'assets': [
                {
                    'asset_id': r['asset_id'],
                    'fss': float(r['fss_value']),
                    'brier': float(r['brier_actual']),
                    'sample_size': r['sample_size'],
                    'tier': get_skill_damper_tier(float(r['fss_value']))
                }
                for r in results
            ]
        }
        evidence_path = os.path.join(script_dir, 'evidence', f'FSS_COMPUTATION_{timestamp}.json')
        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2, default=decimal_default)
        logger.info(f"Evidence: {evidence_path}")

        # 6. Heartbeat
        heartbeat(conn, 'HEALTHY', {
            'system_fss': round(avg_fss, 4),
            'system_tier': system_tier,
            'asset_count': len(results),
            'logged': logged,
        })

        return {
            'status': 'SUCCESS',
            'system_fss': round(avg_fss, 4),
            'system_tier': system_tier,
            'assets': len(results),
            'logged': logged,
            'backfilled': backfilled,
        }

    except Exception as e:
        logger.error(f"FSS computation failed: {e}")
        try:
            heartbeat(conn, 'DEGRADED', {'error': str(e)})
        except Exception:
            pass
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='FSS Computation Daemon')
    parser.add_argument('--once', action='store_true',
                        help='Run a single computation then exit')
    parser.add_argument('--interval', type=int, default=CYCLE_INTERVAL_SECONDS,
                        help=f'Cycle interval in seconds (default: {CYCLE_INTERVAL_SECONDS})')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("FSS COMPUTATION DAEMON")
    logger.info(f"  mode={'once' if args.once else 'continuous'}")
    logger.info(f"  interval={args.interval}s")
    logger.info(f"  formula: FSS = 1 - (Brier / Brier_ref)")
    logger.info("=" * 60)

    if args.once:
        result = run_cycle()
        print(json.dumps(result, indent=2, default=decimal_default))
        return

    while True:
        try:
            run_cycle()
        except Exception as e:
            logger.error(f"Cycle failed: {e}")
        logger.info(f"Next cycle in {args.interval}s")
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
