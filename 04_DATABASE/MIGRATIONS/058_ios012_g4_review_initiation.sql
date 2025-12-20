-- ============================================================
-- IoS-012 G4 CONSTITUTIONAL ACTIVATION REVIEW INITIATION
-- ============================================================
-- Migration: 058_ios012_g4_review_initiation.sql
-- Authority: CEO — ADR-004 (Change Gates)
-- Technical Lead: STIG (CTO)
-- Governance: VEGA
-- Gate: G4 REVIEW INITIATION
-- ADR Compliance: ADR-004, ADR-011, ADR-012, ADR-013, ADR-016
-- ============================================================
-- PURPOSE: Initiate formal G4 Constitutional Activation Review for
--          IoS-012 Execution Engine. This updates governance state
--          to G4_REVIEW_PENDING and freezes the module for review.
-- ============================================================
-- CRITICAL: No elevation to G4 allowed before VEGA certification.
--           IoS-012 execution authority MUST remain OFF during review.
-- ============================================================

BEGIN;

-- ============================================================
-- SECTION 1: UPDATE IoS-012 GOVERNANCE STATE
-- ============================================================

UPDATE fhq_meta.ios_registry
SET
    governance_state = 'G4_REVIEW_PENDING',
    immutability_level = 'FROZEN_FOR_REVIEW',
    modification_requires = 'G4_REVIEW_COMPLETION + VEGA_CERTIFICATION + CEO_SIGNATURE',
    updated_at = NOW()
