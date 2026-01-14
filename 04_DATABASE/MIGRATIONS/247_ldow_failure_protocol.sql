-- =============================================================================
-- MIGRATION 247: LDOW FAILURE PROTOCOL
-- =============================================================================
-- CEO Directive: 2026-01-14 - Failure Protocol Addition
-- Author: STIG
-- Date: 2026-01-14
--
-- Purpose:
--   Implement explicit failure handling rules for LDOW cycles:
--   - Failed cycles do NOT count toward Rung D eligibility
--   - No retry until root cause documented and VEGA attested
--   - Correction resets LDOW counter to 0
--
-- Rationale:
--   "Retry until pass" would undermine evidence value.
--   Failures must be investigated, not retried blindly.
-- =============================================================================

BEGIN;

-- =============================================================================
-- SECTION 1: FAILURE INCIDENT TABLE
-- =============================================================================
-- Tracks cycle failures and required remediation

CREATE TABLE IF NOT EXISTS fhq_governance.ldow_failure_incidents (
    incident_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Failure identification
    cycle_number INTEGER NOT NULL,
    failure_type TEXT NOT NULL CHECK (failure_type IN (
        'COVERAGE_FAIL',
        'STABILITY_FAIL',
        'DAMPER_CHANGED',
        'PRICE_BLACKOUT',
        'SYSTEM_ERROR'
    )),
    failure_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Failure details
    failure_details JSONB NOT NULL DEFAULT '{}',
    coverage_achieved NUMERIC(5,4),
    coverage_required NUMERIC(5,4),
    brier_variance_achieved NUMERIC(8,6),
    brier_variance_required NUMERIC(8,6),
    damper_hash_expected TEXT,
    damper_hash_actual TEXT,

    -- Remediation tracking
    root_cause_documented BOOLEAN NOT NULL DEFAULT FALSE,
    root_cause_description TEXT,
    root_cause_documented_at TIMESTAMPTZ,
    root_cause_documented_by TEXT,

    -- Correction tracking
    correction_applied BOOLEAN NOT NULL DEFAULT FALSE,
    correction_description TEXT,
    correction_applied_at TIMESTAMPTZ,
    correction_applied_by TEXT,

    -- VEGA attestation (required before retry)
    vega_attestation_id UUID,
    vega_attested_at TIMESTAMPTZ,
    vega_attestation_notes TEXT,

    -- Retry authorization
    retry_authorized BOOLEAN NOT NULL DEFAULT FALSE,
    retry_authorized_at TIMESTAMPTZ,
    retry_resets_counter BOOLEAN NOT NULL DEFAULT TRUE,

    -- Status
    incident_status TEXT NOT NULL DEFAULT 'OPEN' CHECK (incident_status IN (
        'OPEN',
        'ROOT_CAUSE_DOCUMENTED',
        'CORRECTION_APPLIED',
        'VEGA_ATTESTED',
        'RETRY_AUTHORIZED',
        'CLOSED'
    )),

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for quick lookup
CREATE INDEX IF NOT EXISTS idx_ldow_failure_cycle
    ON fhq_governance.ldow_failure_incidents(cycle_number);
CREATE INDEX IF NOT EXISTS idx_ldow_failure_status
    ON fhq_governance.ldow_failure_incidents(incident_status);

-- =============================================================================
-- SECTION 2: RETRY BLOCKING FUNCTION
-- =============================================================================
-- Prevents cycle execution if unresolved failure exists

CREATE OR REPLACE FUNCTION fhq_governance.check_retry_authorization(p_cycle_number INTEGER)
RETURNS TABLE (
    can_execute BOOLEAN,
    block_reason TEXT,
    incident_id UUID
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        CASE
            WHEN fi.incident_id IS NULL THEN TRUE
            WHEN fi.retry_authorized = TRUE THEN TRUE
            ELSE FALSE
        END AS can_execute,
        CASE
            WHEN fi.incident_id IS NULL THEN NULL
            WHEN fi.retry_authorized = TRUE THEN NULL
            WHEN fi.incident_status = 'OPEN' THEN 'Failure incident OPEN - root cause not documented'
            WHEN fi.incident_status = 'ROOT_CAUSE_DOCUMENTED' THEN 'Correction not yet applied'
            WHEN fi.incident_status = 'CORRECTION_APPLIED' THEN 'VEGA attestation required before retry'
            WHEN fi.incident_status = 'VEGA_ATTESTED' THEN 'Retry not yet authorized'
            ELSE 'Unknown block reason'
        END AS block_reason,
        fi.incident_id
    FROM (SELECT 1) AS dummy
    LEFT JOIN fhq_governance.ldow_failure_incidents fi
        ON fi.cycle_number = p_cycle_number
        AND fi.incident_status != 'CLOSED'
    ORDER BY fi.created_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 3: FAILURE REGISTRATION FUNCTION
-- =============================================================================
-- Called by daemon when cycle fails

CREATE OR REPLACE FUNCTION fhq_governance.register_ldow_failure(
    p_cycle_number INTEGER,
    p_failure_type TEXT,
    p_failure_details JSONB,
    p_coverage_achieved NUMERIC DEFAULT NULL,
    p_coverage_required NUMERIC DEFAULT NULL,
    p_brier_variance_achieved NUMERIC DEFAULT NULL,
    p_brier_variance_required NUMERIC DEFAULT NULL,
    p_damper_hash_expected TEXT DEFAULT NULL,
    p_damper_hash_actual TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_incident_id UUID;
BEGIN
    INSERT INTO fhq_governance.ldow_failure_incidents (
        cycle_number,
        failure_type,
        failure_details,
        coverage_achieved,
        coverage_required,
        brier_variance_achieved,
        brier_variance_required,
        damper_hash_expected,
        damper_hash_actual
    ) VALUES (
        p_cycle_number,
        p_failure_type,
        p_failure_details,
        p_coverage_achieved,
        p_coverage_required,
        p_brier_variance_achieved,
        p_brier_variance_required,
        p_damper_hash_expected,
        p_damper_hash_actual
    )
    RETURNING incident_id INTO v_incident_id;

    -- Log to governance
    INSERT INTO fhq_governance.governance_actions_log (
        action_type,
        action_target,
        action_target_type,
        initiated_by,
        decision,
        decision_rationale,
        metadata
    ) VALUES (
        'LDOW_CYCLE_FAILURE',
        v_incident_id::TEXT,
        'FAILURE_INCIDENT',
        'LDOW_CYCLE_DAEMON',
        'BLOCKED',
        'CEO Directive: Failed cycle does not count. Retry requires root cause + VEGA attestation.',
        jsonb_build_object(
            'cycle_number', p_cycle_number,
            'failure_type', p_failure_type,
            'incident_id', v_incident_id,
            'retry_resets_counter', TRUE,
            'timestamp', NOW()
        )
    );

    RETURN v_incident_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 4: VEGA ATTESTATION FUNCTION
-- =============================================================================
-- For VEGA to attest that correction is valid

CREATE OR REPLACE FUNCTION fhq_governance.attest_ldow_failure_correction(
    p_incident_id UUID,
    p_attested_by TEXT,
    p_attestation_notes TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    v_current_status TEXT;
BEGIN
    -- Check current status
    SELECT incident_status INTO v_current_status
    FROM fhq_governance.ldow_failure_incidents
    WHERE incident_id = p_incident_id;

    IF v_current_status IS NULL THEN
        RAISE EXCEPTION 'Incident % not found', p_incident_id;
    END IF;

    IF v_current_status != 'CORRECTION_APPLIED' THEN
        RAISE EXCEPTION 'Incident must be in CORRECTION_APPLIED status (current: %)', v_current_status;
    END IF;

    -- Update with attestation
    UPDATE fhq_governance.ldow_failure_incidents
    SET
        vega_attestation_id = gen_random_uuid(),
        vega_attested_at = NOW(),
        vega_attestation_notes = p_attestation_notes,
        incident_status = 'VEGA_ATTESTED'
    WHERE incident_id = p_incident_id;

    -- Log attestation
    INSERT INTO fhq_governance.governance_actions_log (
        action_type,
        action_target,
        action_target_type,
        initiated_by,
        decision,
        decision_rationale,
        metadata
    ) VALUES (
        'LDOW_FAILURE_ATTESTATION',
        p_incident_id::TEXT,
        'FAILURE_INCIDENT',
        p_attested_by,
        'ATTESTED',
        'VEGA attestation: Correction validated, retry may be authorized',
        jsonb_build_object(
            'incident_id', p_incident_id,
            'attestation_notes', p_attestation_notes,
            'timestamp', NOW()
        )
    );

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 5: RETRY AUTHORIZATION FUNCTION
-- =============================================================================
-- CEO authorizes retry (resets counter)

CREATE OR REPLACE FUNCTION fhq_governance.authorize_ldow_retry(
    p_incident_id UUID,
    p_authorized_by TEXT,
    p_reset_counter BOOLEAN DEFAULT TRUE
)
RETURNS BOOLEAN AS $$
DECLARE
    v_current_status TEXT;
    v_cycle_number INTEGER;
BEGIN
    -- Check current status
    SELECT incident_status, cycle_number
    INTO v_current_status, v_cycle_number
    FROM fhq_governance.ldow_failure_incidents
    WHERE incident_id = p_incident_id;

    IF v_current_status IS NULL THEN
        RAISE EXCEPTION 'Incident % not found', p_incident_id;
    END IF;

    IF v_current_status != 'VEGA_ATTESTED' THEN
        RAISE EXCEPTION 'Incident must be VEGA_ATTESTED before retry authorization (current: %)', v_current_status;
    END IF;

    -- Authorize retry
    UPDATE fhq_governance.ldow_failure_incidents
    SET
        retry_authorized = TRUE,
        retry_authorized_at = NOW(),
        retry_resets_counter = p_reset_counter,
        incident_status = 'RETRY_AUTHORIZED'
    WHERE incident_id = p_incident_id;

    -- If counter reset required, reset all cycles to SCHEDULED
    IF p_reset_counter THEN
        UPDATE fhq_governance.ldow_cycle_completion
        SET
            completion_status = 'SCHEDULED',
            started_at = NULL,
            completed_at = NULL,
            forecasts_eligible = 0,
            forecasts_paired = 0,
            forecasts_expired = 0,
            brier_score_run1 = NULL,
            brier_score_run2 = NULL,
            calibration_error = NULL,
            hit_rate = NULL,
            damper_hash_at_end = NULL,
            evidence_id = NULL,
            vega_attestation_id = NULL,
            vega_attested_at = NULL
        WHERE cycle_number >= v_cycle_number;

        -- Log counter reset
        INSERT INTO fhq_governance.governance_actions_log (
            action_type,
            action_target,
            action_target_type,
            initiated_by,
            decision,
            decision_rationale,
            metadata
        ) VALUES (
            'LDOW_COUNTER_RESET',
            'ldow_cycle_completion',
            'TABLE',
            p_authorized_by,
            'EXECUTED',
            'CEO Directive: Correction resets LDOW counter. Cycles must be re-run from scratch.',
            jsonb_build_object(
                'incident_id', p_incident_id,
                'reset_from_cycle', v_cycle_number,
                'timestamp', NOW()
            )
        );
    END IF;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 6: VIEW FOR FAILURE STATUS
-- =============================================================================

CREATE OR REPLACE VIEW fhq_governance.v_ldow_failure_status AS
SELECT
    fi.incident_id,
    fi.cycle_number,
    fi.failure_type,
    fi.failure_timestamp,
    fi.incident_status,
    fi.root_cause_documented,
    fi.correction_applied,
    fi.vega_attested_at IS NOT NULL AS vega_attested,
    fi.retry_authorized,
    fi.retry_resets_counter,
    CASE
        WHEN fi.incident_status = 'OPEN' THEN 'Document root cause'
        WHEN fi.incident_status = 'ROOT_CAUSE_DOCUMENTED' THEN 'Apply correction'
        WHEN fi.incident_status = 'CORRECTION_APPLIED' THEN 'Request VEGA attestation'
        WHEN fi.incident_status = 'VEGA_ATTESTED' THEN 'Request CEO retry authorization'
        WHEN fi.incident_status = 'RETRY_AUTHORIZED' THEN 'Ready for retry (counter will reset)'
        ELSE 'Closed'
    END AS next_action
FROM fhq_governance.ldow_failure_incidents fi
WHERE fi.incident_status != 'CLOSED'
ORDER BY fi.created_at DESC;

-- =============================================================================
-- SECTION 7: GOVERNANCE LOG
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'LDOW_FAILURE_PROTOCOL_ACTIVATION',
    'fhq_governance.ldow_failure_incidents',
    'TABLE',
    'STIG',
    'EXECUTED',
    'CEO Directive: Failed cycles do NOT count. No retry until root cause documented and VEGA attested. Correction resets counter.',
    jsonb_build_object(
        'migration', '247_ldow_failure_protocol.sql',
        'rules', jsonb_build_object(
            'failed_cycles_count', FALSE,
            'retry_requires_root_cause', TRUE,
            'retry_requires_vega_attestation', TRUE,
            'correction_resets_counter', TRUE
        ),
        'timestamp', NOW()
    )
);

COMMIT;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

SELECT 'Migration 247 Complete: LDOW Failure Protocol Active' AS status;

-- Show failure protocol functions
SELECT
    routine_name,
    routine_type
FROM information_schema.routines
WHERE routine_schema = 'fhq_governance'
  AND routine_name LIKE '%ldow%'
ORDER BY routine_name;
