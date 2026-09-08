#!/usr/bin/env python3
"""
Populate fhq_macro.feature_registry for FINN DDATP Integration
==============================================================
Purpose: Enable FINN to read macro data and reduce FALLBACK_UNKNOWN rate

This script populates the feature_registry table with canonical macro features
that already exist in fhq_macro.canonical_series.

Generated: 2026-01-07
Authority: CEO-DIR-2026-016 (DDATP Production)
"""

import os
import sys
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Feature definitions matching ios006_g2_macro_ingest.py
FEATURE_DEFINITIONS = [
    # Cluster A: LIQUIDITY
    {
        "feature_id": "US_M2_YOY",
        "feature_name": "US M2 Money Supply YoY",
        "description": "Year-over-year change in US M2 money supply",
        "provenance": "FRED",
        "source_ticker": "M2SL",
        "frequency": "MONTHLY",
        "lag_period_days": 14,
        "cluster": "LIQUIDITY",
        "hypothesis": "M2 expansion correlates with risk asset appreciation",
        "expected_direction": "POSITIVE",
        "status": "CANONICAL"
    },
    {
        "feature_id": "FED_TOTAL_ASSETS",
        "feature_name": "Federal Reserve Total Assets",
        "description": "Total assets held by the Federal Reserve",
        "provenance": "FRED",
        "source_ticker": "WALCL",
        "frequency": "WEEKLY",
        "lag_period_days": 3,
        "cluster": "LIQUIDITY",
        "hypothesis": "Fed balance sheet expansion supports risk assets",
        "expected_direction": "POSITIVE",
        "status": "CANONICAL"
    },
    {
        "feature_id": "US_TGA_BALANCE",
        "feature_name": "Treasury General Account Balance",
        "description": "US Treasury General Account balance at the Fed",
        "provenance": "FRED",
        "source_ticker": "WTREGEN",
        "frequency": "WEEKLY",
        "lag_period_days": 3,
        "cluster": "LIQUIDITY",
        "hypothesis": "TGA drawdown adds liquidity to system",
        "expected_direction": "NEGATIVE",
        "status": "CANONICAL"
    },
    {
        "feature_id": "FED_RRP_BALANCE",
        "feature_name": "Fed Reverse Repo Balance",
        "description": "Federal Reserve Overnight Reverse Repo Facility balance",
        "provenance": "FRED",
        "source_ticker": "RRPONTSYD",
        "frequency": "DAILY",
        "lag_period_days": 1,
        "cluster": "LIQUIDITY",
        "hypothesis": "RRP drawdown releases liquidity",
        "expected_direction": "NEGATIVE",
        "status": "CANONICAL"
    },
    {
        "feature_id": "US_NET_LIQUIDITY",
        "feature_name": "US Net Liquidity",
        "description": "Fed Assets - TGA - RRP (net liquidity proxy)",
        "provenance": "CALCULATED",
        "source_ticker": "NET_LIQ_V1",
        "frequency": "DAILY",
        "lag_period_days": 1,
        "cluster": "LIQUIDITY",
        "hypothesis": "Net liquidity is primary driver of risk assets",
        "expected_direction": "POSITIVE",
        "status": "CANONICAL"
    },

    # Cluster B: CREDIT
    {
        "feature_id": "US_HY_SPREAD",
        "feature_name": "US High Yield Spread",
        "description": "BofA US High Yield Option-Adjusted Spread",
        "provenance": "FRED",
        "source_ticker": "BAMLH0A0HYM2",
        "frequency": "DAILY",
        "lag_period_days": 1,
        "cluster": "CREDIT",
        "hypothesis": "Widening spreads signal risk-off",
        "expected_direction": "NEGATIVE",
        "status": "CANONICAL"
    },
    {
        "feature_id": "US_IG_SPREAD",
        "feature_name": "US Investment Grade Spread",
        "description": "BofA US Corporate Investment Grade Spread",
        "provenance": "FRED",
        "source_ticker": "BAMLC0A0CM",
        "frequency": "DAILY",
        "lag_period_days": 1,
        "cluster": "CREDIT",
        "hypothesis": "IG spread widening precedes equity weakness",
        "expected_direction": "NEGATIVE",
        "status": "CANONICAL"
    },
    {
        "feature_id": "US_YIELD_CURVE_10Y2Y",
        "feature_name": "US Yield Curve 10Y-2Y",
        "description": "10-Year minus 2-Year Treasury yield spread",
        "provenance": "FRED",
        "source_ticker": "T10Y2Y",
        "frequency": "DAILY",
        "lag_period_days": 1,
        "cluster": "CREDIT",
        "hypothesis": "Curve steepening signals growth expectations",
        "expected_direction": "POSITIVE",
        "status": "CANONICAL"
    },
    {
        "feature_id": "US_FED_FUNDS_RATE",
        "feature_name": "Federal Funds Rate",
        "description": "Effective Federal Funds Rate",
        "provenance": "FRED",
        "source_ticker": "FEDFUNDS",
        "frequency": "MONTHLY",
        "lag_period_days": 1,
        "cluster": "CREDIT",
        "hypothesis": "Rate cuts support risk assets",
        "expected_direction": "NEGATIVE",
        "status": "CANONICAL"
    },

    # Cluster C: VOLATILITY
    {
        "feature_id": "VIX_INDEX",
        "feature_name": "VIX Volatility Index",
        "description": "CBOE VIX Index",
        "provenance": "FRED",
        "source_ticker": "VIXCLS",
        "frequency": "DAILY",
        "lag_period_days": 0,
        "cluster": "VOLATILITY",
        "hypothesis": "High VIX signals risk-off environment",
        "expected_direction": "NEGATIVE",
        "status": "CANONICAL"
    },

    # Cluster D: FACTOR
    {
        "feature_id": "DXY_INDEX",
        "feature_name": "US Dollar Index",
        "description": "Trade Weighted US Dollar Index (Broad)",
        "provenance": "FRED",
        "source_ticker": "DTWEXBGS",
        "frequency": "DAILY",
        "lag_period_days": 1,
        "cluster": "FACTOR",
        "hypothesis": "Dollar strength is headwind for risk assets",
        "expected_direction": "NEGATIVE",
        "status": "CANONICAL"
    },
    {
        "feature_id": "US_10Y_REAL_RATE",
        "feature_name": "US 10Y Real Rate",
        "description": "10-Year Treasury Inflation-Indexed Security",
        "provenance": "FRED",
        "source_ticker": "DFII10",
        "frequency": "DAILY",
        "lag_period_days": 1,
        "cluster": "FACTOR",
        "hypothesis": "Rising real rates pressure growth assets",
        "expected_direction": "NEGATIVE",
        "status": "CANONICAL"
    },
    {
        "feature_id": "GLOBAL_M2_USD",
        "feature_name": "Global M2 (USD proxy)",
        "description": "Global M2 money supply proxy using US M2",
        "provenance": "CALCULATED",
        "source_ticker": "GLOBAL_M2_V1",
        "frequency": "MONTHLY",
        "lag_period_days": 14,
        "cluster": "LIQUIDITY",
        "hypothesis": "Global liquidity drives crypto and risk assets",
        "expected_direction": "POSITIVE",
        "status": "CANONICAL"
    },
]


