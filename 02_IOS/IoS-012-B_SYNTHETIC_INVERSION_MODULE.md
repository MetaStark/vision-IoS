# IoS-012-B - SYNTHETIC INVERSION MODULE

**Canonical Version:** 2026.G0.1
**Status:** G0_EXTENDED (Shadow Mode Only)
**Amendment:** CEO-DIR-20260122-BRS-ASSET-META (BULL CRYPTO Extension)
**Owner:** STIG (CTO)
**Validator:** VEGA (Governance)
**Dependencies:** IoS-012 (Execution Engine), IoS-008 (Runtime Decision Engine)
**ADR Alignment:** ADR-004, ADR-012, ADR-013, ADR-016
**CEO Directive:** CEO-DIR-2026-078 (G4 Canonicalized), CEO-DIR-2026-105 (Hindsight Firewall)

---

## 1. Executive Summary

IoS-012-B is the **Synthetic Inversion Module** - a specialized sub-component of IoS-012 that converts systematic miscalibration into alpha through signal inversion.

**Core Discovery (CEO-DIR-2026-105):**
> STRESS@99%+ equity signals have 0% hit rate across 37 signals. When inverted, this becomes a high-value alpha signal with Brier score 0.0058.

**Extended Discovery (CEO-DIR-20260122-BRS-ASSET-META):**
> BULL@99%+ CRYPTO signals have 12.23% hit rate across 327 signals (87.77% failure rate). When inverted, this yields Brier improvement of 0.7524 - the highest-leverage inversion after STRESS.

**Mission:**
Transform documented calibration failures into profitable trading strategies by inverting directional implications when the system exhibits systematic overconfidence:
1. **STRESS regime** (any confidence, equity) - 100% failure rate
2. **BULL regime** (99%+ confidence, crypto) - 87.77% failure rate

---

## 2. The Alpha Inversion Logic

### 2.1 STRESS Inversion Trigger (G4 Canonicalized)

```
IF regime = 'STRESS'
   AND confidence >= 0.99
   AND asset_class = 'EQUITY'
   AND ticker IN (stress_inversion_universe)
THEN
   invert_directional_implication()
```

### 2.2 BULL CRYPTO Inversion Trigger (G0 EXTENDED - 2026-01-22)

```
IF regime = 'BULL'
   AND confidence >= 0.99
   AND asset_class = 'CRYPTO'
   AND ticker IN (bull_crypto_inversion_universe)
THEN
   invert_directional_implication()
```

**Statistical Basis (Database-Verified 2026-01-22):**
- Sample Size: 327 signals
- Hit Rate: 12.23% (40/327 correct)
- Failure Rate: 87.77% (287/327 wrong)
- Original Brier: 0.8742
- Inverted Brier: 0.1218
- Improvement: 0.7524 (86.1% reduction)

### 2.3 STRESS Inversion Universe (10 Equity Tickers)

| Ticker | Sector | Evidence Base | Status |
|--------|--------|---------------|--------|
| ADBE | Technology | 3+ signals @ 99%+ | G4_CANONICALIZED |
| ADSK | Technology | 3+ signals @ 99%+ | G4_CANONICALIZED |
| AIG | Financials | 3+ signals @ 99%+ | G4_CANONICALIZED |
| AZO | Consumer | 3+ signals @ 99%+ | G4_CANONICALIZED |
| GIS | Consumer | 3+ signals @ 99%+ | G4_CANONICALIZED |
| HNR1.DE | Industrial | 3+ signals @ 99%+ | G4_CANONICALIZED |
| INTU | Technology | 3+ signals @ 99%+ | G4_CANONICALIZED |
| LEN | Real Estate | 3+ signals @ 99%+ | G4_CANONICALIZED |
| NOW | Technology | 3+ signals @ 99%+ | G4_CANONICALIZED |
| PGR | Financials | 3+ signals @ 99%+ | G4_CANONICALIZED |

### 2.4 BULL CRYPTO Inversion Universe (14 Tickers) - G0 EXTENDED

| Ticker | Failures | Avg Confidence | Avg Brier | Status |
|--------|----------|----------------|-----------|--------|
| SHIB-USD | 214 | 99.84% | 0.9969 | G0_CANDIDATE_PRIORITY |
| XRP-USD | 32 | 99.84% | 0.9968 | G0_CANDIDATE |
| ATOM-USD | 9 | 99.90% | 0.9980 | G0_CANDIDATE |
| DOT-USD | 8 | 99.44% | 0.9888 | G0_CANDIDATE |
| XTZ-USD | 6 | 99.79% | 0.9959 | G0_CANDIDATE |
| AVAX-USD | 3 | 99.85% | 0.9970 | G0_CANDIDATE |
| LINK-USD | 3 | 99.76% | 0.9952 | G0_CANDIDATE |
| SOL-USD | 3 | 99.82% | 0.9964 | G0_CANDIDATE |
| UNI-USD | 3 | 99.71% | 0.9942 | G0_CANDIDATE |
| AAVE-USD | 2 | 99.80% | 0.9960 | G0_CANDIDATE |
| ALGO-USD | 2 | 99.75% | 0.9950 | G0_CANDIDATE |
| DOGE-USD | 2 | 99.88% | 0.9976 | G0_CANDIDATE |
| LTC-USD | 2 | 99.79% | 0.9958 | G0_CANDIDATE |
| MATIC-USD | 2 | 99.82% | 0.9964 | G0_CANDIDATE |

