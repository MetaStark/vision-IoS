"""
IoS-004 Backtest Validation Worker
==================================
CEO Directive: CD-EC018-IOS004-ALPHA-PIPELINE-001
Strategic Directive: 2026.SD.04 (REV.1) - ARCHITECTURAL OVERHAUL

============================================================================
PHILOSOPHICAL MANDATE (BINDING):
"IoS-004 is not an Idea Generator or an Alpha Prover.
It is a Falsification Engine.
Its sole purpose is to reject hypotheses that fail to survive contact
with historical reality."
============================================================================

Listens on: ios004_backtest_queue (PostgreSQL NOTIFY)
Input: fhq_alpha.backtest_queue
Output: fhq_alpha.backtest_results

Authority: ZERO execution - validation only

ARCHITECTURAL CONTRACTS:
- Strategy Operational Contract (SOC) required for all strategies
- Data Availability Kill-Switch: Hard fail on missing data
- No skin-suit masquerading: Distinct hypotheses require distinct logic
- Sortino Ratio: DIAGNOSTIC ONLY (not for selection/allocation)
"""

import os
import sys
import json
import time
import select
import logging
import argparse
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, List, Tuple
import uuid
import hashlib

import psycopg2
from psycopg2.extras import RealDictCursor, Json
import numpy as np
from scipy import stats

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='[IoS-004] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('C:/fhq-market-system/vision-ios/logs/ios004_backtest_worker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Validation thresholds (from directive)
VALIDATION_THRESHOLDS = {
    'win_rate_min': 0.52,
    'sharpe_min': 0.3,
    'p_value_max': 0.05,
    'min_samples': 30,
    'profit_factor_min': 1.0
}

# =============================================================================
# CEO DIRECTIVE: CD-IOS-004-BACKTEST-HISTORY-STANDARD-001
# =============================================================================
# Default: Use FULL available canonical historical dataset (IoS-001)
# Override: Only via explicit backtest_requirements.lookback_days
# Rationale: 180-day windows produce false negatives for regime-conditioned
#            and tail-event strategies. Rare signals require long memory.
# =============================================================================
DEFAULT_LOOKBACK_DAYS = None  # None = use full available history

# =============================================================================
# IoS-005 STANDARD CONSTANTS (Alpha Lab Canonical Reference)
# =============================================================================
# These constants MUST match ios005_scientific_audit_v1.py exactly
# Any divergence is a G3 Audit violation (ADR-011)
# =============================================================================
ANNUALIZATION_FACTOR = 252  # Trading days per year
RISK_FREE_RATE = 0.02       # 2% annual (US Treasury proxy)
FRICTION_BPS_ENTRY = 5.0    # 0.05% entry cost
FRICTION_BPS_EXIT = 5.0     # 0.05% exit cost
TOTAL_FRICTION_BPS = FRICTION_BPS_ENTRY + FRICTION_BPS_EXIT  # 10 bps round trip

# =============================================================================
# CROSS-ASSET CANONICAL INSTRUMENTS (IoS-001 Verified)
# =============================================================================
# Only instruments verified to exist in fhq_meta.assets with FULL_HISTORY
# GLD is NOT available - excluded per IoS-001 check 2025-12-16
# =============================================================================
CROSS_ASSET_CRYPTO = ['BTC-USD', 'ETH-USD', 'SOL-USD']
CROSS_ASSET_EQUITY = ['QQQ', 'SPY']  # GLD excluded - not in registry

# =============================================================================
# BIAS PROTECTION: Look-Ahead Guard
# =============================================================================
# All signal generation MUST use data from T-1 (previous day close)
# This constant documents the lag requirement - enforced in code
# =============================================================================
SIGNAL_LAG_DAYS = 1  # Signals use yesterday's close, trade at today's open

# =============================================================================
# STRATEGIC DIRECTIVE 2026.SD.04: STRATEGY OPERATIONAL CONTRACT (SOC)
# =============================================================================
# MANDATE A: No strategy may be executed without a formally validated SOC.
# If two strategies have distinct hypothesis_id but identical trigger_function_hash,
# this raises a Governance Exception (Class B pre-execution, Class A post-execution).
# =============================================================================

def _trigger_generic_mean_reversion(prices, indicators, params, regime_by_date):
    """
    STRATEGY_GENERIC_MEAN_REVERSION_V1
    Baseline control: 7-day trend + 3-day pullback pattern.
    This is the ONLY generic timing strategy. All others must be distinct.
    """
    trades = []
    holding_days = params['holding_days']
    threshold_pct = params['threshold_pct'] / 100
    stop_loss_pct = params['stop_loss_pct'] / 100
    take_profit_pct = params['take_profit_pct'] / 100

    for i in range(30, len(prices) - holding_days - 1):
        price_date = str(prices[i]['price_date'])
        current_regime = regime_by_date.get(price_date, 'NEUTRAL')

        if params['regime_filter'] and current_regime not in params['regime_filter']:
            continue

        entry_price = float(prices[i]['close_price'])
        returns_3d = (entry_price - float(prices[i-3]['close_price'])) / float(prices[i-3]['close_price'])
        returns_7d = (entry_price - float(prices[i-7]['close_price'])) / float(prices[i-7]['close_price']) if i >= 7 else 0

        if returns_7d > threshold_pct * 2 and returns_3d < 0:
            trades.append({
                'entry_idx': i,
                'direction': 'LONG',
                'entry_price': entry_price,
                'pattern': 'PULLBACK_BUY',
                'returns_7d': returns_7d,
                'returns_3d': returns_3d
            })
        elif returns_7d < -threshold_pct * 2 and returns_3d > 0:
            trades.append({
                'entry_idx': i,
                'direction': 'SHORT',
                'entry_price': entry_price,
                'pattern': 'RALLY_SELL',
                'returns_7d': returns_7d,
                'returns_3d': returns_3d
            })
    return trades


def _trigger_weekend_liquidity_gap(prices, indicators, params, regime_by_date):
    """
    STRATEGY_WEEKEND_LIQUIDITY_GAP_V1
    EXPLICIT CALENDAR LOGIC - trades Friday-Monday gaps only.
    This is NOT the generic timing pattern. It uses date.weekday().

    Logic:
    - Friday close vs Monday open gap detection
    - Trade the gap fade (mean reversion to Friday's range)
    - Entry: Monday if gap > threshold
    - Exit: Gap closure or time-based
    """
    trades = []
    holding_days = params['holding_days']
    gap_threshold_pct = params.get('gap_threshold_pct', 2.0) / 100  # Default 2% gap

    for i in range(5, len(prices) - holding_days - 1):
        price_date = prices[i]['price_date']

        # EXPLICIT CALENDAR CHECK - This is what makes this strategy DISTINCT
        if hasattr(price_date, 'weekday'):
            weekday = price_date.weekday()
        else:
            from datetime import datetime as dt
            if isinstance(price_date, str):
                price_date_obj = dt.strptime(str(price_date)[:10], '%Y-%m-%d')
            else:
                price_date_obj = price_date
            weekday = price_date_obj.weekday()

        # Only trade on Monday (weekday == 0)
        if weekday != 0:
            continue

        # Find Friday (should be i-3 for Mon, but weekends may be missing)
        friday_idx = None
        for j in range(1, 5):
            if i - j >= 0:
                prev_date = prices[i-j]['price_date']
                if hasattr(prev_date, 'weekday'):
                    prev_weekday = prev_date.weekday()
                else:
                    prev_date_obj = dt.strptime(str(prev_date)[:10], '%Y-%m-%d') if isinstance(prev_date, str) else prev_date
                    prev_weekday = prev_date_obj.weekday()
                if prev_weekday == 4:  # Friday
                    friday_idx = i - j
                    break

        if friday_idx is None:
            continue

        friday_close = float(prices[friday_idx]['close_price'])
        monday_open = float(prices[i]['open_price']) if 'open_price' in prices[i] else float(prices[i]['close_price'])

        # Calculate weekend gap
        gap_pct = (monday_open - friday_close) / friday_close

        current_regime = regime_by_date.get(str(prices[i]['price_date']), 'NEUTRAL')
        if params['regime_filter'] and current_regime not in params['regime_filter']:
            continue

        # Gap up > threshold: SHORT (fade the gap)
        if gap_pct > gap_threshold_pct:
            trades.append({
                'entry_idx': i,
                'direction': 'SHORT',
                'entry_price': monday_open,
                'pattern': 'GAP_UP_FADE',
                'gap_pct': gap_pct * 100,
                'friday_close': friday_close,
                'monday_open': monday_open,
                'weekday': 'MONDAY'
            })
        # Gap down > threshold: LONG (fade the gap)
        elif gap_pct < -gap_threshold_pct:
            trades.append({
                'entry_idx': i,
                'direction': 'LONG',
                'entry_price': monday_open,
                'pattern': 'GAP_DOWN_FADE',
                'gap_pct': gap_pct * 100,
                'friday_close': friday_close,
                'monday_open': monday_open,
                'weekday': 'MONDAY'
            })

    return trades


# Strategy Operational Contract Registry
# Each entry is a formal contract between hypothesis intent and execution logic
STRATEGY_REGISTRY = {
    'STRATEGY_GENERIC_MEAN_REVERSION_V1': {
        'trigger_function': _trigger_generic_mean_reversion,
        'trigger_function_hash': hashlib.sha256(b'_trigger_generic_mean_reversion_v1_7d3d_pullback').hexdigest(),
        'trigger_signature': ['returns_7d', 'returns_3d', 'threshold_pct', 'regime'],
        'required_data_assets': ['PRICE'],  # Only needs price data
        'expected_trade_profile': {
            'frequency_band': 'LOW',  # ~10-20 trades/year
            'directional_bias': 'NEUTRAL',
            'holding_regime': 'DAYS'
        },
        'description': 'Baseline control strategy. 7-day trend with 3-day pullback.'
    },
    'STRATEGY_WEEKEND_LIQUIDITY_GAP_V1': {
        'trigger_function': _trigger_weekend_liquidity_gap,
        'trigger_function_hash': hashlib.sha256(b'_trigger_weekend_liquidity_gap_v1_calendar_based').hexdigest(),
        'trigger_signature': ['weekday', 'gap_pct', 'friday_close', 'monday_open'],
        'required_data_assets': ['PRICE', 'CALENDAR'],
        'expected_trade_profile': {
            'frequency_band': 'LOW',  # ~50 trades/year (52 weeks)
            'directional_bias': 'MEAN_REVERSION',
            'holding_regime': 'DAYS'
        },
        'description': 'Calendar-based gap fade. DISTINCT from generic timing.'
    }
}

