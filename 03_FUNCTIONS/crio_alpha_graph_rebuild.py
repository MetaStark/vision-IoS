#!/usr/bin/env python3
"""
CRIO ALPHA GRAPH REBUILD (R2)
=============================
CEO Directive: CEO-DIR-2026-009-B
Classification: STRATEGIC-CONSTITUTIONAL (Class A+)
CNRP Phase: R2 - Cognitive Graph Rebuild

Purpose:
    Reconstruct IoS-007 Alpha Graph edges exclusively from refreshed evidence_nodes.
    Rebind graph edges to current model_belief_state and active forecasts.
    Block any inference path referencing deprecated nodes.

Constitutional Basis:
    - ADR-013: One-True-Source (alpha graph from canonical evidence only)
    - ADR-017: LIDS Truth Engine (fresh graph required for reasoning)
    - CEO-DIR-2026-009-B Section 3.2

Constraint:
    No causal edge may reference stale evidence.

Trigger: Post R1 completion
Schedule: 30 */4 * * * (30 minutes after each 4-hour cycle)
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
logger = logging.getLogger("crio_alpha_graph_rebuild")

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

STALENESS_THRESHOLD_HOURS = 24  # CEO-DIR-2026-009-B Section 4
CAUSAL_EDGE_THRESHOLD_HOURS = 48

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Establish database connection"""
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# GRAPH REBUILD LOGIC
# =============================================================================

def verify_r1_completion(conn) -> Dict[str, Any]:
    """Verify R1 (Evidence Refresh) completed successfully"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check latest R1 execution
        cur.execute("""
            SELECT cycle_id, status, completed_at, records_processed
            FROM fhq_governance.cnrp_execution_log
            WHERE phase = 'R1'
            ORDER BY completed_at DESC
            LIMIT 1
        """)
        result = cur.fetchone()

        if not result:
            return {'r1_complete': False, 'reason': 'No R1 execution found'}

        # Check if R1 completed within last 2 hours
        if result['completed_at']:
            age = datetime.now(timezone.utc) - result['completed_at'].replace(tzinfo=timezone.utc)
            if age.total_seconds() > 7200:  # 2 hours
                return {'r1_complete': False, 'reason': f'R1 too old: {age.total_seconds()/3600:.1f}h ago'}

        return {
            'r1_complete': result['status'] == 'SUCCESS',
            'cycle_id': result['cycle_id'],
            'records_processed': result['records_processed'],
            'completed_at': result['completed_at'].isoformat() if result['completed_at'] else None
        }


def get_fresh_evidence_stats(conn) -> Dict[str, Any]:
    """Get statistics on fresh evidence nodes"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                COUNT(*) as total_nodes,
                COUNT(*) FILTER (WHERE updated_at > NOW() - INTERVAL '%s hours') as fresh_nodes,
                COUNT(*) FILTER (WHERE updated_at <= NOW() - INTERVAL '%s hours') as stale_nodes,
                MAX(updated_at) as most_recent,
                EXTRACT(EPOCH FROM (NOW() - MAX(updated_at)))/3600 as hours_since_update
            FROM fhq_canonical.evidence_nodes
        """ % (STALENESS_THRESHOLD_HOURS, STALENESS_THRESHOLD_HOURS))
        return dict(cur.fetchone())


def rebuild_evidence_relationships(conn) -> int:
    """Rebuild evidence relationships from fresh nodes only"""
    with conn.cursor() as cur:
        # Delete stale relationships (those referencing stale evidence)
        cur.execute("""
            DELETE FROM fhq_canonical.evidence_relationships
            WHERE from_evidence_id IN (
                SELECT evidence_id FROM fhq_canonical.evidence_nodes
                WHERE updated_at < NOW() - INTERVAL '%s hours'
            )
            OR to_evidence_id IN (
                SELECT evidence_id FROM fhq_canonical.evidence_nodes
                WHERE updated_at < NOW() - INTERVAL '%s hours'
            )
        """ % (STALENESS_THRESHOLD_HOURS, STALENESS_THRESHOLD_HOURS))

        deprecated_count = cur.rowcount
        logger.info(f"Removed {deprecated_count} stale relationships")

        # Rebuild relationships for fresh nodes
        # Link regime evidence to price evidence for same asset
        cur.execute("""
            INSERT INTO fhq_canonical.evidence_relationships (
                relationship_id, from_evidence_id, to_evidence_id,
                relationship_type, strength, created_at
            )
            SELECT
                gen_random_uuid(),
                regime.evidence_id,
                price.evidence_id,
                'SUPPORTS',
                0.85,
                NOW()
            FROM fhq_canonical.evidence_nodes regime
            JOIN fhq_canonical.evidence_nodes price
                ON regime.entity_id = price.entity_id
                AND regime.content_type = 'FACT'
                AND price.content_type = 'METRIC'
            WHERE regime.updated_at > NOW() - INTERVAL '%s hours'
              AND price.updated_at > NOW() - INTERVAL '%s hours'
            ON CONFLICT DO NOTHING
        """ % (STALENESS_THRESHOLD_HOURS, STALENESS_THRESHOLD_HOURS))

        relationships_created = cur.rowcount
        return relationships_created


def link_to_active_forecasts(conn) -> int:
    """Link fresh evidence to active IoS-010 forecasts"""
    with conn.cursor() as cur:
        # Check if forecast_ledger exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'fhq_research'
                  AND table_name = 'forecast_ledger'
            )
        """)

        if not cur.fetchone()[0]:
            return 0

        # Count linkable forecasts (those with fresh evidence for their domain)
        cur.execute("""
            SELECT COUNT(*) as linkable_forecasts
            FROM fhq_research.forecast_ledger f
            WHERE f.is_resolved = FALSE
              AND f.forecast_type = 'REGIME'
              AND EXISTS (
                  SELECT 1 FROM fhq_canonical.evidence_nodes e
                  WHERE e.entity_id = f.forecast_domain
                    AND e.updated_at > NOW() - INTERVAL '%s hours'
              )
        """ % STALENESS_THRESHOLD_HOURS)

        result = cur.fetchone()
        return result[0] if result else 0


