#!/usr/bin/env python3
"""
PHASE 1 STATISTICAL VALIDATION - CEO DIRECTIVE EXECUTION
Uses ONLY existing alpha_lab infrastructure
NO new tables, NO new abstractions, NO schema changes

CEO Directive: EXECUTE
Effective: Immediate
"""

import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime
import psycopg2

def run_phase1_validation():
    # Database connection
    conn = psycopg2.connect(
        host='127.0.0.1',
        port=54322,
        database='postgres',
        user='postgres',
        password='postgres'
    )

    print('='*70)
    print('PHASE 1: STATISTICAL VALIDATION - 10-YEAR BTC BACKTEST')
    print('CEO Directive: EXECUTE')
    print('Constraints: Existing infrastructure ONLY')
    print('='*70)
    print()

    # Step 1: Load BTC-USD price data
    print('[1/5] Loading BTC-USD 10-year price data...')
    query = '''
    SELECT date, open, high, low, close, volume
    FROM fhq_data.price_series
    WHERE listing_id = 'BTC-USD'
    ORDER BY date ASC
    '''
    df = pd.read_sql(query, conn)
    df['date'] = pd.to_datetime(df['date'])
    print(f'     Loaded {len(df)} daily bars')
    print(f'     Range: {df["date"].min().date()} to {df["date"].max().date()}')
    print(f'     Years: {(df["date"].max() - df["date"].min()).days / 365.25:.1f}')
    print()

    # Step 2: Calculate ATR for ATR-based exits
    print('[2/5] Calculating technical indicators (ATR-14)...')
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    df['atr'] = df['tr'].rolling(window=14).mean()
    df['atr_pct'] = df['atr'] / df['close'] * 100
    print(f'     ATR-14 calculated')
    print(f'     Average ATR%: {df["atr_pct"].mean():.2f}%')
    print()

    # Step 3: Define exit profiles to test
    exit_profiles = {
        'CURRENT': {'tp': 5.0, 'sl': 3.0, 'name': 'Current (+5%/-3%)'},
        'TIGHTER': {'tp': 3.0, 'sl': 2.0, 'name': 'Tighter (+3%/-2%)'},
        'WIDER':   {'tp': 8.0, 'sl': 5.0, 'name': 'Wider (+8%/-5%)'},
        'ATR':     {'tp_mult': 2.0, 'sl_mult': 1.5, 'name': 'ATR-based (2x/1.5x ATR)'}
    }

    print('[3/5] Running backtests for each exit profile...')
    print()

    def run_backtest(df, tp_pct=None, sl_pct=None, atr_tp_mult=None, atr_sl_mult=None, initial_capital=100000):
        """
        Simple long-only momentum backtest with configurable exits.
        Entry: Buy when price > 20-day SMA (simple trend following)
        Exit: Take profit, stop loss, or trend reversal
        """
        capital = initial_capital
        position = 0
        entry_price = 0
        trades = []
        equity_curve = []

        df = df.copy()
        df['sma20'] = df['close'].rolling(window=20).mean()

        for i in range(20, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            price = row['close']

            # Calculate dynamic TP/SL for ATR mode
            if atr_tp_mult is not None:
                current_atr_pct = row['atr_pct'] if not pd.isna(row['atr_pct']) else 3.0
                tp = current_atr_pct * atr_tp_mult
                sl = current_atr_pct * atr_sl_mult
            else:
                tp = tp_pct
                sl = sl_pct

            if position > 0:
                # Check exit conditions
                pnl_pct = (price - entry_price) / entry_price * 100

                exit_reason = None
                if pnl_pct >= tp:
                    exit_reason = 'TAKE_PROFIT'
                elif pnl_pct <= -sl:
                    exit_reason = 'STOP_LOSS'
                elif price < row['sma20']:  # Trend reversal
                    exit_reason = 'TREND_REVERSAL'

                if exit_reason:
                    pnl = (price - entry_price) * position
                    trades.append({
                        'entry_price': entry_price,
                        'exit_price': price,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'exit_reason': exit_reason
                    })
                    capital += pnl
                    position = 0
                    entry_price = 0
            else:
                # Entry condition: price crosses above SMA20
                if prev_row['close'] < prev_row['sma20'] and price > row['sma20']:
                    # Position sizing: 10% of capital per trade
                    position_value = capital * 0.10
                    position = position_value / price
                    entry_price = price

            # Record equity
            if position > 0:
                equity = capital + (price - entry_price) * position
            else:
                equity = capital
            equity_curve.append(equity)

        return trades, equity_curve

    results = {}

    for profile_id, profile in exit_profiles.items():
        print(f'   Testing {profile["name"]}...')

        if 'tp_mult' in profile:
            trades, equity = run_backtest(
                df,
                atr_tp_mult=profile['tp_mult'],
                atr_sl_mult=profile['sl_mult']
            )
        else:
            trades, equity = run_backtest(
                df,
                tp_pct=profile['tp'],
                sl_pct=profile['sl']
            )

        # Calculate metrics
        equity = np.array(equity)
        returns = np.diff(equity) / equity[:-1]
        returns = returns[np.isfinite(returns)]

        total_return = (equity[-1] - 100000) / 100000 * 100
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        max_dd = np.min((equity - np.maximum.accumulate(equity)) / np.maximum.accumulate(equity)) * 100

        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] < 0]
        win_rate = len(wins) / len(trades) * 100 if trades else 0

        avg_win = np.mean([t['pnl_pct'] for t in wins]) if wins else 0
        avg_loss = np.mean([t['pnl_pct'] for t in losses]) if losses else 0

        results[profile_id] = {
            'name': profile['name'],
            'total_trades': len(trades),
            'win_rate': win_rate,
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'avg_win_pct': avg_win,
            'avg_loss_pct': avg_loss,
            'returns': returns,
            'trades': trades
        }

        print(f'      Trades: {len(trades)}, Win Rate: {win_rate:.1f}%, Return: {total_return:.1f}%, Sharpe: {sharpe:.2f}')

    print()

    # Step 4: Bootstrap statistical validation
    print('[4/5] Running bootstrap validation (n=1000)...')
    print()

    def bootstrap_sharpe(returns, n_iterations=1000, confidence=0.95):
        """Bootstrap confidence interval for Sharpe ratio"""
        np.random.seed(42)
        n = len(returns)
        bootstrap_sharpes = []

        for _ in range(n_iterations):
            sample = np.random.choice(returns, size=n, replace=True)
            if np.std(sample) > 0:
                sharpe = np.mean(sample) / np.std(sample) * np.sqrt(252)
            else:
                sharpe = 0
            bootstrap_sharpes.append(sharpe)

        bootstrap_sharpes = np.array(bootstrap_sharpes)
        alpha = 1 - confidence
        ci_lower = np.percentile(bootstrap_sharpes, alpha/2 * 100)
        ci_upper = np.percentile(bootstrap_sharpes, (1 - alpha/2) * 100)
        p_value = np.mean(bootstrap_sharpes <= 0)  # Probability Sharpe <= 0

        return {
            'point_estimate': np.mean(bootstrap_sharpes),
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'std_error': np.std(bootstrap_sharpes),
            'p_value': p_value,
            'significant': p_value < 0.05
        }

    for profile_id, res in results.items():
        bootstrap = bootstrap_sharpe(res['returns'])
        res['bootstrap'] = bootstrap
        sig = 'YES' if bootstrap['significant'] else 'NO'
        print(f'   {res["name"]}:')
        print(f'      Sharpe: {bootstrap["point_estimate"]:.3f} [{bootstrap["ci_lower"]:.3f}, {bootstrap["ci_upper"]:.3f}]')
        print(f'      p-value: {bootstrap["p_value"]:.4f} | Significant (p<0.05): {sig}')
        print()

    # Step 5: Comparative analysis and recommendation
    print('[5/5] COMPARATIVE ANALYSIS & RECOMMENDATION')
    print('='*70)
    print()
    print('EXIT PROFILE COMPARISON (10-year BTC backtest)')
    print('-'*70)
    print(f'{"Profile":<25} {"Trades":>8} {"Win%":>8} {"Return%":>10} {"Sharpe":>8} {"MaxDD%":>10} {"Sig?":>6}')
    print('-'*70)

    for profile_id, res in results.items():
        sig = 'YES' if res['bootstrap']['significant'] else 'NO'
        print(f'{res["name"]:<25} {res["total_trades"]:>8} {res["win_rate"]:>7.1f}% {res["total_return"]:>9.1f}% {res["sharpe_ratio"]:>8.2f} {res["max_drawdown"]:>9.1f}% {sig:>6}')

    print('-'*70)
    print()

    # Determine best profile
    best_sharpe = max(results.values(), key=lambda x: x['sharpe_ratio'])
    best_return = max(results.values(), key=lambda x: x['total_return'])
    best_winrate = max(results.values(), key=lambda x: x['win_rate'])

    # Count significant results
    significant_count = sum(1 for r in results.values() if r['bootstrap']['significant'])

    print('STATISTICAL SIGNIFICANCE SUMMARY:')
    print(f'   Profiles tested: 4')
    print(f'   Statistically significant (p<0.05): {significant_count}')
    print()

    print('BEST PERFORMERS:')
    print(f'   Highest Sharpe: {best_sharpe["name"]} ({best_sharpe["sharpe_ratio"]:.2f})')
    print(f'   Highest Return: {best_return["name"]} ({best_return["total_return"]:.1f}%)')
    print(f'   Highest Win Rate: {best_winrate["name"]} ({best_winrate["win_rate"]:.1f}%)')
    print()

    # Final recommendation
    print('='*70)
    print('PHASE 1 DELIVERABLE: RECOMMENDATION')
    print('='*70)
    print()

    current = results['CURRENT']
    if current['bootstrap']['significant']:
        print('VERDICT: CURRENT EXIT MODEL (+5%/-3%) IS ACCEPTABLE')
        print()
        print('Evidence:')
        print(f'   - Sharpe ratio: {current["sharpe_ratio"]:.2f} (95% CI: [{current["bootstrap"]["ci_lower"]:.2f}, {current["bootstrap"]["ci_upper"]:.2f}])')
        print(f'   - p-value: {current["bootstrap"]["p_value"]:.4f} < 0.05 (statistically significant)')
        print(f'   - Win rate: {current["win_rate"]:.1f}%')
        print(f'   - Max drawdown: {current["max_drawdown"]:.1f}%')
        print()
        print('The current exit model can be deployed in Shadow Ledger.')
        verdict = 'ACCEPTABLE'
    else:
        print('VERDICT: CURRENT EXIT MODEL (+5%/-3%) REQUIRES REPLACEMENT')
        print()
        print('Evidence:')
        print(f'   - p-value: {current["bootstrap"]["p_value"]:.4f} >= 0.05 (NOT statistically significant)')
        print()
        # Find best alternative
        alternatives = [(k, v) for k, v in results.items() if k != 'CURRENT' and v['bootstrap']['significant']]
        if alternatives:
            best_alt = max(alternatives, key=lambda x: x[1]['sharpe_ratio'])
            print(f'RECOMMENDED REPLACEMENT: {best_alt[1]["name"]}')
            print(f'   - Sharpe: {best_alt[1]["sharpe_ratio"]:.2f}')
            print(f'   - p-value: {best_alt[1]["bootstrap"]["p_value"]:.4f}')
        else:
            print('WARNING: No exit profile achieved statistical significance.')
            print('Further research required.')
        verdict = 'REQUIRES_REPLACEMENT'

    print()
    print('='*70)
    print('PHASE 1 COMPLETE')
    print('='*70)

    conn.close()

    # Return structured result for governance logging
    return {
        'verdict': verdict,
        'profiles_tested': 4,
        'significant_count': significant_count,
        'current_profile': {
            'sharpe': current['sharpe_ratio'],
            'p_value': current['bootstrap']['p_value'],
            'significant': current['bootstrap']['significant']
        },
        'best_sharpe_profile': best_sharpe['name'],
        'timestamp': datetime.utcnow().isoformat()
    }


if __name__ == '__main__':
    result = run_phase1_validation()
    print()
    print('Result JSON:')
    print(json.dumps(result, indent=2))
