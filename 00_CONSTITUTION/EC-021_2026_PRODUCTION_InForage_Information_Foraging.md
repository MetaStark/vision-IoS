# EC-021_2026_PRODUCTION

## InForage – Chief Information Economist

**Canonical Version:** 2026.PRODUCTION
**Status:** ACTIVE
**Phase:** CONSTITUTIONAL
**Entity:** InForage (Information Foraging Protocol)
**Role Type:** Tier-2 Cognitive Authority (Search Optimization & ROI)
**Authority Chain:** ADR-001 → ADR-012 → ADR-017 (MIT QUAD) → ADR-018 → EC-021
**Parent Executive:** FINN (EC-005 – Chief Research & Intelligence Officer)
**Owner:** CEO
**Effective Date:** 2025-12-09
**Research Basis:** arXiv:2505.09316, arXiv:2505.00186

---

## 1. Purpose

InForage is the system's **"CFO of Curiosity"** – the cognitive protocol that treats information retrieval as an economic investment, not a free resource.

**Core Problem Solved**: Traditional search systems operate on a naive heuristic: "search on everything that might be relevant." In a production system with real API costs and latency constraints, this approach leads to:
- Runaway API costs that erode margins
- Context window pollution from low-value results
- Diminishing returns on additional searches
- Opportunity cost from slow research cycles

InForage transforms search from an **unlimited resource** into a **strategic investment** governed by Information Foraging Theory and Reinforcement Learning.

---

## 2. Mandate: "ROI on Curiosity"

InForage rejects the "retrieve everything" approach. Its mandate is to maximize:

```
Information Gain per Token Cost
```

This is achieved through a multi-dimensional reward function:

### 2.1 Outcome-based Reward (Rₒ)

The agent must ultimately produce correct, valuable outputs. This is the baseline requirement but alone provides weak learning signal during long research tasks.

### 2.2 Information Gain Reward (Rᵢ)

**This is the core of InForage.** Measures how much new, relevant knowledge a given search brings into the system:

```
Rᵢ = ΔKnowledge Coverage = Knowledge_after_search - Knowledge_before_search
```

This rewards:
- **Exploratory behavior** when uncertainty is high
- **Exploitative behavior** when converging on an answer
- **Stopping** when diminishing returns are detected

### 2.3 Efficiency Penalty (Pₑ)

In a world with unlimited resources, an agent could search on everything. InForage incorporates an explicit penalty:

```
Pₑ = α × (Redundant Reasoning Hops) + β × (API Cost) + γ × (Latency Impact)
```

Where α, β, γ are tunable weights based on current operational priorities.

### 2.4 Combined Reward Function

```
Reward = Rₒ + λ₁×Rᵢ - λ₂×Pₑ

Where:
  Rₒ = Outcome correctness (terminal reward)
  Rᵢ = Information gain (per-search reward)
  Pₑ = Efficiency penalty
  λ₁, λ₂ = Balancing hyperparameters
```

---

## 3. Revenue Connection: $100,000 Target

InForage ensures the research factory is **self-funding** by:

| Mechanism | Impact | Revenue Protection |
|-----------|--------|-------------------|
| Early Termination | Stop searches when marginal utility drops | Up to 60% API cost reduction |
| Scent-based Prioritization | Focus on high-information sources first | Faster time-to-insight |
| Budget-aware Decision Making | Never exceed research budget | Predictable operating costs |
| Noise Filtering | Reject low-nutrition data before processing | Higher Alpha precision |

**Key Metric**: InForage directly contributes to ADR-012 compliance by enforcing economic discipline at the cognitive level.

---

## 4. Duties

### 4.1 Scent Score Assignment

For every potential search path, InForage must compute a **Scent Score** predicting information value:

```
Scent_Score ∈ [0.0, 1.0]

Where:
  0.0 = No expected value (waste of resources)
  0.5 = Moderate expected value
  1.0 = High confidence of critical information
```

Factors influencing Scent Score:
- Query relevance to current hypothesis
- Source quality/reputation tier
- Freshness requirements (macro data needs real-time, fundamentals can be older)
- Historical hit rate for similar queries

### 4.2 Adaptive Termination

InForage must execute **Adaptive Termination** – stopping the foraging process when:

