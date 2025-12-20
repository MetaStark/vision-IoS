-- ============================================================================
-- MIGRATION 101: G2 CAUSAL ENTROPY SCHEMA
-- ============================================================================
-- Operation: CAUSAL_ENTROPY G2 Integration
-- Gate: G2 (Integration)
-- Author: STIG (CTO)
-- Date: 2025-12-09
-- Reviewed By: VEGA (pending)
--
-- Purpose: Prepare IoS-006 (macro) and IoS-007 (graph) schemas for
--          macro-driven causal nodes and edges.
--
-- Constraints:
--   - No writes to fhq_execution or active runtime tables
--   - Warmup firewall remains active
--   - No runtime propagation to IoS-003/004/005/008
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: IoS-006 MACRO SCHEMA EXTENSIONS
-- ============================================================================

-- 1.1 Macro Nodes Table
-- Stores canonical macro factor nodes for Alpha Graph MK2
CREATE TABLE IF NOT EXISTS fhq_macro.macro_nodes (
    node_id TEXT PRIMARY KEY,
    canonical_id TEXT NOT NULL UNIQUE,
    node_type TEXT NOT NULL DEFAULT 'MACRO_FACTOR',
    subtype TEXT NOT NULL,  -- VOLATILITY, LIQUIDITY, CREDIT, RATES, INFLATION, ACTIVITY, FX
    description TEXT,

    -- Data Source
    source_tier TEXT NOT NULL CHECK (source_tier IN ('LAKE', 'PULSE', 'SNIPER', 'DERIVED')),
    source_provider TEXT,
    fred_series_id TEXT,
    frequency TEXT NOT NULL CHECK (frequency IN ('DAILY', 'WEEKLY', 'MONTHLY')),

    -- Statistical Signature (computed)
    rolling_mean FLOAT,
    rolling_std FLOAT,
    current_percentile FLOAT,
    current_zscore FLOAT,
    regime_state TEXT CHECK (regime_state IN ('LOW', 'NORMAL', 'ELEVATED', 'EXTREME')),

    -- Causal Properties
    relevance_horizon_days INTEGER NOT NULL DEFAULT 7,
    volatility_sensitivity FLOAT,  -- Beta to VIX
    missing_data_tolerance_days INTEGER DEFAULT 3,

    -- Thresholds
    stress_threshold FLOAT,
    extreme_threshold FLOAT,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG',
    g2_integrated BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT macro_nodes_subtype_check CHECK (
        subtype IN ('VOLATILITY', 'LIQUIDITY', 'CREDIT', 'RATES', 'INFLATION', 'ACTIVITY', 'FX')
    )
);

-- 1.2 Macro Edges Table
-- Stores causal relationships between macro nodes and equity/indicator nodes
CREATE TABLE IF NOT EXISTS fhq_macro.macro_edges (
    edge_id SERIAL PRIMARY KEY,
    source_node_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,

    -- Edge Parameters
    lag_days INTEGER,
    correlation_value FLOAT,
    threshold_value FLOAT,
    amplification_factor FLOAT,
    inhibition_score FLOAT,
    damping_factor FLOAT,
    transmission_probability FLOAT,

    -- Validation
    minimum_observations INTEGER NOT NULL DEFAULT 60,
    significance_level FLOAT NOT NULL DEFAULT 0.05,
    p_value FLOAT,
    is_significant BOOLEAN,
    stability_verified BOOLEAN DEFAULT FALSE,

    -- Computation Metadata
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    computation_window_start DATE,
    computation_window_end DATE,
    recomputation_due DATE,

    -- Governance
    created_by TEXT NOT NULL DEFAULT 'CRIO',
    verified_by TEXT,
    g2_integrated BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT macro_edges_type_check CHECK (
        edge_type IN ('LEADS', 'AMPLIFIES', 'INHIBITS', 'CORRELATES', 'TRANSMITS', 'DAMPENS')
    ),
    CONSTRAINT macro_edges_unique UNIQUE (source_node_id, target_node_id, edge_type)
);

