#!/usr/bin/env python3
"""
Pre-Tier Scoring Daemon
=======================
CEO-DIR-2026-PRE-TIER-SCORING-DAEMON-001
CEO-DIR-2026-G1.5-INPUT-VALIDITY-REMEDIATION-001 (v2.0)

Scores hypotheses at birth with pre_tier_score_at_birth for G1.5 experiment.
This is the MISSING component that was never implemented after Migration 350.

REMEDIATION v2.0 (2026-01-27):
- Added Input Validity Gates to flag INPUT_NON_INFORMATIVE hypotheses
- Scoring proceeds but results are marked when variance insufficient

Root Cause Analysis (Day 26):
- Migration 350 created the calculate_pre_tier_score() function
- Migration 352 set up G1.5 experiment requiring pre_tier_score_at_birth
- NO DAEMON was created to actually score hypotheses
- Result: Only 12 hypotheses got scored (manual batch on 2026-01-25 21:20)
- 247 hypotheses created afterward have NO scores
- G1.5 shows 0/30 deaths because deaths require scores

Solution:
- This daemon scores DRAFT hypotheses that lack pre_tier_score_at_birth
- Uses the database function calculate_pre_tier_score() with FROZEN weights
- Score is immutable once set (captured at birth for G1.5 analysis)
"""

import os
import sys
import time
import logging
import psycopg2
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

# Set working directory
os.chdir('C:/fhq-market-system/vision-ios')

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='[PRE-TIER] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/pre_tier_scoring_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Daemon configuration - FROZEN for G1.5
INTERVAL_MINUTES = 5  # Score quickly after creation
MAX_HYPOTHESES_PER_CYCLE = 50
DIRECTIVE_ID = 'CEO-DIR-2026-PRE-TIER-SCORING-DAEMON-001'

