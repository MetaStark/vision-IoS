# META-ANALYSE: CEO-DIR-2026-PRE-TIER-GRADIENT-001

**Analysert:** 2026-01-25 20:45 Oslo
**Analysert av:** STIG (EC-003)
**Status:** GAP-ANALYSE MED FORBEDRINGSFORSLAG
**Samlet Dekning:** 62%

---

## 1. DATABASE-VERIFISERT STATUS

### 1.1 Eksisterende Infrastruktur (BEKREFTET)

| Komponent | Status | Database-Bevis |
|-----------|--------|----------------|
| `fhq_learning.hypothesis_canon` | ✅ EXISTS | 55 kolonner, inkl. `causal_graph_depth`, `generator_id`, `semantic_hash` |
| `fhq_governance.defcon_state` | ✅ EXISTS | DEFCON=GREEN (current), validerer Oxygen Rule |
| `fhq_learning.generator_registry` | ✅ EXISTS | `owner_ec` felt for Anti-Echo validering |
| `fhq_learning.hypothesis_provenance` | ✅ EXISTS | K-lineage støtte med `input_hash` |
| `fhq_governance.fortress_anchors` | ✅ EXISTS | ADR-011 hash-chain infrastruktur |
| `fhq_governance.brier_score_ledger` | ✅ EXISTS | For VEGA correlation audit |

### 1.2 Felter som MÅ LEGGES TIL (Migrering Påkrevd)

```sql
-- MANGLENDE FELTER i hypothesis_canon:
pre_tier_score           -- MANGLER
evidence_density_score   -- MANGLER
data_freshness_score     -- MANGLER
causal_depth_score       -- MANGLER (NB: causal_graph_depth EXISTS som INTEGER)
draft_age_hours          -- MANGLER (kan beregnes fra created_at)
draft_decay_penalty      -- MANGLER
pre_tier_score_version   -- MANGLER
pre_tier_score_status    -- MANGLER (enum må opprettes)
pre_tier_scored_by       -- MANGLER
pre_tier_scored_at       -- MANGLER
```

### 1.3 Eksisterende Hypothesis Status-verdier

```
hypothesis_canon.status: DRAFT (12), FALSIFIED (32)
```

### 1.4 Nåværende DEFCON State

```sql
SELECT defcon_level, is_current, triggered_at, trigger_reason
FROM fhq_governance.defcon_state WHERE is_current = true;

-- Resultat:
-- defcon_level: GREEN
-- triggered_at: 2025-12-11
-- trigger_reason: G4 Activation Order - Sovereign Autonomy Release
```

---

## 2. GAP-ANALYSE & FORBEDRINGSFORSLAG

### GAP-1: `causal_depth_score` vs `causal_graph_depth` KONFLIKT

**Problem:** Direktivet spesifiserer `causal_depth_score` som numeric(5,2) 0-100, men `causal_graph_depth` eksisterer allerede som INTEGER (1-N).

**Forslag A (Anbefalt):** Behold `causal_graph_depth` som input, lag beregnet felt:
```sql
causal_depth_score = LEAST(causal_graph_depth * 25.0, 100.0)  -- depth 4+ = 100
```

**Forslag B:** Rename eksisterende felt og migrer data.

**CEO-BESLUTNING PÅKREVD:** Velg A eller B.

---

### GAP-2: Oxygen Rule DEFCON-State Query Ambiguitet

**Problem:** Direktivet sier "DEFCON state must be pulled from fhq_governance.defcon_state (Canonical)" men spesifiserer ikke hvilken kolonne definerer GREEN.

**Database-Bevis:**
```sql
SELECT defcon_level FROM fhq_governance.defcon_state WHERE is_current = true;
-- Result: 'GREEN'
```

**Forslag:** Presiser i direktivet:
```
Oxygen Rule ACTIVE WHEN:
  SELECT 1 FROM fhq_governance.defcon_state
  WHERE is_current = true AND defcon_level = 'GREEN'
```

**Status:** MINOR - kan implementeres med antagelse.

---

### GAP-3: Scoring-Orchestrator IKKE DEFINERT

**Problem:** Direktivet refererer til "Scoring-Orchestrator" som eier av `pre_tier_score_status`, men:
- Ingen orchestrator med dette navn i `fhq_governance.orchestrator_authority`
- Eksisterende orchestrators er for data-ingest (Bulletproof-*), ikke scoring

