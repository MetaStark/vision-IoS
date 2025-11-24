# FINN TIER-2 ALPHA MANDATE v1.0 (REGISTERED)

**Classification:** Canonical Agent Contract
**Status:** REGISTERED & ACTIVE
**Authority:** LARS – Chief Strategy Officer
**Date:** 2025-11-24
**Reference:** HC-LARS-PHASE2-ACTIVATION-20251124
**Contract Hash:** `sha256(FINN_TIER2_ALPHA_MANDATE_v1.0)`

---

## 1. MANDATE REGISTRATION

**Agent:** FINN
**Contract Version:** v1.0
**Contract Type:** Tier-2 Alpha Mandate
**Approval Gate:** G2-approved
**Registration Location:** `fhq_governance.agent_contracts`

**Registered by:** LARS (Chief Strategy Officer)
**Governance Transition:** G3_CLOSED → PHASE_2_ACTIVE
**Effective Date:** 2025-11-24T08:30:00Z

---

## 2. AUTHORITATIVE CONTRACT DEFINITION

**Purpose:** Canonical contract for analytical intelligence, CDS production, relevance scoring, and conflict summaries.

### 2.1 Agent Metadata

- **Agent ID:** `finn`
- **Status:** Active (G2-approved)
- **Authority:** CEO Directive, ADR-001, ADR-007, ADR-010, ADR-012
- **Tier Restrictions:**
  - **Tier-2 LLM:** Synthesis only (conflict summaries)
  - **Tier-4 Python:** All metrics computation (CDS, Relevance)
- **Cost Ceiling:** $0.05 per Tier-2 Conflict Summary (ADR-012)

---

## 3. STRATEGIC CONSTRAINTS (BINDING)

**FINN is subject to the following binding constraints:**

1. ✅ **Function Limit:** Restricted to exactly **3 canonical MVA functions** (defined below)
2. ✅ **LLM Usage:** Capped and bounded by evidentiary bundles (no unbounded generation)
3. ✅ **Mathematical Operations:** Tier-4 Python only (no LLM for calculations)
4. ✅ **Conflict Summary Format:** Exactly **3 sentences**, token-bounded
5. ✅ **Anti-Hallucination Controls:** Mandatory keyword validation (≥2 of 3 keywords from sources)
6. ✅ **ADR-012 Compliance:** All LLM outputs must satisfy economic tolerance rules

**Violations trigger ADR-009 suspension workflow.**

---

## 4. CANONICAL MVA CORE FUNCTIONS

### Function 1: Cognitive Dissonance Score (CDS)

**Tier:** Tier-4 Python (deterministic computation)

**Inputs:**
- `fhq_data.price_series` (OHLCV data)
- `fhq_finn.serper_events` (news/events data)

**Outputs:**
```json
{
  "ticker": "BTCUSD",
  "timestamp": "2025-11-24T08:00:00Z",
  "cds_score": 0.723,
  "cds_tier": "high"
}
```

**ADR-010 Compliance:**
- **Criticality Weight:** 1.0 (highest priority metric)
- **Tolerance:** Max ±0.01 drift from last signed score
- **Validation:** Must be signed before storage

**Algorithm:**
1. Fetch latest price data (last 24h OHLCV)
2. Fetch latest Serper events (last 24h news)
3. Compute semantic divergence between price action and news sentiment
4. Normalize to [0, 1] range
5. Classify into tier (low < 0.3, medium 0.3-0.65, high > 0.65)

---

### Function 2: Relevance Score

**Tier:** Tier-4 Python (deterministic computation)

**Inputs:**
- CDS output (from Function 1)
- HHMM regime-weight (market regime classification)

**Outputs:**
```json
{
  "ticker": "BTCUSD",
  "timestamp": "2025-11-24T08:00:00Z",
  "relevance_score": 0.812,
  "relevance_tier": "high",
  "regime_weight": 0.85
}
```

**ADR-010 Compliance:**
- **Criticality Weight:** 0.7
- **Tolerance:** `regime_weight` must match one of 5 canonical weights (0.25, 0.50, 0.75, 0.85, 1.0)
- **Validation:** Regime weight lookup must be deterministic

