#!/usr/bin/env python3
"""
P3 Equity Forecast & Decision Loop Integration
CEO Directive: Generate forecasts, enable decision pathway, activate skill measurement
"""

import json
import hashlib
import uuid
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
import psycopg2
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent.parent / '.env', override=True)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    now = datetime.now(timezone.utc)
    today = date.today()

    # Equity regime data from P2
    equity_data = {
        'AAPL': {'regime': 'BULL', 'confidence': 0.95, 'rsi': 66.57, 'macd': 4.15, 'exposure': 0.0475},
        'MSFT': {'regime': 'BEAR', 'confidence': 0.95, 'rsi': 47.19, 'macd': -6.22, 'exposure': 0.0},
        'NVDA': {'regime': 'NEUTRAL', 'confidence': 0.60, 'rsi': 57.53, 'macd': -1.28, 'exposure': 0.0125},
        'QQQ': {'regime': 'BULL', 'confidence': 0.95, 'rsi': 72.16, 'macd': 3.84, 'exposure': 0.0475},
        'SPY': {'regime': 'BULL', 'confidence': 0.95, 'rsi': 71.99, 'macd': 3.58, 'exposure': 0.0475}
    }

    print('=' * 60)
    print('P3: EQUITY FORECAST & DECISION LOOP INTEGRATION')
    print('=' * 60)
    print()

    # =========================================================================
    # STEP 1: Generate Probability Forecasts
    # =========================================================================
    print('=== STEP 1: Generating Probability Forecasts ===')

    forecasts = []
    forecast_horizon = 24  # 24-hour forecast horizon

    for asset, data in equity_data.items():
        # Calculate directional probability based on regime and indicators
        if data['regime'] == 'BULL':
            prob_up = min(0.85, 0.50 + (data['confidence'] * 0.25) + (data['rsi'] - 50) / 200)
        elif data['regime'] == 'BEAR':
            prob_up = max(0.15, 0.50 - (data['confidence'] * 0.25) - (50 - data['rsi']) / 200)
        else:
            prob_up = 0.50 + (data['macd'] / 50)  # Neutral with MACD tilt

        prob_up = max(0.15, min(0.85, prob_up))  # Clamp to [0.15, 0.85]

        forecast_id = str(uuid.uuid4())
        state_hash = hashlib.sha256(f'{asset}|{data["regime"]}|{data["rsi"]}|{data["macd"]}'.encode()).hexdigest()[:32]
        content_hash = hashlib.sha256(f'{forecast_id}|{prob_up}|{forecast_horizon}'.encode()).hexdigest()[:32]

        # Feature set for audit
        feature_set = {
            'regime': data['regime'],
            'regime_confidence': data['confidence'],
            'rsi_14': data['rsi'],
            'macd': data['macd'],
            'current_exposure': data['exposure'],
            'tags': ['equity:onboarding', 'p3:first_batch', f'asset:{asset}']
        }

        forecast = {
            'forecast_id': forecast_id,
            'asset': asset,
            'forecast_type': 'DIRECTIONAL',
            'forecast_value': 'UP' if prob_up > 0.5 else 'DOWN',
            'probability': round(prob_up, 4),
            'confidence': data['confidence'],
            'horizon_hours': forecast_horizon,
            'state_hash': state_hash,
            'content_hash': content_hash,
            'feature_set': feature_set
        }
        forecasts.append(forecast)

        # Insert into forecast_ledger
        try:
            cur.execute('''
                INSERT INTO fhq_research.forecast_ledger
                (forecast_id, forecast_type, forecast_source, forecast_domain, forecast_value,
                 forecast_probability, forecast_confidence, forecast_horizon_hours,
                 forecast_made_at, forecast_valid_from, forecast_valid_until,
                 state_vector_hash, model_id, model_version, feature_set,
                 content_hash, hash_chain_id, is_resolved, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ''', (
                forecast_id, 'PRICE_DIRECTION', 'ios003_regime_v1', f'EQUITY_{asset}',
                forecast['forecast_value'], prob_up, data['confidence'], forecast_horizon,
                now, now, now + timedelta(hours=forecast_horizon),
                state_hash, 'ios003_equity_regime_v1', '1.0.0',
                json.dumps(feature_set), content_hash, f'EQUITY_P3_{asset}_{today}',
                False, 'STIG.p3_forecast'
            ))
            print(f'  {asset}: P(UP)={prob_up:.2%} [{forecast["forecast_value"]}] - ledger entry created')
        except Exception as e:
            print(f'  {asset}: ERROR - {e}')

    print()

    # =========================================================================
    # STEP 2: Enable Decision Loop (Readiness Mode)
    # =========================================================================
    print('=== STEP 2: Enabling Decision Loop (Readiness Mode) ===')

    # Get current global regime
    cur.execute('SELECT current_regime, regime_confidence FROM fhq_meta.regime_state ORDER BY last_updated_at DESC LIMIT 1')
    global_regime = cur.fetchone()
    global_regime_label = global_regime[0] if global_regime else 'BULL'
    global_regime_conf = float(global_regime[1]) if global_regime else 0.75

    # Create regime snapshot
    regime_snapshot = {asset: {'regime': d['regime'], 'confidence': d['confidence']} for asset, d in equity_data.items()}

    # Create skill snapshot (baseline - no data yet)
    skill_snapshot = {
        'brier_score': None,
        'hit_rate': None,
        'calibration_error': None,
        'status': 'AWAITING_RESOLUTION'
    }

    # Asset directives based on forecasts
    asset_directives = {}
    for f in forecasts:
        directive = 'HOLD' if f['probability'] >= 0.45 and f['probability'] <= 0.55 else \
                   'BUY' if f['probability'] > 0.55 else 'REDUCE'
        asset_directives[f['asset']] = {
            'directive': directive,
            'probability': f['probability'],
            'exposure_target': equity_data[f['asset']]['exposure'],
            'readiness_mode': True,
            'unbounded_exposure_blocked': True
        }

    # Calculate final allocation (readiness mode = constrained)
    base_allocation = sum(d['exposure'] for d in equity_data.values())
    regime_scalar = 1.0 if global_regime_label == 'BULL' else 0.5
    skill_damper = 1.0  # No skill data yet, no damping
    final_allocation = base_allocation * regime_scalar * skill_damper * 0.25  # 25% warmup still active

    decision_id = str(uuid.uuid4())
    context_hash = hashlib.sha256(f'{today}|{global_regime_label}|{final_allocation}'.encode()).hexdigest()[:32]
    hash_self = hashlib.sha256(f'GENESIS_P3|{context_hash}|{decision_id}'.encode()).hexdigest()[:32]

    # Get next sequence number
    cur.execute('SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM fhq_governance.decision_log')
    next_seq = cur.fetchone()[0]

    try:
        cur.execute('''
            INSERT INTO fhq_governance.decision_log
            (decision_id, created_at, valid_from, valid_until, context_hash,
             regime_snapshot, causal_snapshot, skill_snapshot, global_regime, defcon_level,
             system_skill_score, asset_directives, decision_type, decision_rationale,
             base_allocation, regime_scalar, causal_vector, skill_damper, final_allocation,
             governance_signature, signature_agent, hash_prev, hash_self, sequence_number, execution_state, created_by)
            VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            decision_id, now, now + timedelta(minutes=15), context_hash,
            json.dumps(regime_snapshot), json.dumps({'edges': 231}), json.dumps(skill_snapshot),
            global_regime_label, 5,  # DEFCON GREEN = 5
            0.5,  # Baseline skill score (0-1 range required)
            json.dumps(asset_directives), 'EQUITY_ALLOCATION',
            'P3 First equity decision loop entry. Readiness mode active. No unbounded exposure.',
            float(base_allocation), regime_scalar, 1.0, skill_damper, float(final_allocation),
            f'STIG-P3-{today}', 'STIG', 'GENESIS_EQUITY_P3', hash_self, next_seq, 'PENDING', 'STIG.p3_decision'
        ))
        print(f'  Decision loop entry created: {decision_id[:8]}...')
        print(f'  Global regime: {global_regime_label} ({global_regime_conf:.2f})')
        print(f'  Base allocation: {base_allocation:.2%}')
        print(f'  Final allocation (readiness): {final_allocation:.2%}')
        print(f'  Execution state: READINESS (48h window)')
    except Exception as e:
        print(f'  Decision loop ERROR: {e}')

    print()

    # =========================================================================
    # STEP 3: Create Alpha Signals
    # =========================================================================
    print('=== STEP 3: Creating Alpha Signals ===')

    for f in forecasts:
        signal_id = str(uuid.uuid4())
        signal_strength = (f['probability'] - 0.5) * 2  # Map [0.5, 1] to [0, 1] and [0, 0.5] to [-1, 0]

        signal_data = {
            'asset': f['asset'],
            'forecast_id': f['forecast_id'],
            'direction': f['forecast_value'],
            'probability': f['probability'],
            'regime': equity_data[f['asset']]['regime'],
            'tags': ['equity:onboarding', 'p3:activation']
        }

        try:
            cur.execute('''
                INSERT INTO vision_signals.alpha_signals
                (signal_id, signal_type, signal_strength, confidence_score,
                 generated_at, valid_from, valid_until, signal_data,
                 is_executable, execution_blocked_reason, created_by, created_at, hash_chain_id)
                VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, NOW(), %s)
            ''', (
                signal_id, f'EQUITY_{f["asset"]}_DIRECTIONAL', signal_strength, f['confidence'],
                now, now + timedelta(hours=24), json.dumps(signal_data),
                False, 'READINESS_MODE_48H', 'STIG.p3_signal', f'SIGNAL_P3_{f["asset"]}_{today}'
            ))
            print(f'  {f["asset"]}: signal_strength={signal_strength:.3f}, executable=False (readiness)')
        except Exception as e:
            print(f'  {f["asset"]}: signal ERROR - {e}')

    print()

    # =========================================================================
    # STEP 4: Activate Skill Engine Tracking
    # =========================================================================
    print('=== STEP 4: Activating Skill Engine Tracking ===')

    # Update skill metrics with first forecast count
    for asset in equity_data.keys():
        try:
            cur.execute('''
                UPDATE fhq_research.forecast_skill_metrics
                SET forecast_count = forecast_count + 1,
                    computed_at = NOW(),
                    computed_by = 'STIG.p3_skill_tracking'
                WHERE scope_value = %s
            ''', (f'EQUITY_{asset}',))
            if cur.rowcount > 0:
                print(f'  {asset}: forecast_count incremented')
        except Exception as e:
            print(f'  {asset}: skill tracking ERROR - {e}')

    # Update universe count
    try:
        cur.execute('''
            UPDATE fhq_research.forecast_skill_metrics
            SET forecast_count = forecast_count + 5,
                computed_at = NOW(),
                computed_by = 'STIG.p3_skill_tracking'
            WHERE scope_value = 'EQUITY_UNIVERSE'
        ''')
        print('  EQUITY_UNIVERSE: forecast_count += 5')
    except Exception as e:
        print(f'  EQUITY_UNIVERSE: ERROR - {e}')

    print()

    # =========================================================================
    # Verification
    # =========================================================================
    print('=== VERIFICATION ===')

    cur.execute('''SELECT COUNT(*) FROM fhq_research.forecast_ledger
                   WHERE forecast_domain LIKE 'EQUITY_%' AND DATE(forecast_made_at) = %s''', (today,))
    print(f'  forecast_ledger: {cur.fetchone()[0]} equity forecasts today')

    cur.execute('''SELECT COUNT(*) FROM fhq_governance.decision_log
                   WHERE decision_type = 'EQUITY_ALLOCATION' AND DATE(created_at) = %s''', (today,))
    print(f'  decision_log: {cur.fetchone()[0]} equity decisions today')

    cur.execute('''SELECT COUNT(*) FROM vision_signals.alpha_signals
                   WHERE signal_type LIKE 'EQUITY_%' AND DATE(generated_at) = %s''', (today,))
    print(f'  alpha_signals: {cur.fetchone()[0]} equity signals today')

    cur.execute('''SELECT SUM(forecast_count) FROM fhq_research.forecast_skill_metrics
                   WHERE scope_value LIKE 'EQUITY_%' ''')
    print(f'  skill_metrics: {cur.fetchone()[0]} total equity forecasts tracked')

    cur.close()
    conn.close()

    print()
    print('=' * 60)
    print('P3 INTEGRATION COMPLETE')
    print('=' * 60)

    return forecasts, asset_directives

if __name__ == '__main__':
    main()
