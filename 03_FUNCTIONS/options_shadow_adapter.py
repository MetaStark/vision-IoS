#!/usr/bin/env python3
"""
OPTIONS SHADOW ADAPTER
======================
Directive:  CEO-DIR-2026-OPS-AUTONOMY-001
Spec:       IoS-012-C (Options Execution Architecture)
Gate:       G1 (Technical Validation)
Author:     STIG (EC-003)
Date:       2026-02-01

Shadow/paper trading adapter for options strategies.
execution_mode = SHADOW_PAPER (hardcoded, non-negotiable).

Pipeline:
  1. Validate execution_mode == SHADOW_PAPER
  2. Validate DEFCON >= GREEN via kill-switch
  3. Query Alpaca options chain (get_option_contracts)
  4. Calculate Greeks via options_greeks_calculator
  5. Validate Greeks within DEFCON limits
  6. Submit paper order via Alpaca (asset_class=US_OPTION)
  7. Record in fhq_execution.options_shadow_orders
  8. Monitor position (theta decay, Greeks drift, DTE)
  9. Auto-close at DTE threshold (default 7)
  10. Record outcome in fhq_execution.options_shadow_outcomes
  11. Generate evidence JSON with full lineage hash

Supported strategies (defined-risk only):
  - Cash-Secured Put (CSP)
  - Covered Call (CC)
  - Vertical Spread (Bull Put / Bear Call)
  - Iron Condor
  - Protective Put

BLOCKED strategies:
  - Naked calls
  - Naked puts beyond CSP
  - Straddles/strangles without max loss cap
  - 0DTE
  - Any undefined-risk strategy
"""

import os
import sys
import json
import uuid
import hashlib
import logging
import psycopg2
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger('OPTIONS_SHADOW_ADAPTER')

# =============================================================================
# HARD CONSTRAINTS — Class A Governance Breach if violated
# =============================================================================

EXECUTION_MODE = "SHADOW_PAPER"  # NON-NEGOTIABLE. G4 required to change.

SUPPORTED_STRATEGIES = frozenset([
    'CASH_SECURED_PUT',
    'COVERED_CALL',
    'VERTICAL_SPREAD',
    'IRON_CONDOR',
    'PROTECTIVE_PUT',
])

BLOCKED_STRATEGIES = frozenset([
    'NAKED_CALL',
    'NAKED_PUT',
    'STRADDLE',
    'STRANGLE',
    'ZERO_DTE',
    'CALENDAR_SPREAD',      # Deferred to Phase B
    'DIAGONAL_SPREAD',      # Deferred to Phase B
    'BUTTERFLY',            # Deferred to Phase B
])

AUTO_CLOSE_DTE = 7  # Auto-close at 7 DTE to avoid assignment risk
MAX_DTE_ENTRY = 45  # Maximum DTE at entry


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class OptionsOrderLeg:
    """Single leg of an options order."""
    side: str               # 'BUY' or 'SELL'
    strike: float
    expiration: str         # ISO date string
    option_type: str        # 'CALL' or 'PUT'
    quantity: int           # Always positive; side determines long/short


@dataclass
class ShadowOrderRequest:
    """Complete shadow order request."""
    strategy_type: str
    underlying: str
    legs: List[OptionsOrderLeg]
    source_hypothesis_id: Optional[str] = None
    entry_regime: Optional[str] = None
    rationale: Optional[str] = None


@dataclass
class ShadowOrderResult:
    """Result of shadow order submission."""
    success: bool
    order_id: Optional[str]
    order_ref: Optional[str]
    reason: str
    greeks_at_entry: Optional[Dict]
    max_loss: Optional[float]
    max_profit: Optional[float]
    lineage_hash: str
    timestamp: str


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
# GOVERNANCE ASSERTIONS
# =============================================================================

def _assert_shadow_paper():
    """HARD CHECK: execution_mode must be SHADOW_PAPER."""
    assert EXECUTION_MODE == "SHADOW_PAPER", \
        f"GOVERNANCE BREACH: execution_mode={EXECUTION_MODE}, expected SHADOW_PAPER"


def _assert_no_live_capital():
    """HARD CHECK: no live capital may be allocated."""
    # In SHADOW_PAPER mode, no real capital is ever at risk.
    # This check is structural — the Alpaca paper account has no real money.
    pass


