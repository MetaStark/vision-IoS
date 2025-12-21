#!/usr/bin/env python3
"""
EQS 2.0 SHADOW EVALUATOR
=========================
CEO Directive: CEO-EQS-2-2025-12-21
Classification: RESEARCH-CRITICAL
Mode: SHADOW / READ-ONLY / NO EXECUTION INFLUENCE

Purpose:
    Parallel shadow evaluation of hypotheses using EQS 2.0 methodology.
    All evaluations logged but NOT used for promotion decisions.

Phases:
    A: Semantic & Logical Consistency (gatekeeper)
    B: Regime-Conditioned Statistical Robustness (overfitting penalty)
    C: Economic & Microstructure Coherence (execution feasibility)

Integration:
    Called by wave15_autonomous_hunter.py AFTER EQS 1.0 evaluation.
    Results logged to fhq_research.eqs2_shadow_evaluations.
"""

import os
import sys
import json
import hashlib
import logging
import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

import psycopg2
from psycopg2.extras import RealDictCursor, Json
import requests
from dotenv import load_dotenv

load_dotenv('C:/fhq-market-system/vision-ios/.env')

# Logging
logger = logging.getLogger('EQS2_SHADOW')

# Configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# EQS 2.0 Thresholds
EQS2_THRESHOLD = 0.85
PHASE_A_MIN = 0.70  # Semantic/logic gatekeeper
PHASE_B_MIN = 0.60  # Statistical robustness (after penalty)
PHASE_C_MIN = 0.65  # Economic coherence

# Overfitting Penalty Formula Constants
OVERFITTING_PENALTY_MAX = 0.15
OVERFITTING_PENALTY_COEFFICIENT = 0.02


@dataclass
class EQS2Result:
    """Result of EQS 2.0 shadow evaluation."""
    hypothesis_hash: str
    target_asset: str
    eqs1_score: float
    eqs1_decision: str

    phase_a_score: float
    phase_a_passed: bool
    phase_a_breakdown: Dict

    phase_b_score: float
    phase_b_passed: bool
    phase_b_breakdown: Dict
    shadow_ledger_n: int
    overfitting_penalty: float

    phase_c_score: float
    phase_c_passed: bool
    phase_c_breakdown: Dict

    eqs2_final_score: float
    eqs2_decision: str
    eqs2_confidence: str