**Critical Note:** SHIB-USD alone accounts for 214/287 (74.6%) of all BULL@99%+ CRYPTO failures.

### 2.5 Excluded Assets

| Ticker | Reason | Reference |
|--------|--------|-----------|
| FLOW-USD | VEGA G3 asset class boundary | Day 18 Report Section 14 |
| BTC-USD | Insufficient failure evidence | Meta-analysis 2026-01-22 |
| ETH-USD | Insufficient failure evidence | Meta-analysis 2026-01-22 |

---

## 3. Instrument Selection

### 3.1 STRESS Inversion: Vertical Bull Call Spreads (Equity)

When system predicts STRESS with extreme confidence but is systematically wrong, the inverted implication suggests **bullish** outcome. Vertical Bull Call Spreads provide:

1. **Defined Risk** - Maximum loss = net premium paid
2. **Leverage** - Synthetic exposure without direct equity position
3. **Options Liquidity** - Available on all 10 canonical tickers via Alpaca
4. **Governance Alignment** - Meets ADR-012 economic safety constraints

### 3.2 Structure

```
BUY:  1x Call @ Strike K1 (ATM or slightly OTM)
SELL: 1x Call @ Strike K2 (K2 > K1, further OTM)

Max Profit = (K2 - K1) - Net Premium
Max Loss   = Net Premium Paid
Breakeven  = K1 + Net Premium
```

### 3.3 Strike Selection Rules

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Long Strike (K1) | ATM or 1-2% OTM | Capture directional move |
| Short Strike (K2) | K1 + $5-10 | Defined profit cap |
| Expiration | 14-30 DTE | Theta balance |
| Delta Target | 0.40-0.50 long leg | Moderate directional exposure |

### 3.4 BULL CRYPTO Inversion: Short Spot / Perpetual Futures

When system predicts BULL with 99%+ confidence for CRYPTO but is systematically wrong (87.77% failure rate), the inverted implication suggests **bearish** outcome.

**Instrument Options (Shadow Mode):**

| Instrument | Venue | Rationale |
|------------|-------|-----------|
| Short Spot | Alpaca Crypto | Direct inverse exposure |
| Short Perpetual | Regulated CEX (future) | Leverage with funding |

**Note:** CRYPTO options are NOT available on Alpaca. Shadow mode will simulate short spot positions.

### 3.5 BULL CRYPTO Strike/Size Rules

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Position Size | 1% NAV max | Higher volatility adjustment |
| Stop Loss | 5% adverse move | Tight risk control |
| Take Profit | 3% favorable move | Asymmetric R:R |
| Max Holding | 48 hours | Momentum decay |

---

## 4. Position Sizing & Risk Management

### 4.1 Position Sizing

**STRESS Equity Inversion:**

| Parameter | Value | Constraint |
|-----------|-------|------------|
| Max Position per Ticker | 2.5% NAV | ADR-012 concentration limit |
| Max Total STRESS Exposure | 25% NAV | 10 tickers × 2.5% |
| Premium Budget per Trade | 0.5% NAV | Cost control |

**BULL CRYPTO Inversion:**

| Parameter | Value | Constraint |
|-----------|-------|------------|
| Max Position per Ticker | 1.0% NAV | Volatility-adjusted |
| Max Total CRYPTO Exposure | 14% NAV | 14 tickers × 1.0% |
| Stop Loss per Trade | 5% of position | Tight risk control |

**Combined Limits:**

| Parameter | Value |
|-----------|-------|
| Max Total Inversion Exposure | 39% NAV |
| Max Concurrent Positions | 24 (10 equity + 14 crypto) |

### 4.2 Exit Rules

| Exit Type | Trigger | Action |
|-----------|---------|--------|
| Take Profit | 50% of max profit reached | Close position |
| Stop Loss | 25% of premium remaining | Close position |
| Time Decay | 5 DTE remaining | Close position |
| Regime Change | STRESS regime exits | Evaluate close |

### 4.3 Risk Control Circuit Breaker

