#!/usr/bin/env python3
"""
SENTINEL_DB_INTEGRITY v1.0
===========================
Authority: CEO Directive - Sentinel_DB_Integrity v1.0
Classification: OODA-loop Critical Infrastructure
Reference: ADR-001 → ADR-002 → ADR-003 → ADR-010 → ADR-011 → ADR-013 → ADR-015

PURPOSE:
    Protect data integrity and perception quality FIRST,
    performance (latency) as SECONDARY goal.

    Principle: A slow but correct query is acceptable.
               A fast but incorrect/inconsistent query is NOT acceptable.

MODULES (Priority Order):
    1. Lock Monitor (Critical - Correctness/Availability)
    2. Vacuum & Bloat Watchdog (Stability/Planner Integrity)
    3. High-Impact Slow Query Monitor (Performance, not cosmetic)

OPERATIONAL RHYTHM:
    - Frequency: Every 5 minutes (configurable)
    - Mode: Read-only monitoring
    - Logging: To canonical discrepancy/governance tables (ADR-010/011/015)

BINDING:
    ADR-013: Protects One-Source-of-Truth by monitoring canonical tables
    ADR-015: Output feeds VEGA's meta-governance loop
    ADR-011: All logging hashable into Fortress evidence chain
    EC-003: STIG as sole schema custodian

Generated: 2025-12-08
"""

from __future__ import annotations

import os
import sys
import json
import hashlib
import uuid
import traceback
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Try to import yaml (optional, fallback to defaults if not available)
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

load_dotenv()

# =============================================================================
# CONFIGURATION LOADER (G1 Externalized - Per CEO Directive)
# =============================================================================
# All thresholds externalized to YAML per G1 mandate.
# Sentinel loads config from:
#   1. YAML file (05_ORCHESTRATOR/sentinel_db_integrity_config.yaml)
#   2. Environment variables (overrides)
#   3. Fallback defaults (if YAML not found)
# =============================================================================

DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', 54322)),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}

# Default config (fallback if YAML not available)
DEFAULT_SENTINEL_CONFIG = {
    'interval_seconds': 300,
    'lock_monitor': {
        'warn_wait_seconds': 10,
        'critical_consecutive': 2,
        'critical_schemas': ['fhq_market', 'fhq_perception', 'fhq_research', 'fhq_positions'],
    },
    'bloat_watchdog': {
        'warn_bloat_ratio': 0.10,
        'critical_bloat_ratio': 0.25,
        'critical_vacuum_days': 7,
        'critical_tables': [
            'fhq_market.prices',
            'fhq_market.staging_prices',
            'fhq_perception.regime_daily',
            'fhq_research.regime_predictions_v2',
            'fhq_research.nightly_insights',
        ],
    },
    'slow_query': {
        'mean_time_warn_ms': 500,
        'min_calls': 10,
        'top_n_queries': 10,
        'focus_schemas': ['fhq_market', 'fhq_perception', 'fhq_research', 'fhq_positions'],
    },
    'fault_tolerance': {
        'max_retries': 3,
        'retry_delay_seconds': 5,
        'module_timeout_seconds': 30,
        'continue_on_module_failure': True,
        'error_event_type': 'SYSTEM_ERROR',
    },
}

# ADR-010 Severity Mapping
# Note: DB enum values are INFO, WARN, CRITICAL (not WARNING)
ADR010_SEVERITY = {
    'NORMAL': {'score': 0.0, 'log': False, 'db_severity': 'INFO'},
    'WARNING': {'score': 0.05, 'log': True, 'db_severity': 'WARN'},
    'CRITICAL': {'score': 0.15, 'log': True, 'db_severity': 'CRITICAL'},
}


