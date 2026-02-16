#!/usr/bin/env python3
"""
DECISION PACK GENERATOR
========================
Creates formal, auditable decision_packs from promoted hypotheses.

Pipeline position: Step 5.2 (after shadow exit engine, before capital_simulation)

For each promoted hypothesis with CLOSED shadow trades:
  1. Group shadow trades by asset
  2. Use the most recent entry_price as snapshot_price
  3. Compute EWRE stop-loss and take-profit deterministically
  4. Size position using fixed allocation (no Kelly without calibration data)
  5. Sign and hash for audit chain
  6. INSERT into fhq_learning.decision_packs

Idempotency: LEFT JOIN on (hypothesis_id, asset) ensures one pack per
hypothesis+asset combination. Re-running produces 0 new packs if all are written.

Database operations:
  READS:  promotion_gate_audit, hypothesis_canon, shadow_trades, regime_state
  WRITES: decision_packs

Constraints enforced:
  - hypothesis_id NOT NULL (CEO mandate)
  - direction IN ('LONG','SHORT')
  - All NOT NULL columns populated
  - Immutable: no UPDATE, only INSERT new versions

Usage:
    python decision_pack_generator.py           # Generate packs
    python decision_pack_generator.py --check   # Dry run

Author: STIG (CTO)
Date: 2026-01-30
Contract: EC-003_2026_PRODUCTION
Directive: CEO-DIR-20260130-PIPELINE-COMPLETION-002 D2
"""

import os
import sys
import json
import hashlib
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
    format='[PACK_GEN] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/decision_pack_generator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('pack_gen')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Risk parameters (deterministic EWRE)
EWRE_STOP_LOSS_PCT = 0.05      # 5% stop loss
EWRE_TAKE_PROFIT_PCT = 0.10    # 10% take profit
DEFAULT_POSITION_USD = 1000.0   # $1000 per position
PACK_VERSION = '1.0.0'

DIRECTION_MAP = {
    'BULLISH': 'LONG',
    'BEARISH': 'SHORT',
    'LONG': 'LONG',
    'SHORT': 'SHORT',
}

REGIME_MAP = {
    'BULL': 'BULL',
    'BEAR': 'BEAR',
    'SIDEWAYS': 'SIDEWAYS',
    'CRISIS': 'CRISIS',
    'STRESS': 'CRISIS',
    'UNKNOWN': 'UNKNOWN',
}


def get_current_regime(conn) -> str:
    """Get current regime."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT current_regime FROM fhq_meta.regime_state
            ORDER BY last_updated_at DESC LIMIT 1
        """)
        row = cur.fetchone()
        return row['current_regime'] if row else 'UNKNOWN'


def find_eligible_hypotheses(conn) -> list:
    """Find promoted hypotheses that have terminal (CLOSED or EXPIRED) shadow trades but no decision packs.

    CEO-DIR-2026-TERMINAL-OUTCOME-CLARIFICATION-026 A1:
    Terminal outcomes include both CLOSED (SL/TP) and EXPIRED (TTL).
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT
                hc.canon_id,
                hc.hypothesis_code,
                hc.expected_direction,
                hc.asset_universe,
                hc.current_confidence,
                hc.asset_class,
                pga.evaluated_at,
                pga.causal_node_id,
                pga.gate_id,
                pga.state_snapshot_hash,
                pga.agent_id
            FROM fhq_learning.promotion_gate_audit pga
            JOIN fhq_learning.hypothesis_canon hc ON pga.hypothesis_id = hc.canon_id
            WHERE pga.gate_result = 'PASS'
              AND hc.asset_universe IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM fhq_execution.shadow_trades st
                  WHERE st.source_hypothesis_id = hc.canon_id::text
                  AND st.status IN ('CLOSED', 'EXPIRED')
              )
            ORDER BY pga.evaluated_at
        """)
        return cur.fetchall()


