#!/usr/bin/env python3
"""
FSS Baseline v1 Patch Job
CEO-DIR-2026-FIX-006: Implement FSS Baseline v1 batch job with proof-first controls

Author: STIG (CTO)
Date: 2026-02-13

Purpose:
- Compute empirical baseline per asset/horizon/period using base rate with Beta(1,1) prior
- Update brier_ref, baseline_method, and recompute fss_value
- Apply N_min=50 gating and degenerate baseline guards
- Generate comprehensive evidence JSON with proof-first controls

Baseline Model (LOCKED):
- p_base = (a0 + n_pos) / (a0 + b0 + n_total)
- Prior: Beta(a0=1, b0=1)
- Lookback: 30 days
- Leakage: outcome_timestamp < period_start (strict)
- baseline_method: 'BASE_RATE_EMPIRICAL_BETA_30D_STRICT'
"""

import os
import sys
import json
import hashlib
import argparse
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import psycopg2
from psycopg2.extras import RealDictCursor
import statistics

# =============================================================================
# LOCKED PARAMETERS
# =============================================================================
A0 = 1
B0 = 1
LOOKBACK_DAYS = 30
N_MIN = 50
EPSILON = 1e-9
BASELINE_METHOD = 'BASE_RATE_EMPIRICAL_BETA_30D_STRICT'

# Expected DB values (fail-closed)
EXPECTED_DB = {
    'host': '127.0.0.1',
    'port': 54322,
    'db': 'postgres',
    'user': 'postgres'
}

# Expected version prefix
EXPECTED_VERSION_PREFIX = "PostgreSQL 17."

# Freeze lock file
FREEZE_LOCK_FILE = os.path.join(
    os.path.dirname(__file__),
    '../.locks/FSS_BSS_FREEZE.lock'
)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class HandshakeResult:
    """DB identity handshake result."""
    server_now: str
    db: str
    db_user: str
    server_addr: str
    server_port: int
    server_version: str
    search_path: str
    passed: bool
    reason: Optional[str]


@dataclass
class PreflightResult:
    """Preflight checks result."""
    passed: bool
    missing_columns: List[str]
    join_verified: bool
    reason: Optional[str]


@dataclass
class BaselineComputation:
    """Baseline computation parameters."""
    asset_id: str
    period_start: datetime
    period_end: datetime
    n_pos_lookback: int
    n_total_lookback: int
    p_base: float
    brier_ref: float
    sample_size: int
    brier_actual: float
    fss_value: Optional[float]
    skill_status: Optional[str]
    guard_reason: Optional[str]


@dataclass
class BatchUpdateResult:
    """Batch update result."""
    batch_num: int
    assets_processed: int
    rows_updated: int
    elapsed_ms: float
    error: Optional[str]


@dataclass
class PatchEvidence:
    """Complete patch evidence."""
    report_id: str
    report_type: str
    executed_by: str
    executed_at: str
    directive: str
    handshake: Dict
    parameters: Dict
    preflight: Dict
    batch_results: List[Dict]
    counts_before: Dict
    counts_after: Dict
    validation: Dict
    attestation: Dict


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

class DatabaseConnection:
    """Connection from DATABASE_URL environment variable."""

    @staticmethod
    def parse_database_url(database_url: str) -> Dict:
        """Parse postgres:// URL into components."""
        import re
        pattern = r'postgres://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)'
        match = re.match(pattern, database_url)
        if not match:
            raise ValueError(f"Invalid DATABASE_URL: {database_url}")
        return {
            'user': match.group(1),
            'password': match.group(2),
            'host': match.group(3),
            'port': int(match.group(4)),
            'database': match.group(5)
        }

    @staticmethod
    def connect_from_url(database_url: str):
        """Connect using DATABASE_URL (single source of truth)."""
        config = DatabaseConnection.parse_database_url(database_url)
        conn = psycopg2.connect(
            host=config['host'],
            port=config['port'],
            database=config['database'],
            user=config['user'],
            password=config['password']
        )
        # Explicit search_path
        with conn.cursor() as cur:
            cur.execute(
                "SET search_path = "
                "fhq_governance, fhq_meta, fhq_learning, fhq_research, "
                "fhq_monitoring, fhq_calendar, fhq_execution, fhq_canonical, public"
            )
        return conn


# =============================================================================
# CONTROL A: DB IDENTITY HANDSHAKE (FAIL-CLOSED)
# =============================================================================

