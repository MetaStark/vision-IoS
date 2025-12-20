-- ============================================================================
-- Migration 142: EC-018 Alpha Discovery Schema
-- ============================================================================
-- CEO Directive: CD-EXEC-EC018-DEEPSEEK-ALPHA-001 (Improved)
-- Date: 2025-12-14
-- Executor: STIG (CTO)
--
-- This migration creates the infrastructure for EC-018 Meta-Alpha operations:
-- 1. G0 Draft Proposals table for alpha hypotheses
-- 2. State Vector schema for market perception
-- 3. Alpha hunt sessions tracking
-- 4. Executive summary storage
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: CREATE ALPHA DISCOVERY SCHEMA NAMESPACE
-- ============================================================================

-- Create schema if not exists (under fhq_research domain)
CREATE SCHEMA IF NOT EXISTS fhq_alpha;

COMMENT ON SCHEMA fhq_alpha IS 'EC-018 Meta-Alpha & Freedom Optimizer - Alpha Discovery Infrastructure';

-- Grant appropriate permissions
GRANT USAGE ON SCHEMA fhq_alpha TO PUBLIC;

-- ============================================================================
-- SECTION 2: STATE VECTOR TABLE
-- Per CD-EXEC-EC018-DEEPSEEK-ALPHA-001 Improvement #2
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.state_vectors (
    state_vector_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Timestamp
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ADR-018 State Discipline: Cryptographic State Hash
    -- This hash locks the entire state snapshot for audit purposes
    state_hash TEXT NOT NULL,  -- SHA-256 of all state fields at capture time

    -- Market State (IoS-003 regime perception)
    market_regime TEXT NOT NULL,  -- BULL, BEAR, NEUTRAL, STRESS
    regime_confidence DECIMAL(5,4) NOT NULL CHECK (regime_confidence BETWEEN 0 AND 1),

    -- Key Metrics
    btc_price DECIMAL(20,8),
    btc_24h_change DECIMAL(10,4),
    vix_value DECIMAL(10,4),
    yield_spread DECIMAL(10,4),

    -- Perception Summary
    perception_summary JSONB NOT NULL DEFAULT '{}',

    -- Active Anomalies (IoS-009)
    active_anomalies JSONB NOT NULL DEFAULT '[]',

    -- DEFCON Level (ADR-016)
    defcon_level INTEGER NOT NULL DEFAULT 5 CHECK (defcon_level BETWEEN 1 AND 5),

    -- LLM Budget Status
    daily_budget_remaining DECIMAL(10,4),
    daily_budget_cap DECIMAL(10,4) DEFAULT 2.00,

    -- Metadata
    source_agent TEXT NOT NULL DEFAULT 'EC-018',
    lineage_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ADR-018 Immutability constraint
    CONSTRAINT state_vectors_immutable CHECK (
        -- Once created, state vectors cannot be modified (enforced by app layer)
        captured_at IS NOT NULL AND state_hash IS NOT NULL
    )
);

CREATE INDEX idx_state_vectors_captured_at ON fhq_alpha.state_vectors(captured_at DESC);
CREATE INDEX idx_state_vectors_regime ON fhq_alpha.state_vectors(market_regime);

COMMENT ON TABLE fhq_alpha.state_vectors IS 'Market state snapshots for EC-018 alpha discovery context';

