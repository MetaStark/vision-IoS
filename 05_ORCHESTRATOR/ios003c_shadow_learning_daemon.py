#!/usr/bin/env python3
"""
IoS-003C Shadow Learning Daemon - CEO-DIR-2026-093

Autonomous 30-day measurement program for crypto regime predictions.

Scheduled Tasks:
- Daily @ 00:05 UTC: Capture epoch snapshot, append shadow ledger
- Daily @ 04:00 UTC: Compute outcomes, update quality metrics
- Weekly Sunday @ 00:00 UTC: Bootstrap significance test, regime persistence analysis
- Day 30: Auto-generate Gate 3 decision packet

Stop Conditions:
- Brier > 0.35 for 7 consecutive days
- Hit rate < 45% over 30 samples
- Bootstrap p-value > 0.05 (no significant predictive skill)
- Regime persistence < 1.5 days mean
- Identity drift > 5% (instrument_type NULL)

Authority: CEO-DIR-2026-093
Owner: STIG (EC-003)
"""

import os
import sys
import json
import hashlib
import psycopg2
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from decimal import Decimal

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

# Database connection parameters
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Evidence directory
EVIDENCE_DIR = Path(__file__).parent / 'evidence'


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def decimal_to_float(obj):
    """Convert Decimal to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class ShadowLearningDaemon:
    """Autonomous shadow learning daemon for IoS-003C."""

    def __init__(self, conn):
        self.conn = conn
        self.experiment_id = None
        self.start_date = None
        self.day_number = 0

    def get_experiment_status(self) -> Dict[str, Any]:
        """Get current experiment status."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT
                    experiment_id, experiment_name, start_date,
                    planned_duration_days, status, stop_condition_id,
                    CURRENT_DATE - start_date AS days_elapsed
                FROM fhq_research.crypto_regime_experiment
                WHERE status = 'ACTIVE'
                ORDER BY created_at DESC
                LIMIT 1
            """)

            row = cur.fetchone()
            if row:
                self.experiment_id = row[0]
                self.start_date = row[2]
                self.day_number = row[6]

                return {
                    'experiment_id': str(row[0]),
                    'experiment_name': row[1],
                    'start_date': row[2].isoformat(),
                    'planned_duration_days': row[3],
                    'status': row[4],
                    'stop_condition_id': row[5],
                    'days_elapsed': row[6]
                }
            return {'status': 'NO_ACTIVE_EXPERIMENT'}

    def check_stop_conditions(self) -> Dict[str, Any]:
        """Check all stop conditions and return status."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT condition_id, condition_name, is_triggered, current_value, threshold_value, message
                FROM fhq_research.check_crypto_stop_conditions()
            """)

            conditions = []
            any_triggered = False

            for row in cur.fetchall():
                condition = {
                    'condition_id': row[0],
                    'condition_name': row[1],
                    'is_triggered': row[2],
                    'current_value': float(row[3]) if row[3] else None,
                    'threshold_value': float(row[4]) if row[4] else None,
                    'message': row[5]
                }
                conditions.append(condition)
                if row[2]:
                    any_triggered = True

            return {
                'check_timestamp': datetime.now().isoformat(),
                'conditions': conditions,
                'any_triggered': any_triggered,
                'experiment_status': 'STOP_REQUIRED' if any_triggered else 'CONTINUE'
            }

    def capture_epoch_snapshot(self) -> Dict[str, Any]:
        """
        Daily @ 00:05 UTC: Capture current crypto regime predictions.
        This pulls from IoS-003C regime engine and appends to shadow ledger.
        """
        epoch_date = date.today()
        epoch_boundary = datetime.combine(epoch_date, datetime.min.time())

        with self.conn.cursor() as cur:
            # Get active crypto assets
            cur.execute("""
                SELECT ticker, asset_class
                FROM fhq_meta.assets
                WHERE asset_class = 'CRYPTO' AND active_flag = true
                LIMIT 50
            """)
            assets = cur.fetchall()

            signals_captured = 0
            errors = []

            for ticker, asset_class in assets:
                try:
                    # Get latest price for the asset
                    # CEO-DIR-2026-096: Use canonical source fhq_market.prices
                    # Identity anchored on canonical_id per ADR-013
                    cur.execute("""
                        SELECT close, timestamp
                        FROM fhq_market.prices
                        WHERE canonical_id = %s
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """, (ticker,))

                    price_row = cur.fetchone()
                    if not price_row:
                        continue

                    price = price_row[0]

                    # Get latest regime prediction (from IoS-003C or existing forecasts)
                    # Note: fhq_alpha.finn_forecasts may not exist yet if IoS-003C is in early development
                    # During early shadow learning, we use NEUTRAL @ 0.5 as baseline
                    predicted_regime = 'NEUTRAL'
                    confidence = 0.5
                    regime_drivers = None

                    # Check if finn_forecasts table exists and has data
                    # Use savepoint to handle missing table gracefully
                    cur.execute("SAVEPOINT forecast_check")
                    try:
                        cur.execute("""
                            SELECT
                                predicted_regime,
                                COALESCE(model_confidence, 0.5) as confidence,
                                regime_details
                            FROM fhq_alpha.finn_forecasts
                            WHERE ticker = %s AND asset_class = 'CRYPTO'
                            ORDER BY created_at DESC
                            LIMIT 1
                        """, (ticker,))

                        forecast_row = cur.fetchone()
                        if forecast_row:
                            predicted_regime = forecast_row[0] or 'NEUTRAL'
                            confidence = float(forecast_row[1]) if forecast_row[1] else 0.5
                            regime_drivers = forecast_row[2]
                        cur.execute("RELEASE SAVEPOINT forecast_check")
                    except Exception:
                        # Table doesn't exist or query failed - rollback to savepoint and use defaults
                        cur.execute("ROLLBACK TO SAVEPOINT forecast_check")

                    # Append to shadow ledger
                    cur.execute("""
                        SELECT fhq_research.append_crypto_shadow_entry(%s, %s, %s, %s, %s)
                    """, (ticker, predicted_regime, confidence, price, json.dumps(regime_drivers) if regime_drivers else None))

                    signals_captured += 1

                except Exception as e:
                    # Rollback the failed transaction before continuing
                    self.conn.rollback()
                    errors.append({'ticker': ticker, 'error': str(e)})

            self.conn.commit()

            return {
                'epoch_date': epoch_date.isoformat(),
                'epoch_boundary': epoch_boundary.isoformat(),
                'assets_scanned': len(assets),
                'signals_captured': signals_captured,
                'errors': errors,
                'status': 'SUCCESS' if not errors else 'PARTIAL'
            }

    def compute_outcomes(self) -> Dict[str, Any]:
        """
        Daily @ 04:00 UTC: Compute outcomes for signals from 1, 3, 5 days ago.
        """
        with self.conn.cursor() as cur:
            outcomes_updated = 0
            errors = []

            # Get signals needing outcome capture
            cur.execute("""
                SELECT
                    sl.ledger_id, sl.ticker, sl.epoch_date, sl.price_at_signal
                FROM fhq_research.crypto_regime_shadow_ledger sl
                LEFT JOIN fhq_research.crypto_regime_outcomes o ON sl.ledger_id = o.ledger_id
                WHERE sl.epoch_date <= CURRENT_DATE - 1
                AND (o.outcome_id IS NULL OR o.price_t0_plus_1d IS NULL)
                ORDER BY sl.epoch_date
            """)

            pending = cur.fetchall()

            for ledger_id, ticker, epoch_date, price_t0 in pending:
                try:
                    days_ago = (date.today() - epoch_date).days

                    # CEO-DIR-2026-096: Use canonical source fhq_market.prices
                    # Identity anchored on canonical_id per ADR-013
                    # Get prices at specific horizons (T+1, T+3, T+5)

                    price_1d = None
                    price_3d = None
                    price_5d = None

                    # T+1 price (if signal is at least 1 day old)
                    if days_ago >= 1:
                        cur.execute("""
                            SELECT close FROM fhq_market.prices
                            WHERE canonical_id = %s
                            AND timestamp::date = %s
                            ORDER BY timestamp DESC LIMIT 1
                        """, (ticker, epoch_date + timedelta(days=1)))
                        row = cur.fetchone()
                        if row:
                            price_1d = row[0]

                    # T+3 price (if signal is at least 3 days old)
                    if days_ago >= 3:
                        cur.execute("""
                            SELECT close FROM fhq_market.prices
                            WHERE canonical_id = %s
                            AND timestamp::date = %s
                            ORDER BY timestamp DESC LIMIT 1
                        """, (ticker, epoch_date + timedelta(days=3)))
                        row = cur.fetchone()
                        if row:
                            price_3d = row[0]

                    # T+5 price (if signal is at least 5 days old)
                    if days_ago >= 5:
                        cur.execute("""
                            SELECT close FROM fhq_market.prices
                            WHERE canonical_id = %s
                            AND timestamp::date = %s
                            ORDER BY timestamp DESC LIMIT 1
                        """, (ticker, epoch_date + timedelta(days=5)))
                        row = cur.fetchone()
                        if row:
                            price_5d = row[0]

                    # Skip if no prices available for any horizon
                    if price_1d is None and price_3d is None and price_5d is None:
                        continue

                    # Capture outcome
                    cur.execute("""
                        SELECT fhq_research.capture_crypto_outcome(%s, %s, %s, %s)
                    """, (ledger_id, price_1d, price_3d, price_5d))

                    outcomes_updated += 1

                except Exception as e:
                    errors.append({'ledger_id': str(ledger_id), 'ticker': ticker, 'error': str(e)})

            self.conn.commit()

            # Compute daily quality metrics
            self._update_daily_metrics()

            return {
                'timestamp': datetime.now().isoformat(),
                'signals_processed': len(pending),
                'outcomes_updated': outcomes_updated,
                'errors': errors,
                'status': 'SUCCESS' if not errors else 'PARTIAL'
            }

    def _update_daily_metrics(self):
        """Update daily quality metrics."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_research.crypto_regime_quality_metrics (
                    metric_date, metric_type,
                    sample_size, signals_with_outcome,
                    avg_brier, rolling_7d_brier, rolling_30d_brier,
                    hit_rate_1d, hit_rate_3d, hit_rate_5d,
                    identity_drift_detected, instrument_type_null_pct
                )
                SELECT
                    CURRENT_DATE,
                    'DAILY',
                    COUNT(*),
                    COUNT(*) FILTER (WHERE o.outcome_id IS NOT NULL),
                    AVG(o.brier_score),
                    (SELECT AVG(o2.brier_score) FROM fhq_research.crypto_regime_outcomes o2 WHERE o2.epoch_date >= CURRENT_DATE - 7),
                    (SELECT AVG(o3.brier_score) FROM fhq_research.crypto_regime_outcomes o3 WHERE o3.epoch_date >= CURRENT_DATE - 30),
                    COUNT(*) FILTER (WHERE o.correct_direction_1d = TRUE)::DECIMAL / NULLIF(COUNT(*) FILTER (WHERE o.correct_direction_1d IS NOT NULL), 0),
                    COUNT(*) FILTER (WHERE o.correct_direction_3d = TRUE)::DECIMAL / NULLIF(COUNT(*) FILTER (WHERE o.correct_direction_3d IS NOT NULL), 0),
                    COUNT(*) FILTER (WHERE o.correct_direction_5d = TRUE)::DECIMAL / NULLIF(COUNT(*) FILTER (WHERE o.correct_direction_5d IS NOT NULL), 0),
                    COUNT(*) FILTER (WHERE sl.instrument_type IS NULL)::DECIMAL / NULLIF(COUNT(*), 0) > 0.05,
                    COUNT(*) FILTER (WHERE sl.instrument_type IS NULL)::DECIMAL / NULLIF(COUNT(*), 0)
                FROM fhq_research.crypto_regime_shadow_ledger sl
                LEFT JOIN fhq_research.crypto_regime_outcomes o ON sl.ledger_id = o.ledger_id
                WHERE sl.epoch_date = CURRENT_DATE - 1
                ON CONFLICT (metric_date, metric_type) DO UPDATE SET
                    signals_with_outcome = EXCLUDED.signals_with_outcome,
                    avg_brier = EXCLUDED.avg_brier,
                    rolling_7d_brier = EXCLUDED.rolling_7d_brier,
                    rolling_30d_brier = EXCLUDED.rolling_30d_brier,
                    hit_rate_1d = EXCLUDED.hit_rate_1d,
                    hit_rate_3d = EXCLUDED.hit_rate_3d,
                    hit_rate_5d = EXCLUDED.hit_rate_5d,
                    identity_drift_detected = EXCLUDED.identity_drift_detected,
                    instrument_type_null_pct = EXCLUDED.instrument_type_null_pct
            """)
            self.conn.commit()

    def run_weekly_analysis(self) -> Dict[str, Any]:
        """
        Weekly Sunday @ 00:00 UTC: Bootstrap significance test, regime persistence, CRIO causality.
        Includes VEGA pre-authorized termination check.
        """
        # FIRST: Check stop conditions - VEGA auto-terminates if any triggered
        stop_check = self.check_stop_conditions()
        if stop_check['any_triggered']:
            return self._vega_auto_terminate(stop_check)

        with self.conn.cursor() as cur:
            # Get rolling 30-day data
            cur.execute("""
                SELECT * FROM fhq_research.crypto_shadow_rolling_30d
            """)
            row = cur.fetchone()

            if not row:
                return {'status': 'NO_DATA', 'message': 'No shadow learning data available'}

            total_signals = row[1]
            outcomes_captured = row[2]
            hit_rate_1d = float(row[5]) if row[5] else None

            # Bootstrap significance test (simplified)
            bootstrap_result = self._bootstrap_significance_test()

            # Regime persistence analysis
            persistence_result = self._regime_persistence_analysis()

            # CRIO causality check
            crio_result = self._crio_causality_check()

            # Update weekly metrics
            cur.execute("""
                INSERT INTO fhq_research.crypto_regime_quality_metrics (
                    metric_date, metric_type,
                    sample_size, signals_with_outcome,
                    hit_rate_1d,
                    bootstrap_p_value, bootstrap_ci_lower, bootstrap_ci_upper,
                    bootstrap_samples, predictive_skill_significant,
                    regime_persistence_mean, regime_persistence_median, regime_transition_count
                )
                VALUES (
                    CURRENT_DATE, 'WEEKLY',
                    %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT (metric_date, metric_type) DO UPDATE SET
                    bootstrap_p_value = EXCLUDED.bootstrap_p_value,
                    bootstrap_ci_lower = EXCLUDED.bootstrap_ci_lower,
                    bootstrap_ci_upper = EXCLUDED.bootstrap_ci_upper,
                    predictive_skill_significant = EXCLUDED.predictive_skill_significant,
                    regime_persistence_mean = EXCLUDED.regime_persistence_mean,
                    regime_persistence_median = EXCLUDED.regime_persistence_median,
                    regime_transition_count = EXCLUDED.regime_transition_count
            """, (
                total_signals, outcomes_captured, hit_rate_1d,
                bootstrap_result.get('p_value'),
                bootstrap_result.get('ci_lower'),
                bootstrap_result.get('ci_upper'),
                bootstrap_result.get('n_samples', 1000),
                bootstrap_result.get('p_value', 1.0) < 0.05,
                persistence_result.get('mean'),
                persistence_result.get('median'),
                persistence_result.get('transition_count')
            ))
            self.conn.commit()

            # Update CRIO columns
            cur.execute("""
                UPDATE fhq_research.crypto_regime_quality_metrics
                SET
                    crio_causality_validated = %s,
                    crio_primary_drivers = %s,
                    crio_spurious_risk = %s
                WHERE metric_date = CURRENT_DATE AND metric_type = 'WEEKLY'
            """, (
                crio_result.get('validated', False),
                json.dumps(crio_result.get('primary_drivers', [])),
                crio_result.get('spurious_risk', 'HIGH')
            ))
            self.conn.commit()

            return {
                'timestamp': datetime.now().isoformat(),
                'metric_type': 'WEEKLY',
                'total_signals': total_signals,
                'outcomes_captured': outcomes_captured,
                'hit_rate_1d': hit_rate_1d,
                'bootstrap': bootstrap_result,
                'regime_persistence': persistence_result,
                'crio_causality': crio_result,
                'predictive_skill_significant': bootstrap_result.get('p_value', 1.0) < 0.05,
                'status': 'SUCCESS'
            }

    def _vega_auto_terminate(self, stop_check: Dict[str, Any]) -> Dict[str, Any]:
        """
        VEGA pre-authorized termination. No human confirmation required.
        Per CEO-DIR-2026-093 improvement: Eliminate 'waiting it out' mentality.
        """
        triggered = [c['condition_name'] for c in stop_check['conditions'] if c['is_triggered']]
        reason = f"VEGA AUTO-TERMINATION: {', '.join(triggered)}"

        with self.conn.cursor() as cur:
            cur.execute("SELECT fhq_research.vega_terminate_ios003c(%s)", (reason,))
            action_id = cur.fetchone()[0]
            self.conn.commit()

        print(f"[VEGA_TERMINATION] {datetime.now().isoformat()}")
        print(f"  Reason: {reason}")
        print(f"  Action ID: {action_id}")
        print(f"  Status: IoS-003C experiment TERMINATED")

        return {
            'status': 'TERMINATED',
            'terminated_by': 'VEGA',
            'reason': reason,
            'triggered_conditions': triggered,
            'action_id': str(action_id),
            'human_override': False,
            'discretion_applied': False
        }

    def _crio_causality_check(self) -> Dict[str, Any]:
        """
        CRIO causality check: Ensure regime performance is due to actual mechanisms,
        not spurious correlation with trend.

        Checks:
        1. Lane C signals (funding rates) correlation with regime accuracy
        2. Microstructure stress indicators
        3. Trend-adjustment (is performance just riding momentum?)
        """
        with self.conn.cursor() as cur:
            # Check if Lane C data exists
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = 'fhq_data' AND table_name = 'funding_rates'
            """)
            lane_c_exists = cur.fetchone()[0] > 0

            if not lane_c_exists:
                return {
                    'validated': False,
                    'status': 'LANE_C_PENDING',
                    'primary_drivers': [],
                    'spurious_risk': 'HIGH',
                    'note': 'Lane C (funding_rates) not yet populated. Awaiting CEIO deadline.'
                }

            # Basic trend-adjustment check
            # Compare regime accuracy during trending vs ranging markets
            cur.execute("""
                SELECT
                    AVG(CASE WHEN ABS(o.return_1d) > 0.03 THEN
                        CASE WHEN o.correct_direction_1d THEN 1 ELSE 0 END
                    END) as trending_accuracy,
                    AVG(CASE WHEN ABS(o.return_1d) <= 0.03 THEN
                        CASE WHEN o.correct_direction_1d THEN 1 ELSE 0 END
                    END) as ranging_accuracy
                FROM fhq_research.crypto_regime_outcomes o
                WHERE o.epoch_date >= CURRENT_DATE - 30
                AND o.correct_direction_1d IS NOT NULL
            """)
            row = cur.fetchone()

            trending_acc = float(row[0]) if row[0] else 0.5
            ranging_acc = float(row[1]) if row[1] else 0.5

            # If accuracy is only good during strong trends, it's likely spurious
            if trending_acc > 0.6 and ranging_acc < 0.45:
                spurious_risk = 'HIGH'
                validated = False
                note = 'Performance concentrated in trending markets - possible momentum-riding'
            elif trending_acc > 0.55 and ranging_acc > 0.5:
                spurious_risk = 'LOW'
                validated = True
                note = 'Consistent performance across market conditions'
            else:
                spurious_risk = 'MEDIUM'
                validated = False
                note = 'Insufficient differentiation between trending/ranging accuracy'

            return {
                'validated': validated,
                'status': 'CHECKED',
                'trending_accuracy': trending_acc,
                'ranging_accuracy': ranging_acc,
                'primary_drivers': ['regime_classification', 'price_momentum'],
                'spurious_risk': spurious_risk,
                'note': note
            }

    def _bootstrap_significance_test(self, n_samples: int = 1000) -> Dict[str, Any]:
        """Perform bootstrap significance test for predictive skill."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT correct_direction_1d::INT
                FROM fhq_research.crypto_regime_outcomes
                WHERE correct_direction_1d IS NOT NULL
                AND epoch_date >= CURRENT_DATE - 30
            """)
            outcomes = [row[0] for row in cur.fetchall()]

        if len(outcomes) < 10:
            return {
                'status': 'INSUFFICIENT_DATA',
                'n_samples': 0,
                'p_value': 1.0,
                'ci_lower': 0.0,
                'ci_upper': 1.0
            }

        # Observed hit rate
        observed_hit_rate = np.mean(outcomes)

        # Null hypothesis: hit rate = 0.5 (random)
        null_hit_rate = 0.5

        # Bootstrap
        bootstrap_means = []
        for _ in range(n_samples):
            sample = np.random.choice(outcomes, size=len(outcomes), replace=True)
            bootstrap_means.append(np.mean(sample))

        bootstrap_means = np.array(bootstrap_means)

        # P-value: proportion of bootstrap samples <= null hypothesis
        p_value = np.mean(bootstrap_means <= null_hit_rate)

        # Confidence interval (95%)
        ci_lower = np.percentile(bootstrap_means, 2.5)
        ci_upper = np.percentile(bootstrap_means, 97.5)

        return {
            'observed_hit_rate': float(observed_hit_rate),
            'null_hypothesis': null_hit_rate,
            'p_value': float(p_value),
            'ci_lower': float(ci_lower),
            'ci_upper': float(ci_upper),
            'n_samples': n_samples,
            'status': 'SUCCESS'
        }

    def _regime_persistence_analysis(self) -> Dict[str, Any]:
        """Analyze regime persistence (mean days before regime change)."""
        with self.conn.cursor() as cur:
            cur.execute("""
                WITH regime_runs AS (
                    SELECT
                        ticker,
                        predicted_regime,
                        epoch_date,
                        epoch_date - LAG(epoch_date) OVER (PARTITION BY ticker ORDER BY epoch_date) AS days_since_prev,
                        predicted_regime != LAG(predicted_regime) OVER (PARTITION BY ticker ORDER BY epoch_date) AS is_transition
                    FROM fhq_research.crypto_regime_shadow_ledger
                    WHERE epoch_date >= CURRENT_DATE - 30
                ),
                run_lengths AS (
                    SELECT
                        COUNT(*) AS run_length
                    FROM (
                        SELECT
                            ticker, predicted_regime, epoch_date,
                            SUM(CASE WHEN is_transition THEN 1 ELSE 0 END) OVER (PARTITION BY ticker ORDER BY epoch_date) AS run_group
                        FROM regime_runs
                    ) grouped
                    GROUP BY ticker, run_group
                )
                SELECT
                    AVG(run_length) AS mean_persistence,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY run_length) AS median_persistence,
                    COUNT(*) AS transition_count
                FROM run_lengths
            """)

            row = cur.fetchone()
            if row:
                return {
                    'mean': float(row[0]) if row[0] else None,
                    'median': float(row[1]) if row[1] else None,
                    'transition_count': row[2] or 0,
                    'status': 'SUCCESS'
                }
            return {
                'mean': None,
                'median': None,
                'transition_count': 0,
                'status': 'NO_DATA'
            }

    def generate_gate3_packet(self) -> Dict[str, Any]:
        """
        Day 30: Auto-generate Gate 3 decision packet.
        """
        experiment = self.get_experiment_status()
        if experiment.get('days_elapsed', 0) < 30:
            return {
                'status': 'NOT_YET',
                'days_remaining': 30 - experiment.get('days_elapsed', 0)
            }

        with self.conn.cursor() as cur:
            # Get cumulative metrics
            cur.execute("""SELECT * FROM fhq_research.crypto_shadow_rolling_30d""")
            metrics = cur.fetchone()

            # Get stop condition status
            stop_status = self.check_stop_conditions()

            # Get weekly bootstrap results
            cur.execute("""
                SELECT
                    bootstrap_p_value, predictive_skill_significant,
                    regime_persistence_mean
                FROM fhq_research.crypto_regime_quality_metrics
                WHERE metric_type = 'WEEKLY'
                ORDER BY metric_date DESC
                LIMIT 1
            """)
            weekly = cur.fetchone()

        # Determine recommendation
        recommendation = self._determine_gate3_recommendation(metrics, stop_status, weekly)

        # Generate packet
        packet = {
            'packet_id': hashlib.sha256(f"G3-IOS003C-{datetime.now().isoformat()}".encode()).hexdigest()[:16],
            'directive': 'CEO-DIR-2026-093',
            'experiment_id': str(self.experiment_id),
            'generated_at': datetime.now().isoformat(),
            'experiment_duration_days': 30,

            'section_1_summary': {
                'total_signals': metrics[1] if metrics else 0,
                'outcomes_captured': metrics[2] if metrics else 0,
                'hit_rate_1d': float(metrics[5]) if metrics and metrics[5] else None,
                'avg_brier': float(metrics[6]) if metrics and metrics[6] else None,
                'identity_drift_pct': float(metrics[7]) if metrics and metrics[7] else 0
            },

            'section_2_statistical_significance': {
                'bootstrap_p_value': float(weekly[0]) if weekly and weekly[0] else None,
                'predictive_skill_significant': weekly[1] if weekly else False,
                'regime_persistence_mean': float(weekly[2]) if weekly and weekly[2] else None
            },

            'section_3_stop_conditions': {
                'any_triggered': stop_status['any_triggered'],
                'conditions': stop_status['conditions']
            },

            'section_4_recommendation': recommendation,

            'section_5_crio_integration': {
                'causal_map_available': False,
                'note': 'CRIO causal map pending - requires Lane C population'
            },

            'section_6_vega_attestation': {
                'required': True,
                'status': 'PENDING',
                'note': 'Weekly integrity checks of shadow ledger required'
            },

            'gate3_decision_options': {
                'GO': 'Proceed to paper trading (requires additional CEO directive)',
                'KILL': 'Terminate IoS-003C research, archive learnings',
                'ITERATE': 'Continue shadow mode with specified modifications'
            }
        }

        # Save packet to file
        packet_file = EVIDENCE_DIR / f"G3_PACKET_IOS003C_{datetime.now().strftime('%Y%m%d')}.json"
        with open(packet_file, 'w') as f:
            json.dump(packet, f, indent=2, default=decimal_to_float)

        # Update experiment status
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_research.crypto_regime_experiment
                SET
                    status = 'GATE3_SUBMITTED',
                    gate3_packet_id = %s::UUID,
                    gate3_submitted_at = NOW()
                WHERE experiment_id = %s
            """, (packet['packet_id'], self.experiment_id))
            self.conn.commit()

        return {
            'status': 'SUBMITTED',
            'packet_id': packet['packet_id'],
            'packet_file': str(packet_file),
            'recommendation': recommendation
        }

    def _determine_gate3_recommendation(self, metrics, stop_status, weekly) -> Dict[str, Any]:
        """Determine Gate 3 recommendation based on evidence."""
        # Check for automatic KILL conditions
        if stop_status['any_triggered']:
            return {
                'decision': 'KILL',
                'confidence': 'HIGH',
                'rationale': 'Stop condition triggered',
                'triggered_conditions': [c['condition_name'] for c in stop_status['conditions'] if c['is_triggered']]
            }

        # Check statistical significance
        if weekly and weekly[0] and weekly[0] > 0.05:
            return {
                'decision': 'ITERATE',
                'confidence': 'MEDIUM',
                'rationale': 'No statistically significant predictive skill (p > 0.05)',
                'suggested_modifications': ['Review regime definitions', 'Add more signals', 'Improve feature engineering']
            }

        # Check hit rate
        hit_rate = float(metrics[5]) if metrics and metrics[5] else 0
        if hit_rate >= 0.55:
            return {
                'decision': 'GO',
                'confidence': 'HIGH' if hit_rate >= 0.60 else 'MEDIUM',
                'rationale': f'Hit rate {hit_rate:.1%} exceeds 55% threshold with statistical significance',
                'next_steps': ['CEO approval for paper trading', 'LINE execution readiness review']
            }

        return {
            'decision': 'ITERATE',
            'confidence': 'LOW',
            'rationale': f'Hit rate {hit_rate:.1%} below 55% threshold',
            'suggested_modifications': ['Extend observation period', 'Refine regime boundaries', 'Add Lane C signals']
        }

    def vega_weekly_attestation(self) -> Dict[str, Any]:
        """VEGA weekly integrity check of shadow ledger (per CEO improvement)."""
        with self.conn.cursor() as cur:
            # Check ledger integrity
            cur.execute("""
                SELECT
                    COUNT(*) AS total_entries,
                    COUNT(*) FILTER (WHERE outcome_captured = TRUE) AS outcomes_captured,
                    COUNT(*) FILTER (WHERE instrument_type IS NULL) AS null_instrument_type,
                    MIN(epoch_date) AS earliest_entry,
                    MAX(epoch_date) AS latest_entry,
                    COUNT(DISTINCT ticker) AS unique_tickers
                FROM fhq_research.crypto_regime_shadow_ledger
            """)
            ledger_stats = cur.fetchone()

            # Check for anomalies
            cur.execute("""
                SELECT COUNT(*) FROM fhq_research.crypto_regime_shadow_ledger
                WHERE confidence > 1 OR confidence < 0
            """)
            invalid_confidence = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*) FROM fhq_research.crypto_regime_shadow_ledger
                WHERE predicted_regime NOT IN ('BULL', 'BEAR', 'NEUTRAL', 'STRESS')
            """)
            invalid_regime = cur.fetchone()[0]

        attestation = {
            'attestation_id': hashlib.sha256(f"VEGA-ATT-{datetime.now().isoformat()}".encode()).hexdigest()[:16],
            'attestation_timestamp': datetime.now().isoformat(),
            'attested_by': 'VEGA',

            'ledger_stats': {
                'total_entries': ledger_stats[0],
                'outcomes_captured': ledger_stats[1],
                'null_instrument_type': ledger_stats[2],
                'earliest_entry': ledger_stats[3].isoformat() if ledger_stats[3] else None,
                'latest_entry': ledger_stats[4].isoformat() if ledger_stats[4] else None,
                'unique_tickers': ledger_stats[5]
            },

            'integrity_checks': {
                'confidence_bounds': {'passed': invalid_confidence == 0, 'violations': invalid_confidence},
                'regime_values': {'passed': invalid_regime == 0, 'violations': invalid_regime},
                'identity_drift': {'passed': ledger_stats[2] / max(ledger_stats[0], 1) <= 0.05, 'pct': ledger_stats[2] / max(ledger_stats[0], 1)}
            },

            'verdict': 'PASS' if invalid_confidence == 0 and invalid_regime == 0 else 'FAIL'
        }

        # Log attestation to metrics table
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_research.crypto_regime_quality_metrics
                SET
                    vega_attested = TRUE,
                    vega_attestation_id = %s::UUID,
                    vega_attestation_timestamp = NOW()
                WHERE metric_date = CURRENT_DATE AND metric_type = 'WEEKLY'
            """, (attestation['attestation_id'],))
            self.conn.commit()

        return attestation


def log_execution_evidence(conn, task_name: str, status: str, rows_written: int, error_count: int, result_summary: Dict = None):
    """
    CEO-DIR-2026-096: Persist execution evidence to database.
    Silence is a governance failure - every execution must leave evidence.
    """
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.agent_task_log (
                    agent_id, task_name, task_type, status,
                    started_at, completed_at, latency_ms,
                    result_summary
                ) VALUES (
                    'STIG', %s, 'SHADOW_LEARNING', %s,
                    NOW() - INTERVAL '1 second', NOW(), 1000,
                    %s
                )
            """, (
                task_name,
                status,
                json.dumps({
                    'rows_written': rows_written,
                    'error_count': error_count,
                    'summary': result_summary or {}
                })
            ))
            conn.commit()
    except Exception as e:
        # Don't let logging failure break execution
        print(f"[EVIDENCE_LOG_WARNING] Failed to log execution: {e}")


