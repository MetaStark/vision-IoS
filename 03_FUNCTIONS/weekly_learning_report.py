#!/usr/bin/env python3
"""
WEEKLY LEARNING REPORT GENERATOR
================================
CEO-DIR-2026-128 DAY44: Phase-2 Readiness Assessment

PURPOSE: Generate weekly summary of learning loop metrics.
         Provides CEO decision point data for Phase-2 activation.

METRICS:
- Hypotheses born/killed/survived
- Decision packs generated
- LVI value and trend
- Memory citations issued
- Repeated failure blocks
- FSS average and trend

Authority: CEO-DIR-2026-128
Classification: G4_PRODUCTION_REPORT
Executor: STIG (EC-003)
"""

import os
import sys
import json
import hashlib
import logging
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

DAEMON_NAME = 'weekly_learning_report'

logging.basicConfig(
    level=logging.INFO,
    format='[WEEKLY_REPORT] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/weekly_learning_report.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def get_hypothesis_metrics(cur) -> Dict:
    """Get hypothesis generation and lifecycle metrics."""
    # Hypotheses born this week
    cur.execute("""
        SELECT COUNT(*) as born
        FROM fhq_learning.hypothesis_canon
        WHERE created_at > NOW() - INTERVAL '7 days'
    """)
    born = cur.fetchone()['born']

    # Hypotheses killed this week
    cur.execute("""
        SELECT COUNT(*) as killed
        FROM fhq_learning.hypothesis_canon
        WHERE death_timestamp > NOW() - INTERVAL '7 days'
    """)
    killed = cur.fetchone()['killed']

    # Active hypotheses
    cur.execute("""
        SELECT COUNT(*) as active
        FROM fhq_learning.hypothesis_canon
        WHERE status IN ('ACTIVE', 'DRAFT', 'WEAKENED')
    """)
    active = cur.fetchone()['active']

    # By generator
    cur.execute("""
        SELECT generator_id, COUNT(*) as count
        FROM fhq_learning.hypothesis_canon
        WHERE created_at > NOW() - INTERVAL '7 days'
        GROUP BY generator_id
        ORDER BY count DESC
    """)
    by_generator = {row['generator_id']: row['count'] for row in cur.fetchall()}

    return {
        'born_7d': born,
        'killed_7d': killed,
        'active': active,
        'daily_birth_rate': round(born / 7, 1),
        'by_generator': by_generator
    }


def get_decision_pack_metrics(cur) -> Dict:
    """Get decision pack generation metrics."""
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE execution_status = 'EXECUTED') as executed,
            COUNT(*) FILTER (WHERE execution_status = 'PENDING') as pending,
            COUNT(*) FILTER (WHERE execution_status = 'FAILED') as failed,
            COUNT(*) FILTER (WHERE execution_status = 'EXPIRED') as expired
        FROM fhq_learning.decision_packs
        WHERE created_at > NOW() - INTERVAL '7 days'
    """)
    row = cur.fetchone()

    return {
        'total_7d': row['total'],
        'executed': row['executed'],
        'pending': row['pending'],
        'failed': row['failed'],
        'expired': row['expired']
    }


def get_lvi_metrics(cur) -> Dict:
    """Get Learning Velocity Index metrics."""
    # Latest LVI
    cur.execute("""
        SELECT lvi_value, computed_at
        FROM fhq_governance.lvi_canonical
        ORDER BY computed_at DESC LIMIT 1
    """)
    row = cur.fetchone()
    current_lvi = float(row['lvi_value']) if row else 0.0
    computed_at = row['computed_at'].isoformat() if row else None

    # LVI 7 days ago
    cur.execute("""
        SELECT lvi_value
        FROM fhq_governance.lvi_canonical
        WHERE computed_at < NOW() - INTERVAL '7 days'
        ORDER BY computed_at DESC LIMIT 1
    """)
    row = cur.fetchone()
    prior_lvi = float(row['lvi_value']) if row else 0.0

    return {
        'current': current_lvi,
        'prior_7d': prior_lvi,
        'change': round(current_lvi - prior_lvi, 4),
        'trend': 'UP' if current_lvi > prior_lvi else 'DOWN' if current_lvi < prior_lvi else 'FLAT',
        'computed_at': computed_at
    }


def get_memory_metrics(cur) -> Dict:
    """Get memory citation and block metrics."""
    # Memory citations (hypotheses with prior_hypotheses_count > 0)
    cur.execute("""
        SELECT COUNT(*) as cited
        FROM fhq_learning.hypothesis_canon
        WHERE created_at > NOW() - INTERVAL '7 days'
          AND prior_hypotheses_count IS NOT NULL
          AND prior_hypotheses_count > 0
    """)
    citations = cur.fetchone()['cited']

    # Birth blocks
    cur.execute("""
        SELECT COUNT(*) as blocks, block_reason
        FROM fhq_learning.hypothesis_birth_blocks
        WHERE blocked_at > NOW() - INTERVAL '7 days'
        GROUP BY block_reason
    """)
    blocks_by_reason = {row['block_reason']: row['blocks'] for row in cur.fetchall()}

    total_blocks = sum(blocks_by_reason.values())

    return {
        'memory_citations_7d': citations,
        'birth_blocks_7d': total_blocks,
        'blocks_by_reason': blocks_by_reason
    }


def get_fss_metrics(cur) -> Dict:
    """Get Forecast Skill Score metrics."""
    # Current FSS average
    cur.execute("""
        SELECT AVG(fss_value) as avg_fss
        FROM fhq_research.fss_computation_log
        WHERE computation_timestamp > NOW() - INTERVAL '7 days'
    """)
    row = cur.fetchone()
    current_fss = float(row['avg_fss']) if row and row['avg_fss'] else None

    # Prior week FSS
    cur.execute("""
        SELECT AVG(fss_value) as avg_fss
        FROM fhq_research.fss_computation_log
        WHERE computation_timestamp BETWEEN NOW() - INTERVAL '14 days' AND NOW() - INTERVAL '7 days'
    """)
    row = cur.fetchone()
    prior_fss = float(row['avg_fss']) if row and row['avg_fss'] else None

    # Skill tier distribution
    cur.execute("""
        SELECT skill_tier, COUNT(*) as count
        FROM fhq_research.skill_segmentation
        GROUP BY skill_tier
    """)
    skill_dist = {row['skill_tier']: row['count'] for row in cur.fetchall()}

    return {
        'current_avg': round(current_fss, 3) if current_fss else None,
        'prior_7d_avg': round(prior_fss, 3) if prior_fss else None,
        'change': round(current_fss - prior_fss, 3) if current_fss and prior_fss else None,
        'trend': 'IMPROVING' if current_fss and prior_fss and current_fss > prior_fss else 'DECLINING',
        'skill_distribution': skill_dist
    }


def get_phase2_readiness(cur) -> Dict:
    """Check Phase-2 readiness criteria."""
    # LVI non-zero
    cur.execute("""
        SELECT lvi_value > 0 as nonzero
        FROM fhq_governance.lvi_canonical
        ORDER BY computed_at DESC LIMIT 1
    """)
    row = cur.fetchone()
    lvi_nonzero = row['nonzero'] if row else False

    # Decision packs flowing
    cur.execute("""
        SELECT COUNT(*) > 0 as flowing
        FROM fhq_learning.decision_packs
        WHERE created_at > NOW() - INTERVAL '7 days'
    """)
    packs_flowing = cur.fetchone()['flowing']

    # FSS improving (or at least not catastrophic)
    cur.execute("""
        SELECT AVG(fss_value) > -0.50 as acceptable
        FROM fhq_research.fss_computation_log
        WHERE computation_timestamp > NOW() - INTERVAL '7 days'
    """)
    fss_acceptable = cur.fetchone()['acceptable']

    # Memory citations exist
    cur.execute("""
        SELECT COUNT(*) as count
        FROM fhq_learning.hypothesis_canon
        WHERE prior_hypotheses_count IS NOT NULL
          AND prior_hypotheses_count > 0
    """)
    memory_count = cur.fetchone()['count']

    # DEFCON level
    cur.execute("""
        SELECT defcon_level
        FROM fhq_governance.defcon_state
        WHERE is_current = true
    """)
    row = cur.fetchone()
    defcon = row['defcon_level'] if row else 'UNKNOWN'

    criteria_met = sum([
        lvi_nonzero,
        packs_flowing,
        fss_acceptable or False,
        memory_count > 0
    ])

    return {
        'lvi_nonzero': lvi_nonzero,
        'decision_packs_flowing': packs_flowing,
        'fss_acceptable': fss_acceptable,
        'memory_citations_exist': memory_count > 0,
        'memory_citation_count': memory_count,
        'defcon_level': defcon,
        'criteria_met': criteria_met,
        'criteria_total': 4,
        'ready': criteria_met >= 3 and defcon not in ('RED', 'BLACK')
    }


def generate_weekly_report() -> Dict:
    """Generate complete weekly learning report."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    report = {
        'report_type': 'WEEKLY_LEARNING_REPORT',
        'directive': 'CEO-DIR-2026-128',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'generated_by': 'STIG',
        'ec_contract': 'EC-003',
        'period': {
            'start': (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
            'end': datetime.now(timezone.utc).isoformat()
        },
        'hypotheses': get_hypothesis_metrics(cur),
        'decision_packs': get_decision_pack_metrics(cur),
        'lvi': get_lvi_metrics(cur),
        'memory': get_memory_metrics(cur),
        'fss': get_fss_metrics(cur),
        'phase2_readiness': get_phase2_readiness(cur)
    }

    # Generate evidence hash
    report_str = json.dumps(report, sort_keys=True, default=str)
    report['evidence_hash'] = 'sha256:' + hashlib.sha256(report_str.encode()).hexdigest()

    conn.close()
    return report