class EQS2ShadowEvaluator:
    """
    EQS 2.0 Shadow Evaluator - Three-Phase Validation.

    SHADOW MODE ONLY: Results are logged but do not influence execution.
    """

    def __init__(self, conn=None):
        self.conn = conn
        self.deepseek_key = os.environ.get('DEEPSEEK_API_KEY', '')
        self._own_connection = False

        if not self.conn:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self._own_connection = True

    def close(self):
        """Close connection if we own it."""
        if self._own_connection and self.conn:
            self.conn.close()

    # =========================================================================
    # PHASE A: Semantic & Logical Consistency
    # =========================================================================

    def evaluate_phase_a(self, hypothesis: Dict, context: Dict) -> Tuple[float, bool, Dict]:
        """
        Phase A: Semantic & Logical Consistency (Gatekeeper).

        Checks:
        1. Semantic Coherence: Does the statement make grammatical/logical sense?
        2. Logical Consistency: Are entry/exit conditions non-contradictory?
        3. Adversarial Probe: Can we poke holes in the reasoning?

        Uses lightweight DeepSeek call for semantic analysis.
        """
        breakdown = {
            'semantic_coherence': 0.0,
            'logical_consistency': 0.0,
            'adversarial_probe': 0.0,
            'details': {}
        }

        statement = hypothesis.get('statement', '')
        entry_conditions = hypothesis.get('entry_conditions', [])
        exit_conditions = hypothesis.get('exit_conditions', {})
        rationale = hypothesis.get('rationale', '')

        # 1. Semantic Coherence (rule-based check)
        semantic_score = self._check_semantic_coherence(statement, rationale)
        breakdown['semantic_coherence'] = semantic_score
        breakdown['details']['semantic_issues'] = []

        if len(statement) < 20:
            breakdown['details']['semantic_issues'].append('Statement too short')
            semantic_score *= 0.5

        if not any(c.isalpha() for c in statement):
            breakdown['details']['semantic_issues'].append('No alphabetic content')
            semantic_score = 0.0

        # 2. Logical Consistency (check entry/exit non-contradiction)
        logical_score = self._check_logical_consistency(
            statement, entry_conditions, exit_conditions
        )
        breakdown['logical_consistency'] = logical_score
        breakdown['details']['logical_issues'] = []

        # Check for contradictory conditions
        if exit_conditions:
            tp = exit_conditions.get('take_profit', '')
            sl = exit_conditions.get('stop_loss', '')
            if tp and sl:
                # Basic sanity: TP and SL should be different directions
                tp_is_up = any(x in tp.lower() for x in ['above', 'up', 'increase', 'gain'])
                sl_is_down = any(x in sl.lower() for x in ['below', 'down', 'decrease', 'loss'])
                if tp_is_up and sl_is_down:
                    logical_score = min(1.0, logical_score + 0.1)  # Good structure
                elif not tp and not sl:
                    logical_score *= 0.8
                    breakdown['details']['logical_issues'].append('Missing exit conditions')

        breakdown['logical_consistency'] = logical_score

        # 3. Adversarial Probe (lightweight check without LLM to save cost)
        adversarial_score = self._adversarial_probe_rules(hypothesis, context)
        breakdown['adversarial_probe'] = adversarial_score

        # Calculate Phase A score
        phase_a_score = (
            semantic_score * 0.35 +
            logical_score * 0.35 +
            adversarial_score * 0.30
        )

        passed = phase_a_score >= PHASE_A_MIN

        return phase_a_score, passed, breakdown

    def _check_semantic_coherence(self, statement: str, rationale: str) -> float:
        """Rule-based semantic coherence check."""
        score = 0.8  # Base score

        # Check for complete sentences
        if statement.endswith('.') or statement.endswith('?'):
            score += 0.05

        # Check for trading-relevant terms
        trading_terms = ['price', 'market', 'trade', 'position', 'entry', 'exit',
                         'buy', 'sell', 'long', 'short', 'support', 'resistance']
        terms_found = sum(1 for t in trading_terms if t in statement.lower())
        score += min(0.15, terms_found * 0.03)

        # Check rationale quality
        if rationale and len(rationale) > 20:
            score += 0.05
            if any(x in rationale.lower() for x in ['because', 'due to', 'as', 'since']):
                score += 0.05  # Has causal reasoning

        return min(1.0, score)

    def _check_logical_consistency(self, statement: str, entry: List, exit: Dict) -> float:
        """Check for logical contradictions in hypothesis structure."""
        score = 0.75  # Base score

        # Has entry conditions
        if entry and len(entry) > 0:
            score += 0.1
            if len(entry) >= 2:
                score += 0.05  # Multiple conditions = more specific

        # Has exit conditions
        if exit:
            if exit.get('take_profit'):
                score += 0.05
            if exit.get('stop_loss'):
                score += 0.05
            if exit.get('time_exit'):
                score += 0.05

        return min(1.0, score)

    def _adversarial_probe_rules(self, hypothesis: Dict, context: Dict) -> float:
        """Rule-based adversarial probing without LLM call."""
        score = 0.85  # Base score

        statement = hypothesis.get('statement', '').lower()
        falsification = hypothesis.get('falsification_criteria', '')

        # Check for overconfident language (penalize)
        overconfident = ['always', 'never', 'guaranteed', 'certain', '100%', 'impossible']
        if any(x in statement for x in overconfident):
            score -= 0.15

        # Check for hedging language (slightly penalize - might indicate weak thesis)
        hedging = ['might', 'could', 'possibly', 'perhaps', 'maybe']
        hedge_count = sum(1 for x in hedging if x in statement)
        if hedge_count > 2:
            score -= 0.10

        # Check for falsification criteria quality
        if falsification:
            if len(falsification) > 30:
                score += 0.05
            if any(x in falsification.lower() for x in ['if', 'when', 'unless', 'fails']):
                score += 0.05

        # Regime alignment check
        regime_filter = hypothesis.get('regime_filter', [])
        current_regime = context.get('regime', 'NEUTRAL')
        if regime_filter and current_regime not in regime_filter:
            score -= 0.10  # Misaligned with current regime

        return max(0.0, min(1.0, score))

    # =========================================================================
    # PHASE B: Regime-Conditioned Statistical Robustness
    # =========================================================================

    def evaluate_phase_b(self, hypothesis: Dict, context: Dict) -> Tuple[float, bool, Dict, int, float]:
        """
        Phase B: Regime-Conditioned Statistical Robustness.

        Applies overfitting penalty based on Shadow Ledger count.
        High rejection count for asset = pattern may be overfit.

        Formula: penalty = min(0.15, 0.02 * log2(N+1))
        """
        breakdown = {
            'regime_prior': 0.0,
            'shadow_ledger_penalty': 0.0,
            'statistical_significance': 0.0,
            'details': {}
        }

        # Extract target asset from hypothesis
        statement = hypothesis.get('statement', '')
        title = hypothesis.get('title', '')
        target_asset = self._extract_target_asset(statement + ' ' + title)

        # 1. Regime Prior: How well does hypothesis fit current regime?
        regime_prior = self._calculate_regime_prior(hypothesis, context)
        breakdown['regime_prior'] = regime_prior

        # 2. Shadow Ledger Penalty
        shadow_ledger_n = self._get_shadow_ledger_count(target_asset)
        if shadow_ledger_n > 0:
            # Formula: penalty = min(0.15, 0.02 * log2(N+1))
            overfitting_penalty = min(
                OVERFITTING_PENALTY_MAX,
                OVERFITTING_PENALTY_COEFFICIENT * math.log2(shadow_ledger_n + 1)
            )
        else:
            overfitting_penalty = 0.0

        breakdown['shadow_ledger_penalty'] = -overfitting_penalty
        breakdown['details']['shadow_ledger_n'] = shadow_ledger_n
        breakdown['details']['penalty_formula'] = f'min(0.15, 0.02 * log2({shadow_ledger_n}+1))'

        # 3. Statistical Significance Estimate
        # Based on specificity of hypothesis
        statistical_sig = self._estimate_statistical_significance(hypothesis)
        breakdown['statistical_significance'] = statistical_sig

        # Calculate Phase B score (before penalty)
        base_score = regime_prior * 0.45 + statistical_sig * 0.55

        # Apply overfitting penalty
        phase_b_score = max(0.0, base_score - overfitting_penalty)

        passed = phase_b_score >= PHASE_B_MIN

        return phase_b_score, passed, breakdown, shadow_ledger_n, overfitting_penalty

    def _extract_target_asset(self, text: str) -> str:
        """Extract target asset from hypothesis text."""
        text_upper = text.upper()

        # Crypto assets
        crypto = ['BTC', 'ETH', 'SOL', 'XRP', 'ADA', 'DOGE', 'AVAX', 'DOT', 'LINK']
        for asset in crypto:
            if asset in text_upper:
                return asset

        # Check for full names
        if 'BITCOIN' in text_upper:
            return 'BTC'
        if 'ETHEREUM' in text_upper:
            return 'ETH'
        if 'SOLANA' in text_upper:
            return 'SOL'

        # Equities
        equities = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMZN', 'GOOG']
        for asset in equities:
            if asset in text_upper:
                return asset

        return 'UNKNOWN'

    def _get_shadow_ledger_count(self, target_asset: str, lookback_days: int = 30) -> int:
        """Get count of rejected hypotheses for asset from Shadow Ledger."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT fhq_research.get_shadow_ledger_count(%s, %s)
                """, (target_asset, lookback_days))
                result = cur.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.warning(f"Shadow ledger count failed: {e}")
            return 0

    def _calculate_regime_prior(self, hypothesis: Dict, context: Dict) -> float:
        """Calculate regime prior - how well hypothesis fits current regime."""
        regime_filter = hypothesis.get('regime_filter', [])
        current_regime = context.get('regime', 'NEUTRAL')
        regime_confidence = context.get('regime_confidence', 0.5)

        if not regime_filter:
            return 0.70  # No filter = generic hypothesis

        if current_regime in regime_filter:
            # Aligned with current regime
            return 0.80 + (regime_confidence * 0.20)
        else:
            # Misaligned
            return 0.50 * (1.0 - regime_confidence)

    def _estimate_statistical_significance(self, hypothesis: Dict) -> float:
        """Estimate statistical significance based on specificity."""
        score = 0.70

        statement = hypothesis.get('statement', '')

        # Check for specific numbers (more specific = higher significance potential)
        numbers = re.findall(r'\d+\.?\d*%?', statement)
        if len(numbers) >= 2:
            score += 0.15
        elif len(numbers) >= 1:
            score += 0.08

        # Check for time bounds (testable timeframe)
        time_terms = ['hour', 'day', 'week', 'session', 'period']
        if any(t in statement.lower() for t in time_terms):
            score += 0.08

        # Check for comparison operators
        if any(x in statement for x in ['>', '<', 'above', 'below', 'exceeds']):
            score += 0.07

        return min(1.0, score)

    # =========================================================================
    # PHASE C: Economic & Microstructure Coherence
    # =========================================================================

    def evaluate_phase_c(self, hypothesis: Dict, context: Dict) -> Tuple[float, bool, Dict]:
        """
        Phase C: Economic & Microstructure Coherence.

        Checks:
        1. Bid-Ask Feasibility: Can this be executed with reasonable spread?
        2. Latency Assumption: Are timing assumptions realistic?
        3. Slippage Estimate: Is the expected return > likely slippage?
        """
        breakdown = {
            'bid_ask_feasibility': 0.0,
            'latency_assumption': 0.0,
            'slippage_estimate': 0.0,
            'details': {}
        }

        statement = hypothesis.get('statement', '').lower()
        entry_conditions = hypothesis.get('entry_conditions', [])
        title = hypothesis.get('title', '')
        target_asset = self._extract_target_asset(statement + ' ' + title)

        # 1. Bid-Ask Feasibility
        bid_ask_score = self._check_bid_ask_feasibility(target_asset, hypothesis)
        breakdown['bid_ask_feasibility'] = bid_ask_score

        # 2. Latency Assumption
        latency_score = self._check_latency_assumptions(hypothesis)
        breakdown['latency_assumption'] = latency_score

        # 3. Slippage Estimate
        slippage_score = self._estimate_slippage_feasibility(hypothesis)
        breakdown['slippage_estimate'] = slippage_score

        # Calculate Phase C score
        phase_c_score = (
            bid_ask_score * 0.35 +
            latency_score * 0.30 +
            slippage_score * 0.35
        )

        passed = phase_c_score >= PHASE_C_MIN

        return phase_c_score, passed, breakdown

    def _check_bid_ask_feasibility(self, target_asset: str, hypothesis: Dict) -> float:
        """Check if hypothesis can be executed with reasonable spread."""
        # Major assets have tighter spreads
        liquid_assets = ['BTC', 'ETH', 'SPY', 'QQQ', 'AAPL', 'MSFT']
        medium_liquid = ['SOL', 'XRP', 'ADA', 'NVDA', 'TSLA']

        if target_asset in liquid_assets:
            return 0.95  # Very liquid
        elif target_asset in medium_liquid:
            return 0.85  # Reasonably liquid
        elif target_asset == 'UNKNOWN':
            return 0.70  # Unknown asset - assume moderate
        else:
            return 0.60  # Less liquid

    def _check_latency_assumptions(self, hypothesis: Dict) -> float:
        """Check if timing assumptions are realistic."""
        score = 0.80

        statement = hypothesis.get('statement', '').lower()
        entry_conditions = hypothesis.get('entry_conditions', [])

        # Penalize instant-reaction assumptions
        instant_terms = ['immediately', 'instantly', 'real-time', 'millisecond']
        if any(t in statement for t in instant_terms):
            score -= 0.20  # Unrealistic for retail

        # Check for reasonable timeframes
        reasonable_times = ['within hours', 'next day', 'session', 'week']
        if any(t in statement for t in reasonable_times):
            score += 0.10

        # Check entry conditions for latency assumptions
        entry_text = ' '.join(str(c) for c in entry_conditions).lower()
        if 'instant' in entry_text or 'immediate' in entry_text:
            score -= 0.15

        return max(0.0, min(1.0, score))

    def _estimate_slippage_feasibility(self, hypothesis: Dict) -> float:
        """Estimate if expected return > likely slippage."""
        score = 0.75

        statement = hypothesis.get('statement', '')
        exit_conditions = hypothesis.get('exit_conditions', {})

        # Extract percentage targets
        percentages = re.findall(r'(\d+\.?\d*)%', statement)
        if percentages:
            max_target = max(float(p) for p in percentages)
            if max_target >= 5.0:
                score = 0.90  # Good margin for slippage
            elif max_target >= 2.0:
                score = 0.80
            elif max_target >= 1.0:
                score = 0.70
            else:
                score = 0.50  # Very tight margin

        # Check take profit level
        tp = exit_conditions.get('take_profit', '')
        tp_percentages = re.findall(r'(\d+\.?\d*)%', tp)
        if tp_percentages:
            tp_target = max(float(p) for p in tp_percentages)
            if tp_target < 0.5:
                score -= 0.20  # TP too tight for slippage

        return max(0.0, min(1.0, score))

    # =========================================================================
    # MAIN EVALUATION
    # =========================================================================

    def evaluate(
        self,
        hypothesis: Dict,
        eqs1_score: float,
        eqs1_decision: str,
        context: Dict
    ) -> EQS2Result:
        """
        Run full EQS 2.0 shadow evaluation.

        Returns EQS2Result with all phase scores and final decision.
        This is SHADOW MODE - results are logged but do not influence execution.
        """
        # Generate hypothesis hash for tracking
        hypothesis_hash = hashlib.sha256(
            json.dumps(hypothesis, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

        # Extract target asset
        statement = hypothesis.get('statement', '')
        title = hypothesis.get('title', '')
        target_asset = self._extract_target_asset(statement + ' ' + title)

        # Phase A: Semantic & Logical Consistency
        phase_a_score, phase_a_passed, phase_a_breakdown = self.evaluate_phase_a(
            hypothesis, context
        )

        # Phase B: Regime-Conditioned Statistical Robustness
        phase_b_score, phase_b_passed, phase_b_breakdown, shadow_n, penalty = self.evaluate_phase_b(
            hypothesis, context
        )

        # Phase C: Economic & Microstructure Coherence
        phase_c_score, phase_c_passed, phase_c_breakdown = self.evaluate_phase_c(
            hypothesis, context
        )

        # Calculate final EQS 2.0 score
        # Phase A is gatekeeper - if fails, cap final score
        if not phase_a_passed:
            eqs2_final = phase_a_score * 0.8  # Capped due to gatekeeper failure
        else:
            eqs2_final = (
                phase_a_score * 0.30 +
                phase_b_score * 0.40 +
                phase_c_score * 0.30
            )

        # Determine decision
        if eqs2_final >= EQS2_THRESHOLD:
            eqs2_decision = 'WOULD_ACCEPT'
            eqs2_confidence = 'HIGH'
        elif eqs2_final >= 0.70:
            eqs2_decision = 'WOULD_LOG'
            eqs2_confidence = 'MEDIUM'
        else:
            eqs2_decision = 'WOULD_REJECT'
            eqs2_confidence = 'LOW'

        return EQS2Result(
            hypothesis_hash=hypothesis_hash,
            target_asset=target_asset,
            eqs1_score=eqs1_score,
            eqs1_decision=eqs1_decision,
            phase_a_score=phase_a_score,
            phase_a_passed=phase_a_passed,
            phase_a_breakdown=phase_a_breakdown,
            phase_b_score=phase_b_score,
            phase_b_passed=phase_b_passed,
            phase_b_breakdown=phase_b_breakdown,
            shadow_ledger_n=shadow_n,
            overfitting_penalty=penalty,
            phase_c_score=phase_c_score,
            phase_c_passed=phase_c_passed,
            phase_c_breakdown=phase_c_breakdown,
            eqs2_final_score=eqs2_final,
            eqs2_decision=eqs2_decision,
            eqs2_confidence=eqs2_confidence
        )

    def log_to_database(self, result: EQS2Result, hypothesis: Dict, context: Dict) -> Optional[str]:
        """Log EQS 2.0 shadow evaluation to database."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT fhq_research.log_eqs2_shadow_evaluation(
                        p_hypothesis_hash := %s,
                        p_target_asset := %s,
                        p_hypothesis_title := %s,
                        p_hypothesis_statement := %s,
                        p_eqs1_score := %s,
                        p_eqs1_decision := %s,
                        p_phase_a_score := %s,
                        p_phase_a_passed := %s,
                        p_phase_a_breakdown := %s,
                        p_phase_b_score := %s,
                        p_phase_b_passed := %s,
                        p_phase_b_breakdown := %s,
                        p_shadow_ledger_n := %s,
                        p_overfitting_penalty := %s,
                        p_phase_c_score := %s,
                        p_phase_c_passed := %s,
                        p_phase_c_breakdown := %s,
                        p_eqs2_final_score := %s,
                        p_eqs2_decision := %s,
                        p_eqs2_confidence := %s,
                        p_market_context := %s
                    )
                """, (
                    result.hypothesis_hash,
                    result.target_asset,
                    hypothesis.get('title', '')[:500],
                    hypothesis.get('statement', '')[:2000],
                    result.eqs1_score,
                    result.eqs1_decision,
                    result.phase_a_score,
                    result.phase_a_passed,
                    Json(result.phase_a_breakdown),
                    result.phase_b_score,
                    result.phase_b_passed,
                    Json(result.phase_b_breakdown),
                    result.shadow_ledger_n,
                    result.overfitting_penalty,
                    result.phase_c_score,
                    result.phase_c_passed,
                    Json(result.phase_c_breakdown),
                    result.eqs2_final_score,
                    result.eqs2_decision,
                    result.eqs2_confidence,
                    Json({
                        'regime': context.get('regime', 'NEUTRAL'),
                        'regime_confidence': context.get('regime_confidence', 0.5),
                        'btc_price': context.get('btc_price'),
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                ))
                evaluation_id = cur.fetchone()[0]
                self.conn.commit()

                logger.debug(f"EQS2 shadow logged: {evaluation_id}")
                return str(evaluation_id)

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to log EQS2 evaluation: {e}")
            return None


def evaluate_and_log(
    hypothesis: Dict,
    eqs1_score: float,
    eqs1_decision: str,
    context: Dict,
    conn=None
) -> Optional[EQS2Result]:
    """
    Convenience function for shadow evaluation.

    Called by wave15_autonomous_hunter.py after EQS 1.0 evaluation.
    """
    evaluator = EQS2ShadowEvaluator(conn)
    try:
        result = evaluator.evaluate(hypothesis, eqs1_score, eqs1_decision, context)
        evaluator.log_to_database(result, hypothesis, context)
        return result
    finally:
        if not conn:
            evaluator.close()


if __name__ == "__main__":
    # Test with sample hypothesis
    test_hypothesis = {
        'title': 'BTC Mean Reversion on Volume Spike',
        'statement': 'When BTC drops 5% intraday with volume 200% above average, expect 2-3% bounce within 4 hours',
        'category': 'MEAN_REVERSION',
        'entry_conditions': ['BTC price drop >= 5%', 'Volume >= 200% of 24h average'],
        'exit_conditions': {'take_profit': '3%', 'stop_loss': '2%', 'time_exit': '4 hours'},
        'regime_filter': ['BULL', 'NEUTRAL'],
        'rationale': 'High volume selloffs often exhaust sellers, creating bounce opportunity',
        'falsification_criteria': 'If bounce < 1% within 4 hours, thesis is invalid'
    }

    test_context = {
        'regime': 'NEUTRAL',
        'regime_confidence': 0.75,
        'btc_price': 95000.0
    }

    evaluator = EQS2ShadowEvaluator()
    try:
        result = evaluator.evaluate(
            hypothesis=test_hypothesis,
            eqs1_score=0.87,
            eqs1_decision='ACCEPT',
            context=test_context
        )

        print("\n" + "=" * 60)
        print("EQS 2.0 SHADOW EVALUATION RESULT")
        print("=" * 60)
        print(f"Target Asset: {result.target_asset}")
        print(f"EQS 1.0: {result.eqs1_score:.4f} ({result.eqs1_decision})")
        print("-" * 40)
        print(f"Phase A (Semantic): {result.phase_a_score:.4f} ({'PASS' if result.phase_a_passed else 'FAIL'})")
        print(f"Phase B (Statistical): {result.phase_b_score:.4f} ({'PASS' if result.phase_b_passed else 'FAIL'})")
        print(f"  Shadow Ledger N: {result.shadow_ledger_n}")
        print(f"  Overfitting Penalty: {result.overfitting_penalty:.4f}")
        print(f"Phase C (Economic): {result.phase_c_score:.4f} ({'PASS' if result.phase_c_passed else 'FAIL'})")
        print("-" * 40)
        print(f"EQS 2.0 FINAL: {result.eqs2_final_score:.4f}")
        print(f"Decision: {result.eqs2_decision} ({result.eqs2_confidence})")
        print("=" * 60)

        # Log to database
        eval_id = evaluator.log_to_database(result, test_hypothesis, test_context)
        if eval_id:
            print(f"\nLogged to database: {eval_id}")

    finally:
        evaluator.close()