def get_db_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host=os.getenv('PGHOST', '127.0.0.1'),
        port=os.getenv('PGPORT', '54322'),
        database=os.getenv('PGDATABASE', 'postgres'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', 'postgres')
    )


def populate_feature_registry():
    """Populate fhq_macro.feature_registry with canonical features."""
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            # Check current count
            cur.execute("SELECT COUNT(*) FROM fhq_macro.feature_registry")
            before_count = cur.fetchone()[0]
            print(f"Feature registry before: {before_count} rows")

            # Get date ranges from canonical_series for each feature
            cur.execute("""
                SELECT feature_id,
                       MIN(timestamp)::date as start_date,
                       MAX(timestamp)::date as end_date
                FROM fhq_macro.canonical_series
                GROUP BY feature_id
            """)
            date_ranges = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

            # Insert features
            inserted = 0
            for feature in FEATURE_DEFINITIONS:
                feature_id = feature["feature_id"]

                # Get date range if available
                start_date, end_date = date_ranges.get(feature_id, (None, None))

                # Check if feature already exists
                cur.execute(
                    "SELECT 1 FROM fhq_macro.feature_registry WHERE feature_id = %s",
                    (feature_id,)
                )
                if cur.fetchone():
                    print(f"  SKIP: {feature_id} (already exists)")
                    continue

                # Insert feature
                cur.execute("""
                    INSERT INTO fhq_macro.feature_registry (
                        feature_id, feature_name, description, provenance,
                        source_ticker, frequency, lag_period_days,
                        history_start_date, history_end_date,
                        cluster, hypothesis, expected_direction, status,
                        created_by, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        'STIG', NOW(), NOW()
                    )
                """, (
                    feature_id,
                    feature["feature_name"],
                    feature["description"],
                    feature["provenance"],
                    feature["source_ticker"],
                    feature["frequency"],
                    feature["lag_period_days"],
                    start_date,
                    end_date,
                    feature["cluster"],
                    feature["hypothesis"],
                    feature["expected_direction"],
                    feature["status"]
                ))
                inserted += 1
                print(f"  INSERT: {feature_id} ({feature['cluster']})")

            conn.commit()

            # Verify
            cur.execute("SELECT COUNT(*) FROM fhq_macro.feature_registry")
            after_count = cur.fetchone()[0]

            print(f"\nFeature registry after: {after_count} rows")
            print(f"Inserted: {inserted} features")

            # Show summary by cluster
            cur.execute("""
                SELECT cluster, COUNT(*) as count,
                       COUNT(*) FILTER (WHERE status = 'CANONICAL') as canonical
                FROM fhq_macro.feature_registry
                GROUP BY cluster
                ORDER BY cluster
            """)
            print("\nBy cluster:")
            for row in cur.fetchall():
                print(f"  {row[0]}: {row[1]} features ({row[2]} canonical)")

            return inserted

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("POPULATE MACRO FEATURE REGISTRY")
    print("Purpose: Enable FINN macro data access for DDATP")
    print("=" * 60)
    print()

    inserted = populate_feature_registry()

    print()
    print("=" * 60)
    if inserted > 0:
        print("SUCCESS: Feature registry populated")
        print("FINN will now have macro_available=true")
    else:
        print("No new features inserted (registry may already be populated)")
    print("=" * 60)