# Mapping from hypothesis categories to registered strategies
# MANDATE: Unknown categories MUST fail, not fall through to generic
CATEGORY_TO_STRATEGY = {
    'TIMING': 'STRATEGY_GENERIC_MEAN_REVERSION_V1',  # Explicit baseline
    'WEEKEND_GAP': 'STRATEGY_WEEKEND_LIQUIDITY_GAP_V1',
}

# Strategies requiring data not in IoS-001 - FROZEN per directive
FROZEN_STRATEGIES = [
    'OPTIONS_FLOW',      # Requires options data - not available
    'DEFCON_TRANSITION', # Requires DEFCON state history - to be implemented
    'SENTIMENT',         # Requires sentiment data - not available
    'VIX_CORRELATION',   # Requires VIX data - not in IoS-001
]


def convert_numpy(value):
    """Convert numpy types to Python native types for database storage."""
    if isinstance(value, (np.integer, np.int32, np.int64)):
        return int(value)
    elif isinstance(value, (np.floating, np.float32, np.float64)):
        return float(value)
    elif isinstance(value, np.ndarray):
        return value.tolist()
    elif isinstance(value, np.bool_):
        return bool(value)
    elif value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    elif isinstance(value, (datetime, timedelta)):
        return value.isoformat() if hasattr(value, 'isoformat') else str(value)
    return value


def make_json_safe(obj):
    """Make object JSON serializable by converting dates and numpy types."""
    from datetime import date as date_type
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    elif isinstance(obj, (datetime, date_type)):
        return obj.isoformat()
    elif isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj


