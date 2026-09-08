#!/usr/bin/env python3
"""
Weekly Regret Attribution Report
=================================
Directive: CEO-DIR-2026-021 Optimization Phase
Purpose: Generate executive summary of regret patterns for surgical optimization
Authority: STIG (Observability Enhancement)

Generates weekly report with:
- Type A/B/C breakdown
- Asset class clusters
- Surgical optimization recommendations
- Shadow mode readiness assessment

Usage:
    python weekly_regret_attribution_report.py                    # Current week
    python weekly_regret_attribution_report.py --iso-week 2026-W2 # Specific week
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("weekly_regret_report")

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": os.getenv("PGPORT", "54322"),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres")
}

EVIDENCE_DIR = os.path.join(os.path.dirname(__file__), "evidence")

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Establish database connection"""
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# REPORT GENERATION
# =============================================================================

def get_iso_week(date=None):
    """Get ISO year and week for date"""
    if date is None:
        date = datetime.now()
    iso_calendar = date.isocalendar()
    return iso_calendar[0], iso_calendar[1]

def generate_weekly_report(conn, iso_year: int, iso_week: int) -> Dict[str, Any]:
    """Generate comprehensive weekly regret attribution report"""

    logger.info(f"Generating report for ISO week {iso_year}-W{iso_week:02d}")

    # Get week boundaries
    # ISO week starts on Monday
    jan_4 = datetime(iso_year, 1, 4)
    week_start = jan_4 - timedelta(days=jan_4.weekday()) + timedelta(weeks=iso_week-1)
    week_end = week_start + timedelta(days=7)

    report = {
        'report_id': f'REGRET_ATTRIBUTION_{iso_year}_W{iso_week:02d}',
        'report_type': 'WEEKLY_REGRET_ATTRIBUTION',
        'iso_year': iso_year,
        'iso_week': iso_week,
        'week_start': week_start.isoformat(),
        'week_end': week_end.isoformat(),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'generated_by': 'STIG'
    }

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Overall statistics
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE regret_classification = 'REGRET') as regret_count,
                COUNT(*) FILTER (WHERE regret_classification = 'WISDOM') as wisdom_count,
                COUNT(*) FILTER (WHERE regret_classification = 'UNRESOLVED') as unresolved_count,
                COUNT(*) as total_suppressions,
                AVG(regret_magnitude) FILTER (WHERE regret_classification = 'REGRET') as avg_regret_magnitude,
                AVG(regret_magnitude) FILTER (WHERE regret_classification = 'WISDOM') as avg_wisdom_magnitude
            FROM fhq_governance.epistemic_suppression_ledger
            WHERE suppression_timestamp >= %s
              AND suppression_timestamp < %s
        """, (week_start, week_end))

        stats = dict(cur.fetchone())

        report['overall_statistics'] = {
            'total_suppressions': int(stats['total_suppressions']),
            'regret_count': int(stats['regret_count'] or 0),
            'wisdom_count': int(stats['wisdom_count'] or 0),
            'unresolved_count': int(stats['unresolved_count'] or 0),
            'regret_rate': float(stats['regret_count'] or 0) / max(int(stats['total_suppressions']), 1),
            'wisdom_rate': float(stats['wisdom_count'] or 0) / max(int(stats['total_suppressions']), 1),
            'avg_regret_magnitude': float(stats['avg_regret_magnitude'] or 0),
            'avg_wisdom_magnitude': float(stats['avg_wisdom_magnitude'] or 0)
        }

        # Attribution breakdown
        cur.execute("""
            SELECT
                regret_attribution_type,
                regret_magnitude_category,
                COUNT(*) as count,
                AVG(regret_magnitude) as avg_magnitude,
                ARRAY_AGG(DISTINCT asset_id ORDER BY asset_id) as affected_assets
            FROM fhq_governance.epistemic_suppression_ledger
            WHERE regret_classification = 'REGRET'
              AND suppression_timestamp >= %s
              AND suppression_timestamp < %s
              AND regret_attribution_type IS NOT NULL
            GROUP BY regret_attribution_type, regret_magnitude_category
            ORDER BY count DESC
        """, (week_start, week_end))

        attribution_breakdown = []
        for row in cur.fetchall():
            attribution_breakdown.append({
                'type': row['regret_attribution_type'],
                'magnitude_category': row['regret_magnitude_category'],
                'count': int(row['count']),
                'avg_magnitude': float(row['avg_magnitude']),
                'affected_assets': row['affected_assets'][:5] if row['affected_assets'] else []  # Top 5
            })

        report['attribution_breakdown'] = attribution_breakdown

        # Type A analysis (Hysteresis Lag)
        cur.execute("""
            SELECT
                suppression_category,
                constraint_type,
                COUNT(*) as count,
                AVG(regret_magnitude) as avg_magnitude,
                AVG(suppressed_confidence) as avg_suppressed_confidence,
                AVG(chosen_confidence) as avg_chosen_confidence,
                ARRAY_AGG(DISTINCT asset_id ORDER BY asset_id) as affected_assets
            FROM fhq_governance.epistemic_suppression_ledger
            WHERE regret_classification = 'REGRET'
              AND regret_attribution_type = 'TYPE_A_HYSTERESIS_LAG'
              AND suppression_timestamp >= %s
              AND suppression_timestamp < %s
            GROUP BY suppression_category, constraint_type
            ORDER BY count DESC
        """, (week_start, week_end))

        type_a_analysis = []
        for row in cur.fetchall():
            type_a_analysis.append({
                'suppression_category': row['suppression_category'],
                'constraint_type': row['constraint_type'],
                'count': int(row['count']),
                'avg_magnitude': float(row['avg_magnitude']),
                'avg_suppressed_confidence': float(row['avg_suppressed_confidence']),
                'avg_chosen_confidence': float(row['avg_chosen_confidence']),
                'affected_assets': row['affected_assets'][:10] if row['affected_assets'] else []
            })

        report['type_a_analysis'] = type_a_analysis

    # Generate recommendations
    report['recommendations'] = generate_recommendations(report)

    # Shadow mode readiness
    report['shadow_mode_readiness'] = assess_shadow_mode_readiness(report)

    return report

def generate_recommendations(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate surgical optimization recommendations based on patterns"""

    recommendations = []
    regret_count = report['overall_statistics']['regret_count']
    attribution_breakdown = report['attribution_breakdown']

    if regret_count == 0:
        recommendations.append({
            'type': 'NO_ACTION',
            'priority': 'INFO',
            'title': 'Zero Regret Week',
            'description': 'No regret detected this week. Policy is performing optimally.',
            'action': 'Continue observation'
        })
        return recommendations

    # Type A recommendations
    type_a_count = sum(a['count'] for a in attribution_breakdown if 'TYPE_A' in a['type'])
    if type_a_count > regret_count * 0.5:  # >50% is Type A
        recommendations.append({
            'type': 'TYPE_A_HYSTERESIS_TUNING',
            'priority': 'HIGH',
            'title': 'Hysteresis Lag Dominant',
            'description': f'{type_a_count}/{regret_count} regret cases are Type A (Hysteresis Lag)',
            'action': 'Consider adaptive confirms_required in shadow mode',
            'shadow_mode_target': 'CRIO Adaptive Hysteresis Simulator',
            'readiness': 'Day 28 of observation window'
        })

    # Type B recommendations
    type_b_count = sum(a['count'] for a in attribution_breakdown if 'TYPE_B' in a['type'])
    if type_b_count > regret_count * 0.3:  # >30% is Type B
        recommendations.append({
            'type': 'TYPE_B_CALIBRATION',
            'priority': 'MEDIUM',
            'title': 'Confidence Floor Pattern Detected',
            'description': f'{type_b_count}/{regret_count} regret cases are Type B (Confidence Floor)',
            'action': 'Activate Brier score tracking, review FINN calibration',
            'shadow_mode_target': 'FINN Confidence Calibration',
            'readiness': 'Day 15 of observation window'
        })

    # Type C recommendations
    type_c_count = sum(a['count'] for a in attribution_breakdown if 'TYPE_C' in a['type'])
    if type_c_count > regret_count * 0.2:  # >20% is Type C
        recommendations.append({
            'type': 'TYPE_C_FEATURE_EXPANSION',
            'priority': 'HIGH',
            'title': 'Data Blindness Detected',
            'description': f'{type_c_count}/{regret_count} regret cases are Type C (Data Blindness)',
            'action': 'Expand IoS-006 macro coverage, review missing signals',
            'shadow_mode_target': 'CEIO Signal Expansion',
            'readiness': 'Immediate (data ingestion improvement)'
        })

    return recommendations

