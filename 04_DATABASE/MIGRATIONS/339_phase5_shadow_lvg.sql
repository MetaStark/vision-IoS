-- Migration 339: Phase V Shadow Mode + Learning Velocity Governor
-- CEO-DIR-2026-HYPOTHESIS-ECONOMY-001 Phase V
-- Author: STIG (EC-003)
-- Date: 2026-01-24
--
-- CEO DIRECTIVE:
--   Phase V = Eligibility logic, NOT execution
--   Phase V-A = Learning Velocity Governor (prevent runaway learning)
--   EC-022 = FROZEN until IoS-010 Bridge + 30 market days
--
-- ALLOWED: Eligibility scoring, kill-switch, simulation, options evaluation
-- FORBIDDEN: Live capital, leverage automation, EC-022 dependency

-- ============================================
-- PHASE V: AUTONOMOUS EXECUTION ELIGIBILITY (SHADOW ONLY)
-- "Rehearse adulthood without real consequences"
-- ============================================

-- 1. Execution Eligibility Registry
CREATE TABLE IF NOT EXISTS fhq_learning.execution_eligibility_registry (
    eligibility_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    eligibility_code TEXT UNIQUE NOT NULL,

    -- What we're evaluating
    hypothesis_id UUID REFERENCES fhq_learning.hypothesis_canon(canon_id),
    signal_id UUID,
    asset_symbol TEXT,

    -- Eligibility Criteria Scores
    tier_status TEXT,  -- Must have passed Tier 2 or 3
    confidence_score NUMERIC(4,3),
    regime_alignment_score NUMERIC(4,3),
    risk_adjusted_score NUMERIC(4,3),
    drawdown_resilience_score NUMERIC(4,3),

    -- Composite Eligibility (0-100)
    eligibility_score NUMERIC(5,2) GENERATED ALWAYS AS (
        (COALESCE(confidence_score, 0) * 25 +
         COALESCE(regime_alignment_score, 0) * 25 +
         COALESCE(risk_adjusted_score, 0) * 25 +
         COALESCE(drawdown_resilience_score, 0) * 25)
    ) STORED,

    -- Eligibility Status
    is_eligible BOOLEAN DEFAULT FALSE,
    eligibility_reason TEXT,

    -- SHADOW MODE ENFORCEMENT
    execution_mode TEXT DEFAULT 'SHADOW',
    live_capital_blocked BOOLEAN DEFAULT TRUE,
    leverage_blocked BOOLEAN DEFAULT TRUE,
    ec022_dependency_blocked BOOLEAN DEFAULT TRUE,

    -- Timestamps
    evaluated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '24 hours',
    created_by TEXT DEFAULT 'STIG',

    -- HARD CONSTRAINTS (Phase V Shadow)
    CONSTRAINT chk_shadow_mode CHECK (execution_mode = 'SHADOW'),
    CONSTRAINT chk_no_live_capital CHECK (live_capital_blocked = TRUE),
    CONSTRAINT chk_no_leverage CHECK (leverage_blocked = TRUE),
    CONSTRAINT chk_no_ec022 CHECK (ec022_dependency_blocked = TRUE)
);

CREATE INDEX IF NOT EXISTS idx_elig_hypothesis ON fhq_learning.execution_eligibility_registry(hypothesis_id);
CREATE INDEX IF NOT EXISTS idx_elig_score ON fhq_learning.execution_eligibility_registry(eligibility_score DESC);

