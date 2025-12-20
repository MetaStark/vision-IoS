#!/usr/bin/env python3
"""
IoS-001 COLAB BACKFILL V2 - Korrekt Schema
==========================================
Matcher faktisk fhq_data.price_series schema.

UNIQUE CONSTRAINT: (listing_id, date, resolution)

Kolonnner:
- listing_id (text) - canonical_id fra fhq_meta.assets
- date (timestamptz) - dato
- open, high, low, close, adj_close (numeric)
- volume (bigint)
- price_type (enum: RAW, ADJUSTED, etc.)
- resolution (enum: 1d, 1h, etc.)
- data_source (text)
- adr_epoch (text)

Authority: STIG (CTO)
"""

# =============================================================================
# COLAB SETUP CELLE
# =============================================================================
SETUP_CELL = """
# Celle 1: Setup
!pip install yfinance pandas tqdm psycopg2-binary -q

from google.colab import drive
drive.mount('/content/drive')

!mkdir -p "/content/drive/MyDrive/FjordHQ/ios001_backfill/data"
"""

import os
import json
import time
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Dict, Optional

try:
    import pandas as pd
    import yfinance as yf
    from tqdm import tqdm
except ImportError:
    print("Kjør: pip install yfinance pandas tqdm")

# =============================================================================
# KONFIGURASJON
# =============================================================================

# Checkpoint
CHECKPOINT_DIR = "/content/drive/MyDrive/FjordHQ/ios001_backfill"

# Rate Limits (Colab)
BATCH_SIZE = 5
DELAY_BETWEEN_ASSETS = 8.0
DELAY_BETWEEN_BATCHES = 180.0
MAX_RETRIES = 5
RETRY_BASE_DELAY = 30.0
RATE_LIMIT_BACKOFF = 600.0

# Historie
MAX_HISTORY_YEARS = 10

# Iron Curtain (IoS-001 §4.1)
EQUITY_FX_QUARANTINE = 252
EQUITY_FX_FULL_HISTORY = 1260
CRYPTO_QUARANTINE = 365
CRYPTO_FULL_HISTORY = 1825

# =============================================================================
# QUARANTINED ASSETS FRA DATABASE (45 stk)
# =============================================================================

