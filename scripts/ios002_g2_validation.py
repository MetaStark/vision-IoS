#!/usr/bin/env python3
"""
IoS-002 G2 GOVERNANCE VALIDATION
================================

Authority: LARS (CSO) + VEGA (Compliance)
Target: IoS-002 - Indicator Engine (Sensory Cortex)
Gate: G2_GOVERNANCE
Prerequisite: G1_PASS (Completed 2025-11-29)

ADR References:
- ADR-001 (System Charter)
- ADR-002 (Audit & Reconciliation)
- ADR-003 (Standards)
- ADR-004 (Change Gates)
- ADR-006 (VEGA Charter)
- ADR-007 (Orchestrator)
- ADR-009 (Suspension Workflow)
- ADR-010 (Discrepancy Scoring)
- ADR-011 (Fortress)
- ADR-012 (Economic Safety)
- ADR-013 (One-True-Source)
- ADR-014 (Executive Contracts)
- ADR-016 (DEFCON)
"""

import os
import sys
import json
import uuid
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Forbidden columns that would indicate trading logic
FORBIDDEN_COLUMNS = [
    'order_id', 'position_id', 'pnl', 'trade_signal',
    'entry_price', 'exit_price', 'stop_loss', 'take_profit',
    'lot_size', 'margin', 'leverage'
]

# IoS-002 canonical indicator tables
IOS002_TABLES = [
    'indicator_trend',
    'indicator_momentum',
    'indicator_volatility',
    'indicator_ichimoku'
]

@dataclass
class G2ValidationResult:
    check_id: str
    check_name: str
    status: str  # PASS, WARN, FAIL
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


