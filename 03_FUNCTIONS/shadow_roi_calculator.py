#!/usr/bin/env python3
"""
SHADOW ROI CALCULATOR
=====================
Populates fhq_execution.capital_ledger from CLOSED shadow_trades.
Calculates aggregated shadow-ROI metrics.

Idempotent: uses LEFT JOIN on batch_id = 'SHADOW_TRADE_PNL_' || shadow_trade_ref
to skip trades already written.

Database operations:
  READS:  fhq_execution.shadow_trades (status=CLOSED)
  WRITES: fhq_execution.capital_ledger, fhq_monitoring.daemon_health

Usage:
    python shadow_roi_calculator.py              # Process all CLOSED trades
    python shadow_roi_calculator.py --check      # Dry run
    python shadow_roi_calculator.py --status     # Show ROI summary

Author: STIG (CTO)
Date: 2026-01-31
Contract: EC-003_2026_PRODUCTION
"""

import os
import sys
import json
import hashlib
import logging
import argparse
import math
from datetime import datetime, timezone
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[SHADOW_ROI] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/shadow_roi_calculator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('shadow_roi')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

BATCH_PREFIX = 'SHADOW_TRADE_PNL_'


def compute_evidence_hash(trade: dict) -> str:
    """Deterministic hash of trade data for audit trail."""
    payload = json.dumps({
        'shadow_trade_ref': trade['shadow_trade_ref'],
        'asset_id': trade['asset_id'],
        'direction': trade['direction'],
        'entry_price': str(trade['entry_price']),
        'exit_price': str(trade['exit_price']),
        'shadow_pnl': str(trade['shadow_pnl']),
        'shadow_return_pct': str(trade['shadow_return_pct']),
    }, sort_keys=True)
    return hashlib.md5(payload.encode()).hexdigest()


def find_unprocessed_closed_trades(conn) -> list:
    """
    Find CLOSED shadow_trades not yet in capital_ledger.
    Idempotent via LEFT JOIN on batch_id convention.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                st.shadow_trade_ref,
                st.asset_id,
                st.direction,
                st.entry_price,
                st.exit_price,
                st.entry_time,
                st.exit_time,
                st.entry_regime,
                st.exit_regime,
                st.shadow_pnl,
                st.shadow_return_pct,
                st.max_favorable_excursion,
                st.max_adverse_excursion,
                st.entry_confidence,
                st.shadow_size,
                st.exit_reason,
                st.source_hypothesis_id
            FROM fhq_execution.shadow_trades st
            LEFT JOIN fhq_execution.capital_ledger cl
                ON cl.batch_id = %s || st.shadow_trade_ref
            WHERE st.status = 'CLOSED'
              AND cl.ledger_id IS NULL
            ORDER BY st.exit_time
        """, (BATCH_PREFIX,))
        return cur.fetchall()


def get_next_run_number(conn) -> int:
    """Get next run_number for capital_ledger inserts."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COALESCE(MAX(run_number), 0) + 1
            FROM fhq_execution.capital_ledger
            WHERE batch_id LIKE %s
        """, (BATCH_PREFIX + '%',))
        return cur.fetchone()[0]


