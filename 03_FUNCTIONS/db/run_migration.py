#!/usr/bin/env python3
"""
Python Migration Runner for FjordHQ Vision-iOS

Handles all SQL migrations with proper encoding, error handling,
and ON_ERROR_STOP behavior. Reads UTF-8 SQL files
and executes them via psycopg2.

CEO-DIR-2026-DB-EXECUTION-SUBSTRATE-STABILIZATION-003
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import hashlib
import json
from datetime import datetime

load_dotenv()

# Database configuration
DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": int(os.getenv("PGPORT", 54322)),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres")
}

def run_migration(file_path: str) -> dict:
    """
    Execute a SQL migration file and return result.
    Stops on first error (ON_ERROR_STOP).
    Returns: {"success": bool, "error": str, "changes": int, "rows_affected": int}
    """
    # Read SQL file with UTF-8 encoding
    with open(file_path, "r", encoding="utf-8", newline="") as f:
        sql_content = f.read()

    # Compute SQL hash for tracking
    sql_hash = hashlib.sha256(sql_content.encode('utf-8')).hexdigest()

    result = {
        "file": file_path,
        "sql_hash": sql_hash,
        "timestamp": datetime.utcnow().isoformat(),
        "success": False,
        "error": None,
        "rows_affected": 0
    }

    try:
        # Connect to database
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        cursor = conn.cursor()

        # Execute SQL
        cursor.execute(sql_content)

        # Get rows affected (if any)
        try:
            result["rows_affected"] = cursor.rowcount
        except:
            result["rows_affected"] = 0

        # Commit transaction
        conn.commit()

        result["success"] = True
        print(f"[SUCCESS] {file_path}: {result['rows_affected']} rows affected")

        cursor.close()
        conn.close()

    except psycopg2.Error as e:
        result["error"] = str(e)
        print(f"[ERROR] {file_path}: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_migration.py <sql_file>")
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    result = run_migration(file_path)

    # Exit with error code if migration failed
    sys.exit(0 if result["success"] else 1)
