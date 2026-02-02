#!/usr/bin/env python3
"""
hypothesis_experiment_bridge_daemon.py
======================================
CEO-DIR-2026-OPS-BRIDGE-001 | Authorization: EFFECTIVE IMMEDIATELY
Origin: CEO-DIR-2026-PROMOTION-GATE-AUDIT-004, Recommendation R1 (URGENT)

Problem:  99.2% attrition at hypothesis -> experiment conversion.
Solution: Bridge daemon with 4 CEO-mandated safety constraints.

Constitutional Constraints (Non-Negotiable):
  A) Bridge Scope Guard   - generator_id IN ('FINN-T', 'finn_crypto_scheduler')
  B) Experiment Class Tag  - experiment_class: BRIDGE_THROUGHPUT, promotion_eligible: false
  C) Dead-End Auto-Term    - 48h + 0 outcomes -> TERMINATED_INFRA
  D) Bridge Rate Governor  - Max 20 bridge experiments per 24h
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("FATAL: psycopg2 not installed. pip install psycopg2-binary")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres'),
}

DAEMON_NAME = 'hypothesis_experiment_bridge_daemon'
BRIDGE_VERSION = '1.0'
DAILY_RATE_LIMIT = 20  # Constraint D
ZOMBIE_THRESHOLD_HOURS = 48  # Constraint C

# Constraint A: Scope Guard — ONLY these generators may produce bridge experiments
ALLOWED_GENERATORS = ('FINN-T', 'finn_crypto_scheduler')

# Sentinel UUID for bridge experiments (no real error origin)
BRIDGE_NON_ERROR_ORIGIN = uuid.uuid5(uuid.NAMESPACE_URL, 'BRIDGE_NON_ERROR_ORIGIN')

EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'evidence')

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'hypothesis_experiment_bridge_daemon.log')

logging.basicConfig(
    level=logging.INFO,
    format='[BRIDGE_DAEMON] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def check_defcon(conn) -> tuple:
    """Return (is_green: bool, level: str). Abort cycle if not GREEN."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT defcon_level
            FROM fhq_governance.defcon_state
            ORDER BY triggered_at DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if not row:
            return False, 'UNKNOWN'
        level = row['defcon_level']
        return level == 'GREEN', level


def get_regime_snapshot(conn) -> dict:
    """Current regime from fhq_meta.regime_state."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT current_regime, regime_confidence,
                   last_updated_at AT TIME ZONE 'UTC' as ts
            FROM fhq_meta.regime_state
            ORDER BY last_updated_at DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if not row:
            return {'regime': 'UNKNOWN', 'confidence': 0, 'timestamp': datetime.now(timezone.utc).isoformat()}
        return {
            'regime': row['current_regime'],
            'confidence': float(row['regime_confidence']),
            'timestamp': row['ts'].isoformat() if row['ts'] else datetime.now(timezone.utc).isoformat(),
        }


def get_bridge_count_today(conn) -> int:
    """Constraint D: count bridge experiments created in last 24h."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM fhq_learning.experiment_registry
            WHERE experiment_code LIKE 'EXP_BRIDGE_%%'
              AND created_at > NOW() - INTERVAL '24 hours'
        """)
        return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Core: find eligible hypotheses (Constraint A scope guard)
# ---------------------------------------------------------------------------

def find_eligible_hypotheses(conn, remaining_budget: int) -> list:
    """
    Query ACTIVE hypotheses from allowed generators that have:
    - falsification_criteria defined
    - asset_universe defined
    - NO existing experiment in experiment_registry
    Capped by remaining daily budget (Constraint D).
    """
    if remaining_budget <= 0:
        return []

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT h.canon_id AS hypothesis_id,
                   h.hypothesis_code,
                   h.generator_id,
                   h.falsification_criteria,
                   h.causal_graph_depth,
                   h.asset_universe
            FROM fhq_learning.hypothesis_canon h
            WHERE h.status = 'ACTIVE'
              AND h.falsification_criteria IS NOT NULL
              AND h.asset_universe IS NOT NULL
              AND h.generator_id IN %s
              AND NOT EXISTS (
                  SELECT 1 FROM fhq_learning.experiment_registry e
                  WHERE e.hypothesis_id = h.canon_id
              )
            ORDER BY h.created_at ASC
            LIMIT %s
        """, (ALLOWED_GENERATORS, remaining_budget))
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Core: create bridge experiment (Constraint B tagging)
# ---------------------------------------------------------------------------

