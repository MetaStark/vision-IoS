-- ============================================================
-- MIGRATION 026: IoS-003_Appendix A – HMM REGIME Infrastructure
-- Gate: G0_SUBMISSION (Infrastructure Only)
-- Authority: LARS (Owner IoS-003) → CODE (EC-011)
-- ADR Reference: ADR-004 (Change Gates), ADR-013 (One-True-Source)
-- Date: 2025-11-29
-- ============================================================
--
-- SCOPE: Infrastructure only. NO computation. NO data population.
--
-- Creates:
--   1. fhq_research.regime_model_registry
--   2. fhq_perception.hmm_features_daily
--   3. fhq_research.regime_predictions_v2
--   4. fhq_meta.ios_appendix_registry
--   5. Task registry entry for META_PERCEPTION_HMM_PIPELINE
--   6. Governance action log entry
--
-- ============================================================

-- Pre-migration verification
SELECT 'PRE-MIGRATION CHECK' as stage;
SELECT ios_id, status, version FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-003';

BEGIN;

-- ============================================================
-- STEP 1: Create fhq_research.regime_model_registry
-- Stores canonical HMM regime model parameters and metadata
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_research.regime_model_registry (
    model_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    perception_model_version TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    model_hash TEXT NOT NULL,
    training_window_start DATE NOT NULL,
    training_window_end DATE NOT NULL,
    num_states INTEGER NOT NULL DEFAULT 9,
    transition_matrix JSONB NOT NULL,
    emission_parameters JSONB NOT NULL,
    retrain_hash TEXT,
    is_active BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Lineage columns per ADR-002/ADR-011
    lineage_hash TEXT NOT NULL,
    hash_prev TEXT,
    hash_self TEXT NOT NULL
);

-- Indexes for regime_model_registry
CREATE INDEX IF NOT EXISTS idx_regime_model_registry_version
    ON fhq_research.regime_model_registry(perception_model_version);
CREATE INDEX IF NOT EXISTS idx_regime_model_registry_active
    ON fhq_research.regime_model_registry(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_regime_model_registry_training_window
    ON fhq_research.regime_model_registry(training_window_start, training_window_end);

COMMENT ON TABLE fhq_research.regime_model_registry IS
    'Canonical HMM regime model registry per IoS-003 Appendix A. Stores model parameters, training metadata, and lineage.';

-- ============================================================
-- STEP 2: Create fhq_perception.hmm_features_daily
-- Stores the 7 canonical standardized HMM input features
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_perception.hmm_features_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id TEXT NOT NULL,
    timestamp DATE NOT NULL,
    -- 7 Canonical HMM Features (252-day z-scores per Appendix A)
    return_z NUMERIC NOT NULL,           -- Log returns z-score
    volatility_z NUMERIC NOT NULL,       -- 20-day rolling std dev z-score
    drawdown_z NUMERIC NOT NULL,         -- Drawdown from peak z-score
    macd_diff_z NUMERIC NOT NULL,        -- MACD histogram z-score
    bb_width_z NUMERIC NOT NULL,         -- Bollinger Band width z-score
    rsi_14_z NUMERIC NOT NULL,           -- RSI-14 z-score
    roc_20_z NUMERIC NOT NULL,           -- 20-day Rate of Change z-score
    -- Lineage columns per ADR-002/ADR-011
    engine_version TEXT NOT NULL,
    perception_model_version TEXT NOT NULL,
    formula_hash TEXT NOT NULL,
    lineage_hash TEXT NOT NULL,
    hash_prev TEXT,
    hash_self TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Unique constraint per Appendix A requirement
    CONSTRAINT hmm_features_daily_asset_timestamp_key UNIQUE(asset_id, timestamp)
);

