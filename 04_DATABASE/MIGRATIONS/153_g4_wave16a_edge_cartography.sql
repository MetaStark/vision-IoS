-- ============================================================================
-- Migration 153: G4 WAVE 16A - Edge Cartography & 3-Axis Classification
-- ============================================================================
-- CEO Directive: WAVE 16A - G4 REFINEMENT
-- Date: 2025-12-18
-- Purpose: Transform G4 from binary elimination to high-resolution edge mapping
--
-- STRATEGIC PIVOT: From "Elimination" to "Cartography"
-- Instead of binary PASS/REJECT, we now map edges across 3 axes:
--
-- AXIS A: Historical Merit (based on OOS Sharpe)
--   - STRONG:   Sharpe >= 1.5
--   - MODERATE: Sharpe >= 1.0 AND < 1.5
--   - WEAK:     Sharpe >= 0.5 AND < 1.0
--   - NONE:     Sharpe < 0.5 (but NOT negative)
--
-- AXIS B: Physical Robustness (execution realism)
--   - ROBUST:      Survives 1s latency with >50% edge retention
--   - FRAGILE:     Degrades but still positive
--   - THEORETICAL: Edge destroyed by latency OR untestable
--
-- AXIS C: Regime Dependence
--   - AGNOSTIC:  Works across multiple regimes
--   - SPECIFIC:  Requires specific regime context
--
-- REJECT reserved for: Sharpe < 0.0 (negative expectancy)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. ADD AXIS COLUMNS TO REFINERY RESULTS
-- ============================================================================

-- Add historical_merit axis to refinery results
ALTER TABLE fhq_canonical.g4_refinery_results
ADD COLUMN IF NOT EXISTS historical_merit TEXT;

-- Add constraint after column exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'g4_refinery_historical_merit_check'
    ) THEN
        ALTER TABLE fhq_canonical.g4_refinery_results
        ADD CONSTRAINT g4_refinery_historical_merit_check
        CHECK (historical_merit IN ('STRONG', 'MODERATE', 'WEAK', 'NONE', 'NEGATIVE'));
    END IF;
END $$;

-- Add backtest strategy tracking
ALTER TABLE fhq_canonical.g4_refinery_results
ADD COLUMN IF NOT EXISTS backtest_strategy_id TEXT,
ADD COLUMN IF NOT EXISTS backtest_strategy_version TEXT,
ADD COLUMN IF NOT EXISTS hypothesis_category TEXT,
ADD COLUMN IF NOT EXISTS logic_translation_hash TEXT;

-- ============================================================================
-- 2. ADD AXIS COLUMNS TO PHYSICS RESULTS
-- ============================================================================

-- Add physical robustness refinement
ALTER TABLE fhq_canonical.g4_physics_results
ADD COLUMN IF NOT EXISTS robustness_axis TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'g4_physics_robustness_axis_check'
    ) THEN
        ALTER TABLE fhq_canonical.g4_physics_results
        ADD CONSTRAINT g4_physics_robustness_axis_check
        CHECK (robustness_axis IN ('ROBUST', 'FRAGILE', 'THEORETICAL'));
    END IF;
END $$;

-- ============================================================================
-- 3. ADD 3-AXIS COLUMNS TO COMPOSITE SCORECARD
-- ============================================================================

-- Axis A: Historical Merit
ALTER TABLE fhq_canonical.g4_composite_scorecard
ADD COLUMN IF NOT EXISTS axis_a_historical_merit TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'g4_scorecard_axis_a_check'
    ) THEN
        ALTER TABLE fhq_canonical.g4_composite_scorecard
        ADD CONSTRAINT g4_scorecard_axis_a_check
        CHECK (axis_a_historical_merit IN ('STRONG', 'MODERATE', 'WEAK', 'NONE', 'NEGATIVE'));
    END IF;
END $$;

-- Axis B: Physical Robustness
ALTER TABLE fhq_canonical.g4_composite_scorecard
ADD COLUMN IF NOT EXISTS axis_b_physical_robustness TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'g4_scorecard_axis_b_check'
    ) THEN
        ALTER TABLE fhq_canonical.g4_composite_scorecard
        ADD CONSTRAINT g4_scorecard_axis_b_check
        CHECK (axis_b_physical_robustness IN ('ROBUST', 'FRAGILE', 'THEORETICAL'));
    END IF;
END $$;

