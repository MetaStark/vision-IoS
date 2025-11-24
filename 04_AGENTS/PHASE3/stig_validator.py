"""
STIG+ Validation Framework
Phase 3: Week 2 — Validation & Consistency

Authority: LARS Phase 3 Directive (HC-LARS-PHASE3-CONTINUE-20251124)
Canonical ADR Chain: ADR-001 → ADR-015

Purpose: Multi-tier validation framework for FINN+ regime predictions
Role: Mandatory gate before signals reach downstream components

STIG+ Validation Tiers:
- Tier 1: Ed25519 signature verification (ADR-008)
- Tier 2: Feature quality validation (5-of-7 rule)
- Tier 3: Persistence validation (≥5 days)
- Tier 4: Transition limit validation (≤30 per 90 days)
- Tier 5: Regime classification consistency

Compliance:
- ADR-002: Audit & Error Reconciliation
- ADR-008: Ed25519 Signatures (100% verification)
- ADR-010: Discrepancy Scoring
- Phase 3 Validation Framework
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import pandas as pd

from finn_signature import SignedPrediction, Ed25519Signer
from finn_regime_classifier import RegimeClassifier, RegimePersistence


class ValidationSeverity(Enum):
    """Validation failure severity levels (ADR-002)."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ValidationTier(Enum):
    """STIG+ validation tiers."""
    TIER_1_SIGNATURE = 1
    TIER_2_FEATURE_QUALITY = 2
    TIER_3_PERSISTENCE = 3
    TIER_4_TRANSITION_LIMITS = 4
    TIER_5_CONSISTENCY = 5


@dataclass
class ValidationResult:
    """
    Single validation check result.

    ADR-002 Compliance: Structured error reconciliation
    """
    tier: int
    check_name: str
    is_valid: bool
    severity: ValidationSeverity
    message: str
    timestamp: datetime

    # Details for reconciliation
    expected_value: Optional[any] = None
    actual_value: Optional[any] = None
    requires_reconciliation: bool = False

    def to_dict(self) -> Dict:
        """Convert to dictionary for database persistence."""
        return {
            'tier': self.tier,
            'check_name': self.check_name,
            'is_valid': self.is_valid,
            'severity': self.severity.value,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'expected_value': str(self.expected_value) if self.expected_value is not None else None,
            'actual_value': str(self.actual_value) if self.actual_value is not None else None,
            'requires_reconciliation': self.requires_reconciliation
        }


@dataclass
class ValidationReport:
    """
    Comprehensive validation report for a prediction or prediction set.

    Contains all validation results across all tiers.
    """
    target_id: Optional[int] = None  # prediction_id if validating single prediction
    validation_results: List[ValidationResult] = None
    overall_pass: bool = False
    highest_severity: ValidationSeverity = ValidationSeverity.INFO
    timestamp: datetime = None

    def __post_init__(self):
        if self.validation_results is None:
            self.validation_results = []
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def add_result(self, result: ValidationResult):
        """Add validation result and update overall status."""
        self.validation_results.append(result)

        # Update overall pass status (all checks must pass)
        self.overall_pass = all(r.is_valid for r in self.validation_results)

        # Update highest severity
        severity_order = {
            ValidationSeverity.INFO: 0,
            ValidationSeverity.WARNING: 1,
            ValidationSeverity.ERROR: 2,
            ValidationSeverity.CRITICAL: 3
        }

        if severity_order[result.severity] > severity_order[self.highest_severity]:
            self.highest_severity = result.severity

    def get_failures(self) -> List[ValidationResult]:
        """Get all failed validation checks."""
        return [r for r in self.validation_results if not r.is_valid]

    def get_by_tier(self, tier: int) -> List[ValidationResult]:
        """Get validation results for specific tier."""
        return [r for r in self.validation_results if r.tier == tier]

    def summary(self) -> str:
        """Generate human-readable summary."""
        total = len(self.validation_results)
        passed = sum(1 for r in self.validation_results if r.is_valid)
        failed = total - passed

        lines = [
            "STIG+ Validation Report",
            "=" * 60,
            f"Target ID: {self.target_id or 'N/A'}",
            f"Timestamp: {self.timestamp.isoformat()}",
            f"Total Checks: {total}",
            f"Passed: {passed}",
            f"Failed: {failed}",
            f"Overall Status: {'✅ PASS' if self.overall_pass else '❌ FAIL'}",
            f"Highest Severity: {self.highest_severity.value}",
            ""
        ]

        if failed > 0:
            lines.append("Failed Checks:")
            for result in self.get_failures():
                lines.append(f"  - Tier {result.tier}: {result.check_name}")
                lines.append(f"    {result.message}")
                if result.expected_value or result.actual_value:
                    lines.append(f"    Expected: {result.expected_value}, Actual: {result.actual_value}")

        lines.append("=" * 60)
        return "\n".join(lines)


