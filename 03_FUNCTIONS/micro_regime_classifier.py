#!/usr/bin/env python3
"""
Micro-Regime Classifier — CEO-DIR-2026-OPS-MICROREGIME-003
Author: STIG (EC-003)
Classification: OBSERVATIONAL ONLY

Classifies the current CRISIS macro regime into 4 micro-regimes:
  MR_ACUTE      — Portfolio avg stress_prob > 0.80, >50% assets in STRESS
  MR_SYSTEMIC   — Portfolio avg stress_prob 0.50-0.80, >30% high-stress assets
  MR_SELECTIVE   — Portfolio avg stress_prob 0.20-0.50, localized stress
  MR_EXHAUSTION  — Portfolio avg stress_prob < 0.20, or policy divergent + pending

HARD CONSTRAINTS:
  - EXECUTION_AUTHORITY = NONE
  - CAPITAL_AUTHORITY = ZERO
  - NO import of options_shadow_adapter
  - NO import of unified_execution_gateway
  - NO writes to fhq_execution tables
  - NO changes to IoS-012, IoS-009, or kill-switch

CLI:
  python micro_regime_classifier.py --classify     # Run classification
  python micro_regime_classifier.py --history      # Show classification history
  python micro_regime_classifier.py --backtest     # Backtest on historical data
  python micro_regime_classifier.py --check        # Self-test
"""

import sys
import os
import json
import hashlib
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# =============================================================================
# GOVERNANCE ASSERTIONS — HARD CONSTRAINTS
# =============================================================================

EXECUTION_AUTHORITY = "NONE"
CAPITAL_AUTHORITY = "ZERO"
DIRECTIVE = "CEO-DIR-2026-OPS-MICROREGIME-003"
MODULE_VERSION = "1.0.0"

assert EXECUTION_AUTHORITY == "NONE", "GOVERNANCE BREACH: Execution authority must be NONE"
assert CAPITAL_AUTHORITY == "ZERO", "GOVERNANCE BREACH: Capital authority must be ZERO"

# Verify no execution modules are imported
_FORBIDDEN_MODULES = [
    'options_shadow_adapter',
    'unified_execution_gateway',
    'options_defcon_killswitch',
    'alpaca_paper_adapter',
]
for _mod in _FORBIDDEN_MODULES:
    assert _mod not in sys.modules, f"GOVERNANCE BREACH: {_mod} must not be imported"

# =============================================================================
# MICRO-REGIME DEFINITIONS
# =============================================================================

MICRO_REGIMES = {
    'MR_ACUTE': {
        'label': 'Crisis Acute',
        'description': 'Active contagion, cascade risk, max defensive',
        'avg_stress_threshold': 0.80,
        'pct_stress_threshold': 0.50,
    },
    'MR_SYSTEMIC': {
        'label': 'Crisis Systemic',
        'description': 'Broad stress, cross-asset correlation spike',
        'avg_stress_threshold': 0.50,
        'pct_high_stress_threshold': 0.30,
    },
    'MR_SELECTIVE': {
        'label': 'Crisis Selective',
        'description': 'Sector-specific stress, some assets decoupling',
        'avg_stress_threshold': 0.20,
    },
    'MR_EXHAUSTION': {
        'label': 'Crisis Exhaustion',
        'description': 'Vol compression, potential bottom formation',
    },
}


