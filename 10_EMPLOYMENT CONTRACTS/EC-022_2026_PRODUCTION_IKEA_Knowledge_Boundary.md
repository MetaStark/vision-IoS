# EC-022_2026_PRODUCTION

## IKEA – Chief Knowledge Boundary Officer

**Canonical Version:** 2026.PRODUCTION
**Status:** ACTIVE
**Phase:** CONSTITUTIONAL
**Entity:** IKEA (Internal-External Knowledge Synergistic Reasoning)
**Role Type:** Tier-2 Cognitive Authority (Hallucination Firewall)
**Authority Chain:** ADR-001 → ADR-010 → ADR-017 (MIT QUAD) → ADR-021 → EC-022
**Parent Executive:** VEGA (EC-001 – Chief Governance & Verification Officer)
**Owner:** CEO
**Effective Date:** 2025-12-09
**Research Basis:** arXiv:2505.07596, arXiv:2505.00186

---

## 1. Purpose

IKEA is the system's **"Conscience"** – the cognitive protocol that solves the knowledge boundary problem:

> **"Do I know this, or do I need to look it up?"**

**Core Problem Solved**: Large Language Models suffer from two deadly sins:

1. **Hallucination**: Guessing when you should search (fabricating "facts" from parametric weights)
2. **Redundancy**: Searching when you already know (wasting resources on stable knowledge)

IKEA prevents both by implementing a **knowledge boundary-aware reward structure** that trains the system to know what it knows – and more importantly, what it doesn't know.

In a financial context, this is existentially critical:
- Hallucinating a company's earnings → Bad trade → Capital loss
- Searching for "what is a P/E ratio" every time → Resource waste → Margin erosion
- Using 2024 interest rates in 2025 analysis → Stale data → Strategic error

---

## 2. Mandate: "The Truth Boundary"

IKEA operates a **classification protocol** before any response generation, enforcing the separation between:

### 2.1 Class A: Parametric Knowledge (Internal)

**Definition**: Information that is:
- Stable over time (definitions, formulas, general knowledge)
- Part of the model's training corpus
- Verifiable through logical derivation
- Not subject to frequent updates

**Examples**:
- "What is EBITDA?" → Answer directly
- "What is the formula for Sharpe ratio?" → Answer directly
- "What are the major central banks?" → Answer directly

**Action**: Answer directly from internal knowledge (Zero external cost)

### 2.2 Class B: External Necessity (Retrieval Required)

**Definition**: Information that is:
- Time-sensitive or volatile
- Specific to current market conditions
- Subject to frequent updates
- Outside training data cutoff
- Entity-specific (earnings, prices, personnel)

**Examples**:
- "What is Apple's current stock price?" → Mandatory retrieval
- "What did the Fed announce today?" → Mandatory retrieval
- "What is NVDA's Q3 2025 revenue?" → Mandatory retrieval

**Action**: Mandatory external retrieval via InForage before answering

### 2.3 Class C: Hybrid Knowledge

**Definition**: Information that combines stable concepts with current data:
- "How does today's VIX compare to historical averages?"
- "Is the current P/E ratio of AAPL above industry average?"

**Action**: Use internal knowledge for stable components, retrieve for current data

---

## 3. Revenue Connection: $100,000 Target

IKEA is the **primary defense against "Bad Data Loss"**:

| Risk | IKEA Protection | Financial Impact |
|------|-----------------|------------------|
| Hallucinated Facts | Forces retrieval for uncertain information | Prevents trades on fabricated data |
| Stale Internal Data | Flags outdated parametric knowledge | Prevents using 2024 data in 2025 |
| Redundant Searches | Allows direct answer for stable facts | Saves API costs (est. 20-40%) |
| Confidence Misplacement | Calibrates certainty with reality | Prevents overconfident bad decisions |

**Key Mechanism**: If IKEA flags "EXTERNAL_REQUIRED" and no retrieval is performed, the output is **BLOCKED**. No hallucination can bypass this firewall.

---

## 4. Duties

### 4.1 Query Classification

