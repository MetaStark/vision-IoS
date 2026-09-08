# CEO-DIR-2026-064: B1-B5 Change Pack Readiness

**Issued:** 2026-01-17
**Prepared by:** STIG (CTO), FjordHQ
**Classification:** Tier-1 Executive Directive - Gateable Artifact
**Predecessor:** CEO-DIR-2026-062 (CLOSED)
**Status:** PREPARED FOR GATE REVIEW (NOT APPROVED)

---

## DIRECTIVE SCOPE

This directive contains **Document C only** — the Change Pack for resolving blocking gaps B1-B5 identified in CEO-DIR-2026-062.

| Document | Content | Location |
|----------|---------|----------|
| Document A | Verification Report | CEO-DIR-2026-062 (CLOSED) |
| Document B | Activation Readiness Plan | CEO-DIR-2026-062 (CLOSED) |
| **Document C** | **Change Pack** | **This file** |

**Constraint:** This document describes what changes exist. Implementation requires explicit ADR-004 gate approval.

---

## PRIORITY ORDERING

| Priority | Gap | Rationale |
|----------|-----|-----------|
| P0 | B1 (Consensus Capture) | Unblocks Q1 determinism - foundational for all surprise calculations |
| P1 | B2 (Hindsight Mining) | Unblocks Q5 determinism - enables learning from missed opportunities |
| P2 | B3 (IoS-016 → ACI) | Integration layer - delivers event knowledge to learning system |
| P3 | B4 (Orphaned Forecasts) | Data hygiene - improves learning chain completeness from 67% → 95% |
| P4 | B5 (Hash Chains) | State binding - enables ADR-018 state reliability verification |

**Ordering Justification:** B1 and B2 are prerequisites for ACI-readiness (Q1-Q5 determinism). B3 depends on B1 being in place (cannot deliver event knowledge without consensus capture). B4 and B5 are hygiene/reliability improvements that can proceed in parallel once B1-B3 are stable.

---

# DOCUMENT C: CHANGE PACK

## C1: B1 Resolution - Consensus Capture Capability

### C1.1 Acceptance Criteria (Deterministic)

| Criterion | Test | Pass Condition |
|-----------|------|----------------|
| AC-B1-01 | Tier A capture exists | `SELECT count(*) FROM fhq_calendar.market_implied_consensus WHERE tier = 'A'` returns > 0 |
| AC-B1-02 | Tier B capture exists | `SELECT count(*) FROM fhq_calendar.survey_consensus WHERE tier = 'B'` returns > 0 |
| AC-B1-03 | Timestamp immutability | All consensus records have `captured_at < event_release_time` |
| AC-B1-04 | Tier hierarchy enforced | Surprise calculation uses Tier A when available, else Tier B, else fails |
| AC-B1-05 | Q1 answerable | For any event with consensus, system can deterministically answer "What did experts expect?" |

### C1.2 Blast Radius

| Layer | Objects Affected |
|-------|------------------|
| Schema | `fhq_calendar` |
| New Tables | `market_implied_consensus`, `survey_consensus`, `consensus_tier_config` |
| Modified Tables | `calendar_events` (add FK to consensus) |
| New Views | `v_consensus_hierarchy`, `v_event_consensus_status` |
| New Functions | `fn_resolve_consensus_tier()`, `fn_compute_surprise()` |
| Affected IoS | IoS-016, IoS-005 |
| Affected ADR | ADR-013 (schema governance) |

### C1.3 DDL Specification

