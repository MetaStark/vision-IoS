import os
import re
import hashlib
import psycopg2
from dotenv import load_dotenv

# ------------------------------
# 1. Load environment variables
# ------------------------------
load_dotenv()
DB_DSN = os.getenv("DATABASE_URL")

if not DB_DSN:
    print("❌ CRITICAL: DATABASE_URL missing in .env")
    exit(1)

# ------------------------------
# 2. CONFIGURATION
# ------------------------------
ADR_DIRECTORY = r"C:\fhq-market-system\vision-IoS\00_CONSTITUTION"

def calculate_hash(content):
    """Deterministic SHA-256 hashing with newline normalization."""
    normalized = content.replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def parse_adr_content(content, filename):
    """Extract ADR metadata from canonical documents."""

    # --- ADR ID ---
    id_match = re.search(r"(ADR-\d+)", filename, re.IGNORECASE)
    if not id_match:
        id_match = re.search(r"(ADR-\d+)", content, re.IGNORECASE)

    adr_id = id_match.group(1).upper() if id_match else "UNKNOWN"

    # --- TITLE ---
    # Matches lines like:
    # # ADR-004 – Canonical Something
    # # ADR-012_2026_PRODUCTION_Economic Safety Architecture
    title_match = re.search(
        r"^#\s*(ADR-\d+.*?)\s*$",
        content,
        re.MULTILINE
    )

    if title_match:
        raw_title = title_match.group(1)
        # strip "ADR-001 – " prefix
        title = re.sub(r"ADR-\d+\s*[–-]\s*", "", raw_title).strip()
    else:
        title = filename.replace(".md", "").replace(".MD", "")

    # --- STATUS ---
    status_match = re.search(r"Status:\s*(.*)", content, re.IGNORECASE)
    status = status_match.group(1).strip() if status_match else "ACTIVE"

    # --- VERSION ---
    version_match = re.search(
        r"(Canonical Version|Version):\s*(.*)",
        content,
        re.IGNORECASE
    )
    version = version_match.group(2).strip() if version_match else "2026.PRODUCTION"

    hash_value = calculate_hash(content)

    return {
        "id": adr_id,
        "title": title,
        "status": status,
        "version": version,
        "hash": hash_value
    }

def run_ingestion():
    print(f"🚀 Starting ingestion from: {ADR_DIRECTORY}")

    if not os.path.isdir(ADR_DIRECTORY):
        print(f"❌ Directory not found: {ADR_DIRECTORY}")
        return

    # Filter correct ADR files
    files = sorted([
        f for f in os.listdir(ADR_DIRECTORY)
        if f.upper().startswith("ADR-") and f.upper().endswith(".MD")
    ])

    if not files:
        print("❌ No ADR files found.")
        return

    print(f"📄 Found {len(files)} ADR files.")

    try:
        conn = psycopg2.connect(DB_DSN)
        cur = conn.cursor()

        ingested = 0

        for filename in files:
            filepath = os.path.abspath(os.path.join(ADR_DIRECTORY, filename))

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            meta = parse_adr_content(content, filename)

            if meta["id"] == "UNKNOWN":
                print(f"⚠️ Skipping {filename}: Could not extract ADR ID.")
                continue

            sql = """
                INSERT INTO fhq_meta.adr_registry (
                    id, title, hash, version, status, file_path
                )
                VALUES (%s, %s, %s, %s, %s, %s)
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
                filepath
            ))

            print(f"✅ {meta['id']} written | hash {meta['hash'][:8]}...")
            ingested += 1

        conn.commit()
        cur.close()
        conn.close()

        print(f"\n🎯 DONE: {ingested} ADRs ingested into canonical registry.")

    except Exception as e:
        print(f"\n💥 ERROR: {e}")

if __name__ == "__main__":
    run_ingestion()
