"""
ADR Constitution Ingestion Script
=================================
Ingests ADR-001 (System Charter) into fhq_meta.adr_registry

This script parses the canonical ADR-001 markdown file and inserts/updates
the registry entry in the database, establishing the constitutional foundation.

Usage:
    python ingest_constitution.py

Environment:
    DATABASE_URL: PostgreSQL connection string (required in .env)
"""

import os
import re
import hashlib
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

# ------------------------------
# 1. Load environment variables
# ------------------------------
load_dotenv()
DB_DSN = os.getenv("DATABASE_URL")

if not DB_DSN:
    print("CRITICAL: DATABASE_URL missing in .env")
    exit(1)

# ------------------------------
# 2. CONFIGURATION
# ------------------------------
# Default path - can be overridden
ADR_DIRECTORY = os.getenv(
    "ADR_DIRECTORY",
    r"C:\fhq-market-system\vision-IoS\00_CONSTITUTION"
)


# ------------------------------
# 3. HELPER FUNCTIONS
# ------------------------------

def calculate_hash(content: str) -> str:
    """
    Calculate SHA-256 hash of the file content.
    This creates a unique fingerprint for version tracking.
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def parse_adr_content(content: str, filename: str) -> dict:
    """
    Parse ADR markdown content and extract metadata.

    Returns a dict with:
        - id: ADR identifier (e.g., 'ADR-001')
        - title: Document title
        - version: Version string
        - status: Document status (e.g., 'CANONICAL', 'PRODUCTION')
        - hash: SHA-256 content hash
    """
    # Extract ADR ID from filename (e.g., 'ADR-001' from 'ADR-001_2026_PRODUCTION.md')
    adr_id_match = re.match(r'^(ADR-\d{3})', filename.upper())
    adr_id = adr_id_match.group(1) if adr_id_match else "ADR-UNKNOWN"

    # Extract title from markdown header (# **ADR-001 - TITLE**)
    title_match = re.search(r'^#\s*\*?\*?ADR-\d{3}[^*\n]*\*?\*?\s*[–-]\s*(.+?)(?:\*\*)?$',
                           content, re.MULTILINE | re.IGNORECASE)
    if title_match:
        title = title_match.group(1).strip().rstrip('*')
    else:
        # Fallback: extract from filename
        title = filename.replace('.md', '').replace('_', ' ')

    # Extract version from content
    version_match = re.search(r'\*?\*?Version:?\*?\*?\s*([^\n]+)', content, re.IGNORECASE)
    version = version_match.group(1).strip() if version_match else "1.0"

    # Determine status from filename or content
    status = "PRODUCTION"  # Default
    if "CANONICAL" in content.upper() or "ROOT AUTHORITY" in content.upper():
        status = "CANONICAL"
    elif "DRAFT" in filename.upper():
        status = "DRAFT"
    elif "DEPRECATED" in filename.upper():
        status = "DEPRECATED"

    # Calculate content hash
    content_hash = calculate_hash(content)

    return {
        "id": adr_id,
        "title": title,
        "version": version,
        "status": status,
        "hash": content_hash
    }


def ensure_schema_exists(cur):
    """
    Ensure fhq_meta schema and adr_registry table exist.
    Creates them if they don't exist, and adds missing columns.
    """
    # Create schema if not exists
    cur.execute("CREATE SCHEMA IF NOT EXISTS fhq_meta;")

    # Create adr_registry table if not exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fhq_meta.adr_registry (
            id TEXT PRIMARY KEY,
            title TEXT,
            hash TEXT,
            version TEXT,
            status TEXT DEFAULT 'DRAFT',
            file_path TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            created_by TEXT DEFAULT 'SYSTEM'
        );
    """)

    # Add missing columns if table already exists with different schema
    columns_to_add = [
        ("hash", "TEXT"),
        ("title", "TEXT"),
        ("status", "TEXT DEFAULT 'DRAFT'"),
        ("version", "TEXT"),
        ("file_path", "TEXT"),
        ("created_at", "TIMESTAMPTZ DEFAULT NOW()"),
        ("updated_at", "TIMESTAMPTZ DEFAULT NOW()"),
        ("created_by", "TEXT DEFAULT 'SYSTEM'"),
    ]

    for col_name, col_type in columns_to_add:
        cur.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'fhq_meta'
                    AND table_name = 'adr_registry'
                    AND column_name = '{col_name}'
                ) THEN
                    ALTER TABLE fhq_meta.adr_registry ADD COLUMN {col_name} {col_type};
                END IF;
            END $$;
        """)

    # Create indexes if not exist
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_adr_registry_status
            ON fhq_meta.adr_registry(status);
        CREATE INDEX IF NOT EXISTS idx_adr_registry_hash
            ON fhq_meta.adr_registry(hash);
    """)