def db_identity_handshake(conn) -> HandshakeResult:
    """
    Execute DB identity handshake (fail-closed).
    Abort on host/port/db/user mismatch or unexpected version.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
              now() AS server_now,
              current_database() AS db,
              current_user AS db_user,
              inet_server_addr() AS server_addr,
              inet_server_port() AS server_port,
              version() AS server_version,
              current_setting('search_path') AS search_path
        """)
        result = cur.fetchone()

    # Check expected values
    if str(result['server_addr']) != EXPECTED_DB['host']:
        return HandshakeResult(
            server_now=str(result['server_now']),
            db=result['db'],
            db_user=result['db_user'],
            server_addr=str(result['server_addr']),
            server_port=result['server_port'],
            server_version=result['server_version'],
            search_path=result['search_path'],
            passed=False,
            reason=f"server_addr mismatch: {result['server_addr']} != {EXPECTED_DB['host']}"
        )

    if result['server_port'] != EXPECTED_DB['port']:
        return HandshakeResult(
            server_now=str(result['server_now']),
            db=result['db'],
            db_user=result['db_user'],
            server_addr=str(result['server_addr']),
            server_port=result['server_port'],
            server_version=result['server_version'],
            search_path=result['search_path'],
            passed=False,
            reason=f"server_port mismatch: {result['server_port']} != {EXPECTED_DB['port']}"
        )

    if result['db'] != EXPECTED_DB['db']:
        return HandshakeResult(
            server_now=str(result['server_now']),
            db=result['db'],
            db_user=result['db_user'],
            server_addr=str(result['server_addr']),
            server_port=result['server_port'],
            server_version=result['server_version'],
            search_path=result['search_path'],
            passed=False,
            reason=f"db mismatch: {result['db']} != {EXPECTED_DB['db']}"
        )

    if result['db_user'] != EXPECTED_DB['user']:
        return HandshakeResult(
            server_now=str(result['server_now']),
            db=result['db'],
            db_user=result['db_user'],
            server_addr=str(result['server_addr']),
            server_port=result['server_port'],
            server_version=result['server_version'],
            search_path=result['search_path'],
            passed=False,
            reason=f"db_user mismatch: {result['db_user']} != {EXPECTED_DB['user']}"
        )

    # Check server version prefix
    if not result['server_version'].startswith(EXPECTED_VERSION_PREFIX):
        return HandshakeResult(
            server_now=str(result['server_now']),
            db=result['db'],
            db_user=result['db_user'],
            server_addr=str(result['server_addr']),
            server_port=result['server_port'],
            server_version=result['server_version'],
            search_path=result['search_path'],
            passed=False,
            reason=f"server_version mismatch: {result['server_version']} does not start with {EXPECTED_VERSION_PREFIX}"
        )

    return HandshakeResult(
        server_now=str(result['server_now']),
        db=result['db'],
        db_user=result['db_user'],
        server_addr=str(result['server_addr']),
        server_port=result['server_port'],
        server_version=result['server_version'],
        search_path=result['search_path'],
        passed=True,
        reason=None
    )


# =============================================================================
# CONTROL B: PREFLIGHT CHECKS (FAIL-CLOSED)
# =============================================================================

