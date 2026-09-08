-- ============================================================================
-- Migration 316: CEO-DIR-2026-107 SPOT-Canonical Exit Framework
-- ============================================================================
-- Directive: CEO-DIR-2026-107
-- Classification: GOVERNANCE-CRITICAL
-- Author: STIG
-- Date: 2026-01-19
--
-- Purpose:
-- Transition from OPTIONS-semantic exit rules to SPOT-canonical framework:
-- - Stop Loss: 2.0x ATR(14) from entry (volatility-adjusted, price-based)
-- - Take Profit: 1.25R where R = |entry_price - canonical_stop_loss|
-- - Sentinel daemon as governance enforcement layer
--
-- CEO Precision Upgrades Applied:
-- UPGRADE 1: ATR(14), daily timeframe, per IoS-008 Canonical Indicator Registry
-- UPGRADE 2: R = absolute price distance between entry and canonical SL at initiation
-- UPGRADE 3: Sentinel classified as governance enforcement, not performance logic
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1: Extend paper positions table with canonical exit levels
-- ============================================================================

ALTER TABLE fhq_alpha.ios012b_paper_positions
ADD COLUMN IF NOT EXISTS canonical_stop_loss NUMERIC,
ADD COLUMN IF NOT EXISTS canonical_take_profit NUMERIC,
ADD COLUMN IF NOT EXISTS atr_at_entry NUMERIC,
ADD COLUMN IF NOT EXISTS r_value NUMERIC,
ADD COLUMN IF NOT EXISTS exit_rule_triggered TEXT,
ADD COLUMN IF NOT EXISTS sentinel_monitored BOOLEAN DEFAULT TRUE;

COMMENT ON COLUMN fhq_alpha.ios012b_paper_positions.canonical_stop_loss IS
    'CEO-DIR-2026-107: Stop loss = entry_price - (2.0 * ATR(14)) for LONG, entry_price + (2.0 * ATR(14)) for SHORT';
COMMENT ON COLUMN fhq_alpha.ios012b_paper_positions.canonical_take_profit IS
    'CEO-DIR-2026-107: Take profit = entry_price + (1.25 * R) for LONG, entry_price - (1.25 * R) for SHORT';
COMMENT ON COLUMN fhq_alpha.ios012b_paper_positions.atr_at_entry IS
    'ATR(14) value at position entry, per IoS-008 Canonical Indicator Registry';
COMMENT ON COLUMN fhq_alpha.ios012b_paper_positions.r_value IS
    'Risk unit R = |entry_price - canonical_stop_loss| at trade initiation';
COMMENT ON COLUMN fhq_alpha.ios012b_paper_positions.exit_rule_triggered IS
    'Which exit rule triggered the close: STOP_LOSS_ATR_2X, TAKE_PROFIT_1_25R, REGIME_EXIT, MANUAL';
COMMENT ON COLUMN fhq_alpha.ios012b_paper_positions.sentinel_monitored IS
    'Whether position is under Sentinel governance enforcement';

-- ============================================================================
-- PHASE 2: Deactivate OPTIONS-semantic exit rules
-- ============================================================================

-- Archive old rules for audit trail
UPDATE fhq_alpha.inversion_exit_rules
SET is_active = FALSE
WHERE rule_name IN ('TAKE_PROFIT_50PCT', 'STOP_LOSS_75PCT', 'TIME_DECAY_5DTE');

-- Add deprecation marker
ALTER TABLE fhq_alpha.inversion_exit_rules
ADD COLUMN IF NOT EXISTS deprecated_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS deprecated_by TEXT,
ADD COLUMN IF NOT EXISTS deprecation_reason TEXT,
ADD COLUMN IF NOT EXISTS semantic_type TEXT DEFAULT 'SPOT';

UPDATE fhq_alpha.inversion_exit_rules
SET deprecated_at = NOW(),
    deprecated_by = 'STIG',
    deprecation_reason = 'CEO-DIR-2026-107: OPTIONS-semantic rules replaced by SPOT-canonical framework',
    semantic_type = 'OPTIONS_DEPRECATED'
WHERE rule_name IN ('TAKE_PROFIT_50PCT', 'STOP_LOSS_75PCT', 'TIME_DECAY_5DTE');

-- ============================================================================
-- PHASE 3: Insert SPOT-canonical exit rules
-- ============================================================================

-- STOP_LOSS_ATR_2X: Volatility-adjusted stop loss
INSERT INTO fhq_alpha.inversion_exit_rules (
    rule_id, rule_name, rule_type, trigger_condition, trigger_value, action, priority, is_active, created_at
) VALUES (
    gen_random_uuid(),
    'STOP_LOSS_ATR_2X',
    'STOP_LOSS',
    'current_price <= canonical_stop_loss (LONG) OR current_price >= canonical_stop_loss (SHORT)',
    2.0,
    'CLOSE_POSITION',
    10,
    TRUE,
    NOW()
) ON CONFLICT DO NOTHING;

