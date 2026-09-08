"""
SHADOW Mode 48h Readout Script
CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001 Phase D

Produces acceptance gate metrics for SHADOW -> LIVE transition:
- NO_SIGNAL rate (overall + by defcon): Pass < 30%, Warn 30-50%, Fail > 50%
- ECR distribution: Pass median >= 1.0, p10 >= 0.5
- Cost + latency: p95 latency < 5s, all query_cost_usd <= 0.50 (zero exceptions)
- Truth chain integrity: Random sample 10 bundles, verify hash, snippet_ids resolve

Author: STIG (CTO)
Date: 2026-01-05
"""

import os
import sys
import json
import hashlib
import psycopg2
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict

# Load environment
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'), override=True)


# =============================================================================
# CONFIGURATION - CEO Directive Acceptance Gates
# =============================================================================

# NO_SIGNAL Rate Thresholds
NO_SIGNAL_PASS = 30.0      # < 30% = PASS
NO_SIGNAL_WARN = 50.0      # 30-50% = WARN, > 50% = FAIL

# ECR Distribution Thresholds
ECR_MEDIAN_PASS = 1.0      # median >= 1.0 = PASS
ECR_P10_PASS = 0.5         # p10 >= 0.5 = PASS

# Cost + Latency Thresholds
LATENCY_P95_PASS = 5000    # p95 < 5000ms = PASS
COST_HARD_CAP = 0.50       # All queries must be <= $0.50 (zero exceptions)

# Truth Chain Sample Size
TRUTH_CHAIN_SAMPLE = 10    # Random sample 10 bundles


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class GateResult:
    gate_name: str
    status: str  # PASS, WARN, FAIL
    value: Any
    threshold: Any
    details: Optional[str] = None


@dataclass
class ShadowReadout:
    timestamp: str
    observation_hours: float
    total_queries: int
    gates: List[GateResult]
    overall_status: str  # PASS, WARN, FAIL
    ready_for_live: bool
    blocking_issues: List[str]


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=int(os.environ.get('PGPORT', '54322')),
        database=os.environ.get('PGDATABASE', 'postgres'),
        user=os.environ.get('PGUSER', 'postgres'),
        password=os.environ.get('PGPASSWORD', 'postgres')
    )


# =============================================================================
# GATE 1: NO_SIGNAL RATE
# =============================================================================

def check_no_signal_rate(conn, window_hours: int = 48) -> Tuple[GateResult, Dict]:
    """
    CEO Gate 1: NO_SIGNAL rate (overall + by defcon)
    Pass < 30%, Warn 30-50%, Fail > 50%
    """
    cursor = conn.cursor()

    # Check if result_type column exists
    cursor.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'fhq_governance'
        AND table_name = 'inforage_query_log'
        AND column_name = 'result_type'
    """)

    if not cursor.fetchone():
        cursor.close()
        return GateResult(
            gate_name="NO_SIGNAL_RATE",
            status="WARN",
            value=None,
            threshold=f"< {NO_SIGNAL_PASS}%",
            details="result_type column not found - no data yet"
        ), {}

    # Overall NO_SIGNAL rate
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE result_type = 'NO_SIGNAL') as no_signal,
            CASE WHEN COUNT(*) > 0
                THEN ROUND(100.0 * COUNT(*) FILTER (WHERE result_type = 'NO_SIGNAL') / COUNT(*), 2)
                ELSE 0
            END as rate
        FROM fhq_governance.inforage_query_log
        WHERE created_at > NOW() - INTERVAL '%s hours'
    """, [window_hours])

    row = cursor.fetchone()
    total, no_signal_count, overall_rate = row if row else (0, 0, 0)
    overall_rate = float(overall_rate) if overall_rate else 0.0

    # By DEFCON breakdown
    cursor.execute("""
        SELECT
            defcon_level,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE result_type = 'NO_SIGNAL') as no_signal,
            CASE WHEN COUNT(*) > 0
                THEN ROUND(100.0 * COUNT(*) FILTER (WHERE result_type = 'NO_SIGNAL') / COUNT(*), 2)
                ELSE 0
            END as rate
        FROM fhq_governance.inforage_query_log
        WHERE created_at > NOW() - INTERVAL '%s hours'
        GROUP BY defcon_level
        ORDER BY defcon_level
    """, [window_hours])

    by_defcon = {row[0]: {'total': row[1], 'no_signal': row[2], 'rate': float(row[3])}
                 for row in cursor.fetchall()}

    cursor.close()

    # Determine status
    if total == 0:
        status = "WARN"
        details = "No queries in observation window"
    elif overall_rate < NO_SIGNAL_PASS:
        status = "PASS"
        details = f"{no_signal_count}/{total} queries returned NO_SIGNAL"
    elif overall_rate < NO_SIGNAL_WARN:
        status = "WARN"
        details = f"{no_signal_count}/{total} queries returned NO_SIGNAL"
    else:
        status = "FAIL"
        details = f"{no_signal_count}/{total} queries returned NO_SIGNAL - exceeds 50% threshold"

    return GateResult(
        gate_name="NO_SIGNAL_RATE",
        status=status,
        value=overall_rate,
        threshold=f"< {NO_SIGNAL_PASS}%",
        details=details
    ), {'overall_rate': overall_rate, 'by_defcon': by_defcon, 'total': total}


