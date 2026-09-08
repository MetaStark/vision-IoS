#!/usr/bin/env python3
"""
CEIO Backfill: Simple version using yf.download() with better rate limit handling
CEO-DIR-2026-030 Phase 1 P0 Action
"""

import os
import json
import hashlib
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from uuid import uuid4
import time

try:
    import yfinance as yf
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'yfinance', '-q'])
    import yfinance as yf

DIRECTIVE_ID = "CEO-DIR-2026-030"
BACKFILL_START = "2025-12-01"
BACKFILL_END = "2026-01-10"

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=os.environ.get('PGPORT', '54322'),
        database=os.environ.get('PGDATABASE', 'postgres'),
        user=os.environ.get('PGUSER', 'postgres'),
        password=os.environ.get('PGPASSWORD', 'postgres')
    )

def fetch_and_insert(conn, ticker, batch_id):
    """Fetch prices using yf.download and insert into database."""
    print(f"\nProcessing {ticker}...")

    # Use yf.download which is more robust
    try:
        df = yf.download(ticker, start=BACKFILL_START, end=BACKFILL_END, progress=False)
    except Exception as e:
        print(f"  [!] Error downloading {ticker}: {e}")
        return 0

    if df.empty:
        print(f"  [!] No data for {ticker}")
        return 0

    print(f"  [OK] Downloaded {len(df)} rows")

    cursor = conn.cursor()

    # Check existing
    cursor.execute("""
        SELECT timestamp::date FROM fhq_market.prices WHERE canonical_id = %s
    """, (ticker,))
    existing = set(row[0] for row in cursor.fetchall())

    # Generate asset_id for this ticker
    asset_id = str(uuid4())

    records = []
    for idx, row in df.iterrows():
        price_date = idx.to_pydatetime().replace(tzinfo=None)
        if price_date.date() in existing:
            continue

        data_hash = hashlib.sha256(f"{ticker}|{price_date}|{row['Close']}".encode()).hexdigest()[:32]

        records.append((
            str(uuid4()), asset_id, ticker, price_date,
            float(row['Open']), float(row['High']), float(row['Low']), float(row['Close']),
            float(row['Volume']), 'yfinance', None, data_hash,
            False, False, 1.0, batch_id, datetime.now(), 'CEIO',
            False, None, None, float(row['Close']), 'yfinance', 'PRIMARY', 'EOD'
        ))

    if not records:
        print(f"  [=] All prices exist for {ticker}")
        cursor.close()
        return 0

    execute_values(cursor, """
        INSERT INTO fhq_market.prices (
            id, asset_id, canonical_id, timestamp, open, high, low, close, volume,
            source, staging_id, data_hash, gap_filled, interpolated, quality_score,
            batch_id, canonicalized_at, canonicalized_by, vega_reconciled,
            vega_reconciled_at, vega_attestation_id, adj_close, vendor_id,
            vendor_role, price_class
        ) VALUES %s ON CONFLICT DO NOTHING
    """, records)

    inserted = cursor.rowcount
    conn.commit()
    cursor.close()

    print(f"  [OK] Inserted {inserted} prices for {ticker}")
    return inserted

def main():
    print("=" * 60)
    print("CEIO BACKFILL (Simple) - GLD & TLT")
    print(f"Waiting 60s for rate limit to clear...")
    print("=" * 60)

    # Wait for rate limit to clear
    time.sleep(60)

    conn = get_db_connection()
    batch_id = uuid4()

    # Download both at once (more efficient)
    print("\nDownloading GLD and TLT together...")
    try:
        df = yf.download(['GLD', 'TLT'], start=BACKFILL_START, end=BACKFILL_END, progress=True, group_by='ticker')

        gld_count = 0
        tlt_count = 0

        if 'GLD' in df.columns.get_level_values(0):
            gld_df = df['GLD'].dropna()
            gld_count = insert_from_df(conn, 'GLD', gld_df, batch_id)

        if 'TLT' in df.columns.get_level_values(0):
            tlt_df = df['TLT'].dropna()
            tlt_count = insert_from_df(conn, 'TLT', tlt_df, batch_id)

    except Exception as e:
        print(f"Batch download failed: {e}")
        print("Trying individual downloads with delay...")

        gld_count = fetch_and_insert(conn, 'GLD', batch_id)
        time.sleep(10)
        tlt_count = fetch_and_insert(conn, 'TLT', batch_id)

    # Log to governance
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO fhq_governance.governance_actions_log (
            action_id, action_type, action_target, action_target_type,
            initiated_by, initiated_at, decision, decision_rationale,
            metadata, agent_id, timestamp
        ) VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, NOW())
    """, (
        str(uuid4()),
        'CEIO_PRICE_BACKFILL_COMPLETE',
        'GLD,TLT',
        'ASSET_PRICES',
        'CEIO',
        'EXECUTED',
        f'Backfilled GLD ({gld_count}) and TLT ({tlt_count}) prices for Phase 1 coverage improvement',
        json.dumps({'gld': gld_count, 'tlt': tlt_count, 'batch_id': str(batch_id)}),
        'CEIO'
    ))
    conn.commit()
    cursor.close()

    conn.close()

    print("\n" + "=" * 60)
    print(f"COMPLETE: GLD={gld_count}, TLT={tlt_count}")
    print("=" * 60)

    return 0

def insert_from_df(conn, ticker, df, batch_id):
    """Insert prices from dataframe."""
    cursor = conn.cursor()

    cursor.execute("SELECT timestamp::date FROM fhq_market.prices WHERE canonical_id = %s", (ticker,))
    existing = set(row[0] for row in cursor.fetchall())

    asset_id = str(uuid4())
    records = []

    for idx, row in df.iterrows():
        price_date = idx.to_pydatetime().replace(tzinfo=None)
        if price_date.date() in existing:
            continue

        data_hash = hashlib.sha256(f"{ticker}|{price_date}|{row['Close']}".encode()).hexdigest()[:32]

        records.append((
            str(uuid4()), asset_id, ticker, price_date,
            float(row['Open']), float(row['High']), float(row['Low']), float(row['Close']),
            float(row['Volume']), 'yfinance', None, data_hash,
            False, False, 1.0, batch_id, datetime.now(), 'CEIO',
            False, None, None, float(row['Close']), 'yfinance', 'PRIMARY', 'EOD'
        ))

    if records:
        execute_values(cursor, """
            INSERT INTO fhq_market.prices (
                id, asset_id, canonical_id, timestamp, open, high, low, close, volume,
                source, staging_id, data_hash, gap_filled, interpolated, quality_score,
                batch_id, canonicalized_at, canonicalized_by, vega_reconciled,
                vega_reconciled_at, vega_attestation_id, adj_close, vendor_id,
                vendor_role, price_class
            ) VALUES %s ON CONFLICT DO NOTHING
        """, records)
        conn.commit()

    cursor.close()
    print(f"  [OK] Inserted {len(records)} prices for {ticker}")
    return len(records)

if __name__ == "__main__":
    import sys
    sys.exit(main())
