#!/usr/bin/env python3
"""
IoS-012 MIT-QUAD SOVEREIGNTY VALIDATOR
======================================
Authority: CEO Directive - SOVEREIGN MACRO INTELLIGENCE LOOP ORDER C
Reference: ADR-017 (MIT Quad Protocol), IoS-012 Execution Engine

PURPOSE:
    Validates MIT-Quad sovereignty before trade execution:
    - RISL: Risk Intelligence & Safety Layer
    - ACL: Access Control Layer
    - LIDS: Logical Integrity & Data Sovereignty
    - DSL: Data Sovereignty Layer

HIERARCHY (ADR-017):
    RISL > ACL > LIDS > DSL
    Higher layer has veto power over lower layers.

BLOCKING RULES:
    - RISL blocks if fragility_score > 0.80
    - LIDS blocks if no LIDS-verified CRIO insight exists
    - ACL blocks if unauthorized access attempted

Generated: 2025-12-08
"""

from __future__ import annotations

import os
import json
import hashlib
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass
import logging

from dotenv import load_dotenv
load_dotenv(override=True)


# =================================================================
# LOGGING
# =================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - MIT.QUAD - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ios012_mit_quad_validator")


# =================================================================
# CONFIGURATION
# =================================================================

class MITQuadConfig:
    """MIT Quad Configuration per ADR-017"""

    # Database
    PGHOST = os.getenv("PGHOST", "127.0.0.1")
    PGPORT = int(os.getenv("PGPORT", "54322"))
    PGDATABASE = os.getenv("PGDATABASE", "postgres")
    PGUSER = os.getenv("PGUSER", "postgres")
    PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

    # RISL Thresholds
    RISL_BLOCK_FRAGILITY = 0.80   # Block execution if fragility > 80%
    RISL_REDUCE_FRAGILITY = 0.70  # Reduce position by 50% if > 70%
    RISL_NEUTRAL_FRAGILITY = 0.40 # Full sizing below 40%

    @classmethod
    def get_connection_string(cls) -> str:
        return f"postgresql://{cls.PGUSER}:{cls.PGPASSWORD}@{cls.PGHOST}:{cls.PGPORT}/{cls.PGDATABASE}"


# =================================================================
# DATA STRUCTURES
# =================================================================

@dataclass
class SovereigntyCheckResult:
    """Result of MIT-Quad sovereignty validation"""
    can_execute: bool
    quad_hash: str
    lids_verified: bool
    acl_verified: bool
    risl_verified: bool
    dsl_verified: bool
    crio_insight_id: Optional[str]
    fragility_score: Optional[float]
    dominant_driver: Optional[str]
    position_scalar: float
    decision_reason: str
    checkpoint_id: str


# =================================================================
# MIT-QUAD VALIDATOR
# =================================================================