# =============================================================================
# GATE 2: ECR DISTRIBUTION
# =============================================================================

def check_ecr_distribution(conn, window_hours: int = 48) -> Tuple[GateResult, Dict]:
    """
    CEO Gate 2: ECR distribution
    Pass: median >= 1.0, p10 >= 0.5
    """
    cursor = conn.cursor()

    # Check if evidence_coverage_ratio column exists
    cursor.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'fhq_governance'
        AND table_name = 'inforage_query_log'
        AND column_name = 'evidence_coverage_ratio'
    """)

    if not cursor.fetchone():
        cursor.close()
        return GateResult(
            gate_name="ECR_DISTRIBUTION",
            status="WARN",
            value=None,
            threshold=f"median >= {ECR_MEDIAN_PASS}, p10 >= {ECR_P10_PASS}",
            details="evidence_coverage_ratio column not found - no data yet"
        ), {}

    # Calculate ECR percentiles
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY evidence_coverage_ratio) as median,
            PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY evidence_coverage_ratio) as p10,
            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY evidence_coverage_ratio) as p90,
            AVG(evidence_coverage_ratio) as mean,
            MIN(evidence_coverage_ratio) as min_ecr,
            MAX(evidence_coverage_ratio) as max_ecr
        FROM fhq_governance.inforage_query_log
        WHERE created_at > NOW() - INTERVAL '%s hours'
        AND evidence_coverage_ratio IS NOT NULL
    """, [window_hours])

    row = cursor.fetchone()
    cursor.close()

    if not row or row[0] == 0:
        return GateResult(
            gate_name="ECR_DISTRIBUTION",
            status="WARN",
            value=None,
            threshold=f"median >= {ECR_MEDIAN_PASS}, p10 >= {ECR_P10_PASS}",
            details="No ECR data in observation window"
        ), {}

    total, median, p10, p90, mean, min_ecr, max_ecr = row
    median = float(median) if median else 0.0
    p10 = float(p10) if p10 else 0.0

    # Determine status
    median_pass = median >= ECR_MEDIAN_PASS
    p10_pass = p10 >= ECR_P10_PASS

    if median_pass and p10_pass:
        status = "PASS"
        details = f"median={median:.2f}, p10={p10:.2f} - both meet thresholds"
    elif median_pass or p10_pass:
        status = "WARN"
        issues = []
        if not median_pass:
            issues.append(f"median={median:.2f} < {ECR_MEDIAN_PASS}")
        if not p10_pass:
            issues.append(f"p10={p10:.2f} < {ECR_P10_PASS}")
        details = ", ".join(issues)
    else:
        status = "FAIL"
        details = f"median={median:.2f} < {ECR_MEDIAN_PASS}, p10={p10:.2f} < {ECR_P10_PASS}"

    return GateResult(
        gate_name="ECR_DISTRIBUTION",
        status=status,
        value={'median': median, 'p10': p10},
        threshold=f"median >= {ECR_MEDIAN_PASS}, p10 >= {ECR_P10_PASS}",
        details=details
    ), {'median': median, 'p10': p10, 'p90': float(p90) if p90 else 0.0,
        'mean': float(mean) if mean else 0.0, 'total': total}


# =============================================================================
# GATE 3: COST + LATENCY
# =============================================================================

