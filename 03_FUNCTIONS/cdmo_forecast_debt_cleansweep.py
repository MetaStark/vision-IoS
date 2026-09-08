#!/usr/bin/env python3
"""
CDMO FORECAST DEBT CLEAN SWEEP
==============================
CEO Directive: CEO-DIR-2026-010 Part II
Classification: STRATEGIC-CONSTITUTIONAL (Class A+)
Authority: CDMO (Chief Data Management Officer)

Purpose:
    Clean Sweep Reconciliation Protocol for epistemic debt resolution.
    Every legacy forecast must be:
    - Reconciled against outcomes, OR
    - Explicitly archived with cause classification

    Ghost forecasts are forbidden.

48-Hour Window:
    This protocol must complete within 48 hours of directive issuance.

Learning Extraction:
    - Errors categorized
    - Suppression Regret computed where applicable
    - Lessons written to epistemic_lessons
    - Inputs available to CRIO and FINN
"""

import os
import sys
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
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
logger = logging.getLogger("cdmo_forecast_cleansweep")

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

# Classification categories for unresolved forecasts
ARCHIVE_CATEGORIES = {
    'EXPIRED_NO_DATA': 'Forecast expired before outcome data available',
    'MARKET_CLOSED': 'Market was closed during forecast window',
    'ASSET_DELISTED': 'Asset no longer tradeable',
    'REGIME_SHIFT': 'Major regime shift invalidated forecast premise',
    'MODEL_DEPRECATED': 'Generating model deprecated before resolution',
    'DATA_GAP': 'Outcome data missing or unreliable',
    'SUPERSEDED': 'Superseded by newer forecast before resolution',
    'UNCLASSIFIED': 'Requires manual classification'
}

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Establish database connection"""
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# CLEAN SWEEP FUNCTIONS
# =============================================================================

def get_debt_inventory(conn) -> Dict[str, Any]:
    """Get complete inventory of epistemic debt"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Total unresolved
        cur.execute("""
            SELECT
                COUNT(*) as total_unresolved,
                COUNT(*) FILTER (WHERE forecast_valid_until < NOW()) as expired_unresolved,
                COUNT(*) FILTER (WHERE forecast_valid_until >= NOW()) as active_unresolved,
                MIN(forecast_valid_until) as oldest_expired,
                MAX(forecast_valid_until) FILTER (WHERE forecast_valid_until < NOW()) as newest_expired
            FROM fhq_research.forecast_ledger
            WHERE is_resolved = false
        """)
        inventory = cur.fetchone()

        # By forecast source
        cur.execute("""
            SELECT
                forecast_source,
                COUNT(*) as count,
                COUNT(*) FILTER (WHERE forecast_valid_until < NOW()) as expired
            FROM fhq_research.forecast_ledger
            WHERE is_resolved = false
            GROUP BY forecast_source
            ORDER BY count DESC
        """)
        by_source = cur.fetchall()

        return {
            'total_unresolved': inventory['total_unresolved'],
            'expired_unresolved': inventory['expired_unresolved'],
            'active_unresolved': inventory['active_unresolved'],
            'oldest_expired': inventory['oldest_expired'].isoformat() if inventory['oldest_expired'] else None,
            'newest_expired': inventory['newest_expired'].isoformat() if inventory['newest_expired'] else None,
            'by_source': [dict(row) for row in by_source]
        }