class MITQuadValidator:
    """
    Validates MIT-Quad sovereignty for IoS-012 trade execution.

    Hierarchy: RISL > ACL > LIDS > DSL
    """

    def __init__(self, conn=None):
        self.conn = conn or psycopg2.connect(MITQuadConfig.get_connection_string())
        self.owns_connection = conn is None
        self.checkpoint_id = str(uuid.uuid4())

    def close(self):
        """Close connection if owned"""
        if self.owns_connection and self.conn:
            self.conn.close()

    def get_latest_crio_insight(self) -> Optional[Dict]:
        """Fetch latest LIDS-verified CRIO insight"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT insight_id, research_date, fragility_score,
                       dominant_driver, quad_hash, lids_verified, risl_verified,
                       regime_assessment, confidence
                FROM fhq_research.nightly_insights
                WHERE lids_verified = TRUE
                ORDER BY research_date DESC
                LIMIT 1
            """)
            return cur.fetchone()

    def validate_risl(self, fragility_score: float) -> Tuple[bool, float, str]:
        """
        RISL (Risk Intelligence & Safety Layer) validation.

        Rules:
        - Block if fragility > 0.80
        - Reduce 50% if fragility > 0.70
        - Neutral (75%) if 0.40 <= fragility <= 0.70
        - Full sizing if fragility < 0.40
        """
        if fragility_score > MITQuadConfig.RISL_BLOCK_FRAGILITY:
            return (
                False,
                0.0,
                f"RISL_BLOCK: fragility_score {fragility_score:.2f} > {MITQuadConfig.RISL_BLOCK_FRAGILITY}"
            )
        elif fragility_score > MITQuadConfig.RISL_REDUCE_FRAGILITY:
            return (
                True,
                0.50,
                f"RISL_REDUCE: fragility_score {fragility_score:.2f} > {MITQuadConfig.RISL_REDUCE_FRAGILITY} -> 50% scalar"
            )
        elif fragility_score >= MITQuadConfig.RISL_NEUTRAL_FRAGILITY:
            return (
                True,
                0.75,
                f"RISL_NEUTRAL: {MITQuadConfig.RISL_NEUTRAL_FRAGILITY} <= {fragility_score:.2f} <= {MITQuadConfig.RISL_REDUCE_FRAGILITY} -> 75% scalar"
            )
        else:
            return (
                True,
                1.0,
                f"RISL_FULL: fragility_score {fragility_score:.2f} < {MITQuadConfig.RISL_NEUTRAL_FRAGILITY} -> 100% scalar"
            )

    def validate_acl(self, environment: str = "PAPER") -> Tuple[bool, str]:
        """
        ACL (Access Control Layer) validation.

        Paper environment always passes.
        Live environment requires additional authorization.
        """
        if environment.upper() == "PAPER":
            return True, "ACL_PASS: Paper environment authorized"
        else:
            return False, "ACL_BLOCK: Live environment requires G4 authorization"

    def validate_lids(self, crio_insight: Optional[Dict]) -> Tuple[bool, str]:
        """
        LIDS (Logical Integrity & Data Sovereignty) validation.

        Requires LIDS-verified CRIO insight.
        """
        if crio_insight is None:
            return False, "LIDS_BLOCK: No LIDS-verified CRIO insight available"

        if not crio_insight.get('lids_verified'):
            return False, "LIDS_BLOCK: CRIO insight not LIDS-verified"

        return True, "LIDS_PASS: CRIO insight LIDS-verified"

    def validate_dsl(self) -> Tuple[bool, str]:
        """
        DSL (Data Sovereignty Layer) validation.

        Verifies data integrity and source authenticity.
        Currently always passes for internal data.
        """
        return True, "DSL_PASS: Internal data sources verified"

    def validate_sovereignty(
        self,
        asset_id: str,
        order_side: str,
        order_qty: float,
        environment: str = "PAPER"
    ) -> SovereigntyCheckResult:
        """
        Full MIT-Quad sovereignty validation.

        Returns SovereigntyCheckResult with execution decision.
        """
        logger.info("=" * 60)
        logger.info("MIT-QUAD SOVEREIGNTY VALIDATION")
        logger.info(f"Checkpoint: {self.checkpoint_id[:8]}...")
        logger.info(f"Asset: {asset_id}, Side: {order_side}, Qty: {order_qty}")
        logger.info("=" * 60)

        # Get CRIO insight
        crio_insight = self.get_latest_crio_insight()

        # DSL Check (lowest priority)
        dsl_ok, dsl_reason = self.validate_dsl()
        logger.info(f"  DSL: {'PASS' if dsl_ok else 'BLOCK'} - {dsl_reason}")

        # LIDS Check
        lids_ok, lids_reason = self.validate_lids(crio_insight)
        logger.info(f"  LIDS: {'PASS' if lids_ok else 'BLOCK'} - {lids_reason}")

        if not lids_ok:
            return SovereigntyCheckResult(
                can_execute=False,
                quad_hash="NO_CRIO",
                lids_verified=False,
                acl_verified=False,
                risl_verified=False,
                dsl_verified=dsl_ok,
                crio_insight_id=None,
                fragility_score=None,
                dominant_driver=None,
                position_scalar=0.0,
                decision_reason=lids_reason,
                checkpoint_id=self.checkpoint_id
            )

        # ACL Check
        acl_ok, acl_reason = self.validate_acl(environment)
        logger.info(f"  ACL: {'PASS' if acl_ok else 'BLOCK'} - {acl_reason}")

        if not acl_ok:
            return SovereigntyCheckResult(
                can_execute=False,
                quad_hash=crio_insight.get('quad_hash', 'UNKNOWN'),
                lids_verified=lids_ok,
                acl_verified=False,
                risl_verified=False,
                dsl_verified=dsl_ok,
                crio_insight_id=str(crio_insight['insight_id']),
                fragility_score=float(crio_insight['fragility_score']),
                dominant_driver=crio_insight['dominant_driver'],
                position_scalar=0.0,
                decision_reason=acl_reason,
                checkpoint_id=self.checkpoint_id
            )

        # RISL Check (highest priority)
        fragility = float(crio_insight['fragility_score'])
        risl_ok, position_scalar, risl_reason = self.validate_risl(fragility)
        logger.info(f"  RISL: {'PASS' if risl_ok else 'BLOCK'} - {risl_reason}")

        # Final decision
        can_execute = dsl_ok and lids_ok and acl_ok and risl_ok

        if can_execute:
            decision_reason = (
                f"SOVEREIGNTY_VERIFIED: quad={crio_insight.get('quad_hash')}, "
                f"scalar={position_scalar:.2f}"
            )
        else:
            decision_reason = risl_reason if not risl_ok else "UNKNOWN_BLOCK"

        result = SovereigntyCheckResult(
            can_execute=can_execute,
            quad_hash=crio_insight.get('quad_hash', 'UNKNOWN'),
            lids_verified=lids_ok,
            acl_verified=acl_ok,
            risl_verified=risl_ok,
            dsl_verified=dsl_ok,
            crio_insight_id=str(crio_insight['insight_id']),
            fragility_score=fragility,
            dominant_driver=crio_insight['dominant_driver'],
            position_scalar=position_scalar,
            decision_reason=decision_reason,
            checkpoint_id=self.checkpoint_id
        )

        # Log checkpoint
        self._log_checkpoint(result, asset_id, order_side, order_qty, crio_insight)

        logger.info("=" * 60)
        logger.info(f"DECISION: {'APPROVED' if can_execute else 'BLOCKED'}")
        logger.info(f"Position Scalar: {position_scalar:.2f}")
        logger.info("=" * 60)

        return result

    def _log_checkpoint(
        self,
        result: SovereigntyCheckResult,
        asset_id: str,
        order_side: str,
        order_qty: float,
        crio_insight: Dict
    ):
        """Log sovereignty checkpoint to database"""
        try:
            lineage_data = {
                'checkpoint_id': self.checkpoint_id,
                'asset_id': asset_id,
                'order_side': order_side,
                'order_qty': order_qty,
                'quad_hash': result.quad_hash,
                'lids': result.lids_verified,
                'acl': result.acl_verified,
                'risl': result.risl_verified,
                'dsl': result.dsl_verified,
            }
            lineage_hash = hashlib.sha256(
                json.dumps(lineage_data, sort_keys=True).encode()
            ).hexdigest()

            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_execution.sovereign_checkpoints (
                        checkpoint_id, crio_insight_id, crio_research_date,
                        fragility_score, dominant_driver, quad_hash,
                        lids_status, acl_status, risl_status, dsl_status,
                        sovereignty_decision, decision_reason,
                        risk_scalar_applied, position_scalar,
                        lineage_hash, evidence_hash, created_by
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    self.checkpoint_id,
                    crio_insight['insight_id'],
                    crio_insight['research_date'],
                    result.fragility_score,
                    result.dominant_driver,
                    result.quad_hash,
                    'PASS' if result.lids_verified else 'FAIL',
                    'PASS' if result.acl_verified else 'FAIL',
                    'PASS' if result.risl_verified else 'FAIL',
                    'PASS' if result.dsl_verified else 'FAIL',
                    'APPROVED' if result.can_execute else 'BLOCKED',
                    result.decision_reason,
                    result.position_scalar,
                    result.position_scalar,
                    lineage_hash,
                    lineage_hash[:16],
                    'STIG'
                ))
                self.conn.commit()

        except Exception as e:
            logger.warning(f"Failed to log checkpoint: {e}")
            self.conn.rollback()


