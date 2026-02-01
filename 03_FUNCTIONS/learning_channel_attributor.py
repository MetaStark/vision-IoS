#!/usr/bin/env python3
"""
Learning Channel Attributor - CEO-DIR-2026-112 Mandate C
Tags each evaluation into exactly one learning category:
  - INVERSION_DELTA_LEARNING
  - FRICTION_REFUSAL_LEARNING
  - CALIBRATION_BRIER_LEARNING

Authors: UMA + STIG
"""

import psycopg2
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

class LearningChannelAttributor:
    """
    Mandate C: Learning Channel Attribution
    Goal: Prove that learning is occurring even when trades are blocked.
    """

    CHANNELS = {
        'INVERSION_DELTA_LEARNING': 'Systematic blindspot discovery via STRESS regime inversions',
        'FRICTION_REFUSAL_LEARNING': 'Market constraint learning via TTL/liquidity/DEFCON blocks',
        'CALIBRATION_BRIER_LEARNING': 'Confidence calibration via Reliability vs Resolution'
    }

    def __init__(self, db_conn):
        self.conn = db_conn
        self.conn.autocommit = True
        self.cur = db_conn.cursor()

    def attribute_evaluation(self, evaluation_id: str) -> Dict[str, Any]:
        """
        Attribute a single evaluation to exactly one learning channel.
        """
        # Fetch evaluation
        self.cur.execute('''
            SELECT
                evaluation_id, source_signal_id, source_module, signal_class,
                instrument, direction, confidence, cpto_decision,
                refusal_reason, refusal_category, regime_at_evaluation,
                is_inversion_candidate, inversion_verified,
                slippage_saved_bps, ttl_check_passed
            FROM fhq_research.evaluations
            WHERE evaluation_id = %s
        ''', (evaluation_id,))

        row = self.cur.fetchone()
        if not row:
            return {'error': f'Evaluation {evaluation_id} not found'}

        eval_data = {
            'evaluation_id': str(row[0]),
            'source_signal_id': str(row[1]),
            'source_module': row[2],
            'signal_class': row[3],
            'instrument': row[4],
            'direction': row[5],
            'confidence': float(row[6]),
            'cpto_decision': row[7],
            'refusal_reason': row[8],
            'refusal_category': row[9],
            'regime': row[10],
            'is_inversion': row[11],
            'inversion_verified': row[12],
            'slippage_saved_bps': float(row[13]) if row[13] else 0,
            'ttl_passed': row[14]
        }

        # Determine learning channel
        channel, rationale, channel_data, surprise = self._classify_channel(eval_data)

        # Insert attribution
        self.cur.execute('''
            INSERT INTO fhq_research.learning_channel_attribution (
                evaluation_id, source_signal_id, learning_channel,
                inversion_delta_data, friction_data, calibration_data,
                surprise_metric, attributed_by, attribution_rationale
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING attribution_id
        ''', (
            evaluation_id,
            eval_data['source_signal_id'],
            channel,
            json.dumps(channel_data) if channel == 'INVERSION_DELTA_LEARNING' else None,
            json.dumps(channel_data) if channel == 'FRICTION_REFUSAL_LEARNING' else None,
            json.dumps(channel_data) if channel == 'CALIBRATION_BRIER_LEARNING' else None,
            surprise,
            'UMA+STIG',
            rationale
        ))

        attribution_id = self.cur.fetchone()[0]

        return {
            'attribution_id': str(attribution_id),
            'evaluation_id': evaluation_id,
            'channel': channel,
            'rationale': rationale,
            'surprise_metric': surprise,
            'channel_data': channel_data
        }

    def _classify_channel(self, eval_data: Dict) -> Tuple[str, str, Dict, Optional[float]]:
        """
        Classify evaluation into exactly one learning channel.
        Returns (channel, rationale, channel_data, surprise_metric)
        """
        # Priority 1: Friction/Refusal Learning (blocked signals)
        if eval_data['cpto_decision'].startswith('BLOCKED'):
            channel = 'FRICTION_REFUSAL_LEARNING'
            rationale = f"Signal blocked by {eval_data['refusal_category']}: {eval_data['refusal_reason']}"
            channel_data = {
                'block_category': eval_data['refusal_category'],
                'block_reason': eval_data['refusal_reason'],
                'regime_at_block': eval_data['regime'],
                'confidence_at_block': eval_data['confidence'],
                'learning_insight': self._generate_friction_insight(eval_data)
            }
            # No surprise metric for blocked signals (no outcome yet)
            return channel, rationale, channel_data, None

        # Priority 2: Inversion Delta Learning (inversion candidates)
        if eval_data['is_inversion'] and eval_data['signal_class'] == 'LOW_CONFIDENCE_INVERSION_CANDIDATE':
            channel = 'INVERSION_DELTA_LEARNING'

            # Calculate surprise metric (CEO Addition)
            # Surprise = deviation from inverted belief
            # Higher = more unexpected outcome
            base_confidence = eval_data['confidence']
            inverted_confidence = 1.0 - base_confidence  # What we expected by inverting
            # For now, surprise is 0 since outcome not yet known
            surprise = 0.0  # Will be updated when outcome is verified

            rationale = f"Inversion candidate from {eval_data['regime']} regime with {base_confidence:.2%} original confidence"
            channel_data = {
                'original_confidence': base_confidence,
                'inverted_confidence': inverted_confidence,
                'regime': eval_data['regime'],
                'direction': eval_data['direction'],
                'slippage_saved_bps': eval_data['slippage_saved_bps'],
                'learning_insight': self._generate_inversion_insight(eval_data)
            }
            return channel, rationale, channel_data, surprise

        # Priority 3: Calibration/Brier Learning (standard signals)
        channel = 'CALIBRATION_BRIER_LEARNING'
        rationale = f"Standard signal for calibration: {eval_data['confidence']:.2%} confidence"
        channel_data = {
            'predicted_confidence': eval_data['confidence'],
            'regime': eval_data['regime'],
            'instrument': eval_data['instrument'],
            'direction': eval_data['direction'],
            'learning_insight': 'Calibration data point for Brier decomposition'
        }
        return channel, rationale, channel_data, None

    def _generate_friction_insight(self, eval_data: Dict) -> str:
        """Generate learning insight from friction event."""
        category = eval_data['refusal_category']
        if category == 'TTL':
            return f"Signal latency too high for {eval_data['regime']} regime. Consider pipeline optimization."
        elif category == 'LIQUIDITY':
            return f"Market depth insufficient for {eval_data['instrument']}. Size constraints learned."
        elif category == 'DEFCON':
            return f"DEFCON gate blocked at {eval_data['regime']} regime. Safety boundary confirmed."
        elif category == 'BROKER_TRUTH':
            return "Broker snapshot staleness detected. Freshness requirement validated."
        return f"Friction from {category}: constraint boundary discovered."

    def _generate_inversion_insight(self, eval_data: Dict) -> str:
        """Generate learning insight from inversion candidate."""
        return (
            f"STRESS regime at {eval_data['confidence']:.2%} inverted to {eval_data['direction']}. "
            f"Slippage saved: {eval_data['slippage_saved_bps']:.2f} bps. "
            f"Awaiting outcome for delta verification."
        )

    def attribute_all_pending(self) -> Dict[str, Any]:
        """Attribute all evaluations that don't have attribution yet."""
        self.cur.execute('''
            SELECT e.evaluation_id
            FROM fhq_research.evaluations e
            LEFT JOIN fhq_research.learning_channel_attribution a
                ON a.evaluation_id = e.evaluation_id
            WHERE a.attribution_id IS NULL
            ORDER BY e.created_at DESC
        ''')

        pending = self.cur.fetchall()
        results = []

        for (eval_id,) in pending:
            result = self.attribute_evaluation(str(eval_id))
            results.append(result)

        return {
            'attributed_count': len(results),
            'attributions': results
        }

    def get_channel_summary(self) -> Dict[str, Any]:
        """Get summary of learning by channel."""
        self.cur.execute('''
            SELECT
                learning_channel,
                COUNT(*) as count,
                AVG(surprise_metric) as avg_surprise
            FROM fhq_research.learning_channel_attribution
            GROUP BY learning_channel
            ORDER BY count DESC
        ''')

        channels = {}
        for row in self.cur.fetchall():
            channels[row[0]] = {
                'count': row[1],
                'avg_surprise': float(row[2]) if row[2] else None,
                'description': self.CHANNELS.get(row[0], 'Unknown')
            }

        return {
            'channels': channels,
            'total_attributions': sum(c['count'] for c in channels.values()),
            'generated_at': datetime.now(timezone.utc).isoformat()
        }


