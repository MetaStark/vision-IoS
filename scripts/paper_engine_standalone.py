"""
IoS-012 Paper Execution Engine - Standalone Mode
STIG-004 Directive Implementation
ADR-012: Economic Safety Enforcement
ADR-013: One-True-Source of Evidence
"""
import psycopg2
import json
import hashlib
import time
from datetime import datetime, timezone
from decimal import Decimal

# Safety Configuration (ADR-012)
SAFETY_CONFIG = {
    'max_single_order_usd': Decimal('1000.00'),
    'max_position_usd': Decimal('10000.00'),
    'max_daily_trades': 50,
    'max_daily_turnover_usd': Decimal('50000.00'),
    'max_leverage': Decimal('1.0'),
    'live_trading_enabled': False
}

LOOP_INTERVAL_SECONDS = 300  # 5 minutes

def get_connection():
    return psycopg2.connect(
        host='127.0.0.1',
        port=54322,
        database='postgres',
        user='postgres',
        password='postgres'
    )

def verify_paper_authority(cur):
    """Verify paper execution is authorized and live is blocked"""
    cur.execute('''
        SELECT execution_enabled, live_api_enabled, activation_mode
        FROM fhq_governance.paper_execution_authority
        WHERE ios_id = 'IoS-012'
    ''')
    row = cur.fetchone()
    if not row:
        return False, "NO_AUTHORITY_RECORD"

    execution_enabled, live_api_enabled, mode = row

    if live_api_enabled:
        return False, "LIVE_API_NOT_BLOCKED"
    if not execution_enabled:
        return False, "EXECUTION_DISABLED"
    if mode != 'PAPER':
        return False, f"INVALID_MODE: {mode}"

    return True, "AUTHORIZED"

def get_latest_signals(cur):
    """Get latest regime and exposure signals"""
    cur.execute('''
        SELECT
            r.asset_id,
            r.regime_classification,
            r.regime_stability_flag,
            r.regime_confidence,
            e.exposure_constrained,
            e.regime_label
        FROM fhq_perception.regime_daily r
        JOIN fhq_positions.target_exposure_daily e
            ON r.asset_id = e.asset_id AND r.timestamp = e.timestamp
        WHERE r.timestamp = (SELECT MAX(timestamp) FROM fhq_perception.regime_daily)
        ORDER BY r.asset_id
    ''')
    return cur.fetchall()

def calculate_paper_orders(signals, cur):
    """Calculate paper orders based on signals (no real execution)"""
    orders = []

    for asset_id, regime, stable, confidence, exposure, regime_label in signals:
        # Only generate orders for stable regimes with exposure > 0
        if stable and exposure > 0:
            # Paper order calculation (simplified)
            notional_usd = min(
                float(exposure) * float(SAFETY_CONFIG['max_position_usd']),
                float(SAFETY_CONFIG['max_single_order_usd'])
            )

            orders.append({
                'asset_id': asset_id,
                'side': 'BUY',
                'notional_usd': round(notional_usd, 2),
                'regime': regime,
                'confidence': float(confidence),
                'exposure_target': float(exposure),
                'paper_only': True
            })

    return orders

def log_paper_execution(cur, loop_id, signals, orders, duration_ms):
    """Log paper execution to audit log"""
    result = {
        'loop_id': loop_id,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'executor': 'STIG',
        'mode': 'PAPER',
        'signals_count': len(signals),
        'orders_generated': len(orders),
        'orders': orders,
        'duration_ms': duration_ms,
        'safety_config': {k: str(v) for k, v in SAFETY_CONFIG.items()},
        'live_execution': False
    }

    evidence_hash = hashlib.sha256(
        json.dumps(result, sort_keys=True).encode()
    ).hexdigest()

    cur.execute('''
        INSERT INTO fhq_meta.ios_audit_log
        (audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data, evidence_hash)
        VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)
    ''', (
        'IoS-012',
        'PAPER_EXECUTION_LOOP',
        datetime.now(timezone.utc),
        'STIG',
        'G4',
        json.dumps(result),
        evidence_hash
    ))

    return evidence_hash

