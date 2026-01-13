#!/usr/bin/env python3
"""
CEIO EVIDENCE REFRESH DAEMON (R1)
=================================
CEO Directive: CEO-DIR-2026-009-B
Classification: STRATEGIC-CONSTITUTIONAL (Class A+)
CNRP Phase: R1 - Sensory Re-Grounding

Purpose:
    Force-refresh all external and internal evidence sources to maintain
    epistemic contact with current market reality.

Constitutional Basis:
    - ADR-013: One-True-Source (evidence_nodes is canonical)
    - ADR-017: LIDS Truth Engine (fresh evidence required)
    - CEO-DIR-2026-009-B: Cognitive freshness is constitutional

Constraint:
    Evidence freshness must never exceed staleness threshold (24h).

Schedule: Every 4 hours (0 */4 * * *)
Gate: G2 (STIG authority)
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
from psycopg2.extras import RealDictCursor, execute_values
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ceio_evidence_refresh")

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
HASH_CHAIN_PREFIX = "CNRP-R1-EVIDENCE"

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Establish database connection"""
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# EVIDENCE REFRESH LOGIC
# =============================================================================

def get_current_staleness(conn) -> Dict[str, Any]:
    """Check current staleness of evidence_nodes"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                COUNT(*) as total_nodes,
                MAX(created_at) as most_recent,
                EXTRACT(EPOCH FROM (NOW() - MAX(created_at)))/3600 as hours_stale
            FROM fhq_canonical.evidence_nodes
        """)
        return dict(cur.fetchone())


def refresh_regime_evidence(conn, limit: int = 500) -> int:
    """
    Refresh FACT nodes from sovereign_regime_state_v4.
    Uses latest regime state per asset.
    """
    with conn.cursor() as cur:
        # Get latest regime per asset from last 24h
        cur.execute("""
            WITH latest_per_asset AS (
                SELECT DISTINCT ON (asset_id)
                    asset_id, sovereign_regime, technical_regime,
                    state_probabilities, crio_dominant_driver, created_at
                FROM fhq_perception.sovereign_regime_state_v4
                WHERE created_at > NOW() - INTERVAL '24 hours'
                ORDER BY asset_id, created_at DESC
            )
            SELECT * FROM latest_per_asset
            ORDER BY created_at DESC
            LIMIT %s
        """, [limit])

        rows = cur.fetchall()
        nodes_created = 0

        for row in rows:
            asset_id, sovereign, technical, probs, crio_driver, created_at = row

            # Parse probabilities
            if isinstance(probs, str):
                probs = json.loads(probs)

            # Format probability distribution
            prob_str = ", ".join([f"{k}: {v*100:.1f}%" for k, v in sorted(probs.items(), key=lambda x: -x[1])])

            # Determine domain
            if 'BTC' in asset_id or 'ETH' in asset_id or 'SOL' in asset_id or '-USD' in asset_id:
                domain = 'CRYPTO'
            elif '=' in asset_id:
                domain = 'FOREX'
            elif asset_id.startswith('^'):
                domain = 'INDEX'
            elif '.DE' in asset_id or '.PA' in asset_id or '.L' in asset_id:
                domain = 'EUROPE'
            elif '.OL' in asset_id or '.ST' in asset_id or '.HE' in asset_id:
                domain = 'NORDIC'
            else:
                domain = 'US_EQUITY'

            # Create evidence content
            content = f"Asset {asset_id} is in {sovereign} regime (technical: {technical}). Distribution: {prob_str}. Primary driver: {crio_driver or 'unknown'}."
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            # Insert or update evidence node
            cur.execute("""
                INSERT INTO fhq_canonical.evidence_nodes (
                    evidence_id, content, content_type, source_type, source_reference,
                    domain, entity_type, entity_id, temporal_scope, data_timestamp,
                    expires_at, ttl_regime, confidence_score, verification_status,
                    content_hash, created_by, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), %s, 'FACT', 'DATABASE', %s,
                    %s, 'ASSET', %s, 'CURRENT', %s,
                    %s, 'STANDARD', 0.95, 'VERIFIED',
                    %s, 'CEIO', NOW(), NOW()
                )
                ON CONFLICT (content_hash) DO UPDATE SET
                    updated_at = NOW(),
                    data_timestamp = EXCLUDED.data_timestamp
            """, (
                content,
                f"fhq_perception.sovereign_regime_state_v4:{asset_id}",
                domain,
                asset_id,
                created_at,
                datetime.now(timezone.utc) + timedelta(hours=24),
                content_hash
            ))
            nodes_created += 1

        return nodes_created