def insert_trade_to_ledger(conn, trade: dict, run_number: int,
                           dry_run: bool = False) -> dict:
    """Insert a single CLOSED shadow_trade into capital_ledger."""
    batch_id = BATCH_PREFIX + trade['shadow_trade_ref']
    pnl_usd = float(trade['shadow_pnl'] or 0)
    pnl_pct = float(trade['shadow_return_pct'] or 0)
    mfe = float(trade['max_favorable_excursion'] or 0)
    mae = float(trade['max_adverse_excursion'] or 0)
    entry_regime = trade['entry_regime']
    exit_regime = trade['exit_regime']
    regime_mismatch = (entry_regime != exit_regime) if entry_regime and exit_regime else False
    evidence_hash = compute_evidence_hash(trade)

    # Win proxy: 1 if positive P&L, 0 otherwise
    win = 1.0 if pnl_usd > 0 else 0.0
    # Payoff ratio proxy: abs(pnl) / mae if mae > 0
    payoff = abs(pnl_usd) / mae if mae > 0 else 0.0

    row = {
        'batch_id': batch_id,
        'run_number': run_number,
        'simulated_pnl_usd': round(pnl_usd, 2),
        'simulated_pnl_pct': round(pnl_pct, 4),
        'max_favorable_excursion': round(mfe, 8),
        'max_adverse_excursion': round(mae, 8),
        'regime_at_entry': entry_regime,
        'regime_at_exit': exit_regime,
        'regime_mismatch': regime_mismatch,
        'win_rate_proxy': round(win, 4),
        'payoff_ratio_proxy': round(payoff, 4),
        'evidence_hash': evidence_hash,
    }

    if not dry_run:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_execution.capital_ledger
                    (batch_id, run_number, simulated_pnl_usd, simulated_pnl_pct,
                     max_favorable_excursion, max_adverse_excursion,
                     regime_at_entry, regime_at_exit, regime_mismatch,
                     win_rate_proxy, payoff_ratio_proxy, evidence_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING ledger_id
            """, (
                row['batch_id'], row['run_number'],
                row['simulated_pnl_usd'], row['simulated_pnl_pct'],
                row['max_favorable_excursion'], row['max_adverse_excursion'],
                row['regime_at_entry'], row['regime_at_exit'],
                row['regime_mismatch'],
                row['win_rate_proxy'], row['payoff_ratio_proxy'],
                row['evidence_hash'],
            ))
            ledger_id = cur.fetchone()[0]
            row['ledger_id'] = str(ledger_id)
        logger.info(f"  Inserted: {batch_id} | P&L=${pnl_usd:+.2f} ({pnl_pct:+.4f}%)"
                    f" | regime={entry_regime}->{exit_regime}")
    else:
        logger.info(f"  [DRY RUN] Would insert: {batch_id} | P&L=${pnl_usd:+.2f}"
                    f" ({pnl_pct:+.4f}%)")

    return row


def register_heartbeat(conn, trades_processed: int, dry_run: bool = False):
    """Register heartbeat in fhq_monitoring.daemon_health."""
    if dry_run:
        logger.info("[DRY RUN] Would register heartbeat for shadow_roi_calculator")
        return

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_monitoring.daemon_health
                (daemon_name, status, last_heartbeat, expected_interval_minutes,
                 lifecycle_status, metadata)
            VALUES
                ('shadow_roi_calculator', 'HEALTHY', NOW(), 1440,
                 'ACTIVE',
                 %s::jsonb)
            ON CONFLICT (daemon_name) DO UPDATE SET
                status = 'HEALTHY',
                last_heartbeat = NOW(),
                expected_interval_minutes = 1440,
                lifecycle_status = 'ACTIVE',
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
        """, (json.dumps({
            'trades_processed': trades_processed,
            'last_run': datetime.now(timezone.utc).isoformat(),
            'contract': 'EC-003_2026_PRODUCTION',
        }),))
    logger.info("Heartbeat registered: shadow_roi_calculator HEALTHY (1440 min)")


def compute_aggregate_roi(conn) -> dict:
    """Compute aggregate shadow-ROI from all SHADOW_TRADE_PNL entries in capital_ledger."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(simulated_pnl_usd) as total_pnl_usd,
                AVG(simulated_pnl_pct) as avg_return_pct,
                STDDEV(simulated_pnl_pct) as stddev_return_pct,
                SUM(CASE WHEN simulated_pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN simulated_pnl_usd <= 0 THEN 1 ELSE 0 END) as losses,
                AVG(max_favorable_excursion) as avg_mfe,
                AVG(max_adverse_excursion) as avg_mae,
                SUM(CASE WHEN regime_mismatch THEN 1 ELSE 0 END) as regime_mismatches
            FROM fhq_execution.capital_ledger
            WHERE batch_id LIKE %s
        """, (BATCH_PREFIX + '%',))
        row = cur.fetchone()

    total = int(row['total_trades'] or 0)
    if total == 0:
        return {'total_trades': 0}

    wins = int(row['wins'] or 0)
    total_pnl = float(row['total_pnl_usd'] or 0)
    avg_ret = float(row['avg_return_pct'] or 0)
    std_ret = float(row['stddev_return_pct'] or 0)

    # Sharpe proxy: avg_return / stddev (annualized not applicable for shadow)
    sharpe_proxy = avg_ret / std_ret if std_ret > 0 else 0.0

    return {
        'total_trades': total,
        'total_pnl_usd': round(total_pnl, 2),
        'win_rate': round(wins / total, 4) if total > 0 else 0,
        'wins': wins,
        'losses': int(row['losses'] or 0),
        'avg_return_pct': round(avg_ret, 4),
        'stddev_return_pct': round(std_ret, 4),
        'sharpe_proxy': round(sharpe_proxy, 4),
        'avg_mfe': round(float(row['avg_mfe'] or 0), 8),
        'avg_mae': round(float(row['avg_mae'] or 0), 8),
        'regime_mismatches': int(row['regime_mismatches'] or 0),
    }


