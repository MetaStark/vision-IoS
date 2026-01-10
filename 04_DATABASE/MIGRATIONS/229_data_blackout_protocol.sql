-- Migration 229: DATA_BLACKOUT Protocol
-- Authority: CEO-DIR-2026-035 - Systemic Blackout Response & Epistemic Protection Protocol
-- Classification: CLASS A GOVERNANCE EVENT
-- Author: STIG (CTO)
-- Date: 2026-01-10

-- ============================================================================
-- FORMAL VIOLATIONS ADDRESSED:
-- 1. ADR-012 Violation: Operating paper trading on stale data
-- 2. ADR-013 Violation: One-True-Source freshness invariant not enforced
-- 3. Process Failure: execute_paper_trade() allowed epistemic poisoning
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. DATA BLACKOUT STATE TABLE (separate from DEFCON system_state)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.data_blackout_state (
    blackout_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    is_active BOOLEAN NOT NULL DEFAULT false,
    trigger_reason TEXT,
    triggered_by TEXT NOT NULL,
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    cleared_by TEXT,
    cleared_at TIMESTAMPTZ,
    vega_attestation_id TEXT,
    stale_assets TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert initial DATA_BLACKOUT state (currently ACTIVE based on staleness detected)
INSERT INTO fhq_governance.data_blackout_state (
    is_active,
    trigger_reason,
    triggered_by,
    stale_assets
) VALUES (
    true,
    'CEO-DIR-2026-035: Systemic staleness detected. SPY/GLD prices >24h old.',
    'STIG',
    ARRAY['SPY', 'GLD', 'MSFT', 'TSLA', 'AAPL']
);

-- ============================================================================
-- 2. FRESHNESS THRESHOLDS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.freshness_thresholds (
    threshold_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_class TEXT NOT NULL,
    gate_type TEXT NOT NULL,
    max_staleness_minutes INTEGER NOT NULL,
    description TEXT,
    effective_from TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'STIG',
    CONSTRAINT valid_asset_class CHECK (asset_class IN ('EQUITY', 'CRYPTO', 'COMMODITY', 'FX', 'BOND')),
    CONSTRAINT valid_gate_type CHECK (gate_type IN ('EXECUTION', 'LEARNING')),
    UNIQUE (asset_class, gate_type)
);

-- Insert CEO-mandated thresholds
INSERT INTO fhq_governance.freshness_thresholds (asset_class, gate_type, max_staleness_minutes, description) VALUES
    ('EQUITY', 'EXECUTION', 240, 'CEO-DIR-2026-035: 4h max staleness for equity trade placement'),
    ('EQUITY', 'LEARNING', 60, 'CEO-DIR-2026-035: 60m max staleness for equity model updates'),
    ('CRYPTO', 'EXECUTION', 15, 'CEO-DIR-2026-035: 15m max staleness for crypto trade placement'),
    ('CRYPTO', 'LEARNING', 15, 'CEO-DIR-2026-035: 15m max staleness for crypto model updates'),
    ('COMMODITY', 'EXECUTION', 240, 'Inherit from equity'),
    ('COMMODITY', 'LEARNING', 60, 'Inherit from equity'),
    ('FX', 'EXECUTION', 60, 'FX requires fresher data'),
    ('FX', 'LEARNING', 30, 'FX learning threshold'),
    ('BOND', 'EXECUTION', 240, 'Inherit from equity'),
    ('BOND', 'LEARNING', 60, 'Inherit from equity')
ON CONFLICT (asset_class, gate_type) DO NOTHING;

-- ============================================================================
-- 3. FRESHNESS CHECK FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.check_price_freshness(
    p_canonical_id TEXT,
    p_gate_type TEXT DEFAULT 'EXECUTION'
)
RETURNS TABLE (
    is_fresh BOOLEAN,
    staleness_minutes INTEGER,
    max_allowed_minutes INTEGER,
    asset_class TEXT,
    last_price_time TIMESTAMPTZ,
    learning_weight NUMERIC
) AS $$
DECLARE
    v_asset_class TEXT;
    v_last_price_time TIMESTAMPTZ;
    v_staleness_minutes INTEGER;
    v_max_allowed INTEGER;
BEGIN
    -- Determine asset class from canonical_id
    v_asset_class := CASE
        WHEN p_canonical_id LIKE '%-USD' THEN 'CRYPTO'
        WHEN p_canonical_id IN ('GLD', 'SLV', 'USO', 'UNG') THEN 'COMMODITY'
        WHEN p_canonical_id IN ('TLT', 'IEF', 'SHY', 'BND', 'AGG') THEN 'BOND'
        WHEN p_canonical_id LIKE '%=X' OR p_canonical_id LIKE 'USD%' THEN 'FX'
        ELSE 'EQUITY'
    END;

    -- Get latest price timestamp
    SELECT MAX(timestamp) INTO v_last_price_time
    FROM fhq_market.prices
    WHERE canonical_id = p_canonical_id;

    -- Calculate staleness in minutes
    IF v_last_price_time IS NULL THEN
        v_staleness_minutes := 999999;  -- No data = extremely stale
    ELSE
        v_staleness_minutes := EXTRACT(EPOCH FROM (NOW() - v_last_price_time)) / 60;
    END IF;

    -- Get threshold for this asset class and gate type
    SELECT ft.max_staleness_minutes INTO v_max_allowed
    FROM fhq_governance.freshness_thresholds ft
    WHERE ft.asset_class = v_asset_class
    AND ft.gate_type = p_gate_type;

    -- Default if not found
    v_max_allowed := COALESCE(v_max_allowed, 240);

    RETURN QUERY SELECT
        v_staleness_minutes <= v_max_allowed,
        v_staleness_minutes,
        v_max_allowed,
        v_asset_class,
        v_last_price_time,
        CASE
            WHEN v_staleness_minutes <= v_max_allowed THEN 1.0
            ELSE 0.0  -- learning_weight = 0 if stale
        END;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 4. DATA BLACKOUT CHECK FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.is_data_blackout_active()
RETURNS TABLE (
    is_active BOOLEAN,
    trigger_reason TEXT,
    triggered_at TIMESTAMPTZ,
    stale_assets TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dbs.is_active,
        dbs.trigger_reason,
        dbs.triggered_at,
        dbs.stale_assets
    FROM fhq_governance.data_blackout_state dbs
    ORDER BY dbs.created_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. TRIGGER DATA BLACKOUT FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.trigger_data_blackout(
    p_reason TEXT,
    p_triggered_by TEXT,
    p_stale_assets TEXT[]
)
RETURNS UUID AS $$
DECLARE
    v_blackout_id UUID;
BEGIN
    -- Deactivate any existing blackout first
    UPDATE fhq_governance.data_blackout_state
    SET is_active = false, updated_at = NOW()
    WHERE is_active = true;

    -- Create new blackout
    INSERT INTO fhq_governance.data_blackout_state (
        is_active,
        trigger_reason,
        triggered_by,
        stale_assets
    ) VALUES (
        true,
        p_reason,
        p_triggered_by,
        p_stale_assets
    )
    RETURNING blackout_id INTO v_blackout_id;

    RETURN v_blackout_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. CLEAR DATA BLACKOUT FUNCTION (VEGA ONLY)
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.clear_data_blackout(
    p_cleared_by TEXT,
    p_vega_attestation_id TEXT
)
RETURNS TABLE (
    success BOOLEAN,
    message TEXT
) AS $$
DECLARE
    v_stale_count INTEGER;
BEGIN
    -- Only VEGA can clear DATA_BLACKOUT per CEO-DIR-2026-035
    IF p_cleared_by != 'VEGA' THEN
        RETURN QUERY SELECT
            false,
            'Only VEGA can clear DATA_BLACKOUT state per CEO-DIR-2026-035'::TEXT;
        RETURN;
    END IF;

    -- Verify all primary assets are fresh before clearing
    SELECT COUNT(*) INTO v_stale_count
    FROM (
        SELECT canonical_id
        FROM unnest(ARRAY['SPY', 'GLD', 'BTC-USD', 'ETH-USD', 'SOL-USD']) as canonical_id
        WHERE NOT (SELECT cpf.is_fresh FROM fhq_governance.check_price_freshness(canonical_id, 'EXECUTION') cpf)
    ) stale;

    IF v_stale_count > 0 THEN
        RETURN QUERY SELECT
            false,
            format('Cannot clear blackout: %s primary assets still have stale data', v_stale_count)::TEXT;
        RETURN;
    END IF;

    -- Clear the blackout
    UPDATE fhq_governance.data_blackout_state
    SET
        is_active = false,
        cleared_by = p_cleared_by,
        cleared_at = NOW(),
        vega_attestation_id = p_vega_attestation_id,
        updated_at = NOW()
    WHERE is_active = true;

    RETURN QUERY SELECT
        true,
        'DATA_BLACKOUT cleared. System returning to OPERATIONAL.'::TEXT;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. UPDATE execute_paper_trade() WITH FRESHNESS GATES
-- ============================================================================

-- First drop the existing function
DROP FUNCTION IF EXISTS fhq_governance.execute_paper_trade(TEXT, TEXT, TEXT, NUMERIC, NUMERIC, NUMERIC, UUID, TEXT);

-- Recreate with freshness gates
CREATE OR REPLACE FUNCTION fhq_governance.execute_paper_trade(
    p_asset_id TEXT,
    p_canonical_id TEXT,
    p_direction TEXT,
    p_raw_confidence NUMERIC,
    p_entry_price NUMERIC,
    p_base_size NUMERIC,
    p_forecast_id UUID DEFAULT NULL,
    p_regime TEXT DEFAULT 'NEUTRAL'
)
RETURNS TABLE (
    trade_id UUID,
    executed BOOLEAN,
    blocked_reason TEXT,
    calibrated_confidence NUMERIC,
    effective_size NUMERIC,
    gate_id UUID,
    novelty_score NUMERIC,
    effective_slippage NUMERIC
) AS $$
DECLARE
    v_trade_id UUID;
    v_ceiling NUMERIC;
    v_gate_id UUID;
    v_calibrated_conf NUMERIC;
    v_novelty NUMERIC;
    v_info_weight NUMERIC;
    v_effective_size NUMERIC;
    v_slippage NUMERIC;
    v_slippage_rule TEXT;
    v_effective_entry NUMERIC;
    v_freshness_check RECORD;
    v_blackout_check RECORD;
    v_threshold_result RECORD;
BEGIN
    -- ========================================================================
    -- CEO-DIR-2026-035: DATA_BLACKOUT CHECK
    -- ========================================================================
    SELECT * INTO v_blackout_check
    FROM fhq_governance.is_data_blackout_active();

    IF v_blackout_check.is_active THEN
        RETURN QUERY SELECT
            NULL::UUID,
            false,
            'BLOCKED: DATA_BLACKOUT active. ' || COALESCE(v_blackout_check.trigger_reason, 'System in blackout mode'),
            NULL::NUMERIC,
            NULL::NUMERIC,
            NULL::UUID,
            NULL::NUMERIC,
            NULL::NUMERIC;
        RETURN;
    END IF;

    -- ========================================================================
    -- CEO-DIR-2026-035: EXECUTION FRESHNESS GATE
    -- ========================================================================
    SELECT * INTO v_freshness_check
    FROM fhq_governance.check_price_freshness(p_canonical_id, 'EXECUTION');

    IF NOT v_freshness_check.is_fresh THEN
        RETURN QUERY SELECT
            NULL::UUID,
            false,
            format('BLOCKED: Price data stale. %s minutes old, max allowed %s minutes for %s.',
                   v_freshness_check.staleness_minutes,
                   v_freshness_check.max_allowed_minutes,
                   v_freshness_check.asset_class),
            NULL::NUMERIC,
            NULL::NUMERIC,
            NULL::UUID,
            NULL::NUMERIC,
            NULL::NUMERIC;
        RETURN;
    END IF;

    -- ========================================================================
    -- EXISTING LOGIC: Calibration gate
    -- ========================================================================
    SELECT ccg.gate_id, ccg.confidence_ceiling
    INTO v_gate_id, v_ceiling
    FROM fhq_governance.confidence_calibration_gates ccg
    WHERE ccg.forecast_type = 'PRICE_DIRECTION'
    AND (ccg.regime = p_regime OR ccg.regime = 'ALL')
    AND (ccg.effective_until IS NULL OR ccg.effective_until > NOW())
    ORDER BY
        CASE WHEN ccg.regime = p_regime THEN 0 ELSE 1 END,
        ccg.effective_from DESC
    LIMIT 1;

    v_ceiling := COALESCE(v_ceiling, 0.50);
    v_calibrated_conf := LEAST(p_raw_confidence, v_ceiling);

    -- Get effective threshold (with cadence floor)
    SELECT * INTO v_threshold_result
    FROM fhq_governance.get_effective_confidence_threshold(0.25, 5);

    IF v_calibrated_conf < v_threshold_result.effective_threshold THEN
        RETURN QUERY SELECT
            NULL::UUID,
            false,
            format('BLOCKED: Calibrated confidence %.4f below threshold %.4f',
                   v_calibrated_conf, v_threshold_result.effective_threshold),
            v_calibrated_conf,
            NULL::NUMERIC,
            v_gate_id,
            NULL::NUMERIC,
            NULL::NUMERIC;
        RETURN;
    END IF;

    -- Calculate novelty score
    SELECT ns.novelty_score INTO v_novelty
    FROM fhq_governance.calculate_novelty_score(p_canonical_id, p_direction, p_regime) ns;

    v_novelty := COALESCE(v_novelty, 0.5);

    -- Calculate info-weighted size
    v_info_weight := v_calibrated_conf * (0.8 + 0.4 * v_novelty);
    v_effective_size := p_base_size * v_info_weight;
    v_effective_size := LEAST(v_effective_size, 0.10);

    -- Calculate dynamic slippage
    SELECT ds.effective_slippage, ds.rule_applied
    INTO v_slippage, v_slippage_rule
    FROM fhq_governance.calculate_dynamic_slippage(p_canonical_id, 0.0005) ds;

    v_slippage := COALESCE(v_slippage, 0.0005);

    -- Calculate effective entry price with slippage
    IF p_direction = 'LONG' THEN
        v_effective_entry := p_entry_price * (1 + v_slippage);
    ELSE
        v_effective_entry := p_entry_price * (1 - v_slippage);
    END IF;

    -- Generate trade ID
    v_trade_id := gen_random_uuid();

    -- Insert paper trade
    INSERT INTO fhq_governance.paper_ledger (
        trade_id,
        decision_timestamp,
        asset_id,
        canonical_id,
        direction,
        raw_position_size,
        calibrated_position_size,
        information_weight,
        raw_confidence,
        calibrated_confidence,
        calibration_gate_id,
        confidence_reduction,
        entry_price,
        simulated_slippage,
        effective_entry_price,
        forecast_id,
        regime_at_entry,
        novelty_score,
        slippage_rule_applied,
        created_by,
        executed_by
    ) VALUES (
        v_trade_id,
        NOW(),
        p_asset_id,
        p_canonical_id,
        p_direction,
        p_base_size,
        v_effective_size,
        v_info_weight,
        p_raw_confidence,
        v_calibrated_conf,
        v_gate_id,
        p_raw_confidence - v_calibrated_conf,
        p_entry_price,
        v_slippage,
        v_effective_entry,
        p_forecast_id,
        p_regime,
        v_novelty,
        v_slippage_rule,
        'LARS',
        'LINE'
    );

    -- Log novelty components
    INSERT INTO fhq_governance.novelty_score_components (
        trade_id,
        regime_shift_score,
        regime_shift_reason,
        asset_novelty_score,
        asset_novelty_reason,
        signal_disagreement_score,
        signal_disagreement_reason,
        total_novelty_score
    )
    SELECT
        v_trade_id,
        ns.regime_shift_component,
        'Regime: ' || p_regime,
        ns.asset_novelty_component,
        'Asset: ' || p_canonical_id,
        ns.signal_disagreement_component,
        'Direction: ' || p_direction,
        ns.novelty_score
    FROM fhq_governance.calculate_novelty_score(p_canonical_id, p_direction, p_regime) ns;

    RETURN QUERY SELECT
        v_trade_id,
        true,
        NULL::TEXT,
        v_calibrated_conf,
        v_effective_size,
        v_gate_id,
        v_novelty,
        v_slippage;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. BLACKOUT LOG TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.blackout_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    canonical_id TEXT,
    staleness_minutes INTEGER,
    threshold_minutes INTEGER,
    blocked_action TEXT,
    logged_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_event_type CHECK (event_type IN ('BLACKOUT_TRIGGERED', 'TRADE_BLOCKED', 'LEARNING_BLOCKED', 'BLACKOUT_CLEARED'))
);

-- ============================================================================
-- 9. VERIFICATION
-- ============================================================================

-- Verify blackout state
DO $$
DECLARE
    v_active BOOLEAN;
BEGIN
    SELECT is_active INTO v_active
    FROM fhq_governance.data_blackout_state
    ORDER BY created_at DESC
    LIMIT 1;

    RAISE NOTICE 'DATA_BLACKOUT active: %', COALESCE(v_active, false);
END $$;

-- Verify freshness thresholds
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM fhq_governance.freshness_thresholds;

    RAISE NOTICE 'Freshness thresholds configured: %', v_count;
END $$;

-- Test freshness check on primary assets
DO $$
DECLARE
    r RECORD;
BEGIN
    RAISE NOTICE '--- PRIMARY ASSET FRESHNESS CHECK ---';
    FOR r IN
        SELECT
            u.canonical_id,
            cpf.*
        FROM unnest(ARRAY['SPY', 'GLD', 'BTC-USD', 'SOL-USD']) as u(canonical_id)
        CROSS JOIN LATERAL fhq_governance.check_price_freshness(u.canonical_id, 'EXECUTION') cpf
    LOOP
        RAISE NOTICE '%: fresh=%, staleness=%min, max=%min',
            r.canonical_id, r.is_fresh, r.staleness_minutes, r.max_allowed_minutes;
    END LOOP;
END $$;

-- Test that execute_paper_trade is blocked during blackout
DO $$
DECLARE
    r RECORD;
BEGIN
    SELECT * INTO r
    FROM fhq_governance.execute_paper_trade(
        'test-asset',
        'SPY',
        'LONG',
        0.50,
        595.00,
        0.05
    );

    RAISE NOTICE 'Trade execution test: executed=%, blocked_reason=%',
        r.executed, COALESCE(r.blocked_reason, 'none');
END $$;

COMMIT;

-- ============================================================================
-- MIGRATION COMPLETE
-- CEO-DIR-2026-035: DATA_BLACKOUT Protocol Implemented
-- ============================================================================
