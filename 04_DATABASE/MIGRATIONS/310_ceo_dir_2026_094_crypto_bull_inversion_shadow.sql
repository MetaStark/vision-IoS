-- =============================================================================
-- CEO-DIR-2026-094: CRYPTO BULL 99%+ INVERSION — CANONICAL SHADOW LEARNING
-- =============================================================================
--
-- Authority: CEO
-- Priority: P0
-- Status: ACTIVE
-- Scope: CRYPTO only · BULL regime · confidence >= 0.99 · inversion logic
-- Mode: SHADOW-ONLY (No execution, no capital, no simulation)
--
-- HARD DEPENDENCY: Migration 309 (instrument_type must exist and be NOT NULL)
--
-- Strategic Intent: Extract potential alpha pocket from statistically catastrophic
-- population by isolating it under same discipline as EQUITY STRESS inversion.
-- Goal is FAST FALSIFICATION OR CONFIRMATION, not optimism.
-- =============================================================================

BEGIN;

-- =============================================================================
-- PRE-FLIGHT: VERIFY MIGRATION 309 DEPENDENCY
-- =============================================================================

DO $$
DECLARE
    col_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_meta'
        AND table_name = 'assets'
        AND column_name = 'instrument_type'
    ) INTO col_exists;

    IF NOT col_exists THEN
        RAISE EXCEPTION 'HARD DEPENDENCY FAILED: Migration 309 must be executed first. instrument_type column not found in fhq_meta.assets';
    END IF;
END$$;

-- =============================================================================
-- SECTION 1: CREATE CRYPTO BULL INVERSION SHADOW LEDGER
-- =============================================================================
-- CRITICAL: This is a SEPARATE ledger from stress_inversion_shadow per ADR-013
-- Scope separation is mandatory.

CREATE TABLE IF NOT EXISTS fhq_alpha.crypto_bull_inversion_shadow (
    inversion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Original forecast reference
    original_score_id UUID NOT NULL,
    original_regime TEXT NOT NULL CHECK (original_regime = 'BULL'),
    original_confidence NUMERIC NOT NULL CHECK (original_confidence >= 0.99),
    original_direction TEXT NOT NULL CHECK (original_direction IN ('UP', 'DOWN')),

    -- Inverted signal
    inverted_direction TEXT NOT NULL CHECK (inverted_direction IN ('UP', 'DOWN')),
    inverted_confidence NUMERIC NOT NULL,

    -- Identity (HARD CONSTRAINT per CEO-DIR-2026-094 Section 2.1)
    asset_id TEXT NOT NULL,
    asset_class TEXT NOT NULL CHECK (asset_class = 'CRYPTO'),
    instrument_type TEXT NOT NULL CHECK (instrument_type IN ('SPOT', 'PERP')),

    -- Temporal anchoring (Crypto epoch boundary = 00:00 UTC)
    forecast_timestamp TIMESTAMPTZ NOT NULL,
    epoch_date DATE NOT NULL,  -- Derived from forecast_timestamp, anchored to 00:00 UTC

    -- Multi-horizon outcome tracking (1D/3D/5D)
    outcome_1d BOOLEAN,  -- TRUE = market went UP within 1 day
    outcome_3d BOOLEAN,  -- TRUE = market went UP within 3 days
    outcome_5d BOOLEAN,  -- TRUE = market went UP within 5 days
    outcome_1d_timestamp TIMESTAMPTZ,
    outcome_3d_timestamp TIMESTAMPTZ,
    outcome_5d_timestamp TIMESTAMPTZ,

    -- Scoring per horizon
    original_brier_1d NUMERIC,
    inverted_brier_1d NUMERIC,
    original_brier_3d NUMERIC,
    inverted_brier_3d NUMERIC,
    original_brier_5d NUMERIC,
    inverted_brier_5d NUMERIC,

    -- Brier improvement (computed)
    brier_improvement_1d NUMERIC GENERATED ALWAYS AS (original_brier_1d - inverted_brier_1d) STORED,
    brier_improvement_3d NUMERIC GENERATED ALWAYS AS (original_brier_3d - inverted_brier_3d) STORED,
    brier_improvement_5d NUMERIC GENERATED ALWAYS AS (original_brier_5d - inverted_brier_5d) STORED,

    -- ROI Attribution: Synthetic Options Payoff Proxy (CEO-DIR-2026-079)
    synthetic_payoff_1d NUMERIC,  -- Expected value proxy, not just statistical skill
    synthetic_payoff_3d NUMERIC,
    synthetic_payoff_5d NUMERIC,

    -- Price data for ROI calculation
    entry_price NUMERIC,
    exit_price_1d NUMERIC,
    exit_price_3d NUMERIC,
    exit_price_5d NUMERIC,
    price_change_pct_1d NUMERIC,
    price_change_pct_3d NUMERIC,
    price_change_pct_5d NUMERIC,

    -- Metadata
    inversion_rule TEXT NOT NULL DEFAULT 'CRYPTO_BULL_99PCT_INVERSION',
    shadow_session_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    evaluated_at_1d TIMESTAMPTZ,
    evaluated_at_3d TIMESTAMPTZ,
    evaluated_at_5d TIMESTAMPTZ,

    -- Data quality tracking
    data_completeness_score NUMERIC,  -- 0-1, based on price data availability
    identity_drift_flag BOOLEAN DEFAULT FALSE  -- Should be structurally zero post-309
);