-- Axis C: Regime Dependence
ALTER TABLE fhq_canonical.g4_composite_scorecard
ADD COLUMN IF NOT EXISTS axis_c_regime_dependence TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'g4_scorecard_axis_c_check'
    ) THEN
        ALTER TABLE fhq_canonical.g4_composite_scorecard
        ADD CONSTRAINT g4_scorecard_axis_c_check
        CHECK (axis_c_regime_dependence IN ('AGNOSTIC', 'SPECIFIC'));
    END IF;
END $$;

-- Add edge map coordinates (for visualization)
ALTER TABLE fhq_canonical.g4_composite_scorecard
ADD COLUMN IF NOT EXISTS edge_map_coordinates JSONB;

-- Add logic translation tracking
ALTER TABLE fhq_canonical.g4_composite_scorecard
ADD COLUMN IF NOT EXISTS logic_translation_applied BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS hypothesis_category TEXT,
ADD COLUMN IF NOT EXISTS backtest_strategy_id TEXT;

-- ============================================================================
-- 4. CREATE LOGIC TRANSLATION REGISTRY
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g4_logic_translation_registry (
    strategy_id TEXT PRIMARY KEY,
    hypothesis_category TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    strategy_version TEXT NOT NULL DEFAULT 'v1.0.0',

    -- Strategy definition
    entry_logic JSONB NOT NULL,
    exit_logic JSONB NOT NULL,
    position_sizing JSONB,

    -- Backtest parameters
    default_lookback_years INTEGER DEFAULT 5,
    default_in_sample_ratio DECIMAL(3,2) DEFAULT 0.70,
    requires_specific_indicators JSONB,
    requires_regime_data BOOLEAN DEFAULT false,

    -- Regime specificity
    regime_agnostic BOOLEAN DEFAULT false,
    applicable_regimes TEXT[],

    -- Governance
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT DEFAULT 'STIG',
    approved_by TEXT,
    approval_timestamp TIMESTAMPTZ,

    -- Audit
    strategy_hash TEXT,
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_g4_logic_category
ON fhq_canonical.g4_logic_translation_registry(hypothesis_category);

-- ============================================================================
-- 5. POPULATE LOGIC TRANSLATION REGISTRY WITH CATEGORY STRATEGIES
-- ============================================================================

INSERT INTO fhq_canonical.g4_logic_translation_registry (
    strategy_id, hypothesis_category, strategy_name, strategy_version,
    entry_logic, exit_logic, position_sizing,
    requires_regime_data, regime_agnostic, applicable_regimes
) VALUES
-- MEAN_REVERSION Strategy
(
    'LT-MEAN_REVERSION-v1',
    'MEAN_REVERSION',
    'Statistical Mean Reversion',
    'v1.0.0',
    '{
        "type": "mean_reversion",
        "zscore_entry_threshold": 2.0,
        "lookback_period": 20,
        "confirmation_bars": 1,
        "entry_condition": "price_zscore <= -entry_threshold OR price_zscore >= entry_threshold"
    }'::jsonb,
    '{
        "type": "mean_reversion_exit",
        "zscore_exit_threshold": 0.5,
        "max_holding_days": 10,
        "stop_loss_zscore": 3.0,
        "exit_condition": "ABS(price_zscore) <= exit_threshold OR days_held >= max_holding"
    }'::jsonb,
    '{"base_risk_pct": 0.02, "scale_by_zscore": true}'::jsonb,
    false, true, ARRAY['BULL', 'BEAR', 'NEUTRAL']
),

-- BREAKOUT Strategy
(
    'LT-BREAKOUT-v1',
    'BREAKOUT',
    'Volatility Compression Breakout',
    'v1.0.0',
    '{
        "type": "breakout",
        "bollinger_period": 20,
        "bollinger_std": 2.0,
        "volume_multiplier": 1.5,
        "atr_period": 14,
        "entry_condition": "close > upper_band AND volume > avg_volume * volume_multiplier"
    }'::jsonb,
    '{
        "type": "breakout_exit",
        "trailing_stop_atr": 2.0,
        "profit_target_atr": 4.0,
        "time_stop_days": 20,
        "exit_condition": "trailing_stop_hit OR profit_target_hit OR time_stop"
    }'::jsonb,
    '{"base_risk_pct": 0.01, "atr_based_sizing": true}'::jsonb,
    false, true, ARRAY['BULL', 'BEAR', 'NEUTRAL']
),