# ------------------------------
# 4. MAIN INGESTION FUNCTION
# ------------------------------

def run_ingestion_adr_001():
    """
    Main ingestion function for ADR-001 (System Charter).

    1. Finds ADR-001 file in the constitution directory
    2. Parses metadata from the markdown content
    3. Upserts the entry into fhq_meta.adr_registry
    """
    # Validate directory exists
    if not os.path.isdir(ADR_DIRECTORY):
        print(f"CRITICAL: Directory not found: {ADR_DIRECTORY}")
        print("Set ADR_DIRECTORY environment variable or update the script.")
        return

    try:
        conn = psycopg2.connect(DB_DSN)
        cur = conn.cursor()

        # Ensure schema and table exist
        ensure_schema_exists(cur)
        conn.commit()

        # Find ADR-001 file
        target_file = next(
            (
                f for f in os.listdir(ADR_DIRECTORY)
                if f.upper().startswith("ADR-001") and f.upper().endswith(".MD")
            ),
            None
        )

        if not target_file:
            print("Kritisk: Fant ikke filen ADR-001 i mappen.")
            print(f"Sjekket mappe: {ADR_DIRECTORY}")
            return

        print(f"Fant filen: {target_file}. Starter behandling...")

        filepath = os.path.abspath(os.path.join(ADR_DIRECTORY, target_file))

        # Read and parse content
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        meta = parse_adr_content(content, target_file)

        print(f"   ID:      {meta['id']}")
        print(f"   Tittel:  {meta['title']}")
        print(f"   Versjon: {meta['version']}")
        print(f"   Status:  {meta['status']}")
        print(f"   Hash:    {meta['hash'][:16]}...")

        # SQL: UPSERT (Insert or update if exists)
        sql = """
            INSERT INTO fhq_meta.adr_registry (
                id, title, hash, version, status, file_path, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id)
            DO UPDATE SET
                title = EXCLUDED.title,
                hash = EXCLUDED.hash,
                version = EXCLUDED.version,
                status = EXCLUDED.status,
                file_path = EXCLUDED.file_path,
                updated_at = NOW();
        """

        cur.execute(sql, (
            meta["id"],
            meta["title"],
            meta["hash"],
            meta["version"],
            meta["status"],
            filepath,
            "SYSTEM"
        ))

        conn.commit()

        # Verify the insert
        cur.execute("SELECT id, title, status, hash FROM fhq_meta.adr_registry WHERE id = %s", (meta["id"],))
        result = cur.fetchone()

        if result:
            print(f"\n SUKSESS: {result[0]} er registrert i databasen")
            print(f"   Status: {result[2]}")
            print(f"   Hash:   {result[3][:16]}...")

        cur.close()
        conn.close()

    except psycopg2.Error as e:
        print(f"\n DATABASE FEIL: {e}")
        print("\nSjekk:")
        print("  1. DATABASE_URL er korrekt i .env")
        print("  2. PostgreSQL kjorer")
        print("  3. Du har tilgang til databasen")
    except Exception as e:
        print(f"\n FEIL: {e}")


# ------------------------------
# 5. ENTRY POINT
# ------------------------------

if __name__ == "__main__":
    print("=" * 50)
    print("ADR-001 Constitution Ingestion")
    print("=" * 50)
    print(f"Database: {'Configured' if DB_DSN else 'MISSING!'}")
    print(f"Directory: {ADR_DIRECTORY}")
    print("=" * 50)
    print()

    run_ingestion_adr_001()
