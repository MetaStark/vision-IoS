-- Migration 179: FINN-006 IKEA Feedback Log
-- CEO-DIR-2026-FINN-006: Adaptive Epistemic Learning Loop
-- Section 3.3: EC-022 IKEA Active Feedback
--
-- Purpose: IKEA outcomes shape subsequent runs. The system becomes
-- "selectively paranoid where it has learned to be wrong."
--
-- Authority: CEO APPROVED (2025-12-30T23:30:00Z)
-- Owner: EC-022 (IKEA)

BEGIN;

-- Ensure schema exists
CREATE SCHEMA IF NOT EXISTS fhq_research;

-- ============================================================================
-- TABLE: ikea_feedback_log
-- Logs IKEA boundary decisions and feeds constraints back into EC-020
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.ikea_feedback_log (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Run identification
    run_id                  UUID NOT NULL,
    batch_id                TEXT,
    run_number              INTEGER,

    -- Claim identification
    claim_id                UUID NOT NULL,
    claim_text              TEXT NOT NULL,
    claim_domain            TEXT,                   -- MACRO, CRYPTO, EQUITY, etc.

    -- IKEA Classification (EC-022)
    ikea_classification     TEXT NOT NULL CHECK (ikea_classification IN (
                                'PARAMETRIC',       -- Stable internal knowledge
                                'EXTERNAL_REQUIRED',-- Must retrieve external data
                                'HYBRID'            -- Combined stable + current
                            )),

    -- Classification drivers
    classification_reason   TEXT NOT NULL,
    volatility_class        TEXT CHECK (volatility_class IN (
                                'EXTREME',          -- Prices, live data
                                'HIGH',             -- Earnings, events
                                'MEDIUM',           -- Macro indicators
                                'LOW',              -- Historical patterns
                                'STATIC'            -- Formulas, definitions
                            )),

    -- Uncertainty tracking
    uncertainty_drivers     JSONB NOT NULL DEFAULT '[]'::JSONB,
    uncertainty_score       NUMERIC(5,4),           -- 0.0 = certain, 1.0 = fully uncertain
    confidence_before       NUMERIC(5,4),
    confidence_after        NUMERIC(5,4),

    -- Regime binding
    regime_id               TEXT NOT NULL,
    regime_triggered        BOOLEAN DEFAULT FALSE,  -- Did regime cause EXTERNAL_REQUIRED?

    -- LAKE quota tracking (CEO-DIR-2026-FINN-004)
    lake_quota_used         NUMERIC(5,4),           -- Current LAKE usage ratio
    lake_quota_breached     BOOLEAN DEFAULT FALSE,  -- Exceeded 30% LAKE cap
    lake_quota_forced_ext   BOOLEAN DEFAULT FALSE,  -- EXTERNAL_REQUIRED due to quota

    -- Feedback to EC-020
    feedback_type           TEXT CHECK (feedback_type IN (
                                'QUERY_SCOPE_NARROW',   -- Narrow future query scope
                                'LAKE_QUOTA_STRICT',    -- Stricter LAKE limits
                                'PATH_DOWN_WEIGHT',     -- Down-weight ontology path
                                'REGIME_SENSITIVITY',   -- Increase regime sensitivity
                                'NO_FEEDBACK'           -- Standard classification
                            )),
    feedback_target_path    TEXT[],                 -- Ontology path to affect
    feedback_strength       NUMERIC(5,4),           -- How strongly to apply feedback

    -- Pattern detection
    is_repeated_hybrid      BOOLEAN DEFAULT FALSE,  -- Same claim repeatedly HYBRID
    hybrid_count            INTEGER DEFAULT 1,      -- Times this pattern seen
    pattern_id              UUID,                   -- Links related patterns

    -- Outcome tracking (post-run)
    outcome_verified        BOOLEAN,                -- Was IKEA decision correct?
    outcome_notes           TEXT,
    verification_timestamp  TIMESTAMPTZ,

    -- Timestamps
    classified_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Governance
    directive_ref           TEXT DEFAULT 'CEO-DIR-2026-FINN-006'
);