def load_config_from_yaml(config_path: str = None) -> Dict:
    """
    Load sentinel configuration from YAML file.

    Priority:
    1. Explicit config_path parameter
    2. SENTINEL_CONFIG_PATH environment variable
    3. Default path: 05_ORCHESTRATOR/sentinel_db_integrity_config.yaml
    4. Fallback to DEFAULT_SENTINEL_CONFIG if file not found
    """
    if not YAML_AVAILABLE:
        print("[WARN] PyYAML not installed - using default config")
        return DEFAULT_SENTINEL_CONFIG.copy()

    # Determine config path
    if config_path is None:
        config_path = os.environ.get('SENTINEL_CONFIG_PATH')

    if config_path is None:
        # Try default paths
        script_dir = Path(__file__).parent
        possible_paths = [
            script_dir.parent / '05_ORCHESTRATOR' / 'sentinel_db_integrity_config.yaml',
            script_dir / 'sentinel_db_integrity_config.yaml',
            Path.cwd() / '05_ORCHESTRATOR' / 'sentinel_db_integrity_config.yaml',
        ]

        for path in possible_paths:
            if path.exists():
                config_path = str(path)
                break

    if config_path is None or not Path(config_path).exists():
        print("[WARN] Config YAML not found - using default config")
        return DEFAULT_SENTINEL_CONFIG.copy()

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f)

        # Extract relevant sections and merge with defaults
        config = DEFAULT_SENTINEL_CONFIG.copy()

        if yaml_config.get('sentinel'):
            config['interval_seconds'] = yaml_config['sentinel'].get(
                'interval_seconds', config['interval_seconds']
            )

        if yaml_config.get('lock_monitor'):
            lm = yaml_config['lock_monitor']
            config['lock_monitor'] = {
                'warn_wait_seconds': lm.get('thresholds', {}).get(
                    'warn_wait_seconds', config['lock_monitor']['warn_wait_seconds']
                ),
                'critical_consecutive': lm.get('thresholds', {}).get(
                    'critical_consecutive', config['lock_monitor']['critical_consecutive']
                ),
                'critical_schemas': lm.get(
                    'critical_schemas', config['lock_monitor']['critical_schemas']
                ),
            }

        if yaml_config.get('bloat_watchdog'):
            bw = yaml_config['bloat_watchdog']
            config['bloat_watchdog'] = {
                'warn_bloat_ratio': bw.get('thresholds', {}).get(
                    'warn_bloat_ratio', config['bloat_watchdog']['warn_bloat_ratio']
                ),
                'critical_bloat_ratio': bw.get('thresholds', {}).get(
                    'critical_bloat_ratio', config['bloat_watchdog']['critical_bloat_ratio']
                ),
                'critical_vacuum_days': bw.get('thresholds', {}).get(
                    'critical_vacuum_days', config['bloat_watchdog']['critical_vacuum_days']
                ),
                'critical_tables': bw.get(
                    'critical_tables', config['bloat_watchdog']['critical_tables']
                ),
            }

        if yaml_config.get('slow_query'):
            sq = yaml_config['slow_query']
            config['slow_query'] = {
                'mean_time_warn_ms': sq.get('thresholds', {}).get(
                    'mean_time_warn_ms', config['slow_query']['mean_time_warn_ms']
                ),
                'min_calls': sq.get('thresholds', {}).get(
                    'min_calls', config['slow_query']['min_calls']
                ),
                'top_n_queries': sq.get('thresholds', {}).get(
                    'top_n_queries', config['slow_query']['top_n_queries']
                ),
                'focus_schemas': sq.get(
                    'focus_schemas', config['slow_query']['focus_schemas']
                ),
            }

        if yaml_config.get('fault_tolerance'):
            ft = yaml_config['fault_tolerance']
            config['fault_tolerance'] = {
                'max_retries': ft.get('max_retries', 3),
                'retry_delay_seconds': ft.get('retry_delay_seconds', 5),
                'module_timeout_seconds': ft.get('module_timeout_seconds', 30),
                'continue_on_module_failure': ft.get('continue_on_module_failure', True),
                'error_event_type': ft.get('error_event_type', 'SYSTEM_ERROR'),
            }

        print(f"[INFO] Config loaded from: {config_path}")
        return config

    except Exception as e:
        print(f"[WARN] Error loading YAML config: {e} - using defaults")
        return DEFAULT_SENTINEL_CONFIG.copy()


# Load config at module level (can be overridden by passing config to sentinel)
SENTINEL_CONFIG = load_config_from_yaml()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def compute_hash(data: str) -> str:
    """Compute SHA-256 hash for Fortress evidence chain."""
    return hashlib.sha256(data.encode()).hexdigest()


