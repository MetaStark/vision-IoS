"""
Unit Tests for FINN+ Tier-2 Engine (Causal Coherence)
Phase 3: Week 3 — LARS Directive 6 (Priority 1)

Authority: LARS G2 Approval + Directive 6
Test Coverage: Prompt engineering, LLM mocking, rate limiting, cost tracking

Purpose: Validate FINN+ Tier-2 engine functionality before G1 STIG+ validation
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import time

from finn_tier2_engine import (
    FINNTier2Engine,
    Tier2Input,
    Tier2Result,
    MockLLMClient,
    LLMClient,
    construct_prompt,
    parse_llm_response,
    COHERENCE_PROMPT_TEMPLATE
)


class TestPromptEngineering(unittest.TestCase):
    """Test prompt construction and formatting."""

    def test_construct_prompt_bull_regime(self):
        """Test prompt construction for BULL regime."""
        tier2_input = Tier2Input(
            regime_label="BULL",
            regime_confidence=0.75,
            return_z=1.2,
            volatility_z=0.6,
            drawdown_z=-0.3,
            macd_diff_z=0.8,
            price_change_pct=15.0,
            current_drawdown_pct=-2.0
        )

        prompt = construct_prompt(tier2_input)

        # Verify key elements present
        self.assertIn("BULL", prompt)
        self.assertIn("75.0%", prompt)
        self.assertIn("1.20σ", prompt)
        self.assertIn("+15.0%", prompt)

    def test_construct_prompt_bear_regime(self):
        """Test prompt construction for BEAR regime."""
        tier2_input = Tier2Input(
            regime_label="BEAR",
            regime_confidence=0.65,
            return_z=-1.5,
            volatility_z=1.2,
            drawdown_z=-2.0,
            macd_diff_z=-0.9,
            price_change_pct=-12.0,
            current_drawdown_pct=-15.0
        )

        prompt = construct_prompt(tier2_input)

        # Verify key elements present
        self.assertIn("BEAR", prompt)
        self.assertIn("65.0%", prompt)
        self.assertIn("-1.50σ", prompt)
        self.assertIn("-12.0%", prompt)


class TestResponseParsing(unittest.TestCase):
    """Test LLM response parsing."""

    def test_parse_valid_response(self):
        """Test parsing valid LLM response."""
        response = """
Coherence: 0.85
Justification: The BULL classification is well-supported by positive return z-score (+1.2σ) and minimal drawdown (-2%). Low volatility (0.6σ) confirms stable upward momentum.
"""
        coherence, justification = parse_llm_response(response)

        self.assertAlmostEqual(coherence, 0.85, places=2)
        self.assertIn("BULL classification", justification)
        self.assertLessEqual(len(justification), 300)

    def test_parse_response_with_extra_text(self):
        """Test parsing response with extra text."""
        response = """
Some preamble text here.

Coherence: 0.65
Justification: Mixed signals from the market. Return z-score suggests moderate bullish momentum. However, elevated volatility creates uncertainty.

