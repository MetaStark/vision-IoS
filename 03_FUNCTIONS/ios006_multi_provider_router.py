"""
IoS-006 G2.5 Multi-Provider Canonical Router
=============================================
Authority: LARS (Strategy) + STIG (Technical)
Phase: G2.5 ARCHITECTURE UPGRADE
ADR Compliance: ADR-011 (Lineage), ADR-012 (API Waterfall), ADR-013 (One-True-Source)

Mission: Eliminate single-point-of-failure risks by routing through multiple providers.

Routing Logic:
1. Capability Lookup - Find providers that support the feature
2. Preference Sort - Order by canonical_source_preference (1=Regulatory > 4=Scraper)
3. Quota Check - Filter providers at 99% daily limit
4. Selection - Execute fetch on highest-ranking available provider
5. Failover - On failure, retry with next provider in stack
"""

import os
import json
import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from datetime import timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('IoS-006-Router')

load_dotenv()

# =============================================================================
# ROUTER CONFIGURATION
# =============================================================================

ROUTER_LOGIC_VERSION = "1.0.0"

@dataclass
class ProviderConfig:
    """Provider configuration from database."""
    provider_id: str
    ticker_symbol: str
    preference_rank: int
    daily_limit: int
    used_today: int
    rate_limit_per_minute: int
    api_key_env_var: Optional[str]
    base_url: str


@dataclass
class FetchResult:
    """Result of a data fetch operation."""
    success: bool
    provider_id: str
    data: Optional[pd.DataFrame]
    error: Optional[str]
    response_time_ms: int
    failover_count: int


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host=os.getenv('PGHOST', '127.0.0.1'),
        port=os.getenv('PGPORT', '54322'),
        database=os.getenv('PGDATABASE', 'postgres'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', 'postgres')
    )


# =============================================================================
# PROVIDER IMPLEMENTATIONS
# =============================================================================

class ProviderFetcher:
    """Base class for provider-specific data fetchers."""

    def __init__(self, provider_id: str, api_key: Optional[str] = None):
        self.provider_id = provider_id
        self.api_key = api_key

    def fetch(self, ticker: str, feature_id: str) -> Optional[pd.DataFrame]:
        raise NotImplementedError


class TwelveDataFetcher(ProviderFetcher):
    """TwelveData API fetcher (Exchange Grade)."""

    def fetch(self, ticker: str, feature_id: str) -> Optional[pd.DataFrame]:
        try:
            import requests

            if not self.api_key:
                logger.warning("TwelveData API key not set")
                return None

            url = f"https://api.twelvedata.com/time_series"
            params = {
                'symbol': ticker,
                'interval': '1day',
                'outputsize': 5000,
                'apikey': self.api_key
            }

            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if 'values' not in data:
                logger.error(f"TwelveData error: {data.get('message', 'Unknown error')}")
                return None

            df = pd.DataFrame(data['values'])
            df['timestamp'] = pd.to_datetime(df['datetime'])
            df['value_raw'] = pd.to_numeric(df['close'], errors='coerce')
            df['feature_id'] = feature_id
            df['provenance'] = 'TWELVEDATA'
            df['source_ticker'] = ticker

            df = df[['timestamp', 'value_raw', 'feature_id', 'provenance', 'source_ticker']]
            df = df.dropna(subset=['value_raw']).sort_values('timestamp')

            logger.info(f"TWELVEDATA | {feature_id} ({ticker}): {len(df)} observations")
            return df

        except Exception as e:
            logger.error(f"TwelveData fetch failed: {e}")
            return None


class FinnhubFetcher(ProviderFetcher):
    """Finnhub API fetcher (Aggregator Grade)."""

    def fetch(self, ticker: str, feature_id: str) -> Optional[pd.DataFrame]:
        try:
            import requests

            if not self.api_key:
                logger.warning("Finnhub API key not set")
                return None

            # Get candle data
            end = int(datetime.now().timestamp())
            start = int((datetime.now() - timedelta(days=365*20)).timestamp())

            url = f"https://finnhub.io/api/v1/stock/candle"
            params = {
                'symbol': ticker.replace('^', ''),  # Finnhub doesn't use ^ prefix
                'resolution': 'D',
                'from': start,
                'to': end,
                'token': self.api_key
            }

            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if data.get('s') != 'ok' or 'c' not in data:
                logger.error(f"Finnhub error: {data.get('s', 'Unknown error')}")
                return None

            df = pd.DataFrame({
                'timestamp': pd.to_datetime(data['t'], unit='s'),
                'value_raw': data['c'],
                'feature_id': feature_id,
                'provenance': 'FINNHUB',
                'source_ticker': ticker
            })

            df = df.dropna(subset=['value_raw']).sort_values('timestamp')

            logger.info(f"FINNHUB | {feature_id} ({ticker}): {len(df)} observations")
            return df

        except Exception as e:
            logger.error(f"Finnhub fetch failed: {e}")
            return None


