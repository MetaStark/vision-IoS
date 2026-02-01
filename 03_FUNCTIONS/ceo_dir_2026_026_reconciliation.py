#!/usr/bin/env python3
"""
CEO-DIR-2026-026: Forecast-Outcome Coverage Remediation
Bulk Reconciliation Engine

Authority: CEO Directive 2026-026
Classification: CRITICAL PATH - Epistemic Infrastructure
Executed by: STIG (CTO)

This script reconciles orphaned forecasts against available price data,
creating outcomes and linking them to forecast_outcome_pairs.
"""

import os
import sys
import json
import hashlib
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

# Configuration
DIRECTIVE_ID = "CEO-DIR-2026-026"
BATCH_SIZE = 500
MAX_BATCHES = 50  # Safety limit

def json_serializer(obj):
    """Custom JSON serializer for Decimal and datetime types."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

def get_db_connection():
    """Create database connection."""
    return psycopg2.connect(
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=os.environ.get('PGPORT', '54322'),
        database=os.environ.get('PGDATABASE', 'postgres'),
        user=os.environ.get('PGUSER', 'postgres'),
        password=os.environ.get('PGPASSWORD', 'postgres')
    )

def get_orphaned_price_direction_forecasts(cursor, limit):
    """Get orphaned PRICE_DIRECTION forecasts that have price data available."""
    cursor.execute("""
        SELECT
            f.forecast_id,
            f.forecast_domain,
            f.forecast_value as predicted,
            f.forecast_probability,
            f.forecast_made_at,
            f.forecast_valid_until,
            f.content_hash,
            f.hash_chain_id
        FROM fhq_research.forecast_ledger f
        LEFT JOIN fhq_research.forecast_outcome_pairs fop ON f.forecast_id = fop.forecast_id
        WHERE fop.forecast_id IS NULL
        AND f.forecast_type = 'PRICE_DIRECTION'
        AND EXISTS (
            SELECT 1 FROM fhq_market.prices p
            WHERE UPPER(p.canonical_id) = UPPER(f.forecast_domain)
        )
        LIMIT %s
    """, (limit,))
    return cursor.fetchall()

def get_price_at_date(cursor, asset, target_date):
    """Get closing price for asset at or before target date."""
    cursor.execute("""
        SELECT close, timestamp::date as price_date
        FROM fhq_market.prices
        WHERE UPPER(canonical_id) = UPPER(%s)
        AND timestamp::date <= %s
        ORDER BY timestamp DESC
        LIMIT 1
    """, (asset, target_date))
    result = cursor.fetchone()
    return result if result else None

def reconcile_batch(conn, forecasts):
    """Reconcile a batch of forecasts."""
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    reconciled = 0
    skipped = 0

    for forecast in forecasts:
        forecast_id = forecast['forecast_id']
        domain = forecast['forecast_domain']
        predicted = forecast['predicted']
        probability = forecast['forecast_probability']
        made_at = forecast['forecast_made_at']
        valid_until = forecast['forecast_valid_until']

        # Get start and end prices
        start_price = get_price_at_date(cursor, domain, made_at.date())
        end_price = get_price_at_date(cursor, domain, valid_until.date())

        if not start_price or not end_price:
            skipped += 1
            continue

        # Determine actual direction
        actual_direction = 'UP' if end_price['close'] > start_price['close'] else 'DOWN'

        # Create outcome
        outcome_id = str(uuid4())
        content_hash = hashlib.md5(
            (actual_direction + domain + str(valid_until)).encode()
        ).hexdigest()

        evidence_data = {
            'start_price': float(start_price['close']),
            'end_price': float(end_price['close']),
            'start_date': str(start_price['price_date']),
            'end_date': str(end_price['price_date']),
            'directive': DIRECTIVE_ID
        }

        # Insert outcome
        cursor.execute("""
            INSERT INTO fhq_research.outcome_ledger (
                outcome_id, outcome_type, outcome_domain, outcome_value,
                outcome_timestamp, evidence_source, evidence_data,
                content_hash, hash_chain_id, created_by, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            outcome_id,
            'PRICE_DIRECTION',
            domain,
            actual_direction,
            valid_until,
            'fhq_market.prices',
            json.dumps(evidence_data),
            content_hash,
            f'{DIRECTIVE_ID}-RECONCILE',
            'STIG'
        ))

        # Determine if forecast was correct
        is_correct = (predicted == actual_direction)
        resolution_status = 'CORRECT' if is_correct else 'INCORRECT'

        # Calculate alignment score (0 to 1): high = confident & correct, low = confident & wrong
        # If correct: alignment = probability (confidence rewarded)
        # If wrong: alignment = 1 - probability (confidence penalized)
        alignment_score = float(probability) if is_correct else (1.0 - float(probability))

        # Calculate Brier score: (probability - outcome)^2 where outcome=1 if correct, 0 if wrong
        outcome_binary = 1.0 if is_correct else 0.0
        brier_score = (float(probability) - outcome_binary) ** 2

        # Calculate log score (bounded to avoid -inf)
        import math
        prob_clamped = max(0.001, min(0.999, float(probability)))
        log_score = math.log(prob_clamped) if is_correct else math.log(1 - prob_clamped)

        # Calculate lead time in hours
        lead_time_hours = int((valid_until - made_at).total_seconds() / 3600)

        # Insert forecast-outcome pair
        cursor.execute("""
            INSERT INTO fhq_research.forecast_outcome_pairs (
                pair_id, forecast_id, outcome_id, alignment_score,
                alignment_method, is_exact_match, brier_score, log_score,
                hit_rate_contribution, forecast_lead_time_hours, outcome_within_horizon,
                reconciled_at, reconciled_by, hash_chain_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)
        """, (
            str(uuid4()),
            str(forecast_id),
            outcome_id,
            alignment_score,
            'PRICE_DIRECTION_COMPARE',
            is_correct,
            brier_score,
            log_score,
            is_correct,  # hit_rate_contribution
            lead_time_hours,
            True,  # outcome_within_horizon
            'STIG',
            f'{DIRECTIVE_ID}-RECONCILE'
        ))

        # Update forecast_ledger
        cursor.execute("""
            UPDATE fhq_research.forecast_ledger
            SET is_resolved = true,
                resolution_status = %s,
                resolved_at = NOW(),
                outcome_id = %s
            WHERE forecast_id = %s
        """, (resolution_status, outcome_id, str(forecast_id)))

        reconciled += 1

    conn.commit()
    cursor.close()
    return reconciled, skipped

