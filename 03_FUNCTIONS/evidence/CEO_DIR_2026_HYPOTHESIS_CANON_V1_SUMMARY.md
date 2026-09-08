# Hypothesis Canon v1 - CEO Summary

**Date:** 2026-01-23
**Author:** STIG (EC-003)
**Full Research:** `CEO_DIR_2026_HYPOTHESIS_CANON_V1_RESEARCH.md`

---

## 1. Nøkkelfunn fra MBB-Grade Research

### 1.1 Ledende Hedge Funds - Konsensus

| Firma | Tilnærming | FjordHQ Implikasjon |
|-------|-----------|---------------------|
| **Bridgewater** | Økonomisk intuisjon FØR data mining | Hypoteser må ha kausal teori først |
| **AQR** | Atferdsbasert begrunnelse for alle faktorer | Hver hypotese trenger behavioral basis |
| **Two Sigma** | Vitenskapelig metode, 100k simuleringer/dag | Track full hypothesis lifecycle |

**Bridgewater-sitat:**
> "Large language models have the problem of hallucination. They don't know what greed is, what fear is, what the likely cause-and-effect relationships are."

**Implikasjon:** Daemon skal IKKE "oppdage" hypoteser via data mining. Den skal formalisere økonomisk teori.

---

## 2. Kritiske Krav til "God Hypotese"

### 2.1 Obligatoriske Felter (Pre-Validation Gate)

| Felt | Krav | Begrunnelse |
|------|------|-------------|
| `economic_rationale` | REQUIRED | Forhindrer data mining |
| `causal_mechanism` | REQUIRED | Skiller kausalitet fra korrelasjon |
| `counterfactual_scenario` | REQUIRED | Definerer hva som ville motbevist |
| `falsification_criteria` | REQUIRED | Popperian vitenskapelig metode |
| `regime_validity` | REQUIRED | Regime-avhengighet |
| `sample_size` | >= 30 | Statistisk signifikans |
| `deflated_sharpe` | <= 1.5 | Realisme-sjekk |

### 2.2 Regime-Avhengighet (Kritisk Funn)

**Forskning viser:**
> "Performance exhibits strong regime dependence: +2.4% annualized during high-volatility (2020-2024) versus -0.16% during stable markets (2015-2019)"

**Implikasjon:** Hver hypotese MÅ spesifisere hvilke regimer den er gyldig i:
- RISK_ON
- RISK_OFF
- TRANSITION
- CRISIS
- EXPANSION
- CONTRACTION

### 2.3 Falsifiserbarhet (Popper)

**Formel:**
```
confidence_new = confidence_old × (1 - decay_rate)

Eksempel med decay_rate = 0.1:
- Start: 0.70
- Etter 1 feil: 0.63
- Etter 2 feil: 0.57
- Etter 3 feil: FALSIFIED (hypotese død)
```

### 2.4 Multiple Testing Problem

**Harvey et al. (2014) konklusjon:**
> "Most claimed research findings in financial economics are likely false"

**Årsak:** Forskere tester hundrevis av hypoteser og rapporterer kun de som "virker".

**Løsning for FjordHQ:**
1. Pre-registration (lås hypotese FØR backtest)
2. Deflated Sharpe Ratio (korrigerer for antall tester)
3. Max 30 hypoteser før kontroll

---

## 3. Foreslått Database Schema

### 3.1 Ny Tabell: `fhq_learning.hypothesis_canon`

```sql
CREATE TABLE fhq_learning.hypothesis_canon (
    -- Identitet
    canon_id UUID PRIMARY KEY,
    hypothesis_code TEXT UNIQUE NOT NULL,     -- 'HYP-2026-0001'

    -- Økonomisk Fundament
    economic_rationale TEXT NOT NULL,         -- Hvorfor tror vi dette?
    causal_mechanism TEXT NOT NULL,           -- Hva er kausalmekanismen?
    behavioral_basis TEXT,                    -- Atferdsmessig forklaring
    counterfactual_scenario TEXT NOT NULL,    -- Hva ville motbevist dette?

    -- Event-binding
    event_type_codes TEXT[],                  -- ['US_FOMC', 'BOJ_RATE']
    asset_universe TEXT[],                    -- ['SPY', 'QQQ', 'TLT']

    -- Retning
    expected_direction TEXT NOT NULL,         -- BULLISH/BEARISH/NEUTRAL
    expected_magnitude TEXT,                  -- HIGH/MEDIUM/LOW
    expected_timeframe_hours NUMERIC NOT NULL,

    -- Regime-avhengighet
    regime_validity TEXT[],                   -- ['RISK_ON', 'RISK_OFF']
    regime_conditional_confidence JSONB,      -- {"RISK_ON": 0.7, "RISK_OFF": 0.3}

    -- Falsifiserbarhet
    falsification_criteria JSONB NOT NULL,    -- Når er hypotesen feil?
    falsification_count INT DEFAULT 0,
    confidence_decay_rate NUMERIC DEFAULT 0.1,
    max_falsifications INT DEFAULT 3,

    -- Pre-validering
    pre_validation_passed BOOLEAN DEFAULT FALSE,
    sample_size_historical INT,
    prior_hypotheses_count INT,
    deflated_sharpe_estimate NUMERIC,
    pre_registration_timestamp TIMESTAMPTZ,

    -- Confidence
    initial_confidence NUMERIC NOT NULL,
    current_confidence NUMERIC,

    -- Status
    status TEXT DEFAULT 'DRAFT',              -- DRAFT/PRE_VALIDATED/ACTIVE/WEAKENED/FALSIFIED
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT NOT NULL
);
```

