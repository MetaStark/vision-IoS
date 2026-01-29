#!/usr/bin/env python3
"""
Mechanism Alpha Trigger Daemon
==============================

Purpose: Scan latest indicator data for Alpha Satellite trigger conditions
         and write to fhq_learning.trigger_events.

Trigger conditions (from hypothesis_canon.falsification_criteria):
  TEST A (Vol Squeeze):    BBW < 10th percentile per-asset
  TEST B (Regime Align):   RSI_14 > 70 AND regime = BULL (mapped from STRONG_BULL)
  TEST C (Mean Revert):    close > bb_upper AND regime = NEUTRAL
  TEST D (Breakout):       close > bb_upper AND bbw > bbw_p50 AND regime in (BULL, NEUTRAL)
  TEST E (Trend Pullback): RSI_14 < 35 AND regime = BULL
  TEST F (Panic Bottom):   RSI_14 < 20 AND regime in (BEAR, STRESS)

Authority: CEO Phase 2 Runtime Fabrication Directive
Contract: EC-003_2026_PRODUCTION

Usage:
    python mechanism_alpha_trigger.py              # Run daemon (15 min interval)
    python mechanism_alpha_trigger.py --once       # Single cycle then exit
    python mechanism_alpha_trigger.py --dry-run    # Log triggers without INSERT
    python mechanism_alpha_trigger.py --interval N # Override interval (seconds)

Author: STIG (EC-003)
Date: 2026-01-29
"""

import os
import sys
import json
import uuid
import time
import signal
import hashlib
import logging
import argparse
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='[ALPHA_TRIGGER] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/mechanism_alpha_trigger.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('AlphaTrigger')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

DAEMON_NAME = 'mechanism_alpha_trigger'
DEFAULT_INTERVAL = 900  # 15 minutes

# Regime mapping: blueprint terms → DB sovereign_regime values
REGIME_MAP = {
    "STRONG_BULL": "BULL",
    "WEAK_BEAR": "BEAR",
    "WEAK_BULL": "NEUTRAL",
    "LOW_VOL": "NEUTRAL",
    # Direct mappings (already in DB format)
    "NEUTRAL": "NEUTRAL",
    "BULL": "BULL",
    "BEAR": "BEAR",
    "STRESS": "STRESS",
}

BLOCKED_DEFCON = {'RED', 'BLACK', 'ORANGE'}

# Shutdown signal
SHUTDOWN = False

def handle_signal(signum, frame):
    global SHUTDOWN
    logger.info(f"Received signal {signum}, shutting down...")
    SHUTDOWN = True

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")


def check_gate(cur):
    """Check Phase 2 gate is OPEN."""
    cur.execute("""
        SELECT status FROM fhq_meta.gate_status
        WHERE gate_id = 'PHASE2_HYPOTHESIS_SWARM_V1.1'
    """)
    row = cur.fetchone()
    if not row or row['status'] != 'OPEN':
        return False
    return True


def check_defcon(cur):
    """Check DEFCON is not in blocked state. Returns current level."""
    cur.execute("""
        SELECT defcon_level FROM fhq_governance.defcon_state
        WHERE is_current = true
    """)
    row = cur.fetchone()
    if not row:
        return 'UNKNOWN'
    return row['defcon_level']


def heartbeat(cur, status='RUNNING', metadata=None):
    """Register daemon heartbeat."""
    cur.execute("""
        INSERT INTO fhq_monitoring.daemon_health
            (daemon_name, status, last_heartbeat, metadata, expected_interval_minutes, is_critical)
        VALUES (%s, %s, NOW(), %s, %s, true)
        ON CONFLICT (daemon_name) DO UPDATE SET
            status = EXCLUDED.status,
            last_heartbeat = NOW(),
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
    """, (DAEMON_NAME, status, json.dumps(metadata or {}, default=decimal_default), 15))


def get_active_experiments(cur):
    """Fetch active Alpha Satellite experiments with their blueprint data."""
    cur.execute("""
        SELECT
            er.experiment_id,
            er.experiment_code,
            er.hypothesis_id,
            hc.hypothesis_code,
            hc.falsification_criteria,
            hc.expected_direction,
            hc.expected_timeframe_hours
        FROM fhq_learning.experiment_registry er
        JOIN fhq_learning.hypothesis_canon hc ON er.hypothesis_id = hc.canon_id
        WHERE er.status = 'RUNNING'
          AND er.experiment_code LIKE 'EXP_ALPHA_SAT_%%'
        ORDER BY er.experiment_code
    """)
    return cur.fetchall()