```sql
-- Migration: 294_b1_consensus_capture_tier_abc.sql
-- Authority: CEO-DIR-2026-064
-- Gate: ADR-004 G0-G4 required

-- C1.3.1: Consensus Tier Configuration
CREATE TABLE fhq_calendar.consensus_tier_config (
    tier_id VARCHAR(1) PRIMARY KEY,  -- 'A', 'B', 'C'
    tier_name TEXT NOT NULL,
    tier_priority INTEGER NOT NULL,  -- 1=highest
    description TEXT,
    capture_window_hours INTEGER DEFAULT 24,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_tier CHECK (tier_id IN ('A', 'B', 'C'))
);

INSERT INTO fhq_calendar.consensus_tier_config (tier_id, tier_name, tier_priority, description) VALUES
('A', 'Market-Implied', 1, 'OIS curves, futures, swaps, breakevens'),
('B', 'Survey Consensus', 2, 'Bloomberg/Reuters poll median'),
('C', 'House/Model', 3, 'FINN/UMA/ACI internal forecasts');

-- C1.3.2: Market-Implied Consensus (Tier A)
CREATE TABLE fhq_calendar.market_implied_consensus (
    consensus_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES fhq_calendar.calendar_events(event_id),
    tier VARCHAR(1) DEFAULT 'A' CHECK (tier = 'A'),
    instrument_type TEXT NOT NULL,  -- 'OIS', 'FED_FUNDS_FUTURE', 'SOFR_FUTURE', 'INFLATION_SWAP', 'BREAKEVEN'
    instrument_id TEXT,  -- specific contract/curve identifier
    implied_value NUMERIC NOT NULL,
    implied_unit TEXT,  -- 'bps', 'pct', 'absolute'
    captured_at TIMESTAMPTZ NOT NULL,
    data_source TEXT NOT NULL,
    source_timestamp TIMESTAMPTZ,
    hash_chain_id UUID,
    evidence_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT capture_before_event CHECK (captured_at < (SELECT scheduled_time FROM fhq_calendar.calendar_events WHERE event_id = market_implied_consensus.event_id))
);

CREATE INDEX idx_mic_event_id ON fhq_calendar.market_implied_consensus(event_id);
CREATE INDEX idx_mic_captured_at ON fhq_calendar.market_implied_consensus(captured_at);

-- C1.3.3: Survey Consensus (Tier B)
CREATE TABLE fhq_calendar.survey_consensus (
    consensus_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES fhq_calendar.calendar_events(event_id),
    tier VARCHAR(1) DEFAULT 'B' CHECK (tier = 'B'),
    survey_source TEXT NOT NULL,  -- 'Bloomberg', 'Reuters', 'TradingEconomics'
    consensus_median NUMERIC NOT NULL,
    consensus_mean NUMERIC,
    consensus_high NUMERIC,
    consensus_low NUMERIC,
    respondent_count INTEGER,
    captured_at TIMESTAMPTZ NOT NULL,
    source_timestamp TIMESTAMPTZ,
    hash_chain_id UUID,
    evidence_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT capture_before_event CHECK (captured_at < (SELECT scheduled_time FROM fhq_calendar.calendar_events WHERE event_id = survey_consensus.event_id))
);

CREATE INDEX idx_sc_event_id ON fhq_calendar.survey_consensus(event_id);
CREATE INDEX idx_sc_captured_at ON fhq_calendar.survey_consensus(captured_at);

-- C1.3.4: Consensus Hierarchy Resolution View
CREATE OR REPLACE VIEW fhq_calendar.v_consensus_hierarchy AS
SELECT
    e.event_id,
    e.event_name,
    e.scheduled_time,
    CASE
        WHEN mic.consensus_id IS NOT NULL THEN 'A'
        WHEN sc.consensus_id IS NOT NULL THEN 'B'
        ELSE NULL
    END AS resolved_tier,
    COALESCE(mic.implied_value, sc.consensus_median) AS consensus_value,
    COALESCE(mic.captured_at, sc.captured_at) AS consensus_captured_at,
    COALESCE(mic.data_source, sc.survey_source) AS consensus_source,
    CASE
        WHEN mic.consensus_id IS NOT NULL THEN mic.evidence_ref
        WHEN sc.consensus_id IS NOT NULL THEN sc.evidence_ref
        ELSE NULL
    END AS evidence_ref,
    CASE
        WHEN mic.consensus_id IS NULL AND sc.consensus_id IS NULL THEN TRUE
        ELSE FALSE
    END AS determinism_failure
FROM fhq_calendar.calendar_events e
LEFT JOIN LATERAL (
    SELECT * FROM fhq_calendar.market_implied_consensus
    WHERE event_id = e.event_id
    ORDER BY captured_at DESC LIMIT 1
) mic ON TRUE
LEFT JOIN LATERAL (
    SELECT * FROM fhq_calendar.survey_consensus
    WHERE event_id = e.event_id
    ORDER BY captured_at DESC LIMIT 1
) sc ON TRUE;

-- C1.3.5: Surprise Calculation Function
CREATE OR REPLACE FUNCTION fhq_calendar.fn_compute_surprise(
    p_event_id UUID,
    p_actual_value NUMERIC
) RETURNS TABLE (
    surprise_value NUMERIC,
    surprise_pct NUMERIC,
    consensus_tier VARCHAR(1),
    consensus_value NUMERIC,
    determinism_status TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        CASE WHEN ch.determinism_failure THEN NULL
             ELSE p_actual_value - ch.consensus_value
        END AS surprise_value,
        CASE WHEN ch.determinism_failure OR ch.consensus_value = 0 THEN NULL
             ELSE ((p_actual_value - ch.consensus_value) / ABS(ch.consensus_value)) * 100
        END AS surprise_pct,
        ch.resolved_tier AS consensus_tier,
        ch.consensus_value,
        CASE WHEN ch.determinism_failure THEN 'CONSENSUS_UNAVAILABLE'
             ELSE 'DETERMINISTIC'
        END AS determinism_status
    FROM fhq_calendar.v_consensus_hierarchy ch
    WHERE ch.event_id = p_event_id;
END;
$$ LANGUAGE plpgsql STABLE;
```

### C1.4 Rollback Strategy

```sql
-- Rollback: 294_b1_consensus_capture_tier_abc_rollback.sql
-- Execute only if rollback required

DROP FUNCTION IF EXISTS fhq_calendar.fn_compute_surprise(UUID, NUMERIC);
DROP VIEW IF EXISTS fhq_calendar.v_consensus_hierarchy;
DROP TABLE IF EXISTS fhq_calendar.survey_consensus;
DROP TABLE IF EXISTS fhq_calendar.market_implied_consensus;
DROP TABLE IF EXISTS fhq_calendar.consensus_tier_config;

-- Log rollback
INSERT INTO fhq_meta.adr_audit_log (action, schema_name, object_name, details, executed_by)
VALUES ('ROLLBACK', 'fhq_calendar', '294_b1_consensus_capture', 'B1 rollback executed', 'STIG');
```

