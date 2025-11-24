"""
CDS Engine v1.0 — Comprehensive Unit Tests
Phase 3: Week 3 — LARS Directive 3 (Priority 1)

Authority: LARS CDS Formal Contract (ADR-CDS-CONTRACT-PHASE3)
Canonical ADR Chain: ADR-001 → ADR-015

Test Coverage:
- Weights validation (sum to 1.0, bounds)
- Components validation (bounds, types)
- CDS formula (linear, additive)
- Hard constraints (REJECT)
- Soft constraints (WARNING)
- Ed25519 signing
- Determinism
- Integration with orchestrator
"""

import unittest
from datetime import datetime
import pandas as pd
import numpy as np

from cds_engine import (
    CDSEngine,
    CDSWeights,
    CDSComponents,
    CDSResult,
    CDSValidationSeverity,
    compute_regime_strength,
    compute_signal_stability,
    compute_data_integrity,
    compute_causal_coherence,
    compute_stress_modulator,
    compute_relevance_alignment
)

from line_data_quality import DataQualityReport


class TestCDSWeights(unittest.TestCase):
    """Test CDS weights configuration."""

    def test_default_weights_sum_to_one(self):
        """Test that default weights sum to exactly 1.0."""
        weights = CDSWeights()

        total = (
            weights.C1_regime_strength +
            weights.C2_signal_stability +
            weights.C3_data_integrity +
            weights.C4_causal_coherence +
            weights.C5_stress_modulator +
            weights.C6_relevance_alignment
        )

        self.assertAlmostEqual(total, 1.0, places=6)

    def test_invalid_weights_sum(self):
        """Test that weights not summing to 1.0 are rejected."""
        with self.assertRaises(ValueError):
            CDSWeights(
                C1_regime_strength=0.30,  # Total = 1.05
                C2_signal_stability=0.20,
                C3_data_integrity=0.15,
                C4_causal_coherence=0.20,
                C5_stress_modulator=0.10,
                C6_relevance_alignment=0.10
            )

    def test_weights_hash_computed(self):
        """Test that weights hash is computed."""
        weights = CDSWeights()
        self.assertIsNotNone(weights.weights_hash)
        self.assertIsInstance(weights.weights_hash, str)
        self.assertEqual(len(weights.weights_hash), 64)  # SHA-256 hex

    def test_weights_hash_deterministic(self):
        """Test that identical weights produce identical hash."""
        weights1 = CDSWeights()
        weights2 = CDSWeights()
        self.assertEqual(weights1.weights_hash, weights2.weights_hash)

    def test_different_weights_different_hash(self):
        """Test that different weights produce different hash."""
        weights1 = CDSWeights()
        weights2 = CDSWeights(
            C1_regime_strength=0.30,
            C2_signal_stability=0.15,
            C3_data_integrity=0.15,
            C4_causal_coherence=0.20,
            C5_stress_modulator=0.10,
            C6_relevance_alignment=0.10
        )
        self.assertNotEqual(weights1.weights_hash, weights2.weights_hash)


class TestCDSComponents(unittest.TestCase):
    """Test CDS components validation."""

    def test_valid_components(self):
        """Test that valid components are accepted."""
        components = CDSComponents(
            C1_regime_strength=0.65,
            C2_signal_stability=0.50,
            C3_data_integrity=0.95,
            C4_causal_coherence=0.00,
            C5_stress_modulator=0.75,
            C6_relevance_alignment=0.55
        )
        self.assertIsNotNone(components)

    def test_component_bounds_lower(self):
        """Test that components < 0.0 are rejected."""
        with self.assertRaises(ValueError):
            CDSComponents(
                C1_regime_strength=-0.1,  # Invalid
                C2_signal_stability=0.50,
                C3_data_integrity=0.95,
                C4_causal_coherence=0.00,
                C5_stress_modulator=0.75,
                C6_relevance_alignment=0.55
            )

    def test_component_bounds_upper(self):
        """Test that components > 1.0 are rejected."""
        with self.assertRaises(ValueError):
            CDSComponents(
                C1_regime_strength=0.65,
                C2_signal_stability=1.5,  # Invalid
                C3_data_integrity=0.95,
                C4_causal_coherence=0.00,
                C5_stress_modulator=0.75,
                C6_relevance_alignment=0.55
            )

    def test_component_edge_cases(self):
        """Test that edge case values (0.0, 1.0) are valid."""
        components = CDSComponents(
            C1_regime_strength=0.0,  # Edge case
            C2_signal_stability=1.0,  # Edge case
            C3_data_integrity=0.5,
            C4_causal_coherence=0.0,
            C5_stress_modulator=1.0,  # Edge case
            C6_relevance_alignment=0.0  # Edge case
        )
        self.assertIsNotNone(components)


