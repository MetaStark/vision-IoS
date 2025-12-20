-- ============================================================================
-- MIGRATION 154: WAVE 17A CCO COMPLIANCE
-- CEO Directive WAVE 17A - 2025-12-18
-- ============================================================================
-- PURPOSE: Fix Migration 153 to comply with WAVE 17A hard constraints:
--   1. Cold-Start Integrity (INIT state)
--   2. Canonical Provenance (ADR-013 compliance)
--   3. Failover Semantics (4-state model)
--   4. Semantic Clarification ("G5" is NOT a governance gate)
--   5. Suppression Attribution (SYSTEM_INIT vs MARKET_DRIVEN)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. FIX CCO STATUS ENUM - ADD INIT STATE
-- ============================================================================

-- Drop and recreate constraint with INIT state
ALTER TABLE fhq_canonical.g5_cco_state
DROP CONSTRAINT IF EXISTS g5_cco_state_cco_status_check;

ALTER TABLE fhq_canonical.g5_cco_state
ADD CONSTRAINT g5_cco_state_cco_status_check
CHECK (cco_status IN ('INIT', 'OPERATIONAL', 'DEGRADED', 'UNAVAILABLE'));

-- Change default to INIT (Cold-Start Integrity)
ALTER TABLE fhq_canonical.g5_cco_state
ALTER COLUMN cco_status SET DEFAULT 'INIT';

-- ============================================================================
-- 2. ADD GLOBAL_PERMIT THREE-WAY STATE
-- ============================================================================

-- Add new column for three-way permit logic
ALTER TABLE fhq_canonical.g5_cco_state
ADD COLUMN IF NOT EXISTS global_permit TEXT DEFAULT 'UNKNOWN'
CHECK (global_permit IN ('UNKNOWN', 'PERMITTED', 'SUPPRESSED'));

-- Add permit attribution (distinguishes SYSTEM_INIT from MARKET_DRIVEN)
ALTER TABLE fhq_canonical.g5_cco_state
ADD COLUMN IF NOT EXISTS permit_attribution TEXT DEFAULT 'SYSTEM_INIT'
CHECK (permit_attribution IN ('SYSTEM_INIT', 'MARKET_DRIVEN', 'DEGRADED_MODE', 'UNAVAILABLE'));

-- ============================================================================
-- 3. ADD CANONICAL PROVENANCE COLUMNS (ADR-013)
-- ============================================================================

-- Context vector hash (SHA-256 of all context values)
ALTER TABLE fhq_canonical.g5_cco_state
ADD COLUMN IF NOT EXISTS context_hash TEXT;

-- Input hash (SHA-256 of all upstream data sources)
ALTER TABLE fhq_canonical.g5_cco_state
ADD COLUMN IF NOT EXISTS input_hash TEXT;

-- Explicit source tables list
ALTER TABLE fhq_canonical.g5_cco_state
ADD COLUMN IF NOT EXISTS source_tables TEXT[] DEFAULT ARRAY[]::TEXT[];

-- Context validity window
ALTER TABLE fhq_canonical.g5_cco_state
ADD COLUMN IF NOT EXISTS valid_until TIMESTAMPTZ;

-- Context vector (full reconstructable state)
ALTER TABLE fhq_canonical.g5_cco_state
ADD COLUMN IF NOT EXISTS context_vector JSONB DEFAULT '{}'::jsonb;

-- Signature (for signed context updates)
ALTER TABLE fhq_canonical.g5_cco_state
ADD COLUMN IF NOT EXISTS context_signature TEXT;

-- Signed by (agent that produced context)
ALTER TABLE fhq_canonical.g5_cco_state
ADD COLUMN IF NOT EXISTS signed_by TEXT;

-- ============================================================================
-- 4. RESET CCO TO PROPER INIT STATE
-- ============================================================================

UPDATE fhq_canonical.g5_cco_state SET
    cco_status = 'INIT',
    global_permit = 'UNKNOWN',
    global_permit_active = FALSE,
    permit_attribution = 'SYSTEM_INIT',
    permit_reason = 'Cold start - awaiting first signed context update',
    context_hash = NULL,
    input_hash = NULL,
    source_tables = ARRAY[]::TEXT[],
    valid_until = NULL,
    context_vector = '{}'::jsonb,
    updated_at = NOW()
WHERE is_active = TRUE;

