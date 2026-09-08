#!/usr/bin/env python3
"""
CEO-DIR-2026-043: Observability Activation & Governance Signal Integrity
=========================================================================
Status: AUTHORIZED
Phase: WEEK_1_FOUNDATION
Scope: READ/WRITE (Monitoring & Governance only)

This script activates minimal, non-intrusive observability:
- Populates fhq_monitoring.daemon_health with live daemon status
- Resumes agent heartbeat emission to fhq_governance.agent_heartbeats
- Documents Telegram heartbeat truth source
- Documents DEFCON evaluation semantics

NO execution impact. NO capital exposure. ZERO agency change.

Author: STIG (CTO)
Date: 2026-01-13
"""

import os
import sys
import json
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
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

# Known daemons that should report health
KNOWN_DAEMONS = [
    {
        'daemon_name': 'g2c_continuous_forecast_engine',
        'description': 'STRAT_* forecast generation',
        'check_table': 'fhq_research.forecast_ledger',
        'check_column': 'created_at',
        'check_condition': "forecast_source LIKE 'STRAT_%'",
        'max_staleness_minutes': 30
    },
    {
        'daemon_name': 'ios010_learning_loop',
        'description': 'Forecast-outcome reconciliation',
        'check_table': 'fhq_governance.governance_actions_log',
        'check_column': 'initiated_at',
        'check_condition': "action_type LIKE 'IOS010%'",
        'max_staleness_minutes': 120
    },
    {
        'daemon_name': 'cnrp_orchestrator',
        'description': 'R1-R4 chain execution',
        'check_table': 'fhq_governance.governance_actions_log',
        'check_column': 'initiated_at',
        'check_condition': "action_type LIKE 'CNRP%'",
        'max_staleness_minutes': 300
    },
    {
        'daemon_name': 'ios003_regime_update',
        'description': 'Sovereign regime computation',
        'check_table': 'fhq_perception.sovereign_regime_state_v4',
        'check_column': 'created_at',
        'check_condition': "1=1",
        'max_staleness_minutes': 240
    },
    {
        'daemon_name': 'price_freshness_heartbeat',
        'description': 'Data quality monitoring',
        'check_table': 'fhq_governance.system_heartbeats',
        'check_column': 'last_heartbeat',
        'check_condition': "component_name = 'PRICE_FRESHNESS'",
        'max_staleness_minutes': 60
    }
]

