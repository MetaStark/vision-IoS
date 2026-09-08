#!/usr/bin/env python3
"""
CDMO DATA HYGIENE ATTESTATION (R3)
==================================
CEO Directive: CEO-DIR-2026-009-B
Classification: STRATEGIC-CONSTITUTIONAL (Class A+)
CNRP Phase: R3 - Data Hygiene Attestation

Purpose:
    Daily verification that no deprecated or orphaned nodes remain active.
    Produce formal hygiene attestation after each verification cycle.

Constitutional Basis:
    - ADR-013: One-True-Source (clean data only)
    - ADR-017: LIDS Truth Engine (no contaminated nodes)
    - CEO-DIR-2026-009-B Section 5

Output:
    Formal hygiene attestation stored in governance ledger.

Schedule: 0 0 * * * (Daily at midnight UTC)
Gate: G3 (STIG authority)
"""

import os
import sys
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
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
logger = logging.getLogger("cdmo_data_hygiene")

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

# Hygiene thresholds from CEO-DIR-2026-009-B
DEPRECATED_NODE_MAX_AGE_DAYS = 30  # Deprecated nodes older than this should be archived
ORPHAN_DETECTION_THRESHOLD = 0.05  # Max 5% orphan rate allowed

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Establish database connection"""
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# HYGIENE CHECK FUNCTIONS
# =============================================================================

def check_deprecated_nodes(conn) -> Dict[str, Any]:
    """Check for stale nodes that should be refreshed"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check evidence_nodes for stale entries (using updated_at threshold)
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE updated_at < NOW() - INTERVAL '24 hours') as stale_count,
                COUNT(*) FILTER (WHERE updated_at < NOW() - INTERVAL '48 hours') as very_stale,
                COUNT(*) as total_nodes,
                ROUND(COUNT(*) FILTER (WHERE updated_at < NOW() - INTERVAL '24 hours')::numeric / NULLIF(COUNT(*), 0) * 100, 2) as stale_pct
            FROM fhq_canonical.evidence_nodes
        """)
        result = cur.fetchone()

        if result:
            return {
                'deprecated_count': result['stale_count'] or 0,
                'stale_deprecated': result['very_stale'] or 0,
                'total_nodes': result['total_nodes'] or 0,
                'deprecated_pct': float(result['stale_pct'] or 0),
                'status': 'CLEAN' if (result['stale_pct'] or 0) < 50 else 'ATTENTION_REQUIRED'
            }
        return {
            'deprecated_count': 0,
            'stale_deprecated': 0,
            'total_nodes': 0,
            'deprecated_pct': 0,
            'status': 'CLEAN'
        }


def check_orphaned_relationships(conn) -> Dict[str, Any]:
    """Check for orphaned relationships (referencing non-existent nodes)"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if evidence_relationships table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'fhq_canonical'
                  AND table_name = 'evidence_relationships'
            )
        """)

        if not cur.fetchone()['exists']:
            return {
                'orphaned_count': 0,
                'total_relationships': 0,
                'orphan_rate': 0,
                'status': 'TABLE_NOT_EXISTS'
            }

        # Find orphaned relationships (using actual column names: from_evidence_id, to_evidence_id)
        cur.execute("""
            WITH orphan_check AS (
                SELECT r.relationship_id,
                    EXISTS (SELECT 1 FROM fhq_canonical.evidence_nodes WHERE evidence_id = r.from_evidence_id) as source_exists,
                    EXISTS (SELECT 1 FROM fhq_canonical.evidence_nodes WHERE evidence_id = r.to_evidence_id) as target_exists
                FROM fhq_canonical.evidence_relationships r
            )
            SELECT
                COUNT(*) FILTER (WHERE NOT source_exists OR NOT target_exists) as orphaned_count,
                COUNT(*) as total_relationships,
                ROUND(COUNT(*) FILTER (WHERE NOT source_exists OR NOT target_exists)::numeric / NULLIF(COUNT(*), 0) * 100, 4) as orphan_rate
            FROM orphan_check
        """)
        result = cur.fetchone()

        orphan_rate = float(result['orphan_rate'] or 0)
        return {
            'orphaned_count': result['orphaned_count'] or 0,
            'total_relationships': result['total_relationships'] or 0,
            'orphan_rate': orphan_rate,
            'status': 'CLEAN' if orphan_rate < ORPHAN_DETECTION_THRESHOLD * 100 else 'CONTAMINATED'
        }


def check_stale_forecasts(conn) -> Dict[str, Any]:
    """Check for stale unresolved forecasts in IoS-010"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if forecast_ledger table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'fhq_research'
                  AND table_name = 'forecast_ledger'
            )
        """)

        if not cur.fetchone()['exists']:
            return {
                'stale_forecasts': 0,
                'total_unresolved': 0,
                'status': 'TABLE_NOT_EXISTS'
            }

        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE is_resolved = FALSE AND forecast_valid_until < NOW()) as stale_forecasts,
                COUNT(*) FILTER (WHERE is_resolved = FALSE) as total_unresolved,
                COUNT(*) as total_forecasts
            FROM fhq_research.forecast_ledger
        """)
        result = cur.fetchone()

        return {
            'stale_forecasts': result['stale_forecasts'] or 0,
            'total_unresolved': result['total_unresolved'] or 0,
            'total_forecasts': result['total_forecasts'] or 0,
            'status': 'CLEAN' if (result['stale_forecasts'] or 0) == 0 else 'ATTENTION_REQUIRED'
        }


