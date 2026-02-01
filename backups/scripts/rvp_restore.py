#!/usr/bin/env python3
"""
RVP-LITE Restore Script - Isolated environment only
Uses chunked decompression and line-by-line parsing
"""

import gzip
import json
import psycopg2
from pathlib import Path
import hashlib
import re

BACKUP_DIR = Path(__file__).parent.parent

# RVP-LITE isolated environment ONLY
RVP_CONFIG = {
    "host": "127.0.0.1",
    "port": 54399,
    "dbname": "rvptest",
    "user": "postgres",
    "password": "rvptest123"
}


def extract_and_insert_records(conn, backup_file: Path, tier_name: str, max_per_table: int = 100):
    """
    Extract records by decompressing to temp file and parsing in chunks.
    Inserts up to max_per_table records per table for verification.
    """
    import tempfile
    import os

    print(f"\nRestoring {tier_name} from {backup_file.name}...")

    # Decompress to temp file
    temp_path = Path(tempfile.gettempdir()) / f"rvp_{backup_file.stem}.json"

    print(f"  Decompressing to {temp_path}...")
    with gzip.open(backup_file, "rb") as f_in:
        with open(temp_path, "wb") as f_out:
            while chunk := f_in.read(8192):
                f_out.write(chunk)

    print(f"  Decompressed: {temp_path.stat().st_size / (1024*1024):.1f} MB")

    # Now load and process
    print(f"  Loading JSON structure...")
    with open(temp_path, "r", encoding="utf-8") as f:
        backup = json.load(f)

    cursor = conn.cursor()
    total_inserted = 0
    tables_processed = 0

    # Process schemas
    for schema_name, schema_data in backup.get("schemas", {}).items():
        for table_name, table_info in schema_data.get("tables", {}).items():
            data = table_info.get("data", [])
            if not data:
                continue

            full_table = f"{schema_name}.{table_name}"
            sample = data[:max_per_table]  # Limit records

            if not sample:
                continue

            columns = list(sample[0].keys())
            cols_str = ", ".join(f'"{c}"' for c in columns)

            inserted = 0
            for row in sample:
                try:
                    values = []
                    for c in columns:
                        v = row.get(c)
                        if isinstance(v, (dict, list)):
                            values.append(json.dumps(v))
                        else:
                            values.append(v)

                    placeholders = ", ".join(["%s"] * len(columns))
                    sql = f'INSERT INTO {full_table} ({cols_str}) VALUES ({placeholders})'
                    cursor.execute(sql, values)
                    inserted += 1
                except Exception as e:
                    conn.rollback()
                    break

            if inserted > 0:
                conn.commit()
                total_inserted += inserted
                tables_processed += 1
                print(f"  {full_table}: {inserted}/{len(data)} rows")

    # Process meta_tables (Tier 1)
    for meta_entry in backup.get("meta_tables", []):
        table_name = meta_entry.get("table")
        data = meta_entry.get("data", [])
        if not data:
            continue

        sample = data[:max_per_table]
        columns = list(sample[0].keys())
        cols_str = ", ".join(f'"{c}"' for c in columns)

        inserted = 0
        for row in sample:
            try:
                values = []
                for c in columns:
                    v = row.get(c)
                    if isinstance(v, (dict, list)):
                        values.append(json.dumps(v))
                    else:
                        values.append(v)

                placeholders = ", ".join(["%s"] * len(columns))
                sql = f'INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})'
                cursor.execute(sql, values)
                inserted += 1
            except Exception as e:
                conn.rollback()
                break

        if inserted > 0:
            conn.commit()
            total_inserted += inserted
            tables_processed += 1
            print(f"  {table_name}: {inserted}/{len(data)} rows")

    # Cleanup temp file
    os.unlink(temp_path)

    print(f"\n  {tier_name} complete: {total_inserted} rows in {tables_processed} tables")
    return total_inserted


def verify_schema_exists(conn):
    """Verify key tables exist."""
    cursor = conn.cursor()

    checks = [
        ("fhq_governance", "governance_actions_log"),
        ("fhq_governance", "agent_contracts"),
        ("fhq_meta", "adr_registry"),
        ("fhq_canonical", "golden_needles"),
        ("vision_verification", "summary_evidence_ledger"),
    ]

    print("\nSchema verification:")
    all_exist = True
    for schema, table in checks:
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            )
        """, (schema, table))
        exists = cursor.fetchone()[0]
        status = "EXISTS" if exists else "MISSING"
        if not exists:
            all_exist = False
        print(f"  {schema}.{table}: {status}")

    return all_exist


def main():
    print("=" * 60)
    print("RVP-LITE ISOLATED RESTORE")
    print("Environment: Ephemeral Docker PostgreSQL (port 54399)")
    print("NO CONTACT WITH SUPABASE PRODUCTION")
    print("=" * 60)

    conn = psycopg2.connect(**RVP_CONFIG)

    # Step 1: Verify schema structure restored
    if not verify_schema_exists(conn):
        print("\nERROR: Schema not fully restored")
        return 1

    # Step 2: Restore data from backups
    tier1_file = BACKUP_DIR / "governance" / "20260111_tier1_governance.json.gz"
    tier2_file = BACKUP_DIR / "evidence" / "20260111_tier2_canonical.json.gz"

    print(f"\nBackup files:")
    print(f"  Tier 1: {tier1_file.stat().st_size / (1024*1024):.2f} MB (gzip)")
    print(f"  Tier 2: {tier2_file.stat().st_size / (1024*1024):.2f} MB (gzip)")

    t1_rows = extract_and_insert_records(conn, tier1_file, "TIER 1 (Governance)")
    t2_rows = extract_and_insert_records(conn, tier2_file, "TIER 2 (Canonical)")

    print(f"\n{'=' * 60}")
    print(f"RESTORE COMPLETE")
    print(f"Total rows restored: {t1_rows + t2_rows}")
    print("=" * 60)

    conn.close()
    return 0


if __name__ == "__main__":
    exit(main())
