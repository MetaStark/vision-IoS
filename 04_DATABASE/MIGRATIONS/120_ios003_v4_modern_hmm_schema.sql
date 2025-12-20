-- =============================================================================
-- Migration 120: IoS-003 v4 Modern HMM Schema
-- =============================================================================
-- Authority: CEO Directive IoS-003 v4 Modernization
-- Date: 2025-12-11
-- Executor: STIG (CTO)
--
-- Purpose: Implement modernized HMM regime detection with:
--   - 3-4 states (down from 9) per academic research
--   - IOHMM with macro covariate-driven transitions
--   - Online EM for continuous parameter updates
--   - BOCD for changepoint detection
--   - Student-t emissions for fat tails
--   - Asset-class specific models (crypto, FX, equities)
-- =============================================================================

BEGIN;

-- =============================================================================
-- 1. Update regime classification enum (reduce from 9 to 4 canonical states)
-- =============================================================================

-- Add new STRESS state while preserving backward compatibility
ALTER TABLE fhq_perception.regime_daily
DROP CONSTRAINT IF EXISTS regime_daily_regime_classification_check;

ALTER TABLE fhq_perception.regime_daily
ADD CONSTRAINT regime_daily_regime_classification_check
CHECK (regime_classification = ANY (ARRAY[
    -- v4 Primary States (used going forward)
    'BULL'::text,
    'NEUTRAL'::text,
    'BEAR'::text,
    'STRESS'::text,
    -- v2.0 Legacy States (preserved for historical data)
    'STRONG_BULL'::text,
    'STRONG_BEAR'::text,
    'VOLATILE_NON_DIRECTIONAL'::text,
    'COMPRESSION'::text,
    'BROKEN'::text,
    'UNTRUSTED'::text
]));

-- =============================================================================
-- 2. Create v4 HMM model parameters table
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_perception.hmm_model_params_v4 (
    model_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_class TEXT NOT NULL CHECK (asset_class IN ('CRYPTO', 'FX', 'EQUITIES')),
    asset_id TEXT,  -- NULL means class-wide model
    n_states INTEGER NOT NULL DEFAULT 3 CHECK (n_states BETWEEN 2 AND 5),

    -- Emission parameters (Student-t per state)
    emission_mu JSONB NOT NULL,           -- Array of mu vectors per state
    emission_sigma JSONB NOT NULL,        -- Array of covariance matrices per state
    emission_nu JSONB NOT NULL,           -- Array of degrees of freedom per state

    -- Transition parameters (IOHMM weights)
    transition_weights JSONB NOT NULL,    -- Shape: [n_states, n_states, n_covariates]
    covariate_names JSONB NOT NULL,       -- List of macro covariate names

    -- Initial state distribution
    initial_dist JSONB NOT NULL,          -- Shape: [n_states]

    -- Online EM state
    learning_rate NUMERIC(5,4) DEFAULT 0.01,
    sufficient_stats JSONB,               -- Accumulated statistics for Online EM

    -- BOCD state
    run_length INTEGER DEFAULT 0,
    changepoint_prob NUMERIC(5,4) DEFAULT 0.0,
    hazard_rate NUMERIC(5,4) DEFAULT 0.01,  -- Prior probability of changepoint

    -- Metadata
    engine_version TEXT NOT NULL DEFAULT 'v4.0.0',
    trained_on_rows INTEGER DEFAULT 0,
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (asset_class, asset_id)
);

COMMENT ON TABLE fhq_perception.hmm_model_params_v4 IS
'IoS-003 v4 HMM model parameters with IOHMM transitions and Online EM support';

