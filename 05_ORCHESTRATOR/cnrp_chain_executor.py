#!/usr/bin/env python3
"""
CNRP-001 CHAIN EXECUTOR
=======================
CEO Directive: CEO-DIR-2026-009-B
Classification: STRATEGIC-CONSTITUTIONAL (Class A+)

Purpose:
    Orchestrator-native execution of CNRP causal chain.
    Enforces: R1 → R2 → R3 → R4 with gate authorization.

Design Principle (CEO Position):
    "Clocks trigger. Brainstems decide."
    Windows Scheduler monitors. Orchestrator executes.

ADR-017 Compliance:
    All autonomous cognition executed through orchestrator
    to preserve intent, lineage, and auditability.

Author: STIG (CTO)
Date: 2026-01-07
"""

import os
import sys
import json
import subprocess
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("cnrp_chain_executor")

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": os.getenv("PGPORT", "54322"),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres")
}

FUNCTIONS_DIR = Path(__file__).parent.parent / "03_FUNCTIONS"

# Causal Chain Definition (CEO-DIR-2026-009-B)
CNRP_CHAIN = [
    {
        "phase": "R1",
        "task_id": "CNRP-R1-CEIO",
        "daemon": "ceio_evidence_refresh_daemon.py",
        "gate": "G2",
        "authority": "CEIO",
        "depends_on": None,
        "delay_after_previous": 0,
        "max_retries": 2
    },
    {
        "phase": "R2",
        "task_id": "CNRP-R2-CRIO",
        "daemon": "crio_alpha_graph_rebuild.py",
        "gate": "G3",
        "authority": "CRIO",
        "depends_on": "R1",
        "delay_after_previous": 5,  # minutes
        "max_retries": 1
    },
    {
        "phase": "R3",
        "task_id": "CNRP-R3-CDMO",
        "daemon": "cdmo_data_hygiene_attestation.py",
        "gate": "G3",
        "authority": "CDMO",
        "depends_on": "R2",
        "delay_after_previous": 2,
        "max_retries": 1
    },
    {
        "phase": "R4",
        "task_id": "CNRP-R4-VEGA",
        "daemon": "vega_epistemic_integrity_monitor.py",
        "gate": "G1",
        "authority": "VEGA",
        "depends_on": "R3",
        "delay_after_previous": 1,
        "max_retries": 0  # No retries for integrity monitor
    }
]

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Establish database connection"""
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# GATE AUTHORIZATION
# =============================================================================

def check_gate_authorization(conn, gate: str, authority: str) -> Tuple[bool, str]:
    """Verify gate authorization for execution"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check DEFCON level
        cur.execute("""
            SELECT current_level, allows_autonomous_execution
            FROM fhq_governance.defcon_status
            ORDER BY changed_at DESC
            LIMIT 1
        """)
        defcon = cur.fetchone()

        if defcon and not defcon.get('allows_autonomous_execution', True):
            return False, f"DEFCON {defcon['current_level']} blocks autonomous execution"

        # Gate hierarchy: G1 > G2 > G3 > G4
        gate_level = int(gate[1])

        # G1 (VEGA) can always execute
        # G2 requires no active G1 block
        # G3 requires no active G1/G2 block
        if gate_level >= 2:
            cur.execute("""
                SELECT COUNT(*) as blocks
                FROM fhq_governance.governance_actions_log
                WHERE action_type = 'EXECUTION_BLOCK'
                  AND decision = 'ACTIVE'
                  AND metadata->>'gate_level' < %s
                  AND created_at > NOW() - INTERVAL '24 hours'
            """, [str(gate_level)])
            if cur.fetchone()['blocks'] > 0:
                return False, f"Higher gate block active for {gate}"

    return True, "Authorized"


def check_chain_preconditions(conn, phase_config: Dict) -> Tuple[bool, str]:
    """Check preconditions for phase execution"""
    depends_on = phase_config.get('depends_on')

    if depends_on:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check that dependency completed successfully
            cur.execute("""
                SELECT status, completed_at
                FROM fhq_governance.cnrp_execution_log
                WHERE phase = %s
                ORDER BY completed_at DESC
                LIMIT 1
            """, [depends_on])
            result = cur.fetchone()

            if not result:
                return False, f"Dependency {depends_on} never executed"

            if result['status'] != 'SUCCESS':
                return False, f"Dependency {depends_on} last status: {result['status']}"

            # Check freshness of dependency
            age = datetime.now(timezone.utc) - result['completed_at'].replace(tzinfo=timezone.utc)
            max_age_minutes = 30  # Dependency must be within 30 minutes
            if age.total_seconds() > max_age_minutes * 60:
                return False, f"Dependency {depends_on} too old: {age.total_seconds()/60:.1f}m ago"

    return True, "Preconditions met"

# =============================================================================
# DAEMON EXECUTION
# =============================================================================