def get_crypto_universe(cur):
    """Get distinct crypto assets from volatility table."""
    cur.execute("""
        SELECT DISTINCT listing_id FROM fhq_indicators.volatility
        WHERE listing_id LIKE '%%-USD'
        ORDER BY listing_id
    """)
    return [r['listing_id'] for r in cur.fetchall()]


def get_latest_regime(cur, asset_id):
    """Get latest sovereign regime for an asset."""
    cur.execute("""
        SELECT sovereign_regime, engine_version, timestamp
        FROM fhq_perception.sovereign_regime_state_v4
        WHERE asset_id = %s
        ORDER BY timestamp DESC
        LIMIT 1
    """, (asset_id,))
    return cur.fetchone()


def get_latest_volatility(cur, asset_id):
    """Get latest volatility row for an asset."""
    cur.execute("""
        SELECT volatility_id, signal_date, listing_id,
               bb_upper, bb_middle, bb_lower, atr_14, bbw
        FROM fhq_indicators.volatility
        WHERE listing_id = %s AND bbw IS NOT NULL
        ORDER BY signal_date DESC
        LIMIT 1
    """, (asset_id,))
    return cur.fetchone()


def get_latest_momentum(cur, asset_id):
    """Get latest momentum row for an asset."""
    cur.execute("""
        SELECT momentum_id, signal_date, listing_id, rsi_14
        FROM fhq_indicators.momentum
        WHERE listing_id = %s AND rsi_14 IS NOT NULL
        ORDER BY signal_date DESC
        LIMIT 1
    """, (asset_id,))
    return cur.fetchone()


def get_latest_price(cur, asset_id, signal_date=None):
    """Get latest price for an asset, optionally matching a signal_date."""
    if signal_date:
        cur.execute("""
            SELECT id, listing_id, date, close
            FROM fhq_data.price_series
            WHERE listing_id = %s AND date = %s
            LIMIT 1
        """, (asset_id, signal_date))
        row = cur.fetchone()
        if row:
            return row
    # Fallback: latest available price
    cur.execute("""
        SELECT id, listing_id, date, close
        FROM fhq_data.price_series
        WHERE listing_id = %s
        ORDER BY date DESC
        LIMIT 1
    """, (asset_id,))
    return cur.fetchone()


def compute_bbw_percentile_10(cur, asset_id):
    """Compute 10th percentile of BBW for an asset."""
    cur.execute("""
        SELECT percentile_cont(0.10) WITHIN GROUP (ORDER BY bbw) as p10
        FROM fhq_indicators.volatility
        WHERE listing_id = %s AND bbw IS NOT NULL
    """, (asset_id,))
    row = cur.fetchone()
    return float(row['p10']) if row and row['p10'] is not None else None


def build_context_snapshot(regime_row, defcon_level, vol_state=None):
    """Build context snapshot for trigger event."""
    context = {
        "regime": regime_row['sovereign_regime'] if regime_row else "UNKNOWN",
        "regime_model_version": regime_row['engine_version'] if regime_row else "UNKNOWN",
        "regime_timestamp": regime_row['timestamp'].isoformat() if regime_row and regime_row['timestamp'] else None,
        "vol_state": vol_state or "UNKNOWN",
        "vol_model_version": "ios017_kc_bb_1.0",
        "macro_state": "UNKNOWN",
        "macro_model_version": "NA",
        "defcon_level": defcon_level,
        "capture_timestamp": datetime.now(timezone.utc).isoformat(),
        "data_sources": {
            "regime_source": "fhq_perception.sovereign_regime_state_v4",
            "vol_source": "fhq_indicators.volatility",
            "momentum_source": "fhq_indicators.momentum",
            "price_source": "fhq_data.price_series",
            "macro_source": "NA"
        }
    }
    return context


def compute_context_hash(context):
    """Compute SHA256 hash of context snapshot (canonical key order)."""
    canonical_keys = sorted(context.keys())
    canonical = {k: context[k] for k in canonical_keys}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, default=str).encode()).hexdigest()


def classify_vol_state(bbw, bbw_p10):
    """Classify vol state based on BBW vs percentile."""
    if bbw_p10 is None:
        return "UNKNOWN"
    if bbw < bbw_p10:
        return "SQUEEZE"
    elif bbw < bbw_p10 * 3:
        return "LOW"
    elif bbw < bbw_p10 * 6:
        return "NORMAL"
    else:
        return "EXPANDED"


