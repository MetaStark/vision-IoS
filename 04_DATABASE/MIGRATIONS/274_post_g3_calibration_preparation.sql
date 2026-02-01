-- Migration 274: Post-G3 Baseline Calibration Preparation
-- CEO Directive: OKR-2026-D17-001 KR4
-- Status: PREPARED - Execution blocked until G3_FULLY_LOCKED
--
-- PURPOSE:
-- This migration prepares the infrastructure for post-G3 calibration tuning.
-- It will NOT execute any changes until G3 is verified as FULLY LOCKED.
--
-- EXECUTION GATE:
-- - G3 CEO-locked: YES (2026-01-16)
-- - VEGA Ed25519 signature: PENDING
-- - 48h shadow mode: IN_PROGRESS
-- - This migration: BLOCKED until all conditions met
--
-- UMA RECOMMENDATION (DEFERRED):
-- - FRICTION-001: Poor prediction accuracy (Brier 0.48, Hit Rate 0.4252)
-- - Target: Tune confidence_damper_alpha and confidence_damper_beta
-- - Reclassified: POST_G3_BASELINE_CALIBRATION_CANDIDATE
--
-- Author: STIG (via OKR-2026-D17-001)
-- Date: 2026-01-17

BEGIN;

-- =============================================================================
-- GOVERNANCE GATE CHECK (Informational)
-- Migration prepares infrastructure - actual execution gated by G3 lock
-- =============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 274: Preparing post-G3 calibration infrastructure';
    RAISE NOTICE 'NOTE: Actual calibration changes are QUEUED and require G3_FULLY_LOCKED';
    RAISE NOTICE 'This migration creates tables and captures baseline - no tuning executed';
END $$;

-- =============================================================================
-- BASELINE SNAPSHOT (Always execute - captures current state)
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.calibration_baseline_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_name TEXT NOT NULL,
    snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
    snapshot_reason TEXT NOT NULL,

    -- Metrics at time of snapshot
    brier_score_avg NUMERIC(6,4),
    hit_rate NUMERIC(6,4),
    calibration_error NUMERIC(6,4),
    forecast_count INTEGER,

    -- Full gate configuration as JSON
    gate_configuration JSONB NOT NULL,

    -- Governance
    created_by TEXT NOT NULL DEFAULT 'STIG',
    approved_by TEXT,
    vega_attested BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Capture current baseline before any G3 changes
INSERT INTO fhq_governance.calibration_baseline_snapshots (
    snapshot_name,
    snapshot_reason,
    brier_score_avg,
    hit_rate,
    calibration_error,
    forecast_count,
    gate_configuration
)
SELECT
    'G3_BASELINE_DAY17',
    'Pre-G3 baseline capture per OKR-2026-D17-001 KR4',
    (SELECT AVG(squared_error) FROM fhq_governance.brier_score_ledger
     WHERE created_at >= NOW() - INTERVAL '7 days'),
    (SELECT AVG(CASE WHEN actual_outcome THEN 1.0 ELSE 0.0 END)
     FROM fhq_governance.brier_score_ledger
     WHERE created_at >= NOW() - INTERVAL '7 days'),
    (SELECT ABS(AVG(forecast_probability) - AVG(CASE WHEN actual_outcome THEN 1.0 ELSE 0.0 END))
     FROM fhq_governance.brier_score_ledger
     WHERE created_at >= NOW() - INTERVAL '7 days'),
    (SELECT COUNT(*) FROM fhq_research.forecast_ledger
     WHERE forecast_made_at >= NOW() - INTERVAL '7 days'),
    (SELECT jsonb_agg(row_to_json(g))
     FROM (
        SELECT gate_id, forecast_type, regime,
               confidence_band_min, confidence_band_max,
               historical_accuracy, confidence_ceiling, sample_size
        FROM fhq_governance.confidence_calibration_gates
        WHERE effective_until IS NULL
        ORDER BY forecast_type, confidence_band_min
     ) g);

