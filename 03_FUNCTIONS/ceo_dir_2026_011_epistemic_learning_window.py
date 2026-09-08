#!/usr/bin/env python3
"""
CEO-DIR-2026-011: SIX-HOUR EPISTEMIC LEARNING WINDOW (SHADOW)
==============================================================
Classification: STRATEGIC-EPISTEMIC (CLASS A)
Authority: CEO
Status: DEFCON GREEN
Duration: 6 hours from issuance
Scope: SHADOW / PAPER ONLY

Purpose:
    Extract structure from divergence.
    Separate signal from noise.
    Convert activity into understanding.

Primary Objective:
    Maximize epistemic knowledge per unit time.

Constraints:
    - NO policy changes
    - NO hysteresis parameter tuning
    - NO adaptive feedback activation
    - NO manual intervention

    "Learning without restraint is noise. Restraint creates signal."

Required Measurements:
    4.1 Belief Dynamics
    4.2 Belief vs Policy Divergence
    4.3 Suppression Regret (Observed, Not Acted Upon)
    4.4 Stability vs Responsiveness
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

WINDOW_DURATION_HOURS = 6
MEASUREMENT_INTERVAL_SECONDS = 300  # 5 minutes
EVIDENCE_DIR = os.path.join(os.path.dirname(__file__), "evidence")

DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": os.getenv("PGPORT", "54322"),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres")
}

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("epistemic_learning_window")

# =============================================================================
# DATABASE
# =============================================================================

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# MEASUREMENT FUNCTIONS
# =============================================================================

def measure_belief_dynamics(conn) -> Dict[str, Any]:
    """
    4.1 Belief Dynamics
    - Belief confidence delta per asset
    - Entropy delta per asset
    - Changepoint frequency
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Current beliefs
        cur.execute("""
            SELECT
                asset_id,
                dominant_regime,
                belief_confidence,
                entropy,
                is_changepoint,
                belief_timestamp
            FROM fhq_perception.v_canonical_belief
        """)
        current_beliefs = {row['asset_id']: dict(row) for row in cur.fetchall()}

        # Changepoint frequency (last 6 hours)
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE is_changepoint = true) as changepoint_count,
                COUNT(*) as total_observations
            FROM fhq_perception.model_belief_state
            WHERE belief_timestamp > NOW() - INTERVAL '6 hours'
        """)
        changepoint_stats = cur.fetchone()

        # Average entropy
        cur.execute("""
            SELECT
                AVG(entropy) as avg_entropy,
                MIN(entropy) as min_entropy,
                MAX(entropy) as max_entropy,
                STDDEV(entropy) as stddev_entropy
            FROM fhq_perception.v_canonical_belief
        """)
        entropy_stats = cur.fetchone()

        return {
            'current_beliefs': current_beliefs,
            'changepoint_frequency': {
                'count': changepoint_stats['changepoint_count'] if changepoint_stats else 0,
                'total': changepoint_stats['total_observations'] if changepoint_stats else 0,
                'rate': round(changepoint_stats['changepoint_count'] / max(changepoint_stats['total_observations'], 1), 4) if changepoint_stats else 0
            },
            'entropy_stats': {
                'avg': float(entropy_stats['avg_entropy']) if entropy_stats and entropy_stats['avg_entropy'] else 0,
                'min': float(entropy_stats['min_entropy']) if entropy_stats and entropy_stats['min_entropy'] else 0,
                'max': float(entropy_stats['max_entropy']) if entropy_stats and entropy_stats['max_entropy'] else 0,
                'stddev': float(entropy_stats['stddev_entropy']) if entropy_stats and entropy_stats['stddev_entropy'] else 0
            }
        }


def measure_belief_policy_divergence(conn) -> Dict[str, Any]:
    """
    4.2 Belief vs Policy Divergence
    - Count of suppressed beliefs
    - Average suppressed confidence
    - Duration of suppression states
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Current divergence state
        cur.execute("""
            SELECT
                COUNT(*) as total_assets,
                COUNT(*) FILTER (WHERE is_suppressed = true) as suppressed_count,
                AVG(belief_conf) FILTER (WHERE is_suppressed = true) as avg_suppressed_confidence,
                COUNT(*) FILTER (WHERE policy_regime != belief_regime) as divergent_count
            FROM fhq_perception.v_canonical_policy
        """)
        divergence_stats = cur.fetchone()

        # Suppressed assets detail
        cur.execute("""
            SELECT
                asset_id,
                belief_regime,
                policy_regime,
                belief_conf as belief_confidence,
                policy_confidence,
                suppression_reason,
                transition_state
            FROM fhq_perception.v_canonical_policy
            WHERE is_suppressed = true
        """)
        suppressed_assets = [dict(row) for row in cur.fetchall()]

        # Transition state distribution
        cur.execute("""
            SELECT
                transition_state,
                COUNT(*) as count
            FROM fhq_perception.v_canonical_policy
            GROUP BY transition_state
        """)
        transition_distribution = {row['transition_state']: row['count'] for row in cur.fetchall()}

        return {
            'total_assets': divergence_stats['total_assets'] if divergence_stats else 0,
            'suppressed_count': divergence_stats['suppressed_count'] if divergence_stats else 0,
            'avg_suppressed_confidence': float(divergence_stats['avg_suppressed_confidence']) if divergence_stats and divergence_stats['avg_suppressed_confidence'] else 0,
            'divergent_count': divergence_stats['divergent_count'] if divergence_stats else 0,
            'suppressed_assets': suppressed_assets,
            'transition_distribution': transition_distribution
        }