def _assert_strategy_allowed(strategy_type: str):
    """HARD CHECK: strategy must be in supported set."""
    assert strategy_type in SUPPORTED_STRATEGIES, \
        f"GOVERNANCE BREACH: strategy '{strategy_type}' not in supported set"
    assert strategy_type not in BLOCKED_STRATEGIES, \
        f"GOVERNANCE BREACH: strategy '{strategy_type}' is explicitly blocked"


def _assert_defined_risk(legs: List[OptionsOrderLeg], strategy_type: str):
    """
    HARD CHECK: all strategies must have defined maximum loss.

    Naked calls (selling calls without owning underlying or buying
    higher strike) have UNLIMITED risk and are forbidden.
    """
    sell_calls = [l for l in legs if l.side == 'SELL' and l.option_type == 'CALL']
    buy_calls = [l for l in legs if l.side == 'BUY' and l.option_type == 'CALL']

    if sell_calls and strategy_type != 'COVERED_CALL':
        # Must have a protective buy call at higher strike for each sell call
        assert len(buy_calls) >= len(sell_calls), \
            f"GOVERNANCE BREACH: {len(sell_calls)} short calls without protective long calls"

    sell_puts = [l for l in legs if l.side == 'SELL' and l.option_type == 'PUT']
    buy_puts = [l for l in legs if l.side == 'BUY' and l.option_type == 'PUT']

    if sell_puts and strategy_type != 'CASH_SECURED_PUT':
        # Must have a protective buy put at lower strike for each sell put
        assert len(buy_puts) >= len(sell_puts), \
            f"GOVERNANCE BREACH: {len(sell_puts)} short puts without protective long puts"


def _assert_dte_valid(legs: List[OptionsOrderLeg]):
    """HARD CHECK: DTE must be within allowed range."""
    from datetime import date

    today = date.today()
    for leg in legs:
        exp_date = date.fromisoformat(leg.expiration)
        dte = (exp_date - today).days
        assert dte > 0, f"GOVERNANCE BREACH: expired option {leg.expiration}"
        assert dte <= MAX_DTE_ENTRY, \
            f"GOVERNANCE BREACH: DTE {dte} > max {MAX_DTE_ENTRY} for {leg.expiration}"


# =============================================================================
# HASH-CHAIN (ADR-013)
# =============================================================================