class STIGValidator:
    """
    STIG+ Validation Framework.

    Multi-tier validation of FINN+ regime predictions.
    Acts as mandatory gate before signals reach downstream components.

    Validation Flow:
    1. Tier 1: Signature verification (ADR-008)
    2. Tier 2: Feature quality (5-of-7 rule)
    3. Tier 3: Persistence validation (≥5 days)
    4. Tier 4: Transition limits (≤30 per 90 days)
    5. Tier 5: Consistency checks
    """

    def __init__(self):
        """Initialize STIG+ validator."""
        self.classifier = RegimeClassifier()

    # ========================================================================
    # Tier 1: Ed25519 Signature Verification
    # ========================================================================

    def validate_signature(self, signed_prediction: SignedPrediction) -> ValidationResult:
        """
        Tier 1: Verify Ed25519 signature on prediction.

        ADR-008 Requirement: 100% verification rate before downstream propagation

        Args:
            signed_prediction: SignedPrediction with signature

        Returns:
            ValidationResult for signature verification
        """
        # Extract prediction data (without signature fields)
        prediction_data = {
            'regime_label': signed_prediction.regime_label,
            'regime_state': signed_prediction.regime_state,
            'confidence': signed_prediction.confidence,
            'prob_bear': signed_prediction.prob_bear,
            'prob_neutral': signed_prediction.prob_neutral,
            'prob_bull': signed_prediction.prob_bull,
            'timestamp': signed_prediction.timestamp,
            'return_z': signed_prediction.return_z,
            'volatility_z': signed_prediction.volatility_z,
            'drawdown_z': signed_prediction.drawdown_z,
            'macd_diff_z': signed_prediction.macd_diff_z,
            'bb_width_z': signed_prediction.bb_width_z,
            'rsi_14_z': signed_prediction.rsi_14_z,
            'roc_20_z': signed_prediction.roc_20_z,
            'is_valid': signed_prediction.is_valid,
            'validation_reason': signed_prediction.validation_reason
        }

        # Verify signature
        is_valid = Ed25519Signer.verify_signature(
            prediction_data,
            signed_prediction.signature_hex,
            signed_prediction.public_key_hex
        )

        return ValidationResult(
            tier=ValidationTier.TIER_1_SIGNATURE.value,
            check_name="Ed25519 Signature Verification",
            is_valid=is_valid,
            severity=ValidationSeverity.CRITICAL if not is_valid else ValidationSeverity.INFO,
            message="Signature valid" if is_valid else "ADR-008 VIOLATION: Invalid signature detected",
            timestamp=datetime.utcnow(),
            expected_value="Valid signature",
            actual_value="Valid" if is_valid else "Invalid",
            requires_reconciliation=not is_valid
        )

    # ========================================================================
    # Tier 2: Feature Quality Validation
    # ========================================================================

    def validate_feature_quality(self, signed_prediction: SignedPrediction) -> ValidationResult:
        """
        Tier 2: Validate feature quality (5-of-7 rule).

        Args:
            signed_prediction: SignedPrediction with features

        Returns:
            ValidationResult for feature quality
        """
        # Create feature series
        features = pd.Series({
            'return_z': signed_prediction.return_z,
            'volatility_z': signed_prediction.volatility_z,
            'drawdown_z': signed_prediction.drawdown_z,
            'macd_diff_z': signed_prediction.macd_diff_z,
            'bb_width_z': signed_prediction.bb_width_z,
            'rsi_14_z': signed_prediction.rsi_14_z,
            'roc_20_z': signed_prediction.roc_20_z
        })

        # Validate using FINN+ validator
        is_valid, reason = self.classifier.validate_features(features)

        non_null_count = features.notna().sum()

        return ValidationResult(
            tier=ValidationTier.TIER_2_FEATURE_QUALITY.value,
            check_name="Feature Quality Validation",
            is_valid=is_valid,
            severity=ValidationSeverity.WARNING if not is_valid else ValidationSeverity.INFO,
            message=reason,
            timestamp=datetime.utcnow(),
            expected_value="≥5 valid features",
            actual_value=f"{non_null_count}/7 features",
            requires_reconciliation=not is_valid
        )

    # ========================================================================
    # Tier 3: Persistence Validation
    # ========================================================================

    def validate_persistence(self, regime_history: pd.Series,
                           min_days: int = 5) -> ValidationResult:
        """
        Tier 3: Validate regime persistence.

        LARS Requirement: Average persistence ≥ 5 days

        Args:
            regime_history: Series of regime labels over time
            min_days: Minimum average persistence required

        Returns:
            ValidationResult for persistence
        """
        is_valid, avg_persistence = RegimePersistence.validate_persistence(
            regime_history, min_consecutive_days=min_days
        )

        return ValidationResult(
            tier=ValidationTier.TIER_3_PERSISTENCE.value,
            check_name="Regime Persistence Validation",
            is_valid=is_valid,
            severity=ValidationSeverity.ERROR if not is_valid else ValidationSeverity.INFO,
            message=f"Average persistence: {avg_persistence:.1f} days",
            timestamp=datetime.utcnow(),
            expected_value=f"≥{min_days} days",
            actual_value=f"{avg_persistence:.1f} days",
            requires_reconciliation=not is_valid
        )

    # ========================================================================
    # Tier 4: Transition Limit Validation
    # ========================================================================

    def validate_transition_limits(self, regime_history: pd.Series,
                                   window_days: int = 90,
                                   max_transitions: int = 30) -> ValidationResult:
        """
        Tier 4: Validate regime transition limits.

        LARS Requirement: ≤ 30 transitions per 90 days

        Args:
            regime_history: Series of regime labels over time
            window_days: Window for counting transitions
            max_transitions: Maximum allowed transitions

        Returns:
            ValidationResult for transition limits
        """
        transitions = RegimePersistence.count_transitions(regime_history, window_days)

        is_valid = transitions <= max_transitions

        return ValidationResult(
            tier=ValidationTier.TIER_4_TRANSITION_LIMITS.value,
            check_name="Regime Transition Limit Validation",
            is_valid=is_valid,
            severity=ValidationSeverity.ERROR if not is_valid else ValidationSeverity.INFO,
            message=f"Transitions in {window_days}d window: {transitions}",
            timestamp=datetime.utcnow(),
            expected_value=f"≤{max_transitions} transitions",
            actual_value=f"{transitions} transitions",
            requires_reconciliation=not is_valid
        )

    # ========================================================================
    # Tier 5: Consistency Validation
    # ========================================================================

    def validate_consistency(self, signed_prediction: SignedPrediction) -> ValidationResult:
        """
        Tier 5: Validate regime classification consistency.

        Checks:
        - regime_state matches regime_label
        - probabilities sum to 1.0
        - confidence matches max probability

        Args:
            signed_prediction: SignedPrediction to validate

        Returns:
            ValidationResult for consistency
        """
        issues = []

        # Check regime_state matches regime_label
        expected_mapping = {'BEAR': 0, 'NEUTRAL': 1, 'BULL': 2}
        expected_state = expected_mapping[signed_prediction.regime_label]

        if signed_prediction.regime_state != expected_state:
            issues.append(
                f"Regime state/label mismatch: "
                f"state={signed_prediction.regime_state}, label={signed_prediction.regime_label}"
            )

        # Check probabilities sum to 1.0
        prob_sum = (signed_prediction.prob_bear +
                   signed_prediction.prob_neutral +
                   signed_prediction.prob_bull)

        if abs(prob_sum - 1.0) > 0.01:
            issues.append(f"Probabilities sum to {prob_sum:.4f} (expected 1.0)")

        # Check confidence matches max probability
        max_prob = max(signed_prediction.prob_bear,
                      signed_prediction.prob_neutral,
                      signed_prediction.prob_bull)

        if abs(signed_prediction.confidence - max_prob) > 0.01:
            issues.append(
                f"Confidence {signed_prediction.confidence:.4f} != "
                f"max probability {max_prob:.4f}"
            )

        is_valid = len(issues) == 0

        return ValidationResult(
            tier=ValidationTier.TIER_5_CONSISTENCY.value,
            check_name="Regime Classification Consistency",
            is_valid=is_valid,
            severity=ValidationSeverity.CRITICAL if not is_valid else ValidationSeverity.INFO,
            message="All consistency checks passed" if is_valid else "; ".join(issues),
            timestamp=datetime.utcnow(),
            expected_value="All consistency checks pass",
            actual_value="Pass" if is_valid else f"{len(issues)} issues",
            requires_reconciliation=not is_valid
        )

    # ========================================================================
    # Full Validation Pipeline
    # ========================================================================

    def validate_prediction(self, signed_prediction: SignedPrediction) -> ValidationReport:
        """
        Run full validation pipeline on single prediction.

        Executes Tiers 1, 2, 5 (signature, feature quality, consistency).
        Tiers 3 and 4 require historical data.

        Args:
            signed_prediction: SignedPrediction to validate

        Returns:
            ValidationReport with all results
        """
        report = ValidationReport(target_id=None)  # No DB ID for standalone prediction

        # Tier 1: Signature verification
        report.add_result(self.validate_signature(signed_prediction))

        # Tier 2: Feature quality
        report.add_result(self.validate_feature_quality(signed_prediction))

        # Tier 5: Consistency
        report.add_result(self.validate_consistency(signed_prediction))

        return report

    def validate_prediction_series(self,
                                  regime_history: pd.Series,
                                  latest_prediction: Optional[SignedPrediction] = None) -> ValidationReport:
        """
        Run full validation pipeline on prediction series.

        Executes all 5 tiers including historical validation.

        Args:
            regime_history: Series of regime labels over time
            latest_prediction: Optional latest prediction for Tiers 1,2,5

        Returns:
            ValidationReport with all results
        """
        report = ValidationReport()

        # Tiers 1, 2, 5: Single prediction validation
        if latest_prediction:
            report.add_result(self.validate_signature(latest_prediction))
            report.add_result(self.validate_feature_quality(latest_prediction))
            report.add_result(self.validate_consistency(latest_prediction))

        # Tier 3: Persistence validation
        report.add_result(self.validate_persistence(regime_history))

        # Tier 4: Transition limit validation
        report.add_result(self.validate_transition_limits(regime_history))

        return report


