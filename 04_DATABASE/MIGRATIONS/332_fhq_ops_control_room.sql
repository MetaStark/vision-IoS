-- ============================================================================
-- Migration: 332_fhq_ops_control_room.sql
-- Directive: CEO-DIR-2026-023 Order 3
-- Purpose: Create fhq_ops schema and Control Room infrastructure
-- Date: 2026-01-23
-- Author: STIG (EC-003)
-- ============================================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS fhq_ops;

COMMENT ON SCHEMA fhq_ops IS 'Operational Control Room - CEO single pane of glass';

-- ============================================================================
-- P0: Pipeline Health Metrics
-- ============================================================================

CREATE TABLE fhq_ops.control_room_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name TEXT NOT NULL,
    metric_category TEXT NOT NULL CHECK (metric_category IN ('PIPELINE', 'SIGNAL', 'CALIBRATION', 'EVENT', 'LEARNING', 'LVI')),
    metric_value NUMERIC,
    metric_status TEXT CHECK (metric_status IN ('GREEN', 'YELLOW', 'RED')),
    threshold_yellow NUMERIC,
    threshold_red NUMERIC,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    lineage_tag TEXT,
    computed_by TEXT DEFAULT 'STIG'
);

CREATE INDEX idx_control_room_metrics_category ON fhq_ops.control_room_metrics(metric_category);
CREATE INDEX idx_control_room_metrics_status ON fhq_ops.control_room_metrics(metric_status);

COMMENT ON TABLE fhq_ops.control_room_metrics IS 'P0 metrics for CEO Control Room dashboard';

-- ============================================================================
-- Alerts Table
-- ============================================================================

CREATE TABLE fhq_ops.control_room_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type TEXT NOT NULL,
    alert_severity TEXT NOT NULL CHECK (alert_severity IN ('INFO', 'WARNING', 'CRITICAL')),
    alert_message TEXT NOT NULL,
    alert_source TEXT,
    is_resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    resolution_notes TEXT,
    auto_generated BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_control_room_alerts_severity ON fhq_ops.control_room_alerts(alert_severity);
CREATE INDEX idx_control_room_alerts_unresolved ON fhq_ops.control_room_alerts(is_resolved) WHERE NOT is_resolved;
CREATE INDEX idx_control_room_alerts_created ON fhq_ops.control_room_alerts(created_at DESC);

COMMENT ON TABLE fhq_ops.control_room_alerts IS 'System alerts for CEO attention';

-- ============================================================================
-- LVI Surface
-- ============================================================================

CREATE TABLE fhq_ops.control_room_lvi (
    lvi_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    lvi_score NUMERIC NOT NULL,
    completed_experiments INT DEFAULT 0,
    median_evaluation_time_hours NUMERIC,
    coverage_rate NUMERIC,
    integrity_rate NUMERIC,
    time_factor NUMERIC,
    brier_component NUMERIC,
    drivers JSONB,
    computation_method TEXT DEFAULT 'lvi_calculator_v1'
);

CREATE INDEX idx_control_room_lvi_computed ON fhq_ops.control_room_lvi(computed_at DESC);

COMMENT ON TABLE fhq_ops.control_room_lvi IS 'Learning Velocity Index daily snapshots';

-- ============================================================================
-- Signal Production Stats View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_ops.v_signal_production AS
SELECT
    COUNT(*) as total_signals,
    COUNT(*) FILTER (WHERE direction != 'UNDEFINED') as actionable_signals,
    COUNT(*) FILTER (WHERE direction = 'UNDEFINED') as undefined_signals,
    ROUND(AVG(confidence_score)::numeric, 4) as avg_confidence,
    ROUND(MAX(confidence_score)::numeric, 4) as max_confidence,
    ROUND(MIN(confidence_score)::numeric, 4) as min_confidence,
    MAX(created_at) as last_signal_time,
    EXTRACT(EPOCH FROM NOW() - MAX(created_at)) / 3600 as hours_since_last_signal
FROM fhq_signal_context.weighted_signal_plan
WHERE created_at > NOW() - INTERVAL '24 hours';

COMMENT ON VIEW fhq_ops.v_signal_production IS 'Signal production stats for last 24 hours';

-- ============================================================================
-- Calibration Status Distribution View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_ops.v_calibration_distribution AS
SELECT
    calibration_status,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER(), 0), 2) as pct
FROM fhq_signal_context.weighted_signal_plan
GROUP BY calibration_status;

COMMENT ON VIEW fhq_ops.v_calibration_distribution IS 'Calibration status breakdown';

-- ============================================================================
-- Event Coverage View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_ops.v_event_coverage AS
SELECT
    COUNT(*) as total_events,
    COUNT(*) FILTER (WHERE event_timestamp > NOW()) as upcoming_events,
    COUNT(*) FILTER (WHERE event_timestamp < NOW() AND event_timestamp > NOW() - INTERVAL '24 hours') as recent_events,
    COUNT(*) FILTER (WHERE event_timestamp < NOW() - INTERVAL '24 hours') as past_events
FROM fhq_calendar.calendar_events;

COMMENT ON VIEW fhq_ops.v_event_coverage IS 'IoS-016 event coverage stats';

