#!/usr/bin/env python3
"""
LIDS RE-VALIDATION PROTOCOL
============================
CEO Directive: CEO-DIR-2026-019 (P0-2.4)
Classification: CRITICAL - Learning Activation

Purpose:
    After CNRP completes, check if system can exit cognitive fasting.
    Uses can_exit_cognitive_fasting() from migration 212.

Exit Conditions (ALL must be TRUE):
    - data_freshness_hours <= 12
    - belief_confidence >= 0.70
    - evidence_attachment_ok == TRUE
    - cnrp_completed_successfully == TRUE

Author: STIG (CTO)
Date: 2026-01-07
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("lids_revalidation")

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": os.getenv("PGPORT", "54322"),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres")
}

# CEO-DIR-2026-019 Presisering 4: Mekanisk presis exit conditions
LIDS_MIN_CONFIDENCE = 0.70
LIDS_MAX_FRESHNESS_HOURS = 12


class LIDSRevalidationProtocol:
    """
    CEO-DIR-2026-019 P0-2.4: Re-validation protocol for cognitive fasting exit.

    When LIDS gates block execution, system enters cognitive fasting.
    This protocol checks if conditions are met to exit fasting state.
    """

    def __init__(self):
        self.conn = None

    def connect(self):
        """Establish database connection"""
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(**DB_CONFIG)
        return self.conn

    def close(self):
        """Close database connection"""
        if self.conn and not self.conn.closed:
            self.conn.close()

    def get_current_fasting_state(self) -> Dict:
        """Get current cognitive fasting state from execution_state"""
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    cognitive_fasting,
                    fasting_reason,
                    fasting_started_at,
                    fasting_max_duration_hours,
                    revalidation_required,
                    last_cnrp_completion,
                    fasting_requires_ceo_override
                FROM fhq_governance.execution_state
                WHERE state_key = 'PRIMARY'
                LIMIT 1
            """)
            result = cur.fetchone()

        if not result:
            return {
                'cognitive_fasting': False,
                'fasting_reason': None,
                'fasting_started_at': None,
                'revalidation_required': False
            }
        return dict(result)

    def get_current_belief_metrics(self) -> Dict:
        """Get latest belief confidence and data freshness"""
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get latest belief confidence from model_belief_state
            cur.execute("""
                SELECT
                    dominant_confidence,
                    belief_timestamp,
                    EXTRACT(EPOCH FROM (NOW() - belief_timestamp)) / 3600 as age_hours
                FROM fhq_perception.model_belief_state
                ORDER BY belief_timestamp DESC
                LIMIT 1
            """)
            belief = cur.fetchone()

            # Get data freshness from data sources
            cur.execute("""
                SELECT
                    MAX(last_update) as latest_data,
                    EXTRACT(EPOCH FROM (NOW() - MAX(last_update))) / 3600 as staleness_hours
                FROM (
                    SELECT MAX(timestamp) as last_update FROM fhq_market.prices
                    WHERE timestamp > NOW() - INTERVAL '24 hours'
                ) sq
            """)
            freshness = cur.fetchone()

        return {
            'belief_confidence': float(belief['dominant_confidence']) if belief and belief['dominant_confidence'] else 0.0,
            'belief_age_hours': float(belief['age_hours']) if belief and belief['age_hours'] else 999,
            'data_freshness_hours': float(freshness['staleness_hours']) if freshness and freshness['staleness_hours'] else 999
        }

    def check_cnrp_completion(self) -> Tuple[bool, Optional[datetime]]:
        """Check if CNRP chain completed successfully"""
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    completed_at,
                    status
                FROM fhq_governance.governance_actions_log
                WHERE action_type = 'CNRP_CHAIN_COMPLETION'
                  AND decision = 'COMPLETED'
                  AND initiated_at > NOW() - INTERVAL '24 hours'
                ORDER BY initiated_at DESC
                LIMIT 1
            """)
            result = cur.fetchone()

        if result and result['status'] == 'COMPLETED':
            return True, result['completed_at']
        return False, None

    def check_evidence_attachment(self) -> bool:
        """Check if evidence attachment is operational"""
        conn = self.connect()
        with conn.cursor() as cur:
            # Check if recent evidence has been attached
            cur.execute("""
                SELECT COUNT(*) as recent_evidence
                FROM vision_verification.summary_evidence_ledger
                WHERE created_at > NOW() - INTERVAL '6 hours'
            """)
            result = cur.fetchone()
        return result[0] > 0 if result else False

    def can_exit_fasting(self) -> Tuple[bool, str, Dict]:
        """
        CEO-DIR-2026-019 Presisering 4: Check all exit conditions.

        Returns:
            (can_exit, reason, conditions)
        """
        # Get current metrics
        metrics = self.get_current_belief_metrics()
        cnrp_ok, cnrp_time = self.check_cnrp_completion()
        evidence_ok = self.check_evidence_attachment()

        # Use SQL function for official determination
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM fhq_governance.can_exit_cognitive_fasting(
                    %s, %s, %s, %s
                )
            """, (
                metrics['data_freshness_hours'],
                metrics['belief_confidence'],
                evidence_ok,
                cnrp_ok
            ))
            result = cur.fetchone()

        conditions = {
            'data_freshness_hours': metrics['data_freshness_hours'],
            'belief_confidence': metrics['belief_confidence'],
            'evidence_attachment_ok': evidence_ok,
            'cnrp_completed': cnrp_ok,
            'cnrp_completion_time': cnrp_time.isoformat() if cnrp_time else None
        }

        return result['can_exit'], result['exit_reason'], conditions

    def attempt_exit_fasting(self) -> Dict:
        """
        Attempt to exit cognitive fasting if conditions are met.

        Returns evidence bundle for audit.
        """
        logger.info("[LIDS-REVALIDATION] Checking cognitive fasting exit conditions...")

        # Get current state
        fasting_state = self.get_current_fasting_state()

        if not fasting_state.get('cognitive_fasting', False):
            logger.info("[LIDS-REVALIDATION] Not in cognitive fasting - no action needed")
            return {
                'action': 'NO_ACTION',
                'reason': 'System not in cognitive fasting',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

        # Check if CEO override required
        if fasting_state.get('fasting_requires_ceo_override', False):
            logger.warning("[LIDS-REVALIDATION] Fasting requires CEO override - cannot auto-exit")
            return {
                'action': 'BLOCKED',
                'reason': 'Fasting exceeded max duration - CEO override required',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

        # Check exit conditions
        can_exit, reason, conditions = self.can_exit_fasting()

        if can_exit:
            # Exit cognitive fasting
            conn = self.connect()
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE fhq_governance.execution_state
                    SET cognitive_fasting = FALSE,
                        fasting_reason = NULL,
                        revalidation_required = FALSE,
                        last_cnrp_completion = NOW()
                    WHERE state_key = 'PRIMARY'
                """)

                # Log the exit
                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_type, action_target, action_target_type,
                        initiated_by, decision, decision_rationale, metadata
                    ) VALUES (
                        'COGNITIVE_FASTING_EXIT', 'execution_state', 'STATE',
                        'LIDS_REVALIDATION', 'APPROVED', %s, %s
                    )
                """, (
                    reason,
                    json.dumps(conditions)
                ))

            conn.commit()
            logger.info(f"[LIDS-REVALIDATION] Exited cognitive fasting: {reason}")

            return {
                'action': 'EXITED_FASTING',
                'reason': reason,
                'conditions': conditions,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        else:
            # Log the failed attempt
            conn = self.connect()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_type, action_target, action_target_type,
                        initiated_by, decision, decision_rationale, metadata
                    ) VALUES (
                        'COGNITIVE_FASTING_EXIT_ATTEMPT', 'execution_state', 'STATE',
                        'LIDS_REVALIDATION', 'BLOCKED', %s, %s
                    )
                """, (
                    reason,
                    json.dumps(conditions)
                ))
            conn.commit()

            logger.warning(f"[LIDS-REVALIDATION] Cannot exit fasting: {reason}")
            logger.info(f"[LIDS-REVALIDATION] Conditions: {conditions}")

            return {
                'action': 'STILL_FASTING',
                'reason': reason,
                'conditions': conditions,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

    def enter_fasting(self, reason: str) -> Dict:
        """
        Enter cognitive fasting state when LIDS gates fail.

        This is called by signal_executor_daemon when gates block execution.
        """
        logger.warning(f"[LIDS-REVALIDATION] Entering cognitive fasting: {reason}")

        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_governance.execution_state
                SET cognitive_fasting = TRUE,
                    fasting_reason = %s,
                    fasting_started_at = NOW(),
                    revalidation_required = TRUE
                WHERE state_key = 'PRIMARY'
            """, (reason,))

            # Log entry
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_type, action_target, action_target_type,
                    initiated_by, decision, decision_rationale
                ) VALUES (
                    'COGNITIVE_FASTING_ENTER', 'execution_state', 'STATE',
                    'LIDS_GATE', 'ENFORCED', %s
                )
            """, (reason,))

        conn.commit()

        return {
            'action': 'ENTERED_FASTING',
            'reason': reason,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


def main():
    """Run re-validation check"""
    protocol = LIDSRevalidationProtocol()
    try:
        result = protocol.attempt_exit_fasting()
        print(json.dumps(result, indent=2))
        return 0 if result['action'] in ('NO_ACTION', 'EXITED_FASTING') else 1
    finally:
        protocol.close()


if __name__ == "__main__":
    exit(main())
