# FINN CRITICAL MEMO: CRP-20251208
## Contextual Retrieval Protocol (CRP)

**Classification:** BINDING OPERATIONAL POLICY
**Authority:** CEO DIRECTIVE ARO-20251208/IGNITION
**Employment Contract:** EC-004_2026_PRODUCTION (FINN)
**Effective Date:** 2025-12-08T23:00:00Z
**Status:** ACTIVE

---

## 1. Purpose

This memo defines the Contextual Retrieval Protocol (CRP) for all memory operations in FjordHQ's autonomous intelligence system. With DeepSeek R1 as the primary reasoning engine, proper regime-gated retrieval is critical to prevent:

- Use of Bear-strategies in Bull-regime
- Reactivation of crisis memories in calm markets
- Context-mismatch between CEIO signals and LARS strategy intent
- Methodology corruption from outdated patterns

---

## 2. Regime-Gated Lookup (MANDATORY)

### 2.1 The Regime Gate Rule

**ALL memory queries MUST include a regime filter.**

#### ILLEGAL Retrieval (FORBIDDEN):
```sql
SELECT * FROM fhq_memory.embedding_store
ORDER BY embedding <-> :query
LIMIT 10;
```

#### LEGAL Retrieval (REQUIRED):
```sql
SELECT *
FROM fhq_memory.embedding_store
WHERE regime = (SELECT current_regime FROM fhq_meta.regime_state)
ORDER BY embedding <-> :query
LIMIT 10;
```

### 2.2 Function Usage

All agents MUST use `fhq_memory.regime_gated_search()`:

```sql
SELECT * FROM fhq_memory.regime_gated_search(
    p_query_embedding := :embedding,
    p_current_regime := (SELECT current_regime FROM fhq_meta.regime_state),
    p_querying_agent := 'FINN',
    p_limit := 10,
    p_min_relevance := 0.1
);
```

---

## 3. Temporal Decay Parameters

### 3.1 Decay Formula

```
effective_relevance = base_relevance * exp(-λ * age_in_days)
```

### 3.2 λ (Lambda) Parameters by Content Type

| Content Type | λ Value | Half-Life (days) | Rationale |
|--------------|---------|------------------|-----------|
| Market Signals | 0.35 | 2.0 | Fast-changing, recent dominates |
| Regime Analysis | 0.15 | 4.6 | Medium persistence |
| Causal Edges | 0.07 | 9.9 | Structural relationships persist |
| Research Notes | 0.10 | 6.9 | Methodology insights |
| Strategy Patterns | 0.05 | 13.9 | Strategic memory longer-lived |
| Eternal Truths | 0.00 | ∞ | Permanent causal structures |

### 3.3 Default λ

If content type is unspecified, use **λ = 0.10** (decay_factor column default).

---

## 4. Eternal Truths (PERMANENT_CAUSAL)

### 4.1 Definition

Eternal Truths are fundamental causal structures that should NOT decay. They represent validated relationships in the Alpha Graph that have passed rigorous testing.

### 4.2 Tagging Rules

FINN is the sole authority for tagging content as `PERMANENT_CAUSAL`. Criteria:

1. **Statistical Validation**: p-value < 0.01 across multiple regimes
2. **Temporal Stability**: Relationship held for 6+ months of historical data
3. **Cross-Asset Validity**: Applies to 3+ assets or is explicitly single-asset
4. **VEGA Approval**: Documented in governance evidence

### 4.3 Tagging Command

```sql
UPDATE fhq_memory.embedding_store
SET
    is_eternal_truth = TRUE,
    eternal_truth_tag = 'PERMANENT_CAUSAL',
    decay_factor = 0.0
WHERE embedding_id = :id
  AND source_agent = 'FINN';
```

---

## 5. Cross-Agent Retrieval Boundaries

### 5.1 Agent-Specific Rules

| Agent | Read Access | Write Access | Constraints |
|-------|-------------|--------------|-------------|
| **FINN** | All memories | Own memories | Can define decay params |
| **CEIO** | All memories | Own hypotheses | Must use regime + perception filter |
| **LARS** | Strategic memories | None | Read-only orchestration |
| **LINE** | Execution memories | Execution logs | Current regime only |
| **VEGA** | All memories | Audit logs | Full audit access |
| **STIG** | All memories | Infrastructure | Read-only for data |

### 5.2 CEIO Retrieval Mandate

CEIO must include BOTH regime and perception filters:

```sql
SELECT * FROM fhq_memory.regime_gated_search(
    p_query_embedding := :embedding,
    p_current_regime := (SELECT current_regime FROM fhq_meta.regime_state),
    p_querying_agent := 'CEIO',
    p_limit := 10,
    p_min_relevance := 0.2
)
WHERE perception_type IS NULL
   OR perception_type = (SELECT perception_type FROM fhq_perception.current_state);
```

### 5.3 IoS-012 Execution Engine

IoS-012 may ONLY access memory through LARS-authorized queries. Direct memory access is prohibited.

---

## 6. DeepSeek R1 Chain-of-Thought Instruction

When using DeepSeek R1 (deepseek-reasoner) for heavy reasoning tasks, the system prompt MUST include:

```
MEMORY RETRIEVAL CONSTRAINT:
You are operating in a regime-gated memory system. Before using any retrieved context:
1. Verify the regime filter matches current market regime
2. Apply temporal decay - recent memories (< 7 days) should dominate
3. Flag any cross-regime content with [CROSS_REGIME_WARNING]
4. Do not use memories tagged with regime != {current_regime} for trading decisions

Current Regime: {regime}
Decay Parameter λ: {lambda}
```

---

## 7. VEGA Oversight

### 7.1 Compliance Monitoring

VEGA shall verify via `fhq_memory.retrieval_audit_log`:

- [ ] All queries have `regime_filter_used = TRUE`
- [ ] Decay function is applied (`decay_applied = TRUE`)
- [ ] No cross-regime violations (`cross_regime_attempt = FALSE` or `cross_regime_blocked = TRUE`)
- [ ] Retrieval lineage logged for all queries

### 7.2 Violation Response

| Violation Type | Response |
|----------------|----------|
| Missing regime filter | ADR-009 Class-B Warning |
| Cross-regime unblocked | ADR-009 Class-A Suspension |
| Decay bypass | ADR-009 Class-B Warning |
| Audit log gap | Investigation required |

---

## 8. Implementation Checklist

- [x] `fhq_memory.embedding_store` - regime column present
- [x] `fhq_memory.regime_gated_search()` - function created
- [x] `fhq_memory.calculate_effective_relevance()` - decay function active
- [x] `fhq_memory.retrieval_audit_log` - audit table created
- [x] `fhq_meta.regime_state` - regime state table created
- [x] `fhq_meta.llm_provider_config` - DeepSeek configured
- [x] `fhq_governance.eloop_config` - caching enabled

---

## 9. Attestation

**Certified by:** FINN (Research Director)
**Employment Contract:** EC-004_2026_PRODUCTION
**Statement:** I certify that this Contextual Retrieval Protocol defines the canonical methodology for all memory operations in FjordHQ. DeepSeek R1 reasoning tasks must explicitly use regime filters. Temporal decay with λ = 0.10 default is now active. Eternal truths are reserved for PERMANENT_CAUSAL tagged content only.

**Timestamp:** 2025-12-08T23:00:00Z
**Hash Chain:** HC-FINN-CRP-20251208

---

## 10. References

- ARO-20251208 Section 8 (Contextual Retrieval Protocol)
- ADR-010 (Discrepancy Scoring)
- ADR-015 (Meta-Governance)
- Migration 096 (pgvector Memory Foundation)