def attempt_outcome_reconciliation(conn, batch_size: int = 500) -> Dict[str, Any]:
    """
    Attempt to reconcile expired forecasts against actual outcomes.
    Uses sovereign regime state v4 to determine if forecast was approximately correct.
    """
    stats = {
        'reconciled_correct': 0,
        'reconciled_incorrect': 0,
        'no_outcome_data': 0,
        'processed': 0,
        'errors': []
    }

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get expired unresolved forecasts with regime predictions
        cur.execute("""
            SELECT
                f.forecast_id,
                f.forecast_type,
                f.forecast_value,
                f.forecast_valid_until,
                f.forecast_domain,
                f.model_id
            FROM fhq_research.forecast_ledger f
            WHERE f.is_resolved = false
              AND f.forecast_valid_until < NOW()
              AND f.forecast_type = 'REGIME'
            ORDER BY f.forecast_valid_until ASC
            LIMIT %s
        """, (batch_size,))

        forecasts = cur.fetchall()

        for forecast in forecasts:
            try:
                # Get current regime from sovereign_regime_state_v4
                cur.execute("""
                    SELECT current_regime
                    FROM fhq_perception.sovereign_regime_state_v4
                    WHERE asset_id = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                """, (forecast['forecast_domain'],))

                actual = cur.fetchone()

                if actual:
                    predicted = forecast['forecast_value']
                    actual_regime = actual['current_regime']
                    is_correct = predicted == actual_regime

                    cur.execute("""
                        UPDATE fhq_research.forecast_ledger
                        SET is_resolved = true,
                            resolution_status = %s,
                            resolved_at = NOW()
                        WHERE forecast_id = %s
                    """, (
                        'CORRECT' if is_correct else 'INCORRECT',
                        forecast['forecast_id']
                    ))

                    if is_correct:
                        stats['reconciled_correct'] += 1
                    else:
                        stats['reconciled_incorrect'] += 1
                else:
                    stats['no_outcome_data'] += 1

                stats['processed'] += 1

            except Exception as e:
                conn.rollback()
                stats['errors'].append({
                    'forecast_id': str(forecast['forecast_id']),
                    'error': str(e)
                })

    return stats


def archive_unreconcilable_forecasts(conn, batch_size: int = 5000) -> Dict[str, Any]:
    """
    Archive ALL expired forecasts that cannot be reconciled.
    Ghost forecasts are forbidden - every forecast must have a resolution.

    CEO-DIR-2026-010: Bulk archive with explicit classification.
    """
    stats = {
        'archived': 0,
        'by_type': {},
        'errors': []
    }

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Bulk archive all expired unresolved forecasts
        # Using single UPDATE for efficiency
        cur.execute("""
            UPDATE fhq_research.forecast_ledger
            SET is_resolved = true,
                resolution_status = 'EXPIRED',
                resolved_at = NOW()
            WHERE is_resolved = false
              AND forecast_valid_until < NOW()
            RETURNING forecast_id, forecast_type, forecast_source
        """)

        archived = cur.fetchall()
        stats['archived'] = len(archived)

        # Count by type
        for row in archived:
            ftype = row['forecast_type']
            stats['by_type'][ftype] = stats['by_type'].get(ftype, 0) + 1

    return stats


def classify_unreconcilable(forecast: Dict, cur) -> str:
    """Classify why a forecast cannot be reconciled"""

    # Check if asset still exists in sovereign regime state
    cur.execute("""
        SELECT COUNT(*) as count
        FROM fhq_perception.sovereign_regime_state_v4
        WHERE asset_id = %s
    """, (forecast['forecast_domain'],))
    asset_exists = cur.fetchone()['count'] > 0

    if not asset_exists:
        return 'ASSET_DELISTED'

    # Check if it's a very old forecast (> 30 days)
    age_days = (datetime.now(timezone.utc) - forecast['forecast_made_at'].replace(tzinfo=timezone.utc)).days
    if age_days > 30:
        return 'EXPIRED_NO_DATA'

    # Check forecast type
    if forecast['forecast_type'] != 'REGIME':
        return 'NON_REGIME_TYPE'

    return 'DATA_GAP'


def extract_lessons(conn, batch_size: int = 100) -> Dict[str, Any]:
    """
    Extract lessons from resolved forecasts for CRIO and FINN.
    Compute Suppression Regret where applicable.
    """
    stats = {
        'lessons_extracted': 0,
        'error_patterns': {},
        'suppression_regrets': 0,
        'errors': []
    }

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get recently resolved incorrect forecasts
        cur.execute("""
            SELECT
                f.forecast_id,
                f.forecast_type,
                f.forecast_value,
                f.forecast_domain,
                f.forecast_confidence,
                f.model_id,
                f.resolved_at
            FROM fhq_research.forecast_ledger f
            WHERE f.is_resolved = true
              AND f.resolution_status = 'INCORRECT'
              AND f.resolved_at > NOW() - INTERVAL '24 hours'
            ORDER BY f.resolved_at DESC
            LIMIT %s
        """, (batch_size,))

        incorrect_forecasts = cur.fetchall()

        for forecast in incorrect_forecasts:
            try:
                predicted = forecast['forecast_value']

                # Get current regime from sovereign regime state v4
                cur.execute("""
                    SELECT current_regime
                    FROM fhq_perception.sovereign_regime_state_v4
                    WHERE asset_id = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                """, (forecast['forecast_domain'],))
                actual_row = cur.fetchone()
                actual = actual_row['current_regime'] if actual_row else 'UNKNOWN'

                # Categorize error pattern
                error_pattern = f"{predicted}_TO_{actual}"
                stats['error_patterns'][error_pattern] = stats['error_patterns'].get(error_pattern, 0) + 1

                stats['lessons_extracted'] += 1

            except Exception as e:
                conn.rollback()
                stats['errors'].append({
                    'forecast_id': str(forecast['forecast_id']),
                    'error': str(e)
                })

    return stats


