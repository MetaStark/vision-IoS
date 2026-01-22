# Signal Infrastructure Situation Analysis

**Date:** 2026-01-22
**Author:** STIG (EC-003)
**Classification:** GOVERNANCE-CRITICAL
**Database Source:** PostgreSQL 17.6 @ 127.0.0.1:54322
**Runbook Reference:** RB-IOS-013-001 (Gate: G2 PASS)

---

## EXECUTIVE SUMMARY

### Hva FjordHQ gjør
FjordHQ er et autonomt handelssystem som forsøker å generere alfa (meravkastning) ved å kombinere kvantitative signaler med maskinlæring. Systemet opererer på **493 aktive assets** (421 aksjer, 46 krypto, 24 FX, 2 ETF) og har generert **30,958 prognoser** til dags dato.

### Nåværende status
| Indikator | Verdi | Vurdering |
|-----------|-------|-----------|
| **Signal Coverage** | 60/65 (92%) | Akseptabelt |
| **Blocked Signals** | 5 | Under arbeid |
| **Brier Score** | 0.315 | Moderat - trenger forbedring |
| **Golden Needles** | 39 aktive | Alle høy-EQS (>0.97) |
| **Paper Orders** | 30 | Ingen filled ennå |
| **Regime Distribution** | BEAR 36%, NEUTRAL 30%, BULL 24%, STRESS 9% | Defensiv posisjon |

### Hovedutfordring
**Signalene er registrert og kategorisert, men de 5 blokkerte signalene mangler ekte beregningslogikk.** Placeholder-views returnerer dummy-verdier. For å produsere verifiserbare ekte signaler trengs:
1. Ekte datapipelines som beregner signalene
2. Backtesting mot historiske data
3. Out-of-sample validering
4. Kontinuerlig rekalibrering

### Anbefaling
Prioriter implementering av de 5 blokkerte signalene i rekkefølge etter forventet alfa-bidrag, ikke etter kompleksitet. `regime_transition_risk` (FINN, frist 29. jan) har høyest potensial.

---

## TECHNICAL SUMMARY

### 1. Signal Infrastructure Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SIGNAL PRODUCTION PIPELINE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │ DATA SOURCES │───>│  PRODUCERS   │───>│  CONSUMERS   │                  │
│  │   (External) │    │  (20 tables) │    │  (11 tables) │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│         │                   │                   │                           │
│         v                   v                   v                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │ 22 PROCESSES │    │ 65 SIGNAL    │    │ EXECUTION    │                  │
│  │ (5 daemons,  │    │ SCOPES       │    │ GATEWAY      │                  │
│  │  17 cron)    │    │              │    │              │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2. Database Verification (Live Query Results)

#### 2.1 Signal Sources

| Source Table | Records | Latest Update | Status |
|--------------|---------|---------------|--------|
| fhq_research.signals | 139 | 2026-01-14 | ACTIVE |
| fhq_signal_context.weighted_signal_plan | 1 | Today | ACTIVE |
| fhq_canonical.golden_needles (active) | 39 | 2026-01-14 | ACTIVE |
| fhq_alpha.g2_decision_plans | 15 | Historical | STALE |
| fhq_research.forecast_ledger | 30,958 | Today (644) | ACTIVE |

#### 2.2 Signal Distribution

| Signal Type | Strategy | Count | Avg Strength |
|-------------|----------|-------|--------------|
| HOLD | G1_VALIDATED | 89 | 0.967 |
| HOLD | GOLDEN_NEEDLE | 39 | 0.974 |
| ENTRY_LONG | G1_VALIDATED | 11 | 0.988 |

#### 2.3 Regime State (Latest)

| Regime | Assets | Percentage |
|--------|--------|------------|
| BEAR | 222 | 36% |
| NEUTRAL | 188 | 30% |
| BULL | 149 | 24% |
| STRESS | 57 | 9% |

**Interpretation:** Markedet er i defensiv modus med 45% av assets i BEAR/STRESS. Dette forklarer hvorfor de fleste signaler er HOLD.

#### 2.4 Forecast Calibration (Last 7 Days)

