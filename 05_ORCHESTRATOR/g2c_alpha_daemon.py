#!/usr/bin/env python3
"""
G2-C ALPHA DAEMON v1.1 (LLM-INTEGRATED)
========================================
CEO Directive: CD-G2C-ALPHA-IGNITION-48H-2025-12-13 + Amendment A1
Classification: G2-C CONSTRAINED ALPHA EXPLORATION
Mode: NON-EXECUTING (Forecast, Resolution & Skill Scoring Only)

This daemon runs persistently and handles:
1. Continuous forecast generation (LLM-informed via FINN DeepSeek CRIO)
2. Forecast resolution against actual price outcomes
3. Skill metrics computation for dashboard display
4. Periodic CRIO research cycles (LLM-powered market analysis)

Designed to run as a Windows Scheduled Task or persistent service.

CONSTRAINTS:
    - NO EXECUTION ESCALATION (IoS-012 remains PAPER-ONLY)
    - NO STRATEGY MUTATION (formulas frozen)
    - TTL & HASH INTEGRITY enforced
    - LLM budget: max $5.00/day (ADR-012 enforced via FINN CRIO)

LLM INTEGRATION (v1.1):
    - FINN DeepSeek CRIO research every 30 minutes
    - Research insights inform forecast generation
    - Fragility/regime signals shape direction probability
    - All LLM calls tracked via fhq_telemetry

Authorized Actors: LARS, CEIO, CRIO, FINN
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

# Add parent path for FINN CRIO import
sys.path.insert(0, str(Path(__file__).parent.parent / '06_AGENTS' / 'FINN'))

# =================================================================
# LOGGING
# =================================================================

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - G2C-DAEMON - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "g2c_alpha_daemon.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("g2c_alpha_daemon")

# =================================================================
# CONFIGURATION
# =================================================================

class G2CConfig:
    """G2-C Alpha Daemon Configuration"""

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

    # Resolution intervals
    RESOLUTION_INTERVAL_SECONDS = 300  # Check for resolvable forecasts every 5 minutes
    SKILL_COMPUTE_INTERVAL_SECONDS = 600  # Recompute skill metrics every 10 minutes

    # LLM Research intervals (FINN CRIO)
    CRIO_RESEARCH_INTERVAL_SECONDS = 1800  # Run CRIO research every 30 minutes
    LLM_BUDGET_DAILY_USD = 5.00  # ADR-012 daily limit

    # Asset universe for forecasting - only tickers with price data in fhq_data.price_series
    ASSET_UNIVERSE = [
        "SPY",        # US Equity Index (2747 rows)
        "BTC-USD",    # Bitcoin (3993 rows)
        "ETH-USD",    # Ethereum (3259 rows)
        "SOL-USD",    # Solana (price data available)
        "GLD",        # Gold ETF (price data available)
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
# G2C ALPHA DAEMON
# =================================================================

class G2CAlphaDaemon:
    """
    Persistent daemon that handles:
    1. Forecast generation (LLM-informed via FINN CRIO)
    2. Forecast resolution
    3. Skill metrics computation
    4. Periodic CRIO research cycles
    """

    def __init__(self):
        self.conn = None
        self.running = True
        self.start_time = None
        self.forecast_counts = {s: 0 for s in G2CConfig.STRATEGIES}
        self.last_forecast_time = {s: None for s in G2CConfig.STRATEGIES}
        self.last_resolution_time = None
        self.last_skill_compute_time = None
        self.last_crio_research_time = None
        self.resolution_count = 0
        self.outcome_count = 0
        self.crio_research_count = 0

        # FINN CRIO Engine (lazy loaded)
        self.crio_engine = None
        self.latest_crio_result = None

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        logger.info("Shutdown signal received. Stopping G2C Alpha Daemon...")
        self.running = False

    def connect(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(G2CConfig.get_db_connection_string())
        self.conn.autocommit = False
        logger.info("Database connection established")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def reconnect_if_needed(self):
        """Reconnect if connection is lost"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
        except:
            logger.warning("Database connection lost, reconnecting...")
            self.connect()

    # =================================================================
    # FINN CRIO RESEARCH (LLM-POWERED)
    # =================================================================

    def init_crio_engine(self):
        """Initialize the FINN CRIO engine for LLM research"""
        try:
            from finn_deepseek_researcher import FINNCRIOEngine, CRIOConfig
            config = CRIOConfig()
            self.crio_engine = FINNCRIOEngine(config)
            self.crio_engine.connect()
            logger.info("FINN CRIO Engine initialized for LLM research")
            return True
        except ImportError as e:
            logger.warning(f"FINN CRIO import failed (running without LLM): {e}")
            return False
        except Exception as e:
            logger.error(f"FINN CRIO initialization failed: {e}")
            return False

    def run_crio_research(self) -> Optional[Dict[str, Any]]:
        """
        Execute FINN CRIO research cycle.
        Returns the research result or None on failure.
        """
        if not self.crio_engine:
            if not self.init_crio_engine():
                return None

        try:
            logger.info("=" * 50)
            logger.info("EXECUTING FINN CRIO RESEARCH (LLM-POWERED)")
            logger.info("=" * 50)

            # Execute the CRIO research
            result = self.crio_engine.execute_crio_research()

            if result.get("status") in ["CRIO_VERIFIED", "CRIO_PARTIAL"]:
                self.latest_crio_result = result
                self.crio_research_count += 1

                # Extract key insights
                analysis = result.get("analysis", {})
                fragility = analysis.get("fragility_score", 0.5)
                driver = analysis.get("dominant_driver", "UNKNOWN")
                regime = analysis.get("regime_assessment", "UNCERTAIN")

                logger.info(f"CRIO Research #{self.crio_research_count} complete:")
                logger.info(f"  Fragility: {fragility:.2f}")
                logger.info(f"  Driver: {driver}")
                logger.info(f"  Regime: {regime}")
                logger.info(f"  Status: {result['status']}")

                return result
            else:
                logger.warning(f"CRIO research returned status: {result.get('status')}")
                return result

        except Exception as e:
            logger.error(f"CRIO research failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def should_run_crio_research(self) -> bool:
        """Check if it's time to run CRIO research"""
        if self.last_crio_research_time is None:
            return True

        elapsed = (datetime.now(timezone.utc) - self.last_crio_research_time).total_seconds()
        return elapsed >= G2CConfig.CRIO_RESEARCH_INTERVAL_SECONDS

    # =================================================================
    # FORECAST GENERATION
    # =================================================================

    def get_market_context(self) -> Dict[str, Any]:
        """Get current market context for forecast generation"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get current regime
                cur.execute("""
                    SELECT regime_label as regime_classification,
                           posterior_prob as regime_confidence,
                           updated_at as timestamp
                    FROM fhq_research.regime_predictions
                    ORDER BY updated_at DESC
                    LIMIT 1
                """)
                regime = cur.fetchone()

                # Get DEFCON level
                cur.execute("""
                    SELECT defcon_level
                    FROM fhq_governance.defcon_state
                    WHERE is_current = true
                    ORDER BY triggered_at DESC
                    LIMIT 1
                """)
                defcon = cur.fetchone()

                return {
                    "regime": regime['regime_classification'] if regime else "NEUTRAL",
                    "regime_confidence": float(regime['regime_confidence']) if regime else 0.5,
                    "defcon_level": defcon['defcon_level'] if defcon else "GREEN",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            logger.warning(f"Failed to get market context: {e}. Using defaults.")
            return {
                "regime": "NEUTRAL",
                "regime_confidence": 0.5,
                "defcon_level": "GREEN",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def generate_forecast(
        self,
        strategy_id: str,
        asset: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a single forecast using CRIO research insights"""

        strategy_config = G2CConfig.STRATEGIES[strategy_id]
        now = datetime.now(timezone.utc)

        # Get CRIO research insights (if available)
        crio_fragility = 0.5
        crio_driver = "UNKNOWN"
        crio_regime = "UNCERTAIN"
        crio_confidence = 0.5
        llm_informed = False

        if self.latest_crio_result:
            analysis = self.latest_crio_result.get("analysis", {})
            crio_fragility = analysis.get("fragility_score", 0.5)
            crio_driver = analysis.get("dominant_driver", "UNKNOWN")
            crio_regime = analysis.get("regime_assessment", "UNCERTAIN")
            crio_confidence = analysis.get("confidence", 0.5)
            llm_informed = True

        # Compute forecast parameters based on context + CRIO insights
        regime = context.get("regime", "NEUTRAL")
        regime_confidence = context.get("regime_confidence", 0.5)

        # Direction probability (influenced by regime AND CRIO research)
        regime_bias = {
            "BULL": 0.65, "STRONG_BULL": 0.75,
            "BEAR": 0.35, "STRONG_BEAR": 0.25,
            "NEUTRAL": 0.50, "UNCERTAIN": 0.50,
            "UNKNOWN": 0.50
        }
        base_prob = regime_bias.get(regime, 0.50)

        # Apply CRIO regime adjustment if LLM-informed
        if llm_informed:
            crio_regime_bias = {
                "STRONG_BULL": 0.80, "BULL": 0.65,
                "NEUTRAL": 0.50, "UNCERTAIN": 0.50,
                "BEAR": 0.35, "STRONG_BEAR": 0.20
            }
            crio_bias = crio_regime_bias.get(crio_regime, 0.50)

            # Blend database regime with CRIO assessment (weight CRIO higher)
            base_prob = 0.4 * base_prob + 0.6 * crio_bias

            # Fragility adjustment: high fragility -> more cautious (toward 0.5)
            if crio_fragility > 0.6:
                base_prob = 0.7 * base_prob + 0.3 * 0.5  # Pull toward neutral
            elif crio_fragility < 0.3:
                pass  # Low fragility - trust the signal more

            # Blend confidence with CRIO confidence
            regime_confidence = 0.5 * regime_confidence + 0.5 * crio_confidence

        # Add reduced noise when LLM-informed (more deterministic)
        noise_scale = 0.08 if llm_informed else 0.15
        noise = random.uniform(-noise_scale, noise_scale) * (1 - regime_confidence)
        direction_probability = max(0.05, min(0.95, base_prob + noise))

        # Forecast direction
        direction = "UP" if direction_probability > 0.5 else "DOWN"

        # Confidence (based on blended regime confidence)
        confidence_floor = 0.8 if llm_informed else 0.7
        forecast_confidence = regime_confidence * random.uniform(confidence_floor, 1.0)

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
            "defcon_at_forecast": context.get("defcon_level", "GREEN"),
            # LLM research context
            "llm_informed": llm_informed,
            "crio_fragility": round(crio_fragility, 4) if llm_informed else None,
            "crio_driver": crio_driver if llm_informed else None,
            "crio_regime": crio_regime if llm_informed else None
        }

        return forecast

    def register_forecast(self, forecast: Dict[str, Any]) -> str:
        """Register forecast in forecast_ledger"""
        hash_chain_id = f"HC-G2C-FORECAST-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{forecast['forecast_id'][:8]}"

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
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
                forecast["horizon_minutes"] // 60,
                forecast["forecast_made_at"],
                forecast["valid_from"],
                forecast["valid_until"],
                forecast["context_hash"],
                f"G2C_{forecast['strategy_id']}",
                "1.1",  # v1.1 with LLM integration
                json.dumps({
                    "regime": forecast["regime_at_forecast"],
                    "defcon": forecast["defcon_at_forecast"],
                    "strategy": forecast["strategy_id"],
                    "llm_informed": forecast.get("llm_informed", False),
                    "crio_fragility": forecast.get("crio_fragility"),
                    "crio_driver": forecast.get("crio_driver"),
                    "crio_regime": forecast.get("crio_regime")
                }),
                forecast["context_hash"],
                hash_chain_id,
                False,
                "FINN",
                datetime.now(timezone.utc)
            ))

            self.conn.commit()
            return forecast["forecast_id"]

    def should_generate_forecast(self, strategy_id: str) -> bool:
        """Check if it's time to generate a forecast for this strategy"""
        config = G2CConfig.STRATEGIES[strategy_id]
        last_time = self.last_forecast_time[strategy_id]

        if last_time is None:
            return True

        elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
        return elapsed >= config["interval_seconds"]

    def run_forecast_cycle(self) -> int:
        """Run one forecast cycle for all eligible strategies"""
        total_generated = 0
        context = self.get_market_context()

        for strategy_id in G2CConfig.STRATEGIES:
            if not self.should_generate_forecast(strategy_id):
                continue

            # Generate forecasts for subset of assets
            num_assets = min(3, len(G2CConfig.ASSET_UNIVERSE))
            selected_assets = random.sample(G2CConfig.ASSET_UNIVERSE, num_assets)

            for asset in selected_assets:
                try:
                    forecast = self.generate_forecast(strategy_id, asset, context)
                    self.register_forecast(forecast)

                    self.forecast_counts[strategy_id] += 1
                    total_generated += 1

                except Exception as e:
                    logger.error(f"Failed to generate forecast for {strategy_id}/{asset}: {e}")
                    self.conn.rollback()

            self.last_forecast_time[strategy_id] = datetime.now(timezone.utc)

        return total_generated

    # =================================================================
    # FORECAST RESOLUTION
    # =================================================================

    def get_asset_ticker_mapping(self) -> Dict[str, str]:
        """Get mapping of forecast domain names to database asset IDs"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT canonical_id, ticker
                FROM fhq_meta.assets
                WHERE active_flag = true
            """)
            assets = cur.fetchall()

            mapping = {}
            for asset in assets:
                mapping[asset['ticker']] = str(asset['canonical_id'])

            return mapping

    def get_price_at_time(self, asset_id: str, target_time: datetime) -> Optional[float]:
        """Get price closest to target time. asset_id is actually canonical_id (ticker)."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Try fhq_market.prices first (more recent) - uses canonical_id
            cur.execute("""
                SELECT close, timestamp
                FROM fhq_market.prices
                WHERE canonical_id = %s
                  AND timestamp <= %s
                ORDER BY timestamp DESC
                LIMIT 1
            """, (asset_id, target_time))
            result = cur.fetchone()

            if result:
                return float(result['close'])

            # Fall back to fhq_data.price_series (uses listing_id as text ticker)
            cur.execute("""
                SELECT close, timestamp
                FROM fhq_data.price_series
                WHERE listing_id = %s
                  AND timestamp <= %s
                ORDER BY timestamp DESC
                LIMIT 1
            """, (asset_id, target_time))
            result = cur.fetchone()

            if result:
                return float(result['close'])

            return None

    def create_outcome(self, asset: str, outcome_time: datetime,
                       start_price: float, end_price: float) -> Optional[str]:
        """Create an outcome record based on price movement"""
        direction = "UP" if end_price > start_price else "DOWN"
        pct_change = ((end_price - start_price) / start_price) * 100

        outcome_id = str(uuid.uuid4())
        content_hash = hashlib.sha256(
            f"{asset}|{outcome_time.isoformat()}|{direction}|{pct_change}".encode()
        ).hexdigest()

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_research.outcome_ledger (
                    outcome_id,
                    outcome_type,
                    outcome_domain,
                    outcome_value,
                    outcome_timestamp,
                    evidence_source,
                    evidence_data,
                    content_hash,
                    hash_chain_id,
                    created_by,
                    created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT DO NOTHING
                RETURNING outcome_id
            """, (
                outcome_id,
                "PRICE_DIRECTION",
                asset,
                direction,
                outcome_time,
                "fhq_market.prices",
                json.dumps({
                    "start_price": start_price,
                    "end_price": end_price,
                    "pct_change": round(pct_change, 4)
                }),
                content_hash,
                f"HC-OUTCOME-{outcome_time.strftime('%Y%m%d')}",
                "STIG",
                datetime.now(timezone.utc)
            ))
            result = cur.fetchone()
            self.conn.commit()

            if result:
                self.outcome_count += 1
                return result[0]
            return outcome_id  # Already exists

    def resolve_expired_forecasts(self) -> int:
        """Find and resolve forecasts that have expired"""
        resolved = 0
        asset_mapping = self.get_asset_ticker_mapping()

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get unresolved forecasts that have expired
            cur.execute("""
                SELECT
                    forecast_id,
                    forecast_domain,
                    forecast_value,
                    forecast_probability,
                    forecast_made_at,
                    forecast_valid_until
                FROM fhq_research.forecast_ledger
                WHERE is_resolved = false
                  AND forecast_valid_until < NOW()
                ORDER BY forecast_valid_until ASC
                LIMIT 100
            """)
            forecasts = cur.fetchall()

            if not forecasts:
                return 0

            logger.info(f"Found {len(forecasts)} expired forecasts to resolve")

            for forecast in forecasts:
                try:
                    asset = forecast['forecast_domain']
                    asset_id = asset_mapping.get(asset)

                    if not asset_id:
                        logger.warning(f"No asset mapping for {asset}, skipping")
                        continue

                    # Get price at forecast time and at expiry
                    start_price = self.get_price_at_time(asset_id, forecast['forecast_made_at'])
                    end_price = self.get_price_at_time(asset_id, forecast['forecast_valid_until'])

                    if start_price is None or end_price is None:
                        logger.warning(f"Missing price data for {asset}, skipping")
                        continue

                    # Create outcome
                    outcome_id = self.create_outcome(
                        asset,
                        forecast['forecast_valid_until'],
                        start_price,
                        end_price
                    )

                    # Determine actual direction
                    actual_direction = "UP" if end_price > start_price else "DOWN"
                    predicted_direction = forecast['forecast_value']
                    is_correct = (actual_direction == predicted_direction)

                    # Compute Brier score
                    actual_prob = 1.0 if is_correct else 0.0
                    brier_score = (float(forecast['forecast_probability']) - actual_prob) ** 2

                    # Update forecast as resolved
                    cur.execute("""
                        UPDATE fhq_research.forecast_ledger
                        SET
                            is_resolved = true,
                            resolution_status = %s,
                            resolved_at = NOW(),
                            outcome_id = %s::uuid
                        WHERE forecast_id = %s::uuid
                    """, (
                        'CORRECT' if is_correct else 'INCORRECT',
                        outcome_id,
                        str(forecast['forecast_id'])
                    ))

                    self.conn.commit()
                    resolved += 1
                    self.resolution_count += 1

                except Exception as e:
                    logger.error(f"Failed to resolve forecast {forecast['forecast_id']}: {e}")
                    self.conn.rollback()

        if resolved > 0:
            logger.info(f"Resolved {resolved} forecasts")

        return resolved

    # =================================================================
    # SKILL METRICS COMPUTATION
    # =================================================================

    def compute_skill_metrics(self) -> bool:
        """Compute and update skill metrics for all strategies"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get resolution stats per strategy
                cur.execute("""
                    SELECT
                        forecast_source as strategy_id,
                        COUNT(*) as total_forecasts,
                        COUNT(*) FILTER (WHERE is_resolved) as resolved_count,
                        COUNT(*) FILTER (WHERE resolution_status = 'CORRECT') as correct_count,
                        AVG(CASE WHEN is_resolved THEN
                            POWER(forecast_probability -
                                CASE WHEN resolution_status = 'CORRECT' THEN 1.0 ELSE 0.0 END, 2)
                            END) as brier_score
                    FROM fhq_research.forecast_ledger
                    WHERE forecast_source LIKE 'STRAT_%'
                    GROUP BY forecast_source
                """)
                stats = cur.fetchall()

                today = datetime.now(timezone.utc).date()

                for stat in stats:
                    strategy_id = stat['strategy_id']
                    resolved = stat['resolved_count'] or 0
                    correct = stat['correct_count'] or 0
                    total = stat['total_forecasts'] or 0
                    brier = stat['brier_score']

                    win_rate = correct / resolved if resolved > 0 else 0
                    # Simple Sharpe approximation based on win rate
                    sharpe = (win_rate - 0.5) / 0.25 if resolved >= 10 else None

                    # Delete existing cumulative metric for this strategy, then insert new
                    cur.execute("""
                        DELETE FROM fhq_execution.g2c_skill_metrics
                        WHERE strategy_id = %s
                          AND metric_period = 'CUMULATIVE'
                          AND canonical_skill_source = true
                    """, (strategy_id,))

                    # Insert skill metrics with all required fields
                    cur.execute("""
                        INSERT INTO fhq_execution.g2c_skill_metrics (
                            metric_id,
                            strategy_id,
                            metric_date,
                            metric_period,
                            sharpe_ratio,
                            win_rate,
                            total_trades,
                            canonical_skill_source,
                            calculated_at,
                            calculated_by
                        ) VALUES (
                            gen_random_uuid(),
                            %s,
                            %s,
                            'CUMULATIVE',
                            %s,
                            %s,
                            %s,
                            true,
                            NOW(),
                            'STIG'
                        )
                    """, (
                        strategy_id,
                        today,
                        sharpe,
                        win_rate,
                        resolved
                    ))

                # Update forecast_skill_metrics for dashboard
                # Note: metric_scope must be one of: GLOBAL, AGENT, DOMAIN, TYPE, MODEL, PERIOD
                # We use 'MODEL' scope with strategy_id as the scope_value
                for stat in stats:
                    strategy_id = stat['strategy_id']
                    resolved = stat['resolved_count'] or 0
                    correct = stat['correct_count'] or 0
                    total = stat['total_forecasts'] or 0
                    brier = stat['brier_score']
                    win_rate = correct / resolved if resolved > 0 else None

                    # Compute confidence interval (Wilson score interval approximation)
                    ci_low = None
                    ci_high = None
                    if resolved >= 10 and win_rate is not None:
                        import math
                        z = 1.96  # 95% CI
                        n = resolved
                        p = win_rate
                        denom = 1 + z*z/n
                        center = (p + z*z/(2*n)) / denom
                        spread = z * math.sqrt((p*(1-p) + z*z/(4*n)) / n) / denom
                        ci_low = max(0, center - spread)
                        ci_high = min(1, center + spread)

                    # Delete existing, then insert (using MODEL scope for strategies)
                    cur.execute("""
                        DELETE FROM fhq_research.forecast_skill_metrics
                        WHERE metric_scope = 'MODEL' AND scope_value = %s
                    """, (strategy_id,))

                    cur.execute("""
                        INSERT INTO fhq_research.forecast_skill_metrics (
                            metric_id,
                            metric_scope,
                            scope_value,
                            forecast_count,
                            resolved_count,
                            brier_score_mean,
                            hit_rate,
                            hit_rate_confidence_low,
                            hit_rate_confidence_high,
                            computed_at,
                            computed_by,
                            hash_chain_id
                        ) VALUES (
                            gen_random_uuid(),
                            'MODEL',
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            NOW(),
                            'STIG',
                            %s
                        )
                    """, (
                        strategy_id,
                        total,
                        resolved,
                        float(brier) if brier else None,
                        win_rate,
                        ci_low,
                        ci_high,
                        f"HC-SKILL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
                    ))

                self.conn.commit()
                logger.info(f"Updated skill metrics for {len(stats)} strategies")
                return True

        except Exception as e:
            logger.error(f"Failed to compute skill metrics: {e}")
            import traceback
            traceback.print_exc()
            self.conn.rollback()
            return False

    # =================================================================
    # MAIN LOOP
    # =================================================================

    def print_status(self):
        """Print current status"""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds() / 3600

        logger.info("=" * 70)
        logger.info(f"G2-C ALPHA DAEMON v1.1 (LLM-INTEGRATED) STATUS")
        logger.info(f"Uptime: {elapsed:.2f} hours")
        logger.info("-" * 70)

        total_forecasts = sum(self.forecast_counts.values())
        logger.info(f"Forecasts Generated: {total_forecasts}")
        logger.info(f"Outcomes Created: {self.outcome_count}")
        logger.info(f"Forecasts Resolved: {self.resolution_count}")
        logger.info(f"CRIO Research Cycles: {self.crio_research_count}")
        logger.info(f"LLM-Informed: {'YES' if self.latest_crio_result else 'NO'}")

        for strategy_id, count in self.forecast_counts.items():
            logger.info(f"  {strategy_id}: {count}")

        if self.latest_crio_result:
            analysis = self.latest_crio_result.get("analysis", {})
            logger.info("-" * 70)
            logger.info(f"Latest CRIO Insights:")
            logger.info(f"  Fragility: {analysis.get('fragility_score', 'N/A')}")
            logger.info(f"  Driver: {analysis.get('dominant_driver', 'N/A')}")
            logger.info(f"  Regime: {analysis.get('regime_assessment', 'N/A')}")

        logger.info("=" * 70)

    def run(self):
        """Main execution loop"""
        self.start_time = datetime.now(timezone.utc)

        logger.info("=" * 70)
        logger.info("G2-C ALPHA DAEMON v1.1 (LLM-INTEGRATED) STARTING")
        logger.info(f"Directive: {G2CConfig.DIRECTIVE_ID}")
        logger.info(f"Start: {self.start_time.isoformat()}")
        logger.info(f"LLM Research Interval: {G2CConfig.CRIO_RESEARCH_INTERVAL_SECONDS}s")
        logger.info(f"LLM Daily Budget: ${G2CConfig.LLM_BUDGET_DAILY_USD}")
        logger.info("=" * 70)

        try:
            self.connect()

            # Initial CRIO research (get LLM insights immediately)
            logger.info("Running initial CRIO research cycle...")
            self.run_crio_research()
            self.last_crio_research_time = datetime.now(timezone.utc)

            # Initial skill metrics computation
            self.compute_skill_metrics()

            cycle_count = 0
            status_interval = 300  # Print status every 5 minutes worth of cycles

            while self.running:
                self.reconnect_if_needed()
                now = datetime.now(timezone.utc)

                # 0. CRIO Research cycle (every 30 minutes) - LLM-powered
                if self.should_run_crio_research():
                    try:
                        self.run_crio_research()
                        self.last_crio_research_time = now
                    except Exception as e:
                        logger.error(f"CRIO research cycle error: {e}")

                # 1. Run forecast cycle (now LLM-informed)
                try:
                    generated = self.run_forecast_cycle()
                    if generated > 0:
                        llm_tag = "(LLM-informed)" if self.latest_crio_result else "(heuristic)"
                        logger.info(f"Generated {generated} new forecasts {llm_tag}")
                except Exception as e:
                    logger.error(f"Forecast cycle error: {e}")

                # 2. Resolution check (every 5 minutes)
                if (self.last_resolution_time is None or
                    (now - self.last_resolution_time).total_seconds() >= G2CConfig.RESOLUTION_INTERVAL_SECONDS):
                    try:
                        resolved = self.resolve_expired_forecasts()
                        self.last_resolution_time = now
                    except Exception as e:
                        logger.error(f"Resolution cycle error: {e}")

                # 3. Skill metrics update (every 10 minutes)
                if (self.last_skill_compute_time is None or
                    (now - self.last_skill_compute_time).total_seconds() >= G2CConfig.SKILL_COMPUTE_INTERVAL_SECONDS):
                    try:
                        self.compute_skill_metrics()
                        self.last_skill_compute_time = now
                    except Exception as e:
                        logger.error(f"Skill metrics error: {e}")

                cycle_count += 1

                # Print status periodically
                if cycle_count % status_interval == 0:
                    self.print_status()

                # Sleep before next cycle
                time.sleep(1)

            # Final status
            self.print_status()

            logger.info("=" * 70)
            logger.info("G2-C ALPHA DAEMON v1.1 - SHUTDOWN COMPLETE")
            logger.info("=" * 70)

            return {
                "success": True,
                "uptime_hours": (datetime.now(timezone.utc) - self.start_time).total_seconds() / 3600,
                "forecast_counts": self.forecast_counts,
                "resolutions": self.resolution_count,
                "outcomes": self.outcome_count,
                "crio_research_cycles": self.crio_research_count,
                "llm_informed": self.latest_crio_result is not None
            }

        except Exception as e:
            logger.error(f"Daemon failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

        finally:
            self.close()


# =================================================================
# MAIN
# =================================================================

def main():
    """Main entry point"""
    daemon = G2CAlphaDaemon()
    result = daemon.run()

    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