class IoS004BacktestWorker:
    """Backtest validation worker for alpha hypotheses."""

    def __init__(self):
        self.conn = None
        self.listen_conn = None
        self.worker_id = f"ios004-{uuid.uuid4().hex[:8]}"

    def connect(self):
        """Connect to database."""
        conn_params = {
            'host': os.environ.get('PGHOST', '127.0.0.1'),
            'port': os.environ.get('PGPORT', '54322'),
            'database': os.environ.get('PGDATABASE', 'postgres'),
            'user': os.environ.get('PGUSER', 'postgres'),
            'password': os.environ.get('PGPASSWORD', 'postgres')
        }

        self.conn = psycopg2.connect(**conn_params)
        self.conn.autocommit = True

        # Separate connection for LISTEN (must be in autocommit mode)
        self.listen_conn = psycopg2.connect(**conn_params)
        self.listen_conn.autocommit = True

        logger.info(f"Database connected - Worker ID: {self.worker_id}")

    def close(self):
        """Close database connections."""
        if self.conn:
            self.conn.close()
        if self.listen_conn:
            self.listen_conn.close()

    def check_price_data_availability(self, asset_id: str) -> Dict[str, Any]:
        """
        Check if price data exists for an asset and return coverage info.

        CANONICAL SOURCE: fhq_market.prices (1.16M rows, 470 assets)
        This is the SINGLE source of truth for price data.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as rows,
                    MIN(timestamp)::date as first_date,
                    MAX(timestamp)::date as last_date
                FROM fhq_market.prices
                WHERE canonical_id = %s
            """, (asset_id,))
            result = cur.fetchone()

        if result['rows'] > 0:
            return {
                'available': True,
                'canonical_id': asset_id,
                'rows': result['rows'],
                'first_date': result['first_date'],
                'last_date': result['last_date'],
                'reason': None
            }

        return {
            'available': False,
            'canonical_id': asset_id,
            'rows': 0,
            'first_date': None,
            'last_date': None,
            'reason': f'No price data in fhq_market.prices for {asset_id}'
        }

    def get_price_data(self, asset_id: str = 'BTC-USD', days: Optional[int] = DEFAULT_LOOKBACK_DAYS) -> List[Dict]:
        """
        Get historical price data for backtesting.

        CEO Directive CD-IOS-004-BACKTEST-HISTORY-STANDARD-001:
        - days=None (default): Use FULL available canonical history
        - days=N: Explicit override, must be justified in backtest_requirements

        CANONICAL SOURCE: fhq_market.prices (1.16M rows, 470 assets)
        This is the SINGLE source of truth for price data.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            if days is None:
                cur.execute("""
                    SELECT
                        DATE(timestamp) as price_date,
                        open as open_price,
                        high as high_price,
                        low as low_price,
                        close as close_price,
                        volume
                    FROM fhq_market.prices
                    WHERE canonical_id = %s
                    ORDER BY timestamp ASC
                """, (asset_id,))
            else:
                cur.execute("""
                    SELECT
                        DATE(timestamp) as price_date,
                        open as open_price,
                        high as high_price,
                        low as low_price,
                        close as close_price,
                        volume
                    FROM fhq_market.prices
                    WHERE canonical_id = %s
                      AND timestamp >= CURRENT_DATE - INTERVAL '%s days'
                    ORDER BY timestamp ASC
                """, (asset_id, days))
            return cur.fetchall()

    def get_regime_history(self, asset_id: str = 'BTC-USD', days: Optional[int] = DEFAULT_LOOKBACK_DAYS) -> List[Dict]:
        """
        Get historical regime classifications.

        CEO Directive CD-IOS-004-BACKTEST-HISTORY-STANDARD-001:
        - days=None (default): Use FULL available regime history
        - days=N: Explicit override
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                if days is None:
                    # FULL HISTORY MODE
                    cur.execute("""
                        SELECT
                            DATE(timestamp) as date,
                            sovereign_regime as regime,
                            (state_probabilities->sovereign_regime)::float as confidence
                        FROM fhq_perception.sovereign_regime_state_v4
                        WHERE asset_id = %s
                        ORDER BY timestamp ASC
                    """, (asset_id,))
                else:
                    # EXPLICIT OVERRIDE MODE
                    cur.execute("""
                        SELECT
                            DATE(timestamp) as date,
                            sovereign_regime as regime,
                            (state_probabilities->sovereign_regime)::float as confidence
                        FROM fhq_perception.sovereign_regime_state_v4
                        WHERE asset_id = %s
                          AND timestamp >= CURRENT_DATE - INTERVAL '%s days'
                        ORDER BY timestamp ASC
                    """, (asset_id, days))
                return cur.fetchall()
            except Exception as e:
                logger.warning(f"Regime history query failed: {e}")
                return []

    def get_cross_asset_data(self, target_asset: str, days: Optional[int] = None) -> Dict[str, List[Dict]]:
        """
        Fetch price data for cross-asset analysis.

        IoS-001 VERIFIED INSTRUMENTS (2025-12-16):
        - Crypto: BTC-USD (8163 rows), ETH-USD (3594), SOL-USD (2841)
        - Equity: QQQ (3701), SPY (3700)
        - GLD: NOT IN REGISTRY - excluded

        Returns dict mapping asset_id -> price list
        """
        cross_asset_data = {}

        # Determine which cross-assets to fetch based on target
        if target_asset in CROSS_ASSET_CRYPTO or target_asset.endswith('-USD'):
            # Crypto target: fetch other crypto + equity proxies
            assets_to_fetch = [a for a in CROSS_ASSET_CRYPTO if a != target_asset]
            assets_to_fetch.extend(CROSS_ASSET_EQUITY)
        else:
            # Equity target: fetch crypto for correlation
            assets_to_fetch = CROSS_ASSET_CRYPTO + [a for a in CROSS_ASSET_EQUITY if a != target_asset]

        logger.info(f"Fetching cross-asset data for: {assets_to_fetch}")

        for asset_id in assets_to_fetch:
            try:
                prices = self.get_price_data(asset_id=asset_id, days=days)
                if prices:
                    cross_asset_data[asset_id] = prices
                    logger.info(f"  {asset_id}: {len(prices)} rows")
            except Exception as e:
                logger.warning(f"Could not fetch {asset_id}: {e}")

        return cross_asset_data

    def calculate_indicators(self, prices: List[Dict]) -> Dict[str, np.ndarray]:
        """Calculate technical indicators for backtesting."""
        if not prices:
            return {}

        close = np.array([float(p['close_price']) for p in prices])
        high = np.array([float(p['high_price']) for p in prices])
        low = np.array([float(p['low_price']) for p in prices])
        volume = np.array([float(p['volume'] or 0) for p in prices])

        indicators = {
            'close': close,
            'high': high,
            'low': low,
            'volume': volume,
            'returns': np.diff(close) / close[:-1] if len(close) > 1 else np.array([]),
        }

        # RSI (14-period)
        if len(close) >= 15:
            delta = np.diff(close)
            gain = np.where(delta > 0, delta, 0)
            loss = np.where(delta < 0, -delta, 0)

            avg_gain = np.convolve(gain, np.ones(14)/14, mode='valid')
            avg_loss = np.convolve(loss, np.ones(14)/14, mode='valid')

            rs = np.where(avg_loss != 0, avg_gain / avg_loss, 100)
            rsi = 100 - (100 / (1 + rs))
            indicators['rsi'] = np.concatenate([np.full(14, np.nan), rsi])

        # Bollinger Bands (20-period)
        if len(close) >= 20:
            sma20 = np.convolve(close, np.ones(20)/20, mode='valid')
            std20 = np.array([np.std(close[i:i+20]) for i in range(len(close)-19)])
            indicators['bb_upper'] = np.concatenate([np.full(19, np.nan), sma20 + 2*std20])
            indicators['bb_lower'] = np.concatenate([np.full(19, np.nan), sma20 - 2*std20])
            indicators['bb_width'] = np.concatenate([np.full(19, np.nan), 4*std20 / sma20])

        # Volatility (20-day)
        if len(close) >= 21:
            returns = np.diff(close) / close[:-1]
            vol = np.array([np.std(returns[max(0,i-19):i+1]) for i in range(len(returns))])
            indicators['volatility'] = np.concatenate([np.full(1, np.nan), vol])

        return indicators

    def extract_params_from_hypothesis(self, statement: str, backtest_req: Dict) -> Dict:
        """
        Extract trading parameters from hypothesis statement and backtest requirements.
        Returns a dict with thresholds, holding periods, and conditions.
        """
        import re
        params = {
            'threshold_pct': 5.0,      # Default: 5% move trigger
            'holding_days': 3,          # Default: 3 day hold
            'stop_loss_pct': 5.0,       # Default: 5% stop
            'take_profit_pct': 10.0,    # Default: 10% take profit
            'volatility_threshold': 40, # Default: 40% vol threshold
            'rsi_oversold': 30,         # Default RSI levels
            'rsi_overbought': 70,
            'zscore_threshold': 2.0,    # Default z-score threshold
            'regime_filter': [],
            'lookback_period': 20,
        }

        # Extract from backtest_requirements
        if isinstance(backtest_req, dict):
            params['regime_filter'] = backtest_req.get('regime_filter', [])
            params['lookback_days'] = backtest_req.get('lookback_days', 180)

            # Parse exit conditions
            exit_conds = backtest_req.get('exit_conditions', {})
            if isinstance(exit_conds, dict):
                # Time exit: "7 trading days", "10 days"
                time_exit = exit_conds.get('time_exit', '')
                time_match = re.search(r'(\d+)\s*(?:trading\s+)?days?', str(time_exit))
                if time_match:
                    params['holding_days'] = int(time_match.group(1))

                # Stop loss: "5% loss", "4%"
                stop_loss = exit_conds.get('stop_loss', '')
                stop_match = re.search(r'(\d+(?:\.\d+)?)\s*%', str(stop_loss))
                if stop_match:
                    params['stop_loss_pct'] = float(stop_match.group(1))

                # Take profit: "10% gain", "8%"
                take_profit = exit_conds.get('take_profit', '')
                tp_match = re.search(r'(\d+(?:\.\d+)?)\s*%', str(take_profit))
                if tp_match:
                    params['take_profit_pct'] = float(tp_match.group(1))

        # Extract percentages from statement
        statement_lower = statement.lower() if statement else ''

        # Look for specific patterns
        # "5%+ single-day gain" or "5% move"
        pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%\+?\s*(?:single-day|daily|move|gain|drop)', statement_lower)
        if pct_match:
            params['threshold_pct'] = float(pct_match.group(1))

        # "volatility below 40%"
        vol_match = re.search(r'volatility\s*(?:below|under|<)\s*(\d+(?:\.\d+)?)\s*%', statement_lower)
        if vol_match:
            params['volatility_threshold'] = float(vol_match.group(1))

        # "2 standard deviations" or "z-score > 2"
        zscore_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:standard deviations?|std)', statement_lower)
        if zscore_match:
            params['zscore_threshold'] = float(zscore_match.group(1))

        # "next 3 days" or "within 5 days"
        days_match = re.search(r'(?:next|within|following)\s*(\d+)\s*(?:trading\s+)?days?', statement_lower)
        if days_match:
            params['holding_days'] = int(days_match.group(1))

        # "30-day rolling" lookback
        lookback_match = re.search(r'(\d+)-day\s*(?:rolling|average|mean)', statement_lower)
        if lookback_match:
            params['lookback_period'] = int(lookback_match.group(1))

        return params

    def simulate_signals(self, proposal: Dict, prices: List[Dict], indicators: Dict,
                         cross_asset_data: Optional[Dict[str, List[Dict]]] = None) -> List[Dict]:
        """
        SOC-COMPLIANT Signal Simulation (Strategic Directive 2026.SD.04)
        ================================================================

        ARCHITECTURAL CONTRACT:
        1. Strategy must be registered in STRATEGY_REGISTRY
        2. Data availability is verified (MANDATE B Kill-Switch)
        3. No skin-suit masquerading - distinct hypotheses use distinct logic
        4. Unknown categories HARD FAIL (no fallback to generic)

        Returns empty list with logged error on compliance failure.
        """
        if not prices or len(prices) < 30:
            return []

        hypothesis_id = proposal.get('hypothesis_id', 'UNKNOWN')
        title = proposal.get('hypothesis_title', '').lower()
        statement = proposal.get('hypothesis_statement', '').lower()
        category = proposal.get('hypothesis_category', proposal.get('category', 'UNKNOWN'))

        # =====================================================================
        # MANDATE B: DATA AVAILABILITY KILL-SWITCH
        # =====================================================================
        # Check if strategy requires data not available in IoS-001
        # HARD FAIL - no defaults, no fallbacks, no warnings
        # =====================================================================
        frozen_keywords = {
            'OPTIONS_FLOW': ['options flow', 'option', 'put/call', 'open interest'],
            'DEFCON_TRANSITION': ['defcon', 'defcon-5', 'defcon-4', 'defcon transition'],
            'SENTIMENT': ['sentiment', 'fear', 'greed', 'social'],
            'VIX_CORRELATION': ['vix', 'volatility index', 'vix-btc'],
        }

        for frozen_type, keywords in frozen_keywords.items():
            if any(kw in title or kw in statement for kw in keywords):
                logger.error(f"KILL-SWITCH: {hypothesis_id} requires {frozen_type} data (NOT AVAILABLE)")
                logger.error(f"Strategy FROZEN per Strategic Directive 2026.SD.04 MANDATE B")
                return []  # HARD FAIL - return empty trades

        # =====================================================================
        # STRATEGY DETERMINATION - SOC Registry Lookup
        # =====================================================================
        # Determine which registered strategy to use based on hypothesis content
        # NOT based on generic category mapping alone
        # =====================================================================
        strategy_key = None

        # Check for explicit strategy patterns in hypothesis
        if 'weekend' in title or 'weekend gap' in statement or 'friday' in statement or 'monday' in statement:
            strategy_key = 'STRATEGY_WEEKEND_LIQUIDITY_GAP_V1'
            logger.info(f"SOC: Matched {hypothesis_id} -> WEEKEND_GAP (calendar-based)")
        elif category in CATEGORY_TO_STRATEGY:
            strategy_key = CATEGORY_TO_STRATEGY[category]
            logger.info(f"SOC: Matched {hypothesis_id} -> {strategy_key} via category {category}")
        else:
            # MANDATE: Unknown categories MUST fail, not fall through
            logger.error(f"SOC VIOLATION: {hypothesis_id} has unknown category '{category}'")
            logger.error(f"No registered strategy for this category. HARD FAIL per MANDATE A.")
            return []

        if strategy_key not in STRATEGY_REGISTRY:
            logger.error(f"SOC VIOLATION: Strategy {strategy_key} not in registry")
            return []

        strategy_contract = STRATEGY_REGISTRY[strategy_key]
        logger.info(f"SOC Contract: {strategy_key}")
        logger.info(f"  - Hash: {strategy_contract['trigger_function_hash'][:16]}...")
        logger.info(f"  - Signature: {strategy_contract['trigger_signature']}")
        logger.info(f"  - Required Data: {strategy_contract['required_data_assets']}")

        # =====================================================================
        # EXECUTE REGISTERED TRIGGER FUNCTION
        # =====================================================================
        backtest_req = proposal.get('backtest_requirements', {})
        if isinstance(backtest_req, str):
            try:
                backtest_req = json.loads(backtest_req)
            except:
                backtest_req = {}

        params = self.extract_params_from_hypothesis(statement, backtest_req)
        regimes = self.get_regime_history()
        regime_by_date = {str(r['date']): r['regime'] for r in regimes}

        logger.info(f"Executing trigger function for {hypothesis_id}")
        trigger_fn = strategy_contract['trigger_function']
        raw_signals = trigger_fn(prices, indicators, params, regime_by_date)

        logger.info(f"Trigger generated {len(raw_signals)} raw signals")

        # =====================================================================
        # PROCESS SIGNALS: Apply exits with GAP RISK SIMULATION
        # =====================================================================
        # MANDATE D: Exit prices reflect worst-case fill between
        # theoretical stop-loss price and next available market price
        # =====================================================================
        trades = []
        holding_days = params['holding_days']
        stop_loss_pct = params['stop_loss_pct'] / 100
        take_profit_pct = params['take_profit_pct'] / 100

        for signal in raw_signals:
            entry_idx = signal['entry_idx']
            direction = signal['direction']
            entry_price = signal['entry_price']

            # Simulate exit with gap risk
            exit_idx, exit_price, exit_reason = self._simulate_exit_with_gap_risk(
                prices, entry_idx, holding_days, direction, stop_loss_pct, take_profit_pct
            )

            if exit_idx >= len(prices):
                continue

            # Calculate P&L
            if direction == 'LONG':
                pnl_pct = (exit_price - entry_price) / entry_price * 100
            else:
                pnl_pct = (entry_price - exit_price) / entry_price * 100

            trade = {
                'entry_date': prices[entry_idx]['price_date'],
                'exit_date': prices[exit_idx]['price_date'],
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl_pct': pnl_pct,
                'holding_hours': (exit_idx - entry_idx) * 24,
                'exit_reason': exit_reason,
                'strategy': strategy_key,
                'soc_hash': strategy_contract['trigger_function_hash'][:16]
            }

            # Copy signal-specific metadata
            for key in ['pattern', 'gap_pct', 'returns_7d', 'returns_3d', 'weekday']:
                if key in signal:
                    trade[key] = signal[key]

            trades.append(trade)

        # =====================================================================
        # TRANSACTION COSTS (IoS-005 Standard: 10 bps round trip)
        # =====================================================================
        for trade in trades:
            raw_pnl = trade['pnl_pct']
            friction_cost = TOTAL_FRICTION_BPS / 100
            trade['pnl_pct'] = raw_pnl - friction_cost
            trade['friction_applied_bps'] = TOTAL_FRICTION_BPS

        # =====================================================================
        # NO TRADE CAP - Let strategy dictate natural frequency
        # =====================================================================
        logger.info(f"Final trade count for {hypothesis_id}: {len(trades)}")
        return trades

    def _simulate_exit_with_gap_risk(self, prices: List[Dict], entry_idx: int,
                                      holding_days: int, direction: str,
                                      stop_loss_pct: float, take_profit_pct: float
                                      ) -> Tuple[int, float, str]:
        """
        Exit simulation with GAP RISK (MANDATE D).

        Models adverse overnight and discontinuous price moves.
        Exit price = WORST of:
          - Theoretical stop-loss price
          - Actual next available market price (simulates gaps)
        """
        entry_price = float(prices[entry_idx]['close_price'])
        max_exit_idx = min(entry_idx + holding_days, len(prices) - 1)

        for i in range(entry_idx + 1, max_exit_idx + 1):
            current_price = float(prices[i]['close_price'])

            # Get high/low for gap simulation if available
            day_high = float(prices[i].get('high_price', current_price))
            day_low = float(prices[i].get('low_price', current_price))

            if direction == 'LONG':
                # Stop loss check with gap risk
                stop_price = entry_price * (1 - stop_loss_pct)
                if day_low <= stop_price:
                    # GAP RISK: Exit at worse of stop price or day low
                    exit_price = min(stop_price, day_low)
                    return i, exit_price, 'STOP_LOSS_GAP'

                # Take profit check
                if day_high >= entry_price * (1 + take_profit_pct):
                    return i, entry_price * (1 + take_profit_pct), 'TAKE_PROFIT'
            else:  # SHORT
                # Stop loss check with gap risk
                stop_price = entry_price * (1 + stop_loss_pct)
                if day_high >= stop_price:
                    # GAP RISK: Exit at worse of stop price or day high
                    exit_price = max(stop_price, day_high)
                    return i, exit_price, 'STOP_LOSS_GAP'

                # Take profit check
                if day_low <= entry_price * (1 - take_profit_pct):
                    return i, entry_price * (1 - take_profit_pct), 'TAKE_PROFIT'

        # Time exit
        return max_exit_idx, float(prices[max_exit_idx]['close_price']), 'TIME_EXIT'

    def _legacy_simulate_signals_DEPRECATED(self, proposal: Dict, prices: List[Dict], indicators: Dict,
                         cross_asset_data: Optional[Dict[str, List[Dict]]] = None) -> List[Dict]:
        """
        DEPRECATED: Legacy signal simulation - DO NOT USE
        Kept only for reference during transition period.
        Will be removed after vertical slice validation passes.
        """
        # This is the old simulate_signals code preserved for reference
        if not prices or len(prices) < 30:
            return []

        trades = []
        category = proposal.get('hypothesis_category', proposal.get('category', 'UNKNOWN'))
        statement = proposal.get('hypothesis_statement', '')
        backtest_req = proposal.get('backtest_requirements', {})

        if isinstance(backtest_req, str):
            try:
                backtest_req = json.loads(backtest_req)
            except:
                backtest_req = {}

        params = self.extract_params_from_hypothesis(statement, backtest_req)
        regimes = self.get_regime_history()
        regime_by_date = {str(r['date']): r['regime'] for r in regimes}

        holding_days = params['holding_days']
        threshold_pct = params['threshold_pct'] / 100
        stop_loss_pct = params['stop_loss_pct'] / 100
        take_profit_pct = params['take_profit_pct'] / 100

        # Legacy REGIME_EDGE handling
        if category == 'REGIME_EDGE':
            lookback = params['lookback_period']
            vol_threshold = params['volatility_threshold'] / 100

            for i in range(max(30, lookback), len(prices) - holding_days - 1):
                price_date = str(prices[i]['price_date'])
                current_regime = regime_by_date.get(price_date, 'NEUTRAL')

                # Check regime filter
                if params['regime_filter'] and current_regime not in params['regime_filter']:
                    continue

                entry_price = float(prices[i]['close_price'])

                # Calculate realized volatility
                if len(volatility) > i and not np.isnan(volatility[i]):
                    current_vol = volatility[i] * np.sqrt(252)  # Annualized
                else:
                    continue

                # Check Bollinger Band breakout
                if len(bb_upper) > i and not np.isnan(bb_upper[i]):
                    # Bullish: price breaks above upper BB + low volatility
                    if entry_price > bb_upper[i] and current_vol < vol_threshold:
                        # Simulate with stop-loss and take-profit
                        exit_idx, exit_price, exit_reason = self._simulate_exit_with_stops(
                            prices, i, holding_days, 'LONG', stop_loss_pct, take_profit_pct
                        )
                        pnl_pct = (exit_price - entry_price) / entry_price * 100

                        trades.append({
                            'entry_date': prices[i]['price_date'],
                            'exit_date': prices[exit_idx]['price_date'],
                            'direction': 'LONG',
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'pnl_pct': pnl_pct,
                            'holding_hours': (exit_idx - i) * 24,
                            'regime': current_regime,
                            'exit_reason': exit_reason
                        })

                    # Bearish: price breaks below lower BB
                    elif len(bb_lower) > i and entry_price < bb_lower[i]:
                        exit_idx, exit_price, exit_reason = self._simulate_exit_with_stops(
                            prices, i, holding_days, 'SHORT', stop_loss_pct, take_profit_pct
                        )
                        pnl_pct = (entry_price - exit_price) / entry_price * 100

                        trades.append({
                            'entry_date': prices[i]['price_date'],
                            'exit_date': prices[exit_idx]['price_date'],
                            'direction': 'SHORT',
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'pnl_pct': pnl_pct,
                            'holding_hours': (exit_idx - i) * 24,
                            'regime': current_regime,
                            'exit_reason': exit_reason
                        })

        # ======================================================================
        # CATEGORY: MOMENTUM
        # Uses threshold-based momentum with hypothesis-specific thresholds
        # ======================================================================
        elif category == 'MOMENTUM':
            for i in range(30, len(prices) - holding_days - 1):
                price_date = str(prices[i]['price_date'])
                current_regime = regime_by_date.get(price_date, 'NEUTRAL')

                # Check regime filter
                if params['regime_filter'] and current_regime not in params['regime_filter']:
                    continue

                # Calculate daily return
                daily_return = (float(prices[i]['close_price']) - float(prices[i-1]['close_price'])) / float(prices[i-1]['close_price'])

                entry_price = float(prices[i]['close_price'])

                # Trigger on threshold move (hypothesis-specific)
                if daily_return > threshold_pct:
                    # Momentum continuation - go LONG
                    exit_idx, exit_price, exit_reason = self._simulate_exit_with_stops(
                        prices, i, holding_days, 'LONG', stop_loss_pct, take_profit_pct
                    )
                    pnl_pct = (exit_price - entry_price) / entry_price * 100

                    trades.append({
                        'entry_date': prices[i]['price_date'],
                        'exit_date': prices[exit_idx]['price_date'],
                        'direction': 'LONG',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'holding_hours': (exit_idx - i) * 24,
                        'trigger_return': daily_return * 100,
                        'exit_reason': exit_reason
                    })

                elif daily_return < -threshold_pct:
                    # Momentum continuation - go SHORT
                    exit_idx, exit_price, exit_reason = self._simulate_exit_with_stops(
                        prices, i, holding_days, 'SHORT', stop_loss_pct, take_profit_pct
                    )
                    pnl_pct = (entry_price - exit_price) / entry_price * 100

                    trades.append({
                        'entry_date': prices[i]['price_date'],
                        'exit_date': prices[exit_idx]['price_date'],
                        'direction': 'SHORT',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'holding_hours': (exit_idx - i) * 24,
                        'trigger_return': daily_return * 100,
                        'exit_reason': exit_reason
                    })

        # ======================================================================
        # CATEGORY: MEAN_REVERSION
        # Uses z-score or RSI with hypothesis-specific thresholds
        # ======================================================================
        elif category == 'MEAN_REVERSION':
            zscore_threshold = params['zscore_threshold']
            lookback = params['lookback_period']

            for i in range(max(30, lookback), len(prices) - holding_days - 1):
                price_date = str(prices[i]['price_date'])
                current_regime = regime_by_date.get(price_date, 'NEUTRAL')

                # Check regime filter
                if params['regime_filter'] and current_regime not in params['regime_filter']:
                    continue

                entry_price = float(prices[i]['close_price'])

                # Calculate z-score of price relative to rolling mean
                price_window = close[max(0, i-lookback):i+1]
                if len(price_window) >= lookback:
                    mean_price = np.mean(price_window[:-1])
                    std_price = np.std(price_window[:-1])
                    if std_price > 0:
                        zscore = (entry_price - mean_price) / std_price
                    else:
                        continue
                else:
                    continue

                # Mean reversion: fade extreme z-scores
                if zscore > zscore_threshold:
                    # Overbought - go SHORT expecting reversion
                    exit_idx, exit_price, exit_reason = self._simulate_exit_with_stops(
                        prices, i, holding_days, 'SHORT', stop_loss_pct, take_profit_pct
                    )
                    pnl_pct = (entry_price - exit_price) / entry_price * 100

                    trades.append({
                        'entry_date': prices[i]['price_date'],
                        'exit_date': prices[exit_idx]['price_date'],
                        'direction': 'SHORT',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'holding_hours': (exit_idx - i) * 24,
                        'zscore': zscore,
                        'exit_reason': exit_reason
                    })

                elif zscore < -zscore_threshold:
                    # Oversold - go LONG expecting reversion
                    exit_idx, exit_price, exit_reason = self._simulate_exit_with_stops(
                        prices, i, holding_days, 'LONG', stop_loss_pct, take_profit_pct
                    )
                    pnl_pct = (exit_price - entry_price) / entry_price * 100

                    trades.append({
                        'entry_date': prices[i]['price_date'],
                        'exit_date': prices[exit_idx]['price_date'],
                        'direction': 'LONG',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'holding_hours': (exit_idx - i) * 24,
                        'zscore': zscore,
                        'exit_reason': exit_reason
                    })

        # ======================================================================
        # CATEGORY: TIMING
        # Uses time-based patterns with regime context
        # ======================================================================
        elif category == 'TIMING':
            for i in range(30, len(prices) - holding_days - 1):
                price_date = str(prices[i]['price_date'])
                current_regime = regime_by_date.get(price_date, 'NEUTRAL')

                # Check regime filter
                if params['regime_filter'] and current_regime not in params['regime_filter']:
                    continue

                entry_price = float(prices[i]['close_price'])

                # Multi-day momentum pattern
                returns_3d = (entry_price - float(prices[i-3]['close_price'])) / float(prices[i-3]['close_price'])
                returns_7d = (entry_price - float(prices[i-7]['close_price'])) / float(prices[i-7]['close_price']) if i >= 7 else 0

                # Timing signal: short-term reversal after multi-day trend
                if returns_7d > threshold_pct * 2 and returns_3d < 0:
                    # Pullback after uptrend - buy the dip
                    exit_idx, exit_price, exit_reason = self._simulate_exit_with_stops(
                        prices, i, holding_days, 'LONG', stop_loss_pct, take_profit_pct
                    )
                    pnl_pct = (exit_price - entry_price) / entry_price * 100

                    trades.append({
                        'entry_date': prices[i]['price_date'],
                        'exit_date': prices[exit_idx]['price_date'],
                        'direction': 'LONG',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'holding_hours': (exit_idx - i) * 24,
                        'pattern': 'PULLBACK_BUY',
                        'exit_reason': exit_reason
                    })

                elif returns_7d < -threshold_pct * 2 and returns_3d > 0:
                    # Bounce after downtrend - sell the rally
                    exit_idx, exit_price, exit_reason = self._simulate_exit_with_stops(
                        prices, i, holding_days, 'SHORT', stop_loss_pct, take_profit_pct
                    )
                    pnl_pct = (entry_price - exit_price) / entry_price * 100

                    trades.append({
                        'entry_date': prices[i]['price_date'],
                        'exit_date': prices[exit_idx]['price_date'],
                        'direction': 'SHORT',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'holding_hours': (exit_idx - i) * 24,
                        'pattern': 'RALLY_SELL',
                        'exit_reason': exit_reason
                    })

        # ======================================================================
        # CATEGORY: CROSS_ASSET (FIXED - Actually uses cross-asset data)
        # ======================================================================
        # CEO DIRECTIVE: Cross-asset strategies MUST use actual cross-asset data
        # Bug fix 2025-12-16: Previous implementation only used single asset
        #
        # VALID CROSS-ASSET INSTRUMENTS (IoS-001 verified):
        # - Crypto: BTC-USD, ETH-USD, SOL-USD
        # - Equity: QQQ, SPY
        # - GLD: NOT AVAILABLE (excluded)
        #
        # STRATEGIES:
        # 1. BTC-ETH Spread: Trade divergence between BTC and ETH
        # 2. Crypto-Equity Relative Strength: Trade crypto vs QQQ/SPY
        # 3. Cross-Asset Volatility Divergence: Vol regime disagreements
        # ======================================================================
        elif category == 'CROSS_ASSET':
            # Require cross-asset data - no silent fallback to broken single-asset
            if not cross_asset_data:
                logger.warning("CROSS_ASSET strategy requires cross_asset_data - returning empty")
                # Return empty trades to trigger INSUFFICIENT_DATA, not fake results
                pass  # Fall through to return empty trades
            else:
                # Build date-indexed price lookup for cross-assets
                cross_prices_by_date = {}
                for asset_id, asset_prices in cross_asset_data.items():
                    for p in asset_prices:
                        date_key = str(p['price_date'])
                        if date_key not in cross_prices_by_date:
                            cross_prices_by_date[date_key] = {}
                        cross_prices_by_date[date_key][asset_id] = float(p['close_price'])

                # Determine strategy variant from hypothesis title/statement
                statement_lower = proposal.get('hypothesis_statement', '').lower()
                title_lower = proposal.get('hypothesis_title', '').lower()

                # Strategy 1: BTC-ETH Spread Trading
                if 'eth' in statement_lower or 'btc-eth' in title_lower or 'pairs' in statement_lower:
                    logger.info("CROSS_ASSET variant: BTC-ETH Spread")
                    for i in range(30, len(prices) - holding_days - 1):
                        price_date = str(prices[i]['price_date'])
                        current_regime = regime_by_date.get(price_date, 'NEUTRAL')

                        if params['regime_filter'] and current_regime not in params['regime_filter']:
                            continue

                        # Get cross-asset prices for this date
                        cross_today = cross_prices_by_date.get(price_date, {})
                        if 'ETH-USD' not in cross_today:
                            continue

                        target_price = float(prices[i]['close_price'])
                        eth_price = cross_today['ETH-USD']

                        # Calculate BTC/ETH ratio momentum
                        target_5d = float(prices[i-5]['close_price']) if i >= 5 else target_price
                        date_5d = str(prices[i-5]['price_date']) if i >= 5 else price_date
                        cross_5d = cross_prices_by_date.get(date_5d, {})
                        eth_5d = cross_5d.get('ETH-USD', eth_price)

                        ratio_now = target_price / eth_price if eth_price > 0 else 1
                        ratio_5d = target_5d / eth_5d if eth_5d > 0 else ratio_now
                        ratio_change = (ratio_now - ratio_5d) / ratio_5d if ratio_5d > 0 else 0

                        # Mean reversion on ratio divergence
                        if abs(ratio_change) > threshold_pct:
                            # Ratio expanded = short target (expect convergence)
                            direction = 'SHORT' if ratio_change > 0 else 'LONG'

                            exit_idx, exit_price, exit_reason = self._simulate_exit_with_stops(
                                prices, i + ENTRY_DELAY, holding_days, direction, stop_loss_pct, take_profit_pct
                            )
                            entry_price = float(prices[min(i + ENTRY_DELAY, len(prices)-1)]['close_price'])

                            if direction == 'LONG':
                                pnl_pct = (exit_price - entry_price) / entry_price * 100
                            else:
                                pnl_pct = (entry_price - exit_price) / entry_price * 100

                            trades.append({
                                'entry_date': prices[min(i + ENTRY_DELAY, len(prices)-1)]['price_date'],
                                'exit_date': prices[exit_idx]['price_date'],
                                'direction': direction,
                                'entry_price': entry_price,
                                'exit_price': exit_price,
                                'pnl_pct': pnl_pct,
                                'holding_hours': (exit_idx - i - ENTRY_DELAY) * 24,
                                'cross_asset': 'ETH-USD',
                                'ratio_change': ratio_change,
                                'exit_reason': exit_reason
                            })

                # Strategy 2: Crypto vs Equity Relative Strength
                elif 'qqq' in statement_lower or 'spy' in statement_lower or 'equity' in statement_lower or 'defensive' in title_lower:
                    logger.info("CROSS_ASSET variant: Crypto-Equity Relative Strength")
                    for i in range(30, len(prices) - holding_days - 1):
                        price_date = str(prices[i]['price_date'])
                        current_regime = regime_by_date.get(price_date, 'NEUTRAL')

                        if params['regime_filter'] and current_regime not in params['regime_filter']:
                            continue

                        cross_today = cross_prices_by_date.get(price_date, {})
                        equity_proxy = cross_today.get('QQQ') or cross_today.get('SPY')
                        if not equity_proxy:
                            continue

                        target_price = float(prices[i]['close_price'])
                        target_5d = float(prices[i-5]['close_price']) if i >= 5 else target_price
                        date_5d = str(prices[i-5]['price_date']) if i >= 5 else price_date
                        cross_5d = cross_prices_by_date.get(date_5d, {})
                        equity_5d = cross_5d.get('QQQ') or cross_5d.get('SPY') or equity_proxy

                        # Relative strength: crypto vs equity
                        crypto_return = (target_price - target_5d) / target_5d if target_5d > 0 else 0
                        equity_return = (equity_proxy - equity_5d) / equity_5d if equity_5d > 0 else 0
                        relative_strength = crypto_return - equity_return

                        # Momentum on relative strength
                        if abs(relative_strength) > threshold_pct:
                            direction = 'LONG' if relative_strength > 0 else 'SHORT'

                            exit_idx, exit_price, exit_reason = self._simulate_exit_with_stops(
                                prices, i + ENTRY_DELAY, holding_days, direction, stop_loss_pct, take_profit_pct
                            )
                            entry_price = float(prices[min(i + ENTRY_DELAY, len(prices)-1)]['close_price'])

                            if direction == 'LONG':
                                pnl_pct = (exit_price - entry_price) / entry_price * 100
                            else:
                                pnl_pct = (entry_price - exit_price) / entry_price * 100

                            trades.append({
                                'entry_date': prices[min(i + ENTRY_DELAY, len(prices)-1)]['price_date'],
                                'exit_date': prices[exit_idx]['price_date'],
                                'direction': direction,
                                'entry_price': entry_price,
                                'exit_price': exit_price,
                                'pnl_pct': pnl_pct,
                                'holding_hours': (exit_idx - i - ENTRY_DELAY) * 24,
                                'cross_asset': 'QQQ/SPY',
                                'relative_strength': relative_strength,
                                'exit_reason': exit_reason
                            })

                # Strategy 3: Cross-Asset Volatility Divergence
                else:
                    logger.info("CROSS_ASSET variant: Cross-Asset Volatility Regime")
                    for i in range(30, len(prices) - holding_days - 1):
                        price_date = str(prices[i]['price_date'])
                        current_regime = regime_by_date.get(price_date, 'NEUTRAL')

                        if params['regime_filter'] and current_regime not in params['regime_filter']:
                            continue

                        cross_today = cross_prices_by_date.get(price_date, {})
                        eth_price = cross_today.get('ETH-USD')
                        sol_price = cross_today.get('SOL-USD')

                        if not eth_price and not sol_price:
                            continue

                        target_price = float(prices[i]['close_price'])

                        # Calculate multi-asset momentum consensus
                        target_5d = float(prices[i-5]['close_price']) if i >= 5 else target_price
                        target_ret = (target_price - target_5d) / target_5d if target_5d > 0 else 0

                        date_5d = str(prices[i-5]['price_date']) if i >= 5 else price_date
                        cross_5d = cross_prices_by_date.get(date_5d, {})

                        cross_rets = []
                        if eth_price:
                            eth_5d = cross_5d.get('ETH-USD', eth_price)
                            cross_rets.append((eth_price - eth_5d) / eth_5d if eth_5d > 0 else 0)
                        if sol_price:
                            sol_5d = cross_5d.get('SOL-USD', sol_price)
                            cross_rets.append((sol_price - sol_5d) / sol_5d if sol_5d > 0 else 0)

                        avg_cross_ret = np.mean(cross_rets) if cross_rets else 0
                        divergence = target_ret - avg_cross_ret

                        # Trade divergence from cross-asset consensus
                        if abs(divergence) > threshold_pct:
                            # Target diverged negatively = buy (expect catch-up)
                            direction = 'LONG' if divergence < -threshold_pct else 'SHORT'

                            exit_idx, exit_price, exit_reason = self._simulate_exit_with_stops(
                                prices, i + ENTRY_DELAY, holding_days, direction, stop_loss_pct, take_profit_pct
                            )
                            entry_price = float(prices[min(i + ENTRY_DELAY, len(prices)-1)]['close_price'])

                            if direction == 'LONG':
                                pnl_pct = (exit_price - entry_price) / entry_price * 100
                            else:
                                pnl_pct = (entry_price - exit_price) / entry_price * 100

                            trades.append({
                                'entry_date': prices[min(i + ENTRY_DELAY, len(prices)-1)]['price_date'],
                                'exit_date': prices[exit_idx]['price_date'],
                                'direction': direction,
                                'entry_price': entry_price,
                                'exit_price': exit_price,
                                'pnl_pct': pnl_pct,
                                'holding_hours': (exit_idx - i - ENTRY_DELAY) * 24,
                                'cross_asset': 'ETH+SOL consensus',
                                'divergence': divergence,
                                'exit_reason': exit_reason
                            })

        # ======================================================================
        # CATEGORY: VOLATILITY
        # Volatility compression/expansion strategies
        # ======================================================================
        elif category == 'VOLATILITY':
            for i in range(30, len(prices) - holding_days - 1):
                if len(bb_width) <= i or np.isnan(bb_width[i]):
                    continue

                price_date = str(prices[i]['price_date'])
                current_regime = regime_by_date.get(price_date, 'NEUTRAL')

                if params['regime_filter'] and current_regime not in params['regime_filter']:
                    continue

                entry_price = float(prices[i]['close_price'])
                avg_width = np.nanmean(bb_width[max(0,i-20):i])

                # Compression detected
                if bb_width[i] < avg_width * 0.7:
                    # Determine direction from recent momentum
                    recent_return = (entry_price - float(prices[i-3]['close_price'])) / float(prices[i-3]['close_price'])
                    direction = 'LONG' if recent_return > 0 else 'SHORT'

                    exit_idx, exit_price, exit_reason = self._simulate_exit_with_stops(
                        prices, i, holding_days, direction, stop_loss_pct, take_profit_pct
                    )

                    if direction == 'LONG':
                        pnl_pct = (exit_price - entry_price) / entry_price * 100
                    else:
                        pnl_pct = (entry_price - exit_price) / entry_price * 100

                    trades.append({
                        'entry_date': prices[i]['price_date'],
                        'exit_date': prices[exit_idx]['price_date'],
                        'direction': direction,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'holding_hours': (exit_idx - i) * 24,
                        'bb_compression': bb_width[i] / avg_width,
                        'exit_reason': exit_reason
                    })

        # ======================================================================
        # DEFAULT: Unknown category - conservative approach
        # ======================================================================
        else:
            logger.warning(f"Unknown category '{category}' - using RSI mean reversion")

            for i in range(30, len(prices) - holding_days - 1):
                if len(rsi) <= i or np.isnan(rsi[i]):
                    continue

                entry_price = float(prices[i]['close_price'])

                if rsi[i] < params['rsi_oversold']:
                    exit_idx, exit_price, exit_reason = self._simulate_exit_with_stops(
                        prices, i, holding_days, 'LONG', stop_loss_pct, take_profit_pct
                    )
                    pnl_pct = (exit_price - entry_price) / entry_price * 100

                    trades.append({
                        'entry_date': prices[i]['price_date'],
                        'exit_date': prices[exit_idx]['price_date'],
                        'direction': 'LONG',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'holding_hours': (exit_idx - i) * 24,
                        'rsi': rsi[i],
                        'exit_reason': exit_reason
                    })

                elif rsi[i] > params['rsi_overbought']:
                    exit_idx, exit_price, exit_reason = self._simulate_exit_with_stops(
                        prices, i, holding_days, 'SHORT', stop_loss_pct, take_profit_pct
                    )
                    pnl_pct = (entry_price - exit_price) / entry_price * 100

                    trades.append({
                        'entry_date': prices[i]['price_date'],
                        'exit_date': prices[exit_idx]['price_date'],
                        'direction': 'SHORT',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl_pct,
                        'holding_hours': (exit_idx - i) * 24,
                        'rsi': rsi[i],
                        'exit_reason': exit_reason
                    })

        # =====================================================================
        # TRANSACTION COSTS (IoS-005 Standard: 10 bps round trip)
        # =====================================================================
        # Apply realistic friction to all trades before returning
        # CEO Directive: No frictionless backtests - that's how systems lie
        # =====================================================================
        for trade in trades:
            raw_pnl = trade['pnl_pct']
            # Apply entry + exit friction (10 bps total = 0.10%)
            friction_cost = TOTAL_FRICTION_BPS / 100  # Convert bps to percentage
            trade['pnl_pct'] = raw_pnl - friction_cost
            trade['friction_applied_bps'] = TOTAL_FRICTION_BPS

        # =====================================================================
        # TRADE CAP: Increased from 100 to 10,000
        # =====================================================================
        # Previous: 100 trades (caused artificial sample size limitation)
        # Fix: 10,000 cap (statistical validity requires large N)
        # Rationale: 100 trades over 10 years = ~10/year = meaningless sample
        # =====================================================================
        return trades[:10000]

    def extract_target_asset(self, proposal: Dict) -> str:
        """
        Extract the target asset from a hypothesis proposal.

        Parses hypothesis_title, hypothesis_statement, and backtest_requirements
        to determine which asset the hypothesis targets.

        Returns the canonical asset_id (e.g., 'BTC-USD', 'SOL-USD', 'AAPL')

        Priority:
        1. Explicit asset_id in backtest_requirements
        2. First crypto asset mentioned in title (subject asset)
        3. First crypto asset mentioned in statement
        4. Default BTC-USD for crypto context
        """
        import re

        # Known crypto assets
        crypto_assets = [
            'BTC', 'ETH', 'SOL', 'ADA', 'DOGE', 'XRP', 'DOT', 'LINK', 'AVAX',
            'MATIC', 'UNI', 'ATOM', 'LTC', 'BCH', 'ALGO', 'XLM', 'FIL', 'NEAR',
            'ICP', 'AAVE', 'MKR', 'SNX', 'COMP', 'SUSHI', 'YFI', 'CRV', 'BAL'
        ]

        title = proposal.get('hypothesis_title', '') or ''
        statement = proposal.get('hypothesis_statement', '') or ''

        # Check backtest_requirements for explicit asset
        backtest_req = proposal.get('backtest_requirements', {})
        if isinstance(backtest_req, str):
            try:
                backtest_req = json.loads(backtest_req)
            except:
                backtest_req = {}

        if isinstance(backtest_req, dict):
            explicit_asset = backtest_req.get('asset_id') or backtest_req.get('asset')
            if explicit_asset:
                return explicit_asset

        # Find FIRST crypto asset mentioned in title (by position)
        # This prioritizes the subject asset over trigger conditions
        title_upper = title.upper()
        found_in_title = []
        for asset in crypto_assets:
            match = re.search(rf'\b{asset}\b', title_upper)
            if match:
                found_in_title.append((match.start(), asset))

        if found_in_title:
            # Return the asset that appears FIRST in the title
            found_in_title.sort(key=lambda x: x[0])
            first_asset = found_in_title[0][1]
            logger.info(f"Extracted target asset from title: {first_asset}-USD (position {found_in_title[0][0]})")
            return f'{first_asset}-USD'

        # Search statement if nothing found in title
        statement_upper = statement.upper()
        found_in_statement = []
        for asset in crypto_assets:
            match = re.search(rf'\b{asset}\b', statement_upper)
            if match:
                found_in_statement.append((match.start(), asset))

        if found_in_statement:
            found_in_statement.sort(key=lambda x: x[0])
            first_asset = found_in_statement[0][1]
            logger.info(f"Extracted target asset from statement: {first_asset}-USD")
            return f'{first_asset}-USD'

        # Search for equity tickers (assume uppercase 1-5 char followed by context)
        search_text = f"{title} {statement}".upper()
        equity_match = re.search(r'\b([A-Z]{1,5})\s+(?:stock|equity|shares?)', search_text)
        if equity_match:
            return equity_match.group(1)

        # Default to BTC for crypto-related or generic hypotheses
        if any(term in search_text for term in ['CRYPTO', 'BITCOIN', 'REGIME', 'MARKET']):
            logger.info(f"Defaulting to BTC-USD for crypto/market context")
            return 'BTC-USD'

        # Truly unknown - default to BTC
        logger.warning(f"Could not extract target asset from hypothesis, defaulting to BTC-USD")
        return 'BTC-USD'

    def _simulate_exit_with_stops(self, prices: List[Dict], entry_idx: int,
                                   max_hold_days: int, direction: str,
                                   stop_loss_pct: float, take_profit_pct: float) -> Tuple[int, float, str]:
        """
        Simulate exit with stop-loss and take-profit.
        Returns (exit_idx, exit_price, exit_reason)
        """
        entry_price = float(prices[entry_idx]['close_price'])

        for day in range(1, max_hold_days + 1):
            exit_idx = min(entry_idx + day, len(prices) - 1)
            current_price = float(prices[exit_idx]['close_price'])
            high_price = float(prices[exit_idx]['high_price'])
            low_price = float(prices[exit_idx]['low_price'])

            if direction == 'LONG':
                # Check stop-loss (using low)
                if (entry_price - low_price) / entry_price >= stop_loss_pct:
                    return exit_idx, entry_price * (1 - stop_loss_pct), 'STOP_LOSS'
                # Check take-profit (using high)
                if (high_price - entry_price) / entry_price >= take_profit_pct:
                    return exit_idx, entry_price * (1 + take_profit_pct), 'TAKE_PROFIT'
            else:  # SHORT
                # Check stop-loss (using high)
                if (high_price - entry_price) / entry_price >= stop_loss_pct:
                    return exit_idx, entry_price * (1 + stop_loss_pct), 'STOP_LOSS'
                # Check take-profit (using low)
                if (entry_price - low_price) / entry_price >= take_profit_pct:
                    return exit_idx, entry_price * (1 - take_profit_pct), 'TAKE_PROFIT'

        # Time exit
        final_idx = min(entry_idx + max_hold_days, len(prices) - 1)
        return final_idx, float(prices[final_idx]['close_price']), 'TIME_EXIT'

    def calculate_backtest_metrics(self, trades: List[Dict]) -> Dict[str, Any]:
        """Calculate backtest performance metrics."""
        if not trades:
            return {
                'total_signals': 0,
                'winning_signals': 0,
                'losing_signals': 0,
                'win_rate': 0,
                'total_return_pct': 0,
                'avg_return_bps': 0,
                'median_return_bps': 0,
                'std_return_bps': 0,
                'sharpe_ratio': 0,
                'sortino_ratio': 0,
                'profit_factor': 0,
                'max_drawdown_pct': 0,
                'avg_drawdown_pct': 0,
                'avg_holding_period_hours': 0,
                'max_holding_period_hours': 0,
                'p_value': 1.0,
                't_statistic': 0,
                'validation_outcome': 'INSUFFICIENT_DATA',
                'rejection_reason': 'No trades generated'
            }

        pnl_array = np.array([t['pnl_pct'] for t in trades])
        holding_hours = np.array([t['holding_hours'] for t in trades])

        total = len(trades)
        winners = sum(1 for t in trades if t['pnl_pct'] > 0)
        losers = total - winners
        win_rate = winners / total if total > 0 else 0

        # Return metrics
        avg_return = np.mean(pnl_array)
        median_return = np.median(pnl_array)
        std_return = np.std(pnl_array) if len(pnl_array) > 1 else 0
        total_return = np.sum(pnl_array)

        # =====================================================================
        # IoS-005 COMPLIANT SHARPE/SORTINO CALCULATION
        # =====================================================================
        # For trade-based backtesting, we must:
        # 1. Estimate trades per year from actual data
        # 2. Annualize mean return properly
        # 3. Subtract risk-free rate
        # 4. Annualize volatility properly
        # =====================================================================

        # Calculate actual trading frequency from data
        if len(trades) >= 2:
            first_date = trades[0]['entry_date']
            last_date = trades[-1]['entry_date']
            # Handle both string and date objects
            if isinstance(first_date, str):
                from datetime import datetime as dt
                first_date = dt.fromisoformat(first_date.replace('Z', '+00:00')).date() if 'T' in first_date else dt.strptime(first_date, '%Y-%m-%d').date()
                last_date = dt.fromisoformat(last_date.replace('Z', '+00:00')).date() if 'T' in last_date else dt.strptime(last_date, '%Y-%m-%d').date()
            days_span = (last_date - first_date).days
            trades_per_year = (len(trades) / days_span * 365) if days_span > 0 else len(trades)
        else:
            trades_per_year = len(trades)

        # Annualized mean return (IoS-005 standard)
        annualized_mean = avg_return * trades_per_year / 100  # Convert from % to decimal

        # Annualized volatility (IoS-005 standard: std * sqrt(periods))
        annualized_std = (std_return / 100) * np.sqrt(trades_per_year) if trades_per_year > 0 else 0

        # Sharpe ratio with risk-free rate (IoS-005 STANDARD)
        excess_return = annualized_mean - RISK_FREE_RATE
        if annualized_std > 0:
            sharpe = excess_return / annualized_std
        else:
            sharpe = 0

        # =====================================================================
        # Sortino ratio - DIAGNOSTIC ONLY (MANDATE D)
        # =====================================================================
        # Strategic Directive 2026.SD.04: Sortino is DOWNGRADED to diagnostic.
        # SHALL NOT be used for: Strategy selection, Capital allocation, Alpha validation
        # Rationale: Sample size < 500, fixed stop-loss regime artificially suppresses
        # downside variance, making Sortino unreliable for comparison.
        # =====================================================================
        downside_returns = pnl_array[pnl_array < 0]
        if len(downside_returns) > 0:
            downside_std = (np.std(downside_returns) / 100) * np.sqrt(trades_per_year)
            sortino = excess_return / downside_std if downside_std > 0 else 0
        else:
            sortino = sharpe  # No downside = same as Sharpe
        # FLAG: sortino_is_diagnostic = True (stored in return dict)

        # Profit factor
        gross_profit = sum(t['pnl_pct'] for t in trades if t['pnl_pct'] > 0)
        gross_loss = abs(sum(t['pnl_pct'] for t in trades if t['pnl_pct'] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Max drawdown
        cumulative = np.cumsum(pnl_array)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0

        # Statistical significance (t-test against 0)
        if len(pnl_array) >= 2:
            t_stat, p_value = stats.ttest_1samp(pnl_array, 0)
        else:
            t_stat, p_value = 0, 1.0

        # Holding period
        avg_holding = np.mean(holding_hours)
        max_holding = np.max(holding_hours)

        # Determine validation outcome
        outcome = 'VALIDATED'
        rejection_reasons = []

        if total < VALIDATION_THRESHOLDS['min_samples']:
            outcome = 'INSUFFICIENT_DATA'
            rejection_reasons.append(f"Only {total} samples (min: {VALIDATION_THRESHOLDS['min_samples']})")
        elif win_rate < VALIDATION_THRESHOLDS['win_rate_min']:
            outcome = 'REJECTED'
            rejection_reasons.append(f"Win rate {win_rate:.2%} < {VALIDATION_THRESHOLDS['win_rate_min']:.2%}")
        elif sharpe < VALIDATION_THRESHOLDS['sharpe_min']:
            outcome = 'REJECTED'
            rejection_reasons.append(f"Sharpe {sharpe:.2f} < {VALIDATION_THRESHOLDS['sharpe_min']}")
        elif p_value > VALIDATION_THRESHOLDS['p_value_max']:
            outcome = 'REJECTED'
            rejection_reasons.append(f"P-value {p_value:.4f} > {VALIDATION_THRESHOLDS['p_value_max']}")

        # Cap extreme values to prevent database overflow
        def cap_value(val, max_abs=9999):
            if val is None or np.isnan(val) or np.isinf(val):
                return 0
            return max(-max_abs, min(max_abs, val))

        return {
            'total_signals': total,
            'winning_signals': winners,
            'losing_signals': losers,
            'win_rate': win_rate,
            'total_return_pct': cap_value(total_return, 9999),
            'avg_return_bps': cap_value(avg_return * 100, 9999),  # Convert to bps
            'median_return_bps': cap_value(median_return * 100, 9999),
            'std_return_bps': cap_value(std_return * 100, 9999),
            'sharpe_ratio': cap_value(sharpe, 999),
            'sortino_ratio': cap_value(sortino, 999),
            'profit_factor': cap_value(profit_factor, 999),
            'max_drawdown_pct': cap_value(max_drawdown, 9999),
            'avg_drawdown_pct': cap_value(np.mean(drawdowns) if len(drawdowns) > 0 else 0, 9999),
            'avg_holding_period_hours': cap_value(avg_holding, 99999),
            'max_holding_period_hours': cap_value(max_holding, 99999),
            'p_value': cap_value(p_value, 1.0),
            't_statistic': cap_value(t_stat, 999),
            'validation_outcome': outcome,
            'rejection_reason': '; '.join(rejection_reasons) if rejection_reasons else None
        }

    def run_backtest(self, proposal_id: str) -> Dict[str, Any]:
        """Run backtest for a single proposal."""
        start_time = datetime.now()

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get proposal details
            cur.execute("""
                SELECT * FROM fhq_alpha.g0_draft_proposals
                WHERE proposal_id = %s
            """, (proposal_id,))
            proposal = cur.fetchone()

            if not proposal:
                return {'success': False, 'error': 'Proposal not found'}

        hypothesis_id = proposal['hypothesis_id']
        logger.info(f"Running backtest for {hypothesis_id}")

        # =====================================================================
        # SOC PRE-VALIDATION (HARD GATE - Strategic Directive 2026.SD.04)
        # =====================================================================
        # MANDATE A: No strategy may execute without validated SOC binding.
        # This check happens BEFORE any processing.
        # =====================================================================
        category = proposal.get('hypothesis_category', 'UNKNOWN')
        title = (proposal.get('hypothesis_title') or '').lower()
        statement = (proposal.get('hypothesis_statement') or '').lower()

        # Determine strategy key (same logic as simulate_signals)
        soc_strategy_key = None
        if 'weekend' in title or 'weekend gap' in statement or 'friday' in statement:
            soc_strategy_key = 'STRATEGY_WEEKEND_LIQUIDITY_GAP_V1'
        elif category in CATEGORY_TO_STRATEGY:
            soc_strategy_key = CATEGORY_TO_STRATEGY[category]

        if soc_strategy_key is None or soc_strategy_key not in STRATEGY_REGISTRY:
            error_msg = f"SOC VIOLATION: {hypothesis_id} has no valid SOC binding (category={category})"
            logger.error(error_msg)
            logger.error("HARD FAIL per Strategic Directive 2026.SD.04 MANDATE A")

            # Store SOC violation as INSUFFICIENT_DATA
            with self.conn.cursor() as cur2:
                result_id = str(uuid.uuid4())
                cur2.execute("""
                    INSERT INTO fhq_alpha.backtest_results (
                        result_id, proposal_id, lookback_days,
                        total_signals, winning_signals, losing_signals, win_rate,
                        total_return_pct, sharpe_ratio, validation_outcome, rejection_reason,
                        backtest_completed_at, duration_seconds
                    ) VALUES (%s, %s, 0, 0, 0, 0, 0, 0, 0, 'SOC_VIOLATION', %s, NOW(), %s)
                """, (result_id, proposal_id, error_msg, (datetime.now() - start_time).total_seconds()))
                self.conn.commit()

            return {'success': False, 'error': error_msg, 'outcome': 'SOC_VIOLATION'}

        soc_contract = STRATEGY_REGISTRY[soc_strategy_key]
        logger.info(f"SOC PRE-VALIDATION PASSED: {hypothesis_id} -> {soc_strategy_key}")
        logger.info(f"  SOC Hash: {soc_contract['trigger_function_hash'][:16]}...")
        logger.info(f"  Required Data: {soc_contract['required_data_assets']}")

        # Extract target asset from hypothesis
        target_asset = self.extract_target_asset(dict(proposal))
        logger.info(f"Target asset: {target_asset}")

        # Check if price data is available for this asset
        price_availability = self.check_price_data_availability(target_asset)
        if not price_availability['available']:
            logger.warning(f"No price data for {target_asset} - marking as INSUFFICIENT_DATA")

            # Store result with INSUFFICIENT_DATA outcome
            with self.conn.cursor() as cur:
                result_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO fhq_alpha.backtest_results (
                        result_id, proposal_id, lookback_days,
                        total_signals, winning_signals, losing_signals, win_rate,
                        total_return_pct, sharpe_ratio, validation_outcome, rejection_reason,
                        backtest_completed_at, duration_seconds
                    ) VALUES (
                        %s, %s, 0, 0, 0, 0, 0, 0, 0, 'INSUFFICIENT_DATA', %s, NOW(), %s
                    )
                """, (
                    result_id, proposal_id,
                    f"No price data available for {target_asset}. Run Colab backfill script.",
                    (datetime.now() - start_time).total_seconds()
                ))

                # Update proposal status
                cur.execute("""
                    UPDATE fhq_alpha.g0_draft_proposals
                    SET proposal_status = 'G1_REJECTED'
                    WHERE proposal_id = %s
                """, (proposal_id,))

                self.conn.commit()

            return {
                'success': False,
                'error': f'No price data for {target_asset}',
                'asset': target_asset,
                'outcome': 'INSUFFICIENT_DATA'
            }

        logger.info(f"Price data available: {price_availability['rows']} rows "
                   f"({price_availability['first_date']} to {price_availability['last_date']})")

        # CEO Directive CD-IOS-004-BACKTEST-HISTORY-STANDARD-001:
        # Use full history by default, allow explicit override only via backtest_requirements
        backtest_req = proposal.get('backtest_requirements') or {}
        if isinstance(backtest_req, str):
            import json as json_mod
            try:
                backtest_req = json_mod.loads(backtest_req)
            except:
                backtest_req = {}

        # Only use explicit lookback_days if specified in backtest_requirements
        explicit_lookback = backtest_req.get('lookback_days')  # None = full history (default)
        if explicit_lookback:
            logger.info(f"Using explicit lookback override: {explicit_lookback} days")
        else:
            logger.info("Using FULL available history (CEO Directive default)")

        # Get price data for the TARGET ASSET (not default BTC!)
        prices = self.get_price_data(asset_id=target_asset, days=explicit_lookback)
        logger.info(f"Loaded {len(prices)} days of price history for {target_asset}")

        if len(prices) < 30:
            return {'success': False, 'error': 'Insufficient price data'}

        # Calculate indicators
        indicators = self.calculate_indicators(prices)

        # Fetch cross-asset data for CROSS_ASSET category (IoS-001 verified instruments)
        category = proposal.get('hypothesis_category', proposal.get('category', 'UNKNOWN'))
        cross_asset_data = None
        if category == 'CROSS_ASSET':
            logger.info("CROSS_ASSET strategy detected - fetching cross-asset prices")
            cross_asset_data = self.get_cross_asset_data(target_asset, days=explicit_lookback)
            if not cross_asset_data:
                logger.warning("No cross-asset data available - strategy may fall back to single-asset")

        # Simulate signals
        trades = self.simulate_signals(dict(proposal), prices, indicators, cross_asset_data)

        # Calculate metrics
        metrics = self.calculate_backtest_metrics(trades)

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()

        # Store results
        with self.conn.cursor() as cur:
            result_id = str(uuid.uuid4())

            # Convert numpy types to native Python types
            m = {k: convert_numpy(v) for k, v in metrics.items()}

            cur.execute("""
                INSERT INTO fhq_alpha.backtest_results (
                    result_id, proposal_id, lookback_days, start_date, end_date,
                    total_signals, winning_signals, losing_signals, win_rate,
                    total_return_pct, avg_return_bps, median_return_bps, std_return_bps,
                    sharpe_ratio, sortino_ratio, profit_factor, max_drawdown_pct, avg_drawdown_pct,
                    avg_holding_period_hours, max_holding_period_hours,
                    p_value, t_statistic, validation_outcome, rejection_reason,
                    trade_log, backtest_completed_at, duration_seconds
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s
                )
            """, (
                result_id, proposal_id, len(prices),  # Actual days of history used
                prices[0]['price_date'] if prices else None,
                prices[-1]['price_date'] if prices else None,
                m['total_signals'], m['winning_signals'], m['losing_signals'],
                m['win_rate'], m['total_return_pct'], m['avg_return_bps'],
                m['median_return_bps'], m['std_return_bps'], m['sharpe_ratio'],
                m['sortino_ratio'], m['profit_factor'], m['max_drawdown_pct'],
                m['avg_drawdown_pct'], m['avg_holding_period_hours'],
                m['max_holding_period_hours'], m['p_value'], m['t_statistic'],
                m['validation_outcome'], m['rejection_reason'],
                Json(make_json_safe(trades[:20])),  # Store first 20 trades
                duration
            ))

            # Update proposal status (column is proposal_status, not status)
            new_status = 'G1_APPROVED' if metrics['validation_outcome'] == 'VALIDATED' else 'G1_REJECTED'
            cur.execute("""
                UPDATE fhq_alpha.g0_draft_proposals
                SET proposal_status = %s
                WHERE proposal_id = %s
            """, (new_status, proposal_id))

            # If validated, promote to G1
            if metrics['validation_outcome'] == 'VALIDATED':
                self.promote_to_g1(proposal, metrics, result_id)

            self.conn.commit()

        logger.info(f"Backtest complete: {metrics['validation_outcome']} "
                   f"(WR: {metrics['win_rate']:.1%}, SR: {metrics['sharpe_ratio']:.2f})")

        return {
            'success': True,
            'result_id': result_id,
            'outcome': metrics['validation_outcome'],
            'metrics': metrics
        }

    def promote_to_g1(self, proposal: Dict, metrics: Dict, result_id: str):
        """Promote validated hypothesis to G1."""
        signal_id = str(uuid.uuid4())

        # Calculate confidence score
        confidence = min(1.0, (
            metrics['win_rate'] * 0.3 +
            min(metrics['sharpe_ratio'] / 2, 0.3) +
            (1 - metrics['p_value']) * 0.2 +
            min(metrics['profit_factor'] / 3, 0.2)
        ))

        backtest_summary = {
            'total_signals': metrics['total_signals'],
            'win_rate': metrics['win_rate'],
            'avg_return_bps': metrics['avg_return_bps'],
            'sharpe_ratio': metrics['sharpe_ratio'],
            'profit_factor': metrics['profit_factor'],
            'max_drawdown_pct': metrics['max_drawdown_pct'],
            'avg_holding_period_hours': metrics['avg_holding_period_hours'],
            'p_value': metrics['p_value']
        }

        # Extract backtest requirements for entry/exit conditions
        backtest_req = proposal.get('backtest_requirements', {})
        if isinstance(backtest_req, str):
            import json as json_mod
            try:
                backtest_req = json_mod.loads(backtest_req)
            except:
                backtest_req = {}

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_alpha.g1_validated_signals (
                    signal_id, source_proposal_id, hypothesis_id, title, category,
                    entry_conditions, exit_conditions, regime_filter,
                    backtest_summary, confidence_score,
                    state_hash_at_validation, defcon_at_validation,
                    status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                signal_id,
                proposal['proposal_id'],
                proposal['hypothesis_id'],
                proposal.get('hypothesis_title', proposal.get('title', 'Unknown')),
                proposal.get('hypothesis_category', proposal.get('category', 'UNKNOWN')),
                Json(backtest_req.get('entry_conditions', []) if isinstance(backtest_req, dict) else []),
                Json(backtest_req.get('exit_conditions', {}) if isinstance(backtest_req, dict) else {}),
                backtest_req.get('regime_filter', []) if isinstance(backtest_req, dict) else [],
                Json(backtest_summary),
                confidence,
                proposal.get('state_hash_at_creation', proposal.get('state_hash', 'unknown')),
                proposal.get('defcon_at_creation', 5),
                'VALIDATED'
            ))

            # Notify IoS-008 if confidence is high enough
            if confidence >= 0.60:
                cur.execute("""
                    UPDATE fhq_alpha.g1_validated_signals
                    SET status = 'QUEUED_FOR_IOS008',
                        forwarded_to_ios008_at = NOW()
                    WHERE signal_id = %s
                """, (signal_id,))

                # Send notification
                self.conn.cursor().execute(
                    "SELECT pg_notify('ios008_signal_queue', %s)",
                    (json.dumps({'signal_id': signal_id, 'confidence': confidence}),)
                )

                logger.info(f"Signal {signal_id} forwarded to IoS-008 (confidence: {confidence:.2f})")

            # Log event
            cur.execute("""
                INSERT INTO fhq_monitoring.system_event_log (event_type, status, metadata)
                VALUES ('g1_signal_created', 'completed', %s)
            """, (Json({
                'signal_id': signal_id,
                'hypothesis_id': proposal['hypothesis_id'],
                'confidence': confidence,
                'forwarded_to_ios008': confidence >= 0.60
            }),))

        logger.info(f"Promoted to G1: {signal_id} (confidence: {confidence:.2f})")

    def process_queue(self):
        """Process pending items in backtest queue."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get next pending item
            cur.execute("""
                UPDATE fhq_alpha.backtest_queue
                SET status = 'PROCESSING', started_at = NOW(), worker_id = %s
                WHERE queue_id = (
                    SELECT queue_id FROM fhq_alpha.backtest_queue
                    WHERE status = 'PENDING'
                    ORDER BY priority ASC, queued_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING *
            """, (self.worker_id,))

            item = cur.fetchone()

            if not item:
                return None

            self.conn.commit()

        # Run backtest
        try:
            result = self.run_backtest(str(item['proposal_id']))

            # Update queue status
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE fhq_alpha.backtest_queue
                    SET status = %s, completed_at = NOW()
                    WHERE queue_id = %s
                """, ('COMPLETED' if result['success'] else 'FAILED', item['queue_id']))
                self.conn.commit()

            return result

        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE fhq_alpha.backtest_queue
                    SET status = 'FAILED', error_message = %s
                    WHERE queue_id = %s
                """, (str(e), item['queue_id']))
                self.conn.commit()
            return {'success': False, 'error': str(e)}

    def listen_for_notifications(self):
        """Listen for new proposals via NOTIFY."""
        with self.listen_conn.cursor() as cur:
            cur.execute("LISTEN ios004_backtest_queue")

        logger.info("Listening on ios004_backtest_queue channel...")

        while True:
            # Process any pending queue items first
            while True:
                result = self.process_queue()
                if result is None:
                    break
                logger.info(f"Processed: {json.dumps(result, default=str)}")

            # Wait for notifications
            if select.select([self.listen_conn], [], [], 10) == ([], [], []):
                # Timeout - check queue again
                continue

            self.listen_conn.poll()
            while self.listen_conn.notifies:
                notify = self.listen_conn.notifies.pop(0)
                logger.info(f"Received notification: {notify.payload}")

    def run_daemon(self):
        """Run as continuous daemon."""
        logger.info("IoS-004 Backtest Worker starting...")
        self.listen_for_notifications()


def main():
    parser = argparse.ArgumentParser(description='IoS-004 Backtest Worker')
    parser.add_argument('--daemon', action='store_true', help='Run as continuous daemon')
    parser.add_argument('--proposal', type=str, help='Run backtest for specific proposal ID')
    parser.add_argument('--process-queue', action='store_true', help='Process all pending queue items')
    args = parser.parse_args()

    # Ensure logs directory exists
    os.makedirs('C:/fhq-market-system/vision-ios/logs', exist_ok=True)

    worker = IoS004BacktestWorker()

    try:
        worker.connect()

        if args.daemon:
            worker.run_daemon()
        elif args.proposal:
            result = worker.run_backtest(args.proposal)
            print(json.dumps(result, indent=2, default=str))
        elif args.process_queue:
            while True:
                result = worker.process_queue()
                if result is None:
                    print("Queue empty")
                    break
                print(json.dumps(result, indent=2, default=str))
        else:
            # Default: process queue once
            result = worker.process_queue()
            if result:
                print(json.dumps(result, indent=2, default=str))
            else:
                print("No pending backtests")

    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        worker.close()


if __name__ == '__main__':
    main()