-- ============================================================================
-- SECTION 3: G0 DRAFT PROPOSALS TABLE
-- Per CD-EXEC-EC018-DEEPSEEK-ALPHA-001 Improvement #4
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.g0_draft_proposals (
    proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Session Link
    hunt_session_id UUID NOT NULL,

    -- Hypothesis Identity
    hypothesis_id TEXT NOT NULL,  -- e.g., "ALPHA-2025-12-14-001"
    hypothesis_title TEXT NOT NULL,
    hypothesis_category TEXT NOT NULL,  -- REGIME_EDGE, CROSS_ASSET, TIMING, STRUCTURAL

    -- Core Hypothesis
    hypothesis_statement TEXT NOT NULL,  -- The falsifiable claim
    expected_edge_bps INTEGER,  -- Expected edge in basis points
    confidence_score DECIMAL(5,4) CHECK (confidence_score BETWEEN 0 AND 1),

    -- Evidence & Rationale
    supporting_evidence JSONB NOT NULL DEFAULT '[]',
    data_sources_used JSONB NOT NULL DEFAULT '[]',
    assumptions TEXT[] NOT NULL DEFAULT '{}',

    -- Executive Summary (Human-readable)
    executive_summary TEXT NOT NULL,  -- Why this is smart, in plain language
    risk_factors TEXT[] NOT NULL DEFAULT '{}',

    -- Falsification Criteria
    falsification_criteria JSONB NOT NULL,  -- How to prove/disprove
    backtest_requirements JSONB,  -- Required backtest parameters

    -- Governance Binding & Pipeline Targeting
    -- EC-018 has ZERO execution authority - this is a HARD constitutional constraint
    execution_authority TEXT NOT NULL DEFAULT 'NONE' CHECK (execution_authority = 'NONE'),

    -- Pipeline: EC-018 → IoS-004 → IoS-008 → IoS-012
    ios_target TEXT DEFAULT 'IoS-004',  -- Next step: backtest validation
    downstream_pipeline JSONB NOT NULL DEFAULT '["IoS-004", "IoS-008", "IoS-012"]'::jsonb,
    requires_g1_review BOOLEAN DEFAULT TRUE,

    -- Falsifiability (required for valid G0 proposal per scientific method)
    falsifiability_validated BOOLEAN NOT NULL DEFAULT FALSE,
    falsifiability_statement TEXT,  -- How can this hypothesis be proven wrong?

    -- Token Economics
    tokens_consumed INTEGER NOT NULL DEFAULT 0,
    cost_usd DECIMAL(10,6) NOT NULL DEFAULT 0,

    -- Status (G0 = Hypothesis Only, zero execution authority)
    proposal_status TEXT NOT NULL DEFAULT 'G0_DRAFT'
        CHECK (proposal_status IN ('G0_DRAFT', 'G0_SUBMITTED', 'G1_REVIEW', 'G1_APPROVED', 'G1_REJECTED', 'EXPIRED')),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    reviewed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 days',

    -- ADR-018 State Binding
    state_vector_id UUID NOT NULL REFERENCES fhq_alpha.state_vectors(state_vector_id),
    state_hash_at_creation TEXT NOT NULL,  -- Snapshot of state_hash for audit
    lineage_hash TEXT,

    -- Quality Metrics (post-review)
    novelty_score DECIMAL(5,4),  -- How novel is this hypothesis?
    actionability_score DECIMAL(5,4),  -- How actionable is it?
    reviewer_notes TEXT
);

CREATE INDEX idx_g0_proposals_session ON fhq_alpha.g0_draft_proposals(hunt_session_id);
CREATE INDEX idx_g0_proposals_status ON fhq_alpha.g0_draft_proposals(proposal_status);
CREATE INDEX idx_g0_proposals_category ON fhq_alpha.g0_draft_proposals(hypothesis_category);
CREATE INDEX idx_g0_proposals_created ON fhq_alpha.g0_draft_proposals(created_at DESC);

COMMENT ON TABLE fhq_alpha.g0_draft_proposals IS 'G0 Draft Alpha Hypotheses from EC-018 Meta-Alpha sessions';

-- ============================================================================
-- SECTION 4: ALPHA HUNT SESSIONS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.hunt_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Session Identity
    session_name TEXT NOT NULL,
    initiated_by TEXT NOT NULL DEFAULT 'CEO',  -- Who triggered the hunt

    -- Configuration
    focus_areas JSONB NOT NULL DEFAULT '[]',  -- Specific areas to investigate
    budget_cap_usd DECIMAL(10,4) NOT NULL DEFAULT 2.00,
    token_cap INTEGER DEFAULT 50000,  -- Token backstop per improvement #1

    -- Model Configuration (per improvement #3)
    primary_model TEXT NOT NULL DEFAULT 'deepseek-chat',  -- V3 for broad reasoning
    reasoning_model TEXT DEFAULT 'deepseek-reasoner',  -- R1 for deep analysis

    -- State Vector at Start
    initial_state_vector_id UUID REFERENCES fhq_alpha.state_vectors(state_vector_id),

    -- Session Metrics
    total_tokens_in INTEGER DEFAULT 0,
    total_tokens_out INTEGER DEFAULT 0,
    total_cost_usd DECIMAL(10,6) DEFAULT 0,
    hypotheses_generated INTEGER DEFAULT 0,

    -- Status
    session_status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (session_status IN ('ACTIVE', 'COMPLETED', 'BUDGET_EXHAUSTED', 'TOKEN_CAP_HIT', 'ABORTED', 'ERROR')),

    -- Timestamps
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Results Summary
    session_summary JSONB,
    top_hypotheses JSONB,  -- Quick reference to best findings

    -- Governance
    governance_event_id UUID,
    lineage_hash TEXT
);

CREATE INDEX idx_hunt_sessions_status ON fhq_alpha.hunt_sessions(session_status);
CREATE INDEX idx_hunt_sessions_started ON fhq_alpha.hunt_sessions(started_at DESC);

COMMENT ON TABLE fhq_alpha.hunt_sessions IS 'EC-018 Alpha Hunt session tracking with budget/token controls';

