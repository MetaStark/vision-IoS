"""
ADR Constitution Ingestion Script
=================================
Ingests ADR-001 (System Charter) into fhq_meta.adr_registry

Uses the EXISTING table schema with columns:
- adr_id, adr_title, adr_status, adr_type, current_version
- sha256_hash, file_path, approval_authority, effective_date
- metadata, created_at, updated_at

Usage:
    python ingest_constitution.py

Environment:
    DATABASE_URL: PostgreSQL connection string (required in .env)
"""

import os
import re
import hashlib
import json
import psycopg2
from dotenv import load_dotenv
from datetime import datetime, date

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
ADR_DIRECTORY = os.getenv(
    "ADR_DIRECTORY",
    r"C:\fhq-market-system\vision-IoS\00_CONSTITUTION"
)


# ------------------------------
# 3. HELPER FUNCTIONS
# ------------------------------

def calculate_hash(content: str) -> str:
    """Calculate SHA-256 hash of the file content."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def parse_adr_content(content: str, filename: str) -> dict:
    """
    Parse ADR markdown content and extract metadata.
    Returns dict matching the EXISTING database schema.
    """
    # Extract ADR ID from filename
    adr_id_match = re.match(r'^(ADR-\d{3})', filename.upper())
    adr_id = adr_id_match.group(1) if adr_id_match else "ADR-UNKNOWN"

    # Extract title from markdown header
    title_match = re.search(r'^#\s*\*?\*?ADR-\d{3}[^*\n]*\*?\*?\s*[–-]\s*(.+?)(?:\*\*)?$',
                           content, re.MULTILINE | re.IGNORECASE)
    if title_match:
        title = title_match.group(1).strip().rstrip('*')
    else:
        title = filename.replace('.md', '').replace('_', ' ')

    # Extract version from content
    version_match = re.search(r'\*?\*?Version:?\*?\*?\s*([^\n]+)', content, re.IGNORECASE)
    version = version_match.group(1).strip() if version_match else "1.0"

    # Determine status
    status = "PRODUCTION"
    if "CANONICAL" in content.upper() or "ROOT AUTHORITY" in content.upper():
        status = "CANONICAL"
    elif "DRAFT" in filename.upper():
        status = "DRAFT"
    elif "DEPRECATED" in filename.upper():
        status = "DEPRECATED"

    # Determine type
    adr_type = "GOVERNANCE"  # Default
    if "CHARTER" in filename.upper() or "CHARTER" in content.upper():
        adr_type = "CHARTER"
    elif "COMPLIANCE" in filename.upper():
        adr_type = "COMPLIANCE"
    elif "ORCHESTRATOR" in filename.upper():
        adr_type = "ORCHESTRATOR"

    # Extract owner/approval authority
    owner_match = re.search(r'\*?\*?Owner:?\*?\*?\s*([^\n]+)', content, re.IGNORECASE)
    approval_authority = owner_match.group(1).strip() if owner_match else "CEO"

    # Extract date
    date_match = re.search(r'\*?\*?Date:?\*?\*?\s*(\d{1,2}\s+\w+\s+\d{4})', content, re.IGNORECASE)
    effective_date = None
    if date_match:
        try:
            from dateutil import parser as date_parser
            effective_date = date_parser.parse(date_match.group(1)).date()
        except:
            effective_date = date.today()
    else:
        effective_date = date.today()

    # Calculate content hash
    content_hash = calculate_hash(content)

    # Build metadata JSON
    metadata = {
        "source_file": filename,
        "ingested_at": datetime.now().isoformat(),
        "parser_version": "1.0"
    }

    return {
        "adr_id": adr_id,
        "adr_title": title,
        "adr_status": status,
        "adr_type": adr_type,
        "current_version": version,
        "approval_authority": approval_authority,
        "effective_date": effective_date,
        "sha256_hash": content_hash,
        "metadata": json.dumps(metadata)
    }


# ------------------------------
# 4. MAIN INGESTION FUNCTION
# ------------------------------

def run_ingestion_adr_001():
    """
    Main ingestion function for ADR-001 (System Charter).
    Uses EXISTING table schema.
    """
    if not os.path.isdir(ADR_DIRECTORY):
        print(f"CRITICAL: Directory not found: {ADR_DIRECTORY}")
        return

    try:
        conn = psycopg2.connect(DB_DSN)
        cur = conn.cursor()

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
            return

        print(f"Fant filen: {target_file}. Starter behandling...")

        filepath = os.path.abspath(os.path.join(ADR_DIRECTORY, target_file))

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        meta = parse_adr_content(content, target_file)

        print(f"   ID:       {meta['adr_id']}")
        print(f"   Tittel:   {meta['adr_title']}")
        print(f"   Type:     {meta['adr_type']}")
        print(f"   Status:   {meta['adr_status']}")
        print(f"   Versjon:  {meta['current_version']}")
        print(f"   Hash:     {meta['sha256_hash'][:16]}...")

        # SQL: UPSERT using EXISTING column names
        sql = """
            INSERT INTO fhq_meta.adr_registry (
                adr_id, adr_title, adr_status, adr_type, current_version,
                approval_authority, effective_date, file_path, sha256_hash, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (adr_id)
            DO UPDATE SET
                adr_title = EXCLUDED.adr_title,
                adr_status = EXCLUDED.adr_status,
                adr_type = EXCLUDED.adr_type,
                current_version = EXCLUDED.current_version,
                approval_authority = EXCLUDED.approval_authority,
                effective_date = EXCLUDED.effective_date,
                file_path = EXCLUDED.file_path,
                sha256_hash = EXCLUDED.sha256_hash,
                metadata = EXCLUDED.metadata,
                updated_at = NOW();
        """

        cur.execute(sql, (
            meta["adr_id"],
            meta["adr_title"],
            meta["adr_status"],
            meta["adr_type"],
            meta["current_version"],
            meta["approval_authority"],
            meta["effective_date"],
            filepath,
            meta["sha256_hash"],
            meta["metadata"]
        ))

        conn.commit()

        # Verify
        cur.execute("""
            SELECT adr_id, adr_title, adr_status, sha256_hash
            FROM fhq_meta.adr_registry
            WHERE adr_id = %s
        """, (meta["adr_id"],))
        result = cur.fetchone()

        if result:
            print(f"\nSUKSESS: {result[0]} er registrert i databasen")
            print(f"   Tittel: {result[1]}")
            print(f"   Status: {result[2]}")
            print(f"   Hash:   {result[3][:16] if result[3] else 'N/A'}...")

        cur.close()
        conn.close()

    except psycopg2.Error as e:
        print(f"\nDATABASE FEIL: {e}")
        print("\nSjekk:")
        print("  1. DATABASE_URL er korrekt i .env")
        print("  2. PostgreSQL kjorer")
        print("  3. Du har tilgang til databasen")
    except Exception as e:
        print(f"\nFEIL: {e}")


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
