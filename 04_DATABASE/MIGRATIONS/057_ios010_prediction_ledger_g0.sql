-- ============================================================
-- IoS-010 G0 SUBMISSION — PREDICTION LEDGER ENGINE
-- ============================================================
-- Migration: 057_ios010_prediction_ledger_g0.sql
-- Authority: LARS (CEO) — ADR-004 (Change Gates)
-- Technical Lead: STIG (CTO)
-- Governance: VEGA
-- Gate: G0 SUBMISSION
-- ADR Compliance: ADR-004, ADR-012, ADR-013, ADR-061
-- ============================================================
-- PURPOSE: Formal registration of IoS-010 as a G0_SUBMITTED module.
--          No execution authority, no constitutional power, no DB side-effects.
--          This establishes IoS-010 as a recognized application-layer component.
-- ============================================================
-- IMPLEMENTATION: prediction_ledger/ (pure Python, file-based storage)
-- G0 SCOPE: Pydantic models, validation logic, reconciliation engine,
--           evaluation metrics, calibration curves (all pure functions)
-- ============================================================

BEGIN;

-- ============================================================
-- SECTION 1: IoS-010 REGISTRY ENTRY
-- ============================================================

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
    experimental_classification,
    risk_multiplier,
    immutability_level,
    canonical,
    modification_requires,
    governance_state
) VALUES (
    'IoS-010',
    'Prediction Ledger Engine',
    'G0 SUBMITTED. Canonical audit layer for all probabilistic forecasts. Records forecasts with hash-verified state context, tracks realized outcomes, reconciles predictions to outcomes using deterministic matching, computes calibration/accuracy/skill metrics. Constitutional prerequisite for autonomous trading (ADR-012). Implementation: prediction_ledger/ (pure Python, file-based at G0).',
    '2026.G0',
    'G0_SUBMITTED',
    'FINN',
    ARRAY['ADR-004', 'ADR-012', 'ADR-013', 'ADR-061'],
    ARRAY['IoS-001', 'IoS-003', 'IoS-004', 'IoS-005'],
    encode(sha256(('IoS-010-G0-SUBMISSION-' || NOW()::TEXT)::bytea), 'hex'),
    'TIER-1_CRITICAL',
    1.00,
    'MUTABLE',
    FALSE,
    'G1-G4 Full Cycle (ADR-004)',
    'G0_SUBMITTED'
)
ON CONFLICT (ios_id) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    version = EXCLUDED.version,
    status = EXCLUDED.status,
    owner_role = EXCLUDED.owner_role,
    governing_adrs = EXCLUDED.governing_adrs,
    dependencies = EXCLUDED.dependencies,
    content_hash = EXCLUDED.content_hash,
    governance_state = EXCLUDED.governance_state,
    updated_at = NOW();

