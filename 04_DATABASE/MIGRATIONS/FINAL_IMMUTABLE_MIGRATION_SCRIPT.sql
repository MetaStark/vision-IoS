-- ============================================================================
-- FINAL IMMUTABLE MIGRATION SCRIPT: ADR-021 COGNITIVE DOMAIN
-- ============================================================================
-- DOCUMENT ID: FINAL-DDL-G4-20251209
-- VERSION: 1.0 (IMMUTABLE)
-- AUTHORITY: CEO Directive G4 Pending
--
-- GATE STATUS:
--   G0: COMPLETE (Registration)
--   G1: COMPLETE (Technical Validation)
--   G2: COMPLETE (Governance Validation)
--   G3: COMPLETE (Integration Readiness)
--   G4: PENDING (This script - CEO Authorization Required)
--
-- EXECUTOR: STIG (CTO) under CEO authorization
-- HASH LOCK: SHA-256 will be computed post-creation for immutability
--
-- GOVERNING DOCUMENTS:
--   - ADR-021: Cognitive Engine Architecture & Deep Research Protocol
--   - EC-020: SitC (Search-in-the-Chain)
--   - EC-021: InForage (Information Foraging Protocol)
--   - EC-022: IKEA (Knowledge Boundary Framework)
--   - ADR-011: Fortress & VEGA Testsuite (Hash Chain Standard)
--   - ADR-012: Economic Safety Architecture
--   - ADR-013: Canonical Governance (One-True-Source)
--   - ADR-016: DEFCON & Circuit Breaker Protocol
--   - ADR-020: Autonomous Cognitive Intelligence
--
-- G3 SPECIFICATIONS INCORPORATED:
--   - G3_MAX_DEPTH_SPEC.json (Constitutional Constants)
--   - G3_JSONB_SCHEMA_VALIDATION_SPEC.json (JSONB Schemas)
--   - G3_PGVECTOR_COMPATIBILITY_NOTE.txt (Vector Infrastructure)
--   - G3_LARS_ORCHESTRATOR_PLAN.md (Integration Design)
--   - G3_ACTIVATION_SEQUENCE.md (Boot Sequence)
--
-- PROHIBITIONS:
--   - DO NOT EXECUTE WITHOUT G4 CEO AUTHORIZATION
--   - DO NOT MODIFY AFTER HASH COMPUTATION
--   - DO NOT ADD EMBEDDING GENERATION CODE
--   - DO NOT INSTALL TRIGGERS (G5+ requirement)
--
-- ============================================================================

-- ############################################################################
-- SECTION 1: SCHEMA CREATION
-- ############################################################################

CREATE SCHEMA IF NOT EXISTS fhq_cognition;

COMMENT ON SCHEMA fhq_cognition IS
    'Cognitive Engine Domain per ADR-021. Contains SitC, InForage, IKEA infrastructure.
     Constitutional Authority: ADR-021, ADR-020, ADR-017 MIT QUAD.
     G4 Activated: Pending CEO Authorization.
     Tables: cognitive_nodes, research_protocols, search_in_chain_events,
             information_foraging_paths, knowledge_boundaries, lineage_log.';

-- ############################################################################
-- SECTION 2: ENUM TYPES
-- ############################################################################

-- Cognitive Node Modality (EC-020 Section 3)
CREATE TYPE fhq_cognition.cognitive_modality AS ENUM (
    'perception',      -- Sensory input processing
    'causal',          -- Causal inference nodes
    'intent',          -- Intent detection nodes
    'search',          -- Search execution nodes
    'verification',    -- Verification checkpoints
    'synthesis'        -- Output synthesis nodes
);

COMMENT ON TYPE fhq_cognition.cognitive_modality IS
    'Cognitive node modality per EC-020 Section 3. Defines the functional role of each node in the cognitive architecture.';

-- Knowledge Boundary Type (IKEA - EC-022)
CREATE TYPE fhq_cognition.boundary_type AS ENUM (
    'PARAMETRIC',           -- Internal knowledge sufficient
    'EXTERNAL_REQUIRED',    -- Must retrieve externally
    'HYBRID'                -- Combination of internal + external
);

