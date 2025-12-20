#!/usr/bin/env python3
"""
LAKE Tier Data Ingest - Free API Sources Only
==============================================
Document ID: LAKE-TIER-INGEST-20251203
Authority: CEO Directive
ADR Alignment: ADR-012 (API Waterfall), ADR-013 (One-Source Truth)

SOURCES (100% FREE):
- YFINANCE: Market data (SPX, VIX, Yields, Gold, Oil)
- FRED: Macro series (CPI, PMI, Fed Funds, Claims)

NO API KEYS REQUIRED FOR YFINANCE.
FRED requires free registration at fred.stlouisfed.org
"""

import os
import json
import hashlib
import psycopg2
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import time

# Database connection
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 54322,
    "database": "postgres",
    "user": "postgres",
    "password": "postgres"
}

# YFINANCE symbols - completely free, no API key
YFINANCE_SYMBOLS = {
    # Priority 1: Core indices
    "^GSPC": {"name": "S&P 500", "asset_class": "INDEX", "priority": 1},
    "^VIX": {"name": "VIX Volatility", "asset_class": "INDEX", "priority": 1},
    "^TNX": {"name": "10-Year Treasury Yield", "asset_class": "YIELD", "priority": 1},
    "^IRX": {"name": "13-Week Treasury Bill", "asset_class": "YIELD", "priority": 1},

    # Priority 2: Commodities
    "GC=F": {"name": "Gold Futures", "asset_class": "COMMODITY", "priority": 2},
    "CL=F": {"name": "Crude Oil Futures", "asset_class": "COMMODITY", "priority": 2},

    # Existing assets (ensure complete)
    "BTC-USD": {"name": "Bitcoin USD", "asset_class": "CRYPTO", "priority": 1},
    "ETH-USD": {"name": "Ethereum USD", "asset_class": "CRYPTO", "priority": 1},
    "SOL-USD": {"name": "Solana USD", "asset_class": "CRYPTO", "priority": 2},
}

# FRED series - free with API key
FRED_SERIES = {
    # Priority 1: Yields
    "DGS10": {"name": "10-Year Treasury Rate", "frequency": "daily", "priority": 1},
    "DGS2": {"name": "2-Year Treasury Rate", "frequency": "daily", "priority": 1},
    "DGS30": {"name": "30-Year Treasury Rate", "frequency": "daily", "priority": 2},
    "T10Y2Y": {"name": "10Y-2Y Spread", "frequency": "daily", "priority": 1},

    # Priority 2: Macro
    "CPIAUCSL": {"name": "Consumer Price Index", "frequency": "monthly", "priority": 2},
    "FEDFUNDS": {"name": "Federal Funds Rate", "frequency": "monthly", "priority": 2},
    "UNRATE": {"name": "Unemployment Rate", "frequency": "monthly", "priority": 2},
    "ICSA": {"name": "Initial Jobless Claims", "frequency": "weekly", "priority": 2},

    # Priority 3: Sentiment/Activity
    "UMCSENT": {"name": "Consumer Sentiment", "frequency": "monthly", "priority": 3},
    "INDPRO": {"name": "Industrial Production", "frequency": "monthly", "priority": 3},
}


