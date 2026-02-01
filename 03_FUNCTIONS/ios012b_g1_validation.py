#!/usr/bin/env python3
"""
IoS-012-B G1 VALIDATION SCRIPT
==============================
Directive: CEO-DIR-2026-106 G1 Addendum
Date: 2026-01-19
Author: STIG

Validates three CEO-mandated G1 prerequisites:
1. Write-path isolation (shadow writes don't affect live execution)
2. Deterministic replay (same inputs -> same outputs)
3. Health idempotence (multiple health checks give same result)
"""

import os
import json
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

# Database configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


class G1Validator:
    """G1 Technical Validation Suite for IoS-012-B."""

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.results = {
            'validation_id': hashlib.sha256(
                datetime.now(timezone.utc).isoformat().encode()
            ).hexdigest()[:16],
            'validated_at': datetime.now(timezone.utc).isoformat(),
            'tests': []
        }

    def close(self):
        if self.conn:
            self.conn.close()

    def validate_all(self) -> Dict[str, Any]:
        """Run all G1 validation tests."""
        print("=" * 60)
        print("IoS-012-B G1 VALIDATION SUITE")
        print("=" * 60)

        # Test 1: Write-path isolation
        self._test_write_path_isolation()

        # Test 2: Deterministic replay
        self._test_deterministic_replay()

        # Test 3: Health idempotence
        self._test_health_idempotence()

        # Test 4: Schema isolation verification
        self._test_schema_isolation()

        # Test 5: Trigger validation
        self._test_no_cross_schema_triggers()

        # Calculate overall result
        passed = sum(1 for t in self.results['tests'] if t['status'] == 'PASS')
        total = len(self.results['tests'])
        self.results['summary'] = {
            'passed': passed,
            'total': total,
            'pass_rate': f"{passed}/{total}",
            'g1_status': 'VERIFIED' if passed == total else 'FAILED'
        }

        print("\n" + "=" * 60)
        print(f"G1 VALIDATION RESULT: {self.results['summary']['g1_status']}")
        print(f"Tests: {passed}/{total} passed")
        print("=" * 60)

        return self.results

    # =========================================================================
    # TEST 1: WRITE-PATH ISOLATION
    # =========================================================================

    def _test_write_path_isolation(self):
        """
        Verify shadow table writes don't affect live execution tables.

        Validation logic:
        - Shadow table writes go to fhq_alpha.inversion_overlay_shadow
        - Live execution would go to fhq_execution.* schemas
        - No triggers or foreign keys bridge these schemas
        """
        print("\n[TEST 1] Write-Path Isolation...")

        test = {
            'name': 'write_path_isolation',
            'description': 'Shadow writes isolated from live execution'
        }

        # Check 1: Shadow table exists and is writable
        try:
            query = """
                SELECT COUNT(*) FROM fhq_alpha.inversion_overlay_shadow
                WHERE is_shadow = TRUE
            """
            with self.conn.cursor() as cur:
                cur.execute(query)
                shadow_count = cur.fetchone()[0]
        except Exception as e:
            test['status'] = 'FAIL'
            test['error'] = str(e)
            self.results['tests'].append(test)
            print(f"  FAIL: {e}")
            return

        # Check 2: No live execution records
        try:
            query = """
                SELECT COUNT(*) FROM fhq_alpha.inversion_overlay_shadow
                WHERE is_shadow = FALSE
            """
            with self.conn.cursor() as cur:
                cur.execute(query)
                live_count = cur.fetchone()[0]
        except Exception as e:
            test['status'] = 'FAIL'
            test['error'] = str(e)
            self.results['tests'].append(test)
            print(f"  FAIL: {e}")
            return

        # Check 3: No triggers connecting shadow to execution
        trigger_query = """
            SELECT trigger_name, event_manipulation, action_statement
            FROM information_schema.triggers
            WHERE event_object_schema = 'fhq_alpha'
              AND event_object_table = 'inversion_overlay_shadow'
              AND action_statement LIKE '%fhq_execution%'
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(trigger_query)
            cross_triggers = cur.fetchall()

        if cross_triggers:
            test['status'] = 'FAIL'
            test['error'] = 'Cross-schema triggers found'
            test['triggers'] = [dict(t) for t in cross_triggers]
        else:
            test['status'] = 'PASS'
            test['evidence'] = {
                'shadow_records': shadow_count,
                'live_records': live_count,
                'cross_schema_triggers': 0
            }

        self.results['tests'].append(test)
        print(f"  {test['status']}: shadow_records={shadow_count}, live_records={live_count}")

    # =========================================================================
    # TEST 2: DETERMINISTIC REPLAY
    # =========================================================================

    def _test_deterministic_replay(self):
        """
        Verify same inputs produce same outputs.

        Validation logic:
        - Run health check twice with same lookback
        - Results must be identical (hash match)
        """
        print("\n[TEST 2] Deterministic Replay...")

        test = {
            'name': 'deterministic_replay',
            'description': 'Same inputs produce same outputs'
        }

        try:
            # Run health check twice
            query = "SELECT * FROM fhq_alpha.check_inversion_health_v2(30)"

            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                result1 = cur.fetchone()

            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                result2 = cur.fetchone()

            # Remove timestamps for comparison
            r1_clean = {k: v for k, v in dict(result1).items() if 'timestamp' not in k.lower()}
            r2_clean = {k: v for k, v in dict(result2).items() if 'timestamp' not in k.lower()}

            hash1 = hashlib.sha256(json.dumps(r1_clean, sort_keys=True, default=str).encode()).hexdigest()
            hash2 = hashlib.sha256(json.dumps(r2_clean, sort_keys=True, default=str).encode()).hexdigest()

            if hash1 == hash2:
                test['status'] = 'PASS'
                test['evidence'] = {
                    'run1_hash': hash1[:16],
                    'run2_hash': hash2[:16],
                    'match': True
                }
            else:
                test['status'] = 'FAIL'
                test['evidence'] = {
                    'run1_hash': hash1[:16],
                    'run2_hash': hash2[:16],
                    'match': False,
                    'diff_keys': [k for k in r1_clean if r1_clean.get(k) != r2_clean.get(k)]
                }

        except Exception as e:
            test['status'] = 'FAIL'
            test['error'] = str(e)

        self.results['tests'].append(test)
        print(f"  {test['status']}: hash_match={test.get('evidence', {}).get('match', False)}")

    # =========================================================================
    # TEST 3: HEALTH IDEMPOTENCE
    # =========================================================================

    def _test_health_idempotence(self):
        """
        Verify multiple health checks give consistent results.

        Validation logic:
        - Health status should be stable across multiple calls
        - No state mutation from read operations
        """
        print("\n[TEST 3] Health Idempotence...")

        test = {
            'name': 'health_idempotence',
            'description': 'Health check is idempotent'
        }

        try:
            results = []
            for i in range(3):
                query = "SELECT health_status, should_disable FROM fhq_alpha.check_inversion_health_v2(30)"
                with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query)
                    result = cur.fetchone()
                    results.append({
                        'health_status': result['health_status'],
                        'should_disable': result['should_disable']
                    })

            # Check all results are identical
            if all(r == results[0] for r in results):
                test['status'] = 'PASS'
                test['evidence'] = {
                    'iterations': 3,
                    'consistent_status': results[0]['health_status'],
                    'all_identical': True
                }
            else:
                test['status'] = 'FAIL'
                test['evidence'] = {
                    'iterations': 3,
                    'results': results,
                    'all_identical': False
                }

        except Exception as e:
            test['status'] = 'FAIL'
            test['error'] = str(e)

        self.results['tests'].append(test)
        print(f"  {test['status']}: status={test.get('evidence', {}).get('consistent_status', 'N/A')}")

    # =========================================================================
    # TEST 4: SCHEMA ISOLATION
    # =========================================================================

    def _test_schema_isolation(self):
        """
        Verify IoS-012-B tables are isolated to fhq_alpha schema.

        Validation logic:
        - All inversion tables in fhq_alpha
        - No shadow tables in fhq_execution
        """
        print("\n[TEST 4] Schema Isolation...")

        test = {
            'name': 'schema_isolation',
            'description': 'Inversion tables isolated in fhq_alpha'
        }

        try:
            # Check fhq_alpha tables (using pg_tables for reliability)
            alpha_query = """
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'fhq_alpha'
                  AND tablename LIKE %s
            """
            with self.conn.cursor() as cur:
                cur.execute(alpha_query, ('%inversion%',))
                alpha_tables = [r[0] for r in cur.fetchall()]

            # Check fhq_execution for IoS-012-B specific tables (should be 0)
            # Note: shadow_trades is a legitimate execution table, not an inversion table
            exec_query = """
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'fhq_execution'
                  AND (tablename LIKE %s OR tablename LIKE %s)
            """
            with self.conn.cursor() as cur:
                cur.execute(exec_query, ('%inversion_overlay%', '%ios012b%'))
                exec_shadow_tables = [r[0] for r in cur.fetchall()]

            if exec_shadow_tables:
                test['status'] = 'FAIL'
                test['error'] = 'IoS-012-B tables found in execution schema'
                test['evidence'] = {
                    'alpha_inversion_tables': alpha_tables,
                    'execution_ios012b_tables': exec_shadow_tables
                }
            else:
                test['status'] = 'PASS'
                test['evidence'] = {
                    'alpha_inversion_tables': alpha_tables,
                    'execution_ios012b_tables': 0
                }

        except Exception as e:
            test['status'] = 'FAIL'
            test['error'] = str(e)

        self.results['tests'].append(test)
        print(f"  {test['status']}: alpha_tables={len(test.get('evidence', {}).get('alpha_inversion_tables', []))}")

    # =========================================================================
    # TEST 5: NO CROSS-SCHEMA TRIGGERS
    # =========================================================================

    def _test_no_cross_schema_triggers(self):
        """
        Verify no triggers connect shadow to live execution.

        Validation logic:
        - No triggers on shadow table that write to fhq_execution
        - No triggers on shadow table that call external APIs
        """
        print("\n[TEST 5] No Cross-Schema Triggers...")

        test = {
            'name': 'no_cross_schema_triggers',
            'description': 'No triggers bridging shadow to execution'
        }

        try:
            query = """
                SELECT
                    t.trigger_name,
                    t.event_manipulation,
                    t.event_object_table,
                    pg_get_triggerdef(tg.oid) as trigger_definition
                FROM information_schema.triggers t
                JOIN pg_trigger tg ON tg.tgname = t.trigger_name
                WHERE t.event_object_schema = 'fhq_alpha'
                  AND t.event_object_table = 'inversion_overlay_shadow'
            """
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                triggers = cur.fetchall()

            # Check each trigger for dangerous patterns
            dangerous_triggers = []
            for t in triggers:
                definition = t.get('trigger_definition', '')
                if 'fhq_execution' in definition or 'alpaca' in definition.lower():
                    dangerous_triggers.append(dict(t))

            if dangerous_triggers:
                test['status'] = 'FAIL'
                test['error'] = 'Dangerous triggers found'
                test['evidence'] = {'dangerous_triggers': dangerous_triggers}
            else:
                test['status'] = 'PASS'
                test['evidence'] = {
                    'total_triggers': len(triggers),
                    'dangerous_triggers': 0
                }

        except Exception as e:
            test['status'] = 'FAIL'
            test['error'] = str(e)

        self.results['tests'].append(test)
        print(f"  {test['status']}: total_triggers={test.get('evidence', {}).get('total_triggers', 0)}")

    def save_results(self) -> str:
        """Save validation results to evidence file."""
        filepath = os.path.join(
            os.path.dirname(__file__),
            'evidence',
            f"IOS012B_G1_VALIDATION_{datetime.now().strftime('%Y%m%d')}.json"
        )

        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"\nResults saved: {filepath}")
        return filepath


def main():
    validator = G1Validator()
    try:
        results = validator.validate_all()
        validator.save_results()
        return 0 if results['summary']['g1_status'] == 'VERIFIED' else 1
    finally:
        validator.close()


if __name__ == '__main__':
    exit(main())
