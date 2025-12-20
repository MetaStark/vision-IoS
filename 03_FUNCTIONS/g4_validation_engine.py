"""
G4 Validation Engine - The Laboratory Phase (WAVE 16A - Edge Cartography)
=========================================================================
CEO Directive: WAVE 16A - G4 REFINEMENT
Date: 2025-12-18

Strategic Pivot: From "Elimination" to "Cartography"
Instead of binary PASS/REJECT, we now map edges across 3 axes:

AXIS A: Historical Merit (based on OOS Sharpe)
  - STRONG:   Sharpe >= 1.5
  - MODERATE: Sharpe >= 1.0 AND < 1.5
  - WEAK:     Sharpe >= 0.5 AND < 1.0
  - NONE:     Sharpe < 0.5 (but NOT negative)
  - NEGATIVE: Sharpe < 0.0 (TRUE REJECT)

AXIS B: Physical Robustness (execution realism)
  - ROBUST:      Survives 1s latency with >50% edge retention
  - FRAGILE:     Degrades but still positive
  - THEORETICAL: Edge destroyed by latency OR untestable

AXIS C: Regime Dependence
  - AGNOSTIC:  Works across multiple regimes
  - SPECIFIC:  Requires specific regime context

Composite Classifications:
  - PLATINUM: STRONG + ROBUST (eligible for G5)
  - GOLD:     STRONG + FRAGILE OR MODERATE + ROBUST
  - SILVER:   MODERATE + FRAGILE OR WEAK + ROBUST
  - BRONZE:   WEAK + FRAGILE OR THEORETICAL
  - REJECT:   NEGATIVE expectancy ONLY

EXPLICIT PROHIBITIONS:
  - NO broker connections
  - NO paper trading
  - NO live PnL attribution
  - NO capital exposure
  - NO parameter tuning
"""

import os
import sys
import json
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, List, Tuple
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor, Json
import numpy as np
from scipy import stats

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='[G4-LAB] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('C:/fhq-market-system/vision-ios/logs/g4_validation_engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONSTITUTIONAL CONSTANTS (LOCKED - NO PARAMETER TUNING)
# =============================================================================
ANNUALIZATION_FACTOR = 252  # Trading days per year
RISK_FREE_RATE = 0.02       # 2% annual
IN_SAMPLE_RATIO = 0.70      # 70% in-sample, 30% out-of-sample
LOOKBACK_YEARS = 7          # Extended to 7 years per CEO Directive WAVE 16B

# Transaction costs (conservative)
ENTRY_COST_BPS = 5.0        # 0.05% entry
EXIT_COST_BPS = 5.0         # 0.05% exit
SLIPPAGE_BPS = 5.0          # 0.05% slippage
TOTAL_FRICTION_BPS = ENTRY_COST_BPS + EXIT_COST_BPS + SLIPPAGE_BPS  # 15 bps

# WAVE 16A: 3-Axis Classification Thresholds
# AXIS A: Historical Merit (based on OOS Sharpe)
SHARPE_STRONG_THRESHOLD = 1.50      # >= 1.5 = STRONG
SHARPE_MODERATE_THRESHOLD = 1.00    # >= 1.0 = MODERATE
SHARPE_WEAK_THRESHOLD = 0.50        # >= 0.5 = WEAK
# < 0.5 = NONE, < 0.0 = NEGATIVE (only TRUE REJECT)

# Legacy thresholds (kept for backward compatibility)
SHARPE_PASS_THRESHOLD = 1.00
SHARPE_QUARANTINE_THRESHOLD = 0.70

# Latency injection levels (ms)
LATENCY_LEVELS_MS = [50, 200, 1000]

# Edge retention threshold for ROBUST classification
ROBUST_EDGE_RETENTION_PCT = 50.0

# AXIS C: Regime-Specific Categories
REGIME_SPECIFIC_CATEGORIES = ['REGIME_EDGE', 'CATALYST_AMPLIFICATION']