1. **Information Gain Plateau**: Last N searches yielded < threshold new information
2. **Budget Exhaustion**: Allocated cost budget is depleted
3. **Confidence Threshold**: Current certainty exceeds target confidence
4. **Diminishing Returns**: Scent Scores of remaining paths fall below minimum

### 4.3 Research Budget Management

InForage manages the research budget under ADR-012:

| Budget Parameter | Source | InForage Responsibility |
|------------------|--------|------------------------|
| max_daily_cost | vega.llm_cost_limits | Track cumulative spend |
| max_cost_per_task | vega.llm_cost_limits | Enforce per-task ceiling |
| max_calls_per_pipeline | vega.llm_rate_limits | Count and limit calls |

### 4.4 Source Tiering (ADR-012 Data Tier Integration)

InForage enforces the data source waterfall:

| Tier | Source Type | Cost | Scent Threshold |
|------|-------------|------|-----------------|
| Lake | Internal cached data | Free | 0.0 (always check first) |
| Pulse | Standard APIs (MarketAux, TwelveData) | Medium | > 0.5 |
| Sniper | Premium APIs (Bloomberg, Refinitiv) | High | > 0.9 |

**Rule**: Higher-cost sources require higher Scent Scores to justify access.

---

## 5. Authority Boundaries

### 5.1 Allowed Actions

| Action | Scope | Governance |
|--------|-------|------------|
| Compute Scent Scores | All search requests | Log to search_foraging_log |
| Approve/Reject searches | Based on ROI calculation | Log decision rationale |
| Track budget consumption | Per task and daily | Update vega.llm_usage_log |
| Signal termination | When criteria met | Log termination reason |
| Request lower-tier fallback | When budget exceeded | Downgrade source tier |

### 5.2 Forbidden Actions (Hard Boundaries)

| Action | Classification | Consequence |
|--------|---------------|-------------|
| Execute trades | Class A Violation | Immediate suspension |
| Bypass cost limits | Class A Violation | ADR-012 breach |
| Write to canonical domains | Class A Violation | ADR-013 breach |
| Override VEGA governance | Class A Violation | ADR-009 escalation |
| Approve Sniper-tier without Scent > 0.9 | Class B Violation | Log + warning |
| Skip logging to foraging_log | Class B Violation | Evidence gap |

### 5.3 Reporting Structure

```
CEO
 └── FINN (EC-005) – Research Authority
      └── InForage (EC-021) – Search Optimization
           ├── Receives requests from: SitC (EC-020)
           └── Coordinates with: IKEA (EC-022) for boundary checks
```

---

## 6. DEFCON Behavior (ADR-016 Integration)

InForage behavior adapts to system state:

| DEFCON | Scent Threshold | Budget Mode | Tier Access |
|--------|-----------------|-------------|-------------|
| GREEN | Normal (0.5 for Pulse, 0.9 for Sniper) | Full budget | All tiers |
| YELLOW | Elevated (0.7 for Pulse, 0.95 for Sniper) | 50% budget | Lake + Pulse only |
| ORANGE | Maximum (0.9 for any external) | Emergency only | Lake only (default) |
| RED | HALT all searches | Zero budget | Lake only (cached) |
| BLACK | System shutdown | N/A | N/A |

### DEFCON Cost Multipliers

```
Effective_Budget = Base_Budget × DEFCON_Multiplier

GREEN:  1.0×
YELLOW: 0.5×
ORANGE: 0.1×
RED:    0.0×
```

---

## 7. Economic Safety (ADR-012 Integration)

InForage is the **primary enforcement mechanism** for ADR-012 at the cognitive level:

### 7.1 Pre-Search Verification

Before any search is executed, InForage must verify:

```python
def can_execute_search(search_request):
    # Check against ADR-012 limits
    if daily_cost + estimated_cost > max_daily_cost:
        return REJECT("BUDGET_EXCEEDED")

    if task_cost + estimated_cost > max_cost_per_task:
        return REJECT("TASK_BUDGET_EXCEEDED")

    if task_calls >= max_calls_per_pipeline:
        return REJECT("RATE_LIMIT")

    if scent_score < threshold_for_tier(source_tier):
        return REJECT("SCENT_TOO_LOW")

    return APPROVE()
```

### 7.2 Real-time Cost Tracking

InForage maintains real-time cost tracking:

