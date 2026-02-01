"""
EWRE Calculator - Event-Weighted Risk Envelope
CEO-DIR-2026-01-22: TP/SL anchored to volatility + regime, NOT feelings

Calculates dynamic stop-loss and take-profit levels based on:
- ATR-based volatility
- Regime-conditioned multipliers
- Confidence damping (including Brier inversion)
- Causal alignment bonus
- Historical accuracy calibration

Author: STIG (CTO)
Contract: EC-003_2026_PRODUCTION
"""

import os
import logging
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', '127.0.0.1'),
    'port': int(os.getenv('POSTGRES_PORT', 54322)),
    'dbname': os.getenv('POSTGRES_DB', 'postgres'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
}


# =============================================================================
# CONFIGURATION
# =============================================================================

# Base ATR multipliers (from CPTO EC-015 v1.2.0)
BASE_ATR_SL = 2.0    # 2x ATR for stop loss
BASE_ATR_TP = 2.5    # 2.5x ATR for take profit (1.25 R:R baseline)

# Regime adjustments (from CEO meta-analysis + signal_executor_daemon.py)
REGIME_ADJUSTMENTS = {
    'BULL': {'sl_mult': 1.25, 'tp_mult': 1.60, 'description': 'Let winners run'},
    'STRONG_BULL': {'sl_mult': 1.25, 'tp_mult': 1.60, 'description': 'Let winners run'},
    'BEAR': {'sl_mult': 0.67, 'tp_mult': 0.60, 'description': 'Tight exits'},
    'STRONG_BEAR': {'sl_mult': 0.67, 'tp_mult': 0.60, 'description': 'Tight exits'},
    'STRESS': {'sl_mult': 0.67, 'tp_mult': 0.60, 'description': 'Capital preservation'},
    'BROKEN': {'sl_mult': 0.50, 'tp_mult': 0.40, 'description': 'Emergency mode'},
    'NEUTRAL': {'sl_mult': 1.00, 'tp_mult': 1.00, 'description': 'Baseline'},
}

# Inversion bonus from Brier meta-analysis (12.68% improvement)
INVERSION_TP_BONUS = 1.15  # +15% to TP when inversion active

# Hard limits
MIN_SL_PCT = 0.01    # 1% minimum stop
MAX_SL_PCT = 0.10    # 10% maximum stop
MIN_RR_RATIO = 1.25  # Minimum risk-reward ratio


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class EWREInput:
    """Inputs for Event-Weighted Risk Envelope calculation."""
    damped_confidence: float       # From SkillDamper (0-1)
    historical_accuracy: float     # From calibration gates (0-1)
    volatility_atr_pct: float      # ATR-14 as percentage of price
    regime: str                    # Current regime
    asset_class: str               # CRYPTO, EQUITY, ETF
    inversion_flag: bool           # STRESS/BULL_CRYPTO inversion
    causal_bonus: float            # 0.0-0.15 from causal alignment
    reliability_score: float = 0.5 # From Brier decomposition (lower = better)


@dataclass
class EWREOutput:
    """Event-Weighted Risk Envelope output."""
    stop_loss_pct: float           # e.g., 0.03 = 3%
    take_profit_pct: float         # e.g., 0.08 = 8%
    risk_reward_ratio: float       # TP/SL
    stop_type: str                 # "STOP_MARKET" or "STOP_LIMIT"
    calculation_audit: Dict[str, Any]


# =============================================================================
# EWRE CALCULATOR
# =============================================================================

