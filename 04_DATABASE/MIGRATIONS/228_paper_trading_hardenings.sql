-- Migration 228: Paper Trading Hardenings (Board-Proof)
-- Authority: CEO-DIR-2026-033 G0 Approved with Conditions
-- Executed by: STIG (CTO)
-- Date: 2026-01-10
--
-- PURPOSE: Implement 5 CEO-mandated hardenings to make paper trading
-- "board-proof" - preventing self-deception while maximizing learning.
--
-- HARDENINGS:
-- 1. Cadence floor + timelock (22% minimum, VEGA exception required)
-- 2. Deterministic novelty_score (no gaming possible)
-- 3. Two-tier epistemic stop-loss (SOFT_HALT / HARD_HALT)
-- 4. Dynamic slippage (volatility/liquidity adjusted)
-- 5. Daily Edge Signal cause codes (audit-verifiable)

-- ============================================================================
-- HARDENING 1: CADENCE FLOOR + TIMELOCK
-- ============================================================================

-- Add cadence exception tracking table
CREATE TABLE IF NOT EXISTS fhq_governance.cadence_exception_log (
    exception_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exception_date DATE NOT NULL,
    original_threshold NUMERIC(5,4) NOT NULL,
    requested_threshold NUMERIC(5,4) NOT NULL,
    approved_threshold NUMERIC(5,4),
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    approved_by TEXT,  -- Must be VEGA
    approved_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,  -- Same day midnight
    status TEXT DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Replace the threshold function with hardened version
CREATE OR REPLACE FUNCTION fhq_governance.get_effective_confidence_threshold(
    p_base_threshold NUMERIC DEFAULT 0.25,
    p_min_daily_trades INTEGER DEFAULT 5
)
RETURNS TABLE (
    effective_threshold NUMERIC,
    adjustment_applied BOOLEAN,
    adjustment_reason TEXT,
    trades_today INTEGER,
    vega_exception_active BOOLEAN
) AS $$
DECLARE
    v_trades_today INTEGER;
    v_threshold NUMERIC;
    v_adjustment_reason TEXT;
    v_exception_threshold NUMERIC;
    v_exception_active BOOLEAN := FALSE;
    v_hard_floor NUMERIC := 0.22;  -- HARDENING 1: Hard floor
BEGIN
    -- Count trades today
    SELECT COUNT(*) INTO v_trades_today
    FROM fhq_governance.paper_ledger
    WHERE decision_timestamp::date = CURRENT_DATE;

    -- Check for active VEGA-approved exception
    SELECT approved_threshold INTO v_exception_threshold
    FROM fhq_governance.cadence_exception_log
    WHERE exception_date = CURRENT_DATE
    AND status = 'APPROVED'
    AND expires_at > NOW()
    LIMIT 1;

    IF v_exception_threshold IS NOT NULL THEN
        v_exception_active := TRUE;
        v_hard_floor := v_exception_threshold;  -- VEGA can lower floor
    END IF;

    -- Adjust threshold if below minimum cadence
    IF v_trades_today < p_min_daily_trades THEN
        -- Calculate proposed reduction
        v_threshold := p_base_threshold - (0.01 * (p_min_daily_trades - v_trades_today));

        -- HARDENING 1: Enforce hard floor (22% unless VEGA exception)
        IF v_threshold < v_hard_floor THEN
            v_threshold := v_hard_floor;
            v_adjustment_reason := format(
                'Threshold lowered to floor %s (VEGA exception: %s). Cadence: %s/%s trades',
                v_hard_floor, v_exception_active, v_trades_today, p_min_daily_trades
            );
        ELSE
            v_adjustment_reason := format(
                'Threshold lowered from %s to %s due to cadence (%s/%s trades)',
                p_base_threshold, v_threshold, v_trades_today, p_min_daily_trades
            );
        END IF;

        RETURN QUERY SELECT v_threshold, TRUE, v_adjustment_reason, v_trades_today, v_exception_active;
    ELSE
        RETURN QUERY SELECT p_base_threshold, FALSE, 'Cadence met'::TEXT, v_trades_today, v_exception_active;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- HARDENING 2: DETERMINISTIC NOVELTY SCORE
-- ============================================================================

-- Add novelty score components table for audit trail
CREATE TABLE IF NOT EXISTS fhq_governance.novelty_score_components (
    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id UUID REFERENCES fhq_governance.paper_ledger(trade_id),

    -- Component 1: Regime shift (0-0.4)
    regime_shift_score NUMERIC(5,4) NOT NULL DEFAULT 0,
    regime_shift_reason TEXT,

    -- Component 2: Asset novelty (0-0.3)
    asset_novelty_score NUMERIC(5,4) NOT NULL DEFAULT 0,
    asset_novelty_reason TEXT,

    -- Component 3: Signal disagreement (0-0.3)
    signal_disagreement_score NUMERIC(5,4) NOT NULL DEFAULT 0,
    signal_disagreement_reason TEXT,

    -- Composite score
    total_novelty_score NUMERIC(5,4) GENERATED ALWAYS AS (
        regime_shift_score + asset_novelty_score + signal_disagreement_score
    ) STORED,

    computed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Function to calculate deterministic novelty score
CREATE OR REPLACE FUNCTION fhq_governance.calculate_novelty_score(
    p_canonical_id TEXT,
    p_direction TEXT,
    p_current_regime TEXT,
    p_trade_id UUID DEFAULT NULL
)
RETURNS TABLE (
    novelty_score NUMERIC,
    regime_shift_component NUMERIC,
    asset_novelty_component NUMERIC,
    signal_disagreement_component NUMERIC,
    explanation JSONB
) AS $$
DECLARE
    v_regime_score NUMERIC := 0;
    v_regime_reason TEXT;
    v_asset_score NUMERIC := 0;
    v_asset_reason TEXT;
    v_signal_score NUMERIC := 0;
    v_signal_reason TEXT;
    v_last_regime TEXT;
    v_asset_trade_count INTEGER;
    v_recent_same_direction INTEGER;
    v_recent_opposite_direction INTEGER;
    v_explanation JSONB;
BEGIN
    -- COMPONENT 1: Regime Shift (0-0.4)
    -- Check if regime changed since last belief state
    SELECT dominant_regime INTO v_last_regime
    FROM fhq_perception.model_belief_state
    WHERE created_at < NOW()
    ORDER BY created_at DESC
    OFFSET 1 LIMIT 1;

    IF v_last_regime IS NOT NULL AND v_last_regime != p_current_regime THEN
        v_regime_score := 0.4;
        v_regime_reason := format('Regime shift: %s → %s', v_last_regime, p_current_regime);
    ELSIF v_last_regime IS NULL THEN
        v_regime_score := 0.2;
        v_regime_reason := 'No prior regime data (exploratory)';
    ELSE
        v_regime_score := 0.0;
        v_regime_reason := format('Stable regime: %s', p_current_regime);
    END IF;

    -- COMPONENT 2: Asset Novelty (0-0.3)
    -- How many times have we traded this asset in last 7 days?
    SELECT COUNT(*) INTO v_asset_trade_count
    FROM fhq_governance.paper_ledger
    WHERE canonical_id = p_canonical_id
    AND decision_timestamp >= NOW() - INTERVAL '7 days';

    IF v_asset_trade_count = 0 THEN
        v_asset_score := 0.3;
        v_asset_reason := 'First trade on this asset in 7 days';
    ELSIF v_asset_trade_count < 3 THEN
        v_asset_score := 0.15;
        v_asset_reason := format('Limited history: %s trades in 7 days', v_asset_trade_count);
    ELSE
        v_asset_score := 0.0;
        v_asset_reason := format('Well-traded asset: %s trades in 7 days', v_asset_trade_count);
    END IF;

    -- COMPONENT 3: Signal Disagreement (0-0.3)
    -- Are we going against recent direction for this asset?
    SELECT
        COUNT(*) FILTER (WHERE direction = p_direction),
        COUNT(*) FILTER (WHERE direction != p_direction)
    INTO v_recent_same_direction, v_recent_opposite_direction
    FROM fhq_governance.paper_ledger
    WHERE canonical_id = p_canonical_id
    AND decision_timestamp >= NOW() - INTERVAL '48 hours';

    IF v_recent_opposite_direction > v_recent_same_direction AND v_recent_same_direction > 0 THEN
        v_signal_score := 0.3;
        v_signal_reason := format('Contrarian signal: %s opposite vs %s same in 48h',
                                   v_recent_opposite_direction, v_recent_same_direction);
    ELSIF v_recent_same_direction = 0 AND v_recent_opposite_direction = 0 THEN
        v_signal_score := 0.15;
        v_signal_reason := 'No recent signals for comparison';
    ELSE
        v_signal_score := 0.0;
        v_signal_reason := format('Consensus signal: %s same vs %s opposite in 48h',
                                   v_recent_same_direction, v_recent_opposite_direction);
    END IF;

    v_explanation := jsonb_build_object(
        'regime_shift', jsonb_build_object('score', v_regime_score, 'reason', v_regime_reason),
        'asset_novelty', jsonb_build_object('score', v_asset_score, 'reason', v_asset_reason),
        'signal_disagreement', jsonb_build_object('score', v_signal_score, 'reason', v_signal_reason),
        'total', v_regime_score + v_asset_score + v_signal_score
    );

    -- Log components if trade_id provided
    IF p_trade_id IS NOT NULL THEN
        INSERT INTO fhq_governance.novelty_score_components (
            trade_id, regime_shift_score, regime_shift_reason,
            asset_novelty_score, asset_novelty_reason,
            signal_disagreement_score, signal_disagreement_reason
        ) VALUES (
            p_trade_id, v_regime_score, v_regime_reason,
            v_asset_score, v_asset_reason,
            v_signal_score, v_signal_reason
        );
    END IF;

    RETURN QUERY SELECT
        v_regime_score + v_asset_score + v_signal_score,
        v_regime_score,
        v_asset_score,
        v_signal_score,
        v_explanation;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- HARDENING 3: TWO-TIER EPISTEMIC STOP-LOSS
-- ============================================================================

-- Add halt status columns to epistemic_health_daily
ALTER TABLE fhq_governance.epistemic_health_daily
ADD COLUMN IF NOT EXISTS halt_level TEXT DEFAULT 'NONE' CHECK (halt_level IN ('NONE', 'SOFT_HALT', 'HARD_HALT')),
ADD COLUMN IF NOT EXISTS soft_halt_until TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS hard_halt_vega_attestation TEXT,
ADD COLUMN IF NOT EXISTS high_conf_inversion_days INTEGER DEFAULT 0;

-- Replace epistemic stop-loss checker with two-tier version
CREATE OR REPLACE FUNCTION fhq_governance.check_epistemic_stop_loss()
RETURNS TABLE (
    halt_level TEXT,
    reason TEXT,
    hit_rate_streak INTEGER,
    brier_streak INTEGER,
    repeated_errors INTEGER,
    high_conf_inversion_days INTEGER,
    soft_halt_expires_at TIMESTAMPTZ
) AS $$
DECLARE
    v_hit_streak INTEGER;
    v_brier_streak INTEGER;
    v_type_d_repeats INTEGER;
    v_type_e_repeats INTEGER;
    v_inversion_days INTEGER;
    v_halt_level TEXT := 'NONE';
    v_reason TEXT;
    v_current_halt TEXT;
    v_soft_until TIMESTAMPTZ;
    v_high_conf_accuracy NUMERIC;
BEGIN
    -- Get current status
    SELECT
        COALESCE(hit_rate_decline_streak, 0),
        COALESCE(brier_worsening_streak, 0),
        COALESCE(type_d_count, 0),
        COALESCE(type_e_count, 0),
        COALESCE(high_conf_inversion_days, 0),
        halt_level,
        soft_halt_until
    INTO v_hit_streak, v_brier_streak, v_type_d_repeats, v_type_e_repeats,
         v_inversion_days, v_current_halt, v_soft_until
    FROM fhq_governance.epistemic_health_daily
    WHERE health_date = CURRENT_DATE;

    -- Check if already in HARD_HALT (requires VEGA attestation to exit)
    IF v_current_halt = 'HARD_HALT' THEN
        RETURN QUERY SELECT
            'HARD_HALT'::TEXT,
            'Awaiting VEGA attestation to resume'::TEXT,
            v_hit_streak, v_brier_streak,
            v_type_d_repeats + v_type_e_repeats,
            v_inversion_days,
            NULL::TIMESTAMPTZ;
        RETURN;
    END IF;

    -- Check if in SOFT_HALT and still valid
    IF v_current_halt = 'SOFT_HALT' AND v_soft_until > NOW() THEN
        RETURN QUERY SELECT
            'SOFT_HALT'::TEXT,
            format('Soft halt active until %s', v_soft_until)::TEXT,
            v_hit_streak, v_brier_streak,
            v_type_d_repeats + v_type_e_repeats,
            v_inversion_days,
            v_soft_until;
        RETURN;
    END IF;

    -- Check for HIGH CONFIDENCE INVERSION (>80% conf with <35% accuracy)
    -- This triggers HARD_HALT after 2 days
    SELECT ROUND(100.0 * SUM(CASE WHEN fop.hit_rate_contribution THEN 1 ELSE 0 END)::numeric
                 / NULLIF(COUNT(*), 0), 2)
    INTO v_high_conf_accuracy
    FROM fhq_research.forecast_outcome_pairs fop
    JOIN fhq_research.forecast_ledger fl ON fop.forecast_id = fl.forecast_id
    WHERE fl.forecast_confidence >= 0.80
    AND fop.reconciled_at >= NOW() - INTERVAL '1 day';

    IF v_high_conf_accuracy IS NOT NULL AND v_high_conf_accuracy < 35 THEN
        v_inversion_days := v_inversion_days + 1;
    ELSE
        v_inversion_days := 0;
    END IF;

    -- HARD_HALT conditions
    IF v_inversion_days >= 2 THEN
        v_halt_level := 'HARD_HALT';
        v_reason := format('High-confidence inversion for %s days (>80%% conf with <%s%% accuracy)',
                          v_inversion_days, COALESCE(v_high_conf_accuracy, 0));
    -- SOFT_HALT conditions (12 hour pause)
    ELSIF v_hit_streak >= 3 THEN
        v_halt_level := 'SOFT_HALT';
        v_reason := format('Hit rate declined for %s consecutive days', v_hit_streak);
    ELSIF v_brier_streak >= 3 THEN
        v_halt_level := 'SOFT_HALT';
        v_reason := format('Brier score worsened for %s consecutive days', v_brier_streak);
    ELSIF v_type_d_repeats >= 3 THEN
        v_halt_level := 'SOFT_HALT';
        v_reason := format('TYPE_D (Regime Illusion) repeated %s times today', v_type_d_repeats);
    ELSIF v_type_e_repeats >= 3 THEN
        v_halt_level := 'SOFT_HALT';
        v_reason := format('TYPE_E (Correlation Breakdown) repeated %s times today', v_type_e_repeats);
    ELSE
        v_reason := 'No halt conditions met';
    END IF;

    -- Apply halt if triggered
    IF v_halt_level != 'NONE' THEN
        UPDATE fhq_governance.epistemic_health_daily
        SET halt_level = v_halt_level,
            soft_halt_until = CASE
                WHEN v_halt_level = 'SOFT_HALT' THEN NOW() + INTERVAL '12 hours'
                ELSE NULL
            END,
            high_conf_inversion_days = v_inversion_days,
            epistemic_stop_triggered = TRUE,
            stop_trigger_reason = v_reason,
            stop_triggered_at = NOW()
        WHERE health_date = CURRENT_DATE;

        -- Suspend pending decision plans
        UPDATE fhq_governance.paper_decision_plan
        SET status = 'SUSPENDED',
            suspended_reason = v_reason
        WHERE status IN ('PENDING', 'EXECUTING');
    END IF;

    RETURN QUERY SELECT
        v_halt_level,
        v_reason,
        v_hit_streak,
        v_brier_streak,
        v_type_d_repeats + v_type_e_repeats,
        v_inversion_days,
        CASE WHEN v_halt_level = 'SOFT_HALT' THEN NOW() + INTERVAL '12 hours' ELSE NULL END;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- HARDENING 4: DYNAMIC SLIPPAGE
-- ============================================================================

-- Add volatility/liquidity tracking
ALTER TABLE fhq_governance.paper_ledger
ADD COLUMN IF NOT EXISTS volatility_at_entry NUMERIC(8,4),
ADD COLUMN IF NOT EXISTS liquidity_tier_at_entry TEXT,
ADD COLUMN IF NOT EXISTS slippage_rule_applied TEXT;

-- Function to calculate dynamic slippage
CREATE OR REPLACE FUNCTION fhq_governance.calculate_dynamic_slippage(
    p_canonical_id TEXT,
    p_base_slippage NUMERIC DEFAULT 0.0005
)
RETURNS TABLE (
    effective_slippage NUMERIC,
    volatility_multiplier NUMERIC,
    liquidity_multiplier NUMERIC,
    rule_applied TEXT
) AS $$
DECLARE
    v_volatility NUMERIC;
    v_liquidity_tier TEXT;
    v_vol_mult NUMERIC := 1.0;
    v_liq_mult NUMERIC := 1.0;
    v_slippage NUMERIC;
    v_rule TEXT;
BEGIN
    -- Get recent volatility (std dev of returns over 5 days)
    SELECT COALESCE(STDDEV(
        (close - LAG(close) OVER (ORDER BY timestamp)) / NULLIF(LAG(close) OVER (ORDER BY timestamp), 0)
    ), 0.02)
    INTO v_volatility
    FROM fhq_market.prices
    WHERE canonical_id = p_canonical_id
    AND timestamp >= NOW() - INTERVAL '5 days';

    -- Get liquidity tier from asset metadata
    SELECT COALESCE(liquidity_tier, 'TIER_2')
    INTO v_liquidity_tier
    FROM fhq_meta.assets
    WHERE canonical_id = p_canonical_id;

    -- VOLATILITY MULTIPLIER
    -- Base assumption: 2% daily vol is normal
    IF v_volatility > 0.04 THEN  -- High volatility (>4%)
        v_vol_mult := 2.0;
        v_rule := 'HIGH_VOLATILITY';
    ELSIF v_volatility > 0.025 THEN  -- Elevated volatility
        v_vol_mult := 1.5;
        v_rule := 'ELEVATED_VOLATILITY';
    ELSE
        v_vol_mult := 1.0;
        v_rule := 'NORMAL_VOLATILITY';
    END IF;

    -- LIQUIDITY MULTIPLIER
    CASE v_liquidity_tier
        WHEN 'TIER_1' THEN v_liq_mult := 1.0;  -- High liquidity
        WHEN 'TIER_2' THEN v_liq_mult := 1.5;  -- Medium liquidity
        WHEN 'TIER_3' THEN v_liq_mult := 2.5;  -- Low liquidity
        ELSE v_liq_mult := 2.0;  -- Unknown = conservative
    END CASE;

    v_rule := v_rule || '_' || v_liquidity_tier;

    -- Calculate effective slippage (minimum 0.05%, maximum 1%)
    v_slippage := LEAST(0.01, GREATEST(p_base_slippage, p_base_slippage * v_vol_mult * v_liq_mult));

    RETURN QUERY SELECT v_slippage, v_vol_mult, v_liq_mult, v_rule;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- HARDENING 5: DAILY EDGE SIGNAL CAUSE CODES
-- ============================================================================

-- Add cause code enum and column
ALTER TABLE fhq_governance.epistemic_health_daily
ADD COLUMN IF NOT EXISTS edge_signal_cause_code TEXT CHECK (edge_signal_cause_code IN (
    'CALIBRATION_IMPROVED',
    'CALIBRATION_WORSENED',
    'VOLUME_TOO_LOW',
    'ERROR_CONCENTRATION_TYPE_D',
    'ERROR_CONCENTRATION_TYPE_E',
    'STABLE_NO_CHANGE',
    'MIXED_SIGNALS'
));

-- Replace edge signal function with cause code version
CREATE OR REPLACE FUNCTION fhq_governance.compute_daily_edge_signal()
RETURNS TABLE (
    edge_signal INTEGER,
    cause_code TEXT,
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
    v_type_d_pct NUMERIC;
    v_type_e_pct NUMERIC;
    v_trades_today INTEGER;
    v_signal INTEGER;
    v_cause TEXT;
    v_components JSONB;
BEGIN
    -- Get today's metrics
    SELECT
        COALESCE(hit_rate_today, 0),
        COALESCE(hit_rate_yesterday, 0),
        COALESCE(brier_today, 0.5),
        COALESCE(brier_yesterday, 0.5),
        COALESCE(trades_today, 0),
        COALESCE(type_d_count, 0),
        COALESCE(type_e_count, 0)
    INTO v_hit_today, v_hit_yesterday, v_brier_today, v_brier_yesterday,
         v_trades_today, v_type_d_pct, v_type_e_pct
    FROM fhq_governance.epistemic_health_daily
    WHERE health_date = CURRENT_DATE;

    -- Calculate error type percentages
    IF v_trades_today > 0 THEN
        v_type_d_pct := v_type_d_pct::numeric / v_trades_today;
        v_type_e_pct := v_type_e_pct::numeric / v_trades_today;
    ELSE
        v_type_d_pct := 0;
        v_type_e_pct := 0;
    END IF;

    -- Calculate error diversity
    SELECT COUNT(DISTINCT error_type)::numeric / NULLIF(COUNT(*)::numeric, 0)
    INTO v_error_diversity
    FROM fhq_governance.paper_ledger
    WHERE decision_timestamp >= NOW() - INTERVAL '7 days'
    AND outcome_correct = FALSE;

    v_error_diversity := COALESCE(v_error_diversity, 1.0);

    -- DETERMINE CAUSE CODE (audit-verifiable)
    IF v_trades_today < 3 THEN
        v_signal := 0;
        v_cause := 'VOLUME_TOO_LOW';
    ELSIF v_type_d_pct > 0.4 THEN  -- >40% TYPE_D errors
        v_signal := -1;
        v_cause := 'ERROR_CONCENTRATION_TYPE_D';
    ELSIF v_type_e_pct > 0.4 THEN  -- >40% TYPE_E errors
        v_signal := -1;
        v_cause := 'ERROR_CONCENTRATION_TYPE_E';
    ELSIF (v_hit_today > v_hit_yesterday + 0.02) OR (v_brier_today < v_brier_yesterday - 0.01) THEN
        v_signal := 1;
        v_cause := 'CALIBRATION_IMPROVED';
    ELSIF (v_hit_today < v_hit_yesterday - 0.02) AND (v_brier_today > v_brier_yesterday + 0.01) THEN
        v_signal := -1;
        v_cause := 'CALIBRATION_WORSENED';
    ELSIF ABS(v_hit_today - v_hit_yesterday) < 0.01 AND ABS(v_brier_today - v_brier_yesterday) < 0.005 THEN
        v_signal := 0;
        v_cause := 'STABLE_NO_CHANGE';
    ELSE
        v_signal := 0;
        v_cause := 'MIXED_SIGNALS';
    END IF;

    v_components := jsonb_build_object(
        'hit_rate_today', v_hit_today,
        'hit_rate_yesterday', v_hit_yesterday,
        'hit_rate_delta', v_hit_today - v_hit_yesterday,
        'brier_today', v_brier_today,
        'brier_yesterday', v_brier_yesterday,
        'brier_delta', v_brier_today - v_brier_yesterday,
        'trades_today', v_trades_today,
        'type_d_pct', v_type_d_pct,
        'type_e_pct', v_type_e_pct,
        'error_diversity', v_error_diversity,
        'cause_code', v_cause
    );

    -- Update daily health table
    UPDATE fhq_governance.epistemic_health_daily
    SET daily_edge_signal = v_signal,
        edge_signal_cause_code = v_cause,
        edge_signal_components = v_components,
        computed_at = NOW()
    WHERE health_date = CURRENT_DATE;

    RETURN QUERY SELECT
        v_signal,
        v_cause,
        v_hit_today - v_hit_yesterday,
        v_brier_today - v_brier_yesterday,
        v_error_diversity,
        v_components;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- UPDATE PAPER TRADE EXECUTION WITH HARDENINGS
-- ============================================================================

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
    v_calibrated_conf NUMERIC;
    v_gate_id UUID;
    v_match_type TEXT;
    v_threshold_rec RECORD;
    v_size_rec RECORD;
    v_stop_rec RECORD;
    v_novelty_rec RECORD;
    v_slippage_rec RECORD;
BEGIN
    -- Check epistemic stop-loss first (two-tier)
    SELECT * INTO v_stop_rec FROM fhq_governance.check_epistemic_stop_loss();
    IF v_stop_rec.halt_level IN ('SOFT_HALT', 'HARD_HALT') THEN
        RETURN QUERY SELECT
            NULL::UUID, FALSE,
            format('%s: %s', v_stop_rec.halt_level, v_stop_rec.reason),
            NULL::NUMERIC, NULL::NUMERIC, NULL::UUID, NULL::NUMERIC, NULL::NUMERIC;
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

    -- Get effective threshold (with hard floor)
    SELECT * INTO v_threshold_rec
    FROM fhq_governance.get_effective_confidence_threshold(0.25, 5);

    -- Check if above threshold
    IF v_calibrated_conf < v_threshold_rec.effective_threshold THEN
        RETURN QUERY SELECT
            NULL::UUID, FALSE,
            format('Calibrated confidence %s below threshold %s (floor: 22%%)',
                   v_calibrated_conf, v_threshold_rec.effective_threshold),
            v_calibrated_conf, NULL::NUMERIC, v_gate_id, NULL::NUMERIC, NULL::NUMERIC;
        RETURN;
    END IF;

    -- Generate trade ID first (needed for novelty logging)
    v_trade_id := gen_random_uuid();

    -- Calculate deterministic novelty score (HARDENING 2)
    SELECT * INTO v_novelty_rec
    FROM fhq_governance.calculate_novelty_score(p_canonical_id, p_direction, p_regime, v_trade_id);

    -- Calculate info-weighted size
    SELECT * INTO v_size_rec
    FROM fhq_governance.calculate_info_weighted_size(
        p_base_size, v_calibrated_conf, v_novelty_rec.novelty_score
    );

    -- Calculate dynamic slippage (HARDENING 4)
    SELECT * INTO v_slippage_rec
    FROM fhq_governance.calculate_dynamic_slippage(p_canonical_id, 0.0005);

    -- Execute paper trade
    INSERT INTO fhq_governance.paper_ledger (
        trade_id, asset_id, canonical_id, direction,
        raw_position_size, calibrated_position_size, information_weight,
        raw_confidence, calibrated_confidence, calibration_gate_id,
        entry_price, simulated_slippage, slippage_rule_applied,
        forecast_id, regime_at_entry, novelty_score
    ) VALUES (
        v_trade_id, p_asset_id, p_canonical_id, p_direction,
        p_base_size, v_size_rec.weighted_size, v_size_rec.info_gain_estimate,
        p_raw_confidence, v_calibrated_conf, v_gate_id,
        p_entry_price, v_slippage_rec.effective_slippage, v_slippage_rec.rule_applied,
        p_forecast_id, p_regime, v_novelty_rec.novelty_score
    );

    RETURN QUERY SELECT
        v_trade_id, TRUE, NULL::TEXT,
        v_calibrated_conf, v_size_rec.weighted_size, v_gate_id,
        v_novelty_rec.novelty_score, v_slippage_rec.effective_slippage;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- GOVERNANCE LOGGING
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale,
    metadata, agent_id, timestamp
) VALUES (
    gen_random_uuid(),
    'PAPER_TRADING_HARDENINGS_DEPLOYED',
    'CEO-DIR-2026-033',
    'DIRECTIVE',
    'STIG',
    NOW(),
    'EXECUTED',
    'Deployed 5 CEO-mandated hardenings to make paper trading board-proof: (1) Cadence floor 22% + VEGA exception, (2) Deterministic novelty score, (3) Two-tier SOFT/HARD halt, (4) Dynamic slippage, (5) Edge signal cause codes.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-033',
        'migration', '228_paper_trading_hardenings.sql',
        'hardenings', jsonb_build_array(
            jsonb_build_object('id', 1, 'name', 'Cadence floor + timelock', 'floor', 0.22),
            jsonb_build_object('id', 2, 'name', 'Deterministic novelty score', 'components', 3),
            jsonb_build_object('id', 3, 'name', 'Two-tier epistemic stop-loss', 'levels', 'SOFT_HALT/HARD_HALT'),
            jsonb_build_object('id', 4, 'name', 'Dynamic slippage', 'min', 0.0005, 'max', 0.01),
            jsonb_build_object('id', 5, 'name', 'Edge signal cause codes', 'codes', 7)
        ),
        'classification', 'BOARD_PROOF'
    ),
    'STIG',
    NOW()
);
