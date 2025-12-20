-- Migration 106 Complete Fix: All AOL Tooltip Views
-- Fixes schema location issues and recreates all dependent views
-- Authority: CEO Directive 2026-FHQ-AOL-TOOLTIPS-01

-- Drop existing views to recreate with correct schema references
DROP VIEW IF EXISTS fhq_governance.aol_tooltip_data_v CASCADE;
DROP MATERIALIZED VIEW IF EXISTS fhq_governance.mv_aol_agent_metrics CASCADE;

-- Create aol_tooltip_data_v with CORRECT schema locations
CREATE VIEW fhq_governance.aol_tooltip_data_v AS
SELECT
    ac.agent_id,
    ac.contract_status,
    ac.mandate_scope,

    -- ARS metrics (fhq_governance)
    ars.success_rate_7d as ars_success_rate,
    ars.retry_frequency as ars_retry_frequency,
    ars.fallback_ratio as ars_fallback_ratio,
    ars.error_class_distribution as ars_error_distribution,
    ars.mtbf_hours as ars_mtbf_hours,
    ars.ars_score,

    -- CSI metrics (fhq_cognition)
    csi.reasoning_entropy as csi_reasoning_entropy,
    csi.thought_coherence as csi_thought_coherence,
    csi.response_consistency as csi_response_consistency,
    csi.drift_velocity as csi_drift_velocity,
    csi.anomaly_flags as csi_anomaly_flags,
    csi.csi_score,

    -- RBR metrics (fhq_governance)
    rbr.api_tokens_24h as rbr_api_tokens_24h,
    rbr.llm_calls_24h as rbr_llm_calls_24h,
    rbr.cost_usd_24h as rbr_cost_usd_24h,
    rbr.cost_trend as rbr_cost_trend,
    rbr.budget_utilization_pct as rbr_budget_utilization,
    rbr.projection_30d as rbr_projection_30d,

    -- TCL metrics (fhq_governance)
    tcl.avg_latency_ms as tcl_avg_latency,
    tcl.p95_latency_ms as tcl_p95_latency,
    tcl.slowest_task_type as tcl_slowest_task,
    tcl.queue_depth as tcl_queue_depth,
    tcl.throughput_per_hour as tcl_throughput,

    -- GII metrics (fhq_governance)
    gii.asrp_violation_count as gii_asrp_violations,
    gii.blocked_operation_count as gii_blocked_ops,
    gii.truth_vector_drift as gii_truth_drift,
    gii.last_governance_event as gii_last_event,
    gii.gii_state,
    gii.gii_score,

    -- EIS metrics (fhq_cognition - NOT fhq_execution)
    eis.paper_trade_count as eis_paper_trades,
    eis.signal_contribution_count as eis_signal_contributions,
    eis.downstream_influence as eis_downstream_influence,
    eis.execution_blocked as eis_execution_blocked,
    eis.eis_score,

    -- DDS metrics (fhq_cognition - NOT fhq_governance)
    dds.baseline_behavior_hash as dds_baseline_hash,
    dds.current_behavior_hash as dds_current_hash,
    dds.drift_magnitude as dds_drift_magnitude,
    dds.drift_direction as dds_drift_direction,
    dds.recalibration_recommended as dds_recalibration_needed,
    dds.dds_score,

    -- Confidence metrics (fhq_cognition)
    conf.variance_of_confidence as conf_variance,
    conf.low_confidence_decisions as conf_low_decisions,
    conf.peakedness_index as conf_peakedness,
    conf.uncertainty_fluctuations as conf_fluctuations,

    NOW() as refreshed_at

FROM fhq_governance.agent_contracts ac
LEFT JOIN fhq_governance.ars_metrics_v ars ON ac.agent_id = ars.agent_id
LEFT JOIN fhq_cognition.csi_metrics_v csi ON ac.agent_id = csi.agent_id
LEFT JOIN fhq_governance.rbr_metrics_v rbr ON ac.agent_id = rbr.agent_id
LEFT JOIN fhq_governance.tcl_metrics_v tcl ON ac.agent_id = tcl.agent_id
LEFT JOIN fhq_governance.gii_metrics_v gii ON ac.agent_id = gii.agent_id
LEFT JOIN fhq_cognition.eis_metrics_v eis ON ac.agent_id = eis.agent_id
LEFT JOIN fhq_cognition.dds_metrics_v dds ON ac.agent_id = dds.agent_id
LEFT JOIN fhq_cognition.confidence_metrics_v conf ON ac.agent_id = conf.agent_id
WHERE ac.contract_status = 'ACTIVE';

