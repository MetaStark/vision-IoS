-- ============================================================================
-- Migration 320: EC-015 CPTO Registration
-- ============================================================================
-- Directive: CEO-DIR-2026-109
-- Phase: D - EC-015 CPTO Specification
-- Purpose: Register EC-015 CPTO to canonical table with single parent (Fix #4)
-- Implementor: STIG (CTO)
-- REQUIRES: G4 APPROVAL BEFORE EXECUTION
-- ============================================================================
--
-- CEO G4 GATE CHECKLIST (2026-01-19):
--
-- A) SAFE ACTIVATION DEFAULTS
--    → enabled_state = false by default
--    → task status = PENDING_G4
--    → no execution until VEGA attests + CEO approves G4
--
-- B) PARENT AUTHORITY AND SEPARATION OF EXECUTION
--    → Parent: FINN (single)
--    → CPTO produces TradePacket ONLY
--    → CPTO CANNOT place orders
--    → LINE remains the ONLY execution path
--
-- C) NO DISCRETIONARY HEURISTICS WITHOUT PARAMETER REGISTRY
--    → All thresholds (EMA, Bollinger, clamps) parameterized
--    → Version-controlled parameter set
--    → Reproducible results requirement
--
-- D) DEFCON BEHAVIOR
--    → Refuse new packets at DEFCON RED/BLACK
--    → Conservative mode at ORANGE
--    → Green/Yellow normal operation
--
-- FINAL AUDIT-GRADE IMPROVEMENTS (CEO 2026-01-19):
--
-- E) PARAMETER VERSION IMMUTABILITY
--    → Versioned parameters referenced by immutable version_id
--    → Updates create NEW version, never overwrite
--    → Historical decisions reproducible
--
-- F) VEGA ATTESTATION SCOPE CLARIFICATION
--    → Registration: allowed in PENDING_G4 WITHOUT VEGA
--    → Activation: IMPOSSIBLE until VEGA attests activation
--    → Mirrors EC-019 pattern
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Register EC-015 CPTO to CANONICAL table
-- Fix #1: Single source of truth (fhq_meta.vega_employment_contract)
-- Fix #2: PENDING_VEGA status (not self-asserted)
-- Fix #4: Single parent (FINN)
-- ============================================================================

