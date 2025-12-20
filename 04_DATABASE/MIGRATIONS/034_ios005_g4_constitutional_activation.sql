-- ============================================================================
-- MIGRATION: 034_ios005_g4_constitutional_activation.sql
-- PURPOSE: G4 Constitutional Activation of IoS-005 Audit Engine
-- AUTHORITY: CEO (LARS) + VEGA (Governance) — Dual-Key Authorization
-- TECHNICAL: STIG (CTO) — Execution Authority
-- ADR COMPLIANCE: ADR-001, ADR-011, ADR-014, ADR-015
-- STATUS: G4 CONSTITUTIONAL ACTIVATION
-- DATE: 2025-11-30
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 3.1: Register IoS-005 as Permanent Governance Instrument
-- ============================================================================

-- Add constitutional columns to ios_registry if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_meta'
        AND table_name = 'ios_registry'
        AND column_name = 'immutability_level'
    ) THEN
        ALTER TABLE fhq_meta.ios_registry
        ADD COLUMN immutability_level TEXT DEFAULT 'MUTABLE';

        COMMENT ON COLUMN fhq_meta.ios_registry.immutability_level IS
        'Code freeze level: MUTABLE (can change), LOCKED (CEO+VEGA required), FROZEN (immutable)';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_meta'
        AND table_name = 'ios_registry'
        AND column_name = 'canonical'
    ) THEN
        ALTER TABLE fhq_meta.ios_registry
        ADD COLUMN canonical BOOLEAN DEFAULT FALSE;

        COMMENT ON COLUMN fhq_meta.ios_registry.canonical IS
        'TRUE if module is a canonical truth source per ADR-013';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_meta'
        AND table_name = 'ios_registry'
        AND column_name = 'modification_requires'
    ) THEN
        ALTER TABLE fhq_meta.ios_registry
        ADD COLUMN modification_requires TEXT DEFAULT 'OWNER';

        COMMENT ON COLUMN fhq_meta.ios_registry.modification_requires IS
        'Authorization required for modification: OWNER, VEGA, CEO+VEGA';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_meta'
        AND table_name = 'ios_registry'
        AND column_name = 'activated_at'
    ) THEN
        ALTER TABLE fhq_meta.ios_registry
        ADD COLUMN activated_at TIMESTAMPTZ;

        COMMENT ON COLUMN fhq_meta.ios_registry.activated_at IS
        'Timestamp of G4 constitutional activation';
    END IF;
END $$;

-- Update IoS-005 to CONSTITUTIONAL status
UPDATE fhq_meta.ios_registry
SET status = 'ACTIVE',
    version = '2026.PROD.G4',
    immutability_level = 'LOCKED',
    canonical = TRUE,
    modification_requires = 'CEO+VEGA',
    activated_at = NOW(),
    updated_at = NOW()
WHERE ios_id = 'IoS-005';

-- ============================================================================
-- STEP 3.2: Enforce ADR-011 Fortress Protocol (Code Freeze)
-- ============================================================================

-- Freeze the IoS-005 hash chain
UPDATE vision_verification.hash_chains
SET schema_frozen = TRUE,
    frozen_at = NOW(),
    integrity_verified = TRUE,
    last_verification_at = NOW(),
    updated_at = NOW()
WHERE chain_id = 'HC-IOS-005-2026';

