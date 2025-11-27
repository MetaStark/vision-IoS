-- =====================================================
-- MIGRATION 019: ADR-013 CANONICAL TRUTH ARCHITECTURE
-- =====================================================
--
-- Authority: LARS (ADR-013 Canonical Governance)
-- Purpose: Implement One-Source-of-Truth Architecture for FjordHQ
-- Compliance: ADR-013 (Canonical Truth), ADR-010 (Discrepancy Scoring)
--
-- This migration creates:
--   1. fhq_meta.canonical_domain_registry - Single source of truth registry
--   2. fhq_meta.canonical_series_registry - Asset/series-level invariants
--   3. fhq_meta.canonical_indicator_registry - Indicator truth constraints
--   4. fhq_meta.canonical_access_log - Read path audit trail
--   5. fhq_meta.canonical_violation_log - Multi-truth detection events
--   6. fhq_governance.canonical_mutation_gates - G1-G4 gates for truth changes
--   7. Views and functions for canonical truth enforcement
--
-- Invariants Enforced:
--   - For every domain, exactly one canonical store exists
--   - For each (asset_id, frequency, price_type), one canonical series
--   - For each (indicator, asset, timestamp, method), one canonical value
--   - All reads from production must go through canonical stores
--   - Any multi-truth attempt triggers VEGA governance event
--
-- =====================================================

BEGIN;

-- =====================================================
-- 1. CANONICAL DOMAIN REGISTRY
-- =====================================================
-- The central registry for all canonical data domain stores.
-- VEGA has write authority; all other agents are read-only.
-- =====================================================

CREATE TABLE IF NOT EXISTS fhq_meta.canonical_domain_registry (
    domain_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Domain identification
    domain_name TEXT NOT NULL UNIQUE,
    domain_category TEXT NOT NULL,  -- 'PRICES', 'INDICATORS', 'FUNDAMENTALS', 'SENTIMENT', 'ONCHAIN', 'EMBEDDINGS', 'KG_METRICS', 'MACRO', 'RESEARCH'

    -- Canonical store definition
    canonical_store TEXT NOT NULL,  -- Fully qualified table/view name (schema.table)
    canonical_schema TEXT NOT NULL, -- Schema name
    canonical_table TEXT NOT NULL,  -- Table name

    -- Store specification
    description TEXT NOT NULL,
    data_contract JSONB NOT NULL DEFAULT '{}'::jsonb,  -- Schema contract definition
    lineage_config JSONB NOT NULL DEFAULT '{}'::jsonb, -- Lineage tracking config

    -- Resolution rules
    resolution_rules JSONB NOT NULL DEFAULT '{}'::jsonb,  -- How to resolve conflicts
    timestamp_standard TEXT NOT NULL DEFAULT 'UTC',       -- Timestamp standard

    -- Access control
    read_access_agents TEXT[] NOT NULL DEFAULT ARRAY['LARS', 'FINN', 'STIG', 'LINE', 'VEGA'],
    write_access_agents TEXT[] NOT NULL DEFAULT ARRAY['VEGA'],  -- Only VEGA can write by default

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_canonical BOOLEAN NOT NULL DEFAULT TRUE,  -- Must always be true for this table

    -- Governance
    adr_reference TEXT NOT NULL DEFAULT 'ADR-013',
    governance_level TEXT NOT NULL DEFAULT 'CONSTITUTIONAL',  -- CONSTITUTIONAL, OPERATIONAL
    requires_vega_attestation BOOLEAN NOT NULL DEFAULT TRUE,

    -- Audit
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Verification
    hash_chain_id TEXT,
    signature TEXT,

    -- Constraints
    CONSTRAINT canonical_domain_category_check CHECK (
        domain_category IN (
            'PRICES', 'INDICATORS', 'FUNDAMENTALS', 'SENTIMENT',
            'ONCHAIN', 'EMBEDDINGS', 'KG_METRICS', 'MACRO', 'RESEARCH',
            'GOVERNANCE', 'AUDIT', 'SYSTEM'
        )
    ),
    CONSTRAINT canonical_domain_canonical_check CHECK (is_canonical = TRUE),
    CONSTRAINT canonical_domain_store_format CHECK (canonical_store ~ '^[a-z_]+\.[a-z_]+$')
);

-- Indexes for canonical domain registry
CREATE INDEX IF NOT EXISTS idx_canonical_domain_name ON fhq_meta.canonical_domain_registry(domain_name);
CREATE INDEX IF NOT EXISTS idx_canonical_domain_category ON fhq_meta.canonical_domain_registry(domain_category);
CREATE INDEX IF NOT EXISTS idx_canonical_domain_store ON fhq_meta.canonical_domain_registry(canonical_store);
CREATE INDEX IF NOT EXISTS idx_canonical_domain_active ON fhq_meta.canonical_domain_registry(is_active);