def make_experiment_id(hypothesis_code: str) -> uuid.UUID:
    """Deterministic UUID5 from hypothesis_code."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"BRIDGE_{hypothesis_code}")


def make_experiment_code(hypothesis_code: str) -> str:
    return f"EXP_BRIDGE_{hypothesis_code}"


def compute_system_state_hash(hypothesis_id: str, regime: dict) -> str:
    """SHA256 of bridge input state for reproducibility."""
    payload = json.dumps({
        'hypothesis_id': str(hypothesis_id),
        'regime': regime,
        'bridge_version': BRIDGE_VERSION,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def create_bridge_experiment(conn, hyp: dict, regime: dict, dry_run: bool) -> dict | None:
    """
    INSERT one bridge experiment for the given hypothesis.
    Returns the experiment record dict, or None on conflict/skip.
    """
    exp_id = make_experiment_id(hyp['hypothesis_code'])
    exp_code = make_experiment_code(hyp['hypothesis_code'])

    # Constraint B: tagging payload
    parameters = {
        'min_sample_size': 30,
        'bridge_version': BRIDGE_VERSION,
        'source_generator': hyp['generator_id'],
        'experiment_class': 'BRIDGE_THROUGHPUT',
        'promotion_eligible': False,
    }

    regime_snapshot = regime
    system_hash = compute_system_state_hash(hyp['hypothesis_id'], regime)

    # Dataset signature — bridge experiments start with no dataset; use hash of hypothesis
    dataset_sig = hashlib.sha256(
        f"BRIDGE_{hyp['hypothesis_code']}_{hyp['hypothesis_id']}".encode()
    ).hexdigest()

    today = datetime.now(timezone.utc).date()

    record = {
        'experiment_id': str(exp_id),
        'experiment_code': exp_code,
        'hypothesis_id': str(hyp['hypothesis_id']),
        'origin_error_id': str(BRIDGE_NON_ERROR_ORIGIN),
        'error_id': str(BRIDGE_NON_ERROR_ORIGIN),
        'experiment_tier': 1,
        'tier_name': 'FALSIFICATION_SWEEP',  # for evidence only; generated column in DB
        'system_state_hash': system_hash,
        'regime_snapshot': json.dumps(regime_snapshot),
        'dataset_signature': dataset_sig,
        'dataset_start_date': str(today),
        'dataset_end_date': str(today),
        'dataset_row_count': 0,
        'parameters': json.dumps(parameters),
        'parameter_count': len(parameters),
        'dof_count': 1,
        'prior_experiments_on_hypothesis': 0,
        'execution_mode': 'EXPERIMENT',
        'status': 'RUNNING',
        'created_by': DAEMON_NAME,
    }

    if dry_run:
        log.info(f"[DRY-RUN] Would create {exp_code} for {hyp['hypothesis_code']} "
                 f"(generator={hyp['generator_id']})")
        return record

    with conn.cursor() as cur:
        # tier_name and parameter_count are generated columns — omit from INSERT
        cur.execute("""
            INSERT INTO fhq_learning.experiment_registry (
                experiment_id, experiment_code, hypothesis_id,
                origin_error_id, error_id,
                experiment_tier,
                system_state_hash, regime_snapshot,
                dataset_signature, dataset_start_date, dataset_end_date, dataset_row_count,
                parameters, dof_count,
                prior_experiments_on_hypothesis,
                execution_mode, status, created_by
            ) VALUES (
                %s::uuid, %s, %s::uuid,
                %s::uuid, %s::uuid,
                %s,
                %s, %s::jsonb,
                %s, %s::date, %s::date, %s,
                %s::jsonb, %s,
                %s,
                %s, %s, %s
            )
            ON CONFLICT (experiment_code) DO NOTHING
        """, (
            record['experiment_id'], record['experiment_code'], record['hypothesis_id'],
            record['origin_error_id'], record['error_id'],
            record['experiment_tier'],
            record['system_state_hash'], record['regime_snapshot'],
            record['dataset_signature'], record['dataset_start_date'],
            record['dataset_end_date'], record['dataset_row_count'],
            record['parameters'], record['dof_count'],
            record['prior_experiments_on_hypothesis'],
            record['execution_mode'], record['status'], record['created_by'],
        ))
        inserted = cur.rowcount
        conn.commit()

    if inserted == 0:
        log.info(f"SKIP (conflict): {exp_code} already exists")
        return None

    log.info(f"CREATED: {exp_code} -> hypothesis {hyp['hypothesis_code']} "
             f"(generator={hyp['generator_id']})")
    return record


# ---------------------------------------------------------------------------
# Core: zombie cleanup (Constraint C)
# ---------------------------------------------------------------------------

def cleanup_bridge_zombies(conn, dry_run: bool) -> int:
    """
    Constraint C: RUNNING bridge experiments older than 48h with 0 outcomes
    are terminated as TERMINATED_INFRA.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # First find candidates for logging
        cur.execute("""
            SELECT er.experiment_id, er.experiment_code, er.created_at
            FROM fhq_learning.experiment_registry er
            WHERE er.experiment_code LIKE 'EXP_BRIDGE_%%'
              AND er.created_at < NOW() - INTERVAL '%s hours'
              AND er.status = 'RUNNING'
              AND (SELECT COUNT(*) FROM fhq_learning.outcome_ledger o
                   WHERE o.experiment_id = er.experiment_id) = 0
        """ % ZOMBIE_THRESHOLD_HOURS)
        zombies = cur.fetchall()

        if not zombies:
            return 0

        if dry_run:
            for z in zombies:
                log.info(f"[DRY-RUN] Would terminate zombie: {z['experiment_code']} "
                         f"(created {z['created_at']})")
            return len(zombies)

        cur.execute("""
            UPDATE fhq_learning.experiment_registry
            SET status = 'TERMINATED_INFRA',
                metadata = COALESCE(metadata, '{}'::jsonb) ||
                    jsonb_build_object(
                        'terminated_reason', 'BRIDGE_ZOMBIE_48H_NO_OUTCOMES',
                        'terminated_at', NOW()::text
                    )
            WHERE experiment_code LIKE 'EXP_BRIDGE_%%'
              AND created_at < NOW() - INTERVAL '%s hours'
              AND status = 'RUNNING'
              AND (SELECT COUNT(*) FROM fhq_learning.outcome_ledger o
                   WHERE o.experiment_id = experiment_registry.experiment_id) = 0
        """ % ZOMBIE_THRESHOLD_HOURS)
        terminated = cur.rowcount
        conn.commit()

        for z in zombies:
            log.info(f"TERMINATED_INFRA: {z['experiment_code']} "
                     f"(48h, 0 outcomes, created {z['created_at']})")
        return terminated


