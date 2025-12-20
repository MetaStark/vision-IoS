#!/usr/bin/env python3
"""
IoS-001 COLAB BACKFILL SCRIPT
=============================
For kjøring i Google Colab for å unngå rate limiting.

INSTRUKSJONER:
1. Kopier dette scriptet til Colab
2. Mount Google Drive for checkpoints
3. Sett DATABASE_URL eller bruk CSV-eksport
4. Kjør i batches med pauser

Rate Limiting Strategy:
- Colab IPs blir ofte rate-limited av yfinance
- Bruker lengre pauser og eksponentiell backoff
- Lagrer progress til Google Drive
- Kan resume fra checkpoint

IoS-001 Compliance:
- 500+ assets target (§2.1)
- 3+ års historie for StatArb (STIG-2025-001)
- Iron Curtain thresholds (§4.1)

Authority: STIG (CTO)
"""

# =============================================================================
# COLAB SETUP - KJØR DENNE CELLEN FØRST
# =============================================================================

COLAB_SETUP = """
# Kjør dette i første Colab-celle:

# 1. Installer dependencies
!pip install yfinance pandas psycopg2-binary python-dotenv tqdm -q

# 2. Mount Google Drive for checkpoints
from google.colab import drive
drive.mount('/content/drive')

# 3. Opprett checkpoint-mappe
!mkdir -p "/content/drive/MyDrive/FjordHQ/ios001_backfill"

# 4. Sett miljøvariabler (EDIT DISSE!)
import os
os.environ['PGHOST'] = '127.0.0.1'  # Din database host
os.environ['PGPORT'] = '54322'
os.environ['PGDATABASE'] = 'postgres'
os.environ['PGUSER'] = 'postgres'
os.environ['PGPASSWORD'] = 'postgres'

# 5. Sett checkpoint path
CHECKPOINT_DIR = "/content/drive/MyDrive/FjordHQ/ios001_backfill"
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import hashlib

# Conditional imports
try:
    import pandas as pd
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("ADVARSEL: yfinance ikke installert. Kjør: pip install yfinance pandas")

try:
    import psycopg2
    from psycopg2.extras import execute_values
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("INFO: psycopg2 ikke tilgjengelig. Bruker CSV-eksport modus.")

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False


# =============================================================================
# COLAB-OPTIMALISERT KONFIGURASJON
# =============================================================================

@dataclass
class ColabBackfillConfig:
    """Colab-optimalisert konfigurasjon med aggressive rate limits"""

    # Database (kan være tom for CSV-modus)
    PGHOST: str = os.getenv("PGHOST", "")
    PGPORT: str = os.getenv("PGPORT", "54322")
    PGDATABASE: str = os.getenv("PGDATABASE", "postgres")
    PGUSER: str = os.getenv("PGUSER", "postgres")
    PGPASSWORD: str = os.getenv("PGPASSWORD", "")

    # Rate limiting - COLAB OPTIMALISERT (mer konservativ)
    BATCH_SIZE: int = 5              # Mindre batches for Colab
    DELAY_BETWEEN_ASSETS: float = 8.0  # 8 sekunder mellom hver asset
    DELAY_BETWEEN_BATCHES: float = 180.0  # 3 minutter mellom batches
    MAX_RETRIES: int = 5
    RETRY_BASE_DELAY: float = 30.0   # Start med 30 sek retry
    RATE_LIMIT_BACKOFF: float = 600.0  # 10 minutter ved rate limit

    # Historie (STIG-2025-001: 3 år minimum for StatArb)
    MAX_HISTORY_YEARS: int = 10
    MIN_HISTORY_YEARS: int = 3       # Minimum for StatArb compliance

    # Iron Curtain thresholds (IoS-001 §4.1)
    EQUITY_FX_QUARANTINE: int = 252
    EQUITY_FX_FULL_HISTORY: int = 1260
    CRYPTO_QUARANTINE: int = 365
    CRYPTO_FULL_HISTORY: int = 1825

    # Checkpoint
    CHECKPOINT_DIR: str = "/content/drive/MyDrive/FjordHQ/ios001_backfill"

    # Asset Universe Pools (STIG-2025-001)
    POOLS: Dict = field(default_factory=lambda: {
        "A": {
            "name": "Top ETFs & Index",
            "tickers": [
                "SPY", "QQQ", "IWM", "DIA", "XLF", "XLE", "XLK", "XLV",
                "XLI", "XLU", "XLP", "XLY", "XLB", "XLRE", "XLC",
                "VTI", "VOO", "VEA", "VWO", "BND", "GLD", "SLV", "USO"
            ]
        },
        "B": {
            "name": "Mag7 + Sector Leaders",
            "tickers": [
                "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
                "JPM", "V", "MA", "JNJ", "UNH", "PG", "HD", "BAC",
                "XOM", "CVX", "PFE", "ABBV", "KO", "PEP", "MRK", "TMO",
                "COST", "WMT", "DIS", "NFLX", "ADBE", "CRM", "ORCL"
            ]
        },
        "C": {
            "name": "Crypto Top 25",
            "tickers": [
                "BTC-USD", "ETH-USD", "BNB-USD", "XRP-USD", "ADA-USD",
                "SOL-USD", "DOGE-USD", "DOT-USD", "MATIC-USD", "SHIB-USD",
                "LTC-USD", "TRX-USD", "AVAX-USD", "LINK-USD", "ATOM-USD",
                "UNI-USD", "XMR-USD", "ETC-USD", "XLM-USD", "BCH-USD",
                "ALGO-USD", "VET-USD", "FIL-USD", "ICP-USD", "AAVE-USD"
            ]
        },
        "D": {
            "name": "S&P 500 Extended",
            "tickers": [
                # Financials
                "GS", "MS", "C", "WFC", "AXP", "BLK", "SCHW", "CME",
                # Tech
                "AMD", "INTC", "QCOM", "TXN", "MU", "AMAT", "LRCX",
                # Healthcare
                "LLY", "BMY", "GILD", "AMGN", "REGN", "VRTX", "ISRG",
                # Consumer
                "MCD", "SBUX", "NKE", "TGT", "LOW", "TJX", "ORLY",
                # Industrial
                "CAT", "DE", "HON", "UPS", "RTX", "LMT", "GE",
                # Energy
                "COP", "SLB", "EOG", "PXD", "MPC", "VLO", "PSX"
            ]
        },
        "E": {
            "name": "FX Majors",
            "tickers": [
                "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X",
                "AUDUSD=X", "USDCAD=X", "NZDUSD=X",
                "EURGBP=X", "EURJPY=X", "GBPJPY=X"
            ]
        },
        "F": {
            "name": "Oslo Børs",
            "tickers": [
                "EQNR.OL", "DNB.OL", "TEL.OL", "MOWI.OL", "ORK.OL",
                "YAR.OL", "AKRBP.OL", "SALM.OL", "SUBC.OL", "FRO.OL",
                "AKER.OL", "STB.OL", "GOGL.OL", "BAKKA.OL", "KOG.OL"
            ]
        },
        "G": {
            "name": "European Majors",
            "tickers": [
                # Germany (XETRA)
                "SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE", "BAS.DE",
                "BMW.DE", "MBG.DE", "VOW3.DE", "ADS.DE", "MUV2.DE",
                # France (Paris)
                "MC.PA", "OR.PA", "SAN.PA", "AI.PA", "BNP.PA",
                "AIR.PA", "TTE.PA", "SU.PA", "CS.PA", "CAP.PA",
                # UK (London)
                "SHEL.L", "AZN.L", "HSBA.L", "BP.L", "GSK.L",
                "RIO.L", "ULVR.L", "DGE.L", "LLOY.L", "VOD.L"
            ]
        }
    })

    def get_all_tickers(self) -> List[str]:
        """Få alle tickers fra alle pools"""
        all_tickers = []
        for pool in self.POOLS.values():
            all_tickers.extend(pool["tickers"])
        return list(set(all_tickers))  # Fjern duplikater

    def get_pool_tickers(self, pool_id: str) -> List[str]:
        """Få tickers for en spesifikk pool"""
        if pool_id in self.POOLS:
            return self.POOLS[pool_id]["tickers"]
        return []


# =============================================================================
# CHECKPOINT SYSTEM
# =============================================================================

class CheckpointManager:
    """Håndterer checkpoints for å kunne resume etter disconnect"""

    def __init__(self, checkpoint_dir: str):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file = self.checkpoint_dir / "checkpoint.json"
        self.data_dir = self.checkpoint_dir / "data"
        self.data_dir.mkdir(exist_ok=True)

    def load_checkpoint(self) -> Dict:
        """Last inn checkpoint hvis den finnes"""
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file, 'r') as f:
                return json.load(f)
        return {
            "completed_tickers": [],
            "failed_tickers": [],
            "in_progress": None,
            "last_update": None
        }

    def save_checkpoint(self, checkpoint: Dict):
        """Lagre checkpoint"""
        checkpoint["last_update"] = datetime.now().isoformat()
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)

    def mark_completed(self, ticker: str, checkpoint: Dict):
        """Marker ticker som fullført"""
        if ticker not in checkpoint["completed_tickers"]:
            checkpoint["completed_tickers"].append(ticker)
        if ticker in checkpoint["failed_tickers"]:
            checkpoint["failed_tickers"].remove(ticker)
        checkpoint["in_progress"] = None
        self.save_checkpoint(checkpoint)

    def mark_failed(self, ticker: str, checkpoint: Dict, reason: str):
        """Marker ticker som feilet"""
        if ticker not in checkpoint["failed_tickers"]:
            checkpoint["failed_tickers"].append(ticker)
        checkpoint["in_progress"] = None
        self.save_checkpoint(checkpoint)

    def save_ticker_data(self, ticker: str, df: pd.DataFrame):
        """Lagre ticker data til CSV"""
        safe_ticker = ticker.replace("/", "_").replace("=", "_")
        filepath = self.data_dir / f"{safe_ticker}.csv"
        df.to_csv(filepath)
        return filepath

    def get_pending_tickers(self, all_tickers: List[str], checkpoint: Dict) -> List[str]:
        """Få liste over tickers som gjenstår"""
        completed = set(checkpoint["completed_tickers"])
        return [t for t in all_tickers if t not in completed]


# =============================================================================
# YFINANCE FETCHING MED COLAB-OPTIMALISERING
# =============================================================================

def fetch_with_backoff(
    ticker: str,
    start_date: date,
    end_date: date,
    config: ColabBackfillConfig,
    logger: logging.Logger
) -> Optional[pd.DataFrame]:
    """
    Fetch med eksponentiell backoff for Colab.

    Colab IPs blir ofte throttlet av yfinance, så vi bruker
    aggressive backoff og lengre pauser.
    """
    for attempt in range(config.MAX_RETRIES):
        try:
            # Eksponentiell backoff delay
            if attempt > 0:
                delay = config.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.info(f"  Retry {attempt + 1}/{config.MAX_RETRIES}, venter {delay:.0f}s...")
                time.sleep(delay)

            # Hent data
            df = yf.download(
                ticker,
                start=start_date.strftime('%Y-%m-%d'),
                end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                interval='1d',
                auto_adjust=False,
                progress=False,
                threads=False
            )

            if df is None or df.empty:
                logger.warning(f"  [{ticker}] Tom respons")
                continue

            # Valider data
            df = df.dropna(subset=['Close'])
            if df.empty:
                logger.warning(f"  [{ticker}] Ingen gyldige data etter cleaning")
                continue

            return df

        except Exception as e:
            error_str = str(e).lower()

            # Sjekk for rate limiting
            is_rate_limit = any(x in error_str for x in [
                "too many requests", "rate limit", "429", "throttle",
                "exceeded", "blocked"
            ])

            if is_rate_limit:
                logger.warning(f"  [{ticker}] RATE LIMITED! Venter {config.RATE_LIMIT_BACKOFF}s...")
                time.sleep(config.RATE_LIMIT_BACKOFF)
            else:
                logger.warning(f"  [{ticker}] Feil: {e}")

    return None


# =============================================================================
# HOVEDFUNKSJON
# =============================================================================

def run_colab_backfill(
    config: ColabBackfillConfig = None,
    pools: List[str] = None,
    resume: bool = True,
    export_to_db: bool = False,
    logger: logging.Logger = None
) -> Dict:
    """
    Kjør backfill i Colab med checkpoint support.

    Args:
        config: Konfigurasjon (bruker default hvis None)
        pools: Liste over pool IDs å prosessere (f.eks. ["A", "B"])
               Hvis None, prosesserer alle
        resume: Om vi skal fortsette fra forrige checkpoint
        export_to_db: Om vi skal skrive direkte til database
        logger: Logger instans

    Returns:
        Dict med resultater
    """
    if config is None:
        config = ColabBackfillConfig()

    if logger is None:
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger("colab_backfill")

    # Initialiser checkpoint manager
    checkpoint_mgr = CheckpointManager(config.CHECKPOINT_DIR)

    # Last checkpoint hvis resume
    if resume:
        checkpoint = checkpoint_mgr.load_checkpoint()
        logger.info(f"Lastet checkpoint: {len(checkpoint['completed_tickers'])} fullført, "
                   f"{len(checkpoint['failed_tickers'])} feilet")
    else:
        checkpoint = {
            "completed_tickers": [],
            "failed_tickers": [],
            "in_progress": None,
            "last_update": None
        }

    # Bestem hvilke tickers å prosessere
    if pools:
        all_tickers = []
        for pool_id in pools:
            all_tickers.extend(config.get_pool_tickers(pool_id))
        all_tickers = list(set(all_tickers))
    else:
        all_tickers = config.get_all_tickers()

    pending = checkpoint_mgr.get_pending_tickers(all_tickers, checkpoint)

    logger.info("=" * 60)
    logger.info("IoS-001 COLAB BACKFILL - STIG-2025-001")
    logger.info("=" * 60)
    logger.info(f"Total tickers: {len(all_tickers)}")
    logger.info(f"Allerede fullført: {len(checkpoint['completed_tickers'])}")
    logger.info(f"Gjenstår: {len(pending)}")
    logger.info(f"Rate limits: {config.DELAY_BETWEEN_ASSETS}s mellom assets, "
               f"{config.DELAY_BETWEEN_BATCHES}s mellom batches")
    logger.info("=" * 60)

    # Resultat tracking
    results = {
        "started_at": datetime.now().isoformat(),
        "total_tickers": len(all_tickers),
        "processed": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "total_rows": 0,
        "per_ticker": {}
    }

    # Datoer
    end_date = date.today() - timedelta(days=1)
    start_date = date.today() - timedelta(days=config.MAX_HISTORY_YEARS * 365)

    # Database connection (valgfritt)
    db_conn = None
    if export_to_db and PSYCOPG2_AVAILABLE and config.PGHOST:
        try:
            db_conn = psycopg2.connect(
                host=config.PGHOST,
                port=config.PGPORT,
                database=config.PGDATABASE,
                user=config.PGUSER,
                password=config.PGPASSWORD
            )
            logger.info("Database tilkoblet")
        except Exception as e:
            logger.warning(f"Kunne ikke koble til database: {e}")
            logger.info("Fortsetter med kun CSV-eksport")

    # Prosesser i batches
    try:
        if TQDM_AVAILABLE:
            iterator = tqdm(pending, desc="Backfill")
        else:
            iterator = pending

        batch_count = 0

        for i, ticker in enumerate(iterator):
            results["processed"] += 1
            checkpoint["in_progress"] = ticker

            try:
                logger.info(f"\n[{i+1}/{len(pending)}] Prosesserer {ticker}...")

                # Hent data
                df = fetch_with_backoff(ticker, start_date, end_date, config, logger)

                if df is None or df.empty:
                    logger.warning(f"  [{ticker}] Ingen data hentet")
                    results["failed"] += 1
                    results["per_ticker"][ticker] = {
                        "status": "FAILED",
                        "reason": "no_data"
                    }
                    checkpoint_mgr.mark_failed(ticker, checkpoint, "no_data")
                else:
                    # Lagre til CSV
                    csv_path = checkpoint_mgr.save_ticker_data(ticker, df)
                    rows = len(df)
                    results["total_rows"] += rows

                    # Bestem Iron Curtain status
                    is_crypto = ticker.endswith("-USD")
                    if is_crypto:
                        quarantine = config.CRYPTO_QUARANTINE
                        full_history = config.CRYPTO_FULL_HISTORY
                    else:
                        quarantine = config.EQUITY_FX_QUARANTINE
                        full_history = config.EQUITY_FX_FULL_HISTORY

                    if rows < quarantine:
                        status = "QUARANTINED"
                    elif rows < full_history:
                        status = "SHORT_HISTORY"
                    else:
                        status = "FULL_HISTORY"

                    logger.info(f"  [{ticker}] {rows} rader, status={status}")

                    # Lagre til database hvis tilkoblet
                    if db_conn:
                        try:
                            insert_to_db(db_conn, ticker, df)
                        except Exception as e:
                            logger.warning(f"  DB insert feil: {e}")

                    results["success"] += 1
                    results["per_ticker"][ticker] = {
                        "status": "SUCCESS",
                        "rows": rows,
                        "data_quality": status,
                        "csv_path": str(csv_path),
                        "start_date": df.index.min().strftime('%Y-%m-%d'),
                        "end_date": df.index.max().strftime('%Y-%m-%d')
                    }
                    checkpoint_mgr.mark_completed(ticker, checkpoint)

            except Exception as e:
                logger.error(f"  [{ticker}] Feil: {e}")
                results["failed"] += 1
                results["per_ticker"][ticker] = {
                    "status": "ERROR",
                    "error": str(e)
                }
                checkpoint_mgr.mark_failed(ticker, checkpoint, str(e))

            # Rate limiting
            batch_count += 1
            time.sleep(config.DELAY_BETWEEN_ASSETS)

            # Batch pause
            if batch_count >= config.BATCH_SIZE:
                batch_count = 0
                logger.info(f"\nBatch fullført. Venter {config.DELAY_BETWEEN_BATCHES}s...")
                time.sleep(config.DELAY_BETWEEN_BATCHES)

    except KeyboardInterrupt:
        logger.info("\n\nAvbrutt av bruker. Checkpoint lagret.")

    finally:
        if db_conn:
            db_conn.close()

    # Lagre endelig resultat
    results["completed_at"] = datetime.now().isoformat()
    results["checkpoint"] = {
        "completed": len(checkpoint["completed_tickers"]),
        "failed": len(checkpoint["failed_tickers"])
    }

    # Skriv resultatfil
    results_file = Path(config.CHECKPOINT_DIR) / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Oppsummering
    logger.info("\n" + "=" * 60)
    logger.info("BACKFILL FULLFØRT")
    logger.info("=" * 60)
    logger.info(f"Prosessert: {results['processed']}")
    logger.info(f"Suksess: {results['success']}")
    logger.info(f"Feilet: {results['failed']}")
    logger.info(f"Totalt rader: {results['total_rows']}")
    logger.info(f"Resultater: {results_file}")
    logger.info("=" * 60)

    return results


def insert_to_db(conn, ticker: str, df: pd.DataFrame):
    """Insert data til database"""
    insert_sql = """
        INSERT INTO fhq_data.price_series (
            listing_id, timestamp, vendor_id, frequency, price_type,
            open, high, low, close, volume, adj_close,
            source_id, is_verified
        ) VALUES %s
        ON CONFLICT (listing_id, timestamp, vendor_id) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            adj_close = EXCLUDED.adj_close
    """

    values = []
    for idx, row in df.iterrows():
        ts = idx.tz_localize(None) if hasattr(idx, 'tz_localize') and idx.tzinfo else idx
        close_val = float(row['Close']) if pd.notna(row['Close']) else None
        adj_close_val = float(row.get('Adj Close', row['Close'])) if pd.notna(row.get('Adj Close', row['Close'])) else close_val

        values.append((
            ticker,
            ts,
            'YFINANCE_COLAB',
            'DAILY',
            'RAW',
            float(row['Open']) if pd.notna(row['Open']) else None,
            float(row['High']) if pd.notna(row['High']) else None,
            float(row['Low']) if pd.notna(row['Low']) else None,
            close_val,
            int(row['Volume']) if pd.notna(row['Volume']) else None,
            adj_close_val,
            f"COLAB_BACKFILL_{datetime.now().strftime('%Y%m%d')}",
            False
        ))

    with conn.cursor() as cur:
        execute_values(cur, insert_sql, values)
    conn.commit()


# =============================================================================
# COLAB CELLE-EKSEMPLER
# =============================================================================

COLAB_CELLS = """
# ============================================================
# CELLE 1: Setup
# ============================================================
!pip install yfinance pandas tqdm -q