WHERE ios_id = 'IoS-012';

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
    'G4_REVIEW_INITIATED',
    'IoS-012',
    'CONSTITUTIONAL_ACTIVATION',
    'CEO',
    'IN_PROGRESS',
    'G4 Constitutional Activation Review initiated for IoS-012 Execution Engine. Module frozen for review. Required verifications: (1) Technical Integrity (ADR-004), (2) Economic Safety with NLV Accounting Identity (ADR-012), (3) Data Lineage Integrity (ADR-013), (4) FORTRESS Compliance (ADR-011), (5) Secrets Security. No autonomous execution permitted until VEGA issues G4_PASS.',
    TRUE,
    'HC-IOS012-G4-REVIEW-' || to_char(NOW(), 'YYYYMMDD-HH24MISS')
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
    'IoS-012',
    'UPDATED',
    '{"status": "G3_INTEGRATED", "governance_state": "G3_COMPLETE", "immutability_level": "MUTABLE"}'::jsonb,
    '{"status": "G3_INTEGRATED", "governance_state": "G4_REVIEW_PENDING", "immutability_level": "FROZEN_FOR_REVIEW"}'::jsonb,
    'G4 Constitutional Activation Review initiated by CEO directive. Module frozen for VEGA review. Execution authority remains OFF.',
    'ADR-004, ADR-011, ADR-012, ADR-013',
    TRUE,
    'HC-IOS012-G4-REVIEW-' || to_char(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================
-- SECTION 4: G4 REVIEW TRACKING TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.ios012_g4_review (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id TEXT NOT NULL UNIQUE,
    review_initiated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    review_initiated_by TEXT NOT NULL,

    -- Review Status
    review_status TEXT NOT NULL DEFAULT 'INITIATED'
        CHECK (review_status IN ('INITIATED', 'IN_PROGRESS', 'ARTIFACTS_SUBMITTED', 'VEGA_REVIEW', 'PASSED', 'FAILED', 'REMEDIATION_REQUIRED')),

    -- Technical Integrity (ADR-004)
    technical_integrity_verified BOOLEAN DEFAULT FALSE,
    commit_hash_frozen TEXT,
    determinism_variance_pct NUMERIC(5,4),
    dependency_fingerprint TEXT,

    -- Economic Safety (ADR-012)
    economic_safety_verified BOOLEAN DEFAULT FALSE,
    nlv_accounting_identity_verified BOOLEAN DEFAULT FALSE,
    circuit_breakers_tested BOOLEAN DEFAULT FALSE,
    stress_scenarios_passed INTEGER DEFAULT 0,
    max_adverse_excursion NUMERIC(10,4),

    -- Data Lineage (ADR-013)
    lineage_integrity_verified BOOLEAN DEFAULT FALSE,
    canonical_asset_resolution_verified BOOLEAN DEFAULT FALSE,
    state_hash_reproducibility_verified BOOLEAN DEFAULT FALSE,

    -- FORTRESS (ADR-011)
    fortress_compliance_verified BOOLEAN DEFAULT FALSE,
    fortress_baseline_drift_pct NUMERIC(5,4),
    invariants_passed INTEGER DEFAULT 0,
    invariants_total INTEGER DEFAULT 0,

    -- Secrets Security (NEW)
    secrets_security_verified BOOLEAN DEFAULT FALSE,
    vault_injection_only BOOLEAN DEFAULT FALSE,
    no_secret_leakage_verified BOOLEAN DEFAULT FALSE,
    introspection_safe BOOLEAN DEFAULT FALSE,

    -- Artifacts
    technical_report_path TEXT,
    economic_dossier_path TEXT,
    lineage_report_path TEXT,
    secrets_report_path TEXT,
    vega_bundle_path TEXT,

    -- Review Decision
    vega_decision TEXT CHECK (vega_decision IN ('G4_PASS', 'G4_FAIL', 'REMEDIATION_REQUIRED', NULL)),
    vega_decision_at TIMESTAMPTZ,
    vega_notes TEXT,

    -- CEO Sign-off
    ceo_signature BOOLEAN DEFAULT FALSE,
    ceo_signed_at TIMESTAMPTZ,

    -- Hash Chain
    lineage_hash TEXT NOT NULL,
    hash_self TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_governance.ios012_g4_review IS
'G4 Constitutional Activation Review tracking for IoS-012 Execution Engine. ADR-004 compliance.';

-- Insert initial review record
INSERT INTO fhq_governance.ios012_g4_review (
    review_id,
    review_initiated_by,
    review_status,
    lineage_hash,
    hash_self
) VALUES (
    'IOS012-G4-REVIEW-' || to_char(NOW(), 'YYYYMMDD'),
    'CEO',
    'INITIATED',
    'IOS012-G4-REVIEW-INIT-' || NOW()::TEXT,
    encode(sha256(('IOS012-G4-REVIEW-INIT-' || NOW()::TEXT)::bytea), 'hex')
);

-- ============================================================
-- SECTION 5: G4 REVIEW CONSTRAINTS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.g4_review_constraints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ios_id TEXT NOT NULL,
    review_id TEXT NOT NULL,

    -- Constraints During Review
    execution_authority_off BOOLEAN NOT NULL DEFAULT TRUE,
    no_outbound_trades BOOLEAN NOT NULL DEFAULT TRUE,
    no_capital_modification BOOLEAN NOT NULL DEFAULT TRUE,
    no_exposure_modification BOOLEAN NOT NULL DEFAULT TRUE,
    api_sandbox_only BOOLEAN NOT NULL DEFAULT TRUE,
    no_dynamic_config BOOLEAN NOT NULL DEFAULT TRUE,
    no_unreviewed_commits BOOLEAN NOT NULL DEFAULT TRUE,

    -- Violation Tracking
    constraint_violations INTEGER DEFAULT 0,
    defcon_triggered BOOLEAN DEFAULT FALSE,
    defcon_level TEXT,

    -- Enforcement
    enforced_by TEXT NOT NULL DEFAULT 'STIG',
    enforcement_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    enforcement_ended_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_governance.g4_review_constraints IS
'G4 review constraints enforcement. Any violation triggers ADR-016 DEFCON-2.';

-- Insert constraints record
INSERT INTO fhq_governance.g4_review_constraints (
    ios_id,
    review_id,
    enforced_by
) VALUES (
    'IoS-012',
    'IOS012-G4-REVIEW-' || to_char(NOW(), 'YYYYMMDD'),
    'STIG'
);

-- ============================================================
-- SECTION 6: VERIFICATION QUERIES
-- ============================================================

-- Verify IoS-012 governance state updated
SELECT 'IoS-012 Governance State' AS verification,
       ios_id, status, governance_state, immutability_level, modification_requires
FROM fhq_meta.ios_registry
WHERE ios_id = 'IoS-012';

-- Verify governance action logged
SELECT 'G4 Review Action Logged' AS verification,
       action_type, action_target, initiated_by, decision, hash_chain_id
FROM fhq_governance.governance_actions_log
WHERE action_target = 'IoS-012' AND action_type = 'G4_REVIEW_INITIATED'
ORDER BY initiated_at DESC
LIMIT 1;

-- Verify review tracking record
SELECT 'G4 Review Tracking' AS verification,
       review_id, review_status, review_initiated_by
FROM fhq_governance.ios012_g4_review
ORDER BY created_at DESC
LIMIT 1;

-- Verify constraints enforcement
SELECT 'G4 Review Constraints' AS verification,
       ios_id, execution_authority_off, no_outbound_trades, api_sandbox_only
FROM fhq_governance.g4_review_constraints
WHERE ios_id = 'IoS-012'
ORDER BY created_at DESC
LIMIT 1;

COMMIT;

-- ============================================================
-- MIGRATION COMPLETE: IoS-012 G4 REVIEW INITIATION
-- ============================================================
-- Status: G4_REVIEW_PENDING
-- Execution Authority: OFF
-- Constraints: ENFORCED
-- Next Step: STIG produces G4 artifacts for VEGA review
-- ============================================================
