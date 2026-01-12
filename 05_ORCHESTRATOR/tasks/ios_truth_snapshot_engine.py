#!/usr/bin/env python3
"""
IOS-TRUTH-LOOP v2 - Truth Snapshot Engine
==========================================
Authority: CEO-DIR-2026-039B
Classification: ACI-Bound Cognitive Loop

Purpose: Generate database-verified learning snapshots with full ACI Triangle binding.

ACI Bindings:
- EC-020 (SitC): Chain hash for every SQL execution
- EC-021 (InForage): Cost tracking for every LLM call
- EC-022 (IKEA): Hallucination firewall for LLM output

Mode: READ-ONLY against Postgres. SHADOW mode for ACI engines.
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal


def json_serializer(obj):
    """JSON serializer for non-standard types."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[IOS-TRUTH-LOOP] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Budget constraints (CEO-DIR-2026-039B Section 3)
BUDGET_PER_RUN_USD = 0.03
BUDGET_DAILY_USD = 0.50
BUDGET_MONTHLY_USD = 15.00
BUDGET_MINIMUM_REMAINING = 0.10

# ============================================================================
# CADENCE POLICY (CEO-DIR-2026-040)
# ============================================================================

# Cadence modes (in minutes)
CADENCE_BASELINE_MINUTES = 120  # 2 hours - DEFAULT (12 runs/day)
CADENCE_BURST_MINUTES = 60      # 1 hour - ESCALATION (AT_RISK triggers)
CADENCE_INCIDENT_MINUTES = 30   # 30 min - EXCEPTION ONLY (max 4 hours)

# Auto-revert rule
CONSECUTIVE_GREEN_FOR_REVERT = 2

# Incident mode max duration (4 hours = 8 runs at 30min)
INCIDENT_MODE_MAX_RUNS = 8

# Cadence modes
class CadenceMode:
    BASELINE = "BASELINE"           # 2-hour default
    HOURLY_ESCALATION = "HOURLY_ESCALATION"  # 1-hour burst
    INCIDENT = "INCIDENT"           # 30-min exception

# Thresholds (CEO-DIR-2026-039B Section 5.3)
THRESHOLDS = {
    'forecasts_last_24h': {'healthy': 100, 'at_risk': 10, 'blocked': 0},
    'outcomes_0h_1h_last_24h': {'healthy': 50, 'at_risk': 10, 'blocked': 0},
    'type_x_share_pct': {'healthy': 30, 'at_risk': 50, 'blocked': 100},
    'exposure_total': {'healthy': 0, 'at_risk': 0, 'blocked': 1},  # Any exposure = BLOCKED
}

# Paths
BASE_DIR = Path(r"C:\fhq-market-system\vision-ios")
SQL_DIR = BASE_DIR / "03_FUNCTIONS" / "sql"
OUTPUT_DIR = BASE_DIR / "12_DAILY_REPORTS" / "TRUTH_SNAPSHOT"
EVIDENCE_DIR = BASE_DIR / "03_FUNCTIONS" / "evidence"
COST_LEDGER_PATH = EVIDENCE_DIR / "INFORAGE_COST_LEDGER.json"
ROLLING_7D_PATH = OUTPUT_DIR / "ROLLING_7D.json"
CADENCE_STATE_PATH = OUTPUT_DIR / "CADENCE_STATE.json"

# Database connection
DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', '54322')),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres'),
}


# ============================================================================
# EC-020 SitC: CHAIN HASH GENERATION
# ============================================================================

def generate_sitc_chain_hash(sql_statements: list, timestamp: str, row_counts: list) -> str:
    """
    Generate deterministic chain hash for EC-020 SitC compliance.

    Hash = SHA256(concatenated_sql + timestamp + row_counts)
    """
    content = ''.join(sql_statements) + timestamp + ''.join(str(c) for c in row_counts)
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


# ============================================================================
# EC-021 InForage: COST TRACKING
# ============================================================================

