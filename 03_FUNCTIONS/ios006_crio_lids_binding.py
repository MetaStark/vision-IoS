#!/usr/bin/env python3
"""
IoS-006 CRIO → LIDS TRUTH BINDING
=================================
Authority: CEO Directive - SOVEREIGN MACRO INTELLIGENCE LOOP
Reference: ADR-017 MIT Quad Protocol, ADR-014 Role Contracts
Owner: STIG (CTO)

PURPOSE:
    Activate LIDS certification for CRIO nightly insights using
    deterministic rules per CEO directive.

RULE:
    IF confidence >= 0.40 AND reasoning_summary IS NOT EMPTY
    THEN lids_verified = TRUE
    ELSE lids_verified = FALSE

Generated: 2025-12-08
"""

from __future__ import annotations

import os
import sys
import json
import hashlib
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
import logging

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True)


# =================================================================
# LOGGING
# =================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - LIDS.BINDING - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ios006_crio_lids_binding")


# =================================================================
# CONFIGURATION
# =================================================================

class LIDSBindingConfig:
    """LIDS Truth Binding Configuration per CEO Directive"""

    # Deterministic certification threshold
    # CEO-DIR-2026-019: Updated from 0.40 to 0.70 for ACI 1.0 Learning Activation
    MIN_CONFIDENCE = 0.70

    # Database
    PGHOST = os.getenv("PGHOST", "127.0.0.1")
    PGPORT = int(os.getenv("PGPORT", "54322"))
    PGDATABASE = os.getenv("PGDATABASE", "postgres")
    PGUSER = os.getenv("PGUSER", "postgres")
    PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

    @classmethod
    def get_connection_string(cls) -> str:
        return f"postgresql://{cls.PGUSER}:{cls.PGPASSWORD}@{cls.PGHOST}:{cls.PGPORT}/{cls.PGDATABASE}"


# =================================================================
# LIDS TRUTH BINDING ENGINE
# =================================================================

