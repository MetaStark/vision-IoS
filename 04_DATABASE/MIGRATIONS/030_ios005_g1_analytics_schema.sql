-- ============================================================================
-- MIGRATION: 030_ios005_g1_analytics_schema.sql
-- PURPOSE: G1 Scientific Validation Schema for IoS-005
-- AUTHORITY: LARS (Owner) → STIG (Technical Authority) → CODE (Execution)
-- ADR COMPLIANCE: ADR-003, ADR-004, ADR-011, ADR-013
-- STATUS: G1 ACTIVATION
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: CREATE fhq_analytics SCHEMA
-- ============================================================================
-- fhq_analytics is an analytics/reporting schema, NOT a truth source.
-- Canonical data remains in fhq_market, fhq_research, fhq_positions.

CREATE SCHEMA IF NOT EXISTS fhq_analytics;

COMMENT ON SCHEMA fhq_analytics IS
'Analytics and reporting schema for IoS-005 Forecast Calibration & Skill Engine.
Not a canonical truth source per ADR-013. Derived metrics only.';

-- ============================================================================
-- SECTION 2: CORE TABLES
-- ============================================================================

-- 2.1 Skill Scorecard Monthly
-- Stores canonical monthly performance summaries
CREATE TABLE IF NOT EXISTS fhq_analytics.skill_scorecard_monthly (
    scorecard_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Time & Asset Identification
    month_start DATE NOT NULL,
    month_end DATE NOT NULL,
    asset TEXT NOT NULL,                              -- e.g., "BTC-USD" or "PORTFOLIO"

    -- FjordHQ Skill Score (FSS)
    fss_score NUMERIC(6,5) NOT NULL,                  -- 0.00000 to 1.00000

    -- Core Performance Metrics
    sharpe_ratio NUMERIC(8,4) NOT NULL,
    sortino_ratio NUMERIC(8,4) NOT NULL,
    calmar_ratio NUMERIC(8,4) NOT NULL,

    -- Statistical Validation
    p_value_bootstrap NUMERIC(6,5) NOT NULL,          -- Bootstrap p-value
    p_value_permutation NUMERIC(6,5) NOT NULL,        -- Permutation p-value
    confidence_interval_lower NUMERIC(8,4) NOT NULL,  -- 95% CI lower (Sharpe)
    confidence_interval_upper NUMERIC(8,4) NOT NULL,  -- 95% CI upper (Sharpe)

    -- Engine & Lineage
    engine_version TEXT NOT NULL,                     -- e.g., "IoS-004_v2026.PROD.1"
    data_hash TEXT NOT NULL,                          -- Hash of input data
    lineage_hash TEXT NOT NULL,                       -- ADR-011 lineage

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG',

    -- CHECK Constraints per G1 Mandate
    CONSTRAINT chk_p_bootstrap_range CHECK (p_value_bootstrap >= 0.0 AND p_value_bootstrap <= 1.0),
    CONSTRAINT chk_p_permutation_range CHECK (p_value_permutation >= 0.0 AND p_value_permutation <= 1.0),
    CONSTRAINT chk_fss_range CHECK (fss_score >= 0.0 AND fss_score <= 1.0),
    CONSTRAINT chk_sharpe_range CHECK (sharpe_ratio >= -10.0 AND sharpe_ratio <= 20.0),
    CONSTRAINT chk_sortino_range CHECK (sortino_ratio >= -10.0 AND sortino_ratio <= 20.0),
    CONSTRAINT chk_hashes_not_null CHECK (data_hash IS NOT NULL AND lineage_hash IS NOT NULL),

    -- Uniqueness
    CONSTRAINT unique_monthly_scorecard UNIQUE (month_start, asset, engine_version)
);

-- 2.2 Calibration Curve
-- Reliability curve: predicted confidence vs realized frequency
CREATE TABLE IF NOT EXISTS fhq_analytics.calibration_curve (
    curve_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Bucket Identification
    bucket_id INTEGER NOT NULL,                       -- 0-9 for decile bins
    predicted_bin_center NUMERIC(4,3) NOT NULL,       -- e.g., 0.05, 0.15, 0.25...

    -- Realized Statistics
    realized_frequency NUMERIC(6,5) NOT NULL,         -- Actual hit rate in bucket
    count INTEGER NOT NULL,                           -- Number of observations

    -- Scope
    asset TEXT,                                       -- NULL for portfolio-level
    evaluation_period_start DATE NOT NULL,
    evaluation_period_end DATE NOT NULL,

    -- Engine & Lineage
    engine_version TEXT NOT NULL,
    lineage_hash TEXT NOT NULL,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- CHECK Constraints per G1 Mandate
    CONSTRAINT chk_predicted_range CHECK (predicted_bin_center >= 0.0 AND predicted_bin_center <= 1.0),
    CONSTRAINT chk_realized_range CHECK (realized_frequency >= 0.0 AND realized_frequency <= 1.0),
    CONSTRAINT chk_count_positive CHECK (count >= 0),

    -- Uniqueness
    CONSTRAINT unique_calibration_bucket UNIQUE (bucket_id, asset, engine_version, evaluation_period_start)
);

-- 2.3 Rolling Sharpe Log
-- 12-month rolling Sharpe for decay analysis
CREATE TABLE IF NOT EXISTS fhq_analytics.rolling_sharpe_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Time Window
    window_end_date DATE NOT NULL,
    window_months INTEGER NOT NULL DEFAULT 12,

    -- Metrics
    rolling_sharpe NUMERIC(8,4) NOT NULL,
    rolling_sortino NUMERIC(8,4),
    rolling_return NUMERIC(10,6),
    rolling_volatility NUMERIC(8,6),

    -- Asset Scope
    asset TEXT NOT NULL,

    -- Engine & Lineage
    engine_version TEXT NOT NULL,
    lineage_hash TEXT NOT NULL,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_rolling_sharpe UNIQUE (window_end_date, asset, engine_version)
);

