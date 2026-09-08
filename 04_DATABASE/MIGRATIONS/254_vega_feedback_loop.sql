-- Migration 254: VEGA Constitutional Feedback Loop
-- Directive C: Close the loop - Learning outcomes → Governance adjustments → Better learning
-- Scope Limitation: Feedback CANNOT amend ADR text (only thresholds, parameters, procedures)

BEGIN;

-- ============================================================================
-- VEGA Feedback Loop Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.vega_feedback_loop (
    feedback_id SERIAL PRIMARY KEY,
    feedback_type TEXT NOT NULL,  -- 'gate_adjustment', 'threshold_recalibration', 'constraint_relaxation', 'procedure_interpretation'
    source_agent TEXT NOT NULL,   -- Usually 'UMA'
    target_gate TEXT,             -- 'G1', 'G2', 'G3', 'G4' (NULL if not gate-specific)
    target_parameter TEXT,        -- Parameter being adjusted
    current_value JSONB NOT NULL,
    proposed_value JSONB NOT NULL,
    lvi_impact_estimate DECIMAL(5,4),  -- Estimated LVI improvement
    lvi_calculation_method TEXT,       -- How the estimate was derived
    evidence_references TEXT[],        -- Links to evidence files/records
    evidence_hashes TEXT[],            -- SHA-256 hashes for court-proof verification
    vega_ruling TEXT,                  -- 'APPROVED', 'REJECTED', 'DEFERRED'
    ruling_rationale TEXT,
    ruling_agent TEXT,                 -- Usually 'VEGA'
    defcon_at_submission TEXT,
    defcon_at_ruling TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    ruled_at TIMESTAMPTZ,
    CONSTRAINT valid_feedback_type CHECK (feedback_type IN (
        'gate_adjustment',
        'threshold_recalibration',
        'constraint_relaxation',
        'procedure_interpretation'
    )),
    CONSTRAINT valid_ruling CHECK (vega_ruling IS NULL OR vega_ruling IN ('APPROVED', 'REJECTED', 'DEFERRED')),
    CONSTRAINT no_adr_amendment CHECK (
        -- VEGA feedback CANNOT amend ADR text - only operational parameters
        feedback_type != 'adr_amendment'
    )
);

COMMENT ON TABLE fhq_governance.vega_feedback_loop IS
    'VEGA constitutional feedback loop per EC-014 Section 7. Feedback CANNOT amend ADR text.';

COMMENT ON COLUMN fhq_governance.vega_feedback_loop.lvi_impact_estimate IS
    'Estimated LVI improvement. Advisory only - UMA cannot enforce based on this estimate.';

-- ============================================================================
-- Scope Limitation Check Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.validate_feedback_scope()
RETURNS TRIGGER AS $$
BEGIN
    -- Enforce: VEGA feedback CANNOT amend ADR text
    -- Only gate thresholds, operational parameters, and procedure interpretations allowed

    IF NEW.target_parameter ILIKE 'adr_%_text%' OR
       NEW.target_parameter ILIKE '%constitution%' OR
       NEW.target_parameter ILIKE '%charter%' THEN
        RAISE EXCEPTION 'VEGA feedback cannot amend ADR text. Use standard G4 ADR amendment process.';
    END IF;

    -- Validate source agent is authorized
    IF NEW.source_agent NOT IN ('UMA', 'STIG', 'VEGA') THEN
        RAISE EXCEPTION 'Only UMA, STIG, or VEGA can submit feedback. Source: %', NEW.source_agent;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER validate_feedback_scope_trigger
BEFORE INSERT OR UPDATE ON fhq_governance.vega_feedback_loop
FOR EACH ROW EXECUTE FUNCTION fhq_governance.validate_feedback_scope();

-- ============================================================================
-- Feedback Ruling Log (Court-Proof)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.vega_feedback_ruling_log (
    log_id SERIAL PRIMARY KEY,
    feedback_id INTEGER REFERENCES fhq_governance.vega_feedback_loop(feedback_id),
    ruling TEXT NOT NULL,
    rationale TEXT NOT NULL,
    evidence_verified BOOLEAN DEFAULT FALSE,
    defcon_level TEXT NOT NULL,
    constitutional_check JSONB,  -- Which constitutional checks were performed
    ruling_timestamp TIMESTAMPTZ DEFAULT NOW(),
    ruling_signature TEXT  -- Ed25519 signature
);

COMMENT ON TABLE fhq_governance.vega_feedback_ruling_log IS
    'Court-proof log of all VEGA rulings on feedback. Immutable audit trail.';

