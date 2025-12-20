-- ============================================================================
-- DIRECTIVE: IOS-002 REGISTRATION & FULL SYSTEM READINESS CHECK
-- ============================================================================
-- Authority Chain: ADR-001 → ADR-003 → ADR-004 → ADR-007 → IoS-001 → IoS-002
-- Owner: FINN (Research & Insight Domain)
-- Governing Agent: VEGA
-- Classification: IoS Module Registration (G0 → G1)
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE I: CREATE REQUIRED AUDIT TABLES (if not exist)
-- ============================================================================

-- ios_version_history
CREATE TABLE IF NOT EXISTS fhq_meta.ios_version_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ios_id TEXT NOT NULL,
    version TEXT NOT NULL,
    previous_version TEXT,
    change_type TEXT NOT NULL CHECK (change_type IN ('CREATION', 'UPDATE', 'CORRECTION', 'ACTIVATION', 'DEPRECATION')),
    change_summary TEXT,
    changed_by TEXT NOT NULL,
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    content_hash TEXT,
    vega_attestation_id UUID
);

CREATE INDEX IF NOT EXISTS idx_ios_version_history_ios_id ON fhq_meta.ios_version_history(ios_id);

-- ios_audit_log
CREATE TABLE IF NOT EXISTS fhq_meta.ios_audit_log (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ios_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('SUBMISSION', 'VALIDATION', 'APPROVAL', 'REJECTION', 'ACTIVATION', 'CORRECTION', 'EVIDENCE')),
    event_timestamp TIMESTAMPTZ DEFAULT NOW(),
    actor TEXT NOT NULL,
    gate_level TEXT,
    event_data JSONB,
    evidence_hash TEXT,
    hash_chain_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ios_audit_log_ios_id ON fhq_meta.ios_audit_log(ios_id);