class LakeTierIngest:
    """LAKE Tier ingestion using only free APIs"""

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.results = {
            "ingest_id": f"LAKE-INGEST-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "yfinance": {},
            "fred": {},
            "errors": [],
            "summary": {}
        }

    def log_api_usage(self, provider: str, endpoint: str, status: int, agent: str = "STIG"):
        """Log API usage for budget tracking"""
        with self.conn.cursor() as cur:
            # Update daily budget
            cur.execute("""
                INSERT INTO fhq_governance.api_budget_log
                    (provider_name, usage_date, requests_made, daily_limit, last_request_at)
                SELECT %s, CURRENT_DATE, 1, COALESCE(daily_limit, 0), NOW()
                FROM fhq_governance.api_provider_registry
                WHERE provider_name = %s
                ON CONFLICT (provider_name, usage_date)
                DO UPDATE SET
                    requests_made = fhq_governance.api_budget_log.requests_made + 1,
                    last_request_at = NOW(),
                    updated_at = NOW()
            """, (provider, provider))

            # Log event
            cur.execute("""
                INSERT INTO fhq_governance.api_usage_events
                    (provider_name, endpoint, response_status, agent_id)
                VALUES (%s, %s, %s, %s)
            """, (provider, endpoint, status, agent))

            self.conn.commit()

    def check_budget_threshold(self, provider: str) -> Dict[str, Any]:
        """Check if provider is at 90% threshold"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT requests_made, daily_limit, usage_percent,
                       threshold_90_breached, threshold_100_breached
                FROM fhq_governance.api_budget_log
                WHERE provider_name = %s AND usage_date = CURRENT_DATE
            """, (provider,))
            row = cur.fetchone()

        if row:
            return {
                "requests_made": row[0],
                "daily_limit": row[1],
                "usage_percent": float(row[2]) if row[2] else 0,
                "at_90_percent": row[3],
                "at_100_percent": row[4]
            }
        return {"requests_made": 0, "daily_limit": 0, "usage_percent": 0}

    def ingest_yfinance(self, symbols: List[str] = None, period: str = "10y") -> Dict[str, Any]:
        """Ingest data from yfinance (completely free)"""
        try:
            import yfinance as yf
        except ImportError:
            return {"error": "yfinance not installed. Run: pip install yfinance"}

        if symbols is None:
            symbols = list(YFINANCE_SYMBOLS.keys())

        results = {}

        for symbol in symbols:
            print(f"[YFINANCE] Fetching {symbol}...")
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period)

                if hist.empty:
                    results[symbol] = {"status": "NO_DATA", "records": 0}
                    continue

                # Store in database
                records_inserted = self._store_price_data(symbol, hist, "YFINANCE")

                results[symbol] = {
                    "status": "SUCCESS",
                    "records": records_inserted,
                    "start": str(hist.index.min()),
                    "end": str(hist.index.max()),
                    "source": "YFINANCE"
                }

                # Log API usage (yfinance is free but we track anyway)
                self.log_api_usage("YFINANCE", f"history/{symbol}", 200)

                # Small delay to be respectful
                time.sleep(0.5)

            except Exception as e:
                results[symbol] = {"status": "ERROR", "error": str(e)}
                self.results["errors"].append(f"YFINANCE/{symbol}: {str(e)}")

        self.results["yfinance"] = results
        return results

    def ingest_fred(self, series: List[str] = None, start_date: str = "2015-01-01") -> Dict[str, Any]:
        """Ingest data from FRED (free with API key)"""
        fred_api_key = os.environ.get("FRED_API_KEY")

        if not fred_api_key:
            return {"error": "FRED_API_KEY not set. Get free key at fred.stlouisfed.org"}

        try:
            from fredapi import Fred
            fred = Fred(api_key=fred_api_key)
        except ImportError:
            return {"error": "fredapi not installed. Run: pip install fredapi"}

        if series is None:
            series = list(FRED_SERIES.keys())

        results = {}

        for series_id in series:
            # Check budget before each request
            budget = self.check_budget_threshold("FRED")
            if budget.get("at_90_percent"):
                print(f"[FRED] WARNING: At 90% budget ({budget['usage_percent']}%)")
            if budget.get("at_100_percent"):
                print(f"[FRED] BLOCKED: Daily limit reached")
                results[series_id] = {"status": "BUDGET_EXCEEDED"}
                continue

            print(f"[FRED] Fetching {series_id}...")
            try:
                data = fred.get_series(series_id, observation_start=start_date)

                if data.empty:
                    results[series_id] = {"status": "NO_DATA", "records": 0}
                    continue

                # Store in database
                records_inserted = self._store_macro_data(series_id, data, "FRED")

                results[series_id] = {
                    "status": "SUCCESS",
                    "records": records_inserted,
                    "start": str(data.index.min()),
                    "end": str(data.index.max()),
                    "source": "FRED"
                }

                # Log API usage
                self.log_api_usage("FRED", f"series/{series_id}", 200)

                # Respect rate limits (120/min = 2/sec)
                time.sleep(0.5)

            except Exception as e:
                results[series_id] = {"status": "ERROR", "error": str(e)}
                self.results["errors"].append(f"FRED/{series_id}: {str(e)}")

        self.results["fred"] = results
        return results

    def _store_price_data(self, symbol: str, data, vendor: str) -> int:
        """Store price data in fhq_data.price_series"""
        records = 0

        # Normalize symbol for listing_id
        listing_id = symbol.replace("^", "").replace("=F", "")

        with self.conn.cursor() as cur:
            for idx, row in data.iterrows():
                try:
                    cur.execute("""
                        INSERT INTO fhq_data.price_series
                            (listing_id, timestamp, vendor_id, frequency, price_type,
                             open, high, low, close, volume, source_id, is_verified)
                        VALUES (%s, %s, %s, 'DAILY', 'SPOT', %s, %s, %s, %s, %s, %s, TRUE)
                        ON CONFLICT DO NOTHING
                    """, (
                        listing_id,
                        idx.to_pydatetime(),
                        vendor,
                        float(row.get('Open', 0)) if row.get('Open') else None,
                        float(row.get('High', 0)) if row.get('High') else None,
                        float(row.get('Low', 0)) if row.get('Low') else None,
                        float(row.get('Close', 0)) if row.get('Close') else None,
                        int(row.get('Volume', 0)) if row.get('Volume') else None,
                        f"{vendor}_{listing_id}"
                    ))
                    records += cur.rowcount
                except Exception as e:
                    print(f"  Error storing {symbol} {idx}: {e}")

            self.conn.commit()

        return records

    def _store_macro_data(self, series_id: str, data, vendor: str) -> int:
        """Store macro data in fhq_research.macro_indicators"""
        records = 0
        series_info = FRED_SERIES.get(series_id, {})

        with self.conn.cursor() as cur:
            for idx, value in data.items():
                if pd.isna(value):
                    continue
                try:
                    cur.execute("""
                        INSERT INTO fhq_research.macro_indicators
                            (indicator_id, date, vendor_id, value, indicator_name,
                             indicator_type, retrieved_at, is_verified)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW(), TRUE)
                        ON CONFLICT DO NOTHING
                    """, (
                        series_id,
                        idx.date(),
                        vendor,
                        float(value),
                        series_info.get("name", series_id),
                        series_info.get("frequency", "daily")
                    ))
                    records += cur.rowcount
                except Exception as e:
                    print(f"  Error storing {series_id} {idx}: {e}")

            self.conn.commit()

        return records

    def run_priority_1(self) -> Dict[str, Any]:
        """Run Priority 1 ingest: SPX, VIX, Yields"""
        print("=" * 70)
        print("LAKE TIER INGEST - PRIORITY 1")
        print("=" * 70)

        # Priority 1 symbols
        p1_yfinance = ["^GSPC", "^VIX", "^TNX", "^IRX"]
        p1_fred = ["DGS10", "DGS2", "T10Y2Y"]

        self.ingest_yfinance(p1_yfinance)
        self.ingest_fred(p1_fred)

        return self.results

    def run_priority_2(self) -> Dict[str, Any]:
        """Run Priority 2 ingest: Gold, Oil, Macro"""
        print("=" * 70)
        print("LAKE TIER INGEST - PRIORITY 2")
        print("=" * 70)

        p2_yfinance = ["GC=F", "CL=F"]
        p2_fred = ["CPIAUCSL", "FEDFUNDS", "UNRATE", "ICSA"]

        self.ingest_yfinance(p2_yfinance)
        self.ingest_fred(p2_fred)

        return self.results

    def run_full_ingest(self) -> Dict[str, Any]:
        """Run complete LAKE tier ingest"""
        print("=" * 70)
        print("LAKE TIER INGEST - FULL")
        print("=" * 70)

        self.ingest_yfinance()
        self.ingest_fred()

        self.results["completed_at"] = datetime.now(timezone.utc).isoformat()
        self.results["summary"] = {
            "yfinance_symbols": len(self.results.get("yfinance", {})),
            "fred_series": len(self.results.get("fred", {})),
            "errors": len(self.results.get("errors", []))
        }

        return self.results

    def close(self):
        self.conn.close()


def main():
    """Execute LAKE tier ingest"""
    import pandas as pd  # Import here to check availability

    ingest = LakeTierIngest()
    try:
        # Run Priority 1 first
        results = ingest.run_priority_1()

        # Save results
        output_path = "05_GOVERNANCE/PHASE3/LAKE_INGEST_RESULTS.json"
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\nResults saved to: {output_path}")
        print(f"Errors: {len(results.get('errors', []))}")

        return results
    finally:
        ingest.close()


if __name__ == "__main__":
    main()
