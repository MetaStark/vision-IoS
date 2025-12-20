#!/usr/bin/env python3
"""
LINE: LIVE MARKET SNAPSHOT
===========================
CEO DIRECTIVE: CI-20251209 / REALITY MANDATE

We do not mock reality. We sense it.
This script uses REAL market data from the canonical price store.
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Dict, Any, Optional


def get_db_connection():
    """Get database connection"""
    host = os.getenv("PGHOST", "127.0.0.1")
    port = os.getenv("PGPORT", "54322")
    database = os.getenv("PGDATABASE", "postgres")
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD", "postgres")
    return psycopg2.connect(f"postgresql://{user}:{password}@{host}:{port}/{database}")


def fetch_canonical_prices() -> Dict[str, Any]:
    """
    Fetch REAL prices from the canonical fhq_market.prices store.

    This is REAL data that was ingested from market sources.
    """
    conn = get_db_connection()
    prices = {}

    print("\n[LINE] Fetching from CANONICAL price store (fhq_market.prices)...")

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get latest prices for key assets
            cur.execute("""
                SELECT DISTINCT ON (canonical_id)
                    canonical_id,
                    close,
                    open,
                    high,
                    low,
                    volume,
                    timestamp,
                    source
                FROM fhq_market.prices
                WHERE canonical_id IN ('BTC-USD', 'ETH-USD', 'SOL-USD', 'EURUSD')
                ORDER BY canonical_id, timestamp DESC
            """)

            for row in cur.fetchall():
                prices[row['canonical_id']] = {
                    "price": float(row['close']),
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "volume": float(row['volume']) if row['volume'] else 0,
                    "timestamp": row['timestamp'].isoformat() if row['timestamp'] else None,
                    "source": row['source']
                }
                print(f"  [{row['canonical_id']}] ${float(row['close']):,.2f} (as of {row['timestamp']})")

    finally:
        conn.close()

    return prices


def determine_regime_from_data(prices: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine market regime from REAL price data.

    Based on price action and volatility.
    """
    btc = prices.get("BTC-USD", {})
    btc_price = btc.get("price", 0)
    btc_open = btc.get("open", btc_price)
    btc_high = btc.get("high", btc_price)
    btc_low = btc.get("low", btc_price)

    # Calculate metrics
    btc_change = ((btc_price - btc_open) / btc_open * 100) if btc_open > 0 else 0
    btc_range = ((btc_high - btc_low) / btc_low * 100) if btc_low > 0 else 0

    # Regime determination based on BTC price action
    if btc_price > 100000:
        regime = "BULL"
        confidence = 0.85
        reasoning = f"BTC above $100k indicates strong bull market"
    elif btc_price > 80000 and btc_change >= 0:
        regime = "BULL"
        confidence = 0.75
        reasoning = f"BTC at ${btc_price:,.0f} with positive momentum"
    elif btc_change < -5:
        regime = "BEAR"
        confidence = 0.70
        reasoning = f"BTC dropped {btc_change:.1f}% - bearish signal"
    elif btc_range > 5:
        regime = "CRISIS" if btc_change < -3 else "SIDEWAYS"
        confidence = 0.65
        reasoning = f"High volatility ({btc_range:.1f}% range)"
    else:
        regime = "SIDEWAYS"
        confidence = 0.60
        reasoning = f"BTC at ${btc_price:,.0f}, low volatility"

    return {
        "regime": regime,
        "confidence": confidence,
        "btc_price": btc_price,
        "btc_change_pct": btc_change,
        "btc_range_pct": btc_range,
        "reasoning": reasoning
    }