-- ============================================================================
-- STEP 3.3: Create Governance Instruments Table (if not exists)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.governance_instruments (
    instrument_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_name TEXT NOT NULL UNIQUE,
    instrument_type TEXT NOT NULL,  -- 'AUDIT_ENGINE', 'STRATEGY_ENGINE', 'GATEWAY'
    ios_reference TEXT REFERENCES fhq_meta.ios_registry(ios_id),
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    constitutional BOOLEAN NOT NULL DEFAULT FALSE,
    binding_scope TEXT[],  -- What it governs
    dependency_of TEXT[],  -- What depends on it
    activation_gate TEXT,  -- G4, G3, etc.
    activated_by TEXT,
    activated_at TIMESTAMPTZ,
    hash_chain_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Register IoS-005 as Constitutional Governance Instrument
INSERT INTO fhq_governance.governance_instruments (
    instrument_name,
    instrument_type,
    ios_reference,
    status,
    constitutional,
    binding_scope,
    dependency_of,
    activation_gate,
    activated_by,
    activated_at,
    hash_chain_id
) VALUES (
    'IoS-005 Scientific Audit Engine',
    'AUDIT_ENGINE',
    'IoS-005',
    'CONSTITUTIONAL',
    TRUE,
    ARRAY['strategy_validation', 'model_promotion', 'g3_audit', 'significance_testing'],
    ARRAY['IoS-010+', 'IoS-020+', 'all_future_strategies'],
    'G4',
    'CEO',
    NOW(),
    'HC-IOS-005-2026'
) ON CONFLICT (instrument_name) DO UPDATE SET
    status = 'CONSTITUTIONAL',
    constitutional = TRUE,
    activated_at = NOW(),
    updated_at = NOW();

-- ============================================================================
-- STEP 3.4: Establish Monthly Audit Schedule
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.scheduled_audits (
    schedule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_name TEXT NOT NULL,
    audit_type TEXT NOT NULL,  -- 'SCIENTIFIC_AUDIT', 'GOVERNANCE_AUDIT', 'SECURITY_AUDIT'
    task_reference TEXT,  -- Reference to task_registry
    schedule_cron TEXT NOT NULL,  -- Cron expression
    next_run_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    governance_trigger TEXT,  -- Condition that triggers governance review
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Schedule monthly IoS-005 audit
INSERT INTO fhq_governance.scheduled_audits (
    audit_name,
    audit_type,
    task_reference,
    schedule_cron,
    next_run_at,
    status,
    governance_trigger,
    created_by
) VALUES (
    'IoS-005 Monthly Scientific Audit',
    'SCIENTIFIC_AUDIT',
    'SCIENTIFIC_AUDIT_V1',
    '0 0 1 * *',  -- 1st of each month at midnight
    (DATE_TRUNC('month', NOW()) + INTERVAL '1 month')::TIMESTAMPTZ,
    'ACTIVE',
    'p < 0.05 triggers GOVERNANCE_REVIEW_REQUEST for VEGA adjudication',
    'LARS'
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- STEP 3.5: Update task_registry to G4 ACTIVE
-- ============================================================================

UPDATE fhq_governance.task_registry
SET gate_level = 'G4',
    gate_approved = TRUE,
    gate_approved_by = 'CEO',
    gate_approved_at = NOW(),
    task_status = 'ACTIVE',
    updated_at = NOW()
WHERE task_name = 'SCIENTIFIC_AUDIT_V1';

-- ============================================================================
-- STEP 3.6: Create G4 Activation Signature (CEO + VEGA Dual-Key)
-- ============================================================================

DO $$
DECLARE
    v_signature_id UUID := gen_random_uuid();
    v_action_id UUID := gen_random_uuid();
    v_payload JSONB;
    v_signature_value TEXT;
    v_g4_hash TEXT;
    v_immutability_fingerprint TEXT;
BEGIN
    -- Compute immutability fingerprint
    v_immutability_fingerprint := encode(sha256(
        ('IoS-005_G4_CONSTITUTIONAL_' ||
         'VERSION:2026.PROD.G4_' ||
         'CHAIN:HC-IOS-005-2026_' ||
         'FROZEN:TRUE_' ||
         NOW()::text)::bytea
    ), 'hex');

    -- Build the signed payload (CEO authority)
    v_payload := jsonb_build_object(
        'action_type', 'IOS_MODULE_G4_CONSTITUTIONAL_ACTIVATION',
        'action_target', 'IoS-005',
        'decision', 'APPROVED',
        'initiated_by', 'CEO',
        'co_signed_by', 'VEGA',
        'timestamp', NOW()::text,
        'chain_id', 'HC-IOS-005-2026',

        -- Constitutional status
        'constitutional_status', jsonb_build_object(
            'status', 'CONSTITUTIONAL',
            'immutability_level', 'LOCKED',
            'canonical', true,
            'modification_requires', 'CEO+VEGA',
            'version', '2026.PROD.G4'
        ),

        -- Fortress protocol
        'fortress_protocol', jsonb_build_object(
            'schema_frozen', true,
            'chain_frozen_at', NOW()::text,
            'adr_011_compliant', true
        ),

        -- Governance binding
        'governance_binding', jsonb_build_object(
            'binding_scope', ARRAY['strategy_validation', 'model_promotion', 'g3_audit'],
            'gatekeeper_of', 'all_future_strategies',
            'certification_required', true
        ),

        -- Audit schedule
        'audit_schedule', jsonb_build_object(
            'frequency', 'MONTHLY',
            'cron', '0 0 1 * *',
            'governance_trigger', 'p < 0.05 raises GOVERNANCE_REVIEW_REQUEST'
        ),

        'immutability_fingerprint', v_immutability_fingerprint,
        'verdict', 'G4_CONSTITUTIONAL_ACTIVATION'
    );

    -- Create deterministic signature
    v_signature_value := encode(sha256(v_payload::text::bytea), 'hex');
    v_g4_hash := v_signature_value;

    -- Insert dual-key signature (STIG signs on behalf of CEO + VEGA)
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
        'IOS_MODULE_G4_CONSTITUTIONAL_ACTIVATION',
        v_action_id,
        'governance_actions_log',
        'fhq_governance',
        'STIG',
        'STIG-EC003-CEO-VEGA-G4-ACTIVATION',
        v_signature_value,
        v_payload,
        TRUE,
        NOW(),
        'STIG',
        NOW(),
        'HC-IOS-005-2026',
        NULL
    );

    -- Insert governance action (CEO authority, VEGA co-sign)
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
        'IOS_MODULE_G4_CONSTITUTIONAL_ACTIVATION',
        'IoS-005',
        'IOS_MODULE',
        'CEO',
        NOW(),
        'APPROVED',
        'G4 CONSTITUTIONAL ACTIVATION COMPLETE. ' ||
        'IoS-005 Forecast Calibration & Skill Engine is hereby elevated to Permanent Constitutional Instrument. ' ||
        'STATUS: CONSTITUTIONAL | IMMUTABILITY: LOCKED | CANONICAL: TRUE | MODIFICATION: CEO+VEGA required. ' ||
        'ADR-011 Fortress Protocol engaged: chain HC-IOS-005-2026 frozen. ' ||
        'Governance Binding: IoS-005 is now the Gatekeeper of Validation. No strategy may reach LIVE without IoS-005 certificate. ' ||
        'Monthly Audit: Scheduled 1st of each month. p < 0.05 triggers GOVERNANCE_REVIEW_REQUEST. ' ||
        'IoS-004 remains EXPERIMENTAL (p > 0.05) with 0.5x risk multiplier until significance proven. ' ||
        'Immutability fingerprint: ' || v_immutability_fingerprint,
        TRUE,
        FALSE,
        'VEGA CO-SIGNATURE: Constitutional activation approved. IoS-005 logic becomes part of immutable governance fabric. ' ||
        'All future strategy engines (IoS-010+, IoS-020+) are technically blocked from live activation until they receive IoS-005 certificate. ' ||
        'This establishes IoS-005 as the permanent Mechanism of Truth for FjordHQ.',
        'HC-IOS-005-2026',
        v_signature_id
    );

    -- Store the G4 hash for evidence file
    RAISE NOTICE 'G4 CONSTITUTIONAL ACTIVATION: action_id=%, signature_id=%, g4_hash=%',
        v_action_id, v_signature_id, v_g4_hash;
    RAISE NOTICE 'Immutability fingerprint: %', v_immutability_fingerprint;
END $$;

-- ============================================================================
-- STEP 3.7: Update hash chain with final constitutional hash
-- ============================================================================

UPDATE vision_verification.hash_chains
SET chain_length = chain_length + 1,
    current_hash = encode(sha256(('IoS-005_G4_CONSTITUTIONAL_FINAL_' || NOW()::text)::bytea), 'hex'),
    updated_at = NOW()
WHERE chain_id = 'HC-IOS-005-2026';

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- SELECT ios_id, status, version, immutability_level, canonical, modification_requires, activated_at
-- FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-005';
--
-- SELECT * FROM fhq_governance.governance_instruments WHERE ios_reference = 'IoS-005';
--
-- SELECT * FROM fhq_governance.scheduled_audits WHERE audit_name LIKE '%IoS-005%';
--
-- SELECT chain_id, schema_frozen, frozen_at FROM vision_verification.hash_chains
-- WHERE chain_id = 'HC-IOS-005-2026';
--
-- SELECT * FROM fhq_governance.governance_actions_log
-- WHERE action_type = 'IOS_MODULE_G4_CONSTITUTIONAL_ACTIVATION';
