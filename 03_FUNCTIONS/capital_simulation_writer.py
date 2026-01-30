#!/usr/bin/env python3
"""
CAPITAL SIMULATION WRITER
=========================
Populates capital_simulation_ledger from promoted experiments with positive shadow results.

Pipeline position: Step 6 (after shadow_tier_registry, before execution_eligibility)

When shadow_tier shows positive or awaiting shadow_result:
  1. Create simulation entry in capital_simulation_ledger
  2. Use decision_packs for entry/exit prices, position sizing
  3. Track simulated P&L at exit

Database operations:
  READS:  shadow_tier_registry, decision_packs, hypothesis_canon
  WRITES: capital_simulation_ledger

Usage:
    python capital_simulation_writer.py              # Process all eligible
    python capital_simulation_writer.py --check      # Dry run
    python capital_simulation_writer.py --status     # Show simulation status

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
    format='[CAP_SIM] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/capital_simulation_writer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('capital_sim')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Default simulation parameters
DEFAULT_POSITION_USD = 1000.0  # $1000 simulated position per trade
MAX_LOSS_PCT = 0.02            # 2% max loss per position


def find_eligible_shadow_entries(conn) -> list:
    """
    Find shadow_tier_registry entries eligible for capital simulation.

    Eligible: any terminal shadow_result (including NEGATIVE for measurement).
    Excluded: CONTAMINATED only (broken lineage).
    No existing capital_simulation_ledger entry.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                str.shadow_id,
                str.source_hypothesis_id,
                str.source_experiment_id,
                str.shadow_result,
                str.shadow_confidence,
                str.shadow_metrics,
                str.cross_contamination_detected,
                hc.hypothesis_code,
                hc.expected_direction,
                hc.asset_universe,
                hc.asset_class,
                hc.current_confidence
            FROM fhq_learning.shadow_tier_registry str
            JOIN fhq_learning.hypothesis_canon hc
                ON str.source_hypothesis_id = hc.canon_id
            LEFT JOIN fhq_learning.capital_simulation_ledger csl
                ON csl.hypothesis_id = str.source_hypothesis_id
            WHERE str.shadow_result NOT IN ('CONTAMINATED')
            AND str.cross_contamination_detected = false
            AND csl.simulation_id IS NULL
            ORDER BY str.sampled_at
        """)
        return cur.fetchall()


def find_decision_packs_for_hypothesis(conn, hypothesis_id: str) -> list:
    """Find decision_packs linked to this hypothesis for pricing data."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT pack_id, asset, direction, snapshot_price,
                   entry_limit_price, take_profit_price, stop_loss_price,
                   position_usd, position_qty, kelly_fraction,
                   ewre_stop_loss_pct, ewre_take_profit_pct,
                   damped_confidence, snapshot_volatility_atr,
                   execution_status, created_at
            FROM fhq_learning.decision_packs
            WHERE hypothesis_id = %s
            ORDER BY created_at DESC
        """, (hypothesis_id,))
        return cur.fetchall()


def create_simulation(conn, shadow_entry: dict, decision_pack: dict,
                      dry_run: bool = False) -> dict:
    """Create a capital_simulation_ledger entry from shadow tier + decision pack."""
    hyp_id = str(shadow_entry['source_hypothesis_id'])
    hyp_code = shadow_entry['hypothesis_code']
    asset = decision_pack['asset']
    direction = decision_pack['direction']

    # Simulation code
    sim_code = f"SIM_{hyp_code}_{asset}_{datetime.now().strftime('%Y%m%d')}"

    # Use decision pack pricing
    entry_price = float(decision_pack['entry_limit_price'] or
                        decision_pack['snapshot_price'] or 0)
    stop_loss = float(decision_pack['stop_loss_price'] or 0)
    take_profit = float(decision_pack['take_profit_price'] or 0)
    position_usd = float(decision_pack['position_usd'] or DEFAULT_POSITION_USD)

    # Position sizing
    if entry_price > 0:
        position_qty = position_usd / entry_price
    else:
        position_qty = 0

    # Risk calculation
    if entry_price > 0 and stop_loss > 0:
        if direction.upper() == 'LONG':
            max_loss_amount = position_qty * (entry_price - stop_loss)
        else:
            max_loss_amount = position_qty * (stop_loss - entry_price)
        position_risk_pct = abs(max_loss_amount) / position_usd if position_usd > 0 else 0
    else:
        max_loss_amount = position_usd * MAX_LOSS_PCT
        position_risk_pct = MAX_LOSS_PCT

    sim = {
        'simulation_code': sim_code,
        'hypothesis_id': hyp_id,
        'asset_symbol': asset,
        'simulated_direction': direction,
        'simulated_size': round(position_qty, 6),
        'simulated_entry_price': entry_price,
        'simulated_stop_loss': stop_loss if stop_loss > 0 else None,
        'simulated_take_profit': take_profit if take_profit > 0 else None,
        'max_loss_amount': round(abs(max_loss_amount), 2),
        'position_risk_pct': round(position_risk_pct, 6),
        'status': 'OPEN',
        'is_paper_only': True,
        'real_capital_used': 0,
    }

    if not dry_run:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_learning.capital_simulation_ledger
                    (simulation_code, hypothesis_id, asset_symbol,
                     simulated_direction, simulated_size, simulated_entry_price,
                     simulated_stop_loss, simulated_take_profit,
                     max_loss_amount, position_risk_pct,
                     status, is_paper_only, real_capital_used, created_by)
                VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s,
                        'OPEN', true, 0, 'STIG_CAPITAL_SIM')
                RETURNING simulation_id
            """, (
                sim['simulation_code'],
                sim['hypothesis_id'],
                sim['asset_symbol'],
                sim['simulated_direction'],
                sim['simulated_size'],
                sim['simulated_entry_price'],
                sim['simulated_stop_loss'],
                sim['simulated_take_profit'],
                sim['max_loss_amount'],
                sim['position_risk_pct'],
            ))
            sim_id = cur.fetchone()[0]
            conn.commit()
            sim['simulation_id'] = str(sim_id)
            logger.info(f"  Created simulation: {sim_code} ({asset} {direction}) "
                        f"entry={entry_price}, SL={stop_loss}, TP={take_profit}")
    else:
        logger.info(f"  [DRY RUN] Would create: {sim_code} ({asset} {direction})")

    return sim


