#!/usr/bin/env python3
"""
P2 Strategic Equity Integration Script
IoS-004, IoS-005, IoS-007 activation
"""

import json
import hashlib
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
import psycopg2
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent.parent / '.env', override=True)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    regime_data = {
        'AAPL': {'regime': 'BULL', 'confidence': 0.95},
        'MSFT': {'regime': 'BEAR', 'confidence': 0.95},
        'NVDA': {'regime': 'NEUTRAL', 'confidence': 0.60},
        'QQQ': {'regime': 'BULL', 'confidence': 0.95},
        'SPY': {'regime': 'BULL', 'confidence': 0.95}
    }

    today = date.today()
    model_id = str(uuid.uuid4())

    print('=== IoS-004: Activating Exposure Generation (Conservative Warmup) ===')

    # CEO Directive: Conservative exposure for first 48 hours
    WARMUP_MULTIPLIER = 0.25  # 25% of normal exposure during warmup

    for asset, data in regime_data.items():
        # Calculate exposure based on regime
        if data['regime'] == 'BULL':
            exposure_raw = Decimal('0.20') * Decimal(str(data['confidence']))
        elif data['regime'] == 'BEAR':
            exposure_raw = Decimal('-0.10') * Decimal(str(data['confidence']))
        else:
            exposure_raw = Decimal('0.05')

        # Apply warmup constraint
        exposure_constrained = exposure_raw * Decimal(str(WARMUP_MULTIPLIER))
        cash_weight = Decimal('1.0') - abs(exposure_constrained)

        lineage_hash = hashlib.sha256(f'{asset}|{today}|{exposure_raw}|warmup'.encode()).hexdigest()[:32]
        hash_self = hashlib.sha256(f'GENESIS|{lineage_hash}'.encode()).hexdigest()[:32]

        try:
            cur.execute('DELETE FROM fhq_positions.target_exposure_daily WHERE asset_id = %s AND timestamp = %s', (asset, today))

            cur.execute('''
                INSERT INTO fhq_positions.target_exposure_daily
                (asset_id, timestamp, exposure_raw, exposure_constrained, cash_weight, model_id,
                 regime_label, confidence, lineage_hash, hash_prev, hash_self, engine_version, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ''', (
                asset, today, float(exposure_raw), float(exposure_constrained), float(cash_weight),
                model_id, data['regime'], data['confidence'], lineage_hash, 'GENESIS_EQUITY', hash_self, 'ios004_v1.0'
            ))
            print(f'  {asset}: raw={float(exposure_raw):.2%}, constrained={float(exposure_constrained):.2%} (warmup 25%)')
        except Exception as e:
            print(f'  {asset}: ERROR - {e}')

    print()
    print('=== IoS-005: Activating Skill Measurement (Baseline) ===')

    for asset, data in regime_data.items():
        try:
            cur.execute('''
                SELECT metric_id FROM fhq_research.forecast_skill_metrics
                WHERE metric_scope = 'asset' AND scope_value = %s
            ''', (asset,))

            if cur.fetchone():
                print(f'  {asset}: baseline already exists')
                continue

            cur.execute('''
                INSERT INTO fhq_research.forecast_skill_metrics
                (metric_id, metric_scope, scope_value, period_start, period_end,
                 forecast_count, resolved_count, brier_score_mean, brier_score_std, brier_skill_score,
                 log_score_mean, log_score_std, hit_rate, hit_rate_confidence_low, hit_rate_confidence_high,
                 calibration_error, overconfidence_ratio, drift_detected, computed_at, computed_by, hash_chain_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)
            ''', (
                str(uuid.uuid4()), 'asset', asset, today, today,
                0, 0, None, None, None,
                None, None, None, None, None,
                None, None, False, 'STIG.ios005_baseline', f'BASELINE_{asset}_{today}'
            ))
            print(f'  {asset}: skill baseline initialized')
        except Exception as e:
            print(f'  {asset}: ERROR - {e}')

    print()
    print('=== IoS-007: Emitting Alpha Graph Edges ===')

    # Create nodes for equities
    nodes_created = 0
    for asset in regime_data.keys():
        try:
            cur.execute('SELECT node_id FROM vision_signals.alpha_graph_nodes WHERE node_id = %s', (asset,))
            if not cur.fetchone():
                cur.execute('''
                    INSERT INTO vision_signals.alpha_graph_nodes
                    (node_id, node_type, display_name, data_source, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                ''', (asset, 'EQUITY', asset, 'yahoo_chart_v8_raw', True))
                nodes_created += 1
        except Exception as e:
            print(f'  Node {asset}: ERROR - {e}')

    print(f'  Created {nodes_created} new equity nodes')

    # Create indicator nodes
    indicator_nodes = ['RSI_14', 'MACD', 'BB_WIDTH', 'ATR_14', 'EMA_STRUCTURE']
    for ind in indicator_nodes:
        try:
            cur.execute('SELECT node_id FROM vision_signals.alpha_graph_nodes WHERE node_id = %s', (ind,))
            if not cur.fetchone():
                cur.execute('''
                    INSERT INTO vision_signals.alpha_graph_nodes
                    (node_id, node_type, display_name, data_source, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                ''', (ind, 'INDICATOR', ind, 'calc_indicators_v1', True))
        except Exception as e:
            pass

    # Create causal edges
    edges_created = 0
    edge_types = [
        ('RSI_14', 'MOMENTUM_SIGNAL', 0.30),
        ('MACD', 'TREND_SIGNAL', 0.35),
        ('EMA_STRUCTURE', 'TREND_STRUCTURE', 0.25),
        ('BB_WIDTH', 'VOLATILITY_SIGNAL', 0.10)
    ]

    for asset, data in regime_data.items():
        for source, edge_type, weight in edge_types:
            try:
                cur.execute('''
                    INSERT INTO vision_signals.alpha_graph_edges
                    (edge_id, source_node, target_node, edge_type, confidence, causal_weight,
                     is_active, evidence_count, last_validated, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ''', (
                    str(uuid.uuid4()), source, asset, edge_type,
                    data['confidence'], weight, True, 1
                ))
                edges_created += 1
            except Exception as e:
                pass

    print(f'  Created {edges_created} causal edges')

    # Verify
    print()
    print('=== Verification ===')
    cur.execute('SELECT COUNT(*) FROM fhq_positions.target_exposure_daily WHERE timestamp = %s', (today,))
    print(f'  target_exposure_daily: {cur.fetchone()[0]} equity records')

    cur.execute("SELECT COUNT(*) FROM fhq_research.forecast_skill_metrics WHERE metric_scope = 'asset'")
    print(f'  forecast_skill_metrics: {cur.fetchone()[0]} asset baselines')

    cur.execute("SELECT COUNT(*) FROM vision_signals.alpha_graph_nodes WHERE node_type = 'EQUITY'")
    print(f'  alpha_graph_nodes: {cur.fetchone()[0]} equity nodes')

    cur.execute('''SELECT COUNT(*) FROM vision_signals.alpha_graph_edges
                   WHERE target_node IN ('NVDA','AAPL','MSFT','SPY','QQQ')''')
    print(f'  alpha_graph_edges: {cur.fetchone()[0]} equity edges')

    cur.close()
    conn.close()
    print()
    print('IoS-004, IoS-005, IoS-007 integration complete.')

if __name__ == '__main__':
    main()