-- 2. Kill-Switch Registry
CREATE TABLE IF NOT EXISTS fhq_learning.killswitch_registry (
    killswitch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    killswitch_code TEXT UNIQUE NOT NULL,
    killswitch_name TEXT NOT NULL,

    -- Trigger Conditions
    trigger_type TEXT NOT NULL,  -- 'THRESHOLD', 'MANUAL', 'REGIME_BREACH', 'VELOCITY_SPIKE'
    trigger_condition JSONB NOT NULL,
    trigger_threshold NUMERIC,

    -- Current State
    is_armed BOOLEAN DEFAULT TRUE,
    is_triggered BOOLEAN DEFAULT FALSE,
    triggered_at TIMESTAMPTZ,
    triggered_by TEXT,
    trigger_reason TEXT,

    -- Scope
    scope TEXT DEFAULT 'GLOBAL',  -- 'GLOBAL', 'ASSET', 'HYPOTHESIS', 'TIER'
    scope_target TEXT,

    -- Auto-Recovery
    auto_reset BOOLEAN DEFAULT FALSE,
    reset_after_hours INT,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'STIG',

    CONSTRAINT chk_trigger_type CHECK (trigger_type IN ('THRESHOLD', 'MANUAL', 'REGIME_BREACH', 'VELOCITY_SPIKE', 'DRAWDOWN', 'CORRELATION_BREAK'))
);

-- Insert default kill-switches
INSERT INTO fhq_learning.killswitch_registry (killswitch_code, killswitch_name, trigger_type, trigger_condition, trigger_threshold, scope) VALUES
    ('KS-GLOBAL-001', 'Global Emergency Halt', 'MANUAL', '{"requires": "CEO_APPROVAL"}', NULL, 'GLOBAL'),
    ('KS-DRAWDOWN-001', 'Drawdown Limit', 'DRAWDOWN', '{"max_drawdown_pct": 5}', 5.0, 'GLOBAL'),
    ('KS-VELOCITY-001', 'Learning Velocity Spike', 'VELOCITY_SPIKE', '{"max_hypotheses_per_day": 50}', 50, 'GLOBAL'),
    ('KS-REGIME-001', 'Regime Breach Halt', 'REGIME_BREACH', '{"confidence_below": 0.5}', 0.5, 'GLOBAL'),
    ('KS-CORRELATION-001', 'Correlation Break', 'CORRELATION_BREAK', '{"expected_vs_actual_delta": 0.3}', 0.3, 'GLOBAL')
ON CONFLICT (killswitch_code) DO NOTHING;

-- 3. Capital-at-Risk Simulation Ledger (PAPER ONLY)
CREATE TABLE IF NOT EXISTS fhq_learning.capital_simulation_ledger (
    simulation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    simulation_code TEXT UNIQUE NOT NULL,

    -- Simulated Position
    hypothesis_id UUID REFERENCES fhq_learning.hypothesis_canon(canon_id),
    asset_symbol TEXT NOT NULL,
    simulated_direction TEXT NOT NULL,  -- 'LONG', 'SHORT'
    simulated_size NUMERIC(12,2) NOT NULL,
    simulated_entry_price NUMERIC(14,6),
    simulated_entry_time TIMESTAMPTZ DEFAULT NOW(),

    -- Risk Parameters
    simulated_stop_loss NUMERIC(14,6),
    simulated_take_profit NUMERIC(14,6),
    max_loss_amount NUMERIC(12,2),
    position_risk_pct NUMERIC(4,2),

    -- Outcome (when closed)
    simulated_exit_price NUMERIC(14,6),
    simulated_exit_time TIMESTAMPTZ,
    simulated_pnl NUMERIC(12,2),
    simulated_pnl_pct NUMERIC(6,3),

    -- Status
    status TEXT DEFAULT 'OPEN',  -- 'OPEN', 'CLOSED', 'STOPPED', 'TARGET_HIT'

    -- PAPER MODE ENFORCEMENT
    is_paper_only BOOLEAN DEFAULT TRUE,
    real_capital_used NUMERIC(12,2) DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'STIG',

    -- HARD CONSTRAINT: No real capital
    CONSTRAINT chk_paper_only CHECK (is_paper_only = TRUE AND real_capital_used = 0),
    CONSTRAINT chk_direction CHECK (simulated_direction IN ('LONG', 'SHORT')),
    CONSTRAINT chk_status CHECK (status IN ('OPEN', 'CLOSED', 'STOPPED', 'TARGET_HIT'))
);