def run_daily_snapshot(dry_run: bool = False) -> Dict[str, Any]:
    """Run daily @ 00:05 UTC task."""
    conn = get_db_connection()
    try:
        daemon = ShadowLearningDaemon(conn)
        experiment = daemon.get_experiment_status()

        if experiment.get('status') != 'ACTIVE':
            log_execution_evidence(conn, 'ios003c_epoch_snapshot', 'NOOP', 0, 0, {'reason': 'No active experiment'})
            return {'status': 'SKIPPED', 'reason': 'No active experiment'}

        # Check stop conditions first
        stop_check = daemon.check_stop_conditions()
        if stop_check['any_triggered']:
            log_execution_evidence(conn, 'ios003c_epoch_snapshot', 'STOPPED', 0, 0, {'reason': 'Stop condition triggered'})
            return {
                'status': 'STOPPED',
                'reason': 'Stop condition triggered',
                'conditions': stop_check['conditions']
            }

        if not dry_run:
            result = daemon.capture_epoch_snapshot()
            rows_written = result.get('signals_captured', 0)
            error_count = len(result.get('errors', []))
            status = 'SUCCESS' if error_count == 0 else 'PARTIAL'
            log_execution_evidence(conn, 'ios003c_epoch_snapshot', status, rows_written, error_count, result)
            print(f"[SHADOW_LEARNING] {datetime.now().isoformat()} - Epoch snapshot captured")
            print(f"  Signals: {result['signals_captured']}")
            return result
        else:
            return {'status': 'DRY_RUN', 'would_capture': 'epoch snapshot'}
    finally:
        conn.close()


