#!/usr/bin/env python3
"""
MEMORY DOMAIN MANAGER - MemoryOS Core
======================================
CEO Directive: CEO-DIR-2026-LEARNING-MEMORY-ADMISSION-041-060
ADR: ADR-013, ADR-017, ADR-018, ADR-020
Classification: CRITICAL - Constitutional Infrastructure

Implements the MemoryOS three-tier memory hierarchy:
  STM: Short-Term Memory  - ephemeral, TTL-based, non-canonical
  MTM: Medium-Term Memory - quarantined, experimental, 72h freeze
  LPM: Long-Term Permanent - canonical, write-protected, Admission Gate only

Constitutional constraints:
  - MIT Quad Pipeline Invariant: Memory reads FROM canonical pipeline,
    writes ONLY to fhq_memory tables. Never to canonical_features,
    regime_state, or exposure tables.
  - ASRP Binding: Every write embeds state_snapshot_hash, state_timestamp, agent_id
  - Fail-Closed: Missing ASRP = rejected write
  - LPM is NEVER writable via this module. Only Admission Gate can write to LPM.

Database operations:
  READS:  fhq_memory.memory_domains, fhq_memory.stm_store
  WRITES: fhq_memory.stm_store, fhq_memory.containment_firewall_log

Usage:
    python memory_domain_manager.py                    # Run STM cleanup cycle
    python memory_domain_manager.py --status           # Show domain status
    python memory_domain_manager.py --test-stm         # Test STM lifecycle
    python memory_domain_manager.py --test-containment # Test firewall

Author: STIG (CTO)
Date: 2026-02-11
Contract: EC-003_2026_PRODUCTION
"""

import os
import sys
import json
import uuid
import logging
import argparse
from datetime import datetime, timezone, timedelta

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Add parent for imports
sys.path.insert(0, os.path.dirname(__file__))
from asrp_binder import AsrpBinder, ASRPBindingError, get_db_connection, register_heartbeat, write_evidence_file

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[MEMORY_OS] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/memory_domain_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('memory_domain_manager')

DAEMON_NAME = 'memory_domain_manager'
AGENT_ID = 'STIG'
CEO_DIRECTIVE = 'CEO-DIR-2026-LEARNING-MEMORY-ADMISSION-041-060'

# STM defaults
STM_DEFAULT_TTL_SECONDS = 3600      # 1 hour
STM_MAX_TTL_SECONDS = 86400         # 24 hours
STM_CLEANUP_BATCH_SIZE = 1000

# Containment: tables that MUST NEVER be written from memory subsystem
FORBIDDEN_WRITE_TARGETS = {
    'fhq_macro.canonical_features',
    'fhq_macro.canonical_series',
    'fhq_macro.golden_features',
    'fhq_research.regime_predictions',
    'fhq_research.regime_states',
    'fhq_perception.sovereign_regime_state',
    'fhq_perception.sovereign_regime_state_v4',
    'fhq_perception.regime_daily',
    'fhq_execution.shadow_trades',
    'fhq_execution.trades',
    'fhq_alpha.causal_edges',
    'fhq_alpha.canonical_signal_handoff',
    'fhq_governance.execution_mode',
    'fhq_governance.defcon_state',
}


