-- ============================================================
-- IoS-012 G4 CONDITIONAL — PAPER ACTIVATION
-- ============================================================
-- Migration: 060_ios012_paper_activation.sql
-- Authority: CEO (Two-Man Rule with VEGA G4_WARN)
-- Gate: G4 CONDITIONAL ACTIVATION
-- Mode: PAPER_ONLY
-- ADR Compliance: ADR-004, ADR-008, ADR-012, ADR-013, ADR-016
-- ============================================================
-- PURPOSE: Activate IoS-012 for PAPER environment execution
--          under constitutional constraints. LIVE remains blocked.
-- ============================================================
-- CEO MANDATE REFERENCE: G4 CONDITIONAL ACTIVATION & REMEDIATION ORDER
-- VEGA CERTIFICATION: IOS012_G4_VEGA_CERTIFICATION_20251201.json
-- ============================================================

BEGIN;

-- ============================================================
-- SECTION 1: UPDATE IoS-012 STATUS TO G4_CONDITIONAL
-- ============================================================

UPDATE fhq_meta.ios_registry
SET
    status = 'G4_CONSTITUTIONAL',
    governance_state = 'G4_CONDITIONAL',
    immutability_level = 'FROZEN_PAPER_ACTIVE',
    modification_requires = 'CEO_DIRECTIVE + VEGA_RE_CERTIFICATION for LIVE',
    version = '2026.PROD.G4.PAPER',
    updated_at = NOW()
WHERE ios_id = 'IoS-012';

