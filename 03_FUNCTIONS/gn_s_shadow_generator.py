#!/usr/bin/env python3
"""
GN-S Shadow Discovery Generator
CEO-DIR-2026-POR-001: Multi-Generator Research Portfolio

Generator C: GN-S (Golden Needles Shadow Feed)
Purpose: Orthogonal discovery and Symmetry Watch benchmark
Constraints: Shadow-tier only, no reward, no execution eligibility
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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

    # Build semantic hash for duplicate detection
    semantic_content = f"GN:{needle['needle_id']}:{needle['hypothesis_title']}"
    semantic_hash = hashlib.md5(semantic_content.encode()).hexdigest()

    cur = conn.cursor()

    # Check for duplicate
    cur.execute("""
        SELECT hypothesis_code FROM fhq_learning.hypothesis_canon
        WHERE semantic_hash = %s
    """, (semantic_hash,))

    if cur.fetchone():
        logger.info(f"Duplicate detected for needle {needle['needle_id']}, skipping")
        return None

    # Build causal mechanism text
    causal_mechanism = ' -> '.join(chain_template['causal_chain'])

    # Parse falsification criteria from needle
    falsification = needle.get('falsification_criteria')
    if isinstance(falsification, str):
        try:
            falsification = json.loads(falsification)
        except:
            falsification = {'criteria': falsification}

    # Insert hypothesis
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
            semantic_hash,
            created_at,
            created_by
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
            %s, -- semantic_hash
            NOW(),
            'GN-S'
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
        semantic_hash
    ))

    result = cur.fetchone()
    conn.commit()

    logger.info(f"Generated SHADOW {hypothesis_code} from needle {needle['needle_id']} (depth={mechanism_graph['depth']})")
    return result[0] if result else None


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


def run_generator():
    """Run the GN-S shadow generator."""
    logger.info("=" * 60)
    logger.info("GN-S Shadow Discovery Generator Starting")
    logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    logger.info("Constraints: Shadow-tier only, no reward coupling")
    logger.info("=" * 60)

    conn = get_connection()

    try:
        # Get recent Golden Needles
        needles = get_recent_golden_needles(conn, limit=5)
        logger.info(f"Found {len(needles)} Golden Needles (last 30 days)")

        if not needles:
            logger.warning("No Golden Needles found in last 30 days")
            return {'generated': 0, 'skipped': 0}

        input_hash = compute_input_hash(needles)

        generated = 0
        skipped = 0

        # Generate shadow hypotheses
        categories_processed = set()

        for needle in needles:
            category = needle.get('hypothesis_category', 'REGIME_EDGE')

            # Limit to one per category per run
            if category in categories_processed:
                continue

            hypothesis_code = generate_shadow_hypothesis(conn, needle, input_hash)

            if hypothesis_code:
                insert_provenance(conn, hypothesis_code, needle, input_hash)
                generated += 1
                categories_processed.add(category)
            else:
                skipped += 1

        logger.info(f"Generation complete: {generated} SHADOW hypotheses, {skipped} skipped")

        return {'generated': generated, 'skipped': skipped}

    finally:
        conn.close()


if __name__ == '__main__':
    result = run_generator()
    print(json.dumps(result, indent=2))
