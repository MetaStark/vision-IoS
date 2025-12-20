-- ============================================================================
-- G1 SCHEMA PROPOSAL: ADR-021 COGNITIVE ENGINE ARCHITECTURE
-- ============================================================================
-- STATUS: PROPOSAL ONLY — NOT TO BE EXECUTED
-- Gate: G1_TECHNICAL_VALIDATION
-- Authority: CEO Directive G1 2025-12-09
-- Executor: STIG (CTO)
--
-- PURPOSE: Define canonical schema architecture for Cognitive Domain
--          This is architectural validation, NOT implementation.
--
-- PROHIBITIONS ACKNOWLEDGED:
--   ✗ No tables shall be created
--   ✗ No code shall be written
--   ✗ No queries shall be executed
--   ✗ No agents receive extended privileges
--   ✗ No runtime coupling
--   ✗ No pre-computations
--
-- DOCUMENTS GOVERNING THIS PROPOSAL:
--   - ADR-021: Cognitive Engine Architecture & Deep Research Protocol
--   - EC-020: SitC (Search-in-the-Chain)
--   - EC-021: InForage (Information Foraging Protocol)
--   - EC-022: IKEA (Knowledge Boundary Framework)
--   - ADR-011: Fortress & VEGA Testsuite (Hash Chain Standard)
--   - ADR-013: Canonical Governance (One-True-Source)
--   - ADR-020: Autonomous Cognitive Intelligence Protocol
-- ============================================================================

-- ############################################################################
-- SCHEMA CREATION (fhq_cognition)
-- ############################################################################

-- CREATE SCHEMA IF NOT EXISTS fhq_cognition;
-- COMMENT ON SCHEMA fhq_cognition IS
--     'Cognitive Engine Domain per ADR-021. Contains SitC, InForage, IKEA infrastructure.
--      Constitutional Authority: ADR-021, ADR-020, ADR-017 MIT QUAD.
--      G1 Proposal - Awaiting G2/G3/G4 activation.';

-- ############################################################################
-- ENUM TYPES
-- ############################################################################

-- Cognitive Node Modality (EC-020 §3)
-- CREATE TYPE fhq_cognition.cognitive_modality AS ENUM (
--     'perception',      -- Sensory input processing
--     'causal',          -- Causal inference nodes
--     'intent',          -- Intent detection nodes
--     'search',          -- Search execution nodes
--     'verification',    -- Verification checkpoints
--     'synthesis'        -- Output synthesis nodes
-- );

-- Knowledge Boundary Type (IKEA - EC-022)
-- CREATE TYPE fhq_cognition.boundary_type AS ENUM (
--     'PARAMETRIC',           -- Internal knowledge sufficient
--     'EXTERNAL_REQUIRED',    -- Must retrieve externally
--     'HYBRID'                -- Combination of internal + external
-- );

-- Chain Node Status (SitC - EC-020)
-- CREATE TYPE fhq_cognition.chain_node_status AS ENUM (
--     'PENDING',      -- Not yet processed
--     'VERIFIED',     -- Successfully verified
--     'FAILED',       -- Verification failed
--     'SKIPPED',      -- Intentionally skipped
--     'ABORTED'       -- Chain aborted
-- );

-- Foraging Termination Reason (InForage - EC-021)
-- CREATE TYPE fhq_cognition.forage_termination AS ENUM (
--     'EXECUTED',             -- Search was executed
--     'SCENT_TOO_LOW',        -- Scent score below threshold
--     'BUDGET_EXCEEDED',      -- Cost budget exhausted
--     'DIMINISHING_RETURNS',  -- Information gain plateau
--     'CONFIDENCE_REACHED',   -- Target confidence achieved
--     'NO_VIABLE_PATHS'       -- No paths above minimum scent
-- );

-- Research Protocol Status
-- CREATE TYPE fhq_cognition.protocol_status AS ENUM (
--     'INITIALIZING',
--     'PLANNING',
--     'EXECUTING',
--     'SEARCHING',
--     'VERIFYING',
--     'REVISING',
--     'COMPLETED',
--     'ABORTED'
-- );

-- ############################################################################
-- TABLE 1: fhq_cognition.cognitive_nodes
-- ############################################################################
-- Master registry of all cognitive nodes in the system
-- Source: ADR-021 §4, EC-020 §3