def evaluate_test_a(vol_row, bbw_p10):
    """TEST A: BBW < 10th percentile (Vol Squeeze)."""
    if vol_row is None or bbw_p10 is None:
        return False, {}
    bbw = float(vol_row['bbw'])
    triggered = bbw < bbw_p10
    indicators = {
        'bbw': bbw,
        'bbw_percentile_10': bbw_p10,
        'atr_14': float(vol_row['atr_14']) if vol_row['atr_14'] else None,
        'bb_upper': float(vol_row['bb_upper']) if vol_row['bb_upper'] else None,
        'bb_middle': float(vol_row['bb_middle']) if vol_row['bb_middle'] else None,
        'bb_lower': float(vol_row['bb_lower']) if vol_row['bb_lower'] else None,
    }
    return triggered, indicators


def evaluate_test_b(mom_row, regime_row):
    """TEST B: RSI_14 > 70 AND regime = BULL (mapped from STRONG_BULL)."""
    if mom_row is None or regime_row is None:
        return False, {}
    rsi = float(mom_row['rsi_14'])
    db_regime = regime_row['sovereign_regime']
    required_regime = REGIME_MAP.get('STRONG_BULL', 'BULL')
    rsi_triggered = rsi > 70
    regime_match = db_regime == required_regime
    triggered = rsi_triggered and regime_match
    indicators = {
        'rsi_14': rsi,
        'regime': db_regime,
        'regime_filter': 'STRONG_BULL',
        'regime_mapped_to': required_regime,
        'regime_match': regime_match,
    }
    return triggered, indicators


def evaluate_test_c(vol_row, price_row, regime_row):
    """TEST C: close > bb_upper AND regime = NEUTRAL."""
    if vol_row is None or price_row is None or regime_row is None:
        return False, {}
    close = float(price_row['close'])
    bb_upper = float(vol_row['bb_upper']) if vol_row['bb_upper'] else None
    db_regime = regime_row['sovereign_regime']
    if bb_upper is None:
        return False, {}
    price_above = close > bb_upper
    regime_match = db_regime == 'NEUTRAL'
    triggered = price_above and regime_match
    indicators = {
        'close': close,
        'bb_upper': bb_upper,
        'bb_middle': float(vol_row['bb_middle']) if vol_row['bb_middle'] else None,
        'atr_14': float(vol_row['atr_14']) if vol_row['atr_14'] else None,
        'regime': db_regime,
        'regime_filter': 'NEUTRAL',
        'regime_match': regime_match,
    }
    return triggered, indicators


def evaluate_test_d(vol_row, price_row, regime_row, bbw_p50):
    """TEST D: close > bb_upper AND bbw > bbw_p50 AND regime in (BULL, NEUTRAL)."""
    if vol_row is None or price_row is None or regime_row is None or bbw_p50 is None:
        return False, {}
    close = float(price_row['close'])
    bb_upper = float(vol_row['bb_upper']) if vol_row['bb_upper'] else None
    bbw = float(vol_row['bbw']) if vol_row['bbw'] else None
    db_regime = regime_row['sovereign_regime']
    if bb_upper is None or bbw is None:
        return False, {}
    price_above = close > bb_upper
    vol_expanding = bbw > bbw_p50
    regime_match = db_regime in ('BULL', 'NEUTRAL')
    triggered = price_above and vol_expanding and regime_match
    indicators = {
        'close': close,
        'bb_upper': bb_upper,
        'bb_middle': float(vol_row['bb_middle']) if vol_row['bb_middle'] else None,
        'bbw': bbw,
        'bbw_percentile_50': bbw_p50,
        'atr_14': float(vol_row['atr_14']) if vol_row['atr_14'] else None,
        'regime': db_regime,
        'regime_filter': 'BULL_OR_NEUTRAL',
        'regime_match': regime_match,
    }
    return triggered, indicators


def evaluate_test_e(mom_row, regime_row, vol_row):
    """TEST E: RSI_14 < 35 AND regime = BULL (Trend Pullback)."""
    if mom_row is None or regime_row is None:
        return False, {}
    rsi = float(mom_row['rsi_14'])
    db_regime = regime_row['sovereign_regime']
    rsi_oversold = rsi < 35
    regime_match = db_regime == 'BULL'
    triggered = rsi_oversold and regime_match
    indicators = {
        'rsi_14': rsi,
        'macd_histogram': float(mom_row['macd_histogram']) if mom_row.get('macd_histogram') else None,
        'atr_14': float(vol_row['atr_14']) if vol_row and vol_row.get('atr_14') else None,
        'regime': db_regime,
        'regime_filter': 'BULL',
        'regime_match': regime_match,
    }
    return triggered, indicators