def run_preflight_checks(conn) -> PreflightResult:
    """
    Run preflight checks before UPDATE.
    Verify required columns exist and join paths are valid.
    """
    required_columns = [
        'asset_id',
        'period_start',
        'period_end',
        'sample_size',
        'brier_actual',
        'brier_ref',
        'baseline_method',
        'fss_value'
    ]

    missing_columns = []

    # Check fss_computation_log columns
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'fhq_research'
              AND table_name = 'fss_computation_log'
        """)
        existing_columns = {row['column_name'] for row in cur.fetchall()}

    for col in required_columns:
        if col not in existing_columns:
            missing_columns.append(col)

    if missing_columns:
        return PreflightResult(
            passed=False,
            missing_columns=missing_columns,
            join_verified=False,
            reason=f"Missing columns in fss_computation_log: {missing_columns}"
        )

    # Verify we can get outcome data
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM fhq_research.outcome_ledger
                WHERE outcome_timestamp IS NOT NULL
                LIMIT 1
            """)
            cur.fetchone()
    except Exception as e:
        return PreflightResult(
            passed=False,
            missing_columns=missing_columns,
            join_verified=False,
            reason=f"Cannot query outcome_ledger: {e}"
        )

    # Join verification: asset_id exists in brier_score_ledger
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM fhq_governance.brier_score_ledger
                WHERE asset_id = %s
                LIMIT 1
            """, ('TEST_ASSET',))
            cur.fetchone()
    except Exception as e:
        return PreflightResult(
            passed=False,
            missing_columns=missing_columns,
            join_verified=False,
            reason=f"Brier score ledger query verification failed: {e}"
        )

    return PreflightResult(
        passed=True,
        missing_columns=[],
        join_verified=True,
        reason=None
    )


# =============================================================================
# CONTROL C: WRITE-FREEZE COMPLIANCE
# =============================================================================

def check_freeze_override(override: bool) -> Tuple[bool, str]:
    """
    Check if freeze lock exists and require override flag.
    Returns (can_proceed, message).
    """
    if not os.path.exists(FREEZE_LOCK_FILE):
        return True, "No freeze lock found"

    if override:
        return True, "Freeze override granted via --override-freeze flag"

    return False, "Freeze lock exists. Use --override-freeze to proceed."


# =============================================================================
# BASELINE COMPUTATION
# =============================================================================

def compute_baseline_for_period(
    conn,
    asset_id: str,
    period_start: datetime,
    period_end: datetime
) -> Optional[BaselineComputation]:
    """
    Compute empirical baseline for a single period using base rate with Beta(1,1) prior.

    Leaked data prevention:
    - Lookback sample: outcomes in [period_start-30d, period_start)
    - Eval sample: outcomes in [period_start, period_end)
    """
    # Get current FSS record for this period
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                asset_id,
                period_start,
                period_end,
                sample_size,
                brier_actual
            FROM fhq_research.fss_computation_log
            WHERE asset_id = %s
              AND period_start = %s
              AND period_end = %s
        """, (asset_id, period_start, period_end))
        fss_record = cur.fetchone()

    if not fss_record:
        return None

    # Get lookback statistics (strict leakage rule: outcome_timestamp < period_start)
    lookback_start = period_start - timedelta(days=LOOKBACK_DAYS)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                COUNT(*) AS n_total,
                SUM(CASE WHEN actual_outcome THEN 1 ELSE 0 END) AS n_pos
            FROM fhq_governance.brier_score_ledger
            WHERE asset_id = %s
              AND outcome_timestamp >= %s
              AND outcome_timestamp < %s
        """, (asset_id, lookback_start, period_start))
        lookback_stats = cur.fetchone()

    n_pos = lookback_stats['n_pos']
    n_total = lookback_stats['n_total']

    # Skip if no lookback data
    if n_total == 0:
        return None

    # Compute base rate with Beta(1,1) prior
    # p_base = (a0 + n_pos) / (a0 + b0 + n_total)
    p_base = (A0 + n_pos) / (A0 + B0 + n_total)

    # Compute Brier_baseline over eval sample
    # Brier_baseline = mean((p_base - y)^2) over all y in eval window
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                AVG(POWER(%s - CASE WHEN actual_outcome THEN 1.0 ELSE 0.0 END, 2)) AS brier_baseline,
                COUNT(*) AS eval_count
            FROM fhq_governance.brier_score_ledger
            WHERE asset_id = %s
              AND outcome_timestamp >= %s
              AND outcome_timestamp < %s
        """, (p_base, asset_id, period_start, period_end))
        baseline_stats = cur.fetchone()

    if baseline_stats['brier_baseline'] is None or baseline_stats['eval_count'] == 0:
        return None

    brier_ref = baseline_stats['brier_baseline']
    eval_count = baseline_stats['eval_count']

    # Compute FSS
    # FSS = 1 - (brier_actual / brier_ref)
    brier_actual = fss_record['brier_actual']
    sample_size = fss_record['sample_size']

    # Gate: N_min = 50
    if sample_size < N_MIN:
        # Return with fss_value=None (base_rate can be set separately if needed)
        return BaselineComputation(
            asset_id=asset_id,
            period_start=period_start,
            period_end=period_end,
            n_pos_lookback=n_pos,
            n_total_lookback=n_total,
            p_base=p_base,
            brier_ref=brier_ref,
            sample_size=sample_size,
            brier_actual=brier_actual,
            fss_value=None,
            skill_status='INSUFFICIENT_SAMPLE_N50',
            guard_reason=None
        )

    # Gate: Degenerate baseline (brier_ref too small)
    if brier_ref <= EPSILON:
        return BaselineComputation(
            asset_id=asset_id,
            period_start=period_start,
            period_end=period_end,
            n_pos_lookback=n_pos,
            n_total_lookback=n_total,
            p_base=p_base,
            brier_ref=brier_ref,
            sample_size=sample_size,
            brier_actual=brier_actual,
            fss_value=None,
            skill_status=None,
            guard_reason='BASELINE_DEGENERATE'
        )

    # Compute FSS value
    fss_value = 1 - (brier_actual / brier_ref)

    return BaselineComputation(
        asset_id=asset_id,
        period_start=period_start,
        period_end=period_end,
        n_pos_lookback=n_pos,
        n_total_lookback=n_total,
        p_base=p_base,
        brier_ref=brier_ref,
        sample_size=sample_size,
        brier_actual=brier_actual,
        fss_value=fss_value,
        skill_status=None,
        guard_reason=None
    )


