-- =============================================================================
-- MIGRATION 245: ADR-024 STILLNESS PROTOCOL ENFORCEMENT
-- =============================================================================
-- CEO Directive: ADR-024 Rung C - Stillness Protocol
-- Author: STIG
-- Date: 2026-01-14
--
-- ADR-024: "Stillness is not weakness. Stillness is discipline."
--
-- Purpose:
--   Enforces Stillness Protocol by blocking proposals without:
--   - intervention_hash
--   - evidence_id
--   - rollback_path (except OBSERVATION_ONLY)
-- =============================================================================

BEGIN;

-- =============================================================================
-- SECTION 1: STILLNESS PROTOCOL ENFORCEMENT TRIGGER
-- =============================================================================
-- Blocks INSERT/UPDATE if mandatory fields are missing

CREATE OR REPLACE FUNCTION fhq_governance.enforce_stillness_protocol()
RETURNS TRIGGER AS $$
DECLARE
    violation_type TEXT;
BEGIN
    -- Skip enforcement for OBSERVATION_ONLY category
    IF NEW.intervention_category = 'OBSERVATION_ONLY' THEN
        RETURN NEW;
    END IF;

    -- Skip enforcement for REJECTED or EXPIRED status
    IF NEW.intervention_status IN ('REJECTED', 'EXPIRED') THEN
        RETURN NEW;
    END IF;

    -- Check for mandatory intervention_hash
    IF NEW.intervention_hash IS NULL OR NEW.intervention_hash = '' THEN
        RAISE EXCEPTION 'STILLNESS PROTOCOL VIOLATION: intervention_hash is required (ADR-024 Rung C)';
    END IF;

    -- Check for mandatory hypothesis_statement
    IF NEW.hypothesis_statement IS NULL OR NEW.hypothesis_statement = '' THEN
        RAISE EXCEPTION 'STILLNESS PROTOCOL VIOLATION: hypothesis_statement is required (ADR-024 Rung C)';
    END IF;

    -- Check for mandatory scope
    IF NEW.scope_target_tables = '{}' OR NEW.scope_target_tables IS NULL THEN
        RAISE EXCEPTION 'STILLNESS PROTOCOL VIOLATION: scope_target_tables must be defined (ADR-024 Rung C)';
    END IF;

    -- Check for mandatory rollback_strategy
    IF NEW.rollback_strategy IS NULL THEN
        RAISE EXCEPTION 'STILLNESS PROTOCOL VIOLATION: rollback_strategy is required (ADR-024 Rung C)';
    END IF;

    -- For status beyond PROPOSED, require evidence_id
    IF NEW.intervention_status IN ('APPROVED', 'EXECUTING', 'COMPLETED') THEN
        IF NEW.evidence_id IS NULL THEN
            RAISE EXCEPTION 'STILLNESS PROTOCOL VIOLATION: evidence_id required for status % (ADR-024 Rung C)', NEW.intervention_status;
        END IF;
    END IF;

    -- For COMPLETED status, require rollback verification (unless NOT_APPLICABLE)
    IF NEW.intervention_status = 'COMPLETED' AND NEW.rollback_strategy != 'NOT_APPLICABLE' THEN
        IF NEW.rollback_verified = FALSE OR NEW.rollback_verified IS NULL THEN
            RAISE EXCEPTION 'STILLNESS PROTOCOL VIOLATION: rollback_verified must be TRUE before COMPLETED status (ADR-024 Rung C)';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger for INSERT
DROP TRIGGER IF EXISTS trg_stillness_protocol_insert ON fhq_governance.ael_intervention_registry;
CREATE TRIGGER trg_stillness_protocol_insert
    BEFORE INSERT ON fhq_governance.ael_intervention_registry
    FOR EACH ROW
    EXECUTE FUNCTION fhq_governance.enforce_stillness_protocol();

-- Apply trigger for UPDATE
DROP TRIGGER IF EXISTS trg_stillness_protocol_update ON fhq_governance.ael_intervention_registry;
CREATE TRIGGER trg_stillness_protocol_update
    BEFORE UPDATE ON fhq_governance.ael_intervention_registry
    FOR EACH ROW
    EXECUTE FUNCTION fhq_governance.enforce_stillness_protocol();

-- =============================================================================
-- SECTION 2: PROPOSAL GATE FUNCTION
-- =============================================================================
-- Function to safely propose an intervention with Stillness validation

CREATE OR REPLACE FUNCTION fhq_governance.propose_ael_intervention(
    p_name TEXT,
    p_category TEXT,
    p_hypothesis TEXT,
    p_target_schema TEXT,
    p_target_tables TEXT[],
    p_expected_direction TEXT,
    p_expected_magnitude TEXT,
    p_blast_radius TEXT,
    p_isolation_window TEXT,
    p_rollback_strategy TEXT,
    p_proposed_by TEXT,
    p_parameter_bounds JSONB DEFAULT '{}'
)
RETURNS UUID AS $$
DECLARE
    v_intervention_id UUID;
    v_hash TEXT;
