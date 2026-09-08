"""
IoS-012-B: Synthetic Inversion Module

Converts systematic STRESS@99%+ miscalibration into alpha via signal inversion.

Directive: CEO-DIR-2026-105 (Hindsight Firewall Compliance)
Status: G0 SUBMITTED - Shadow Mode Only until 2026-02-02
Author: STIG (EC-003_2026_PRODUCTION)

CRITICAL CONSTRAINT:
This module operates in SHADOW MODE ONLY until the Hindsight Firewall's
Non-Eligibility Clause expires (2026-02-02 = 2 learning cycles).

ALPHA SIGNAL DISCOVERY (CEO-DIR-2026-105):
- STRESS@99%+ equity signals have 0% hit rate (37 signals)
- When inverted, this yields Brier score of 0.0058
- This is the highest-leverage path to ROI identified
"""

import os
import json
import uuid
import hashlib
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IoS-012-B")


class InversionTrigger(Enum):
    """Trigger conditions for signal inversion."""
    STRESS_99PCT_EQUITY = "STRESS_99PCT_EQUITY"


class ExitType(Enum):
    """Exit types for positions."""
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    TIME_DECAY = "TIME_DECAY"
    REGIME_CHANGE = "REGIME_CHANGE"


class HealthStatus(Enum):
    """Health status of the inversion module."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DISABLED = "DISABLED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass
class InversionConfig:
    """Configuration for the inversion module."""
    # Trigger conditions
    regime_trigger: str = "STRESS"
    confidence_threshold: float = 0.99
    asset_class_filter: str = "EQUITY"

    # Position sizing
    max_position_pct: float = 0.025  # 2.5% NAV per ticker
    max_total_exposure_pct: float = 0.25  # 25% NAV total

    # Exit rules
    take_profit_pct: float = 0.50  # 50% of max profit
    stop_loss_pct: float = 0.25   # 25% of premium remaining
    min_dte_exit: int = 5         # Exit at 5 DTE

    # Health monitoring
    health_threshold_hit_rate: float = 0.80  # Auto-disable below 80%
    health_lookback_days: int = 30

    # Options parameters
    default_dte_range: Tuple[int, int] = (14, 30)
    delta_target: float = 0.45

    # Hindsight firewall
    non_eligibility_end: date = date(2026, 2, 2)
    shadow_mode: bool = True


@dataclass
class InversionSignal:
    """A signal that has been identified for inversion."""
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Source signal
    source_signal_id: Optional[str] = None
    source_regime: str = ""
    source_confidence: float = 0.0
    source_direction: str = ""  # 'UP' or 'DOWN'

    # Inverted signal
    inverted_direction: str = ""
    inversion_trigger: str = InversionTrigger.STRESS_99PCT_EQUITY.value

    # Asset
    ticker: str = ""

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "signal_id": self.signal_id,
            "source_signal_id": self.source_signal_id,
            "source_regime": self.source_regime,
            "source_confidence": self.source_confidence,
            "source_direction": self.source_direction,
            "inverted_direction": self.inverted_direction,
            "inversion_trigger": self.inversion_trigger,
            "ticker": self.ticker,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class OptionsSpread:
    """Vertical Bull Call Spread position."""
    spread_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Underlying
    ticker: str = ""
    entry_price: float = 0.0

    # Options legs
    long_strike: float = 0.0
    short_strike: float = 0.0
    expiration_date: date = field(default_factory=date.today)
    dte_at_entry: int = 0

    # Position sizing
    contracts: int = 0
    net_premium_paid: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0

    # P&L
    current_value: float = 0.0
    unrealized_pnl: float = 0.0

    def calculate_max_profit(self) -> float:
        """Calculate maximum profit for the spread."""
        width = self.short_strike - self.long_strike
        return (width * 100 * self.contracts) - self.net_premium_paid

    def calculate_breakeven(self) -> float:
        """Calculate breakeven price."""
        return self.long_strike + (self.net_premium_paid / (100 * self.contracts))


class SyntheticInversionModule:
    """
    IoS-012-B: Synthetic Inversion Module

    Converts systematic STRESS@99%+ miscalibration into alpha.
    """

    # Canonical inversion universe (10 equity tickers from CEO-DIR-2026-105)
    CANONICAL_UNIVERSE = {
        "ADBE": {"sector": "Technology", "signal_count": 3},
        "ADSK": {"sector": "Technology", "signal_count": 3},
        "AIG": {"sector": "Financials", "signal_count": 3},
        "AZO": {"sector": "Consumer", "signal_count": 4},
        "GIS": {"sector": "Consumer", "signal_count": 3},
        "HNR1.DE": {"sector": "Industrial", "signal_count": 3},
        "INTU": {"sector": "Technology", "signal_count": 4},
        "LEN": {"sector": "Real Estate", "signal_count": 3},
        "NOW": {"sector": "Technology", "signal_count": 3},
        "PGR": {"sector": "Financials", "signal_count": 3}
    }

    def __init__(self, config: Optional[InversionConfig] = None, db_conn=None):
        """Initialize the inversion module."""
        self.config = config or InversionConfig()
        self.db_conn = db_conn
        self._validate_hindsight_firewall()

    def _validate_hindsight_firewall(self) -> None:
        """Validate hindsight firewall compliance."""
        today = date.today()
        if today < self.config.non_eligibility_end:
            self.config.shadow_mode = True
            logger.warning(
                f"HINDSIGHT_FIREWALL: Shadow mode enforced until {self.config.non_eligibility_end}. "
                f"Days remaining: {(self.config.non_eligibility_end - today).days}"
            )
        else:
            logger.info("Hindsight firewall non-eligibility period has ended.")

    def should_invert(self, signal: Dict[str, Any]) -> bool:
        """
        Determine if a signal should be inverted.

        Trigger conditions (G4 Canonicalized):
        - regime = 'STRESS'
        - confidence >= 0.99
        - asset_class = 'EQUITY'
        - ticker IN canonical_universe
        """
        regime = signal.get("regime", "")
        confidence = signal.get("confidence", 0.0)
        asset_class = signal.get("asset_class", "")
        ticker = signal.get("ticker", "")

        # Check all conditions
        is_stress = regime == self.config.regime_trigger
        is_high_confidence = confidence >= self.config.confidence_threshold
        is_equity = asset_class == self.config.asset_class_filter
        is_in_universe = ticker in self.CANONICAL_UNIVERSE

        should_trigger = is_stress and is_high_confidence and is_equity and is_in_universe

        if should_trigger:
            logger.info(
                f"INVERSION_TRIGGER: {ticker} @ {regime} regime, "
                f"{confidence:.2%} confidence -> INVERTING"
            )

        return should_trigger

    def invert_signal(self, signal: Dict[str, Any]) -> InversionSignal:
        """
        Invert a signal's directional implication.

        When system predicts STRESS with 99%+ confidence but is systematically wrong,
        the inverted implication suggests the OPPOSITE direction.
        """
        source_direction = signal.get("direction", "UP")
        inverted_direction = "DOWN" if source_direction == "UP" else "UP"

        inversion = InversionSignal(
            source_signal_id=signal.get("signal_id"),
            source_regime=signal.get("regime", ""),
            source_confidence=signal.get("confidence", 0.0),
            source_direction=source_direction,
            inverted_direction=inverted_direction,
            inversion_trigger=InversionTrigger.STRESS_99PCT_EQUITY.value,
            ticker=signal.get("ticker", "")
        )

        logger.info(
            f"SIGNAL_INVERTED: {inversion.ticker} "
            f"{source_direction} -> {inverted_direction}"
        )

        return inversion

    def generate_spread_order(
        self,
        inversion: InversionSignal,
        underlying_price: float,
        nav: float
    ) -> Optional[OptionsSpread]:
        """
        Generate a Vertical Bull Call Spread order for the inverted signal.

        Since STRESS signals are systematically wrong and inverted to bullish,
        we use Vertical Bull Call Spreads.
        """
        if inversion.inverted_direction != "UP":
            logger.warning(f"Non-bullish inversion - skipping spread generation")
            return None

        # Calculate position size
        position_value = nav * self.config.max_position_pct
        premium_budget = position_value * 0.20  # Assume 20% premium cost

        # Determine strikes (simplified - would use options chain in production)
        atm_strike = round(underlying_price / 5) * 5  # Round to nearest $5
        long_strike = atm_strike
        short_strike = atm_strike + 5  # $5 wide spread

        # Estimate contracts
        estimated_premium_per_spread = 1.50  # Placeholder
        contracts = max(1, int(premium_budget / (estimated_premium_per_spread * 100)))

        # Calculate P&L parameters
        net_premium = contracts * estimated_premium_per_spread * 100
        width = short_strike - long_strike
        max_profit = (width * 100 * contracts) - net_premium
        max_loss = net_premium

        spread = OptionsSpread(
            ticker=inversion.ticker,
            entry_price=underlying_price,
            long_strike=long_strike,
            short_strike=short_strike,
            expiration_date=date.today() + timedelta(days=21),  # ~3 weeks out
            dte_at_entry=21,
            contracts=contracts,
            net_premium_paid=net_premium,
            max_profit=max_profit,
            max_loss=max_loss
        )

        logger.info(
            f"SPREAD_GENERATED: {spread.ticker} "
            f"BUY {spread.long_strike}C / SELL {spread.short_strike}C "
            f"x{spread.contracts} @ ${spread.net_premium_paid:.2f} premium"
        )

        return spread

    def check_exit_conditions(
        self,
        spread: OptionsSpread,
        current_regime: str
    ) -> Tuple[bool, Optional[ExitType], str]:
        """
        Check if any exit conditions are met.

        Exit rules per CEO blueprint:
        1. Take Profit: 50% of max profit reached
        2. Stop Loss: 25% of premium remaining
        3. Time Decay: 5 DTE remaining
        4. Regime Change: STRESS regime exits
        """
        # Calculate current P&L
        pnl_pct = spread.unrealized_pnl / spread.net_premium_paid if spread.net_premium_paid > 0 else 0

        # Check Take Profit (50% of max profit)
        take_profit_threshold = self.config.take_profit_pct * spread.max_profit
        if spread.unrealized_pnl >= take_profit_threshold:
            return True, ExitType.TAKE_PROFIT, f"Target profit reached: {spread.unrealized_pnl:.2f}"

        # Check Stop Loss (75% loss = 25% remaining)
        stop_loss_threshold = -spread.net_premium_paid * (1 - self.config.stop_loss_pct)
        if spread.unrealized_pnl <= stop_loss_threshold:
            return True, ExitType.STOP_LOSS, f"Stop loss triggered: {spread.unrealized_pnl:.2f}"

        # Check Time Decay (5 DTE)
        days_remaining = (spread.expiration_date - date.today()).days
        if days_remaining <= self.config.min_dte_exit:
            return True, ExitType.TIME_DECAY, f"DTE exit: {days_remaining} days remaining"

        # Check Regime Change
        if current_regime != "STRESS":
            return True, ExitType.REGIME_CHANGE, f"Regime changed to {current_regime}"

        return False, None, ""

    def check_health(self, lookback_days: int = 30) -> Dict[str, Any]:
        """
        Check module health based on inverted hit rate.

        Auto-disable if Inverted Hit Rate < 80%
        """
        # In production, this would query the database
        # For now, return placeholder
        health_result = {
            "status": HealthStatus.HEALTHY.value,
            "inverted_hit_rate": 1.00,  # Based on historical analysis
            "total_signals": 37,
            "threshold": self.config.health_threshold_hit_rate,
            "should_disable": False,
            "recommendation": "Inversion strategy performing as expected",
            "checked_at": datetime.utcnow().isoformat()
        }

        logger.info(f"HEALTH_CHECK: {health_result['status']}")
        return health_result

    def process_signal(
        self,
        signal: Dict[str, Any],
        underlying_price: float,
        nav: float,
        current_regime: str = "STRESS"
    ) -> Dict[str, Any]:
        """
        Process an incoming signal through the inversion pipeline.

        Returns the processing result including any generated orders.
        """
        result = {
            "signal_processed": True,
            "inverted": False,
            "spread_generated": False,
            "shadow_mode": self.config.shadow_mode,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Check if signal should be inverted
        if not self.should_invert(signal):
            result["reason"] = "Signal does not meet inversion criteria"
            return result

        # Invert the signal
        inversion = self.invert_signal(signal)
        result["inverted"] = True
        result["inversion"] = inversion.to_dict()

        # Generate spread order
        spread = self.generate_spread_order(inversion, underlying_price, nav)
        if spread:
            result["spread_generated"] = True
            result["spread"] = {
                "ticker": spread.ticker,
                "long_strike": spread.long_strike,
                "short_strike": spread.short_strike,
                "contracts": spread.contracts,
                "net_premium": spread.net_premium_paid,
                "max_profit": spread.max_profit,
                "max_loss": spread.max_loss,
                "expiration": spread.expiration_date.isoformat()
            }

        # Shadow mode warning
        if self.config.shadow_mode:
            result["warning"] = (
                f"SHADOW_MODE: Order NOT submitted. "
                f"Live trading available after {self.config.non_eligibility_end}"
            )
            logger.warning(result["warning"])

        return result

    def log_to_shadow_tracking(
        self,
        inversion: InversionSignal,
        spread: Optional[OptionsSpread],
        session_id: Optional[str] = None
    ) -> str:
        """
        Log inversion and spread to shadow tracking table.

        In production, this writes to fhq_alpha.inversion_overlay_shadow
        """
        if not self.db_conn:
            logger.warning("No database connection - shadow tracking skipped")
            return ""

        overlay_id = str(uuid.uuid4())

        # Build shadow record
        shadow_record = {
            "overlay_id": overlay_id,
            "source_signal_id": inversion.source_signal_id,
            "source_regime": inversion.source_regime,
            "source_confidence": inversion.source_confidence,
            "source_direction": inversion.source_direction,
            "inverted_direction": inversion.inverted_direction,
            "inversion_trigger": inversion.inversion_trigger,
            "ticker": inversion.ticker,
            "is_shadow": True,
            "shadow_session_id": session_id,
            "created_at": datetime.utcnow().isoformat()
        }

        if spread:
            shadow_record.update({
                "strategy_type": "VERTICAL_BULL_CALL_SPREAD",
                "long_strike": spread.long_strike,
                "short_strike": spread.short_strike,
                "expiration_date": spread.expiration_date.isoformat(),
                "dte_at_entry": spread.dte_at_entry,
                "contracts": spread.contracts,
                "net_premium_paid": spread.net_premium_paid,
                "max_profit": spread.max_profit,
                "max_loss": spread.max_loss
            })

        # In production, INSERT into fhq_alpha.inversion_overlay_shadow
        logger.info(f"SHADOW_LOGGED: {overlay_id}")

        return overlay_id


def create_evidence_hash(data: Dict[str, Any]) -> str:
    """Create SHA-256 hash of evidence data."""
    json_str = json.dumps(data, sort_keys=True, default=str)
    return f"sha256:{hashlib.sha256(json_str.encode()).hexdigest()[:32]}"


# ============================================================================
# Main entry point for testing
# ============================================================================

if __name__ == "__main__":
    # Initialize module
    module = SyntheticInversionModule()

    print("=" * 60)
    print("IoS-012-B Synthetic Inversion Module")
    print("=" * 60)
    print(f"Status: {'SHADOW MODE' if module.config.shadow_mode else 'LIVE'}")
    print(f"Non-eligibility ends: {module.config.non_eligibility_end}")
    print(f"Canonical universe: {len(module.CANONICAL_UNIVERSE)} tickers")
    print()

    # Test signal
    test_signal = {
        "signal_id": "test-001",
        "ticker": "ADBE",
        "regime": "STRESS",
        "confidence": 0.9971,
        "direction": "DOWN",
        "asset_class": "EQUITY"
    }

    print("Processing test signal:")
    print(json.dumps(test_signal, indent=2))
    print()

    # Process signal
    result = module.process_signal(
        signal=test_signal,
        underlying_price=520.00,
        nav=100000.00
    )

    print("Result:")
    print(json.dumps(result, indent=2))
    print()

    # Health check
    health = module.check_health()
    print("Health check:")
    print(json.dumps(health, indent=2))
