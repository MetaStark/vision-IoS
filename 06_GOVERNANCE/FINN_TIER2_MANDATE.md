# FINN TIER-2 MANDATE (Canonical Draft)

**Agent:** FINN (Financial Investments Neural Network)
**Tier:** Tier-2 LLM Access (OpenAI GPT-4 Turbo only per ADR-007)
**Authority Level:** 8 (Research Leadership)
**Compliance:** ADR-003 (Institutional Standards), ADR-007 (Provider Routing), ADR-008 (Ed25519 Signatures), ADR-010 (Discrepancy Scoring)

---

## 1. PURPOSE

Tier-2 laget skal konvertere deterministiske Tier-4-signaler (CDS, Relevance) til auditerbar Alpha-syntese i tråd med ADR-003, ADR-008 og ADR-010.

**Mission:**
- Transform deterministic Tier-4 signals into actionable alpha intelligence
- Maintain auditability through structured output contracts
- Enforce discrepancy scoring per ADR-010
- Sign all outputs with Ed25519 per ADR-008

---

## 2. INPUTS (Fixed Schema)

```python
tier4_inputs = {
    "cds_score": float,              # From cds_engine.calculate_cds()
    "relevance_score": float,        # From relevance_engine.calculate_relevance()
    "price_direction": enum("up", "down", "flat"),
    "narrative_direction": enum("pos", "neg", "neutral"),
    "volume_factor": float,
    "serper_terms": list[str]        # Event keywords that triggered relevance
}
```

**Input Constraints:**
- `cds_score`: Range [0.0, 1.0], tolerance ±0.01
- `relevance_score`: Range [0.0, 1.0], tolerance ±0.01
- `price_direction`: Must be one of {up, down, flat}
- `narrative_direction`: Must be one of {pos, neg, neutral}
- `volume_factor`: Non-negative float
- `serper_terms`: List of 1-10 keywords (no empty list allowed)

**Input Validation:**
- All numeric inputs must be validated against schema
- Missing fields trigger FAIL state (no inference)
- Out-of-range values trigger VEGA alert

---

## 3. OUTPUTS (Tier-2 Alpha Contract)

```python
tier2_outputs = {
    "conflict_summary": str,         # Max 3 sentences, deterministic template
    "alpha_direction": enum("risk_up", "risk_down", "uncertainty"),
    "discrepancy_metadata": {
        "cds_tolerance_match": bool,
        "term_similarity": float,
        "structure_valid": bool
    },
    "signature": ed25519_signature   # ADR-008 requirement
}
```

**Output Constraints:**
- `conflict_summary`: EXACTLY 3 sentences (hard limit), deterministic template
- `alpha_direction`: Must be one of {risk_up, risk_down, uncertainty}
- `discrepancy_metadata.term_similarity`: Range [0.0, 1.0]
- `signature`: Valid Ed25519 signature of SHA-256(tier4_inputs + tier2_outputs)

**Output Validation:**
- Sentence count verification (reject if ≠ 3)
- Signature verification (reject if invalid)
- Schema compliance check (reject if missing fields)

---

## 4. CONFLICT SUMMARY TEMPLATE

### Deterministisk Struktur (3 Setninger, Hard Limit)

**Template:**
```
Sentence 1 (Driver Setning): [Top 3 sentiment drivers, cross-checked with serper_terms]
Sentence 2 (Divergens Setning): [Explanation of CDS vs Relevance divergence]
Sentence 3 (Risk Setning): [Expected risk flow direction, NOT prediction]
```

**Example Output:**
```
Driver Setning: Fed rate hike signals (serper: "fed", "hike", "inflation") dominate sentiment with 0.85 relevance score aligned to positive narrative direction.

Divergens Setning: CDS score (0.42) diverges from relevance (0.85) due to credit spread compression despite elevated macro uncertainty.

Risk Setning: Risk flow direction indicates risk_up as narrative momentum outweighs credit deterioration signals.
```

### **Krav (Non-Negotiable):**
1. **Ingen modalverb** (should, could, would, may, might) - BANNED
2. **Ingen fremtidsforutsigelser** (will, going to, expected to happen) - BANNED
3. **Kun syntese** (present-tense factual statements only)
4. **EXACTLY 3 sentences** - No more, no less

