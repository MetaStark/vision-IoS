#!/usr/bin/env python3
"""
FINN-T World-Model Generator
CEO-DIR-2026-POR-001: Multi-Generator Research Portfolio

Generator B: FINN-T (Theory / World-Model Alignment)
Purpose: Generate hypotheses from validated macro/credit/liquidity/factor drivers
Requirement: N-tier mechanism chains (depth >= 2)
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

GENERATOR_ID = 'FINN-T'
MIN_CAUSAL_DEPTH = 2

# Mechanism chain templates for G3 clusters
MECHANISM_CHAINS = {
    'LIQUIDITY': {
        'causal_chain': [
            'Fed policy changes liquidity conditions',
            'Liquidity flows into/out of risk assets',
            'Asset prices adjust to new liquidity equilibrium'
        ],
        'behavioral_basis': 'Institutional portfolio rebalancing follows liquidity signals',
        'regime_validity': ['RISK_ON', 'RISK_OFF', 'EXPANSION'],
        'assets': ['SPY', 'QQQ', 'TLT']
    },
    'CREDIT': {
        'causal_chain': [
            'Credit conditions tighten or loosen',
            'Corporate borrowing costs change',
            'Investment and earnings expectations adjust',
            'Equity valuations re-rate'
        ],
        'behavioral_basis': 'Credit cycles lead equity cycles by 3-6 months',
        'regime_validity': ['CONTRACTION', 'EXPANSION', 'TRANSITION'],
        'assets': ['SPY', 'XLF', 'HYG']
    },
    'FACTOR': {
        'causal_chain': [
            'Factor exposure concentrations build',
            'Regime shift triggers factor rotation',
            'Crowded positions unwind creating momentum'
        ],
        'behavioral_basis': 'Factor crowding creates mean-reversion pressure',
        'regime_validity': ['TRANSITION', 'RISK_OFF'],
        'assets': ['SPY', 'IWM', 'QQQ']
    }
}


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def compute_input_hash(features: List[Dict]) -> str:
    """Compute hash of input artifacts for provenance."""
    content = json.dumps([f['feature_id'] for f in features], sort_keys=True)
    return hashlib.md5(content.encode()).hexdigest()


def get_g3_golden_features(conn) -> List[Dict]:
    """Get G3 Golden Features for hypothesis generation."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT feature_id, cluster, hypothesis, expected_direction, status
        FROM fhq_macro.golden_features
        WHERE status = 'CANONICAL'
        ORDER BY cluster, feature_id
    """)
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


def build_mechanism_graph(cluster: str, feature: Dict) -> Dict:
    """Build N-tier mechanism graph for a feature."""
    chain_template = MECHANISM_CHAINS.get(cluster, MECHANISM_CHAINS['LIQUIDITY'])

    return {
        'nodes': [
            {'tier': i+1, 'mechanism': step, 'evidence_required': True}
            for i, step in enumerate(chain_template['causal_chain'])
        ],
        'root_driver': feature['feature_id'],
        'terminal_outcome': f"Asset price movement in {feature['expected_direction']} direction",
        'depth': len(chain_template['causal_chain'])
    }


def map_direction(direction: str) -> str:
    """Map feature direction to valid hypothesis_canon values."""
    mapping = {
        'POSITIVE': 'BULLISH',
        'NEGATIVE': 'BEARISH',
        'NEUTRAL': 'NEUTRAL',
        'BULLISH': 'BULLISH',
        'BEARISH': 'BEARISH',
    }
    return mapping.get(direction.upper() if direction else 'NEUTRAL', 'NEUTRAL')


def generate_hypothesis_from_feature(conn, feature: Dict, input_hash: str) -> Optional[str]:
    """Generate a hypothesis from a G3 Golden Feature."""
    cluster = feature['cluster']
    chain_template = MECHANISM_CHAINS.get(cluster, MECHANISM_CHAINS['LIQUIDITY'])

    hypothesis_code = get_next_hypothesis_code(conn)
    mechanism_graph = build_mechanism_graph(cluster, feature)
    mapped_direction = map_direction(feature['expected_direction'])

    # Build semantic hash for duplicate detection
    semantic_content = f"{feature['feature_id']}:{feature['hypothesis']}:{cluster}"
    semantic_hash = hashlib.md5(semantic_content.encode()).hexdigest()

    cur = conn.cursor()

    # Check for duplicate
    cur.execute("""
        SELECT hypothesis_code FROM fhq_learning.hypothesis_canon
        WHERE semantic_hash = %s
    """, (semantic_hash,))

    if cur.fetchone():
        logger.info(f"Duplicate detected for {feature['feature_id']}, skipping")
        return None

    # Build causal mechanism text
    causal_mechanism = ' -> '.join(chain_template['causal_chain'])

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
            'ECONOMIC_THEORY',
            %s, -- origin_rationale
            %s, -- economic_rationale
            %s, -- causal_mechanism
            %s, -- counterfactual_scenario
            %s, -- behavioral_basis
            %s, -- event_type_codes
            %s, -- asset_universe
            %s, -- expected_direction
            'MEDIUM',
            72, -- expected_timeframe_hours
            %s, -- regime_validity
            %s, -- regime_conditional_confidence
            %s, -- falsification_criteria
            3,
            0.60,
            0.60,
            'ACTIVE',
            %s, -- generator_id
            %s, -- input_artifacts_hash
            %s, -- mechanism_graph
            %s, -- causal_graph_depth
            %s, -- complexity_score
            %s, -- semantic_hash
            NOW(),
            'FINN-T'
        )
        RETURNING hypothesis_code
    """, (
        hypothesis_code,
        f"Generated from G3 Golden Feature: {feature['feature_id']} ({cluster})",
        feature['hypothesis'],
        causal_mechanism,
        f"If {feature['feature_id']} signal fails to manifest, expect no directional move or reversal within 72h",
        chain_template['behavioral_basis'],
        [cluster],  # event_type_codes
        chain_template['assets'],
        mapped_direction,
        chain_template['regime_validity'],
        json.dumps({regime: 0.65 for regime in chain_template['regime_validity']}),  # regime_conditional_confidence
        json.dumps({
            'direction_violation': f"Price moves opposite to {feature['expected_direction']} after {feature['feature_id']} signal",
            'magnitude_threshold': '2 standard deviations',
            'time_window_hours': 72
        }),
        GENERATOR_ID,
        input_hash,
        json.dumps(mechanism_graph),
        mechanism_graph['depth'],
        round(mechanism_graph['depth'] * 0.5, 2),  # complexity score based on depth
        semantic_hash
    ))

    result = cur.fetchone()
    conn.commit()

    logger.info(f"Generated {hypothesis_code} from {feature['feature_id']} (depth={mechanism_graph['depth']})")
    return result[0] if result else None