-- ============================================================================
-- Learning Loop Health View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_ops.v_learning_loop_health AS
SELECT
    (SELECT COUNT(*) FROM fhq_governance.learning_hypothesis_registry) as hypothesis_registry_count,
    (SELECT COUNT(*) FROM fhq_research.outcome_ledger) as outcome_ledger_count,
    (SELECT COUNT(*) FROM fhq_learning.decision_packs) as decision_packs_count,
    (SELECT COUNT(*) FROM fhq_governance.epistemic_proposals) as epistemic_proposals_count,
    CASE
        WHEN (SELECT COUNT(*) FROM fhq_governance.epistemic_proposals) = 0 THEN 'BLOCKED'
        WHEN (SELECT COUNT(*) FROM fhq_learning.decision_packs) = 0 THEN 'INCOMPLETE'
        ELSE 'OPERATIONAL'
    END as loop_status;

COMMENT ON VIEW fhq_ops.v_learning_loop_health IS 'Learning loop operational status';

-- ============================================================================
-- Daemon Health View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_ops.v_daemon_health AS
SELECT
    component,
    last_heartbeat,
    health_score,
    EXTRACT(EPOCH FROM NOW() - last_heartbeat) / 3600 as hours_since_heartbeat,
    CASE
        WHEN EXTRACT(EPOCH FROM NOW() - last_heartbeat) / 3600 > 24 THEN 'STALE'
        WHEN EXTRACT(EPOCH FROM NOW() - last_heartbeat) / 3600 > 4 THEN 'WARNING'
        ELSE 'HEALTHY'
    END as daemon_status
FROM fhq_governance.agent_heartbeats
ORDER BY last_heartbeat DESC;

COMMENT ON VIEW fhq_ops.v_daemon_health IS 'Agent daemon heartbeat status';

-- ============================================================================
-- Brier Calibration Summary View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_ops.v_brier_summary AS
SELECT
    ROUND(AVG(brier_score_mean)::numeric, 4) as avg_brier_score,
    COUNT(*) as sample_count,
    ROUND(AVG(forecast_count)::numeric, 0) as avg_forecast_count,
    ROUND(MAX(0.1, 1.0 - (AVG(brier_score_mean) * 1.8))::numeric, 4) as skill_factor,
    MAX(computed_at) as last_computed
FROM fhq_research.forecast_skill_metrics
WHERE brier_score_mean IS NOT NULL;

COMMENT ON VIEW fhq_ops.v_brier_summary IS 'Brier score and skill factor summary';

-- ============================================================================
-- Control Room Dashboard View (Unified)
-- ============================================================================

CREATE OR REPLACE VIEW fhq_ops.v_control_room_dashboard AS
SELECT
    -- Signal Production
    (SELECT total_signals FROM fhq_ops.v_signal_production) as signals_24h,
    (SELECT actionable_signals FROM fhq_ops.v_signal_production) as actionable_signals,
    (SELECT hours_since_last_signal FROM fhq_ops.v_signal_production) as hours_since_signal,

    -- Calibration
    (SELECT count FROM fhq_ops.v_calibration_distribution WHERE calibration_status = 'CALIBRATED') as calibrated_count,
    (SELECT pct FROM fhq_ops.v_calibration_distribution WHERE calibration_status = 'CALIBRATED') as calibrated_pct,

    -- Events
    (SELECT upcoming_events FROM fhq_ops.v_event_coverage) as upcoming_events,

    -- Brier
    (SELECT avg_brier_score FROM fhq_ops.v_brier_summary) as brier_score,
    (SELECT skill_factor FROM fhq_ops.v_brier_summary) as skill_factor,

    -- Learning Loop
    (SELECT loop_status FROM fhq_ops.v_learning_loop_health) as learning_loop_status,
    (SELECT outcome_ledger_count FROM fhq_ops.v_learning_loop_health) as outcome_ledger_count,

    -- LVI (latest)
    (SELECT lvi_score FROM fhq_ops.control_room_lvi ORDER BY computed_at DESC LIMIT 1) as lvi_score,

    -- Timestamp
    NOW() as dashboard_timestamp;

COMMENT ON VIEW fhq_ops.v_control_room_dashboard IS 'Single pane of glass for CEO';

-- ============================================================================
-- Seed initial metrics
-- ============================================================================

INSERT INTO fhq_ops.control_room_metrics (metric_name, metric_category, metric_value, metric_status, threshold_yellow, threshold_red, lineage_tag)
VALUES
    ('pipeline_hours_since_signal', 'PIPELINE', 0, 'GREEN', 1, 4, 'CEO-DIR-2026-023'),
    ('signal_production_24h', 'SIGNAL', 0, 'GREEN', 10, 0, 'CEO-DIR-2026-023'),
    ('calibration_pct', 'CALIBRATION', 0, 'GREEN', 80, 50, 'CEO-DIR-2026-023'),
    ('upcoming_events', 'EVENT', 0, 'GREEN', 5, 0, 'CEO-DIR-2026-023'),
    ('experiment_throughput_weekly', 'LEARNING', 0, 'GREEN', 1, 0, 'CEO-DIR-2026-023'),
    ('lvi_score', 'LVI', 0, 'GREEN', 0.3, 0.1, 'CEO-DIR-2026-023');

-- ============================================================================
-- Migration complete
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 332_fhq_ops_control_room.sql completed successfully';
    RAISE NOTICE 'Created schema: fhq_ops';
    RAISE NOTICE 'Created tables: control_room_metrics, control_room_alerts, control_room_lvi';
    RAISE NOTICE 'Created views: v_signal_production, v_calibration_distribution, v_event_coverage, v_learning_loop_health, v_daemon_health, v_brier_summary, v_control_room_dashboard';
END $$;
