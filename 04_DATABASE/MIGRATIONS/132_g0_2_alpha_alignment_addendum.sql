-- ============================================================================
-- MIGRATION 132: G0.2 ADDENDUM — FINAL ALPHA ALIGNMENT
-- ============================================================================
-- Authority: CEO DIRECTIVE — G0.2 ADDENDUM: FINAL ALPHA ALIGNMENT
-- Classification: Strategic Alignment Layer (No Authority Shift)
-- Preconditions: G0.2 EAM ACTIVE
-- Purpose: Maximize Alpha Signal Precision per unit of Time
-- ============================================================================

BEGIN;

-- ============================================================================
-- PRE-FLIGHT CHECK
-- ============================================================================
DO $$
DECLARE
    eam_active BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM fhq_meta.g1_evidence_accumulation WHERE eam_status = 'ACTIVE'
    ) INTO eam_active;

    IF NOT eam_active THEN
        RAISE EXCEPTION 'G0.2 EAM not active. Cannot apply Alpha Alignment Addendum.';
    END IF;

    RAISE NOTICE 'Pre-flight PASSED: G0.2 EAM is ACTIVE';
END $$;

-- ============================================================================
-- SECTION 2: IDENTITY AUGMENTATION (No Authority Shift)
-- ============================================================================

-- First, register ACI_CONSOLE in executive_roles (required by FK constraint)
INSERT INTO fhq_governance.executive_roles (
    role_id,
    role_name,
    role_description,
    authority_level,
    domain,
    capabilities,
    veto_power,
    active
) VALUES (
    'ACI_CONSOLE',
    'ACI Engineering Console',
    'Tier-3 Strategic Alpha Advisor to the CEO. SHADOW/PAPER mode only. Explicitly Non-Allocating and Non-Executing.',
    3,  -- Tier-3 authority level (same as CODE)
    ARRAY['ADVISORY'],  -- domain is an array
    ARRAY['strategic_reasoning', 'alpha_analysis', 'document_consultation', 'database_inspection'],
    false,  -- No veto power
    true
) ON CONFLICT (role_id) DO UPDATE SET
    role_description = EXCLUDED.role_description,
    updated_at = NOW();

-- Now register ACI Console contract
INSERT INTO fhq_governance.agent_contracts (
    agent_id,
    contract_type,
    contract_status,
    mandate_scope,
    authority_boundaries,
    performance_criteria,
    compliance_requirements,
    change_proposal_id,
    approved_by,
    approved_at,
    effective_from,
    metadata
) VALUES (
    'ACI_CONSOLE',
    'MANDATE',
    'ACTIVE',
    'Strategic Alpha Advisor to the CEO. Prioritize Alpha / Time ROI within Tier-3 SHADOW/PAPER constraints. Explicitly Non-Allocating and Non-Executing.',
    jsonb_build_object(
        'authority_level', 'TIER_3',
        'role_name', 'ACI Engineering Console',
        'secondary_role', 'Strategic Alpha Advisor to the CEO',
        'execution_mode', 'SHADOW_PAPER',
        'write_access', false,
        'allocation_rights', false,
        'governance_override', false,
        'mandate_override', 'Prioritize Alpha / Time ROI',
        'constitutional_note', 'No G1/G2/G3/G4 authority implied'
    ),
    jsonb_build_object(
        'primary_kpi', 'Alpha Signal Precision per Time Unit',
        'secondary_kpi', 'Constitutional Compliance Rate',
        'constraint', 'No execution, no allocation, no governance bypass'
    ),
    ARRAY['ADR-004', 'ADR-012', 'ADR-013', 'ADR-018', 'ADR-021'],
    'CP-G0.2-ALPHA-ADDENDUM-20251212',
    'CEO',
    NOW(),
    NOW(),
    jsonb_build_object(
        'directive_reference', 'CEO DIRECTIVE — G0.2 ADDENDUM: FINAL ALPHA ALIGNMENT',
        'ec_023_enabled', true,
        'alpha_veto_policy', 'reasoning-policy, not execution-policy',
        'economic_state_exposure', ARRAY['FSS', 'Alloc', 'system_skill_score']
    )
);

