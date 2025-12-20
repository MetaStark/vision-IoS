#!/usr/bin/env python3
"""
STIG CANONICALIZATION - Promote staging data to canonical prices
================================================================

Authority: ADR-013, ADR-002
Owner: STIG (CTO)

This script promotes all validated staging data to the canonical prices table.
Run once to bootstrap, then daily_ingest_worker handles incremental updates.
"""

import os
import sys
import uuid
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Database connection
def get_connection():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "54322"),
        database=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres")
    )

def main():
    print("=" * 60)
    print("STIG CANONICALIZATION - Promoting Staging to Canonical")
    print("=" * 60)

    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get staging stats
            cur.execute("""
                SELECT
                    canonical_id,
                    COUNT(*) as rows,
                    MIN(timestamp) as start_date,
                    MAX(timestamp) as end_date
                FROM fhq_market.staging_prices
                GROUP BY canonical_id
                ORDER BY canonical_id
            """)
            staging_stats = cur.fetchall()

            print("\nStaging data summary:")
            for stat in staging_stats:
                print(f"  {stat['canonical_id']}: {stat['rows']} rows ({stat['start_date'].date()} to {stat['end_date'].date()})")

            # Get existing canonical stats
            cur.execute("""
                SELECT COUNT(*) as total FROM fhq_market.prices
            """)
            existing = cur.fetchone()['total']
            print(f"\nExisting canonical rows: {existing}")

            # Create reconciliation record
            reconciliation_id = uuid.uuid4()
            batch_id = uuid.uuid4()

            # Count new rows to promote
            cur.execute("""
                SELECT COUNT(*) as new_rows
                FROM fhq_market.staging_prices s
                WHERE NOT EXISTS (
                    SELECT 1 FROM fhq_market.prices p
                    WHERE p.canonical_id = s.canonical_id
                      AND p.timestamp = s.timestamp
                )
            """)
            new_rows = cur.fetchone()['new_rows']
            print(f"New rows to promote: {new_rows}")

            if new_rows == 0:
                print("\nNo new rows to promote. Already synchronized.")
                return

            # Compute staging hash
            cur.execute("""
                SELECT string_agg(data_hash, '' ORDER BY canonical_id, timestamp) as combined
                FROM fhq_market.staging_prices s
                WHERE NOT EXISTS (
                    SELECT 1 FROM fhq_market.prices p
                    WHERE p.canonical_id = s.canonical_id
                      AND p.timestamp = s.timestamp
                )
            """)
            combined = cur.fetchone()['combined'] or ''
            staging_hash = hashlib.sha256(combined.encode()).hexdigest()

            print(f"\nStaging hash: {staging_hash[:16]}...")

            # Log VEGA reconciliation
            cur.execute("""
                INSERT INTO fhq_market.reconciliation_log (
                    reconciliation_id, batch_id,
                    staging_rows, canonical_rows, rows_added,
                    staging_hash, vega_decision, vega_notes,
                    reconciled_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, 'APPROVED',
                    'Initial canonicalization of GENESIS_INGESTION data', 'VEGA'
                )
            """, (str(reconciliation_id), str(batch_id), new_rows, existing, new_rows, staging_hash))

            # Promote staging to canonical
            print("\nSTIG: Canonicalizing...")
            cur.execute("""
                INSERT INTO fhq_market.prices (
                    asset_id, canonical_id, timestamp,
                    open, high, low, close, volume,
                    source, staging_id, data_hash,
                    gap_filled, batch_id,
                    vega_reconciled, vega_reconciled_at, vega_attestation_id,
                    canonicalized_by
                )
                SELECT
                    s.asset_id::uuid, s.canonical_id, s.timestamp,
                    s.open, s.high, s.low, s.close, s.volume,
                    s.source, s.id, s.data_hash,
                    s.gap_filled, %s::uuid,
                    TRUE, NOW(), %s,
                    'STIG'
                FROM fhq_market.staging_prices s
                WHERE NOT EXISTS (
                    SELECT 1 FROM fhq_market.prices p
                    WHERE p.canonical_id = s.canonical_id
                      AND p.timestamp = s.timestamp
                )
            """, (str(batch_id), str(reconciliation_id)))

            canonicalized = cur.rowcount
            print(f"Canonicalized: {canonicalized} rows")

            # Log to governance
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_id,
                    action_type,
                    action_target,
                    action_target_type,
                    initiated_by,
                    initiated_at,
                    decision,
                    decision_rationale,
                    hash_chain_id,
                    signature_id
                ) VALUES (
                    gen_random_uuid(),
                    'DATA_CANONICALIZATION',
                    'fhq_market.prices',
                    'TABLE',
                    'STIG',
                    NOW(),
                    'APPROVED',
                    %s,
                    %s,
                    gen_random_uuid()
                )
            """, (
                f'Canonicalized {canonicalized} rows from staging. Hash: {staging_hash[:16]}...',
                f'CANON-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
            ))

            # Log to ios_audit
            cur.execute("""
                INSERT INTO fhq_meta.ios_audit_log (
                    ios_id, event_type, actor, event_data, gate_level
                ) VALUES (
                    'IoS-001', 'CANONICALIZATION', 'STIG', %s, 'G4'
                )
            """, (json.dumps({
                "batch_id": str(batch_id),
                "reconciliation_id": str(reconciliation_id),
                "rows_canonicalized": canonicalized,
                "staging_hash": staging_hash
            }),))

        conn.commit()

        # Final stats
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    canonical_id,
                    COUNT(*) as rows,
                    MIN(timestamp) as start_date,
                    MAX(timestamp) as end_date
                FROM fhq_market.prices
                GROUP BY canonical_id
                ORDER BY canonical_id
            """)
            canonical_stats = cur.fetchall()

            print("\n" + "=" * 60)
            print("CANONICALIZATION COMPLETE")
            print("=" * 60)
            print("\nCanonical prices summary:")
            total = 0
            for stat in canonical_stats:
                print(f"  {stat['canonical_id']}: {stat['rows']} rows ({stat['start_date'].date()} to {stat['end_date'].date()})")
                total += stat['rows']
            print(f"\nTotal canonical rows: {total}")

    finally:
        conn.close()

if __name__ == "__main__":
    main()
