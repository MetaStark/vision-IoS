-- Migration 175: FINN GraphRAG Evidence Infrastructure
-- CEO-DIR-2025-FINN-001 Phase 1
-- Date: 2025-12-30
-- Author: STIG (CTO)
--
-- Purpose: Create evidence node storage for GraphRAG retrieval.
-- CRITICAL RULE: Qdrant stores embeddings, Postgres stores relationships.
--
-- GraphRAG Retrieval Contract:
--   Step 1: Qdrant → candidate nodes (semantic proximity)
--   Step 2: Postgres → relationship expansion (edges, hops, causality)
--   Step 3: FINN → reasoning + synthesis
--
-- ADR Compliance: ADR-020 (ACI), ADR-013 (Canonical Truth), ADR-011 (Hash Chains)
-- EC Compliance: EC-020 (SitC), EC-021 (InForage), EC-022 (IKEA)

BEGIN;

-- ============================================================================
-- SCHEMA: fhq_canonical (constitutional truth storage)
-- ============================================================================

-- Table: evidence_nodes
-- Stores structured facts with Qdrant embedding references
-- This is the authoritative source; Qdrant mirrors for similarity search
CREATE TABLE IF NOT EXISTS fhq_canonical.evidence_nodes (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Content
    content TEXT NOT NULL,
    content_type TEXT NOT NULL,  -- FACT, CLAIM, CITATION, METRIC, OBSERVATION
    source_type TEXT NOT NULL,   -- API, DATABASE, DOCUMENT, FINN_INFERENCE
    source_reference TEXT,       -- URL, table.column, document path

    -- Semantic classification
    domain TEXT NOT NULL DEFAULT 'FINANCE',  -- FINANCE, MACRO, CRYPTO, REGULATORY
    entity_type TEXT,            -- ASSET, INDICATOR, EVENT, RELATIONSHIP
    entity_id TEXT,              -- Reference to fhq_canonical.assets or similar
    temporal_scope TEXT,         -- POINT_IN_TIME, RANGE, ONGOING

    -- Timestamps
    data_timestamp TIMESTAMPTZ,  -- When the fact was true (not when recorded)
    expires_at TIMESTAMPTZ,      -- TTL based on regime multiplier
    ttl_regime TEXT DEFAULT 'NEUTRAL',  -- NEUTRAL, VOLATILE, BROKEN

    -- Quality metrics
    confidence_score NUMERIC(5,4) DEFAULT 1.0,  -- 0-1, from EC-022 IKEA
    verification_status TEXT DEFAULT 'UNVERIFIED',  -- UNVERIFIED, VERIFIED, STALE, FABRICATION
    verification_method TEXT,    -- DIRECT_QUERY, CROSS_REFERENCE, MANUAL
    verified_at TIMESTAMPTZ,
    verified_by TEXT,

    -- Qdrant sync
    qdrant_collection TEXT DEFAULT 'evidence_nodes',
    qdrant_point_id TEXT,        -- UUID from Qdrant
    embedding_model TEXT DEFAULT 'text-embedding-3-small',
    embedding_generated_at TIMESTAMPTZ,

    -- Hash chain (ADR-011)
    content_hash TEXT NOT NULL,
    hash_prev TEXT,
    hash_self TEXT,

    -- Provenance
    created_by TEXT DEFAULT 'FINN',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constitutional constraint
    CONSTRAINT evidence_confidence_range CHECK (confidence_score >= 0 AND confidence_score <= 1)
);