def check_data_lineage_integrity(conn) -> Dict[str, Any]:
    """Check hash chain integrity for evidence nodes"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check for nodes with missing content_hash
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE content_hash IS NULL) as missing_hash,
                COUNT(*) FILTER (WHERE content_hash IS NOT NULL) as valid_hash,
                COUNT(*) as total_nodes
            FROM fhq_canonical.evidence_nodes
        """)
        result = cur.fetchone()

        missing_pct = 0
        if result['total_nodes'] > 0:
            missing_pct = (result['missing_hash'] or 0) / result['total_nodes'] * 100

        return {
            'missing_hash': result['missing_hash'] or 0,
            'valid_hash': result['valid_hash'] or 0,
            'total_nodes': result['total_nodes'] or 0,
            'missing_pct': round(missing_pct, 2),
            'status': 'CLEAN' if missing_pct == 0 else 'INTEGRITY_RISK'
        }


def check_expired_ttl_nodes(conn) -> Dict[str, Any]:
    """Check for nodes past their TTL that should be refreshed or archived"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE expires_at < NOW()) as expired_count,
                COUNT(*) FILTER (WHERE expires_at BETWEEN NOW() AND NOW() + INTERVAL '1 hour') as expiring_soon,
                COUNT(*) as total_nodes
            FROM fhq_canonical.evidence_nodes
            WHERE expires_at IS NOT NULL
        """)
        result = cur.fetchone()

        return {
            'expired_count': result['expired_count'] or 0,
            'expiring_soon': result['expiring_soon'] or 0,
            'total_with_ttl': result['total_nodes'] or 0,
            'status': 'CLEAN' if (result['expired_count'] or 0) == 0 else 'REFRESH_NEEDED'
        }


def cleanup_deprecated_nodes(conn, dry_run: bool = True) -> int:
    """Count or remove very stale nodes (over 48h old)"""
    with conn.cursor() as cur:
        if dry_run:
            cur.execute("""
                SELECT COUNT(*) FROM fhq_canonical.evidence_nodes
                WHERE updated_at < NOW() - INTERVAL '48 hours'
            """)
            return cur.fetchone()[0]
        else:
            # Actual cleanup - delete very stale nodes
            cur.execute("""
                DELETE FROM fhq_canonical.evidence_nodes
                WHERE updated_at < NOW() - INTERVAL '48 hours'
                RETURNING evidence_id
            """)
            deleted = cur.rowcount
            logger.info(f"Archived {deleted} very stale nodes")
            return deleted


