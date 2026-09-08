-- Migration 313: IoS-012-B Synthetic Inversion Module Infrastructure
-- Directive: CEO-DIR-2026-105 (Hindsight Firewall Compliance)
-- Date: 2026-01-19
-- Author: STIG
-- Status: G0 SUBMITTED - Shadow Mode Only until 2026-02-02
--
-- PURPOSE:
-- Create infrastructure for IoS-012-B (Synthetic Inversion Module) which converts
-- systematic STRESS@99%+ miscalibration into alpha via Vertical Bull Call Spreads.
--
-- GOVERNANCE CONSTRAINT:
-- This module operates in SHADOW MODE ONLY until the Hindsight Firewall's
-- Non-Eligibility Clause expires (2026-02-02 = 2 learning cycles).
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Create Schema for Alpha Operations (if not exists)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS fhq_alpha;

COMMENT ON SCHEMA fhq_alpha IS
'Schema for alpha generation strategies. IoS-012-B operates here in shadow mode.';

-- ============================================================================
-- SECTION 2: Canonical Inversion Universe Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.inversion_universe (
    ticker TEXT PRIMARY KEY,
    asset_class TEXT NOT NULL DEFAULT 'EQUITY',
    sector TEXT,

    -- Evidence from CEO-DIR-2026-105
    signal_count INTEGER NOT NULL,
    hit_rate NUMERIC NOT NULL,
    mean_confidence NUMERIC NOT NULL,
    inverted_brier NUMERIC NOT NULL,

    -- Status
    canonical_status TEXT NOT NULL DEFAULT 'G4_CANONICALIZED',
    added_date DATE NOT NULL DEFAULT CURRENT_DATE,
    directive_reference TEXT NOT NULL,

    -- Options eligibility
    options_eligible BOOLEAN DEFAULT TRUE,
    min_liquidity_score NUMERIC DEFAULT 0.7,

    -- Constraints
    CONSTRAINT valid_hit_rate CHECK (hit_rate >= 0 AND hit_rate <= 1),
    CONSTRAINT valid_confidence CHECK (mean_confidence >= 0 AND mean_confidence <= 1)
);

-- Insert canonical inversion universe (10 equity tickers from CEO-DIR-2026-105)
INSERT INTO fhq_alpha.inversion_universe (
    ticker, asset_class, sector, signal_count, hit_rate, mean_confidence,
    inverted_brier, canonical_status, directive_reference
) VALUES
    ('ADBE', 'EQUITY', 'Technology', 3, 0.00, 0.9971, 0.0058, 'G4_CANONICALIZED', 'CEO-DIR-2026-078'),
    ('ADSK', 'EQUITY', 'Technology', 3, 0.00, 0.9971, 0.0058, 'G4_CANONICALIZED', 'CEO-DIR-2026-078'),
    ('AIG', 'EQUITY', 'Financials', 3, 0.00, 0.9971, 0.0058, 'G4_CANONICALIZED', 'CEO-DIR-2026-078'),
    ('AZO', 'EQUITY', 'Consumer', 4, 0.00, 0.9971, 0.0058, 'G4_CANONICALIZED', 'CEO-DIR-2026-078'),
    ('GIS', 'EQUITY', 'Consumer', 3, 0.00, 0.9971, 0.0058, 'G4_CANONICALIZED', 'CEO-DIR-2026-078'),
    ('HNR1.DE', 'EQUITY', 'Industrial', 3, 0.00, 0.9971, 0.0058, 'G4_CANONICALIZED', 'CEO-DIR-2026-078'),
    ('INTU', 'EQUITY', 'Technology', 4, 0.00, 0.9971, 0.0058, 'G4_CANONICALIZED', 'CEO-DIR-2026-078'),
    ('LEN', 'EQUITY', 'Real Estate', 3, 0.00, 0.9971, 0.0058, 'G4_CANONICALIZED', 'CEO-DIR-2026-078'),
    ('NOW', 'EQUITY', 'Technology', 3, 0.00, 0.9971, 0.0058, 'G4_CANONICALIZED', 'CEO-DIR-2026-078'),
    ('PGR', 'EQUITY', 'Financials', 3, 0.00, 0.9971, 0.0058, 'G4_CANONICALIZED', 'CEO-DIR-2026-078')