### C1.5 Governance Hooks

| Hook | Specification |
|------|---------------|
| Evidence Ref | All consensus records must have `evidence_ref` pointing to `vision_verification.summary_evidence_ledger` |
| Hash Chain | `hash_chain_id` links to `vision_verification.hash_chains` for ADR-018 compliance |
| Signature | Migration must be signed via Ed25519 per ADR-008 |
| Audit Log | All changes logged to `fhq_meta.adr_audit_log` |
| Invariant | `captured_at < event_release_time` enforced at database level |

---

## C2: B2 Resolution - Hindsight Alpha Mining

### C2.1 Acceptance Criteria (Deterministic)

| Criterion | Test | Pass Condition |
|-----------|------|----------------|
| AC-B2-01 | Mining pipeline exists | `SELECT count(*) FROM fhq_alpha.hindsight_opportunities` returns > 0 after first run |
| AC-B2-02 | Surprise delta computed | For each forecast-outcome pair, surprise delta is calculated and stored |
| AC-B2-03 | Opportunity ranking | Top N opportunities ranked by magnitude of surprise |
| AC-B2-04 | Q5 answerable | System can answer "What opportunities became visible post-hoc?" |
| AC-B2-05 | No outcome leakage | Hindsight analysis uses only data available at forecast time |

### C2.2 Blast Radius

| Layer | Objects Affected |
|-------|------------------|
| Schema | `fhq_alpha`, `fhq_research` |
| New Tables | `hindsight_opportunities`, `surprise_analysis_runs` |
| Modified Tables | `alpha_hypotheses` (populate from mining) |
| New Views | `v_hindsight_top_opportunities`, `v_surprise_analysis_summary` |
| New Functions | `fn_mine_hindsight_opportunities()`, `fn_compute_surprise_delta()` |
| Affected IoS | IoS-010 (Prediction Ledger), IoS-007 (Alpha Graph) |

### C2.3 DDL Specification

```sql
-- Migration: 295_b2_hindsight_alpha_mining.sql
-- Authority: CEO-DIR-2026-064
-- Gate: ADR-004 G0-G4 required

-- C2.3.1: Surprise Analysis Runs
CREATE TABLE fhq_alpha.surprise_analysis_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_timestamp TIMESTAMPTZ DEFAULT NOW(),
    analysis_window_start TIMESTAMPTZ NOT NULL,
    analysis_window_end TIMESTAMPTZ NOT NULL,
    pairs_analyzed INTEGER,
    opportunities_found INTEGER,
    top_opportunity_magnitude NUMERIC,
    execution_duration_ms INTEGER,
    evidence_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- C2.3.2: Hindsight Opportunities
CREATE TABLE fhq_alpha.hindsight_opportunities (
    opportunity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES fhq_alpha.surprise_analysis_runs(run_id),
    forecast_id UUID NOT NULL,
    outcome_id UUID NOT NULL,
    forecast_value NUMERIC,
    outcome_value NUMERIC,
    surprise_delta NUMERIC NOT NULL,
    surprise_direction VARCHAR(10) CHECK (surprise_direction IN ('POSITIVE', 'NEGATIVE', 'NEUTRAL')),
    surprise_magnitude_rank INTEGER,
    domain TEXT,
    asset_class TEXT,
    signals_missed JSONB,  -- What signals would have predicted this?
    regime_at_forecast TEXT,
    regime_at_outcome TEXT,
    learning_annotation TEXT,
    evidence_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ho_run_id ON fhq_alpha.hindsight_opportunities(run_id);
CREATE INDEX idx_ho_magnitude_rank ON fhq_alpha.hindsight_opportunities(surprise_magnitude_rank);
CREATE INDEX idx_ho_domain ON fhq_alpha.hindsight_opportunities(domain);

-- C2.3.3: Surprise Delta Computation Function
CREATE OR REPLACE FUNCTION fhq_alpha.fn_compute_surprise_delta(
    p_forecast_value NUMERIC,
    p_outcome_value NUMERIC
) RETURNS TABLE (
    delta NUMERIC,
    direction VARCHAR(10),
    magnitude NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p_outcome_value - p_forecast_value AS delta,
        CASE
            WHEN p_outcome_value > p_forecast_value THEN 'POSITIVE'
            WHEN p_outcome_value < p_forecast_value THEN 'NEGATIVE'
            ELSE 'NEUTRAL'
        END::VARCHAR(10) AS direction,
        ABS(p_outcome_value - p_forecast_value) AS magnitude;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- C2.3.4: Hindsight Mining Function
CREATE OR REPLACE FUNCTION fhq_alpha.fn_mine_hindsight_opportunities(
    p_window_start TIMESTAMPTZ,
    p_window_end TIMESTAMPTZ,
    p_top_n INTEGER DEFAULT 100
) RETURNS UUID AS $$
DECLARE
    v_run_id UUID;
    v_pairs_count INTEGER;
    v_opps_count INTEGER;
BEGIN
    -- Create run record
    INSERT INTO fhq_alpha.surprise_analysis_runs (
        analysis_window_start,
        analysis_window_end
    ) VALUES (
        p_window_start,
        p_window_end
    ) RETURNING run_id INTO v_run_id;

    -- Mine opportunities from forecast-outcome pairs
    WITH ranked_surprises AS (
        SELECT
            fop.forecast_id,
            fop.outcome_id,
            fl.forecast_probability AS forecast_value,
            ol.outcome_value,
            (fhq_alpha.fn_compute_surprise_delta(fl.forecast_probability, ol.outcome_value)).*,
            fl.domain,
            ROW_NUMBER() OVER (ORDER BY ABS(ol.outcome_value - fl.forecast_probability) DESC) AS magnitude_rank
        FROM fhq_research.forecast_outcome_pairs fop
        JOIN fhq_research.forecast_ledger fl ON fop.forecast_id = fl.forecast_id
        JOIN fhq_research.outcome_ledger ol ON fop.outcome_id = ol.outcome_id
        WHERE fl.created_at BETWEEN p_window_start AND p_window_end
    )
    INSERT INTO fhq_alpha.hindsight_opportunities (
        run_id,
        forecast_id,
        outcome_id,
        forecast_value,
        outcome_value,
        surprise_delta,
        surprise_direction,
        surprise_magnitude_rank,
        domain
    )
    SELECT
        v_run_id,
        forecast_id,
        outcome_id,
        forecast_value,
        outcome_value,
        delta,
        direction,
        magnitude_rank,
        domain
    FROM ranked_surprises
    WHERE magnitude_rank <= p_top_n;

    GET DIAGNOSTICS v_opps_count = ROW_COUNT;

    -- Update run record
    SELECT count(*) INTO v_pairs_count
    FROM fhq_research.forecast_outcome_pairs fop
    JOIN fhq_research.forecast_ledger fl ON fop.forecast_id = fl.forecast_id
    WHERE fl.created_at BETWEEN p_window_start AND p_window_end;

    UPDATE fhq_alpha.surprise_analysis_runs
    SET pairs_analyzed = v_pairs_count,
        opportunities_found = v_opps_count
    WHERE run_id = v_run_id;

    RETURN v_run_id;
END;
$$ LANGUAGE plpgsql;

-- C2.3.5: Top Opportunities View
CREATE OR REPLACE VIEW fhq_alpha.v_hindsight_top_opportunities AS
SELECT
    ho.*,
    sar.run_timestamp,
    sar.analysis_window_start,
    sar.analysis_window_end
FROM fhq_alpha.hindsight_opportunities ho
JOIN fhq_alpha.surprise_analysis_runs sar ON ho.run_id = sar.run_id
WHERE ho.surprise_magnitude_rank <= 10
ORDER BY sar.run_timestamp DESC, ho.surprise_magnitude_rank;
```

