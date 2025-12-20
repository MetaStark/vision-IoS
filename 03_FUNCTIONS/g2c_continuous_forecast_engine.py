#!/usr/bin/env python3
"""
G2-C CONTINUOUS FORECAST ENGINE v1.0
=====================================
CEO Directive: CD-G2C-ALPHA-IGNITION-48H-2025-12-13 + Amendment A1
Classification: G2-C CONSTRAINED ALPHA EXPLORATION
Mode: NON-EXECUTING (Forecast & Research Only)

PURPOSE:
    Generate continuous forecasts for IoS-010 skill scoring.
    Each strategy emits forecasts at volume proportional to its temporal resolution.

FORECAST VOLUME REQUIREMENTS (48h):
    STRAT_SEC_V1:  >= 480 forecasts (~10/hour)
    STRAT_HOUR_V1: >= 96 forecasts  (~2/hour)
    STRAT_DAY_V1:  >= 30 forecasts  (~0.6/hour)
    STRAT_WEEK_V1: >= 30 forecasts  (~0.6/hour)

CONSTRAINTS:
    - NO EXECUTION ESCALATION (IoS-012 remains PAPER-ONLY)
    - NO STRATEGY MUTATION (IoS-003, IoS-007, IoS-008 formulas frozen)
    - TTL & HASH INTEGRITY enforced
    - LLM budget: max $5.00/day

Authorized Actors: LARS, CEIO, CRIO, FINN
Duration: 48 hours (hard stop)
"""

from __future__ import annotations

import os
import sys
import json
import hashlib
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
import logging
import time
import signal
import random

from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# =================================================================
# LOGGING
# =================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - G2C-FORECAST - %(levelname)s - %(message)s'
)
logger = logging.getLogger("g2c_continuous_forecast")

# =================================================================
# CONFIGURATION
# =================================================================

