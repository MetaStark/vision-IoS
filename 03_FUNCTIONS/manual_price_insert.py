#!/usr/bin/env python3
"""
MANUAL PRICE INSERT
====================
CEO-DIR-2026-TRADE-LEARNING-ACTIVATION-004

Inserts 2026-02-10 price data for SPY and XLF to unblock exit engine.

Executed by: STIG (EC-003)
Date: 2026-02-10 22:30 Oslo
"""

import os
import psycopg2
from datetime import datetime
import hashlib
import uuid

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', '')
}

PRICE_DATA = [
    {
        'canonical_id': 'SPY',
        'asset_id': '01769791-cf50-4f53-b05a-96e54ecee808',
        'timestamp': '2026-02-10 21:00:00',
        'close': 692.12
    },
    {
        'canonical_id': 'XLF',
        'asset_id': '10722ca8-fa40-46a5-9882-042542df5f77',
        'timestamp': '2026-02-10 21:00:00',
        'close': 53.55
    }
]

def main():
    print("=" * 60)
    print("MANUAL PRICE INSERT - 2026-02-10")
    print("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    batch_id = str(uuid.uuid4())
    print(f"Batch ID: {batch_id}")

    for p in PRICE_DATA:
        data_hash = hashlib.md5(f"{p['canonical_id']}-2026-02-10-{p['close']}".encode()).hexdigest()

        cur.execute("""
            INSERT INTO fhq_market.prices (
                id, asset_id, canonical_id, timestamp,
                open, high, low, close, volume,
                source, data_hash, batch_id, canonicalized_by, adj_close
            )
            VALUES (
                gen_random_uuid(), %s, %s, %s::timestamp,
                %s, %s, %s, %s, 0,
                'manual_ingest_stig', %s, %s::uuid, 'STIG', %s
            )
            ON CONFLICT DO NOTHING
            RETURNING id
        """, (
            p['asset_id'], p['canonical_id'], p['timestamp'],
            p['close'], p['close'], p['close'], p['close'],
            data_hash, batch_id, p['close']
        ))

        result = cur.fetchone()
        if result:
            print(f"  INSERTED: {p['canonical_id']} @ {p['close']} (id: {result[0]})")
        else:
            print(f"  SKIPPED: {p['canonical_id']} (already exists)")

    # Verify
    cur.execute("""
        SELECT canonical_id, timestamp::date as date, close
        FROM fhq_market.prices
        WHERE canonical_id IN ('SPY', 'XLF')
        AND timestamp::date = '2026-02-10'
    """)

    print("\nVerification:")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} = {row[2]}")

    cur.close()
    conn.close()

    print("\n" + "=" * 60)
    print("COMPLETE - Exit engine can now evaluate trades")
    print("=" * 60)

if __name__ == '__main__':
    main()