-- =============================================================================
-- SECTION 2: CREATE INDEXES FOR PERFORMANCE
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_crypto_bull_inv_session
ON fhq_alpha.crypto_bull_inversion_shadow(shadow_session_id);

CREATE INDEX IF NOT EXISTS idx_crypto_bull_inv_epoch
ON fhq_alpha.crypto_bull_inversion_shadow(epoch_date);

CREATE INDEX IF NOT EXISTS idx_crypto_bull_inv_instrument
ON fhq_alpha.crypto_bull_inversion_shadow(instrument_type);

CREATE INDEX IF NOT EXISTS idx_crypto_bull_inv_outcome_1d
ON fhq_alpha.crypto_bull_inversion_shadow(outcome_1d)
WHERE outcome_1d IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_crypto_bull_inv_asset
ON fhq_alpha.crypto_bull_inversion_shadow(asset_id);

-- =============================================================================
-- SECTION 3: CREATE SHADOW SESSION FOR CRYPTO BULL INVERSION
-- =============================================================================

INSERT INTO fhq_calendar.shadow_mode_sessions (
    session_id,
    session_name,
    started_at,
    planned_end_at,
    status,
    initiated_by,
    determinism_checks,
    determinism_failures,
    drift_detected,
    metadata
) VALUES (
    'b2c3d4e5-f6a7-8901-bcde-f23456789012'::uuid,
    'CRYPTO_BULL_INVERSION_30D_TEST',
    NOW(),
    NOW() + INTERVAL '30 days',
    'ACTIVE',
    'STIG',
    0,
    0,
    FALSE,
    jsonb_build_object(
        'session_type', 'SIGNAL_INVERSION',
        'directive', 'CEO-DIR-2026-094',
        'target_asset_class', 'CRYPTO',
        'target_regime', 'BULL',
        'confidence_threshold', 0.99,
        'inversion_rule', 'BET_AGAINST',
        'horizons', ARRAY['1D', '3D', '5D'],
        'expected_inverse_hit_rate', 0.8836,
        'hard_dependency', 'MIGRATION_309_INSTRUMENT_IDENTITY',
        'authorized_by', 'CEO',
        'authorized_at', NOW(),
        'trading_authority', 'NONE'
    )
) ON CONFLICT (session_id) DO NOTHING;

-- =============================================================================
-- SECTION 4: CREATE QUALITY METRICS VIEW (Day 0 Measurement Package)
-- =============================================================================

