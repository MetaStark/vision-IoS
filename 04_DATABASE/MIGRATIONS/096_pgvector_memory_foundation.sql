-- ============================================================================
-- MIGRATION 096: PGVECTOR MEMORY FOUNDATION
-- ============================================================================
-- CEO DIRECTIVE: ARO-20251208 (Autonomy Restoration Order)
-- Authority: Tier-1 Executive Mandate
-- ADR Binding: ADR-007, ADR-013, ADR-014, ADR-015, ADR-016
-- Gate: G0→G4 Architecture Alignment
-- Executor: STIG (CTO) - EC-003_2026_PRODUCTION
-- ============================================================================
-- PURPOSE: Install the "brain" - pgvector extension and fhq_memory schema
-- This is the foundation for agent memory, semantic search, and learning.
-- Without this, DeepSeek/FINN cannot store embeddings, no semantic search.
-- ============================================================================

-- Migration metadata
DO $$
BEGIN
    RAISE NOTICE '=== MIGRATION 096: PGVECTOR MEMORY FOUNDATION ===';
    RAISE NOTICE 'CEO DIRECTIVE: ARO-20251208';
    RAISE NOTICE 'Executor: STIG (CTO)';
    RAISE NOTICE 'Timestamp: %', NOW();
END $$;

-- ============================================================================
-- SECTION 1: INSTALL PGVECTOR EXTENSION
-- ============================================================================
-- Note: This requires superuser privileges. If running on Supabase,
-- pgvector may need to be enabled via dashboard or support request.

CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE NOTICE 'SUCCESS: pgvector extension installed';
    ELSE
        RAISE WARNING 'pgvector extension not available - contact database admin';
    END IF;
END $$;

-- ============================================================================
-- SECTION 2: CREATE FHQ_MEMORY SCHEMA
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS fhq_memory;

COMMENT ON SCHEMA fhq_memory IS
'FjordHQ Agent Memory System - ARO-20251208
Provides persistent memory, embeddings, and semantic search for autonomous agents.
ADR-013 Canonical Schema. VEGA auditable.';

-- ============================================================================
-- SECTION 3: EMBEDDING STORE (Core Vector Storage)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_memory.embedding_store (
    embedding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Content identification
    content_hash VARCHAR(64) NOT NULL,  -- SHA256 of original content
    content_type VARCHAR(50) NOT NULL,  -- 'research_note', 'signal', 'regime_analysis', etc.
    source_agent VARCHAR(20) NOT NULL,  -- FINN, CEIO, LARS, LINE, VEGA, STIG
    source_reference VARCHAR(255),       -- External reference ID

    -- The actual embedding vector (1536 for OpenAI ada-002, 3072 for text-embedding-3-large)
    embedding vector(1536),

    -- Content metadata
    content_text TEXT,                   -- Original text (for debugging/audit)
    content_summary VARCHAR(500),        -- Brief summary

    -- Regime-gated retrieval (MANDATORY per ARO-20251208 Section 8.1)
    regime VARCHAR(20) NOT NULL,         -- BULL, BEAR, SIDEWAYS, CRISIS, UNKNOWN
    regime_confidence DECIMAL(5,4),      -- 0.0000 to 1.0000

    -- Temporal decay (ARO-20251208 Section 8.2)
    relevance_score DECIMAL(5,4) DEFAULT 1.0000,
    decay_factor DECIMAL(5,4) DEFAULT 0.1000,  -- λ in decay formula
    last_used_at TIMESTAMP WITH TIME ZONE,
    use_count INTEGER DEFAULT 0,

    -- Permanent truth flag (bypasses decay)
    is_eternal_truth BOOLEAN DEFAULT FALSE,
    eternal_truth_tag VARCHAR(50),       -- e.g., 'PERMANENT_CAUSAL'

    -- Lineage and audit
    lineage_hash VARCHAR(64),            -- SHA256 chain
    parent_embedding_id UUID REFERENCES fhq_memory.embedding_store(embedding_id),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,  -- Optional TTL

    -- Constraints
    CONSTRAINT valid_regime CHECK (regime IN ('BULL', 'BEAR', 'SIDEWAYS', 'CRISIS', 'UNKNOWN')),
    CONSTRAINT valid_agent CHECK (source_agent IN ('FINN', 'CEIO', 'LARS', 'LINE', 'VEGA', 'STIG', 'SYSTEM'))
);