/*
CREATE TABLE fhq_cognition.cognitive_nodes (
    -- Primary Key (ADR-020 §6 - must be hash-anchored)
    cognitive_node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Node Identity
    node_code TEXT NOT NULL,                                    -- Human-readable code (e.g., 'SITC-001')
    node_name TEXT NOT NULL,                                    -- Descriptive name
    modality fhq_cognition.cognitive_modality NOT NULL,         -- EC-020 §3

    -- Hierarchical Structure
    parent_node_id UUID REFERENCES fhq_cognition.cognitive_nodes(cognitive_node_id),
    depth_level INT NOT NULL DEFAULT 0 CHECK (depth_level >= 0),

    -- Cognitive Attributes (ADR-021)
    attention_weight FLOAT8 NOT NULL DEFAULT 0.5
        CHECK (attention_weight >= 0 AND attention_weight <= 1),  -- Normalized 0-1
    activation_threshold FLOAT8 DEFAULT 0.5
        CHECK (activation_threshold >= 0 AND activation_threshold <= 1),

    -- Causal Links (EC-020 §4 - must support future vector embedding)
    causal_links JSONB NOT NULL DEFAULT '[]'::jsonb,
    causal_strength FLOAT8 DEFAULT 0.0,

    -- Governance (ADR-013)
    source_document TEXT NOT NULL,                              -- ADR/EC reference
    governance_class TEXT NOT NULL,                             -- e.g., 'CONSTITUTIONAL-RESEARCH'
    owner_agent TEXT NOT NULL,                                  -- FINN, LARS, VEGA, etc.

    -- Hash Chain (ADR-011 Fortress Standard)
    hash_self TEXT NOT NULL,
    hash_prev TEXT,
    lineage_hash TEXT NOT NULL,

    -- Temporal (Required fields)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT cognitive_nodes_modality_check CHECK (modality IS NOT NULL),
    CONSTRAINT cognitive_nodes_governance_check CHECK (governance_class IS NOT NULL)
);

-- Comments
COMMENT ON TABLE fhq_cognition.cognitive_nodes IS
    'Master registry of cognitive nodes per ADR-021, EC-020. Each node represents a reasoning unit in the Cognitive Engine Architecture.';
COMMENT ON COLUMN fhq_cognition.cognitive_nodes.modality IS
    'Node type per EC-020 §3: perception, causal, intent, search, verification, synthesis';
COMMENT ON COLUMN fhq_cognition.cognitive_nodes.causal_links IS
    'JSONB array of causal relationships. Must support future vector embedding per EC-020 §4';
COMMENT ON COLUMN fhq_cognition.cognitive_nodes.attention_weight IS
    'Normalized attention weight 0-1 per ADR-021';
COMMENT ON COLUMN fhq_cognition.cognitive_nodes.lineage_hash IS
    'Full hash chain per ADR-011 Fortress Standard';
*/

-- ############################################################################
-- TABLE 2: fhq_cognition.research_protocols
-- ############################################################################
-- Registry of active research protocols and their states
-- Source: ADR-021 §5 CECF

/*
CREATE TABLE fhq_cognition.research_protocols (
    -- Primary Key
    protocol_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Protocol Identity
    protocol_code TEXT NOT NULL UNIQUE,                         -- e.g., 'RP-2025-12-09-001'
    protocol_name TEXT NOT NULL,
    protocol_type TEXT NOT NULL,                                -- 'DEEP_RESEARCH', 'QUICK_LOOKUP', etc.

    -- Status Management
    status fhq_cognition.protocol_status NOT NULL DEFAULT 'INITIALIZING',

    -- Cognitive Engine Assignment
    primary_engine TEXT NOT NULL,                               -- 'SitC', 'InForage', 'IKEA'
    secondary_engines TEXT[] DEFAULT ARRAY[]::TEXT[],

    -- Task Reference
    task_id UUID,                                               -- Reference to fhq_org.org_tasks
    hypothesis TEXT,                                            -- Research hypothesis

    -- Economic Constraints (ADR-012)
    budget_allocated_usd NUMERIC(10,4) NOT NULL DEFAULT 0.50,
    budget_consumed_usd NUMERIC(10,4) NOT NULL DEFAULT 0.00,
    max_search_calls INT NOT NULL DEFAULT 5,
    search_calls_made INT NOT NULL DEFAULT 0,

    -- DEFCON Awareness (ADR-016)
    defcon_at_creation TEXT NOT NULL DEFAULT 'GREEN',
    defcon_current TEXT NOT NULL DEFAULT 'GREEN',

    -- Governance (ADR-013)
    source_document TEXT NOT NULL DEFAULT 'ADR-021',
    governance_class TEXT NOT NULL DEFAULT 'RESEARCH-METHOD',
    initiating_agent TEXT NOT NULL,

    -- Hash Chain (ADR-011)
    hash_self TEXT NOT NULL,
    hash_prev TEXT,
    lineage_hash TEXT NOT NULL,

    -- Temporal
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT research_protocols_budget_check CHECK (budget_consumed_usd <= budget_allocated_usd),
    CONSTRAINT research_protocols_calls_check CHECK (search_calls_made <= max_search_calls)
);

COMMENT ON TABLE fhq_cognition.research_protocols IS
    'Registry of research protocols per ADR-021 §5 CECF. Tracks protocol lifecycle and resource consumption.';
*/