-- ============================================================================
-- TABLE: ikea_pattern_registry
-- Tracks repeated HYBRID patterns that trigger stricter constraints
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.ikea_pattern_registry (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Pattern identification
    pattern_hash            TEXT NOT NULL UNIQUE,   -- Hash of claim domain + drivers
    pattern_domain          TEXT NOT NULL,
    pattern_drivers         JSONB NOT NULL,

    -- Occurrence tracking
    first_seen_run          INTEGER NOT NULL,
    last_seen_run           INTEGER NOT NULL,
    occurrence_count        INTEGER NOT NULL DEFAULT 1,

    -- Escalation state
    escalation_level        INTEGER NOT NULL DEFAULT 0 CHECK (escalation_level BETWEEN 0 AND 3),
    -- 0 = Normal
    -- 1 = Watch (3+ occurrences)
    -- 2 = Narrow (5+ occurrences)
    -- 3 = Strict (10+ occurrences)

    escalation_actions      JSONB DEFAULT '[]'::JSONB,

    -- Regime association
    primary_regime          TEXT,
    regime_correlation      NUMERIC(5,4),           -- How regime-specific is this pattern

    -- Learning signals
    query_scope_modifier    NUMERIC(5,4) DEFAULT 1.0,  -- 1.0 = normal, <1.0 = narrower
    lake_quota_modifier     NUMERIC(5,4) DEFAULT 1.0,  -- 1.0 = normal, <1.0 = stricter

    -- Status
    is_active               BOOLEAN DEFAULT TRUE,
    suppressed_reason       TEXT,

    -- Timestamps
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Governance
    directive_ref           TEXT DEFAULT 'CEO-DIR-2026-FINN-006'
);

