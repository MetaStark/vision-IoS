#!/usr/bin/env python3
"""
SHADOW TRADE CREATOR
====================
Creates deterministic shadow trades from hypothesis trigger events.

Pipeline position: Step 4.5 (after trigger_events exist, before shadow_tier_bridge)

For each promoted hypothesis (promotion_gate_audit.gate_result = 'PASS'):
  1. Find trigger_events with no corresponding shadow_trade
  2. Map direction (BULLISH->LONG, BEARISH->SHORT)
  3. Get current regime from regime_state
  4. INSERT into fhq_execution.shadow_trades

Idempotency: LEFT JOIN on trigger_event_id ensures each trigger creates exactly
one shadow trade. Re-running produces 0 new trades if all triggers are processed.

Safety:
  - shadow_size = 1.0 (unit observation, not capital)
  - shadow_leverage = 1.0 (no leverage)
  - status = 'OPEN' only
  - No broker API calls
  - No writes to paper_orders or trades tables

Database operations:
  READS:  promotion_gate_audit, hypothesis_canon, experiment_registry,
          trigger_events, regime_state
  WRITES: shadow_trades (fhq_execution)

Usage:
    python shadow_trade_creator.py           # Create shadow trades
    python shadow_trade_creator.py --check   # Dry run: report without writing

Author: STIG (CTO)
Date: 2026-01-30
Contract: EC-003_2026_PRODUCTION
Directive: CEO-DIR-20260130-SHADOW-EXECUTION-BRIDGE-001
"""

import os
import sys
import json
import uuid
import logging
import argparse
from datetime import datetime, timezone
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from governance_preflight import run_governance_preflight, GovernancePreflightError

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[SHADOW_CREATOR] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/shadow_trade_creator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('shadow_creator')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

DIRECTION_MAP = {
    'BULLISH': 'LONG',
    'BEARISH': 'SHORT',
    'LONG': 'LONG',
    'SHORT': 'SHORT',
    'NEUTRAL': 'NEUTRAL',
}

REGIME_MAP = {
    'BULL': 'BULL',
    'BEAR': 'BEAR',
    'SIDEWAYS': 'SIDEWAYS',
    'CRISIS': 'CRISIS',
    'STRESS': 'CRISIS',
    'UNKNOWN': 'UNKNOWN',
}


def find_eligible_hypotheses(conn) -> list:
    """Find promoted hypotheses with asset_universe that may need shadow trades."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT
                hc.canon_id,
                hc.hypothesis_code,
                hc.expected_direction,
                hc.asset_universe,
                hc.current_confidence,
                er.experiment_id,
                er.experiment_code,
                pga.evaluated_at
            FROM fhq_learning.promotion_gate_audit pga
            JOIN fhq_learning.hypothesis_canon hc ON pga.hypothesis_id = hc.canon_id
            JOIN fhq_learning.experiment_registry er ON er.hypothesis_id = hc.canon_id
            WHERE pga.gate_result IN ('PASS', 'EXPLORATION_PASS')
              AND hc.asset_universe IS NOT NULL
              AND er.status IN ('RUNNING', 'COMPLETED')
            ORDER BY pga.evaluated_at
        """)
        return cur.fetchall()


def find_unprocessed_triggers(conn, experiment_id: str) -> list:
    """Find trigger_events that have no corresponding shadow trade."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT te.trigger_event_id, te.asset_id, te.event_timestamp,
                   te.entry_price, te.evidence_hash
            FROM fhq_learning.trigger_events te
            LEFT JOIN fhq_execution.shadow_trades st
                ON st.trigger_event_id = te.trigger_event_id
            WHERE te.experiment_id = %s
              AND st.trade_id IS NULL
            ORDER BY te.event_timestamp
        """, (experiment_id,))
        return cur.fetchall()