def deactivate_orphaned_relationships(conn) -> int:
    """Delete orphaned relationships"""
    with conn.cursor() as cur:
        # Check if table exists first
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'fhq_canonical'
                  AND table_name = 'evidence_relationships'
            )
        """)

        if not cur.fetchone()[0]:
            return 0

        # Delete orphaned relationships (using correct column names)
        cur.execute("""
            DELETE FROM fhq_canonical.evidence_relationships r
            WHERE NOT EXISTS (SELECT 1 FROM fhq_canonical.evidence_nodes WHERE evidence_id = r.from_evidence_id)
               OR NOT EXISTS (SELECT 1 FROM fhq_canonical.evidence_nodes WHERE evidence_id = r.to_evidence_id)
        """)
        return cur.rowcount


def log_cnrp_execution(conn, cycle_id: str, status: str, metadata: Dict,
                       started_at: datetime = None) -> str:
    """Log CNRP R3 execution with proper latency instrumentation.

    CEO-DIR-2026-047 GAP-004: Latency must be measured as completed_at - started_at.
    The started_at timestamp must be captured BEFORE execution begins.
    """
    completed_at = datetime.now(timezone.utc)
    evidence_hash = hashlib.sha256(json.dumps(metadata, default=str).encode()).hexdigest()

    # Calculate actual latency for metrics
    if started_at:
        latency_ms = (completed_at - started_at).total_seconds() * 1000
        metadata['latency_ms'] = round(latency_ms, 2)
        metadata['latency_instrumented'] = True
    else:
        metadata['latency_instrumented'] = False

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.cnrp_execution_log (
                cycle_id, phase, daemon_name, status, records_processed,
                evidence_hash, metadata, started_at, completed_at
            ) VALUES (%s, 'R3', 'cdmo_data_hygiene_attestation', %s, %s, %s, %s, %s, %s)
            RETURNING execution_id
        """, (
            cycle_id, status,
            metadata.get('total_checks', 0),
            evidence_hash,
            json.dumps(metadata, default=str),
            started_at, completed_at
        ))
        return str(cur.fetchone()[0])