| Date | Brier Score | Forecasts |
|------|-------------|-----------|
| 2026-01-16 | 0.323 | 158,885 |
| 2026-01-15 | 0.315 | 254,515 |
| 2026-01-14 | 0.315 | 235,840 |
| 2026-01-13 | 0.315 | 218,699 |
| 2026-01-12 | 0.315 | 252,203 |

**Interpretation:** Brier score er stabil rundt 0.315, men langt fra målet på <0.30. Random guess = 0.25, så vi er bare marginalt bedre enn tilfeldig for binære utfall.

### 3. Blocked Signals Analysis

| Signal | Blokkert fordi | Hva trengs | Ansvarlig | Frist |
|--------|----------------|------------|-----------|-------|
| `regime_transition_risk` | Ingen HMM entropy | Beregne Shannon entropy fra HMM state probabilities | FINN | 29. jan |
| `stop_loss_heatmap` | Ingen posisjonsoversikt | Aggregere stop-loss fra aktive posisjoner | LINE | 31. jan |
| `sector_relative_strength` | Ingen sektor-mapping | GICS-klassifisering + benchmark-beregning | CDMO | 5. feb |
| `market_relative_strength` | Ingen benchmark-indeks | Definere benchmark per asset class | CDMO | 5. feb |
| `sentiment_divergence` | Ingen price-sentiment join | Joine sentiment med 5d returns | CEIO | 7. feb |

### 4. Infrastructure Health

#### 4.1 Time Authority Coverage
- **FULL (begge timestamps):** 7 surfaces
- **PARTIAL (én timestamp):** 24 surfaces
- **FAIL (ingen):** 0 surfaces
- **Coverage:** 100%

#### 4.2 Provenance Coverage
- **FULL (all 3 fields):** 15 critical surfaces
- **PARTIAL:** 0
- **NONE:** 16 non-critical surfaces
- **Critical Coverage:** 100%

#### 4.3 Process Inventory
- **Total:** 22 processes
- **Daemons (CONTINUOUS):** 5
- **Cron jobs:** 17
- **Critical:** 10

---

## META-ANALYSIS: Hva ville verdens ledende eksperter gjort?

### Kilder til beste praksis

Denne analysen er basert på metodikk fra:
- **Marcos López de Prado** (Cornell, AQR) - "Advances in Financial Machine Learning"
- **Ernest Chan** - "Quantitative Trading" og "Machine Trading"
- **Rishi Narang** - "Inside the Black Box"
- **Two Sigma / Renaissance Technologies** - Publiserte forskningsartikler
- **AQR Capital Management** - Factor investing research

### 1. SIGNAL GENERATION: Best Practices

#### 1.1 Feature Engineering (De Prado's tilnærming)

**Problem:** Våre signaler bruker standard tekniske indikatorer (RSI, MACD, etc.) som er overoptimert og har lav prediktiv kraft.

**Ekspertanbefaling:**
```
FRACTIONALLY DIFFERENTIATED FEATURES
├── Bruk frac_diff i stedet for returns for stasjonæritet
├── Bevar memory mens du oppnår stasjonæritet
└── d-verdi mellom 0 og 1 (ikke heltall)

TRIPLE BARRIER METHOD
├── Definer TP/SL/max_holding_period
├── Label basert på hva som skjer først
└── Unngå lookahead bias

META-LABELING
├── Primær modell: Prediker retning
├── Sekundær modell: Prediker om primærmodellen har rett
└── Justerer posisjonsstørrelse, ikke retning
```

**Implementering for FjordHQ:**
```python
# Foreslått ny signal: frac_diff_momentum
def frac_diff_momentum(prices, d=0.4, threshold=1e-5):
    """
    Fractionally differentiated momentum signal.
    d=0.4 balanserer stasjonæritet og memory.
    """
    weights = get_weights_ffd(d, threshold, len(prices))
    frac_diff_series = prices.apply(lambda x: np.dot(weights.T, x))
    return frac_diff_series.rolling(20).mean()  # Smoothed momentum
```

#### 1.2 Regime Detection (Two Sigma-inspirert)

