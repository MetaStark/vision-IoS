#!/usr/bin/env python3
"""
FINN Outcome Analyzer
CEO-DIR-2026-033: Paper Trade Learning Engine

Purpose: Extract lessons from paper trades, classify errors (TYPE_D/TYPE_E),
         and feed learnings back into calibration system.

Author: STIG (CTO)
Date: 2026-01-10
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('PGHOST', '127.0.0.1'),
        port=os.getenv('PGPORT', '54322'),
        database=os.getenv('PGDATABASE', 'postgres'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', 'postgres')
    )

class FinnOutcomeAnalyzer:
    """
    Analyzes paper trade outcomes and extracts epistemic lessons.

    Error Classification:
    - TYPE_D (Regime Illusion): Correct direction, wrong magnitude/timing due to regime misread
    - TYPE_E (Correlation Breakdown): Historical correlation failed in current market
    """

    def __init__(self):
        self.conn = get_db_connection()
        self.evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')

    def get_open_paper_trades(self):
        """Get all open paper positions."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    trade_id,
                    canonical_id,
                    direction,
                    raw_confidence,
                    calibrated_confidence,
                    calibrated_position_size,
                    entry_price,
                    effective_entry_price,
                    simulated_slippage,
                    slippage_rule_applied,
                    novelty_score,
                    regime_at_entry,
                    decision_plan_id,
                    created_at
                FROM fhq_governance.paper_ledger
                WHERE exit_price IS NULL
                ORDER BY created_at DESC
            """)
            return cur.fetchall()

    def get_current_prices(self, canonical_ids: list):
        """Get latest available prices for assets."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT ON (canonical_id)
                    canonical_id,
                    close as current_price,
                    high,
                    low,
                    volume,
                    timestamp as price_time
                FROM fhq_market.prices
                WHERE canonical_id = ANY(%s)
                ORDER BY canonical_id, timestamp DESC
            """, (canonical_ids,))
            return {row['canonical_id']: row for row in cur.fetchall()}

    def calculate_unrealized_pnl(self, trade: dict, current_price: float) -> dict:
        """Calculate unrealized P&L for an open position."""
        entry = float(trade['effective_entry_price'] or trade['entry_price'])
        size = float(trade['calibrated_position_size'])
        direction = trade['direction']

        if direction == 'LONG':
            pnl_pct = (current_price - entry) / entry
        else:  # SHORT
            pnl_pct = (entry - current_price) / entry

        pnl_absolute = pnl_pct * size * 100000  # Assuming $100k notional

        return {
            'entry_price': entry,
            'current_price': current_price,
            'direction': direction,
            'pnl_pct': round(pnl_pct * 100, 4),
            'pnl_absolute': round(pnl_absolute, 2),
            'is_winning': pnl_pct > 0
        }

    def close_paper_trade(self, trade_id: str, exit_price: float,
                          outcome_correct: bool, error_type: str = None):
        """Close a paper trade and record outcome."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_governance.paper_ledger
                SET
                    exit_price = %s,
                    exit_timestamp = NOW(),
                    effective_exit_price = %s * (1 - CASE WHEN direction = 'SHORT' THEN simulated_slippage ELSE -simulated_slippage END),
                    outcome_correct = %s,
                    error_type = %s,
                    paper_pnl = CASE
                        WHEN direction = 'LONG' THEN (%s - entry_price) * calibrated_position_size
                        ELSE (entry_price - %s) * calibrated_position_size
                    END,
                    paper_pnl_pct = CASE
                        WHEN direction = 'LONG' THEN (%s - entry_price) / entry_price * 100
                        ELSE (entry_price - %s) / entry_price * 100
                    END,
                    updated_at = NOW()
                WHERE trade_id = %s
                RETURNING trade_id, canonical_id, outcome_correct, error_type, paper_pnl_pct
            """, (exit_price, exit_price, outcome_correct, error_type,
                  exit_price, exit_price, exit_price, exit_price, trade_id))
            self.conn.commit()
            return cur.fetchone()

    def classify_error(self, trade: dict, outcome: dict, regime_now: str) -> str:
        """
        Classify prediction error as TYPE_D or TYPE_E.

        TYPE_D (Regime Illusion):
        - Regime changed between entry and exit
        - Or regime was misclassified at entry

        TYPE_E (Correlation Breakdown):
        - Regime stable but expected correlation didn't hold
        - Historical pattern failed in current market
        """
        regime_at_entry = trade['regime_at_entry']

        # If regime changed, it's likely TYPE_D
        if regime_at_entry != regime_now:
            return 'TYPE_D'

        # If high novelty score and wrong, likely TYPE_E
        if trade['novelty_score'] and float(trade['novelty_score']) > 0.7:
            return 'TYPE_E'

        # If high confidence but wrong, TYPE_D (overconfident in regime read)
        if float(trade['calibrated_confidence']) > 0.40 and not outcome['is_winning']:
            return 'TYPE_D'

        # Default to TYPE_E for unexplained failures
        return 'TYPE_E'

    def extract_lesson(self, trade: dict, outcome: dict, error_type: str) -> dict:
        """Extract a structured lesson from a closed trade."""
        lesson = {
            'trade_id': str(trade['trade_id']),
            'canonical_id': trade['canonical_id'],
            'lesson_type': 'CONFIRMATION' if outcome['is_winning'] else 'CORRECTION',
            'error_type': error_type,
            'confidence_was': float(trade['calibrated_confidence']),
            'direction_was': trade['direction'],
            'regime_was': trade['regime_at_entry'],
            'novelty_was': float(trade['novelty_score']) if trade['novelty_score'] else 0,
            'pnl_pct': outcome['pnl_pct'],
            'lesson_text': self._generate_lesson_text(trade, outcome, error_type),
            'extracted_at': datetime.utcnow().isoformat()
        }
        return lesson

    def _generate_lesson_text(self, trade: dict, outcome: dict, error_type: str) -> str:
        """Generate human-readable lesson text."""
        asset = trade['canonical_id']
        direction = trade['direction']
        regime = trade['regime_at_entry']
        conf = float(trade['calibrated_confidence']) * 100
        pnl = outcome['pnl_pct']

        if outcome['is_winning']:
            return f"{asset} {direction} in {regime} regime: Correct at {conf:.1f}% confidence (+{pnl:.2f}%). Pattern validated."
        else:
            if error_type == 'TYPE_D':
                return f"{asset} {direction} in {regime} regime: REGIME ILLUSION at {conf:.1f}% confidence ({pnl:.2f}%). Regime read was wrong or changed."
            else:
                return f"{asset} {direction} in {regime} regime: CORRELATION BREAKDOWN at {conf:.1f}% confidence ({pnl:.2f}%). Historical pattern failed."

    def update_epistemic_health(self, lessons: list):
        """Update daily epistemic health metrics based on lessons."""
        type_d_count = sum(1 for l in lessons if l.get('error_type') == 'TYPE_D' and l['lesson_type'] == 'CORRECTION')
        type_e_count = sum(1 for l in lessons if l.get('error_type') == 'TYPE_E' and l['lesson_type'] == 'CORRECTION')
        hits = sum(1 for l in lessons if l['lesson_type'] == 'CONFIRMATION')
        total = len(lessons)

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.epistemic_health_daily (
                    health_date, trades_today, hits_today, hit_rate_today,
                    type_d_count, type_e_count
                ) VALUES (
                    CURRENT_DATE, %s, %s, %s, %s, %s
                )
                ON CONFLICT (health_date) DO UPDATE SET
                    trades_today = EXCLUDED.trades_today,
                    hits_today = EXCLUDED.hits_today,
                    hit_rate_today = EXCLUDED.hit_rate_today,
                    type_d_count = EXCLUDED.type_d_count,
                    type_e_count = EXCLUDED.type_e_count,
                    computed_at = NOW()
            """, (total, hits, hits/total if total > 0 else None, type_d_count, type_e_count))
            self.conn.commit()

    def generate_7h_learning_report(self) -> dict:
        """
        Generate a report on what we've learned in the last 7 hours.
        Even with open trades, we can analyze:
        1. Unrealized P&L trajectory
        2. Regime stability
        3. Volatility behavior vs expectations
        4. Slippage accuracy
        """
        trades = self.get_open_paper_trades()
        if not trades:
            return {'status': 'NO_TRADES', 'message': 'No open paper trades found'}

        canonical_ids = [t['canonical_id'] for t in trades]
        prices = self.get_current_prices(canonical_ids)

        report = {
            'report_type': 'FINN_7H_LEARNING_REPORT',
            'generated_at': datetime.utcnow().isoformat(),
            'hours_elapsed': 7,
            'trades_analyzed': len(trades),
            'positions': [],
            'aggregate_metrics': {},
            'preliminary_learnings': [],
            'data_quality_issues': []
        }

        total_unrealized_pnl = 0
        winning_count = 0

        for trade in trades:
            canonical_id = trade['canonical_id']
            price_data = prices.get(canonical_id)

            if not price_data:
                report['data_quality_issues'].append({
                    'asset': canonical_id,
                    'issue': 'NO_PRICE_DATA',
                    'severity': 'HIGH'
                })
                continue

            # Check data freshness
            price_age_hours = (datetime.utcnow() - price_data['price_time'].replace(tzinfo=None)).total_seconds() / 3600

            if price_age_hours > 24:
                report['data_quality_issues'].append({
                    'asset': canonical_id,
                    'issue': 'STALE_PRICE_DATA',
                    'price_age_hours': round(price_age_hours, 1),
                    'severity': 'MEDIUM'
                })

            current_price = float(price_data['current_price'])
            pnl = self.calculate_unrealized_pnl(trade, current_price)

            position_analysis = {
                'trade_id': str(trade['trade_id']),
                'asset': canonical_id,
                'direction': trade['direction'],
                'entry_price': float(trade['entry_price']),
                'current_price': current_price,
                'price_age_hours': round(price_age_hours, 1),
                'unrealized_pnl_pct': pnl['pnl_pct'],
                'is_winning': pnl['is_winning'],
                'calibrated_confidence': float(trade['calibrated_confidence']),
                'novelty_score': float(trade['novelty_score']) if trade['novelty_score'] else 0,
                'regime_at_entry': trade['regime_at_entry'],
                'slippage_rule': trade['slippage_rule_applied']
            }

            report['positions'].append(position_analysis)
            total_unrealized_pnl += pnl['pnl_pct']
            if pnl['is_winning']:
                winning_count += 1

        # Aggregate metrics
        valid_positions = len(report['positions'])
        if valid_positions > 0:
            report['aggregate_metrics'] = {
                'total_unrealized_pnl_pct': round(total_unrealized_pnl, 4),
                'avg_unrealized_pnl_pct': round(total_unrealized_pnl / valid_positions, 4),
                'winning_positions': winning_count,
                'losing_positions': valid_positions - winning_count,
                'win_rate': round(winning_count / valid_positions * 100, 1)
            }

        # Generate preliminary learnings
        report['preliminary_learnings'] = self._generate_preliminary_learnings(report)

        return report

    def _generate_preliminary_learnings(self, report: dict) -> list:
        """Generate preliminary learnings even before trades close."""
        learnings = []

        # Data quality learning
        if report['data_quality_issues']:
            stale_count = sum(1 for i in report['data_quality_issues'] if i['issue'] == 'STALE_PRICE_DATA')
            if stale_count > 0:
                learnings.append({
                    'learning_id': 'L001_DATA_FRESHNESS',
                    'type': 'INFRASTRUCTURE',
                    'severity': 'HIGH',
                    'observation': f'{stale_count} assets have stale price data (>24h old)',
                    'implication': 'Paper P&L calculations are unreliable until price feeds are current',
                    'action_required': 'CEIO must ensure price ingestion is running for paper trading assets'
                })

        # Volatility vs slippage learning
        positions = report.get('positions', [])
        high_vol_positions = [p for p in positions if p.get('slippage_rule') == 'HIGH_VOLATILITY_TIER_1']
        if high_vol_positions:
            learnings.append({
                'learning_id': 'L002_VOLATILITY_DETECTION',
                'type': 'EXECUTION',
                'severity': 'INFO',
                'observation': f'{len(high_vol_positions)} positions triggered HIGH_VOLATILITY slippage',
                'assets': [p['asset'] for p in high_vol_positions],
                'implication': 'Dynamic slippage is correctly identifying volatile assets',
                'action_required': None
            })

        # Calibration gate effectiveness
        capped_positions = [p for p in positions if p.get('calibrated_confidence') == 0.4659]
        if capped_positions:
            learnings.append({
                'learning_id': 'L003_CALIBRATION_GATE_ACTIVE',
                'type': 'EPISTEMIC',
                'severity': 'INFO',
                'observation': f'{len(capped_positions)} positions hit the 46.59% confidence ceiling',
                'implication': 'Calibration gates are preventing overconfidence as designed',
                'action_required': None
            })

        # Borderline confidence learning
        borderline = [p for p in positions if 0.30 <= p.get('calibrated_confidence', 0) <= 0.35]
        if borderline:
            learnings.append({
                'learning_id': 'L004_BORDERLINE_TEST',
                'type': 'DIAGNOSTIC',
                'severity': 'INFO',
                'observation': f'{len(borderline)} borderline confidence trades in flight',
                'assets': [p['asset'] for p in borderline],
                'implication': 'Testing threshold boundary for learning purposes',
                'action_required': 'Monitor outcome to calibrate minimum threshold'
            })

        # Win rate early signal (unreliable but indicative)
        metrics = report.get('aggregate_metrics', {})
        if metrics.get('win_rate') is not None:
            win_rate = metrics['win_rate']
            learnings.append({
                'learning_id': 'L005_EARLY_SIGNAL',
                'type': 'PERFORMANCE',
                'severity': 'WARNING' if win_rate < 50 else 'INFO',
                'observation': f'Unrealized win rate: {win_rate}% ({metrics["winning_positions"]}/{metrics["winning_positions"] + metrics["losing_positions"]})',
                'implication': 'PRELIMINARY - based on potentially stale prices',
                'action_required': 'Wait for fresh price data before drawing conclusions'
            })

        return learnings

    def save_evidence(self, report: dict):
        """Save report as court-proof evidence."""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"FINN_OUTCOME_ANALYSIS_{timestamp}.json"
        filepath = os.path.join(self.evidence_dir, filename)

        # Add hash for court-proof
        report['content_hash'] = hashlib.sha256(
            json.dumps(report, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        print(f"Evidence saved: {filepath}")
        return filepath


def main():
    """Run FINN outcome analysis."""
    print("=" * 60)
    print("FINN OUTCOME ANALYZER")
    print("CEO-DIR-2026-033: 7-Hour Learning Report")
    print("=" * 60)

    analyzer = FinnOutcomeAnalyzer()

    # Generate 7-hour learning report
    report = analyzer.generate_7h_learning_report()

    # Print summary
    print(f"\nTrades Analyzed: {report.get('trades_analyzed', 0)}")
    print(f"Data Quality Issues: {len(report.get('data_quality_issues', []))}")

    print("\n--- POSITIONS ---")
    for pos in report.get('positions', []):
        status = "+" if pos['is_winning'] else "-"
        print(f"  {pos['asset']:10} {pos['direction']:5} @ ${pos['entry_price']:.2f} -> ${pos['current_price']:.2f} "
              f"({status}{abs(pos['unrealized_pnl_pct']):.2f}%) [conf: {pos['calibrated_confidence']*100:.1f}%]")

    print("\n--- AGGREGATE ---")
    metrics = report.get('aggregate_metrics', {})
    if metrics:
        print(f"  Total Unrealized P&L: {metrics.get('total_unrealized_pnl_pct', 0):.4f}%")
        print(f"  Win Rate (unrealized): {metrics.get('win_rate', 0):.1f}%")

    print("\n--- PRELIMINARY LEARNINGS ---")
    for learning in report.get('preliminary_learnings', []):
        severity = learning.get('severity', 'INFO')
        icon = "[!]" if severity == 'WARNING' else "[i]" if severity == 'INFO' else "[X]"
        print(f"  [{learning['learning_id']}] {icon} {learning['observation']}")
        if learning.get('action_required'):
            print(f"      -> Action: {learning['action_required']}")

    print("\n--- DATA QUALITY ISSUES ---")
    for issue in report.get('data_quality_issues', []):
        print(f"  [!] {issue['asset']}: {issue['issue']} (severity: {issue['severity']})")

    # Save evidence
    filepath = analyzer.save_evidence(report)

    print("\n" + "=" * 60)
    print("REPORT COMPLETE")
    print("=" * 60)

    return report


if __name__ == '__main__':
    main()
