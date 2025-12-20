"""
Wave 10: Cognitive Stress & Selection Framework
===============================================
CEO Directive: CD-WAVE10-STRESS-SELECTION-20251217

Purpose: Prove antifragility by demonstrating that the EC-018 / EC-020 cognitive stack:
- Rejects weak hypotheses decisively
- Aborts gracefully under uncertainty or data loss
- Prefers silence over false certainty
- Maintains constitutional discipline under stress

The system must prove it can say "no" correctly before it is ever trusted to say "yes" at scale.

Operating Mode: SHADOW / PAPER ONLY
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import random
import uuid

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='[WAVE10] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('C:/fhq-market-system/vision-ios/logs/wave10_stress.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class StressMode(Enum):
    """Wave 10 Stress Injection Modes"""
    NONE = "NONE"  # Normal operation
    FOG_OF_WAR = "FOG_OF_WAR"  # Ambiguity stress - sideways, choppy markets
    LIARS_POKER = "LIARS_POKER"  # Contradiction stress - conflicting signals
    DATA_BLACKOUT = "DATA_BLACKOUT"  # Edge case stress - partial data unavailability
    MIXED = "MIXED"  # Randomly apply different stress modes


class OutcomeCategory(Enum):
    """Hypothesis outcome categories for Kill Report"""
    HIGH = "HIGH"  # Accepted - signal rate
    MEDIUM = "MEDIUM"  # Review required - uncertainty rate
    LOW = "LOW"  # Rejected - silence rate
    ABORT = "ABORT"  # Silent drop - silence rate


@dataclass
class HypothesisOutcome:
    """Record of a hypothesis validation outcome"""
    hypothesis_id: str
    hypothesis_title: str
    outcome: OutcomeCategory
    confidence: float
    stress_mode: StressMode
    session_id: str
    timestamp: datetime
    cost_usd: float
    reason: str
    sitc_plan_id: Optional[str] = None
    is_good_kill: bool = False  # For "Good Kill" sampling


@dataclass
class KillReport:
    """Daily Kill Report per CEO Directive Wave 10"""
    report_id: str
    report_date: str
    total_hypotheses: int
    high_count: int
    medium_count: int
    low_count: int
    abort_count: int
    signal_rate: float  # HIGH / total (must be < 50%)
    uncertainty_rate: float  # MEDIUM / total (must be >= 20%)
    silence_rate: float  # (LOW + ABORT) / total (must be >= 30%)
    cost_total_usd: float
    cost_per_survivor_usd: float  # Cost per HIGH hypothesis
    constitutional_violation: bool
    violation_reason: Optional[str]
    good_kill_example: Optional[Dict]
    stress_mode_distribution: Dict[str, int]
    outcomes: List[Dict]

    def to_json(self) -> str:
        """Serialize to JSON for storage"""
        return json.dumps(asdict(self), indent=2, default=str)

    def meets_targets(self) -> Tuple[bool, List[str]]:
        """Check if Kill Report meets Wave 10 success metrics"""
        failures = []

        # Silence Rate (LOW + ABORT): >= 30%
        if self.silence_rate < 0.30:
            failures.append(f"Silence rate {self.silence_rate:.1%} < 30% target")

        # Uncertainty Rate (MEDIUM): >= 20%
        if self.uncertainty_rate < 0.20:
            failures.append(f"Uncertainty rate {self.uncertainty_rate:.1%} < 20% target")

        # Signal Rate (HIGH): < 50%
        if self.signal_rate >= 0.50:
            failures.append(f"Signal rate {self.signal_rate:.1%} >= 50% ceiling")

        return (len(failures) == 0, failures)


class StressInjector:
    """
    Wave 10 Stress Injection Engine

    Modifies market context to simulate adverse conditions:
    - FOG_OF_WAR: Sideways, choppy, post-shock markets
    - LIARS_POKER: Contradictory signals across data sources
    - DATA_BLACKOUT: Partial data unavailability
    """

    # Historical stress scenarios for replay
    STRESS_SCENARIOS = {
        StressMode.FOG_OF_WAR: [
            {
                "name": "BTC May-June 2021 Post-Crash Consolidation",
                "regime": "NEUTRAL",
                "regime_confidence": 0.45,  # Low confidence
                "defcon": 3,
                "volatility_state": "ELEVATED",
                "market_description": "Post-crash sideways consolidation with mixed signals"
            },
            {
                "name": "ETH Sept 2022 Merge Uncertainty",
                "regime": "NEUTRAL",
                "regime_confidence": 0.52,
                "defcon": 3,
                "volatility_state": "HIGH",
                "market_description": "Pre-event uncertainty with choppy price action"
            },
            {
                "name": "Q1 2023 Banking Crisis Aftermath",
                "regime": "STRESS",
                "regime_confidence": 0.48,
                "defcon": 2,
                "volatility_state": "EXTREME",
                "market_description": "Post-shock recovery with unclear direction"
            }
        ],
        StressMode.LIARS_POKER: [
            {
                "name": "Bullish Price / Bearish On-Chain",
                "regime": "BULL",
                "regime_confidence": 0.65,
                "defcon": 4,
                "contradiction": {
                    "price_signal": "BULLISH",
                    "onchain_signal": "BEARISH",
                    "macro_signal": "NEUTRAL",
                    "description": "Price rising but exchange inflows increasing (distribution)"
                }
            },
            {
                "name": "Bearish Price / Bullish Fundamentals",
                "regime": "BEAR",
                "regime_confidence": 0.60,
                "defcon": 3,
                "contradiction": {
                    "price_signal": "BEARISH",
                    "onchain_signal": "BULLISH",
                    "macro_signal": "BEARISH",
                    "description": "Price falling but accumulation addresses increasing"
                }
            },
            {
                "name": "Macro-Crypto Divergence",
                "regime": "NEUTRAL",
                "regime_confidence": 0.55,
                "defcon": 3,
                "contradiction": {
                    "price_signal": "BULLISH",
                    "onchain_signal": "NEUTRAL",
                    "macro_signal": "BEARISH",
                    "description": "Crypto rallying while equities and risk assets sell off"
                }
            }
        ],
        StressMode.DATA_BLACKOUT: [
            {
                "name": "Exchange API Unavailable",
                "missing_data": ["btc_price", "volume", "order_book"],
                "available_data": ["onchain_metrics", "macro_indicators"],
                "blackout_severity": "PARTIAL"
            },
            {
                "name": "On-Chain Data Delay",
                "missing_data": ["onchain_metrics", "whale_movements"],
                "available_data": ["btc_price", "volume", "macro_indicators"],
                "blackout_severity": "PARTIAL"
            },
            {
                "name": "Full Data Blackout",
                "missing_data": ["btc_price", "volume", "onchain_metrics"],
                "available_data": ["macro_indicators"],
                "blackout_severity": "SEVERE"
            }
        ]
    }

    def __init__(self):
        self.current_mode = StressMode.NONE
        self.injection_count = 0

    def inject_stress(self, context: Dict, mode: StressMode) -> Tuple[Dict, Dict]:
        """
        Inject stress into market context.

        Returns:
            Tuple of (modified_context, stress_metadata)
        """
        if mode == StressMode.NONE:
            return context, {"stress_mode": "NONE", "injected": False}

        if mode == StressMode.MIXED:
            mode = random.choice([StressMode.FOG_OF_WAR, StressMode.LIARS_POKER, StressMode.DATA_BLACKOUT])

        self.current_mode = mode
        self.injection_count += 1

        if mode == StressMode.FOG_OF_WAR:
            return self._inject_fog_of_war(context)
        elif mode == StressMode.LIARS_POKER:
            return self._inject_liars_poker(context)
        elif mode == StressMode.DATA_BLACKOUT:
            return self._inject_data_blackout(context)

        return context, {"stress_mode": mode.value, "injected": False}

    def _inject_fog_of_war(self, context: Dict) -> Tuple[Dict, Dict]:
        """
        Fog of War: Ambiguity stress - sideways, choppy markets

        Expected EC-020 behavior: Return MEDIUM (REVIEW_REQUIRED)
        """
        scenario = random.choice(self.STRESS_SCENARIOS[StressMode.FOG_OF_WAR])

        modified = context.copy()
        modified['regime'] = scenario['regime']
        modified['regime_confidence'] = scenario['regime_confidence']
        modified['defcon'] = scenario['defcon']
        modified['stress_injected'] = True
        modified['stress_scenario'] = scenario['name']
        modified['market_description'] = scenario['market_description']

        # Add volatility state if not present
        modified['volatility_state'] = scenario.get('volatility_state', 'ELEVATED')

        metadata = {
            "stress_mode": StressMode.FOG_OF_WAR.value,
            "injected": True,
            "scenario": scenario['name'],
            "expected_outcome": "MEDIUM (REVIEW_REQUIRED)",
            "rationale": "Low regime confidence and elevated volatility should trigger uncertainty"
        }

        logger.info(f"FOG_OF_WAR injected: {scenario['name']}")
        return modified, metadata

    def _inject_liars_poker(self, context: Dict) -> Tuple[Dict, Dict]:
        """
        Liar's Poker: Contradiction stress - conflicting signals

        Expected EC-020 behavior: Return LOW or ABORT
        """
        scenario = random.choice(self.STRESS_SCENARIOS[StressMode.LIARS_POKER])

        modified = context.copy()
        modified['regime'] = scenario['regime']
        modified['regime_confidence'] = scenario['regime_confidence']
        modified['defcon'] = scenario['defcon']
        modified['stress_injected'] = True
        modified['stress_scenario'] = scenario['name']

        # Inject contradiction into context
        modified['signal_contradiction'] = scenario['contradiction']
        modified['conflicting_evidence'] = True
        modified['contradiction_description'] = scenario['contradiction']['description']

        metadata = {
            "stress_mode": StressMode.LIARS_POKER.value,
            "injected": True,
            "scenario": scenario['name'],
            "contradiction": scenario['contradiction'],
            "expected_outcome": "LOW or ABORT",
            "rationale": "Conflicting signals should trigger hypothesis rejection"
        }

        logger.info(f"LIARS_POKER injected: {scenario['name']}")
        return modified, metadata

    def _inject_data_blackout(self, context: Dict) -> Tuple[Dict, Dict]:
        """
        Data Blackout: Edge case stress - partial data unavailability

        Expected EC-020 behavior: ABORT (Silent Drop)
        """
        scenario = random.choice(self.STRESS_SCENARIOS[StressMode.DATA_BLACKOUT])

        modified = context.copy()
        modified['stress_injected'] = True
        modified['stress_scenario'] = scenario['name']
        modified['data_blackout'] = True
        modified['blackout_severity'] = scenario['blackout_severity']

        # Null out missing data fields
        for field in scenario['missing_data']:
            if field in modified:
                modified[field] = None
            # Also set specific markers
            modified[f'{field}_unavailable'] = True

        # Mark available data
        modified['available_data'] = scenario['available_data']

        metadata = {
            "stress_mode": StressMode.DATA_BLACKOUT.value,
            "injected": True,
            "scenario": scenario['name'],
            "missing_data": scenario['missing_data'],
            "available_data": scenario['available_data'],
            "severity": scenario['blackout_severity'],
            "expected_outcome": "ABORT (Silent Drop)",
            "rationale": "Partial data unavailability should trigger graceful abort"
        }

        logger.info(f"DATA_BLACKOUT injected: {scenario['name']} (severity: {scenario['blackout_severity']})")
        return modified, metadata


class Wave10BatchRunner:
    """
    Wave 10 Batch Runner

    Executes multiple hypothesis generation cycles with stress injection
    to meet the minimum 30 hypothesis requirement.
    """

    FOCUS_AREAS = [
        'momentum', 'mean_reversion', 'breakout', 'volatility',
        'regime_transition', 'correlation', 'liquidity', 'sentiment'
    ]

    def __init__(self, daemon):
        """
        Initialize with EC-018 daemon instance.

        Args:
            daemon: EC018AlphaDaemon instance
        """
        self.daemon = daemon
        self.stress_injector = StressInjector()
        self.outcomes: List[HypothesisOutcome] = []
        self.batch_id = f"WAVE10-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def run_stress_batch(
        self,
        target_hypotheses: int = 30,
        stress_distribution: Optional[Dict[str, float]] = None
    ) -> KillReport:
        """
        Run a batch of hypothesis generation with stress injection.

        Args:
            target_hypotheses: Minimum number of hypotheses to generate (default 30)
            stress_distribution: Distribution of stress modes (default: equal)

        Returns:
            KillReport with aggregated results
        """
        logger.info(f"Starting Wave 10 stress batch: {self.batch_id}")
        logger.info(f"Target: {target_hypotheses} hypotheses")

        if stress_distribution is None:
            # Default: 30% each stress mode, 10% normal
            stress_distribution = {
                StressMode.FOG_OF_WAR.value: 0.30,
                StressMode.LIARS_POKER.value: 0.30,
                StressMode.DATA_BLACKOUT.value: 0.30,
                StressMode.NONE.value: 0.10
            }

        total_hypotheses = 0
        hunt_count = 0
        total_cost = 0.0

        # Track stress mode distribution
        mode_counts = {mode.value: 0 for mode in StressMode}

        while total_hypotheses < target_hypotheses:
            # Select stress mode based on distribution
            stress_mode = self._select_stress_mode(stress_distribution)
            mode_counts[stress_mode.value] += 1

            # Select focus area
            focus_area = self.FOCUS_AREAS[hunt_count % len(self.FOCUS_AREAS)]

            logger.info(f"Hunt {hunt_count + 1}: {focus_area} with {stress_mode.value}")

            try:
                # Run hunt with stress injection
                result = self._run_stressed_hunt(focus_area, stress_mode)

                if result.get('success'):
                    hypotheses_generated = result.get('hypotheses_generated', 0)
                    total_hypotheses += hypotheses_generated
                    total_cost += result.get('cost_usd', 0)

                    # Record outcomes
                    self._record_outcomes(result, stress_mode)

                    logger.info(
                        f"Hunt {hunt_count + 1} complete: {hypotheses_generated} hypotheses, "
                        f"running total: {total_hypotheses}"
                    )
                else:
                    logger.warning(f"Hunt {hunt_count + 1} failed: {result.get('reason', 'unknown')}")

            except Exception as e:
                logger.error(f"Hunt {hunt_count + 1} error: {e}")

            hunt_count += 1

            # Safety limit
            if hunt_count > 20:
                logger.warning("Hunt limit reached (20), generating partial report")
                break

        # Generate Kill Report
        report = self._generate_kill_report(mode_counts, total_cost)

        logger.info(f"Batch complete: {total_hypotheses} hypotheses across {hunt_count} hunts")
        logger.info(f"Silence rate: {report.silence_rate:.1%}, Signal rate: {report.signal_rate:.1%}")

        return report

    def _select_stress_mode(self, distribution: Dict[str, float]) -> StressMode:
        """Select stress mode based on probability distribution."""
        r = random.random()
        cumulative = 0.0

        for mode_str, prob in distribution.items():
            cumulative += prob
            if r <= cumulative:
                return StressMode(mode_str)

        return StressMode.NONE

    def _run_stressed_hunt(self, focus_area: str, stress_mode: StressMode) -> Dict:
        """
        Run a single hunt with stress injection.

        Modifies the daemon's get_market_context to inject stress.
        """
        # Store original method
        original_get_context = self.daemon.get_market_context

        def stressed_get_context():
            """Wrapper that injects stress into market context."""
            context = original_get_context()
            modified_context, metadata = self.stress_injector.inject_stress(context, stress_mode)
            # Store metadata in context for later retrieval
            modified_context['_stress_metadata'] = metadata
            return modified_context

        try:
            # Replace method temporarily
            self.daemon.get_market_context = stressed_get_context

            # Run hunt
            result = self.daemon.run_hunt(focus_area)

            # Add stress metadata to result
            result['stress_mode'] = stress_mode.value

            return result

        finally:
            # Restore original method
            self.daemon.get_market_context = original_get_context

    def _record_outcomes(self, result: Dict, stress_mode: StressMode):
        """Record hypothesis outcomes from hunt result."""
        sitc_validation = result.get('sitc_validation', {})

        # Create outcome records based on validation results
        accepted = sitc_validation.get('accepted', 0)
        log_only = sitc_validation.get('log_only', 0)
        rejected = sitc_validation.get('rejected', 0)
        aborted = sitc_validation.get('aborted', 0)

        session_id = result.get('session_id', 'unknown')
        cost_per = result.get('cost_usd', 0) / max(accepted + log_only + rejected + aborted, 1)

        # Record each outcome type
        for i in range(accepted):
            self.outcomes.append(HypothesisOutcome(
                hypothesis_id=f"{session_id}-HIGH-{i}",
                hypothesis_title=f"Hypothesis (HIGH confidence)",
                outcome=OutcomeCategory.HIGH,
                confidence=0.85,
                stress_mode=stress_mode,
                session_id=session_id,
                timestamp=datetime.now(timezone.utc),
                cost_usd=cost_per,
                reason="HIGH confidence - accepted"
            ))

        for i in range(log_only):
            self.outcomes.append(HypothesisOutcome(
                hypothesis_id=f"{session_id}-MEDIUM-{i}",
                hypothesis_title=f"Hypothesis (MEDIUM confidence)",
                outcome=OutcomeCategory.MEDIUM,
                confidence=0.60,
                stress_mode=stress_mode,
                session_id=session_id,
                timestamp=datetime.now(timezone.utc),
                cost_usd=cost_per,
                reason="MEDIUM confidence - review required"
            ))

        for i in range(rejected):
            self.outcomes.append(HypothesisOutcome(
                hypothesis_id=f"{session_id}-LOW-{i}",
                hypothesis_title=f"Hypothesis (LOW confidence)",
                outcome=OutcomeCategory.LOW,
                confidence=0.35,
                stress_mode=stress_mode,
                session_id=session_id,
                timestamp=datetime.now(timezone.utc),
                cost_usd=cost_per,
                reason="LOW confidence - rejected",
                is_good_kill=True  # Candidate for Good Kill example
            ))

        for i in range(aborted):
            self.outcomes.append(HypothesisOutcome(
                hypothesis_id=f"{session_id}-ABORT-{i}",
                hypothesis_title=f"Hypothesis (ABORTED)",
                outcome=OutcomeCategory.ABORT,
                confidence=0.0,
                stress_mode=stress_mode,
                session_id=session_id,
                timestamp=datetime.now(timezone.utc),
                cost_usd=cost_per,
                reason="ABORT - silent drop",
                is_good_kill=True
            ))

    def _generate_kill_report(self, mode_counts: Dict[str, int], total_cost: float) -> KillReport:
        """Generate the Kill Report per CEO Directive."""
        total = len(self.outcomes)
        if total == 0:
            logger.error("No outcomes recorded - cannot generate Kill Report")
            total = 1  # Prevent division by zero

        high_count = sum(1 for o in self.outcomes if o.outcome == OutcomeCategory.HIGH)
        medium_count = sum(1 for o in self.outcomes if o.outcome == OutcomeCategory.MEDIUM)
        low_count = sum(1 for o in self.outcomes if o.outcome == OutcomeCategory.LOW)
        abort_count = sum(1 for o in self.outcomes if o.outcome == OutcomeCategory.ABORT)

        signal_rate = high_count / total
        uncertainty_rate = medium_count / total
        silence_rate = (low_count + abort_count) / total

        # Cost per survivor (HIGH only)
        cost_per_survivor = total_cost / max(high_count, 1)

        # Check constitutional violation (>80% HIGH)
        constitutional_violation = signal_rate > 0.80
        violation_reason = None
        if constitutional_violation:
            violation_reason = (
                f"Signal rate {signal_rate:.1%} exceeds 80% threshold. "
                "Thresholds deemed constitutionally too loose. "
                "G1-governed remediation proposal required."
            )

        # Select Good Kill example
        good_kill_example = self._select_good_kill()

        report = KillReport(
            report_id=f"KILL-{self.batch_id}",
            report_date=datetime.now().strftime('%Y-%m-%d'),
            total_hypotheses=total,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            abort_count=abort_count,
            signal_rate=signal_rate,
            uncertainty_rate=uncertainty_rate,
            silence_rate=silence_rate,
            cost_total_usd=total_cost,
            cost_per_survivor_usd=cost_per_survivor,
            constitutional_violation=constitutional_violation,
            violation_reason=violation_reason,
            good_kill_example=good_kill_example,
            stress_mode_distribution=mode_counts,
            outcomes=[asdict(o) for o in self.outcomes]
        )

        return report

    def _select_good_kill(self) -> Optional[Dict]:
        """
        Select a Good Kill example for the report.

        Per CEO Directive: One rejected hypothesis per report,
        randomly sampled, fully anonymized.
        """
        # Find candidates (LOW or ABORT outcomes)
        candidates = [o for o in self.outcomes if o.is_good_kill]

        if not candidates:
            return None

        # Random selection
        selected = random.choice(candidates)

        # Anonymize
        return {
            "outcome": selected.outcome.value,
            "stress_mode": selected.stress_mode.value,
            "reason": selected.reason,
            "cost_usd": selected.cost_usd,
            "description": (
                "A seductive hypothesis that was correctly rejected due to "
                f"{selected.stress_mode.value} stress conditions. "
                "Asset and regime identifiers redacted per policy."
            )
        }


def main():
    """CLI entry point for Wave 10 stress testing."""
    import argparse

    parser = argparse.ArgumentParser(description='Wave 10: Cognitive Stress & Selection')
    parser.add_argument('--batch', action='store_true', help='Run full stress batch (30+ hypotheses)')
    parser.add_argument('--target', type=int, default=30, help='Target number of hypotheses')
    parser.add_argument('--report', type=str, help='Output path for Kill Report JSON')
    parser.add_argument('--mode', type=str, choices=['fog', 'liar', 'blackout', 'mixed', 'none'],
                        default='mixed', help='Stress mode')
    args = parser.parse_args()

    # Import EC-018 daemon
    from ec018_alpha_daemon import EC018AlphaDaemon

    # Create daemon and runner
    daemon = EC018AlphaDaemon()

    try:
        daemon.connect()

        if args.batch:
            runner = Wave10BatchRunner(daemon)

            # Configure stress distribution based on mode
            if args.mode == 'mixed':
                distribution = {
                    StressMode.FOG_OF_WAR.value: 0.30,
                    StressMode.LIARS_POKER.value: 0.30,
                    StressMode.DATA_BLACKOUT.value: 0.30,
                    StressMode.NONE.value: 0.10
                }
            else:
                mode_map = {
                    'fog': StressMode.FOG_OF_WAR,
                    'liar': StressMode.LIARS_POKER,
                    'blackout': StressMode.DATA_BLACKOUT,
                    'none': StressMode.NONE
                }
                selected_mode = mode_map.get(args.mode, StressMode.NONE)
                distribution = {selected_mode.value: 1.0}

            report = runner.run_stress_batch(target_hypotheses=args.target)

            # Output report
            print("\n" + "=" * 60)
            print("WAVE 10 KILL REPORT")
            print("=" * 60)
            print(f"Report ID: {report.report_id}")
            print(f"Date: {report.report_date}")
            print(f"Total Hypotheses: {report.total_hypotheses}")
            print()
            print("OUTCOME DISTRIBUTION:")
            print(f"  HIGH (Signal):      {report.high_count:3d} ({report.signal_rate:.1%})")
            print(f"  MEDIUM (Uncertain): {report.medium_count:3d} ({report.uncertainty_rate:.1%})")
            print(f"  LOW (Rejected):     {report.low_count:3d}")
            print(f"  ABORT (Silent):     {report.abort_count:3d}")
            print(f"  SILENCE RATE:       {report.silence_rate:.1%}")
            print()
            print("TARGETS:")
            meets, failures = report.meets_targets()
            print(f"  Signal < 50%:    {'PASS' if report.signal_rate < 0.50 else 'FAIL'}")
            print(f"  Uncertainty >= 20%: {'PASS' if report.uncertainty_rate >= 0.20 else 'FAIL'}")
            print(f"  Silence >= 30%:  {'PASS' if report.silence_rate >= 0.30 else 'FAIL'}")
            print()
            print(f"Constitutional Violation: {'YES - REMEDIATION REQUIRED' if report.constitutional_violation else 'NO'}")
            print()
            print(f"Cost Total: ${report.cost_total_usd:.4f}")
            print(f"Cost per Survivor: ${report.cost_per_survivor_usd:.4f}")
            print("=" * 60)

            if args.report:
                with open(args.report, 'w') as f:
                    f.write(report.to_json())
                print(f"\nKill Report saved to: {args.report}")

        else:
            print("Use --batch to run Wave 10 stress batch")

    finally:
        daemon.close()


if __name__ == '__main__':
    main()