class AlphaVantageFetcher(ProviderFetcher):
    """Alpha Vantage API fetcher (Aggregator Grade)."""

    def fetch(self, ticker: str, feature_id: str) -> Optional[pd.DataFrame]:
        try:
            import requests

            if not self.api_key:
                logger.warning("AlphaVantage API key not set")
                return None

            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'TIME_SERIES_DAILY',
                'symbol': ticker,
                'outputsize': 'full',
                'apikey': self.api_key
            }

            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            time_series_key = 'Time Series (Daily)'
            if time_series_key not in data:
                logger.error(f"AlphaVantage error: {data.get('Note', data.get('Error Message', 'Unknown error'))}")
                return None

            records = []
            for date_str, values in data[time_series_key].items():
                records.append({
                    'timestamp': pd.to_datetime(date_str),
                    'value_raw': float(values['4. close']),
                    'feature_id': feature_id,
                    'provenance': 'ALPHAVANTAGE',
                    'source_ticker': ticker
                })

            df = pd.DataFrame(records)
            df = df.sort_values('timestamp')

            logger.info(f"ALPHAVANTAGE | {feature_id} ({ticker}): {len(df)} observations")
            return df

        except Exception as e:
            logger.error(f"AlphaVantage fetch failed: {e}")
            return None


class FMPFetcher(ProviderFetcher):
    """Financial Modeling Prep API fetcher (Aggregator Grade)."""

    def fetch(self, ticker: str, feature_id: str) -> Optional[pd.DataFrame]:
        try:
            import requests

            if not self.api_key:
                logger.warning("FMP API key not set")
                return None

            # Clean ticker
            clean_ticker = ticker.replace('^', '%5E')

            url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{clean_ticker}"
            params = {'apikey': self.api_key}

            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if 'historical' not in data:
                logger.error(f"FMP error: {data.get('Error Message', 'No historical data')}")
                return None

            df = pd.DataFrame(data['historical'])
            df['timestamp'] = pd.to_datetime(df['date'])
            df['value_raw'] = pd.to_numeric(df['close'], errors='coerce')
            df['feature_id'] = feature_id
            df['provenance'] = 'FMP'
            df['source_ticker'] = ticker

            df = df[['timestamp', 'value_raw', 'feature_id', 'provenance', 'source_ticker']]
            df = df.dropna(subset=['value_raw']).sort_values('timestamp')

            logger.info(f"FMP | {feature_id} ({ticker}): {len(df)} observations")
            return df

        except Exception as e:
            logger.error(f"FMP fetch failed: {e}")
            return None


class YahooFetcher(ProviderFetcher):
    """Yahoo Finance fetcher (Scraper Grade)."""

    def fetch(self, ticker: str, feature_id: str) -> Optional[pd.DataFrame]:
        try:
            import yfinance as yf

            time.sleep(2)  # Rate limiting

            # Use auto_adjust=False to avoid column issues with new yfinance
            data = yf.download(ticker, period='max', progress=False, timeout=30, auto_adjust=False)

            if data is None or len(data) == 0:
                logger.error(f"Yahoo returned empty data for {ticker}")
                return None

            # Handle multi-index columns from yfinance
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            value_col = 'Adj Close' if 'Adj Close' in data.columns else 'Close'

            # Extract values properly
            values = data[value_col].values
            if hasattr(values, 'flatten'):
                values = values.flatten()

            df = pd.DataFrame({
                'timestamp': data.index,
                'value_raw': values,
                'feature_id': feature_id,
                'provenance': 'YAHOO',
                'source_ticker': ticker
            })

            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.dropna(subset=['value_raw'])

            logger.info(f"YAHOO | {feature_id} ({ticker}): {len(df)} observations")
            return df

        except Exception as e:
            logger.error(f"Yahoo fetch failed: {e}")
            return None