-- Indexes for hmm_features_daily
CREATE INDEX IF NOT EXISTS idx_hmm_features_daily_asset_ts
    ON fhq_perception.hmm_features_daily(asset_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_hmm_features_daily_version
    ON fhq_perception.hmm_features_daily(perception_model_version);

COMMENT ON TABLE fhq_perception.hmm_features_daily IS
    'Canonical 7-feature HMM input vectors per IoS-003 Appendix A. All features are 252-day rolling z-scores.';

-- ============================================================
-- STEP 3: Create fhq_research.regime_predictions_v2
-- Stores model-level predictions with full lineage tracking
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_research.regime_predictions_v2 (
    prediction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id TEXT NOT NULL,
    timestamp DATE NOT NULL,
    model_id UUID REFERENCES fhq_research.regime_model_registry(model_id),
    perception_model_version TEXT NOT NULL,
    regime_raw INTEGER NOT NULL,         -- Internal HMM state ID (0-8)
    regime_label TEXT NOT NULL,          -- Human-readable regime label
    confidence_score NUMERIC NOT NULL,   -- Posterior probability [0,1]
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Lineage columns per ADR-002/ADR-011
    lineage_hash TEXT NOT NULL,
    hash_prev TEXT,
    hash_self TEXT NOT NULL,
    -- Constraints
    CONSTRAINT regime_predictions_v2_asset_timestamp_key UNIQUE(asset_id, timestamp),
    CONSTRAINT regime_predictions_v2_confidence_check CHECK (
        confidence_score >= 0 AND confidence_score <= 1
    ),
    CONSTRAINT regime_predictions_v2_regime_label_check CHECK (
        regime_label IN (
            'STRONG_BULL', 'BULL', 'RANGE_UP', 'NEUTRAL', 'RANGE_DOWN',
            'BEAR', 'STRONG_BEAR', 'PARABOLIC', 'BROKEN', 'UNTRUSTED'
        )
    )
);

-- Indexes for regime_predictions_v2
CREATE INDEX IF NOT EXISTS idx_regime_predictions_v2_asset_ts
    ON fhq_research.regime_predictions_v2(asset_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_regime_predictions_v2_model
    ON fhq_research.regime_predictions_v2(model_id);
CREATE INDEX IF NOT EXISTS idx_regime_predictions_v2_label
    ON fhq_research.regime_predictions_v2(regime_label);
CREATE INDEX IF NOT EXISTS idx_regime_predictions_v2_version
    ON fhq_research.regime_predictions_v2(perception_model_version);

COMMENT ON TABLE fhq_research.regime_predictions_v2 IS
    'HMM regime predictions with full lineage per IoS-003 Appendix A. Replaces legacy regime_predictions table.';

-- ============================================================
-- STEP 4: Create fhq_meta.ios_appendix_registry
-- Tracks appendices linked to IoS modules
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_meta.ios_appendix_registry (
    appendix_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ios_id TEXT NOT NULL,
    appendix_code TEXT NOT NULL,
    appendix_title TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    content_hash TEXT NOT NULL,
    owner_role TEXT,
    governing_adrs TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Unique constraint
    CONSTRAINT ios_appendix_unique UNIQUE(ios_id, appendix_code),
    -- Status check
    CONSTRAINT ios_appendix_status_check CHECK (
        status IN ('DRAFT', 'REGISTERED', 'ACTIVE', 'DEPRECATED', 'ARCHIVED')
    )
);

CREATE INDEX IF NOT EXISTS idx_ios_appendix_registry_ios
    ON fhq_meta.ios_appendix_registry(ios_id);

COMMENT ON TABLE fhq_meta.ios_appendix_registry IS
    'Registry of appendices linked to IoS modules. Tracks version, status, and content hash.';

-- ============================================================
-- STEP 5: Register Appendix A in ios_appendix_registry
-- ============================================================

INSERT INTO fhq_meta.ios_appendix_registry (
    ios_id,
    appendix_code,
    appendix_title,
    version,
    status,
    content_hash,
    owner_role,
    governing_adrs
) VALUES (
    'IoS-003',
    'Appendix_A_HMM_REGIME',
    'Canonical Regime Model Specification (HMM v2.0)',
    '2026.PROD.1',
    'REGISTERED',
    -- Content hash will be computed from the appendix document
    encode(sha256('IoS-003_Appendix_A_HMM_REGIME_v2026.PROD.1'::bytea), 'hex'),
    'LARS',
    ARRAY['ADR-001', 'ADR-002', 'ADR-003', 'ADR-006', 'ADR-007', 'ADR-009', 'ADR-010', 'ADR-011', 'ADR-012', 'ADR-013', 'ADR-016']
);

-- ============================================================
-- STEP 6: Update IoS-003 registry with appendix reference
-- ============================================================

UPDATE fhq_meta.ios_registry
SET
    governing_adrs = array_append(governing_adrs, 'IoS-003_Appendix_A_HMM_REGIME'),
    updated_at = NOW()
WHERE ios_id = 'IoS-003'
AND NOT ('IoS-003_Appendix_A_HMM_REGIME' = ANY(governing_adrs));

-- ============================================================
-- STEP 7: Register META_PERCEPTION_HMM_PIPELINE in task_registry
-- gate_approved = FALSE, vega_reviewed = FALSE per G0 requirements
-- ============================================================

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
    updated_at
) VALUES (
    gen_random_uuid(),
    'META_PERCEPTION_HMM_PIPELINE',
    'PERCEPTION_FEATURE_PIPELINE',
    'IOS_003_INTERNAL',
    'LARS',
    'CODE',
    ARRAY['fhq_market', 'fhq_research'],
    ARRAY['fhq_perception', 'fhq_research'],
    'G1',
    false,  -- gate_approved = FALSE per G0
    false,  -- vega_reviewed = FALSE per G0
    'HMM v2.0 Regime Detection Pipeline per IoS-003 Appendix A. Computes 7 canonical z-score features and deterministic argmax regime classification. Feature set: return_z, volatility_z, drawdown_z, macd_diff_z, bb_width_z, rsi_14_z, roc_20_z.',
    'REGISTERED',
    'STIG',
    NOW(),
    NOW()
) ON CONFLICT (task_name) DO NOTHING;

-- ============================================================
-- STEP 8: Log governance action for G0 submission
-- ============================================================

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
    hash_chain_id,
    signature_id
) VALUES (
    gen_random_uuid(),
    'IOS_APPENDIX_G0_SUBMISSION',
    'IoS-003_Appendix_A_HMM_REGIME',
    'IOS_APPENDIX',
    'LARS',
    NOW(),
    'APPROVED',
    'G0 submission APPROVED for HMM v2.0 regime pipeline infrastructure. Tables created: regime_model_registry, hmm_features_daily, regime_predictions_v2. Task registered: META_PERCEPTION_HMM_PIPELINE. No computation executed. No data populated.',
    false,
    'IOS003-APPENDIX-A-G0-' || to_char(NOW(), 'YYYYMMDD-HH24MISS'),
    gen_random_uuid()
);