```python
def inversion_health_check():
    """Auto-disable if Inverted Hit Rate < 80%"""
    recent_signals = get_inverted_signals(lookback_days=30)
    inverted_hit_rate = calculate_hit_rate(recent_signals)

    if inverted_hit_rate < 0.80:
        disable_ios012b()
        alert_lars("INVERSION_DEGRADATION", inverted_hit_rate)
        return False
    return True
```

---

## 5. Hindsight Firewall Compliance

### 5.1 Non-Eligibility Period

| Constraint | Value | Reference |
|------------|-------|-----------|
| is_retrospective | TRUE | CEO-DIR-2026-105 |
| non_eligibility_until | 2026-02-02 | 2 learning cycles |
| current_mode | SHADOW_ONLY | No live execution |

### 5.2 Permitted Actions (Pre-2026-02-02)

- Shadow signal generation
- Paper trading simulation
- Performance tracking
- Evidence collection for G4 review

### 5.3 Prohibited Actions (Until 2026-02-02)

- Live execution on Alpaca
- SkillDamper parameter modification
- Model retraining based on inversion data
- Autonomous trading activation

---

## 6. Implementation Architecture

### 6.1 Data Flow

```
IoS-008 (Runtime Decision Engine)
    ↓
    Signal: {ticker, direction, confidence, regime, asset_class}
    ↓
IoS-012-B (Synthetic Inversion Module)
    ↓
    ┌─────────────────────────────────────────────────────────┐
    │ INVERSION CHECK (Dual-End Strategy)                      │
    │                                                          │
    │ Path A: STRESS Inversion (Equity)                        │
    │   IF regime == STRESS                                    │
    │      AND confidence >= 0.99                              │
    │      AND asset_class == EQUITY                           │
    │      AND ticker IN stress_universe                       │
    │   THEN invert_direction(), generate_bull_spread()        │
    │                                                          │
    │ Path B: BULL CRYPTO Inversion (Crypto)                   │
    │   IF regime == BULL                                      │
    │      AND confidence >= 0.99                              │
    │      AND asset_class == CRYPTO                           │
    │      AND ticker IN bull_crypto_universe                  │
    │   THEN invert_direction(), generate_short_spot()         │
    └─────────────────────────────────────────────────────────┘
    ↓
    IF SHADOW_MODE: log_to_shadow_tracking()
    ↓
    IF LIVE_MODE (post-firewall): submit_to_alpaca()
    ↓
IoS-012 (Execution Engine)
    ↓
    Lineage Hash, Audit Trail, Compliance Metrics
```

### 6.2 Database Objects

```sql
-- Shadow tracking table
fhq_provisional.inversion_overlay_shadow

-- Shadow performance view
fhq_provisional.v_inversion_overlay_performance

-- Health monitoring
fhq_governance.inversion_health_metrics
```

### 6.3 Python Module

```
03_FUNCTIONS/ios012b_synthetic_inversion_module.py
```

---

## 7. Evidence Base

### 7.1 STRESS Inversion Statistics (G4 Canonicalized)

| Metric | Value | Source |
|--------|-------|--------|
| N (signals) | 37 | CEO-DIR-2026-105 |
| Original Hit Rate | 0.00% | Brier Ledger |
| Original Brier | 0.9942 | Brier Ledger |
| Inverted Brier | 0.0058 | Calculated |
| Inverted Hit Rate | 100% (theoretical) | Inverse |

### 7.2 BULL CRYPTO Inversion Statistics (G0 Extended - 2026-01-22)

| Metric | Value | Source |
|--------|-------|--------|
| N (signals) | 327 | Brier Ledger (Database Query) |
| Original Hit Rate | 12.23% | 40/327 correct |
| Original Brier | 0.8742 | Brier Ledger |
| Inverted Brier | 0.1218 | Calculated |
| Inverted Hit Rate | 87.77% (theoretical) | Inverse |
| Brier Improvement | 0.7524 | 86.1% reduction |

**Worst Offender Detail:**
| Ticker | Failures | % of Total |
|--------|----------|------------|
| SHIB-USD | 214 | 74.6% |
| XRP-USD | 32 | 11.1% |
| Other 12 | 41 | 14.3% |

### 7.3 Combined System Impact

| Strategy | Current Brier | With Strategy | Improvement |
|----------|---------------|---------------|-------------|
| Baseline | 0.5662 | - | - |
| +STRESS Only | 0.5662 | 0.5454 | 3.69% |
| +STRESS+BULL_CRYPTO | 0.5662 | 0.4944 | **12.68%** |

### 7.4 Evidence Artifacts