class CBOEFetcher(ProviderFetcher):
    """CBOE public data fetcher (Exchange Grade)."""

    def fetch(self, ticker: str, feature_id: str) -> Optional[pd.DataFrame]:
        try:
            import requests

            # CBOE provides VIX data via CSV downloads
            if ticker in ['VIX', 'VIX9D', 'VIX3M']:
                url = f"https://cdn.cboe.com/api/global/delayed_quotes/{ticker.lower()}.csv"
            else:
                logger.warning(f"CBOE does not support ticker: {ticker}")
                return None

            response = requests.get(url, timeout=30)

            if response.status_code != 200:
                logger.error(f"CBOE returned status {response.status_code}")
                return None

            # CBOE CSV format varies, try to parse
            from io import StringIO
            df = pd.read_csv(StringIO(response.text))

            # Normalize column names
            df.columns = [c.lower().strip() for c in df.columns]

            if 'date' in df.columns and 'close' in df.columns:
                df['timestamp'] = pd.to_datetime(df['date'])
                df['value_raw'] = pd.to_numeric(df['close'], errors='coerce')
            elif 'trade date' in df.columns and 'close' in df.columns:
                df['timestamp'] = pd.to_datetime(df['trade date'])
                df['value_raw'] = pd.to_numeric(df['close'], errors='coerce')
            else:
                logger.error(f"CBOE CSV format not recognized: {df.columns.tolist()}")
                return None

            df['feature_id'] = feature_id
            df['provenance'] = 'CBOE'
            df['source_ticker'] = ticker

            df = df[['timestamp', 'value_raw', 'feature_id', 'provenance', 'source_ticker']]
            df = df.dropna(subset=['value_raw']).sort_values('timestamp')

            logger.info(f"CBOE | {feature_id} ({ticker}): {len(df)} observations")
            return df

        except Exception as e:
            logger.error(f"CBOE fetch failed: {e}")
            return None


class FREDFetcher(ProviderFetcher):
    """FRED API fetcher (Regulatory Grade)."""

    def fetch(self, ticker: str, feature_id: str) -> Optional[pd.DataFrame]:
        try:
            # Try using fredapi if available
            try:
                from fredapi import Fred

                if not self.api_key:
                    logger.warning("FRED API key not set, trying fallback")
                    return self._fred_fallback(ticker, feature_id)

                fred = Fred(api_key=self.api_key)
                series = fred.get_series(ticker)

                if series is None or len(series) == 0:
                    return None

                df = pd.DataFrame({
                    'timestamp': series.index,
                    'value_raw': series.values,
                    'feature_id': feature_id,
                    'provenance': 'FRED',
                    'source_ticker': ticker
                })

                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.dropna(subset=['value_raw'])

                logger.info(f"FRED | {feature_id} ({ticker}): {len(df)} observations")
                return df

            except ImportError:
                return self._fred_fallback(ticker, feature_id)

        except Exception as e:
            logger.error(f"FRED fetch failed: {e}")
            return None

    def _fred_fallback(self, ticker: str, feature_id: str) -> Optional[pd.DataFrame]:
        """Fallback FRED fetcher using pandas_datareader."""
        try:
            import pandas_datareader as pdr

            start_date = datetime(2000, 1, 1)
            end_date = datetime.now()

            series = pdr.get_data_fred(ticker, start=start_date, end=end_date)

            if series is None or len(series) == 0:
                return None

            df = pd.DataFrame({
                'timestamp': series.index,
                'value_raw': series[ticker].values,
                'feature_id': feature_id,
                'provenance': 'FRED',
                'source_ticker': ticker
            })

            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.dropna(subset=['value_raw'])

            logger.info(f"FRED (fallback) | {feature_id} ({ticker}): {len(df)} observations")
            return df

        except Exception as e:
            logger.error(f"FRED fallback failed: {e}")
            return None


# Provider factory
PROVIDER_FETCHERS = {
    'fred': FREDFetcher,
    'twelvedata': TwelveDataFetcher,
    'finnhub': FinnhubFetcher,
    'alphavantage': AlphaVantageFetcher,
    'fmp': FMPFetcher,
    'yahoo': YahooFetcher,
    'cboe': CBOEFetcher,
}


# =============================================================================
# MULTI-PROVIDER ROUTER
# =============================================================================

