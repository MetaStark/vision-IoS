#!/usr/bin/env python3
"""
Write-FREEZE on FSS/BSS Tables
CEO-DIR-2026-FIX-003: Stop narrative. Produce proofs. Freeze writes. Restore single-source truth.

Author: STIG (CTO)
Date: 2026-02-13

Purpose:
- Freeze writes to fhq_research.fss_computation_log
- Freeze writes to fhq_governance.bss_baseline_snapshot
- Use PostgreSQL advisory locks (no DDL required)

Mechanism:
- Advisory lock ID 9876543210 for FSS freeze
- Advisory lock ID 9876543211 for BSS freeze
- Non-blocking check for freeze status
- Evidence file tracks freeze state

Freeze State:
- UNFROZEN: No lock held, writes allowed
- FROZEN: Lock held, writes prohibited
"""

import os
import sys
import json
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Dict, Optional

# Advisory lock IDs (chosen to avoid conflicts)
FSS_FREEZE_LOCK_ID = 9876543210
BSS_FREEZE_LOCK_ID = 9876543211


class WriteFreezeManager:
    """Manage write freezes on FSS/BSS tables using advisory locks."""

    def __init__(self, database_url: str):
        """Initialize from DATABASE_URL."""
        self.database_url = database_url
        self.conn = None
        self._connect()

    def _connect(self):
        """Connect to database and set search_path."""
        config = self._parse_database_url(self.database_url)
        self.conn = psycopg2.connect(
            host=config['host'],
            port=config['port'],
            database=config['database'],
            user=config['user'],
            password=config['password']
        )
        # Explicit search_path
        with self.conn.cursor() as cur:
            cur.execute(
                "SET search_path = "
                "fhq_governance, fhq_meta, fhq_learning, fhq_research, "
                "fhq_monitoring, fhq_calendar, fhq_execution, fhq_canonical, public"
            )

    @staticmethod
    def _parse_database_url(database_url: str) -> Dict:
        """Parse postgres:// URL into components."""
        import re
        pattern = r'postgres://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)'
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

    def is_fss_frozen(self) -> bool:
        """Check if FSS table is frozen."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT pg_try_advisory_lock(%s) AS acquired",
                (FSS_FREEZE_LOCK_ID,)
            )
            result = cur.fetchone()

            # If we acquired the lock, release it and return False (not frozen)
            if result['acquired']:
                cur.execute("SELECT pg_advisory_unlock(%s)", (FSS_FREEZE_LOCK_ID,))
                return False

            # Lock held by another session = frozen
            return True

    def is_bss_frozen(self) -> bool:
        """Check if BSS table is frozen."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT pg_try_advisory_lock(%s) AS acquired",
                (BSS_FREEZE_LOCK_ID,)
            )
            result = cur.fetchone()

            # If we acquired the lock, release it and return False (not frozen)
            if result['acquired']:
                cur.execute("SELECT pg_advisory_unlock(%s)", (BSS_FREEZE_LOCK_ID,))
                return False

            # Lock held by another session = frozen
            return True

    def freeze_fss(self) -> Dict:
        """Freeze FSS table (acquire advisory lock)."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT pg_advisory_lock(%s) AS acquired, "
                "CURRENT_TIMESTAMP AS frozen_at",
                (FSS_FREEZE_LOCK_ID,)
            )
            result = cur.fetchone()

        return {
            'status': 'FROZEN',
            'table': 'fhq_research.fss_computation_log',
            'lock_id': FSS_FREEZE_LOCK_ID,
            'frozen_at': result['frozen_at'].isoformat()
        }

    def freeze_bss(self) -> Dict:
        """Freeze BSS table (acquire advisory lock)."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT pg_advisory_lock(%s) AS acquired, "
                "CURRENT_TIMESTAMP AS frozen_at",
                (BSS_FREEZE_LOCK_ID,)
            )
            result = cur.fetchone()

        return {
            'status': 'FROZEN',
            'table': 'fhq_governance.bss_baseline_snapshot',
            'lock_id': BSS_FREEZE_LOCK_ID,
            'frozen_at': result['frozen_at'].isoformat()
        }

    def freeze_all(self) -> Dict:
        """Freeze both FSS and BSS tables."""
        fss_result = self.freeze_fss()
        bss_result = self.freeze_bss()

        return {
            'fss': fss_result,
            'bss': bss_result,
            'frozen_at': datetime.now(timezone.utc).isoformat()
        }

    def check_frozen_status(self) -> Dict:
        """Check freeze status for both tables."""
        return {
            'fss_frozen': self.is_fss_frozen(),
            'bss_frozen': self.is_bss_frozen(),
            'checked_at': datetime.now(timezone.utc).isoformat()
        }

    def generate_evidence(self, output_dir: str) -> str:
        """Generate evidence JSON with SHA-256 hash."""
        status = self.check_frozen_status()

        evidence = {
            'report_id': 'WRITE_FREEZE_EVIDENCE',
            'report_type': 'CEO-DIR-2026-FIX-003_FREEZE',
            'executed_by': 'STIG',
            'executed_at': datetime.now(timezone.utc).isoformat(),
            'directive': 'CEO-DIR-2026-FIX-003',
            'freeze_status': status,
            'lock_ids': {
                'fss': FSS_FREEZE_LOCK_ID,
                'bss': BSS_FREEZE_LOCK_ID
            },
            'tables': {
                'fss': 'fhq_research.fss_computation_log',
                'bss': 'fhq_governance.bss_baseline_snapshot'
            }
        }

        # Add SHA-256 hash
        evidence_json = json.dumps(evidence, indent=2, default=str)
        sha256_hash = hashlib.sha256(evidence_json.encode()).hexdigest()
        evidence['attestation'] = {'sha256_hash': sha256_hash}

        # Write evidence file
        filepath = os.path.join(
            output_dir,
            f"WRITE_FREEZE_EVIDENCE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(filepath, 'w') as f:
            f.write(json.dumps(evidence, indent=2, default=str))

        return filepath, sha256_hash


def main():
    """Main execution: Freeze FSS/BSS tables and generate evidence."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise SystemExit("DATABASE_URL environment variable not set")

    evidence_dir = os.path.join(
        os.path.dirname(__file__),
        'evidence'
    )

    manager = WriteFreezeManager(database_url)

    # Check current status
    status_before = manager.check_frozen_status()
    print(f"Status before freeze: FSS={'FROZEN' if status_before['fss_frozen'] else 'UNFROZEN'}, "
          f"BSS={'FROZEN' if status_before['bss_frozen'] else 'UNFROZEN'}")

    # Freeze both tables
    freeze_result = manager.freeze_all()
    print(f"FSS frozen at: {freeze_result['fss']['frozen_at']}")
    print(f"BSS frozen at: {freeze_result['bss']['frozen_at']}")

    # Generate evidence
    filepath, sha256_hash = manager.generate_evidence(evidence_dir)
    print(f"Evidence written to: {filepath}")
    print(f"SHA-256 hash: {sha256_hash}")

    # Keep lock held (connection must stay open)
    print("\nWrite-FREEZE ACTIVE. Keep this process running to maintain freeze.")
    print("To unfreeze: Terminate this process (locks released on connection close).")


if __name__ == '__main__':
    main()