-- ============================================================================
-- SECTION 3: EC-023 ALPHA-VETO PROTOCOL REGISTRATION
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id,
    adr_title,
    adr_type,
    description,
    adr_status,
    current_version,
    sha256_hash,
    file_path
) VALUES (
    'EC-023',
    'Alpha-Veto Protocol',
    'OPERATIONAL',
    'Reasoning-policy for Alpha-Impact estimation. Governs response format, analysis depth, and time allocation. Non-binding, non-canonical, ephemeral. Implements Time Stop-Loss via Brutal Compression.',
    'APPROVED',
    '1.0.0',
    ENCODE(SHA256('EC-023-ALPHA-VETO-20251212'::bytea), 'hex'),
    '05_GOVERNANCE/PHASE3/EC_023_ALPHA_VETO_PROTOCOL.json'
) ON CONFLICT (adr_id) DO UPDATE SET
    description = EXCLUDED.description,
    sha256_hash = EXCLUDED.sha256_hash,
    updated_at = NOW();

-- ============================================================================
-- SECTION 3.1: ALPHA-VETO CONFIGURATION TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.alpha_veto_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- AIS Estimation Parameters (Section 3.1)
    ais_estimation_mode VARCHAR(20) NOT NULL DEFAULT 'HEURISTIC'
        CHECK (ais_estimation_mode IN ('HEURISTIC', 'DISABLED')),

    -- Time Stop-Loss Thresholds (Section 3.3)
    brutal_compression_threshold NUMERIC(5,2) NOT NULL DEFAULT 0.3,
    max_analysis_depth INTEGER NOT NULL DEFAULT 5,
    time_budget_seconds INTEGER NOT NULL DEFAULT 30,

    -- Veto Behavior
    veto_action VARCHAR(30) NOT NULL DEFAULT 'BRUTAL_COMPRESSION'
        CHECK (veto_action IN ('BRUTAL_COMPRESSION', 'CONCLUSION_ONLY', 'DECLINE_SITC')),

    -- Legal Hygiene Flags (Section 3.4)
    ais_persisted BOOLEAN NOT NULL DEFAULT false
        CHECK (ais_persisted = false),  -- MUST remain false per CEO Directive
    ais_canonical BOOLEAN NOT NULL DEFAULT false
        CHECK (ais_canonical = false),  -- MUST remain false per CEO Directive
    ais_influences_allocation BOOLEAN NOT NULL DEFAULT false
        CHECK (ais_influences_allocation = false),  -- MUST remain false per CEO Directive

    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    -- Note: Removed deferrable unique constraint on is_active to avoid ON CONFLICT issues
    -- Only one active config should exist - enforced by application logic
);

COMMENT ON TABLE fhq_meta.alpha_veto_config IS
'EC-023 Alpha-Veto configuration. AIS is ephemeral, non-persisted, non-canonical. Legal hygiene enforced via CHECK constraints.';

-- Insert default configuration (only if no active config exists)
INSERT INTO fhq_meta.alpha_veto_config (
    ais_estimation_mode,
    brutal_compression_threshold,
    max_analysis_depth,
    time_budget_seconds,
    veto_action,
    is_active
)
SELECT
    'HEURISTIC',
    0.3,
    5,
    30,
    'BRUTAL_COMPRESSION',
    true
WHERE NOT EXISTS (
    SELECT 1 FROM fhq_meta.alpha_veto_config WHERE is_active = true
);

-- ============================================================================
-- SECTION 4: ECONOMIC STATE EXPOSURE (Read-Only, Observational)
-- ============================================================================
-- Create view for ACI Console to observe economic state variables