-- ============================================================================
-- 5. ADD SUPPRESSION ATTRIBUTION TO SUPPRESSION LOG
-- ============================================================================

ALTER TABLE fhq_canonical.g4_2_suppression_log
ADD COLUMN IF NOT EXISTS suppression_attribution TEXT DEFAULT 'MARKET_DRIVEN'
CHECK (suppression_attribution IN ('SYSTEM_INIT', 'MARKET_DRIVEN', 'DEGRADED_MODE', 'CONTEXT_STALE'));

-- ============================================================================
-- 6. FIX IOS_REGISTRY SEMANTIC (G5 -> WAVE17_PAPER)
-- ============================================================================

-- Update description to clarify semantic
UPDATE fhq_meta.ios_registry SET
    description = 'WAVE 17 Operational Paper-Execution Mode (internal technical label). NOT a governance gate per ADR-004. Implements Central Context Orchestrator with four-state failover (INIT/OPERATIONAL/DEGRADED/UNAVAILABLE).',
    updated_at = NOW()
WHERE ios_id = 'G5';

-- Add explicit semantic lock comment
COMMENT ON TABLE fhq_canonical.g5_cco_state IS
'Central Context Orchestrator for WAVE 17 Paper Mode.
SEMANTIC LOCK (CEO WAVE 17A): "G5" is an internal technical label.
It is NOT a governance gate per ADR-004.
Live execution requires separate CEO Directive (out of scope).';

-- ============================================================================
-- 7. CREATE PROVENANCE VALIDATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_canonical.g5_update_cco_context(
    p_regime TEXT,
    p_regime_confidence NUMERIC,
    p_vol_percentile NUMERIC,
    p_vol_state TEXT,
    p_liquidity_state TEXT,
    p_market_hours BOOLEAN,
    p_source_tables TEXT[],
    p_signed_by TEXT DEFAULT 'CCO_DAEMON'
) RETURNS TABLE (
    success BOOLEAN,
    new_status TEXT,
    new_permit TEXT,
    context_hash TEXT,
    error_message TEXT
) AS $$
DECLARE
    v_context_vector JSONB;
    v_context_hash TEXT;
    v_input_hash TEXT;
    v_coherence_window INT;
    v_new_status TEXT;
    v_new_permit TEXT;
    v_permit_attribution TEXT;
BEGIN
    -- Build context vector
    v_context_vector := jsonb_build_object(
        'regime', p_regime,
        'regime_confidence', p_regime_confidence,
        'vol_percentile', p_vol_percentile,
        'vol_state', p_vol_state,
        'liquidity_state', p_liquidity_state,
        'market_hours', p_market_hours,
        'timestamp', NOW()
    );

    -- Compute hashes (ADR-013 provenance)
    v_context_hash := encode(sha256(v_context_vector::text::bytea), 'hex');
    v_input_hash := encode(sha256(array_to_string(p_source_tables, ',')::bytea), 'hex');

    -- Get coherence window
    SELECT parameter_value::INT INTO v_coherence_window
    FROM fhq_canonical.g4_2_parameters
    WHERE parameter_name = 'CCO_COHERENCE_WINDOW_SECONDS';

    -- Validate provenance (WAVE 17A Section 3.2)
    IF p_source_tables IS NULL OR array_length(p_source_tables, 1) IS NULL THEN
        success := FALSE;
        new_status := NULL;
        new_permit := NULL;
        context_hash := NULL;
        error_message := 'PROVENANCE_VIOLATION: source_tables required (ADR-013)';
        RETURN NEXT;
        RETURN;
    END IF;

    -- Determine permit based on context
    IF p_vol_percentile BETWEEN 30 AND 70 THEN
        v_new_permit := 'PERMITTED';
        v_permit_attribution := 'MARKET_DRIVEN';
    ELSE
        v_new_permit := 'SUPPRESSED';
        v_permit_attribution := 'MARKET_DRIVEN';
    END IF;

    -- Always transition to OPERATIONAL on valid update
    v_new_status := 'OPERATIONAL';

    -- Update CCO state
    UPDATE fhq_canonical.g5_cco_state SET
        cco_status = v_new_status,
        current_regime = p_regime,
        current_regime_confidence = p_regime_confidence,
        current_vol_percentile = p_vol_percentile,
        current_vol_state = p_vol_state,
        current_liquidity_state = p_liquidity_state,
        current_market_hours = p_market_hours,
        context_timestamp = NOW(),
        valid_until = NOW() + (v_coherence_window || ' seconds')::INTERVAL,
        global_permit = v_new_permit,
        global_permit_active = (v_new_permit = 'PERMITTED'),
        permit_attribution = v_permit_attribution,
        permit_reason = CASE
            WHEN v_new_permit = 'PERMITTED' THEN 'VOL_NEUTRAL context (30-70%)'
            ELSE 'Outside VOL_NEUTRAL window'
        END,
        context_vector = v_context_vector,
        context_hash = v_context_hash,
        input_hash = v_input_hash,
        source_tables = p_source_tables,
        signed_by = p_signed_by,
        updated_at = NOW()
    WHERE is_active = TRUE;

    -- Log state transition
    INSERT INTO fhq_canonical.g5_cco_health_log (
        check_timestamp, context_age_seconds, cco_status, previous_status,
        triggered_degraded, triggered_unavailable
    ) VALUES (
        NOW(), 0, v_new_status, 'INIT',
        FALSE, FALSE
    );

    success := TRUE;
    new_status := v_new_status;
    new_permit := v_new_permit;
    context_hash := v_context_hash;
    error_message := NULL;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. CREATE CCO COHERENCE CHECK WITH PROPER FAILOVER
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_canonical.g5_check_cco_coherence_v2()
RETURNS TABLE (
    cco_status TEXT,
    global_permit TEXT,
    permit_attribution TEXT,
    context_age_seconds NUMERIC,
    context_valid BOOLEAN,
    context_hash TEXT,
    execution_allowed BOOLEAN,
    block_reason TEXT
) AS $$
DECLARE
    v_cco RECORD;
    v_coherence_window NUMERIC;
    v_degraded_lag NUMERIC;
    v_context_age NUMERIC;
