-- ============================================================================
-- MIGRATION: 032_ios005_g2_governance_attestation.sql
-- PURPOSE: G2 Governance Attestation for IoS-005 + IoS-004 Classification
-- AUTHORITY: VEGA (Tier-1 Governance) per LARS Directive
-- ADR COMPLIANCE: ADR-001, ADR-003, ADR-004, ADR-011
-- STATUS: G2 PASS_WITH_CONDITIONS
-- DATE: 2025-11-30
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Add risk_multiplier column to ios_registry if not exists
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_meta'
        AND table_name = 'ios_registry'
        AND column_name = 'risk_multiplier'
    ) THEN
        ALTER TABLE fhq_meta.ios_registry
        ADD COLUMN risk_multiplier NUMERIC(3,2) DEFAULT 1.0;

        COMMENT ON COLUMN fhq_meta.ios_registry.risk_multiplier IS
        'Capital allocation risk multiplier. 1.0 = full allocation, 0.5 = half allocation (EXPERIMENTAL), 0.0 = suspended';
    END IF;
END $$;

-- ============================================================================
-- STEP 2: Update IoS-004 classification per VEGA decision
-- ============================================================================

UPDATE fhq_meta.ios_registry
SET experimental_classification = 'EXPERIMENTAL',
    risk_multiplier = 0.5,
    updated_at = NOW()
WHERE ios_id = 'IoS-004';

-- ============================================================================
-- STEP 3: Update IoS-005 to G2 attestation status
-- ============================================================================

UPDATE fhq_governance.task_registry
SET gate_level = 'G2',
    vega_reviewed = TRUE,
    vega_approved = TRUE,
    vega_reviewer = 'VEGA',
    vega_reviewed_at = NOW(),
    updated_at = NOW()
WHERE task_name = 'SCIENTIFIC_AUDIT_V1';

-- ============================================================================
-- STEP 4: Create Signature for VEGA Governance Action (ADR-008)
-- ============================================================================

DO $$
DECLARE
    v_signature_id UUID := gen_random_uuid();
    v_action_id UUID := gen_random_uuid();
    v_payload JSONB;
    v_signature_value TEXT;
    v_g2_evidence_hash TEXT := 'f06ae7d5febaf05ac2fd1a6aececaa0f1c85758fb664a5bfbd8aff9522bd3012';
BEGIN
    -- Build the signed payload
    v_payload := jsonb_build_object(
        'action_type', 'IOS_MODULE_G2_ATTESTATION',
        'action_target', 'IoS-005',
        'decision', 'PASS_WITH_CONDITIONS',
        'initiated_by', 'VEGA',
        'timestamp', NOW()::text,
        'chain_id', 'HC-IOS-005-2026',
        'evidence_hash', v_g2_evidence_hash,
        'auditor_certification', jsonb_build_object(
            'subject', 'IoS-005',
            'sovereign_auditor_check', 'COMPLIANT',
            'one_true_source_check', 'LINEAGE_VALID',
            'certification_status', 'CERTIFIED'
        ),
        'strategy_adjudication', jsonb_build_object(
            'subject', 'IoS-004',
            'classification', 'EXPERIMENTAL',
            'risk_multiplier', 0.5,
            'rationale', 'p > 0.05 on both bootstrap and permutation tests'
        ),
        'conditions', jsonb_build_array(
            'IoS-004 tagged as EXPERIMENTAL',
            'Risk multiplier 0.5x enforced',
            'Quarterly re-audit required',
            'VEGA review mandatory upon p < 0.05'
        )
    );

    -- Create deterministic signature
    v_signature_value := encode(sha256(v_payload::text::bytea), 'hex');

    -- Insert signature (STIG signs on behalf of VEGA governance decision per ADR-008)
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
        'IOS_MODULE_G2_ATTESTATION',
        v_action_id,
        'governance_actions_log',
        'fhq_governance',
        'STIG',  -- STIG executes VEGA governance decisions per ADR-008
        'STIG-EC003-VEGA-G2-ATTESTATION',
        v_signature_value,
        v_payload,
        TRUE,
        NOW(),
        'STIG',  -- Technical verification by STIG
        NOW(),
        'HC-IOS-005-2026',
        NULL
    );

    -- Insert governance action
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
        'IOS_MODULE_G2_ATTESTATION',
        'IoS-005',
        'IOS_MODULE',
        'VEGA',
        NOW(),
        'APPROVED',  -- APPROVED with conditions documented in rationale
        'G2 GOVERNANCE ATTESTATION: APPROVED WITH CONDITIONS. ' ||
        'IoS-005 Audit Engine CERTIFIED: Sovereign Auditor Check COMPLIANT, One-True-Source LINEAGE_VALID. ' ||
        'IoS-004 Strategy Engine ADJUDICATED: Classification set to EXPERIMENTAL with 0.5x risk multiplier. ' ||
        'Rationale: p_bootstrap=0.501, p_permutation=0.173 (both > 0.05) per Expected Null Result Regime clause. ' ||
        'CONDITIONS: (1) Quarterly re-audit required, (2) VEGA review mandatory on significance achievement, (3) Capital preservation mode enforced. ' ||
        'Evidence hash: ' || v_g2_evidence_hash,
        TRUE,
        FALSE,
        'VEGA G2 Review: IoS-005 passes all governance checks. IoS-004 classified EXPERIMENTAL per scientific findings. ' ||
        'This establishes binding precedent for treatment of non-significant strategies under ADR-012 Economic Safety.',
        'HC-IOS-005-2026',
        v_signature_id
    );

    RAISE NOTICE 'G2 ATTESTATION recorded: action_id=%, signature_id=%', v_action_id, v_signature_id;
END $$;

-- ============================================================================
-- STEP 5: Update hash chain
-- ============================================================================

UPDATE vision_verification.hash_chains
SET chain_length = chain_length + 1,
    current_hash = encode(sha256(('IoS-005_G2_ATTESTATION_VEGA_' || NOW()::text)::bytea), 'hex'),
    updated_at = NOW()
WHERE chain_id = 'HC-IOS-005-2026';

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- SELECT ios_id, experimental_classification, risk_multiplier FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-004';
-- SELECT * FROM fhq_governance.task_registry WHERE task_name = 'SCIENTIFIC_AUDIT_V1';
-- SELECT * FROM fhq_governance.governance_actions_log WHERE action_type = 'IOS_MODULE_G2_ATTESTATION' ORDER BY initiated_at DESC LIMIT 1;
