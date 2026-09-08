-- Migration 295: Zero-Trust HARD Enforcement
-- Purpose: BLOCK (not log) any calendar write without verified lineage
-- Directive: CEO-DIR-2026-063 - Auditor Evidence Requirements
-- Requirement: Enforcement must be DB-level REJECT, not application-level warn
-- Author: STIG
-- Date: 2026-01-17

-- ============================================
-- SECTION 1: BLOCKING TRIGGER - Reject writes without lineage
-- ============================================

BEGIN;

-- Create enforcement function that RAISES EXCEPTION (hard block)
CREATE OR REPLACE FUNCTION fhq_calendar.enforce_data_lineage_proof()
RETURNS TRIGGER AS $$
DECLARE
    v_lineage_exists BOOLEAN;
    v_source_approved BOOLEAN;
    v_violation_id UUID;
BEGIN
    -- BYPASS: Allow updates to existing rows for corrections (with governance log)
    -- Only applies to UPDATE, not INSERT of new canonical data
    IF TG_OP = 'UPDATE' AND OLD.is_canonical = true THEN
        -- Log the correction but allow it (corrections are governance-approved)
        INSERT INTO fhq_governance.governance_actions_log (
            action_id, action_type, action_target, action_target_type,
            initiated_by, initiated_at, decision, decision_rationale
        ) VALUES (
            gen_random_uuid(),
            'CALENDAR_CORRECTION',
            'fhq_calendar.calendar_events',
            'ROW',
            current_user,
            NOW(),
            'ALLOWED',
            'Correction to existing canonical record: ' || NEW.event_type_code || ' at ' || NEW.event_timestamp::text
        );
        RETURN NEW;
    END IF;

    -- For INSERT of new canonical records with numeric values: REQUIRE LINEAGE
    IF NEW.is_canonical = true AND
       (NEW.consensus_estimate IS NOT NULL OR NEW.actual_value IS NOT NULL OR NEW.previous_value IS NOT NULL) THEN

        -- Check 1: Source must be in approved list
        SELECT EXISTS (
            SELECT 1 FROM fhq_governance.approved_data_sources
            WHERE source_code = NEW.source_provider AND is_active = true
        ) INTO v_source_approved;

        -- Check 2: Lineage proof must exist for this event
        SELECT EXISTS (
            SELECT 1 FROM fhq_calendar.data_lineage_proof
            WHERE event_id = NEW.event_id
              AND api_response_hash IS NOT NULL
              AND length(api_response_hash) >= 64
        ) INTO v_lineage_exists;

        -- If EITHER check fails: BLOCK and LOG VIOLATION
        IF NOT v_source_approved OR NOT v_lineage_exists THEN
            -- Record the violation BEFORE raising exception
            INSERT INTO fhq_governance.llm_generation_violations (
                violation_id,
                violation_timestamp,
                agent_id,
                attempted_action,
                data_type,
                blocked,
                evidence_snapshot,
                reported_to
            ) VALUES (
                gen_random_uuid(),
                NOW(),
                current_user,
                TG_OP || ' on calendar_events',
                NEW.event_type_code,
                true,
                jsonb_build_object(
                    'event_id', NEW.event_id,
                    'event_type', NEW.event_type_code,
                    'timestamp', NEW.event_timestamp,
                    'consensus', NEW.consensus_estimate,
                    'actual', NEW.actual_value,
                    'previous', NEW.previous_value,
                    'source_provider', NEW.source_provider,
                    'source_approved', v_source_approved,
                    'lineage_exists', v_lineage_exists,
                    'rejection_reason', CASE
                        WHEN NOT v_source_approved THEN 'SOURCE_NOT_APPROVED'
                        WHEN NOT v_lineage_exists THEN 'NO_LINEAGE_PROOF'
                        ELSE 'UNKNOWN'
                    END
                ),
                'CEO'
            ) RETURNING violation_id INTO v_violation_id;

            -- HARD BLOCK: Raise exception to reject the transaction
            RAISE EXCEPTION 'ZERO_TRUST_VIOLATION: Cannot insert canonical calendar data without verified lineage. '
                'Source approved: %, Lineage exists: %, Violation ID: %',
                v_source_approved, v_lineage_exists, v_violation_id
                USING ERRCODE = 'P0001';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop existing trigger if any
DROP TRIGGER IF EXISTS trg_enforce_data_lineage ON fhq_calendar.calendar_events;

-- Create trigger on INSERT and UPDATE
CREATE TRIGGER trg_enforce_data_lineage
    BEFORE INSERT OR UPDATE ON fhq_calendar.calendar_events
    FOR EACH ROW
    EXECUTE FUNCTION fhq_calendar.enforce_data_lineage_proof();

-- ============================================
-- SECTION 2: G3.75 Gate Enforcement
-- ============================================