-- ############################################################################
-- TABLE 3: fhq_cognition.search_in_chain_events (SitC - EC-020)
-- ############################################################################
-- Chain-of-Query state tracking for SitC
-- Source: EC-020 §4, §11

/*
CREATE TABLE fhq_cognition.search_in_chain_events (
    -- Primary Key
    sitc_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Protocol Reference
    protocol_id UUID NOT NULL REFERENCES fhq_cognition.research_protocols(protocol_id),

    -- Chain Position
    node_index INT NOT NULL CHECK (node_index >= 0),
    node_type fhq_cognition.chain_node_status NOT NULL DEFAULT 'PENDING',

    -- Node Content
    node_content TEXT,
    query_text TEXT,
    reasoning_step TEXT,

    -- Verification
    verification_status fhq_cognition.chain_node_status NOT NULL DEFAULT 'PENDING',
    verification_evidence JSONB,

    -- Search Results (if search node)
    search_executed BOOLEAN DEFAULT FALSE,
    search_result_id UUID,                                      -- Reference to search results
    search_depth INT NOT NULL DEFAULT 0 CHECK (search_depth >= 0),  -- SitC depth validation

    -- Chain Integrity (EC-020 §8)
    chain_integrity_score NUMERIC(5,4),                         -- verified_nodes / total_nodes

    -- Plan Revision Tracking
    revision_count INT NOT NULL DEFAULT 0,
    nodes_invalidated INT[] DEFAULT ARRAY[]::INT[],

    -- Governance (ADR-013)
    source_document TEXT NOT NULL DEFAULT 'EC-020',
    governance_class TEXT NOT NULL DEFAULT 'RESEARCH-METHOD',

    -- Hash Chain (ADR-011)
    hash_self TEXT NOT NULL,
    hash_prev TEXT,
    lineage_hash TEXT NOT NULL,

    -- Temporal
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Uniqueness
    CONSTRAINT sitc_events_unique_node UNIQUE (protocol_id, node_index)
);

COMMENT ON TABLE fhq_cognition.search_in_chain_events IS
    'Chain-of-Query state tracking per EC-020 (SitC). Each row represents a node in the reasoning chain.';
COMMENT ON COLUMN fhq_cognition.search_in_chain_events.search_depth IS
    'Search depth per SitC specification. Must be >= 0.';
COMMENT ON COLUMN fhq_cognition.search_in_chain_events.chain_integrity_score IS
    'Per EC-020 §8: verified_nodes / total_nodes. Score < 0.80 = CATASTROPHIC.';
*/

-- ############################################################################
-- TABLE 4: fhq_cognition.information_foraging_paths (InForage - EC-021)
-- ############################################################################
-- Search optimization and ROI tracking for InForage
-- Source: EC-021 §4, §11

