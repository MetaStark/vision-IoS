# IoS-003C: Crypto Regime Engine

**Status:** P1_ACTIVATED
**Assigned To:** FINN (Financial Investments Neural Network)
**API Requirement:** DeepSeek Reasoning API
**Activated:** 2026-01-18
**Directive:** CEO-DIR-2026-076

---

## 1. Executive Summary

The Crypto Regime Engine (IoS-003C) is a dedicated research module to develop regime classification for cryptocurrency assets. This is explicitly **separate** from the equity regime engine (IoS-003) due to fundamental structural differences between asset classes.

**Core Principle:** Crypto follows different market microstructure dynamics than equities. Applying equity regime logic to crypto has been empirically proven to fail.

---

## 2. Why Equity Regimes Fail for Crypto

| Equity Regime Driver | Crypto Reality |
|---------------------|----------------|
| M2 Money Supply | Stablecoin Velocity is the driver |
| Real Rates (10Y TIPS) | DeFi yields and funding rates dominate |
| VIX as stress proxy | Perp funding rates + liquidation cascades |
| Sector rotation | Protocol/narrative rotation |
| Market hours | 24/7 continuous trading |
| Regulatory clarity | Regulatory uncertainty is structural |

**Empirical Evidence:**
- STRESS@99%+ on crypto has **inconsistent** inversion characteristics
- Vol-squeezes are misinterpreted as STRESS by equity HMMs
- Funding rate dynamics have no equity analog

---

## 3. Research Mandate

### 3.1 Candidate Regime Dimensions

FINN shall investigate the following as potential crypto regime indicators:

| Dimension | Data Source | Hypothesis |
|-----------|-------------|------------|
| **Net Stablecoin Liquidity** | On-chain (Glassnode, Dune) | Stablecoin inflows = risk-on, outflows = risk-off |
| **Global Liquidity Friction** | DXY + 10Y Real Rates | Macro squeeze compresses crypto first |
| **Microstructure Stress** | Perp Funding Rates + Liquidations | Extreme funding = mean reversion signal |
| **Exchange Flow Ratio** | Inflows vs Outflows to CEXs | Selling pressure indicator |
| **Volatility Clustering** | GARCH/realized vol patterns | Regime persistence detection |
| **Narrative Momentum** | Social sentiment (LunarCrush, Santiment) | Reflexivity in crypto markets |

### 3.2 Explicitly Disallowed

- Equity regime logic transfer
- Macro proxies designed for TradFi
- Confidence logic from equity calibration
- Any blending with IoS-003 outputs

### 3.3 Success Criteria

| Metric | Target | Rationale |
|--------|--------|-----------|
| Brier Score | < 0.25 | Must beat random by structural correctness |
| Hit Rate | > 55% | Directional edge required |
| Regime Persistence | > 3 days mean | Regimes must be tradeable |
| Sample Size | > 100 forecasts | Statistical validity |

---

## 4. Research Sources

FINN shall consult:

1. **Academic Literature**
   - "Cryptocurrency Market Microstructure" (Makarov & Schoar, 2020)
   - "Bitcoin Trading and Volatility" (Baur & Dimpfl, 2021)
   - "Stablecoin Runs" (Lyons & Viswanath-Natraj, 2023)

2. **On-Chain Analytics Providers**
   - Glassnode (chain metrics)
   - Dune Analytics (DeFi flows)
   - DefiLlama (TVL dynamics)

3. **Market Microstructure Data**
   - Coinglass (funding rates, liquidations)
   - Laevitas (options flow)
   - Kaiko (order book depth)

4. **Sentiment/Narrative**
   - LunarCrush (social metrics)
   - Santiment (developer activity)

---

## 5. Deliverables

### Phase 1: Literature Review (Week 1)
- [ ] Survey of crypto regime classification approaches
- [ ] Identify candidate indicator set
- [ ] API availability assessment

### Phase 2: Data Pipeline Design (Week 2)
- [ ] Define data sources and ingestion cadence
- [ ] Schema design for crypto regime indicators
- [ ] Integration with existing fhq_data infrastructure

### Phase 3: Model Development (Week 3-4)
- [ ] HMM/regime-switching model specific to crypto
- [ ] Backtesting framework
- [ ] Comparison with equity regime misapplication

### Phase 4: Validation (Week 5)
- [ ] Out-of-sample testing
- [ ] VEGA G3 audit submission
- [ ] CEO presentation

---

## 6. Governance

### 6.1 Isolation Requirements

```
CRYPTO REGIME ENGINE (IoS-003C)
├── Separate schema: vision_crypto (proposed)
├── Separate forecast table: crypto_regime_forecasts
├── Separate outcome table: crypto_regime_outcomes
├── NO cross-reference to equity tables
└── NO shared calibration parameters
```

### 6.2 Authority Boundaries

- FINN: Research and model development
- STIG: Data pipeline and infrastructure
- VEGA: Audit and governance review
- CEO: Approval for production activation

### 6.3 Crypto Forecast Status

**CURRENT: BLOCKED**

No crypto forecasts may be generated until IoS-003C passes G3 audit.

---

## 7. Timeline

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Research Kickoff | 2026-01-18 | ACTIVATED |
| Literature Review Complete | 2026-01-25 | PENDING |
| Data Pipeline Design | 2026-02-01 | PENDING |
| Model v1 Complete | 2026-02-15 | PENDING |
| G3 Audit Submission | 2026-02-22 | PENDING |
| CEO Decision Gate | 2026-02-28 | PENDING |

---

## 8. Risk Factors

1. **Data Availability**: On-chain data may require paid APIs
2. **Regime Non-Stationarity**: Crypto regimes may be more volatile than equity
3. **Sample Size**: Crypto history is shorter than equity
4. **Regulatory Events**: Unpredictable regime shifts from regulation

---

## 9. CEO Guidance

> "This is not caution. This is correctness. Crypto and equity are epistemically non-transferable domains. Build from first principles."
>
> — CEO-DIR-2026-076

---

## References

- CEO-DIR-2026-076: STRESS Inversion Validation + Crypto Regime Separation
- ADR-003: Institutional Standards (MDLC)
- IoS-003: Regime Classification Engine (EQUITY)