class MultiProviderRouter:
    """
    Multi-Provider Canonical Router.

    Deterministic routing logic:
    1. Capability Lookup - Find providers supporting the feature
    2. Preference Sort - Order by canonical_source_preference
    3. Quota Check - Filter at 99% daily limit
    4. Selection - Fetch from highest-ranking available
    5. Failover - Retry with next provider on failure
    """

    def __init__(self):
        self.conn = get_db_connection()
        self.router_logic_hash = self._compute_router_hash()
        self.fetch_results: List[FetchResult] = []

    def _compute_router_hash(self) -> str:
        """Compute hash of routing logic for ADR-011 lineage."""
        logic_str = f"ROUTER_V{ROUTER_LOGIC_VERSION}:PREFERENCE_SORT:QUOTA_99PCT:FAILOVER"
        return hashlib.sha256(logic_str.encode()).hexdigest()[:16]

    def get_providers_for_feature(self, feature_id: str) -> List[Dict]:
        """Get ranked list of providers for a feature."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT
                    pqs.provider_id,
                    pc.ticker_symbol,
                    pqs.canonical_source_preference,
                    pqs.daily_limit,
                    pqs.used_today,
                    pqs.rate_limit_per_minute,
                    pqs.api_key_env_var,
                    pqs.base_url,
                    pqs.consecutive_failures,
                    pqs.cooldown_until,
                    pqs.requires_api_key
                FROM fhq_macro.provider_quota_state pqs
                JOIN fhq_macro.provider_capability pc ON pqs.provider_id = pc.provider_id
                WHERE pc.feature_id = %s
                  AND pc.is_active = TRUE
                  AND pqs.is_active = TRUE
                ORDER BY pqs.canonical_source_preference ASC, pqs.consecutive_failures ASC
            """, (feature_id,))

            providers = []
            for row in cur.fetchall():
                providers.append({
                    'provider_id': row[0],
                    'ticker_symbol': row[1],
                    'preference_rank': row[2],
                    'daily_limit': row[3],
                    'used_today': row[4],
                    'rate_limit_per_minute': row[5],
                    'api_key_env_var': row[6],
                    'base_url': row[7],
                    'consecutive_failures': row[8],
                    'cooldown_until': row[9],
                    'requires_api_key': row[10]
                })

            return providers

    def record_usage(self, provider_id: str, success: bool, response_time_ms: int = None):
        """Record provider usage in database."""
        with self.conn.cursor() as cur:
            if success:
                cur.execute("""
                    UPDATE fhq_macro.provider_quota_state
                    SET used_today = used_today + 1,
                        used_this_month = COALESCE(used_this_month, 0) + 1,
                        last_successful_call = NOW(),
                        consecutive_failures = 0,
                        cooldown_until = NULL,
                        updated_at = NOW()
                    WHERE provider_id = %s
                """, (provider_id,))
            else:
                cur.execute("""
                    UPDATE fhq_macro.provider_quota_state
                    SET consecutive_failures = consecutive_failures + 1,
                        last_failed_call = NOW(),
                        cooldown_until = NOW() + (POWER(2, LEAST(consecutive_failures + 1, 6))::INTEGER || ' minutes')::INTERVAL,
                        updated_at = NOW()
                    WHERE provider_id = %s
                """, (provider_id,))
        self.conn.commit()

    def fetch_feature(self, feature_id: str, max_retries: int = 5) -> FetchResult:
        """
        Fetch data for a feature using multi-provider routing.

        Returns FetchResult with data from the highest-priority available provider.
        """
        providers = self.get_providers_for_feature(feature_id)

        if not providers:
            logger.error(f"No providers configured for {feature_id}")
            return FetchResult(
                success=False,
                provider_id='NONE',
                data=None,
                error='No providers configured',
                response_time_ms=0,
                failover_count=0
            )

        logger.info(f"ROUTER | {feature_id}: {len(providers)} providers available")

        excluded_providers = []
        failover_count = 0

        for attempt in range(max_retries):
            # Filter providers
            available = [
                p for p in providers
                if p['provider_id'] not in excluded_providers
                and p['used_today'] < (p['daily_limit'] * 0.99)
                and (p['cooldown_until'] is None or p['cooldown_until'] < datetime.now(timezone.utc))
            ]

            if not available:
                logger.warning(f"ROUTER | {feature_id}: All providers exhausted or at quota")
                break

            # Select top provider
            provider = available[0]
            provider_id = provider['provider_id']
            ticker = provider['ticker_symbol']

            logger.info(f"ROUTER | {feature_id}: Trying {provider_id} (pref={provider['preference_rank']}, "
                       f"used={provider['used_today']}/{provider['daily_limit']})")

            # Get API key if required
            api_key = None
            requires_key = provider.get('requires_api_key', True)
            if requires_key and provider.get('api_key_env_var'):
                api_key = os.getenv(provider['api_key_env_var'])
                if not api_key:
                    logger.warning(f"ROUTER | {feature_id}: {provider_id} API key not set, skipping")
                    excluded_providers.append(provider_id)
                    continue
            elif not requires_key:
                # Provider doesn't require API key (e.g., Yahoo, CBOE public feeds)
                logger.info(f"ROUTER | {feature_id}: {provider_id} (no API key required)")

            # Create fetcher
            fetcher_class = PROVIDER_FETCHERS.get(provider_id)
            if not fetcher_class:
                logger.warning(f"ROUTER | {feature_id}: No fetcher for {provider_id}")
                excluded_providers.append(provider_id)
                continue

            # Execute fetch
            start_time = time.time()
            try:
                fetcher = fetcher_class(provider_id, api_key)
                data = fetcher.fetch(ticker, feature_id)
                response_time_ms = int((time.time() - start_time) * 1000)

                if data is not None and len(data) > 0:
                    self.record_usage(provider_id, success=True, response_time_ms=response_time_ms)

                    result = FetchResult(
                        success=True,
                        provider_id=provider_id,
                        data=data,
                        error=None,
                        response_time_ms=response_time_ms,
                        failover_count=failover_count
                    )
                    self.fetch_results.append(result)

                    logger.info(f"ROUTER | {feature_id}: SUCCESS via {provider_id} "
                               f"({len(data)} obs, {response_time_ms}ms, failovers={failover_count})")
                    return result

                else:
                    logger.warning(f"ROUTER | {feature_id}: {provider_id} returned empty data")
                    self.record_usage(provider_id, success=False)
                    excluded_providers.append(provider_id)
                    failover_count += 1

            except Exception as e:
                response_time_ms = int((time.time() - start_time) * 1000)
                logger.error(f"ROUTER | {feature_id}: {provider_id} failed - {e}")
                self.record_usage(provider_id, success=False)
                excluded_providers.append(provider_id)
                failover_count += 1

            # Add delay between retries
            time.sleep(1)

        # All attempts failed
        return FetchResult(
            success=False,
            provider_id='NONE',
            data=None,
            error=f'All {len(providers)} providers failed after {failover_count} failovers',
            response_time_ms=0,
            failover_count=failover_count
        )

    def save_to_staging(self, feature_id: str, result: FetchResult):
        """Save fetched data to raw_staging with router lineage."""
        if not result.success or result.data is None:
            return

        df = result.data

        with self.conn.cursor() as cur:
            # Clear existing data for this feature
            cur.execute("DELETE FROM fhq_macro.raw_staging WHERE feature_id = %s", (feature_id,))

            # Prepare records with router lineage
            records = [
                (
                    feature_id,
                    row['timestamp'],
                    float(row['value_raw']),
                    'CEIO',
                    hashlib.sha256(f"{feature_id}:{row['timestamp']}:{row['value_raw']}".encode()).hexdigest()[:32],
                    result.provider_id,
                    self.router_logic_hash,
                    result.failover_count
                )
                for _, row in df.iterrows()
            ]

            execute_values(
                cur,
                """
                INSERT INTO fhq_macro.raw_staging
                (feature_id, timestamp, value_raw, ingested_by, source_response_hash,
                 provider_id, router_logic_hash, failover_count)
                VALUES %s
                """,
                records
            )

        self.conn.commit()
        logger.info(f"RAW_STAGING | {feature_id}: {len(records)} records saved via {result.provider_id}")

    def close(self):
        """Close database connection."""
        self.conn.close()