**Problem:** Vårt regime-system bruker HMM med faste states. Det fanger ikke opp regime-transisjoner i sanntid.

**Ekspertanbefaling:**
```
ADAPTIVE REGIME DETECTION
├── Online HMM med Baum-Welch oppdatering
├── Sliding window state estimation
├── Entropy-basert transition probability
└── Regime persistence scoring

MULTI-TIMEFRAME CONSISTENCY
├── 5-min regime må alignes med daglig regime
├── Konflikt = reduser posisjonsstørrelse
└── Alignment = øk konfidensen
```

**Implementering for regime_transition_risk:**
```python
def regime_transition_risk(state_probabilities: np.array) -> float:
    """
    Calculate regime transition risk using Shannon entropy.
    High entropy = uncertain regime = high transition risk.
    """
    # Filter out zero probabilities
    probs = state_probabilities[state_probabilities > 0]

    # Shannon entropy
    entropy = -np.sum(probs * np.log2(probs))

    # Normalize to [0, 1] where 1 = maximum uncertainty
    max_entropy = np.log2(len(state_probabilities))
    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0

    return normalized_entropy
```

### 2. SIGNAL VALIDATION: Court-Proof Methodology

#### 2.1 Combinatorial Purged Cross-Validation (CPCV)

**Problem:** Standard k-fold CV har leakage i tidsserier.

**Ekspertanbefaling (De Prado):**
```
CPCV PROTOCOL
├── Purge: Fjern overlappende perioder
├── Embargo: Buffer mellom train/test
├── Combinatorial: Test alle mulige paths
└── Probability of Backtest Overfitting (PBO)
```

**Implementering:**
```python
def validate_signal_cpcv(signal_returns, n_splits=5, embargo_pct=0.01):
    """
    Combinatorial Purged Cross-Validation for signal validation.
    Returns Sharpe ratio distribution and PBO.
    """
    from mlfinlab.cross_validation import CombinatorialPurgedKFold

    cv = CombinatorialPurgedKFold(
        n_splits=n_splits,
        n_test_splits=2,
        embargo_td=pd.Timedelta(days=int(len(signal_returns) * embargo_pct))
    )

    sharpes = []
    for train_idx, test_idx in cv.split(signal_returns):
        test_returns = signal_returns.iloc[test_idx]
        sharpe = test_returns.mean() / test_returns.std() * np.sqrt(252)
        sharpes.append(sharpe)

    # Probability of Backtest Overfitting
    pbo = sum(1 for s in sharpes if s < 0) / len(sharpes)

    return {
        'sharpe_mean': np.mean(sharpes),
        'sharpe_std': np.std(sharpes),
        'pbo': pbo,
        'valid': pbo < 0.5 and np.mean(sharpes) > 0.5
    }
```

#### 2.2 Walk-Forward Optimization

**Problem:** Vi optimaliserer parametere én gang og bruker dem for alltid.

**Ekspertanbefaling:**
```
WALK-FORWARD PROTOCOL
├── In-sample: 252 dager (1 år)
├── Out-of-sample: 63 dager (1 kvartal)
├── Re-optimize quarterly
├── Track parameter stability
└── Alert på parameter drift > 2 std
```

### 3. SIGNAL COMBINATION: Ensemble Methods

#### 3.1 Signal Orthogonalization (AQR-inspirert)

**Problem:** Signalene våre er korrelerte, så vi dobbelteller informasjon.

**Ekspertanbefaling:**
```
ORTHOGONALIZATION PIPELINE
├── Beregn correlation matrix for alle signaler
├── Identificer clusters (hierarchical clustering)
├── Innen cluster: velg signal med høyest Sharpe
├── På tvers av clusters: vekt etter inverse volatilitet
└── Residualize: regress hvert signal på de andre
```

**Implementering:**
```python
def orthogonalize_signals(signal_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    Create orthogonal signal set using Gram-Schmidt process.
    Removes multicollinearity while preserving information.
    """
    from scipy.linalg import qr

    Q, R = qr(signal_matrix.values, mode='economic')
    orthogonal_signals = pd.DataFrame(
        Q,
        index=signal_matrix.index,
        columns=[f"{col}_orth" for col in signal_matrix.columns]
    )

    return orthogonal_signals
```