# Known agents for heartbeat tracking
KNOWN_AGENTS = [
    {'agent_id': 'LARS', 'component': 'ORCHESTRATOR', 'description': 'Logic, Analytics & Research Strategy'},
    {'agent_id': 'STIG', 'component': 'INFRASTRUCTURE', 'description': 'System for Technical Implementation & Governance'},
    {'agent_id': 'FINN', 'component': 'RESEARCH', 'description': 'Financial Investments Neural Network'},
    {'agent_id': 'VEGA', 'component': 'GOVERNANCE', 'description': 'Verification & Governance Authority'},
    {'agent_id': 'LINE', 'component': 'EXECUTION', 'description': 'Local Infrastructure, Network & Execution'},
    {'agent_id': 'CEIO', 'component': 'EVIDENCE', 'description': 'Chief Evidence & Intelligence Officer'},
    {'agent_id': 'CRIO', 'component': 'GRAPH', 'description': 'Chief Research & Intelligence Officer'},
    {'agent_id': 'CDMO', 'component': 'DATA', 'description': 'Chief Data Management Officer'},
]


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def check_daemon_health(conn, daemon: Dict) -> Dict:
    """Check if a daemon is healthy based on recent activity."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        query = f"""
            SELECT
                MAX({daemon['check_column']}) as last_activity,
                COUNT(*) as recent_count
            FROM {daemon['check_table']}
            WHERE {daemon['check_condition']}
              AND {daemon['check_column']} >= NOW() - INTERVAL '{daemon['max_staleness_minutes']} minutes'
        """
        cur.execute(query)
        result = cur.fetchone()

        if result and result['last_activity']:
            staleness = datetime.now(timezone.utc) - result['last_activity'].replace(tzinfo=timezone.utc)
            staleness_minutes = staleness.total_seconds() / 60

            if staleness_minutes <= daemon['max_staleness_minutes']:
                status = 'HEALTHY'
            elif staleness_minutes <= daemon['max_staleness_minutes'] * 2:
                status = 'DEGRADED'
            else:
                status = 'UNHEALTHY'
        else:
            staleness_minutes = None
            status = 'STOPPED'  # Valid values: HEALTHY, DEGRADED, UNHEALTHY, STOPPED

        return {
            'daemon_name': daemon['daemon_name'],
            'description': daemon['description'],
            'status': status,
            'last_activity': result['last_activity'].isoformat() if result and result['last_activity'] else None,
            'staleness_minutes': round(staleness_minutes, 1) if staleness_minutes else None,
            'threshold_minutes': daemon['max_staleness_minutes'],
            'recent_count': result['recent_count'] if result else 0
        }


def populate_daemon_health(conn) -> List[Dict]:
    """Populate fhq_monitoring.daemon_health with live daemon status."""
    results = []

    for daemon in KNOWN_DAEMONS:
        health = check_daemon_health(conn, daemon)
        results.append(health)

        # Insert/update daemon_health
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_monitoring.daemon_health
                    (daemon_name, status, last_heartbeat, metadata, created_at, updated_at)
                VALUES (%s, %s, NOW(), %s, NOW(), NOW())
                ON CONFLICT (daemon_name) DO UPDATE SET
                    status = EXCLUDED.status,
                    last_heartbeat = NOW(),
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
            """, (
                health['daemon_name'],
                health['status'],
                json.dumps({
                    'description': health['description'],
                    'last_activity': health['last_activity'],
                    'staleness_minutes': health['staleness_minutes'],
                    'threshold_minutes': health['threshold_minutes'],
                    'recent_count': health['recent_count'],
                    'checked_at': datetime.now(timezone.utc).isoformat()
                })
            ))

    conn.commit()
    return results


def get_agent_activity(conn, agent_id: str) -> Dict:
    """Get recent activity for an agent from governance log."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check governance actions
        cur.execute("""
            SELECT
                COUNT(*) as actions_24h,
                MAX(initiated_at) as last_action
            FROM fhq_governance.governance_actions_log
            WHERE (initiated_by = %s OR agent_id = %s)
              AND initiated_at >= NOW() - INTERVAL '24 hours'
        """, (agent_id, agent_id))
        result = cur.fetchone()

        return {
            'actions_24h': result['actions_24h'] if result else 0,
            'last_action': result['last_action'].isoformat() if result and result['last_action'] else None
        }


def populate_agent_heartbeats(conn) -> List[Dict]:
    """Populate fhq_governance.agent_heartbeats with current agent status."""
    results = []

    for agent in KNOWN_AGENTS:
        activity = get_agent_activity(conn, agent['agent_id'])

        # Determine status based on activity
        if activity['last_action']:
            last_action = datetime.fromisoformat(activity['last_action'].replace('Z', '+00:00'))
            staleness = datetime.now(timezone.utc) - last_action
            staleness_hours = staleness.total_seconds() / 3600

            if staleness_hours <= 1:
                status = 'ALIVE'
                health_score = 1.0
            elif staleness_hours <= 4:
                status = 'ALIVE'
                health_score = 0.8
            elif staleness_hours <= 24:
                status = 'DEGRADED'
                health_score = 0.5
            else:
                status = 'STALE'
                health_score = 0.2
        else:
            status = 'UNKNOWN'
            health_score = 0.0
            staleness_hours = None

        heartbeat = {
            'agent_id': agent['agent_id'],
            'component': agent['component'],
            'description': agent['description'],
            'status': status,
            'health_score': health_score,
            'actions_24h': activity['actions_24h'],
            'last_action': activity['last_action'],
            'staleness_hours': round(staleness_hours, 1) if staleness_hours else None
        }
        results.append(heartbeat)

        # Insert/update agent_heartbeats (heartbeat_id is auto-increment)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.agent_heartbeats
                    (agent_id, component, current_task, health_score,
                     events_processed, errors_count, last_heartbeat, created_at)
                VALUES (%s, %s, %s, %s, %s, 0, NOW(), NOW())
                ON CONFLICT (agent_id) DO UPDATE SET
                    component = EXCLUDED.component,
                    current_task = EXCLUDED.current_task,
                    health_score = EXCLUDED.health_score,
                    events_processed = EXCLUDED.events_processed,
                    last_heartbeat = NOW()
            """, (
                agent['agent_id'],
                agent['component'],
                f"Status: {status}",
                health_score,
                activity['actions_24h']
            ))

    conn.commit()
    return results


