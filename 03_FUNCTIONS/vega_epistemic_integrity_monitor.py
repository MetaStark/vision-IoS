#!/usr/bin/env python3
"""
VEGA EPISTEMIC INTEGRITY MONITOR (R4)
=====================================
CEO Directive: CEO-DIR-2026-009-B, CEO-DIR-2026-010
Classification: STRATEGIC-CONSTITUTIONAL (Class A+)
CNRP Phase: R4 - Epistemic Integrity Monitoring

Purpose:
    Continuous monitoring of lineage and hash integrity across all
    cognitive assets. Immediate CEO escalation on any violation.

Constitutional Basis:
    - ADR-011: Fortress & VEGA Testsuite (hash chain integrity)
    - ADR-013: One-True-Source (canonical lineage)
    - ADR-017: LIDS Truth Engine (epistemic trust)
    - CEO-DIR-2026-009-B Section 6
    - CEO-DIR-2026-010 Part III (Automated DEFCON Escalation)

Escalation:
    - Immediate CEO notification on integrity violation
    - CEO-DIR-2026-010: Automated DEFCON YELLOW when staleness > 24h
      (No human approval required - system-driven)

Schedule: */15 * * * * (Every 15 minutes)
Gate: G1 (VEGA authority - highest)
"""

import os
import sys
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("vega_epistemic_monitor")

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

# Integrity thresholds from CEO-DIR-2026-009-B
STALENESS_THRESHOLD_HOURS = 24
CAUSAL_STALENESS_THRESHOLD_HOURS = 48
HASH_MISSING_THRESHOLD_PCT = 0.0  # Zero tolerance for missing hashes
SPLIT_BRAIN_THRESHOLD = 0.01  # 1% divergence triggers alert

# CEO-DIR-2026-010: Automated DEFCON Escalation
AUTO_DEFCON_ESCALATION_ENABLED = True  # No human discretion
DEFCON_ESCALATION_STALENESS_HOURS = 24  # >24h = auto YELLOW

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Establish database connection"""
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# INTEGRITY CHECK FUNCTIONS
# =============================================================================

def check_evidence_staleness(conn) -> Dict[str, Any]:
    """Check evidence_nodes staleness against constitutional threshold"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                COUNT(*) as total_nodes,
                COUNT(*) FILTER (WHERE updated_at > NOW() - INTERVAL '%s hours') as fresh_nodes,
                COUNT(*) FILTER (WHERE updated_at <= NOW() - INTERVAL '%s hours') as stale_nodes,
                MAX(updated_at) as most_recent,
                EXTRACT(EPOCH FROM (NOW() - MAX(updated_at)))/3600 as hours_since_update
            FROM fhq_canonical.evidence_nodes
        """ % (STALENESS_THRESHOLD_HOURS, STALENESS_THRESHOLD_HOURS))
        result = cur.fetchone()

        hours_stale = float(result['hours_since_update'] or 0)
        is_compliant = hours_stale <= STALENESS_THRESHOLD_HOURS

        return {
            'total_nodes': result['total_nodes'] or 0,
            'fresh_nodes': result['fresh_nodes'] or 0,
            'stale_nodes': result['stale_nodes'] or 0,
            'hours_since_update': round(hours_stale, 2),
            'threshold_hours': STALENESS_THRESHOLD_HOURS,
            'is_compliant': is_compliant,
            'status': 'COMPLIANT' if is_compliant else 'VIOLATION'
        }


def check_hash_chain_integrity(conn) -> Dict[str, Any]:
    """Verify hash chain integrity across evidence nodes"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check for missing hashes
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE content_hash IS NULL) as missing_hash,
                COUNT(*) FILTER (WHERE content_hash IS NOT NULL) as valid_hash,
                COUNT(*) as total_nodes
            FROM fhq_canonical.evidence_nodes
        """)
        result = cur.fetchone()

        total = result['total_nodes'] or 0
        missing = result['missing_hash'] or 0
        missing_pct = (missing / total * 100) if total > 0 else 0

        is_compliant = missing_pct <= HASH_MISSING_THRESHOLD_PCT

        return {
            'total_nodes': total,
            'missing_hash': missing,
            'valid_hash': result['valid_hash'] or 0,
            'missing_pct': round(missing_pct, 4),
            'threshold_pct': HASH_MISSING_THRESHOLD_PCT,
            'is_compliant': is_compliant,
            'status': 'COMPLIANT' if is_compliant else 'VIOLATION'
        }


def verify_content_hash_samples(conn, sample_size: int = 50) -> Dict[str, Any]:
    """Verify content hash matches actual content for random samples (fresh nodes only)

    Uses PostgreSQL's hash_evidence_content function directly to avoid format mismatches.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Use PostgreSQL to compute expected hash - avoids Python/PG format differences
        cur.execute("""
            SELECT
                evidence_id,
                content_hash,
                fhq_canonical.hash_evidence_content(content, source_type, data_timestamp) as expected_hash
            FROM fhq_canonical.evidence_nodes
            WHERE content_hash IS NOT NULL
              AND updated_at > NOW() - INTERVAL '24 hours'
            ORDER BY RANDOM()
            LIMIT %s
        """, [sample_size])

        rows = cur.fetchall()
        verified = 0
        failed = 0
        failed_ids = []

        for row in rows:
            if row['content_hash'] == row['expected_hash']:
                verified += 1
            else:
                failed += 1
                failed_ids.append(str(row['evidence_id']))

        is_compliant = failed == 0

        return {
            'samples_checked': len(rows),
            'verified': verified,
            'failed': failed,
            'failed_ids': failed_ids[:10],  # Limit to first 10
            'is_compliant': is_compliant,
            'status': 'COMPLIANT' if is_compliant else 'HASH_MISMATCH'
        }