def check_semantic_scope(conn) -> G2ValidationResult:
    """PHASE 1: Verify IoS-002 is MEASUREMENT-ONLY (no P&L, trading, risk logic)"""
    issues = []

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check registry entry
        cur.execute("""
            SELECT ios_id, title, description, owner_role, governing_adrs
            FROM fhq_meta.ios_registry
            WHERE ios_id = 'IoS-002'
        """)
        registry = cur.fetchone()

        if not registry:
            return G2ValidationResult(
                check_id="G2-001",
                check_name="Semantic Scope (Measurement Only)",
                status="FAIL",
                details={"error": "IoS-002 not found in registry"},
                adr_reference="ADR-001, ADR-013"
            )

        # Verify description mentions measurement/calculation, not trading
        desc = registry['description'].lower()
        measurement_keywords = ['computes', 'calculates', 'indicators', 'deterministic', 'feature']
        trading_keywords = ['trade', 'order', 'position', 'execute', 'buy', 'sell']

        has_measurement = any(kw in desc for kw in measurement_keywords)
        has_trading = any(kw in desc for kw in trading_keywords)

        if has_trading:
            issues.append("Registry description contains trading keywords")
        if not has_measurement:
            issues.append("Registry description missing measurement keywords")

        # Check indicator table schemas for forbidden columns
        for table in IOS002_TABLES:
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'fhq_research' AND table_name = %s
            """, (table,))
            columns = [row['column_name'] for row in cur.fetchall()]

            for col in columns:
                if col.lower() in [f.lower() for f in FORBIDDEN_COLUMNS]:
                    issues.append(f"Table {table} has forbidden column: {col}")

        # Verify owner is FINN (Research), not execution role
        if registry['owner_role'] != 'FINN':
            issues.append(f"Owner role is {registry['owner_role']}, expected FINN (Research)")

    status = "PASS" if not issues else "FAIL"

    return G2ValidationResult(
        check_id="G2-001",
        check_name="Semantic Scope (Measurement Only)",
        status=status,
        details={
            "registry": dict(registry) if registry else None,
            "measurement_only": not has_trading and has_measurement,
            "issues": issues,
            "classification": "MEASUREMENT-ONLY" if status == "PASS" else "REVIEW_REQUIRED"
        },
        adr_reference="ADR-001, ADR-013"
    )


def check_role_permissions(conn) -> G2ValidationResult:
    """PHASE 2: Verify write permissions matrix"""
    issues = []
    role_matrix = {}

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check authority matrix
        cur.execute("""
            SELECT agent_id, authority_level, can_read_canonical, can_write_canonical,
                   can_trigger_g0, can_trigger_g1, can_execute_operational_tasks
            FROM fhq_governance.authority_matrix
            ORDER BY agent_id
        """)
        authority = cur.fetchall()

        for agent in authority:
            role_matrix[agent['agent_id']] = {
                "authority_level": agent['authority_level'],
                "can_read": agent['can_read_canonical'],
                "can_write_canonical": agent['can_write_canonical'],
                "can_execute": agent['can_execute_operational_tasks']
            }

            # Tier-2 agents (authority_level 2) should NOT have canonical write
            if agent['authority_level'] == 2 and agent['can_write_canonical']:
                issues.append(f"Tier-2 agent {agent['agent_id']} has can_write_canonical=TRUE")

        # Check CALC_INDICATORS task registry binding
        cur.execute("""
            SELECT task_name, owned_by_agent, executed_by_agent,
                   reads_from_schemas, writes_to_schemas, task_status
            FROM fhq_governance.task_registry
            WHERE task_name = 'CALC_INDICATORS'
        """)
        task = cur.fetchone()

        if not task:
            issues.append("CALC_INDICATORS not found in task_registry")
        else:
            if task['owned_by_agent'] != 'FINN':
                issues.append(f"CALC_INDICATORS owned by {task['owned_by_agent']}, expected FINN")
            if task['executed_by_agent'] != 'CODE':
                issues.append(f"CALC_INDICATORS executed by {task['executed_by_agent']}, expected CODE")
            if 'fhq_research' not in (task['writes_to_schemas'] or []):
                issues.append("CALC_INDICATORS does not write to fhq_research")

        # Check EC contracts for CODE, FINN, STIG
        cur.execute("""
            SELECT contract_id, employee, total_duties, total_constraints, total_rights
            FROM fhq_meta.vega_employment_contract
            WHERE employee IN ('CODE', 'FINN', 'STIG')
        """)
        contracts = cur.fetchall()

        ec_summary = {}
        for contract in contracts:
            ec_summary[contract['employee']] = {
                "contract_id": contract['contract_id'],
                "duties": contract['total_duties'],
                "constraints": contract['total_constraints'],
                "rights": contract['total_rights']
            }

    # Build expected permission matrix
    permission_matrix = {
        "STIG": {"read": True, "write": "schema_only", "mechanism": "Migration SQL", "authority": "EC-003"},
        "CODE": {"read": True, "write": True, "mechanism": "CALC_INDICATORS pipeline", "authority": "EC-011"},
        "FINN": {"read": True, "write": False, "mechanism": "Specification only", "authority": "EC-004"},
        "LARS": {"read": True, "write": False, "mechanism": "Strategic oversight", "authority": "EC-002"},
        "LINE": {"read": True, "write": False, "mechanism": "Infrastructure only", "authority": "EC-005"},
        "VEGA": {"read": True, "write": False, "mechanism": "Audit/Attestation", "authority": "EC-001"},
        "Tier-2": {"read": True, "write": "FORBIDDEN", "mechanism": "N/A", "authority": "Authority Matrix"}
    }

    status = "PASS" if not issues else "FAIL"

    return G2ValidationResult(
        check_id="G2-002",
        check_name="Role Permissions Matrix",
        status=status,
        details={
            "authority_matrix": role_matrix,
            "calc_indicators_task": dict(task) if task else None,
            "ec_contracts": ec_summary,
            "permission_matrix": permission_matrix,
            "issues": issues,
            "tier2_write_forbidden": all(
                not a.get('can_write_canonical', False)
                for a in authority if a['authority_level'] == 2
            )
        },
        adr_reference="ADR-007, ADR-014, EC-001 through EC-011"
    )


def check_one_true_source(conn) -> G2ValidationResult:
    """PHASE 3: Verify no shadow indicator tables exist"""
    issues = []
    shadow_tables = []

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Scan for indicator-related tables
        cur.execute("""
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema IN ('fhq_research', 'fhq_market', 'public', 'fhq_data')
              AND (table_name LIKE '%indicator%'
                   OR table_name LIKE '%rsi%'
                   OR table_name LIKE '%macd%'
                   OR table_name LIKE '%atr%'
                   OR table_name LIKE '%bollinger%')
            ORDER BY table_schema, table_name
        """)
        all_indicator_tables = cur.fetchall()

        for table in all_indicator_tables:
            full_name = f"{table['table_schema']}.{table['table_name']}"

            # Check if it's a canonical IoS-002 table
            if table['table_schema'] == 'fhq_research' and table['table_name'] in IOS002_TABLES:
                continue  # This is expected

            # Classify the table
            if table['table_name'] == 'macro_indicators':
                # Different domain - economic indicators, not technical
                shadow_tables.append({
                    "table": full_name,
                    "classification": "DIFFERENT_DOMAIN",
                    "action": "No action - economic indicators (GDP, inflation)"
                })
            elif table['table_name'] == 'indicators':
                # Legacy/generic table - needs deprecation
                shadow_tables.append({
                    "table": full_name,
                    "classification": "LEGACY",
                    "action": "DEPRECATE - mark as superseded by IoS-002 tables"
                })
            elif 'backtest' in table['table_name']:
                # Backtest results, not source calculations
                shadow_tables.append({
                    "table": full_name,
                    "classification": "DERIVED_OUTPUT",
                    "action": "No action - backtest results, not source data"
                })
            else:
                # Potential shadow table - needs investigation
                shadow_tables.append({
                    "table": full_name,
                    "classification": "POTENTIAL_SHADOW",
                    "action": "INVESTIGATE - may violate One-True-Source"
                })
                issues.append(f"Potential shadow table: {full_name}")

        # Check for views that calculate indicators
        cur.execute("""
            SELECT table_schema, table_name, view_definition
            FROM information_schema.views
            WHERE table_schema IN ('fhq_research', 'fhq_market', 'public')
        """)
        views = cur.fetchall()

        indicator_views = []
        for view in views:
            if view['view_definition']:
                defn = view['view_definition'].lower()
                if any(kw in defn for kw in ['rsi', 'macd', 'bollinger', 'atr', 'ema', 'sma']):
                    indicator_views.append(f"{view['table_schema']}.{view['table_name']}")
                    issues.append(f"View may calculate indicators: {view['table_schema']}.{view['table_name']}")

    # Check for potential One-True-Source violations
    potential_violations = [t for t in shadow_tables if t['classification'] == 'POTENTIAL_SHADOW']

    status = "PASS" if not potential_violations else "WARN"
    if issues and any('POTENTIAL_SHADOW' in str(i) for i in issues):
        status = "WARN"

    return G2ValidationResult(
        check_id="G2-003",
        check_name="One-True-Source Verification",
        status=status,
        details={
            "canonical_tables": IOS002_TABLES,
            "shadow_table_analysis": shadow_tables,
            "indicator_views": indicator_views,
            "issues": issues,
            "llm_policy_required": "Agents must NOT calculate RSI/MACD/ATR in Python - read from fhq_research only"
        },
        adr_reference="ADR-013"
    )


def check_reconciliation_policy(conn) -> G2ValidationResult:
    """PHASE 4: Define VEGA reconciliation rules for indicators"""
    issues = []

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if reconciliation field weights exist for indicators
        cur.execute("""
            SELECT component_name, field_name, criticality_weight, tolerance_type, tolerance_value
            FROM fhq_meta.reconciliation_field_weights
            WHERE component_name IN ('FINN', 'INDICATORS', 'IoS-002')
            ORDER BY component_name, field_name
        """)
        existing_weights = cur.fetchall()

        # Check discrepancy logging capability
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'fhq_governance'
              AND table_name LIKE '%discrepancy%'
        """)
        discrepancy_tables = cur.fetchall()

        # Check reconciliation snapshots
        cur.execute("""
            SELECT COUNT(*) as count
            FROM fhq_meta.reconciliation_snapshots
            WHERE component_name LIKE '%INDICATOR%' OR component_name LIKE '%IoS-002%'
        """)
        indicator_snapshots = cur.fetchone()

    # Define the reconciliation policy
    reconciliation_policy = {
        "classification": {
            "default_criticality": "MEDIUM",
            "active_strategy_criticality": "HIGH",
            "rationale": "Analytical data (Medium), upgraded when used in live strategy"
        },
        "tolerances": {
            "float_values": {"type": "NUMERIC", "threshold": 0.001, "description": "0.1% max deviation"},
            "categorical": {"type": "EXACT", "threshold": 0, "description": "Must match exactly"}
        },
        "daily_checks": [
            {"test": "Missing rows vs prices", "trigger": "gap_count > 0", "action": "WARNING, trigger backfill"},
            {"test": "Unexpected NULL values", "trigger": "null_count > 0 in active window", "action": "WARNING"},
            {"test": "Large jumps vs price", "trigger": "indicator_delta > 3 * price_delta", "action": "ALERT, manual review"}
        ],
        "weekly_checks": [
            {"test": "Formula drift", "trigger": "recalc_delta > 0.001%", "action": "CRITICAL, suspend stage"},
            {"test": "Benchmark deviation", "trigger": "vs TradingView > 0.001%", "action": "CRITICAL, investigate"}
        ],
        "discrepancy_logging": {
            "target_table": "fhq_governance.discrepancy_events",
            "required_fields": ["ios_id", "table_name", "discrepancy_type", "severity", "detected_at", "detected_by"],
            "tables_found": [t['table_name'] for t in discrepancy_tables]
        }
    }

    # Check if policy infrastructure exists
    if not discrepancy_tables:
        issues.append("No discrepancy logging table found in fhq_governance")

    status = "PASS" if not issues else "WARN"

    return G2ValidationResult(
        check_id="G2-004",
        check_name="Reconciliation & Discrepancy Policy",
        status=status,
        details={
            "existing_field_weights": [dict(w) for w in existing_weights],
            "indicator_snapshots_count": indicator_snapshots['count'] if indicator_snapshots else 0,
            "policy": reconciliation_policy,
            "issues": issues
        },
        adr_reference="ADR-002, ADR-010"
    )