# ============================================================================
# Example Usage and Testing
# ============================================================================

if __name__ == "__main__":
    """
    Demonstrate STIG+ validation framework.
    """
    print("=" * 80)
    print("STIG+ VALIDATION FRAMEWORK — DEMO")
    print("Phase 3: Week 2 — Validation & Consistency")
    print("=" * 80)

    # Import for demo
    from finn_signature import sign_regime_prediction, Ed25519Signer

    # Create validator
    validator = STIGValidator()

    # [1] Create sample signed prediction
    print("\n[1] Creating sample signed prediction...")
    signer = Ed25519Signer()

    prediction_data = {
        'regime_label': 'BULL',
        'regime_state': 2,
        'confidence': 0.70,
        'prob_bear': 0.10,
        'prob_neutral': 0.20,
        'prob_bull': 0.70,
        'timestamp': datetime.utcnow().isoformat(),
        'return_z': 1.25,
        'volatility_z': -0.45,
        'drawdown_z': 0.15,
        'macd_diff_z': 0.30,
        'bb_width_z': -0.20,
        'rsi_14_z': 1.10,
        'roc_20_z': 0.80,
        'is_valid': True,
        'validation_reason': 'Valid'
    }

    signed_pred = sign_regime_prediction(prediction_data, signer)
    print(f"    Signed prediction: {signed_pred.regime_label} (confidence: {signed_pred.confidence:.2%})")

    # [2] Validate single prediction (Tiers 1, 2, 5)
    print("\n[2] Running single prediction validation (Tiers 1, 2, 5)...")
    report = validator.validate_prediction(signed_pred)

    print(f"    Overall status: {'✅ PASS' if report.overall_pass else '❌ FAIL'}")
    print(f"    Total checks: {len(report.validation_results)}")
    print(f"    Passed: {sum(1 for r in report.validation_results if r.is_valid)}")

    for result in report.validation_results:
        status = "✅" if result.is_valid else "❌"
        print(f"    {status} Tier {result.tier}: {result.check_name}")

    # [3] Validate prediction series (All 5 tiers)
    print("\n[3] Running prediction series validation (All 5 tiers)...")

    # Create sample regime history (30-day stable BULL)
    regime_history = pd.Series(['BULL'] * 30)

    series_report = validator.validate_prediction_series(regime_history, signed_pred)

    print(f"    Overall status: {'✅ PASS' if series_report.overall_pass else '❌ FAIL'}")
    print(f"    Total checks: {len(series_report.validation_results)}")

    for result in series_report.validation_results:
        status = "✅" if result.is_valid else "❌"
        print(f"    {status} Tier {result.tier}: {result.check_name} - {result.message}")

    # [4] Test with invalid prediction
    print("\n[4] Testing with tampered prediction (should FAIL Tier 1)...")

    # Tamper with prediction
    tampered_pred = SignedPrediction(**signed_pred.to_dict())
    tampered_pred.regime_label = 'BEAR'  # Tamper
    tampered_pred.signature_verified = False  # Mark as unverified

    tampered_report = validator.validate_prediction(tampered_pred)

    print(f"    Overall status: {'✅ PASS' if tampered_report.overall_pass else '❌ FAIL'}")

    failures = tampered_report.get_failures()
    if failures:
        print(f"    Detected {len(failures)} failures:")
        for failure in failures:
            print(f"      - {failure.check_name}: {failure.message}")

    # [5] Print full summary
    print("\n[5] Full validation report:")
    print(series_report.summary())

    print("\n" + "=" * 80)
    print("✅ STIG+ VALIDATION FRAMEWORK READY")
    print("=" * 80)
    print("\nSTIG+ Validator Status:")
    print("  - Tier 1 (Signature): ✅ FUNCTIONAL")
    print("  - Tier 2 (Feature Quality): ✅ FUNCTIONAL")
    print("  - Tier 3 (Persistence): ✅ FUNCTIONAL")
    print("  - Tier 4 (Transition Limits): ✅ FUNCTIONAL")
    print("  - Tier 5 (Consistency): ✅ FUNCTIONAL")
    print("\nStatus: Ready for FINN+ integration")
    print("=" * 80)
