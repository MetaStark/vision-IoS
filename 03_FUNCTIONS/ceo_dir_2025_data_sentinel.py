#!/usr/bin/env python3
"""
CEO-DIR-2025-DATA-001 + CEO-DIR-2025-SENT-001 PERMANENT SENTINELS
=================================================================

Authority: CEO
Executor: STIG (EC-003)
Date: 2025-12-30

Automated sentinels that alert VEGA + CEO if:
1. Ingest updates = 0
2. Volume sanity violated
3. Regime updates skip a day
4. Regime diversity < 15%
5. Asset coverage < 100

CEO-DIR-2025-SENT-001 SEVERITY CLASSIFICATION:
- INFO:  Holiday equity volume anomalies (log only)
- WARN:  Asset coverage below soft threshold (log + dashboard flag)
- ALERT: Regime diversity < 15% (notify CEO + VEGA)
- BLOCK: Corrupt price ingest / missing regime day (halt downstream)

Governance logging mandatory per CEO-DIR-2025-SENT-001 Section C.
"""

import os
import sys
import json
import uuid
import hashlib
import logging
import requests
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Any

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load .env
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / '.env')

# Database config
DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', 54322)),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}

# Alert webhook (Slack/Discord/etc)
ALERT_WEBHOOK_URL = os.environ.get('ALERT_WEBHOOK_URL', '')

# Evidence directory
EVIDENCE_DIR = Path(__file__).parent / "evidence"
EVIDENCE_DIR.mkdir(exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger("CEO_DIR_SENTINEL")

# =============================================================================
# THRESHOLDS (CEO-DIR-2025-DATA-001 Section E)
# =============================================================================

# Ingest sentinel
INGEST_MIN_UPDATES = 1  # Alert if 0 updates

# Volume sanity
CRYPTO_VOLUME_MIN = 1000  # Alert if crypto volume below this
EQUITY_VOLUME_MIN = 100   # Alert if equity volume below this

# Regime sentinel
REGIME_MAX_STALE_DAYS = 1  # Alert if regime skips more than 1 day
REGIME_MIN_DIVERSITY_PCT = 15  # Alert if diversity < 15%
REGIME_MIN_ASSET_COVERAGE = 100  # Alert if coverage < 100 assets

# =============================================================================
# CEO-DIR-2025-SENT-001 SEVERITY CLASSIFICATION
# =============================================================================
# Severity levels with exit codes and actions
SEVERITY_INFO = 'INFO'      # Log only, exit 0
SEVERITY_WARN = 'WARN'      # Log + dashboard flag, exit 0
SEVERITY_ALERT = 'ALERT'    # Notify CEO + VEGA, exit 1
SEVERITY_BLOCK = 'BLOCK'    # Halt downstream execution, exit 2

# Sentinel -> Severity mapping (codified per CEO directive)
SENTINEL_SEVERITY_MAP = {
    'INGEST_UPDATES': {
        'pass': SEVERITY_INFO,
        'fail': SEVERITY_BLOCK,  # Zero ingest = BLOCK downstream
    },
    'VOLUME_SANITY': {
        'pass': SEVERITY_INFO,
        'fail': SEVERITY_INFO,   # Holiday volumes = INFO only
    },
    'REGIME_FRESHNESS': {
        'pass': SEVERITY_INFO,
        'fail': SEVERITY_BLOCK,  # Missing regime day = BLOCK
    },
    'REGIME_DIVERSITY': {
        'pass': SEVERITY_INFO,
        'fail': SEVERITY_ALERT,  # Low diversity = ALERT CEO+VEGA
    },
    'ASSET_COVERAGE': {
        'pass': SEVERITY_INFO,
        'fail': SEVERITY_WARN,   # Low coverage = WARN (data sufficiency)
    },
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG, options='-c client_encoding=UTF8')


def send_alert(severity: str, component: str, message: str, details: Dict = None):
    """
    Send alert via webhook and log locally.

    Severity levels:
    - CRITICAL: Requires immediate attention
    - WARNING: Needs review
    - INFO: Informational
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    alert_data = {
        'severity': severity,
        'component': component,
        'message': message,
        'timestamp': timestamp,
        'details': details or {},
        'directive': 'CEO-DIR-2025-DATA-001'
    }

    # Always log locally
    if severity == 'CRITICAL':
        logger.critical(f"[{component}] {message}")
    elif severity == 'WARNING':
        logger.warning(f"[{component}] {message}")
    else:
        logger.info(f"[{component}] {message}")

    # Send webhook if configured
    if ALERT_WEBHOOK_URL:
        try:
            # Format for Slack/Discord
            webhook_payload = {
                'text': f"*[{severity}]* {component}\n{message}",
                'attachments': [{
                    'color': 'danger' if severity == 'CRITICAL' else 'warning',
                    'fields': [
                        {'title': k, 'value': str(v), 'short': True}
                        for k, v in (details or {}).items()
                    ][:10]  # Limit fields
                }]
            }
            requests.post(ALERT_WEBHOOK_URL, json=webhook_payload, timeout=10)
        except Exception as e:
            logger.warning(f"Webhook alert failed: {e}")

    return alert_data


def log_sentinel_result(conn, sentinel_name: str, status: str, severity: str, details: Dict):
    """
    Log sentinel check result to fhq_governance.governance_actions_log.
    CEO-DIR-2025-SENT-001 Section C: Governance logging mandatory.
    """
    try:
        # Generate summary hash for audit trail
        summary_str = json.dumps(details, sort_keys=True, default=str)
        summary_hash = hashlib.sha256(summary_str.encode()).hexdigest()[:16]

        # Affected assets count
        affected_count = details.get('assets_updated', 0) or details.get('covered_assets', 0) or 0

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_id, action_type, action_target, action_target_type,
                    initiated_by, initiated_at, decision, decision_rationale,
                    metadata, agent_id, timestamp
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, NOW(), %s, %s,
                    %s, %s, NOW()
                )
            """, (
                str(uuid.uuid4()),
                'SENTINEL_CHECK',
                sentinel_name,
                'SENTINEL',
                'CEO-DIR-2025-SENT-001',
                status,
                f"Severity: {severity}",
                json.dumps({
                    'sentinel_id': sentinel_name,
                    'run_timestamp': datetime.now(timezone.utc).isoformat(),
                    'severity': severity,
                    'affected_assets_count': affected_count,
                    'summary_hash': summary_hash,
                    'details': details
                }, default=str),
                'STIG'
            ))
            conn.commit()
        logger.debug(f"Governance log written for {sentinel_name}")
    except Exception as e:
        logger.warning(f"Governance logging failed: {e}")
        conn.rollback()


