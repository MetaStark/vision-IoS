#!/usr/bin/env python3
"""
VEGA DDATP Validator - CEO-DIR-2026-015C
=========================================
Agent: VEGA (Verification & Governance Authority)
Directive: CEO-DIR-2026-015C

PURPOSE:
    Validate FINN DDATP output compliance by running consecutive
    FINN cycles and checking for zero violations.

VALIDATION RULES (Non-Negotiable):
    1. SENTIMENT claim requires sentiment_used=true
    2. OBSERVED_DATA basis requires at least one external feed used
    3. fallback_reason required when driver_basis != OBSERVED_DATA
    4. technical_feature_set required when driver_claim = TECHNICAL
    5. All enum values must be from allowed sets

SUCCESS CRITERIA:
    - 50 consecutive FINN outputs
    - Zero trigger violations
    - SENTIMENT claim rate = 0

ABORT CONDITIONS:
    - Any DDATP trigger violation
    - Any invalid enum
    - Any SENTIMENT claim without sentiment_used=true
    - Any missing fallback_reason when required

Generated: 2026-01-07
Authorized: CEO-DIR-2026-015C
"""

import os
import sys
import json
import hashlib
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv(override=True)

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / '06_AGENTS' / 'FINN'))
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - VEGA.DDATP - %(levelname)s - %(message)s'
)
logger = logging.getLogger("vega_ddatp_validator")

# =============================================================================
# DDATP VALIDATION RULES
# =============================================================================

ALLOWED_DRIVER_CLAIMS = frozenset([
    "LIQUIDITY", "CREDIT", "VOLATILITY", "TECHNICAL",
    "PRICE_ACTION", "SENTIMENT", "UNKNOWN"
])

ALLOWED_DRIVER_BASIS = frozenset([
    "OBSERVED_DATA", "INFERRED_FROM_PRICE", "FALLBACK_UNKNOWN"
])

ALLOWED_TECHNICAL_FEATURES = frozenset([
    "INDICATORS_ONLY", "RETURNS_VOL_ONLY", "MIXED_FEATURES",
    "ONCHAIN_HYBRID", "UNKNOWN"
])


class DDATPViolation(Exception):
    """Raised when a DDATP validation rule is violated."""
    pass