def refresh_price_evidence(conn, limit: int = 500) -> int:
    """Refresh METRIC nodes from market prices"""
    with conn.cursor() as cur:
        cur.execute("""
            WITH latest_prices AS (
                SELECT DISTINCT ON (canonical_id)
                    canonical_id, close, volume, timestamp
                FROM fhq_market.prices
                WHERE timestamp > NOW() - INTERVAL '24 hours'
                ORDER BY canonical_id, timestamp DESC
            )
            SELECT * FROM latest_prices
            ORDER BY timestamp DESC
            LIMIT %s
        """, [limit])

        rows = cur.fetchall()
        nodes_created = 0

        for row in rows:
            symbol, close_price, volume, timestamp = row

            # Determine domain
            if 'BTC' in symbol or 'ETH' in symbol or '-USD' in symbol:
                domain = 'CRYPTO'
            elif '=' in symbol:
                domain = 'FOREX'
            else:
                domain = 'EQUITY'

            content = f"{symbol} last traded at ${close_price:.2f} with volume {volume:,.0f} as of {timestamp.isoformat()}"
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            cur.execute("""
                INSERT INTO fhq_canonical.evidence_nodes (
                    evidence_id, content, content_type, source_type, source_reference,
                    domain, entity_type, entity_id, temporal_scope, data_timestamp,
                    expires_at, ttl_regime, confidence_score, verification_status,
                    content_hash, created_by, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), %s, 'METRIC', 'DATABASE', %s,
                    %s, 'PRICE', %s, 'CURRENT', %s,
                    %s, 'STANDARD', 0.99, 'VERIFIED',
                    %s, 'CEIO', NOW(), NOW()
                )
                ON CONFLICT (content_hash) DO UPDATE SET
                    updated_at = NOW(),
                    data_timestamp = EXCLUDED.data_timestamp
            """, (
                content,
                f"fhq_market.prices:{symbol}",
                domain,
                symbol,
                timestamp,
                datetime.now(timezone.utc) + timedelta(hours=12),
                content_hash
            ))
            nodes_created += 1

        return nodes_created


def log_cnrp_execution(conn, cycle_id: str, phase: str, daemon_name: str,
                       status: str, records: int, evidence_hash: str,
                       metadata: Dict, started_at: datetime = None) -> str:
    """Log CNRP execution to governance with proper latency instrumentation.

    CEO-DIR-2026-047 GAP-004: Latency must be measured as completed_at - started_at.
    The started_at timestamp must be captured BEFORE execution begins.
    """
    completed_at = datetime.now(timezone.utc)

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
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING execution_id
        """, (
            cycle_id, phase, daemon_name, status, records,
            evidence_hash, json.dumps(metadata, default=str),
            started_at, completed_at
        ))
        return str(cur.fetchone()[0])


def log_governance_action(conn, stats: Dict[str, Any]) -> str:
    """Log refresh to governance actions"""
    evidence_id = str(uuid.uuid4())
    evidence_hash = hashlib.sha256(json.dumps(stats, default=str).encode()).hexdigest()

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
                'CNRP_R1_EVIDENCE_REFRESH',
                'fhq_canonical.evidence_nodes',
                'DAEMON_EXECUTION',
                'CEIO',
                'EXECUTED',
                'CEO-DIR-2026-009-B: Epistemic freshness maintained via constitutional refresh',
                %s
            )
            RETURNING action_id
        """, (json.dumps({
            'evidence_id': evidence_id,
            'directive': 'CEO-DIR-2026-009-B',
            'cnrp_phase': 'R1',
            'daemon': 'ceio_evidence_refresh_daemon',
            'statistics': stats,
            'evidence_hash': evidence_hash,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, default=str),))

    return evidence_id