# =============================================================================
# SENTINEL 1: INGEST UPDATES
# =============================================================================

def check_ingest_updates(conn) -> Tuple[bool, Dict]:
    """
    Check if today's ingest updated any assets.
    Alert if updates = 0.
    """
    today = date.today()
    yesterday = today - timedelta(days=1)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check for price updates in last 24h (use canonicalized_at or timestamp)
        cur.execute("""
            SELECT
                COUNT(DISTINCT canonical_id) as assets_updated,
                COUNT(*) as rows_inserted,
                MAX(canonicalized_at) as last_update
            FROM fhq_market.prices
            WHERE canonicalized_at >= %s
        """, (yesterday,))
        result = cur.fetchone()

    assets_updated = result['assets_updated'] or 0
    rows_inserted = result['rows_inserted'] or 0

    passed = assets_updated >= INGEST_MIN_UPDATES

    details = {
        'assets_updated': assets_updated,
        'rows_inserted': rows_inserted,
        'last_update': str(result['last_update']),
        'threshold': INGEST_MIN_UPDATES,
        'check_date': str(today)
    }

    if not passed:
        send_alert(
            'CRITICAL',
            'INGEST_SENTINEL',
            f'INGEST FAILURE: 0 assets updated in last 24h!',
            details
        )

    return passed, details


# =============================================================================
# SENTINEL 2: VOLUME SANITY
# =============================================================================