ON CONFLICT (ticker) DO UPDATE SET
    signal_count = EXCLUDED.signal_count,
    hit_rate = EXCLUDED.hit_rate,
    directive_reference = EXCLUDED.directive_reference;

-- ============================================================================
-- SECTION 3: Inversion Overlay Shadow Tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.inversion_overlay_shadow (
    overlay_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Signal reference
    source_signal_id UUID,
    source_regime TEXT NOT NULL,
    source_confidence NUMERIC NOT NULL,
    source_direction TEXT NOT NULL,  -- Original predicted direction

    -- Inversion details
    inverted_direction TEXT NOT NULL,  -- Opposite of source
    inversion_trigger TEXT NOT NULL DEFAULT 'STRESS_99PCT_EQUITY',

    -- Asset info
    ticker TEXT NOT NULL REFERENCES fhq_alpha.inversion_universe(ticker),

    -- Options strategy details (Vertical Bull Call Spread)
    strategy_type TEXT NOT NULL DEFAULT 'VERTICAL_BULL_CALL_SPREAD',
    long_strike NUMERIC,
    short_strike NUMERIC,
    expiration_date DATE,
    dte_at_entry INTEGER,

    -- Position sizing
    nav_at_entry NUMERIC,
    position_size_pct NUMERIC DEFAULT 0.025,  -- 2.5% NAV
    contracts INTEGER,
    net_premium_paid NUMERIC,
    max_profit NUMERIC,
    max_loss NUMERIC,

    -- Entry details
    entry_timestamp TIMESTAMPTZ DEFAULT NOW(),
    entry_price_underlying NUMERIC,
    entry_iv NUMERIC,

    -- Exit details (filled when closed)
    exit_timestamp TIMESTAMPTZ,
    exit_price_underlying NUMERIC,
    exit_type TEXT,  -- 'TAKE_PROFIT', 'STOP_LOSS', 'TIME_DECAY', 'REGIME_CHANGE'
    exit_pnl NUMERIC,
    exit_pnl_pct NUMERIC,

    -- Performance tracking
    actual_outcome BOOLEAN,  -- Did market go in inverted direction?
    outcome_timestamp TIMESTAMPTZ,
    inverted_brier NUMERIC,

    -- Shadow mode flag
    is_shadow BOOLEAN DEFAULT TRUE,
    shadow_session_id UUID,

    -- Governance
    created_at TIMESTAMPTZ DEFAULT NOW(),
    evaluated_at TIMESTAMPTZ,
    evidence_hash TEXT,

    -- Constraints
    CONSTRAINT valid_position_size CHECK (position_size_pct > 0 AND position_size_pct <= 0.10),
    CONSTRAINT valid_strikes CHECK (short_strike IS NULL OR short_strike > long_strike)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_inversion_overlay_ticker
ON fhq_alpha.inversion_overlay_shadow(ticker);

CREATE INDEX IF NOT EXISTS idx_inversion_overlay_shadow_session
ON fhq_alpha.inversion_overlay_shadow(shadow_session_id);

CREATE INDEX IF NOT EXISTS idx_inversion_overlay_entry_date
ON fhq_alpha.inversion_overlay_shadow(entry_timestamp);

CREATE INDEX IF NOT EXISTS idx_inversion_overlay_exit_pending
ON fhq_alpha.inversion_overlay_shadow(exit_timestamp)
WHERE exit_timestamp IS NULL;

-- ============================================================================
-- SECTION 4: Inversion Health Monitoring
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.inversion_health_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    lookback_days INTEGER NOT NULL DEFAULT 30,

    -- Performance metrics
    total_signals INTEGER NOT NULL,
    inverted_hits INTEGER NOT NULL,
    inverted_hit_rate NUMERIC NOT NULL,
    avg_inverted_brier NUMERIC NOT NULL,

    -- Health status
    health_status TEXT NOT NULL,  -- 'HEALTHY', 'DEGRADED', 'DISABLED'
    threshold_inverted_hit_rate NUMERIC DEFAULT 0.80,

    -- Auto-disable tracking
    auto_disabled BOOLEAN DEFAULT FALSE,
    disabled_at TIMESTAMPTZ,
    disabled_reason TEXT,

    -- Governance
    evidence_hash TEXT,

    -- Constraints
    CONSTRAINT valid_hit_rate CHECK (inverted_hit_rate >= 0 AND inverted_hit_rate <= 1)
);

