-- Migration 227: Paper Trading Infrastructure
-- Authority: CEO-DIR-2026-033 "First Paper Capital Deployment Under Calibration Gates"
-- Executed by: STIG (CTO)
-- Date: 2026-01-10
--
-- PURPOSE: Enable paper trading with calibrated confidence, epistemic stop-loss,
-- and learning optimization features.
--
-- OPTIMIZATIONS INCLUDED:
-- 1. Min trade cadence enforcement (5-15 trades/day)
-- 2. Information-weighted risk sizing
-- 3. Epistemic stop-loss triggers
-- 4. Daily edge signal computation

-- ============================================================================
-- 1. PAPER LEDGER - Core Trade Log
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.paper_ledger (
    trade_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Decision context
    decision_plan_id UUID,
    decision_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Asset details
    asset_id TEXT NOT NULL,
    canonical_id TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT', 'CLOSE')),

    -- Sizing
    raw_position_size NUMERIC(12,4) NOT NULL,
    calibrated_position_size NUMERIC(12,4) NOT NULL,
    information_weight NUMERIC(5,4) DEFAULT 1.0,

    -- Confidence metrics
    raw_confidence NUMERIC(5,4) NOT NULL,
    calibrated_confidence NUMERIC(5,4) NOT NULL,
    calibration_gate_id UUID REFERENCES fhq_governance.confidence_calibration_gates(gate_id),
    confidence_reduction NUMERIC(5,4) GENERATED ALWAYS AS (raw_confidence - calibrated_confidence) STORED,

    -- Price data
    entry_price NUMERIC(18,8) NOT NULL,
    simulated_slippage NUMERIC(5,4) DEFAULT 0.0005,  -- 0.05% default
    effective_entry_price NUMERIC(18,8) GENERATED ALWAYS AS (
        CASE
            WHEN direction = 'LONG' THEN entry_price * (1 + simulated_slippage)
            WHEN direction = 'SHORT' THEN entry_price * (1 - simulated_slippage)
            ELSE entry_price
        END
    ) STORED,

    -- Exit data (populated when closed)
    exit_price NUMERIC(18,8),
    exit_timestamp TIMESTAMPTZ,
    effective_exit_price NUMERIC(18,8),

    -- PnL (calculated on exit)
    paper_pnl NUMERIC(18,8),
    paper_pnl_pct NUMERIC(8,4),

    -- Outcome tracking
    forecast_id UUID,
    outcome_correct BOOLEAN,

    -- Regime context
    regime_at_entry TEXT,
    regime_at_exit TEXT,

    -- Learning metadata
    novelty_score NUMERIC(5,4) DEFAULT 0.5,  -- How "new" is this signal type
    error_type TEXT,  -- TYPE_A, TYPE_B, TYPE_C, TYPE_D, TYPE_E, TYPE_X
    lesson_extracted BOOLEAN DEFAULT FALSE,

    -- Audit
    created_by TEXT DEFAULT 'LARS',
    executed_by TEXT DEFAULT 'LINE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_paper_ledger_date ON fhq_governance.paper_ledger (decision_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_paper_ledger_asset ON fhq_governance.paper_ledger (canonical_id);
CREATE INDEX IF NOT EXISTS idx_paper_ledger_gate ON fhq_governance.paper_ledger (calibration_gate_id);

-- ============================================================================
-- 2. DECISION PLAN TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.paper_decision_plan (
    plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Plan metadata
    plan_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    plan_type TEXT DEFAULT 'PAPER_ALPHA',

    -- Allocation model
    allocation_model TEXT DEFAULT 'RISK_PARITY_INFO_WEIGHTED',

    -- Thresholds (dynamic based on trade cadence)
    min_confidence_threshold NUMERIC(5,4) NOT NULL DEFAULT 0.25,
    effective_threshold NUMERIC(5,4),  -- May be lowered for cadence
    threshold_adjustment_reason TEXT,

    -- Leverage
    max_leverage NUMERIC(4,2) DEFAULT 1.0,

    -- Positions planned
    positions_planned INTEGER NOT NULL DEFAULT 0,
    positions_executed INTEGER DEFAULT 0,
    positions_blocked INTEGER DEFAULT 0,

    -- Risk metrics
    total_risk_units NUMERIC(10,4),
    max_single_position_pct NUMERIC(5,4) DEFAULT 0.10,

    -- Regime context
    dominant_regime TEXT,
    regime_confidence NUMERIC(5,4),

    -- Status
    status TEXT DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'EXECUTING', 'COMPLETED', 'SUSPENDED')),
    suspended_reason TEXT,

    -- Audit
    created_by TEXT DEFAULT 'LARS',
    approved_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 3. EPISTEMIC STOP-LOSS TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.epistemic_health_daily (
    health_date DATE PRIMARY KEY DEFAULT CURRENT_DATE,

    -- Hit rate metrics
    trades_today INTEGER DEFAULT 0,
    hits_today INTEGER DEFAULT 0,
    hit_rate_today NUMERIC(5,4),
    hit_rate_yesterday NUMERIC(5,4),
    hit_rate_2d_ago NUMERIC(5,4),
    hit_rate_3d_ago NUMERIC(5,4),

    -- Hit rate trend (consecutive decline days)
    hit_rate_decline_streak INTEGER DEFAULT 0,

    -- Brier score metrics
    brier_today NUMERIC(6,4),
    brier_yesterday NUMERIC(6,4),
    brier_2d_ago NUMERIC(6,4),
    brier_worsening_streak INTEGER DEFAULT 0,

    -- Error type tracking
    type_d_count INTEGER DEFAULT 0,  -- Regime Illusion
    type_e_count INTEGER DEFAULT 0,  -- Correlation Breakdown
    repeated_error_count INTEGER DEFAULT 0,

    -- Stop-loss status
    epistemic_stop_triggered BOOLEAN DEFAULT FALSE,
    stop_trigger_reason TEXT,
    stop_triggered_at TIMESTAMPTZ,

    -- Edge signal
    daily_edge_signal INTEGER CHECK (daily_edge_signal IN (-1, 0, 1)),
    edge_signal_components JSONB,

    -- Audit
    computed_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 4. TRADE CADENCE ENFORCEMENT
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.get_effective_confidence_threshold(
    p_base_threshold NUMERIC DEFAULT 0.30,
    p_min_daily_trades INTEGER DEFAULT 5
)
RETURNS TABLE (
    effective_threshold NUMERIC,
    adjustment_applied BOOLEAN,
    adjustment_reason TEXT,
    trades_today INTEGER
) AS $$
DECLARE
    v_trades_today INTEGER;
    v_threshold NUMERIC;
    v_adjustment_reason TEXT;
BEGIN
    -- Count trades today
    SELECT COUNT(*) INTO v_trades_today
    FROM fhq_governance.paper_ledger
    WHERE decision_timestamp::date = CURRENT_DATE;

    -- Adjust threshold if below minimum cadence
    IF v_trades_today < p_min_daily_trades THEN
        -- Reduce threshold by 5% for each missing trade (floor at 0.20)
        v_threshold := GREATEST(0.20, p_base_threshold - (0.05 * (p_min_daily_trades - v_trades_today)));
        v_adjustment_reason := format('Threshold lowered from %s to %s due to low cadence (%s/%s trades)',
                                       p_base_threshold, v_threshold, v_trades_today, p_min_daily_trades);

        RETURN QUERY SELECT v_threshold, TRUE, v_adjustment_reason, v_trades_today;
    ELSE
        RETURN QUERY SELECT p_base_threshold, FALSE, 'Cadence met'::TEXT, v_trades_today;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. INFORMATION-WEIGHTED POSITION SIZING
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.calculate_info_weighted_size(
    p_base_size NUMERIC,
    p_calibrated_confidence NUMERIC,
    p_novelty_score NUMERIC DEFAULT 0.5,
    p_max_position_pct NUMERIC DEFAULT 0.10
)
RETURNS TABLE (
    weighted_size NUMERIC,
    confidence_factor NUMERIC,
    novelty_factor NUMERIC,
    info_gain_estimate NUMERIC
) AS $$
DECLARE
    v_conf_factor NUMERIC;
    v_novelty_factor NUMERIC;
    v_info_gain NUMERIC;
    v_weighted_size NUMERIC;
BEGIN
    -- Confidence factor: higher confidence = larger position (linear)
    v_conf_factor := p_calibrated_confidence;

    -- Novelty factor: higher novelty = we want to learn more = slightly larger position
    -- But capped to avoid overexposure to unknown situations
    v_novelty_factor := LEAST(1.2, 0.8 + (p_novelty_score * 0.4));

    -- Information gain estimate: combination of confidence and novelty
    v_info_gain := v_conf_factor * v_novelty_factor;

    -- Calculate weighted size (capped at max position %)
    v_weighted_size := LEAST(
        p_base_size * v_conf_factor * v_novelty_factor,
        p_max_position_pct
    );

    RETURN QUERY SELECT v_weighted_size, v_conf_factor, v_novelty_factor, v_info_gain;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. DAILY EDGE SIGNAL COMPUTATION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.compute_daily_edge_signal()
RETURNS TABLE (
    edge_signal INTEGER,
    hit_rate_delta NUMERIC,
    brier_delta NUMERIC,
    error_diversity NUMERIC,
    components JSONB
) AS $$
DECLARE
    v_hit_today NUMERIC;
    v_hit_yesterday NUMERIC;
    v_brier_today NUMERIC;
    v_brier_yesterday NUMERIC;
    v_error_diversity NUMERIC;
    v_signal INTEGER;
    v_components JSONB;
BEGIN
    -- Get today's metrics
    SELECT
        COALESCE(hit_rate_today, 0),
        COALESCE(hit_rate_yesterday, 0),
        COALESCE(brier_today, 0.5),
        COALESCE(brier_yesterday, 0.5)
    INTO v_hit_today, v_hit_yesterday, v_brier_today, v_brier_yesterday
    FROM fhq_governance.epistemic_health_daily
    WHERE health_date = CURRENT_DATE;

    -- Calculate error diversity (lower is better - means we're making different errors)
    SELECT COUNT(DISTINCT error_type)::numeric / NULLIF(COUNT(*)::numeric, 0)
    INTO v_error_diversity
    FROM fhq_governance.paper_ledger
    WHERE decision_timestamp >= NOW() - INTERVAL '7 days'
    AND outcome_correct = FALSE;

    v_error_diversity := COALESCE(v_error_diversity, 1.0);

    -- Compute edge signal: +1 (improving), 0 (stable), -1 (degrading)
    v_signal := CASE
        -- Improving: hit rate up OR brier down significantly
        WHEN (v_hit_today > v_hit_yesterday + 0.02) OR (v_brier_today < v_brier_yesterday - 0.01) THEN 1
        -- Degrading: hit rate down AND brier up
        WHEN (v_hit_today < v_hit_yesterday - 0.02) AND (v_brier_today > v_brier_yesterday + 0.01) THEN -1
        -- Stable
        ELSE 0
    END;

    v_components := jsonb_build_object(
        'hit_rate_today', v_hit_today,
        'hit_rate_yesterday', v_hit_yesterday,
        'hit_rate_delta', v_hit_today - v_hit_yesterday,
        'brier_today', v_brier_today,
        'brier_yesterday', v_brier_yesterday,
        'brier_delta', v_brier_today - v_brier_yesterday,
        'error_diversity', v_error_diversity
    );

    -- Update daily health table
    UPDATE fhq_governance.epistemic_health_daily
    SET daily_edge_signal = v_signal,
        edge_signal_components = v_components,
        computed_at = NOW()
    WHERE health_date = CURRENT_DATE;

    RETURN QUERY SELECT
        v_signal,
        v_hit_today - v_hit_yesterday,
        v_brier_today - v_brier_yesterday,
        v_error_diversity,
        v_components;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. EPISTEMIC STOP-LOSS CHECKER
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.check_epistemic_stop_loss()
RETURNS TABLE (
    should_stop BOOLEAN,
    reason TEXT,
    hit_rate_streak INTEGER,
    brier_streak INTEGER,
    repeated_errors INTEGER
) AS $$
DECLARE
    v_hit_streak INTEGER;
    v_brier_streak INTEGER;
    v_type_d_repeats INTEGER;
    v_type_e_repeats INTEGER;
    v_should_stop BOOLEAN := FALSE;
    v_reason TEXT;
BEGIN
    -- Get current streaks
    SELECT
        COALESCE(hit_rate_decline_streak, 0),
        COALESCE(brier_worsening_streak, 0),
        COALESCE(type_d_count, 0),
        COALESCE(type_e_count, 0)
    INTO v_hit_streak, v_brier_streak, v_type_d_repeats, v_type_e_repeats
    FROM fhq_governance.epistemic_health_daily
    WHERE health_date = CURRENT_DATE;

    -- Check stop conditions
    IF v_hit_streak >= 3 THEN
        v_should_stop := TRUE;
        v_reason := format('Hit rate declined for %s consecutive days', v_hit_streak);
    ELSIF v_brier_streak >= 3 THEN
        v_should_stop := TRUE;
        v_reason := format('Brier score worsened for %s consecutive days', v_brier_streak);
    ELSIF v_type_d_repeats >= 3 THEN
        v_should_stop := TRUE;
        v_reason := format('TYPE_D (Regime Illusion) repeated %s times today', v_type_d_repeats);
    ELSIF v_type_e_repeats >= 3 THEN
        v_should_stop := TRUE;
        v_reason := format('TYPE_E (Correlation Breakdown) repeated %s times today', v_type_e_repeats);
    END IF;

    -- If stop triggered, log it
    IF v_should_stop THEN
        UPDATE fhq_governance.epistemic_health_daily
        SET epistemic_stop_triggered = TRUE,
            stop_trigger_reason = v_reason,
            stop_triggered_at = NOW()
        WHERE health_date = CURRENT_DATE;

        -- Also update any pending decision plans
        UPDATE fhq_governance.paper_decision_plan
        SET status = 'SUSPENDED',
            suspended_reason = v_reason
        WHERE status = 'PENDING' OR status = 'EXECUTING';
    END IF;

    RETURN QUERY SELECT
        v_should_stop,
        COALESCE(v_reason, 'No stop condition met'),
        v_hit_streak,
        v_brier_streak,
        v_type_d_repeats + v_type_e_repeats;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. PAPER TRADE EXECUTION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.execute_paper_trade(
    p_asset_id TEXT,
    p_canonical_id TEXT,
    p_direction TEXT,
    p_raw_confidence NUMERIC,
    p_entry_price NUMERIC,
    p_base_size NUMERIC,
    p_forecast_id UUID DEFAULT NULL,
    p_regime TEXT DEFAULT 'NEUTRAL',
    p_novelty_score NUMERIC DEFAULT 0.5
)
RETURNS TABLE (
    trade_id UUID,
    executed BOOLEAN,
    blocked_reason TEXT,
    calibrated_confidence NUMERIC,
    effective_size NUMERIC,
    gate_id UUID
) AS $$
DECLARE
    v_trade_id UUID;
    v_calibrated_conf NUMERIC;
    v_gate_id UUID;
    v_match_type TEXT;
    v_threshold_rec RECORD;
    v_size_rec RECORD;
    v_stop_rec RECORD;
BEGIN
    -- Check epistemic stop-loss first
    SELECT * INTO v_stop_rec FROM fhq_governance.check_epistemic_stop_loss();
    IF v_stop_rec.should_stop THEN
        RETURN QUERY SELECT
            NULL::UUID, FALSE, v_stop_rec.reason,
            NULL::NUMERIC, NULL::NUMERIC, NULL::UUID;
        RETURN;
    END IF;

    -- Get calibrated confidence
    SELECT ceiling, g.gate_id, g.match_type
    INTO v_calibrated_conf, v_gate_id, v_match_type
    FROM fhq_governance.get_active_confidence_ceiling(
        CASE WHEN p_canonical_id LIKE '%REGIME%' THEN 'REGIME' ELSE 'PRICE_DIRECTION' END,
        p_regime
    ) g;

    v_calibrated_conf := LEAST(p_raw_confidence, v_calibrated_conf);

    -- Get effective threshold (may be lowered for cadence)
    SELECT * INTO v_threshold_rec
    FROM fhq_governance.get_effective_confidence_threshold(0.25, 5);

    -- Check if above threshold
    IF v_calibrated_conf < v_threshold_rec.effective_threshold THEN
        RETURN QUERY SELECT
            NULL::UUID, FALSE,
            format('Calibrated confidence %s below threshold %s',
                   v_calibrated_conf, v_threshold_rec.effective_threshold),
            v_calibrated_conf, NULL::NUMERIC, v_gate_id;
        RETURN;
    END IF;

    -- Calculate info-weighted size
    SELECT * INTO v_size_rec
    FROM fhq_governance.calculate_info_weighted_size(
        p_base_size, v_calibrated_conf, p_novelty_score
    );

    -- Execute paper trade
    v_trade_id := gen_random_uuid();

    INSERT INTO fhq_governance.paper_ledger (
        trade_id, asset_id, canonical_id, direction,
        raw_position_size, calibrated_position_size, information_weight,
        raw_confidence, calibrated_confidence, calibration_gate_id,
        entry_price, forecast_id, regime_at_entry, novelty_score
    ) VALUES (
        v_trade_id, p_asset_id, p_canonical_id, p_direction,
        p_base_size, v_size_rec.weighted_size, v_size_rec.info_gain_estimate,
        p_raw_confidence, v_calibrated_conf, v_gate_id,
        p_entry_price, p_forecast_id, p_regime, p_novelty_score
    );

    RETURN QUERY SELECT
        v_trade_id, TRUE, NULL::TEXT,
        v_calibrated_conf, v_size_rec.weighted_size, v_gate_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 9. INITIALIZE TODAY'S HEALTH TRACKING
-- ============================================================================

INSERT INTO fhq_governance.epistemic_health_daily (health_date)
VALUES (CURRENT_DATE)
ON CONFLICT (health_date) DO NOTHING;

-- ============================================================================
-- 10. GOVERNANCE LOGGING
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale,
    metadata, agent_id, timestamp
) VALUES (
    gen_random_uuid(),
    'PAPER_TRADING_INFRASTRUCTURE_DEPLOYED',
    'CEO-DIR-2026-033',
    'DIRECTIVE',
    'STIG',
    NOW(),
    'EXECUTED',
    'Deployed paper trading infrastructure with calibration gate integration, epistemic stop-loss, information-weighted sizing, and daily edge signal computation.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-033',
        'migration', '227_paper_trading_infrastructure.sql',
        'features', jsonb_build_array(
            'paper_ledger with calibration gate linkage',
            'decision_plan tracking',
            'min trade cadence enforcement (5/day)',
            'information-weighted position sizing',
            'epistemic stop-loss (3-day streak triggers)',
            'daily edge signal (+1/0/-1)'
        ),
        'thresholds', jsonb_build_object(
            'base_confidence', 0.25,
            'min_daily_trades', 5,
            'simulated_slippage', 0.0005
        )
    ),
    'STIG',
    NOW()
);

-- ============================================================================
-- VERIFICATION QUERIES (for manual testing)
-- ============================================================================

-- VERIFY: Test trade execution
-- SELECT * FROM fhq_governance.execute_paper_trade(
--     'asset-001', 'AAPL', 'LONG', 0.85, 150.00, 0.05, NULL, 'BULL', 0.7
-- );

-- VERIFY: Check effective threshold
-- SELECT * FROM fhq_governance.get_effective_confidence_threshold(0.25, 5);

-- VERIFY: Compute edge signal
-- SELECT * FROM fhq_governance.compute_daily_edge_signal();

-- VERIFY: Check epistemic stop-loss
-- SELECT * FROM fhq_governance.check_epistemic_stop_loss();
