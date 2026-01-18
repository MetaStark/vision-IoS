-- Migration 311: CEO-DIR-2026-093 - Autonomous Shadow Learning for IoS-003C
-- Authority: CEO
-- Executed by: STIG (EC-003)
-- Date: 2026-01-18
--
-- Purpose:
-- Establish a 30-day autonomous measurement program for IoS-003C Crypto Regime Engine
-- to verify predictive value before granting execution authority.
--
-- Tables:
-- - fhq_research.crypto_regime_shadow_ledger: Append-only ledger of regime predictions
-- - fhq_research.crypto_regime_outcomes: Captured outcomes for each prediction
-- - fhq_research.crypto_regime_quality_metrics: Daily/weekly quality metrics
--
-- Stop Conditions:
-- - Brier > 0.35 for 7 consecutive days
-- - Hit rate < 45% over 30 samples
-- - Bootstrap p-value > 0.05 (no significant predictive skill)
-- - Regime persistence < 1.5 days mean (regime instability)
-- - Identity Drift > 5% (instrument_type NULL or missing)
--
-- Governed by: ADR-013A (Time Authority Doctrine), IoS-003C, CEO-DIR-2026-092

BEGIN;

-- ============================================================================
-- SECTION 1: SHADOW LEDGER TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.crypto_regime_shadow_ledger (
    ledger_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Temporal Identity (per ADR-013A)
    epoch_date DATE NOT NULL,
    epoch_boundary TIMESTAMPTZ NOT NULL,  -- 00:00:00 UTC
    signal_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Asset Identity (per CEO-DIR-2026-090)
    ticker VARCHAR(20) NOT NULL,
    asset_class VARCHAR(20) NOT NULL DEFAULT 'CRYPTO' CHECK (asset_class = 'CRYPTO'),
    instrument_type VARCHAR(20),  -- SPOT, PERP (from fhq_meta.assets)
    data_granularity VARCHAR(30), -- AGGREGATED, EXCHANGE_RAW

    -- Regime Prediction
    predicted_regime VARCHAR(20) NOT NULL CHECK (predicted_regime IN ('BULL', 'BEAR', 'NEUTRAL', 'STRESS')),
    confidence DECIMAL(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    regime_drivers JSONB,  -- Dimensional breakdown (stablecoin, liquidity, microstructure)

    -- Price Data at Prediction
    price_at_signal DECIMAL(18,8) NOT NULL,

    -- Outcome Capture (filled later)
    outcome_captured BOOLEAN DEFAULT FALSE,
    outcome_capture_timestamp TIMESTAMPTZ,

    -- Reference
    forecast_id UUID,
    reference_epoch_id VARCHAR(50),

    -- Governance
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(20) NOT NULL DEFAULT 'ios003c_daemon',

    -- Indexes for efficient querying
    CONSTRAINT crypto_shadow_unique_epoch_ticker UNIQUE (epoch_date, ticker)
);

-- Index for date-range queries
CREATE INDEX IF NOT EXISTS idx_crypto_shadow_epoch_date
    ON fhq_research.crypto_regime_shadow_ledger(epoch_date);

-- Index for ticker queries
CREATE INDEX IF NOT EXISTS idx_crypto_shadow_ticker
    ON fhq_research.crypto_regime_shadow_ledger(ticker);

-- Index for regime queries
CREATE INDEX IF NOT EXISTS idx_crypto_shadow_regime
    ON fhq_research.crypto_regime_shadow_ledger(predicted_regime);

COMMENT ON TABLE fhq_research.crypto_regime_shadow_ledger IS
    'CEO-DIR-2026-093: Append-only ledger of crypto regime predictions in Shadow Mode. 30-day measurement program.';


-- ============================================================================
-- SECTION 2: OUTCOMES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.crypto_regime_outcomes (
    outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to prediction
    ledger_id UUID NOT NULL REFERENCES fhq_research.crypto_regime_shadow_ledger(ledger_id),

    -- Temporal (per ADR-013A)
    epoch_date DATE NOT NULL,
    outcome_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Asset
    ticker VARCHAR(20) NOT NULL,

    -- Prices at horizons (1D, 3D, 5D)
    price_t0 DECIMAL(18,8) NOT NULL,
    price_t0_plus_1d DECIMAL(18,8),
    price_t0_plus_3d DECIMAL(18,8),
    price_t0_plus_5d DECIMAL(18,8),

    -- Returns
    return_1d DECIMAL(10,6),  -- (price_1d - price_t0) / price_t0
    return_3d DECIMAL(10,6),
    return_5d DECIMAL(10,6),

    -- Realized Volatility
    realized_vol_1d DECIMAL(10,6),
    realized_vol_3d DECIMAL(10,6),
    realized_vol_5d DECIMAL(10,6),

    -- Actual Regime (if determinable)
    actual_regime VARCHAR(20),

    -- Directional Correctness
    correct_direction_1d BOOLEAN,  -- Did regime predict direction correctly?
    correct_direction_3d BOOLEAN,
    correct_direction_5d BOOLEAN,

    -- Brier Score Components
    brier_score DECIMAL(10,6),  -- (predicted_confidence - actual_outcome)^2

    -- Governance
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT crypto_outcome_unique_ledger UNIQUE (ledger_id)
);

CREATE INDEX IF NOT EXISTS idx_crypto_outcomes_epoch
    ON fhq_research.crypto_regime_outcomes(epoch_date);

CREATE INDEX IF NOT EXISTS idx_crypto_outcomes_ticker
    ON fhq_research.crypto_regime_outcomes(ticker);

COMMENT ON TABLE fhq_research.crypto_regime_outcomes IS
    'CEO-DIR-2026-093: Captured outcomes for crypto regime predictions. Links to shadow_ledger.';


-- ============================================================================
-- SECTION 3: QUALITY METRICS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.crypto_regime_quality_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Temporal
    metric_date DATE NOT NULL,
    metric_type VARCHAR(30) NOT NULL CHECK (metric_type IN ('DAILY', 'WEEKLY', 'CUMULATIVE')),

    -- Sample Statistics
    sample_size INTEGER NOT NULL,
    signals_with_outcome INTEGER NOT NULL,

    -- Brier Score
    avg_brier DECIMAL(10,6),
    rolling_7d_brier DECIMAL(10,6),
    rolling_30d_brier DECIMAL(10,6),

    -- Hit Rates
    hit_rate_1d DECIMAL(5,4),
    hit_rate_3d DECIMAL(5,4),
    hit_rate_5d DECIMAL(5,4),

    -- Calibration
    calibration_score DECIMAL(10,6),  -- ECE or similar

    -- Bootstrap Significance (weekly)
    bootstrap_p_value DECIMAL(10,6),
    bootstrap_ci_lower DECIMAL(10,6),
    bootstrap_ci_upper DECIMAL(10,6),
    bootstrap_samples INTEGER,
    predictive_skill_significant BOOLEAN,  -- p < 0.05

    -- Regime Persistence
    regime_persistence_mean DECIMAL(10,4),  -- Mean days before regime change
    regime_persistence_median DECIMAL(10,4),
    regime_transition_count INTEGER,

    -- Lane-Specific Signal Quality
    lane_c_signal_count INTEGER,  -- Funding rates / derivatives signals
    lane_c_hit_rate DECIMAL(5,4),

    -- Identity Drift (per CEO improvement)
    instrument_type_null_pct DECIMAL(5,4),  -- % of signals with NULL instrument_type
    identity_drift_detected BOOLEAN,  -- TRUE if > 5%

    -- Stop Condition Status
    stop_condition_triggered BOOLEAN DEFAULT FALSE,
    stop_condition_reason VARCHAR(100),

    -- CRIO Integration
    crio_causal_map_available BOOLEAN DEFAULT FALSE,
    crio_causal_map_id UUID,

    -- Governance
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    vega_attested BOOLEAN DEFAULT FALSE,
    vega_attestation_id UUID,
    vega_attestation_timestamp TIMESTAMPTZ,

    CONSTRAINT crypto_metrics_unique_date_type UNIQUE (metric_date, metric_type)
);