-- ============================================================================
-- SECTION 5: Exit Rules Configuration
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.inversion_exit_rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name TEXT UNIQUE NOT NULL,
    rule_type TEXT NOT NULL,  -- 'TAKE_PROFIT', 'STOP_LOSS', 'TIME_DECAY', 'REGIME_CHANGE'

    -- Trigger conditions
    trigger_condition TEXT NOT NULL,
    trigger_value NUMERIC,

    -- Action
    action TEXT NOT NULL DEFAULT 'CLOSE_POSITION',
    priority INTEGER DEFAULT 100,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default exit rules per CEO blueprint
INSERT INTO fhq_alpha.inversion_exit_rules (rule_name, rule_type, trigger_condition, trigger_value, priority)
VALUES
    ('TAKE_PROFIT_50PCT', 'TAKE_PROFIT', 'current_pnl >= 0.50 * max_profit', 0.50, 10),
    ('STOP_LOSS_75PCT', 'STOP_LOSS', 'current_value <= 0.25 * entry_premium', 0.25, 20),
    ('TIME_DECAY_5DTE', 'TIME_DECAY', 'days_to_expiration <= 5', 5, 30),
    ('REGIME_EXIT', 'REGIME_CHANGE', 'current_regime != STRESS', NULL, 40)
ON CONFLICT (rule_name) DO NOTHING;

-- ============================================================================
-- SECTION 6: Hindsight Firewall Compliance Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_alpha.inversion_hindsight_compliance (
    compliance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    checked_at TIMESTAMPTZ DEFAULT NOW(),

    -- Module status
    module_name TEXT NOT NULL DEFAULT 'IoS-012-B',
    mode TEXT NOT NULL DEFAULT 'SHADOW_ONLY',

    -- Non-eligibility tracking
    non_eligibility_start DATE NOT NULL DEFAULT '2026-01-19',
    non_eligibility_end DATE NOT NULL DEFAULT '2026-02-02',
    learning_cycles_required INTEGER DEFAULT 2,
    learning_cycles_completed INTEGER DEFAULT 0,

    -- Compliance checks
    is_retrospective BOOLEAN DEFAULT TRUE,
    retrospective_data_used BOOLEAN DEFAULT FALSE,
    contamination_detected BOOLEAN DEFAULT FALSE,

    -- Prohibited actions check
    model_selection_attempted BOOLEAN DEFAULT FALSE,
    parameter_adjustment_attempted BOOLEAN DEFAULT FALSE,
    retraining_attempted BOOLEAN DEFAULT FALSE,
    decision_damping_attempted BOOLEAN DEFAULT FALSE,

    -- Verdict
    compliance_status TEXT NOT NULL DEFAULT 'COMPLIANT',
    violation_details TEXT,

    -- Governance
    verified_by TEXT DEFAULT 'VEGA',
    evidence_hash TEXT
);

-- Insert initial compliance record
INSERT INTO fhq_alpha.inversion_hindsight_compliance (
    module_name, mode, compliance_status
) VALUES (
    'IoS-012-B', 'SHADOW_ONLY', 'COMPLIANT'
);

