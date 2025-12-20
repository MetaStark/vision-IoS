"""
CEO-DIR-2025-INGEST-001: Canonical Document Ingestion
======================================================
First-Order Truth Declaration for ADR, IoS, EC documents

FORBEHOLD 1: This is Layer 8 (Observability), NOT Layer 1
FORBEHOLD 2: One-way authority only - Files -> canonical_documents -> registries
FORBEHOLD 3: Ingestion = readability only, NOT operational authority

Executor: STIG
Verifier: VEGA
"""

import os
import sys
import io
import re
import hashlib
import json
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Database connection
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 54322,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'postgres'
}

BASE_PATH = r"C:\fhq-market-system\vision-ios"

# Document mappings
ADR_PATH = os.path.join(BASE_PATH, "00_CONSTITUTION")
IOS_PATH = os.path.join(BASE_PATH, "02_IOS")
EC_PATH = os.path.join(BASE_PATH, "10_EMPLOYMENT CONTRACTS")

# ADR metadata mapping (document_code -> owner, tier, status)
ADR_METADATA = {
    'ADR-001': {'owner': 'CEO', 'tier': 1, 'status': 'ACTIVE', 'title': 'System Charter'},
    'ADR-002': {'owner': 'VEGA', 'tier': 1, 'status': 'ACTIVE', 'title': 'Audit and Error Reconciliation Charter'},
    'ADR-003': {'owner': 'STIG', 'tier': 2, 'status': 'ACTIVE', 'title': 'Institutional Standards and Compliance Framework'},
    'ADR-004': {'owner': 'VEGA', 'tier': 1, 'status': 'ACTIVE', 'title': 'Change Gates Architecture (G0-G4)'},
    'ADR-005': {'owner': 'CEO', 'tier': 1, 'status': 'ACTIVE', 'title': 'Mission & Vision Charter'},
    'ADR-006': {'owner': 'CEO', 'tier': 1, 'status': 'ACTIVE', 'title': 'VEGA Autonomy and Governance Engine Charter'},
    'ADR-007': {'owner': 'CEO', 'tier': 1, 'status': 'ACTIVE', 'title': 'Orchestrator Architecture'},
    'ADR-008': {'owner': 'STIG', 'tier': 1, 'status': 'ACTIVE', 'title': 'Cryptographic Key Management and Rotation'},
    'ADR-009': {'owner': 'VEGA', 'tier': 2, 'status': 'ACTIVE', 'title': 'Governance Approval Workflow for Agent Suspension'},
    'ADR-010': {'owner': 'STIG', 'tier': 2, 'status': 'ACTIVE', 'title': 'State Reconciliation Methodology and Discrepancy Scoring'},
    'ADR-011': {'owner': 'STIG', 'tier': 2, 'status': 'ACTIVE', 'title': 'Fortress and VEGA Testsuite'},
    'ADR-012': {'owner': 'CEO', 'tier': 1, 'status': 'ACTIVE', 'title': 'Economic Safety Architecture'},
    'ADR-013': {'owner': 'STIG', 'tier': 2, 'status': 'ACTIVE', 'title': 'Canonical ADR Governance and One-True-Source'},
    'ADR-014': {'owner': 'CEO', 'tier': 1, 'status': 'ACTIVE', 'title': 'Executive Activation and Sub-Executive Governance'},
    'ADR-015': {'owner': 'VEGA', 'tier': 2, 'status': 'ACTIVE', 'title': 'Meta-Governance Framework for ADR Ingestion'},
    'ADR-016': {'owner': 'LINE', 'tier': 1, 'status': 'ACTIVE', 'title': 'DEFCON Circuit Breaker Protocol'},
    'ADR-017': {'owner': 'CEO', 'tier': 1, 'status': 'ACTIVE', 'title': 'MIT Quad Protocol for Alpha Sovereignty'},
    'ADR-018': {'owner': 'STIG', 'tier': 2, 'status': 'ACTIVE', 'title': 'Agent State Reliability Protocol (ASRP)'},
    'ADR-019': {'owner': 'CEO', 'tier': 1, 'status': 'ACTIVE', 'title': 'Human Interaction & Application Layer Charter'},
    'ADR-020': {'owner': 'CEO', 'tier': 1, 'status': 'ACTIVE', 'title': 'Autonomous Cognitive Intelligence'},
    'ADR-021': {'owner': 'FINN', 'tier': 2, 'status': 'ACTIVE', 'title': 'Cognitive Engine Architecture Deep Research Protocol'},
}