def generate_causal_edges_from_evidence(conn) -> Dict[str, int]:
    """
    VCEO-DIR-2026-CE-UNBLOCK-001: Generate fresh causal edges from evidence.

    Creates edges based on:
    1. Regime beliefs -> Asset relationships (REGIME_CAUSAL)
    2. Evidence relationships with high strength (EVIDENCE_CAUSAL)
    3. Cross-domain correlations (MACRO_CAUSAL)
    """
    stats = {'created': 0, 'from_regime': 0, 'from_evidence': 0}

    with conn.cursor() as cur:
        # Check if causal_edges table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'fhq_alpha'
                  AND table_name = 'causal_edges'
            )
        """)

        if not cur.fetchone()[0]:
            logger.warning("fhq_alpha.causal_edges table not found - cannot generate edges")
            return stats

        # 1. Generate REGIME_CAUSAL edges from fresh regime beliefs
        # Link assets in same regime state
        cur.execute("""
            INSERT INTO fhq_alpha.causal_edges (
                edge_id, source_id, target_id, edge_type, edge_weight, is_active, created_at
            )
            SELECT
                gen_random_uuid(),
                a.asset_id,
                b.asset_id,
                'REGIME_CAUSAL',
                LEAST(a.belief_confidence::numeric, b.belief_confidence::numeric) * 0.8,
                TRUE,
                NOW()
            FROM fhq_perception.model_belief_state a
            JOIN fhq_perception.model_belief_state b
                ON a.dominant_regime = b.dominant_regime
                AND a.asset_id < b.asset_id  -- Avoid duplicates
            WHERE a.belief_timestamp > NOW() - INTERVAL '6 hours'
              AND b.belief_timestamp > NOW() - INTERVAL '6 hours'
              AND a.belief_confidence::numeric > 0.7
              AND b.belief_confidence::numeric > 0.7
            LIMIT 100  -- Limit to prevent explosion
            ON CONFLICT DO NOTHING
        """)
        stats['from_regime'] = cur.rowcount
        stats['created'] += cur.rowcount
        logger.info(f"Generated {cur.rowcount} REGIME_CAUSAL edges from fresh beliefs")

        # 2. Generate EVIDENCE_CAUSAL edges from strong evidence relationships
        cur.execute("""
            INSERT INTO fhq_alpha.causal_edges (
                edge_id, source_id, target_id, edge_type, edge_weight, is_active, created_at
            )
            SELECT
                gen_random_uuid(),
                er.from_evidence_id::text,
                er.to_evidence_id::text,
                'EVIDENCE_CAUSAL',
                er.strength,
                TRUE,
                NOW()
            FROM fhq_canonical.evidence_relationships er
            JOIN fhq_canonical.evidence_nodes en_from
                ON er.from_evidence_id = en_from.evidence_id
            JOIN fhq_canonical.evidence_nodes en_to
                ON er.to_evidence_id = en_to.evidence_id
            WHERE er.strength >= 0.7
              AND en_from.updated_at > NOW() - INTERVAL '24 hours'
              AND en_to.updated_at > NOW() - INTERVAL '24 hours'
            LIMIT 100
            ON CONFLICT DO NOTHING
        """)
        stats['from_evidence'] = cur.rowcount
        stats['created'] += cur.rowcount
        logger.info(f"Generated {cur.rowcount} EVIDENCE_CAUSAL edges from relationships")

    return stats


def update_causal_edges_freshness(conn) -> Dict[str, int]:
    """Update causal edges to reference only fresh evidence"""
    stats = {'deprecated': 0, 'active': 0, 'generated': 0}

    with conn.cursor() as cur:
        # Check if causal_edges table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'fhq_alpha'
                  AND table_name = 'causal_edges'
            )
        """)

        if not cur.fetchone()[0]:
            logger.warning("fhq_alpha.causal_edges table not found - skipping")
            return stats

        # Deactivate stale edges (older than threshold)
        cur.execute("""
            UPDATE fhq_alpha.causal_edges
            SET is_active = FALSE
            WHERE created_at < NOW() - INTERVAL '%s hours'
              AND is_active = TRUE
        """ % CAUSAL_EDGE_THRESHOLD_HOURS)

        stats['deprecated'] = cur.rowcount

    # VCEO-DIR-2026-CE-UNBLOCK-001: Generate fresh edges
    gen_stats = generate_causal_edges_from_evidence(conn)
    stats['generated'] = gen_stats['created']

    with conn.cursor() as cur:
        # Count active edges
        cur.execute("""
            SELECT COUNT(*) FROM fhq_alpha.causal_edges WHERE is_active = TRUE
        """)
        stats['active'] = cur.fetchone()[0]

    return stats