-- ============================================================================
-- TABLE: ec020_constraint_feedback
-- Constraints fed back from IKEA to EC-020 for query formation
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.ec020_constraint_feedback (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source tracking
    source_pattern_id       UUID REFERENCES fhq_research.ikea_pattern_registry(id),
    source_feedback_log_id  UUID REFERENCES fhq_research.ikea_feedback_log(id),

    -- Constraint definition
    constraint_type         TEXT NOT NULL CHECK (constraint_type IN (
                                'SCOPE_LIMIT',          -- Limit query scope
                                'PATH_EXCLUSION',       -- Exclude ontology path
                                'PATH_DOWN_WEIGHT',     -- Reduce path priority
                                'LAKE_QUOTA_OVERRIDE',  -- Stricter LAKE limit
                                'REGIME_GATE',          -- Gate by regime
                                'MANDATORY_EXTERNAL'    -- Always require external
                            )),

    -- Constraint parameters
    target_ontology_path    TEXT[],
    target_domain           TEXT,
    target_regime           TEXT,                   -- NULL = all regimes

    -- Constraint strength
    weight_modifier         NUMERIC(5,4),           -- Multiplier for priority
    quota_modifier          NUMERIC(5,4),           -- Multiplier for quota
    scope_modifier          NUMERIC(5,4),           -- Multiplier for scope

    -- Validity
    valid_from              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until             TIMESTAMPTZ,            -- NULL = indefinite
    is_active               BOOLEAN DEFAULT TRUE,

    -- Effectiveness tracking
    times_applied           INTEGER DEFAULT 0,
    effectiveness_score     NUMERIC(5,4),           -- Did constraint improve outcomes?

    -- Governance
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    directive_ref           TEXT DEFAULT 'CEO-DIR-2026-FINN-006'
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Feedback log queries
CREATE INDEX idx_ikea_feedback_run
    ON fhq_research.ikea_feedback_log(run_id);

CREATE INDEX idx_ikea_feedback_classification
    ON fhq_research.ikea_feedback_log(ikea_classification);

CREATE INDEX idx_ikea_feedback_hybrid
    ON fhq_research.ikea_feedback_log(is_repeated_hybrid)
    WHERE is_repeated_hybrid = TRUE;

CREATE INDEX idx_ikea_feedback_regime
    ON fhq_research.ikea_feedback_log(regime_id, claim_domain);

-- Pattern registry
CREATE INDEX idx_ikea_pattern_escalation
    ON fhq_research.ikea_pattern_registry(escalation_level DESC)
    WHERE is_active = TRUE;

CREATE INDEX idx_ikea_pattern_domain
    ON fhq_research.ikea_pattern_registry(pattern_domain);

-- Constraint feedback
CREATE INDEX idx_ec020_constraint_active
    ON fhq_research.ec020_constraint_feedback(is_active, constraint_type)
    WHERE is_active = TRUE;

CREATE INDEX idx_ec020_constraint_path
    ON fhq_research.ec020_constraint_feedback USING GIN(target_ontology_path)
    WHERE is_active = TRUE;

-- ============================================================================
-- VIEW: IKEA Classification Distribution
-- Monitor IKEA decision patterns per regime
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_ikea_classification_distribution AS
SELECT
    regime_id,
    claim_domain,
    ikea_classification,
    COUNT(*) as classification_count,
    ROUND(
        COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER (PARTITION BY regime_id, claim_domain),
        4
    ) as classification_ratio,
    AVG(uncertainty_score) as avg_uncertainty,
    COUNT(*) FILTER (WHERE lake_quota_breached = TRUE) as lake_breaches,
    COUNT(*) FILTER (WHERE regime_triggered = TRUE) as regime_triggers
FROM fhq_research.ikea_feedback_log
GROUP BY regime_id, claim_domain, ikea_classification
ORDER BY regime_id, claim_domain, classification_count DESC;

-- ============================================================================
-- VIEW: Escalated Patterns Requiring Attention
-- Patterns that have triggered constraint feedback
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_escalated_patterns AS
SELECT
    p.id as pattern_id,
    p.pattern_domain,
    p.occurrence_count,
    p.escalation_level,
    CASE p.escalation_level
        WHEN 0 THEN 'NORMAL'
        WHEN 1 THEN 'WATCH'
        WHEN 2 THEN 'NARROW'
        WHEN 3 THEN 'STRICT'
    END as escalation_status,
    p.query_scope_modifier,
    p.lake_quota_modifier,
    p.primary_regime,
    COUNT(c.id) as active_constraints
FROM fhq_research.ikea_pattern_registry p
LEFT JOIN fhq_research.ec020_constraint_feedback c
    ON c.source_pattern_id = p.id AND c.is_active = TRUE
WHERE p.is_active = TRUE
  AND p.escalation_level > 0
GROUP BY p.id
ORDER BY p.escalation_level DESC, p.occurrence_count DESC;

-- ============================================================================
-- FUNCTION: Update pattern escalation
-- Called after each IKEA feedback log entry
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.update_pattern_escalation(
    p_pattern_id UUID
)
RETURNS VOID AS $$
DECLARE
    v_count INTEGER;
    v_new_level INTEGER;
BEGIN
    -- Get occurrence count
    SELECT occurrence_count INTO v_count
    FROM fhq_research.ikea_pattern_registry
    WHERE id = p_pattern_id;

    -- Determine escalation level
    v_new_level := CASE
        WHEN v_count >= 10 THEN 3  -- STRICT
        WHEN v_count >= 5 THEN 2   -- NARROW
        WHEN v_count >= 3 THEN 1   -- WATCH
        ELSE 0                      -- NORMAL
    END;

    -- Update pattern
    UPDATE fhq_research.ikea_pattern_registry
    SET
        escalation_level = v_new_level,
        query_scope_modifier = CASE
            WHEN v_new_level = 3 THEN 0.5   -- 50% scope reduction
            WHEN v_new_level = 2 THEN 0.7   -- 30% scope reduction
            WHEN v_new_level = 1 THEN 0.9   -- 10% scope reduction
            ELSE 1.0
        END,
        lake_quota_modifier = CASE
            WHEN v_new_level = 3 THEN 0.5   -- 50% LAKE reduction (15% cap)
            WHEN v_new_level = 2 THEN 0.7   -- 70% LAKE (21% cap)
            WHEN v_new_level = 1 THEN 0.9   -- 90% LAKE (27% cap)
            ELSE 1.0
        END,
        updated_at = NOW()
    WHERE id = p_pattern_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Get active constraints for EC-020
-- Returns constraints applicable to a given query context
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.get_active_constraints(
    p_ontology_path TEXT[],
    p_domain TEXT,
    p_regime_id TEXT
)
RETURNS TABLE (
    constraint_type TEXT,
    weight_modifier NUMERIC,
    quota_modifier NUMERIC,
    scope_modifier NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.constraint_type,
        c.weight_modifier,
        c.quota_modifier,
        c.scope_modifier
    FROM fhq_research.ec020_constraint_feedback c
    WHERE c.is_active = TRUE
      AND (c.valid_until IS NULL OR c.valid_until > NOW())
      AND (
          c.target_ontology_path && p_ontology_path  -- Path overlap
          OR c.target_domain = p_domain
          OR c.target_regime = p_regime_id
          OR (c.target_regime IS NULL AND c.target_domain IS NULL)  -- Global constraint
      );
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
    '179_finn006_ikea_feedback_log',
    'DATABASE_MIGRATION',
    'STIG',
    'APPROVED',
    'CEO-DIR-2026-FINN-006 Section 3.3: EC-022 IKEA Active Feedback',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-FINN-006',
        'section', '3.3 EC-022 IKEA Active Feedback',
        'tables', ARRAY['ikea_feedback_log', 'ikea_pattern_registry', 'ec020_constraint_feedback'],
        'purpose', 'System becomes selectively paranoid where it has learned to be wrong'
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
        AND table_name = 'ikea_feedback_log'
    ) THEN
        RAISE EXCEPTION 'Migration 179 FAILED: ikea_feedback_log not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_research'
        AND table_name = 'ikea_pattern_registry'
    ) THEN
        RAISE EXCEPTION 'Migration 179 FAILED: ikea_pattern_registry not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_research'
        AND table_name = 'ec020_constraint_feedback'
    ) THEN
        RAISE EXCEPTION 'Migration 179 FAILED: ec020_constraint_feedback not created';
    END IF;

    RAISE NOTICE 'Migration 179 SUCCESS: IKEA feedback infrastructure created';
END $$;
