#!/usr/bin/env python3
"""
PHASE 2: CONDITIONAL EXIT VALIDATION - CEO DIRECTIVE EXECUTION

Objective: Test whether context-conditioned exits (using IoS-003 regime state)
produce statistically valid improvement over unconditional exits.

Conditioning:
- BULL regime -> wider exits (+8%/-5%)
- BEAR regime -> tighter exits (+3%/-2%)
- NEUTRAL/other -> baseline (+5%/-3%)

Constraints:
- Same 10-year BTC dataset as Phase 1
- Same entry logic
- Same bootstrap protocol (n >= 1000)
- Same significance threshold (p < 0.05)
- NO new indicators, NO new formulas
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone
import psycopg2

def run_phase2_validation():
    # Database connection
    conn = psycopg2.connect(
        host='127.0.0.1',
        port=54322,
        database='postgres',
        user='postgres',
        password='postgres'
    )

    print('='*70)
    print('PHASE 2: CONDITIONAL EXIT VALIDATION')
    print('CEO Directive: EXECUTE')
    print('Conditioning Variable: IoS-003 Regime State')
    print('='*70)
    print()

    # Step 1: Load BTC-USD price data
    print('[1/6] Loading BTC-USD price data...')
    price_query = '''
    SELECT date, open, high, low, close, volume
    FROM fhq_data.price_series
    WHERE listing_id = 'BTC-USD'
    ORDER BY date ASC
    '''
    df_price = pd.read_sql(price_query, conn)
    df_price['date'] = pd.to_datetime(df_price['date']).dt.date
    print(f'      Price data: {len(df_price)} bars')

    # Step 2: Load IoS-003 regime classifications
    print('[2/6] Loading IoS-003 regime classifications...')
    regime_query = '''
    SELECT
        timestamp::date as date,
        regime_classification,
        regime_confidence
    FROM fhq_perception.regime_daily
    WHERE asset_id LIKE '%BTC%'
    ORDER BY timestamp ASC
    '''
    df_regime = pd.read_sql(regime_query, conn)
    df_regime['date'] = pd.to_datetime(df_regime['date']).dt.date
    print(f'      Regime data: {len(df_regime)} days')

    # Regime distribution
    regime_counts = df_regime['regime_classification'].value_counts()
    print(f'      Regime distribution:')
    for regime, count in regime_counts.items():
        print(f'         {regime}: {count} days')
    print()

    # Step 3: Merge price and regime data
    print('[3/6] Merging price and regime data...')
    df = pd.merge(df_price, df_regime, on='date', how='inner')
    df = df.sort_values('date').reset_index(drop=True)
    print(f'      Merged dataset: {len(df)} bars with regime labels')
    print(f'      Date range: {df["date"].min()} to {df["date"].max()}')
    print()

    # Map regimes to exit conditions
    # BULL: BULL, STRONG_BULL -> wider exits
    # BEAR: BEAR, STRONG_BEAR, STRESS, BROKEN -> tighter exits
    # NEUTRAL: NEUTRAL, VOLATILE_NON_DIRECTIONAL -> baseline
    def map_regime_to_exit(regime):
        if regime in ['BULL', 'STRONG_BULL']:
            return 'BULL'
        elif regime in ['BEAR', 'STRONG_BEAR', 'STRESS', 'BROKEN']:
            return 'BEAR'
        else:
            return 'NEUTRAL'

    df['exit_regime'] = df['regime_classification'].apply(map_regime_to_exit)

    exit_regime_counts = df['exit_regime'].value_counts()
    print(f'      Exit regime mapping:')
    for regime, count in exit_regime_counts.items():
        print(f'         {regime}: {count} days')
    print()

    # Calculate SMA for entry logic
    df['sma20'] = df['close'].rolling(window=20).mean()

    # Step 4: Define exit configurations
    print('[4/6] Running backtests...')
    print()

    # Exit parameters (from Phase 1 tested ranges ONLY)
    EXIT_PARAMS = {
        'BULL': {'tp': 8.0, 'sl': 5.0},      # Wider exits
        'BEAR': {'tp': 3.0, 'sl': 2.0},      # Tighter exits
        'NEUTRAL': {'tp': 5.0, 'sl': 3.0}    # Baseline
    }

    def run_backtest(df, conditional=True, initial_capital=100000):
        """
        Run backtest with conditional or unconditional exits.

        Args:
            df: DataFrame with price data, regime, sma20
            conditional: If True, use regime-conditioned exits. If False, use baseline.
            initial_capital: Starting capital
        """
        capital = initial_capital
        position = 0
        entry_price = 0
        trades = []
        equity_curve = []

        for i in range(20, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            price = row['close']
            regime = row['exit_regime']

            # Determine exit parameters
            if conditional:
                tp = EXIT_PARAMS[regime]['tp']
                sl = EXIT_PARAMS[regime]['sl']
            else:
                # Unconditional baseline (+5%/-3%)
                tp = 5.0
                sl = 3.0

            if position > 0:
                # Check exit conditions
                pnl_pct = (price - entry_price) / entry_price * 100

                exit_reason = None
                if pnl_pct >= tp:
                    exit_reason = 'TAKE_PROFIT'
                elif pnl_pct <= -sl:
                    exit_reason = 'STOP_LOSS'
                elif price < row['sma20']:
                    exit_reason = 'TREND_REVERSAL'

                if exit_reason:
                    pnl = (price - entry_price) * position
                    trades.append({
                        'entry_price': entry_price,
                        'exit_price': price,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'exit_reason': exit_reason,
                        'regime_at_exit': regime
                    })
                    capital += pnl
                    position = 0
                    entry_price = 0
            else:
                # Entry: price crosses above SMA20
                if prev_row['close'] < prev_row['sma20'] and price > row['sma20']:
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

    def calculate_metrics(trades, equity, initial_capital=100000):
        """Calculate performance metrics."""
        equity = np.array(equity)
        returns = np.diff(equity) / equity[:-1]
        returns = returns[np.isfinite(returns)]

        total_return = (equity[-1] - initial_capital) / initial_capital * 100
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        max_dd = np.min((equity - np.maximum.accumulate(equity)) / np.maximum.accumulate(equity)) * 100

        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] < 0]
        win_rate = len(wins) / len(trades) * 100 if trades else 0

        return {
            'total_trades': len(trades),
            'win_rate': win_rate,
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'returns': returns
        }

    def bootstrap_sharpe(returns, n_iterations=1000, confidence=0.95):
        """Bootstrap confidence interval for Sharpe ratio."""
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
        p_value = np.mean(bootstrap_sharpes <= 0)

        return {
            'point_estimate': np.mean(bootstrap_sharpes),
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'std_error': np.std(bootstrap_sharpes),
            'p_value': p_value,
            'significant': p_value < 0.05
        }

    # Run unconditional baseline
    print('   Running UNCONDITIONAL baseline (+5%/-3%)...')
    trades_uncond, equity_uncond = run_backtest(df, conditional=False)
    metrics_uncond = calculate_metrics(trades_uncond, equity_uncond)
    print(f'      Trades: {metrics_uncond["total_trades"]}, Win Rate: {metrics_uncond["win_rate"]:.1f}%, '
          f'Return: {metrics_uncond["total_return"]:.1f}%, Sharpe: {metrics_uncond["sharpe_ratio"]:.2f}')

    # Run conditional exits
    print('   Running CONDITIONAL exits (BULL:+8/-5, BEAR:+3/-2, NEUTRAL:+5/-3)...')
    trades_cond, equity_cond = run_backtest(df, conditional=True)
    metrics_cond = calculate_metrics(trades_cond, equity_cond)
    print(f'      Trades: {metrics_cond["total_trades"]}, Win Rate: {metrics_cond["win_rate"]:.1f}%, '
          f'Return: {metrics_cond["total_return"]:.1f}%, Sharpe: {metrics_cond["sharpe_ratio"]:.2f}')
    print()

    # Step 5: Bootstrap validation
    print('[5/6] Running bootstrap validation (n=1000)...')
    print()

    bootstrap_uncond = bootstrap_sharpe(metrics_uncond['returns'])
    bootstrap_cond = bootstrap_sharpe(metrics_cond['returns'])

    print('   UNCONDITIONAL (+5%/-3%):')
    print(f'      Sharpe: {bootstrap_uncond["point_estimate"]:.3f} '
          f'[{bootstrap_uncond["ci_lower"]:.3f}, {bootstrap_uncond["ci_upper"]:.3f}]')
    print(f'      p-value: {bootstrap_uncond["p_value"]:.4f} | '
          f'Significant: {"YES" if bootstrap_uncond["significant"] else "NO"}')
    print()

    print('   CONDITIONAL (regime-based):')
    print(f'      Sharpe: {bootstrap_cond["point_estimate"]:.3f} '
          f'[{bootstrap_cond["ci_lower"]:.3f}, {bootstrap_cond["ci_upper"]:.3f}]')
    print(f'      p-value: {bootstrap_cond["p_value"]:.4f} | '
          f'Significant: {"YES" if bootstrap_cond["significant"] else "NO"}')
    print()

    # Step 6: Comparative analysis and verdict
    print('[6/6] COMPARATIVE ANALYSIS & VERDICT')
    print('='*70)
    print()

    # Comparison table
    print('CONDITIONAL vs UNCONDITIONAL COMPARISON')
    print('-'*70)
    print(f'{"Metric":<25} {"Unconditional":>20} {"Conditional":>20}')
    print('-'*70)
    print(f'{"Total Trades":<25} {metrics_uncond["total_trades"]:>20} {metrics_cond["total_trades"]:>20}')
    print(f'{"Win Rate":<25} {metrics_uncond["win_rate"]:>19.1f}% {metrics_cond["win_rate"]:>19.1f}%')
    print(f'{"Total Return":<25} {metrics_uncond["total_return"]:>19.1f}% {metrics_cond["total_return"]:>19.1f}%')
    print(f'{"Sharpe Ratio":<25} {metrics_uncond["sharpe_ratio"]:>20.3f} {metrics_cond["sharpe_ratio"]:>20.3f}')
    print(f'{"Max Drawdown":<25} {metrics_uncond["max_drawdown"]:>19.1f}% {metrics_cond["max_drawdown"]:>19.1f}%')
    print(f'{"p-value":<25} {bootstrap_uncond["p_value"]:>20.4f} {bootstrap_cond["p_value"]:>20.4f}')
    print(f'{"Significant (p<0.05)":<25} {"YES" if bootstrap_uncond["significant"] else "NO":>20} {"YES" if bootstrap_cond["significant"] else "NO":>20}')
    print('-'*70)
    print()

    # Calculate improvement
    sharpe_improvement = metrics_cond['sharpe_ratio'] - metrics_uncond['sharpe_ratio']
    sharpe_improvement_pct = (sharpe_improvement / abs(metrics_uncond['sharpe_ratio'])) * 100 if metrics_uncond['sharpe_ratio'] != 0 else 0
    dd_improvement = metrics_cond['max_drawdown'] - metrics_uncond['max_drawdown']  # Less negative = better

    print('IMPROVEMENT ANALYSIS')
    print('-'*70)
    print(f'Sharpe Improvement: {sharpe_improvement:+.3f} ({sharpe_improvement_pct:+.1f}%)')
    print(f'MaxDD Change: {dd_improvement:+.1f}% ({"better" if dd_improvement > 0 else "worse"})')
    print()

    # Regime-segmented analysis
    print('REGIME-SEGMENTED PERFORMANCE')
    print('-'*70)
    for regime in ['BULL', 'BEAR', 'NEUTRAL']:
        regime_trades = [t for t in trades_cond if t['regime_at_exit'] == regime]
        if regime_trades:
            wins = len([t for t in regime_trades if t['pnl'] > 0])
            wr = wins / len(regime_trades) * 100
            avg_pnl = np.mean([t['pnl_pct'] for t in regime_trades])
            print(f'{regime:<10} Trades: {len(regime_trades):>4}, Win Rate: {wr:>5.1f}%, Avg PnL: {avg_pnl:>+6.2f}%')
    print('-'*70)
    print()

    # VERDICT
    print('='*70)
    print('PHASE 2 VERDICT')
    print('='*70)
    print()

    # Evaluation criteria from CEO directive:
    # 1. p < 0.05
    # 2. Improved Sharpe vs unconditional
    # 3. Does not materially increase MaxDD

    cond_significant = bootstrap_cond['significant']
    sharpe_improved = metrics_cond['sharpe_ratio'] > metrics_uncond['sharpe_ratio']
    dd_acceptable = metrics_cond['max_drawdown'] >= (metrics_uncond['max_drawdown'] - 2.0)  # Allow 2% worse

    if cond_significant and sharpe_improved and dd_acceptable:
        verdict = 'VALIDATED'
        print('VERDICT: VALIDATED')
        print()
        print('Conditional exit model PASSES all criteria:')
        print(f'   [X] p-value < 0.05: {bootstrap_cond["p_value"]:.4f}')
        print(f'   [X] Sharpe improved: {metrics_uncond["sharpe_ratio"]:.3f} -> {metrics_cond["sharpe_ratio"]:.3f}')
        print(f'   [X] MaxDD acceptable: {metrics_cond["max_drawdown"]:.1f}%')
        print()
        print('AUTHORIZED FOR SHADOW LEDGER DEPLOYMENT')
    else:
        verdict = 'INVALIDATED'
        print('VERDICT: INVALIDATED')
        print()
        print('Conditional exit model FAILS criteria:')
        if not cond_significant:
            print(f'   [ ] p-value < 0.05: FAILED (p = {bootstrap_cond["p_value"]:.4f})')
        else:
            print(f'   [X] p-value < 0.05: {bootstrap_cond["p_value"]:.4f}')

        if not sharpe_improved:
            print(f'   [ ] Sharpe improved: FAILED ({metrics_uncond["sharpe_ratio"]:.3f} -> {metrics_cond["sharpe_ratio"]:.3f})')
        else:
            print(f'   [X] Sharpe improved: {metrics_uncond["sharpe_ratio"]:.3f} -> {metrics_cond["sharpe_ratio"]:.3f}')

        if not dd_acceptable:
            print(f'   [ ] MaxDD acceptable: FAILED ({metrics_cond["max_drawdown"]:.1f}%)')
        else:
            print(f'   [X] MaxDD acceptable: {metrics_cond["max_drawdown"]:.1f}%')

        print()
        print('EXIT-BASED ALPHA HYPOTHESIS IS REJECTED')
        print('NO deployment authorized')

    print()
    print('='*70)
    print('PHASE 2 COMPLETE')
    print('='*70)

    conn.close()

    return {
        'verdict': verdict,
        'unconditional': {
            'sharpe': float(metrics_uncond['sharpe_ratio']),
            'p_value': float(bootstrap_uncond['p_value']),
            'significant': bool(bootstrap_uncond['significant']),
            'max_dd': float(metrics_uncond['max_drawdown'])
        },
        'conditional': {
            'sharpe': float(metrics_cond['sharpe_ratio']),
            'p_value': float(bootstrap_cond['p_value']),
            'significant': bool(bootstrap_cond['significant']),
            'max_dd': float(metrics_cond['max_drawdown'])
        },
        'improvement': {
            'sharpe_delta': float(sharpe_improvement),
            'sharpe_pct': float(sharpe_improvement_pct)
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


if __name__ == '__main__':
    import json
    result = run_phase2_validation()
    print()
    print('Result JSON:')
    print(json.dumps(result, indent=2))
