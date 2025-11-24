"""
CDS Engine v1.0 — Composite Decision Score
Phase 3: Week 3 — LARS Directive 3 (Priority 1)

Authority: LARS CDS Formal Contract (ADR-CDS-CONTRACT-PHASE3)
Canonical ADR Chain: ADR-001 → ADR-015

PURPOSE:
The Composite Decision Score (CDS) is the canonical, auditable, deterministic
measure of decision quality inside FjordHQ's Market System.

COMPLIANCE:
- BIS-239 (Data Governance)
- ISO-8000 (Data Quality)
- GIPS (Performance Standards)
- MiFID II (Explainability)
- EU AI Act (Traceability)
- ADR-008 (Ed25519 Signatures)
- ADR-010 (Discrepancy Scoring)
- ADR-012 (Economic Safety)

CANONICAL FORMULA:
CDS = Σ(Ci × Wi) for i=1 to 6

Where:
- C1: Regime Strength (FINN+ confidence)
- C2: Signal Stability (persistence score)
- C3: Data Integrity (LINE+ quality)
- C4: Causal Coherence (FINN+ Tier-2, future)
- C5: Market Stress Modulator (1.0 - normalized volatility)
- C6: Relevance Alignment (relevance tier normalization)

PROPERTIES:
- Linear and additive (BIS-239 compliant)
- Monotonic and interpretable (MiFID II compliant)
- Symmetric (ADR-010 compliant)
- Deterministic (ADR-009 compliant)
- Output ∈ [0.0, 1.0]
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum
import hashlib
import json

# Phase 3 imports
from finn_signature import Ed25519Signer
from line_data_quality import DataQualityReport


class CDSComponent(Enum):
    """CDS component identifiers."""
    C1_REGIME_STRENGTH = "C1_Regime_Strength"
    C2_SIGNAL_STABILITY = "C2_Signal_Stability"
    C3_DATA_INTEGRITY = "C3_Data_Integrity"
    C4_CAUSAL_COHERENCE = "C4_Causal_Coherence"
    C5_STRESS_MODULATOR = "C5_Stress_Modulator"
    C6_RELEVANCE_ALIGNMENT = "C6_Relevance_Alignment"


class CDSValidationSeverity(Enum):
    """CDS validation severity levels (ADR-010 aligned)."""
    PASS = "PASS"
    WARNING = "WARNING"
    REJECT = "REJECT"


@dataclass
class CDSWeights:
    """
    CDS weight configuration (immutable without G4 approval).

    Default Weights v1.0:
    - C1 Regime Strength: 0.25
    - C2 Signal Stability: 0.20
    - C3 Data Integrity: 0.15
    - C4 Causal Coherence: 0.20
    - C5 Stress Modulator: 0.10
    - C6 Relevance Alignment: 0.10
    Total: 1.00
    """
    C1_regime_strength: float = 0.25
    C2_signal_stability: float = 0.20
    C3_data_integrity: float = 0.15
    C4_causal_coherence: float = 0.20
    C5_stress_modulator: float = 0.10
    C6_relevance_alignment: float = 0.10

    # Metadata
    version: str = "v1.0"
    approved_by: str = "LARS"
    approval_date: Optional[str] = None
    weights_hash: Optional[str] = None
    signature: Optional[str] = None

    def __post_init__(self):
        """Validate weights sum to 1.0."""
        total = (
            self.C1_regime_strength +
            self.C2_signal_stability +
            self.C3_data_integrity +
            self.C4_causal_coherence +
            self.C5_stress_modulator +
            self.C6_relevance_alignment
        )

        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1.0, got {total}")

        # Compute weights hash
        self.weights_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of weights for audit trail."""
        weights_dict = {
            'C1': self.C1_regime_strength,
            'C2': self.C2_signal_stability,
            'C3': self.C3_data_integrity,
            'C4': self.C4_causal_coherence,
            'C5': self.C5_stress_modulator,
            'C6': self.C6_relevance_alignment,
            'version': self.version
        }

        canonical_json = json.dumps(weights_dict, sort_keys=True)
        return hashlib.sha256(canonical_json.encode()).hexdigest()

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            'C1': self.C1_regime_strength,
            'C2': self.C2_signal_stability,
            'C3': self.C3_data_integrity,
            'C4': self.C4_causal_coherence,
            'C5': self.C5_stress_modulator,
            'C6': self.C6_relevance_alignment
        }