def insert_provenance(conn, hypothesis_code: str, feature: Dict, input_hash: str):
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
            'ECONOMIC_THEORY',
            %s,
            %s,
            causal_graph_depth,
            %s
        FROM fhq_learning.hypothesis_canon
        WHERE hypothesis_code = %s
    """, (
        GENERATOR_ID,
        json.dumps({'g3_feature': feature['feature_id'], 'cluster': feature['cluster']}),
        input_hash,
        f"G3 {feature['cluster']} feature: {feature['hypothesis']}",
        hypothesis_code
    ))
    conn.commit()


def run_generator():
    """Run the FINN-T generator."""
    logger.info("=" * 60)
    logger.info("FINN-T World-Model Generator Starting")
    logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 60)

    conn = get_connection()

    try:
        # Get G3 Golden Features
        features = get_g3_golden_features(conn)
        logger.info(f"Found {len(features)} G3 Golden Features")

        if not features:
            logger.warning("No G3 Golden Features found")
            return {'generated': 0, 'skipped': 0}

        input_hash = compute_input_hash(features)

        generated = 0
        skipped = 0

        # Generate one hypothesis per cluster (to avoid flooding)
        clusters_processed = set()

        for feature in features:
            cluster = feature['cluster']

            # Limit to one per cluster per run
            if cluster in clusters_processed:
                continue

            hypothesis_code = generate_hypothesis_from_feature(conn, feature, input_hash)

            if hypothesis_code:
                insert_provenance(conn, hypothesis_code, feature, input_hash)
                generated += 1
                clusters_processed.add(cluster)
            else:
                skipped += 1

        logger.info(f"Generation complete: {generated} generated, {skipped} skipped")

        return {'generated': generated, 'skipped': skipped}

    finally:
        conn.close()


if __name__ == '__main__':
    result = run_generator()
    print(json.dumps(result, indent=2))