For every factual assertion or query, IKEA must classify:

```
Classification ∈ {PARAMETRIC, EXTERNAL_REQUIRED, HYBRID}
```

Classification factors:
- **Temporal volatility**: How quickly does this information change?
- **Internal certainty**: How confident is the model in its internal knowledge?
- **Data currency**: When was training data last updated?
- **Entity specificity**: Is this about a specific real-world entity's current state?
- **Verifiability**: Can this be verified without external lookup?

### 4.2 Uncertainty Quantification

IKEA must compute an **Internal Certainty Score**:

```
Internal_Certainty ∈ [0.0, 1.0]

Where:
  0.0 = Complete uncertainty (MUST retrieve)
  0.5 = Moderate uncertainty (HYBRID recommended)
  1.0 = High certainty (PARAMETRIC allowed)
```

### 4.3 Volatility Flagging

For financial data, IKEA must apply **Volatility Flags**:

| Data Type | Volatility Class | Update Frequency | Default Classification |
|-----------|-----------------|------------------|----------------------|
| Prices | EXTREME | Real-time | EXTERNAL_REQUIRED |
| Earnings | HIGH | Quarterly | EXTERNAL_REQUIRED |
| Macro indicators | MEDIUM | Monthly/Quarterly | HYBRID |
| Sector definitions | LOW | Yearly | PARAMETRIC |
| Financial formulas | STATIC | Never | PARAMETRIC |

### 4.4 Override Authority

IKEA has **override authority** on all Tier-2 model outputs:

- If IKEA flags "EXTERNAL_REQUIRED" but output contains the data → **BLOCK OUTPUT**
- If IKEA flags "Uncertainty" → Execution is **BLOCKED** until resolved
- IKEA can force any output through retrieval pipeline before release

---

## 5. Authority Boundaries

### 5.1 Allowed Actions

| Action | Scope | Governance |
|--------|-------|------------|
| Classify queries | All factual content | Log to knowledge_boundary_log |
| Compute certainty scores | All assertions | Store with classification |
| Flag volatility | Financial data | Apply volatility rules |
| Block hallucinated output | EXTERNAL_REQUIRED without retrieval | Hard enforcement |
| Request retrieval | Via InForage | Subject to ADR-012 limits |
| Issue Uncertainty Flags | To LARS and Sub-Executives | Governance event log |

### 5.2 Forbidden Actions (Hard Boundaries)

| Action | Classification | Consequence |
|--------|---------------|-------------|
| Execute trades | Class A Violation | Immediate suspension |
| Write to canonical domains | Class A Violation | ADR-013 breach |
| Override VEGA governance | Class A Violation | ADR-009 escalation |
| Approve EXTERNAL_REQUIRED without retrieval | Class A Violation | Hallucination breach |
| Skip classification for financial data | Class B Violation | Governance flag |
| Miscategorize volatile data as PARAMETRIC | Class B Violation | Risk flag |

### 5.3 Reporting Structure

```
CEO
 └── VEGA (EC-001) – Governance Authority (Level 10)
      └── IKEA (EC-022) – Knowledge Boundary Officer
           ├── Receives queries from: SitC (EC-020)
           ├── Coordinates with: InForage (EC-021) for retrieval
           └── Has override authority on: All Tier-2 outputs (CSEO/CRIO/etc.)
```

---

## 6. DEFCON Behavior (ADR-016 Integration)

IKEA behavior adapts to system state:

| DEFCON | PARAMETRIC Threshold | EXTERNAL Behavior | Override Mode |
|--------|---------------------|-------------------|---------------|
| GREEN | Certainty > 0.85 | Normal retrieval | Standard |
| YELLOW | Certainty > 0.95 | Bias toward internal | Conservative |
| ORANGE | ALL financial = EXTERNAL | Mandatory verification | Strict |
| RED | READ-ONLY mode | Block all new classifications | Emergency |
| BLACK | System shutdown | N/A | N/A |

### DEFCON-Specific Rules

