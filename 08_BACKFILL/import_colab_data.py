"""
IoS-001 Colab Data Importer
Imports CSV files from Colab backfill into fhq_data.price_series
"""
import os
import glob
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

# Database connection
DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": os.getenv("PGPORT", "54322"),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres")
}

CSV_DIR = os.path.join(os.path.dirname(__file__), "ios001_extracted")

def import_csv(conn, csv_path):
    """Import a single CSV file into price_series."""
    filename = os.path.basename(csv_path)

    # Read CSV
    df = pd.read_csv(csv_path)

    if df.empty:
        return 0, "empty"

    # Parse dates - convert to UTC then remove timezone
    df['date'] = pd.to_datetime(df['date'], utc=True).dt.tz_localize(None)

    # Prepare data tuples
    rows = []
    for _, row in df.iterrows():
        rows.append((
            row['listing_id'],
            row['date'].to_pydatetime(),
            float(row['open']) if pd.notna(row['open']) else None,
            float(row['high']) if pd.notna(row['high']) else None,
            float(row['low']) if pd.notna(row['low']) else None,
            float(row['close']) if pd.notna(row['close']) else None,
            float(row['adj_close']) if pd.notna(row['adj_close']) else None,
            int(row['volume']) if pd.notna(row['volume']) else None,
            row['price_type'],
            row['resolution'],
            row['data_source'],
            row['adr_epoch']
        ))

    # Upsert with ON CONFLICT
    sql = """
        INSERT INTO fhq_data.price_series
            (listing_id, date, open, high, low, close, adj_close, volume,
             price_type, resolution, data_source, adr_epoch)
        VALUES %s
        ON CONFLICT (listing_id, date, resolution)
        DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            adj_close = EXCLUDED.adj_close,
            volume = EXCLUDED.volume,
            data_source = EXCLUDED.data_source,
            adr_epoch = EXCLUDED.adr_epoch
    """

    with conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=500)

    conn.commit()
    return len(rows), "ok"

def update_asset_status(conn, listing_id, row_count):
    """Update asset status in fhq_meta.assets."""
    # Determine status based on row count (IoS-001 Iron Curtain thresholds)
    if row_count >= 1260:
        status = 'FULL_HISTORY'
    elif row_count >= 252:
        status = 'SHORT_HISTORY'
    else:
        status = 'QUARANTINED'

    sql = """
        UPDATE fhq_meta.assets
        SET valid_row_count = %s,
            data_quality_status = %s,
            updated_at = NOW()
        WHERE canonical_id = %s
    """

    with conn.cursor() as cur:
        cur.execute(sql, (row_count, status, listing_id))
    conn.commit()
    return status

def main():
    print("=" * 60)
    print("IoS-001 Colab Data Importer")
    print("=" * 60)

    # Find all CSV files
    csv_files = glob.glob(os.path.join(CSV_DIR, "*.csv"))
    print(f"Found {len(csv_files)} CSV files in {CSV_DIR}")

    if not csv_files:
        print("ERROR: No CSV files found!")
        return

    # Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    print(f"Connected to {DB_CONFIG['host']}:{DB_CONFIG['port']}")

    results = {"ok": [], "fail": []}
    total_rows = 0

    for i, csv_path in enumerate(sorted(csv_files)):
        filename = os.path.basename(csv_path)
        # Convert filename back to listing_id (e.g., BRK_B.csv -> BRK.B)
        listing_id = filename.replace(".csv", "").replace("_", ".")

        print(f"[{i+1}/{len(csv_files)}] {listing_id}...", end=" ")

        try:
            row_count, status = import_csv(conn, csv_path)

            if status == "ok" and row_count > 0:
                # Update asset status
                new_status = update_asset_status(conn, listing_id, row_count)
                print(f"OK ({row_count} rows -> {new_status})")
                results["ok"].append(listing_id)
                total_rows += row_count
            else:
                print(f"EMPTY")
                results["fail"].append(listing_id)

        except Exception as e:
            print(f"ERROR: {e}")
            results["fail"].append(listing_id)
            conn.rollback()

    conn.close()

    print()
    print("=" * 60)
    print(f"COMPLETE: {len(results['ok'])} OK, {len(results['fail'])} failed")
    print(f"Total rows imported: {total_rows:,}")
    print("=" * 60)

    if results["fail"]:
        print("\nFailed assets:")
        for a in results["fail"]:
            print(f"  - {a}")

if __name__ == "__main__":
    main()