def run_evidence_refresh() -> Dict[str, Any]:
    """Main execution function for R1 Evidence Refresh"""
    logger.info("=" * 60)
    logger.info("CNRP-001 PHASE R1: CEIO EVIDENCE REFRESH DAEMON")
    logger.info("Directive: CEO-DIR-2026-009-B")
    logger.info("=" * 60)

    # CEO-DIR-2026-047 GAP-004: Capture started_at BEFORE any execution
    execution_started_at = datetime.now(timezone.utc)

    cycle_id = f"CNRP-{execution_started_at.strftime('%Y%m%d-%H%M%S')}"

    stats = {
        'cycle_id': cycle_id,
        'started_at': execution_started_at.isoformat(),
        'phase': 'R1',
        'daemon': 'ceio_evidence_refresh_daemon',
        'regime_nodes_refreshed': 0,
        'price_nodes_refreshed': 0,
        'total_nodes_refreshed': 0,
        'staleness_before_hours': None,
        'staleness_after_hours': None,
        'status': 'SUCCESS'
    }

    conn = None
    try:
        conn = get_db_connection()

        # Check current staleness
        staleness_before = get_current_staleness(conn)
        stats['staleness_before_hours'] = round(staleness_before['hours_stale'], 2)
        logger.info(f"Current staleness: {stats['staleness_before_hours']}h (threshold: {STALENESS_THRESHOLD_HOURS}h)")

        # Refresh regime evidence
        logger.info("Refreshing regime evidence from sovereign_regime_state_v4...")
        regime_count = refresh_regime_evidence(conn)
        stats['regime_nodes_refreshed'] = regime_count
        logger.info(f"Refreshed {regime_count} regime evidence nodes")

        # Refresh price evidence
        logger.info("Refreshing price evidence from fhq_market.prices...")
        price_count = refresh_price_evidence(conn)
        stats['price_nodes_refreshed'] = price_count
        logger.info(f"Refreshed {price_count} price evidence nodes")

        stats['total_nodes_refreshed'] = regime_count + price_count

        conn.commit()

        # Check new staleness
        staleness_after = get_current_staleness(conn)
        stats['staleness_after_hours'] = round(staleness_after['hours_stale'], 2)

        # Log CNRP execution with proper latency instrumentation (CEO-DIR-2026-047 GAP-004)
        evidence_hash = hashlib.sha256(json.dumps(stats, default=str).encode()).hexdigest()
        log_cnrp_execution(conn, cycle_id, 'R1', 'ceio_evidence_refresh_daemon',
                          'SUCCESS', stats['total_nodes_refreshed'], evidence_hash, stats,
                          started_at=execution_started_at)

        # Log governance action
        evidence_id = log_governance_action(conn, stats)
        stats['evidence_id'] = evidence_id

        conn.commit()

        # Check if threshold now met
        if stats['staleness_after_hours'] <= STALENESS_THRESHOLD_HOURS:
            logger.info(f"Staleness threshold MET: {stats['staleness_after_hours']}h <= {STALENESS_THRESHOLD_HOURS}h")
            stats['threshold_status'] = 'MET'
        else:
            logger.warning(f"Staleness threshold NOT MET: {stats['staleness_after_hours']}h > {STALENESS_THRESHOLD_HOURS}h")
            stats['threshold_status'] = 'NOT_MET'

        logger.info(f"R1 Evidence Refresh complete: {stats['total_nodes_refreshed']} nodes refreshed")

    except Exception as e:
        logger.error(f"R1 Evidence Refresh failed: {e}")
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
    result = run_evidence_refresh()
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result['status'] == 'SUCCESS' else 1)