| Artifact | Location | Status |
|----------|----------|--------|
| STRESS Regime-Conditional | `evidence/CEO_DIR_2026_105_REGIME_CONDITIONAL_MISCALIBRATION.json` | G4_COMPLETE |
| STRESS Retrospective | `evidence/CEO_DIR_2026_105_RETROSPECTIVE_CALIBRATION.json` | G4_COMPLETE |
| **BULL CRYPTO Meta-Analysis** | `evidence/BRIER_DUAL_END_INVERSION_META_ANALYSIS_20260122.json` | **G0_NEW** |
| **Governance Summary** | `05_GOVERNANCE/BRIER_DUAL_END_INVERSION_ANALYSIS_20260122.md` | **G0_NEW** |

---

## 8. Governance Gates

### 8.1 Current Status: G0 EXTENDED

| Component | Gate | Status | Requirement |
|-----------|------|--------|-------------|
| **STRESS Equity** | G0 | COMPLETE | IoS-012-B v1.0 |
| **STRESS Equity** | G1 | PENDING | Technical validation by STIG |
| **STRESS Equity** | G2 | PENDING | Governance validation by VEGA |
| **STRESS Equity** | G3 | SHADOW | Integration testing active |
| **STRESS Equity** | G4 | BLOCKED | Requires CEO + 2026-02-02 |
| **BULL CRYPTO** | G0 | **EXTENDED** | CEO-DIR-20260122-BRS-ASSET-META |
| **BULL CRYPTO** | G1 | PENDING | Statistical validation (this document) |
| **BULL CRYPTO** | G2 | PENDING | VEGA governance review |
| **BULL CRYPTO** | G3 | NOT_STARTED | Shadow testing required |
| **BULL CRYPTO** | G4 | BLOCKED | Requires separate approval cycle |

### 8.2 G4 Activation Criteria

1. Shadow testing complete with 14+ days data
2. Inverted Hit Rate >= 80% in shadow mode
3. No Hindsight Firewall violations
4. VEGA attestation of non-contamination
5. CEO signature

---

## 9. Risk Assessment

### 9.1 Identified Risks - STRESS Inversion

| Risk | Severity | Mitigation |
|------|----------|------------|
| Regime model drift | HIGH | Auto-disable at 80% threshold |
| Overfitting to historical pattern | HIGH | Hindsight Firewall, 2 learning cycles |
| Options liquidity | MEDIUM | Limit to canonical universe |
| Model contamination | CRITICAL | VEGA evidence guardian |

### 9.2 Identified Risks - BULL CRYPTO Inversion

| Risk | Severity | Mitigation |
|------|----------|------------|
| SHIB-USD concentration | HIGH | 214/287 failures from single asset |
| Crypto volatility spike | HIGH | 1% NAV limit, 5% stop loss |
| 12.23% correct predictions | MEDIUM | Accept 1-in-8 loss scenario |
| Regime model drift | HIGH | Auto-disable at 75% threshold |
| Short squeeze risk | MEDIUM | 48-hour max holding period |

### 9.3 Failure Modes

| Mode | Detection | Response |
|------|-----------|----------|
| STRESS Inverted Hit Rate < 80% | Health check | Auto-disable STRESS |
| BULL CRYPTO Inverted Hit Rate < 75% | Health check | Auto-disable CRYPTO |
| Regime undefined | Regime validator | Block signal |
| Ticker not in universe | Universe filter | Reject signal |
| Hindsight contamination | VEGA audit | System halt |
| Single-asset concentration > 50% | Concentration check | Alert LARS |

---

## 10. Acceptance Criteria

### 10.1 Shadow Mode Acceptance (G3)

- [ ] Shadow tracking table operational
- [ ] Paper trading on Alpaca Paper Account
- [ ] Performance metrics computed daily
- [ ] No contamination of ex-ante beliefs

### 10.2 Live Mode Acceptance (G4)

- [ ] 14+ days of shadow data
- [ ] Inverted Hit Rate >= 80%
- [ ] VEGA attestation signed
- [ ] CEO approval received
- [ ] Date >= 2026-02-02

---

## 11. Prepared By

**STIG** - System for Technical Implementation & Governance
**Agent ID:** EC-003_2026_PRODUCTION

**Original Document:**
- Date: 2026-01-19
- Directive: CEO-DIR-2026-105 (Phase 2)

**G0.1 Amendment (BULL CRYPTO Extension):**
- Date: 2026-01-22
- Directive: CEO-DIR-20260122-BRS-ASSET-META
- Evidence: `evidence/BRIER_DUAL_END_INVERSION_META_ANALYSIS_20260122.json`

---

## 12. Approval Chain

| Role | Agent | Status | Signature |
|------|-------|--------|-----------|
| Technical | STIG | SUBMITTED | pending |
| Governance | VEGA | PENDING | - |
| Strategy | LARS | PENDING | - |
| Authority | CEO | PENDING | - |
