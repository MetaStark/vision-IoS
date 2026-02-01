#!/usr/bin/env python3
"""
EQS v2 Calculator - Rank-Based Evidence Quality Scoring

Author: FINN (Financial Investments Neural Network)
Date: 2025-12-26
Updated: 2025-12-26 by STIG (VEGA Conditions C1 & C2)
Purpose: Implement rank-based EQS to break the score collapse

This module calculates EQS v2 using percentile-based relative ranking
instead of absolute thresholds, creating meaningful discrimination even
under constrained conditions (single asset, single regime).

VEGA CONDITIONS IMPLEMENTED:
- C1: Hard Stop when regime diversity < 15% (RegimeDiversityError)
- C2: Court-proof calculation logging to vision_verification.eqs_v2_calculation_log
"""

import psycopg2
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json
import hashlib
import uuid


class RegimeDiversityError(Exception):
    """
    VEGA Condition C1: Raised when regime diversity is insufficient for EQS v2 scoring.

    Hard Stop is triggered when non-dominant regime < 15% of total signals.
    This prevents EQS v2 from running in degraded mode without explicit warning.

    Per VEGA G3 Audit (2025-12-26):
    - Forces upstream fix (CEIO/CDMO must address regime classifier)
    - Prevents degraded scores polluting historical record
    - Court-proof transparency (explicit error, auditable)
    - "Fail loudly, not quietly" (CEO principle)
    """

    def __init__(self, diversity_pct: float, threshold_pct: float, regime_distribution: Dict):
        self.diversity_pct = diversity_pct
        self.threshold_pct = threshold_pct
        self.regime_distribution = regime_distribution
        self.message = (
            f"REGIME DIVERSITY HARD STOP: Non-dominant regime at {diversity_pct:.2f}% "
            f"(required: >= {threshold_pct:.2f}%). "
            f"EQS v2 cannot operate without regime variance. "
            f"Distribution: {regime_distribution}. "
            f"Action: CEIO/CDMO must fix regime classifier."
        )
        super().__init__(self.message)


