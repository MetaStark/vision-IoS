#!/usr/bin/env python3
"""
GOVERNANCE PREFLIGHT — Fail-Closed Runtime Gate
================================================
Enforces 3 constitutional checks before any daemon writes:
  1. DEFCON gate: must be GREEN or YELLOW (RED/BLACK/ORANGE blocked)
  2. Paper Execution Authority: IoS-012 must be PAPER with live_api_enabled=false
  3. Execution Eligibility: blocking flags must be readable and consistent

Fail-closed design: any check failure or missing data = daemon aborts.
No writes occur without all 3 checks passing.

Directive: CEO-DIR-2026-RUNTIME-BINDING-AND-CALIBRATION-010 Workstream B
Author: STIG (CTO) | EC-003_2026_PRODUCTION
Date: 2026-02-02
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger('governance_preflight')

BLOCKED_DEFCON_LEVELS = {'RED', 'BLACK', 'ORANGE'}


class GovernancePreflightError(Exception):
    """Raised when a governance preflight check fails. Daemon must abort."""
    pass


def check_defcon_gate(cur):
    """
    Check 1: DEFCON must be GREEN or YELLOW.
    Fail-closed: no row or blocked level = abort.
    """
    cur.execute("""
        SELECT defcon_level FROM fhq_governance.defcon_state
        WHERE is_current = true
    """)
    row = cur.fetchone()
    if not row:
        raise GovernancePreflightError(
            "DEFCON_GATE_FAIL: No current DEFCON state found. Fail-closed: aborting."
        )
    level = row['defcon_level']
    if level in BLOCKED_DEFCON_LEVELS:
        raise GovernancePreflightError(
            f"DEFCON_GATE_FAIL: Current level is {level}. "
            f"Blocked levels: {BLOCKED_DEFCON_LEVELS}. Aborting."
        )
    return level


def check_paper_execution_authority(cur):
    """
    Check 2: paper_execution_authority for IoS-012 must enforce:
      - activation_mode = 'PAPER'
      - live_api_enabled = false
    Fail-closed: missing row = abort.
    """
    cur.execute("""
        SELECT ios_id, activation_mode, live_api_enabled, paper_api_enabled,
               execution_enabled, vega_certification_ref
        FROM fhq_governance.paper_execution_authority
        WHERE ios_id = 'IoS-012'
    """)
    row = cur.fetchone()
    if not row:
        raise GovernancePreflightError(
            "PAPER_AUTH_FAIL: No paper_execution_authority row for IoS-012. "
            "Fail-closed: aborting."
        )
    if row['activation_mode'] != 'PAPER':
        raise GovernancePreflightError(
            f"PAPER_AUTH_FAIL: activation_mode={row['activation_mode']}, expected PAPER. Aborting."
        )
    if row['live_api_enabled']:
        raise GovernancePreflightError(
            "PAPER_AUTH_FAIL: live_api_enabled=true. Constitutional violation. Aborting."
        )
    return {
        'activation_mode': row['activation_mode'],
        'live_api_enabled': row['live_api_enabled'],
        'paper_api_enabled': row['paper_api_enabled'],
        'vega_cert': row['vega_certification_ref']
    }


def check_execution_eligibility(cur):
    """
    Check 3: execution_eligibility_registry must be readable.
    If entries exist, all blocking flags (live_capital_blocked, leverage_blocked,
    ec022_dependency_blocked) must be True. False or NULL = fail-closed abort.
    If no entries exist, shadow operations proceed (pre-eligibility pipeline stage).
    """
    cur.execute("""
        SELECT eligibility_code, tier_status, execution_mode,
               live_capital_blocked, leverage_blocked, ec022_dependency_blocked
        FROM fhq_learning.execution_eligibility_registry
        ORDER BY evaluated_at DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    if not row:
        return {
            'status': 'NO_ENTRIES',
            'note': 'No eligibility entries. Shadow operations proceed (pre-eligibility stage).'
        }

    flags = {
        'live_capital_blocked': row['live_capital_blocked'],
        'leverage_blocked': row['leverage_blocked'],
        'ec022_dependency_blocked': row['ec022_dependency_blocked']
    }

    for flag_name, flag_value in flags.items():
        if flag_value is None:
            raise GovernancePreflightError(
                f"ELIGIBILITY_FAIL: {flag_name} is NULL. Unmappable state. "
                f"Fail-closed: aborting."
            )
        if not flag_value:
            raise GovernancePreflightError(
                f"ELIGIBILITY_FAIL: {flag_name}=False. Live capital/leverage not blocked. "
                f"Constitutional violation. Aborting."
            )

    return {
        'eligibility_code': row['eligibility_code'],
        'tier_status': row['tier_status'],
        'execution_mode': row['execution_mode'],
        **flags
    }


def run_governance_preflight(cur, daemon_name: str) -> dict:
    """
    Execute all 3 governance checks. Returns result dict on success.
    Raises GovernancePreflightError on any failure (fail-closed).
    """
    logger.info(f"[{daemon_name}] GOVERNANCE PREFLIGHT -- Starting 3-check sequence")

    defcon_level = check_defcon_gate(cur)
    logger.info(f"[{daemon_name}]   PASS DEFCON: {defcon_level}")

    paper_auth = check_paper_execution_authority(cur)
    logger.info(f"[{daemon_name}]   PASS PAPER_AUTH: mode={paper_auth['activation_mode']}, "
                f"live_api={paper_auth['live_api_enabled']}")

    eligibility = check_execution_eligibility(cur)
    elig_status = eligibility.get('status', eligibility.get('tier_status', 'OK'))
    logger.info(f"[{daemon_name}]   PASS ELIGIBILITY: {elig_status}")

    result = {
        'preflight_passed': True,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'daemon': daemon_name,
        'defcon_level': defcon_level,
        'paper_authority': paper_auth,
        'eligibility': eligibility
    }

    logger.info(f"[{daemon_name}] GOVERNANCE PREFLIGHT -- ALL CHECKS PASSED")
    return result
