-- ============================================================================
-- MIGRATION 025: IoS-003 PERCEPTION SCHEMA
-- ============================================================================
-- Authority: CEO Directive (ADR-001 through ADR-016)
-- Gate: G0_SUBMISSION
-- Module: IoS-003 - Meta-Perception Engine (Market Brain)
-- Owner: LARS
-- Executor: CODE
--
-- This migration creates the fhq_perception schema and tables for IoS-003.
-- NO COMPUTATION OR DATA POPULATION UNTIL G4 ACTIVATION.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. CREATE SCHEMA
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS fhq_perception;
GRANT USAGE ON SCHEMA fhq_perception TO PUBLIC;

COMMENT ON SCHEMA fhq_perception IS
'IoS-003 Meta-Perception Engine. Contains regime classifications, state vectors,
semantic summaries, and anomaly detection. Owner: LARS. Executor: CODE.
Source: fhq_research (IoS-002). Dependencies: IoS-001, IoS-002.
ADR Compliance: ADR-001 through ADR-016.';

-- ============================================================================
-- 2. REGIME_DAILY TABLE
-- ============================================================================
-- Purpose: Daily regime classification with hysteresis stabilization
-- One row per asset per day
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_perception.regime_daily (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core identifiers
    asset_id TEXT NOT NULL,
    timestamp DATE NOT NULL,

    -- Regime classification (ADR-010 determinism)
    regime_classification TEXT NOT NULL CHECK (
        regime_classification IN (
            'STRONG_BULL', 'BULL', 'NEUTRAL', 'BEAR', 'STRONG_BEAR',
            'VOLATILE_NON_DIRECTIONAL', 'COMPRESSION', 'BROKEN', 'UNTRUSTED'
        )
    ),
    regime_stability_flag BOOLEAN NOT NULL DEFAULT TRUE,
    regime_confidence NUMERIC(5,4) CHECK (regime_confidence >= 0 AND regime_confidence <= 1),

    -- Hysteresis tracking (prevents flip-flopping)
    consecutive_confirms INTEGER DEFAULT 0,
    prior_regime TEXT,
    regime_change_date DATE,

    -- Anomaly detection (ADR-016 DEFCON integration)
    anomaly_flag BOOLEAN NOT NULL DEFAULT FALSE,
    anomaly_type TEXT,
    anomaly_severity TEXT CHECK (anomaly_severity IN ('INFO', 'WARN', 'CRITICAL')),

    -- Lineage & versioning (ADR-002, ADR-013)
    engine_version TEXT NOT NULL,
    perception_model_version TEXT NOT NULL,
    formula_hash TEXT NOT NULL,
    lineage_hash TEXT NOT NULL,
    hash_prev TEXT,
    hash_self TEXT NOT NULL,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    UNIQUE(asset_id, timestamp)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_regime_daily_asset_ts
ON fhq_perception.regime_daily(asset_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_regime_daily_regime
ON fhq_perception.regime_daily(regime_classification);

CREATE INDEX IF NOT EXISTS idx_regime_daily_anomaly
ON fhq_perception.regime_daily(anomaly_flag) WHERE anomaly_flag = TRUE;

COMMENT ON TABLE fhq_perception.regime_daily IS
'Daily regime classification per asset. Includes hysteresis stabilization to prevent
noise-induced flip-flopping. Regimes: STRONG_BULL, BULL, NEUTRAL, BEAR, STRONG_BEAR,
VOLATILE_NON_DIRECTIONAL, COMPRESSION, BROKEN, UNTRUSTED.';

-- ============================================================================
-- 3. STATE_VECTORS TABLE
-- ============================================================================
-- Purpose: Multi-dimensional perception vectors with semantic summaries
-- Contains trend/momentum/volatility/confidence scores and deterministic language
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_perception.state_vectors (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core identifiers
    asset_id TEXT NOT NULL,
    timestamp DATE NOT NULL,

    -- Perception scores (deterministic, bounded)
    trend_score NUMERIC(6,4) NOT NULL CHECK (trend_score >= -1.0 AND trend_score <= 1.0),
    momentum_score NUMERIC(6,4) NOT NULL CHECK (momentum_score >= -1.0 AND momentum_score <= 1.0),
    volatility_score NUMERIC(5,4) NOT NULL CHECK (volatility_score >= 0.0 AND volatility_score <= 1.0),
    confidence_score NUMERIC(5,4) NOT NULL CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),

    -- Composite scores (weighted hierarchy per spec)
    -- final_score = trend*0.50 + momentum*0.30 + volatility*0.20
    final_score NUMERIC(6,4),
    trend_weight NUMERIC(4,2) DEFAULT 0.50,
    momentum_weight NUMERIC(4,2) DEFAULT 0.30,
    volatility_weight NUMERIC(4,2) DEFAULT 0.20,

    -- Component breakdown (JSON for flexibility)
    component_scores JSONB,

    -- Semantic output (deterministic template-based, NOT LLM-generated)
    semantic_context_summary TEXT NOT NULL,
    semantic_template_id TEXT,

    -- Regime link
    regime_classification TEXT NOT NULL,
    regime_daily_id UUID REFERENCES fhq_perception.regime_daily(id),

    -- Lineage & versioning (ADR-002, ADR-013)
    engine_version TEXT NOT NULL,
    perception_model_version TEXT NOT NULL,
    formula_hash TEXT NOT NULL,
    lineage_hash TEXT NOT NULL,
    hash_prev TEXT,
    hash_self TEXT NOT NULL,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    UNIQUE(asset_id, timestamp)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_state_vectors_asset_ts
ON fhq_perception.state_vectors(asset_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_state_vectors_regime
ON fhq_perception.state_vectors(regime_classification);

CREATE INDEX IF NOT EXISTS idx_state_vectors_confidence
ON fhq_perception.state_vectors(confidence_score);

COMMENT ON TABLE fhq_perception.state_vectors IS
'Multi-dimensional perception vectors per asset/day. Contains trend, momentum, volatility,
and confidence scores. Includes deterministic semantic_context_summary (template-based,
NOT LLM-generated). Hierarchical weighting: trend(0.50) > momentum(0.30) > volatility(0.20).';

-- ============================================================================
-- 4. ANOMALY_LOG TABLE
-- ============================================================================
-- Purpose: Structural breaks, extreme volatility, data gaps, perception inconsistencies
-- Integrates with ADR-016 DEFCON circuit breaker
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_perception.anomaly_log (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core identifiers
    asset_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    detection_date DATE NOT NULL,

    -- Anomaly classification
    anomaly_type TEXT NOT NULL CHECK (
        anomaly_type IN (
            'VOLATILITY_SPIKE', 'STRUCTURAL_BREAK', 'DATA_GAP',
            'SIGNAL_CONTRADICTION', 'REGIME_INSTABILITY', 'EXTREME_DEVIATION',
            'LIQUIDITY_COLLAPSE', 'CORRELATION_BREAK', 'OTHER'
        )
    ),
    severity TEXT NOT NULL CHECK (severity IN ('INFO', 'WARN', 'CRITICAL')),

    -- Anomaly details
    description TEXT NOT NULL,
    trigger_values JSONB,
    threshold_breached TEXT,
    deviation_magnitude NUMERIC(10,4),
    z_score NUMERIC(8,4),

    -- Impact assessment
    affected_indicators TEXT[],
    perception_impact TEXT CHECK (perception_impact IN ('NONE', 'DEGRADED', 'SUSPENDED')),
    regime_impact TEXT,

    -- Resolution tracking
    resolution_status TEXT DEFAULT 'OPEN' CHECK (
        resolution_status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'FALSE_POSITIVE')
    ),
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    resolution_notes TEXT,

    -- DEFCON integration (ADR-016)
    defcon_triggered BOOLEAN DEFAULT FALSE,
    defcon_level TEXT,

    -- Lineage
    engine_version TEXT NOT NULL,
    perception_model_version TEXT NOT NULL,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_anomaly_log_asset_date
ON fhq_perception.anomaly_log(asset_id, detection_date DESC);

CREATE INDEX IF NOT EXISTS idx_anomaly_log_severity
ON fhq_perception.anomaly_log(severity);

CREATE INDEX IF NOT EXISTS idx_anomaly_log_type
ON fhq_perception.anomaly_log(anomaly_type);

CREATE INDEX IF NOT EXISTS idx_anomaly_log_open
ON fhq_perception.anomaly_log(resolution_status) WHERE resolution_status = 'OPEN';

COMMENT ON TABLE fhq_perception.anomaly_log IS
'Anomaly detection log for IoS-003. Records volatility spikes, structural breaks,
data gaps, signal contradictions, and other perception inconsistencies.
Integrates with ADR-016 DEFCON circuit breaker for automatic escalation.';

-- ============================================================================
-- 5. PERCEPTION MODEL VERSION TRACKING
-- ============================================================================
-- Tracks perception logic versions for audit and backtest reproducibility
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_perception.perception_model_versions (
    -- Primary Key
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Version identifiers
    version_name TEXT NOT NULL UNIQUE,
    version_number TEXT NOT NULL,

    -- Version metadata
    description TEXT,
    effective_from DATE NOT NULL,
    effective_to DATE,
    is_current BOOLEAN DEFAULT FALSE,

    -- Logic hashes
    regime_logic_hash TEXT NOT NULL,
    scoring_logic_hash TEXT NOT NULL,
    semantic_logic_hash TEXT NOT NULL,
    combined_hash TEXT NOT NULL,

    -- Change tracking
    previous_version_id UUID REFERENCES fhq_perception.perception_model_versions(version_id),
    change_summary TEXT,

    -- Governance
    approved_by TEXT NOT NULL,
    approval_gate TEXT NOT NULL,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_perception.perception_model_versions IS
'Tracks perception model versions for IoS-003. Required for backtest reproducibility
and audit trails. Each version change requires G0-G4 gate approval.';

-- Insert initial version (placeholder for G4 activation)
INSERT INTO fhq_perception.perception_model_versions (
    version_name, version_number, description, effective_from, is_current,
    regime_logic_hash, scoring_logic_hash, semantic_logic_hash, combined_hash,
    approved_by, approval_gate
) VALUES (
    'v2026.DRAFT.1', '2026.DRAFT.1',
    'Initial IoS-003 perception model. G0 submission. Awaiting G1-G4 validation.',
    CURRENT_DATE, TRUE,
    'pending_g1', 'pending_g1', 'pending_g1', 'pending_g1',
    'CEO', 'G0'
) ON CONFLICT (version_name) DO NOTHING;

-- ============================================================================
-- 6. REGISTER META_PERCEPTION PIPELINE STAGE
-- ============================================================================

INSERT INTO fhq_governance.task_registry (
    task_id, task_name, task_description, owner_role, executor_role,
    source_schema, target_schema, task_status, gate_approved, vega_reviewed,
    created_at, updated_at
) VALUES (
    gen_random_uuid(),
    'META_PERCEPTION',
    'IoS-003 Meta-Perception Engine: Computes regime classification, state vectors, and semantic summaries from IoS-001 prices and IoS-002 indicators.',
    'LARS',
    'CODE',
    'fhq_research',
    'fhq_perception',
    'REGISTERED',
    FALSE,
    FALSE,
    NOW(),
    NOW()
) ON CONFLICT (task_name) DO UPDATE SET
    task_description = EXCLUDED.task_description,
    updated_at = NOW();

-- ============================================================================
-- 7. REGISTER IoS-003 IN IOS_REGISTRY
-- ============================================================================

INSERT INTO fhq_meta.ios_registry (
    ios_id, title, description, version, status, owner_role,
    governing_adrs, dependencies, content_hash, created_at, updated_at
) VALUES (
    'IoS-003',
    'Meta-Perception Engine (Market Brain)',
    'Deterministic perception module producing canonical market regimes, state vectors, semantic summaries, anomaly detection, and hysteresis-stabilised context.',
    '2026.DRAFT.1',
    'DRAFT',
    'LARS',
    ARRAY['ADR-001', 'ADR-002', 'ADR-003', 'ADR-004', 'ADR-006', 'ADR-007',
          'ADR-009', 'ADR-010', 'ADR-011', 'ADR-012', 'ADR-013', 'ADR-014', 'ADR-016'],
    ARRAY['IoS-001', 'IoS-002'],
    'pending_g1_hash',
    NOW(),
    NOW()
) ON CONFLICT (ios_id) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    version = EXCLUDED.version,
    updated_at = NOW();

-- ============================================================================
-- 8. LOG G0 SUBMISSION
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale,
    hash_chain_id, signature_id
) VALUES (
    gen_random_uuid(), 'IOS_MODULE_G0_SUBMISSION', 'IoS-003', 'IOS_MODULE',
    'CEO', NOW(), 'APPROVED',
    'G0 Registration complete via migration 025. IoS-003 Meta-Perception Engine schema created. Awaiting G1 Technical Validation.',
    'G0-MIG-025', gen_random_uuid()
);

COMMIT;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- IoS-003 G0_REGISTERED
-- Next: G1_TECHNICAL_VALIDATION
--
-- CONSTRAINTS ACTIVE:
-- - No computation until G4
-- - No inference until G4
-- - No perception events until G4
-- - Read-only access to IoS-001 and IoS-002
-- - Write-only access to fhq_perception.*
-- ============================================================================