CREATE OR REPLACE VIEW fhq_alpha.v_crypto_bull_inversion_performance AS
SELECT
    shadow_session_id,
    inversion_rule,
    instrument_type,

    -- Sample sizes
    COUNT(*) as total_eligible,
    COUNT(CASE WHEN outcome_1d IS NOT NULL THEN 1 END) as evaluated_1d,
    COUNT(CASE WHEN outcome_3d IS NOT NULL THEN 1 END) as evaluated_3d,
    COUNT(CASE WHEN outcome_5d IS NOT NULL THEN 1 END) as evaluated_5d,

    -- 1D Horizon Performance
    ROUND(AVG(original_brier_1d)::numeric, 4) as avg_original_brier_1d,
    ROUND(AVG(inverted_brier_1d)::numeric, 4) as avg_inverted_brier_1d,
    ROUND(100.0 * SUM(CASE WHEN outcome_1d = FALSE AND inverted_direction = 'DOWN' THEN 1
                           WHEN outcome_1d = TRUE AND inverted_direction = 'UP' THEN 1
                           ELSE 0 END) / NULLIF(COUNT(CASE WHEN outcome_1d IS NOT NULL THEN 1 END), 0)::numeric, 2) as inverted_hit_rate_1d_pct,

    -- 3D Horizon Performance
    ROUND(AVG(original_brier_3d)::numeric, 4) as avg_original_brier_3d,
    ROUND(AVG(inverted_brier_3d)::numeric, 4) as avg_inverted_brier_3d,
    ROUND(100.0 * SUM(CASE WHEN outcome_3d = FALSE AND inverted_direction = 'DOWN' THEN 1
                           WHEN outcome_3d = TRUE AND inverted_direction = 'UP' THEN 1
                           ELSE 0 END) / NULLIF(COUNT(CASE WHEN outcome_3d IS NOT NULL THEN 1 END), 0)::numeric, 2) as inverted_hit_rate_3d_pct,

    -- 5D Horizon Performance
    ROUND(AVG(original_brier_5d)::numeric, 4) as avg_original_brier_5d,
    ROUND(AVG(inverted_brier_5d)::numeric, 4) as avg_inverted_brier_5d,
    ROUND(100.0 * SUM(CASE WHEN outcome_5d = FALSE AND inverted_direction = 'DOWN' THEN 1
                           WHEN outcome_5d = TRUE AND inverted_direction = 'UP' THEN 1
                           ELSE 0 END) / NULLIF(COUNT(CASE WHEN outcome_5d IS NOT NULL THEN 1 END), 0)::numeric, 2) as inverted_hit_rate_5d_pct,

    -- Brier improvement
    ROUND(AVG(brier_improvement_1d)::numeric, 4) as avg_brier_improvement_1d,
    ROUND(AVG(brier_improvement_3d)::numeric, 4) as avg_brier_improvement_3d,
    ROUND(AVG(brier_improvement_5d)::numeric, 4) as avg_brier_improvement_5d,

    -- ROI Attribution: Synthetic Payoff (CEO-DIR-2026-079)
    ROUND(AVG(synthetic_payoff_1d)::numeric, 4) as avg_synthetic_payoff_1d,
    ROUND(AVG(synthetic_payoff_3d)::numeric, 4) as avg_synthetic_payoff_3d,
    ROUND(AVG(synthetic_payoff_5d)::numeric, 4) as avg_synthetic_payoff_5d,
    ROUND(SUM(synthetic_payoff_1d)::numeric, 2) as total_synthetic_payoff_1d,

    -- Data quality
    ROUND(AVG(data_completeness_score)::numeric, 4) as avg_data_completeness,
    SUM(CASE WHEN identity_drift_flag THEN 1 ELSE 0 END) as identity_drift_count,

    -- Target compliance (Brier < 0.10)
    COUNT(CASE WHEN inverted_brier_1d < 0.10 THEN 1 END) as signals_under_target_1d,
    ROUND(100.0 * COUNT(CASE WHEN inverted_brier_1d < 0.10 THEN 1 END) / NULLIF(COUNT(CASE WHEN outcome_1d IS NOT NULL THEN 1 END), 0)::numeric, 2) as pct_under_target_1d

FROM fhq_alpha.crypto_bull_inversion_shadow
WHERE outcome_1d IS NOT NULL OR outcome_3d IS NOT NULL OR outcome_5d IS NOT NULL
GROUP BY shadow_session_id, inversion_rule, instrument_type;

-- =============================================================================
-- SECTION 5: STOP CONDITIONS TABLE (Experiment-Local Only per CEO-DIR-2026-094 S7)
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.crypto_bull_inversion_stop_conditions (
    condition_id TEXT PRIMARY KEY,
    condition_name TEXT NOT NULL,
    condition_type TEXT NOT NULL CHECK (condition_type IN ('THRESHOLD', 'DURATION', 'STATISTICAL')),
    threshold_value NUMERIC,
    threshold_operator TEXT CHECK (threshold_operator IN ('>', '<', '>=', '<=', '=')),
    duration_days INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_triggered BOOLEAN NOT NULL DEFAULT FALSE,
    triggered_at TIMESTAMPTZ,
    triggered_value NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL
);

-- Insert stop conditions per CEO-DIR-2026-094 Section 7
INSERT INTO fhq_alpha.crypto_bull_inversion_stop_conditions
    (condition_id, condition_name, condition_type, threshold_value, threshold_operator, duration_days, created_by)