-- REGIME_EDGE Strategy
(
    'LT-REGIME_EDGE-v1',
    'REGIME_EDGE',
    'Regime Transition Edge',
    'v1.0.0',
    '{
        "type": "regime_transition",
        "regime_lookback": 30,
        "transition_signal": "regime_change_detected",
        "confirmation_volume": 1.3,
        "entry_condition": "regime_transition_signal AND volume_confirmation"
    }'::jsonb,
    '{
        "type": "regime_edge_exit",
        "regime_stabilization_days": 5,
        "adverse_regime_change": true,
        "profit_target_pct": 10.0,
        "stop_loss_pct": 5.0,
        "exit_condition": "regime_stabilized OR adverse_change OR target_hit OR stop_hit"
    }'::jsonb,
    '{"base_risk_pct": 0.015, "regime_confidence_scaling": true}'::jsonb,
    true, false, ARRAY['NEUTRAL']  -- Only triggers on transition
),

-- CATALYST_AMPLIFICATION Strategy
(
    'LT-CATALYST_AMPLIFICATION-v1',
    'CATALYST_AMPLIFICATION',
    'Catalyst Event Amplification',
    'v1.0.0',
    '{
        "type": "catalyst",
        "pre_catalyst_vol_compression": true,
        "volume_surge_threshold": 2.0,
        "price_move_threshold_pct": 3.0,
        "entry_condition": "catalyst_detected AND volume_surge AND price_direction_confirmed"
    }'::jsonb,
    '{
        "type": "catalyst_exit",
        "momentum_exhaustion_signal": true,
        "volume_decline_threshold": 0.7,
        "max_holding_hours": 72,
        "trailing_stop_pct": 2.0,
        "exit_condition": "momentum_exhaustion OR volume_decline OR time_stop OR trailing_stop"
    }'::jsonb,
    '{"base_risk_pct": 0.01, "catalyst_strength_scaling": true}'::jsonb,
    false, false, ARRAY['BULL', 'NEUTRAL']
),

-- VOLATILITY Strategy
(
    'LT-VOLATILITY-v1',
    'VOLATILITY',
    'Volatility Regime Trading',
    'v1.0.0',
    '{
        "type": "volatility",
        "vol_percentile_lookback": 60,
        "low_vol_threshold_pct": 20,
        "high_vol_threshold_pct": 80,
        "entry_condition": "vol_percentile <= low_threshold OR vol_percentile >= high_threshold"
    }'::jsonb,
    '{
        "type": "volatility_exit",
        "vol_mean_reversion_target": 50,
        "max_holding_days": 15,
        "stop_loss_pct": 3.0,
        "exit_condition": "vol_normalized OR time_stop OR stop_loss"
    }'::jsonb,
    '{"base_risk_pct": 0.01, "inverse_vol_sizing": true}'::jsonb,
    false, true, ARRAY['BULL', 'BEAR', 'NEUTRAL']
),

-- TIMING Strategy
(
    'LT-TIMING-v1',
    'TIMING',
    'Temporal Pattern Trading',
    'v1.0.0',
    '{
        "type": "timing",
        "intraday_pattern": true,
        "session_bias": "first_hour",
        "day_of_week_filter": [1, 2, 3, 4, 5],
        "entry_condition": "timing_pattern_detected AND session_aligned"
    }'::jsonb,
    '{
        "type": "timing_exit",
        "session_end_exit": true,
        "max_holding_hours": 8,
        "intraday_stop_pct": 1.0,
        "exit_condition": "session_end OR time_stop OR intraday_stop"
    }'::jsonb,
    '{"base_risk_pct": 0.005, "time_decay_adjustment": true}'::jsonb,
    false, true, ARRAY['BULL', 'BEAR', 'NEUTRAL']
),

-- MOMENTUM Strategy
(
    'LT-MOMENTUM-v1',
    'MOMENTUM',
    'Trend Following Momentum',
    'v1.0.0',
    '{
        "type": "momentum",
        "fast_ma": 10,
        "slow_ma": 30,
        "rsi_period": 14,
        "rsi_threshold": 50,
        "entry_condition": "fast_ma > slow_ma AND rsi > threshold AND price > slow_ma"
    }'::jsonb,
    '{
        "type": "momentum_exit",
        "ma_cross_exit": true,
        "rsi_reversal_threshold": 30,
        "trailing_stop_pct": 5.0,
        "exit_condition": "ma_cross_down OR rsi_reversal OR trailing_stop"
    }'::jsonb,
    '{"base_risk_pct": 0.02, "trend_strength_scaling": true}'::jsonb,
    false, false, ARRAY['BULL']
),

