"""
Evidence Node to Qdrant Sync
CEO-DIR-2026-COGNITIVE-ENGINES-001
CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001 (court-proof eligibility gate)

Syncs evidence nodes from Postgres to Qdrant with embeddings.
- Generates embeddings via OpenAI text-embedding-3-small
- Upserts to Qdrant evidence_nodes collection
- Updates qdrant_point_id in Postgres for traceability

COURT-PROOF ELIGIBILITY GATE (CEO Directive):
Evidence nodes eligible for Qdrant sync MUST pass court-proof validation:
- court_proof_verified = TRUE
- source_preference <= EVIDENCE_PREFERENCE_THRESHOLD OR trusted = TRUE
- quarantined = FALSE

This keeps the cognitive organism clean while preserving full audit trail.
Evidence can exist in Postgres for audit purposes but be EXCLUDED from
retrieval in production modes.

Author: STIG (CTO)
Date: 2026-01-04
"""

import os
import sys
import uuid
import json
import time
import psycopg2
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Load environment
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'), override=True)

# Import embedding generator
sys.path.insert(0, os.path.dirname(__file__))
from embedding_generator import EmbeddingGenerator, EmbeddingError

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct, VectorParams, Distance
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    print("[ERROR] qdrant-client not installed. Run: pip install qdrant-client")


# CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001: Court-proof eligibility threshold
# source_preference values: 0=constitutional, 1=CEO, 10=automated, 999=untrusted
# Default threshold: 100 (allows constitutional, CEO, and automated sources)
EVIDENCE_PREFERENCE_THRESHOLD = 100


def is_eligible_for_retrieval(evidence_node: Dict) -> bool:
    """
    Court-proof eligibility gate: determines if evidence can be used in production retrieval.

    Evidence may exist in Postgres for audit purposes but be EXCLUDED from
    cognitive operations if it doesn't meet eligibility requirements.

    CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001 Section 8.1.1

    Args:
        evidence_node: Dict with evidence node fields

    Returns:
        True if evidence is eligible for Qdrant sync and retrieval
    """
    # Must have court-proof validation
    if not evidence_node.get('court_proof_verified'):
        return False

    # Must have trusted source or low source_preference
    source_pref = evidence_node.get('source_preference', 999)
    is_trusted = evidence_node.get('trusted', False)

    if source_pref > EVIDENCE_PREFERENCE_THRESHOLD and not is_trusted:
        return False

    # Must not be flagged as quarantined
    if evidence_node.get('quarantined', False):
        return False

    return True


def get_db_connection():
    return psycopg2.connect(
        host='127.0.0.1',
        port=54322,
        database='postgres',
        user='postgres',
        password='postgres'
    )


def get_unsynced_evidence(conn, batch_size: int = 50, enforce_eligibility: bool = True) -> List[Dict]:
    """
    Get evidence nodes that don't have qdrant_point_id and pass eligibility gate.

    CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001: Only eligible evidence is synced.
    Eligibility requirements:
    - court_proof_verified = TRUE
    - source_preference <= EVIDENCE_PREFERENCE_THRESHOLD OR trusted = TRUE
    - quarantined = FALSE

    Args:
        conn: Database connection
        batch_size: Maximum number of evidence nodes to return
        enforce_eligibility: If True, apply court-proof eligibility gate

    Returns:
        List of eligible evidence node dicts
    """
    cursor = conn.cursor()

    if enforce_eligibility:
        # Court-proof eligibility gate enforced at SQL level
        cursor.execute("""
            SELECT
                evidence_id::text, content, content_type, source_type,
                domain, entity_type, entity_id, source_reference,
                data_timestamp, confidence_score,
                court_proof_verified, source_preference, trusted, quarantined
            FROM fhq_canonical.evidence_nodes
            WHERE qdrant_point_id IS NULL
              AND court_proof_verified = TRUE
              AND quarantined = FALSE
              AND (source_preference <= %s OR trusted = TRUE)
            ORDER BY created_at DESC
            LIMIT %s
        """, [EVIDENCE_PREFERENCE_THRESHOLD, batch_size])

        columns = ['evidence_id', 'content', 'content_type', 'source_type',
                   'domain', 'entity_type', 'entity_id', 'source_reference',
                   'data_timestamp', 'confidence_score',
                   'court_proof_verified', 'source_preference', 'trusted', 'quarantined']
    else:
        # Legacy mode - no eligibility gate (for backward compatibility)
        cursor.execute("""
            SELECT
                evidence_id::text, content, content_type, source_type,
                domain, entity_type, entity_id, source_reference,
                data_timestamp, confidence_score
            FROM fhq_canonical.evidence_nodes
            WHERE qdrant_point_id IS NULL
            ORDER BY created_at DESC
            LIMIT %s
        """, [batch_size])

        columns = ['evidence_id', 'content', 'content_type', 'source_type',
                   'domain', 'entity_type', 'entity_id', 'source_reference',
                   'data_timestamp', 'confidence_score']

    rows = cursor.fetchall()
    cursor.close()

    return [dict(zip(columns, row)) for row in rows]


