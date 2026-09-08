#!/usr/bin/env python3
"""
CEO-DIR-044: Outcome Settlement Daemon Heartbeat Verification
"""
import os
import sys
import json
import hashlib
import psycopg2
from datetime import datetime, timezone

# Database connection
DB_HOST = "127.0.0.1"
DB_PORT = 54322
DB_NAME = "postgres"
DB_USER = "postgres"

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER
    )

def main():
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now(timezone.utc)

    # Service Liveness - Windows service status
    result = os.popen('sc query FjordHQ_OutcomeSettlement_Daemon').read()
    service_status = "RUNNING" in result.upper()

    # Settlement throughput
    cur.execute("""
        SELECT COUNT(*) AS rows_last_1h
        FROM fhq_learning.outcome_settlement_log
        WHERE settled_at >= NOW() - INTERVAL '1 hour'
    """)
    settlement_rows = cur.fetchone()[0]

    # Heartbeat freshness
    cur.execute("""
        SELECT
            daemon_name,
            status,
            last_heartbeat,
            NOW() - last_heartbeat AS time_since_heartbeat
        FROM fhq_monitoring.daemon_health
        WHERE daemon_name = 'outcome_settlement_daemon'
        ORDER BY last_heartbeat DESC
        LIMIT 1
    """)
    heartbeat_row = cur.fetchone()

    # Chain snapshot row written
    cur.execute("""
        SELECT COUNT(*) AS snapshot_count
        FROM fhq_governance.chain_liveness_hourly
        WHERE snapshot_at >= NOW() - INTERVAL '1 hour'
    """)
    snapshot_rows = cur.fetchone()[0]

    # Build proof block
    proof_block = {
        "verification_timestamp": now.isoformat(),
        "service_liveness": {
            "service_name": "FjordHQ_OutcomeSettlement_Daemon",
            "running": service_status,
            "sc_query_output": result.strip()
        },
        "settlement_throughput": {
            "rows_last_1h": settlement_rows,
            "query": "SELECT COUNT(*) FROM fhq_learning.outcome_settlement_log WHERE settled_at >= NOW() - INTERVAL '1 hour'"
        },
        "heartbeat_freshness": {
            "daemon_name": heartbeat_row[0] if heartbeat_row else None,
            "status": heartbeat_row[1] if heartbeat_row else None,
            "last_heartbeat": heartbeat_row[2].isoformat() if heartbeat_row and heartbeat_row[2] else None,
            "time_since_heartbeat": str(heartbeat_row[3]) if heartbeat_row and heartbeat_row[3] else None,
            "within_75_min": heartbeat_row[3] and heartbeat_row[3].total_seconds() <= 75*60 if heartbeat_row and heartbeat_row[3] else False
        },
        "chain_snapshot": {
            "rows_last_1h": snapshot_rows,
            "hourly_snapshot_recorded": snapshot_rows > 0
        },
        "verdict": {
            "service_running": service_status,
            "settlement_active": settlement_rows > 0,
            "heartbeat_fresh": heartbeat_row[3].total_seconds() <= 75*60 if heartbeat_row and heartbeat_row[3] else False,
            "overall": "PASS" if service_status and settlement_rows > 0 and (heartbeat_row[3].total_seconds() <= 75*60 if heartbeat_row and heartbeat_row[3] else False) else "FAIL"
        }
    }

    # Calculate evidence hash
    evidence_hash = "sha256:" + hashlib.sha256(json.dumps(proof_block, sort_keys=True).encode()).hexdigest()
    proof_block["evidence_hash"] = evidence_hash

    # Write evidence file
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    evidence_path = os.path.join(
        os.path.dirname(__file__),
        "evidence",
        f"DIR_044_SERVICE_INSTALL_EVIDENCE_{timestamp_str}.json"
    )
    with open(evidence_path, "w") as f:
        json.dump(proof_block, f, indent=2)

    # Print for CEO verification
    print(json.dumps(proof_block, indent=2))

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