def safe_float(value) -> Optional[float]:
    """Safely convert to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# =============================================================================
# MODULE 1: LOCK MONITOR (Priority 1 - Correctness)
# =============================================================================

class LockMonitor:
    """
    Detects and logs concurrency problems that could cause:
    - Write processes blocking reads (stale data for IoS-003/004)
    - Deadlocks/timeouts causing incomplete data (ADR-013 violation)

    Uses: pg_stat_activity, pg_locks
    """

    def __init__(self, conn, config: Dict):
        self.conn = conn
        self.config = config
        self.consecutive_alerts = {}  # Track consecutive alerts per blocker

    def check_lock_contention(self) -> Dict[str, Any]:
        """
        Check for lock contention issues.

        Returns dict with:
        - status: NORMAL/WARNING/CRITICAL
        - lock_waits: list of waiting processes
        - blockers: list of blocking processes
        - affected_schemas: list of affected schemas
        """
        cur = self.conn.cursor(cursor_factory=RealDictCursor)

        # Query 1: Find processes waiting on locks
        cur.execute("""
            SELECT
                blocked.pid AS blocked_pid,
                blocked.usename AS blocked_user,
                blocked.query AS blocked_query,
                blocked.state AS blocked_state,
                blocked.wait_event_type,
                blocked.wait_event,
                EXTRACT(EPOCH FROM (NOW() - blocked.query_start)) AS wait_seconds,
                blocking.pid AS blocking_pid,
                blocking.usename AS blocking_user,
                blocking.query AS blocking_query,
                blocking.state AS blocking_state
            FROM pg_stat_activity blocked
            LEFT JOIN pg_locks blocked_locks ON blocked.pid = blocked_locks.pid
            LEFT JOIN pg_locks blocking_locks ON blocked_locks.locktype = blocking_locks.locktype
                AND blocked_locks.relation = blocking_locks.relation
                AND blocked_locks.pid != blocking_locks.pid
                AND blocking_locks.granted = true
                AND blocked_locks.granted = false
            LEFT JOIN pg_stat_activity blocking ON blocking_locks.pid = blocking.pid
            WHERE blocked.wait_event_type = 'Lock'
                AND blocked.state != 'idle'
            ORDER BY wait_seconds DESC
        """)

        lock_waits = cur.fetchall()

        # Query 2: Get lock statistics by schema
        cur.execute("""
            SELECT
                n.nspname AS schema_name,
                c.relname AS table_name,
                l.mode AS lock_mode,
                l.granted,
                COUNT(*) AS lock_count
            FROM pg_locks l
            JOIN pg_class c ON l.relation = c.oid
            JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
                AND l.locktype = 'relation'
            GROUP BY n.nspname, c.relname, l.mode, l.granted
            HAVING COUNT(*) > 1
            ORDER BY lock_count DESC
        """)

        lock_stats = cur.fetchall()
        cur.close()

        # Analyze results
        result = {
            'status': 'NORMAL',
            'severity_score': 0.0,
            'lock_waits': [],
            'blockers': [],
            'affected_schemas': set(),
            'affected_tables': [],
            'total_waiting': 0,
            'max_wait_seconds': 0.0,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        warn_threshold = self.config['warn_wait_seconds']
        critical_schemas = self.config['critical_schemas']

        for wait in lock_waits:
            wait_seconds = safe_float(wait['wait_seconds']) or 0
            result['total_waiting'] += 1
            result['max_wait_seconds'] = max(result['max_wait_seconds'], wait_seconds)

            wait_info = {
                'blocked_pid': wait['blocked_pid'],
                'blocked_query': (wait['blocked_query'] or '')[:200],
                'wait_seconds': round(wait_seconds, 2),
                'blocking_pid': wait['blocking_pid'],
                'blocking_query': (wait['blocking_query'] or '')[:200],
            }
            result['lock_waits'].append(wait_info)

            if wait['blocking_pid']:
                result['blockers'].append({
                    'pid': wait['blocking_pid'],
                    'query': (wait['blocking_query'] or '')[:200],
                    'state': wait['blocking_state']
                })

        # Check affected schemas from lock stats
        for stat in lock_stats:
            schema = stat['schema_name']
            table = f"{schema}.{stat['table_name']}"
            result['affected_schemas'].add(schema)
            if not stat['granted']:  # Pending locks
                result['affected_tables'].append({
                    'table': table,
                    'mode': stat['lock_mode'],
                    'count': stat['lock_count']
                })

        result['affected_schemas'] = list(result['affected_schemas'])

        # Determine severity
        if result['total_waiting'] > 0:
            # Check if critical schemas affected
            critical_affected = any(s in critical_schemas for s in result['affected_schemas'])

            if result['max_wait_seconds'] >= warn_threshold:
                if critical_affected:
                    result['status'] = 'CRITICAL'
                    result['severity_score'] = ADR010_SEVERITY['CRITICAL']['score']
                else:
                    result['status'] = 'WARNING'
                    result['severity_score'] = ADR010_SEVERITY['WARNING']['score']
            else:
                result['status'] = 'WARNING'
                result['severity_score'] = ADR010_SEVERITY['WARNING']['score']

        return result


# =============================================================================
# MODULE 2: VACUUM & BLOAT WATCHDOG (Priority 2 - Planner Integrity)
# =============================================================================

class BloatWatchdog:
    """
    Prevents table bloat and stale statistics from causing bad plans.
    Supports ADR-011 Fortress requirement for deterministic replay.

    Uses: pg_stat_user_tables
    """

    def __init__(self, conn, config: Dict):
        self.conn = conn
        self.config = config

    def check_table_bloat(self) -> Dict[str, Any]:
        """
        Check for table bloat and vacuum health.

        Returns dict with:
        - status: NORMAL/WARNING/CRITICAL
        - tables: list of table health stats
        - critical_tables_at_risk: list of critical tables with issues
        """
        cur = self.conn.cursor(cursor_factory=RealDictCursor)

        # Query table statistics
        cur.execute("""
            SELECT
                schemaname || '.' || relname AS table_name,
                n_live_tup,
                n_dead_tup,
                CASE
                    WHEN (n_live_tup + n_dead_tup) > 0
                    THEN n_dead_tup::float / (n_live_tup + n_dead_tup)
                    ELSE 0
                END AS bloat_ratio,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze,
                GREATEST(last_vacuum, last_autovacuum) AS last_any_vacuum,
                EXTRACT(EPOCH FROM (NOW() - GREATEST(last_vacuum, last_autovacuum))) / 86400 AS days_since_vacuum
            FROM pg_stat_user_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY n_dead_tup DESC
        """)

        tables = cur.fetchall()
        cur.close()

        result = {
            'status': 'NORMAL',
            'severity_score': 0.0,
            'tables': [],
            'critical_tables_at_risk': [],
            'warn_tables': [],
            'total_dead_tuples': 0,
            'total_live_tuples': 0,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        warn_ratio = self.config['warn_bloat_ratio']
        critical_ratio = self.config['critical_bloat_ratio']
        critical_vacuum_days = self.config['critical_vacuum_days']
        critical_tables = self.config['critical_tables']

        for table in tables:
            table_name = table['table_name']
            bloat_ratio = safe_float(table['bloat_ratio']) or 0
            days_since = safe_float(table['days_since_vacuum'])
            n_live = table['n_live_tup'] or 0
            n_dead = table['n_dead_tup'] or 0

            result['total_live_tuples'] += n_live
            result['total_dead_tuples'] += n_dead

            table_status = 'NORMAL'
            is_critical_table = table_name in critical_tables

            # Minimum dead tuples to trigger CRITICAL (avoid false positives on tiny tables)
            MIN_DEAD_FOR_CRITICAL = 100

            # Check bloat ratio (require minimum dead tuples for CRITICAL)
            if bloat_ratio >= critical_ratio and n_dead >= MIN_DEAD_FOR_CRITICAL:
                table_status = 'CRITICAL'
            elif bloat_ratio >= critical_ratio and n_dead < MIN_DEAD_FOR_CRITICAL:
                table_status = 'WARNING'  # Demote to WARNING for tiny tables
            elif bloat_ratio >= warn_ratio:
                table_status = 'WARNING'

            # Check vacuum freshness for critical tables
            if is_critical_table and days_since is not None:
                if days_since > critical_vacuum_days:
                    table_status = 'CRITICAL'

            table_info = {
                'table': table_name,
                'live_tuples': n_live,
                'dead_tuples': n_dead,
                'bloat_ratio': round(bloat_ratio, 4),
                'days_since_vacuum': round(days_since, 1) if days_since else None,
                'last_vacuum': str(table['last_any_vacuum']) if table['last_any_vacuum'] else None,
                'status': table_status,
                'is_critical': is_critical_table
            }

            result['tables'].append(table_info)

            if table_status == 'CRITICAL' and is_critical_table:
                result['critical_tables_at_risk'].append(table_info)
            elif table_status == 'WARNING':
                result['warn_tables'].append(table_info)

        # Determine overall severity
        if result['critical_tables_at_risk']:
            result['status'] = 'CRITICAL'
            result['severity_score'] = ADR010_SEVERITY['CRITICAL']['score']
        elif result['warn_tables']:
            result['status'] = 'WARNING'
            result['severity_score'] = ADR010_SEVERITY['WARNING']['score']

        # Limit tables in output to top 20 by dead tuples
        result['tables'] = sorted(
            result['tables'],
            key=lambda x: x['dead_tuples'],
            reverse=True
        )[:20]

        return result


# =============================================================================
# MODULE 3: HIGH-IMPACT SLOW QUERY MONITOR (Priority 3 - Performance)
# =============================================================================

class SlowQueryMonitor:
    """
    Captures strategically problematic queries - not cosmetic performance tuning.

    Uses: pg_stat_statements

    Note: Does NOT suggest indexes or modify schema.
          Produces curated, governance-loggable shortlist only.
    """

    def __init__(self, conn, config: Dict):
        self.conn = conn
        self.config = config

    def check_slow_queries(self) -> Dict[str, Any]:
        """
        Check for high-impact slow queries.

        Returns dict with:
        - status: NORMAL/WARNING/CRITICAL
        - slow_queries: list of top N most expensive queries
        - total_queries_analyzed: count
        """
        cur = self.conn.cursor(cursor_factory=RealDictCursor)

        # Check if pg_stat_statements is available
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
            ) AS has_extension
        """)

        has_extension = cur.fetchone()['has_extension']

        if not has_extension:
            cur.close()
            return {
                'status': 'NORMAL',
                'severity_score': 0.0,
                'message': 'pg_stat_statements extension not installed',
                'slow_queries': [],
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

        mean_time_threshold = self.config['mean_time_warn_ms']
        min_calls = self.config['min_calls']
        top_n = self.config['top_n_queries']

        # Query slow statements
        try:
            cur.execute("""
                SELECT
                    queryid,
                    LEFT(query, 500) AS query_text,
                    calls,
                    total_exec_time AS total_time_ms,
                    mean_exec_time AS mean_time_ms,
                    min_exec_time AS min_time_ms,
                    max_exec_time AS max_time_ms,
                    stddev_exec_time AS stddev_time_ms,
                    rows,
                    shared_blks_hit,
                    shared_blks_read,
                    CASE
                        WHEN (shared_blks_hit + shared_blks_read) > 0
                        THEN shared_blks_hit::float / (shared_blks_hit + shared_blks_read)
                        ELSE 1.0
                    END AS cache_hit_ratio
                FROM pg_stat_statements
                WHERE calls >= %s
                ORDER BY total_exec_time DESC
                LIMIT %s
            """, (min_calls, top_n * 2))  # Get extra to filter

            statements = cur.fetchall()
        except Exception as e:
            cur.close()
            return {
                'status': 'NORMAL',
                'severity_score': 0.0,
                'message': f'Error querying pg_stat_statements: {str(e)}',
                'slow_queries': [],
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

        cur.close()

        result = {
            'status': 'NORMAL',
            'severity_score': 0.0,
            'slow_queries': [],
            'total_queries_analyzed': len(statements),
            'queries_above_threshold': 0,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        focus_schemas = self.config['focus_schemas']

        for stmt in statements:
            mean_time = safe_float(stmt['mean_time_ms']) or 0
            total_time = safe_float(stmt['total_time_ms']) or 0
            query_text = stmt['query_text'] or ''

            # Check if query touches focus schemas
            touches_focus = any(
                schema in query_text.lower()
                for schema in focus_schemas
            )

            if mean_time >= mean_time_threshold:
                result['queries_above_threshold'] += 1

                query_info = {
                    'queryid': str(stmt['queryid']),
                    'query_fingerprint': query_text[:200],
                    'calls': stmt['calls'],
                    'mean_time_ms': round(mean_time, 2),
                    'total_time_ms': round(total_time, 2),
                    'max_time_ms': round(safe_float(stmt['max_time_ms']) or 0, 2),
                    'rows_per_call': round((stmt['rows'] or 0) / max(stmt['calls'], 1), 2),
                    'cache_hit_ratio': round(safe_float(stmt['cache_hit_ratio']) or 0, 4),
                    'touches_focus_schema': touches_focus,
                    'severity': 'WARNING' if mean_time >= mean_time_threshold else 'NORMAL'
                }

                result['slow_queries'].append(query_info)

        # Limit to top N
        result['slow_queries'] = result['slow_queries'][:top_n]

        # Determine severity
        if result['queries_above_threshold'] > 0:
            # Check if any touch focus schemas
            focus_affected = any(q['touches_focus_schema'] for q in result['slow_queries'])
            if focus_affected:
                result['status'] = 'WARNING'
                result['severity_score'] = ADR010_SEVERITY['WARNING']['score']
            else:
                result['status'] = 'WARNING'
                result['severity_score'] = ADR010_SEVERITY['WARNING']['score'] * 0.5

        return result


# =============================================================================
# MAIN SENTINEL CLASS
# =============================================================================

class SentinelDBIntegrity:
    """
    Sentinel_DB_Integrity v1.0

    Protects data integrity and perception quality.
    Three modules in priority order:
    1. Lock Monitor (Correctness)
    2. Bloat Watchdog (Stability)
    3. Slow Query Monitor (Performance)

    G1 FAULT TOLERANCE:
    - Each module wrapped in try/except
    - On error: emit SYSTEM_ERROR discrepancy event
    - Continue running other modules even if one fails
    - Never crash the orchestrator
    """

    def __init__(self, config: Dict = None):
        self.config = config or SENTINEL_CONFIG
        self.conn = None
        self.fault_config = self.config.get('fault_tolerance', DEFAULT_SENTINEL_CONFIG['fault_tolerance'])
        self.results = {
            'sentinel': 'Sentinel_DB_Integrity',
            'version': '1.0',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'executor': 'STIG',
            'adr_binding': ['ADR-010', 'ADR-011', 'ADR-013', 'ADR-015'],
            'config_source': 'YAML' if YAML_AVAILABLE else 'DEFAULT',
            'modules': {},
            'module_errors': [],
            'overall_status': 'PENDING',
            'discrepancies_logged': 0
        }
        # Initialize connection with fault tolerance
        self._init_connection()

    def _init_connection(self):
        """Initialize database connection with retry logic."""
        max_retries = self.fault_config.get('max_retries', 3)
        retry_delay = self.fault_config.get('retry_delay_seconds', 5)

        for attempt in range(max_retries):
            try:
                self.conn = get_connection()
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[WARN] DB connection failed (attempt {attempt + 1}/{max_retries}): {e}")
                    import time
                    time.sleep(retry_delay)
                else:
                    self._log_system_error('DB_CONNECTION', str(e))
                    raise

    def _log_system_error(self, module: str, error_msg: str):
        """Log SYSTEM_ERROR discrepancy event (G1 fault tolerance)."""
        error_data = {
            'status': 'ERROR',
            'severity_score': ADR010_SEVERITY['CRITICAL']['score'],
            'module': module,
            'error_message': error_msg[:500],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        self.results['module_errors'].append(error_data)

        # Try to log to discrepancy_events if connection available
        # Schema: ios_id, agent_id, target_table, discrepancy_type, severity, context_data
        if self.conn:
            try:
                cur = self.conn.cursor()
                cur.execute("""
                    INSERT INTO fhq_governance.discrepancy_events (
                        ios_id, agent_id, target_table,
                        discrepancy_type, discrepancy_score, severity,
                        detection_method, context_data, adr_reference
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    'IoS-014',  # Sentinel IoS ID
                    'STIG',
                    module,
                    self.fault_config.get('error_event_type', 'SYSTEM_ERROR'),
                    ADR010_SEVERITY['CRITICAL']['score'],
                    'CRITICAL',  # DB enum value
                    'SENTINEL_FAULT_TOLERANCE',
                    json.dumps(error_data, default=str),
                    'ADR-010'
                ))
                self.conn.commit()
                cur.close()
            except Exception:
                pass  # Fail silently - we're already in error handling

    def _run_module_safe(self, module_name: str, runner_func) -> Tuple[Dict, bool]:
        """
        Run a module with fault tolerance.

        Returns:
            Tuple of (result_dict, success_bool)
        """
        try:
            result = runner_func()
            return result, True
        except Exception as e:
            error_msg = f"{module_name} failed: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg[:200]}")
            self._log_system_error(module_name, str(e))

            # Return error result
            return {
                'status': 'ERROR',
                'severity_score': 0.0,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }, False

    def run_lock_monitor(self) -> Dict:
        """Run Module 1: Lock Monitor"""
        monitor = LockMonitor(self.conn, self.config['lock_monitor'])
        return monitor.check_lock_contention()

    def run_bloat_watchdog(self) -> Dict:
        """Run Module 2: Vacuum & Bloat Watchdog"""
        watchdog = BloatWatchdog(self.conn, self.config['bloat_watchdog'])
        return watchdog.check_table_bloat()

    def run_slow_query_monitor(self) -> Dict:
        """Run Module 3: Slow Query Monitor"""
        monitor = SlowQueryMonitor(self.conn, self.config['slow_query'])
        return monitor.check_slow_queries()

    def log_discrepancy(self, discrepancy_type: str, module: str, data: Dict):
        """Log discrepancy to fhq_governance.discrepancy_events (ADR-010 schema)."""
        if data.get('severity_score', 0) == 0:
            return False

        # Map status to DB enum (INFO, WARN, CRITICAL)
        status = data.get('status', 'NORMAL')
        severity_info = ADR010_SEVERITY.get(status, ADR010_SEVERITY.get('WARNING'))
        db_severity = severity_info.get('db_severity', 'WARN')

        cur = self.conn.cursor()
        try:
            cur.execute("""
                INSERT INTO fhq_governance.discrepancy_events (
                    ios_id, agent_id, target_table,
                    discrepancy_type, discrepancy_score, severity,
                    detection_method, context_data, adr_reference
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                'IoS-014',  # Sentinel IoS ID
                'STIG',
                module,
                discrepancy_type,
                data['severity_score'],
                db_severity,
                'SENTINEL_DB_INTEGRITY',
                json.dumps(data, default=str),
                'ADR-010'
            ))
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            return False
        finally:
            cur.close()

    def log_audit(self):
        """Log sentinel run to ios_audit_log"""
        evidence_hash = compute_hash(json.dumps(self.results, sort_keys=True, default=str))
        self.results['evidence_hash'] = evidence_hash

        cur = self.conn.cursor()
        try:
            cur.execute("""
                INSERT INTO fhq_meta.ios_audit_log
                (audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data, evidence_hash)
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)
            """, (
                'SYSTEM',
                'DB_INTEGRITY_SENTINEL',
                datetime.now(timezone.utc),
                'STIG',
                'G1',
                json.dumps(self.results, default=str),
                evidence_hash[:16]
            ))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
        finally:
            cur.close()

    def run(self) -> Dict:
        """
        Run full sentinel check with G1 fault tolerance.

        Each module is wrapped in try/except to ensure:
        - One failing module doesn't crash the entire sentinel
        - SYSTEM_ERROR events are emitted for failures
        - Orchestrator is never crashed by sentinel
        """
        print("=" * 70)
        print("SENTINEL_DB_INTEGRITY v1.0 (G1 Fault-Tolerant)")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        print(f"Config: {self.results.get('config_source', 'UNKNOWN')}")
        print("ADR Binding: ADR-010, ADR-011, ADR-013, ADR-015")
        print("=" * 70)

        discrepancies = 0
        continue_on_failure = self.fault_config.get('continue_on_module_failure', True)
        statuses = []

        # Module 1: Lock Monitor (Priority 1)
        print("\n[MODULE 1] LOCK MONITOR (Priority: CRITICAL - Correctness)")
        print("-" * 50)
        lock_result, lock_success = self._run_module_safe('lock_monitor', self.run_lock_monitor)
        self.results['modules']['lock_monitor'] = lock_result

        if lock_success:
            icon = {'NORMAL': '+', 'WARNING': '!', 'CRITICAL': 'X'}.get(lock_result['status'], '?')
            print(f"  [{icon}] Status: {lock_result['status']}")
            print(f"      Waiting processes: {lock_result.get('total_waiting', 0)}")
            print(f"      Max wait time: {lock_result.get('max_wait_seconds', 0):.1f}s")
            if lock_result.get('affected_schemas'):
                print(f"      Affected schemas: {', '.join(lock_result['affected_schemas'])}")

            if lock_result['status'] != 'NORMAL':
                if self.log_discrepancy('DB_LOCK_CONTENTION', 'lock_monitor', lock_result):
                    discrepancies += 1
            statuses.append(lock_result['status'])
        else:
            print(f"  [X] ERROR: Module failed - {lock_result.get('error', 'Unknown')[:100]}")
            statuses.append('ERROR')
            if not continue_on_failure:
                self.results['overall_status'] = 'ERROR'
                return self.results

        # Module 2: Bloat Watchdog (Priority 2)
        print("\n[MODULE 2] VACUUM & BLOAT WATCHDOG (Priority: HIGH - Stability)")
        print("-" * 50)
        bloat_result, bloat_success = self._run_module_safe('bloat_watchdog', self.run_bloat_watchdog)
        self.results['modules']['bloat_watchdog'] = bloat_result

        if bloat_success:
            icon = {'NORMAL': '+', 'WARNING': '!', 'CRITICAL': 'X'}.get(bloat_result['status'], '?')
            print(f"  [{icon}] Status: {bloat_result['status']}")
            print(f"      Total dead tuples: {bloat_result.get('total_dead_tuples', 0):,}")
            print(f"      Critical tables at risk: {len(bloat_result.get('critical_tables_at_risk', []))}")

            if bloat_result.get('critical_tables_at_risk'):
                for t in bloat_result['critical_tables_at_risk'][:3]:
                    print(f"        - {t['table']}: bloat={t['bloat_ratio']:.1%}, dead={t['dead_tuples']:,}")

            if bloat_result['status'] != 'NORMAL':
                if self.log_discrepancy('DB_BLOAT_RISK', 'bloat_watchdog', bloat_result):
                    discrepancies += 1
            statuses.append(bloat_result['status'])
        else:
            print(f"  [X] ERROR: Module failed - {bloat_result.get('error', 'Unknown')[:100]}")
            statuses.append('ERROR')
            if not continue_on_failure:
                self.results['overall_status'] = 'ERROR'
                return self.results

        # Module 3: Slow Query Monitor (Priority 3)
        print("\n[MODULE 3] SLOW QUERY MONITOR (Priority: MEDIUM - Performance)")
        print("-" * 50)
        slow_result, slow_success = self._run_module_safe('slow_query_monitor', self.run_slow_query_monitor)
        self.results['modules']['slow_query_monitor'] = slow_result

        if slow_success:
            icon = {'NORMAL': '+', 'WARNING': '!', 'CRITICAL': 'X'}.get(slow_result['status'], '?')
            print(f"  [{icon}] Status: {slow_result['status']}")
            print(f"      Queries analyzed: {slow_result.get('total_queries_analyzed', 0)}")
            print(f"      Above threshold: {slow_result.get('queries_above_threshold', 0)}")

            if slow_result.get('slow_queries'):
                print("      Top slow queries:")
                for q in slow_result['slow_queries'][:3]:
                    focus_tag = " [FOCUS]" if q.get('touches_focus_schema') else ""
                    print(f"        - {q.get('mean_time_ms', 0):.0f}ms avg, {q.get('calls', 0)} calls{focus_tag}")

            if slow_result['status'] != 'NORMAL':
                if self.log_discrepancy('SLOW_QUERY_CANDIDATE', 'slow_query_monitor', slow_result):
                    discrepancies += 1
            statuses.append(slow_result['status'])
        else:
            print(f"  [X] ERROR: Module failed - {slow_result.get('error', 'Unknown')[:100]}")
            statuses.append('ERROR')

        # Determine overall status (worst of all modules)
        if 'ERROR' in statuses:
            self.results['overall_status'] = 'ERROR'
        elif 'CRITICAL' in statuses:
            self.results['overall_status'] = 'CRITICAL'
        elif 'WARNING' in statuses:
            self.results['overall_status'] = 'WARNING'
        else:
            self.results['overall_status'] = 'NORMAL'

        self.results['discrepancies_logged'] = discrepancies

        # Log to audit (also fault-tolerant)
        try:
            self.log_audit()
        except Exception as e:
            print(f"[WARN] Audit logging failed: {e}")
            self._log_system_error('AUDIT_LOG', str(e))

        # Summary
        print("\n" + "=" * 70)
        print(f"OVERALL STATUS: {self.results['overall_status']}")
        print(f"Discrepancies logged: {discrepancies}")
        if self.results['module_errors']:
            print(f"Module errors: {len(self.results['module_errors'])}")
        print(f"Evidence hash: {self.results.get('evidence_hash', 'N/A')[:32]}...")
        print("=" * 70)

        return self.results

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


# =============================================================================
# PUBLIC API
# =============================================================================

def run_db_integrity_sentinel(config: Dict = None) -> Dict:
    """Public API for DB integrity sentinel."""
    sentinel = SentinelDBIntegrity(config)
    try:
        return sentinel.run()
    finally:
        sentinel.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run Sentinel_DB_Integrity v1.0"""
    results = run_db_integrity_sentinel()

    # Exit code: 0 for NORMAL/WARNING, 1 for CRITICAL
    return results['overall_status'] != 'CRITICAL'


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
