#!/usr/bin/env python3
"""
OPTIONS DEFCON KILL-SWITCH
==========================
Directive:  CEO-DIR-2026-OPS-AUTONOMY-001
Spec:       IoS-012-C (Options Execution Architecture)
Gate:       G1 (Technical Validation)
Author:     STIG (EC-003)
Date:       2026-02-01

Integration with ADR-016 DEFCON system.
Options-specific rules layered on top of existing DEFCON infrastructure.

MiFID II Art. 17 compliance:
  - Latency kill-switch (>500ms roundtrip)
  - Runaway order detection (>10 orders/60s)
  - Margin breach (>50% portfolio)
  - Greeks breach (exceeds DEFCON limits)

ADR-019 Break-Glass: OPTIONS_FLATTEN command.
ADR-013: Hash-chain on all kill-switch events.
"""

import os
import json
import hashlib
import logging
import psycopg2
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from collections import deque

logger = logging.getLogger('OPTIONS_DEFCON_KILLSWITCH')

# =============================================================================
# DEFCON RULES (OPTIONS-SPECIFIC)
# =============================================================================

OPTIONS_DEFCON_RULES = {
    "DEFCON_5_GREEN": {
        "options_shadow_allowed": True,
        "options_live_allowed": False,       # ALWAYS False until G4
        "max_portfolio_delta": 50.0,
        "max_portfolio_gamma": 10.0,
        "max_portfolio_vega": 5000.0,
        "max_portfolio_theta": -500.0,       # max daily theta loss
        "max_single_position_notional": 5000,
        "max_dte_allowed": 45,
        "max_positions": 10,
        "action": "NORMAL",
    },
    "DEFCON_4_YELLOW": {
        "options_shadow_allowed": True,
        "options_live_allowed": False,
        "max_portfolio_delta": 25.0,
        "max_portfolio_gamma": 5.0,
        "max_portfolio_vega": 2500.0,
        "max_portfolio_theta": -250.0,
        "max_single_position_notional": 2500,
        "max_dte_allowed": 30,
        "max_positions": 5,
        "action": "TIGHTEN_GREEKS_LIMITS",
    },
    "DEFCON_3_ORANGE": {
        "options_shadow_allowed": False,
        "options_live_allowed": False,
        "action": "HALT_ALL_OPTIONS",
    },
    "DEFCON_2_RED": {
        "options_shadow_allowed": False,
        "options_live_allowed": False,
        "action": "FLATTEN_ALL_OPTIONS",
    },
    "DEFCON_1_BLACK": {
        "options_shadow_allowed": False,
        "options_live_allowed": False,
        "action": "SYSTEM_ISOLATED",
    },
}

# DEFCON level name mapping
DEFCON_LEVEL_MAP = {
    'GREEN': 'DEFCON_5_GREEN',
    'DEFCON_5_GREEN': 'DEFCON_5_GREEN',
    'YELLOW': 'DEFCON_4_YELLOW',
    'DEFCON_4_YELLOW': 'DEFCON_4_YELLOW',
    'ORANGE': 'DEFCON_3_ORANGE',
    'DEFCON_3_ORANGE': 'DEFCON_3_ORANGE',
    'RED': 'DEFCON_2_RED',
    'DEFCON_2_RED': 'DEFCON_2_RED',
    'BLACK': 'DEFCON_1_BLACK',
    'DEFCON_1_BLACK': 'DEFCON_1_BLACK',
}