QUARANTINED_ASSETS = {
    # ARCX ETFs (15)
    "DIA": {"exchange": "ARCX", "yf_ticker": "DIA"},
    "IWM": {"exchange": "ARCX", "yf_ticker": "IWM"},
    "VOO": {"exchange": "ARCX", "yf_ticker": "VOO"},
    "VTI": {"exchange": "ARCX", "yf_ticker": "VTI"},
    "XLB": {"exchange": "ARCX", "yf_ticker": "XLB"},
    "XLC": {"exchange": "ARCX", "yf_ticker": "XLC"},
    "XLE": {"exchange": "ARCX", "yf_ticker": "XLE"},
    "XLF": {"exchange": "ARCX", "yf_ticker": "XLF"},
    "XLI": {"exchange": "ARCX", "yf_ticker": "XLI"},
    "XLK": {"exchange": "ARCX", "yf_ticker": "XLK"},
    "XLP": {"exchange": "ARCX", "yf_ticker": "XLP"},
    "XLRE": {"exchange": "ARCX", "yf_ticker": "XLRE"},
    "XLU": {"exchange": "ARCX", "yf_ticker": "XLU"},
    "XLV": {"exchange": "ARCX", "yf_ticker": "XLV"},
    "XLY": {"exchange": "ARCX", "yf_ticker": "XLY"},

    # XNAS (9)
    "AMZN": {"exchange": "XNAS", "yf_ticker": "AMZN"},
    "ANSS": {"exchange": "XNAS", "yf_ticker": "ANSS"},
    "ASML": {"exchange": "XNAS", "yf_ticker": "ASML"},
    "GOOG": {"exchange": "XNAS", "yf_ticker": "GOOG"},
    "GOOGL": {"exchange": "XNAS", "yf_ticker": "GOOGL"},
    "META": {"exchange": "XNAS", "yf_ticker": "META"},
    "PARA": {"exchange": "XNAS", "yf_ticker": "PARA"},
    "SPLK": {"exchange": "XNAS", "yf_ticker": "SPLK"},
    "TSLA": {"exchange": "XNAS", "yf_ticker": "TSLA"},

    # XNYS (7)
    "BRK.B": {"exchange": "XNYS", "yf_ticker": "BRK-B"},
    "HES": {"exchange": "XNYS", "yf_ticker": "HES"},
    "JNJ": {"exchange": "XNYS", "yf_ticker": "JNJ"},
    "MA": {"exchange": "XNYS", "yf_ticker": "MA"},
    "SQ": {"exchange": "XNYS", "yf_ticker": "SQ"},
    "UNH": {"exchange": "XNYS", "yf_ticker": "UNH"},
    "V": {"exchange": "XNYS", "yf_ticker": "V"},

    # XOSL (12)
    "BELCO.OL": {"exchange": "XOSL", "yf_ticker": "BELCO.OL"},
    "CRAYN.OL": {"exchange": "XOSL", "yf_ticker": "CRAYN.OL"},
    "FLNG.OL": {"exchange": "XOSL", "yf_ticker": "FLNG.OL"},
    "GJFAH.OL": {"exchange": "XOSL", "yf_ticker": "GJFAH.OL"},
    "GOGL.OL": {"exchange": "XOSL", "yf_ticker": "GOGL.OL"},
    "KAHOT.OL": {"exchange": "XOSL", "yf_ticker": "KAHOT.OL"},
    "PROTCT.OL": {"exchange": "XOSL", "yf_ticker": "PROTCT.OL"},
    "REC.OL": {"exchange": "XOSL", "yf_ticker": "REC.OL"},
    "SCHA.OL": {"exchange": "XOSL", "yf_ticker": "SCHA.OL"},
    "SCHB.OL": {"exchange": "XOSL", "yf_ticker": "SCHB.OL"},
    "SRBNK.OL": {"exchange": "XOSL", "yf_ticker": "SRBNK.OL"},
    "XXL.OL": {"exchange": "XOSL", "yf_ticker": "XXL.OL"},

    # XLON (1)
    "BT.A.L": {"exchange": "XLON", "yf_ticker": "BT-A.L"},

    # XPAR (1)
    "STM.PA": {"exchange": "XPAR", "yf_ticker": "STM.PA"},
}

# =============================================================================
# CHECKPOINT
# =============================================================================

def load_checkpoint():
    checkpoint_file = Path(CHECKPOINT_DIR) / "checkpoint_v2.json"
    if checkpoint_file.exists():
        with open(checkpoint_file, 'r') as f:
            return json.load(f)
    return {"completed": [], "failed": [], "last_update": None}

def save_checkpoint(checkpoint):
    checkpoint["last_update"] = datetime.now().isoformat()
    checkpoint_file = Path(CHECKPOINT_DIR) / "checkpoint_v2.json"
    with open(checkpoint_file, 'w') as f:
        json.dump(checkpoint, f, indent=2)

def save_csv(canonical_id: str, df: pd.DataFrame) -> Path:
    """Lagre data til CSV med korrekt format for import"""
    data_dir = Path(CHECKPOINT_DIR) / "data"
    data_dir.mkdir(exist_ok=True)

    # Preparer data for import
    export_df = pd.DataFrame({
        'listing_id': canonical_id,
        'date': df.index,
        'open': df['Open'],
        'high': df['High'],
        'low': df['Low'],
        'close': df['Close'],
        'adj_close': df.get('Adj Close', df['Close']),
        'volume': df['Volume'].astype('Int64'),
        'price_type': 'RAW',
        'resolution': '1d',
        'data_source': 'yfinance_colab',
        'adr_epoch': 'COLAB_2024'
    })

    filepath = data_dir / f"{canonical_id.replace('.', '_')}.csv"
    export_df.to_csv(filepath, index=False)
    return filepath

# =============================================================================
# FETCH
# =============================================================================

