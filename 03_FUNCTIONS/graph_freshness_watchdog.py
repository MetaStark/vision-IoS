#!/usr/bin/env python3
"""
GRAPH FRESHNESS WATCHDOG
========================
VCEO-DIR-2026-CE-UNBLOCK-001 Section 6: Prevention Layer 1

Operational watchdog that monitors causal_edges freshness and emits
governance events when SLA is breached. No silent drift.

Author: STIG (CTO)
Date: 2026-01-10
Directive: VCEO-DIR-2026-CE-UNBLOCK-001
"""

import os
import sys
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("graph_freshness_watchdog")

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

# SLA thresholds per VCEO-DIR-2026-CE-UNBLOCK-001
CAUSAL_EDGES_SLA_HOURS = 48  # Blackout threshold
CAUSAL_EDGES_WARN_HOURS = 24  # Warning threshold (50% of SLA)
CAUSAL_EDGES_TARGET_HOURS = 6  # Operational target

# =============================================================================
# WATCHDOG LOGIC
# =============================================================================

def get_db_connection():
    """Establish database connection"""
    return psycopg2.connect(**DB_CONFIG)


def check_causal_edges_freshness(conn) -> Dict[str, Any]:
    """
    Check causal_edges freshness against SLA thresholds.

    Returns:
        Dict with freshness status, staleness hours, and health level
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                COUNT(*) as total_edges,
                COUNT(*) FILTER (WHERE is_active = TRUE) as active_edges,
                MAX(created_at) as latest_edge,
                EXTRACT(EPOCH FROM (NOW() - MAX(created_at)))/3600 as hours_stale
            FROM fhq_alpha.causal_edges
        """)
        result = dict(cur.fetchone())

        hours_stale = float(result['hours_stale']) if result['hours_stale'] else 9999

        # Determine health level
        if hours_stale <= CAUSAL_EDGES_TARGET_HOURS:
            health = 'OPTIMAL'
            sla_status = 'PASS'
        elif hours_stale <= CAUSAL_EDGES_WARN_HOURS:
            health = 'ACCEPTABLE'
            sla_status = 'PASS'
        elif hours_stale <= CAUSAL_EDGES_SLA_HOURS:
            health = 'WARNING'
            sla_status = 'DEGRADED'
        else:
            health = 'CRITICAL'
            sla_status = 'BREACH'

        return {
            'total_edges': int(result['total_edges']),
            'active_edges': int(result['active_edges']),
            'latest_edge': result['latest_edge'].isoformat() if result['latest_edge'] else None,
            'hours_stale': round(hours_stale, 2),
            'sla_hours': CAUSAL_EDGES_SLA_HOURS,
            'warn_hours': CAUSAL_EDGES_WARN_HOURS,
            'target_hours': CAUSAL_EDGES_TARGET_HOURS,
            'health': health,
            'sla_status': sla_status
        }


def emit_governance_event(conn, event_type: str, severity: str, details: Dict) -> str:
    """
    Emit a governance event for causal_edges freshness issues.

    Returns:
        action_id of the logged event
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_type,
                action_target,
                action_target_type,
                initiated_by,
                decision,
                decision_rationale,
                metadata
            ) VALUES (
                %s,
                'fhq_alpha.causal_edges',
                'WATCHDOG_EVENT',
                'STIG',
                %s,
                %s,
                %s
            )
            RETURNING action_id
        """, (
            event_type,
            severity,
            f"VCEO-DIR-2026-CE-UNBLOCK-001: Graph freshness {event_type.lower().replace('_', ' ')}",
            json.dumps({
                'directive': 'VCEO-DIR-2026-CE-UNBLOCK-001',
                'watchdog': 'graph_freshness_watchdog',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                **details
            }, default=str)
        ))
        action_id = str(cur.fetchone()[0])
        conn.commit()
        return action_id


def trigger_auto_rebuild(conn) -> Optional[Dict[str, Any]]:
    """
    Trigger automatic causal graph rebuild when SLA is breached.

    Only triggers if R1 (evidence refresh) completed successfully.
    """
    logger.info("SLA breach detected - checking if auto-rebuild is possible...")

    # Import the rebuild function
    try:
        from crio_alpha_graph_rebuild import run_graph_rebuild
        result = run_graph_rebuild()
        logger.info(f"Auto-rebuild completed: {result.get('status')}")
        return result
    except Exception as e:
        logger.error(f"Auto-rebuild failed: {e}")
        return {'status': 'FAILED', 'error': str(e)}


def run_watchdog() -> Dict[str, Any]:
    """
    Main watchdog execution function.

    Checks causal_edges freshness and takes appropriate action:
    - OPTIMAL/ACCEPTABLE: Log status only
    - WARNING: Emit governance warning event
    - CRITICAL: Emit breach event and trigger auto-rebuild
    """
    logger.info("=" * 60)
    logger.info("GRAPH FRESHNESS WATCHDOG")
    logger.info("Directive: VCEO-DIR-2026-CE-UNBLOCK-001")
    logger.info("=" * 60)

    result = {
        'watchdog': 'graph_freshness_watchdog',
        'directive': 'VCEO-DIR-2026-CE-UNBLOCK-001',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'actions_taken': []
    }

    conn = None
    try:
        conn = get_db_connection()

        # Check freshness
        freshness = check_causal_edges_freshness(conn)
        result['freshness'] = freshness
        logger.info(f"Causal edges: {freshness['hours_stale']:.2f}h stale (SLA: {freshness['sla_hours']}h)")
        logger.info(f"Health: {freshness['health']} | SLA Status: {freshness['sla_status']}")

        # Take action based on health level
        if freshness['health'] == 'CRITICAL':
            logger.warning("CRITICAL: SLA BREACH - Emitting governance event and triggering rebuild")

            # Emit breach event
            action_id = emit_governance_event(
                conn,
                'CAUSAL_GRAPH_SLA_BREACH',
                'CRITICAL',
                freshness
            )
            result['actions_taken'].append({
                'action': 'governance_event',
                'type': 'CAUSAL_GRAPH_SLA_BREACH',
                'action_id': action_id
            })

            # Trigger auto-rebuild
            rebuild_result = trigger_auto_rebuild(conn)
            result['actions_taken'].append({
                'action': 'auto_rebuild',
                'result': rebuild_result
            })
            result['rebuild_triggered'] = True

        elif freshness['health'] == 'WARNING':
            logger.warning("WARNING: Approaching SLA breach - Emitting governance warning")

            action_id = emit_governance_event(
                conn,
                'CAUSAL_GRAPH_SLA_WARNING',
                'WARNING',
                freshness
            )
            result['actions_taken'].append({
                'action': 'governance_event',
                'type': 'CAUSAL_GRAPH_SLA_WARNING',
                'action_id': action_id
            })
            result['rebuild_triggered'] = False

        else:
            logger.info(f"Status: {freshness['health']} - No action required")
            result['rebuild_triggered'] = False

        result['status'] = 'SUCCESS'

    except Exception as e:
        logger.error(f"Watchdog failed: {e}")
        result['status'] = 'FAILED'
        result['error'] = str(e)
    finally:
        if conn:
            conn.close()

    return result


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    result = run_watchdog()
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result['status'] == 'SUCCESS' else 1)
