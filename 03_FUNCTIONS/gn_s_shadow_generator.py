#!/usr/bin/env python3
"""
GN-S Shadow Discovery Generator
CEO-DIR-2026-POR-001: Multi-Generator Research Portfolio

Generator C: GN-S (Golden Needles Shadow Feed)
Purpose: Orthogonal discovery and Symmetry Watch benchmark
Constraints: Shadow-tier only, no reward, no execution eligibility
"""

import os
import sys
import json
import hashlib
import logging
import argparse
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

DAEMON_NAME = 'gn_s_shadow_generator'
CYCLE_INTERVAL_SECONDS = 21600  # 6h

logging.basicConfig(
    level=logging.INFO,
    format='[GN_S_DAEMON] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/gn_s_shadow_generator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 54322,
    'database': 'postgres',
    'user': 'postgres'
}

GENERATOR_ID = 'GN-S'
MIN_CAUSAL_DEPTH = 2

# Golden Needle category to mechanism chain mapping
NEEDLE_MECHANISMS = {
    'REGIME_EDGE': {
        'causal_chain': [
            'Regime transition signal detected',
            'Cross-asset correlations begin shifting',
            'Momentum factors reverse direction',
            'New regime establishes with different factor loadings'
        ],
        'behavioral_basis': 'Regime changes create temporary inefficiencies as models recalibrate',
        'regime_validity': ['TRANSITION', 'RISK_OFF', 'RISK_ON'],
        'assets': ['SPY', 'TLT', 'GLD', 'VXX']
    },
    'TIMING': {
        'causal_chain': [
            'Calendar effect or event timing identified',
            'Institutional flows concentrate around timing',
            'Price impact manifests in predictable window'
        ],
        'behavioral_basis': 'Calendar effects persist due to institutional constraints',
        'regime_validity': ['EXPANSION', 'RISK_ON'],
        'assets': ['SPY', 'QQQ']
    },
    'CROSS_ASSET': {
        'causal_chain': [
            'Cross-asset divergence exceeds historical norm',
            'Arbitrage forces begin correction',
            'Convergence creates directional opportunity'
        ],
        'behavioral_basis': 'Cross-asset relationships mean-revert over medium term',
        'regime_validity': ['EXPANSION', 'CONTRACTION'],
        'assets': ['SPY', 'TLT', 'GLD', 'DXY']
    },
    'MEAN_REVERSION': {
        'causal_chain': [
            'Price deviates significantly from fundamental value',
            'Value investors accumulate positions',
            'Price reverts toward fair value'
        ],
        'behavioral_basis': 'Overreaction creates mean-reversion opportunities',
        'regime_validity': ['RISK_OFF', 'TRANSITION'],
        'assets': ['SPY', 'IWM']
    },
    'VOLATILITY': {
        'causal_chain': [
            'Volatility regime shift detected',
            'Options market reprices risk',
            'Volatility term structure adjusts',
            'Equity returns impacted by vol regime'
        ],
        'behavioral_basis': 'Volatility clustering creates predictable vol regimes',
        'regime_validity': ['RISK_OFF', 'TRANSITION', 'CONTRACTION'],
        'assets': ['SPY', 'VXX', 'UVXY']
    }
}


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def compute_input_hash(needles: List[Dict]) -> str:
    """Compute hash of input artifacts for provenance."""
    content = json.dumps([str(n['needle_id']) for n in needles], sort_keys=True)
    return hashlib.md5(content.encode()).hexdigest()


def get_recent_golden_needles(conn, limit: int = 10) -> List[Dict]:
    """Get recent Golden Needles for shadow hypothesis generation."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
            needle_id,
            hypothesis_category,
            hypothesis_title,
            hypothesis_statement,
            executive_summary,
            eqs_score,
            confluence_factor_count,
            target_asset,
            regime_technical,
            falsification_criteria,
            created_at
        FROM fhq_canonical.golden_needles
        WHERE created_at >= NOW() - INTERVAL '30 days'
          AND is_current = TRUE
        ORDER BY eqs_score DESC, created_at DESC
        LIMIT %s
    """, (limit,))
    return cur.fetchall()


