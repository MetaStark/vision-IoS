# C4 (Causal Coherence) Implementation Plan
## FINN+ Tier-2 Conflict Summarization

**Document ID:** C4-IMPLEMENTATION-PLAN-PHASE3
**Status:** PLANNING (Ready for Implementation)
**Authority:** LARS Directive 5.1 (Priority 2)
**Date:** 2025-11-24

---

## Executive Summary

**C4 (Causal Coherence)** is currently the only CDS component returning 0.0 (placeholder). This component represents **20% of the total CDS weight** and is critical for proving that FINN+ can handle narrative dissonance, as required for G3 VEGA audit.

**Current Status:**
- Weight: 0.20 (20% of CDS)
- Implementation: Placeholder (returns 0.0)
- Impact: CDS operates at 80% theoretical maximum

**Proposed Solution:**
- Implement FINN+ Tier-2 Conflict Summarization
- Use LLM to assess causal coherence of regime narratives
- Score coherence from 0.0 (incoherent) to 1.0 (perfectly coherent)

---

## Problem Statement

### Why C4 Matters

From LARS CDS Formal Contract:

> **C4 – Causal Coherence:**
> LLM-based causal link score (bounded + normalized)
> Source: FINN+ Tier-2

**Purpose:** Assess whether the market regime classification is supported by coherent causal narratives.

**Example:**
- **BEAR regime** with **rising prices** = **LOW coherence** (contradictory)
- **BULL regime** with **strong momentum** = **HIGH coherence** (aligned)

### Current Gap

Without C4 implementation:
- CDS max theoretical value: 0.80 (instead of 1.0)
- No assessment of narrative coherence
- FINN+ Tier-2 mandate unfulfilled (FINN_TIER2_MANDATE.md)
- G3 audit requirement: "Prove FINN handles dissonance"

---

## FINN+ Tier-2: Conflict Summarization

### Mandate (from FINN_TIER2_MANDATE.md)

**FINN+ Tier-2 is mandated to:**

1. **Detect conflicts** between FINN+ regime classification and market narratives
2. **Summarize conflicts** in 3 sentences or less
3. **Assess coherence** of regime classification given narratives
4. **Use LLM** for causal reasoning (Claude/GPT-4)

**Cost Constraint (ADR-012):**
- Maximum: $0.50 per summary
- Rate limit: 100 summaries/hour
- Daily budget: $500 cap

---

## Proposed Implementation

### Architecture

```
Market Data + Regime Classification
            ↓
  FINN+ Tier-2 Engine
            ↓
    LLM Prompt Engineering
    (Claude/GPT-4)
            ↓
  Conflict Summarization
  (3 sentences max)
            ↓
   Coherence Score (0.0–1.0)
            ↓
    C4 Component → CDS Engine
```

### Input Contract

**FINN+ Tier-2 receives:**
- Regime classification: BEAR/NEUTRAL/BULL
- Regime confidence: 0.0–1.0
- Features: 7 z-scored indicators
- Recent price action: Last N bars
- (Optional) News headlines/sentiment

### Processing Logic

**Step 1: Narrative Construction**
- Extract key features (return_z, volatility_z, drawdown_z)
- Build narrative: "Market shows [indicators] suggesting [regime]"

**Step 2: LLM Prompt**
```
You are a market analyst. Assess the causal coherence of the following:

Regime: BULL
Confidence: 75%
Recent price action: +15% over 20 days
Volatility: Low (0.8% daily)
Drawdown: Minimal (-2% from peak)

Question: Is the BULL classification causally coherent given the indicators?
Rate coherence from 0.0 (incoherent) to 1.0 (perfectly coherent).
Provide: Coherence score + 3-sentence justification.
```

**Step 3: Parse LLM Response**
- Extract coherence score: 0.0–1.0
- Extract justification: 3 sentences
- Validate bounds

**Step 4: Output**
- Coherence score → C4 component
- Justification → Stored for audit
- Cost tracking → ADR-012 compliance

### Output Contract

