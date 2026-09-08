"""
IoS-006 G2 Macro Ingest & Canonicalization Engine
=================================================
Authority: LARS (Owner IoS-006) + STIG (Technical)
Phase: G2 DATA ACQUISITION
ADR Compliance: ADR-002, ADR-011, ADR-012, ADR-013

Mission: "Bring the World to FjordHQ."

This module implements:
1. CEIO Ingestion Protocol - FRED + Yahoo Finance API integration
2. STIG Canonicalization Protocol - Lag alignment, gap handling, hash governance
3. Stationarity Gate - ADF testing with transformation cascade
4. Evidence Generation - G2 compliance artifacts
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import warnings

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values, Json
from dotenv import load_dotenv

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('IoS-006-G2')

# Load environment
load_dotenv()

# CEO-DIR-2026-020 D2: Mandatory Evidence Attachment
try:
    from mandatory_evidence_contract import attach_evidence, MissingEvidenceViolation
    EVIDENCE_CONTRACT_ENABLED = True
except ImportError:
    EVIDENCE_CONTRACT_ENABLED = False

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class FeatureConfig:
    """Configuration for a macro feature."""
    feature_id: str
    provenance: str
    source_ticker: str
    frequency: str
    lag_period_days: int
    stationarity_method: str
    cluster: str


# Feature mapping: feature_id -> (provenance, source_ticker)
# PRIORITY: FRED first (free, reliable, no rate limits), then Yahoo as fallback
FEATURE_MAP = {
    # Cluster A: LIQUIDITY
    'US_M2_YOY': ('FRED', 'M2SL'),
    'FED_TOTAL_ASSETS': ('FRED', 'WALCL'),
    'US_TGA_BALANCE': ('FRED', 'WTREGEN'),
    'FED_RRP_BALANCE': ('FRED', 'RRPONTSYD'),
    'US_NET_LIQUIDITY': ('CALCULATED', 'NET_LIQ_V1'),
    'GLOBAL_M2_USD': ('CALCULATED', 'GLOBAL_M2_V1'),

    # Cluster B: CREDIT
    'US_HY_SPREAD': ('FRED', 'BAMLH0A0HYM2'),
    'US_IG_SPREAD': ('FRED', 'BAMLC0A0CM'),
    'US_YIELD_CURVE_10Y2Y': ('FRED', 'T10Y2Y'),
    'MOVE_INDEX': ('YAHOO', '^MOVE'),  # Not on FRED
    'TED_SPREAD': ('FRED', 'TEDRATE'),
    'US_FED_FUNDS_RATE': ('FRED', 'FEDFUNDS'),

    # Cluster C: VOLATILITY - Use FRED where available
    'VIX_INDEX': ('FRED', 'VIXCLS'),  # FRED has VIX daily close
    'VIX_TERM_STRUCTURE': ('CALCULATED', 'VIX_TERM_V1'),
    'VIX9D_INDEX': ('YAHOO', '^VIX9D'),  # Not on FRED
    'SPX_RVOL_20D': ('CALCULATED', 'SPX_RVOL_20D_V1'),
    'VIX_RVOL_SPREAD': ('CALCULATED', 'VIX_RVOL_SPREAD_V1'),

    # Cluster D: FACTOR - Use FRED where available
    'DXY_INDEX': ('FRED', 'DTWEXBGS'),  # FRED Trade Weighted USD Index (Broad)
    'US_10Y_REAL_RATE': ('FRED', 'DFII10'),
    'NDX_INDEX': ('YAHOO', '^NDX'),  # Not on FRED
    'GOLD_SPX_RATIO': ('CALCULATED', 'GOLD_SPX_V1'),
    'COPPER_GOLD_RATIO': ('CALCULATED', 'COPPER_GOLD_V1'),
}

# Tickers needed for calculated features
SUPPORTING_TICKERS = {
    'YAHOO': ['^GSPC', 'GC=F', 'HG=F', '^VIX3M'],  # SPX, Gold, Copper, VIX3M
}

# ADF significance threshold
ADF_THRESHOLD = 0.05

# Minimum history requirement (years)
MIN_HISTORY_YEARS = 10

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




def check_feature_freshness(conn, feature_id: str, max_staleness_days: int = 2) -> bool:
    """Check if a feature has recent data and can be skipped.
    
    Returns True if feature is FRESH (can skip), False if STALE (needs update).
    """
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT MAX(timestamp)::date as latest_date,
                       CURRENT_DATE - MAX(timestamp)::date as days_behind
                FROM fhq_macro.canonical_series
                WHERE feature_id = %s
            """, (feature_id,))
            row = cur.fetchone()
            
            if row and row[0] is not None:
                days_behind = row[1] or 0
                if days_behind <= max_staleness_days:
                    logger.info(f"FRESHNESS | {feature_id}: FRESH ({days_behind}d old) - SKIP")
                    return True
                else:
                    logger.info(f"FRESHNESS | {feature_id}: STALE ({days_behind}d old) - FETCH")
                    return False
            else:
                logger.info(f"FRESHNESS | {feature_id}: NO DATA - FETCH")
                return False
    except Exception as e:
        logger.warning(f"FRESHNESS | {feature_id}: Check failed ({e}) - FETCH")
        return False

# =============================================================================
# CEIO INGESTION PROTOCOL
# =============================================================================