-- 1.3 Shock Signatures Table
-- Stores shock detection parameters and events
CREATE TABLE IF NOT EXISTS fhq_macro.shock_signatures (
    shock_id TEXT PRIMARY KEY,
    shock_type TEXT NOT NULL,
    description TEXT,

    -- Detection Parameters
    primary_indicator TEXT NOT NULL,
    secondary_indicators TEXT[],
    lookback_window_days INTEGER NOT NULL,
    baseline_period_days INTEGER NOT NULL DEFAULT 252,

    -- Thresholds by Severity
    minor_threshold_low FLOAT,
    minor_threshold_high FLOAT,
    moderate_threshold_low FLOAT,
    moderate_threshold_high FLOAT,
    severe_threshold_low FLOAT,
    severe_threshold_high FLOAT,
    extreme_threshold FLOAT,

    -- Confidence Scoring
    base_confidence_minor FLOAT DEFAULT 0.6,
    base_confidence_moderate FLOAT DEFAULT 0.75,
    base_confidence_severe FLOAT DEFAULT 0.85,
    base_confidence_extreme FLOAT DEFAULT 0.95,

    -- Override Logic
    override_condition TEXT,
    override_action TEXT,
    override_rationale TEXT,

    -- Priority
    priority_rank INTEGER NOT NULL,  -- 1=highest (VOLATILITY), 4=lowest (LIQUIDITY)

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'CRIO',
    g2_integrated BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT shock_type_check CHECK (
        shock_type IN ('SHOCK_LIQUIDITY', 'SHOCK_RATES', 'SHOCK_VOLATILITY', 'SHOCK_CREDIT')
    )
);

-- 1.4 Shock Events Table (for detected shocks)
CREATE TABLE IF NOT EXISTS fhq_macro.shock_events (
    event_id SERIAL PRIMARY KEY,
    shock_id TEXT NOT NULL REFERENCES fhq_macro.shock_signatures(shock_id),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    observation_date DATE NOT NULL,

    -- Detection Details
    severity TEXT NOT NULL CHECK (severity IN ('MINOR', 'MODERATE', 'SEVERE', 'EXTREME')),
    confidence_score FLOAT NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),

    -- Feature Vector (JSONB for flexibility)
    feature_vector JSONB NOT NULL,

    -- Secondary Confirmations
    secondary_confirmations JSONB,

    -- Override
    override_applied BOOLEAN DEFAULT FALSE,
    override_reason TEXT,
    original_severity TEXT,

    -- Propagation (G3+ only - not active in G2)
    propagated_at TIMESTAMPTZ,
    propagation_blocked BOOLEAN DEFAULT TRUE,  -- Warmup firewall

    -- Metadata
    created_by TEXT NOT NULL DEFAULT 'SYSTEM',

    CONSTRAINT shock_events_unique_day UNIQUE (shock_id, observation_date)
);

-- 1.5 Causal Parameters Table
-- Stores edge computation parameters for reproducibility
CREATE TABLE IF NOT EXISTS fhq_macro.causal_parameters (
    param_id SERIAL PRIMARY KEY,
    edge_type TEXT NOT NULL,
    parameter_name TEXT NOT NULL,
    parameter_value JSONB NOT NULL,

    -- Versioning
    version INTEGER NOT NULL DEFAULT 1,
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_until DATE,

    -- Governance
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'CRIO',
    approved_by TEXT,

    CONSTRAINT causal_params_unique UNIQUE (edge_type, parameter_name, version)
);

-- ============================================================================
-- SECTION 2: IoS-007 GRAPH SCHEMA EXTENSIONS
-- ============================================================================

-- 2.1 Extend alpha_graph_nodes with macro attributes
DO $$
BEGIN
    -- Add statistical_signature column if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'vision_signals'
        AND table_name = 'alpha_graph_nodes'
        AND column_name = 'statistical_signature'
    ) THEN
        ALTER TABLE vision_signals.alpha_graph_nodes
        ADD COLUMN statistical_signature JSONB;
    END IF;

    -- Add relevance_horizon column if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'vision_signals'
        AND table_name = 'alpha_graph_nodes'
        AND column_name = 'relevance_horizon'
    ) THEN
        ALTER TABLE vision_signals.alpha_graph_nodes
        ADD COLUMN relevance_horizon INTEGER;
    END IF;

    -- Add regime_state column if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'vision_signals'
        AND table_name = 'alpha_graph_nodes'
        AND column_name = 'regime_state'
    ) THEN
        ALTER TABLE vision_signals.alpha_graph_nodes
        ADD COLUMN regime_state TEXT;
    END IF;

    -- Add is_macro_node flag
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'vision_signals'
        AND table_name = 'alpha_graph_nodes'
        AND column_name = 'is_macro_node'
    ) THEN
        ALTER TABLE vision_signals.alpha_graph_nodes
        ADD COLUMN is_macro_node BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- 2.2 Extend alpha_graph_edges with causal attributes