-- CROSS_ASSET Strategy
(
    'LT-CROSS_ASSET-v1',
    'CROSS_ASSET',
    'Cross-Asset Correlation',
    'v1.0.0',
    '{
        "type": "cross_asset",
        "correlation_lookback": 30,
        "correlation_threshold": 0.7,
        "divergence_zscore": 2.0,
        "entry_condition": "correlation_breakdown OR divergence_detected"
    }'::jsonb,
    '{
        "type": "cross_asset_exit",
        "correlation_restoration": true,
        "divergence_mean_reversion": true,
        "max_holding_days": 10,
        "exit_condition": "correlation_restored OR divergence_closed OR time_stop"
    }'::jsonb,
    '{"base_risk_pct": 0.01, "pair_neutral_sizing": true}'::jsonb,
    false, true, ARRAY['BULL', 'BEAR', 'NEUTRAL']
),

-- CONTRARIAN Strategy
(
    'LT-CONTRARIAN-v1',
    'CONTRARIAN',
    'Sentiment Contrarian',
    'v1.0.0',
    '{
        "type": "contrarian",
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "volume_capitulation_mult": 2.5,
        "entry_condition": "(rsi <= oversold AND volume_spike) OR (rsi >= overbought AND volume_spike)"
    }'::jsonb,
    '{
        "type": "contrarian_exit",
        "rsi_neutral_zone": [40, 60],
        "profit_target_pct": 5.0,
        "stop_loss_pct": 3.0,
        "exit_condition": "rsi_normalized OR target_hit OR stop_hit"
    }'::jsonb,
    '{"base_risk_pct": 0.01, "extreme_sentiment_scaling": true}'::jsonb,
    false, false, ARRAY['BEAR', 'NEUTRAL']
),

-- LIQUIDITY_SHIFT Strategy
(
    'LT-LIQUIDITY_SHIFT-v1',
    'LIQUIDITY_SHIFT',
    'Liquidity Flow Detection',
    'v1.0.0',
    '{
        "type": "liquidity",
        "volume_ma_period": 20,
        "liquidity_surge_mult": 2.0,
        "bid_ask_spread_threshold": 0.5,
        "entry_condition": "liquidity_surge_detected AND spread_compression"
    }'::jsonb,
    '{
        "type": "liquidity_exit",
        "liquidity_normalization": true,
        "spread_expansion_exit": true,
        "max_holding_hours": 48,
        "exit_condition": "liquidity_normal OR spread_expand OR time_stop"
    }'::jsonb,
    '{"base_risk_pct": 0.01, "liquidity_adjusted_sizing": true}'::jsonb,
    false, true, ARRAY['BULL', 'BEAR', 'NEUTRAL']
)
ON CONFLICT (strategy_id) DO UPDATE SET
    strategy_version = EXCLUDED.strategy_version,
    entry_logic = EXCLUDED.entry_logic,
    exit_logic = EXCLUDED.exit_logic,
    position_sizing = EXCLUDED.position_sizing;

-- ============================================================================
-- 6. CREATE EDGE CARTOGRAPHY VIEW
-- ============================================================================

CREATE OR REPLACE VIEW fhq_canonical.v_g4_edge_cartography AS
SELECT
    gn.needle_id,
    gn.hypothesis_title,
    gn.hypothesis_category,
    gn.eqs_score,
    gn.regime_sovereign,

    -- Axis A: Historical Merit
    COALESCE(sc.axis_a_historical_merit, 'PENDING') as axis_a_historical_merit,
    rr.oos_sharpe_ratio,

    -- Axis B: Physical Robustness
    COALESCE(sc.axis_b_physical_robustness, 'PENDING') as axis_b_physical_robustness,
    pr.edge_retained_1000ms_pct,
    pr.signal_half_life_seconds,

    -- Axis C: Regime Dependence
    COALESCE(sc.axis_c_regime_dependence, 'PENDING') as axis_c_regime_dependence,

    -- Composite Classification
    COALESCE(sc.classification, 'PENDING') as classification,
    sc.eligible_for_g5,

    -- Logic Translation Status
    COALESCE(sc.logic_translation_applied, false) as logic_translation_applied,
    sc.backtest_strategy_id,

    -- Queue Status
    q.refinery_status,
    q.physics_status,

    -- Timestamps
    gn.created_at as needle_created,
    sc.scored_at as scorecard_created