-- ============================================================
-- STEP 9: Create hash chain entry for appendix registration
-- ============================================================

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
    'HC-IOS-003-APPENDIX-A-' || to_char(NOW(), 'YYYYMMDD'),
    'IOS_APPENDIX',
    'HMM_REGIME_PIPELINE',
    encode(sha256(('IoS-003:Appendix_A:G0:SUBMISSION:' || NOW()::text)::bytea), 'hex'),
    encode(sha256(('IoS-003:Appendix_A:G0:SUBMISSION:' || NOW()::text)::bytea), 'hex'),
    1,
    true,
    NOW(),
    'STIG',
    NOW(),
    NOW()
);

COMMIT;

-- ============================================================
-- POST-MIGRATION VERIFICATION
-- ============================================================

SELECT 'POST-MIGRATION VERIFICATION' as stage;

-- Verify tables created
SELECT 'TABLES CREATED' as check_type;
SELECT table_schema, table_name
FROM information_schema.tables
WHERE (table_schema = 'fhq_research' AND table_name IN ('regime_model_registry', 'regime_predictions_v2'))
   OR (table_schema = 'fhq_perception' AND table_name = 'hmm_features_daily')
   OR (table_schema = 'fhq_meta' AND table_name = 'ios_appendix_registry')
ORDER BY table_schema, table_name;

-- Verify all tables are empty
SELECT 'ROW COUNTS (must all be 0)' as check_type;
SELECT 'regime_model_registry' as table_name, COUNT(*) as rows FROM fhq_research.regime_model_registry
UNION ALL SELECT 'regime_predictions_v2', COUNT(*) FROM fhq_research.regime_predictions_v2
UNION ALL SELECT 'hmm_features_daily', COUNT(*) FROM fhq_perception.hmm_features_daily;

-- Verify task registry entry
SELECT 'TASK REGISTRY ENTRY' as check_type;
SELECT task_name, task_status, gate_approved, vega_reviewed
FROM fhq_governance.task_registry
WHERE task_name = 'META_PERCEPTION_HMM_PIPELINE';

-- Verify appendix registry entry
SELECT 'APPENDIX REGISTRY ENTRY' as check_type;
SELECT ios_id, appendix_code, status, version
FROM fhq_meta.ios_appendix_registry
WHERE ios_id = 'IoS-003';

-- Verify IoS-003 status unchanged
SELECT 'IoS-003 STATUS (must be ACTIVE)' as check_type;
SELECT ios_id, status, version
FROM fhq_meta.ios_registry
WHERE ios_id = 'IoS-003';

SELECT 'G0 MIGRATION COMPLETE' as status;