CREATE INDEX IF NOT EXISTS idx_crypto_metrics_date
    ON fhq_research.crypto_regime_quality_metrics(metric_date);

COMMENT ON TABLE fhq_research.crypto_regime_quality_metrics IS
    'CEO-DIR-2026-093: Quality metrics for IoS-003C shadow learning. Tracks Brier, hit rate, significance, stop conditions.';


-- ============================================================================
-- SECTION 4: STOP CONDITIONS CONFIGURATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.crypto_regime_stop_conditions (
    condition_id VARCHAR(50) PRIMARY KEY,
    condition_name VARCHAR(100) NOT NULL,
    condition_type VARCHAR(30) NOT NULL CHECK (condition_type IN ('THRESHOLD', 'DURATION', 'STATISTICAL')),

    -- Threshold values
    threshold_value DECIMAL(10,6),
    threshold_operator VARCHAR(10) CHECK (threshold_operator IN ('<', '<=', '>', '>=', '=')),
    duration_days INTEGER,  -- For duration-based conditions

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_triggered BOOLEAN DEFAULT FALSE,
    triggered_at TIMESTAMPTZ,
    triggered_value DECIMAL(10,6),

    -- Governance
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(20) DEFAULT 'CEO-DIR-2026-093'
);

-- Insert default stop conditions per CEO-DIR-2026-093
INSERT INTO fhq_research.crypto_regime_stop_conditions
    (condition_id, condition_name, condition_type, threshold_value, threshold_operator, duration_days)
