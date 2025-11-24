# FINN TIER-2 MANDATE (CANONICAL)

**Classification:** Tier-2 Governance Specification
**Status:** FROZEN – G3 Audit Scope
**Authority:** LARS – Chief Strategy Officer
**Reference:** HC-LARS-ADR004-G2-PASS-20251124

---

## 1. Scope Definition

**FINN Tier-2** is the canonical conflict summarization layer that converts Tier-4 analytical inputs into deterministic, signed, actionable intelligence.

### 1.1 Mandatory Inputs (Tier-4)

1. **CDS Score** (Contextual Discrepancy Score)
   - Range: [0.0, 1.0]
   - Source: `cds_engine`
   - Purpose: Quantify semantic drift between expected and observed state

2. **Relevance Score**
   - Range: [0.0, 1.0]
   - Source: `relevance_engine`
   - Purpose: Measure signal strength vs noise floor

### 1.2 Mandatory Output Structure

**Deterministic 3-Sentence Format:**

```
Sentence 1: Conflict identification (what diverged)
Sentence 2: Quantitative assessment (CDS + Relevance scores)
Sentence 3: Recommended action (deterministic based on ADR-010 thresholds)
```

### 1.3 Cryptographic Requirements (ADR-008)

- **Signature Algorithm:** Ed25519
- **Key Source:** FINN agent private key (managed via ADR-008)
- **Signature Scope:** Full 3-sentence summary + metadata
- **Verification:** Public key validation required before database storage

---

## 2. Quality Thresholds (ADR-010)

### 2.1 Semantic Similarity Requirement

**Minimum threshold:** ≥ 0.65

- Measured between FINN output and canonical reference patterns
- Enforced via embedding-based similarity scoring
- Violations trigger ADR-009 suspension workflow

### 2.2 Tolerance Layers

Per **ADR-010 – Discrepancy Scoring Specification:**

| Metric | Green Zone | Yellow Zone | Red Zone |
|--------|-----------|-------------|----------|
| CDS Score | < 0.30 | 0.30 - 0.70 | > 0.70 |
| Relevance | > 0.70 | 0.40 - 0.70 | < 0.40 |
| Semantic Similarity | ≥ 0.65 | 0.50 - 0.65 | < 0.50 |

**Action Matrix:**
- **Green:** Automatic approval
- **Yellow:** VEGA review required
- **Red:** Automatic suspension (ADR-009)

---

## 3. Database Contract

### 3.1 Storage Schema

**Table:** `vision_signals.finn_tier2`

**Mandatory Columns:**
```sql
id                  SERIAL PRIMARY KEY
conflict_summary    TEXT NOT NULL  -- 3-sentence output
cds_score          NUMERIC(4,3) CHECK (cds_score BETWEEN 0 AND 1)
relevance_score    NUMERIC(4,3) CHECK (relevance_score BETWEEN 0 AND 1)
semantic_similarity NUMERIC(4,3) CHECK (semantic_similarity >= 0.65)
signature          TEXT NOT NULL  -- Ed25519 base64-encoded
public_key         TEXT NOT NULL  -- FINN's Ed25519 public key
timestamp          TIMESTAMPTZ DEFAULT NOW()
hash_chain_id      TEXT NOT NULL  -- ADR-002 lineage tracking
```

### 3.2 Insertion Requirements

**Pre-insertion validation:**
1. Ed25519 signature verification passes
2. Semantic similarity ≥ 0.65
3. CDS and Relevance scores in valid range [0, 1]
4. 3-sentence structure validated
5. Hash chain lineage verified

**Rejection behavior:**
- Invalid signatures → reject with error code
- Failed semantic threshold → trigger ADR-009 suspension
- Schema violations → log to `fhq_meta.adr_audit_log`

---

## 4. Economic Safety (ADR-012)

### 4.1 Rate Limits

**FINN Tier-2 execution limits:**
- Maximum 100 summaries per hour
- Cost ceiling: $0.50 per summary (LLM + embedding costs)
- Daily budget cap: $500

### 4.2 Cost Tracking

All FINN Tier-2 operations log to `fhq_meta.cost_tracking`:
- Input token count
- Output token count
- Embedding API calls
- Total USD cost

**Suspension trigger:** If daily budget exceeded, ADR-009 auto-suspension activates.

---

## 5. G3 Audit Requirements

VEGA must verify the following for G3 PASS:

1. ✅ Discrepancy contracts match ADR-010 specification
2. ✅ Ed25519 signature enforcement functional (sign → verify → reject invalid)
3. ✅ Deterministic 3-sentence structure validated
4. ✅ Semantic similarity threshold ≥ 0.65 enforced
5. ✅ Tolerance layer correctness (Green/Yellow/Red zones)
6. ✅ Economic safety compliance (rate limits + cost caps)
7. ✅ Evidence bundle formation (all operations logged to `fhq_meta`)
8. ✅ Governance lineage integrity (ADR-002 hash chain)

---

## 6. Exclusions (Out of Scope for G3)

The following are **NOT** part of FINN Tier-2 mandate:

- ❌ Tier-1 execution (actionable trades)
- ❌ Tier-3 meta-analysis
- ❌ FINN Phase 2 features (future roadmap)
- ❌ Integration with STIG/LINE agents
- ❌ Live production deployment

**G3 audit scope is limited to FINN Tier-2 only.**

---

## 7. Governance Compliance

This mandate is frozen and canonical for G3 audit.

**References:**
- ADR-002: Audit & Error Reconciliation Charter
- ADR-003: Institutional Standards Framework
- ADR-007: Orchestrator Architecture
- ADR-008: Cryptographic Key Management
- ADR-009: Suspension Workflow
- ADR-010: Discrepancy Scoring Specification
- ADR-012: Economic Safety Architecture

**Authorized by:** LARS – CSO
**Hash Chain:** HC-LARS-ADR004-G2-PASS-20251124
**Status:** FROZEN – No modifications permitted until G3 PASS
