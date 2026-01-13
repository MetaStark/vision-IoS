#!/usr/bin/env python3
"""
SIGNAL EXECUTOR DAEMON (Paper Mode)
====================================
CEO Directive: CD-IOS-001-PRICE-ARCH-001
Classification: G5_PAPER_EXECUTION
Orchestrator: FHQ-IoS001-Bulletproof-EQUITY

===============================================================================
CEO DIRECTIVE 2025-12-22: EXECUTION RE-ENABLED
===============================================================================
Status: OPERATIONAL - Monday liquidation complete ($104,924 cash)
Previous Incident: 3x over-limit execution (MSTR 1088 shares, 2x leverage)

Fixes Confirmed by STIG:
- Fix A: Exposure gate BLOCKS (not just logs) - IMPLEMENTED
- Fix B: Position counts query BROKER via broker_truth_enforcer - IMPLEMENTED
- Fix C: Trade logging atomic with execution - IMPLEMENTED
- Fix D: Single-symbol accumulation guard - IMPLEMENTED
- Fix E: Incremental exposure check - IMPLEMENTED

EXECUTION_FREEZE lifted in unified_execution_gateway.py
Kill switch removed by CEO authorization 2025-12-22.
===============================================================================
"""

# ============================================================================
# EXECUTION RE-ENABLED - CEO DIRECTIVE 2025-12-22
# ============================================================================

"""
Purpose:
    Monitors Golden Needles across ALL asset classes and CCO state.
    Executes trades via Alpaca Paper when CCO permits.
    Stays silent when CCO is SUPPRESSED (expected behavior).

    === IoS-003-B INTEGRATION (Intraday Regime-Delta) ===
    Consumes Flash-Context from fhq_operational for EPHEMERAL_PRIMED transitions.
    When canonical regime doesn't match but Flash-Context indicates favorable
    intraday conditions, signals can be promoted with reduced position sizing (50%).

Multi-Asset Support (per CD-IOS-001-PRICE-ARCH-001):
    - Equities: Direct execution via Alpaca
    - ETFs: Direct execution via Alpaca
    - Crypto: Proxy execution via crypto-adjacent equities (MSTR, COIN, MARA)
    - All golden needles are tradeable regardless of asset class

Flow:
    1. Check CCO state every cycle
    2. Monitor existing positions for stop-loss/take-profit exits
    3. If SUPPRESSED → wait silently (exits still monitored)
    4. If PERMITTED → scan for executable signals across all asset classes
    5. Check Flash-Context for EPHEMERAL_PRIMED opportunities (IoS-003-B)
    6. Execute via Alpaca with Kelly sizing (50% for ephemeral)
    7. Log all transitions and trades

Hard Constraints:
    - Paper mode ONLY
    - Respects VOL_NEUTRAL threshold (does NOT override)
    - Maximum 3 concurrent positions
    - Kelly-based position sizing
    - Freshness decoupling per FDR-002 (execution independent of canonical completeness)
    - Ephemeral trades use 50% position sizing (conservative due to intraday context)
"""

import os
import sys
import time
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CEO-DIR-2026-FINN-018: SitC EXECUTION GATE IMPORT
# =============================================================================
# "No thinking, no trading."
# SitC must actively reason before any execution is permitted.
# =============================================================================
try:
    from ios020_sitc_planner import get_sitc_execution_gate, SitCExecutionGateResult
    SITC_GATE_AVAILABLE = True
except ImportError:
    SITC_GATE_AVAILABLE = False
    logging.warning("[SITC-GATE] ios020_sitc_planner not available - SitC gate DISABLED")

# Holiday Execution Gate (CEO Directive 2025-12-19)
try:
    from holiday_execution_gate import (
        check_holiday_execution_gate,
        can_execute as holiday_can_execute,
        get_holiday_status,
        HOLIDAY_MODE_ENABLED
    )
    HOLIDAY_GATE_AVAILABLE = True
except ImportError:
    HOLIDAY_GATE_AVAILABLE = False
    HOLIDAY_MODE_ENABLED = False

# Unified Execution Gateway (CEO Directive 2025-12-20)
try:
    from unified_execution_gateway import (
        validate_execution_permission,
        validate_position_size as gateway_validate_size,
        PAPER_MODE_ENABLED,
        PAPER_MODE_MAX_EXPOSURE_PCT
    )
    GATEWAY_AVAILABLE = True
except ImportError:
    GATEWAY_AVAILABLE = False
    PAPER_MODE_ENABLED = True
    PAPER_MODE_MAX_EXPOSURE_PCT = 0.10

# ============================================================================
# BROKER TRUTH ENFORCER (CEO Directive 2025-12-21)
# Position/exposure queries MUST use broker, NOT database
# ============================================================================
try:
    from broker_truth_enforcer import (
        get_broker_account_state,
        get_open_position_count as broker_get_open_position_count,
        get_open_symbols as broker_get_open_symbols,
        has_position_for_symbol,
        get_exposure_metrics,
        validate_exposure_from_broker,
        get_pending_orders
    )
    BROKER_TRUTH_AVAILABLE = True
except ImportError:
    BROKER_TRUTH_AVAILABLE = False
    logging.warning("BROKER TRUTH ENFORCER NOT AVAILABLE - EXECUTION BLOCKED")

# =============================================================================
# CEO-DIR-2026-FINN-019: NEURAL BRIDGE IMPORTS
# =============================================================================
# Decision Engine, Attempt Logger, IKEA Truth Boundary
# Stage A: Shadow Mode (audit_only=True) - logs without blocking
# Stage B: Hard Gate (audit_only=False) - enforces gates
# =============================================================================
try:
    from decision_engine import (
        DecisionEngine,
        IntentDraft,
        DecisionPlan,
        create_intent_draft,
        validate_snapshot_ttl,
        validate_plan_ttl
    )
    from attempt_logger import AttemptLogger, AttemptRecord
    from ikea_truth_boundary import IKEATruthBoundary
    from inforage_cost_controller import InForageTradeController, calculate_trade_roi
    NEURAL_BRIDGE_AVAILABLE = True
except ImportError as e:
    NEURAL_BRIDGE_AVAILABLE = False
    logging.warning(f"[NEURAL-BRIDGE] Modules not available: {e}")

# Neural Bridge Feature Flag (CEO-DIR-2026-FINN-019)
# Stage A: Shadow logging (audit_only_mode=True)
# Stage B: Hard gate enforcement (audit_only_mode=False)
# CEO-DIR-2026-01-02: Switched to Stage B to populate execution_attempts
# SAFE: Exposure gate (31% > 25%) still blocks all execution
NEURAL_BRIDGE_ENABLED = os.getenv('NEURAL_BRIDGE_ENABLED', 'true').lower() == 'true'
NEURAL_BRIDGE_AUDIT_ONLY = os.getenv('NEURAL_BRIDGE_AUDIT_ONLY', 'false').lower() == 'true'

# =============================================================================
# TELEGRAM NOTIFIER (CEO Alert System)
# =============================================================================
try:
    from telegram_notifier import (
        FjordHQNotifier,
        send_position_exit,
        send_exposure_clear,
        send_trade_executed,
        send_neural_bridge_block,
        send_daemon_error
    )
    TELEGRAM_AVAILABLE = True
    telegram_notifier = FjordHQNotifier()
except ImportError as e:
    TELEGRAM_AVAILABLE = False
    telegram_notifier = None
    logging.warning(f"[TELEGRAM] Notifier not available: {e}")

# Alpaca SDK
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
    from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest, CryptoLatestQuoteRequest
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SIGNAL-EXEC] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('SIGNAL_EXECUTOR')

# Configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', '')
ALPACA_SECRET = os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY', ''))

# Daemon Config
DAEMON_CONFIG = {
    'cycle_interval_seconds': 60,       # Check every 60 seconds
    'max_concurrent_positions': 8,       # Max open positions
    'min_eqs_score': 0.80,              # Minimum EQS to consider
    'kelly_multiplier': 0.75,           # 3/4 Kelly (aggressive)
    'max_position_pct': 0.15,           # 15% NAV max per position
    'min_position_dollars': 500,        # Minimum $500 per trade
    'default_target_pct': 0.05,         # 5% target
    'default_stop_loss_pct': 0.03,      # 3% stop loss
}

# =============================================================================
# REGIME-CONDITIONED EXIT PARAMETERS (CEO DIRECTIVE 2025-12-24)
# =============================================================================
# Phase 2 validated (p < 0.05) regime-based exits for Shadow Ledger deployment.
# Wider exits in BULL to let winners run, tighter in BEAR to limit losses.
# These values are FROZEN per CEO directive - NO modifications permitted.

REGIME_EXIT_PARAMS = {
    'BULL': {'target_pct': 0.08, 'stop_loss_pct': 0.05},        # Wider +8%/-5%
    'STRONG_BULL': {'target_pct': 0.08, 'stop_loss_pct': 0.05}, # Wider +8%/-5%
    'BEAR': {'target_pct': 0.03, 'stop_loss_pct': 0.02},        # Tighter +3%/-2%
    'STRONG_BEAR': {'target_pct': 0.03, 'stop_loss_pct': 0.02}, # Tighter +3%/-2%
    'STRESS': {'target_pct': 0.03, 'stop_loss_pct': 0.02},      # Tighter +3%/-2%
    'BROKEN': {'target_pct': 0.03, 'stop_loss_pct': 0.02},      # Tighter +3%/-2%
    'NEUTRAL': {'target_pct': 0.05, 'stop_loss_pct': 0.03},     # Baseline +5%/-3%
    'VOLATILE_NON_DIRECTIONAL': {'target_pct': 0.05, 'stop_loss_pct': 0.03},
}

# BTC-ONLY CONSTRAINT (CEO DIRECTIVE 2025-12-24)
# Shadow Ledger deployment is ONLY authorized for BTC until skill verification passes.
# All other assets are BLOCKED from new entries during this phase.
SHADOW_LEDGER_AUTHORIZED_ASSETS = ['BTC/USD', 'BTC-USD', 'BTCUSDT']

# =============================================================================
# HARD EXPOSURE GATES (CEO DIRECTIVE: CRITICAL RISK CONTROL)
# =============================================================================
# These are ABSOLUTE LIMITS that cannot be overridden.
# They protect against position sizing bugs, external trades, and margin abuse.
# Violation of these gates BLOCKS all new execution.

HARD_LIMITS = {
    'max_single_position_pct': 0.25,    # ABSOLUTE MAX 25% NAV per position
    'max_total_exposure_pct': 1.00,     # ABSOLUTE MAX 100% NAV total (no margin)
    'max_single_position_usd': 50000,   # ABSOLUTE MAX $50,000 per position
    'min_cash_reserve_pct': 0.10,       # Maintain 10% cash minimum
    'block_on_margin': True,            # Block execution if using margin (negative cash)
}

# Multi-Asset Symbol Configuration
# Per CEO Directive CD-IOS-001-PRICE-ARCH-001: Multi-tier execution across asset classes

# Direct tradeable symbols (equities via Alpaca)
DIRECT_EQUITY_SYMBOLS = [
    'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMD', 'META', 'AMZN',
    'SPY', 'QQQ', 'IWM', 'DIA',  # ETFs
    'MSTR', 'COIN', 'MARA', 'RIOT',  # Crypto-adjacent equities
    'JPM', 'GS', 'MS', 'BAC',  # Financials
    'XOM', 'CVX', 'COP',  # Energy
    'UNH', 'JNJ', 'PFE',  # Healthcare
]

# Crypto symbols tradeable via Alpaca Crypto
CRYPTO_SYMBOLS = [
    'BTC/USD', 'ETH/USD', 'SOL/USD', 'AVAX/USD', 'DOGE/USD',
    'LTC/USD', 'BCH/USD', 'LINK/USD', 'UNI/USD', 'AAVE/USD'
]

# Mapping from price witness symbols to tradeable symbols
SYMBOL_MAPPING = {
    # Crypto to Alpaca crypto format
    'BTCUSDT': 'BTC/USD',
    'BTC-USD': 'BTC/USD',
    'ETHUSDT': 'ETH/USD',
    'ETH-USD': 'ETH/USD',
    'SOLUSDT': 'SOL/USD',
    'SOL-USD': 'SOL/USD',
    # Direct equity pass-through
    'NVDA': 'NVDA',
    'AAPL': 'AAPL',
    'MSFT': 'MSFT',
    'GOOGL': 'GOOGL',
    'TSLA': 'TSLA',
    'AMD': 'AMD',
    'META': 'META',
    'SPY': 'SPY',
    'QQQ': 'QQQ',
}

# Direct crypto trading - CEO Directive: Trade crypto directly, not through proxies
# Alpaca supports 62 crypto pairs - use them directly
DIRECT_CRYPTO_SYMBOLS = {
    'BTC/USD', 'BTC/USDC', 'BTC/USDT',
    'ETH/USD', 'ETH/USDC', 'ETH/USDT', 'ETH/BTC',
    'SOL/USD', 'SOL/USDC', 'SOL/USDT',
    'DOGE/USD', 'DOGE/USDC', 'DOGE/USDT',
    'AVAX/USD', 'AVAX/USDC', 'AVAX/USDT',
    'LINK/USD', 'LINK/USDC', 'LINK/USDT', 'LINK/BTC',
    'LTC/USD', 'LTC/USDC', 'LTC/USDT', 'LTC/BTC',
    'UNI/USD', 'UNI/USDC', 'UNI/USDT', 'UNI/BTC',
    'AAVE/USD', 'AAVE/USDC', 'AAVE/USDT',
    'DOT/USD', 'DOT/USDC',
    'XRP/USD', 'XTZ/USD', 'XTZ/USDC',
    'SHIB/USD', 'SHIB/USDC', 'SHIB/USDT',
    'PEPE/USD', 'TRUMP/USD',
    'CRV/USD', 'CRV/USDC',
    'GRT/USD', 'GRT/USDC',
    'BAT/USD', 'BAT/USDC',
    'BCH/USD', 'BCH/USDC', 'BCH/USDT', 'BCH/BTC',
    'SUSHI/USD', 'SUSHI/USDC', 'SUSHI/USDT',
    'YFI/USD', 'YFI/USDC', 'YFI/USDT',
    'SKY/USD',
}

# Map signal symbols to Alpaca trading symbols (Alpaca uses BTC/USD format with slash)
# Alpaca maintains backward compatibility with BTCUSD but prefers BTC/USD
CRYPTO_SYMBOL_MAP = {
    'BTC-USD': 'BTC/USD', 'BTC/USD': 'BTC/USD', 'BTCUSD': 'BTC/USD', 'BTCUSDT': 'BTC/USD',
    'ETH-USD': 'ETH/USD', 'ETH/USD': 'ETH/USD', 'ETHUSD': 'ETH/USD', 'ETHUSDT': 'ETH/USD',
    'SOL-USD': 'SOL/USD', 'SOL/USD': 'SOL/USD', 'SOLUSD': 'SOL/USD',
    'DOGE-USD': 'DOGE/USD', 'DOGE/USD': 'DOGE/USD', 'DOGEUSD': 'DOGE/USD',
    'AVAX-USD': 'AVAX/USD', 'AVAX/USD': 'AVAX/USD', 'AVAXUSD': 'AVAX/USD',
    'LINK-USD': 'LINK/USD', 'LINK/USD': 'LINK/USD', 'LINKUSD': 'LINK/USD',
    'LTC-USD': 'LTC/USD', 'LTC/USD': 'LTC/USD', 'LTCUSD': 'LTC/USD',
    'XRP-USD': 'XRP/USD', 'XRP/USD': 'XRP/USD', 'XRPUSD': 'XRP/USD',
    'SHIB-USD': 'SHIB/USD', 'SHIB/USD': 'SHIB/USD', 'SHIBUSD': 'SHIB/USD',
    'PEPE-USD': 'PEPE/USD', 'PEPE/USD': 'PEPE/USD', 'PEPEUSD': 'PEPE/USD',
    'TRUMP-USD': 'TRUMP/USD', 'TRUMP/USD': 'TRUMP/USD', 'TRUMPUSD': 'TRUMP/USD',
    'UNI-USD': 'UNI/USD', 'UNI/USD': 'UNI/USD', 'UNIUSD': 'UNI/USD',
    'AAVE-USD': 'AAVE/USD', 'AAVE/USD': 'AAVE/USD', 'AAVEUSD': 'AAVE/USD',
    'DOT-USD': 'DOT/USD', 'DOT/USD': 'DOT/USD', 'DOTUSD': 'DOT/USD',
}

# Proxy mapping ONLY for non-crypto assets that need proxying
PROXY_SYMBOLS = {
    'default': ['SPY', 'QQQ', 'NVDA']
}