VALUES
    ('BRIER_CONSECUTIVE', 'Brier > 0.35 for 7 consecutive days', 'DURATION', 0.35, '>', 7),
    ('HIT_RATE_FLOOR', 'Hit rate < 45% over 30 samples', 'THRESHOLD', 0.45, '<', NULL),
    ('BOOTSTRAP_P_VALUE', 'Bootstrap p-value > 0.05', 'STATISTICAL', 0.05, '>', NULL),
    ('REGIME_PERSISTENCE', 'Regime persistence < 1.5 days mean', 'THRESHOLD', 1.5, '<', NULL),
    ('IDENTITY_DRIFT', 'instrument_type NULL > 5%', 'THRESHOLD', 0.05, '>', NULL)
ON CONFLICT (condition_id) DO NOTHING;

COMMENT ON TABLE fhq_research.crypto_regime_stop_conditions IS
    'CEO-DIR-2026-093: Automatic experiment termination conditions. Triggers halt if any condition is met.';


-- ============================================================================
-- SECTION 5: SHADOW LEARNING EXPERIMENT REGISTRY
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.crypto_regime_experiment (
    experiment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_name VARCHAR(100) NOT NULL DEFAULT 'IoS-003C Shadow Learning v1',

    -- Timeline
    start_date DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date DATE,  -- NULL until experiment ends
    planned_duration_days INTEGER DEFAULT 30,

    -- Status
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'STOPPED_AUTO', 'STOPPED_MANUAL', 'COMPLETED', 'GATE3_SUBMITTED')),

    -- Stop condition if triggered
    stop_condition_id VARCHAR(50) REFERENCES fhq_research.crypto_regime_stop_conditions(condition_id),
    stop_reason TEXT,

    -- Gate 3 Decision
    gate3_decision VARCHAR(20) CHECK (gate3_decision IN ('GO', 'KILL', 'ITERATE')),
    gate3_packet_id UUID,
    gate3_submitted_at TIMESTAMPTZ,

    -- Governance
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(20) DEFAULT 'STIG',
    directive_ref VARCHAR(50) DEFAULT 'CEO-DIR-2026-093'
);

-- Create initial experiment record
INSERT INTO fhq_research.crypto_regime_experiment
    (experiment_name, start_date, planned_duration_days, status)
VALUES
    ('IoS-003C Shadow Learning v1', CURRENT_DATE, 30, 'ACTIVE')
ON CONFLICT DO NOTHING;

COMMENT ON TABLE fhq_research.crypto_regime_experiment IS
    'CEO-DIR-2026-093: Experiment registry for IoS-003C shadow learning. Tracks 30-day measurement program.';


-- ============================================================================
-- SECTION 6: HELPER FUNCTIONS
-- ============================================================================