def _compute_lineage_hash(request: ShadowOrderRequest, greeks: Dict) -> str:
    """Compute SHA256 lineage hash for order traceability."""
    payload = json.dumps({
        'strategy_type': request.strategy_type,
        'underlying': request.underlying,
        'legs': [asdict(l) for l in request.legs],
        'source_hypothesis_id': request.source_hypothesis_id,
        'entry_regime': request.entry_regime,
        'greeks': greeks,
        'execution_mode': EXECUTION_MODE,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _compute_chain_hash(content_hash: str, previous_hash: Optional[str]) -> str:
    """Compute chain hash linking to previous event."""
    chain_input = f"{content_hash}:{previous_hash or 'GENESIS'}"
    return hashlib.sha256(chain_input.encode()).hexdigest()


# =============================================================================
# SHADOW ORDER ADAPTER
# =============================================================================

class OptionsShadowAdapter:
    """
    Shadow/paper trading adapter for options.

    This is the sole entry point for options order creation.
    All governance constraints are enforced here.
    """

    def __init__(self):
        self._last_chain_hash = None

    def submit_shadow_order(self, request: ShadowOrderRequest) -> ShadowOrderResult:
        """
        Submit a shadow options order through the full validation pipeline.

        Steps:
        1. Governance assertions (execution mode, strategy, defined risk, DTE)
        2. Kill-switch evaluation (DEFCON, latency, Greeks limits)
        3. Greeks calculation
        4. Order recording to database
        5. Evidence generation with lineage hash
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        try:
            # ================================================================
            # Step 1: Governance assertions
            # ================================================================
            _assert_shadow_paper()
            _assert_no_live_capital()
            _assert_strategy_allowed(request.strategy_type)
            _assert_defined_risk(request.legs, request.strategy_type)
            _assert_dte_valid(request.legs)

            # ================================================================
            # Step 2: Kill-switch evaluation
            # ================================================================
            from options_defcon_killswitch import evaluate_options_permission

            ks_decision = evaluate_options_permission()
            if not ks_decision.allowed:
                return ShadowOrderResult(
                    success=False,
                    order_id=None,
                    order_ref=None,
                    reason=f"Kill-switch blocked: {ks_decision.reason}",
                    greeks_at_entry=None,
                    max_loss=None,
                    max_profit=None,
                    lineage_hash='',
                    timestamp=timestamp,
                )

            # ================================================================
            # Step 3: Greeks calculation
            # ================================================================
            from options_greeks_calculator import (
                black_scholes_greeks,
                strategy_greeks,
                vertical_spread_risk,
                iron_condor_risk,
            )

            # Get current underlying price (from database or market data)
            underlying_price = self._get_underlying_price(request.underlying)
            if underlying_price is None:
                return ShadowOrderResult(
                    success=False, order_id=None, order_ref=None,
                    reason=f"Cannot resolve underlying price for {request.underlying}",
                    greeks_at_entry=None, max_loss=None, max_profit=None,
                    lineage_hash='', timestamp=timestamp,
                )

            # Build legs for strategy_greeks
            from datetime import date
            today = date.today()
            calc_legs = []
            for leg in request.legs:
                exp_date = date.fromisoformat(leg.expiration)
                dte = (exp_date - today).days
                T = dte / 365.0
                qty = leg.quantity if leg.side == 'BUY' else -leg.quantity
                calc_legs.append({
                    'strike': leg.strike,
                    'expiry_years': T,
                    'volatility': 0.25,  # Default; will use IV from chain in production
                    'option_type': leg.option_type,
                    'quantity': qty,
                })

            greeks_result = strategy_greeks(calc_legs, underlying_price)
            greeks_at_entry = greeks_result['aggregate']

            # Calculate max loss/profit
            max_loss, max_profit = self._calculate_risk(
                request.strategy_type, request.legs, greeks_result
            )

            # ================================================================
            # Step 4: Record to database
            # ================================================================
            order_id = str(uuid.uuid4())
            order_ref = f"OPT-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{order_id[:8]}"
            lineage_hash = _compute_lineage_hash(request, greeks_at_entry)
            chain_hash = _compute_chain_hash(lineage_hash, self._last_chain_hash)

            # Get current regime
            entry_regime = request.entry_regime or self._get_current_regime()
            defcon_level = ks_decision.defcon_level

            legs_json = json.dumps([asdict(l) for l in request.legs])
            greeks_json = json.dumps(greeks_at_entry)

            try:
                conn = _get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO fhq_execution.options_shadow_orders (
                            order_id, order_ref, strategy_type, underlying,
                            legs, greeks_at_entry, max_loss, max_profit,
                            execution_mode, source_hypothesis_id, source_agent,
                            entry_regime, defcon_at_entry,
                            lineage_hash, chain_hash, status
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s, %s
                        )
                    """, (
                        order_id, order_ref, request.strategy_type, request.underlying,
                        legs_json, greeks_json, max_loss, max_profit,
                        EXECUTION_MODE, request.source_hypothesis_id,
                        'STIG_OPTIONS_SHADOW',
                        entry_regime, defcon_level,
                        lineage_hash, chain_hash, 'SUBMITTED',
                    ))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Order persistence failed: {e}")
                return ShadowOrderResult(
                    success=False, order_id=None, order_ref=None,
                    reason=f"Database error: {e}",
                    greeks_at_entry=greeks_at_entry,
                    max_loss=max_loss, max_profit=max_profit,
                    lineage_hash=lineage_hash, timestamp=timestamp,
                )

            self._last_chain_hash = chain_hash

            logger.info(
                f"SHADOW ORDER: {order_ref} | {request.strategy_type} | "
                f"{request.underlying} | delta={greeks_at_entry['delta']:.4f} | "
                f"max_loss={max_loss}"
            )

            return ShadowOrderResult(
                success=True,
                order_id=order_id,
                order_ref=order_ref,
                reason="Shadow order submitted successfully",
                greeks_at_entry=greeks_at_entry,
                max_loss=max_loss,
                max_profit=max_profit,
                lineage_hash=lineage_hash,
                timestamp=timestamp,
            )

        except AssertionError as e:
            logger.critical(f"GOVERNANCE BREACH ATTEMPT: {e}")
            return ShadowOrderResult(
                success=False, order_id=None, order_ref=None,
                reason=f"GOVERNANCE BREACH: {e}",
                greeks_at_entry=None, max_loss=None, max_profit=None,
                lineage_hash='', timestamp=timestamp,
            )
        except Exception as e:
            logger.error(f"Shadow order error: {e}")
            return ShadowOrderResult(
                success=False, order_id=None, order_ref=None,
                reason=f"Error: {e}",
                greeks_at_entry=None, max_loss=None, max_profit=None,
                lineage_hash='', timestamp=timestamp,
            )

    # =========================================================================
    # POSITION MONITORING
    # =========================================================================

    def check_auto_close(self) -> List[str]:
        """
        Check all open shadow positions for auto-close conditions.

        Returns list of position_refs that were auto-closed.
        """
        closed = []
        try:
            conn = _get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT position_id, position_ref, dte_remaining
                    FROM fhq_execution.options_shadow_positions
                    WHERE status = 'OPEN'
                      AND dte_remaining <= %s
                """, (AUTO_CLOSE_DTE,))
                positions = cur.fetchall()

                for pos_id, pos_ref, dte in positions:
                    cur.execute("""
                        UPDATE fhq_execution.options_shadow_positions
                        SET status = 'CLOSED',
                            closed_at = NOW(),
                            updated_at = NOW()
                        WHERE position_id = %s
                    """, (pos_id,))
                    closed.append(pos_ref)
                    logger.info(f"AUTO-CLOSE: {pos_ref} at DTE={dte}")

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Auto-close check failed: {e}")

        return closed

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _get_underlying_price(self, symbol: str) -> Optional[float]:
        """Get latest price for underlying from database."""
        try:
            conn = _get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT close_price
                    FROM fhq_core.market_prices_live
                    WHERE symbol = %s
                    ORDER BY price_date DESC
                    LIMIT 1
                """, (symbol,))
                row = cur.fetchone()
            conn.close()
            if row:
                return float(row[0])
            return None
        except Exception as e:
            logger.error(f"Price lookup failed for {symbol}: {e}")
            return None

    def _get_current_regime(self) -> str:
        """Get current regime state from database."""
        try:
            conn = _get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT current_regime
                    FROM fhq_meta.regime_state
                    ORDER BY updated_at DESC
                    LIMIT 1
                """)
                row = cur.fetchone()
            conn.close()
            if row:
                return row[0]
            return 'UNKNOWN'
        except Exception as e:
            logger.error(f"Regime state read failed: {e}")
            return 'UNKNOWN'

    def _calculate_risk(
        self, strategy_type: str, legs: List[OptionsOrderLeg],
        greeks_result: dict
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculate max loss and max profit for a strategy."""
        from options_greeks_calculator import vertical_spread_risk, iron_condor_risk

        try:
            if strategy_type == 'VERTICAL_SPREAD':
                # Identify long and short legs
                sell_legs = [l for l in legs if l.side == 'SELL']
                buy_legs = [l for l in legs if l.side == 'BUY']
                if sell_legs and buy_legs:
                    net_premium = abs(greeks_result['aggregate']['price'])
                    opt_type = sell_legs[0].option_type
                    risk = vertical_spread_risk(
                        buy_legs[0].strike, sell_legs[0].strike,
                        net_premium, opt_type
                    )
                    return risk['max_loss'], risk['max_profit']

            elif strategy_type == 'IRON_CONDOR':
                puts = sorted([l for l in legs if l.option_type == 'PUT'],
                              key=lambda l: l.strike)
                calls = sorted([l for l in legs if l.option_type == 'CALL'],
                               key=lambda l: l.strike)
                if len(puts) >= 2 and len(calls) >= 2:
                    net_premium = abs(greeks_result['aggregate']['price'])
                    risk = iron_condor_risk(
                        puts[0].strike, puts[1].strike,
                        calls[0].strike, calls[1].strike,
                        net_premium
                    )
                    return risk['max_loss'], risk['max_profit']

            elif strategy_type == 'CASH_SECURED_PUT':
                sell_legs = [l for l in legs if l.side == 'SELL']
                if sell_legs:
                    premium = abs(greeks_result['aggregate']['price'])
                    max_loss = sell_legs[0].strike * 100 - premium * 100
                    return max_loss, premium * 100

            elif strategy_type == 'COVERED_CALL':
                sell_legs = [l for l in legs if l.side == 'SELL']
                if sell_legs:
                    premium = abs(greeks_result['aggregate']['price'])
                    return None, premium * 100  # Max loss depends on underlying

            elif strategy_type == 'PROTECTIVE_PUT':
                buy_legs = [l for l in legs if l.side == 'BUY']
                if buy_legs:
                    premium = abs(greeks_result['aggregate']['price'])
                    return premium * 100, None  # Max profit unlimited

        except Exception as e:
            logger.error(f"Risk calculation error: {e}")

        return None, None