def get_current_regime(conn) -> str:
    """Get current regime from regime_state, mapped for shadow_trades constraint."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT current_regime
            FROM fhq_meta.regime_state
            ORDER BY last_updated_at DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if not row:
            return 'UNKNOWN'
        raw = row['current_regime']
        return REGIME_MAP.get(raw, 'UNKNOWN')


def generate_trade_ref() -> str:
    """Generate unique shadow trade reference: ST-YYYYMMDD-HHMMSS-<8-char-uuid>."""
    now = datetime.now(timezone.utc)
    short_uuid = uuid.uuid4().hex[:8]
    return f"ST-{now.strftime('%Y%m%d-%H%M%S')}-{short_uuid}"


def create_shadow_trades(conn, hypothesis: dict, triggers: list,
                         regime: str, dry_run: bool = False) -> list:
    """Create shadow trades for unprocessed trigger events."""
    canon_id = str(hypothesis['canon_id'])
    direction_raw = hypothesis['expected_direction']
    direction = DIRECTION_MAP.get(direction_raw)
    if not direction:
        logger.error(f"  Unknown direction '{direction_raw}' for {hypothesis['hypothesis_code']}")
        return []

    confidence = float(hypothesis['current_confidence'] or 0.5)
    created = []

    for te in triggers:
        trade_ref = generate_trade_ref()

        trade_data = {
            'shadow_trade_ref': trade_ref,
            'trigger_event_id': str(te['trigger_event_id']),
            'source_agent': 'STIG',
            'source_hypothesis_id': canon_id,
            'asset_id': te['asset_id'],
            'direction': direction,
            'entry_price': te['entry_price'],
            'entry_time': te['event_timestamp'],
            'entry_confidence': confidence,
            'entry_regime': regime,
            'shadow_size': 1.0,
            'shadow_leverage': 1.0,
            'status': 'OPEN',
            'lineage_hash': te['evidence_hash'],
        }

        if dry_run:
            logger.info(f"  [DRY RUN] Would create: {trade_ref} | "
                        f"{te['asset_id']} {direction} @ {te['entry_price']}")
        else:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_execution.shadow_trades
                        (shadow_trade_ref, trigger_event_id, source_agent,
                         source_hypothesis_id, asset_id, direction,
                         entry_price, entry_time, entry_confidence,
                         entry_regime, shadow_size, shadow_leverage,
                         status, lineage_hash)
                    VALUES
                        (%s, %s::uuid, %s, %s, %s, %s,
                         %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING trade_id
                """, (
                    trade_ref,
                    te['trigger_event_id'],
                    'STIG',
                    canon_id,
                    te['asset_id'],
                    direction,
                    te['entry_price'],
                    te['event_timestamp'],
                    confidence,
                    regime,
                    1.0,
                    1.0,
                    'OPEN',
                    te['evidence_hash'],
                ))
                trade_id = cur.fetchone()[0]
                trade_data['trade_id'] = str(trade_id)
                logger.info(f"  Created: {trade_ref} | {te['asset_id']} "
                            f"{direction} @ {te['entry_price']} | trade_id={trade_id}")

        created.append(trade_data)

    if not dry_run and created:
        conn.commit()

    return created