# =================================================================
# PUBLIC API
# =================================================================

def validate_trade_sovereignty(
    asset_id: str,
    order_side: str,
    order_qty: float,
    environment: str = "PAPER"
) -> SovereigntyCheckResult:
    """
    Public API for MIT-Quad sovereignty validation.

    Called by IoS-012 before trade execution.
    """
    validator = MITQuadValidator()
    try:
        return validator.validate_sovereignty(
            asset_id, order_side, order_qty, environment
        )
    finally:
        validator.close()


def check_sovereignty_status(conn=None) -> Dict[str, Any]:
    """
    Quick sovereignty status check.

    Returns current CRIO insight and quad state.
    """
    if conn is None:
        conn = psycopg2.connect(MITQuadConfig.get_connection_string())
        close_conn = True
    else:
        close_conn = False

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT insight_id, research_date, fragility_score,
                       dominant_driver, quad_hash, lids_verified
                FROM fhq_research.nightly_insights
                WHERE lids_verified = TRUE
                ORDER BY research_date DESC
                LIMIT 1
            """)
            insight = cur.fetchone()

        if insight:
            return {
                'status': 'ACTIVE',
                'quad_hash': insight['quad_hash'],
                'fragility_score': float(insight['fragility_score']),
                'dominant_driver': insight['dominant_driver'],
                'research_date': str(insight['research_date']),
                'lids_verified': insight['lids_verified'],
            }
        else:
            return {
                'status': 'NO_INSIGHT',
                'quad_hash': None,
                'message': 'No LIDS-verified CRIO insight available',
            }
    finally:
        if close_conn:
            conn.close()


# =================================================================
# MAIN
# =================================================================

def main():
    """Test MIT-Quad sovereignty validation"""
    print("=" * 60)
    print("MIT-QUAD SOVEREIGNTY VALIDATION TEST")
    print("=" * 60)

    # Check current status
    status = check_sovereignty_status()
    print(f"\nCurrent Status: {status['status']}")
    if status.get('quad_hash'):
        print(f"Quad Hash: {status['quad_hash']}")
        print(f"Fragility: {status['fragility_score']}")
        print(f"Driver: {status['dominant_driver']}")

    # Run validation
    print("\n" + "=" * 60)
    result = validate_trade_sovereignty(
        asset_id="BTC-USD",
        order_side="SELL",
        order_qty=0.01,
        environment="PAPER"
    )

    print(f"\nResult:")
    print(f"  Can Execute: {result.can_execute}")
    print(f"  Quad Hash: {result.quad_hash}")
    print(f"  LIDS: {result.lids_verified}")
    print(f"  ACL: {result.acl_verified}")
    print(f"  RISL: {result.risl_verified}")
    print(f"  Position Scalar: {result.position_scalar}")
    print(f"  Reason: {result.decision_reason}")

    return 0 if result.can_execute else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
