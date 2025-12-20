-- ============================================================
-- MIGRATION 063: IoS-013.HCP-LAB G3 Activation
-- Live Paper Trading - Continuous Market Operation
-- Date: 2025-12-02
-- Author: STIG (CTO)
-- Authority: CEO Directive
-- ============================================================
--
-- G3 SCOPE: Continuous 15-minute loop during market hours
-- MODE: SYNTHETIC / LIVE DATA / PAPER EXECUTION
-- MISSION: "Funding the Escape Velocity"
-- ============================================================

BEGIN;

-- ============================================================
-- 1. G3 METRICS TRACKING
-- ============================================================
-- Tracks G3 exit criteria progress

CREATE TABLE IF NOT EXISTS fhq_positions.hcp_g3_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Loop Metrics
    total_loops_completed INTEGER DEFAULT 0,
    loops_today INTEGER DEFAULT 0,
    loops_this_hour INTEGER DEFAULT 0,

    -- Signal Diversity
    unique_regime_liquidity_combos INTEGER DEFAULT 0,
    regime_combos_seen JSONB DEFAULT '[]'::jsonb,

    -- Structure Metrics
    total_structures_generated INTEGER DEFAULT 0,
    structures_by_type JSONB DEFAULT '{}'::jsonb,

    -- Skill Evaluations (IoS-005)
    skill_evaluations_completed INTEGER DEFAULT 0,
    skill_evaluations_pending INTEGER DEFAULT 0,
    average_skill_score NUMERIC(6,4),

    -- Safety Metrics
    production_contamination_events INTEGER DEFAULT 0,
    operational_safety_violations INTEGER DEFAULT 0,
    rate_limit_hits INTEGER DEFAULT 0,
    stale_data_blocks INTEGER DEFAULT 0,

    -- NAV Tracking
    starting_nav NUMERIC(18,2),
    current_nav NUMERIC(18,2),
    peak_nav NUMERIC(18,2),
    trough_nav NUMERIC(18,2),
    max_drawdown_pct NUMERIC(8,4),

    -- G3 Exit Criteria Status
    criterion_10_loops BOOLEAN DEFAULT FALSE,
    criterion_4_combos BOOLEAN DEFAULT FALSE,
    criterion_3_skill_evals BOOLEAN DEFAULT FALSE,
    criterion_zero_contamination BOOLEAN DEFAULT TRUE,
    criterion_zero_violations BOOLEAN DEFAULT TRUE,
    g3_exit_ready BOOLEAN DEFAULT FALSE,

    -- Governance
    hash_chain_id TEXT,
    updated_by TEXT DEFAULT 'HCP-ENGINE'
);

COMMENT ON TABLE fhq_positions.hcp_g3_metrics IS
'IoS-013.HCP-LAB G3: Exit criteria tracking and performance metrics.';

-- Initialize G3 metrics
INSERT INTO fhq_positions.hcp_g3_metrics (
    starting_nav,
    current_nav,
    peak_nav,
    trough_nav,
    hash_chain_id
)
SELECT
    current_nav,
    current_nav,
    current_nav,
    current_nav,
    'HC-HCP-LAB-G3-INIT-' || TO_CHAR(NOW(), 'YYYYMMDD')
FROM fhq_positions.synthetic_lab_nav
LIMIT 1;

-- ============================================================
-- 2. IoS-005 SKILL EVALUATION INTEGRATION
-- ============================================================
-- Links HCP structures to IoS-005 skill tracking