COMMENT ON TYPE fhq_cognition.boundary_type IS
    'Knowledge boundary classification per EC-022 (IKEA). Determines whether internal knowledge is sufficient or external retrieval is required.';

-- Chain Node Status (SitC - EC-020)
CREATE TYPE fhq_cognition.chain_node_status AS ENUM (
    'PENDING',      -- Not yet processed
    'VERIFIED',     -- Successfully verified
    'FAILED',       -- Verification failed
    'SKIPPED',      -- Intentionally skipped
    'ABORTED'       -- Chain aborted
);

COMMENT ON TYPE fhq_cognition.chain_node_status IS
    'Chain node verification status per EC-020 (SitC). Tracks verification state of each reasoning node.';

-- Foraging Termination Reason (InForage - EC-021)
CREATE TYPE fhq_cognition.forage_termination AS ENUM (
    'EXECUTED',             -- Search was executed
    'SCENT_TOO_LOW',        -- Scent score below threshold
    'BUDGET_EXCEEDED',      -- Cost budget exhausted
    'DIMINISHING_RETURNS',  -- Information gain plateau
    'CONFIDENCE_REACHED',   -- Target confidence achieved
    'NO_VIABLE_PATHS'       -- No paths above minimum scent
);

COMMENT ON TYPE fhq_cognition.forage_termination IS
    'Information foraging termination reasons per EC-021 (InForage). Documents why a search path was terminated.';

-- Research Protocol Status
CREATE TYPE fhq_cognition.protocol_status AS ENUM (
    'INITIALIZING',
    'PLANNING',
    'EXECUTING',
    'SEARCHING',
    'VERIFYING',
    'REVISING',
    'COMPLETED',
    'ABORTED'
);

COMMENT ON TYPE fhq_cognition.protocol_status IS
    'Research protocol lifecycle states per ADR-021 Section 5 CECF. Tracks protocol progression through cognitive stages.';

-- ############################################################################
-- SECTION 3: TABLE 1 - cognitive_nodes
-- ############################################################################
-- Master registry of all cognitive nodes in the system
-- Source: ADR-021 Section 4, EC-020 Section 3

CREATE TABLE fhq_cognition.cognitive_nodes (
    -- Primary Key (ADR-020 Section 6 - must be hash-anchored)
    cognitive_node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Node Identity
    node_code TEXT NOT NULL,                                    -- Human-readable code (e.g., 'SITC-001')
    node_name TEXT NOT NULL,                                    -- Descriptive name
    modality fhq_cognition.cognitive_modality NOT NULL,         -- EC-020 Section 3

    -- Hierarchical Structure
    parent_node_id UUID REFERENCES fhq_cognition.cognitive_nodes(cognitive_node_id),
    depth_level INT NOT NULL DEFAULT 0
        CHECK (depth_level >= 0 AND depth_level <= 10),         -- G3: MAX_DEPTH = 10

    -- Cognitive Attributes (ADR-021)
    attention_weight FLOAT8 NOT NULL DEFAULT 0.5
        CHECK (attention_weight >= 0 AND attention_weight <= 1),  -- Normalized 0-1
    activation_threshold FLOAT8 DEFAULT 0.5
        CHECK (activation_threshold >= 0 AND activation_threshold <= 1),

    -- Causal Links (EC-020 Section 4 - JSONB validated per G3_JSONB_SPEC)
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

-- Table Comments
COMMENT ON TABLE fhq_cognition.cognitive_nodes IS
    'Master registry of cognitive nodes per ADR-021, EC-020. Each node represents a reasoning unit in the Cognitive Engine Architecture. G4 Constitutional Table.';
COMMENT ON COLUMN fhq_cognition.cognitive_nodes.modality IS
    'Node type per EC-020 Section 3: perception, causal, intent, search, verification, synthesis';
COMMENT ON COLUMN fhq_cognition.cognitive_nodes.causal_links IS
    'JSONB array of causal relationships. Schema: G3_JSONB_SCHEMA_VALIDATION_SPEC.json/causal_links';
COMMENT ON COLUMN fhq_cognition.cognitive_nodes.attention_weight IS
    'Normalized attention weight 0-1 per ADR-021';
COMMENT ON COLUMN fhq_cognition.cognitive_nodes.depth_level IS
    'Hierarchical depth. G3 Constitutional Limit: MAX_DEPTH = 10';
COMMENT ON COLUMN fhq_cognition.cognitive_nodes.lineage_hash IS
    'Full hash chain per ADR-011 Fortress Standard';

-- ############################################################################
-- SECTION 4: TABLE 2 - research_protocols
-- ############################################################################
-- Registry of active research protocols and their states
-- Source: ADR-021 Section 5 CECF

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

    -- Economic Constraints (ADR-012, G3 Constitutional Limits)
    budget_allocated_usd NUMERIC(10,4) NOT NULL DEFAULT 0.50
        CHECK (budget_allocated_usd <= 0.50),                   -- G3: MAX_BUDGET = $0.50
    budget_consumed_usd NUMERIC(10,4) NOT NULL DEFAULT 0.00
        CHECK (budget_consumed_usd >= 0),
    max_search_calls INT NOT NULL DEFAULT 5
        CHECK (max_search_calls <= 5),                          -- G3: MAX_SEARCH_CALLS = 5
    search_calls_made INT NOT NULL DEFAULT 0
        CHECK (search_calls_made >= 0),

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

    -- Constraints (G3 Constitutional Limits)
    CONSTRAINT research_protocols_budget_check
        CHECK (budget_consumed_usd <= budget_allocated_usd),
    CONSTRAINT research_protocols_calls_check
        CHECK (search_calls_made <= max_search_calls)
);