def fetch_with_backoff(yf_ticker: str, start_date: date, end_date: date) -> Optional[pd.DataFrame]:
    """Fetch med eksponentiell backoff"""
    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(f"  Retry {attempt + 1}/{MAX_RETRIES}, venter {delay:.0f}s...")
                time.sleep(delay)

            df = yf.download(
                yf_ticker,
                start=start_date.strftime('%Y-%m-%d'),
                end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                interval='1d',
                auto_adjust=False,
                progress=False,
                threads=False
            )

            if df is None or df.empty:
                continue

            df = df.dropna(subset=['Close'])
            if not df.empty:
                return df

        except Exception as e:
            error_str = str(e).lower()
            if any(x in error_str for x in ["rate limit", "429", "too many"]):
                print(f"  RATE LIMITED! Venter {RATE_LIMIT_BACKOFF}s...")
                time.sleep(RATE_LIMIT_BACKOFF)
            else:
                print(f"  Feil: {e}")

    return None

# =============================================================================
# HOVEDFUNKSJON
# =============================================================================

def run_quarantined_backfill(resume: bool = True):
    """Backfill kun QUARANTINED assets"""
    checkpoint = load_checkpoint() if resume else {"completed": [], "failed": [], "last_update": None}

    # Filtrer ut allerede prosesserte
    pending = [cid for cid in QUARANTINED_ASSETS.keys()
               if cid not in checkpoint["completed"]]

    print("=" * 60)
    print("IoS-001 QUARANTINED BACKFILL")
    print("=" * 60)
    print(f"Total QUARANTINED: {len(QUARANTINED_ASSETS)}")
    print(f"Allerede fullført: {len(checkpoint['completed'])}")
    print(f"Gjenstår: {len(pending)}")
    print("=" * 60)

    if not pending:
        print("Alle QUARANTINED assets er prosessert!")
        return

    end_date = date.today() - timedelta(days=1)
    start_date = date.today() - timedelta(days=MAX_HISTORY_YEARS * 365)

    results = {"processed": 0, "success": 0, "failed": 0, "total_rows": 0}
    batch_count = 0

    for i, canonical_id in enumerate(tqdm(pending, desc="Backfill")):
        asset_info = QUARANTINED_ASSETS[canonical_id]
        yf_ticker = asset_info["yf_ticker"]

        results["processed"] += 1
        print(f"\n[{i+1}/{len(pending)}] {canonical_id} ({yf_ticker})...")

        try:
            df = fetch_with_backoff(yf_ticker, start_date, end_date)

            if df is None or df.empty:
                print(f"  FEILET: Ingen data")
                results["failed"] += 1
                if canonical_id not in checkpoint["failed"]:
                    checkpoint["failed"].append(canonical_id)
            else:
                csv_path = save_csv(canonical_id, df)
                rows = len(df)
                results["total_rows"] += rows

                # Iron Curtain status
                if rows < EQUITY_FX_QUARANTINE:
                    status = "QUARANTINED"
                elif rows < EQUITY_FX_FULL_HISTORY:
                    status = "SHORT_HISTORY"
                else:
                    status = "FULL_HISTORY"

                print(f"  OK: {rows} rader, {status} -> {csv_path.name}")
                results["success"] += 1

                if canonical_id not in checkpoint["completed"]:
                    checkpoint["completed"].append(canonical_id)
                if canonical_id in checkpoint["failed"]:
                    checkpoint["failed"].remove(canonical_id)

            save_checkpoint(checkpoint)

        except KeyboardInterrupt:
            print("\n\nAvbrutt! Checkpoint lagret.")
            save_checkpoint(checkpoint)
            return results
        except Exception as e:
            print(f"  ERROR: {e}")
            results["failed"] += 1

        # Rate limiting
        batch_count += 1
        time.sleep(DELAY_BETWEEN_ASSETS)

        if batch_count >= BATCH_SIZE:
            batch_count = 0
            print(f"\nBatch pause: {DELAY_BETWEEN_BATCHES}s...")
            time.sleep(DELAY_BETWEEN_BATCHES)

    # Oppsummering
    print("\n" + "=" * 60)
    print("FULLFØRT")
    print("=" * 60)
    print(f"Prosessert: {results['processed']}")
    print(f"Suksess: {results['success']}")
    print(f"Feilet: {results['failed']}")
    print(f"Totalt rader: {results['total_rows']}")

    return results

# =============================================================================
# IMPORT SCRIPT GENERATOR
# =============================================================================