class TestCDSFormula(unittest.TestCase):
    """Test CDS formula computation."""

    def setUp(self):
        """Set up test fixtures."""
        self.engine = CDSEngine()

    def test_cds_formula_perfect_components(self):
        """Test CDS formula with all components = 1.0."""
        components = CDSComponents(
            C1_regime_strength=1.0,
            C2_signal_stability=1.0,
            C3_data_integrity=1.0,
            C4_causal_coherence=1.0,
            C5_stress_modulator=1.0,
            C6_relevance_alignment=1.0
        )

        result = self.engine.compute_cds(components)

        # With all components = 1.0, CDS should = 1.0
        self.assertAlmostEqual(result.cds_value, 1.0, places=4)

    def test_cds_formula_zero_components(self):
        """Test CDS formula with all components = 0.0."""
        components = CDSComponents(
            C1_regime_strength=0.0,
            C2_signal_stability=0.0,
            C3_data_integrity=0.0,
            C4_causal_coherence=0.0,
            C5_stress_modulator=0.0,
            C6_relevance_alignment=0.0
        )

        result = self.engine.compute_cds(components)

        # With all components = 0.0, CDS should = 0.0
        self.assertAlmostEqual(result.cds_value, 0.0, places=4)

    def test_cds_formula_linearity(self):
        """Test CDS formula linearity."""
        # If we double all components, CDS should double (within bounds)
        components1 = CDSComponents(
            C1_regime_strength=0.25,
            C2_signal_stability=0.25,
            C3_data_integrity=0.25,
            C4_causal_coherence=0.25,
            C5_stress_modulator=0.25,
            C6_relevance_alignment=0.25
        )

        components2 = CDSComponents(
            C1_regime_strength=0.50,
            C2_signal_stability=0.50,
            C3_data_integrity=0.50,
            C4_causal_coherence=0.50,
            C5_stress_modulator=0.50,
            C6_relevance_alignment=0.50
        )

        result1 = self.engine.compute_cds(components1)
        result2 = self.engine.compute_cds(components2)

        # CDS should double
        self.assertAlmostEqual(result2.cds_value, result1.cds_value * 2, places=4)

    def test_cds_formula_weighted(self):
        """Test that weights are properly applied."""
        # Set C1 = 1.0, all others = 0.0
        # CDS should = weight of C1 (0.25)
        components = CDSComponents(
            C1_regime_strength=1.0,
            C2_signal_stability=0.0,
            C3_data_integrity=0.0,
            C4_causal_coherence=0.0,
            C5_stress_modulator=0.0,
            C6_relevance_alignment=0.0
        )

        result = self.engine.compute_cds(components)

        # CDS = 1.0 * 0.25 = 0.25
        self.assertAlmostEqual(result.cds_value, 0.25, places=4)