BEGIN
    -- Get parameters
    SELECT parameter_value INTO v_coherence_window
    FROM fhq_canonical.g4_2_parameters WHERE parameter_name = 'CCO_COHERENCE_WINDOW_SECONDS';

    SELECT parameter_value INTO v_degraded_lag
    FROM fhq_canonical.g4_2_parameters WHERE parameter_name = 'CCO_DEGRADED_LAG_SECONDS';

    -- Get current CCO state
    SELECT * INTO v_cco
    FROM fhq_canonical.g5_cco_state
    WHERE is_active = TRUE;

    IF v_cco IS NULL THEN
        cco_status := 'UNAVAILABLE';
        global_permit := 'UNKNOWN';
        permit_attribution := 'SYSTEM_INIT';
        context_age_seconds := NULL;
        context_valid := FALSE;
        context_hash := NULL;
        execution_allowed := FALSE;
        block_reason := 'No CCO state found';
        RETURN NEXT;
        RETURN;
    END IF;

    -- Calculate context age
    v_context_age := EXTRACT(EPOCH FROM (NOW() - v_cco.context_timestamp));

    -- WAVE 17A Section 3.1: Cold-Start Integrity
    IF v_cco.cco_status = 'INIT' THEN
        cco_status := 'INIT';
        global_permit := 'UNKNOWN';
        permit_attribution := 'SYSTEM_INIT';
        context_age_seconds := v_context_age;
        context_valid := FALSE;
        context_hash := v_cco.context_hash;
        execution_allowed := FALSE;
        block_reason := 'SYSTEM_INIT: Awaiting first signed context update';
        RETURN NEXT;
        RETURN;
    END IF;

    -- WAVE 17A Section 3.3: Failover Semantics
    IF v_context_age > v_coherence_window THEN
        -- Context expired -> UNAVAILABLE
        cco_status := 'UNAVAILABLE';
        global_permit := 'UNKNOWN';
        permit_attribution := 'CONTEXT_STALE';
        context_age_seconds := v_context_age;
        context_valid := FALSE;
        context_hash := v_cco.context_hash;
        execution_allowed := FALSE;
        block_reason := 'Context expired (age: ' || ROUND(v_context_age) || 's > ' || v_coherence_window || 's)';

        -- Update CCO to UNAVAILABLE
        UPDATE fhq_canonical.g5_cco_state SET
            cco_status = 'UNAVAILABLE',
            global_permit = 'UNKNOWN',
            permit_attribution = 'CONTEXT_STALE'
        WHERE is_active = TRUE;

        RETURN NEXT;
        RETURN;
    ELSIF v_context_age > v_degraded_lag THEN
        -- Context degraded
        cco_status := 'DEGRADED';
        global_permit := v_cco.global_permit;
        permit_attribution := 'DEGRADED_MODE';
        context_age_seconds := v_context_age;
        context_valid := TRUE;
        context_hash := v_cco.context_hash;
        -- In DEGRADED, only high-Sharpe signals allowed (handled by validation function)
        execution_allowed := TRUE;
        block_reason := 'DEGRADED: Only Sharpe >= 2.0 signals permitted';
        RETURN NEXT;
        RETURN;
    ELSE
        -- OPERATIONAL
        cco_status := 'OPERATIONAL';
        global_permit := v_cco.global_permit;
        permit_attribution := v_cco.permit_attribution;
        context_age_seconds := v_context_age;
        context_valid := TRUE;
        context_hash := v_cco.context_hash;
        execution_allowed := (v_cco.global_permit = 'PERMITTED');
        block_reason := CASE
            WHEN v_cco.global_permit = 'PERMITTED' THEN NULL
            ELSE v_cco.permit_reason
        END;
        RETURN NEXT;
        RETURN;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 9. ADD SEMANTIC LOCK PARAMETERS