-- 2.4 Scientific Audit Log
-- Complete audit trail of scientific validation runs
CREATE TABLE IF NOT EXISTS fhq_analytics.scientific_audit_log (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Run Identification
    run_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    engine_version TEXT NOT NULL,
    alpha_lab_version TEXT NOT NULL,

    -- Data Scope
    data_start_date DATE NOT NULL,
    data_end_date DATE NOT NULL,
    n_trading_days INTEGER NOT NULL,
    n_assets INTEGER NOT NULL,

    -- Results Summary
    actual_sharpe NUMERIC(8,4) NOT NULL,
    actual_sortino NUMERIC(8,4) NOT NULL,
    actual_calmar NUMERIC(8,4) NOT NULL,

    p_value_bootstrap NUMERIC(6,5) NOT NULL,
    p_value_permutation NUMERIC(6,5) NOT NULL,

    n_bootstrap_samples INTEGER NOT NULL DEFAULT 1000,
    n_permutation_samples INTEGER NOT NULL DEFAULT 1000,

    -- Calibration Status
    calibration_status TEXT NOT NULL,                 -- 'PASS' or 'WARNING: STRATEGY_NOT_SIGNIFICANT'

    -- Friction Applied
    friction_bps_entry NUMERIC(4,2) NOT NULL DEFAULT 5.0,
    friction_bps_exit NUMERIC(4,2) NOT NULL DEFAULT 5.0,

    -- Drift Validation
    drift_validated BOOLEAN NOT NULL DEFAULT FALSE,
    drift_tolerance NUMERIC(10,8),
    max_drift_observed NUMERIC(10,8),

    -- Excellence Flags
    bootstrap_p_lt_001 BOOLEAN NOT NULL DEFAULT FALSE,
    permutation_p_lt_001 BOOLEAN NOT NULL DEFAULT FALSE,

    -- Lineage
    data_hash TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    lineage_hash TEXT NOT NULL,
    hash_prev TEXT,
    hash_self TEXT NOT NULL,

    -- Metadata
    created_by TEXT NOT NULL DEFAULT 'STIG',
    evidence_file_path TEXT
);

-- ============================================================================
-- SECTION 3: INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_scorecard_month ON fhq_analytics.skill_scorecard_monthly(month_start);
CREATE INDEX IF NOT EXISTS idx_scorecard_asset ON fhq_analytics.skill_scorecard_monthly(asset);
CREATE INDEX IF NOT EXISTS idx_scorecard_engine ON fhq_analytics.skill_scorecard_monthly(engine_version);

CREATE INDEX IF NOT EXISTS idx_calibration_engine ON fhq_analytics.calibration_curve(engine_version);
CREATE INDEX IF NOT EXISTS idx_calibration_period ON fhq_analytics.calibration_curve(evaluation_period_start);

CREATE INDEX IF NOT EXISTS idx_rolling_date ON fhq_analytics.rolling_sharpe_log(window_end_date);
CREATE INDEX IF NOT EXISTS idx_rolling_asset ON fhq_analytics.rolling_sharpe_log(asset);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON fhq_analytics.scientific_audit_log(run_timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_engine ON fhq_analytics.scientific_audit_log(engine_version);

-- ============================================================================
-- SECTION 4: TASK REGISTRATION (G1)
-- ============================================================================

-- Update existing task to G1 or create new SCIENTIFIC_AUDIT task
INSERT INTO fhq_governance.task_registry (
    task_id,
    task_name,
    task_type,
    task_scope,
    owned_by_agent,
    executed_by_agent,
    reads_from_schemas,
    writes_to_schemas,
    gate_level,
    gate_approved,
    vega_reviewed,
    description,
    task_status,
    created_by,
    created_at,
    updated_at,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'SCIENTIFIC_AUDIT_V1',
    'SCIENTIFIC_AUDIT',
    'IOS_005_INTERNAL',
    'LARS',
    'CODE',
    ARRAY['fhq_market', 'fhq_research', 'fhq_positions'],
    ARRAY['fhq_analytics'],
    'G1',
    FALSE,
    FALSE,
    'Scientific Audit Engine for IoS-005. Performs bootstrap analysis, permutation tests, rolling Sharpe computation, and calibration curve generation. Evaluates IoS-004 strategy performance with statistical rigor.',
    'REGISTERED',
    'STIG',
    NOW(),
    NOW(),
    'HC-IOS-005-2026'
) ON CONFLICT (task_name) DO UPDATE SET
    gate_level = 'G1',
    reads_from_schemas = ARRAY['fhq_market', 'fhq_research', 'fhq_positions'],
    writes_to_schemas = ARRAY['fhq_analytics'],
    updated_at = NOW();

-- Update hash chain
UPDATE vision_verification.hash_chains
SET chain_length = chain_length + 1,
    current_hash = encode(sha256(('IoS-005_G1_ANALYTICS_SCHEMA_' || NOW()::text)::bytea), 'hex'),
    updated_at = NOW()
WHERE chain_id = 'HC-IOS-005-2026';

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================
-- SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'fhq_analytics';
-- SELECT * FROM fhq_governance.task_registry WHERE task_name = 'SCIENTIFIC_AUDIT_V1';
