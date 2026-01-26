#!/usr/bin/env python3
"""
PRICE FRESHNESS HEARTBEAT
=========================
CEO-DIR-2026-0YC: Heartbeat Policy Alignment (2026-01-11)
(Supersedes CEO-DIR-2026-SITC-DATA-BLACKOUT-FIX-001 P2)

Scheduled heartbeat task that monitors price staleness for CRYPTO and FX.
Runs every 30 minutes via orchestrator.

CEO-DIR-2026-116: SPY/QQQ REMOVED from monitoring (2026-01-20)
- They are not in daily_ingest_worker.py asset universe
- Regime data comes from fhq_perception.regime_daily, not price data
- Monitoring non-ingested assets created persistent false alerts

Thresholds aligned to DAILY BAR granularity (yfinance ~1 bar/day):
- CRYPTO: max_ok=24h, warn=36h, blackout=48h
- FX:     max_ok=36h, warn=48h, blackout=72h (weekend closure)

Previous thresholds (6h/12h) were too aggressive for daily bars and caused
false alerts every Sunday when same-day bars weren't available yet.

Author: STIG (CTO)
Date: 2026-01-06 (original), 2026-01-11 (CEO-DIR-2026-0YC update)
"""

import os
import sys
import json
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('price_heartbeat')

# Database configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CEO_TELEGRAM_CHAT_ID = os.getenv('CEO_TELEGRAM_CHAT_ID')
CEO_GATEWAY_ENABLED = os.getenv('CEO_GATEWAY_ENABLED', '0') == '1'

# Market-aware price staleness thresholds
# CEO-DIR-2026-0YC: Aligned to DAILY BAR granularity (yfinance provides ~1 bar/day)
# CEO-DIR-2026-EURUSD-PERMANENT-FIX: FX weekend awareness
#
# FX MARKET HOURS: Sun 5PM ET to Fri 5PM ET (continuous)
# FX WEEKEND CLOSURE: Fri 5PM ET to Sun 5PM ET = 48h gap
# yfinance daily bars: Available after market close (Fri 5PM ET)
# On Monday morning ET, Friday's bar is ~60h old - this is EXPECTED
#
PRICE_STALENESS_CRYPTO = {
    'max_ok_hours': 24,      # Full confidence: within 24h of last daily bar
    'warn_hours': 36,        # Warn: 1.5x daily cadence
    'blackout_hours': 48     # Blackout: missed 2 daily bars
}

PRICE_STALENESS_EQUITY = {
    'max_ok_hours': 36,      # Full confidence: accounts for overnight + weekend start
    'warn_hours': 48,        # Warn: approaching weekend gap
    'blackout_hours': 72     # Blackout: missed full weekend (Fri close -> Mon open)
}

PRICE_STALENESS_FX = {
    'max_ok_hours': 60,      # FX weekend: Fri 5PM -> Mon 5PM ET = 72h max expected
    'warn_hours': 72,        # Warn: past Monday open without data
    'blackout_hours': 96     # Blackout: missed Monday entirely
}

# Assets to monitor
# CEO-DIR-2026-116: Only monitor assets that are actively ingested
# SPY/QQQ removed - not in daily_ingest_worker.py, only used for regime reference
# Regime data comes from fhq_perception.regime_daily, not price data
CANONICAL_CRYPTO = ['BTC-USD', 'ETH-USD', 'SOL-USD']
CANONICAL_EQUITY = []  # Empty - equity prices not ingested, regime from separate pipeline
CANONICAL_FX = ['EURUSD=X']


