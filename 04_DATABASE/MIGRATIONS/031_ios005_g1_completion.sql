-- ============================================================================
-- MIGRATION: 031_ios005_g1_completion.sql
-- PURPOSE: G1 Scientific Audit PASS for IoS-005 Forecast Calibration Engine
-- AUTHORITY: LARS (Owner) → STIG (Technical Validation) → CODE (Execution)
-- ADR COMPLIANCE: ADR-002, ADR-004, ADR-008, ADR-011, ADR-013
-- STATUS: G1 PASS → Ready for G2 Governance Review
-- DATE: 2025-11-30
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Update task_registry to G1 PASS
-- ============================================================================

-- Note: task_status remains 'REGISTERED' until G4 activation (then 'ACTIVE')
-- Gate progression is tracked via gate_level and gate_approved columns
UPDATE fhq_governance.task_registry
SET gate_approved = TRUE,
    gate_level = 'G1',
    gate_approved_by = 'STIG',
    gate_approved_at = NOW(),
    updated_at = NOW()
WHERE task_name = 'SCIENTIFIC_AUDIT_V1';

-- ============================================================================
-- STEP 2: Create Signature for Governance Action (ADR-008 Compliance)
-- ============================================================================

DO $$
DECLARE
    v_signature_id UUID := gen_random_uuid();
    v_action_id UUID := gen_random_uuid();
    v_payload JSONB;
    v_signature_value TEXT;
    v_evidence_hash TEXT := '53cc174b0760f0b2ad2d99f9d5a5a2202ebe084e374fe9f2e3f622de0f5feafc';
BEGIN
    -- Build the signed payload
    v_payload := jsonb_build_object(
        'action_type', 'IOS_MODULE_G1_PASS',
        'action_target', 'IoS-005',
        'decision', 'APPROVED',
        'initiated_by', 'STIG',
        'timestamp', NOW()::text,
        'chain_id', 'HC-IOS-005-2026',
        'evidence_hash', v_evidence_hash,
        'scientific_results', jsonb_build_object(
            'actual_sharpe', 2.6113,
            'actual_sortino', 3.2277,
            'actual_calmar', 6.4726,
            'p_value_bootstrap', 0.501,
            'p_value_permutation', 0.173,
            'calibration_status', 'WARNING: STRATEGY_NOT_SIGNIFICANT'
        ),
        'g1_criteria', jsonb_build_object(
            'tests_executed_without_error', true,
            'bootstrap_engine_executed', true,
            'permutation_engine_executed', true,
            'rolling_sharpe_computed', true,
            'deterministic_replay_succeeded', true,
            'zero_drift_vs_ios004', true,
            'evidence_file_generated', true,
            'lineage_hashes_verified', true,
            'schema_integrity_pass', true
        )
    );

    -- Create deterministic signature (hash of payload for audit trail)
    v_signature_value := encode(sha256(v_payload::text::bytea), 'hex');

    -- Insert signature first
    INSERT INTO vision_verification.operation_signatures (
        signature_id,
        operation_type,
        operation_id,
        operation_table,
        operation_schema,
        signing_agent,
        signing_key_id,
        signature_value,
        signed_payload,
        verified,
        verified_at,
        verified_by,
        created_at,
        hash_chain_id,
        previous_signature_id
    ) VALUES (
        v_signature_id,
        'IOS_MODULE_G1_PASS',
        v_action_id,
        'governance_actions_log',
        'fhq_governance',
        'STIG',
        'STIG-EC003-G1-SCIENTIFIC-AUDIT',
        v_signature_value,
        v_payload,
        TRUE,
        NOW(),
        'STIG',
        NOW(),
        'HC-IOS-005-2026',
        NULL
    );

    -- Insert governance action with signature reference
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
    ) VALUES (
        v_action_id,
        'IOS_MODULE_G1_PASS',
        'IoS-005',
        'IOS_MODULE',
        'STIG',
        NOW(),
        'APPROVED',
        'G1 SCIENTIFIC AUDIT PASS. IoS-005 Forecast Calibration & Skill Engine validated. ' ||
        'All 9 G1 criteria passed: tests executed without error, bootstrap/permutation engines functional, ' ||
        'deterministic replay achieved zero drift vs IoS-004 G4, evidence file generated with hash ' ||
        v_evidence_hash || '. ' ||
        'Scientific findings on IoS-004: Sharpe=2.61, p_bootstrap=0.501, p_permutation=0.173. ' ||
        'Strategy flagged as STRATEGY_NOT_SIGNIFICANT (expected per Null Result Regime clause). ' ||
        'IoS-005 is ready for G2 Governance Review. Recommendation: Tag IoS-004 as EXPERIMENTAL.',
        FALSE,  -- G2 VEGA review pending
        FALSE,
        'G1 gate passed. Scientific validation complete. Awaiting G2 governance review by VEGA.',
        'HC-IOS-005-2026',
        v_signature_id
    );

    RAISE NOTICE 'G1 PASS recorded: action_id=%, signature_id=%', v_action_id, v_signature_id;
END $$;

-- ============================================================================
-- STEP 3: Update hash chain
-- ============================================================================

UPDATE vision_verification.hash_chains
SET chain_length = chain_length + 1,
    current_hash = encode(sha256(('IoS-005_G1_PASS_' || NOW()::text)::bytea), 'hex'),
    updated_at = NOW()
WHERE chain_id = 'HC-IOS-005-2026';

-- ============================================================================
-- STEP 4: Tag IoS-004 as EXPERIMENTAL (G2 Recommendation Pre-Registration)
-- ============================================================================
-- This prepares the recommendation for VEGA's G2 review.
-- Final EXPERIMENTAL status will be confirmed during G2.

-- Add experimental_classification column if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_meta'
        AND table_name = 'ios_registry'
        AND column_name = 'experimental_classification'
    ) THEN
        ALTER TABLE fhq_meta.ios_registry
        ADD COLUMN experimental_classification TEXT DEFAULT 'UNCLASSIFIED';

        COMMENT ON COLUMN fhq_meta.ios_registry.experimental_classification IS
        'Scientific classification per IoS-005 G1 audit: PROVEN (p<0.05), EXPERIMENTAL (p>=0.05), UNCLASSIFIED (not yet audited)';
    END IF;
END $$;

-- Pre-register EXPERIMENTAL recommendation (pending G2 approval)
UPDATE fhq_meta.ios_registry
SET experimental_classification = 'PENDING_G2_EXPERIMENTAL',
    updated_at = NOW()
WHERE ios_id = 'IoS-004';

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- SELECT * FROM fhq_governance.task_registry WHERE task_name = 'SCIENTIFIC_AUDIT_V1';
-- SELECT * FROM fhq_governance.governance_actions_log WHERE action_target = 'IoS-005' ORDER BY initiated_at DESC LIMIT 1;
-- SELECT * FROM vision_verification.operation_signatures WHERE operation_type = 'IOS_MODULE_G1_PASS' ORDER BY created_at DESC LIMIT 1;
-- SELECT ios_id, experimental_classification FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-004';