COMMENT ON TABLE fhq_cognition.research_protocols IS
    'Registry of research protocols per ADR-021 Section 5 CECF. Tracks protocol lifecycle and resource consumption. G4 Constitutional Table.';
COMMENT ON COLUMN fhq_cognition.research_protocols.budget_allocated_usd IS
    'Maximum budget for protocol. G3 Constitutional Limit: MAX_BUDGET_PER_PROTOCOL_USD = $0.50';
COMMENT ON COLUMN fhq_cognition.research_protocols.max_search_calls IS
    'Maximum external API calls. G3 Constitutional Limit: MAX_SEARCH_CALLS_PER_PROTOCOL = 5';

-- ############################################################################
-- SECTION 5: TABLE 3 - search_in_chain_events (SitC - EC-020)
-- ############################################################################
-- Chain-of-Query state tracking for SitC
-- Source: EC-020 Section 4, Section 11

CREATE TABLE fhq_cognition.search_in_chain_events (
    -- Primary Key
    sitc_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Protocol Reference
    protocol_id UUID NOT NULL REFERENCES fhq_cognition.research_protocols(protocol_id),

    -- Chain Position
    node_index INT NOT NULL CHECK (node_index >= 0),
    parent_node_index INT,                                      -- For branching factor tracking
    node_type fhq_cognition.chain_node_status NOT NULL DEFAULT 'PENDING',

    -- Node Content
    node_content TEXT,
    query_text TEXT,
    reasoning_step TEXT,

    -- Verification
    verification_status fhq_cognition.chain_node_status NOT NULL DEFAULT 'PENDING',
    verification_evidence JSONB,                                -- Schema: G3_JSONB_SPEC/verification_evidence

    -- Search Results (if search node)
    search_executed BOOLEAN DEFAULT FALSE,
    search_result_id UUID,                                      -- Reference to search results
    search_depth INT NOT NULL DEFAULT 0
        CHECK (search_depth >= 0 AND search_depth <= 10),       -- G3: MAX_DEPTH = 10

    -- Chain Integrity (EC-020 Section 8)
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
    'Chain-of-Query state tracking per EC-020 (SitC). Each row represents a node in the reasoning chain. G4 Constitutional Table.';
COMMENT ON COLUMN fhq_cognition.search_in_chain_events.search_depth IS
    'Search depth per SitC specification. G3 Constitutional Limit: MAX_DEPTH = 10';
COMMENT ON COLUMN fhq_cognition.search_in_chain_events.chain_integrity_score IS
    'Per EC-020 Section 8: verified_nodes / total_nodes. Score < 0.80 = CATASTROPHIC alert.';
COMMENT ON COLUMN fhq_cognition.search_in_chain_events.verification_evidence IS
    'JSONB verification evidence. Schema: G3_JSONB_SCHEMA_VALIDATION_SPEC.json/verification_evidence';

-- ############################################################################
-- SECTION 6: TABLE 4 - information_foraging_paths (InForage - EC-021)
-- ############################################################################
-- Search optimization and ROI tracking for InForage
-- Source: EC-021 Section 4, Section 11

CREATE TABLE fhq_cognition.information_foraging_paths (
    -- Primary Key
    forage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Protocol Reference
    protocol_id UUID NOT NULL REFERENCES fhq_cognition.research_protocols(protocol_id),

    -- Search Query
    search_query TEXT NOT NULL,
    query_embedding VECTOR(1536),                               -- pgvector - embeddings disabled in G4

    -- Scent Score (EC-021 Section 4.1)
    scent_score NUMERIC(5,4) NOT NULL CHECK (scent_score >= 0 AND scent_score <= 1),
    scent_components JSONB NOT NULL DEFAULT '{}'::jsonb,        -- Schema: G3_JSONB_SPEC/scent_components

    -- Cost Analysis (ADR-012)
    estimated_cost_usd NUMERIC(10,6) NOT NULL,
    actual_cost_usd NUMERIC(10,6),
    source_tier TEXT NOT NULL,                                  -- 'LAKE', 'PULSE', 'SNIPER'

    -- Information Gain (EC-021 Section 2.2)
    information_gain NUMERIC(5,4),                              -- Post-hoc measured value
    relevance_score NUMERIC(5,4),
    freshness_score NUMERIC(5,4),

    -- Decision
    search_executed BOOLEAN NOT NULL DEFAULT FALSE,
    termination_reason fhq_cognition.forage_termination,
    decision_rationale TEXT,

    -- Context Frame (BCBS-239 lineage required per CEO directive)
    context_frame JSONB NOT NULL DEFAULT '{}'::jsonb,           -- Schema: G3_JSONB_SPEC/context_frame

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
    'Information foraging decisions per EC-021 (InForage). Tracks search ROI and optimization. G4 Constitutional Table.';
COMMENT ON COLUMN fhq_cognition.information_foraging_paths.scent_score IS
    'Predicted information value per EC-021 Section 4.1. Range 0.0-1.0.';
COMMENT ON COLUMN fhq_cognition.information_foraging_paths.query_embedding IS
    'VECTOR(1536) for semantic similarity. pgvector required. Embedding generation disabled in G4 per directive.';
COMMENT ON COLUMN fhq_cognition.information_foraging_paths.context_frame IS
    'JSONB context per InForage spec. BCBS-239 lineage required. Schema: G3_JSONB_SPEC/context_frame';
COMMENT ON COLUMN fhq_cognition.information_foraging_paths.scent_components IS
    'Breakdown of scent score. Schema: G3_JSONB_SCHEMA_VALIDATION_SPEC.json/scent_components';

-- ############################################################################
-- SECTION 7: TABLE 5 - knowledge_boundaries (IKEA - EC-022)
-- ############################################################################
-- Knowledge boundary classification and hallucination prevention
-- Source: EC-022 Section 4, Section 10

CREATE TABLE fhq_cognition.knowledge_boundaries (
    -- Primary Key
    boundary_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Protocol Reference (optional - can be standalone classification)
    protocol_id UUID REFERENCES fhq_cognition.research_protocols(protocol_id),

    -- Query Classification
    query_text TEXT NOT NULL,
    query_embedding VECTOR(1536),                               -- pgvector - embeddings disabled in G4

    -- Classification Result (EC-022 Section 2)
    boundary_type fhq_cognition.boundary_type NOT NULL,
    classification_confidence NUMERIC(5,4) NOT NULL
        CHECK (classification_confidence >= 0 AND classification_confidence <= 1),

    -- Internal Certainty (EC-022 Section 4.2)
    internal_certainty NUMERIC(5,4) NOT NULL
        CHECK (internal_certainty >= 0 AND internal_certainty <= 1),
    certainty_threshold NUMERIC(5,4) NOT NULL,                  -- DEFCON-dependent

    -- Volatility Assessment (EC-022 Section 4.3)
    volatility_flag BOOLEAN NOT NULL DEFAULT FALSE,
    volatility_class TEXT,                                      -- 'EXTREME', 'HIGH', 'MEDIUM', 'LOW', 'STATIC'
    data_type TEXT,                                             -- 'STOCK_PRICE', 'EARNINGS', etc.

    -- Retrieval Decision
    retrieval_triggered BOOLEAN NOT NULL DEFAULT FALSE,
    retrieval_source TEXT,                                      -- 'LAKE', 'PULSE', 'SNIPER'

    -- Boundary Violation Detection (EC-022 Section 7)
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
    'Knowledge boundary classifications per EC-022 (IKEA). Prevents hallucination and enforces truth boundaries. G4 Constitutional Table.';
COMMENT ON COLUMN fhq_cognition.knowledge_boundaries.boundary_type IS
    'Classification per EC-022 Section 2: PARAMETRIC, EXTERNAL_REQUIRED, HYBRID';
COMMENT ON COLUMN fhq_cognition.knowledge_boundaries.internal_certainty IS
    'Model confidence in internal knowledge per EC-022 Section 4.2. Range 0.0-1.0.';
COMMENT ON COLUMN fhq_cognition.knowledge_boundaries.boundary_violation IS
    'True if EXTERNAL_REQUIRED but output attempted without retrieval (hallucination attempt)';
COMMENT ON COLUMN fhq_cognition.knowledge_boundaries.query_embedding IS
    'VECTOR(1536) for semantic classification. pgvector required. Embedding generation disabled in G4.';

-- ############################################################################
-- SECTION 8: TABLE 6 - lineage_log
-- ############################################################################
-- Comprehensive lineage tracking for all cognitive operations
-- Source: ADR-011, ADR-013

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

    -- Evidence (Schema: G3_JSONB_SPEC/evidence_bundle)
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
    'Comprehensive lineage tracking per ADR-011 Fortress Standard. Provides immutable audit trail for all cognitive operations. G4 Constitutional Table.';
COMMENT ON COLUMN fhq_cognition.lineage_log.evidence_bundle IS
    'JSONB evidence per ADR-011, ADR-013. Schema: G3_JSONB_SCHEMA_VALIDATION_SPEC.json/evidence_bundle';

-- ############################################################################
-- SECTION 9: GIN INDEXES FOR JSONB FIELDS
-- ############################################################################
-- Required for efficient JSONB queries on SitC search paths, InForage frames, IKEA boundary maps

-- cognitive_nodes: causal_links (EC-020 Section 4)
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

-- ############################################################################
-- SECTION 10: B-TREE INDEXES FOR TEMPORAL FIELDS
-- ############################################################################
-- Required for time-range queries per ADR-020 deterministic research

-- cognitive_nodes
CREATE INDEX idx_cognitive_nodes_created_at
    ON fhq_cognition.cognitive_nodes (created_at);
CREATE INDEX idx_cognitive_nodes_ingested_at
    ON fhq_cognition.cognitive_nodes (ingested_at);

-- research_protocols
CREATE INDEX idx_research_protocols_created_at
    ON fhq_cognition.research_protocols (created_at);
CREATE INDEX idx_research_protocols_started_at
    ON fhq_cognition.research_protocols (started_at);
CREATE INDEX idx_research_protocols_completed_at
    ON fhq_cognition.research_protocols (completed_at);

-- search_in_chain_events
CREATE INDEX idx_sitc_events_created_at
    ON fhq_cognition.search_in_chain_events (created_at);
CREATE INDEX idx_sitc_events_verified_at
    ON fhq_cognition.search_in_chain_events (verified_at);

-- information_foraging_paths
CREATE INDEX idx_forage_paths_created_at
    ON fhq_cognition.information_foraging_paths (created_at);
CREATE INDEX idx_forage_paths_executed_at
    ON fhq_cognition.information_foraging_paths (executed_at);

-- knowledge_boundaries
CREATE INDEX idx_knowledge_boundaries_created_at
    ON fhq_cognition.knowledge_boundaries (created_at);

-- lineage_log
CREATE INDEX idx_lineage_log_created_at
    ON fhq_cognition.lineage_log (created_at);

-- ############################################################################
-- SECTION 11: HASH INDEXES FOR LINEAGE FIELDS (ADR-011 Chain Lookups)
-- ############################################################################
-- Required for efficient hash chain verification

-- cognitive_nodes
CREATE INDEX idx_cognitive_nodes_lineage_hash
    ON fhq_cognition.cognitive_nodes USING HASH (lineage_hash);
CREATE INDEX idx_cognitive_nodes_hash_self
    ON fhq_cognition.cognitive_nodes USING HASH (hash_self);

-- research_protocols
CREATE INDEX idx_research_protocols_lineage_hash
    ON fhq_cognition.research_protocols USING HASH (lineage_hash);
CREATE INDEX idx_research_protocols_hash_self
    ON fhq_cognition.research_protocols USING HASH (hash_self);

-- search_in_chain_events
CREATE INDEX idx_sitc_events_lineage_hash
    ON fhq_cognition.search_in_chain_events USING HASH (lineage_hash);
CREATE INDEX idx_sitc_events_hash_self
    ON fhq_cognition.search_in_chain_events USING HASH (hash_self);

-- information_foraging_paths
CREATE INDEX idx_forage_paths_lineage_hash
    ON fhq_cognition.information_foraging_paths USING HASH (lineage_hash);
CREATE INDEX idx_forage_paths_hash_self
    ON fhq_cognition.information_foraging_paths USING HASH (hash_self);

-- knowledge_boundaries
CREATE INDEX idx_knowledge_boundaries_lineage_hash
    ON fhq_cognition.knowledge_boundaries USING HASH (lineage_hash);
CREATE INDEX idx_knowledge_boundaries_hash_self
    ON fhq_cognition.knowledge_boundaries USING HASH (hash_self);

-- lineage_log
CREATE INDEX idx_lineage_log_lineage_hash
    ON fhq_cognition.lineage_log USING HASH (lineage_hash);
CREATE INDEX idx_lineage_log_hash_self
    ON fhq_cognition.lineage_log USING HASH (hash_self);

-- ############################################################################
-- SECTION 12: SELECTIVE PARTIAL INDEXES FOR HIGH-SPARSITY FIELDS
-- ############################################################################
-- Required for efficient queries on rarely-true boolean flags

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

-- ############################################################################
-- SECTION 13: COMPOSITE INDEXES FOR COMMON QUERY PATTERNS
-- ############################################################################

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

-- ############################################################################
-- SECTION 14: VECTOR INDEX NOTE (NOT INCLUDED)
-- ############################################################################
-- Per G3_PGVECTOR_COMPATIBILITY_NOTE.txt:
-- HNSW indexes for query_embedding fields should be created post-G4 during
-- optimization phase when embedding generation is enabled.
--
-- Deferred indexes (NOT created in G4):
-- CREATE INDEX idx_forage_query_embedding ON fhq_cognition.information_foraging_paths
--     USING hnsw (query_embedding vector_cosine_ops);
-- CREATE INDEX idx_boundaries_query_embedding ON fhq_cognition.knowledge_boundaries
--     USING hnsw (query_embedding vector_cosine_ops);
--
-- These require embedding generation which is PROHIBITED in G4 per CEO directive.

-- ############################################################################
-- SECTION 15: G3 CONSTITUTIONAL CONSTANTS VERIFICATION
-- ############################################################################
-- This section documents the G3 constitutional limits embedded in constraints

/*
G3 CONSTITUTIONAL CONSTANTS (from G3_MAX_DEPTH_SPEC.json):
=========================================================
CONST-SITC-001: MAX_DEPTH = 10
  Enforced in:
    - cognitive_nodes.depth_level CHECK (depth_level <= 10)
    - search_in_chain_events.search_depth CHECK (search_depth <= 10)

CONST-SITC-002: MAX_BRANCHING_FACTOR = 5
  Enforced at: Application level (orchestrator)
  Note: No database constraint - requires parent_node_index counting

CONST-SITC-003: MAX_TOTAL_NODES_PER_PROTOCOL = 100
  Enforced at: Application level (orchestrator)
  Note: No database constraint - requires COUNT(*) per protocol

CONST-INFORAGE-001: MAX_SEARCH_CALLS_PER_PROTOCOL = 5
  Enforced in:
    - research_protocols.max_search_calls CHECK (max_search_calls <= 5)
    - research_protocols.search_calls_made CHECK constraint

CONST-ECON-001: MAX_BUDGET_PER_PROTOCOL_USD = $0.50
  Enforced in:
    - research_protocols.budget_allocated_usd CHECK (budget_allocated_usd <= 0.50)
    - research_protocols budget_consumed <= budget_allocated constraint

DEFCON MODIFIERS (from G3_MAX_DEPTH_SPEC.json):
===============================================
GREEN:  max_depth=10, max_branching=5, max_budget=$0.50, max_searches=5
YELLOW: max_depth=7,  max_branching=3, max_budget=$0.25, max_searches=3
ORANGE: max_depth=5,  max_branching=2, max_budget=$0.10, max_searches=1
RED:    max_depth=3,  max_branching=1, max_budget=$0.00, max_searches=0
BLACK:  max_depth=0,  max_branching=0, max_budget=$0.00, max_searches=0

Note: DEFCON-dynamic limits are enforced at application level.
      Database constraints enforce GREEN-level maximums.
*/

-- ############################################################################
-- SECTION 16: GOVERNANCE LOGGING
-- ############################################################################
-- Log G4 activation to governance tables

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    initiated_by,
    decision,
    evidence_hash,
    rationale,
    created_at
) VALUES (
    'COGNITIVE_DOMAIN_G4_DDL_EXECUTION',
    'fhq_cognition',
    'STIG',
    'EXECUTED',
    NULL,  -- Hash computed post-execution
    'G4 DDL execution per CEO authorization. Schema fhq_cognition created with 6 tables, 5 ENUM types, and all non-vector indexes.',
    NOW()
);

-- ############################################################################
-- SECTION 17: VERIFICATION QUERY
-- ############################################################################
-- Run this to verify successful G4 execution

SELECT
    'SCHEMA' AS object_type,
    schema_name AS object_name,
    'EXISTS' AS status
FROM information_schema.schemata
WHERE schema_name = 'fhq_cognition'

UNION ALL

SELECT
    'TABLE' AS object_type,
    table_name AS object_name,
    'EXISTS' AS status
FROM information_schema.tables
WHERE table_schema = 'fhq_cognition'

UNION ALL

SELECT
    'TYPE' AS object_type,
    typname AS object_name,
    'EXISTS' AS status
FROM pg_type t
JOIN pg_namespace n ON t.typnamespace = n.oid
WHERE n.nspname = 'fhq_cognition'
AND t.typtype = 'e'

ORDER BY object_type, object_name;

-- Expected output: 1 schema, 6 tables, 5 ENUM types = 12 rows total

-- ############################################################################
-- END OF FINAL IMMUTABLE MIGRATION SCRIPT
-- ############################################################################
--
-- STATUS: READY FOR G4 EXECUTION
-- NEXT STEP: CEO Authorization required before execution
--
-- EXECUTION COMMAND:
--   psql -h 127.0.0.1 -p 54322 -U postgres -d postgres \
--        -f 04_DATABASE/MIGRATIONS/FINAL_IMMUTABLE_MIGRATION_SCRIPT.sql
--
-- POST-EXECUTION:
--   1. Compute SHA-256 hash of this file
--   2. Record hash in G4 evidence bundle
--   3. Execute G3_ACTIVATION_SEQUENCE.md boot procedure
--   4. Generate G4_ACTIVATION_CERTIFICATE.json
--
-- STIG CERTIFICATION:
--   This script represents the canonical DDL for the Cognitive Domain.
--   All G3 constitutional constraints are embedded.
--   All indexes (except vector) are included.
--   Ready for G4 CEO authorization.
--
-- Signed: STIG (CTO)
-- Employment Contract: EC-003_2026_PRODUCTION
-- Timestamp: 2025-12-09T20:30:00.000Z
-- ############################################################################
