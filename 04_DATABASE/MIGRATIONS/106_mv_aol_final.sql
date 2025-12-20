-- Migration 106 Final Part 2: Materialized View with correct column names
-- Authority: CEO Directive 2026-FHQ-AOL-TOOLTIPS-01

DROP MATERIALIZED VIEW IF EXISTS fhq_governance.mv_aol_agent_metrics CASCADE;

-- Create mv_aol_agent_metrics with CORRECT column names from source views
CREATE MATERIALIZED VIEW fhq_governance.mv_aol_agent_metrics AS
SELECT
    ac.agent_id,
    ac.contract_status,
    ac.mandate_scope,

    -- Last Activity (agent_last_activity_v)
    la.last_activity,
    la.last_activity_source,

    -- ARS - Agent Reliability Score (agent_task_stats_v - no _7d suffix)
    ts.success_count as success_count_7d,
    ts.failure_count as failure_count_7d,
    ts.retry_count as retry_count_7d,
    ts.fallback_count as fallback_count_7d,
    CASE
        WHEN ts.total_tasks > 0
        THEN ROUND((ts.success_count::numeric / ts.total_tasks) * 100)
        ELSE NULL
    END as ars_score,

    -- CSI - Cognitive Stability Index (agent_csi_stats_v)
    csi.csi_score,
    csi.avg_entropy as reasoning_entropy,
    csi.avg_coherence as thought_coherence,

    -- RBR - Resource Burn Rate (agent_cost_stats_v)
    cs.api_requests_24h,
    cs.api_requests_7d,
    cs.api_cost_7d,
    cs.llm_requests_7d,
    cs.total_cost_7d,

    -- GII - Governance Integrity Index (agent_gii_stats_v)
    gii.gii_state,
    gii.gii_score,
    gii.asrp_violations,
    gii.blocked_operations,
    gii.truth_vector_drift,

    -- DDS - Decision Drift Score (fhq_cognition.dds_metrics_v)
    COALESCE(dds.dds_score, 0) as dds_score,

    -- Research activity (fhq_governance.research_log)
    COALESCE(
        (SELECT COUNT(*) FROM fhq_governance.research_log rl
         WHERE rl.agent_id = ac.agent_id
         AND rl.created_at >= NOW() - INTERVAL '7 days'),
        0
    ) as research_events_7d,

    -- Tooltip data fields from aol_tooltip_data_v
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
GRANT SELECT ON fhq_governance.mv_aol_agent_metrics TO PUBLIC;

-- Verify
SELECT agent_id, ars_score, csi_score, gii_score, dds_score, eis_score
FROM fhq_governance.mv_aol_agent_metrics
LIMIT 5;