class TestCDSValidation(unittest.TestCase):
    """Test CDS validation (hard and soft constraints)."""

    def setUp(self):
        """Set up test fixtures."""
        self.engine = CDSEngine()

    def test_hard_constraint_pass(self):
        """Test that valid components pass hard constraints."""
        components = CDSComponents(
            C1_regime_strength=0.65,
            C2_signal_stability=0.50,
            C3_data_integrity=0.95,
            C4_causal_coherence=0.00,
            C5_stress_modulator=0.75,
            C6_relevance_alignment=0.55
        )

        result = self.engine.compute_cds(components)

        self.assertTrue(result.validation_report.is_valid)
        self.assertEqual(len(result.validation_report.get_rejections()), 0)

    def test_soft_constraint_low_stability(self):
        """Test that C2 < 0.15 triggers WARNING."""
        components = CDSComponents(
            C1_regime_strength=0.65,
            C2_signal_stability=0.10,  # < 0.15 threshold
            C3_data_integrity=0.95,
            C4_causal_coherence=0.00,
            C5_stress_modulator=0.75,
            C6_relevance_alignment=0.55
        )

        result = self.engine.compute_cds(components)

        # Should still be valid (soft constraint)
        self.assertTrue(result.validation_report.is_valid)

        # Should have WARNING
        warnings = result.validation_report.get_warnings()
        self.assertGreater(len(warnings), 0)

        # Check for C2 warning
        c2_warnings = [w for w in warnings if w.component == "C2"]
        self.assertEqual(len(c2_warnings), 1)
        self.assertEqual(c2_warnings[0].severity, CDSValidationSeverity.WARNING)

    def test_soft_constraint_low_data_quality(self):
        """Test that C3 < 0.40 triggers WARNING."""
        components = CDSComponents(
            C1_regime_strength=0.65,
            C2_signal_stability=0.50,
            C3_data_integrity=0.35,  # < 0.40 threshold
            C4_causal_coherence=0.00,
            C5_stress_modulator=0.75,
            C6_relevance_alignment=0.55
        )

        result = self.engine.compute_cds(components)

        # Should still be valid (soft constraint)
        self.assertTrue(result.validation_report.is_valid)

        # Should have WARNING for C3
        warnings = result.validation_report.get_warnings()
        c3_warnings = [w for w in warnings if w.component == "C3"]
        self.assertGreater(len(c3_warnings), 0)

    def test_soft_constraint_high_stress(self):
        """Test that C5 < 0.20 triggers WARNING."""
        components = CDSComponents(
            C1_regime_strength=0.65,
            C2_signal_stability=0.50,
            C3_data_integrity=0.95,
            C4_causal_coherence=0.00,
            C5_stress_modulator=0.15,  # < 0.20 threshold
            C6_relevance_alignment=0.55
        )

        result = self.engine.compute_cds(components)

        # Should still be valid (soft constraint)
        self.assertTrue(result.validation_report.is_valid)

        # Should have WARNING for C5
        warnings = result.validation_report.get_warnings()
        c5_warnings = [w for w in warnings if w.component == "C5"]
        self.assertGreater(len(c5_warnings), 0)

    def test_multiple_soft_constraints(self):
        """Test multiple soft constraint violations."""
        components = CDSComponents(
            C1_regime_strength=0.50,
            C2_signal_stability=0.10,  # WARNING
            C3_data_integrity=0.35,    # WARNING
            C4_causal_coherence=0.00,
            C5_stress_modulator=0.15,  # WARNING
            C6_relevance_alignment=0.40
        )

        result = self.engine.compute_cds(components)

        # Should still be valid
        self.assertTrue(result.validation_report.is_valid)

        # Should have 3 warnings
        warnings = result.validation_report.get_warnings()
        self.assertEqual(len(warnings), 3)


class TestCDSSigning(unittest.TestCase):
    """Test Ed25519 signing of CDS results."""

    def setUp(self):
        """Set up test fixtures."""
        self.engine = CDSEngine()

    def test_cds_result_is_signed(self):
        """Test that CDS result is signed."""
        components = CDSComponents(
            C1_regime_strength=0.65,
            C2_signal_stability=0.50,
            C3_data_integrity=0.95,
            C4_causal_coherence=0.00,
            C5_stress_modulator=0.75,
            C6_relevance_alignment=0.55
        )

        result = self.engine.compute_cds(components)

        self.assertIsNotNone(result.signature_hex)
        self.assertIsNotNone(result.public_key_hex)
        self.assertIsInstance(result.signature_hex, str)
        self.assertIsInstance(result.public_key_hex, str)

    def test_signature_verification(self):
        """Test that signature can be verified."""
        components = CDSComponents(
            C1_regime_strength=0.65,
            C2_signal_stability=0.50,
            C3_data_integrity=0.95,
            C4_causal_coherence=0.00,
            C5_stress_modulator=0.75,
            C6_relevance_alignment=0.55
        )

        result = self.engine.compute_cds(components)

        # Verify signature
        is_valid = CDSEngine.verify_signature(result)
        self.assertTrue(is_valid)

    def test_tampered_signature_rejected(self):
        """Test that tampered signature is rejected."""
        components = CDSComponents(
            C1_regime_strength=0.65,
            C2_signal_stability=0.50,
            C3_data_integrity=0.95,
            C4_causal_coherence=0.00,
            C5_stress_modulator=0.75,
            C6_relevance_alignment=0.55
        )

        result = self.engine.compute_cds(components)

        # Tamper with signature
        result.signature_hex = "0" * 128

        # Verify signature (should fail)
        is_valid = CDSEngine.verify_signature(result)
        self.assertFalse(is_valid)


