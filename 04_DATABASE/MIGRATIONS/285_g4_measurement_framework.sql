-- Migration 285: G4 24-48h Measurement Framework
-- CEO Success Criteria: Brier improvement vs 0.5358, confidence alignment, LVI increase
-- Date: 2026-01-17
-- Author: STIG
-- Purpose: Mechanical measurement of calibration effectiveness

-- ============================================================================
-- G4 MEASUREMENT FRAMEWORK
-- ============================================================================
-- CEO Success Criteria:
--   1. Brier improves materially vs 0.5358
--   2. Confidence curves align with empirical hit rates
--   3. STRESS no longer pretends certainty
--   4. LVI increases because false learning is gone
-- ============================================================================

-- Step 1: Create measurement checkpoint table
CREATE TABLE IF NOT EXISTS fhq_governance.g4_measurement_checkpoints (
    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    checkpoint_type TEXT NOT NULL,
    checkpoint_name TEXT NOT NULL,
    measurement_timestamp TIMESTAMPTZ DEFAULT NOW(),

    -- Baseline reference
    baseline_brier NUMERIC DEFAULT 0.5358,
    baseline_hit_rate NUMERIC DEFAULT 0.3265,

    -- Current measurements
    current_brier NUMERIC,
    current_hit_rate NUMERIC,
    current_calibration_error NUMERIC,

    -- Deltas
    brier_delta NUMERIC GENERATED ALWAYS AS (baseline_brier - current_brier) STORED,
    hit_rate_delta NUMERIC GENERATED ALWAYS AS (current_hit_rate - baseline_hit_rate) STORED,

    -- By regime
    regime_metrics JSONB,

    -- Verdict
    verdict TEXT CHECK (verdict IN ('IMPROVING', 'STABLE', 'REGRESSING', 'PENDING')),
    verdict_rationale TEXT,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    measured_by TEXT DEFAULT 'STIG'
);

-- Step 2: Create measurement function
CREATE OR REPLACE FUNCTION fhq_governance.capture_g4_checkpoint(
    p_checkpoint_name TEXT DEFAULT 'HOURLY'
)
RETURNS UUID AS $$
DECLARE
    v_checkpoint_id UUID;
    v_current_brier NUMERIC;
    v_current_hit_rate NUMERIC;
    v_regime_metrics JSONB;
    v_verdict TEXT;
    v_rationale TEXT;
BEGIN
    -- Calculate current overall metrics
    SELECT
        AVG(squared_error),
        AVG(CASE WHEN actual_outcome THEN 1.0 ELSE 0.0 END)
    INTO v_current_brier, v_current_hit_rate
    FROM fhq_governance.brier_score_ledger
    WHERE created_at >= NOW() - INTERVAL '24 hours'
    AND eligible_for_calibration = true;

    -- Calculate per-regime metrics
    SELECT jsonb_object_agg(
        regime,
        jsonb_build_object(
            'brier', ROUND(avg_brier::numeric, 4),
            'hit_rate', ROUND(hit_rate::numeric, 4),
            'avg_confidence', ROUND(avg_conf::numeric, 4),
            'count', cnt
        )
    ) INTO v_regime_metrics
    FROM (
        SELECT
            regime,
            AVG(squared_error) as avg_brier,
            AVG(CASE WHEN actual_outcome THEN 1.0 ELSE 0.0 END) as hit_rate,
            AVG(forecast_probability) as avg_conf,
            COUNT(*) as cnt
        FROM fhq_governance.brier_score_ledger
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        AND eligible_for_calibration = true
        GROUP BY regime
    ) t;

    -- Determine verdict
    IF v_current_brier IS NULL THEN
        v_verdict := 'PENDING';
        v_rationale := 'Insufficient data for measurement';
    ELSIF v_current_brier < 0.5358 THEN
        v_verdict := 'IMPROVING';
        v_rationale := 'Brier ' || ROUND(v_current_brier::numeric, 4) || ' < baseline 0.5358. Delta: ' || ROUND((0.5358 - v_current_brier)::numeric, 4);
    ELSIF v_current_brier > 0.5358 + 0.03 THEN
        v_verdict := 'REGRESSING';
        v_rationale := 'Brier ' || ROUND(v_current_brier::numeric, 4) || ' > baseline + 0.03. STOP-LOSS triggered.';
    ELSE
        v_verdict := 'STABLE';
        v_rationale := 'Brier ' || ROUND(v_current_brier::numeric, 4) || ' within tolerance of baseline 0.5358.';
    END IF;

    -- Insert checkpoint
    INSERT INTO fhq_governance.g4_measurement_checkpoints (
        checkpoint_type,
        checkpoint_name,
        current_brier,
        current_hit_rate,
        regime_metrics,
        verdict,
        verdict_rationale
    ) VALUES (
        'G4_CALIBRATION',
        p_checkpoint_name,
        v_current_brier,
        v_current_hit_rate,
        v_regime_metrics,
        v_verdict,
        v_rationale
    )
    RETURNING checkpoint_id INTO v_checkpoint_id;

    RETURN v_checkpoint_id;
