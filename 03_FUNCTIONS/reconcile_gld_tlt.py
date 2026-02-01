#!/usr/bin/env python3
"""
Reconcile GLD and TLT Forecasts with newly backfilled prices
CEO-DIR-2026-030 Phase 1 - Coverage Improvement
"""

import os
import json
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from uuid import uuid4

BATCH_SIZE = 500

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=os.environ.get('PGPORT', '54322'),
        database=os.environ.get('PGDATABASE', 'postgres'),
        user=os.environ.get('PGUSER', 'postgres'),
        password=os.environ.get('PGPASSWORD', 'postgres')
    )

def reconcile_asset(conn, asset):
    """Reconcile all unreconciled forecasts for an asset."""
    cursor = conn.cursor()

    # Get unreconciled forecasts for this asset
    cursor.execute("""
        SELECT
            f.forecast_id,
            f.forecast_domain,
            f.forecast_value,
            f.forecast_probability,
            f.forecast_made_at,
            f.forecast_valid_until
        FROM fhq_research.forecast_ledger f
        LEFT JOIN fhq_research.forecast_outcome_pairs fop ON f.forecast_id = fop.forecast_id
        WHERE f.forecast_domain = %s
        AND f.forecast_type = 'PRICE_DIRECTION'
        AND fop.pair_id IS NULL
        ORDER BY f.forecast_made_at
    """, (asset,))

    forecasts = cursor.fetchall()
    print(f"  Found {len(forecasts)} unreconciled forecasts for {asset}")

    if not forecasts:
        cursor.close()
        return 0

    # Get price data for this asset
    cursor.execute("""
        SELECT timestamp::date as price_date, close
        FROM fhq_market.prices
        WHERE canonical_id = %s
        ORDER BY timestamp
    """, (asset,))

    prices = {row[0]: row[1] for row in cursor.fetchall()}
    print(f"  Loaded {len(prices)} price records for {asset}")

    if not prices:
        print(f"  [!] No prices available for {asset}")
        cursor.close()
        return 0

    # Process forecasts in batches
    total_reconciled = 0
    batch = []

    for forecast in forecasts:
        forecast_id, domain, value, probability, made_at, valid_until = forecast

        # Get price at forecast time and outcome time
        forecast_date = made_at.date()
        outcome_date = valid_until.date()

        # Find closest available price dates
        price_at_forecast = None
        price_at_outcome = None

        for d in sorted(prices.keys()):
            if d <= forecast_date:
                price_at_forecast = prices[d]
            if d <= outcome_date:
                price_at_outcome = prices[d]

        if price_at_forecast is None or price_at_outcome is None:
            continue

        # Determine actual outcome
        actual_direction = 'UP' if price_at_outcome > price_at_forecast else 'DOWN'
        is_correct = (value == actual_direction)

        # Calculate scores
        prob = float(probability) if probability else 0.5
        outcome_binary = 1.0 if is_correct else 0.0

        # Brier score: (probability - outcome)^2
        brier_score = (prob - outcome_binary) ** 2

        # Alignment score (0-1, higher is better)
        alignment_score = prob if is_correct else (1.0 - prob)

        # Lead time
        lead_time_hours = int((valid_until - made_at).total_seconds() / 3600)

        # Create outcome record
        outcome_id = uuid4()
        import hashlib
        content_hash = hashlib.sha256(f"{domain}|{actual_direction}|{valid_until}".encode()).hexdigest()[:32]

        # Outcome record for outcome_ledger
        outcome_record = (
            str(outcome_id),
            'PRICE_DIRECTION',
            domain,
            actual_direction,
            valid_until,
            'fhq_market.prices',
            json.dumps({'price_before': price_at_forecast, 'price_after': price_at_outcome}),
            content_hash,
            f'CEO-DIR-2026-030-{asset}',
            'STIG',
            datetime.now()
        )

        # Pair record for forecast_outcome_pairs
        pair_record = (
            str(uuid4()),           # pair_id
            str(forecast_id),       # forecast_id
            str(outcome_id),        # outcome_id
            alignment_score,        # alignment_score
            'PRICE_COMPARISON',     # alignment_method
            True,                   # is_exact_match
            brier_score,            # brier_score
            None,                   # log_score
            is_correct,             # hit_rate_contribution
            lead_time_hours,        # forecast_lead_time_hours
            True,                   # outcome_within_horizon
            datetime.now(),         # reconciled_at
            'STIG',                 # reconciled_by
            f'CEO-DIR-2026-030-{asset}'  # hash_chain_id
        )

        batch.append((outcome_record, pair_record))

        if len(batch) >= BATCH_SIZE:
            inserted = insert_batch(conn, batch)
            total_reconciled += inserted
            print(f"    Batch complete: {total_reconciled} reconciled so far")
            batch = []

    # Insert remaining
    if batch:
        inserted = insert_batch(conn, batch)
        total_reconciled += inserted

    cursor.close()
    return total_reconciled