def calculate_ewre(inputs: EWREInput) -> EWREOutput:
    """
    Calculate Event-Weighted Risk Envelope.

    CEO Requirements:
    - TP/SL anchored to volatility + regime, NOT feelings
    - Confidence damping at extremes (dual-end inversion)
    - Integration with Brier decomposition findings
    - Causal bonus for high-alignment setups

    Args:
        inputs: EWREInput with all market context

    Returns:
        EWREOutput with calculated envelope and full audit trail
    """
    logger.info(f"[EWRE] Calculating for {inputs.regime} regime, "
                f"ATR={inputs.volatility_atr_pct:.2f}%, "
                f"conf={inputs.damped_confidence:.2f}")

    # Get regime adjustment
    regime_adj = REGIME_ADJUSTMENTS.get(
        inputs.regime,
        {'sl_mult': 1.0, 'tp_mult': 1.0, 'description': 'Unknown regime'}
    )

    # Confidence-weighted adjustment
    # Lower confidence = wider stops (more room), tighter targets (less ambitious)
    # Scale: 0.5 confidence → factor 0.75, 1.0 confidence → factor 1.0
    confidence_sl_factor = 0.5 + (inputs.damped_confidence * 0.5)  # 0.5-1.0
    confidence_tp_factor = 0.5 + (inputs.damped_confidence * 0.5)  # 0.5-1.0

    # Reliability penalty (from Brier decomposition)
    # Higher reliability_score = worse calibration = wider stops
    # Scale: 0.0 reliability → penalty 1.0, 1.0 reliability → penalty 1.5
    reliability_penalty = 1.0 + (inputs.reliability_score * 0.5)  # 1.0-1.5

    # Causal bonus rewards good alignment with tighter stops
    # Scale: 0.0 bonus → factor 1.0, 0.15 bonus → factor 0.97
    causal_sl_adjustment = 1.0 - (inputs.causal_bonus * 0.2)  # 0.97-1.0
    causal_tp_adjustment = 1.0 + (inputs.causal_bonus * 0.3)  # 1.0-1.045

    # Inversion bonus (12.68% improvement from Brier meta-analysis)
    inversion_mult = INVERSION_TP_BONUS if inputs.inversion_flag else 1.0

    # Calculate final ATR multipliers
    sl_multiplier = (
        BASE_ATR_SL
        * regime_adj['sl_mult']
        * (1.0 / confidence_sl_factor)  # Lower confidence = wider SL
        * reliability_penalty
        * causal_sl_adjustment
    )

    tp_multiplier = (
        BASE_ATR_TP
        * regime_adj['tp_mult']
        * confidence_tp_factor
        * inversion_mult
        * causal_tp_adjustment
    )

    # Convert ATR multipliers to actual percentages
    stop_loss_pct = inputs.volatility_atr_pct * sl_multiplier / 100.0
    take_profit_pct = inputs.volatility_atr_pct * tp_multiplier / 100.0

    # Apply hard caps
    stop_loss_pct = max(MIN_SL_PCT, min(stop_loss_pct, MAX_SL_PCT))

    # Ensure minimum risk-reward ratio
    min_tp_pct = stop_loss_pct * MIN_RR_RATIO
    take_profit_pct = max(take_profit_pct, min_tp_pct)

    # Calculate final risk-reward ratio
    risk_reward_ratio = take_profit_pct / stop_loss_pct if stop_loss_pct > 0 else 0

    # Determine stop type based on regime
    # STRESS/BROKEN: stop-market for guaranteed exit (accept slippage)
    # Normal: stop-limit for price control
    if inputs.regime in ('STRESS', 'BROKEN'):
        stop_type = "STOP_MARKET"
    else:
        stop_type = "STOP_LIMIT"

    # Build audit trail
    calculation_audit = {
        'inputs': asdict(inputs),
        'base_atr_sl': BASE_ATR_SL,
        'base_atr_tp': BASE_ATR_TP,
        'regime_adjustment': regime_adj,
        'confidence_sl_factor': confidence_sl_factor,
        'confidence_tp_factor': confidence_tp_factor,
        'reliability_penalty': reliability_penalty,
        'causal_sl_adjustment': causal_sl_adjustment,
        'causal_tp_adjustment': causal_tp_adjustment,
        'inversion_mult': inversion_mult,
        'sl_multiplier': sl_multiplier,
        'tp_multiplier': tp_multiplier,
        'pre_cap_sl_pct': inputs.volatility_atr_pct * sl_multiplier / 100.0,
        'pre_cap_tp_pct': inputs.volatility_atr_pct * tp_multiplier / 100.0,
        'hard_caps_applied': {
            'min_sl_pct': MIN_SL_PCT,
            'max_sl_pct': MAX_SL_PCT,
            'min_rr_ratio': MIN_RR_RATIO
        },
        'calculated_at': datetime.now(timezone.utc).isoformat()
    }

    result = EWREOutput(
        stop_loss_pct=round(stop_loss_pct, 4),
        take_profit_pct=round(take_profit_pct, 4),
        risk_reward_ratio=round(risk_reward_ratio, 2),
        stop_type=stop_type,
        calculation_audit=calculation_audit
    )

    logger.info(f"[EWRE] Result: SL={result.stop_loss_pct:.2%}, "
                f"TP={result.take_profit_pct:.2%}, "
                f"R:R={result.risk_reward_ratio:.1f}:1, "
                f"Type={result.stop_type}")

    return result