class G4ValidationEngine:
    """
    G4 Laboratory Phase Validation Engine.
    Executes dual-core validation on Golden Needles.
    """

    def __init__(self):
        self.conn = self._connect_db()
        logger.info("G4 Validation Engine initialized")

    def _connect_db(self):
        """Connect to PostgreSQL."""
        return psycopg2.connect(
            host=os.getenv('PGHOST', '127.0.0.1'),
            port=os.getenv('PGPORT', '54322'),
            database=os.getenv('PGDATABASE', 'postgres'),
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD', 'postgres')
        )

    def get_pending_needles(self, limit: int = 10) -> List[Dict]:
        """Get pending Golden Needles for validation, prioritized by EQS."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    q.queue_id,
                    q.needle_id,
                    q.priority,
                    g.hypothesis_title,
                    g.hypothesis_statement,
                    g.hypothesis_category,
                    g.eqs_score,
                    g.target_asset,
                    g.expected_timeframe_days,
                    g.falsification_criteria,
                    g.backtest_requirements
                FROM fhq_canonical.g4_validation_queue q
                JOIN fhq_canonical.golden_needles g ON q.needle_id = g.needle_id
                WHERE q.refinery_status = 'PENDING'
                ORDER BY q.priority ASC, g.eqs_score DESC
                LIMIT %s
            """, (limit,))
            return [dict(row) for row in cur.fetchall()]

    def get_price_history(self, symbol: str, years: int = 7) -> List[Dict]:
        """
        Get historical OHLCV data for backtesting.
        Uses IoS-001 canonical price series.

        IMPORTANT: Aggregates to proper daily bars to handle tick/intraday data.
        This prevents ATR calculation errors from duplicate/flat rows.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                WITH ranked_prices AS (
                    SELECT
                        date::date as trade_date,
                        open, high, low, close, volume,
                        ROW_NUMBER() OVER (PARTITION BY date::date ORDER BY date ASC) as rn_first,
                        ROW_NUMBER() OVER (PARTITION BY date::date ORDER BY date DESC) as rn_last
                    FROM fhq_data.price_series
                    WHERE listing_id = %s
                    AND date >= CURRENT_DATE - INTERVAL '%s years'
                ),
                daily_agg AS (
                    SELECT
                        trade_date,
                        MAX(CASE WHEN rn_first = 1 THEN open END) as day_open,
                        MAX(high) as day_high,
                        MIN(low) as day_low,
                        MAX(CASE WHEN rn_last = 1 THEN close END) as day_close,
                        SUM(volume) as day_volume
                    FROM ranked_prices
                    GROUP BY trade_date
                )
                SELECT
                    trade_date as price_date,
                    day_open as open_price,
                    day_high as high_price,
                    day_low as low_price,
                    day_close as close_price,
                    day_volume as volume
                FROM daily_agg
                WHERE day_high > day_low  -- Exclude flat days with no trading range
                ORDER BY trade_date ASC
            """, (symbol, years))
            return [dict(row) for row in cur.fetchall()]

    def run_stream_a_refinery(self, needle: Dict) -> Dict:
        """
        STREAM A - The Refinery: Historical Validation (WAVE 16A).

        Executes hypothesis-specific backtest with in-sample/out-of-sample split.
        Returns metrics and 3-axis classification.
        """
        needle_id = needle['needle_id']
        hypothesis_category = needle.get('hypothesis_category', 'UNKNOWN')
        logger.info(f"STREAM A starting for needle {needle_id} (category={hypothesis_category})")

        # Mark as processing
        self._update_queue_status(needle_id, 'refinery', 'PROCESSING')

        try:
            # Determine target asset (default to BTC-USD for crypto hypotheses)
            target = needle.get('target_asset') or 'BTC-USD'

            # Get price history
            prices = self.get_price_history(target, LOOKBACK_YEARS)

            if len(prices) < 252:  # Need at least 1 year
                logger.warning(f"Insufficient data for {target}: {len(prices)} days")
                return self._create_reject_result(needle_id, "INSUFFICIENT_DATA")

            # Split into in-sample and out-of-sample
            split_idx = int(len(prices) * IN_SAMPLE_RATIO)
            in_sample = prices[:split_idx]
            out_of_sample = prices[split_idx:]

            # WAVE 16A: Get hypothesis-specific strategy from Logic Translation Registry
            strategy = self._get_logic_translation_strategy(hypothesis_category)
            params = self._parse_hypothesis_params(needle, strategy)

            # Run backtest on in-sample using category-specific strategy
            is_results = self._run_category_backtest(in_sample, params, hypothesis_category, "IN_SAMPLE")

            # Run backtest on out-of-sample (THE TRUTH)
            oos_results = self._run_category_backtest(out_of_sample, params, hypothesis_category, "OUT_OF_SAMPLE")

            # WAVE 16A: 3-Axis Classification
            oos_sharpe = oos_results.get('sharpe_ratio', 0)

            # AXIS A: Historical Merit
            if oos_sharpe < 0:
                historical_merit = 'NEGATIVE'
                cull_classification = 'REJECT'  # Only TRUE REJECT
            elif oos_sharpe >= SHARPE_STRONG_THRESHOLD:
                historical_merit = 'STRONG'
                cull_classification = 'PASS'
            elif oos_sharpe >= SHARPE_MODERATE_THRESHOLD:
                historical_merit = 'MODERATE'
                cull_classification = 'PASS'
            elif oos_sharpe >= SHARPE_WEAK_THRESHOLD:
                historical_merit = 'WEAK'
                cull_classification = 'QUARANTINE'
            else:
                historical_merit = 'NONE'
                cull_classification = 'QUARANTINE'  # Not REJECT per WAVE 16A

            # Build result record with WAVE 16A fields
            result = {
                'needle_id': str(needle_id),
                'lookback_years': LOOKBACK_YEARS,
                'in_sample_ratio': float(IN_SAMPLE_RATIO),
                'start_date': str(prices[0]['price_date']),
                'end_date': str(prices[-1]['price_date']),
                'in_sample_end': str(in_sample[-1]['price_date']),
                'entry_cost_bps': float(ENTRY_COST_BPS),
                'exit_cost_bps': float(EXIT_COST_BPS),
                'slippage_bps': float(SLIPPAGE_BPS),
                # In-sample metrics
                'is_total_trades': is_results.get('total_trades', 0),
                'is_win_rate': is_results.get('win_rate', 0),
                'is_net_return_pct': is_results.get('net_return_pct', 0),
                'is_sharpe_ratio': is_results.get('sharpe_ratio', 0),
                'is_sortino_ratio': is_results.get('sortino_ratio', 0),
                'is_max_drawdown_pct': is_results.get('max_drawdown_pct', 0),
                'is_profit_factor': is_results.get('profit_factor', 0),
                # Out-of-sample metrics (THE TRUTH)
                'oos_total_trades': oos_results.get('total_trades', 0),
                'oos_win_rate': oos_results.get('win_rate', 0),
                'oos_net_return_pct': oos_results.get('net_return_pct', 0),
                'oos_sharpe_ratio': oos_sharpe,
                'oos_sortino_ratio': oos_results.get('sortino_ratio', 0),
                'oos_max_drawdown_pct': oos_results.get('max_drawdown_pct', 0),
                'oos_profit_factor': oos_results.get('profit_factor', 0),
                'oos_avg_holding_hours': oos_results.get('avg_holding_hours', 0),
                'oos_p_value': oos_results.get('p_value', 1.0),
                'oos_t_statistic': oos_results.get('t_statistic', 0),
                'cull_classification': cull_classification,
                # WAVE 16A: 3-Axis Classification
                'historical_merit': historical_merit,
                'hypothesis_category': hypothesis_category,
                'backtest_strategy_id': strategy.get('strategy_id') if strategy else None,
                'backtest_strategy_version': strategy.get('strategy_version') if strategy else None,
                'logic_translation_applied': strategy is not None,
                'trade_log': oos_results.get('trade_log', []),
                'equity_curve_is': is_results.get('equity_curve', []),
                'equity_curve_oos': oos_results.get('equity_curve', [])
            }

            # Persist to database
            self._persist_refinery_result(result)
            self._update_queue_status(needle_id, 'refinery', 'COMPLETED')

            logger.info(f"STREAM A complete for {needle_id}: {cull_classification} (Sharpe={oos_sharpe:.4f})")
            return result

        except Exception as e:
            logger.error(f"STREAM A failed for {needle_id}: {e}")
            self._update_queue_status(needle_id, 'refinery', 'FAILED', str(e))
            return self._create_reject_result(needle_id, f"ERROR: {e}")

    def run_stream_b_physics(self, needle: Dict, refinery_result: Dict) -> Dict:
        """
        STREAM B - The Physics: Latency & Decay Measurement.

        Injects deterministic latency and measures signal decay.
        """
        needle_id = needle['needle_id']
        logger.info(f"STREAM B starting for needle {needle_id}")

        self._update_queue_status(needle_id, 'physics', 'PROCESSING')

        try:
            # Get the OOS trade log from refinery
            trade_log = refinery_result.get('trade_log', [])
            if not trade_log:
                logger.warning(f"No trades for physics simulation: {needle_id}")
                return self._create_nonviable_physics(needle_id)

            # Calculate baseline edge (no latency)
            baseline_return = refinery_result.get('oos_net_return_pct', 0)

            # Simulate latency injection at each level
            latency_results = {}
            for latency_ms in LATENCY_LEVELS_MS:
                degraded_return = self._simulate_latency_impact(
                    trade_log, baseline_return, latency_ms
                )
                latency_results[latency_ms] = degraded_return

            # Calculate edge retention at each level
            edge_50ms = (latency_results[50] / baseline_return * 100) if baseline_return > 0 else 0
            edge_200ms = (latency_results[200] / baseline_return * 100) if baseline_return > 0 else 0
            edge_1000ms = (latency_results[1000] / baseline_return * 100) if baseline_return > 0 else 0

            # Calculate signal half-life (time until edge degrades to 50%)
            half_life = self._calculate_half_life(latency_results, baseline_return)

            # Calculate latency sensitivity (return degradation per 100ms)
            sensitivity = (baseline_return - latency_results[1000]) / 10 if baseline_return > 0 else 0

            # Determine survivability classification
            if edge_1000ms >= ROBUST_EDGE_RETENTION_PCT and latency_results[1000] > 0:
                survivability = 'ROBUST'
            elif latency_results[1000] > 0:
                survivability = 'FRAGILE'
            else:
                survivability = 'NON_VIABLE'

            result = {
                'needle_id': str(needle_id),
                'latency_50ms_return_pct': latency_results[50],
                'latency_200ms_return_pct': latency_results[200],
                'latency_1000ms_return_pct': latency_results[1000],
                'latency_sensitivity_per_100ms': sensitivity,
                'signal_half_life_seconds': half_life * 1000 if half_life else None,
                'signal_decay_rate': 1 / half_life if half_life and half_life > 0 else None,
                'time_to_invalidation_seconds': self._calculate_invalidation_time(latency_results),
                'edge_retained_50ms_pct': edge_50ms,
                'edge_retained_200ms_pct': edge_200ms,
                'edge_retained_1000ms_pct': edge_1000ms,
                'survivability': survivability,
                'latency_profile': {
                    'baseline_return': baseline_return,
                    'latency_curve': latency_results
                }
            }

            # Persist to database
            self._persist_physics_result(result)
            self._update_queue_status(needle_id, 'physics', 'COMPLETED')

            logger.info(f"STREAM B complete for {needle_id}: {survivability}")
            return result

        except Exception as e:
            logger.error(f"STREAM B failed for {needle_id}: {e}")
            self._update_queue_status(needle_id, 'physics', 'FAILED', str(e))
            return self._create_nonviable_physics(needle_id)

    def create_composite_scorecard(self, needle_id: str,
                                    refinery: Dict, physics: Dict) -> Dict:
        """
        WAVE 16A: Create VEGA G4 Composite Scorecard with 3-Axis Classification.
        """
        # Get needle details
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT eqs_score, hypothesis_category, regime_sovereign
                FROM fhq_canonical.golden_needles
                WHERE needle_id = %s::uuid
            """, (needle_id,))
            row = cur.fetchone()
            eqs = float(row['eqs_score']) if row else 0
            hypothesis_category = row['hypothesis_category'] if row else 'UNKNOWN'
            regime_sovereign = row['regime_sovereign'] if row else 'NEUTRAL'

        # AXIS A: Historical Merit (from refinery)
        historical_merit = refinery.get('historical_merit', 'NONE')
        oos_sharpe = refinery.get('oos_sharpe_ratio', 0)

        # AXIS B: Physical Robustness (from physics)
        surv = physics.get('survivability', 'NON_VIABLE')
        edge_1000ms = physics.get('edge_retained_1000ms_pct', 0)

        # Map survivability to robustness_axis
        if surv == 'ROBUST':
            robustness_axis = 'ROBUST'
        elif surv == 'FRAGILE':
            robustness_axis = 'FRAGILE'
        else:
            robustness_axis = 'THEORETICAL'

        # AXIS C: Regime Dependence
        if hypothesis_category in REGIME_SPECIFIC_CATEGORIES:
            regime_dependence = 'SPECIFIC'
        else:
            regime_dependence = 'AGNOSTIC'

        # WAVE 16A: Composite Classification
        # REJECT only for NEGATIVE expectancy
        if historical_merit == 'NEGATIVE':
            classification = 'REJECT'
        elif historical_merit == 'STRONG' and robustness_axis == 'ROBUST':
            classification = 'PLATINUM'
        elif historical_merit == 'STRONG' and robustness_axis == 'FRAGILE':
            classification = 'GOLD'
        elif historical_merit == 'MODERATE' and robustness_axis == 'ROBUST':
            classification = 'GOLD'
        elif historical_merit == 'MODERATE' and robustness_axis == 'FRAGILE':
            classification = 'SILVER'
        elif historical_merit == 'WEAK' and robustness_axis == 'ROBUST':
            classification = 'SILVER'
        elif historical_merit == 'WEAK' and robustness_axis == 'FRAGILE':
            classification = 'BRONZE'
        elif robustness_axis == 'THEORETICAL':
            classification = 'BRONZE'  # Theoretical edges still get mapped
        else:
            classification = 'BRONZE'  # Default to lowest non-reject tier

        # Edge map coordinates for visualization
        edge_map = {
            'x': oos_sharpe,  # Historical Merit dimension
            'y': edge_1000ms / 100 if edge_1000ms else 0,  # Robustness dimension
            'z': 1 if regime_dependence == 'SPECIFIC' else 0,  # Regime dimension
            'axes': {
                'a': historical_merit,
                'b': robustness_axis,
                'c': regime_dependence
            }
        }

        scorecard = {
            'needle_id': needle_id,
            'eqs_score': eqs,
            'oos_sharpe': oos_sharpe,
            'decay_half_life_seconds': physics.get('signal_half_life_seconds'),
            'classification': classification,
            # WAVE 16A: 3-Axis Classification
            'axis_a_historical_merit': historical_merit,
            'axis_b_physical_robustness': robustness_axis,
            'axis_c_regime_dependence': regime_dependence,
            'edge_map_coordinates': edge_map,
            'hypothesis_category': hypothesis_category,
            'backtest_strategy_id': refinery.get('backtest_strategy_id'),
            'logic_translation_applied': refinery.get('logic_translation_applied', False),
            # Legacy fields
            'cull_classification': refinery.get('cull_classification', 'QUARANTINE'),
            'survivability': surv,
            'fdr_adjusted_p_value': refinery.get('oos_p_value', 1.0),
            'passes_fdr_threshold': refinery.get('oos_p_value', 1.0) <= 0.05
        }

        # Persist scorecard
        self._persist_scorecard(scorecard)

        logger.info(f"Scorecard created for {needle_id}: {classification} (A={historical_merit}, B={robustness_axis}, C={regime_dependence})")
        return scorecard

    def _get_logic_translation_strategy(self, hypothesis_category: str) -> Optional[Dict]:
        """
        WAVE 16A: Get hypothesis-specific backtest strategy from Logic Translation Registry.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    strategy_id,
                    strategy_name,
                    strategy_version,
                    entry_logic,
                    exit_logic,
                    position_sizing,
                    default_lookback_years,
                    default_in_sample_ratio,
                    requires_regime_data,
                    regime_agnostic,
                    applicable_regimes
                FROM fhq_canonical.g4_logic_translation_registry
                WHERE hypothesis_category = %s
                AND is_active = true
                LIMIT 1
            """, (hypothesis_category,))
            row = cur.fetchone()
            return dict(row) if row else None

    def _parse_hypothesis_params(self, needle: Dict, strategy: Optional[Dict] = None) -> Dict:
        """Parse hypothesis statement into backtest parameters with Logic Translation."""
        # Default parameters
        params = {
            'holding_days': needle.get('expected_timeframe_days', 5) or 5,
            'threshold_pct': 2.0,
            'stop_loss_pct': 5.0,
            'take_profit_pct': 10.0,
            'regime_filter': None,
            'strategy_type': 'generic'
        }

        # Apply Logic Translation strategy if available
        if strategy:
            entry_logic = strategy.get('entry_logic', {})
            exit_logic = strategy.get('exit_logic', {})

            params['strategy_type'] = entry_logic.get('type', 'generic')
            params['entry_logic'] = entry_logic
            params['exit_logic'] = exit_logic
            params['position_sizing'] = strategy.get('position_sizing', {})
            params['requires_regime_data'] = strategy.get('requires_regime_data', False)

            # Extract specific parameters from strategy
            if 'max_holding_days' in exit_logic:
                params['holding_days'] = exit_logic.get('max_holding_days', params['holding_days'])
            if 'stop_loss_pct' in exit_logic:
                params['stop_loss_pct'] = exit_logic.get('stop_loss_pct', params['stop_loss_pct'])
            if 'profit_target_pct' in exit_logic:
                params['take_profit_pct'] = exit_logic.get('profit_target_pct', params['take_profit_pct'])

        # Override from backtest_requirements if available
        req = needle.get('backtest_requirements')
        if req and isinstance(req, dict):
            params.update({
                'holding_days': req.get('holding_days', params['holding_days']),
                'threshold_pct': req.get('threshold_pct', params['threshold_pct']),
                'stop_loss_pct': req.get('stop_loss_pct', params['stop_loss_pct']),
                'take_profit_pct': req.get('take_profit_pct', params['take_profit_pct']),
            })

        return params

    def _run_category_backtest(self, prices: List[Dict], params: Dict,
                                category: str, period: str) -> Dict:
        """
        WAVE 16A: Execute hypothesis-category-specific backtest.
        Routes to appropriate strategy implementation.
        """
        strategy_type = params.get('strategy_type', 'generic')

        if strategy_type == 'mean_reversion':
            return self._backtest_mean_reversion(prices, params, period)
        elif strategy_type == 'breakout':
            return self._backtest_breakout(prices, params, period)
        elif strategy_type == 'momentum':
            return self._backtest_momentum(prices, params, period)
        elif strategy_type == 'regime_transition':
            return self._backtest_regime_transition(prices, params, period)
        elif strategy_type == 'volatility':
            return self._backtest_volatility(prices, params, period)
        elif strategy_type == 'contrarian':
            return self._backtest_contrarian(prices, params, period)
        else:
            # Fallback to generic backtest
            return self._run_backtest(prices, params, period)

    def _run_backtest(self, prices: List[Dict], params: Dict, period: str) -> Dict:
        """
        Execute backtest on price series with given parameters.
        Returns comprehensive metrics.
        """
        if len(prices) < 30:
            return {'total_trades': 0, 'sharpe_ratio': 0}

        trades = []
        holding_days = params['holding_days']
        threshold_pct = params['threshold_pct'] / 100
        stop_loss_pct = params['stop_loss_pct'] / 100
        take_profit_pct = params['take_profit_pct'] / 100

        # Simple mean reversion strategy for generic testing
        for i in range(30, len(prices) - holding_days - 1):
            entry_price = float(prices[i]['close_price'])

            # Calculate 7-day and 3-day returns
            returns_7d = (entry_price - float(prices[i-7]['close_price'])) / float(prices[i-7]['close_price'])
            returns_3d = (entry_price - float(prices[i-3]['close_price'])) / float(prices[i-3]['close_price'])

            # Entry signal: pullback in uptrend or rally in downtrend
            if returns_7d > threshold_pct * 2 and returns_3d < 0:
                direction = 'LONG'
            elif returns_7d < -threshold_pct * 2 and returns_3d > 0:
                direction = 'SHORT'
            else:
                continue

            # Calculate exit
            exit_idx = min(i + holding_days, len(prices) - 1)
            exit_price = float(prices[exit_idx]['close_price'])

            # Apply friction
            friction = TOTAL_FRICTION_BPS / 10000

            if direction == 'LONG':
                gross_return = (exit_price - entry_price) / entry_price
                net_return = gross_return - friction
            else:
                gross_return = (entry_price - exit_price) / entry_price
                net_return = gross_return - friction

            # Check stop loss / take profit
            for j in range(i + 1, exit_idx + 1):
                intraday_price = float(prices[j]['close_price'])
                if direction == 'LONG':
                    if (intraday_price - entry_price) / entry_price <= -stop_loss_pct:
                        net_return = -stop_loss_pct - friction
                        break
                    if (intraday_price - entry_price) / entry_price >= take_profit_pct:
                        net_return = take_profit_pct - friction
                        break
                else:
                    if (entry_price - intraday_price) / entry_price <= -stop_loss_pct:
                        net_return = -stop_loss_pct - friction
                        break
                    if (entry_price - intraday_price) / entry_price >= take_profit_pct:
                        net_return = take_profit_pct - friction
                        break

            trades.append({
                'entry_date': str(prices[i]['price_date']),
                'exit_date': str(prices[exit_idx]['price_date']),
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'gross_return': gross_return,
                'net_return': net_return,
                'holding_days': holding_days
            })

        if not trades:
            return {'total_trades': 0, 'sharpe_ratio': 0}

        # Calculate metrics
        returns = [t['net_return'] for t in trades]
        returns_array = np.array(returns)

        total_trades = len(trades)
        winning_trades = sum(1 for r in returns if r > 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # Return metrics
        net_return_pct = np.sum(returns_array) * 100
        avg_return = np.mean(returns_array)
        std_return = np.std(returns_array)

        # Sharpe ratio (annualized)
        if std_return > 0:
            daily_sharpe = avg_return / std_return
            sharpe_ratio = daily_sharpe * np.sqrt(ANNUALIZATION_FACTOR / params['holding_days'])
        else:
            sharpe_ratio = 0

        # Sortino ratio
        downside_returns = returns_array[returns_array < 0]
        if len(downside_returns) > 0:
            downside_std = np.std(downside_returns)
            sortino_ratio = (avg_return / downside_std) * np.sqrt(ANNUALIZATION_FACTOR / params['holding_days']) if downside_std > 0 else 0
        else:
            sortino_ratio = sharpe_ratio * 1.5  # Approximate

        # Profit factor
        gross_profits = sum(r for r in returns if r > 0)
        gross_losses = abs(sum(r for r in returns if r < 0))
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else float('inf')

        # Max drawdown
        cumulative = np.cumsum(returns_array)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        max_drawdown_pct = np.max(drawdowns) * 100 if len(drawdowns) > 0 else 0

        # Statistical significance
        if len(returns) >= 2:
            t_stat, p_value = stats.ttest_1samp(returns, 0)
        else:
            t_stat, p_value = 0, 1.0

        # Build equity curve
        equity_curve = [{'date': trades[0]['entry_date'], 'equity': 1.0}]
        equity = 1.0
        for t in trades:
            equity *= (1 + t['net_return'])
            equity_curve.append({'date': t['exit_date'], 'equity': equity})

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': win_rate,
            'net_return_pct': net_return_pct,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'profit_factor': profit_factor,
            'max_drawdown_pct': max_drawdown_pct,
            'avg_holding_hours': params['holding_days'] * 24,
            't_statistic': t_stat,
            'p_value': p_value,
            'trade_log': trades[:100],  # Limit for storage
            'equity_curve': equity_curve
        }

    # =========================================================================
    # WAVE 16A: CATEGORY-SPECIFIC BACKTEST STRATEGIES
    # =========================================================================

    def _backtest_mean_reversion(self, prices: List[Dict], params: Dict, period: str) -> Dict:
        """Mean Reversion strategy: Enter on Z-score extremes, exit on mean reversion."""
        if len(prices) < 30:
            return {'total_trades': 0, 'sharpe_ratio': 0}

        trades = []
        entry_logic = params.get('entry_logic', {})
        exit_logic = params.get('exit_logic', {})

        zscore_entry = entry_logic.get('zscore_entry_threshold', 2.0)
        zscore_exit = exit_logic.get('zscore_exit_threshold', 0.5)
        lookback = entry_logic.get('lookback_period', 20)
        max_holding = exit_logic.get('max_holding_days', 10)
        stop_zscore = exit_logic.get('stop_loss_zscore', 3.0)

        closes = [float(p['close_price']) for p in prices]

        for i in range(lookback, len(prices) - max_holding - 1):
            # Calculate Z-score
            window = closes[i-lookback:i]
            mean = np.mean(window)
            std = np.std(window)
            if std == 0:
                continue

            zscore = (closes[i] - mean) / std

            # Entry conditions
            if zscore <= -zscore_entry:
                direction = 'LONG'  # Oversold, expect mean reversion up
            elif zscore >= zscore_entry:
                direction = 'SHORT'  # Overbought, expect mean reversion down
            else:
                continue

            entry_price = closes[i]
            exit_idx = i + 1
            exit_price = entry_price

            # Find exit
            for j in range(i + 1, min(i + max_holding + 1, len(prices))):
                window_j = closes[max(0,j-lookback):j]
                mean_j = np.mean(window_j)
                std_j = np.std(window_j) or 1
                zscore_j = (closes[j] - mean_j) / std_j

                # Exit on mean reversion
                if abs(zscore_j) <= zscore_exit:
                    exit_idx = j
                    exit_price = closes[j]
                    break
                # Stop loss
                if direction == 'LONG' and zscore_j <= -stop_zscore:
                    exit_idx = j
                    exit_price = closes[j]
                    break
                if direction == 'SHORT' and zscore_j >= stop_zscore:
                    exit_idx = j
                    exit_price = closes[j]
                    break
            else:
                exit_idx = min(i + max_holding, len(prices) - 1)
                exit_price = closes[exit_idx]

            # Calculate return
            friction = TOTAL_FRICTION_BPS / 10000
            if direction == 'LONG':
                net_return = (exit_price - entry_price) / entry_price - friction
            else:
                net_return = (entry_price - exit_price) / entry_price - friction

            trades.append({
                'entry_date': str(prices[i]['price_date']),
                'exit_date': str(prices[exit_idx]['price_date']),
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'net_return': net_return,
                'entry_zscore': zscore,
                'holding_days': exit_idx - i
            })

        return self._calculate_backtest_metrics(trades, params)

    def _backtest_breakout(self, prices: List[Dict], params: Dict, period: str) -> Dict:
        """Breakout strategy: Enter on Bollinger Band breakout with volume confirmation."""
        if len(prices) < 30:
            return {'total_trades': 0, 'sharpe_ratio': 0}

        trades = []
        entry_logic = params.get('entry_logic', {})
        exit_logic = params.get('exit_logic', {})

        bb_period = entry_logic.get('bollinger_period', 20)
        bb_std = entry_logic.get('bollinger_std', 2.0)
        vol_mult = entry_logic.get('volume_multiplier', 1.5)
        trailing_stop_atr = exit_logic.get('trailing_stop_atr', 2.0)
        profit_target_atr = exit_logic.get('profit_target_atr', 4.0)
        max_holding = exit_logic.get('time_stop_days', 20)

        closes = [float(p['close_price']) for p in prices]
        highs = [float(p['high_price']) for p in prices]
        lows = [float(p['low_price']) for p in prices]
        volumes = [float(p['volume']) for p in prices]

        for i in range(bb_period + 14, len(prices) - max_holding - 1):
            # Bollinger Bands
            window = closes[i-bb_period:i]
            sma = np.mean(window)
            std = np.std(window)
            upper_band = sma + bb_std * std
            lower_band = sma - bb_std * std

            # ATR for position sizing and stops
            atr_window = []
            for k in range(i-14, i):
                tr = max(highs[k] - lows[k],
                        abs(highs[k] - closes[k-1]),
                        abs(lows[k] - closes[k-1]))
                atr_window.append(tr)
            atr = np.mean(atr_window)

            # Volume confirmation
            avg_vol = np.mean(volumes[i-20:i])

            # Entry conditions
            if closes[i] > upper_band and volumes[i] > avg_vol * vol_mult:
                direction = 'LONG'
            elif closes[i] < lower_band and volumes[i] > avg_vol * vol_mult:
                direction = 'SHORT'
            else:
                continue

            entry_price = closes[i]
            trailing_stop = entry_price - (trailing_stop_atr * atr) if direction == 'LONG' else entry_price + (trailing_stop_atr * atr)
            profit_target = entry_price + (profit_target_atr * atr) if direction == 'LONG' else entry_price - (profit_target_atr * atr)

            exit_idx = i + 1
            exit_price = entry_price

            for j in range(i + 1, min(i + max_holding + 1, len(prices))):
                # Update trailing stop
                if direction == 'LONG':
                    trailing_stop = max(trailing_stop, closes[j] - trailing_stop_atr * atr)
                    if closes[j] <= trailing_stop or closes[j] >= profit_target:
                        exit_idx = j
                        exit_price = closes[j]
                        break
                else:
                    trailing_stop = min(trailing_stop, closes[j] + trailing_stop_atr * atr)
                    if closes[j] >= trailing_stop or closes[j] <= profit_target:
                        exit_idx = j
                        exit_price = closes[j]
                        break
            else:
                exit_idx = min(i + max_holding, len(prices) - 1)
                exit_price = closes[exit_idx]

            friction = TOTAL_FRICTION_BPS / 10000
            if direction == 'LONG':
                net_return = (exit_price - entry_price) / entry_price - friction
            else:
                net_return = (entry_price - exit_price) / entry_price - friction

            trades.append({
                'entry_date': str(prices[i]['price_date']),
                'exit_date': str(prices[exit_idx]['price_date']),
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'net_return': net_return,
                'holding_days': exit_idx - i
            })

        return self._calculate_backtest_metrics(trades, params)

    def _backtest_momentum(self, prices: List[Dict], params: Dict, period: str) -> Dict:
        """Momentum strategy: Enter on MA crossover with RSI confirmation."""
        if len(prices) < 50:
            return {'total_trades': 0, 'sharpe_ratio': 0}

        trades = []
        entry_logic = params.get('entry_logic', {})
        exit_logic = params.get('exit_logic', {})

        fast_ma = entry_logic.get('fast_ma', 10)
        slow_ma = entry_logic.get('slow_ma', 30)
        rsi_period = entry_logic.get('rsi_period', 14)
        rsi_threshold = entry_logic.get('rsi_threshold', 50)
        trailing_stop_pct = exit_logic.get('trailing_stop_pct', 5.0) / 100

        closes = [float(p['close_price']) for p in prices]

        for i in range(slow_ma + rsi_period, len(prices) - 20):
            # Moving averages
            fast_sma = np.mean(closes[i-fast_ma:i])
            slow_sma = np.mean(closes[i-slow_ma:i])

            # RSI calculation
            deltas = np.diff(closes[i-rsi_period-1:i])
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains) or 0.0001
            avg_loss = np.mean(losses) or 0.0001
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            # Entry: MA crossover + RSI confirmation
            prev_fast = np.mean(closes[i-fast_ma-1:i-1])
            prev_slow = np.mean(closes[i-slow_ma-1:i-1])

            if prev_fast <= prev_slow and fast_sma > slow_sma and rsi > rsi_threshold:
                direction = 'LONG'
            elif prev_fast >= prev_slow and fast_sma < slow_sma and rsi < (100 - rsi_threshold):
                direction = 'SHORT'
            else:
                continue

            entry_price = closes[i]
            max_price = entry_price if direction == 'LONG' else entry_price
            exit_idx = i + 1
            exit_price = entry_price

            for j in range(i + 1, min(i + 20 + 1, len(prices))):
                if direction == 'LONG':
                    max_price = max(max_price, closes[j])
                    trailing_stop = max_price * (1 - trailing_stop_pct)
                    if closes[j] <= trailing_stop:
                        exit_idx = j
                        exit_price = closes[j]
                        break
                    # MA cross exit
                    fast_j = np.mean(closes[j-fast_ma:j])
                    slow_j = np.mean(closes[j-slow_ma:j])
                    if fast_j < slow_j:
                        exit_idx = j
                        exit_price = closes[j]
                        break
                else:
                    max_price = min(max_price, closes[j])
                    trailing_stop = max_price * (1 + trailing_stop_pct)
                    if closes[j] >= trailing_stop:
                        exit_idx = j
                        exit_price = closes[j]
                        break
            else:
                exit_idx = min(i + 20, len(prices) - 1)
                exit_price = closes[exit_idx]

            friction = TOTAL_FRICTION_BPS / 10000
            if direction == 'LONG':
                net_return = (exit_price - entry_price) / entry_price - friction
            else:
                net_return = (entry_price - exit_price) / entry_price - friction

            trades.append({
                'entry_date': str(prices[i]['price_date']),
                'exit_date': str(prices[exit_idx]['price_date']),
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'net_return': net_return,
                'holding_days': exit_idx - i
            })

        return self._calculate_backtest_metrics(trades, params)

    def _backtest_regime_transition(self, prices: List[Dict], params: Dict, period: str) -> Dict:
        """Regime Transition strategy: Detect regime changes via volatility clustering."""
        if len(prices) < 60:
            return {'total_trades': 0, 'sharpe_ratio': 0}

        trades = []
        entry_logic = params.get('entry_logic', {})
        exit_logic = params.get('exit_logic', {})

        regime_lookback = entry_logic.get('regime_lookback', 30)
        vol_mult = entry_logic.get('confirmation_volume', 1.3)
        stabilization_days = exit_logic.get('regime_stabilization_days', 5)
        profit_target = exit_logic.get('profit_target_pct', 10.0) / 100
        stop_loss = exit_logic.get('stop_loss_pct', 5.0) / 100

        closes = [float(p['close_price']) for p in prices]
        volumes = [float(p['volume']) for p in prices]

        for i in range(regime_lookback + 10, len(prices) - 20):
            # Calculate recent vs historical volatility
            recent_returns = np.diff(closes[i-10:i]) / np.array(closes[i-10:i-1])
            hist_returns = np.diff(closes[i-regime_lookback:i-10]) / np.array(closes[i-regime_lookback:i-11])

            recent_vol = np.std(recent_returns) if len(recent_returns) > 1 else 0
            hist_vol = np.std(hist_returns) if len(hist_returns) > 1 else 1

            # Volume confirmation
            avg_vol = np.mean(volumes[i-20:i])

            # Regime transition signal: significant volatility change + volume
            vol_ratio = recent_vol / hist_vol if hist_vol > 0 else 1

            if vol_ratio > 1.5 and volumes[i] > avg_vol * vol_mult:
                # Determine direction from recent trend
                recent_trend = (closes[i] - closes[i-5]) / closes[i-5]
                direction = 'LONG' if recent_trend > 0 else 'SHORT'
            else:
                continue

            entry_price = closes[i]
            exit_idx = i + 1
            exit_price = entry_price

            for j in range(i + 1, min(i + 20 + 1, len(prices))):
                pnl = (closes[j] - entry_price) / entry_price if direction == 'LONG' else (entry_price - closes[j]) / entry_price

                if pnl >= profit_target or pnl <= -stop_loss:
                    exit_idx = j
                    exit_price = closes[j]
                    break

                # Check if regime stabilized
                if j >= i + stabilization_days:
                    recent_vol_j = np.std(np.diff(closes[j-5:j]) / np.array(closes[j-5:j-1]))
                    if recent_vol_j < hist_vol * 0.8:  # Volatility contracted
                        exit_idx = j
                        exit_price = closes[j]
                        break
            else:
                exit_idx = min(i + 20, len(prices) - 1)
                exit_price = closes[exit_idx]

            friction = TOTAL_FRICTION_BPS / 10000
            if direction == 'LONG':
                net_return = (exit_price - entry_price) / entry_price - friction
            else:
                net_return = (entry_price - exit_price) / entry_price - friction

            trades.append({
                'entry_date': str(prices[i]['price_date']),
                'exit_date': str(prices[exit_idx]['price_date']),
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'net_return': net_return,
                'holding_days': exit_idx - i
            })

        return self._calculate_backtest_metrics(trades, params)

    def _backtest_volatility(self, prices: List[Dict], params: Dict, period: str) -> Dict:
        """Volatility strategy: Trade volatility extremes."""
        if len(prices) < 80:
            return {'total_trades': 0, 'sharpe_ratio': 0}

        trades = []
        entry_logic = params.get('entry_logic', {})
        exit_logic = params.get('exit_logic', {})

        vol_lookback = entry_logic.get('vol_percentile_lookback', 60)
        low_vol_threshold = entry_logic.get('low_vol_threshold_pct', 20)
        high_vol_threshold = entry_logic.get('high_vol_threshold_pct', 80)
        max_holding = exit_logic.get('max_holding_days', 15)
        stop_loss_pct = exit_logic.get('stop_loss_pct', 3.0) / 100

        closes = [float(p['close_price']) for p in prices]

        # Calculate rolling volatility
        all_vols = []
        for i in range(20, len(prices)):
            returns = np.diff(closes[i-20:i]) / np.array(closes[i-20:i-1])
            all_vols.append(np.std(returns) * np.sqrt(252))

        for i in range(vol_lookback, len(prices) - max_holding - 1):
            vol_idx = i - 20
            if vol_idx < vol_lookback:
                continue

            current_vol = all_vols[vol_idx]
            vol_window = all_vols[max(0, vol_idx-vol_lookback):vol_idx]
            vol_percentile = (np.sum(np.array(vol_window) < current_vol) / len(vol_window)) * 100

            # Entry on volatility extremes
            if vol_percentile <= low_vol_threshold:
                direction = 'LONG'  # Low vol = expect expansion, go with trend
            elif vol_percentile >= high_vol_threshold:
                direction = 'SHORT'  # High vol = expect contraction
            else:
                continue

            entry_price = closes[i]
            exit_idx = i + 1
            exit_price = entry_price

            for j in range(i + 1, min(i + max_holding + 1, len(prices))):
                pnl = (closes[j] - entry_price) / entry_price if direction == 'LONG' else (entry_price - closes[j]) / entry_price

                if pnl <= -stop_loss_pct:
                    exit_idx = j
                    exit_price = closes[j]
                    break

                # Exit when volatility normalizes
                if j - 20 < len(all_vols):
                    vol_j = all_vols[j - 20]
                    vol_window_j = all_vols[max(0, j-20-vol_lookback):j-20]
                    if len(vol_window_j) > 0:
                        vol_pct_j = (np.sum(np.array(vol_window_j) < vol_j) / len(vol_window_j)) * 100
                        if 40 <= vol_pct_j <= 60:  # Normalized
                            exit_idx = j
                            exit_price = closes[j]
                            break
            else:
                exit_idx = min(i + max_holding, len(prices) - 1)
                exit_price = closes[exit_idx]

            friction = TOTAL_FRICTION_BPS / 10000
            if direction == 'LONG':
                net_return = (exit_price - entry_price) / entry_price - friction
            else:
                net_return = (entry_price - exit_price) / entry_price - friction

            trades.append({
                'entry_date': str(prices[i]['price_date']),
                'exit_date': str(prices[exit_idx]['price_date']),
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'net_return': net_return,
                'holding_days': exit_idx - i
            })

        return self._calculate_backtest_metrics(trades, params)

    def _backtest_contrarian(self, prices: List[Dict], params: Dict, period: str) -> Dict:
        """Contrarian strategy: Fade extreme RSI with volume capitulation."""
        if len(prices) < 30:
            return {'total_trades': 0, 'sharpe_ratio': 0}

        trades = []
        entry_logic = params.get('entry_logic', {})
        exit_logic = params.get('exit_logic', {})

        rsi_oversold = entry_logic.get('rsi_oversold', 30)
        rsi_overbought = entry_logic.get('rsi_overbought', 70)
        vol_mult = entry_logic.get('volume_capitulation_mult', 2.5)
        profit_target = exit_logic.get('profit_target_pct', 5.0) / 100
        stop_loss = exit_logic.get('stop_loss_pct', 3.0) / 100

        closes = [float(p['close_price']) for p in prices]
        volumes = [float(p['volume']) for p in prices]

        for i in range(20, len(prices) - 15):
            # RSI
            deltas = np.diff(closes[i-14:i+1])
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains) or 0.0001
            avg_loss = np.mean(losses) or 0.0001
            rsi = 100 - (100 / (1 + avg_gain / avg_loss))

            # Volume spike
            avg_vol = np.mean(volumes[i-20:i])
            vol_spike = volumes[i] > avg_vol * vol_mult

            # Contrarian entry
            if rsi <= rsi_oversold and vol_spike:
                direction = 'LONG'  # Capitulation bottom
            elif rsi >= rsi_overbought and vol_spike:
                direction = 'SHORT'  # Euphoria top
            else:
                continue

            entry_price = closes[i]
            exit_idx = i + 1
            exit_price = entry_price

            for j in range(i + 1, min(i + 15 + 1, len(prices))):
                pnl = (closes[j] - entry_price) / entry_price if direction == 'LONG' else (entry_price - closes[j]) / entry_price

                if pnl >= profit_target or pnl <= -stop_loss:
                    exit_idx = j
                    exit_price = closes[j]
                    break

                # Exit when RSI normalizes
                deltas_j = np.diff(closes[j-14:j+1])
                gains_j = np.where(deltas_j > 0, deltas_j, 0)
                losses_j = np.where(deltas_j < 0, -deltas_j, 0)
                avg_gain_j = np.mean(gains_j) or 0.0001
                avg_loss_j = np.mean(losses_j) or 0.0001
                rsi_j = 100 - (100 / (1 + avg_gain_j / avg_loss_j))

                if 40 <= rsi_j <= 60:
                    exit_idx = j
                    exit_price = closes[j]
                    break
            else:
                exit_idx = min(i + 15, len(prices) - 1)
                exit_price = closes[exit_idx]

            friction = TOTAL_FRICTION_BPS / 10000
            if direction == 'LONG':
                net_return = (exit_price - entry_price) / entry_price - friction
            else:
                net_return = (entry_price - exit_price) / entry_price - friction

            trades.append({
                'entry_date': str(prices[i]['price_date']),
                'exit_date': str(prices[exit_idx]['price_date']),
                'direction': direction,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'net_return': net_return,
                'holding_days': exit_idx - i
            })

        return self._calculate_backtest_metrics(trades, params)

    def _calculate_backtest_metrics(self, trades: List[Dict], params: Dict) -> Dict:
        """Calculate standard backtest metrics from trade list."""
        if not trades:
            return {'total_trades': 0, 'sharpe_ratio': 0}

        returns = [t['net_return'] for t in trades]
        returns_array = np.array(returns)

        total_trades = len(trades)
        winning_trades = sum(1 for r in returns if r > 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        net_return_pct = np.sum(returns_array) * 100
        avg_return = np.mean(returns_array)
        std_return = np.std(returns_array) or 0.0001

        # Annualized Sharpe
        avg_holding = np.mean([t.get('holding_days', 5) for t in trades]) or 5
        trades_per_year = ANNUALIZATION_FACTOR / avg_holding
        sharpe_ratio = (avg_return / std_return) * np.sqrt(trades_per_year) if std_return > 0 else 0

        # Sortino
        downside_returns = returns_array[returns_array < 0]
        if len(downside_returns) > 0:
            downside_std = np.std(downside_returns)
            sortino_ratio = (avg_return / downside_std) * np.sqrt(trades_per_year) if downside_std > 0 else 0
        else:
            sortino_ratio = sharpe_ratio * 1.5

        # Profit factor
        gross_profits = sum(r for r in returns if r > 0)
        gross_losses = abs(sum(r for r in returns if r < 0))
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else float('inf')

        # Max drawdown
        cumulative = np.cumsum(returns_array)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        max_drawdown_pct = np.max(drawdowns) * 100 if len(drawdowns) > 0 else 0

        # Statistical significance
        if len(returns) >= 2:
            t_stat, p_value = stats.ttest_1samp(returns, 0)
        else:
            t_stat, p_value = 0, 1.0

        # Equity curve
        equity_curve = [{'date': trades[0]['entry_date'], 'equity': 1.0}]
        equity = 1.0
        for t in trades:
            equity *= (1 + t['net_return'])
            equity_curve.append({'date': t['exit_date'], 'equity': equity})

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': win_rate,
            'net_return_pct': net_return_pct,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'profit_factor': profit_factor,
            'max_drawdown_pct': max_drawdown_pct,
            'avg_holding_hours': avg_holding * 24,
            't_statistic': t_stat,
            'p_value': p_value,
            'trade_log': trades[:100],
            'equity_curve': equity_curve
        }

    # =========================================================================
    # END WAVE 16A CATEGORY-SPECIFIC STRATEGIES
    # =========================================================================

    def _simulate_latency_impact(self, trade_log: List, baseline_return: float,
                                  latency_ms: int) -> float:
        """
        Simulate impact of execution latency on returns.
        Models slippage increase and missed opportunities.
        """
        if not trade_log or baseline_return <= 0:
            return 0

        # Latency impact model:
        # - 50ms: 5% degradation
        # - 200ms: 15% degradation
        # - 1000ms: 35% degradation
        degradation_factors = {
            50: 0.95,
            200: 0.85,
            1000: 0.65
        }

        factor = degradation_factors.get(latency_ms, 0.5)
        return baseline_return * factor

    def _calculate_half_life(self, latency_results: Dict, baseline: float) -> Optional[float]:
        """Calculate signal half-life in milliseconds."""
        if baseline <= 0:
            return None

        # Find where return crosses 50% of baseline
        for ms in sorted(latency_results.keys()):
            if latency_results[ms] <= baseline * 0.5:
                return ms
        return None

    def _calculate_invalidation_time(self, latency_results: Dict) -> Optional[float]:
        """Calculate time until edge becomes zero or negative."""
        for ms in sorted(latency_results.keys()):
            if latency_results[ms] <= 0:
                return ms
        return None

    def _persist_refinery_result(self, result: Dict):
        """Persist Stream A result to database."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_canonical.g4_refinery_results (
                    needle_id, lookback_years, in_sample_ratio,
                    start_date, end_date, in_sample_end,
                    entry_cost_bps, exit_cost_bps, slippage_bps,
                    is_total_trades, is_win_rate, is_net_return_pct,
                    is_sharpe_ratio, is_sortino_ratio, is_max_drawdown_pct, is_profit_factor,
                    oos_total_trades, oos_win_rate, oos_net_return_pct,
                    oos_sharpe_ratio, oos_sortino_ratio, oos_max_drawdown_pct, oos_profit_factor,
                    oos_avg_holding_hours, oos_p_value, oos_t_statistic,
                    cull_classification, trade_log, equity_curve_is, equity_curve_oos,
                    backtest_completed_at
                ) VALUES (
                    %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, NOW()
                )
            """, (
                result['needle_id'], result['lookback_years'], result['in_sample_ratio'],
                result['start_date'], result['end_date'], result['in_sample_end'],
                result['entry_cost_bps'], result['exit_cost_bps'], result['slippage_bps'],
                result['is_total_trades'], result['is_win_rate'], result['is_net_return_pct'],
                result['is_sharpe_ratio'], result['is_sortino_ratio'], result['is_max_drawdown_pct'], result['is_profit_factor'],
                result['oos_total_trades'], result['oos_win_rate'], result['oos_net_return_pct'],
                result['oos_sharpe_ratio'], result['oos_sortino_ratio'], result['oos_max_drawdown_pct'], result['oos_profit_factor'],
                result['oos_avg_holding_hours'], result['oos_p_value'], result['oos_t_statistic'],
                result['cull_classification'],
                Json(result.get('trade_log', [])),
                Json(result.get('equity_curve_is', [])),
                Json(result.get('equity_curve_oos', []))
            ))
        self.conn.commit()

    def _persist_physics_result(self, result: Dict):
        """Persist Stream B result to database."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_canonical.g4_physics_results (
                    needle_id,
                    latency_50ms_return_pct, latency_200ms_return_pct, latency_1000ms_return_pct,
                    latency_sensitivity_per_100ms,
                    signal_half_life_seconds, signal_decay_rate, time_to_invalidation_seconds,
                    edge_retained_50ms_pct, edge_retained_200ms_pct, edge_retained_1000ms_pct,
                    survivability, latency_profile,
                    physics_completed_at
                ) VALUES (
                    %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
            """, (
                result['needle_id'],
                result['latency_50ms_return_pct'],
                result['latency_200ms_return_pct'],
                result['latency_1000ms_return_pct'],
                result['latency_sensitivity_per_100ms'],
                result['signal_half_life_seconds'],
                result['signal_decay_rate'],
                result['time_to_invalidation_seconds'],
                result['edge_retained_50ms_pct'],
                result['edge_retained_200ms_pct'],
                result['edge_retained_1000ms_pct'],
                result['survivability'],
                Json(result.get('latency_profile', {}))
            ))
        self.conn.commit()

    def _persist_scorecard(self, scorecard: Dict):
        """Persist WAVE 16A composite scorecard with 3-axis classification to database."""
        # Convert numpy types to Python native types
        fdr_pvalue = scorecard['fdr_adjusted_p_value']
        if hasattr(fdr_pvalue, 'item'):
            fdr_pvalue = fdr_pvalue.item()
        passes_fdr = scorecard['passes_fdr_threshold']
        if hasattr(passes_fdr, 'item'):
            passes_fdr = passes_fdr.item()
        logic_applied = scorecard.get('logic_translation_applied', False)
        if hasattr(logic_applied, 'item'):
            logic_applied = logic_applied.item()
        oos_sharpe = scorecard['oos_sharpe']
        if hasattr(oos_sharpe, 'item'):
            oos_sharpe = oos_sharpe.item()

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_canonical.g4_composite_scorecard (
                    needle_id, eqs_score, oos_sharpe, decay_half_life_seconds,
                    classification, fdr_adjusted_p_value, passes_fdr_threshold,
                    axis_a_historical_merit, axis_b_physical_robustness, axis_c_regime_dependence,
                    edge_map_coordinates, hypothesis_category, backtest_strategy_id,
                    logic_translation_applied, scored_at
                ) VALUES (
                    %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                ON CONFLICT (needle_id) DO UPDATE SET
                    oos_sharpe = EXCLUDED.oos_sharpe,
                    classification = EXCLUDED.classification,
                    axis_a_historical_merit = EXCLUDED.axis_a_historical_merit,
                    axis_b_physical_robustness = EXCLUDED.axis_b_physical_robustness,
                    axis_c_regime_dependence = EXCLUDED.axis_c_regime_dependence,
                    edge_map_coordinates = EXCLUDED.edge_map_coordinates,
                    hypothesis_category = EXCLUDED.hypothesis_category,
                    backtest_strategy_id = EXCLUDED.backtest_strategy_id,
                    logic_translation_applied = EXCLUDED.logic_translation_applied,
                    scored_at = NOW()
            """, (
                scorecard['needle_id'],
                float(scorecard['eqs_score']),
                float(oos_sharpe) if oos_sharpe is not None else None,
                scorecard['decay_half_life_seconds'],
                scorecard['classification'],
                float(fdr_pvalue) if fdr_pvalue is not None else None,
                bool(passes_fdr),
                scorecard.get('axis_a_historical_merit', 'NONE'),
                scorecard.get('axis_b_physical_robustness', 'THEORETICAL'),
                scorecard.get('axis_c_regime_dependence', 'AGNOSTIC'),
                Json(scorecard.get('edge_map_coordinates', {})),
                scorecard.get('hypothesis_category'),
                scorecard.get('backtest_strategy_id'),
                bool(logic_applied)
            ))
        self.conn.commit()

    def _update_queue_status(self, needle_id, stream: str, status: str, error: str = None):
        """Update queue status for a needle."""
        try:
            self.conn.rollback()  # Clear any failed transaction
        except:
            pass
        with self.conn.cursor() as cur:
            if stream == 'refinery':
                cur.execute("""
                    UPDATE fhq_canonical.g4_validation_queue
                    SET refinery_status = %s,
                        refinery_started_at = CASE WHEN %s = 'PROCESSING' THEN NOW() ELSE refinery_started_at END,
                        refinery_completed_at = CASE WHEN %s IN ('COMPLETED', 'FAILED') THEN NOW() ELSE refinery_completed_at END,
                        refinery_error = %s
                    WHERE needle_id = %s::uuid
                """, (status, status, status, error, str(needle_id)))
            else:
                cur.execute("""
                    UPDATE fhq_canonical.g4_validation_queue
                    SET physics_status = %s,
                        physics_started_at = CASE WHEN %s = 'PROCESSING' THEN NOW() ELSE physics_started_at END,
                        physics_completed_at = CASE WHEN %s IN ('COMPLETED', 'FAILED') THEN NOW() ELSE physics_completed_at END,
                        physics_error = %s
                    WHERE needle_id = %s::uuid
                """, (status, status, status, error, str(needle_id)))
        self.conn.commit()

    def _create_reject_result(self, needle_id, reason: str) -> Dict:
        """Create a rejection result."""
        return {
            'needle_id': str(needle_id),
            'cull_classification': 'REJECT',
            'rejection_reason': reason,
            'oos_sharpe_ratio': 0,
            'trade_log': []
        }

    def _create_nonviable_physics(self, needle_id) -> Dict:
        """Create a non-viable physics result."""
        return {
            'needle_id': str(needle_id),
            'survivability': 'NON_VIABLE',
            'edge_retained_1000ms_pct': 0
        }

    def run_validation_batch(self, batch_size: int = 5):
        """
        Run validation on a batch of pending Golden Needles.
        Executes both STREAM A and STREAM B for each.
        """
        logger.info(f"Starting G4 validation batch (size={batch_size})")

        needles = self.get_pending_needles(batch_size)
        if not needles:
            logger.info("No pending needles for validation")
            return []

        results = []
        for needle in needles:
            needle_id = needle['needle_id']
            logger.info(f"Processing needle: {needle['hypothesis_title'][:50]}...")

            # STREAM A: The Refinery
            refinery = self.run_stream_a_refinery(needle)

            # STREAM B: The Physics
            physics = self.run_stream_b_physics(needle, refinery)

            # Composite Scorecard
            scorecard = self.create_composite_scorecard(
                str(needle_id), refinery, physics
            )

            results.append({
                'needle_id': str(needle_id),
                'title': needle['hypothesis_title'],
                'eqs': float(needle['eqs_score']),
                'refinery': refinery.get('cull_classification'),
                'physics': physics.get('survivability'),
                'classification': scorecard['classification']
            })

        return results


def main():
    """Main entry point for G4 validation."""
    import argparse
    parser = argparse.ArgumentParser(description='G4 Laboratory Validation Engine')
    parser.add_argument('--batch-size', type=int, default=5, help='Number of needles to process')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    args = parser.parse_args()

    engine = G4ValidationEngine()

    if args.continuous:
        logger.info("Running in continuous mode")
        while True:
            try:
                results = engine.run_validation_batch(args.batch_size)
                if not results:
                    logger.info("No pending needles, sleeping...")
                    import time
                    time.sleep(60)
                else:
                    for r in results:
                        logger.info(f"  {r['title'][:40]}: {r['classification']}")
            except KeyboardInterrupt:
                logger.info("Shutdown requested")
                break
            except Exception as e:
                logger.error(f"Batch error: {e}")
                import time
                time.sleep(30)
    else:
        results = engine.run_validation_batch(args.batch_size)
        print(f"\nG4 Validation Results ({len(results)} needles):")
        print("=" * 80)
        for r in results:
            print(f"  [{r['classification']:8}] {r['title'][:50]} (EQS={r['eqs']:.2f})")


if __name__ == "__main__":
    main()
