"""
Diagnose existing adr_registry table schema
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DB_DSN = os.getenv("DATABASE_URL")

if not DB_DSN:
    print("CRITICAL: DATABASE_URL missing")
    exit(1)

try:
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor()

    # Check if table exists and get columns
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'fhq_meta'
        AND table_name = 'adr_registry'
        ORDER BY ordinal_position;
    """)

    columns = cur.fetchall()

    if columns:
        print("=" * 60)
        print("EXISTING fhq_meta.adr_registry SCHEMA")
        print("=" * 60)
        print(f"{'Column':<25} {'Type':<20} {'Nullable':<10}")
        print("-" * 60)
        for col in columns:
            print(f"{col[0]:<25} {col[1]:<20} {col[2]:<10}")
        print("=" * 60)

        # Show CHECK constraints
        cur.execute("""
            SELECT conname, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'fhq_meta.adr_registry'::regclass
            AND contype = 'c';
        """)
        constraints = cur.fetchall()
        if constraints:
            print("\nCHECK CONSTRAINTS:")
            for c in constraints:
                print(f"  {c[0]}: {c[1]}")

        # Also show sample data
        cur.execute("SELECT * FROM fhq_meta.adr_registry LIMIT 3;")
        rows = cur.fetchall()
        if rows:
            print("\nSAMPLE DATA:")
            for row in rows:
                print(row)
    else:
        print("Table fhq_meta.adr_registry does NOT exist")

    cur.close()
    conn.close()

except Exception as e:
    print(f"ERROR: {e}")