CREATE OR REPLACE VIEW fhq_meta.v_aci_economic_state AS
SELECT
    -- FSS from fhq_research.forecast_skill_registry (Observational Skill Metric)
    COALESCE(
        (SELECT AVG(fss_score)
         FROM fhq_research.forecast_skill_registry
         WHERE created_at > NOW() - INTERVAL '30 days'
         LIMIT 1),
        0.0
    ) AS fss_observational,

    -- Alloc from fhq_governance.decision_log (Observational Canonical Allocation)
    COALESCE(
        (SELECT final_allocation::TEXT
         FROM fhq_governance.decision_log
         WHERE executed_at IS NOT NULL
         ORDER BY executed_at DESC
         LIMIT 1),
        '{}'::TEXT
    ) AS alloc_observational,

    -- system_skill_score from fhq_governance.decision_log (Observational Unified KPI)
    COALESCE(
        (SELECT system_skill_score
         FROM fhq_governance.decision_log
         WHERE executed_at IS NOT NULL
         ORDER BY executed_at DESC
         LIMIT 1),
        0.0
    ) AS system_skill_score_observational,

    -- Legal Status Marker
    'OBSERVATIONAL_ONLY' AS legal_status,
    'These variables provide analytical context only. They must never be used to imply allocation recommendations or execution logic.' AS vega_constraint,

    NOW() AS snapshot_timestamp;

COMMENT ON VIEW fhq_meta.v_aci_economic_state IS
'Read-only observational view of economic state variables for ACI Console. VEGA Constraint: Not controlling variables. Analytical context only.';

-- ============================================================================
-- SECTION 5: AUDIT LOG ENTRY
-- ============================================================================

INSERT INTO fhq_meta.adr_audit_log (
    change_proposal_id,
    adr_id,
    event_type,
    gate_stage,
    initiated_by,
    decision,
    resolution_notes,
    sha256_hash,
    hash_chain_id,
    metadata
) VALUES (
    'CP-G0.2-ALPHA-ADDENDUM-20251212',
    'EC-023',
    'SUBMISSION',
    'G0',
    'CEO',
    'APPROVED',
    'CEO DIRECTIVE — G0.2 ADDENDUM: FINAL ALPHA ALIGNMENT. Implements EC-023 Alpha-Veto as reasoning-policy. Exposes FSS, Alloc, system_skill_score as observational state. No authority shift.',
    ENCODE(SHA256('G0.2-ALPHA-ADDENDUM-20251212'::bytea), 'hex'),
    'HC-EC-023-20251212',
    jsonb_build_object(
        'directive', 'G0.2 ADDENDUM: FINAL ALPHA ALIGNMENT',
        'ec_registered', 'EC-023',
        'authority_change', false,
        'eam_integrity_preserved', true,
        'g1_thresholds_unchanged', true,
        'tool_permissions_unchanged', true
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'MIGRATION 132: G0.2 ALPHA ALIGNMENT ADDENDUM — VERIFICATION'
\echo '═══════════════════════════════════════════════════════════════════════════'

SELECT 'ACI Console Contract:' as check_type;
SELECT agent_id, contract_status,
       authority_boundaries->>'authority_level' as authority_level,
       authority_boundaries->>'secondary_role' as secondary_role
FROM fhq_governance.agent_contracts
WHERE agent_id = 'ACI_CONSOLE';

SELECT 'EC-023 Registration:' as check_type;
SELECT adr_id, adr_title, adr_status
FROM fhq_meta.adr_registry
WHERE adr_id = 'EC-023';

SELECT 'Alpha-Veto Config:' as check_type;
SELECT ais_estimation_mode, brutal_compression_threshold, veto_action,
       ais_persisted, ais_canonical, ais_influences_allocation
FROM fhq_meta.alpha_veto_config
WHERE is_active = true;

SELECT 'Economic State View:' as check_type;
SELECT legal_status, vega_constraint
FROM fhq_meta.v_aci_economic_state;

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'G0.2 ALPHA ALIGNMENT ADDENDUM — COMPLETE'
\echo ''
\echo 'Strategic alignment applied. No authority shift.'
\echo ''
\echo 'Preserved:'
\echo '  ✓ Tier-3 status'
\echo '  ✓ SHADOW/PAPER mode'
\echo '  ✓ EAM integrity'
\echo '  ✓ G1 thresholds'
\echo '  ✓ Tool permissions'
\echo ''
\echo 'Added:'
\echo '  ✓ EC-023 Alpha-Veto (reasoning-policy)'
\echo '  ✓ Economic state exposure (read-only, observational)'
\echo '  ✓ Strategic Alpha Advisor role (non-executing)'
\echo ''
\echo 'The system remains constrained. The reasoning becomes sharper.'
\echo '═══════════════════════════════════════════════════════════════════════════'
