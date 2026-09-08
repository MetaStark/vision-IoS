-- ============================================================
-- MIGRATION 209: EPISTEMIC IMMUTABILITY CONTROLS
-- ============================================================
-- Directive: CEO-DIR-2026-003
-- Authority Chain: ADR-013 → ADR-004 → CEO-DIR-2026-001 → CEO-DIR-2026-003
-- Author: STIG (CTO)
-- Date: 2026-01-06
-- Classification: GOVERNANCE-CRITICAL (Class A)
--
-- PURPOSE:
--   Enforce append-only immutability for fhq_perception.model_belief_state
--   per CEO-DIR-2026-003 mandate: "The belief layer must be treated as
--   evidence, not data."
--
-- SCOPE:
--   - fhq_perception.model_belief_state (primary target)
--   - fhq_governance.governance_actions_log (violation logging)
--
-- ACCEPTANCE CRITERIA (CEO-DIR-2026-003 Section 5):
--   1. UPDATE and DELETE against model_belief_state fail deterministically
--   2. INSERT continues to function for authorized write-paths
--   3. Violations generate governance-grade audit log entries
--   4. Learning systems verified to read from v_canonical_belief
--
-- CONSTITUTIONAL ALIGNMENT:
--   - ADR-013: "immutable truth snapshotting"
--   - ADR-004: Change gate discipline (G2 approved via CEO directive)
--   - CEO-DIR-2026-001: "Learning SHALL reference belief, not action"
--
-- ============================================================

BEGIN;

-- ============================================================
-- SECTION 1: IMMUTABILITY ENFORCEMENT FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION fhq_perception.enforce_belief_immutability()
RETURNS TRIGGER AS $$
DECLARE
    v_action_id UUID;
BEGIN
    -- Log violation attempt to governance actions log
    INSERT INTO fhq_governance.governance_actions_log (
        action_type,
        action_target,
        action_target_type,
        initiated_by,
        decision,
        decision_rationale,
        metadata
    ) VALUES (
        'IMMUTABILITY_VIOLATION_ATTEMPT',
        CASE
            WHEN TG_OP = 'UPDATE' THEN OLD.belief_id::text
            WHEN TG_OP = 'DELETE' THEN OLD.belief_id::text
            ELSE NULL
        END,
        'fhq_perception.model_belief_state',
        COALESCE(current_setting('app.current_agent', true), current_user),
        'BLOCKED',
        'CEO-DIR-2026-003: model_belief_state is immutable (append-only). ' || TG_OP || ' operations are prohibited.',
        jsonb_build_object(
            'attempted_operation', TG_OP,
            'target_table', TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
            'target_belief_id', OLD.belief_id,
            'target_asset_id', OLD.asset_id,
            'session_user', session_user,
            'current_user', current_user,
            'application_name', current_setting('application_name', true),
            'directive', 'CEO-DIR-2026-003',
            'classification', 'CLASS_A_VIOLATION'
        )
    )
    RETURNING action_id INTO v_action_id;

    -- Raise exception with governance reference
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'IMMUTABILITY_VIOLATION: model_belief_state records cannot be modified. Directive: CEO-DIR-2026-003. Attempted to UPDATE belief_id: %. Violation logged as action_id: %',
            OLD.belief_id, v_action_id;
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'IMMUTABILITY_VIOLATION: model_belief_state records cannot be deleted. Directive: CEO-DIR-2026-003. Attempted to DELETE belief_id: %. Violation logged as action_id: %',
            OLD.belief_id, v_action_id;
    END IF;

    -- This return is never reached, but required for trigger function syntax
    RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fhq_perception.enforce_belief_immutability() IS
'CEO-DIR-2026-003: Enforces append-only immutability for model_belief_state. Blocks UPDATE/DELETE and logs violations to governance_actions_log.';

-- ============================================================
-- SECTION 2: IMMUTABILITY TRIGGER
-- ============================================================