def run_shadow_creator(dry_run: bool = False):
    """Main entry: find promoted hypotheses and create shadow trades for unprocessed triggers."""
    logger.info("=" * 60)
    logger.info("SHADOW TRADE CREATOR - Deterministic shadow trade generation")
    logger.info(f"  dry_run={dry_run}")
    logger.info(f"  directive=CEO-DIR-20260130-SHADOW-EXECUTION-BRIDGE-001")
    logger.info("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        # GOVERNANCE PREFLIGHT — fail-closed (CEO-DIR-010 Workstream B)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                preflight = run_governance_preflight(cur, 'SHADOW_TRADE_CREATOR')
            except GovernancePreflightError as e:
                logger.error(f"GOVERNANCE PREFLIGHT BLOCKED: {e}")
                return

        # Step 1: Find eligible hypotheses
        hypotheses = find_eligible_hypotheses(conn)
        logger.info(f"Found {len(hypotheses)} promoted hypothesis(es) with asset_universe")

        if not hypotheses:
            logger.info("No eligible hypotheses. Nothing to do.")
            # DIR-006: Write evidence for zero-eligible case
            evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
            os.makedirs(evidence_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            evidence = {
                'directive': 'CEO-DIR-20260130-SHADOW-EXECUTION-BRIDGE-001',
                'executed_at': datetime.now(timezone.utc).isoformat(),
                'executed_by': 'STIG_SHADOW_CREATOR',
                'dry_run': dry_run,
                'gate': 'NO_PROMOTED_HYPOTHESES',
                'hypotheses_processed': 0,
                'trades_created': 0,
                'hypothesis_disposition': [],
            }
            evidence_path = os.path.join(evidence_dir, f'SHADOW_TRADE_CREATOR_{ts}.json')
            with open(evidence_path, 'w') as f:
                json.dump(evidence, f, indent=2, default=str)
            logger.info(f"Evidence: {evidence_path}")
            return

        # Step 2: Get current regime
        regime = get_current_regime(conn)
        logger.info(f"Current regime: {regime}")

        total_created = 0
        all_trades = []
        hypothesis_disposition = []  # DIR-006: Per-hypothesis disposition tracking

        for hyp in hypotheses:
            logger.info(f"\nProcessing: {hyp['hypothesis_code']} "
                        f"(canon_id={str(hyp['canon_id'])[:8]}...)")
            logger.info(f"  direction={hyp['expected_direction']} -> "
                        f"{DIRECTION_MAP.get(hyp['expected_direction'], '?')}")
            logger.info(f"  experiment={hyp['experiment_code']} "
                        f"(id={str(hyp['experiment_id'])[:8]}...)")

            # Step 3: Find unprocessed triggers
            triggers = find_unprocessed_triggers(conn, str(hyp['experiment_id']))
            logger.info(f"  Unprocessed triggers: {len(triggers)}")

            if not triggers:
                logger.info("  All triggers already have shadow trades. Skipping.")
                hypothesis_disposition.append({
                    'hypothesis_code': hyp['hypothesis_code'],
                    'gate': 'ALL_TRIGGERS_PROCESSED',
                    'reason': f"0 unprocessed triggers for experiment {hyp['experiment_code']}",
                })
                continue

            # Step 4: Create shadow trades
            created = create_shadow_trades(conn, hyp, triggers, regime, dry_run)
            total_created += len(created)
            all_trades.extend(created)
            hypothesis_disposition.append({
                'hypothesis_code': hyp['hypothesis_code'],
                'gate': 'TRADES_CREATED',
                'trades_created': len(created),
            })

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info(f"SHADOW CREATOR SUMMARY")
        logger.info(f"  Hypotheses processed: {len(hypotheses)}")
        logger.info(f"  Shadow trades {'would be ' if dry_run else ''}created: {total_created}")
        logger.info("=" * 60)

        # Write evidence
        evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence = {
            'directive': 'CEO-DIR-20260130-SHADOW-EXECUTION-BRIDGE-001',
            'executed_at': datetime.now(timezone.utc).isoformat(),
            'executed_by': 'STIG_SHADOW_CREATOR',
            'dry_run': dry_run,
            'regime_at_creation': regime,
            'hypotheses_processed': len(hypotheses),
            'trades_created': total_created,
            'hypothesis_disposition': hypothesis_disposition,
            'trades': [
                {k: str(v) if isinstance(v, (uuid.UUID, Decimal)) else v
                 for k, v in t.items()}
                for t in all_trades
            ]
        }
        evidence_path = os.path.join(
            evidence_dir,
            f'SHADOW_TRADE_CREATOR_{ts}.json'
        )
        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)
        logger.info(f"Evidence: {evidence_path}")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Shadow Trade Creator')
    parser.add_argument('--check', '--dry-run', action='store_true',
                        help='Dry run: report what would be created without writing')
    args = parser.parse_args()
    run_shadow_creator(dry_run=args.check)


if __name__ == '__main__':
    main()