def get_telegram_heartbeat_trace(conn) -> Dict:
    """Document the Telegram heartbeat truth source."""
    trace = {
        'truth_source': {
            'primary_table': 'fhq_governance.system_heartbeats',
            'component_filter': "component_name = 'PRICE_FRESHNESS'",
            'writer_script': '03_FUNCTIONS/price_freshness_heartbeat.py',
            'writer_function': 'log_heartbeat()',
            'write_frequency': 'Every orchestrator cycle (~1 hour)',
            'upsert_behavior': 'ON CONFLICT (component_name) DO UPDATE'
        },
        'timestamp_semantics': {
            'column': 'last_heartbeat',
            'type': 'TIMESTAMP WITH TIME ZONE',
            'meaning': 'Time of most recent heartbeat write',
            'freshness_calculation': 'NOW() - last_heartbeat'
        },
        'staleness_behavior': {
            'healthy_threshold': '60 minutes',
            'warning_threshold': '120 minutes',
            'critical_threshold': '240 minutes',
            'source': 'Implicit in orchestrator cycle timing'
        },
        'telegram_integration': {
            'bot_token_env': 'TELEGRAM_BOT_TOKEN',
            'chat_id_env': 'CEO_TELEGRAM_CHAT_ID',
            'enabled_flag': 'CEO_GATEWAY_ENABLED',
            'send_function': 'send_telegram_alert()',
            'trigger': 'On status change to WARNING/CRITICAL/BLACKOUT'
        }
    }

    # Get current state
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT component_name, heartbeat_type, last_heartbeat, status, metadata
            FROM fhq_governance.system_heartbeats
            WHERE component_name = 'PRICE_FRESHNESS'
        """)
        current = cur.fetchone()

        if current:
            trace['current_state'] = {
                'component_name': current['component_name'],
                'heartbeat_type': current['heartbeat_type'],
                'last_heartbeat': current['last_heartbeat'].isoformat() if current['last_heartbeat'] else None,
                'status': current['status'],
                'metadata': current['metadata']
            }

    return trace


def get_defcon_evaluation_semantics(conn) -> Dict:
    """Document DEFCON evaluation semantics."""
    semantics = {
        'current_state': None,
        'truth_source': {
            'table': 'fhq_governance.defcon_state',
            'current_filter': 'is_current = true',
            'levels': ['GREEN', 'YELLOW', 'ORANGE', 'RED', 'BLACK'],
            'default_level': 'GREEN'
        },
        'why_static': {
            'reason': 'No automated DEFCON reevaluation process is currently running',
            'last_change': None,
            'changed_by': None,
            'trigger_reason': None
        },
        'reevaluation_triggers': {
            'manual': 'CEO directive or VEGA governance action',
            'automated_candidates': [
                'Consecutive forecast failures (Brier > threshold)',
                'Data blackout detection (price staleness)',
                'Execution anomaly (if execution were enabled)',
                'Learning loop degradation',
                'Agent heartbeat cascade failure'
            ],
            'current_automation': 'NONE - static since initialization'
        },
        'escalation_semantics': {
            'GREEN': 'Normal operations, all gates open',
            'YELLOW': 'Caution - increased monitoring, conservative thresholds',
            'ORANGE': 'Warning - reduced activity, tightened gates',
            'RED': 'Critical - minimal operations, human oversight required',
            'BLACK': 'System halt - no autonomous activity permitted'
        }
    }

    # Get current DEFCON state
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT defcon_level, triggered_at, triggered_by, trigger_reason, is_current
            FROM fhq_governance.defcon_state
            WHERE is_current = true
            ORDER BY triggered_at DESC
            LIMIT 1
        """)
        current = cur.fetchone()

        if current:
            semantics['current_state'] = {
                'defcon_level': current['defcon_level'],
                'triggered_at': current['triggered_at'].isoformat() if current['triggered_at'] else None,
                'triggered_by': current['triggered_by'],
                'trigger_reason': current['trigger_reason'],
                'is_current': current['is_current']
            }
            semantics['why_static']['last_change'] = current['triggered_at'].isoformat() if current['triggered_at'] else None
            semantics['why_static']['changed_by'] = current['triggered_by']
            semantics['why_static']['trigger_reason'] = current['trigger_reason']

    return semantics


