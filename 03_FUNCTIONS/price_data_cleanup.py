#!/usr/bin/env python3
"""
Price Data Cleanup - Per CD-IOS-001-PRICE-ARCH-001
===================================================
Removes duplicate/invalid price records and normalizes data.
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

def main():
    print("=" * 60)
    print("PRICE DATA CLEANUP - CD-IOS-001-PRICE-ARCH-001")
    print("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)

    # Step 1: Delete websocket intraday data (P2 class in P1 table)
    print("\n[STEP 1] Removing alpaca_websocket intraday data...")
    with conn.cursor() as cur:
        cur.execute("DELETE FROM fhq_market.prices WHERE source = 'alpaca_websocket'")
        deleted = cur.rowcount
        print(f"  Deleted {deleted} websocket records")
    conn.commit()

    # Step 2: Show remaining duplicates per (canonical_id, date)
    print("\n[STEP 2] Checking remaining duplicates...")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT canonical_id, timestamp::date as date, COUNT(*) as cnt
            FROM fhq_market.prices
            WHERE timestamp > NOW() - INTERVAL '30 days'
            GROUP BY canonical_id, timestamp::date
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
            LIMIT 10
        """)
        dups = cur.fetchall()
        if dups:
            print(f"  Found {len(dups)} date/symbol combinations with duplicates:")
            for row in dups[:5]:
                print(f"    {row[0]} on {row[1]}: {row[2]} records")
        else:
            print("  No duplicates found!")

    # Step 3: Deduplicate - keep record with best vendor_role or most recent
    print("\n[STEP 3] Deduplicating price records...")
    with conn.cursor() as cur:
        # Delete duplicates keeping the one with best vendor_role (CANONICAL_PRIMARY > others)
        # or if same role, keep the one with latest ingestion
        cur.execute("""
            WITH ranked AS (
                SELECT
                    ctid,
                    canonical_id,
                    timestamp::date as date,
                    ROW_NUMBER() OVER (
                        PARTITION BY canonical_id, timestamp::date
                        ORDER BY
                            CASE
                                WHEN vendor_role = 'CANONICAL_PRIMARY' THEN 1
                                WHEN vendor_role = 'BACKUP_ONLY' THEN 2
                                WHEN vendor_role IS NOT NULL THEN 3
                                ELSE 4
                            END,
                            CASE
                                WHEN source IN ('binance', 'alpaca') THEN 1
                                WHEN source IN ('BINANCE', 'ALPACA') THEN 1
                                WHEN source IN ('yfinance', 'YAHOO') THEN 2
                                ELSE 3
                            END,
                            timestamp DESC
                    ) as rn
                FROM fhq_market.prices
            )
            DELETE FROM fhq_market.prices
            WHERE ctid IN (
                SELECT ctid FROM ranked WHERE rn > 1
            )
        """)
        deduped = cur.rowcount
        print(f"  Removed {deduped} duplicate records")
    conn.commit()

    # Step 4: Verify cleanup
    print("\n[STEP 4] Verification...")
    with conn.cursor() as cur:
        # Check total records
        cur.execute("SELECT COUNT(*) FROM fhq_market.prices")
        total = cur.fetchone()[0]
        print(f"  Total records: {total:,}")

        # Check for remaining duplicates
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT canonical_id, timestamp::date
                FROM fhq_market.prices
                GROUP BY canonical_id, timestamp::date
                HAVING COUNT(*) > 1
            ) t
        """)
        remaining_dups = cur.fetchone()[0]
        print(f"  Remaining duplicate date/symbol combos: {remaining_dups}")

        # Show latest data per key symbol
        cur.execute("""
            SELECT canonical_id, MAX(timestamp::date) as latest, COUNT(*) as total
            FROM fhq_market.prices
            WHERE canonical_id IN ('NVDA', 'SPY', 'BTC-USD', 'ETH-USD')
            GROUP BY canonical_id
            ORDER BY canonical_id
        """)
        print("\n  Key symbols:")
        for row in cur.fetchall():
            print(f"    {row[0]}: latest={row[1]}, total={row[2]}")

    # Step 5: VACUUM ANALYZE
    print("\n[STEP 5] Running VACUUM ANALYZE...")
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("VACUUM ANALYZE fhq_market.prices")
    print("  Done!")

    conn.close()
    print("\n" + "=" * 60)
    print("CLEANUP COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