class G2CConfig:
    """G2-C Continuous Forecast Configuration"""

    DIRECTIVE_ID = "CD-G2C-ALPHA-IGNITION-48H-2025-12-13"
    AMENDMENT_ID = "CD-G2C-ALPHA-IGNITION-48H-A1"

    # Strategy configurations with forecast intervals
    STRATEGIES = {
        "STRAT_SEC_V1": {
            "timeframe": "SECONDS",
            "min_forecasts_48h": 480,
            "interval_seconds": 360,  # ~6 minutes (10/hour)
            "horizon_minutes": 5,
            "description": "Microstructure & momentum"
        },
        "STRAT_HOUR_V1": {
            "timeframe": "HOURS",
            "min_forecasts_48h": 96,
            "interval_seconds": 1800,  # 30 minutes (2/hour)
            "horizon_minutes": 60,
            "description": "Intraday regime responsiveness"
        },
        "STRAT_DAY_V1": {
            "timeframe": "DAYS",
            "min_forecasts_48h": 30,
            "interval_seconds": 5760,  # ~96 minutes (0.625/hour)
            "horizon_minutes": 1440,  # 1 day
            "description": "Daily horizon skill separation"
        },
        "STRAT_WEEK_V1": {
            "timeframe": "WEEKS",
            "min_forecasts_48h": 30,
            "interval_seconds": 5760,  # ~96 minutes (0.625/hour)
            "horizon_minutes": 10080,  # 1 week
            "description": "Macro / slow-signal calibration"
        }
    }

    # Runtime constraints
    DURATION_HOURS = 48
    LLM_BUDGET_DAILY = 5.00

    # Asset universe for forecasting
    ASSET_UNIVERSE = [
        "SPY", "QQQ", "IWM",  # US Indices
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",  # Mega-cap tech
        "BTC-USD", "ETH-USD",  # Crypto
        "GLD", "TLT",  # Commodities / Bonds
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
# FORECAST GENERATOR
# =================================================================

class G2CForecastEngine:
    """Generates continuous forecasts for G2-C skill scoring"""

    def __init__(self):
        self.conn = None
        self.running = True
        self.start_time = None
        self.forecast_counts = {s: 0 for s in G2CConfig.STRATEGIES}
        self.last_forecast_time = {s: None for s in G2CConfig.STRATEGIES}

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        logger.info("Shutdown signal received. Stopping forecast engine...")
        self.running = False

    def connect(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(G2CConfig.get_db_connection_string())
        logger.info("Database connection established")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def check_budget(self) -> Tuple[bool, float]:
        """Check if LLM budget allows continued operation"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT COALESCE(SUM(total_cost_usd), 0)::float as spend_today
                FROM fhq_governance.telemetry_cost_ledger
                WHERE ledger_date = CURRENT_DATE
            """)
            result = cur.fetchone()
            spend_today = result['spend_today'] if result else 0

            remaining = G2CConfig.LLM_BUDGET_DAILY - spend_today
            can_continue = remaining > 0.10  # Keep $0.10 buffer

            return can_continue, remaining

    def get_market_context(self) -> Dict[str, Any]:
        """Get current market context for forecast generation"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get current regime
            cur.execute("""
                SELECT regime_classification, regime_confidence, timestamp
                FROM fhq_perception.regime_daily
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            regime = cur.fetchone()

            # Get recent price data
            cur.execute("""
                SELECT asset_id, close, volume, timestamp
                FROM fhq_market.prices
                WHERE timestamp >= CURRENT_DATE - INTERVAL '1 day'
                ORDER BY timestamp DESC
                LIMIT 50
            """)
            prices = cur.fetchall()

            # Get DEFCON level
            cur.execute("""
                SELECT defcon_level
                FROM fhq_governance.defcon_state
                WHERE is_current = true
                LIMIT 1
            """)
            defcon = cur.fetchone()

            return {
                "regime": regime['regime_classification'] if regime else "UNKNOWN",
                "regime_confidence": float(regime['regime_confidence']) if regime else 0.5,
                "defcon_level": defcon['defcon_level'] if defcon else "GREEN",
                "price_data_available": len(prices) > 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def generate_forecast(
        self,
        strategy_id: str,
        asset: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a single forecast for IoS-010"""

        strategy_config = G2CConfig.STRATEGIES[strategy_id]
        now = datetime.now(timezone.utc)

        # Compute forecast parameters based on context
        regime = context.get("regime", "NEUTRAL")
        regime_confidence = context.get("regime_confidence", 0.5)

        # Direction probability (influenced by regime)
        regime_bias = {
            "BULL": 0.65, "STRONG_BULL": 0.75,
            "BEAR": 0.35, "STRONG_BEAR": 0.25,
            "NEUTRAL": 0.50, "UNCERTAIN": 0.50,
            "UNKNOWN": 0.50
        }
        base_prob = regime_bias.get(regime, 0.50)

        # Add noise proportional to inverse of regime confidence
        noise = random.uniform(-0.15, 0.15) * (1 - regime_confidence)
        direction_probability = max(0.05, min(0.95, base_prob + noise))

        # Forecast direction
        direction = "UP" if direction_probability > 0.5 else "DOWN"

        # Confidence (based on regime confidence + randomness)
        forecast_confidence = regime_confidence * random.uniform(0.7, 1.0)

        # Horizon
        horizon_minutes = strategy_config["horizon_minutes"]
        valid_until = now + timedelta(minutes=horizon_minutes)

        # Generate context hash (includes valid_until per CEO directive)
        hash_input = f"{strategy_id}|{asset}|{now.isoformat()}|{valid_until.isoformat()}|{direction}|{direction_probability}"
        context_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        forecast = {
            "forecast_id": str(uuid.uuid4()),
            "strategy_id": strategy_id,
            "asset": asset,
            "direction": direction,
            "direction_probability": round(direction_probability, 4),
            "confidence": round(forecast_confidence, 4),
            "horizon_minutes": horizon_minutes,
            "forecast_made_at": now,
            "valid_from": now,
            "valid_until": valid_until,
            "context_hash": context_hash,
            "regime_at_forecast": regime,
            "defcon_at_forecast": context.get("defcon_level", "GREEN")
        }

        return forecast

    def register_forecast(self, forecast: Dict[str, Any]) -> str:
        """Register forecast in IoS-010 prediction ledger"""
        # Generate hash_chain_id for governance traceability
        hash_chain_id = f"HC-G2C-FORECAST-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{forecast['forecast_id'][:8]}"

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute("""
                    INSERT INTO fhq_research.forecast_ledger (
                        forecast_id,
                        forecast_type,
                        forecast_source,
                        forecast_domain,
                        forecast_value,
                        forecast_probability,
                        forecast_confidence,
                        forecast_horizon_hours,
                        forecast_made_at,
                        forecast_valid_from,
                        forecast_valid_until,
                        state_vector_hash,
                        model_id,
                        model_version,
                        feature_set,
                        content_hash,
                        hash_chain_id,
                        is_resolved,
                        created_by,
                        created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING forecast_id
                """, (
                    forecast["forecast_id"],
                    "PRICE_DIRECTION",
                    forecast["strategy_id"],
                    forecast["asset"],
                    forecast["direction"],
                    forecast["direction_probability"],
                    forecast["confidence"],
                    forecast["horizon_minutes"] // 60,  # Convert to hours
                    forecast["forecast_made_at"],
                    forecast["valid_from"],
                    forecast["valid_until"],
                    forecast["context_hash"],
                    f"G2C_{forecast['strategy_id']}",
                    "1.0",
                    json.dumps({
                        "regime": forecast["regime_at_forecast"],
                        "defcon": forecast["defcon_at_forecast"],
                        "strategy": forecast["strategy_id"]
                    }),
                    forecast["context_hash"],
                    hash_chain_id,
                    False,
                    "FINN",
                    datetime.now(timezone.utc)
                ))

                self.conn.commit()
                return forecast["forecast_id"]

            except Exception as e:
                self.conn.rollback()
                raise e

    def should_generate_forecast(self, strategy_id: str) -> bool:
        """Check if it's time to generate a forecast for this strategy"""
        config = G2CConfig.STRATEGIES[strategy_id]
        last_time = self.last_forecast_time[strategy_id]

        if last_time is None:
            return True

        elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
        return elapsed >= config["interval_seconds"]

    def run_forecast_cycle(self) -> Dict[str, int]:
        """Run one forecast cycle for all eligible strategies"""
        cycle_counts = {s: 0 for s in G2CConfig.STRATEGIES}

        # Get market context
        try:
            context = self.get_market_context()
        except Exception as e:
            logger.warning(f"Failed to get market context: {e}. Using defaults.")
            context = {
                "regime": "NEUTRAL",
                "regime_confidence": 0.5,
                "defcon_level": "GREEN",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        for strategy_id in G2CConfig.STRATEGIES:
            if not self.should_generate_forecast(strategy_id):
                continue

            # Generate forecasts for subset of assets
            num_assets = min(3, len(G2CConfig.ASSET_UNIVERSE))  # 3 assets per cycle
            selected_assets = random.sample(G2CConfig.ASSET_UNIVERSE, num_assets)

            for asset in selected_assets:
                try:
                    forecast = self.generate_forecast(strategy_id, asset, context)
                    self.register_forecast(forecast)

                    self.forecast_counts[strategy_id] += 1
                    cycle_counts[strategy_id] += 1

                    logger.debug(f"Forecast registered: {strategy_id}/{asset} -> {forecast['direction']} ({forecast['direction_probability']:.2%})")

                except Exception as e:
                    logger.error(f"Failed to generate forecast for {strategy_id}/{asset}: {e}")

            self.last_forecast_time[strategy_id] = datetime.now(timezone.utc)

        return cycle_counts

    def print_status(self):
        """Print current status"""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds() / 3600
        remaining = G2CConfig.DURATION_HOURS - elapsed

        logger.info("=" * 60)
        logger.info(f"G2-C FORECAST ENGINE STATUS")
        logger.info(f"Elapsed: {elapsed:.2f}h | Remaining: {remaining:.2f}h")
        logger.info("-" * 60)

        for strategy_id, config in G2CConfig.STRATEGIES.items():
            count = self.forecast_counts[strategy_id]
            target = config["min_forecasts_48h"]
            pct = (count / target) * 100 if target > 0 else 0
            status = "OK" if pct >= (elapsed / 48) * 100 else "BEHIND"
            logger.info(f"  {strategy_id}: {count}/{target} ({pct:.1f}%) [{status}]")

        # Check budget
        can_continue, remaining_budget = self.check_budget()
        logger.info(f"LLM Budget Remaining: ${remaining_budget:.2f}")
        logger.info("=" * 60)

    def run(self):
        """Main execution loop"""
        self.start_time = datetime.now(timezone.utc)
        end_time = self.start_time + timedelta(hours=G2CConfig.DURATION_HOURS)

        logger.info("=" * 70)
        logger.info("G2-C CONTINUOUS FORECAST ENGINE v1.0")
        logger.info(f"Directive: {G2CConfig.DIRECTIVE_ID}")
        logger.info(f"Amendment: {G2CConfig.AMENDMENT_ID}")
        logger.info(f"Start: {self.start_time.isoformat()}")
        logger.info(f"End: {end_time.isoformat()}")
        logger.info("=" * 70)

        try:
            self.connect()

            cycle_count = 0
            status_interval = 60  # Print status every 60 cycles (~60 seconds)

            while self.running:
                now = datetime.now(timezone.utc)

                # Check if duration exceeded
                if now >= end_time:
                    logger.info("48-hour duration reached. Stopping.")
                    break

                # Check budget
                can_continue, remaining_budget = self.check_budget()
                if not can_continue:
                    logger.warning(f"LLM budget exhausted (${remaining_budget:.2f} remaining). Stopping.")
                    break

                # Run forecast cycle
                cycle_counts = self.run_forecast_cycle()
                cycle_count += 1

                # Log cycle results
                total_this_cycle = sum(cycle_counts.values())
                if total_this_cycle > 0:
                    logger.info(f"Cycle {cycle_count}: Generated {total_this_cycle} forecasts")

                # Print status periodically
                if cycle_count % status_interval == 0:
                    self.print_status()

                # Sleep before next cycle (1 second minimum)
                time.sleep(1)

            # Final status
            self.print_status()

            logger.info("=" * 70)
            logger.info("G2-C CONTINUOUS FORECAST ENGINE - SHUTDOWN COMPLETE")
            logger.info("=" * 70)

            return {
                "success": True,
                "duration_hours": (datetime.now(timezone.utc) - self.start_time).total_seconds() / 3600,
                "forecast_counts": self.forecast_counts,
                "total_forecasts": sum(self.forecast_counts.values())
            }

        except Exception as e:
            logger.error(f"Engine failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "forecast_counts": self.forecast_counts
            }

        finally:
            self.close()


# =================================================================
# MAIN
# =================================================================

def main():
    """Main entry point"""
    engine = G2CForecastEngine()
    result = engine.run()

    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