-- Drop trigger if exists (idempotent)
DROP TRIGGER IF EXISTS trg_model_belief_state_immutable ON fhq_perception.model_belief_state;

-- Create immutability trigger
CREATE TRIGGER trg_model_belief_state_immutable
    BEFORE UPDATE OR DELETE ON fhq_perception.model_belief_state
    FOR EACH ROW
    EXECUTE FUNCTION fhq_perception.enforce_belief_immutability();

COMMENT ON TRIGGER trg_model_belief_state_immutable ON fhq_perception.model_belief_state IS
'CEO-DIR-2026-003: Append-only enforcement. Prevents UPDATE/DELETE operations on belief records.';

-- ============================================================
-- SECTION 3: BELIEF DISTRIBUTION VALIDATION FUNCTION
-- ============================================================
-- Per PREFLIGHT_208_BELIEF_DISTRIBUTION_SCHEMA.json

CREATE OR REPLACE FUNCTION fhq_perception.validate_belief_distribution(
    p_distribution JSONB
) RETURNS BOOLEAN AS $$
DECLARE
    v_bull NUMERIC;
    v_bear NUMERIC;
    v_neutral NUMERIC;
    v_stress NUMERIC;
    v_sum NUMERIC;
BEGIN
    -- Check required keys exist
    IF NOT (p_distribution ? 'BULL' AND p_distribution ? 'BEAR' AND
            p_distribution ? 'NEUTRAL' AND p_distribution ? 'STRESS') THEN
        RAISE EXCEPTION 'belief_distribution must contain BULL, BEAR, NEUTRAL, STRESS keys';
    END IF;

    -- Extract values
    v_bull := (p_distribution->>'BULL')::numeric;
    v_bear := (p_distribution->>'BEAR')::numeric;
    v_neutral := (p_distribution->>'NEUTRAL')::numeric;
    v_stress := (p_distribution->>'STRESS')::numeric;

    -- Check range [0, 1]
    IF v_bull < 0 OR v_bull > 1 OR v_bear < 0 OR v_bear > 1 OR
       v_neutral < 0 OR v_neutral > 1 OR v_stress < 0 OR v_stress > 1 THEN
        RAISE EXCEPTION 'All probabilities must be between 0 and 1';
    END IF;

    -- Check sum to one (with floating point tolerance)
    v_sum := v_bull + v_bear + v_neutral + v_stress;
    IF ABS(v_sum - 1.0) > 0.0001 THEN
        RAISE EXCEPTION 'Probabilities must sum to 1.0, got %', v_sum;
    END IF;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fhq_perception.validate_belief_distribution(JSONB) IS
'CEO-DIR-2026-001: Validates belief_distribution JSONB has required keys and sums to 1.0';

-- ============================================================
-- SECTION 4: ENTROPY COMPUTATION FUNCTION
-- ============================================================
-- Per PREFLIGHT_208_BELIEF_DISTRIBUTION_SCHEMA.json

CREATE OR REPLACE FUNCTION fhq_perception.compute_entropy(
    p_distribution JSONB
) RETURNS NUMERIC AS $$
DECLARE
    v_entropy NUMERIC := 0;
    v_prob NUMERIC;
    v_key TEXT;
BEGIN
    FOR v_key IN SELECT jsonb_object_keys(p_distribution)
    LOOP
        v_prob := (p_distribution->>v_key)::numeric;
        IF v_prob > 0 THEN
            v_entropy := v_entropy - (v_prob * log(2, v_prob));
        END IF;
    END LOOP;
    RETURN ROUND(v_entropy, 4);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fhq_perception.compute_entropy(JSONB) IS
'CEO-DIR-2026-001: Computes Shannon entropy of belief distribution. 0 = certainty, 2 = max uncertainty (4 equal states)';

