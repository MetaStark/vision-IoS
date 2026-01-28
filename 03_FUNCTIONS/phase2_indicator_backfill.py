#!/usr/bin/env python3
"""
PHASE 2 INDICATOR BACKFILL
CEO Directive: Phase 2 Foundation - Governance Normalization & Pre-Flight Ops
Date: 2026-01-28
Author: STIG

PURPOSE:
Backfill fhq_indicators.momentum and fhq_indicators.volatility tables
from fhq_data.price_series for Phase 2 Hypothesis Swarm execution.

INDICATORS COMPUTED:
- Momentum: RSI(14), MACD, Stochastic
- Volatility: Bollinger Bands (20,2), BBW, ATR(14)
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import execute_values
import numpy as np
import pandas as pd

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("phase2_indicator_backfill")

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "54322"),
        database=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres")
    )

# =============================================================================
# INDICATOR CALCULATIONS
# =============================================================================

def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI (Relative Strength Index)."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
    """Calculate MACD."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {"macd_line": macd_line, "macd_signal": signal_line, "macd_histogram": histogram}


def calc_stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                    k_period: int = 14, d_period: int = 3) -> Dict[str, pd.Series]:
    """Calculate Stochastic Oscillator."""
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()

    stoch_k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    stoch_d = stoch_k.rolling(window=d_period).mean()

    return {"stoch_k": stoch_k, "stoch_d": stoch_d}


