#!/usr/bin/env python3
"""
Write-FREEZE Marker Manager (Persistent Freeze)
CEO-DIR-2026-FIX-003: Stop narrative. Produce proofs. Freeze writes. Restore single-source truth.

Author: STIG (CTO)
Date: 2026-02-13

Purpose:
- Create persistent freeze marker file for FSS/BSS tables
- No DDL required (uses file-based lock)
- Daemons must check marker before writes

Mechanism:
- Marker file: 03_FUNCTIONS/.locks/FSS_BSS_FREEZE.lock
- Marker contains freeze timestamp and SHA-256 hash
- Persistent across connections and restarts
"""

import os
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict

LOCK_DIR = os.path.join(os.path.dirname(__file__), '.locks')
FREEZE_MARKER_FILE = os.path.join(LOCK_DIR, 'FSS_BSS_FREEZE.lock')


def ensure_lock_dir():
    """Ensure lock directory exists."""
    os.makedirs(LOCK_DIR, exist_ok=True)


def is_frozen() -> bool:
    """Check if FSS/BSS tables are frozen (marker exists)."""
    return os.path.exists(FREEZE_MARKER_FILE)


def freeze() -> Dict:
    """Create freeze marker."""
    ensure_lock_dir()

    freeze_data = {
        'freeze_type': 'FSS_BSS_WRITE_FREEZE',
        'frozen_at': datetime.now(timezone.utc).isoformat(),
        'executed_by': 'STIG',
        'directive': 'CEO-DIR-2026-FIX-003',
        'tables': {
            'fss': 'fhq_research.fss_computation_log',
            'bss': 'fhq_governance.bss_baseline_snapshot'
        }
    }

    # Add SHA-256
    data_json = json.dumps(freeze_data, indent=2)
    sha256_hash = hashlib.sha256(data_json.encode()).hexdigest()
    freeze_data['attestation'] = {'sha256_hash': sha256_hash}

    # Write marker
    with open(FREEZE_MARKER_FILE, 'w') as f:
        f.write(json.dumps(freeze_data, indent=2))

    return {
        'status': 'FROZEN',
        'frozen_at': freeze_data['frozen_at'],
        'marker_file': FREEZE_MARKER_FILE,
        'sha256_hash': sha256_hash
    }


def unfreeze() -> Dict:
    """Remove freeze marker."""
    if not is_frozen():
        return {'status': 'NOT_FROZEN', 'message': 'No freeze marker exists'}

    os.remove(FREEZE_MARKER_FILE)
    return {'status': 'UNFROZEN', 'marker_file': FREEZE_MARKER_FILE}


def get_freeze_status() -> Dict:
    """Get current freeze status."""
    if not is_frozen():
        return {
            'status': 'UNFROZEN',
            'marker_exists': False
        }

    with open(FREEZE_MARKER_FILE, 'r') as f:
        freeze_data = json.load(f)

    return {
        'status': 'FROZEN',
        'frozen_at': freeze_data['frozen_at'],
        'executed_by': freeze_data['executed_by'],
        'directive': freeze_data['directive'],
        'attestation': freeze_data['attestation'],
        'marker_file': FREEZE_MARKER_FILE
    }


def main():
    """Main execution: Create freeze marker."""
    if is_frozen():
        status = get_freeze_status()
        print(f"Already FROZEN since: {status['frozen_at']}")
        print(f"SHA-256: {status['attestation']['sha256_hash']}")
        return

    result = freeze()
    print(f"Status: {result['status']}")
    print(f"Frozen at: {result['frozen_at']}")
    print(f"Marker file: {result['marker_file']}")
    print(f"SHA-256: {result['sha256_hash']}")


if __name__ == '__main__':
    main()