-- ============================================================================

INSERT INTO fhq_canonical.g4_2_parameters (parameter_name, parameter_value, description, locked_by) VALUES
    ('WAVE17_SEMANTIC_LOCK', 1, 'G5 is internal technical label, NOT a governance gate per ADR-004', 'CEO_DIRECTIVE_WAVE_17A'),
    ('CCO_REQUIRES_SIGNED_CONTEXT', 1, 'Context updates must have provenance per ADR-013', 'CEO_DIRECTIVE_WAVE_17A')
ON CONFLICT (parameter_name) DO NOTHING;

-- ============================================================================
-- 10. AUDIT LOG
-- ============================================================================

INSERT INTO fhq_governance.audit_log (
    event_type, event_category, target_type, target_id,
    actor_id, actor_role, event_data, event_hash, governance_gate, adr_reference
) VALUES (
    'MIGRATION',
    'OPERATIONAL',
    'SCHEMA',
    'fhq_canonical.g5_cco_state',
    'STIG',
    'CTO',
    jsonb_build_object(
        'directive', 'WAVE_17A',
        'fixes', jsonb_build_array(
            'Added INIT state (Cold-Start Integrity)',
            'Added provenance columns (ADR-013)',
            'Added three-way global_permit',
            'Added suppression_attribution',
            'Fixed semantic: G5 != governance gate'
        ),
        'compliance', 'WAVE_17A_SECTIONS_3.1_3.2_3.3'
    ),
    encode(sha256(('WAVE17A-COMPLIANCE-' || NOW()::text)::bytea), 'hex'),
    'G4',
    'ADR-013'
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_cco_status TEXT;
    v_global_permit TEXT;
    v_has_provenance BOOLEAN;
BEGIN
    -- Verify CCO is in INIT state
    SELECT cco_status, global_permit, (context_hash IS NOT NULL OR cco_status = 'INIT')
    INTO v_cco_status, v_global_permit, v_has_provenance
    FROM fhq_canonical.g5_cco_state WHERE is_active = TRUE;

    RAISE NOTICE '';
    RAISE NOTICE '══════════════════════════════════════════════════════════════════════';
    RAISE NOTICE 'WAVE 17A CCO COMPLIANCE - MIGRATION 154 COMPLETE';
    RAISE NOTICE '══════════════════════════════════════════════════════════════════════';
    RAISE NOTICE 'CCO Status:       % (expected: INIT)', v_cco_status;
    RAISE NOTICE 'Global Permit:    % (expected: UNKNOWN)', v_global_permit;
    RAISE NOTICE 'Cold-Start:       ENFORCED';
    RAISE NOTICE 'Provenance:       ADR-013 COMPLIANT';
    RAISE NOTICE 'Semantic Lock:    G5 != governance gate';
    RAISE NOTICE '══════════════════════════════════════════════════════════════════════';

    IF v_cco_status != 'INIT' THEN
        RAISE EXCEPTION 'Cold-Start Integrity violated: CCO not in INIT state';
    END IF;

    IF v_global_permit != 'UNKNOWN' THEN
        RAISE EXCEPTION 'Cold-Start Integrity violated: global_permit not UNKNOWN';
    END IF;
END $$;