def update_qdrant_point_id(conn, evidence_id: str, qdrant_point_id: str, collection: str):
    """Update the qdrant_point_id in Postgres."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE fhq_canonical.evidence_nodes
        SET qdrant_point_id = %s,
            qdrant_collection = %s,
            embedding_model = 'text-embedding-3-small',
            updated_at = NOW()
        WHERE evidence_id = %s
    """, [qdrant_point_id, collection, evidence_id])
    conn.commit()
    cursor.close()


def ensure_collection_exists(qdrant: QdrantClient, collection_name: str, dimension: int = 1536):
    """Ensure the Qdrant collection exists with correct config."""
    collections = qdrant.get_collections().collections
    exists = any(c.name == collection_name for c in collections)

    if not exists:
        print(f"[INFO] Creating collection {collection_name}...")
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=dimension, distance=Distance.COSINE)
        )
    return True


def sync_batch(
    conn,
    qdrant: QdrantClient,
    embedder: EmbeddingGenerator,
    evidence_batch: List[Dict],
    collection: str = "evidence_nodes"
) -> Dict[str, int]:
    """Sync a batch of evidence nodes to Qdrant."""
    stats = {'success': 0, 'failed': 0, 'skipped': 0}

    # Generate embeddings for all content in batch
    contents = [e['content'] for e in evidence_batch]

    try:
        embeddings = embedder.generate(contents)
    except EmbeddingError as e:
        print(f"[ERROR] Embedding generation failed: {e}")
        stats['failed'] = len(evidence_batch)
        return stats

    # Prepare Qdrant points
    points = []
    point_mapping = []  # Track evidence_id -> qdrant_point_id

    for evidence, embedding in zip(evidence_batch, embeddings):
        qdrant_point_id = str(uuid.uuid4())

        payload = {
            'evidence_id': evidence['evidence_id'],
            'content': evidence['content'][:1000],  # Truncate for payload
            'content_type': evidence['content_type'],
            'source_type': evidence['source_type'],
            'domain': evidence['domain'],
            'entity_type': evidence['entity_type'],
            'entity_id': evidence['entity_id'],
            'confidence_score': float(evidence['confidence_score']) if evidence['confidence_score'] else 1.0,
            'synced_at': datetime.now(timezone.utc).isoformat()
        }

        point = PointStruct(
            id=qdrant_point_id,
            vector=embedding,
            payload=payload
        )
        points.append(point)
        point_mapping.append((evidence['evidence_id'], qdrant_point_id))

    # Upsert to Qdrant
    try:
        qdrant.upsert(collection_name=collection, points=points)

        # Update Postgres with qdrant_point_ids
        for evidence_id, qdrant_point_id in point_mapping:
            update_qdrant_point_id(conn, evidence_id, qdrant_point_id, collection)
            stats['success'] += 1

    except Exception as e:
        print(f"[ERROR] Qdrant upsert failed: {e}")
        stats['failed'] = len(points)

    return stats


