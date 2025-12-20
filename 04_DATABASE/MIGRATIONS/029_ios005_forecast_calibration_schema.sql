-- ============================================================================
-- MIGRATION: 029_ios005_forecast_calibration_schema.sql
-- PURPOSE: Schema foundation for IoS-005 Forecast Calibration & Skill Engine
-- AUTHORITY: LARS (Owner) → STIG (Technical Authority) → CODE (Execution)
-- ADR COMPLIANCE: ADR-003 (Institutional Standards), ADR-011 (Fortress), ADR-013 (Kernel)
-- STATUS: G0 SUBMISSION
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: CORE TABLES
-- ============================================================================

-- 1.1 Forecast Skill Registry
-- The permanent record of strategic competence per module version
CREATE TABLE IF NOT EXISTS fhq_research.forecast_skill_registry (
    scorecard_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Engine Identification
    engine_version TEXT NOT NULL,                    -- e.g., "IoS-004_v2026.PROD.1"
    engine_module TEXT NOT NULL,                     -- e.g., "IoS-004"
    evaluation_date DATE NOT NULL,

    -- FjordHQ Skill Score (FSS)
    fss_score NUMERIC(5,4) NOT NULL,                 -- 0.0000 to 1.0000
    fss_risk_adj_return NUMERIC(5,4),                -- Component: 40% weight
    fss_stability NUMERIC(5,4),                      -- Component: 30% weight
    fss_significance NUMERIC(5,4),                   -- Component: 20% weight
    fss_consistency NUMERIC(5,4),                    -- Component: 10% weight

    -- Core Performance Metrics
    sharpe_ratio NUMERIC(8,4),
    sortino_ratio NUMERIC(8,4),
    calmar_ratio NUMERIC(8,4),
    information_ratio NUMERIC(8,4),

    -- Return Metrics
    cagr NUMERIC(8,6),                               -- Compound Annual Growth Rate
    total_return NUMERIC(10,6),
    annualized_volatility NUMERIC(8,6),

    -- Risk Metrics
    max_drawdown NUMERIC(8,6),
    max_drawdown_duration INTEGER,                   -- Days
    downside_deviation NUMERIC(8,6),
    var_95 NUMERIC(8,6),                             -- Value at Risk 95%
    cvar_95 NUMERIC(8,6),                            -- Conditional VaR 95%

    -- Behavioral Metrics
    hit_rate NUMERIC(5,4),                           -- Win percentage
    win_loss_ratio NUMERIC(8,4),
    profit_factor NUMERIC(8,4),
    tail_ratio NUMERIC(8,4),

    -- Statistical Validation
    p_value_bootstrap NUMERIC(6,5),                  -- Bootstrap resampling p-value
    p_value_permutation NUMERIC(6,5),                -- Permutation test p-value
    confidence_interval_lower NUMERIC(8,4),          -- 95% CI lower bound (Sharpe)
    confidence_interval_upper NUMERIC(8,4),          -- 95% CI upper bound (Sharpe)
    n_bootstrap_samples INTEGER DEFAULT 1000,
    n_permutation_samples INTEGER DEFAULT 1000,

    -- Certification Status
    is_certified BOOLEAN DEFAULT FALSE,              -- TRUE if p < 0.05 AND Sharpe > 1.0
    certification_reason TEXT,

    -- Backtest Parameters
    backtest_start_date DATE NOT NULL,
    backtest_end_date DATE NOT NULL,
    n_trading_days INTEGER NOT NULL,
    n_assets INTEGER NOT NULL,

    -- Configuration & Lineage
    config_hash TEXT NOT NULL,                       -- Hash of Alpha Lab configuration
    alpha_lab_version TEXT NOT NULL,                 -- e.g., "1.0.0"

    -- ADR-011 Hash Chain
    lineage_hash TEXT NOT NULL,
    hash_prev TEXT,
    hash_self TEXT NOT NULL,

    -- Metadata
    created_by TEXT NOT NULL DEFAULT 'STIG',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT fss_range CHECK (fss_score >= 0 AND fss_score <= 1),
    CONSTRAINT p_value_range CHECK (p_value_bootstrap >= 0 AND p_value_bootstrap <= 1),
    CONSTRAINT unique_engine_evaluation UNIQUE (engine_version, evaluation_date)
);