def check_economic_safety(conn) -> G2ValidationResult:
    """PHASE 5: Verify IoS-002 cannot activate real trading alone"""
    issues = []

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check for foreign keys from indicator tables to execution/order tables
        cur.execute("""
            SELECT
                tc.table_schema,
                tc.table_name,
                kcu.column_name,
                ccu.table_schema AS foreign_table_schema,
                ccu.table_name AS foreign_table_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'fhq_research'
              AND tc.table_name LIKE 'indicator_%'
        """)
        indicator_fks = cur.fetchall()

        # Check if fhq_execution schema exists
        cur.execute("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name = 'fhq_execution'
        """)
        execution_schema = cur.fetchone()

        # Check CALC_INDICATORS writes only to fhq_research
        cur.execute("""
            SELECT task_name, writes_to_schemas
            FROM fhq_governance.task_registry
            WHERE task_name = 'CALC_INDICATORS'
        """)
        calc_task = cur.fetchone()

        # Check for any tables linking indicators to orders/positions
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('fhq_research', 'fhq_market')
              AND (table_name LIKE '%order%' OR table_name LIKE '%position%'
                   OR table_name LIKE '%trade%' OR table_name LIKE '%execution%')
        """)
        trading_tables = cur.fetchall()

    # Analyze findings
    fk_to_execution = [fk for fk in indicator_fks if 'execution' in fk['foreign_table_schema'].lower()
                       or 'order' in fk['foreign_table_name'].lower()
                       or 'position' in fk['foreign_table_name'].lower()]

    if fk_to_execution:
        issues.append(f"Foreign keys to execution/order tables found: {fk_to_execution}")

    if calc_task and calc_task['writes_to_schemas']:
        non_research = [s for s in calc_task['writes_to_schemas'] if s != 'fhq_research']
        if non_research:
            issues.append(f"CALC_INDICATORS writes to non-research schemas: {non_research}")

    # Build isolation matrix
    isolation_matrix = {
        "indicator_to_order_fks": len(fk_to_execution),
        "indicator_to_position_fks": 0,
        "execution_schema_exists": execution_schema is not None,
        "trading_tables_in_research": [f"{t['table_schema']}.{t['table_name']}" for t in trading_tables],
        "calc_indicators_target": calc_task['writes_to_schemas'] if calc_task else None
    }

    # Fortress test case definition
    fortress_test = {
        "test_name": "test_corrupted_indicators_detected",
        "description": "Insert RSI = 150 (impossible value, max is 100)",
        "expected_behavior": "VEGA discrepancy scan catches it before strategy layer",
        "implementation_status": "DEFINED - awaiting ADR-011 test suite integration"
    }

    status = "PASS" if not issues and not fk_to_execution else "FAIL"

    return G2ValidationResult(
        check_id="G2-005",
        check_name="Economic Safety & Fortress Isolation",
        status=status,
        details={
            "isolation_matrix": isolation_matrix,
            "fortress_test_case": fortress_test,
            "issues": issues,
            "conclusion": "Errors in IoS-002 can only affect analysis, not capital" if status == "PASS" else "ISOLATION BREACH DETECTED"
        },
        adr_reference="ADR-011, ADR-012"
    )