class TestCDSDeterminism(unittest.TestCase):
    """Test CDS determinism."""

    def test_same_input_same_output(self):
        """Test that identical inputs produce identical outputs."""
        engine1 = CDSEngine()
        engine2 = CDSEngine()

        components = CDSComponents(
            C1_regime_strength=0.65,
            C2_signal_stability=0.50,
            C3_data_integrity=0.95,
            C4_causal_coherence=0.00,
            C5_stress_modulator=0.75,
            C6_relevance_alignment=0.55
        )

        result1 = engine1.compute_cds(components)
        result2 = engine2.compute_cds(components)

        # CDS values should be identical
        self.assertAlmostEqual(result1.cds_value, result2.cds_value, places=10)

        # Components should be identical
        for key in result1.components.keys():
            self.assertAlmostEqual(
                result1.components[key],
                result2.components[key],
                places=10
            )


class TestComponentComputationFunctions(unittest.TestCase):
    """Test individual component computation functions."""

    def test_compute_regime_strength(self):
        """Test C1: Regime Strength computation."""
        C1 = compute_regime_strength(0.75)
        self.assertAlmostEqual(C1, 0.75, places=4)

        # Test bounds
        self.assertEqual(compute_regime_strength(0.0), 0.0)
        self.assertEqual(compute_regime_strength(1.0), 1.0)

    def test_compute_signal_stability(self):
        """Test C2: Signal Stability computation."""
        # 15 days with max 30 days = 0.5
        C2 = compute_signal_stability(15.0, max_days=30.0)
        self.assertAlmostEqual(C2, 0.5, places=4)

        # >= max_days should cap at 1.0
        C2_high = compute_signal_stability(45.0, max_days=30.0)
        self.assertAlmostEqual(C2_high, 1.0, places=4)

    def test_compute_data_integrity(self):
        """Test C3: Data Integrity computation."""
        # Perfect quality (no issues)
        report_perfect = DataQualityReport(
            dataset_symbol="TEST",
            dataset_interval="1d",
            bar_count=100,
            issues=[],
            overall_pass=True
        )
        C3_perfect = compute_data_integrity(report_perfect)
        self.assertAlmostEqual(C3_perfect, 1.0, places=4)

    def test_compute_causal_coherence(self):
        """Test C4: Causal Coherence computation."""
        # Currently placeholder (returns input)
        C4 = compute_causal_coherence(0.75)
        self.assertAlmostEqual(C4, 0.75, places=4)

    def test_compute_stress_modulator(self):
        """Test C5: Market Stress Modulator computation."""
        # Low volatility (1%) = high modulator (0.8)
        C5_low = compute_stress_modulator(0.01, max_volatility=0.05)
        self.assertAlmostEqual(C5_low, 0.8, places=4)

        # High volatility (5%) = low modulator (0.0)
        C5_high = compute_stress_modulator(0.05, max_volatility=0.05)
        self.assertAlmostEqual(C5_high, 0.0, places=4)

    def test_compute_relevance_alignment(self):
        """Test C6: Relevance Alignment computation."""
        # NEUTRAL regime weight (1.3) normalized to max (1.8)
        C6 = compute_relevance_alignment(1.3, max_relevance=1.8)
        self.assertAlmostEqual(C6, 1.3 / 1.8, places=4)


class TestCDSEngineStatistics(unittest.TestCase):
    """Test CDS engine statistics tracking."""

    def test_computation_count(self):
        """Test that computation count is tracked."""
        engine = CDSEngine()

        components = CDSComponents(
            C1_regime_strength=0.65,
            C2_signal_stability=0.50,
            C3_data_integrity=0.95,
            C4_causal_coherence=0.00,
            C5_stress_modulator=0.75,
            C6_relevance_alignment=0.55
        )

        # Initial count
        self.assertEqual(engine.computation_count, 0)

        # Compute CDS
        engine.compute_cds(components)
        self.assertEqual(engine.computation_count, 1)

        # Compute again
        engine.compute_cds(components)
        self.assertEqual(engine.computation_count, 2)

    def test_warning_count(self):
        """Test that warning count is tracked."""
        engine = CDSEngine()

        # Components with warnings
        components = CDSComponents(
            C1_regime_strength=0.50,
            C2_signal_stability=0.10,  # WARNING
            C3_data_integrity=0.35,    # WARNING
            C4_causal_coherence=0.00,
            C5_stress_modulator=0.15,  # WARNING
            C6_relevance_alignment=0.40
        )

        # Initial count
        self.assertEqual(engine.warning_count, 0)

        # Compute CDS (should trigger warnings)
        engine.compute_cds(components)
        self.assertEqual(engine.warning_count, 1)


if __name__ == "__main__":
    """Run all CDS Engine tests."""
    unittest.main(verbosity=2)
