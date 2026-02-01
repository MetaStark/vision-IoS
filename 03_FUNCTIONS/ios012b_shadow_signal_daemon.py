#!/usr/bin/env python3
"""
IoS-012-B SHADOW SIGNAL CAPTURE DAEMON
======================================
Directive: CEO-DIR-2026-106
Classification: SHADOW_ONLY (Hindsight Firewall until 2026-02-02)
Date: 2026-01-19

Monitors for STRESS@99%+ signals and logs inverted signals to shadow table.
DOES NOT EXECUTE - Shadow mode only. Daily measurement, no execution.

CRITICAL: This daemon measures, it does not act.

Run modes:
  --capture    Capture current STRESS@99%+ signals and log inversions
  --evaluate   Evaluate outcomes for previously captured signals
  --health     Run health check
  --report     Generate daily shadow performance report

Scheduled execution:
  22:30 UTC daily (after IoS-003 regime update at 22:05)
"""

import os
import sys
import json
import uuid
import hashlib
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[IoS-012-B-SHADOW] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Canonical inversion universe (10 equity tickers)
CANONICAL_UNIVERSE = [
    'ADBE', 'ADSK', 'AIG', 'AZO', 'GIS',
    'HNR1.DE', 'INTU', 'LEN', 'NOW', 'PGR'
]

# Trigger conditions
REGIME_TRIGGER = 'STRESS'
CONFIDENCE_THRESHOLD = 0.99
ASSET_CLASS_FILTER = 'EQUITY'

# Hindsight firewall
NON_ELIGIBILITY_END = date(2026, 2, 2)
SHADOW_MODE = True  # HARDCODED until 2026-02-02


@dataclass
class InversionCapture:
    """A captured inversion signal."""
    capture_id: str
    source_score_id: str
    ticker: str
    source_regime: str
    source_confidence: float
    source_direction: str
    inverted_direction: str
    capture_timestamp: datetime
    underlying_price: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'capture_id': self.capture_id,
            'source_score_id': self.source_score_id,
            'ticker': self.ticker,
            'source_regime': self.source_regime,
            'source_confidence': self.source_confidence,
            'source_direction': self.source_direction,
            'inverted_direction': self.inverted_direction,
            'capture_timestamp': self.capture_timestamp.isoformat(),
            'underlying_price': self.underlying_price
        }


