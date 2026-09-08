#!/usr/bin/env python3
"""
CEO-DIR-2026-086: Populate Trading Calendar

Populates fhq_meta.calendar_days with US Equity trading days 2025-2027.
Establishes trading calendar as first-class economic primitive.

Authority: CEO
Executed by: STIG (EC-003)
"""

import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import psycopg2


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "54322"),
        database=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres")
    )


# US Market Holidays (NYSE/NASDAQ)
US_HOLIDAYS = {
    # 2025
    date(2025, 1, 1): "New Year's Day",
    date(2025, 1, 20): "Martin Luther King Jr. Day",
    date(2025, 2, 17): "Presidents Day",
    date(2025, 4, 18): "Good Friday",
    date(2025, 5, 26): "Memorial Day",
    date(2025, 6, 19): "Juneteenth",
    date(2025, 7, 4): "Independence Day",
    date(2025, 9, 1): "Labor Day",
    date(2025, 11, 27): "Thanksgiving Day",
    date(2025, 12, 25): "Christmas Day",

    # 2026
    date(2026, 1, 1): "New Year's Day",
    date(2026, 1, 19): "Martin Luther King Jr. Day",
    date(2026, 2, 16): "Presidents Day",
    date(2026, 4, 3): "Good Friday",
    date(2026, 5, 25): "Memorial Day",
    date(2026, 6, 19): "Juneteenth",
    date(2026, 7, 3): "Independence Day (Observed)",
    date(2026, 9, 7): "Labor Day",
    date(2026, 11, 26): "Thanksgiving Day",
    date(2026, 12, 25): "Christmas Day",

    # 2027
    date(2027, 1, 1): "New Year's Day",
    date(2027, 1, 18): "Martin Luther King Jr. Day",
    date(2027, 2, 15): "Presidents Day",
    date(2027, 3, 26): "Good Friday",
    date(2027, 5, 31): "Memorial Day",
    date(2027, 6, 18): "Juneteenth (Observed)",
    date(2027, 7, 5): "Independence Day (Observed)",
    date(2027, 9, 6): "Labor Day",
    date(2027, 11, 25): "Thanksgiving Day",
    date(2027, 12, 24): "Christmas Day (Observed)",
}

# Early close days (1:00 PM ET)
US_EARLY_CLOSE = {
    date(2025, 11, 28): "Day after Thanksgiving",
    date(2025, 12, 24): "Christmas Eve",
    date(2026, 11, 27): "Day after Thanksgiving",
    date(2026, 12, 24): "Christmas Eve",
    date(2027, 11, 26): "Day after Thanksgiving",
}


def populate_trading_calendar(conn):
    """Populate trading calendar for 2025-2027."""
    print("=" * 60)
    print("CEO-DIR-2026-086: TRADING CALENDAR POPULATION")
    print("=" * 60)

    cur = conn.cursor()

    # Ensure trading_calendars has the entry
    cur.execute("""
        INSERT INTO fhq_meta.trading_calendars
        (calendar_id, calendar_name, version, effective_from, effective_to, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (
        'US_EQUITY',
        'US Equity Markets (NYSE/NASDAQ)',
        '1.0',
        date(2025, 1, 1),
        None,
        datetime.now()
    ))

    # Generate all dates from 2025-01-01 to 2027-12-31
    start_date = date(2025, 1, 1)
    end_date = date(2027, 12, 31)

    current = start_date
    inserted = 0
    skipped = 0

    while current <= end_date:
        dow = current.weekday()  # 0=Monday, 6=Sunday
        is_weekend = dow >= 5
        is_holiday = current in US_HOLIDAYS
        is_early = current in US_EARLY_CLOSE

        is_open = not is_weekend and not is_holiday

        if is_weekend:
            notes = "Saturday" if dow == 5 else "Sunday"
            session_open = None
            session_close = None
        elif is_holiday:
            notes = US_HOLIDAYS[current]
            session_open = None
            session_close = None
        elif is_early:
            notes = f"{US_EARLY_CLOSE[current]} (Early Close)"
            session_open = "09:30"
            session_close = "13:00"
        else:
            notes = None
            session_open = "09:30"
            session_close = "16:00"

        try:
            cur.execute("""
                INSERT INTO fhq_meta.calendar_days
                (calendar_id, date, is_open, session_open, session_close, early_close, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                'US_EQUITY',
                current,
                is_open,
                session_open,
                session_close,
                is_early,
                notes
            ))
            inserted += 1
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            skipped += 1
        except Exception as e:
            conn.rollback()
            print(f"  Error on {current}: {e}")

        current += timedelta(days=1)

    conn.commit()

    print(f"\n  Dates processed: {(end_date - start_date).days + 1}")
    print(f"  Inserted: {inserted}")
    print(f"  Skipped (existing): {skipped}")

    return inserted