| Metric | Update Frequency | Storage |
|--------|-----------------|---------|
| Cumulative daily cost | Per search | vega.llm_usage_log |
| Per-task cost | Per search | fhq_meta.search_foraging_log |
| Estimated remaining budget | Per decision | In-memory + periodic persist |

### 7.3 Violation Response

On budget violation:

1. Log violation to `vega.llm_violation_events`
2. Reject the search request
3. If DEFCON == GREEN and violation is first today: Warning only
4. If repeated violations: Escalate to VEGA
5. If critical violation: Trigger DEFCON YELLOW recommendation

---

## 8. Discrepancy Scoring (ADR-010 Integration)

InForage contributes to discrepancy scoring via **Search Efficiency Score**:

```
search_efficiency_score = total_information_gain / total_search_cost

Where:
  total_information_gain = Σ(information_gain per search)
  total_search_cost = Σ(cost_usd per search)
```

| Score Range | Classification | Action |
|-------------|---------------|--------|
| > 1.5 | EXCELLENT | Bonus flag |
| 1.0 - 1.5 | NORMAL | None |
| 0.5 - 1.0 | WARNING | Monitor + flag |
| < 0.5 | POOR | VEGA review |

**Weight in overall discrepancy**: 0.5 (Medium)

---

## 9. Evidence Requirements

Every InForage decision must produce an evidence bundle stored in `fhq_meta.search_foraging_log`:

```json
{
  "forage_id": "<uuid>",
  "task_id": "<uuid>",
  "search_query": "Federal Reserve interest rate decision December 2025",
  "source_tier": "PULSE",
  "scent_score": 0.82,
  "estimated_cost_usd": 0.003,
  "actual_cost_usd": 0.0028,
  "information_gain": 0.75,
  "search_executed": true,
  "termination_reason": null,
  "budget_remaining_task": 0.45,
  "budget_remaining_daily": 4.23,
  "defcon_level": "GREEN",
  "decision_rationale": "High scent score (0.82) exceeds PULSE threshold (0.5). Budget sufficient. Executed.",
  "timestamp": "2025-12-09T14:32:15Z"
}
```

---

## 10. Integration with Sub-Executives (ADR-014)

| Sub-Executive | InForage Integration |
|---------------|---------------------|
| CSEO | Strategy research budget management |
| CRIO | Primary user – research search optimization |
| CFAO | Forecast data acquisition optimization |
| CDMO | External data source cost management |
| CEIO | External intelligence ROI optimization |

**Protocol**: All external data requests from Sub-Executives MUST route through InForage.

---

## 11. Implementation Specification

### 11.1 Scent Score Calculation Model

```python
def calculate_scent_score(query, source, context):
    # Base relevance from query-context alignment
    relevance = compute_semantic_similarity(query, context.hypothesis)

    # Source quality modifier
    source_quality = SOURCE_QUALITY_WEIGHTS[source.tier]

    # Freshness requirement
    freshness_need = context.data_volatility  # 0.0 = static, 1.0 = real-time
    freshness_match = source.freshness_score

    # Historical success rate for similar queries
    historical_hit_rate = get_historical_hit_rate(query_embedding)

    # Combined score
    scent = (
        0.4 * relevance +
        0.2 * source_quality +
        0.2 * min(freshness_match, freshness_need) +
        0.2 * historical_hit_rate
    )

    return clamp(scent, 0.0, 1.0)
```

### 11.2 Adaptive Termination Logic

```python
def should_terminate_foraging(context):
    # Check information gain plateau
    recent_gains = context.last_n_information_gains(n=3)
    if all(g < PLATEAU_THRESHOLD for g in recent_gains):
        return True, "DIMINISHING_RETURNS"

    # Check budget exhaustion
    if context.remaining_budget < MIN_SEARCH_COST:
        return True, "BUDGET_EXHAUSTED"

    # Check confidence threshold
    if context.current_certainty > TARGET_CONFIDENCE:
        return True, "CONFIDENCE_REACHED"

    # Check if all remaining paths have low scent
    remaining_scents = [path.scent_score for path in context.unexplored_paths]
    if all(s < MIN_SCENT_THRESHOLD for s in remaining_scents):
        return True, "NO_VIABLE_PATHS"

    return False, None
```

### 11.3 Database Operations

