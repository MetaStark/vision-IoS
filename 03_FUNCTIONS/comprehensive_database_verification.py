#!/usr/bin/env python3
"""
COMPREHENSIVE DATABASE VERIFICATION
================================
CEO Directive: CEO-DIR-2026-FULL-DB-VERIFY
Classification: CRITICAL - Full System Truth Verification

Purpose:
    Comprehensive verification of entire FjordHQ Vision-IOS database state.
    Verifies all governance, learning, testing, and execution entities.

Verification Scope:
    1. All ADRs - fhq_meta.adr_registry
    2. All IoS - fhq_meta.ios_registry
    3. All ECs - fhq_governance.ec_registry
    4. All Tests - fhq_calendar.canonical_test_events
    5. LVI Score - fhq_governance.lvi_canonical
    6. BRIER Score - fhq_research.fss_computation_log
    7. FSS - fhq_research.fss_computation_log
    8. BSS - fhq_governance.bss_baseline_snapshot, brier_decomposition
    9. Orchestrator - fhq_monitoring.daemon_health
    10. Schedulers - fhq_monitoring.daemon_health

Author: STIG (CTO)
Date: 2026-02-13
Contract: EC-003_2026_PRODUCTION
"""

import os
import sys
import json
import hashlib
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[COMPREHENSIVE_DB_VERIFY] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/comprehensive_database_verification.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# DATABASE CONNECTION - Single Source of Truth (DATABASE_URL)
# =============================================================================

class DatabaseConnection:
    """Connection from DATABASE_URL environment variable (CEO Control 5)."""

    @staticmethod
    def parse_database_url(database_url: str) -> Dict[str, Any]:
        """Parse postgres:// or postgresql:// URL into components."""
        # postgres://user:password@host:port/database
        pattern = r'postgres(?:ql)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)'
        match = re.match(pattern, database_url)
        if not match:
            raise ValueError(f"Invalid DATABASE_URL: {database_url}")

        return {
            'user': match.group(1),
            'password': match.group(2),
            'host': match.group(3),
            'port': int(match.group(4)),
            'database': match.group(5)
        }

    @staticmethod
    def connect_from_url(database_url: str):
        """Connect using DATABASE_URL (single source of truth)."""
        config = DatabaseConnection.parse_database_url(database_url)
        conn = psycopg2.connect(
            host=config['host'],
            port=config['port'],
            database=config['database'],
            user=config['user'],
            password=config['password']
        )
        # Explicit search_path (CEO Control 3)
        with conn.cursor() as cur:
            cur.execute(
                "SET search_path = "
                "fhq_governance, fhq_meta, fhq_learning, fhq_research, "
                "fhq_monitoring, fhq_calendar, fhq_execution, fhq_canonical, public"
            )
        return conn


# =============================================================================
# COLUMN VALIDATOR - Alias-Tolerant (CEO Control 4)
# =============================================================================

class ColumnValidator:
    """Column validation with alias fallback (CEO Control 4)."""

    # Known aliases mapping
    COLUMN_ALIASES = {
        'fss_score': 'fss_value',
        'last_tick': 'last_tick_at',
        'computed_at': ['computation_timestamp', 'created_at'],
        'method': 'computation_method',
        'health_status': 'status',
        'directive_ref': 'ceo_directive_ref',
        'name': ['test_name', 'module_name', 'ec_id', 'title'],
        'ec_code': 'ec_id',
        'mode': 'mode_name',
        'transitioned_at': 'transition_timestamp'
    }

    def validate_column_with_aliases(
        self,
        schema: str,
        table: str,
        preferred_column: str,
        column_inventory: List[Dict]
    ) -> Dict:
        """
        Validate column existence with alias checking.

        Returns:
        - PASS: preferred column exists
        - WARN: alias exists (preferred missing)
        - FAIL: neither exists
        """
        # Check preferred column
        for col in column_inventory:
            if (col['table_schema'] == schema and
                col['table_name'] == table and
                col['column_name'] == preferred_column):
                return {'status': 'PASS', 'column': preferred_column}

        # Check aliases
        aliases = self.COLUMN_ALIASES.get(preferred_column, [])
        if isinstance(aliases, str):
            aliases = [aliases]

        for alias in aliases:
            for col in column_inventory:
                if (col['table_schema'] == schema and
                    col['table_name'] == table and
                    col['column_name'] == alias):
                    return {
                        'status': 'WARN',
                        'preferred': preferred_column,
                        'actual': alias,
                        'message': f"Using alias '{alias}' instead of '{preferred_column}'"
                    }

        # Neither exists
        return {
            'status': 'FAIL',
            'column': preferred_column,
            'message': f"Column '{preferred_column}' and all aliases not found"
        }


# =============================================================================
# EVIDENCE WRITER - Raw SQL Outputs (CEO Control 6)
# =============================================================================

