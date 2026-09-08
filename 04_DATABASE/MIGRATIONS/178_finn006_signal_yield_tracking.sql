-- Migration 178: FINN-006 Signal Yield Tracking
-- CEO-DIR-2026-FINN-006: Adaptive Epistemic Learning Loop
-- Section 3.2: EC-021 Signal-Yield Gating
--
-- Purpose: Transform InForage from cost-control to attention-control.
-- Track signal yield per source to optimize retrieval priority.
--
-- Authority: CEO APPROVED (2025-12-30T23:30:00Z)
-- Owner: EC-021 (InForage)

BEGIN;

-- Ensure schema exists
CREATE SCHEMA IF NOT EXISTS fhq_research;

-- ============================================================================
-- TABLE: signal_yield_tracking
-- Tracks signal value generated per source/path/regime combination
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.signal_yield_tracking (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Run identification
    run_id                  UUID NOT NULL,
    batch_id                TEXT,

    -- Source classification (ADR-012 Waterfall)
    source_tier             TEXT NOT NULL CHECK (source_tier IN ('LAKE', 'PULSE', 'SNIPER')),
    source_name             TEXT NOT NULL,          -- Specific source (yfinance, FRED, Alpha Vantage, etc.)
    source_endpoint         TEXT,                   -- API endpoint if applicable

    -- Ontology binding
    ontology_path           TEXT[],
    ontology_concept_id     UUID,
    domain                  TEXT,

    -- Regime binding
    regime_id               TEXT NOT NULL,
    regime_confidence       NUMERIC(5,4),

    -- Yield metrics
    queries_made            INTEGER NOT NULL DEFAULT 1,
    evidence_nodes_returned INTEGER NOT NULL DEFAULT 0,
    evidence_nodes_used     INTEGER NOT NULL DEFAULT 0,
    signal_yield_ratio      NUMERIC(5,4) GENERATED ALWAYS AS (
                                CASE WHEN evidence_nodes_returned > 0
                                     THEN evidence_nodes_used::NUMERIC / evidence_nodes_returned
                                     ELSE 0
                                END
                            ) STORED,

    -- Cost tracking
    query_cost_usd          NUMERIC(10,6) NOT NULL DEFAULT 0,
    cost_per_signal         NUMERIC(10,6) GENERATED ALWAYS AS (
                                CASE WHEN evidence_nodes_used > 0
                                     THEN query_cost_usd / evidence_nodes_used
                                     ELSE query_cost_usd
                                END
                            ) STORED,

    -- Justification tracking (low-yield sources need higher justification)
    justification_required  BOOLEAN DEFAULT FALSE,
    justification_threshold NUMERIC(5,4),           -- Required confidence to use this source
    justification_provided  TEXT,                   -- Reason for using low-yield source

    -- Priority adjustment
    current_priority        NUMERIC(5,4) DEFAULT 0.5,
    priority_adjustment     NUMERIC(5,4) DEFAULT 0,
    new_priority            NUMERIC(5,4) GENERATED ALWAYS AS (
                                GREATEST(0, LEAST(1, current_priority + priority_adjustment))
                            ) STORED,

    -- Surprise re-sampling (Anti-Confirmation Bias)
    is_surprise_sample      BOOLEAN DEFAULT FALSE,  -- Part of 5% exploration quota
    surprise_quota_id       UUID,                   -- Links to quota batch
    surprise_outcome        TEXT CHECK (surprise_outcome IN (
                                'CONFIRMED_NOISE',  -- Still noise after re-test
                                'SIGNAL_FOUND',     -- Was noise, now signal
                                'INCONCLUSIVE',     -- Needs more data
                                NULL                -- Not a surprise sample
                            )),

    -- Learning metadata
    learning_batch_id       TEXT,                   -- Which 100-run batch
    -- Note: is_low_yield computed via view/query, not generated column
    -- (PostgreSQL limitation: cannot reference other generated columns)

    -- Timestamps
    queried_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Governance
    directive_ref           TEXT DEFAULT 'CEO-DIR-2026-FINN-006'
);

