"""
STIG-006: Continuous Paper Engine Startup
ADR-012/ADR-013 Safety Guarantees
Loop interval: 300s (5 minutes)
"""
import psycopg2
import json
import hashlib
import time
import sys
from datetime import datetime, timezone
from decimal import Decimal

# ADR-012 Safety Config (LOCKED)
SAFETY_CONFIG = {
    'max_single_order_usd': Decimal('1000.00'),
    'max_position_usd': Decimal('10000.00'),
    'max_daily_trades': 50,
    'max_daily_turnover_usd': Decimal('50000.00'),
    'max_leverage': Decimal('1.0'),
    'live_trading_enabled': False
}

LOOP_INTERVAL = 300  # 5 minutes per directive

def get_conn():
    return psycopg2.connect(host='127.0.0.1', port=54322, database='postgres', user='postgres', password='postgres')

def verify_authority(cur):
    cur.execute('''
        SELECT execution_enabled, live_api_enabled, activation_mode
        FROM fhq_governance.paper_execution_authority WHERE ios_id = 'IoS-012'
    ''')
    row = cur.fetchone()
    if not row:
        return False, "NO_AUTHORITY"
    if row[1]:
        return False, "LIVE_API_NOT_BLOCKED"
    if not row[0]:
        return False, "EXECUTION_DISABLED"
    if row[2] != 'PAPER':
        return False, f"INVALID_MODE:{row[2]}"
    return True, "OK"

def get_signals(cur):
    cur.execute('''
        SELECT r.asset_id, r.regime_classification, r.regime_stability_flag,
               r.regime_confidence, e.exposure_constrained
        FROM fhq_perception.regime_daily r
        JOIN fhq_positions.target_exposure_daily e
            ON r.asset_id = e.asset_id AND r.timestamp = e.timestamp
        WHERE r.timestamp = (SELECT MAX(timestamp) FROM fhq_perception.regime_daily)
    ''')
    return cur.fetchall()

def calc_orders(signals):
    orders = []
    for asset_id, regime, stable, conf, exposure in signals:
        if stable and exposure > 0:
            notional = min(float(exposure) * float(SAFETY_CONFIG['max_position_usd']),
                          float(SAFETY_CONFIG['max_single_order_usd']))
            orders.append({
                'asset_id': asset_id,
                'side': 'BUY',
                'notional_usd': round(notional, 2),
                'regime': regime,
                'paper_only': True
            })
    return orders

def log_event(cur, conn, event_type, data):
    evidence_hash = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    cur.execute('''
        INSERT INTO fhq_meta.ios_audit_log
        (audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data, evidence_hash)
        VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)
    ''', ('IoS-012', event_type, datetime.now(timezone.utc), 'STIG', 'G4', json.dumps(data, default=str), evidence_hash))
    conn.commit()
    return evidence_hash

def run_loop(conn, cur, loop_num):
    start = datetime.now(timezone.utc)
    loop_id = f"PAPER_{start.strftime('%Y%m%d_%H%M%S')}_{loop_num:04d}"

    # Verify authority each loop
    ok, reason = verify_authority(cur)
    if not ok:
        return None, f"HALT:{reason}"

    # Get signals from IoS-004
    signals = get_signals(cur)
    if len(signals) == 0:
        return None, "HALT:SIGNALS_ZERO"

    # Calculate paper orders
    orders = calc_orders(signals)

    duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

    result = {
        'loop_id': loop_id,
        'loop_num': loop_num,
        'timestamp': start.isoformat(),
        'signals_count': len(signals),
        'orders_count': len(orders),
        'orders': orders,
        'duration_ms': round(duration_ms, 2),
        'safety_config': {k: str(v) for k, v in SAFETY_CONFIG.items()}
    }

    evidence_hash = log_event(cur, conn, 'PAPER_LOOP', result)

    return {
        'loop_num': loop_num,
        'signals': len(signals),
        'orders': len(orders),
        'duration_ms': round(duration_ms, 2),
        'evidence_hash': evidence_hash
    }, None

def main():
    print("=" * 60)
    print("STIG-006 ENGINE STARTED")
    print("IoS-012 Continuous Paper Engine | ADR-012/ADR-013")
    print("=" * 60)

    conn = get_conn()
    cur = conn.cursor()

    # Verify before start
    ok, reason = verify_authority(cur)
    if not ok:
        print(f"STARTUP BLOCKED: {reason}")
        return

    # Log engine activation
    activation_data = {
        'event': 'PAPER_ENGINE_ACTIVE',
        'directive': 'STIG-006',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'loop_interval': LOOP_INTERVAL,
        'safety_config': {k: str(v) for k, v in SAFETY_CONFIG.items()}
    }
    activation_hash = log_event(cur, conn, 'PAPER_ENGINE_ACTIVE', activation_data)
    print(f"Activation Hash: {activation_hash[:16]}...")
    print(f"Loop Interval: {LOOP_INTERVAL}s")
    print("-" * 60)

    loop_num = 0
    first_three = []

    try:
        while True:
            loop_num += 1
            result, error = run_loop(conn, cur, loop_num)

            if error:
                print(f"Loop {loop_num:04d}: {error}")
                # Log halt
                log_event(cur, conn, 'PAPER_ENGINE_HALT', {'reason': error, 'loop': loop_num})
                print("ENGINE HALTED - Escalate to STIG-005 diagnostics")
                break

            print(f"Loop {loop_num:04d}: signals={result['signals']}, orders={result['orders']}, {result['duration_ms']:.1f}ms | {result['evidence_hash'][:16]}...")

            # Collect first 3 for CEO report
            if loop_num <= 3:
                first_three.append(result)

            if loop_num == 3:
                print("-" * 60)
                print("FIRST 3 LOOPS COMPLETE - Continuing...")
                print("-" * 60)

            # Wait for next interval
            time.sleep(LOOP_INTERVAL)

    except KeyboardInterrupt:
        print("")
        print("-" * 60)
        print(f"Engine stopped after {loop_num} loops")
        log_event(cur, conn, 'PAPER_ENGINE_SHUTDOWN', {'loops': loop_num, 'reason': 'USER_INTERRUPT'})

    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
