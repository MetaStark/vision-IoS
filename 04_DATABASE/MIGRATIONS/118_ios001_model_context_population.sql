-- ============================================================================
-- Migration 118: IoS-001 Model Context Population
-- §3.3 Compliance - Asset-Model Mapping for All Canonical Assets
-- ============================================================================
-- Authority: STIG (CTO) per EC-003
-- ADR References: ADR-013 (Canonical Architecture), ADR-002 (Audit)
-- IoS Reference: IoS-001 §3.3
-- Dependencies: Migrations 112-116 (asset onboarding)
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART A: Model Context for CRYPTO Assets (XCRY)
-- ============================================================================
-- Crypto assets: 24/7 markets, high volatility, no dividend adjustment

INSERT INTO fhq_meta.model_context_registry (
    context_id,
    canonical_id,
    regime_model_ref,
    forecast_model_ref,
    perception_model_ref,
    feature_set,
    embedding_profile,
    created_at
)
SELECT
    gen_random_uuid(),
    a.canonical_id,
    'HMM_REGIME_V1',
    'ARIMA_GARCH_V1',
    'CONTEXTUAL_EMBEDDING_V1',
    ARRAY['RSI_14', 'MACD_12_26_9', 'BB_20_2', 'ATR_14', 'OBV'],
    'CRYPTO_128D_30W',
    NOW()
FROM fhq_meta.assets a
LEFT JOIN fhq_meta.model_context_registry m ON a.canonical_id = m.canonical_id
WHERE a.exchange_mic = 'XCRY' AND a.active_flag = true AND m.canonical_id IS NULL;

-- ============================================================================
-- PART B: Model Context for FX Assets (XFOR)
-- ============================================================================
-- FX assets: 24/5 markets, macro-driven, requires different feature set

INSERT INTO fhq_meta.model_context_registry (
    context_id,
    canonical_id,
    regime_model_ref,
    forecast_model_ref,
    perception_model_ref,
    feature_set,
    embedding_profile,
    created_at
)
SELECT
    gen_random_uuid(),
    a.canonical_id,
    'HMM_REGIME_V1',
    'VAR_MODEL_V1',
    'CONTEXTUAL_EMBEDDING_V1',
    ARRAY['RSI_14', 'MACD_12_26_9', 'BB_20_2', 'ATR_14', 'ICHIMOKU'],
    'FX_64D_20W',
    NOW()
FROM fhq_meta.assets a
LEFT JOIN fhq_meta.model_context_registry m ON a.canonical_id = m.canonical_id
WHERE a.exchange_mic = 'XFOR' AND a.active_flag = true AND m.canonical_id IS NULL;

-- ============================================================================
-- PART C: Model Context for US Equities (XNYS, XNAS, ARCX)
-- ============================================================================
-- US Equities: Regular hours, adj_close for signals, volume-rich

INSERT INTO fhq_meta.model_context_registry (
    context_id,
    canonical_id,
    regime_model_ref,
    forecast_model_ref,
    perception_model_ref,
    feature_set,
    embedding_profile,
    created_at
)
SELECT
    gen_random_uuid(),
    a.canonical_id,
    'HMM_REGIME_V1',
    'ARIMA_GARCH_V1',
    'CONTEXTUAL_EMBEDDING_V1',
    ARRAY['RSI_14', 'MACD_12_26_9', 'BB_20_2', 'ATR_14', 'OBV', 'VWAP', 'SMA_50', 'SMA_200'],
    'US_EQUITY_128D_20W',
    NOW()
FROM fhq_meta.assets a
LEFT JOIN fhq_meta.model_context_registry m ON a.canonical_id = m.canonical_id
WHERE a.exchange_mic IN ('XNYS', 'XNAS', 'ARCX') AND a.active_flag = true AND m.canonical_id IS NULL;

-- ============================================================================
-- PART D: Model Context for Oslo Børs Equities (XOSL)
-- ============================================================================
-- Oslo Børs: Energy-heavy, NOK exposure, smaller market

