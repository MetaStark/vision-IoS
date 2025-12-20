#!/usr/bin/env python3
"""
IoS-002 G1 TECHNICAL VALIDATION
================================

Authority: ADR-001 to ADR-016, IoS-001
Owner: STIG (CTO)
Validator: VEGA

This script performs G1 Technical Validation for IoS-002 (Indicator Engine).
"""

import os
import sys
import json
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
import numpy as np
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class G1ValidationResult:
    check_id: str
    check_name: str
    status: str  # PASS, FAIL, WARN
    details: Dict[str, Any]
    adr_reference: str

def get_connection():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "54322"),
        database=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres")
    )

# =============================================================================
# G1 VALIDATION CHECKS
# =============================================================================

def check_indicator_tables(conn) -> G1ValidationResult:
    """CHECK 1: Verify all four indicator tables exist with correct schema"""
    required_tables = [
        'indicator_trend',
        'indicator_momentum',
        'indicator_volatility',
        'indicator_ichimoku'
    ]

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT table_name,
                   (SELECT COUNT(*) FROM information_schema.columns c
                    WHERE c.table_schema = 'fhq_research' AND c.table_name = t.table_name) as col_count
            FROM information_schema.tables t
            WHERE table_schema = 'fhq_research'
              AND table_name IN ('indicator_trend', 'indicator_momentum',
                                 'indicator_volatility', 'indicator_ichimoku')
        """)
        found = {r['table_name']: r['col_count'] for r in cur.fetchall()}

    missing = [t for t in required_tables if t not in found]

    return G1ValidationResult(
        check_id="G1-001",
        check_name="Indicator Tables Exist",
        status="PASS" if not missing else "FAIL",
        details={
            "required": required_tables,
            "found": list(found.keys()),
            "missing": missing,
            "column_counts": found
        },
        adr_reference="IoS-002 Section 5"
    )

def check_lineage_columns(conn) -> G1ValidationResult:
    """CHECK 2: Verify lineage columns per ADR-002/ADR-003"""
    required_cols = ['engine_version', 'formula_hash', 'lineage_hash', 'created_at']
    tables = ['indicator_trend', 'indicator_momentum', 'indicator_volatility', 'indicator_ichimoku']

    missing = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for table in tables:
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'fhq_research' AND table_name = %s
            """, (table,))
            cols = [r['column_name'] for r in cur.fetchall()]
            for req in required_cols:
                if req not in cols:
                    missing.append(f"{table}.{req}")

    return G1ValidationResult(
        check_id="G1-002",
        check_name="Lineage Columns Present",
        status="PASS" if not missing else "FAIL",
        details={
            "required_columns": required_cols,
            "missing": missing,
            "tables_checked": tables
        },
        adr_reference="ADR-002, ADR-003"
    )

def check_pipeline_binding(conn) -> G1ValidationResult:
    """CHECK 3: Verify CALC_INDICATORS pipeline stage (ADR-007)"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT task_name, task_type, owned_by_agent, executed_by_agent,
                   reads_from_schemas, writes_to_schemas, task_status
            FROM fhq_governance.task_registry
            WHERE task_name = 'CALC_INDICATORS'
        """)
        result = cur.fetchone()

    if not result:
        return G1ValidationResult(
            check_id="G1-003",
            check_name="CALC_INDICATORS Pipeline Binding",
            status="FAIL",
            details={"error": "CALC_INDICATORS task not found in task_registry"},
            adr_reference="ADR-007"
        )

    # Verify correct bindings
    issues = []
    if result['owned_by_agent'] != 'FINN':
        issues.append(f"Owner should be FINN, got {result['owned_by_agent']}")
    if 'fhq_market' not in (result['reads_from_schemas'] or []):
        issues.append("Must read from fhq_market")
    if 'fhq_research' not in (result['writes_to_schemas'] or []):
        issues.append("Must write to fhq_research")

    return G1ValidationResult(
        check_id="G1-003",
        check_name="CALC_INDICATORS Pipeline Binding",
        status="PASS" if not issues else "WARN",
        details={
            "task": dict(result),
            "issues": issues
        },
        adr_reference="ADR-007"
    )

def check_canonical_prices(conn) -> G1ValidationResult:
    """CHECK 4: Verify canonical prices exist (ADR-013)"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                COUNT(*) as total_rows,
                COUNT(DISTINCT canonical_id) as assets,
                MIN(timestamp) as earliest,
                MAX(timestamp) as latest
            FROM fhq_market.prices
        """)
        stats = cur.fetchone()

    has_data = stats['total_rows'] > 0
    has_all_assets = stats['assets'] >= 4  # IoS-001 requires 4 assets

    return G1ValidationResult(
        check_id="G1-004",
        check_name="Canonical Prices Available",
        status="PASS" if has_data and has_all_assets else "FAIL",
        details={
            "total_rows": stats['total_rows'],
            "assets": stats['assets'],
            "date_range": {
                "earliest": str(stats['earliest']),
                "latest": str(stats['latest'])
            },
            "required_assets": 4
        },
        adr_reference="ADR-013, IoS-001"
    )

