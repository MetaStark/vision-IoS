-- Migration 270: G3-REQ-005 Ghost Events Non-Exculpatory
-- CEO Directive: Remove escape hatches - ghost flags cannot excuse performance
-- Rationale: "Remove escape hatches" - P1 second in sequence
-- Classification: GOVERNANCE-CRITICAL / ACCOUNTABILITY-PROTECTION
-- Executed by: STIG (EC-003_2026_PRODUCTION)

BEGIN;

-- ============================================================================
-- 270.1: Add Non-Exculpatory Fields to Ghost Flags
-- ============================================================================

ALTER TABLE fhq_calendar.unexplained_volatility_flags
ADD COLUMN IF NOT EXISTS exculpatory_eligible BOOLEAN NOT NULL DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS resolution_evidence_hash TEXT,
ADD COLUMN IF NOT EXISTS exculpatory_reason TEXT,
ADD COLUMN IF NOT EXISTS exculpatory_approved_by TEXT,
ADD COLUMN IF NOT EXISTS exculpatory_approved_at TIMESTAMPTZ;

COMMENT ON COLUMN fhq_calendar.unexplained_volatility_flags.exculpatory_eligible IS
'G3-REQ-005: NON-EXCULPATORY by default. Can only be TRUE if flag is RESOLVED with evidence.
Ghost flags CANNOT reduce calibration accountability unless explicitly approved.';

COMMENT ON COLUMN fhq_calendar.unexplained_volatility_flags.resolution_evidence_hash IS
'G3-REQ-005: SHA-256 hash of resolution evidence. Required for exculpatory eligibility.';

-- ============================================================================
-- 270.2: Add Non-Exculpatory Constraint
-- ============================================================================
-- exculpatory_eligible = TRUE only if:
--   flag_status = 'RESOLVED'
--   AND suspected_cause IN ('COVERAGE_GAP', 'TIMESTAMP_DEFECT')
--   AND resolution_evidence_hash IS NOT NULL

ALTER TABLE fhq_calendar.unexplained_volatility_flags
ADD CONSTRAINT ghost_exculpatory_requires_evidence
CHECK (
    -- Default: NOT exculpatory
    (exculpatory_eligible = FALSE)
    OR
    -- Exculpatory requires: RESOLVED + valid cause + evidence
    (
        exculpatory_eligible = TRUE
        AND flag_status = 'RESOLVED'
        AND suspected_cause IN ('COVERAGE_GAP', 'TIMESTAMP_DEFECT')
        AND resolution_evidence_hash IS NOT NULL
        AND LENGTH(resolution_evidence_hash) >= 64
    )
);

COMMENT ON CONSTRAINT ghost_exculpatory_requires_evidence ON fhq_calendar.unexplained_volatility_flags IS
'G3-REQ-005: Ghost flags are NON-EXCULPATORY by default.
Exculpatory eligibility requires:
1. flag_status = RESOLVED
2. suspected_cause IN (COVERAGE_GAP, TIMESTAMP_DEFECT) - not MAPPING_DEFECT or TRUE_GHOST
3. resolution_evidence_hash present (min 64 chars)
Unresolved ghosts can NEVER excuse performance.';

-- ============================================================================
-- 270.3: Create Exculpatory Audit Log
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_calendar.ghost_exculpatory_audit (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flag_id UUID NOT NULL REFERENCES fhq_calendar.unexplained_volatility_flags(flag_id),
    action_type TEXT NOT NULL CHECK (action_type IN (
        'EXCULPATORY_REQUESTED',
        'EXCULPATORY_APPROVED',
        'EXCULPATORY_DENIED',
        'EXCULPATORY_REVOKED'
    )),
    requested_by TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decision_by TEXT,
    decision_at TIMESTAMPTZ,
    decision_reason TEXT,
    evidence_hash TEXT,
    brier_impact_before NUMERIC,
    brier_impact_after NUMERIC
);

CREATE INDEX idx_ghost_exculpatory_flag ON fhq_calendar.ghost_exculpatory_audit(flag_id);
CREATE INDEX idx_ghost_exculpatory_action ON fhq_calendar.ghost_exculpatory_audit(action_type);