def execute_daemon(daemon_path: Path, phase: str) -> Tuple[bool, Dict[str, Any]]:
    """Execute a CNRP daemon and capture result"""
    logger.info(f"Executing {phase}: {daemon_path.name}")

    try:
        result = subprocess.run(
            [sys.executable, str(daemon_path)],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=str(daemon_path.parent)
        )

        # Parse JSON output
        output = result.stdout.strip()
        if output:
            try:
                daemon_result = json.loads(output)
            except json.JSONDecodeError:
                daemon_result = {"raw_output": output}
        else:
            daemon_result = {}

        daemon_result['exit_code'] = result.returncode
        daemon_result['stderr'] = result.stderr if result.stderr else None

        success = result.returncode == 0
        return success, daemon_result

    except subprocess.TimeoutExpired:
        return False, {"error": "Execution timeout (300s)"}
    except Exception as e:
        return False, {"error": str(e)}


def log_chain_execution(conn, cycle_id: str, phase: str, status: str,
                        result: Dict, authority: str) -> str:
    """Log chain execution to governance"""
    evidence_hash = hashlib.sha256(
        json.dumps(result, default=str, sort_keys=True).encode()
    ).hexdigest()

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_type,
                action_target,
                action_target_type,
                initiated_by,
                decision,
                decision_rationale,
                metadata
            ) VALUES (
                'CNRP_CHAIN_EXECUTION',
                %s,
                'DAEMON_EXECUTION',
                %s,
                %s,
                'CEO-DIR-2026-009-B: Orchestrator-native CNRP execution',
                %s
            )
            RETURNING action_id
        """, (
            f"CNRP-{phase}",
            authority,
            status,
            json.dumps({
                "cycle_id": cycle_id,
                "phase": phase,
                "evidence_hash": evidence_hash,
                "result_summary": {
                    k: v for k, v in result.items()
                    if k in ['status', 'total_nodes_refreshed', 'relationships_rebuilt',
                             'attestation_id', 'violations', 'error']
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, default=str)
        ))
        return str(cur.fetchone()[0])

# =============================================================================
# CHAIN EXECUTOR
# =============================================================================

def execute_cnrp_chain(start_phase: str = "R1", stop_phase: str = "R4") -> Dict[str, Any]:
    """
    Execute CNRP causal chain through orchestrator.

    This is the ONLY authorized way to run CNRP daemons.
    Windows Scheduler must NOT call daemons directly.
    """
    cycle_id = f"CNRP-CHAIN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    logger.info("=" * 70)
    logger.info("CNRP-001 CAUSAL CHAIN EXECUTION")
    logger.info("Directive: CEO-DIR-2026-009-B")
    logger.info("Executor: FjordHQ Orchestrator (ADR-017 Compliant)")
    logger.info(f"Cycle: {cycle_id}")
    logger.info("=" * 70)

    chain_result = {
        "cycle_id": cycle_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "phases": {},
        "chain_status": "SUCCESS",
        "halted_at": None,
        "halt_reason": None
    }

    # Determine which phases to execute
    phase_order = [p['phase'] for p in CNRP_CHAIN]
    start_idx = phase_order.index(start_phase) if start_phase in phase_order else 0
    stop_idx = phase_order.index(stop_phase) if stop_phase in phase_order else len(phase_order) - 1

    conn = None
    try:
        conn = get_db_connection()

        for i, phase_config in enumerate(CNRP_CHAIN):
            phase = phase_config['phase']

            # Skip phases outside requested range
            if i < start_idx or i > stop_idx:
                continue

            logger.info(f"\n--- Phase {phase} ({phase_config['authority']}) ---")

            # Check gate authorization
            authorized, auth_reason = check_gate_authorization(
                conn, phase_config['gate'], phase_config['authority']
            )
            if not authorized:
                logger.error(f"Gate authorization failed: {auth_reason}")
                chain_result['phases'][phase] = {
                    "status": "BLOCKED",
                    "reason": auth_reason
                }
                chain_result['chain_status'] = "HALTED"
                chain_result['halted_at'] = phase
                chain_result['halt_reason'] = auth_reason
                break

            # Check chain preconditions
            precond_ok, precond_reason = check_chain_preconditions(conn, phase_config)
            if not precond_ok:
                logger.error(f"Precondition failed: {precond_reason}")
                chain_result['phases'][phase] = {
                    "status": "PRECONDITION_FAILED",
                    "reason": precond_reason
                }
                chain_result['chain_status'] = "HALTED"
                chain_result['halted_at'] = phase
                chain_result['halt_reason'] = precond_reason
                break

            # Apply delay after previous phase
            delay = phase_config.get('delay_after_previous', 0)
            if delay > 0 and i > start_idx:
                logger.info(f"Waiting {delay} minutes before {phase}...")
                import time
                time.sleep(delay * 60)

            # Execute daemon with retries
            daemon_path = FUNCTIONS_DIR / phase_config['daemon']
            max_retries = phase_config.get('max_retries', 0)
            attempt = 0
            success = False
            daemon_result = {}

            while attempt <= max_retries and not success:
                if attempt > 0:
                    logger.info(f"Retry {attempt}/{max_retries} for {phase}")
                    import time
                    time.sleep(120)  # 2 minute delay between retries

                success, daemon_result = execute_daemon(daemon_path, phase)
                attempt += 1

            # Log execution
            status = "SUCCESS" if success else "FAILED"
            log_chain_execution(conn, cycle_id, phase, status,
                               daemon_result, phase_config['authority'])
            conn.commit()

            chain_result['phases'][phase] = {
                "status": status,
                "attempts": attempt,
                "result": daemon_result.get('status', daemon_result.get('error', 'unknown'))
            }

            if not success:
                logger.error(f"Phase {phase} failed after {attempt} attempts")
                chain_result['chain_status'] = "HALTED"
                chain_result['halted_at'] = phase
                chain_result['halt_reason'] = daemon_result.get('error', 'Execution failed')

                # Escalate based on phase
                escalate_failure(conn, phase, daemon_result, phase_config)
                conn.commit()
                break

            logger.info(f"Phase {phase}: SUCCESS")

        # Emit cycle attestation if complete
        if chain_result['chain_status'] == "SUCCESS":
            emit_cycle_attestation(conn, chain_result)
            conn.commit()

    except Exception as e:
        logger.error(f"Chain execution error: {e}")
        chain_result['chain_status'] = "ERROR"
        chain_result['error'] = str(e)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

    chain_result['completed_at'] = datetime.now(timezone.utc).isoformat()

    logger.info("\n" + "=" * 70)
    logger.info(f"Chain Status: {chain_result['chain_status']}")
    logger.info("=" * 70)

    return chain_result


def escalate_failure(conn, phase: str, result: Dict, phase_config: Dict):
    """Escalate failure based on phase and severity"""
    escalation_target = {
        "R1": "LINE",
        "R2": "LINE",
        "R3": "CDMO",
        "R4": "CEO"
    }.get(phase, "LINE")

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_type,
                action_target,
                action_target_type,
                initiated_by,
                decision,
                decision_rationale,
                metadata
            ) VALUES (
                'CNRP_CHAIN_ESCALATION',
                %s,
                'FAILURE_ESCALATION',
                'ORCHESTRATOR',
                'ESCALATED',
                'CEO-DIR-2026-009-B: Chain failure requires attention',
                %s
            )
        """, (
            escalation_target,
            json.dumps({
                "phase": phase,
                "authority": phase_config['authority'],
                "error": result.get('error', 'Unknown'),
                "escalation_level": escalation_target,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, default=str)
        ))

    logger.critical(f"ESCALATED to {escalation_target}: {phase} failure")


