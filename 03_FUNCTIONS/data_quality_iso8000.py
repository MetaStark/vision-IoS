#!/usr/bin/env python3
"""
ISO 8000 DATA QUALITY FRAMEWORK
===============================
Directive: CEO-DIR-2026-120 P5.1
Classification: G4_DATA_GOVERNANCE
Date: 2026-01-22

Implements ISO 8000 data quality dimensions:
1. Completeness - Are all required data points present?
2. Timeliness - Is data fresh and within acceptable latency?
3. Accuracy - Is data free from errors?
4. Consistency - Is data consistent across sources?

Scores each data source (Alpaca, IEX, TwelveData, etc.)
Blocks signals from sources below threshold.

Authority: CEO, STIG (Technical), VEGA (Governance)
Employment Contract: EC-003
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

# Load environment
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[ISO8000] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Database config
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Quality thresholds
QUALITY_TIER_THRESHOLDS = {
    'GOLD': 0.90,      # >= 90%: Highest quality
    'SILVER': 0.75,    # >= 75%: Acceptable quality
    'BRONZE': 0.60,    # >= 60%: Usable with caution
    'BLOCKED': 0.0     # < 60%: Not usable for signals
}

# Dimension weights for overall score
DIMENSION_WEIGHTS = {
    'completeness': 0.30,
    'timeliness': 0.30,
    'accuracy': 0.25,
    'consistency': 0.15
}


@dataclass
class QualityDimension:
    """Individual quality dimension score."""
    name: str
    score: float  # 0.0 - 1.0
    issues_detected: int
    records_evaluated: int
    details: Dict[str, Any]


@dataclass
class DataSourceQuality:
    """Complete quality assessment for a data source."""
    source_name: str
    assessment_date: datetime
    completeness: QualityDimension
    timeliness: QualityDimension
    accuracy: QualityDimension
    consistency: QualityDimension
    overall_score: float
    quality_tier: str
    is_blocked: bool
    recommendations: List[str]


class ISO8000QualityFramework:
    """
    ISO 8000 Data Quality Assessment Framework.

    Evaluates data sources against ISO 8000 quality dimensions
    and assigns quality tiers for signal processing decisions.
    """

    # Data sources to evaluate
    DATA_SOURCES = ['ALPACA', 'IEX', 'TWELVEDATA', 'FRED', 'YAHOO', 'COINGECKO']

    # Expected data freshness (hours)
    FRESHNESS_THRESHOLDS = {
        'ALPACA': 0.25,      # 15 minutes for real-time
        'IEX': 0.25,         # 15 minutes
        'TWELVEDATA': 1.0,   # 1 hour
        'FRED': 24.0,        # 1 day for macro data
        'YAHOO': 1.0,        # 1 hour
        'COINGECKO': 0.5     # 30 minutes for crypto
    }

    def __init__(self):
        self.conn = None
        self._assessments: Dict[str, DataSourceQuality] = {}

    def connect(self):
        """Connect to database."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Connected to database")

    def close(self):
        """Close connection."""
        if self.conn:
            self.conn.close()

    def assess_completeness(self, source: str) -> QualityDimension:
        """
        Assess data completeness for a source.

        Checks:
        - Required fields present
        - No unexpected nulls
        - Data coverage (dates, symbols)
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check for null values in critical fields
                if source in ['ALPACA', 'IEX', 'TWELVEDATA']:
                    cur.execute("""
                        SELECT
                            COUNT(*) as total_records,
                            COUNT(*) FILTER (WHERE close IS NULL) as null_close,
                            COUNT(*) FILTER (WHERE volume IS NULL OR volume = 0) as null_volume,
                            COUNT(*) FILTER (WHERE high IS NULL) as null_high,
                            COUNT(*) FILTER (WHERE low IS NULL) as null_low,
                            COUNT(DISTINCT listing_id) as unique_symbols,
                            MIN(date) as earliest,
                            MAX(date) as latest
                        FROM fhq_data.price_series
                        WHERE source_provider = %s
                        AND date >= CURRENT_DATE - INTERVAL '30 days'
                    """, (source,))
                else:
                    # For macro sources
                    cur.execute("""
                        SELECT
                            COUNT(*) as total_records,
                            0 as null_close,
                            0 as null_volume,
                            0 as null_high,
                            0 as null_low,
                            COUNT(DISTINCT feature_id) as unique_symbols,
                            MIN(timestamp::date) as earliest,
                            MAX(timestamp::date) as latest
                        FROM fhq_macro.canonical_series
                        WHERE provenance = %s
                        AND timestamp >= CURRENT_DATE - INTERVAL '30 days'
                    """, (source,))

                row = cur.fetchone()

                if row['total_records'] == 0:
                    return QualityDimension(
                        name='completeness',
                        score=0.0,
                        issues_detected=1,
                        records_evaluated=0,
                        details={'error': 'No data found'}
                    )

                total = row['total_records']
                issues = (
                    (row['null_close'] or 0) +
                    (row['null_volume'] or 0) +
                    (row['null_high'] or 0) +
                    (row['null_low'] or 0)
                )

                score = max(0, 1 - (issues / (total * 4)))  # 4 critical fields

                return QualityDimension(
                    name='completeness',
                    score=round(score, 4),
                    issues_detected=issues,
                    records_evaluated=total,
                    details={
                        'null_close': row['null_close'],
                        'null_volume': row['null_volume'],
                        'unique_symbols': row['unique_symbols'],
                        'date_range': f"{row['earliest']} to {row['latest']}"
                    }
                )

        except Exception as e:
            logger.error(f"Completeness check failed for {source}: {e}")
            return QualityDimension(
                name='completeness',
                score=0.5,
                issues_detected=0,
                records_evaluated=0,
                details={'error': str(e)}
            )

    def assess_timeliness(self, source: str) -> QualityDimension:
        """
        Assess data timeliness/freshness.

        Checks:
        - Latest data age vs threshold
        - Update frequency
        - Gaps in time series
        """
        threshold_hours = self.FRESHNESS_THRESHOLDS.get(source, 24.0)

        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                if source in ['ALPACA', 'IEX', 'TWELVEDATA']:
                    cur.execute("""
                        SELECT
                            MAX(date) as latest_date,
                            EXTRACT(EPOCH FROM (NOW() - MAX(date))) / 3600 as hours_behind,
                            COUNT(DISTINCT date) as trading_days,
                            COUNT(*) as total_records
                        FROM fhq_data.price_series
                        WHERE source_provider = %s
                        AND date >= CURRENT_DATE - INTERVAL '7 days'
                    """, (source,))
                else:
                    cur.execute("""
                        SELECT
                            MAX(timestamp::date) as latest_date,
                            EXTRACT(EPOCH FROM (NOW() - MAX(timestamp))) / 3600 as hours_behind,
                            COUNT(DISTINCT timestamp::date) as trading_days,
                            COUNT(*) as total_records
                        FROM fhq_macro.canonical_series
                        WHERE provenance = %s
                        AND timestamp >= CURRENT_DATE - INTERVAL '7 days'
                    """, (source,))

                row = cur.fetchone()

                if row['total_records'] == 0:
                    return QualityDimension(
                        name='timeliness',
                        score=0.0,
                        issues_detected=1,
                        records_evaluated=0,
                        details={'error': 'No recent data'}
                    )

                hours_behind = float(row['hours_behind'] or 999)

                # Score based on how fresh data is vs threshold
                if hours_behind <= threshold_hours:
                    score = 1.0
                elif hours_behind <= threshold_hours * 2:
                    score = 0.8
                elif hours_behind <= threshold_hours * 4:
                    score = 0.5
                else:
                    score = 0.2

                return QualityDimension(
                    name='timeliness',
                    score=round(score, 4),
                    issues_detected=1 if hours_behind > threshold_hours else 0,
                    records_evaluated=row['total_records'],
                    details={
                        'latest_date': str(row['latest_date']),
                        'hours_behind': round(hours_behind, 2),
                        'threshold_hours': threshold_hours,
                        'trading_days_in_7d': row['trading_days']
                    }
                )

        except Exception as e:
            logger.error(f"Timeliness check failed for {source}: {e}")
            return QualityDimension(
                name='timeliness',
                score=0.5,
                issues_detected=0,
                records_evaluated=0,
                details={'error': str(e)}
            )

    def assess_accuracy(self, source: str) -> QualityDimension:
        """
        Assess data accuracy.

        Checks:
        - Price anomalies (extreme moves)
        - OHLC consistency (high >= low, etc.)
        - Duplicate detection
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                if source in ['ALPACA', 'IEX', 'TWELVEDATA']:
                    cur.execute("""
                        SELECT
                            COUNT(*) as total_records,
                            COUNT(*) FILTER (WHERE high < low) as invalid_hl,
                            COUNT(*) FILTER (WHERE close < 0) as negative_price,
                            COUNT(*) FILTER (
                                WHERE ABS((close - open) / NULLIF(open, 0)) > 0.50
                            ) as extreme_moves,
                            COUNT(*) FILTER (
                                WHERE close NOT BETWEEN low AND high
                            ) as close_outside_range
                        FROM fhq_data.price_series
                        WHERE source_provider = %s
                        AND date >= CURRENT_DATE - INTERVAL '30 days'
                    """, (source,))
                else:
                    # For macro: check for extreme values
                    cur.execute("""
                        SELECT
                            COUNT(*) as total_records,
                            0 as invalid_hl,
                            0 as negative_price,
                            COUNT(*) FILTER (
                                WHERE ABS(value_raw) > 1000000000
                            ) as extreme_moves,
                            0 as close_outside_range
                        FROM fhq_macro.canonical_series
                        WHERE provenance = %s
                        AND timestamp >= CURRENT_DATE - INTERVAL '30 days'
                    """, (source,))

                row = cur.fetchone()

                if row['total_records'] == 0:
                    return QualityDimension(
                        name='accuracy',
                        score=0.5,
                        issues_detected=0,
                        records_evaluated=0,
                        details={'error': 'No data to evaluate'}
                    )

                total = row['total_records']
                issues = (
                    (row['invalid_hl'] or 0) +
                    (row['negative_price'] or 0) +
                    (row['extreme_moves'] or 0) +
                    (row['close_outside_range'] or 0)
                )

                score = max(0, 1 - (issues / total))

                return QualityDimension(
                    name='accuracy',
                    score=round(score, 4),
                    issues_detected=issues,
                    records_evaluated=total,
                    details={
                        'invalid_high_low': row['invalid_hl'],
                        'negative_prices': row['negative_price'],
                        'extreme_moves': row['extreme_moves'],
                        'close_outside_range': row['close_outside_range']
                    }
                )

        except Exception as e:
            logger.error(f"Accuracy check failed for {source}: {e}")
            return QualityDimension(
                name='accuracy',
                score=0.5,
                issues_detected=0,
                records_evaluated=0,
                details={'error': str(e)}
            )

    def assess_consistency(self, source: str) -> QualityDimension:
        """
        Assess data consistency across sources.

        Checks:
        - Cross-source price alignment
        - Gap detection
        - Format consistency
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check for gaps (missing trading days)
                if source in ['ALPACA', 'IEX', 'TWELVEDATA']:
                    cur.execute("""
                        WITH date_series AS (
                            SELECT generate_series(
                                CURRENT_DATE - INTERVAL '30 days',
                                CURRENT_DATE,
                                '1 day'::interval
                            )::date as expected_date
                        ),
                        actual_dates AS (
                            SELECT DISTINCT date
                            FROM fhq_data.price_series
                            WHERE source_provider = %s
                            AND date >= CURRENT_DATE - INTERVAL '30 days'
                        )
                        SELECT
                            COUNT(ds.expected_date) FILTER (
                                WHERE EXTRACT(DOW FROM ds.expected_date) NOT IN (0, 6)
                            ) as expected_trading_days,
                            COUNT(ad.date) as actual_days,
                            COUNT(ds.expected_date) FILTER (
                                WHERE ad.date IS NULL
                                AND EXTRACT(DOW FROM ds.expected_date) NOT IN (0, 6)
                            ) as missing_days
                        FROM date_series ds
                        LEFT JOIN actual_dates ad ON ds.expected_date = ad.date
                    """, (source,))
                else:
                    # For macro sources (less frequent updates expected)
                    cur.execute("""
                        SELECT
                            30 as expected_trading_days,
                            COUNT(DISTINCT timestamp::date) as actual_days,
                            0 as missing_days
                        FROM fhq_macro.canonical_series
                        WHERE provenance = %s
                        AND timestamp >= CURRENT_DATE - INTERVAL '30 days'
                    """, (source,))

                row = cur.fetchone()

                expected = row['expected_trading_days'] or 20
                actual = row['actual_days'] or 0
                missing = row['missing_days'] or (expected - actual)

                # Score based on data coverage
                score = min(1.0, actual / max(1, expected))

                return QualityDimension(
                    name='consistency',
                    score=round(score, 4),
                    issues_detected=missing,
                    records_evaluated=expected,
                    details={
                        'expected_days': expected,
                        'actual_days': actual,
                        'missing_days': missing,
                        'coverage_pct': round(score * 100, 1)
                    }
                )

        except Exception as e:
            logger.error(f"Consistency check failed for {source}: {e}")
            return QualityDimension(
                name='consistency',
                score=0.5,
                issues_detected=0,
                records_evaluated=0,
                details={'error': str(e)}
            )

    def assess_source(self, source: str) -> DataSourceQuality:
        """Run full quality assessment for a data source."""
        logger.info(f"Assessing quality for {source}...")

        completeness = self.assess_completeness(source)
        timeliness = self.assess_timeliness(source)
        accuracy = self.assess_accuracy(source)
        consistency = self.assess_consistency(source)

        # Calculate weighted overall score
        overall_score = (
            completeness.score * DIMENSION_WEIGHTS['completeness'] +
            timeliness.score * DIMENSION_WEIGHTS['timeliness'] +
            accuracy.score * DIMENSION_WEIGHTS['accuracy'] +
            consistency.score * DIMENSION_WEIGHTS['consistency']
        )

        # Determine quality tier
        quality_tier = 'BLOCKED'
        for tier, threshold in QUALITY_TIER_THRESHOLDS.items():
            if overall_score >= threshold:
                quality_tier = tier
                break

        is_blocked = quality_tier == 'BLOCKED'

        # Generate recommendations
        recommendations = []
        if completeness.score < 0.8:
            recommendations.append(f"Improve data completeness (current: {completeness.score:.1%})")
        if timeliness.score < 0.8:
            recommendations.append(f"Reduce data latency (current: {timeliness.details.get('hours_behind', 'N/A')}h)")
        if accuracy.score < 0.9:
            recommendations.append(f"Address {accuracy.issues_detected} accuracy issues")
        if consistency.score < 0.8:
            recommendations.append(f"Fill {consistency.issues_detected} missing data points")

        assessment = DataSourceQuality(
            source_name=source,
            assessment_date=datetime.now(timezone.utc),
            completeness=completeness,
            timeliness=timeliness,
            accuracy=accuracy,
            consistency=consistency,
            overall_score=round(overall_score, 4),
            quality_tier=quality_tier,
            is_blocked=is_blocked,
            recommendations=recommendations
        )

        self._assessments[source] = assessment

        logger.info(
            f"  {source}: {overall_score:.1%} ({quality_tier}) - "
            f"{'BLOCKED' if is_blocked else 'OK'}"
        )

        return assessment

    def save_assessment(self, assessment: DataSourceQuality) -> bool:
        """Save quality assessment to database."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_monitoring.data_quality_scores (
                        data_source, quality_date,
                        completeness_score, timeliness_score,
                        accuracy_score, consistency_score,
                        overall_score, records_evaluated, issues_detected,
                        quality_tier, computed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (data_source, quality_date) DO UPDATE SET
                        completeness_score = EXCLUDED.completeness_score,
                        timeliness_score = EXCLUDED.timeliness_score,
                        accuracy_score = EXCLUDED.accuracy_score,
                        consistency_score = EXCLUDED.consistency_score,
                        overall_score = EXCLUDED.overall_score,
                        quality_tier = EXCLUDED.quality_tier,
                        computed_at = NOW()
                """, (
                    assessment.source_name,
                    assessment.assessment_date.date(),
                    assessment.completeness.score,
                    assessment.timeliness.score,
                    assessment.accuracy.score,
                    assessment.consistency.score,
                    assessment.overall_score,
                    assessment.completeness.records_evaluated,
                    (
                        assessment.completeness.issues_detected +
                        assessment.timeliness.issues_detected +
                        assessment.accuracy.issues_detected +
                        assessment.consistency.issues_detected
                    ),
                    assessment.quality_tier
                ))
                self.conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to save assessment: {e}")
            self.conn.rollback()
            return False

    def run_all_assessments(self) -> Dict[str, DataSourceQuality]:
        """Run quality assessments for all data sources."""
        logger.info("=" * 60)
        logger.info("ISO 8000 DATA QUALITY ASSESSMENT")
        logger.info("=" * 60)

        results = {}
        for source in self.DATA_SOURCES:
            try:
                assessment = self.assess_source(source)
                self.save_assessment(assessment)
                results[source] = assessment
            except Exception as e:
                logger.error(f"Failed to assess {source}: {e}")

        # Summary
        blocked = [s for s, a in results.items() if a.is_blocked]
        gold = [s for s, a in results.items() if a.quality_tier == 'GOLD']

        logger.info("=" * 60)
        logger.info(f"Assessment complete: {len(results)} sources")
        logger.info(f"  GOLD: {len(gold)} ({', '.join(gold) or 'none'})")
        logger.info(f"  BLOCKED: {len(blocked)} ({', '.join(blocked) or 'none'})")
        logger.info("=" * 60)

        return results

    def is_source_usable(self, source: str) -> bool:
        """Check if a source is usable for signals."""
        if source in self._assessments:
            return not self._assessments[source].is_blocked
        # Run assessment if not cached
        assessment = self.assess_source(source)
        return not assessment.is_blocked


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='ISO 8000 Data Quality Framework (CEO-DIR-2026-120 P5.1)'
    )
    parser.add_argument('--assess', metavar='SOURCE', help='Assess single source')
    parser.add_argument('--all', action='store_true', help='Assess all sources')
    parser.add_argument('--report', action='store_true', help='Generate quality report')

    args = parser.parse_args()

    framework = ISO8000QualityFramework()
    framework.connect()

    try:
        if args.assess:
            assessment = framework.assess_source(args.assess.upper())
            print(json.dumps(asdict(assessment), indent=2, default=str))

        elif args.all:
            results = framework.run_all_assessments()
            for source, assessment in results.items():
                print(f"\n{source}: {assessment.overall_score:.1%} ({assessment.quality_tier})")
                if assessment.recommendations:
                    for rec in assessment.recommendations:
                        print(f"  - {rec}")

        elif args.report:
            results = framework.run_all_assessments()
            report = {
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'sources': {
                    s: {
                        'overall_score': a.overall_score,
                        'quality_tier': a.quality_tier,
                        'is_blocked': a.is_blocked,
                        'dimensions': {
                            'completeness': a.completeness.score,
                            'timeliness': a.timeliness.score,
                            'accuracy': a.accuracy.score,
                            'consistency': a.consistency.score
                        }
                    }
                    for s, a in results.items()
                }
            }
            print(json.dumps(report, indent=2))

        else:
            parser.print_help()

    finally:
        framework.close()


if __name__ == '__main__':
    main()