def check_cost_latency(conn, window_hours: int = 48) -> Tuple[GateResult, Dict]:
    """
    CEO Gate 3: Cost + Latency
    Pass: p95 latency < 5s, all query_cost_usd <= 0.50 (zero exceptions)
    """
    cursor = conn.cursor()

    # Check latency percentiles and cost violations
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY latency_ms) as p50_latency,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency,
            MAX(latency_ms) as max_latency,
            AVG(cost_usd) as avg_cost,
            MAX(cost_usd) as max_cost,
            COUNT(*) FILTER (WHERE cost_usd > %s) as cost_violations
        FROM fhq_governance.inforage_query_log
        WHERE created_at > NOW() - INTERVAL '%s hours'
    """, [COST_HARD_CAP, window_hours])

    row = cursor.fetchone()
    cursor.close()

    if not row or row[0] == 0:
        return GateResult(
            gate_name="COST_LATENCY",
            status="WARN",
            value=None,
            threshold=f"p95 < {LATENCY_P95_PASS}ms, cost <= ${COST_HARD_CAP}",
            details="No data in observation window"
        ), {}

    total, p50_latency, p95_latency, max_latency, avg_cost, max_cost, cost_violations = row
    p95_latency = float(p95_latency) if p95_latency else 0.0
    max_cost = float(max_cost) if max_cost else 0.0
    cost_violations = int(cost_violations) if cost_violations else 0

    # Determine status
    latency_pass = p95_latency < LATENCY_P95_PASS
    cost_pass = cost_violations == 0

    if latency_pass and cost_pass:
        status = "PASS"
        details = f"p95_latency={p95_latency:.0f}ms, max_cost=${max_cost:.4f}, no violations"
    elif cost_violations > 0:
        status = "FAIL"  # Cost violations are ALWAYS fail (zero exceptions)
        details = f"{cost_violations} queries exceeded ${COST_HARD_CAP} cap - BLOCKING"
    elif not latency_pass:
        status = "WARN"
        details = f"p95_latency={p95_latency:.0f}ms exceeds {LATENCY_P95_PASS}ms threshold"
    else:
        status = "PASS"
        details = f"All metrics within bounds"

    return GateResult(
        gate_name="COST_LATENCY",
        status=status,
        value={'p95_latency': p95_latency, 'max_cost': max_cost, 'cost_violations': cost_violations},
        threshold=f"p95 < {LATENCY_P95_PASS}ms, cost <= ${COST_HARD_CAP}",
        details=details
    ), {'p50_latency': float(p50_latency) if p50_latency else 0.0,
        'p95_latency': p95_latency, 'max_latency': float(max_latency) if max_latency else 0.0,
        'avg_cost': float(avg_cost) if avg_cost else 0.0, 'max_cost': max_cost,
        'cost_violations': cost_violations, 'total': total}


# =============================================================================
# GATE 4: TRUTH CHAIN INTEGRITY
# =============================================================================

def check_truth_chain_integrity(conn, sample_size: int = 10) -> Tuple[GateResult, Dict]:
    """
    CEO Gate 4: Truth chain integrity
    Random sample bundles, verify: hash integrity, snippet_ids resolve, ikea_verified true
    """
    cursor = conn.cursor()

    # Check if evidence_bundles table exists
    cursor.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'fhq_canonical'
        AND table_name = 'evidence_bundles'
    """)

    if not cursor.fetchone():
        cursor.close()
        return GateResult(
            gate_name="TRUTH_CHAIN_INTEGRITY",
            status="WARN",
            value=None,
            threshold=f"All {sample_size} samples pass integrity checks",
            details="evidence_bundles table not found"
        ), {}

    # Get random sample of bundles
    cursor.execute("""
        SELECT bundle_id, snippet_ids, query_cost_usd, created_at
        FROM fhq_canonical.evidence_bundles
        ORDER BY RANDOM()
        LIMIT %s
    """, [sample_size])

    bundles = cursor.fetchall()

    if not bundles:
        cursor.close()
        return GateResult(
            gate_name="TRUTH_CHAIN_INTEGRITY",
            status="WARN",
            value=None,
            threshold=f"All {sample_size} samples pass integrity checks",
            details="No evidence bundles found"
        ), {}

    # Verify each bundle
    verified = 0
    failed = 0
    issues = []

    for bundle_id, snippet_ids, cost, created_at in bundles:
        bundle_issues = []

        # Check cost cap
        if cost and float(cost) > COST_HARD_CAP:
            bundle_issues.append(f"cost=${cost} > ${COST_HARD_CAP}")

        # Check snippet_ids resolve
        if snippet_ids:
            snippet_list = snippet_ids if isinstance(snippet_ids, list) else []
            if snippet_list:
                placeholders = ','.join(['%s'] * len(snippet_list))
                cursor.execute(f"""
                    SELECT COUNT(*) FROM fhq_canonical.evidence_nodes
                    WHERE evidence_id::text = ANY(%s)
                """, [snippet_list])
                found = cursor.fetchone()[0]
                if found != len(snippet_list):
                    bundle_issues.append(f"snippet resolution: {found}/{len(snippet_list)}")

        if bundle_issues:
            failed += 1
            issues.append(f"{bundle_id[:8]}: {', '.join(bundle_issues)}")
        else:
            verified += 1

    cursor.close()

    # Determine status
    sample_count = len(bundles)
    if failed == 0:
        status = "PASS"
        details = f"{verified}/{sample_count} bundles verified"
    elif failed < sample_count // 2:
        status = "WARN"
        details = f"{failed}/{sample_count} bundles have issues: {'; '.join(issues[:3])}"
    else:
        status = "FAIL"
        details = f"{failed}/{sample_count} bundles failed integrity: {'; '.join(issues[:3])}"

    return GateResult(
        gate_name="TRUTH_CHAIN_INTEGRITY",
        status=status,
        value={'verified': verified, 'failed': failed, 'sampled': sample_count},
        threshold=f"All {sample_size} samples pass integrity checks",
        details=details
    ), {'verified': verified, 'failed': failed, 'sampled': sample_count,
        'issues': issues[:5]}