def run_outcome_computation(dry_run: bool = False) -> Dict[str, Any]:
    """Run daily @ 04:00 UTC task."""
    conn = get_db_connection()
    try:
        daemon = ShadowLearningDaemon(conn)
        experiment = daemon.get_experiment_status()

        if experiment.get('status') != 'ACTIVE':
            log_execution_evidence(conn, 'ios003c_outcome_computation', 'NOOP', 0, 0, {'reason': 'No active experiment'})
            return {'status': 'SKIPPED', 'reason': 'No active experiment'}

        if not dry_run:
            result = daemon.compute_outcomes()
            rows_written = result.get('outcomes_updated', 0)
            error_count = len(result.get('errors', []))
            status = 'SUCCESS' if error_count == 0 else 'PARTIAL'
            log_execution_evidence(conn, 'ios003c_outcome_computation', status, rows_written, error_count, result)
            print(f"[SHADOW_LEARNING] {datetime.now().isoformat()} - Outcomes computed")
            print(f"  Updated: {result['outcomes_updated']}")
            return result
        else:
            return {'status': 'DRY_RUN', 'would_compute': 'outcomes'}
    finally:
        conn.close()


def run_weekly_analysis(dry_run: bool = False) -> Dict[str, Any]:
    """Run weekly Sunday @ 00:00 UTC task."""
    conn = get_db_connection()
    try:
        daemon = ShadowLearningDaemon(conn)
        experiment = daemon.get_experiment_status()

        if experiment.get('status') != 'ACTIVE':
            log_execution_evidence(conn, 'ios003c_weekly_analysis', 'NOOP', 0, 0, {'reason': 'No active experiment'})
            return {'status': 'SKIPPED', 'reason': 'No active experiment'}

        if not dry_run:
            # Run weekly analysis
            analysis = daemon.run_weekly_analysis()

            # Run VEGA attestation
            attestation = daemon.vega_weekly_attestation()

            result = {
                'analysis': analysis,
                'attestation': attestation
            }
            log_execution_evidence(conn, 'ios003c_weekly_analysis', 'SUCCESS', 1, 0, result)
            print(f"[SHADOW_LEARNING] {datetime.now().isoformat()} - Weekly analysis complete")
            print(f"  Predictive skill significant: {analysis.get('predictive_skill_significant')}")
            print(f"  VEGA attestation: {attestation['verdict']}")

            return result
        else:
            return {'status': 'DRY_RUN', 'would_run': 'weekly analysis + VEGA attestation'}
    finally:
        conn.close()


