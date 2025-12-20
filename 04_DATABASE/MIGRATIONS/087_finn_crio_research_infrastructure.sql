-- ============================================================================
-- MIGRATION 087: FINN CRIO RESEARCH INFRASTRUCTURE
-- ============================================================================
-- Authority: CEO Directive - ACTIVATE FINN DEEPSEEK RESEARCH ENGINE
-- Reference: ADR-017 (MIT Quad Protocol), EC-004 (FINN Contract)
-- Generated: 2025-12-08
--
-- PURPOSE:
--   Create infrastructure for FINN CRIO DeepSeek research engine:
--   - fhq_research.nightly_insights (canonical research outputs)
--   - fhq_governance.research_log (audit trail)
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: NIGHTLY INSIGHTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.nightly_insights (
    -- Primary Key
    insight_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Temporal
    research_date DATE NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    -- Engine Metadata
    engine_version VARCHAR(50) NOT NULL,

    -- Core CRIO Outputs
    fragility_score DECIMAL(5,4) NOT NULL CHECK (fragility_score >= 0 AND fragility_score <= 1),
    dominant_driver VARCHAR(50) NOT NULL CHECK (dominant_driver IN ('LIQUIDITY', 'CREDIT', 'VOLATILITY', 'SENTIMENT', 'UNKNOWN')),
    regime_assessment VARCHAR(50) NOT NULL CHECK (regime_assessment IN ('STRONG_BULL', 'BULL', 'NEUTRAL', 'BEAR', 'STRONG_BEAR', 'UNCERTAIN')),
    confidence DECIMAL(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),

    -- Analysis Details
    key_observations JSONB NOT NULL DEFAULT '[]',
    risk_factors JSONB NOT NULL DEFAULT '[]',
    reasoning_summary TEXT NOT NULL,

    -- Sovereignty Validation
    context_hash VARCHAR(64) NOT NULL,
    quad_hash VARCHAR(16) NOT NULL,
    lids_verified BOOLEAN NOT NULL DEFAULT FALSE,
    risl_verified BOOLEAN NOT NULL DEFAULT FALSE,

    -- Cryptographic
    finn_signature VARCHAR(64) NOT NULL
);

-- Index for date-based queries
CREATE INDEX IF NOT EXISTS idx_nightly_insights_date ON fhq_research.nightly_insights(research_date DESC);

-- Index for fragility monitoring
CREATE INDEX IF NOT EXISTS idx_nightly_insights_fragility ON fhq_research.nightly_insights(fragility_score DESC);

COMMENT ON TABLE fhq_research.nightly_insights IS
'FINN CRIO canonical research outputs. One row per day. ADR-017 compliant.';

COMMENT ON COLUMN fhq_research.nightly_insights.fragility_score IS
'Market fragility score 0.0-1.0. >0.8 triggers defensive mode.';

COMMENT ON COLUMN fhq_research.nightly_insights.quad_hash IS
'MIT Quad validation hash (LIDS|ACL|RISL|DSL state)';


-- ============================================================================
-- SECTION 2: RESEARCH LOG TABLE (Governance Audit)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.research_log (
    -- Primary Key
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Research Reference
    research_id UUID NOT NULL,
    agent_id VARCHAR(20) NOT NULL,
    engine_version VARCHAR(50) NOT NULL,

    -- Event Details
    event_type VARCHAR(50) NOT NULL,
    quad_hash VARCHAR(16),
    context_hash VARCHAR(64),
    decision_trace JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(50) NOT NULL,

    -- Temporal
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for research_id lookup
CREATE INDEX IF NOT EXISTS idx_research_log_research_id ON fhq_governance.research_log(research_id);

-- Index for agent queries
CREATE INDEX IF NOT EXISTS idx_research_log_agent ON fhq_governance.research_log(agent_id, created_at DESC);

-- Index for event type
CREATE INDEX IF NOT EXISTS idx_research_log_event ON fhq_governance.research_log(event_type);

COMMENT ON TABLE fhq_governance.research_log IS
'FINN CRIO research audit log. Required for G2->G3 governance progression.';


-- ============================================================================
-- SECTION 3: REGISTER IN IOS REGISTRY
-- ============================================================================

INSERT INTO fhq_meta.ios_registry (
    ios_id,
    title,
    description,
    version,
    status,
    owner_role,
    governing_adrs,
    content_hash,
    created_at
) VALUES (
    'IoS-006.CRIO',
    'FINN CRIO Research Engine',
    'DeepSeek-powered research engine for FINN. Replaces RNG mock with real LLM analysis.',
    '1.0.0',
    'ACTIVE',
    'FINN',
    ARRAY['ADR-017', 'ADR-012'],
    encode(sha256('IoS-006.CRIO:FINN_CRIO_Research_Engine:1.0.0'::bytea), 'hex'),
    NOW()
) ON CONFLICT (ios_id) DO UPDATE SET
    status = 'ACTIVE',
    description = EXCLUDED.description;


-- ============================================================================
-- SECTION 4: LOG MIGRATION
-- ============================================================================

INSERT INTO fhq_meta.ios_audit_log (
    audit_id,
    ios_id,
    event_type,
    event_timestamp,
    actor,
    gate_level,
    event_data,
    created_at
) VALUES (
    gen_random_uuid(),
    'IoS-006.CRIO',
    'CRIO_INFRASTRUCTURE_CREATED',
    NOW(),
    'STIG',
    'G1',
    jsonb_build_object(
        'migration', '087_finn_crio_research_infrastructure',
        'tables_created', ARRAY['fhq_research.nightly_insights', 'fhq_governance.research_log'],
        'authority', 'CEO Directive',
        'timestamp', NOW()
    ),
    NOW()
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    -- Verify nightly_insights table
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_research' AND table_name = 'nightly_insights'
    ) THEN
        RAISE EXCEPTION 'nightly_insights table not created';
    END IF;

    -- Verify research_log table
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_governance' AND table_name = 'research_log'
    ) THEN
        RAISE EXCEPTION 'research_log table not created';
    END IF;

    RAISE NOTICE 'Migration 087 completed successfully';
    RAISE NOTICE 'FINN CRIO infrastructure ready';
END $$;