VALUES
    ('BRIER_DETERIORATION', 'Brier deterioration > baseline + 0.05', 'THRESHOLD', 0.05, '>', NULL, 'CEO-DIR-2026-094'),
    ('HIT_RATE_FLOOR', 'Inverted hit rate < 60% over 50 samples', 'THRESHOLD', 0.60, '<', NULL, 'CEO-DIR-2026-094'),
    ('BOOTSTRAP_P_VALUE', 'Bootstrap p-value > 0.05 (not significant)', 'STATISTICAL', 0.05, '>', NULL, 'CEO-DIR-2026-094'),
    ('REGIME_PERSISTENCE', 'Regime persistence collapse < 1 day mean', 'THRESHOLD', 1.0, '<', NULL, 'CEO-DIR-2026-094'),
    ('IDENTITY_DRIFT', 'Identity drift > 0% (any NULL instrument_type)', 'THRESHOLD', 0.00, '>', NULL, 'CEO-DIR-2026-094')
ON CONFLICT (condition_id) DO NOTHING;

-- =============================================================================
-- SECTION 6: SCHEDULED TASKS REGISTRATION (per CEO-DIR-2026-094 S6)
-- =============================================================================

-- Task 1: Daily epoch snapshot (00:05 UTC)
INSERT INTO fhq_execution.task_registry (
    task_id, task_name, gate_level, owned_by, executed_by, enabled,
    schedule_cron, run_count, error_count, config, created_at
) VALUES (
    gen_random_uuid(),
    'crypto_bull_inversion_epoch_snapshot',
    'G2',
    'STIG',
    'WINDOWS_SCHEDULER',
    true,
    '5 0 * * *',
    0,
    0,
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-094',
        'description', 'Daily epoch snapshot at 00:05 UTC - captures new CRYPTO BULL 99%+ forecasts',
        'target_table', 'fhq_alpha.crypto_bull_inversion_shadow'
    ),
    NOW()
) ON CONFLICT DO NOTHING;

-- Task 2: Daily outcome computation + metrics (04:00 UTC)
INSERT INTO fhq_execution.task_registry (
    task_id, task_name, gate_level, owned_by, executed_by, enabled,
    schedule_cron, run_count, error_count, config, created_at
) VALUES (
    gen_random_uuid(),
    'crypto_bull_inversion_outcome_compute',
    'G2',
    'STIG',
    'WINDOWS_SCHEDULER',
    true,
    '0 4 * * *',
    0,
    0,
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-094',
        'description', 'Daily outcome computation + metrics at 04:00 UTC',
        'horizons', ARRAY['1D', '3D', '5D'],
        'target_view', 'fhq_alpha.v_crypto_bull_inversion_performance'
    ),
    NOW()
) ON CONFLICT DO NOTHING;

-- Task 3: Weekly bootstrap + VEGA attestation (Sunday 00:00 UTC)
INSERT INTO fhq_execution.task_registry (
    task_id, task_name, gate_level, owned_by, executed_by, enabled,
    schedule_cron, run_count, error_count, config, created_at
) VALUES (
    gen_random_uuid(),
    'crypto_bull_inversion_weekly_bootstrap',
    'G3',
    'VEGA',
    'WINDOWS_SCHEDULER',
    true,
    '0 0 * * 0',
    0,
    0,
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-094',
        'description', 'Weekly bootstrap significance test + VEGA attestation (Sunday 00:00 UTC)',
        'requires_attestation', true,
        'min_sample_size', 30
    ),
    NOW()
) ON CONFLICT DO NOTHING;

-- Task 4: Daily Gate-eligibility check (04:30 UTC)
INSERT INTO fhq_execution.task_registry (
    task_id, task_name, gate_level, owned_by, executed_by, enabled,
    schedule_cron, run_count, error_count, config, created_at
) VALUES (
    gen_random_uuid(),
    'crypto_bull_inversion_gate_check',
    'G2',
    'STIG',
    'WINDOWS_SCHEDULER',
    true,
    '30 4 * * *',
    0,
    0,
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-094',
        'description', 'Daily Gate-eligibility check at 04:30 UTC - evaluates stop conditions',
        'stop_conditions_table', 'fhq_alpha.crypto_bull_inversion_stop_conditions'
    ),
    NOW()
) ON CONFLICT DO NOTHING;