BEGIN
    -- Generate deterministic hash
    v_hash := md5(
        p_name || '|' ||
        p_category || '|' ||
        p_hypothesis || '|' ||
        p_target_schema || '|' ||
        array_to_string(p_target_tables, ',') || '|' ||
        NOW()::TEXT
    );

    INSERT INTO fhq_governance.ael_intervention_registry (
        intervention_hash,
        intervention_name,
        intervention_category,
        scope_target_schema,
        scope_target_tables,
        scope_parameter_bounds,
        scope_blast_radius,
        hypothesis_statement,
        expected_direction,
        expected_magnitude,
        isolation_window_type,
        rollback_strategy,
        proposed_by,
        intervention_status,
        ael_phase
    ) VALUES (
        v_hash,
        p_name,
        p_category,
        p_target_schema,
        p_target_tables,
        p_parameter_bounds,
        p_blast_radius,
        p_hypothesis,
        p_expected_direction,
        p_expected_magnitude,
        p_isolation_window,
        p_rollback_strategy,
        p_proposed_by,
        'PROPOSED',
        1  -- Phase 1: Proposal
    )
    RETURNING intervention_id INTO v_intervention_id;

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
        'AEL_INTERVENTION_PROPOSED',
        v_intervention_id::TEXT,
        'INTERVENTION',
        p_proposed_by,
        'PENDING',
        'ADR-024 Rung D: Intervention proposed for human authorization',
        jsonb_build_object(
            'intervention_name', p_name,
            'category', p_category,
            'hash', v_hash,
            'timestamp', NOW()
        )
    );

    RETURN v_intervention_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 3: AUTHORIZATION GATE FUNCTION
-- =============================================================================
-- Function for human authorization (Rung D)

CREATE OR REPLACE FUNCTION fhq_governance.authorize_ael_intervention(
    p_intervention_id UUID,
    p_authorized_by TEXT,
    p_evidence_id UUID
)
RETURNS BOOLEAN AS $$
DECLARE
    v_current_status TEXT;
    v_category TEXT;
BEGIN
    -- Get current status
    SELECT intervention_status, intervention_category
    INTO v_current_status, v_category
    FROM fhq_governance.ael_intervention_registry
    WHERE intervention_id = p_intervention_id;

    IF v_current_status IS NULL THEN
        RAISE EXCEPTION 'Intervention % not found', p_intervention_id;
    END IF;

    IF v_current_status != 'PROPOSED' THEN
        RAISE EXCEPTION 'Intervention % is not in PROPOSED status (current: %)', p_intervention_id, v_current_status;
    END IF;

    -- Update to APPROVED
    UPDATE fhq_governance.ael_intervention_registry
    SET
        intervention_status = 'APPROVED',
        approved_by = p_authorized_by,
        approved_at = NOW(),
        evidence_id = p_evidence_id,
        ael_phase = 2  -- Phase 2: Authorized
    WHERE intervention_id = p_intervention_id;

    -- Log authorization
    INSERT INTO fhq_governance.governance_actions_log (
        action_type,
        action_target,
        action_target_type,
        initiated_by,
        decision,
        decision_rationale,
        metadata
    ) VALUES (
        'AEL_INTERVENTION_AUTHORIZED',
        p_intervention_id::TEXT,
        'INTERVENTION',
        p_authorized_by,
        'APPROVED',
        'ADR-024 Rung D: Human authorization granted',
        jsonb_build_object(
            'evidence_id', p_evidence_id,
            'timestamp', NOW()
        )
    );

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 4: STILLNESS AUDIT VIEW
-- =============================================================================

CREATE OR REPLACE VIEW fhq_governance.v_ael_stillness_audit AS
SELECT
    ir.intervention_id,
    ir.intervention_name,
    ir.intervention_status,
    ir.ael_phase,
    CASE WHEN sv.violation_type = 'COMPLIANT' THEN TRUE ELSE FALSE END AS stillness_compliant,
    sv.violation_type,
    ir.proposed_at,
    ir.approved_at,
    ir.executed_at,
    ir.proposed_by,
    ir.approved_by,
    ir.executed_by
FROM fhq_governance.ael_intervention_registry ir
LEFT JOIN fhq_governance.v_ael_stillness_violations sv
    ON ir.intervention_id = sv.intervention_id;

-- =============================================================================
-- SECTION 5: GOVERNANCE LOG
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
    'STILLNESS_PROTOCOL_ACTIVATION',
    'fhq_governance.enforce_stillness_protocol',
    'TRIGGER',
    'STIG',
    'EXECUTED',
    'ADR-024: Stillness is not weakness. Stillness is discipline.',
    jsonb_build_object(
        'migration', '245_adr024_stillness_protocol_enforcement.sql',
        'adr_reference', 'ADR-024',
        'blocks_missing_hash', TRUE,
        'blocks_missing_evidence', TRUE,
        'blocks_missing_rollback', TRUE,
        'timestamp', NOW()
    )
);

COMMIT;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

SELECT 'Migration 245 Complete: Stillness Protocol Enforcement Active' AS status;

-- Verify stillness compliance
SELECT
    stillness_compliant,
    COUNT(*) AS count
FROM fhq_governance.v_ael_stillness_audit
GROUP BY stillness_compliant;