def print_summary(report: Dict):
    """Print human-readable summary."""
    print("\n" + "=" * 70)
    print("WEEKLY LEARNING REPORT")
    print(f"Period: {report['period']['start'][:10]} to {report['period']['end'][:10]}")
    print("=" * 70)

    print("\n[ HYPOTHESES ]")
    h = report['hypotheses']
    print(f"  Born (7d):    {h['born_7d']} ({h['daily_birth_rate']}/day)")
    print(f"  Killed (7d):  {h['killed_7d']}")
    print(f"  Active:       {h['active']}")

    print("\n[ DECISION PACKS ]")
    dp = report['decision_packs']
    print(f"  Total (7d):   {dp['total_7d']}")
    print(f"  Executed:     {dp['executed']}")
    print(f"  Pending:      {dp['pending']}")

    print("\n[ LVI - Learning Velocity Index ]")
    lvi = report['lvi']
    print(f"  Current:      {lvi['current']}")
    print(f"  Prior (7d):   {lvi['prior_7d']}")
    print(f"  Trend:        {lvi['trend']} ({lvi['change']:+.4f})")

    print("\n[ MEMORY ]")
    m = report['memory']
    print(f"  Citations:    {m['memory_citations_7d']}")
    print(f"  Birth blocks: {m['birth_blocks_7d']}")
    if m['blocks_by_reason']:
        for reason, count in m['blocks_by_reason'].items():
            print(f"    - {reason}: {count}")

    print("\n[ FSS - Forecast Skill Score ]")
    fss = report['fss']
    print(f"  Current avg:  {fss['current_avg']}")
    print(f"  Prior (7d):   {fss['prior_7d_avg']}")
    print(f"  Trend:        {fss['trend']}")
    print(f"  Skill distribution:")
    for tier, count in fss.get('skill_distribution', {}).items():
        print(f"    - {tier}: {count} assets")

    print("\n[ PHASE-2 READINESS ]")
    p2 = report['phase2_readiness']
    print(f"  LVI > 0:           {'YES' if p2['lvi_nonzero'] else 'NO'}")
    print(f"  Packs flowing:     {'YES' if p2['decision_packs_flowing'] else 'NO'}")
    print(f"  FSS acceptable:    {'YES' if p2['fss_acceptable'] else 'NO'}")
    print(f"  Memory active:     {'YES' if p2['memory_citations_exist'] else 'NO'} ({p2['memory_citation_count']} citations)")
    print(f"  DEFCON:            {p2['defcon_level']}")
    print(f"  Criteria met:      {p2['criteria_met']}/{p2['criteria_total']}")
    print(f"  PHASE-2 READY:     {'YES' if p2['ready'] else 'NO'}")

    print("\n" + "=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Weekly Learning Report Generator')
    parser.add_argument('--json', action='store_true', help='Output JSON only')
    parser.add_argument('--save', action='store_true', help='Save to evidence file')
    args = parser.parse_args()

    logger.info("Generating weekly learning report...")

    report = generate_weekly_report()

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print_summary(report)

    if args.save:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence_path = os.path.join(script_dir, 'evidence', f'WEEKLY_LEARNING_REPORT_{timestamp}.json')
        with open(evidence_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Saved: {evidence_path}")

    return report


if __name__ == '__main__':
    main()