DO $$
BEGIN
    -- Add lag_days column if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'vision_signals'
        AND table_name = 'alpha_graph_edges'
        AND column_name = 'lag_days'
    ) THEN
        ALTER TABLE vision_signals.alpha_graph_edges
        ADD COLUMN lag_days INTEGER;
    END IF;

    -- Add threshold_value column if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'vision_signals'
        AND table_name = 'alpha_graph_edges'
        AND column_name = 'threshold_value'
    ) THEN
        ALTER TABLE vision_signals.alpha_graph_edges
        ADD COLUMN threshold_value FLOAT;
    END IF;

    -- Add amplification_factor column if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'vision_signals'
        AND table_name = 'alpha_graph_edges'
        AND column_name = 'amplification_factor'
    ) THEN
        ALTER TABLE vision_signals.alpha_graph_edges
        ADD COLUMN amplification_factor FLOAT;
    END IF;

    -- Add inhibition_score column if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'vision_signals'
        AND table_name = 'alpha_graph_edges'
        AND column_name = 'inhibition_score'
    ) THEN
        ALTER TABLE vision_signals.alpha_graph_edges
        ADD COLUMN inhibition_score FLOAT;
    END IF;

    -- Add is_causal_edge flag
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'vision_signals'
        AND table_name = 'alpha_graph_edges'
        AND column_name = 'is_causal_edge'
    ) THEN
        ALTER TABLE vision_signals.alpha_graph_edges
        ADD COLUMN is_causal_edge BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- ============================================================================
-- SECTION 3: GOVERNANCE AUDIT TABLES
-- ============================================================================

-- 3.1 Causal Entropy Audit Log
CREATE TABLE IF NOT EXISTS fhq_governance.causal_entropy_audit (
    audit_id SERIAL PRIMARY KEY,
    operation TEXT NOT NULL,
    gate TEXT NOT NULL CHECK (gate IN ('G0', 'G1', 'G2', 'G3', 'G4')),
    task_group TEXT,  -- A, B, C, D, E

    -- Operation Details
    entity_type TEXT NOT NULL,  -- NODE, EDGE, SHOCK, PARAMETER
    entity_id TEXT,
    operation_type TEXT NOT NULL,  -- CREATE, UPDATE, DELETE, COMPUTE

    -- Before/After State
    old_value JSONB,
    new_value JSONB,

    -- Execution Context
    executed_by TEXT NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Governance
    warmup_active BOOLEAN NOT NULL DEFAULT TRUE,
    propagation_blocked BOOLEAN NOT NULL DEFAULT TRUE,

    -- Verification
    hash_before TEXT,
    hash_after TEXT
);

-- 3.2 Causal Edge Computation Log
CREATE TABLE IF NOT EXISTS fhq_governance.causal_edge_log (
    log_id SERIAL PRIMARY KEY,
    edge_type TEXT NOT NULL,
    source_node TEXT NOT NULL,
    target_node TEXT NOT NULL,

    -- Computation Parameters
    parameters JSONB NOT NULL,

    -- Results
    computed_value FLOAT,
    p_value FLOAT,
    is_significant BOOLEAN,

    -- Data Window
    window_start DATE NOT NULL,
    window_end DATE NOT NULL,
    observations_used INTEGER NOT NULL,

    -- Reproducibility
    computation_hash TEXT NOT NULL,  -- SHA256 of inputs
    deterministic_verified BOOLEAN DEFAULT TRUE,

    -- Metadata
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    computed_by TEXT NOT NULL DEFAULT 'CRIO'
);

-- ============================================================================
-- SECTION 4: INDEXES FOR PERFORMANCE
-- ============================================================================

-- Macro nodes indexes
CREATE INDEX IF NOT EXISTS idx_macro_nodes_subtype ON fhq_macro.macro_nodes(subtype);
CREATE INDEX IF NOT EXISTS idx_macro_nodes_source ON fhq_macro.macro_nodes(source_tier);
CREATE INDEX IF NOT EXISTS idx_macro_nodes_regime ON fhq_macro.macro_nodes(regime_state);

-- Macro edges indexes
CREATE INDEX IF NOT EXISTS idx_macro_edges_source ON fhq_macro.macro_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_macro_edges_target ON fhq_macro.macro_edges(target_node_id);
CREATE INDEX IF NOT EXISTS idx_macro_edges_type ON fhq_macro.macro_edges(edge_type);

