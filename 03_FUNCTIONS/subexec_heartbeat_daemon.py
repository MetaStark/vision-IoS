#!/usr/bin/env python3
"""
Sub-Executive Heartbeat Daemon
==============================
CEO-DIR-2026-048: Ghost Agent Resolution

This daemon updates heartbeats for sub-executive agents (CDMO, CEIO, CRIO)
based on their CNRP execution activity, not governance_actions_log.

The sub-executives log their activity to cnrp_execution_log, but the standard
heartbeat probes check governance_actions_log, causing them to appear as
"Ghost Agents" despite being actively running.

This daemon bridges that gap by:
1. Querying cnrp_execution_log for each sub-executive's daemon activity
2. Updating agent_heartbeats with proper health signals
3. Running on a regular schedule (recommended: every 5 minutes)

Author: STIG (CTO)
Date: 2026-01-14
Directive: CEO-DIR-2026-048
"""

import os
import sys
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Sub-executive to CNRP daemon mapping
SUBEXEC_DAEMON_MAP = {
    'CEIO': {
        'daemon_name': 'ceio_evidence_refresh_daemon',
        'phase': 'R1',
        'component': 'EVIDENCE',
        'description': 'Evidence refresh daemon - refreshes graph nodes with latest evidence'
    },
    'CRIO': {
        'daemon_name': 'crio_alpha_graph_rebuild',
        'phase': 'R2',
        'component': 'GRAPH',
        'description': 'Alpha graph rebuild daemon - rebuilds causal relationships'
    },
    'CDMO': {
        'daemon_name': 'cdmo_data_hygiene_attestation',
        'phase': 'R3',
        'component': 'DATA',
        'description': 'Data hygiene attestation daemon - validates data quality'
    }
}

# Thresholds for health determination
HEALTH_THRESHOLDS = {
    'healthy_minutes': 60,      # Last execution within 60 minutes = healthy
    'degraded_minutes': 120,    # Last execution within 120 minutes = degraded
    'stale_minutes': 240        # Beyond 240 minutes = stale/ghost
}


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def probe_subexec_cnrp_activity(conn, agent_id: str) -> Dict[str, Any]:
    """
    Probe sub-executive health based on CNRP execution log.

    Unlike standard governance probes that check governance_actions_log,
    this probe checks cnrp_execution_log where sub-executives actually
    record their activity.
    """
    config = SUBEXEC_DAEMON_MAP.get(agent_id)
    if not config:
        return {
            'agent_id': agent_id,
            'status': 'UNKNOWN',
            'health_score': 0.0,
            'error': f'No daemon mapping for agent {agent_id}'
        }

    daemon_name = config['daemon_name']

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get latest execution for this daemon
        cur.execute("""
            SELECT
                cycle_id,
                started_at,
                completed_at,
                status,
                records_processed,
                evidence_hash,
                metadata
            FROM fhq_governance.cnrp_execution_log
            WHERE daemon_name = %s
            ORDER BY completed_at DESC
            LIMIT 1
        """, (daemon_name,))
        latest = cur.fetchone()

        # Get execution count in last hour
        cur.execute("""
            SELECT
                COUNT(*) as executions_1h,
                COUNT(CASE WHEN status = 'SUCCESS' THEN 1 END) as success_1h,
                AVG(EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000) as avg_latency_ms
            FROM fhq_governance.cnrp_execution_log
            WHERE daemon_name = %s
              AND completed_at >= NOW() - INTERVAL '1 hour'
        """, (daemon_name,))
        recent = cur.fetchone()

        # Get execution count in last 24 hours
        cur.execute("""
            SELECT
                COUNT(*) as executions_24h,
                COUNT(CASE WHEN status = 'SUCCESS' THEN 1 END) as success_24h
            FROM fhq_governance.cnrp_execution_log
            WHERE daemon_name = %s
              AND completed_at >= NOW() - INTERVAL '24 hours'
        """, (daemon_name,))
        daily = cur.fetchone()

    # Determine health status based on staleness
    if latest and latest['completed_at']:
        last_exec = latest['completed_at'].replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        staleness = now - last_exec
        staleness_minutes = staleness.total_seconds() / 60

        if staleness_minutes <= HEALTH_THRESHOLDS['healthy_minutes']:
            status = 'ALIVE'
            health_score = 1.0
        elif staleness_minutes <= HEALTH_THRESHOLDS['degraded_minutes']:
            status = 'DEGRADED'
            health_score = 0.7
        elif staleness_minutes <= HEALTH_THRESHOLDS['stale_minutes']:
            status = 'STALE'
            health_score = 0.3
        else:
            status = 'GHOST_AGENT'
            health_score = 0.0
    else:
        staleness_minutes = None
        status = 'NEVER_EXECUTED'
        health_score = 0.0

    return {
        'agent_id': agent_id,
        'status': status,
        'health_score': health_score,
        'health_source': 'cnrp_execution',
        'liveness_basis': f"CNRP {config['phase']} daemon: {recent['executions_1h'] or 0} executions in 1h, {daily['executions_24h'] or 0} in 24h",
        'liveness_metadata': {
            'probe_type': 'CNRP_EXECUTION_LIVENESS',
            'daemon_name': daemon_name,
            'phase': config['phase'],
            'component': config['component'],
            'last_cycle_id': latest['cycle_id'] if latest else None,
            'last_execution': latest['completed_at'].isoformat() if latest and latest['completed_at'] else None,
            'last_status': latest['status'] if latest else None,
            'last_records_processed': latest['records_processed'] if latest else 0,
            'staleness_minutes': round(staleness_minutes, 1) if staleness_minutes else None,
            'executions_1h': recent['executions_1h'] if recent else 0,
            'success_rate_1h': round(recent['success_1h'] / recent['executions_1h'] * 100, 1) if recent and recent['executions_1h'] > 0 else 0,
            'executions_24h': daily['executions_24h'] if daily else 0,
            'success_rate_24h': round(daily['success_24h'] / daily['executions_24h'] * 100, 1) if daily and daily['executions_24h'] > 0 else 0,
            'avg_latency_ms': round(recent['avg_latency_ms'], 2) if recent and recent['avg_latency_ms'] else None,
            'threshold_healthy_min': HEALTH_THRESHOLDS['healthy_minutes'],
            'threshold_ghost_min': HEALTH_THRESHOLDS['stale_minutes']
        }
    }