-- 1.2 Backtest Results (Daily Performance Ledger)
-- Detailed daily performance logs for visualization and drill-down analysis
CREATE TABLE IF NOT EXISTS fhq_research.backtest_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scorecard_id UUID NOT NULL REFERENCES fhq_research.forecast_skill_registry(scorecard_id),

    -- Time & Asset
    timestamp DATE NOT NULL,
    asset_id TEXT,                                   -- NULL for portfolio-level metrics

    -- Position & Exposure
    exposure NUMERIC(8,6),                           -- Actual exposure taken
    target_exposure NUMERIC(8,6),                    -- Target from IoS-004

    -- Returns
    daily_return NUMERIC(10,8),                      -- Strategy return
    benchmark_return NUMERIC(10,8),                  -- Buy-and-hold return
    excess_return NUMERIC(10,8),                     -- Strategy - Benchmark

    -- Cumulative Performance
    cumulative_return NUMERIC(12,8),
    cumulative_benchmark NUMERIC(12,8),

    -- Risk Metrics (Rolling)
    rolling_volatility_20d NUMERIC(8,6),
    rolling_sharpe_20d NUMERIC(8,4),
    rolling_drawdown NUMERIC(8,6),

    -- Regime Context
    regime_label TEXT,
    regime_confidence NUMERIC(5,4),

    -- Portfolio State
    portfolio_value NUMERIC(16,4),                   -- Simulated portfolio value
    cash_weight NUMERIC(8,6),

    -- Lineage
    lineage_hash TEXT NOT NULL,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Indexes for performance
    CONSTRAINT backtest_asset_date UNIQUE (scorecard_id, timestamp, asset_id)
);

-- 1.3 Canonical Price Cache (for backtest reproducibility)
-- Stores the exact prices used for each backtest run
CREATE TABLE IF NOT EXISTS fhq_research.backtest_price_cache (
    cache_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scorecard_id UUID NOT NULL REFERENCES fhq_research.forecast_skill_registry(scorecard_id),

    -- Price Data
    asset_id TEXT NOT NULL,
    timestamp DATE NOT NULL,
    close_price NUMERIC(18,8) NOT NULL,
    adj_close_price NUMERIC(18,8),

    -- Source Tracking
    source_table TEXT NOT NULL,                      -- e.g., "fhq_data.price_series"
    source_hash TEXT,                                -- Hash of source row

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT price_cache_unique UNIQUE (scorecard_id, asset_id, timestamp)
);

-- ============================================================================
-- SECTION 2: INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_skill_registry_engine ON fhq_research.forecast_skill_registry(engine_version);
CREATE INDEX IF NOT EXISTS idx_skill_registry_certified ON fhq_research.forecast_skill_registry(is_certified);
CREATE INDEX IF NOT EXISTS idx_skill_registry_fss ON fhq_research.forecast_skill_registry(fss_score DESC);

CREATE INDEX IF NOT EXISTS idx_backtest_results_date ON fhq_research.backtest_results(timestamp);
CREATE INDEX IF NOT EXISTS idx_backtest_results_scorecard ON fhq_research.backtest_results(scorecard_id);
CREATE INDEX IF NOT EXISTS idx_backtest_results_asset ON fhq_research.backtest_results(asset_id);

CREATE INDEX IF NOT EXISTS idx_price_cache_asset_date ON fhq_research.backtest_price_cache(asset_id, timestamp);

-- ============================================================================
-- SECTION 3: HASH CHAIN REGISTRATION
-- ============================================================================

INSERT INTO vision_verification.hash_chains (
    chain_id,
    chain_type,
    chain_scope,
    genesis_hash,
    current_hash,
    chain_length,
    integrity_verified,
    last_verification_at,
    created_by,
    created_at,
    updated_at
) VALUES (
    'HC-IOS-005-2026',
    'IOS_MODULE',
    'IoS-005',
    encode(sha256('IoS-005_GENESIS_FORECAST_CALIBRATION_2026'::bytea), 'hex'),
    encode(sha256('IoS-005_GENESIS_FORECAST_CALIBRATION_2026'::bytea), 'hex'),
    1,
    TRUE,
    NOW(),
    'STIG',
    NOW(),
    NOW()
) ON CONFLICT (chain_id) DO NOTHING;

-- ============================================================================
-- SECTION 4: TASK REGISTRATION (G0)
-- ============================================================================

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
    'FORECAST_CALIBRATION_ENGINE_V1',
    'CALIBRATION_ENGINE',
    'IOS_005_INTERNAL',
    'LARS',
    'CODE',
    ARRAY['fhq_research', 'fhq_positions', 'fhq_data'],
    ARRAY['fhq_research'],
    'G0',
    FALSE,
    FALSE,
    'Forecast Calibration & Skill Engine. Validates IoS-004 allocation performance using statistical methods. Computes FjordHQ Skill Score (FSS), performs bootstrap/permutation tests, and maintains immutable performance ledger.',
    'REGISTERED',
    'STIG',
    NOW(),
    NOW(),
    'HC-IOS-005-2026'
) ON CONFLICT (task_name) DO NOTHING;

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- SELECT * FROM fhq_research.forecast_skill_registry LIMIT 1;
-- SELECT * FROM fhq_governance.task_registry WHERE task_name = 'FORECAST_CALIBRATION_ENGINE_V1';
-- SELECT * FROM vision_verification.hash_chains WHERE chain_id = 'HC-IOS-005-2026';
