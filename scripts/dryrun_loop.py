"""
SYSTEM LOOP DRY-RUN
Governance-Compliant Implementation per STIG-001 Directive
ADR-013: One-True-Source of Evidence
ADR-015: Meta-Governance - Forbidden Overstatement
"""
import psycopg2
import json
import hashlib
from datetime import datetime, timezone

conn = psycopg2.connect(host='127.0.0.1', port=54322, database='postgres', user='postgres', password='postgres')
cur = conn.cursor()

print('=== SYSTEM LOOP DRY-RUN (10 ROUNDS) ===')
print('Tests: null drift, null unauthorized writes, live execution blocked')
print('Compliance: ADR-013, ADR-015, IoS-008/012')

cur.execute('SELECT MAX(timestamp)::date FROM fhq_perception.regime_daily')
base_date = cur.fetchone()[0]

loop_traces = []
unauthorized_writes = 0
drift_detected = 0
live_breach_detected = False  # STIG-001 §A: Track live API breaches

cur.execute('SELECT COUNT(*) FROM fhq_execution.trades')
initial_trades = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM fhq_positions.target_exposure_daily')
initial_exposures = cur.fetchone()[0]

print(f'Initial State: Trades={initial_trades}, Exposures={initial_exposures}')
print('Executing 10 rounds...')

for r in range(1, 11):
    start = datetime.now(timezone.utc)

    # Read perception state
    cur.execute('SELECT asset_id, regime_classification, regime_stability_flag FROM fhq_perception.regime_daily WHERE timestamp = %s', (base_date,))
    perception = cur.fetchall()

    # Read exposure targets
    cur.execute('SELECT asset_id, exposure_constrained FROM fhq_positions.target_exposure_daily WHERE timestamp = %s', (base_date,))
    exposures = cur.fetchall()

    # Check live API block status
    cur.execute('SELECT live_api_enabled FROM fhq_governance.paper_execution_authority WHERE ios_id = %s', ('IoS-012',))
    live_api_enabled = cur.fetchone()[0]

    # STIG-001 §A: Track if live API was ever enabled (breach)
    if live_api_enabled:
        live_breach_detected = True

    # Check for unauthorized writes to trades
    cur.execute('SELECT COUNT(*) FROM fhq_execution.trades')
    trades_now = cur.fetchone()[0]
    if trades_now > initial_trades:
        unauthorized_writes += 1

    # Check for drift in exposure count
    cur.execute('SELECT COUNT(*) FROM fhq_positions.target_exposure_daily')
    exp_now = cur.fetchone()[0]
    if exp_now != initial_exposures:
        drift_detected += 1

    dur = (datetime.now(timezone.utc) - start).total_seconds() * 1000

    # Per-round status: PASS only if live was blocked this round
    round_status = 'PASS' if not live_api_enabled else 'FAIL'

    loop_traces.append({
        'round': r,
        'duration_ms': round(dur, 2),
        'perception_assets': len(perception),
        'exposure_assets': len(exposures),
        'live_api_blocked': not live_api_enabled,
        'status': round_status
    })
    print(f'  Round {r:2d}: {dur:6.2f}ms | Assets: {len(perception)} | Live Blocked: {not live_api_enabled} | {round_status}')

# Final state verification
cur.execute('SELECT COUNT(*) FROM fhq_execution.trades')
final_trades = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM fhq_positions.target_exposure_daily')
final_exposures = cur.fetchone()[0]

print(f'\nFinal State:')
print(f'  Trades: {final_trades} (delta: {final_trades - initial_trades})')
print(f'  Exposures: {final_exposures} (delta: {final_exposures - initial_exposures})')
print(f'  Unauthorized Writes: {unauthorized_writes}')
print(f'  Drift Rounds: {drift_detected}')
print(f'  Live Breach Detected: {live_breach_detected}')

# STIG-001 §A: all_pass requires live execution was 100% blocked
all_pass = (
    final_trades == initial_trades and
    final_exposures == initial_exposures and
    unauthorized_writes == 0 and
    drift_detected == 0 and
    not live_breach_detected  # STIG-001 §A: Hard requirement
)

# STIG-001 §D: Neutral result type
result = {
    'type': 'SYSTEM_LOOP_DRYRUN_RESULT',  # STIG-001 §D: Neutral type
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'executor': 'STIG',
    'rounds_executed': 10,
    'traces': loop_traces,
    'verification': {
        'null_drift': drift_detected == 0,
        'null_unauthorized_writes': unauthorized_writes == 0,
        'live_execution_blocked': not live_breach_detected,  # STIG-001 §B: Replaces null_leakage
        'initial_trades': initial_trades,
        'final_trades': final_trades,
        'initial_exposures': initial_exposures,
        'final_exposures': final_exposures
    },
    'status': 'PASS' if all_pass else 'FAIL'  # Authoritative status
}

evidence_hash = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()

# STIG-001 §C: Event type is ATTEMPT, not OK
cur.execute('''
    INSERT INTO fhq_meta.ios_audit_log
    (audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data, evidence_hash)
    VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)
''', ('SYSTEM', 'SYSTEM_LOOP_DRYRUN_ATTEMPT', datetime.now(timezone.utc), 'STIG', 'G1', json.dumps(result), evidence_hash))

conn.commit()

print(f'\n=== DRY-RUN {result["status"]} ===')
print(f'Evidence Hash: {evidence_hash}')
print(f'Compliance: ADR-013 (One-True-Source), ADR-015 (No Overstatement)')

cur.close()
conn.close()