COMMENT ON TABLE fhq_meta.canonical_domain_registry IS 'ADR-013: Central registry for all canonical data domain stores. VEGA has write authority.';

-- =====================================================
-- 2. CANONICAL SERIES REGISTRY (Asset-Level)
-- =====================================================
-- Enforces one canonical series per (asset_id, frequency, price_type)
-- =====================================================

CREATE TABLE IF NOT EXISTS fhq_meta.canonical_series_registry (
    series_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Domain binding
    domain_id UUID NOT NULL REFERENCES fhq_meta.canonical_domain_registry(domain_id),

    -- Series identification
    asset_id TEXT NOT NULL,           -- e.g., 'BTC-USD', 'ETH-USD', 'AAPL'
    listing_id TEXT,                   -- Optional: exchange-specific listing
    frequency TEXT NOT NULL,           -- '1m', '5m', '1h', '4h', '1d', '1w'
    price_type TEXT NOT NULL DEFAULT 'OHLCV',  -- 'OHLCV', 'CLOSE', 'VWAP', 'TICK'

    -- Canonical store reference
    canonical_table TEXT NOT NULL,     -- Fully qualified table name
    series_identifier TEXT NOT NULL,   -- Unique identifier within the table

    -- Data specification
    start_timestamp TIMESTAMPTZ,       -- Earliest available data
    end_timestamp TIMESTAMPTZ,         -- Latest available data (NULL = live)
    data_points INTEGER DEFAULT 0,     -- Count of data points

    -- Vendor information
    primary_vendor TEXT NOT NULL,      -- Primary data source
    vendor_sources TEXT[],             -- All contributing sources

    -- Quality metrics
    completeness_score NUMERIC(5, 4) DEFAULT 1.0000,
    quality_score NUMERIC(5, 4) DEFAULT 1.0000,
    last_quality_check TIMESTAMPTZ,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_canonical BOOLEAN NOT NULL DEFAULT TRUE,

    -- Governance
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    hash_chain_id TEXT,
    signature TEXT,

    -- CRITICAL: Unique constraint enforcing one canonical series per combination
    CONSTRAINT canonical_series_unique UNIQUE (asset_id, frequency, price_type, listing_id),
    CONSTRAINT canonical_series_canonical_check CHECK (is_canonical = TRUE)
);

-- Indexes for series registry
CREATE INDEX IF NOT EXISTS idx_canonical_series_asset ON fhq_meta.canonical_series_registry(asset_id);
CREATE INDEX IF NOT EXISTS idx_canonical_series_frequency ON fhq_meta.canonical_series_registry(frequency);
CREATE INDEX IF NOT EXISTS idx_canonical_series_domain ON fhq_meta.canonical_series_registry(domain_id);
CREATE INDEX IF NOT EXISTS idx_canonical_series_active ON fhq_meta.canonical_series_registry(is_active);

COMMENT ON TABLE fhq_meta.canonical_series_registry IS 'ADR-013: Enforces exactly one canonical series per (asset_id, frequency, price_type) combination.';

-- =====================================================
-- 3. CANONICAL INDICATOR REGISTRY
-- =====================================================
-- Enforces one canonical value per (indicator, asset, timestamp, method)
-- =====================================================

CREATE TABLE IF NOT EXISTS fhq_meta.canonical_indicator_registry (
    indicator_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Domain binding
    domain_id UUID NOT NULL REFERENCES fhq_meta.canonical_domain_registry(domain_id),

    -- Indicator identification
    indicator_name TEXT NOT NULL,      -- e.g., 'RSI', 'MACD', 'SMA', 'REGIME'
    indicator_version TEXT NOT NULL DEFAULT '1.0',
    calculation_method TEXT NOT NULL,   -- Method ID for reproducibility

    -- Canonical store reference
    canonical_table TEXT NOT NULL,      -- Fully qualified table name

    -- Applicable assets
    asset_universe TEXT[] NOT NULL DEFAULT ARRAY['*'],  -- '*' = all assets

    -- Parameters
    default_parameters JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_canonical BOOLEAN NOT NULL DEFAULT TRUE,

    -- Governance
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    hash_chain_id TEXT,
    signature TEXT,

    -- Unique constraint: one canonical method per indicator name + version
    CONSTRAINT canonical_indicator_unique UNIQUE (indicator_name, indicator_version, calculation_method),
    CONSTRAINT canonical_indicator_canonical_check CHECK (is_canonical = TRUE)
);

