# Hypothesis Canon v1: MBB-Grade Research Foundation

**Directive:** CEO-DIR-2026-VERBAL (Pre-Daemon Research)
**Author:** STIG (EC-003)
**Date:** 2026-01-23
**Classification:** STRATEGIC / RESEARCH-GRADE
**Purpose:** Foundational research for automatic hypothesis generation architecture

---

## Executive Summary

This document synthesizes research from leading systematic hedge funds (Bridgewater, AQR, Two Sigma), academic literature (2024-2026), and best practices in quantitative finance to establish the "Hypothesis Canon" - a rigorous framework for automated hypothesis generation in FjordHQ's learning system.

**Key Finding:** The gap between backtest performance and live trading is primarily a hypothesis quality problem. Over 90% of academic strategies fail when implemented because they violate fundamental principles of falsifiability, regime-dependence, and causal validity.

---

## 1. Methodologies from Leading Systematic Hedge Funds

### 1.1 Bridgewater Associates: Economic Intuition + Systematic Validation

Bridgewater's approach explicitly balances **economic intuition** (cause-effect understanding) with **systematic testing**:

> "The world can be understood. Markets and economies follow cause-and-effect relationships—and by understanding them, they believe they can beat the markets."
> — [Bridgewater Research & Insights](https://www.bridgewater.com/research-and-insights)

**Key Principles:**
1. **Start with fundamental cause-effect understanding** - not data mining
2. **Represent understanding in a "System"** - code and algorithms that generate views automatically
3. **Stress-test through time** - being systematic allows backtesting quality of ideas
4. **Reconcile human intuition with system outputs** - most impactful improvements come from investors watching markets and reconciling views

**ML Integration Caveat (2024):**
> "Large language models have the problem of hallucination. They don't know what greed is, what fear is, what the likely cause-and-effect relationships are."
> — Greg Jensen, Co-CIO, Bridgewater

**Implication for FjordHQ:** Hypotheses must be grounded in economic theory BEFORE statistical validation. The daemon should not "discover" hypotheses through data mining.

### 1.2 AQR Capital: Factor-Based + Behavioral Foundation

AQR's approach emphasizes that even "price-based" signals have fundamental justification:

> "A large part of momentum effects can be traced back to common investor underreaction to fundamental news."
> — [AQR Systematic vs Discretionary](https://www.aqr.com/-/media/AQR/Documents/Insights/Alternative-Thinking/AQR-Alternative-Thinking--3Q17.pdf)

**Key Principles:**
1. **Academic foundation** - Asness's dissertation focused on momentum and value
2. **Behavioral justification** - every factor has a behavioral or risk-based explanation
3. **Diversification across factors** - value, momentum, defensive, carry used together
4. **ML expansion with interpretability** - NLP and alternative data expand signals, but factor logic persists

**Performance Evidence (2024):**
- 59% of discretionary managers had negative alpha
- 71% of systematic managers earned positive alpha when controlling for Mag-7 exposure

**Implication for FjordHQ:** Each hypothesis must cite a behavioral or risk-based mechanism, not just statistical pattern.

### 1.3 Two Sigma: Scientific Method + Massive Simulation

Two Sigma's explicit use of the scientific method:

> "Quantitative Research teams use the scientific method to develop sophisticated and predictive investment models and refine their insights into how the markets will behave."
> — [Two Sigma Investment Management](https://www.twosigma.com/businesses/investment-management/)

**Key Principles:**
1. **Inspired ideas through scientific thinking** - curiosity and precision
2. **Systematically testing and expanding hypotheses** - shape company strategy
3. **100,000 simulations daily** - massive infrastructure for testing
4. **Alternative data integration** - ecommerce, energy, traffic patterns

**Implication for FjordHQ:** Hypothesis generation must be followed by rigorous simulation. The system must track hypothesis lifecycle from generation through falsification.

---

## 2. Automated Scientific Discovery Frameworks (2024-2026)

### 2.1 Agentic AI for Hypothesis Generation

Recent research establishes frameworks for AI-driven hypothesis generation:

> "Unlike traditional AI, Agentic AI systems are designed to operate with a high degree of autonomy, allowing them to independently perform tasks such as hypothesis generation, literature review, experimental design, and data analysis."
> — [Agentic AI for Scientific Discovery](https://arxiv.org/html/2503.08979v1)

**Key Framework Components:**

| Component | Function | FjordHQ Mapping |
|-----------|----------|-----------------|
| Reasoning Engine | Navigate hypothesis search space | FINN methodology |
| Causal Understanding | Move beyond correlational patterns | IoS-007 causal model |
| Memory System | Maintain causally-linked histories | hypothesis_ledger |
| Active Learning | Guide exploration to unexplored regions | epistemic_proposals |

### 2.2 Causal Inference Integration

Critical distinction between correlation and causation:

> "By defining and estimating unit-level causal effects, CAGE enables controllable generation based on counterfactual sampling, addressing the limitations of mere proximity in latent spaces."
> — [Towards Scientific Discovery with Generative AI](https://arxiv.org/html/2412.11427v1)

**Challenge Identified:**
> "The core difficulty is enabling long-term causal reasoning, as scientific insights can emerge from connecting experiments conducted months or even years apart."

**Implication for FjordHQ:** The system must maintain long-term causal chains. A hypothesis about "FOMC impact on equities" must connect to outcomes from multiple FOMC meetings over years.

### 2.3 Causal Machine Learning in Asset Pricing (2025)

Breakthrough research on distinguishing mechanisms from correlations:

> "Rao and Rojas (2025) move beyond predicting market downturns to investigate their causes. Using a flexible DML (Double Machine Learning) framework to estimate Average Partial Effects, they find that the volatility of options-implied risk appetite and market liquidity are key causal drivers of market troughs."
> — [Causal Machine Learning in Asset Pricing](https://www.researchgate.net/publication/398655455)

**Key Insight:**
> "During crises like the GFC and COVID-19 pandemic, non-causal feature selection methods consistently show higher prediction errors than causal methods."

**Implication for FjordHQ:** Hypotheses that rely on causal mechanisms will be more robust during regime shifts than those based on statistical correlations.

---

## 3. Requirements for a "Good Hypothesis"

### 3.1 Causality vs. Correlation in Time Series

**The Fundamental Problem:**
> "Feature attribution methods are commonly employed to provide insights into model decisions, but these attributions are often misconstrued as indicators of true causal influence—a leap that can be particularly perilous in finance where spurious correlations and confounding variables are prevalent."
> — [Causal Pitfalls of Feature Attributions](https://www.preprints.org/manuscript/202505.1046)

**Confounders in Finance:**
- Market-wide factors (broad sentiment)
- Macroeconomic announcements (interest rates, inflation)
- Geopolitical events
- Unobserved liquidity shocks

**Database Field Requirements:**

```sql
-- Causal justification fields
causal_mechanism TEXT NOT NULL,           -- Economic theory basis
confounders_identified TEXT[],            -- Known confounders
counterfactual_defined TEXT,              -- What would disprove this?
causal_direction TEXT CHECK (causal_direction IN ('X_CAUSES_Y', 'Y_CAUSES_X', 'BIDIRECTIONAL', 'CONFOUNDED'))
```

### 3.2 Regime-Dependence

**Research Finding:**
> "Performance exhibits strong regime dependence: positive returns during high-volatility periods (2020-2024: +2.4% annualized) versus negative returns during stable markets (2015-2019: -0.16% annualized)."
> — [Interpretable Hypothesis-Driven Trading](https://arxiv.org/html/2512.12924v1)

**Regime Classification Challenge:**
> "Traditional Hidden Markov Models (HMMs)—the high imbalance and persistence of regimes, low signal-to-noise ratio, and limited data availability often cause HMMs to generate state sequences that lack persistence and stability."

**Database Field Requirements:**

```sql
-- Regime dependence fields
regime_validity TEXT[] CHECK (regime_validity <@ ARRAY['RISK_ON', 'RISK_OFF', 'TRANSITION', 'CRISIS', 'EXPANSION', 'CONTRACTION']),
regime_conditional_confidence JSONB,      -- {"RISK_ON": 0.7, "RISK_OFF": 0.3}
regime_at_generation TEXT,                -- Regime when hypothesis was formed
regime_invalidation_threshold NUMERIC     -- Confidence below which regime invalidates
```

### 3.3 Falsifiability Criteria

**Popper's Framework Applied to Finance:**
> "In practice, this means designing your thesis to be falsifiable. Write down not just why 'Company XYZ will succeed,' but also what evidence would indicate it's failing."
> — [What Would Prove You Wrong?](https://www.polymathinvestor.com/p/what-would-prove-you-wrong-the-most)

**Concrete Falsifiability Example:**
> "I will consider this hypothesis invalid if quarterly revenue growth falls below 10% or if a major competitor captures more than 15% market share."

**Database Field Requirements:**

```sql
-- Falsifiability fields
falsification_criteria JSONB NOT NULL,    -- {"metric": "return", "threshold": -0.05, "window": "24h"}
falsification_count INT DEFAULT 0,        -- Times criteria triggered
confidence_decay_rate NUMERIC DEFAULT 0.1,-- Per falsification event
max_falsifications INT DEFAULT 3,         -- Before hypothesis death
hypothesis_status TEXT CHECK (hypothesis_status IN ('ACTIVE', 'WEAKENED', 'FALSIFIED', 'EXPIRED'))
```

---

## 4. Narrative-to-Signal Conversion

### 4.1 Central Bank Communication Processing

**State-of-the-Art (2024-2025):**
> "A text-based measure of monetary policy stance that models FOMC statements as convex combinations of dovish and hawkish alternatives, providing a tractable representation of the Committee's position along the policy spectrum."
> — [Deciphering Federal Reserve Communication](https://www.kansascityfed.org/documents/5642/rwp20-14dohsongyang.pdf)

**Key Methods:**
| Method | Application | Performance |
|--------|-------------|-------------|
| FinBERT | FOMC sentiment | Best for negative sentiment |
| GPT-4 | FOMC stance coding | Expert-level accuracy |
| SBERT | Statement-minutes alignment | Semantic comparison |
| LLM Summaries | Unconstrained abstraction | 2025 research |

**Geopolitical Risk Quantification:**
> "The BlackRock Geopolitical Risk Indicator (BGRI) tracks the relative frequency of brokerage reports and financial news stories associated with specific geopolitical risks, adjusting for whether the sentiment is positive or negative."
> — [BlackRock Geopolitical Risk Dashboard](https://www.blackrock.com/corporate/insights/blackrock-investment-institute/interactive-charts/geopolitical-risk-dashboard)

### 4.2 Narrative Lag

**Research Finding:**
Sentiment signals often precede price movements, but the lag varies by event type:

| Event Type | Typical Lag | Signal Decay |
|------------|-------------|--------------|
| FOMC Statement | Minutes to hours | 24-48h |
| Geopolitical | Hours to days | 1-2 weeks |
| Earnings | Immediate | 1-3 days |
| Macro Data Release | Immediate | 24h |

**Database Field Requirements:**

```sql
-- Narrative conversion fields
narrative_source TEXT,                    -- 'FOMC', 'GEOPOLITICAL', 'EARNINGS'
narrative_sentiment_score NUMERIC,        -- -1.0 to 1.0
narrative_confidence NUMERIC,             -- NLP model confidence
narrative_lag_hours NUMERIC,              -- Expected signal lag
narrative_decay_hours NUMERIC,            -- Signal validity window
narrative_extraction_method TEXT          -- 'FINBERT', 'GPT4', 'CUSTOM'
```

---

## 5. Pre-Validation Metrics (Before Backtesting)

### 5.1 The Multiple Testing Problem

**The Crisis:**
> "Harvey and Liu [2014] and Harvey et al. [2014] report hundreds of examples where multiple testing and selection bias have taken place in the factor investing literature... This leads these authors to conclude that 'most claimed research findings in financial economics are likely false.'"
> — [Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)

**The Reality:**
> "A strategy with a 3.0 Sharpe ratio in backtests is almost certainly fake. Real-world Sharpe ratios above 1.2 are rare, and above 1.5 are almost always overfitted."

### 5.2 Pre-Validation Checklist

Before any hypothesis enters backtesting:

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Economic rationale documented | Required | Prevents data mining |
| Regime validity specified | Required | Ensures robustness |
| Falsification criteria defined | Required | Scientific method |
| Sample size (historical events) | >= 30 | Statistical significance |
| Confounders identified | >= 1 | Causal validity |
| Expected Sharpe | <= 1.5 | Realism check |
| Prior hypotheses tested | <= 30 | Multiple testing control |

### 5.3 Correction Methods

**Deflated Sharpe Ratio (DSR):**
> "Bailey introduced the Deflated Sharpe Ratio to correct for selection bias under multiple testing and non-normal returns."

**Combinatorial Purged Cross-Validation (CPCV):**
> "CSCV cuts false positives from 68% down to 22%."

**Pre-Registration:**
> "Survey data from 2024 shows traders using formal controls like CSCV, SPA, or pre-registration had 23% higher consistency between backtest and live results."

**Database Field Requirements:**

```sql
-- Pre-validation fields
pre_validation_passed BOOLEAN DEFAULT FALSE,
economic_rationale_documented BOOLEAN,
sample_size_historical INT,
prior_hypotheses_count INT,              -- Track multiple testing
deflated_sharpe_estimate NUMERIC,
validation_method TEXT,                  -- 'CPCV', 'WALK_FORWARD', 'BOTH'
pre_registration_timestamp TIMESTAMPTZ   -- Lock before backtest
```

---

## 6. Hypothesis Canon v1: Database Schema

### 6.1 Proposed Table: hypothesis_canon

```sql
CREATE TABLE fhq_learning.hypothesis_canon (
    -- Identity
    canon_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_code TEXT UNIQUE NOT NULL,  -- 'HYP-2026-0001'

    -- Economic Foundation (Section 1)
    economic_rationale TEXT NOT NULL,
    causal_mechanism TEXT NOT NULL,
    behavioral_basis TEXT,                 -- AQR-style justification
    confounders_identified TEXT[],
    counterfactual_scenario TEXT NOT NULL,

    -- Event Binding (Section 2)
    event_type_codes TEXT[],              -- ['US_FOMC', 'BOJ_RATE']
    asset_universe TEXT[],                -- ['SPY', 'QQQ', 'TLT']

    -- Directional Hypothesis
    expected_direction TEXT NOT NULL CHECK (expected_direction IN ('BULLISH', 'BEARISH', 'NEUTRAL')),
    expected_magnitude TEXT CHECK (expected_magnitude IN ('HIGH', 'MEDIUM', 'LOW')),
    expected_timeframe_hours NUMERIC NOT NULL,

    -- Regime Dependence (Section 3.2)
    regime_validity TEXT[] DEFAULT ARRAY['RISK_ON', 'RISK_OFF'],
    regime_conditional_confidence JSONB,
    regime_at_generation TEXT,

    -- Falsifiability (Section 3.3)
    falsification_criteria JSONB NOT NULL,
    falsification_count INT DEFAULT 0,
    confidence_decay_rate NUMERIC DEFAULT 0.1,
    max_falsifications INT DEFAULT 3,

    -- Narrative Source (Section 4)
    narrative_source TEXT,
    narrative_extraction_method TEXT,
    narrative_lag_hours NUMERIC,
    narrative_decay_hours NUMERIC,

    -- Pre-Validation (Section 5)
    pre_validation_passed BOOLEAN DEFAULT FALSE,
    sample_size_historical INT,
    prior_hypotheses_count INT,
    deflated_sharpe_estimate NUMERIC,
    pre_registration_timestamp TIMESTAMPTZ,

    -- Confidence Management
    initial_confidence NUMERIC NOT NULL CHECK (initial_confidence BETWEEN 0 AND 1),
    current_confidence NUMERIC CHECK (current_confidence BETWEEN 0 AND 1),
    confidence_last_updated TIMESTAMPTZ,

    -- Lifecycle
    status TEXT DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'PRE_VALIDATED', 'ACTIVE', 'WEAKENED', 'FALSIFIED', 'EXPIRED')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT NOT NULL,
    expires_at TIMESTAMPTZ,

    -- Audit
    evidence_hash TEXT,
    version INT DEFAULT 1
);

-- Indexes
CREATE INDEX idx_hypothesis_canon_status ON fhq_learning.hypothesis_canon(status);
CREATE INDEX idx_hypothesis_canon_events ON fhq_learning.hypothesis_canon USING GIN(event_type_codes);
CREATE INDEX idx_hypothesis_canon_assets ON fhq_learning.hypothesis_canon USING GIN(asset_universe);
CREATE INDEX idx_hypothesis_canon_regime ON fhq_learning.hypothesis_canon USING GIN(regime_validity);
```

### 6.2 Logical Operators Required

```sql
-- Hypothesis evaluation functions

-- 1. Check if hypothesis is valid for current regime
CREATE OR REPLACE FUNCTION fhq_learning.hypothesis_valid_for_regime(
    p_hypothesis_id UUID,
    p_current_regime TEXT
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM fhq_learning.hypothesis_canon
        WHERE canon_id = p_hypothesis_id
        AND p_current_regime = ANY(regime_validity)
        AND status IN ('ACTIVE', 'WEAKENED')
    );
END;
$$ LANGUAGE plpgsql;

-- 2. Apply confidence decay after falsification event
CREATE OR REPLACE FUNCTION fhq_learning.apply_confidence_decay(
    p_hypothesis_id UUID
) RETURNS NUMERIC AS $$
DECLARE
    v_new_confidence NUMERIC;
    v_decay_rate NUMERIC;
    v_max_falsifications INT;
    v_current_falsifications INT;
BEGIN
    SELECT
        current_confidence * (1 - confidence_decay_rate),
        confidence_decay_rate,
        max_falsifications,
        falsification_count + 1
    INTO v_new_confidence, v_decay_rate, v_max_falsifications, v_current_falsifications
    FROM fhq_learning.hypothesis_canon
    WHERE canon_id = p_hypothesis_id;

    UPDATE fhq_learning.hypothesis_canon
    SET
        current_confidence = v_new_confidence,
        falsification_count = v_current_falsifications,
        confidence_last_updated = NOW(),
        status = CASE
            WHEN v_current_falsifications >= v_max_falsifications THEN 'FALSIFIED'
            WHEN v_new_confidence < 0.2 THEN 'WEAKENED'
            ELSE status
        END
    WHERE canon_id = p_hypothesis_id;

    RETURN v_new_confidence;
END;
$$ LANGUAGE plpgsql;

-- 3. Pre-validation gate
CREATE OR REPLACE FUNCTION fhq_learning.pre_validate_hypothesis(
    p_hypothesis_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    v_passes BOOLEAN := TRUE;
    v_record RECORD;
BEGIN
    SELECT * INTO v_record FROM fhq_learning.hypothesis_canon WHERE canon_id = p_hypothesis_id;

    -- Check all pre-validation criteria
    IF v_record.economic_rationale IS NULL THEN v_passes := FALSE; END IF;
    IF v_record.causal_mechanism IS NULL THEN v_passes := FALSE; END IF;
    IF v_record.counterfactual_scenario IS NULL THEN v_passes := FALSE; END IF;
    IF v_record.falsification_criteria IS NULL THEN v_passes := FALSE; END IF;
    IF v_record.sample_size_historical < 30 THEN v_passes := FALSE; END IF;
    IF v_record.deflated_sharpe_estimate > 1.5 THEN v_passes := FALSE; END IF;
    IF v_record.prior_hypotheses_count > 30 THEN v_passes := FALSE; END IF;

    IF v_passes THEN
        UPDATE fhq_learning.hypothesis_canon
        SET
            pre_validation_passed = TRUE,
            pre_registration_timestamp = NOW(),
            status = 'PRE_VALIDATED'
        WHERE canon_id = p_hypothesis_id;
    END IF;

    RETURN v_passes;
END;
$$ LANGUAGE plpgsql;
```

---

## 7. Recommended Architecture for FjordHQ

### 7.1 Hypothesis Generation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HYPOTHESIS GENERATION ARCHITECTURE                        │
└─────────────────────────────────────────────────────────────────────────────┘

Step 1: Event Detection (calendar_integrity_daemon)
         │
         ▼
Step 2: Economic Context Assembly
         ├── IoS-003: Current regime (RISK_ON/RISK_OFF)
         ├── IoS-006: Macro alignment score
         ├── IoS-007: Causal model state
         └── IoS-016: Event history for this type
         │
         ▼
Step 3: Hypothesis Formation (FINN responsibility)
         ├── MUST provide: economic_rationale
         ├── MUST provide: causal_mechanism
         ├── MUST provide: counterfactual_scenario
         ├── MUST provide: falsification_criteria
         └── MUST specify: regime_validity
         │
         ▼
Step 4: Pre-Validation Gate
         ├── Sample size >= 30
         ├── Prior hypotheses <= 30
         ├── Deflated Sharpe <= 1.5
         └── All required fields present
         │
         ▼
Step 5: Registration (immutable after event)
         └── pre_registration_timestamp = NOW()
         │
         ▼
Step 6: Event Occurs
         │
         ▼
Step 7: Outcome Recording (expectation_outcome_ledger)
         │
         ▼
Step 8: Verdict Assignment
         ├── VALIDATED: Confidence maintained/increased
         ├── WEAKENED: Confidence decayed
         └── FALSIFIED: Hypothesis retired
         │
         ▼
Step 9: Learning Feedback
         └── Update IoS-013 signal weights
```

### 7.2 CEO Decision Required

To implement this architecture:

| Decision | Options | Recommendation |
|----------|---------|----------------|
| Schema ownership | fhq_learning vs fhq_research | fhq_learning |
| Agent responsibility | FINN vs STIG | FINN (methodological) |
| Write mandate extension | fhq_learning.hypothesis_canon | Grant to FINN |
| Pre-validation authority | Automatic vs CEO approval | Automatic with audit |
| Falsification threshold | 3 strikes vs configurable | Configurable per hypothesis |

---

## 8. Sources

### Hedge Fund Research
- [Bridgewater Research & Insights](https://www.bridgewater.com/research-and-insights)
- [Inside Bridgewater's Pure Alpha](https://navnoorbawa.substack.com/p/inside-bridgewaters-pure-alpha-how)
- [AQR Systematic Equities](https://www.aqr.com/Learning-Center/Systematic-Equities)
- [Two Sigma Investment Management](https://www.twosigma.com/businesses/investment-management/)

### Academic Research (2024-2026)
- [Agentic AI for Scientific Discovery](https://arxiv.org/html/2503.08979v1)
- [Scientific Hypothesis Generation and Validation](https://arxiv.org/html/2505.04651v1)
- [Causal Machine Learning in Asset Pricing](https://www.researchgate.net/publication/398655455)
- [Causality-Inspired Models for Financial Time Series](https://arxiv.org/html/2408.09960v1)
- [Interpretable Hypothesis-Driven Trading](https://arxiv.org/html/2512.12924v1)

### Methodology
- [Backtest Overfitting - Bailey](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)
- [Dynamic Factor Allocation with Regime-Switching](https://arxiv.org/html/2410.14841v1)
- [Deciphering Federal Reserve Communication](https://www.kansascityfed.org/documents/5642/rwp20-14dohsongyang.pdf)

### Industry Reports
- [BlackRock Geopolitical Risk Dashboard](https://www.blackrock.com/corporate/insights/blackrock-investment-institute/interactive-charts/geopolitical-risk-dashboard)
- [How Hedge Funds Generated Alpha in 2024](https://navnoorbawa.substack.com/p/how-hedge-funds-generated-262-alpha)

---

## 9. Next Steps

1. **CEO Review:** Approve Hypothesis Canon v1 schema
2. **Migration:** Create `fhq_learning.hypothesis_canon` table
3. **Authority:** Grant FINN write_mandate for new table
4. **Daemon Design:** Architect `hypothesis_generation_daemon.py` based on Section 7.1
5. **Integration:** Connect to existing IoS-003, IoS-006, IoS-007, IoS-016

---

**Signed:** STIG (EC-003)
**Timestamp:** 2026-01-23T21:00:00.000Z
**Classification:** STRATEGIC / RESEARCH-GRADE
**Evidence Hash:** (to be computed on commit)