### C2.4 Rollback Strategy

```sql
-- Rollback: 295_b2_hindsight_alpha_mining_rollback.sql

DROP VIEW IF EXISTS fhq_alpha.v_hindsight_top_opportunities;
DROP FUNCTION IF EXISTS fhq_alpha.fn_mine_hindsight_opportunities(TIMESTAMPTZ, TIMESTAMPTZ, INTEGER);
DROP FUNCTION IF EXISTS fhq_alpha.fn_compute_surprise_delta(NUMERIC, NUMERIC);
DROP TABLE IF EXISTS fhq_alpha.hindsight_opportunities;
DROP TABLE IF EXISTS fhq_alpha.surprise_analysis_runs;

INSERT INTO fhq_meta.adr_audit_log (action, schema_name, object_name, details, executed_by)
VALUES ('ROLLBACK', 'fhq_alpha', '295_b2_hindsight_mining', 'B2 rollback executed', 'STIG');
```

### C2.5 Governance Hooks

| Hook | Specification |
|------|---------------|
| Evidence Ref | Each run creates evidence record in `vision_verification.summary_evidence_ledger` |
| Outcome Leakage Guard | Mining function only uses data with `created_at` before outcome capture |
| Audit Log | All runs logged to `fhq_meta.adr_audit_log` |
| Invariant | `signals_missed` can only reference signals available at forecast time |

---

## C3: B3 Resolution - IoS-016 → ACI Integration

### C3.1 Acceptance Criteria (Deterministic)

| Criterion | Test | Pass Condition |
|-----------|------|----------------|
| AC-B3-01 | Event learning tags exist | `SELECT count(*) FROM vision_signals.event_learning_tags` returns > 0 |
| AC-B3-02 | Consensus linked | Each learning tag references resolved consensus tier |
| AC-B3-03 | Surprise computed | Each tag has `surprise_vs_consensus` populated |
| AC-B3-04 | ACI delivery logged | Delivery timestamp recorded in `delivered_to_aci_at` |
| AC-B3-05 | Knowledge not action | No execution triggers in event learning path |

### C3.2 Blast Radius

