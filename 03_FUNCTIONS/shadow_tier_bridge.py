#!/usr/bin/env python3
"""
SHADOW TIER BRIDGE
==================
Links promoted hypotheses to shadow trades via shadow_tier_registry.

Pipeline position: Step 5 (after promotion_gate_audit PASS, before capital_simulation)

When promotion_gate_audit gives gate_result = 'PASS':
  1. Create shadow_tier_registry entry linking hypothesis → shadow environment
  2. Match existing shadow_trades to hypotheses via asset + direction
  3. Monitor cross_contamination_detected flag

Database operations:
  READS:  promotion_gate_audit, hypothesis_canon, experiment_registry,
          fhq_execution.shadow_trades
  WRITES: shadow_tier_registry

Usage:
    python shadow_tier_bridge.py              # Process all promoted hypotheses
    python shadow_tier_bridge.py --check      # Dry run
    python shadow_tier_bridge.py --status     # Show current shadow tier status

Author: STIG (CTO)
Date: 2026-01-29
Contract: EC-003_2026_PRODUCTION
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timezone
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[SHADOW_BRIDGE] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/shadow_tier_bridge.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('shadow_bridge')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


def find_promoted_hypotheses(conn) -> list:
    """Find hypotheses that passed promotion gate but have no shadow_tier_registry entry."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                pga.hypothesis_id,
                pga.gate_result,
                pga.metrics_snapshot,
                pga.evaluated_at,
                hc.hypothesis_code,
                hc.asset_universe,
                hc.expected_direction,
                hc.asset_class,
                hc.current_confidence,
                er.experiment_id,
                er.experiment_code
            FROM fhq_learning.promotion_gate_audit pga
            JOIN fhq_learning.hypothesis_canon hc ON pga.hypothesis_id = hc.canon_id
            JOIN fhq_learning.experiment_registry er ON er.hypothesis_id = hc.canon_id
            LEFT JOIN fhq_learning.shadow_tier_registry str
                ON str.source_hypothesis_id = pga.hypothesis_id
            WHERE pga.gate_result = 'PASS'
            AND str.shadow_id IS NULL
            AND er.status IN ('RUNNING', 'COMPLETED')
            ORDER BY pga.evaluated_at
        """)
        return cur.fetchall()


def find_matching_shadow_trades(conn, hypothesis: dict) -> list:
    """Find shadow_trades that match a hypothesis by asset and direction."""
    asset_universe = hypothesis['asset_universe'] or []
    direction = hypothesis['expected_direction']

    if not asset_universe:
        logger.warning(f"  No asset_universe for {hypothesis['hypothesis_code']}")
        return []

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Match by asset_id IN asset_universe AND direction
        cur.execute("""
            SELECT trade_id, shadow_trade_ref, source_hypothesis_id,
                   asset_id, direction, entry_price, entry_time,
                   shadow_pnl, shadow_return_pct, status
            FROM fhq_execution.shadow_trades
            WHERE asset_id = ANY(%s)
            AND UPPER(direction) = UPPER(%s)
            ORDER BY entry_time
        """, (asset_universe, direction))
        return cur.fetchall()


def check_cross_contamination(hypothesis: dict, shadow_trades: list) -> bool:
    """
    Detect cross-contamination: shadow trades that reference a different hypothesis.

    If shadow_trades.source_hypothesis_id points to a different hypothesis than
    the one being promoted, flag contamination.
    """
    hyp_id = str(hypothesis['hypothesis_id'])
    for trade in shadow_trades:
        source = trade.get('source_hypothesis_id')
        if source and str(source) != hyp_id:
            logger.warning(
                f"  Cross-contamination detected: trade {trade['shadow_trade_ref']} "
                f"has source_hypothesis_id={source} but promoting {hyp_id}"
            )
            return True
    return False


def create_shadow_tier_entry(conn, hypothesis: dict, shadow_trades: list,
                             contaminated: bool, dry_run: bool = False) -> dict:
    """Create shadow_tier_registry entry for a promoted hypothesis."""
    hyp_id = str(hypothesis['hypothesis_id'])
    exp_id = str(hypothesis['experiment_id'])
    hyp_code = hypothesis['hypothesis_code']

    # Compute shadow metrics from matched trades
    shadow_metrics = {
        'matched_trades': len(shadow_trades),
        'assets_matched': list(set(t['asset_id'] for t in shadow_trades)),
        'total_shadow_pnl': sum(
            float(t['shadow_pnl'] or 0) for t in shadow_trades
        ),
        'trade_statuses': dict(),
        'promotion_gate_metrics': json.loads(
            json.dumps(hypothesis['metrics_snapshot'], default=str)
        ) if hypothesis.get('metrics_snapshot') else {}
    }

    for t in shadow_trades:
        status = t['status']
        shadow_metrics['trade_statuses'][status] = \
            shadow_metrics['trade_statuses'].get(status, 0) + 1

    # Determine shadow result
    if not shadow_trades:
        shadow_result = 'NO_TRADES_MATCHED'
    elif contaminated:
        shadow_result = 'CONTAMINATED'
    else:
        # Assess based on available P&L data
        trades_with_pnl = [t for t in shadow_trades if t['shadow_pnl'] is not None]
        if not trades_with_pnl:
            shadow_result = 'AWAITING_EXIT'
        else:
            total_pnl = sum(float(t['shadow_pnl']) for t in trades_with_pnl)
            shadow_result = 'POSITIVE' if total_pnl > 0 else 'NEGATIVE'

    shadow_confidence = float(hypothesis['current_confidence'] or 0.5)

    entry = {
        'source_hypothesis_id': hyp_id,
        'source_experiment_id': exp_id,
        'execution_environment': 'SHADOW',
        'shadow_result': shadow_result,
        'shadow_confidence': shadow_confidence,
        'shadow_metrics': shadow_metrics,
        'cross_contamination_detected': contaminated,
    }

    if not dry_run:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_learning.shadow_tier_registry
                    (source_hypothesis_id, source_experiment_id,
                     execution_environment, shadow_result, shadow_confidence,
                     shadow_metrics, cross_contamination_detected, created_by)
                VALUES (%s::uuid, %s::uuid, 'SHADOW', %s, %s,
                        %s::jsonb, %s, 'STIG_SHADOW_BRIDGE')
                RETURNING shadow_id
            """, (
                hyp_id, exp_id, shadow_result, shadow_confidence,
                json.dumps(shadow_metrics, default=str),
                contaminated
            ))
            shadow_id = cur.fetchone()[0]
            conn.commit()
            logger.info(f"  Created shadow_tier_registry: {shadow_id} "
                        f"for {hyp_code} ({shadow_result})")
            entry['shadow_id'] = str(shadow_id)
    else:
        logger.info(f"  [DRY RUN] Would create shadow_tier entry for {hyp_code} "
                     f"({shadow_result})")

    return entry