def run_sync(batch_size: int = 50, max_batches: int = 100):
    """Main sync function."""
    print("=" * 70)
    print("EVIDENCE NODE TO QDRANT SYNC")
    print("CEO-DIR-2026-COGNITIVE-ENGINES-001")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    if not QDRANT_AVAILABLE:
        print("[ERROR] Qdrant client not available")
        return

    # Initialize connections
    conn = get_db_connection()
    qdrant = QdrantClient(host="localhost", port=6333)

    # Check API key
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key or api_key == 'placeholder':
        print("[ERROR] Valid OPENAI_API_KEY not found")
        return

    embedder = EmbeddingGenerator(api_key=api_key)

    # Get initial count with eligibility breakdown
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            COUNT(*) FILTER (WHERE qdrant_point_id IS NULL) as needs_sync,
            COUNT(*) FILTER (WHERE qdrant_point_id IS NOT NULL) as already_synced,
            COUNT(*) FILTER (WHERE qdrant_point_id IS NULL
                AND court_proof_verified = TRUE
                AND quarantined = FALSE
                AND (source_preference <= %s OR trusted = TRUE)) as eligible_for_sync,
            COUNT(*) FILTER (WHERE quarantined = TRUE) as quarantined_count,
            COUNT(*) FILTER (WHERE court_proof_verified = FALSE) as unverified_count
        FROM fhq_canonical.evidence_nodes
    """, [EVIDENCE_PREFERENCE_THRESHOLD])
    initial = cursor.fetchone()
    cursor.close()

    print(f"\n[INFO] Initial state:")
    print(f"       Total needs sync:     {initial[0]}")
    print(f"       Already synced:       {initial[1]}")
    print(f"       Eligible for sync:    {initial[2]} (court-proof gate)")
    print(f"       Quarantined:          {initial[3]}")
    print(f"       Unverified:           {initial[4]}")

    if initial[2] == 0:
        if initial[0] == 0:
            print("\n[INFO] All evidence nodes already synced!")
        else:
            print(f"\n[INFO] No ELIGIBLE evidence nodes to sync ({initial[0]} unsynced but ineligible)")
        return

    # Ensure collection exists
    ensure_collection_exists(qdrant, "evidence_nodes", dimension=1536)

    # Process in batches
    total_stats = {'success': 0, 'failed': 0, 'skipped': 0}
    batch_num = 0

    print(f"\n[INFO] Starting sync (batch_size={batch_size}, max_batches={max_batches})...")

    while batch_num < max_batches:
        # Get next batch
        batch = get_unsynced_evidence(conn, batch_size)

        if not batch:
            print("\n[INFO] No more evidence nodes to sync")
            break

        batch_num += 1
        print(f"\n[Batch {batch_num}] Processing {len(batch)} evidence nodes...")

        # Sync batch
        start_time = time.time()
        stats = sync_batch(conn, qdrant, embedder, batch)
        elapsed = time.time() - start_time

        # Accumulate stats
        for k, v in stats.items():
            total_stats[k] += v

        print(f"           Success: {stats['success']}, Failed: {stats['failed']} ({elapsed:.1f}s)")

        # Rate limit (OpenAI has rate limits)
        if batch_num < max_batches and len(batch) == batch_size:
            time.sleep(1)  # Brief pause between batches

    # Final report
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            COUNT(*) FILTER (WHERE qdrant_point_id IS NULL) as needs_sync,
            COUNT(*) FILTER (WHERE qdrant_point_id IS NOT NULL) as synced
        FROM fhq_canonical.evidence_nodes
    """)
    final = cursor.fetchone()
    cursor.close()

    # Get Qdrant collection stats
    collection_info = qdrant.get_collection("evidence_nodes")

    print("\n" + "=" * 70)
    print("SYNC COMPLETE")
    print("=" * 70)
    print(f"Total success: {total_stats['success']}")
    print(f"Total failed:  {total_stats['failed']}")
    print(f"Batches processed: {batch_num}")
    print(f"\nPostgres state:")
    print(f"  Still needs sync: {final[0]}")
    print(f"  Synced to Qdrant: {final[1]}")
    print(f"\nQdrant collection:")
    print(f"  Vectors: {collection_info.vectors_count}")
    print(f"  Points:  {collection_info.points_count}")

    # Store evidence
    evidence = {
        'operation': 'QDRANT_EVIDENCE_SYNC',
        'directive': 'CEO-DIR-2026-COGNITIVE-ENGINES-001',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'initial_needs_sync': initial[0],
        'initial_synced': initial[1],
        'final_needs_sync': final[0],
        'final_synced': final[1],
        'total_success': total_stats['success'],
        'total_failed': total_stats['failed'],
        'batches_processed': batch_num,
        'qdrant_vectors': collection_info.vectors_count
    }

    evidence_path = f'evidence/QDRANT_SYNC_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.json'
    with open(evidence_path, 'w') as f:
        json.dump(evidence, f, indent=2)
    print(f"\nEvidence stored: {evidence_path}")

    conn.close()
    return evidence


if __name__ == '__main__':
    run_sync(batch_size=50, max_batches=30)  # Process up to 1500 nodes
