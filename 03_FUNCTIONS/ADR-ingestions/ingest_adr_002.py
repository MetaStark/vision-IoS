import os
import psycopg2
import json
from datetime import datetime
from dotenv import load_dotenv

# -------------------------------------------------------
# calculate_hash + parse_adr_content
# -------------------------------------------------------

def calculate_hash(content):
    normalized = content.replace("\r\n", "\n")
    import hashlib
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def parse_adr_content(content, filename):
    import re

    # Extract ADR ID
    id_match = re.search(r"(ADR-\d+)", filename, re.IGNORECASE)
    if not id_match:
        id_match = re.search(r"(ADR-\d+)", content, re.IGNORECASE)
    adr_id = id_match.group(1).upper() if id_match else "UNKNOWN"

    # Title
    title_match = re.search(r"^#\s*(.*)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else filename.replace(".md","")

    # Status
    status_match = re.search(r"Status:\s*(.*)", content, re.IGNORECASE)
    status = status_match.group(1).strip() if status_match else "ACTIVE"

    # Version
    version_match = re.search(r"Version:\s*(.*)", content, re.IGNORECASE)
    version = version_match.group(1).strip() if version_match else "1.0"

    return {
        "id": adr_id,
        "title": title,
        "status": status,
        "version": version,
        "hash": calculate_hash(content)
    }

# -------------------------------------------------------
# Konfigurasjon
# -------------------------------------------------------

load_dotenv()
DB_DSN = os.getenv("DATABASE_URL")
ADR_DIRECTORY = r"C:\fhq-market-system\vision-IoS\00_CONSTITUTION"

# -------------------------------------------------------
# ADR-002 ingestion
# -------------------------------------------------------

def run_ingestion_adr_002():
    if not DB_DSN:
        print("❌ DATABASE_URL mangler i .env")
        return

    print("==================================================")
    print("ADR-002 Ingestion")
    print("==================================================")
    print(f"Directory: {ADR_DIRECTORY}")

    try:
        conn = psycopg2.connect(DB_DSN)
        cur = conn.cursor()

        target_file = next(
            (
                f for f in os.listdir(ADR_DIRECTORY)
                if f.upper().startswith("ADR-002") and f.upper().endswith(".MD")
            ),
            None
        )

        if not target_file:
            print("❌ Fant ikke ADR-002 filen.")
            return

        path = os.path.join(ADR_DIRECTORY, target_file)
        with open(path, "r", encoding="utf-8") as file:
            content = file.read()

        meta = parse_adr_content(content, target_file)

        # Metadata JSONB
        metadata = {
            "ingested_at": datetime.utcnow().isoformat(),
            "source_file": target_file,
            "parser_version": "1.0"
        }

        sql = """
            INSERT INTO fhq_meta.adr_registry (
                adr_id,
                adr_title,
                adr_status,
                adr_type,
                current_version,
                approval_authority,
                effective_date,
                superseded_by,
                file_path,
                hash,
                hash_length,
                metadata,
                created_by
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (adr_id)
            DO UPDATE SET
                adr_title = EXCLUDED.adr_title,
                adr_status = EXCLUDED.adr_status,
                adr_type = EXCLUDED.adr_type,
                current_version = EXCLUDED.current_version,
                approval_authority = EXCLUDED.approval_authority,
                effective_date = EXCLUDED.effective_date,
                superseded_by = EXCLUDED.superseded_by,
                file_path = EXCLUDED.file_path,
                hash = EXCLUDED.hash,
                hash_length = EXCLUDED.hash_length,
                metadata = EXCLUDED.metadata,
                updated_at = NOW();
        """

        cur.execute(sql, (
            meta["id"],
            meta["title"],
            meta["status"],
            "COMPLIANCE",
            meta["version"],
            "CEO",
            datetime.utcnow().date(),
            None,
            path,
            meta["hash"],
            len(meta["hash"]),
            json.dumps(metadata),
            "SYSTEM"
        ))

        conn.commit()
        cur.close()
        conn.close()

        print(f"🎉 SUKSESS: ADR-002 registrert | Hash: {meta['hash'][:8]}")

    except Exception as e:
        print(f"💥 FEIL: {e}")

if __name__ == "__main__":
    run_ingestion_adr_002()