# IoS metadata mapping
IOS_METADATA = {
    'IoS-001': {'owner': 'STIG', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-003', 'ADR-012']},
    'IoS-002': {'owner': 'STIG', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-003']},
    'IoS-003': {'owner': 'FINN', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-003', 'ADR-017']},
    'IoS-004': {'owner': 'FINN', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-012', 'ADR-017']},
    'IoS-005': {'owner': 'FINN', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-012']},
    'IoS-007': {'owner': 'FINN', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-017', 'ADR-020']},
    'IoS-008': {'owner': 'LINE', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-012', 'ADR-016']},
    'IoS-009': {'owner': 'FINN', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-020']},
    'IoS-010': {'owner': 'FINN', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-017']},
    'IoS-011': {'owner': 'FINN', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-003']},
    'IoS-012': {'owner': 'LINE', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-012', 'ADR-016', 'ADR-017']},
    'IoS-013': {'owner': 'FINN', 'tier': 3, 'status': 'ACTIVE', 'governing_adrs': ['ADR-020']},
    'IoS-014': {'owner': 'STIG', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-007', 'ADR-014']},
    'IoS-015': {'owner': 'FINN', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-012', 'ADR-017', 'ADR-020']},
}

# EC metadata mapping (FROZEN for EC-018, EC-020, EC-021, EC-022)
EC_METADATA = {
    'EC-001': {'owner': 'VEGA', 'tier': 1, 'status': 'ACTIVE', 'governing_adrs': ['ADR-006']},
    'EC-002': {'owner': 'LARS', 'tier': 1, 'status': 'ACTIVE', 'governing_adrs': ['ADR-007']},
    'EC-003': {'owner': 'STIG', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-007']},
    'EC-004': {'owner': 'FINN', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-007']},
    'EC-005': {'owner': 'LINE', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-007']},
    'EC-006': {'owner': 'CSEO', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-007']},
    'EC-007': {'owner': 'CDMO', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-007']},
    'EC-008': {'owner': 'FRAMEWORK', 'tier': 2, 'status': 'FRAMEWORK_CHARTER', 'governing_adrs': ['ADR-007']},
    'EC-009': {'owner': 'CEIO', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-007']},
    'EC-010': {'owner': 'CFAO', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-007']},
    'EC-011': {'owner': 'CODE', 'tier': 3, 'status': 'ACTIVE', 'governing_adrs': ['ADR-007']},
    'EC-012': {'owner': 'RESERVED', 'tier': 3, 'status': 'RESERVED', 'governing_adrs': ['ADR-007']},
    'EC-013': {'owner': 'CRIO', 'tier': 2, 'status': 'ACTIVE', 'governing_adrs': ['ADR-007']},
    'EC-018': {'owner': 'CEIO', 'tier': 2, 'status': 'FROZEN', 'governing_adrs': ['ADR-020']},
    'EC-019': {'owner': 'CEO', 'tier': 1, 'status': 'ACTIVE', 'governing_adrs': ['ADR-007', 'ADR-019']},
    'EC-020': {'owner': 'FINN', 'tier': 2, 'status': 'FROZEN', 'governing_adrs': ['ADR-020']},
    'EC-021': {'owner': 'FINN', 'tier': 2, 'status': 'FROZEN', 'governing_adrs': ['ADR-020']},
    'EC-022': {'owner': 'FINN', 'tier': 2, 'status': 'FROZEN', 'governing_adrs': ['ADR-020']},
}

def compute_sha256(content: str) -> str:
    """Compute SHA-256 hash of content."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def normalize_unicode(content: str) -> str:
    """Normalize Unicode characters to WIN1252-compatible ASCII equivalents."""
    replacements = {
        '\u2192': '->',    # → rightward arrow
        '\u2190': '<-',    # ← leftward arrow
        '\u2194': '<->',   # ↔ bidirectional arrow
        '\u21d2': '=>',    # ⇒ double rightward arrow
        '\u21d0': '<=',    # ⇐ double leftward arrow
        '\u2265': '>=',    # ≥ greater than or equal
        '\u2264': '<=',    # ≤ less than or equal
        '\u2260': '!=',    # ≠ not equal
        '\u2022': '*',     # • bullet
        '\u2013': '-',     # – en dash
        '\u2014': '--',    # — em dash
        '\u2018': "'",     # ' left single quote
        '\u2019': "'",     # ' right single quote
        '\u201c': '"',     # " left double quote
        '\u201d': '"',     # " right double quote
        '\u2026': '...',   # … ellipsis
        '\u00d7': 'x',     # × multiplication
        '\u00f7': '/',     # ÷ division
        '\u221e': 'inf',   # ∞ infinity
        '\u2211': 'SUM',   # ∑ summation
        '\u220f': 'PROD',  # ∏ product
        '\u221a': 'sqrt',  # √ square root
        '\u2248': '~=',    # ≈ approximately equal
        '\u2261': '===',   # ≡ identical to
        '\u2282': 'subset',# ⊂ subset
        '\u2208': 'in',    # ∈ element of
        '\u2229': 'AND',   # ∩ intersection
        '\u222a': 'OR',    # ∪ union
        '\u00b2': '^2',    # ² superscript 2
        '\u00b3': '^3',    # ³ superscript 3
        '\u00b0': 'deg',   # ° degree
        '\u03b1': 'alpha', # α alpha
        '\u03b2': 'beta',  # β beta
        '\u03b3': 'gamma', # γ gamma
        '\u03b4': 'delta', # δ delta
        '\u03bc': 'mu',    # μ mu
        '\u03c3': 'sigma', # σ sigma
        '\u03c0': 'pi',    # π pi
        '\u2713': '[x]',   # ✓ check mark
        '\u2717': '[ ]',   # ✗ cross mark
        '\u2605': '*',     # ★ star
        '\u2606': '*',     # ☆ white star
        '\u25cf': 'o',     # ● black circle
        '\u25cb': 'o',     # ○ white circle
        '\u25a0': '#',     # ■ black square
        '\u25a1': '[]',    # □ white square
        '\u2502': '|',     # │ box drawing vertical
        '\u2500': '-',     # ─ box drawing horizontal
        '\u250c': '+',     # ┌ box corner
        '\u2510': '+',     # ┐ box corner
        '\u2514': '+',     # └ box corner
        '\u2518': '+',     # ┘ box corner
        '\u251c': '+',     # ├ box tee
        '\u2524': '+',     # ┤ box tee
        '\u252c': '+',     # ┬ box tee
        '\u2534': '+',     # ┴ box tee
        '\u253c': '+',     # ┼ box cross
    }

    result = content
    for unicode_char, ascii_equiv in replacements.items():
        result = result.replace(unicode_char, ascii_equiv)

    # Remove any remaining non-WIN1252 characters
    try:
        result.encode('cp1252')
    except UnicodeEncodeError:
        # Replace remaining problematic characters
        result = result.encode('cp1252', errors='replace').decode('cp1252')

    return result

def extract_adr_code(filename: str) -> str:
    """Extract ADR code from filename."""
    match = re.match(r'(ADR-\d+)', filename)
    return match.group(1) if match else None

def extract_ios_code(filename: str) -> str:
    """Extract IoS code from filename."""
    match = re.match(r'(IoS-\d+)', filename, re.IGNORECASE)
    return match.group(1) if match else None

def extract_ec_code(filename: str) -> str:
    """Extract EC code from filename."""
    match = re.match(r'(EC-\d+)', filename)
    return match.group(1) if match else None

def extract_title_from_content(content: str) -> str:
    """Extract title from document content (first # heading)."""
    lines = content.split('\n')
    for line in lines:
        if line.startswith('# '):
            return line[2:].strip()
    return None

def ingest_adrs(conn):
    """Ingest all ADR documents."""
    print("\n=== INGESTING ADRs ===")
    cursor = conn.cursor()

    ingested = 0
    files = [f for f in os.listdir(ADR_PATH) if f.endswith('.md') and f.startswith('ADR-')]

    for filename in files:
        doc_code = extract_adr_code(filename)
        if not doc_code:
            print(f"  SKIP: {filename} (no valid ADR code)")
            continue

        filepath = os.path.join(ADR_PATH, filename)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  ERROR reading {filename}: {e}")
            continue

        # Hash original content, but normalize for storage
        content_hash = compute_sha256(content)
        normalized_content = normalize_unicode(content)

        # Get metadata or use defaults
        meta = ADR_METADATA.get(doc_code, {
            'owner': 'SYSTEM',
            'tier': 3,
            'status': 'ACTIVE',
            'title': extract_title_from_content(content) or filename
        })

        title = normalize_unicode(meta.get('title') or extract_title_from_content(content) or doc_code)

        try:
            cursor.execute("""
                INSERT INTO fhq_meta.canonical_documents (
                    document_type, document_code, title, version, status, tier, owner,
                    content_hash, content_text, source_path, source, ingestion_directive
                ) VALUES (
                    'ADR', %s, %s, '2026.PRODUCTION', %s, %s, %s,
                    %s, %s, %s, 'CANONICAL_DOCUMENT', 'CEO-DIR-2025-INGEST-001'
                )
                ON CONFLICT (document_code) DO UPDATE SET
                    content_hash = EXCLUDED.content_hash,
                    content_text = EXCLUDED.content_text,
                    updated_at = NOW()
            """, (
                doc_code,
                title,
                meta['status'],
                meta['tier'],
                meta['owner'],
                content_hash,
                normalized_content,
                filepath
            ))
            conn.commit()  # Commit each successful insert
            ingested += 1
            print(f"  OK: {doc_code} - {title[:50]}...")
        except Exception as e:
            conn.rollback()  # Rollback failed transaction
            print(f"  ERROR inserting {doc_code}: {e}")

    print(f"\n  TOTAL ADRs INGESTED: {ingested}")
    return ingested

def ingest_ioss(conn):
    """Ingest all IoS documents (handling duplicates)."""
    print("\n=== INGESTING IoSs ===")
    cursor = conn.cursor()

    # Preferred files per IoS code (avoid duplicates)
    preferred_files = {
        'IoS-001': 'IoS-001_2026_PRODUCTION.md',
        'IoS-002': 'IoS-002.md',
        'IoS-003': 'IoS-003.v4_2026_PRODUCTION.md',
        'IoS-004': 'IoS-004 – Regime-Driven Allocation Engine.md',
        'IoS-005': 'IoS-005_Forecast Calibration and Skill Engine.md',
        'IoS-007': 'IoS-007_ALPHA GRAPH ENGINE - CAUSAL REASONING CORE.md',
        'IoS-008': 'IoS-008_Runtime Decision Engine.md',
        'IoS-009': 'IoS-009 — Meta-Perception Layer.md',
        'IoS-010': 'IoS-010_PREDICTION LEDGER ENGINE.md',
        'IoS-011': 'IoS-011_TECHNICAL ANALYSIS PIPELINE.md',
        'IoS-012': 'IoS-012_EXECUTION ENGINE.md',
        'IoS-013': 'IoS-013.HCP-LAB.md',
        'IoS-014': 'IoS-014_Autonomous Task Orchestration Engine.md',
        'IoS-015': 'IoS-015_Multi-Strategy, Cognitive Trading Infrastructure.md',
    }

    ingested = 0

    for doc_code, filename in preferred_files.items():
        filepath = os.path.join(IOS_PATH, filename)

        if not os.path.exists(filepath):
            print(f"  SKIP: {filename} (file not found)")
            continue

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  ERROR reading {filename}: {e}")
            continue

        # Hash original content, but normalize for storage
        content_hash = compute_sha256(content)
        normalized_content = normalize_unicode(content)

        meta = IOS_METADATA.get(doc_code, {
            'owner': 'SYSTEM',
            'tier': 2,
            'status': 'ACTIVE',
            'governing_adrs': []
        })

        title = normalize_unicode(extract_title_from_content(content) or doc_code)

        try:
            cursor.execute("""
                INSERT INTO fhq_meta.canonical_documents (
                    document_type, document_code, title, version, status, tier, owner,
                    content_hash, content_text, source_path, source, ingestion_directive,
                    governing_adrs
                ) VALUES (
                    'IoS', %s, %s, '2026.PRODUCTION', %s, %s, %s,
                    %s, %s, %s, 'CANONICAL_DOCUMENT', 'CEO-DIR-2025-INGEST-001',
                    %s
                )
                ON CONFLICT (document_code) DO UPDATE SET
                    content_hash = EXCLUDED.content_hash,
                    content_text = EXCLUDED.content_text,
                    governing_adrs = EXCLUDED.governing_adrs,
                    updated_at = NOW()
            """, (
                doc_code,
                title[:200],  # Truncate long titles
                meta['status'],
                meta['tier'],
                meta['owner'],
                content_hash,
                normalized_content,
                filepath,
                meta.get('governing_adrs', [])
            ))
            conn.commit()  # Commit each successful insert
            ingested += 1
            print(f"  OK: {doc_code} - {title[:50]}...")
        except Exception as e:
            conn.rollback()  # Rollback failed transaction
            print(f"  ERROR inserting {doc_code}: {e}")

    print(f"\n  TOTAL IoSs INGESTED: {ingested}")
    return ingested

def ingest_ecs(conn):
    """Ingest all EC documents."""
    print("\n=== INGESTING ECs ===")
    cursor = conn.cursor()

    ingested = 0
    files = [f for f in os.listdir(EC_PATH) if f.endswith('.md') and f.startswith('EC-')]

    for filename in files:
        doc_code = extract_ec_code(filename)
        if not doc_code:
            print(f"  SKIP: {filename} (no valid EC code)")
            continue

        filepath = os.path.join(EC_PATH, filename)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  ERROR reading {filename}: {e}")
            continue

        # Hash original content, but normalize for storage
        content_hash = compute_sha256(content)
        normalized_content = normalize_unicode(content)

        meta = EC_METADATA.get(doc_code, {
            'owner': 'SYSTEM',
            'tier': 3,
            'status': 'ACTIVE',
            'governing_adrs': ['ADR-007']
        })

        title = normalize_unicode(extract_title_from_content(content) or doc_code)

        try:
            cursor.execute("""
                INSERT INTO fhq_meta.canonical_documents (
                    document_type, document_code, title, version, status, tier, owner,
                    content_hash, content_text, source_path, source, ingestion_directive,
                    governing_adrs
                ) VALUES (
                    'EC', %s, %s, '2026.PRODUCTION', %s, %s, %s,
                    %s, %s, %s, 'CANONICAL_DOCUMENT', 'CEO-DIR-2025-INGEST-001',
                    %s
                )
                ON CONFLICT (document_code) DO UPDATE SET
                    content_hash = EXCLUDED.content_hash,
                    content_text = EXCLUDED.content_text,
                    governing_adrs = EXCLUDED.governing_adrs,
                    status = EXCLUDED.status,
                    updated_at = NOW()
            """, (
                doc_code,
                title[:200],
                meta['status'],
                meta['tier'],
                meta['owner'],
                content_hash,
                normalized_content,
                filepath,
                meta.get('governing_adrs', [])
            ))
            conn.commit()  # Commit each successful insert
            ingested += 1
            print(f"  OK: {doc_code} ({meta['status']}) - {title[:40]}...")
        except Exception as e:
            conn.rollback()  # Rollback failed transaction
            print(f"  ERROR inserting {doc_code}: {e}")

    print(f"\n  TOTAL ECs INGESTED: {ingested}")
    return ingested

def verify_counts(conn):
    """Verify final document counts."""
    print("\n=== VERIFICATION ===")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT document_type, COUNT(*) as count
        FROM fhq_meta.canonical_documents
        GROUP BY document_type
        ORDER BY document_type
    """)

    results = cursor.fetchall()
    total = 0
    for doc_type, count in results:
        print(f"  {doc_type}: {count}")
        total += count

    print(f"\n  TOTAL: {total}")

    # Check for FROZEN status
    cursor.execute("""
        SELECT document_code, status
        FROM fhq_meta.canonical_documents
        WHERE status = 'FROZEN'
        ORDER BY document_code
    """)

    frozen = cursor.fetchall()
    if frozen:
        print(f"\n  FROZEN DOCUMENTS ({len(frozen)}):")
        for code, status in frozen:
            print(f"    - {code}")

    return total

def main():
    """Main ingestion function."""
    print("=" * 60)
    print("CEO-DIR-2025-INGEST-001: CANONICAL DOCUMENT INGESTION")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Executor: STIG")
    print()
    print("FORBEHOLD 1: Layer 8 Observability, NOT Layer 1 Constitutional")
    print("FORBEHOLD 2: One-way authority (Files -> canonical -> registries)")
    print("FORBEHOLD 3: Ingestion = readability only, NOT activation")
    print("=" * 60)

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_client_encoding('UTF8')
        print("\nDatabase connected (UTF-8 encoding).")

        adr_count = ingest_adrs(conn)
        ios_count = ingest_ioss(conn)
        ec_count = ingest_ecs(conn)

        total = verify_counts(conn)

        print("\n" + "=" * 60)
        print("INGESTION SUMMARY")
        print("=" * 60)
        print(f"  ADRs ingested: {adr_count}")
        print(f"  IoSs ingested: {ios_count}")
        print(f"  ECs ingested:  {ec_count}")
        print(f"  ---")
        print(f"  TOTAL:         {total}")
        print()

        if total >= 50:  # Target was 54
            print("  STATUS: INGESTION COMPLETE")
        else:
            print(f"  STATUS: PARTIAL (expected ~54, got {total})")

        conn.close()

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        raise

if __name__ == '__main__':
    main()