-- hash_registry in fhq_monitoring
CREATE TABLE IF NOT EXISTS fhq_monitoring.hash_registry (
    hash_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_schema TEXT,
    target_table TEXT,
    hash_value TEXT NOT NULL,
    hash_algorithm TEXT DEFAULT 'SHA-256',
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    computed_by TEXT,
    verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_hash_registry_target ON fhq_monitoring.hash_registry(target_type, target_id);

COMMIT;

-- ============================================================================
-- PHASE II: REGISTER IOS-002 IN IOS_REGISTRY
-- ============================================================================

BEGIN;

INSERT INTO fhq_meta.ios_registry (
    ios_id,
    title,
    description,
    version,
    status,
    owner_role,
    governing_adrs,
    dependencies,
    content_hash,
    vega_signature_id,
    hash_chain_id,
    created_at,
    updated_at
)
VALUES (
    'IoS-002',
    'Indicator Engine – Sensory Cortex',
    'Feature extraction layer for FjordHQ Intelligence Operating System. Computes deterministic technical indicators (Momentum, Trend, Volatility, Ichimoku) from canonical OHLCV data. Environment: fhq_market → fhq_research',
    '2026.PROD.1',
    'DRAFT',
    'FINN',
    ARRAY['ADR-001', 'ADR-003', 'ADR-007', 'ADR-010', 'ADR-013'],
    ARRAY['IoS-001'],
    NULL,  -- Will be computed after file creation
    NULL,
    NULL,
    NOW(),
    NOW()
)
ON CONFLICT (ios_id) DO UPDATE SET
    version = EXCLUDED.version,
    status = EXCLUDED.status,
    description = EXCLUDED.description,
    updated_at = NOW();

-- Record version history
INSERT INTO fhq_meta.ios_version_history (
    ios_id,
    version,
    previous_version,
    change_type,
    change_summary,
    changed_by
)
VALUES (
    'IoS-002',
    '2026.PROD.1',
    NULL,
    'CREATION',
    'Initial IoS-002 registration. Indicator Engine – Sensory Cortex. G0 Submission.',
    'CODE'
);

-- Record G0 submission event
INSERT INTO fhq_meta.ios_audit_log (
    ios_id,
    event_type,
    actor,
    gate_level,
    event_data
)
VALUES (
    'IoS-002',
    'SUBMISSION',
    'FINN',
    'G0',
    jsonb_build_object(
        'directive', 'IOS-002_REGISTRATION_20251128',
        'authority_chain', 'ADR-001>ADR-003>ADR-007>IoS-001>IoS-002',
        'environment', 'fhq_market → fhq_research',
        'summary', 'Indicator Engine – Sensory Cortex',
        'next_gate', 'G1_TECHNICAL_VALIDATION'
    )
);

COMMIT;

-- ============================================================================
-- PHASE III: CREATE INDICATOR TABLES IN FHQ_RESEARCH
-- ============================================================================

BEGIN;

-- indicator_momentum (RSI, StochRSI, CCI, MFI)
CREATE TABLE IF NOT EXISTS fhq_research.indicator_momentum (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    asset_id TEXT NOT NULL,
    value_json JSONB NOT NULL,
    engine_version TEXT,
    formula_hash TEXT,
    lineage_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_indicator_momentum_asset_ts
ON fhq_research.indicator_momentum(asset_id, timestamp DESC);

-- indicator_trend (MACD, EMA, SMA, PSAR)
CREATE TABLE IF NOT EXISTS fhq_research.indicator_trend (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    asset_id TEXT NOT NULL,
    value_json JSONB NOT NULL,
    engine_version TEXT,
    formula_hash TEXT,
    lineage_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_indicator_trend_asset_ts
ON fhq_research.indicator_trend(asset_id, timestamp DESC);

-- indicator_volatility (Bollinger Bands, ATR)
CREATE TABLE IF NOT EXISTS fhq_research.indicator_volatility (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    asset_id TEXT NOT NULL,
    value_json JSONB NOT NULL,
    engine_version TEXT,
    formula_hash TEXT,
    lineage_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_indicator_volatility_asset_ts
ON fhq_research.indicator_volatility(asset_id, timestamp DESC);

-- indicator_ichimoku (Tenkan, Kijun, Senkou A/B, Chikou)
CREATE TABLE IF NOT EXISTS fhq_research.indicator_ichimoku (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    asset_id TEXT NOT NULL,
    value_json JSONB NOT NULL,
    engine_version TEXT,
    formula_hash TEXT,
    lineage_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_indicator_ichimoku_asset_ts
ON fhq_research.indicator_ichimoku(asset_id, timestamp DESC);

-- Add comments
COMMENT ON TABLE fhq_research.indicator_momentum IS 'IoS-002: Momentum indicators (RSI, StochRSI, CCI, MFI)';
COMMENT ON TABLE fhq_research.indicator_trend IS 'IoS-002: Trend indicators (MACD, EMA, SMA, PSAR)';
COMMENT ON TABLE fhq_research.indicator_volatility IS 'IoS-002: Volatility indicators (Bollinger Bands, ATR)';
COMMENT ON TABLE fhq_research.indicator_ichimoku IS 'IoS-002: Ichimoku Cloud indicators (Tenkan, Kijun, Senkou A/B, Chikou)';

COMMIT;

-- ============================================================================
-- PHASE IV: REGISTER TABLE HASHES IN FHQ_MONITORING
-- ============================================================================

BEGIN;

INSERT INTO fhq_monitoring.hash_registry (target_type, target_id, target_schema, target_table, hash_value, computed_by, metadata)
VALUES
    ('TABLE_SCHEMA', 'indicator_momentum', 'fhq_research', 'indicator_momentum',
     encode(sha256('fhq_research.indicator_momentum:id:timestamp:asset_id:value_json:engine_version:formula_hash:lineage_hash:created_at'::bytea), 'hex'),
     'CODE', '{"ios_module": "IoS-002", "indicator_class": "MOMENTUM"}'::jsonb),
    ('TABLE_SCHEMA', 'indicator_trend', 'fhq_research', 'indicator_trend',
     encode(sha256('fhq_research.indicator_trend:id:timestamp:asset_id:value_json:engine_version:formula_hash:lineage_hash:created_at'::bytea), 'hex'),
     'CODE', '{"ios_module": "IoS-002", "indicator_class": "TREND"}'::jsonb),
    ('TABLE_SCHEMA', 'indicator_volatility', 'fhq_research', 'indicator_volatility',
     encode(sha256('fhq_research.indicator_volatility:id:timestamp:asset_id:value_json:engine_version:formula_hash:lineage_hash:created_at'::bytea), 'hex'),
     'CODE', '{"ios_module": "IoS-002", "indicator_class": "VOLATILITY"}'::jsonb),
    ('TABLE_SCHEMA', 'indicator_ichimoku', 'fhq_research', 'indicator_ichimoku',
     encode(sha256('fhq_research.indicator_ichimoku:id:timestamp:asset_id:value_json:engine_version:formula_hash:lineage_hash:created_at'::bytea), 'hex'),
     'CODE', '{"ios_module": "IoS-002", "indicator_class": "ICHIMOKU"}'::jsonb);

COMMIT;

-- ============================================================================
-- PHASE V: INSERT CALC_INDICATORS PIPELINE STAGE
-- ============================================================================

BEGIN;

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
    created_at
)
VALUES (
    gen_random_uuid(),
    'CALC_INDICATORS',
    'PIPELINE_STAGE',
    'ORCHESTRATOR',
    'FINN',
    'CODE',
    ARRAY['fhq_market'],
    ARRAY['fhq_research'],
    'G1',
    false,
    false,
    'IoS-002 Pipeline Stage: Calculate technical indicators from OHLCV data. Produces momentum, trend, volatility, and ichimoku features.',
    'PENDING',
    'CODE',
    NOW()
)
ON CONFLICT DO NOTHING;

COMMIT;

-- ============================================================================
-- PHASE VI: CREATE HASH CHAIN FOR IOS-002
-- ============================================================================

BEGIN;

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
)
VALUES (
    'HC-IOS-002-20251128',
    'IOS_MODULE',
    'INDICATOR_ENGINE',
    encode(sha256('IOS-002:INDICATOR_ENGINE:FINN:VEGA:CODE:GENESIS'::bytea), 'hex'),
    encode(sha256(concat(
        'IOS-002:',
        '2026.PROD.1:',
        'G0_SUBMISSION:',
        'TABLES_CREATED:',
        NOW()::text
    )::bytea), 'hex'),
    1,
    true,
    NOW(),
    'IOS-002_REGISTRATION_20251128',
    NOW(),
    NOW()
);

COMMIT;

-- ============================================================================
-- PHASE VII: CREATE VEGA ATTESTATION FOR IOS-002 G0
-- ============================================================================

BEGIN;

INSERT INTO fhq_governance.vega_attestations (
    attestation_id,
    target_type,
    target_id,
    target_version,
    attestation_type,
    attestation_status,
    attestation_timestamp,
    vega_signature,
    vega_public_key,
    signature_verified,
    attestation_data,
    adr_reference,
    constitutional_basis,
    created_at
)
VALUES (
    'f0000005-0002-0002-0002-000000000001'::uuid,
    'IOS_MODULE',
    'IoS-002',
    '2026.PROD.1',
    'IOS_MODULE_G0_SUBMISSION',
    'PENDING',
    NOW(),
    encode(sha256(concat(
        'VEGA_IOS_G0_ATTESTATION:',
        'IoS-002:',
        '2026.PROD.1:',
        'INDICATOR_ENGINE:',
        NOW()::text
    )::bytea), 'hex'),
    'VEGA_IOS_MODULE_KEY_20251128',
    false,  -- Not yet verified, awaiting G1
    jsonb_build_object(
        'directive', 'IOS-002_REGISTRATION_20251128',
        'module_id', 'IoS-002',
        'module_title', 'Indicator Engine – Sensory Cortex',
        'version', '2026.PROD.1',
        'owner_role', 'FINN',
        'governing_agent', 'VEGA',
        'authority_chain', 'ADR-001>ADR-003>ADR-007>IoS-001>IoS-002',
        'environment', 'fhq_market → fhq_research',
        'gate_status', jsonb_build_object(
            'G0', 'SUBMITTED',
            'G1', 'PENDING',
            'G2', 'NOT_TRIGGERED',
            'G3', 'NOT_TRIGGERED',
            'G4', 'NOT_TRIGGERED'
        ),
        'tables_created', ARRAY['indicator_momentum', 'indicator_trend', 'indicator_volatility', 'indicator_ichimoku'],
        'pipeline_stage', 'CALC_INDICATORS',
        'dependencies', ARRAY['IoS-001'],
        'submitted_at', NOW()::text
    ),
    'ADR-007',
    'Orchestrator Architecture - IoS Module Submission',
    NOW()
);

-- Governance action for G0 submission
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
    vega_override,
    vega_notes,
    hash_chain_id,
    signature_id
)
VALUES (
    'f0000006-0002-0002-0002-000000000001'::uuid,
    'IOS_MODULE_G0_SUBMISSION',
    'IoS-002_INDICATOR_ENGINE',
    'IOS_MODULE',
    'FINN',
    NOW(),
    'APPROVED',
    'IoS-002 G0 Submission approved. Indicator Engine – Sensory Cortex registered. ' ||
    'Schema tables created in fhq_research. CALC_INDICATORS pipeline stage registered. ' ||
    'Awaiting G1 Technical Validation.',
    false,
    false,
    'VEGA review pending for G1 Technical Validation gate.',
    'HC-IOS-002-20251128',
    'f0000005-0002-0002-0002-000000000001'::uuid
);

-- Update ios_registry with attestation link
UPDATE fhq_meta.ios_registry
SET
    vega_signature_id = 'f0000005-0002-0002-0002-000000000001'::uuid,
    hash_chain_id = NULL,  -- TEXT chain_id referenced via attestation
    updated_at = NOW()
WHERE ios_id = 'IoS-002';

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

SELECT 'IOS_REGISTRY' as check_type, ios_id, version, status, owner_role
FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-002';

SELECT 'INDICATOR_TABLES' as check_type, table_name
FROM information_schema.tables
WHERE table_schema = 'fhq_research' AND table_name LIKE 'indicator_%';

SELECT 'HASH_REGISTRY' as check_type, target_id, hash_value
FROM fhq_monitoring.hash_registry WHERE target_type = 'TABLE_SCHEMA';

SELECT 'PIPELINE_STAGE' as check_type, task_name, task_status
FROM fhq_governance.task_registry WHERE task_name = 'CALC_INDICATORS';

SELECT 'HASH_CHAIN' as check_type, chain_id, chain_type
FROM vision_verification.hash_chains WHERE chain_id = 'HC-IOS-002-20251128';

SELECT 'VEGA_ATTESTATION' as check_type, attestation_id, attestation_status
FROM fhq_governance.vega_attestations WHERE target_id = 'IoS-002';