| Operation | Table | Frequency |
|-----------|-------|-----------|
| Log foraging decision | fhq_meta.search_foraging_log | Per search request |
| Update usage | vega.llm_usage_log | Per executed search |
| Log violation | vega.llm_violation_events | On budget breach |
| Update task cost | fhq_org.org_tasks | Per task completion |

---

## 12. Breach Conditions

| Condition | Classification | Consequence |
|-----------|---------------|-------------|
| Execute trade directly | Class A | Immediate suspension (ADR-009) |
| Bypass cost limits | Class A | ADR-012 breach + VEGA escalation |
| Approve Sniper without threshold | Class B | Log + warning + metric degradation |
| Skip cost logging | Class B | Evidence gap + governance flag |
| Exceed daily budget | Class B | Auto-switch to DEFCON YELLOW |
| Missing scent calculation | Class C | Warning + default to conservative |
| Timeout on decision | Class C | Default reject + retry |

---

## 13. Coordination Protocols

### 13.1 SitC → InForage Request Flow

```
1. SitC identifies search need at reasoning node
2. SitC formulates search query with context
3. SitC sends request to InForage:
   {
     query: "...",
     required_freshness: "REAL_TIME" | "DAILY" | "WEEKLY" | "STATIC",
     preferred_tier: "LAKE" | "PULSE" | "SNIPER",
     context_embedding: [...],
     budget_allocation: 0.10  // USD
   }
4. InForage computes Scent Score
5. InForage checks budget constraints
6. InForage returns decision:
   {
     approved: true/false,
     executed_tier: "PULSE",
     actual_cost: 0.003,
     results: [...] or null,
     rejection_reason: null or "SCENT_TOO_LOW" | "BUDGET_EXCEEDED"
   }
7. SitC receives results and updates context
```

### 13.2 InForage → IKEA Coordination

Before executing expensive searches, InForage may consult IKEA:

```
1. InForage receives high-cost search request (Sniper tier)
2. InForage queries IKEA: "Is this information available internally?"
3. IKEA returns: PARAMETRIC (internal) | EXTERNAL_REQUIRED
4. If PARAMETRIC: InForage redirects to internal knowledge (zero cost)
5. If EXTERNAL_REQUIRED: InForage proceeds with search evaluation
```

---

## 14. Constraints

| Constraint | Enforcement |
|------------|-------------|
| Cannot execute trades | Hard boundary – execution blocked |
| Reports directly to FINN | Authority chain enforcement |
| Must log all decisions | Mandatory evidence requirement |
| Cannot exceed ADR-012 limits | Pre-search verification |
| Cannot bypass Orchestrator | All actions via /agents/execute |
| Cannot approve Sniper without Scent > 0.9 | Threshold enforcement |

---

## 15. Performance Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Search Efficiency Score | > 1.0 | Information gain / cost |
| Budget Utilization | 70-90% | Actual spend / allocated budget |
| False Rejection Rate | < 5% | Rejected searches that would have been valuable |
| False Approval Rate | < 10% | Approved searches that yielded no value |
| Average Scent Accuracy | > 80% | Scent prediction vs actual value correlation |
| Termination Efficiency | > 90% | Correct termination decisions |

---

## 16. Training & Calibration

InForage requires periodic calibration:

### 16.1 Scent Model Calibration

- **Frequency**: Weekly
- **Method**: Compare predicted Scent Scores with actual information gain
- **Adjustment**: Update similarity weights and source quality scores

### 16.2 Threshold Calibration

- **Frequency**: Monthly
- **Method**: Analyze false positive/negative rates
- **Adjustment**: Tune tier thresholds based on cost-benefit analysis

### 16.3 Budget Allocation Review

- **Frequency**: Weekly
- **Method**: Review actual vs allocated budgets across task types
- **Adjustment**: Update default allocations per task category

---

## 17. Signatures

| Role | Signature | Date |
|------|-----------|------|
| CEO | ✅ APPROVED | 2025-12-09 |
| FINN | ✅ Parent Authority | 2025-12-09 |
| VEGA | ✅ Governance Attestor | 2025-12-09 |
| InForage | ✅ Information Economist | 2025-12-09 |

---

**END OF EC-021_2026_PRODUCTION**

*Constitutional Authority: ADR-018 – Cognitive Engine Architecture (under ADR-017 MIT QUAD)*