**FINN+ Tier-2 produces:**
- **coherence_score:** float ∈ [0.0, 1.0] (C4 component)
- **summary:** string (3 sentences max, 300 char limit)
- **llm_cost:** float (USD)
- **llm_api_calls:** int
- **timestamp:** datetime
- **signature:** Ed25519 (ADR-008)

---

## Implementation Steps

### Phase 1: Core Engine (Week 3)

1. **Create `finn_tier2_engine.py`**
   - FINNTier2Engine class
   - Prompt engineering module
   - LLM API integration (Claude/GPT-4)
   - Response parsing + validation

2. **Integration with CDS Engine**
   - Replace C4 placeholder: `compute_causal_coherence(0.0)` → `tier2_engine.compute_coherence(...)`
   - Pass coherence score to CDS

3. **Unit Tests**
   - Test prompt generation
   - Test response parsing
   - Test cost tracking
   - Mock LLM responses

### Phase 2: Cost Management (Week 3)

1. **Rate Limiting**
   - Max 100 calls/hour
   - Exponential backoff on rate limit

2. **Caching**
   - Cache recent coherence scores
   - Avoid redundant LLM calls for same inputs

3. **Cost Tracking**
   - Log every LLM call (timestamp, cost, token count)
   - Alert if approaching daily budget ($500)

### Phase 3: Production Readiness (Week 4+)

1. **Multi-LLM Support**
   - Claude (primary)
   - GPT-4 (fallback)
   - Open-source models (backup)

2. **Database Persistence**
   - Store tier2_results in fhq_phase3.tier2_summaries
   - Include justification text, coherence score, cost

3. **Monitoring & Alerts**
   - Track coherence score distribution
   - Alert on unusually low coherence (< 0.3)
   - Alert on cost spikes

---

## Prompt Engineering

### Template

```python
COHERENCE_PROMPT_TEMPLATE = """
You are a quantitative market analyst assessing regime classification coherence.

**Regime Classification:**
- Regime: {regime_label}
- Confidence: {confidence:.1%}

**Market Indicators (z-scored):**
- Return (20d): {return_z:.2f}σ
- Volatility: {volatility_z:.2f}σ
- Drawdown: {drawdown_z:.2f}σ
- MACD: {macd_diff_z:.2f}σ

**Recent Price Action:**
- Price change (20d): {price_change:.1%}
- Current drawdown: {drawdown:.1%}

**Task:**
1. Assess if the {regime_label} classification is causally coherent given the indicators.
2. Rate coherence from 0.0 (incoherent/contradictory) to 1.0 (perfectly coherent/aligned).
3. Provide a 3-sentence justification.

**Format:**
Coherence: [0.0-1.0]
Justification: [3 sentences, max 300 characters]
"""
```

### Example Output

```
Coherence: 0.85
Justification: The BULL classification is well-supported by positive return z-score (+1.2σ) and minimal drawdown (-2%). Low volatility (0.6σ) confirms stable upward momentum. All indicators align with bullish regime characteristics.
```

### Scoring Rubric

| Coherence | Description | Example |
|-----------|-------------|---------|
| 0.9–1.0 | Perfect alignment | BULL + strong momentum + low vol |
| 0.7–0.9 | Strong alignment | BULL + moderate momentum |
| 0.5–0.7 | Weak alignment | NEUTRAL + mixed signals |
| 0.3–0.5 | Contradictory | BULL + high drawdown |
| 0.0–0.3 | Severe mismatch | BEAR + rising prices |

---

## Cost Estimation

### Per-Call Cost (Claude/GPT-4)

**Assumptions:**
- Input tokens: ~300 (prompt + context)
- Output tokens: ~100 (coherence score + justification)
- Claude 3 Sonnet: $0.003/1K input tokens, $0.015/1K output tokens

**Cost per call:**
```
Input:  300 tokens × $0.003/1K = $0.0009
Output: 100 tokens × $0.015/1K = $0.0015
Total: ~$0.0024 per call
```

**Daily budget:**
- 100 calls/hour × 24 hours = 2,400 calls/day
- 2,400 calls × $0.0024 = **$5.76/day** (well under $500 cap)