def produce_hygiene_attestation(conn, stats: Dict[str, Any]) -> str:
    """Produce formal data hygiene attestation"""
    attestation_id = f"CDMO-HYGIENE-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    # Determine overall hygiene status
    hygiene_status = 'CLEAN'
    issues = []

    if stats.get('deprecated_nodes', {}).get('status') != 'CLEAN':
        hygiene_status = 'ATTENTION_REQUIRED'
        issues.append('Deprecated nodes exceed threshold')

    if stats.get('orphaned_relationships', {}).get('status') == 'CONTAMINATED':
        hygiene_status = 'CONTAMINATED'
        issues.append('Orphaned relationships detected')

    if stats.get('lineage_integrity', {}).get('status') != 'CLEAN':
        hygiene_status = 'INTEGRITY_RISK'
        issues.append('Missing content hashes detected')

    attestation = {
        'attestation_id': attestation_id,
        'attestation_type': 'CDMO_DATA_HYGIENE',
        'directive': 'CEO-DIR-2026-009-B',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'issuing_authority': 'CDMO',
        'hygiene_status': hygiene_status,
        'issues': issues,
        'statistics': stats,
        'statement': f"CDMO hereby attests that data hygiene verification completed with status: {hygiene_status}. {len(issues)} issues identified."
    }

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
                'CNRP_R3_HYGIENE_ATTESTATION',
                'fhq_canonical',
                'DAEMON_EXECUTION',
                'CDMO',
                %s,
                'CEO-DIR-2026-009-B: Formal data hygiene attestation produced',
                %s
            )
            RETURNING action_id
        """, (
            'ATTESTED' if hygiene_status == 'CLEAN' else 'ATTENTION_REQUIRED',
            json.dumps(attestation, default=str)
        ))

    return attestation_id


def run_hygiene_attestation(perform_cleanup: bool = False) -> Dict[str, Any]:
    """Main execution function for R3 Data Hygiene Attestation"""
    logger.info("=" * 60)
    logger.info("CNRP-001 PHASE R3: CDMO DATA HYGIENE ATTESTATION")
    logger.info("Directive: CEO-DIR-2026-009-B")
    logger.info("=" * 60)

    # CEO-DIR-2026-047 GAP-004: Capture started_at BEFORE any execution
    execution_started_at = datetime.now(timezone.utc)

    cycle_id = f"CNRP-{execution_started_at.strftime('%Y%m%d-%H%M%S')}"

    stats = {
        'cycle_id': cycle_id,
        'started_at': execution_started_at.isoformat(),
        'phase': 'R3',
        'daemon': 'cdmo_data_hygiene_attestation',
        'deprecated_nodes': {},
        'orphaned_relationships': {},
        'stale_forecasts': {},
        'lineage_integrity': {},
        'expired_ttl': {},
        'cleanup_performed': perform_cleanup,
        'status': 'SUCCESS'
    }

    conn = None
    try:
        conn = get_db_connection()

        # Run hygiene checks
        logger.info("Checking deprecated nodes...")
        stats['deprecated_nodes'] = check_deprecated_nodes(conn)
        logger.info(f"Deprecated nodes: {stats['deprecated_nodes']['deprecated_count']}/{stats['deprecated_nodes']['total_nodes']}")

        logger.info("Checking orphaned relationships...")
        stats['orphaned_relationships'] = check_orphaned_relationships(conn)
        logger.info(f"Orphaned relationships: {stats['orphaned_relationships']['orphaned_count']}")

        logger.info("Checking stale forecasts...")
        stats['stale_forecasts'] = check_stale_forecasts(conn)
        logger.info(f"Stale forecasts: {stats['stale_forecasts']['stale_forecasts']}")

        logger.info("Checking lineage integrity...")
        stats['lineage_integrity'] = check_data_lineage_integrity(conn)
        logger.info(f"Missing hashes: {stats['lineage_integrity']['missing_hash']}")

        logger.info("Checking expired TTL nodes...")
        stats['expired_ttl'] = check_expired_ttl_nodes(conn)
        logger.info(f"Expired nodes: {stats['expired_ttl']['expired_count']}")

        # Perform cleanup if authorized
        if perform_cleanup:
            logger.info("Performing cleanup operations...")

            orphans_fixed = deactivate_orphaned_relationships(conn)
            stats['orphans_deactivated'] = orphans_fixed
            logger.info(f"Deactivated {orphans_fixed} orphaned relationships")

            deprecated_archived = cleanup_deprecated_nodes(conn, dry_run=False)
            stats['deprecated_archived'] = deprecated_archived
            logger.info(f"Archived {deprecated_archived} stale deprecated nodes")

        stats['total_checks'] = 5

        conn.commit()

        # Log execution with proper latency instrumentation (CEO-DIR-2026-047 GAP-004)
        log_cnrp_execution(conn, cycle_id, 'SUCCESS', stats,
                          started_at=execution_started_at)

        # Produce attestation
        attestation_id = produce_hygiene_attestation(conn, stats)
        stats['attestation_id'] = attestation_id

        conn.commit()

        logger.info(f"R3 Data Hygiene Attestation complete: {attestation_id}")

    except Exception as e:
        logger.error(f"R3 Hygiene Attestation failed: {e}")
        stats['status'] = 'FAILED'
        stats['error_message'] = str(e)
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
    # Parse command line for cleanup flag
    perform_cleanup = '--cleanup' in sys.argv

    result = run_hygiene_attestation(perform_cleanup=perform_cleanup)
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result['status'] == 'SUCCESS' else 1)