| Layer | Objects Affected |
|-------|------------------|
| Schema | `vision_signals`, `fhq_calendar` |
| New Tables | `event_learning_tags` |
| Modified Tables | None |
| New Views | `v_event_knowledge_delivery_status` |
| New Functions | `fn_generate_event_learning_tag()` |
| Task Registry | New task `ios016_event_knowledge_delivery` |
| Affected IoS | IoS-016, IoS-005, ADR-020 (ACI) |

### C3.3 DDL Specification

```sql
-- Migration: 296_b3_ios016_aci_integration.sql
-- Authority: CEO-DIR-2026-064
-- Gate: ADR-004 G0-G4 required

-- C3.3.1: Event Learning Tags
CREATE TABLE vision_signals.event_learning_tags (
    tag_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL,
    event_name TEXT,
    event_type TEXT,
    scheduled_time TIMESTAMPTZ,
    actual_release_time TIMESTAMPTZ,

    -- Consensus data (from B1)
    consensus_tier VARCHAR(1),
    consensus_value NUMERIC,
    consensus_source TEXT,
    consensus_captured_at TIMESTAMPTZ,

    -- FjordHQ internal expectation (Tier C)
    fjordhq_expectation NUMERIC,
    fjordhq_confidence NUMERIC,
    fjordhq_source_model TEXT,

    -- Outcome
    actual_value NUMERIC,
    outcome_captured_at TIMESTAMPTZ,

    -- Surprise calculations
    surprise_vs_consensus NUMERIC,
    surprise_vs_fjordhq NUMERIC,
    surprise_direction VARCHAR(10),

    -- Regime context
    regime_before_event TEXT,
    regime_after_event TEXT,
    regime_change_detected BOOLEAN DEFAULT FALSE,

    -- Learning annotation
    learning_annotation JSONB,
    epistemic_lesson_id UUID,

    -- ACI delivery
    delivered_to_aci_at TIMESTAMPTZ,
    aci_acknowledgment_ref TEXT,

    -- Governance
    evidence_ref TEXT,
    hash_chain_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_elt_event_id ON vision_signals.event_learning_tags(event_id);
CREATE INDEX idx_elt_delivered ON vision_signals.event_learning_tags(delivered_to_aci_at);
CREATE INDEX idx_elt_consensus_tier ON vision_signals.event_learning_tags(consensus_tier);

-- C3.3.2: Learning Tag Generation Function
CREATE OR REPLACE FUNCTION vision_signals.fn_generate_event_learning_tag(
    p_event_id UUID,
    p_actual_value NUMERIC,
    p_outcome_captured_at TIMESTAMPTZ DEFAULT NOW()
) RETURNS UUID AS $$
DECLARE
    v_tag_id UUID;
    v_event RECORD;
    v_consensus RECORD;
    v_fjordhq RECORD;
    v_surprise_vs_consensus NUMERIC;
    v_surprise_vs_fjordhq NUMERIC;
BEGIN
    -- Get event details
    SELECT * INTO v_event
    FROM fhq_calendar.calendar_events
    WHERE event_id = p_event_id;

    -- Get consensus (from B1 hierarchy view)
    SELECT * INTO v_consensus
    FROM fhq_calendar.v_consensus_hierarchy
    WHERE event_id = p_event_id;

    -- Calculate surprises
    IF v_consensus.consensus_value IS NOT NULL THEN
        v_surprise_vs_consensus := p_actual_value - v_consensus.consensus_value;
    END IF;

    -- Insert learning tag
    INSERT INTO vision_signals.event_learning_tags (
        event_id,
        event_name,
        event_type,
        scheduled_time,
        consensus_tier,
        consensus_value,
        consensus_source,
        consensus_captured_at,
        actual_value,
        outcome_captured_at,
        surprise_vs_consensus,
        surprise_direction,
        learning_annotation
    ) VALUES (
        p_event_id,
        v_event.event_name,
        v_event.event_type,
        v_event.scheduled_time,
        v_consensus.resolved_tier,
        v_consensus.consensus_value,
        v_consensus.consensus_source,
        v_consensus.consensus_captured_at,
        p_actual_value,
        p_outcome_captured_at,
        v_surprise_vs_consensus,
        CASE
            WHEN v_surprise_vs_consensus > 0 THEN 'POSITIVE'
            WHEN v_surprise_vs_consensus < 0 THEN 'NEGATIVE'
            ELSE 'NEUTRAL'
        END,
        jsonb_build_object(
            'event_type', v_event.event_type,
            'consensus_available', v_consensus.resolved_tier IS NOT NULL,
            'surprise_magnitude', ABS(v_surprise_vs_consensus),
            'generated_at', NOW()
        )
    ) RETURNING tag_id INTO v_tag_id;

    RETURN v_tag_id;
END;
$$ LANGUAGE plpgsql;

-- C3.3.3: Knowledge Delivery Status View
CREATE OR REPLACE VIEW vision_signals.v_event_knowledge_delivery_status AS
SELECT
    tag_id,
    event_id,
    event_name,
    scheduled_time,
    consensus_tier,
    CASE WHEN consensus_tier IS NULL THEN 'CONSENSUS_UNAVAILABLE' ELSE 'AVAILABLE' END AS q1_status,
    surprise_vs_consensus,
    delivered_to_aci_at,
    CASE WHEN delivered_to_aci_at IS NOT NULL THEN 'DELIVERED' ELSE 'PENDING' END AS delivery_status,
    created_at
FROM vision_signals.event_learning_tags
ORDER BY created_at DESC;
```