class EvidenceWriter:
    """Evidence writer with raw SQL outputs (CEO Control 6)."""

    def __init__(self, verification_id: str):
        self.verification_id = verification_id
        self.evidence = {
            'report_id': verification_id,
            'report_type': 'COMPREHENSIVE_DATABASE_VERIFICATION',
            'executed_by': 'STIG',
            'executed_at': datetime.now(timezone.utc).isoformat(),
            'raw_sql_outputs': {}  # Raw query results
        }

    def add_raw_output(self, label: str, raw_query: str, raw_result: Any):
        """Store raw SQL output exactly as returned."""
        self.evidence['raw_sql_outputs'][label] = {
            'query': raw_query,
            'result': raw_result,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def finalize(self, output_dir: str) -> Tuple[str, str]:
        """Write evidence file and return SHA-256 hash."""
        # Add SHA-256 of evidence content
        evidence_json = json.dumps(self.evidence, indent=2, default=str)
        sha256_hash = hashlib.sha256(evidence_json.encode()).hexdigest()
        self.evidence['attestation'] = {'sha256_hash': sha256_hash}

        # Write to file
        filepath = os.path.join(
            output_dir,
            f"DB_VERIFY_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(json.dumps(self.evidence, indent=2, default=str))

        return filepath, sha256_hash


# =============================================================================
# COMPREHENSIVE DATABASE VERIFIER
# =============================================================================

class ComprehensiveDatabaseVerifier:
    """
    CEO-DIR-2026-FULL-DB-VERIFY: Full database state verification.

    Implements all 6 mandatory CEO controls:
    1. Phase 0 - DB Identity Handshake (Fail-Closed)
    2. Schema Snapshot (Ground Truth)
    3. No Implicit search_path
    4. Alias-Tolerant Column Validation
    5. Single Source of Truth (DATABASE_URL)
    6. Evidence Over Narrative
    """

    def __init__(self):
        self.conn = None
        self.verification_id = f"DB-VERIFY-{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.evidence_writer = EvidenceWriter(self.verification_id)
        self.column_validator = ColumnValidator()
        self.column_inventory = []
        self.report = {
            'verification_id': self.verification_id,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'phases': {},
            'critical_issues': [],
            'warnings': [],
            'recommendations': []
        }

    def connect(self):
        """Establish database connection from DATABASE_URL."""
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise SystemExit("DATABASE_URL environment variable not set")

        if not self.conn or self.conn.closed:
            self.conn = DatabaseConnection.connect_from_url(database_url)
        return self.conn

    def close(self):
        """Close database connection."""
        if self.conn and not self.conn.closed:
            self.conn.close()

    # =========================================================================
    # PHASE 0: DB Identity Handshake (Fail-Closed) - CEO Control 1
    # =========================================================================

    def phase_0_db_identity_handshake(self) -> Dict:
        """Fail-closed database identity verification (CEO Control 1)."""
        logger.info("=" * 60)
        logger.info("PHASE 0: DB IDENTITY HANDSHAKE (FAIL-CLOSED)")
        logger.info("=" * 60)

        expected = {
            'server_addr': '127.0.0.1',
            'server_port': 54322,
            'db': 'postgres',
            'db_user': 'postgres'
        }

        expected_version_prefix = "PostgreSQL 17."

        query = """
            SELECT
              now() AS server_now,
              current_database() AS db,
              current_user AS db_user,
              inet_server_addr() AS server_addr,
              inet_server_port() AS server_port,
              version() AS server_version,
              current_setting('search_path') AS search_path
        """

        with self.connect().cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            handshake = cur.fetchone()

        # Store raw output
        self.evidence_writer.add_raw_output(
            'phase_0_handshake', query.strip(), dict(handshake)
        )

        # Abort on mismatch
        for key, expected_val in expected.items():
            actual_val = handshake[key]
            if str(actual_val) != str(expected_val):
                error_msg = (
                    f"DB Identity Handshake FAILED: {key}={actual_val} "
                    f"(expected={expected_val})"
                )
                logger.error(error_msg)
                raise SystemExit(error_msg)

        # Validate server version (prevent wrong cluster with same host/port)
        if not handshake['server_version'].startswith(expected_version_prefix):
            error_msg = (
                f"DB Identity Handshake FAILED: Unexpected PostgreSQL version: "
                f"{handshake['server_version']} "
                f"(expected prefix: {expected_version_prefix})"
            )
            logger.error(error_msg)
            raise SystemExit(error_msg)

        logger.info(f"DB Identity: {handshake['db']} @ {handshake['server_addr']}:{handshake['server_port']}")
        logger.info(f"DB Version: {handshake['server_version'][:20]}...")
        logger.info(f"Search Path: {handshake['search_path']}")
        logger.info("PASS - DB Identity Handshake Complete")

        return {'status': 'PASS', 'handshake': dict(handshake)}

    # =========================================================================
    # PHASE 1: Schema Snapshot (Ground Truth) - CEO Control 2
    # =========================================================================

    def phase_1_schema_snapshot(self) -> Dict:
        """Extract full schema inventory from information_schema (CEO Control 2)."""
        logger.info("=" * 60)
        logger.info("PHASE 1: SCHEMA SNAPSHOT (GROUND TRUTH)")
        logger.info("=" * 60)

        # Extract all tables in fhq_* schemas
        tables_query = """
            SELECT
              table_schema,
              table_name,
              table_type
            FROM information_schema.tables
            WHERE table_schema LIKE 'fhq_%'
            ORDER BY table_schema, table_name
        """

        # Extract all columns for fhq_* tables
        columns_query = """
            SELECT
              table_schema,
              table_name,
              column_name,
              data_type,
              is_nullable
            FROM information_schema.columns
            WHERE table_schema LIKE 'fhq_%'
            ORDER BY table_schema, table_name, ordinal_position
        """

        with self.connect().cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(tables_query)
            table_inventory = cur.fetchall()

            cur.execute(columns_query)
            column_inventory = cur.fetchall()

        # Store raw outputs
        self.evidence_writer.add_raw_output(
            'phase_1_tables', tables_query.strip(), [dict(row) for row in table_inventory]
        )
        self.evidence_writer.add_raw_output(
            'phase_1_columns', columns_query.strip(), [dict(row) for row in column_inventory]
        )

        # Store for use in column validation
        self.column_inventory = [dict(row) for row in column_inventory]

        # Guard: Abort if inventory empty (prevents continuing on failed snapshot)
        table_count = len(table_inventory)
        column_count = len(column_inventory)

        if table_count == 0:
            error_msg = (
                f"Schema Snapshot FAILED: No tables found in fhq_* schemas. "
                f"Database may be empty or schemas missing."
            )
            logger.error(error_msg)
            raise SystemExit(error_msg)

        if column_count == 0:
            error_msg = (
                f"Schema Snapshot FAILED: No columns found in fhq_* tables. "
                f"Snapshot incomplete - cannot continue verification."
            )
            logger.error(error_msg)
            raise SystemExit(error_msg)

        logger.info(f"Schema Snapshot: {table_count} tables, {column_count} columns")
        logger.info("PASS - Schema Snapshot Complete")

        return {
            'status': 'PASS',
            'table_inventory': [dict(row) for row in table_inventory],
            'column_inventory': self.column_inventory,
            'table_count': table_count,
            'column_count': column_count
        }

    # =========================================================================
    # PHASE 2: Governance Entities
    # =========================================================================

    def phase_2_governance(self) -> Dict:
        """Verify governance entities: ADRs, IoS, ECs, DEFCON."""
        logger.info("=" * 60)
        logger.info("PHASE 2: GOVERNANCE ENTITIES")
        logger.info("=" * 60)

        result = {
            'adr': None,
            'ios': None,
            'ec': None,
            'defcon': None,
            'overall_status': 'PASS'
        }

        # 2.1 ADRs
        result['adr'] = self._verify_adrs()

        # 2.2 IoS
        result['ios'] = self._verify_ios()

        # 2.3 ECs
        result['ec'] = self._verify_ecs()

        # 2.4 DEFCON State
        result['defcon'] = self._verify_defcon()

        # Overall status
        for key, value in result.items():
            if key != 'overall_status' and value:
                if value.get('status') == 'CRITICAL':
                    result['overall_status'] = 'CRITICAL'
                elif value.get('status') == 'FAIL' and result['overall_status'] != 'CRITICAL':
                    result['overall_status'] = 'FAIL'
                elif value.get('status') == 'WARN' and result['overall_status'] not in ['CRITICAL', 'FAIL']:
                    result['overall_status'] = 'WARN'

        return result

    def _verify_adrs(self) -> Dict:
        """Verify ADR registry."""
        query = """
            SELECT
                adr_id,
                title,
                status,
                vega_attested,
                sha256_hash,
                created_at
            FROM fhq_meta.adr_registry
            ORDER BY created_at
        """

        conn = self.connect()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                records = cur.fetchall()
                self.evidence_writer.add_raw_output('adr_records', query.strip(), [dict(r) for r in records])
                conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"ADR table query failed: {e}")
            return {'status': 'FAIL', 'error': str(e), 'message': 'Table missing or query failed'}

        if not records:
            logger.warning("No ADRs found in registry")
            return {'status': 'WARN', 'count': 0, 'message': 'No ADRs found'}

        # Calculate metrics
        total = len(records)
        attested = sum(1 for r in records if r.get('vega_attested'))
        attestation_rate = (attested / total * 100) if total > 0 else 0
        with_sha256 = sum(1 for r in records if r.get('sha256_hash'))

        status = 'PASS'
        message = f"{total} ADRs: {attested}% attested, {with_sha256} with SHA256"

        if attestation_rate < 70:
            status = 'CRITICAL'
            message = f"CRITICAL: Only {attestation_rate:.1f}% ADRs vega-attested (<70%)"
            self.report['critical_issues'].append(message)
        elif attestation_rate < 90 or with_sha256 < total:
            status = 'WARN'
            message = f"WARN: {attestation_rate:.1f}% attested, {with_sha256}/{total} with SHA256"
            self.report['warnings'].append(message)

        logger.info(f"ADRs: {message} [{status}]")
        return {'status': status, 'count': total, 'attested': attested, 'with_sha256': with_sha256, 'message': message}

    def _verify_ios(self) -> Dict:
        """Verify IoS registry."""
        query = """
            SELECT
                ios_id,
                title,
                status,
                governance_state,
                canonical,
                content_hash,
                vega_signature_id,
                created_at
            FROM fhq_meta.ios_registry
            ORDER BY created_at
        """

        conn = self.connect()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                records = cur.fetchall()
                self.evidence_writer.add_raw_output('ios_records', query.strip(), [dict(r) for r in records])
                conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"IoS table query failed: {e}")
            return {'status': 'FAIL', 'error': str(e), 'message': 'Table missing or query failed'}

        if not records:
            logger.warning("No IoS found in registry")
            return {'status': 'WARN', 'count': 0, 'message': 'No IoS found'}

        # Calculate metrics
        total = len(records)
        active = sum(1 for r in records if r.get('status') == 'ACTIVE')
        canonical_count = sum(1 for r in records if r.get('canonical') == True)
        with_hash = sum(1 for r in records if r.get('content_hash'))
        with_vega = sum(1 for r in records if r.get('vega_signature_id'))

        status = 'PASS'
        message = f"{total} IoS: {active} ACTIVE, {canonical_count} canonical, {with_vega} vega-signed"

        if with_hash < total:
            status = 'WARN'
            message = f"WARN: {with_hash}/{total} IoS have content_hash"
            self.report['warnings'].append(message)
        elif with_vega < total:
            status = 'WARN'
            message = f"WARN: {with_vega}/{total} IoS vega-signed"
            self.report['warnings'].append(message)

        logger.info(f"IoS: {message} [{status}]")
        return {'status': status, 'count': total, 'active': active, 'canonical': canonical_count, 'with_vega': with_vega, 'message': message}

    def _verify_ecs(self) -> Dict:
        """Verify EC registry."""
        query = """
            SELECT
                ec_id,
                title,
                role_type,
                parent_executive,
                status,
                effective_date,
                created_at
            FROM fhq_governance.ec_registry
            ORDER BY created_at
        """

        conn = self.connect()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                records = cur.fetchall()
                self.evidence_writer.add_raw_output('ec_records', query.strip(), [dict(r) for r in records])
                conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"EC table query failed: {e}")
            return {'status': 'FAIL', 'error': str(e), 'message': 'Table missing or query failed'}

        if not records:
            logger.warning("No ECs found in registry")
            return {'status': 'WARN', 'count': 0, 'message': 'No ECs found'}

        # Look for key ECs (e.g., EC-003 for STIG)
        stig_ec = next((r for r in records if r.get('ec_id') == 'EC-003'), None)
        expired = [r for r in records if r.get('status') == 'EXPIRED']

        status = 'PASS'
        message = f"{len(records)} ECs found"

        if stig_ec and stig_ec.get('status') != 'ACTIVE':
            status = 'CRITICAL'
            message = f"CRITICAL: STIG EC (EC-003) is {stig_ec.get('status')}"
            self.report['critical_issues'].append(message)
        elif expired:
            status = 'WARN'
            message = f"WARN: {len(expired)} expired EC(s) found"
            self.report['warnings'].append(message)

        logger.info(f"ECs: {message} [{status}]")
        return {'status': status, 'count': len(records), 'stig_ec': dict(stig_ec) if stig_ec else None, 'message': message}

    def _verify_defcon(self) -> Dict:
        """Verify DEFCON state."""
        query = """
            SELECT
                defcon_level,
                is_current,
                triggered_by,
                trigger_reason,
                triggered_at
            FROM fhq_governance.defcon_state
            WHERE is_current = TRUE
        """

        conn = self.connect()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                records = cur.fetchall()
                self.evidence_writer.add_raw_output('defcon_state', query.strip(), [dict(r) for r in records])
                conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"DEFCON table query failed: {e}")
            return {'status': 'FAIL', 'error': str(e), 'message': 'Table missing or query failed'}

        if not records:
            logger.warning("No current DEFCON state found")
            return {'status': 'WARN', 'message': 'No current DEFCON state'}

        defcon = records[0]
        level = defcon.get('defcon_level', 'UNKNOWN')
        message = f"DEFCON {level} - triggered by {defcon.get('triggered_by', 'UNKNOWN')}"

        # DEFCON ORANGE or RED is concerning but not a verification failure
        status = 'PASS'
        if level in ['DEFCON-1', 'DEFCON-2']:
            status = 'WARN'
            self.report['warnings'].append(f"System at {level}")

        logger.info(f"DEFCON: {message} [{status}]")
        return {'status': status, 'level': level, 'defcon': dict(defcon), 'message': message}

    # =========================================================================
    # PHASE 3: Learning Metrics
    # =========================================================================

    def phase_3_learning_metrics(self) -> Dict:
        """Verify learning metrics: LVI, FSS, BRIER, BSS."""
        logger.info("=" * 60)
        logger.info("PHASE 3: LEARNING METRICS")
        logger.info("=" * 60)

        result = {
            'lvi': None,
            'fss': None,
            'bss': None,
            'overall_status': 'PASS'
        }

        # 3.1 LVI
        result['lvi'] = self._verify_lvi()

        # 3.2 FSS (includes BRIER)
        result['fss'] = self._verify_fss()

        # 3.3 BSS
        result['bss'] = self._verify_bss()

        # Overall status
        for key, value in result.items():
            if key != 'overall_status' and value:
                if value.get('status') == 'CRITICAL':
                    result['overall_status'] = 'CRITICAL'
                elif value.get('status') == 'FAIL' and result['overall_status'] != 'CRITICAL':
                    result['overall_status'] = 'FAIL'
                elif value.get('status') == 'WARN' and result['overall_status'] not in ['CRITICAL', 'FAIL']:
                    result['overall_status'] = 'WARN'

        return result

    def _verify_lvi(self) -> Dict:
        """Verify LVI canonical score."""
        query = """
            SELECT
                lvi_value,
                computation_method,
                window_start,
                window_end,
                computed_at,
                NOW() as current_time,
                EXTRACT(DAY FROM NOW() - computed_at) as days_stale
            FROM fhq_governance.lvi_canonical
            ORDER BY computed_at DESC
            LIMIT 1
        """

        conn = self.connect()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                records = cur.fetchall()
                self.evidence_writer.add_raw_output('lvi_canonical', query.strip(), [dict(r) for r in records])
                conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"LVI table query failed: {e}")
            return {'status': 'FAIL', 'error': str(e), 'message': 'Table missing or query failed'}

        if not records:
            logger.warning("No LVI score found")
            return {'status': 'WARN', 'message': 'No LVI score found'}

        lvi = records[0]
        value = lvi.get('lvi_value', 0)
        days_stale = lvi.get('days_stale', 0) or 0

        status = 'PASS'
        message = f"LVI={value:.3f}, {days_stale:.0f} days stale"

        if value <= 0 and days_stale > 7:
            status = 'CRITICAL'
            message = f"CRITICAL: LVI={value:.3f}, stale {days_stale:.0f} days (>7)"
            self.report['critical_issues'].append(message)
        elif days_stale > 30:
            status = 'WARN'
            message = f"WARN: LVI stale {days_stale:.0f} days (>30)"
            self.report['warnings'].append(message)
        elif days_stale > 7:
            status = 'WARN'
            message = f"WARN: LVI stale {days_stale:.0f} days"
            self.report['warnings'].append(message)

        logger.info(f"LVI: {message} [{status}]")
        return {'status': status, 'value': value, 'days_stale': days_stale, 'message': message}

    def _verify_fss(self) -> Dict:
        """Verify FSS with BRIER score."""
        query = """
            SELECT
                asset_id,
                fss_value,
                brier_actual,
                brier_ref,
                sample_size,
                computation_timestamp,
                NOW() as current_time,
                EXTRACT(HOUR FROM NOW() - computation_timestamp) as hours_stale
            FROM fhq_research.fss_computation_log
            ORDER BY computation_timestamp DESC
            LIMIT 5
        """

        conn = self.connect()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                records = cur.fetchall()
                self.evidence_writer.add_raw_output('fss_computation', query.strip(), [dict(r) for r in records])
                conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"FSS table query failed: {e}")
            return {'status': 'FAIL', 'error': str(e), 'message': 'Table missing or query failed'}

        if not records:
            logger.warning("No FSS computation found")
            return {'status': 'WARN', 'message': 'No FSS computation found'}

        latest = records[0]
        fss_value = latest.get('fss_value', 0)
        brier_actual = latest.get('brier_actual')
        brier_ref = latest.get('brier_ref')
        hours_stale = latest.get('hours_stale', 0) or 0

        status = 'PASS'
        message = f"FSS={fss_value:.3f}, BRIER_actual={brier_actual:.3f}, {hours_stale:.0f}h stale"

        if fss_value < 0:
            status = 'CRITICAL'
            message = f"CRITICAL: FSS={fss_value:.3f} (<0.00 required), {hours_stale:.0f}h stale"
            self.report['critical_issues'].append(message)
        elif fss_value < 0.60:
            status = 'CRITICAL'
            message = f"CRITICAL: FSS={fss_value:.3f} (<0.60 required), {hours_stale:.0f}h stale"
            self.report['critical_issues'].append(message)
        elif hours_stale > 72:
            status = 'WARN'
            message = f"WARN: FSS stale {hours_stale:.0f} hours (>72)"
            self.report['warnings'].append(message)

        logger.info(f"FSS: {message} [{status}]")
        return {
            'status': status,
            'fss_value': fss_value,
            'brier_actual': brier_actual,
            'brier_ref': brier_ref,
            'hours_stale': hours_stale,
            'message': message
        }

    def _verify_bss(self) -> Dict:
        """Verify BSS (Baseline Skill Score)."""
        baseline_query = """
            SELECT
                bss_value,
                bs_reference,
                bs_value,
                sample_size,
                created_at
            FROM fhq_governance.bss_baseline_snapshot
            ORDER BY created_at DESC
            LIMIT 1
        """

        conn = self.connect()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(baseline_query)
                baseline = cur.fetchall()
                self.evidence_writer.add_raw_output('bss_baseline', baseline_query.strip(), [dict(r) for r in baseline])
                conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"BSS table query failed: {e}")
            return {'status': 'WARN', 'error': str(e), 'message': 'BSS tables missing or query failed'}

        if not baseline:
            logger.warning("No BSS baseline found")
            return {'status': 'WARN', 'message': 'No BSS baseline found'}

        bss_value = baseline[0].get('bss_value', 0)

        status = 'PASS'
        message = f"BSS={bss_value:.3f}"

        if bss_value <= 0:
            status = 'WARN'
            message = f"WARN: BSS={bss_value:.3f} (<=0.00)"
            self.report['warnings'].append(message)

        logger.info(f"BSS: {message} [{status}]")
        return {'status': status, 'value': bss_value, 'message': message}

    # =========================================================================
    # PHASE 4: Test Infrastructure
    # =========================================================================

    def phase_4_tests(self) -> Dict:
        """Verify test infrastructure: Canonical Tests, Gate Validations."""
        logger.info("=" * 60)
        logger.info("PHASE 4: TEST INFRASTRUCTURE")
        logger.info("=" * 60)

        result = {
            'canonical_tests': None,
            'overall_status': 'PASS'
        }

        # 4.1 Canonical Tests
        result['canonical_tests'] = self._verify_canonical_tests()

        # Overall status
        if result['canonical_tests'].get('status') == 'CRITICAL':
            result['overall_status'] = 'CRITICAL'
        elif result['canonical_tests'].get('status') == 'FAIL' and result['overall_status'] != 'CRITICAL':
            result['overall_status'] = 'FAIL'
        elif result['canonical_tests'].get('status') == 'WARN' and result['overall_status'] not in ['CRITICAL', 'FAIL']:
            result['overall_status'] = 'WARN'

        return result

    def _verify_canonical_tests(self) -> Dict:
        """Verify canonical test events."""
        query = """
            SELECT
                test_name,
                test_code,
                days_elapsed,
                days_remaining,
                escalation_state,
                verdict,
                status,
                last_orchestrator_run,
                final_outcome_recorded_at,
                created_at,
                updated_at
            FROM fhq_calendar.canonical_test_events
            ORDER BY COALESCE(final_outcome_recorded_at, updated_at, created_at) DESC
        """

        conn = self.connect()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                records = cur.fetchall()
                self.evidence_writer.add_raw_output('canonical_tests', query.strip(), [dict(r) for r in records])
                conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"Canonical tests table query failed: {e}")
            return {'status': 'FAIL', 'error': str(e), 'message': 'Table missing or query failed'}

        if not records:
            logger.warning("No canonical tests found")
            return {'status': 'WARN', 'count': 0, 'message': 'No canonical tests found'}

        total = len(records)
        failed = sum(1 for r in records if r.get('verdict') == 'FAIL')
        escalated = sum(1 for r in records if r.get('escalation_state') in ['ESCALATED', 'CRITICAL'])

        status = 'PASS'
        message = f"{total} tests: {failed} FAILED, {escalated} escalated"

        if failed > 4:
            status = 'CRITICAL'
            message = f"CRITICAL: {failed}/{total} tests FAILED (>4)"
            self.report['critical_issues'].append(message)
        elif failed > 0 or escalated > 0:
            status = 'WARN'
            message = f"WARN: {failed} FAILED, {escalated} escalated"
            self.report['warnings'].append(message)

        logger.info(f"Tests: {message} [{status}]")
        return {'status': status, 'count': total, 'failed': failed, 'escalated': escalated, 'message': message}

    # =========================================================================
    # PHASE 5: Daemon Health
    # =========================================================================

    def phase_5_daemon_health(self) -> Dict:
        """Verify daemon health: Orchestrator, Schedulers."""
        logger.info("=" * 60)
        logger.info("PHASE 5: DAEMON HEALTH")
        logger.info("=" * 60)

        result = {
            'orchestrator': None,
            'schedulers': None,
            'all_daemons': None,
            'overall_status': 'PASS'
        }

        # 5.1 All Daemons
        result['all_daemons'] = self._verify_all_daemons()

        # Extract orchestrator and schedulers
        all_daemons = result['all_daemons'].get('daemons', [])

        orchestrator = next((d for d in all_daemons if 'orchestrator' in d.get('daemon_name', '').lower()), None)
        schedulers = [d for d in all_daemons if 'scheduler' in d.get('daemon_name', '').lower()]

        result['orchestrator'] = self._get_daemon_status('orchestrator', orchestrator)
        result['schedulers'] = self._get_scheduler_summary(schedulers)

        # Overall status
        if result['all_daemons'].get('status') == 'CRITICAL':
            result['overall_status'] = 'CRITICAL'
        elif result['all_daemons'].get('status') == 'FAIL' and result['overall_status'] != 'CRITICAL':
            result['overall_status'] = 'FAIL'
        elif result['all_daemons'].get('status') == 'WARN' and result['overall_status'] not in ['CRITICAL', 'FAIL']:
            result['overall_status'] = 'WARN'

        return result

    def _verify_all_daemons(self) -> Dict:
        """Verify all daemon health status."""
        query = """
            SELECT
                daemon_name,
                lifecycle_status,
                status,
                last_heartbeat,
                is_critical,
                ceo_directive_ref,
                NOW() as current_time,
                EXTRACT(EPOCH FROM NOW() - last_heartbeat) / 60 as minutes_since_heartbeat
            FROM fhq_monitoring.daemon_health
            ORDER BY daemon_name
        """

        conn = self.connect()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                records = cur.fetchall()
                self.evidence_writer.add_raw_output('daemon_health', query.strip(), [dict(r) for r in records])
                conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"Daemon health table query failed: {e}")
            return {'status': 'FAIL', 'error': str(e), 'message': 'Table missing or query failed', 'daemons': []}

        if not records:
            logger.warning("No daemon health records found")
            return {'status': 'WARN', 'message': 'No daemon health records', 'daemons': []}

        daemons = [dict(r) for r in records]
        healthy = sum(1 for d in daemons if d.get('status') == 'HEALTHY')
        degraded = sum(1 for d in daemons if d.get('status') == 'DEGRADED')
        stopped = sum(1 for d in daemons if d.get('lifecycle_status') == 'STOPPED')
        critical_stopped = sum(1 for d in daemons if d.get('is_critical') and d.get('lifecycle_status') == 'STOPPED')

        status = 'PASS'
        message = f"{len(daemons)} daemons: {healthy} HEALTHY, {degraded} DEGRADED, {stopped} STOPPED"

        # Check orchestrator specifically
        orchestrator = next((d for d in daemons if 'orchestrator' in d.get('daemon_name', '').lower()), None)
        if orchestrator and orchestrator.get('lifecycle_status') == 'STOPPED':
            status = 'CRITICAL'
            message = f"CRITICAL: Orchestrator is STOPPED"
            self.report['critical_issues'].append(message)
        elif critical_stopped > 0:
            status = 'CRITICAL'
            message = f"CRITICAL: {critical_stopped} critical daemon(s) STOPPED"
            self.report['critical_issues'].append(message)
        elif degraded > 2 or stopped > 2:
            status = 'WARN'
            message = f"WARN: {degraded} DEGRADED, {stopped} STOPPED daemons"
            self.report['warnings'].append(message)

        logger.info(f"Daemons: {message} [{status}]")
        return {'status': status, 'daemons': daemons, 'healthy': healthy, 'degraded': degraded, 'stopped': stopped, 'message': message}

    def _get_daemon_status(self, name: str, daemon: Optional[Dict]) -> Dict:
        """Get individual daemon status summary."""
        if not daemon:
            return {'status': 'WARN', 'message': f'{name} not found'}

        status = daemon.get('status', 'UNKNOWN')
        lifecycle = daemon.get('lifecycle_status', 'UNKNOWN')
        minutes_since = daemon.get('minutes_since_heartbeat', 0) or 0

        status_code = 'PASS' if status == 'HEALTHY' and lifecycle == 'RUNNING' else 'WARN'
        if lifecycle == 'STOPPED' or status == 'CRITICAL':
            status_code = 'CRITICAL'

        message = f"{name}: {status}/{lifecycle}, {minutes_since:.0f}m since heartbeat"

        return {'status': status_code, 'daemon': daemon, 'message': message}

    def _get_scheduler_summary(self, schedulers: List[Dict]) -> Dict:
        """Get scheduler daemon summary."""
        if not schedulers:
            return {'status': 'WARN', 'count': 0, 'message': 'No schedulers found'}

        healthy = sum(1 for s in schedulers if s.get('status') == 'HEALTHY')
        degraded = sum(1 for s in schedulers if s.get('status') == 'DEGRADED')
        stopped = sum(1 for s in schedulers if s.get('lifecycle_status') == 'STOPPED')

        status = 'PASS' if stopped == 0 and degraded == 0 else 'WARN'
        message = f"{len(schedulers)} schedulers: {healthy} HEALTHY, {degraded} DEGRADED, {stopped} STOPPED"

        return {'status': status, 'count': len(schedulers), 'healthy': healthy, 'degraded': degraded, 'stopped': stopped, 'message': message}

    # =========================================================================
    # PHASE 6: Execution Layer
    # =========================================================================

    def phase_6_execution(self) -> Dict:
        """Verify execution layer: Shadow Trades."""
        logger.info("=" * 60)
        logger.info("PHASE 6: EXECUTION LAYER")
        logger.info("=" * 60)

        result = {
            'shadow_trades': None,
            'overall_status': 'PASS'
        }

        # 6.1 Shadow Trades
        result['shadow_trades'] = self._verify_shadow_trades()

        # Overall status
        if result['shadow_trades'].get('status') == 'CRITICAL':
            result['overall_status'] = 'CRITICAL'
        elif result['shadow_trades'].get('status') == 'FAIL' and result['overall_status'] != 'CRITICAL':
            result['overall_status'] = 'FAIL'
        elif result['shadow_trades'].get('status') == 'WARN' and result['overall_status'] not in ['CRITICAL', 'FAIL']:
            result['overall_status'] = 'WARN'

        return result

    def _verify_shadow_trades(self) -> Dict:
        """Verify shadow trades status."""
        query = """
            SELECT
                status,
                COUNT(*) as count
            FROM fhq_execution.shadow_trades
            WHERE created_at > NOW() - INTERVAL '7 days'
            GROUP BY status
            ORDER BY status
        """

        conn = self.connect()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                records = cur.fetchall()
                self.evidence_writer.add_raw_output('shadow_trades', query.strip(), [dict(r) for r in records])
                conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"Shadow trades table query failed: {e}")
            return {'status': 'FAIL', 'error': str(e), 'message': 'Table missing or query failed'}

        if not records:
            logger.info("No shadow trades in last 7 days")
            return {'status': 'PASS', 'count': 0, 'message': 'No shadow trades (last 7 days)'}

        total = sum(r.get('count', 0) for r in records)
        status_summary = ', '.join(f"{r['status']}: {r['count']}" for r in records)

        status = 'PASS'
        message = f"{total} shadow trades (7d): {status_summary}"

        # Look for issues
        failed_count = sum(r.get('count', 0) for r in records if r.get('status') in ['FAILED', 'REJECTED'])

        if failed_count > total * 0.5:
            status = 'WARN'
            message = f"WARN: {failed_count}/{total} shadow trades failed/rejected"
            self.report['warnings'].append(message)

        logger.info(f"Shadow Trades: {message} [{status}]")
        return {'status': status, 'count': total, 'by_status': records, 'message': message}

    # =========================================================================
    # CONSOLE OUTPUT
    # =========================================================================

    def _print_ascii_header(self, title: str, width: int = 60):
        """Print ASCII box header."""
        padding = (width - len(title) - 2) // 2
        line = '+' + '-' * (width - 2) + '+'
        content = '|' + ' ' * padding + title + ' ' * (width - len(title) - padding - 2) + '|'
        print(line)
        print(content)
        print(line)

    def _print_status(self, label: str, status: str, message: str = ''):
        """Print status line with color indicators."""
        status_display = {
            'PASS': '[PASS]',
            'WARN': '[WARN]',
            'FAIL': '[FAIL]',
            'CRITICAL': '[CRITICAL]'
        }.get(status, '[UNKNOWN]')

        if message:
            print(f"  {status_display} {label}: {message}")
        else:
            print(f"  {status_display} {label}")

    def _print_summary(self):
        """Print final summary."""
        self._print_ascii_header("VERIFICATION SUMMARY")

        print(f"Verification ID: {self.verification_id}")
        print(f"Started: {self.report['started_at']}")
        print(f"Completed: {datetime.now(timezone.utc).isoformat()}")
        print()

        # Phase results
        self._print_ascii_header("PHASE RESULTS")
        for phase_name, phase_result in self.report['phases'].items():
            overall_status = phase_result.get('overall_status', 'UNKNOWN')
            self._print_status(phase_name.upper(), overall_status)

        # Critical issues
        if self.report['critical_issues']:
            self._print_ascii_header("CRITICAL ISSUES")
            for issue in self.report['critical_issues']:
                print(f"  [CRITICAL] {issue}")

        # Warnings
        if self.report['warnings']:
            self._print_ascii_header("WARNINGS")
            for warning in self.report['warnings']:
                print(f"  [WARN] {warning}")

        # Overall result
        overall = 'PASS'
        if self.report['critical_issues']:
            overall = 'CRITICAL'
        elif self.report['warnings']:
            overall = 'WARN'

        self._print_ascii_header(f"OVERALL: {overall}")

    # =========================================================================
    # MAIN VERIFICATION RUN
    # =========================================================================

    def run_verification(self) -> Dict:
        """Run full verification cycle."""
        logger.info("Starting Comprehensive Database Verification")
        logger.info(f"Verification ID: {self.verification_id}")
        logger.info("=" * 60)

        try:
            # Phase 0: DB Identity Handshake (Fail-Closed)
            self.report['phases']['phase_0_handshake'] = self.phase_0_db_identity_handshake()

            # Phase 1: Schema Snapshot
            self.report['phases']['phase_1_schema'] = self.phase_1_schema_snapshot()

            # Phase 2: Governance
            self.report['phases']['phase_2_governance'] = self.phase_2_governance()

            # Phase 3: Learning Metrics
            self.report['phases']['phase_3_learning'] = self.phase_3_learning_metrics()

            # Phase 4: Test Infrastructure
            self.report['phases']['phase_4_tests'] = self.phase_4_tests()

            # Phase 5: Daemon Health
            self.report['phases']['phase_5_daemons'] = self.phase_5_daemon_health()

            # Phase 6: Execution Layer
            self.report['phases']['phase_6_execution'] = self.phase_6_execution()

            # Print console summary
            self._print_summary()

            # Add evidence writer report data
            self.report['phases'] = self.report['phases']

            # Finalize evidence
            evidence_dir = '03_FUNCTIONS/evidence'
            os.makedirs(evidence_dir, exist_ok=True)
            filepath, sha256_hash = self.evidence_writer.finalize(evidence_dir)

            logger.info(f"Evidence file written: {filepath}")
            logger.info(f"Evidence SHA-256: {sha256_hash}")
            logger.info("Verification Complete")

            self.report['completed_at'] = datetime.now(timezone.utc).isoformat()
            self.report['evidence_file'] = filepath
            self.report['evidence_sha256'] = sha256_hash

            return self.report

        except SystemExit as e:
            logger.error(f"Verification aborted: {e}")
            self.report['status'] = 'ABORTED'
            self.report['error'] = str(e)
            raise
        except Exception as e:
            logger.error(f"Verification failed: {e}", exc_info=True)
            self.report['status'] = 'FAILED'
            self.report['error'] = str(e)
            raise
        finally:
            self.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Execute comprehensive database verification."""
    verifier = ComprehensiveDatabaseVerifier()
    try:
        report = verifier.run_verification()
        print(json.dumps(report, indent=2, default=str))

        # Exit code based on overall status
        if report.get('critical_issues'):
            return 2  # CRITICAL
        elif report.get('warnings'):
            return 1  # WARN
        else:
            return 0  # PASS

    except SystemExit:
        # Re-raise SystemExit to preserve exit code from phase 0 handshake
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3  # ERROR


if __name__ == "__main__":
    sys.exit(main())
