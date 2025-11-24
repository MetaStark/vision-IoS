"""
G4 CEO SIGNATURE SCRIPT
Phase 3: G4 Canonicalization — CEO Authorization

Authority: CEO Final Authorization for Production Deployment
Reference: LARS Directive 10, 10B — G4 Canonicalization
Canonical ADR Chain: ADR-001 → ADR-015

PURPOSE:
This script verifies all G4 requirements are met and applies the CEO signature
to the G4 Canonicalization Packet, marking the system as production-ready.

REQUIREMENTS:
1. G4 Weight Lock must exist (in DB and JSON)
2. G4 Evidence Bundle must be generated
3. All tests must pass (72/72)
4. All ADR compliance checks must pass

CEO_AUTHORIZATION_CODE environment variable required.
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - CEO SIGN - %(levelname)s - %(message)s'
)
logger = logging.getLogger("g4_ceo_signature")


class G4CEOSignature:
    """
    G4 CEO Signature Manager — Final Production Authorization

    Verifies all G4 requirements and applies CEO signature.
    """

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize signature manager."""
        if base_path is None:
            base_path = Path(__file__).parent

        self.base_path = base_path
        self.governance_path = base_path.parent.parent / '05_GOVERNANCE' / 'PHASE3'
        self.signature_timestamp = datetime.now(timezone.utc)

    def find_weight_lock(self) -> Optional[Dict]:
        """Find the canonical G4 weight lock."""
        lock_files = list(self.governance_path.glob('G4_WEIGHT_LOCK_*.json'))

        if not lock_files:
            return None

        # Get most recent lock file
        latest_lock = sorted(lock_files, reverse=True)[0]

        with open(latest_lock, 'r', encoding='utf-8') as f:
            return json.load(f)

    def find_evidence_bundle(self) -> Optional[Dict]:
        """Find the G4 evidence bundle."""
        bundle_files = list(self.governance_path.glob('G4_EVIDENCE_BUNDLE_*.json'))

        if not bundle_files:
            return None

        # Get most recent bundle
        latest_bundle = sorted(bundle_files, reverse=True)[0]

        with open(latest_bundle, 'r', encoding='utf-8') as f:
            return json.load(f)

    def verify_prerequisites(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify all G4 prerequisites are met.

        Returns:
            Tuple of (all_passed, verification_details)
        """
        results = {
            "weight_lock": {"status": "FAIL", "details": None},
            "evidence_bundle": {"status": "FAIL", "details": None},
            "tests": {"status": "FAIL", "details": None},
            "compliance": {"status": "FAIL", "details": None}
        }

        # Check 1: Weight Lock
        weight_lock = self.find_weight_lock()
        if weight_lock:
            results["weight_lock"] = {
                "status": "PASS",
                "details": {
                    "lock_id": weight_lock.get("lock_id"),
                    "weight_hash": weight_lock.get("weight_hash", "")[:32] + "..."
                }
            }

        # Check 2: Evidence Bundle
        evidence_bundle = self.find_evidence_bundle()
        if evidence_bundle:
            results["evidence_bundle"] = {
                "status": "PASS",
                "details": {
                    "bundle_id": evidence_bundle.get("bundle_id"),
                    "overall_status": evidence_bundle.get("overall_status")
                }
            }

            # Check 3: Tests from bundle
            test_results = evidence_bundle.get("test_results", {})
            if test_results.get("pass_rate", 0) == 100.0:
                results["tests"] = {
                    "status": "PASS",
                    "details": {
                        "passed": test_results.get("passed", 0),
                        "failed": test_results.get("failed", 0),
                        "pass_rate": test_results.get("pass_rate", 0)
                    }
                }

            # Check 4: Compliance from bundle
            compliance = evidence_bundle.get("compliance_checks", [])
            all_pass = all(c.get("status") == "PASS" for c in compliance)
            if all_pass and len(compliance) > 0:
                results["compliance"] = {
                    "status": "PASS",
                    "details": {
                        "checks_passed": len(compliance),
                        "adrs": [c.get("adr_id") for c in compliance]
                    }
                }

        all_passed = all(r["status"] == "PASS" for r in results.values())
        return all_passed, results

    def compute_signature_hash(self, ceo_name: str, ceo_code: str) -> str:
        """Compute CEO signature hash."""
        data = {
            "ceo_name": ceo_name,
            "timestamp": self.signature_timestamp.isoformat(),
            "authorization_code_hash": hashlib.sha256(ceo_code.encode()).hexdigest()
        }
        canonical = json.dumps(data, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def update_canonicalization_packet(self, ceo_name: str, signature_hash: str) -> bool:
        """Update the G4 Canonicalization Packet with CEO signature."""
        packet_path = self.governance_path / 'G4_CANONICALIZATION_PACKET.md'

        if not packet_path.exists():
            logger.error("G4_CANONICALIZATION_PACKET.md not found")
            return False

        try:
            content = packet_path.read_text(encoding='utf-8')

            # Update status
            content = content.replace(
                "**Status:** ✅ READY FOR CEO SIGNATURE",
                "**Status:** ✅ CEO SIGNED — PRODUCTION AUTHORIZED"
            )

            # Update the banner
            content = content.replace(
                "G4 CANONICALIZATION COMPLETE — AWAITING CEO SIGNATURE",
                "G4 CANONICALIZATION COMPLETE — CEO SIGNED"
            )

            packet_path.write_text(content, encoding='utf-8')
            logger.info("✅ G4_CANONICALIZATION_PACKET.md updated with CEO signature")
            return True

        except Exception as e:
            logger.error(f"Failed to update packet: {e}")
            return False

    def create_signature_record(self, ceo_name: str, signature_hash: str) -> Dict:
        """Create a signature record for audit trail."""
        weight_lock = self.find_weight_lock()
        evidence_bundle = self.find_evidence_bundle()

        record = {
            "signature_id": f"G4-CEO-SIG-{self.signature_timestamp.strftime('%Y%m%d_%H%M%S')}",
            "signature_timestamp": self.signature_timestamp.isoformat(),
            "ceo_name": ceo_name,
            "signature_hash": signature_hash,
            "weight_lock_id": weight_lock.get("lock_id") if weight_lock else None,
            "weight_hash": weight_lock.get("weight_hash") if weight_lock else None,
            "evidence_bundle_id": evidence_bundle.get("bundle_id") if evidence_bundle else None,
            "authorization": {
                "production_deployment": True,
                "weight_immutability": True,
                "live_market_operations": True
            },
            "compliance": {
                "adr_chain": "ADR-001 → ADR-015",
                "regulatory": ["EU AI Act", "BIS-239", "MiFID II", "GIPS", "DORA", "ISO-8000"]
            }
        }

        return record

    def save_signature_record(self, record: Dict) -> str:
        """Save signature record to governance folder."""
        filename = f"G4_CEO_SIGNATURE_{record['signature_id']}.json"
        filepath = self.governance_path / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(record, f, indent=2, default=str)

        logger.info(f"✅ Signature record saved: {filepath}")
        return str(filepath)

    def execute_signature(self, ceo_name: str, ceo_code: str) -> Tuple[bool, Dict]:
        """
        Execute CEO signature process.

        Args:
            ceo_name: CEO's name
            ceo_code: CEO authorization code

        Returns:
            Tuple of (success, signature_record)
        """
        logger.info("=" * 70)
        logger.info("G4 CEO SIGNATURE — EXECUTING")
        logger.info("=" * 70)

        # Verify prerequisites
        logger.info("\n[1] Verifying G4 prerequisites...")
        all_passed, verification = self.verify_prerequisites()

        for check, result in verification.items():
            status = "✅" if result["status"] == "PASS" else "❌"
            logger.info(f"    {status} {check}: {result['status']}")

        if not all_passed:
            logger.error("\n❌ Prerequisites not met — cannot sign")
            return False, verification

        logger.info("\n✅ All prerequisites verified")

        # Compute signature
        logger.info("\n[2] Computing CEO signature hash...")
        signature_hash = self.compute_signature_hash(ceo_name, ceo_code)
        logger.info(f"    Signature: {signature_hash[:32]}...")

        # Create signature record
        logger.info("\n[3] Creating signature record...")
        record = self.create_signature_record(ceo_name, signature_hash)

        # Save signature record
        logger.info("\n[4] Saving signature record...")
        self.save_signature_record(record)

        # Update canonicalization packet
        logger.info("\n[5] Updating G4 Canonicalization Packet...")
        self.update_canonicalization_packet(ceo_name, signature_hash)

        logger.info("\n" + "=" * 70)
        logger.info("✅ G4 CEO SIGNATURE COMPLETE")
        logger.info("=" * 70)

        return True, record


def display_signature_summary(record: Dict):
    """Display signature summary."""
    print("\n" + "=" * 70)
    print("G4 CEO SIGNATURE — PRODUCTION AUTHORIZATION")
    print("=" * 70)

    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                    G4 CEO SIGNATURE — AUTHORIZED                             ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Signature ID: {record['signature_id']:<54} ║
║  Timestamp:    {record['signature_timestamp']:<54} ║
║  CEO:          {record['ceo_name']:<54} ║
║                                                                              ║
║  Signature Hash: {record['signature_hash'][:48]}... ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  AUTHORIZED:                                                                 ║
║  ✅ Permanent deployment of CDS Engine v1.0 to production                    ║
║  ✅ Immutable locking of CDS Weights v1.0                                    ║
║  ✅ Activation of Phase 3 system for live market operations                  ║
║                                                                              ║
║  Weight Lock: {record['weight_lock_id']:<55} ║
║  Evidence:    {record['evidence_bundle_id']:<55} ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    print("=" * 70)
    print("✅ CDS Engine v1.0 is now PRODUCTION AUTHORIZED")
    print("=" * 70)


def main():
    """Execute G4 CEO Signature."""
    print("=" * 70)
    print("G4 CEO SIGNATURE SCRIPT")
    print("Phase 3: G4 Canonicalization — CEO Final Authorization")
    print("=" * 70)

    # Check for authorization code
    ceo_code = os.environ.get("CEO_AUTHORIZATION_CODE")

    if not ceo_code:
        print("\n❌ CEO_AUTHORIZATION_CODE environment variable not set.")
        print("\nTo sign, set the authorization code:")
        print("  $env:CEO_AUTHORIZATION_CODE = '<your-code>'  # PowerShell")
        print("  export CEO_AUTHORIZATION_CODE=<your-code>    # Bash")
        print("  python g4_ceo_signature.py")
        return 1

    # Get CEO name
    ceo_name = os.environ.get("CEO_NAME", "")

    if not ceo_name:
        print("\nEnter CEO name for signature record:")
        ceo_name = input("CEO Name: ").strip()

        if not ceo_name:
            print("\n❌ CEO name required for signature")
            return 1

    print(f"\n👤 CEO: {ceo_name}")
    print(f"🔑 Authorization code: {ceo_code[:8]}...")

    # Confirm
    print("\n⚠️  This will PERMANENTLY authorize the CDS Engine v1.0 for production.")
    confirm = input("\nProceed with CEO signature? (yes/no): ").strip().lower()

    if confirm != "yes":
        print("\n❌ Signature cancelled by user")
        return 1

    # Execute signature
    signer = G4CEOSignature()
    success, record = signer.execute_signature(ceo_name, ceo_code)

    if success:
        display_signature_summary(record)
        return 0
    else:
        print("\n❌ Signature failed — prerequisites not met")
        return 2


if __name__ == "__main__":
    sys.exit(main())
