#!/usr/bin/env python3
import os, sys, json, logging, argparse
from datetime import datetime, timedelta, timezone
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='[SMOKE_TEST] %(asctime)s %(levelname)s: %(message)s', handlers=[logging.FileHandler('03_FUNCTIONS/e2e_smoke_test.log'), logging.StreamHandler()])
logger = logging.getLogger('smoke_test')

DB_CONFIG = {'host': os.getenv('PGHOST', '127.0.0.1'), 'port': int(os.getenv('PGPORT', 54322)), 'database': os.getenv('PGDATABASE', 'postgres'), 'user': os.getenv('PGUSER', 'postgres'), 'password': os.getenv('PGPASSWORD', 'postgres')}

def count_new_audit_rows(conn, minutes: int = 60) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM fhq_learning.promotion_gate_audit WHERE evaluated_at >= NOW() - INTERVAL '%s minutes' AND causal_node_id IS NOT NULL AND gate_id IS NOT NULL AND state_snapshot_hash IS NOT NULL AND agent_id IS NOT NULL", (minutes,))
        count = cur.fetchone()[0]
        logger.info(f"  New audit rows (full binding, last {minutes} min): {count}")
        return count

def check_canonical_mutation_gates(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as total, SUM(CASE WHEN admission_state = 'LOCKED' THEN 1 ELSE 0 END) as locked, SUM(CASE WHEN admission_state = 'REVIEW' THEN 1 ELSE 0 END) as review, SUM(CASE WHEN admission_state = 'PROMOTE' THEN 1 ELSE 0 END) as promote, SUM(CASE WHEN admission_state = 'REJECT' THEN 1 ELSE 0 END) as reject FROM fhq_governance.canonical_mutation_gates")
        result = cur.fetchone()
        logger.info(f"  canonical_mutation_gates: total={result[0]}, LOCKED={result[1]}, REVIEW={result[2]}, PROMOTE={result[3]}, REJECT={result[4]}")
        return {'total': result[0], 'locked': result[1], 'review': result[2], 'promote': result[3], 'reject': result[4]}

def check_g5_promotion_ledger(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as total, SUM(CASE WHEN gate_id IS NOT NULL THEN 1 ELSE 0 END) as with_gate_id, SUM(CASE WHEN causal_node_id IS NOT NULL THEN 1 ELSE 0 END) as with_causal_node_id, SUM(CASE WHEN gate_id IS NOT NULL AND causal_node_id IS NOT NULL THEN 1 ELSE 0 END) as full_binding FROM fhq_canonical.g5_promotion_ledger")
        result = cur.fetchone()
        logger.info(f"  g5_promotion_ledger: total={result[0]}, with_gate_id={result[1]}, with_causal_node_id={result[2]}, full_binding={result[3]}")
        return {'total': result[0], 'with_gate_id': result[1], 'with_causal_node_id': result[2], 'full_binding': result[3]}

def test_gate_prerequisites(conn) -> dict:
    with conn.cursor() as cur:
        try:
            cur.execute("SELECT fhq_governance.fn_check_promotion_prerequisites()")
            result = cur.fetchone()
            if result and result[0]:
                logger.info("  fn_check_promotion_prerequisites(): PASS")
                return {'result': 'PASS', 'message': 'Gate prerequisites satisfied'}
            else:
                logger.warning("  fn_check_promotion_prerequisites(): FAIL - returned FALSE")
                return {'result': 'FAIL', 'message': 'Gate prerequisites not satisfied'}
        except Exception as e:
            logger.warning(f"  fn_check_promotion_prerequisites(): BLOCKED - {e}")
            return {'result': 'BLOCKED', 'message': str(e)}

def verify_enforcement_trigger(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT trigger_name, event_manipulation FROM information_schema.triggers WHERE trigger_schema = 'fhq_learning' AND trigger_name = 'trg_enforce_chain_binding_pga'")
        trigger = cur.fetchone()
        if trigger:
            logger.info(f"  Enforcement trigger: {trigger[0]} ({trigger[1]})")
            return True
        else:
            logger.error("  Enforcement trigger: NOT FOUND")
            return False

def run_smoke_test() -> dict:
    logger.info("=" * 60)
    logger.info("E2E SMOKE TEST - CEO-DIR-2026-CHAIN-WRITE-ACTIVATION-006")
    logger.info("=" * 60)
    conn = psycopg2.connect(**DB_CONFIG)
    results = {}
    try:
        logger.info("
[1] Verifying enforcement trigger...")
        results['enforcement_trigger'] = verify_enforcement_trigger(conn)
        logger.info("
[2] Checking promotion_gate_audit...")
        results['new_audit_rows'] = count_new_audit_rows(conn, minutes=60)
        logger.info("
[3] Checking canonical_mutation_gates...")
        results['canonical_mutation_gates'] = check_canonical_mutation_gates(conn)
        logger.info("
[4] Checking g5_promotion_ledger...")
        results['g5_promotion_ledger'] = check_g5_promotion_ledger(conn)
        logger.info("
[5] Testing fn_check_promotion_prerequisites()...")
        results['gate_prerequisites'] = test_gate_prerequisites(conn)
        logger.info("
" + "=" * 60)
        logger.info("SMOKE TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"  Enforcement trigger: {'OK' if results['enforcement_trigger'] else 'FAIL'}")
        logger.info(f"  New audit rows (60min): {results['new_audit_rows']}")
        logger.info(f"  Canonical gates total: {results['canonical_mutation_gates']['total']}")
        logger.info(f"  G5 full binding: {results['g5_promotion_ledger']['full_binding']}")
        logger.info(f"  Gate prerequisites: {results['gate_prerequisites']['result']}")
        evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence_path = os.path.join(evidence_dir, f'E2E_SMOKE_TEST_{ts}.json')
        evidence = {'directive': 'CEO-DIR-2026-CHAIN-WRITE-ACTIVATION-006', 'executed_at': datetime.now(timezone.utc).isoformat(), 'executed_by': 'STIG', 'results': results}
        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)
        logger.info(f"
Evidence: {evidence_path}")
        return results
    finally:
        conn.close()

def main():
    import argparse
    parser = argparse.ArgumentParser(description='E2E Smoke Test')
    args = parser.parse_args()
    results = run_smoke_test()
    critical_failures = []
    if not results.get('enforcement_trigger'):
        critical_failures.append('Enforcement trigger missing')
    if critical_failures:
        logger.error(f"
CRITICAL FAILURES: {', '.join(critical_failures)}")
        logger.error("STOP: Daemon must be patched before continuing.")
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    main()