def evaluate_test_f(mom_row, regime_row, vol_row):
    """TEST F: RSI_14 < 20 AND regime in (BEAR, STRESS) (Panic Bottom)."""
    if mom_row is None or regime_row is None:
        return False, {}
    rsi = float(mom_row['rsi_14'])
    db_regime = regime_row['sovereign_regime']
    rsi_panic = rsi < 20
    regime_match = db_regime in ('BEAR', 'STRESS')
    triggered = rsi_panic and regime_match
    indicators = {
        'rsi_14': rsi,
        'stoch_k': float(mom_row['stoch_k']) if mom_row.get('stoch_k') else None,
        'atr_14': float(vol_row['atr_14']) if vol_row and vol_row.get('atr_14') else None,
        'regime': db_regime,
        'regime_filter': 'BEAR_OR_STRESS',
        'regime_match': regime_match,
    }
    return triggered, indicators


def compute_bbw_percentile_50(cur, asset_id):
    """Compute 50th percentile of BBW for an asset."""
    cur.execute("""
        SELECT percentile_cont(0.50) WITHIN GROUP (ORDER BY bbw) as p50
        FROM fhq_indicators.volatility
        WHERE listing_id = %s AND bbw IS NOT NULL
    """, (asset_id,))
    row = cur.fetchone()
    return float(row['p50']) if row and row['p50'] is not None else None


def check_freshness(signal_date, historical=False):
    """Check if signal_date is within 24h of now. Returns True if fresh."""
    if historical:
        return True
    if signal_date is None:
        return False
    now = datetime.now(timezone.utc)
    # signal_date may be date or datetime
    if not isinstance(signal_date, datetime):
        signal_date = datetime(signal_date.year, signal_date.month, signal_date.day, tzinfo=timezone.utc)
    elif hasattr(signal_date, 'tzinfo') and signal_date.tzinfo is None:
        signal_date = signal_date.replace(tzinfo=timezone.utc)
    age = now - signal_date
    return age < timedelta(hours=24)