-- ============================================================================
-- UMA Feedback Statistics View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_governance.uma_feedback_statistics AS
SELECT
    feedback_type,
    COUNT(*) AS total_submissions,
    COUNT(*) FILTER (WHERE vega_ruling = 'APPROVED') AS approved,
    COUNT(*) FILTER (WHERE vega_ruling = 'REJECTED') AS rejected,
    COUNT(*) FILTER (WHERE vega_ruling = 'DEFERRED') AS deferred,
    COUNT(*) FILTER (WHERE vega_ruling IS NULL) AS pending,
    AVG(lvi_impact_estimate) FILTER (WHERE vega_ruling = 'APPROVED') AS avg_approved_lvi_impact,
    AVG(EXTRACT(EPOCH FROM (ruled_at - created_at))/3600)
        FILTER (WHERE ruled_at IS NOT NULL) AS avg_ruling_hours
FROM fhq_governance.vega_feedback_loop
GROUP BY feedback_type;

COMMENT ON VIEW fhq_governance.uma_feedback_statistics IS
    'UMA feedback submission and ruling statistics. Tracks governance efficiency.';

-- ============================================================================
-- DEFCON-Aware Feedback Check
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.check_feedback_defcon_eligibility(
    p_feedback_type TEXT
)
RETURNS JSONB AS $$
DECLARE
    v_defcon TEXT;
BEGIN
    -- Get current DEFCON
    SELECT current_level INTO v_defcon
    FROM fhq_monitoring.defcon_status
    WHERE deactivated_at IS NULL
    ORDER BY activated_at DESC
    LIMIT 1;

    IF v_defcon IS NULL THEN
        v_defcon := 'GREEN';
    END IF;

    -- Per EC-014 Section 7.2:
    -- GREEN/YELLOW: Full operation
    -- ORANGE: Latency reduction only
    -- RED: Analysis-only, no recommendations
    -- BLACK: Suspended

    CASE v_defcon
        WHEN 'GREEN', 'YELLOW' THEN
            RETURN jsonb_build_object(
                'eligible', true,
                'defcon', v_defcon,
                'mode', 'FULL_OPERATION'
            );
        WHEN 'ORANGE' THEN
            IF p_feedback_type = 'threshold_recalibration' THEN
                RETURN jsonb_build_object(
                    'eligible', true,
                    'defcon', v_defcon,
                    'mode', 'LATENCY_REDUCTION_ONLY',
                    'restriction', 'Only latency-reducing adjustments allowed'
                );
            ELSE
                RETURN jsonb_build_object(
                    'eligible', false,
                    'defcon', v_defcon,
                    'reason', 'ORANGE: Only latency reduction feedback allowed'
                );
            END IF;
        WHEN 'RED' THEN
            RETURN jsonb_build_object(
                'eligible', false,
                'defcon', v_defcon,
                'reason', 'RED: Analysis-only mode, no recommendations'
            );
        WHEN 'BLACK' THEN
            RETURN jsonb_build_object(
                'eligible', false,
                'defcon', v_defcon,
                'reason', 'BLACK: UMA suspended'
            );
        ELSE
            RETURN jsonb_build_object(
                'eligible', false,
                'defcon', v_defcon,
                'reason', 'Unknown DEFCON state'
            );
    END CASE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Migration Audit Log
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
    'INFRASTRUCTURE_CREATE',
    'VEGA_FEEDBACK_LOOP',
    'DIRECTIVE_C',
    'STIG',
    NOW(),
    'DEPLOYED',
    'CEO Directive 2026-01-16 - Directive C: VEGA Constitutional Feedback Loop',
    jsonb_build_object(
        'migration', '254_vega_feedback_loop.sql',
        'directive', 'CEO Directive 2026-01-16 - Directive C',
        'tables_created', ARRAY['vega_feedback_loop', 'vega_feedback_ruling_log'],
        'views_created', ARRAY['uma_feedback_statistics'],
        'functions_created', ARRAY['validate_feedback_scope', 'check_feedback_defcon_eligibility'],
        'scope_limitation', 'VEGA feedback CANNOT amend ADR text',
        'defcon_integration', 'Per EC-014 Section 7.2'
    ),
    'STIG',
    NOW()
);

COMMIT;

-- ============================================================================
-- Verification Queries
-- ============================================================================
-- SELECT * FROM fhq_governance.vega_feedback_loop;
-- SELECT * FROM fhq_governance.uma_feedback_statistics;
-- SELECT fhq_governance.check_feedback_defcon_eligibility('gate_adjustment');
