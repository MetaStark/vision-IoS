"""
Live Data Evidence Seeder
CEO-DIR-2026-COGNITIVE-ENGINES-001

Seeds evidence_nodes from LIVE production data:
1. Regime states (sovereign_regime_state_v4) → FACT nodes
2. Price data (fhq_market.prices) → METRIC nodes
3. Regime transitions → OBSERVATION nodes
4. Asset definitions (fhq_graph.nodes) → FACT nodes

NO TEST DATA - 100% production records converted to evidence format.
Each node is traceable back to source via source_reference field.

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

def seed_regime_facts(conn, limit: int = 150) -> int:
    """
    Seed FACT nodes from sovereign_regime_state_v4.
    Uses latest regime state per asset from last 24 hours.
    """
    cursor = conn.cursor()

    # Get latest regime per asset from last 24h
    cursor.execute("""
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

    rows = cursor.fetchall()
    nodes_created = 0

    for row in rows:
        asset_id, sovereign, technical, probs, crio_driver, created_at = row

        # Parse probabilities
        if isinstance(probs, str):
            probs = json.loads(probs)

        # Format probability distribution
        prob_str = ", ".join([f"{k}: {v*100:.1f}%" for k, v in sorted(probs.items(), key=lambda x: -x[1])])

        # Determine domain from asset_id
        if 'BTC' in asset_id or 'ETH' in asset_id or 'SOL' in asset_id:
            domain = 'CRYPTO'
        elif '=' in asset_id:  # Forex pairs like USDTRY=X
            domain = 'FOREX'
        elif asset_id.startswith('^'):  # Indices
            domain = 'INDEX'
        else:
            domain = 'EQUITY'

        # Build content
        content = (
            f"{asset_id} sovereign regime is {sovereign} (technical: {technical}). "
            f"State probability distribution: {prob_str}. "
            f"Dominant driver: {crio_driver if crio_driver else 'UNSPECIFIED'}. "
            f"Assessed {created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}."
        )

        content_hash = generate_content_hash(content)
        evidence_id = str(uuid.uuid4())

        # Check for duplicate
        cursor.execute("""
            SELECT 1 FROM fhq_canonical.evidence_nodes
            WHERE content_hash = %s
        """, [content_hash])

        if cursor.fetchone():
            continue  # Skip duplicate

        # Insert evidence node
        cursor.execute("""
            INSERT INTO fhq_canonical.evidence_nodes (
                evidence_id, content, content_type, source_type,
                domain, entity_type, entity_id, source_reference,
                data_timestamp, confidence_score, content_hash, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [
            evidence_id,
            content,
            'FACT',
            'DATABASE',
            domain,
            'REGIME',
            f'REGIME_{asset_id}',
            f'fhq_perception.sovereign_regime_state_v4:{asset_id}:{created_at.isoformat()}',
            created_at,
            0.95,  # High confidence for direct DB extraction
            content_hash,
            datetime.now(timezone.utc)
        ])

        nodes_created += 1

    conn.commit()
    cursor.close()
    return nodes_created


def seed_price_metrics(conn, limit: int = 200) -> int:
    """
    Seed METRIC nodes from fhq_market.prices.
    Uses latest price per asset_id from last 7 days.
    """
    cursor = conn.cursor()

    # Get latest price per asset_id from last 7 days
    cursor.execute("""
        WITH latest_per_asset AS (
            SELECT DISTINCT ON (asset_id)
                asset_id, open, high, low, close, volume, timestamp
            FROM fhq_market.prices
            WHERE timestamp > NOW() - INTERVAL '7 days'
              AND close IS NOT NULL
              AND volume IS NOT NULL
            ORDER BY asset_id, timestamp DESC
        )
        SELECT * FROM latest_per_asset
        ORDER BY volume DESC NULLS LAST
        LIMIT %s
    """, [limit])

    rows = cursor.fetchall()
    nodes_created = 0

    for row in rows:
        asset_id, open_p, high, low, close, volume, timestamp = row
        symbol = asset_id  # Use asset_id as symbol

        # Determine domain
        if 'BTC' in symbol or 'ETH' in symbol or 'SOL' in symbol or 'DOGE' in symbol:
            domain = 'CRYPTO'
        elif '=' in symbol:
            domain = 'FOREX'
        elif symbol.startswith('^'):
            domain = 'INDEX'
        else:
            domain = 'EQUITY'

        # Format volume
        if volume and volume > 1e9:
            vol_str = f"${volume/1e9:.2f}B"
        elif volume and volume > 1e6:
            vol_str = f"${volume/1e6:.2f}M"
        else:
            vol_str = f"${volume:,.0f}" if volume else "N/A"

        # Build content
        content = (
            f"{symbol} closed at ${close:,.2f} on {timestamp.strftime('%Y-%m-%d')}. "
            f"Daily range: ${low:,.2f} - ${high:,.2f}. "
            f"Trading volume: {vol_str}."
        )

        content_hash = generate_content_hash(content)
        evidence_id = str(uuid.uuid4())

        # Check for duplicate
        cursor.execute("""
            SELECT 1 FROM fhq_canonical.evidence_nodes
            WHERE content_hash = %s
        """, [content_hash])

        if cursor.fetchone():
            continue

        cursor.execute("""
            INSERT INTO fhq_canonical.evidence_nodes (
                evidence_id, content, content_type, source_type,
                domain, entity_type, entity_id, source_reference,
                data_timestamp, confidence_score, content_hash, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [
            evidence_id,
            content,
            'METRIC',
            'DATABASE',
            domain,
            'PRICE',
            f'PRICE_{symbol}',
            f'fhq_market.prices:{symbol}:{timestamp.isoformat()}',
            timestamp,
            0.99,  # Very high confidence for market data
            content_hash,
            datetime.now(timezone.utc)
        ])

        nodes_created += 1

    conn.commit()
    cursor.close()
    return nodes_created


def seed_regime_transitions(conn, limit: int = 100) -> int:
    """
    Seed OBSERVATION nodes for regime state changes.
    Identifies transitions where sovereign_regime changed.
    """
    cursor = conn.cursor()

    # Find regime transitions in last 7 days
    cursor.execute("""
        WITH regime_changes AS (
            SELECT
                asset_id,
                sovereign_regime as current_regime,
                LAG(sovereign_regime) OVER (PARTITION BY asset_id ORDER BY created_at) as prev_regime,
                created_at,
                state_probabilities
            FROM fhq_perception.sovereign_regime_state_v4
            WHERE created_at > NOW() - INTERVAL '7 days'
        )
        SELECT asset_id, prev_regime, current_regime, created_at, state_probabilities
        FROM regime_changes
        WHERE prev_regime IS NOT NULL
          AND prev_regime != current_regime
        ORDER BY created_at DESC
        LIMIT %s
    """, [limit])

    rows = cursor.fetchall()
    nodes_created = 0

    for row in rows:
        asset_id, prev_regime, current_regime, created_at, probs = row

        if isinstance(probs, str):
            probs = json.loads(probs)

        # Get current regime probability
        current_prob = probs.get(current_regime, 0) * 100

        # Determine domain
        if 'BTC' in asset_id or 'ETH' in asset_id or 'SOL' in asset_id:
            domain = 'CRYPTO'
        elif '=' in asset_id:
            domain = 'FOREX'
        else:
            domain = 'EQUITY'

        content = (
            f"REGIME TRANSITION: {asset_id} shifted from {prev_regime} to {current_regime} "
            f"on {created_at.strftime('%Y-%m-%d %H:%M UTC')}. "
            f"New regime confidence: {current_prob:.1f}%."
        )

        content_hash = generate_content_hash(content)
        evidence_id = str(uuid.uuid4())

        cursor.execute("""
            SELECT 1 FROM fhq_canonical.evidence_nodes
            WHERE content_hash = %s
        """, [content_hash])

        if cursor.fetchone():
            continue

        cursor.execute("""
            INSERT INTO fhq_canonical.evidence_nodes (
                evidence_id, content, content_type, source_type,
                domain, entity_type, entity_id, source_reference,
                data_timestamp, confidence_score, content_hash, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [
            evidence_id,
            content,
            'OBSERVATION',
            'DATABASE',
            domain,
            'REGIME_TRANSITION',
            f'TRANSITION_{asset_id}_{created_at.strftime("%Y%m%d%H%M")}',
            f'fhq_perception.sovereign_regime_state_v4:transition:{asset_id}:{created_at.isoformat()}',
            created_at,
            0.90,
            content_hash,
            datetime.now(timezone.utc)
        ])

        nodes_created += 1

    conn.commit()
    cursor.close()
    return nodes_created


def seed_asset_definitions(conn) -> int:
    """
    Seed FACT nodes from fhq_graph.nodes (asset definitions).
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT node_id, node_type, label, description, metadata, created_at
        FROM fhq_graph.nodes
        WHERE status = 'active' OR status IS NULL
    """)

    rows = cursor.fetchall()
    nodes_created = 0

    for row in rows:
        node_id, node_type, label, description, metadata, created_at = row

        if isinstance(metadata, str):
            properties = json.loads(metadata) if metadata else {}
        else:
            properties = metadata if metadata else {}

        # Determine domain
        if node_type in ['CRYPTO_ASSET', 'CRYPTOCURRENCY']:
            domain = 'CRYPTO'
        elif node_type in ['FOREX_PAIR', 'CURRENCY']:
            domain = 'FOREX'
        elif node_type in ['INDEX', 'MARKET_INDEX']:
            domain = 'INDEX'
        elif node_type in ['MACRO_INDICATOR', 'ECONOMIC']:
            domain = 'MACRO'
        else:
            domain = 'FINANCE'

        # Build content from description and metadata
        desc_str = description if description else "No description available"
        props_str = ", ".join([f"{k}: {v}" for k, v in properties.items()]) if properties else ""

        content = (
            f"ASSET DEFINITION: {label} ({node_id}). "
            f"Type: {node_type}. "
            f"Description: {desc_str}."
            + (f" Metadata: {props_str}." if props_str else "")
        )

        content_hash = generate_content_hash(content)
        evidence_id = str(uuid.uuid4())

        cursor.execute("""
            SELECT 1 FROM fhq_canonical.evidence_nodes
            WHERE content_hash = %s
        """, [content_hash])

        if cursor.fetchone():
            continue

        cursor.execute("""
            INSERT INTO fhq_canonical.evidence_nodes (
                evidence_id, content, content_type, source_type,
                domain, entity_type, entity_id, source_reference,
                data_timestamp, confidence_score, content_hash, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [
            evidence_id,
            content,
            'FACT',
            'DATABASE',
            domain,
            'ASSET',
            f'ASSET_{node_id}',
            f'fhq_graph.nodes:{node_id}',
            created_at,
            1.0,  # Definitional facts are 100% confident
            content_hash,
            datetime.now(timezone.utc)
        ])

        nodes_created += 1

    conn.commit()
    cursor.close()
    return nodes_created


def run_seeding():
    """Main seeding function."""
    print("=" * 70)
    print("LIVE DATA EVIDENCE SEEDER")
    print("CEO-DIR-2026-COGNITIVE-ENGINES-001")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    conn = get_db_connection()

    # Get initial count
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM fhq_canonical.evidence_nodes")
    initial_count = cursor.fetchone()[0]
    cursor.close()
    print(f"\nInitial evidence nodes: {initial_count}")

    # Seed from each source
    print("\n[1/4] Seeding regime state FACTs...")
    regime_count = seed_regime_facts(conn, limit=150)
    print(f"      Created: {regime_count} nodes")

    print("\n[2/4] Seeding price METRICs...")
    price_count = seed_price_metrics(conn, limit=200)
    print(f"      Created: {price_count} nodes")

    print("\n[3/4] Seeding regime transition OBSERVATIONs...")
    transition_count = seed_regime_transitions(conn, limit=100)
    print(f"      Created: {transition_count} nodes")

    print("\n[4/4] Seeding asset definition FACTs...")
    asset_count = seed_asset_definitions(conn)
    print(f"      Created: {asset_count} nodes")

    # Get final count
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM fhq_canonical.evidence_nodes")
    final_count = cursor.fetchone()[0]

    # Get freshness stats
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as last_hour,
            MAX(data_timestamp) as latest_data,
            MIN(data_timestamp) as oldest_data
        FROM fhq_canonical.evidence_nodes
    """)
    stats = cursor.fetchone()
    cursor.close()

    total_created = regime_count + price_count + transition_count + asset_count

    print("\n" + "=" * 70)
    print("SEEDING COMPLETE")
    print("=" * 70)
    print(f"Initial count:  {initial_count}")
    print(f"Final count:    {final_count}")
    print(f"Nodes created:  {total_created}")
    print(f"  - Regime FACTs:      {regime_count}")
    print(f"  - Price METRICs:     {price_count}")
    print(f"  - Transitions:       {transition_count}")
    print(f"  - Asset definitions: {asset_count}")
    print(f"\nFreshness:")
    print(f"  - Created in last hour: {stats[1]}")
    print(f"  - Latest data_timestamp: {stats[2]}")
    print(f"  - Oldest data_timestamp: {stats[3]}")

    conn.close()

    # Store evidence
    evidence = {
        'operation': 'LIVE_DATA_EVIDENCE_SEEDING',
        'directive': 'CEO-DIR-2026-COGNITIVE-ENGINES-001',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'initial_count': initial_count,
        'final_count': final_count,
        'nodes_created': {
            'regime_facts': regime_count,
            'price_metrics': price_count,
            'transitions': transition_count,
            'asset_definitions': asset_count,
            'total': total_created
        },
        'sources': [
            'fhq_perception.sovereign_regime_state_v4',
            'fhq_market.prices',
            'fhq_graph.nodes'
        ],
        'data_type': 'LIVE_PRODUCTION_DATA',
        'test_data_used': False
    }

    evidence_path = f'evidence/LIVE_DATA_SEEDING_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.json'
    with open(evidence_path, 'w') as f:
        json.dump(evidence, f, indent=2)
    print(f"\nEvidence stored: {evidence_path}")

    return evidence


if __name__ == '__main__':
    run_seeding()