def check_volume_sanity(conn) -> Tuple[bool, Dict]:
    """
    Check for any recent corrupted volume values.
    Alert if CRYPTO volumes < 1000 or EQUITY volumes < 100.
    """
    today = date.today()
    week_ago = today - timedelta(days=7)

    # Use separate cursor for each query to avoid state issues
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Check CRYPTO volume sanity
        cur.execute("""
            SELECT
                COUNT(*)::integer as corrupted_count,
                COUNT(DISTINCT canonical_id)::integer as assets_affected
            FROM fhq_market.prices
            WHERE canonical_id LIKE %s
            AND volume < %s
            AND timestamp::date >= %s
        """, ('%-USD', CRYPTO_VOLUME_MIN, week_ago))
        crypto_result = cur.fetchone()

        # Check EQUITY volume sanity (excluding FX)
        cur.execute("""
            SELECT
                COUNT(*)::integer as corrupted_count,
                COUNT(DISTINCT p.canonical_id)::integer as assets_affected
            FROM fhq_market.prices p
            JOIN fhq_meta.assets a ON p.canonical_id = a.canonical_id
            WHERE a.asset_class = %s
            AND p.volume < %s
            AND p.timestamp::date >= %s
        """, ('EQUITY', EQUITY_VOLUME_MIN, week_ago))
        equity_result = cur.fetchone()
    finally:
        cur.close()

    crypto_corrupted = crypto_result['corrupted_count'] if crypto_result else 0
    equity_corrupted = equity_result['corrupted_count'] if equity_result else 0

    passed = crypto_corrupted == 0 and equity_corrupted == 0

    details = {
        'crypto_corrupted_rows': crypto_corrupted,
        'crypto_assets_affected': crypto_result['assets_affected'] if crypto_result else 0,
        'equity_corrupted_rows': equity_corrupted,
        'equity_assets_affected': equity_result['assets_affected'] if equity_result else 0,
        'crypto_threshold': CRYPTO_VOLUME_MIN,
        'equity_threshold': EQUITY_VOLUME_MIN,
        'check_window_days': 7
    }

    if not passed:
        send_alert(
            'CRITICAL',
            'VOLUME_SANITY_SENTINEL',
            f'VOLUME CORRUPTION DETECTED: {crypto_corrupted} crypto, {equity_corrupted} equity rows with invalid volumes!',
            details
        )

    return passed, details


# =============================================================================
# SENTINEL 3: REGIME FRESHNESS
# =============================================================================

def check_regime_freshness(conn) -> Tuple[bool, Dict]:
    """
    Check if regime updates are current.
    Alert if regime skipped more than 1 day.
    """
    today = date.today()

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get latest regime date (use perception_model_version for v4)
        cur.execute("""
            SELECT
                MAX(timestamp::date) as latest_date,
                COUNT(DISTINCT timestamp::date) as dates_in_week
            FROM fhq_perception.regime_daily
            WHERE perception_model_version LIKE '2026.PROD%'
            AND timestamp >= CURRENT_DATE - INTERVAL '7 days'
        """)
        result = cur.fetchone()

    latest_date = result['latest_date']
    days_stale = (today - latest_date).days if latest_date else 999

    passed = days_stale <= REGIME_MAX_STALE_DAYS

    details = {
        'latest_regime_date': str(latest_date),
        'days_stale': days_stale,
        'threshold_days': REGIME_MAX_STALE_DAYS,
        'dates_in_last_week': result['dates_in_week'] or 0
    }

    if not passed:
        send_alert(
            'CRITICAL',
            'REGIME_FRESHNESS_SENTINEL',
            f'REGIME STALE: Last update was {days_stale} days ago!',
            details
        )

    return passed, details


# =============================================================================
# SENTINEL 4: REGIME DIVERSITY
# =============================================================================

