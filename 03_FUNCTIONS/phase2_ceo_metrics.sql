-- ============================================================
-- PHASE 2 CEO OBSERVABILITY SNAPSHOT
-- ============================================================
-- Authority: CEO Directive - Phase 2 Observability & Signal Discipline
-- Contract:  EC-003_2026_PRODUCTION
-- Author:    STIG (CTO)
-- Date:      2026-01-29
--
-- Usage:     psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -f phase2_ceo_metrics.sql
-- ============================================================

-- PART A: Per-Test Metrics
SELECT
    er.experiment_code,
    COUNT(DISTINCT te.trigger_event_id)                                  AS trigger_count,
    COUNT(DISTINCT ol.outcome_id)                                        AS outcome_count,
    ROUND(AVG(CASE WHEN ol.result_bool THEN 1.0 ELSE 0.0 END) * 100, 1) AS win_rate_pct,
    ROUND(AVG(ol.return_bps::numeric), 4)                                AS avg_return_bps,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ol.mfe_atr_multiple)::numeric, 4) AS median_mfe_atr,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ol.mae_atr_multiple)::numeric, 4) AS median_mae_atr,
    COUNT(DISTINCT te.trigger_event_id) FILTER (
        WHERE te.trigger_indicators->>'regime' = 'BULL')                 AS regime_bull,
    COUNT(DISTINCT te.trigger_event_id) FILTER (
        WHERE te.trigger_indicators->>'regime' = 'BEAR')                 AS regime_bear,
    COUNT(DISTINCT te.trigger_event_id) FILTER (
        WHERE te.trigger_indicators->>'regime' = 'STRESS')              AS regime_stress,
    COUNT(DISTINCT te.trigger_event_id) FILTER (
        WHERE te.trigger_indicators->>'regime' = 'NEUTRAL')             AS regime_neutral,
    COUNT(DISTINCT te.trigger_event_id) FILTER (
        WHERE te.trigger_indicators->>'regime' IS NULL)                  AS regime_none
FROM fhq_learning.experiment_registry er
LEFT JOIN fhq_learning.trigger_events te  ON er.experiment_id = te.experiment_id
LEFT JOIN fhq_learning.outcome_ledger ol  ON te.trigger_event_id = ol.trigger_event_id
WHERE er.experiment_code LIKE 'EXP_ALPHA_SAT_%'
GROUP BY er.experiment_code
ORDER BY er.experiment_code;

-- PART B: Global System Status
SELECT jsonb_build_object(
    'snapshot_timestamp', NOW() AT TIME ZONE 'Europe/Oslo',
    'triggers_last_24h', (
        SELECT COUNT(*) FROM fhq_learning.trigger_events
        WHERE created_at > NOW() - INTERVAL '24 hours'
    ),
    'outcomes_last_24h', (
        SELECT COUNT(*) FROM fhq_learning.outcome_ledger
        WHERE created_at > NOW() - INTERVAL '24 hours'
    ),
    'data_lag_status', (
        SELECT CASE
            WHEN MAX(signal_date) >= (CURRENT_DATE - 1) THEN 'OK'
            ELSE 'BLOCKED'
        END
        FROM fhq_indicators.volatility
        WHERE listing_id LIKE '%-USD'
    ),
    'max_signal_date', (
        SELECT MAX(signal_date)
        FROM fhq_indicators.volatility
        WHERE listing_id LIKE '%-USD'
    ),
    'daemon_health_trigger', (
        SELECT jsonb_build_object(
            'status', status,
            'last_heartbeat', last_heartbeat,
            'age_minutes', ROUND(EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) / 60)
        )
        FROM fhq_monitoring.daemon_health
        WHERE daemon_name = 'mechanism_alpha_trigger'
    ),
    'daemon_health_outcome', (
        SELECT jsonb_build_object(
            'status', status,
            'last_heartbeat', last_heartbeat,
            'age_minutes', ROUND(EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) / 60)
        )
        FROM fhq_monitoring.daemon_health
        WHERE daemon_name = 'mechanism_alpha_outcome'
    ),
    'gate_status', (
        SELECT status FROM fhq_meta.gate_status
        WHERE gate_id = 'PHASE2_HYPOTHESIS_SWARM_V1.1'
    ),
    'defcon_level', (
        SELECT defcon_level FROM fhq_governance.defcon_state
        WHERE is_current = true
    ),
    'total_experiments', (
        SELECT COUNT(*) FROM fhq_learning.experiment_registry
        WHERE experiment_code LIKE 'EXP_ALPHA_SAT_%' AND status = 'RUNNING'
    ),
    'total_triggers', (
        SELECT COUNT(*) FROM fhq_learning.trigger_events te
        JOIN fhq_learning.experiment_registry er ON te.experiment_id = er.experiment_id
        WHERE er.experiment_code LIKE 'EXP_ALPHA_SAT_%'
    ),
    'total_outcomes', (
        SELECT COUNT(*) FROM fhq_learning.outcome_ledger ol
        JOIN fhq_learning.experiment_registry er ON ol.experiment_id = er.experiment_id
        WHERE er.experiment_code LIKE 'EXP_ALPHA_SAT_%'
    ),
    'pending_outcomes', (
        SELECT COUNT(*) FROM fhq_learning.trigger_events te
        JOIN fhq_learning.experiment_registry er ON te.experiment_id = er.experiment_id
        JOIN fhq_learning.hypothesis_canon hc ON er.hypothesis_id = hc.canon_id
        LEFT JOIN fhq_learning.outcome_ledger ol ON te.trigger_event_id = ol.trigger_event_id
        WHERE ol.outcome_id IS NULL
          AND er.experiment_code LIKE 'EXP_ALPHA_SAT_%'
    )
) AS global_status;
