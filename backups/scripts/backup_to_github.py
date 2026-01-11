#!/usr/bin/env python3
"""
FjordHQ Tier 1-2 Database Backup to Git
========================================
CEO Decision: 2026-01-11
Reference: STIG-VERIFY-2026-011

Backs up Tier 1 (Governance/Evidence/Audit) and Tier 2 (Canonical/Configs)
data to JSON files for Git-based backup in vision-IoS repository.

Tier 3 (Market/Research data - 9.1 GB) is excluded per CEO decision;
recovery model is re-ingestion only.
"""

import os
import json
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Configuration
BACKUP_DATE = datetime.now(timezone.utc).strftime("%Y%m%d")
BACKUP_DIR = Path(__file__).parent.parent
SCHEMA_DIR = BACKUP_DIR / "schema"
GOVERNANCE_DIR = BACKUP_DIR / "governance"
EVIDENCE_DIR = BACKUP_DIR / "evidence"

# Database connection (from environment or defaults)
DB_HOST = os.environ.get("PGHOST", "127.0.0.1")
DB_PORT = os.environ.get("PGPORT", "54322")
DB_NAME = os.environ.get("PGDATABASE", "postgres")
DB_USER = os.environ.get("PGUSER", "postgres")

# Tier 1: Governance / Evidence / Audit (IRREPLACEABLE)
TIER1_SCHEMAS = ["fhq_governance", "vision_verification", "vega"]
TIER1_META_TABLES = [
    "fhq_meta.adr_registry",
    "fhq_meta.adr_audit_log",
    "fhq_meta.adr_version_history",
    "fhq_meta.adr_drift_events",
    "fhq_meta.adr_archive",
    "fhq_meta.adr_dependencies",
    "fhq_meta.adr_supplements",
    "fhq_meta.ios_audit_log",
    "fhq_meta.dynamic_regime_weights_audit",
]

# Tier 2: Canonical / Configs / Agents (DIFFICULT TO RECREATE)
TIER2_SCHEMAS = [
    "fhq_canonical",
    "fhq_security",
    "fhq_org",
    "fhq_finn",
    "vision_core",
    "vision_autonomy",
    "vision_signals",
    "vision_cinematic",
]


def run_psql(query: str, output_format: str = "json") -> str:
    """Execute psql query and return output."""
    cmd = [
        "psql",
        "-h", DB_HOST,
        "-p", DB_PORT,
        "-U", DB_USER,
        "-d", DB_NAME,
        "-t",  # Tuples only
        "-A",  # Unaligned output
        "-c", query,
    ]

    env = os.environ.copy()
    env["PGPASSWORD"] = os.environ.get("PGPASSWORD", "postgres")

    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"psql failed: {result.stderr}")
    return result.stdout.strip()


def export_table_to_json(schema: str, table: str) -> dict:
    """Export a single table to JSON format."""
    full_name = f"{schema}.{table}"

    # Get row count
    count_query = f"SELECT COUNT(*) FROM {full_name}"
    count = int(run_psql(count_query) or "0")

    if count == 0:
        return {"table": full_name, "row_count": 0, "data": [], "hash": hashlib.sha256(b"[]").hexdigest()}

    # Export data as JSON
    json_query = f"SELECT json_agg(t) FROM {full_name} t"
    raw_json = run_psql(json_query)

    if not raw_json or raw_json == "":
        data = []
    else:
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            data = []

    # Calculate hash for verification
    data_hash = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

    return {
        "table": full_name,
        "row_count": count,
        "data": data,
        "hash": data_hash,
    }


def get_schema_tables(schema: str) -> list:
    """Get list of tables in a schema."""
    query = f"SELECT tablename FROM pg_tables WHERE schemaname = '{schema}' ORDER BY tablename"
    result = run_psql(query)
    if not result:
        return []
    return [t.strip() for t in result.split("\n") if t.strip()]