def check_cnrp_cycle_health(conn) -> Dict[str, Any]:
    """Check health of CNRP R1-R3 execution cycle"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check latest execution of each phase
        cur.execute("""
            WITH latest_per_phase AS (
                SELECT DISTINCT ON (phase)
                    phase, daemon_name, status, completed_at,
                    EXTRACT(EPOCH FROM (NOW() - completed_at))/3600 as hours_ago
                FROM fhq_governance.cnrp_execution_log
                ORDER BY phase, completed_at DESC
            )
            SELECT * FROM latest_per_phase
            ORDER BY phase
        """)
        results = cur.fetchall()

        phases = {}
        all_healthy = True

        for row in results:
            phase = row['phase']
            hours_ago = float(row['hours_ago'] or 999)

            # Define expected frequency per phase
            expected_hours = {
                'R1': 4,   # Every 4 hours
                'R2': 4,   # Every 4 hours (30 min after R1)
                'R3': 24,  # Daily
                'R4': 0.25  # Every 15 minutes
            }.get(phase, 24)

            is_healthy = hours_ago <= expected_hours * 1.5  # Allow 50% buffer

            phases[phase] = {
                'daemon': row['daemon_name'],
                'status': row['status'],
                'hours_ago': round(hours_ago, 2),
                'expected_hours': expected_hours,
                'is_healthy': is_healthy
            }

            if not is_healthy or row['status'] != 'SUCCESS':
                all_healthy = False

        return {
            'phases': phases,
            'all_healthy': all_healthy,
            'status': 'HEALTHY' if all_healthy else 'DEGRADED'
        }


def check_lineage_continuity(conn) -> Dict[str, Any]:
    """Check for lineage breaks in evidence chain"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if evidence_relationships maintains continuity
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'fhq_canonical'
                  AND table_name = 'evidence_relationships'
            )
        """)

        if not cur.fetchone()['exists']:
            return {
                'lineage_breaks': 0,
                'total_relationships': 0,
                'is_compliant': True,
                'status': 'TABLE_NOT_EXISTS'
            }

        # Check for orphaned relationships (referencing non-existent nodes)
        cur.execute("""
            WITH orphan_check AS (
                SELECT r.relationship_id,
                    EXISTS (SELECT 1 FROM fhq_canonical.evidence_nodes WHERE evidence_id = r.from_evidence_id) as source_exists,
                    EXISTS (SELECT 1 FROM fhq_canonical.evidence_nodes WHERE evidence_id = r.to_evidence_id) as target_exists
                FROM fhq_canonical.evidence_relationships r
            )
            SELECT
                COUNT(*) FILTER (WHERE NOT source_exists OR NOT target_exists) as lineage_breaks,
                COUNT(*) as total_relationships
            FROM orphan_check
        """)
        result = cur.fetchone()

        breaks = result['lineage_breaks'] or 0
        total = result['total_relationships'] or 0
        break_rate = (breaks / total * 100) if total > 0 else 0

        is_compliant = break_rate < 5  # Less than 5% breaks

        return {
            'lineage_breaks': breaks,
            'total_relationships': total,
            'break_rate_pct': round(break_rate, 2),
            'is_compliant': is_compliant,
            'status': 'COMPLIANT' if is_compliant else 'LINEAGE_DEGRADED'
        }


def check_ios010_forecast_integrity(conn) -> Dict[str, Any]:
    """Check IoS-010 forecast ledger integrity"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if forecast_ledger exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'fhq_research'
                  AND table_name = 'forecast_ledger'
            )
        """)

        if not cur.fetchone()['exists']:
            return {
                'forecast_integrity': 'TABLE_NOT_EXISTS',
                'is_compliant': True
            }

        # Check forecast statistics
        cur.execute("""
            SELECT
                COUNT(*) as total_forecasts,
                COUNT(*) FILTER (WHERE is_resolved = FALSE) as pending,
                COUNT(*) FILTER (WHERE is_resolved = TRUE) as resolved,
                COUNT(*) FILTER (WHERE is_resolved = FALSE AND forecast_valid_until < NOW()) as expired_unresolved
            FROM fhq_research.forecast_ledger
        """)
        result = cur.fetchone()

        # Check if outcome capture is working
        cur.execute("""
            SELECT COUNT(*) as outcome_count
            FROM fhq_research.outcome_ledger
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        outcome_result = cur.fetchone()

        return {
            'total_forecasts': result['total_forecasts'] or 0,
            'pending': result['pending'] or 0,
            'resolved': result['resolved'] or 0,
            'expired_unresolved': result['expired_unresolved'] or 0,
            'recent_outcomes': outcome_result['outcome_count'] or 0,
            'is_compliant': True,  # Informational check
            'status': 'OPERATIONAL'
        }