**Eksisterende orchestrators:**
```
- FHQ-IoS001-Bulletproof-CRYPTO
- FHQ-IoS001-Bulletproof-EQUITY
- FHQ-IoS001-Bulletproof-FX
```

**Forslag:**
1. Opprett ny rad i `orchestrator_authority`:
```sql
INSERT INTO fhq_governance.orchestrator_authority (
  orchestrator_id, orchestrator_name, scope, constitutional_authority, enabled
) VALUES (
  'FHQ-PreTier-Scoring-Orchestrator',
  'Pre-Tier Gradient Scoring Engine',
  'Hypothesis pre-tier scoring',
  true, true
);
```

2. Alternativt: Definer scoring-ansvar i EC-registry (VEGA EC-004?)

**CEO-BESLUTNING PÅKREVD:** Hvem eier scoring-orchestrator?

---

### GAP-4: Cross-Agent Entropy Beregning USPESIFISERT

**Problem:** Formelen inkluderer `agreement_score = 100 - cross_agent_entropy`, men:
- Hvordan beregnes entropy?
- Hvilke inputs?
- Hvor lagres validator-scores før aggregering?

**Forslag - Ny tabell:**
```sql
CREATE TABLE fhq_learning.pre_tier_validator_scores (
  validation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  hypothesis_id UUID REFERENCES hypothesis_canon(canon_id),
  validator_ec TEXT NOT NULL,  -- EC-ID for validator agent
  evidence_density_estimate NUMERIC(5,2),
  causal_depth_estimate NUMERIC(5,2),
  data_freshness_estimate NUMERIC(5,2),
  validation_timestamp TIMESTAMPTZ DEFAULT NOW(),
  validation_hash TEXT  -- For ADR-011
);
```

**Entropy-formel forslag:**
```sql
cross_agent_entropy = (STDDEV(scores) / NULLIF(AVG(scores), 0)) * 100
-- Coefficient of Variation, normalized
agreement_score = 100 - LEAST(cross_agent_entropy, 100)
```

**CEO-BESLUTNING PÅKREVD:** Godkjenn entropy-definisjon.

---

### GAP-5: Anti-Echo Rule Enforcement Mechanism

**Problem:** Direktivet krever at "generator has zero authority over pre_tier_score_status", men:
- Ingen database-constraint som håndhever dette
- `generator_id` og `created_by` er ofte identiske

**Database-Bevis (VIOLATION-eksempel):**
```sql
SELECT generator_id, created_by FROM fhq_learning.hypothesis_canon LIMIT 5;
-- FINN-E, FINN-E  <-- SAME AGENT = VIOLATION RISK
-- GN-S, GN-S      <-- SAME AGENT = VIOLATION RISK
```

**Forslag - Database-level enforcement:**
```sql
-- CHECK constraint på scoring
ALTER TABLE fhq_learning.hypothesis_canon
ADD CONSTRAINT chk_anti_echo_rule
CHECK (
  pre_tier_scored_by IS NULL
  OR NOT (pre_tier_scored_by::jsonb ? generator_id)
);
```

Plus VEGA validation rule:
```sql
INSERT INTO fhq_governance.vega_validation_rules (
  rule_name, rule_type, applies_to, condition_sql, failure_action,
  constitutional_basis, is_active
) VALUES (
  'Anti-Echo Pre-Tier Scoring',
  'HARD_CONSTRAINT',
  ARRAY['fhq_learning.hypothesis_canon'],
  'SELECT 1 FROM fhq_learning.hypothesis_canon WHERE pre_tier_scored_by::jsonb ? generator_id',
  'BLOCK',
  'CEO-DIR-2026-PRE-TIER-GRADIENT-001 Section 4.1',
  true
);
```

**Status:** KRITISK - Må implementeres for epistemic integrity.

---

### GAP-6: K-Lineage Hash Vector INKOMPLETT

**Problem:** Direktivet spesifiserer birth-hash skal inkludere `[score_inputs, version, scorers, status]`, men:
- `hypothesis_provenance.input_hash` eksisterer for generering
- Scoring-hash trenger egen kolonne

**Forslag:**
```sql
ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN pre_tier_birth_hash TEXT,
ADD COLUMN pre_tier_hash_verified BOOLEAN DEFAULT FALSE;
```