-- =============================================================================
-- SECTION 7: POPULATE HISTORICAL DATA (Deterministic Inclusion Rule)
-- =============================================================================
-- Only include records where instrument_type can be verified via fhq_meta.assets

INSERT INTO fhq_alpha.crypto_bull_inversion_shadow (
    original_score_id,
    original_regime,
    original_confidence,
    original_direction,
    inverted_direction,
    inverted_confidence,
    asset_id,
    asset_class,
    instrument_type,
    forecast_timestamp,
    epoch_date,
    outcome_1d,
    outcome_1d_timestamp,
    original_brier_1d,
    inverted_brier_1d,
    entry_price,
    inversion_rule,
    shadow_session_id,
    evaluated_at_1d,
    data_completeness_score
)
SELECT
    bsl.score_id,
    bsl.regime,
    bsl.forecast_probability,
    CASE WHEN bsl.forecast_probability > 0.5 THEN 'UP' ELSE 'DOWN' END,
    -- INVERT: If original predicted UP with 99%, inverted predicts DOWN
    CASE WHEN bsl.forecast_probability > 0.5 THEN 'DOWN' ELSE 'UP' END,
    bsl.forecast_probability,
    bsl.asset_id,
    bsl.asset_class,
    COALESCE(a.instrument_type, 'SPOT'),  -- Default to SPOT if not found (all current CRYPTO is SPOT)
    bsl.forecast_timestamp,
    DATE(bsl.forecast_timestamp AT TIME ZONE 'UTC'),  -- Epoch date anchored to 00:00 UTC
    bsl.actual_outcome,
    bsl.outcome_timestamp,
    bsl.squared_error,
    -- Inverted Brier: If original was wrong, inverted is right
    CASE
        WHEN bsl.actual_outcome = FALSE AND bsl.forecast_probability >= 0.99
        THEN POWER(1 - bsl.forecast_probability, 2)
        WHEN bsl.actual_outcome = TRUE AND bsl.forecast_probability >= 0.99
        THEN POWER(bsl.forecast_probability, 2)
        ELSE bsl.squared_error
    END,
    NULL,  -- entry_price to be populated by outcome daemon
    'CRYPTO_BULL_99PCT_INVERSION',
    'b2c3d4e5-f6a7-8901-bcde-f23456789012'::uuid,
    NOW(),
    1.0  -- Full completeness for historical data with outcomes
FROM fhq_governance.brier_score_ledger bsl
LEFT JOIN fhq_meta.assets a ON bsl.asset_id = a.canonical_id
WHERE bsl.asset_class = 'CRYPTO'
  AND bsl.regime = 'BULL'
  AND bsl.forecast_probability >= 0.99
  AND bsl.actual_outcome IS NOT NULL
  AND COALESCE(a.instrument_type, 'SPOT') IN ('SPOT', 'PERP');

-- =============================================================================
-- SECTION 8: GOVERNANCE LOGGING
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
    metadata
) VALUES (
    gen_random_uuid(),
    'CRYPTO_BULL_INVERSION_SHADOW_ACTIVATED',
    'fhq_alpha.crypto_bull_inversion_shadow',
    'SHADOW_TEST',
    'CEO',
    NOW(),
    'APPROVED',
    'CEO-DIR-2026-094: Authorized CRYPTO BULL 99%+ inversion shadow test (30 days). Based on 88.36% inverse hit rate finding. Hard dependency on Migration 309 (instrument_type). Goal: Fast falsification or confirmation, not optimism.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-094',
        'migration', '310_ceo_dir_2026_094_crypto_bull_inversion_shadow.sql',
        'target_population', 318,
        'expected_inverse_hit_rate', 0.8836,
        'hard_dependency', 'MIGRATION_309_INSTRUMENT_IDENTITY',
        'horizons', ARRAY['1D', '3D', '5D'],
        'mode', 'SHADOW_ONLY',
        'trading_authority', 'NONE',
        'executed_at', NOW()
    )
);

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES (Run after migration)
-- =============================================================================

-- SELECT COUNT(*) as total_records FROM fhq_alpha.crypto_bull_inversion_shadow;
-- SELECT * FROM fhq_alpha.v_crypto_bull_inversion_performance;
-- SELECT * FROM fhq_alpha.crypto_bull_inversion_stop_conditions;
-- SELECT task_name, schedule_cron, enabled FROM fhq_execution.task_registry WHERE task_name LIKE 'crypto_bull%';