def run_shadow_bridge(dry_run: bool = False):
    """Main entry: process all promoted hypotheses."""
    logger.info("=" * 60)
    logger.info("SHADOW TIER BRIDGE — Linking promoted hypotheses to shadow trades")
    logger.info(f"  dry_run={dry_run}")
    logger.info("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        promoted = find_promoted_hypotheses(conn)

        if not promoted:
            logger.info("No promoted hypotheses pending shadow tier registration")

            # Report current state
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN gate_result = 'PASS' THEN 1 ELSE 0 END) as passed,
                           SUM(CASE WHEN gate_result = 'FAIL' THEN 1 ELSE 0 END) as failed
                    FROM fhq_learning.promotion_gate_audit
                """)
                audit = cur.fetchone()
                cur.execute("SELECT COUNT(*) as cnt FROM fhq_learning.shadow_tier_registry")
                shadow_cnt = cur.fetchone()['cnt']

            logger.info(f"  promotion_gate_audit: {audit['total']} total "
                        f"({audit['passed']} PASS, {audit['failed']} FAIL)")
            logger.info(f"  shadow_tier_registry: {shadow_cnt} entries")
            return

        results = []
        for hyp in promoted:
            logger.info(f"Processing {hyp['hypothesis_code']} "
                        f"(experiment: {hyp['experiment_code']})")

            # Find matching shadow trades
            trades = find_matching_shadow_trades(conn, hyp)
            logger.info(f"  Found {len(trades)} matching shadow trades")

            # Check contamination
            contaminated = check_cross_contamination(hyp, trades)

            # Create entry
            entry = create_shadow_tier_entry(conn, hyp, trades, contaminated,
                                             dry_run=dry_run)
            results.append(entry)

        # Summary
        logger.info("=" * 60)
        logger.info(f"SHADOW BRIDGE SUMMARY: {len(results)} entries created")
        for r in results:
            logger.info(f"  {r['source_hypothesis_id'][:8]}... -> {r['shadow_result']}")

        # Evidence
        evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence = {
            'executed_at': datetime.now(timezone.utc).isoformat(),
            'executed_by': 'STIG_SHADOW_BRIDGE',
            'dry_run': dry_run,
            'entries_created': len(results),
            'results': results
        }
        evidence_path = os.path.join(evidence_dir, f'SHADOW_BRIDGE_{ts}.json')
        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)
        logger.info(f"Evidence: {evidence_path}")

    finally:
        conn.close()


def show_status():
    """Show current shadow tier status."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Shadow tier entries
            cur.execute("""
                SELECT str.shadow_id, str.source_hypothesis_id,
                       str.shadow_result, str.shadow_confidence,
                       str.cross_contamination_detected,
                       str.sampled_at,
                       hc.hypothesis_code
                FROM fhq_learning.shadow_tier_registry str
                JOIN fhq_learning.hypothesis_canon hc
                    ON str.source_hypothesis_id = hc.canon_id
                ORDER BY str.sampled_at
            """)
            entries = cur.fetchall()

            # Promotion gate summary
            cur.execute("""
                SELECT pga.gate_result, COUNT(*) as cnt
                FROM fhq_learning.promotion_gate_audit pga
                GROUP BY pga.gate_result
            """)
            gate_summary = cur.fetchall()

            # Shadow trades
            cur.execute("""
                SELECT status, COUNT(*) as cnt
                FROM fhq_execution.shadow_trades
                GROUP BY status
            """)
            trade_summary = cur.fetchall()

        print("\n=== SHADOW TIER STATUS ===\n")

        print("Promotion Gate:")
        for g in gate_summary:
            print(f"  {g['gate_result']}: {g['cnt']}")
        if not gate_summary:
            print("  (empty)")

        print(f"\nShadow Tier Registry: {len(entries)} entries")
        for e in entries:
            print(f"  {e['hypothesis_code']}: {e['shadow_result']} "
                  f"(confidence={e['shadow_confidence']}, "
                  f"contaminated={e['cross_contamination_detected']})")
        if not entries:
            print("  (empty)")

        print("\nShadow Trades:")
        for t in trade_summary:
            print(f"  {t['status']}: {t['cnt']}")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Shadow Tier Bridge')
    parser.add_argument('--check', action='store_true', help='Dry run')
    parser.add_argument('--status', action='store_true', help='Show status')
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        run_shadow_bridge(dry_run=args.check)


if __name__ == '__main__':
    main()