def verify_calendar(conn):
    """Verify calendar population."""
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    cur = conn.cursor()

    # Summary
    cur.execute("""
        SELECT
            COUNT(*) as total_days,
            SUM(CASE WHEN is_open THEN 1 ELSE 0 END) as trading_days,
            SUM(CASE WHEN NOT is_open AND EXTRACT(DOW FROM date) NOT IN (0, 6) THEN 1 ELSE 0 END) as holidays,
            SUM(CASE WHEN early_close THEN 1 ELSE 0 END) as early_close_days,
            MIN(date) as coverage_start,
            MAX(date) as coverage_end
        FROM fhq_meta.calendar_days
        WHERE calendar_id = 'US_EQUITY'
    """)
    row = cur.fetchone()

    print(f"  Total Days: {row[0]}")
    print(f"  Trading Days: {row[1]}")
    print(f"  Holidays: {row[2]}")
    print(f"  Early Close Days: {row[3]}")
    print(f"  Coverage: {row[4]} to {row[5]}")

    # Test the resolver
    print("\n  Testing trading_days_forward function:")

    test_cases = [
        ('2026-01-07', 3, 'Wed Jan 7 + 3T'),  # Should skip weekend
        ('2026-01-06', 3, 'Tue Jan 6 + 3T'),  # Should skip weekend
        ('2026-01-05', 1, 'Mon Jan 5 + 1T'),  # Normal case
    ]

    for test_date, days, label in test_cases:
        cur.execute("""
            SELECT fhq_research.roi_horizon_date(%s::timestamptz, %s, 'US_EQUITY')
        """, (test_date, days))
        result = cur.fetchone()[0]
        dow = result.strftime('%a') if result else 'NULL'
        print(f"    {label} = {result} ({dow})")

    return row


def main():
    """Execute trading calendar population."""
    print("=" * 60)
    print("CEO-DIR-2026-086: TRADING CALENDAR CANONICALIZATION")
    print("=" * 60)
    print(f"Executed: {datetime.now().isoformat()}")
    print("Authority: CEO")
    print("Executed by: STIG (EC-003)")

    conn = get_db_connection()

    try:
        # Add primary key if missing
        cur = conn.cursor()
        try:
            cur.execute("""
                ALTER TABLE fhq_meta.trading_calendars
                ADD CONSTRAINT trading_calendars_pkey PRIMARY KEY (calendar_id)
            """)
            conn.commit()
            print("\n  Added primary key to trading_calendars")
        except:
            conn.rollback()

        try:
            cur.execute("""
                ALTER TABLE fhq_meta.calendar_days
                ADD CONSTRAINT calendar_days_pkey PRIMARY KEY (calendar_id, date)
            """)
            conn.commit()
            print("  Added primary key to calendar_days")
        except:
            conn.rollback()

        # Populate calendar
        inserted = populate_trading_calendar(conn)

        # Verify
        verify_calendar(conn)

        print("\n" + "=" * 60)
        print("TRADING CALENDAR CANONICALIZATION: COMPLETE")
        print("=" * 60)
        print("\nCanonical question now has one answer:")
        print("  'Is the market open?' -> fhq_meta.is_trading_day(date)")
        print("  'What is T+3 trading days?' -> fhq_research.roi_horizon_date(ts, 3)")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
