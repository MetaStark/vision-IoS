"""
STIG-006: Paper Engine Startup - Initial 3 loops then continuous
"""
import psycopg2
import json
import hashlib
import time
from datetime import datetime, timezone
from decimal import Decimal

SAFETY_CONFIG = {
    'max_single_order_usd': Decimal('1000.00'),
    'max_position_usd': Decimal('10000.00'),
    'max_daily_trades': 50,
    'live_trading_enabled': False
}

CONTINUOUS_INTERVAL = 300  # 5 min for continuous mode

conn = psycopg2.connect(host='127.0.0.1', port=54322, database='postgres', user='postgres', password='postgres')
cur = conn.cursor()

print("=" * 60)
print("STIG-006 ENGINE STARTED")
print("IoS-012 Continuous Paper Engine | ADR-012/ADR-013")
print("=" * 60)

# Verify authority
cur.execute('''SELECT execution_enabled, live_api_enabled, activation_mode
               FROM fhq_governance.paper_execution_authority WHERE ios_id = 'IoS-012' ''')
row = cur.fetchone()
if not row or row[1] or not row[0] or row[2] != 'PAPER':
    print(f"STARTUP BLOCKED: {row}")
    exit(1)

# Log activation
activation = {
    'event': 'PAPER_ENGINE_ACTIVE',
    'directive': 'STIG-006',
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'mode': 'CONTINUOUS',
    'interval': CONTINUOUS_INTERVAL
}
activation_hash = hashlib.sha256(json.dumps(activation, sort_keys=True).encode()).hexdigest()
cur.execute('''INSERT INTO fhq_meta.ios_audit_log
               (audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data, evidence_hash)
               VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)''',
            ('IoS-012', 'PAPER_ENGINE_ACTIVE', datetime.now(timezone.utc), 'STIG', 'G4', json.dumps(activation), activation_hash))
conn.commit()

print(f"Activation: {activation_hash[:16]}...")
print(f"Interval: {CONTINUOUS_INTERVAL}s")
print("-" * 60)

def run_loop(loop_num):
    start = datetime.now(timezone.utc)
    loop_id = f"PAPER_{start.strftime('%Y%m%d_%H%M%S')}_{loop_num:04d}"

    # Get signals
    cur.execute('''SELECT r.asset_id, r.regime_classification, r.regime_stability_flag,
                          r.regime_confidence, e.exposure_constrained
                   FROM fhq_perception.regime_daily r
                   JOIN fhq_positions.target_exposure_daily e
                       ON r.asset_id = e.asset_id AND r.timestamp = e.timestamp
                   WHERE r.timestamp = (SELECT MAX(timestamp) FROM fhq_perception.regime_daily)''')
    signals = cur.fetchall()

    if len(signals) == 0:
        return None, "HALT:SIGNALS_ZERO"

    # Calculate orders
    orders = []
    for asset_id, regime, stable, conf, exposure in signals:
        if stable and exposure > 0:
            notional = min(float(exposure) * 10000, 1000)
            orders.append({'asset_id': asset_id, 'notional_usd': round(notional, 2), 'regime': regime, 'paper_only': True})

    duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

    result = {
        'loop_id': loop_id,
        'loop_num': loop_num,
        'signals_count': len(signals),
        'orders_count': len(orders),
        'orders': orders,
        'duration_ms': round(duration_ms, 2)
    }
    evidence_hash = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()

    cur.execute('''INSERT INTO fhq_meta.ios_audit_log
                   (audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data, evidence_hash)
                   VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)''',
                ('IoS-012', 'PAPER_LOOP', datetime.now(timezone.utc), 'STIG', 'G4', json.dumps(result), evidence_hash))
    conn.commit()

    return {'loop_num': loop_num, 'signals': len(signals), 'orders': len(orders),
            'duration_ms': round(duration_ms, 2), 'evidence_hash': evidence_hash}, None

# Run first 3 loops immediately for CEO report
loop_results = []
for i in range(1, 4):
    result, error = run_loop(i)
    if error:
        print(f"Loop {i:04d}: {error}")
        exit(1)
    loop_results.append(result)
    print(f"Loop {i:04d}: signals={result['signals']}, orders={result['orders']}, {result['duration_ms']:.1f}ms | {result['evidence_hash'][:16]}...")

print("-" * 60)
print("FIRST 3 LOOPS COMPLETE")
print("-" * 60)

# Continue with 300s interval
print(f"Continuing with {CONTINUOUS_INTERVAL}s interval (Ctrl+C to stop)...")
loop_num = 3

try:
    while True:
        time.sleep(CONTINUOUS_INTERVAL)
        loop_num += 1
        result, error = run_loop(loop_num)
        if error:
            print(f"Loop {loop_num:04d}: {error}")
            break
        print(f"Loop {loop_num:04d}: signals={result['signals']}, orders={result['orders']}, {result['duration_ms']:.1f}ms | {result['evidence_hash'][:16]}...")
except KeyboardInterrupt:
    print(f"\nEngine stopped after {loop_num} loops")
    shutdown = {'event': 'PAPER_ENGINE_SHUTDOWN', 'loops': loop_num, 'reason': 'USER_INTERRUPT'}
    shutdown_hash = hashlib.sha256(json.dumps(shutdown, sort_keys=True).encode()).hexdigest()
    cur.execute('''INSERT INTO fhq_meta.ios_audit_log
                   (audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data, evidence_hash)
                   VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)''',
                ('IoS-012', 'PAPER_ENGINE_SHUTDOWN', datetime.now(timezone.utc), 'STIG', 'G4', json.dumps(shutdown), shutdown_hash))
    conn.commit()

cur.close()
conn.close()
