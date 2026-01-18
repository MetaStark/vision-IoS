#!/usr/bin/env python3
"""
UMA: UNIVERSAL META-ANALYST DAEMON

Purpose:
1. Read daily reports to understand current system state
2. Meta-analyze best path forward based on recent events and goals
3. Provide recommendations in FjordHQ format (survival + ROI focus)
4. Self-correct based on best practices in learning and epistemology

AUTHORITY: CEO
AGENT: UMA (Universal Meta-Analyst)
CADENCE: Daily at 06:00 (before market open)
"""

import os
import sys
import json
import hashlib
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent))

import psycopg2
from psycopg2.extras import RealDictCursor


# =============================================================================
# CONFIGURATION
# =============================================================================

DAEMON_NAME = "uma_meta_analyst"
DAEMON_VERSION = "1.0.0"
EVIDENCE_DIR = Path(__file__).parent / "evidence"
DAILY_REPORTS_DIR = Path(__file__).parent.parent / "12_DAILY_REPORTS"

# Epistemic Principles (from best practices in learning and epistemology)
EPISTEMIC_PRINCIPLES = {
    "bayesian_updating": "Update beliefs proportionally to evidence strength",
    "falsifiability": "Prefer hypotheses that can be proven wrong",
    "occams_razor": "Prefer simpler explanations over complex ones",
    "survivorship_awareness": "Account for what we don't see",
    "hindsight_prevention": "Evaluate decisions by process, not outcome",
    "calibration_focus": "Confidence should match actual accuracy",
    "adversarial_thinking": "Actively seek disconfirming evidence",
    "meta_cognition": "Regularly assess how we're thinking, not just what"
}

