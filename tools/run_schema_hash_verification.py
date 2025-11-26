#!/usr/bin/env python3
"""
SCHEMA HASH VERIFICATION TOOL
Agent: STIG
Purpose: Compute SHA-256 hashes for database schemas and tables
Compliance: ADR-007 Section 10.1, ADR-010, ADR-014

Usage:
    python tools/run_schema_hash_verification.py \
        --schemas fhq_org fhq_governance fhq_meta \
        --output logs/orchestrator_schema_hashes.json \
        --component FHQ_INTELLIGENCE_ORCHESTRATOR
"""

import os
import sys
import json
import hashlib
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List

import psycopg2
from psycopg2.extras import RealDictCursor


class Config:
    AGENT_ID = "STIG"

    @staticmethod
    def get_db_connection_string() -> str:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def compute_table_hash(conn, schema: str, table: str) -> Dict[str, Any]:
    """Compute SHA-256 hash for a table"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        try:
            cur.execute(f"SELECT * FROM {schema}.{table} ORDER BY 1")
            rows = cur.fetchall()
            data_str = json.dumps([dict(r) for r in rows], default=str, sort_keys=True)
            hash_value = hashlib.sha256(data_str.encode()).hexdigest()

            return {
                "schema": schema,
                "table": table,
                "hash_algorithm": "SHA-256",
                "hash_value": hash_value,
                "row_count": len(rows),
                "status": "PASS",
                "computed_at": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "schema": schema,
                "table": table,
                "status": "FAIL",
                "error": str(e)
            }


def get_schema_tables(conn, schema: str) -> List[str]:
    """Get all tables in a schema"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
            ORDER BY table_name
        """, (schema,))
        return [row[0] for row in cur.fetchall()]


def register_hashes(conn, hashes: List[Dict], component: str):
    """Register hashes in fhq_monitoring.hash_registry"""
    with conn.cursor() as cur:
        for h in hashes:
            if h.get("status") == "PASS":
                cur.execute("""
                    INSERT INTO fhq_monitoring.hash_registry (
                        schema_name, table_name, hash_algorithm,
                        hash_value, row_count, computed_by,
                        verification_status, adr_reference
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    h["schema"], h["table"], h["hash_algorithm"],
                    h["hash_value"], h["row_count"], Config.AGENT_ID,
                    "VERIFIED", "ADR-007"
                ))
        conn.commit()


def main():
    parser = argparse.ArgumentParser(description='Schema Hash Verification Tool')
    parser.add_argument('--schemas', nargs='+', required=True, help='Schemas to verify')
    parser.add_argument('--output', required=True, help='Output JSON file')
    parser.add_argument('--component', required=True, help='Component name')
    args = parser.parse_args()

    print(f"[STIG] Schema Hash Verification for {args.component}")
    print("=" * 60)

    conn = psycopg2.connect(Config.get_db_connection_string())

    result = {
        "component": args.component,
        "verification_type": "SCHEMA_HASH",
        "agent": Config.AGENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "schemas": {},
        "summary": {
            "total_tables": 0,
            "passed": 0,
            "failed": 0
        }
    }

    all_hashes = []

    for schema in args.schemas:
        print(f"\n[{schema}]")
        tables = get_schema_tables(conn, schema)
        result["schemas"][schema] = {"tables": []}

        for table in tables:
            hash_result = compute_table_hash(conn, schema, table)
            result["schemas"][schema]["tables"].append(hash_result)
            all_hashes.append(hash_result)

            result["summary"]["total_tables"] += 1
            if hash_result["status"] == "PASS":
                result["summary"]["passed"] += 1
                print(f"  [PASS] {table}: {hash_result['hash_value'][:16]}... ({hash_result['row_count']} rows)")
            else:
                result["summary"]["failed"] += 1
                print(f"  [FAIL] {table}: {hash_result.get('error', 'Unknown error')}")

    # Register hashes
    register_hashes(conn, all_hashes, args.component)
    print(f"\n[INFO] Registered {len(all_hashes)} hashes in fhq_monitoring.hash_registry")

    # Compute overall status
    result["status"] = "PASS" if result["summary"]["failed"] == 0 else "FAIL"

    # Compute bundle hash
    bundle_str = json.dumps(result, sort_keys=True)
    result["evidence_hash"] = hashlib.sha256(bundle_str.encode()).hexdigest()

    # Write output
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"RESULT: {result['status']}")
    print(f"Tables: {result['summary']['passed']}/{result['summary']['total_tables']} PASS")
    print(f"Evidence hash: {result['evidence_hash'][:32]}...")
    print(f"Output: {args.output}")

    conn.close()
    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == '__main__':
    main()