def get_shadow_trade_snapshots(conn, hypothesis_uuid: str) -> list:
    """Get the most recent terminal (CLOSED or EXPIRED) shadow trade per asset for snapshot pricing.

    CEO-DIR-2026-TERMINAL-OUTCOME-CLARIFICATION-026 A1:
    Terminal outcomes include both CLOSED (SL/TP) and EXPIRED (TTL).

    Returns: List of shadow trade snapshots with status, exit_reason for terminal_reason mapping.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT ON (asset_id)
                asset_id, entry_price, exit_price, entry_time,
                shadow_pnl, shadow_return_pct, direction, entry_regime,
                status, exit_reason
            FROM fhq_execution.shadow_trades
            WHERE source_hypothesis_id = %s
            AND status IN ('CLOSED', 'EXPIRED')
            ORDER BY asset_id, entry_time DESC
        """, (hypothesis_uuid,))
        return cur.fetchall()


def check_existing_pack(conn, hypothesis_uuid: str, asset: str) -> bool:
    """Check if a decision pack already exists for this hypothesis+asset.

    CEO-DIR-2026-TERMINAL-OUTCOME-CLARIFICATION-026 A1 Fix:
    Use hypothesis_uuid (UUID) to match decision_packs.hypothesis_uuid column.
    Previous bug used hypothesis_id (TEXT) causing false negatives for EXPIRED hypotheses.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM fhq_learning.decision_packs
            WHERE hypothesis_uuid = %s AND asset = %s
            LIMIT 1
        """, (hypothesis_uuid, asset))
        return cur.fetchone() is not None