from google.colab import drive
drive.mount('/content/drive')

!mkdir -p "/content/drive/MyDrive/FjordHQ/ios001_backfill"

# ============================================================
# CELLE 2: Importer scriptet
# ============================================================
# Last ned scriptet fra GitHub eller kopier innholdet hit
# exec(open('colab_ios001_backfill.py').read())

# Eller bare kopier hele scriptet over og kjør denne cellen

# ============================================================
# CELLE 3: Kjør Pool A (ETFs)
# ============================================================
config = ColabBackfillConfig()
results_a = run_colab_backfill(
    config=config,
    pools=["A"],
    resume=True
)

# ============================================================
# CELLE 4: Kjør Pool B (Mag7 + Leaders)
# ============================================================
results_b = run_colab_backfill(
    config=config,
    pools=["B"],
    resume=True
)

# ============================================================
# CELLE 5: Kjør Pool C (Crypto)
# ============================================================
results_c = run_colab_backfill(
    config=config,
    pools=["C"],
    resume=True
)

# ============================================================
# CELLE 6: Generer import-script for lokal DB
# ============================================================
import pandas as pd
from pathlib import Path

checkpoint_dir = Path("/content/drive/MyDrive/FjordHQ/ios001_backfill/data")
csv_files = list(checkpoint_dir.glob("*.csv"))