**Algorithm:**
1. Take CDS score as base
2. Lookup current market regime (HHMM: bull/bear/neutral/volatile/crisis)
3. Apply regime weight multiplier
4. Compute final relevance score
5. Classify into tier

**Canonical Regime Weights:**
- **Bull:** 1.0 (high relevance)
- **Volatile:** 0.85 (elevated relevance)
- **Neutral:** 0.75 (moderate relevance)
- **Bear:** 0.50 (reduced relevance)
- **Crisis:** 0.25 (low relevance, noise dominates)

---

### Function 3: Tier-2 Conflict Summary

**Tier:** Tier-2 LLM (OpenAI GPT-4 or equivalent)

**Trigger:** CDS ≥ 0.65 (high cognitive dissonance detected)

**Evidentiary Bundle (REQUIRED, must be hashed):**
```json
{
  "cds_score": 0.723,
  "top_3_events": [
    {
      "title": "Fed signals rate pause",
      "url": "https://...",
      "sentiment": "dovish",
      "source_hash": "sha256(...)",
      "text": "Full event text..."
    },
    {
      "title": "Bitcoin rallies despite warnings",
      "url": "https://...",
      "sentiment": "bullish",
      "source_hash": "sha256(...)",
      "text": "Full event text..."
    },
    {
      "title": "Regulatory concerns mount",
      "url": "https://...",
      "sentiment": "bearish",
      "source_hash": "sha256(...)",
      "text": "Full event text..."
    }
  ],
  "bundle_hash": "sha256(...)"
}
```

**Outputs:**
```json
{
  "summary": "Fed rate pause signals dovish stance while Bitcoin rallies to new highs despite regulatory headwinds. Market exhibits cognitive dissonance between policy expectations and price action. Conflict severity: HIGH (CDS 0.72).",
  "keywords": ["Fed", "rate pause", "Bitcoin", "rally", "regulatory"],
  "source_hashes": ["sha256(...)", "sha256(...)", "sha256(...)"],
  "signer_key_id": "uuid-of-finn-active-key"
}
```

**ADR-010 Compliance:**
- **Criticality Weight:** 0.9
- **Anti-Hallucination Rule:** Summary MUST contain ≥2 of 3 keywords from source events
- **Sentence Count:** Exactly 3 sentences (enforced by token limit)
- **Signature Requirement:** Ed25519 signed by FINN's ACTIVE key (ADR-008)

**LLM Prompt Structure:**
```
You are FINN, a financial intelligence agent.

Evidentiary Bundle Hash: {bundle_hash}

CDS Score: {cds_score} (HIGH COGNITIVE DISSONANCE)

Top 3 Events:
1. {event_1_title}: {event_1_text} (Sentiment: {sentiment_1})
2. {event_2_title}: {event_2_text} (Sentiment: {sentiment_2})
3. {event_3_title}: {event_3_text} (Sentiment: {sentiment_3})

Task: Generate a 3-sentence conflict summary.

Requirements:
- Sentence 1: Identify the primary conflict
- Sentence 2: Explain the divergence
- Sentence 3: State conflict severity with CDS score

Keywords to include (use ≥2): {extracted_keywords}

Max tokens: 150
Format: Exactly 3 sentences.
```

**Anti-Hallucination Validation:**
1. Extract keywords from top-3 events
2. Check that summary contains ≥2 of 3 keywords
3. Reject summary if validation fails
4. Log rejection to `fhq_meta.adr_audit_log`

---

## 5. ECONOMIC CONSTRAINTS (ADR-012)

**Per-Summary Costs:**
- LLM API call: ~$0.03 (GPT-4, 150 tokens)
- Embedding API (3 calls): ~$0.02
- **Total:** ≤ $0.05 per summary

**Daily Limits:**
- **Max Summaries:** 100 per day
- **Max Daily Cost:** $5.00
- **Trigger Limit:** Only when CDS ≥ 0.65

**Enforcement:**
- Cost tracking logged to `fhq_meta.cost_tracking`
- Automatic suspension if daily cap exceeded (ADR-009)
- VEGA weekly cost report required