**Violation Handling:**
- If output contains modal verbs → REJECT, log to `vega.llm_violation_events`
- If output ≠ 3 sentences → REJECT, log to `vega.llm_violation_events`
- If output contains future predictions → REJECT, log to `vega.llm_violation_events`

---

## 5. DISCREPANCY CONTRACTS (ADR-010-Aligned)

```yaml
discrepancy_contracts:
  cds_score:
    weight: 1.0
    tolerance: 0.01  # ±1%
    description: "CDS score must match within 1% absolute error"

  relevance_score:
    weight: 1.0
    tolerance: 0.01  # ±1%
    description: "Relevance score must match within 1% absolute error"

  conflict_summary:
    weight: 0.9
    semantic_similarity_min: 0.65
    required_keyword_count: 1  # At least 1 serper_term must appear
    description: "Summary must have ≥65% semantic similarity and include ≥1 keyword"

  fields:
    - price_direction:
        weight: 0.8
        tolerance: "exact"
    - narrative_direction:
        weight: 0.8
        tolerance: "exact"
    - volume_factor:
        weight: 0.6
        tolerance: 0.05  # ±5%

validation:
  agent_vs_canonical: strict
  reconciliation_frequency: "per-execution"
  vega_escalation_threshold: 0.10  # Trigger suspension request if discrepancy > 0.10
```

### **Discrepancy Score Calculation (ADR-010 Formula):**

```python
discrepancy_score = Σ(weight_i × δ_i) / Σ(weight_i)

where:
  δ_i = 0 if field matches within tolerance
  δ_i = 1 if mismatch

Classification:
  0.00 – 0.05: NORMAL (VEGA certifies, proceed)
  0.05 – 0.10: WARNING (log & monitor)
  > 0.10:      CATASTROPHIC (trigger VEGA suspension request per ADR-009)
```

### **Validation Responsibilities:**

**STIG validates:**
- Numerical tolerances (cds_score, relevance_score, volume_factor)
- Field types (price_direction, narrative_direction enums)
- Schema compliance

**VEGA validates:**
- Semantic similarity (conflict_summary ≥ 0.65)
- Keyword presence (≥1 serper_term in summary)
- Structure compliance (3 sentences, no modal verbs, no predictions)
- Ed25519 signature validity

---

## 6. STORAGE CONTRACT (vision_signals)

```sql
CREATE TABLE IF NOT EXISTS vision_signals.finn_tier2 (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Tier-4 Inputs (deterministic)
    cds_score NUMERIC(5,4) NOT NULL CHECK (cds_score BETWEEN 0.0 AND 1.0),
    relevance_score NUMERIC(5,4) NOT NULL CHECK (relevance_score BETWEEN 0.0 AND 1.0),
    price_direction VARCHAR(10) NOT NULL CHECK (price_direction IN ('up', 'down', 'flat')),
    narrative_direction VARCHAR(10) NOT NULL CHECK (narrative_direction IN ('pos', 'neg', 'neutral')),
    volume_factor NUMERIC(10,4) NOT NULL CHECK (volume_factor >= 0),
    serper_terms TEXT[] NOT NULL CHECK (array_length(serper_terms, 1) BETWEEN 1 AND 10),

    -- Tier-2 Outputs (alpha synthesis)
    conflict_summary TEXT NOT NULL,
    alpha_direction VARCHAR(20) NOT NULL CHECK (alpha_direction IN ('risk_up', 'risk_down', 'uncertainty')),

    -- Discrepancy Metadata (ADR-010)
    discrepancy_score NUMERIC(6,5) NOT NULL CHECK (discrepancy_score BETWEEN 0.0 AND 1.0),
    cds_tolerance_match BOOLEAN NOT NULL,
    term_similarity NUMERIC(4,3) NOT NULL CHECK (term_similarity BETWEEN 0.0 AND 1.0),
    structure_valid BOOLEAN NOT NULL,

    -- Audit Trail (ADR-008)
    evidence_bundle JSONB NOT NULL,
    hash_chain_id VARCHAR(100) NOT NULL,
    signature_id VARCHAR(200) NOT NULL,
    signature BYTEA NOT NULL,  -- Ed25519 signature

    -- Indexes
    INDEX idx_finn_tier2_created_at (created_at DESC),
    INDEX idx_finn_tier2_alpha_direction (alpha_direction),
    INDEX idx_finn_tier2_discrepancy_score (discrepancy_score)
);

COMMENT ON TABLE vision_signals.finn_tier2 IS 'FINN Tier-2 Alpha Synthesis Output (ADR-010 compliant)';
COMMENT ON COLUMN vision_signals.finn_tier2.conflict_summary IS 'EXACTLY 3 sentences, no modal verbs, no predictions';
COMMENT ON COLUMN vision_signals.finn_tier2.discrepancy_score IS 'ADR-010 discrepancy score (0.0-1.0), >0.10 triggers VEGA escalation';
COMMENT ON COLUMN vision_signals.finn_tier2.signature IS 'Ed25519 signature of SHA-256(tier4_inputs + tier2_outputs)';
```

