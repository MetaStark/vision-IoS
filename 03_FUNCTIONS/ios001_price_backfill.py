#!/usr/bin/env python3
"""
IoS-001 PRICE BACKFILL PIPELINE
================================
CEO ORDER: Activate PRICE INGESTION PIPELINE for all 352 assets.

Requirements:
- Daily price series ingest (close/adj_close/volume)
- Backfill to max available history
- Recalculate valid_row_count
- Auto-update data_quality_status based on thresholds:
  - < 252 (Equities/FX) or < 365 (Crypto) → QUARANTINED
  - >= 252/365 but < 1260/1825 → SHORT_HISTORY
  - >= 1260/1825 (5 years) → FULL_HISTORY

Rate-Limit Protection (CEO Directive):
- Batches of 20 tickers
- 3-second pause between individual fetches
- 60-second pause between batches
- Retry logic on API errors

Authority: STIG (CTO) per EC-003
ADR References: ADR-012 (API Waterfall), ADR-013 (Canonical)
IoS Reference: IoS-001 §4.1 (Iron Curtain Rule)
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

import pandas as pd
import yfinance as yf
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Load environment
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class BackfillConfig:
    """Backfill configuration per CEO directive"""
    # Database
    PGHOST: str = os.getenv("PGHOST", "127.0.0.1")
    PGPORT: str = os.getenv("PGPORT", "54322")
    PGDATABASE: str = os.getenv("PGDATABASE", "postgres")
    PGUSER: str = os.getenv("PGUSER", "postgres")
    PGPASSWORD: str = os.getenv("PGPASSWORD", "postgres")

    # Rate limiting (CEO directive) - Conservative settings
    BATCH_SIZE: int = 10  # Smaller batches
    DELAY_BETWEEN_ASSETS: float = 5.0  # seconds - longer delay
    DELAY_BETWEEN_BATCHES: float = 120.0  # seconds - 2 minute pause
    MAX_RETRIES: int = 5
    RETRY_DELAY: float = 60.0  # seconds - wait longer on failure
    RATE_LIMIT_BACKOFF: float = 300.0  # 5 minutes when rate limited

    # History depth
    MAX_HISTORY_YEARS: int = 10  # Fetch up to 10 years

    # Iron Curtain thresholds (IoS-001 §4.1)
    EQUITY_FX_QUARANTINE: int = 252
    EQUITY_FX_FULL_HISTORY: int = 1260
    CRYPTO_QUARANTINE: int = 365
    CRYPTO_FULL_HISTORY: int = 1825

    # Paths
    EVIDENCE_DIR: Path = field(default_factory=lambda: Path(__file__).parent / "evidence")

    def __post_init__(self):
        self.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    def get_connection_string(self) -> str:
        return f"host={self.PGHOST} port={self.PGPORT} dbname={self.PGDATABASE} user={self.PGUSER} password={self.PGPASSWORD}"


# =============================================================================
# LOGGING
# =============================================================================

def setup_logging() -> logging.Logger:
    """Configure logging"""
    logger = logging.getLogger("ios001_backfill")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console.setFormatter(formatter)
        logger.addHandler(console)

    return logger


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

class DatabaseManager:
    """Database connection and operations"""

    def __init__(self, config: BackfillConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.conn = None

    def connect(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(self.config.get_connection_string())
        self.logger.info("Database connection established")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.logger.info("Database connection closed")

    def get_all_assets(self) -> List[Dict]:
        """Get all active assets with exchange info for ticker construction"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT
                    a.canonical_id,
                    a.ticker,
                    a.exchange_mic,
                    a.asset_class,
                    a.currency,
                    a.quarantine_threshold,
                    a.full_history_threshold,
                    COALESCE(e.yahoo_suffix, '') as yahoo_suffix
                FROM fhq_meta.assets a
                LEFT JOIN fhq_meta.exchanges e ON a.exchange_mic = e.mic
                WHERE a.active_flag = true
                ORDER BY a.exchange_mic, a.canonical_id
            """)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_existing_row_count(self, canonical_id: str) -> int:
        """Get existing price row count for an asset"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM fhq_data.price_series
                WHERE listing_id = %s
            """, (canonical_id,))
            return cur.fetchone()[0]

    def get_last_timestamp(self, canonical_id: str) -> Optional[datetime]:
        """Get the most recent timestamp for an asset"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT MAX(timestamp) FROM fhq_data.price_series
                WHERE listing_id = %s
            """, (canonical_id,))
            result = cur.fetchone()[0]
            return result

    def insert_prices(self, canonical_id: str, df: pd.DataFrame, vendor_id: str = "YFINANCE") -> int:
        """Insert price data into fhq_data.price_series"""
        if df.empty:
            return 0

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
                adj_close = EXCLUDED.adj_close,
                is_verified = false
        """

        values = []
        for idx, row in df.iterrows():
            # Handle timezone
            ts = idx.tz_localize(None) if hasattr(idx, 'tz_localize') and idx.tzinfo else idx

            # For yfinance with auto_adjust=False, we get both close and adj_close
            # For auto_adjust=True, Close is already adjusted
            close_val = float(row['Close']) if pd.notna(row['Close']) else None
            adj_close_val = float(row.get('Adj Close', row['Close'])) if pd.notna(row.get('Adj Close', row['Close'])) else close_val

            values.append((
                canonical_id,
                ts,
                vendor_id,
                'DAILY',
                'RAW',
                float(row['Open']) if pd.notna(row['Open']) else None,
                float(row['High']) if pd.notna(row['High']) else None,
                float(row['Low']) if pd.notna(row['Low']) else None,
                close_val,
                int(row['Volume']) if pd.notna(row['Volume']) else None,
                adj_close_val,
                f"BACKFILL_{datetime.now().strftime('%Y%m%d')}",
                False
            ))

        with self.conn.cursor() as cur:
            execute_values(cur, insert_sql, values)
            inserted = cur.rowcount

        self.conn.commit()
        return inserted

    def update_valid_row_count(self, canonical_id: str) -> int:
        """Update valid_row_count for an asset"""
        with self.conn.cursor() as cur:
            # Count rows
            cur.execute("""
                SELECT COUNT(*) FROM fhq_data.price_series
                WHERE listing_id = %s AND close IS NOT NULL
            """, (canonical_id,))
            count = cur.fetchone()[0]

            # Update asset
            cur.execute("""
                UPDATE fhq_meta.assets
                SET valid_row_count = %s,
                    updated_at = NOW()
                WHERE canonical_id = %s
            """, (count, canonical_id))

        self.conn.commit()
        return count

    def update_data_quality_status(self, canonical_id: str, valid_row_count: int, asset_class: str) -> str:
        """Update data_quality_status based on Iron Curtain thresholds"""
        # Determine thresholds based on asset class
        if asset_class == 'CRYPTO':
            quarantine_threshold = self.config.CRYPTO_QUARANTINE
            full_history_threshold = self.config.CRYPTO_FULL_HISTORY
        else:
            quarantine_threshold = self.config.EQUITY_FX_QUARANTINE
            full_history_threshold = self.config.EQUITY_FX_FULL_HISTORY

        # Determine status
        if valid_row_count < quarantine_threshold:
            status = 'QUARANTINED'
        elif valid_row_count < full_history_threshold:
            status = 'SHORT_HISTORY'
        else:
            status = 'FULL_HISTORY'

        # Update
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_meta.assets
                SET data_quality_status = %s::data_quality_status,
                    updated_at = NOW()
                WHERE canonical_id = %s
            """, (status, canonical_id))

        self.conn.commit()
        return status

    def log_governance_action(self, action_type: str, target: str, decision: str, rationale: str):
        """Log action to fhq_governance.governance_actions_log (ADR-002 compliance)"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_id,
                    action_type,
                    action_target,
                    action_target_type,
                    initiated_by,
                    initiated_at,
                    decision,
                    decision_rationale,
                    vega_reviewed,
                    hash_chain_id
                ) VALUES (
                    gen_random_uuid(),
                    %s,
                    %s,
                    'DATA',
                    'STIG',
                    NOW(),
                    %s,
                    %s,
                    false,
                    'BACKFILL-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
                )
            """, (action_type, target, decision, rationale))
        self.conn.commit()

    def log_discrepancy(self, canonical_id: str, discrepancy_type: str, details: str):
        """Log data discrepancy for audit trail (ADR-002 compliance)"""
        self.log_governance_action(
            'DATA_DISCREPANCY',
            canonical_id,
            'ESCALATED',  # Valid decision per governance_actions_log_decision_check
            f'{discrepancy_type}: {details}'
        )


# =============================================================================
# YFINANCE FETCHING
# =============================================================================

def construct_yf_ticker(asset: Dict) -> str:
    """Construct yfinance ticker from asset data"""
    ticker = asset['ticker']
    suffix = asset.get('yahoo_suffix', '') or ''
    exchange_mic = asset['exchange_mic']

    # Special handling for different asset classes
    if exchange_mic == 'XCRY':
        # Crypto: ticker already has -USD suffix (e.g., BTC-USD)
        return ticker
    elif exchange_mic == 'XFOR':
        # FX: ticker may need =X suffix if not already there
        if not ticker.endswith('=X'):
            return f"{ticker}=X"
        return ticker
    else:
        # Equities: append exchange suffix
        return f"{ticker}{suffix}"


def fetch_historical_data(
    yf_ticker: str,
    canonical_id: str,
    start_date: date,
    end_date: date,
    logger: logging.Logger,
    max_retries: int = 3,
    retry_delay: float = 10.0
) -> Optional[pd.DataFrame]:
    """Fetch historical OHLCV data from yfinance with retry logic"""

    for attempt in range(max_retries):
        try:
            logger.debug(f"  Fetching {yf_ticker} ({start_date} to {end_date}), attempt {attempt + 1}")

            # Create ticker and download data
            ticker = yf.Ticker(yf_ticker)

            # Use download instead of history for more stability
            df = yf.download(
                yf_ticker,
                start=start_date.strftime('%Y-%m-%d'),
                end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                interval='1d',
                auto_adjust=False,  # Get both Close and Adj Close
                progress=False,
                threads=False
            )

            if df is None or df.empty:
                if attempt < max_retries - 1:
                    logger.warning(f"  [{canonical_id}] Empty response, retrying...")
                    time.sleep(retry_delay)
                    continue
                logger.warning(f"  [{canonical_id}] No data returned from yfinance")
                return None

            # Clean data
            df = df.dropna(subset=['Close'])

            if df.empty:
                logger.warning(f"  [{canonical_id}] No valid data after cleaning")
                return None

            return df

        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = any(x in error_str for x in [
                "too many requests", "rate limit", "429", "throttle"
            ])

            if is_rate_limit:
                wait_time = retry_delay * (attempt + 1)  # Exponential backoff
                logger.warning(f"  [{canonical_id}] Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            elif attempt < max_retries - 1:
                logger.warning(f"  [{canonical_id}] Error: {e}, retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                continue
            else:
                logger.error(f"  [{canonical_id}] Failed after {max_retries} attempts: {e}")
                return None

    return None


# =============================================================================
# MAIN BACKFILL PIPELINE
# =============================================================================

def run_backfill(
    config: BackfillConfig,
    logger: logging.Logger,
    exchange_filter: Optional[str] = None,
    limit: Optional[int] = None
) -> Dict:
    """
    Execute the full backfill pipeline for all assets.

    Args:
        config: Backfill configuration
        logger: Logger instance
        exchange_filter: Optional MIC to filter assets (e.g., 'XOSL')
        limit: Optional limit on number of assets to process

    Returns:
        Dictionary with backfill results
    """
    logger.info("=" * 70)
    logger.info("IoS-001 PRICE BACKFILL PIPELINE - Starting")
    logger.info("=" * 70)
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info(f"Rate limiting: {config.BATCH_SIZE} assets/batch, {config.DELAY_BETWEEN_ASSETS}s between assets")
    logger.info("=" * 70)

    # Initialize
    db = DatabaseManager(config, logger)
    db.connect()

    results = {
        "started_at": datetime.now().isoformat(),
        "assets_processed": 0,
        "assets_success": 0,
        "assets_failed": 0,
        "assets_skipped": 0,
        "total_rows_inserted": 0,
        "status_changes": {
            "QUARANTINED": 0,
            "SHORT_HISTORY": 0,
            "FULL_HISTORY": 0
        },
        "errors": [],
        "per_asset": {}
    }

    try:
        # ADR-002: Log pipeline start
        db.log_governance_action(
            'PRICE_BACKFILL_START',
            'fhq_data.price_series',
            'IN_PROGRESS',
            f'IoS-001 Price Backfill Pipeline initiated. Exchange filter: {exchange_filter or "ALL"}, Limit: {limit or "NONE"}'
        )
        # Get all assets
        assets = db.get_all_assets()

        # Apply filters
        if exchange_filter:
            assets = [a for a in assets if a['exchange_mic'] == exchange_filter]
            logger.info(f"Filtered to {exchange_filter}: {len(assets)} assets")

        if limit:
            assets = assets[:limit]
            logger.info(f"Limited to {limit} assets")

        total_assets = len(assets)
        logger.info(f"Total assets to process: {total_assets}")

        # Calculate end date (yesterday to avoid partial data)
        end_date = date.today() - timedelta(days=1)
        start_date = date.today() - timedelta(days=config.MAX_HISTORY_YEARS * 365)

        # Process in batches
        for batch_idx in range(0, total_assets, config.BATCH_SIZE):
            batch = assets[batch_idx:batch_idx + config.BATCH_SIZE]
            batch_num = (batch_idx // config.BATCH_SIZE) + 1
            total_batches = (total_assets + config.BATCH_SIZE - 1) // config.BATCH_SIZE

            logger.info(f"\n{'='*50}")
            logger.info(f"BATCH {batch_num}/{total_batches} ({len(batch)} assets)")
            logger.info(f"{'='*50}")

            for asset in batch:
                canonical_id = asset['canonical_id']
                results["assets_processed"] += 1

                try:
                    # Construct yfinance ticker
                    yf_ticker = construct_yf_ticker(asset)

                    # Check existing data
                    existing_count = db.get_existing_row_count(canonical_id)
                    last_ts = db.get_last_timestamp(canonical_id)

                    # Determine fetch start date
                    if last_ts:
                        fetch_start = (last_ts + timedelta(days=1)).date()
                        if fetch_start > end_date:
                            logger.info(f"  [{canonical_id}] Already up to date ({existing_count} rows)")
                            results["assets_skipped"] += 1
                            results["per_asset"][canonical_id] = {
                                "status": "SKIPPED",
                                "reason": "up_to_date",
                                "existing_rows": existing_count
                            }
                            continue
                    else:
                        fetch_start = start_date

                    logger.info(f"  [{canonical_id}] Fetching {yf_ticker} from {fetch_start}")

                    # Fetch data
                    df = fetch_historical_data(
                        yf_ticker, canonical_id,
                        fetch_start, end_date,
                        logger,
                        config.MAX_RETRIES,
                        config.RETRY_DELAY
                    )

                    if df is None or df.empty:
                        logger.warning(f"  [{canonical_id}] No data fetched")
                        results["assets_failed"] += 1
                        results["per_asset"][canonical_id] = {
                            "status": "FAILED",
                            "reason": "no_data",
                            "yf_ticker": yf_ticker
                        }
                        # ADR-002: Log discrepancy for failed fetch
                        db.log_discrepancy(
                            canonical_id,
                            'FETCH_FAILURE',
                            f'No data returned from yfinance for ticker {yf_ticker}'
                        )
                        time.sleep(config.DELAY_BETWEEN_ASSETS)
                        continue

                    # Insert data
                    inserted = db.insert_prices(canonical_id, df)
                    results["total_rows_inserted"] += inserted

                    # Update valid_row_count
                    valid_count = db.update_valid_row_count(canonical_id)

                    # Update data_quality_status
                    new_status = db.update_data_quality_status(
                        canonical_id, valid_count, asset['asset_class']
                    )
                    results["status_changes"][new_status] += 1

                    logger.info(f"  [{canonical_id}] Inserted {inserted} rows, total {valid_count}, status={new_status}")

                    results["assets_success"] += 1
                    results["per_asset"][canonical_id] = {
                        "status": "SUCCESS",
                        "rows_inserted": inserted,
                        "valid_row_count": valid_count,
                        "data_quality_status": new_status,
                        "yf_ticker": yf_ticker
                    }

                except Exception as e:
                    logger.error(f"  [{canonical_id}] Error: {e}")
                    results["assets_failed"] += 1
                    results["errors"].append({
                        "canonical_id": canonical_id,
                        "error": str(e)
                    })
                    results["per_asset"][canonical_id] = {
                        "status": "ERROR",
                        "error": str(e)
                    }
                    # ADR-002: Log discrepancy for error
                    try:
                        db.log_discrepancy(
                            canonical_id,
                            'PROCESSING_ERROR',
                            str(e)[:500]  # Truncate long error messages
                        )
                    except:
                        pass  # Don't fail pipeline on logging error

                # Rate limiting between assets
                time.sleep(config.DELAY_BETWEEN_ASSETS)

            # Rate limiting between batches
            if batch_idx + config.BATCH_SIZE < total_assets:
                logger.info(f"\nBatch complete. Waiting {config.DELAY_BETWEEN_BATCHES}s before next batch...")
                time.sleep(config.DELAY_BETWEEN_BATCHES)

        results["status"] = "COMPLETED"

        # ADR-002: Log pipeline completion
        db.log_governance_action(
            'PRICE_BACKFILL_COMPLETE',
            'fhq_data.price_series',
            'COMPLETED',
            f'IoS-001 Price Backfill completed. Processed: {results["assets_processed"]}, Success: {results["assets_success"]}, Failed: {results["assets_failed"]}, Rows inserted: {results["total_rows_inserted"]}'
        )

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        results["status"] = "FAILED"
        results["error"] = str(e)

        # ADR-002: Log pipeline failure
        try:
            db.log_governance_action(
                'PRICE_BACKFILL_FAILED',
                'fhq_data.price_series',
                'FAILED',
                f'IoS-001 Price Backfill failed: {str(e)[:500]}'
            )
        except:
            pass

    finally:
        db.close()

    results["completed_at"] = datetime.now().isoformat()

    # Write evidence
    evidence_file = config.EVIDENCE_DIR / f"BACKFILL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(evidence_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"\nEvidence written to: {evidence_file}")

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("BACKFILL COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Status: {results['status']}")
    logger.info(f"Assets processed: {results['assets_processed']}")
    logger.info(f"  - Success: {results['assets_success']}")
    logger.info(f"  - Failed: {results['assets_failed']}")
    logger.info(f"  - Skipped: {results['assets_skipped']}")
    logger.info(f"Total rows inserted: {results['total_rows_inserted']}")
    logger.info(f"Status distribution:")
    logger.info(f"  - QUARANTINED: {results['status_changes']['QUARANTINED']}")
    logger.info(f"  - SHORT_HISTORY: {results['status_changes']['SHORT_HISTORY']}")
    logger.info(f"  - FULL_HISTORY: {results['status_changes']['FULL_HISTORY']}")
    logger.info("=" * 70)

    return results


# =============================================================================
# IRON CURTAIN REPORT
# =============================================================================

def generate_iron_curtain_report(config: BackfillConfig, logger: logging.Logger) -> Dict:
    """Generate Iron Curtain Eligibility Report after backfill"""
    logger.info("\n" + "=" * 70)
    logger.info("IRON CURTAIN ELIGIBILITY REPORT")
    logger.info("=" * 70)

    db = DatabaseManager(config, logger)
    db.connect()

    try:
        with db.conn.cursor() as cur:
            # Summary by status
            cur.execute("""
                SELECT
                    data_quality_status,
                    COUNT(*) as count,
                    MIN(valid_row_count) as min_rows,
                    MAX(valid_row_count) as max_rows,
                    ROUND(AVG(valid_row_count)) as avg_rows
                FROM fhq_meta.assets
                WHERE active_flag = true
                GROUP BY data_quality_status
                ORDER BY data_quality_status
            """)
            status_summary = cur.fetchall()

            logger.info("\nStatus Summary:")
            logger.info("-" * 50)
            for row in status_summary:
                status, count, min_r, max_r, avg_r = row
                logger.info(f"  {status}: {count} assets (rows: {min_r}-{max_r}, avg: {avg_r})")

            # By asset class
            cur.execute("""
                SELECT
                    asset_class,
                    data_quality_status,
                    COUNT(*) as count
                FROM fhq_meta.assets
                WHERE active_flag = true
                GROUP BY asset_class, data_quality_status
                ORDER BY asset_class, data_quality_status
            """)
            class_summary = cur.fetchall()

            logger.info("\nBy Asset Class:")
            logger.info("-" * 50)
            for row in class_summary:
                asset_class, status, count = row
                logger.info(f"  {asset_class} / {status}: {count}")

            # IoS-003 eligible (not QUARANTINED)
            cur.execute("""
                SELECT COUNT(*)
                FROM fhq_meta.assets
                WHERE active_flag = true AND data_quality_status != 'QUARANTINED'
            """)
            ios003_eligible = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*)
                FROM fhq_meta.assets
                WHERE active_flag = true
            """)
            total_active = cur.fetchone()[0]

            logger.info(f"\nIoS-003 Eligible: {ios003_eligible}/{total_active} assets")

            report = {
                "generated_at": datetime.now().isoformat(),
                "status_summary": [
                    {"status": r[0], "count": r[1], "min_rows": r[2], "max_rows": r[3], "avg_rows": r[4]}
                    for r in status_summary
                ],
                "class_summary": [
                    {"asset_class": r[0], "status": r[1], "count": r[2]}
                    for r in class_summary
                ],
                "ios003_eligible": ios003_eligible,
                "total_active": total_active
            }

    finally:
        db.close()

    logger.info("=" * 70)

    return report


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="IoS-001 Price Backfill Pipeline")
    parser.add_argument("--exchange", type=str, help="Filter by exchange MIC (e.g., XOSL)")
    parser.add_argument("--limit", type=int, help="Limit number of assets to process")
    parser.add_argument("--report-only", action="store_true", help="Only generate Iron Curtain report")
    parser.add_argument("--batch-size", type=int, default=20, help="Assets per batch")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between assets (seconds)")

    args = parser.parse_args()

    config = BackfillConfig()
    if args.batch_size:
        config.BATCH_SIZE = args.batch_size
    if args.delay:
        config.DELAY_BETWEEN_ASSETS = args.delay

    logger = setup_logging()

    if args.report_only:
        generate_iron_curtain_report(config, logger)
    else:
        run_backfill(config, logger, args.exchange, args.limit)
        generate_iron_curtain_report(config, logger)