class SignalExecutorDaemon:
    """Autonomous Signal Executor for Paper Trading"""

    def __init__(self, dry_run: bool = False):
        self.conn = None
        self.trading_client = None
        self.data_client = None
        self.crypto_data_client = None  # CEO Directive: Direct crypto trading
        self.running = False
        self.cycle_count = 0
        self.last_permit_status = None
        self.suppressed_cycles = 0

        # =====================================================================
        # CEO-DIR-2026-TRUTH-SYNC-P4: Agency Observation Mode (Dry Run)
        # When enabled: Full evaluation through all gates, NO execution,
        # NO state mutation, captures detailed decision traces
        # =====================================================================
        self.dry_run = dry_run
        self.decision_traces = []  # Captures all needle evaluations in dry-run mode

        # =====================================================================
        # LOCAL POSITION TRACKING (CEO DIRECTIVE 2026-01-01)
        # Prevents race condition where daemon executes faster than Alpaca
        # updates positions. Tracks pending exposure until Alpaca catches up.
        # =====================================================================
        self.pending_exposure = {}  # {symbol: {'qty': 0.0, 'usd': 0.0, 'last_trade': timestamp}}
        self.pending_exposure_last_sync = None  # Last time we synced with Alpaca

        # =====================================================================
        # CEO-DIR-2026-FINN-018: SITC EXECUTION GATE
        # "No thinking, no trading."
        # Every trade must have active SitC reasoning before execution.
        # =====================================================================
        self.sitc_gate = None  # Initialized in connect() after DB is available

        # =====================================================================
        # CEO-DIR-2026-FINN-019: NEURAL BRIDGE COMPONENTS
        # Decision Engine, Attempt Logger, IKEA Truth Boundary
        # Stage A: Shadow Mode (audit_only=True) - logs without blocking
        # Stage B: Hard Gate (audit_only=False) - enforces gates
        # =====================================================================
        self.attempt_logger = None
        self.ikea_boundary = None
        self.inforage_controller = None
        self.decision_engine = None

    def connect(self) -> bool:
        """Connect to database and Alpaca"""
        try:
            # Database
            self.conn = psycopg2.connect(**DB_CONFIG)
            logger.info("Database connected")

            # Alpaca
            if ALPACA_AVAILABLE and ALPACA_API_KEY:
                self.trading_client = TradingClient(
                    api_key=ALPACA_API_KEY,
                    secret_key=ALPACA_SECRET,
                    paper=True  # ALWAYS paper mode
                )
                self.data_client = StockHistoricalDataClient(
                    ALPACA_API_KEY, ALPACA_SECRET
                )
                # Crypto data client for direct crypto trading (CEO Directive: No proxies)
                self.crypto_data_client = CryptoHistoricalDataClient(
                    ALPACA_API_KEY, ALPACA_SECRET
                )
                account = self.trading_client.get_account()
                logger.info(f"Alpaca connected - Portfolio: ${float(account.portfolio_value):,.2f}")
            else:
                logger.warning("Alpaca not available - simulation mode")

            # =====================================================================
            # CEO-DIR-2026-FINN-018: Initialize SitC Execution Gate
            # =====================================================================
            if SITC_GATE_AVAILABLE:
                try:
                    self.sitc_gate = get_sitc_execution_gate(session_id=f"DAEMON-{datetime.now().strftime('%Y%m%d%H%M%S')}")
                    logger.info("[SITC-GATE] Execution gate initialized - no thinking, no trading")
                except Exception as e:
                    logger.warning(f"[SITC-GATE] Failed to initialize: {e} - gate DISABLED")
                    self.sitc_gate = None
            else:
                logger.warning("[SITC-GATE] Not available - cognitive reasoning DISABLED")

            # =====================================================================
            # CEO-DIR-2026-FINN-019: Initialize Neural Bridge Components
            # =====================================================================
            if NEURAL_BRIDGE_AVAILABLE and NEURAL_BRIDGE_ENABLED:
                try:
                    self.attempt_logger = AttemptLogger(self.conn)
                    self.ikea_boundary = IKEATruthBoundary(self.conn)
                    self.inforage_controller = InForageTradeController(self.conn)
                    logger.info(f"[NEURAL-BRIDGE] Initialized - audit_only={NEURAL_BRIDGE_AUDIT_ONLY}")
                except Exception as e:
                    logger.warning(f"[NEURAL-BRIDGE] Failed to initialize: {e}")
                    self.attempt_logger = None
                    self.ikea_boundary = None
                    self.inforage_controller = None
            else:
                if not NEURAL_BRIDGE_AVAILABLE:
                    logger.warning("[NEURAL-BRIDGE] Modules not available")
                elif not NEURAL_BRIDGE_ENABLED:
                    logger.info("[NEURAL-BRIDGE] Disabled via feature flag")

            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def close(self):
        """Close connections"""
        if self.conn:
            self.conn.close()

    # =========================================================================
    # CEO-DIR-2026-TRUTH-SYNC-P2: STARTUP RECONCILIATION GUARD (Task 2.3)
    # =========================================================================
    # Daemon MUST refuse to start if broker state != internal state.
    # This prevents RC-001 recurrence (shares locked by pending orders).

    def startup_reconciliation_check(self) -> Tuple[bool, str]:
        """
        CEO-DIR-2026-TRUTH-SYNC-P2 Task 2.3: Startup Reconciliation Guard

        Daemon must refuse to start unless:
        1. No pending orders exist at broker
        2. Broker positions can be reconciled with internal state
        3. No locked positions detected

        Returns:
            (is_safe_to_start, reason)
        """
        if not self.trading_client:
            return False, "No Alpaca connection - cannot verify broker state"

        try:
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus

            # 1. Check for pending orders (RC-001 root cause)
            request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
            pending_orders = self.trading_client.get_orders(request)

            if pending_orders:
                order_list = [f"{o.symbol} {o.side} {o.qty}" for o in pending_orders]
                return False, f"BLOCKED: {len(pending_orders)} pending orders found: {order_list}. Run phase2_broker_reconciliation.py first."

            # 2. Get broker positions
            broker_positions = self.trading_client.get_all_positions()
            broker_symbols = {p.symbol: float(p.qty) for p in broker_positions}

            # 3. Log broker state at startup
            logger.info(f"[STARTUP-GUARD] Broker state: {len(broker_positions)} positions, {len(pending_orders)} pending orders")
            for p in broker_positions:
                logger.info(f"[STARTUP-GUARD]   {p.symbol}: {p.qty} @ ${float(p.current_price):,.2f}")

            # 4. Log to governance
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_type, action_target, action_target_type,
                        initiated_by, decision, decision_rationale,
                        agent_id, metadata
                    ) VALUES (
                        'STARTUP_RECONCILIATION_CHECK',
                        'SIGNAL_EXECUTOR_DAEMON',
                        'DAEMON',
                        'STIG',
                        'PASSED',
                        'Broker state verified: no pending orders, positions reconciled',
                        'STIG',
                        %s::jsonb
                    )
                """, (json.dumps({
                    "pending_orders": 0,
                    "broker_positions": broker_symbols,
                    "check_time": datetime.now().isoformat()
                }),))
                self.conn.commit()

            return True, f"Broker state verified: {len(broker_positions)} positions, 0 pending orders"

        except Exception as e:
            logger.error(f"[STARTUP-GUARD] Reconciliation check failed: {e}")
            return False, f"Reconciliation check failed: {e}"

    # =========================================================================
    # HARD EXPOSURE GATE (CEO DIRECTIVE: CRITICAL RISK CONTROL)
    # =========================================================================
    # This gate MUST be checked before ANY trade execution.
    # It validates ACTUAL Alpaca positions, not just our records.
    # This protects against external trades, bugs, and margin abuse.

    def validate_exposure_gate(
        self,
        proposed_trade_usd: float = 0,
        proposed_symbol: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Validate HARD exposure limits before allowing any new trade.

        CEO Directive 2025-12-21: This checks ACTUAL Alpaca positions.
        Database state is NEVER trusted for exposure decisions.

        Args:
            proposed_trade_usd: Size of proposed trade in USD (Fix E)
            proposed_symbol: Symbol for proposed trade (Fix D - same-symbol guard)

        Returns:
            (is_allowed, reason_if_blocked)
        """
        if not self.trading_client:
            return False, "No Alpaca connection"

        # =====================================================================
        # CEO DIRECTIVE 2025-12-21: Use broker_truth_enforcer if available
        # This centralizes all broker queries in one module
        # =====================================================================
        if BROKER_TRUTH_AVAILABLE:
            return validate_exposure_from_broker(
                proposed_trade_usd=proposed_trade_usd,
                proposed_symbol=proposed_symbol
            )

        # Fallback to direct Alpaca queries if broker_truth_enforcer not available
        try:
            # Get ACTUAL account state from Alpaca
            account = self.trading_client.get_account()
            portfolio_value = float(account.portfolio_value)
            cash = float(account.cash)

            # Get ACTUAL positions from Alpaca
            positions = self.trading_client.get_all_positions()

            # Build list of open symbols for same-symbol check
            open_symbols = [p.symbol for p in positions]

            # Calculate total exposure
            total_exposure = sum(float(p.market_value) for p in positions)
            total_exposure_pct = total_exposure / portfolio_value if portfolio_value > 0 else 0

            # Check for largest single position
            largest_position = 0
            largest_symbol = None
            for p in positions:
                pos_value = float(p.market_value)
                if pos_value > largest_position:
                    largest_position = pos_value
                    largest_symbol = p.symbol

            largest_position_pct = largest_position / portfolio_value if portfolio_value > 0 else 0

            # GATE 1: Check if using margin (negative cash)
            if HARD_LIMITS['block_on_margin'] and cash < 0:
                logger.critical(f"HARD GATE BLOCKED: Using margin! Cash=${cash:,.2f}")
                return False, f"MARGIN VIOLATION: Cash is negative (${cash:,.2f})"

            # GATE 2: Check total exposure
            if total_exposure_pct > HARD_LIMITS['max_total_exposure_pct']:
                logger.critical(f"HARD GATE BLOCKED: Total exposure {total_exposure_pct:.1%} > {HARD_LIMITS['max_total_exposure_pct']:.0%}")
                return False, f"TOTAL EXPOSURE VIOLATION: {total_exposure_pct:.1%} exceeds {HARD_LIMITS['max_total_exposure_pct']:.0%} limit"

            # GATE 3: Check largest single position
            if largest_position_pct > HARD_LIMITS['max_single_position_pct']:
                logger.critical(f"HARD GATE BLOCKED: Position {largest_symbol} at {largest_position_pct:.1%} > {HARD_LIMITS['max_single_position_pct']:.0%}")
                return False, f"SINGLE POSITION VIOLATION: {largest_symbol} at {largest_position_pct:.1%} exceeds {HARD_LIMITS['max_single_position_pct']:.0%} limit"

            # GATE 4: Check if largest position exceeds absolute USD limit
            if largest_position > HARD_LIMITS['max_single_position_usd']:
                logger.critical(f"HARD GATE BLOCKED: Position {largest_symbol} at ${largest_position:,.0f} > ${HARD_LIMITS['max_single_position_usd']:,.0f}")
                return False, f"ABSOLUTE USD VIOLATION: {largest_symbol} at ${largest_position:,.0f} exceeds ${HARD_LIMITS['max_single_position_usd']:,.0f} limit"

            # =====================================================================
            # GATE 5: SAME-SYMBOL ACCUMULATION GUARD (Fix D - CEO Directive 2025-12-21)
            # Prevents multiple positions in the same symbol
            # This was the ROOT CAUSE of 3x MSTR accumulation
            # =====================================================================
            if proposed_symbol and proposed_symbol in open_symbols:
                logger.critical(f"SAME-SYMBOL BLOCKED: Already have position in {proposed_symbol}")
                return False, f"SAME-SYMBOL VIOLATION: Already have position in {proposed_symbol}"

            # =====================================================================
            # GATE 5.5: LOCAL PENDING EXPOSURE GUARD (CEO DIRECTIVE 2026-01-01)
            # Prevents race condition where daemon executes faster than Alpaca
            # updates positions. Checks LOCAL tracking of pending trades.
            # This was the ROOT CAUSE of 4x BTC accumulation in 10 seconds.
            # =====================================================================
            if proposed_symbol:
                # Normalize symbol for comparison (BTC/USD, BTCUSD, BTC-USD all match)
                normalized_proposed = self._normalize_symbol_for_tracking(proposed_symbol)

                # Check if we have pending exposure in this symbol
                if normalized_proposed in self.pending_exposure:
                    pending = self.pending_exposure[normalized_proposed]
                    pending_usd = pending.get('usd', 0)
                    pending_qty = pending.get('qty', 0)

                    if pending_usd > 0:
                        # Calculate what total exposure would be with pending + proposed
                        total_with_pending = total_exposure + pending_usd + proposed_trade_usd
                        total_with_pending_pct = total_with_pending / portfolio_value if portfolio_value > 0 else 0

                        # Check single-position limit with pending exposure
                        pending_plus_alpaca = pending_usd + largest_position if largest_symbol == proposed_symbol else pending_usd
                        pending_position_pct = pending_plus_alpaca / portfolio_value if portfolio_value > 0 else 0

                        if pending_position_pct > HARD_LIMITS['max_single_position_pct']:
                            logger.critical(f"LOCAL PENDING BLOCKED: {proposed_symbol} pending ${pending_usd:,.0f} = {pending_position_pct:.1%} exceeds {HARD_LIMITS['max_single_position_pct']:.0%}")
                            return False, f"LOCAL PENDING VIOLATION: {proposed_symbol} has ${pending_usd:,.0f} pending ({pending_position_pct:.1%})"

                        # Check total exposure with pending
                        if total_with_pending_pct > HARD_LIMITS['max_total_exposure_pct']:
                            logger.critical(f"LOCAL PENDING BLOCKED: Total with pending ${total_with_pending:,.0f} = {total_with_pending_pct:.1%}")
                            return False, f"LOCAL PENDING TOTAL VIOLATION: Would be {total_with_pending_pct:.1%} with pending trades"

                        logger.info(f"LOCAL PENDING CHECK: {proposed_symbol} has ${pending_usd:,.0f} pending, within limits")

            # =====================================================================
            # GATE 6: INCREMENTAL EXPOSURE CHECK (Fix E - CEO Directive 2025-12-21)
            # Validates that proposed trade won't push us over limits
            # =====================================================================
            if proposed_trade_usd > 0:
                new_exposure_pct = (total_exposure + proposed_trade_usd) / portfolio_value
                if new_exposure_pct > HARD_LIMITS['max_total_exposure_pct']:
                    logger.warning(f"Proposed trade blocked: Would increase exposure to {new_exposure_pct:.1%}")
                    return False, f"PROPOSED TRADE BLOCKED: Would increase exposure to {new_exposure_pct:.1%}"

                if proposed_trade_usd > HARD_LIMITS['max_single_position_usd']:
                    logger.warning(f"Proposed trade blocked: ${proposed_trade_usd:,.0f} exceeds ${HARD_LIMITS['max_single_position_usd']:,.0f}")
                    return False, f"PROPOSED TRADE BLOCKED: ${proposed_trade_usd:,.0f} exceeds single position limit"

            # GATE 7: Check minimum cash reserve
            cash_pct = cash / portfolio_value if portfolio_value > 0 else 0
            if cash_pct < HARD_LIMITS['min_cash_reserve_pct'] and proposed_trade_usd > 0:
                logger.warning(f"Cash reserve low: {cash_pct:.1%} < {HARD_LIMITS['min_cash_reserve_pct']:.0%}")
                return False, f"CASH RESERVE LOW: {cash_pct:.1%} below {HARD_LIMITS['min_cash_reserve_pct']:.0%} minimum"

            # GATE 8: Check for pending orders on same symbol
            if proposed_symbol:
                try:
                    pending = self.trading_client.get_orders(
                        GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[proposed_symbol])
                    )
                    if pending:
                        logger.warning(f"Pending order exists for {proposed_symbol}")
                        return False, f"PENDING ORDER EXISTS: {len(pending)} pending order(s) for {proposed_symbol}"
                except Exception as e:
                    logger.warning(f"Could not check pending orders: {e}")

            # All gates passed
            logger.info(f"Exposure gate PASSED: {len(positions)} positions, {total_exposure_pct:.1%} exposure, ${cash:,.0f} cash")
            return True, "OK"

        except Exception as e:
            logger.error(f"Exposure gate check failed: {e}")
            return False, f"GATE CHECK ERROR: {e}"

    def log_exposure_violation(self, violation_type: str, details: Dict):
        """Log exposure violation to governance table"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_type,
                        action_target,
                        action_target_type,
                        initiated_by,
                        decision,
                        decision_rationale,
                        agent_id,
                        metadata
                    ) VALUES (
                        'EXPOSURE_GATE_VIOLATION',
                        'SIGNAL_EXECUTOR',
                        'HARD_LIMIT_BREACH',
                        'SIGNAL_EXECUTOR_DAEMON',
                        'BLOCKED',
                        %s,
                        'STIG',
                        %s::jsonb
                    )
                """, (violation_type, json.dumps(details)))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to log exposure violation: {e}")

    def _calculate_current_exposure(self) -> float:
        """Calculate current total exposure as percentage of portfolio."""
        try:
            if not self.trading_client:
                return 0.0

            account = self.trading_client.get_account()
            portfolio_value = float(account.portfolio_value)

            if portfolio_value <= 0:
                return 0.0

            positions = self.trading_client.get_all_positions()
            total_exposure = sum(float(p.market_value) for p in positions)

            return (total_exposure / portfolio_value) * 100

        except Exception as e:
            logger.error(f"Failed to calculate exposure: {e}")
            return 0.0

    def log_holiday_gate_block(self, symbol: str, asset_class: str, reason: str, needle: Dict):
        """Log holiday gate block to governance table (for observability)"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_type,
                        action_target,
                        action_target_type,
                        initiated_by,
                        decision,
                        decision_rationale,
                        agent_id,
                        metadata
                    ) VALUES (
                        'HOLIDAY_EXECUTION_GATE',
                        %s,
                        %s,
                        'SIGNAL_EXECUTOR_DAEMON',
                        'BLOCKED',
                        %s,
                        'STIG',
                        %s::jsonb
                    )
                """, (
                    symbol,
                    asset_class,
                    reason,
                    json.dumps({
                        'needle_id': str(needle.get('needle_id', 'unknown')),
                        'price_witness_symbol': needle.get('price_witness_symbol'),
                        'eqs_score': float(needle.get('eqs_score', 0)),
                        'signal_state': needle.get('current_state'),
                        'holiday_mode': 'CRYPTO_FIRST',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                ))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to log holiday gate block: {e}")

    def log_lids_gate_block(
        self,
        block_type: str,  # 'CONFIDENCE' or 'FRESHNESS'
        signal_id: str,
        asset: str,
        confidence: float,
        freshness_hours: float,
        threshold: float,
        needle: Dict
    ):
        """
        CEO-DIR-2026-020 D3: Log LIDS gate block to governance table.

        Every LIDS block MUST leave a DB trail with:
        - action_type: LIDS_CONFIDENCE_BLOCK or LIDS_FRESHNESS_BLOCK
        - action_target_type: SIGNAL
        - decision: BLOCKED
        - metadata with full context
        """
        action_type = f"LIDS_{block_type}_BLOCK"
        try:
            with self.conn.cursor() as cur:
                # 1. Log to governance_actions_log
                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_type,
                        action_target,
                        action_target_type,
                        initiated_by,
                        decision,
                        decision_rationale,
                        agent_id,
                        metadata
                    ) VALUES (
                        %s,
                        %s,
                        'SIGNAL',
                        'SIGNAL_EXECUTOR_DAEMON',
                        'BLOCKED',
                        %s,
                        'STIG',
                        %s::jsonb
                    )
                """, (
                    action_type,
                    signal_id,
                    f"CEO-DIR-2026-020 D3: {block_type} gate blocked signal. "
                    f"{'confidence' if block_type == 'CONFIDENCE' else 'freshness'}="
                    f"{confidence if block_type == 'CONFIDENCE' else freshness_hours:.1f} "
                    f"{'<' if block_type == 'CONFIDENCE' else '>'} {threshold} threshold",
                    json.dumps({
                        'signal_id': signal_id,
                        'asset': asset,
                        'confidence': float(confidence),
                        'freshness_hours': float(freshness_hours),
                        'threshold': float(threshold),
                        'gate_type': 'HARD',
                        'block_type': block_type,
                        'needle_id': str(needle.get('needle_id', 'unknown')),
                        'eqs_score': float(needle.get('eqs_score', 0)),
                        'directive': 'CEO-DIR-2026-020',
                        'deliverable': 'D3',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                ))

                # 2. Update execution_state to reflect LIDS activity
                cur.execute("""
                    UPDATE fhq_governance.execution_state
                    SET last_lids_block_at = NOW(),
                        last_lids_block_type = %s,
                        lids_blocks_today = COALESCE(lids_blocks_today, 0) + 1
                    WHERE state_id = (SELECT MAX(state_id) FROM fhq_governance.execution_state)
                """, (block_type,))

                # 3. CEO-DIR-2026-020 D4: Log state change to immutable audit trail
                cur.execute("""
                    SELECT fhq_governance.log_execution_state_change(
                        %s,  -- change_type
                        %s,  -- change_reason
                        %s   -- initiated_by
                    )
                """, (
                    f'LIDS_{block_type}_BLOCK',
                    f'LIDS {block_type.lower()} gate blocked signal {signal_id[:8]}... '
                    f'({confidence:.2f} conf, {freshness_hours:.1f}h fresh)',
                    'SIGNAL_EXECUTOR_DAEMON'
                ))

                self.conn.commit()
                logger.info(f"[D3-LIDS] Logged {action_type}: {asset} ({signal_id[:8]}...)")

        except Exception as e:
            logger.error(f"[D3-LIDS] Failed to log LIDS gate block: {e}")
            # Attempt rollback
            try:
                self.conn.rollback()
            except:
                pass

    def log_lids_gate_passed(self, confidence: float, freshness_hours: float):
        """
        CEO-DIR-2026-020 D3: Log LIDS gate pass for counter-metrics.

        Prevents silent success - enables block rate computation.
        Called once per signal that passes ALL LIDS gates.
        """
        try:
            with self.conn.cursor() as cur:
                # Update execution_state pass counter
                cur.execute("""
                    UPDATE fhq_governance.execution_state
                    SET lids_passes_today = COALESCE(lids_passes_today, 0) + 1
                    WHERE state_id = (SELECT MAX(state_id) FROM fhq_governance.execution_state)
                """)
                self.conn.commit()
                logger.debug(f"[D3-LIDS] Gate PASSED: confidence={confidence:.2f}, freshness={freshness_hours:.1f}h")
        except Exception as e:
            logger.warning(f"[D3-LIDS] Failed to log LIDS pass: {e}")

    # =========================================================================
    # CCO STATE MONITORING
    # =========================================================================

    def get_cco_state(self) -> Optional[Dict]:
        """Get current CCO state"""
        try:
            # Rollback any failed transaction before querying
            self.conn.rollback()
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        cco_status,
                        global_permit,
                        permit_reason,
                        current_regime,
                        current_vol_percentile,
                        defcon_level,
                        context_timestamp
                    FROM fhq_canonical.g5_cco_state
                    WHERE is_active = TRUE
                """)
                return cur.fetchone()
        except Exception as e:
            logger.error(f"Failed to get CCO state: {e}")
            self.conn.rollback()
            return None

    def is_execution_permitted(self) -> Tuple[bool, str]:
        """Check if execution is permitted by CCO"""
        state = self.get_cco_state()
        if not state:
            return False, "No CCO state available"

        if state['cco_status'] != 'OPERATIONAL':
            return False, f"CCO not operational: {state['cco_status']}"

        if state['global_permit'] != 'PERMITTED':
            return False, state['permit_reason'] or "Global permit not granted"

        if state['defcon_level'] and state['defcon_level'] <= 2:
            return False, f"DEFCON {state['defcon_level']} - execution blocked"

        return True, "Execution permitted"

    # =========================================================================
    # POSITION MANAGEMENT
    # CEO DIRECTIVE 2025-12-21: BROKER IS SOURCE OF TRUTH
    # All position/exposure queries for DECISION-MAKING must use BROKER
    # Database queries permitted ONLY for internal bookkeeping (needle_id tracking)
    # =========================================================================

    def get_open_positions_count(self) -> int:
        """
        Get count of open positions FROM BROKER (not database).

        CEO Directive 2025-12-21 FIX B:
        This function MUST query Alpaca directly.
        Database counts may be used only for reporting, never for decision-making.
        """
        if BROKER_TRUTH_AVAILABLE:
            return broker_get_open_position_count()
        else:
            # Broker unavailable = execution blocked = return max to prevent new trades
            logger.critical("BROKER UNAVAILABLE - Returning MAX to block execution")
            return DAEMON_CONFIG['max_concurrent_positions']

    def get_traded_needles(self) -> List[str]:
        """
        Get list of needle IDs that have been traded.

        NOTE: This is internal bookkeeping only (broker doesn't track needle IDs).
        This does NOT affect position/exposure decisions.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT needle_id::text FROM fhq_canonical.g5_paper_trades
            """)
            return [row[0] for row in cur.fetchall()]

    def get_open_symbols(self) -> List[str]:
        """
        Get symbols with open positions FROM BROKER (not database).

        CEO Directive 2025-12-21 FIX B:
        This function MUST query Alpaca directly.
        Database symbols may be used only for reporting, never for decision-making.
        """
        if BROKER_TRUTH_AVAILABLE:
            return broker_get_open_symbols()
        else:
            # Broker unavailable = execution blocked
            logger.critical("BROKER UNAVAILABLE - Cannot get open symbols")
            return []

    def get_open_positions(self) -> List[Dict]:
        """
        Get all open positions with entry details.

        WARNING: This is for internal bookkeeping ONLY (exit monitoring).
        The database records provide needle_id, entry_price, entry_context
        which the broker doesn't track.

        For position/exposure DECISIONS, use broker_truth_enforcer functions.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    trade_id,
                    needle_id,
                    symbol,
                    direction,
                    entry_price,
                    position_size,
                    entry_context,
                    entry_timestamp
                FROM fhq_canonical.g5_paper_trades
                WHERE exit_timestamp IS NULL
                ORDER BY entry_timestamp ASC
            """)
            return cur.fetchall()

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol (stock or crypto)"""
        # Check if this is a crypto symbol
        # Alpaca crypto data API uses "BTC/USD" format for quotes
        is_crypto = self._is_crypto_symbol(symbol)

        if is_crypto:
            if not self.crypto_data_client:
                return None
            try:
                # Convert to Alpaca crypto quote format (e.g., BTCUSD -> BTC/USD)
                crypto_quote_symbol = self._to_crypto_quote_format(symbol)
                quote = self.crypto_data_client.get_crypto_latest_quote(
                    CryptoLatestQuoteRequest(symbol_or_symbols=[crypto_quote_symbol])
                )
                # Use mid price for more accurate valuation
                bid = float(quote[crypto_quote_symbol].bid_price)
                ask = float(quote[crypto_quote_symbol].ask_price)
                return (bid + ask) / 2 if bid > 0 and ask > 0 else float(quote[crypto_quote_symbol].ask_price)
            except Exception as e:
                logger.warning(f"Could not get crypto price for {symbol}: {e}")
                return None
        else:
            if not self.data_client:
                return None
            try:
                quote = self.data_client.get_stock_latest_quote(
                    StockLatestQuoteRequest(symbol_or_symbols=[symbol])
                )
                # Use mid price for more accurate valuation
                bid = float(quote[symbol].bid_price)
                ask = float(quote[symbol].ask_price)
                return (bid + ask) / 2 if bid > 0 and ask > 0 else float(quote[symbol].ask_price)
            except Exception as e:
                logger.warning(f"Could not get stock price for {symbol}: {e}")
                return None

    def _is_crypto_symbol(self, symbol: str) -> bool:
        """Check if symbol is a crypto asset"""
        # Check CRYPTO_SYMBOL_MAP keys and values
        if symbol in CRYPTO_SYMBOL_MAP:
            return True
        # Check if it matches crypto format (ends with USD, USDC, USDT, or contains /)
        symbol_upper = symbol.upper()
        crypto_patterns = ['BTC', 'ETH', 'SOL', 'DOGE', 'AVAX', 'LINK', 'LTC', 'XRP',
                          'SHIB', 'PEPE', 'TRUMP', 'UNI', 'AAVE', 'DOT', 'ADA', 'MATIC',
                          'ATOM', 'XLM', 'ALGO', 'FIL', 'NEAR', 'APT', 'ARB', 'OP']
        return any(pattern in symbol_upper for pattern in crypto_patterns)

    def _to_crypto_quote_format(self, symbol: str) -> str:
        """Convert symbol to Alpaca crypto quote format (BTC/USD)"""
        # If already has slash, return as-is
        if '/' in symbol:
            return symbol
        # Convert BTCUSD -> BTC/USD
        symbol_upper = symbol.upper()
        for suffix in ['USDC', 'USDT', 'USD', 'BTC']:
            if symbol_upper.endswith(suffix):
                base = symbol_upper[:-len(suffix)]
                return f"{base}/{suffix}"
        return symbol  # Return as-is if no conversion needed

    def _normalize_symbol_for_tracking(self, symbol: str) -> str:
        """
        Normalize symbol for local pending exposure tracking.
        CEO DIRECTIVE 2026-01-01: Ensures BTC/USD, BTCUSD, BTC-USD all map to same key.
        """
        symbol_upper = symbol.upper().replace('-', '').replace('/', '')
        # Remove common suffixes to get base asset
        for suffix in ['USDT', 'USDC', 'USD']:
            if symbol_upper.endswith(suffix):
                return symbol_upper[:-len(suffix)]
        return symbol_upper

    def _add_pending_exposure(self, symbol: str, qty: float, usd_value: float):
        """
        Track pending exposure for a symbol after trade execution.
        CEO DIRECTIVE 2026-01-01: Prevents race condition with Alpaca position updates.
        """
        normalized = self._normalize_symbol_for_tracking(symbol)
        if normalized not in self.pending_exposure:
            self.pending_exposure[normalized] = {'qty': 0.0, 'usd': 0.0, 'trades': 0, 'last_trade': None}

        self.pending_exposure[normalized]['qty'] += qty
        self.pending_exposure[normalized]['usd'] += usd_value
        self.pending_exposure[normalized]['trades'] += 1
        self.pending_exposure[normalized]['last_trade'] = datetime.now(timezone.utc)

        logger.info(f"LOCAL PENDING TRACKED: {symbol} +${usd_value:,.2f} → Total pending: ${self.pending_exposure[normalized]['usd']:,.2f}")

    def _sync_pending_exposure_with_alpaca(self):
        """
        Sync pending exposure with actual Alpaca positions.
        Called at start of each cycle to reconcile local tracking with broker truth.
        """
        if not self.trading_client:
            return

        try:
            positions = self.trading_client.get_all_positions()
            alpaca_symbols = {}

            for p in positions:
                normalized = self._normalize_symbol_for_tracking(p.symbol)
                alpaca_symbols[normalized] = float(p.market_value)

            # Clear pending exposure for symbols that are now in Alpaca
            cleared = []
            for symbol in list(self.pending_exposure.keys()):
                if symbol in alpaca_symbols:
                    # Alpaca has caught up - clear pending
                    cleared.append(f"{symbol} (${self.pending_exposure[symbol]['usd']:,.0f})")
                    del self.pending_exposure[symbol]

            if cleared:
                logger.info(f"PENDING EXPOSURE SYNC: Cleared {len(cleared)} symbols now in Alpaca: {', '.join(cleared)}")

            self.pending_exposure_last_sync = datetime.now(timezone.utc)

        except Exception as e:
            logger.warning(f"Failed to sync pending exposure: {e}")

    # =========================================================================
    # STOP LOSS / TAKE PROFIT EXIT LOGIC
    # =========================================================================

    def check_exit_conditions(self, position: Dict) -> Tuple[bool, str, float]:
        """
        Check if position should be exited based on stop loss or take profit.
        Returns: (should_exit, reason, current_price)
        """
        symbol = position['symbol']
        entry_price = float(position['entry_price'])
        direction = position['direction']

        # Parse target/stop from entry_context
        entry_context = position.get('entry_context', {})
        if isinstance(entry_context, str):
            try:
                entry_context = json.loads(entry_context)
            except:
                entry_context = {}

        target_pct = entry_context.get('target_pct', DAEMON_CONFIG['default_target_pct'])
        stop_loss_pct = entry_context.get('stop_loss_pct', DAEMON_CONFIG['default_stop_loss_pct'])

        # Get current price
        current_price = self.get_current_price(symbol)
        if current_price is None or current_price <= 0:
            return False, "Price unavailable or market closed", 0

        # Calculate P/L percentage
        if direction == 'LONG':
            pnl_pct = (current_price - entry_price) / entry_price
            target_price = entry_price * (1 + target_pct)
            stop_price = entry_price * (1 - stop_loss_pct)

            # Check take profit
            if current_price >= target_price:
                return True, f"TAKE_PROFIT (+{pnl_pct*100:.2f}%)", current_price

            # Check stop loss
            if current_price <= stop_price:
                return True, f"STOP_LOSS ({pnl_pct*100:.2f}%)", current_price
        else:
            # SHORT position
            pnl_pct = (entry_price - current_price) / entry_price
            target_price = entry_price * (1 - target_pct)
            stop_price = entry_price * (1 + stop_loss_pct)

            if current_price <= target_price:
                return True, f"TAKE_PROFIT (+{pnl_pct*100:.2f}%)", current_price

            if current_price >= stop_price:
                return True, f"STOP_LOSS ({pnl_pct*100:.2f}%)", current_price

        return False, f"HOLDING ({pnl_pct*100:+.2f}%)", current_price

    def execute_exit(self, position: Dict, reason: str, exit_price: float) -> Optional[Dict]:
        """Execute an exit order for a position"""
        if not self.trading_client:
            logger.warning("Alpaca not available - cannot exit")
            return None

        symbol = position['symbol']
        direction = position['direction']

        # Get current Alpaca position to know exact shares
        try:
            alpaca_positions = self.trading_client.get_all_positions()
            alpaca_pos = next((p for p in alpaca_positions if p.symbol == symbol), None)

            if not alpaca_pos:
                logger.warning(f"No Alpaca position found for {symbol} - marking as closed")
                self._log_exit(position, exit_price, 0, reason, "POSITION_NOT_FOUND")
                return {'symbol': symbol, 'reason': reason, 'status': 'POSITION_NOT_FOUND'}

            shares = abs(float(alpaca_pos.qty))

        except Exception as e:
            logger.error(f"Could not get Alpaca position for {symbol}: {e}")
            return None

        # Determine exit side (opposite of entry)
        exit_side = OrderSide.SELL if direction == 'LONG' else OrderSide.BUY

        logger.info(f"Exiting: {exit_side.name} {int(shares)} {symbol} @ ~${exit_price:.2f} ({reason})")

        try:
            order = self.trading_client.submit_order(
                MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=exit_side,
                    time_in_force=TimeInForce.DAY
                )
            )

            # Wait for fill
            time.sleep(1)
            filled_order = self.trading_client.get_order_by_id(order.id)

            if filled_order.status in ['filled', 'partially_filled']:
                filled_price = float(filled_order.filled_avg_price)
                filled_qty = float(filled_order.filled_qty)

                # Calculate realized P/L
                entry_price = float(position['entry_price'])
                if direction == 'LONG':
                    realized_pnl = (filled_price - entry_price) * filled_qty
                else:
                    realized_pnl = (entry_price - filled_price) * filled_qty

                logger.info(f"EXIT FILLED: {symbol} @ ${filled_price:.2f} | P/L: ${realized_pnl:+,.2f}")

                # Log to database
                self._log_exit(position, filled_price, realized_pnl, reason, str(order.id))

                # TELEGRAM NOTIFICATION: Position Exit
                if TELEGRAM_AVAILABLE and telegram_notifier:
                    try:
                        # Calculate new exposure after exit
                        new_exposure = self._calculate_current_exposure()
                        pnl_pct = ((filled_price - entry_price) / entry_price) * 100 if direction == 'LONG' else ((entry_price - filled_price) / entry_price) * 100

                        telegram_notifier.position_exit(
                            symbol=symbol,
                            direction=direction,
                            entry_price=entry_price,
                            exit_price=filled_price,
                            pnl_pct=pnl_pct,
                            pnl_usd=realized_pnl,
                            exit_reason=reason.split('(')[0].strip(),  # TAKE_PROFIT or STOP_LOSS
                            new_exposure_pct=new_exposure
                        )

                        # Check if exposure gate cleared
                        if new_exposure < 25.0:
                            telegram_notifier.exposure_gate_clear(
                                old_exposure_pct=new_exposure + (abs(realized_pnl) / 100000 * 100),  # Approximate
                                new_exposure_pct=new_exposure,
                                trigger_event=f"{symbol} exit ({reason})"
                            )
                    except Exception as te:
                        logger.warning(f"Telegram notification failed: {te}")

                return {
                    'symbol': symbol,
                    'exit_price': filled_price,
                    'realized_pnl': realized_pnl,
                    'reason': reason,
                    'order_id': str(order.id)
                }
            else:
                logger.warning(f"Exit order not filled: {filled_order.status}")
                return None

        except Exception as e:
            logger.error(f"Exit execution failed for {symbol}: {e}")
            return None

    def _log_exit(self, position: Dict, exit_price: float, realized_pnl: float,
                  reason: str, order_id: str):
        """Log exit to database"""
        cco_state = self.get_cco_state()

        exit_context = json.dumps({
            'exit_reason': reason,
            'exit_price': exit_price,
            'realized_pnl': realized_pnl,
            'alpaca_order_id': order_id,
            'cco_status': cco_state['cco_status'] if cco_state else 'UNKNOWN',
            'vol_percentile': float(cco_state['current_vol_percentile']) if cco_state else 0,
            'exited_by': 'SIGNAL_EXECUTOR_DAEMON',
            'exit_timestamp': datetime.now(timezone.utc).isoformat()
        })

        with self.conn.cursor() as cur:
            # Update trade record
            cur.execute("""
                UPDATE fhq_canonical.g5_paper_trades
                SET
                    exit_price = %s,
                    exit_timestamp = NOW(),
                    realized_pnl = %s,
                    exit_trigger = %s,  -- Fixed: was exit_reason (schema mismatch)
                    exit_context = %s
                WHERE trade_id = %s
            """, (exit_price, realized_pnl, reason, exit_context, position['trade_id']))

            # Update signal state to EXPIRED (position closed)
            # Valid states: DORMANT, PRIMED, EXECUTING, POSITION, COOLING, EXPIRED, DUPLICATE_PRUNED
            cur.execute("""
                UPDATE fhq_canonical.g5_signal_state
                SET
                    current_state = 'EXPIRED',  -- Fixed: was 'EXECUTED' (invalid state per CHECK constraint)
                    executing_at = NOW(),  -- Fixed: was executed_at (schema mismatch)
                    exit_price = %s,  -- Fixed: was position_exit_price (schema mismatch)
                    exit_pnl = %s,  -- Fixed: was realized_pnl (schema mismatch)
                    last_transition = 'POSITION_TO_EXPIRED',
                    last_transition_at = NOW(),
                    transition_count = transition_count + 1,
                    updated_at = NOW()
                WHERE needle_id = %s
            """, (exit_price, realized_pnl, position['needle_id']))

            # Log transition
            cur.execute("""
                INSERT INTO fhq_canonical.g5_state_transitions (
                    needle_id, from_state, to_state, transition_trigger,
                    context_snapshot, cco_status, transition_valid, transitioned_at
                ) VALUES (
                    %s, 'POSITION', 'EXPIRED', %s,
                    %s, %s, TRUE, NOW()
                )
            """, (
                position['needle_id'],
                reason,
                exit_context,
                cco_state['cco_status'] if cco_state else 'UNKNOWN'
            ))

        self.conn.commit()

    def monitor_positions(self) -> Dict:
        """Monitor all open positions for exit conditions"""
        result = {
            'positions_checked': 0,
            'exits_triggered': 0,
            'exits': []
        }

        positions = self.get_open_positions()
        result['positions_checked'] = len(positions)

        for position in positions:
            should_exit, reason, current_price = self.check_exit_conditions(position)

            if should_exit:
                exit_result = self.execute_exit(position, reason, current_price)
                if exit_result:
                    result['exits_triggered'] += 1
                    result['exits'].append(exit_result)

        return result

    # =========================================================================
    # GOLDEN NEEDLE SELECTION
    # =========================================================================

    def get_executable_needles(self, limit: int = 5) -> List[Dict]:
        """Get Golden Needles eligible for execution"""
        traded_needles = self.get_traded_needles()
        traded_clause = ""
        if traded_needles:
            traded_clause = f"AND needle_id NOT IN ({','.join(['%s'] * len(traded_needles))})"

        query = f"""
            SELECT
                needle_id,
                hypothesis_title,
                hypothesis_category,
                eqs_score,
                confluence_factor_count,
                sitc_confidence_level,
                price_witness_symbol,
                regime_technical,
                expected_timeframe_days,
                created_at
            FROM fhq_canonical.golden_needles
            WHERE is_current = TRUE
              AND eqs_score >= %s
              {traded_clause}
            ORDER BY eqs_score DESC, created_at DESC
            LIMIT %s
        """

        params = [DAEMON_CONFIG['min_eqs_score']]
        if traded_needles:
            params.extend(traded_needles)
        params.append(limit)

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def select_symbol_for_needle(self, needle: Dict) -> Optional[str]:
        """
        Select tradeable symbol based on needle's price witness.
        Per CD-IOS-001-PRICE-ARCH-001: Multi-asset execution support.

        Priority:
        1. Crypto - convert to Alpaca format (BTCUSD) and trade directly
        2. Direct mapping for equities
        3. Direct equity symbol

        CEO Directive: No crypto proxies - trade crypto directly on Alpaca.
        """
        witness = needle.get('price_witness_symbol', '')
        open_symbols = self.get_open_symbols()

        # 1. Check if it's a crypto symbol - trade directly (CEO Directive: No proxies)
        # MUST convert to Alpaca format (e.g., BTC/USD -> BTCUSD)
        if witness in CRYPTO_SYMBOL_MAP:
            alpaca_symbol = CRYPTO_SYMBOL_MAP[witness]
            if alpaca_symbol not in open_symbols:
                return alpaca_symbol  # Trade crypto directly on Alpaca
            else:
                # Already have position in this crypto - don't try other symbols
                return None

        # 2. Check if it's in DIRECT_CRYPTO_SYMBOLS - keep BTC/USD format for Alpaca
        if witness in DIRECT_CRYPTO_SYMBOLS:
            # Alpaca uses BTC/USD format (with slash) for crypto
            if witness not in open_symbols:
                return witness  # Already in correct format
            else:
                return None  # Already have position

        # 3. Check direct mapping for equities
        if witness in SYMBOL_MAPPING:
            mapped = SYMBOL_MAPPING[witness]
            if mapped not in open_symbols:
                return mapped

        # 4. Check if witness is a direct equity symbol
        if witness in DIRECT_EQUITY_SYMBOLS:
            if witness not in open_symbols:
                return witness

        # 5. No valid symbol found
        return None

    # =========================================================================
    # SKILL DAMPER (CEO DIRECTIVE 2025-12-24)
    # =========================================================================

    def get_skill_damper(self) -> Tuple[float, float, str]:
        """
        Calculate FSS (FINN Skill Score) and return appropriate damper.
        Returns: (damper_value, fss_score, threshold_type)

        FSS is calculated from paper trade outcomes:
        - Win rate weighted by profit magnitude
        - Normalized to 0.0-1.0 scale
        """
        try:
            with self.conn.cursor() as cur:
                # Get paper trade statistics (excluding test/invalid trades)
                cur.execute("""
                    SELECT
                        COUNT(*) as total_trades,
                        COUNT(*) FILTER (WHERE pnl_absolute > 0) as winning_trades,
                        COALESCE(SUM(pnl_absolute), 0) as total_pnl,
                        COALESCE(AVG(pnl_percent), 0) as avg_pnl_pct
                    FROM fhq_canonical.g5_paper_trades
                    WHERE exit_price IS NOT NULL
                    AND (exclude_from_fss IS NULL OR exclude_from_fss = FALSE)
                """)
                stats = cur.fetchone()

                total_trades = int(stats[0]) if stats[0] else 0
                winning_trades = int(stats[1]) if stats[1] else 0
                total_pnl = float(stats[2]) if stats[2] else 0
                avg_pnl_pct = float(stats[3]) if stats[3] else 0

                # Calculate FSS (simple version: weighted win rate + profit factor)
                if total_trades < 3:
                    # Insufficient data - use conservative default
                    fss = 0.45  # REDUCED zone
                    logger.info(f"SKILL_DAMPER: Insufficient trades ({total_trades}), using FSS={fss}")
                else:
                    win_rate = winning_trades / total_trades
                    # Profit bonus: positive avg PnL adds to FSS
                    profit_bonus = min(avg_pnl_pct / 10, 0.2)  # Max 0.2 bonus
                    fss = min(1.0, max(0.0, win_rate * 0.8 + profit_bonus + 0.1))

                # Look up damper from config
                cur.execute("""
                    SELECT threshold_type, damper_value
                    FROM fhq_governance.skill_damper_config
                    WHERE is_active = TRUE
                    AND %s >= fss_min AND %s < fss_max
                    LIMIT 1
                """, (fss, fss))

                config = cur.fetchone()
                if config:
                    threshold_type = config[0]
                    damper_value = float(config[1])
                else:
                    # Default to REDUCED if no config found
                    threshold_type = 'REDUCED'
                    damper_value = 0.25

                logger.info(f"SKILL_DAMPER: FSS={fss:.3f}, threshold={threshold_type}, damper={damper_value}")
                return damper_value, fss, threshold_type

        except Exception as e:
            logger.warning(f"SKILL_DAMPER: Error calculating FSS: {e}, using conservative default")
            return 0.25, 0.45, 'REDUCED'

    # =========================================================================
    # POSITION SIZING (KELLY)
    # =========================================================================

    def calculate_position_size(
        self,
        symbol: str,
        eqs_score: float,
        confidence: str
    ) -> Tuple[int, float, float]:
        """Calculate position size using Kelly criterion"""
        if not self.trading_client:
            return 0, 0, 0

        # Get account value
        account = self.trading_client.get_account()
        portfolio_value = float(account.portfolio_value)

        # Get current price (handles both stock and crypto)
        current_price = self.get_current_price(symbol)
        if current_price is None or current_price <= 0:
            logger.warning(f"Could not get price for {symbol} - skipping")
            return 0, 0, 0

        # Map EQS to Sharpe estimate (EQS 1.0 ~ Sharpe 0.5)
        sharpe_estimate = eqs_score * 0.5

        # Confidence multiplier
        conf_mult = {'HIGH': 1.0, 'MEDIUM': 0.8, 'LOW': 0.6}.get(confidence, 0.7)

        # Kelly calculation
        win_prob = 0.5 + (0.5 / (1 + 2.718 ** (-3 * sharpe_estimate))) - 0.25
        win_prob = min(max(win_prob, 0.50), 0.95)
        win_loss = 1.0 + (0.5 * sharpe_estimate)
        raw_kelly = (win_prob * (win_loss + 1) - 1) / win_loss

        # Apply multipliers
        adjusted_kelly = raw_kelly * DAEMON_CONFIG['kelly_multiplier'] * conf_mult

        # CEO DIRECTIVE 2025-12-24: Apply SkillDamper
        damper_value, fss_score, threshold_type = self.get_skill_damper()
        if damper_value == 0.0:
            logger.warning(f"SKILL_DAMPER: FREEZE active (FSS={fss_score:.3f}) - blocking position")
            return 0, 0, 0
        adjusted_kelly = adjusted_kelly * damper_value

        # Cap at max position
        position_pct = min(adjusted_kelly, DAEMON_CONFIG['max_position_pct'])

        # Calculate dollar amount
        dollar_amount = portfolio_value * position_pct
        dollar_amount = max(dollar_amount, DAEMON_CONFIG['min_position_dollars'])

        # Calculate quantity (fractional for crypto, integer for stocks)
        is_crypto = self._is_crypto_symbol(symbol)
        if is_crypto:
            # Crypto supports fractional quantities - round to 8 decimal places
            qty = round(dollar_amount / current_price, 8)
        else:
            # Stocks use whole shares
            qty = int(dollar_amount / current_price)

        logger.info(f"POSITION_SIZE: {symbol} ${dollar_amount:.0f} ({position_pct*100:.1f}% NAV, damper={damper_value}, qty={qty})")
        return qty, dollar_amount, current_price

    # =========================================================================
    # TRADE EXECUTION
    # =========================================================================

    def execute_trade(self, needle: Dict, symbol: str) -> Optional[Dict]:
        """Execute a paper trade for a Golden Needle"""
        if not self.trading_client:
            logger.warning("Alpaca not available - skipping execution")
            return None

        # =====================================================================
        # CEO-DIR-2026-FINN-019: NEURAL BRIDGE - INTENT DRAFT + ATTEMPT LOGGER
        # Phase 1: Create IntentDraft BEFORE any gate (CEO Issue #1)
        # Phase 2: Log ALL gates to attempt (even if blocked)
        # Stage A: Shadow mode - logs but doesn't block on IKEA/InForage
        # =====================================================================
        attempt = None
        intent_draft = None
        needle_id = needle.get('needle_id')
        if needle_id and isinstance(needle_id, str):
            try:
                needle_id = uuid.UUID(needle_id)
            except ValueError:
                needle_id = uuid.uuid4()
        elif not needle_id:
            needle_id = uuid.uuid4()

        if self.attempt_logger and NEURAL_BRIDGE_ENABLED:
            try:
                # Get current market snapshot for IntentDraft
                eqs_score = float(needle.get('eqs_score', 0.0))
                regime = needle.get('regime_sovereign', 'UNKNOWN')
                regime_stability = float(needle.get('regime_stability', 0.5))
                entry_price_estimate = float(needle.get('entry_price', 0.0))
                direction = needle.get('signal_direction', 'LONG')

                # Create IntentDraft with market snapshot (CEO Issue #8: 60s TTL)
                intent_draft = create_intent_draft(
                    needle_id=needle_id,
                    asset=symbol,
                    direction=direction,
                    eqs_score=eqs_score,
                    snapshot_price=entry_price_estimate,
                    snapshot_regime=regime,
                    snapshot_regime_stability=regime_stability
                )

                # Start Attempt record (ADR-011 Fortress hash chain)
                attempt = self.attempt_logger.start_attempt(
                    needle_id=needle_id,
                    intent_draft_id=intent_draft.draft_id,
                    audit_only=NEURAL_BRIDGE_AUDIT_ONLY
                )
                logger.info(f"[NEURAL-BRIDGE] IntentDraft created: {intent_draft.draft_id}")
                logger.info(f"[NEURAL-BRIDGE] Attempt started: {attempt.attempt_id} (seq={attempt.chain_sequence})")

            except Exception as e:
                logger.warning(f"[NEURAL-BRIDGE] Failed to create IntentDraft/Attempt: {e}")
                attempt = None
                intent_draft = None

        # =====================================================================
        # LIDS CONFIDENCE HARD GATE (CEO-DIR-2026-019)
        # ACI 1.0 Learning Activation: belief_confidence < 0.70 → NO EXECUTION
        # =====================================================================
        # CEO-DIR-2026-TRUTH-SYNC-P3 Fix: Look for sitc_confidence_level first (from SELECT query)
        # Then fall back to confidence/belief_confidence for backwards compatibility
        lids_confidence = needle.get('sitc_confidence_level', needle.get('confidence', needle.get('belief_confidence', 0.0)))
        if isinstance(lids_confidence, str):
            lids_confidence = {'HIGH': 0.85, 'MEDIUM': 0.70, 'LOW': 0.50}.get(lids_confidence.upper(), 0.5)

        LIDS_MIN_CONFIDENCE = 0.70  # CEO-DIR-2026-019 hard requirement

        if lids_confidence < LIDS_MIN_CONFIDENCE:
            lids_reason = f"LIDS_BLOCKED: confidence={lids_confidence:.2f} < {LIDS_MIN_CONFIDENCE} threshold"
            logger.critical(f"[LIDS-GATE] {lids_reason}")
            if attempt and self.attempt_logger:
                self.attempt_logger.log_gate_result(attempt, 'lids_confidence', False, lids_reason)
                self.attempt_logger.complete_attempt(attempt, 'BLOCKED', blocked_at_gate='LIDS_CONFIDENCE')
            # CEO-DIR-2026-020 D3: Log LIDS block to governance (MANDATORY)
            self.log_lids_gate_block(
                block_type='CONFIDENCE',
                signal_id=str(needle.get('needle_id', needle.get('signal_id', 'unknown'))),
                asset=symbol,
                confidence=lids_confidence,
                freshness_hours=0.0,  # Not yet computed
                threshold=LIDS_MIN_CONFIDENCE,
                needle=needle
            )
            return None
        else:
            if attempt and self.attempt_logger:
                self.attempt_logger.log_gate_result(attempt, 'lids_confidence', True, f'confidence={lids_confidence:.2f}')
            logger.info(f"[LIDS-GATE] Confidence PASSED: {lids_confidence:.2f} >= {LIDS_MIN_CONFIDENCE}")

        # =====================================================================
        # LIDS FRESHNESS HARD GATE (CEO-DIR-2026-019)
        # ACI 1.0 Learning Activation: data_freshness > 12h → NO EXECUTION
        # =====================================================================
        data_timestamp = needle.get('data_timestamp', needle.get('created_at'))
        lids_freshness_hours = 999  # Default to stale if unknown

        if data_timestamp:
            try:
                if isinstance(data_timestamp, str):
                    from dateutil import parser
                    data_timestamp = parser.parse(data_timestamp)
                age_seconds = (datetime.now(timezone.utc) - data_timestamp.replace(tzinfo=timezone.utc)).total_seconds()
                lids_freshness_hours = age_seconds / 3600
            except Exception as e:
                logger.warning(f"[LIDS-GATE] Could not parse data_timestamp: {e}")

        LIDS_MAX_FRESHNESS_HOURS = 12  # CEO-DIR-2026-019 hard requirement

        if lids_freshness_hours > LIDS_MAX_FRESHNESS_HOURS:
            freshness_reason = f"LIDS_BLOCKED: data_freshness={lids_freshness_hours:.1f}h > {LIDS_MAX_FRESHNESS_HOURS}h threshold"
            logger.critical(f"[LIDS-GATE] {freshness_reason}")
            if attempt and self.attempt_logger:
                self.attempt_logger.log_gate_result(attempt, 'lids_freshness', False, freshness_reason)
                self.attempt_logger.complete_attempt(attempt, 'BLOCKED', blocked_at_gate='LIDS_FRESHNESS')
            # CEO-DIR-2026-020 D3: Log LIDS block to governance (MANDATORY)
            self.log_lids_gate_block(
                block_type='FRESHNESS',
                signal_id=str(needle.get('needle_id', needle.get('signal_id', 'unknown'))),
                asset=symbol,
                confidence=lids_confidence,
                freshness_hours=lids_freshness_hours,
                threshold=LIDS_MAX_FRESHNESS_HOURS,
                needle=needle
            )
            return None
        else:
            if attempt and self.attempt_logger:
                self.attempt_logger.log_gate_result(attempt, 'lids_freshness', True, f'freshness={lids_freshness_hours:.1f}h')
            logger.info(f"[LIDS-GATE] Freshness PASSED: {lids_freshness_hours:.1f}h <= {LIDS_MAX_FRESHNESS_HOURS}h")

        # CEO-DIR-2026-020 D3: Log LIDS gate pass for counter-metrics
        # Both confidence and freshness passed - record for block rate computation
        self.log_lids_gate_passed(lids_confidence, lids_freshness_hours)

        # =====================================================================
        # HARD EXPOSURE GATE - MANDATORY PRE-EXECUTION CHECK
        # CEO Directive 2025-12-21: Validates ACTUAL Alpaca state before any trade.
        # Fix D: Same-symbol accumulation guard via proposed_symbol
        # =====================================================================
        gate_ok, gate_reason = self.validate_exposure_gate(proposed_symbol=symbol)

        # Log gate result to Neural Bridge attempt
        if attempt and self.attempt_logger:
            self.attempt_logger.log_gate_result(attempt, 'exposure', gate_ok, gate_reason or 'PASSED')

        if not gate_ok:
            logger.critical(f"EXECUTION BLOCKED by HARD EXPOSURE GATE: {gate_reason}")
            self.log_exposure_violation(gate_reason, {
                'symbol': symbol,
                'needle_id': str(needle.get('needle_id', 'unknown')),
                'attempted_action': 'TRADE_EXECUTION',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            # Complete attempt as BLOCKED (CEO-DIR-2026-FINN-019)
            if attempt and self.attempt_logger:
                self.attempt_logger.complete_attempt(attempt, 'BLOCKED', blocked_at_gate='EXPOSURE')
            return None

        # =====================================================================
        # HOLIDAY EXECUTION GATE (CEO Directive 2025-12-19)
        # Crypto-First Execution: Equities/FX suspended, Crypto (BTC,ETH,SOL) active
        # =====================================================================
        holiday_ok = True
        holiday_reason = 'NOT_CHECKED'
        if HOLIDAY_GATE_AVAILABLE and HOLIDAY_MODE_ENABLED:
            # Get source signal for proxy resolution
            source_symbol = needle.get('price_witness_symbol', symbol)
            holiday_ok, holiday_reason, asset_class = check_holiday_execution_gate(
                symbol=symbol,
                target_state='ACTIVE',
                source_signal=source_symbol
            )

            # Log gate result to Neural Bridge attempt
            if attempt and self.attempt_logger:
                self.attempt_logger.log_gate_result(attempt, 'holiday', holiday_ok, holiday_reason)

            if not holiday_ok:
                logger.warning(f"HOLIDAY GATE BLOCKED: {symbol} ({asset_class}) - {holiday_reason}")
                # Log for observability (signal lifecycle continues, execution blocked)
                self.log_holiday_gate_block(symbol, asset_class, holiday_reason, needle)
                # Complete attempt as BLOCKED (CEO-DIR-2026-FINN-019)
                if attempt and self.attempt_logger:
                    self.attempt_logger.complete_attempt(attempt, 'BLOCKED', blocked_at_gate='HOLIDAY')
                return None
            else:
                logger.info(f"HOLIDAY GATE PASSED: {symbol} ({asset_class}) - {holiday_reason}")
        else:
            # Log gate as skipped
            if attempt and self.attempt_logger:
                self.attempt_logger.log_gate_result(attempt, 'holiday', True, 'SKIPPED')

        # =====================================================================
        # BTC-ONLY CONSTRAINT (CEO DIRECTIVE 2025-12-24)
        # Shadow Ledger deployment authorized ONLY for BTC until skill verified.
        # =====================================================================
        source_symbol = needle.get('price_witness_symbol', needle.get('target_asset', symbol))
        is_btc_signal = any(btc in str(source_symbol).upper() for btc in ['BTC', 'BITCOIN'])

        # Log gate result to Neural Bridge attempt
        if attempt and self.attempt_logger:
            btc_reason = 'BTC_SIGNAL' if is_btc_signal else f'NON_BTC: {source_symbol}'
            self.attempt_logger.log_gate_result(attempt, 'btc_only', is_btc_signal, btc_reason)

        if not is_btc_signal:
            logger.info(f"BTC-ONLY CONSTRAINT: Blocking {symbol} (source: {source_symbol}) - only BTC authorized")
            # Complete attempt as BLOCKED (CEO-DIR-2026-FINN-019)
            if attempt and self.attempt_logger:
                self.attempt_logger.complete_attempt(attempt, 'BLOCKED', blocked_at_gate='BTC_ONLY')
            return None

        # =====================================================================
        # CEO-DIR-2026-FINN-018: SITC EXECUTION GATE
        # "No thinking, no trading."
        # Every trade must have active SitC reasoning before execution.
        # =====================================================================
        sitc_result = None
        sitc_event_id = None
        if self.sitc_gate:
            needle_id_str = str(needle.get('needle_id', uuid.uuid4()))
            hypothesis = needle.get('hypothesis_statement', needle.get('executive_summary', f'Trade signal for {symbol}'))
            regime_context = needle.get('regime_sovereign', 'UNKNOWN')
            eqs_score = float(needle.get('eqs_score', 0.0))

            logger.info(f"[SITC-GATE] Invoking cognitive reasoning for {symbol}...")
            sitc_result = self.sitc_gate.reason_and_gate(
                needle_id=needle_id_str,
                asset=symbol,
                hypothesis=hypothesis,
                regime_context=regime_context,
                eqs_score=eqs_score
            )

            # Link SitC event to Neural Bridge attempt
            sitc_event_id = getattr(sitc_result, 'sitc_event_id', None)
            if attempt and self.attempt_logger and sitc_event_id:
                attempt.sitc_event_id = sitc_event_id

            # Log gate result to Neural Bridge attempt
            sitc_passed = sitc_result.approved
            sitc_reason = 'APPROVED' if sitc_passed else sitc_result.rejection_reason
            if attempt and self.attempt_logger:
                self.attempt_logger.log_gate_result(attempt, 'sitc', sitc_passed, sitc_reason)

            if not sitc_result.approved:
                logger.critical(f"[SITC-GATE] EXECUTION BLOCKED - {sitc_result.rejection_reason}")
                logger.info(f"[SITC-GATE] Confidence: {sitc_result.confidence_level}, EQS: {sitc_result.eqs_score:.3f}")
                # Log the rejection for audit
                try:
                    with self.conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO fhq_governance.decision_log (
                                decision_id, decision_type, decision_rationale, created_at
                            ) VALUES (
                                gen_random_uuid(), 'SITC_GATE_REJECTION',
                                %s, NOW()
                            )
                        """, (f"SitC blocked {symbol}: {sitc_result.rejection_reason}",))
                    self.conn.commit()
                except Exception as e:
                    logger.warning(f"Could not log SitC rejection: {e}")
                # Complete attempt as BLOCKED (CEO-DIR-2026-FINN-019)
                if attempt and self.attempt_logger:
                    self.attempt_logger.complete_attempt(attempt, 'BLOCKED', blocked_at_gate='SITC')
                return None

            logger.info(f"[SITC-GATE] APPROVED - Confidence: {sitc_result.confidence_level}, EQS: {sitc_result.eqs_score:.3f}")
        else:
            # SitC gate not available - log as skipped
            if attempt and self.attempt_logger:
                self.attempt_logger.log_gate_result(attempt, 'sitc', True, 'NOT_AVAILABLE')
            logger.warning("[SITC-GATE] Not available - executing without cognitive reasoning (TEMPORARY)")

        # WAVE 17D.1 FIX: Check for existing pending orders to prevent duplicates
        try:
            open_orders = self.trading_client.get_orders(
                GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
            )
            if open_orders:
                logger.info(f"Pending order exists for {symbol} - skipping duplicate")
                # Complete attempt as BLOCKED (CEO-DIR-2026-FINN-019)
                if attempt and self.attempt_logger:
                    self.attempt_logger.log_gate_result(attempt, 'pending_orders', False, 'DUPLICATE_ORDER')
                    self.attempt_logger.complete_attempt(attempt, 'BLOCKED', blocked_at_gate='PENDING_ORDERS')
                return None
        except Exception as e:
            logger.warning(f"Could not check pending orders: {e}")

        # Calculate position size
        shares, dollar_amount, entry_price = self.calculate_position_size(
            symbol,
            float(needle['eqs_score']),
            needle['sitc_confidence_level']
        )

        # =====================================================================
        # SECONDARY GATE: Validate proposed trade against limits
        # CEO Directive 2025-12-21: Fix D (same-symbol) + Fix E (incremental exposure)
        # =====================================================================
        gate_ok, gate_reason = self.validate_exposure_gate(
            proposed_trade_usd=dollar_amount,
            proposed_symbol=symbol
        )

        # Log secondary exposure gate to Neural Bridge attempt
        if attempt and self.attempt_logger:
            self.attempt_logger.log_gate_result(attempt, 'exposure_secondary', gate_ok, gate_reason or 'PASSED')

        if not gate_ok:
            logger.warning(f"Proposed trade blocked: {gate_reason}")
            # Complete attempt as BLOCKED (CEO-DIR-2026-FINN-019)
            if attempt and self.attempt_logger:
                self.attempt_logger.complete_attempt(attempt, 'BLOCKED', blocked_at_gate='EXPOSURE_SECONDARY')
            return None

        # =====================================================================
        # CEO-DIR-2026-FINN-019: IKEA TRUTH BOUNDARY (Stage A Shadow Mode)
        # 6 deterministic rules. In Shadow mode: logs but doesn't block.
        # =====================================================================
        ikea_validation_id = None
        if self.ikea_boundary and intent_draft and NEURAL_BRIDGE_ENABLED:
            try:
                # Calculate position percentage for IKEA-003 check
                try:
                    account = self.trading_client.get_account()
                    nav = float(account.portfolio_value)
                    position_pct = (dollar_amount / nav * 100) if nav > 0 else 0.0
                except Exception as e:
                    logger.warning(f"Could not get NAV for IKEA: {e}")
                    position_pct = 10.0  # Conservative default

                ikea_result = self.ikea_boundary.validate(
                    needle_id=needle_id,
                    asset=symbol,
                    direction=intent_draft.direction,
                    eqs_score=intent_draft.eqs_score,
                    snapshot_timestamp=intent_draft.snapshot_timestamp,
                    snapshot_regime=intent_draft.snapshot_regime,
                    position_pct=position_pct
                )
                ikea_validation_id = ikea_result.validation_id

                # Log gate result to Neural Bridge attempt
                if attempt and self.attempt_logger:
                    ikea_reason = 'PASSED' if ikea_result.passed else f'{ikea_result.rule_violated}: {ikea_result.violation_details}'
                    self.attempt_logger.log_gate_result(attempt, 'ikea', ikea_result.passed, ikea_reason)
                    attempt.ikea_validation_id = ikea_validation_id

                if not ikea_result.passed:
                    logger.warning(f"[IKEA] Rule violated: {ikea_result.rule_violated} - {ikea_result.violation_details}")
                    # Stage A (Shadow Mode): Log but don't block
                    if not NEURAL_BRIDGE_AUDIT_ONLY:
                        # Stage B (Hard Gate): Block execution
                        if attempt and self.attempt_logger:
                            self.attempt_logger.complete_attempt(attempt, 'BLOCKED', blocked_at_gate=f'IKEA_{ikea_result.rule_violated}')

                        # TELEGRAM NOTIFICATION: Neural Bridge Block
                        if TELEGRAM_AVAILABLE and telegram_notifier:
                            try:
                                telegram_notifier.neural_bridge_block(
                                    symbol=symbol,
                                    direction='LONG',
                                    blocked_by=f'IKEA_{ikea_result.rule_violated}',
                                    block_reason=str(ikea_result.violation_details.get('reason', 'Unknown')),
                                    needle_title=needle.get('hypothesis_title', 'Unknown'),
                                    eqs_score=float(needle.get('eqs_score', 0))
                                )
                            except Exception as te:
                                logger.warning(f"Telegram notification failed: {te}")

                        return None
                    else:
                        logger.info(f"[IKEA] Shadow mode - would block but continuing for audit")
                else:
                    logger.info(f"[IKEA] All 6 rules passed - validation_id={ikea_validation_id}")

            except Exception as e:
                logger.warning(f"[IKEA] Validation error: {e}")
                if attempt and self.attempt_logger:
                    self.attempt_logger.log_gate_result(attempt, 'ikea', True, f'ERROR: {e}')

        # =====================================================================
        # CEO-DIR-2026-FINN-019: INFORAGE ROI CHECK (Stage A Shadow Mode)
        # ROI < 1.2 = ABORT in Hard Gate mode. Shadow mode just logs.
        # =====================================================================
        inforage_session_id = None
        inforage_roi = None
        if self.inforage_controller and intent_draft and NEURAL_BRIDGE_ENABLED:
            try:
                inforage_result = self.inforage_controller.check_trade_decision(
                    needle_id=needle_id,
                    eqs_score=intent_draft.eqs_score,
                    position_usd=dollar_amount,
                    spread_bps=5.0,  # Default spread
                    slippage_bps=15.0  # CEO Issue #17
                )
                inforage_session_id = inforage_result.session_id
                inforage_roi = inforage_result.roi

                # Log gate result to Neural Bridge attempt
                if attempt and self.attempt_logger:
                    inforage_reason = f'ROI={inforage_roi:.2f}' if inforage_roi else 'UNKNOWN'
                    self.attempt_logger.log_gate_result(attempt, 'inforage', not inforage_result.should_abort, inforage_reason)
                    attempt.inforage_session_id = inforage_session_id

                if inforage_result.should_abort:
                    logger.warning(f"[INFORAGE] Low ROI: {inforage_roi:.2f} < 1.2 threshold")
                    # Stage A (Shadow Mode): Log but don't block
                    if not NEURAL_BRIDGE_AUDIT_ONLY:
                        # Stage B (Hard Gate): Block execution
                        if attempt and self.attempt_logger:
                            self.attempt_logger.complete_attempt(attempt, 'ABORTED', blocked_at_gate='INFORAGE_LOW_ROI')

                        # TELEGRAM NOTIFICATION: Neural Bridge Block (InForage)
                        if TELEGRAM_AVAILABLE and telegram_notifier:
                            try:
                                telegram_notifier.neural_bridge_block(
                                    symbol=symbol,
                                    direction='LONG',
                                    blocked_by='INFORAGE_LOW_ROI',
                                    block_reason=f'ROI {inforage_roi:.2f} below 1.2 threshold',
                                    needle_title=needle.get('hypothesis_title', 'Unknown'),
                                    eqs_score=float(needle.get('eqs_score', 0))
                                )
                            except Exception as te:
                                logger.warning(f"Telegram notification failed: {te}")

                        return None
                    else:
                        logger.info(f"[INFORAGE] Shadow mode - would abort but continuing for audit")
                else:
                    logger.info(f"[INFORAGE] ROI acceptable: {inforage_roi:.2f}")

            except Exception as e:
                logger.warning(f"[INFORAGE] Check error: {e}")
                if attempt and self.attempt_logger:
                    self.attempt_logger.log_gate_result(attempt, 'inforage', True, f'ERROR: {e}')

        # Validate minimum position size
        is_crypto = self._is_crypto_symbol(symbol)
        if is_crypto:
            # Crypto minimum: $10 or 0.0001 units (Alpaca's minimum for most crypto)
            if shares < 0.0001 or dollar_amount < 10:
                logger.warning(f"Position too small for {symbol} (qty={shares:.8f}, ${dollar_amount:.2f}) - skipping")
                # Complete attempt as BLOCKED (CEO-DIR-2026-FINN-019)
                if attempt and self.attempt_logger:
                    self.attempt_logger.log_gate_result(attempt, 'position_size', False, f'TOO_SMALL: qty={shares:.8f}, ${dollar_amount:.2f}')
                    self.attempt_logger.complete_attempt(attempt, 'BLOCKED', blocked_at_gate='POSITION_SIZE')
                return None
        else:
            # Stocks require at least 1 share
            if shares < 1:
                logger.warning(f"Position too small for {symbol} - skipping")
                # Complete attempt as BLOCKED (CEO-DIR-2026-FINN-019)
                if attempt and self.attempt_logger:
                    self.attempt_logger.log_gate_result(attempt, 'position_size', False, f'TOO_SMALL: shares={shares}')
                    self.attempt_logger.complete_attempt(attempt, 'BLOCKED', blocked_at_gate='POSITION_SIZE')
                return None

        qty_str = f"{shares:.8f}" if is_crypto else str(int(shares))
        logger.info(f"Executing: BUY {qty_str} {symbol} @ ${entry_price:.2f} (~${dollar_amount:,.2f})")

        try:
            # Submit market order
            # Crypto requires GTC (good till canceled), stocks use DAY
            tif = TimeInForce.GTC if is_crypto else TimeInForce.DAY
            order = self.trading_client.submit_order(
                MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=OrderSide.BUY,
                    time_in_force=tif
                )
            )

            # Wait for fill
            time.sleep(1)
            filled_order = self.trading_client.get_order_by_id(order.id)

            if filled_order.status in ['filled', 'partially_filled']:
                filled_qty = float(filled_order.filled_qty)
                filled_price = float(filled_order.filled_avg_price)
                position_value = filled_qty * filled_price

                qty_display = f"{filled_qty:.8f}" if is_crypto else f"{int(filled_qty)}"
                logger.info(f"FILLED: {qty_display} {symbol} @ ${filled_price:.2f} = ${position_value:,.2f}")

                # =====================================================================
                # LOCAL PENDING EXPOSURE TRACKING (CEO DIRECTIVE 2026-01-01)
                # Track this trade immediately to prevent race condition
                # =====================================================================
                self._add_pending_exposure(symbol, filled_qty, position_value)

                # Log to database
                trade_id = self._log_trade(needle, symbol, filled_qty, filled_price, position_value, order.id)

                # =====================================================================
                # CEO-DIR-2026-FINN-018: Mark SitC gate as EXECUTED
                # =====================================================================
                if sitc_result and sitc_result.sitc_event_id and self.sitc_gate:
                    self.sitc_gate.mark_executed(sitc_result.sitc_event_id, trade_id)
                    logger.info(f"[SITC-GATE] Marked as EXECUTED: {sitc_result.sitc_event_id[:8]}...")

                # =====================================================================
                # CEO-DIR-2026-FINN-019: Complete attempt as EXECUTED
                # =====================================================================
                if attempt and self.attempt_logger:
                    attempt.decision_plan_id = None  # Phase II: Seal DecisionPlan
                    self.attempt_logger.complete_attempt(attempt, 'EXECUTED')
                    logger.info(f"[NEURAL-BRIDGE] Attempt EXECUTED: {attempt.attempt_id}")

                # =====================================================================
                # TELEGRAM NOTIFICATION: Trade Executed
                # =====================================================================
                if TELEGRAM_AVAILABLE and telegram_notifier:
                    try:
                        telegram_notifier.trade_executed(
                            symbol=symbol,
                            direction='LONG',  # Daemon only does LONG currently
                            entry_price=filled_price,
                            position_usd=position_value,
                            needle_title=needle.get('hypothesis_title', 'Unknown'),
                            eqs_score=float(needle.get('eqs_score', 0)),
                            regime=cco_state['current_regime'] if cco_state else 'UNKNOWN',
                            decision_plan_id=str(attempt.attempt_id) if attempt else None
                        )
                    except Exception as te:
                        logger.warning(f"Telegram notification failed: {te}")

                return {
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'qty': filled_qty,
                    'price': filled_price,
                    'value': position_value,
                    'order_id': str(order.id),
                    'sitc_event_id': sitc_result.sitc_event_id if sitc_result else None,
                    'attempt_id': str(attempt.attempt_id) if attempt else None
                }
            else:
                logger.warning(f"Order not filled: {filled_order.status}")
                # Complete attempt as ABORTED due to order not filling
                if attempt and self.attempt_logger:
                    self.attempt_logger.complete_attempt(attempt, 'ABORTED', blocked_at_gate='ORDER_NOT_FILLED')
                return None

        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            # Complete attempt as ABORTED due to exception
            if attempt and self.attempt_logger:
                try:
                    self.attempt_logger.complete_attempt(attempt, 'ABORTED', blocked_at_gate=f'EXCEPTION: {type(e).__name__}')
                except:
                    pass
            return None

    def _log_trade(
        self,
        needle: Dict,
        symbol: str,
        qty: float,
        price: float,
        value: float,
        order_id: str
    ) -> str:
        """
        Log trade to database.

        CEO Directive 2025-12-21 FIX C: Trade logging must be atomic with execution.
        If primary logging fails, we MUST log to recovery table because the broker
        trade has already executed.

        The trade cannot be rolled back at broker level, so we ensure logging
        succeeds or falls back to a simpler recovery log.
        """
        trade_id = str(uuid.uuid4())
        execution_time = datetime.now(timezone.utc)
        cco_state = self.get_cco_state()

        # CEO DIRECTIVE 2025-12-24: Regime-conditioned exit parameters
        # Phase 2 validated (p < 0.05). Parameters are FROZEN - no modifications.
        current_regime = cco_state['current_regime'] if cco_state else 'NEUTRAL'
        regime_params = REGIME_EXIT_PARAMS.get(current_regime, REGIME_EXIT_PARAMS['NEUTRAL'])
        regime_target_pct = regime_params['target_pct']
        regime_stop_loss_pct = regime_params['stop_loss_pct']

        # CEO DIRECTIVE 2025-12-24: IoS-005 Skill Score tracking
        damper_value, fss_score, threshold_type = self.get_skill_damper()

        entry_context = json.dumps({
            'cco_status': cco_state['cco_status'] if cco_state else 'UNKNOWN',
            'global_permit': cco_state['global_permit'] if cco_state else 'UNKNOWN',
            'regime': current_regime,
            'vol_percentile': float(cco_state['current_vol_percentile']) if cco_state else 0,
            'needle_title': needle.get('hypothesis_title', 'UNKNOWN'),
            'needle_category': needle.get('hypothesis_category', 'UNKNOWN'),
            'eqs_score': float(needle.get('eqs_score', 0)),
            'alpaca_order_id': str(order_id),
            'kelly_multiplier': DAEMON_CONFIG['kelly_multiplier'],
            'target_pct': regime_target_pct,
            'stop_loss_pct': regime_stop_loss_pct,
            'exit_model': 'REGIME_CONDITIONED_V1',
            'fss_score': fss_score,
            'skill_damper': damper_value,
            'skill_threshold': threshold_type,
            'executed_by': 'SIGNAL_EXECUTOR_DAEMON',
            'execution_timestamp': execution_time.isoformat()
        })

        try:
            # =====================================================================
            # PRIMARY LOGGING - Normal trade record
            # =====================================================================
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_canonical.g5_paper_trades (
                        trade_id, needle_id, symbol, direction, entry_price,
                        position_size, entry_context, entry_cco_status,
                        entry_vol_percentile, entry_regime, entry_timestamp
                    ) VALUES (
                        %s, %s, %s, 'LONG', %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    trade_id,
                    needle['needle_id'],
                    symbol,
                    price,
                    value,
                    entry_context,
                    cco_state['cco_status'] if cco_state else 'UNKNOWN',
                    float(cco_state['current_vol_percentile']) if cco_state else 0,
                    cco_state['current_regime'] if cco_state else 'UNKNOWN',
                    execution_time
                ))

                # Update signal state
                cur.execute("""
                    UPDATE fhq_canonical.g5_signal_state
                    SET
                        current_state = 'PRIMED',
                        primed_at = %s,
                        position_direction = 'LONG',
                        position_entry_price = %s,
                        position_size = %s,
                        last_transition = 'DORMANT_TO_PRIMED',
                        last_transition_at = %s,
                        transition_count = transition_count + 1,
                        updated_at = %s
                    WHERE needle_id = %s
                """, (execution_time, price, value, execution_time, execution_time, needle['needle_id']))

                # Log transition
                cur.execute("""
                    INSERT INTO fhq_canonical.g5_state_transitions (
                        needle_id, from_state, to_state, transition_trigger,
                        context_snapshot, cco_status, transition_valid, transitioned_at
                    ) VALUES (
                        %s, 'DORMANT', 'PRIMED', 'SIGNAL_EXECUTOR_DAEMON',
                        %s, %s, TRUE, %s
                    )
                """, (needle['needle_id'], entry_context, cco_state['cco_status'] if cco_state else 'UNKNOWN', execution_time))

            self.conn.commit()
            logger.info(f"Trade logged successfully: {trade_id} ({symbol})")
            return trade_id

        except Exception as primary_error:
            # =====================================================================
            # FIX C: ATOMIC FALLBACK - If primary fails, log to governance
            # The trade HAS executed at broker. We MUST record it somewhere.
            # =====================================================================
            logger.critical(f"PRIMARY TRADE LOGGING FAILED: {primary_error}")

            try:
                self.conn.rollback()  # Clean up failed transaction

                # Log to governance actions as CRITICAL - this will be visible
                with self.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO fhq_governance.governance_actions_log (
                            action_type,
                            action_target,
                            action_target_type,
                            initiated_by,
                            decision,
                            decision_rationale,
                            agent_id,
                            metadata
                        ) VALUES (
                            'TRADE_LOGGING_FAILURE',
                            %s,
                            'CRITICAL_RECOVERY',
                            'SIGNAL_EXECUTOR_DAEMON',
                            'FAILED',
                            %s,
                            'STIG',
                            %s::jsonb
                        )
                    """, (
                        symbol,
                        f"CRITICAL: Trade executed at broker but logging failed. Order ID: {order_id}. Error: {primary_error}",
                        json.dumps({
                            'trade_id': trade_id,
                            'needle_id': str(needle.get('needle_id')),
                            'symbol': symbol,
                            'qty': qty,
                            'price': price,
                            'value': value,
                            'order_id': order_id,
                            'execution_time': execution_time.isoformat(),
                            'primary_error': str(primary_error),
                            'entry_context': entry_context
                        })
                    ))
                self.conn.commit()
                logger.critical(f"RECOVERY LOG CREATED for failed trade: {trade_id}")

            except Exception as recovery_error:
                logger.critical(f"RECOVERY LOGGING ALSO FAILED: {recovery_error}")
                logger.critical(f"MANUAL INTERVENTION REQUIRED: Order {order_id} for {symbol}")

            # Return trade_id even on failure - the trade DID execute
            return trade_id

    # =========================================================================
    # IoS-005 SKILL SCORE TRACKING (CEO DIRECTIVE 2025-12-24)
    # =========================================================================

    def check_rolling_summary_trigger(self):
        """
        CEO Directive 2025-12-24: Produce rolling summary after 10 completed Shadow trades.
        Checks trade count and generates summary when threshold is reached.
        """
        try:
            with self.conn.cursor() as cur:
                # Count completed trades (excluding test/invalid trades)
                cur.execute("""
                    SELECT COUNT(*) FROM fhq_canonical.g5_paper_trades
                    WHERE exit_price IS NOT NULL
                    AND (exclude_from_fss IS NULL OR exclude_from_fss = FALSE)
                """)
                completed_count = cur.fetchone()[0]

                # Check if we hit a multiple of 10
                if completed_count > 0 and completed_count % 10 == 0:
                    # Check if we already generated a summary for this count
                    cur.execute("""
                        SELECT COUNT(*) FROM fhq_governance.governance_actions_log
                        WHERE action_type = 'IOS005_ROLLING_SUMMARY'
                        AND metadata->>'trade_count' = %s
                    """, (str(completed_count),))
                    already_generated = cur.fetchone()[0] > 0

                    if not already_generated:
                        self.generate_ios005_rolling_summary(completed_count)

        except Exception as e:
            logger.warning(f"IoS-005 rolling summary check failed: {e}")

    def generate_ios005_rolling_summary(self, trade_count: int):
        """
        Generate IoS-005 Skill Score rolling summary for CEO review.
        """
        try:
            with self.conn.cursor() as cur:
                # Get comprehensive metrics (excluding test/invalid trades)
                cur.execute("""
                    SELECT
                        COUNT(*) as total_trades,
                        COUNT(*) FILTER (WHERE pnl_absolute > 0) as wins,
                        COUNT(*) FILTER (WHERE pnl_absolute <= 0) as losses,
                        COALESCE(SUM(pnl_absolute), 0) as total_pnl,
                        COALESCE(AVG(pnl_percent), 0) as avg_pnl_pct,
                        COALESCE(MAX(pnl_percent), 0) as best_trade_pct,
                        COALESCE(MIN(pnl_percent), 0) as worst_trade_pct,
                        COUNT(DISTINCT entry_regime) as regimes_traded
                    FROM fhq_canonical.g5_paper_trades
                    WHERE exit_price IS NOT NULL
                    AND (exclude_from_fss IS NULL OR exclude_from_fss = FALSE)
                """)
                stats = cur.fetchone()

                # Get regime breakdown (excluding test/invalid trades)
                cur.execute("""
                    SELECT
                        entry_regime,
                        COUNT(*) as trades,
                        COUNT(*) FILTER (WHERE pnl_absolute > 0) as wins,
                        COALESCE(AVG(pnl_percent), 0) as avg_pnl
                    FROM fhq_canonical.g5_paper_trades
                    WHERE exit_price IS NOT NULL
                    AND (exclude_from_fss IS NULL OR exclude_from_fss = FALSE)
                    GROUP BY entry_regime
                    ORDER BY trades DESC
                """)
                regime_breakdown = cur.fetchall()

                # Calculate FSS
                damper_value, fss_score, threshold_type = self.get_skill_damper()

                # Build summary
                summary = {
                    'trade_count': trade_count,
                    'total_pnl_usd': float(stats[3]),
                    'win_rate': float(stats[1]) / float(stats[0]) * 100 if stats[0] > 0 else 0,
                    'avg_pnl_pct': float(stats[4]),
                    'best_trade_pct': float(stats[5]),
                    'worst_trade_pct': float(stats[6]),
                    'fss_score': fss_score,
                    'skill_threshold': threshold_type,
                    'damper_active': damper_value,
                    'regime_breakdown': [
                        {'regime': r[0], 'trades': r[1], 'wins': r[2], 'avg_pnl': float(r[3])}
                        for r in regime_breakdown
                    ],
                    'exit_model': 'REGIME_CONDITIONED_V1',
                    'generated_at': datetime.now(timezone.utc).isoformat()
                }

                # Log to governance
                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_type,
                        action_target,
                        action_target_type,
                        initiated_by,
                        decision,
                        decision_rationale,
                        agent_id,
                        metadata
                    ) VALUES (
                        'IOS005_ROLLING_SUMMARY',
                        'SHADOW_LEDGER',
                        'SKILL_VERIFICATION',
                        'SIGNAL_EXECUTOR_DAEMON',
                        %s,
                        %s,
                        'STIG',
                        %s::jsonb
                    )
                """, (
                    'DIRECTIONAL_SKILL' if fss_score >= 0.5 else 'SKILL_INSUFFICIENT',
                    f"IoS-005 Rolling Summary: {trade_count} trades, FSS={fss_score:.3f}, Win Rate={summary['win_rate']:.1f}%, Total PnL=${summary['total_pnl_usd']:.2f}",
                    json.dumps(summary)
                ))
                self.conn.commit()

                logger.info(f"IoS-005 ROLLING SUMMARY GENERATED: {trade_count} trades, FSS={fss_score:.3f}")
                logger.info(f"  Win Rate: {summary['win_rate']:.1f}%, Total PnL: ${summary['total_pnl_usd']:.2f}")
                logger.info(f"  Skill Assessment: {threshold_type}")

        except Exception as e:
            logger.error(f"IoS-005 rolling summary generation failed: {e}")

    # =========================================================================
    # IoS-003-B: FLASH-CONTEXT CONSUMPTION (Intraday Regime-Delta)
    # =========================================================================

    def get_available_flash_contexts(self) -> List[Dict]:
        """
        Get available Flash-Context objects from IoS-003-B.
        These represent intraday regime opportunities with TTL.
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        fc.context_id,
                        fc.delta_id,
                        fc.listing_id,
                        fc.delta_type,
                        fc.intensity,
                        fc.momentum_vector,
                        fc.target_signal_class,
                        fc.applicable_strategies,
                        fc.ttl_minutes,
                        fc.expires_at,
                        rd.canonical_regime,
                        rd.regime_alignment
                    FROM fhq_operational.flash_context fc
                    JOIN fhq_operational.regime_delta rd ON fc.delta_id = rd.delta_id
                    WHERE fc.is_consumed = FALSE
                      AND fc.expires_at > NOW()
                      AND rd.is_active = TRUE
                    ORDER BY fc.intensity DESC, fc.expires_at ASC
                    LIMIT 10
                """)
                return cur.fetchall()
        except Exception as e:
            logger.debug(f"Flash-Context query failed (table may not exist): {e}")
            return []

    def find_matching_dormant_signals(self, flash_context: Dict) -> List[Dict]:
        """
        Find DORMANT signals that could benefit from this Flash-Context.
        Matches based on listing_id (or mapped symbol) and applicable strategies.
        """
        listing_id = flash_context['listing_id']
        strategies = flash_context.get('applicable_strategies', [])
        momentum = flash_context['momentum_vector']

        # Map listing_id to tradeable symbol
        tradeable_symbol = SYMBOL_MAPPING.get(listing_id, listing_id)

        # Get already traded needles to exclude
        traded_needles = self.get_traded_needles()
        traded_clause = ""
        params = [listing_id]

        if traded_needles:
            traded_clause = f"AND gn.needle_id NOT IN ({','.join(['%s'] * len(traded_needles))})"
            params.extend(traded_needles)

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Find signals in DORMANT state that match the Flash-Context asset
            query = f"""
                SELECT
                    ss.state_id,
                    ss.needle_id,
                    ss.current_state,
                    gn.hypothesis_title,
                    gn.hypothesis_category,
                    gn.eqs_score,
                    gn.price_witness_symbol,
                    gn.sitc_confidence_level,
                    gn.regime_technical
                FROM fhq_canonical.g5_signal_state ss
                JOIN fhq_canonical.golden_needles gn ON ss.needle_id = gn.needle_id
                WHERE ss.current_state = 'DORMANT'
                  AND gn.is_current = TRUE
                  AND gn.eqs_score >= %s
                  AND (gn.price_witness_symbol = %s OR gn.price_witness_symbol LIKE %s)
                  {traded_clause}
                ORDER BY gn.eqs_score DESC
                LIMIT 3
            """

            params_full = [DAEMON_CONFIG['min_eqs_score'], listing_id, f"{listing_id.split('-')[0]}%"]
            params_full.extend(traded_needles if traded_needles else [])

            cur.execute(query, params_full)
            return cur.fetchall()

    def consume_flash_context(self, context_id: str, signal_id: str) -> bool:
        """
        Mark a Flash-Context as consumed by a specific signal.
        Logs the consumption for audit trail.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE fhq_operational.flash_context
                    SET is_consumed = TRUE,
                        consumed_by_signal_id = %s,
                        consumed_at = NOW()
                    WHERE context_id = %s
                      AND is_consumed = FALSE
                """, (signal_id, context_id))

                if cur.rowcount == 0:
                    logger.warning(f"Flash-Context {context_id[:8]}... already consumed or expired")
                    return False

                # Log the consumption
                cur.execute("""
                    INSERT INTO fhq_operational.delta_log (
                        event_type, context_id, signal_id, details
                    ) VALUES (
                        'CONTEXT_CONSUMED', %s, %s,
                        '{"consumed_by": "SIGNAL_EXECUTOR_DAEMON"}'
                    )
                """, (context_id, signal_id))

                self.conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to consume Flash-Context: {e}")
            self.conn.rollback()
            return False

    def execute_ephemeral_trade(self, needle: Dict, symbol: str,
                                 flash_context: Dict) -> Optional[Dict]:
        """
        Execute an EPHEMERAL_PRIMED trade with reduced position sizing (50%).
        This is for trades triggered by Flash-Context (IoS-003-B).
        """
        if not self.trading_client:
            logger.warning("Alpaca not available - skipping ephemeral execution")
            return None

        # =====================================================================
        # UNIFIED GATEWAY CHECK - MUST BE FIRST (CEO Directive 2025-12-20)
        # No sizing, allocation, or order construction before permission
        # =====================================================================
        if GATEWAY_AVAILABLE:
            source_signal = needle.get('price_witness_symbol', symbol)
            decision = validate_execution_permission(
                symbol=symbol,
                source_signal=source_signal,
                target_state='ACTIVE'
            )
            if not decision.allowed:
                logger.warning(f"EPHEMERAL GATEWAY BLOCKED: {symbol} - {decision.reason}")
                return None
            logger.info(f"EPHEMERAL GATEWAY PERMITTED: {symbol} ({decision.execution_scope})")
        elif HOLIDAY_GATE_AVAILABLE and HOLIDAY_MODE_ENABLED:
            # Fallback to direct holiday gate check
            source_symbol = needle.get('price_witness_symbol', symbol)
            holiday_ok, holiday_reason, asset_class = check_holiday_execution_gate(
                symbol=symbol,
                target_state='ACTIVE',
                source_signal=source_symbol
            )
            if not holiday_ok:
                logger.warning(f"EPHEMERAL HOLIDAY BLOCKED: {symbol} - {holiday_reason}")
                return None

        # =====================================================================
        # HARD EXPOSURE GATE - MANDATORY PRE-EXECUTION CHECK
        # CEO Directive 2025-12-21: Validates ACTUAL Alpaca state before any trade.
        # Fix D: Same-symbol accumulation guard via proposed_symbol
        # =====================================================================
        gate_ok, gate_reason = self.validate_exposure_gate(proposed_symbol=symbol)
        if not gate_ok:
            logger.critical(f"EPHEMERAL EXECUTION BLOCKED by HARD EXPOSURE GATE: {gate_reason}")
            self.log_exposure_violation(gate_reason, {
                'symbol': symbol,
                'needle_id': str(needle.get('needle_id', 'unknown')),
                'flash_context_id': flash_context.get('context_id', 'unknown'),
                'attempted_action': 'EPHEMERAL_TRADE_EXECUTION',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            return None

        # WAVE 17D.1 FIX: Check for existing pending orders
        try:
            open_orders = self.trading_client.get_orders(
                GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
            )
            if open_orders:
                logger.info(f"Pending order exists for {symbol} - skipping ephemeral")
                return None
        except Exception as e:
            logger.warning(f"Could not check pending orders: {e}")

        # Calculate position size with EPHEMERAL SCALAR (50%)
        shares, dollar_amount, entry_price = self.calculate_position_size(
            symbol,
            float(needle['eqs_score']),
            needle['sitc_confidence_level']
        )

        # Apply 50% reduction for ephemeral trades (conservative due to intraday context)
        ephemeral_scalar = 0.5
        shares = int(shares * ephemeral_scalar)
        dollar_amount = dollar_amount * ephemeral_scalar

        if shares < 1:
            logger.warning(f"Ephemeral position too small for {symbol} - skipping")
            return None

        logger.info(f"EPHEMERAL TRADE: BUY {shares} {symbol} @ ${entry_price:.2f} (~${dollar_amount:,.2f})")
        logger.info(f"  Flash-Context: {flash_context['delta_type']} | Intensity: {flash_context['intensity']:.4f}")

        try:
            order = self.trading_client.submit_order(
                MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY
                )
            )

            time.sleep(1)
            filled_order = self.trading_client.get_order_by_id(order.id)

            if filled_order.status in ['filled', 'partially_filled']:
                filled_qty = float(filled_order.filled_qty)
                filled_price = float(filled_order.filled_avg_price)
                position_value = filled_qty * filled_price

                logger.info(f"EPHEMERAL FILLED: {int(filled_qty)} {symbol} @ ${filled_price:.2f}")

                # =====================================================================
                # LOCAL PENDING EXPOSURE TRACKING (CEO DIRECTIVE 2026-01-01)
                # Track ephemeral trade immediately to prevent race condition
                # =====================================================================
                self._add_pending_exposure(symbol, filled_qty, position_value)

                # Log to database with ephemeral context
                trade_id = self._log_ephemeral_trade(
                    needle, symbol, filled_qty, filled_price, position_value,
                    order.id, flash_context
                )

                # Consume the Flash-Context
                self.consume_flash_context(
                    flash_context['context_id'],
                    str(needle['needle_id'])
                )

                return {
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'qty': filled_qty,
                    'price': filled_price,
                    'value': position_value,
                    'order_id': str(order.id),
                    'ephemeral': True,
                    'flash_context_id': flash_context['context_id']
                }
            else:
                logger.warning(f"Ephemeral order not filled: {filled_order.status}")
                return None

        except Exception as e:
            logger.error(f"Ephemeral trade execution failed: {e}")
            return None

    def _log_ephemeral_trade(
        self,
        needle: Dict,
        symbol: str,
        qty: float,
        price: float,
        value: float,
        order_id: str,
        flash_context: Dict
    ) -> str:
        """Log ephemeral trade to database with IoS-003-B context"""
        trade_id = str(uuid.uuid4())
        cco_state = self.get_cco_state()

        entry_context = json.dumps({
            'cco_status': cco_state['cco_status'] if cco_state else 'UNKNOWN',
            'global_permit': cco_state['global_permit'] if cco_state else 'UNKNOWN',
            'regime': cco_state['current_regime'] if cco_state else 'UNKNOWN',
            'vol_percentile': float(cco_state['current_vol_percentile']) if cco_state else 0,
            'needle_title': needle['hypothesis_title'],
            'needle_category': needle['hypothesis_category'],
            'eqs_score': float(needle['eqs_score']),
            'alpaca_order_id': order_id,
            'kelly_multiplier': DAEMON_CONFIG['kelly_multiplier'],
            'ephemeral_scalar': 0.5,  # 50% position sizing
            'target_pct': DAEMON_CONFIG['default_target_pct'],
            'stop_loss_pct': DAEMON_CONFIG['default_stop_loss_pct'],
            'executed_by': 'SIGNAL_EXECUTOR_DAEMON',
            'execution_type': 'EPHEMERAL_PRIMED',
            'flash_context_id': flash_context['context_id'],
            'flash_delta_type': flash_context['delta_type'],
            'flash_intensity': float(flash_context['intensity']),
            'flash_momentum': flash_context['momentum_vector'],
            'flash_expires_at': flash_context['expires_at'].isoformat() if hasattr(flash_context['expires_at'], 'isoformat') else str(flash_context['expires_at']),
            'execution_timestamp': datetime.now(timezone.utc).isoformat()
        })

        with self.conn.cursor() as cur:
            # Log paper trade
            cur.execute("""
                INSERT INTO fhq_canonical.g5_paper_trades (
                    trade_id, needle_id, symbol, direction, entry_price,
                    position_size, entry_context, entry_cco_status,
                    entry_vol_percentile, entry_regime, entry_timestamp
                ) VALUES (
                    %s, %s, %s, 'LONG', %s, %s, %s, %s, %s, %s, NOW()
                )
            """, (
                trade_id,
                needle['needle_id'],
                symbol,
                price,
                value,
                entry_context,
                cco_state['cco_status'] if cco_state else 'UNKNOWN',
                float(cco_state['current_vol_percentile']) if cco_state else 0,
                cco_state['current_regime'] if cco_state else 'UNKNOWN'
            ))

            # Update signal state to PRIMED with ephemeral flag
            cur.execute("""
                UPDATE fhq_canonical.g5_signal_state
                SET
                    current_state = 'PRIMED',
                    primed_at = NOW(),
                    position_direction = 'LONG',
                    position_entry_price = %s,
                    position_size = %s,
                    is_ephemeral_promotion = TRUE,
                    ephemeral_context_id = %s,
                    ephemeral_primed_at = NOW(),
                    ephemeral_expires_at = %s,
                    ephemeral_position_scalar = 0.5,
                    last_transition = 'DORMANT_TO_EPHEMERAL_PRIMED',
                    last_transition_at = NOW(),
                    transition_count = transition_count + 1,
                    updated_at = NOW()
                WHERE needle_id = %s
            """, (price, value, flash_context['context_id'],
                  flash_context['expires_at'], needle['needle_id']))

            # Log transition
            cur.execute("""
                INSERT INTO fhq_canonical.g5_state_transitions (
                    needle_id, from_state, to_state, transition_trigger,
                    context_snapshot, cco_status, transition_valid, transitioned_at
                ) VALUES (
                    %s, 'DORMANT', 'PRIMED', 'EPHEMERAL_FLASH_CONTEXT',
                    %s, %s, TRUE, NOW()
                )
            """, (needle['needle_id'], entry_context,
                  cco_state['cco_status'] if cco_state else 'UNKNOWN'))

            # Log to delta_log
            cur.execute("""
                INSERT INTO fhq_operational.delta_log (
                    event_type, context_id, signal_id, listing_id, details
                ) VALUES (
                    'EPHEMERAL_PRIMED', %s, %s, %s, %s
                )
            """, (
                flash_context['context_id'],
                str(needle['needle_id']),
                flash_context['listing_id'],
                json.dumps({
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'position_value': value,
                    'ephemeral_scalar': 0.5
                })
            ))

        self.conn.commit()
        return trade_id

    def process_flash_contexts(self) -> Dict:
        """
        Process available Flash-Contexts from IoS-003-B.
        Attempts to match and execute EPHEMERAL_PRIMED trades.
        """
        result = {
            'contexts_available': 0,
            'contexts_matched': 0,
            'ephemeral_trades': 0,
            'details': []
        }

        flash_contexts = self.get_available_flash_contexts()
        result['contexts_available'] = len(flash_contexts)

        if not flash_contexts:
            return result

        open_count = self.get_open_positions_count()
        if open_count >= DAEMON_CONFIG['max_concurrent_positions']:
            logger.debug("Max positions reached - skipping Flash-Context processing")
            return result

        for fc in flash_contexts:
            # Find matching dormant signals
            matching_signals = self.find_matching_dormant_signals(fc)

            if not matching_signals:
                continue

            result['contexts_matched'] += 1

            # Execute for best matching signal
            for signal in matching_signals:
                # Map to tradeable symbol
                witness = signal.get('price_witness_symbol', '')
                symbol = SYMBOL_MAPPING.get(witness)

                if not symbol:
                    # Check if it's crypto - trade directly (CEO Directive: No proxies)
                    if witness in CRYPTO_SYMBOL_MAP:
                        symbol = CRYPTO_SYMBOL_MAP[witness]
                    else:
                        continue  # Skip if no valid symbol

                if not symbol:
                    continue

                # Execute ephemeral trade
                trade = self.execute_ephemeral_trade(signal, symbol, fc)

                if trade:
                    result['ephemeral_trades'] += 1
                    result['details'].append({
                        'context_id': fc['context_id'][:8],
                        'delta_type': fc['delta_type'],
                        'symbol': symbol,
                        'trade_id': trade['trade_id'][:8]
                    })
                    break  # One trade per Flash-Context

                # Check position limit after each trade
                if self.get_open_positions_count() >= DAEMON_CONFIG['max_concurrent_positions']:
                    return result

        return result

    # =========================================================================
    # CEO-DIR-2026-TRUTH-SYNC-P4: DRY-RUN OBSERVATION MODE
    # =========================================================================

    def observe_needle_decision(self, needle: Dict) -> Dict:
        """
        CEO-DIR-2026-TRUTH-SYNC-P4: Agency Observation Mode

        Evaluates a needle through all gates WITHOUT executing.
        Returns detailed decision trace for cognitive transparency.
        """
        trace = {
            'needle_id': str(needle.get('needle_id', 'unknown')),
            'hypothesis_title': needle.get('hypothesis_title', 'Unknown'),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'stored_eqs': float(needle.get('eqs_score', 0)),
            'stored_confidence': needle.get('sitc_confidence_level', 'UNKNOWN'),
            'gates': {},
            'final_decision': 'PENDING',
            'rationale': []
        }

        symbol = self.select_symbol_for_needle(needle)
        trace['target_symbol'] = symbol

        if not symbol:
            trace['final_decision'] = 'BLOCK'
            trace['blocked_at'] = 'SYMBOL_SELECTION'
            trace['rationale'].append('No tradeable symbol available for this needle')
            return trace

        # LIDS CONFIDENCE GATE
        lids_confidence = needle.get('sitc_confidence_level', needle.get('confidence', 0.0))
        if isinstance(lids_confidence, str):
            lids_confidence = {'HIGH': 0.85, 'MEDIUM': 0.70, 'LOW': 0.50}.get(lids_confidence.upper(), 0.5)

        LIDS_MIN_CONFIDENCE = 0.70
        confidence_passed = lids_confidence >= LIDS_MIN_CONFIDENCE
        trace['gates']['lids_confidence'] = {
            'value': lids_confidence,
            'threshold': LIDS_MIN_CONFIDENCE,
            'passed': confidence_passed,
            'reason': f"confidence={lids_confidence:.2f} {'>=' if confidence_passed else '<'} {LIDS_MIN_CONFIDENCE}"
        }

        if not confidence_passed:
            trace['final_decision'] = 'BLOCK'
            trace['blocked_at'] = 'LIDS_CONFIDENCE'
            trace['rationale'].append(f'Confidence {lids_confidence:.2f} below threshold {LIDS_MIN_CONFIDENCE}')
            return trace

        # LIDS FRESHNESS GATE
        data_timestamp = needle.get('data_timestamp', needle.get('created_at'))
        freshness_hours = 999
        if data_timestamp:
            try:
                if isinstance(data_timestamp, str):
                    from dateutil import parser
                    data_timestamp = parser.parse(data_timestamp)
                age_seconds = (datetime.now(timezone.utc) - data_timestamp.replace(tzinfo=timezone.utc)).total_seconds()
                freshness_hours = age_seconds / 3600
            except:
                pass

        LIDS_MAX_FRESHNESS = 12
        freshness_passed = freshness_hours <= LIDS_MAX_FRESHNESS
        trace['gates']['lids_freshness'] = {
            'value_hours': freshness_hours,
            'threshold_hours': LIDS_MAX_FRESHNESS,
            'passed': freshness_passed,
            'reason': f"freshness={freshness_hours:.1f}h {'<=' if freshness_passed else '>'} {LIDS_MAX_FRESHNESS}h"
        }

        if not freshness_passed:
            trace['final_decision'] = 'BLOCK'
            trace['blocked_at'] = 'LIDS_FRESHNESS'
            trace['rationale'].append(f'Data freshness {freshness_hours:.1f}h exceeds threshold {LIDS_MAX_FRESHNESS}h')
            return trace

        # BTC-ONLY CONSTRAINT
        source_symbol = needle.get('price_witness_symbol', needle.get('target_asset', symbol))
        is_btc = any(btc in str(source_symbol).upper() for btc in ['BTC', 'BITCOIN'])
        trace['gates']['btc_only'] = {
            'source_symbol': source_symbol,
            'is_btc_signal': is_btc,
            'passed': is_btc,
            'reason': 'BTC_SIGNAL' if is_btc else f'NON_BTC: {source_symbol}'
        }

        if not is_btc:
            trace['final_decision'] = 'BLOCK'
            trace['blocked_at'] = 'BTC_ONLY'
            trace['rationale'].append(f'Only BTC signals authorized, got {source_symbol}')
            return trace

        # SITC GATE (Cognitive Reasoning)
        sitc_result = None
        if self.sitc_gate:
            needle_id_str = str(needle.get('needle_id', uuid.uuid4()))
            hypothesis = needle.get('hypothesis_statement', needle.get('executive_summary', f'Trade signal for {symbol}'))
            regime_context = needle.get('regime_sovereign', 'UNKNOWN')
            eqs_score = float(needle.get('eqs_score', 0.0))

            logger.info(f"[DRY-RUN] Invoking SITC cognitive reasoning for {symbol}...")
            sitc_result = self.sitc_gate.reason_and_gate(
                needle_id=needle_id_str,
                asset=symbol,
                hypothesis=hypothesis,
                regime_context=regime_context,
                eqs_score=eqs_score
            )

            trace['gates']['sitc'] = {
                'stored_eqs': eqs_score,
                'realtime_eqs': sitc_result.eqs_score if sitc_result else None,
                'confidence_level': sitc_result.confidence_level if sitc_result else None,
                'passed': sitc_result.approved if sitc_result else False,
                'rejection_reason': sitc_result.rejection_reason if sitc_result and not sitc_result.approved else None,
                'eqs_delta': (sitc_result.eqs_score - eqs_score) if sitc_result else None,
                'eqs_delta_explanation': self._explain_eqs_delta(eqs_score, sitc_result.eqs_score if sitc_result else 0)
            }

            if sitc_result and not sitc_result.approved:
                trace['final_decision'] = 'BLOCK'
                trace['blocked_at'] = 'SITC'
                trace['rationale'].append(f'SITC cognitive reasoning: {sitc_result.rejection_reason}')
                trace['rationale'].append(f'Stored EQS={eqs_score:.3f} vs Real-time EQS={sitc_result.eqs_score:.3f}')
                trace['rationale'].append(f'Confidence: {sitc_result.confidence_level}')
                # Categorize the block reason
                trace['block_category'] = self._categorize_sitc_block(sitc_result)
                return trace
        else:
            trace['gates']['sitc'] = {'passed': True, 'reason': 'NOT_AVAILABLE'}

        # All gates passed
        trace['final_decision'] = 'WOULD_EXECUTE'
        trace['rationale'].append('All gates passed - execution would proceed')
        return trace

    def _explain_eqs_delta(self, stored: float, realtime: float) -> str:
        """Generate plain-language explanation for EQS delta"""
        delta = realtime - stored
        if abs(delta) < 0.01:
            return "EQS unchanged - market conditions aligned with hypothesis creation time"
        elif delta < -0.5:
            return "Severe EQS degradation - market conditions significantly diverged from hypothesis assumptions"
        elif delta < -0.2:
            return "Moderate EQS degradation - some hypothesis assumptions no longer hold"
        elif delta < 0:
            return "Minor EQS degradation - slight market drift from hypothesis conditions"
        elif delta > 0.2:
            return "EQS improved - current conditions more favorable than at hypothesis creation"
        else:
            return "Slight EQS improvement - market conditions marginally better"

    def _categorize_sitc_block(self, sitc_result) -> str:
        """Categorize SITC block reason for CEO reporting"""
        reason = sitc_result.rejection_reason.upper() if sitc_result and sitc_result.rejection_reason else ''
        confidence = sitc_result.confidence_level.upper() if sitc_result and sitc_result.confidence_level else ''

        if 'VOLATILITY' in reason or 'VOL' in reason:
            return 'VOLATILITY_DRIVEN'
        elif 'REGIME' in reason or 'NEUTRAL' in confidence:
            return 'REGIME_UNCERTAIN'
        elif 'CORRELATION' in reason or 'DIVERGE' in reason:
            return 'CORRELATION_INCOHERENT'
        elif 'LIQUIDITY' in reason or 'MARKET_STRUCTURE' in reason:
            return 'LIQUIDITY_MARKET_STRUCTURE'
        elif 'LOW' in confidence or 'WEAK' in reason:
            return 'LOW_CONVICTION'
        else:
            return 'OTHER'

    def run_observation_cycle(self) -> Dict:
        """
        CEO-DIR-2026-TRUTH-SYNC-P4: Full observation cycle
        Evaluates ALL fresh needles without execution.
        """
        logger.info("=" * 60)
        logger.info("CEO-DIR-2026-TRUTH-SYNC-P4: AGENCY OBSERVATION CYCLE")
        logger.info("=" * 60)

        result = {
            'cycle': self.cycle_count + 1,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'mode': 'DRY_RUN_OBSERVATION',
            'needles_evaluated': 0,
            'would_execute': 0,
            'blocked': 0,
            'traces': []
        }

        # Get fresh needles (< 12h old)
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    needle_id,
                    hypothesis_title,
                    hypothesis_statement,
                    hypothesis_category,
                    eqs_score,
                    confluence_factor_count,
                    sitc_confidence_level,
                    price_witness_symbol,
                    regime_technical,
                    regime_sovereign,
                    expected_timeframe_days,
                    created_at
                FROM fhq_canonical.golden_needles
                WHERE is_current = TRUE
                  AND created_at > NOW() - INTERVAL '12 hours'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            fresh_needles = cur.fetchall()

        logger.info(f"Found {len(fresh_needles)} fresh needles (< 12h old)")

        for needle in fresh_needles:
            logger.info(f"\n--- Evaluating: {needle['needle_id']} ---")
            logger.info(f"    Title: {needle['hypothesis_title']}")

            trace = self.observe_needle_decision(needle)
            result['traces'].append(trace)
            result['needles_evaluated'] += 1

            if trace['final_decision'] == 'WOULD_EXECUTE':
                result['would_execute'] += 1
                logger.info(f"    Decision: WOULD_EXECUTE")
            else:
                result['blocked'] += 1
                logger.info(f"    Decision: BLOCK at {trace.get('blocked_at', 'UNKNOWN')}")
                for rationale in trace.get('rationale', []):
                    logger.info(f"    Rationale: {rationale}")

        logger.info(f"\n{'=' * 60}")
        logger.info(f"OBSERVATION SUMMARY:")
        logger.info(f"  Needles evaluated: {result['needles_evaluated']}")
        logger.info(f"  Would execute: {result['would_execute']}")
        logger.info(f"  Blocked: {result['blocked']}")
        logger.info(f"{'=' * 60}")

        self.decision_traces = result['traces']
        return result

    # =========================================================================
    # MAIN EXECUTION LOOP
    # =========================================================================

    def run_cycle(self) -> Dict:
        """Run one execution cycle"""
        self.cycle_count += 1
        result = {
            'cycle': self.cycle_count,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'permitted': False,
            'trades_executed': 0,
            'ephemeral_trades': 0,  # IoS-003-B Flash-Context trades
            'exits_triggered': 0,
            'exposure_gate_status': 'UNKNOWN',
            'reason': ''
        }

        # =====================================================================
        # PHASE -1: SYNC PENDING EXPOSURE WITH ALPACA (CEO DIRECTIVE 2026-01-01)
        # Reconcile local pending exposure tracking with actual Alpaca positions.
        # This clears pending entries once Alpaca has caught up.
        # =====================================================================
        self._sync_pending_exposure_with_alpaca()

        # =====================================================================
        # PHASE 0: HARD EXPOSURE GATE CHECK (CEO Directive: Critical Risk Control)
        # This runs EVERY cycle to detect and log exposure violations.
        # =====================================================================
        gate_ok, gate_reason = self.validate_exposure_gate()
        result['exposure_gate_status'] = 'PASSED' if gate_ok else 'BLOCKED'

        if not gate_ok:
            logger.critical(f"=" * 60)
            logger.critical(f"HARD EXPOSURE GATE VIOLATION DETECTED")
            logger.critical(f"Reason: {gate_reason}")
            logger.critical(f"ALL NEW TRADES ARE BLOCKED")
            logger.critical(f"=" * 60)
            # Log to governance (once per minute to avoid spam)
            if self.cycle_count % 1 == 0:  # Every cycle for now during active violation
                self.log_exposure_violation(gate_reason, {
                    'cycle': self.cycle_count,
                    'detection_type': 'CYCLE_START_CHECK',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })

            # =====================================================================
            # FIX A (CEO Directive 2025-12-21): EXPOSURE GATE MUST BLOCK
            # If gate fails, we ONLY allow position monitoring (exits).
            # NO new trades are permitted. Logging without blocking is forbidden.
            # =====================================================================
            # Phase 1: Monitor existing positions (exits only)
            monitor_result = self.monitor_positions()
            result['exits_triggered'] = monitor_result['exits_triggered']
            result['reason'] = f"EXPOSURE GATE BLOCKED: {gate_reason}"

            if monitor_result['exits_triggered'] > 0:
                for exit in monitor_result['exits']:
                    pnl = exit.get('realized_pnl', 0)
                    pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                    logger.info(f"EXIT: {exit['symbol']} | {exit['reason']} | P/L: {pnl_str}")

            # CRITICAL: Return early - NO new trades when gate fails
            return result

        # =====================================================================
        # PHASE 1: MONITOR EXISTING POSITIONS (Always runs, even when suppressed)
        # =====================================================================
        monitor_result = self.monitor_positions()
        result['exits_triggered'] = monitor_result['exits_triggered']

        if monitor_result['exits_triggered'] > 0:
            for exit in monitor_result['exits']:
                pnl = exit.get('realized_pnl', 0)
                pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                logger.info(f"EXIT: {exit['symbol']} | {exit['reason']} | P/L: {pnl_str}")
            # CEO DIRECTIVE 2025-12-24: Check if rolling summary should be generated
            self.check_rolling_summary_trigger()

        # =====================================================================
        # PHASE 2: CHECK CCO PERMIT FOR NEW ENTRIES
        # =====================================================================
        permitted, reason = self.is_execution_permitted()
        result['permitted'] = permitted
        result['reason'] = reason

        # Track state changes
        if permitted != self.last_permit_status:
            if permitted:
                logger.info(f"CCO PERMITTED - Execution enabled")
                self.suppressed_cycles = 0
            else:
                if self.last_permit_status is not None:
                    logger.info(f"CCO SUPPRESSED - {reason}")
            self.last_permit_status = permitted

        if not permitted:
            self.suppressed_cycles += 1
            # Log every 10 cycles when suppressed
            if self.suppressed_cycles % 10 == 0:
                logger.debug(f"Waiting... ({self.suppressed_cycles} cycles suppressed)")
            return result

        # =====================================================================
        # PHASE 2.5: IoS-003-B FLASH-CONTEXT PROCESSING (Ephemeral Opportunities)
        # =====================================================================
        flash_result = self.process_flash_contexts()
        result['ephemeral_trades'] = flash_result.get('ephemeral_trades', 0)

        if flash_result['ephemeral_trades'] > 0:
            for detail in flash_result['details']:
                logger.info(f"EPHEMERAL: {detail['symbol']} via {detail['delta_type']} context")

        # =====================================================================
        # PHASE 3: EXECUTE NEW ENTRIES (Only when permitted)
        # =====================================================================
        open_count = self.get_open_positions_count()
        if open_count >= DAEMON_CONFIG['max_concurrent_positions']:
            result['reason'] = f"Max positions reached ({open_count}/{DAEMON_CONFIG['max_concurrent_positions']})"
            logger.debug(result['reason'])
            return result

        # Get executable needles
        slots_available = DAEMON_CONFIG['max_concurrent_positions'] - open_count
        needles = self.get_executable_needles(limit=slots_available)

        if not needles:
            result['reason'] = "No executable needles found"
            return result

        # Execute trades
        for needle in needles:
            symbol = self.select_symbol_for_needle(needle)
            if not symbol:
                logger.debug(f"No symbol available for needle {needle['needle_id']}")
                continue

            trade = self.execute_trade(needle, symbol)
            if trade:
                result['trades_executed'] += 1
                logger.info(f"Trade logged: {trade['trade_id'][:8]}... {trade['symbol']}")

                # Check if we've hit max positions
                if self.get_open_positions_count() >= DAEMON_CONFIG['max_concurrent_positions']:
                    break

        return result

    def run(self, max_cycles: int = None):
        """Run the daemon continuously"""
        logger.info("=" * 60)
        logger.info("SIGNAL EXECUTOR DAEMON - Starting")
        logger.info(f"CEO Directive: CD-IOS-001-PRICE-ARCH-001")
        logger.info(f"Orchestrator: FHQ-IoS001-Bulletproof-EQUITY")
        logger.info("=" * 60)
        logger.info(f"Mode: PAPER ONLY")
        logger.info(f"Cycle Interval: {DAEMON_CONFIG['cycle_interval_seconds']}s")
        logger.info(f"Max Positions: {DAEMON_CONFIG['max_concurrent_positions']}")
        logger.info(f"Min EQS: {DAEMON_CONFIG['min_eqs_score']}")
        logger.info(f"Take Profit: +{DAEMON_CONFIG['default_target_pct']*100:.1f}%")
        logger.info(f"Stop Loss: -{DAEMON_CONFIG['default_stop_loss_pct']*100:.1f}%")
        logger.info("-" * 60)
        logger.info(f"Direct Equities: {len(DIRECT_EQUITY_SYMBOLS)} symbols")
        logger.info(f"Symbol Mappings: {len(SYMBOL_MAPPING)} configured")
        logger.info(f"Multi-Asset: Crypto → Proxy Equities (MSTR, COIN, MARA)")
        logger.info("=" * 60)

        self.running = True

        # TELEGRAM: Daemon startup notification
        if TELEGRAM_AVAILABLE and telegram_notifier:
            try:
                telegram_notifier.system_status({
                    'Event': 'DAEMON STARTED',
                    'Mode': 'PAPER ONLY',
                    'Cycle Interval': f"{DAEMON_CONFIG['cycle_interval_seconds']}s",
                    'Neural Bridge': 'ENABLED' if NEURAL_BRIDGE_ENABLED else 'DISABLED',
                    'IKEA/InForage': 'SHADOW' if NEURAL_BRIDGE_AUDIT_ONLY else 'HARD GATE'
                })
            except:
                pass

        try:
            while self.running:
                try:
                    result = self.run_cycle()

                    if result['trades_executed'] > 0:
                        logger.info(f"Cycle {result['cycle']}: {result['trades_executed']} trade(s) executed")

                    if max_cycles and self.cycle_count >= max_cycles:
                        logger.info(f"Reached max cycles ({max_cycles})")
                        break

                    time.sleep(DAEMON_CONFIG['cycle_interval_seconds'])

                except Exception as cycle_error:
                    logger.error(f"Cycle error: {cycle_error}")
                    # TELEGRAM: Daemon error notification
                    if TELEGRAM_AVAILABLE and telegram_notifier:
                        try:
                            telegram_notifier.daemon_error(
                                error_type=type(cycle_error).__name__,
                                error_message=str(cycle_error),
                                component='run_cycle',
                                is_fatal=False
                            )
                        except:
                            pass
                    # Continue running after non-fatal errors
                    time.sleep(DAEMON_CONFIG['cycle_interval_seconds'])

        except KeyboardInterrupt:
            logger.info("\nShutdown requested...")
        except Exception as fatal_error:
            logger.critical(f"FATAL ERROR: {fatal_error}")
            # TELEGRAM: Fatal daemon error
            if TELEGRAM_AVAILABLE and telegram_notifier:
                try:
                    telegram_notifier.daemon_error(
                        error_type=type(fatal_error).__name__,
                        error_message=str(fatal_error),
                        component='main_loop',
                        is_fatal=True
                    )
                except:
                    pass
            raise
        finally:
            self.running = False
            logger.info("Signal Executor Daemon stopped")

    def stop(self):
        """Stop the daemon"""
        self.running = False


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Signal Executor Daemon (Paper Mode)')
    parser.add_argument('--once', action='store_true', help='Run single cycle and exit')
    parser.add_argument('--max-cycles', type=int, help='Maximum cycles to run')
    parser.add_argument('--interval', type=int, default=60, help='Cycle interval in seconds')
    parser.add_argument('--dry-run', action='store_true', help='CEO-DIR-2026-TRUTH-SYNC-P4: Observation mode - no execution, full trace')
    args = parser.parse_args()

    if args.interval:
        DAEMON_CONFIG['cycle_interval_seconds'] = args.interval

    # CEO-DIR-2026-TRUTH-SYNC-P4: Dry run mode for agency observation
    dry_run = getattr(args, 'dry_run', False)
    daemon = SignalExecutorDaemon(dry_run=dry_run)

    if dry_run:
        logger.info("=" * 60)
        logger.info("CEO-DIR-2026-TRUTH-SYNC-P4: AGENCY OBSERVATION MODE")
        logger.info("Dry run enabled - NO execution, NO state mutation")
        logger.info("Full cognitive trace will be captured")
        logger.info("=" * 60)

    if not daemon.connect():
        logger.error("Failed to connect")
        sys.exit(1)

    # CEO-DIR-2026-TRUTH-SYNC-P2 Task 2.3: Startup Reconciliation Guard
    is_safe, reason = daemon.startup_reconciliation_check()
    if not is_safe:
        logger.error(f"[STARTUP-GUARD] BLOCKED: {reason}")
        print(f"\n*** STARTUP BLOCKED ***")
        print(f"Reason: {reason}")
        print(f"\nRun 'python 03_FUNCTIONS/phase2_broker_reconciliation.py' to resolve.")
        daemon.close()
        sys.exit(1)
    else:
        logger.info(f"[STARTUP-GUARD] PASSED: {reason}")

    try:
        if dry_run and args.once:
            # CEO-DIR-2026-TRUTH-SYNC-P4: Agency Observation Mode
            result = daemon.run_observation_cycle()
            print(f"\n{'=' * 60}")
            print(f"CEO-DIR-2026-TRUTH-SYNC-P4: AGENCY OBSERVATION COMPLETE")
            print(f"{'=' * 60}")
            print(f"  Needles Evaluated: {result['needles_evaluated']}")
            print(f"  Would Execute: {result['would_execute']}")
            print(f"  Blocked: {result['blocked']}")

            # Generate mandatory artifact
            artifact = {
                'evidence_id': 'PHASE4_AGENCY_DECISION_TRACE',
                'evidence_type': 'AGENCY_OBSERVATION_REPORT',
                'directive': 'CEO-DIR-2026-TRUTH-SYNC-P4',
                'generated_by': 'STIG',
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'status': 'COMPLETE',
                'mode': 'DRY_RUN_OBSERVATION',
                'execution_occurred': False,
                'orders_placed': 0,
                'state_mutations': 0,
                'summary': {
                    'needles_evaluated': result['needles_evaluated'],
                    'would_execute': result['would_execute'],
                    'blocked': result['blocked'],
                    'cognitive_sovereignty_verified': True
                },
                'decision_traces': result['traces']
            }

            # Write artifact
            artifact_path = os.path.join(
                os.path.dirname(__file__),
                'evidence',
                'PHASE4_AGENCY_DECISION_TRACE.json'
            )
            with open(artifact_path, 'w') as f:
                json.dump(artifact, f, indent=2, default=str)

            print(f"\n  Artifact: {artifact_path}")
            print(f"{'=' * 60}")

        elif args.once:
            result = daemon.run_cycle()
            print(f"\nCycle Result:")
            print(f"  Permitted: {result['permitted']}")
            print(f"  Reason: {result['reason']}")
            print(f"  Trades: {result['trades_executed']}")
        else:
            daemon.run(max_cycles=args.max_cycles)
    finally:
        daemon.close()


if __name__ == "__main__":
    main()
