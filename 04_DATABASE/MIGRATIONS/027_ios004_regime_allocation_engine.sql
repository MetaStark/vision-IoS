-- ============================================================================
-- MIGRATION 027: IoS-004 Regime-Driven Allocation Engine (G0 Infrastructure)
-- ============================================================================
-- Module: IoS-004
-- Gate: G0_SUBMISSION (Infrastructure Only)
-- Owner: LARS
-- Executed By: CODE (EC-011)
-- Authority: ADR-001/002/004/011/013, IoS Governance Charter
--
-- SCOPE: Infrastructure setup ONLY. No allocation logic. No data insertion.
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Create fhq_positions Schema
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS fhq_positions;

COMMENT ON SCHEMA fhq_positions IS
'FjordHQ Positions Schema - Capital allocation and exposure management.
Owned by STIG (infrastructure), controlled by LARS (strategy).
Created for IoS-004 Regime-Driven Allocation Engine.';

-- ============================================================================
-- SECTION 2: Create target_exposure_daily Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_positions.target_exposure_daily (
    -- Primary identification
    asset_id            TEXT        NOT NULL,
    timestamp           DATE        NOT NULL,

    -- Exposure values
    exposure_raw        NUMERIC     NOT NULL,
    exposure_constrained NUMERIC    NOT NULL,
    cash_weight         NUMERIC     NOT NULL,

    -- Model lineage
    model_id            UUID        NOT NULL,
    regime_label        TEXT        NOT NULL,
    confidence          NUMERIC     NOT NULL,

    -- ADR-011 Hash Chain Lineage
    lineage_hash        TEXT        NOT NULL,
    hash_prev           TEXT        NOT NULL,
    hash_self           TEXT        NOT NULL,

    -- Metadata
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Primary Key
    PRIMARY KEY (asset_id, timestamp),

    -- Exposure Constraints (0-1 range)
    CONSTRAINT chk_exposure_raw_range
        CHECK (exposure_raw >= 0 AND exposure_raw <= 1),
    CONSTRAINT chk_exposure_constrained_range
        CHECK (exposure_constrained >= 0 AND exposure_constrained <= 1),
    CONSTRAINT chk_cash_weight_range
        CHECK (cash_weight >= 0 AND cash_weight <= 1),
    CONSTRAINT chk_confidence_range
        CHECK (confidence >= 0 AND confidence <= 1),

    -- Regime Label Constraint (9 canonical HMM states)
    CONSTRAINT chk_regime_label_valid
        CHECK (regime_label IN (
            'STRONG_BULL',
            'BULL',
            'RANGE_UP',
            'NEUTRAL',
            'RANGE_DOWN',
            'BEAR',
            'STRONG_BEAR',
            'PARABOLIC',
            'BROKEN'
        ))
);

COMMENT ON TABLE fhq_positions.target_exposure_daily IS
'Daily target exposure allocations derived from IoS-003 HMM regime predictions.
IoS-004 Regime-Driven Allocation Engine output table.
Portfolio invariant: SUM(exposure_constrained) + cash_weight = 1.0 per date.';

COMMENT ON COLUMN fhq_positions.target_exposure_daily.asset_id IS 'Canonical asset symbol';
COMMENT ON COLUMN fhq_positions.target_exposure_daily.timestamp IS 'Trading date';
COMMENT ON COLUMN fhq_positions.target_exposure_daily.exposure_raw IS 'Pre-constraint exposure target (0-1)';
COMMENT ON COLUMN fhq_positions.target_exposure_daily.exposure_constrained IS 'Final exposure after portfolio constraints (0-1)';
COMMENT ON COLUMN fhq_positions.target_exposure_daily.cash_weight IS 'Cash allocation = 1.0 - SUM(exposure_constrained)';
COMMENT ON COLUMN fhq_positions.target_exposure_daily.model_id IS 'Active HMM model UUID from regime_model_registry';
COMMENT ON COLUMN fhq_positions.target_exposure_daily.regime_label IS 'Canonical 9-state HMM regime label';
COMMENT ON COLUMN fhq_positions.target_exposure_daily.confidence IS 'Model confidence score (0-1)';
COMMENT ON COLUMN fhq_positions.target_exposure_daily.lineage_hash IS 'ADR-011 lineage hash for deterministic replay';
COMMENT ON COLUMN fhq_positions.target_exposure_daily.hash_prev IS 'Previous row hash in chain';
COMMENT ON COLUMN fhq_positions.target_exposure_daily.hash_self IS 'Current row hash';