CREATE TABLE IF NOT EXISTS fhq_positions.hcp_skill_evaluations (
    evaluation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Structure Link
    structure_id UUID NOT NULL REFERENCES fhq_positions.structure_plan_hcp(structure_id),
    signal_state_id UUID REFERENCES fhq_positions.hcp_signal_state(state_id),

    -- Prediction (at entry)
    predicted_direction TEXT NOT NULL,  -- UP, DOWN, NEUTRAL
    predicted_magnitude NUMERIC(8,4),   -- Expected % move
    prediction_confidence NUMERIC(6,4),
    prediction_horizon_days INTEGER DEFAULT 30,

    -- Outcome (at evaluation)
    actual_direction TEXT,
    actual_magnitude NUMERIC(8,4),
    outcome_date DATE,
    outcome_recorded BOOLEAN DEFAULT FALSE,

    -- Skill Metrics
    direction_correct BOOLEAN,
    magnitude_error NUMERIC(8,4),
    skill_score NUMERIC(6,4),  -- FjordHQ Skill Score (FSS)
    calibration_score NUMERIC(6,4),

    -- IoS-005 Integration
    ios005_forecast_id UUID,
    ios005_evaluation_id UUID,
    ios005_registered BOOLEAN DEFAULT FALSE,

    -- P&L Attribution
    entry_premium NUMERIC(12,2),
    exit_premium NUMERIC(12,2),
    realized_pnl NUMERIC(12,2),
    pnl_attribution JSONB,

    -- Governance
    hash_chain_id TEXT,
    created_by TEXT DEFAULT 'HCP-ENGINE'
);

COMMENT ON TABLE fhq_positions.hcp_skill_evaluations IS
'IoS-013.HCP-LAB G3: Links HCP structures to IoS-005 skill tracking for performance measurement.';

CREATE INDEX idx_hcp_skill_evaluations_structure ON fhq_positions.hcp_skill_evaluations(structure_id);
CREATE INDEX idx_hcp_skill_evaluations_pending ON fhq_positions.hcp_skill_evaluations(outcome_recorded) WHERE NOT outcome_recorded;

-- ============================================================
-- 3. MARKET HOURS CONFIGURATION
-- ============================================================

INSERT INTO fhq_positions.hcp_engine_config (config_key, config_value, config_type, description) VALUES
    ('market_open_hour', '9', 'INTEGER', 'Market open hour (ET)'),
    ('market_open_minute', '30', 'INTEGER', 'Market open minute'),
    ('market_close_hour', '16', 'INTEGER', 'Market close hour (ET)'),
    ('market_close_minute', '0', 'INTEGER', 'Market close minute'),
    ('timezone', 'America/New_York', 'STRING', 'Market timezone'),
    ('g3_active', 'true', 'BOOLEAN', 'G3 mode active'),
    ('continuous_loop_enabled', 'true', 'BOOLEAN', 'Continuous loop enabled'),
    ('ios005_integration_enabled', 'true', 'BOOLEAN', 'IoS-005 skill tracking enabled'),
    ('deepseek_required', 'true', 'BOOLEAN', 'DeepSeek RiskEnvelope required')
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    updated_at = NOW();

-- Update execution mode to G3_ACTIVE
UPDATE fhq_positions.hcp_engine_config
SET config_value = 'G3_ACTIVE', updated_at = NOW()
WHERE config_key = 'execution_mode';

-- ============================================================
-- 4. REGIME-LIQUIDITY COMBO TRACKING
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_positions.hcp_combo_tracker (
    combo_id SERIAL PRIMARY KEY,
    ios003_regime TEXT NOT NULL,
    ios007_liquidity TEXT NOT NULL,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    occurrence_count INTEGER DEFAULT 1,
    structures_generated INTEGER DEFAULT 0,
    structures_executed INTEGER DEFAULT 0,

    UNIQUE(ios003_regime, ios007_liquidity)
);

COMMENT ON TABLE fhq_positions.hcp_combo_tracker IS
'IoS-013.HCP-LAB G3: Tracks unique regime-liquidity combinations for exit criteria.';

-- Seed with combos from G2
INSERT INTO fhq_positions.hcp_combo_tracker (ios003_regime, ios007_liquidity, structures_generated, structures_executed)
SELECT
    ios003_regime_at_entry,
    ios007_liquidity_state,
    COUNT(*),
    COUNT(*) FILTER (WHERE status = 'ACTIVE')