-- ============================================
-- PHASE V-A: LEARNING VELOCITY GOVERNOR (LVG)
-- "Prevent runaway learning"
-- ============================================

-- 4. Learning Velocity Metrics Table
CREATE TABLE IF NOT EXISTS fhq_learning.learning_velocity_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_date DATE NOT NULL,

    -- Daily Counts
    hypotheses_born INT DEFAULT 0,
    hypotheses_killed INT DEFAULT 0,
    hypotheses_weakened INT DEFAULT 0,
    hypotheses_promoted INT DEFAULT 0,

    -- Experiments
    experiments_run INT DEFAULT 0,
    tier1_experiments INT DEFAULT 0,
    tier1_deaths INT DEFAULT 0,

    -- Time Metrics
    mean_time_to_falsification_hours NUMERIC(8,2),
    median_time_to_falsification_hours NUMERIC(8,2),

    -- Velocity Indicators
    net_hypothesis_change INT GENERATED ALWAYS AS (hypotheses_born - hypotheses_killed) STORED,
    death_rate_pct NUMERIC(5,2),

    -- Historical Bands (for LVG)
    historical_avg_born NUMERIC(6,2),
    historical_std_born NUMERIC(6,2),
    historical_avg_killed NUMERIC(6,2),
    historical_std_killed NUMERIC(6,2),

    -- Velocity Governor Status
    velocity_status TEXT DEFAULT 'NORMAL',  -- 'NORMAL', 'ELEVATED', 'SPIKE', 'BRAKE_ACTIVE'
    brake_triggered BOOLEAN DEFAULT FALSE,
    brake_reason TEXT,

    -- Timestamps
    computed_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_velocity_date UNIQUE (metric_date),
    CONSTRAINT chk_velocity_status CHECK (velocity_status IN ('NORMAL', 'ELEVATED', 'SPIKE', 'BRAKE_ACTIVE'))
);

-- 5. Learning Velocity Governor Function
CREATE OR REPLACE FUNCTION fhq_learning.compute_learning_velocity(
    p_date DATE DEFAULT CURRENT_DATE
) RETURNS JSONB AS $$
DECLARE
    v_born INT;
    v_killed INT;
    v_weakened INT;
    v_experiments INT;
    v_tier1_deaths INT;
    v_historical_avg_born NUMERIC;
    v_historical_std_born NUMERIC;
    v_velocity_status TEXT := 'NORMAL';
    v_brake_triggered BOOLEAN := FALSE;
    v_brake_reason TEXT;
    v_upper_band NUMERIC;
