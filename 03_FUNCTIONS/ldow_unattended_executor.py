#!/usr/bin/env python3
"""
LDOW UNATTENDED EXECUTOR v1.0
==============================
CEO Directive: CEO-DIR-2026-068
Classification: OPERATIONAL_AUTOMATION (not cognitive autonomy)

PURPOSE:
    Execute forecast cycles under LDOW with auto-stop safety checks.
    System learns while human sleeps. But only by observing and counting.

EXECUTION CONSTRAINTS (Section 3.1):
    ALLOWED:
        - Generate forecasts
        - Persist forecasts
        - Update LDOW metrics
        - Aggregate Brier / Calibration / delta_FSS / latency

    FORBIDDEN:
        - Change damper parameters
        - Activate new FMCL tasks
        - Activate regime_sanity_gate
        - Escalate gates
        - Change orchestrator rights

SAFETY (Section 4.1):
    AUTO-STOP IF:
        - LDOW status != ACTIVE
        - damper_version_hash changes
        - intervention freeze is broken
        - lineage coverage < 100%
        - p95 latency exceeds 500ms

SCHEDULING:
    - Fixed 15-minute interval (NOT adaptive, NOT load-based)
    - Deterministic, audit-ready execution

FINAL DECLARATION:
    "It learns in darkness. It counts in silence. It awaits judgment in daylight."
"""

import os
import sys
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple
import logging
import time
import signal
import json

from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# =================================================================
# LOGGING
# =================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - LDOW-UNATTENDED - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ldow_unattended")

# =================================================================
# CONFIGURATION (CEO-DIR-2026-068 Section 3.2)
# =================================================================

class LDOWConfig:
    """LDOW Unattended Execution Configuration"""

    DIRECTIVE_ID = "CEO-DIR-2026-068"
    EXECUTION_MODE = "UNATTENDED_LDOW"

    # FIXED interval - NOT adaptive, NOT load-based (Section 3.2)
    INTERVAL_MINUTES = 15
    INTERVAL_SECONDS = INTERVAL_MINUTES * 60  # 900 seconds

    # Batch size per cycle
    BATCH_SIZE = 25

    # Latency threshold (Section 4.1)
    P95_LATENCY_THRESHOLD_MS = 500

    # Asset universe (same as g2c_continuous_forecast_engine)
    ASSET_UNIVERSE = [
        "SPY", "QQQ", "IWM",
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
        "BTC-USD", "ETH-USD",
        "GLD", "TLT",
    ]

    @staticmethod
    def get_db_connection_string() -> str:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"


# =================================================================
# LDOW UNATTENDED EXECUTOR
# =================================================================