def reconcile_regime_forecasts(conn, limit):
    """Reconcile REGIME forecasts (different logic)."""
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get orphaned REGIME forecasts
    cursor.execute("""
        SELECT
            f.forecast_id,
            f.forecast_domain,
            f.forecast_value as predicted,
            f.forecast_probability,
            f.forecast_made_at,
            f.forecast_valid_until
        FROM fhq_research.forecast_ledger f
        LEFT JOIN fhq_research.forecast_outcome_pairs fop ON f.forecast_id = fop.forecast_id
        WHERE fop.forecast_id IS NULL
        AND f.forecast_type = 'REGIME'
        LIMIT %s
    """, (limit,))

    forecasts = cursor.fetchall()
    reconciled = 0

    for forecast in forecasts:
        forecast_id = forecast['forecast_id']
        domain = forecast['forecast_domain']
        predicted = forecast['predicted']
        probability = forecast['forecast_probability']
        valid_until = forecast['forecast_valid_until']

        # For regime forecasts, use the current regime state
        cursor.execute("""
            SELECT dominant_regime
            FROM fhq_perception.model_belief_state
            WHERE created_at <= %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (valid_until,))

        regime_result = cursor.fetchone()
        if not regime_result:
            continue

        actual_regime = regime_result['dominant_regime']

        # Create outcome
        outcome_id = str(uuid4())
        content_hash = hashlib.md5(
            (actual_regime + domain + str(valid_until)).encode()
        ).hexdigest()

        cursor.execute("""
            INSERT INTO fhq_research.outcome_ledger (
                outcome_id, outcome_type, outcome_domain, outcome_value,
                outcome_timestamp, evidence_source, evidence_data,
                content_hash, hash_chain_id, created_by, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            outcome_id,
            'REGIME',
            domain,
            actual_regime,
            valid_until,
            'fhq_perception.model_belief_state',
            json.dumps({'directive': DIRECTIVE_ID}),
            content_hash,
            f'{DIRECTIVE_ID}-RECONCILE',
            'STIG'
        ))

        # Determine resolution
        is_correct = (predicted.upper() == actual_regime.upper())
        resolution_status = 'CORRECT' if is_correct else 'INCORRECT'
        alignment_score = float(probability) if is_correct else (1.0 - float(probability))

        # Calculate Brier and log scores
        outcome_binary = 1.0 if is_correct else 0.0
        brier_score = (float(probability) - outcome_binary) ** 2
        import math
        prob_clamped = max(0.001, min(0.999, float(probability)))
        log_score = math.log(prob_clamped) if is_correct else math.log(1 - prob_clamped)

        # Default lead time for regime forecasts (24 hours typical)
        lead_time_hours = 24

        cursor.execute("""
            INSERT INTO fhq_research.forecast_outcome_pairs (
                pair_id, forecast_id, outcome_id, alignment_score,
                alignment_method, is_exact_match, brier_score, log_score,
                hit_rate_contribution, forecast_lead_time_hours, outcome_within_horizon,
                reconciled_at, reconciled_by, hash_chain_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)
        """, (
            str(uuid4()),
            str(forecast_id),
            outcome_id,
            alignment_score,
            'REGIME_COMPARE',
            is_correct,
            brier_score,
            log_score,
            is_correct,
            lead_time_hours,
            True,
            'STIG',
            f'{DIRECTIVE_ID}-RECONCILE'
        ))

        cursor.execute("""
            UPDATE fhq_research.forecast_ledger
            SET is_resolved = true,
                resolution_status = %s,
                resolved_at = NOW(),
                outcome_id = %s
            WHERE forecast_id = %s
        """, (resolution_status, outcome_id, str(forecast_id)))

        reconciled += 1

    conn.commit()
    cursor.close()
    return reconciled