### **Storage Validation Rules:**

1. **Sentence Count Constraint:**
   ```sql
   -- Trigger to enforce 3-sentence rule
   CREATE OR REPLACE FUNCTION validate_conflict_summary()
   RETURNS TRIGGER AS $$
   DECLARE
       sentence_count INTEGER;
   BEGIN
       sentence_count := array_length(regexp_split_to_array(NEW.conflict_summary, '\.\s+'), 1);
       IF sentence_count != 3 THEN
           RAISE EXCEPTION 'Conflict summary must have exactly 3 sentences, found %', sentence_count;
       END IF;
       RETURN NEW;
   END;
   $$ LANGUAGE plpgsql;

   CREATE TRIGGER enforce_3_sentences
   BEFORE INSERT OR UPDATE ON vision_signals.finn_tier2
   FOR EACH ROW EXECUTE FUNCTION validate_conflict_summary();
   ```

2. **Signature Verification:**
   ```sql
   -- Signature must be valid Ed25519 (32 bytes)
   ALTER TABLE vision_signals.finn_tier2
   ADD CONSTRAINT valid_ed25519_signature
   CHECK (octet_length(signature) = 64);  -- 32 bytes = 64 hex chars
   ```

---

## 7. PROVIDER TIERING

**LLM Provider:** OpenAI GPT-4 Turbo (per ADR-007 Tier Model)

**FINN = Tier-2 LLM Access:**
- **Provider:** OpenAI only (no Anthropic, no DeepSeek)
- **Model:** `gpt-4-turbo`
- **Fallback:** Anthropic Claude Haiku (if OpenAI unavailable)
- **Data Sharing:** NOT ALLOWED (per ADR-007 §4.5)

**Economic Safety Constraints (ADR-012):**
```yaml
rate_limits:
  calls_per_minute: 5
  calls_per_pipeline: 10
  daily_limit: 150

cost_limits:
  max_cost_per_call_usd: 0.04
  max_cost_per_task_usd: 0.50
  max_cost_per_day_usd: 1.00

execution_limits:
  max_llm_steps_per_task: 5
  max_total_latency_ms: 5000
  max_total_tokens_generated: 4096
  abort_on_overrun: true
```

**Violation Actions:**
- Rate limit exceeded → SWITCH_TO_STUB (use mock tier2_outputs)
- Cost limit exceeded → NOTIFY_VEGA (suspend if critical)
- Execution limit exceeded → ABORT_TASK (log to vega.llm_violation_events)

---

## 8. VEGA AUDIT RULES

### **Pre-Execution Validation (VEGA):**

1. **Verify Ed25519 Signature:**
   ```python
   def verify_tier2_signature(tier4_inputs, tier2_outputs, signature):
       message = sha256(json.dumps(tier4_inputs) + json.dumps(tier2_outputs))
       public_key = get_finn_public_key()  # From fhq_meta.agent_keys
       return ed25519.verify(signature, message, public_key)
   ```

2. **Measure Structure (3 Sentences):**
   ```python
   def validate_structure(conflict_summary):
       sentences = re.split(r'\.\s+', conflict_summary)
       if len(sentences) != 3:
           raise StructureViolation(f"Expected 3 sentences, found {len(sentences)}")

       # Check for banned modal verbs
       modal_verbs = ["should", "could", "would", "may", "might", "will", "going to"]
       for verb in modal_verbs:
           if verb in conflict_summary.lower():
               raise ModalVerbViolation(f"Banned modal verb detected: {verb}")

       return True
   ```