def compute_evidence_hash(pack_data: dict) -> str:
    """Compute deterministic hash of pack data for audit chain."""
    canonical = json.dumps(pack_data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def create_decision_pack(conn, hypothesis: dict, snapshot: dict,
                         regime: str, dry_run: bool = False) -> dict:
    """Create a single decision pack from hypothesis + shadow trade snapshot."""
    # CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024: Use hypothesis_uuid (FK to hypothesis_ledger)
    hypothesis_uuid = hypothesis['canon_id']  # Maps to hypothesis_ledger.hypothesis_id

    # Hard fail: NULL hypothesis_uuid is not allowed
    if hypothesis_uuid is None:
        logger.error(f"  NULL hypothesis_uuid detected — ABORTING pack creation for hypothesis {hypothesis.get('hypothesis_code', 'UNKNOWN')}")
        # Log to system_event_log for audit
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_monitoring.system_event_log
                    (event_type, severity, description, metadata, created_at)
                VALUES
                    ('PACK_GEN_NULL_UUID', 'ERROR', %s, %s, NOW())
            """, (
                f"NULL hypothesis_uuid in create_decision_pack for hypothesis_code={hypothesis.get('hypothesis_code')}",
                json.dumps({'hypothesis': hypothesis, 'snapshot': snapshot})
            ))
            conn.commit()
        return None

    asset = snapshot['asset_id']
    raw_direction = hypothesis['expected_direction']
    direction = DIRECTION_MAP.get(raw_direction)
    if not direction:
        logger.error(f"  Unknown direction '{raw_direction}' — skipping {asset}")
        return None

    entry_price = float(snapshot['entry_price'])
    confidence = float(hypothesis['current_confidence'] or 0.5)
    asset_class = hypothesis['asset_class'] or 'CRYPTO'

    # EWRE bracket computation
    if direction == 'LONG':
        stop_loss_price = round(entry_price * (1 - EWRE_STOP_LOSS_PCT), 8)
        take_profit_price = round(entry_price * (1 + EWRE_TAKE_PROFIT_PCT), 8)
    else:
        stop_loss_price = round(entry_price * (1 + EWRE_STOP_LOSS_PCT), 8)
        take_profit_price = round(entry_price * (1 - EWRE_TAKE_PROFIT_PCT), 8)

    # Position sizing
    position_usd = DEFAULT_POSITION_USD
    position_qty = round(position_usd / entry_price, 8) if entry_price > 0 else 0

    # Risk/reward
    risk_reward_ratio = EWRE_TAKE_PROFIT_PCT / EWRE_STOP_LOSS_PCT

    # CEO-DIR-2026-TERMINAL-OUTCOME-CLARIFICATION-026 A1: Terminal reason
    # Map shadow trade status + exit_reason to terminal_reason for pack metadata
    status = snapshot.get('status')
    exit_reason = snapshot.get('exit_reason', 'UNKNOWN')
    if status == 'CLOSED':
        if exit_reason == 'STOP_LOSS':
            terminal_reason = 'SL'
        elif exit_reason == 'TAKE_PROFIT':
            terminal_reason = 'TP'
        else:
            terminal_reason = exit_reason
    elif status == 'EXPIRED':
        terminal_reason = 'EXPIRY'
    else:
        terminal_reason = 'UNKNOWN'

    now = datetime.now(timezone.utc)

    # CEO-DIR-2026-CHAIN-WRITE-ACTIVATION-006: Chain binding + ASRP
    causal_node_id = hypothesis.get('causal_node_id')
    gate_id = hypothesis.get('gate_id')
    state_snapshot_hash = hypothesis.get('state_snapshot_hash')
    agent_id = hypothesis.get('agent_id', 'STIG')

    pack_data = {
        'hypothesis_uuid': hypothesis_uuid,  # Maps to hypothesis_ledger.hypothesis_id
        'asset': asset,
        'direction': direction,
        'asset_class': asset_class,
        'snapshot_price': entry_price,
        'snapshot_regime': regime,
        'snapshot_timestamp': now.isoformat(),
        'raw_confidence': confidence,
        'damped_confidence': confidence,  # No damping without calibration
        'ewre_stop_loss_pct': EWRE_STOP_LOSS_PCT,
        'ewre_take_profit_pct': EWRE_TAKE_PROFIT_PCT,
        'ewre_risk_reward_ratio': risk_reward_ratio,
        'entry_limit_price': entry_price,
        'stop_loss_price': stop_loss_price,
        'take_profit_price': take_profit_price,
        'position_usd': position_usd,
        'position_qty': position_qty,
        'pack_version': PACK_VERSION,
        # CEO-DIR-2026-TERMINAL-OUTCOME-CLARIFICATION-026 A1: Terminal reason
        'terminal_reason': terminal_reason,
        'shadow_trade_status': status,
        'shadow_trade_exit_reason': exit_reason,
        # CEO-DIR-2026-CHAIN-WRITE-ACTIVATION-006: Chain binding fields
        'causal_node_id': causal_node_id,
        'gate_id': gate_id,
        'asrp': {
            'state_snapshot_hash': state_snapshot_hash,
            'agent_id': agent_id,
        }
    }

    evidence_hash = compute_evidence_hash(pack_data)
    pack_data['evidence_hash'] = evidence_hash

    if dry_run:
        logger.info(f"  [DRY RUN] Would create pack: {asset} {direction} | "
                    f"entry={entry_price} SL={stop_loss_price} TP={take_profit_price} | "
                    f"size=${position_usd} qty={position_qty} | "
                    f"causal_node_id={causal_node_id}, gate_id={gate_id}")
        return pack_data

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_learning.decision_packs
                (hypothesis_uuid, asset, direction, asset_class,
                 snapshot_price, snapshot_regime, snapshot_timestamp,
                 snapshot_ttl_valid_until,
                 raw_confidence, damped_confidence,
                 ewre_stop_loss_pct, ewre_take_profit_pct, ewre_risk_reward_ratio,
                 entry_limit_price, stop_loss_price, take_profit_price,
                 position_usd, position_qty,
                 pack_version, evidence_hash,
                 signature, signing_agent, signing_key_id, signed_at,
                 execution_status)
            VALUES
                (%s::uuid, %s, %s, %s,
                 %s, %s, %s,
                 %s,
                 %s, %s,
                 %s, %s, %s,
                 %s, %s, %s,
                 %s, %s,
                 %s, %s,
                 %s, %s, %s, %s,
                 'PENDING')
            RETURNING hypothesis_uuid
        """, (
            hypothesis_uuid, asset, direction, asset_class,
            entry_price, regime, now,
            now,  # snapshot_ttl_valid_until (shadow, no real TTL)
            confidence, confidence,
            EWRE_STOP_LOSS_PCT, EWRE_TAKE_PROFIT_PCT, risk_reward_ratio,
            entry_price, stop_loss_price, take_profit_price,
            position_usd, position_qty,
            PACK_VERSION, evidence_hash,
            evidence_hash,  # signature = hash (deterministic signing)
            'STIG',         # signing_agent
            'EC-003-STIG-2026',  # signing_key_id
            now,            # signed_at
        ))
        pack_id = cur.fetchone()[0]
        pack_data['pack_id'] = str(pack_id)
        logger.info(f"  Created pack: {asset} {direction} | "
                    f"entry={entry_price} SL={stop_loss_price} TP={take_profit_price} | "
                    f"pack_id={pack_id} | causal_node_id={causal_node_id}, gate_id={gate_id}")

    return pack_data