-- ============================================================
-- SECTION 2: PAPER EXECUTION AUTHORITY TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.paper_execution_authority (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ios_id TEXT NOT NULL,
    activation_mode TEXT NOT NULL CHECK (activation_mode IN ('PAPER', 'LIVE', 'DISABLED')),

    -- Authority Scope
    execution_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    paper_api_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    live_api_enabled BOOLEAN NOT NULL DEFAULT FALSE,

    -- Source Mandate Override (CEO Temporary Auth)
    source_mandate_override BOOLEAN NOT NULL DEFAULT FALSE,
    override_source TEXT,
    override_authorized_by TEXT,
    override_expires_on TEXT,  -- 'LIVE_ACTIVATION_REQUEST' or timestamp

    -- Constraints
    code_immutability_enforced BOOLEAN NOT NULL DEFAULT TRUE,
    adr_012_constraints_enforced BOOLEAN NOT NULL DEFAULT TRUE,
    governance_logging_required BOOLEAN NOT NULL DEFAULT TRUE,

    -- Activation Details
    activated_by TEXT NOT NULL,
    activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    vega_certification_ref TEXT NOT NULL,
    ceo_mandate_ref TEXT NOT NULL,

    -- Hash Chain
    hash_chain_id TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_governance.paper_execution_authority IS
'Tracks PAPER execution authority for IoS modules under G4 Conditional activation. ADR-012 compliance.';

-- Insert IoS-012 PAPER activation record
INSERT INTO fhq_governance.paper_execution_authority (
    ios_id,
    activation_mode,
    execution_enabled,
    paper_api_enabled,
    live_api_enabled,
    source_mandate_override,
    override_source,
    override_authorized_by,
    override_expires_on,
    code_immutability_enforced,
    adr_012_constraints_enforced,
    governance_logging_required,
    activated_by,
    vega_certification_ref,
    ceo_mandate_ref,
    hash_chain_id
) VALUES (
    'IoS-012',
    'PAPER',
    TRUE,                                    -- Execution enabled
    TRUE,                                    -- PAPER API enabled
    FALSE,                                   -- LIVE API disabled
    TRUE,                                    -- Source mandate override active
    'CEO_TEMPORARY_AUTH',                    -- Override source
    'CEO',                                   -- Authorized by
    'LIVE_ACTIVATION_REQUEST',               -- Expires when LIVE requested
    TRUE,                                    -- Code immutability enforced
    TRUE,                                    -- ADR-012 constraints enforced
    TRUE,                                    -- Governance logging required
    'CEO',
    'VEGA-IOS012-G4-CERT-20251201',
    'CEO-IOS012-PAPER-MANDATE-20251201',
    'HC-IOS012-PAPER-ACTIVATION-' || to_char(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================
-- SECTION 3: IoS-008 TEMPORARY MANDATE AUTHORITY
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.ios008_mandate_authority (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Authority Scope
    target_ios_id TEXT NOT NULL,
    environment TEXT NOT NULL CHECK (environment IN ('PAPER', 'LIVE')),
    mandate_authority_granted BOOLEAN NOT NULL DEFAULT FALSE,

    -- Override Details
    override_type TEXT NOT NULL,
    override_source TEXT NOT NULL,
    authorized_by TEXT NOT NULL,
    authorized_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Expiration
    expires_on_condition TEXT NOT NULL,
    expired BOOLEAN NOT NULL DEFAULT FALSE,
    expired_at TIMESTAMPTZ,
    expired_reason TEXT,

    -- Constraints
    must_tag_override_source BOOLEAN NOT NULL DEFAULT TRUE,
    required_tag TEXT NOT NULL,

    -- Hash Chain
    hash_chain_id TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_governance.ios008_mandate_authority IS
'Tracks IoS-008 temporary mandate authority for execution targets. CEO override for PAPER mode.';

-- Grant IoS-008 temporary mandate authority for IoS-012 PAPER
INSERT INTO fhq_governance.ios008_mandate_authority (
    target_ios_id,
    environment,
    mandate_authority_granted,
    override_type,
    override_source,
    authorized_by,
    expires_on_condition,
    must_tag_override_source,
    required_tag,
    hash_chain_id
) VALUES (
    'IoS-012',
    'PAPER',
    TRUE,
    'CEO_TEMPORARY_AUTH',
    'CEO Mandate — G4 Conditional Activation',
    'CEO',
    'LIVE_ACTIVATION_REQUEST',
    TRUE,
    'CEO_TEMPORARY_AUTH',
    'HC-IOS008-MANDATE-AUTH-' || to_char(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================
-- SECTION 4: UPDATE G4 REVIEW CONSTRAINTS FOR PAPER MODE
-- ============================================================

UPDATE fhq_governance.g4_review_constraints
SET
    execution_authority_off = FALSE,      -- Execution now enabled for PAPER
    no_outbound_trades = FALSE,           -- PAPER trades allowed
    no_capital_modification = TRUE,       -- No real capital impact
    no_exposure_modification = TRUE,      -- No real exposure changes
    api_sandbox_only = TRUE,              -- PAPER/Sandbox API only
    no_dynamic_config = TRUE,             -- Config frozen
    no_unreviewed_commits = TRUE          -- Code frozen
WHERE ios_id = 'IoS-012';

-- ============================================================
-- SECTION 5: PAPER EXECUTION LOOP CONFIGURATION
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.paper_execution_loop (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loop_id TEXT NOT NULL UNIQUE,

    -- Pipeline Configuration
    source_module TEXT NOT NULL,          -- IoS-008
    execution_module TEXT NOT NULL,       -- IoS-012
    target_api TEXT NOT NULL,             -- PAPER_API

    -- Loop State
    loop_status TEXT NOT NULL DEFAULT 'INITIALIZED'
        CHECK (loop_status IN ('INITIALIZED', 'RUNNING', 'PAUSED', 'HALTED', 'ERROR')),

    -- Constraints
    governance_logging_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    override_tag_required TEXT,
    adr_012_compliance BOOLEAN NOT NULL DEFAULT TRUE,

    -- Activation
    activated_by TEXT NOT NULL,
    activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Hash Chain
    hash_chain_id TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_governance.paper_execution_loop IS
'Configuration for PAPER execution pipeline: IoS-008 → IoS-012 → PAPER_API.';

-- Initialize PAPER execution loop
INSERT INTO fhq_governance.paper_execution_loop (
    loop_id,
    source_module,
    execution_module,
    target_api,
    loop_status,
    governance_logging_enabled,
    override_tag_required,
    adr_012_compliance,
    activated_by,
    hash_chain_id
) VALUES (
    'PAPER-LOOP-IOS008-IOS012-20251201',
    'IoS-008',
    'IoS-012',
    'PAPER_API',
    'INITIALIZED',
    TRUE,
    'CEO_TEMPORARY_AUTH',
    TRUE,
    'CEO',
    'HC-PAPER-LOOP-' || to_char(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================
-- SECTION 6: GOVERNANCE ACTION LOG — CEO ACTIVATION
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
    'G4_CONDITIONAL_ACTIVATION',
    'IoS-012',
    'PAPER_EXECUTION',
    'CEO',
    'APPROVED',
    'Two-Man Rule fulfilled. CEO accepts VEGA G4_WARN conditions. PAPER-ONLY activation authorized. IoS-008 granted temporary mandate authority for PAPER mode with required tag CEO_TEMPORARY_AUTH. LIVE activation remains BLOCKED pending remediation of CV-001, CV-002, HV-001, HV-002. Execution loop: IoS-008 → IoS-012 → PAPER_API under full governance logging.',
    TRUE,
    'HC-CEO-PAPER-ACTIVATION-' || to_char(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================
-- SECTION 7: REGISTRY RECONCILIATION LOG
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
    'CEO',
    'IoS-012',
    'UPDATED',
    '{"status": "G4_CONSTITUTIONAL", "governance_state": "G4_CONDITIONAL", "immutability_level": "PAPER_ONLY"}'::jsonb,
    '{"status": "G4_CONSTITUTIONAL", "governance_state": "G4_CONDITIONAL", "immutability_level": "FROZEN_PAPER_ACTIVE", "execution_mode": "PAPER", "ios008_override": true, "live_blocked": true}'::jsonb,
    'CEO Two-Man Rule activation. PAPER mode enabled with IoS-008 temporary mandate authority. LIVE blocked pending remediations.',
    'ADR-004, ADR-008, ADR-012, ADR-013, ADR-016',
    TRUE,
    'HC-CEO-PAPER-ACTIVATION-' || to_char(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================
-- SECTION 8: VERIFICATION QUERIES
-- ============================================================

-- Verify IoS-012 status
SELECT 'IoS-012 G4 Conditional Status' AS verification,
       ios_id, status, governance_state, immutability_level, version
FROM fhq_meta.ios_registry
WHERE ios_id = 'IoS-012';

-- Verify PAPER execution authority
SELECT 'PAPER Execution Authority' AS verification,
       ios_id, activation_mode, execution_enabled, paper_api_enabled, live_api_enabled,
       source_mandate_override, override_source
FROM fhq_governance.paper_execution_authority
WHERE ios_id = 'IoS-012';

-- Verify IoS-008 mandate authority
SELECT 'IoS-008 Mandate Authority' AS verification,
       target_ios_id, environment, mandate_authority_granted, override_type, required_tag
FROM fhq_governance.ios008_mandate_authority
WHERE target_ios_id = 'IoS-012';

-- Verify PAPER execution loop
SELECT 'PAPER Execution Loop' AS verification,
       loop_id, source_module, execution_module, target_api, loop_status
FROM fhq_governance.paper_execution_loop
WHERE execution_module = 'IoS-012';

-- Verify G4 review constraints updated
SELECT 'G4 Review Constraints' AS verification,
       ios_id, execution_authority_off, no_outbound_trades, api_sandbox_only
FROM fhq_governance.g4_review_constraints
WHERE ios_id = 'IoS-012';

COMMIT;

-- ============================================================
-- MIGRATION COMPLETE: IoS-012 PAPER ACTIVATION
-- ============================================================
-- Status: G4_CONDITIONAL
-- Mode: PAPER_ONLY
-- Execution: ENABLED (PAPER_API)
-- IoS-008 Override: ACTIVE (CEO_TEMPORARY_AUTH)
-- LIVE Status: BLOCKED
-- Pipeline: IoS-008 → IoS-012 → PAPER_API
-- Next Step: STIG remediation of CV-001, CV-002, HV-001, HV-002
-- ============================================================