def get_next_hypothesis_code(conn) -> str:
    """Get next hypothesis code."""
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(MAX(CAST(SUBSTRING(hypothesis_code FROM 10) AS INTEGER)), 0) + 1
        FROM fhq_learning.hypothesis_canon
        WHERE hypothesis_code LIKE 'HYP-2026-%'
    """)
    next_num = cur.fetchone()[0]
    return f"HYP-2026-{next_num:04d}"


def build_mechanism_graph(category: str, needle: Dict) -> Dict:
    """Build N-tier mechanism graph from Golden Needle."""
    chain_template = NEEDLE_MECHANISMS.get(category, NEEDLE_MECHANISMS['REGIME_EDGE'])

    return {
        'nodes': [
            {'tier': i+1, 'mechanism': step, 'evidence_required': True}
            for i, step in enumerate(chain_template['causal_chain'])
        ],
        'root_driver': f"Golden Needle: {needle['hypothesis_title']}",
        'terminal_outcome': needle.get('executive_summary', 'Price movement opportunity'),
        'depth': len(chain_template['causal_chain']),
        'source_eqs': float(needle['eqs_score']) if needle['eqs_score'] else 0.0,
        'confluence_factors': needle['confluence_factor_count']
    }


def generate_shadow_hypothesis(conn, needle: Dict, input_hash: str) -> Optional[str]:
    """Generate a shadow hypothesis from a Golden Needle."""
    category = needle.get('hypothesis_category', 'REGIME_EDGE')
    chain_template = NEEDLE_MECHANISMS.get(category, NEEDLE_MECHANISMS['REGIME_EDGE'])

    hypothesis_code = get_next_hypothesis_code(conn)
    mechanism_graph = build_mechanism_graph(category, needle)

    cur = conn.cursor()

    # Build causal mechanism text
    causal_mechanism = ' -> '.join(chain_template['causal_chain'])

    # Compute semantic_hash EXACTLY as the DB trigger does:
    # trg_compute_semantic_hash → compute_hypothesis_hash(origin_rationale, causal_mechanism, direction, event_type_codes)
    # Formula: md5(lower(trim(origin || '|' || mechanism || '|' || direction || '|' || codes)))
    origin_rationale = f"Shadow hypothesis from Golden Needle: {needle['hypothesis_title']}"
    event_codes_str = category  # single-element array joined = just the category
    trigger_content = f"{origin_rationale}|{causal_mechanism}|NEUTRAL|{event_codes_str}"
    semantic_hash = hashlib.md5(trigger_content.lower().strip().encode()).hexdigest()

    # Check for duplicate using trigger-compatible hash
    cur.execute("SELECT hypothesis_code FROM fhq_learning.hypothesis_canon WHERE semantic_hash = %s", (semantic_hash,))
    existing = cur.fetchone()
    if existing:
        logger.info(f"DEDUP BLOCK: needle={needle['needle_id']} exists as {existing[0]}")
        return None

    # CEO-DIR-2026-128: MEMORY BIRTH GATE
    # Query prior failures before hypothesis birth
    asset_universe = chain_template['assets']
    cur.execute("""
        SELECT prior_count, exact_duplicate_exists, similar_failures,
               memory_citation, should_block, block_reason
        FROM fhq_learning.check_prior_failures(%s, %s, %s, %s)
    """, (causal_mechanism, semantic_hash, asset_universe, GENERATOR_ID))
    memory_result = cur.fetchone()

    if memory_result and memory_result[4]:  # should_block = True
        # Log the block
        cur.execute("""
            INSERT INTO fhq_learning.hypothesis_birth_blocks (
                block_reason, generator_id, proposed_semantic_hash,
                proposed_causal_mechanism, proposed_asset_universe,
                prior_failures_count, similar_failures
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            memory_result[5],  # block_reason
            GENERATOR_ID,
            semantic_hash,
            causal_mechanism[:500],
            asset_universe,
            memory_result[0],  # prior_count
            json.dumps(memory_result[2]) if memory_result[2] else None
        ))
        conn.commit()
        logger.warning(f"MEMORY_BLOCK: {memory_result[5]} - prior_count={memory_result[0]} (needle={needle['needle_id']})")
        return None

    # Extract memory citation for hypothesis birth
    prior_hypotheses_count = memory_result[0] if memory_result else 0

    # Parse falsification criteria from needle
    falsification = needle.get('falsification_criteria')
    if isinstance(falsification, str):
        try:
            falsification = json.loads(falsification)
        except:
            falsification = {'criteria': falsification}

    # INSERT — semantic_hash is computed by DB trigger trg_compute_semantic_hash
    # Dedup is handled by the check above using the same hash formula
    # CEO-DIR-2026-128: Now includes prior_hypotheses_count from memory gate
    cur.execute("""
        INSERT INTO fhq_learning.hypothesis_canon (
            canon_id,
            hypothesis_code,
            origin_type,
            origin_rationale,
            economic_rationale,
            causal_mechanism,
            counterfactual_scenario,
            behavioral_basis,
            event_type_codes,
            asset_universe,
            expected_direction,
            expected_magnitude,
            expected_timeframe_hours,
            regime_validity,
            regime_conditional_confidence,
            falsification_criteria,
            max_falsifications,
            initial_confidence,
            current_confidence,
            status,
            generator_id,
            input_artifacts_hash,
            mechanism_graph,
            causal_graph_depth,
            complexity_score,
            created_at,
            created_by,
            prior_hypotheses_count
        ) VALUES (
            gen_random_uuid(),
            %s, -- hypothesis_code
            'REGIME_CHANGE',
            %s, -- origin_rationale
            %s, -- economic_rationale
            %s, -- causal_mechanism
            %s, -- counterfactual_scenario
            %s, -- behavioral_basis
            %s, -- event_type_codes
            %s, -- asset_universe
            'NEUTRAL', -- shadow discoveries start neutral
            'MEDIUM',
            48, -- expected_timeframe_hours (shadow uses shorter window)
            %s, -- regime_validity
            %s, -- regime_conditional_confidence
            %s, -- falsification_criteria
            3,
            0.50, -- lower initial confidence for shadow
            0.50,
            'DRAFT', -- shadow-tier uses DRAFT status (not execution-eligible)
            %s, -- generator_id
            %s, -- input_artifacts_hash
            %s, -- mechanism_graph
            %s, -- causal_graph_depth
            %s, -- complexity_score
            NOW(),
            'GN-S',
            %s  -- prior_hypotheses_count (CEO-DIR-2026-128)
        )
        RETURNING hypothesis_code
    """, (
        hypothesis_code,
        f"Shadow hypothesis from Golden Needle: {needle['hypothesis_title']}",
        needle.get('hypothesis_statement', needle['hypothesis_title']),
        causal_mechanism,
        f"If Golden Needle pattern fails to materialize, expect mean-reversion or no significant move within 48h",
        chain_template['behavioral_basis'],
        [category],
        chain_template['assets'],
        chain_template['regime_validity'],
        json.dumps({regime: 0.55 for regime in chain_template['regime_validity']}),  # lower confidence for shadow
        json.dumps(falsification if falsification else {
            'price_reversal': 'Opposite direction move within 48h',
            'magnitude_threshold': '1.5 standard deviations'
        }),
        GENERATOR_ID,
        input_hash,
        json.dumps(mechanism_graph),
        mechanism_graph['depth'],
        round(mechanism_graph['depth'] * 0.6 + (needle['confluence_factor_count'] or 0) * 0.1, 2),
        prior_hypotheses_count,
    ))

    result = cur.fetchone()
    conn.commit()

    if result:
        logger.info(f"Generated SHADOW {hypothesis_code} from needle {needle['needle_id']} (depth={mechanism_graph['depth']})")
        return result[0]
    else:
        logger.info(f"Duplicate detected for needle {needle['needle_id']}, skipping")
        return None


