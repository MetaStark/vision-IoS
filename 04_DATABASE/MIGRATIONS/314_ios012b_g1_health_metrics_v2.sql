-- Migration 314: IoS-012-B G1 Health Metrics V2 (P&L Semantics)
-- Directive: CEO-DIR-2026-106 G1 Addendum
-- Date: 2026-01-19
-- Author: STIG
-- Purpose: Address CEO G1 prerequisites - P&L-weighted health metrics
--
-- CEO FEEDBACK (2026-01-19):
-- "Options spreads require P&L-weighted health, not signal hit-rate alone."
--
-- This migration implements dual-layer health monitoring:
-- Layer 1: Directional Health (Signal Quality) - threshold 80%
-- Layer 2: P&L Health (Execution Quality) - threshold 0% (breakeven)
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Drop old health check function
-- ============================================================================

DROP FUNCTION IF EXISTS fhq_alpha.check_inversion_health(INTEGER);

-- ============================================================================
-- SECTION 2: Create V2 Health Check with P&L Semantics
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_alpha.check_inversion_health_v2(
    p_lookback_days INTEGER DEFAULT 30
) RETURNS TABLE (
    directional_health NUMERIC,
    pnl_health NUMERIC,
    total_signals INTEGER,
    closed_positions INTEGER,
    total_premium_at_risk NUMERIC,
    total_pnl NUMERIC,
    health_status TEXT,
    should_disable BOOLEAN,
    disable_reason TEXT,
    recommendation TEXT
) AS $$
DECLARE
    v_dir_health NUMERIC;
    v_pnl_health NUMERIC;
    v_signals INTEGER;
    v_closed INTEGER;
    v_premium NUMERIC;
    v_total_pnl NUMERIC;
BEGIN
    -- Calculate directional health (signal quality)
    SELECT
        COALESCE(SUM(CASE WHEN actual_outcome THEN 1 ELSE 0 END)::NUMERIC /
                 NULLIF(COUNT(CASE WHEN actual_outcome IS NOT NULL THEN 1 END), 0), 0)
    INTO v_dir_health
    FROM fhq_alpha.inversion_overlay_shadow
    WHERE entry_timestamp >= NOW() - (p_lookback_days || ' days')::INTERVAL
      AND actual_outcome IS NOT NULL;

    -- Calculate P&L health (execution quality)
    SELECT
        COUNT(*),
        COUNT(CASE WHEN exit_pnl IS NOT NULL THEN 1 END),
        COALESCE(SUM(net_premium_paid), 0),
        COALESCE(SUM(exit_pnl), 0)
    INTO v_signals, v_closed, v_premium, v_total_pnl
    FROM fhq_alpha.inversion_overlay_shadow
    WHERE entry_timestamp >= NOW() - (p_lookback_days || ' days')::INTERVAL;

    -- Calculate P&L health ratio
    v_pnl_health := CASE
        WHEN v_premium > 0 THEN v_total_pnl / v_premium
        ELSE 0
    END;

    -- Log health metric
    INSERT INTO fhq_governance.inversion_health_metrics (
        lookback_days,
        total_signals,
        inverted_hits,
        inverted_hit_rate,
        avg_inverted_brier,
        health_status,
        auto_disabled,
        disabled_reason
    ) VALUES (
        p_lookback_days,
        v_signals,
        COALESCE((SELECT SUM(CASE WHEN actual_outcome THEN 1 ELSE 0 END)
                  FROM fhq_alpha.inversion_overlay_shadow
                  WHERE entry_timestamp >= NOW() - (p_lookback_days || ' days')::INTERVAL
                    AND actual_outcome IS NOT NULL), 0),
        v_dir_health,
        COALESCE((SELECT AVG(inverted_brier)
                  FROM fhq_alpha.inversion_overlay_shadow
                  WHERE entry_timestamp >= NOW() - (p_lookback_days || ' days')::INTERVAL
                    AND inverted_brier IS NOT NULL), 0),
        CASE
            WHEN v_closed < 10 THEN 'INSUFFICIENT_DATA'
            WHEN v_dir_health < 0.80 THEN 'SIGNAL_DEGRADED'
            WHEN v_pnl_health < 0 THEN 'EXECUTION_DEGRADED'
            ELSE 'HEALTHY'
        END,
        v_pnl_health < 0 AND v_closed >= 10,
        CASE
            WHEN v_pnl_health < 0 AND v_closed >= 10 THEN 'P&L negative over lookback period'
            ELSE NULL
        END
    );

    -- Return comprehensive health report
    RETURN QUERY
    SELECT
        v_dir_health,
        v_pnl_health,
        v_signals,
        v_closed,
        v_premium,
        v_total_pnl,
        CASE
            WHEN v_closed < 10 THEN 'INSUFFICIENT_DATA'::TEXT
            WHEN v_dir_health < 0.80 THEN 'SIGNAL_DEGRADED'::TEXT
            WHEN v_pnl_health < 0 THEN 'EXECUTION_DEGRADED'::TEXT
            ELSE 'HEALTHY'::TEXT
        END,
        v_pnl_health < 0 AND v_closed >= 10,  -- Auto-disable on P&L breach ONLY
        CASE
            WHEN v_pnl_health < 0 AND v_closed >= 10 THEN 'P&L_BREACH: Total P&L negative'::TEXT
            WHEN v_dir_health < 0.80 AND v_closed >= 10 THEN 'SIGNAL_DEGRADED: Directional accuracy below 80%'::TEXT
            ELSE NULL::TEXT
        END,
        CASE
            WHEN v_closed < 10 THEN 'Need minimum 10 closed positions for health assessment'::TEXT
            WHEN v_pnl_health < 0 AND v_closed >= 10 THEN 'AUTO-DISABLE TRIGGERED: P&L negative over lookback period. Manual review required.'::TEXT
            WHEN v_dir_health < 0.80 AND v_closed >= 10 THEN 'WARNING: Directional accuracy degraded but P&L positive. Continue with caution.'::TEXT
            ELSE 'Module performing within parameters. Directional: ' || ROUND(v_dir_health * 100, 1) || '%, P&L: ' || ROUND(v_pnl_health * 100, 1) || '%'::TEXT
        END;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 3: Add P&L tracking columns to health metrics table