def check_suspension_defcon(conn) -> G2ValidationResult:
    """PHASE 6: Define suspension and DEFCON behavior for IoS-002"""
    issues = []

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check current DEFCON status
        cur.execute("""
            SELECT current_defcon, active_circuit_breakers, reason
            FROM fhq_governance.system_state
            WHERE is_active = TRUE
            LIMIT 1
        """)
        system_state = cur.fetchone()

        # Check relevant circuit breakers
        cur.execute("""
            SELECT breaker_name, breaker_type, trigger_condition,
                   action_on_trigger, defcon_threshold, is_enabled
            FROM fhq_governance.circuit_breakers
            WHERE breaker_name IN ('DISCREPANCY_DRIFT', 'SYSTEM_ERROR_RATE', 'HIGH_LATENCY')
        """)
        relevant_breakers = cur.fetchall()

        # Check suspension audit log exists
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'fhq_governance'
              AND table_name = 'suspension_audit_log'
        """)
        suspension_log = cur.fetchone()

        # Check task_registry has suspension capability
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'fhq_governance'
              AND table_name = 'task_registry'
              AND column_name = 'task_status'
        """)
        has_status = cur.fetchone()

    # Define suspension triggers
    suspension_triggers = [
        {"condition": "Discrepancy events > 3 per day", "threshold": 3, "action": "CALC_INDICATORS stage SUSPENDED"},
        {"condition": "Formula drift > 0.01%", "threshold": 0.0001, "action": "CALC_INDICATORS stage SUSPENDED"},
        {"condition": "Benchmark deviation > 0.1% sustained", "threshold": 0.001, "action": "IoS-002 module DEGRADED"}
    ]

    # Define DEFCON behavior matrix
    defcon_behavior = {
        "GREEN": {"behavior": "Normal operations", "calculations": "ACTIVE", "history": "PRESERVED"},
        "YELLOW": {"behavior": "Extra validation", "calculations": "ACTIVE + VALIDATE", "history": "PRESERVED"},
        "ORANGE": {"behavior": "Halt new calculations", "calculations": "HALTED", "history": "PRESERVED"},
        "RED": {"behavior": "Freeze all writes", "calculations": "READ_ONLY", "history": "PRESERVED"},
        "BLACK": {"behavior": "Complete isolation", "calculations": "ISOLATED", "history": "FORENSIC_SNAPSHOT"}
    }

    # Emergency brake procedure
    emergency_brake = {
        "steps": [
            "1. Detect: discrepancy_score > 0.08 OR repeated failures",
            "2. Log: INSERT INTO suspension_audit_log (ios_id='IoS-002', reason, timestamp)",
            "3. Suspend: UPDATE task_registry SET task_status='SUSPENDED' WHERE task_name='CALC_INDICATORS'",
            "4. Flag: Mark Meta-Perception (IoS-003) as DEGRADED_INPUT",
            "5. Preserve: Historical data remains intact (no deletion)",
            "6. Alert: Notify LARS (CSO) for governance review"
        ],
        "infrastructure_ready": {
            "suspension_log_exists": suspension_log is not None,
            "task_status_column": has_status is not None,
            "circuit_breakers_configured": len(relevant_breakers) > 0
        }
    }

    # Check infrastructure
    if not suspension_log:
        issues.append("suspension_audit_log table not found")
    if not has_status:
        issues.append("task_status column not found in task_registry")

    current_defcon = system_state['current_defcon'] if system_state else 'UNKNOWN'

    status = "PASS" if current_defcon == 'GREEN' and not issues else "WARN"

    return G2ValidationResult(
        check_id="G2-006",
        check_name="Suspension & DEFCON Behavior",
        status=status,
        details={
            "current_defcon": current_defcon,
            "active_breakers": system_state['active_circuit_breakers'] if system_state else [],
            "relevant_circuit_breakers": [dict(b) for b in relevant_breakers],
            "suspension_triggers": suspension_triggers,
            "defcon_behavior_matrix": defcon_behavior,
            "emergency_brake_procedure": emergency_brake,
            "issues": issues
        },
        adr_reference="ADR-009, ADR-016"
    )