def check_regime_diversity(conn) -> Tuple[bool, Dict]:
    """
    Check regime state diversity.
    Alert if diversity < 15% (i.e., all assets in same regime).
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get latest regime date's diversity
        cur.execute("""
            WITH latest_regime AS (
                SELECT
                    regime_classification,
                    COUNT(*) as count
                FROM fhq_perception.regime_daily
                WHERE perception_model_version LIKE '2026.PROD%'
                AND timestamp = (
                    SELECT MAX(timestamp) FROM fhq_perception.regime_daily
                    WHERE perception_model_version LIKE '2026.PROD%'
                )
                GROUP BY regime_classification
            )
            SELECT
                COUNT(DISTINCT regime_classification) as unique_regimes,
                SUM(count) as total_assets,
                MAX(count)::float / NULLIF(SUM(count), 0) * 100 as max_concentration
            FROM latest_regime
        """)
        result = cur.fetchone()

    unique_regimes = result['unique_regimes'] or 0
    total_assets = result['total_assets'] or 0
    max_concentration = result['max_concentration'] or 100

    # Diversity = 100 - max_concentration (if one regime has 85%, diversity is 15%)
    diversity_pct = 100 - max_concentration if max_concentration else 0

    passed = diversity_pct >= REGIME_MIN_DIVERSITY_PCT

    details = {
        'unique_regimes': unique_regimes,
        'total_assets': total_assets,
        'diversity_pct': round(diversity_pct, 1),
        'max_concentration_pct': round(max_concentration, 1),
        'threshold_diversity_pct': REGIME_MIN_DIVERSITY_PCT
    }

    if not passed:
        send_alert(
            'WARNING',
            'REGIME_DIVERSITY_SENTINEL',
            f'LOW REGIME DIVERSITY: {diversity_pct:.1f}% (threshold: {REGIME_MIN_DIVERSITY_PCT}%)',
            details
        )

    return passed, details


# =============================================================================
# SENTINEL 5: ASSET COVERAGE
# =============================================================================

def check_asset_coverage(conn) -> Tuple[bool, Dict]:
    """
    Check regime asset coverage.
    Alert if coverage < 100 assets.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get latest regime date's coverage
        cur.execute("""
            SELECT
                COUNT(DISTINCT asset_id) as covered_assets,
                (SELECT COUNT(*) FROM fhq_meta.assets WHERE active_flag = true) as total_assets
            FROM fhq_perception.regime_daily
            WHERE perception_model_version LIKE '2026.PROD%'
            AND timestamp = (
                SELECT MAX(timestamp) FROM fhq_perception.regime_daily
                WHERE perception_model_version LIKE '2026.PROD%'
            )
        """)
        result = cur.fetchone()

    covered = result['covered_assets'] or 0
    total = result['total_assets'] or 0
    coverage_pct = (covered / total * 100) if total > 0 else 0

    passed = covered >= REGIME_MIN_ASSET_COVERAGE

    details = {
        'covered_assets': covered,
        'total_assets': total,
        'coverage_pct': round(coverage_pct, 1),
        'threshold_assets': REGIME_MIN_ASSET_COVERAGE
    }

    if not passed:
        send_alert(
            'CRITICAL',
            'ASSET_COVERAGE_SENTINEL',
            f'LOW REGIME COVERAGE: Only {covered} assets covered (threshold: {REGIME_MIN_ASSET_COVERAGE})',
            details
        )

    return passed, details


# =============================================================================
# MAIN SENTINEL RUNNER
# =============================================================================