Hash-beregning:
```sql
pre_tier_birth_hash = SHA256(
  evidence_density_score || '|' ||
  causal_depth_score || '|' ||
  data_freshness_score || '|' ||
  pre_tier_score_version || '|' ||
  pre_tier_scored_by::text || '|' ||
  pre_tier_score_status
)
```

---

### GAP-7: Reasoning-Delta Audit MANGLER STRUKTUR

**Problem:** VEGA skal produsere "weekly correlation report: Score_at_Birth vs. Time_to_Falsification", men:
- Ingen tabell for å lagre denne korrelasjonen
- Threshold r < 0.3 er statistisk, men sample-size ikke spesifisert

**Forslag:**
```sql
CREATE TABLE fhq_governance.pre_tier_calibration_audit (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_week DATE NOT NULL,
  sample_size INTEGER NOT NULL,
  pearson_r NUMERIC(5,4),
  spearman_rho NUMERIC(5,4),
  flag_for_review BOOLEAN DEFAULT FALSE,
  ceo_reviewed_at TIMESTAMPTZ,
  weight_adjustment_proposal JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Minimum sample-size forslag:** n >= 30 for statistisk validitet.

---

## 3. FORMULA-VALIDERING

### Direktivets Formula:
```
pre_tier_score = CLAMP(
  (evidence_density_score * 0.3) +
  (causal_depth_score * 0.4) +
  (data_freshness_score * 0.2) +
  (agreement_score * 0.1) -
  (draft_decay_penalty),
  0, 100
)
```

### Vekter (SUM = 1.0): KORREKT
- Evidence: 0.3
- Causal: 0.4
- Freshness: 0.2
- Agreement: 0.1
- **Total: 1.0**

### Decay Penalty Interaksjon: KORREKT
- Best case: 100 - 0 = 100
- Worst case: 0 - 25 = -25, CLAMP -> 0

**Status:** Formula er matematisk sound.

---

## 4. ENUM-TYPE FORSLAG

```sql
CREATE TYPE fhq_learning.pre_tier_score_status_enum AS ENUM (
  'PENDING',           -- Ikke scoret ennå
  'SCORING',           -- Under validering
  'SCORED',            -- Fullført scoring
  'FAIL_CLOSED',       -- Validering feilet (score = 0)
  'STALE',             -- Score utdatert (re-score påkrevd)
  'OVERRIDE_CEO'       -- CEO-overstyrt score
);
```

---

## 5. OPPSUMMERING: ER DIREKTIVET DEKKENDE?

| Aspekt | Vurdering | Handling |
|--------|-----------|----------|
| Schema-spesifikasjon | 85% | Mangler entropy-definisjon, validator-tabell |
| Formula | 100% | Matematisk korrekt |
| ADR-011 Integration | 70% | Mangler eksplisitt hash-kolonne |
| Anti-Echo Enforcement | 40% | Ingen database-constraint |
| DEFCON Integration | 90% | Minor clarification needed |
| Audit Infrastructure | 50% | Mangler calibration-audit tabell |
| Orchestrator Definition | 0% | Ikke spesifisert hvem som eier |

### SAMLET: 62% DEKKENDE

**Anbefaling:** Direktivet trenger amendments før G1 kan starte.

---

## 6. FORESLÅTTE AMENDMENTS

### Amendment A: Scoring-Orchestrator Definition
Legg til seksjon 4.3:
```
4.3 Scoring-Orchestrator Authority:
The Scoring-Orchestrator function is delegated to VEGA (EC-004) with the following constraints:
- VEGA coordinates but does not score
- Minimum 2 Tier-2 agents (FINN-E, GN-S, or equivalent) must score
- VEGA aggregates and owns status-transition authority
```

### Amendment B: Cross-Agent Entropy Formula
Legg til seksjon 4.2.1:
```
4.2.1 Entropy Calculation:
cross_agent_entropy = (STDDEV(all_validator_scores) / NULLIF(AVG(all_validator_scores), 0)) * 100
-- Capped at 100. NULL-safe.
```

### Amendment C: Minimum Sample Size for Calibration Audit
Legg til seksjon 6, bullet 3:
```
- Reasoning-Delta Audit is ONLY valid when sample_size >= 30 falsified hypotheses
- Below threshold: report as "INSUFFICIENT_DATA", no CEO escalation
```

---

## 7. CEO-BESLUTNINGER PÅKREVD

| # | Beslutning | Alternativer |
|---|------------|--------------|
| 1 | causal_depth_score behandling | A: Beregnet fra eksisterende / B: Nytt felt |
| 2 | Scoring-Orchestrator eierskap | VEGA (anbefalt) / Ny agent / Annet |
| 3 | Entropy-formel | CV-basert (anbefalt) / Annet |
| 4 | Minimum sample-size for audit | n=30 (anbefalt) / Annet |
| 5 | Nye tabeller | Godkjenn: pre_tier_validator_scores, pre_tier_calibration_audit |

---

## 8. KOMPLETT MIGRERINGS-SQL (DRAFT)

Når CEO godkjenner amendments, vil følgende migrering genereres:

```sql
-- Migration: XXX_pre_tier_gradient_schema.sql
-- Directive: CEO-DIR-2026-PRE-TIER-GRADIENT-001
-- Status: DRAFT - AWAITING CEO APPROVAL