class CEIOIngestionEngine:
    """
    CEIO Ingestion Protocol Implementation.

    Connects to FRED and Yahoo Finance APIs to fetch historical macro data.
    Adheres to ADR-012 API Waterfall (FRED/Yahoo = Tier 1 Lake = FREE).
    """

    def __init__(self, conn=None, incremental: bool = True):
        self.fred_api_key = os.getenv('FRED_API_KEY')
        self.ingestion_timestamp = datetime.utcnow()
        self.raw_data: Dict[str, pd.DataFrame] = {}
        self.errors: List[Dict] = []
        self.conn = conn
        self.incremental = incremental

    def ingest_fred_series(self, ticker: str, feature_id: str) -> Optional[pd.DataFrame]:
        """Fetch a series from FRED."""
        try:
            from fredapi import Fred

            if not self.fred_api_key:
                logger.warning(f"FRED API key not set. Using pandas_datareader fallback for {ticker}")
                return self._fred_fallback(ticker, feature_id)

            fred = Fred(api_key=self.fred_api_key)

            # Fetch full history
            series = fred.get_series(ticker)

            if series is None or len(series) == 0:
                logger.error(f"FRED returned empty series for {ticker}")
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

            logger.info(f"FRED | {feature_id} ({ticker}): {len(df)} observations, "
                       f"{df['timestamp'].min().date()} to {df['timestamp'].max().date()}")

            return df

        except ImportError:
            logger.warning("fredapi not installed. Using fallback.")
            return self._fred_fallback(ticker, feature_id)
        except Exception as e:
            logger.error(f"FRED ingestion failed for {ticker}: {e}")
            self.errors.append({
                'feature_id': feature_id,
                'source': 'FRED',
                'ticker': ticker,
                'error': str(e)
            })
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
            logger.error(f"FRED fallback failed for {ticker}: {e}")
            return None

    def ingest_yahoo_series(self, ticker: str, feature_id: str, retry_count: int = 3) -> Optional[pd.DataFrame]:
        """Fetch a series from Yahoo Finance with rate limiting."""
        import time

        for attempt in range(retry_count):
            try:
                import yfinance as yf

                # Add delay to avoid rate limiting (longer delay on retries)
                time.sleep(2 + attempt * 3)

                # Fetch maximum history
                data = yf.download(ticker, period='max', progress=False, timeout=30)

                if data is None or len(data) == 0:
                    if attempt < retry_count - 1:
                        logger.warning(f"Yahoo returned empty data for {ticker}, retry {attempt + 1}/{retry_count}")
                        continue
                    logger.error(f"Yahoo returned empty data for {ticker} after {retry_count} attempts")
                    return None

                # Use adjusted close for price series, close for indices
                value_col = 'Adj Close' if 'Adj Close' in data.columns else 'Close'

                df = pd.DataFrame({
                    'timestamp': data.index,
                    'value_raw': data[value_col].values,
                    'feature_id': feature_id,
                    'provenance': 'YAHOO',
                    'source_ticker': ticker
                })

                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.dropna(subset=['value_raw'])

                logger.info(f"YAHOO | {feature_id} ({ticker}): {len(df)} observations, "
                           f"{df['timestamp'].min().date()} to {df['timestamp'].max().date()}")

                return df

            except Exception as e:
                if 'Rate' in str(e) and attempt < retry_count - 1:
                    logger.warning(f"Yahoo rate limited for {ticker}, retry {attempt + 1}/{retry_count}")
                    time.sleep(5 + attempt * 5)  # Back off on rate limit
                    continue
                logger.error(f"Yahoo ingestion failed for {ticker}: {e}")
                self.errors.append({
                    'feature_id': feature_id,
                    'source': 'YAHOO',
                    'ticker': ticker,
                    'error': str(e)
                })
                return None

        return None

    def ingest_supporting_data(self) -> Dict[str, pd.DataFrame]:
        """Fetch supporting data needed for calculated features."""
        supporting_data = {}

        for source, tickers in SUPPORTING_TICKERS.items():
            for ticker in tickers:
                if source == 'YAHOO':
                    df = self.ingest_yahoo_series(ticker, f'_SUPPORT_{ticker}')
                    if df is not None:
                        supporting_data[ticker] = df

        return supporting_data

    def calculate_derived_features(self, supporting_data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Calculate derived/composite features."""
        calculated = {}

        # US_NET_LIQUIDITY = FED_TOTAL_ASSETS - US_TGA_BALANCE - FED_RRP_BALANCE
        if all(k in self.raw_data for k in ['FED_TOTAL_ASSETS', 'US_TGA_BALANCE', 'FED_RRP_BALANCE']):
            try:
                fed = self.raw_data['FED_TOTAL_ASSETS'].set_index('timestamp')['value_raw']
                tga = self.raw_data['US_TGA_BALANCE'].set_index('timestamp')['value_raw']
                rrp = self.raw_data['FED_RRP_BALANCE'].set_index('timestamp')['value_raw']

                # Align and compute
                aligned = pd.DataFrame({'fed': fed, 'tga': tga, 'rrp': rrp})
                aligned = aligned.ffill().dropna()
                net_liq = aligned['fed'] - aligned['tga'] - aligned['rrp']

                calculated['US_NET_LIQUIDITY'] = pd.DataFrame({
                    'timestamp': net_liq.index,
                    'value_raw': net_liq.values,
                    'feature_id': 'US_NET_LIQUIDITY',
                    'provenance': 'CALCULATED',
                    'source_ticker': 'NET_LIQ_V1'
                })
                logger.info(f"CALCULATED | US_NET_LIQUIDITY: {len(calculated['US_NET_LIQUIDITY'])} observations")
            except Exception as e:
                logger.error(f"Failed to calculate US_NET_LIQUIDITY: {e}")

        # VIX_TERM_STRUCTURE = VIX - VIX3M (if VIX3M available)
        if 'VIX_INDEX' in self.raw_data and '^VIX3M' in supporting_data:
            try:
                vix = self.raw_data['VIX_INDEX'].set_index('timestamp')['value_raw']
                vix3m = supporting_data['^VIX3M'].set_index('timestamp')['value_raw']

                aligned = pd.DataFrame({'vix': vix, 'vix3m': vix3m}).dropna()
                term_struct = aligned['vix'] - aligned['vix3m']

                calculated['VIX_TERM_STRUCTURE'] = pd.DataFrame({
                    'timestamp': term_struct.index,
                    'value_raw': term_struct.values,
                    'feature_id': 'VIX_TERM_STRUCTURE',
                    'provenance': 'CALCULATED',
                    'source_ticker': 'VIX_TERM_V1'
                })
                logger.info(f"CALCULATED | VIX_TERM_STRUCTURE: {len(calculated['VIX_TERM_STRUCTURE'])} observations")
            except Exception as e:
                logger.error(f"Failed to calculate VIX_TERM_STRUCTURE: {e}")

        # SPX_RVOL_20D = 20-day rolling std of SPX returns, annualized
        if '^GSPC' in supporting_data:
            try:
                spx = supporting_data['^GSPC'].set_index('timestamp')['value_raw']
                returns = spx.pct_change().dropna()
                rvol = returns.rolling(20).std() * np.sqrt(252) * 100
                rvol = rvol.dropna()

                calculated['SPX_RVOL_20D'] = pd.DataFrame({
                    'timestamp': rvol.index,
                    'value_raw': rvol.values,
                    'feature_id': 'SPX_RVOL_20D',
                    'provenance': 'CALCULATED',
                    'source_ticker': 'SPX_RVOL_20D_V1'
                })
                logger.info(f"CALCULATED | SPX_RVOL_20D: {len(calculated['SPX_RVOL_20D'])} observations")
            except Exception as e:
                logger.error(f"Failed to calculate SPX_RVOL_20D: {e}")

        # VIX_RVOL_SPREAD = VIX - SPX_RVOL_20D
        if 'VIX_INDEX' in self.raw_data and 'SPX_RVOL_20D' in calculated:
            try:
                vix = self.raw_data['VIX_INDEX'].set_index('timestamp')['value_raw']
                rvol = calculated['SPX_RVOL_20D'].set_index('timestamp')['value_raw']

                aligned = pd.DataFrame({'vix': vix, 'rvol': rvol}).dropna()
                spread = aligned['vix'] - aligned['rvol']

                calculated['VIX_RVOL_SPREAD'] = pd.DataFrame({
                    'timestamp': spread.index,
                    'value_raw': spread.values,
                    'feature_id': 'VIX_RVOL_SPREAD',
                    'provenance': 'CALCULATED',
                    'source_ticker': 'VIX_RVOL_SPREAD_V1'
                })
                logger.info(f"CALCULATED | VIX_RVOL_SPREAD: {len(calculated['VIX_RVOL_SPREAD'])} observations")
            except Exception as e:
                logger.error(f"Failed to calculate VIX_RVOL_SPREAD: {e}")

        # GOLD_SPX_RATIO = Gold / SPX
        if 'GC=F' in supporting_data and '^GSPC' in supporting_data:
            try:
                gold = supporting_data['GC=F'].set_index('timestamp')['value_raw']
                spx = supporting_data['^GSPC'].set_index('timestamp')['value_raw']

                aligned = pd.DataFrame({'gold': gold, 'spx': spx}).dropna()
                ratio = aligned['gold'] / aligned['spx']

                calculated['GOLD_SPX_RATIO'] = pd.DataFrame({
                    'timestamp': ratio.index,
                    'value_raw': ratio.values,
                    'feature_id': 'GOLD_SPX_RATIO',
                    'provenance': 'CALCULATED',
                    'source_ticker': 'GOLD_SPX_V1'
                })
                logger.info(f"CALCULATED | GOLD_SPX_RATIO: {len(calculated['GOLD_SPX_RATIO'])} observations")
            except Exception as e:
                logger.error(f"Failed to calculate GOLD_SPX_RATIO: {e}")

        # COPPER_GOLD_RATIO = Copper / Gold
        if 'HG=F' in supporting_data and 'GC=F' in supporting_data:
            try:
                copper = supporting_data['HG=F'].set_index('timestamp')['value_raw']
                gold = supporting_data['GC=F'].set_index('timestamp')['value_raw']

                aligned = pd.DataFrame({'copper': copper, 'gold': gold}).dropna()
                ratio = aligned['copper'] / aligned['gold']

                calculated['COPPER_GOLD_RATIO'] = pd.DataFrame({
                    'timestamp': ratio.index,
                    'value_raw': ratio.values,
                    'feature_id': 'COPPER_GOLD_RATIO',
                    'provenance': 'CALCULATED',
                    'source_ticker': 'COPPER_GOLD_V1'
                })
                logger.info(f"CALCULATED | COPPER_GOLD_RATIO: {len(calculated['COPPER_GOLD_RATIO'])} observations")
            except Exception as e:
                logger.error(f"Failed to calculate COPPER_GOLD_RATIO: {e}")

        # GLOBAL_M2_USD - simplified: use US M2 as proxy (full implementation requires ECB, BOJ, PBOC data)
        if 'US_M2_YOY' in self.raw_data:
            # For now, use US M2 as base; full global M2 requires additional data sources
            calculated['GLOBAL_M2_USD'] = self.raw_data['US_M2_YOY'].copy()
            calculated['GLOBAL_M2_USD']['feature_id'] = 'GLOBAL_M2_USD'
            calculated['GLOBAL_M2_USD']['source_ticker'] = 'GLOBAL_M2_V1'
            logger.info(f"CALCULATED | GLOBAL_M2_USD: Using US M2 as proxy (full global M2 requires additional sources)")

        return calculated

    # =========================================================================
    # CEO-DIR-2026-120 P2.1: FAMA-FRENCH FACTOR INTEGRATION
    # =========================================================================

    def ingest_fama_french_factors(self) -> Optional[pd.DataFrame]:
        """
        Ingest Fama-French 5-Factor Model data from Kenneth French Data Library.

        CEO-DIR-2026-120 P2.1: Factor-based weighting methodology for IoS-013.

        Factors:
        - MKT_RF: Market Risk Premium (Rm - Rf)
        - SMB: Small Minus Big (size factor)
        - HML: High Minus Low (value factor)
        - RMW: Robust Minus Weak (profitability factor)
        - CMA: Conservative Minus Aggressive (investment factor)
        - RF: Risk-Free Rate
        - MOM: Momentum factor (optional, from separate file)

        Returns:
            DataFrame with daily factor returns, or None if ingestion fails
        """
        import io
        import zipfile
        import urllib.request

        # Kenneth French Data Library URLs
        FF5_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
        MOM_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip"

        logger.info("FAMA-FRENCH | Fetching 5-Factor data from Kenneth French Data Library...")

        try:
            # Fetch and extract 5-Factor data
            ff5_df = self._fetch_french_csv(FF5_URL, 'F-F_Research_Data_5_Factors_2x3_daily')

            if ff5_df is None or len(ff5_df) == 0:
                logger.error("FAMA-FRENCH | Failed to fetch 5-Factor data")
                return None

            logger.info(f"FAMA-FRENCH | 5-Factor data: {len(ff5_df)} observations, "
                       f"{ff5_df.index.min()} to {ff5_df.index.max()}")

            # Try to fetch Momentum factor
            try:
                mom_df = self._fetch_french_csv(MOM_URL, 'F-F_Momentum_Factor_daily')
                if mom_df is not None and len(mom_df) > 0:
                    # Merge momentum with 5-factor data
                    ff5_df = ff5_df.join(mom_df, how='left')
                    logger.info(f"FAMA-FRENCH | Momentum factor merged: {len(mom_df)} observations")
            except Exception as mom_err:
                logger.warning(f"FAMA-FRENCH | Could not fetch Momentum factor: {mom_err}")
                ff5_df['Mom'] = None  # Add empty momentum column

            # Standardize column names
            column_map = {
                'Mkt-RF': 'mkt_rf',
                'SMB': 'smb',
                'HML': 'hml',
                'RMW': 'rmw',
                'CMA': 'cma',
                'RF': 'rf',
                'Mom': 'mom'
            }
            ff5_df = ff5_df.rename(columns=column_map)

            # Convert from percentage to decimal (French data is in percentage)
            for col in ['mkt_rf', 'smb', 'hml', 'rmw', 'cma', 'rf', 'mom']:
                if col in ff5_df.columns:
                    ff5_df[col] = ff5_df[col] / 100.0

            # Add date column from index
            ff5_df = ff5_df.reset_index()
            ff5_df = ff5_df.rename(columns={'index': 'date'})

            logger.info(f"FAMA-FRENCH | Ingestion complete: {len(ff5_df)} daily factor returns")

            return ff5_df

        except Exception as e:
            logger.error(f"FAMA-FRENCH | Ingestion failed: {e}")
            self.errors.append({
                'feature_id': 'FAMA_FRENCH_5F',
                'source': 'FRENCH_DATA_LIBRARY',
                'error': str(e)
            })
            return None

    def _fetch_french_csv(self, url: str, filename_prefix: str) -> Optional[pd.DataFrame]:
        """Fetch and parse a CSV from Kenneth French Data Library ZIP file."""
        import io
        import zipfile
        import urllib.request

        try:
            # Download ZIP file
            with urllib.request.urlopen(url, timeout=30) as response:
                zip_data = io.BytesIO(response.read())

            # Extract CSV from ZIP
            with zipfile.ZipFile(zip_data, 'r') as zf:
                # Find the CSV file
                csv_name = None
                for name in zf.namelist():
                    if name.endswith('.CSV') or name.endswith('.csv'):
                        csv_name = name
                        break

                if csv_name is None:
                    logger.error(f"FAMA-FRENCH | No CSV found in {url}")
                    return None

                with zf.open(csv_name) as f:
                    # Read and parse CSV
                    # French data has header rows we need to skip
                    lines = f.read().decode('utf-8').splitlines()

                    # Find where data starts (after header text)
                    data_start = 0
                    for i, line in enumerate(lines):
                        if line.strip() and line[0].isdigit():
                            data_start = i
                            break

                    # Find where data ends (before annual data or footer)
                    data_end = len(lines)
                    for i in range(data_start + 1, len(lines)):
                        line = lines[i].strip()
                        if not line or (not line[0].isdigit() and ',' not in line):
                            # Check if it's annual data section
                            if 'Annual' in line or not line:
                                data_end = i
                                break

                    # Get header row (one row before data)
                    header_line = lines[data_start - 1] if data_start > 0 else lines[0]

                    # Parse data
                    csv_text = header_line + '\n' + '\n'.join(lines[data_start:data_end])
                    df = pd.read_csv(io.StringIO(csv_text))

                    # First column is date
                    date_col = df.columns[0]
                    df[date_col] = pd.to_datetime(df[date_col].astype(str), format='%Y%m%d', errors='coerce')
                    df = df.dropna(subset=[date_col])
                    df = df.set_index(date_col)

                    # Drop any non-numeric columns
                    numeric_cols = df.select_dtypes(include=[np.number]).columns
                    df = df[numeric_cols]

                    return df

        except Exception as e:
            logger.error(f"FAMA-FRENCH | Failed to fetch {url}: {e}")
            return None

    def save_fama_french_to_database(self, ff_df: pd.DataFrame) -> int:
        """
        Save Fama-French factor data to database.

        CEO-DIR-2026-120 P2.1: Persist to fhq_research.fama_french_factors
        """
        if ff_df is None or len(ff_df) == 0:
            return 0

        if self.conn is None:
            logger.warning("FAMA-FRENCH | No database connection, skipping save")
            return 0

        try:
            rows_inserted = 0
            with self.conn.cursor() as cur:
                # Use upsert to handle duplicates
                for _, row in ff_df.iterrows():
                    cur.execute("""
                        INSERT INTO fhq_research.fama_french_factors (
                            date, mkt_rf, smb, hml, rmw, cma, rf, mom, source, ingested_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (date) DO UPDATE SET
                            mkt_rf = EXCLUDED.mkt_rf,
                            smb = EXCLUDED.smb,
                            hml = EXCLUDED.hml,
                            rmw = EXCLUDED.rmw,
                            cma = EXCLUDED.cma,
                            rf = EXCLUDED.rf,
                            mom = EXCLUDED.mom,
                            ingested_at = NOW()
                    """, (
                        row['date'],
                        row.get('mkt_rf'),
                        row.get('smb'),
                        row.get('hml'),
                        row.get('rmw'),
                        row.get('cma'),
                        row.get('rf'),
                        row.get('mom'),
                        'FRENCH_DATA_LIBRARY'
                    ))
                    rows_inserted += 1

                self.conn.commit()
                logger.info(f"FAMA-FRENCH | Saved {rows_inserted} rows to database")

            return rows_inserted

        except Exception as e:
            logger.error(f"FAMA-FRENCH | Database save failed: {e}")
            self.conn.rollback()
            return 0

    def run_ingestion(self) -> Dict[str, pd.DataFrame]:
        """Execute full ingestion pipeline."""
        logger.info("=" * 60)
        logger.info("CEIO INGESTION PROTOCOL - INITIATED")
        logger.info("=" * 60)

        # Fetch primary features (with incremental freshness check)
        skipped_count = 0
        for feature_id, (provenance, ticker) in FEATURE_MAP.items():
            # Check freshness if incremental mode and we have a connection
            if self.incremental and self.conn and provenance != 'CALCULATED':
                if check_feature_freshness(self.conn, feature_id, max_staleness_days=2):
                    skipped_count += 1
                    continue
            
            if provenance == 'FRED':
                df = self.ingest_fred_series(ticker, feature_id)
                if df is not None:
                    self.raw_data[feature_id] = df
            elif provenance == 'YAHOO':
                df = self.ingest_yahoo_series(ticker, feature_id)
                if df is not None:
                    self.raw_data[feature_id] = df
            # CALCULATED features are handled separately
        
        if skipped_count > 0:
            logger.info(f"FRESHNESS | Skipped {skipped_count} fresh features")

        # Fetch supporting data
        logger.info("-" * 40)
        logger.info("Fetching supporting data for calculated features...")
        supporting_data = self.ingest_supporting_data()

        # Calculate derived features
        logger.info("-" * 40)
        logger.info("Computing calculated features...")
        calculated = self.calculate_derived_features(supporting_data)

        # Merge calculated into raw_data
        self.raw_data.update(calculated)

        logger.info("=" * 60)
        logger.info(f"CEIO INGESTION COMPLETE: {len(self.raw_data)} features ingested")
        logger.info(f"Errors encountered: {len(self.errors)}")
        logger.info("=" * 60)

        return self.raw_data


# =============================================================================
# STIG CANONICALIZATION PROTOCOL
# =============================================================================

class STIGCanonicalizationEngine:
    """
    STIG Canonicalization Protocol Implementation.

    Transforms raw staging data into canonical series with:
    - Lag alignment (publication date adjustment)
    - Gap handling (deterministic forward-fill policy)
    - Hash governance (ADR-011 compliance)
    """

    def __init__(self, conn):
        self.conn = conn
        self.canonicalization_timestamp = datetime.utcnow()

    def get_feature_config(self, feature_id: str) -> Optional[Dict]:
        """Fetch feature configuration from registry."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT feature_id, lag_period_days, frequency, stationarity_method
                FROM fhq_macro.feature_registry
                WHERE feature_id = %s
            """, (feature_id,))
            row = cur.fetchone()
            if row:
                return {
                    'feature_id': row[0],
                    'lag_period_days': row[1],
                    'frequency': row[2],
                    'stationarity_method': row[3]
                }
        return None

    def apply_lag_alignment(self, df: pd.DataFrame, lag_days: int) -> pd.DataFrame:
        """
        Apply lag alignment to prevent look-ahead bias.

        The effective_date is shifted forward by lag_days to reflect
        when the data was actually available for trading decisions.
        """
        df = df.copy()
        df['publication_date'] = df['timestamp']
        df['effective_date'] = df['timestamp'] + timedelta(days=lag_days)
        return df

    def handle_gaps(self, df: pd.DataFrame, frequency: str) -> Tuple[pd.DataFrame, Dict]:
        """
        Handle data gaps with deterministic forward-fill policy.

        Returns:
            - DataFrame with gaps filled
            - Gap report dictionary
        """
        df = df.copy().sort_values('timestamp')

        # Determine expected frequency
        freq_map = {
            'DAILY': 'B',      # Business days
            'WEEKLY': 'W',
            'MONTHLY': 'MS',   # Month start
            'QUARTERLY': 'QS',
            'ANNUAL': 'AS'
        }

        gap_report = {
            'original_count': len(df),
            'gaps_filled': 0,
            'fill_method': 'FORWARD_FILL',
            'max_gap_days': 0
        }

        if frequency in freq_map:
            # Create expected date range
            date_range = pd.date_range(
                start=df['timestamp'].min(),
                end=df['timestamp'].max(),
                freq=freq_map[frequency]
            )

            # Reindex and forward-fill
            df_indexed = df.set_index('timestamp')
            df_reindexed = df_indexed.reindex(date_range)

            # Calculate gaps before filling
            gaps = df_reindexed['value_raw'].isna()
            gap_report['gaps_filled'] = gaps.sum()

            if gap_report['gaps_filled'] > 0:
                # Find max gap length
                gap_groups = (~gaps).cumsum()[gaps]
                if len(gap_groups) > 0:
                    gap_lengths = gap_groups.value_counts()
                    gap_report['max_gap_days'] = int(gap_lengths.max())

            # Forward fill
            df_reindexed = df_reindexed.ffill()
            df_reindexed = df_reindexed.reset_index()
            df_reindexed.columns = ['timestamp'] + list(df_indexed.columns)

            return df_reindexed.dropna(subset=['value_raw']), gap_report

        return df, gap_report

    def compute_data_hash(self, df: pd.DataFrame) -> str:
        """Compute SHA-256 hash of data for ADR-011 compliance."""
        # Create deterministic string representation
        data_str = df[['timestamp', 'value_raw']].to_json(date_format='iso')
        return hashlib.sha256(data_str.encode()).hexdigest()

    def canonicalize_feature(self, feature_id: str, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """
        Canonicalize a single feature.

        Returns:
            - Canonicalized DataFrame
            - Canonicalization report
        """
        config = self.get_feature_config(feature_id)
        if not config:
            logger.error(f"Feature {feature_id} not found in registry")
            return None, {'error': 'Feature not registered'}

        report = {
            'feature_id': feature_id,
            'raw_count': len(df),
            'lag_applied_days': config['lag_period_days'],
            'frequency': config['frequency']
        }

        # Apply lag alignment
        df = self.apply_lag_alignment(df, config['lag_period_days'])

        # Handle gaps
        df, gap_report = self.handle_gaps(df, config['frequency'])
        report.update(gap_report)

        # Compute data hash
        report['data_hash'] = self.compute_data_hash(df)

        # Add canonicalization metadata
        df['canonicalized_at'] = self.canonicalization_timestamp
        df['canonicalized_by'] = 'STIG'
        df['data_hash'] = report['data_hash']

        report['canonical_count'] = len(df)
        report['start_date'] = df['timestamp'].min().isoformat()
        report['end_date'] = df['timestamp'].max().isoformat()

        logger.info(f"CANONICALIZED | {feature_id}: {report['raw_count']} → {report['canonical_count']} "
                   f"(gaps filled: {report['gaps_filled']}, lag: {report['lag_applied_days']}d)")

        return df, report


# =============================================================================
# STATIONARITY GATE (P-HACKING FIREWALL)
# =============================================================================

class StationarityGate:
    """
    Stationarity Gate Implementation.

    The P-Hacking Firewall: Only stationary data may pass to IoS-005.

    Transformation cascade:
    1. LEVEL (no transform)
    2. DIFF (first difference)
    3. LOG_DIFF (log returns)
    4. SECOND_DIFF (second difference)

    If no transformation achieves p < 0.05, feature is REJECTED.
    """

    TRANSFORMATION_CASCADE = ['NONE', 'DIFF', 'LOG_DIFF', 'SECOND_DIFF']

    def __init__(self, conn):
        self.conn = conn
        self.test_results: List[Dict] = []

    def run_adf_test(self, series: pd.Series) -> Dict:
        """Run Augmented Dickey-Fuller test."""
        try:
            from statsmodels.tsa.stattools import adfuller

            # Remove NaN and infinite values
            clean_series = series.replace([np.inf, -np.inf], np.nan).dropna()

            if len(clean_series) < 20:
                return {
                    'statistic': None,
                    'p_value': 1.0,
                    'is_stationary': False,
                    'error': 'Insufficient observations'
                }

            result = adfuller(clean_series, autolag='AIC')

            return {
                'statistic': float(result[0]),
                'p_value': float(result[1]),
                'critical_1pct': float(result[4]['1%']),
                'critical_5pct': float(result[4]['5%']),
                'critical_10pct': float(result[4]['10%']),
                'n_observations': len(clean_series),
                'is_stationary': result[1] < ADF_THRESHOLD
            }

        except Exception as e:
            logger.error(f"ADF test failed: {e}")
            return {
                'statistic': None,
                'p_value': 1.0,
                'is_stationary': False,
                'error': str(e)
            }

    def apply_transformation(self, series: pd.Series, method: str) -> pd.Series:
        """Apply stationarity transformation."""
        if method == 'NONE':
            return series
        elif method == 'DIFF':
            return series.diff().dropna()
        elif method == 'LOG_DIFF':
            # Handle negative values
            if (series <= 0).any():
                # Shift to positive domain
                shifted = series - series.min() + 1
                return np.log(shifted).diff().dropna()
            return np.log(series).diff().dropna()
        elif method == 'SECOND_DIFF':
            return series.diff().diff().dropna()
        elif method == 'PCT_CHANGE':
            return series.pct_change().dropna()
        elif method == 'Z_SCORE':
            return (series - series.mean()) / series.std()
        else:
            return series

    def test_feature(self, feature_id: str, df: pd.DataFrame) -> Dict:
        """
        Test a feature for stationarity with transformation cascade.

        Returns:
            Dict with test results and final transformation
        """
        series = df.set_index('timestamp')['value_raw']

        result = {
            'feature_id': feature_id,
            'sample_start': df['timestamp'].min().date().isoformat(),
            'sample_end': df['timestamp'].max().date().isoformat(),
            'n_observations': len(df),
            'tests': [],
            'final_transformation': None,
            'final_p_value': None,
            'is_stationary': False,
            'status': 'REJECTED'
        }

        # Test each transformation in cascade
        for transform in self.TRANSFORMATION_CASCADE:
            transformed_series = self.apply_transformation(series, transform)
            adf_result = self.run_adf_test(transformed_series)

            test_record = {
                'transformation': transform,
                **adf_result
            }
            result['tests'].append(test_record)

            logger.debug(f"{feature_id} | {transform}: p={adf_result['p_value']:.4f}, "
                        f"stationary={adf_result['is_stationary']}")

            if adf_result['is_stationary']:
                result['final_transformation'] = transform
                result['final_p_value'] = adf_result['p_value']
                result['is_stationary'] = True
                result['status'] = 'CANDIDATE'  # Ready for IoS-005 testing

                logger.info(f"STATIONARITY GATE | {feature_id}: PASS "
                           f"(transform={transform}, p={adf_result['p_value']:.4f})")
                break

        if not result['is_stationary']:
            logger.warning(f"STATIONARITY GATE | {feature_id}: REJECTED "
                          f"(no transformation achieved p < {ADF_THRESHOLD})")

        self.test_results.append(result)
        return result

    def save_test_results(self, feature_id: str, result: Dict):
        """Save stationarity test results to database."""
        with self.conn.cursor() as cur:
            for test in result['tests']:
                if test.get('statistic') is not None:
                    cur.execute("""
                        INSERT INTO fhq_macro.stationarity_tests (
                            feature_id, test_type, sample_start, sample_end, n_observations,
                            test_statistic, p_value, critical_value_1pct, critical_value_5pct,
                            critical_value_10pct, is_stationary, transformation_required,
                            post_transform_stationary, tested_by
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        feature_id,
                        'ADF',
                        result['sample_start'],
                        result['sample_end'],
                        int(test.get('n_observations', result['n_observations'])),
                        float(test['statistic']),
                        float(test['p_value']),
                        float(test['critical_1pct']) if test.get('critical_1pct') else None,
                        float(test['critical_5pct']) if test.get('critical_5pct') else None,
                        float(test['critical_10pct']) if test.get('critical_10pct') else None,
                        bool(test['is_stationary']),
                        test['transformation'] if not test['is_stationary'] else None,
                        bool(result['is_stationary']),
                        'STIG'
                    ))

            # Update feature registry with stationarity results
            if result['is_stationary']:
                cur.execute("""
                    UPDATE fhq_macro.feature_registry
                    SET is_stationary = TRUE,
                        stationarity_method = %s,
                        adf_p_value = %s,
                        adf_test_date = NOW(),
                        updated_at = NOW()
                    WHERE feature_id = %s
                """, (result['final_transformation'], float(result['final_p_value']), feature_id))
            else:
                cur.execute("""
                    UPDATE fhq_macro.feature_registry
                    SET is_stationary = FALSE,
                        status = 'REJECTED',
                        adf_test_date = NOW(),
                        updated_at = NOW()
                    WHERE feature_id = %s
                """, (feature_id,))

        self.conn.commit()


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def save_to_raw_staging(conn, feature_id: str, df: pd.DataFrame):
    """Save ingested data to raw_staging table."""
    with conn.cursor() as cur:
        # Clear existing data for this feature
        cur.execute("DELETE FROM fhq_macro.raw_staging WHERE feature_id = %s", (feature_id,))

        # Prepare data for insertion
        records = [
            (
                feature_id,
                row['timestamp'],
                float(row['value_raw']),
                'CEIO',
                hashlib.sha256(f"{feature_id}:{row['timestamp']}:{row['value_raw']}".encode()).hexdigest()[:32]
            )
            for _, row in df.iterrows()
        ]

        execute_values(
            cur,
            """
            INSERT INTO fhq_macro.raw_staging
            (feature_id, timestamp, value_raw, ingested_by, source_response_hash)
            VALUES %s
            """,
            records
        )

    conn.commit()
    logger.info(f"RAW_STAGING | {feature_id}: {len(records)} records saved")


def save_to_canonical_series(conn, feature_id: str, df: pd.DataFrame, transform: str = None):
    """Save canonicalized data to canonical_series table."""
    with conn.cursor() as cur:
        # Clear existing data for this feature
        cur.execute("DELETE FROM fhq_macro.canonical_series WHERE feature_id = %s", (feature_id,))

        # Apply transformation if specified
        if transform and transform != 'NONE':
            gate = StationarityGate(conn)
            series = df.set_index('timestamp')['value_raw']
            transformed = gate.apply_transformation(series, transform)
            df = df.copy()
            df = df[df['timestamp'].isin(transformed.index)]
            df['value_transformed'] = transformed.values
            df['transformation_method'] = transform
        else:
            df['value_transformed'] = df['value_raw']
            df['transformation_method'] = 'NONE'

        # Prepare data for insertion
        records = [
            (
                feature_id,
                row['timestamp'],
                float(row['value_raw']),
                float(row['value_transformed']) if pd.notna(row['value_transformed']) else None,
                row['transformation_method'],
                row.get('publication_date', row['timestamp']),
                row.get('effective_date', row['timestamp']),
                row.get('data_hash', hashlib.sha256(f"{feature_id}:{row['timestamp']}".encode()).hexdigest()),
                'STIG'
            )
            for _, row in df.iterrows()
            if pd.notna(row['value_raw'])
        ]

        execute_values(
            cur,
            """
            INSERT INTO fhq_macro.canonical_series
            (feature_id, timestamp, value_raw, value_transformed, transformation_method,
             publication_date, effective_date, data_hash, canonicalized_by)
            VALUES %s
            """,
            records
        )

    conn.commit()
    logger.info(f"CANONICAL_SERIES | {feature_id}: {len(records)} records saved (transform={transform})")


# =============================================================================
# EVIDENCE GENERATION
# =============================================================================

def generate_g2_evidence(
    ingestion_results: Dict,
    canonicalization_reports: List[Dict],
    stationarity_results: List[Dict],
    output_path: str
):
    """Generate G2 compliance evidence file."""

    evidence = {
        'metadata': {
            'document_type': 'IOS006_G2_DATA_INGEST',
            'generated_at': datetime.utcnow().isoformat(),
            'generated_by': 'STIG',
            'authority': 'LARS (IoS-006 Owner)',
            'adr_compliance': ['ADR-002', 'ADR-011', 'ADR-012', 'ADR-013'],
            'hash_chain_id': 'HC-IOS-006-2026'
        },
        'coverage_map': {},
        'stationarity_audit': [],
        'rejection_log': [],
        'summary': {
            'total_features': 0,
            'features_ingested': 0,
            'features_stationary': 0,
            'features_rejected': 0,
            'total_observations': 0
        }
    }

    # Build coverage map
    for report in canonicalization_reports:
        feature_id = report['feature_id']
        evidence['coverage_map'][feature_id] = {
            'start_date': report.get('start_date'),
            'end_date': report.get('end_date'),
            'observations': report.get('canonical_count', 0),
            'gaps_filled': report.get('gaps_filled', 0),
            'lag_days': report.get('lag_applied_days', 0),
            'data_hash': report.get('data_hash')
        }
        evidence['summary']['total_observations'] += report.get('canonical_count', 0)

    # Build stationarity audit
    for result in stationarity_results:
        feature_id = result['feature_id']

        audit_entry = {
            'feature_id': feature_id,
            'is_stationary': result['is_stationary'],
            'transformation': result.get('final_transformation'),
            'p_value': result.get('final_p_value'),
            'tests_run': len(result.get('tests', []))
        }
        evidence['stationarity_audit'].append(audit_entry)

        if result['is_stationary']:
            evidence['summary']['features_stationary'] += 1
        else:
            evidence['rejection_log'].append({
                'feature_id': feature_id,
                'reason': 'STATIONARITY_FAILED',
                'details': f"No transformation achieved p < {ADF_THRESHOLD}"
            })
            evidence['summary']['features_rejected'] += 1

    evidence['summary']['total_features'] = len(FEATURE_MAP)
    evidence['summary']['features_ingested'] = len(canonicalization_reports)

    # Compute evidence hash
    evidence_str = json.dumps(evidence, sort_keys=True, default=str)
    evidence['integrity_hash'] = hashlib.sha256(evidence_str.encode()).hexdigest()

    # Save evidence file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    logger.info(f"EVIDENCE | Generated: {output_path}")
    logger.info(f"EVIDENCE | Hash: {evidence['integrity_hash'][:16]}...")

    return evidence


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_g2_pipeline():
    """Execute the full G2 pipeline."""
    logger.info("=" * 70)
    logger.info("IoS-006 G2 PIPELINE — INITIATED")
    logger.info("Mission: Bring the World to FjordHQ")
    logger.info("=" * 70)

    conn = get_db_connection()

    try:
        # Phase 1: CEIO Ingestion
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 1: CEIO INGESTION PROTOCOL")
        logger.info("=" * 70)

        ceio = CEIOIngestionEngine(conn=conn, incremental=True)
        raw_data = ceio.run_ingestion()

        # Phase 2: Save to raw_staging
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 2: RAW STAGING")
        logger.info("=" * 70)

        for feature_id, df in raw_data.items():
            if not feature_id.startswith('_SUPPORT_'):
                save_to_raw_staging(conn, feature_id, df)

        # Phase 3: STIG Canonicalization
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 3: STIG CANONICALIZATION PROTOCOL")
        logger.info("=" * 70)

        canonicalizer = STIGCanonicalizationEngine(conn)
        canonicalization_reports = []

        for feature_id, df in raw_data.items():
            if not feature_id.startswith('_SUPPORT_'):
                canonical_df, report = canonicalizer.canonicalize_feature(feature_id, df)
                if canonical_df is not None:
                    canonicalization_reports.append(report)
                    raw_data[feature_id] = canonical_df  # Update with canonicalized data

        # Phase 4: Stationarity Gate
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 4: STATIONARITY GATE (P-HACKING FIREWALL)")
        logger.info("=" * 70)

        gate = StationarityGate(conn)
        stationarity_results = []

        for feature_id, df in raw_data.items():
            if not feature_id.startswith('_SUPPORT_'):
                result = gate.test_feature(feature_id, df)
                stationarity_results.append(result)
                gate.save_test_results(feature_id, result)

                # Save to canonical_series with appropriate transformation
                if result['is_stationary']:
                    save_to_canonical_series(conn, feature_id, df, result['final_transformation'])

        # Phase 5: Evidence Generation
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 5: EVIDENCE GENERATION")
        logger.info("=" * 70)

        timestamp = datetime.utcnow().strftime('%Y%m%d')
        evidence_path = f"evidence/IOS006_G2_DATA_INGEST_{timestamp}.json"

        evidence = generate_g2_evidence(
            raw_data,
            canonicalization_reports,
            stationarity_results,
            evidence_path
        )

        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("G2 PIPELINE — COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Features Ingested: {evidence['summary']['features_ingested']}/{evidence['summary']['total_features']}")
        logger.info(f"Features Stationary: {evidence['summary']['features_stationary']}")
        logger.info(f"Features Rejected: {evidence['summary']['features_rejected']}")
        logger.info(f"Total Observations: {evidence['summary']['total_observations']:,}")
        logger.info(f"Evidence File: {evidence_path}")
        logger.info("=" * 70)

        # CEO-DIR-2026-020 D2: Attach court-proof evidence to ledger
        if EVIDENCE_CONTRACT_ENABLED:
            try:
                raw_query = """
                SELECT feature_id, timestamp, value_raw, value_transformed, transformation_method
                FROM fhq_macro.canonical_series
                WHERE timestamp > NOW() - INTERVAL '7 days'
                ORDER BY timestamp DESC
                -- G2 macro ingest evidence query
                """
                summary_id = f"G2-INGEST-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                evidence_result = attach_evidence(
                    conn=conn,
                    summary_id=summary_id,
                    summary_type='G2_INGEST_SUMMARY',
                    generating_agent='CEIO',
                    raw_query=raw_query,
                    query_result=evidence,
                    summary_content={
                        'features_ingested': evidence['summary']['features_ingested'],
                        'features_stationary': evidence['summary']['features_stationary'],
                        'features_rejected': evidence['summary']['features_rejected'],
                        'total_observations': evidence['summary']['total_observations'],
                        'evidence_file': evidence_path,
                        'integrity_hash': evidence['integrity_hash'][:32]
                    },
                    evidence_sources=['FRED', 'YAHOO', 'fhq_macro.canonical_series']
                )
                logger.info(f"[EVIDENCE-D2] G2 ingest evidence attached: {evidence_result['evidence_id']}")
            except Exception as e:
                logger.error(f"[EVIDENCE-D2] Failed to attach G2 evidence: {e}")

        return evidence

    except Exception as e:
        logger.error(f"G2 Pipeline failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run_g2_pipeline()