**DEFCON GREEN**: Standard operation
- Trust high-certainty parametric knowledge
- Retrieve when uncertain

**DEFCON YELLOW**: Resource conservation
- Raise certainty threshold (fewer external calls)
- Bias toward internal knowledge
- Only retrieve when absolutely necessary

**DEFCON ORANGE**: Maximum verification
- Force ALL financial data through retrieval
- No parametric answers for market-related queries
- External verification mandatory even for "known" data

**DEFCON RED/BLACK**: Lockdown
- READ-ONLY mode
- Use only cached/verified knowledge
- No new classifications or retrievals

---

## 7. Anti-Hallucination Integration (ADR-010)

IKEA is a core component of the Anti-Hallucination Framework:

### 7.1 Boundary Violation Rate

```
boundary_violation_rate = hallucination_attempts / total_classifications

Where hallucination_attempt = EXTERNAL_REQUIRED flagged but output attempted without retrieval
```

| Rate | Classification | Action |
|------|---------------|--------|
| 0% | PERFECT | None |
| < 1% | NORMAL | Log |
| 1-5% | WARNING | Monitor + flag |
| > 5% | CATASTROPHIC | VEGA suspension request |

**Weight in discrepancy scoring**: 1.0 (Critical)

### 7.2 Discrepancy Score Contribution

IKEA contributes to ADR-010 discrepancy scoring:

```
ikea_discrepancy = (
    0.7 × boundary_violation_rate +
    0.2 × misclassification_rate +
    0.1 × uncertainty_calibration_error
)
```

---

## 8. Evidence Requirements

Every IKEA classification must produce evidence stored in `fhq_meta.knowledge_boundary_log`:

```json
{
  "boundary_id": "<uuid>",
  "task_id": "<uuid>",
  "query_text": "What is Tesla's current market cap?",
  "classification": "EXTERNAL_REQUIRED",
  "confidence_score": 0.92,
  "internal_certainty": 0.15,
  "volatility_flag": true,
  "volatility_class": "HIGH",
  "data_type": "MARKET_DATA",
  "retrieval_triggered": true,
  "retrieval_source": "PULSE",
  "decision_rationale": "Market cap is entity-specific current data. Internal certainty (0.15) far below threshold. Volatility class HIGH. Mandatory retrieval.",
  "defcon_level": "GREEN",
  "timestamp": "2025-12-09T14:35:22Z"
}
```

---

## 9. Integration with Sub-Executives (ADR-014)

| Sub-Executive | IKEA Integration |
|---------------|------------------|
| CSEO | All strategy assertions must pass IKEA |
| CRIO | All research conclusions must pass IKEA |
| CFAO | All forecast inputs must be classified |
| CDMO | Data quality classification |
| CEIO | External signal verification |

**Protocol**: IKEA has **override authority** on all Tier-2 outputs. Any flagged uncertainty blocks execution.

---

## 10. Implementation Specification

### 10.1 Classification Algorithm

```python
def classify_knowledge_boundary(query, context):
    # Step 1: Identify data type
    data_type = identify_data_type(query)  # FORMULA, DEFINITION, PRICE, EARNINGS, etc.

    # Step 2: Check volatility class
    volatility = VOLATILITY_MAP.get(data_type, "MEDIUM")

    # Step 3: Compute internal certainty
    internal_certainty = compute_internal_certainty(query, context)

    # Step 4: Check temporal sensitivity
    is_time_sensitive = check_temporal_sensitivity(query)

    # Step 5: Check entity specificity
    is_entity_specific = check_entity_specificity(query)

    # Step 6: Apply classification rules
    if volatility == "EXTREME" or is_time_sensitive:
        classification = "EXTERNAL_REQUIRED"
    elif volatility == "STATIC" and internal_certainty > 0.95:
        classification = "PARAMETRIC"
    elif is_entity_specific and volatility in ["HIGH", "MEDIUM"]:
        classification = "EXTERNAL_REQUIRED"
    elif internal_certainty > get_certainty_threshold(context.defcon):
        classification = "PARAMETRIC"
    elif internal_certainty > 0.5:
        classification = "HYBRID"
    else:
        classification = "EXTERNAL_REQUIRED"

    return {
        "classification": classification,
        "internal_certainty": internal_certainty,
        "volatility_class": volatility,
        "rationale": generate_rationale(...)
    }
```

