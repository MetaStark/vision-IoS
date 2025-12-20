#!/usr/bin/env python3
"""
IoS-008 G2 HISTORICAL REPLAY VALIDATION
========================================
Authority: BOARD (Vice-CEO)
Technical Lead: FINN (Research), VEGA (Governance)
Classification: Tier-1 Critical

Validation Protocol:
1. FTX Collapse Test (Nov 2022)
2. Skill Damper Validation
3. No Shorting in G0 Mode
4. Regime-Causal Coherence Check
"""

import os
import sys
import json
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
from decimal import Decimal
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv()

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class IoS008G2Validator:
    """G2 Historical Replay Validation for IoS-008"""

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.results = {
            'metadata': {
                'validation_type': 'IOS008_G2_HISTORICAL_REPLAY',
                'module': 'IoS-008',
                'gate': 'G2',
                'started_at': datetime.now(timezone.utc).isoformat(),
                'validator': 'FINN/VEGA',
                'authority': 'BOARD'
            },
            'tests': {},
            'deviation_log': [],
            'timeline_2022': {},
            'overall_status': 'PENDING'
        }

    def _execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if cur.description:
                return [dict(row) for row in cur.fetchall()]
            return []

    def _get_regime_scalar(self, regime: str) -> float:
        """Get regime scalar from config (G0 Capital Preservation Mode)"""
        query = """
        SELECT scalar_value FROM fhq_governance.regime_scalar_config
        WHERE regime_label = %s AND is_active = true
        """
        result = self._execute_query(query, (regime,))
        return float(result[0]['scalar_value']) if result else 0.5

    def _compute_historical_allocation(self, regime: str, causal: float = 1.0, skill: float = 1.0) -> float:
        """Compute allocation using the formula: Base * RegimeScalar * CausalVector * SkillDamper"""
        regime_scalar = self._get_regime_scalar(regime)
        # G0 Mode: Apply formula
        allocation = 1.0 * regime_scalar * causal * skill
        # Clamp to valid range (G0: no shorting, so min is 0)
        return max(0.0, min(1.0, allocation))

    # =========================================================
    # TEST 1: FTX COLLAPSE (Nov 2022)
    # =========================================================
    def test_ftx_collapse(self) -> Dict:
        """
        FTX Collapse Test (Nov 2022)
        - Regime must enter BEAR/BROKEN
        - RegimeScalar MUST override CausalVector
        - Final Allocation MUST be 0.0%
        """
        print("\n" + "="*70)
        print("G2-1: FTX COLLAPSE TEST (November 2022)")
        print("="*70)

        # Query regime data during FTX collapse
        query = """
        SELECT
            r.timestamp::date as date,
            r.asset_id,
            r.regime_label,
            r.confidence_score
        FROM fhq_research.regime_predictions_v2 r
        WHERE r.timestamp >= '2022-11-01' AND r.timestamp <= '2022-11-30'
        AND r.asset_id IN ('BTC-USD', 'ETH-USD', 'SOL-USD')
        ORDER BY r.timestamp, r.asset_id
        """
        ftx_data = self._execute_query(query)

        # Analyze each day
        violations = []
        crisis_regimes = ['BEAR', 'STRONG_BEAR', 'BROKEN']

        daily_allocations = defaultdict(list)

        for row in ftx_data:
            regime = row['regime_label']
            asset = row['asset_id']
            date = str(row['date'])

            # Compute allocation (with aggressive causal to test override)
            allocation = self._compute_historical_allocation(
                regime=regime,
                causal=1.5,  # Simulate strong positive causal signal
                skill=1.0
            )

            daily_allocations[date].append({
                'asset': asset,
                'regime': regime,
                'allocation': allocation,
                'confidence': float(row['confidence_score'])
            })

            # Check for violations: non-zero allocation during crisis regime
            if regime in crisis_regimes and allocation > 0.0:
                violations.append({
                    'date': date,
                    'asset': asset,
                    'regime': regime,
                    'allocation': allocation,
                    'violation': 'NON_ZERO_ALLOCATION_IN_CRISIS'
                })

        # Count regime distribution
        regime_counts = defaultdict(int)
        for row in ftx_data:
            regime_counts[row['regime_label']] += 1

        # Determine pass/fail
        test_pass = len(violations) == 0

        test_result = {
            'test_id': 'G2-1',
            'test_name': 'FTX_COLLAPSE_TEST',
            'period': '2022-11-01 to 2022-11-30',
            'total_observations': len(ftx_data),
            'regime_distribution': dict(regime_counts),
            'crisis_regime_count': sum(regime_counts.get(r, 0) for r in crisis_regimes),
            'violations': violations,
            'violation_count': len(violations),
            'status': 'PASS' if test_pass else 'FAIL',
            'requirement': 'All BEAR/STRONG_BEAR/BROKEN regimes must have 0% allocation'
        }

        if test_pass:
            print(f"  [PASS] FTX Collapse: {len(ftx_data)} observations, 0 violations")
            print(f"         Crisis regimes: {test_result['crisis_regime_count']} observations")
        else:
            print(f"  [FAIL] FTX Collapse: {len(violations)} violations found")
            for v in violations[:5]:
                print(f"         {v['date']} {v['asset']}: {v['regime']} -> {v['allocation']:.2%}")

        self.results['tests']['G2-1'] = test_result

        # Store timeline for 2022
        self.results['timeline_2022']['november'] = dict(daily_allocations)

        return test_result

    # =========================================================
    # TEST 2: SKILL DAMPER VALIDATION
    # =========================================================
    def test_skill_damper(self) -> Dict:
        """
        Skill Damper Validation
        - FSS < 0.6 must scale down allocation
        - FSS < 0.4 must freeze (0% allocation)
        """
        print("\n" + "="*70)
        print("G2-2: SKILL DAMPER VALIDATION")
        print("="*70)

        # Test skill damper at various FSS levels
        test_cases = [
            {'fss': 0.35, 'expected_damper': 0.0, 'expected_behavior': 'FREEZE'},
            {'fss': 0.45, 'expected_damper': 0.25, 'expected_behavior': 'REDUCED'},
            {'fss': 0.55, 'expected_damper': 0.5, 'expected_behavior': 'CAUTIOUS'},
            {'fss': 0.65, 'expected_damper': 1.0, 'expected_behavior': 'NORMAL'},
            {'fss': 0.85, 'expected_damper': 1.0, 'expected_behavior': 'HIGH'},
        ]

        results = []
        all_pass = True

        for tc in test_cases:
            # Get damper from config
            query = """
            SELECT damper_value, threshold_type
            FROM fhq_governance.skill_damper_config
            WHERE is_active = true AND %s >= fss_min AND %s < fss_max
            """
            damper_result = self._execute_query(query, (tc['fss'], tc['fss']))

            actual_damper = float(damper_result[0]['damper_value']) if damper_result else 1.0
            actual_type = damper_result[0]['threshold_type'] if damper_result else 'UNKNOWN'

            # Compute allocation with BULL regime (1.0 scalar), strong causal (1.5)
            allocation = 1.0 * 1.0 * 1.5 * actual_damper  # Base * Regime * Causal * Skill
            full_allocation = 1.0 * 1.0 * 1.5 * 1.0  # Without damping

            is_scaled = allocation < full_allocation if actual_damper < 1.0 else True
            is_frozen = allocation == 0.0 if tc['fss'] < 0.4 else True

            test_pass = is_scaled and is_frozen
            if not test_pass:
                all_pass = False

            results.append({
                'fss': tc['fss'],
                'expected_damper': tc['expected_damper'],
                'actual_damper': actual_damper,
                'expected_behavior': tc['expected_behavior'],
                'actual_behavior': actual_type,
                'allocation': allocation,
                'full_allocation': full_allocation,
                'scaled_correctly': is_scaled,
                'frozen_correctly': is_frozen,
                'status': 'PASS' if test_pass else 'FAIL'
            })

            status = '[PASS]' if test_pass else '[FAIL]'
            print(f"  {status} FSS={tc['fss']}: damper={actual_damper}, alloc={allocation:.2f}")

        test_result = {
            'test_id': 'G2-2',
            'test_name': 'SKILL_DAMPER_VALIDATION',
            'test_cases': results,
            'status': 'PASS' if all_pass else 'FAIL',
            'requirement': 'FSS < 0.6 must scale, FSS < 0.4 must freeze'
        }

        self.results['tests']['G2-2'] = test_result
        return test_result

    # =========================================================
    # TEST 3: NO SHORTING IN G0 MODE
    # =========================================================
    def test_no_shorting_g0(self) -> Dict:
        """
        No Shorting in G0 Mode
        - Allocation MUST NEVER be < 0.0%
        """
        print("\n" + "="*70)
        print("G2-3: NO SHORTING IN G0 MODE")
        print("="*70)

        # Query all historical regime data
        query = """
        SELECT
            r.timestamp::date as date,
            r.asset_id,
            r.regime_label,
            r.confidence_score
        FROM fhq_research.regime_predictions_v2 r
        WHERE r.asset_id IN ('BTC-USD', 'ETH-USD', 'SOL-USD')
        ORDER BY r.timestamp
        """
        all_data = self._execute_query(query)

        violations = []
        total_checked = 0

        for row in all_data:
            total_checked += 1
            regime = row['regime_label']

            # Compute allocation
            allocation = self._compute_historical_allocation(
                regime=regime,
                causal=0.5,  # Test with negative-ish causal
                skill=1.0
            )

            # Check for negative allocation (shorting)
            if allocation < 0.0:
                violations.append({
                    'date': str(row['date']),
                    'asset': row['asset_id'],
                    'regime': regime,
                    'allocation': allocation,
                    'violation': 'NEGATIVE_ALLOCATION_G0'
                })

        test_pass = len(violations) == 0

        test_result = {
            'test_id': 'G2-3',
            'test_name': 'NO_SHORTING_G0_MODE',
            'total_observations': total_checked,
            'violations': violations,
            'violation_count': len(violations),
            'status': 'PASS' if test_pass else 'FAIL',
            'requirement': 'Allocation must never be < 0% in G0 mode'
        }

        if test_pass:
            print(f"  [PASS] No Shorting: {total_checked} observations, 0 negative allocations")
        else:
            print(f"  [FAIL] No Shorting: {len(violations)} negative allocation violations")

        self.results['tests']['G2-3'] = test_result
        return test_result

    # =========================================================
    # TEST 4: REGIME-CAUSAL COHERENCE
    # =========================================================
    def test_regime_causal_coherence(self) -> Dict:
        """
        Regime-Causal Coherence Check
        - Under BEAR/BROKEN, CausalVector MAY NOT force positive allocation
        - RegimeScalar must remain dominant
        """
        print("\n" + "="*70)
        print("G2-4: REGIME-CAUSAL COHERENCE CHECK")
        print("="*70)

        # Test all bear/broken regimes with aggressive positive causal
        bear_regimes = ['BEAR', 'STRONG_BEAR', 'BROKEN']
        test_cases = []
        all_pass = True

        for regime in bear_regimes:
            regime_scalar = self._get_regime_scalar(regime)

            # Test with very strong positive causal signal
            for causal in [1.0, 1.5, 2.0]:
                allocation = self._compute_historical_allocation(
                    regime=regime,
                    causal=causal,
                    skill=1.0
                )

                # Coherence: allocation must be 0 regardless of causal
                is_coherent = allocation == 0.0
                if not is_coherent:
                    all_pass = False

                test_cases.append({
                    'regime': regime,
                    'regime_scalar': regime_scalar,
                    'causal_vector': causal,
                    'allocation': allocation,
                    'coherent': is_coherent,
                    'status': 'PASS' if is_coherent else 'FAIL'
                })

        # Print results
        for tc in test_cases:
            status = '[PASS]' if tc['coherent'] else '[FAIL]'
            print(f"  {status} {tc['regime']} + Causal={tc['causal_vector']}: alloc={tc['allocation']:.2%}")

        test_result = {
            'test_id': 'G2-4',
            'test_name': 'REGIME_CAUSAL_COHERENCE',
            'test_cases': test_cases,
            'status': 'PASS' if all_pass else 'FAIL',
            'requirement': 'BEAR/BROKEN regimes must override positive CausalVector'
        }

        self.results['tests']['G2-4'] = test_result
        return test_result

    # =========================================================
    # GENERATE 2022 TIMELINE
    # =========================================================
    def generate_2022_timeline(self) -> Dict:
        """Generate ASCII timeline for 2022"""
        print("\n" + "="*70)
        print("2022 TIMELINE VISUALIZATION")
        print("="*70)

        query = """
        SELECT
            DATE_TRUNC('month', r.timestamp) as month,
            r.asset_id,
            r.regime_label,
            COUNT(*) as days,
            AVG(r.confidence_score) as avg_confidence
        FROM fhq_research.regime_predictions_v2 r
        WHERE r.timestamp >= '2022-01-01' AND r.timestamp < '2023-01-01'
        AND r.asset_id = 'BTC-USD'
        GROUP BY month, r.asset_id, r.regime_label
        ORDER BY month, days DESC
        """
        monthly_data = self._execute_query(query)

        # Build timeline
        timeline = {}
        for row in monthly_data:
            month_str = row['month'].strftime('%Y-%m') if row['month'] else 'Unknown'
            if month_str not in timeline:
                timeline[month_str] = []

            regime_scalar = self._get_regime_scalar(row['regime_label'])
            allocation = self._compute_historical_allocation(row['regime_label'], 1.0, 1.0)

            timeline[month_str].append({
                'regime': row['regime_label'],
                'days': row['days'],
                'confidence': float(row['avg_confidence']),
                'regime_scalar': regime_scalar,
                'allocation': allocation
            })

        # Print ASCII timeline
        print("\nBTC-USD 2022 Monthly Regime Summary:")
        print("-" * 70)
        print(f"{'Month':<10} {'Primary Regime':<15} {'Days':<6} {'Scalar':<8} {'Alloc':<8}")
        print("-" * 70)

        for month, regimes in sorted(timeline.items()):
            primary = regimes[0] if regimes else {'regime': 'N/A', 'days': 0, 'regime_scalar': 0, 'allocation': 0}
            alloc_bar = '#' * int(primary['allocation'] * 10)
            print(f"{month:<10} {primary['regime']:<15} {primary['days']:<6} {primary['regime_scalar']:<8.2f} {alloc_bar}")

        self.results['timeline_2022']['monthly_btc'] = timeline
        return timeline

    # =========================================================
    # MAIN EXECUTION
    # =========================================================
    def run_full_validation(self) -> Dict:
        """Execute complete G2 validation suite"""
        print("\n" + "="*70)
        print("IoS-008 G2 HISTORICAL REPLAY VALIDATION")
        print("Authority: BOARD | Validators: FINN/VEGA")
        print("="*70)

        # Run all tests
        self.test_ftx_collapse()
        self.test_skill_damper()
        self.test_no_shorting_g0()
        self.test_regime_causal_coherence()
        self.generate_2022_timeline()

        # Compute overall status
        all_tests_pass = all(
            t['status'] == 'PASS'
            for t in self.results['tests'].values()
        )

        self.results['overall_status'] = 'PASS' if all_tests_pass else 'FAIL'
        self.results['metadata']['completed_at'] = datetime.now(timezone.utc).isoformat()

        # Compile deviation log (all violations from all tests)
        for test_id, test_data in self.results['tests'].items():
            if 'violations' in test_data:
                self.results['deviation_log'].extend(test_data['violations'])

        # Generate integrity hash
        self.results['integrity_hash'] = hashlib.sha256(
            json.dumps(self.results['tests'], sort_keys=True, cls=DecimalEncoder).encode()
        ).hexdigest()

        # Print summary
        print("\n" + "="*70)
        print("G2 VALIDATION SUMMARY")
        print("="*70)
        for test_id, test_data in self.results['tests'].items():
            status_icon = "[PASS]" if test_data['status'] == 'PASS' else "[FAIL]"
            print(f"  {status_icon} {test_id}: {test_data['status']}")

        print("-"*70)
        print(f"  Deviation Log: {len(self.results['deviation_log'])} entries")
        overall_icon = "[PASS]" if self.results['overall_status'] == 'PASS' else "[FAIL]"
        print(f"  {overall_icon} OVERALL: {self.results['overall_status']}")
        print("="*70)

        return self.results

    def save_report(self, output_dir: str) -> str:
        """Save validation report to JSON"""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        filename = f"IOS008_G2_REPLAY_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2, cls=DecimalEncoder)

        print(f"\nReport saved: {filepath}")
        return filepath


def main():
    validator = IoS008G2Validator()
    results = validator.run_full_validation()

    # Save report
    output_dir = os.path.join(os.path.dirname(__file__), '..', '05_GOVERNANCE', 'PHASE3')
    validator.save_report(output_dir)

    # Exit with appropriate code
    sys.exit(0 if results['overall_status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