def calc_bollinger(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict[str, pd.Series]:
    """Calculate Bollinger Bands and BBW."""
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    bbw = (upper - lower) / sma
    return {
        "bb_upper": upper,
        "bb_middle": sma,
        "bb_lower": lower,
        "bbw": bbw
    }


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate ATR (Average True Range)."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = abs(high - prev_close)
    tr3 = abs(low - prev_close)
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr

# =============================================================================
# DATA LOADING
# =============================================================================

def get_assets(conn) -> List[str]:
    """Get list of assets from price_series."""
    query = """
        SELECT DISTINCT listing_id
        FROM fhq_data.price_series
        ORDER BY listing_id
    """
    with conn.cursor() as cur:
        cur.execute(query)
        return [row[0] for row in cur.fetchall()]


def load_price_data(conn, listing_id: str) -> pd.DataFrame:
    """Load price data for an asset."""
    query = """
        SELECT date, open, high, low, close, volume
        FROM fhq_data.price_series
        WHERE listing_id = %s
        ORDER BY date
    """
    df = pd.read_sql(query, conn, params=(listing_id,))
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    return df


def get_existing_dates(conn, listing_id: str, table: str) -> set:
    """Get dates already in indicator table."""
    query = f"""
        SELECT signal_date
        FROM fhq_indicators.{table}
        WHERE listing_id = %s
    """
    with conn.cursor() as cur:
        cur.execute(query, (listing_id,))
        return {row[0] for row in cur.fetchall()}

# =============================================================================
# BACKFILL LOGIC
# =============================================================================

def backfill_momentum(conn, listing_id: str, price_df: pd.DataFrame) -> int:
    """Backfill momentum indicators for one asset."""
    if len(price_df) < 30:
        return 0

    # Get existing dates
    existing = get_existing_dates(conn, listing_id, 'momentum')

    # Calculate indicators
    rsi = calc_rsi(price_df['close'])
    macd = calc_macd(price_df['close'])
    stoch = calc_stochastic(price_df['high'], price_df['low'], price_df['close'])

    # Build rows
    rows = []
    for i, row in price_df.iterrows():
        date = row['date'].date()
        if date in existing:
            continue
        if pd.isna(rsi.iloc[i]):
            continue

        rows.append((
            date,
            listing_id,
            float(rsi.iloc[i]) if pd.notna(rsi.iloc[i]) else None,
            float(macd['macd_line'].iloc[i]) if pd.notna(macd['macd_line'].iloc[i]) else None,
            float(macd['macd_signal'].iloc[i]) if pd.notna(macd['macd_signal'].iloc[i]) else None,
            float(macd['macd_histogram'].iloc[i]) if pd.notna(macd['macd_histogram'].iloc[i]) else None,
            float(stoch['stoch_k'].iloc[i]) if pd.notna(stoch['stoch_k'].iloc[i]) else None,
            float(stoch['stoch_d'].iloc[i]) if pd.notna(stoch['stoch_d'].iloc[i]) else None
        ))

    if rows:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO fhq_indicators.momentum
                (signal_date, listing_id, rsi_14, macd_line, macd_signal, macd_histogram, stoch_k, stoch_d)
                VALUES %s
                ON CONFLICT DO NOTHING
            """, rows, page_size=1000)
        conn.commit()

    return len(rows)


def backfill_volatility(conn, listing_id: str, price_df: pd.DataFrame) -> int:
    """Backfill volatility indicators for one asset."""
    if len(price_df) < 30:
        return 0

    # Get existing dates
    existing = get_existing_dates(conn, listing_id, 'volatility')

    # Calculate indicators
    bb = calc_bollinger(price_df['close'])
    atr = calc_atr(price_df['high'], price_df['low'], price_df['close'])

    # Build rows
    rows = []
    for i, row in price_df.iterrows():
        date = row['date'].date()
        if date in existing:
            continue
        if pd.isna(bb['bb_middle'].iloc[i]):
            continue

        rows.append((
            date,
            listing_id,
            float(bb['bb_upper'].iloc[i]) if pd.notna(bb['bb_upper'].iloc[i]) else None,
            float(bb['bb_middle'].iloc[i]) if pd.notna(bb['bb_middle'].iloc[i]) else None,
            float(bb['bb_lower'].iloc[i]) if pd.notna(bb['bb_lower'].iloc[i]) else None,
            float(atr.iloc[i]) if pd.notna(atr.iloc[i]) else None,
            float(bb['bbw'].iloc[i]) if pd.notna(bb['bbw'].iloc[i]) else None
        ))

    if rows:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO fhq_indicators.volatility
                (signal_date, listing_id, bb_upper, bb_middle, bb_lower, atr_14, bbw)
                VALUES %s
                ON CONFLICT DO NOTHING
            """, rows, page_size=1000)
        conn.commit()

    return len(rows)

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_backfill() -> Dict:
    """Run full indicator backfill."""
    logger.info("=" * 60)
    logger.info("PHASE 2 INDICATOR BACKFILL")
    logger.info("CEO Directive: Execution Blocker Removal")
    logger.info("=" * 60)

    conn = get_db_connection()

    try:
        # Get assets
        assets = get_assets(conn)
        logger.info(f"Found {len(assets)} assets to process")

        # Track results
        results = {
            "assets_processed": 0,
            "momentum_rows": 0,
            "volatility_rows": 0,
            "errors": []
        }

        for i, listing_id in enumerate(assets):
            try:
                # Load price data
                price_df = load_price_data(conn, listing_id)

                if len(price_df) < 30:
                    logger.debug(f"  Skipping {listing_id}: insufficient data ({len(price_df)} rows)")
                    continue

                # Backfill
                mom_rows = backfill_momentum(conn, listing_id, price_df)
                vol_rows = backfill_volatility(conn, listing_id, price_df)

                results["momentum_rows"] += mom_rows
                results["volatility_rows"] += vol_rows
                results["assets_processed"] += 1

                if (i + 1) % 50 == 0:
                    logger.info(f"Progress: {i+1}/{len(assets)} assets processed")

            except Exception as e:
                logger.error(f"Error processing {listing_id}: {e}")
                results["errors"].append({"asset": listing_id, "error": str(e)})

        # Get final counts
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fhq_indicators.momentum")
            results["momentum_total"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM fhq_indicators.volatility")
            results["volatility_total"] = cur.fetchone()[0]

            # Coverage stats
            cur.execute("""
                SELECT
                    COUNT(DISTINCT listing_id) as assets,
                    MIN(signal_date) as min_date,
                    MAX(signal_date) as max_date,
                    SUM(CASE WHEN rsi_14 IS NULL THEN 1 ELSE 0 END) as rsi_nulls
                FROM fhq_indicators.momentum
            """)
            row = cur.fetchone()
            results["momentum_coverage"] = {
                "assets": row[0],
                "min_date": str(row[1]),
                "max_date": str(row[2]),
                "rsi_null_count": row[3]
            }

            cur.execute("""
                SELECT
                    COUNT(DISTINCT listing_id) as assets,
                    MIN(signal_date) as min_date,
                    MAX(signal_date) as max_date,
                    SUM(CASE WHEN bb_upper IS NULL THEN 1 ELSE 0 END) as bb_upper_nulls,
                    SUM(CASE WHEN bb_middle IS NULL THEN 1 ELSE 0 END) as bb_middle_nulls,
                    SUM(CASE WHEN bb_lower IS NULL THEN 1 ELSE 0 END) as bb_lower_nulls,
                    SUM(CASE WHEN bbw IS NULL THEN 1 ELSE 0 END) as bbw_nulls,
                    SUM(CASE WHEN atr_14 IS NULL THEN 1 ELSE 0 END) as atr_nulls
                FROM fhq_indicators.volatility
            """)
            row = cur.fetchone()
            results["volatility_coverage"] = {
                "assets": row[0],
                "min_date": str(row[1]),
                "max_date": str(row[2]),
                "bb_upper_null_count": row[3],
                "bb_middle_null_count": row[4],
                "bb_lower_null_count": row[5],
                "bbw_null_count": row[6],
                "atr_null_count": row[7]
            }

        logger.info("\n" + "=" * 60)
        logger.info("BACKFILL COMPLETE")
        logger.info(f"  Assets processed: {results['assets_processed']}")
        logger.info(f"  Momentum rows inserted: {results['momentum_rows']}")
        logger.info(f"  Volatility rows inserted: {results['volatility_rows']}")
        logger.info(f"  Momentum total: {results['momentum_total']}")
        logger.info(f"  Volatility total: {results['volatility_total']}")
        logger.info(f"  Errors: {len(results['errors'])}")
        logger.info("=" * 60)

        return results

    finally:
        conn.close()


if __name__ == "__main__":
    results = run_backfill()

    # Write evidence artifact
    evidence = {
        "evidence_type": "INDICATOR_BACKFILL_COMPLETION",
        "directive": "CEO_DIR_2026_PHASE2_FOUNDATION",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results
    }

    evidence_path = "03_FUNCTIONS/evidence/PHASE2_INDICATOR_BACKFILL_COMPLETION_REPORT.json"
    with open(evidence_path, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    logger.info(f"Evidence written to {evidence_path}")