def classify_micro_regime(
    sovereign_states: List[Dict],
    macro_state: Dict,
) -> Tuple[str, Dict]:
    """
    Classify the current CRISIS macro into a micro-regime.

    Args:
        sovereign_states: List of dicts with keys:
            - asset_id, sovereign_regime, stress_prob, bear_prob
        macro_state: Dict with keys:
            - current_regime, is_policy_divergent, transition_state,
              belief_regime, belief_confidence, regime_confidence

    Returns:
        (micro_regime_code, classification_details)
    """
    if not sovereign_states:
        return 'MR_SELECTIVE', {'reason': 'no_sovereign_data', 'assets_evaluated': 0}

    total = len(sovereign_states)
    stress_probs = [float(s.get('stress_prob', 0) or 0) for s in sovereign_states]
    avg_stress = sum(stress_probs) / total if total > 0 else 0.0

    stress_count = sum(1 for s in sovereign_states if s.get('sovereign_regime') == 'STRESS')
    bear_count = sum(1 for s in sovereign_states if s.get('sovereign_regime') == 'BEAR')
    neutral_count = sum(1 for s in sovereign_states if s.get('sovereign_regime') == 'NEUTRAL')
    bull_count = sum(1 for s in sovereign_states if s.get('sovereign_regime') == 'BULL')

    pct_stress = stress_count / total if total > 0 else 0.0
    high_stress_count = sum(1 for sp in stress_probs if sp > 0.60)
    pct_high_stress = high_stress_count / total if total > 0 else 0.0

    is_divergent = macro_state.get('is_policy_divergent', False)
    transition_state = macro_state.get('transition_state', '')

    details = {
        'total_assets_evaluated': total,
        'avg_stress_prob': round(avg_stress, 6),
        'pct_stress_assets': round(pct_stress, 4),
        'pct_high_stress_assets': round(pct_high_stress, 4),
        'assets_in_stress': stress_count,
        'assets_in_bear': bear_count,
        'assets_in_neutral': neutral_count,
        'assets_in_bull': bull_count,
        'is_policy_divergent': is_divergent,
        'transition_state': transition_state,
        'belief_regime': macro_state.get('belief_regime'),
        'belief_confidence': float(macro_state.get('belief_confidence', 0) or 0),
    }

    # Check exhaustion first (divergence signal with low stress)
    if is_divergent and transition_state == 'PENDING_CONFIRMATION':
        if avg_stress < 0.20:
            details['classification_reason'] = (
                f'Policy divergent + pending confirmation + avg_stress={avg_stress:.4f} < 0.20'
            )
            return 'MR_EXHAUSTION', details

    # Acute: overwhelming stress
    if avg_stress > 0.80 and pct_stress > 0.50:
        details['classification_reason'] = (
            f'avg_stress={avg_stress:.4f} > 0.80 AND pct_stress={pct_stress:.4f} > 0.50'
        )
        return 'MR_ACUTE', details

    # Systemic: broad elevated stress
    if avg_stress > 0.50 and pct_high_stress > 0.30:
        details['classification_reason'] = (
            f'avg_stress={avg_stress:.4f} > 0.50 AND pct_high_stress={pct_high_stress:.4f} > 0.30'
        )
        return 'MR_SYSTEMIC', details

    # Selective: localized stress
    if avg_stress > 0.20:
        details['classification_reason'] = (
            f'avg_stress={avg_stress:.4f} > 0.20 (selective stress)'
        )
        return 'MR_SELECTIVE', details

    # Exhaustion: stress fading
    details['classification_reason'] = (
        f'avg_stress={avg_stress:.4f} <= 0.20 (stress exhaustion)'
    )
    return 'MR_EXHAUSTION', details


def compute_momentum_vector(
    current_avg_stress: float,
    previous_avg_stress: Optional[float],
) -> str:
    """Determine if stress is improving, deteriorating, or stable."""
    if previous_avg_stress is None:
        return 'STABLE'
    delta = current_avg_stress - previous_avg_stress
    if abs(delta) < 0.02:
        return 'STABLE'
    return 'DETERIORATING' if delta > 0 else 'IMPROVING'