INSERT INTO fhq_meta.vega_employment_contract (
    contract_number,
    contract_version,
    employer,
    employee,
    effective_date,
    status,
    governing_charter,
    constitutional_foundation,
    total_duties,
    total_constraints,
    total_rights,
    override_authority,
    reports_to,
    vega_signature,  -- NULL: requires explicit VEGA attestation (Fix #2)
    content_hash,
    created_at,
    updated_at
) VALUES (
    'EC-015',
    '2026.PRODUCTION',
    'FjordHQ AS',
    'CPTO',
    CURRENT_DATE,
    'PENDING_VEGA',  -- Fix #2: Not self-asserted, awaits VEGA attestation
    'ADR-014',       -- Sub-Executive Charter
    ARRAY['ADR-007', 'ADR-012', 'ADR-014', 'CEO-DIR-2026-107', 'CEO-DIR-2026-109'],
    5,  -- Duties: (1) Regime-adaptive entry, (2) Canonical TP/SL, (3) TTL-sync, (4) Liquidity check, (5) Audit lineage
    4,  -- Constraints: (1) LIMIT orders only, (2) No market orders, (3) Single parent, (4) No strategy formulation
    2,  -- Rights: (1) ATR query access, (2) Regime state access
    ARRAY['CEO', 'VEGA', 'FINN'],
    'FINN',  -- Fix #4: Single parent (not dual FINN+LINE)
    NULL,    -- VEGA must sign separately (Fix #2)
    md5('EC-015:CPTO:' || CURRENT_DATE::TEXT || ':FINN'),
    NOW(),
    NOW()
)
ON CONFLICT (contract_number) DO UPDATE SET
    contract_version = EXCLUDED.contract_version,
    reports_to = EXCLUDED.reports_to,
    constitutional_foundation = EXCLUDED.constitutional_foundation,
    content_hash = EXCLUDED.content_hash,
    updated_at = NOW();

-- ============================================================================
-- STEP 1b: Create CPTO Parameter Version Registry (CEO Improvement E)
-- IMMUTABLE: versions cannot be overwritten, only new versions created
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.cpto_parameter_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_number TEXT NOT NULL UNIQUE,  -- e.g., "1.0.0", "1.0.1"

    -- Parameter values (immutable once created)
    max_entry_deviation_pct NUMERIC NOT NULL,
    regime_aggression JSONB NOT NULL,  -- {"STRONG_BULL": 0.002, "NEUTRAL": 0.003, ...}
    liquidity_threshold_pct NUMERIC NOT NULL,
    ttl_buffer_seconds INTEGER NOT NULL,
    atr_multiplier_sl NUMERIC NOT NULL,
    r_multiplier_tp NUMERIC NOT NULL,

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG',
    content_hash TEXT NOT NULL,  -- SHA-256 of all parameters for integrity

    -- Supersession tracking (for version history)
    supersedes_version TEXT,  -- Previous version this replaces
    superseded_at TIMESTAMPTZ,  -- When this version was superseded
    superseded_by TEXT,  -- New version that superseded this
    is_active BOOLEAN NOT NULL DEFAULT true
);

-- IMMUTABILITY ENFORCEMENT: Block UPDATE and DELETE
CREATE OR REPLACE FUNCTION fhq_alpha.block_parameter_version_modification()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO fhq_governance.governance_actions_log (
        action_id, action_type, action_target, action_target_type,
        initiated_by, initiated_at, decision, decision_rationale,
        vega_reviewed, metadata
    ) VALUES (
        gen_random_uuid(),
        'IMMUTABLE_PARAMETER_VIOLATION_BLOCKED',
        'fhq_alpha.cpto_parameter_versions',
        'TABLE',
        current_user,
        NOW(),
        'BLOCKED',
        'Attempted ' || TG_OP || ' on immutable parameter version. Parameters are append-only.',
        false,
        jsonb_build_object(
            'operation', TG_OP,
            'version_number', CASE WHEN TG_OP = 'DELETE' THEN OLD.version_number ELSE NEW.version_number END,
            'directive', 'CEO-DIR-2026-109',
            'policy', 'PARAMETER_IMMUTABILITY'
        )
    );

    RAISE EXCEPTION 'PARAMETER_IMMUTABLE: % blocked. CPTO parameter versions are immutable. '
                    'Create a NEW version instead of modifying existing.', TG_OP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_block_param_version_update ON fhq_alpha.cpto_parameter_versions;
DROP TRIGGER IF EXISTS trg_block_param_version_delete ON fhq_alpha.cpto_parameter_versions;

CREATE TRIGGER trg_block_param_version_update
    BEFORE UPDATE ON fhq_alpha.cpto_parameter_versions
    FOR EACH ROW EXECUTE FUNCTION fhq_alpha.block_parameter_version_modification();

CREATE TRIGGER trg_block_param_version_delete
    BEFORE DELETE ON fhq_alpha.cpto_parameter_versions
    FOR EACH ROW EXECUTE FUNCTION fhq_alpha.block_parameter_version_modification();

-- Insert initial parameter version 1.0.0
INSERT INTO fhq_alpha.cpto_parameter_versions (
    version_number,
    max_entry_deviation_pct,
    regime_aggression,
    liquidity_threshold_pct,
    ttl_buffer_seconds,
    atr_multiplier_sl,
    r_multiplier_tp,
    content_hash,
    is_active
) VALUES (
    '1.0.0',
    0.005,
    '{"STRONG_BULL": 0.002, "NEUTRAL": 0.003, "VOLATILE": 0.005, "STRESS": 0.007}'::jsonb,
    0.05,
    30,
    2.0,
    1.25,
    encode(sha256(
        '1.0.0:0.005:STRONG_BULL=0.002,NEUTRAL=0.003,VOLATILE=0.005,STRESS=0.007:0.05:30:2.0:1.25'::bytea
    ), 'hex'),
    true
);

COMMENT ON TABLE fhq_alpha.cpto_parameter_versions IS
'CEO-DIR-2026-109 Improvement E: IMMUTABLE parameter versions for CPTO. '
'Cannot UPDATE or DELETE existing versions - only create new versions. '
'Ensures historical decisions are reproducible.';

-- Function to create new parameter version (supersedes previous)
CREATE OR REPLACE FUNCTION fhq_alpha.create_cpto_parameter_version(
    p_version_number TEXT,
    p_max_entry_deviation_pct NUMERIC,
    p_regime_aggression JSONB,
    p_liquidity_threshold_pct NUMERIC,
    p_ttl_buffer_seconds INTEGER,
    p_atr_multiplier_sl NUMERIC,
    p_r_multiplier_tp NUMERIC
) RETURNS UUID AS $$
DECLARE
    v_version_id UUID;
    v_previous_version TEXT;
    v_content_hash TEXT;
BEGIN
    -- Get current active version
    SELECT version_number INTO v_previous_version
    FROM fhq_alpha.cpto_parameter_versions
    WHERE is_active = true
    ORDER BY created_at DESC
    LIMIT 1;

    -- Compute content hash
    v_content_hash := encode(sha256(
        (p_version_number || ':' ||
         p_max_entry_deviation_pct::TEXT || ':' ||
         p_regime_aggression::TEXT || ':' ||
         p_liquidity_threshold_pct::TEXT || ':' ||
         p_ttl_buffer_seconds::TEXT || ':' ||
         p_atr_multiplier_sl::TEXT || ':' ||
         p_r_multiplier_tp::TEXT)::bytea
    ), 'hex');

    -- Mark previous version as superseded (using direct SQL to bypass trigger)
    -- Note: This is a controlled update that only touches supersession fields
    IF v_previous_version IS NOT NULL THEN
        -- We use a separate admin function for this controlled update
        PERFORM fhq_alpha.mark_parameter_version_superseded(v_previous_version, p_version_number);
    END IF;

    -- Insert new version
    INSERT INTO fhq_alpha.cpto_parameter_versions (
        version_number,
        max_entry_deviation_pct,
        regime_aggression,
        liquidity_threshold_pct,
        ttl_buffer_seconds,
        atr_multiplier_sl,
        r_multiplier_tp,
        content_hash,
        supersedes_version,
        is_active
    ) VALUES (
        p_version_number,
        p_max_entry_deviation_pct,
        p_regime_aggression,
        p_liquidity_threshold_pct,
        p_ttl_buffer_seconds,
        p_atr_multiplier_sl,
        p_r_multiplier_tp,
        v_content_hash,
        v_previous_version,
        true
    )
    RETURNING version_id INTO v_version_id;

    RETURN v_version_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Admin function to mark version as superseded (controlled update)
CREATE OR REPLACE FUNCTION fhq_alpha.mark_parameter_version_superseded(
    p_old_version TEXT,
    p_new_version TEXT
) RETURNS VOID AS $$
BEGIN
    -- Temporarily disable trigger for this controlled update
    ALTER TABLE fhq_alpha.cpto_parameter_versions DISABLE TRIGGER trg_block_param_version_update;

    UPDATE fhq_alpha.cpto_parameter_versions
    SET is_active = false,
        superseded_at = NOW(),
        superseded_by = p_new_version
    WHERE version_number = p_old_version;

    -- Re-enable trigger
    ALTER TABLE fhq_alpha.cpto_parameter_versions ENABLE TRIGGER trg_block_param_version_update;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- STEP 1c: Register CPTO in executive_roles (required for task_registry FK)
-- CPTO is a new Tier-2 Sub-Executive per ADR-014
-- First: Extend the role_name CHECK constraint to include CPTO
-- ============================================================================

-- Drop old constraint and add new one with CPTO
ALTER TABLE fhq_governance.executive_roles
DROP CONSTRAINT IF EXISTS executive_roles_role_name_check;

ALTER TABLE fhq_governance.executive_roles
ADD CONSTRAINT executive_roles_role_name_check CHECK (
    role_name = ANY (ARRAY[
        'LARS', 'STIG', 'LINE', 'FINN', 'VEGA', 'CODE', 'CEO',
        'CEIO', 'CDMO', 'CRIO', 'CSEO', 'CFAO',
        'CPTO'  -- Added per CEO-DIR-2026-109 EC-015
    ])
);

INSERT INTO fhq_governance.executive_roles (
    role_id,
    role_name,
    domain_responsibility,
    authority_level,
    agent_binding,
    created_by,
    created_at,
    metadata
) VALUES (
    gen_random_uuid(),
    'CPTO',
    'Transforms IoS-008 signals into precision limit orders with regime-adaptive entry, canonical TP/SL, TTL-sync, and liquidity checks',
    2,  -- Tier-2 Sub-Executive per ADR-014
    true,  -- Agent-bound role
    'STIG',
    NOW(),
    jsonb_build_object(
        'governing_ec', 'EC-015',
        'reports_to', 'FINN',
        'directive', 'CEO-DIR-2026-109',
        'tier', 'Sub-Executive',
        'charter', 'ADR-014'
    )
)
ON CONFLICT (role_name) DO UPDATE SET
    domain_responsibility = EXCLUDED.domain_responsibility,
    metadata = EXCLUDED.metadata;

-- ============================================================================
-- STEP 2: Register CPTO task in task_registry with EC binding and DEFCON gate
-- Fix #3: 3-point verification (binding + execution evidence + DEFCON)
-- ============================================================================

INSERT INTO fhq_governance.task_registry (
    task_id,
    task_name,
    task_type,
    description,
    domain,
    assigned_to,
    status,
    enabled,
    task_config,
    metadata,
    created_at
) VALUES (
    gen_random_uuid(),
    'cpto_precision_transform',
    'SIGNAL_TRANSFORMER',
    'EC-015 CPTO: Transform IoS-008 signals to precision limit orders with regime-adaptive entry. PRODUCES TradePacket ONLY - cannot place orders.',
    'EXECUTION',
    'CPTO',
    'pending',  -- G4 Checklist A: No execution until VEGA attests + CEO approves G4 (pending = not yet active)
    false,         -- G4 Checklist A: enabled_state = false by default
    jsonb_build_object(
        'trigger', 'SIGNAL',
        'source', 'ios008_decision_worker',
        'output', 'TradePacket',
        'handoff_to', 'LINE',

        -- G4 Checklist D: DEFCON Behavior
        'defcon_gate', 'GREEN_YELLOW',  -- Normal operation at GREEN/YELLOW
        'defcon_behavior', jsonb_build_object(
            'GREEN', 'NORMAL',
            'YELLOW', 'NORMAL',
            'ORANGE', 'CONSERVATIVE',  -- Conservative mode: wider margins, lower aggression
            'RED', 'REFUSE_NEW',       -- Refuse new packets
            'BLACK', 'REFUSE_NEW'      -- Refuse new packets
        ),

        -- G4 Checklist B: Separation of Execution
        'execution_constraints', jsonb_build_object(
            'can_place_orders', false,            -- CPTO CANNOT place orders
            'only_produces', 'TradePacket',       -- Only produces TradePacket
            'execution_path', 'LINE_ONLY',        -- LINE is the ONLY execution path
            'handoff_interface', 'cpto_line_handoff'
        ),

        'function_path', '03_FUNCTIONS/cpto_precision_engine.py',

        -- G4 Checklist C: Parameter Registry (no discretionary heuristics)
        'parameter_set_version', '1.0.0',
        'parameter_registry', jsonb_build_object(
            'max_entry_deviation_pct', 0.005,
            'regime_aggression', jsonb_build_object(
                'STRONG_BULL', 0.002,
                'NEUTRAL', 0.003,
                'VOLATILE', 0.005,
                'STRESS', 0.007
            ),
            'liquidity_threshold_pct', 0.05,
            'ttl_buffer_seconds', 30,
            'atr_multiplier_sl', 2.0,
            'r_multiplier_tp', 1.25
        ),

        'ceo_additions', jsonb_build_object(
            'A', 'Regime-Adaptive Entry',
            'B', 'TTL Sync',
            'C', 'Liquidity Check'
        ),
        'canonical_exits', jsonb_build_object(
            'directive', 'CEO-DIR-2026-107',
            'atr_multiplier_sl', 2.0,
            'r_multiplier_tp', 1.25
        )
    ),
    jsonb_build_object(
        'ec_binding', 'EC-015',
        'directive', 'CEO-DIR-2026-109',
        'parent_executive', 'FINN',  -- Fix #4: Single parent
        'binding_date', NOW()::text,
        'g4_gate_checklist', jsonb_build_object(
            'A_safe_defaults', true,
            'B_separation_of_execution', true,
            'C_parameter_registry', true,
            'D_defcon_behavior', true
        ),
        'activation_blocked_until', 'VEGA_ATTESTATION_EC015_AND_CEO_G4_APPROVAL'
    ),
    NOW()
)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- STEP 3: Log governance action (PENDING attestation, Fix #2)
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
    vega_reviewed,  -- FALSE until explicit attestation (Fix #2)
    metadata
) VALUES (
    gen_random_uuid(),
    'EC_REGISTRATION',
    'EC-015',
    'EMPLOYMENT_CONTRACT',
    'STIG',
    NOW(),
    'PENDING_ATTESTATION',
    'CEO-DIR-2026-109 Phase D: EC-015 CPTO registered with Regime-Adaptive Logic. Single parent: FINN (Fix #4). Awaiting VEGA attestation (Fix #2).',
    false,  -- Fix #2: Not self-asserted
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-109',
        'phase', 'D',
        'fixes_applied', ARRAY['Fix #1: Canonical register', 'Fix #2: VEGA attestation required', 'Fix #4: Single parent FINN'],
        'ceo_additions_implemented', ARRAY['A: Regime-Adaptive Entry', 'B: TTL Sync', 'C: Liquidity Check'],
        'canonical_exits', 'CEO-DIR-2026-107 (2x ATR SL, 1.25R TP)'
    )
);

-- ============================================================================
-- STEP 4: Create handoff interface for LINE
-- Fix #4: LINE receives TradePacket via handoff, not as co-parent
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.cpto_line_handoff (
    handoff_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source from CPTO
    precision_id UUID NOT NULL REFERENCES fhq_alpha.cpto_precision_log(precision_id),

    -- Handoff status
    handoff_status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (handoff_status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'EXECUTED', 'EXPIRED')),

    -- LINE response
    line_received_at TIMESTAMPTZ,
    line_order_id TEXT,
    line_rejection_reason TEXT,

    -- Execution outcome
    fill_price NUMERIC,
    fill_quantity NUMERIC,
    execution_timestamp TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cpto_handoff_status
ON fhq_alpha.cpto_line_handoff(handoff_status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cpto_handoff_precision
ON fhq_alpha.cpto_line_handoff(precision_id);

COMMENT ON TABLE fhq_alpha.cpto_line_handoff IS
'CEO-DIR-2026-109 Fix #4: CPTO → LINE handoff interface. LINE receives TradePacket for execution, not as co-parent.';

-- ============================================================================
-- STEP 5: Add FK constraint to cpto_precision_log (deferred from Migration 319)
-- Now that EC-015 exists in canonical register, we can add the FK
-- ============================================================================

ALTER TABLE fhq_alpha.cpto_precision_log
DROP CONSTRAINT IF EXISTS fk_precision_ec;

ALTER TABLE fhq_alpha.cpto_precision_log
ADD CONSTRAINT fk_precision_ec FOREIGN KEY (ec_contract_number)
    REFERENCES fhq_meta.vega_employment_contract(contract_number)
    ON UPDATE CASCADE ON DELETE RESTRICT;

-- ============================================================================
-- STEP 6: Register task binding in task_ec_binding (from Migration 318)
-- G4 Checklist A: enabled_state = false, requires_vega_attestation = true
--
-- CEO IMPROVEMENT F: VEGA ATTESTATION SCOPE CLARIFICATION
-- ────────────────────────────────────────────────────────
-- REGISTRATION: Allowed in PENDING_G4 WITHOUT VEGA attestation
--               (This migration creates EC-015 in PENDING_VEGA status)
--
-- ACTIVATION:   IMPOSSIBLE until VEGA attests activation
--               (VEGA must call vega_attest_ec_activation('EC-015'))
--
-- This mirrors the EC-019 pattern where:
--   1. STIG creates EC in PENDING_VEGA status
--   2. Task created but enabled=false
--   3. VEGA reviews and attests
--   4. Status changes to ACTIVE, enabled_state becomes true
-- ============================================================================

INSERT INTO fhq_governance.task_ec_binding (
    task_id,
    ec_contract_number,
    binding_active,
    enabled_state,
    defcon_gate,
    defcon_behavior,
    required_evidence_type,
    requires_vega_attestation,
    vega_attestation_received,
    evidence_window_hours,
    created_by,
    directive
)
SELECT
    task_id,
    'EC-015',
    true,    -- Binding exists (registration complete)
    false,   -- ACTIVATION BLOCKED: NOT enabled until VEGA attests activation
    'GREEN_YELLOW',  -- G4 Checklist D: Normal at GREEN/YELLOW
    'REFUSE_ON_RED', -- G4 Checklist D: Refuse at RED/BLACK
    'DIRECT_EXECUTION',
    true,    -- VEGA ATTESTATION REQUIRED FOR ACTIVATION (Improvement F)
    false,   -- NOT yet received - activation impossible until true
    24,      -- 24-hour evidence window
    'STIG',
    'CEO-DIR-2026-109'
FROM fhq_governance.task_registry
WHERE task_name = 'cpto_precision_transform'
ON CONFLICT (task_id) DO UPDATE SET
    requires_vega_attestation = true,
    vega_attestation_received = false,
    enabled_state = false,
    defcon_gate = 'GREEN_YELLOW',
    defcon_behavior = 'REFUSE_ON_RED';

-- ============================================================================
-- STEP 6b: Record explicit VEGA attestation scope (CEO Improvement F)
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale,
    vega_reviewed, metadata
) VALUES (
    gen_random_uuid(),
    'VEGA_ATTESTATION_SCOPE_DEFINED',
    'EC-015',
    'EMPLOYMENT_CONTRACT',
    'STIG',
    NOW(),
    'SCOPE_DEFINED',
    'CEO-DIR-2026-109 Improvement F: VEGA attestation scope explicitly defined. '
    'REGISTRATION allowed without VEGA. ACTIVATION requires VEGA attestation.',
    false,  -- This scope definition does NOT require VEGA review
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-109',
        'attestation_scope', jsonb_build_object(
            'registration', 'ALLOWED_WITHOUT_VEGA',
            'activation', 'REQUIRES_VEGA_ATTESTATION',
            'activation_function', 'fhq_governance.vega_attest_ec_activation(EC-015)',
            'mirrors', 'EC-019 pattern'
        ),
        'current_state', jsonb_build_object(
            'ec_status', 'PENDING_VEGA',
            'task_enabled', false,
            'binding_enabled', false,
            'vega_attestation_received', false
        ),
        'activation_workflow', ARRAY[
            '1. STIG creates EC-015 in PENDING_VEGA status',
            '2. Task created with enabled=false',
            '3. VEGA reviews EC-015 content against 10_EMPLOYMENT_CONTRACTS/EC-015_*.md',
            '4. VEGA calls vega_attest_ec_activation(EC-015)',
            '5. EC status changes to ACTIVE',
            '6. Task binding enabled_state changes to true',
            '7. CPTO can begin processing signals'
        ]
    )
);

