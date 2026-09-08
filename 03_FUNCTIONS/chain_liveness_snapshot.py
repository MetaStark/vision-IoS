#!/usr/bin/env python3
"""
CEO-DIR-043: Chain Liveness Hourly Snapshot
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

def calculate_stage_status(latest_ts, rows_last_hour, sla_window_hours, threshold_rows=0):
    """Determine stage status based on freshness and throughput"""
    status = "PASS"
    suspected_cause = None

    now = datetime.now(timezone.utc)

    # Freshness check
    if latest_ts:
        age_hours = (now - latest_ts).total_seconds() / 3600
        if age_hours > sla_window_hours * 2:
            status = "FAIL"
            suspected_cause = f"Stale: {age_hours:.1f}h > {sla_window_hours * 2}h SLA"
        elif age_hours > sla_window_hours:
            status = "DEGRADED"
            suspected_cause = f"Aging: {age_hours:.1f}h > {sla_window_hours}h SLA"

    # Throughput check
    if rows_last_hour <= threshold_rows:
        if status == "PASS":
            status = "DEGRADED" if threshold_rows == 0 else "FAIL"
        suspected_cause = f"No throughput: {rows_last_hour} rows/hour"
    else:
        suspected_cause = None

    return status, suspected_cause

def main():
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now(timezone.utc)

    # Stage 1: Ingest Freshness (outcome_ledger)
    cur.execute("""
        SELECT
            MAX(outcome_timestamp) AS latest,
            COUNT(*) FILTER (WHERE outcome_timestamp >= %s) AS rows_last_hour
        FROM fhq_research.outcome_ledger
    """, (now - timedelta(hours=1),))
    row = cur.fetchone()
    ingest_freshness_latest = row[0]
    ingest_freshness_rows = row[1]
    ingest_freshness_status, ingest_freshness_cause = calculate_stage_status(
        ingest_freshness_latest, ingest_freshness_rows, 1
    )

    # Stage 2: Indicator Continuity (decision_packs creation)
    cur.execute("""
        SELECT
            MAX(created_at) AS latest,
            COUNT(*) FILTER (WHERE created_at >= %s) AS rows_last_hour
        FROM fhq_learning.decision_packs
    """, (now - timedelta(hours=1),))
    row = cur.fetchone()
    indicator_continuity_latest = row[0]
    indicator_continuity_rows = row[1]
    indicator_continuity_status, indicator_continuity_cause = calculate_stage_status(
        indicator_continuity_latest, indicator_continuity_rows, 2
    )

    # Stage 3: Forecast Production (brier_score_ledger)
    cur.execute("""
        SELECT
            MAX(forecast_timestamp) AS latest,
            COUNT(*) FILTER (WHERE forecast_timestamp >= %s) AS rows_last_hour
        FROM fhq_governance.brier_score_ledger
    """, (now - timedelta(hours=1),))
    row = cur.fetchone()
    forecast_production_latest = row[0]
    forecast_production_rows = row[1]
    forecast_production_status, forecast_production_cause = calculate_stage_status(
        forecast_production_latest, forecast_production_rows, 0.1, threshold_rows=1
    )

    # Stage 4: Alpha Graph Edges
    cur.execute("""
        SELECT
            MAX(created_at) AS latest,
            COUNT(*) FILTER (WHERE created_at >= %s) AS rows_last_hour
        FROM vision_signals.alpha_graph_edges
    """, (now - timedelta(hours=1),))
    row = cur.fetchone()
    alpha_graph_edges_latest = row[0]
    alpha_graph_edges_rows = row[1]
    alpha_graph_edges_status, alpha_graph_edges_cause = calculate_stage_status(
        alpha_graph_edges_latest, alpha_graph_edges_rows, 0.1, threshold_rows=1
    )

    # Stage 5: Decision Pack Execution
    cur.execute("""
        SELECT
            MAX(terminalized_at) AS latest,
            COUNT(*) FILTER (WHERE terminalized_at >= %s AND execution_status IN ('EXECUTED', 'FAILED')) AS rows_last_hour
        FROM fhq_learning.decision_packs
    """, (now - timedelta(hours=1),))
    row = cur.fetchone()
    decision_pack_execution_latest = row[0]
    decision_pack_execution_rows = row[1]
    decision_pack_execution_status, decision_pack_execution_cause = calculate_stage_status(
        decision_pack_execution_latest, decision_pack_execution_rows, 0.1, threshold_rows=1
    )

    # Stage 6: Outcome Settlement
    cur.execute("""
        SELECT
            MAX(settled_at) AS latest,
            COUNT(*) FILTER (WHERE settled_at >= %s) AS rows_last_hour
        FROM fhq_learning.outcome_settlement_log
    """, (now - timedelta(hours=1),))
    row = cur.fetchone()
    outcome_settlement_latest = row[0]
    outcome_settlement_rows = row[1]
    outcome_settlement_status, outcome_settlement_cause = calculate_stage_status(
        outcome_settlement_latest, outcome_settlement_rows, 1, threshold_rows=1
    )

    # Stage 7: LVI Canonical
    cur.execute("""
        SELECT
            MAX(computed_at) AS latest,
            COUNT(*) FILTER (WHERE computed_at >= %s) AS rows_last_hour
        FROM fhq_governance.lvi_canonical
    """, (now - timedelta(hours=1),))
    row = cur.fetchone()
    lvi_canonical_latest = row[0]
    lvi_canonical_rows = row[1]
    lvi_canonical_status, lvi_canonical_cause = calculate_stage_status(
        lvi_canonical_latest, lvi_canonical_rows, 1.08, threshold_rows=1
    )

    # Daemon heartbeats
    cur.execute("""
        SELECT daemon_name, last_heartbeat, status
        FROM fhq_monitoring.daemon_health
        WHERE daemon_name IN (
            'decision_pack_generator', 'finn_crypto_scheduler', 'mechanism_alpha_trigger',
            'alpha_graph_sync', 'outcome_settlement_daemon', 'lvi_calculator'
        )
    """)
    daemon_heartbeats = {row[0]: row[1] for row in cur.fetchall()}

    # Count passes
    stages = [
        ("ingest_freshness", ingest_freshness_status),
        ("indicator_continuity", indicator_continuity_status),
        ("forecast_production", forecast_production_status),
        ("alpha_graph_edges", alpha_graph_edges_status),
        ("decision_pack_execution", decision_pack_execution_status),
        ("outcome_settlement", outcome_settlement_status),
        ("lvi_canonical", lvi_canonical_status),
    ]
    pass_count = sum(1 for _, status in stages if status == "PASS")
    fail_count = sum(1 for _, status in stages if status != "PASS")

    # Build snapshot
    snapshot = {
        "snapshot_id": "manual-snapshot-001",
        "snapshot_at": now.isoformat(),
        "ingest_freshness": {
            "latest": ingest_freshness_latest.isoformat() if ingest_freshness_latest else None,
            "rows_last_hour": ingest_freshness_rows,
            "daemon_last_heartbeat": daemon_heartbeats.get("finn_crypto_scheduler").isoformat() if daemon_heartbeats.get("finn_crypto_scheduler") else None,
            "status": ingest_freshness_status,
            "suspected_cause": ingest_freshness_cause
        },
        "indicator_continuity": {
            "latest": indicator_continuity_latest.isoformat() if indicator_continuity_latest else None,
            "rows_last_hour": indicator_continuity_rows,
            "daemon_last_heartbeat": daemon_heartbeats.get("decision_pack_generator").isoformat() if daemon_heartbeats.get("decision_pack_generator") else None,
            "status": indicator_continuity_status,
            "suspected_cause": indicator_continuity_cause
        },
        "forecast_production": {
            "latest": forecast_production_latest.isoformat() if forecast_production_latest else None,
            "rows_last_hour": forecast_production_rows,
            "daemon_last_heartbeat": daemon_heartbeats.get("mechanism_alpha_trigger").isoformat() if daemon_heartbeats.get("mechanism_alpha_trigger") else None,
            "status": forecast_production_status,
            "suspected_cause": forecast_production_cause
        },
        "alpha_graph_edges": {
            "latest": alpha_graph_edges_latest.isoformat() if alpha_graph_edges_latest else None,
            "rows_last_hour": alpha_graph_edges_rows,
            "daemon_last_heartbeat": daemon_heartbeats.get("alpha_graph_sync").isoformat() if daemon_heartbeats.get("alpha_graph_sync") else None,
            "status": alpha_graph_edges_status,
            "suspected_cause": alpha_graph_edges_cause
        },
        "decision_pack_execution": {
            "latest": decision_pack_execution_latest.isoformat() if decision_pack_execution_latest else None,
            "rows_last_hour": decision_pack_execution_rows,
            "daemon_last_heartbeat": daemon_heartbeats.get("outcome_settlement_daemon").isoformat() if daemon_heartbeats.get("outcome_settlement_daemon") else None,
            "status": decision_pack_execution_status,
            "suspected_cause": decision_pack_execution_cause
        },
        "outcome_settlement": {
            "latest": outcome_settlement_latest.isoformat() if outcome_settlement_latest else None,
            "rows_last_hour": outcome_settlement_rows,
            "daemon_last_heartbeat": daemon_heartbeats.get("outcome_settlement_daemon").isoformat() if daemon_heartbeats.get("outcome_settlement_daemon") else None,
            "status": outcome_settlement_status,
            "suspected_cause": outcome_settlement_cause
        },
        "lvi_canonical": {
            "latest": lvi_canonical_latest.isoformat() if lvi_canonical_latest else None,
            "rows_last_hour": lvi_canonical_rows,
            "daemon_last_heartbeat": daemon_heartbeats.get("lvi_calculator").isoformat() if daemon_heartbeats.get("lvi_calculator") else None,
            "status": lvi_canonical_status,
            "suspected_cause": lvi_canonical_cause
        },
        "overall_pass_count": pass_count,
        "overall_fail_count": fail_count,
        "overall_verdict": "PASS" if pass_count == 7 else "FAIL" if fail_count >= 4 else "DEGRADED"
    }

    # Calculate evidence hash
    evidence_hash = "sha256:" + hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()

    snapshot["evidence_hash"] = evidence_hash

    # Write to database
    cur.execute("""
        INSERT INTO fhq_governance.chain_liveness_hourly (
            snapshot_id, snapshot_at,
            ingest_freshness_latest, ingest_freshness_rows_last_hour,
            ingest_freshness_daemon_last_heartbeat, ingest_freshness_status, ingest_freshness_suspected_cause,
            indicator_continuity_latest, indicator_continuity_rows_last_hour,
            indicator_continuity_daemon_last_heartbeat, indicator_continuity_status, indicator_continuity_suspected_cause,
            forecast_production_latest, forecast_production_rows_last_hour,
            forecast_production_daemon_last_heartbeat, forecast_production_status, forecast_production_suspected_cause,
            alpha_graph_edges_latest, alpha_graph_edges_rows_last_hour,
            alpha_graph_edges_daemon_last_heartbeat, alpha_graph_edges_status, alpha_graph_edges_suspected_cause,
            decision_pack_execution_latest, decision_pack_execution_rows_last_hour,
            decision_pack_execution_daemon_last_heartbeat, decision_pack_execution_status, decision_pack_execution_suspected_cause,
            outcome_settlement_latest, outcome_settlement_rows_last_hour,
            outcome_settlement_daemon_last_heartbeat, outcome_settlement_status, outcome_settlement_suspected_cause,
            lvi_canonical_latest, lvi_canonical_rows_last_hour,
            lvi_canonical_daemon_last_heartbeat, lvi_canonical_status, lvi_canonical_suspected_cause,
            overall_pass_count, overall_fail_count, overall_verdict, evidence_hash
        ) VALUES (
            gen_random_uuid(), %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s
        )
    """, (
        now,
        ingest_freshness_latest, ingest_freshness_rows, daemon_heartbeats.get("finn_crypto_scheduler"), ingest_freshness_status, ingest_freshness_cause,
        indicator_continuity_latest, indicator_continuity_rows, daemon_heartbeats.get("decision_pack_generator"), indicator_continuity_status, indicator_continuity_cause,
        forecast_production_latest, forecast_production_rows, daemon_heartbeats.get("mechanism_alpha_trigger"), forecast_production_status, forecast_production_cause,
        alpha_graph_edges_latest, alpha_graph_edges_rows, daemon_heartbeats.get("alpha_graph_sync"), alpha_graph_edges_status, alpha_graph_edges_cause,
        decision_pack_execution_latest, decision_pack_execution_rows, daemon_heartbeats.get("outcome_settlement_daemon"), decision_pack_execution_status, decision_pack_execution_cause,
        outcome_settlement_latest, outcome_settlement_rows, daemon_heartbeats.get("outcome_settlement_daemon"), outcome_settlement_status, outcome_settlement_cause,
        lvi_canonical_latest, lvi_canonical_rows, daemon_heartbeats.get("lvi_calculator"), lvi_canonical_status, lvi_canonical_cause,
        pass_count, fail_count, "PASS" if pass_count == 7 else "FAIL" if fail_count >= 4 else "DEGRADED", evidence_hash
    ))

    conn.commit()
    cur.close()
    conn.close()

    # Write evidence file
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    evidence_path = os.path.join(os.path.dirname(__file__), "evidence", f"CHAIN_LIVENESS_SNAPSHOT_{timestamp_str}.json")
    with open(evidence_path, "w") as f:
        json.dump(snapshot, f, indent=2)

    print(json.dumps(snapshot, indent=2))
    return snapshot

if __name__ == "__main__":
    from datetime import timedelta
    main()
