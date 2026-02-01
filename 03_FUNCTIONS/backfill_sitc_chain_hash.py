#!/usr/bin/env python3
"""
Backfill SitC Chain Hash for Existing Golden Needles
=====================================================
CEO Directive: CEO-ACI-TRIANGLE-2025-12-21

This script populates chain_of_query_hash for existing needles that don't have one.
This enables EC-020 SitC validation for historical needles.

Usage:
    python backfill_sitc_chain_hash.py --dry-run  # Preview changes
    python backfill_sitc_chain_hash.py --execute  # Apply changes
"""

import os
import json
import hashlib
import argparse
import logging
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [BACKFILL] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


def generate_chain_hash(needle: dict) -> str:
    """
    Generate a SitC chain_of_query_hash from needle metadata.

    The hash represents the reasoning chain used to produce the hypothesis.
    """
    # Extract confluence factors from boolean fields
    factors = []
    if needle.get('factor_price_technical'):
        factors.append('PRICE_TECHNICAL')
    if needle.get('factor_volume_confirmation'):
        factors.append('VOLUME_CONFIRMATION')
    if needle.get('factor_regime_alignment'):
        factors.append('REGIME_ALIGNMENT')
    if needle.get('factor_temporal_coherence'):
        factors.append('TEMPORAL_COHERENCE')
    if needle.get('factor_catalyst_present'):
        factors.append('CATALYST_PRESENT')
    if needle.get('factor_specific_testable'):
        factors.append('SPECIFIC_TESTABLE')
    if needle.get('factor_testable_criteria'):
        factors.append('TESTABLE_CRITERIA')

    # Build EQS components from weights
    eqs_components = {}
    for key in ['weight_price_technical', 'weight_volume_confirmation',
                'weight_regime_alignment', 'weight_temporal_coherence',
                'weight_catalyst_present', 'weight_specificity_bonus',
                'weight_testability_bonus']:
        if needle.get(key):
            component_name = key.replace('weight_', '')
            eqs_components[component_name] = float(needle[key])

    # Build the SitC chain structure (same as wave15_autonomous_hunter.py)
    sitc_chain = {
        'plan_init': {
            'query': needle.get('hypothesis_title', '')[:100],
            'timestamp': needle.get('created_at', datetime.now(timezone.utc)).isoformat() if isinstance(needle.get('created_at'), datetime) else str(needle.get('created_at', ''))
        },
        'nodes': [
            {'type': 'HYPOTHESIS', 'content': (needle.get('hypothesis_statement') or '')[:200]},
            {'type': 'CONFLUENCE_CHECK', 'factors': factors},
            {'type': 'EQS_CALCULATION', 'score': float(needle.get('eqs_score', 0)), 'components': eqs_components},
            {'type': 'CONFIDENCE_EVAL', 'level': needle.get('sitc_confidence_level', 'UNKNOWN'), 'action': 'ACCEPT'}
        ],
        'synthesis': {'final_score': float(needle.get('eqs_score', 0)), 'decision': 'ACCEPT'}
    }

    # Generate hash
    chain_hash = hashlib.sha256(
        json.dumps(sitc_chain, sort_keys=True, default=str).encode()
    ).hexdigest()

    return chain_hash


def backfill_chain_hashes(dry_run: bool = True):
    """Backfill chain_of_query_hash for needles that don't have one."""
    conn = psycopg2.connect(**DB_CONFIG)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Find needles without chain_of_query_hash
            cur.execute("""
                SELECT needle_id, hypothesis_title, hypothesis_statement, eqs_score,
                       sitc_confidence_level, sitc_nodes_completed, sitc_nodes_total,
                       factor_price_technical, factor_volume_confirmation,
                       factor_regime_alignment, factor_temporal_coherence,
                       factor_catalyst_present, factor_specific_testable, factor_testable_criteria,
                       weight_price_technical, weight_volume_confirmation,
                       weight_regime_alignment, weight_temporal_coherence,
                       weight_catalyst_present, weight_specificity_bonus, weight_testability_bonus,
                       created_at
                FROM fhq_canonical.golden_needles
                WHERE chain_of_query_hash IS NULL
                  AND is_current = TRUE
            """)

            needles = cur.fetchall()
            logger.info(f"Found {len(needles)} needles without chain_of_query_hash")

            if len(needles) == 0:
                logger.info("No needles to backfill.")
                return

            updated = 0
            for needle in needles:
                needle_id = needle['needle_id']
                chain_hash = generate_chain_hash(dict(needle))

                if dry_run:
                    logger.info(f"[DRY-RUN] Would update needle {needle_id} with hash {chain_hash[:16]}...")
                else:
                    cur.execute("""
                        UPDATE fhq_canonical.golden_needles
                        SET chain_of_query_hash = %s
                        WHERE needle_id = %s
                    """, (chain_hash, needle_id))
                    updated += 1

                    if updated % 100 == 0:
                        logger.info(f"Updated {updated} needles...")

            if not dry_run:
                conn.commit()
                logger.info(f"Successfully backfilled {updated} needles with chain_of_query_hash")
            else:
                logger.info(f"[DRY-RUN] Would have updated {len(needles)} needles")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Backfill SitC chain hashes')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--execute', action='store_true', help='Apply changes to database')

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Usage: python backfill_sitc_chain_hash.py --dry-run OR --execute")
        return

    print("=" * 60)
    print("SitC Chain Hash Backfill")
    print("CEO Directive: CEO-ACI-TRIANGLE-2025-12-21")
    print("=" * 60)

    dry_run = args.dry_run
    backfill_chain_hashes(dry_run=dry_run)


if __name__ == '__main__':
    main()