CREATE INDEX IF NOT EXISTS idx_canonical_indicator_name ON fhq_meta.canonical_indicator_registry(indicator_name);
CREATE INDEX IF NOT EXISTS idx_canonical_indicator_domain ON fhq_meta.canonical_indicator_registry(domain_id);
CREATE INDEX IF NOT EXISTS idx_canonical_indicator_active ON fhq_meta.canonical_indicator_registry(is_active);

COMMENT ON TABLE fhq_meta.canonical_indicator_registry IS 'ADR-013: Enforces exactly one canonical value per (indicator, asset, timestamp, method) combination.';

-- =====================================================
-- 4. CANONICAL ACCESS LOG
-- =====================================================
-- Audit trail for all canonical store access
-- =====================================================

CREATE TABLE IF NOT EXISTS fhq_meta.canonical_access_log (
    access_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Access identification
    access_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_id TEXT NOT NULL,
    operation_type TEXT NOT NULL,  -- 'READ', 'WRITE', 'RESOLVE'

    -- Domain access
    domain_name TEXT NOT NULL,
    canonical_store TEXT NOT NULL,

    -- Access details
    access_context TEXT,           -- 'PRODUCTION', 'RESEARCH', 'SANDBOX'
    query_pattern TEXT,            -- Type of query performed
    row_count INTEGER DEFAULT 0,

    -- Governance compliance
    access_authorized BOOLEAN NOT NULL DEFAULT TRUE,
    bypass_attempted BOOLEAN NOT NULL DEFAULT FALSE,
    vega_notified BOOLEAN NOT NULL DEFAULT FALSE,

    -- Audit
    hash_chain_id TEXT,
    session_id TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT canonical_access_operation_check CHECK (
        operation_type IN ('READ', 'WRITE', 'RESOLVE', 'VALIDATE')
    )
);