/*
CREATE TABLE fhq_cognition.information_foraging_paths (
    -- Primary Key
    forage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Protocol Reference
    protocol_id UUID NOT NULL REFERENCES fhq_cognition.research_protocols(protocol_id),

    -- Search Query
    search_query TEXT NOT NULL,
    query_embedding VECTOR(1536),                               -- For semantic similarity

    -- Scent Score (EC-021 §4.1)
    scent_score NUMERIC(5,4) NOT NULL CHECK (scent_score >= 0 AND scent_score <= 1),
    scent_components JSONB NOT NULL DEFAULT '{}'::jsonb,        -- Breakdown of score

    -- Cost Analysis (ADR-012)
    estimated_cost_usd NUMERIC(10,6) NOT NULL,
    actual_cost_usd NUMERIC(10,6),
    source_tier TEXT NOT NULL,                                  -- 'LAKE', 'PULSE', 'SNIPER'

    -- Information Gain (EC-021 §2.2)
    information_gain NUMERIC(5,4),                              -- Post-hoc measured value
    relevance_score NUMERIC(5,4),
    freshness_score NUMERIC(5,4),

    -- Decision
    search_executed BOOLEAN NOT NULL DEFAULT FALSE,
    termination_reason fhq_cognition.forage_termination,
    decision_rationale TEXT,

    -- Context Frame (BCBS-239 lineage required per CEO directive)
    context_frame JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Governance (ADR-013)
    source_document TEXT NOT NULL DEFAULT 'EC-021',
    governance_class TEXT NOT NULL DEFAULT 'RESEARCH-METHOD',

    -- Hash Chain (ADR-011)
    hash_self TEXT NOT NULL,
    hash_prev TEXT,
    lineage_hash TEXT NOT NULL,

    -- Temporal
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    executed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_cognition.information_foraging_paths IS
    'Information foraging decisions per EC-021 (InForage). Tracks search ROI and optimization.';
COMMENT ON COLUMN fhq_cognition.information_foraging_paths.scent_score IS
    'Predicted information value per EC-021 §4.1. Range 0.0-1.0.';
COMMENT ON COLUMN fhq_cognition.information_foraging_paths.context_frame IS
    'JSONB context per InForage spec. BCBS-239 lineage required.';
*/

-- ############################################################################
-- TABLE 5: fhq_cognition.knowledge_boundaries (IKEA - EC-022)
-- ############################################################################
-- Knowledge boundary classification and hallucination prevention
-- Source: EC-022 §4, §10

/*
CREATE TABLE fhq_cognition.knowledge_boundaries (
    -- Primary Key
    boundary_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Protocol Reference (optional - can be standalone classification)
    protocol_id UUID REFERENCES fhq_cognition.research_protocols(protocol_id),

    -- Query Classification
    query_text TEXT NOT NULL,
    query_embedding VECTOR(1536),

    -- Classification Result (EC-022 §2)
    boundary_type fhq_cognition.boundary_type NOT NULL,
    classification_confidence NUMERIC(5,4) NOT NULL
        CHECK (classification_confidence >= 0 AND classification_confidence <= 1),

    -- Internal Certainty (EC-022 §4.2)
    internal_certainty NUMERIC(5,4) NOT NULL
        CHECK (internal_certainty >= 0 AND internal_certainty <= 1),
    certainty_threshold NUMERIC(5,4) NOT NULL,                  -- DEFCON-dependent

    -- Volatility Assessment (EC-022 §4.3)
    volatility_flag BOOLEAN NOT NULL DEFAULT FALSE,
    volatility_class TEXT,                                      -- 'EXTREME', 'HIGH', 'MEDIUM', 'LOW', 'STATIC'
    data_type TEXT,                                             -- 'STOCK_PRICE', 'EARNINGS', etc.

    -- Retrieval Decision
    retrieval_triggered BOOLEAN NOT NULL DEFAULT FALSE,
    retrieval_source TEXT,                                      -- 'LAKE', 'PULSE', 'SNIPER'

    -- Boundary Violation Detection (EC-022 §7)
    boundary_violation BOOLEAN NOT NULL DEFAULT FALSE,
    hallucination_attempt BOOLEAN NOT NULL DEFAULT FALSE,
    reflexive_trigger BOOLEAN DEFAULT FALSE,                    -- For partial index

    -- Decision Rationale
    decision_rationale TEXT NOT NULL,

    -- DEFCON Context (ADR-016)
    defcon_level TEXT NOT NULL DEFAULT 'GREEN',

    -- Governance (ADR-013)
    source_document TEXT NOT NULL DEFAULT 'EC-022',
    governance_class TEXT NOT NULL DEFAULT 'RESEARCH-METHOD / KNOWLEDGE-BOUNDARY',

    -- Hash Chain (ADR-011)
    hash_self TEXT NOT NULL,
    hash_prev TEXT,
    lineage_hash TEXT NOT NULL,

    -- Temporal
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_cognition.knowledge_boundaries IS
    'Knowledge boundary classifications per EC-022 (IKEA). Prevents hallucination and enforces truth boundaries.';
COMMENT ON COLUMN fhq_cognition.knowledge_boundaries.boundary_type IS
    'Classification per EC-022 §2: PARAMETRIC, EXTERNAL_REQUIRED, HYBRID';
COMMENT ON COLUMN fhq_cognition.knowledge_boundaries.internal_certainty IS
    'Model confidence in internal knowledge per EC-022 §4.2. Range 0.0-1.0.';
COMMENT ON COLUMN fhq_cognition.knowledge_boundaries.boundary_violation IS
    'True if EXTERNAL_REQUIRED but output attempted without retrieval (hallucination attempt)';
*/