-- ============================================================================
-- SECTION 7: Performance View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_alpha.v_inversion_overlay_performance AS
SELECT
    ticker,
    COUNT(*) as total_positions,

    -- Entry stats
    ROUND(AVG(position_size_pct)::numeric, 4) as avg_position_size,
    ROUND(AVG(net_premium_paid)::numeric, 2) as avg_premium_paid,

    -- Exit stats
    COUNT(CASE WHEN exit_type = 'TAKE_PROFIT' THEN 1 END) as take_profit_count,
    COUNT(CASE WHEN exit_type = 'STOP_LOSS' THEN 1 END) as stop_loss_count,
    COUNT(CASE WHEN exit_type = 'TIME_DECAY' THEN 1 END) as time_decay_count,
    COUNT(CASE WHEN exit_type = 'REGIME_CHANGE' THEN 1 END) as regime_change_count,

    -- P&L
    ROUND(SUM(exit_pnl)::numeric, 2) as total_pnl,
    ROUND(AVG(exit_pnl_pct)::numeric, 4) as avg_pnl_pct,

    -- Hit rate on direction
    ROUND(100.0 * SUM(CASE WHEN actual_outcome THEN 1 ELSE 0 END) /
          NULLIF(COUNT(CASE WHEN actual_outcome IS NOT NULL THEN 1 END), 0)::numeric, 2) as inverted_hit_rate_pct,

    -- Brier
    ROUND(AVG(inverted_brier)::numeric, 4) as avg_inverted_brier,

    -- Shadow mode indicator
    bool_and(is_shadow) as all_shadow

FROM fhq_alpha.inversion_overlay_shadow
GROUP BY ticker;

-- ============================================================================
-- SECTION 8: System-Level Performance View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_alpha.v_inversion_overlay_system_performance AS
SELECT
    COUNT(*) as total_signals,

    -- Direction accuracy
    SUM(CASE WHEN actual_outcome THEN 1 ELSE 0 END) as correct_directions,
    ROUND(100.0 * SUM(CASE WHEN actual_outcome THEN 1 ELSE 0 END) /
          NULLIF(COUNT(CASE WHEN actual_outcome IS NOT NULL THEN 1 END), 0)::numeric, 2) as inverted_hit_rate_pct,

    -- Brier performance
    ROUND(AVG(inverted_brier)::numeric, 4) as avg_inverted_brier,

    -- P&L summary
    SUM(exit_pnl) as total_pnl,
    ROUND(AVG(exit_pnl_pct)::numeric, 4) as avg_pnl_pct,

    -- Exit breakdown
    ROUND(100.0 * COUNT(CASE WHEN exit_type = 'TAKE_PROFIT' THEN 1 END) /
          NULLIF(COUNT(CASE WHEN exit_type IS NOT NULL THEN 1 END), 0)::numeric, 2) as take_profit_pct,
    ROUND(100.0 * COUNT(CASE WHEN exit_type = 'STOP_LOSS' THEN 1 END) /
          NULLIF(COUNT(CASE WHEN exit_type IS NOT NULL THEN 1 END), 0)::numeric, 2) as stop_loss_pct,

    -- Health check
    CASE
        WHEN COUNT(CASE WHEN actual_outcome IS NOT NULL THEN 1 END) = 0 THEN 'INSUFFICIENT_DATA'
        WHEN 100.0 * SUM(CASE WHEN actual_outcome THEN 1 ELSE 0 END) /
             COUNT(CASE WHEN actual_outcome IS NOT NULL THEN 1 END) >= 80 THEN 'HEALTHY'
        ELSE 'DEGRADED'
    END as health_status,

    -- Shadow mode
    bool_and(is_shadow) as all_shadow,

    -- Time range
    MIN(entry_timestamp) as first_signal,
    MAX(entry_timestamp) as last_signal