3. **Measure Semantic Similarity (≥0.65):**
   ```python
   def validate_semantic_similarity(conflict_summary, serper_terms):
       # Use sentence embeddings (e.g., OpenAI embeddings API)
       summary_embedding = get_embedding(conflict_summary)
       terms_embedding = get_embedding(" ".join(serper_terms))

       similarity = cosine_similarity(summary_embedding, terms_embedding)

       if similarity < 0.65:
           raise SemanticSimilarityViolation(f"Similarity {similarity} < 0.65 threshold")

       return similarity
   ```

4. **Check Tolerances Against CDS Baseline:**
   ```python
   def validate_tolerances(tier4_inputs, reconciled_inputs):
       discrepancy_score = calculate_adr010_score(tier4_inputs, reconciled_inputs)

       if discrepancy_score > 0.10:
           # Trigger VEGA suspension request per ADR-009
           create_suspension_request(
               agent_id="FINN",
               reason="CATASTROPHIC_DISCREPANCY",
               discrepancy_score=discrepancy_score,
               evidence={"tier4_inputs": tier4_inputs, "reconciled": reconciled_inputs}
           )

       return discrepancy_score
   ```

5. **Classify Deviations (ADR-010):**
   ```python
   def classify_deviation(discrepancy_score):
       if discrepancy_score <= 0.05:
           return "NORMAL"  # VEGA certifies, proceed
       elif discrepancy_score <= 0.10:
           return "WARNING"  # Log & monitor
       else:
           return "CATASTROPHIC"  # Trigger suspension request
   ```

### **Post-Execution Audit (VEGA):**

```sql
-- Log audit event to fhq_governance.governance_actions_log
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    agent_id,
    decision,
    metadata,
    hash_chain_id,
    signature,
    timestamp
) VALUES (
    'FINN_TIER2_AUDIT',
    'VEGA',
    'VERIFIED',  -- or 'BLOCKED' if violations found
    jsonb_build_object(
        'tier2_output_id', tier2_id,
        'discrepancy_score', discrepancy_score,
        'structure_valid', structure_valid,
        'semantic_similarity', term_similarity,
        'signature_valid', signature_valid,
        'classification', classification  -- NORMAL/WARNING/CATASTROPHIC
    ),
    'HC-VEGA-TIER2-' || tier2_id,
    vega_signature,
    NOW()
);
```

---

## 9. AGENT CONTRACT REGISTRATION

**After G4 (CEO Canonicalization):**

```sql
INSERT INTO fhq_governance.agent_contracts (
    agent_id,
    contract_type,
    contract_status,
    mandate_scope,
    authority_boundaries,
    communication_protocols,
    escalation_rules,
    performance_criteria,
    compliance_requirements,
    change_proposal_id,
    approved_by,
    approved_at,
    effective_from,
    audit_log_id,
    signature_id,
    metadata
) VALUES (
    'FINN',
    'MANDATE',
    'ACTIVE',
    'Tier-2 Alpha Synthesis: Convert deterministic Tier-4 signals (CDS, Relevance) to auditable alpha intelligence with ADR-010 discrepancy scoring and ADR-008 Ed25519 signatures',
    jsonb_build_object(
        'can_execute', ARRAY['tier2_alpha_synthesis', 'conflict_summary_generation', 'discrepancy_scoring'],
        'cannot_execute', ARRAY['production_trading', 'database_writes', 'constitutional_changes'],
        'escalation_to', ARRAY['LARS', 'VEGA'],
        'llm_provider', 'OPENAI',
        'tier', 'TIER2',
        'max_cost_per_day_usd', 1.00
    ),
    jsonb_build_object(
        'input_schema', 'tier4_inputs (cds_score, relevance_score, price_direction, narrative_direction, volume_factor, serper_terms)',
        'output_schema', 'tier2_outputs (conflict_summary, alpha_direction, discrepancy_metadata, signature)',
        'storage_table', 'vision_signals.finn_tier2',
        'validation_owner', 'VEGA'
    ),
    jsonb_build_object(
        'discrepancy_threshold', 0.10,
        'escalation_action', 'VEGA_SUSPENSION_REQUEST',
        'vega_audit_required', true,
        'stig_validation_required', true
    ),
    jsonb_build_object(
        'conflict_summary', '3 sentences EXACTLY, no modal verbs, no predictions',
        'semantic_similarity', '≥0.65 required',
        'discrepancy_score', '≤0.10 for NORMAL classification',
        'signature', 'Ed25519 required per ADR-008'
    ),
    ARRAY['ADR-003', 'ADR-007', 'ADR-008', 'ADR-010', 'ADR-012'],
    'G0-2025-11-23-LINE-MANDATE',
    'CEO',
    NOW(),
    NOW(),
    (SELECT audit_id FROM fhq_meta.adr_audit_log WHERE change_proposal_id = 'G0-2025-11-23-LINE-MANDATE' AND gate_stage = 'G4'),
    'GENESIS_SIGNATURE_FINN_TIER2_' || MD5(NOW()::TEXT),
    jsonb_build_object(
        'canonical_draft', 'FINN_TIER2_MANDATE.md',
        'approved_by_ceo', true,
        'g1_pass', true,
        'g2_pass', true,
        'g3_verify', true,
        'g4_canonicalized', true
    )
);
```