def export_schema_ddl() -> str:
    """Export schema DDL (structure only, no data)."""
    # Build list of schemas to export
    all_schemas = TIER1_SCHEMAS + TIER2_SCHEMAS + ["fhq_meta"]
    schema_list = ",".join(all_schemas)

    cmd = [
        "pg_dump",
        "-h", DB_HOST,
        "-p", DB_PORT,
        "-U", DB_USER,
        "-d", DB_NAME,
        "--schema-only",
        "--no-owner",
        "--no-privileges",
    ]

    # Add each schema
    for schema in all_schemas:
        cmd.extend(["-n", schema])

    env = os.environ.copy()
    env["PGPASSWORD"] = os.environ.get("PGPASSWORD", "postgres")

    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr}")
    return result.stdout


def backup_tier1():
    """Backup Tier 1: Governance / Evidence / Audit."""
    print("=" * 60)
    print("TIER 1 BACKUP: Governance / Evidence / Audit")
    print("=" * 60)

    backup_data = {
        "backup_type": "TIER_1_GOVERNANCE",
        "backup_date": BACKUP_DATE,
        "backup_timestamp": datetime.now(timezone.utc).isoformat(),
        "classification": "IRREPLACEABLE",
        "schemas": {},
        "meta_tables": [],
    }

    total_rows = 0

    # Export Tier 1 schemas
    for schema in TIER1_SCHEMAS:
        print(f"\nExporting schema: {schema}")
        tables = get_schema_tables(schema)
        schema_data = {"tables": {}, "table_count": len(tables)}

        for table in tables:
            print(f"  - {table}", end="")
            table_data = export_table_to_json(schema, table)
            schema_data["tables"][table] = {
                "row_count": table_data["row_count"],
                "hash": table_data["hash"],
                "data": table_data["data"],
            }
            total_rows += table_data["row_count"]
            print(f" ({table_data['row_count']} rows)")

        backup_data["schemas"][schema] = schema_data

    # Export specific fhq_meta audit/ADR tables
    print(f"\nExporting fhq_meta audit tables")
    for full_table in TIER1_META_TABLES:
        schema, table = full_table.split(".")
        print(f"  - {table}", end="")
        try:
            table_data = export_table_to_json(schema, table)
            backup_data["meta_tables"].append({
                "table": full_table,
                "row_count": table_data["row_count"],
                "hash": table_data["hash"],
                "data": table_data["data"],
            })
            total_rows += table_data["row_count"]
            print(f" ({table_data['row_count']} rows)")
        except Exception as e:
            print(f" (SKIPPED: {e})")

    backup_data["total_rows"] = total_rows
    backup_data["verification_hash"] = hashlib.sha256(
        json.dumps(backup_data, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]

    # Write to file
    output_file = GOVERNANCE_DIR / f"{BACKUP_DATE}_tier1_governance.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2, default=str)

    file_size = output_file.stat().st_size / (1024 * 1024)
    print(f"\nTier 1 backup complete: {output_file.name}")
    print(f"Total rows: {total_rows:,}")
    print(f"File size: {file_size:.2f} MB")

    return output_file


def backup_tier2():
    """Backup Tier 2: Canonical / Configs / Agents."""
    print("\n" + "=" * 60)
    print("TIER 2 BACKUP: Canonical / Configs / Agents")
    print("=" * 60)

    backup_data = {
        "backup_type": "TIER_2_CANONICAL",
        "backup_date": BACKUP_DATE,
        "backup_timestamp": datetime.now(timezone.utc).isoformat(),
        "classification": "DIFFICULT_TO_RECREATE",
        "schemas": {},
    }

    total_rows = 0

    for schema in TIER2_SCHEMAS:
        print(f"\nExporting schema: {schema}")
        tables = get_schema_tables(schema)
        schema_data = {"tables": {}, "table_count": len(tables)}

        for table in tables:
            print(f"  - {table}", end="")
            table_data = export_table_to_json(schema, table)
            schema_data["tables"][table] = {
                "row_count": table_data["row_count"],
                "hash": table_data["hash"],
                "data": table_data["data"],
            }
            total_rows += table_data["row_count"]
            print(f" ({table_data['row_count']} rows)")

        backup_data["schemas"][schema] = schema_data

    backup_data["total_rows"] = total_rows
    backup_data["verification_hash"] = hashlib.sha256(
        json.dumps(backup_data, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]

    # Write to file
    output_file = EVIDENCE_DIR / f"{BACKUP_DATE}_tier2_canonical.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2, default=str)

    file_size = output_file.stat().st_size / (1024 * 1024)
    print(f"\nTier 2 backup complete: {output_file.name}")
    print(f"Total rows: {total_rows:,}")
    print(f"File size: {file_size:.2f} MB")

    return output_file


def backup_schema():
    """Backup schema DDL (structure only)."""
    print("\n" + "=" * 60)
    print("SCHEMA BACKUP: DDL Export")
    print("=" * 60)

    ddl = export_schema_ddl()

    output_file = SCHEMA_DIR / f"{BACKUP_DATE}_schema.sql"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"-- FjordHQ Schema Backup\n")
        f.write(f"-- Date: {BACKUP_DATE}\n")
        f.write(f"-- Timestamp: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"-- Tier 1+2 Schemas (Governance, Canonical, Configs)\n")
        f.write(f"-- Hash: {hashlib.sha256(ddl.encode()).hexdigest()[:16]}\n")
        f.write(f"--\n\n")
        f.write(ddl)

    file_size = output_file.stat().st_size / 1024
    print(f"Schema backup complete: {output_file.name}")
    print(f"File size: {file_size:.1f} KB")

    return output_file


def generate_manifest(files: list):
    """Generate backup manifest."""
    manifest = {
        "backup_date": BACKUP_DATE,
        "backup_timestamp": datetime.now(timezone.utc).isoformat(),
        "backup_type": "TIER_1_2_GIT_BACKUP",
        "ceo_decision_ref": "2026-01-11",
        "stig_verification_ref": "STIG-VERIFY-2026-011",
        "files": [],
        "classification": {
            "tier1": "IRREPLACEABLE - Governance/Evidence/Audit",
            "tier2": "DIFFICULT_TO_RECREATE - Canonical/Configs",
            "tier3": "EXCLUDED - Re-ingestion recovery model",
        },
    }

    total_size = 0
    for f in files:
        size = f.stat().st_size
        total_size += size
        manifest["files"].append({
            "filename": f.name,
            "path": str(f.relative_to(BACKUP_DIR)),
            "size_bytes": size,
            "size_human": f"{size / (1024*1024):.2f} MB" if size > 1024*1024 else f"{size / 1024:.1f} KB",
            "hash": hashlib.sha256(f.read_bytes()).hexdigest()[:16],
        })

    manifest["total_size_bytes"] = total_size
    manifest["total_size_human"] = f"{total_size / (1024*1024):.2f} MB"

    manifest_file = BACKUP_DIR / f"{BACKUP_DATE}_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest: {manifest_file.name}")
    print(f"Total backup size: {manifest['total_size_human']}")

    return manifest_file


def main():
    """Execute Tier 1-2 backup."""
    print("=" * 60)
    print("FjordHQ TIER 1-2 DATABASE BACKUP")
    print(f"Date: {BACKUP_DATE}")
    print(f"Target: vision-IoS Git Repository")
    print("=" * 60)

    # Ensure directories exist
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    GOVERNANCE_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    files = []

    try:
        # Execute backups
        files.append(backup_schema())
        files.append(backup_tier1())
        files.append(backup_tier2())

        # Generate manifest
        manifest_file = generate_manifest(files)
        files.append(manifest_file)

        print("\n" + "=" * 60)
        print("BACKUP COMPLETE")
        print("=" * 60)
        print(f"Files generated: {len(files)}")
        for f in files:
            print(f"  - {f.relative_to(BACKUP_DIR)}")

        return 0

    except Exception as e:
        print(f"\nBACKUP FAILED: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