**Production volume:**
- 1 call per orchestrator cycle
- ~100 cycles/day (realistic)
- **~$0.24/day** in production

---

## Integration with CDS Engine

### Before (Current State)

```python
# C4: Causal Coherence (FINN+ Tier-2, not implemented yet)
C4 = compute_causal_coherence(0.0)  # Placeholder
```

### After (With FINN+ Tier-2)

```python
# C4: Causal Coherence (FINN+ Tier-2)
tier2_input = {
    'regime_label': regime_prediction.regime_label,
    'confidence': regime_prediction.confidence,
    'features': latest_features,  # 7 z-scored indicators
    'price_df': price_df.tail(20)  # Recent price action
}

tier2_result = self.tier2_engine.compute_coherence(tier2_input)

C4 = tier2_result['coherence_score']  # 0.0–1.0
tier2_summary = tier2_result['summary']  # 3 sentences
tier2_cost = tier2_result['cost_usd']  # ADR-012 tracking
```

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| LLM API outage | HIGH | Fallback to C4 = 0.5 (neutral coherence) |
| Cost overrun | MEDIUM | Rate limiting + daily budget cap |
| Low coherence scores | LOW | Alert + manual review |
| Prompt injection | LOW | Input sanitization + validation |
| Response parsing errors | MEDIUM | Retry with stricter prompt |

---

## Testing Strategy

### Unit Tests

1. **Prompt Generation**
   - Test template formatting
   - Test with BEAR/NEUTRAL/BULL regimes
   - Test with edge case z-scores

2. **Response Parsing**
   - Test valid responses
   - Test malformed responses
   - Test out-of-bounds coherence scores

3. **Cost Tracking**
   - Verify cost calculation
   - Test budget cap enforcement
   - Test rate limiting

### Integration Tests

1. **End-to-End Pipeline**
   - FINN+ → Tier-2 → CDS Engine
   - Verify C4 propagates to CDS value
   - Verify cost tracking

2. **Mock LLM Responses**
   - Test with synthetic responses
   - Test error handling
   - Test timeout handling

---

## Success Criteria

**C4 Implementation Complete When:**

1. ✅ FINN+ Tier-2 engine functional
2. ✅ LLM API integrated (Claude/GPT-4)
3. ✅ Coherence score ∈ [0.0, 1.0] validated
4. ✅ 3-sentence summaries generated
5. ✅ Cost tracking operational (ADR-012)
6. ✅ Rate limiting enforced (100/hour)
7. ✅ CDS Engine receives C4 component
8. ✅ Unit tests pass (100%)
9. ✅ Integration tests pass
10. ✅ G3 audit requirement satisfied: "FINN handles dissonance"

---

## Timeline

**Week 3 (Current):**
- ⏳ Planning document (this document)
- ⏳ Prompt engineering finalization
- ⏳ Cost estimation validation

**Week 4:**
- 🔜 Implement FINN+ Tier-2 engine
- 🔜 LLM API integration
- 🔜 Unit tests
- 🔜 Integration with CDS Engine

**Week 5:**
- 🔜 Production testing
- 🔜 Cost monitoring
- 🔜 G3 audit preparation

---

## Conclusion

**C4 (Causal Coherence) is critical for:**
1. Completing CDS Engine to 100% capacity (currently 80%)
2. Fulfilling FINN+ Tier-2 mandate
3. Satisfying G3 VEGA audit requirement: "Prove FINN handles dissonance"
4. Demonstrating causal reasoning capability

**Implementation is feasible:**
- Cost: ~$0.24/day in production (well under budget)
- Technical complexity: Moderate (prompt engineering + API integration)
- Timeline: 1-2 weeks to production-ready

**Recommendation:** Proceed with implementation in Week 4.

---

**Authority:** LARS Directive 5.1 (Priority 2: Governance Formalization)
**Status:** READY FOR IMPLEMENTATION
**Next Step:** Implement `finn_tier2_engine.py`

---

**END OF C4 IMPLEMENTATION PLAN**
