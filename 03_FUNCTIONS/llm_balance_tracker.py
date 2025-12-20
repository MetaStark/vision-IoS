#!/usr/bin/env python3
"""
LLM Balance Tracker - Live balance fetching from DeepSeek API
FjordHQ IoS - ADR-012 Economic Safety Compliance

This module fetches live balance data from LLM providers and tracks
consumption over time by comparing balance snapshots.

Usage:
    python llm_balance_tracker.py              # Fetch and store current balance
    python llm_balance_tracker.py --report     # Show usage report
    python llm_balance_tracker.py --daemon     # Run continuous monitoring
"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime, timedelta
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

# Database connection
DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": os.getenv("PGPORT", "54322"),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres"),
}

# DeepSeek API configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-14afe9362fbb42deb0e62e0ef89535c1")
DEEPSEEK_BALANCE_URL = "https://api.deepseek.com/user/balance"


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def fetch_deepseek_balance() -> dict:
    """Fetch current balance from DeepSeek API."""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(DEEPSEEK_BALANCE_URL, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching DeepSeek balance: {e}")
        return None


def store_balance(balance_data: dict) -> bool:
    """Store balance snapshot in database."""
    if not balance_data or not balance_data.get("balance_infos"):
        return False

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        for info in balance_data["balance_infos"]:
            cur.execute("""
                INSERT INTO fhq_governance.llm_provider_balance
                (provider, currency, total_balance, granted_balance, topped_up_balance,
                 is_available, api_key_masked)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                "deepseek",
                info.get("currency", "USD"),
                Decimal(info.get("total_balance", "0")),
                Decimal(info.get("granted_balance", "0")),
                Decimal(info.get("topped_up_balance", "0")),
                balance_data.get("is_available", True),
                f"{DEEPSEEK_API_KEY[:7]}...{DEEPSEEK_API_KEY[-4:]}"
            ))

        conn.commit()
        print(f"[{datetime.now().isoformat()}] Balance stored: ${info.get('total_balance')} USD")
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error storing balance: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def calculate_consumption(hours: int = 24) -> dict:
    """Calculate consumption over the specified time period."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Get oldest and newest balance in period
        cur.execute("""
            WITH period_bounds AS (
                SELECT
                    MIN(fetched_at) as first_fetch,
                    MAX(fetched_at) as last_fetch
                FROM fhq_governance.llm_provider_balance
                WHERE provider = 'deepseek'
                  AND fetched_at >= NOW() - INTERVAL '%s hours'
            ),
            first_balance AS (
                SELECT total_balance, fetched_at
                FROM fhq_governance.llm_provider_balance b
                JOIN period_bounds p ON b.fetched_at = p.first_fetch
                WHERE provider = 'deepseek'
                LIMIT 1
            ),
            last_balance AS (
                SELECT total_balance, fetched_at
                FROM fhq_governance.llm_provider_balance b
                JOIN period_bounds p ON b.fetched_at = p.last_fetch
                WHERE provider = 'deepseek'
                LIMIT 1
            )
            SELECT
                f.total_balance as start_balance,
                f.fetched_at as start_time,
                l.total_balance as end_balance,
                l.fetched_at as end_time,
                (f.total_balance - l.total_balance) as consumed
            FROM first_balance f, last_balance l
        """, (hours,))

        result = cur.fetchone()
        return dict(result) if result else {}
    finally:
        cur.close()
        conn.close()


def update_telemetry_from_balance():
    """Update telemetry_cost_ledger based on balance changes."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Get daily consumption from balance snapshots
        cur.execute("""
            WITH daily_balances AS (
                SELECT
                    DATE(fetched_at) as day,
                    MIN(total_balance) FILTER (WHERE fetched_at = (
                        SELECT MIN(fetched_at) FROM fhq_governance.llm_provider_balance b2
                        WHERE DATE(b2.fetched_at) = DATE(b.fetched_at) AND b2.provider = 'deepseek'
                    )) as day_start_balance,
                    MIN(total_balance) FILTER (WHERE fetched_at = (
                        SELECT MAX(fetched_at) FROM fhq_governance.llm_provider_balance b2
                        WHERE DATE(b2.fetched_at) = DATE(b.fetched_at) AND b2.provider = 'deepseek'
                    )) as day_end_balance
                FROM fhq_governance.llm_provider_balance b
                WHERE provider = 'deepseek'
                GROUP BY DATE(fetched_at)
                ORDER BY day
            )
            SELECT
                day,
                day_start_balance,
                day_end_balance,
                COALESCE(day_start_balance - day_end_balance, 0) as daily_spend
            FROM daily_balances
            WHERE day_start_balance IS NOT NULL AND day_end_balance IS NOT NULL
        """)

        results = cur.fetchall()

        for row in results:
            if row["daily_spend"] > 0:
                # Upsert into telemetry_cost_ledger
                cur.execute("""
                    INSERT INTO fhq_governance.telemetry_cost_ledger
                    (ledger_date, agent_id, total_cost_usd, llm_requests, api_requests)
                    VALUES (%s, 'FINN', %s, 0, 0)
                    ON CONFLICT (ledger_date, agent_id)
                    DO UPDATE SET total_cost_usd = EXCLUDED.total_cost_usd
                """, (row["day"], row["daily_spend"]))

        conn.commit()
        print(f"Updated telemetry from {len(results)} daily balance records")
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error updating telemetry: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def print_report():
    """Print usage report."""
    balance_data = fetch_deepseek_balance()

    print("\n" + "="*60)
    print("FjordHQ LLM Usage Report - DeepSeek")
    print("="*60)

    if balance_data and balance_data.get("balance_infos"):
        for info in balance_data["balance_infos"]:
            print(f"\nCurrent Balance ({info['currency']}):")
            print(f"  Total:     ${info['total_balance']}")
            print(f"  Granted:   ${info['granted_balance']}")
            print(f"  Topped-up: ${info['topped_up_balance']}")
            print(f"  Available: {'Yes' if balance_data['is_available'] else 'No'}")

    # Show consumption
    for hours in [24, 168]:  # 24h and 7 days
        consumption = calculate_consumption(hours)
        if consumption:
            label = "24 hours" if hours == 24 else "7 days"
            print(f"\nConsumption (last {label}):")
            print(f"  Start: ${consumption.get('start_balance', 'N/A')}")
            print(f"  End:   ${consumption.get('end_balance', 'N/A')}")
            print(f"  Spent: ${consumption.get('consumed', 'N/A')}")

    print("\n" + "="*60)


def daemon_mode(interval_minutes: int = 60):
    """Run in daemon mode, fetching balance periodically."""
    import time

    print(f"Starting LLM Balance Tracker daemon (interval: {interval_minutes} min)")

    while True:
        try:
            balance = fetch_deepseek_balance()
            if balance:
                store_balance(balance)
                update_telemetry_from_balance()
        except Exception as e:
            print(f"Daemon error: {e}")

        time.sleep(interval_minutes * 60)


def main():
    parser = argparse.ArgumentParser(description="LLM Balance Tracker")
    parser.add_argument("--report", action="store_true", help="Show usage report")
    parser.add_argument("--daemon", action="store_true", help="Run in daemon mode")
    parser.add_argument("--interval", type=int, default=60, help="Daemon interval in minutes")

    args = parser.parse_args()

    if args.report:
        print_report()
    elif args.daemon:
        daemon_mode(args.interval)
    else:
        # Default: fetch and store current balance
        balance = fetch_deepseek_balance()
        if balance:
            store_balance(balance)
            print(json.dumps(balance, indent=2))
        else:
            print("Failed to fetch balance")
            sys.exit(1)


if __name__ == "__main__":
    main()