def run_paper_loop(conn, cur, loop_count):
    """Execute one paper trading loop iteration"""
    start = datetime.now(timezone.utc)
    loop_id = f"PAPER_LOOP_{start.strftime('%Y%m%d_%H%M%S')}_{loop_count:04d}"

    # Verify authority every loop
    authorized, reason = verify_paper_authority(cur)
    if not authorized:
        print(f"  [{loop_id}] BLOCKED: {reason}")
        return None

    # Get signals
    signals = get_latest_signals(cur)

    # Calculate paper orders
    orders = calculate_paper_orders(signals, cur)

    # Calculate duration
    duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

    # Log execution
    evidence_hash = log_paper_execution(cur, loop_id, signals, orders, duration_ms)
    conn.commit()

    return {
        'loop_id': loop_id,
        'signals': len(signals),
        'orders': len(orders),
        'duration_ms': round(duration_ms, 2),
        'evidence_hash': evidence_hash[:16] + '...'
    }

def log_engine_active(cur, conn):
    """Log PAPER_ENGINE_ACTIVE event"""
    event_data = {
        'event': 'PAPER_ENGINE_ACTIVE',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'executor': 'STIG',
        'directive': 'STIG-004',
        'mode': 'STANDALONE',
        'safety_config': {k: str(v) for k, v in SAFETY_CONFIG.items()},
        'loop_interval_seconds': LOOP_INTERVAL_SECONDS
    }

    evidence_hash = hashlib.sha256(
        json.dumps(event_data, sort_keys=True).encode()
    ).hexdigest()

    cur.execute('''
        INSERT INTO fhq_meta.ios_audit_log
        (audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data, evidence_hash)
        VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)
    ''', (
        'IoS-012',
        'PAPER_ENGINE_ACTIVE',
        datetime.now(timezone.utc),
        'STIG',
        'G4',
        json.dumps(event_data),
        evidence_hash
    ))
    conn.commit()

    return evidence_hash

def main():
    print("=" * 60)
    print("IoS-012 PAPER EXECUTION ENGINE - STANDALONE MODE")
    print("STIG-004 Directive | ADR-012 Economic Safety")
    print("=" * 60)

    conn = get_connection()
    cur = conn.cursor()

    # Verify authority before starting
    authorized, reason = verify_paper_authority(cur)
    if not authorized:
        print(f"STARTUP BLOCKED: {reason}")
        cur.close()
        conn.close()
        return

    print(f"Paper Authority: VERIFIED")
    print(f"Safety Config: max_order=${SAFETY_CONFIG['max_single_order_usd']}, max_pos=${SAFETY_CONFIG['max_position_usd']}")
    print(f"Loop Interval: {LOOP_INTERVAL_SECONDS}s")
    print("")

    # Log engine activation
    activation_hash = log_engine_active(cur, conn)
    print(f"PAPER_ENGINE_ACTIVE logged: {activation_hash[:16]}...")
    print("")

    # Run initial loop
    print("Starting continuous paper loop (Ctrl+C to stop)...")
    print("-" * 60)

    loop_count = 0
    try:
        while True:
            loop_count += 1
            result = run_paper_loop(conn, cur, loop_count)

            if result:
                print(f"Loop {loop_count:4d}: {result['signals']} signals, {result['orders']} orders, {result['duration_ms']:.1f}ms | {result['evidence_hash']}")

            # Wait for next interval
            time.sleep(LOOP_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("")
        print("-" * 60)
        print(f"Paper engine stopped after {loop_count} loops")

        # Log shutdown
        shutdown_data = {
            'event': 'PAPER_ENGINE_SHUTDOWN',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'loops_completed': loop_count,
            'reason': 'USER_INTERRUPT'
        }
        shutdown_hash = hashlib.sha256(
            json.dumps(shutdown_data, sort_keys=True).encode()
        ).hexdigest()

        cur.execute('''
            INSERT INTO fhq_meta.ios_audit_log
            (audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data, evidence_hash)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)
        ''', (
            'IoS-012',
            'PAPER_ENGINE_SHUTDOWN',
            datetime.now(timezone.utc),
            'STIG',
            'G4',
            json.dumps(shutdown_data),
            shutdown_hash
        ))
        conn.commit()
        print(f"Shutdown logged: {shutdown_hash[:16]}...")

    finally:
        cur.close()
        conn.close()
        print("Connection closed.")

if __name__ == '__main__':
    main()