-- ============================================================================

ALTER TABLE fhq_governance.inversion_health_metrics
ADD COLUMN IF NOT EXISTS pnl_health NUMERIC,
ADD COLUMN IF NOT EXISTS total_premium_at_risk NUMERIC,
ADD COLUMN IF NOT EXISTS total_pnl NUMERIC,
ADD COLUMN IF NOT EXISTS closed_positions INTEGER,
ADD COLUMN IF NOT EXISTS disabled_reason TEXT;

-- ============================================================================
-- SECTION 4: Create Regime Transition Tracking Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.inversion_regime_transitions (
    transition_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Regime change details
    previous_regime TEXT NOT NULL,
    new_regime TEXT NOT NULL,
    transition_detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Timing
    regime_update_timestamp TIMESTAMPTZ NOT NULL,
    next_market_open TIMESTAMPTZ,
    exit_window_start TIMESTAMPTZ,
    exit_window_end TIMESTAMPTZ,

    -- Affected positions
    positions_to_exit INTEGER DEFAULT 0,
    positions_exited INTEGER DEFAULT 0,

    -- Status
    status TEXT DEFAULT 'PENDING_EXIT',  -- PENDING_EXIT, EXITED, CANCELLED
    completed_at TIMESTAMPTZ,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- SECTION 5: Create Exit Window Configuration
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.inversion_timing_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_key TEXT UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert timing configuration (FROZEN per G1 addendum)
INSERT INTO fhq_alpha.inversion_timing_config (config_key, config_value, description)
VALUES
    ('REGIME_UPDATE_TIME_UTC', '22:05', 'IoS-003 regime update time (after market close)'),
    ('EXECUTION_CHECK_TIME_UTC', '22:30', 'IoS-012-B execution check time'),
    ('MARKET_OPEN_ET', '09:30', 'US equity market open (Eastern Time)'),
    ('MARKET_CLOSE_ET', '16:00', 'US equity market close (Eastern Time)'),
    ('EXIT_WINDOW_BUFFER_MINUTES', '30', 'Minutes after market open for regime change exit'),
    ('REGIME_GRANULARITY', 'DAILY', 'Regime update frequency (no intraday updates)')
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    updated_at = NOW();

-- ============================================================================
-- SECTION 6: Log G1 Addendum Completion
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
    'G1_PREREQUISITE_ADDRESSED',
    'IoS-012-B',
    'SYNTHETIC_INVERSION_MODULE',
    'STIG',
    NOW(),
    'ADDRESSED',
    'CEO G1 Prerequisites addressed: (1) Formal Inverted Brier Score definition with methodology freeze, (2) Dual-layer health metrics with P&L semantics - auto-disable on P&L breach only, (3) Regime transition timing with time-anchored exit windows.'
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- SELECT * FROM fhq_alpha.check_inversion_health_v2(30);
-- SELECT * FROM fhq_alpha.inversion_timing_config;