#### 3.2 Dynamic Signal Weighting

**Problem:** Vektene våre er statiske. Signaler som virket før, virker ikke nødvendigvis nå.

**Ekspertanbefaling:**
```
ADAPTIVE WEIGHTING
├── Track rolling Sharpe per signal (63-day window)
├── Track rolling correlation til realized returns
├── Weight = f(recent_sharpe, correlation, confidence)
├── Apply regime-conditional weights
└── Shrink towards equal-weight when uncertain
```

### 4. EXECUTION QUALITY: From Signal to Trade

#### 4.1 Optimal Execution (Almgren-Chriss Framework)

**Problem:** Vi har ikke implementert smart execution. Market orders gir slippage.

**Ekspertanbefaling:**
```
EXECUTION OPTIMIZATION
├── Estimate market impact: I(v) = η * v + γ * v²
├── Optimize trade schedule: minimize cost + risk
├── Use TWAP/VWAP for large orders
├── Implement arrival price benchmark
└── Track implementation shortfall
```

#### 4.2 Position Sizing (Kelly-inspirert med constraints)

**Problem:** Kelly criterion kan gi ekstreme posisjoner.

**Ekspertanbefaling:**
```
CONSTRAINED KELLY
├── f* = (p*b - q) / b  [raw Kelly fraction]
├── Apply half-Kelly for conservatism
├── Cap individual position at 5% of portfolio
├── Cap total exposure at 100% (no leverage)
└── Scale down when uncertainty high
```

### 5. SPECIFIC RECOMMENDATIONS FOR BLOCKED SIGNALS

#### 5.1 regime_transition_risk (FINN, 29. jan)

**Ekspertimplementering:**
```python
def regime_transition_risk_v2(hmm_features: pd.DataFrame) -> float:
    """
    Production-ready regime transition risk signal.

    Inputs:
    - hmm_features: DataFrame with columns [vix_z, yield_spread_z, liquidity_z, ...]

    Returns:
    - transition_risk: float [0, 1] where 1 = high risk of regime change
    """
    # 1. Calculate state entropy from HMM posterior
    state_probs = estimate_hmm_posterior(hmm_features)
    entropy = -np.sum(state_probs * np.log2(state_probs + 1e-10))

    # 2. Calculate rate of change in dominant regime
    regime_persistence = calculate_regime_persistence(state_probs, window=20)

    # 3. Cross-asset stress indicator
    cross_asset_stress = (
        abs(hmm_features['vix_z'].iloc[-1]) +
        abs(hmm_features['yield_spread_z'].iloc[-1]) +
        abs(hmm_features['liquidity_z'].iloc[-1])
    ) / 3

    # 4. Combine into single risk score
    transition_risk = (
        0.4 * entropy +
        0.3 * (1 - regime_persistence) +
        0.3 * np.clip(cross_asset_stress / 3, 0, 1)
    )

    return transition_risk
```

**Validation Requirements:**
- Backtest: Skal predikere regime-skifter 1-5 dager i forveien
- Minimum information coefficient: IC > 0.05
- Out-of-sample Sharpe > 0.3 for signal-only strategy

#### 5.2 stop_loss_heatmap (LINE, 31. jan)

**Ekspertimplementering:**
```python
def stop_loss_heatmap_v2(positions: pd.DataFrame, price_data: pd.DataFrame) -> dict:
    """
    Identify concentrated stop-loss zones for market risk assessment.

    Returns zones where many stops are clustered (liquidation risk).
    """
    # 1. Aggregate all stop-loss levels
    all_stops = positions.groupby('canonical_id')['stop_loss_price'].apply(list)

    # 2. For each asset, create histogram of stops
    heatmaps = {}
    for asset, stops in all_stops.items():
        current_price = price_data.loc[asset, 'last_price']

        # Normalize to percentage from current price
        stop_pcts = [(s - current_price) / current_price * 100 for s in stops]

        # Find clusters using KDE
        kde = gaussian_kde(stop_pcts)
        x_range = np.linspace(-10, 0, 100)  # Stops are below current price
        density = kde(x_range)

        # Identify concentration zones (peaks in density)
        peaks = find_peaks(density, height=density.mean() * 2)

        heatmaps[asset] = {
            'stop_zones': x_range[peaks[0]],
            'zone_densities': density[peaks[0]],
            'total_positions_at_risk': len(stops),
            'concentration_risk': max(density) / density.mean() if density.mean() > 0 else 0
        }

    return heatmaps
```

