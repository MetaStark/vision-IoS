-- Migration 226: Calibration Gates Infrastructure
-- Authority: CEO-DIR-2026-032 "The Diagnostic Pivot"
-- Executed by: STIG (CTO)
-- Date: 2026-01-10
--
-- PURPOSE: Implement confidence ceiling enforcement to address catastrophic
-- inverse calibration where higher confidence correlates with LOWER accuracy.
--
-- HARDENING UPGRADES (per CEO directive):
-- 1. Sample-size floor: Gates only activate when n >= 100
-- 2. Asymmetric safety margin: +5% below 50%, +2% at 50-60%, +0% above 60%
-- 3. Regime precedence: exact match > forecast_type+ALL > global fallback

-- ============================================================================
-- 1. CORE TABLES
-- ============================================================================

-- Active confidence gates configuration
CREATE TABLE IF NOT EXISTS fhq_governance.confidence_calibration_gates (
    gate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    forecast_type TEXT NOT NULL,
    regime TEXT DEFAULT 'ALL',  -- 'ALL', 'BULL', 'BEAR', 'NEUTRAL'
    confidence_band_min NUMERIC(5,4) NOT NULL,
    confidence_band_max NUMERIC(5,4) NOT NULL,
    historical_accuracy NUMERIC(5,4) NOT NULL,
    sample_size INTEGER NOT NULL,
    confidence_ceiling NUMERIC(5,4) NOT NULL,
    safety_margin NUMERIC(5,4) NOT NULL,
    calculation_window_days INTEGER DEFAULT 30,
    effective_from TIMESTAMPTZ DEFAULT NOW(),
    effective_until TIMESTAMPTZ,
    approved_by TEXT NOT NULL,
    approval_timestamp TIMESTAMPTZ DEFAULT NOW(),
    vega_attestation_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- CONSTRAINT: Valid band range
    CONSTRAINT valid_band CHECK (confidence_band_min < confidence_band_max),
    -- CONSTRAINT: Ceiling cannot exceed 95%
    CONSTRAINT valid_ceiling CHECK (confidence_ceiling <= 0.95),
    -- CONSTRAINT: Sample size floor (Hardening #1)
    CONSTRAINT min_sample_size CHECK (sample_size >= 100)
);

-- Gate history for audit trail
CREATE TABLE IF NOT EXISTS fhq_governance.calibration_gate_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gate_id UUID NOT NULL,
    action TEXT NOT NULL,  -- 'CREATED', 'UPDATED', 'DEACTIVATED', 'RECALIBRATED'
    old_ceiling NUMERIC(5,4),
    new_ceiling NUMERIC(5,4),
    old_accuracy NUMERIC(5,4),
    new_accuracy NUMERIC(5,4),
    change_reason TEXT,
    changed_by TEXT NOT NULL,
    changed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Gate violation log - records when forecasts exceed gates
CREATE TABLE IF NOT EXISTS fhq_governance.gate_violation_log (
    violation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    forecast_id UUID,
    original_confidence NUMERIC(5,4) NOT NULL,
    applied_ceiling NUMERIC(5,4) NOT NULL,
    gate_id UUID,
    forecast_type TEXT NOT NULL,
    regime TEXT,
    confidence_reduction NUMERIC(5,4) GENERATED ALWAYS AS (original_confidence - applied_ceiling) STORED,
    violation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    enforced_by TEXT DEFAULT 'STIG'
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_gates_active ON fhq_governance.confidence_calibration_gates
    (forecast_type, regime, effective_from, effective_until);
CREATE INDEX IF NOT EXISTS idx_violations_timestamp ON fhq_governance.gate_violation_log
    (violation_timestamp DESC);

-- ============================================================================
-- 2. ASYMMETRIC SAFETY MARGIN FUNCTION (Hardening #2)
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.calculate_asymmetric_safety_margin(
    p_historical_accuracy NUMERIC
)
RETURNS NUMERIC AS $$
BEGIN
    -- Asymmetric safety margin: keeps humility longer than optimism
    -- +5% when accuracy < 50%
    -- +2% when accuracy >= 50% and < 60%
    -- +0% when accuracy >= 60%
    CASE
        WHEN p_historical_accuracy < 0.50 THEN RETURN 0.05;
        WHEN p_historical_accuracy < 0.60 THEN RETURN 0.02;
        ELSE RETURN 0.00;
    END CASE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fhq_governance.calculate_asymmetric_safety_margin IS
    'Hardening #2: Asymmetric safety margin prevents confidence from outrunning truth during recovery.
     +5% below 50%, +2% at 50-60%, +0% above 60%.';

-- ============================================================================
-- 3. CONFIDENCE CEILING LOOKUP WITH PRECEDENCE (Hardening #3)
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.get_active_confidence_ceiling(
    p_forecast_type TEXT,
    p_regime TEXT DEFAULT 'ALL'
)
RETURNS TABLE (
    ceiling NUMERIC,
    gate_id UUID,
    match_type TEXT,
    historical_accuracy NUMERIC,
    sample_size INTEGER
) AS $$
BEGIN
    -- PRECEDENCE ORDER (Hardening #3):
    -- 1. Exact match: (forecast_type, regime)
    -- 2. Type + ALL: (forecast_type, 'ALL')
    -- 3. Global fallback: conservative 0.45

    -- Try exact match first
    RETURN QUERY
    SELECT
        g.confidence_ceiling,
        g.gate_id,
        'EXACT'::TEXT as match_type,
        g.historical_accuracy,
        g.sample_size
    FROM fhq_governance.confidence_calibration_gates g
    WHERE g.forecast_type = p_forecast_type
    AND g.regime = p_regime
    AND g.effective_from <= NOW()
    AND (g.effective_until IS NULL OR g.effective_until > NOW())
    ORDER BY g.confidence_ceiling ASC
    LIMIT 1;

    IF FOUND THEN RETURN; END IF;

    -- Try forecast_type + ALL
    RETURN QUERY
    SELECT
        g.confidence_ceiling,
        g.gate_id,
        'TYPE_ALL'::TEXT as match_type,
        g.historical_accuracy,
        g.sample_size
    FROM fhq_governance.confidence_calibration_gates g
    WHERE g.forecast_type = p_forecast_type
    AND g.regime = 'ALL'
    AND g.effective_from <= NOW()
    AND (g.effective_until IS NULL OR g.effective_until > NOW())
    ORDER BY g.confidence_ceiling ASC
    LIMIT 1;

    IF FOUND THEN RETURN; END IF;

    -- Global fallback: conservative 0.45 (no gate found)
    RETURN QUERY
    SELECT
        0.45::NUMERIC as ceiling,
        NULL::UUID as gate_id,
        'GLOBAL_FALLBACK'::TEXT as match_type,
        NULL::NUMERIC as historical_accuracy,
        NULL::INTEGER as sample_size;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.get_active_confidence_ceiling IS
    'Hardening #3: Regime-conditional override precedence.
     Resolution order: exact (type+regime) > type+ALL > global fallback (0.45)';

-- ============================================================================
-- 4. ENFORCEMENT FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.enforce_calibration_gate(
    p_forecast_id UUID,
    p_confidence NUMERIC,
    p_forecast_type TEXT,
    p_regime TEXT DEFAULT 'ALL'
)
RETURNS TABLE (
    adjusted_confidence NUMERIC,
    was_capped BOOLEAN,
    gate_id UUID,
    match_type TEXT
) AS $$
DECLARE
    v_ceiling_rec RECORD;
BEGIN
    -- Get the active ceiling using precedence rules
    SELECT * INTO v_ceiling_rec
    FROM fhq_governance.get_active_confidence_ceiling(p_forecast_type, p_regime);

    IF p_confidence > v_ceiling_rec.ceiling THEN
        -- Log violation
        INSERT INTO fhq_governance.gate_violation_log (
            forecast_id, original_confidence, applied_ceiling,
            gate_id, forecast_type, regime, enforced_by
        ) VALUES (
            p_forecast_id, p_confidence, v_ceiling_rec.ceiling,
            v_ceiling_rec.gate_id, p_forecast_type, p_regime, 'STIG'
        );

        RETURN QUERY SELECT
            v_ceiling_rec.ceiling,
            TRUE,
            v_ceiling_rec.gate_id,
            v_ceiling_rec.match_type;
    ELSE
        RETURN QUERY SELECT
            p_confidence,
            FALSE,
            v_ceiling_rec.gate_id,
            v_ceiling_rec.match_type;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. WEEKLY RECALIBRATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.recalculate_calibration_gates(
    p_window_days INTEGER DEFAULT 30,
    p_min_sample_size INTEGER DEFAULT 100,
    p_approver TEXT DEFAULT 'STIG'
)
RETURNS TABLE (
    forecast_type TEXT,
    regime TEXT,
    historical_accuracy NUMERIC,
    sample_size INTEGER,
    safety_margin NUMERIC,
    new_ceiling NUMERIC,
    status TEXT
) AS $$
DECLARE
    v_rec RECORD;
    v_safety NUMERIC;
    v_ceiling NUMERIC;
BEGIN
    -- Calculate accuracy per band from forecast_outcome_pairs
    FOR v_rec IN (
        SELECT
            fl.forecast_type,
            COALESCE(bs.dominant_regime, 'ALL') as regime,
            ROUND(AVG(CASE WHEN fop.hit_rate_contribution THEN 1 ELSE 0 END)::numeric, 4) as accuracy,
            COUNT(*) as n
        FROM fhq_research.forecast_outcome_pairs fop
        JOIN fhq_research.forecast_ledger fl ON fop.forecast_id = fl.forecast_id
        LEFT JOIN fhq_perception.model_belief_state bs
            ON bs.created_at::date = fl.forecast_made_at::date
        WHERE fop.reconciled_at >= NOW() - (p_window_days || ' days')::interval
        GROUP BY fl.forecast_type, COALESCE(bs.dominant_regime, 'ALL')
        HAVING COUNT(*) >= p_min_sample_size
    )
    LOOP
        -- Calculate asymmetric safety margin
        v_safety := fhq_governance.calculate_asymmetric_safety_margin(v_rec.accuracy);
        v_ceiling := LEAST(0.95, v_rec.accuracy + v_safety);

        -- Deactivate old gate
        UPDATE fhq_governance.confidence_calibration_gates
        SET effective_until = NOW()
        WHERE forecast_type = v_rec.forecast_type
        AND regime = v_rec.regime
        AND effective_until IS NULL;

        -- Insert new gate
        INSERT INTO fhq_governance.confidence_calibration_gates (
            forecast_type, regime, confidence_band_min, confidence_band_max,
            historical_accuracy, sample_size, confidence_ceiling, safety_margin,
            calculation_window_days, approved_by
        ) VALUES (
            v_rec.forecast_type, v_rec.regime, 0.0, 1.0,
            v_rec.accuracy, v_rec.n, v_ceiling, v_safety,
            p_window_days, p_approver
        );

        -- Log history
        INSERT INTO fhq_governance.calibration_gate_history (
            gate_id, action, new_ceiling, new_accuracy, change_reason, changed_by
        ) VALUES (
            (SELECT gate_id FROM fhq_governance.confidence_calibration_gates
             WHERE forecast_type = v_rec.forecast_type AND regime = v_rec.regime
             AND effective_until IS NULL LIMIT 1),
            'RECALIBRATED',
            v_ceiling,
            v_rec.accuracy,
            'Weekly recalibration from ' || p_window_days || ' day window',
            p_approver
        );

        RETURN QUERY SELECT
            v_rec.forecast_type,
            v_rec.regime,
            v_rec.accuracy,
            v_rec.n,
            v_safety,
            v_ceiling,
            'UPDATED'::TEXT;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. INITIAL GATE POPULATION
-- ============================================================================

-- Populate initial gates from historical accuracy data
-- Uses asymmetric safety margin and respects sample-size floor
INSERT INTO fhq_governance.confidence_calibration_gates (
    forecast_type, regime, confidence_band_min, confidence_band_max,
    historical_accuracy, sample_size, confidence_ceiling, safety_margin,
    calculation_window_days, approved_by
)
SELECT
    fl.forecast_type,
    'ALL' as regime,
    0.0 as band_min,
    1.0 as band_max,
    ROUND(AVG(CASE WHEN fop.hit_rate_contribution THEN 1 ELSE 0 END)::numeric, 4) as historical_accuracy,
    COUNT(*) as sample_size,
    LEAST(0.95,
        ROUND(AVG(CASE WHEN fop.hit_rate_contribution THEN 1 ELSE 0 END)::numeric, 4) +
        CASE
            WHEN AVG(CASE WHEN fop.hit_rate_contribution THEN 1 ELSE 0 END) < 0.50 THEN 0.05
            WHEN AVG(CASE WHEN fop.hit_rate_contribution THEN 1 ELSE 0 END) < 0.60 THEN 0.02
            ELSE 0.00
        END
    ) as ceiling,
    CASE
        WHEN AVG(CASE WHEN fop.hit_rate_contribution THEN 1 ELSE 0 END) < 0.50 THEN 0.05
        WHEN AVG(CASE WHEN fop.hit_rate_contribution THEN 1 ELSE 0 END) < 0.60 THEN 0.02
        ELSE 0.00
    END as safety_margin,
    30 as window_days,
    'STIG'
FROM fhq_research.forecast_outcome_pairs fop
JOIN fhq_research.forecast_ledger fl ON fop.forecast_id = fl.forecast_id
WHERE fl.forecast_confidence IS NOT NULL
AND fop.reconciled_at >= NOW() - INTERVAL '30 days'
GROUP BY fl.forecast_type
HAVING COUNT(*) >= 100  -- Sample-size floor (Hardening #1)
ON CONFLICT DO NOTHING;

-- Log initial population
INSERT INTO fhq_governance.calibration_gate_history (
    gate_id, action, new_ceiling, change_reason, changed_by
)
SELECT
    gate_id,
    'CREATED',
    confidence_ceiling,
    'Initial population per CEO-DIR-2026-032',
    'STIG'
FROM fhq_governance.confidence_calibration_gates
WHERE created_at >= NOW() - INTERVAL '1 minute';

-- ============================================================================
-- 7. GOVERNANCE LOGGING
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale,
    metadata, agent_id, timestamp
) VALUES (
    gen_random_uuid(),
    'CALIBRATION_GATES_DEPLOYED',
    'CEO-DIR-2026-032',
    'DIRECTIVE',
    'STIG',
    NOW(),
    'EXECUTED',
    'Deployed calibration gates infrastructure to enforce confidence ceilings based on historical accuracy. Includes three hardening upgrades: (1) sample-size floor n>=100, (2) asymmetric safety margin, (3) regime precedence logic.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-032',
        'migration', '226_calibration_gates.sql',
        'hardening_upgrades', jsonb_build_array(
            'Sample-size floor (n >= 100)',
            'Asymmetric safety margin (+5%/<50%, +2%/50-60%, +0%/>60%)',
            'Regime precedence (exact > type+ALL > global)'
        ),
        'initial_gates_created', (SELECT COUNT(*) FROM fhq_governance.confidence_calibration_gates)
    ),
    'STIG',
    NOW()
);

-- ============================================================================
-- 8. VERIFICATION QUERIES (for manual verification after migration)
-- ============================================================================

-- VERIFY: Show active gates
-- SELECT * FROM fhq_governance.confidence_calibration_gates WHERE effective_until IS NULL;

-- VERIFY: Test ceiling lookup
-- SELECT * FROM fhq_governance.get_active_confidence_ceiling('PRICE_DIRECTION', 'ALL');

-- VERIFY: Test enforcement
-- SELECT * FROM fhq_governance.enforce_calibration_gate(
--     gen_random_uuid(), 0.85, 'PRICE_DIRECTION', 'ALL'
-- );
