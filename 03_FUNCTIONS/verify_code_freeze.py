#!/usr/bin/env python3
"""
verify_code_freeze.py - G2 Code Freeze Verification Tool

CEO Directive CD-G1-G2-WAVE12-20251217 mandates a codebase freeze on
EC-018/EC-020 cognitive stack modules during the G2 governance review.

This script verifies that frozen files have not been modified by comparing
their SHA-256 hashes against the freeze registry.

Usage:
    python verify_code_freeze.py           # Verify all frozen files
    python verify_code_freeze.py --strict  # Exit with error on any mismatch

Freeze Registry: 05_GOVERNANCE/PHASE3/CODE_FREEZE_REGISTRY_G2_20251217.json
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[FREEZE-CHECK] %(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# =============================================================================
# FREEZE REGISTRY (Inline copy for portability)
# =============================================================================
# These hashes represent the exact state of files that passed Wave 11.1
# and are constitutionally locked for G2 governance review.

FROZEN_FILES = {
    "ec018_alpha_daemon.py": {
        # Amendment AMEND-001: Live Price Witness (Constitutional Remediation)
        # Authorization: CD-EC018-LIVE-PRICE-PRECONDITION-20251217
        # Previous hash: 05f9f508bc508569587aeccb64f49cffcb3b719bfa20e46ad2998d8a596be47f
        # Amendment AMEND-002: G2 Reporting Contract Remediation (Observability Only)
        # Authorization: CD-AMEND-002-G2-REPORTING-20251217
        # Previous hash: f3a078d8601b8809da672abc0862b1fb37c1c952fcbdb36436e3b8827408eff7
        "sha256": "195e2d16e1abd99f196abf5ebb2612a3b4ef43ca8316958531b55a33b535fdfd",
        "component": "EC-018 Alpha Daemon",
        "freeze_date": "2025-12-17",
        "amendment_date": "2025-12-17"
    },
    "ios020_sitc_planner.py": {
        "sha256": "2fb7e4ac9db8d076fd204bb752f2d961516f8c99ee33a0eb4c457d4540c41fa0",
        "component": "EC-020 SitC Planner",
        "freeze_date": "2025-12-17"
    },
    "wave11_acceptance_framework.py": {
        "sha256": "e62913914347224f59a083ec0aec82fd4d780447e791a6ecdd3f098761b773e4",
        "component": "Wave 11 Acceptance Framework",
        "freeze_date": "2025-12-17"
    }
}

# Constitutional parameters that must not change
CONSTITUTIONAL_LOCKS = {
    "EQS_HIGH_THRESHOLD": {
        "file": "ios020_sitc_planner.py",
        "pattern": "EQS_HIGH_THRESHOLD = 0.85",
        "value": 0.85,
        "authority": "CEO Directive - Tier-1 Constitutional"
    },
    "EQS_MEDIUM_THRESHOLD": {
        "file": "ios020_sitc_planner.py",
        "pattern": "EQS_MEDIUM_THRESHOLD = 0.50",
        "value": 0.50,
        "authority": "CEO Directive"
    }
}


def get_base_path() -> Path:
    """Get the base path for the functions directory."""
    script_path = Path(__file__).resolve()
    return script_path.parent


def calculate_file_hash(filepath: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def verify_file_hash(filename: str, expected_hash: str, base_path: Path) -> dict:
    """Verify a single file against its frozen hash."""
    filepath = base_path / filename
    result = {
        "file": filename,
        "exists": False,
        "hash_match": False,
        "expected_hash": expected_hash,
        "actual_hash": None,
        "status": "UNKNOWN"
    }

    if not filepath.exists():
        result["status"] = "FILE_MISSING"
        logger.error(f"MISSING: {filename} - File not found!")
        return result

    result["exists"] = True
    actual_hash = calculate_file_hash(filepath)
    result["actual_hash"] = actual_hash

    if actual_hash == expected_hash:
        result["hash_match"] = True
        result["status"] = "VERIFIED"
        logger.info(f"VERIFIED: {filename} - Hash matches freeze registry")
    else:
        result["status"] = "MODIFIED"
        logger.error(f"VIOLATION: {filename} - File has been modified!")
        logger.error(f"  Expected: {expected_hash}")
        logger.error(f"  Actual:   {actual_hash}")

    return result


def verify_constitutional_parameter(param_name: str, config: dict, base_path: Path) -> dict:
    """Verify a constitutional parameter has not been changed."""
    result = {
        "parameter": param_name,
        "file": config["file"],
        "expected_pattern": config["pattern"],
        "found": False,
        "status": "UNKNOWN"
    }

    filepath = base_path / config["file"]
    if not filepath.exists():
        result["status"] = "FILE_MISSING"
        return result

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if config["pattern"] in content:
        result["found"] = True
        result["status"] = "VERIFIED"
        logger.info(f"VERIFIED: {param_name} = {config['value']} (constitutionally locked)")
    else:
        result["status"] = "TAMPERED"
        logger.error(f"VIOLATION: {param_name} - Constitutional parameter may have been modified!")
        logger.error(f"  Expected pattern: {config['pattern']}")

    return result


def generate_verification_report(results: dict) -> dict:
    """Generate a comprehensive verification report."""
    all_verified = all(r["status"] == "VERIFIED" for r in results["files"].values())
    params_verified = all(r["status"] == "VERIFIED" for r in results["parameters"].values())

    report = {
        "report_type": "CODE_FREEZE_VERIFICATION",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "directive_ref": "CD-G1-G2-WAVE12-20251217",
        "phase": "G2 Governance Review",
        "overall_status": "PASS" if (all_verified and params_verified) else "FAIL",
        "file_verification": results["files"],
        "parameter_verification": results["parameters"],
        "summary": {
            "files_checked": len(results["files"]),
            "files_verified": sum(1 for r in results["files"].values() if r["status"] == "VERIFIED"),
            "files_modified": sum(1 for r in results["files"].values() if r["status"] == "MODIFIED"),
            "files_missing": sum(1 for r in results["files"].values() if r["status"] == "FILE_MISSING"),
            "parameters_checked": len(results["parameters"]),
            "parameters_verified": sum(1 for r in results["parameters"].values() if r["status"] == "VERIFIED")
        }
    }

    if report["overall_status"] == "FAIL":
        report["governance_action"] = "G2 PROCESS MUST BE RESET - Code freeze violation detected"
        report["escalation"] = ["VEGA (Governance)", "CEO"]
    else:
        report["governance_action"] = "G2 review may proceed"

    return report


def main():
    """Main verification routine."""
    import argparse
    parser = argparse.ArgumentParser(description='G2 Code Freeze Verification')
    parser.add_argument('--strict', action='store_true',
                        help='Exit with error code on any violation')
    parser.add_argument('--json', action='store_true',
                        help='Output results as JSON')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("G2 CODE FREEZE VERIFICATION")
    logger.info("CEO Directive: CD-G1-G2-WAVE12-20251217")
    logger.info("=" * 60)

    base_path = get_base_path()
    logger.info(f"Base path: {base_path}")

    results = {
        "files": {},
        "parameters": {}
    }

    # Verify frozen files
    logger.info("-" * 40)
    logger.info("Verifying frozen files...")
    logger.info("-" * 40)

    for filename, config in FROZEN_FILES.items():
        result = verify_file_hash(filename, config["sha256"], base_path)
        result["component"] = config["component"]
        result["freeze_date"] = config["freeze_date"]
        results["files"][filename] = result

    # Verify constitutional parameters
    logger.info("-" * 40)
    logger.info("Verifying constitutional parameters...")
    logger.info("-" * 40)

    for param_name, config in CONSTITUTIONAL_LOCKS.items():
        result = verify_constitutional_parameter(param_name, config, base_path)
        results["parameters"][param_name] = result

    # Generate report
    report = generate_verification_report(results)

    logger.info("-" * 40)
    logger.info(f"OVERALL STATUS: {report['overall_status']}")
    logger.info(f"Files: {report['summary']['files_verified']}/{report['summary']['files_checked']} verified")
    logger.info(f"Parameters: {report['summary']['parameters_verified']}/{report['summary']['parameters_checked']} verified")
    logger.info("-" * 40)

    if args.json:
        print(json.dumps(report, indent=2))

    if report["overall_status"] == "FAIL":
        logger.error("CODE FREEZE VIOLATION DETECTED!")
        logger.error(report["governance_action"])
        if args.strict:
            sys.exit(1)
    else:
        logger.info("All frozen files and parameters verified successfully.")
        logger.info("G2 governance review may proceed.")

    return report


if __name__ == "__main__":
    main()