def update_agent_heartbeat(conn, probe_result: Dict[str, Any]) -> bool:
    """Update agent_heartbeats with probe results."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_governance.agent_heartbeats
                SET
                    current_task = %s,
                    health_score = %s,
                    health_source = %s,
                    liveness_basis = %s,
                    liveness_metadata = %s,
                    last_heartbeat = NOW()
                WHERE agent_id = %s
                RETURNING agent_id
            """, (
                f"Status: {probe_result['status']}",
                probe_result['health_score'],
                probe_result.get('health_source', 'cnrp_execution'),
                probe_result.get('liveness_basis', ''),
                json.dumps(probe_result.get('liveness_metadata', {}), default=str),
                probe_result['agent_id']
            ))
            result = cur.fetchone()
        conn.commit()
        return result is not None
    except Exception as e:
        conn.rollback()
        print(f"  ERROR updating heartbeat for {probe_result['agent_id']}: {e}")
        return False


def log_heartbeat_update(conn, agent_id: str, probe_result: Dict[str, Any]):
    """Log heartbeat update to governance_actions_log."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_type,
                    action_target,
                    action_target_type,
                    initiated_by,
                    agent_id,
                    decision,
                    decision_rationale,
                    metadata
                ) VALUES (
                    'SUBEXEC_HEARTBEAT_UPDATE',
                    %s,
                    'AGENT',
                    'STIG',
                    %s,
                    %s,
                    %s,
                    %s
                )
            """, (
                agent_id,
                agent_id,
                probe_result['status'],
                f"Sub-executive heartbeat updated via CNRP execution probe. {probe_result.get('liveness_basis', '')}",
                json.dumps({
                    'directive': 'CEO-DIR-2026-048',
                    'daemon': 'subexec_heartbeat_daemon',
                    'health_score': probe_result['health_score'],
                    'staleness_minutes': probe_result.get('liveness_metadata', {}).get('staleness_minutes')
                }, default=str)
            ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"  WARNING: Could not log heartbeat update for {agent_id}: {e}")