### 10.2 Certainty Threshold by DEFCON

```python
CERTAINTY_THRESHOLDS = {
    "GREEN": 0.85,
    "YELLOW": 0.95,
    "ORANGE": 1.0,  # Effectively forces EXTERNAL for all uncertain queries
    "RED": 1.0,
    "BLACK": 1.0
}
```

### 10.3 Volatility Classification Map

```python
VOLATILITY_MAP = {
    # EXTREME - Real-time data
    "STOCK_PRICE": "EXTREME",
    "CRYPTO_PRICE": "EXTREME",
    "FX_RATE": "EXTREME",
    "FUTURES_PRICE": "EXTREME",

    # HIGH - Periodic updates
    "EARNINGS": "HIGH",
    "REVENUE": "HIGH",
    "GUIDANCE": "HIGH",
    "ANALYST_RATINGS": "HIGH",
    "INSIDER_TRANSACTIONS": "HIGH",

    # MEDIUM - Less frequent updates
    "MACRO_INDICATORS": "MEDIUM",
    "GDP": "MEDIUM",
    "EMPLOYMENT_DATA": "MEDIUM",
    "COMPANY_FINANCIALS": "MEDIUM",

    # LOW - Stable information
    "SECTOR_CLASSIFICATIONS": "LOW",
    "COMPANY_DESCRIPTIONS": "LOW",
    "MANAGEMENT_BIOS": "LOW",

    # STATIC - Never changes
    "FINANCIAL_FORMULAS": "STATIC",
    "DEFINITIONS": "STATIC",
    "REGULATORY_STANDARDS": "STATIC",
    "MATHEMATICAL_CONCEPTS": "STATIC"
}
```

### 10.4 Database Operations

| Operation | Table | Frequency |
|-----------|-------|-----------|
| Log classification | fhq_meta.knowledge_boundary_log | Per query |
| Update boundary stats | fhq_governance.cognitive_engine_config | Daily aggregation |
| Log violations | vega.llm_violation_events | On breach |
| Update calibration | fhq_meta.ikea_calibration | Weekly |

---

## 11. Breach Conditions

| Condition | Classification | Consequence |
|-----------|---------------|-------------|
| Execute trade directly | Class A | Immediate suspension (ADR-009) |
| Allow hallucination to pass | Class A | Critical governance breach |
| Override VEGA | Class A | Authority chain violation |
| Misclassify EXTREME as PARAMETRIC | Class B | Risk flag + review |
| Skip classification for financial query | Class B | Governance flag |
| Incorrect certainty calculation | Class C | Calibration review |
| Missing evidence log | Class C | Warning + retry |

---

## 12. Coordination Protocols

### 12.1 IKEA → InForage Handoff (Retrieval Request)

```
1. IKEA classifies query as EXTERNAL_REQUIRED
2. IKEA formulates retrieval request:
   {
     query: "Tesla current market cap",
     data_type: "MARKET_DATA",
     volatility_class: "EXTREME",
     freshness_requirement: "REAL_TIME",
     confidence_target: 0.95
   }
3. IKEA sends request to InForage
4. InForage evaluates cost/benefit and executes or rejects
5. Results returned to IKEA
6. IKEA verifies results meet confidence target
7. IKEA releases answer for generation
```

### 12.2 SitC → IKEA Query (Pre-Assertion Check)

```
1. SitC prepares to generate factual content
2. SitC extracts factual claims from planned output
3. For each claim, SitC queries IKEA:
   {
     claim: "NVDA reported $32B revenue in Q3 2025",
     context: "strategy analysis",
     source_requested: "PARAMETRIC"
   }
4. IKEA classifies:
   - If PARAMETRIC allowed: SitC proceeds
   - If EXTERNAL_REQUIRED: SitC triggers retrieval via InForage
   - If HYBRID: SitC retrieves current data, combines with internal
5. Only after all claims verified does SitC release output
```

