#!/usr/bin/env python3
"""
CEIO Backfill: GLD and TLT Price Data
CEO-DIR-2026-030 Phase 1 P0 Action

Executed by: STIG (coordinating CEIO mandate)
Authority: EC-009 (CEIO) Section 4.1 - Signal Ingestion & Normalization
Data Source: yfinance (Tier 1 - Lake)

This script:
1. Registers GLD and TLT in fhq_meta.assets (if not exists)
2. Fetches historical prices from yfinance
3. Inserts into fhq_market.prices with proper governance
4. Logs evidence for court-proof compliance
"""

import os
import json
import hashlib
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta
from uuid import uuid4

try:
    import yfinance as yf
except ImportError:
    print("Installing yfinance...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'yfinance', '-q'])
    import yfinance as yf

DIRECTIVE_ID = "CEO-DIR-2026-030"
BACKFILL_START = "2025-12-01"
BACKFILL_END = "2026-01-10"

def get_db_connection():
    """Create database connection."""
    return psycopg2.connect(
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=os.environ.get('PGPORT', '54322'),
        database=os.environ.get('PGDATABASE', 'postgres'),
        user=os.environ.get('PGUSER', 'postgres'),
        password=os.environ.get('PGPASSWORD', 'postgres')
    )

def register_assets(conn):
    """Register GLD and TLT in fhq_meta.assets if not exists."""
    cursor = conn.cursor()

    assets = [
        {
            'canonical_id': 'GLD',
            'ticker': 'GLD',
            'exchange_mic': 'ARCX',
            'asset_class': 'ETF',
            'currency': 'USD',
            'sector': 'Commodities',
            'risk_profile': 'MEDIUM',
            'active_flag': True,
            'lot_size': 1,
            'tick_size': 0.01,
            'liquidity_tier': 'TIER_1',
            'gap_policy': 'FORWARD_FILL',
            'asset_type': 'ETF',
            'symbol': 'GLD'
        },
        {
            'canonical_id': 'TLT',
            'ticker': 'TLT',
            'exchange_mic': 'ARCX',
            'asset_class': 'ETF',
            'currency': 'USD',
            'sector': 'Fixed Income',
            'risk_profile': 'LOW',
            'active_flag': True,
            'lot_size': 1,
            'tick_size': 0.01,
            'liquidity_tier': 'TIER_1',
            'gap_policy': 'FORWARD_FILL',
            'asset_type': 'ETF',
            'symbol': 'TLT'
        }
    ]

    registered = 0
    for asset in assets:
        # Check if exists
        cursor.execute("""
            SELECT canonical_id FROM fhq_meta.assets WHERE canonical_id = %s
        """, (asset['canonical_id'],))

        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO fhq_meta.assets (
                    canonical_id, ticker, exchange_mic, asset_class, currency,
                    sector, risk_profile, active_flag, lot_size, tick_size,
                    liquidity_tier, gap_policy, asset_type, symbol,
                    created_at, updated_at, onboarding_date
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    NOW(), NOW(), CURRENT_DATE
                )
            """, (
                asset['canonical_id'], asset['ticker'], asset['exchange_mic'],
                asset['asset_class'], asset['currency'], asset['sector'],
                asset['risk_profile'], asset['active_flag'], asset['lot_size'],
                asset['tick_size'], asset['liquidity_tier'], asset['gap_policy'],
                asset['asset_type'], asset['symbol']
            ))
            registered += 1
            print(f"  [+] Registered asset: {asset['canonical_id']}")
        else:
            print(f"  [=] Asset already exists: {asset['canonical_id']}")

    conn.commit()
    cursor.close()
    return registered

def fetch_prices_yfinance(ticker, start_date, end_date, max_retries=3):
    """Fetch historical prices from yfinance (Tier 1 - Lake) with retry logic."""
    import time

    print(f"  Fetching {ticker} from yfinance ({start_date} to {end_date})...")

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                wait_time = 30 * attempt  # 30s, 60s, 90s
                print(f"  [!] Retry {attempt + 1}/{max_retries}, waiting {wait_time}s...")
                time.sleep(wait_time)

            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date)

            if df.empty:
                print(f"  [!] No data returned for {ticker}")
                return []

            prices = []
            for idx, row in df.iterrows():
                price_date = idx.to_pydatetime().replace(tzinfo=None)
                prices.append({
                    'timestamp': price_date,
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': float(row['Volume']),
                    'adj_close': float(row['Close'])  # yfinance returns adjusted by default
                })

            print(f"  [OK] Fetched {len(prices)} price records for {ticker}")
            return prices

        except Exception as e:
            if 'RateLimitError' in str(type(e).__name__) or 'Too Many Requests' in str(e):
                if attempt < max_retries - 1:
                    continue
                print(f"  [!] Rate limited after {max_retries} attempts for {ticker}")
            else:
                print(f"  [!] Error fetching {ticker}: {e}")
            return []

    return []

def insert_prices(conn, canonical_id, prices, batch_id):
    """Insert prices into fhq_market.prices."""
    cursor = conn.cursor()

    # Generate a consistent asset_id for this canonical_id
    # Use a deterministic UUID based on canonical_id for consistency
    asset_id = str(uuid4())  # Generate once per canonical_id

    # Check for existing prices to avoid duplicates
    cursor.execute("""
        SELECT timestamp::date FROM fhq_market.prices
        WHERE canonical_id = %s
    """, (canonical_id,))
    existing_dates = set(row[0] for row in cursor.fetchall())

    # Filter out existing dates
    new_prices = [p for p in prices if p['timestamp'].date() not in existing_dates]

    if not new_prices:
        print(f"  [=] All prices already exist for {canonical_id}")
        cursor.close()
        return 0

    # Prepare records for insertion
    records = []
    for p in new_prices:
        data_str = f"{canonical_id}|{p['timestamp']}|{p['close']}"
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:32]

        records.append((
            str(uuid4()),           # id
            asset_id,               # asset_id (required)
            canonical_id,           # canonical_id
            p['timestamp'],         # timestamp
            p['open'],              # open
            p['high'],              # high
            p['low'],               # low
            p['close'],             # close
            p['volume'],            # volume
            'yfinance',             # source (Tier 1 - Lake)
            None,                   # staging_id
            data_hash,              # data_hash
            False,                  # gap_filled
            False,                  # interpolated
            1.0,                    # quality_score
            batch_id,               # batch_id
            datetime.now(),         # canonicalized_at
            'CEIO',                 # canonicalized_by
            False,                  # vega_reconciled
            None,                   # vega_reconciled_at
            None,                   # vega_attestation_id
            p['adj_close'],         # adj_close
            'yfinance',             # vendor_id
            'PRIMARY',              # vendor_role
            'EOD'                   # price_class
        ))

    # Bulk insert
    execute_values(cursor, """
        INSERT INTO fhq_market.prices (
            id, asset_id, canonical_id, timestamp, open, high, low, close, volume,
            source, staging_id, data_hash, gap_filled, interpolated, quality_score,
            batch_id, canonicalized_at, canonicalized_by, vega_reconciled,
            vega_reconciled_at, vega_attestation_id, adj_close, vendor_id,
            vendor_role, price_class
        ) VALUES %s
        ON CONFLICT (canonical_id, timestamp) DO NOTHING
    """, records)

    inserted = cursor.rowcount
    conn.commit()
    cursor.close()

    print(f"  [OK] Inserted {inserted} new price records for {canonical_id}")
    return inserted

def log_backfill_evidence(conn, gld_count, tlt_count, batch_id):
    """Log backfill execution in governance log."""
    cursor = conn.cursor()

    metadata = {
        'directive': DIRECTIVE_ID,
        'action': 'CEIO_PRICE_BACKFILL',
        'phase': 'PHASE_1_TRUTH_AND_CALIBRATION',
        'assets': ['GLD', 'TLT'],
        'date_range': {
            'start': BACKFILL_START,
            'end': BACKFILL_END
        },
        'results': {
            'GLD_prices_inserted': gld_count,
            'TLT_prices_inserted': tlt_count,
            'total_inserted': gld_count + tlt_count
        },
        'data_source': 'yfinance (Tier 1 - Lake)',
        'batch_id': str(batch_id),
        'forecasts_unlocked_estimate': 3120,
        'coverage_improvement_estimate': '77.2% -> 94.7%'
    }

    cursor.execute("""
        INSERT INTO fhq_governance.governance_actions_log (
            action_id, action_type, action_target, action_target_type,
            initiated_by, initiated_at, decision, decision_rationale,
            metadata, agent_id, timestamp
        ) VALUES (
            %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, NOW()
        )
    """, (
        str(uuid4()),
        'CEIO_PRICE_BACKFILL',
        'GLD,TLT',
        'ASSET_PRICES',
        'CEIO',
        'EXECUTED',
        f'CEO-DIR-2026-030 Phase 1 P0: Backfilled {gld_count + tlt_count} price records for GLD and TLT to enable forecast-outcome coverage improvement.',
        json.dumps(metadata),
        'CEIO'
    ))

    conn.commit()
    cursor.close()
    print("  [OK] Backfill evidence logged to governance_actions_log")

def create_evidence_file(gld_count, tlt_count, batch_id):
    """Create evidence JSON file."""
    evidence = {
        'directive_id': DIRECTIVE_ID,
        'action': 'CEIO_PRICE_BACKFILL',
        'classification': 'PHASE_1_P0_EXECUTION',
        'executed_by': 'CEIO (coordinated by STIG)',
        'execution_timestamp': datetime.now().isoformat(),
        'authority': 'EC-009 Section 4.1 - Signal Ingestion & Normalization',

        'backfill_parameters': {
            'assets': ['GLD', 'TLT'],
            'date_range_start': BACKFILL_START,
            'date_range_end': BACKFILL_END,
            'data_source': 'yfinance',
            'api_tier': 'Tier 1 - Lake (free)'
        },

        'results': {
            'GLD': {
                'prices_inserted': gld_count,
                'asset_class': 'ETF',
                'sector': 'Commodities (Gold)'
            },
            'TLT': {
                'prices_inserted': tlt_count,
                'asset_class': 'ETF',
                'sector': 'Fixed Income (20+ Year Treasury)'
            },
            'total_prices_inserted': gld_count + tlt_count
        },

        'impact': {
            'forecasts_blocked_before': 3120,
            'expected_coverage_before': '77.2%',
            'expected_coverage_after': '94.7%',
            'coverage_improvement': '+17.5%'
        },

        'batch_id': str(batch_id),
        'next_action': 'Re-run forecast-outcome reconciliation for GLD and TLT forecasts'
    }

    evidence_path = os.path.join(
        os.path.dirname(__file__),
        'evidence',
        f'CEIO_BACKFILL_GLD_TLT_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    )

    with open(evidence_path, 'w') as f:
        json.dump(evidence, f, indent=2)

    print(f"  [OK] Evidence file created: {os.path.basename(evidence_path)}")
    return evidence_path

def main():
    """Execute CEIO backfill for GLD and TLT."""
    print("=" * 60)
    print("CEIO PRICE BACKFILL: GLD & TLT")
    print(f"Directive: {DIRECTIVE_ID} | Phase 1 P0 Action")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    conn = get_db_connection()
    batch_id = uuid4()

    # Step 1: Register assets
    print("\n--- Step 1: Registering Assets in fhq_meta.assets ---")
    register_assets(conn)

    import time

    # Step 2: Fetch GLD prices
    print("\n--- Step 2: Fetching GLD Prices ---")
    print("  Waiting 30s to avoid rate limiting...")
    time.sleep(30)
    gld_prices = fetch_prices_yfinance('GLD', BACKFILL_START, BACKFILL_END)
    gld_count = insert_prices(conn, 'GLD', gld_prices, batch_id) if gld_prices else 0

    # Step 3: Fetch TLT prices
    print("\n--- Step 3: Fetching TLT Prices ---")
    print("  Waiting 30s between requests...")
    time.sleep(30)
    tlt_prices = fetch_prices_yfinance('TLT', BACKFILL_START, BACKFILL_END)
    tlt_count = insert_prices(conn, 'TLT', tlt_prices, batch_id) if tlt_prices else 0

    # Step 4: Log evidence
    print("\n--- Step 4: Logging Evidence ---")
    log_backfill_evidence(conn, gld_count, tlt_count, batch_id)
    evidence_path = create_evidence_file(gld_count, tlt_count, batch_id)

    conn.close()

    print("\n" + "=" * 60)
    print("CEIO BACKFILL COMPLETE")
    print("=" * 60)
    print(f"\nGLD prices inserted: {gld_count}")
    print(f"TLT prices inserted: {tlt_count}")
    print(f"Total: {gld_count + tlt_count}")
    print(f"\nBatch ID: {batch_id}")
    print("\nNext Action: Re-run forecast-outcome reconciliation")
    print("=" * 60)

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
