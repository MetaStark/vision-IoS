#!/usr/bin/env python3
"""
IoS-001 ALPACA PRICE INGEST - Multi-Timeframe
==============================================

Authority:
- IoS-001 Market Truth (G4_CONSTITUTIONAL)
- ADR-006 VEGA Governance & Attestation
- ADR-012 API Waterfall (Tier 3 - Sniper)
- ADR-013 Infrastructure Sovereignty

Executor: LINE (EC-004) under STIG (CTO) supervision
VEGA Attestation: Required for all ingested data

Timeframes per ADR-001:
- 1m (minute) - Alpaca only
- 1h (hour) - Alpaca
- 1d (daily) - Alpaca

Asset Coverage: US Equities & Crypto via Alpaca

Usage:
    python ios001_alpaca_price_ingest.py --timeframe 1d --asset-class EQUITY
    python ios001_alpaca_price_ingest.py --timeframe 1h --asset-class CRYPTO
    python ios001_alpaca_price_ingest.py --timeframe 1m --symbols AAPL,MSFT,NVDA
    python ios001_alpaca_price_ingest.py --dry-run
"""

import os
import sys
import json
import hashlib
import logging
import argparse
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import uuid

import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# ALPACA SDK
# =============================================================================

try:
    from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.data.enums import DataFeed  # CEO-DIR-2026-119: Use IEX feed for free tier
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    print("WARNING: alpaca-py not installed. Run: pip install alpaca-py")

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', 54322)),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}

# Alpaca credentials (per .env file)
ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.environ.get('ALPACA_SECRET', '') or os.environ.get('ALPACA_SECRET_KEY', '')

# Rate limiting
BATCH_SIZE = 50
BATCH_DELAY_SECONDS = 1

# Paths
EVIDENCE_DIR = Path(__file__).parent / "evidence"
EVIDENCE_DIR.mkdir(exist_ok=True)

# Timeframe mapping
TIMEFRAME_MAP = {
    '1m': TimeFrame(1, TimeFrameUnit.Minute) if ALPACA_AVAILABLE else None,
    '1h': TimeFrame(1, TimeFrameUnit.Hour) if ALPACA_AVAILABLE else None,
    '1d': TimeFrame(1, TimeFrameUnit.Day) if ALPACA_AVAILABLE else None,
}