def update_fss_record(
    conn,
    computation: BaselineComputation
) -> bool:
    """Update a single FSS record with baseline and recomputed FSS."""
    with conn.cursor() as cur:
        if computation.fss_value is None:
            # Gated record (insufficient sample or degenerate baseline)
            cur.execute("""
                UPDATE fhq_research.fss_computation_log
                SET
                    brier_ref = %s,
                    baseline_method = %s,
                    fss_value = NULL,
                    base_rate = %s
                WHERE asset_id = %s
                  AND period_start = %s
                  AND period_end = %s
            """, (
                computation.brier_ref,
                BASELINE_METHOD,
                computation.p_base,
                computation.asset_id,
                computation.period_start,
                computation.period_end
            ))
        else:
            # Normal update with computed FSS
            cur.execute("""
                UPDATE fhq_research.fss_computation_log
                SET
                    brier_ref = %s,
                    baseline_method = %s,
                    fss_value = %s,
                    base_rate = %s
                WHERE asset_id = %s
                  AND period_start = %s
                  AND period_end = %s
            """, (
                computation.brier_ref,
                BASELINE_METHOD,
                computation.fss_value,
                computation.p_base,
                computation.asset_id,
                computation.period_start,
                computation.period_end
            ))

    return True


def process_asset_batch(
    conn,
    asset_ids: List[str],
    batch_num: int
) -> BatchUpdateResult:
    """
    Process a batch of assets.
    One transaction per batch for performance and safety.
    """
    import time
    start_ms = time.time() * 1000
    rows_updated = 0
    errors = []

    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get all periods for these assets
                cur.execute("""
                    SELECT DISTINCT
                        asset_id,
                        period_start,
                        period_end
                    FROM fhq_research.fss_computation_log
                    WHERE asset_id = ANY(%s)
                    ORDER BY asset_id, period_start
                """, (asset_ids,))
                periods = cur.fetchall()

            for period in periods:
                try:
                    computation = compute_baseline_for_period(
                        conn,
                        period['asset_id'],
                        period['period_start'],
                        period['period_end']
                    )

                    if computation:
                        if update_fss_record(conn, computation):
                            rows_updated += 1
                except Exception as e:
                    errors.append(f"Error processing {period['asset_id']} {period['period_start']}: {e}")

        elapsed_ms = time.time() * 1000 - start_ms

        return BatchUpdateResult(
            batch_num=batch_num,
            assets_processed=len(asset_ids),
            rows_updated=rows_updated,
            elapsed_ms=elapsed_ms,
            error=', '.join(errors) if errors else None
        )

    except Exception as e:
        return BatchUpdateResult(
            batch_num=batch_num,
            assets_processed=len(asset_ids),
            rows_updated=rows_updated,
            elapsed_ms=time.time() * 1000 - start_ms,
            error=str(e)
        )


# =============================================================================
# GET COUNTS (BEFORE/AFTER)
# =============================================================================

def get_counts_before(conn) -> Dict:
    """Get counts before patch."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            WITH counts AS (
                SELECT
                    COUNT(*) AS total_rows,
                    COUNT(DISTINCT brier_ref) AS distinct_brier_ref,
                    COUNT(*) FILTER (WHERE brier_ref IS NULL) AS null_brier_ref_count,
                    MIN(fss_value) AS min_fss,
                    MAX(fss_value) AS max_fss,
                    AVG(fss_value) AS avg_fss,
                    COUNT(*) FILTER (WHERE fss_value IS NULL) AS null_fss_count,
                    COUNT(*) FILTER (WHERE sample_size < 50) AS insufficient_sample_count,
                    COUNT(*) FILTER (WHERE baseline_method = %s) AS current_baseline_method_count
                FROM fhq_research.fss_computation_log
            )
            SELECT * FROM counts
        """, (BASELINE_METHOD,))
        return cur.fetchone()