-- Shock signatures indexes
CREATE INDEX IF NOT EXISTS idx_shock_signatures_type ON fhq_macro.shock_signatures(shock_type);
CREATE INDEX IF NOT EXISTS idx_shock_events_date ON fhq_macro.shock_events(observation_date);
CREATE INDEX IF NOT EXISTS idx_shock_events_severity ON fhq_macro.shock_events(severity);

-- Audit indexes
CREATE INDEX IF NOT EXISTS idx_causal_entropy_audit_gate ON fhq_governance.causal_entropy_audit(gate);
CREATE INDEX IF NOT EXISTS idx_causal_entropy_audit_entity ON fhq_governance.causal_entropy_audit(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_causal_edge_log_type ON fhq_governance.causal_edge_log(edge_type);

-- ============================================================================
-- SECTION 5: WARMUP FIREWALL CONSTRAINTS
-- ============================================================================

-- Prevent shock propagation during warmup
CREATE OR REPLACE FUNCTION fhq_macro.enforce_warmup_firewall()
RETURNS TRIGGER AS $$
BEGIN
    -- Check if warmup is active (until 2025-12-11 12:00 UTC)
    IF NOW() < '2025-12-11 12:00:00+00'::TIMESTAMPTZ THEN
        -- Block propagation
        NEW.propagation_blocked := TRUE;
        NEW.propagated_at := NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_warmup_firewall ON fhq_macro.shock_events;
CREATE TRIGGER trg_warmup_firewall
    BEFORE INSERT OR UPDATE ON fhq_macro.shock_events
    FOR EACH ROW
    EXECUTE FUNCTION fhq_macro.enforce_warmup_firewall();

-- ============================================================================
-- SECTION 6: REGISTER MIGRATION
-- ============================================================================

INSERT INTO fhq_meta.adr_audit_log (
    audit_id,
    change_proposal_id,
    event_type,
    gate_stage,
    adr_id,
    initiated_by,
    decision,
    resolution_notes,
    evidence_path,
    sha256_hash,
    metadata
) VALUES (
    gen_random_uuid(),
    'CP-101-G2-CAUSAL-ENTROPY',
    'G2_GOVERNANCE_VALIDATION',
    'G2',
    'ADR-007',
    'STIG',
    'EXECUTED',
    'G2 Causal Entropy schema migration: macro_nodes, macro_edges, shock_signatures, causal_parameters tables created. IoS-006/007 extended for Alpha Graph MK2.',
    '05_GOVERNANCE/PHASE3/G2_CAUSAL_ENTROPY_SCHEMA_MIGRATION.sql',
    encode(sha256('101_g2_causal_entropy_schema_STIG_G2_20251209'::bytea), 'hex'),
    jsonb_build_object(
        'gate', 'G2',
        'operation', 'CAUSAL_ENTROPY',
        'tables_created', ARRAY[
            'fhq_macro.macro_nodes',
            'fhq_macro.macro_edges',
            'fhq_macro.shock_signatures',
            'fhq_macro.shock_events',
            'fhq_macro.causal_parameters'
        ],
        'tables_extended', ARRAY[
            'vision_signals.alpha_graph_nodes',
            'vision_signals.alpha_graph_edges'
        ],
        'audit_tables', ARRAY[
            'fhq_governance.causal_entropy_audit',
            'fhq_governance.causal_edge_log'
        ],
        'warmup_firewall', TRUE,
        'runtime_propagation', FALSE,
        'signature', 'STIG.g2_causal_entropy_schema_migration'
    )
);

COMMIT;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- Tables Created:
--   - fhq_macro.macro_nodes (15 macro factor nodes)
--   - fhq_macro.macro_edges (causal relationships)
--   - fhq_macro.shock_signatures (4 shock classes)
--   - fhq_macro.shock_events (detected shocks)
--   - fhq_macro.causal_parameters (edge computation params)
--
-- Tables Extended:
--   - vision_signals.alpha_graph_nodes (+4 columns)
--   - vision_signals.alpha_graph_edges (+5 columns)
--
-- Audit Tables:
--   - fhq_governance.causal_entropy_audit
--   - fhq_governance.causal_edge_log
--
-- Firewall: Warmup constraint active until 2025-12-11 12:00 UTC
-- ============================================================================
