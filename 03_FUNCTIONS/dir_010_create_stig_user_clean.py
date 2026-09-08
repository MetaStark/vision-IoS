#!/usr/bin/env python3
"""
CEO-DIR-2026-WINNER-STRUCTURE-ANALYSIS-010
-- Create STIG user if not exists
"""

import psycopg2
import json
from datetime import datetime, timezone

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 54322,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'postgres'
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_user WHERE usename = 'postgres'")
            exists = cur.fetchone()
            if not exists[0]:
                print("[DIR-010] STIG user does not exist, creating...")
                cur.execute("""
                    CREATE USER STIG
                          WITH PASSWORD 'STIG_DAEMON_PASSWORD_CHANGE_IT'
                          NOINHERIT
                          NOCREATEDB
                          LOGIN
                          SUPERUSER
                    """)
                conn.commit()
                print("[DIR-010] Created STIG user")
            except Exception as e:
                print("[DIR-010] ERROR creating user: " + str(e))

            conn.commit()

    except Exception as e:
        print("[DIR-010] ERROR: " + str(e))

    finally:
        conn.close()

if __name__ == "__main__":
    main()