def escalate_to_ceo(conn, violation_type: str, details: Dict) -> str:
    """Escalate integrity violation to CEO"""
    escalation_id = f"VEGA-ESC-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    logger.critical(f"CEO ESCALATION: {violation_type}")
    logger.critical(f"Details: {json.dumps(details, indent=2, default=str)}")

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_type,
                action_target,
                action_target_type,
                initiated_by,
                decision,
                decision_rationale,
                metadata
            ) VALUES (
                'VEGA_CEO_ESCALATION',
                'EPISTEMIC_INTEGRITY',
                'INTEGRITY_VIOLATION',
                'VEGA',
                'ESCALATED',
                'CEO-DIR-2026-009-B: Immediate CEO escalation on integrity violation',
                %s
            )
            RETURNING action_id
        """, (json.dumps({
            'escalation_id': escalation_id,
            'violation_type': violation_type,
            'directive': 'CEO-DIR-2026-009-B',
            'severity': 'CRITICAL',
            'details': details,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'requires_acknowledgment': True
        }, default=str),))

    return escalation_id


def auto_escalate_defcon(conn, staleness_hours: float) -> Optional[str]:
    """
    CEO-DIR-2026-010: Automated DEFCON Escalation

    When evidence staleness > 24h, automatically escalate to DEFCON YELLOW.
    No human approval required. This is system-driven.
    """
    if not AUTO_DEFCON_ESCALATION_ENABLED:
        return None

    if staleness_hours <= DEFCON_ESCALATION_STALENESS_HOURS:
        return None  # No escalation needed

    escalation_id = f"DEFCON-AUTO-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    logger.critical("=" * 60)
    logger.critical("AUTOMATED DEFCON ESCALATION - CEO-DIR-2026-010")
    logger.critical(f"Evidence staleness: {staleness_hours:.2f}h > {DEFCON_ESCALATION_STALENESS_HOURS}h threshold")
    logger.critical("Escalating to DEFCON YELLOW (automated, no human approval)")
    logger.critical("=" * 60)

    with conn.cursor() as cur:
        # Check current DEFCON level
        cur.execute("""
            SELECT defcon_level FROM fhq_governance.defcon_state
            WHERE is_current = true
            ORDER BY triggered_at DESC LIMIT 1
        """)
        current = cur.fetchone()
        current_level = current[0] if current else 'GREEN'

        if current_level == 'YELLOW':
            logger.info("Already at DEFCON YELLOW, no transition needed")
            return None

        # Mark current state as not current
        cur.execute("""
            UPDATE fhq_governance.defcon_state
            SET is_current = false
            WHERE is_current = true
        """)

        # Insert new YELLOW state
        cur.execute("""
            INSERT INTO fhq_governance.defcon_state (
                state_id, defcon_level, triggered_at, triggered_by,
                trigger_reason, is_current
            ) VALUES (
                gen_random_uuid(), 'YELLOW', NOW(), 'VEGA-AUTOMATED',
                %s, true
            )
        """, (f"CEO-DIR-2026-010: Automated escalation - evidence staleness {staleness_hours:.2f}h > {DEFCON_ESCALATION_STALENESS_HOURS}h threshold",))

        # Log to governance
        cur.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_type,
                action_target,
                action_target_type,
                initiated_by,
                decision,
                decision_rationale,
                metadata
            ) VALUES (
                'DEFCON_AUTO_ESCALATION',
                'DEFCON_STATE',
                'AUTOMATED_TRANSITION',
                'VEGA-AUTOMATED',
                'GREEN_TO_YELLOW',
                'CEO-DIR-2026-010: Human discretion explicitly removed from this pathway',
                %s
            )
        """, (json.dumps({
            'escalation_id': escalation_id,
            'directive': 'CEO-DIR-2026-010',
            'from_level': current_level,
            'to_level': 'YELLOW',
            'trigger': 'EVIDENCE_STALENESS',
            'staleness_hours': staleness_hours,
            'threshold_hours': DEFCON_ESCALATION_STALENESS_HOURS,
            'automated': True,
            'human_approval_required': False,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, default=str),))

    logger.critical(f"DEFCON YELLOW activated: {escalation_id}")
    return escalation_id