class EQSv2Calculator:
    """
    Calculate rank-based Evidence Quality Score (v2) for Golden Needles.

    Key differences from v1:
    - Uses percentile ranks instead of absolute thresholds
    - Exploits hidden dimensions: SITC completeness, factor patterns, categories, recency
    - Creates meaningful variance even when all signals pass similar quality gates
    """

    # Category strength weights (hypothesis-driven, to be validated)
    CATEGORY_STRENGTH = {
        "CATALYST_AMPLIFICATION": 1.00,
        "REGIME_EDGE": 0.95,
        "TIMING": 0.90,
        "VOLATILITY": 0.85,
        "MOMENTUM": 0.80,
        "BREAKOUT": 0.75,
        "MEAN_REVERSION": 0.70,
        "CONTRARIAN": 0.65,
        "CROSS_ASSET": 0.60,
        "TREND_FOLLOWING": 0.55,
        # Multi-category combinations get average of components
    }

    # Factor criticality weights (how much it hurts to miss this factor)
    FACTOR_CRITICALITY = {
        "price_technical": 1.0,
        "volume_confirmation": 0.9,
        "temporal_coherence": 0.9,
        "regime_alignment": 0.8,
        "testable_criteria": 0.8,
        "specific_testable": 0.7,
        "catalyst_present": 0.5,
    }

    # Scoring weights (adjusted to create meaningful spread)
    # Base score contributes 0.60, premiums contribute 0.40
    BASE_WEIGHT = 0.60
    WEIGHT_SITC = 0.15
    WEIGHT_FACTOR_QUALITY = 0.10
    WEIGHT_CATEGORY = 0.10
    WEIGHT_RECENCY = 0.05
    # Total: 0.60 + 0.40 = 1.00 max

    # VEGA Condition C1: Regime diversity threshold
    REGIME_DIVERSITY_THRESHOLD = 15.0  # Non-dominant regime must be >= 15%

    # Calculation version for audit trail (C2)
    CALCULATION_VERSION = "2.0.0"

    def __init__(self, db_conn, enforce_hard_stop: bool = True):
        """
        Initialize calculator with database connection.

        Args:
            db_conn: psycopg2 connection object
            enforce_hard_stop: If True, raise RegimeDiversityError when diversity < threshold (C1)
        """
        self.conn = db_conn
        self.enforce_hard_stop = enforce_hard_stop
        self._formula_hash = self._compute_formula_hash()

    def _compute_formula_hash(self) -> str:
        """Compute SHA-256 hash of the formula constants for reproducibility."""
        formula_components = {
            "base_weight": self.BASE_WEIGHT,
            "weight_sitc": self.WEIGHT_SITC,
            "weight_factor_quality": self.WEIGHT_FACTOR_QUALITY,
            "weight_category": self.WEIGHT_CATEGORY,
            "weight_recency": self.WEIGHT_RECENCY,
            "category_strength": self.CATEGORY_STRENGTH,
            "factor_criticality": self.FACTOR_CRITICALITY,
            "version": self.CALCULATION_VERSION,
        }
        formula_json = json.dumps(formula_components, sort_keys=True)
        return hashlib.sha256(formula_json.encode()).hexdigest()[:16]

    def check_regime_diversity(self) -> Dict:
        """
        VEGA Condition C1: Check if regime diversity is sufficient for EQS v2.

        Queries fhq_canonical.v_regime_diversity_status to determine if
        non-dominant regime >= 15% of total signals.

        Returns:
            Dict with:
            - sufficient: bool (True if diversity >= threshold)
            - non_dominant_pct: float (percentage of non-dominant regime)
            - dominant_regime: str (the dominant regime)
            - distribution: Dict (regime -> count mapping)
            - status: str (COLLAPSED, MARGINAL, FUNCTIONAL, OPTIMAL)
        """
        cursor = self.conn.cursor()

        # Query regime distribution from dormant signals
        cursor.execute("""
            SELECT
                gn.regime_sovereign as regime,
                COUNT(*) as signal_count,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) as pct_of_total
            FROM fhq_canonical.golden_needles gn
            JOIN fhq_canonical.g5_signal_state ss ON gn.needle_id = ss.needle_id
            WHERE ss.current_state = 'DORMANT'
            GROUP BY gn.regime_sovereign
            ORDER BY signal_count DESC;
        """)

        rows = cursor.fetchall()
        cursor.close()

        if not rows:
            return {
                "sufficient": False,
                "non_dominant_pct": 0.0,
                "dominant_regime": "UNKNOWN",
                "distribution": {},
                "status": "NO_SIGNALS"
            }

        # Build distribution
        distribution = {row[0]: int(row[1]) for row in rows}
        total_signals = sum(distribution.values())

        # Dominant regime is the first (highest count)
        dominant_regime = rows[0][0]
        dominant_pct = float(rows[0][2])

        # Non-dominant percentage
        non_dominant_pct = 100.0 - dominant_pct

        # Determine status
        if non_dominant_pct < 5:
            status = "COLLAPSED"
        elif non_dominant_pct < 15:
            status = "MARGINAL"
        elif non_dominant_pct < 30:
            status = "FUNCTIONAL"
        else:
            status = "OPTIMAL"

        return {
            "sufficient": non_dominant_pct >= self.REGIME_DIVERSITY_THRESHOLD,
            "non_dominant_pct": non_dominant_pct,
            "dominant_regime": dominant_regime,
            "distribution": distribution,
            "status": status,
            "total_signals": total_signals
        }

    def log_hard_stop_event(self, diversity_info: Dict, signals_blocked: int) -> None:
        """
        VEGA Condition C1: Log hard stop event for audit trail.

        Args:
            diversity_info: Result from check_regime_diversity()
            signals_blocked: Number of signals that would have been scored
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO vision_verification.eqs_v2_hard_stop_events (
                regime_diversity_pct,
                required_threshold_pct,
                regime_distribution,
                signals_blocked,
                error_message,
                enforced_by
            ) VALUES (%s, %s, %s, %s, %s, %s);
        """, (
            diversity_info['non_dominant_pct'],
            self.REGIME_DIVERSITY_THRESHOLD,
            json.dumps(diversity_info['distribution']),
            signals_blocked,
            f"Hard Stop triggered: {diversity_info['status']} ({diversity_info['non_dominant_pct']:.2f}% < {self.REGIME_DIVERSITY_THRESHOLD}%)",
            'STIG'
        ))
        self.conn.commit()
        cursor.close()

    def log_calculation(self, needle_id: str, eqs_v2_score: float, eqs_v2_tier: str,
                        sitc_pct: float, factor_pct: float, category_pct: float,
                        recency_pct: float, base_score: float, regime_state: str,
                        regime_diversity_pct: float, input_hash: str,
                        hard_stop_triggered: bool = False, hard_stop_reason: str = None) -> None:
        """
        VEGA Condition C2: Log EQS v2 calculation to audit trail.

        This creates court-proof evidence per CEO Directive 2025-12-20.
        All values are logged to vision_verification.eqs_v2_calculation_log.

        Args:
            needle_id: UUID of the signal
            eqs_v2_score: Final EQS v2 score
            eqs_v2_tier: Tier (S/A/B/C)
            sitc_pct: SITC completeness percentile
            factor_pct: Factor quality percentile
            category_pct: Category strength percentile
            recency_pct: Recency percentile
            base_score: Base score component
            regime_state: Current regime (BULL/BEAR/NEUTRAL)
            regime_diversity_pct: Non-dominant regime percentage
            input_hash: SHA-256 hash of input data
            hard_stop_triggered: Whether hard stop was triggered
            hard_stop_reason: Reason for hard stop (if applicable)
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO vision_verification.eqs_v2_calculation_log (
                needle_id,
                eqs_v2_score,
                eqs_v2_tier,
                sitc_pct,
                factor_pct,
                category_pct,
                recency_pct,
                base_score,
                regime_state,
                regime_diversity_pct,
                hard_stop_triggered,
                hard_stop_reason,
                calculation_version,
                formula_hash,
                input_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (
            needle_id,
            eqs_v2_score,
            eqs_v2_tier,
            sitc_pct,
            factor_pct,
            category_pct,
            recency_pct,
            base_score,
            regime_state,
            regime_diversity_pct,
            hard_stop_triggered,
            hard_stop_reason,
            self.CALCULATION_VERSION,
            self._formula_hash,
            input_hash
        ))
        cursor.close()

    def _compute_input_hash(self, row: pd.Series) -> str:
        """Compute SHA-256 hash of input data for reproducibility."""
        input_data = {
            "needle_id": str(row.get('needle_id', '')),
            "confluence_factor_count": int(row.get('confluence_factor_count', 0)),
            "sitc_nodes_completed": int(row.get('sitc_nodes_completed', 0)),
            "sitc_nodes_total": int(row.get('sitc_nodes_total', 0)),
            "hypothesis_category": str(row.get('hypothesis_category', '')),
            "created_at": str(row.get('created_at', '')),
        }
        input_json = json.dumps(input_data, sort_keys=True)
        return hashlib.sha256(input_json.encode()).hexdigest()[:16]

    def fetch_dormant_signals(self) -> pd.DataFrame:
        """
        Fetch all dormant signals with required fields for EQS v2 calculation.

        Returns:
            DataFrame with signal metrics
        """
        query = """
        SELECT
            gn.needle_id,
            gn.eqs_score as eqs_v1,
            gn.confluence_factor_count,
            gn.sitc_nodes_completed,
            gn.sitc_nodes_total,
            gn.hypothesis_category,
            gn.created_at,
            gn.factor_price_technical,
            gn.factor_volume_confirmation,
            gn.factor_regime_alignment,
            gn.factor_temporal_coherence,
            gn.factor_catalyst_present,
            gn.factor_specific_testable,
            gn.factor_testable_criteria
        FROM fhq_canonical.golden_needles gn
        JOIN fhq_canonical.g5_signal_state ss ON gn.needle_id = ss.needle_id
        WHERE ss.current_state = 'DORMANT'
        ORDER BY gn.created_at DESC;
        """

        return pd.read_sql_query(query, self.conn)

    def calculate_sitc_completeness(self, df: pd.DataFrame) -> pd.Series:
        """Calculate SITC completeness ratio."""
        return df['sitc_nodes_completed'] / df['sitc_nodes_total'].replace(0, np.nan)

    def calculate_factor_quality_score(self, row: pd.Series) -> float:
        """
        Calculate factor quality score based on which factors are present.

        Higher score = better factor combination
        Missing critical factors (price, volume) hurts more than missing catalyst.
        """
        total_weight = 0.0
        achieved_weight = 0.0

        for factor, criticality in self.FACTOR_CRITICALITY.items():
            total_weight += criticality
            if row[f'factor_{factor}']:
                achieved_weight += criticality

        return achieved_weight / total_weight if total_weight > 0 else 0.0

    def calculate_category_strength(self, category: str) -> float:
        """
        Calculate category strength score.

        For multi-category hypotheses (e.g., "MEAN_REVERSION|VOLATILITY"),
        return average of component strengths.
        """
        if '|' in category:
            # Multi-category: average of components
            components = category.split('|')
            strengths = [self.CATEGORY_STRENGTH.get(c.strip(), 0.70) for c in components]
            return np.mean(strengths)
        else:
            # Single category
            return self.CATEGORY_STRENGTH.get(category, 0.70)

    def calculate_age_hours(self, df: pd.DataFrame) -> pd.Series:
        """Calculate signal age in hours."""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        created_at = pd.to_datetime(df['created_at'])
        # Ensure both are timezone-aware
        if created_at.dt.tz is None:
            created_at = created_at.dt.tz_localize('UTC')
        return (now - created_at).dt.total_seconds() / 3600

    def calculate_diversity_bonus(self, category: str) -> float:
        """
        Multi-category hypotheses show broader thinking.

        Args:
            category: hypothesis_category string

        Returns:
            0.05 if multi-category, 0.0 otherwise
        """
        return self.BONUS_DIVERSITY if '|' in category else 0.0

    def calculate_percentile_rank(self, series: pd.Series) -> pd.Series:
        """
        Calculate percentile rank for a series.

        Returns values 0.0 to 1.0 where:
        - 0.0 = worst (lowest value)
        - 1.0 = best (highest value)
        """
        return series.rank(pct=True, method='average')

    def calculate_eqs_v2(self, df: pd.DataFrame, log_calculations: bool = True) -> pd.DataFrame:
        """
        Calculate EQS v2 for all signals using rank-based approach.

        VEGA CONDITIONS:
        - C1: Checks regime diversity first; raises RegimeDiversityError if < 15%
        - C2: Logs all calculations to vision_verification.eqs_v2_calculation_log

        Args:
            df: DataFrame from fetch_dormant_signals()
            log_calculations: If True, log each calculation to audit trail (C2)

        Returns:
            DataFrame with additional columns:
            - eqs_v2: new rank-based score
            - eqs_v2_tier: categorical tier (S/A/B/C)
            - various intermediate calculation columns

        Raises:
            RegimeDiversityError: If regime diversity < 15% and enforce_hard_stop=True
        """
        # =====================================================================
        # VEGA CONDITION C1: REGIME DIVERSITY HARD STOP (BLOCKING CHECK)
        # =====================================================================
        diversity_info = self.check_regime_diversity()

        if not diversity_info['sufficient'] and self.enforce_hard_stop:
            # Log the hard stop event for audit trail
            self.log_hard_stop_event(diversity_info, len(df))

            # Raise exception to halt processing
            raise RegimeDiversityError(
                diversity_pct=diversity_info['non_dominant_pct'],
                threshold_pct=self.REGIME_DIVERSITY_THRESHOLD,
                regime_distribution=diversity_info['distribution']
            )

        # Store diversity info for logging
        regime_state = diversity_info['dominant_regime']
        regime_diversity_pct = diversity_info['non_dominant_pct']

        # Step 1: Calculate base score (scaled down to leave room for premiums)
        df['base_score'] = (df['confluence_factor_count'] / 7.0) * self.BASE_WEIGHT

        # Step 2: Calculate component metrics
        df['sitc_completeness'] = self.calculate_sitc_completeness(df)
        df['factor_quality_score'] = df.apply(self.calculate_factor_quality_score, axis=1)
        df['category_strength'] = df['hypothesis_category'].apply(self.calculate_category_strength)
        df['age_hours'] = self.calculate_age_hours(df)

        # Step 3: Calculate percentile ranks (0.0 to 1.0)
        df['sitc_pct'] = self.calculate_percentile_rank(df['sitc_completeness'])
        df['factor_pct'] = self.calculate_percentile_rank(df['factor_quality_score'])
        df['category_pct'] = self.calculate_percentile_rank(df['category_strength'])
        # Recency: invert so newer = higher percentile
        df['recency_pct'] = 1.0 - self.calculate_percentile_rank(df['age_hours'])

        # Step 4: Calculate final EQS v2
        df['eqs_v2'] = (
            df['base_score'] +
            (self.WEIGHT_SITC * df['sitc_pct']) +
            (self.WEIGHT_FACTOR_QUALITY * df['factor_pct']) +
            (self.WEIGHT_CATEGORY * df['category_pct']) +
            (self.WEIGHT_RECENCY * df['recency_pct'])
        )

        # Ensure bounds [0.0, 1.0]
        df['eqs_v2'] = df['eqs_v2'].clip(0.0, 1.0)

        # Step 5: Assign tiers
        df['eqs_v2_tier'] = pd.cut(
            df['eqs_v2'],
            bins=[0.0, 0.78, 0.88, 0.95, 1.0],
            labels=['C', 'B', 'A', 'S'],
            include_lowest=True
        )

        # =====================================================================
        # VEGA CONDITION C2: CALCULATION LOGGING (COURT-PROOF EVIDENCE)
        # =====================================================================
        if log_calculations:
            for _, row in df.iterrows():
                input_hash = self._compute_input_hash(row)
                self.log_calculation(
                    needle_id=str(row['needle_id']),
                    eqs_v2_score=float(row['eqs_v2']),
                    eqs_v2_tier=str(row['eqs_v2_tier']),
                    sitc_pct=float(row['sitc_pct']) if pd.notna(row['sitc_pct']) else None,
                    factor_pct=float(row['factor_pct']) if pd.notna(row['factor_pct']) else None,
                    category_pct=float(row['category_pct']) if pd.notna(row['category_pct']) else None,
                    recency_pct=float(row['recency_pct']) if pd.notna(row['recency_pct']) else None,
                    base_score=float(row['base_score']),
                    regime_state=regime_state,
                    regime_diversity_pct=regime_diversity_pct,
                    input_hash=input_hash
                )
            # Commit all logs
            self.conn.commit()

        return df

    def generate_distribution_report(self, df: pd.DataFrame) -> Dict:
        """
        Generate statistical report comparing EQS v1 vs v2 distributions.

        Args:
            df: DataFrame with eqs_v1 and eqs_v2 columns

        Returns:
            Dictionary with distribution metrics
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_signals": len(df),
            "eqs_v1": {
                "distinct_buckets": df['eqs_v1'].nunique(),
                "min": float(df['eqs_v1'].min()),
                "max": float(df['eqs_v1'].max()),
                "mean": float(df['eqs_v1'].mean()),
                "std": float(df['eqs_v1'].std()),
                "percentiles": {
                    "p01": float(df['eqs_v1'].quantile(0.01)),
                    "p10": float(df['eqs_v1'].quantile(0.10)),
                    "p25": float(df['eqs_v1'].quantile(0.25)),
                    "p50": float(df['eqs_v1'].quantile(0.50)),
                    "p75": float(df['eqs_v1'].quantile(0.75)),
                    "p90": float(df['eqs_v1'].quantile(0.90)),
                    "p99": float(df['eqs_v1'].quantile(0.99)),
                },
                "p90_p10_spread": float(df['eqs_v1'].quantile(0.90) - df['eqs_v1'].quantile(0.10)),
            },
            "eqs_v2": {
                "distinct_buckets": len(pd.cut(df['eqs_v2'], bins=20).value_counts()),
                "min": float(df['eqs_v2'].min()),
                "max": float(df['eqs_v2'].max()),
                "mean": float(df['eqs_v2'].mean()),
                "std": float(df['eqs_v2'].std()),
                "percentiles": {
                    "p01": float(df['eqs_v2'].quantile(0.01)),
                    "p10": float(df['eqs_v2'].quantile(0.10)),
                    "p25": float(df['eqs_v2'].quantile(0.25)),
                    "p50": float(df['eqs_v2'].quantile(0.50)),
                    "p75": float(df['eqs_v2'].quantile(0.75)),
                    "p90": float(df['eqs_v2'].quantile(0.90)),
                    "p99": float(df['eqs_v2'].quantile(0.99)),
                },
                "p90_p10_spread": float(df['eqs_v2'].quantile(0.90) - df['eqs_v2'].quantile(0.10)),
            },
            "tier_distribution": df['eqs_v2_tier'].value_counts().to_dict(),
            "improvement_metrics": {
                "std_improvement_factor": float(df['eqs_v2'].std() / df['eqs_v1'].std()),
                "spread_improvement_factor": float(
                    (df['eqs_v2'].quantile(0.90) - df['eqs_v2'].quantile(0.10)) /
                    max(0.001, df['eqs_v1'].quantile(0.90) - df['eqs_v1'].quantile(0.10))
                ),
            },
            "selectivity": {
                "v1_above_090": int((df['eqs_v1'] >= 0.90).sum()),
                "v1_above_090_pct": float((df['eqs_v1'] >= 0.90).sum() / len(df) * 100),
                "v2_above_090": int((df['eqs_v2'] >= 0.90).sum()),
                "v2_above_090_pct": float((df['eqs_v2'] >= 0.90).sum() / len(df) * 100),
            }
        }

        return report

    def save_to_database(self, df: pd.DataFrame, dry_run: bool = True):
        """
        Save EQS v2 scores to database.

        Args:
            df: DataFrame with needle_id and eqs_v2
            dry_run: If True, only print SQL without executing
        """
        if dry_run:
            print("DRY RUN MODE - SQL to be executed:")
            print("\n-- Add column if not exists")
            print("ALTER TABLE fhq_canonical.golden_needles ADD COLUMN IF NOT EXISTS eqs_score_v2 NUMERIC(5,4);")
            print("\n-- Sample update statements (first 5):")
            for idx, row in df.head().iterrows():
                print(f"UPDATE fhq_canonical.golden_needles SET eqs_score_v2 = {row['eqs_v2']:.4f} WHERE needle_id = '{row['needle_id']}';")
            print(f"\n... and {len(df) - 5} more updates")
        else:
            cursor = self.conn.cursor()

            # Add column if not exists
            cursor.execute("""
                ALTER TABLE fhq_canonical.golden_needles
                ADD COLUMN IF NOT EXISTS eqs_score_v2 NUMERIC(5,4);
            """)

            # Batch update
            for _, row in df.iterrows():
                cursor.execute("""
                    UPDATE fhq_canonical.golden_needles
                    SET eqs_score_v2 = %s
                    WHERE needle_id = %s;
                """, (float(row['eqs_v2']), row['needle_id']))

            self.conn.commit()
            cursor.close()
            print(f"Updated {len(df)} signals with EQS v2 scores")