class CRIOLIDSBinding:
    """
    LIDS Truth Binding for CRIO Nightly Insights.

    Implements CEO Directive deterministic rule:
    - confidence >= 0.40 AND reasoning_summary IS NOT EMPTY → lids_verified = TRUE
    """

    def __init__(self):
        self.conn = None
        self.binding_id = str(uuid.uuid4())
        self.hash_chain_id = f"HC-LIDS-BINDING-{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    def connect(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(LIDSBindingConfig.get_connection_string())
        logger.info("Database connection established")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def _generate_canonical_hash(self, insight: Dict) -> str:
        """Generate canonical hash for LIDS-verified insight"""
        data = {
            'insight_id': str(insight.get('insight_id')),
            'research_date': str(insight.get('research_date')),
            'fragility_score': str(insight.get('fragility_score')),
            'dominant_driver': insight.get('dominant_driver'),
            'regime_assessment': insight.get('regime_assessment'),
            'confidence': str(insight.get('confidence'))
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def _generate_quad_hash(self, lids_valid: bool, acl_valid: bool = True,
                           risl_valid: bool = True, dsl_valid: bool = True) -> str:
        """Generate MIT Quad validation hash"""
        quad_state = f"LIDS:{lids_valid}|ACL:{acl_valid}|RISL:{risl_valid}|DSL:{dsl_valid}"
        return hashlib.sha256(quad_state.encode()).hexdigest()[:16]

    def _generate_lineage_reference(self, insight: Dict) -> Dict:
        """Generate lineage reference for sovereign audit trail"""
        return {
            'source': 'CRIO_DEEPSEEK_V1',
            'insight_id': str(insight.get('insight_id')),
            'research_date': str(insight.get('research_date')),
            'binding_id': self.binding_id,
            'hash_chain_id': self.hash_chain_id,
            'bound_at': datetime.now(timezone.utc).isoformat(),
            'authority': 'ADR-017'
        }

    def evaluate_lids_rule(self, insight: Dict) -> Tuple[bool, str]:
        """
        Apply CEO Directive deterministic rule:

        IF confidence >= 0.40 AND reasoning_summary IS NOT EMPTY
        THEN lids_verified = TRUE
        ELSE lids_verified = FALSE
        """
        confidence = float(insight.get('confidence', 0))
        reasoning = insight.get('reasoning_summary', '')

        # Deterministic rule
        if confidence >= LIDSBindingConfig.MIN_CONFIDENCE and reasoning and len(reasoning.strip()) > 0:
            return True, f"LIDS_CERTIFIED: confidence={confidence:.2f} >= {LIDSBindingConfig.MIN_CONFIDENCE}, reasoning present"
        elif confidence < LIDSBindingConfig.MIN_CONFIDENCE:
            return False, f"LIDS_REJECTED: confidence={confidence:.2f} < {LIDSBindingConfig.MIN_CONFIDENCE}"
        else:
            return False, "LIDS_REJECTED: reasoning_summary is empty"

    def bind_insight(self, insight_id: str) -> Dict[str, Any]:
        """
        Bind a single CRIO insight with LIDS certification.

        Returns binding result with canonical_hash, quad_hash, lineage.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Fetch insight
            cur.execute("""
                SELECT insight_id, research_date, fragility_score, dominant_driver,
                       regime_assessment, confidence, reasoning_summary,
                       lids_verified, risl_verified, context_hash, quad_hash
                FROM fhq_research.nightly_insights
                WHERE insight_id = %s
            """, (insight_id,))

            insight = cur.fetchone()
            if not insight:
                return {'success': False, 'error': f'Insight {insight_id} not found'}

            # Apply deterministic rule
            lids_valid, lids_reason = self.evaluate_lids_rule(insight)

            # Generate hashes and lineage
            canonical_hash = self._generate_canonical_hash(insight)
            quad_hash = self._generate_quad_hash(lids_valid, True, bool(insight.get('risl_verified')), True)
            lineage = self._generate_lineage_reference(insight)

            # Update insight with LIDS binding
            cur.execute("""
                UPDATE fhq_research.nightly_insights
                SET lids_verified = %s,
                    context_hash = COALESCE(context_hash, %s),
                    quad_hash = %s,
                    updated_at = NOW()
                WHERE insight_id = %s
            """, (lids_valid, canonical_hash, quad_hash, insight_id))

            # Log event
            event_type = 'ADR017_LIDS_CERTIFICATION' if lids_valid else 'ADR017_LIDS_REJECTION_EVENT'
            cur.execute("""
                INSERT INTO fhq_meta.ios_audit_log (
                    audit_id, ios_id, event_type, event_timestamp,
                    actor, gate_level, event_data, evidence_hash
                ) VALUES (
                    gen_random_uuid(), 'IoS-006.LIDS', %s, NOW(),
                    'LIDS', 'G2', %s, %s
                )
            """, (
                event_type,
                json.dumps({
                    'insight_id': str(insight_id),
                    'research_date': str(insight.get('research_date')),
                    'confidence': str(insight.get('confidence')),
                    'lids_valid': lids_valid,
                    'reason': lids_reason,
                    'canonical_hash': canonical_hash,
                    'quad_hash': quad_hash,
                    'lineage': lineage
                }),
                canonical_hash[:16]
            ))

            self.conn.commit()

            logger.info(f"LIDS Binding: {insight_id} → {event_type}")
            logger.info(f"  Rule: {lids_reason}")
            logger.info(f"  Quad Hash: {quad_hash}")

            return {
                'success': True,
                'insight_id': str(insight_id),
                'lids_verified': lids_valid,
                'reason': lids_reason,
                'canonical_hash': canonical_hash,
                'quad_hash': quad_hash,
                'lineage': lineage
            }

    def bind_pending_insights(self) -> Dict[str, Any]:
        """
        Bind all pending CRIO insights (where lids_verified is NULL or FALSE
        and confidence/reasoning should qualify).
        """
        logger.info("=" * 60)
        logger.info("LIDS TRUTH BINDING FOR CRIO INSIGHTS")
        logger.info(f"Binding ID: {self.binding_id}")
        logger.info(f"Hash Chain: {self.hash_chain_id}")
        logger.info("=" * 60)

        results = {
            'binding_id': self.binding_id,
            'certified': 0,
            'rejected': 0,
            'errors': 0,
            'insights': []
        }

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Find insights needing LIDS binding
            cur.execute("""
                SELECT insight_id, research_date, confidence, reasoning_summary,
                       lids_verified
                FROM fhq_research.nightly_insights
                WHERE lids_verified = FALSE OR lids_verified IS NULL
                ORDER BY research_date DESC
            """)

            pending = cur.fetchall()
            logger.info(f"Found {len(pending)} insights pending LIDS binding")

            for insight in pending:
                try:
                    result = self.bind_insight(str(insight['insight_id']))
                    results['insights'].append(result)

                    if result.get('lids_verified'):
                        results['certified'] += 1
                    else:
                        results['rejected'] += 1
                except Exception as e:
                    logger.error(f"Error binding {insight['insight_id']}: {e}")
                    results['errors'] += 1

        logger.info("=" * 60)
        logger.info(f"LIDS Binding Complete: {results['certified']} certified, {results['rejected']} rejected")
        logger.info("=" * 60)

        return results


# =================================================================
# SOVEREIGN LOOP INTEGRATION
# =================================================================

def lids_certify_crio_insight(insight_id: str) -> Dict[str, Any]:
    """
    Standalone function for sovereign loop integration.

    Called by IoS-003 before perception refresh.
    """
    binding = CRIOLIDSBinding()
    try:
        binding.connect()
        return binding.bind_insight(insight_id)
    finally:
        binding.close()


def lids_certify_all_pending() -> Dict[str, Any]:
    """
    Certify all pending CRIO insights.

    Called by orchestrator on each cycle.
    """
    binding = CRIOLIDSBinding()
    try:
        binding.connect()
        return binding.bind_pending_insights()
    finally:
        binding.close()


# =================================================================
# MAIN
# =================================================================

def main():
    """Run LIDS Truth Binding for all pending CRIO insights."""
    result = lids_certify_all_pending()
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get('errors', 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