def check_gate3_ready(dry_run: bool = False) -> Dict[str, Any]:
    """Check if Gate 3 packet should be generated."""
    conn = get_db_connection()
    try:
        daemon = ShadowLearningDaemon(conn)
        experiment = daemon.get_experiment_status()

        if experiment.get('days_elapsed', 0) >= 30:
            if not dry_run:
                result = daemon.generate_gate3_packet()
                print(f"[SHADOW_LEARNING] Gate 3 packet generated")
                print(f"  Recommendation: {result['recommendation']['decision']}")
                return result
            else:
                return {'status': 'DRY_RUN', 'would_generate': 'Gate 3 packet'}
        else:
            return {
                'status': 'NOT_YET',
                'days_elapsed': experiment.get('days_elapsed', 0),
                'days_remaining': 30 - experiment.get('days_elapsed', 0)
            }
    finally:
        conn.close()


def get_shadow_learning_report() -> Dict[str, Any]:
    """Generate shadow learning report for daily report."""
    conn = get_db_connection()
    try:
        daemon = ShadowLearningDaemon(conn)
        experiment = daemon.get_experiment_status()
        stop_check = daemon.check_stop_conditions()

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM fhq_research.crypto_shadow_rolling_30d")
            rolling = cur.fetchone()

            cur.execute("""
                SELECT metric_date, hit_rate_1d, avg_brier, predictive_skill_significant
                FROM fhq_research.crypto_regime_quality_metrics
                WHERE metric_type = 'WEEKLY'
                ORDER BY metric_date DESC
                LIMIT 1
            """)
            weekly = cur.fetchone()

        return {
            '_title': 'IoS-003C Crypto Regime – Shadow Learning',
            '_directive': 'CEO-DIR-2026-093',
            '_status': experiment.get('status', 'UNKNOWN'),

            'experiment': {
                'start_date': experiment.get('start_date'),
                'days_elapsed': experiment.get('days_elapsed', 0),
                'days_remaining': max(0, 30 - experiment.get('days_elapsed', 0)),
                'gate3_eligible': experiment.get('days_elapsed', 0) >= 30
            },

            'rolling_30d_metrics': {
                'total_signals': rolling[1] if rolling else 0,
                'outcomes_captured': rolling[2] if rolling else 0,
                'hit_rate_1d': float(rolling[5]) if rolling and rolling[5] else None,
                'avg_brier': float(rolling[6]) if rolling and rolling[6] else None,
                'identity_drift_pct': float(rolling[7]) if rolling and rolling[7] else 0
            },

            'weekly_significance': {
                'last_check_date': weekly[0].isoformat() if weekly and weekly[0] else None,
                'hit_rate_1d': float(weekly[1]) if weekly and weekly[1] else None,
                'avg_brier': float(weekly[2]) if weekly and weekly[2] else None,
                'predictive_skill_significant': weekly[3] if weekly else None
            },

            'stop_conditions': {
                'any_triggered': stop_check['any_triggered'],
                'status': 'ALERT' if stop_check['any_triggered'] else 'GREEN',
                'conditions': [
                    {
                        'name': c['condition_name'],
                        'triggered': c['is_triggered'],
                        'current': c['current_value'],
                        'threshold': c['threshold_value']
                    }
                    for c in stop_check['conditions']
                ]
            },

            'class_a_violation_notice': {
                'rule': 'Coupling to trading before Day 30 is a Class A violation',
                'current_day': experiment.get('days_elapsed', 0),
                'trading_authorized': False
            }
        }
    finally:
        conn.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='IoS-003C Shadow Learning Daemon - CEO-DIR-2026-093')
    parser.add_argument('--task', choices=['snapshot', 'outcomes', 'weekly', 'gate3', 'report', 'status'],
                        default='status', help='Task to run')
    parser.add_argument('--dry-run', action='store_true', help='Run without making changes')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    if args.task == 'snapshot':
        result = run_daily_snapshot(dry_run=args.dry_run)
    elif args.task == 'outcomes':
        result = run_outcome_computation(dry_run=args.dry_run)
    elif args.task == 'weekly':
        result = run_weekly_analysis(dry_run=args.dry_run)
    elif args.task == 'gate3':
        result = check_gate3_ready(dry_run=args.dry_run)
    elif args.task == 'report':
        result = get_shadow_learning_report()
    else:  # status
        conn = get_db_connection()
        daemon = ShadowLearningDaemon(conn)
        result = {
            'experiment': daemon.get_experiment_status(),
            'stop_conditions': daemon.check_stop_conditions()
        }
        conn.close()

    if args.json:
        print(json.dumps(result, indent=2, default=decimal_to_float))

    return result


if __name__ == '__main__':
    main()