def insert_batch(conn, batch):
    """Insert a batch of reconciliation records (outcomes + pairs)."""
    cursor = conn.cursor()

    # Extract outcomes and pairs from batch
    outcomes = [item[0] for item in batch]
    pairs = [item[1] for item in batch]

    # First insert outcomes
    execute_values(cursor, """
        INSERT INTO fhq_research.outcome_ledger (
            outcome_id, outcome_type, outcome_domain, outcome_value,
            outcome_timestamp, evidence_source, evidence_data, content_hash,
            hash_chain_id, created_by, created_at
        ) VALUES %s
        ON CONFLICT DO NOTHING
    """, outcomes)

    # Then insert pairs
    execute_values(cursor, """
        INSERT INTO fhq_research.forecast_outcome_pairs (
            pair_id, forecast_id, outcome_id, alignment_score, alignment_method,
            is_exact_match, brier_score, log_score, hit_rate_contribution,
            forecast_lead_time_hours, outcome_within_horizon, reconciled_at,
            reconciled_by, hash_chain_id
        ) VALUES %s
        ON CONFLICT DO NOTHING
    """, pairs)

    inserted = cursor.rowcount
    conn.commit()
    cursor.close()
    return inserted

def main():
    print("=" * 60)
    print("GLD/TLT FORECAST RECONCILIATION")
    print(f"CEO-DIR-2026-030 Phase 1 Coverage Improvement")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    conn = get_db_connection()

    print("\n--- Reconciling GLD Forecasts ---")
    gld_count = reconcile_asset(conn, 'GLD')
    print(f"  [OK] GLD: {gld_count} forecasts reconciled")

    print("\n--- Reconciling TLT Forecasts ---")
    tlt_count = reconcile_asset(conn, 'TLT')
    print(f"  [OK] TLT: {tlt_count} forecasts reconciled")

    # Log to governance
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO fhq_governance.governance_actions_log (
            action_id, action_type, action_target, action_target_type,
            initiated_by, initiated_at, decision, decision_rationale,
            metadata, agent_id, timestamp
        ) VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, NOW())
    """, (
        str(uuid4()),
        'FORECAST_RECONCILIATION',
        'GLD,TLT',
        'FORECAST_OUTCOME_PAIRS',
        'STIG',
        'EXECUTED',
        f'Reconciled {gld_count + tlt_count} forecasts for GLD/TLT using backfilled prices',
        json.dumps({
            'directive': 'CEO-DIR-2026-030',
            'phase': 'PHASE_1_TRUTH_AND_CALIBRATION',
            'gld_reconciled': gld_count,
            'tlt_reconciled': tlt_count,
            'total_reconciled': gld_count + tlt_count
        }),
        'STIG'
    ))
    conn.commit()
    cursor.close()

    conn.close()

    print("\n" + "=" * 60)
    print("RECONCILIATION COMPLETE")
    print(f"GLD: {gld_count} | TLT: {tlt_count} | Total: {gld_count + tlt_count}")
    print("=" * 60)

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