FROM fhq_alpha.inversion_overlay_shadow;

-- ============================================================================
-- SECTION 9: Health Check Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_alpha.check_inversion_health(
    p_lookback_days INTEGER DEFAULT 30
) RETURNS TABLE (
    health_status TEXT,
    inverted_hit_rate NUMERIC,
    total_signals INTEGER,
    threshold NUMERIC,
    should_disable BOOLEAN,
    recommendation TEXT
) AS $$
DECLARE
    v_hit_rate NUMERIC;
    v_signals INTEGER;
    v_threshold NUMERIC := 0.80;
BEGIN
    -- Calculate inverted hit rate for lookback period
    SELECT
        COALESCE(SUM(CASE WHEN actual_outcome THEN 1 ELSE 0 END)::NUMERIC /
                 NULLIF(COUNT(CASE WHEN actual_outcome IS NOT NULL THEN 1 END), 0), 0),
        COUNT(*)
    INTO v_hit_rate, v_signals
    FROM fhq_alpha.inversion_overlay_shadow
    WHERE entry_timestamp >= NOW() - (p_lookback_days || ' days')::INTERVAL
      AND actual_outcome IS NOT NULL;

    -- Log health metric
    INSERT INTO fhq_governance.inversion_health_metrics (
        lookback_days,
        total_signals,
        inverted_hits,
        inverted_hit_rate,
        avg_inverted_brier,
        health_status,
        auto_disabled
    )
    SELECT
        p_lookback_days,
        v_signals,
        COALESCE(SUM(CASE WHEN actual_outcome THEN 1 ELSE 0 END), 0),
        v_hit_rate,
        COALESCE(AVG(inverted_brier), 0),
        CASE
            WHEN v_signals < 10 THEN 'INSUFFICIENT_DATA'
            WHEN v_hit_rate >= v_threshold THEN 'HEALTHY'
            ELSE 'DEGRADED'
        END,
        v_hit_rate < v_threshold AND v_signals >= 10
    FROM fhq_alpha.inversion_overlay_shadow
    WHERE entry_timestamp >= NOW() - (p_lookback_days || ' days')::INTERVAL;

    -- Return results
    RETURN QUERY
    SELECT
        CASE
            WHEN v_signals < 10 THEN 'INSUFFICIENT_DATA'::TEXT
            WHEN v_hit_rate >= v_threshold THEN 'HEALTHY'::TEXT
            ELSE 'DEGRADED'::TEXT
        END,
        v_hit_rate,
        v_signals,
        v_threshold,
        v_hit_rate < v_threshold AND v_signals >= 10,
        CASE
            WHEN v_signals < 10 THEN 'Need minimum 10 signals for health assessment'::TEXT
            WHEN v_hit_rate >= v_threshold THEN 'Inversion strategy performing as expected'::TEXT
            ELSE 'WARNING: Inverted hit rate below threshold - recommend manual review'::TEXT
        END;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 10: Register IoS-012-B in IoS Registry
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
    'IOS_MODULE_REGISTERED',
    'IoS-012-B',
    'SYNTHETIC_INVERSION_MODULE',
    'STIG',
    NOW(),
    'G0_SUBMITTED',
    'CEO-DIR-2026-105: IoS-012-B Synthetic Inversion Module registered. Converts STRESS@99%+ miscalibration into alpha via Vertical Bull Call Spreads. SHADOW MODE ONLY until 2026-02-02 per Hindsight Firewall Non-Eligibility Clause.'
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check inversion universe
-- SELECT * FROM fhq_alpha.inversion_universe;

-- Check exit rules
-- SELECT * FROM fhq_alpha.inversion_exit_rules;

-- Check hindsight compliance
-- SELECT * FROM fhq_alpha.inversion_hindsight_compliance;

-- Check governance log
-- SELECT * FROM fhq_governance.governance_actions_log
-- WHERE action_target = 'IoS-012-B' ORDER BY initiated_at DESC;