print(f"Fant {len(csv_files)} CSV-filer")

# Generer SQL import statements
with open("/content/drive/MyDrive/FjordHQ/ios001_backfill/import_script.sql", "w") as f:
    f.write("-- IoS-001 Import Script\\n")
    f.write("-- Generert: " + datetime.now().isoformat() + "\\n\\n")

    for csv_file in csv_files:
        ticker = csv_file.stem
        f.write(f"-- Import {ticker}\\n")
        f.write(f"\\\\copy fhq_data.price_series FROM '{csv_file}' WITH CSV HEADER;\\n\\n")

print("Import script generert!")
"""


# =============================================================================
# LOKAL TESTING / CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="IoS-001 Colab Backfill")
    parser.add_argument("--pools", type=str, nargs="+", help="Pool IDs (A, B, C, etc.)")
    parser.add_argument("--no-resume", action="store_true", help="Start fra scratch")
    parser.add_argument("--checkpoint-dir", type=str, default="./ios001_checkpoint")
    parser.add_argument("--list-pools", action="store_true", help="List alle pools")

    args = parser.parse_args()

    config = ColabBackfillConfig()
    config.CHECKPOINT_DIR = args.checkpoint_dir

    if args.list_pools:
        print("\nTilgjengelige Pools:")
        print("-" * 40)
        for pool_id, pool in config.POOLS.items():
            print(f"  {pool_id}: {pool['name']} ({len(pool['tickers'])} tickers)")
        print()
        sys.exit(0)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )
    logger = logging.getLogger("colab_backfill")

    results = run_colab_backfill(
        config=config,
        pools=args.pools,
        resume=not args.no_resume,
        logger=logger
    )