def run_capital_simulation(dry_run: bool = False):
    """Main entry: create simulations for all eligible shadow tier entries."""
    logger.info("=" * 60)
    logger.info("CAPITAL SIMULATION WRITER — Creating simulations from shadow tier")
    logger.info(f"  dry_run={dry_run}")
    logger.info("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        eligible = find_eligible_shadow_entries(conn)

        if not eligible:
            logger.info("No shadow tier entries eligible for simulation")

            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM fhq_learning.shadow_tier_registry")
                shadow_cnt = cur.fetchone()['cnt']
                cur.execute("SELECT COUNT(*) as cnt FROM fhq_learning.capital_simulation_ledger")
                sim_cnt = cur.fetchone()['cnt']

            logger.info(f"  shadow_tier_registry: {shadow_cnt} entries")
            logger.info(f"  capital_simulation_ledger: {sim_cnt} entries")
            return

        results = []
        for entry in eligible:
            hyp_id = str(entry['source_hypothesis_id'])
            hyp_code = entry['hypothesis_code']
            logger.info(f"Processing {hyp_code} (shadow_result={entry['shadow_result']})")

            # Find decision packs for this hypothesis
            packs = find_decision_packs_for_hypothesis(conn, hyp_id)

            if not packs:
                logger.warning(f"  No decision packs for {hyp_code} — skipping")
                continue

            # Create one simulation per unique asset in the decision packs
            seen_assets = set()
            for pack in packs:
                asset = pack['asset']
                if asset in seen_assets:
                    continue
                seen_assets.add(asset)

                sim = create_simulation(conn, entry, pack, dry_run=dry_run)
                results.append(sim)

        # Summary
        logger.info("=" * 60)
        logger.info(f"CAPITAL SIMULATION SUMMARY: {len(results)} simulations created")
        total_risk = sum(r.get('max_loss_amount', 0) for r in results)
        logger.info(f"  Total max loss exposure: ${total_risk:,.2f}")

        # Evidence
        evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence = {
            'executed_at': datetime.now(timezone.utc).isoformat(),
            'executed_by': 'STIG_CAPITAL_SIM',
            'dry_run': dry_run,
            'simulations_created': len(results),
            'total_max_loss_exposure': total_risk,
            'results': results
        }
        evidence_path = os.path.join(evidence_dir, f'CAPITAL_SIMULATION_{ts}.json')
        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)
        logger.info(f"Evidence: {evidence_path}")

    finally:
        conn.close()


def show_status():
    """Show current capital simulation status."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT simulation_code, asset_symbol, simulated_direction,
                       simulated_entry_price, simulated_stop_loss,
                       simulated_take_profit, simulated_pnl, simulated_pnl_pct,
                       status, max_loss_amount, position_risk_pct
                FROM fhq_learning.capital_simulation_ledger
                ORDER BY created_at
            """)
            sims = cur.fetchall()

        print("\n=== CAPITAL SIMULATION STATUS ===\n")
        if not sims:
            print("  (empty — no simulations yet)")
            print("  Pipeline: shadow_tier_registry -> capital_simulation_ledger")
            return

        for s in sims:
            pnl = s['simulated_pnl']
            pnl_str = f"${float(pnl):+.2f}" if pnl is not None else "OPEN"
            print(f"  {s['simulation_code']}: {s['asset_symbol']} "
                  f"{s['simulated_direction']} @ {s['simulated_entry_price']} "
                  f"| SL={s['simulated_stop_loss']} TP={s['simulated_take_profit']} "
                  f"| P&L: {pnl_str} | Status: {s['status']}")

        # Aggregate
        total_pnl = sum(float(s['simulated_pnl'] or 0) for s in sims)
        open_count = sum(1 for s in sims if s['status'] == 'OPEN')
        closed_count = sum(1 for s in sims if s['status'] != 'OPEN')
        print(f"\n  Total: {len(sims)} simulations "
              f"({open_count} open, {closed_count} closed)")
        print(f"  Total simulated P&L: ${total_pnl:+,.2f}")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Capital Simulation Writer')
    parser.add_argument('--check', action='store_true', help='Dry run')
    parser.add_argument('--status', action='store_true', help='Show status')
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        run_capital_simulation(dry_run=args.check)


if __name__ == '__main__':
    main()