def main():
    """
    Main execution: calculate EQS v2 for all dormant signals and generate report.
    """
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # Database connection
    conn = psycopg2.connect(
        host=os.getenv('PGHOST', '127.0.0.1'),
        port=os.getenv('PGPORT', '54322'),
        database=os.getenv('PGDATABASE', 'postgres'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', 'postgres')
    )

    try:
        # Initialize calculator
        calc = EQSv2Calculator(conn)

        print("Fetching dormant signals...")
        df = calc.fetch_dormant_signals()
        print(f"Found {len(df)} dormant signals")

        print("\nCalculating EQS v2...")
        df_scored = calc.calculate_eqs_v2(df)

        print("\nGenerating distribution report...")
        report = calc.generate_distribution_report(df_scored)

        # Save report
        report_path = "03_FUNCTIONS/evidence/EQS_V2_DISTRIBUTION_REPORT.json"
        with open(report_path, 'w') as f:
            json.dump(report, indent=2, fp=f)
        print(f"Report saved to: {report_path}")

        # Print summary
        print("\n" + "="*80)
        print("EQS V2 DISTRIBUTION REPORT")
        print("="*80)
        print(f"\nTotal Signals: {report['total_signals']}")

        print("\n--- EQS v1 (Current) ---")
        print(f"Distinct Buckets: {report['eqs_v1']['distinct_buckets']}")
        print(f"Std Dev: {report['eqs_v1']['std']:.4f}")
        print(f"P90-P10 Spread: {report['eqs_v1']['p90_p10_spread']:.4f}")
        print(f"Signals >= 0.90: {report['selectivity']['v1_above_090']} ({report['selectivity']['v1_above_090_pct']:.1f}%)")

        print("\n--- EQS v2 (Proposed) ---")
        print(f"Distinct Buckets: {report['eqs_v2']['distinct_buckets']}")
        print(f"Std Dev: {report['eqs_v2']['std']:.4f}")
        print(f"P90-P10 Spread: {report['eqs_v2']['p90_p10_spread']:.4f}")
        print(f"Signals >= 0.90: {report['selectivity']['v2_above_090']} ({report['selectivity']['v2_above_090_pct']:.1f}%)")

        print("\n--- Improvement ---")
        print(f"Std Dev Improvement: {report['improvement_metrics']['std_improvement_factor']:.1f}x")
        print(f"Spread Improvement: {report['improvement_metrics']['spread_improvement_factor']:.1f}x")

        print("\n--- Tier Distribution ---")
        for tier in ['S', 'A', 'B', 'C']:
            count = report['tier_distribution'].get(tier, 0)
            pct = count / report['total_signals'] * 100
            print(f"Tier {tier}: {count} signals ({pct:.1f}%)")

        print("\n--- Percentiles (v2) ---")
        for pct, val in report['eqs_v2']['percentiles'].items():
            print(f"{pct.upper()}: {val:.4f}")

        # Save scored signals to CSV
        output_csv = "03_FUNCTIONS/evidence/EQS_V2_SCORED_SIGNALS.csv"
        df_scored[['needle_id', 'hypothesis_category', 'eqs_v1', 'eqs_v2', 'eqs_v2_tier',
                   'sitc_completeness', 'factor_quality_score', 'category_strength']].to_csv(
            output_csv, index=False
        )
        print(f"\nScored signals saved to: {output_csv}")

        # Ask about database update
        print("\n" + "="*80)
        response = input("Save EQS v2 scores to database? (yes/no/dry-run): ").strip().lower()
        if response == 'yes':
            calc.save_to_database(df_scored, dry_run=False)
        elif response == 'dry-run':
            calc.save_to_database(df_scored, dry_run=True)
        else:
            print("Skipping database update")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
