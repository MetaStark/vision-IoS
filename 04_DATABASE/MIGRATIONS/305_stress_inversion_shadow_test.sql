-- Migration 305: STRESS Signal Inversion Shadow Test
-- Directive: CEO-DIR-2026-075 Order 1
-- Authorization: CEO authorized STRESS inversion shadow test (48h)
-- Date: 2026-01-17
-- Author: STIG
-- Mode: SHADOW_TEST (no production impact)

-- ============================================================================
-- CRITICAL DISCOVERY: STRESS 99%+ predictions are 100% WRONG
-- IMPLICATION: Inverting them yields 100% hit rate, Brier 0.0058
-- THIS IS THE ALPHA SIGNAL
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Create Inverted Signal Tracking Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.stress_inversion_shadow (
    inversion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Original forecast reference
    original_score_id UUID NOT NULL,
    original_regime TEXT NOT NULL,
    original_confidence NUMERIC NOT NULL,
    original_direction TEXT NOT NULL,  -- 'UP' or 'DOWN'

    -- Inverted signal
    inverted_direction TEXT NOT NULL,  -- Opposite of original
    inverted_confidence NUMERIC NOT NULL,  -- Same magnitude, inverted meaning

    -- Tracking
    asset_id TEXT NOT NULL,
    asset_class TEXT,
    forecast_timestamp TIMESTAMPTZ NOT NULL,

    -- Outcome (filled when known)
    actual_outcome BOOLEAN,  -- TRUE = market went UP
    outcome_timestamp TIMESTAMPTZ,

    -- Scoring
    original_brier NUMERIC,
    inverted_brier NUMERIC,
    brier_improvement NUMERIC GENERATED ALWAYS AS (original_brier - inverted_brier) STORED,

    -- Metadata
    inversion_rule TEXT NOT NULL DEFAULT 'STRESS_99PCT_INVERSION',
    shadow_session_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    evaluated_at TIMESTAMPTZ
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_stress_inversion_shadow_session
ON fhq_alpha.stress_inversion_shadow(shadow_session_id);

CREATE INDEX IF NOT EXISTS idx_stress_inversion_shadow_outcome
ON fhq_alpha.stress_inversion_shadow(actual_outcome)
WHERE actual_outcome IS NOT NULL;

-- ============================================================================
-- SECTION 2: Create Shadow Session for 48h Test
-- ============================================================================

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
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890'::uuid,
    'STRESS_INVERSION_48H_TEST',
    NOW(),
    NOW() + INTERVAL '48 hours',
    'ACTIVE',
    'STIG',
    0,
    0,
    FALSE,
    jsonb_build_object(
        'session_type', 'SIGNAL_INVERSION',
        'directive', 'CEO-DIR-2026-075',
        'target_regime', 'STRESS',
        'confidence_threshold', 0.99,
        'inversion_rule', 'BET_AGAINST',
        'expected_inverse_hit_rate', 1.00,
        'expected_inverse_brier', 0.0058,
        'authorized_by', 'CEO',
        'authorized_at', NOW()
    )
) ON CONFLICT (session_id) DO NOTHING;

-- ============================================================================
-- SECTION 3: Populate Initial Inverted Signals from Historical Data
-- ============================================================================

-- Insert historical STRESS 99%+ forecasts with inverted signals
INSERT INTO fhq_alpha.stress_inversion_shadow (
    original_score_id,
    original_regime,
    original_confidence,
    original_direction,
    inverted_direction,
    inverted_confidence,
    asset_id,
    asset_class,
    forecast_timestamp,
    actual_outcome,
    outcome_timestamp,
    original_brier,
    inverted_brier,
    inversion_rule,
    shadow_session_id,
    evaluated_at
)
SELECT
    score_id,
    regime,
    forecast_probability,
    CASE WHEN forecast_probability > 0.5 THEN 'UP' ELSE 'DOWN' END,
    -- INVERT: If original predicted UP with 99%, inverted predicts DOWN with 99%
    CASE WHEN forecast_probability > 0.5 THEN 'DOWN' ELSE 'UP' END,
    forecast_probability,  -- Same confidence, inverted direction
    asset_id,
    asset_class,
    forecast_timestamp,
    actual_outcome,
    outcome_timestamp,
    squared_error as original_brier,
    -- Inverted Brier: If original was wrong (squared_error high), inverted is right (squared_error low)
    -- Brier for inverted = (1 - original_probability - actual)^2 when actual=0
    -- Simplified: If original was 0.99 UP and market went DOWN (actual=FALSE),
    -- inverted 0.99 DOWN would have Brier = (0.99 - 0)^2 = 0.0001
    CASE
        WHEN actual_outcome = FALSE AND forecast_probability >= 0.99
        THEN POWER(1 - forecast_probability, 2)  -- Near-perfect inverse
        WHEN actual_outcome = TRUE AND forecast_probability >= 0.99
        THEN POWER(forecast_probability, 2)  -- Would have been wrong if inverted
        ELSE squared_error  -- Fallback
    END as inverted_brier,
    'STRESS_99PCT_INVERSION',
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890'::uuid,
    NOW()
FROM fhq_governance.brier_score_ledger
WHERE regime = 'STRESS'
  AND forecast_probability >= 0.99;

-- ============================================================================
-- SECTION 4: Create Inversion Performance View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_alpha.v_stress_inversion_performance AS
SELECT
    shadow_session_id,
    inversion_rule,
    COUNT(*) as total_signals,

    -- Original performance
    ROUND(AVG(original_brier)::numeric, 4) as avg_original_brier,
    ROUND(100.0 * SUM(CASE WHEN actual_outcome AND original_direction = 'UP' THEN 1
                           WHEN NOT actual_outcome AND original_direction = 'DOWN' THEN 1
                           ELSE 0 END) / NULLIF(COUNT(*), 0)::numeric, 2) as original_hit_rate_pct,

    -- Inverted performance
    ROUND(AVG(inverted_brier)::numeric, 4) as avg_inverted_brier,
    ROUND(100.0 * SUM(CASE WHEN actual_outcome AND inverted_direction = 'UP' THEN 1
                           WHEN NOT actual_outcome AND inverted_direction = 'DOWN' THEN 1
                           ELSE 0 END) / NULLIF(COUNT(*), 0)::numeric, 2) as inverted_hit_rate_pct,

    -- Improvement
    ROUND(AVG(brier_improvement)::numeric, 4) as avg_brier_improvement,

    -- Target compliance
    COUNT(CASE WHEN inverted_brier < 0.10 THEN 1 END) as signals_under_target,
    ROUND(100.0 * COUNT(CASE WHEN inverted_brier < 0.10 THEN 1 END) / NULLIF(COUNT(*), 0)::numeric, 2) as pct_under_target

FROM fhq_alpha.stress_inversion_shadow
WHERE actual_outcome IS NOT NULL
GROUP BY shadow_session_id, inversion_rule;

-- ============================================================================
-- SECTION 5: Log CEO Authorization
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale
) VALUES (
    gen_random_uuid(),
    'SIGNAL_INVERSION_TEST_AUTHORIZED',
    'fhq_alpha.stress_inversion_shadow',
    'SHADOW_TEST',
    'CEO',
    NOW(),
    'APPROVED',
    'CEO-DIR-2026-075: Authorized STRESS signal inversion shadow test (48h). Based on Tier-1 Meta Review finding that STRESS 99%+ predictions are 100% wrong, yielding inverted Brier of 0.0058. This is the highest-leverage path to ROI identified by all 5 Tier-1 agents.'
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERY (Run after migration)
-- ============================================================================

-- SELECT * FROM fhq_alpha.v_stress_inversion_performance;