# MiFID II Art. 17 thresholds
LATENCY_THRESHOLD_MS = 500
RUNAWAY_ORDER_LIMIT = 10
RUNAWAY_ORDER_WINDOW_SECONDS = 60
MARGIN_BREACH_PCT = 50.0
IV_STALENESS_MAX_SECONDS = 60

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class KillSwitchDecision:
    """Result of a kill-switch evaluation."""
    allowed: bool
    reason: str
    defcon_level: str
    action: str
    limits: Optional[Dict] = None
    timestamp: str = ''

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class KillSwitchEvent:
    """Immutable kill-switch event for hash-chain logging."""
    trigger_type: str
    trigger_value: Optional[float]
    threshold: Optional[float]
    defcon_level: str
    action_taken: str
    affected_orders: Optional[List[str]]
    details: Optional[Dict]
    content_hash: str
    chain_hash: str
    previous_hash: Optional[str]


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def _get_db_connection():
    """Get database connection using standard FHQ parameters."""
    return psycopg2.connect(
        host=os.getenv('PGHOST', '127.0.0.1'),
        port=os.getenv('PGPORT', '54322'),
        database=os.getenv('PGDATABASE', 'postgres'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', 'postgres')
    )


# =============================================================================
# DEFCON STATE READER
# =============================================================================

def get_current_defcon() -> str:
    """Read current DEFCON level from fhq_monitoring.defcon_status."""
    try:
        conn = _get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT current_level
                FROM fhq_monitoring.defcon_status
                WHERE deactivated_at IS NULL
                ORDER BY activated_at DESC
                LIMIT 1
            """)
            row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
        return 'GREEN'
    except Exception as e:
        logger.error(f"DEFCON state read failed: {e}")
        # Fail-closed: assume worst case
        return 'ORANGE'


def get_options_defcon_rules(defcon_level: str) -> Dict:
    """Get options-specific rules for current DEFCON level."""
    mapped = DEFCON_LEVEL_MAP.get(defcon_level, 'DEFCON_3_ORANGE')
    return OPTIONS_DEFCON_RULES.get(mapped, OPTIONS_DEFCON_RULES['DEFCON_3_ORANGE'])


# =============================================================================
# KILL-SWITCH EVALUATOR
# =============================================================================

class OptionsKillSwitch:
    """
    Options-specific kill-switch with MiFID II Art. 17 compliance.

    Fail-closed: any evaluation error results in HALT.
    """

    def __init__(self):
        self._order_timestamps = deque(maxlen=100)
        self._last_chain_hash = None

    def evaluate(
        self,
        portfolio_delta: float = 0.0,
        portfolio_gamma: float = 0.0,
        portfolio_vega: float = 0.0,
        portfolio_theta: float = 0.0,
        margin_utilized_pct: float = 0.0,
        last_roundtrip_ms: Optional[int] = None,
        iv_data_age_seconds: Optional[int] = None,
    ) -> KillSwitchDecision:
        """
        Evaluate whether options activity is permitted.

        Checks (in order):
        1. DEFCON level
        2. Latency breach (MiFID II Art. 17)
        3. Runaway order detection
        4. Margin breach
        5. IV staleness
        6. Greeks limits

        Returns:
            KillSwitchDecision with allowed status and details
        """
        try:
            defcon_level = get_current_defcon()
            rules = get_options_defcon_rules(defcon_level)

            # --- Check 1: DEFCON level ---
            if not rules.get('options_shadow_allowed', False):
                return KillSwitchDecision(
                    allowed=False,
                    reason=f"DEFCON {defcon_level}: options shadow trading halted",
                    defcon_level=defcon_level,
                    action=rules.get('action', 'HALT_ALL_OPTIONS')
                )

            # --- Check 2: Latency breach (MiFID II Art. 17) ---
            if last_roundtrip_ms is not None and last_roundtrip_ms > LATENCY_THRESHOLD_MS:
                self._log_event(
                    trigger_type='LATENCY_BREACH',
                    trigger_value=float(last_roundtrip_ms),
                    threshold=float(LATENCY_THRESHOLD_MS),
                    defcon_level=defcon_level,
                    action_taken='HALT_NEW_ORDERS',
                    details={'roundtrip_ms': last_roundtrip_ms}
                )
                return KillSwitchDecision(
                    allowed=False,
                    reason=f"MiFID II Art.17: latency {last_roundtrip_ms}ms > {LATENCY_THRESHOLD_MS}ms threshold",
                    defcon_level=defcon_level,
                    action='HALT_NEW_ORDERS'
                )

            # --- Check 3: Runaway order detection ---
            now = datetime.now(timezone.utc)
            self._order_timestamps.append(now)
            window_start = now - timedelta(seconds=RUNAWAY_ORDER_WINDOW_SECONDS)
            recent_count = sum(1 for ts in self._order_timestamps if ts >= window_start)

            if recent_count > RUNAWAY_ORDER_LIMIT:
                self._log_event(
                    trigger_type='RUNAWAY_ORDERS',
                    trigger_value=float(recent_count),
                    threshold=float(RUNAWAY_ORDER_LIMIT),
                    defcon_level=defcon_level,
                    action_taken='HALT_NEW_ORDERS',
                    details={'orders_in_window': recent_count, 'window_seconds': RUNAWAY_ORDER_WINDOW_SECONDS}
                )
                return KillSwitchDecision(
                    allowed=False,
                    reason=f"Runaway detection: {recent_count} orders in {RUNAWAY_ORDER_WINDOW_SECONDS}s (limit {RUNAWAY_ORDER_LIMIT})",
                    defcon_level=defcon_level,
                    action='HALT_NEW_ORDERS'
                )

            # --- Check 4: Margin breach ---
            if margin_utilized_pct > MARGIN_BREACH_PCT:
                self._log_event(
                    trigger_type='MARGIN_BREACH',
                    trigger_value=margin_utilized_pct,
                    threshold=MARGIN_BREACH_PCT,
                    defcon_level=defcon_level,
                    action_taken='HALT_NEW_ORDERS',
                    details={'margin_pct': margin_utilized_pct}
                )
                return KillSwitchDecision(
                    allowed=False,
                    reason=f"Margin breach: {margin_utilized_pct:.1f}% > {MARGIN_BREACH_PCT}% threshold",
                    defcon_level=defcon_level,
                    action='HALT_NEW_ORDERS'
                )

            # --- Check 5: IV staleness ---
            if iv_data_age_seconds is not None and iv_data_age_seconds > IV_STALENESS_MAX_SECONDS:
                self._log_event(
                    trigger_type='STALE_IV',
                    trigger_value=float(iv_data_age_seconds),
                    threshold=float(IV_STALENESS_MAX_SECONDS),
                    defcon_level=defcon_level,
                    action_taken='HALT_NEW_ORDERS',
                    details={'iv_age_seconds': iv_data_age_seconds}
                )
                return KillSwitchDecision(
                    allowed=False,
                    reason=f"Stale IV data: {iv_data_age_seconds}s > {IV_STALENESS_MAX_SECONDS}s threshold",
                    defcon_level=defcon_level,
                    action='HALT_NEW_ORDERS'
                )

            # --- Check 6: Greeks limits ---
            greeks_checks = [
                ('portfolio_delta', abs(portfolio_delta), rules.get('max_portfolio_delta', 50.0)),
                ('portfolio_gamma', abs(portfolio_gamma), rules.get('max_portfolio_gamma', 10.0)),
                ('portfolio_vega', abs(portfolio_vega), rules.get('max_portfolio_vega', 5000.0)),
            ]

            # Theta is negative (cost), check absolute value against negative limit
            max_theta = rules.get('max_portfolio_theta', -500.0)
            if portfolio_theta < max_theta:
                self._log_event(
                    trigger_type='GREEKS_BREACH',
                    trigger_value=portfolio_theta,
                    threshold=max_theta,
                    defcon_level=defcon_level,
                    action_taken='HALT_NEW_ORDERS',
                    details={'greek': 'theta', 'value': portfolio_theta, 'limit': max_theta}
                )
                return KillSwitchDecision(
                    allowed=False,
                    reason=f"Greeks breach: theta {portfolio_theta:.2f} < {max_theta:.2f} limit",
                    defcon_level=defcon_level,
                    action='HALT_NEW_ORDERS'
                )

            for greek_name, greek_val, greek_limit in greeks_checks:
                if greek_val > greek_limit:
                    self._log_event(
                        trigger_type='GREEKS_BREACH',
                        trigger_value=greek_val,
                        threshold=greek_limit,
                        defcon_level=defcon_level,
                        action_taken='HALT_NEW_ORDERS',
                        details={'greek': greek_name, 'value': greek_val, 'limit': greek_limit}
                    )
                    return KillSwitchDecision(
                        allowed=False,
                        reason=f"Greeks breach: {greek_name} {greek_val:.2f} > {greek_limit:.2f} limit",
                        defcon_level=defcon_level,
                        action='HALT_NEW_ORDERS'
                    )

            # All checks passed
            return KillSwitchDecision(
                allowed=True,
                reason=f"All kill-switch checks passed at DEFCON {defcon_level}",
                defcon_level=defcon_level,
                action='NORMAL',
                limits={
                    'max_portfolio_delta': rules.get('max_portfolio_delta'),
                    'max_portfolio_vega': rules.get('max_portfolio_vega'),
                    'max_positions': rules.get('max_positions'),
                    'max_dte_allowed': rules.get('max_dte_allowed'),
                }
            )

        except Exception as e:
            logger.error(f"Kill-switch evaluation error: {e}")
            # Fail-closed
            return KillSwitchDecision(
                allowed=False,
                reason=f"Kill-switch evaluation error (fail-closed): {e}",
                defcon_level='UNKNOWN',
                action='HALT_ALL_OPTIONS'
            )

    def flatten_all_options(self) -> KillSwitchEvent:
        """
        ADR-019 Break-Glass: OPTIONS_FLATTEN command.
        Marks all open shadow positions for closure.
        RISL authority, no human input required.
        """
        defcon_level = get_current_defcon()
        event = self._log_event(
            trigger_type='MANUAL_HALT',
            trigger_value=None,
            threshold=None,
            defcon_level=defcon_level,
            action_taken='FLATTEN_ALL_OPTIONS',
            details={'command': 'OPTIONS_FLATTEN', 'authority': 'RISL'}
        )

        # Mark all open positions for closure in database
        try:
            conn = _get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE fhq_execution.options_shadow_positions
                    SET status = 'CLOSED',
                        closed_at = NOW(),
                        updated_at = NOW()
                    WHERE status = 'OPEN'
                    RETURNING position_id
                """)
                closed = cur.fetchall()
                conn.commit()
            conn.close()
            logger.warning(f"OPTIONS_FLATTEN: Closed {len(closed)} shadow positions")
        except Exception as e:
            logger.error(f"OPTIONS_FLATTEN database error: {e}")

        return event

    # =========================================================================
    # HASH-CHAIN EVENT LOGGING (ADR-013)
    # =========================================================================

    def _log_event(
        self,
        trigger_type: str,
        trigger_value: Optional[float],
        threshold: Optional[float],
        defcon_level: str,
        action_taken: str,
        details: Optional[Dict] = None,
        affected_orders: Optional[List[str]] = None,
    ) -> KillSwitchEvent:
        """
        Create and persist a hash-chained kill-switch event.
        ADR-013 compliant: SHA256 content_hash + chain_hash.
        """
        # Content hash: hash of event payload
        content_payload = json.dumps({
            'trigger_type': trigger_type,
            'trigger_value': trigger_value,
            'threshold': threshold,
            'defcon_level': defcon_level,
            'action_taken': action_taken,
            'details': details,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }, sort_keys=True)
        content_hash = hashlib.sha256(content_payload.encode()).hexdigest()

        # Chain hash: hash of content_hash + previous_hash
        chain_input = f"{content_hash}:{self._last_chain_hash or 'GENESIS'}"
        chain_hash = hashlib.sha256(chain_input.encode()).hexdigest()

        event = KillSwitchEvent(
            trigger_type=trigger_type,
            trigger_value=trigger_value,
            threshold=threshold,
            defcon_level=defcon_level,
            action_taken=action_taken,
            affected_orders=affected_orders,
            details=details,
            content_hash=content_hash,
            chain_hash=chain_hash,
            previous_hash=self._last_chain_hash,
        )

        # Persist to database
        try:
            conn = _get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_monitoring.options_killswitch_events (
                        trigger_type, trigger_value, threshold, defcon_level,
                        action_taken, affected_orders, details,
                        content_hash, chain_hash, previous_hash, triggered_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    trigger_type, trigger_value, threshold, defcon_level,
                    action_taken,
                    json.dumps(affected_orders) if affected_orders else None,
                    json.dumps(details) if details else None,
                    content_hash, chain_hash, self._last_chain_hash,
                    'RISL_OPTIONS_KILLSWITCH'
                ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Kill-switch event persistence failed: {e}")

        # Update chain
        self._last_chain_hash = chain_hash
        logger.warning(
            f"KILLSWITCH EVENT: {trigger_type} -> {action_taken} "
            f"[chain={chain_hash[:12]}...]"
        )

        return event


# =============================================================================
# MODULE-LEVEL INSTANCE
# =============================================================================

_killswitch = OptionsKillSwitch()


def evaluate_options_permission(**kwargs) -> KillSwitchDecision:
    """Module-level convenience function for kill-switch evaluation."""
    return _killswitch.evaluate(**kwargs)


def flatten_all_options() -> KillSwitchEvent:
    """Module-level convenience for OPTIONS_FLATTEN break-glass."""
    return _killswitch.flatten_all_options()


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("OPTIONS DEFCON KILL-SWITCH — Self-Test")
    print("IoS-012-C / CEO-DIR-2026-OPS-AUTONOMY-001")
    print("=" * 60)

    ks = OptionsKillSwitch()

    # Test 1: Normal conditions
    result = ks.evaluate(
        portfolio_delta=10.0,
        portfolio_gamma=2.0,
        portfolio_vega=1000.0,
        portfolio_theta=-100.0,
    )
    print(f"\n1. Normal conditions:")
    print(f"   Allowed: {result.allowed}")
    print(f"   Reason:  {result.reason}")
    print(f"   DEFCON:  {result.defcon_level}")

    # Test 2: Latency breach
    result = ks.evaluate(last_roundtrip_ms=750)
    print(f"\n2. Latency breach (750ms):")
    print(f"   Allowed: {result.allowed}")
    print(f"   Reason:  {result.reason}")
    assert not result.allowed, "Should be blocked"
    print("   PASS: Blocked")

    # Test 3: Greeks breach
    result = ks.evaluate(portfolio_delta=100.0)
    print(f"\n3. Delta breach (100.0):")
    print(f"   Allowed: {result.allowed}")
    print(f"   Reason:  {result.reason}")
    assert not result.allowed, "Should be blocked"
    print("   PASS: Blocked")

    # Test 4: Margin breach
    result = ks.evaluate(margin_utilized_pct=75.0)
    print(f"\n4. Margin breach (75%):")
    print(f"   Allowed: {result.allowed}")
    print(f"   Reason:  {result.reason}")
    assert not result.allowed, "Should be blocked"
    print("   PASS: Blocked")

    # Test 5: Stale IV
    result = ks.evaluate(iv_data_age_seconds=120)
    print(f"\n5. Stale IV (120s):")
    print(f"   Allowed: {result.allowed}")
    print(f"   Reason:  {result.reason}")
    assert not result.allowed, "Should be blocked"
    print("   PASS: Blocked")

    # Test 6: DEFCON rules lookup
    for level in ['GREEN', 'YELLOW', 'ORANGE', 'RED', 'BLACK']:
        rules = get_options_defcon_rules(level)
        shadow = rules.get('options_shadow_allowed', False)
        print(f"\n6. DEFCON {level}: shadow_allowed={shadow}, action={rules['action']}")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