-- TAKE_PROFIT_1_25R: R-multiple take profit
INSERT INTO fhq_alpha.inversion_exit_rules (
    rule_id, rule_name, rule_type, trigger_condition, trigger_value, action, priority, is_active, created_at
) VALUES (
    gen_random_uuid(),
    'TAKE_PROFIT_1_25R',
    'TAKE_PROFIT',
    'current_price >= canonical_take_profit (LONG) OR current_price <= canonical_take_profit (SHORT)',
    1.25,
    'CLOSE_POSITION',
    20,
    TRUE,
    NOW()
) ON CONFLICT DO NOTHING;

-- Update REGIME_EXIT with SPOT semantic marker
UPDATE fhq_alpha.inversion_exit_rules
SET semantic_type = 'SPOT'
WHERE rule_name = 'REGIME_EXIT';

-- ============================================================================
-- PHASE 4: ATR Lookup Function (IoS-008 Canonical)
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_alpha.get_canonical_atr(
    p_ticker TEXT,
    p_date DATE DEFAULT CURRENT_DATE,
    p_period INTEGER DEFAULT 14
)
RETURNS NUMERIC
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_atr NUMERIC;
BEGIN
    -- Get ATR(14) from canonical indicator source
    -- Per CEO-DIR-2026-107 UPGRADE 1: ATR(14), daily timeframe
    SELECT indicator_value INTO v_atr
    FROM fhq_data.indicators
    WHERE canonical_id = p_ticker
      AND indicator_name = 'ATR'
      AND DATE(timestamp) <= p_date
    ORDER BY timestamp DESC
    LIMIT 1;

    -- If no ATR available, calculate from price data
    IF v_atr IS NULL THEN
        WITH price_data AS (
            SELECT
                high, low, close,
                LAG(close) OVER (ORDER BY timestamp) as prev_close
            FROM fhq_market.prices
            WHERE canonical_id = p_ticker
              AND DATE(timestamp) <= p_date
            ORDER BY timestamp DESC
            LIMIT p_period + 1
        ),
        true_ranges AS (
            SELECT GREATEST(
                high - low,
                ABS(high - COALESCE(prev_close, high)),
                ABS(low - COALESCE(prev_close, low))
            ) as tr
            FROM price_data
            WHERE prev_close IS NOT NULL
        )
        SELECT AVG(tr) INTO v_atr FROM true_ranges;
    END IF;

    RETURN COALESCE(v_atr, 0);
END;
$$;

COMMENT ON FUNCTION fhq_alpha.get_canonical_atr IS
    'CEO-DIR-2026-107 UPGRADE 1: Returns ATR(14) per IoS-008 Canonical Indicator Registry';

