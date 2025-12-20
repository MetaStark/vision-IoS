-- ============================================================================
-- MIGRATION 155: VEGA ATTESTATION - WAVE 17A COMPLETION
-- 2025-12-18
-- ============================================================================
-- PURPOSE: Record VEGA attestation for WAVE 17A CCO Activation
-- ============================================================================

BEGIN;

-- Insert VEGA attestation into audit log
INSERT INTO fhq_governance.audit_log (
    event_type, event_category, target_type, target_id,
    actor_id, actor_role, event_data, event_hash, governance_gate, adr_reference
) VALUES (
    'ATTESTATION',
    'OPERATIONAL',
    'DIRECTIVE',
    'CEO_DIRECTIVE_WAVE_17A',
    'VEGA',
    'GOVERNANCE',
    jsonb_build_object(
        'attestation_id', 'VEGA-WAVE17A-ATT-20251218-001',
        'attestation_file', '05_GOVERNANCE/PHASE3/VEGA_ATTESTATION_WAVE17A_CCO_ACTIVATION_20251218.json',
        'verdict', 'FULLY_COMPLIANT',
        'sections_verified', jsonb_build_array('3.1', '3.2', '3.3', '2'),
        'compliance_summary', jsonb_build_object(
            'section_3_1_cold_start', 'VERIFIED',
            'section_3_2_provenance', 'VERIFIED',
            'section_3_3_failover', 'VERIFIED',
            'section_2_semantic', 'VERIFIED'
        ),
        'cco_status', 'OPERATIONAL',
        'daemon_status', 'RUNNING',
        'signals_armed', 22,
        'paper_execution', 'AUTHORIZED',
        'live_execution', 'BLOCKED (out of scope)'
    ),
    encode(sha256('VEGA-WAVE17A-ATT-20251218-001'::bytea), 'hex'),
    'G4',
    'ADR-013'
);

-- Update G5 exit criteria to reflect VEGA attestation for WAVE 17A
UPDATE fhq_canonical.g5_exit_criteria_status SET
    vega_attestation = 'G5_PASS',
    vega_attestation_at = NOW(),
    last_updated = NOW()
WHERE is_active = TRUE;

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_attestation_count INT;
    v_vega_status TEXT;
BEGIN
    SELECT COUNT(*) INTO v_attestation_count
    FROM fhq_governance.audit_log
    WHERE event_type = 'ATTESTATION'
    AND target_id = 'CEO_DIRECTIVE_WAVE_17A';

    SELECT vega_attestation INTO v_vega_status
    FROM fhq_canonical.g5_exit_criteria_status
    WHERE is_active = TRUE;

    RAISE NOTICE '';
    RAISE NOTICE '══════════════════════════════════════════════════════════════════════';
    RAISE NOTICE 'VEGA ATTESTATION - WAVE 17A - RECORDED';
    RAISE NOTICE '══════════════════════════════════════════════════════════════════════';
    RAISE NOTICE 'Attestation Records: %', v_attestation_count;
    RAISE NOTICE 'G5 Exit Criteria VEGA Status: %', v_vega_status;
    RAISE NOTICE '══════════════════════════════════════════════════════════════════════';
END $$;