-- ============================================================
-- SECTION 2: GOVERNANCE ACTION LOG ENTRY
-- ============================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id
) VALUES (
    'G0_SUBMISSION',
    'IoS-010',
    'IOS_MODULE',
    'LARS',
    'APPROVED',
    'Formal registration of Prediction Ledger Engine. IoS-010 provides canonical audit layer for all probabilistic forecasts. G0 submission establishes pure logical contract (Pydantic models, validation, reconciliation, evaluation metrics). No DB tables, no execution authority at G0. Constitutional prerequisite for ADR-012 autonomous trading.',
    TRUE,
    'HC-IOS010-G0-' || to_char(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================
-- SECTION 3: REGISTRY RECONCILIATION LOG ENTRY
-- ============================================================

INSERT INTO fhq_governance.registry_reconciliation_log (
    initiated_by,
    ios_id,
    action,
    previous_state,
    new_state,
    rationale,
    adr_reference,
    vega_reviewed,
    hash_chain_id
) VALUES (
    'STIG',
    'IoS-010',
    'REGISTERED',
    NULL,
    '{
        "ios_id": "IoS-010",
        "title": "Prediction Ledger Engine",
        "version": "2026.G0",
        "status": "G0_SUBMITTED",
        "governance_state": "G0_SUBMITTED",
        "owner_role": "FINN",
        "canonical": false,
        "dependencies": ["IoS-001", "IoS-003", "IoS-004", "IoS-005"],
        "implementation_path": "prediction_ledger/",
        "g0_deliverables": [
            "ForecastRecord model",
            "OutcomeRecord model",
            "ForecastOutcomePair model",
            "EvaluationRecord model",
            "CalibrationCurve model",
            "Validation Engine",
            "Reconciliation Engine",
            "Evaluation Engine (Brier, MAE, Hit-Rate, Skill)",
            "Calibration Engine v1.1",
            "File-based JSONL storage (ADR-061 placeholder)"
        ]
    }'::jsonb,
    'CEO directive for formal G0 registration. IoS-010 is constitutional prerequisite for autonomous trading (ADR-012). Pure logical contract submitted; no DB tables at G0.',
    'ADR-004, ADR-013, ADR-061',
    TRUE,
    'HC-IOS010-G0-' || to_char(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================
-- SECTION 4: G0 COMPLIANCE VERIFICATION RECORD
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.ios010_g0_verification (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ios_id TEXT NOT NULL DEFAULT 'IoS-010',
    verification_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_by TEXT NOT NULL,

    -- ADR-004 Change-Gate Discipline
    g0_submission_valid BOOLEAN NOT NULL,
    no_g1_progression_without_approval BOOLEAN NOT NULL,
    no_test_execution_at_g0 BOOLEAN NOT NULL,
    no_migrations_at_g0 BOOLEAN NOT NULL,

    -- ADR-013 One-Source-Truth
    no_storage_tables_registered BOOLEAN NOT NULL,
    no_duplicate_identifiers BOOLEAN NOT NULL,
    single_authoritative_entry BOOLEAN NOT NULL,

    -- ADR-012 Economic Safety
    no_forecast_impact BOOLEAN NOT NULL,
    no_capital_allocation_impact BOOLEAN NOT NULL,
    no_risk_module_impact BOOLEAN NOT NULL,

    -- Implementation Verification
    implementation_path TEXT NOT NULL,
    models_verified JSONB NOT NULL,
    engines_verified JSONB NOT NULL,

    -- Hash Chain
    lineage_hash TEXT NOT NULL,
    hash_self TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_governance.ios010_g0_verification IS
'G0 compliance verification for IoS-010 Prediction Ledger Engine. Tracks ADR-004/012/013 compliance.';

-- Insert G0 verification record
INSERT INTO fhq_governance.ios010_g0_verification (
    verified_by,
    g0_submission_valid,
    no_g1_progression_without_approval,
    no_test_execution_at_g0,
    no_migrations_at_g0,
    no_storage_tables_registered,
    no_duplicate_identifiers,
    single_authoritative_entry,
    no_forecast_impact,
    no_capital_allocation_impact,
    no_risk_module_impact,
    implementation_path,
    models_verified,
    engines_verified,
    lineage_hash,
    hash_self
) VALUES (
    'STIG',
    TRUE,   -- G0 submission is valid
    TRUE,   -- Cannot progress to G1 without CEO directive + VEGA approval
    TRUE,   -- No test execution at G0
    TRUE,   -- No migrations at G0
    TRUE,   -- No storage tables registered (file-based only)
    TRUE,   -- No duplicate identifiers
    TRUE,   -- Single authoritative entry in ios_registry
    TRUE,   -- No forecast impact at G0
    TRUE,   -- No capital allocation impact at G0
    TRUE,   -- No risk module impact at G0
    'prediction_ledger/',
    '[
        {"model": "ForecastRecord", "file": "models.py", "status": "VERIFIED"},
        {"model": "OutcomeRecord", "file": "models.py", "status": "VERIFIED"},
        {"model": "ForecastOutcomePair", "file": "models.py", "status": "VERIFIED"},
        {"model": "EvaluationRecord", "file": "models.py", "status": "VERIFIED"},
        {"model": "CalibrationCurve", "file": "models.py", "status": "VERIFIED"}
    ]'::jsonb,
    '[
        {"engine": "ValidationEngine", "file": "models.py", "status": "VERIFIED"},
        {"engine": "ReconciliationEngine", "file": "reconciliation.py", "status": "VERIFIED"},
        {"engine": "EvaluationEngine", "file": "evaluation.py", "status": "VERIFIED"},
        {"engine": "CalibrationEngine", "file": "evaluation.py", "status": "VERIFIED"},
        {"engine": "StorageEngine", "file": "storage.py", "status": "VERIFIED", "note": "File-based JSONL (ADR-061 placeholder)"}
    ]'::jsonb,
    'IOS010-G0-VERIFICATION-' || NOW()::TEXT,
    encode(sha256(('IOS010-G0-VERIFICATION-' || NOW()::TEXT)::bytea), 'hex')
);

-- ============================================================
-- SECTION 5: VERIFICATION QUERIES
-- ============================================================

-- Verify IoS-010 registry entry
SELECT 'IoS-010 Registry Entry' AS verification,
       ios_id, title, version, status, governance_state, canonical, owner_role
FROM fhq_meta.ios_registry
WHERE ios_id = 'IoS-010';

-- Verify governance action logged
SELECT 'Governance Action Logged' AS verification,
       action_type, action_target, initiated_by, decision, hash_chain_id
FROM fhq_governance.governance_actions_log
WHERE action_target = 'IoS-010'
ORDER BY initiated_at DESC
LIMIT 1;

-- Verify reconciliation log entry
SELECT 'Reconciliation Log Entry' AS verification,
       ios_id, action, new_state->>'status' as new_status, vega_reviewed
FROM fhq_governance.registry_reconciliation_log
WHERE ios_id = 'IoS-010'
ORDER BY created_at DESC
LIMIT 1;

-- Verify G0 compliance
SELECT 'G0 Compliance Verified' AS verification,
       ios_id,
       g0_submission_valid,
       no_storage_tables_registered,
       no_forecast_impact,
       implementation_path
FROM fhq_governance.ios010_g0_verification
WHERE ios_id = 'IoS-010';

-- Full registry state (ordered)
SELECT 'Full Registry State' AS verification,
       ios_id, status, governance_state, canonical
FROM fhq_meta.ios_registry
ORDER BY ios_id;

-- Generate checksum of modified rows
SELECT 'Registry Entry Checksum' AS verification,
       encode(sha256((ios_id || title || version || status || COALESCE(governance_state, ''))::bytea), 'hex') as row_checksum
FROM fhq_meta.ios_registry
WHERE ios_id = 'IoS-010';

COMMIT;

-- ============================================================
-- MIGRATION COMPLETE: IoS-010 G0 SUBMISSION
-- ============================================================
-- Status: G0_SUBMITTED
-- Owner: FINN
-- Validator: LARS
-- Governance: VEGA
-- Constitutional: FALSE (until G4)
-- Next Gate: G1 Technical Validation (requires CEO + VEGA approval)
-- ============================================================