FROM fhq_canonical.golden_needles gn
LEFT JOIN fhq_canonical.g4_validation_queue q ON gn.needle_id = q.needle_id
LEFT JOIN fhq_canonical.g4_refinery_results rr ON gn.needle_id = rr.needle_id
LEFT JOIN fhq_canonical.g4_physics_results pr ON gn.needle_id = pr.needle_id
LEFT JOIN fhq_canonical.g4_composite_scorecard sc ON gn.needle_id = sc.needle_id
WHERE gn.is_current = true
ORDER BY gn.eqs_score DESC, gn.created_at DESC;

-- ============================================================================
-- 7. CREATE CLASSIFICATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_canonical.fn_classify_3axis(
    p_oos_sharpe DECIMAL,
    p_edge_retained_1000ms DECIMAL,
    p_signal_half_life DECIMAL,
    p_regime_sovereign TEXT,
    p_hypothesis_category TEXT
) RETURNS TABLE (
    axis_a TEXT,
    axis_b TEXT,
    axis_c TEXT,
    composite TEXT,
    eligible_g5 BOOLEAN
) AS $$
DECLARE
    v_axis_a TEXT;
    v_axis_b TEXT;
    v_axis_c TEXT;
    v_composite TEXT;
    v_eligible BOOLEAN := false;
BEGIN
    -- AXIS A: Historical Merit
    IF p_oos_sharpe IS NULL THEN
        v_axis_a := 'NONE';
    ELSIF p_oos_sharpe < 0 THEN
        v_axis_a := 'NEGATIVE';
    ELSIF p_oos_sharpe >= 1.5 THEN
        v_axis_a := 'STRONG';
    ELSIF p_oos_sharpe >= 1.0 THEN
        v_axis_a := 'MODERATE';
    ELSIF p_oos_sharpe >= 0.5 THEN
        v_axis_a := 'WEAK';
    ELSE
        v_axis_a := 'NONE';
    END IF;

    -- AXIS B: Physical Robustness
    IF p_edge_retained_1000ms IS NULL OR p_signal_half_life IS NULL THEN
        v_axis_b := 'THEORETICAL';
    ELSIF p_edge_retained_1000ms >= 50 THEN
        v_axis_b := 'ROBUST';
    ELSIF p_edge_retained_1000ms > 0 THEN
        v_axis_b := 'FRAGILE';
    ELSE
        v_axis_b := 'THEORETICAL';
    END IF;

    -- AXIS C: Regime Dependence
    -- Categories that are regime-specific
    IF p_hypothesis_category IN ('REGIME_EDGE', 'CATALYST_AMPLIFICATION') THEN
        v_axis_c := 'SPECIFIC';
    ELSE
        v_axis_c := 'AGNOSTIC';
    END IF;

    -- COMPOSITE CLASSIFICATION (WAVE 16A Rules)
    IF v_axis_a = 'NEGATIVE' THEN
        v_composite := 'REJECT';  -- Only true REJECT: negative expectancy
    ELSIF v_axis_a = 'STRONG' AND v_axis_b = 'ROBUST' THEN
        v_composite := 'PLATINUM';
        v_eligible := true;
    ELSIF v_axis_a = 'STRONG' AND v_axis_b = 'FRAGILE' THEN
        v_composite := 'GOLD';
    ELSIF v_axis_a = 'MODERATE' AND v_axis_b = 'ROBUST' THEN
        v_composite := 'GOLD';
    ELSIF v_axis_a = 'MODERATE' AND v_axis_b = 'FRAGILE' THEN
        v_composite := 'SILVER';
    ELSIF v_axis_a = 'WEAK' AND v_axis_b = 'ROBUST' THEN
        v_composite := 'SILVER';
    ELSIF v_axis_a = 'WEAK' AND v_axis_b = 'FRAGILE' THEN
        v_composite := 'BRONZE';
    ELSIF v_axis_a IN ('NONE', 'WEAK') AND v_axis_b = 'THEORETICAL' THEN
        v_composite := 'BRONZE';  -- Still mappable, not rejected
    ELSE
        v_composite := 'BRONZE';  -- Default to lowest non-reject tier
    END IF;

    RETURN QUERY SELECT v_axis_a, v_axis_b, v_axis_c, v_composite, v_eligible;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. UPDATE CLASSIFICATION CONSTRAINT