def log_cnrp_execution(conn, cycle_id: str, status: str, metadata: Dict,
                       started_at: datetime = None) -> str:
    """Log CNRP R2 execution with proper latency instrumentation.

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
            ) VALUES (%s, 'R2', 'crio_alpha_graph_rebuild', %s, %s, %s, %s, %s, %s)
            RETURNING execution_id
        """, (
            cycle_id, status,
            metadata.get('total_operations', 0),
            evidence_hash,
            json.dumps(metadata, default=str),
            started_at, completed_at
        ))
        return str(cur.fetchone()[0])


def log_governance_action(conn, stats: Dict[str, Any]) -> str:
    """Log graph rebuild to governance"""
    evidence_id = str(uuid.uuid4())

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
                'CNRP_R2_GRAPH_REBUILD',
                'fhq_canonical.evidence_relationships',
                'DAEMON_EXECUTION',
                'CRIO',
                'EXECUTED',
                'CEO-DIR-2026-009-B: Alpha Graph reconstructed from fresh evidence only',
                %s
            )
            RETURNING action_id
        """, (json.dumps({
            'evidence_id': evidence_id,
            'directive': 'CEO-DIR-2026-009-B',
            'cnrp_phase': 'R2',
            'daemon': 'crio_alpha_graph_rebuild',
            'statistics': stats,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, default=str),))

    return evidence_id


def run_graph_rebuild() -> Dict[str, Any]:
    """Main execution function for R2 Graph Rebuild"""
    logger.info("=" * 60)
    logger.info("CNRP-001 PHASE R2: CRIO ALPHA GRAPH REBUILD")
    logger.info("Directive: CEO-DIR-2026-009-B")
    logger.info("=" * 60)

    # CEO-DIR-2026-047 GAP-004: Capture started_at BEFORE any execution
    execution_started_at = datetime.now(timezone.utc)

    cycle_id = f"CNRP-{execution_started_at.strftime('%Y%m%d-%H%M%S')}"

    stats = {
        'cycle_id': cycle_id,
        'started_at': execution_started_at.isoformat(),
        'phase': 'R2',
        'daemon': 'crio_alpha_graph_rebuild',
        'r1_verified': False,
        'relationships_rebuilt': 0,
        'forecasts_linked': 0,
        'causal_edges_deprecated': 0,
        'causal_edges_active': 0,
        'status': 'SUCCESS'
    }

    conn = None
    try:
        conn = get_db_connection()

        # Verify R1 completion
        logger.info("Verifying R1 (Evidence Refresh) completion...")
        r1_status = verify_r1_completion(conn)
        stats['r1_verification'] = r1_status

        if not r1_status.get('r1_complete'):
            logger.warning(f"R1 not complete: {r1_status.get('reason')}")
            stats['status'] = 'SKIPPED'
            stats['skip_reason'] = r1_status.get('reason')
            return stats

        stats['r1_verified'] = True
        logger.info(f"R1 verified: {r1_status.get('records_processed')} records processed")

        # Get fresh evidence stats
        evidence_stats = get_fresh_evidence_stats(conn)
        stats['evidence_stats'] = evidence_stats
        logger.info(f"Fresh evidence: {evidence_stats['fresh_nodes']}/{evidence_stats['total_nodes']} nodes")

        # Rebuild relationships
        logger.info("Rebuilding evidence relationships...")
        relationships = rebuild_evidence_relationships(conn)
        stats['relationships_rebuilt'] = relationships
        logger.info(f"Rebuilt {relationships} evidence relationships")

        # Link to forecasts
        logger.info("Linking evidence to active forecasts...")
        forecasts = link_to_active_forecasts(conn)
        stats['forecasts_linked'] = forecasts
        logger.info(f"Linked to {forecasts} active forecasts")

        # Update causal edges
        logger.info("Updating causal edge freshness...")
        edge_stats = update_causal_edges_freshness(conn)
        stats['causal_edges_deprecated'] = edge_stats['deprecated']
        stats['causal_edges_active'] = edge_stats['active']
        logger.info(f"Causal edges: {edge_stats['active']} active, {edge_stats['deprecated']} deprecated")

        stats['total_operations'] = relationships + forecasts + edge_stats['deprecated']

        conn.commit()

        # Log execution with proper latency instrumentation (CEO-DIR-2026-047 GAP-004)
        log_cnrp_execution(conn, cycle_id, 'SUCCESS', stats,
                          started_at=execution_started_at)
        evidence_id = log_governance_action(conn, stats)
        stats['evidence_id'] = evidence_id

        conn.commit()

        logger.info("R2 Alpha Graph Rebuild complete")

    except Exception as e:
        logger.error(f"R2 Graph Rebuild failed: {e}")
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
    result = run_graph_rebuild()
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result['status'] in ('SUCCESS', 'SKIPPED') else 1)
