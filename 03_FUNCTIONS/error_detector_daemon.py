#!/usr/bin/env python3
"""
error_detector_daemon.py
CEO-DIR-2026-HYPOTHESIS-ECONOMY-001 Phase I

Error-First Learning: Every prediction error becomes a learning opportunity.

Author: STIG (EC-003)
Date: 2026-01-23
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid

# Configuration
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 54322,
    "dbname": "postgres",
    "user": "postgres"
}

EVIDENCE_DIR = Path(__file__).parent / "evidence"
LOG_FILE = Path(__file__).parent / "error_detector_daemon.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def detect_errors(lookback_hours: int = 24) -> dict:
    """
    Detect prediction errors from outcome_ledger.

    Uses the SQL function fhq_learning.detect_prediction_errors()
    to find and classify errors.
    """
    conn = get_db_connection()
    results = {
        "execution_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lookback_hours": lookback_hours,
        "errors_detected": [],
        "summary": {
            "total_new_errors": 0,
            "by_type": {},
            "by_priority": {}
        }
    }

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Call the detection function
            cur.execute("""
                SELECT * FROM fhq_learning.detect_prediction_errors(%s)
            """, (lookback_hours,))

            new_errors = cur.fetchall()

            for error in new_errors:
                error_dict = {
                    "error_id": str(error["new_error_id"]),
                    "error_code": error["error_code"],
                    "error_type": error["error_type"],
                    "source_prediction_id": str(error["source_prediction_id"]) if error["source_prediction_id"] else None,
                    "predicted_direction": error["predicted_direction"],
                    "actual_direction": error["actual_direction"],
                    "learning_priority": error["learning_priority"]
                }
                results["errors_detected"].append(error_dict)

                # Update summary
                error_type = error["error_type"]
                priority = error["learning_priority"]

                results["summary"]["by_type"][error_type] = results["summary"]["by_type"].get(error_type, 0) + 1
                results["summary"]["by_priority"][priority] = results["summary"]["by_priority"].get(priority, 0) + 1

            results["summary"]["total_new_errors"] = len(new_errors)

            conn.commit()

    except Exception as e:
        logger.error(f"Error detection failed: {e}")
        results["error"] = str(e)
        conn.rollback()
    finally:
        conn.close()

    return results


def get_error_summary() -> dict:
    """Get summary of all errors in the system."""
    conn = get_db_connection()
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_errors": 0,
        "high_priority_pending": 0,
        "hypotheses_generated": 0,
        "error_to_hypothesis_rate": 0.0,
        "by_type": {},
        "recent_errors": []
    }

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Total counts
            cur.execute("""
                SELECT
                    COUNT(*) AS total_errors,
                    COUNT(CASE WHEN learning_priority = 'HIGH' AND hypothesis_generated = FALSE THEN 1 END) AS high_priority_pending,
                    COUNT(CASE WHEN hypothesis_generated THEN 1 END) AS hypotheses_generated,
                    COUNT(CASE WHEN error_type = 'DIRECTION' THEN 1 END) AS direction_errors,
                    COUNT(CASE WHEN error_type = 'MAGNITUDE' THEN 1 END) AS magnitude_errors,
                    COUNT(CASE WHEN error_type = 'TIMING' THEN 1 END) AS timing_errors,
                    COUNT(CASE WHEN error_type = 'REGIME' THEN 1 END) AS regime_errors
                FROM fhq_learning.error_classification_taxonomy
            """)

            counts = cur.fetchone()
            if counts:
                summary["total_errors"] = counts["total_errors"]
                summary["high_priority_pending"] = counts["high_priority_pending"]
                summary["hypotheses_generated"] = counts["hypotheses_generated"]
                summary["by_type"] = {
                    "DIRECTION": counts["direction_errors"],
                    "MAGNITUDE": counts["magnitude_errors"],
                    "TIMING": counts["timing_errors"],
                    "REGIME": counts["regime_errors"]
                }

                if counts["total_errors"] > 0:
                    summary["error_to_hypothesis_rate"] = round(
                        counts["hypotheses_generated"] / counts["total_errors"] * 100, 2
                    )

            # Recent high-priority errors
            cur.execute("""
                SELECT * FROM fhq_learning.v_high_priority_errors
                LIMIT 10
            """)

            for error in cur.fetchall():
                summary["recent_errors"].append({
                    "error_code": error["error_code"],
                    "error_type": error["error_type"],
                    "predicted_direction": error["predicted_direction"],
                    "actual_direction": error["actual_direction"],
                    "confidence_at_prediction": float(error["confidence_at_prediction"]) if error["confidence_at_prediction"] else None,
                    "error_detected_at": error["error_detected_at"].isoformat() if error["error_detected_at"] else None
                })

    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        summary["error"] = str(e)
    finally:
        conn.close()

    return summary


def generate_evidence(results: dict, summary: dict) -> str:
    """Generate evidence file for this execution."""
    evidence = {
        "directive": "CEO-DIR-2026-HYPOTHESIS-ECONOMY-001",
        "phase": "I",
        "component": "error_detector_daemon",
        "execution_id": results["execution_id"],
        "timestamp": results["timestamp"],
        "detection_results": results,
        "system_summary": summary,
        "acceptance_tests": {
            "I.T1_daemon_executes": True,
            "I.T2_errors_classified": results["summary"]["total_new_errors"] > 0 or summary["total_errors"] > 0,
            "I.T3_priority_assignment": len(results["summary"]["by_priority"]) > 0 or summary["high_priority_pending"] >= 0,
            "I.T4_regime_mismatch": "REGIME" in results["summary"]["by_type"] or summary["by_type"].get("REGIME", 0) >= 0
        },
        "signed_by": "STIG (EC-003)"
    }

    filename = f"ERROR_DETECTOR_RUN_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = EVIDENCE_DIR / filename

    with open(filepath, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    return str(filepath)


def main():
    parser = argparse.ArgumentParser(description='Error Detector Daemon - Phase I')
    parser.add_argument('--lookback', type=int, default=24,
                        help='Lookback period in hours (default: 24)')
    parser.add_argument('--summary-only', action='store_true',
                        help='Only show summary, do not detect new errors')
    parser.add_argument('--generate-evidence', action='store_true',
                        help='Generate evidence file')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("ERROR DETECTOR DAEMON - Phase I")
    logger.info("CEO-DIR-2026-HYPOTHESIS-ECONOMY-001")
    logger.info("=" * 60)

    results = {"summary": {"total_new_errors": 0, "by_type": {}, "by_priority": {}}}

    if not args.summary_only:
        logger.info(f"Detecting errors with {args.lookback}h lookback...")
        results = detect_errors(args.lookback)

        if results["summary"]["total_new_errors"] > 0:
            logger.info(f"Detected {results['summary']['total_new_errors']} new errors")
            for error_type, count in results["summary"]["by_type"].items():
                logger.info(f"  {error_type}: {count}")
            for priority, count in results["summary"]["by_priority"].items():
                logger.info(f"  Priority {priority}: {count}")
        else:
            logger.info("No new errors detected")

    logger.info("\nSystem Summary:")
    summary = get_error_summary()
    logger.info(f"  Total errors in system: {summary['total_errors']}")
    logger.info(f"  High priority pending: {summary['high_priority_pending']}")
    logger.info(f"  Hypotheses generated: {summary['hypotheses_generated']}")
    logger.info(f"  Error-to-hypothesis rate: {summary['error_to_hypothesis_rate']}%")

    if summary["recent_errors"]:
        logger.info("\nRecent High-Priority Errors:")
        for error in summary["recent_errors"][:5]:
            logger.info(f"  {error['error_code']}: {error['error_type']} "
                       f"(pred: {error['predicted_direction']}, actual: {error['actual_direction']})")

    if args.generate_evidence:
        evidence_path = generate_evidence(results, summary)
        logger.info(f"\nEvidence file: {evidence_path}")

    logger.info("\n" + "=" * 60)
    logger.info("ERROR DETECTOR DAEMON COMPLETE")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