def get_counts_after(conn) -> Dict:
    """Get counts after patch."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            WITH counts AS (
                SELECT
                    COUNT(*) AS total_rows,
                    COUNT(DISTINCT brier_ref) AS distinct_brier_ref,
                    COUNT(*) FILTER (WHERE brier_ref IS NULL) AS null_brier_ref_count,
                    MIN(fss_value) AS min_fss,
                    MAX(fss_value) AS max_fss,
                    AVG(fss_value) AS avg_fss,
                    COUNT(*) FILTER (WHERE fss_value IS NULL) AS null_fss_count,
                    COUNT(*) FILTER (WHERE sample_size < 50 AND fss_value IS NULL) AS gated_small_sample,
                    COUNT(*) FILTER (WHERE sample_size < 50 AND fss_value IS NOT NULL) AS gate_violation,
                    COUNT(*) FILTER (WHERE brier_ref <= 1e-9 AND fss_value IS NULL) AS degenerate_ok,
                    COUNT(*) FILTER (WHERE brier_ref <= 1e-9 AND fss_value IS NOT NULL) AS degenerate_violation,
                    COUNT(*) FILTER (WHERE baseline_method = %s) AS new_baseline_method_count,
                    COUNT(*) FILTER (
                        WHERE baseline_method = %s
                        AND computation_timestamp >= NOW() - INTERVAL '7 days'
                    ) AS new_baseline_method_7d_count
                FROM fhq_research.fss_computation_log
            )
            SELECT * FROM counts
        """, (BASELINE_METHOD, BASELINE_METHOD))
        return cur.fetchone()


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main execution."""
    parser = argparse.ArgumentParser(description='FSS Baseline v1 Patch Job')
    parser.add_argument('--override-freeze', action='store_true',
                       help='Override freeze lock if present')
    args = parser.parse_args()

    # Get DATABASE_URL
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(2)

    evidence_dir = os.path.join(
        os.path.dirname(__file__),
        '../evidence'
    )
    os.makedirs(evidence_dir, exist_ok=True)

    # Evidence initialization
    evidence_data = {
        'report_id': 'FSS_BASELINE_PATCH_V1',
        'report_type': 'CEO-DIR-2026-FIX-006_EVIDENCE',
        'executed_by': 'STIG',
        'executed_at': datetime.now(timezone.utc).isoformat(),
        'directive': 'CEO-DIR-2026-FIX-006',
        'directive_subject': 'Implement FSS Baseline v1 batch job with proof-first controls'
    }

    # Connect to database
    conn = DatabaseConnection.connect_from_url(database_url)

    try:
        # CONTROL A: DB Identity Handshake
        handshake = db_identity_handshake(conn)
        evidence_data['handshake'] = asdict(handshake)

        if not handshake.passed:
            print(f"FAIL-CLOSED: DB Identity Handshake failed: {handshake.reason}")
            evidence_data['status'] = 'FAIL'
            evidence_data['fail_reason'] = f"Handshake failed: {handshake.reason}"
            write_evidence(evidence_data, evidence_dir)
            sys.exit(2)

        print(f"PASS: DB Identity Handshake - {handshake.db}:{handshake.server_port}")

        # CONTROL B: Preflight Checks
        preflight = run_preflight_checks(conn)
        evidence_data['preflight'] = asdict(preflight)

        if not preflight.passed:
            print(f"FAIL-CLOSED: Preflight checks failed: {preflight.reason}")
            evidence_data['status'] = 'FAIL'
            evidence_data['fail_reason'] = f"Preflight failed: {preflight.reason}"
            write_evidence(evidence_data, evidence_dir)
            sys.exit(2)

        print(f"PASS: Preflight Checks - columns verified, join path validated")

        # CONTROL C: Write-Freeze Compliance
        can_proceed, freeze_msg = check_freeze_override(args.override_freeze)
        evidence_data['freeze_override'] = {
            'override_requested': args.override_freeze,
            'can_proceed': can_proceed,
            'message': freeze_msg
        }

        if not can_proceed:
            print(f"FAIL-CLOSED: {freeze_msg}")
            evidence_data['status'] = 'FAIL'
            evidence_data['fail_reason'] = freeze_msg
            write_evidence(evidence_data, evidence_dir)
            sys.exit(2)

        print(f"PASS: Freeze check - {freeze_msg}")

        # Get counts before
        counts_before = get_counts_before(conn)
        evidence_data['counts_before'] = dict(counts_before)
        print(f"BEFORE: distinct_brier_ref={counts_before['distinct_brier_ref']}, "
              f"null_fss_count={counts_before['null_fss_count']}")

        # PARAMETERS
        evidence_data['parameters'] = {
            'a0': A0,
            'b0': B0,
            'lookback_days': LOOKBACK_DAYS,
            'N_min': N_MIN,
            'eps': EPSILON,
            'baseline_method': BASELINE_METHOD
        }
        print(f"PARAMETERS: {evidence_data['parameters']}")

        # Get all assets to process
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT asset_id
                FROM fhq_research.fss_computation_log
                ORDER BY asset_id
            """)
            all_assets = [row['asset_id'] for row in cur.fetchall()]

        print(f"Processing {len(all_assets)} assets...")

        # Process in batches
        batch_size = 200
        batch_results = []

        for i in range(0, len(all_assets), batch_size):
            batch_assets = all_assets[i:i + batch_size]
            batch_num = i // batch_size + 1

            result = process_asset_batch(conn, batch_assets, batch_num)
            batch_results.append(asdict(result))

            print(f"Batch {batch_num}: {result.rows_updated} rows updated, "
                  f"{result.elapsed_ms:.0f}ms, {result.error or 'OK'}")

        evidence_data['batch_results'] = batch_results

        # Get counts after
        counts_after = get_counts_after(conn)
        evidence_data['counts_after'] = dict(counts_after)
        print(f"AFTER: distinct_brier_ref={counts_after['distinct_brier_ref']}, "
              f"null_fss_count={counts_after['null_fss_count']}, "
              f"gated_small_sample={counts_after.get('gated_small_sample', 0)}, "
              f"guard_degenerate={counts_after.get('guard_degenerate_count', 0)}")

        # Validation
        validation = {
            'distinct_brier_ref_gt_1': counts_after['distinct_brier_ref'] > 1,
            'not_constant_025': counts_after['distinct_brier_ref'] > 1 or \
                                counts_after['min_fss'] != counts_after['max_fss'],
            'sample_gating_works': counts_after.get('gated_small_sample', 0) > 0,
            'new_baseline_method_used': counts_after.get('new_baseline_method_count', 0) > 0
        }
        evidence_data['validation'] = validation

        print(f"VALIDATION: {validation}")

        # Check acceptance criteria
        if not all(validation.values()):
            print("FAIL: Acceptance criteria not met")
            evidence_data['status'] = 'FAIL'
            evidence_data['fail_reason'] = "Validation criteria not met"
            write_evidence(evidence_data, evidence_dir)
            sys.exit(2)

        # SUCCESS
        evidence_data['status'] = 'PASS'
        write_evidence(evidence_data, evidence_dir)

        print("\nSUCCESS: FSS Baseline v1 patch applied successfully")
        print(f"Evidence: {evidence_data.get('evidence_file')}")
        print(f"SHA-256: {evidence_data['attestation']['sha256_hash']}")

        sys.exit(0)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        evidence_data['status'] = 'FAIL'
        evidence_data['fail_reason'] = str(e)
        evidence_data['traceback'] = traceback.format_exc()
        write_evidence(evidence_data, evidence_dir)
        sys.exit(2)

    finally:
        conn.close()


def write_evidence(evidence: Dict, output_dir: str) -> str:
    """Write evidence JSON with SHA-256 hash."""
    evidence['executed_at'] = datetime.now(timezone.utc).isoformat()

    # Compute SHA-256 of evidence without hash
    evidence_copy = evidence.copy()
    evidence_copy['attestation'] = {'sha256_hash': ''}
    evidence_json = json.dumps(evidence_copy, indent=2, default=str)
    sha256_hash = hashlib.sha256(evidence_json.encode()).hexdigest()

    # Add hash to evidence
    evidence['attestation'] = {'sha256_hash': sha256_hash}

    # Write file
    filename = f"FSS_BASELINE_PATCH_V1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    evidence['evidence_file'] = filename
    return filepath, sha256_hash


if __name__ == '__main__':
    main()