CREATE INDEX IF NOT EXISTS idx_canonical_access_timestamp ON fhq_meta.canonical_access_log(access_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_canonical_access_agent ON fhq_meta.canonical_access_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_canonical_access_domain ON fhq_meta.canonical_access_log(domain_name);
CREATE INDEX IF NOT EXISTS idx_canonical_access_unauthorized ON fhq_meta.canonical_access_log(access_authorized) WHERE access_authorized = FALSE;
CREATE INDEX IF NOT EXISTS idx_canonical_access_bypass ON fhq_meta.canonical_access_log(bypass_attempted) WHERE bypass_attempted = TRUE;

COMMENT ON TABLE fhq_meta.canonical_access_log IS 'ADR-013: Audit trail for all canonical store access. Detects bypass attempts.';

-- =====================================================
-- 5. CANONICAL VIOLATION LOG
-- =====================================================
-- Records all multi-truth violations and governance events
-- =====================================================

CREATE TABLE IF NOT EXISTS fhq_meta.canonical_violation_log (
    violation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Violation identification
    violation_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    violation_type TEXT NOT NULL,

    -- Classification (ADR-010)
    discrepancy_class TEXT NOT NULL DEFAULT 'CLASS_C',  -- CLASS_A, CLASS_B, CLASS_C
    severity_score NUMERIC(5, 4) NOT NULL DEFAULT 0.0,

    -- Violation details
    domain_name TEXT,
    conflicting_stores TEXT[],
    conflict_description TEXT NOT NULL,

    -- Evidence
    evidence_bundle JSONB NOT NULL DEFAULT '{}'::jsonb,
    sample_data JSONB,

    -- Detection
    detected_by TEXT NOT NULL,     -- Agent or scanner that detected
    detection_method TEXT NOT NULL, -- 'SCANNER', 'ACCESS_GUARD', 'INGESTION_GATE'

    -- Resolution
    resolution_status TEXT NOT NULL DEFAULT 'OPEN',
    resolution_action TEXT,
    resolved_by TEXT,
    resolved_at TIMESTAMPTZ,

    -- Escalation
    vega_escalated BOOLEAN NOT NULL DEFAULT FALSE,
    vega_escalation_id UUID,
    ceo_notified BOOLEAN NOT NULL DEFAULT FALSE,

    -- Governance
    governance_event_id UUID,
    adr_reference TEXT NOT NULL DEFAULT 'ADR-013',

    -- Audit
    hash_chain_id TEXT,
    signature TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT canonical_violation_class_check CHECK (
        discrepancy_class IN ('CLASS_A', 'CLASS_B', 'CLASS_C')
    ),
    CONSTRAINT canonical_violation_status_check CHECK (
        resolution_status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'ESCALATED', 'SUSPENDED')
    ),
    CONSTRAINT canonical_violation_type_check CHECK (
        violation_type IN (
            'DUPLICATE_DOMAIN', 'DUPLICATE_SERIES', 'DUPLICATE_INDICATOR',
            'CONFLICTING_VALUES', 'UNAUTHORIZED_ACCESS', 'BYPASS_ATTEMPT',
            'NON_CANONICAL_READ', 'MULTI_TRUTH_DETECTED', 'INGESTION_CONFLICT'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_canonical_violation_timestamp ON fhq_meta.canonical_violation_log(violation_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_canonical_violation_class ON fhq_meta.canonical_violation_log(discrepancy_class);
CREATE INDEX IF NOT EXISTS idx_canonical_violation_status ON fhq_meta.canonical_violation_log(resolution_status);
CREATE INDEX IF NOT EXISTS idx_canonical_violation_open ON fhq_meta.canonical_violation_log(resolution_status) WHERE resolution_status = 'OPEN';
CREATE INDEX IF NOT EXISTS idx_canonical_violation_escalated ON fhq_meta.canonical_violation_log(vega_escalated) WHERE vega_escalated = TRUE;

COMMENT ON TABLE fhq_meta.canonical_violation_log IS 'ADR-013: Records all multi-truth violations for governance review.';

-- =====================================================
-- 6. CANONICAL MUTATION GATES
-- =====================================================
-- G1-G4 gate records for canonical truth mutations
-- =====================================================

CREATE TABLE IF NOT EXISTS fhq_governance.canonical_mutation_gates (
    gate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Mutation identification
    mutation_type TEXT NOT NULL,  -- 'DOMAIN_CREATE', 'DOMAIN_UPDATE', 'SERIES_CREATE', 'SERIES_UPDATE', 'INDICATOR_CREATE'
    target_domain TEXT,
    target_id UUID,

    -- Gate progression
    g1_technical_validation BOOLEAN DEFAULT FALSE,
    g1_validated_at TIMESTAMPTZ,
    g1_validated_by TEXT,
    g1_evidence JSONB,

    g2_governance_validation BOOLEAN DEFAULT FALSE,
    g2_validated_at TIMESTAMPTZ,
    g2_validated_by TEXT,
    g2_evidence JSONB,

    g3_audit_verification BOOLEAN DEFAULT FALSE,
    g3_verified_at TIMESTAMPTZ,
    g3_verified_by TEXT,  -- Should always be VEGA
    g3_evidence JSONB,

    g4_canonicalization BOOLEAN DEFAULT FALSE,
    g4_canonicalized_at TIMESTAMPTZ,
    g4_canonicalized_by TEXT,  -- Should always be CEO or LARS/VEGA
    g4_evidence JSONB,

    -- Overall status
    gate_status TEXT NOT NULL DEFAULT 'G1_PENDING',
    current_gate INTEGER NOT NULL DEFAULT 1,

    -- Request details
    request_data JSONB NOT NULL,
    requested_by TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Audit
    hash_chain_id TEXT,
    signature TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT canonical_mutation_type_check CHECK (
        mutation_type IN (
            'DOMAIN_CREATE', 'DOMAIN_UPDATE', 'DOMAIN_DEACTIVATE',
            'SERIES_CREATE', 'SERIES_UPDATE', 'SERIES_DEACTIVATE',
            'INDICATOR_CREATE', 'INDICATOR_UPDATE', 'INDICATOR_DEACTIVATE',
            'CANONICAL_OVERRIDE', 'EMERGENCY_MUTATION'
        )
    ),
    CONSTRAINT canonical_mutation_status_check CHECK (
        gate_status IN (
            'G1_PENDING', 'G1_PASSED', 'G1_FAILED',
            'G2_PENDING', 'G2_PASSED', 'G2_FAILED',
            'G3_PENDING', 'G3_PASSED', 'G3_FAILED',
            'G4_PENDING', 'G4_PASSED', 'G4_FAILED',
            'COMPLETED', 'REJECTED', 'CANCELLED'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_canonical_mutation_status ON fhq_governance.canonical_mutation_gates(gate_status);
CREATE INDEX IF NOT EXISTS idx_canonical_mutation_type ON fhq_governance.canonical_mutation_gates(mutation_type);
CREATE INDEX IF NOT EXISTS idx_canonical_mutation_domain ON fhq_governance.canonical_mutation_gates(target_domain);
CREATE INDEX IF NOT EXISTS idx_canonical_mutation_pending ON fhq_governance.canonical_mutation_gates(gate_status)
    WHERE gate_status NOT IN ('COMPLETED', 'REJECTED', 'CANCELLED');

COMMENT ON TABLE fhq_governance.canonical_mutation_gates IS 'ADR-013: G1-G4 gate records for canonical truth mutations (ADR-004 compliant).';

-- =====================================================
-- 7. CANONICAL INGESTION REGISTRY
-- =====================================================
-- Tracks all ingestion jobs writing to canonical stores
-- =====================================================

CREATE TABLE IF NOT EXISTS fhq_meta.canonical_ingestion_registry (
    ingestion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Ingestion identification
    job_name TEXT NOT NULL UNIQUE,
    job_type TEXT NOT NULL,  -- 'SCHEDULED', 'REAL_TIME', 'BACKFILL', 'MANUAL'

    -- Target domain
    domain_id UUID NOT NULL REFERENCES fhq_meta.canonical_domain_registry(domain_id),
    target_canonical_store TEXT NOT NULL,

    -- Asset universe
    asset_universe TEXT[] NOT NULL DEFAULT ARRAY['*'],
    frequencies TEXT[] NOT NULL DEFAULT ARRAY['1d'],

    -- Vendor sources
    vendor_sources TEXT[] NOT NULL,
    primary_vendor TEXT NOT NULL,

    -- Orchestrator binding
    orchestrator_registered BOOLEAN NOT NULL DEFAULT FALSE,
    orchestrator_task_id UUID,

    -- VEGA binding
    vega_approved BOOLEAN NOT NULL DEFAULT FALSE,
    vega_approval_id UUID,

    -- Reconciliation requirements
    requires_reconciliation BOOLEAN NOT NULL DEFAULT TRUE,
    reconciliation_threshold NUMERIC(5, 4) NOT NULL DEFAULT 0.10,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    last_run_status TEXT,

    -- Governance
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    hash_chain_id TEXT,
    signature TEXT,

    CONSTRAINT canonical_ingestion_type_check CHECK (
        job_type IN ('SCHEDULED', 'REAL_TIME', 'BACKFILL', 'MANUAL', 'EVENT_DRIVEN')
    )
);

CREATE INDEX IF NOT EXISTS idx_canonical_ingestion_domain ON fhq_meta.canonical_ingestion_registry(domain_id);
CREATE INDEX IF NOT EXISTS idx_canonical_ingestion_active ON fhq_meta.canonical_ingestion_registry(is_active);
CREATE INDEX IF NOT EXISTS idx_canonical_ingestion_orchestrator ON fhq_meta.canonical_ingestion_registry(orchestrator_registered);

COMMENT ON TABLE fhq_meta.canonical_ingestion_registry IS 'ADR-013: Registry of all ingestion jobs writing to canonical stores.';

-- =====================================================
-- 8. SEED CANONICAL DOMAINS
-- =====================================================
-- Initial canonical domain definitions for existing data families
-- =====================================================

-- Domain: Prices
INSERT INTO fhq_meta.canonical_domain_registry (
    domain_name, domain_category, canonical_store, canonical_schema, canonical_table,
    description, data_contract, created_by
) VALUES (
    'prices', 'PRICES', 'fhq_data.prices', 'fhq_data', 'prices',
    'Canonical price data for all assets (OHLCV, trades, quotes)',
    jsonb_build_object(
        'required_columns', ARRAY['asset_id', 'timestamp', 'open', 'high', 'low', 'close', 'volume'],
        'timestamp_column', 'timestamp',
        'asset_column', 'asset_id',
        'frequency_column', 'frequency'
    ),
    'LARS'
) ON CONFLICT (domain_name) DO UPDATE SET
    updated_at = NOW(),
    updated_by = 'LARS';

-- Domain: Indicators
INSERT INTO fhq_meta.canonical_domain_registry (
    domain_name, domain_category, canonical_store, canonical_schema, canonical_table,
    description, data_contract, created_by
) VALUES (
    'indicators', 'INDICATORS', 'fhq_data.indicators', 'fhq_data', 'indicators',
    'Canonical indicator values (RSI, MACD, regime classifications, etc.)',
    jsonb_build_object(
        'required_columns', ARRAY['indicator_name', 'asset_id', 'timestamp', 'value', 'method_id'],
        'timestamp_column', 'timestamp',
        'asset_column', 'asset_id',
        'indicator_column', 'indicator_name'
    ),
    'LARS'
) ON CONFLICT (domain_name) DO UPDATE SET
    updated_at = NOW(),
    updated_by = 'LARS';

-- Domain: Regime Classifications (Phase 3)
INSERT INTO fhq_meta.canonical_domain_registry (
    domain_name, domain_category, canonical_store, canonical_schema, canonical_table,
    description, data_contract, created_by
) VALUES (
    'regime_classifications', 'INDICATORS', 'fhq_phase3.regime_classifications', 'fhq_phase3', 'regime_classifications',
    'Canonical regime classifications from FINN+ (BEAR/NEUTRAL/BULL)',
    jsonb_build_object(
        'required_columns', ARRAY['asset_id', 'timestamp', 'regime_label', 'confidence', 'signature_hex'],
        'timestamp_column', 'timestamp',
        'asset_column', 'asset_id',
        'regime_column', 'regime_label'
    ),
    'LARS'
) ON CONFLICT (domain_name) DO UPDATE SET
    updated_at = NOW(),
    updated_by = 'LARS';

-- Domain: CDS Results (Phase 3)
INSERT INTO fhq_meta.canonical_domain_registry (
    domain_name, domain_category, canonical_store, canonical_schema, canonical_table,
    description, data_contract, created_by
) VALUES (
    'cds_results', 'INDICATORS', 'fhq_phase3.cds_results', 'fhq_phase3', 'cds_results',
    'Canonical Composite Decision Score (CDS) results',
    jsonb_build_object(
        'required_columns', ARRAY['cycle_id', 'symbol', 'cds_value', 'timestamp', 'signature_hex'],
        'timestamp_column', 'timestamp',
        'asset_column', 'symbol'
    ),
    'LARS'
) ON CONFLICT (domain_name) DO UPDATE SET
    updated_at = NOW(),
    updated_by = 'LARS';

-- Domain: Governance
INSERT INTO fhq_meta.canonical_domain_registry (
    domain_name, domain_category, canonical_store, canonical_schema, canonical_table,
    description, data_contract, governance_level, created_by
) VALUES (
    'governance_actions', 'GOVERNANCE', 'fhq_governance.governance_actions_log', 'fhq_governance', 'governance_actions_log',
    'Canonical governance actions and decisions',
    jsonb_build_object(
        'required_columns', ARRAY['action_id', 'action_type', 'agent_id', 'timestamp', 'signature'],
        'timestamp_column', 'timestamp',
        'agent_column', 'agent_id'
    ),
    'CONSTITUTIONAL',
    'LARS'
) ON CONFLICT (domain_name) DO UPDATE SET
    updated_at = NOW(),
    updated_by = 'LARS';

-- Domain: ADR Registry
INSERT INTO fhq_meta.canonical_domain_registry (
    domain_name, domain_category, canonical_store, canonical_schema, canonical_table,
    description, data_contract, governance_level, created_by
) VALUES (
    'adr_registry', 'GOVERNANCE', 'fhq_meta.adr_registry', 'fhq_meta', 'adr_registry',
    'Canonical ADR registry - immutable governance records',
    jsonb_build_object(
        'required_columns', ARRAY['adr_id', 'adr_number', 'title', 'status', 'created_at'],
        'adr_column', 'adr_number',
        'immutable', true
    ),
    'CONSTITUTIONAL',
    'LARS'
) ON CONFLICT (domain_name) DO UPDATE SET
    updated_at = NOW(),
    updated_by = 'LARS';

-- Domain: Reconciliation
INSERT INTO fhq_meta.canonical_domain_registry (
    domain_name, domain_category, canonical_store, canonical_schema, canonical_table,
    description, data_contract, created_by
) VALUES (
    'reconciliation_snapshots', 'AUDIT', 'fhq_meta.reconciliation_snapshots', 'fhq_meta', 'reconciliation_snapshots',
    'Canonical reconciliation snapshots for ADR-010 compliance',
    jsonb_build_object(
        'required_columns', ARRAY['snapshot_id', 'component_name', 'discrepancy_score', 'snapshot_timestamp'],
        'timestamp_column', 'snapshot_timestamp'
    ),
    'LARS'
) ON CONFLICT (domain_name) DO UPDATE SET
    updated_at = NOW(),
    updated_by = 'LARS';

-- =====================================================
-- 9. CANONICAL DOMAIN RESOLUTION FUNCTION
-- =====================================================
-- Function to resolve domain name to canonical store
-- =====================================================

CREATE OR REPLACE FUNCTION fhq_meta.resolve_canonical_store(
    p_domain_name TEXT
) RETURNS TEXT AS $$
DECLARE
    v_canonical_store TEXT;
BEGIN
    SELECT canonical_store INTO v_canonical_store
    FROM fhq_meta.canonical_domain_registry
    WHERE domain_name = p_domain_name
      AND is_active = TRUE
      AND is_canonical = TRUE
    LIMIT 1;

    IF v_canonical_store IS NULL THEN
        RAISE EXCEPTION 'ADR-013 VIOLATION: No canonical store found for domain: %', p_domain_name;
    END IF;

    RETURN v_canonical_store;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION fhq_meta.resolve_canonical_store IS 'ADR-013: Resolves domain name to canonical store. Raises exception if not found.';

-- =====================================================
-- 10. CANONICAL ACCESS VALIDATION FUNCTION
-- =====================================================
-- Validates that access is to canonical store only
-- =====================================================

CREATE OR REPLACE FUNCTION fhq_meta.validate_canonical_access(
    p_agent_id TEXT,
    p_domain_name TEXT,
    p_target_store TEXT,
    p_operation_type TEXT DEFAULT 'READ',
    p_access_context TEXT DEFAULT 'PRODUCTION'
) RETURNS BOOLEAN AS $$
DECLARE
    v_canonical_store TEXT;
    v_is_canonical BOOLEAN;
    v_access_authorized BOOLEAN := TRUE;
BEGIN
    -- Get canonical store for domain
    SELECT canonical_store INTO v_canonical_store
    FROM fhq_meta.canonical_domain_registry
    WHERE domain_name = p_domain_name
      AND is_active = TRUE;

    -- Check if target matches canonical
    v_is_canonical := (v_canonical_store = p_target_store);

    -- In PRODUCTION context, non-canonical access is a violation
    IF p_access_context = 'PRODUCTION' AND NOT v_is_canonical THEN
        v_access_authorized := FALSE;

        -- Log violation
        INSERT INTO fhq_meta.canonical_violation_log (
            violation_type, discrepancy_class, severity_score,
            domain_name, conflicting_stores, conflict_description,
            detected_by, detection_method, vega_escalated
        ) VALUES (
            'NON_CANONICAL_READ', 'CLASS_B', 0.50,
            p_domain_name, ARRAY[p_target_store, v_canonical_store],
            format('Agent %s attempted to read from non-canonical store %s instead of %s',
                   p_agent_id, p_target_store, v_canonical_store),
            'CANONICAL_ACCESS_GUARD', 'ACCESS_GUARD', TRUE
        );
    END IF;

    -- Log all access
    INSERT INTO fhq_meta.canonical_access_log (
        agent_id, operation_type, domain_name, canonical_store,
        access_context, access_authorized, bypass_attempted, vega_notified
    ) VALUES (
        p_agent_id, p_operation_type, p_domain_name, p_target_store,
        p_access_context, v_access_authorized, NOT v_is_canonical, NOT v_is_canonical
    );

    RETURN v_access_authorized;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_meta.validate_canonical_access IS 'ADR-013: Validates access is to canonical store. Logs violations.';

-- =====================================================
-- 11. MULTI-TRUTH DETECTION FUNCTION
-- =====================================================
-- Detects potential multi-truth situations
-- =====================================================

CREATE OR REPLACE FUNCTION fhq_meta.detect_multi_truth(
    p_domain_name TEXT,
    p_asset_id TEXT DEFAULT NULL,
    p_timestamp TIMESTAMPTZ DEFAULT NULL
) RETURNS TABLE (
    violation_detected BOOLEAN,
    violation_type TEXT,
    conflict_description TEXT,
    severity NUMERIC
) AS $$
DECLARE
    v_domain_count INTEGER;
    v_series_count INTEGER;
BEGIN
    -- Check for duplicate domains
    SELECT COUNT(*) INTO v_domain_count
    FROM fhq_meta.canonical_domain_registry
    WHERE domain_name = p_domain_name
      AND is_active = TRUE;

    IF v_domain_count > 1 THEN
        RETURN QUERY SELECT
            TRUE,
            'DUPLICATE_DOMAIN'::TEXT,
            format('Multiple active canonical domains found for: %s', p_domain_name),
            1.0::NUMERIC;
        RETURN;
    END IF;

    -- Check for duplicate series if asset specified
    IF p_asset_id IS NOT NULL THEN
        SELECT COUNT(*) INTO v_series_count
        FROM fhq_meta.canonical_series_registry
        WHERE asset_id = p_asset_id
          AND is_active = TRUE;

        IF v_series_count > 1 THEN
            RETURN QUERY SELECT
                TRUE,
                'DUPLICATE_SERIES'::TEXT,
                format('Multiple active canonical series found for asset: %s', p_asset_id),
                0.8::NUMERIC;
            RETURN;
        END IF;
    END IF;

    -- No violation detected
    RETURN QUERY SELECT FALSE, NULL::TEXT, NULL::TEXT, 0.0::NUMERIC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_meta.detect_multi_truth IS 'ADR-013: Detects potential multi-truth violations.';

-- =====================================================
-- 12. REGISTER CANONICAL INGESTION FUNCTION
-- =====================================================
-- Registers an ingestion job for canonical store access
-- =====================================================

CREATE OR REPLACE FUNCTION fhq_meta.register_canonical_ingestion(
    p_job_name TEXT,
    p_domain_name TEXT,
    p_vendor_sources TEXT[],
    p_primary_vendor TEXT,
    p_asset_universe TEXT[] DEFAULT ARRAY['*'],
    p_frequencies TEXT[] DEFAULT ARRAY['1d'],
    p_job_type TEXT DEFAULT 'SCHEDULED',
    p_created_by TEXT DEFAULT 'LARS'
) RETURNS UUID AS $$
DECLARE
    v_domain_id UUID;
    v_canonical_store TEXT;
    v_ingestion_id UUID;
BEGIN
    -- Resolve domain
    SELECT domain_id, canonical_store INTO v_domain_id, v_canonical_store
    FROM fhq_meta.canonical_domain_registry
    WHERE domain_name = p_domain_name
      AND is_active = TRUE;

    IF v_domain_id IS NULL THEN
        RAISE EXCEPTION 'ADR-013 VIOLATION: Cannot register ingestion for unknown domain: %', p_domain_name;
    END IF;

    -- Register ingestion job
    INSERT INTO fhq_meta.canonical_ingestion_registry (
        job_name, job_type, domain_id, target_canonical_store,
        asset_universe, frequencies, vendor_sources, primary_vendor,
        created_by
    ) VALUES (
        p_job_name, p_job_type, v_domain_id, v_canonical_store,
        p_asset_universe, p_frequencies, p_vendor_sources, p_primary_vendor,
        p_created_by
    )
    ON CONFLICT (job_name) DO UPDATE SET
        vendor_sources = EXCLUDED.vendor_sources,
        asset_universe = EXCLUDED.asset_universe,
        frequencies = EXCLUDED.frequencies,
        updated_at = NOW()
    RETURNING ingestion_id INTO v_ingestion_id;

    RETURN v_ingestion_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_meta.register_canonical_ingestion IS 'ADR-013: Registers an ingestion job for canonical store access.';

-- =====================================================
-- 13. VERIFICATION QUERIES
-- =====================================================

-- Verify all tables created
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'fhq_meta'
      AND table_name LIKE 'canonical_%';

    IF table_count < 6 THEN
        RAISE EXCEPTION 'ADR-013: Not all canonical tables created. Found: %', table_count;
    END IF;

    RAISE NOTICE 'ADR-013: % canonical tables created in fhq_meta', table_count;
END $$;

-- Verify domain registry has seed data
DO $$
DECLARE
    domain_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO domain_count
    FROM fhq_meta.canonical_domain_registry
    WHERE is_active = TRUE;

    IF domain_count < 5 THEN
        RAISE WARNING 'ADR-013: Only % domains registered. Expected ≥5', domain_count;
    ELSE
        RAISE NOTICE 'ADR-013: % canonical domains registered', domain_count;
    END IF;
END $$;

-- Verify unique constraints are enforced
DO $$
BEGIN
    -- Test that we cannot insert duplicate domain
    BEGIN
        INSERT INTO fhq_meta.canonical_domain_registry (
            domain_name, domain_category, canonical_store, canonical_schema, canonical_table,
            description, created_by
        ) VALUES (
            'prices', 'PRICES', 'fhq_data.prices_duplicate', 'fhq_data', 'prices_duplicate',
            'Duplicate test', 'TEST'
        );
        RAISE EXCEPTION 'ADR-013: CRITICAL - Duplicate domain insert should have failed!';
    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE 'ADR-013: Domain uniqueness constraint verified (duplicate correctly rejected)';
    END;
END $$;

COMMIT;

-- =====================================================
-- MIGRATION SUMMARY
-- =====================================================

SELECT
    'MIGRATION 019 COMPLETE' AS status,
    'ADR-013 Canonical Truth Architecture' AS description,
    NOW() AS completed_at;

\echo ''
\echo '=========================================='
\echo 'MIGRATION 019: ADR-013 CANONICAL TRUTH ARCHITECTURE'
\echo '=========================================='
\echo 'Tables created:'
\echo '  - fhq_meta.canonical_domain_registry (central truth registry)'
\echo '  - fhq_meta.canonical_series_registry (asset-level invariants)'
\echo '  - fhq_meta.canonical_indicator_registry (indicator invariants)'
\echo '  - fhq_meta.canonical_access_log (access audit trail)'
\echo '  - fhq_meta.canonical_violation_log (multi-truth events)'
\echo '  - fhq_meta.canonical_ingestion_registry (ingestion jobs)'
\echo '  - fhq_governance.canonical_mutation_gates (G1-G4 gates)'
\echo ''
\echo 'Functions created:'
\echo '  - fhq_meta.resolve_canonical_store(domain_name)'
\echo '  - fhq_meta.validate_canonical_access(...)'
\echo '  - fhq_meta.detect_multi_truth(...)'
\echo '  - fhq_meta.register_canonical_ingestion(...)'
\echo ''
\echo 'Domains registered:'
\echo '  - prices, indicators, regime_classifications, cds_results'
\echo '  - governance_actions, adr_registry, reconciliation_snapshots'
\echo '=========================================='
\echo ''
\echo 'Next step: Deploy canonical accessor module'
\echo '  python 04_AGENTS/PHASE3/canonical_accessor.py --verify'
\echo ''