def load_daily_cost() -> float:
    """Load today's accumulated LLM cost from ledger."""
    if not COST_LEDGER_PATH.exists():
        return 0.0

    try:
        with open(COST_LEDGER_PATH, 'r') as f:
            ledger = json.load(f)

        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        return sum(
            entry.get('cost_usd', 0)
            for entry in ledger.get('entries', [])
            if entry.get('date', '').startswith(today)
        )
    except Exception as e:
        logger.warning(f"Could not load cost ledger: {e}")
        return 0.0


def record_llm_cost(model: str, tokens_in: int, tokens_out: int, cost_usd: float, reason: str):
    """Record LLM call cost for EC-021 compliance."""
    entry = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'model': model,
        'tokens_in': tokens_in,
        'tokens_out': tokens_out,
        'cost_usd': cost_usd,
        'reason': reason,
        'budget_pressure_pct': (load_daily_cost() + cost_usd) / BUDGET_DAILY_USD * 100
    }

    # Load or create ledger
    if COST_LEDGER_PATH.exists():
        with open(COST_LEDGER_PATH, 'r') as f:
            ledger = json.load(f)
    else:
        ledger = {'entries': [], 'created_at': datetime.now(timezone.utc).isoformat()}

    ledger['entries'].append(entry)
    ledger['last_updated'] = datetime.now(timezone.utc).isoformat()

    COST_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COST_LEDGER_PATH, 'w') as f:
        json.dump(ledger, f, indent=2)

    return entry


# ============================================================================
# CADENCE MANAGEMENT (CEO-DIR-2026-040)
# ============================================================================

def load_cadence_state() -> Dict[str, Any]:
    """Load current cadence state from file."""
    if not CADENCE_STATE_PATH.exists():
        return {
            'mode': CadenceMode.BASELINE,
            'interval_minutes': CADENCE_BASELINE_MINUTES,
            'consecutive_green': 0,
            'incident_runs': 0,
            'incident_id': None,
            'escalation_reason': None,
            'last_updated': None,
        }

    try:
        with open(CADENCE_STATE_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load cadence state: {e}")
        return {
            'mode': CadenceMode.BASELINE,
            'interval_minutes': CADENCE_BASELINE_MINUTES,
            'consecutive_green': 0,
            'incident_runs': 0,
            'incident_id': None,
            'escalation_reason': None,
            'last_updated': None,
        }


def save_cadence_state(state: Dict[str, Any]):
    """Save cadence state to file."""
    state['last_updated'] = datetime.now(timezone.utc).isoformat()
    CADENCE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CADENCE_STATE_PATH, 'w') as f:
        json.dump(state, f, indent=2)


