-- ============================================================
-- GENERATE FIRST ALPHA SIGNALS
-- Authority: STIG (CTO)
-- Purpose: Create first regime-based alpha signals from IoS-007
-- Migration: 050_generate_first_alpha_signals.sql
-- ============================================================

BEGIN;

-- ============================================================
-- ACTION 1: Generate alpha signals from current regime state
-- ============================================================

WITH latest_regime AS (
    SELECT
        r.asset_id,
        r.regime_label,
        r.confidence_score,
        r.timestamp
    FROM fhq_research.regime_predictions_v2 r
    WHERE r.timestamp = (SELECT MAX(timestamp) FROM fhq_research.regime_predictions_v2)
),
signals_to_insert AS (
    SELECT
        lr.asset_id,
        lr.regime_label,
        lr.confidence_score,
        lr.timestamp,
        p.target_allocation,
        p.max_position_pct,
        p.stop_loss_pct,
        p.confidence_threshold
    FROM latest_regime lr
    JOIN vision_signals.regime_position_rules p
        ON lr.asset_id = p.asset_id
        AND lr.regime_label = p.regime_label
    WHERE lr.confidence_score >= p.confidence_threshold
)
INSERT INTO vision_signals.alpha_signals (
    signal_id, signal_type, signal_strength, confidence_score,
    generated_at, valid_from, valid_until, signal_data,
    is_executable, execution_blocked_reason, created_by, hash_chain_id
)
SELECT
    gen_random_uuid(),
    'REGIME_BASED',
    s.target_allocation::numeric,
    s.confidence_score::numeric,
    NOW(),
    s.timestamp,
    s.timestamp + INTERVAL '1 day',
    jsonb_build_object(
        'asset_id', s.asset_id,
        'regime', s.regime_label,
        'target_allocation', s.target_allocation,
        'max_position_pct', s.max_position_pct,
        'stop_loss_pct', s.stop_loss_pct,
        'confidence_threshold', s.confidence_threshold,
        'golden_features', ARRAY['US_M2_YOY', 'GLOBAL_M2_USD', 'US_10Y_REAL_RATE', 'US_NET_LIQUIDITY'],
        'ios_version', 'IoS-007-G1'
    ),
    false,  -- Not executable (ADR-012 QG-F6 not passed)
    'ADR-012 QG-F6 NOT PASSED - Awaiting execution approval',
    'STIG',
    'HC-SIGNAL-001'
FROM signals_to_insert s;

-- ============================================================
-- Log governance action
-- ============================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale,
    vega_reviewed, vega_override, hash_chain_id
) VALUES (
    gen_random_uuid(),
    'SIGNAL_GENERATION',
    'vision_signals.alpha_signals',
    'DATA',
    'STIG',
    NOW(),
    'APPROVED',
    'Generated first regime-based alpha signals from IoS-007 G1 execution. Signals NOT EXECUTABLE per ADR-012 until QG-F6 gate passes.',
    false,
    false,
    'HC-SIGNAL-GEN-050'
);

COMMIT;

-- ============================================================
-- Verification
-- ============================================================

SELECT
    signal_id,
    signal_type,
    signal_data->>'asset_id' as asset,
    signal_data->>'regime' as regime,
    signal_strength as target_allocation,
    confidence_score,
    is_executable,
    execution_blocked_reason
FROM vision_signals.alpha_signals
ORDER BY (signal_data->>'asset_id');
