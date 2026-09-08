#!/usr/bin/env python3
"""
IoS-010 Regret Attribution Classifier
======================================
Directive: CEO-DIR-2026-021 Optimization Phase
Purpose: Classify regret into Type A/B/C for surgical optimization
Authority: STIG (Observability Enhancement)

Type A (Hysteresis Lag): Policy confirms_required prevented flip
Type B (Confidence Floor): Belief confidence just below LIDS threshold
Type C (Data Blindness): Macro signal changed, not captured in feature set

Usage:
    python ios010_regret_attribution_classifier.py           # Classify all unattributed regret
    python ios010_regret_attribution_classifier.py --dry-run # Show classification without writing
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("regret_attribution_classifier")

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": os.getenv("PGPORT", "54322"),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres")
}

# Type B threshold: If confidence gap is within 5% of threshold, classify as Confidence Floor
TYPE_B_THRESHOLD = 0.05

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Establish database connection"""
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# REGRET CLASSIFICATION LOGIC
# =============================================================================

def classify_regret_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify a single regret record into Type A/B/C/X.

    Returns classification dict with:
    - regret_attribution_type
    - regret_root_cause (JSONB)
    - regret_magnitude_category
    """

    # Extract fields
    suppression_reason = record.get('suppression_reason', '')
    suppression_category = record.get('suppression_category', '')
    constraint_type = record.get('constraint_type', '')
    regret_magnitude = float(record.get('regret_magnitude', 0))
    suppressed_confidence = float(record.get('suppressed_confidence', 0))
    chosen_confidence = float(record.get('chosen_confidence', 0))
    asset_id = record.get('asset_id', '')

    # Categorize magnitude
    if regret_magnitude < 0.02:
        magnitude_category = 'LOW'
    elif regret_magnitude < 0.05:
        magnitude_category = 'MEDIUM'
    elif regret_magnitude < 0.10:
        magnitude_category = 'HIGH'
    else:
        magnitude_category = 'EXTREME'

    # Type A: Hysteresis Lag
    # Indicates: confirms_required or temporal constraint prevented flip
    if suppression_category == 'HYSTERESIS':
        return {
            'regret_attribution_type': 'TYPE_A_HYSTERESIS_LAG',
            'regret_root_cause': {
                'type': 'HYSTERESIS_LAG',
                'constraint_type': constraint_type,
                'suppression_reason': suppression_reason,
                'suppressed_confidence': suppressed_confidence,
                'chosen_confidence': chosen_confidence,
                'confidence_delta': chosen_confidence - suppressed_confidence,
                'asset_id': asset_id
            },
            'regret_magnitude_category': magnitude_category
        }

    # Type B: Confidence Floor
    # Indicates: Belief was just below LIDS threshold (e.g., 0.68 when threshold is 0.70)
    # Assume LIDS threshold is 0.70 (this should be parameterized in production)
    LIDS_THRESHOLD = 0.70
    confidence_gap = LIDS_THRESHOLD - suppressed_confidence

    if 0 <= confidence_gap <= TYPE_B_THRESHOLD:
        return {
            'regret_attribution_type': 'TYPE_B_CONFIDENCE_FLOOR',
            'regret_root_cause': {
                'type': 'CONFIDENCE_FLOOR',
                'lids_threshold': LIDS_THRESHOLD,
                'suppressed_confidence': suppressed_confidence,
                'confidence_gap': confidence_gap,
                'suppression_reason': suppression_reason,
                'asset_id': asset_id
            },
            'regret_magnitude_category': magnitude_category
        }

    # Type C: Data Blindness
    # Indicates: Missing macro signal or feature not in model
    # Heuristic: If not Type A or B, and regret is HIGH/EXTREME, likely data blindness
    # (More sophisticated version would check if macro factors changed significantly)
    if magnitude_category in ['HIGH', 'EXTREME']:
        return {
            'regret_attribution_type': 'TYPE_C_DATA_BLINDNESS',
            'regret_root_cause': {
                'type': 'DATA_BLINDNESS',
                'suppression_reason': suppression_reason,
                'suppressed_confidence': suppressed_confidence,
                'chosen_confidence': chosen_confidence,
                'regret_magnitude': regret_magnitude,
                'asset_id': asset_id,
                'hypothesis': 'Macro signal changed, not captured in feature set'
            },
            'regret_magnitude_category': magnitude_category
        }

    # Type X: Unknown
    # Fallback for cases that don't fit Type A/B/C
    return {
        'regret_attribution_type': 'TYPE_X_UNKNOWN',
        'regret_root_cause': {
            'type': 'UNKNOWN',
            'suppression_reason': suppression_reason,
            'suppression_category': suppression_category,
            'asset_id': asset_id
        },
        'regret_magnitude_category': magnitude_category
    }

# =============================================================================
# BATCH CLASSIFICATION
# =============================================================================

def classify_unattributed_regret(conn, dry_run: bool = False) -> Dict[str, Any]:
    """
    Classify all REGRET records that don't have attribution yet.
    """

    logger.info("Fetching unattributed REGRET records...")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get all REGRET records without attribution
        cur.execute("""
            SELECT
                suppression_id,
                asset_id,
                suppression_category,
                suppression_reason,
                constraint_type,
                constraint_value,
                suppressed_confidence,
                chosen_confidence,
                regret_classification,
                regret_magnitude,
                suppression_timestamp
            FROM fhq_governance.epistemic_suppression_ledger
            WHERE regret_classification = 'REGRET'
              AND regret_attribution_type IS NULL
            ORDER BY suppression_timestamp DESC
        """)

        records = cur.fetchall()

    if not records:
        logger.info("No unattributed REGRET records found")
        return {
            'classified_count': 0,
            'type_a_count': 0,
            'type_b_count': 0,
            'type_c_count': 0,
            'type_x_count': 0
        }

    logger.info(f"Found {len(records)} unattributed REGRET records")

    # Classify each record
    classifications = []
    type_counts = {'TYPE_A': 0, 'TYPE_B': 0, 'TYPE_C': 0, 'TYPE_X': 0}

    for record in records:
        classification = classify_regret_record(dict(record))

        classifications.append({
            'suppression_id': str(record['suppression_id']),
            **classification
        })

        # Count by type
        attr_type = classification['regret_attribution_type']
        if 'TYPE_A' in attr_type:
            type_counts['TYPE_A'] += 1
        elif 'TYPE_B' in attr_type:
            type_counts['TYPE_B'] += 1
        elif 'TYPE_C' in attr_type:
            type_counts['TYPE_C'] += 1
        else:
            type_counts['TYPE_X'] += 1

    logger.info(f"Classification complete: A={type_counts['TYPE_A']}, B={type_counts['TYPE_B']}, C={type_counts['TYPE_C']}, X={type_counts['TYPE_X']}")

    if dry_run:
        logger.info("[DRY RUN] Would update database with classifications")
        return {
            'classified_count': len(classifications),
            'type_a_count': type_counts['TYPE_A'],
            'type_b_count': type_counts['TYPE_B'],
            'type_c_count': type_counts['TYPE_C'],
            'type_x_count': type_counts['TYPE_X'],
            'dry_run': True
        }

    # Update database
    logger.info("Writing classifications to database...")

    with conn.cursor() as cur:
        for classification in classifications:
            cur.execute("""
                UPDATE fhq_governance.epistemic_suppression_ledger
                SET
                    regret_attribution_type = %s,
                    regret_root_cause = %s,
                    regret_magnitude_category = %s
                WHERE suppression_id = %s::uuid
            """, (
                classification['regret_attribution_type'],
                json.dumps(classification['regret_root_cause']),
                classification['regret_magnitude_category'],
                classification['suppression_id']
            ))

    conn.commit()

    logger.info(f"✅ Successfully classified {len(classifications)} REGRET records")

    # Refresh attribution summary
    logger.info("Refreshing regret_attribution_summary...")
    with conn.cursor() as cur:
        cur.execute("SELECT fhq_governance.refresh_regret_attribution_summary()")
    conn.commit()

    return {
        'classified_count': len(classifications),
        'type_a_count': type_counts['TYPE_A'],
        'type_b_count': type_counts['TYPE_B'],
        'type_c_count': type_counts['TYPE_C'],
        'type_x_count': type_counts['TYPE_X'],
        'dry_run': False
    }

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main(dry_run: bool = False):
    """Main execution"""

    logger.info("=" * 60)
    logger.info("IoS-010 REGRET ATTRIBUTION CLASSIFIER")
    logger.info("Directive: CEO-DIR-2026-021 Optimization Phase")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}")
    logger.info("=" * 60)

    conn = None

    try:
        conn = get_db_connection()
        result = classify_unattributed_regret(conn, dry_run=dry_run)

        logger.info("=" * 60)
        logger.info("CLASSIFICATION COMPLETE")
        logger.info(f"Records Classified: {result['classified_count']}")
        logger.info(f"Type A (Hysteresis Lag): {result['type_a_count']}")
        logger.info(f"Type B (Confidence Floor): {result['type_b_count']}")
        logger.info(f"Type C (Data Blindness): {result['type_c_count']}")
        logger.info(f"Type X (Unknown): {result['type_x_count']}")
        logger.info("=" * 60)

        print(json.dumps(result, indent=2))
        return 0

    except Exception as e:
        logger.error(f"Classification failed: {e}")
        if conn:
            conn.rollback()
        return 1
    finally:
        if conn:
            conn.close()

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="IoS-010 Regret Attribution Classifier")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show classification without writing to database")
    args = parser.parse_args()

    sys.exit(main(dry_run=args.dry_run))