def compute_evidence_hash(classification: Dict) -> str:
    """SHA256 hash of the classification for ADR-013 compliance."""
    payload = json.dumps(classification, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def get_db_connection():
    """Connect to PostgreSQL 17.6 on port 54322."""
    try:
        import psycopg2
        return psycopg2.connect(
            host='127.0.0.1',
            port=54322,
            dbname='postgres',
            user='postgres',
        )
    except ImportError:
        print("ERROR: psycopg2 not installed. Install via: pip install psycopg2-binary")
        sys.exit(1)


def fetch_sovereign_states(conn) -> List[Dict]:
    """Fetch latest sovereign regime states from the database."""
    cur = conn.cursor()
    cur.execute("""
        SELECT asset_id, sovereign_regime,
               (state_probabilities->>'STRESS')::numeric as stress_prob,
               (state_probabilities->>'BEAR')::numeric as bear_prob,
               crio_dominant_driver
        FROM fhq_perception.sovereign_regime_state_v4
        WHERE timestamp = (SELECT MAX(timestamp) FROM fhq_perception.sovereign_regime_state_v4)
        ORDER BY asset_id
    """)
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    return [dict(zip(columns, row)) for row in rows]


def fetch_macro_state(conn) -> Dict:
    """Fetch current macro regime state."""
    cur = conn.cursor()
    cur.execute("""
        SELECT current_regime, regime_confidence, belief_regime, belief_confidence,
               is_policy_divergent, divergence_reason, transition_state
        FROM fhq_meta.regime_state
        ORDER BY last_updated_at DESC LIMIT 1
    """)
    columns = [desc[0] for desc in cur.description]
    row = cur.fetchone()
    cur.close()
    if row is None:
        return {}
    return dict(zip(columns, row))


def fetch_previous_classification(conn) -> Optional[Dict]:
    """Fetch the most recent micro-regime classification."""
    cur = conn.cursor()
    cur.execute("""
        SELECT micro_regime, avg_stress_prob, classified_at
        FROM fhq_learning.micro_regime_classifications
        ORDER BY classified_at DESC LIMIT 1
    """)
    row = cur.fetchone()
    cur.close()
    if row is None:
        return None
    return {
        'micro_regime': row[0],
        'avg_stress_prob': float(row[1]),
        'classified_at': row[2],
    }


def store_classification(conn, micro_regime: str, details: Dict,
                         previous: Optional[Dict], momentum: str,
                         evidence_hash: str):
    """Store classification result in the database."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO fhq_learning.micro_regime_classifications (
            macro_regime, micro_regime, avg_stress_prob, pct_stress_assets,
            pct_high_stress_assets, total_assets_evaluated, assets_in_stress,
            assets_in_bear, assets_in_neutral, assets_in_bull,
            is_policy_divergent, transition_state, belief_regime, belief_confidence,
            previous_micro_regime, regime_delta_intensity, momentum_vector,
            classified_by, evidence_hash
        ) VALUES (
            'CRISIS', %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """, (
        micro_regime,
        details['avg_stress_prob'],
        details['pct_stress_assets'],
        details['pct_high_stress_assets'],
        details['total_assets_evaluated'],
        details['assets_in_stress'],
        details['assets_in_bear'],
        details['assets_in_neutral'],
        details['assets_in_bull'],
        details['is_policy_divergent'],
        details.get('transition_state'),
        details.get('belief_regime'),
        details.get('belief_confidence'),
        previous['micro_regime'] if previous else None,
        abs(details['avg_stress_prob'] - previous['avg_stress_prob']) if previous else None,
        momentum,
        'micro_regime_classifier_v1.0',
        evidence_hash,
    ))
    conn.commit()
    cur.close()


def write_regime_delta(conn, micro_regime: str, previous: Optional[Dict],
                       details: Dict, momentum: str):
    """Write a MICRO_REGIME_SHIFT event to regime_delta if regime changed."""
    if previous is None or previous['micro_regime'] == micro_regime:
        return  # No shift

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO fhq_operational.regime_delta (
            listing_id, detected_at, timeframe, delta_type, intensity,
            momentum_vector, canonical_regime, regime_alignment,
            ttl_hours, expires_at, is_active, issuing_agent
        ) VALUES (
            'PORTFOLIO', NOW(), 'DAILY', 'MICRO_REGIME_SHIFT',
            %s, %s, 'CRISIS', true,
            24, NOW() + INTERVAL '24 hours', true,
            'micro_regime_classifier'
        )
    """, (
        abs(details['avg_stress_prob'] - previous['avg_stress_prob']),
        momentum,
    ))
    conn.commit()
    cur.close()


# =============================================================================
# CLI COMMANDS
# =============================================================================

def cmd_classify(args):
    """Run micro-regime classification against live database."""
    conn = get_db_connection()

    # Fetch data
    sovereign_states = fetch_sovereign_states(conn)
    macro_state = fetch_macro_state(conn)
    previous = fetch_previous_classification(conn)

    if macro_state.get('current_regime') != 'CRISIS':
        print(f"SKIP: Macro regime is {macro_state.get('current_regime')}, not CRISIS.")
        print("Micro-regime classification only applies under CRISIS macro.")
        conn.close()
        return

    # Classify
    micro_regime, details = classify_micro_regime(sovereign_states, macro_state)
    momentum = compute_momentum_vector(
        details['avg_stress_prob'],
        previous['avg_stress_prob'] if previous else None,
    )

    # Build evidence record
    evidence = {
        'directive': DIRECTIVE,
        'module_version': MODULE_VERSION,
        'classified_at': datetime.now(timezone.utc).isoformat(),
        'macro_regime': 'CRISIS',
        'micro_regime': micro_regime,
        'micro_regime_label': MICRO_REGIMES[micro_regime]['label'],
        'momentum_vector': momentum,
        'previous_micro_regime': previous['micro_regime'] if previous else None,
        'classification_details': details,
    }
    evidence_hash = compute_evidence_hash(evidence)
    evidence['evidence_hash'] = evidence_hash

    # Store
    if not args.dry_run:
        store_classification(conn, micro_regime, details, previous,
                             momentum, evidence_hash)
        write_regime_delta(conn, micro_regime, previous, details, momentum)
        print(f"Classification stored: {micro_regime}")
    else:
        print(f"DRY RUN — would store: {micro_regime}")

    # Output
    print(f"\n=== MICRO-REGIME CLASSIFICATION ===")
    print(f"Macro:          CRISIS (confidence {macro_state.get('regime_confidence')})")
    print(f"Micro-Regime:   {micro_regime} ({MICRO_REGIMES[micro_regime]['label']})")
    print(f"Momentum:       {momentum}")
    print(f"Avg Stress:     {details['avg_stress_prob']:.4f}")
    print(f"Assets Eval:    {details['total_assets_evaluated']}")
    print(f"  STRESS:       {details['assets_in_stress']}")
    print(f"  BEAR:         {details['assets_in_bear']}")
    print(f"  NEUTRAL:      {details['assets_in_neutral']}")
    print(f"  BULL:         {details['assets_in_bull']}")
    print(f"High-Stress:    {details['pct_high_stress_assets']:.1%}")
    print(f"Divergent:      {details['is_policy_divergent']}")
    print(f"Transition:     {details.get('transition_state')}")
    print(f"Reason:         {details.get('classification_reason')}")
    print(f"Evidence Hash:  {evidence_hash[:16]}...")
    if previous:
        print(f"Previous:       {previous['micro_regime']} ({previous['classified_at']})")

    conn.close()
    return evidence


def cmd_history(args):
    """Show classification history."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT micro_regime, avg_stress_prob, pct_stress_assets,
               momentum_vector, previous_micro_regime, classified_at
        FROM fhq_learning.micro_regime_classifications
        ORDER BY classified_at DESC
        LIMIT 20
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        print("No classification history found.")
        return

    print(f"{'Timestamp':<28} {'Micro-Regime':<16} {'Avg Stress':<12} {'Momentum':<14} {'Previous':<16}")
    print("-" * 90)
    for row in rows:
        print(f"{str(row[5]):<28} {row[0]:<16} {float(row[1]):<12.4f} {row[3] or '-':<14} {row[4] or '-':<16}")