BEGIN
    -- Count today's activity
    SELECT COUNT(*) INTO v_born
    FROM fhq_learning.hypothesis_canon
    WHERE DATE(created_at) = p_date;

    SELECT COUNT(*) INTO v_killed
    FROM fhq_learning.hypothesis_canon
    WHERE DATE(falsified_at) = p_date AND status = 'FALSIFIED';

    SELECT COUNT(*) INTO v_weakened
    FROM fhq_learning.hypothesis_canon
    WHERE DATE(last_updated_at) = p_date AND status = 'WEAKENED';

    SELECT COUNT(*) INTO v_experiments
    FROM fhq_learning.experiment_registry
    WHERE DATE(created_at) = p_date;

    SELECT COUNT(*) INTO v_tier1_deaths
    FROM fhq_learning.experiment_registry
    WHERE DATE(created_at) = p_date
      AND experiment_tier = 1
      AND result = 'FALSIFIED';

    -- Calculate historical bands (last 30 days)
    SELECT
        AVG(hypotheses_born),
        STDDEV(hypotheses_born)
    INTO v_historical_avg_born, v_historical_std_born
    FROM fhq_learning.learning_velocity_metrics
    WHERE metric_date >= p_date - INTERVAL '30 days'
      AND metric_date < p_date;

    -- Default if no history
    v_historical_avg_born := COALESCE(v_historical_avg_born, 5);
    v_historical_std_born := COALESCE(v_historical_std_born, 3);

    -- Calculate upper band (2 standard deviations)
    v_upper_band := v_historical_avg_born + (2 * v_historical_std_born);

    -- Determine velocity status
    IF v_born > v_upper_band * 2 THEN
        v_velocity_status := 'SPIKE';
        v_brake_triggered := TRUE;
        v_brake_reason := 'Hypothesis generation rate exceeds 2x upper band';
    ELSIF v_born > v_upper_band THEN
        v_velocity_status := 'ELEVATED';
    END IF;

    -- Also check for anomalous kill rate (too low could indicate p-hacking)
    IF v_experiments > 10 AND v_tier1_deaths::NUMERIC / v_experiments < 0.5 THEN
        v_velocity_status := 'ELEVATED';
        v_brake_reason := COALESCE(v_brake_reason || '; ', '') || 'Tier-1 death rate below 50%';
    END IF;

    -- Insert or update metrics
    INSERT INTO fhq_learning.learning_velocity_metrics (
        metric_date,
        hypotheses_born,
        hypotheses_killed,
        hypotheses_weakened,
        experiments_run,
        tier1_experiments,
        tier1_deaths,
        death_rate_pct,
        historical_avg_born,
        historical_std_born,
        velocity_status,
        brake_triggered,
        brake_reason
    ) VALUES (
        p_date,
        v_born,
        v_killed,
        v_weakened,
        v_experiments,
        v_experiments,  -- Assuming all are Tier-1 for now
        v_tier1_deaths,
        CASE WHEN v_experiments > 0 THEN ROUND(v_tier1_deaths::NUMERIC / v_experiments * 100, 2) ELSE 0 END,
        v_historical_avg_born,
        v_historical_std_born,
        v_velocity_status,
        v_brake_triggered,
        v_brake_reason
    )
    ON CONFLICT (metric_date) DO UPDATE SET
        hypotheses_born = EXCLUDED.hypotheses_born,
        hypotheses_killed = EXCLUDED.hypotheses_killed,
        hypotheses_weakened = EXCLUDED.hypotheses_weakened,
        experiments_run = EXCLUDED.experiments_run,
        tier1_deaths = EXCLUDED.tier1_deaths,
        death_rate_pct = EXCLUDED.death_rate_pct,
        velocity_status = EXCLUDED.velocity_status,
        brake_triggered = EXCLUDED.brake_triggered,
        brake_reason = EXCLUDED.brake_reason,
        computed_at = NOW();

    -- If brake triggered, also trigger kill-switch
    IF v_brake_triggered THEN
        UPDATE fhq_learning.killswitch_registry
        SET is_triggered = TRUE,
            triggered_at = NOW(),
            triggered_by = 'LVG',
            trigger_reason = v_brake_reason
        WHERE killswitch_code = 'KS-VELOCITY-001';
    END IF;

    RETURN jsonb_build_object(
        'date', p_date,
        'hypotheses_born', v_born,
        'hypotheses_killed', v_killed,
        'experiments_run', v_experiments,
        'tier1_deaths', v_tier1_deaths,
        'historical_avg', ROUND(v_historical_avg_born, 2),
        'upper_band', ROUND(v_upper_band, 2),
        'velocity_status', v_velocity_status,
        'brake_triggered', v_brake_triggered,
        'brake_reason', v_brake_reason
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 30-DAY OBSERVATION WINDOW TRACKING
-- ============================================

-- 6. Observation Window Table
CREATE TABLE IF NOT EXISTS fhq_learning.observation_window (
    window_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    window_name TEXT NOT NULL,
    window_type TEXT NOT NULL,  -- 'EC022_ELIGIBILITY', 'PHASE_V_READINESS', 'CALIBRATION'

    -- Window Parameters
    start_date DATE NOT NULL,
    end_date DATE GENERATED ALWAYS AS (start_date + 30) STORED,
    required_market_days INT DEFAULT 30,
    current_market_days INT DEFAULT 0,

    -- Tracking Metrics
    metrics_snapshot JSONB DEFAULT '{}',
    weekly_deltas JSONB DEFAULT '[]',

    -- Acceptance Criteria
    acceptance_criteria JSONB NOT NULL,
    criteria_met BOOLEAN DEFAULT FALSE,
    criteria_evaluation JSONB,

    -- Status
    status TEXT DEFAULT 'ACTIVE',  -- 'ACTIVE', 'COMPLETED', 'FAILED', 'EXTENDED'

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT chk_window_type CHECK (window_type IN ('EC022_ELIGIBILITY', 'PHASE_V_READINESS', 'CALIBRATION')),
    CONSTRAINT chk_window_status CHECK (status IN ('ACTIVE', 'COMPLETED', 'FAILED', 'EXTENDED'))
);

-- Create EC-022 observation window
INSERT INTO fhq_learning.observation_window (
    window_name,
    window_type,
    start_date,
    required_market_days,
    acceptance_criteria
) VALUES (
    'EC-022 Activation Eligibility Window',
    'EC022_ELIGIBILITY',
    CURRENT_DATE,
    30,
    '{
        "ios010_bridge_operational": true,
        "context_confidence_lift": {
            "macro_regimes_tested": 2,
            "drawdown_phases_tested": 1,
            "minimum_lift_vs_baseline": 0.05
        },
        "tier1_calibration": {
            "min_experiments": 30,
            "death_rate_min": 0.70,
            "death_rate_max": 0.90
        }
    }'::jsonb
)
ON CONFLICT DO NOTHING;