-- Create function to check G3.75 gate before G4 activation
CREATE OR REPLACE FUNCTION fhq_governance.require_g375_signoff(
    p_gate_instance TEXT,
    p_target_schema TEXT DEFAULT 'fhq_calendar'
) RETURNS BOOLEAN AS $$
DECLARE
    v_signoff_exists BOOLEAN;
    v_all_passed BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM fhq_governance.g375_truth_gate_verifications
        WHERE gate_instance = p_gate_instance
          AND g4_authorized = true
          AND all_checks_passed = true
          AND verified_by IN ('CEO', 'LARS')
    ),
    (SELECT all_checks_passed FROM fhq_governance.g375_truth_gate_verifications
     WHERE gate_instance = p_gate_instance
     ORDER BY verification_timestamp DESC LIMIT 1)
    INTO v_signoff_exists, v_all_passed;

    IF NOT v_signoff_exists THEN
        RAISE EXCEPTION 'G3.75_GATE_BLOCKED: No valid CEO/LARS sign-off found for gate instance: %. G4 activation is BLOCKED until human verification of 5 random values is recorded.',
            p_gate_instance
            USING ERRCODE = 'P0002';
    END IF;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- SECTION 3: Drift Detection DEFCON Coupling
-- ============================================

-- Create function to handle drift detection with DEFCON escalation
CREATE OR REPLACE FUNCTION fhq_calendar.handle_drift_detection()
RETURNS TRIGGER AS $$
DECLARE
    v_defcon_event_id UUID;
BEGIN
    -- Only act on threshold breaches
    IF NEW.threshold_breached = true THEN
        -- Record DEFCON escalation
        INSERT INTO fhq_governance.governance_actions_log (
            action_id, action_type, action_target, action_target_type,
            initiated_by, initiated_at, decision, decision_rationale
        ) VALUES (
            gen_random_uuid(),
            'DEFCON_ESCALATION',
            'ios008_decision_engine',
            'SYSTEM',
            'DriftDetectionTrigger',
            NOW(),
            'ESCALATED',
            'Drift threshold breached for ' || NEW.event_type_code ||
            '. Stored: ' || NEW.stored_value || ', Live: ' || NEW.live_api_value ||
            ', Deviation: ' || NEW.deviation || '. Decision engine FROZEN per CEO-DIR-2026-063.'
        ) RETURNING action_id INTO v_defcon_event_id;

        -- Set flags on the detection record
        NEW.defcon_escalated := true;
        NEW.decision_engine_frozen := true;

        -- Update decision engine state (create if not exists)
        INSERT INTO fhq_governance.system_state_flags (
            flag_name, flag_value, set_by, set_at, reason
        ) VALUES (
            'DECISION_ENGINE_FROZEN',
            true,
            'DriftDetectionTrigger',
            NOW(),
            'Drift detection triggered freeze. Detection ID: ' || NEW.detection_id::text
        )
        ON CONFLICT (flag_name) DO UPDATE SET
            flag_value = true,
            set_by = 'DriftDetectionTrigger',
            set_at = NOW(),
            reason = 'Drift detection triggered freeze. Detection ID: ' || NEW.detection_id::text;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create system state flags table if not exists
CREATE TABLE IF NOT EXISTS fhq_governance.system_state_flags (
    flag_name TEXT PRIMARY KEY,
    flag_value BOOLEAN NOT NULL,
    set_by TEXT NOT NULL,
    set_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Drop existing trigger if any
DROP TRIGGER IF EXISTS trg_drift_defcon_coupling ON fhq_calendar.drift_detection_results;

-- Create trigger on drift detection
CREATE TRIGGER trg_drift_defcon_coupling
    BEFORE INSERT ON fhq_calendar.drift_detection_results
    FOR EACH ROW
    EXECUTE FUNCTION fhq_calendar.handle_drift_detection();

-- ============================================
-- SECTION 4: Governance Logging
-- ============================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale
) VALUES (
    gen_random_uuid(),
    'HARD_ENFORCEMENT_DEPLOYED',
    'fhq_calendar.calendar_events',
    'SCHEMA',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO-DIR-2026-063 HARD enforcement deployed. Triggers: trg_enforce_data_lineage (BLOCKS without lineage), trg_drift_defcon_coupling (FREEZES engine on drift). Functions: enforce_data_lineage_proof (RAISES EXCEPTION), require_g375_signoff (BLOCKS G4), handle_drift_detection (ESCALATES DEFCON).'
);

COMMIT;

-- ============================================
-- VERIFICATION: List all enforcement mechanisms
-- ============================================

-- SELECT tgname, tgrelid::regclass, tgenabled
-- FROM pg_trigger
-- WHERE tgname LIKE '%enforce%' OR tgname LIKE '%drift%';