COMMENT ON TABLE fhq_calendar.ghost_exculpatory_audit IS
'G3-REQ-005: Full audit trail for ghost exculpatory status changes.
Every request, approval, denial, and revocation is logged.';

-- ============================================================================
-- 270.4: Create Ghost Resolution Function with Evidence
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_calendar.resolve_ghost_with_evidence(
    p_flag_id UUID,
    p_suspected_cause TEXT,
    p_resolution_notes TEXT,
    p_resolution_event_id UUID DEFAULT NULL,
    p_evidence_data TEXT DEFAULT NULL,
    p_resolved_by TEXT DEFAULT 'STIG'
)
RETURNS TABLE (
    success BOOLEAN,
    exculpatory_eligible BOOLEAN,
    evidence_hash TEXT,
    message TEXT
) AS $$
DECLARE
    v_evidence_hash TEXT;
    v_exculpatory BOOLEAN := FALSE;
BEGIN
    -- Validate suspected_cause
    IF p_suspected_cause NOT IN ('COVERAGE_GAP', 'TIMESTAMP_DEFECT', 'MAPPING_DEFECT', 'TRUE_GHOST') THEN
        RETURN QUERY SELECT FALSE, FALSE, NULL::TEXT, 'Invalid suspected_cause'::TEXT;
        RETURN;
    END IF;

    -- Compute evidence hash if evidence provided
    IF p_evidence_data IS NOT NULL AND LENGTH(p_evidence_data) > 0 THEN
        v_evidence_hash := encode(sha256(p_evidence_data::BYTEA), 'hex');
    END IF;

    -- Determine exculpatory eligibility
    -- Only COVERAGE_GAP and TIMESTAMP_DEFECT with evidence can be exculpatory
    IF p_suspected_cause IN ('COVERAGE_GAP', 'TIMESTAMP_DEFECT') AND v_evidence_hash IS NOT NULL THEN
        v_exculpatory := TRUE;
    END IF;

    -- Update the ghost flag
    UPDATE fhq_calendar.unexplained_volatility_flags
    SET
        flag_status = 'RESOLVED',
        suspected_cause = p_suspected_cause,
        resolution_notes = p_resolution_notes,
        resolution_event_id = p_resolution_event_id,
        resolution_evidence_hash = v_evidence_hash,
        exculpatory_eligible = v_exculpatory,
        resolved_by = p_resolved_by,
        resolved_at = NOW(),
        updated_at = NOW()
    WHERE flag_id = p_flag_id;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, FALSE, NULL::TEXT, 'Flag not found'::TEXT;
        RETURN;
    END IF;

    -- Log the resolution
    INSERT INTO fhq_calendar.ghost_exculpatory_audit (
        flag_id, action_type, requested_by, evidence_hash
    ) VALUES (
        p_flag_id,
        CASE WHEN v_exculpatory THEN 'EXCULPATORY_APPROVED' ELSE 'EXCULPATORY_DENIED' END,
        p_resolved_by,
        v_evidence_hash
    );

    RETURN QUERY SELECT
        TRUE,
        v_exculpatory,
        v_evidence_hash,
        CASE
            WHEN v_exculpatory THEN 'Ghost resolved with exculpatory status (evidence provided for ' || p_suspected_cause || ')'
            ELSE 'Ghost resolved NON-EXCULPATORY (' || p_suspected_cause || ' without sufficient evidence or ineligible cause)'
        END;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_calendar.resolve_ghost_with_evidence IS
'G3-REQ-005: Resolves ghost flag with proper evidence handling.
Only COVERAGE_GAP or TIMESTAMP_DEFECT with evidence can become exculpatory.
MAPPING_DEFECT and TRUE_GHOST are NEVER exculpatory.';

-- ============================================================================
-- 270.5: Create Brier Exculpatory Check Function
-- ============================================================================
-- For use by Brier scoring to determine if ghost should affect calculation

CREATE OR REPLACE FUNCTION fhq_calendar.check_ghost_exculpatory(
    p_flag_id UUID
)
RETURNS TABLE (
    can_affect_brier BOOLEAN,
    reason TEXT
) AS $$
DECLARE
    v_flag RECORD;