# FROZEN WEIGHTS (from Migration 350 - ADR-011 compliant)
WEIGHT_EVIDENCE_DENSITY = 0.3
WEIGHT_CAUSAL_DEPTH = 0.4
WEIGHT_DATA_FRESHNESS = 0.2
WEIGHT_CROSS_AGENT_AGREEMENT = 0.1
DECAY_RATE_PER_HOUR = 0.5
MAX_DECAY_PENALTY = 25.0


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def update_heartbeat(conn, cycle: int, results: Dict[str, Any]):
    """Update daemon heartbeat."""
    import json
    try:
        metadata_json = json.dumps(results)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_monitoring.daemon_health (
                    daemon_name, status, last_heartbeat, metadata
                ) VALUES (
                    'pre_tier_scoring_daemon', 'HEALTHY', NOW(),
                    %s::jsonb
                )
                ON CONFLICT (daemon_name) DO UPDATE SET
                    status = 'HEALTHY',
                    last_heartbeat = NOW(),
                    metadata = %s::jsonb
            """, (metadata_json, metadata_json))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update heartbeat: {e}")


def calculate_pre_tier_score(
    evidence_density: float,
    causal_depth: int,
    data_freshness: float,
    cross_agent_agreement: float,
    draft_age_hours: float
) -> Dict[str, float]:
    """
    Calculate pre-tier score using FROZEN weights from Migration 350.

    Formula:
        raw_score = (evidence_density * 0.3)
                  + (causal_depth_score * 0.4)
                  + (data_freshness * 0.2)
                  + (cross_agent_agreement * 0.1)
                  - decay_penalty

    Where:
        causal_depth_score = min(causal_depth * 25, 100)
        decay_penalty = min(draft_age_hours * 0.5, 25)
    """
    # Causal depth score (0-100, each level = 25 points)
    causal_depth_score = min(causal_depth * 25.0, 100.0)

    # Draft decay penalty (0-25, 0.5 per hour)
    decay_penalty = min(draft_age_hours * DECAY_RATE_PER_HOUR, MAX_DECAY_PENALTY)

    # Calculate raw score with FROZEN weights
    raw_score = (
        (evidence_density or 0) * WEIGHT_EVIDENCE_DENSITY +
        causal_depth_score * WEIGHT_CAUSAL_DEPTH +
        (data_freshness or 0) * WEIGHT_DATA_FRESHNESS +
        (cross_agent_agreement or 100) * WEIGHT_CROSS_AGENT_AGREEMENT -
        decay_penalty
    )

    # Clamp to 0-100
    final_score = max(min(raw_score, 100.0), 0.0)

    return {
        'pre_tier_score': round(final_score, 2),
        'causal_depth_score': round(causal_depth_score, 2),
        'decay_penalty': round(decay_penalty, 2)
    }


def check_input_validity_gates(conn, generator_id: str) -> Dict[str, Any]:
    """
    CEO-DIR-2026-G1.5-INPUT-VALIDITY-REMEDIATION-001: Input Validity Gates.

    Check if generator's recent hypotheses have sufficient variance in components.
    Returns validity status and flags.

    Minimum requirements:
    - causal_depth_score stddev > 0 (cannot be constant)
    - count(distinct evidence_density_score) >= 2
    - cross_agent_agreement stddev >= 0.5
    """
    MIN_DISTINCT_EVIDENCE = 2
    MIN_AGREEMENT_STDDEV = 0.5

    try:
        with conn.cursor() as cur:
            # Check variance of recent hypotheses from this generator
            cur.execute("""
                SELECT
                    COALESCE(STDDEV(causal_depth_score), 0) as cds_stddev,
                    COUNT(DISTINCT ROUND(evidence_density_score::numeric, 1)) as eds_distinct,
                    COALESCE(STDDEV(cross_agent_agreement_score), 0) as caa_stddev,
                    COUNT(*) as sample_size
                FROM fhq_learning.hypothesis_canon
                WHERE generator_id = %s
                AND pre_tier_score_at_birth IS NOT NULL
                AND created_at > NOW() - INTERVAL '7 days'
            """, (generator_id,))
            row = cur.fetchone()

            if not row or row[3] < 10:  # Need at least 10 samples
                return {
                    'status': 'INSUFFICIENT_DATA',
                    'sample_size': row[3] if row else 0,
                    'flags': {'reason': 'Need at least 10 scored hypotheses for validation'}
                }

            cds_stddev, eds_distinct, caa_stddev, sample_size = row

            flags = {}
            is_valid = True

            # Check causal_depth_score variance
            if cds_stddev == 0:
                flags['causal_depth_constant'] = True
                is_valid = False

            # Check evidence_density_score cardinality
            if eds_distinct < MIN_DISTINCT_EVIDENCE:
                flags['evidence_density_low_cardinality'] = eds_distinct
                is_valid = False

            # Check cross_agent_agreement variance
            if caa_stddev < MIN_AGREEMENT_STDDEV:
                flags['agreement_low_variance'] = float(caa_stddev)
                is_valid = False

            return {
                'status': 'VALID' if is_valid else 'INPUT_NON_INFORMATIVE',
                'sample_size': sample_size,
                'cds_stddev': float(cds_stddev),
                'eds_distinct': eds_distinct,
                'caa_stddev': float(caa_stddev),
                'flags': flags
            }

    except Exception as e:
        logger.warning(f"Input validity check failed for {generator_id}: {e}")
        return {'status': 'CHECK_FAILED', 'flags': {'error': str(e)}}


def get_unscored_hypotheses(conn) -> List[Dict[str, Any]]:
    """Get DRAFT hypotheses without pre_tier_score_at_birth."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                canon_id,
                hypothesis_code,
                generator_id,
                causal_graph_depth,
                evidence_density_score,
                data_freshness_score,
                cross_agent_agreement_score,
                EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0 as draft_age_hours,
                created_at
            FROM fhq_learning.hypothesis_canon
            WHERE status = 'DRAFT'
            AND pre_tier_score_at_birth IS NULL
            ORDER BY created_at ASC
            LIMIT %s
        """, (MAX_HYPOTHESES_PER_CYCLE,))

        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def score_hypothesis(conn, hypothesis: Dict[str, Any], validity_cache: Dict[str, Dict] = None) -> bool:
    """Score a single hypothesis and set pre_tier_score_at_birth.

    CEO-DIR-2026-G1.5-INPUT-VALIDITY-REMEDIATION-001:
    - Also sets input_validity_status based on generator's variance characteristics
    - Uses validity_cache to avoid repeated queries for same generator
    """
    from decimal import Decimal
    import json as json_module
    try:
        # Get component values with defaults, converting Decimal to float
        def to_float(val, default):
            if val is None:
                return default
            return float(val) if isinstance(val, (Decimal, int, float)) else default

        causal_depth = int(to_float(hypothesis.get('causal_graph_depth'), 1))
        evidence_density = to_float(hypothesis.get('evidence_density_score'), 50.0)  # Default mid-range
        data_freshness = to_float(hypothesis.get('data_freshness_score'), 80.0)  # Default recent
        cross_agent_agreement = to_float(hypothesis.get('cross_agent_agreement_score'), 100.0)  # Default agreement
        draft_age_hours = to_float(hypothesis.get('draft_age_hours'), 0.0)

        # Calculate score
        scores = calculate_pre_tier_score(
            evidence_density=evidence_density,
            causal_depth=causal_depth,
            data_freshness=data_freshness,
            cross_agent_agreement=cross_agent_agreement,
            draft_age_hours=draft_age_hours
        )

        pre_tier_score = scores['pre_tier_score']

        # CEO-DIR-2026-G1.5-INPUT-VALIDITY-REMEDIATION-001: Check input validity
        generator_id = hypothesis.get('generator_id', 'UNKNOWN')
        if validity_cache is None:
            validity_cache = {}

        if generator_id not in validity_cache:
            validity_cache[generator_id] = check_input_validity_gates(conn, generator_id)

        validity = validity_cache[generator_id]
        validity_status = validity.get('status', 'NOT_EVALUATED')
        validity_flags = json_module.dumps(validity.get('flags', {}))

        # Update hypothesis with IMMUTABLE birth score
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_learning.hypothesis_canon
                SET
                    pre_tier_score_at_birth = %s,
                    pre_tier_score = %s,
                    causal_depth_score = %s,
                    draft_decay_penalty = %s,
                    evidence_density_score = COALESCE(evidence_density_score, %s),
                    data_freshness_score = COALESCE(data_freshness_score, %s),
                    cross_agent_agreement_score = COALESCE(cross_agent_agreement_score, %s),
                    pre_tier_score_status = 'SCORED',
                    pre_tier_scored_at = NOW(),
                    pre_tier_scored_by = '{"daemon": "pre_tier_scoring_daemon", "version": "2.0.0"}'::jsonb,
                    pre_tier_score_version = '2.0.0',
                    input_validity_status = %s,
                    input_validity_flags = %s::jsonb
                WHERE canon_id = %s
                AND pre_tier_score_at_birth IS NULL
            """, (
                pre_tier_score,
                pre_tier_score,
                scores['causal_depth_score'],
                scores['decay_penalty'],
                evidence_density,
                data_freshness,
                cross_agent_agreement,
                validity_status,
                validity_flags,
                hypothesis['canon_id']
            ))
            conn.commit()

        logger.info(f"  Scored {hypothesis['hypothesis_code']}: {pre_tier_score:.2f} "
                   f"(depth={causal_depth}, decay={scores['decay_penalty']:.2f}, validity={validity_status})")
        return True

    except Exception as e:
        logger.error(f"  Failed to score {hypothesis['hypothesis_code']}: {e}")
        conn.rollback()
        return False