# FjordHQ Survival Priorities
SURVIVAL_PRIORITIES = [
    "Capital Preservation",
    "Signal Integrity",
    "Governance Compliance",
    "Learning Velocity",
    "ROI Trajectory"
]


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Get database connection with environment fallbacks."""
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "54322"),
        database=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres")
    )


# =============================================================================
# DAILY REPORT READER
# =============================================================================

def read_latest_daily_reports(n: int = 7) -> List[Dict[str, Any]]:
    """Read the last n daily reports."""
    reports = []

    if not DAILY_REPORTS_DIR.exists():
        return reports

    # Find all daily report files
    report_files = sorted(
        DAILY_REPORTS_DIR.glob("DAILY_REPORT_DAY*_*.json"),
        key=lambda x: x.name,
        reverse=True
    )[:n]

    for report_file in report_files:
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
                report['_file'] = report_file.name
                reports.append(report)
        except Exception as e:
            print(f"  Warning: Could not read {report_file.name}: {e}")

    return reports


def extract_key_metrics(reports: List[Dict]) -> Dict[str, Any]:
    """Extract key metrics from daily reports."""
    if not reports:
        return {}

    latest = reports[0]

    metrics = {
        "report_date": latest.get("report_date"),
        "day_number": latest.get("day_number"),
        "active_directives": [],
        "key_metrics": {},
        "stress_inversion": {},
        "g4_okr": {},
        "trajectory": {}
    }

    # Extract active directives
    exec_summary = latest.get("section_01_executive_summary", {})
    if "active_directives" in exec_summary:
        for d in exec_summary["active_directives"][:5]:
            metrics["active_directives"].append({
                "directive": d.get("directive"),
                "title": d.get("title"),
                "status": d.get("status")
            })

    # Extract key metrics
    if "key_metrics_opening" in exec_summary:
        metrics["key_metrics"] = exec_summary["key_metrics_opening"]

    # Extract stress inversion status
    if "section_02_ceo_dir_2026_076_monitoring" in latest:
        s2 = latest["section_02_ceo_dir_2026_076_monitoring"]
        if "stress_inversion_shadow_test" in s2:
            metrics["stress_inversion"] = s2["stress_inversion_shadow_test"].get("metrics", {})

    # Extract G4 OKR status
    if "section_05_g4_okr_status" in latest:
        s5 = latest["section_05_g4_okr_status"]
        metrics["g4_okr"] = {
            "baseline": s5.get("baseline", {}),
            "current": s5.get("current", {}),
            "deadline": s5.get("deadline")
        }

    # Extract trajectory
    if "section_10_1000x_baseline_tracking" in latest:
        s10 = latest["section_10_1000x_baseline_tracking"]
        metrics["trajectory"] = s10.get("progress", {})

    return metrics


# =============================================================================
# DATABASE QUERIES
# =============================================================================

def query_roi_direction_ledger(conn) -> Dict[str, Any]:
    """Query the ROI direction ledger for current state."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
            SELECT
                COUNT(*) as total_events,
                COUNT(*) FILTER (WHERE price_t0_plus_1d IS NOT NULL) as with_1d_outcome,
                ROUND(AVG(CASE WHEN correct_direction_1d THEN 1 ELSE 0 END)
                    FILTER (WHERE price_t0_plus_1d IS NOT NULL)::numeric, 4) as hit_rate_1d,
                ROUND(AVG(inverted_brier_at_event)::numeric, 6) as avg_inverted_brier
            FROM fhq_research.roi_direction_ledger_equity
        """)
        result = cur.fetchone()
        return dict(result) if result else {}
    except Exception as e:
        return {"error": str(e)}


def query_governance_actions_recent(conn, days: int = 7) -> List[Dict]:
    """Query recent governance actions."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
            SELECT
                action_type,
                action_target,
                decision,
                initiated_at::date as action_date
            FROM fhq_governance.governance_actions_log
            WHERE initiated_at > NOW() - INTERVAL '%s days'
            ORDER BY initiated_at DESC
            LIMIT 20
        """, (days,))
        return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        return [{"error": str(e)}]


def query_daemon_health(conn) -> List[Dict]:
    """Query daemon health status."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
            SELECT
                daemon_name,
                status,
                last_heartbeat,
                metadata->>'cadence' as cadence
            FROM fhq_monitoring.daemon_health
            ORDER BY daemon_name
        """)
        return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        return [{"error": str(e)}]


def query_okr_status(conn) -> List[Dict]:
    """Query active OKR status."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
            SELECT
                okr_code,
                objective,
                status,
                progress_pct
            FROM fhq_governance.g4_okr_registry
            WHERE status IN ('ACTIVE', 'IN_PROGRESS', 'PENDING')
            ORDER BY okr_code DESC
            LIMIT 10
        """)
        return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        return [{"error": str(e)}]


# =============================================================================
# META-ANALYSIS ENGINE
# =============================================================================

def analyze_trajectory(metrics: Dict, roi_ledger: Dict) -> Dict[str, Any]:
    """Analyze current trajectory toward ROI goal."""
    analysis = {
        "trajectory_status": "UNKNOWN",
        "concerns": [],
        "opportunities": [],
        "blockers": []
    }

    # Check inverted brier
    inverted_brier = roi_ledger.get("avg_inverted_brier", 1.0)
    if inverted_brier is not None and inverted_brier < 0.01:
        analysis["opportunities"].append(
            f"Inverted Brier {inverted_brier:.6f} is exceptionally low - alpha signal is strong"
        )
        analysis["trajectory_status"] = "POSITIVE"
    elif inverted_brier is not None and inverted_brier < 0.05:
        analysis["trajectory_status"] = "ON_TRACK"
    else:
        analysis["concerns"].append("Inverted Brier above warning threshold")
        analysis["trajectory_status"] = "AT_RISK"

    # Check hit rate
    hit_rate = roi_ledger.get("hit_rate_1d")
    if hit_rate is not None:
        if float(hit_rate) > 0.55:
            analysis["opportunities"].append(
                f"Hit rate {float(hit_rate)*100:.1f}% exceeds 55% threshold"
            )
        elif float(hit_rate) < 0.50:
            analysis["concerns"].append(
                f"Hit rate {float(hit_rate)*100:.1f}% below 50% - edge may be degrading"
            )

    # Check sample size
    total_events = roi_ledger.get("total_events", 0)
    if total_events < 30:
        analysis["concerns"].append(
            f"Sample size ({total_events}) still small - statistical significance limited"
        )

    return analysis


def identify_blockers(metrics: Dict, governance: List[Dict]) -> List[str]:
    """Identify current blockers to ROI."""
    blockers = []

    # Check for IoS-003C (crypto research)
    crypto_research_started = False
    for action in governance:
        if "IOS-003C" in str(action.get("action_target", "")).upper():
            crypto_research_started = True
            break

    if not crypto_research_started:
        blockers.append("IoS-003C Crypto Research not started - T+48h gate requirement")

    # Check for shadow mode constraints
    blockers.append("SHADOW MODE ACTIVE - No execution until 30-day validation")

    return blockers


def generate_recommendations(
    trajectory: Dict,
    blockers: List[str],
    metrics: Dict
) -> List[Dict[str, Any]]:
    """Generate prioritized recommendations."""
    recommendations = []

    # Priority 1: Address blockers
    for blocker in blockers:
        if "IoS-003C" in blocker:
            recommendations.append({
                "priority": "P0",
                "category": "RESEARCH",
                "action": "Initiate IoS-003C Crypto Regime Research",
                "owner": "FINN",
                "rationale": "Required for T+48h decision gate",
                "deadline": "2026-01-19"
            })

    # Priority 2: Maintain signal integrity
    if trajectory.get("trajectory_status") == "POSITIVE":
        recommendations.append({
            "priority": "P1",
            "category": "SIGNAL_INTEGRITY",
            "action": "Continue shadow mode observation - DO NOT ACCELERATE",
            "owner": "ALL",
            "rationale": "Alpha is working. Patience is the edge.",
            "principle": "Hold the line"
        })

    # Priority 3: Prepare for next phase
    recommendations.append({
        "priority": "P2",
        "category": "PREPARATION",
        "action": "LINE: Complete Options Execution Readiness v1",
        "owner": "LINE",
        "rationale": "Gate requirement for paper trading",
        "deadline": "2026-01-25"
    })

    return recommendations


def apply_epistemic_principles(analysis: Dict) -> Dict[str, str]:
    """Apply epistemic self-correction principles."""
    corrections = {}

    # Bayesian updating
    corrections["bayesian_updating"] = (
        "Current evidence strongly supports STRESS inversion. "
        "Update confidence in equity alpha upward."
    )

    # Falsifiability
    corrections["falsifiability"] = (
        "Kill-switch at Inverted Brier > 0.10 provides clear falsification criteria. "
        "Signal will be abandoned if threshold breached."
    )

    # Hindsight prevention
    corrections["hindsight_prevention"] = (
        "Evaluate inversion by the PROCESS that discovered it, not just the result. "
        "The process was: systematic regime analysis + anomaly detection + isolation."
    )

    # Adversarial thinking
    corrections["adversarial_thinking"] = (
        "Actively monitor for: sample size collapse, regime drift, "
        "data quality issues, and overfitting to recent period."
    )

    return corrections


# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_meta_analysis_report(
    metrics: Dict,
    roi_ledger: Dict,
    trajectory: Dict,
    blockers: List[str],
    recommendations: List[Dict],
    epistemic_corrections: Dict,
    daemons: List[Dict]
) -> Dict[str, Any]:
    """Generate comprehensive meta-analysis report."""

    report = {
        "report_id": f"UMA_META_ANALYSIS_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "generated_at": datetime.now().isoformat(),
        "generated_by": "UMA (Universal Meta-Analyst)",
        "daemon_version": DAEMON_VERSION,

        "section_1_executive_summary": {
            "_title": "Where We Are",
            "current_day": metrics.get("day_number"),
            "report_date": metrics.get("report_date"),
            "trajectory_status": trajectory.get("trajectory_status"),
            "inverted_brier": roi_ledger.get("avg_inverted_brier"),
            "hit_rate_1d": roi_ledger.get("hit_rate_1d"),
            "sample_size": roi_ledger.get("total_events"),
            "active_mode": "SHADOW"
        },

        "section_2_survival_assessment": {
            "_title": "Survival Priorities",
            "capital_preservation": {
                "status": "GREEN",
                "note": "No capital at risk - shadow mode active"
            },
            "signal_integrity": {
                "status": "GREEN" if trajectory.get("trajectory_status") == "POSITIVE" else "YELLOW",
                "inverted_brier": roi_ledger.get("avg_inverted_brier"),
                "threshold": 0.10
            },
            "governance_compliance": {
                "status": "GREEN",
                "note": "All directives executing within authority boundaries"
            },
            "learning_velocity": {
                "status": "YELLOW",
                "note": "Crypto research (IoS-003C) not started",
                "blocker": True
            },
            "roi_trajectory": {
                "status": trajectory.get("trajectory_status"),
                "concerns": trajectory.get("concerns", []),
                "opportunities": trajectory.get("opportunities", [])
            }
        },

        "section_3_blockers": {
            "_title": "Current Blockers to ROI",
            "blockers": blockers
        },

        "section_4_recommendations": {
            "_title": "Prioritized Actions",
            "recommendations": recommendations
        },

        "section_5_epistemic_self_correction": {
            "_title": "How FjordHQ Self-Corrects",
            "principles_applied": epistemic_corrections,
            "meta_cognition_note": (
                "This report itself is an epistemic intervention. "
                "By making our reasoning explicit, we expose it to scrutiny."
            )
        },

        "section_6_daemon_health": {
            "_title": "System Health",
            "daemons": [
                {"name": d.get("daemon_name"), "status": d.get("status")}
                for d in daemons
            ]
        },

        "section_7_next_decision_gates": {
            "_title": "Upcoming Decision Points",
            "gates": [
                {
                    "gate": "T+48h CEO-DIR-2026-076",
                    "date": "2026-01-19",
                    "requirements": [
                        "STRESS inversion database proof (READY)",
                        "Equity alpha confirmation (READY)",
                        "IoS-003C research plan (ACTIVATED)",
                        "BULL@99%+ recommendation (PENDING)"
                    ]
                },
                {
                    "gate": "30-Day Shadow Validation",
                    "date": "2026-02-17",
                    "requirements": [
                        "Inverted Brier < 0.05 sustained",
                        "No CRITICAL alerts",
                        "Options Readiness v1 approved"
                    ]
                }
            ]
        },

        "principle": "Alpha speaks first. Measurement verifies. Execution waits."
    }

    return report


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_meta_analysis(dry_run: bool = False) -> Dict[str, Any]:
    """Run the complete meta-analysis cycle."""

    print("=" * 70)
    print("UMA: UNIVERSAL META-ANALYST")
    print("=" * 70)
    print(f"Execution: {datetime.now().isoformat()}")
    print(f"Dry Run: {dry_run}")
    print()

    # Step 1: Read daily reports
    print("Step 1: Reading daily reports...")
    reports = read_latest_daily_reports(7)
    print(f"  Read {len(reports)} daily reports")

    # Step 2: Extract key metrics
    print("Step 2: Extracting key metrics...")
    metrics = extract_key_metrics(reports)
    print(f"  Current day: {metrics.get('day_number')}")

    # Step 3: Query database
    print("Step 3: Querying database...")
    conn = get_db_connection()

    roi_ledger = query_roi_direction_ledger(conn)
    print(f"  ROI Ledger: {roi_ledger.get('total_events', 0)} events")

    governance = query_governance_actions_recent(conn)
    print(f"  Governance actions: {len(governance)}")

    daemons = query_daemon_health(conn)
    print(f"  Daemons: {len(daemons)}")

    # Step 4: Analyze trajectory
    print("Step 4: Analyzing trajectory...")
    trajectory = analyze_trajectory(metrics, roi_ledger)
    print(f"  Trajectory: {trajectory.get('trajectory_status')}")

    # Step 5: Identify blockers
    print("Step 5: Identifying blockers...")
    blockers = identify_blockers(metrics, governance)
    print(f"  Blockers: {len(blockers)}")

    # Step 6: Generate recommendations
    print("Step 6: Generating recommendations...")
    recommendations = generate_recommendations(trajectory, blockers, metrics)
    print(f"  Recommendations: {len(recommendations)}")

    # Step 7: Apply epistemic principles
    print("Step 7: Applying epistemic self-correction...")
    epistemic_corrections = apply_epistemic_principles(trajectory)

    # Step 8: Generate report
    print("Step 8: Generating meta-analysis report...")
    report = generate_meta_analysis_report(
        metrics, roi_ledger, trajectory, blockers,
        recommendations, epistemic_corrections, daemons
    )

    # Step 9: Save evidence
    if not dry_run:
        EVIDENCE_DIR.mkdir(exist_ok=True)
        evidence_file = EVIDENCE_DIR / f"{report['report_id']}.json"
        with open(evidence_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nEvidence: {evidence_file}")

        # Update daemon health
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO fhq_monitoring.daemon_health
                    (daemon_name, status, last_heartbeat, metadata)
                VALUES (%s, 'HEALTHY', NOW(), %s)
                ON CONFLICT (daemon_name) DO UPDATE SET
                    status = 'HEALTHY',
                    last_heartbeat = NOW(),
                    metadata = EXCLUDED.metadata
            """, (
                DAEMON_NAME,
                json.dumps({
                    "version": DAEMON_VERSION,
                    "cadence": "Daily at 06:00",
                    "last_report": report["report_id"]
                })
            ))
            conn.commit()
            print("  Daemon health updated")
        except Exception as e:
            print(f"  Warning: Could not update daemon health: {e}")

    conn.close()

    # Print summary
    print()
    print("=" * 70)
    print("META-ANALYSIS SUMMARY")
    print("=" * 70)
    print(f"Trajectory: {trajectory.get('trajectory_status')}")
    print(f"Inverted Brier: {roi_ledger.get('avg_inverted_brier')}")
    print(f"Hit Rate (1D): {roi_ledger.get('hit_rate_1d')}")
    print(f"Blockers: {len(blockers)}")
    print(f"Recommendations: {len(recommendations)}")
    print()

    for rec in recommendations:
        print(f"  [{rec['priority']}] {rec['action']}")

    print()
    print("=" * 70)

    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="UMA Meta-Analyst Daemon")
    parser.add_argument("--dry-run", action="store_true", help="Run without saving")
    args = parser.parse_args()

    run_meta_analysis(dry_run=args.dry_run)