FROM fhq_positions.structure_plan_hcp
WHERE ios003_regime_at_entry IS NOT NULL
GROUP BY ios003_regime_at_entry, ios007_liquidity_state
ON CONFLICT (ios003_regime, ios007_liquidity) DO UPDATE SET
    occurrence_count = hcp_combo_tracker.occurrence_count + EXCLUDED.occurrence_count,
    last_seen = NOW();

-- ============================================================
-- 5. UPDATE IoS REGISTRY TO G3_ACTIVE
-- ============================================================

UPDATE fhq_meta.ios_registry
SET
    version = '2026.LAB.G3',
    status = 'G3_INTEGRATED',
    governance_state = 'G3_ACTIVE',
    description = 'G3 ACTIVE. Live Paper Trading operational. Continuous 15-min loop during market hours. IoS-005 skill integration enabled. Exit criteria: 10 loops, 4 combos, 3 skill evals, zero contamination.',
    updated_at = NOW()
WHERE ios_id = 'IoS-013.HCP-LAB';

-- ============================================================
-- 6. LOG G3 ACTIVATION
-- ============================================================

INSERT INTO fhq_governance.governance_actions_log
(action_id, action_type, action_target, action_target_type,
 initiated_by, initiated_at, decision, decision_rationale,
 vega_reviewed, hash_chain_id)
VALUES (
    gen_random_uuid(),
    'G3_ACTIVATION',
    'IoS-013.HCP-LAB',
    'IOS_MODULE',
    'CEO',
    NOW(),
    'APPROVED',
    'G3 Activation by CEO directive. Live paper trading authorized. Continuous loop enabled. IoS-005 skill integration active. Exit criteria defined.',
    false,
    'HC-HCP-LAB-G3-ACTIVATION-20251202'
);

-- ============================================================
-- 7. G3 EXIT CRITERIA VIEW
-- ============================================================

CREATE OR REPLACE VIEW fhq_positions.v_hcp_g3_exit_status AS
SELECT
    m.metric_id,
    m.recorded_at,

    -- Criterion 1: 10 Loops
    m.total_loops_completed as loops_completed,
    m.total_loops_completed >= 10 as criterion_1_met,

    -- Criterion 2: 4 Unique Combos
    (SELECT COUNT(*) FROM fhq_positions.hcp_combo_tracker) as unique_combos,
    (SELECT COUNT(*) FROM fhq_positions.hcp_combo_tracker) >= 4 as criterion_2_met,

    -- Criterion 3: 3 Skill Evaluations
    m.skill_evaluations_completed as skill_evals,
    m.skill_evaluations_completed >= 3 as criterion_3_met,

    -- Criterion 4: Zero Contamination
    m.production_contamination_events = 0 as criterion_4_met,

    -- Criterion 5: Zero Violations
    m.operational_safety_violations = 0 as criterion_5_met,

    -- Overall
    (m.total_loops_completed >= 10 AND
     (SELECT COUNT(*) FROM fhq_positions.hcp_combo_tracker) >= 4 AND
     m.skill_evaluations_completed >= 3 AND
     m.production_contamination_events = 0 AND
     m.operational_safety_violations = 0) as g3_exit_ready,

    -- NAV Performance
    m.starting_nav,
    m.current_nav,
    m.peak_nav,
    m.trough_nav,
    m.max_drawdown_pct,
    CASE
        WHEN m.starting_nav > 0 THEN
            ((m.current_nav - m.starting_nav) / m.starting_nav * 100)::NUMERIC(8,4)
        ELSE 0
    END as total_return_pct

FROM fhq_positions.hcp_g3_metrics m
ORDER BY m.recorded_at DESC
LIMIT 1;

COMMIT;

-- ============================================================
-- VERIFICATION
-- ============================================================
SELECT 'G3 Activation Complete' as status;
SELECT ios_id, version, status, governance_state FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-013.HCP-LAB';
SELECT * FROM fhq_positions.v_hcp_g3_exit_status;
SELECT config_key, config_value FROM fhq_positions.hcp_engine_config WHERE config_key IN ('execution_mode', 'g3_active', 'continuous_loop_enabled') ORDER BY config_key;