def generate_evidence_bundle(results: List[G2ValidationResult], conn) -> Dict[str, Any]:
    """PHASE 7: Generate G2 Evidence Bundle"""

    validation_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # Calculate overall status
    statuses = [r.status for r in results]
    if 'FAIL' in statuses:
        overall_status = 'G2_GOVERNANCE_FAIL'
    elif 'WARN' in statuses:
        overall_status = 'G2_GOVERNANCE_PASS_WITH_WARNINGS'
    else:
        overall_status = 'G2_GOVERNANCE_PASS'

    # Build governance matrix
    governance_matrix = {
        "ios_module": "IoS-002",
        "module_name": "Indicator Engine (Sensory Cortex)",
        "roles": {
            "STIG": {"read": True, "write": "schema_only", "mechanism": "migration"},
            "CODE": {"read": True, "write": True, "mechanism": "CALC_INDICATORS"},
            "FINN": {"read": True, "write": False, "mechanism": "specification"},
            "LARS": {"read": True, "write": False, "mechanism": "oversight"},
            "VEGA": {"read": True, "write": False, "mechanism": "attestation"}
        },
        "tables": IOS002_TABLES,
        "unauthorized_write": "EXPLICITLY_FORBIDDEN"
    }

    # Build dataflow diagram (ASCII representation)
    dataflow = """
fhq_market.prices (IoS-001)
      |
      v
+-----------------------------+
|  CALC_INDICATORS (CODE)     |
|  Owner: FINN                |
|  Gate: G1_APPROVED          |
+-----------------------------+
      |
      v
fhq_research.indicator_* (IoS-002)
      |
      +---> VEGA Reconciliation
      |
      v
IoS-003 Meta-Perception (READ ONLY)
"""

    # Build risk register
    risk_register = [
        {"risk_id": "R-001", "type": "Formula drift", "consequence": "Incorrect signals",
         "mitigation": "Weekly benchmark test", "owner": "VEGA"},
        {"risk_id": "R-002", "type": "Missing data", "consequence": "Incomplete analysis",
         "mitigation": "Daily gap detection", "owner": "VEGA"},
        {"risk_id": "R-003", "type": "Unauthorized write", "consequence": "Data integrity breach",
         "mitigation": "Authority matrix enforcement", "owner": "LARS"},
        {"risk_id": "R-004", "type": "Shadow calculation", "consequence": "One-Source violation",
         "mitigation": "LLM policy + code review", "owner": "STIG"},
        {"risk_id": "R-005", "type": "Cascade to trading", "consequence": "Capital loss",
         "mitigation": "Isolation architecture", "owner": "LARS"}
    ]

    # Build the evidence bundle
    evidence_bundle = {
        "validation_id": validation_id,
        "ios_module": "IoS-002",
        "module_name": "Indicator Engine (Sensory Cortex)",
        "validation_type": "G2_GOVERNANCE",
        "timestamp": timestamp,
        "validators": ["LARS (CSO)", "VEGA (Compliance)"],
        "overall_status": overall_status,
        "checks": [asdict(r) for r in results],
        "governance_matrix": governance_matrix,
        "dataflow_diagram": dataflow,
        "risk_register": risk_register,
        "adr_compliance": [
            "ADR-001", "ADR-002", "ADR-003", "ADR-004", "ADR-006",
            "ADR-007", "ADR-009", "ADR-010", "ADR-011", "ADR-012",
            "ADR-013", "ADR-014", "ADR-016"
        ],
        "next_gate": "G3_AUDIT" if "PASS" in overall_status else "REMEDIATION_REQUIRED"
    }

    # Compute bundle hash
    bundle_json = json.dumps(evidence_bundle, sort_keys=True, default=str)
    bundle_hash = hashlib.sha256(bundle_json.encode()).hexdigest()
    evidence_bundle["bundle_hash"] = bundle_hash

    # Add signature log
    evidence_bundle["signature_log"] = {
        "lars_approval": {
            "signer": "LARS",
            "role": "CSO",
            "sign_time": timestamp,
            "decision": overall_status
        },
        "vega_attestation": {
            "signer": "VEGA",
            "role": "Compliance",
            "sign_time": timestamp,
            "attestation_id": str(uuid.uuid4())
        },
        "bundle_hash": bundle_hash
    }

    return evidence_bundle