---

## 10. IMPLEMENTATION CHECKLIST (POST-G4)

**CODE Team Responsibilities:**

- [ ] Create `vision_signals.finn_tier2` table with structure validation trigger
- [ ] Implement tier2_alpha_synthesis() function in `05_ORCHESTRATOR/finn_tier2.py`
- [ ] Integrate with cds_engine and relevance_engine outputs
- [ ] Implement 3-sentence template generator
- [ ] Add modal verb and prediction detection
- [ ] Implement semantic similarity validation (OpenAI embeddings API)
- [ ] Integrate Ed25519 signing per ADR-008
- [ ] Add discrepancy score calculation (ADR-010 formula)
- [ ] Connect to vega.llm_violation_events for audit
- [ ] Register in fhq_governance.task_registry as FINN_FUNCTION
- [ ] Add to orchestrator cycle (hourly execution)
- [ ] Implement STUB mode for rate limit violations
- [ ] Create VEGA audit dashboard queries

**STIG Validation:**
- [ ] Execute schema creation (vision_signals.finn_tier2)
- [ ] Verify numeric tolerance constraints
- [ ] Test 3-sentence validation trigger
- [ ] Verify Ed25519 signature constraint (64 bytes)

**VEGA Audit:**
- [ ] Implement pre-execution signature verification
- [ ] Implement semantic similarity measurement
- [ ] Implement structure compliance checks
- [ ] Configure CATASTROPHIC escalation (discrepancy > 0.10)
- [ ] Enable continuous monitoring of finn_tier2 outputs

---

## 11. COMPLIANCE SUMMARY

**ADR-003 (Institutional Standards):**
✅ Structured output contracts (tier4_inputs → tier2_outputs)
✅ Auditability through evidence_bundle and signature

**ADR-007 (Provider Routing):**
✅ FINN = Tier-2 LLM (OpenAI GPT-4 Turbo only)
✅ No data sharing allowed
✅ Fallback to Anthropic if OpenAI unavailable

**ADR-008 (Ed25519 Signatures):**
✅ All tier2_outputs signed with Ed25519
✅ Signature verification in VEGA audit
✅ 64-byte signature constraint enforced

**ADR-010 (Discrepancy Scoring):**
✅ Field-level weights defined (cds_score: 1.0, conflict_summary: 0.9)
✅ Tolerances specified (±0.01 for scores, ≥0.65 for semantic similarity)
✅ Discrepancy score calculation formula implemented
✅ Classification thresholds: NORMAL (≤0.05), WARNING (≤0.10), CATASTROPHIC (>0.10)

**ADR-012 (Economic Safety):**
✅ Rate limits: 5 calls/min, 150 calls/day
✅ Cost limits: $0.04/call, $1.00/day
✅ Execution limits: 5 LLM steps MAX, 5000ms latency, 4096 tokens

---

## 12. CANONICAL STATUS

**Document Status:** CANONICAL DRAFT
**Approval Path:** G2 (LARS) → G3 (VEGA) → G4 (CEO)
**Registration Target:** `fhq_governance.agent_contracts`
**Effective After:** G4 Canonicalization (CEO approval)

**Signed:**
LARS (Logic, Analytics & Research Strategy)
Date: [Pending G2 approval]
Hash Chain ID: HC-LARS-FINN-TIER2-MANDATE

---

**End of FINN TIER-2 MANDATE (Canonical Draft)**