# =============================================================================
# G2.5 TACTICAL RECOVERY
# =============================================================================

def run_g2_5_recovery():
    """
    Execute G2.5 tactical recovery for blocked G2 features.

    Targets:
    - VOLATILITY: VIX_INDEX, VIX_TERM_STRUCTURE, VIX9D_INDEX, SPX_RVOL_20D, VIX_RVOL_SPREAD
    - FACTOR: DXY_INDEX, NDX_INDEX, GOLD_SPX_RATIO, COPPER_GOLD_RATIO
    - CREDIT: MOVE_INDEX
    """
    logger.info("=" * 70)
    logger.info("IoS-006 G2.5 TACTICAL RECOVERY — INITIATED")
    logger.info("Multi-Provider Canonical Router Engaged")
    logger.info("=" * 70)

    # Pending features from G2
    pending_features = [
        # VOLATILITY cluster
        'VIX_INDEX',
        'VIX9D_INDEX',
        # FACTOR cluster
        'DXY_INDEX',
        'NDX_INDEX',
        # CREDIT cluster
        'MOVE_INDEX',
    ]

    # Supporting features for calculated series
    supporting_features = [
        'SPX_RVOL_20D',      # Needs SPX data
        'GOLD_SPX_RATIO',    # Needs Gold + SPX
        'COPPER_GOLD_RATIO', # Needs Copper + Gold
        'VIX_TERM_STRUCTURE', # Needs VIX + VIX3M
        'VIX_RVOL_SPREAD',   # Needs VIX + RVOL
    ]

    router = MultiProviderRouter()
    results = {}

    try:
        # Phase 1: Fetch primary features
        logger.info("\n" + "-" * 50)
        logger.info("PHASE 1: PRIMARY FEATURES")
        logger.info("-" * 50)

        for feature_id in pending_features:
            result = router.fetch_feature(feature_id)
            results[feature_id] = result

            if result.success:
                router.save_to_staging(feature_id, result)
            else:
                logger.warning(f"FAILED | {feature_id}: {result.error}")

            time.sleep(2)  # Rate limiting between features

        # Phase 2: Fetch supporting features
        logger.info("\n" + "-" * 50)
        logger.info("PHASE 2: SUPPORTING FEATURES")
        logger.info("-" * 50)

        for feature_id in supporting_features:
            result = router.fetch_feature(feature_id)
            results[feature_id] = result

            if result.success:
                router.save_to_staging(feature_id, result)
            else:
                logger.warning(f"FAILED | {feature_id}: {result.error}")

            time.sleep(2)

        # Generate summary
        successful = [f for f, r in results.items() if r.success]
        failed = [f for f, r in results.items() if not r.success]

        logger.info("\n" + "=" * 70)
        logger.info("G2.5 TACTICAL RECOVERY — SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Features Attempted: {len(results)}")
        logger.info(f"Successful: {len(successful)}")
        logger.info(f"Failed: {len(failed)}")

        if successful:
            logger.info(f"Recovered: {', '.join(successful)}")
        if failed:
            logger.info(f"Still Pending: {', '.join(failed)}")

        return results

    finally:
        router.close()