def main():
    """Run learning channel attribution for all pending evaluations."""
    conn = psycopg2.connect(
        host='127.0.0.1',
        port=54322,
        database='postgres',
        user='postgres',
        password='postgres'
    )

    print('=' * 60)
    print('CEO-DIR-2026-112 MANDATE C: Learning Channel Attribution')
    print('=' * 60)

    attributor = LearningChannelAttributor(conn)

    # Attribute all pending
    print('\n[ATTRIBUTING PENDING EVALUATIONS]')
    results = attributor.attribute_all_pending()
    print(f'  Attributed: {results["attributed_count"]} evaluations')

    for attr in results['attributions']:
        print(f'\n  Evaluation: {attr["evaluation_id"][:8]}...')
        print(f'  Channel: {attr["channel"]}')
        print(f'  Rationale: {attr["rationale"]}')
        if attr['surprise_metric'] is not None:
            print(f'  Surprise Metric: {attr["surprise_metric"]:.4f}')

    # Get summary
    print('\n[LEARNING CHANNEL SUMMARY]')
    summary = attributor.get_channel_summary()
    for channel, data in summary['channels'].items():
        print(f'\n  {channel}:')
        print(f'    Count: {data["count"]}')
        print(f'    Description: {data["description"]}')

    print(f'\n  Total Attributions: {summary["total_attributions"]}')

    print('\n' + '=' * 60)
    print('MANDATE C: COMPLETE')
    print('=' * 60)

    conn.close()


if __name__ == '__main__':
    main()