Some additional commentary.
"""
        coherence, justification = parse_llm_response(response)

        self.assertAlmostEqual(coherence, 0.65, places=2)
        self.assertIn("Mixed signals", justification)

    def test_parse_response_truncates_long_justification(self):
        """Test that long justifications are truncated to 300 chars."""
        long_justification = "This is a very long justification. " * 20  # > 300 chars
        response = f"Coherence: 0.75\nJustification: {long_justification}"

        coherence, justification = parse_llm_response(response)

        self.assertAlmostEqual(coherence, 0.75, places=2)
        self.assertLessEqual(len(justification), 300)
        self.assertTrue(justification.endswith("..."))

    def test_parse_response_missing_coherence_raises_error(self):
        """Test that missing coherence score raises ValueError."""
        response = "Justification: Some text but no coherence score."

        with self.assertRaises(ValueError) as context:
            parse_llm_response(response)

        self.assertIn("coherence score", str(context.exception).lower())

    def test_parse_response_missing_justification_raises_error(self):
        """Test that missing justification raises ValueError."""
        response = "Coherence: 0.85"

        with self.assertRaises(ValueError) as context:
            parse_llm_response(response)

        self.assertIn("justification", str(context.exception).lower())

    def test_parse_response_out_of_bounds_raises_error(self):
        """Test that out-of-bounds coherence raises ValueError."""
        response = "Coherence: 1.5\nJustification: Invalid score."

        with self.assertRaises(ValueError) as context:
            parse_llm_response(response)

        self.assertIn("out of bounds", str(context.exception).lower())


class TestMockLLMClient(unittest.TestCase):
    """Test MockLLMClient functionality."""

    def test_mock_client_generates_valid_response(self):
        """Test that MockLLMClient generates valid responses."""
        client = MockLLMClient()

        prompt = construct_prompt(Tier2Input(
            regime_label="BULL",
            regime_confidence=0.75,
            return_z=1.2,
            volatility_z=0.6,
            drawdown_z=-0.3,
            macd_diff_z=0.8,
            price_change_pct=15.0,
            current_drawdown_pct=-2.0
        ))

        response = client.generate(prompt)

        # Verify response structure
        self.assertIn('response_text', response)
        self.assertIn('cost_usd', response)
        self.assertIn('tokens_input', response)
        self.assertIn('tokens_output', response)
        self.assertIn('model', response)

        # Verify cost
        self.assertAlmostEqual(response['cost_usd'], 0.0024, places=4)

        # Verify response can be parsed
        coherence, justification = parse_llm_response(response['response_text'])
        self.assertGreaterEqual(coherence, 0.0)
        self.assertLessEqual(coherence, 1.0)

    def test_mock_client_bull_regime_high_coherence(self):
        """Test that MockLLMClient gives high coherence for aligned BULL regime."""
        client = MockLLMClient()

        prompt = construct_prompt(Tier2Input(
            regime_label="BULL",
            regime_confidence=0.80,
            return_z=1.5,  # Strong positive return
            volatility_z=0.4,  # Low volatility
            drawdown_z=-0.2,
            macd_diff_z=1.0,
            price_change_pct=20.0,
            current_drawdown_pct=-1.0
        ))

        response = client.generate(prompt)
        coherence, _ = parse_llm_response(response['response_text'])

        # Expect high coherence for well-aligned BULL
        self.assertGreaterEqual(coherence, 0.7)

    def test_mock_client_bear_contradictory_low_coherence(self):
        """Test that MockLLMClient gives low coherence for contradictory BEAR regime."""
        client = MockLLMClient()

        prompt = construct_prompt(Tier2Input(
            regime_label="BEAR",
            regime_confidence=0.60,
            return_z=1.2,  # Positive return (contradicts BEAR)
            volatility_z=0.5,
            drawdown_z=-0.1,
            macd_diff_z=0.8,
            price_change_pct=10.0,
            current_drawdown_pct=-1.0
        ))

        response = client.generate(prompt)
        coherence, _ = parse_llm_response(response['response_text'])

        # Expect low coherence for contradictory BEAR
        self.assertLess(coherence, 0.6)

    def test_mock_client_tracks_statistics(self):
        """Test that MockLLMClient tracks statistics correctly."""
        client = MockLLMClient()

        # Generate 3 requests
        for i in range(3):
            client.generate("test prompt")

        stats = client.get_statistics()

        self.assertEqual(stats['request_count'], 3)
        self.assertAlmostEqual(stats['total_cost'], 0.0024 * 3, places=5)


class TestFINNTier2Engine(unittest.TestCase):
    """Test FINN+ Tier-2 Engine core functionality."""

    def test_engine_initialization(self):
        """Test engine initialization."""
        engine = FINNTier2Engine(use_production_mode=False)

        self.assertIsNotNone(engine.llm_client)
        self.assertIsNotNone(engine.signer)
        self.assertEqual(engine.computation_count, 0)
        self.assertEqual(engine.max_calls_per_hour, 100)
        self.assertEqual(engine.daily_budget_usd, 500.0)

    def test_placeholder_mode_returns_zero(self):
        """Test that placeholder mode returns 0.0 coherence."""
        engine = FINNTier2Engine(use_production_mode=False)

        tier2_input = Tier2Input(
            regime_label="BULL",
            regime_confidence=0.75,
            return_z=1.2,
            volatility_z=0.6,
            drawdown_z=-0.3,
            macd_diff_z=0.8,
            price_change_pct=15.0,
            current_drawdown_pct=-2.0
        )

        result = engine.compute_coherence(tier2_input)

        self.assertEqual(result.coherence_score, 0.0)
        self.assertIn("PLACEHOLDER", result.summary)
        self.assertEqual(result.llm_cost_usd, 0.0)
        self.assertEqual(result.llm_api_calls, 0)

    def test_production_mode_computes_coherence(self):
        """Test that production mode computes actual coherence."""
        engine = FINNTier2Engine(use_production_mode=True)  # Uses MockLLMClient

        tier2_input = Tier2Input(
            regime_label="BULL",
            regime_confidence=0.75,
            return_z=1.2,
            volatility_z=0.6,
            drawdown_z=-0.3,
            macd_diff_z=0.8,
            price_change_pct=15.0,
            current_drawdown_pct=-2.0
        )

        result = engine.compute_coherence(tier2_input)

        self.assertGreaterEqual(result.coherence_score, 0.0)
        self.assertLessEqual(result.coherence_score, 1.0)
        self.assertGreater(len(result.summary), 0)
        self.assertGreater(result.llm_cost_usd, 0.0)
        self.assertEqual(result.llm_api_calls, 1)

    def test_result_has_signature(self):
        """Test that Tier-2 result includes Ed25519 signature."""
        engine = FINNTier2Engine(use_production_mode=True)

        tier2_input = Tier2Input(
            regime_label="BULL",
            regime_confidence=0.75,
            return_z=1.2,
            volatility_z=0.6,
            drawdown_z=-0.3,
            macd_diff_z=0.8,
            price_change_pct=15.0,
            current_drawdown_pct=-2.0
        )

        result = engine.compute_coherence(tier2_input)

        self.assertIsNotNone(result.signature_hex)
        self.assertIsNotNone(result.public_key_hex)
        self.assertGreater(len(result.signature_hex), 0)

    def test_caching_reduces_llm_calls(self):
        """Test that caching reduces redundant LLM calls."""
        engine = FINNTier2Engine(use_production_mode=True)

        tier2_input = Tier2Input(
            regime_label="BULL",
            regime_confidence=0.75,
            return_z=1.2,
            volatility_z=0.6,
            drawdown_z=-0.3,
            macd_diff_z=0.8,
            price_change_pct=15.0,
            current_drawdown_pct=-2.0
        )

        # First call
        result1 = engine.compute_coherence(tier2_input)

        # Second call (should hit cache)
        result2 = engine.compute_coherence(tier2_input)

        # Verify cache hit
        self.assertEqual(engine.cache_hits, 1)
        self.assertEqual(result1.coherence_score, result2.coherence_score)

    def test_rate_limiting_enforced(self):
        """Test that rate limiting is enforced."""
        engine = FINNTier2Engine(use_production_mode=True)
        engine.max_calls_per_hour = 3  # Lower limit for testing

        tier2_input = Tier2Input(
            regime_label="BULL",
            regime_confidence=0.75,
            return_z=1.2,
            volatility_z=0.6,
            drawdown_z=-0.3,
            macd_diff_z=0.8,
            price_change_pct=15.0,
            current_drawdown_pct=-2.0
        )

        # Make calls up to rate limit
        for i in range(3):
            # Vary input to avoid cache
            tier2_input.return_z = 1.0 + (i * 0.1)
            result = engine.compute_coherence(tier2_input)
            self.assertGreater(result.coherence_score, -1)  # Valid result

        # Next call should be rate limited
        tier2_input.return_z = 2.0
        result = engine.compute_coherence(tier2_input)

        self.assertEqual(result.coherence_score, 0.0)
        self.assertIn("RATE LIMIT", result.summary)

    def test_cost_tracking(self):
        """Test that costs are tracked correctly."""
        engine = FINNTier2Engine(use_production_mode=True)

        tier2_input = Tier2Input(
            regime_label="BULL",
            regime_confidence=0.75,
            return_z=1.2,
            volatility_z=0.6,
            drawdown_z=-0.3,
            macd_diff_z=0.8,
            price_change_pct=15.0,
            current_drawdown_pct=-2.0
        )

        # Make 2 calls
        for i in range(2):
            tier2_input.return_z = 1.0 + (i * 0.5)  # Vary to avoid cache
            engine.compute_coherence(tier2_input)

        stats = engine.get_statistics()

        self.assertEqual(stats['computation_count'], 2)
        self.assertGreater(stats['daily_cost_usd'], 0.0)
        self.assertAlmostEqual(stats['daily_cost_usd'], 0.0024 * 2, places=5)

    def test_computation_count_increments(self):
        """Test that computation count increments correctly."""
        engine = FINNTier2Engine(use_production_mode=True)

        tier2_input = Tier2Input(
            regime_label="BULL",
            regime_confidence=0.75,
            return_z=1.2,
            volatility_z=0.6,
            drawdown_z=-0.3,
            macd_diff_z=0.8,
            price_change_pct=15.0,
            current_drawdown_pct=-2.0
        )

        # Make 3 calls
        for i in range(3):
            engine.compute_coherence(tier2_input)

        self.assertEqual(engine.computation_count, 3)


class TestTier2InputValidation(unittest.TestCase):
    """Test Tier2Input validation."""

    def test_valid_tier2_input(self):
        """Test that valid Tier2Input is accepted."""
        tier2_input = Tier2Input(
            regime_label="BULL",
            regime_confidence=0.75,
            return_z=1.2,
            volatility_z=0.6,
            drawdown_z=-0.3,
            macd_diff_z=0.8,
            price_change_pct=15.0,
            current_drawdown_pct=-2.0
        )

        self.assertEqual(tier2_input.regime_label, "BULL")
        self.assertAlmostEqual(tier2_input.regime_confidence, 0.75)


class TestTier2ResultValidation(unittest.TestCase):
    """Test Tier2Result validation."""

    def test_valid_tier2_result(self):
        """Test that valid Tier2Result is accepted."""
        result = Tier2Result(
            coherence_score=0.85,
            summary="Test summary",
            llm_cost_usd=0.0024,
            llm_api_calls=1
        )

        self.assertAlmostEqual(result.coherence_score, 0.85)

    def test_out_of_bounds_coherence_raises_error(self):
        """Test that out-of-bounds coherence raises ValueError."""
        with self.assertRaises(ValueError) as context:
            Tier2Result(
                coherence_score=1.5,
                summary="Invalid",
                llm_cost_usd=0.0,
                llm_api_calls=0
            )

        self.assertIn("0.0", str(context.exception))
        self.assertIn("1.0", str(context.exception))

    def test_negative_coherence_raises_error(self):
        """Test that negative coherence raises ValueError."""
        with self.assertRaises(ValueError) as context:
            Tier2Result(
                coherence_score=-0.1,
                summary="Invalid",
                llm_cost_usd=0.0,
                llm_api_calls=0
            )

        self.assertIn("0.0", str(context.exception))

    def test_result_to_dict(self):
        """Test Tier2Result serialization to dict."""
        result = Tier2Result(
            coherence_score=0.85,
            summary="Test summary",
            llm_cost_usd=0.0024,
            llm_api_calls=1,
            llm_model="test-model"
        )

        result_dict = result.to_dict()

        self.assertEqual(result_dict['coherence_score'], 0.85)
        self.assertEqual(result_dict['summary'], "Test summary")
        self.assertEqual(result_dict['llm_model'], "test-model")


# ============================================================================
# Test Suite Execution
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("FINN+ TIER-2 ENGINE — UNIT TESTS")
    print("Phase 3: Week 3 — LARS Directive 6 (Priority 1)")
    print("=" * 80)
    print()

    # Run tests
    unittest.main(verbosity=2)
