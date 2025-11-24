-- ============================================================================
-- FHQ-IoS Phase 3 Database Schema
-- Authority: LARS Phase 3 Directive (HC-LARS-PHASE3-CONTINUE-20251124)
-- Canonical ADR Chain: ADR-001 → ADR-015
-- ============================================================================
--
-- Purpose: Phase 3 expansion isolated from Gold Baseline v1.0
-- Scope: Autonomous intelligence, orchestrator expansion, integration
-- Schema: fhq_phase3 (separate from production schema)
--
-- ADR Compliance:
-- - ADR-008: Ed25519 cryptographic signatures on all predictions
-- - ADR-012: Economic safety (cost tracking, rate limits)
-- - ADR-014: Canonical ADR governance
-- - ADR-015: Meta-governance framework
-- ============================================================================

-- Create Phase 3 schema (isolated from production)
CREATE SCHEMA IF NOT EXISTS fhq_phase3;

-- Set search path for Phase 3 development
SET search_path TO fhq_phase3, public;

-- ============================================================================
-- FINN+ Tables: Market Regime Classification
-- ============================================================================

-- Regime Predictions Table
-- Stores FINN+ regime classifications with Ed25519 signatures
CREATE TABLE IF NOT EXISTS regime_predictions (
    -- Primary identification
    prediction_id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Regime classification
    regime_label VARCHAR(10) NOT NULL CHECK (regime_label IN ('BEAR', 'NEUTRAL', 'BULL')),
    regime_state INTEGER NOT NULL CHECK (regime_state IN (0, 1, 2)),
    confidence DECIMAL(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),

    -- Regime probabilities
    prob_bear DECIMAL(5,4) NOT NULL CHECK (prob_bear >= 0 AND prob_bear <= 1),
    prob_neutral DECIMAL(5,4) NOT NULL CHECK (prob_neutral >= 0 AND prob_neutral <= 1),
    prob_bull DECIMAL(5,4) NOT NULL CHECK (prob_bull >= 0 AND prob_bull <= 1),

    -- Feature inputs (z-scored)
    return_z DECIMAL(10,4),
    volatility_z DECIMAL(10,4),
    drawdown_z DECIMAL(10,4),
    macd_diff_z DECIMAL(10,4),
    bb_width_z DECIMAL(10,4),
    rsi_14_z DECIMAL(10,4),
    roc_20_z DECIMAL(10,4),

    -- Validation metadata
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    validation_reason TEXT,
    candidate_regime INTEGER CHECK (candidate_regime IN (0, 1, 2)),
    candidate_count INTEGER DEFAULT 0,

    -- Persistence tracking
    persistence_days INTEGER,
    raw_regime INTEGER CHECK (raw_regime IN (0, 1, 2)),

    -- ADR-008: Ed25519 cryptographic signature
    signature_hex TEXT NOT NULL,
    public_key_hex TEXT NOT NULL,
    signature_verified BOOLEAN NOT NULL DEFAULT FALSE,

    -- ADR-012: Economic safety tracking
    llm_api_calls INTEGER DEFAULT 0,
    llm_cost_usd DECIMAL(10,6) DEFAULT 0.0,

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50) DEFAULT 'FINN+',

    -- Constraints
    CONSTRAINT prob_sum_check CHECK (
        ABS((prob_bear + prob_neutral + prob_bull) - 1.0) < 0.01
    ),
    CONSTRAINT timestamp_index_unique UNIQUE (timestamp)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_regime_predictions_timestamp
    ON regime_predictions(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_regime_predictions_regime_label
    ON regime_predictions(regime_label);

CREATE INDEX IF NOT EXISTS idx_regime_predictions_created_at
    ON regime_predictions(created_at DESC);

-- Comments
COMMENT ON TABLE regime_predictions IS
    'FINN+ market regime classifications with Ed25519 signatures (Phase 3)';

COMMENT ON COLUMN regime_predictions.signature_hex IS
    'Ed25519 signature (ADR-008): Signs JSON payload of prediction';

COMMENT ON COLUMN regime_predictions.public_key_hex IS
    'Ed25519 public key for signature verification';

COMMENT ON COLUMN regime_predictions.llm_api_calls IS
    'ADR-012: Count of LLM API calls for this prediction (Week 1: always 0)';


-- ============================================================================
-- STIG+ Tables: Validation Framework
-- ============================================================================

-- Validation Results Table
-- Stores STIG+ validation results for multi-tier checks
CREATE TABLE IF NOT EXISTS validation_results (
    -- Primary identification
    validation_id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Validation target
    target_table VARCHAR(50) NOT NULL,
    target_id BIGINT NOT NULL,
    validation_tier INTEGER NOT NULL CHECK (validation_tier IN (1, 2, 3, 4, 5)),

    -- Validation outcome
    is_valid BOOLEAN NOT NULL,
    validation_score DECIMAL(5,4) CHECK (validation_score >= 0 AND validation_score <= 1),
    severity VARCHAR(20) CHECK (severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')),

    -- Validation details
    check_name VARCHAR(100) NOT NULL,
    check_description TEXT,
    failure_reason TEXT,

    -- Reconciliation
    requires_reconciliation BOOLEAN DEFAULT FALSE,
    reconciliation_status VARCHAR(20) CHECK (
        reconciliation_status IN ('PENDING', 'IN_PROGRESS', 'RESOLVED', 'ESCALATED')
    ),

    -- ADR-008: Ed25519 signature for validation attestation
    signature_hex TEXT,
    public_key_hex TEXT,

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50) DEFAULT 'STIG+',

    -- Foreign key constraint (enforced at application level)
    CONSTRAINT fk_target CHECK (
        (target_table = 'regime_predictions' AND target_id IS NOT NULL) OR
        (target_table != 'regime_predictions')
    )
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_validation_results_timestamp
    ON validation_results(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_validation_results_target
    ON validation_results(target_table, target_id);

CREATE INDEX IF NOT EXISTS idx_validation_results_tier
    ON validation_results(validation_tier);

-- Comments
COMMENT ON TABLE validation_results IS
    'STIG+ multi-tier validation results (Phase 3)';


-- ============================================================================
-- LINE+ Tables: Data Pipeline
-- ============================================================================

-- OHLCV Data Table (Multi-interval)
-- Stores market data at multiple time intervals
CREATE TABLE IF NOT EXISTS ohlcv_data (
    -- Primary identification
    ohlcv_id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    interval VARCHAR(10) NOT NULL CHECK (interval IN ('1m', '5m', '15m', '1h', '1d')),

    -- OHLCV data
    open DECIMAL(20,8) NOT NULL CHECK (open > 0),
    high DECIMAL(20,8) NOT NULL CHECK (high > 0),
    low DECIMAL(20,8) NOT NULL CHECK (low > 0),
    close DECIMAL(20,8) NOT NULL CHECK (close > 0),
    volume DECIMAL(20,8) NOT NULL CHECK (volume >= 0),

    -- Data quality
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    quality_score DECIMAL(5,4),
    data_source VARCHAR(50),

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50) DEFAULT 'LINE+',

    -- Constraints
    CONSTRAINT ohlcv_price_check CHECK (
        low <= open AND low <= close AND
        high >= open AND high >= close
    ),
    CONSTRAINT ohlcv_unique UNIQUE (timestamp, symbol, interval)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_ohlcv_timestamp_symbol
    ON ohlcv_data(timestamp DESC, symbol);

CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_interval
    ON ohlcv_data(symbol, interval, timestamp DESC);

-- Comments
COMMENT ON TABLE ohlcv_data IS
    'LINE+ multi-interval OHLCV market data (Phase 3)';


-- ============================================================================
-- Orchestrator Tables: Decision Flow Tracking
-- ============================================================================

-- Orchestrator Cycles Table
-- Tracks Phase 3 orchestrator execution cycles
CREATE TABLE IF NOT EXISTS orchestrator_cycles (
    -- Primary identification
    cycle_id BIGSERIAL PRIMARY KEY,
    cycle_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cycle_end TIMESTAMPTZ,

    -- Cycle metadata
    cycle_type VARCHAR(20) CHECK (cycle_type IN ('PHASE3_TIER1', 'PHASE3_TIER2', 'PHASE3_TIER3')),
    cycle_status VARCHAR(20) NOT NULL CHECK (
        cycle_status IN ('RUNNING', 'COMPLETED', 'FAILED', 'ABORTED')
    ),

    -- Tier execution tracking
    tier1_completed BOOLEAN DEFAULT FALSE,
    tier2_completed BOOLEAN DEFAULT FALSE,
    tier3_completed BOOLEAN DEFAULT FALSE,

    -- Step tracking (25 steps total)
    steps_completed INTEGER DEFAULT 0 CHECK (steps_completed >= 0 AND steps_completed <= 25),
    current_step INTEGER CHECK (current_step >= 1 AND current_step <= 25),

    -- Economic tracking (ADR-012)
    total_llm_calls INTEGER DEFAULT 0,
    total_cost_usd DECIMAL(10,6) DEFAULT 0.0,

    -- Output tracking
    decision_outcome VARCHAR(20),
    decision_confidence DECIMAL(5,4),

    -- Error handling
    error_message TEXT,
    error_tier INTEGER,
    error_step INTEGER,

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_orchestrator_cycles_start
    ON orchestrator_cycles(cycle_start DESC);

CREATE INDEX IF NOT EXISTS idx_orchestrator_cycles_status
    ON orchestrator_cycles(cycle_status);

-- Comments
COMMENT ON TABLE orchestrator_cycles IS
    'Phase 3 orchestrator execution tracking';


-- ============================================================================
-- Cost Tracking Table (ADR-012 Compliance)
-- ============================================================================

-- LLM API Cost Tracking
CREATE TABLE IF NOT EXISTS llm_api_costs (
    -- Primary identification
    cost_id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Agent identification
    agent_name VARCHAR(50) NOT NULL CHECK (agent_name IN ('FINN+', 'STIG+', 'LINE+', 'VEGA+')),

    -- Cost details
    api_calls INTEGER NOT NULL DEFAULT 0,
    cost_usd DECIMAL(10,6) NOT NULL DEFAULT 0.0,

    -- Rate limiting (ADR-012)
    daily_calls INTEGER DEFAULT 0,
    daily_cost_usd DECIMAL(10,6) DEFAULT 0.0,
    rate_limit_hit BOOLEAN DEFAULT FALSE,

    -- Context
    operation_type VARCHAR(50),
    reference_table VARCHAR(50),
    reference_id BIGINT,

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_llm_costs_timestamp
    ON llm_api_costs(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_llm_costs_agent
    ON llm_api_costs(agent_name, timestamp DESC);

-- Comments
COMMENT ON TABLE llm_api_costs IS
    'ADR-012: LLM API cost tracking and rate limit enforcement';


-- ============================================================================
-- Views for Monitoring and Reporting
-- ============================================================================

-- Regime Prediction Summary View
CREATE OR REPLACE VIEW v_regime_summary AS
SELECT
    DATE(timestamp) as date,
    regime_label,
    COUNT(*) as prediction_count,
    AVG(confidence) as avg_confidence,
    AVG(persistence_days) as avg_persistence,
    SUM(llm_api_calls) as total_api_calls,
    SUM(llm_cost_usd) as total_cost_usd
FROM regime_predictions
GROUP BY DATE(timestamp), regime_label
ORDER BY date DESC, regime_label;

COMMENT ON VIEW v_regime_summary IS
    'Daily regime prediction summary with cost tracking';


-- Validation Summary View
CREATE OR REPLACE VIEW v_validation_summary AS
SELECT
    DATE(timestamp) as date,
    validation_tier,
    target_table,
    COUNT(*) as total_validations,
    SUM(CASE WHEN is_valid THEN 1 ELSE 0 END) as passed,
    SUM(CASE WHEN NOT is_valid THEN 1 ELSE 0 END) as failed,
    AVG(validation_score) as avg_score
FROM validation_results
GROUP BY DATE(timestamp), validation_tier, target_table
ORDER BY date DESC, validation_tier;

COMMENT ON VIEW v_validation_summary IS
    'Daily validation results summary by tier and target';


-- Cost Summary View (ADR-012)
CREATE OR REPLACE VIEW v_cost_summary AS
SELECT
    DATE(timestamp) as date,
    agent_name,
    SUM(api_calls) as total_calls,
    SUM(cost_usd) as total_cost_usd,
    MAX(daily_calls) as peak_daily_calls,
    MAX(daily_cost_usd) as peak_daily_cost
FROM llm_api_costs
GROUP BY DATE(timestamp), agent_name
ORDER BY date DESC, agent_name;

COMMENT ON VIEW v_cost_summary IS
    'ADR-012: Daily LLM API cost summary by agent';


-- ============================================================================
-- Grants and Permissions
-- ============================================================================

-- Grant read access to reporting role (if exists)
-- GRANT SELECT ON ALL TABLES IN SCHEMA fhq_phase3 TO reporting_role;
-- GRANT SELECT ON ALL SEQUENCES IN SCHEMA fhq_phase3 TO reporting_role;

-- Grant write access to application role (if exists)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA fhq_phase3 TO app_role;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA fhq_phase3 TO app_role;


-- ============================================================================
-- Schema Version Tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version_id SERIAL PRIMARY KEY,
    version VARCHAR(20) NOT NULL,
    description TEXT,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO schema_version (version, description) VALUES
    ('1.0.0', 'Phase 3 initial schema: FINN+, STIG+, LINE+, Orchestrator tables')
ON CONFLICT DO NOTHING;

COMMENT ON TABLE schema_version IS
    'Phase 3 database schema version tracking';


-- ============================================================================
-- End of Phase 3 Schema
-- ============================================================================