def log_cnrp_execution(conn, cycle_id: str, status: str, metadata: Dict,
                       started_at: datetime = None) -> str:
    """Log CNRP R4 execution with proper latency instrumentation.

    CEO-DIR-2026-047 GAP-004: Latency must be measured as completed_at - started_at.
    The started_at timestamp must be captured BEFORE execution begins.
    """
    completed_at = datetime.now(timezone.utc)
    evidence_hash = hashlib.sha256(json.dumps(metadata, default=str).encode()).hexdigest()

    # Calculate actual latency for metrics
    if started_at:
        latency_ms = (completed_at - started_at).total_seconds() * 1000
        metadata['latency_ms'] = round(latency_ms, 2)
        metadata['latency_instrumented'] = True
    else:
        metadata['latency_instrumented'] = False

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.cnrp_execution_log (
                cycle_id, phase, daemon_name, status, records_processed,
                evidence_hash, metadata, started_at, completed_at
            ) VALUES (%s, 'R4', 'vega_epistemic_integrity_monitor', %s, %s, %s, %s, %s, %s)
            RETURNING execution_id
        """, (
            cycle_id, status,
            metadata.get('total_checks', 0),
            evidence_hash,
            json.dumps(metadata, default=str),
            started_at, completed_at
        ))
        return str(cur.fetchone()[0])


def run_integrity_monitor() -> Dict[str, Any]:
    """Main execution function for R4 Epistemic Integrity Monitor"""
    logger.info("=" * 60)
    logger.info("CNRP-001 PHASE R4: VEGA EPISTEMIC INTEGRITY MONITOR")
    logger.info("Directive: CEO-DIR-2026-009-B")
    logger.info("=" * 60)

    # CEO-DIR-2026-047 GAP-004: Capture started_at BEFORE any execution
    execution_started_at = datetime.now(timezone.utc)

    cycle_id = f"CNRP-{execution_started_at.strftime('%Y%m%d-%H%M%S')}"

    stats = {
        'cycle_id': cycle_id,
        'started_at': execution_started_at.isoformat(),
        'phase': 'R4',
        'daemon': 'vega_epistemic_integrity_monitor',
        'evidence_staleness': {},
        'hash_integrity': {},
        'hash_verification': {},
        'cnrp_health': {},
        'lineage_continuity': {},
        'ios010_integrity': {},
        'violations': [],
        'escalations': [],
        'status': 'SUCCESS'
    }

    conn = None
    try:
        conn = get_db_connection()

        # Check evidence staleness
        logger.info("Checking evidence staleness...")
        stats['evidence_staleness'] = check_evidence_staleness(conn)
        staleness_hours = stats['evidence_staleness'].get('hours_since_update', 0)

        # CEO-DIR-2026-010: Automated DEFCON escalation when staleness > 24h
        if staleness_hours > DEFCON_ESCALATION_STALENESS_HOURS:
            defcon_escalation = auto_escalate_defcon(conn, staleness_hours)
            if defcon_escalation:
                stats['defcon_escalation'] = defcon_escalation
                conn.commit()  # Commit DEFCON change immediately

        if stats['evidence_staleness']['status'] == 'VIOLATION':
            stats['violations'].append({
                'type': 'STALENESS_VIOLATION',
                'hours': staleness_hours,
                'threshold': STALENESS_THRESHOLD_HOURS
            })
            logger.warning(f"STALENESS VIOLATION: {staleness_hours}h > {STALENESS_THRESHOLD_HOURS}h")

        # Check hash chain integrity
        logger.info("Checking hash chain integrity...")
        stats['hash_integrity'] = check_hash_chain_integrity(conn)
        if stats['hash_integrity']['status'] == 'VIOLATION':
            stats['violations'].append({
                'type': 'HASH_MISSING_VIOLATION',
                'missing': stats['hash_integrity']['missing_hash']
            })
            logger.warning(f"HASH VIOLATION: {stats['hash_integrity']['missing_hash']} missing hashes")

        # Verify hash samples
        logger.info("Verifying content hash samples...")
        stats['hash_verification'] = verify_content_hash_samples(conn)
        if stats['hash_verification']['status'] == 'HASH_MISMATCH':
            stats['violations'].append({
                'type': 'HASH_MISMATCH_VIOLATION',
                'failed': stats['hash_verification']['failed']
            })
            logger.warning(f"HASH MISMATCH: {stats['hash_verification']['failed']} mismatches detected")

        # Check CNRP cycle health
        logger.info("Checking CNRP cycle health...")
        stats['cnrp_health'] = check_cnrp_cycle_health(conn)
        if stats['cnrp_health']['status'] == 'DEGRADED':
            logger.warning("CNRP cycle health DEGRADED")

        # Check lineage continuity
        logger.info("Checking lineage continuity...")
        stats['lineage_continuity'] = check_lineage_continuity(conn)

        # Check IoS-010 integrity
        logger.info("Checking IoS-010 forecast integrity...")
        stats['ios010_integrity'] = check_ios010_forecast_integrity(conn)

        stats['total_checks'] = 6

        # Escalate violations to CEO if any
        if stats['violations']:
            stats['status'] = 'FAILED'  # Violations detected - uses FAILED per constraint
            for violation in stats['violations']:
                escalation_id = escalate_to_ceo(conn, violation['type'], violation)
                stats['escalations'].append(escalation_id)
            logger.critical(f"ESCALATED {len(stats['violations'])} violations to CEO")

        conn.commit()

        # Log execution with proper latency instrumentation (CEO-DIR-2026-047 GAP-004)
        log_cnrp_execution(conn, cycle_id, stats['status'], stats,
                          started_at=execution_started_at)
        conn.commit()

        # Summary
        if stats['violations']:
            logger.warning(f"R4 Monitor complete: {len(stats['violations'])} violations detected, {len(stats['escalations'])} escalations issued")
        else:
            logger.info("R4 Monitor complete: All integrity checks passed")

    except Exception as e:
        logger.error(f"R4 Integrity Monitor failed: {e}")
        stats['status'] = 'FAILED'
        stats['error_message'] = str(e)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

    stats['completed_at'] = datetime.now(timezone.utc).isoformat()
    return stats


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    result = run_integrity_monitor()
    print(json.dumps(result, indent=2, default=str))

    # Exit with appropriate code
    if result['status'] == 'SUCCESS':
        sys.exit(0)
    elif result['status'] == 'FAILED' and result.get('violations'):
        sys.exit(2)  # Violation but monitored
    else:
        sys.exit(1)  # Failure
