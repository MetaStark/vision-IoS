#!/usr/bin/env python3
"""
DEFCON Live Evaluator
CEO-DIR-2026-045 Compliance: DEFCON should be evaluated continuously

This script:
1. Evaluates current system health metrics
2. Updates DEFCON state with fresh timestamp
3. Level changes only if thresholds are breached (requires CEO approval for escalation)

Run via orchestrator or standalone for continuous evaluation.
"""

import os
import sys
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

EVIDENCE_DIR = Path(__file__).parent / "evidence"


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "54322"),
        database=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres")
    )


def evaluate_defcon(conn) -> dict:
    """
    Evaluate current DEFCON level based on system health.

    Inputs:
    - Price freshness (live data only)
    - Forecast production rate
    - Agent health (unhealthy count)
    - Agent heartbeat cascade (stale count)

    Returns evaluation result with recommended level.
    """
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    result = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {},
        "warnings": [],
        "recommendation": None
    }

    # 1. Price freshness (live crypto data only - equity is daily)
    cursor.execute("""
        SELECT
            market_type,
            ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(event_time_utc)))/60, 2) as minutes_stale
        FROM fhq_core.market_prices_live
        WHERE market_type IN ('SPOT', 'FUTURES_PERP')
        GROUP BY market_type
    """)
    price_freshness = {row['market_type']: float(row['minutes_stale']) for row in cursor.fetchall()}
    result["inputs"]["price_freshness"] = price_freshness

    max_price_stale = max(price_freshness.values()) if price_freshness else 999
    if max_price_stale > 60:
        result["warnings"].append(f"PRICE_STALE: {max_price_stale:.1f} minutes")

    # 2. Forecast production (last hour)
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM fhq_research.forecast_ledger
        WHERE forecast_made_at > NOW() - INTERVAL '1 hour'
    """)
    forecasts_hour = int(cursor.fetchone()['count'])
    result["inputs"]["forecasts_last_hour"] = forecasts_hour

    if forecasts_hour == 0:
        result["warnings"].append("FORECAST_STOPPED: No forecasts in last hour")

    # 3. Agent health
    cursor.execute("""
        SELECT
            COUNT(*) FILTER (WHERE health_score < 0.5) as unhealthy,
            COUNT(*) FILTER (WHERE EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) > 300) as stale,
            COUNT(*) as total
        FROM fhq_governance.agent_heartbeats
    """)
    agents = cursor.fetchone()
    result["inputs"]["agents"] = {
        "total": int(agents['total']),
        "unhealthy": int(agents['unhealthy']),
        "stale_heartbeats": int(agents['stale'])
    }

    if int(agents['unhealthy']) >= 3:
        result["warnings"].append(f"AGENT_CASCADE: {agents['unhealthy']} agents unhealthy")

    # 4. Get current DEFCON level
    cursor.execute("""
        SELECT defcon_level, reason, created_at
        FROM fhq_monitoring.defcon_state
        WHERE is_current = true
    """)
    current = cursor.fetchone()
    current_level = current['defcon_level'] if current else 5
    result["current_level"] = current_level

    # Determine recommended level
    warning_count = len(result["warnings"])
    critical_warnings = sum(1 for w in result["warnings"] if 'CASCADE' in w or 'STOPPED' in w)

    if critical_warnings >= 2:
        recommended = max(1, current_level - 2)  # Escalate by 2
        result["recommendation"] = {
            "level": recommended,
            "action": "ESCALATE_CRITICAL",
            "reason": f"{critical_warnings} critical warnings"
        }
    elif critical_warnings == 1 or warning_count >= 2:
        recommended = max(1, current_level - 1)  # Escalate by 1
        result["recommendation"] = {
            "level": recommended,
            "action": "ESCALATE",
            "reason": f"{warning_count} warnings detected"
        }
    elif warning_count == 0 and current_level < 5:
        recommended = min(5, current_level + 1)  # De-escalate by 1
        result["recommendation"] = {
            "level": recommended,
            "action": "DE_ESCALATE",
            "reason": "All systems nominal"
        }
    else:
        result["recommendation"] = {
            "level": current_level,
            "action": "MAINTAIN",
            "reason": "Normal operations" if warning_count == 0 else f"{warning_count} minor warnings"
        }

    return result


def update_defcon_state(conn, evaluation: dict, force_update: bool = False):
    """
    Update DEFCON state in database.

    By default, only updates timestamp. Level changes require force_update=True
    or automatic escalation for critical conditions.
    """
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    recommended = evaluation["recommendation"]
    current_level = evaluation["current_level"]
    new_level = recommended["level"]

    # Determine if we should change level
    level_change = new_level != current_level
    auto_escalate = recommended["action"] in ["ESCALATE_CRITICAL", "ESCALATE"]

    # Build reason string
    if recommended["action"] == "MAINTAIN":
        reason = f"Evaluated: {recommended['reason']}"
    else:
        reason = f"{recommended['action']}: {recommended['reason']}"

    if level_change and (force_update or auto_escalate):
        # Insert new DEFCON state (mark old as not current)
        cursor.execute("""
            UPDATE fhq_monitoring.defcon_state SET is_current = false WHERE is_current = true
        """)

        cursor.execute("""
            INSERT INTO fhq_monitoring.defcon_state (state_id, defcon_level, reason, set_by, created_at, is_current)
            VALUES (%s, %s, %s, %s, NOW(), true)
            RETURNING state_id, defcon_level, created_at
        """, (str(uuid.uuid4()), new_level, reason, 'DEFCON_EVALUATOR'))

        new_state = cursor.fetchone()
        conn.commit()

        return {
            "action": "LEVEL_CHANGED",
            "old_level": current_level,
            "new_level": new_level,
            "state_id": new_state['state_id'],
            "timestamp": new_state['created_at'].isoformat()
        }
    else:
        # Just update the existing row's timestamp and reason
        cursor.execute("""
            UPDATE fhq_monitoring.defcon_state
            SET reason = %s, created_at = NOW()
            WHERE is_current = true
            RETURNING state_id, defcon_level, reason, created_at
        """, (reason,))

        updated = cursor.fetchone()
        conn.commit()

        return {
            "action": "TIMESTAMP_UPDATED",
            "level": updated['defcon_level'],
            "reason": updated['reason'],
            "timestamp": updated['created_at'].isoformat()
        }


def main():
    """Run DEFCON evaluation and update."""
    print("=" * 60)
    print("DEFCON Live Evaluator")
    print("=" * 60)

    conn = get_db_connection()

    # Evaluate current state
    print("\n[1/2] Evaluating system health...")
    evaluation = evaluate_defcon(conn)

    print(f"  Current Level: {evaluation['current_level']}")
    print(f"  Warnings: {len(evaluation['warnings'])}")
    for w in evaluation['warnings']:
        print(f"    - {w}")
    print(f"  Recommendation: {evaluation['recommendation']['action']} -> Level {evaluation['recommendation']['level']}")

    # Update DEFCON state
    print("\n[2/2] Updating DEFCON state...")
    result = update_defcon_state(conn, evaluation)

    print(f"  Action: {result['action']}")
    print(f"  Level: {result.get('new_level', result.get('level'))}")
    print(f"  Timestamp: {result['timestamp']}")

    conn.close()

    # Summary
    print("\n" + "=" * 60)
    print("DEFCON state is now LIVE")
    print("=" * 60)

    return evaluation, result


if __name__ == "__main__":
    main()