-- Index for regime-gated vector search (CRITICAL for performance)
CREATE INDEX IF NOT EXISTS idx_embedding_regime_vector
    ON fhq_memory.embedding_store USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_embedding_regime
    ON fhq_memory.embedding_store(regime);

CREATE INDEX IF NOT EXISTS idx_embedding_agent
    ON fhq_memory.embedding_store(source_agent);

CREATE INDEX IF NOT EXISTS idx_embedding_created
    ON fhq_memory.embedding_store(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_embedding_content_hash
    ON fhq_memory.embedding_store(content_hash);

COMMENT ON TABLE fhq_memory.embedding_store IS
'Core vector storage for semantic memory. All queries MUST use regime filter per ARO-20251208.';

-- ============================================================================
-- SECTION 4: AGENT MEMORY (Short-term Semantic Memory)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_memory.agent_memory (
    memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Agent identification
    agent_id VARCHAR(20) NOT NULL,
    session_id UUID,

    -- Memory content
    memory_type VARCHAR(30) NOT NULL,    -- 'working', 'attention', 'context', 'goal'
    memory_key VARCHAR(100) NOT NULL,    -- Unique key within agent context
    memory_value JSONB NOT NULL,

    -- Regime context (MANDATORY)
    regime VARCHAR(20) NOT NULL,

    -- Priority and relevance
    priority INTEGER DEFAULT 5,          -- 1-10, higher = more important
    relevance_score DECIMAL(5,4) DEFAULT 1.0000,
    decay_factor DECIMAL(5,4) DEFAULT 0.2000,

    -- Embedding reference (optional)
    embedding_id UUID REFERENCES fhq_memory.embedding_store(embedding_id),

    -- Lineage
    lineage_hash VARCHAR(64),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT valid_memory_regime CHECK (regime IN ('BULL', 'BEAR', 'SIDEWAYS', 'CRISIS', 'UNKNOWN')),
    CONSTRAINT valid_memory_agent CHECK (agent_id IN ('FINN', 'CEIO', 'LARS', 'LINE', 'VEGA', 'STIG', 'SYSTEM')),
    CONSTRAINT unique_agent_memory_key UNIQUE (agent_id, memory_key, regime)
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_agent_regime
    ON fhq_memory.agent_memory(agent_id, regime);

CREATE INDEX IF NOT EXISTS idx_agent_memory_type
    ON fhq_memory.agent_memory(memory_type);

CREATE INDEX IF NOT EXISTS idx_agent_memory_expires
    ON fhq_memory.agent_memory(expires_at) WHERE expires_at IS NOT NULL;

COMMENT ON TABLE fhq_memory.agent_memory IS
'Short-term working memory for agents. Regime-filtered access required.';

-- ============================================================================
-- SECTION 5: EPISODIC MEMORY (Historical State)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_memory.episodic_memory (
    episode_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Episode identification
    episode_type VARCHAR(50) NOT NULL,   -- 'market_event', 'decision', 'trade', 'regime_shift', 'crisis'
    episode_title VARCHAR(200),
    episode_description TEXT,

    -- Temporal bounds
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ended_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,

    -- Context
    regime_at_start VARCHAR(20) NOT NULL,
    regime_at_end VARCHAR(20),

    -- Participants
    agents_involved VARCHAR(100)[],      -- Array of agent IDs
    primary_agent VARCHAR(20),

    -- Outcome
    outcome_type VARCHAR(30),            -- 'success', 'failure', 'neutral', 'learning'
    outcome_value DECIMAL(20,8),         -- Quantified outcome (P&L, score, etc.)
    outcome_metadata JSONB,

    -- Embedding for semantic search
    embedding_id UUID REFERENCES fhq_memory.embedding_store(embedding_id),

    -- Importance (affects retrieval priority)
    importance_score DECIMAL(5,4) DEFAULT 0.5000,
    is_landmark BOOLEAN DEFAULT FALSE,   -- Significant event worth remembering

    -- Lineage
    lineage_hash VARCHAR(64),
    parent_episode_id UUID REFERENCES fhq_memory.episodic_memory(episode_id),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT valid_episode_regime CHECK (regime_at_start IN ('BULL', 'BEAR', 'SIDEWAYS', 'CRISIS', 'UNKNOWN'))
);

CREATE INDEX IF NOT EXISTS idx_episodic_regime
    ON fhq_memory.episodic_memory(regime_at_start);

CREATE INDEX IF NOT EXISTS idx_episodic_type
    ON fhq_memory.episodic_memory(episode_type);

CREATE INDEX IF NOT EXISTS idx_episodic_started
    ON fhq_memory.episodic_memory(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_episodic_landmark
    ON fhq_memory.episodic_memory(is_landmark) WHERE is_landmark = TRUE;

COMMENT ON TABLE fhq_memory.episodic_memory IS
'Historical event memory. Used for learning from past experiences.';

-- ============================================================================
-- SECTION 6: STATE SNAPSHOTS (CEIO, FINN, LARS, LINE, VEGA)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_memory.state_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Snapshot identification
    agent_id VARCHAR(20) NOT NULL,
    snapshot_type VARCHAR(30) NOT NULL,  -- 'full', 'delta', 'checkpoint', 'recovery'
    snapshot_name VARCHAR(100),

    -- State data
    state_data JSONB NOT NULL,
    state_version INTEGER DEFAULT 1,
    state_hash VARCHAR(64) NOT NULL,     -- SHA256 of state_data

    -- Context
    regime VARCHAR(20) NOT NULL,
    defcon_level INTEGER,

    -- Trigger
    trigger_event VARCHAR(50),           -- What caused this snapshot
    trigger_event_id UUID,

    -- Recovery info
    is_recoverable BOOLEAN DEFAULT TRUE,
    recovery_priority INTEGER DEFAULT 5,

    -- Lineage
    lineage_hash VARCHAR(64),
    parent_snapshot_id UUID REFERENCES fhq_memory.state_snapshots(snapshot_id),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    valid_until TIMESTAMP WITH TIME ZONE,

    CONSTRAINT valid_snapshot_agent CHECK (agent_id IN ('FINN', 'CEIO', 'LARS', 'LINE', 'VEGA', 'STIG', 'SYSTEM')),
    CONSTRAINT valid_snapshot_regime CHECK (regime IN ('BULL', 'BEAR', 'SIDEWAYS', 'CRISIS', 'UNKNOWN'))
);

CREATE INDEX IF NOT EXISTS idx_snapshot_agent_regime
    ON fhq_memory.state_snapshots(agent_id, regime);

CREATE INDEX IF NOT EXISTS idx_snapshot_created
    ON fhq_memory.state_snapshots(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_snapshot_recoverable
    ON fhq_memory.state_snapshots(is_recoverable, recovery_priority DESC) WHERE is_recoverable = TRUE;

COMMENT ON TABLE fhq_memory.state_snapshots IS
'Agent state snapshots for recovery and continuity. Critical for autonomy.';

-- ============================================================================
-- SECTION 7: PERCEPTION MEMORY (IoS-009 Snapshots)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_memory.perception_memory (
    perception_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Perception identification
    ios_layer VARCHAR(20) NOT NULL,      -- 'IOS-003', 'IOS-007', 'IOS-009', etc.
    perception_type VARCHAR(50) NOT NULL, -- 'regime', 'stress', 'intent', 'market_state'

    -- Perception data
    perception_data JSONB NOT NULL,
    confidence DECIMAL(5,4),

    -- Context (MANDATORY regime filter)
    regime VARCHAR(20) NOT NULL,
    defcon_level INTEGER,

    -- Embedding for semantic retrieval
    embedding_id UUID REFERENCES fhq_memory.embedding_store(embedding_id),

    -- Temporal decay
    relevance_score DECIMAL(5,4) DEFAULT 1.0000,
    decay_factor DECIMAL(5,4) DEFAULT 0.1500,

    -- Source
    source_event_id UUID,
    source_snapshot_id UUID,

    -- Lineage
    lineage_hash VARCHAR(64),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    valid_until TIMESTAMP WITH TIME ZONE,

    CONSTRAINT valid_perception_regime CHECK (regime IN ('BULL', 'BEAR', 'SIDEWAYS', 'CRISIS', 'UNKNOWN'))
);

CREATE INDEX IF NOT EXISTS idx_perception_regime
    ON fhq_memory.perception_memory(regime);

CREATE INDEX IF NOT EXISTS idx_perception_layer
    ON fhq_memory.perception_memory(ios_layer);

CREATE INDEX IF NOT EXISTS idx_perception_type_regime
    ON fhq_memory.perception_memory(perception_type, regime);

CREATE INDEX IF NOT EXISTS idx_perception_created
    ON fhq_memory.perception_memory(created_at DESC);

COMMENT ON TABLE fhq_memory.perception_memory IS
'IoS perception layer memories. Used for contextual intelligence retrieval.';

-- ============================================================================
-- SECTION 8: RETRIEVAL AUDIT LOG (VEGA Oversight - ARO Section 8.4)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_memory.retrieval_audit_log (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Query info
    querying_agent VARCHAR(20) NOT NULL,
    query_type VARCHAR(30) NOT NULL,     -- 'embedding_search', 'memory_lookup', 'episode_retrieval'
    query_text TEXT,

    -- Regime compliance (MANDATORY check)
    regime_filter_used BOOLEAN NOT NULL,
    regime_at_query VARCHAR(20) NOT NULL,

    -- Decay compliance
    decay_applied BOOLEAN NOT NULL,

    -- Cross-regime violation check
    cross_regime_attempt BOOLEAN DEFAULT FALSE,
    cross_regime_blocked BOOLEAN DEFAULT FALSE,

    -- Results
    results_count INTEGER,
    execution_time_ms INTEGER,

    -- Lineage
    lineage_hash VARCHAR(64),

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT valid_audit_agent CHECK (querying_agent IN ('FINN', 'CEIO', 'LARS', 'LINE', 'VEGA', 'STIG', 'SYSTEM'))
);

CREATE INDEX IF NOT EXISTS idx_retrieval_audit_agent
    ON fhq_memory.retrieval_audit_log(querying_agent);

CREATE INDEX IF NOT EXISTS idx_retrieval_audit_violations
    ON fhq_memory.retrieval_audit_log(cross_regime_attempt) WHERE cross_regime_attempt = TRUE;

CREATE INDEX IF NOT EXISTS idx_retrieval_audit_created
    ON fhq_memory.retrieval_audit_log(created_at DESC);

COMMENT ON TABLE fhq_memory.retrieval_audit_log IS
'VEGA oversight: All memory retrievals logged for compliance verification.';

-- ============================================================================
-- SECTION 9: MEMORY DECAY FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_memory.calculate_effective_relevance(
    p_base_relevance DECIMAL,
    p_decay_factor DECIMAL,
    p_created_at TIMESTAMP WITH TIME ZONE
) RETURNS DECIMAL AS $$
DECLARE
    v_age_days DECIMAL;
    v_effective_relevance DECIMAL;
BEGIN
    -- Calculate age in days
    v_age_days := EXTRACT(EPOCH FROM (NOW() - p_created_at)) / 86400.0;

    -- Apply exponential decay: effective_relevance = base_relevance * exp(-λ * age_in_days)
    v_effective_relevance := p_base_relevance * EXP(-p_decay_factor * v_age_days);

    -- Floor at 0.01 to prevent complete zeroing
    RETURN GREATEST(v_effective_relevance, 0.01);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fhq_memory.calculate_effective_relevance IS
'ARO-20251208 Section 8.2: Temporal decay formula for memory relevance.';

-- ============================================================================
-- SECTION 10: REGIME-GATED RETRIEVAL FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_memory.regime_gated_search(
    p_query_embedding vector(1536),
    p_current_regime VARCHAR(20),
    p_querying_agent VARCHAR(20),
    p_limit INTEGER DEFAULT 10,
    p_min_relevance DECIMAL DEFAULT 0.1
) RETURNS TABLE (
    embedding_id UUID,
    content_text TEXT,
    content_summary VARCHAR(500),
    similarity DECIMAL,
    effective_relevance DECIMAL,
    source_agent VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
DECLARE
    v_audit_id UUID;
BEGIN
    -- Log the retrieval attempt (VEGA oversight)
    INSERT INTO fhq_memory.retrieval_audit_log (
        querying_agent, query_type, regime_filter_used, regime_at_query, decay_applied
    ) VALUES (
        p_querying_agent, 'embedding_search', TRUE, p_current_regime, TRUE
    ) RETURNING audit_id INTO v_audit_id;

    -- Return regime-filtered results with decay applied
    RETURN QUERY
    SELECT
        e.embedding_id,
        e.content_text,
        e.content_summary,
        (1 - (e.embedding <=> p_query_embedding))::DECIMAL AS similarity,
        CASE
            WHEN e.is_eternal_truth THEN e.relevance_score
            ELSE fhq_memory.calculate_effective_relevance(e.relevance_score, e.decay_factor, e.created_at)
        END AS effective_relevance,
        e.source_agent,
        e.created_at
    FROM fhq_memory.embedding_store e
    WHERE e.regime = p_current_regime  -- MANDATORY regime filter
      AND (e.expires_at IS NULL OR e.expires_at > NOW())
      AND (
          e.is_eternal_truth
          OR fhq_memory.calculate_effective_relevance(e.relevance_score, e.decay_factor, e.created_at) >= p_min_relevance
      )
    ORDER BY
        (1 - (e.embedding <=> p_query_embedding)) *
        CASE
            WHEN e.is_eternal_truth THEN e.relevance_score
            ELSE fhq_memory.calculate_effective_relevance(e.relevance_score, e.decay_factor, e.created_at)
        END DESC
    LIMIT p_limit;

    -- Update audit with results count
    UPDATE fhq_memory.retrieval_audit_log
    SET results_count = (SELECT COUNT(*) FROM fhq_memory.embedding_store WHERE regime = p_current_regime)
    WHERE audit_id = v_audit_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_memory.regime_gated_search IS
'ARO-20251208 Section 8.1: MANDATORY regime-gated vector search. All agents must use this function.';

-- ============================================================================
-- SECTION 11: REGISTER IN ADR REGISTRY
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id, title, status, category, description, created_at
) VALUES (
    'MIG-096',
    'PGVECTOR MEMORY FOUNDATION',
    'ACTIVE',
    'INFRASTRUCTURE',
    'ARO-20251208: Install pgvector extension and fhq_memory schema for agent memory, embeddings, and semantic search.',
    NOW()
) ON CONFLICT (adr_id) DO UPDATE SET
    status = 'ACTIVE',
    updated_at = NOW();

-- ============================================================================
-- SECTION 12: REGISTER FUNCTIONS IN FUNCTION REGISTRY
-- ============================================================================

INSERT INTO fhq_meta.function_registry (
    function_id, function_name, function_schema, ios_layer, status, description
) VALUES
    ('FN-MEM-001', 'calculate_effective_relevance', 'fhq_memory', 'MEMORY', 'ACTIVE', 'Temporal decay calculation'),
    ('FN-MEM-002', 'regime_gated_search', 'fhq_memory', 'MEMORY', 'ACTIVE', 'Regime-filtered vector search')
ON CONFLICT (function_id) DO UPDATE SET
    status = 'ACTIVE',
    updated_at = NOW();

-- ============================================================================
-- COMPLETION
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '=== MIGRATION 096 COMPLETE ===';
    RAISE NOTICE 'pgvector: INSTALLED (if available)';
    RAISE NOTICE 'fhq_memory schema: CREATED';
    RAISE NOTICE 'Tables created: embedding_store, agent_memory, episodic_memory, state_snapshots, perception_memory, retrieval_audit_log';
    RAISE NOTICE 'Functions created: calculate_effective_relevance, regime_gated_search';
    RAISE NOTICE 'ARO-20251208 Section 1 & 8: COMPLETE';
END $$;

-- ============================================================================
-- ROLLBACK SCRIPT (if needed)
-- ============================================================================
/*
DROP FUNCTION IF EXISTS fhq_memory.regime_gated_search;
DROP FUNCTION IF EXISTS fhq_memory.calculate_effective_relevance;
DROP TABLE IF EXISTS fhq_memory.retrieval_audit_log;
DROP TABLE IF EXISTS fhq_memory.perception_memory;
DROP TABLE IF EXISTS fhq_memory.state_snapshots;
DROP TABLE IF EXISTS fhq_memory.episodic_memory;
DROP TABLE IF EXISTS fhq_memory.agent_memory;
DROP TABLE IF EXISTS fhq_memory.embedding_store;
DROP SCHEMA IF EXISTS fhq_memory;
-- Note: DROP EXTENSION vector; requires superuser
*/