---

## 4. CEO Beslutninger Required

### 4.1 Schema Eierskap

| Alternativ | Fordel | Ulempe |
|------------|--------|--------|
| `fhq_learning` (Anbefalt) | Konsistent med hypothesis_ledger | - |
| `fhq_research` | FINN har allerede tilgang | Blander læring og forskning |

**Anbefaling:** `fhq_learning`

### 4.2 Agent Ansvar

| Alternativ | Begrunnelse | Kontrakt-basis |
|------------|-------------|----------------|
| **FINN (Anbefalt)** | Metodologisk eierskap | EC-004 Section 3 |
| STIG | Bredere infrastruktur-tilgang | EC-003 Section 3 |

**Anbefaling:** FINN - hypoteser er metodologiske artefakter

### 4.3 Write Mandate

FINN trenger ny write_mandate:

```sql
INSERT INTO fhq_governance.write_mandate_registry
(agent_role, expected_action, authorized_write_targets, schema_scope, is_active, directive_reference)
VALUES
('FINN', 'HYPOTHESIS_GENERATION',
 ARRAY['fhq_learning.hypothesis_canon'],
 ARRAY['fhq_learning'],
 true,
 'CEO-DIR-2026-HYPOTHESIS-CANON-V1');
```

### 4.4 Pre-Validation Authority

| Alternativ | Beskrivelse |
|------------|-------------|
| Automatisk (Anbefalt) | Gate-funksjon sjekker alle krav automatisk |
| CEO Approval | Hver hypotese krever manuell godkjenning |

**Anbefaling:** Automatisk med full audit trail

---

## 5. Hypothesis Generation Flow

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Event Detection                                     │
│  calendar_integrity_daemon oppdager upcoming event           │
│  Eksempel: BOJ_RATE om 4 timer                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Context Assembly                                    │
│  ├── IoS-003: Regime = RISK_ON                               │
│  ├── IoS-006: Macro alignment = 0.5                          │
│  ├── IoS-007: Causal model state                             │
│  └── IoS-016: Historiske BOJ_RATE outcomes                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Hypothesis Formation (FINN)                         │
│                                                              │
│  economic_rationale: "BOJ rate hikes strengthen JPY,         │
│    reducing USD/JPY carry trade attractiveness"              │
│                                                              │
│  causal_mechanism: "Higher JPY rates → reduced carry         │
│    trade → JPY appreciation → risk-off spillover"            │
│                                                              │
│  expected_direction: BEARISH (for US equities)               │
│  expected_timeframe: 24 hours                                │
│                                                              │
│  falsification_criteria: {                                   │
│    "metric": "SPY_return_24h",                               │
│    "condition": "SPY > +1% post-BOJ-hike"                    │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: Pre-Validation Gate                                 │
│  ├── economic_rationale: ✓                                   │
│  ├── causal_mechanism: ✓                                     │
│  ├── falsification_criteria: ✓                               │
│  ├── sample_size (30 historical BOJ events): ✓               │
│  └── deflated_sharpe <= 1.5: ✓                               │
│                                                              │
│  RESULT: PRE_VALIDATED                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 5: Pre-Registration (IMMUTABLE)                        │
│  pre_registration_timestamp = NOW()                          │
│  Ingen endringer tillatt etter event_timestamp               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 6: Event Occurs                                        │
│  BOJ annonserer rate decision                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 7: Outcome Recording (T+24h)                           │
│  actual_direction: BEARISH                                   │
│  SPY_return_24h: -0.8%                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 8: Verdict                                             │
│  ├── VALIDATED: Hypotese korrekt → confidence maintained     │
│  ├── WEAKENED: Delvis korrekt → confidence decayed           │
│  └── FALSIFIED: Hypotese feil → hypothesis retired           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 9: Learning Feedback                                   │
│  Oppdater IoS-013 signal weights basert på verdict           │
│  Oppdater LVI score                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Neste Steg

| Steg | Handling | Ansvarlig |
|------|----------|-----------|
| 1 | CEO godkjenner Hypothesis Canon v1 schema | CEO |
| 2 | Kjør migration for `hypothesis_canon` tabell | STIG |
| 3 | Grant FINN write_mandate | STIG (CEO approval) |
| 4 | Design `hypothesis_generation_daemon.py` | STIG + FINN |
| 5 | Integrer med IoS-003, IoS-006, IoS-007, IoS-016 | STIG |
| 6 | Test med BOJ_RATE event (om 7 timer) | FINN |

---

## 7. Kilder (Full liste i research-dokumentet)

- Bridgewater Research & Insights
- AQR Systematic Equities
- Two Sigma Investment Management
- Agentic AI for Scientific Discovery (2025)
- Causal Machine Learning in Asset Pricing (2025)
- Harvey et al. - Multiple Testing in Finance (2014)
- Bailey - Probability of Backtest Overfitting

---

**Signed:** STIG (EC-003)
**Timestamp:** 2026-01-23T21:15:00.000Z

**Full research document:** `03_FUNCTIONS/evidence/CEO_DIR_2026_HYPOTHESIS_CANON_V1_RESEARCH.md`