-- ============================================================================
-- SECTION 5: TELEMETRY LINK (Per Improvement #5)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.hunt_telemetry (
    telemetry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Links
    session_id UUID NOT NULL REFERENCES fhq_alpha.hunt_sessions(session_id),
    envelope_id UUID,  -- Link to fhq_governance.llm_routing_log

    -- Call Details
    call_sequence INTEGER NOT NULL,
    model_used TEXT NOT NULL,
    call_purpose TEXT NOT NULL,  -- 'state_analysis', 'hypothesis_generation', 'deep_reasoning'

    -- Token Metrics
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    cost_usd DECIMAL(10,6) NOT NULL,
    latency_ms INTEGER,

    -- Running Totals
    cumulative_tokens INTEGER NOT NULL,
    cumulative_cost_usd DECIMAL(10,6) NOT NULL,
    budget_remaining DECIMAL(10,6) NOT NULL,

    -- Timestamps
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_hunt_telemetry_session ON fhq_alpha.hunt_telemetry(session_id);

COMMENT ON TABLE fhq_alpha.hunt_telemetry IS 'Per-call telemetry for EC-018 alpha hunt sessions';

-- ============================================================================
-- SECTION 6: REGISTER SCHEMA IN ADR REGISTRY
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id,
    adr_status,
    adr_title,
    title,
    description,
    rationale,
    governance_tier,
    owner,
    constitutional_authority,
    affects,
    approval_authority,
    effective_date,
    status,
    created_at,
    updated_at
) VALUES (
    'SCHEMA-ALPHA',
    'APPROVED',
    'Alpha Discovery Schema',
    'fhq_alpha Schema Registration',
    'Database schema for EC-018 Meta-Alpha & Freedom Optimizer operations. Stores state vectors, G0 draft proposals, hunt sessions, and telemetry.',
    'Required infrastructure for CD-EXEC-EC018-DEEPSEEK-ALPHA-001 directive implementation.',
    'TIER-3',
    'STIG',
    'EC-018, ADR-003, ADR-013',
    ARRAY['EC-018', 'FINN', 'LARS', 'IoS-004'],
    'CEO',
    CURRENT_DATE,
    'ACTIVE',
    NOW(),
    NOW()
)
ON CONFLICT (adr_id) DO UPDATE SET
    status = 'ACTIVE',
    updated_at = NOW();

-- ============================================================================
-- SECTION 7: LOG GOVERNANCE EVENT
-- ============================================================================

INSERT INTO fhq_governance.system_events (
    event_id,
    event_type,
    event_category,
    event_severity,
    source_agent,
    source_component,
    source_ios_layer,
    event_title,
    event_description,
    event_data,
    lineage_hash,
    created_at
) VALUES (
    gen_random_uuid(),
    'SCHEMA_CREATED',
    'INFRASTRUCTURE',
    'INFO',
    'STIG',
    'EC-018',
    'META',
    'Alpha Discovery Schema Created',
    'Migration 142: Created fhq_alpha schema with state_vectors, g0_draft_proposals, hunt_sessions, and hunt_telemetry tables per CD-EXEC-EC018-DEEPSEEK-ALPHA-001.',
    jsonb_build_object(
        'migration', '142_ec018_alpha_discovery_schema.sql',
        'directive', 'CD-EXEC-EC018-DEEPSEEK-ALPHA-001',
        'tables_created', ARRAY['state_vectors', 'g0_draft_proposals', 'hunt_sessions', 'hunt_telemetry'],
        'improvements_implemented', ARRAY[
            'Budget cap with token backstop',
            'State Vector Schema',
            'Model mapping (V3/R1)',
            'G0 Draft Proposal Schema',
            'Telemetry reporting'
        ]
    ),
    encode(sha256('MIGRATION-142|fhq_alpha|2025-12-14|STIG'::bytea), 'hex'),
    NOW()
);

COMMIT;

-- ============================================================================
-- MIGRATION 142 SUMMARY
-- ============================================================================
--
-- SCHEMA CREATED: fhq_alpha
--
-- TABLES:
-- [CREATED] fhq_alpha.state_vectors - Market state snapshots
-- [CREATED] fhq_alpha.g0_draft_proposals - Alpha hypotheses (G0 drafts)
-- [CREATED] fhq_alpha.hunt_sessions - Hunt session tracking
-- [CREATED] fhq_alpha.hunt_telemetry - Per-call telemetry
--
-- CD-EXEC-EC018-DEEPSEEK-ALPHA-001 IMPROVEMENTS IMPLEMENTED:
-- [1] Budget cap with token backstop (50k tokens)
-- [2] State Vector Schema defined
-- [3] Model mapping (V3 -> deepseek-chat, R1 -> deepseek-reasoner)
-- [4] G0 Draft Proposal Schema with executive summaries
-- [5] Telemetry reporting mechanism
--
-- REMAINING (Code-level):
-- [6] API endpoint contract (/api/alpha/hunt)
-- [7] IoS-004 pipeline binding
-- [8] VEGA security trigger
-- ============================================================================