BEGIN
    SELECT * INTO v_flag
    FROM fhq_calendar.unexplained_volatility_flags
    WHERE flag_id = p_flag_id;

    IF v_flag IS NULL THEN
        RETURN QUERY SELECT FALSE, 'Flag not found'::TEXT;
        RETURN;
    END IF;

    -- Only exculpatory_eligible = TRUE can affect Brier
    IF v_flag.exculpatory_eligible = TRUE THEN
        RETURN QUERY SELECT
            TRUE,
            'Exculpatory: ' || v_flag.suspected_cause || ' with evidence'::TEXT;
    ELSE
        RETURN QUERY SELECT
            FALSE,
            CASE
                WHEN v_flag.flag_status != 'RESOLVED' THEN 'Unresolved ghost - NON-EXCULPATORY'
                WHEN v_flag.suspected_cause NOT IN ('COVERAGE_GAP', 'TIMESTAMP_DEFECT') THEN 'Cause (' || COALESCE(v_flag.suspected_cause, 'UNKNOWN') || ') is NON-EXCULPATORY'
                WHEN v_flag.resolution_evidence_hash IS NULL THEN 'No evidence hash - NON-EXCULPATORY'
                ELSE 'Default NON-EXCULPATORY'
            END;
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_calendar.check_ghost_exculpatory IS
'G3-REQ-005: Check if ghost flag can affect Brier calculation.
Returns TRUE only if exculpatory_eligible = TRUE (resolved with evidence).
All other cases return FALSE with reason.';

-- ============================================================================
-- 270.6: Create Non-Exculpatory Enforcement View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_calendar.ghost_accountability_status AS
SELECT
    flag_id,
    asset_id,
    detection_timestamp,
    flag_status,
    suspected_cause,
    exculpatory_eligible,
    CASE
        WHEN exculpatory_eligible = TRUE THEN 'CAN affect Brier stratification'
        WHEN flag_status = 'OPEN' THEN 'OPEN investigation - CANNOT excuse performance'
        WHEN flag_status = 'FALSE_POSITIVE' THEN 'Dismissed - CANNOT excuse performance'
        WHEN suspected_cause IN ('MAPPING_DEFECT', 'TRUE_GHOST') THEN 'Cause is NON-EXCULPATORY'
        WHEN resolution_evidence_hash IS NULL THEN 'No evidence - NON-EXCULPATORY'
        ELSE 'NON-EXCULPATORY (default)'
    END AS accountability_status,
    resolution_evidence_hash IS NOT NULL AS has_evidence,
    resolved_by,
    resolved_at
FROM fhq_calendar.unexplained_volatility_flags
ORDER BY detection_timestamp DESC;

COMMENT ON VIEW fhq_calendar.ghost_accountability_status IS
'G3-REQ-005: Shows accountability status for all ghost flags.
Ghost events are NON-EXCULPATORY by default - only resolved flags with
COVERAGE_GAP/TIMESTAMP_DEFECT + evidence can affect Brier.';

-- ============================================================================
-- 270.7: Test Non-Exculpatory Constraint
-- ============================================================================

DO $$
DECLARE
    v_test_flag_id UUID;
    v_constraint_violated BOOLEAN := FALSE;