def emit_cycle_attestation(conn, chain_result: Dict):
    """Emit attestation for completed cycle"""
    attestation_id = f"CNRP-CYCLE-ATT-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_type,
                action_target,
                action_target_type,
                initiated_by,
                decision,
                decision_rationale,
                metadata
            ) VALUES (
                'CNRP_CYCLE_ATTESTATION',
                %s,
                'CYCLE_COMPLETE',
                'ORCHESTRATOR',
                'ATTESTED',
                'CEO-DIR-2026-009-B: Full CNRP cycle completed successfully',
                %s
            )
        """, (
            attestation_id,
            json.dumps({
                "attestation_id": attestation_id,
                "cycle_id": chain_result['cycle_id'],
                "phases_completed": list(chain_result['phases'].keys()),
                "all_success": all(
                    p['status'] == 'SUCCESS'
                    for p in chain_result['phases'].values()
                ),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, default=str)
        ))

    logger.info(f"Cycle attestation issued: {attestation_id}")

# =============================================================================
# R4 STANDALONE MONITOR (for continuous 15-minute checks)
# =============================================================================

def execute_r4_standalone() -> Dict[str, Any]:
    """
    Execute R4 integrity monitor standalone (for 15-minute interval checks).
    Does NOT require full chain completion.
    """
    logger.info("Executing R4 standalone integrity monitor")

    conn = get_db_connection()
    try:
        # Check gate authorization
        authorized, reason = check_gate_authorization(conn, "G1", "VEGA")
        if not authorized:
            return {"status": "BLOCKED", "reason": reason}

        daemon_path = FUNCTIONS_DIR / "vega_epistemic_integrity_monitor.py"
        success, result = execute_daemon(daemon_path, "R4")

        log_chain_execution(
            conn,
            f"R4-MONITOR-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            "R4",
            "SUCCESS" if success else "FAILED",
            result,
            "VEGA"
        )
        conn.commit()

        return result

    finally:
        conn.close()

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CNRP Chain Executor")
    parser.add_argument("--full-cycle", action="store_true",
                       help="Execute full R1-R2-R3-R4 chain")
    parser.add_argument("--r4-monitor", action="store_true",
                       help="Execute R4 standalone monitor")
    parser.add_argument("--start-phase", default="R1",
                       help="Start from specific phase")
    parser.add_argument("--stop-phase", default="R4",
                       help="Stop at specific phase")

    args = parser.parse_args()

    if args.r4_monitor:
        result = execute_r4_standalone()
    else:
        result = execute_cnrp_chain(
            start_phase=args.start_phase,
            stop_phase=args.stop_phase
        )

    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result.get('chain_status', result.get('status')) == 'SUCCESS' else 1)