-- ============================================================================
-- TABLE: surprise_resampling_quota
-- Tracks the 5% exploration quota for anti-confirmation bias
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.surprise_resampling_quota (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Quota identification
    batch_id                TEXT NOT NULL,
    batch_start_run         INTEGER NOT NULL,
    batch_end_run           INTEGER NOT NULL,

    -- Quota allocation
    total_retrievals        INTEGER NOT NULL DEFAULT 0,
    surprise_quota_count    INTEGER GENERATED ALWAYS AS (
                                GREATEST(1, FLOOR(total_retrievals * 0.05))
                            ) STORED,
    surprise_samples_used   INTEGER NOT NULL DEFAULT 0,
    quota_remaining         INTEGER GENERATED ALWAYS AS (
                                GREATEST(0, FLOOR(total_retrievals * 0.05) - surprise_samples_used)
                            ) STORED,

    -- Outcomes
    signals_found           INTEGER NOT NULL DEFAULT 0,
    confirmed_noise         INTEGER NOT NULL DEFAULT 0,
    inconclusive            INTEGER NOT NULL DEFAULT 0,

    -- Effectiveness tracking
    exploration_roi         NUMERIC(5,4) GENERATED ALWAYS AS (
                                CASE WHEN surprise_samples_used > 0
                                     THEN signals_found::NUMERIC / surprise_samples_used
                                     ELSE 0
                                END
                            ) STORED,

    -- Timestamps
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at               TIMESTAMPTZ,

    -- Governance
    directive_ref           TEXT DEFAULT 'CEO-DIR-2026-FINN-006'
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Signal yield queries
CREATE INDEX idx_signal_yield_source
    ON fhq_research.signal_yield_tracking(source_tier, source_name);

CREATE INDEX idx_signal_yield_regime
    ON fhq_research.signal_yield_tracking(regime_id, domain);

CREATE INDEX idx_signal_yield_low
    ON fhq_research.signal_yield_tracking(signal_yield_ratio)
    WHERE signal_yield_ratio < 0.30;

CREATE INDEX idx_signal_yield_surprise
    ON fhq_research.signal_yield_tracking(is_surprise_sample)
    WHERE is_surprise_sample = TRUE;

-- Quota tracking
CREATE INDEX idx_surprise_quota_batch
    ON fhq_research.surprise_resampling_quota(batch_id);

-- ============================================================================
-- VIEW: Source Tier Performance Summary
-- For EC-021 to adjust retrieval priorities
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_source_tier_performance AS
SELECT
    source_tier,
    source_name,
    regime_id,
    COUNT(*) as total_queries,
    SUM(evidence_nodes_returned) as total_nodes_returned,
    SUM(evidence_nodes_used) as total_nodes_used,
    ROUND(AVG(signal_yield_ratio), 4) as avg_yield_ratio,
    SUM(query_cost_usd) as total_cost,
    ROUND(AVG(cost_per_signal), 6) as avg_cost_per_signal,
    COUNT(*) FILTER (WHERE signal_yield_ratio < 0.30) as low_yield_queries,
    ROUND(
        COUNT(*) FILTER (WHERE signal_yield_ratio < 0.30)::NUMERIC / NULLIF(COUNT(*), 0),
        4
    ) as low_yield_ratio
FROM fhq_research.signal_yield_tracking
GROUP BY source_tier, source_name, regime_id
ORDER BY avg_yield_ratio DESC;

-- ============================================================================
-- VIEW: Surprise Resampling Effectiveness
-- Monitors the anti-confirmation bias mechanism
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_surprise_resampling_effectiveness AS
SELECT
    q.batch_id,
    q.total_retrievals,
    q.surprise_quota_count,
    q.surprise_samples_used,
    q.signals_found,
    q.confirmed_noise,
    q.exploration_roi,
    CASE
        WHEN q.exploration_roi > 0.10 THEN 'HIGH_VALUE'
        WHEN q.exploration_roi > 0.05 THEN 'MODERATE_VALUE'
        ELSE 'LOW_VALUE'
    END as exploration_assessment
FROM fhq_research.surprise_resampling_quota q
ORDER BY q.created_at DESC;

-- ============================================================================
-- FUNCTION: Get adjusted retrieval priority
-- Returns priority based on historical yield
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.get_adjusted_priority(
    p_source_name TEXT,
    p_regime_id TEXT,
    p_default_priority NUMERIC DEFAULT 0.5
)
RETURNS NUMERIC AS $$
DECLARE
    v_avg_yield NUMERIC;
    v_adjusted_priority NUMERIC;
BEGIN
    -- Get average yield for this source/regime combination
    SELECT AVG(signal_yield_ratio)
    INTO v_avg_yield
    FROM fhq_research.signal_yield_tracking
    WHERE source_name = p_source_name
      AND regime_id = p_regime_id
      AND created_at > NOW() - INTERVAL '7 days';

    IF v_avg_yield IS NULL THEN
        -- No history, use default
        RETURN p_default_priority;
    END IF;

    -- Adjust priority based on yield
    -- High yield (>0.7) increases priority
    -- Low yield (<0.3) decreases priority
    v_adjusted_priority := p_default_priority + (v_avg_yield - 0.5) * 0.4;

    -- Clamp to [0.1, 0.9] range (never fully exclude, never fully trust)
    RETURN GREATEST(0.1, LEAST(0.9, v_adjusted_priority));
END;
$$ LANGUAGE plpgsql;

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
    '178_finn006_signal_yield_tracking',
    'DATABASE_MIGRATION',
    'STIG',
    'APPROVED',
    'CEO-DIR-2026-FINN-006 Section 3.2: EC-021 Signal-Yield Gating',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-FINN-006',
        'section', '3.2 EC-021 Signal-Yield Gating',
        'tables', ARRAY['signal_yield_tracking', 'surprise_resampling_quota'],
        'purpose', 'Transform InForage from cost-control to attention-control'
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
        AND table_name = 'signal_yield_tracking'
    ) THEN
        RAISE EXCEPTION 'Migration 178 FAILED: signal_yield_tracking not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_research'
        AND table_name = 'surprise_resampling_quota'
    ) THEN
        RAISE EXCEPTION 'Migration 178 FAILED: surprise_resampling_quota not created';
    END IF;

    RAISE NOTICE 'Migration 178 SUCCESS: signal_yield_tracking + surprise_resampling_quota created';
END $$;