-- ############################################################################
-- TABLE 6: fhq_cognition.lineage_log
-- ############################################################################
-- Comprehensive lineage tracking for all cognitive operations
-- Source: ADR-011, ADR-013

/*
CREATE TABLE fhq_cognition.lineage_log (
    -- Primary Key
    lineage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Target Reference
    target_table TEXT NOT NULL,                                 -- Table name
    target_id UUID NOT NULL,                                    -- Row ID in target table

    -- Lineage Chain
    sequence_number BIGINT NOT NULL,
    hash_self TEXT NOT NULL,
    hash_prev TEXT,
    lineage_hash TEXT NOT NULL,

    -- Operation Type
    operation_type TEXT NOT NULL,                               -- 'INSERT', 'UPDATE', 'VERIFY'
    operation_agent TEXT NOT NULL,                              -- Agent that performed operation

    -- Verification
    integrity_verified BOOLEAN NOT NULL DEFAULT FALSE,
    verification_timestamp TIMESTAMPTZ,
    verification_agent TEXT,

    -- Evidence
    evidence_bundle JSONB,
    signature TEXT,                                             -- Ed25519 signature (ADR-008)

    -- Governance (ADR-013)
    source_document TEXT NOT NULL,
    governance_class TEXT NOT NULL,

    -- Temporal
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Uniqueness
    CONSTRAINT lineage_log_unique_seq UNIQUE (target_table, target_id, sequence_number)
);

COMMENT ON TABLE fhq_cognition.lineage_log IS
    'Comprehensive lineage tracking per ADR-011 Fortress Standard. Provides immutable audit trail for all cognitive operations.';
*/

-- ############################################################################
-- PERFORMANCE INDEXING STRATEGY (CEO Directive §2.1b)
-- ############################################################################
-- Purpose: Ensure domain can scale to millions of rows without latency regression

-- ==========================================================================
-- GIN INDEXES FOR JSONB FIELDS
-- ==========================================================================
-- Required for efficient JSONB queries on SitC search paths, InForage frames, IKEA boundary maps

/*
-- cognitive_nodes: causal_links (EC-020 §4)
CREATE INDEX idx_cognitive_nodes_causal_links_gin
    ON fhq_cognition.cognitive_nodes USING GIN (causal_links);

-- search_in_chain_events: verification_evidence
CREATE INDEX idx_sitc_events_evidence_gin
    ON fhq_cognition.search_in_chain_events USING GIN (verification_evidence);

-- information_foraging_paths: scent_components, context_frame
CREATE INDEX idx_forage_paths_scent_gin
    ON fhq_cognition.information_foraging_paths USING GIN (scent_components);
CREATE INDEX idx_forage_paths_context_gin
    ON fhq_cognition.information_foraging_paths USING GIN (context_frame);

-- lineage_log: evidence_bundle
CREATE INDEX idx_lineage_log_evidence_gin
    ON fhq_cognition.lineage_log USING GIN (evidence_bundle);
*/

-- ==========================================================================
-- B-TREE INDEXES FOR TEMPORAL FIELDS
-- ==========================================================================
-- Required for time-range queries per ADR-020 deterministic research

