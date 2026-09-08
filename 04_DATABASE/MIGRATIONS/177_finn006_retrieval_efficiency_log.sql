-- Migration 177: FINN-006 Retrieval Efficiency Log
-- CEO-DIR-2026-FINN-006: Adaptive Epistemic Learning Loop
-- Section 3.1: EC-020 Discipline-Aware Query Formation
--
-- Purpose: Track retrieval efficiency per run to enable regime-aware
-- query optimization during the first 1,000 cognitive runs.
--
-- Authority: CEO APPROVED (2025-12-30T23:30:00Z)
-- Owner: EC-020 (SitC)

BEGIN;

-- Ensure schema exists
CREATE SCHEMA IF NOT EXISTS fhq_research;

-- ============================================================================
-- TABLE: retrieval_efficiency_log
-- Logs every evidence node retrieved per FINN run with utilization tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.retrieval_efficiency_log (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Run identification
    run_id                  UUID NOT NULL,
    batch_id                TEXT,
    run_number              INTEGER NOT NULL,

    -- Evidence node tracking
    evidence_node_id        UUID NOT NULL,
    evidence_node_hash      TEXT,                   -- SHA-256 for integrity

    -- Utilization classification
    was_used_in_chain       BOOLEAN NOT NULL DEFAULT FALSE,
    usage_type              TEXT CHECK (usage_type IN (
                                'REASONING',        -- Used in reasoning node
                                'VERIFICATION',     -- Used for verification
                                'SYNTHESIS',        -- Used in final synthesis
                                'UNUSED',           -- Retrieved but not used
                                'DISCARDED'         -- Explicitly discarded
                            )),

    -- Ontology binding (ADR-013)
    ontology_path           TEXT[],                 -- Full path in ontology tree
    ontology_concept_id     UUID,                   -- Link to canonical concept
    domain                  TEXT,                   -- MACRO, CRYPTO, EQUITY, etc.

    -- Regime binding (IoS-003)
    regime_id               TEXT NOT NULL,          -- STRONG_BULL, VOLATILE, BROKEN, etc.
    regime_confidence       NUMERIC(5,4),

    -- Efficiency metrics
    retrieval_latency_ms    INTEGER,
    retrieval_cost_usd      NUMERIC(10,6),
    source_tier             TEXT CHECK (source_tier IN ('LAKE', 'PULSE', 'SNIPER')),

    -- SitC delta tracking
    sitc_discipline_before  NUMERIC(5,4),
    sitc_discipline_after   NUMERIC(5,4),
    sitc_discipline_delta   NUMERIC(5,4) GENERATED ALWAYS AS
                            (sitc_discipline_after - sitc_discipline_before) STORED,

    -- Learning signals
    is_noise_candidate      BOOLEAN DEFAULT FALSE,  -- Flagged for down-weighting
    noise_score             NUMERIC(5,4),           -- 0.0 = pure signal, 1.0 = pure noise

    -- Timestamps
    retrieved_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Governance
    directive_ref           TEXT DEFAULT 'CEO-DIR-2026-FINN-006'
);

-- ============================================================================
-- INDEXES for efficient learning queries
-- ============================================================================

-- Primary query patterns for learning loop
CREATE INDEX idx_retrieval_eff_run_id
    ON fhq_research.retrieval_efficiency_log(run_id);

CREATE INDEX idx_retrieval_eff_regime
    ON fhq_research.retrieval_efficiency_log(regime_id);

CREATE INDEX idx_retrieval_eff_unused
    ON fhq_research.retrieval_efficiency_log(was_used_in_chain)
    WHERE was_used_in_chain = FALSE;

CREATE INDEX idx_retrieval_eff_ontology
    ON fhq_research.retrieval_efficiency_log USING GIN(ontology_path);

CREATE INDEX idx_retrieval_eff_noise
    ON fhq_research.retrieval_efficiency_log(noise_score DESC)
    WHERE is_noise_candidate = TRUE;

-- Composite index for regime-specific efficiency analysis
CREATE INDEX idx_retrieval_eff_regime_domain
    ON fhq_research.retrieval_efficiency_log(regime_id, domain, was_used_in_chain);

-- ============================================================================
-- VIEW: Regime-Specific Efficiency Summary
-- For EC-020 to learn from retrieval patterns per regime
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_regime_retrieval_efficiency AS
SELECT
    regime_id,
    domain,
    COUNT(*) as total_retrieved,
    COUNT(*) FILTER (WHERE was_used_in_chain = TRUE) as total_used,
    COUNT(*) FILTER (WHERE was_used_in_chain = FALSE) as total_unused,
    ROUND(
        COUNT(*) FILTER (WHERE was_used_in_chain = TRUE)::NUMERIC /
        NULLIF(COUNT(*), 0), 4
    ) as efficiency_ratio,
    AVG(noise_score) FILTER (WHERE is_noise_candidate = TRUE) as avg_noise_score,
    AVG(retrieval_cost_usd) as avg_cost_per_retrieval,
    SUM(retrieval_cost_usd) as total_cost
FROM fhq_research.retrieval_efficiency_log
GROUP BY regime_id, domain;

-- ============================================================================
-- VIEW: Ontology Path Utilization
-- Identifies which ontology paths are consistently unused (noise paths)
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_ontology_path_utilization AS
SELECT
    unnest(ontology_path) as ontology_node,
    regime_id,
    COUNT(*) as times_retrieved,
    COUNT(*) FILTER (WHERE was_used_in_chain = TRUE) as times_used,
    ROUND(
        COUNT(*) FILTER (WHERE was_used_in_chain = TRUE)::NUMERIC /
        NULLIF(COUNT(*), 0), 4
    ) as utilization_rate,
    AVG(noise_score) as avg_noise_score
FROM fhq_research.retrieval_efficiency_log
GROUP BY unnest(ontology_path), regime_id
HAVING COUNT(*) >= 5  -- Minimum sample size for statistical relevance
ORDER BY utilization_rate ASC;

-- ============================================================================
-- AUDIT: Log migration
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'MIGRATION_EXECUTE',
    '177_finn006_retrieval_efficiency_log',
    'DATABASE_MIGRATION',
    'STIG',
    'APPROVED',
    'CEO-DIR-2026-FINN-006 Section 3.1: EC-020 Discipline-Aware Query Formation',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-FINN-006',
        'section', '3.1 EC-020 Discipline-Aware Query',
        'table', 'fhq_research.retrieval_efficiency_log',
        'purpose', 'Track retrieval efficiency for regime-aware learning'
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_research'
        AND table_name = 'retrieval_efficiency_log'
    ) THEN
        RAISE EXCEPTION 'Migration 177 FAILED: retrieval_efficiency_log not created';
    END IF;

    RAISE NOTICE 'Migration 177 SUCCESS: retrieval_efficiency_log created for FINN-006 learning';
END $$;