def store_live_snapshot(prices: Dict[str, Any], regime_data: Dict[str, Any]) -> str:
    """
    Store the LIVE snapshot into the database.
    """
    conn = get_db_connection()
    snapshot_id = None

    try:
        with conn.cursor() as cur:
            # Update regime state with REAL data
            cur.execute("""
                UPDATE fhq_meta.regime_state
                SET current_regime = %s,
                    regime_confidence = %s,
                    last_updated_at = NOW(),
                    updated_by = 'LINE.live_snapshot'
                RETURNING state_id
            """, (regime_data["regime"], regime_data["confidence"]))

            result = cur.fetchone()
            if result:
                print(f"\n[LINE] Regime updated: {regime_data['regime']} ({regime_data['confidence']:.0%})")
                print(f"[LINE] Reasoning: {regime_data['reasoning']}")

            # Log as system event
            cur.execute("""
                INSERT INTO fhq_governance.system_events (
                    event_id,
                    event_type,
                    event_category,
                    event_severity,
                    source_agent,
                    source_component,
                    source_ios_layer,
                    event_title,
                    event_description,
                    event_data,
                    regime,
                    defcon_level,
                    created_at
                ) VALUES (
                    gen_random_uuid(),
                    'MARKET_SNAPSHOT',
                    'PERCEPTION',
                    'INFO',
                    'LINE',
                    'live_snapshot',
                    'IoS-001',
                    'Canonical Price Snapshot',
                    %s,
                    %s,
                    %s,
                    5,
                    NOW()
                ) RETURNING event_id
            """, (
                f"BTC: ${prices.get('BTC-USD', {}).get('price', 0):,.0f}, "
                f"ETH: ${prices.get('ETH-USD', {}).get('price', 0):,.0f}, "
                f"Regime: {regime_data['regime']} - {regime_data['reasoning']}",
                json.dumps({"prices": prices, "regime": regime_data}, default=str),
                regime_data["regime"]
            ))

            result = cur.fetchone()
            if result:
                snapshot_id = str(result[0])
                print(f"[LINE] Event logged: {snapshot_id[:8]}...")

            # Store as episodic memory (REAL observation)
            cur.execute("""
                INSERT INTO fhq_memory.episodic_memory (
                    episode_id,
                    episode_type,
                    episode_title,
                    episode_description,
                    started_at,
                    regime_at_start,
                    primary_agent,
                    outcome_type,
                    outcome_metadata,
                    importance_score,
                    created_at
                ) VALUES (
                    gen_random_uuid(),
                    'MARKET_OBSERVATION',
                    'Canonical Price Snapshot',
                    %s,
                    NOW(),
                    %s,
                    'LINE',
                    'SUCCESS',
                    %s,
                    0.70,
                    NOW()
                ) RETURNING episode_id
            """, (
                f"CANONICAL DATA from fhq_market.prices: "
                f"BTC=${prices.get('BTC-USD', {}).get('price', 0):,.0f}, "
                f"ETH=${prices.get('ETH-USD', {}).get('price', 0):,.0f}. "
                f"Regime={regime_data['regime']} ({regime_data['confidence']:.0%}). "
                f"{regime_data['reasoning']}",
                regime_data["regime"],
                json.dumps(prices, default=str)
            ))

            result = cur.fetchone()
            if result:
                print(f"[LINE] Episodic memory stored: {result[0]}")

            conn.commit()
            print("[LINE] Database committed successfully")

    except Exception as e:
        print(f"[ERROR] Database error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

    return snapshot_id


def fetch_live_snapshot() -> Dict[str, Any]:
    """
    Main entry point: Fetch live market snapshot from canonical store.
    """
    print("\n" + "=" * 60)
    print("LINE: CANONICAL MARKET SNAPSHOT")
    print("CEO DIRECTIVE: CI-20251209 / REALITY MANDATE")
    print("=" * 60)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

    # Fetch REAL prices from canonical store
    prices = fetch_canonical_prices()

    if not prices:
        print("[ERROR] No price data in canonical store")
        return {"success": False, "error": "No price data"}

    # Determine regime from REAL data
    regime_data = determine_regime_from_data(prices)

    # Store in database
    snapshot_id = store_live_snapshot(prices, regime_data)

    result = {
        "success": True,
        "snapshot_id": snapshot_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prices": prices,
        "regime": regime_data
    }

    print("\n" + "=" * 60)
    print("[LINE] CANONICAL SNAPSHOT COMPLETE")
    print("=" * 60)

    return result


if __name__ == "__main__":
    fetch_live_snapshot()