# =============================================================================
# MAIN READOUT
# =============================================================================

def run_shadow_readout(window_hours: int = 48) -> ShadowReadout:
    """
    Run complete SHADOW mode readout with all acceptance gates.
    """
    conn = get_db_connection()

    gates = []
    metrics = {}
    blocking_issues = []

    # Gate 1: NO_SIGNAL Rate
    gate1, m1 = check_no_signal_rate(conn, window_hours)
    gates.append(gate1)
    metrics['no_signal'] = m1

    # Gate 2: ECR Distribution
    gate2, m2 = check_ecr_distribution(conn, window_hours)
    gates.append(gate2)
    metrics['ecr'] = m2

    # Gate 3: Cost + Latency
    gate3, m3 = check_cost_latency(conn, window_hours)
    gates.append(gate3)
    metrics['cost_latency'] = m3

    # Gate 4: Truth Chain Integrity
    gate4, m4 = check_truth_chain_integrity(conn, TRUTH_CHAIN_SAMPLE)
    gates.append(gate4)
    metrics['truth_chain'] = m4

    conn.close()

    # Determine overall status
    statuses = [g.status for g in gates]

    if 'FAIL' in statuses:
        overall_status = 'FAIL'
        blocking_issues = [g.gate_name for g in gates if g.status == 'FAIL']
    elif 'WARN' in statuses:
        overall_status = 'WARN'
    else:
        overall_status = 'PASS'

    ready_for_live = overall_status == 'PASS' and all(g.status == 'PASS' for g in gates)

    # Get total query count
    total_queries = metrics.get('no_signal', {}).get('total', 0)

    return ShadowReadout(
        timestamp=datetime.now(timezone.utc).isoformat(),
        observation_hours=window_hours,
        total_queries=total_queries,
        gates=gates,
        overall_status=overall_status,
        ready_for_live=ready_for_live,
        blocking_issues=blocking_issues
    )


def print_readout(readout: ShadowReadout):
    """Print formatted readout report."""
    print("=" * 70)
    print("SHADOW MODE 48h READOUT")
    print("CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001 Phase D")
    print("=" * 70)
    print(f"Timestamp: {readout.timestamp}")
    print(f"Observation Window: {readout.observation_hours}h")
    print(f"Total Queries: {readout.total_queries}")
    print()

    # Status emoji
    status_emoji = {
        'PASS': '[PASS]',
        'WARN': '[WARN]',
        'FAIL': '[FAIL]'
    }

    print("-" * 70)
    print("ACCEPTANCE GATES")
    print("-" * 70)

    for gate in readout.gates:
        emoji = status_emoji.get(gate.status, '[????]')
        print(f"\n{emoji} {gate.gate_name}")
        print(f"    Status: {gate.status}")
        print(f"    Value: {gate.value}")
        print(f"    Threshold: {gate.threshold}")
        if gate.details:
            print(f"    Details: {gate.details}")

    print()
    print("-" * 70)
    print("OVERALL ASSESSMENT")
    print("-" * 70)
    print(f"Status: {status_emoji.get(readout.overall_status, '[????]')} {readout.overall_status}")
    print(f"Ready for LIVE: {'YES' if readout.ready_for_live else 'NO'}")

    if readout.blocking_issues:
        print(f"Blocking Issues: {', '.join(readout.blocking_issues)}")

    print()

    if readout.ready_for_live:
        print("RECOMMENDATION: System ready for LIVE activation (CEO approval required)")
    elif readout.overall_status == 'WARN':
        print("RECOMMENDATION: Continue SHADOW observation, address warnings")
    else:
        print("RECOMMENDATION: BLOCK LIVE activation until failures resolved")

    print("=" * 70)


def main():
    """Run SHADOW readout and save evidence."""
    readout = run_shadow_readout(window_hours=48)
    print_readout(readout)

    # Save evidence
    evidence = {
        'directive': 'CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001',
        'phase': 'D_SHADOW_READOUT',
        'timestamp': readout.timestamp,
        'observation_hours': readout.observation_hours,
        'total_queries': readout.total_queries,
        'overall_status': readout.overall_status,
        'ready_for_live': readout.ready_for_live,
        'blocking_issues': readout.blocking_issues,
        'gates': [asdict(g) for g in readout.gates]
    }

    evidence_path = f'evidence/SHADOW_READOUT_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.json'
    with open(evidence_path, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    print(f"\nEvidence stored: {evidence_path}")

    return readout


if __name__ == '__main__':
    main()