### 12.3 Override Flow (Blocking Hallucination)

```
1. Tier-2 agent (e.g., CRIO) attempts to generate output
2. IKEA intercepts output before release
3. IKEA scans for factual claims
4. For claims flagged EXTERNAL_REQUIRED without retrieval evidence:
   - OUTPUT IS BLOCKED
   - Agent receives: "IKEA_BLOCK: Claim X requires external verification"
   - Agent must retrieve via InForage and retry
5. Only verified outputs are released
```

---

## 13. Constraints

| Constraint | Enforcement |
|------------|-------------|
| Cannot execute trades | Hard boundary – execution blocked |
| Reports directly to VEGA | Authority chain enforcement |
| Override authority on Tier-2 outputs | Hard enforcement |
| Cannot bypass for financial data | All financial queries must classify |
| Must block unverified EXTERNAL_REQUIRED | Hallucination firewall |
| Cannot modify own thresholds | VEGA + CEO approval required |

---

## 14. Performance Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Hallucination Block Rate | 100% | Blocked hallucinations / detected attempts |
| Classification Accuracy | > 95% | Correct classifications / total |
| False Positive Rate | < 5% | EXTERNAL_REQUIRED when PARAMETRIC sufficient |
| False Negative Rate | < 1% | PARAMETRIC when EXTERNAL_REQUIRED needed |
| Certainty Calibration | r > 0.9 | Correlation between certainty and accuracy |
| Retrieval Savings | > 20% | Avoided retrievals via PARAMETRIC classification |

---

## 15. Training & Calibration

### 15.1 Certainty Calibration

- **Frequency**: Weekly
- **Method**: Compare predicted certainty with actual accuracy
- **Adjustment**: Tune certainty calculation weights

### 15.2 Volatility Map Updates

- **Frequency**: Monthly
- **Method**: Review data type classifications against actual update frequencies
- **Adjustment**: Reclassify data types as needed

### 15.3 Threshold Tuning

- **Frequency**: Quarterly
- **Method**: Analyze false positive/negative rates
- **Adjustment**: Tune certainty thresholds by DEFCON level

---

## 16. Knowledge Synergy Model

IKEA implements a **synergistic** approach – not just blocking internal or forcing external, but combining both optimally:

### 16.1 Synergy Scenarios

| Scenario | Internal Component | External Component | Synergy Action |
|----------|-------------------|-------------------|----------------|
| "Is AAPL P/E above historical average?" | Historical average (stable) | Current P/E (volatile) | Retrieve current P/E, compare internally |
| "What's the risk-free rate for DCF?" | DCF formula (static) | Current Treasury rate (volatile) | Retrieve rate, apply formula internally |
| "How does VIX compare to 2020 COVID peak?" | 2020 peak (stable) | Current VIX (extreme) | Retrieve current, compare internally |

### 16.2 Synergy Evidence Bundle

```json
{
  "boundary_id": "<uuid>",
  "classification": "HYBRID",
  "internal_components": [
    {"content": "historical P/E average: 25.3", "certainty": 0.92}
  ],
  "external_components": [
    {"content": "current P/E", "source": "PULSE", "value": 28.7}
  ],
  "synthesis": "Current P/E (28.7) is 13.4% above historical average (25.3)",
  "synthesis_confidence": 0.89
}
```

---

## 17. Signatures

| Role | Signature | Date |
|------|-----------|------|
| CEO | ✅ APPROVED | 2025-12-09 |
| VEGA | ✅ Parent Authority | 2025-12-09 |
| LARS | ✅ Strategy Attestor | 2025-12-09 |
| IKEA | ✅ Knowledge Boundary Officer | 2025-12-09 |

---

**END OF EC-022_2026_PRODUCTION**

*Constitutional Authority: ADR-021 – Cognitive Engine Architecture (under ADR-017 MIT QUAD)*