def measure_suppression_regret(conn) -> Dict[str, Any]:
    """
    4.3 Suppression Regret (Observed, Not Acted Upon)
    - Estimated alpha foregone due to hysteresis
    - Classification: Wisdom vs Regret
    - Asset-level breakdown

    Regret = When suppressed belief would have been correct
    Wisdom = When suppression prevented a false signal
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get suppression ledger summary
        cur.execute("""
            SELECT
                suppression_category,
                COUNT(*) as count,
                AVG(suppressed_confidence) as avg_confidence,
                SUM(COALESCE(opportunity_cost_realized, 0)) as total_realized_cost,
                COUNT(*) FILTER (WHERE lesson_extracted IS NOT NULL) as lessons_extracted
            FROM fhq_governance.epistemic_suppression_ledger
            WHERE suppression_timestamp > NOW() - INTERVAL '6 hours'
            GROUP BY suppression_category
        """)
        suppression_summary = [dict(row) for row in cur.fetchall()]

        # Calculate theoretical regret for currently suppressed assets
        # Regret = suppressed confidence * (1 - policy confidence)
        cur.execute("""
            SELECT
                asset_id,
                belief_regime,
                policy_regime,
                belief_conf as belief_confidence,
                policy_confidence,
                (belief_conf - policy_confidence) as confidence_gap,
                suppression_reason
            FROM fhq_perception.v_canonical_policy
            WHERE is_suppressed = true
            ORDER BY (belief_conf - policy_confidence) DESC
        """)
        regret_candidates = [dict(row) for row in cur.fetchall()]

        # Compute aggregate regret metrics
        total_confidence_gap = sum(float(r['confidence_gap'] or 0) for r in regret_candidates)
        avg_confidence_gap = total_confidence_gap / max(len(regret_candidates), 1)

        return {
            'suppression_summary': suppression_summary,
            'regret_candidates': regret_candidates,
            'aggregate_metrics': {
                'total_confidence_gap': round(total_confidence_gap, 4),
                'avg_confidence_gap': round(avg_confidence_gap, 4),
                'suppressed_asset_count': len(regret_candidates)
            },
            'classification_pending': 'Requires market outcome data for Wisdom vs Regret classification'
        }


def measure_stability_responsiveness(conn) -> Dict[str, Any]:
    """
    4.4 Stability vs Responsiveness
    - Assets transitioning from PENDING → STABLE
    - Assets oscillating (early warning of noise sensitivity)
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Current transition states
        cur.execute("""
            SELECT
                asset_id,
                transition_state,
                consecutive_confirms,
                confirms_required,
                pending_regime
            FROM fhq_perception.v_canonical_policy
            WHERE transition_state != 'STABLE'
        """)
        pending_assets = [dict(row) for row in cur.fetchall()]

        # Count by transition state
        cur.execute("""
            SELECT
                transition_state,
                COUNT(*) as count
            FROM fhq_perception.v_canonical_policy
            GROUP BY transition_state
        """)
        state_counts = {row['transition_state']: row['count'] for row in cur.fetchall()}

        # Stability ratio
        total = sum(state_counts.values())
        stable = state_counts.get('STABLE', 0)
        stability_ratio = stable / max(total, 1)

        return {
            'state_distribution': state_counts,
            'stability_ratio': round(stability_ratio, 4),
            'pending_assets': pending_assets,
            'pending_count': len(pending_assets),
            'oscillation_warning': len(pending_assets) > total * 0.5
        }