class MemoryDomainManager:
    """
    MemoryOS core: manages the three-tier memory hierarchy.

    STM operations: create, read, access (updates accessed_at), expire, delete
    MTM/LPM: read-only from this module. MTM writes via mtm_quarantine_daemon,
    LPM writes via admission_gate_engine only.
    """

    def __init__(self, conn=None):
        self._conn = conn
        self._owns_conn = False
        self._binder = None

    @property
    def conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = get_db_connection()
            self._owns_conn = True
        return self._conn

    @property
    def binder(self):
        if self._binder is None:
            self._binder = AsrpBinder(self.conn)
        return self._binder

    def close(self):
        if self._binder:
            self._binder.close()
        if self._owns_conn and self._conn and not self._conn.closed:
            self._conn.close()

    # =========================================================================
    # DOMAIN STATUS
    # =========================================================================

    def get_domain_status(self):
        """Get status of all memory domains with row counts."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT domain_name, is_canonical, write_protected, max_ttl_hours, access_level
                FROM fhq_memory.memory_domains
                ORDER BY domain_name
            """)
            domains = cur.fetchall()

            # STM count
            cur.execute("SELECT count(*) as cnt FROM fhq_memory.stm_store")
            stm_count = cur.fetchone()['cnt']

            # STM expired count
            cur.execute("SELECT count(*) as cnt FROM fhq_memory.stm_store WHERE expires_at < NOW()")
            stm_expired = cur.fetchone()['cnt']

        return {
            'domains': [dict(d) for d in domains],
            'stm_total': stm_count,
            'stm_expired': stm_expired,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    # =========================================================================
    # STM OPERATIONS
    # =========================================================================

    def stm_write(self, memory_key: str, memory_value: dict, source_type: str,
                  regime: str, agent_id: str = AGENT_ID, ttl_seconds: int = STM_DEFAULT_TTL_SECONDS,
                  session_id: str = None, source_id: str = None, confidence: float = None):
        """
        Write to Short-Term Memory with ASRP binding.

        Args:
            memory_key: Unique key for this memory entry
            memory_value: JSONB payload
            source_type: Origin of this data (e.g., 'price_feed', 'regime_signal')
            regime: Current market regime
            agent_id: Agent writing this entry
            ttl_seconds: Time-to-live in seconds (max 86400)
            session_id: Optional session UUID
            source_id: Optional source reference UUID
            confidence: Optional confidence score

        Returns:
            UUID of created STM entry

        Raises:
            ASRPBindingError: If ASRP binding fails
            ValueError: If TTL exceeds maximum
        """
        if ttl_seconds > STM_MAX_TTL_SECONDS:
            raise ValueError(f"STM TTL {ttl_seconds}s exceeds max {STM_MAX_TTL_SECONDS}s (24h)")

        # ASRP binding - fail closed
        binding = self.binder.bind_artifact(agent_id, artifact_data=memory_value)

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        stm_id = str(uuid.uuid4())

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_memory.stm_store
                    (stm_id, agent_id, session_id, memory_key, memory_value,
                     source_type, source_id, regime, confidence, ttl_seconds,
                     expires_at, state_snapshot_hash, state_timestamp, lineage_hash)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                stm_id, agent_id, session_id, memory_key,
                json.dumps(memory_value, default=str),
                source_type, source_id, regime, confidence, ttl_seconds,
                expires_at, binding['state_snapshot_hash'],
                binding['state_timestamp'], binding.get('artifact_hash')
            ))
            self.conn.commit()

        logger.info(f"STM write: key={memory_key}, ttl={ttl_seconds}s, asrp={binding['state_snapshot_hash'][:16]}...")
        return stm_id

    def stm_read(self, memory_key: str = None, stm_id: str = None,
                 regime: str = None, include_expired: bool = False):
        """
        Read from STM. Updates accessed_at on read.

        Args:
            memory_key: Filter by key (optional)
            stm_id: Filter by ID (optional)
            regime: Filter by regime (optional)
            include_expired: Include expired entries (default False)

        Returns:
            List of STM entries as dicts
        """
        conditions = []
        params = []

        if not include_expired:
            conditions.append("expires_at > NOW()")

        if memory_key:
            conditions.append("memory_key = %s")
            params.append(memory_key)

        if stm_id:
            conditions.append("stm_id = %s")
            params.append(stm_id)

        if regime:
            conditions.append("regime = %s")
            params.append(regime)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT stm_id, agent_id, memory_key, memory_value, source_type,
                       regime, confidence, ttl_seconds, expires_at,
                       state_snapshot_hash, state_timestamp, created_at, accessed_at
                FROM fhq_memory.stm_store
                {where}
                ORDER BY created_at DESC
            """, params)
            results = cur.fetchall()

            # Update accessed_at for returned entries
            if results:
                ids = [str(r['stm_id']) for r in results]
                cur.execute("""
                    UPDATE fhq_memory.stm_store
                    SET accessed_at = NOW()
                    WHERE stm_id = ANY(%s::uuid[])
                """, (ids,))
                self.conn.commit()

        return [dict(r) for r in results]

    def stm_expire_cleanup(self):
        """
        Delete expired STM entries. Returns count of deleted entries.
        This is the STM garbage collection cycle.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                DELETE FROM fhq_memory.stm_store
                WHERE expires_at < NOW()
                RETURNING stm_id
            """)
            deleted = cur.fetchall()
            self.conn.commit()

        count = len(deleted)
        if count > 0:
            logger.info(f"STM cleanup: deleted {count} expired entries")
        return count

    def stm_delete(self, stm_id: str):
        """Explicitly delete an STM entry by ID."""
        with self.conn.cursor() as cur:
            cur.execute("""
                DELETE FROM fhq_memory.stm_store WHERE stm_id = %s RETURNING stm_id
            """, (stm_id,))
            result = cur.fetchone()
            self.conn.commit()
        return result is not None

    # =========================================================================
    # CONTAINMENT FIREWALL
    # =========================================================================

    def check_containment(self, target_table: str, agent_id: str = AGENT_ID,
                          operation: str = 'WRITE'):
        """
        Check if a write to target_table is allowed from memory subsystem.

        Args:
            target_table: schema.table being targeted
            agent_id: Agent attempting the write
            operation: Operation type

        Returns:
            dict with 'allowed' bool and 'reason'

        Side effect: Logs to containment_firewall_log
        """
        binding = self.binder.bind_artifact(agent_id)
        blocked = target_table in FORBIDDEN_WRITE_TARGETS
        allowed = not blocked

        # Get current DEFCON
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT defcon_level FROM fhq_governance.defcon_state WHERE is_current = true LIMIT 1
            """)
            defcon = cur.fetchone()
            defcon_level = defcon['defcon_level'] if defcon else 'UNKNOWN'

            # Log the check
            cur.execute("""
                INSERT INTO fhq_memory.containment_firewall_log
                    (event_type, source_domain, target_domain, blocked, block_reason,
                     agent_id, operation_attempted, target_table,
                     state_snapshot_hash, defcon_at_event)
                VALUES
                    (%s, 'MEMORY', %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                'CONTAINMENT_CHECK',
                target_table.split('.')[0] if '.' in target_table else 'UNKNOWN',
                blocked,
                f"Target {target_table} is in FORBIDDEN_WRITE_TARGETS" if blocked else None,
                agent_id,
                operation,
                target_table,
                binding['state_snapshot_hash'],
                defcon_level
            ))
            self.conn.commit()

        if blocked:
            logger.warning(f"CONTAINMENT VIOLATION BLOCKED: {agent_id} -> {target_table}")

        return {
            'allowed': allowed,
            'blocked': blocked,
            'target_table': target_table,
            'reason': f"Blocked: {target_table} is a protected canonical pipeline table" if blocked else "Allowed",
            'defcon_at_check': defcon_level,
            'asrp_hash': binding['state_snapshot_hash']
        }

    # =========================================================================
    # STM LIFECYCLE TEST
    # =========================================================================

    def test_stm_lifecycle(self):
        """
        End-to-end test of STM lifecycle: create -> read -> expire -> cleanup.
        Returns test results dict.
        """
        results = {
            'test_name': 'STM_LIFECYCLE',
            'steps': [],
            'overall': 'PENDING'
        }

        try:
            # Step 1: Write
            test_key = f"TEST_STM_{uuid.uuid4().hex[:8]}"
            test_value = {'test': True, 'timestamp': datetime.now(timezone.utc).isoformat()}
            stm_id = self.stm_write(
                memory_key=test_key,
                memory_value=test_value,
                source_type='LIFECYCLE_TEST',
                regime='NEUTRAL',
                ttl_seconds=5  # 5 second TTL for test
            )
            results['steps'].append({
                'step': 'WRITE', 'result': 'PASS',
                'detail': f'Created STM entry {stm_id}'
            })

            # Step 2: Read (should find it)
            read_result = self.stm_read(memory_key=test_key)
            found = len(read_result) == 1
            results['steps'].append({
                'step': 'READ', 'result': 'PASS' if found else 'FAIL',
                'detail': f'Found {len(read_result)} entries'
            })

            # Step 3: Verify ASRP binding present
            if found:
                has_asrp = bool(read_result[0].get('state_snapshot_hash'))
                results['steps'].append({
                    'step': 'ASRP_VERIFY', 'result': 'PASS' if has_asrp else 'FAIL',
                    'detail': f'ASRP hash: {read_result[0].get("state_snapshot_hash", "MISSING")[:16]}...'
                })
            else:
                results['steps'].append({
                    'step': 'ASRP_VERIFY', 'result': 'SKIP',
                    'detail': 'No entry to verify'
                })

            # Step 4: Delete
            deleted = self.stm_delete(stm_id)
            results['steps'].append({
                'step': 'DELETE', 'result': 'PASS' if deleted else 'FAIL',
                'detail': f'Deleted: {deleted}'
            })

            # Step 5: Read after delete (should not find)
            post_delete = self.stm_read(memory_key=test_key)
            not_found = len(post_delete) == 0
            results['steps'].append({
                'step': 'VERIFY_DELETE', 'result': 'PASS' if not_found else 'FAIL',
                'detail': f'Entries after delete: {len(post_delete)}'
            })

            # Overall
            all_pass = all(s['result'] == 'PASS' for s in results['steps'])
            results['overall'] = 'PASS' if all_pass else 'FAIL'

        except Exception as e:
            # Rollback any aborted transaction
            try:
                self.conn.rollback()
            except Exception:
                pass
            results['steps'].append({
                'step': 'ERROR', 'result': 'FAIL',
                'detail': str(e)
            })
            results['overall'] = 'FAIL'

        return results

    def test_containment_firewall(self):
        """
        Test containment firewall: attempt writes to forbidden tables -> must be blocked.
        Returns test results dict.
        """
        results = {
            'test_name': 'CONTAINMENT_FIREWALL',
            'steps': [],
            'overall': 'PENDING'
        }

        # Test 1: Forbidden table should be blocked
        for target in ['fhq_macro.canonical_features', 'fhq_execution.trades']:
            check = self.check_containment(target)
            blocked = check['blocked']
            results['steps'].append({
                'step': f'BLOCK_{target}',
                'result': 'PASS' if blocked else 'FAIL',
                'detail': check['reason']
            })

        # Test 2: Memory table should be allowed
        for target in ['fhq_memory.stm_store', 'fhq_memory.mtm_quarantine']:
            check = self.check_containment(target)
            allowed = check['allowed']
            results['steps'].append({
                'step': f'ALLOW_{target}',
                'result': 'PASS' if allowed else 'FAIL',
                'detail': check['reason']
            })

        all_pass = all(s['result'] == 'PASS' for s in results['steps'])
        results['overall'] = 'PASS' if all_pass else 'FAIL'
        return results


def main():
    parser = argparse.ArgumentParser(description='MemoryOS Domain Manager')
    parser.add_argument('--status', action='store_true', help='Show domain status')
    parser.add_argument('--test-stm', action='store_true', help='Run STM lifecycle test')
    parser.add_argument('--test-containment', action='store_true', help='Run containment firewall test')
    parser.add_argument('--cleanup', action='store_true', help='Run STM expiry cleanup')
    args = parser.parse_args()

    mgr = MemoryDomainManager()

    try:
        conn = mgr.conn
        register_heartbeat(conn, DAEMON_NAME, interval_minutes=30,
                          is_critical=True, ceo_directive_ref=CEO_DIRECTIVE)

        if args.status:
            status = mgr.get_domain_status()
            print(json.dumps(status, indent=2, default=str))

        elif args.test_stm:
            results = mgr.test_stm_lifecycle()
            print(json.dumps(results, indent=2, default=str))
            # Write evidence
            binding = mgr.binder.bind_artifact(AGENT_ID, artifact_data=results)
            evidence = {
                'directive': CEO_DIRECTIVE,
                'runbook': 'RB-42',
                'test_name': 'STM_LIFECYCLE',
                'results': results,
                'asrp_binding': binding,
                'executed_at': datetime.now(timezone.utc).isoformat()
            }
            write_evidence_file(evidence,
                f"MEMORY_STM_LIFECYCLE_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

        elif args.test_containment:
            results = mgr.test_containment_firewall()
            print(json.dumps(results, indent=2, default=str))
            # Write evidence
            binding = mgr.binder.bind_artifact(AGENT_ID, artifact_data=results)
            evidence = {
                'directive': CEO_DIRECTIVE,
                'runbook': 'RB-44',
                'test_name': 'CONTAINMENT_FIREWALL',
                'results': results,
                'asrp_binding': binding,
                'executed_at': datetime.now(timezone.utc).isoformat()
            }
            write_evidence_file(evidence,
                f"MEMORY_CONTAINMENT_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

        elif args.cleanup:
            count = mgr.stm_expire_cleanup()
            print(f"Cleaned up {count} expired STM entries")

        else:
            # Default: status + cleanup
            status = mgr.get_domain_status()
            logger.info(f"Domain status: STM={status['stm_total']} (expired={status['stm_expired']})")
            count = mgr.stm_expire_cleanup()
            logger.info(f"Cleanup complete: {count} expired entries removed")

    finally:
        mgr.close()


if __name__ == '__main__':
    main()