class VEGADDATPValidator:
    """
    VEGA DDATP Validation Engine for CEO-DIR-2026-015C.

    Runs FINN cycles and validates output against DDATP rules.
    Tracks consecutive successes and aborts on first violation.
    """

    def __init__(self, target_outputs: int = 50):
        self.target_outputs = target_outputs
        self.consecutive_successes = 0
        self.validation_log: List[Dict] = []
        self.aborted = False
        self.abort_reason: Optional[str] = None
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

        # Track metrics
        self.total_outputs = 0
        self.sentiment_claims = 0
        self.unknown_fallback_count = 0
        self.technical_inferred_count = 0

    def validate_ddatp_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a single FINN output against DDATP rules.

        Returns validation result dict.
        Raises DDATPViolation on any rule breach.
        """
        validation = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "output_hash": hashlib.sha256(json.dumps(output, sort_keys=True, default=str).encode()).hexdigest()[:16],
            "passed": False,
            "violations": []
        }

        # Extract DDATP fields
        driver_claim = output.get("driver_claim")
        driver_basis = output.get("driver_basis")
        technical_feature_set = output.get("technical_feature_set")
        input_coverage = output.get("input_coverage", {})
        fallback_reason = output.get("fallback_reason")

        # RULE 1: Validate enums
        if driver_claim and driver_claim not in ALLOWED_DRIVER_CLAIMS:
            validation["violations"].append(f"Invalid driver_claim: {driver_claim}")

        if driver_basis and driver_basis not in ALLOWED_DRIVER_BASIS:
            validation["violations"].append(f"Invalid driver_basis: {driver_basis}")

        if technical_feature_set and technical_feature_set not in ALLOWED_TECHNICAL_FEATURES:
            validation["violations"].append(f"Invalid technical_feature_set: {technical_feature_set}")

        # RULE 2: SENTIMENT claim requires sentiment_used=true
        if driver_claim == "SENTIMENT":
            sentiment_available = input_coverage.get("sentiment_available", False)
            sentiment_used = input_coverage.get("sentiment_used", False)
            if not (sentiment_available and sentiment_used):
                validation["violations"].append(
                    f"SENTIMENT claim without sentiment data: "
                    f"available={sentiment_available}, used={sentiment_used}"
                )

        # RULE 3: OBSERVED_DATA basis requires external feed used
        if driver_basis == "OBSERVED_DATA":
            macro_used = input_coverage.get("macro_used", False)
            sentiment_used = input_coverage.get("sentiment_used", False)
            onchain_used = input_coverage.get("onchain_used", False)
            if not (macro_used or sentiment_used or onchain_used):
                validation["violations"].append(
                    "OBSERVED_DATA basis without any external feed used"
                )

        # RULE 4: fallback_reason required when basis != OBSERVED_DATA
        if driver_basis and driver_basis != "OBSERVED_DATA":
            if not fallback_reason:
                validation["violations"].append(
                    f"Missing fallback_reason for driver_basis={driver_basis}"
                )

        # RULE 5: technical_feature_set required when driver_claim = TECHNICAL
        if driver_claim == "TECHNICAL":
            if not technical_feature_set or technical_feature_set == "UNKNOWN":
                validation["violations"].append(
                    "TECHNICAL claim without valid technical_feature_set"
                )

        # Determine pass/fail
        if validation["violations"]:
            validation["passed"] = False
            raise DDATPViolation("; ".join(validation["violations"]))
        else:
            validation["passed"] = True

        # Track metrics
        if driver_claim == "SENTIMENT":
            self.sentiment_claims += 1
        if driver_basis == "FALLBACK_UNKNOWN":
            self.unknown_fallback_count += 1
        if driver_claim == "TECHNICAL" and driver_basis == "INFERRED_FROM_PRICE":
            self.technical_inferred_count += 1

        return validation

    def run_single_cycle(self) -> Dict[str, Any]:
        """
        Run a single FINN CRIO cycle and validate output.

        Returns the FINN output with validation result.
        """
        from finn_deepseek_researcher import execute_finn_crio_research

        logger.info(f"Running FINN cycle {self.total_outputs + 1}/{self.target_outputs}")

        try:
            result = execute_finn_crio_research()
            self.total_outputs += 1

            # Extract DDATP fields from result
            ddatp_output = {
                "driver_claim": result.get("driver_claim"),
                "driver_basis": result.get("driver_basis"),
                "technical_feature_set": result.get("technical_feature_set"),
                "input_coverage": result.get("input_coverage", {}),
                "fallback_reason": result.get("fallback_reason")
            }

            # Validate
            validation = self.validate_ddatp_output(ddatp_output)

            # Success
            self.consecutive_successes += 1

            log_entry = {
                "cycle": self.total_outputs,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ddatp_output": ddatp_output,
                "validation": validation,
                "status": result.get("status"),
                "lids_status": result.get("lids_status")
            }
            self.validation_log.append(log_entry)

            logger.info(f"Cycle {self.total_outputs} PASSED - {self.consecutive_successes}/{self.target_outputs} consecutive")

            return log_entry

        except DDATPViolation as e:
            self.aborted = True
            self.abort_reason = str(e)
            logger.error(f"DDATP VIOLATION: {e}")
            raise

        except Exception as e:
            logger.error(f"FINN cycle failed: {e}")
            raise

    def run_validation_bundle(self, delay_between_cycles: float = 0.5) -> Dict[str, Any]:
        """
        Run the full validation bundle until 50 successes or abort.

        Args:
            delay_between_cycles: Seconds to wait between cycles

        Returns:
            Final validation bundle result
        """
        self.start_time = datetime.now(timezone.utc)

        logger.info(f"Starting VEGA DDATP Validation Bundle - Target: {self.target_outputs} consecutive outputs")

        try:
            while self.consecutive_successes < self.target_outputs:
                self.run_single_cycle()

                # Small delay to avoid hammering
                if self.consecutive_successes < self.target_outputs:
                    time.sleep(delay_between_cycles)

            # Success!
            self.end_time = datetime.now(timezone.utc)
            return self._generate_success_artifact()

        except DDATPViolation:
            self.end_time = datetime.now(timezone.utc)
            return self._generate_failure_artifact()

    def _generate_success_artifact(self) -> Dict[str, Any]:
        """Generate PASSED validation artifact."""
        artifact = {
            "directive_id": "CEO-DIR-2026-015C",
            "artifact_type": "VEGA_DDATP_VALIDATION_BUNDLE",
            "status": "PASSED",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": "VEGA",

            "validation_summary": {
                "target_outputs": self.target_outputs,
                "consecutive_successes": self.consecutive_successes,
                "total_outputs": self.total_outputs,
                "violations": 0,
                "sentiment_claim_rate": self.sentiment_claims / max(self.total_outputs, 1),
                "unknown_fallback_rate": self.unknown_fallback_count / max(self.total_outputs, 1),
                "technical_inferred_rate": self.technical_inferred_count / max(self.total_outputs, 1)
            },

            "execution_window": {
                "start": self.start_time.isoformat() if self.start_time else None,
                "end": self.end_time.isoformat() if self.end_time else None,
                "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else None
            },

            "production_enablement": {
                "gate_passed": True,
                "finn_ddatp_production_ready": True,
                "recommendation": "FINN DDATP schema may be promoted from SHADOW_ONLY to PRODUCTION"
            },

            "validation_log_summary": {
                "first_output": self.validation_log[0] if self.validation_log else None,
                "last_output": self.validation_log[-1] if self.validation_log else None,
                "total_logged": len(self.validation_log)
            },

            "lineage_hash": hashlib.sha256(
                json.dumps(self.validation_log, sort_keys=True, default=str).encode()
            ).hexdigest()
        }

        return artifact

    def _generate_failure_artifact(self) -> Dict[str, Any]:
        """Generate FAILED validation artifact."""
        artifact = {
            "directive_id": "CEO-DIR-2026-015C",
            "artifact_type": "VEGA_DDATP_VALIDATION_BUNDLE",
            "status": "FAILED",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": "VEGA",

            "abort_details": {
                "reason": self.abort_reason,
                "at_cycle": self.total_outputs,
                "consecutive_before_abort": self.consecutive_successes
            },

            "validation_summary": {
                "target_outputs": self.target_outputs,
                "consecutive_successes": self.consecutive_successes,
                "total_outputs": self.total_outputs,
                "aborted": True
            },

            "execution_window": {
                "start": self.start_time.isoformat() if self.start_time else None,
                "end": self.end_time.isoformat() if self.end_time else None
            },

            "production_enablement": {
                "gate_passed": False,
                "finn_ddatp_production_ready": False,
                "recommendation": "FINN DDATP requires remediation before production enablement"
            },

            "lineage_hash": hashlib.sha256(
                json.dumps(self.validation_log, sort_keys=True, default=str).encode()
            ).hexdigest()
        }

        return artifact

    def save_artifact(self, artifact: Dict[str, Any], output_dir: str = None):
        """Save the validation artifact to file."""
        if output_dir is None:
            output_dir = str(Path(__file__).parent / "evidence")

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"CEO_DIR_2026_015C_VEGA_DDATP_VALIDATION_{timestamp}.json"
        filepath = Path(output_dir) / filename

        with open(filepath, 'w') as f:
            json.dump(artifact, f, indent=2, default=str)

        logger.info(f"Artifact saved: {filepath}")
        return str(filepath)


def main():
    """Run VEGA DDATP Validation Bundle."""
    print("=" * 60)
    print("VEGA DDATP VALIDATION BUNDLE - CEO-DIR-2026-015C")
    print("=" * 60)
    print()
    print("Mode: PRODUCTION (promoted via CEO-DIR-2026-016)")
    print("Target: 50 consecutive FINN outputs with zero violations")
    print("Abort on: Any DDATP trigger violation")
    print()
    print("Starting validation...")
    print()

    validator = VEGADDATPValidator(target_outputs=50)

    try:
        artifact = validator.run_validation_bundle()

        # Save artifact
        filepath = validator.save_artifact(artifact)

        # Print result
        print()
        print("=" * 60)
        if artifact["status"] == "PASSED":
            print("VEGA DDATP Validation PASSED")
            print(f"50/50 consecutive outputs with zero violations")
        else:
            print("VEGA DDATP Validation FAILED")
            print(f"Abort reason: {artifact['abort_details']['reason']}")
        print("=" * 60)
        print()
        print(f"Artifact: {filepath}")

        return 0 if artifact["status"] == "PASSED" else 1

    except Exception as e:
        logger.error(f"Validation bundle failed: {e}")
        print(f"\nERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