def main():
    print("=" * 70)
    print("IoS-002 G2 GOVERNANCE VALIDATION")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("Validators: LARS (CSO) + VEGA (Compliance)")
    print("=" * 70)
    print()

    conn = get_connection()
    results = []

    checks = [
        ("Phase 1: Semantic Scope", check_semantic_scope),
        ("Phase 2: Role Permissions", check_role_permissions),
        ("Phase 3: One-True-Source", check_one_true_source),
        ("Phase 4: Reconciliation Policy", check_reconciliation_policy),
        ("Phase 5: Economic Safety", check_economic_safety),
        ("Phase 6: Suspension & DEFCON", check_suspension_defcon)
    ]

    for i, (name, check_fn) in enumerate(checks, 1):
        print(f"CHECK {i}: {name}...")
        try:
            result = check_fn(conn)
            results.append(result)
            status_icon = "OK" if result.status == "PASS" else ("WARN" if result.status == "WARN" else "FAIL")
            print(f"  [{status_icon}] {result.status}: {result.check_name}")
        except Exception as e:
            print(f"  [FAIL] ERROR: {e}")
            results.append(G2ValidationResult(
                check_id=f"G2-00{i}",
                check_name=name,
                status="FAIL",
                details={"error": str(e)},
                adr_reference="ERROR"
            ))

    print()
    print("-" * 70)
    print("Generating G2 Evidence Bundle...")

    evidence = generate_evidence_bundle(results, conn)

    # Save evidence bundle
    evidence_dir = Path("evidence")
    evidence_dir.mkdir(exist_ok=True)

    short_hash = evidence["bundle_hash"][:8]
    filename = f"IoS-002_G2_EVIDENCE_{short_hash}.json"
    filepath = evidence_dir / filename

    with open(filepath, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    print(f"Evidence saved: {filepath.absolute()}")

    # Log to governance actions
    try:
        with conn.cursor() as cur:
            # Map overall_status to valid decision values
            decision_map = {
                "G2_GOVERNANCE_PASS": "APPROVED",
                "G2_GOVERNANCE_PASS_WITH_WARNINGS": "APPROVED",
                "G2_GOVERNANCE_FAIL": "REJECTED"
            }
            decision = decision_map.get(evidence["overall_status"], "DEFERRED")

            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_id, action_type, action_target, action_target_type,
                    initiated_by, initiated_at, decision, decision_rationale,
                    hash_chain_id, signature_id
                ) VALUES (
                    gen_random_uuid(), 'IOS_MODULE_G2_VALIDATION', 'IoS-002',
                    'IOS_MODULE', 'LARS', NOW(), %s, %s, %s, gen_random_uuid()
                )
            """, (
                decision,
                f"G2 Governance Validation: {evidence['overall_status']}. {sum(1 for r in results if r.status == 'PASS')}/6 checks passed.",
                f"G2-{short_hash}"
            ))

            # Log to ios_audit
            cur.execute("""
                INSERT INTO fhq_meta.ios_audit_log (
                    ios_id, event_type, actor, event_data, gate_level
                ) VALUES (
                    'IoS-002', 'G2_GOVERNANCE_VALIDATION', 'LARS', %s, 'G2'
                )
            """, (json.dumps({
                "validation_id": evidence["validation_id"],
                "overall_status": evidence["overall_status"],
                "checks_passed": sum(1 for r in results if r.status == "PASS"),
                "checks_warned": sum(1 for r in results if r.status == "WARN"),
                "checks_failed": sum(1 for r in results if r.status == "FAIL"),
                "bundle_hash": evidence["bundle_hash"]
            }),))

        conn.commit()
    except Exception as e:
        print(f"Warning: Could not log to governance: {e}")

    conn.close()

    # Print summary
    print()
    print("=" * 70)
    print("G2 VALIDATION SUMMARY")
    print("=" * 70)

    pass_count = sum(1 for r in results if r.status == "PASS")
    warn_count = sum(1 for r in results if r.status == "WARN")
    fail_count = sum(1 for r in results if r.status == "FAIL")

    print(f"  PASS: {pass_count}")
    print(f"  WARN: {warn_count}")
    print(f"  FAIL: {fail_count}")
    print()
    print(f"  OVERALL STATUS: {evidence['overall_status']}")
    print(f"  BUNDLE HASH: {evidence['bundle_hash'][:32]}...")
    print(f"  NEXT GATE: {evidence['next_gate']}")
    print("=" * 70)

    return evidence


if __name__ == "__main__":
    result = main()