-- 7. Weekly Delta Tracking Function
CREATE OR REPLACE FUNCTION fhq_learning.record_weekly_delta(
    p_window_id UUID
) RETURNS JSONB AS $$
DECLARE
    v_delta JSONB;
    v_brier_current NUMERIC;
    v_brier_previous NUMERIC;
    v_context_lift NUMERIC;
    v_false_death_recovery NUMERIC;
    v_tier1_stats RECORD;
BEGIN
    -- Get current Brier score
    SELECT AVG(brier_score_mean) INTO v_brier_current
    FROM fhq_research.forecast_skill_metrics
    WHERE computed_at >= NOW() - INTERVAL '7 days';

    -- Get previous week Brier
    SELECT AVG(brier_score_mean) INTO v_brier_previous
    FROM fhq_research.forecast_skill_metrics
    WHERE computed_at >= NOW() - INTERVAL '14 days'
      AND computed_at < NOW() - INTERVAL '7 days';

    -- Get Tier-1 stats
    SELECT * INTO v_tier1_stats
    FROM fhq_learning.v_tier1_calibration_status;

    -- Calculate context lift (placeholder - needs real implementation)
    v_context_lift := 0;

    -- Calculate false death recovery from shadow tier
    SELECT
        COALESCE(shadow_survived::NUMERIC / NULLIF(shadow_total, 0), 0)
    INTO v_false_death_recovery
    FROM fhq_learning.v_tier1_calibration_status;

    v_delta := jsonb_build_object(
        'week_ending', CURRENT_DATE,
        'brier_score', jsonb_build_object(
            'current', ROUND(COALESCE(v_brier_current, 0)::NUMERIC, 4),
            'previous', ROUND(COALESCE(v_brier_previous, 0)::NUMERIC, 4),
            'delta', ROUND(COALESCE(v_brier_current - v_brier_previous, 0)::NUMERIC, 4)
        ),
        'context_lift', v_context_lift,
        'false_death_recovery_rate', ROUND(COALESCE(v_false_death_recovery, 0)::NUMERIC, 4),
        'tier1_death_rate', v_tier1_stats.death_rate_pct,
        'tier1_experiments', v_tier1_stats.total_experiments,
        'recorded_at', NOW()
    );

    -- Append to weekly_deltas array
    UPDATE fhq_learning.observation_window
    SET weekly_deltas = weekly_deltas || v_delta,
        last_updated_at = NOW()
    WHERE window_id = p_window_id;

    RETURN v_delta;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- VIEWS
-- ============================================