def detect_escalation_triggers(snapshot: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Detect if escalation from BASELINE to HOURLY_ESCALATION is warranted.

    CEO-DIR-2026-040 Section 3 triggers:
    - Snapshot status = AT_RISK
    - forecasts_last_24h below healthy threshold
    - outcomes_0h_1h unexpectedly drops to zero
    - type_x_share > 50% not explained by HORIZON_NOT_MATURED

    Returns: (should_escalate, trigger_reason)
    """
    status = snapshot.get('status', 'OK')

    # Trigger 1: AT_RISK status
    if status == 'AT_RISK':
        violations = snapshot.get('threshold_violations', [])
        # Check if AT_RISK is from expected causes (new system, horizon maturing)
        expected_at_risk = all(
            v.get('field') in ['outcomes_0h_1h_last_24h', 'type_x_share_pct']
            for v in violations
        )
        if not expected_at_risk:
            return True, f"AT_RISK_UNEXPECTED: {[v.get('field') for v in violations]}"

    # Trigger 2: BLOCKED status (always escalate)
    if status == 'BLOCKED':
        return True, f"BLOCKED_STATUS"

    # Trigger 3: forecasts_last_24h below healthy
    forecasts = snapshot.get('learning_volume', {}).get('forecasts_last_24h', 0) or 0
    if forecasts < THRESHOLDS['forecasts_last_24h']['at_risk']:
        return True, f"FORECASTS_CRITICAL: {forecasts}"

    # Trigger 4: type_x > 50% with non-HORIZON_NOT_MATURED explanation
    type_x_pct = snapshot.get('suppression', {}).get('type_x_share_pct', 0) or 0
    if type_x_pct > 50:
        # Check forensic breakdown - if most are ATTRIBUTION_LOGIC_GAP, escalate
        # For now, we allow high type_x if system is new (expected)
        unresolved = snapshot.get('suppression', {}).get('unresolved_count', 0) or 0
        total_supp = snapshot.get('suppression', {}).get('suppressions_last_24h', 0) or 0
        if total_supp > 0 and unresolved < total_supp * 0.7:
            # Less than 70% unresolved means attribution gap, not horizon
            return True, f"TYPE_X_ATTRIBUTION_GAP: {type_x_pct}%"

    return False, None


def evaluate_cadence_transition(snapshot: Dict[str, Any], current_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate whether cadence should transition based on snapshot results.

    Rules (CEO-DIR-2026-040):
    - Escalate to HOURLY if triggers detected
    - Revert to BASELINE after 2 consecutive GREEN (OK status)
    - Incident mode auto-reverts after max runs

    Returns: Updated cadence state
    """
    new_state = current_state.copy()
    status = snapshot.get('status', 'OK')
    current_mode = current_state.get('mode', CadenceMode.BASELINE)

    # Handle INCIDENT mode (exception path)
    if current_mode == CadenceMode.INCIDENT:
        new_state['incident_runs'] = current_state.get('incident_runs', 0) + 1
        if new_state['incident_runs'] >= INCIDENT_MODE_MAX_RUNS:
            logger.info("INCIDENT mode max runs reached - reverting to BASELINE")
            new_state['mode'] = CadenceMode.BASELINE
            new_state['interval_minutes'] = CADENCE_BASELINE_MINUTES
            new_state['incident_runs'] = 0
            new_state['incident_id'] = None
            new_state['escalation_reason'] = None
        return new_state

    # Track consecutive GREEN status for revert logic
    if status == 'OK':
        new_state['consecutive_green'] = current_state.get('consecutive_green', 0) + 1
    else:
        new_state['consecutive_green'] = 0

    # Check for auto-revert (HOURLY -> BASELINE)
    if current_mode == CadenceMode.HOURLY_ESCALATION:
        if new_state['consecutive_green'] >= CONSECUTIVE_GREEN_FOR_REVERT:
            logger.info(f"2 consecutive GREEN - reverting to BASELINE cadence")
            new_state['mode'] = CadenceMode.BASELINE
            new_state['interval_minutes'] = CADENCE_BASELINE_MINUTES
            new_state['escalation_reason'] = None
            new_state['consecutive_green'] = 0
            return new_state

    # Check for escalation (BASELINE -> HOURLY)
    if current_mode == CadenceMode.BASELINE:
        should_escalate, trigger = detect_escalation_triggers(snapshot)
        if should_escalate:
            logger.warning(f"Escalation triggered: {trigger}")
            new_state['mode'] = CadenceMode.HOURLY_ESCALATION
            new_state['interval_minutes'] = CADENCE_BURST_MINUTES
            new_state['escalation_reason'] = trigger
            new_state['consecutive_green'] = 0

    return new_state


def enter_incident_mode(incident_id: str, reason: str) -> Dict[str, Any]:
    """
    Enter INCIDENT mode (30-minute cadence) - EXCEPTION ONLY.

    Requires explicit incident identifier.
    Max duration: 4 hours (auto-reverts).

    This function should only be called during active incident response.
    """
    logger.warning(f"ENTERING INCIDENT MODE: {incident_id} - {reason}")
    state = {
        'mode': CadenceMode.INCIDENT,
        'interval_minutes': CADENCE_INCIDENT_MINUTES,
        'consecutive_green': 0,
        'incident_runs': 0,
        'incident_id': incident_id,
        'escalation_reason': reason,
    }
    save_cadence_state(state)
    return state


# ============================================================================
# EC-022 IKEA: HALLUCINATION FIREWALL
# ============================================================================

# Known DB field names for validation
KNOWN_DB_FIELDS = {
    'forecasts_last_24h', 'forecasts_last_6h', 'outcomes_resolved', 'brier_score',
    'hit_rate', 'type_x_share', 'suppressions', 'wisdom_count', 'regret_count',
    'exposure_total', 'learning_velocity_index', 'monotonicity_status',
    'sitc_score', 'ikea_score', 'inforage_cost', 'confidence_band'
}

ACTION_WORDS = {
    'implement', 'change', 'modify', 'update', 'fix', 'tune', 'adjust',
    'deploy', 'migrate', 'refactor', 'optimize', 'improve', 'add', 'remove'
}


def validate_ikea(llm_output: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate LLM output against EC-022 IKEA rules.

    Checks:
    1. db_field_references >= 3
    2. tomorrow_focus contains measurement only (no action verbs)
    3. top_1_risk references a valid DB field

    Returns: (is_valid, failure_reason)
    """
    summary = llm_output.get('10_line_summary', '')
    tomorrow_focus = llm_output.get('one_focus_for_tomorrow', '')
    top_risk = llm_output.get('top_1_risk', '')

    # Check 1: DB field references >= 3
    field_count = sum(1 for field in KNOWN_DB_FIELDS if field.lower() in summary.lower())
    if field_count < 3:
        return False, f"db_field_references={field_count} (requires >=3)"

    # Check 2: No action words in tomorrow_focus
    for word in ACTION_WORDS:
        if word.lower() in tomorrow_focus.lower():
            return False, f"tomorrow_focus contains action word: '{word}'"

    # Check 3: top_1_risk references DB field
    risk_has_field = any(field.lower() in top_risk.lower() for field in KNOWN_DB_FIELDS)
    if not risk_has_field:
        return False, "top_1_risk does not reference a DB field"

    return True, None


# ============================================================================
# SQL BUNDLE EXECUTION
# ============================================================================

def execute_sql_bundle(conn, sql_file: Path) -> Tuple[Dict[str, Any], list, list]:
    """
    Execute SQL bundle and return results with chain hash components.

    Returns: (results_dict, sql_statements, row_counts)
    """
    if not sql_file.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_file}")

    with open(sql_file, 'r') as f:
        sql_content = f.read()

    # Parse SQL statements - split by semicolon but handle multi-line statements
    raw_statements = sql_content.split(';')
    statements = []

    for stmt in raw_statements:
        # Strip whitespace and remove pure comment lines from start
        lines = stmt.strip().split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip pure comment lines at start, but keep inline comments
            if cleaned_lines or not stripped.startswith('--'):
                cleaned_lines.append(line)

        cleaned_stmt = '\n'.join(cleaned_lines).strip()
        # Only include if there's actual SQL (not just comments)
        if cleaned_stmt and not all(line.strip().startswith('--') or not line.strip() for line in cleaned_stmt.split('\n')):
            statements.append(cleaned_stmt)

    results = {}
    row_counts = []

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for i, stmt in enumerate(statements):
            try:
                cur.execute(stmt)
                rows = cur.fetchall()
                results[f"query_{i}"] = [dict(r) for r in rows]
                row_counts.append(len(rows))
                logger.debug(f"Query {i}: {len(rows)} rows")
            except Exception as e:
                logger.warning(f"Query {i} failed: {e}")
                results[f"query_{i}"] = {'error': str(e), 'status': 'UNKNOWN'}
                row_counts.append(-1)

    logger.info(f"Executed {len(statements)} queries from {sql_file.name}")
    return results, statements, row_counts


# ============================================================================
# THRESHOLD EVALUATION
# ============================================================================

def evaluate_thresholds(metrics: Dict[str, Any]) -> Tuple[str, list]:
    """
    Evaluate metrics against thresholds.

    Returns: (overall_status, list of violations)
    """
    violations = []
    status = 'OK'

    # Check exposure (immediate BLOCKED if > 0)
    exposure = metrics.get('exposure_total', 0) or 0
    if exposure > 0:
        violations.append({
            'field': 'exposure_total',
            'value': exposure,
            'threshold': 0,
            'severity': 'BLOCKED'
        })
        return 'BLOCKED', violations

    # Check other thresholds
    forecasts = metrics.get('forecasts_last_24h', 0) or 0
    if forecasts < THRESHOLDS['forecasts_last_24h']['blocked']:
        violations.append({'field': 'forecasts_last_24h', 'value': forecasts, 'severity': 'BLOCKED'})
        status = 'BLOCKED'
    elif forecasts < THRESHOLDS['forecasts_last_24h']['at_risk']:
        violations.append({'field': 'forecasts_last_24h', 'value': forecasts, 'severity': 'AT_RISK'})
        if status == 'OK':
            status = 'AT_RISK'

    outcomes = metrics.get('outcomes_0h_1h_last_24h', 0) or 0
    if outcomes < THRESHOLDS['outcomes_0h_1h_last_24h']['blocked']:
        violations.append({'field': 'outcomes_0h_1h_last_24h', 'value': outcomes, 'severity': 'BLOCKED'})
        status = 'BLOCKED'
    elif outcomes < THRESHOLDS['outcomes_0h_1h_last_24h']['at_risk']:
        violations.append({'field': 'outcomes_0h_1h_last_24h', 'value': outcomes, 'severity': 'AT_RISK'})
        if status == 'OK':
            status = 'AT_RISK'

    type_x = metrics.get('type_x_share_pct', 0) or 0
    if type_x > THRESHOLDS['type_x_share_pct']['at_risk']:
        violations.append({'field': 'type_x_share_pct', 'value': type_x, 'severity': 'AT_RISK'})
        if status == 'OK':
            status = 'AT_RISK'

    return status, violations


# ============================================================================
# MAIN SNAPSHOT GENERATION
# ============================================================================

def generate_snapshot() -> Dict[str, Any]:
    """
    Generate complete Truth Snapshot with ACI bindings.
    """
    timestamp = datetime.now(timezone.utc)
    timestamp_str = timestamp.isoformat()

    snapshot = {
        'snapshot_id': f"TRUTH_{timestamp.strftime('%Y%m%d_%H%M')}",
        'generated_at': timestamp_str,
        'directive': 'CEO-DIR-2026-039B',
        'mode': 'OBSERVATION',
        'aci_mode': 'SHADOW',
    }

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Database connected")

        # Execute main bundle
        bundle_results, bundle_sql, bundle_counts = execute_sql_bundle(
            conn, SQL_DIR / "ios_truth_snapshot_bundle.sql"
        )

        # Execute delta bundle
        delta_results, delta_sql, delta_counts = execute_sql_bundle(
            conn, SQL_DIR / "ios_truth_snapshot_delta.sql"
        )

        # Generate SitC chain hash (EC-020)
        all_sql = bundle_sql + delta_sql
        all_counts = bundle_counts + delta_counts
        sitc_chain_hash = generate_sitc_chain_hash(all_sql, timestamp_str, all_counts)

        # Extract key metrics
        metrics = extract_metrics(bundle_results, delta_results)

        # Evaluate thresholds
        status, violations = evaluate_thresholds(metrics)

        # Single instance proof
        try:
            single_results, _, _ = execute_sql_bundle(
                conn, SQL_DIR / "ios_truth_snapshot_single_instance_proof.sql"
            )
            single_instance_proof = 'VERIFIED' if single_results else 'UNKNOWN'
        except Exception as e:
            single_instance_proof = 'UNKNOWN'
            logger.warning(f"Single instance proof failed: {e}")

        conn.close()

        # Build snapshot
        snapshot.update({
            # Section A: Learning Volume
            'learning_volume': metrics.get('learning_volume', {}),

            # Section B: Calibration Direction
            'calibration': metrics.get('calibration', {}),

            # Section C: Suppression Truth
            'suppression': metrics.get('suppression', {}),

            # Section D: Integrity Invariants
            'integrity': {
                'exposure_total': metrics.get('exposure_total', 0),
                'gate_violations_last_24h': metrics.get('gate_violations_last_24h', 0),
                'policy_changes_last_24h': metrics.get('policy_changes_last_24h', 0),
                'ios003b_non_interference': metrics.get('ios003b_non_interference', 'UNKNOWN'),
                'single_instance_proof': single_instance_proof,
            },

            # Section E: Day-over-Day Delta
            'delta': metrics.get('delta', {}),

            # Section F: Learning Velocity Index
            'learning_velocity': metrics.get('learning_velocity', {}),

            # ACI Bindings (Sections 11-13)
            'aci_bindings': {
                'ec_020_sitc': {
                    'chain_hash': sitc_chain_hash,
                    'status': 'OK' if sitc_chain_hash else 'CHAIN_BROKEN',
                    'sql_statements_executed': len(all_sql),
                    'total_rows_returned': sum(c for c in all_counts if c >= 0),
                },
                'ec_021_inforage': {
                    'daily_spent_usd': load_daily_cost(),
                    'daily_cap_usd': BUDGET_DAILY_USD,
                    'budget_pressure_pct': (load_daily_cost() / BUDGET_DAILY_USD) * 100,
                    'llm_calls_this_snapshot': 0,  # Will be updated if LLM called
                },
                'ec_022_ikea': {
                    'llm_validation': 'NOT_CALLED',  # Will be updated if LLM called
                    'fabrication_flags': 0,
                },
            },

            # Status & Thresholds
            'status': status,
            'threshold_violations': violations,

            # LLM interpretation placeholder
            'llm_interpretation': {
                'status': 'LLM_NOT_CALLED',
                'reason': 'Initial snapshot - LLM optional',
            },

            # Cadence state placeholder (CEO-DIR-2026-040)
            # Will be populated by main() after evaluation
            'cadence': None,
        })

        logger.info(f"Snapshot generated: {snapshot['snapshot_id']}, status={status}")

    except Exception as e:
        logger.error(f"Snapshot generation failed: {e}")
        snapshot.update({
            'status': 'ERROR',
            'error': str(e),
            'aci_bindings': {
                'ec_020_sitc': {'status': 'CHAIN_BROKEN', 'error': str(e)},
                'ec_021_inforage': {'status': 'UNKNOWN'},
                'ec_022_ikea': {'status': 'UNKNOWN'},
            }
        })

    return snapshot


def extract_metrics(bundle_results: Dict, delta_results: Dict) -> Dict[str, Any]:
    """Extract and structure metrics from SQL results."""
    metrics = {}

    # Parse bundle results (queries are numbered)
    try:
        # A1: Forecasts
        if 'query_0' in bundle_results and bundle_results['query_0']:
            q = bundle_results['query_0'][0]
            metrics['learning_volume'] = {
                'forecasts_last_24h': q.get('forecasts_last_24h', 0),
                'forecasts_last_6h': q.get('forecasts_last_6h', 0),
            }
            metrics['forecasts_last_24h'] = q.get('forecasts_last_24h', 0)

        # A2: Outcomes by horizon
        if 'query_1' in bundle_results:
            metrics['learning_volume'] = metrics.get('learning_volume', {})
            metrics['learning_volume']['outcomes_by_horizon'] = bundle_results['query_1']

        # B1-B3: Calibration
        metrics['calibration'] = {
            'brier_by_horizon': bundle_results.get('query_4', []),
            'hit_rate_by_band': bundle_results.get('query_5', []),
            'monotonicity': bundle_results.get('query_6', [{}])[0] if bundle_results.get('query_6') else {},
        }

        # C1-C3: Suppression
        if 'query_7' in bundle_results and bundle_results['query_7']:
            q = bundle_results['query_7'][0]
            metrics['suppression'] = {
                'suppressions_last_24h': q.get('suppressions_last_24h', 0),
                'wisdom_count': q.get('wisdom_count_last_24h', 0),
                'regret_count': q.get('regret_count_last_24h', 0),
                'unresolved_count': q.get('unresolved_count_last_24h', 0),
            }

        if 'query_8' in bundle_results and bundle_results['query_8']:
            q = bundle_results['query_8'][0]
            metrics['suppression'] = metrics.get('suppression', {})
            metrics['suppression']['type_x_share_pct'] = q.get('type_x_share_pct', 0)
            metrics['type_x_share_pct'] = q.get('type_x_share_pct', 0)

        # D1: Exposure
        if 'query_10' in bundle_results and bundle_results['query_10']:
            q = bundle_results['query_10'][0]
            metrics['exposure_total'] = q.get('exposure_total', 0)

        # D2-D3: Violations
        if 'query_11' in bundle_results and bundle_results['query_11']:
            metrics['gate_violations_last_24h'] = bundle_results['query_11'][0].get('gate_violations_last_24h', 0)
        if 'query_12' in bundle_results and bundle_results['query_12']:
            metrics['policy_changes_last_24h'] = bundle_results['query_12'][0].get('policy_changes_last_24h', 0)

        # D4: IOS-003-B non-interference
        if 'query_13' in bundle_results and bundle_results['query_13']:
            metrics['ios003b_non_interference'] = bundle_results['query_13'][0].get('ios003b_non_interference', False)

    except Exception as e:
        logger.warning(f"Error extracting bundle metrics: {e}")

    # Parse delta results
    try:
        # LVI from last query
        if delta_results:
            last_key = max(k for k in delta_results.keys() if k.startswith('query_'))
            if delta_results[last_key]:
                lvi_data = delta_results[last_key][0]
                metrics['learning_velocity'] = {
                    'index': lvi_data.get('learning_velocity_index'),
                    'interpretation': lvi_data.get('lvi_interpretation', 'UNKNOWN'),
                    'outcomes_ratio': lvi_data.get('outcomes_ratio'),
                    'type_x_ratio': lvi_data.get('type_x_ratio'),
                    'brier_ratio': lvi_data.get('brier_ratio'),
                }

        # Deltas
        metrics['delta'] = {
            'forecasts': delta_results.get('query_0', [{}])[0] if delta_results.get('query_0') else {},
            'outcomes': delta_results.get('query_1', [{}])[0] if delta_results.get('query_1') else {},
            'brier': delta_results.get('query_2', [{}])[0] if delta_results.get('query_2') else {},
            'type_x': delta_results.get('query_3', [{}])[0] if delta_results.get('query_3') else {},
        }

        # Extract outcomes_0h_1h for threshold check
        if 'query_1' in delta_results and delta_results['query_1']:
            metrics['outcomes_0h_1h_last_24h'] = delta_results['query_1'][0].get('outcomes_0h_1h_last_24h', 0)

    except Exception as e:
        logger.warning(f"Error extracting delta metrics: {e}")

    return metrics


def save_snapshot(snapshot: Dict[str, Any]):
    """Save snapshot to designated paths."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Main snapshot file
    filename = f"TRUTH_SNAPSHOT_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    filepath = OUTPUT_DIR / filename

    with open(filepath, 'w') as f:
        json.dump(snapshot, f, indent=2, default=json_serializer)

    logger.info(f"Snapshot saved: {filepath}")

    # Update LATEST.json
    latest_path = OUTPUT_DIR / "LATEST.json"
    with open(latest_path, 'w') as f:
        json.dump(snapshot, f, indent=2, default=json_serializer)

    # Append to rolling 7D
    append_to_rolling_7d(snapshot)

    return filepath


def append_to_rolling_7d(snapshot: Dict[str, Any]):
    """Append snapshot summary to rolling 7-day file."""
    summary = {
        'snapshot_id': snapshot.get('snapshot_id'),
        'generated_at': snapshot.get('generated_at'),
        'status': snapshot.get('status'),
        'lvi': snapshot.get('learning_velocity', {}).get('index'),
        'lvi_interpretation': snapshot.get('learning_velocity', {}).get('interpretation'),
        'forecasts_24h': snapshot.get('learning_volume', {}).get('forecasts_last_24h'),
        'type_x_pct': snapshot.get('suppression', {}).get('type_x_share_pct'),
        'sitc_status': snapshot.get('aci_bindings', {}).get('ec_020_sitc', {}).get('status'),
        'ikea_status': snapshot.get('aci_bindings', {}).get('ec_022_ikea', {}).get('llm_validation'),
        # CEO-DIR-2026-040: Cadence tracking
        'cadence_mode': snapshot.get('cadence', {}).get('mode') if snapshot.get('cadence') else None,
        'cadence_transition': snapshot.get('cadence', {}).get('transition') if snapshot.get('cadence') else None,
    }

    # Load existing or create new
    if ROLLING_7D_PATH.exists():
        with open(ROLLING_7D_PATH, 'r') as f:
            rolling = json.load(f)
    else:
        rolling = {'entries': [], 'created_at': datetime.now(timezone.utc).isoformat()}

    rolling['entries'].append(summary)
    rolling['last_updated'] = datetime.now(timezone.utc).isoformat()

    # Keep only last 7 days (assuming 12 snapshots/day = 84 entries)
    rolling['entries'] = rolling['entries'][-168:]  # 7 days * 24 hours

    with open(ROLLING_7D_PATH, 'w') as f:
        json.dump(rolling, f, indent=2, default=json_serializer)

    logger.info(f"Rolling 7D updated: {len(rolling['entries'])} entries")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point for IOS-TRUTH-LOOP."""
    logger.info("=" * 60)
    logger.info("IOS-TRUTH-LOOP v2 - ACI-BOUND SNAPSHOT ENGINE")
    logger.info("Authority: CEO-DIR-2026-039B, CEO-DIR-2026-040")
    logger.info("Mode: OBSERVATION | ACI: SHADOW")
    logger.info("=" * 60)

    # Load current cadence state (CEO-DIR-2026-040)
    cadence_state = load_cadence_state()
    logger.info(f"Cadence: {cadence_state.get('mode')} ({cadence_state.get('interval_minutes')}min)")

    # Generate snapshot
    snapshot = generate_snapshot()

    # Evaluate cadence transition based on snapshot results
    new_cadence_state = evaluate_cadence_transition(snapshot, cadence_state)

    # Add cadence to snapshot metadata
    snapshot['cadence'] = {
        'mode': new_cadence_state.get('mode'),
        'interval_minutes': new_cadence_state.get('interval_minutes'),
        'escalation_reason': new_cadence_state.get('escalation_reason'),
        'consecutive_green': new_cadence_state.get('consecutive_green'),
        'incident_id': new_cadence_state.get('incident_id'),
        'transition': None,
    }

    # Log transition if mode changed
    if new_cadence_state.get('mode') != cadence_state.get('mode'):
        transition = f"{cadence_state.get('mode')} -> {new_cadence_state.get('mode')}"
        snapshot['cadence']['transition'] = transition
        logger.info(f"CADENCE TRANSITION: {transition}")
        if new_cadence_state.get('escalation_reason'):
            logger.info(f"  Reason: {new_cadence_state.get('escalation_reason')}")

    # Save updated cadence state
    save_cadence_state(new_cadence_state)

    # Save snapshot
    filepath = save_snapshot(snapshot)

    # Summary
    logger.info("-" * 60)
    logger.info(f"Snapshot ID: {snapshot.get('snapshot_id')}")
    logger.info(f"Status: {snapshot.get('status')}")
    logger.info(f"Cadence: {new_cadence_state.get('mode')} ({new_cadence_state.get('interval_minutes')}min)")
    logger.info(f"SitC Chain Hash: {snapshot.get('aci_bindings', {}).get('ec_020_sitc', {}).get('chain_hash', 'N/A')[:16]}...")
    logger.info(f"LVI: {snapshot.get('learning_velocity', {}).get('index')} ({snapshot.get('learning_velocity', {}).get('interpretation')})")
    logger.info(f"Output: {filepath}")
    logger.info("=" * 60)

    return snapshot


if __name__ == '__main__':
    main()