-- ============================================================================
-- PHASE 5: Canonical Exit Level Calculator
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_alpha.calculate_canonical_exit_levels(
    p_ticker TEXT,
    p_entry_price NUMERIC,
    p_direction TEXT,  -- 'UP' (LONG) or 'DOWN' (SHORT)
    p_entry_date DATE DEFAULT CURRENT_DATE,
    p_atr_multiplier NUMERIC DEFAULT 2.0,
    p_r_multiplier NUMERIC DEFAULT 1.25
)
RETURNS TABLE (
    canonical_stop_loss NUMERIC,
    canonical_take_profit NUMERIC,
    atr_at_entry NUMERIC,
    r_value NUMERIC
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_atr NUMERIC;
    v_stop_loss NUMERIC;
    v_take_profit NUMERIC;
    v_r NUMERIC;
BEGIN
    -- Get ATR(14) at entry
    v_atr := fhq_alpha.get_canonical_atr(p_ticker, p_entry_date);

    -- Calculate Stop Loss: 2.0x ATR from entry
    -- Per CEO-DIR-2026-107 §3.1
    IF p_direction = 'UP' THEN
        -- LONG position: SL below entry
        v_stop_loss := p_entry_price - (p_atr_multiplier * v_atr);
    ELSE
        -- SHORT position: SL above entry
        v_stop_loss := p_entry_price + (p_atr_multiplier * v_atr);
    END IF;

    -- Calculate R-value: |entry_price - canonical_stop_loss|
    -- Per CEO-DIR-2026-107 UPGRADE 2
    v_r := ABS(p_entry_price - v_stop_loss);

    -- Calculate Take Profit: 1.25R from entry
    -- Per CEO-DIR-2026-107 §3.2
    IF p_direction = 'UP' THEN
        -- LONG position: TP above entry
        v_take_profit := p_entry_price + (p_r_multiplier * v_r);
    ELSE
        -- SHORT position: TP below entry
        v_take_profit := p_entry_price - (p_r_multiplier * v_r);
    END IF;

    RETURN QUERY SELECT v_stop_loss, v_take_profit, v_atr, v_r;
END;
$$;

COMMENT ON FUNCTION fhq_alpha.calculate_canonical_exit_levels IS
    'CEO-DIR-2026-107: Calculates SPOT-canonical SL (2.0x ATR) and TP (1.25R) levels';

-- ============================================================================
-- PHASE 6: Sentinel Governance Enforcement Layer
-- ============================================================================

-- Sentinel is a GOVERNANCE component, not performance logic
-- Per CEO-DIR-2026-107 UPGRADE 3

CREATE TABLE IF NOT EXISTS fhq_alpha.exit_sentinel_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID NOT NULL REFERENCES fhq_alpha.ios012b_paper_positions(position_id),
    check_timestamp TIMESTAMPTZ DEFAULT NOW(),
    current_price NUMERIC NOT NULL,
    canonical_stop_loss NUMERIC NOT NULL,
    canonical_take_profit NUMERIC NOT NULL,
    sl_distance_pct NUMERIC,
    tp_distance_pct NUMERIC,
    exit_triggered BOOLEAN DEFAULT FALSE,
    exit_rule TEXT,
    sentinel_action TEXT,  -- 'MONITOR', 'ALERT', 'EXECUTE_EXIT'
    evidence_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE fhq_alpha.exit_sentinel_log IS
    'CEO-DIR-2026-107 UPGRADE 3: Governance enforcement layer for exit rule monitoring. NOT performance logic.';

CREATE INDEX IF NOT EXISTS idx_sentinel_position ON fhq_alpha.exit_sentinel_log(position_id);
CREATE INDEX IF NOT EXISTS idx_sentinel_timestamp ON fhq_alpha.exit_sentinel_log(check_timestamp);

-- Sentinel check function
CREATE OR REPLACE FUNCTION fhq_alpha.sentinel_check_position(
    p_position_id UUID
)
RETURNS TABLE (
    position_id UUID,
    ticker TEXT,
    direction TEXT,
    entry_price NUMERIC,
    current_price NUMERIC,
    canonical_stop_loss NUMERIC,
    canonical_take_profit NUMERIC,
    sl_hit BOOLEAN,
    tp_hit BOOLEAN,
    regime_exit BOOLEAN,
    exit_action TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_pos RECORD;
    v_current_price NUMERIC;
    v_current_regime TEXT;
    v_sl_hit BOOLEAN := FALSE;
    v_tp_hit BOOLEAN := FALSE;
    v_regime_exit BOOLEAN := FALSE;
    v_exit_action TEXT := 'HOLD';
BEGIN
    -- Get position
    SELECT * INTO v_pos
    FROM fhq_alpha.ios012b_paper_positions
    WHERE ios012b_paper_positions.position_id = p_position_id
      AND status = 'OPEN';

    IF NOT FOUND THEN
        RETURN;
    END IF;

    -- Get current price
    SELECT close INTO v_current_price
    FROM fhq_market.prices
    WHERE canonical_id = v_pos.ticker
    ORDER BY timestamp DESC
    LIMIT 1;

    -- Check Stop Loss
    IF v_pos.direction = 'UP' THEN
        -- LONG: SL hit if price <= SL
        v_sl_hit := v_current_price <= v_pos.canonical_stop_loss;
        -- TP hit if price >= TP
        v_tp_hit := v_current_price >= v_pos.canonical_take_profit;
    ELSE
        -- SHORT: SL hit if price >= SL
        v_sl_hit := v_current_price >= v_pos.canonical_stop_loss;
        -- TP hit if price <= TP
        v_tp_hit := v_current_price <= v_pos.canonical_take_profit;
    END IF;

    -- Check Regime Exit (STRESS regime must persist)
    SELECT regime INTO v_current_regime
    FROM fhq_research.regime_states
    WHERE asset_id = v_pos.ticker
    ORDER BY created_at DESC
    LIMIT 1;

    v_regime_exit := v_current_regime IS NOT NULL AND v_current_regime != 'STRESS';

    -- Determine action (priority order per rules)
    IF v_sl_hit THEN
        v_exit_action := 'EXIT_STOP_LOSS_ATR_2X';
    ELSIF v_tp_hit THEN
        v_exit_action := 'EXIT_TAKE_PROFIT_1_25R';
    ELSIF v_regime_exit THEN
        v_exit_action := 'EXIT_REGIME_CHANGE';
    END IF;

    -- Log the check
    INSERT INTO fhq_alpha.exit_sentinel_log (
        position_id, current_price, canonical_stop_loss, canonical_take_profit,
        sl_distance_pct, tp_distance_pct, exit_triggered, exit_rule, sentinel_action
    ) VALUES (
        p_position_id,
        v_current_price,
        v_pos.canonical_stop_loss,
        v_pos.canonical_take_profit,
        ((v_current_price - v_pos.canonical_stop_loss) / v_pos.entry_price) * 100,
        ((v_pos.canonical_take_profit - v_current_price) / v_pos.entry_price) * 100,
        v_sl_hit OR v_tp_hit OR v_regime_exit,
        CASE
            WHEN v_sl_hit THEN 'STOP_LOSS_ATR_2X'
            WHEN v_tp_hit THEN 'TAKE_PROFIT_1_25R'
            WHEN v_regime_exit THEN 'REGIME_EXIT'
            ELSE NULL
        END,
        v_exit_action
    );

    RETURN QUERY SELECT
        v_pos.position_id,
        v_pos.ticker,
        v_pos.direction,
        v_pos.entry_price,
        v_current_price,
        v_pos.canonical_stop_loss,
        v_pos.canonical_take_profit,
        v_sl_hit,
        v_tp_hit,
        v_regime_exit,
        v_exit_action;
END;
$$;

COMMENT ON FUNCTION fhq_alpha.sentinel_check_position IS
    'CEO-DIR-2026-107: Sentinel governance check for a single position. Deterministic, no signal generation access.';

-- Batch sentinel check for all open positions
CREATE OR REPLACE FUNCTION fhq_alpha.sentinel_check_all_open()
RETURNS TABLE (
    position_id UUID,
    ticker TEXT,
    exit_action TEXT,
    exit_triggered BOOLEAN
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_pos RECORD;
    v_result RECORD;
BEGIN
    FOR v_pos IN
        SELECT p.position_id
        FROM fhq_alpha.ios012b_paper_positions p
        WHERE p.status = 'OPEN' AND p.sentinel_monitored = TRUE
    LOOP
        SELECT * INTO v_result FROM fhq_alpha.sentinel_check_position(v_pos.position_id);
        IF v_result IS NOT NULL THEN
            RETURN QUERY SELECT
                v_result.position_id,
                v_result.ticker,
                v_result.exit_action,
                (v_result.sl_hit OR v_result.tp_hit OR v_result.regime_exit);
        END IF;
    END LOOP;
END;
$$;

COMMENT ON FUNCTION fhq_alpha.sentinel_check_all_open IS
    'CEO-DIR-2026-107: Batch sentinel governance check for all monitored positions.';

-- ============================================================================
-- PHASE 7: View for active SPOT-canonical rules
-- ============================================================================

CREATE OR REPLACE VIEW fhq_alpha.v_active_exit_rules AS
SELECT
    rule_id,
    rule_name,
    rule_type,
    trigger_condition,
    trigger_value,
    action,
    priority,
    semantic_type,
    created_at
FROM fhq_alpha.inversion_exit_rules
WHERE is_active = TRUE
  AND (semantic_type = 'SPOT' OR semantic_type IS NULL)
ORDER BY priority;

COMMENT ON VIEW fhq_alpha.v_active_exit_rules IS
    'CEO-DIR-2026-107: Active SPOT-canonical exit rules only';

-- ============================================================================
-- PHASE 8: Governance evidence
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale
) VALUES (
    gen_random_uuid(),
    'MIGRATION_EXECUTE',
    'CEO-DIR-2026-107',
    'EXIT_FRAMEWORK_CANONICAL',
    'STIG',
    NOW(),
    'APPROVED',
    'Migration 316: SPOT-canonical exit framework. Replaced OPTIONS-semantic rules (entry_premium, max_profit, DTE) with ATR-based SL (2.0x ATR(14)) and R-multiple TP (1.25R). Sentinel daemon created as governance enforcement layer.'
);

COMMIT;

-- ============================================================================
-- POST-MIGRATION VERIFICATION QUERIES
-- ============================================================================

-- Verify new rules are active
-- SELECT * FROM fhq_alpha.v_active_exit_rules;

-- Verify deprecated rules
-- SELECT rule_name, is_active, deprecated_at, deprecation_reason
-- FROM fhq_alpha.inversion_exit_rules
-- WHERE semantic_type = 'OPTIONS_DEPRECATED';

-- Test exit level calculation
-- SELECT * FROM fhq_alpha.calculate_canonical_exit_levels('PGR', 202.37, 'UP');
