"""
Phase 2 Hypothesis Swarm - Pydantic Models V1.1
CEO Directive: OFFLINE DESIGN
Date: 2026-01-28
Author: STIG

V1.1 Upgrades:
- trigger_event_id: 1:1 traceability between triggers and outcomes
- PnL split: gross vs net separation
- ATR multiples: Dynamic risk normalization
- Context versioning: Model versions included in hash computation
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Dict, Any, List, Literal
from uuid import UUID
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json


class ContextSnapshotV11(BaseModel):
    """Context at experiment entry point - V1.1 with model versions."""
    regime: str
    regime_model_version: str
    vol_state: str
    vol_model_version: str
    macro_state: str
    macro_model_version: str = "NA"  # Default if not versioned
    defcon_level: Optional[int] = None
    capture_timestamp: datetime
    data_sources: Dict[str, str]

    def compute_hash(self) -> str:
        """SHA256 hash of critical context fields INCLUDING model versions."""
        canonical = json.dumps({
            "regime": self.regime,
            "regime_model_version": self.regime_model_version,
            "vol_state": self.vol_state,
            "vol_model_version": self.vol_model_version,
            "macro_state": self.macro_state,
            "macro_model_version": self.macro_model_version
        }, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()


class TriggerIndicators(BaseModel):
    """Indicator values captured at trigger event."""
    bbw: Optional[Decimal] = None
    bbw_percentile: Optional[int] = None
    rsi_14: Optional[Decimal] = None
    bb_position: Optional[str] = None
    bb_upper: Optional[Decimal] = None
    bb_middle: Optional[Decimal] = None
    atr_14: Decimal  # Required for ATR normalization
    entry_price: Decimal


class TriggerEventEntry(BaseModel):
    """Trigger event record - links experiments to outcomes."""
    trigger_event_id: Optional[UUID] = None
    experiment_id: UUID
    asset_id: str
    event_timestamp: datetime
    trigger_indicators: TriggerIndicators
    entry_price: Decimal
    price_source_table: str = "fhq_data.price_series"
    price_source_row_id: Optional[UUID] = None
    context_snapshot_hash: str
    context_details: ContextSnapshotV11
    created_at: Optional[datetime] = None
    created_by: str = "STIG"
    evidence_hash: Optional[str] = None

    @model_validator(mode='after')
    def validate_context_hash(self):
        """Ensure context_snapshot_hash matches computed hash from context_details."""
        if self.context_details:
            expected = self.context_details.compute_hash()
            if self.context_snapshot_hash != expected:
                raise ValueError(f"Context hash mismatch: {self.context_snapshot_hash} != {expected}")
        return self


class OutcomeLedgerEntryV11(BaseModel):
    """Outcome ledger record V1.1 with full traceability."""
    outcome_id: Optional[UUID] = None
    experiment_id: UUID
    trigger_event_id: UUID  # V1.1: Required 1:1 traceability
    result_bool: bool

    # V1.1: PnL split
    pnl_gross_simulated: Optional[Decimal] = Field(None, description="Pure price move P&L")
    pnl_net_est: Optional[Decimal] = Field(None, description="Gross minus fees/spread estimate")

    context_snapshot_hash: str
    context_details: ContextSnapshotV11

    # Excursions (absolute)
    mfe: Optional[Decimal] = Field(None, description="Max Favorable Excursion")
    mae: Optional[Decimal] = Field(None, description="Max Adverse Excursion")

    # V1.1: ATR multiples
    mfe_atr_multiple: Optional[Decimal] = Field(None, description="MFE / ATR at entry")
    mae_atr_multiple: Optional[Decimal] = Field(None, description="MAE / ATR at entry")

    time_to_outcome: Optional[timedelta] = None
    created_at: Optional[datetime] = None
    created_by: str = "STIG"
    evidence_hash: Optional[str] = None

    @model_validator(mode='after')
    def validate_context_hash(self):
        """Ensure context_snapshot_hash matches computed hash from context_details."""
        if self.context_details:
            expected = self.context_details.compute_hash()
            if self.context_snapshot_hash != expected:
                raise ValueError(f"Context hash mismatch: {self.context_snapshot_hash} != {expected}")
        return self


class AlphaSatelliteTriggerV11(BaseModel):
    """Trigger condition for Alpha Satellite test V1.1."""
    indicator: str
    condition: str
    regime_filter: Optional[str] = None
    source_table: str
    capture_fields: List[str]  # V1.1: Explicit fields to capture


class AlphaSatelliteMeasurementV11(BaseModel):
    """Single measurement in Alpha Satellite test V1.1."""
    name: str
    type: Literal["BOOLEAN", "NUMERIC", "INTEGER", "INTERVAL"]
    description: str
    threshold_atr_multiple: Optional[Decimal] = None  # V1.1: ATR-normalized threshold


class ATRLoggingConfig(BaseModel):
    """ATR logging configuration for ATR-normalized thresholds."""
    field: str
    stored_in: str
    used_for: List[str]


class AlphaSatelliteConfigV11(BaseModel):
    """Complete Alpha Satellite test configuration V1.1."""
    test_code: str
    version: str = "1.1"
    hypothesis_text: str
    trigger: AlphaSatelliteTriggerV11
    measurements: List[AlphaSatelliteMeasurementV11]
    falsification_criteria: Dict[str, Any]
    regime_validity: List[str]
    min_sample_size: int = 30
    atr_logging: ATRLoggingConfig
    regime_model_version_required: Optional[str] = None


# =============================================================================
# PRE-CONFIGURED TEST BLUEPRINTS V1.1
# =============================================================================

TEST_A_VOLATILITY_SQUEEZE_V11 = AlphaSatelliteConfigV11(
    test_code="ALPHA_SAT_A",
    version="1.1",
    hypothesis_text="Volatility compression contains latent energy",
    trigger=AlphaSatelliteTriggerV11(
        indicator="BBW",
        condition="< 10th_percentile",
        source_table="fhq_indicators.volatility",
        capture_fields=["bbw", "bbw_percentile", "atr_14", "entry_price"]
    ),
    measurements=[
        AlphaSatelliteMeasurementV11(
            name="direction_correct",
            type="BOOLEAN",
            description="Did price move in predicted direction?"
        ),
        AlphaSatelliteMeasurementV11(
            name="magnitude_significant",
            type="BOOLEAN",
            description="Was movement > 2x ATR?",
            threshold_atr_multiple=Decimal("2.0")
        )
    ],
    falsification_criteria={
        "direction_falsified_if": "win_rate_direction < 0.52",
        "magnitude_falsified_if": "magnitude_hit_rate < 0.30",
        "magnitude_threshold_atr_multiple": 2.0
    },
    regime_validity=["NEUTRAL", "LOW_VOL"],
    min_sample_size=30,
    atr_logging=ATRLoggingConfig(
        field="atr_14",
        stored_in="trigger_indicators.atr_14",
        used_for=["magnitude_threshold", "mfe_atr_multiple", "mae_atr_multiple"]
    ),
    regime_model_version_required="sovereign_v4_ddatp_1.2"
)

TEST_B_REGIME_ALIGNMENT_V11 = AlphaSatelliteConfigV11(
    test_code="ALPHA_SAT_B",
    version="1.1",
    hypothesis_text="RSI meaning is regime-dependent (Context > Signal)",
    trigger=AlphaSatelliteTriggerV11(
        indicator="RSI_14",
        condition="> 70",
        regime_filter="STRONG_BULL",
        source_table="fhq_indicators.momentum",
        capture_fields=["rsi_14", "atr_14", "entry_price"]
    ),
    measurements=[
        AlphaSatelliteMeasurementV11(
            name="long_win_rate",
            type="NUMERIC",
            description="Win rate on trend-following LONG signals"
        ),
        AlphaSatelliteMeasurementV11(
            name="short_win_rate",
            type="NUMERIC",
            description="Win rate on mean-reversion SHORT signals"
        ),
        AlphaSatelliteMeasurementV11(
            name="mae_survived",
            type="BOOLEAN",
            description="Did trade survive MAE < 1.5x ATR?",
            threshold_atr_multiple=Decimal("1.5")
        )
    ],
    falsification_criteria={
        "falsified_if": "trend_win_rate < mean_reversion_win_rate",
        "mae_threshold_atr_multiple": 1.5,
        "mae_survival_required": True
    },
    regime_validity=["STRONG_BULL"],
    min_sample_size=25,
    atr_logging=ATRLoggingConfig(
        field="atr_14",
        stored_in="trigger_indicators.atr_14",
        used_for=["mae_threshold", "mae_atr_multiple"]
    ),
    regime_model_version_required="sovereign_v4_ddatp_1.2"
)

TEST_C_MEAN_REVERSION_V11 = AlphaSatelliteConfigV11(
    test_code="ALPHA_SAT_C",
    version="1.1",
    hypothesis_text="Mean reversion dominates in low-trend regimes",
    trigger=AlphaSatelliteTriggerV11(
        indicator="BB_POSITION",
        condition="price > bb_upper",
        regime_filter="NEUTRAL",
        source_table="fhq_indicators.volatility",
        capture_fields=["bb_upper", "bb_middle", "atr_14", "entry_price"]
    ),
    measurements=[
        AlphaSatelliteMeasurementV11(
            name="touched_mean",
            type="BOOLEAN",
            description="Did price touch 20 SMA within timeframe?"
        ),
        AlphaSatelliteMeasurementV11(
            name="time_to_mean_minutes",
            type="INTEGER",
            description="Minutes until mean touch (for distribution)"
        )
    ],
    falsification_criteria={
        "falsified_if": "mean_touch_rate < 0.55",
        "max_time_hours": 72
    },
    regime_validity=["NEUTRAL", "WEAK_BEAR", "WEAK_BULL"],
    min_sample_size=30,
    atr_logging=ATRLoggingConfig(
        field="atr_14",
        stored_in="trigger_indicators.atr_14",
        used_for=["mfe_atr_multiple", "mae_atr_multiple"]
    ),
    regime_model_version_required="sovereign_v4_ddatp_1.2"
)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_all_test_blueprints() -> List[AlphaSatelliteConfigV11]:
    """Return all pre-configured test blueprints."""
    return [
        TEST_A_VOLATILITY_SQUEEZE_V11,
        TEST_B_REGIME_ALIGNMENT_V11,
        TEST_C_MEAN_REVERSION_V11
    ]


def get_test_blueprint_by_code(code: str) -> Optional[AlphaSatelliteConfigV11]:
    """Get a specific test blueprint by code."""
    blueprints = {
        "ALPHA_SAT_A": TEST_A_VOLATILITY_SQUEEZE_V11,
        "ALPHA_SAT_B": TEST_B_REGIME_ALIGNMENT_V11,
        "ALPHA_SAT_C": TEST_C_MEAN_REVERSION_V11
    }
    return blueprints.get(code)