class ShadowSignalDaemon:
    """
    IoS-012-B Shadow Signal Capture Daemon

    Monitors Brier ledger for STRESS@99%+ equity signals,
    inverts them, and logs to shadow tracking table.

    Shadow mode only - no execution until 2026-02-02.
    """

    def __init__(self):
        self.conn = None
        self._validate_hindsight_firewall()

    def _validate_hindsight_firewall(self):
        """Validate hindsight firewall compliance."""
        today = date.today()
        if today < NON_ELIGIBILITY_END:
            days_remaining = (NON_ELIGIBILITY_END - today).days
            logger.info(f"HINDSIGHT_FIREWALL: Shadow mode enforced. {days_remaining} days until eligibility.")
        else:
            logger.warning("Hindsight firewall period ended. Live execution may be enabled.")

    def connect(self):
        """Connect to database."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Connected to database")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    # =========================================================================
    # SIGNAL CAPTURE (22:30 UTC daily)
    # =========================================================================

    def capture_stress_signals(self) -> List[InversionCapture]:
        """
        Capture STRESS@99%+ equity signals from recent Brier ledger.

        Query logic:
        - regime = 'STRESS'
        - forecast_probability >= 0.99
        - asset_id IN canonical_universe
        - Recent signals (last 7 days for shadow capture)
        """
        captures = []

        # Query for STRESS@99%+ signals in canonical universe
        # Note: In production, we'd filter by today's signals
        # For shadow mode, we capture recent historical data to build the dataset
        query = """
            SELECT
                score_id,
                asset_id,
                regime,
                forecast_probability,
                actual_outcome,
                forecast_timestamp,
                created_at
            FROM fhq_governance.brier_score_ledger
            WHERE regime = %s
              AND forecast_probability >= %s
              AND asset_id = ANY(%s)
              AND created_at >= NOW() - INTERVAL '7 days'
            ORDER BY created_at DESC
            LIMIT 100
        """

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (REGIME_TRIGGER, CONFIDENCE_THRESHOLD, CANONICAL_UNIVERSE))
            rows = cur.fetchall()

        logger.info(f"Found {len(rows)} STRESS@99%+ signals in canonical universe")

        for row in rows:
            # KRITISK FIX (CEO-DIR-2026-106 P0):
            # STRESS regime predikerer NEDSIDE (DOWN), ikke opp
            # forecast_probability er konfidens for REGIME, ikke prisretning
            # Høy sannsynlighet STRESS = sterk DOWN-prediksjon
            if row['regime'] == 'STRESS':
                source_direction = 'DOWN'  # STRESS predikerer nedside
                inverted_direction = 'UP'   # Invertert = oppside (BUY)
            else:
                # For andre regimer (f.eks. BULL), høy prob = UP prediction
                source_direction = 'UP' if row['forecast_probability'] > 0.5 else 'DOWN'
                inverted_direction = 'DOWN' if source_direction == 'UP' else 'UP'

            capture = InversionCapture(
                capture_id=str(uuid.uuid4()),
                source_score_id=str(row['score_id']),
                ticker=row['asset_id'],
                source_regime=row['regime'],
                source_confidence=float(row['forecast_probability']),
                source_direction=source_direction,
                inverted_direction=inverted_direction,
                capture_timestamp=datetime.now(timezone.utc)
            )

            # Get underlying price
            capture.underlying_price = self._get_current_price(row['asset_id'])

            captures.append(capture)
            logger.info(f"CAPTURE: {capture.ticker} {source_direction} -> {inverted_direction} @ {capture.source_confidence:.4f}")

        return captures

    def _get_current_price(self, ticker: str) -> Optional[float]:
        """Get current price for ticker."""
        query = """
            SELECT close FROM fhq_market.prices
            WHERE canonical_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (ticker,))
                row = cur.fetchone()
                return float(row[0]) if row else None
        except Exception as e:
            logger.warning(f"Could not get price for {ticker}: {e}")
            # Rollback to clear transaction error state
            self.conn.rollback()
            return None

    def log_captures_to_shadow(self, captures: List[InversionCapture]) -> int:
        """
        Log captured inversions to shadow tracking table.

        SHADOW MODE ONLY - No execution.
        """
        if not captures:
            logger.info("No captures to log")
            return 0

        logged = 0
        for capture in captures:
            try:
                self._insert_shadow_record(capture)
                logged += 1
            except Exception as e:
                logger.error(f"Failed to log capture {capture.ticker}: {e}")
                self.conn.rollback()

        logger.info(f"Logged {logged}/{len(captures)} captures to shadow table")
        return logged

    def _insert_shadow_record(self, capture: InversionCapture):
        """Insert shadow record to database."""
        query = """
            INSERT INTO fhq_alpha.inversion_overlay_shadow (
                overlay_id,
                source_signal_id,
                source_regime,
                source_confidence,
                source_direction,
                inverted_direction,
                inversion_trigger,
                ticker,
                strategy_type,
                entry_timestamp,
                entry_price_underlying,
                is_shadow,
                evidence_hash
            ) VALUES (
                %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s
            )
        """

        evidence_hash = hashlib.sha256(
            json.dumps(capture.to_dict(), sort_keys=True).encode()
        ).hexdigest()[:32]

        with self.conn.cursor() as cur:
            cur.execute(query, (
                capture.capture_id,
                capture.source_score_id,
                capture.source_regime,
                capture.source_confidence,
                capture.source_direction,
                capture.inverted_direction,
                'STRESS_99PCT_EQUITY',
                capture.ticker,
                'DIRECTION_ONLY',  # No options in shadow mode
                capture.capture_timestamp,
                capture.underlying_price,
                f"sha256:{evidence_hash}"
            ))
        self.conn.commit()

    # =========================================================================
    # OUTCOME EVALUATION (04:00 UTC daily, T+1)
    # =========================================================================

    def evaluate_outcomes(self) -> Dict[str, Any]:
        """
        Evaluate outcomes for signals captured T-1.

        Checks if market moved in inverted direction.
        """
        # Get yesterday's unevaluated captures
        query = """
            SELECT
                overlay_id,
                ticker,
                source_direction,
                inverted_direction,
                entry_price_underlying,
                entry_timestamp
            FROM fhq_alpha.inversion_overlay_shadow
            WHERE is_shadow = TRUE
              AND actual_outcome IS NULL
              AND DATE(entry_timestamp) < CURRENT_DATE
        """

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            pending = cur.fetchall()

        logger.info(f"Evaluating outcomes for {len(pending)} pending signals")

        results = {
            'evaluated': 0,
            'correct_inversions': 0,
            'incorrect_inversions': 0,
            'no_price_data': 0
        }

        for row in pending:
            outcome = self._evaluate_single_outcome(row)
            if outcome is None:
                results['no_price_data'] += 1
            elif outcome:
                results['correct_inversions'] += 1
            else:
                results['incorrect_inversions'] += 1
            results['evaluated'] += 1

        # Calculate hit rate
        total_with_outcome = results['correct_inversions'] + results['incorrect_inversions']
        if total_with_outcome > 0:
            results['inverted_hit_rate'] = results['correct_inversions'] / total_with_outcome
        else:
            results['inverted_hit_rate'] = None

        logger.info(f"Evaluation complete: {results}")
        return results

    def _evaluate_single_outcome(self, row: Dict) -> Optional[bool]:
        """
        Evaluate single signal outcome.

        Returns:
            True if inverted direction was correct
            False if inverted direction was wrong
            None if no price data available
        """
        ticker = row['ticker']
        entry_price = row['entry_price_underlying']
        inverted_direction = row['inverted_direction']
        entry_date = row['entry_timestamp'].date()

        if entry_price is None:
            return None

        # Get T+1 price
        t1_date = entry_date + timedelta(days=1)
        query = """
            SELECT close FROM fhq_market.prices
            WHERE canonical_id = %s AND DATE(timestamp) = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (ticker, t1_date))
                t1_row = cur.fetchone()
        except Exception as e:
            logger.warning(f"Could not get T+1 price for {ticker}: {e}")
            self.conn.rollback()
            return None

        if not t1_row:
            return None

        t1_price = float(t1_row[0])

        # Determine actual direction
        if t1_price > entry_price:
            actual_direction = 'UP'
        elif t1_price < entry_price:
            actual_direction = 'DOWN'
        else:
            actual_direction = 'FLAT'

        # Was inversion correct?
        inversion_correct = (actual_direction == inverted_direction)

        # Calculate inverted Brier
        # If we predicted UP with 0.99 confidence and it went UP, Brier = (0.99 - 1)^2 = 0.0001
        # If we predicted UP with 0.99 confidence and it went DOWN, Brier = (0.99 - 0)^2 = 0.98
        if actual_direction == 'FLAT':
            inverted_brier = 0.25  # Neutral
        elif inversion_correct:
            inverted_brier = 0.0001  # Near perfect
        else:
            inverted_brier = 0.9801  # Wrong

        # Update shadow record
        update_query = """
            UPDATE fhq_alpha.inversion_overlay_shadow
            SET actual_outcome = %s,
                outcome_timestamp = NOW(),
                inverted_brier = %s,
                exit_price_underlying = %s,
                evaluated_at = NOW()
            WHERE overlay_id = %s
        """

        with self.conn.cursor() as cur:
            cur.execute(update_query, (
                inversion_correct,
                inverted_brier,
                t1_price,
                row['overlay_id']
            ))
        self.conn.commit()

        logger.info(f"OUTCOME: {ticker} inverted={inverted_direction} actual={actual_direction} correct={inversion_correct}")

        return inversion_correct

    # =========================================================================
    # HEALTH CHECK
    # =========================================================================

    def run_health_check(self) -> Dict[str, Any]:
        """
        Run dual-layer health check.

        Layer 1: Directional Health (signal quality) >= 80%
        Layer 2: P&L Health (execution quality) >= 0%

        For shadow mode, we only have Layer 1 (no P&L yet).
        """
        query = "SELECT * FROM fhq_alpha.check_inversion_health_v2(30)"

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            result = cur.fetchone()

        health = dict(result) if result else {}
        health['checked_at'] = datetime.now(timezone.utc).isoformat()
        health['mode'] = 'SHADOW'
        health['hindsight_firewall_active'] = date.today() < NON_ELIGIBILITY_END

        logger.info(f"Health check: {health['health_status']} (dir={health.get('directional_health', 0):.2%})")

        return health

    # =========================================================================
    # DAILY REPORT
    # =========================================================================

    def generate_daily_report(self) -> Dict[str, Any]:
        """
        Generate daily shadow performance report.

        This is what we measure every day.
        """
        # Get system-level performance
        query = "SELECT * FROM fhq_alpha.v_inversion_overlay_system_performance"
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            system_perf = cur.fetchone()

        # Get per-ticker performance
        query = "SELECT * FROM fhq_alpha.v_inversion_overlay_performance"
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            ticker_perf = cur.fetchall()

        # Get health status
        health = self.run_health_check()

        # Get today's captures
        query = """
            SELECT COUNT(*) as today_captures
            FROM fhq_alpha.inversion_overlay_shadow
            WHERE DATE(entry_timestamp) = CURRENT_DATE
        """
        with self.conn.cursor() as cur:
            cur.execute(query)
            today_captures = cur.fetchone()[0]

        report = {
            'report_type': 'IOS012B_SHADOW_DAILY',
            'report_date': date.today().isoformat(),
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'mode': 'SHADOW_ONLY',
            'hindsight_firewall': {
                'active': date.today() < NON_ELIGIBILITY_END,
                'eligibility_date': NON_ELIGIBILITY_END.isoformat(),
                'days_remaining': max(0, (NON_ELIGIBILITY_END - date.today()).days)
            },
            'system_performance': dict(system_perf) if system_perf else {},
            'ticker_performance': [dict(t) for t in ticker_perf] if ticker_perf else [],
            'health_status': health,
            'today_captures': today_captures,
            'canonical_universe': CANONICAL_UNIVERSE
        }

        return report

    def save_daily_report(self, report: Dict[str, Any]) -> str:
        """Save daily report to evidence folder."""
        report_date = date.today().strftime('%Y%m%d')
        filename = f"IOS012B_SHADOW_REPORT_{report_date}.json"
        filepath = os.path.join(
            os.path.dirname(__file__),
            'evidence',
            filename
        )

        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Daily report saved: {filepath}")
        return filepath


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description='IoS-012-B Shadow Signal Daemon')
    parser.add_argument('--capture', action='store_true', help='Capture STRESS@99%+ signals')
    parser.add_argument('--evaluate', action='store_true', help='Evaluate T-1 outcomes')
    parser.add_argument('--health', action='store_true', help='Run health check')
    parser.add_argument('--report', action='store_true', help='Generate daily report')
    parser.add_argument('--all', action='store_true', help='Run capture + evaluate + report')
    args = parser.parse_args()

    daemon = ShadowSignalDaemon()
    daemon.connect()

    try:
        if args.capture or args.all:
            print("\n=== SIGNAL CAPTURE ===")
            captures = daemon.capture_stress_signals()
            logged = daemon.log_captures_to_shadow(captures)
            print(f"Captured: {len(captures)}, Logged: {logged}")

        if args.evaluate or args.all:
            print("\n=== OUTCOME EVALUATION ===")
            results = daemon.evaluate_outcomes()
            print(json.dumps(results, indent=2))

        if args.health or args.all:
            print("\n=== HEALTH CHECK ===")
            health = daemon.run_health_check()
            print(json.dumps(health, indent=2, default=str))

        if args.report or args.all:
            print("\n=== DAILY REPORT ===")
            report = daemon.generate_daily_report()
            filepath = daemon.save_daily_report(report)
            print(f"Report saved: {filepath}")
            print(json.dumps(report, indent=2, default=str))

        if not any([args.capture, args.evaluate, args.health, args.report, args.all]):
            parser.print_help()

    finally:
        daemon.close()


if __name__ == '__main__':
    main()