# ---------------------------------------------------------------------------
# Evidence file
# ---------------------------------------------------------------------------

def write_evidence(cycle_stats: dict) -> str:
    """Write evidence JSON with SHA256 hash. Returns file path."""
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"BRIDGE_DAEMON_{ts}.json"
    filepath = os.path.join(EVIDENCE_DIR, filename)

    evidence = {
        'daemon': DAEMON_NAME,
        'directive': 'CEO-DIR-2026-OPS-BRIDGE-001',
        'origin': 'CEO-DIR-2026-PROMOTION-GATE-AUDIT-004/R1',
        'bridge_version': BRIDGE_VERSION,
        'executed_at': datetime.now(timezone.utc).isoformat(),
        'constitutional_constraints': {
            'A_scope_guard': list(ALLOWED_GENERATORS),
            'B_experiment_class': 'BRIDGE_THROUGHPUT',
            'B_promotion_eligible': False,
            'C_zombie_threshold_hours': ZOMBIE_THRESHOLD_HOURS,
            'D_daily_rate_limit': DAILY_RATE_LIMIT,
        },
        **cycle_stats,
    }

    # Compute evidence hash (excluding the hash field itself)
    payload = json.dumps(evidence, sort_keys=True, default=str)
    evidence['evidence_sha256'] = hashlib.sha256(payload.encode()).hexdigest()

    with open(filepath, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    log.info(f"Evidence written: {filepath}")
    return filepath


# ---------------------------------------------------------------------------
# Main cycle
# ---------------------------------------------------------------------------

def run_cycle(dry_run: bool = False, batch_size: int = DAILY_RATE_LIMIT) -> dict:
    """Execute one bridge daemon cycle. Returns stats dict."""
    cycle_start = datetime.now(timezone.utc)
    stats = {
        'dry_run': dry_run,
        'cycle_start': cycle_start.isoformat(),
        'defcon_level': None,
        'defcon_ok': False,
        'regime_snapshot': None,
        'rate_limit_used_today': 0,
        'rate_limit_remaining': 0,
        'eligible_hypotheses_found': 0,
        'experiments_created': 0,
        'experiments_skipped_conflict': 0,
        'zombies_terminated': 0,
        'created_experiments': [],
        'errors': [],
    }

    conn = None
    try:
        conn = get_connection()

        # 1. DEFCON gate
        defcon_ok, defcon_level = check_defcon(conn)
        stats['defcon_level'] = defcon_level
        stats['defcon_ok'] = defcon_ok
        if not defcon_ok:
            log.warning(f"DEFCON={defcon_level} (not GREEN). Cycle aborted.")
            stats['abort_reason'] = f'DEFCON_{defcon_level}'
            return stats

        log.info(f"DEFCON={defcon_level} -- proceeding")

        # 2. Rate Governor (Constraint D)
        already_today = get_bridge_count_today(conn)
        remaining = DAILY_RATE_LIMIT - already_today
        effective_budget = min(remaining, batch_size)
        stats['rate_limit_used_today'] = already_today
        stats['rate_limit_remaining'] = remaining

        if remaining <= 0:
            log.info(f"Rate limit reached: {already_today}/{DAILY_RATE_LIMIT} "
                     "bridge experiments in last 24h. Skipping creation.")
            stats['abort_reason'] = 'RATE_LIMIT_REACHED'
            # Still run zombie cleanup
            stats['zombies_terminated'] = cleanup_bridge_zombies(conn, dry_run)
            return stats

        log.info(f"Rate governor: {already_today}/{DAILY_RATE_LIMIT} used, "
                 f"budget this cycle: {effective_budget}")

        # 3. Get regime snapshot
        regime = get_regime_snapshot(conn)
        stats['regime_snapshot'] = regime
        log.info(f"Regime: {regime['regime']} (confidence={regime['confidence']})")

        # 4. Find eligible hypotheses (Constraint A)
        eligible = find_eligible_hypotheses(conn, effective_budget)
        stats['eligible_hypotheses_found'] = len(eligible)
        log.info(f"Eligible hypotheses (scope guard: {ALLOWED_GENERATORS}): {len(eligible)}")

        # 5. Create bridge experiments (Constraint B)
        for hyp in eligible:
            try:
                result = create_bridge_experiment(conn, hyp, regime, dry_run)
                if result:
                    stats['experiments_created'] += 1
                    stats['created_experiments'].append({
                        'experiment_code': result['experiment_code'],
                        'hypothesis_code': hyp['hypothesis_code'],
                        'generator_id': hyp['generator_id'],
                    })
                else:
                    stats['experiments_skipped_conflict'] += 1
            except Exception as e:
                conn.rollback()  # reset transaction state for next iteration
                err_msg = f"Failed creating experiment for {hyp['hypothesis_code']}: {e}"
                log.error(err_msg)
                stats['errors'].append(err_msg)

        # 6. Zombie cleanup (Constraint C)
        stats['zombies_terminated'] = cleanup_bridge_zombies(conn, dry_run)

        # Cycle summary
        stats['cycle_end'] = datetime.now(timezone.utc).isoformat()
        log.info(
            f"Cycle complete: created={stats['experiments_created']}, "
            f"skipped={stats['experiments_skipped_conflict']}, "
            f"zombies_terminated={stats['zombies_terminated']}"
        )

    except Exception as e:
        err_msg = f"Cycle failed: {e}"
        log.error(err_msg, exc_info=True)
        stats['errors'].append(err_msg)
    finally:
        if conn:
            conn.close()

    return stats


# ---------------------------------------------------------------------------
# Daemon loop / CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Hypothesis-Experiment Bridge Daemon (CEO-DIR-2026-OPS-BRIDGE-001)')
    parser.add_argument('--test', action='store_true',
                        help='Single cycle then exit (dry-run verification)')
    parser.add_argument('--interval', type=int, default=60,
                        help='Minutes between cycles (default: 60)')
    parser.add_argument('--batch-size', type=int, default=DAILY_RATE_LIMIT,
                        help=f'Max experiments per cycle (default: {DAILY_RATE_LIMIT}, '
                             f'capped by daily budget)')
    args = parser.parse_args()

    # Cap batch-size to daily rate limit
    batch = min(args.batch_size, DAILY_RATE_LIMIT)

    log.info("=" * 70)
    log.info(f"BRIDGE DAEMON START | mode={'TEST' if args.test else 'CONTINUOUS'} | "
             f"interval={args.interval}m | batch={batch}")
    log.info(f"Scope guard (Constraint A): {ALLOWED_GENERATORS}")
    log.info(f"Rate governor (Constraint D): {DAILY_RATE_LIMIT}/24h")
    log.info("=" * 70)

    if args.test:
        stats = run_cycle(dry_run=True, batch_size=batch)
        evidence_path = write_evidence(stats)
        log.info(f"TEST cycle complete. Evidence: {evidence_path}")
        # Print summary to stdout
        print(json.dumps(stats, indent=2, default=str))
        return

    # Continuous daemon loop
    while True:
        try:
            stats = run_cycle(dry_run=False, batch_size=batch)
            write_evidence(stats)
        except Exception as e:
            log.error(f"Daemon loop error: {e}", exc_info=True)

        log.info(f"Sleeping {args.interval} minutes until next cycle...")
        time.sleep(args.interval * 60)


if __name__ == '__main__':
    main()
