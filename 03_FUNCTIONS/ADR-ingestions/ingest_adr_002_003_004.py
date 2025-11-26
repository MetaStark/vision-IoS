"""
ADR Batch Ingestion Script (ADR-002 to ADR-004)
================================================
Ingests ADR-002, ADR-003, ADR-004 into fhq_meta.adr_registry

Uses the EXISTING table schema with check constraints:
- adr_status: DRAFT, PROPOSED, APPROVED, DEPRECATED, SUPERSEDED
- adr_type: CONSTITUTIONAL, ARCHITECTURAL, OPERATIONAL, COMPLIANCE, ECONOMIC

Usage:
    python ingest_adr_002_003_004.py
"""

import os
import re
import hashlib
import json
import psycopg2
from dotenv import load_dotenv
from datetime import datetime, date

load_dotenv()
DB_DSN = os.getenv("DATABASE_URL")

if not DB_DSN:
    print("CRITICAL: DATABASE_URL missing in .env")
    exit(1)

ADR_DIRECTORY = os.getenv(
    "ADR_DIRECTORY",
    r"C:\fhq-market-system\vision-IoS\00_CONSTITUTION"
)

# Target ADRs to ingest
TARGET_ADRS = ["ADR-002", "ADR-003", "ADR-004"]


def calculate_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def parse_adr_content(content: str, filename: str) -> dict:
    """Parse ADR markdown and return metadata matching DB schema."""

    # Extract ADR ID
    adr_id_match = re.match(r'^(ADR-\d{3})', filename.upper())
    adr_id = adr_id_match.group(1) if adr_id_match else "ADR-UNKNOWN"

    # Extract title
    title_match = re.search(r'^#\s*\*?\*?ADR-\d{3}[^*\n]*\*?\*?\s*[–-]\s*(.+?)(?:\*\*)?$',
                           content, re.MULTILINE | re.IGNORECASE)
    if title_match:
        title = title_match.group(1).strip().rstrip('*')
    else:
        title = filename.replace('.md', '').replace('_', ' ')

    # Extract version
    version_match = re.search(r'\*?\*?Version:?\*?\*?\s*([^\n]+)', content, re.IGNORECASE)
    version = version_match.group(1).strip() if version_match else "1.0"

    # Determine status (allowed: DRAFT, PROPOSED, APPROVED, DEPRECATED, SUPERSEDED)
    status = "APPROVED"
    if "DRAFT" in filename.upper():
        status = "DRAFT"
    elif "DEPRECATED" in filename.upper():
        status = "DEPRECATED"
    elif "SUPERSEDED" in filename.upper():
        status = "SUPERSEDED"

    # Determine type (allowed: CONSTITUTIONAL, ARCHITECTURAL, OPERATIONAL, COMPLIANCE, ECONOMIC)
    adr_type = "CONSTITUTIONAL"

    # ADR-specific type mapping
    if adr_id == "ADR-002":
        adr_type = "OPERATIONAL"  # Audit & Error Reconciliation
    elif adr_id == "ADR-003":
        adr_type = "COMPLIANCE"   # Institutional Standards & Compliance
    elif adr_id == "ADR-004":
        adr_type = "ARCHITECTURAL"  # Change Gates Architecture

    # Override based on content keywords
    if "COMPLIANCE" in filename.upper() or "COMPLIANCE FRAMEWORK" in content.upper():
        adr_type = "COMPLIANCE"
    elif "ECONOMIC" in filename.upper() or "ECONOMIC SAFETY" in content.upper():
        adr_type = "ECONOMIC"

    # Extract owner
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

    content_hash = calculate_hash(content)

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


def run_ingestion():
    if not os.path.isdir(ADR_DIRECTORY):
        print(f"CRITICAL: Directory not found: {ADR_DIRECTORY}")
        return

    try:
        conn = psycopg2.connect(DB_DSN)
        cur = conn.cursor()

        # Find all target ADR files
        all_files = os.listdir(ADR_DIRECTORY)

        success_count = 0
        error_count = 0

        for target_adr in TARGET_ADRS:
            target_file = next(
                (f for f in all_files if f.upper().startswith(target_adr) and f.upper().endswith(".MD")),
                None
            )

            if not target_file:
                print(f"  IKKE FUNNET: {target_adr}")
                error_count += 1
                continue

            print(f"\n{'='*50}")
            print(f"Behandler: {target_file}")
            print('='*50)

            filepath = os.path.abspath(os.path.join(ADR_DIRECTORY, target_file))

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            meta = parse_adr_content(content, target_file)

            print(f"   ID:       {meta['adr_id']}")
            print(f"   Tittel:   {meta['adr_title'][:50]}...")
            print(f"   Type:     {meta['adr_type']}")
            print(f"   Status:   {meta['adr_status']}")
            print(f"   Versjon:  {meta['current_version']}")

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
            print(f"   SUKSESS!")
            success_count += 1

        # Summary
        print(f"\n{'='*50}")
        print("OPPSUMMERING")
        print('='*50)
        print(f"   Vellykket: {success_count}")
        print(f"   Feilet:    {error_count}")

        # Show what's in the registry now
        cur.execute("""
            SELECT adr_id, adr_title, adr_status, adr_type
            FROM fhq_meta.adr_registry
            ORDER BY adr_id
        """)
        rows = cur.fetchall()
        if rows:
            print(f"\nADR REGISTRY INNHOLD ({len(rows)} rader):")
            for row in rows:
                print(f"   {row[0]}: {row[1][:40]}... [{row[2]}/{row[3]}]")

        cur.close()
        conn.close()

    except psycopg2.Error as e:
        print(f"\nDATABASE FEIL: {e}")
    except Exception as e:
        print(f"\nFEIL: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("ADR Batch Ingestion (ADR-002, ADR-003, ADR-004)")
    print("=" * 50)
    print(f"Database: {'Configured' if DB_DSN else 'MISSING!'}")
    print(f"Directory: {ADR_DIRECTORY}")
    print(f"Targets: {', '.join(TARGET_ADRS)}")

    run_ingestion()
