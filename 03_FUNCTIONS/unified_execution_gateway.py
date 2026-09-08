#!/usr/bin/env python3
"""
UNIFIED EXECUTION GATEWAY
=========================
CEO Directive: 2025-12-20
Classification: CRITICAL SECURITY INFRASTRUCTURE

This module is the SINGLE MANDATORY entry point for ALL trade execution.
No position sizing, capital allocation, or order construction may occur
before execution permission returns TRUE.

Constitutional Authority: ADR-012, ADR-017, ADR-018
VEGA Attestation Required: Yes

Author: STIG (System for Technical Implementation & Governance)

===============================================================================
CEO DIRECTIVE 2025-12-21: EXECUTION FREEZE ACTIVE
===============================================================================
Status: ALL EXECUTION BLOCKED - CASCADE FAILURE CONTAINMENT
Incident: 3x over-limit execution (MSTR 1088 shares, 2x leverage)
Root Cause: Database/Broker desync, exposure gate logged but didn't block

EXECUTION_FREEZE = True blocks ALL execution paths through this gateway.
This is the MASTER KILL SWITCH for the entire execution subsystem.

Re-enablement requires:
- STIG confirmation of all fixes (A-E)
- VEGA attestation
- CEO explicit approval

DO NOT SET EXECUTION_FREEZE = False WITHOUT CEO AUTHORIZATION.
===============================================================================
"""

# MASTER KILL SWITCH - CEO DIRECTIVE 2025-12-21
# LIFTED: CEO DIRECTIVE 2025-12-22 - Monday liquidation complete ($104,924 cash)
EXECUTION_FREEZE = False  # LIFTED by CEO 2025-12-22 after successful liquidation

import os
import logging
import psycopg2
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

logger = logging.getLogger('UNIFIED_GATEWAY')

# =============================================================================
# DATABASE CONNECTION FOR EXECUTION STATE
# =============================================================================