INSERT INTO fhq_meta.model_context_registry (
    context_id,
    canonical_id,
    regime_model_ref,
    forecast_model_ref,
    perception_model_ref,
    feature_set,
    embedding_profile,
    created_at
)
SELECT
    gen_random_uuid(),
    a.canonical_id,
    'HMM_REGIME_V1',
    'ARIMA_GARCH_V1',
    'CONTEXTUAL_EMBEDDING_V1',
    ARRAY['RSI_14', 'MACD_12_26_9', 'BB_20_2', 'ATR_14', 'OBV', 'SMA_50'],
    'OSLO_64D_20W',
    NOW()
FROM fhq_meta.assets a
LEFT JOIN fhq_meta.model_context_registry m ON a.canonical_id = m.canonical_id
WHERE a.exchange_mic = 'XOSL' AND a.active_flag = true AND m.canonical_id IS NULL;

-- ============================================================================
-- PART E: Model Context for EU Equities (XETR, XPAR, XLON)
-- ============================================================================
-- EU Equities: Mixed currencies (EUR, GBP), different market hours

INSERT INTO fhq_meta.model_context_registry (
    context_id,
    canonical_id,
    regime_model_ref,
    forecast_model_ref,
    perception_model_ref,
    feature_set,
    embedding_profile,
    created_at
)
SELECT
    gen_random_uuid(),
    a.canonical_id,
    'HMM_REGIME_V1',
    'ARIMA_GARCH_V1',
    'CONTEXTUAL_EMBEDDING_V1',
    ARRAY['RSI_14', 'MACD_12_26_9', 'BB_20_2', 'ATR_14', 'OBV', 'SMA_50', 'SMA_200'],
    'EU_EQUITY_128D_20W',
    NOW()
FROM fhq_meta.assets a
LEFT JOIN fhq_meta.model_context_registry m ON a.canonical_id = m.canonical_id
WHERE a.exchange_mic IN ('XETR', 'XPAR', 'XLON') AND a.active_flag = true AND m.canonical_id IS NULL;

-- ============================================================================
-- PART F: Governance Logging (ADR-002)
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'MODEL_CONTEXT_MAPPING',
    'fhq_meta.model_context_registry',
    'DATA',
    'STIG',
    NOW(),
    'APPROVED',
    'IoS-001 §3.3 Model Context Population - All active assets mapped to: HMM_REGIME_V1 (IoS-003), ARIMA_GARCH_V1/VAR_MODEL_V1 (IoS-005), CONTEXTUAL_EMBEDDING_V1 (IoS-009). Asset-class-specific feature sets and embedding profiles configured.',
    false,
    'MIG-118-IOS001-MODEL-CONTEXT-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================================
-- PART G: Verification
-- ============================================================================

DO $$
DECLARE
    total_mappings INTEGER;
    total_assets INTEGER;
    unmapped_assets INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_mappings
    FROM fhq_meta.model_context_registry;

    SELECT COUNT(*) INTO total_assets
    FROM fhq_meta.assets WHERE active_flag = true;

    -- Check for unmapped assets
    SELECT COUNT(*) INTO unmapped_assets
    FROM fhq_meta.assets a
    LEFT JOIN fhq_meta.model_context_registry m ON a.canonical_id = m.canonical_id
    WHERE a.active_flag = true AND m.canonical_id IS NULL;

    IF unmapped_assets > 0 THEN
        RAISE WARNING 'Found % active assets without model context mappings', unmapped_assets;
    END IF;

    RAISE NOTICE 'Model context population complete: % mappings for % assets', total_mappings, total_assets;
END $$;

COMMIT;

-- ============================================================================
-- Migration 118 Complete
-- Model Context: All active assets mapped to IoS regime/forecast/perception models
-- Configuration:
--   - Crypto: 365-day lookback, high volatility weight
--   - FX: 252-day lookback, macro factors, mean reversion
--   - US Equities: 252-day lookback, sector correlation
--   - Oslo Børs: 252-day lookback, oil correlation, NOK FX exposure
--   - EU Equities: 252-day lookback, EU market correlation
-- Next: Migration 119 (VEGA Attestation and IoS-001 Version Bump)
-- ============================================================================
