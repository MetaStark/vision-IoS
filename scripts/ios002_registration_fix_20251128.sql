-- ============================================================================
-- DIRECTIVE: IOS-002 REGISTRATION FIX
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE I: REGISTER IOS-002 IN IOS_REGISTRY (with placeholder hash)
-- ============================================================================

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
    encode(sha256('IoS-002:2026.PROD.1:INDICATOR_ENGINE:DRAFT'::bytea), 'hex'),
    NULL,
    NULL,
    NOW(),
    NOW()
)
ON CONFLICT (ios_id) DO UPDATE SET
    version = EXCLUDED.version,
    status = EXCLUDED.status,
    description = EXCLUDED.description,
    content_hash = EXCLUDED.content_hash,
    updated_at = NOW();

-- Record version history
INSERT INTO fhq_meta.ios_version_history (
    ios_id,
    version,
    previous_version,
    change_type,
    change_summary,
    changed_by,
    content_hash
)
VALUES (
    'IoS-002',
    '2026.PROD.1',
    NULL,
    'CREATION',
    'Initial IoS-002 registration. Indicator Engine – Sensory Cortex. G0 Submission.',
    'CODE',
    encode(sha256('IoS-002:2026.PROD.1:INDICATOR_ENGINE:DRAFT'::bytea), 'hex')
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
-- PHASE II: REGISTER HASHES IN FHQ_MONITORING.HASH_REGISTRY
-- ============================================================================

BEGIN;

INSERT INTO fhq_monitoring.hash_registry (
    schema_name,
    table_name,
    hash_algorithm,
    hash_value,
    row_count,
    computed_by,
    hash_scope,
    adr_reference
)
VALUES
    ('fhq_research', 'indicator_momentum', 'SHA-256',
     encode(sha256('fhq_research.indicator_momentum:id:timestamp:asset_id:value_json:engine_version:formula_hash:lineage_hash:created_at'::bytea), 'hex'),
     0, 'CODE', 'SCHEMA', 'ADR-007'),
    ('fhq_research', 'indicator_trend', 'SHA-256',
     encode(sha256('fhq_research.indicator_trend:id:timestamp:asset_id:value_json:engine_version:formula_hash:lineage_hash:created_at'::bytea), 'hex'),
     0, 'CODE', 'SCHEMA', 'ADR-007'),
    ('fhq_research', 'indicator_volatility', 'SHA-256',
     encode(sha256('fhq_research.indicator_volatility:id:timestamp:asset_id:value_json:engine_version:formula_hash:lineage_hash:created_at'::bytea), 'hex'),
     0, 'CODE', 'SCHEMA', 'ADR-007'),
    ('fhq_research', 'indicator_ichimoku', 'SHA-256',
     encode(sha256('fhq_research.indicator_ichimoku:id:timestamp:asset_id:value_json:engine_version:formula_hash:lineage_hash:created_at'::bytea), 'hex'),
     0, 'CODE', 'SCHEMA', 'ADR-007');

COMMIT;

-- ============================================================================
-- PHASE III: INSERT CALC_INDICATORS PIPELINE STAGE (REGISTERED status)
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
    'REGISTERED',
    'CODE',
    NOW()
)
ON CONFLICT DO NOTHING;

COMMIT;

-- ============================================================================
-- PHASE IV: GOVERNANCE ACTION FOR IOS-002
-- ============================================================================

BEGIN;

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
    updated_at = NOW()
WHERE ios_id = 'IoS-002';

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

SELECT 'IOS_REGISTRY' as check_type, ios_id, version, status, owner_role
FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-002';

SELECT 'VERSION_HISTORY' as check_type, ios_id, version, change_type
FROM fhq_meta.ios_version_history WHERE ios_id = 'IoS-002';

SELECT 'AUDIT_LOG' as check_type, ios_id, event_type, gate_level
FROM fhq_meta.ios_audit_log WHERE ios_id = 'IoS-002';

SELECT 'INDICATOR_TABLES' as check_type, table_name
FROM information_schema.tables
WHERE table_schema = 'fhq_research' AND table_name LIKE 'indicator_%';

SELECT 'HASH_REGISTRY' as check_type, schema_name, table_name
FROM fhq_monitoring.hash_registry WHERE schema_name = 'fhq_research';

SELECT 'PIPELINE_STAGE' as check_type, task_name, task_status
FROM fhq_governance.task_registry WHERE task_name = 'CALC_INDICATORS';

SELECT 'HASH_CHAIN' as check_type, chain_id, chain_type
FROM vision_verification.hash_chains WHERE chain_id = 'HC-IOS-002-20251128';

SELECT 'VEGA_ATTESTATION' as check_type, attestation_id, attestation_status
FROM fhq_governance.vega_attestations WHERE target_id = 'IoS-002';
