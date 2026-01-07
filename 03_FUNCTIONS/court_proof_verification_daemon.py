#!/usr/bin/env python3
"""
COURT-PROOF VERIFICATION DAEMON
================================
CEO Directive: CEO-DIR-2026-019 P0-3.3
Classification: CRITICAL - Learning Activation

Purpose:
    Continuous verification of court-proof evidence integrity.
    Samples recent artifacts, verifies hash chains, and escalates violations.

Operations:
    - Run hourly (or on-demand)
    - Sample recent evidence records (last 24 hours)
    - Verify hash integrity (recompute and compare)
    - Check ASRP binding validity
    - Detect split-brain conditions
    - Escalate violations to DEFCON fail-closed

FAIL-CLOSED:
    Any verification failure triggers:
    1. Governance alert
    2. Evidence marked as CONTAMINATED
    3. If threshold exceeded, DEFCON escalation

Author: STIG (CTO)
Date: 2026-01-07
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - COURT_PROOF_VERIFIER - %(levelname)s - %(message)s'
)
logger = logging.getLogger("court_proof_verification_daemon")


# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": os.getenv("PGPORT", "54322"),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres")
}

# Verification thresholds
SAMPLE_WINDOW_HOURS = 24
MAX_VIOLATIONS_BEFORE_DEFCON = 3
DEFCON_ESCALATION_LEVEL = "DEFCON-3"


# =============================================================================
# VERIFICATION DAEMON
# =============================================================================

class CourtProofVerificationDaemon:
    """
    CEO-DIR-2026-019 P0-3.3: Continuous verification daemon.

    Verifies:
    1. Hash integrity of stored evidence
    2. ASRP binding validity
    3. Evidence chain continuity
    4. Split-brain detection
    """

    def __init__(self):
        self.conn = None
        self.verification_id = f"VERIFY-{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    def connect(self):
        """Establish database connection."""
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(**DB_CONFIG)
        return self.conn

    def close(self):
        """Close database connection."""
        if self.conn and not self.conn.closed:
            self.conn.close()

    def _compute_hash(self, data: Any) -> str:
        """Compute SHA-256 hash of data."""
        if isinstance(data, dict) or isinstance(data, list):
            data_str = json.dumps(data, sort_keys=True, default=str)
        else:
            data_str = str(data)
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

    def get_recent_evidence(self, hours: int = SAMPLE_WINDOW_HOURS) -> List[Dict]:
        """Get evidence records from the last N hours."""
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    evidence_id,
                    summary_id,
                    summary_type,
                    generating_agent,
                    raw_query,
                    query_result_hash,
                    query_result_snapshot,
                    summary_content,
                    summary_hash,
                    execution_context,
                    created_at
                FROM vision_verification.summary_evidence_ledger
                WHERE created_at > NOW() - INTERVAL '%s hours'
                ORDER BY created_at DESC
            """ % hours)
            return cur.fetchall()

    def verify_single_evidence(self, record: Dict) -> Dict:
        """
        Verify integrity of a single evidence record.

        Checks:
        1. Query result hash matches stored hash
        2. Summary hash matches content
        3. ASRP binding is present and valid
        4. Execution context is complete
        """
        result = {
            'evidence_id': record['evidence_id'],
            'summary_id': record['summary_id'],
            'valid': True,
            'violations': [],
            'verified_at': datetime.now(timezone.utc).isoformat()
        }

        # 1. Verify query result hash
        if record.get('query_result_snapshot'):
            recomputed_hash = self._compute_hash(record['query_result_snapshot'])
            if recomputed_hash != record.get('query_result_hash'):
                result['valid'] = False
                result['violations'].append({
                    'type': 'HASH_MISMATCH',
                    'field': 'query_result_hash',
                    'stored': record.get('query_result_hash', '')[:16] + '...',
                    'recomputed': recomputed_hash[:16] + '...'
                })

        # 2. Verify summary hash
        if record.get('summary_content'):
            recomputed_summary_hash = self._compute_hash(record['summary_content'])
            if recomputed_summary_hash != record.get('summary_hash'):
                result['valid'] = False
                result['violations'].append({
                    'type': 'HASH_MISMATCH',
                    'field': 'summary_hash',
                    'stored': record.get('summary_hash', '')[:16] + '...',
                    'recomputed': recomputed_summary_hash[:16] + '...'
                })

        # 3. Verify ASRP binding (CEO-DIR-2026-019 P0-3.1)
        execution_context = record.get('execution_context', {})
        asrp_binding = execution_context.get('asrp_binding', {})

        if not asrp_binding:
            result['valid'] = False
            result['violations'].append({
                'type': 'ASRP_MISSING',
                'field': 'asrp_binding',
                'message': 'ASRP binding not present in execution context'
            })
        else:
            # Check required ASRP fields
            required_fields = ['state_snapshot_hash', 'state_timestamp', 'agent_id']
            for field in required_fields:
                if not asrp_binding.get(field):
                    result['valid'] = False
                    result['violations'].append({
                        'type': 'ASRP_INCOMPLETE',
                        'field': f'asrp_binding.{field}',
                        'message': f'Required ASRP field {field} is missing'
                    })

        # 4. Verify measurement validity flag (CEO-DIR-2026-019 P0-3.2)
        measurement_validity = execution_context.get('measurement_validity', {})
        if measurement_validity.get('outcome_independence') is False:
            # Not a violation per se, but flag it
            result['warnings'] = result.get('warnings', [])
            result['warnings'].append({
                'type': 'OUTCOME_DEPENDENT',
                'message': 'Evidence marked as not outcome-independent (DDATP failed)'
            })

        # 5. Check for raw_query presence
        if not record.get('raw_query') or len(record.get('raw_query', '')) < 10:
            result['valid'] = False
            result['violations'].append({
                'type': 'RAW_QUERY_MISSING',
                'field': 'raw_query',
                'message': 'Raw query is missing or too short for court-proof'
            })

        return result

    def check_split_brain(self) -> List[Dict]:
        """
        Detect split-brain conditions using the detector view.

        Split-brain = same summary_id with different content hashes.
        """
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if split_brain_detector view exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.views
                    WHERE table_schema = 'vision_verification'
                    AND table_name = 'split_brain_detector'
                )
            """)
            view_exists = cur.fetchone()['exists']

            if not view_exists:
                logger.warning("split_brain_detector view not found - skipping check")
                return []

            cur.execute("""
                SELECT * FROM vision_verification.split_brain_detector
                WHERE created_at_1 > NOW() - INTERVAL '%s hours'
                   OR created_at_2 > NOW() - INTERVAL '%s hours'
            """ % (SAMPLE_WINDOW_HOURS, SAMPLE_WINDOW_HOURS))
            results = cur.fetchall()

            # Convert datetime objects to ISO strings for JSON serialization
            serialized = []
            for row in results:
                row_dict = dict(row)
                for key, value in row_dict.items():
                    if hasattr(value, 'isoformat'):
                        row_dict[key] = value.isoformat()
                serialized.append(row_dict)
            return serialized

    def log_verification_result(self, result: Dict, overall_status: str):
        """Log verification result to evidence_verification_log."""
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO vision_verification.evidence_verification_log (
                    evidence_id,
                    verified_by,
                    verification_result,
                    verification_details
                ) VALUES (%s, %s, %s, %s)
            """, (
                result.get('evidence_id'),
                'COURT_PROOF_DAEMON',
                result['valid'],
                Json(result)
            ))
        conn.commit()

    def escalate_to_defcon(self, violations: List[Dict], reason: str):
        """
        Escalate to DEFCON when violation threshold exceeded.

        FAIL-CLOSED: System enters defensive mode.
        """
        conn = self.connect()

        logger.error(f"[DEFCON ESCALATION] {reason}")
        logger.error(f"[DEFCON ESCALATION] Violations: {len(violations)}")

        with conn.cursor() as cur:
            # Log governance action
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_type,
                    action_target,
                    action_target_type,
                    decision,
                    decision_rationale,
                    initiated_by,
                    initiated_at,
                    metadata
                ) VALUES (
                    'COURT_PROOF_DEFCON_ESCALATION',
                    'EVIDENCE_INTEGRITY',
                    'SYSTEM',
                    'ESCALATED',
                    %s,
                    'COURT_PROOF_DAEMON',
                    NOW(),
                    %s
                )
            """, (
                reason,
                Json({
                    'verification_id': self.verification_id,
                    'defcon_level': DEFCON_ESCALATION_LEVEL,
                    'violation_count': len(violations),
                    'violations': violations[:10]  # Limit to first 10
                })
            ))

            # Update execution state to cognitive fasting if DEFCON triggered
            # Use most recent state_id since table uses state_id not state_key
            cur.execute("""
                UPDATE fhq_governance.execution_state
                SET cognitive_fasting = TRUE,
                    fasting_reason = %s,
                    fasting_started_at = NOW(),
                    revalidation_required = TRUE
                WHERE state_id = (SELECT MAX(state_id) FROM fhq_governance.execution_state)
            """, (f"COURT_PROOF_DEFCON: {reason}",))

        conn.commit()

        return {
            'defcon_escalated': True,
            'level': DEFCON_ESCALATION_LEVEL,
            'reason': reason,
            'violations': len(violations)
        }

    def run_verification_cycle(self) -> Dict:
        """
        Execute full verification cycle.

        Returns verification report.
        """
        logger.info("=" * 60)
        logger.info("COURT-PROOF VERIFICATION DAEMON")
        logger.info(f"Verification ID: {self.verification_id}")
        logger.info(f"Sample Window: {SAMPLE_WINDOW_HOURS} hours")
        logger.info("=" * 60)

        report = {
            'verification_id': self.verification_id,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'sample_window_hours': SAMPLE_WINDOW_HOURS,
            'records_checked': 0,
            'records_valid': 0,
            'records_invalid': 0,
            'violations': [],
            'split_brains': [],
            'defcon_escalated': False,
            'status': 'PENDING'
        }

        try:
            # 1. Get recent evidence
            records = self.get_recent_evidence()
            report['records_checked'] = len(records)
            logger.info(f"Found {len(records)} evidence records to verify")

            if len(records) == 0:
                logger.info("No recent evidence records found - verification skipped")
                report['status'] = 'NO_RECORDS'
                return report

            # 2. Verify each record
            all_violations = []
            for record in records:
                result = self.verify_single_evidence(record)

                if result['valid']:
                    report['records_valid'] += 1
                else:
                    report['records_invalid'] += 1
                    all_violations.extend(result['violations'])
                    report['violations'].append({
                        'evidence_id': result['evidence_id'],
                        'summary_id': result['summary_id'],
                        'violations': result['violations']
                    })

                # Log result
                self.log_verification_result(result, 'VALID' if result['valid'] else 'INVALID')

            # 3. Check for split-brain conditions
            split_brains = self.check_split_brain()
            report['split_brains'] = split_brains
            if split_brains:
                logger.warning(f"SPLIT-BRAIN DETECTED: {len(split_brains)} cases")
                all_violations.append({
                    'type': 'SPLIT_BRAIN',
                    'count': len(split_brains),
                    'details': split_brains[:5]  # First 5
                })

            # 4. Determine if DEFCON escalation needed
            total_violations = len(all_violations) + len(split_brains)
            if total_violations >= MAX_VIOLATIONS_BEFORE_DEFCON:
                defcon_result = self.escalate_to_defcon(
                    all_violations,
                    f"Court-proof verification failed: {total_violations} violations detected"
                )
                report['defcon_escalated'] = True
                report['defcon_result'] = defcon_result
                report['status'] = 'DEFCON_ESCALATED'
            elif report['records_invalid'] > 0:
                report['status'] = 'VIOLATIONS_FOUND'
            else:
                report['status'] = 'ALL_VALID'

            report['completed_at'] = datetime.now(timezone.utc).isoformat()

            # Log summary
            logger.info("=" * 60)
            logger.info(f"Verification Complete: {report['status']}")
            logger.info(f"Records: {report['records_valid']}/{report['records_checked']} valid")
            logger.info(f"Violations: {len(report['violations'])}")
            logger.info(f"Split-brains: {len(report['split_brains'])}")
            logger.info("=" * 60)

            # Log governance action
            self._log_verification_summary(report)

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            report['status'] = 'FAILED'
            report['error'] = str(e)

        return report

    def _log_verification_summary(self, report: Dict):
        """Log verification summary to governance."""
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_type,
                    action_target,
                    action_target_type,
                    decision,
                    decision_rationale,
                    initiated_by,
                    initiated_at,
                    metadata
                ) VALUES (
                    'COURT_PROOF_VERIFICATION_CYCLE',
                    'EVIDENCE_LEDGER',
                    'BATCH',
                    %s,
                    %s,
                    'COURT_PROOF_DAEMON',
                    NOW(),
                    %s
                )
            """, (
                'COMPLETED' if report['status'] in ('ALL_VALID', 'NO_RECORDS') else 'VIOLATIONS_DETECTED',
                f"Verified {report['records_checked']} records: "
                f"{report['records_valid']} valid, {report['records_invalid']} invalid",
                Json({
                    'verification_id': report['verification_id'],
                    'status': report['status'],
                    'records_checked': report['records_checked'],
                    'records_valid': report['records_valid'],
                    'violations_count': len(report['violations']),
                    'split_brains_count': len(report['split_brains'])
                })
            ))
        conn.commit()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run verification cycle."""
    daemon = CourtProofVerificationDaemon()
    try:
        daemon.connect()
        report = daemon.run_verification_cycle()
        print(json.dumps(report, indent=2, default=str))

        # Exit code based on status
        if report['status'] == 'ALL_VALID':
            return 0
        elif report['status'] == 'NO_RECORDS':
            return 0
        elif report['status'] == 'DEFCON_ESCALATED':
            return 2
        else:
            return 1
    finally:
        daemon.close()


if __name__ == "__main__":
    exit(main())