def assess_shadow_mode_readiness(report: Dict[str, Any]) -> Dict[str, Any]:
    """Assess readiness for shadow mode simulations"""

    regret_count = report['overall_statistics']['regret_count']
    total_suppressions = report['overall_statistics']['total_suppressions']

    # Require minimum 10 regret cases for meaningful shadow simulation
    has_sufficient_data = regret_count >= 10

    # Require clear dominant pattern (>60% of one type)
    attribution_breakdown = report['attribution_breakdown']
    dominant_type = max(attribution_breakdown, key=lambda x: x['count']) if attribution_breakdown else None
    has_clear_pattern = dominant_type and (dominant_type['count'] / max(regret_count, 1)) > 0.6 if dominant_type else False

    return {
        'ready_for_shadow_mode': has_sufficient_data and has_clear_pattern,
        'has_sufficient_data': has_sufficient_data,
        'has_clear_pattern': has_clear_pattern,
        'regret_sample_size': regret_count,
        'dominant_pattern': dominant_type['type'] if dominant_type else None,
        'dominant_pattern_percentage': (dominant_type['count'] / max(regret_count, 1)) * 100 if dominant_type else 0,
        'recommendation': 'READY for shadow simulation' if (has_sufficient_data and has_clear_pattern) else 'WAIT for more data or clearer patterns'
    }