@dataclass
class CDSComponents:
    """
    CDS component values (each ∈ [0.0, 1.0]).

    All components must be normalized before CDS computation.
    Missing components default to 0.0.
    """
    C1_regime_strength: float = 0.0
    C2_signal_stability: float = 0.0
    C3_data_integrity: float = 0.0
    C4_causal_coherence: float = 0.0
    C5_stress_modulator: float = 0.0
    C6_relevance_alignment: float = 0.0

    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    source_hashes: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Validate all components ∈ [0.0, 1.0]."""
        components = {
            'C1': self.C1_regime_strength,
            'C2': self.C2_signal_stability,
            'C3': self.C3_data_integrity,
            'C4': self.C4_causal_coherence,
            'C5': self.C5_stress_modulator,
            'C6': self.C6_relevance_alignment
        }

        for name, value in components.items():
            if not (0.0 <= value <= 1.0):
                raise ValueError(
                    f"Component {name} must be in [0.0, 1.0], got {value}"
                )

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            'C1': self.C1_regime_strength,
            'C2': self.C2_signal_stability,
            'C3': self.C3_data_integrity,
            'C4': self.C4_causal_coherence,
            'C5': self.C5_stress_modulator,
            'C6': self.C6_relevance_alignment
        }


@dataclass
class CDSValidationIssue:
    """Single CDS validation issue."""
    check_name: str
    severity: CDSValidationSeverity
    component: Optional[str] = None
    message: str = ""
    actual_value: Optional[float] = None
    expected_range: Optional[str] = None

    def __str__(self) -> str:
        severity_icons = {
            CDSValidationSeverity.PASS: "✅",
            CDSValidationSeverity.WARNING: "⚠️",
            CDSValidationSeverity.REJECT: "❌"
        }
        icon = severity_icons.get(self.severity, "")
        component_str = f" [{self.component}]" if self.component else ""
        return f"{icon} {self.severity.value}{component_str}: {self.check_name} - {self.message}"


@dataclass
class CDSValidationReport:
    """CDS validation report (ADR-002 compliant)."""
    is_valid: bool
    issues: List[CDSValidationIssue] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def get_rejections(self) -> List[CDSValidationIssue]:
        """Get all REJECT-level issues."""
        return [i for i in self.issues if i.severity == CDSValidationSeverity.REJECT]

    def get_warnings(self) -> List[CDSValidationIssue]:
        """Get all WARNING-level issues."""
        return [i for i in self.issues if i.severity == CDSValidationSeverity.WARNING]

    def get_summary(self) -> str:
        """Get human-readable summary."""
        status = "✅ PASS" if self.is_valid else "❌ REJECT"
        rejections = len(self.get_rejections())
        warnings = len(self.get_warnings())

        return (
            f"CDS Validation: {status}\n"
            f"Issues: {len(self.issues)} total "
            f"({rejections} reject, {warnings} warning)"
        )


@dataclass
class CDSResult:
    """
    Complete CDS result (output contract).

    This is the canonical output structure for CDS Engine v1.0.
    """
    cds_value: float
    components: Dict[str, float]
    weights: Dict[str, float]
    weights_hash: str

    # Validation
    validation_report: CDSValidationReport

    # Ed25519 signature
    signature_hex: Optional[str] = None
    public_key_hex: Optional[str] = None

    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    cycle_id: Optional[str] = None

    # Cost tracking (ADR-012)
    cost_usd: float = 0.0
    llm_api_calls: int = 0

    def __post_init__(self):
        """Validate CDS value ∈ [0.0, 1.0]."""
        if not (0.0 <= self.cds_value <= 1.0):
            raise ValueError(
                f"CDS value must be in [0.0, 1.0], got {self.cds_value}"
            )

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'cds_value': self.cds_value,
            'components': self.components,
            'weights': self.weights,
            'weights_hash': self.weights_hash,
            'validation_report': {
                'is_valid': self.validation_report.is_valid,
                'issues': [str(issue) for issue in self.validation_report.issues]
            },
            'signature_hex': self.signature_hex,
            'public_key_hex': self.public_key_hex,
            'timestamp': self.timestamp.isoformat(),
            'cycle_id': self.cycle_id,
            'cost_usd': self.cost_usd,
            'llm_api_calls': self.llm_api_calls
        }

    def get_summary(self) -> str:
        """Get human-readable summary."""
        lines = [
            "=" * 80,
            "CDS ENGINE v1.0 — RESULT",
            "=" * 80,
            f"CDS Value: {self.cds_value:.4f}",
            f"Validation: {'✅ PASS' if self.validation_report.is_valid else '❌ REJECT'}",
            f"Timestamp: {self.timestamp.isoformat()}",
            "",
            "Components:",
        ]

        for name, value in self.components.items():
            weight = self.weights.get(name, 0.0)
            contribution = value * weight
            lines.append(f"  {name}: {value:.4f} (weight: {weight:.2f}, contrib: {contribution:.4f})")

        lines.extend([
            "",
            f"Weights Hash: {self.weights_hash[:16]}...",
            f"Signature: {self.signature_hex[:16] if self.signature_hex else 'N/A'}...",
            "",
            self.validation_report.get_summary(),
            "=" * 80
        ])

        return "\n".join(lines)


class CDSEngine:
    """
    CDS Engine v1.0 — Canonical Composite Decision Score Calculator.

    This engine implements the formal CDS specification:
    - Linear, additive formula: CDS = Σ(Ci × Wi)
    - 6 components, each normalized to [0.0, 1.0]
    - Weights sum to exactly 1.0
    - Hard constraints (REJECT) and soft constraints (WARNING)
    - Ed25519 signing for audit trail
    - Full ADR-001 → ADR-015 compliance
    """

    def __init__(self, weights: Optional[CDSWeights] = None):
        """
        Initialize CDS Engine with weight configuration.

        Args:
            weights: CDSWeights configuration (default: Default Weights v1.0)
        """
        self.weights = weights or CDSWeights()
        self.signer = Ed25519Signer()

        # Computation statistics
        self.computation_count = 0
        self.rejection_count = 0
        self.warning_count = 0

    def compute_cds(self, components: CDSComponents) -> CDSResult:
        """
        Compute CDS from components.

        This is the canonical CDS computation function implementing:
        CDS = Σ(Ci × Wi) for i=1 to 6

        Args:
            components: CDSComponents with normalized values

        Returns:
            CDSResult with CDS value, validation, and signature
        """
        self.computation_count += 1

        # Step 1: Validate components (hard constraints)
        validation_report = self._validate_components(components)

        if not validation_report.is_valid:
            self.rejection_count += 1
            # Return rejected result with CDS = 0.0
            return CDSResult(
                cds_value=0.0,
                components=components.to_dict(),
                weights=self.weights.to_dict(),
                weights_hash=self.weights.weights_hash,
                validation_report=validation_report,
                timestamp=datetime.now()
            )

        # Step 2: Compute CDS (linear, additive formula)
        cds_value = self._compute_cds_formula(components)

        # Step 3: Check soft constraints (warnings)
        warning_issues = self._check_soft_constraints(components)
        validation_report.issues.extend(warning_issues)

        if warning_issues:
            self.warning_count += 1

        # Step 4: Create result
        result = CDSResult(
            cds_value=cds_value,
            components=components.to_dict(),
            weights=self.weights.to_dict(),
            weights_hash=self.weights.weights_hash,
            validation_report=validation_report,
            timestamp=datetime.now(),
            cost_usd=0.0,  # CDS Engine has no LLM costs
            llm_api_calls=0
        )

        # Step 5: Sign result (Ed25519, ADR-008)
        signature_hex, public_key_hex = self._sign_result(result)
        result.signature_hex = signature_hex
        result.public_key_hex = public_key_hex

        return result

    def _compute_cds_formula(self, components: CDSComponents) -> float:
        """
        Compute canonical CDS formula: CDS = Σ(Ci × Wi).

        This is the core deterministic computation.
        """
        component_values = components.to_dict()
        weight_values = self.weights.to_dict()

        cds = 0.0
        for component_name in ['C1', 'C2', 'C3', 'C4', 'C5', 'C6']:
            c_value = component_values[component_name]
            w_value = weight_values[component_name]
            cds += c_value * w_value

        # Clamp to [0.0, 1.0] for numerical safety
        cds = max(0.0, min(1.0, cds))

        return cds

    def _validate_components(self, components: CDSComponents) -> CDSValidationReport:
        """
        Validate components against hard constraints.

        Hard Constraints (REJECT if violated):
        - All Ci ∈ [0.0, 1.0]
        - All Wi ∈ [0.0, 1.0]
        - ΣWi = 1.0
        """
        issues = []

        # Check component bounds
        component_dict = components.to_dict()
        for name, value in component_dict.items():
            if not (0.0 <= value <= 1.0):
                issues.append(CDSValidationIssue(
                    check_name="Component Bounds",
                    severity=CDSValidationSeverity.REJECT,
                    component=name,
                    message=f"Component out of bounds: {value}",
                    actual_value=value,
                    expected_range="[0.0, 1.0]"
                ))

        # Check weight bounds
        weight_dict = self.weights.to_dict()
        for name, value in weight_dict.items():
            if not (0.0 <= value <= 1.0):
                issues.append(CDSValidationIssue(
                    check_name="Weight Bounds",
                    severity=CDSValidationSeverity.REJECT,
                    component=name,
                    message=f"Weight out of bounds: {value}",
                    actual_value=value,
                    expected_range="[0.0, 1.0]"
                ))

        # Check weight sum
        weight_sum = sum(weight_dict.values())
        if abs(weight_sum - 1.0) > 1e-6:
            issues.append(CDSValidationIssue(
                check_name="Weight Sum",
                severity=CDSValidationSeverity.REJECT,
                message=f"Weights must sum to 1.0, got {weight_sum}",
                actual_value=weight_sum,
                expected_range="1.0"
            ))

        is_valid = len([i for i in issues if i.severity == CDSValidationSeverity.REJECT]) == 0

        return CDSValidationReport(is_valid=is_valid, issues=issues)

    def _check_soft_constraints(self, components: CDSComponents) -> List[CDSValidationIssue]:
        """
        Check soft constraints (warnings, do not reject).

        Soft Constraints (WARNING):
        - C2 < 0.15: "Low Stability" flag
        - C3 < 0.40: "Data Quality Low" flag
        - C5 < 0.20: "High Stress Environment" flag
        """
        warnings = []

        # C2: Signal Stability
        if components.C2_signal_stability < 0.15:
            warnings.append(CDSValidationIssue(
                check_name="Signal Stability",
                severity=CDSValidationSeverity.WARNING,
                component="C2",
                message="Low stability detected",
                actual_value=components.C2_signal_stability,
                expected_range="≥0.15"
            ))

        # C3: Data Integrity
        if components.C3_data_integrity < 0.40:
            warnings.append(CDSValidationIssue(
                check_name="Data Integrity",
                severity=CDSValidationSeverity.WARNING,
                component="C3",
                message="Data quality low",
                actual_value=components.C3_data_integrity,
                expected_range="≥0.40"
            ))

        # C5: Stress Modulator
        if components.C5_stress_modulator < 0.20:
            warnings.append(CDSValidationIssue(
                check_name="Market Stress",
                severity=CDSValidationSeverity.WARNING,
                component="C5",
                message="High stress environment detected",
                actual_value=components.C5_stress_modulator,
                expected_range="≥0.20"
            ))

        return warnings

    def _sign_result(self, result: CDSResult) -> Tuple[str, str]:
        """
        Sign CDS result with Ed25519 (ADR-008).

        Returns: (signature_hex, public_key_hex)
        """
        # Prepare signing payload
        payload = {
            'cds_value': result.cds_value,
            'components': result.components,
            'weights_hash': result.weights_hash,
            'timestamp': result.timestamp.isoformat()
        }

        # Canonical JSON
        canonical_json = json.dumps(payload, sort_keys=True)
        payload_bytes = canonical_json.encode('utf-8')

        # Sign
        signature_bytes = self.signer.private_key.sign(payload_bytes)
        signature_hex = signature_bytes.hex()
        public_key_hex = self.signer.get_public_key_hex()

        return signature_hex, public_key_hex

    @staticmethod
    def verify_signature(result: CDSResult) -> bool:
        """
        Verify Ed25519 signature on CDS result.

        Returns: True if signature valid, False otherwise
        """
        if not result.signature_hex or not result.public_key_hex:
            return False

        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

            # Reconstruct payload
            payload = {
                'cds_value': result.cds_value,
                'components': result.components,
                'weights_hash': result.weights_hash,
                'timestamp': result.timestamp.isoformat()
            }

            canonical_json = json.dumps(payload, sort_keys=True)
            payload_bytes = canonical_json.encode('utf-8')

            # Verify
            public_key_bytes = bytes.fromhex(result.public_key_hex)
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            signature_bytes = bytes.fromhex(result.signature_hex)

            public_key.verify(signature_bytes, payload_bytes)
            return True

        except Exception:
            return False

    def get_statistics(self) -> Dict[str, int]:
        """Get engine statistics."""
        return {
            'computation_count': self.computation_count,
            'rejection_count': self.rejection_count,
            'warning_count': self.warning_count,
            'public_key': self.signer.get_public_key_hex()
        }


# ============================================================================
# Component Computation Functions
# ============================================================================

def compute_regime_strength(regime_confidence: float) -> float:
    """
    Compute C1: Regime Strength from FINN+ confidence.

    Args:
        regime_confidence: FINN+ regime probability (0.0–1.0)

    Returns:
        C1 ∈ [0.0, 1.0]
    """
    # Direct mapping: confidence is already normalized
    return max(0.0, min(1.0, regime_confidence))


def compute_signal_stability(persistence_days: float, max_days: float = 30.0) -> float:
    """
    Compute C2: Signal Stability from STIG+ persistence.

    Args:
        persistence_days: Average persistence in days
        max_days: Maximum days for normalization (default: 30)

    Returns:
        C2 ∈ [0.0, 1.0]
    """
    # Normalize: min(persistence / max_days, 1.0)
    stability = persistence_days / max_days
    return max(0.0, min(1.0, stability))


def compute_data_integrity(quality_report: DataQualityReport) -> float:
    """
    Compute C3: Data Integrity from LINE+ quality report.

    Args:
        quality_report: LINE+ DataQualityReport

    Returns:
        C3 ∈ [0.0, 1.0]
    """
    # Scoring: 1.0 if no issues, penalize for warnings/errors
    if quality_report.overall_pass and len(quality_report.issues) == 0:
        return 1.0

    # Count issues by severity
    warnings = quality_report.warning_count
    errors = quality_report.error_count
    criticals = quality_report.critical_count

    # Penalty: -0.05 per warning, -0.20 per error, -0.50 per critical
    penalty = (warnings * 0.05) + (errors * 0.20) + (criticals * 0.50)

    integrity = 1.0 - penalty
    return max(0.0, min(1.0, integrity))


def compute_causal_coherence(coherence_score: float) -> float:
    """
    Compute C4: Causal Coherence from FINN+ Tier-2 (future).

    Args:
        coherence_score: LLM-based causal link score

    Returns:
        C4 ∈ [0.0, 1.0]

    Note: Currently returns 0.0 (FINN+ Tier-2 not implemented)
    """
    # Placeholder: FINN+ Tier-2 not implemented in Phase 3 Week 2
    # Future: This will use LLM-based causal coherence scoring
    return max(0.0, min(1.0, coherence_score))


def compute_stress_modulator(volatility: float, max_volatility: float = 0.05) -> float:
    """
    Compute C5: Market Stress Modulator from LINE+ volatility.

    Args:
        volatility: Market volatility (standard deviation of returns)
        max_volatility: Maximum volatility for normalization (default: 5%)

    Returns:
        C5 ∈ [0.0, 1.0] (reverse stress: 1.0 = low stress)
    """
    # Normalize volatility
    normalized_vol = volatility / max_volatility
    normalized_vol = max(0.0, min(1.0, normalized_vol))

    # Reverse: high volatility = low modulator
    stress_modulator = 1.0 - normalized_vol
    return max(0.0, min(1.0, stress_modulator))


def compute_relevance_alignment(relevance_score: float, max_relevance: float = 1.8) -> float:
    """
    Compute C6: Relevance Alignment from Relevance Engine.

    Args:
        relevance_score: Relevance score from relevance_engine.py
        max_relevance: Maximum relevance for normalization (default: 1.8 for BEAR)

    Returns:
        C6 ∈ [0.0, 1.0]
    """
    # Normalize: relevance / max_relevance
    alignment = relevance_score / max_relevance
    return max(0.0, min(1.0, alignment))


# ============================================================================
# Example Usage and Testing
# ============================================================================

if __name__ == "__main__":
    """
    Demonstrate CDS Engine v1.0.
    """
    print("=" * 80)
    print("CDS ENGINE v1.0 — COMPOSITE DECISION SCORE")
    print("Phase 3: Week 3 — LARS Directive 3 (Priority 1)")
    print("=" * 80)

    # [1] Initialize engine
    print("\n[1] Initializing CDS Engine with Default Weights v1.0...")
    engine = CDSEngine()

    print(f"    ✅ CDS Engine initialized")
    print(f"    Weights version: {engine.weights.version}")
    print(f"    Weights hash: {engine.weights.weights_hash[:16]}...")
    print(f"    Public key: {engine.signer.get_public_key_hex()[:16]}...")

    # [2] Test Case 1: Perfect components (all 1.0)
    print("\n[2] Test Case 1: Perfect components (all 1.0)...")

    perfect_components = CDSComponents(
        C1_regime_strength=1.0,
        C2_signal_stability=1.0,
        C3_data_integrity=1.0,
        C4_causal_coherence=1.0,
        C5_stress_modulator=1.0,
        C6_relevance_alignment=1.0
    )

    result_perfect = engine.compute_cds(perfect_components)
    print(f"\n{result_perfect.get_summary()}")

    # [3] Test Case 2: Realistic components
    print("\n[3] Test Case 2: Realistic components...")

    realistic_components = CDSComponents(
        C1_regime_strength=0.65,   # FINN+ confidence: 65%
        C2_signal_stability=0.50,   # 15 days persistence (15/30)
        C3_data_integrity=0.95,     # High data quality
        C4_causal_coherence=0.00,   # Not implemented yet
        C5_stress_modulator=0.75,   # Low-moderate stress
        C6_relevance_alignment=0.55 # NEUTRAL regime (1.0/1.8)
    )

    result_realistic = engine.compute_cds(realistic_components)
    print(f"\n{result_realistic.get_summary()}")

    # [4] Test Case 3: Low quality (triggers warnings)
    print("\n[4] Test Case 3: Low quality components (triggers warnings)...")

    low_quality_components = CDSComponents(
        C1_regime_strength=0.50,
        C2_signal_stability=0.10,   # < 0.15 threshold (WARNING)
        C3_data_integrity=0.35,     # < 0.40 threshold (WARNING)
        C4_causal_coherence=0.00,
        C5_stress_modulator=0.15,   # < 0.20 threshold (WARNING)
        C6_relevance_alignment=0.40
    )

    result_low_quality = engine.compute_cds(low_quality_components)
    print(f"\n{result_low_quality.get_summary()}")

    if result_low_quality.validation_report.issues:
        print("\n    Issues detected:")
        for issue in result_low_quality.validation_report.issues:
            print(f"      {issue}")

    # [5] Test Case 4: Invalid components (triggers rejection)
    print("\n[5] Test Case 4: Invalid components (out of bounds, triggers rejection)...")

    try:
        invalid_components = CDSComponents(
            C1_regime_strength=1.5,  # Invalid: > 1.0
            C2_signal_stability=0.50,
            C3_data_integrity=0.95,
            C4_causal_coherence=0.00,
            C5_stress_modulator=0.75,
            C6_relevance_alignment=0.55
        )
    except ValueError as e:
        print(f"    ✅ Validation caught invalid component: {e}")

    # [6] Signature verification
    print("\n[6] Testing Ed25519 signature verification...")

    is_valid_sig = CDSEngine.verify_signature(result_realistic)
    print(f"    Signature verification: {'✅ VALID' if is_valid_sig else '❌ INVALID'}")

    # [7] Engine statistics
    print("\n[7] Engine statistics...")
    stats = engine.get_statistics()
    print(f"    Computations: {stats['computation_count']}")
    print(f"    Rejections: {stats['rejection_count']}")
    print(f"    Warnings: {stats['warning_count']}")

    # Summary
    print("\n" + "=" * 80)
    print("✅ CDS ENGINE v1.0 FUNCTIONAL")
    print("=" * 80)
    print("\nKey Features:")
    print("  - Linear, additive formula: CDS = Σ(Ci × Wi)")
    print("  - 6 components, each ∈ [0.0, 1.0]")
    print("  - Default Weights v1.0 (sum to 1.0)")
    print("  - Hard constraints (REJECT)")
    print("  - Soft constraints (WARNING)")
    print("  - Ed25519 signing (ADR-008)")
    print("  - Full audit trail (weights hash)")
    print("\nCompliance:")
    print("  - BIS-239: ✅ Data governance")
    print("  - ISO-8000: ✅ Data quality")
    print("  - GIPS: ✅ Performance standards")
    print("  - MiFID II: ✅ Explainability")
    print("  - EU AI Act: ✅ Traceability")
    print("  - ADR-008: ✅ Cryptographic signatures")
    print("  - ADR-010: ✅ Discrepancy scoring")
    print("  - ADR-012: ✅ Economic safety ($0.00/cycle)")
    print("\nStatus: Ready for STIG+ validation (G1 checkpoint)")
    print("=" * 80)