def run_shadow_roi(dry_run: bool = False):
    """Main entry: process CLOSED shadow_trades into capital_ledger."""
    logger.info("=" * 60)
    logger.info("SHADOW ROI CALCULATOR — Processing CLOSED shadow trades")
    logger.info(f"  dry_run={dry_run}")
    logger.info("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        unprocessed = find_unprocessed_closed_trades(conn)
        next_run = get_next_run_number(conn)

        if not unprocessed:
            logger.info("No new CLOSED shadow trades to process")
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM fhq_execution.shadow_trades
                    WHERE status = 'CLOSED'
                """)
                closed_cnt = cur.fetchone()[0]
                cur.execute("""
                    SELECT COUNT(*) FROM fhq_execution.capital_ledger
                    WHERE batch_id LIKE %s
                """, (BATCH_PREFIX + '%',))
                ledger_cnt = cur.fetchone()[0]
            logger.info(f"  CLOSED shadow_trades: {closed_cnt}")
            logger.info(f"  capital_ledger (shadow): {ledger_cnt}")
            logger.info(f"  All {closed_cnt} trades already in ledger — idempotent")

            # Still register heartbeat even if nothing new
            register_heartbeat(conn, 0, dry_run)
            conn.commit()

            # Still compute and log aggregate ROI
            roi = compute_aggregate_roi(conn)
            logger.info(f"  Aggregate shadow-ROI: {json.dumps(roi, indent=2)}")
            return

        results = []
        run_num = next_run
        for trade in unprocessed:
            row = insert_trade_to_ledger(conn, trade, run_num, dry_run)
            results.append(row)
            run_num += 1

        if not dry_run:
            conn.commit()

        register_heartbeat(conn, len(results), dry_run)
        if not dry_run:
            conn.commit()

        # Aggregate ROI
        roi = compute_aggregate_roi(conn)

        # Summary
        logger.info("=" * 60)
        logger.info(f"SHADOW ROI SUMMARY: {len(results)} new trades processed")
        logger.info(f"  Total P&L: ${roi.get('total_pnl_usd', 0):+,.2f}")
        logger.info(f"  Win rate: {roi.get('win_rate', 0):.1%} "
                    f"({roi.get('wins', 0)}W / {roi.get('losses', 0)}L)")
        logger.info(f"  Avg return: {roi.get('avg_return_pct', 0):+.4f}%")
        logger.info(f"  Sharpe proxy: {roi.get('sharpe_proxy', 0):.4f}")
        logger.info(f"  Regime mismatches: {roi.get('regime_mismatches', 0)}")
        logger.info("=" * 60)

        # Evidence
        evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence = {
            'executed_at': datetime.now(timezone.utc).isoformat(),
            'executed_by': 'STIG_SHADOW_ROI',
            'contract': 'EC-003_2026_PRODUCTION',
            'dry_run': dry_run,
            'new_trades_processed': len(results),
            'aggregate_roi': roi,
            'trades': results,
        }
        evidence_path = os.path.join(evidence_dir, f'SHADOW_ROI_{ts}.json')
        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)
        logger.info(f"Evidence: {evidence_path}")

    finally:
        conn.close()


def show_status():
    """Show current shadow-ROI status summary."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        roi = compute_aggregate_roi(conn)

        print("\n=== SHADOW ROI STATUS ===\n")
        if roi['total_trades'] == 0:
            print("  (empty — no shadow trades in capital_ledger)")
            return

        print(f"  Total trades:       {roi['total_trades']}")
        print(f"  Total P&L:          ${roi['total_pnl_usd']:+,.2f}")
        print(f"  Win rate:           {roi['win_rate']:.1%} "
              f"({roi['wins']}W / {roi['losses']}L)")
        print(f"  Avg return:         {roi['avg_return_pct']:+.4f}%")
        print(f"  Std dev return:     {roi['stddev_return_pct']:.4f}%")
        print(f"  Sharpe proxy:       {roi['sharpe_proxy']:.4f}")
        print(f"  Avg MFE:            {roi['avg_mfe']:.8f}")
        print(f"  Avg MAE:            {roi['avg_mae']:.8f}")
        print(f"  Regime mismatches:  {roi['regime_mismatches']}")

        # Per-trade detail
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT batch_id, run_number, simulated_pnl_usd, simulated_pnl_pct,
                       regime_at_entry, regime_at_exit, regime_mismatch,
                       win_rate_proxy, evidence_hash
                FROM fhq_execution.capital_ledger
                WHERE batch_id LIKE %s
                ORDER BY run_number
            """, (BATCH_PREFIX + '%',))
            rows = cur.fetchall()

        print(f"\n  --- Per-trade detail ---")
        for r in rows:
            ref = r['batch_id'].replace(BATCH_PREFIX, '')
            pnl = float(r['simulated_pnl_usd'] or 0)
            pct = float(r['simulated_pnl_pct'] or 0)
            regime = f"{r['regime_at_entry']}->{r['regime_at_exit']}"
            mismatch = " [MISMATCH]" if r['regime_mismatch'] else ""
            win = "W" if float(r['win_rate_proxy'] or 0) > 0 else "L"
            print(f"  #{r['run_number']:>2} {ref}: ${pnl:+.2f} ({pct:+.4f}%) "
                  f"{regime}{mismatch} [{win}]")

        # Daemon health
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT status, last_heartbeat, lifecycle_status
                FROM fhq_monitoring.daemon_health
                WHERE daemon_name = 'shadow_roi_calculator'
            """)
            health = cur.fetchone()

        if health:
            print(f"\n  Daemon: {health['status']} | "
                  f"Last heartbeat: {health['last_heartbeat']} | "
                  f"Lifecycle: {health['lifecycle_status']}")
        else:
            print(f"\n  Daemon: NOT REGISTERED")

        print()
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Shadow ROI Calculator')
    parser.add_argument('--check', action='store_true', help='Dry run — no writes')
    parser.add_argument('--status', action='store_true', help='Show ROI summary')
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        run_shadow_roi(dry_run=args.check)


if __name__ == '__main__':
    main()