def save_report(report: Dict[str, Any]):
    """Save report to evidence directory"""

    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    filename = f"{report['report_id']}.json"
    filepath = os.path.join(EVIDENCE_DIR, filename)

    with open(filepath, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    logger.info(f"Report saved: {filepath}")
    return filepath

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main(iso_week_str: str = None):
    """Main execution"""

    logger.info("=" * 60)
    logger.info("WEEKLY REGRET ATTRIBUTION REPORT")
    logger.info("Directive: CEO-DIR-2026-021 Optimization Phase")
    logger.info("=" * 60)

    # Parse ISO week
    if iso_week_str:
        try:
            iso_year, iso_week = map(int, iso_week_str.split('-W'))
        except:
            logger.error(f"Invalid ISO week format: {iso_week_str}. Use format: 2026-W2")
            return 1
    else:
        iso_year, iso_week = get_iso_week()

    logger.info(f"Target: {iso_year}-W{iso_week:02d}")

    conn = None

    try:
        conn = get_db_connection()
        report = generate_weekly_report(conn, iso_year, iso_week)

        # Save report
        filepath = save_report(report)

        # Print summary
        logger.info("=" * 60)
        logger.info("REPORT SUMMARY")
        logger.info(f"Total Suppressions: {report['overall_statistics']['total_suppressions']}")
        logger.info(f"Regret Count: {report['overall_statistics']['regret_count']}")
        logger.info(f"Regret Rate: {report['overall_statistics']['regret_rate']:.1%}")
        logger.info(f"Wisdom Rate: {report['overall_statistics']['wisdom_rate']:.1%}")
        logger.info("")
        logger.info("ATTRIBUTION BREAKDOWN:")
        for attr in report['attribution_breakdown']:
            logger.info(f"  {attr['type']}: {attr['count']} cases ({attr['avg_magnitude']:.4f} avg magnitude)")
        logger.info("")
        logger.info("RECOMMENDATIONS:")
        for rec in report['recommendations']:
            logger.info(f"  [{rec['priority']}] {rec['title']}: {rec['action']}")
        logger.info("")
        logger.info(f"Shadow Mode Ready: {report['shadow_mode_readiness']['ready_for_shadow_mode']}")
        logger.info("=" * 60)

        print(json.dumps(report, indent=2, default=str))
        return 0

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return 1
    finally:
        if conn:
            conn.close()

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Weekly Regret Attribution Report")
    parser.add_argument("--iso-week", type=str,
                        help="ISO week to report on (format: 2026-W2). Default: current week")
    args = parser.parse_args()

    sys.exit(main(iso_week_str=args.iso_week))