-- ============================================================================
-- SECTION 3: Portfolio Invariant Enforcement (Trigger)
-- ============================================================================
-- Invariant: SUM(exposure_constrained) + cash_weight = 1.0 per portfolio/date
-- For v1.0: Single global portfolio (no portfolio_id column)

CREATE OR REPLACE FUNCTION fhq_positions.validate_portfolio_invariant()
RETURNS TRIGGER AS $$
DECLARE
    total_exposure NUMERIC;
    expected_cash NUMERIC;
    tolerance NUMERIC := 0.0001; -- Floating point tolerance
BEGIN
    -- Calculate total exposure for this date (including the new/updated row)
    SELECT COALESCE(SUM(exposure_constrained), 0)
    INTO total_exposure
    FROM fhq_positions.target_exposure_daily
    WHERE timestamp = NEW.timestamp;

    -- Expected cash weight
    expected_cash := 1.0 - total_exposure;

    -- Validate: cash_weight must equal expected_cash (within tolerance)
    -- Note: This validates the NEW row's cash_weight matches what's expected
    IF ABS(NEW.cash_weight - expected_cash) > tolerance THEN
        RAISE EXCEPTION 'Portfolio invariant violation: cash_weight (%) does not match expected (1.0 - SUM(exposure_constrained) = %). Date: %',
            NEW.cash_weight, expected_cash, NEW.timestamp;
    END IF;

    -- Validate: Total exposure cannot exceed 1.0
    IF total_exposure > (1.0 + tolerance) THEN
        RAISE EXCEPTION 'Portfolio invariant violation: SUM(exposure_constrained) = % exceeds 1.0. Date: %',
            total_exposure, NEW.timestamp;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_positions.validate_portfolio_invariant() IS
'Enforces portfolio invariant: SUM(exposure_constrained) + cash_weight = 1.0 per date.
ADR-011 compliance for deterministic replay and audit integrity.';

-- Create trigger for INSERT and UPDATE
DROP TRIGGER IF EXISTS trg_validate_portfolio_invariant ON fhq_positions.target_exposure_daily;

CREATE TRIGGER trg_validate_portfolio_invariant
    AFTER INSERT OR UPDATE ON fhq_positions.target_exposure_daily
    FOR EACH ROW
    EXECUTE FUNCTION fhq_positions.validate_portfolio_invariant();

-- ============================================================================
-- SECTION 4: Indexes for Performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_target_exposure_daily_timestamp
    ON fhq_positions.target_exposure_daily(timestamp);

CREATE INDEX IF NOT EXISTS idx_target_exposure_daily_model_id
    ON fhq_positions.target_exposure_daily(model_id);

CREATE INDEX IF NOT EXISTS idx_target_exposure_daily_regime
    ON fhq_positions.target_exposure_daily(regime_label);

CREATE INDEX IF NOT EXISTS idx_target_exposure_daily_hash_self
    ON fhq_positions.target_exposure_daily(hash_self);

-- ============================================================================
-- SECTION 5: Register IoS-004 in ios_registry
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
    created_at,
    updated_at
) VALUES (
    'IoS-004',
    'Regime-Driven Allocation Engine',
    'Transforms canonical regime states from IoS-003 HMM v2.0 Meta-Perception Engine into deterministic, auditable portfolio weights. First capital-allocation module of FjordHQ.',
    '2026.PROD.0',
    'DRAFT',
    'LARS',
    ARRAY[
        'ADR-001', 'ADR-002', 'ADR-003', 'ADR-004',
        'ADR-006', 'ADR-007', 'ADR-011', 'ADR-012',
        'ADR-013', 'ADR-014', 'ADR-016',
        'IoS-003_Appendix_A_HMM_REGIME'
    ],
    ARRAY['IoS-003'],
    encode(sha256(
        'IoS-004:Regime-Driven Allocation Engine:2026.PROD.0:LARS:DRAFT:' ||
        NOW()::TEXT
    ::bytea), 'hex'),
    NOW(),
    NOW()
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
    updated_at = NOW();

-- ============================================================================
-- SECTION 6: Register Task in task_registry
-- ============================================================================

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
    'REGIME_ALLOCATION_ENGINE_V1',
    'ALLOCATION_ENGINE',
    'IOS_004_INTERNAL',
    'LARS',
    'CODE',
    ARRAY['fhq_research', 'fhq_perception'],
    ARRAY['fhq_positions'],
    'G1',
    FALSE,
    FALSE,
    'Deterministic regime-driven allocation engine bound to IoS-003 HMM regimes. Transforms regime_predictions_v2 into target_exposure_daily. Portfolio invariant enforced.',
    'REGISTERED',
    'STIG',
    NOW(),
    NOW()
)
ON CONFLICT (task_name) DO UPDATE SET
    task_type = EXCLUDED.task_type,
    task_scope = EXCLUDED.task_scope,
    owned_by_agent = EXCLUDED.owned_by_agent,
    executed_by_agent = EXCLUDED.executed_by_agent,
    reads_from_schemas = EXCLUDED.reads_from_schemas,
    writes_to_schemas = EXCLUDED.writes_to_schemas,
    gate_level = EXCLUDED.gate_level,
    description = EXCLUDED.description,
    task_status = EXCLUDED.task_status,
    updated_at = NOW();

