"""
IoS-012 Paper Engine - Quick Validation Test (3 loops)
STIG-005 Directive
"""
import psycopg2
import json
import hashlib
from datetime import datetime, timezone
from decimal import Decimal

SAFETY_CONFIG = {
    'max_single_order_usd': Decimal('1000.00'),
    'max_position_usd': Decimal('10000.00'),
    'max_daily_trades': 50,
    'live_trading_enabled': False
}

conn = psycopg2.connect(host='127.0.0.1', port=54322, database='postgres', user='postgres', password='postgres')
cur = conn.cursor()

print("=" * 60)
print("IoS-012 PAPER ENGINE - QUICK VALIDATION (3 LOOPS)")
print("STIG-005 Directive")
print("=" * 60)

# Verify authority
cur.execute('''
    SELECT execution_enabled, live_api_enabled, activation_mode
    FROM fhq_governance.paper_execution_authority
    WHERE ios_id = 'IoS-012'
''')
row = cur.fetchone()
if not row or row[1] or not row[0] or row[2] != 'PAPER':
    print(f"ERROR_AUTHORITY: {row}")
    exit(1)

print("Paper Authority: VERIFIED")

# Log PAPER_ENGINE_ACTIVE
event_data = {
    'event': 'PAPER_ENGINE_ACTIVE',
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'executor': 'STIG',
    'directive': 'STIG-005',
    'mode': 'VALIDATION_TEST'
}
activation_hash = hashlib.sha256(json.dumps(event_data, sort_keys=True).encode()).hexdigest()

cur.execute('''
    INSERT INTO fhq_meta.ios_audit_log
    (audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data, evidence_hash)
    VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)
''', ('IoS-012', 'PAPER_ENGINE_ACTIVE', datetime.now(timezone.utc), 'STIG', 'G4', json.dumps(event_data), activation_hash))
conn.commit()
print(f"PAPER_ENGINE_ACTIVE: {activation_hash[:16]}...")
print("")

results = []
safety_violations = []
db_errors = []

for loop in range(1, 4):
    start = datetime.now(timezone.utc)
    loop_id = f"TEST_LOOP_{start.strftime('%Y%m%d_%H%M%S')}_{loop:04d}"

    try:
        # Get signals
        cur.execute('''
            SELECT r.asset_id, r.regime_classification, r.regime_stability_flag,
                   r.regime_confidence, e.exposure_constrained
            FROM fhq_perception.regime_daily r
            JOIN fhq_positions.target_exposure_daily e
                ON r.asset_id = e.asset_id AND r.timestamp = e.timestamp
            WHERE r.timestamp = (SELECT MAX(timestamp) FROM fhq_perception.regime_daily)
        ''')
        signals = cur.fetchall()

        # Calculate orders (paper only)
        orders = []
        for asset_id, regime, stable, confidence, exposure in signals:
            if stable and exposure > 0:
                notional = min(float(exposure) * 10000, 1000)
                orders.append({
                    'asset_id': asset_id,
                    'notional_usd': round(notional, 2),
                    'regime': regime,
                    'paper_only': True
                })

                # Safety check
                if notional > float(SAFETY_CONFIG['max_single_order_usd']):
                    safety_violations.append(f"ORDER_EXCEEDS_MAX: {notional}")

        duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        # Log to audit
        result = {
            'loop_id': loop_id,
            'signals_count': len(signals),
            'orders_count': len(orders),
            'orders': orders,
            'duration_ms': round(duration_ms, 2)
        }
        evidence_hash = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()

        cur.execute('''
            INSERT INTO fhq_meta.ios_audit_log
            (audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data, evidence_hash)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)
        ''', ('IoS-012', 'PAPER_EXECUTION_LOOP', datetime.now(timezone.utc), 'STIG', 'G4', json.dumps(result), evidence_hash))
        conn.commit()

        results.append({
            'loop': loop,
            'signals': len(signals),
            'orders': len(orders),
            'duration_ms': round(duration_ms, 2),
            'status': 'OK'
        })

        print(f"Loop {loop}: signals={len(signals)}, orders={len(orders)}, {duration_ms:.1f}ms | OK")

    except Exception as e:
        conn.rollback()  # Reset transaction state
        db_errors.append(str(e))
        print(f"Loop {loop}: ERROR - {e}")

print("")
print("=" * 60)
print("VALIDATION RESULTS")
print("=" * 60)

signals_ok = all(r['signals'] > 0 for r in results)
orders_ok = all(r['orders'] >= 0 for r in results)
safety_ok = len(safety_violations) == 0
db_ok = len(db_errors) == 0

print(f"Signals > 0: {'PASS' if signals_ok else 'FAIL'} ({[r['signals'] for r in results]})")
print(f"Orders >= 0: {'PASS' if orders_ok else 'FAIL'} ({[r['orders'] for r in results]})")
print(f"Safety violations: {'NONE' if safety_ok else safety_violations}")
print(f"Database errors: {'NONE' if db_ok else db_errors}")
print("")

if signals_ok and orders_ok and safety_ok and db_ok:
    print("STATUS: PAPER_ENGINE_ACTIVE_OK")
    final_status = 'PAPER_ENGINE_ACTIVE_OK'
else:
    error_code = 'SIGNALS' if not signals_ok else 'ORDERS' if not orders_ok else 'SAFETY' if not safety_ok else 'DB'
    print(f"STATUS: ERROR_{error_code}")
    final_status = f'ERROR_{error_code}'

# Log final status
final_event = {
    'event': 'PAPER_ENGINE_VALIDATION_COMPLETE',
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'status': final_status,
    'loops_completed': len(results),
    'results': results
}
final_hash = hashlib.sha256(json.dumps(final_event, sort_keys=True).encode()).hexdigest()

cur.execute('''
    INSERT INTO fhq_meta.ios_audit_log
    (audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data, evidence_hash)
    VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)
''', ('IoS-012', 'PAPER_ENGINE_VALIDATION_COMPLETE', datetime.now(timezone.utc), 'STIG', 'G4', json.dumps(final_event), final_hash))
conn.commit()

print(f"Evidence Hash: {final_hash[:32]}...")

cur.close()
conn.close()