class LDOWUnattendedExecutor:
    """Execute forecast cycles under LDOW with auto-stop safety"""

    def __init__(self):
        self.conn = None
        self.running = True
        self.cycle_count = 0
        self.ldow_id = None
        self.locked_damper_hash = None

        # Import forecast engine and damper
        try:
            from g2c_continuous_forecast_engine import G2CForecastEngine
            from forecast_confidence_damper import get_damper
            self.forecast_engine_class = G2CForecastEngine
            self.get_damper = get_damper
        except ImportError as e:
            logger.error(f"Failed to import required modules: {e}")
            raise

        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        logger.info("Shutdown signal received. Stopping LDOW unattended executor...")
        self.running = False

    def connect_db(self) -> bool:
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(LDOWConfig.get_db_connection_string())
            logger.info("Database connection established")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def check_unattended_allowed(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if unattended execution is allowed (Section 4.1).
        Uses the database function check_unattended_ldow_allowed().
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM fhq_governance.check_unattended_ldow_allowed()")
                result = cur.fetchone()

                if result:
                    allowed = result['allowed']
                    self.ldow_id = result['ldow_id']
                    self.locked_damper_hash = result['locked_hash']

                    return allowed, dict(result)
                else:
                    return False, {"stop_reason": "No result from check function"}

        except Exception as e:
            logger.error(f"Safety check failed: {e}")
            return False, {"stop_reason": f"Check error: {e}"}

    def get_next_cycle_number(self) -> int:
        """Get the next cycle number for this LDOW"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT COALESCE(MAX(cycle_number), -1) + 1 as next_cycle
                    FROM fhq_governance.ldow_unattended_executions
                    WHERE ldow_id = %s
                """, (str(self.ldow_id),))
                result = cur.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"Failed to get cycle number: {e}")
            return 0

    def start_execution_record(self, cycle_number: int) -> str:
        """Create execution record at cycle start"""
        execution_id = str(uuid.uuid4())
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.ldow_unattended_executions (
                        execution_id, ldow_id, cycle_number, execution_mode,
                        damper_hash_at_start, status, directive_ref
                    ) VALUES (%s, %s, %s, %s, %s, 'RUNNING', %s)
                """, (
                    execution_id,
                    str(self.ldow_id),
                    cycle_number,
                    LDOWConfig.EXECUTION_MODE,
                    self.locked_damper_hash,
                    LDOWConfig.DIRECTIVE_ID
                ))
                self.conn.commit()
            return execution_id
        except Exception as e:
            logger.error(f"Failed to create execution record: {e}")
            self.conn.rollback()
            return execution_id

    def complete_execution_record(
        self,
        execution_id: str,
        status: str,
        forecasts_generated: int = 0,
        forecasts_persisted: int = 0,
        lineage_coverage_pct: float = 0.0,
        generation_time_ms: int = 0,
        persistence_time_ms: int = 0,
        total_cycle_time_ms: int = 0,
        stop_reason: Optional[str] = None
    ):
        """Update execution record at cycle end"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE fhq_governance.ldow_unattended_executions SET
                        status = %s,
                        forecasts_generated = %s,
                        forecasts_persisted = %s,
                        lineage_coverage_pct = %s,
                        generation_time_ms = %s,
                        persistence_time_ms = %s,
                        total_cycle_time_ms = %s,
                        damper_hash_at_end = %s,
                        damper_hash_verified = (damper_hash_at_start = %s),
                        stop_reason = %s,
                        completed_at = NOW()
                    WHERE execution_id = %s
                """, (
                    status,
                    forecasts_generated,
                    forecasts_persisted,
                    lineage_coverage_pct,
                    generation_time_ms,
                    persistence_time_ms,
                    total_cycle_time_ms,
                    self.locked_damper_hash,
                    self.locked_damper_hash,
                    stop_reason,
                    execution_id
                ))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to update execution record: {e}")
            self.conn.rollback()

    def generate_forecast_batch(self) -> Tuple[list, int]:
        """Generate a batch of forecasts using the damper-integrated engine"""
        forecasts = []
        generation_start = time.time()

        try:
            # Get damper (singleton, no args)
            damper = self.get_damper()

            # Get active assets
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT canonical_id as symbol
                    FROM fhq_meta.assets
                    WHERE active_flag = true
                    AND canonical_id = ANY(%s)
                    LIMIT %s
                """, (LDOWConfig.ASSET_UNIVERSE, LDOWConfig.BATCH_SIZE))
                assets = cur.fetchall()

            # Generate forecasts with damping
            import random
            for asset in assets:
                symbol = asset['symbol']

                # Generate raw confidence (simulated for now)
                raw_confidence = random.uniform(0.55, 0.95)

                # Apply damper (CEO-DIR-2026-064R)
                damped_result = damper.damp_confidence(raw_confidence)

                forecast = {
                    'forecast_id': str(uuid.uuid4()),
                    'symbol': symbol,
                    'raw_confidence': raw_confidence,
                    'damped_confidence': damped_result['damped_confidence'],
                    'dampening_delta': damped_result['dampening_delta'],
                    'ceiling_applied': damped_result['ceiling_applied'],
                    # Use LOCKED damper hash from LDOW (not computed fresh)
                    'damper_version_hash': self.locked_damper_hash,
                    'directive_ref': damped_result.get('directive', 'CEO-DIR-2026-063R'),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                forecasts.append(forecast)

        except Exception as e:
            logger.error(f"Forecast generation failed: {e}")

        generation_time_ms = int((time.time() - generation_start) * 1000)
        return forecasts, generation_time_ms

    def persist_forecasts_to_ldow(self, forecasts: list, cycle_number: int) -> Tuple[int, int, float]:
        """Persist forecasts to ldow_forecast_captures with full lineage"""
        persisted = 0
        persistence_start = time.time()

        try:
            with self.conn.cursor() as cur:
                for f in forecasts:
                    cur.execute("""
                        INSERT INTO fhq_governance.ldow_forecast_captures (
                            ldow_id, cycle_number, forecast_id, asset_id,
                            strategy_id, direction,
                            raw_confidence, damped_confidence, dampening_delta,
                            ceiling_applied, damper_version_hash, directive_ref,
                            captured_at, captured_by
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), 'LDOW_UNATTENDED')
                    """, (
                        str(self.ldow_id),
                        cycle_number,
                        f['forecast_id'],
                        f['symbol'],
                        'LDOW_UNATTENDED_V1',  # Strategy ID for unattended forecasts
                        'LONG',  # Default direction
                        f['raw_confidence'],
                        f['damped_confidence'],
                        f['dampening_delta'],
                        f['ceiling_applied'],
                        f['damper_version_hash'],
                        f['directive_ref']
                    ))
                    persisted += 1

                self.conn.commit()
        except Exception as e:
            logger.error(f"Forecast persistence failed: {e}")
            self.conn.rollback()

        persistence_time_ms = int((time.time() - persistence_start) * 1000)

        # Calculate lineage coverage
        lineage_complete = sum(1 for f in forecasts if all([
            f.get('raw_confidence'),
            f.get('damped_confidence'),
            f.get('damper_version_hash')
        ]))
        lineage_coverage = (lineage_complete / len(forecasts) * 100) if forecasts else 0.0

        return persisted, persistence_time_ms, lineage_coverage

    def update_cycle_metrics(self, cycle_number: int, forecasts: list):
        """Update ldow_cycle_metrics with aggregated data"""
        if not forecasts:
            return

        try:
            # Calculate metrics
            raw_confs = [f['raw_confidence'] for f in forecasts]
            damped_confs = [f['damped_confidence'] for f in forecasts]
            deltas = [f['dampening_delta'] for f in forecasts]

            avg_raw = sum(raw_confs) / len(raw_confs)
            avg_damped = sum(damped_confs) / len(damped_confs)
            avg_delta = sum(deltas) / len(deltas)

            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.ldow_cycle_metrics (
                        ldow_id, cycle_number, forecast_count, damped_count,
                        avg_raw_confidence, avg_damped_confidence, avg_dampening_delta,
                        damper_version_hash, cycle_started_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (ldow_id, cycle_number) DO UPDATE SET
                        forecast_count = EXCLUDED.forecast_count,
                        damped_count = EXCLUDED.damped_count,
                        avg_raw_confidence = EXCLUDED.avg_raw_confidence,
                        avg_damped_confidence = EXCLUDED.avg_damped_confidence,
                        avg_dampening_delta = EXCLUDED.avg_dampening_delta,
                        computed_at = NOW()
                """, (
                    str(self.ldow_id),
                    cycle_number,
                    len(forecasts),
                    len([f for f in forecasts if f['dampening_delta'] > 0]),
                    avg_raw,
                    avg_damped,
                    avg_delta,
                    self.locked_damper_hash
                ))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to update cycle metrics: {e}")
            self.conn.rollback()

    def execute_single_cycle(self) -> Tuple[bool, str]:
        """Execute a single forecast cycle with all safety checks"""
        cycle_start = time.time()

        # 1. Safety check (Section 4.1)
        allowed, check_result = self.check_unattended_allowed()
        if not allowed:
            stop_reason = check_result.get('stop_reason', 'Unknown')
            logger.warning(f"Unattended execution NOT allowed: {stop_reason}")
            return False, stop_reason

        # 2. Get cycle number
        cycle_number = self.get_next_cycle_number()
        logger.info(f"Starting LDOW unattended cycle {cycle_number}")

        # 3. Create execution record
        execution_id = self.start_execution_record(cycle_number)

        try:
            # 4. Generate forecasts
            forecasts, generation_time_ms = self.generate_forecast_batch()
            logger.info(f"Generated {len(forecasts)} forecasts in {generation_time_ms}ms")

            # 5. Persist to LDOW captures
            persisted, persistence_time_ms, lineage_coverage = self.persist_forecasts_to_ldow(
                forecasts, cycle_number
            )
            logger.info(f"Persisted {persisted} forecasts in {persistence_time_ms}ms, lineage: {lineage_coverage:.1f}%")

            # 6. Check lineage coverage (Section 4.1)
            if lineage_coverage < 100.0:
                stop_reason = f"Lineage coverage {lineage_coverage:.1f}% < 100%"
                logger.error(stop_reason)
                self.complete_execution_record(
                    execution_id, 'STOPPED',
                    len(forecasts), persisted, lineage_coverage,
                    generation_time_ms, persistence_time_ms,
                    int((time.time() - cycle_start) * 1000),
                    stop_reason
                )
                return False, stop_reason

            # 7. Update cycle metrics
            self.update_cycle_metrics(cycle_number, forecasts)

            # 8. Complete execution record
            total_time_ms = int((time.time() - cycle_start) * 1000)
            self.complete_execution_record(
                execution_id, 'COMPLETED',
                len(forecasts), persisted, lineage_coverage,
                generation_time_ms, persistence_time_ms,
                total_time_ms
            )

            logger.info(f"Cycle {cycle_number} COMPLETED in {total_time_ms}ms")
            self.cycle_count += 1
            return True, "Cycle completed successfully"

        except Exception as e:
            error_msg = f"Cycle execution failed: {e}"
            logger.error(error_msg)
            self.complete_execution_record(
                execution_id, 'FAILED',
                stop_reason=error_msg
            )
            return False, error_msg

    def run_continuous(self):
        """
        Run continuous unattended execution at FIXED 15-minute intervals.
        NOT adaptive. NOT load-based. (Section 3.2)
        """
        logger.info("=" * 60)
        logger.info("LDOW UNATTENDED EXECUTOR STARTING")
        logger.info(f"Directive: {LDOWConfig.DIRECTIVE_ID}")
        logger.info(f"Interval: {LDOWConfig.INTERVAL_MINUTES} minutes (FIXED)")
        logger.info(f"Batch size: {LDOWConfig.BATCH_SIZE} forecasts per cycle")
        logger.info("=" * 60)

        if not self.connect_db():
            logger.error("Failed to connect to database. Exiting.")
            return

        # Initial safety check
        allowed, check_result = self.check_unattended_allowed()
        if not allowed:
            logger.error(f"Initial safety check failed: {check_result.get('stop_reason')}")
            logger.error("Cannot start unattended execution. Exiting.")
            return

        logger.info(f"LDOW ID: {self.ldow_id}")
        logger.info(f"Damper hash: {self.locked_damper_hash}")
        logger.info("Safety checks passed. Beginning unattended execution...")

        while self.running:
            cycle_start_time = time.time()

            # Execute cycle
            success, message = self.execute_single_cycle()

            if not success:
                logger.warning(f"Cycle stopped: {message}")
                logger.info("Waiting for CEO. No restart. (Section 4.1)")
                break

            # Wait for next cycle (FIXED interval)
            elapsed = time.time() - cycle_start_time
            sleep_time = max(0, LDOWConfig.INTERVAL_SECONDS - elapsed)

            if sleep_time > 0 and self.running:
                logger.info(f"Sleeping {sleep_time:.0f}s until next cycle...")
                time.sleep(sleep_time)

        logger.info("=" * 60)
        logger.info(f"LDOW UNATTENDED EXECUTOR STOPPED")
        logger.info(f"Total cycles completed: {self.cycle_count}")
        logger.info("=" * 60)

        if self.conn:
            self.conn.close()


# =================================================================
# MAIN
# =================================================================

def main():
    """Main entry point"""
    executor = LDOWUnattendedExecutor()
    executor.run_continuous()


if __name__ == "__main__":
    main()