END;
$$ LANGUAGE plpgsql;

-- Step 3: Create summary view for CEO
CREATE OR REPLACE VIEW fhq_governance.v_g4_calibration_status AS
SELECT
    checkpoint_name,
    measurement_timestamp,
    ROUND(current_brier::numeric, 4) as current_brier,
    ROUND(baseline_brier::numeric, 4) as baseline_brier,
    ROUND(brier_delta::numeric, 4) as brier_improvement,
    CASE
        WHEN brier_delta > 0 THEN '+' || ROUND((brier_delta / baseline_brier * 100)::numeric, 1) || '%'
        ELSE ROUND((brier_delta / baseline_brier * 100)::numeric, 1) || '%'
    END as improvement_pct,
    verdict,
    verdict_rationale,
    regime_metrics
FROM fhq_governance.g4_measurement_checkpoints
WHERE checkpoint_type = 'G4_CALIBRATION'
ORDER BY measurement_timestamp DESC
LIMIT 10;

-- Step 4: Create stop-loss check function
CREATE OR REPLACE FUNCTION fhq_governance.check_g4_stop_loss()
RETURNS TABLE (
    stop_loss_triggered BOOLEAN,
    current_brier NUMERIC,
    threshold NUMERIC,
    action_required TEXT
) AS $$
DECLARE
    v_brier NUMERIC;
    v_threshold NUMERIC := 0.5358 + 0.03;  -- Baseline + 3% margin
BEGIN
    SELECT AVG(squared_error) INTO v_brier
    FROM fhq_governance.brier_score_ledger
    WHERE created_at >= NOW() - INTERVAL '24 hours'
    AND eligible_for_calibration = true;

    IF v_brier > v_threshold THEN
        RETURN QUERY SELECT
            TRUE,
            v_brier,
            v_threshold,
            'HALT: Brier regression exceeds stop-loss threshold. Rollback calibration.'::TEXT;
    ELSE
        RETURN QUERY SELECT
            FALSE,
            v_brier,
            v_threshold,
            'CONTINUE: Brier within acceptable range.'::TEXT;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Step 5: Capture initial checkpoint (T0)
SELECT fhq_governance.capture_g4_checkpoint('T0_CALIBRATION_BASELINE');

-- Step 6: Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'G4_MEASUREMENT_FRAMEWORK_DEPLOYED',
    'g4_measurement_checkpoints',
    'MEASUREMENT_SYSTEM',
    'CEO',
    'ACTIVE',
    'G4 measurement framework deployed. 24-48h verification period begins. Success = Brier < 0.5358, confidence aligned, LVI increased.',
    jsonb_build_object(
        'baseline_brier', 0.5358,
        'baseline_hit_rate', 0.3265,
        'stop_loss_threshold', 0.5658,
        'measurement_interval', '24 hours',
        'success_criteria', ARRAY[
            'Brier improves materially vs 0.5358',
            'Confidence curves align with hit rates',
            'STRESS no longer pretends certainty',
            'LVI increases'
        ],
        'ceo_principle', 'ROI will not come from brilliance. It will come from not being wrong with confidence.'
    )
);

-- Verification
DO $$
DECLARE
    v_checkpoint RECORD;
BEGIN
    SELECT * INTO v_checkpoint
    FROM fhq_governance.g4_measurement_checkpoints
    WHERE checkpoint_name = 'T0_CALIBRATION_BASELINE'
    ORDER BY created_at DESC LIMIT 1;

    RAISE NOTICE '===========================================';
    RAISE NOTICE 'G4 MEASUREMENT FRAMEWORK ACTIVE';
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'T0 Checkpoint captured';
    RAISE NOTICE 'Baseline Brier: 0.5358';
    RAISE NOTICE 'Stop-loss threshold: 0.5658';
    RAISE NOTICE 'Measurement deadline: 24-48 hours';
    RAISE NOTICE '===========================================';
END $$;