/*
-- All tables: created_at, ingested_at
CREATE INDEX idx_cognitive_nodes_created_at
    ON fhq_cognition.cognitive_nodes (created_at);
CREATE INDEX idx_cognitive_nodes_ingested_at
    ON fhq_cognition.cognitive_nodes (ingested_at);

CREATE INDEX idx_research_protocols_created_at
    ON fhq_cognition.research_protocols (created_at);
CREATE INDEX idx_research_protocols_started_at
    ON fhq_cognition.research_protocols (started_at);
CREATE INDEX idx_research_protocols_completed_at
    ON fhq_cognition.research_protocols (completed_at);

CREATE INDEX idx_sitc_events_created_at
    ON fhq_cognition.search_in_chain_events (created_at);
CREATE INDEX idx_sitc_events_verified_at
    ON fhq_cognition.search_in_chain_events (verified_at);

CREATE INDEX idx_forage_paths_created_at
    ON fhq_cognition.information_foraging_paths (created_at);
CREATE INDEX idx_forage_paths_executed_at
    ON fhq_cognition.information_foraging_paths (executed_at);

CREATE INDEX idx_knowledge_boundaries_created_at
    ON fhq_cognition.knowledge_boundaries (created_at);

CREATE INDEX idx_lineage_log_created_at
    ON fhq_cognition.lineage_log (created_at);
*/

-- ==========================================================================
-- HASH INDEXES FOR LINEAGE FIELDS (ADR-011 Chain Lookups)
-- ==========================================================================
-- Required for efficient hash chain verification

/*
-- All tables: lineage_hash, hash_self
CREATE INDEX idx_cognitive_nodes_lineage_hash
    ON fhq_cognition.cognitive_nodes USING HASH (lineage_hash);
CREATE INDEX idx_cognitive_nodes_hash_self
    ON fhq_cognition.cognitive_nodes USING HASH (hash_self);

CREATE INDEX idx_research_protocols_lineage_hash
    ON fhq_cognition.research_protocols USING HASH (lineage_hash);
CREATE INDEX idx_research_protocols_hash_self
    ON fhq_cognition.research_protocols USING HASH (hash_self);

CREATE INDEX idx_sitc_events_lineage_hash
    ON fhq_cognition.search_in_chain_events USING HASH (lineage_hash);
CREATE INDEX idx_sitc_events_hash_self
    ON fhq_cognition.search_in_chain_events USING HASH (hash_self);

CREATE INDEX idx_forage_paths_lineage_hash
    ON fhq_cognition.information_foraging_paths USING HASH (lineage_hash);
CREATE INDEX idx_forage_paths_hash_self
    ON fhq_cognition.information_foraging_paths USING HASH (hash_self);

CREATE INDEX idx_knowledge_boundaries_lineage_hash
    ON fhq_cognition.knowledge_boundaries USING HASH (lineage_hash);
CREATE INDEX idx_knowledge_boundaries_hash_self
    ON fhq_cognition.knowledge_boundaries USING HASH (hash_self);

CREATE INDEX idx_lineage_log_lineage_hash
    ON fhq_cognition.lineage_log USING HASH (lineage_hash);
CREATE INDEX idx_lineage_log_hash_self
    ON fhq_cognition.lineage_log USING HASH (hash_self);
*/

-- ==========================================================================
-- SELECTIVE PARTIAL INDEXES FOR HIGH-SPARSITY FIELDS
-- ==========================================================================
-- Required for efficient queries on rarely-true boolean flags