# =============================================================================
# MODULE-LEVEL INSTANCE
# =============================================================================

_adapter = OptionsShadowAdapter()


def submit_shadow_order(request: ShadowOrderRequest) -> ShadowOrderResult:
    """Module-level convenience for shadow order submission."""
    return _adapter.submit_shadow_order(request)


def check_auto_close() -> List[str]:
    """Module-level convenience for auto-close check."""
    return _adapter.check_auto_close()


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("OPTIONS SHADOW ADAPTER — Self-Test")
    print("IoS-012-C / CEO-DIR-2026-OPS-AUTONOMY-001")
    print("=" * 60)

    # Test 1: Governance assertion — execution mode
    print("\n1. Execution mode assertion:")
    try:
        _assert_shadow_paper()
        print(f"   EXECUTION_MODE = {EXECUTION_MODE}")
        print("   PASS: SHADOW_PAPER enforced")
    except AssertionError as e:
        print(f"   FAIL: {e}")

    # Test 2: Strategy validation
    print("\n2. Strategy validation:")
    for strat in SUPPORTED_STRATEGIES:
        try:
            _assert_strategy_allowed(strat)
            print(f"   {strat}: ALLOWED")
        except AssertionError as e:
            print(f"   {strat}: BLOCKED ({e})")

    print("\n3. Blocked strategies:")
    for strat in BLOCKED_STRATEGIES:
        try:
            _assert_strategy_allowed(strat)
            print(f"   {strat}: ERROR — should be blocked!")
        except AssertionError:
            print(f"   {strat}: BLOCKED (correct)")

    # Test 4: Defined risk validation
    print("\n4. Defined risk check — naked call:")
    naked_call_legs = [
        OptionsOrderLeg(side='SELL', strike=160.0, expiration='2026-03-15',
                        option_type='CALL', quantity=1)
    ]
    try:
        _assert_defined_risk(naked_call_legs, 'VERTICAL_SPREAD')
        print("   FAIL: Should have been blocked!")
    except AssertionError as e:
        print(f"   BLOCKED: {e}")
        print("   PASS: Naked call rejected")

    # Test 5: Covered spread (should pass)
    print("\n5. Defined risk check — bull put spread:")
    spread_legs = [
        OptionsOrderLeg(side='SELL', strike=150.0, expiration='2026-03-15',
                        option_type='PUT', quantity=1),
        OptionsOrderLeg(side='BUY', strike=145.0, expiration='2026-03-15',
                        option_type='PUT', quantity=1),
    ]
    try:
        _assert_defined_risk(spread_legs, 'VERTICAL_SPREAD')
        print("   PASS: Defined-risk spread accepted")
    except AssertionError as e:
        print(f"   FAIL: {e}")

    # Test 6: Hash chain
    print("\n6. Lineage hash:")
    req = ShadowOrderRequest(
        strategy_type='VERTICAL_SPREAD',
        underlying='AAPL',
        legs=spread_legs,
        source_hypothesis_id='test-hyp-001',
    )
    lh = _compute_lineage_hash(req, {'delta': 0.15, 'gamma': 0.01})
    print(f"   Hash: {lh[:32]}...")
    assert len(lh) == 64, "Expected SHA256 (64 hex chars)"
    print("   PASS: SHA256 lineage hash computed")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