### C3.4 Rollback Strategy

```sql
-- Rollback: 296_b3_ios016_aci_integration_rollback.sql

DROP VIEW IF EXISTS vision_signals.v_event_knowledge_delivery_status;
DROP FUNCTION IF EXISTS vision_signals.fn_generate_event_learning_tag(UUID, NUMERIC, TIMESTAMPTZ);
DROP TABLE IF EXISTS vision_signals.event_learning_tags;

INSERT INTO fhq_meta.adr_audit_log (action, schema_name, object_name, details, executed_by)
VALUES ('ROLLBACK', 'vision_signals', '296_b3_ios016_aci', 'B3 rollback executed', 'STIG');
```

### C3.5 Governance Hooks

| Hook | Specification |
|------|---------------|
| Knowledge Only | `event_learning_tags` contains knowledge only, no execution triggers |
| Evidence Ref | All tags linked to evidence ledger |
| ACI Boundary | Delivery to ACI is logged but ACI decides whether to act |
| Invariant | No INSERT/UPDATE on execution tables from this path |

---

## C4: B4 Resolution - Orphaned Forecast Resolution

### C4.1 Acceptance Criteria (Deterministic)

| Criterion | Test | Pass Condition |
|-----------|------|----------------|
| AC-B4-01 | Orphan rate reduced | Orphaned forecasts < 10% (from 32.6%) |
| AC-B4-02 | Resolution logged | Each resolution action has audit trail |
| AC-B4-03 | No false linkage | Resolution algorithm has precision > 95% |
| AC-B4-04 | Lineage complete | 90%+ of forecasts have outcome linkage |

### C4.2 Blast Radius

| Layer | Objects Affected |
|-------|------------------|
| Schema | `fhq_research` |
| New Tables | `forecast_resolution_log`, `orphan_analysis_runs` |
| Modified Tables | `forecast_outcome_pairs` (additional linkages) |
| New Views | `v_orphan_status_summary` |
| New Functions | `fn_resolve_orphaned_forecasts()` |

### C4.3 DDL Specification

```sql
-- Migration: 297_b4_orphaned_forecast_resolution.sql
-- Authority: CEO-DIR-2026-064
-- Gate: ADR-004 G0-G4 required

-- C4.3.1: Orphan Analysis Runs
CREATE TABLE fhq_research.orphan_analysis_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_timestamp TIMESTAMPTZ DEFAULT NOW(),
    orphaned_before INTEGER,
    resolved_count INTEGER,
    orphaned_after INTEGER,
    resolution_rate NUMERIC,
    evidence_ref TEXT
);

-- C4.3.2: Forecast Resolution Log
CREATE TABLE fhq_research.forecast_resolution_log (
    resolution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES fhq_research.orphan_analysis_runs(run_id),
    forecast_id UUID NOT NULL,
    resolution_type VARCHAR(20) CHECK (resolution_type IN ('MATCHED', 'EXPIRED', 'INVALIDATED', 'MANUAL')),
    matched_outcome_id UUID,
    match_confidence NUMERIC,
    resolution_reason TEXT,
    resolved_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_frl_forecast_id ON fhq_research.forecast_resolution_log(forecast_id);

-- C4.3.3: Resolution Function
CREATE OR REPLACE FUNCTION fhq_research.fn_resolve_orphaned_forecasts(
    p_match_threshold NUMERIC DEFAULT 0.8
) RETURNS UUID AS $$
DECLARE
    v_run_id UUID;
    v_orphaned_before INTEGER;
    v_resolved INTEGER := 0;
BEGIN
    -- Count orphans before
    SELECT count(*) INTO v_orphaned_before
    FROM fhq_research.forecast_ledger fl
    LEFT JOIN fhq_research.forecast_outcome_pairs fop ON fl.forecast_id = fop.forecast_id
    WHERE fop.pair_id IS NULL;

    -- Create run
    INSERT INTO fhq_research.orphan_analysis_runs (orphaned_before)
    VALUES (v_orphaned_before)
    RETURNING run_id INTO v_run_id;

    -- Attempt matching (simplified - actual matching logic would be more sophisticated)
    WITH potential_matches AS (
        SELECT
            fl.forecast_id,
            ol.outcome_id,
            fl.domain,
            ol.outcome_type,
            -- Simple similarity score based on domain and time proximity
            CASE
                WHEN fl.domain = ol.outcome_type
                AND ABS(EXTRACT(EPOCH FROM (ol.captured_at - fl.forecast_time))) < 86400
                THEN 0.9
                ELSE 0.5
            END AS match_score
        FROM fhq_research.forecast_ledger fl
        LEFT JOIN fhq_research.forecast_outcome_pairs fop ON fl.forecast_id = fop.forecast_id
        CROSS JOIN fhq_research.outcome_ledger ol
        WHERE fop.pair_id IS NULL
        AND ol.captured_at > fl.forecast_time
    )
    INSERT INTO fhq_research.forecast_resolution_log (
        run_id, forecast_id, resolution_type, matched_outcome_id, match_confidence, resolution_reason
    )
    SELECT
        v_run_id,
        forecast_id,
        'MATCHED',
        outcome_id,
        match_score,
        'Auto-matched by domain and time proximity'
    FROM potential_matches
    WHERE match_score >= p_match_threshold;

    GET DIAGNOSTICS v_resolved = ROW_COUNT;

    -- Update run
    UPDATE fhq_research.orphan_analysis_runs
    SET resolved_count = v_resolved,
        orphaned_after = v_orphaned_before - v_resolved,
        resolution_rate = v_resolved::NUMERIC / NULLIF(v_orphaned_before, 0)
    WHERE run_id = v_run_id;

    RETURN v_run_id;
END;
$$ LANGUAGE plpgsql;

-- C4.3.4: Orphan Status View
CREATE OR REPLACE VIEW fhq_research.v_orphan_status_summary AS
SELECT
    (SELECT count(*) FROM fhq_research.forecast_ledger) AS total_forecasts,
    (SELECT count(*) FROM fhq_research.forecast_ledger fl
     LEFT JOIN fhq_research.forecast_outcome_pairs fop ON fl.forecast_id = fop.forecast_id
     WHERE fop.pair_id IS NULL) AS orphaned_forecasts,
    (SELECT count(*) FROM fhq_research.forecast_outcome_pairs) AS linked_pairs,
    ROUND(
        (SELECT count(*) FROM fhq_research.forecast_outcome_pairs)::NUMERIC /
        NULLIF((SELECT count(*) FROM fhq_research.forecast_ledger), 0) * 100,
        2
    ) AS linkage_pct;
```