# Resolution mapping for database
RESOLUTION_MAP = {
    '1m': '1m',
    '1h': '1h',
    '1d': '1d',
}

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(EVIDENCE_DIR / f"ios001_alpaca_ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger("IOS001_ALPACA")


def get_connection():
    return psycopg2.connect(**DB_CONFIG, options='-c client_encoding=UTF8')


# =============================================================================
# VEGA ATTESTATION (ADR-006)
# =============================================================================

@dataclass
class VEGAAttestation:
    """VEGA attestation record per ADR-006."""
    attestation_id: str
    ios_id: str
    data_source: str
    asset_count: int
    record_count: int
    timeframe: str
    data_hash: str
    attestation_timestamp: datetime
    executor: str
    governance_status: str

    def to_dict(self) -> Dict:
        return {
            'attestation_id': self.attestation_id,
            'ios_id': self.ios_id,
            'data_source': self.data_source,
            'asset_count': self.asset_count,
            'record_count': self.record_count,
            'timeframe': self.timeframe,
            'data_hash': self.data_hash,
            'attestation_timestamp': self.attestation_timestamp.isoformat(),
            'executor': self.executor,
            'governance_status': self.governance_status
        }


def compute_data_hash(df: pd.DataFrame) -> str:
    """Compute SHA-256 hash of dataframe for attestation."""
    data_str = df.to_csv(index=True)
    return hashlib.sha256(data_str.encode()).hexdigest()[:32]


def create_vega_attestation(
    conn,
    data_source: str,
    asset_count: int,
    record_count: int,
    timeframe: str,
    data_hash: str
) -> VEGAAttestation:
    """Create and store VEGA attestation per ADR-006."""

    attestation = VEGAAttestation(
        attestation_id=str(uuid.uuid4()),
        ios_id='IOS-001',
        data_source=data_source,
        asset_count=asset_count,
        record_count=record_count,
        timeframe=timeframe,
        data_hash=data_hash,
        attestation_timestamp=datetime.now(timezone.utc),
        executor='LINE',
        governance_status='G4_CONSTITUTIONAL'
    )

    # Store attestation - CEO-DIR-2026-119: Updated to match existing schema
    attestation_data = {
        'ios_id': attestation.ios_id,
        'data_source': attestation.data_source,
        'asset_count': attestation.asset_count,
        'record_count': attestation.record_count,
        'timeframe': attestation.timeframe,
        'data_hash': attestation.data_hash,
        'executor': attestation.executor
    }

    # Generate signature hash for VEGA (placeholder until proper signing implemented)
    signature_data = f"{attestation.attestation_id}|{attestation.ios_id}|{attestation.data_hash}"
    vega_signature = hashlib.sha256(signature_data.encode()).hexdigest()
    vega_public_key = 'VEGA_LINE_INGEST_KEY_001'  # Placeholder key identifier

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.vega_attestations (
                attestation_id, target_type, target_id, attestation_type,
                attestation_status, attestation_timestamp, attestation_data,
                adr_reference, constitutional_basis, vega_signature, vega_public_key, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (attestation_id) DO NOTHING
        """, (
            attestation.attestation_id,
            'DATA_INGEST',  # target_type
            attestation.ios_id,  # target_id
            'IOS001_PRICE_INGEST',  # attestation_type
            attestation.governance_status,  # attestation_status
            attestation.attestation_timestamp,
            json.dumps(attestation_data),  # attestation_data
            'ADR-006',  # adr_reference
            'G4_CONSTITUTIONAL',  # constitutional_basis
            vega_signature,  # vega_signature
            vega_public_key  # vega_public_key
        ))
    conn.commit()

    logger.info(f"VEGA Attestation created: {attestation.attestation_id}")
    return attestation


def verify_vega_attestation_table(conn) -> bool:
    """Verify VEGA attestation table exists, create if not."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'fhq_governance'
                AND table_name = 'vega_attestations'
            )
        """)
        exists = cur.fetchone()[0]

        if not exists:
            logger.info("Creating VEGA attestations table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fhq_governance.vega_attestations (
                    attestation_id UUID PRIMARY KEY,
                    ios_id VARCHAR(20) NOT NULL,
                    data_source VARCHAR(50) NOT NULL,
                    asset_count INTEGER NOT NULL,
                    record_count INTEGER NOT NULL,
                    timeframe VARCHAR(10) NOT NULL,
                    data_hash VARCHAR(64) NOT NULL,
                    attestation_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    executor VARCHAR(20) NOT NULL,
                    governance_status VARCHAR(30) NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            conn.commit()
            return True
    return True


# =============================================================================
# ASSET UNIVERSE
# =============================================================================

def get_alpaca_eligible_assets(conn, asset_class: Optional[str] = None) -> List[Dict]:
    """
    Get assets eligible for Alpaca data fetch.
    Only US equities and crypto are supported by Alpaca.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get assets that are active and have proper exchange codes
        query = """
            SELECT DISTINCT
                a.canonical_id,
                a.ticker,
                a.symbol,
                a.asset_class,
                a.exchange_mic
            FROM fhq_meta.assets a
            WHERE a.active_flag = true
        """

        if asset_class == 'EQUITY':
            # US equities only (Alpaca supports US markets)
            query += """
                AND a.asset_class = 'EQUITY'
                AND (a.exchange_mic IN ('XNYS', 'XNAS', 'ARCX', 'BATS')
                     OR a.ticker NOT LIKE '%.%')
            """
        elif asset_class == 'CRYPTO':
            query += " AND a.asset_class = 'CRYPTO'"
        else:
            # Default: both
            query += """
                AND (
                    (a.asset_class = 'EQUITY' AND (a.exchange_mic IN ('XNYS', 'XNAS', 'ARCX', 'BATS') OR a.ticker NOT LIKE '%.%'))
                    OR a.asset_class = 'CRYPTO'
                )
            """

        query += " ORDER BY a.asset_class, a.canonical_id LIMIT 200"  # Limit for rate limits

        cur.execute(query)
        return cur.fetchall()


def get_alpaca_symbol(asset: Dict) -> str:
    """Convert canonical_id to Alpaca symbol format."""
    canonical = asset['canonical_id']
    asset_class = asset['asset_class']

    if asset_class == 'CRYPTO':
        # Alpaca crypto format: BTC/USD
        if '-USD' in canonical:
            return canonical.replace('-USD', '/USD')
        return canonical
    else:
        # Equities: just the ticker
        ticker = asset.get('ticker') or canonical
        # Remove exchange suffixes for US stocks
        if '.' in ticker:
            parts = ticker.split('.')
            if parts[1] in ['OL', 'DE', 'PA', 'L']:
                return None  # Not US, skip
        # CEO-DIR-2026-119: Fix share class symbols (BRK-B -> BRK.B)
        # Alpaca uses period notation for share classes
        if '-' in ticker and ticker.split('-')[1] in ['A', 'B', 'C']:
            ticker = ticker.replace('-', '.')
        return ticker


# =============================================================================
# DATA FETCHING
# =============================================================================

class AlpacaPriceIngester:
    """IoS-001 compliant Alpaca price ingester with VEGA attestation."""

    def __init__(self, dry_run: bool = False):
        self.conn = get_connection()
        self.dry_run = dry_run
        self.stock_client = None
        self.crypto_client = None

        # Verify VEGA attestation table
        verify_vega_attestation_table(self.conn)

        # Initialize Alpaca clients
        if ALPACA_AVAILABLE and ALPACA_API_KEY:
            self.stock_client = StockHistoricalDataClient(
                api_key=ALPACA_API_KEY,
                secret_key=ALPACA_SECRET_KEY
            )
            self.crypto_client = CryptoHistoricalDataClient(
                api_key=ALPACA_API_KEY,
                secret_key=ALPACA_SECRET_KEY
            )
            logger.info("Alpaca clients initialized")
        else:
            logger.error("Alpaca credentials not configured!")
            raise RuntimeError("ALPACA_API_KEY and ALPACA_SECRET_KEY required")

        # Results tracking
        self.results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'executor': 'LINE',
            'supervisor': 'STIG',
            'dry_run': dry_run,
            'assets_processed': 0,
            'records_ingested': 0,
            'errors': [],
            'attestation_id': None
        }

    def fetch_stock_bars(
        self,
        symbols: List[str],
        timeframe: str,
        start: datetime,
        end: datetime
    ) -> pd.DataFrame:
        """Fetch stock bars from Alpaca."""
        if not self.stock_client:
            return pd.DataFrame()

        tf = TIMEFRAME_MAP.get(timeframe)
        if not tf:
            raise ValueError(f"Invalid timeframe: {timeframe}")

        # CEO-DIR-2026-119: Use IEX feed (free tier compatible)
        # SIP feed requires paid subscription
        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=tf,
            start=start,
            end=end,
            feed=DataFeed.IEX  # Free tier: use IEX instead of SIP
        )

        bars = self.stock_client.get_stock_bars(request)

        # Convert to DataFrame
        records = []
        for symbol, bar_list in bars.data.items():
            for bar in bar_list:
                records.append({
                    'symbol': symbol,
                    'timestamp': bar.timestamp,
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': int(bar.volume),
                    'vwap': float(bar.vwap) if bar.vwap else None
                })

        return pd.DataFrame(records)

    def fetch_crypto_bars(
        self,
        symbols: List[str],
        timeframe: str,
        start: datetime,
        end: datetime
    ) -> pd.DataFrame:
        """Fetch crypto bars from Alpaca."""
        if not self.crypto_client:
            return pd.DataFrame()

        tf = TIMEFRAME_MAP.get(timeframe)
        if not tf:
            raise ValueError(f"Invalid timeframe: {timeframe}")

        request = CryptoBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=tf,
            start=start,
            end=end
        )

        bars = self.crypto_client.get_crypto_bars(request)

        # Convert to DataFrame
        records = []
        for symbol, bar_list in bars.data.items():
            for bar in bar_list:
                records.append({
                    'symbol': symbol,
                    'timestamp': bar.timestamp,
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': float(bar.volume),
                    'vwap': float(bar.vwap) if bar.vwap else None
                })

        return pd.DataFrame(records)

    def store_prices(
        self,
        df: pd.DataFrame,
        timeframe: str,
        asset_class: str
    ) -> int:
        """
        Store prices in fhq_market.prices with IoS-001 compliance.
        CEO-DIR-2026-119: Changed from fhq_data.price_series to fhq_market.prices
        to align with ios001_daily_ingest.py approach using canonical_id.
        """
        if df.empty:
            return 0

        # Map Alpaca symbols to canonical_ids
        symbol_to_canonical = {}
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            for symbol in df['symbol'].unique():
                # Convert Alpaca symbol format back to canonical
                # BTC/USD -> BTC-USD, BRK.B -> BRK-B
                lookup_symbol = symbol.replace('/', '-').replace('.', '-')

                cur.execute("""
                    SELECT canonical_id
                    FROM fhq_meta.assets
                    WHERE canonical_id = %s
                       OR ticker = %s
                       OR ticker = %s
                    LIMIT 1
                """, (lookup_symbol, symbol, lookup_symbol))
                row = cur.fetchone()
                if row:
                    symbol_to_canonical[symbol] = row['canonical_id']

        # Prepare records for insertion
        records = []
        batch_id = str(uuid.uuid4())

        for _, row in df.iterrows():
            canonical_id = symbol_to_canonical.get(row['symbol'])
            if not canonical_id:
                continue

            # Convert timestamp
            ts = row['timestamp']
            if hasattr(ts, 'tz_localize'):
                try:
                    ts = ts.tz_localize(None)
                except:
                    pass

            # Data hash
            data_str = f"{canonical_id}|{ts}|{row['open']}|{row['high']}|{row['low']}|{row['close']}|{row['volume']}"
            data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]

            records.append((
                str(uuid.uuid4()),  # id
                str(uuid.uuid4()),  # asset_id
                canonical_id,
                ts,
                float(row['open']),
                float(row['high']),
                float(row['low']),
                float(row['close']),
                float(row['volume']),
                'alpaca',           # source
                None,               # staging_id
                data_hash,
                False,              # gap_filled
                False,              # interpolated
                1.0,                # quality_score
                batch_id,
                'LINE',             # canonicalized_by
                float(row['close']) # adj_close
            ))

        if not records:
            return 0

        if self.dry_run:
            logger.info(f"  [DRY RUN] Would insert {len(records)} records")
            return len(records)

        # Insert with upsert into fhq_market.prices (CEO-DIR-2026-119)
        try:
            with self.conn.cursor() as cur:
                execute_values(cur, """
                    INSERT INTO fhq_market.prices (
                        id, asset_id, canonical_id, timestamp, open, high, low, close, volume,
                        source, staging_id, data_hash, gap_filled, interpolated, quality_score,
                        batch_id, canonicalized_by, adj_close
                    ) VALUES %s
                    ON CONFLICT (canonical_id, timestamp) DO UPDATE SET
                        adj_close = EXCLUDED.adj_close,
                        data_hash = EXCLUDED.data_hash
                    WHERE fhq_market.prices.adj_close IS NULL
                """, records)
            self.conn.commit()
            return len(records)
        except Exception as e:
            self.conn.rollback()
            logger.error(f"  Insert error: {e}")
            return 0

    def run(
        self,
        timeframe: str = '1d',
        asset_class: Optional[str] = None,
        symbols: Optional[List[str]] = None,
        lookback_days: int = 5
    ) -> Dict:
        """
        Run the price ingest pipeline with VEGA attestation.

        Args:
            timeframe: '1m', '1h', or '1d'
            asset_class: 'EQUITY', 'CRYPTO', or None for both
            symbols: Optional list of specific symbols
            lookback_days: Days to look back for data
        """
        logger.info("=" * 70)
        logger.info("IoS-001 ALPACA PRICE INGEST")
        logger.info("=" * 70)
        logger.info(f"Executor: LINE (EC-004)")
        logger.info(f"Supervisor: STIG (CTO)")
        logger.info(f"Authority: IoS-001 G4_CONSTITUTIONAL")
        logger.info(f"Timeframe: {timeframe}")
        logger.info(f"Asset Class: {asset_class or 'ALL'}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info("=" * 70)

        # Time range
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=lookback_days)

        all_data = pd.DataFrame()
        total_records = 0

        # Get eligible assets or use provided symbols
        if symbols:
            # Direct symbol list
            stock_symbols = [s for s in symbols if '/' not in s and '-USD' not in s]
            crypto_symbols = [s for s in symbols if '/' in s or '-USD' in s]
        else:
            assets = get_alpaca_eligible_assets(self.conn, asset_class)
            logger.info(f"Found {len(assets)} eligible assets")

            stock_symbols = []
            crypto_symbols = []

            for asset in assets:
                alpaca_sym = get_alpaca_symbol(asset)
                if not alpaca_sym:
                    continue
                if asset['asset_class'] == 'CRYPTO':
                    crypto_symbols.append(alpaca_sym)
                else:
                    stock_symbols.append(alpaca_sym)

        # Fetch stock data
        if stock_symbols and (asset_class in [None, 'EQUITY']):
            logger.info(f"\nFetching {len(stock_symbols)} US equities...")

            # Batch to avoid rate limits
            for i in range(0, len(stock_symbols), BATCH_SIZE):
                batch = stock_symbols[i:i+BATCH_SIZE]
                logger.info(f"  Batch {i//BATCH_SIZE + 1}: {len(batch)} symbols")

                try:
                    df = self.fetch_stock_bars(batch, timeframe, start, end)
                    if not df.empty:
                        records = self.store_prices(df, timeframe, 'EQUITY')
                        total_records += records
                        all_data = pd.concat([all_data, df], ignore_index=True)
                        logger.info(f"    Stored {records} records")
                except Exception as e:
                    error_msg = f"Stock batch error: {str(e)[:100]}"
                    logger.error(f"    {error_msg}")
                    self.results['errors'].append(error_msg)

        # Fetch crypto data
        if crypto_symbols and (asset_class in [None, 'CRYPTO']):
            logger.info(f"\nFetching {len(crypto_symbols)} crypto assets...")

            for i in range(0, len(crypto_symbols), BATCH_SIZE):
                batch = crypto_symbols[i:i+BATCH_SIZE]
                logger.info(f"  Batch {i//BATCH_SIZE + 1}: {len(batch)} symbols")

                try:
                    df = self.fetch_crypto_bars(batch, timeframe, start, end)
                    if not df.empty:
                        records = self.store_prices(df, timeframe, 'CRYPTO')
                        total_records += records
                        all_data = pd.concat([all_data, df], ignore_index=True)
                        logger.info(f"    Stored {records} records")
                except Exception as e:
                    error_msg = f"Crypto batch error: {str(e)[:100]}"
                    logger.error(f"    {error_msg}")
                    self.results['errors'].append(error_msg)

        # Create VEGA attestation
        if not self.dry_run and total_records > 0:
            data_hash = compute_data_hash(all_data) if not all_data.empty else "empty"
            attestation = create_vega_attestation(
                self.conn,
                data_source='ALPACA',
                asset_count=len(stock_symbols) + len(crypto_symbols),
                record_count=total_records,
                timeframe=timeframe,
                data_hash=data_hash
            )
            self.results['attestation_id'] = attestation.attestation_id

        # Update results
        self.results['assets_processed'] = len(stock_symbols) + len(crypto_symbols)
        self.results['records_ingested'] = total_records

        # Save evidence
        evidence_file = EVIDENCE_DIR / f"ios001_alpaca_ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(evidence_file, 'w') as f:
            json.dump(self.results, f, indent=2)

        logger.info("\n" + "=" * 70)
        logger.info(f"Assets Processed: {self.results['assets_processed']}")
        logger.info(f"Records Ingested: {self.results['records_ingested']}")
        logger.info(f"VEGA Attestation: {self.results['attestation_id']}")
        logger.info(f"Errors: {len(self.results['errors'])}")
        logger.info("=" * 70)

        return self.results

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='IoS-001 Alpaca Price Ingest with VEGA Attestation'
    )
    parser.add_argument(
        '--timeframe', '-t',
        choices=['1m', '1h', '1d'],
        default='1d',
        help='Timeframe (default: 1d)'
    )
    parser.add_argument(
        '--asset-class', '-a',
        choices=['EQUITY', 'CRYPTO'],
        help='Asset class filter'
    )
    parser.add_argument(
        '--symbols', '-s',
        help='Comma-separated list of symbols (e.g., AAPL,MSFT,BTC/USD)'
    )
    parser.add_argument(
        '--lookback', '-l',
        type=int,
        default=5,
        help='Lookback days (default: 5)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run (no database writes)'
    )
    parser.add_argument(
        '--trigger-regime',
        action='store_true',
        help='Trigger regime update after ingest'
    )

    args = parser.parse_args()

    # Parse symbols
    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',')]

    # Run ingester
    ingester = AlpacaPriceIngester(dry_run=args.dry_run)

    try:
        results = ingester.run(
            timeframe=args.timeframe,
            asset_class=args.asset_class,
            symbols=symbols,
            lookback_days=args.lookback
        )

        # Trigger regime update if requested
        if args.trigger_regime and results['records_ingested'] > 0:
            logger.info("\nTriggering IoS-003 regime update...")
            import subprocess
            subprocess.run([
                sys.executable,
                str(Path(__file__).parent / 'ios003_daily_regime_update_v4.py')
            ], check=False)

    finally:
        ingester.close()


if __name__ == '__main__':
    main()