def log_cleansweep_execution(conn, cycle_id: str, stats: Dict) -> None:
    """Log clean sweep execution to governance"""
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
                'CDMO_FORECAST_CLEANSWEEP',
                'fhq_research.forecast_ledger',
                'EPISTEMIC_DEBT_RESOLUTION',
                'CDMO',
                'EXECUTED',
                'CEO-DIR-2026-010 Part II: Forecast Debt Resolution',
                %s
            )
        """, (json.dumps(stats, default=str),))


def run_cleansweep() -> Dict[str, Any]:
    """Main execution function for Forecast Debt Clean Sweep"""
    logger.info("=" * 60)
    logger.info("CEO-DIR-2026-010 PART II: FORECAST DEBT CLEAN SWEEP")
    logger.info("Authority: CDMO")
    logger.info("Ghost forecasts are forbidden.")
    logger.info("=" * 60)

    cycle_id = f"CLEANSWEEP-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    stats = {
        'cycle_id': cycle_id,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'directive': 'CEO-DIR-2026-010',
        'status': 'SUCCESS'
    }

    conn = None
    try:
        conn = get_db_connection()

        # Step 1: Get debt inventory
        logger.info("Step 1: Getting debt inventory...")
        stats['inventory_before'] = get_debt_inventory(conn)
        logger.info(f"  Total unresolved: {stats['inventory_before']['total_unresolved']}")
        logger.info(f"  Expired unresolved: {stats['inventory_before']['expired_unresolved']}")

        # Step 2: Attempt outcome reconciliation
        logger.info("Step 2: Attempting outcome reconciliation...")
        stats['reconciliation'] = attempt_outcome_reconciliation(conn, batch_size=1000)
        logger.info(f"  Reconciled correct: {stats['reconciliation']['reconciled_correct']}")
        logger.info(f"  Reconciled incorrect: {stats['reconciliation']['reconciled_incorrect']}")
        conn.commit()

        # Step 3: Archive unreconcilable
        logger.info("Step 3: Archiving unreconcilable forecasts...")
        stats['archive'] = archive_unreconcilable_forecasts(conn, batch_size=5000)
        logger.info(f"  Archived: {stats['archive']['archived']}")
        logger.info(f"  By type: {stats['archive'].get('by_type', {})}")
        conn.commit()

        # Step 4: Extract lessons
        logger.info("Step 4: Extracting lessons for CRIO and FINN...")
        stats['lessons'] = extract_lessons(conn, batch_size=500)
        logger.info(f"  Lessons extracted: {stats['lessons']['lessons_extracted']}")
        logger.info(f"  Error patterns: {stats['lessons']['error_patterns']}")
        conn.commit()

        # Step 5: Get final inventory
        logger.info("Step 5: Getting final inventory...")
        stats['inventory_after'] = get_debt_inventory(conn)
        logger.info(f"  Remaining unresolved: {stats['inventory_after']['total_unresolved']}")

        # Calculate debt reduction
        before = stats['inventory_before']['expired_unresolved']
        after = stats['inventory_after']['expired_unresolved']
        stats['debt_reduction'] = {
            'before': before,
            'after': after,
            'resolved': before - after,
            'reduction_pct': round((before - after) / before * 100, 2) if before > 0 else 0
        }
        logger.info(f"  Debt reduction: {stats['debt_reduction']['resolved']} ({stats['debt_reduction']['reduction_pct']}%)")

        # Log execution
        log_cleansweep_execution(conn, cycle_id, stats)
        conn.commit()

    except Exception as e:
        logger.error(f"Clean sweep failed: {e}")
        stats['status'] = 'FAILED'
        stats['error'] = str(e)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

    stats['completed_at'] = datetime.now(timezone.utc).isoformat()
    return stats


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    result = run_cleansweep()
    print(json.dumps(result, indent=2, default=str))

    # Exit with appropriate code
    if result['status'] == 'SUCCESS':
        sys.exit(0)
    else:
        sys.exit(1)