-- Create mv_aol_agent_metrics with CORRECT schema locations
CREATE MATERIALIZED VIEW fhq_governance.mv_aol_agent_metrics AS
SELECT
    ac.agent_id,
    ac.contract_status,
    ac.mandate_scope,

    -- Last Activity (from multiple sources)
    la.last_activity,
    la.last_activity_source,

    -- ARS - Agent Reliability Score
    ts.success_count_7d,
    ts.failure_count_7d,
    ts.retry_count_7d,
    ts.fallback_count_7d,
    ts.ars_score,

    -- CSI - Cognitive Stability Index (fhq_governance.agent_csi_stats_v)
    csi.csi_score,
    csi.reasoning_entropy,
    csi.thought_coherence,

    -- RBR - Resource Burn Rate
    cs.api_requests_24h,
    cs.api_requests_7d,
    cs.api_cost_7d,
    cs.llm_requests_7d,
    cs.total_cost_7d,

    -- GII - Governance Integrity Index
    gii.gii_state,
    gii.gii_score,
    gii.asrp_violations,
    gii.blocked_operations,
    gii.truth_vector_drift,

    -- DDS - Decision Drift Score (fhq_cognition.dds_metrics_v)
    COALESCE(dds.dds_score, 0) as dds_score,

    -- Research activity
    COALESCE(
        (SELECT COUNT(*) FROM fhq_research.research_log rl
         WHERE rl.agent_id = ac.agent_id
         AND rl.created_at >= NOW() - INTERVAL '7 days'),
        0
    ) as research_events_7d,

    -- Tooltip data fields from comprehensive view
    td.ars_success_rate,
    td.ars_retry_frequency,
    td.ars_fallback_ratio,
    td.ars_mtbf_hours,
    td.csi_reasoning_entropy,
    td.csi_thought_coherence,
    td.csi_response_consistency,
    td.csi_drift_velocity,
    td.rbr_api_tokens_24h,
    td.rbr_llm_calls_24h,
    td.rbr_cost_usd_24h,
    td.rbr_cost_trend,
    td.rbr_budget_utilization,
    td.tcl_avg_latency,
    td.tcl_p95_latency,
    td.tcl_throughput,
    td.gii_asrp_violations,
    td.gii_blocked_ops,
    td.gii_truth_drift,
    td.eis_paper_trades,
    td.eis_signal_contributions,
    td.eis_score,
    td.dds_baseline_hash,
    td.dds_drift_magnitude,
    td.dds_recalibration_needed,
    td.conf_variance,
    td.conf_low_decisions,

    NOW() as refreshed_at

FROM fhq_governance.agent_contracts ac
LEFT JOIN fhq_governance.agent_last_activity_v la ON ac.agent_id = la.agent_id
LEFT JOIN fhq_governance.agent_task_stats_v ts ON ac.agent_id = ts.agent_id
LEFT JOIN fhq_governance.agent_csi_stats_v csi ON ac.agent_id = csi.agent_id
LEFT JOIN fhq_governance.agent_cost_stats_v cs ON ac.agent_id = cs.agent_id
LEFT JOIN fhq_governance.agent_gii_stats_v gii ON ac.agent_id = gii.agent_id
LEFT JOIN fhq_cognition.dds_metrics_v dds ON ac.agent_id = dds.agent_id
LEFT JOIN fhq_governance.aol_tooltip_data_v td ON ac.agent_id = td.agent_id
WHERE ac.contract_status = 'ACTIVE';

-- Create index for performance
CREATE UNIQUE INDEX idx_mv_aol_agent_metrics_agent_id
ON fhq_governance.mv_aol_agent_metrics(agent_id);

-- Grant permissions
GRANT SELECT ON fhq_governance.aol_tooltip_data_v TO PUBLIC;
GRANT SELECT ON fhq_governance.mv_aol_agent_metrics TO PUBLIC;

SELECT 'Migration 106 complete fix - all views created with correct schema references' as status;
