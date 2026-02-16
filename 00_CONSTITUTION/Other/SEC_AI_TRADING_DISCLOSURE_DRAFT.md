# SEC AI TRADING DISCLOSURE DRAFT
## FjordHQ Autonomous Trading System

**Version:** 1.0.0-DRAFT
**Date:** 2026-01-22
**Classification:** REGULATORY_PREPARATION
**Directive:** CEO-DIR-2026-120 P6.1
**Status:** DRAFT - Requires Legal Review

---

## 1. EXECUTIVE SUMMARY

This document provides disclosure of artificial intelligence and machine learning systems used in FjordHQ's autonomous trading operations, in accordance with anticipated SEC guidelines for AI-powered trading systems.

FjordHQ operates an AI-enhanced trading system that:
- Uses machine learning for market regime classification
- Employs automated signal generation and risk assessment
- Maintains human oversight through governance gates (G0-G4)
- Operates in paper trading mode during the learning phase

---

## 2. SYSTEM DESCRIPTION

### 2.1 AI/ML Components

| Component | Function | Model Type | Training Data |
|-----------|----------|------------|---------------|
| IoS-003 Regime Classifier | Market state classification | Hidden Markov Model | Historical market data (10+ years) |
| IoS-008 Signal Generator | Trading signal generation | Rule-based + ML ensemble | Price/volume/macro data |
| IoS-013 Signal Weighting | Signal confidence scoring | Factor-weighted scoring | Backtested performance |
| FINN Intelligence | Research synthesis | Large Language Model (Claude) | Public market research |
| CPTO Precision Engine | Order optimization | Algorithmic pricing | NBBO quotes, ATR |

### 2.2 System Architecture

```
[Market Data] → [CEIO Ingest] → [Regime Classification]
                                        ↓
[Macro Data] → [Factor Model] → [Signal Generation]
                                        ↓
                              [Signal Weighting (IoS-013)]
                                        ↓
                              [CPTO Precision Engine]
                                        ↓
                              [LINE Execution Agent]
                                        ↓
                              [Alpaca Paper Trading]
```

### 2.3 Decision-Making Process

1. **Data Ingestion**: Market and macro data collected from regulated exchanges and official sources (FRED, Alpaca, IEX)
2. **Regime Classification**: HMM model classifies current market state (6 regimes)
3. **Signal Generation**: IoS-008 generates directional signals with confidence scores
4. **Signal Weighting**: IoS-013 applies factor-based weights per current regime
5. **Order Optimization**: CPTO calculates precision entry/exit prices
6. **Execution**: LINE executes via broker API with mandatory TP/SL

---

## 3. TRAINING DATA SOURCES

### 3.1 Price Data Sources

| Source | Data Type | History | Regulatory Status |
|--------|-----------|---------|-------------------|
| Alpaca Markets | US Equities | 5+ years | FINRA/SEC registered |
| IEX Cloud | US Equities | 5+ years | SEC registered exchange |
| TwelveData | Global indices | 10+ years | Licensed data vendor |

### 3.2 Macro Data Sources

| Source | Data Type | History |
|--------|-----------|---------|
| FRED (Federal Reserve) | Economic indicators | 20+ years |
| Kenneth French Data Library | Factor returns | 30+ years |
| Yahoo Finance | Index prices | 10+ years |

### 3.3 Data Quality Assurance

- ISO 8000 quality framework applied to all data sources
- Four dimensions assessed: Completeness, Timeliness, Accuracy, Consistency
- Sources below 60% overall quality are blocked from signal generation

---

## 4. MODEL GOVERNANCE

### 4.1 Governance Gate Structure (ADR-004)

| Gate | Authority | Threshold | Purpose |
|------|-----------|-----------|---------|
| G0 | CEO | Any change | Strategic alignment |
| G1 | VEGA | Constitutional | Rule/ADR compliance |
| G2 | STIG | Technical | Implementation quality |
| G3 | LARS | Research | Methodology validation |
| G4 | LINE | Execution | Risk/compliance check |

### 4.2 Human Oversight Mechanisms

1. **CEO Directives**: All significant system changes require CEO directive
2. **VEGA Attestation**: Governance agent verifies constitutional compliance
3. **DEFCON System**: 5-level alert system that restricts trading automatically
4. **Circuit Breakers**: Automatic trading halt on excessive losses
5. **Daily Runbooks**: Human-reviewed operational reports

### 4.3 Model Change Control

- All model changes tracked in `fhq_monitoring.change_control_index`
- Parameter versions stored in `fhq_alpha.cpto_parameter_versions`
- Full audit trail via hash verification (ADR-011 Fortress)

---

## 5. RISK CONTROLS

### 5.1 Position Limits

| Control | Limit | Enforcement |
|---------|-------|-------------|
| Max position size | 10% of NAV | Unified Execution Gateway |
| Max daily loss | 3% of NAV | Circuit breaker |
| Max concentration | 25% per sector | Pre-trade check |

### 5.2 Execution Controls

- **Bracket Orders**: All positions require TP/SL (CEO-DIR-2026-119)
- **ATR-Based Stops**: 2.0x ATR stop loss, 1.25R take profit
- **Liquidity Checks**: Orders blocked if > 5% of order book depth

### 5.3 DEFCON Alert Levels

| Level | Condition | Trading Impact |
|-------|-----------|----------------|
| GREEN | Normal | Full operations |
| YELLOW | Elevated risk | Enhanced monitoring |
| ORANGE | High stress | Conservative mode, tighter stops |
| RED | Critical | No new positions |
| BLACK | Emergency | Full trading halt |

---

## 6. FMSB ALIGNMENT

This system aligns with Financial Markets Standards Board (FMSB) guidelines:

### 6.1 Algorithmic Trading Principles

- **Transparency**: Complete audit trail of all decisions
- **Accountability**: Clear ownership (EC-015 CPTO, EC-016 LINE)
- **Oversight**: Multi-level governance gates
- **Testing**: Paper trading validation before live deployment

### 6.2 Risk Management Standards

- Pre-trade risk checks mandatory
- Position limits enforced programmatically
- Kill switch capability (DEFCON BLACK)
- Independent risk monitoring

---

## 7. PERFORMANCE REPORTING

### 7.1 Return Calculation Methodology

- **Time-Weighted Returns (TWR)**: Used for performance reporting
- **Daily NAV Calculation**: Mark-to-market at market close
- **Benchmark Comparison**: S&P 500 Total Return Index

### 7.2 GIPS Preparation (Future)

- 3-year ex post standard deviation tracking initiated
- Composite construction rules documented
- Independent verification planned for Year 2

---

## 8. DISCLOSURE SUMMARY

FjordHQ's AI trading system:

1. **Uses AI/ML for**: Regime classification, signal generation, order optimization
2. **Does NOT use AI for**: Final execution decisions (rule-based), risk limit overrides
3. **Human oversight**: CEO directives, VEGA governance, daily reviews
4. **Risk controls**: Position limits, circuit breakers, bracket orders
5. **Current status**: Paper trading / Learning Phase
6. **Regulatory posture**: Proactive compliance, awaiting final SEC AI guidance

---

## 9. CONTACT INFORMATION

**System Owner**: FjordHQ
**Technical Lead**: EC-003 (STIG)
**Governance Lead**: VEGA
**Compliance Contact**: [TO BE DESIGNATED]

---

## REVISION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0-DRAFT | 2026-01-22 | EC-003 | Initial draft per CEO-DIR-2026-120 |

---

**DISCLAIMER**: This document is a draft prepared in anticipation of SEC guidance on AI trading systems. It should be reviewed by legal counsel before any external distribution or regulatory submission.