-- ============================================================================
-- SECTION 7: Create Hash Chain for IoS-004
-- ============================================================================

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
    'HC-IOS-004-2026',
    'IOS_MODULE',
    'IoS-004',
    encode(sha256(('IoS-004:GENESIS:' || NOW()::TEXT)::bytea), 'hex'),
    encode(sha256(('IoS-004:GENESIS:' || NOW()::TEXT)::bytea), 'hex'),
    1,
    TRUE,
    NOW(),
    'STIG',
    NOW(),
    NOW()
)
ON CONFLICT (chain_id) DO NOTHING;

-- ============================================================================
-- SECTION 8: Audit Log Entry
-- ============================================================================

INSERT INTO fhq_meta.adr_audit_log (
    audit_id,
    change_proposal_id,
    event_type,
    gate_stage,
    adr_id,
    initiated_by,
    decision,
    resolution_notes,
    evidence_path,
    sha256_hash,
    hash_chain_id,
    metadata,
    timestamp
) VALUES (
    gen_random_uuid(),
    'CP-IOS004-G0-' || TO_CHAR(NOW(), 'YYYYMMDD'),
    'SUBMISSION',
    'G0',
    NULL,  -- IoS-004 is an IoS module, not an ADR
    'STIG',
    'APPROVED',
    'G0 infrastructure submission for IoS-004 Regime-Driven Allocation Engine. Schema fhq_positions created, target_exposure_daily table deployed with portfolio invariant enforcement.',
    'evidence/IOS004_G0_SUBMISSION_' || TO_CHAR(NOW(), 'YYYYMMDD') || '.json',
    encode(sha256(('IoS-004:G0_SUBMISSION:' || NOW()::TEXT)::bytea), 'hex'),
    'HC-IOS-004-2026',
    jsonb_build_object(
        'gate', 'G0',
        'module', 'IoS-004',
        'title', 'Regime-Driven Allocation Engine',
        'version', '2026.PROD.0',
        'owner', 'LARS',
        'infrastructure_created', jsonb_build_array(
            'fhq_positions schema',
            'fhq_positions.target_exposure_daily table',
            'Portfolio invariant trigger',
            'Performance indexes'
        ),
        'registry_entries', jsonb_build_array(
            'fhq_meta.ios_registry: IoS-004',
            'fhq_governance.task_registry: REGIME_ALLOCATION_ENGINE_V1',
            'vision_verification.hash_chains: HC-IOS-004-2026'
        ),
        'dependencies', ARRAY['IoS-003']::TEXT[],
        'governing_adrs', 'IoS-003_Appendix_A_HMM_REGIME included',
        'executed_by', 'CODE (EC-011)',
        'authorized_by', 'LARS (G0 SUBMISSION DIRECTIVE)'
    ),
    NOW()
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (Post-Migration)
-- ============================================================================
-- Run these to verify G0 success:

-- 1. Verify IoS-004 registry entry
-- SELECT * FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-004';

-- 2. Verify table structure
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_schema = 'fhq_positions' AND table_name = 'target_exposure_daily';

-- 3. Verify constraints
-- SELECT conname, pg_get_constraintdef(oid)
-- FROM pg_constraint
-- WHERE conrelid = 'fhq_positions.target_exposure_daily'::regclass;

-- 4. Verify table is empty
-- SELECT COUNT(*) FROM fhq_positions.target_exposure_daily;

-- 5. Verify task registry entry
-- SELECT * FROM fhq_governance.task_registry WHERE task_name = 'REGIME_ALLOCATION_ENGINE_V1';

-- 6. Verify hash chain
-- SELECT * FROM vision_verification.hash_chains WHERE chain_id = 'HC-IOS-004-2026';