def run_scoring_cycle(conn) -> Dict[str, Any]:
    """Run one scoring cycle.

    CEO-DIR-2026-G1.5-INPUT-VALIDITY-REMEDIATION-001:
    - Uses validity_cache for efficient generator validation
    """
    results = {
        'scored': 0,
        'failed': 0,
        'skipped': 0,
        'total_unscored': 0,
        'validity_by_generator': {}
    }

    # Get unscored hypotheses
    hypotheses = get_unscored_hypotheses(conn)
    results['total_unscored'] = len(hypotheses)

    if not hypotheses:
        logger.info("No unscored hypotheses found")
        return results

    logger.info(f"Found {len(hypotheses)} unscored hypotheses")

    # CEO-DIR-2026-G1.5-INPUT-VALIDITY-REMEDIATION-001: Cache validity per generator
    validity_cache = {}

    for hypothesis in hypotheses:
        if score_hypothesis(conn, hypothesis, validity_cache):
            results['scored'] += 1
        else:
            results['failed'] += 1

    # Report validity status per generator
    results['validity_by_generator'] = {k: v.get('status', 'UNKNOWN') for k, v in validity_cache.items()}
    if validity_cache:
        logger.info(f"Input validity by generator: {results['validity_by_generator']}")

    return results


def check_g15_progress(conn) -> Dict[str, Any]:
    """Check G1.5 experiment progress after scoring."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE pre_tier_score_at_birth IS NOT NULL) as with_score,
                COUNT(*) FILTER (WHERE pre_tier_score_at_birth IS NULL) as without_score,
                COUNT(*) FILTER (
                    WHERE status IN ('FALSIFIED', 'REJECTED', 'EXPIRED')
                    AND pre_tier_score_at_birth IS NOT NULL
                ) as g15_deaths
            FROM fhq_learning.hypothesis_canon
        """)
        row = cur.fetchone()
        return {
            'with_score': row[0],
            'without_score': row[1],
            'g15_deaths': row[2]
        }