def calculate_bracket_prices(
    entry_price: float,
    direction: str,
    ewre: EWREOutput
) -> Dict[str, float]:
    """
    Calculate absolute TP/SL prices from EWRE percentages.

    Args:
        entry_price: Entry limit price
        direction: "LONG" or "SHORT"
        ewre: EWRE output with percentages

    Returns:
        Dict with take_profit_price, stop_loss_price, stop_limit_price
    """
    if direction == "LONG":
        take_profit_price = entry_price * (1 + ewre.take_profit_pct)
        stop_loss_price = entry_price * (1 - ewre.stop_loss_pct)
        # Stop-limit: set limit 0.5% below stop for buffer
        stop_limit_price = stop_loss_price * 0.995 if ewre.stop_type == "STOP_LIMIT" else None
    else:  # SHORT
        take_profit_price = entry_price * (1 - ewre.take_profit_pct)
        stop_loss_price = entry_price * (1 + ewre.stop_loss_pct)
        # Stop-limit: set limit 0.5% above stop for buffer
        stop_limit_price = stop_loss_price * 1.005 if ewre.stop_type == "STOP_LIMIT" else None

    return {
        'take_profit_price': round(take_profit_price, 2),
        'stop_loss_price': round(stop_loss_price, 2),
        'stop_limit_price': round(stop_limit_price, 2) if stop_limit_price else None
    }


# =============================================================================
# DATABASE INTEGRATION
# =============================================================================