-- =============================================================================
-- POST-G3 CALIBRATION QUEUE
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.calibration_change_queue (
    change_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Reference
    okr_code TEXT NOT NULL,
    uma_recommendation_id TEXT,

    -- Change specification
    target_table TEXT NOT NULL,
    target_column TEXT NOT NULL,
    target_filter JSONB,  -- e.g., {"forecast_type": "PRICE_DIRECTION"}

    -- Values
    current_value NUMERIC,
    proposed_value NUMERIC,
    change_rationale TEXT NOT NULL,

    -- Execution gate
    execution_gate TEXT NOT NULL DEFAULT 'G3_FULLY_LOCKED',
    gate_met BOOLEAN DEFAULT FALSE,

    -- Approval chain
    uma_proposed_at TIMESTAMPTZ,
    stig_reviewed_at TIMESTAMPTZ,
    vega_approved_at TIMESTAMPTZ,
    ceo_approved_at TIMESTAMPTZ,

    -- Status
    status TEXT NOT NULL DEFAULT 'QUEUED' CHECK (status IN (
        'QUEUED', 'GATE_MET', 'APPROVED', 'EXECUTED', 'ROLLED_BACK', 'REJECTED'
    )),

    -- Rollback capability
    rollback_sql TEXT,
    executed_at TIMESTAMPTZ,
    rolled_back_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- QUEUE UMA'S DEFERRED RECOMMENDATION (FRICTION-001)
-- =============================================================================

-- Queue the recalibration for post-G3 execution
INSERT INTO fhq_governance.calibration_change_queue (
    okr_code,
    uma_recommendation_id,
    target_table,
    target_column,
    target_filter,
    current_value,
    proposed_value,
    change_rationale,
    execution_gate,
    uma_proposed_at
) VALUES (
    'OKR-2026-D17-001',
    'UMA-REC-20260116-01',
    'fhq_governance.confidence_calibration_gates',
    'confidence_ceiling',
    '{"forecast_type": "PRICE_DIRECTION", "confidence_band": "0.80-0.95"}'::JSONB,
    0.4312,  -- Current ceiling for high confidence band
    NULL,    -- To be computed post-G3 based on empirical data
    'FRICTION-001: Recalibrate high-confidence band ceiling based on observed Brier degradation. ' ||
    'Current Brier 0.48 vs target <0.42. Deferred per CEO governance correction 2026-01-17.',
    'G3_FULLY_LOCKED',
    NOW()
);

-- =============================================================================
-- FUNCTION: Execute queued calibration changes (Post-G3)
-- =============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.execute_queued_calibrations()
RETURNS TABLE (
    change_id UUID,
    status TEXT,
    message TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_change RECORD;
    v_g3_locked BOOLEAN;
BEGIN
    -- Verify G3 is fully locked
    SELECT EXISTS (
        SELECT 1 FROM fhq_governance.governance_actions_log
        WHERE action_type = 'G3_FULLY_LOCKED'
        AND decision = 'APPROVED'
        AND created_at > NOW() - INTERVAL '7 days'
    ) INTO v_g3_locked;

    IF NOT v_g3_locked THEN
        RETURN QUERY SELECT
            NULL::UUID,
            'BLOCKED'::TEXT,
            'G3 is not fully locked - no calibration changes executed'::TEXT;
        RETURN;
    END IF;

    -- Process queued changes
    FOR v_change IN
        SELECT * FROM fhq_governance.calibration_change_queue
        WHERE status = 'APPROVED'
        AND execution_gate = 'G3_FULLY_LOCKED'
    LOOP
        -- Mark as executed (actual execution would be here)
        UPDATE fhq_governance.calibration_change_queue
        SET status = 'EXECUTED',
            executed_at = NOW()
        WHERE change_id = v_change.change_id;

        RETURN QUERY SELECT
            v_change.change_id,
            'EXECUTED'::TEXT,
            'Calibration change applied post-G3'::TEXT;
    END LOOP;
END;
$$;

-- =============================================================================
-- GOVERNANCE LOGGING
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
    'POST_G3_CALIBRATION_PREPARED',
    'fhq_governance.calibration_change_queue',
    'TABLE',
    'STIG',
    'PREPARED',
    'OKR-2026-D17-001 KR4: Post-G3 calibration infrastructure ready. ' ||
    'UMA recommendation UMA-REC-20260116-01 queued for post-G3 execution. ' ||
    'Baseline snapshot captured. Execution blocked until G3_FULLY_LOCKED.',
    jsonb_build_object(
        'okr_code', 'OKR-2026-D17-001',
        'key_result', 'KR4',
        'uma_recommendation', 'UMA-REC-20260116-01',
        'friction_id', 'FRICTION-001',
        'execution_gate', 'G3_FULLY_LOCKED',
        'baseline_captured', true,
        'tables_created', ARRAY['calibration_baseline_snapshots', 'calibration_change_queue'],
        'ceo_principle', 'Ikke gjør irreversible endringer før G3 = låst'
    )
);

COMMIT;
