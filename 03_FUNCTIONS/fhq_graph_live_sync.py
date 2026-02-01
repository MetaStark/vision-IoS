"""
FHQ Graph Live Sync Daemon
CEO-DIR-2026-COGNITIVE-ENGINES-001

Corporate Standard: Live update synchronization for fhq_graph.nodes
- Syncs assets from sovereign_regime_state_v4 to fhq_graph.nodes
- Auto-creates evidence_nodes for new graph nodes
- Maintains ACTIVE/INACTIVE status based on data freshness
- Runs as scheduled daemon or one-shot sync

Author: STIG (CTO)
Date: 2026-01-04
"""

import psycopg2
from psycopg2.extras import execute_values
import uuid
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple


def get_db_connection():
    return psycopg2.connect(
        host='127.0.0.1',
        port=54322,
        database='postgres',
        user='postgres',
        password='postgres'
    )


def generate_content_hash(content: str) -> str:
    """Generate SHA-256 hash for content deduplication."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def classify_asset(asset_id: str) -> Tuple[str, str]:
    """
    Classify asset by type and domain.
    Returns (node_type, domain).

    NOTE: node_type must be one of: ASSET, REGIME, MACRO, FUTURE (enum constraint)
    Domain is stored in metadata for finer classification.
    """
    asset_upper = asset_id.upper()

    # Crypto assets
    if any(crypto in asset_upper for crypto in ['BTC', 'ETH', 'SOL', 'ADA', 'DOGE', 'XRP', 'DOT', 'AVAX', 'MATIC']):
        return 'ASSET', 'CRYPTO'

    # Forex pairs
    if '=' in asset_id:
        return 'ASSET', 'FOREX'

    # Indices
    if asset_id.startswith('^'):
        return 'ASSET', 'INDEX'

    # Regional equities
    if '.DE' in asset_id or '.PA' in asset_id:
        return 'ASSET', 'EUROPE'
    if '.OL' in asset_id:
        return 'ASSET', 'NORDIC'
    if '.L' in asset_id:
        return 'ASSET', 'UK'

    # Default: US Equity
    return 'ASSET', 'US_EQUITY'


def sync_graph_nodes(conn, lookback_hours: int = 24) -> Dict[str, int]:
    """
    Sync fhq_graph.nodes from sovereign_regime_state_v4.
    Only considers assets with recent regime data.

    Returns stats dict.
    """
    cursor = conn.cursor()
    stats = {'new': 0, 'updated': 0, 'deactivated': 0, 'evidence_created': 0}

    # Get distinct assets with recent regime data
    cursor.execute("""
        SELECT DISTINCT asset_id,
               MAX(created_at) as last_regime_update,
               MAX(sovereign_regime) as latest_regime
        FROM fhq_perception.sovereign_regime_state_v4
        WHERE created_at > NOW() - INTERVAL '%s hours'
        GROUP BY asset_id
    """, [lookback_hours])

    active_assets = cursor.fetchall()
    active_asset_ids = set()

    for asset_id, last_update, regime in active_assets:
        active_asset_ids.add(asset_id)
        node_type, domain = classify_asset(asset_id)

        # Generate node_id from asset_id
        node_id = f"ASSET_{asset_id.replace('-', '_').replace('.', '_').replace('=', '_')}"

        # Check if node exists
        cursor.execute("""
            SELECT node_id, status, updated_at FROM fhq_graph.nodes
            WHERE node_id = %s
        """, [node_id])

        existing = cursor.fetchone()

        if existing:
            # Update existing node
            old_status = existing[1]
            if old_status != 'ACTIVE':
                cursor.execute("""
                    UPDATE fhq_graph.nodes
                    SET status = 'ACTIVE', updated_at = NOW()
                    WHERE node_id = %s
                """, [node_id])
                stats['updated'] += 1
        else:
            # Create new node
            label = f"{asset_id} Price & Volatility"
            description = f"Tracked asset {asset_id}. Type: {node_type}. Domain: {domain}. Latest regime: {regime}."
            metadata = json.dumps({
                'asset_id': asset_id,
                'node_type': node_type,
                'domain': domain,
                'auto_created': True,
                'created_by': 'fhq_graph_live_sync'
            })

            cursor.execute("""
                INSERT INTO fhq_graph.nodes
                (node_id, node_type, label, description, metadata, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, 'ACTIVE', NOW(), NOW())
            """, [node_id, node_type, label, description, metadata])
            stats['new'] += 1

            # Create evidence node for the new graph node
            evidence_id = str(uuid.uuid4())
            evidence_content = f"ASSET DEFINITION: {label} ({node_id}). Type: {node_type}. Domain: {domain}. Description: {description}."
            content_hash = generate_content_hash(evidence_content)

            # Check for duplicate evidence
            cursor.execute("""
                SELECT 1 FROM fhq_canonical.evidence_nodes WHERE content_hash = %s
            """, [content_hash])

            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO fhq_canonical.evidence_nodes (
                        evidence_id, content, content_type, source_type,
                        domain, entity_type, entity_id, source_reference,
                        data_timestamp, confidence_score, content_hash, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, [
                    evidence_id,
                    evidence_content,
                    'FACT',
                    'DATABASE',
                    domain,
                    'ASSET',
                    f'ASSET_{node_id}',
                    f'fhq_graph.nodes:{node_id}',
                    datetime.now(timezone.utc),
                    1.0,  # Definitional facts are 100% confident
                    content_hash,
                    datetime.now(timezone.utc)
                ])
                stats['evidence_created'] += 1

    # Deactivate ASSET nodes that haven't had regime updates
    # Only deactivate auto-created nodes (metadata contains 'auto_created')
    cursor.execute("""
        UPDATE fhq_graph.nodes
        SET status = 'INACTIVE', updated_at = NOW()
        WHERE node_type = 'ASSET'
          AND status = 'ACTIVE'
          AND metadata::text LIKE '%%auto_created%%'
          AND node_id NOT IN (
              SELECT 'ASSET_' || REPLACE(REPLACE(REPLACE(asset_id, '-', '_'), '.', '_'), '=', '_')
              FROM fhq_perception.sovereign_regime_state_v4
              WHERE created_at > NOW() - INTERVAL '%s hours'
          )
    """, [lookback_hours * 2])  # Use 2x lookback for deactivation

    stats['deactivated'] = cursor.rowcount

    conn.commit()
    cursor.close()

    return stats


def get_sync_status(conn) -> Dict[str, Any]:
    """Get current sync status of fhq_graph.nodes."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) as total_nodes,
            COUNT(*) FILTER (WHERE status = 'ACTIVE') as active_nodes,
            COUNT(*) FILTER (WHERE status = 'INACTIVE') as inactive_nodes,
            COUNT(*) FILTER (WHERE status = 'RESERVED') as reserved_nodes,
            COUNT(*) FILTER (WHERE node_type = 'ASSET') as asset_nodes,
            COUNT(*) FILTER (WHERE node_type = 'REGIME') as regime_nodes,
            COUNT(*) FILTER (WHERE node_type = 'MACRO') as macro_nodes,
            MAX(updated_at) as last_update
        FROM fhq_graph.nodes
    """)

    row = cursor.fetchone()
    cursor.close()

    return {
        'total_nodes': row[0],
        'active_nodes': row[1],
        'inactive_nodes': row[2],
        'reserved_nodes': row[3],
        'asset_nodes': row[4],
        'regime_nodes': row[5],
        'macro_nodes': row[6],
        'last_update': row[7].isoformat() if row[7] else None
    }


def run_sync():
    """Main sync function."""
    print("=" * 70)
    print("FHQ GRAPH LIVE SYNC")
    print("CEO-DIR-2026-COGNITIVE-ENGINES-001")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    conn = get_db_connection()

    # Get initial status
    print("\n[1/3] Current graph status:")
    initial = get_sync_status(conn)
    for k, v in initial.items():
        print(f"      {k}: {v}")

    # Run sync
    print("\n[2/3] Syncing from sovereign_regime_state_v4...")
    stats = sync_graph_nodes(conn, lookback_hours=48)
    print(f"      New nodes created: {stats['new']}")
    print(f"      Nodes reactivated: {stats['updated']}")
    print(f"      Nodes deactivated: {stats['deactivated']}")
    print(f"      Evidence nodes created: {stats['evidence_created']}")

    # Get final status
    print("\n[3/3] Final graph status:")
    final = get_sync_status(conn)
    for k, v in final.items():
        print(f"      {k}: {v}")

    conn.close()

    # Store evidence
    evidence = {
        'operation': 'FHQ_GRAPH_LIVE_SYNC',
        'directive': 'CEO-DIR-2026-COGNITIVE-ENGINES-001',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'initial_status': initial,
        'sync_stats': stats,
        'final_status': final,
        'corporate_standard': 'LIVE_UPDATE_V1'
    }

    evidence_path = f'evidence/GRAPH_LIVE_SYNC_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.json'
    with open(evidence_path, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)
    print(f"\nEvidence stored: {evidence_path}")

    print("\n" + "=" * 70)
    print("SYNC COMPLETE")
    print("=" * 70)

    return evidence


if __name__ == '__main__':
    run_sync()
