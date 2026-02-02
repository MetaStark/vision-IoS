#!/usr/bin/env python3
"""
EC DRIFT RECONCILIATION REPORT
===============================
Directive: CEO-DIR-2026-RUNTIME-BINDING-AND-CALIBRATION-010 (EC Scope Lock)
Decision: Option 2 — Scope Separation

Canonical sources:
  - vega_employment_contract (fhq_meta): ALL employment contracts (21 agents)
  - ec_registry (fhq_governance): Cognitive authority tier ONLY (EC-014, EC-018, EC-020-022)

This script detects drift between the two registries:
  1. ec_registry entries that have no matching vega_employment_contract
  2. ec_registry entries with mismatched status vs vega_employment_contract
  3. Unexpected ec_registry entries outside cognitive authority scope

Schedule: Daily (recommended alongside other governance daemons)
Author: STIG (CTO) | EC-003_2026_PRODUCTION
Date: 2026-02-02
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[EC_DRIFT] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/ec_drift_reconciliation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ec_drift')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Cognitive authority tier ECs that SHOULD be in ec_registry
COGNITIVE_AUTHORITY_SCOPE = {'EC-014', 'EC-018', 'EC-020', 'EC-021', 'EC-022'}


def run_drift_check():
    """Execute the daily EC drift reconciliation."""
    logger.info("=" * 60)
    logger.info("EC DRIFT RECONCILIATION — CEO-DIR-010 Scope Lock (Option 2)")
    logger.info("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)
    findings = []
    drift_detected = False

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Get all ec_registry entries
            cur.execute("SELECT ec_id, title, role_type, status FROM fhq_governance.ec_registry ORDER BY ec_id")
            ec_entries = {r['ec_id']: dict(r) for r in cur.fetchall()}

            # 2. Get all vega_employment_contract entries
            cur.execute("""
                SELECT contract_number, employee, status, effective_date
                FROM fhq_meta.vega_employment_contract
                ORDER BY contract_number
            """)
            vec_entries = {r['contract_number']: dict(r) for r in cur.fetchall()}

        # Check 1: ec_registry should only contain COGNITIVE_AUTHORITY_SCOPE
        ec_ids_in_registry = set(ec_entries.keys())
        unexpected_in_registry = ec_ids_in_registry - COGNITIVE_AUTHORITY_SCOPE
        missing_from_registry = COGNITIVE_AUTHORITY_SCOPE - ec_ids_in_registry

        if unexpected_in_registry:
            drift_detected = True
            findings.append({
                'check': 'SCOPE_VIOLATION',
                'severity': 'HIGH',
                'detail': f"ec_registry contains non-cognitive-authority entries: {sorted(unexpected_in_registry)}",
                'action': 'These ECs should NOT be in ec_registry under Option 2'
            })
            logger.warning(f"DRIFT: Unexpected entries in ec_registry: {sorted(unexpected_in_registry)}")

        if missing_from_registry:
            drift_detected = True
            findings.append({
                'check': 'MISSING_COGNITIVE_AUTHORITY',
                'severity': 'HIGH',
                'detail': f"ec_registry missing cognitive authority entries: {sorted(missing_from_registry)}",
                'action': 'These ECs should be present in ec_registry'
            })
            logger.warning(f"DRIFT: Missing from ec_registry: {sorted(missing_from_registry)}")

        # Check 2: Status consistency for shared entries
        for ec_id in ec_ids_in_registry & set(vec_entries.keys()):
            ec_status = ec_entries[ec_id]['status']
            vec_status = vec_entries[ec_id]['status']
            if ec_status != vec_status:
                drift_detected = True
                findings.append({
                    'check': 'STATUS_MISMATCH',
                    'severity': 'MEDIUM',
                    'detail': f"{ec_id}: ec_registry.status={ec_status}, vec.status={vec_status}",
                    'action': 'Reconcile status between registries'
                })
                logger.warning(f"DRIFT: {ec_id} status mismatch: ec_registry={ec_status}, vec={vec_status}")

        # Check 3: ec_registry entries without matching vec
        for ec_id in ec_ids_in_registry - set(vec_entries.keys()):
            drift_detected = True
            findings.append({
                'check': 'ORPHANED_EC_REGISTRY',
                'severity': 'CRITICAL',
                'detail': f"{ec_id} exists in ec_registry but NOT in vega_employment_contract",
                'action': 'Investigate: ec_registry entry without canonical source'
            })
            logger.error(f"DRIFT CRITICAL: {ec_id} in ec_registry has no vec entry")

        # Summary
        logger.info(f"\nec_registry entries: {len(ec_entries)}")
        logger.info(f"vega_employment_contract entries: {len(vec_entries)}")
        logger.info(f"Scope check: ec_registry scope = {sorted(ec_ids_in_registry)}")
        logger.info(f"Expected scope: {sorted(COGNITIVE_AUTHORITY_SCOPE)}")
        logger.info(f"Drift detected: {drift_detected}")
        logger.info(f"Findings: {len(findings)}")

        if not drift_detected:
            logger.info("NO DRIFT DETECTED — Both registries are consistent with Option 2 scope lock")

        # Evidence
        report = {
            'directive': 'CEO-DIR-2026-RUNTIME-BINDING-AND-CALIBRATION-010',
            'scope_lock': 'Option 2',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'executed_by': 'STIG',
            'ec': 'EC-003',
            'ec_registry_count': len(ec_entries),
            'vec_count': len(vec_entries),
            'ec_registry_scope': sorted(ec_ids_in_registry),
            'expected_scope': sorted(COGNITIVE_AUTHORITY_SCOPE),
            'drift_detected': drift_detected,
            'findings': findings,
            'canonical_sources': {
                'all_contracts': 'fhq_meta.vega_employment_contract (21 entries)',
                'cognitive_authority': 'fhq_governance.ec_registry (5 entries)'
            }
        }

        report_json = json.dumps(report, indent=2, default=str)
        report['evidence_hash'] = hashlib.sha256(report_json.encode()).hexdigest()

        evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence_path = os.path.join(evidence_dir, f'EC_DRIFT_RECONCILIATION_{ts}.json')
        with open(evidence_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Evidence: {evidence_path}")

        return report

    finally:
        conn.close()


if __name__ == '__main__':
    run_drift_check()