-- ============================================================
-- SECTION 5: LINEAGE HASH COMPUTATION FUNCTION
-- ============================================================
-- Per PREFLIGHT_208_LINEAGE_HASH_CONTRACT.json

CREATE OR REPLACE FUNCTION fhq_perception.compute_lineage_hash(
    p_asset_id TEXT,
    p_timestamp TIMESTAMPTZ,
    p_regime TEXT,
    p_confidence NUMERIC,
    p_distribution JSONB,
    p_prev_hash TEXT DEFAULT 'GENESIS'
) RETURNS TEXT AS $$
DECLARE
    v_belief_data TEXT;
    v_belief_hash TEXT;
    v_lineage_data TEXT;
    v_sorted_dist TEXT;
BEGIN
    -- Sort distribution keys for deterministic hashing
    SELECT string_agg(kv, ',' ORDER BY kv) INTO v_sorted_dist
    FROM (
        SELECT '"' || key || '":' || value as kv
        FROM jsonb_each_text(p_distribution)
    ) sub;

    -- Compute belief hash
    v_belief_data := p_asset_id || '|' || p_timestamp::TEXT || '|' || p_regime || '|' ||
                     TO_CHAR(p_confidence, 'FM0.0000') || '|' || '{' || v_sorted_dist || '}';
    v_belief_hash := encode(sha256(v_belief_data::bytea), 'hex');

    -- Compute lineage hash (chain link)
    v_lineage_data := v_belief_hash || '|' || COALESCE(p_prev_hash, 'GENESIS');
    RETURN encode(sha256(v_lineage_data::bytea), 'hex');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fhq_perception.compute_lineage_hash(TEXT, TIMESTAMPTZ, TEXT, NUMERIC, JSONB, TEXT) IS
'ADR-011: Computes SHA-256 lineage hash for belief records, enabling chain verification and replay integrity';

-- ============================================================
-- SECTION 6: GOVERNANCE LOG ENTRY
-- ============================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'CONSTITUTIONAL_ENFORCEMENT',
    'CEO-DIR-2026-003',
    'MIGRATION',
    'CEO',
    'EXECUTED',
    'Migration 209: Epistemic Immutability Controls deployed. model_belief_state is now append-only per CEO-DIR-2026-003.',
    jsonb_build_object(
        'migration', '209_epistemic_immutability_controls.sql',
        'directive', 'CEO-DIR-2026-003',
        'classification', 'GOVERNANCE-CRITICAL (Class A)',
        'controls_deployed', jsonb_build_array(
            'trg_model_belief_state_immutable',
            'fhq_perception.enforce_belief_immutability()',
            'fhq_perception.validate_belief_distribution()',
            'fhq_perception.compute_entropy()',
            'fhq_perception.compute_lineage_hash()'
        ),
        'constitutional_alignment', jsonb_build_array(
            'ADR-013 (immutable truth snapshotting)',
            'ADR-004 (change gate discipline)',
            'CEO-DIR-2026-001 (epistemic separation)'
        ),
        'executed_by', 'STIG',
        'timestamp', NOW()
    )
);

-- ============================================================
-- SECTION 7: VERIFICATION
-- ============================================================

COMMIT;

-- Verify trigger exists
SELECT
    tgname as trigger_name,
    tgtype as trigger_type,
    tgenabled as enabled
FROM pg_trigger
WHERE tgrelid = 'fhq_perception.model_belief_state'::regclass
AND tgname = 'trg_model_belief_state_immutable';

-- Verify functions exist
SELECT
    proname as function_name,
    pg_get_function_identity_arguments(oid) as arguments
FROM pg_proc
WHERE pronamespace = 'fhq_perception'::regnamespace
AND proname IN (
    'enforce_belief_immutability',
    'validate_belief_distribution',
    'compute_entropy',
    'compute_lineage_hash'
);

-- Migration 209 complete
SELECT 'Migration 209: Epistemic Immutability Controls - DEPLOYED' as status;