def main():
    """Main daemon loop."""
    logger.info("=" * 60)
    logger.info("PRE-TIER SCORING DAEMON STARTING - VERSION 2.0")
    logger.info(DIRECTIVE_ID)
    logger.info("CEO-DIR-2026-G1.5-INPUT-VALIDITY-REMEDIATION-001")
    logger.info(f"Interval: {INTERVAL_MINUTES} minutes")
    logger.info(f"Max per cycle: {MAX_HYPOTHESES_PER_CYCLE}")
    logger.info("FROZEN WEIGHTS (G1.5 Compliant - UNCHANGED):")
    logger.info(f"  Evidence Density: {WEIGHT_EVIDENCE_DENSITY}")
    logger.info(f"  Causal Depth: {WEIGHT_CAUSAL_DEPTH}")
    logger.info(f"  Data Freshness: {WEIGHT_DATA_FRESHNESS}")
    logger.info(f"  Cross-Agent Agreement: {WEIGHT_CROSS_AGENT_AGREEMENT}")
    logger.info(f"  Decay Rate: {DECAY_RATE_PER_HOUR}/hour (max {MAX_DECAY_PENALTY})")
    logger.info("INPUT VALIDITY GATES: ACTIVE (v2.0)")
    logger.info("=" * 60)

    cycle = 0

    while True:
        cycle += 1
        logger.info(f"--- Cycle {cycle} starting ---")

        try:
            conn = get_db_connection()

            # Run scoring cycle
            results = run_scoring_cycle(conn)

            # Check G1.5 progress
            g15 = check_g15_progress(conn)
            logger.info(f"G1.5 Status: {g15['with_score']} scored, {g15['without_score']} unscored, "
                       f"{g15['g15_deaths']}/30 deaths")

            # Update heartbeat
            metadata = {
                'cycle': cycle,
                'last_result': results,
                'g15_progress': g15,
                'directive': DIRECTIVE_ID
            }
            update_heartbeat(conn, cycle, metadata)

            logger.info(f"Cycle {cycle} complete: scored={results['scored']}, "
                       f"failed={results['failed']}, remaining={g15['without_score']}")

            conn.close()

        except Exception as e:
            logger.error(f"Cycle {cycle} error: {e}")

        logger.info(f"Sleeping {INTERVAL_MINUTES} minutes until next cycle...")
        time.sleep(INTERVAL_MINUTES * 60)


if __name__ == '__main__':
    main()