class HealthStatus(Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    BLACKOUT = "BLACKOUT"


@dataclass
class AssetHealth:
    """Health status for a single asset."""
    asset_id: str
    asset_type: str
    staleness_hours: float
    threshold_hours: float
    status: HealthStatus
    latest_timestamp: Optional[datetime]
    record_count: int


def send_telegram_alert(message: str) -> bool:
    """Send alert to CEO via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not CEO_TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured - skipping alert")
        return False

    if not CEO_GATEWAY_ENABLED:
        logger.info(f"CEO Gateway disabled - would send: {message[:100]}...")
        return False

    try:
        import requests
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                'chat_id': CEO_TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'Markdown'
            },
            timeout=10
        )

        if response.ok:
            logger.info("CEO alert sent via Telegram")
            return True
        else:
            logger.error(f"Telegram send failed: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram exception: {e}")
        return False


def get_asset_type(asset_id: str) -> str:
    """Determine asset type for threshold lookup."""
    if asset_id in CANONICAL_CRYPTO:
        return 'CRYPTO'
    elif asset_id in CANONICAL_EQUITY:
        return 'EQUITY'
    elif asset_id in CANONICAL_FX:
        return 'FX'
    else:
        return 'UNKNOWN'


def get_thresholds(asset_type: str) -> Dict[str, float]:
    """Get staleness thresholds for asset type (CEO-DIR-2026-0YC aligned to daily bars)."""
    if asset_type == 'CRYPTO':
        return PRICE_STALENESS_CRYPTO
    elif asset_type == 'EQUITY':
        return PRICE_STALENESS_EQUITY
    elif asset_type == 'FX':
        return PRICE_STALENESS_FX
    else:
        return PRICE_STALENESS_CRYPTO  # Default to crypto thresholds


def check_price_freshness(conn) -> List[AssetHealth]:
    """Check price freshness for all canonical assets."""
    results = []
    all_assets = CANONICAL_CRYPTO + CANONICAL_EQUITY + CANONICAL_FX

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for asset_id in all_assets:
            cur.execute("""
                SELECT
                    COUNT(*) as record_count,
                    MAX(timestamp) as latest_timestamp
                FROM fhq_market.prices
                WHERE canonical_id = %s
            """, (asset_id,))

            row = cur.fetchone()

            if not row or not row['latest_timestamp']:
                # No data - critical
                results.append(AssetHealth(
                    asset_id=asset_id,
                    asset_type=get_asset_type(asset_id),
                    staleness_hours=9999,
                    threshold_hours=0,
                    status=HealthStatus.BLACKOUT,
                    latest_timestamp=None,
                    record_count=0
                ))
                continue

            latest = row['latest_timestamp']
            if latest.tzinfo is None:
                latest = latest.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            staleness = now - latest
            staleness_hours = staleness.total_seconds() / 3600

            asset_type = get_asset_type(asset_id)
            thresholds = get_thresholds(asset_type)

            # Determine status
            if staleness_hours <= thresholds['max_ok_hours']:
                status = HealthStatus.HEALTHY
            elif staleness_hours <= thresholds['warn_hours']:
                status = HealthStatus.WARNING
            elif staleness_hours <= thresholds['blackout_hours']:
                status = HealthStatus.CRITICAL
            else:
                status = HealthStatus.BLACKOUT

            results.append(AssetHealth(
                asset_id=asset_id,
                asset_type=asset_type,
                staleness_hours=staleness_hours,
                threshold_hours=thresholds['warn_hours'],
                status=status,
                latest_timestamp=latest,
                record_count=row['record_count']
            ))

    return results


def log_heartbeat(conn, results: List[AssetHealth], alert_sent: bool = False) -> str:
    """Log heartbeat to system_heartbeats table."""
    # Determine overall status
    statuses = [r.status for r in results]
    if HealthStatus.BLACKOUT in statuses:
        overall_status = 'BLACKOUT'
    elif HealthStatus.CRITICAL in statuses:
        overall_status = 'CRITICAL'
    elif HealthStatus.WARNING in statuses:
        overall_status = 'WARNING'
    else:
        overall_status = 'HEALTHY'

    # Build metadata (including alert deduplication state)
    now_iso = datetime.now(timezone.utc).isoformat()
    metadata = {
        'timestamp': now_iso,
        'assets': [
            {
                'asset_id': r.asset_id,
                'type': r.asset_type,
                'staleness_hours': round(r.staleness_hours, 2),
                'status': r.status.value,
                'latest': r.latest_timestamp.isoformat() if r.latest_timestamp else None
            }
            for r in results
        ],
        'summary': {
            'healthy': sum(1 for r in results if r.status == HealthStatus.HEALTHY),
            'warning': sum(1 for r in results if r.status == HealthStatus.WARNING),
            'critical': sum(1 for r in results if r.status == HealthStatus.CRITICAL),
            'blackout': sum(1 for r in results if r.status == HealthStatus.BLACKOUT)
        }
    }

    # CEO-DIR-2026-EURUSD-PERMANENT-FIX: Alert deduplication state
    # Preserve existing last_alert_status when suppressing duplicate alerts
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT metadata->>'last_alert_status', metadata->>'last_alert_time'
                FROM fhq_governance.system_heartbeats
                WHERE component_name = 'PRICE_FRESHNESS'
            """)
            row = cur.fetchone()
            prev_alert_status = row[0] if row else None
            prev_alert_time = row[1] if row else None
    except:
        prev_alert_status = None
        prev_alert_time = None

    # Update logic:
    # 1. Alert sent -> record new alert state
    # 2. HEALTHY -> reset dedup state
    # 3. WARNING/CRITICAL/BLACKOUT but no alert -> preserve previous state
    if alert_sent:
        metadata['last_alert_status'] = overall_status
        metadata['last_alert_time'] = now_iso
    elif overall_status == 'HEALTHY':
        metadata['last_alert_status'] = 'HEALTHY'
        metadata['last_alert_time'] = None
    else:
        # Preserve previous alert state (for dedup)
        metadata['last_alert_status'] = prev_alert_status
        metadata['last_alert_time'] = prev_alert_time

    with conn.cursor() as cur:
        # Upsert heartbeat
        cur.execute("""
            INSERT INTO fhq_governance.system_heartbeats
                (component_name, heartbeat_type, last_heartbeat, status, metadata)
            VALUES ('PRICE_FRESHNESS', 'DATA_QUALITY', NOW(), %s, %s)
            ON CONFLICT (component_name)
            DO UPDATE SET
                last_heartbeat = NOW(),
                status = EXCLUDED.status,
                metadata = EXCLUDED.metadata
            RETURNING id
        """, (overall_status, json.dumps(metadata)))

        # Add unique constraint if not exists (will fail silently if exists)
        try:
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_heartbeats_component_unique
                ON fhq_governance.system_heartbeats(component_name)
            """)
        except:
            pass

        conn.commit()

    return overall_status


def generate_alert_message(results: List[AssetHealth]) -> Optional[str]:
    """Generate alert message for unhealthy assets."""
    unhealthy = [r for r in results if r.status in (HealthStatus.WARNING, HealthStatus.CRITICAL, HealthStatus.BLACKOUT)]

    if not unhealthy:
        return None

    # Build message
    lines = [
        "🚨 *PRICE FRESHNESS ALERT*",
        f"_CEO-DIR-2026-SITC P2 Heartbeat_",
        ""
    ]

    for asset in unhealthy:
        icon = {
            HealthStatus.WARNING: "⚠️",
            HealthStatus.CRITICAL: "🔴",
            HealthStatus.BLACKOUT: "⛔"
        }.get(asset.status, "❓")

        lines.append(f"{icon} *{asset.asset_id}* ({asset.asset_type})")
        lines.append(f"   Staleness: {asset.staleness_hours:.1f}h (threshold: {asset.threshold_hours:.0f}h)")
        if asset.latest_timestamp:
            lines.append(f"   Last update: {asset.latest_timestamp.strftime('%Y-%m-%d %H:%M')} UTC")
        lines.append("")

    lines.append(f"_Checked at {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC_")

    return "\n".join(lines)


def get_last_alert_status(conn) -> Optional[str]:
    """Get last alerted status to prevent duplicate alerts."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT metadata->>'last_alert_status', metadata->>'last_alert_time'
                FROM fhq_governance.system_heartbeats
                WHERE component_name = 'PRICE_FRESHNESS'
            """)
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
    except Exception as e:
        logger.warning(f"Could not get last alert status: {e}")
    return None


def should_send_alert(conn, current_status: str, results: List[AssetHealth]) -> bool:
    """
    Determine if alert should be sent (deduplication logic).

    CEO-DIR-2026-EURUSD-PERMANENT-FIX: Alert deduplication
    - Only alert on status CHANGE (e.g., HEALTHY -> WARNING)
    - OR if critical/blackout and >4h since last alert
    - Prevents spam during expected weekend staleness
    """
    if current_status == 'HEALTHY':
        return False

    last_status = get_last_alert_status(conn)

    # First alert for this condition
    if last_status is None or last_status == 'HEALTHY':
        logger.info(f"Alert dedup: Status changed from {last_status} to {current_status} - SENDING")
        return True

    # Status escalation (e.g., WARNING -> CRITICAL)
    severity_order = ['HEALTHY', 'WARNING', 'CRITICAL', 'BLACKOUT']
    if current_status in severity_order and last_status in severity_order:
        if severity_order.index(current_status) > severity_order.index(last_status):
            logger.info(f"Alert dedup: Escalated from {last_status} to {current_status} - SENDING")
            return True

    # Same status - don't spam
    logger.info(f"Alert dedup: Status unchanged ({current_status}) - SUPPRESSING duplicate alert")
    return False


def run_heartbeat() -> Dict[str, Any]:
    """Execute price freshness heartbeat check."""
    logger.info("=" * 60)
    logger.info("PRICE FRESHNESS HEARTBEAT")
    logger.info("CEO-DIR-2026-SITC-DATA-BLACKOUT-FIX-001 P2")
    logger.info("CEO-DIR-2026-EURUSD-PERMANENT-FIX: With alert deduplication")
    logger.info("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        # Check all assets
        results = check_price_freshness(conn)

        # Log results
        for r in results:
            icon = {
                HealthStatus.HEALTHY: "✓",
                HealthStatus.WARNING: "!",
                HealthStatus.CRITICAL: "X",
                HealthStatus.BLACKOUT: "⛔"
            }.get(r.status, "?")
            logger.info(f"  [{icon}] {r.asset_id}: {r.staleness_hours:.1f}h ({r.status.value})")

        # Determine overall status first
        statuses = [r.status for r in results]
        if HealthStatus.BLACKOUT in statuses:
            overall_status = 'BLACKOUT'
        elif HealthStatus.CRITICAL in statuses:
            overall_status = 'CRITICAL'
        elif HealthStatus.WARNING in statuses:
            overall_status = 'WARNING'
        else:
            overall_status = 'HEALTHY'

        logger.info(f"\nOverall Status: {overall_status}")

        # Send alert if needed (with deduplication)
        alert_sent = False
        if should_send_alert(conn, overall_status, results):
            message = generate_alert_message(results)
            if message:
                alert_sent = send_telegram_alert(message)
                if alert_sent:
                    logger.info("Telegram alert sent successfully")

        # Log heartbeat to database (after alert decision, to store dedup state)
        log_heartbeat(conn, results, alert_sent=alert_sent)

        # Build result
        result = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': overall_status,
            'assets_checked': len(results),
            'healthy': sum(1 for r in results if r.status == HealthStatus.HEALTHY),
            'warning': sum(1 for r in results if r.status == HealthStatus.WARNING),
            'critical': sum(1 for r in results if r.status == HealthStatus.CRITICAL),
            'blackout': sum(1 for r in results if r.status == HealthStatus.BLACKOUT),
            'alert_sent': alert_sent,
            'alert_suppressed': overall_status != 'HEALTHY' and not alert_sent,
            'details': [
                {
                    'asset_id': r.asset_id,
                    'staleness_hours': round(r.staleness_hours, 2),
                    'status': r.status.value
                }
                for r in results
            ]
        }

        logger.info(f"\nHeartbeat complete: {result['healthy']}/{len(results)} healthy")
        if result.get('alert_suppressed'):
            logger.info("(Alert suppressed - duplicate condition)")

        return result

    finally:
        conn.close()


def main():
    """Main entry point."""
    result = run_heartbeat()

    # Write evidence file
    evidence_path = f"evidence/PRICE_HEARTBEAT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs('evidence', exist_ok=True)
    with open(evidence_path, 'w') as f:
        json.dump(result, f, indent=2)

    logger.info(f"Evidence: {evidence_path}")

    # Return success if no blackout
    return result['status'] != 'BLACKOUT'


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