def run_pack_generator(dry_run: bool = False):
    """Main entry: generate decision packs for all eligible hypotheses."""
    logger.info("=" * 60)
    logger.info("DECISION PACK GENERATOR — Formal execution intent")
    logger.info(f"  dry_run={dry_run}")
    logger.info(f"  directive=CEO-DIR-20260130-PIPELINE-COMPLETION-002 D2")
    logger.info(f"  EWRE: SL={EWRE_STOP_LOSS_PCT*100}% TP={EWRE_TAKE_PROFIT_PCT*100}%")
    logger.info(f"  Position: ${DEFAULT_POSITION_USD}")
    logger.info("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        regime = get_current_regime(conn)
        logger.info(f"Current regime: {regime}")

        hypotheses = find_eligible_hypotheses(conn)
        logger.info(f"Eligible hypotheses: {len(hypotheses)}")

        if not hypotheses:
            logger.info("No hypotheses eligible for decision pack generation.")
            return

        all_packs = []

        for hyp in hypotheses:
            canon_id = str(hyp['canon_id'])
            logger.info(f"\nProcessing: {hyp['hypothesis_code']} (canon_id={canon_id[:8]}...)")

            snapshots = get_shadow_trade_snapshots(conn, canon_id)
            logger.info(f"  Shadow trade snapshots: {len(snapshots)} assets")

            created_for_hyp = 0
            for snap in snapshots:
                asset = snap['asset_id']

                # Idempotency: skip if pack exists
                if check_existing_pack(conn, canon_id, asset):
                    logger.info(f"  {asset}: pack already exists — skipping")
                    continue

                pack = create_decision_pack(conn, hyp, snap, regime, dry_run)
                if pack:
                    all_packs.append(pack)
                    created_for_hyp += 1

            if not dry_run and created_for_hyp > 0:
                conn.commit()
            logger.info(f"  Packs {'would be ' if dry_run else ''}created: {created_for_hyp}")

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info(f"PACK GENERATOR SUMMARY")
        logger.info(f"  Hypotheses processed: {len(hypotheses)}")
        logger.info(f"  Packs {'would be ' if dry_run else ''}created: {len(all_packs)}")
        logger.info("=" * 60)

        # Evidence
        evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence = {
            'directive': 'CEO-DIR-20260130-PIPELINE-COMPLETION-002',
            'deliverable': 'D2',
            'executed_at': datetime.now(timezone.utc).isoformat(),
            'executed_by': 'STIG_PACK_GEN',
            'dry_run': dry_run,
            'regime': regime,
            'hypotheses_processed': len(hypotheses),
            'packs_created': len(all_packs),
            'risk_parameters': {
                'ewre_stop_loss_pct': EWRE_STOP_LOSS_PCT,
                'ewre_take_profit_pct': EWRE_TAKE_PROFIT_PCT,
                'position_usd': DEFAULT_POSITION_USD,
            },
            'packs': all_packs,
        }
        evidence_path = os.path.join(evidence_dir, f'DECISION_PACK_GEN_{ts}.json')
        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)
        logger.info(f"Evidence: {evidence_path}")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Decision Pack Generator')
    parser.add_argument('--check', '--dry-run', action='store_true',
                        help='Dry run: report without writing')
    args = parser.parse_args()
    run_pack_generator(dry_run=args.check)


if __name__ == '__main__':
    main()