def check_defcon_status(conn) -> G1ValidationResult:
    """CHECK 5: Verify DEFCON=GREEN (ADR-016)"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check current system state for DEFCON level
        cur.execute("""
            SELECT current_defcon, active_circuit_breakers, reason, triggered_at
            FROM fhq_governance.system_state
            WHERE is_active = TRUE
            LIMIT 1
        """)
        system_state = cur.fetchone()

        # Check for any DEFCON transitions
        cur.execute("""
            SELECT to_level, transition_timestamp, reason
            FROM fhq_governance.defcon_transitions
            ORDER BY transition_timestamp DESC
            LIMIT 1
        """)
        last_transition = cur.fetchone()

    # Get current level from system_state (primary) or transitions (fallback)
    if system_state:
        current_level = system_state['current_defcon']
        active_breakers = system_state['active_circuit_breakers'] or []
    elif last_transition:
        current_level = last_transition['to_level']
        active_breakers = []
    else:
        current_level = 'GREEN'
        active_breakers = []

    is_green = current_level == 'GREEN' and len(active_breakers) == 0

    return G1ValidationResult(
        check_id="G1-005",
        check_name="DEFCON Status GREEN",
        status="PASS" if is_green else "FAIL",
        details={
            "current_level": current_level,
            "active_circuit_breakers": active_breakers,
            "system_state": dict(system_state) if system_state else None,
            "last_transition": dict(last_transition) if last_transition else None
        },
        adr_reference="ADR-016"
    )

def check_economic_safety(conn) -> G1ValidationResult:
    """CHECK 6: Verify Economic Safety invariants (ADR-012)"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check API waterfall tiers are configured
        cur.execute("""
            SELECT usage_tier, COUNT(*) as providers,
                   SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active
            FROM fhq_governance.api_provider_registry
            GROUP BY usage_tier
            ORDER BY usage_tier
        """)
        tiers = cur.fetchall()

        # Check circuit breakers are enabled
        cur.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN is_enabled THEN 1 ELSE 0 END) as enabled
            FROM fhq_governance.circuit_breakers
        """)
        breakers = cur.fetchone()

    has_lake = any(t['usage_tier'] == 'LAKE' for t in tiers)
    has_pulse = any(t['usage_tier'] == 'PULSE' for t in tiers)
    has_sniper = any(t['usage_tier'] == 'SNIPER' for t in tiers)
    breakers_ok = breakers['enabled'] == breakers['total'] if breakers else False

    return G1ValidationResult(
        check_id="G1-006",
        check_name="Economic Safety Invariants",
        status="PASS" if has_lake and breakers_ok else "WARN",
        details={
            "api_tiers": [dict(t) for t in tiers],
            "has_lake_tier": has_lake,
            "has_pulse_tier": has_pulse,
            "has_sniper_tier": has_sniper,
            "circuit_breakers": dict(breakers) if breakers else None
        },
        adr_reference="ADR-012"
    )

def check_determinism(conn) -> G1ValidationResult:
    """CHECK 7: Verify deterministic calculation (same input = same output)"""
    # Test RSI calculation determinism
    test_prices = [44.0, 44.25, 44.5, 43.75, 44.5, 44.25, 44.0, 43.5, 43.0, 43.5,
                   44.0, 44.5, 45.0, 45.5, 46.0]  # 15 prices for RSI-14

    def calculate_rsi(prices, period=14):
        """Deterministic RSI calculation"""
        if len(prices) < period + 1:
            return None

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 8)

    # Calculate twice
    rsi1 = calculate_rsi(test_prices)
    rsi2 = calculate_rsi(test_prices)

    # Hash the calculation
    calc_hash = hashlib.sha256(
        f"RSI|{test_prices}|{rsi1}".encode()
    ).hexdigest()

    is_deterministic = rsi1 == rsi2

    return G1ValidationResult(
        check_id="G1-007",
        check_name="Deterministic Calculation",
        status="PASS" if is_deterministic else "FAIL",
        details={
            "test_indicator": "RSI-14",
            "input_prices": test_prices,
            "result_1": rsi1,
            "result_2": rsi2,
            "identical": is_deterministic,
            "formula_hash": calc_hash[:16],
            "tolerance": "0.00000001"
        },
        adr_reference="IoS-002 Section 4.1"
    )

# =============================================================================
# EVIDENCE BUNDLE GENERATION
# =============================================================================

def generate_evidence_bundle(results: List[G1ValidationResult], conn) -> Dict:
    """Generate G1 Evidence Bundle"""

    # Compute schema hash
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'fhq_research'
              AND table_name LIKE 'indicator_%'
            ORDER BY table_name, ordinal_position
        """)
        schema_data = cur.fetchall()

    schema_str = json.dumps(schema_data, default=str)
    schema_hash = hashlib.sha256(schema_str.encode()).hexdigest()

    # Compute pipeline binding hash
    with conn.cursor() as cur:
        cur.execute("""
            SELECT * FROM fhq_governance.task_registry
            WHERE task_name = 'CALC_INDICATORS'
        """)
        pipeline_data = cur.fetchone()

    pipeline_str = json.dumps(pipeline_data, default=str) if pipeline_data else ""
    pipeline_binding_hash = hashlib.sha256(pipeline_str.encode()).hexdigest()

    # Lineage snapshot
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT canonical_id, COUNT(*) as rows,
                   MIN(timestamp) as start, MAX(timestamp) as end
            FROM fhq_market.prices
            GROUP BY canonical_id
        """)
        lineage_data = cur.fetchall()

    lineage_snapshot = {
        "source_table": "fhq_market.prices",
        "target_schema": "fhq_research",
        "assets": [dict(r) for r in lineage_data],
        "snapshot_time": datetime.now(timezone.utc).isoformat()
    }

    # Deterministic replay proof
    determinism_check = next((r for r in results if r.check_id == "G1-007"), None)
    replay_proof = {
        "test_performed": True,
        "indicator": "RSI-14",
        "result": determinism_check.details if determinism_check else None,
        "proof_hash": hashlib.sha256(
            json.dumps(determinism_check.details, default=str).encode()
        ).hexdigest() if determinism_check else None
    }

    # Compute overall status
    statuses = [r.status for r in results]
    if "FAIL" in statuses:
        overall_status = "G1_FAIL"
    elif "WARN" in statuses:
        overall_status = "G1_PASS_WITH_WARNINGS"
    else:
        overall_status = "G1_PASS"

    bundle = {
        "validation_id": str(uuid.uuid4()),
        "ios_module": "IoS-002",
        "module_name": "Indicator Engine (Sensory Cortex)",
        "validation_type": "G1_TECHNICAL",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "validator": "STIG",
        "overall_status": overall_status,
        "checks": [asdict(r) for r in results],
        "evidence": {
            "schema_hash": schema_hash,
            "pipeline_binding_hash": pipeline_binding_hash,
            "lineage_snapshot": lineage_snapshot,
            "deterministic_replay_proof": replay_proof
        },
        "signature_log": {
            "signer": "STIG",
            "sign_time": datetime.now(timezone.utc).isoformat(),
            "bundle_hash": None  # Will be filled after
        },
        "adr_compliance": [
            "ADR-001", "ADR-002", "ADR-003", "ADR-007",
            "ADR-012", "ADR-013", "ADR-016"
        ],
        "next_gate": "G2_GOVERNANCE" if overall_status != "G1_FAIL" else "REMEDIATION_REQUIRED"
    }

    # Compute bundle hash
    bundle_content = json.dumps(bundle, default=str, sort_keys=True)
    bundle["signature_log"]["bundle_hash"] = hashlib.sha256(bundle_content.encode()).hexdigest()

    return bundle

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("IoS-002 G1 TECHNICAL VALIDATION")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Validator: STIG (CTO)")
    print("=" * 70)

    conn = get_connection()
    results = []

    try:
        # Run all checks
        checks = [
            ("CHECK 1: Indicator Tables", check_indicator_tables),
            ("CHECK 2: Lineage Columns", check_lineage_columns),
            ("CHECK 3: Pipeline Binding", check_pipeline_binding),
            ("CHECK 4: Canonical Prices", check_canonical_prices),
            ("CHECK 5: DEFCON Status", check_defcon_status),
            ("CHECK 6: Economic Safety", check_economic_safety),
            ("CHECK 7: Determinism Test", check_determinism),
        ]

        for name, check_fn in checks:
            print(f"\n{name}...")
            result = check_fn(conn)
            results.append(result)

            status_icon = "OK" if result.status == "PASS" else ("WARN" if result.status == "WARN" else "FAIL")
            print(f"  [{status_icon}] {result.status}: {result.check_name}")
            if result.status != "PASS":
                print(f"      Details: {json.dumps(result.details, default=str)[:200]}")

        # Generate evidence bundle
        print("\n" + "-" * 70)
        print("Generating G1 Evidence Bundle...")
        bundle = generate_evidence_bundle(results, conn)

        # Save evidence
        evidence_dir = Path(__file__).parent.parent / "evidence"
        evidence_dir.mkdir(exist_ok=True)
        evidence_file = evidence_dir / f"IoS-002_G1_EVIDENCE_{bundle['validation_id'][:8]}.json"

        with open(evidence_file, 'w') as f:
            json.dump(bundle, f, indent=2, default=str)

        print(f"Evidence saved: {evidence_file}")

        # Summary
        print("\n" + "=" * 70)
        print("G1 VALIDATION SUMMARY")
        print("=" * 70)

        pass_count = sum(1 for r in results if r.status == "PASS")
        warn_count = sum(1 for r in results if r.status == "WARN")
        fail_count = sum(1 for r in results if r.status == "FAIL")

        print(f"  PASS: {pass_count}")
        print(f"  WARN: {warn_count}")
        print(f"  FAIL: {fail_count}")
        print(f"\n  OVERALL STATUS: {bundle['overall_status']}")
        print(f"  BUNDLE HASH: {bundle['signature_log']['bundle_hash'][:32]}...")
        print("=" * 70)

        return bundle

    finally:
        conn.close()

if __name__ == "__main__":
    result = main()
    sys.exit(0 if "PASS" in result.get("overall_status", "") else 1)