-- ============================================================================

-- Drop old constraint if exists
ALTER TABLE fhq_canonical.g4_composite_scorecard
DROP CONSTRAINT IF EXISTS g4_composite_scorecard_classification_check;

-- Add updated constraint allowing PENDING
ALTER TABLE fhq_canonical.g4_composite_scorecard
ADD CONSTRAINT g4_composite_scorecard_classification_check
CHECK (classification IN ('PLATINUM', 'GOLD', 'SILVER', 'BRONZE', 'REJECT', 'PENDING'));

-- ============================================================================
-- 9. GOVERNANCE REGISTRATION
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id, adr_title, adr_status, adr_type, file_path, sha256_hash,
    title, status, current_version, created_by
) VALUES (
    'G4-WAVE16A-001',
    'G4 WAVE 16A - Edge Cartography & 3-Axis Classification',
    'APPROVED',
    'OPERATIONAL',
    '04_DATABASE/MIGRATIONS/153_g4_wave16a_edge_cartography.sql',
    encode(sha256('g4-wave16a-edge-cartography-20251218'::bytea), 'hex'),
    'G4 Edge Cartography Schema',
    'ACTIVE',
    '1.0.0',
    'STIG'
) ON CONFLICT (adr_id) DO UPDATE SET
    adr_status = 'APPROVED',
    status = 'ACTIVE',
    updated_at = NOW();

-- ============================================================================
-- 10. LOG ACTIVATION EVENT
-- ============================================================================

INSERT INTO fhq_monitoring.system_event_log (event_type, severity, source_system, event_message, metadata)
VALUES (
    'g4_wave16a_activated',
    'INFO',
    'STIG',
    'G4 WAVE 16A Edge Cartography activated per CEO Directive',
    jsonb_build_object(
        'directive', 'CEO DIRECTIVE WAVE 16A',
        'strategic_pivot', 'Elimination -> Cartography',
        'axes', jsonb_build_object(
            'axis_a', 'Historical Merit (STRONG/MODERATE/WEAK/NONE/NEGATIVE)',
            'axis_b', 'Physical Robustness (ROBUST/FRAGILE/THEORETICAL)',
            'axis_c', 'Regime Dependence (AGNOSTIC/SPECIFIC)'
        ),
        'reject_criteria', 'Sharpe < 0.0 (negative expectancy only)',
        'logic_translation_strategies', 10,
        'hypothesis_categories_covered', ARRAY[
            'MEAN_REVERSION', 'BREAKOUT', 'REGIME_EDGE', 'CATALYST_AMPLIFICATION',
            'VOLATILITY', 'TIMING', 'MOMENTUM', 'CROSS_ASSET', 'CONTRARIAN', 'LIQUIDITY_SHIFT'
        ],
        'timestamp', NOW()
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_strategies INTEGER;
    v_needles INTEGER;
    v_categories INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_strategies
    FROM fhq_canonical.g4_logic_translation_registry
    WHERE is_active = true;

    SELECT COUNT(*) INTO v_needles
    FROM fhq_canonical.golden_needles
    WHERE is_current = true;

    SELECT COUNT(DISTINCT hypothesis_category) INTO v_categories
    FROM fhq_canonical.golden_needles
    WHERE is_current = true;

    RAISE NOTICE '=== G4 WAVE 16A Edge Cartography Verification ===';
    RAISE NOTICE 'Logic Translation Strategies Registered: %', v_strategies;
    RAISE NOTICE 'Golden Needles Ready for Cartography: %', v_needles;
    RAISE NOTICE 'Hypothesis Categories Detected: %', v_categories;
    RAISE NOTICE '';
    RAISE NOTICE 'AXIS A (Historical Merit): STRONG >= 1.5, MODERATE >= 1.0, WEAK >= 0.5, NONE < 0.5';
    RAISE NOTICE 'AXIS B (Physical Robustness): ROBUST > 50%% edge @ 1s, FRAGILE > 0%%, THEORETICAL = untestable';
    RAISE NOTICE 'AXIS C (Regime Dependence): AGNOSTIC = multi-regime, SPECIFIC = regime-bound';
    RAISE NOTICE '';
    RAISE NOTICE 'REJECT reserved for: Sharpe < 0.0 (negative expectancy ONLY)';
    RAISE NOTICE 'STATUS: WAVE 16A EDGE CARTOGRAPHY ACTIVE';
END $$;