-- 8. Phase V Readiness View
CREATE OR REPLACE VIEW fhq_learning.v_phase5_readiness AS
SELECT
    -- Eligibility Status
    (SELECT COUNT(*) FROM fhq_learning.execution_eligibility_registry WHERE is_eligible) as eligible_hypotheses,
    (SELECT COUNT(*) FROM fhq_learning.execution_eligibility_registry) as evaluated_hypotheses,

    -- Kill-Switch Status
    (SELECT COUNT(*) FROM fhq_learning.killswitch_registry WHERE is_armed AND NOT is_triggered) as active_killswitches,
    (SELECT COUNT(*) FROM fhq_learning.killswitch_registry WHERE is_triggered) as triggered_killswitches,

    -- Simulation Status
    (SELECT COUNT(*) FROM fhq_learning.capital_simulation_ledger WHERE status = 'OPEN') as open_simulations,
    (SELECT COALESCE(SUM(simulated_pnl), 0) FROM fhq_learning.capital_simulation_ledger WHERE status = 'CLOSED') as total_simulated_pnl,

    -- Learning Velocity
    (SELECT velocity_status FROM fhq_learning.learning_velocity_metrics ORDER BY metric_date DESC LIMIT 1) as current_velocity_status,
    (SELECT brake_triggered FROM fhq_learning.learning_velocity_metrics ORDER BY metric_date DESC LIMIT 1) as velocity_brake_active,

    -- Observation Window
    (SELECT current_market_days FROM fhq_learning.observation_window WHERE window_type = 'EC022_ELIGIBILITY' LIMIT 1) as ec022_observation_days,
    (SELECT criteria_met FROM fhq_learning.observation_window WHERE window_type = 'EC022_ELIGIBILITY' LIMIT 1) as ec022_criteria_met,

    -- Hard Constraints
    TRUE as shadow_mode_enforced,
    TRUE as live_capital_blocked,
    TRUE as leverage_blocked,
    TRUE as ec022_frozen,

    NOW() as checked_at;

-- 9. Learning Velocity Dashboard View
CREATE OR REPLACE VIEW fhq_learning.v_learning_velocity_dashboard AS
SELECT
    metric_date,
    hypotheses_born,
    hypotheses_killed,
    net_hypothesis_change,
    experiments_run,
    tier1_deaths,
    death_rate_pct,
    velocity_status,
    brake_triggered,
    brake_reason,
    ROUND(historical_avg_born, 2) as avg_daily_born,
    ROUND(historical_avg_born + 2 * historical_std_born, 2) as upper_band
FROM fhq_learning.learning_velocity_metrics
ORDER BY metric_date DESC
LIMIT 30;

-- ============================================
-- PERMISSIONS
-- ============================================

GRANT SELECT, INSERT, UPDATE ON fhq_learning.execution_eligibility_registry TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON fhq_learning.killswitch_registry TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON fhq_learning.capital_simulation_ledger TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON fhq_learning.learning_velocity_metrics TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON fhq_learning.observation_window TO PUBLIC;
GRANT SELECT ON fhq_learning.v_phase5_readiness TO PUBLIC;
GRANT SELECT ON fhq_learning.v_learning_velocity_dashboard TO PUBLIC;

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON TABLE fhq_learning.execution_eligibility_registry IS 'Phase V: Shadow-only execution eligibility. Hard constraints enforce no live capital, no leverage, no EC-022.';
COMMENT ON TABLE fhq_learning.killswitch_registry IS 'Phase V: Emergency halt mechanisms. All armed by default.';
COMMENT ON TABLE fhq_learning.capital_simulation_ledger IS 'Phase V: Paper trading only. Real capital = 0 enforced.';
COMMENT ON TABLE fhq_learning.learning_velocity_metrics IS 'Phase V-A: Learning Velocity Governor. Auto-brake if velocity spikes.';
COMMENT ON TABLE fhq_learning.observation_window IS '30-day observation windows. EC-022 requires 30 market days before activation eligibility.';