def run_all_sentinels() -> Dict[str, Any]:
    """
    Run all sentinels and return results.
    CEO-DIR-2025-SENT-001: Severity-classified execution with governance logging.
    """
    start_time = datetime.now(timezone.utc)

    logger.info("=" * 70)
    logger.info("CEO-DIR-2025-SENT-001 DAILY SENTINEL EXECUTION")
    logger.info("=" * 70)
    logger.info(f"Time: {start_time.isoformat()}")
    logger.info("=" * 70)

    conn = get_connection()

    results = {
        'run_timestamp': start_time.isoformat(),
        'directive': 'CEO-DIR-2025-SENT-001',
        'sentinels': {},
        'all_passed': True,
        'highest_severity': SEVERITY_INFO,
        'severity_counts': {
            SEVERITY_INFO: 0,
            SEVERITY_WARN: 0,
            SEVERITY_ALERT: 0,
            SEVERITY_BLOCK: 0,
        }
    }

    # Severity priority for exit code determination
    SEVERITY_PRIORITY = {SEVERITY_INFO: 0, SEVERITY_WARN: 1, SEVERITY_ALERT: 2, SEVERITY_BLOCK: 3}

    # Run each sentinel
    sentinels = [
        ('INGEST_UPDATES', check_ingest_updates),
        ('VOLUME_SANITY', check_volume_sanity),
        ('REGIME_FRESHNESS', check_regime_freshness),
        ('REGIME_DIVERSITY', check_regime_diversity),
        ('ASSET_COVERAGE', check_asset_coverage),
    ]

    for name, check_func in sentinels:
        logger.info(f"\nRunning {name} sentinel...")
        try:
            # Reset connection state before each check
            conn.rollback()
            passed, details = check_func(conn)

            # Determine severity from codified mapping
            severity_map = SENTINEL_SEVERITY_MAP.get(name, {'pass': SEVERITY_INFO, 'fail': SEVERITY_WARN})
            severity = severity_map['pass'] if passed else severity_map['fail']

            results['sentinels'][name] = {
                'passed': passed,
                'severity': severity,
                'details': details
            }

            # Track severity counts
            results['severity_counts'][severity] += 1

            # Track highest severity
            if SEVERITY_PRIORITY[severity] > SEVERITY_PRIORITY[results['highest_severity']]:
                results['highest_severity'] = severity

            if passed:
                logger.info(f"  PASSED [{severity}]")
            else:
                results['all_passed'] = False
                if severity == SEVERITY_BLOCK:
                    logger.critical(f"  FAILED [{severity}] - DOWNSTREAM BLOCKED")
                elif severity == SEVERITY_ALERT:
                    logger.error(f"  FAILED [{severity}] - CEO+VEGA NOTIFIED")
                elif severity == SEVERITY_WARN:
                    logger.warning(f"  FAILED [{severity}]")
                else:
                    logger.info(f"  FAILED [{severity}] - Expected anomaly")

            # CEO-DIR-2025-SENT-001 Section C: Governance logging mandatory
            log_sentinel_result(conn, name, 'PASSED' if passed else 'FAILED', severity, details)

        except Exception as e:
            logger.error(f"  ERROR: {e}")
            conn.rollback()  # Reset connection on error
            results['sentinels'][name] = {
                'passed': False,
                'severity': SEVERITY_BLOCK,
                'error': str(e)
            }
            results['all_passed'] = False
            results['severity_counts'][SEVERITY_BLOCK] += 1
            results['highest_severity'] = SEVERITY_BLOCK

    # Summary
    results['completed_at'] = datetime.now(timezone.utc).isoformat()

    logger.info("\n" + "=" * 70)
    logger.info("SENTINEL RUN COMPLETE")
    logger.info("=" * 70)
    logger.info(f"All Passed: {results['all_passed']}")
    logger.info(f"Highest Severity: {results['highest_severity']}")
    logger.info(f"Severity Counts: INFO={results['severity_counts'][SEVERITY_INFO]}, "
                f"WARN={results['severity_counts'][SEVERITY_WARN]}, "
                f"ALERT={results['severity_counts'][SEVERITY_ALERT]}, "
                f"BLOCK={results['severity_counts'][SEVERITY_BLOCK]}")
    logger.info("=" * 70)

    # Save evidence
    evidence_file = EVIDENCE_DIR / f"CEO_DIR_SENTINEL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(evidence_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Evidence: {evidence_file}")

    conn.close()
    return results


if __name__ == "__main__":
    results = run_all_sentinels()

    # CEO-DIR-2025-SENT-001: Exit code based on highest severity
    # INFO/WARN = 0 (success), ALERT = 1 (notify), BLOCK = 2 (halt downstream)
    highest = results['highest_severity']
    if highest == SEVERITY_BLOCK:
        logger.critical("EXIT CODE 2: BLOCK - Downstream execution halted")
        sys.exit(2)
    elif highest == SEVERITY_ALERT:
        logger.error("EXIT CODE 1: ALERT - CEO+VEGA notification required")
        sys.exit(1)
    else:
        # INFO and WARN are non-fatal
        logger.info("EXIT CODE 0: System healthy (INFO/WARN only)")
        sys.exit(0)