def cmd_check(args):
    """Self-test: verify classification logic with known inputs."""
    print("=== SELF-TEST: micro_regime_classifier ===\n")
    tests_passed = 0
    tests_total = 0

    # Test 1: MR_ACUTE — need avg_stress > 0.80 AND pct_stress > 0.50
    tests_total += 1
    states = [{'sovereign_regime': 'STRESS', 'stress_prob': 0.95}] * 60 + \
             [{'sovereign_regime': 'BEAR', 'stress_prob': 0.60}] * 40
    # avg = (60*0.95 + 40*0.60)/100 = 0.81, pct_stress = 0.60
    macro = {'current_regime': 'CRISIS', 'is_policy_divergent': False, 'transition_state': None}
    result, _ = classify_micro_regime(states, macro)
    if result == 'MR_ACUTE':
        print(f"  [PASS] Test 1: MR_ACUTE — 60% STRESS, avg_stress=0.81")
        tests_passed += 1
    else:
        print(f"  [FAIL] Test 1: Expected MR_ACUTE, got {result}")

    # Test 2: MR_SYSTEMIC — need avg_stress > 0.50 AND pct_high_stress > 0.30
    tests_total += 1
    states = [{'sovereign_regime': 'STRESS', 'stress_prob': 0.95}] * 20 + \
             [{'sovereign_regime': 'BEAR', 'stress_prob': 0.70}] * 40 + \
             [{'sovereign_regime': 'NEUTRAL', 'stress_prob': 0.10}] * 40
    # avg = (20*0.95 + 40*0.70 + 40*0.10)/100 = 0.51, pct_high_stress = 60/100 = 0.60
    result, details = classify_micro_regime(states, macro)
    if result == 'MR_SYSTEMIC':
        print(f"  [PASS] Test 2: MR_SYSTEMIC — avg={details['avg_stress_prob']:.4f}, high_stress={details['pct_high_stress_assets']:.1%}")
        tests_passed += 1
    else:
        print(f"  [FAIL] Test 2: Expected MR_SYSTEMIC, got {result} (details: {details})")

    # Test 3: MR_SELECTIVE — need avg_stress 0.20-0.50, not matching SYSTEMIC
    tests_total += 1
    states = [{'sovereign_regime': 'STRESS', 'stress_prob': 0.90}] * 10 + \
             [{'sovereign_regime': 'BEAR', 'stress_prob': 0.35}] * 30 + \
             [{'sovereign_regime': 'NEUTRAL', 'stress_prob': 0.05}] * 60
    # avg = (10*0.90 + 30*0.35 + 60*0.05)/100 = 0.225, pct_high_stress = 10/100 = 0.10
    result, details = classify_micro_regime(states, macro)
    if result == 'MR_SELECTIVE':
        print(f"  [PASS] Test 3: MR_SELECTIVE — avg={details['avg_stress_prob']:.4f}")
        tests_passed += 1
    else:
        print(f"  [FAIL] Test 3: Expected MR_SELECTIVE, got {result} (details: {details})")

    # Test 4: MR_EXHAUSTION (low stress)
    tests_total += 1
    states = [{'sovereign_regime': 'BEAR', 'stress_prob': 0.10}] * 50 + \
             [{'sovereign_regime': 'NEUTRAL', 'stress_prob': 0.05}] * 50
    result, details = classify_micro_regime(states, macro)
    if result == 'MR_EXHAUSTION':
        print(f"  [PASS] Test 4: MR_EXHAUSTION — 0% STRESS, avg={details['avg_stress_prob']:.4f}")
        tests_passed += 1
    else:
        print(f"  [FAIL] Test 4: Expected MR_EXHAUSTION, got {result} (details: {details})")

    # Test 5: MR_EXHAUSTION (divergence)
    tests_total += 1
    states = [{'sovereign_regime': 'BEAR', 'stress_prob': 0.15}] * 80 + \
             [{'sovereign_regime': 'NEUTRAL', 'stress_prob': 0.05}] * 20
    macro_div = {
        'current_regime': 'CRISIS',
        'is_policy_divergent': True,
        'transition_state': 'PENDING_CONFIRMATION',
        'belief_regime': 'STRESS',
        'belief_confidence': 0.85,
    }
    result, details = classify_micro_regime(states, macro_div)
    if result == 'MR_EXHAUSTION':
        print(f"  [PASS] Test 5: MR_EXHAUSTION (divergent) — avg={details['avg_stress_prob']:.4f}")
        tests_passed += 1
    else:
        print(f"  [FAIL] Test 5: Expected MR_EXHAUSTION, got {result} (details: {details})")

    # Test 6: Momentum vector
    tests_total += 1
    m1 = compute_momentum_vector(0.45, 0.60)
    m2 = compute_momentum_vector(0.60, 0.45)
    m3 = compute_momentum_vector(0.45, 0.44)
    if m1 == 'IMPROVING' and m2 == 'DETERIORATING' and m3 == 'STABLE':
        print(f"  [PASS] Test 6: Momentum vector — IMPROVING/DETERIORATING/STABLE")
        tests_passed += 1
    else:
        print(f"  [FAIL] Test 6: Momentum — got {m1}/{m2}/{m3}")

    # Test 7: Evidence hash determinism
    tests_total += 1
    data = {'test': 'value', 'number': 42}
    h1 = compute_evidence_hash(data)
    h2 = compute_evidence_hash(data)
    if h1 == h2 and len(h1) == 64:
        print(f"  [PASS] Test 7: Evidence hash deterministic (SHA256)")
        tests_passed += 1
    else:
        print(f"  [FAIL] Test 7: Hash mismatch or wrong length")

    # Test 8: Governance assertions
    tests_total += 1
    assert EXECUTION_AUTHORITY == "NONE"
    assert CAPITAL_AUTHORITY == "ZERO"
    for mod in _FORBIDDEN_MODULES:
        assert mod not in sys.modules
    print(f"  [PASS] Test 8: Governance assertions intact")
    tests_passed += 1

    print(f"\nResult: {tests_passed}/{tests_total} passed")
    if tests_passed == tests_total:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
        sys.exit(1)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Micro-Regime Classifier — CEO-DIR-2026-OPS-MICROREGIME-003'
    )
    parser.add_argument('--classify', action='store_true',
                        help='Run classification against live database')
    parser.add_argument('--history', action='store_true',
                        help='Show classification history')
    parser.add_argument('--check', action='store_true',
                        help='Run self-tests')
    parser.add_argument('--dry-run', action='store_true',
                        help='Classify without storing results')

    args = parser.parse_args()

    if args.check:
        cmd_check(args)
    elif args.classify:
        cmd_classify(args)
    elif args.history:
        cmd_history(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