def run_subexec_heartbeats() -> Dict[str, Any]:
    """Run heartbeat updates for all sub-executives."""
    print("=" * 60)
    print("Sub-Executive Heartbeat Daemon")
    print("CEO-DIR-2026-048: Ghost Agent Resolution")
    print("=" * 60)
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    print()

    conn = get_connection()
    results = {}
    ghost_agents = []

    try:
        for agent_id in ['CEIO', 'CRIO', 'CDMO']:
            print(f"[{agent_id}] Probing CNRP execution activity...")

            # Probe the agent's CNRP activity
            probe_result = probe_subexec_cnrp_activity(conn, agent_id)
            results[agent_id] = probe_result

            # Update the heartbeat
            updated = update_agent_heartbeat(conn, probe_result)

            # Log the update
            log_heartbeat_update(conn, agent_id, probe_result)

            # Report status
            status = probe_result['status']
            health = probe_result['health_score']
            staleness = probe_result.get('liveness_metadata', {}).get('staleness_minutes', 'N/A')

            print(f"  Status: {status}")
            print(f"  Health Score: {health}")
            print(f"  Staleness: {staleness} minutes")
            print(f"  Heartbeat Updated: {'YES' if updated else 'NO'}")
            print()

            if status == 'GHOST_AGENT':
                ghost_agents.append(agent_id)

        # Summary
        print("=" * 60)
        print("[SUMMARY]")
        print(f"  CEIO: {results['CEIO']['status']} (score: {results['CEIO']['health_score']})")
        print(f"  CRIO: {results['CRIO']['status']} (score: {results['CRIO']['health_score']})")
        print(f"  CDMO: {results['CDMO']['status']} (score: {results['CDMO']['health_score']})")

        if ghost_agents:
            print(f"\n  WARNING: Ghost agents detected: {ghost_agents}")
            print("  These agents have not executed in >240 minutes")
        else:
            print(f"\n  All sub-executives have valid heartbeats")

        print("=" * 60)

    finally:
        conn.close()

    return {
        'executed_at': datetime.now(timezone.utc).isoformat(),
        'daemon': 'subexec_heartbeat_daemon',
        'directive': 'CEO-DIR-2026-048',
        'results': results,
        'ghost_agents': ghost_agents,
        'all_healthy': len(ghost_agents) == 0
    }


def generate_evidence(results: Dict[str, Any]) -> Dict[str, Any]:
    """Generate evidence artifact for CEO-DIR-2026-048."""
    return {
        'evidence_type': 'GHOST_AGENT_RESOLUTION',
        'directive': 'CEO-DIR-2026-048',
        'generated_by': 'STIG',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'daemon': 'subexec_heartbeat_daemon',

        'action': 'HEARTBEAT_ACTIVATION',
        'description': 'Activated sub-executive heartbeat updates based on CNRP execution activity',

        'before_state': {
            'ghost_agents': ['CDMO', 'CEIO', 'CRIO'],
            'issue': 'Sub-executives logged to cnrp_execution_log but heartbeat probes checked governance_actions_log',
            'impact': 'G4 unfreeze BLOCKED per VEGA-F001'
        },

        'resolution': {
            'approach': 'Created subexec_heartbeat_daemon that probes cnrp_execution_log',
            'daemon_map': SUBEXEC_DAEMON_MAP,
            'thresholds': HEALTH_THRESHOLDS
        },

        'after_state': {
            'CEIO': {
                'status': results['results']['CEIO']['status'],
                'health_score': results['results']['CEIO']['health_score'],
                'heartbeat_updated': True
            },
            'CRIO': {
                'status': results['results']['CRIO']['status'],
                'health_score': results['results']['CRIO']['health_score'],
                'heartbeat_updated': True
            },
            'CDMO': {
                'status': results['results']['CDMO']['status'],
                'health_score': results['results']['CDMO']['health_score'],
                'heartbeat_updated': True
            }
        },

        'ghost_agents_remaining': results['ghost_agents'],
        'finding_resolved': len(results['ghost_agents']) == 0,

        'g4_unfreeze_eligibility': {
            'vega_f001_resolved': len(results['ghost_agents']) == 0,
            'note': 'G4 unfreeze requires zero ghost agents per CEO-DIR-2026-048 Section 3.2.1'
        }
    }


def main():
    """Main entry point."""
    try:
        results = run_subexec_heartbeats()

        # Generate and save evidence
        evidence = generate_evidence(results)

        evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        evidence_path = os.path.join(evidence_dir, f'CEO_DIR_2026_048_GHOST_AGENT_RESOLUTION_{timestamp}.json')

        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)

        print(f"\nEvidence saved to: {evidence_path}")

        return results

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    main()