def insert_provenance(conn, hypothesis_code: str, needle: Dict, input_hash: str):
    """Insert provenance record."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO fhq_learning.hypothesis_provenance (
            hypothesis_id,
            generator_id,
            origin_type,
            input_artifacts,
            input_hash,
            causal_depth,
            mechanism_summary
        )
        SELECT
            canon_id,
            %s,
            'REGIME_CHANGE',
            %s,
            %s,
            causal_graph_depth,
            %s
        FROM fhq_learning.hypothesis_canon
        WHERE hypothesis_code = %s
    """, (
        GENERATOR_ID,
        json.dumps({
            'golden_needle_id': str(needle['needle_id']),
            'category': needle.get('hypothesis_category'),
            'eqs_score': float(needle['eqs_score']) if needle['eqs_score'] else None
        }),
        input_hash,
        f"Golden Needle shadow: {needle['hypothesis_title']}",
        hypothesis_code
    ))
    conn.commit()


def heartbeat(conn, status: str, details: dict = None):
    """Update daemon heartbeat in daemon_health."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_monitoring.daemon_health (daemon_name, status, last_heartbeat, metadata)
                VALUES (%s, %s, NOW(), %s)
                ON CONFLICT (daemon_name)
                DO UPDATE SET status = EXCLUDED.status,
                              last_heartbeat = NOW(),
                              metadata = EXCLUDED.metadata,
                              updated_at = NOW()
            """, (DAEMON_NAME, status, json.dumps(details) if details else None))
            conn.commit()
    except Exception as e:
        logger.warning(f"Heartbeat failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass


def run_cycle() -> dict:
    """Run one GN-S generation cycle. Returns result dict."""
    conn = get_connection()
    try:
        logger.info("=" * 60)
        logger.info("GN-S Shadow Discovery Generator — Cycle Start")
        logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        logger.info("Constraints: Shadow-tier only, no reward coupling")
        logger.info("=" * 60)

        # Get recent Golden Needles — fetch more to maximize category coverage
        needles = get_recent_golden_needles(conn, limit=20)
        logger.info(f"Found {len(needles)} Golden Needles (last 30 days)")

        if not needles:
            logger.warning("No Golden Needles found in last 30 days")
            heartbeat(conn, 'DEGRADED', {'reason': 'NO_GOLDEN_NEEDLES'})
            return {'generated': 0, 'skipped': 0, 'duplicates': 0}

        input_hash = compute_input_hash(needles)

        generated = 0
        skipped = 0
        duplicates = 0

        # Generate shadow hypotheses
        categories_processed = set()

        for needle in needles:
            category = needle.get('hypothesis_category', 'REGIME_EDGE')

            # Limit to one per category per run
            if category in categories_processed:
                skipped += 1
                continue

            hypothesis_code = generate_shadow_hypothesis(conn, needle, input_hash)

            if hypothesis_code:
                insert_provenance(conn, hypothesis_code, needle, input_hash)
                generated += 1
                categories_processed.add(category)
            else:
                duplicates += 1
                categories_processed.add(category)

        logger.info(f"Generation complete: {generated} new, {duplicates} duplicate, {skipped} skipped")

        # Evidence file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence = {
            'daemon': DAEMON_NAME,
            'directive': 'CEO-DIR-2026-POR-001',
            'evidence_type': 'GN_S_GENERATION',
            'generated': generated,
            'duplicates': duplicates,
            'skipped': skipped,
            'categories_processed': list(categories_processed),
            'needles_available': len(needles),
            'computed_at': datetime.now(timezone.utc).isoformat()
        }
        evidence_path = os.path.join(script_dir, 'evidence', f'GN_S_GENERATION_{timestamp}.json')
        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2)
        logger.info(f"Evidence: {evidence_path}")

        heartbeat(conn, 'HEALTHY', {
            'generated': generated,
            'duplicates': duplicates,
            'categories': list(categories_processed)
        })

        return {'generated': generated, 'skipped': skipped, 'duplicates': duplicates}

    except Exception as e:
        logger.error(f"GN-S cycle failed: {e}")
        try:
            heartbeat(conn, 'DEGRADED', {'error': str(e)})
        except Exception:
            pass
        raise
    finally:
        conn.close()


def main():
    """Main entry point for GN-S daemon."""
    parser = argparse.ArgumentParser(description='GN-S Shadow Discovery Generator Daemon')
    parser.add_argument('--once', action='store_true',
                        help='Run a single generation cycle then exit')
    parser.add_argument('--interval', type=int, default=CYCLE_INTERVAL_SECONDS,
                        help=f'Cycle interval in seconds (default: {CYCLE_INTERVAL_SECONDS})')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("GN-S SHADOW DISCOVERY GENERATOR DAEMON")
    logger.info(f"  mode={'once' if args.once else 'continuous'}")
    logger.info(f"  interval={args.interval}s")
    logger.info("=" * 60)

    if args.once:
        result = run_cycle()
        print(json.dumps(result, indent=2))
        return

    # Continuous daemon loop
    while True:
        try:
            run_cycle()
        except Exception as e:
            logger.error(f"Cycle failed: {e}")
        logger.info(f"Next cycle in {args.interval}s")
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