-- 1. Create enum type
CREATE TYPE fhq_learning.pre_tier_score_status_enum AS ENUM (
  'PENDING', 'SCORING', 'SCORED', 'FAIL_CLOSED', 'STALE', 'OVERRIDE_CEO'
);

-- 2. Add columns to hypothesis_canon
ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN pre_tier_score NUMERIC(5,2) CHECK (pre_tier_score >= 0 AND pre_tier_score <= 100),
ADD COLUMN evidence_density_score NUMERIC(5,2) CHECK (evidence_density_score >= 0 AND evidence_density_score <= 100),
ADD COLUMN data_freshness_score NUMERIC(5,2) CHECK (data_freshness_score >= 0 AND data_freshness_score <= 100),
ADD COLUMN causal_depth_score NUMERIC(5,2) CHECK (causal_depth_score >= 0 AND causal_depth_score <= 100),
ADD COLUMN draft_age_hours NUMERIC(10,2),
ADD COLUMN draft_decay_penalty NUMERIC(5,2) CHECK (draft_decay_penalty >= 0 AND draft_decay_penalty <= 25),
ADD COLUMN pre_tier_score_version VARCHAR(10) DEFAULT '1.0.0',
ADD COLUMN pre_tier_score_status fhq_learning.pre_tier_score_status_enum DEFAULT 'PENDING',
ADD COLUMN pre_tier_scored_by JSONB,
ADD COLUMN pre_tier_scored_at TIMESTAMPTZ,
ADD COLUMN pre_tier_birth_hash TEXT,
ADD COLUMN pre_tier_hash_verified BOOLEAN DEFAULT FALSE;

-- 3. Create validator scores table
CREATE TABLE fhq_learning.pre_tier_validator_scores (
  validation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  hypothesis_id UUID REFERENCES fhq_learning.hypothesis_canon(canon_id),
  validator_ec TEXT NOT NULL,
  evidence_density_estimate NUMERIC(5,2),
  causal_depth_estimate NUMERIC(5,2),
  data_freshness_estimate NUMERIC(5,2),
  validation_timestamp TIMESTAMPTZ DEFAULT NOW(),
  validation_hash TEXT
);

-- 4. Create calibration audit table
CREATE TABLE fhq_governance.pre_tier_calibration_audit (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_week DATE NOT NULL,
  sample_size INTEGER NOT NULL,
  pearson_r NUMERIC(5,4),
  spearman_rho NUMERIC(5,4),
  flag_for_review BOOLEAN DEFAULT FALSE,
  ceo_reviewed_at TIMESTAMPTZ,
  weight_adjustment_proposal JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Anti-Echo constraint (AFTER scoring columns exist)
ALTER TABLE fhq_learning.hypothesis_canon
ADD CONSTRAINT chk_anti_echo_rule
CHECK (
  pre_tier_scored_by IS NULL
  OR NOT (pre_tier_scored_by::jsonb ? generator_id)
);

-- 6. Index for performance
CREATE INDEX idx_hypothesis_pre_tier_score ON fhq_learning.hypothesis_canon(pre_tier_score)
WHERE pre_tier_score_status = 'SCORED';

CREATE INDEX idx_validator_scores_hypothesis ON fhq_learning.pre_tier_validator_scores(hypothesis_id);
```

---

**Signert:** STIG (EC-003)
**Timestamp:** 2026-01-25T20:45:00Z
**Awaiting:** CEO Approval on 5 Decision Points