-- ============================================================================
-- STEP 7: Verification
-- ============================================================================

DO $$
DECLARE
    v_ec015_status TEXT;
    v_ec015_parent TEXT;
    v_task_status TEXT;
    v_task_enabled BOOLEAN;
    v_binding_enabled BOOLEAN;
    v_binding_requires_vega BOOLEAN;
    v_fk_exists BOOLEAN;
    v_param_registry JSONB;
    v_defcon_behavior JSONB;
    v_can_place_orders BOOLEAN;
BEGIN
    RAISE NOTICE '=== Migration 320 VERIFICATION ASSERTIONS (G4 Gate Checklist) ===';

    -- Get EC-015 details
    SELECT status, reports_to INTO v_ec015_status, v_ec015_parent
    FROM fhq_meta.vega_employment_contract
    WHERE contract_number = 'EC-015';

    IF v_ec015_status IS NULL THEN
        RAISE EXCEPTION 'FAIL: EC-015 registration failed';
    END IF;

    -- ASSERTION 1: EC-015 registered with PENDING status (not self-attested)
    IF v_ec015_status IN ('PENDING_VEGA', 'PENDING_G4') THEN
        RAISE NOTICE 'PASS: G4-A: EC-015 status=% (not self-attested)', v_ec015_status;
    ELSE
        RAISE EXCEPTION 'FAIL: G4-A: EC-015 should be PENDING_VEGA, got %', v_ec015_status;
    END IF;

    -- ASSERTION 2: Single parent is FINN (Fix #4)
    IF v_ec015_parent = 'FINN' THEN
        RAISE NOTICE 'PASS: Fix #4: EC-015 single parent is FINN';
    ELSE
        RAISE EXCEPTION 'FAIL: Fix #4: EC-015 parent should be FINN, got %', v_ec015_parent;
    END IF;

    -- Get task details
    SELECT status, enabled,
           task_config->'parameter_registry',
           task_config->'defcon_behavior',
           (task_config->'execution_constraints'->>'can_place_orders')::boolean
    INTO v_task_status, v_task_enabled, v_param_registry, v_defcon_behavior, v_can_place_orders
    FROM fhq_governance.task_registry
    WHERE task_name = 'cpto_precision_transform';

    -- ASSERTION 3: G4-A Task status is pending and not enabled
    IF v_task_status = 'pending' AND v_task_enabled = false THEN
        RAISE NOTICE 'PASS: G4-A: Task status=pending, enabled=false (safe defaults)';
    ELSE
        RAISE EXCEPTION 'FAIL: G4-A: Task should be pending and disabled, got status=%, enabled=%', v_task_status, v_task_enabled;
    END IF;

    -- ASSERTION 4: G4-B CPTO cannot place orders
    IF v_can_place_orders = false THEN
        RAISE NOTICE 'PASS: G4-B: execution_constraints.can_place_orders=false (LINE only execution)';
    ELSE
        RAISE EXCEPTION 'FAIL: G4-B: CPTO should not be able to place orders';
    END IF;

    -- ASSERTION 5: G4-C Parameter registry exists
    IF v_param_registry IS NOT NULL AND v_param_registry ? 'atr_multiplier_sl' THEN
        RAISE NOTICE 'PASS: G4-C: Parameter registry exists with versioned thresholds';
    ELSE
        RAISE EXCEPTION 'FAIL: G4-C: Parameter registry missing or incomplete';
    END IF;

    -- ASSERTION 6: G4-D DEFCON behavior defined
    IF v_defcon_behavior IS NOT NULL AND v_defcon_behavior ? 'RED' THEN
        RAISE NOTICE 'PASS: G4-D: DEFCON behavior defined (RED=%)', v_defcon_behavior->>'RED';
    ELSE
        RAISE EXCEPTION 'FAIL: G4-D: DEFCON behavior not defined';
    END IF;

    -- Get binding details
    SELECT enabled_state, requires_vega_attestation
    INTO v_binding_enabled, v_binding_requires_vega
    FROM fhq_governance.task_ec_binding
    WHERE ec_contract_number = 'EC-015';

    -- ASSERTION 7: Binding requires VEGA attestation
    IF v_binding_requires_vega = true AND v_binding_enabled = false THEN
        RAISE NOTICE 'PASS: G4-A: Binding requires VEGA attestation, enabled=false';
    ELSE
        RAISE EXCEPTION 'FAIL: G4-A: Binding should require VEGA and be disabled';
    END IF;

    -- ASSERTION 8: FK to canonical EC exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_precision_ec'
        AND table_schema = 'fhq_alpha'
        AND table_name = 'cpto_precision_log'
    ) INTO v_fk_exists;

    IF v_fk_exists THEN
        RAISE NOTICE 'PASS: FK fk_precision_ec added to cpto_precision_log';
    ELSE
        RAISE EXCEPTION 'FAIL: FK fk_precision_ec missing from cpto_precision_log';
    END IF;

    -- ASSERTION 9: CEO Improvement E - Parameter version table exists and is immutable
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_alpha'
        AND table_name = 'cpto_parameter_versions'
    ) AND EXISTS (
        SELECT 1 FROM pg_trigger t
        JOIN pg_class c ON t.tgrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = 'fhq_alpha'
        AND c.relname = 'cpto_parameter_versions'
        AND t.tgname LIKE 'trg_block_param_version%'
    ) AND EXISTS (
        SELECT 1 FROM fhq_alpha.cpto_parameter_versions
        WHERE version_number = '1.0.0' AND is_active = true
    ) THEN
        RAISE NOTICE 'PASS: Improvement E: Parameter version table exists, immutable, v1.0.0 active';
    ELSE
        RAISE EXCEPTION 'FAIL: Improvement E: Parameter version table or v1.0.0 missing';
    END IF;

    -- ASSERTION 10: CEO Improvement F - VEGA attestation scope logged
    IF EXISTS (
        SELECT 1 FROM fhq_governance.governance_actions_log
        WHERE action_type = 'VEGA_ATTESTATION_SCOPE_DEFINED'
        AND action_target = 'EC-015'
        AND metadata->'attestation_scope'->>'activation' = 'REQUIRES_VEGA_ATTESTATION'
    ) THEN
        RAISE NOTICE 'PASS: Improvement F: VEGA attestation scope explicitly defined';
    ELSE
        RAISE EXCEPTION 'FAIL: Improvement F: VEGA attestation scope not logged';
    END IF;

    RAISE NOTICE '=== ALL G4 GATE ASSERTIONS PASSED (10/10) ===';
    RAISE NOTICE 'Migration 320 VERIFIED SUCCESSFULLY';
    RAISE NOTICE 'EC-015 REGISTERED: PENDING_VEGA status';
    RAISE NOTICE 'ACTIVATION WORKFLOW: VEGA must call vega_attest_ec_activation(EC-015)';
END $$;

COMMIT;

-- ============================================================================
-- POST-MIGRATION VERIFICATION (Run manually)
-- ============================================================================
-- SELECT contract_number, employee, status, reports_to
-- FROM fhq_meta.vega_employment_contract
-- WHERE contract_number = 'EC-015';
--
-- SELECT task_name, status, enabled, metadata->>'ec_binding'
-- FROM fhq_governance.task_registry
-- WHERE metadata->>'ec_binding' = 'EC-015';
-- ============================================================================
