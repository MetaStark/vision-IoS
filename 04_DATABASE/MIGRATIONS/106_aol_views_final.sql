-- Migration 106 Final: AOL Tooltip Views with correct column mappings
-- Authority: CEO Directive 2026-FHQ-AOL-TOOLTIPS-01

-- Drop existing views
DROP VIEW IF EXISTS fhq_governance.aol_tooltip_data_v CASCADE;
DROP MATERIALIZED VIEW IF EXISTS fhq_governance.mv_aol_agent_metrics CASCADE;

-- Create aol_tooltip_data_v with ACTUAL column names from source views
CREATE VIEW fhq_governance.aol_tooltip_data_v AS
SELECT
    ac.agent_id,
    ac.contract_status,
    ac.mandate_scope,

    -- ARS metrics (fhq_governance.ars_metrics_v)
    ars.success_rate_pct as ars_success_rate,
    ars.retry_events as ars_retry_frequency,
    ars.fallback_llm_events as ars_fallback_ratio,
    ars.task_error_count as ars_error_count,
    ars.task_success_count as ars_success_count,
    ars.weighted_ars_score as ars_score,

    -- CSI metrics (fhq_cognition.csi_metrics_v)
    csi.reasoning_entropy as csi_reasoning_entropy,
    csi.avg_chain_length as csi_avg_chain_length,
    csi.branching_factor as csi_branching_factor,
    csi.chain_collapse_events as csi_chain_collapse,
    csi.hallucination_block_events as csi_hallucination_blocks,
    csi.stability_variance as csi_stability_variance,
    csi.csi_score,

    -- RBR metrics (fhq_governance.rbr_metrics_v)
    rbr.tokens_per_hour as rbr_tokens_per_hour,
    rbr.deep_mode_seconds as rbr_deep_mode_seconds,
    rbr.shallow_mode_seconds as rbr_shallow_mode_seconds,
    rbr.cost_per_unit_value as rbr_cost_per_unit,
    rbr.week_over_week_drift as rbr_cost_trend,
    rbr.total_cost_7d as rbr_total_cost_7d,
    rbr.rbr_score,

    -- TCL metrics (fhq_governance.tcl_metrics_v)
    tcl.avg_cycle_time_ms as tcl_avg_latency,
    tcl.max_cycle_time_ms as tcl_max_latency,
    tcl.min_cycle_time_ms as tcl_min_latency,
    tcl.time_data_fetch_ms as tcl_data_fetch,
    tcl.time_reasoning_ms as tcl_reasoning,
    tcl.time_output_ms as tcl_output,
    tcl.tasks_measured as tcl_tasks_measured,

    -- GII metrics (fhq_governance.gii_metrics_v)
    gii.asrp_violations as gii_asrp_violations,
    gii.blocked_operations as gii_blocked_ops,
    gii.truth_gateway_skews as gii_truth_drift,
    gii.signature_missing as gii_signature_missing,
    gii.invalid_authority_escalations as gii_authority_escalations,
    gii.gii_status as gii_state,
    gii.gii_score,

    -- EIS metrics (fhq_cognition.eis_metrics_v)
    eis.dependent_modules_count as eis_dependent_modules,
    eis.dependent_tasks_count as eis_dependent_tasks,
    eis.alpha_graph_edge_contribution as eis_alpha_contribution,
    eis.eis_score,

    -- DDS metrics (fhq_cognition.dds_metrics_v)
    dds.drift_events as dds_drift_events,
    dds.volatility_of_action_probability as dds_volatility,
    dds.context_revisions as dds_context_revisions,
    dds.pain_triggered_changes as dds_pain_changes,
    dds.dds_score,

    -- Confidence metrics (fhq_cognition.confidence_metrics_v)
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

-- Create mv_aol_agent_metrics with tooltip data embedded
CREATE MATERIALIZED VIEW fhq_governance.mv_aol_agent_metrics AS
SELECT
    ac.agent_id,
    ac.contract_status,
    ac.mandate_scope,

    -- Last Activity
    la.last_activity,
    la.last_activity_source,

    -- ARS - Agent Reliability Score
    ts.success_count_7d,
    ts.failure_count_7d,
    ts.retry_count_7d,
    ts.fallback_count_7d,
    ts.ars_score,

    -- CSI - Cognitive Stability Index
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

    -- DDS - Decision Drift Score
    COALESCE(dds.dds_score, 0) as dds_score,

    -- Research activity
    COALESCE(
        (SELECT COUNT(*) FROM fhq_research.research_log rl
         WHERE rl.agent_id = ac.agent_id
         AND rl.created_at >= NOW() - INTERVAL '7 days'),
        0
    ) as research_events_7d,

    -- Tooltip data fields
    td.ars_success_rate,
    td.ars_retry_frequency,
    td.ars_fallback_ratio,
    td.ars_score as ars_tooltip_score,
    td.csi_reasoning_entropy as csi_tooltip_entropy,
    td.csi_avg_chain_length,
    td.csi_branching_factor,
    td.csi_stability_variance,
    td.rbr_tokens_per_hour,
    td.rbr_cost_per_unit,
    td.rbr_cost_trend,
    td.rbr_total_cost_7d,
    td.tcl_avg_latency,
    td.tcl_max_latency,
    td.tcl_data_fetch,
    td.tcl_reasoning,
    td.gii_asrp_violations as gii_tooltip_violations,
    td.gii_blocked_ops as gii_tooltip_blocked,
    td.gii_truth_drift,
    td.gii_signature_missing,
    td.eis_dependent_modules,
    td.eis_dependent_tasks,
    td.eis_alpha_contribution,
    td.eis_score,
    td.dds_drift_events,
    td.dds_volatility,
    td.dds_context_revisions,
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

SELECT 'Migration 106 final - AOL tooltip views created successfully' as status;