def _get_execution_state():
    """CEO-DIR-2026-020 D4: Read execution_state for cognitive fasting check."""
    try:
        conn = psycopg2.connect(
            host=os.getenv('PGHOST', '127.0.0.1'),
            port=os.getenv('PGPORT', '54322'),
            database=os.getenv('PGDATABASE', 'postgres'),
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD', 'postgres')
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cognitive_fasting, fasting_reason, defcon_level
                FROM fhq_governance.execution_state
                ORDER BY state_id DESC
                LIMIT 1
            """)
            row = cur.fetchone()
        conn.close()
        if row:
            return {
                'cognitive_fasting': row[0],
                'fasting_reason': row[1],
                'defcon_level': row[2]
            }
        return {'cognitive_fasting': False, 'fasting_reason': None, 'defcon_level': 'NORMAL'}
    except Exception as e:
        logger.error(f"Failed to read execution_state: {e}")
        # Fail-closed: assume fasting if we can't read state
        return {'cognitive_fasting': True, 'fasting_reason': 'STATE_READ_FAILED', 'defcon_level': 'UNKNOWN'}

# =============================================================================
# EXECUTION DECISION (Non-Negotiable Contract)
# =============================================================================

@dataclass
class ExecutionDecision:
    """
    Immutable execution decision returned by gateway.

    Rule: No sizing, allocation, or order construction may occur
    before allowed == True.
    """
    allowed: bool
    reason: str
    execution_scope: str  # 'CRYPTO' | 'EQUITY' | 'ETF' | 'FX' | 'BLOCKED'
    asset_class: str
    symbol: str
    timestamp: str

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


# =============================================================================
# PAPER MODE HARD CAP (CEO DIRECTIVE - TEMPORARY BUT CRITICAL)
# =============================================================================

PAPER_MODE_MAX_EXPOSURE_PCT = 0.10  # 10% hard cap per trade
PAPER_MODE_ENABLED = True  # Always true during testing/bugfix phase

def validate_position_size(
    symbol: str,
    requested_size: float,
    account_equity: float
) -> Tuple[float, str]:
    """
    Cap position size regardless of Kelly/confidence/regime.

    This is SECURITY LOGIC, not trading logic.
    Lives ONLY in gateway, never spread around.

    Returns:
        Tuple of (capped_size, reason)
    """
    if not PAPER_MODE_ENABLED:
        return requested_size, "Paper mode disabled"

    max_allowed = account_equity * PAPER_MODE_MAX_EXPOSURE_PCT

    if requested_size > max_allowed:
        logger.warning(
            f"PAPER CAP: {symbol} requested ${requested_size:.2f}, "
            f"capped to ${max_allowed:.2f} (10% of ${account_equity:.2f})"
        )
        return max_allowed, f"Capped from ${requested_size:.2f} to 10% max"

    return requested_size, "Within limits"


# =============================================================================
# HOLIDAY EXECUTION GATE INTEGRATION
# =============================================================================

try:
    from holiday_execution_gate import (
        check_holiday_execution_gate,
        classify_asset,
        HOLIDAY_MODE_ENABLED,
        APPROVED_CRYPTO_ASSETS
    )
    HOLIDAY_GATE_AVAILABLE = True
    logger.info(f"Holiday gate loaded: ENABLED={HOLIDAY_MODE_ENABLED}")
except ImportError as e:
    logger.error(f"CRITICAL: Holiday gate import failed: {e}")
    HOLIDAY_GATE_AVAILABLE = False
    HOLIDAY_MODE_ENABLED = False
    APPROVED_CRYPTO_ASSETS = {'BTC', 'ETH', 'SOL'}

    def check_holiday_execution_gate(symbol, target_state, source_signal=None):
        return True, "Holiday gate not available", "UNKNOWN"

    def classify_asset(symbol):
        return "UNKNOWN"


# =============================================================================
# BLOCKED EXECUTION LOGGING
# =============================================================================

def log_blocked_execution(
    symbol: str,
    asset_class: str,
    reason: str,
    source_signal: Optional[str] = None,
    requested_size: Optional[float] = None
):
    """
    Log blocked execution to governance audit trail.

    This creates an immutable record of all blocked trades.
    """
    log_entry = {
        'event_type': 'EXECUTION_BLOCKED',
        'symbol': symbol,
        'asset_class': asset_class,
        'reason': reason,
        'source_signal': source_signal,
        'requested_size': requested_size,
        'holiday_mode': HOLIDAY_MODE_ENABLED,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'gateway_version': '1.0.0'
    }

    logger.warning(f"EXECUTION BLOCKED: {log_entry}")

    # TODO: Write to fhq_governance.execution_blocks table
    # This should be implemented when database schema is ready


# =============================================================================
# MAIN GATEWAY FUNCTION
# =============================================================================

def validate_execution_permission(
    symbol: str,
    source_signal: Optional[str] = None,
    target_state: str = 'ACTIVE'
) -> ExecutionDecision:
    """
    MANDATORY gateway for ALL trade execution.

    CRITICAL RULES:
    1. This function MUST be called BEFORE any sizing calculation
    2. This function MUST be called BEFORE any order construction
    3. This function MUST be called BEFORE any capital allocation
    4. If allowed == False, caller MUST return early with NO further processing

    Args:
        symbol: The asset symbol to trade (e.g., 'NVDA', 'BTC/USD')
        source_signal: Optional source signal for proxy resolution
        target_state: Target execution state (default 'ACTIVE')

    Returns:
        ExecutionDecision with allowed status and details
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # =========================================================================
    # MASTER KILL SWITCH - CEO DIRECTIVE 2025-12-21
    # This check MUST be first. No execution permitted when freeze is active.
    # =========================================================================
    if EXECUTION_FREEZE:
        logger.critical(
            f"EXECUTION FREEZE ACTIVE: {symbol} blocked by CEO Directive 2025-12-21"
        )
        return ExecutionDecision(
            allowed=False,
            reason="CEO DIRECTIVE 2025-12-21: EXECUTION FREEZE - Cascade failure containment",
            execution_scope='BLOCKED',
            asset_class='FROZEN',
            symbol=symbol,
            timestamp=timestamp
        )

    # =========================================================================
    # CEO-DIR-2026-020 D4: COGNITIVE FASTING CHECK
    # Block execution when system is in cognitive fasting state
    # =========================================================================
    exec_state = _get_execution_state()
    if exec_state.get('cognitive_fasting', False):
        fasting_reason = exec_state.get('fasting_reason', 'Unknown')
        logger.warning(
            f"COGNITIVE FASTING ACTIVE: {symbol} blocked - {fasting_reason}"
        )
        return ExecutionDecision(
            allowed=False,
            reason=f"CEO-DIR-2026-020: COGNITIVE FASTING - {fasting_reason}",
            execution_scope='BLOCKED',
            asset_class='FASTING',
            symbol=symbol,
            timestamp=timestamp
        )

    # Classify the asset
    asset_class = classify_asset(symbol)

    # If holiday gate not available, default to BLOCKED for safety
    if not HOLIDAY_GATE_AVAILABLE:
        logger.error(f"GATEWAY BLOCKED: Holiday gate unavailable for {symbol}")
        return ExecutionDecision(
            allowed=False,
            reason="Holiday gate unavailable - blocking for safety",
            execution_scope='BLOCKED',
            asset_class=asset_class,
            symbol=symbol,
            timestamp=timestamp
        )

    # Check holiday execution gate
    permitted, reason, gate_asset_class = check_holiday_execution_gate(
        symbol=symbol,
        target_state=target_state,
        source_signal=source_signal
    )

    if not permitted:
        log_blocked_execution(
            symbol=symbol,
            asset_class=gate_asset_class,
            reason=reason,
            source_signal=source_signal
        )
        return ExecutionDecision(
            allowed=False,
            reason=reason,
            execution_scope='BLOCKED',
            asset_class=gate_asset_class,
            symbol=symbol,
            timestamp=timestamp
        )

    # Determine execution scope
    execution_scope = gate_asset_class
    if gate_asset_class == 'CRYPTO':
        execution_scope = 'CRYPTO'
    elif gate_asset_class == 'CRYPTO_PROXY':
        execution_scope = 'CRYPTO'  # Treat as crypto for execution purposes
    elif gate_asset_class in ('EQUITY', 'ETF'):
        execution_scope = 'EQUITY'
    elif gate_asset_class == 'FX':
        execution_scope = 'FX'
    else:
        execution_scope = gate_asset_class

    logger.info(f"GATEWAY PERMITTED: {symbol} ({execution_scope}) - {reason}")

    return ExecutionDecision(
        allowed=True,
        reason=reason,
        execution_scope=execution_scope,
        asset_class=gate_asset_class,
        symbol=symbol,
        timestamp=timestamp
    )


# =============================================================================
# OPTIONS EXECUTION PERMISSION (IoS-012-C)
# CEO-DIR-2026-OPS-AUTONOMY-001 / G1 Technical Validation
# =============================================================================

def validate_options_permission(
    symbol: str,
    strategy_type: str,
    source_signal: Optional[str] = None
) -> ExecutionDecision:
    """
    Validate whether an options order is permitted.

    This is the OPTIONS-SPECIFIC gateway. Called by options_shadow_adapter
    BEFORE any options order construction.

    Checks:
    1. Master kill switch (EXECUTION_FREEZE)
    2. Cognitive fasting
    3. DEFCON level (options require GREEN or YELLOW)
    4. Strategy type is in allowed set

    Args:
        symbol: The underlying symbol (e.g., 'AAPL')
        strategy_type: Options strategy type (e.g., 'VERTICAL_SPREAD')
        source_signal: Optional source signal

    Returns:
        ExecutionDecision with allowed status
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Inherit all base gateway checks
    if EXECUTION_FREEZE:
        return ExecutionDecision(
            allowed=False,
            reason="CEO DIRECTIVE: EXECUTION FREEZE - options blocked",
            execution_scope='BLOCKED',
            asset_class='OPTIONS',
            symbol=symbol,
            timestamp=timestamp
        )

    exec_state = _get_execution_state()
    if exec_state.get('cognitive_fasting', False):
        return ExecutionDecision(
            allowed=False,
            reason=f"COGNITIVE FASTING: options blocked - {exec_state.get('fasting_reason')}",
            execution_scope='BLOCKED',
            asset_class='OPTIONS',
            symbol=symbol,
            timestamp=timestamp
        )

    # Options-specific: DEFCON must be GREEN or YELLOW
    defcon = exec_state.get('defcon_level', 'UNKNOWN')
    options_allowed_defcon = {'NORMAL', 'GREEN', 'DEFCON_5_GREEN', 'YELLOW', 'DEFCON_4_YELLOW'}
    if defcon not in options_allowed_defcon:
        log_blocked_execution(
            symbol=symbol,
            asset_class='OPTIONS',
            reason=f"DEFCON {defcon}: options require GREEN or YELLOW",
            source_signal=source_signal
        )
        return ExecutionDecision(
            allowed=False,
            reason=f"DEFCON {defcon}: options trading halted (requires GREEN or YELLOW)",
            execution_scope='BLOCKED',
            asset_class='OPTIONS',
            symbol=symbol,
            timestamp=timestamp
        )

    # Strategy validation
    allowed_strategies = {
        'CASH_SECURED_PUT', 'COVERED_CALL', 'VERTICAL_SPREAD',
        'IRON_CONDOR', 'PROTECTIVE_PUT'
    }
    if strategy_type not in allowed_strategies:
        log_blocked_execution(
            symbol=symbol,
            asset_class='OPTIONS',
            reason=f"Strategy {strategy_type} not in allowed set",
            source_signal=source_signal
        )
        return ExecutionDecision(
            allowed=False,
            reason=f"Strategy {strategy_type} blocked by gateway (not in allowed set)",
            execution_scope='BLOCKED',
            asset_class='OPTIONS',
            symbol=symbol,
            timestamp=timestamp
        )

    logger.info(f"OPTIONS GATEWAY PERMITTED: {symbol} / {strategy_type}")
    return ExecutionDecision(
        allowed=True,
        reason=f"Options shadow permitted: {strategy_type} on {symbol}",
        execution_scope='OPTIONS',
        asset_class='OPTIONS',
        symbol=symbol,
        timestamp=timestamp
    )


def can_execute(symbol: str, source_signal: Optional[str] = None) -> bool:
    """
    Quick boolean check for execution permission.

    Use this ONLY for pre-flight checks. Full workflow MUST use
    validate_execution_permission() to get complete decision.
    """
    decision = validate_execution_permission(symbol, source_signal)
    return decision.allowed


# =============================================================================
# GATEWAY STATUS
# =============================================================================

def get_gateway_status() -> dict:
    """
    Get current gateway configuration status.
    """
    return {
        'gateway_version': '1.1.0',
        'holiday_gate_available': HOLIDAY_GATE_AVAILABLE,
        'holiday_mode_enabled': HOLIDAY_MODE_ENABLED,
        'paper_mode_enabled': PAPER_MODE_ENABLED,
        'paper_max_exposure_pct': PAPER_MODE_MAX_EXPOSURE_PCT,
        'approved_crypto_assets': list(APPROVED_CRYPTO_ASSETS) if HOLIDAY_GATE_AVAILABLE else [],
        'options_gateway_enabled': True,
        'options_execution_mode': 'SHADOW_PAPER',
        'checked_at': datetime.now(timezone.utc).isoformat()
    }


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("UNIFIED EXECUTION GATEWAY - Self Test")
    print("=" * 60)

    print("\n1. Gateway Status:")
    status = get_gateway_status()
    for k, v in status.items():
        print(f"   {k}: {v}")

    print("\n2. Execution Permission Tests:")
    test_cases = [
        ('BTC/USD', None, "Crypto - should be ALLOWED"),
        ('ETH/USD', None, "Crypto - should be ALLOWED"),
        ('NVDA', None, "Equity - should be BLOCKED"),
        ('MSTR', None, "Crypto proxy no source - should be BLOCKED"),
        ('MSTR', 'BTC-USD', "Crypto proxy with crypto source - should be ALLOWED"),
        ('SPY', None, "ETF - should be BLOCKED"),
    ]

    for symbol, source, desc in test_cases:
        decision = validate_execution_permission(symbol, source)
        status = "PASS" if decision.allowed else "BLOCK"
        print(f"   [{status}] {symbol} ({desc})")
        print(f"         Reason: {decision.reason}")

    print("\n3. Position Size Cap Tests:")
    cap_tests = [
        ('BTC/USD', 50000, 100000, "50% request"),
        ('ETH/USD', 5000, 100000, "5% request"),
        ('SOL/USD', 90000, 100000, "90% request (should cap)"),
    ]

    for symbol, requested, equity, desc in cap_tests:
        capped, reason = validate_position_size(symbol, requested, equity)
        print(f"   {symbol}: ${requested} -> ${capped:.2f} ({desc})")

    print("\n" + "=" * 60)
    print("Self-test complete")
    print("=" * 60)