def main():
    """Main execution."""
    print(f"=" * 60)
    print(f"CEO-DIR-2026-026: Forecast-Outcome Coverage Remediation")
    print(f"Executor: STIG | Started: {datetime.now().isoformat()}")
    print(f"=" * 60)

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get initial stats
    cursor.execute("""
        SELECT
            COUNT(*) as total_forecasts,
            COUNT(fop.forecast_id) as with_outcome,
            COUNT(*) - COUNT(fop.forecast_id) as orphaned
        FROM fhq_research.forecast_ledger f
        LEFT JOIN fhq_research.forecast_outcome_pairs fop ON f.forecast_id = fop.forecast_id
    """)
    initial_stats = cursor.fetchone()
    print(f"\nINITIAL STATE:")
    print(f"  Total Forecasts: {initial_stats['total_forecasts']}")
    print(f"  With Outcome: {initial_stats['with_outcome']}")
    print(f"  Orphaned: {initial_stats['orphaned']}")
    print(f"  Coverage: {(initial_stats['with_outcome'] / initial_stats['total_forecasts'] * 100):.1f}%")

    # Process PRICE_DIRECTION forecasts
    print(f"\n--- Processing PRICE_DIRECTION Forecasts ---")
    total_reconciled = 0
    total_skipped = 0
    batch_num = 0

    while batch_num < MAX_BATCHES:
        forecasts = get_orphaned_price_direction_forecasts(cursor, BATCH_SIZE)
        if not forecasts:
            break

        batch_num += 1
        reconciled, skipped = reconcile_batch(conn, forecasts)
        total_reconciled += reconciled
        total_skipped += skipped

        print(f"  Batch {batch_num}: Reconciled {reconciled}, Skipped {skipped}")

    print(f"\nPRICE_DIRECTION Summary:")
    print(f"  Batches Processed: {batch_num}")
    print(f"  Total Reconciled: {total_reconciled}")
    print(f"  Total Skipped: {total_skipped}")

    # Process REGIME forecasts
    print(f"\n--- Processing REGIME Forecasts ---")
    regime_reconciled = reconcile_regime_forecasts(conn, 1000)
    print(f"  REGIME Reconciled: {regime_reconciled}")

    # Get final stats
    cursor.execute("""
        SELECT
            COUNT(*) as total_forecasts,
            COUNT(fop.forecast_id) as with_outcome,
            COUNT(*) - COUNT(fop.forecast_id) as orphaned
        FROM fhq_research.forecast_ledger f
        LEFT JOIN fhq_research.forecast_outcome_pairs fop ON f.forecast_id = fop.forecast_id
    """)
    final_stats = cursor.fetchone()

    print(f"\n" + "=" * 60)
    print(f"FINAL STATE:")
    print(f"  Total Forecasts: {final_stats['total_forecasts']}")
    print(f"  With Outcome: {final_stats['with_outcome']}")
    print(f"  Orphaned: {final_stats['orphaned']}")
    print(f"  Coverage: {(final_stats['with_outcome'] / final_stats['total_forecasts'] * 100):.1f}%")
    print(f"\nCOVERAGE DELTA: {initial_stats['with_outcome']} -> {final_stats['with_outcome']}")
    print(f"Improvement: +{final_stats['with_outcome'] - initial_stats['with_outcome']} forecasts reconciled")
    print(f"=" * 60)

    # Log governance action
    cursor.execute("""
        INSERT INTO fhq_governance.governance_actions_log (
            action_id, action_type, action_target, action_target_type,
            initiated_by, initiated_at, decision, decision_rationale,
            metadata, agent_id, timestamp
        ) VALUES (
            gen_random_uuid(),
            'BULK_RECONCILIATION',
            'fhq_research.forecast_outcome_pairs',
            'TABLE',
            'STIG',
            NOW(),
            'EXECUTED',
            %s,
            %s,
            'STIG',
            NOW()
        )
    """, (
        f'CEO-DIR-2026-026 Bulk Reconciliation: {total_reconciled + regime_reconciled} forecasts reconciled',
        json.dumps({
            'directive': DIRECTIVE_ID,
            'price_direction_reconciled': total_reconciled,
            'regime_reconciled': regime_reconciled,
            'initial_coverage_pct': float(initial_stats['with_outcome'] / initial_stats['total_forecasts'] * 100),
            'final_coverage_pct': float(final_stats['with_outcome'] / final_stats['total_forecasts'] * 100)
        })
    ))
    conn.commit()

    cursor.close()
    conn.close()

    print(f"\nCompleted: {datetime.now().isoformat()}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