def generate_g2_5_evidence(results: Dict[str, FetchResult], output_path: str):
    """Generate G2.5 evidence file."""
    evidence = {
        'metadata': {
            'document_type': 'IOS006_G2_5_MULTI_ROUTER',
            'generated_at': datetime.utcnow().isoformat(),
            'generated_by': 'STIG',
            'authority': 'LARS (IoS-006 Owner)',
            'adr_compliance': ['ADR-011', 'ADR-012', 'ADR-013'],
            'hash_chain_id': 'HC-IOS-006-2026',
            'router_version': ROUTER_LOGIC_VERSION
        },
        'routing_results': [],
        'provider_usage': {},
        'summary': {
            'features_attempted': len(results),
            'features_successful': 0,
            'features_failed': 0,
            'total_failovers': 0,
            'providers_used': set()
        }
    }

    for feature_id, result in results.items():
        entry = {
            'feature_id': feature_id,
            'success': result.success,
            'provider_id': result.provider_id,
            'observations': len(result.data) if result.data is not None else 0,
            'response_time_ms': result.response_time_ms,
            'failover_count': result.failover_count,
            'error': result.error
        }
        evidence['routing_results'].append(entry)

        if result.success:
            evidence['summary']['features_successful'] += 1
            evidence['summary']['providers_used'].add(result.provider_id)

            if result.provider_id not in evidence['provider_usage']:
                evidence['provider_usage'][result.provider_id] = 0
            evidence['provider_usage'][result.provider_id] += 1
        else:
            evidence['summary']['features_failed'] += 1

        evidence['summary']['total_failovers'] += result.failover_count

    evidence['summary']['providers_used'] = list(evidence['summary']['providers_used'])

    # Compute integrity hash
    evidence_str = json.dumps(evidence, sort_keys=True, default=str)
    evidence['integrity_hash'] = hashlib.sha256(evidence_str.encode()).hexdigest()

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    logger.info(f"EVIDENCE | Generated: {output_path}")
    return evidence


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    # Run tactical recovery
    results = run_g2_5_recovery()

    # Generate evidence
    timestamp = datetime.utcnow().strftime('%Y%m%d')
    evidence_path = f"evidence/IOS006_G2_5_MULTI_ROUTER_{timestamp}.json"
    generate_g2_5_evidence(results, evidence_path)