def get_confidence_calibration(
    forecast_type: str = 'PRICE_DIRECTION',
    regime: str = 'ALL'
) -> Dict[str, float]:
    """
    Fetch confidence calibration gates from database.

    Returns:
        Dict with historical_accuracy, confidence_ceiling, reliability_score
    """
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT
                historical_accuracy,
                confidence_ceiling,
                sample_size,
                safety_margin
            FROM fhq_governance.confidence_calibration_gates
            WHERE forecast_type = %s
              AND (regime = %s OR regime = 'ALL')
            ORDER BY
                CASE WHEN regime = %s THEN 0 ELSE 1 END,
                created_at DESC
            LIMIT 1
        """, (forecast_type, regime, regime))

        row = cur.fetchone()
        if row:
            return {
                'historical_accuracy': float(row['historical_accuracy'] or 0.5),
                'confidence_ceiling': float(row['confidence_ceiling'] or 0.5),
                'reliability_score': 1.0 - float(row['historical_accuracy'] or 0.5),
                'sample_size': int(row['sample_size'] or 0)
            }
        else:
            # Cold start fallback
            return {
                'historical_accuracy': 0.40,
                'confidence_ceiling': 0.40,
                'reliability_score': 0.60,
                'sample_size': 0
            }

    except Exception as e:
        logger.error(f"[EWRE] Failed to get calibration: {e}")
        return {
            'historical_accuracy': 0.40,
            'confidence_ceiling': 0.40,
            'reliability_score': 0.60,
            'sample_size': 0
        }
    finally:
        if conn:
            conn.close()


def get_current_atr(asset: str, lookback_days: int = 14) -> Optional[float]:
    """
    Get current ATR as percentage of price for an asset.

    Returns:
        ATR as percentage (e.g., 2.8 means 2.8%)
    """
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Try to get from technical indicators
        cur.execute("""
            SELECT
                atr_14 / NULLIF(close_price, 0) * 100 as atr_pct
            FROM fhq_research.technical_signal_feed
            WHERE canonical_id = %s
              AND atr_14 IS NOT NULL
            ORDER BY signal_time DESC
            LIMIT 1
        """, (asset.replace('/', '').replace('-', ''),))

        row = cur.fetchone()
        if row and row['atr_pct']:
            return float(row['atr_pct'])

        # Fallback: estimate from recent volatility
        cur.execute("""
            SELECT
                STDDEV(pct_change) * SQRT(14) * 100 as estimated_atr_pct
            FROM (
                SELECT
                    (close - LAG(close) OVER (ORDER BY date)) / LAG(close) OVER (ORDER BY date) as pct_change
                FROM fhq_research.price_history
                WHERE symbol = %s
                ORDER BY date DESC
                LIMIT 30
            ) sub
            WHERE pct_change IS NOT NULL
        """, (asset,))

        row = cur.fetchone()
        if row and row['estimated_atr_pct']:
            return float(row['estimated_atr_pct'])

        # Final fallback: asset-class defaults
        if 'BTC' in asset or 'ETH' in asset:
            return 3.5  # Crypto default
        elif 'SPY' in asset or 'QQQ' in asset:
            return 1.2  # ETF default
        else:
            return 2.0  # Generic default

    except Exception as e:
        logger.error(f"[EWRE] Failed to get ATR for {asset}: {e}")
        return 2.5  # Safe default
    finally:
        if conn:
            conn.close()


def detect_inversion_condition(
    regime: str,
    raw_confidence: float,
    asset_class: str
) -> tuple[bool, Optional[str]]:
    """
    Detect if Brier inversion should be applied.

    From CEO meta-analysis:
    - STRESS @ 99%+ confidence: 0% hit rate → MANDATORY inversion
    - BULL CRYPTO @ 99%+ confidence: 87.77% wrong → inversion recommended

    Returns:
        Tuple of (inversion_flag, inversion_type)
    """
    # STRESS regime with high confidence
    if regime == 'STRESS' and raw_confidence > 0.70:
        return True, "STRESS_HIGH_CONFIDENCE"

    # BULL CRYPTO with extreme confidence
    if regime in ('BULL', 'STRONG_BULL') and asset_class == 'CRYPTO' and raw_confidence > 0.95:
        return True, "BULL_CRYPTO_EXTREME"

    # No inversion needed
    return False, None


# =============================================================================
# MAIN / TESTING
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("EWRE Calculator Test")
    print("=" * 60)

    # Test scenarios
    test_cases = [
        {
            'name': 'BTC NEUTRAL regime, moderate confidence',
            'inputs': EWREInput(
                damped_confidence=0.65,
                historical_accuracy=0.47,
                volatility_atr_pct=2.8,
                regime='NEUTRAL',
                asset_class='CRYPTO',
                inversion_flag=False,
                causal_bonus=0.05,
                reliability_score=0.53
            )
        },
        {
            'name': 'BTC BULL regime with inversion',
            'inputs': EWREInput(
                damped_confidence=0.75,
                historical_accuracy=0.40,
                volatility_atr_pct=3.2,
                regime='BULL',
                asset_class='CRYPTO',
                inversion_flag=True,
                causal_bonus=0.10,
                reliability_score=0.60
            )
        },
        {
            'name': 'SPY STRESS regime',
            'inputs': EWREInput(
                damped_confidence=0.55,
                historical_accuracy=0.30,
                volatility_atr_pct=1.8,
                regime='STRESS',
                asset_class='EQUITY',
                inversion_flag=False,
                causal_bonus=0.0,
                reliability_score=0.70
            )
        }
    ]

    for test in test_cases:
        print(f"\n{'='*60}")
        print(f"Test: {test['name']}")
        print("-" * 60)

        result = calculate_ewre(test['inputs'])

        print(f"Stop Loss: {result.stop_loss_pct:.2%}")
        print(f"Take Profit: {result.take_profit_pct:.2%}")
        print(f"Risk/Reward: {result.risk_reward_ratio:.1f}:1")
        print(f"Stop Type: {result.stop_type}")

        # Calculate actual prices for $100,000 BTC
        entry_price = 103500.0
        prices = calculate_bracket_prices(entry_price, "LONG", result)
        print(f"\nFor entry @ ${entry_price:,.0f} LONG:")
        print(f"  TP: ${prices['take_profit_price']:,.2f}")
        print(f"  SL: ${prices['stop_loss_price']:,.2f}")
        if prices['stop_limit_price']:
            print(f"  SL Limit: ${prices['stop_limit_price']:,.2f}")

    print("\n" + "=" * 60)
    print("EWRE Calculator Test Complete")
    print("=" * 60)