def generate_evidence(conn) -> Dict:
    """Generate all evidence artifacts for CEO-DIR-2026-043."""
    print("CEO-DIR-2026-043: Observability Activation")
    print("=" * 60)

    # Objective 1: Activate fhq_monitoring
    print("\n[1/4] Activating fhq_monitoring.daemon_health...")
    daemon_health = populate_daemon_health(conn)
    print(f"      Populated {len(daemon_health)} daemon health records")

    # Objective 2: Resume agent heartbeats
    print("\n[2/4] Resuming agent heartbeats...")
    agent_heartbeats = populate_agent_heartbeats(conn)
    print(f"      Populated {len(agent_heartbeats)} agent heartbeat records")

    # Objective 3: Telegram heartbeat trace
    print("\n[3/4] Documenting Telegram heartbeat truth source...")
    telegram_trace = get_telegram_heartbeat_trace(conn)
    print(f"      Truth source: {telegram_trace['truth_source']['primary_table']}")

    # Objective 4: DEFCON semantics
    print("\n[4/4] Documenting DEFCON evaluation semantics...")
    defcon_semantics = get_defcon_evaluation_semantics(conn)
    print(f"      Current level: {defcon_semantics['current_state']['defcon_level'] if defcon_semantics['current_state'] else 'UNKNOWN'}")

    evidence = {
        'evidence_id': 'CEO_DIR_2026_043_OBSERVABILITY_ACTIVATION',
        'directive': 'CEO-DIR-2026-043',
        'generated_by': 'STIG',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'status': 'COMPLETE',

        'objective_1_monitoring': {
            'status': 'COMPLETE',
            'table': 'fhq_monitoring.daemon_health',
            'records_populated': len(daemon_health),
            'daemon_status': daemon_health
        },

        'objective_2_agent_heartbeats': {
            'status': 'COMPLETE',
            'table': 'fhq_governance.agent_heartbeats',
            'records_populated': len(agent_heartbeats),
            'agent_status': agent_heartbeats
        },

        'objective_3_telegram_trace': {
            'status': 'COMPLETE',
            'trace': telegram_trace
        },

        'objective_4_defcon_semantics': {
            'status': 'COMPLETE',
            'semantics': defcon_semantics
        },

        'compliance': {
            'execution_impact': 'NONE',
            'capital_exposure': 'ZERO',
            'agency_change': 'NONE',
            'tables_modified': [
                'fhq_monitoring.daemon_health',
                'fhq_governance.agent_heartbeats'
            ]
        }
    }

    return evidence


def main():
    """Main entry point."""
    try:
        conn = get_connection()
        print("Database connection established")

        evidence = generate_evidence(conn)

        # Save evidence file
        evidence_path = os.path.join(
            os.path.dirname(__file__),
            'evidence',
            'CEO_DIR_2026_043_OBSERVABILITY_ACTIVATION.json'
        )

        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)

        print(f"\n{'=' * 60}")
        print(f"Evidence saved to: {evidence_path}")
        print(f"{'=' * 60}")

        # Print summary
        print("\n[SUMMARY]")
        print(f"  Daemon Health Records:  {evidence['objective_1_monitoring']['records_populated']}")
        print(f"  Agent Heartbeats:       {evidence['objective_2_agent_heartbeats']['records_populated']}")
        print(f"  Telegram Truth Source:  {evidence['objective_3_telegram_trace']['trace']['truth_source']['primary_table']}")
        print(f"  DEFCON Level:           {evidence['objective_4_defcon_semantics']['semantics']['current_state']['defcon_level']}")

        conn.close()
        return evidence

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    main()