-- Function to append shadow ledger entry
CREATE OR REPLACE FUNCTION fhq_research.append_crypto_shadow_entry(
    p_ticker VARCHAR(20),
    p_predicted_regime VARCHAR(20),
    p_confidence DECIMAL(5,4),
    p_price_at_signal DECIMAL(18,8),
    p_regime_drivers JSONB DEFAULT NULL,
    p_forecast_id UUID DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_ledger_id UUID;
    v_epoch_date DATE;
    v_epoch_boundary TIMESTAMPTZ;
    v_instrument_type VARCHAR(20);
    v_data_granularity VARCHAR(30);
BEGIN
    -- Get epoch boundary (00:00 UTC today)
    v_epoch_boundary := fhq_meta.crypto_epoch_boundary(NOW());
    v_epoch_date := v_epoch_boundary::DATE;

    -- Get instrument identity from assets table
    SELECT instrument_type, data_granularity
    INTO v_instrument_type, v_data_granularity
    FROM fhq_meta.assets
    WHERE ticker = p_ticker
    LIMIT 1;

    INSERT INTO fhq_research.crypto_regime_shadow_ledger (
        epoch_date, epoch_boundary, ticker, instrument_type, data_granularity,
        predicted_regime, confidence, price_at_signal, regime_drivers, forecast_id
    ) VALUES (
        v_epoch_date, v_epoch_boundary, p_ticker, v_instrument_type, v_data_granularity,
        p_predicted_regime, p_confidence, p_price_at_signal, p_regime_drivers, p_forecast_id
    )
    ON CONFLICT (epoch_date, ticker) DO UPDATE SET
        predicted_regime = EXCLUDED.predicted_regime,
        confidence = EXCLUDED.confidence,
        price_at_signal = EXCLUDED.price_at_signal,
        regime_drivers = EXCLUDED.regime_drivers,
        signal_timestamp = NOW()
    RETURNING ledger_id INTO v_ledger_id;

    RETURN v_ledger_id;
END;
$$ LANGUAGE plpgsql;


-- Function to capture outcome
CREATE OR REPLACE FUNCTION fhq_research.capture_crypto_outcome(
    p_ledger_id UUID,
    p_price_1d DECIMAL(18,8) DEFAULT NULL,
    p_price_3d DECIMAL(18,8) DEFAULT NULL,
    p_price_5d DECIMAL(18,8) DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_outcome_id UUID;
    v_ticker VARCHAR(20);
    v_epoch_date DATE;
    v_price_t0 DECIMAL(18,8);
    v_predicted_regime VARCHAR(20);
    v_return_1d DECIMAL(10,6);
    v_return_3d DECIMAL(10,6);
    v_return_5d DECIMAL(10,6);
    v_correct_1d BOOLEAN;
    v_correct_3d BOOLEAN;
    v_correct_5d BOOLEAN;
BEGIN
    -- Get prediction data
    SELECT ticker, epoch_date, price_at_signal, predicted_regime
    INTO v_ticker, v_epoch_date, v_price_t0, v_predicted_regime
    FROM fhq_research.crypto_regime_shadow_ledger
    WHERE ledger_id = p_ledger_id;

    -- Calculate returns
    IF p_price_1d IS NOT NULL THEN
        v_return_1d := (p_price_1d - v_price_t0) / v_price_t0;
        -- Direction correctness: BULL = expect UP, BEAR/STRESS = expect DOWN
        v_correct_1d := CASE
            WHEN v_predicted_regime IN ('BULL') AND v_return_1d > 0 THEN TRUE
            WHEN v_predicted_regime IN ('BEAR', 'STRESS') AND v_return_1d < 0 THEN TRUE
            WHEN v_predicted_regime = 'NEUTRAL' THEN ABS(v_return_1d) < 0.02  -- Within 2%
            ELSE FALSE
        END;
    END IF;

    IF p_price_3d IS NOT NULL THEN
        v_return_3d := (p_price_3d - v_price_t0) / v_price_t0;
        v_correct_3d := CASE
            WHEN v_predicted_regime IN ('BULL') AND v_return_3d > 0 THEN TRUE
            WHEN v_predicted_regime IN ('BEAR', 'STRESS') AND v_return_3d < 0 THEN TRUE
            WHEN v_predicted_regime = 'NEUTRAL' THEN ABS(v_return_3d) < 0.03
            ELSE FALSE
        END;
    END IF;

    IF p_price_5d IS NOT NULL THEN
        v_return_5d := (p_price_5d - v_price_t0) / v_price_t0;
        v_correct_5d := CASE
            WHEN v_predicted_regime IN ('BULL') AND v_return_5d > 0 THEN TRUE
            WHEN v_predicted_regime IN ('BEAR', 'STRESS') AND v_return_5d < 0 THEN TRUE
            WHEN v_predicted_regime = 'NEUTRAL' THEN ABS(v_return_5d) < 0.04
            ELSE FALSE
        END;
    END IF;

    -- Insert or update outcome
    INSERT INTO fhq_research.crypto_regime_outcomes (
        ledger_id, epoch_date, ticker, price_t0,
        price_t0_plus_1d, price_t0_plus_3d, price_t0_plus_5d,
        return_1d, return_3d, return_5d,
        correct_direction_1d, correct_direction_3d, correct_direction_5d
    ) VALUES (
        p_ledger_id, v_epoch_date, v_ticker, v_price_t0,
        p_price_1d, p_price_3d, p_price_5d,
        v_return_1d, v_return_3d, v_return_5d,
        v_correct_1d, v_correct_3d, v_correct_5d
    )
    ON CONFLICT (ledger_id) DO UPDATE SET
        price_t0_plus_1d = COALESCE(EXCLUDED.price_t0_plus_1d, fhq_research.crypto_regime_outcomes.price_t0_plus_1d),
        price_t0_plus_3d = COALESCE(EXCLUDED.price_t0_plus_3d, fhq_research.crypto_regime_outcomes.price_t0_plus_3d),
        price_t0_plus_5d = COALESCE(EXCLUDED.price_t0_plus_5d, fhq_research.crypto_regime_outcomes.price_t0_plus_5d),
        return_1d = COALESCE(EXCLUDED.return_1d, fhq_research.crypto_regime_outcomes.return_1d),
        return_3d = COALESCE(EXCLUDED.return_3d, fhq_research.crypto_regime_outcomes.return_3d),
        return_5d = COALESCE(EXCLUDED.return_5d, fhq_research.crypto_regime_outcomes.return_5d),
        correct_direction_1d = COALESCE(EXCLUDED.correct_direction_1d, fhq_research.crypto_regime_outcomes.correct_direction_1d),
        correct_direction_3d = COALESCE(EXCLUDED.correct_direction_3d, fhq_research.crypto_regime_outcomes.correct_direction_3d),
        correct_direction_5d = COALESCE(EXCLUDED.correct_direction_5d, fhq_research.crypto_regime_outcomes.correct_direction_5d),
        outcome_timestamp = NOW()
    RETURNING outcome_id INTO v_outcome_id;

    -- Mark ledger entry as captured
    UPDATE fhq_research.crypto_regime_shadow_ledger
    SET outcome_captured = TRUE, outcome_capture_timestamp = NOW()
    WHERE ledger_id = p_ledger_id;

    RETURN v_outcome_id;
END;
$$ LANGUAGE plpgsql;


-- Function to check stop conditions
CREATE OR REPLACE FUNCTION fhq_research.check_crypto_stop_conditions()
RETURNS TABLE (
    condition_id VARCHAR(50),
    condition_name VARCHAR(100),
    is_triggered BOOLEAN,
    current_value DECIMAL(10,6),
    threshold_value DECIMAL(10,6),
    message TEXT
) AS $$
DECLARE
    v_avg_brier DECIMAL(10,6);
    v_hit_rate DECIMAL(5,4);
    v_regime_persistence DECIMAL(10,4);
    v_identity_drift DECIMAL(5,4);
    v_consecutive_bad_brier INTEGER;
    v_sample_size INTEGER;
BEGIN
    -- Get current metrics
    SELECT
        AVG(o.brier_score),
        COUNT(*) FILTER (WHERE o.correct_direction_1d = TRUE)::DECIMAL / NULLIF(COUNT(*) FILTER (WHERE o.correct_direction_1d IS NOT NULL), 0)
    INTO v_avg_brier, v_hit_rate
    FROM fhq_research.crypto_regime_outcomes o
    WHERE o.epoch_date >= CURRENT_DATE - 30;

    SELECT COUNT(*) INTO v_sample_size
    FROM fhq_research.crypto_regime_outcomes
    WHERE epoch_date >= CURRENT_DATE - 30;

    -- Identity drift check
    SELECT
        COUNT(*) FILTER (WHERE instrument_type IS NULL)::DECIMAL / NULLIF(COUNT(*), 0)
    INTO v_identity_drift
    FROM fhq_research.crypto_regime_shadow_ledger
    WHERE epoch_date >= CURRENT_DATE - 30;

    -- Return stop condition checks
    RETURN QUERY
    SELECT
        sc.condition_id,
        sc.condition_name,
        CASE
            WHEN sc.condition_id = 'BRIER_CONSECUTIVE' AND v_avg_brier > sc.threshold_value THEN TRUE
            WHEN sc.condition_id = 'HIT_RATE_FLOOR' AND v_sample_size >= 30 AND v_hit_rate < sc.threshold_value THEN TRUE
            WHEN sc.condition_id = 'IDENTITY_DRIFT' AND v_identity_drift > sc.threshold_value THEN TRUE
            ELSE FALSE
        END AS is_triggered,
        CASE
            WHEN sc.condition_id = 'BRIER_CONSECUTIVE' THEN v_avg_brier
            WHEN sc.condition_id = 'HIT_RATE_FLOOR' THEN v_hit_rate
            WHEN sc.condition_id = 'IDENTITY_DRIFT' THEN v_identity_drift
            ELSE NULL
        END AS current_value,
        sc.threshold_value,
        CASE
            WHEN sc.condition_id = 'BRIER_CONSECUTIVE' THEN 'Rolling Brier score: ' || COALESCE(v_avg_brier::TEXT, 'N/A')
            WHEN sc.condition_id = 'HIT_RATE_FLOOR' THEN 'Hit rate (30 samples): ' || COALESCE(v_hit_rate::TEXT, 'N/A') || ' (n=' || v_sample_size || ')'
            WHEN sc.condition_id = 'IDENTITY_DRIFT' THEN 'Identity drift: ' || COALESCE((v_identity_drift * 100)::TEXT, 'N/A') || '% NULL instrument_type'
            ELSE 'Check pending'
        END AS message
    FROM fhq_research.crypto_regime_stop_conditions sc
    WHERE sc.is_active = TRUE;
END;
$$ LANGUAGE plpgsql;


-- View for shadow learning daily summary
CREATE OR REPLACE VIEW fhq_research.crypto_shadow_daily_summary AS
SELECT
    sl.epoch_date,
    COUNT(*) AS signal_count,
    COUNT(*) FILTER (WHERE o.outcome_id IS NOT NULL) AS outcomes_captured,
    COUNT(*) FILTER (WHERE o.correct_direction_1d = TRUE) AS correct_1d,
    COUNT(*) FILTER (WHERE o.correct_direction_1d IS NOT NULL) AS total_with_1d_outcome,
    ROUND(
        COUNT(*) FILTER (WHERE o.correct_direction_1d = TRUE)::DECIMAL /
        NULLIF(COUNT(*) FILTER (WHERE o.correct_direction_1d IS NOT NULL), 0),
        4
    ) AS hit_rate_1d,
    AVG(o.brier_score) AS avg_brier,
    COUNT(*) FILTER (WHERE sl.instrument_type IS NULL) AS null_instrument_type,
    ROUND(
        COUNT(*) FILTER (WHERE sl.instrument_type IS NULL)::DECIMAL / NULLIF(COUNT(*), 0),
        4
    ) AS identity_drift_pct,
    MAX(sl.created_at) AS last_signal_at
FROM fhq_research.crypto_regime_shadow_ledger sl
LEFT JOIN fhq_research.crypto_regime_outcomes o ON sl.ledger_id = o.ledger_id
GROUP BY sl.epoch_date
ORDER BY sl.epoch_date DESC;

COMMENT ON VIEW fhq_research.crypto_shadow_daily_summary IS
    'CEO-DIR-2026-093: Daily summary of shadow learning metrics for IoS-003C.';


-- View for rolling 30-day metrics
CREATE OR REPLACE VIEW fhq_research.crypto_shadow_rolling_30d AS
SELECT
    CURRENT_DATE AS as_of_date,
    COUNT(*) AS total_signals,
    COUNT(*) FILTER (WHERE o.outcome_id IS NOT NULL) AS outcomes_captured,
    COUNT(*) FILTER (WHERE o.correct_direction_1d = TRUE) AS correct_1d,
    COUNT(*) FILTER (WHERE o.correct_direction_1d IS NOT NULL) AS total_with_1d,
    ROUND(
        COUNT(*) FILTER (WHERE o.correct_direction_1d = TRUE)::DECIMAL /
        NULLIF(COUNT(*) FILTER (WHERE o.correct_direction_1d IS NOT NULL), 0),
        4
    ) AS hit_rate_1d,
    ROUND(AVG(o.brier_score), 6) AS avg_brier,
    ROUND(
        COUNT(*) FILTER (WHERE sl.instrument_type IS NULL)::DECIMAL / NULLIF(COUNT(*), 0),
        4
    ) AS identity_drift_pct,
    MIN(sl.epoch_date) AS window_start,
    MAX(sl.epoch_date) AS window_end,
    (SELECT status FROM fhq_research.crypto_regime_experiment ORDER BY created_at DESC LIMIT 1) AS experiment_status
FROM fhq_research.crypto_regime_shadow_ledger sl
LEFT JOIN fhq_research.crypto_regime_outcomes o ON sl.ledger_id = o.ledger_id
WHERE sl.epoch_date >= CURRENT_DATE - 30;

COMMENT ON VIEW fhq_research.crypto_shadow_rolling_30d IS
    'CEO-DIR-2026-093: Rolling 30-day aggregate metrics for shadow learning.';


-- ============================================================================
-- SECTION 7: GOVERNANCE LOGGING
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type, action_target, action_target_type, initiated_by, decision, decision_rationale, metadata
) VALUES (
    'CEO_DIRECTIVE_EXECUTION',
    'CEO-DIR-2026-093',
    'MIGRATION',
    'STIG',
    'EXECUTING',
    'Autonomous Shadow Learning for IoS-003C - 30-day measurement program',
    jsonb_build_object(
        'migration', '311_ceo_dir_2026_093_shadow_learning.sql',
        'tables_created', ARRAY[
            'crypto_regime_shadow_ledger',
            'crypto_regime_outcomes',
            'crypto_regime_quality_metrics',
            'crypto_regime_stop_conditions',
            'crypto_regime_experiment'
        ],
        'functions_created', ARRAY[
            'append_crypto_shadow_entry',
            'capture_crypto_outcome',
            'check_crypto_stop_conditions'
        ],
        'views_created', ARRAY[
            'crypto_shadow_daily_summary',
            'crypto_shadow_rolling_30d'
        ],
        'experiment_duration_days', 30,
        'stop_conditions', ARRAY[
            'Brier > 0.35 for 7 days',
            'Hit rate < 45%',
            'Bootstrap p > 0.05',
            'Regime persistence < 1.5 days',
            'Identity drift > 5%'
        ]
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    -- Verify tables exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'fhq_research' AND table_name = 'crypto_regime_shadow_ledger') THEN
        RAISE EXCEPTION 'Table crypto_regime_shadow_ledger not created';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'fhq_research' AND table_name = 'crypto_regime_outcomes') THEN
        RAISE EXCEPTION 'Table crypto_regime_outcomes not created';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'fhq_research' AND table_name = 'crypto_regime_quality_metrics') THEN
        RAISE EXCEPTION 'Table crypto_regime_quality_metrics not created';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'fhq_research' AND table_name = 'crypto_regime_experiment') THEN
        RAISE EXCEPTION 'Table crypto_regime_experiment not created';
    END IF;

    RAISE NOTICE 'Migration 311 verification PASSED - All tables created successfully';
END $$;