def generate_import_script():
    """Generer Python script for import til lokal database"""

    script = '''#!/usr/bin/env python3
"""
IoS-001 IMPORT SCRIPT - Matcher fhq_data.price_series schema
Generert: {timestamp}

UNIQUE CONSTRAINT: (listing_id, date, resolution)
"""
import pandas as pd
import psycopg2
from pathlib import Path

DB_CONFIG = {{
    "host": "127.0.0.1",
    "port": "54322",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres"
}}

DATA_DIR = Path("./ios001_data")  # Kopier CSV-filer hit

def import_csv(conn, filepath):
    """Import en CSV til database"""
    df = pd.read_csv(filepath)

    insert_sql = """
        INSERT INTO fhq_data.price_series (
            listing_id, date, open, high, low, close, adj_close,
            volume, price_type, resolution, data_source, adr_epoch
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::price_type, %s::resolution, %s, %s)
        ON CONFLICT (listing_id, date, resolution) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            adj_close = EXCLUDED.adj_close,
            volume = EXCLUDED.volume,
            data_source = EXCLUDED.data_source
    """

    inserted = 0
    with conn.cursor() as cur:
        for _, row in df.iterrows():
            try:
                cur.execute(insert_sql, (
                    row['listing_id'],
                    row['date'],
                    row['open'] if pd.notna(row['open']) else None,
                    row['high'] if pd.notna(row['high']) else None,
                    row['low'] if pd.notna(row['low']) else None,
                    row['close'] if pd.notna(row['close']) else None,
                    row['adj_close'] if pd.notna(row['adj_close']) else None,
                    int(row['volume']) if pd.notna(row['volume']) else None,
                    row['price_type'],
                    row['resolution'],
                    row['data_source'],
                    row['adr_epoch']
                ))
                inserted += 1
            except Exception as e:
                print(f"  Row error: {{e}}")
        conn.commit()

    return inserted

def update_asset_status(conn, canonical_id: str):
    """Oppdater valid_row_count og data_quality_status"""
    with conn.cursor() as cur:
        # Tell rader
        cur.execute("""
            SELECT COUNT(*) FROM fhq_data.price_series
            WHERE listing_id = %s AND close IS NOT NULL
        """, (canonical_id,))
        count = cur.fetchone()[0]

        # Bestem status (IoS-001 Iron Curtain)
        if count < 252:
            status = 'QUARANTINED'
        elif count < 1260:
            status = 'SHORT_HISTORY'
        else:
            status = 'FULL_HISTORY'

        # Oppdater
        cur.execute("""
            UPDATE fhq_meta.assets
            SET valid_row_count = %s,
                data_quality_status = %s::data_quality_status
            WHERE canonical_id = %s
        """, (count, status, canonical_id))
        conn.commit()

    return count, status

if __name__ == "__main__":
    conn = psycopg2.connect(**DB_CONFIG)
    csv_files = list(DATA_DIR.glob("*.csv"))

    print(f"Importerer {{len(csv_files)}} filer...")
    print("=" * 50)

    total_rows = 0
    for f in csv_files:
        canonical_id = f.stem.replace("_", ".")
        try:
            rows = import_csv(conn, f)
            count, status = update_asset_status(conn, canonical_id)
            total_rows += rows
            print(f"{{canonical_id}}: {{rows}} rader -> {{status}} ({{count}} total)")
        except Exception as e:
            print(f"{{canonical_id}}: FEIL - {{e}}")

    conn.close()
    print("=" * 50)
    print(f"Totalt: {{total_rows}} rader importert")
'''.format(timestamp=datetime.now().isoformat())

    script_path = Path(CHECKPOINT_DIR) / "import_to_db_v2.py"
    with open(script_path, 'w') as f:
        f.write(script)

    print(f"Import script: {script_path}")
    return script_path

# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--generate-import", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        print(f"QUARANTINED assets ({len(QUARANTINED_ASSETS)}):")
        for cid, info in QUARANTINED_ASSETS.items():
            print(f"  {cid} -> {info['yf_ticker']} ({info['exchange']})")
    elif args.generate_import:
        generate_import_script()
    else:
        run_quarantined_backfill(resume=not args.no_resume)