/*
-- knowledge_boundaries: reflexive_trigger (sparse - only TRUE for reflexive cases)
CREATE INDEX idx_knowledge_boundaries_reflexive_partial
    ON fhq_cognition.knowledge_boundaries (reflexive_trigger)
    WHERE reflexive_trigger = TRUE;

-- knowledge_boundaries: boundary_violation (sparse - only TRUE for violations)
CREATE INDEX idx_knowledge_boundaries_violation_partial
    ON fhq_cognition.knowledge_boundaries (boundary_violation)
    WHERE boundary_violation = TRUE;

-- knowledge_boundaries: hallucination_attempt (sparse - only TRUE for attempts)
CREATE INDEX idx_knowledge_boundaries_hallucination_partial
    ON fhq_cognition.knowledge_boundaries (hallucination_attempt)
    WHERE hallucination_attempt = TRUE;

-- search_in_chain_events: verification_status = 'FAILED' (sparse)
CREATE INDEX idx_sitc_events_failed_partial
    ON fhq_cognition.search_in_chain_events (verification_status)
    WHERE verification_status = 'FAILED';

-- research_protocols: status = 'ABORTED' (sparse)
CREATE INDEX idx_research_protocols_aborted_partial
    ON fhq_cognition.research_protocols (status)
    WHERE status = 'ABORTED';

-- information_foraging_paths: search_executed = FALSE (for pending searches)
CREATE INDEX idx_forage_paths_not_executed_partial
    ON fhq_cognition.information_foraging_paths (search_executed)
    WHERE search_executed = FALSE;

-- lineage_log: integrity_verified = FALSE (for unverified entries)
CREATE INDEX idx_lineage_log_unverified_partial
    ON fhq_cognition.lineage_log (integrity_verified)
    WHERE integrity_verified = FALSE;
*/

-- ==========================================================================
-- COMPOSITE INDEXES FOR COMMON QUERY PATTERNS
-- ==========================================================================

/*
-- Protocol lookups by status and engine
CREATE INDEX idx_research_protocols_status_engine
    ON fhq_cognition.research_protocols (status, primary_engine);

-- SitC events by protocol and node index (for chain traversal)
CREATE INDEX idx_sitc_events_protocol_node
    ON fhq_cognition.search_in_chain_events (protocol_id, node_index);

-- Foraging paths by protocol and scent score (for ROI analysis)
CREATE INDEX idx_forage_paths_protocol_scent
    ON fhq_cognition.information_foraging_paths (protocol_id, scent_score DESC);

-- Knowledge boundaries by type and confidence (for classification queries)
CREATE INDEX idx_knowledge_boundaries_type_confidence
    ON fhq_cognition.knowledge_boundaries (boundary_type, classification_confidence DESC);

-- Lineage log by target (for audit queries)
CREATE INDEX idx_lineage_log_target
    ON fhq_cognition.lineage_log (target_table, target_id, sequence_number);
*/

-- ############################################################################
-- SCHEMA COHERENCE VALIDATION
-- ############################################################################
-- This section validates that all tables can be created without conflict

/*
-- Validation Query 1: Check for naming conflicts
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_name IN (
    'cognitive_nodes',
    'research_protocols',
    'search_in_chain_events',
    'information_foraging_paths',
    'knowledge_boundaries',
    'lineage_log'
);
-- Expected: 0 rows (no conflicts)

-- Validation Query 2: Check for type conflicts
SELECT typname
FROM pg_type
WHERE typname IN (
    'cognitive_modality',
    'boundary_type',
    'chain_node_status',
    'forage_termination',
    'protocol_status'
);
-- Expected: 0 rows (no conflicts)

-- Validation Query 3: Verify fhq_cognition schema doesn't exist
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name = 'fhq_cognition';
-- Expected: 0 rows (schema doesn't exist yet)
*/

-- ############################################################################
-- END OF G1 SCHEMA PROPOSAL
-- ############################################################################
-- STATUS: PROPOSAL COMPLETE
-- NEXT GATE: G2_GOVERNANCE_VALIDATION (requires VEGA approval)
--
-- Exit Criteria Met:
--   [x] Schema Coherence: All tables can be established without conflict
--   [x] Lineage Integrity: Hash-chain design validates against ADR-011
--   [x] Governance Integration: Source documents and classes defined
--   [x] Performance Scalability: GIN/B-tree/Hash/Partial indexes defined
--   [x] Determinism: No fields with undefined semantics
--   [x] Cross-Document Coherence: ADR-021 + EC-020/21/22 match without logical gaps
--
-- STIG Certification:
--   This schema proposal has been architected in compliance with:
--   - ADR-021: Cognitive Engine Architecture
--   - EC-020: SitC (Search-in-the-Chain)
--   - EC-021: InForage (Information Foraging Protocol)
--   - EC-022: IKEA (Knowledge Boundary Framework)
--   - ADR-011: Fortress & VEGA Testsuite
--   - ADR-013: Canonical Governance
--   - ADR-020: Autonomous Cognitive Intelligence
--
-- All DDL is commented out per CEO directive G1 prohibitions.
-- ############################################################################