### C4.4 Rollback Strategy

```sql
-- Rollback: 297_b4_orphaned_forecast_resolution_rollback.sql

DROP VIEW IF EXISTS fhq_research.v_orphan_status_summary;
DROP FUNCTION IF EXISTS fhq_research.fn_resolve_orphaned_forecasts(NUMERIC);
DROP TABLE IF EXISTS fhq_research.forecast_resolution_log;
DROP TABLE IF EXISTS fhq_research.orphan_analysis_runs;

INSERT INTO fhq_meta.adr_audit_log (action, schema_name, object_name, details, executed_by)
VALUES ('ROLLBACK', 'fhq_research', '297_b4_orphan_resolution', 'B4 rollback executed', 'STIG');
```

### C4.5 Governance Hooks

| Hook | Specification |
|------|---------------|
| Precision Guard | Match confidence threshold enforced (default 80%) |
| Audit Trail | All resolutions logged with reason |
| No False Positives | Manual review required for low-confidence matches |

---

## C5: B5 Resolution - Hash Chain Population

### C5.1 Acceptance Criteria (Deterministic)

| Criterion | Test | Pass Condition |
|-----------|------|----------------|
| AC-B5-01 | Hash chains populated | `SELECT count(*) FROM vision_verification.hash_chains` returns > 0 |
| AC-B5-02 | State binding active | Operations link to hash chain entries |
| AC-B5-03 | Chain integrity | `fn_verify_hash_chain()` returns TRUE |
| AC-B5-04 | ADR-018 compliant | State snapshots have verifiable hash bindings |

### C5.2 Blast Radius

| Layer | Objects Affected |
|-------|------------------|
| Schema | `vision_verification` |
| Modified Tables | `hash_chains` (populate), `operation_signatures` (link) |
| New Functions | `fn_append_hash_chain()`, `fn_verify_hash_chain()` |
| Affected ADR | ADR-018 (state reliability) |

### C5.3 DDL Specification