def run_cycle(dry_run=False, historical=False):
    """Execute one trigger detection cycle."""
    conn = get_db_connection()
    conn.autocommit = False
    triggers_found = 0
    triggers_inserted = 0
    assets_scanned = 0

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Gate check
            if not check_gate(cur):
                logger.warning("GATE CLOSED: PHASE2_HYPOTHESIS_SWARM_V1.1 is not OPEN. Skipping cycle.")
                heartbeat(cur, status='DEGRADED', metadata={'reason': 'GATE_CLOSED'})
                conn.commit()
                return 0, 0, 0

            # DEFCON check
            defcon = check_defcon(cur)
            if defcon in BLOCKED_DEFCON:
                logger.warning(f"DEFCON {defcon}: Blocked. Skipping cycle.")
                heartbeat(cur, status='DEGRADED', metadata={'reason': f'DEFCON_{defcon}'})
                conn.commit()
                return 0, 0, 0

            # Load active experiments
            experiments = get_active_experiments(cur)
            if not experiments:
                logger.warning("No active experiments found. Skipping cycle.")
                heartbeat(cur, status='DEGRADED', metadata={'reason': 'NO_EXPERIMENTS'})
                conn.commit()
                return 0, 0, 0
            logger.info(f"Active experiments: {len(experiments)}")

            # Get crypto universe
            universe = get_crypto_universe(cur)
            logger.info(f"Asset universe: {len(universe)} crypto assets")

            # DATA_LAG guard: block entire cycle if MAX(signal_date) > 24h stale
            if not historical:
                cur.execute("""
                    SELECT MAX(signal_date) as max_date
                    FROM fhq_indicators.volatility
                    WHERE listing_id LIKE '%%-USD'
                """)
                max_row = cur.fetchone()
                if max_row and max_row['max_date']:
                    max_date = max_row['max_date']
                    # signal_date is date type; convert to datetime for comparison
                    if not isinstance(max_date, datetime):
                        max_signal = datetime(max_date.year, max_date.month, max_date.day, tzinfo=timezone.utc)
                    elif hasattr(max_date, 'tzinfo') and max_date.tzinfo is None:
                        max_signal = max_date.replace(tzinfo=timezone.utc)
                    else:
                        max_signal = max_date
                    data_age = datetime.now(timezone.utc) - max_signal
                    if data_age > timedelta(hours=24):
                        logger.error(f"DATA_LAG BLOCK: MAX(signal_date) = {max_row['max_date']}, "
                                     f"age = {data_age}. Data stale > 24h. Cycle BLOCKED.")
                        heartbeat(cur, status='DEGRADED', metadata={
                            'reason': 'DATA_LAG',
                            'max_signal_date': str(max_row['max_date']),
                            'data_age_hours': round(data_age.total_seconds() / 3600, 1),
                        })
                        conn.commit()
                        return 0, 0, 0

            # Pre-compute BBW percentiles (for TEST A + D)
            bbw_p10_cache = {}
            bbw_p50_cache = {}
            for asset_id in universe:
                bbw_p10_cache[asset_id] = compute_bbw_percentile_10(cur, asset_id)
                bbw_p50_cache[asset_id] = compute_bbw_percentile_50(cur, asset_id)

            # Scan each experiment x asset
            for exp in experiments:
                test_code = exp['falsification_criteria'].get('measurement_schema', {}).get('test_code', '')
                logger.info(f"Scanning {exp['experiment_code']} (test={test_code})")

                for asset_id in universe:
                    assets_scanned += 1

                    # Get latest data
                    regime_row = get_latest_regime(cur, asset_id)
                    vol_row = get_latest_volatility(cur, asset_id)
                    mom_row = get_latest_momentum(cur, asset_id)

                    # Freshness guard: skip stale data unless --historical
                    if test_code in ('ALPHA_SAT_A', 'ALPHA_SAT_C', 'ALPHA_SAT_D'):
                        freshness_date = vol_row['signal_date'] if vol_row else None
                    else:
                        freshness_date = mom_row['signal_date'] if mom_row else None
                    if not check_freshness(freshness_date, historical=historical):
                        continue

                    # Evaluate trigger based on test type
                    triggered = False
                    trigger_indicators = {}

                    if test_code == 'ALPHA_SAT_A':
                        bbw_p10 = bbw_p10_cache.get(asset_id)
                        triggered, trigger_indicators = evaluate_test_a(vol_row, bbw_p10)
                    elif test_code == 'ALPHA_SAT_B':
                        triggered, trigger_indicators = evaluate_test_b(mom_row, regime_row)
                    elif test_code == 'ALPHA_SAT_C':
                        signal_date = vol_row['signal_date'] if vol_row else None
                        price_row = get_latest_price(cur, asset_id, signal_date)
                        triggered, trigger_indicators = evaluate_test_c(vol_row, price_row, regime_row)
                    elif test_code == 'ALPHA_SAT_D':
                        signal_date = vol_row['signal_date'] if vol_row else None
                        price_row = get_latest_price(cur, asset_id, signal_date)
                        bbw_p50 = bbw_p50_cache.get(asset_id)
                        triggered, trigger_indicators = evaluate_test_d(vol_row, price_row, regime_row, bbw_p50)
                    elif test_code == 'ALPHA_SAT_E':
                        triggered, trigger_indicators = evaluate_test_e(mom_row, regime_row, vol_row)
                    elif test_code == 'ALPHA_SAT_F':
                        triggered, trigger_indicators = evaluate_test_f(mom_row, regime_row, vol_row)

                    if not triggered:
                        continue

                    triggers_found += 1

                    # Get entry price
                    price_row = get_latest_price(cur, asset_id)
                    if not price_row:
                        logger.warning(f"  No price data for {asset_id}. Skipping trigger.")
                        continue
                    entry_price = price_row['close']
                    trigger_indicators['entry_price'] = float(entry_price)

                    # Build context
                    vol_state = classify_vol_state(
                        float(vol_row['bbw']) if vol_row and vol_row['bbw'] else 0,
                        bbw_p10_cache.get(asset_id)
                    ) if vol_row else "UNKNOWN"
                    context = build_context_snapshot(regime_row, defcon, vol_state)
                    context_hash = compute_context_hash(context)

                    # Event timestamp = signal_date of the indicator that triggered
                    if test_code in ('ALPHA_SAT_B', 'ALPHA_SAT_E', 'ALPHA_SAT_F') and mom_row:
                        event_ts = mom_row['signal_date']
                    elif vol_row:
                        event_ts = vol_row['signal_date']
                    else:
                        event_ts = datetime.now(timezone.utc)

                    if dry_run:
                        logger.info(f"  [DRY_RUN] TRIGGER: {asset_id} test={test_code} "
                                    f"entry={entry_price} indicators={trigger_indicators}")
                        continue

                    # INSERT with dedup
                    cur.execute("""
                        INSERT INTO fhq_learning.trigger_events (
                            experiment_id, asset_id, event_timestamp,
                            trigger_indicators, entry_price,
                            price_source_table, price_source_row_id,
                            context_snapshot_hash, context_details,
                            created_by
                        ) VALUES (
                            %s, %s, %s,
                            %s, %s,
                            'fhq_data.price_series', %s,
                            %s, %s,
                            'STIG'
                        )
                        ON CONFLICT (experiment_id, asset_id, event_timestamp) DO NOTHING
                        RETURNING trigger_event_id
                    """, (
                        str(exp['experiment_id']), asset_id, event_ts,
                        json.dumps(trigger_indicators, default=decimal_default), entry_price,
                        str(price_row['id']) if price_row.get('id') else None,
                        context_hash, json.dumps(context, default=decimal_default),
                    ))
                    result = cur.fetchone()
                    if result:
                        triggers_inserted += 1
                        logger.info(f"  TRIGGER INSERTED: {asset_id} test={test_code} "
                                    f"entry={entry_price} id={result['trigger_event_id']}")
                    else:
                        logger.info(f"  TRIGGER DEDUPED (already exists): {asset_id} test={test_code}")

            # Heartbeat
            heartbeat(cur, status='HEALTHY', metadata={
                'cycle_time': datetime.now(timezone.utc).isoformat(),
                'triggers_found': triggers_found,
                'triggers_inserted': triggers_inserted,
                'assets_scanned': assets_scanned,
                'defcon': defcon,
                'dry_run': dry_run,
            })

            # Guard 1: Minimum signal rate
            cur.execute("""
                SELECT COUNT(*) as cnt FROM fhq_learning.trigger_events
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)
            recent_count = cur.fetchone()['cnt']
            if recent_count < 5 and not dry_run:
                logger.warning(f"GUARD: TRIGGER_SENSITIVITY_TOO_LOW - Only {recent_count} triggers in 24h")

            conn.commit()

    except Exception as e:
        conn.rollback()
        logger.error(f"Cycle failed: {e}", exc_info=True)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                heartbeat(cur, status='UNHEALTHY', metadata={'error': str(e)})
                conn.commit()
        except Exception:
            pass
        raise
    finally:
        conn.close()

    return triggers_found, triggers_inserted, assets_scanned


def run_daemon(interval, dry_run=False, historical=False):
    """Run continuous daemon loop."""
    logger.info(f"Starting daemon (interval={interval}s, dry_run={dry_run}, historical={historical})")
    cycle = 0

    while not SHUTDOWN:
        cycle += 1
        logger.info(f"=== Cycle {cycle} ===")
        try:
            found, inserted, scanned = run_cycle(dry_run=dry_run, historical=historical)
            logger.info(f"Cycle {cycle} complete: found={found} inserted={inserted} scanned={scanned}")
        except Exception as e:
            logger.error(f"Cycle {cycle} failed: {e}")

        # Granular sleep (check shutdown every second)
        for _ in range(interval):
            if SHUTDOWN:
                break
            time.sleep(1)

    logger.info("Daemon shutdown complete.")


def main():
    parser = argparse.ArgumentParser(description='Alpha Satellite Trigger Daemon')
    parser.add_argument('--dry-run', action='store_true', help='Log triggers without INSERT')
    parser.add_argument('--once', action='store_true', help='Single cycle then exit')
    parser.add_argument('--interval', type=int, default=DEFAULT_INTERVAL, help='Cycle interval in seconds')
    parser.add_argument('--historical', action='store_true', help='Allow stale data (skip freshness guard)')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("MECHANISM ALPHA TRIGGER DAEMON")
    logger.info(f"Mode: {'DRY_RUN' if args.dry_run else 'LIVE'}")
    logger.info(f"Interval: {args.interval}s")
    logger.info(f"Once: {args.once}")
    logger.info("=" * 60)

    if args.once:
        found, inserted, scanned = run_cycle(dry_run=args.dry_run, historical=args.historical)
        logger.info(f"Single cycle complete: found={found} inserted={inserted} scanned={scanned}")
        return 0

    run_daemon(args.interval, dry_run=args.dry_run, historical=args.historical)
    return 0


if __name__ == '__main__':
    sys.exit(main())