-- =============================================================================
-- 3. Create v4 HMM features table (extended with macro factors)
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_perception.hmm_features_v4 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id TEXT NOT NULL,
    timestamp DATE NOT NULL,

    -- Technical features (7 canonical, z-scored)
    return_z NUMERIC(10,6),
    volatility_z NUMERIC(10,6),
    drawdown_z NUMERIC(10,6),
    macd_diff_z NUMERIC(10,6),
    bb_width_z NUMERIC(10,6),
    rsi_14_z NUMERIC(10,6),
    roc_20_z NUMERIC(10,6),

    -- Macro covariates (for IOHMM transitions)
    yield_spread_z NUMERIC(10,6),         -- 10Y-3M term spread
    vix_z NUMERIC(10,6),                  -- VIX index
    inflation_z NUMERIC(10,6),            -- CPI y/y or breakeven
    liquidity_z NUMERIC(10,6),            -- TED spread / credit spread

    -- Crypto-specific (NULL for non-crypto)
    onchain_hash_z NUMERIC(10,6),         -- Hashrate z-score
    onchain_tx_z NUMERIC(10,6),           -- Transaction volume z-score

    -- Feature vector as array (for model input)
    feature_vector JSONB,                 -- Ordered array of all features
    covariate_vector JSONB,               -- Ordered array of macro covariates

    -- Metadata
    asset_class TEXT NOT NULL CHECK (asset_class IN ('CRYPTO', 'FX', 'EQUITIES')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (asset_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_hmm_features_v4_asset_ts
ON fhq_perception.hmm_features_v4 (asset_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_hmm_features_v4_class
ON fhq_perception.hmm_features_v4 (asset_class, timestamp DESC);

COMMENT ON TABLE fhq_perception.hmm_features_v4 IS
'IoS-003 v4 HMM features with technical indicators and macro covariates';

-- =============================================================================
-- 4. Create BOCD changepoint detection log
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_perception.bocd_changepoint_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    timestamp DATE NOT NULL,

    -- Changepoint metrics
    changepoint_probability NUMERIC(5,4) NOT NULL,
    run_length INTEGER NOT NULL,
    prior_run_length INTEGER,

    -- Was this flagged as a changepoint?
    is_changepoint BOOLEAN NOT NULL DEFAULT FALSE,
    changepoint_threshold NUMERIC(5,4) DEFAULT 0.5,

    -- Model state before/after
    regime_before TEXT,
    regime_after TEXT,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (asset_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_bocd_changepoints
ON fhq_perception.bocd_changepoint_log (asset_id, timestamp DESC)
WHERE is_changepoint = TRUE;

COMMENT ON TABLE fhq_perception.bocd_changepoint_log IS
'Bayesian Online Changepoint Detection log for IoS-003 v4';

-- =============================================================================
-- 5. Extend regime_daily for v4 fields
-- =============================================================================

-- Add technical_regime column (before CRIO modifiers)
ALTER TABLE fhq_perception.regime_daily
ADD COLUMN IF NOT EXISTS technical_regime TEXT;

-- Add BOCD fields
ALTER TABLE fhq_perception.regime_daily
ADD COLUMN IF NOT EXISTS changepoint_probability NUMERIC(5,4);

ALTER TABLE fhq_perception.regime_daily
ADD COLUMN IF NOT EXISTS run_length INTEGER;

-- Add model version tracking
ALTER TABLE fhq_perception.regime_daily
ADD COLUMN IF NOT EXISTS hmm_version TEXT DEFAULT 'v2.0';

-- =============================================================================
-- 6. Create sovereign regime state table (v4 spec)
-- =============================================================================
-- Note: sovereign_regime_state already exists as a VIEW, so we use a different name

CREATE TABLE IF NOT EXISTS fhq_perception.sovereign_regime_state_v4 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id TEXT NOT NULL,
    timestamp DATE NOT NULL,

    -- Regime classifications
    technical_regime TEXT NOT NULL,       -- Raw IOHMM output
    sovereign_regime TEXT NOT NULL,       -- After CRIO modifiers

    -- State probabilities
    state_probabilities JSONB NOT NULL,   -- Posterior prob for each state

    -- CRIO modifier tracking
    crio_dominant_driver TEXT,            -- LIQUIDITY, CREDIT, VIX, etc.
    crio_override_reason TEXT,

    -- Metadata
    engine_version TEXT NOT NULL DEFAULT 'v4.0.0',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (asset_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_sovereign_regime_v4_asset_ts
ON fhq_perception.sovereign_regime_state_v4 (asset_id, timestamp DESC);

COMMENT ON TABLE fhq_perception.sovereign_regime_state_v4 IS
'IoS-003 v4 Sovereign regime state with IOHMM technical regime and CRIO-modified sovereign regime';

-- =============================================================================
-- 7. Create v4 model configuration table
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_perception.hmm_v4_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_class TEXT NOT NULL,

    -- Model structure
    n_states INTEGER NOT NULL DEFAULT 3,
    emission_type TEXT NOT NULL DEFAULT 'student_t',
    use_iohmm BOOLEAN NOT NULL DEFAULT TRUE,

    -- Online EM settings
    learning_rate NUMERIC(5,4) DEFAULT 0.01,
    learning_rate_decay NUMERIC(5,4) DEFAULT 0.999,
    min_learning_rate NUMERIC(6,5) DEFAULT 0.001,

    -- BOCD settings
    hazard_rate NUMERIC(5,4) DEFAULT 0.01,
    changepoint_threshold NUMERIC(5,4) DEFAULT 0.5,

    -- Hysteresis settings
    hysteresis_days INTEGER DEFAULT 5,

    -- Feature configuration
    technical_features JSONB NOT NULL DEFAULT '["return_z", "volatility_z", "drawdown_z", "macd_diff_z", "bb_width_z", "rsi_14_z", "roc_20_z"]',
    macro_covariates JSONB NOT NULL DEFAULT '["yield_spread_z", "vix_z", "liquidity_z"]',

    -- Asset-class specific features
    crypto_features JSONB DEFAULT '["onchain_hash_z", "onchain_tx_z"]',

    -- State labels
    state_labels JSONB NOT NULL DEFAULT '["BULL", "NEUTRAL", "BEAR"]',

    -- Metadata
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (asset_class, is_active) -- Only one active config per class
);

-- Insert default configurations for each asset class
INSERT INTO fhq_perception.hmm_v4_config (
    asset_class, n_states, emission_type, use_iohmm,
    learning_rate, hazard_rate, changepoint_threshold, hysteresis_days,
    technical_features, macro_covariates, crypto_features, state_labels, is_active
) VALUES
-- Crypto: 4 states (includes STRESS), with on-chain features
('CRYPTO', 4, 'student_t', TRUE,
 0.02, 0.02, 0.5, 3,
 '["return_z", "volatility_z", "drawdown_z", "macd_diff_z", "bb_width_z", "rsi_14_z", "roc_20_z"]',
 '["vix_z", "liquidity_z"]',
 '["onchain_hash_z", "onchain_tx_z"]',
 '["BULL", "NEUTRAL", "BEAR", "STRESS"]',
 TRUE),

-- FX: 3 states, macro-heavy
('FX', 3, 'student_t', TRUE,
 0.01, 0.01, 0.5, 5,
 '["return_z", "volatility_z", "drawdown_z", "macd_diff_z", "bb_width_z", "rsi_14_z", "roc_20_z"]',
 '["yield_spread_z", "vix_z", "inflation_z", "liquidity_z"]',
 NULL,
 '["BULL", "NEUTRAL", "BEAR"]',
 TRUE),

-- Equities: 4 states, full macro suite
('EQUITIES', 4, 'student_t', TRUE,
 0.01, 0.01, 0.5, 5,
 '["return_z", "volatility_z", "drawdown_z", "macd_diff_z", "bb_width_z", "rsi_14_z", "roc_20_z"]',
 '["yield_spread_z", "vix_z", "inflation_z", "liquidity_z"]',
 NULL,
 '["BULL", "NEUTRAL", "BEAR", "STRESS"]',
 TRUE)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 8. Create regime mapping table (v2 to v4)
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_perception.regime_v2_to_v4_mapping (
    v2_regime TEXT PRIMARY KEY,
    v4_regime TEXT NOT NULL,
    mapping_confidence NUMERIC(3,2) NOT NULL DEFAULT 1.0
);

-- Insert canonical mappings
INSERT INTO fhq_perception.regime_v2_to_v4_mapping (v2_regime, v4_regime, mapping_confidence) VALUES
('STRONG_BULL', 'BULL', 1.0),
('BULL', 'BULL', 1.0),
('NEUTRAL', 'NEUTRAL', 1.0),
('BEAR', 'BEAR', 1.0),
('STRONG_BEAR', 'BEAR', 1.0),
('VOLATILE_NON_DIRECTIONAL', 'STRESS', 0.9),
('COMPRESSION', 'NEUTRAL', 0.8),
('BROKEN', 'STRESS', 0.7),
('UNTRUSTED', 'NEUTRAL', 0.5)
ON CONFLICT (v2_regime) DO UPDATE SET
    v4_regime = EXCLUDED.v4_regime,
    mapping_confidence = EXCLUDED.mapping_confidence;

-- =============================================================================
-- 9. Register IoS-003 v4 task in task registry
-- =============================================================================

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
    schedule_cron,
    schedule_timezone,
    schedule_description,
    schedule_enabled
) VALUES (
    gen_random_uuid(),
    'IOS003_DAILY_REGIME_UPDATE_V4',
    'PERCEPTION_PIPELINE',
    'IoS-003',
    'LARS',
    'CODE',
    '{fhq_market,fhq_research,fhq_macro}',
    '{fhq_perception}',
    'G4',
    true,
    true,
    'IoS-003 v4 Modern HMM Regime Detection. Uses IOHMM with macro covariates, Student-t emissions, Online EM, and BOCD changepoint detection. 3-4 states per asset class.',
    'REGISTERED',
    'STIG',
    '20 0 * * *',
    'UTC',
    'Daily at 00:20 UTC after indicators',
    false  -- Disabled until fully tested
) ON CONFLICT (task_name) DO UPDATE SET
    description = EXCLUDED.description,
    updated_at = NOW();

-- =============================================================================
-- 10. Governance logging
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'SCHEMA_MIGRATION',
    'IoS-003',
    'MODULE',
    'STIG',
    NOW(),
    'COMPLETED',
    'IoS-003 v4 Modern HMM Schema - IOHMM + Online EM + BOCD. Reduces states from 9 to 3-4, adds macro covariates, Student-t emissions.',
    encode(sha256('120_ios003_v4_modern_hmm_schema'::bytea), 'hex')
);

COMMIT;

-- =============================================================================
-- Verification
-- =============================================================================

DO $$
BEGIN
    -- Verify tables created
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables
                   WHERE table_schema = 'fhq_perception'
                   AND table_name = 'hmm_model_params_v4') THEN
        RAISE EXCEPTION 'hmm_model_params_v4 table not created';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables
                   WHERE table_schema = 'fhq_perception'
                   AND table_name = 'hmm_features_v4') THEN
        RAISE EXCEPTION 'hmm_features_v4 table not created';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables
                   WHERE table_schema = 'fhq_perception'
                   AND table_name = 'bocd_changepoint_log') THEN
        RAISE EXCEPTION 'bocd_changepoint_log table not created';
    END IF;

    -- Verify configs inserted
    IF (SELECT COUNT(*) FROM fhq_perception.hmm_v4_config WHERE is_active = TRUE) < 3 THEN
        RAISE EXCEPTION 'Not all asset class configs created';
    END IF;

    RAISE NOTICE 'IoS-003 v4 schema migration completed successfully';
END $$;