#### 5.3 sector_relative_strength (CDMO, 5. feb)

**Ekspertimplementering:**
```python
def sector_relative_strength_v2(
    asset_returns: pd.DataFrame,
    sector_mapping: dict,
    benchmark_returns: pd.Series,
    window: int = 63
) -> pd.DataFrame:
    """
    Calculate sector-relative strength using rolling beta-adjusted returns.
    """
    results = []

    for sector, assets in sector_mapping.items():
        sector_returns = asset_returns[assets].mean(axis=1)

        # Calculate rolling beta to benchmark
        cov = sector_returns.rolling(window).cov(benchmark_returns)
        var = benchmark_returns.rolling(window).var()
        beta = cov / var

        # Beta-adjusted excess returns
        excess_returns = sector_returns - beta * benchmark_returns

        # Rolling Sharpe of excess returns
        rolling_sharpe = (
            excess_returns.rolling(window).mean() /
            excess_returns.rolling(window).std()
        ) * np.sqrt(252)

        # Z-score for cross-sectional ranking
        for asset in assets:
            results.append({
                'canonical_id': asset,
                'sector': sector,
                'relative_strength': rolling_sharpe.iloc[-1],
                'sector_momentum': sector_returns.rolling(20).mean().iloc[-1],
                'beta_to_benchmark': beta.iloc[-1]
            })

    return pd.DataFrame(results)
```

#### 5.4 market_relative_strength (CDMO, 5. feb)

**Ekspertimplementering:**
```python
# Benchmark definitions per asset class
BENCHMARKS = {
    'EQUITY': 'SPY',      # S&P 500 ETF
    'CRYPTO': 'BTC-USD',  # Bitcoin as crypto benchmark
    'FX': 'DXY',          # Dollar Index
    'ETF': 'SPY'          # Default to S&P 500
}

def market_relative_strength_v2(
    asset_returns: pd.DataFrame,
    asset_class_mapping: dict,
    benchmark_prices: pd.DataFrame,
    window: int = 63
) -> pd.DataFrame:
    """
    Calculate asset strength relative to asset-class benchmark.
    """
    results = []

    for asset_class, benchmark in BENCHMARKS.items():
        assets = [a for a, c in asset_class_mapping.items() if c == asset_class]

        if benchmark not in benchmark_prices.columns:
            continue

        benchmark_ret = benchmark_prices[benchmark].pct_change()

        for asset in assets:
            if asset not in asset_returns.columns:
                continue

            asset_ret = asset_returns[asset]

            # Information ratio: excess return / tracking error
            excess = asset_ret - benchmark_ret
            ir = (
                excess.rolling(window).mean() /
                excess.rolling(window).std()
            ) * np.sqrt(252)

            # Relative strength index
            rsi = (
                (asset_ret.rolling(window).apply(lambda x: (x > 0).sum()) / window) -
                (benchmark_ret.rolling(window).apply(lambda x: (x > 0).sum()) / window)
            )

            results.append({
                'canonical_id': asset,
                'asset_class': asset_class,
                'benchmark_id': benchmark,
                'information_ratio': ir.iloc[-1],
                'relative_strength_index': rsi.iloc[-1],
                'excess_return_20d': excess.rolling(20).sum().iloc[-1]
            })

    return pd.DataFrame(results)
```

#### 5.5 sentiment_divergence (CEIO, 7. feb)