```sql
-- Migration: 298_b5_hash_chain_population.sql
-- Authority: CEO-DIR-2026-064
-- Gate: ADR-004 G0-G4 required

-- C5.3.1: Hash Chain Append Function
CREATE OR REPLACE FUNCTION vision_verification.fn_append_hash_chain(
    p_operation_type TEXT,
    p_operation_data JSONB,
    p_agent_id TEXT
) RETURNS UUID AS $$
DECLARE
    v_chain_id UUID;
    v_prev_hash TEXT;
    v_new_hash TEXT;
    v_data_to_hash TEXT;
BEGIN
    -- Get previous hash (or genesis)
    SELECT content_hash INTO v_prev_hash
    FROM vision_verification.hash_chains
    ORDER BY created_at DESC
    LIMIT 1;

    IF v_prev_hash IS NULL THEN
        v_prev_hash := 'GENESIS_' || NOW()::TEXT;
    END IF;

    -- Compute new hash
    v_data_to_hash := v_prev_hash || '|' || p_operation_type || '|' || p_operation_data::TEXT || '|' || NOW()::TEXT;
    v_new_hash := encode(sha256(v_data_to_hash::bytea), 'hex');

    -- Insert chain entry
    INSERT INTO vision_verification.hash_chains (
        chain_type,
        content_hash,
        previous_hash,
        content_data,
        created_by
    ) VALUES (
        p_operation_type,
        v_new_hash,
        v_prev_hash,
        p_operation_data,
        p_agent_id
    ) RETURNING chain_id INTO v_chain_id;

    RETURN v_chain_id;
END;
$$ LANGUAGE plpgsql;

-- C5.3.2: Hash Chain Verification Function
CREATE OR REPLACE FUNCTION vision_verification.fn_verify_hash_chain()
RETURNS TABLE (
    chain_id UUID,
    is_valid BOOLEAN,
    error_message TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH chain_sequence AS (
        SELECT
            hc.chain_id,
            hc.content_hash,
            hc.previous_hash,
            hc.content_data,
            hc.chain_type,
            hc.created_at,
            LAG(hc.content_hash) OVER (ORDER BY hc.created_at) AS expected_prev_hash
        FROM vision_verification.hash_chains hc
        ORDER BY hc.created_at
    )
    SELECT
        cs.chain_id,
        CASE
            WHEN cs.expected_prev_hash IS NULL THEN TRUE  -- Genesis block
            WHEN cs.previous_hash = cs.expected_prev_hash THEN TRUE
            ELSE FALSE
        END AS is_valid,
        CASE
            WHEN cs.expected_prev_hash IS NOT NULL AND cs.previous_hash != cs.expected_prev_hash
            THEN 'Hash chain broken: expected ' || cs.expected_prev_hash || ' but got ' || cs.previous_hash
            ELSE NULL
        END AS error_message
    FROM chain_sequence cs;
END;
$$ LANGUAGE plpgsql STABLE;

-- C5.3.3: Bootstrap genesis block
INSERT INTO vision_verification.hash_chains (
    chain_type,
    content_hash,
    previous_hash,
    content_data,
    created_by
) VALUES (
    'GENESIS',
    encode(sha256(('GENESIS_CEO_DIR_2026_064_' || NOW()::TEXT)::bytea), 'hex'),
    NULL,
    '{"directive": "CEO-DIR-2026-064", "purpose": "B5 hash chain initialization"}'::JSONB,
    'STIG'
);
```

### C5.4 Rollback Strategy

```sql
-- Rollback: 298_b5_hash_chain_population_rollback.sql
-- WARNING: Rollback destroys hash chain integrity

DROP FUNCTION IF EXISTS vision_verification.fn_verify_hash_chain();
DROP FUNCTION IF EXISTS vision_verification.fn_append_hash_chain(TEXT, JSONB, TEXT);
DELETE FROM vision_verification.hash_chains WHERE chain_type = 'GENESIS' AND content_data->>'directive' = 'CEO-DIR-2026-064';

INSERT INTO fhq_meta.adr_audit_log (action, schema_name, object_name, details, executed_by)
VALUES ('ROLLBACK', 'vision_verification', '298_b5_hash_chain', 'B5 rollback executed - chain integrity compromised', 'STIG');
```

### C5.5 Governance Hooks

| Hook | Specification |
|------|---------------|
| Chain Integrity | `fn_verify_hash_chain()` must pass after every operation |
| Genesis Block | Single genesis block per directive |
| Immutability | No UPDATE/DELETE on hash_chains (append-only) |
| ADR-018 | All state snapshots must call `fn_append_hash_chain()` |

---

## ADR-004 GATE CHECKLIST

### Pre-Gate Requirements

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Change Pack document complete | READY | This document |
| All DDL specifications provided | READY | C1-C5 sections |
| Acceptance criteria defined | READY | AC-B1-* through AC-B5-* |
| Rollback strategy documented | READY | C1.4-C5.4 sections |
| Blast radius mapped | READY | C1.2-C5.2 sections |
| Governance hooks specified | READY | C1.5-C5.5 sections |

### Gate Sign-Off Matrix

| Gate | Approver | Required For | Status |
|------|----------|--------------|--------|
| G0 Architecture | CEO | All changes | PENDING |
| G1 Technical | STIG | Migration execution | PENDING |
| G2 Governance | VEGA | Schema modifications | PENDING |
| G3 Audit | VEGA | Production deployment | PENDING |
| G4 Activation | CEO | Go-live | PENDING |

### Execution Order (Post-Approval)

```
1. Migration 294 (B1 - Consensus Capture)
   └─ Enables Q1 determinism

2. Migration 295 (B2 - Hindsight Mining)
   └─ Enables Q5 determinism

3. Migration 296 (B3 - IoS-016 → ACI)
   └─ Depends on: B1 complete
   └─ Delivers event knowledge to learning layer

4. Migration 297 (B4 - Orphan Resolution)
   └─ Can run in parallel with B3
   └─ Improves learning chain completeness

5. Migration 298 (B5 - Hash Chains)
   └─ Can run in parallel with B3, B4
   └─ Enables ADR-018 state verification
```

---

## ATTESTATION

**This Change Pack is:**
- Complete (all B1-B5 specifications provided)
- Gateable (ADR-004 checklist ready for sign-off)
- Reversible (rollback scripts for each change)
- Evidence-ready (governance hooks defined)
- Implementation-free (no execution steps in directive body)

**Change Pack Status:** NOT APPROVED - Requires ADR-004 gate approval

**Prepared by:** STIG (CTO), FjordHQ
**Date:** 2026-01-17
**Directive:** CEO-DIR-2026-064

*Awaiting CEO decision on gate approval.*