---

## 6. COMPLIANCE REQUIREMENTS

**All FINN Tier-2 operations MUST:**

1. ✅ **Ed25519 Signature:** All outputs signed by FINN's active key
2. ✅ **Evidentiary Bundle Hashing:** SHA-256 hash of input bundle stored
3. ✅ **ADR-010 Tolerance Rules:** CDS drift ≤ 0.01, regime weights canonical
4. ✅ **ADR-012 Cost Ceilings:** Per-summary cost ≤ $0.05, daily cost ≤ $5.00
5. ✅ **VEGA Attestation:** All Tier-2 outputs require VEGA attestation for production use

**Failure to comply triggers:**
- ADR-009 suspension workflow (automatic)
- VEGA escalation to LARS
- Audit log entry in `fhq_meta.adr_audit_log`

---

## 7. INTER-AGENT DEPENDENCIES

**FINN depends on:**

| Agent | Dependency | Purpose |
|-------|-----------|---------|
| **LINE** | Price data ingestion | CDS computation requires OHLCV data |
| **STIG** | Validation layer | All FINN outputs validated by STIG before storage |
| **VEGA** | Attestation | Tier-2 summaries require VEGA attestation for production |

**FINN provides to:**

| Agent | Output | Purpose |
|-------|--------|---------|
| **STIG** | CDS + Relevance scores | Validation input for risk boundaries |
| **LINE** | Conflict summaries | Execution decision context |
| **VEGA** | All outputs | Attestation and reconciliation |

---

## 8. GOVERNANCE LIFECYCLE

**Contract Lifecycle:**

1. **Registration:** Registered in `fhq_governance.agent_contracts` (this document)
2. **Activation:** Active status, bound to FINN agent_id
3. **Operation:** FINN executes 3 canonical functions
4. **Attestation:** VEGA attests outputs weekly
5. **Review:** Monthly ADR compliance audit
6. **Renewal:** Contract renewal at v2.0 (after 6 months or Phase 3 activation)

**Suspension Triggers (ADR-009):**
- CDS drift > 0.01 for >10 consecutive outputs
- Daily cost exceeds $5.00
- Anti-hallucination validation fails >5 times per day
- VEGA attestation rejection rate > 10%

---

## 9. EVIDENCE & ATTESTATION

**Contract Registration Evidence:**
- **SQL Migration:** `04_DATABASE/MIGRATIONS/002_phase2_agent_contracts.sql`
- **Database Record:** `fhq_governance.agent_contracts` WHERE `agent_id='finn'`
- **Hash Chain:** HC-LARS-PHASE2-ACTIVATION-20251124
- **Change Log:** `fhq_governance.change_log` (Phase 2 activation entry)

**VEGA Attestation Required:**
- Weekly: VEGA attests FINN outputs for compliance
- Monthly: VEGA audits contract adherence
- Post-execution: VEGA certifies Phase 2 activation complete

---

## 10. REFERENCES

**Foundation ADRs:**
- ADR-001: System Charter (agent identity)
- ADR-002: Audit & Error Reconciliation
- ADR-007: Orchestrator Architecture
- ADR-008: Cryptographic Key Management
- ADR-009: Suspension Workflow
- ADR-010: Discrepancy Scoring Specification
- ADR-012: Economic Safety Architecture

**Related Governance Files:**
- `05_GOVERNANCE/FINN_TIER2_MANDATE.md` (canonical specification, G3-frozen)
- `05_GOVERNANCE/G2_LARS_GOVERNANCE_MATERIALS.md` (strategic approval)
- `04_DATABASE/MIGRATIONS/002_phase2_agent_contracts.sql` (registration SQL)

---

**Status:** REGISTERED & ACTIVE
**Registered by:** LARS – Chief Strategy Officer
**Date:** 2025-11-24T08:30:00Z
**Hash Chain:** HC-LARS-PHASE2-ACTIVATION-20251124
**Contract Version:** v1.0
**Next Review:** 2026-05-24 (6 months) or Phase 3 activation
