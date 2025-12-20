"""
WAVE-001 PATCH: W001-D — CALC_INDICATORS Timeout Fix
=====================================================
Target: calc_indicators_v1.py
Issue: 300s timeout due to slow row-by-row iteration
Root Cause: Non-vectorized processing, no batching, no progress checkpoints
Fix: Vectorize indicator persistence, add batch processing

Author: STIG (CTO)
Date: 2025-12-03
Authority: CEO_DIRECTIVE_WAVE001_20251203
"""

# PATCH INSTRUCTIONS:
# Apply to: 03_FUNCTIONS/calc_indicators_v1.py

# CHANGE 1: Vectorize persist_momentum_indicators (replace lines 230-276)
# Replace the row-by-row loop with vectorized batch insert:

"""
def persist_momentum_indicators_optimized(conn, asset_id: str, price_df: pd.DataFrame):
    '''Optimized batch persistence for momentum indicators.'''

    # Calculate all indicators at once (already vectorized)
    rsi = calc_rsi(price_df['close'])
    stoch_rsi = calc_stoch_rsi(price_df['close'])
    cci = calc_cci(price_df['high'], price_df['low'], price_df['close'])
    mfi = calc_mfi(price_df['high'], price_df['low'], price_df['close'], price_df['volume'])

    # Create DataFrame for batch insert
    indicators_df = pd.DataFrame({
        'timestamp': price_df.index,
        'rsi_14': rsi,
        'stoch_rsi_14': stoch_rsi,
        'cci_20': cci,
        'mfi_14': mfi
    }).dropna(subset=['rsi_14'])  # Filter once

    if indicators_df.empty:
        return

    # Batch prepare rows
    rows = []
    for _, row in indicators_df.iterrows():
        value_json = {
            "rsi_14": float(row['rsi_14']) if pd.notna(row['rsi_14']) else None,
            "stoch_rsi_14": float(row['stoch_rsi_14']) if pd.notna(row['stoch_rsi_14']) else None,
            "cci_20": float(row['cci_20']) if pd.notna(row['cci_20']) else None,
            "mfi_14": float(row['mfi_14']) if pd.notna(row['mfi_14']) else None
        }
        lineage_hash = compute_lineage_hash(asset_id, str(row['timestamp']), FORMULA_HASH, json.dumps(value_json))
        rows.append((
            str(uuid.uuid4()),
            row['timestamp'],
            asset_id,
            json.dumps(value_json),
            ENGINE_VERSION,
            FORMULA_HASH,
            lineage_hash,
            datetime.now(timezone.utc)
        ))

    # Batch insert with larger page_size
    if rows:
        with conn.cursor() as cur:
            execute_values(cur, '''
                INSERT INTO fhq_research.indicator_momentum
                (id, timestamp, asset_id, value_json, engine_version, formula_hash, lineage_hash, created_at)
                VALUES %s
                ON CONFLICT (id) DO NOTHING
            ''', rows, page_size=5000)  # Increased from default 100
        conn.commit()
        logger.info(f"  [MOMENTUM] Inserted {len(rows)} rows for {asset_id}")
"""

# CHANGE 2: Add progress logging in run_calc_indicators (line 447)
# ADD inside the asset loop:
#     logger.info(f"\n[{i+1}/{len(assets)}] Processing {asset_id}...")

# CHANGE 3: Add explicit commit after each asset to prevent long transactions
# ADD after line 462 (after all persist calls):
#     conn.commit()
#     logger.info(f"  Checkpoint: {asset_id} complete")

# CHANGE 4: Add batch size configuration
# ADD after line 52:
#     BATCH_SIZE = 5000  # Rows per batch insert
#     COMMIT_INTERVAL = 1  # Commit after each asset

PATCH_ID = "W001-D"
PATCH_TARGET = "calc_indicators_v1.py"
PATCH_ISSUE = "300s timeout from slow row-by-row iteration"
PATCH_FIX = "Vectorize processing, increase batch size, add checkpoints"