def compute_measurement_hash(measurements: Dict) -> str:
    """Compute hash for measurement integrity"""
    content = json.dumps(measurements, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()


def capture_snapshot(conn, snapshot_number: int, window_start: datetime) -> Dict[str, Any]:
    """Capture a complete measurement snapshot"""
    timestamp = datetime.now(timezone.utc)
    elapsed = (timestamp - window_start).total_seconds() / 3600  # hours

    snapshot = {
        'snapshot_id': f"LEARN-{window_start.strftime('%Y%m%d%H%M')}-{snapshot_number:04d}",
        'timestamp': timestamp.isoformat(),
        'elapsed_hours': round(elapsed, 3),
        'window_start': window_start.isoformat(),
        'directive': 'CEO-DIR-2026-011',
        'measurements': {
            'belief_dynamics': measure_belief_dynamics(conn),
            'divergence': measure_belief_policy_divergence(conn),
            'suppression_regret': measure_suppression_regret(conn),
            'stability': measure_stability_responsiveness(conn)
        }
    }

    # Compute lineage hash
    snapshot['lineage_hash'] = compute_measurement_hash(snapshot['measurements'])

    return snapshot


def log_to_governance(conn, snapshot: Dict) -> None:
    """Log snapshot to governance actions log"""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_type,
                action_target,
                action_target_type,
                initiated_by,
                decision,
                decision_rationale,
                metadata
            ) VALUES (
                'EPISTEMIC_LEARNING_SNAPSHOT',
                %s,
                'MEASUREMENT',
                'CEO',
                'OBSERVED',
                'CEO-DIR-2026-011: 6-hour epistemic learning window',
                %s
            )
        """, (
            snapshot['snapshot_id'],
            json.dumps({
                'snapshot_id': snapshot['snapshot_id'],
                'elapsed_hours': snapshot['elapsed_hours'],
                'lineage_hash': snapshot['lineage_hash'],
                'suppressed_count': snapshot['measurements']['divergence']['suppressed_count'],
                'stability_ratio': snapshot['measurements']['stability']['stability_ratio'],
                'avg_entropy': snapshot['measurements']['belief_dynamics']['entropy_stats']['avg']
            }, default=str)
        ))
        conn.commit()


def save_evidence(snapshot: Dict) -> str:
    """Save snapshot to evidence directory"""
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    filename = f"EPISTEMIC_LEARNING_{snapshot['snapshot_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(EVIDENCE_DIR, filename)

    with open(filepath, 'w') as f:
        json.dump(snapshot, f, indent=2, default=str)

    return filepath


def run_learning_window() -> Dict[str, Any]:
    """
    Execute the 6-hour epistemic learning window.

    "We do not learn by acting. We learn by watching ourselves hesitate."
    """
    window_start = datetime.now(timezone.utc)
    window_end = window_start + timedelta(hours=WINDOW_DURATION_HOURS)

    logger.info("=" * 70)
    logger.info("CEO-DIR-2026-011: EPISTEMIC LEARNING WINDOW")
    logger.info("=" * 70)
    logger.info(f"Window Start: {window_start.isoformat()}")
    logger.info(f"Window End:   {window_end.isoformat()}")
    logger.info(f"Duration:     {WINDOW_DURATION_HOURS} hours")
    logger.info(f"Measurement Interval: {MEASUREMENT_INTERVAL_SECONDS} seconds")
    logger.info("")
    logger.info("Constraints Active:")
    logger.info("  - NO policy changes")
    logger.info("  - NO hysteresis tuning")
    logger.info("  - NO adaptive feedback")
    logger.info("  - NO manual intervention")
    logger.info("")
    logger.info("\"Learning without restraint is noise. Restraint creates signal.\"")
    logger.info("=" * 70)

    results = {
        'directive': 'CEO-DIR-2026-011',
        'window_start': window_start.isoformat(),
        'window_end': window_end.isoformat(),
        'status': 'IN_PROGRESS',
        'snapshots': [],
        'evidence_files': []
    }

    snapshot_number = 0

    try:
        conn = get_db_connection()

        # Initial snapshot
        logger.info("\n[SNAPSHOT #0000] Capturing initial state...")
        initial_snapshot = capture_snapshot(conn, snapshot_number, window_start)
        results['initial_state'] = initial_snapshot
        log_to_governance(conn, initial_snapshot)
        evidence_path = save_evidence(initial_snapshot)
        results['evidence_files'].append(evidence_path)

        logger.info(f"  Suppressed: {initial_snapshot['measurements']['divergence']['suppressed_count']}")
        logger.info(f"  Stability:  {initial_snapshot['measurements']['stability']['stability_ratio']:.2%}")
        logger.info(f"  Avg Entropy: {initial_snapshot['measurements']['belief_dynamics']['entropy_stats']['avg']:.4f}")
        logger.info(f"  Evidence: {evidence_path}")

        # Continuous measurement loop
        import time
        while datetime.now(timezone.utc) < window_end:
            time.sleep(MEASUREMENT_INTERVAL_SECONDS)
            snapshot_number += 1

            logger.info(f"\n[SNAPSHOT #{snapshot_number:04d}] Capturing measurement...")

            try:
                snapshot = capture_snapshot(conn, snapshot_number, window_start)
                results['snapshots'].append(snapshot['snapshot_id'])
                log_to_governance(conn, snapshot)
                evidence_path = save_evidence(snapshot)
                results['evidence_files'].append(evidence_path)

                # Log key metrics
                div = snapshot['measurements']['divergence']
                stab = snapshot['measurements']['stability']
                belief = snapshot['measurements']['belief_dynamics']

                logger.info(f"  Elapsed: {snapshot['elapsed_hours']:.2f}h")
                logger.info(f"  Suppressed: {div['suppressed_count']} | Stability: {stab['stability_ratio']:.2%}")
                logger.info(f"  Entropy: avg={belief['entropy_stats']['avg']:.4f}, stddev={belief['entropy_stats']['stddev']:.4f}")
                logger.info(f"  Hash: {snapshot['lineage_hash'][:16]}...")

            except Exception as e:
                logger.error(f"  Snapshot failed: {e}")
                conn.rollback()

        # Final snapshot
        snapshot_number += 1
        logger.info(f"\n[SNAPSHOT #{snapshot_number:04d}] Capturing final state...")
        final_snapshot = capture_snapshot(conn, snapshot_number, window_start)
        results['final_state'] = final_snapshot
        log_to_governance(conn, final_snapshot)
        evidence_path = save_evidence(final_snapshot)
        results['evidence_files'].append(evidence_path)

        results['status'] = 'COMPLETED'
        results['total_snapshots'] = snapshot_number + 1

        # Compute deltas
        if results.get('initial_state') and results.get('final_state'):
            initial_div = results['initial_state']['measurements']['divergence']
            final_div = results['final_state']['measurements']['divergence']

            results['learning_summary'] = {
                'suppression_delta': final_div['suppressed_count'] - initial_div['suppressed_count'],
                'stability_delta': results['final_state']['measurements']['stability']['stability_ratio'] -
                                   results['initial_state']['measurements']['stability']['stability_ratio'],
                'entropy_delta': results['final_state']['measurements']['belief_dynamics']['entropy_stats']['avg'] -
                                 results['initial_state']['measurements']['belief_dynamics']['entropy_stats']['avg']
            }

        conn.close()

    except Exception as e:
        logger.error(f"Learning window failed: {e}")
        results['status'] = 'FAILED'
        results['error'] = str(e)

    logger.info("")
    logger.info("=" * 70)
    logger.info(f"LEARNING WINDOW {results['status']}")
    logger.info(f"Total Snapshots: {results.get('total_snapshots', 0)}")
    logger.info("=" * 70)

    return results


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    result = run_learning_window()
    print(json.dumps(result, indent=2, default=str))