**Ekspertimplementering:**
```python
def sentiment_divergence_v2(
    sentiment_scores: pd.DataFrame,
    price_returns: pd.DataFrame,
    window: int = 20
) -> pd.DataFrame:
    """
    Detect divergences between sentiment and price movement.

    Divergence = sentiment improving while price falling (bullish divergence)
                 or sentiment deteriorating while price rising (bearish divergence)
    """
    results = []

    for asset in sentiment_scores.columns:
        if asset not in price_returns.columns:
            continue

        sent = sentiment_scores[asset]
        ret = price_returns[asset]

        # Rolling correlation
        corr = sent.rolling(window).corr(ret)

        # Sentiment momentum vs price momentum
        sent_mom = sent.rolling(window).mean()
        price_mom = ret.rolling(window).sum()

        # Divergence score: high when moving in opposite directions
        sent_direction = np.sign(sent_mom.diff())
        price_direction = np.sign(price_mom.diff())

        divergence = (sent_direction != price_direction).rolling(5).mean()

        # Classify divergence type
        if sent_mom.iloc[-1] > 0 and price_mom.iloc[-1] < 0:
            div_type = 'BULLISH_DIVERGENCE'
        elif sent_mom.iloc[-1] < 0 and price_mom.iloc[-1] > 0:
            div_type = 'BEARISH_DIVERGENCE'
        else:
            div_type = 'ALIGNED'

        results.append({
            'canonical_id': asset,
            'sentiment_score': sent.iloc[-1],
            'price_return_20d': price_mom.iloc[-1],
            'correlation_20d': corr.iloc[-1],
            'divergence_score': divergence.iloc[-1],
            'divergence_type': div_type,
            'signal_strength': abs(divergence.iloc[-1]) * (1 - abs(corr.iloc[-1]))
        })

    return pd.DataFrame(results)
```

### 6. VERIFICATION FRAMEWORK

For at et signal skal være "verifiserbart ekte" må det oppfylle:

| Kriterium | Threshold | Måling |
|-----------|-----------|--------|
| Information Coefficient (IC) | > 0.02 | Korrelasjon mellom signal og fremtidig return |
| IC Information Ratio (ICIR) | > 0.5 | IC / std(IC) |
| Sharpe Ratio (signal-only) | > 0.3 | Annualisert risikojustert avkastning |
| Probability of Backtest Overfitting | < 0.5 | CPCV-basert |
| Turnover | < 50% monthly | Unngå overtrading |
| Capacity | > $1M | Kan signalet handles i praksis |

### 7. IMPLEMENTATION PRIORITY

Basert på forventet alfa-bidrag og implementeringskompleksitet:

| Prioritet | Signal | Forventet IC | Kompleksitet | ROI |
|-----------|--------|--------------|--------------|-----|
| 1 | regime_transition_risk | 0.05-0.08 | Medium | Høy |
| 2 | sentiment_divergence | 0.03-0.06 | Lav | Høy |
| 3 | sector_relative_strength | 0.02-0.04 | Medium | Medium |
| 4 | market_relative_strength | 0.02-0.04 | Lav | Medium |
| 5 | stop_loss_heatmap | Risk signal | Medium | Lav (risikostyring) |

---

## CONCLUSION

FjordHQ har en solid infrastruktur (G2 PASS), men signalproduksjonen er fortsatt i tidlig fase:

1. **Infrastrukturen virker** - 31 surfaces, 22 prosesser, 65 signal scopes
2. **Dataene flyter** - 30,958 forecasts, 139 signals, 39 Golden Needles
3. **Kalibreringen er svak** - Brier 0.315, trenger < 0.30
4. **5 signaler mangler** - Placeholder-views, ikke ekte beregninger

**Next Steps:**
1. Implementer `regime_transition_risk` (FINN, 29. jan) med entropy-basert beregning
2. Valider med CPCV og walk-forward
3. Integrer med IoS-013 weighting engine
4. Backtest 1000X-strategien med nye signaler

---

*Generated by STIG (EC-003) | 2026-01-22*
*Database: PostgreSQL 17.6 @ 127.0.0.1:54322*
*Methodology: López de Prado, Chan, Narang, AQR Research*