-- Indexes for GraphRAG retrieval
CREATE INDEX IF NOT EXISTS idx_evidence_domain ON fhq_canonical.evidence_nodes(domain);
CREATE INDEX IF NOT EXISTS idx_evidence_entity ON fhq_canonical.evidence_nodes(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_evidence_temporal ON fhq_canonical.evidence_nodes(data_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_expires ON fhq_canonical.evidence_nodes(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_evidence_qdrant ON fhq_canonical.evidence_nodes(qdrant_point_id);
CREATE INDEX IF NOT EXISTS idx_evidence_verification ON fhq_canonical.evidence_nodes(verification_status);

-- ============================================================================
-- Table: evidence_relationships
-- Links between evidence nodes (not causal - that's in fhq_graph.edges)
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_canonical.evidence_relationships (
    relationship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_evidence_id UUID NOT NULL REFERENCES fhq_canonical.evidence_nodes(evidence_id),
    to_evidence_id UUID NOT NULL REFERENCES fhq_canonical.evidence_nodes(evidence_id),

    relationship_type TEXT NOT NULL,  -- SUPPORTS, CONTRADICTS, CITES, UPDATES, EXPANDS
    strength NUMERIC(5,4) DEFAULT 1.0,

    -- For GraphRAG traversal
    traversal_weight NUMERIC(5,4) DEFAULT 1.0,  -- Used for hop scoring

    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT evidence_rel_not_self CHECK (from_evidence_id != to_evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_evidence_rel_from ON fhq_canonical.evidence_relationships(from_evidence_id);
CREATE INDEX IF NOT EXISTS idx_evidence_rel_to ON fhq_canonical.evidence_relationships(to_evidence_id);
CREATE INDEX IF NOT EXISTS idx_evidence_rel_type ON fhq_canonical.evidence_relationships(relationship_type);

-- ============================================================================
-- Table: financial_ontology
-- FIBO-inspired concept taxonomy for semantic classification
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_canonical.financial_ontology (
    concept_id TEXT PRIMARY KEY,
    parent_concept_id TEXT REFERENCES fhq_canonical.financial_ontology(concept_id),

    label TEXT NOT NULL,
    description TEXT,
    ontology_source TEXT DEFAULT 'FIBO',  -- FIBO, CUSTOM, DERIVED

    -- Hierarchy
    level INTEGER DEFAULT 0,
    path_from_root TEXT,  -- Materialized path for fast hierarchy queries

    -- Semantic properties
    synonyms TEXT[],
    related_concepts TEXT[],

    -- Usage tracking
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed FIBO core concepts relevant to FjordHQ
INSERT INTO fhq_canonical.financial_ontology (concept_id, label, description, level, path_from_root)
VALUES
    -- Level 0: Root domains
    ('FBC', 'Financial Business & Commerce', 'FIBO Foundation Business & Commerce', 0, '/FBC'),
    ('FND', 'Foundations', 'FIBO Foundations', 0, '/FND'),
    ('SEC', 'Securities', 'FIBO Securities', 0, '/SEC'),
    ('IND', 'Indices & Indicators', 'FIBO Indices & Indicators', 0, '/IND'),

    -- Level 1: Core concepts
    ('FBC/ASSET', 'Asset', 'A resource controlled by an entity', 1, '/FBC/ASSET'),
    ('FBC/INSTRUMENT', 'Financial Instrument', 'A contract that gives rise to a financial asset', 1, '/FBC/INSTRUMENT'),
    ('FBC/MARKET', 'Market', 'A venue for trading', 1, '/FBC/MARKET'),
    ('FBC/ENTITY', 'Market Participant', 'An entity that participates in markets', 1, '/FBC/ENTITY'),

    ('FND/QUANTITATIVE', 'Quantitative Value', 'A measurable quantity', 1, '/FND/QUANTITATIVE'),
    ('FND/TEMPORAL', 'Temporal Concept', 'Time-related concept', 1, '/FND/TEMPORAL'),
    ('FND/RELATION', 'Relation', 'A connection between concepts', 1, '/FND/RELATION'),

    ('SEC/EQUITY', 'Equity Security', 'Ownership in a company', 1, '/SEC/EQUITY'),
    ('SEC/DEBT', 'Debt Security', 'A debt obligation', 1, '/SEC/DEBT'),
    ('SEC/DERIVATIVE', 'Derivative', 'A contract derived from underlying', 1, '/SEC/DERIVATIVE'),

    ('IND/PRICE', 'Price Indicator', 'Price-based indicator', 1, '/IND/PRICE'),
    ('IND/MACRO', 'Macroeconomic Indicator', 'Economy-wide indicator', 1, '/IND/MACRO'),
    ('IND/SENTIMENT', 'Sentiment Indicator', 'Market sentiment measure', 1, '/IND/SENTIMENT')
ON CONFLICT (concept_id) DO NOTHING;

-- Level 2: FjordHQ-specific concepts
INSERT INTO fhq_canonical.financial_ontology (concept_id, parent_concept_id, label, description, level, path_from_root)
VALUES
    -- Crypto assets (not in FIBO, custom extension)
    ('FBC/ASSET/CRYPTO', 'FBC/ASSET', 'Cryptocurrency', 'Digital asset using cryptography', 2, '/FBC/ASSET/CRYPTO'),
    ('FBC/ASSET/CRYPTO/BTC', 'FBC/ASSET/CRYPTO', 'Bitcoin', 'BTC cryptocurrency', 3, '/FBC/ASSET/CRYPTO/BTC'),
    ('FBC/ASSET/CRYPTO/ETH', 'FBC/ASSET/CRYPTO', 'Ethereum', 'ETH cryptocurrency', 3, '/FBC/ASSET/CRYPTO/ETH'),
    ('FBC/ASSET/CRYPTO/SOL', 'FBC/ASSET/CRYPTO', 'Solana', 'SOL cryptocurrency', 3, '/FBC/ASSET/CRYPTO/SOL'),

    -- Macro indicators
    ('IND/MACRO/FED', 'IND/MACRO', 'Federal Reserve', 'Fed policy indicators', 2, '/IND/MACRO/FED'),
    ('IND/MACRO/YIELD', 'IND/MACRO', 'Yield Curve', 'Bond yield indicators', 2, '/IND/MACRO/YIELD'),
    ('IND/MACRO/LIQUIDITY', 'IND/MACRO', 'Liquidity', 'Market liquidity metrics', 2, '/IND/MACRO/LIQUIDITY'),

    -- Regime concepts (FjordHQ-specific)
    ('FND/REGIME', 'FND/TEMPORAL', 'Market Regime', 'Characterization of market state', 2, '/FND/TEMPORAL/REGIME'),
    ('FND/REGIME/RISK_ON', 'FND/REGIME', 'Risk-On Regime', 'Risk-seeking market state', 3, '/FND/TEMPORAL/REGIME/RISK_ON'),
    ('FND/REGIME/RISK_OFF', 'FND/REGIME', 'Risk-Off Regime', 'Risk-averse market state', 3, '/FND/TEMPORAL/REGIME/RISK_OFF'),
    ('FND/REGIME/TRANSITION', 'FND/REGIME', 'Regime Transition', 'Changing market state', 3, '/FND/TEMPORAL/REGIME/TRANSITION'),

    -- Causal concepts
    ('FND/RELATION/CAUSAL', 'FND/RELATION', 'Causal Relation', 'Cause-effect relationship', 2, '/FND/RELATION/CAUSAL'),
    ('FND/RELATION/CORRELATION', 'FND/RELATION', 'Correlation', 'Statistical co-movement', 2, '/FND/RELATION/CORRELATION'),
    ('FND/RELATION/GRANGER', 'FND/RELATION/CAUSAL', 'Granger Causality', 'Temporal predictive relationship', 3, '/FND/RELATION/CAUSAL/GRANGER')
ON CONFLICT (concept_id) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_ontology_parent ON fhq_canonical.financial_ontology(parent_concept_id);
CREATE INDEX IF NOT EXISTS idx_ontology_path ON fhq_canonical.financial_ontology(path_from_root);

-- ============================================================================
-- Table: qdrant_sync_log
-- Tracks synchronization between Postgres and Qdrant
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_operational.qdrant_sync_log (
    sync_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_name TEXT NOT NULL,
    operation TEXT NOT NULL,  -- INSERT, UPDATE, DELETE, BULK_SYNC
    source_table TEXT NOT NULL,  -- fhq_canonical.evidence_nodes, etc.
    source_id TEXT NOT NULL,

    qdrant_point_id TEXT,
    qdrant_response JSONB,

    status TEXT DEFAULT 'PENDING',  -- PENDING, SUCCESS, FAILED, RETRY
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_qdrant_sync_status ON fhq_operational.qdrant_sync_log(status);
CREATE INDEX IF NOT EXISTS idx_qdrant_sync_collection ON fhq_operational.qdrant_sync_log(collection_name, source_table);

-- ============================================================================
-- Function: calculate_evidence_ttl
-- Calculates TTL based on regime multiplier from calibration_versions
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_canonical.calculate_evidence_ttl(
    p_base_ttl_days INTEGER,
    p_regime TEXT
) RETURNS TIMESTAMPTZ AS $$
DECLARE
    v_multiplier NUMERIC;
    v_param_name TEXT;
BEGIN
    -- Map regime to calibration parameter
    v_param_name := 'TTL_' || UPPER(p_regime);

    -- Get active multiplier from calibration_versions
    SELECT value INTO v_multiplier
    FROM fhq_governance.calibration_versions
    WHERE parameter_name = v_param_name
      AND is_active = TRUE
    LIMIT 1;

    -- Default to 1.0 if not found
    IF v_multiplier IS NULL THEN
        v_multiplier := 1.0;
    END IF;

    RETURN NOW() + (p_base_ttl_days * v_multiplier || ' days')::INTERVAL;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- Function: hash_evidence_content
-- Creates content hash for evidence nodes (ADR-011)
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_canonical.hash_evidence_content(
    p_content TEXT,
    p_source_type TEXT,
    p_data_timestamp TIMESTAMPTZ
) RETURNS TEXT AS $$
BEGIN
    RETURN encode(
        sha256(
            (p_content || '|' || p_source_type || '|' || COALESCE(p_data_timestamp::TEXT, 'NULL'))::bytea
        ),
        'hex'
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- Trigger: evidence_hash_chain
-- Automatically maintains hash chain on insert
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_canonical.evidence_hash_chain_trigger()
RETURNS TRIGGER AS $$
DECLARE
    v_prev_hash TEXT;
BEGIN
    -- Calculate content hash
    NEW.content_hash := fhq_canonical.hash_evidence_content(
        NEW.content, NEW.source_type, NEW.data_timestamp
    );

    -- Get previous hash from last evidence in same domain
    SELECT hash_self INTO v_prev_hash
    FROM fhq_canonical.evidence_nodes
    WHERE domain = NEW.domain
    ORDER BY created_at DESC
    LIMIT 1;

    NEW.hash_prev := COALESCE(v_prev_hash, 'GENESIS');

    -- Calculate self hash (includes prev for chain integrity)
    NEW.hash_self := encode(
        sha256((NEW.content_hash || '|' || NEW.hash_prev)::bytea),
        'hex'
    );

    NEW.updated_at := NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_evidence_hash_chain
    BEFORE INSERT ON fhq_canonical.evidence_nodes
    FOR EACH ROW
    EXECUTE FUNCTION fhq_canonical.evidence_hash_chain_trigger();

-- ============================================================================
-- View: evidence_graph_nodes
-- GraphRAG-friendly view for 2-hop retrieval
-- ============================================================================
CREATE OR REPLACE VIEW fhq_canonical.evidence_graph_view AS
SELECT
    e.evidence_id,
    e.content,
    e.content_type,
    e.domain,
    e.entity_type,
    e.entity_id,
    e.data_timestamp,
    e.confidence_score,
    e.verification_status,
    e.qdrant_point_id,
    -- Related evidence (1-hop)
    (
        SELECT jsonb_agg(jsonb_build_object(
            'evidence_id', r.to_evidence_id,
            'relationship_type', r.relationship_type,
            'strength', r.strength
        ))
        FROM fhq_canonical.evidence_relationships r
        WHERE r.from_evidence_id = e.evidence_id
    ) as outgoing_relations,
    (
        SELECT jsonb_agg(jsonb_build_object(
            'evidence_id', r.from_evidence_id,
            'relationship_type', r.relationship_type,
            'strength', r.strength
        ))
        FROM fhq_canonical.evidence_relationships r
        WHERE r.to_evidence_id = e.evidence_id
    ) as incoming_relations
FROM fhq_canonical.evidence_nodes e
WHERE e.verification_status != 'FABRICATION'
  AND (e.expires_at IS NULL OR e.expires_at > NOW());

-- ============================================================================
-- Grants
-- ============================================================================
GRANT SELECT ON fhq_canonical.evidence_nodes TO PUBLIC;
GRANT SELECT ON fhq_canonical.evidence_relationships TO PUBLIC;
GRANT SELECT ON fhq_canonical.financial_ontology TO PUBLIC;
GRANT SELECT ON fhq_canonical.evidence_graph_view TO PUBLIC;
GRANT SELECT ON fhq_operational.qdrant_sync_log TO PUBLIC;

-- FINN can write evidence (via G0 proposals)
GRANT INSERT, UPDATE ON fhq_canonical.evidence_nodes TO postgres;
GRANT INSERT ON fhq_canonical.evidence_relationships TO postgres;
GRANT INSERT ON fhq_operational.qdrant_sync_log TO postgres;
GRANT UPDATE ON fhq_operational.qdrant_sync_log TO postgres;

COMMIT;

-- ============================================================================
-- Migration verification
-- ============================================================================
DO $$
DECLARE
    v_evidence_count INTEGER;
    v_ontology_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_evidence_count FROM fhq_canonical.evidence_nodes;
    SELECT COUNT(*) INTO v_ontology_count FROM fhq_canonical.financial_ontology;

    RAISE NOTICE 'Migration 175 complete:';
    RAISE NOTICE '  - evidence_nodes table created (% rows)', v_evidence_count;
    RAISE NOTICE '  - evidence_relationships table created';
    RAISE NOTICE '  - financial_ontology seeded with % FIBO concepts', v_ontology_count;
    RAISE NOTICE '  - qdrant_sync_log tracking table created';
    RAISE NOTICE '  - TTL calculation bound to calibration_versions';
    RAISE NOTICE '  - Hash chain triggers active (ADR-011)';
END $$;