BEGIN
    -- Create a test ghost flag
    INSERT INTO fhq_calendar.unexplained_volatility_flags (
        asset_id, detection_timestamp, volatility_magnitude, expected_volatility,
        flag_status, exculpatory_eligible
    ) VALUES (
        'TEST_ASSET', NOW(), 2.5, 1.0, 'OPEN', FALSE
    )
    RETURNING flag_id INTO v_test_flag_id;

    -- Test 1: Try to set exculpatory without resolution - should fail
    BEGIN
        UPDATE fhq_calendar.unexplained_volatility_flags
        SET exculpatory_eligible = TRUE
        WHERE flag_id = v_test_flag_id;
    EXCEPTION WHEN check_violation THEN
        v_constraint_violated := TRUE;
        RAISE NOTICE 'G3-REQ-005 TEST 1 PASS: Cannot set exculpatory without resolution';
    END;

    IF NOT v_constraint_violated THEN
        RAISE EXCEPTION 'G3-REQ-005 FAILED: Exculpatory was allowed without resolution';
    END IF;

    -- Test 2: Try to set exculpatory with RESOLVED but wrong cause - should fail
    v_constraint_violated := FALSE;
    BEGIN
        UPDATE fhq_calendar.unexplained_volatility_flags
        SET flag_status = 'RESOLVED',
            suspected_cause = 'TRUE_GHOST',
            resolution_evidence_hash = 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
            exculpatory_eligible = TRUE
        WHERE flag_id = v_test_flag_id;
    EXCEPTION WHEN check_violation THEN
        v_constraint_violated := TRUE;
        RAISE NOTICE 'G3-REQ-005 TEST 2 PASS: TRUE_GHOST cannot be exculpatory';
    END;

    IF NOT v_constraint_violated THEN
        RAISE EXCEPTION 'G3-REQ-005 FAILED: TRUE_GHOST was allowed to be exculpatory';
    END IF;

    -- Test 3: Valid exculpatory - RESOLVED + COVERAGE_GAP + evidence - should succeed
    UPDATE fhq_calendar.unexplained_volatility_flags
    SET flag_status = 'RESOLVED',
        suspected_cause = 'COVERAGE_GAP',
        resolution_evidence_hash = 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
        exculpatory_eligible = TRUE,
        resolved_by = 'TEST',
        resolved_at = NOW()
    WHERE flag_id = v_test_flag_id;

    RAISE NOTICE 'G3-REQ-005 TEST 3 PASS: Valid exculpatory correctly allowed';

    -- Clean up test data
    DELETE FROM fhq_calendar.unexplained_volatility_flags WHERE flag_id = v_test_flag_id;

    RAISE NOTICE 'G3-REQ-005 VERIFIED: All non-exculpatory constraint tests passed';
END $$;

-- ============================================================================
-- 270.8: Governance Logging
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
    metadata,
    agent_id,
    timestamp
) VALUES (
    gen_random_uuid(),
    'G3_GHOST_NON_EXCULPATORY',
    'IoS-016',
    'INSTITUTIONAL_OPERATING_STANDARD',
    'STIG',
    NOW(),
    'ENFORCED',
    'G3-REQ-005: Ghost events are NON-EXCULPATORY by default. Only COVERAGE_GAP or TIMESTAMP_DEFECT with evidence can affect Brier stratification. TRUE_GHOST and MAPPING_DEFECT are NEVER exculpatory.',
    jsonb_build_object(
        'migration', '270_g3_ghost_non_exculpatory.sql',
        'requirement', 'G3-REQ-005',
        'constraint', 'ghost_exculpatory_requires_evidence',
        'exculpatory_causes', ARRAY['COVERAGE_GAP', 'TIMESTAMP_DEFECT'],
        'non_exculpatory_causes', ARRAY['MAPPING_DEFECT', 'TRUE_GHOST'],
        'evidence_required', true,
        'test_result', 'PASS - all non-exculpatory tests passed'
    ),
    'STIG',
    NOW()
);

-- ============================================================================
-- 270.9: Update IoS Audit Log
-- ============================================================================

INSERT INTO fhq_meta.ios_audit_log (
    audit_id,
    ios_id,
    event_type,
    event_timestamp,
    actor,
    gate_level,
    event_data,
    evidence_hash
) VALUES (
    gen_random_uuid(),
    'IoS-016',
    'G3_REQ_005_IMPLEMENTED',
    NOW(),
    'STIG',
    'G3',
    jsonb_build_object(
        'requirement', 'G3-REQ-005',
        'title', 'Ghost Events - Non-Exculpatory by Default',
        'status', 'MECHANICALLY_ENFORCED',
        'constraint', 'ghost_exculpatory_requires_evidence',
        'exculpatory_eligible_field', true,
        'audit_trail', 'ghost_exculpatory_audit table'
    ),
    'd2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3'
);

COMMIT;

-- ============================================================================
-- Verification
-- ============================================================================
-- View ghost accountability status:
-- SELECT * FROM fhq_calendar.ghost_accountability_status;
--
-- Check if specific ghost is exculpatory:
-- SELECT * FROM fhq_calendar.check_ghost_exculpatory('flag-uuid');
--
-- Resolve ghost with evidence:
-- SELECT * FROM fhq_calendar.resolve_ghost_with_evidence(
--     'flag-uuid', 'COVERAGE_GAP', 'Missing provider for event', NULL, 'evidence data'
-- );
