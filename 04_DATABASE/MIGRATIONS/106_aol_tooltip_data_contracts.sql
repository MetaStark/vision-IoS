-- ============================================================================
-- Migration 106: AOL Tooltip Data Contracts
-- CEO Directive 2026-FHQ-AOL-TOOLTIPS-01 Section 2
-- ============================================================================
--
-- Authority: ADR-001, ADR-006, ADR-009, ADR-011, ADR-012, ADR-013, ADR-018, ADR-019
-- Classification: CONSTITUTIONAL - Semantic Tooltip Layer (TL-1)
--
-- This migration creates stable SQL views for tooltip data binding.
-- No synthetic values. No placeholders. Backend truth only.
-- ============================================================================

-- ============================================================================
-- Section 2.1: ARS Data Contract (Agent Reliability Score)
-- ============================================================================

DROP VIEW IF EXISTS fhq_governance.ars_metrics_v CASCADE;

CREATE VIEW fhq_governance.ars_metrics_v AS
WITH task_stats AS (
    SELECT
        agent_id,
        COUNT(*) FILTER (WHERE status = 'SUCCESS') as task_success_count,
        COUNT(*) FILTER (WHERE status IN ('FAILED', 'ERROR')) as task_error_count,
        COUNT(*) FILTER (WHERE fallback_used = true) as fallback_llm_events,
        COUNT(*) FILTER (WHERE retry_count > 0) as retry_events,
        SUM(COALESCE(cost_usd, 0)) as total_cost,
        COUNT(*) as total_tasks,
        AVG(COALESCE(cost_usd, 0)) as token_cost_per_task
    FROM fhq_governance.agent_task_log
    WHERE created_at >= NOW() - INTERVAL '7 days'
    GROUP BY agent_id
),
governance_stats AS (
    SELECT
        agent_id,
        COUNT(*) as governance_violations_count
    FROM fhq_governance.asrp_violations
    WHERE created_at >= NOW() - INTERVAL '7 days'
      AND resolution_status != 'RESOLVED'
    GROUP BY agent_id
)
SELECT
    ac.agent_id,
    COALESCE(ts.task_success_count, 0) as task_success_count,
    COALESCE(ts.task_error_count, 0) as task_error_count,
    COALESCE(gs.governance_violations_count, 0) as governance_violations_count,
    COALESCE(ts.fallback_llm_events, 0) as fallback_llm_events,
    COALESCE(ts.retry_events, 0) as retry_events,
    COALESCE(ts.token_cost_per_task, 0)::numeric(10,6) as token_cost_per_task,
    -- Weighted ARS Score:
    -- Base 100 - (errors * 5) - (governance * 20) - (fallbacks * 2) - (retries * 1)
    GREATEST(0, LEAST(100,
        100
        - (COALESCE(ts.task_error_count, 0) * 5)
        - (COALESCE(gs.governance_violations_count, 0) * 20)
        - (COALESCE(ts.fallback_llm_events, 0) * 2)
        - (COALESCE(ts.retry_events, 0) * 1)
    ))::integer as weighted_ars_score,
    -- Raw success rate for display
    CASE
        WHEN COALESCE(ts.total_tasks, 0) > 0
        THEN ROUND((COALESCE(ts.task_success_count, 0)::numeric / ts.total_tasks) * 100, 1)
        ELSE NULL
    END as success_rate_pct,
    -- Formula text for tooltip
    'ARS = 100 - (errors×5) - (gov_violations×20) - (fallbacks×2) - (retries×1)'::text as formula
FROM fhq_governance.agent_contracts ac
LEFT JOIN task_stats ts ON ac.agent_id = ts.agent_id
LEFT JOIN governance_stats gs ON ac.agent_id = gs.agent_id
WHERE ac.contract_status = 'ACTIVE';

-- ============================================================================
-- Section 2.2: CSI Data Contract (Cognitive Stability Index)
-- ============================================================================

DROP VIEW IF EXISTS fhq_cognition.csi_metrics_v CASCADE;

CREATE VIEW fhq_cognition.csi_metrics_v AS
WITH cognitive_stats AS (
    SELECT
        agent_id,
        AVG(reasoning_entropy) as reasoning_entropy,
        AVG(chain_length) as avg_chain_length,
        AVG(branching_factor) as branching_factor,
        COUNT(*) FILTER (WHERE collapse_rate > 0.5) as chain_collapse_events,
        STDDEV(reasoning_entropy) as stability_variance,
        COUNT(*) as measurement_count
    FROM fhq_cognition.cognitive_metrics
    WHERE measured_at >= NOW() - INTERVAL '7 days'
    GROUP BY agent_id
),
hallucination_stats AS (
    SELECT
        agent_id,
        COUNT(*) as hallucination_block_events
    FROM fhq_governance.asrp_violations
    WHERE created_at >= NOW() - INTERVAL '7 days'
      AND violation_type ILIKE '%hallucination%'
    GROUP BY agent_id
)
SELECT
    ac.agent_id,
    COALESCE(cs.reasoning_entropy, NULL)::numeric(8,6) as reasoning_entropy,
    COALESCE(cs.avg_chain_length, NULL)::numeric(6,2) as avg_chain_length,
    COALESCE(cs.branching_factor, NULL)::numeric(6,3) as branching_factor,
    COALESCE(cs.chain_collapse_events, 0) as chain_collapse_events,
    COALESCE(hs.hallucination_block_events, 0) as hallucination_block_events,
    COALESCE(cs.stability_variance, NULL)::numeric(8,6) as stability_variance,
    -- CSI Score: 80 base + coherence bonus - entropy penalty - collapse penalty
    CASE WHEN cs.measurement_count > 0 THEN
        GREATEST(0, LEAST(100,
            80
            + (20 * (1 - COALESCE(cs.reasoning_entropy, 0.5)))
            - (COALESCE(cs.chain_collapse_events, 0) * 5)
            - (COALESCE(hs.hallucination_block_events, 0) * 10)
            - (COALESCE(cs.stability_variance, 0) * 20)
        ))::integer
    ELSE NULL END as csi_score,
    'CSI = 80 + coherence_bonus - entropy_penalty - collapse_penalty - hallucination_penalty'::text as formula
FROM fhq_governance.agent_contracts ac
LEFT JOIN cognitive_stats cs ON ac.agent_id = cs.agent_id
LEFT JOIN hallucination_stats hs ON ac.agent_id = hs.agent_id
WHERE ac.contract_status = 'ACTIVE';

-- ============================================================================
-- Section 2.3: RBR Data Contract (Resource Burn Rate)
-- ============================================================================

DROP VIEW IF EXISTS fhq_governance.rbr_metrics_v CASCADE;

CREATE VIEW fhq_governance.rbr_metrics_v AS
WITH current_week AS (
    SELECT
        agent_id,
        SUM(tokens_in + tokens_out) as total_tokens,
        COUNT(*) as total_tasks,
        SUM(cost_usd) as total_cost,
        SUM(latency_ms) / 1000.0 as total_seconds,
        -- Estimate deep vs shallow by latency (>5s = deep mode)
        SUM(CASE WHEN latency_ms > 5000 THEN latency_ms ELSE 0 END) / 1000.0 as deep_mode_seconds,
        SUM(CASE WHEN latency_ms <= 5000 THEN latency_ms ELSE 0 END) / 1000.0 as shallow_mode_seconds
    FROM fhq_governance.agent_task_log
    WHERE created_at >= NOW() - INTERVAL '7 days'
    GROUP BY agent_id
),
prev_week AS (
    SELECT
        agent_id,
        SUM(cost_usd) as prev_cost
    FROM fhq_governance.agent_task_log
    WHERE created_at >= NOW() - INTERVAL '14 days'
      AND created_at < NOW() - INTERVAL '7 days'
    GROUP BY agent_id
)
SELECT
    ac.agent_id,
    COALESCE(cw.total_tokens / NULLIF(EXTRACT(EPOCH FROM INTERVAL '168 hours') / 3600, 0), 0)::integer as tokens_per_hour,
    COALESCE(cw.deep_mode_seconds, 0)::numeric(10,2) as deep_mode_seconds,
    COALESCE(cw.shallow_mode_seconds, 0)::numeric(10,2) as shallow_mode_seconds,
    -- Cost per unit value (simplified: cost / tasks)
    CASE WHEN COALESCE(cw.total_tasks, 0) > 0
        THEN (COALESCE(cw.total_cost, 0) / cw.total_tasks)::numeric(10,6)
        ELSE 0
    END as cost_per_unit_value,
    -- Week over week drift percentage
    CASE
        WHEN COALESCE(pw.prev_cost, 0) > 0
        THEN ((COALESCE(cw.total_cost, 0) - pw.prev_cost) / pw.prev_cost * 100)::numeric(6,2)
        ELSE NULL
    END as week_over_week_drift,
    -- RBR Score: Lower is better, inverted for display (100 = efficient)
    GREATEST(0, LEAST(100,
        100 - (COALESCE(cw.total_cost, 0) * 10)
    ))::integer as rbr_score,
    COALESCE(cw.total_cost, 0)::numeric(10,4) as total_cost_7d,
    'RBR = 100 - (total_cost × 10). Lower cost = higher score.'::text as formula
FROM fhq_governance.agent_contracts ac
LEFT JOIN current_week cw ON ac.agent_id = cw.agent_id
LEFT JOIN prev_week pw ON ac.agent_id = pw.agent_id
WHERE ac.contract_status = 'ACTIVE';

-- ============================================================================
-- Section 2.4: TCL Data Contract (Task Cycle Latency)
-- ============================================================================

DROP VIEW IF EXISTS fhq_governance.tcl_metrics_v CASCADE;

CREATE VIEW fhq_governance.tcl_metrics_v AS
SELECT
    ac.agent_id,
    -- Segment timing (estimated based on task types)
    COALESCE(AVG(tl.latency_ms) FILTER (WHERE tl.task_type = 'API_CALL'), 0)::integer as time_data_fetch_ms,
    COALESCE(AVG(tl.latency_ms) FILTER (WHERE tl.task_type IN ('LLM_CALL', 'RESEARCH')), 0)::integer as time_reasoning_ms,
    COALESCE(AVG(tl.latency_ms) FILTER (WHERE tl.task_type = 'EXECUTION'), 0)::integer as time_output_ms,
    -- Total cycle time (avg latency across all tasks)
    COALESCE(AVG(tl.latency_ms), 0)::integer as avg_cycle_time_ms,
    COALESCE(MAX(tl.latency_ms), 0)::integer as max_cycle_time_ms,
    COALESCE(MIN(tl.latency_ms) FILTER (WHERE tl.latency_ms > 0), 0)::integer as min_cycle_time_ms,
    COUNT(tl.task_id) as tasks_measured,
    'TCL = time_fetch + time_reasoning + time_output'::text as formula
FROM fhq_governance.agent_contracts ac
LEFT JOIN fhq_governance.agent_task_log tl ON ac.agent_id = tl.agent_id
    AND tl.created_at >= NOW() - INTERVAL '7 days'
WHERE ac.contract_status = 'ACTIVE'
GROUP BY ac.agent_id;

-- ============================================================================
-- Section 2.5: GII Data Contract (Governance Integrity Index)
-- ============================================================================

DROP VIEW IF EXISTS fhq_governance.gii_metrics_v CASCADE;

CREATE VIEW fhq_governance.gii_metrics_v AS
WITH signature_stats AS (
    SELECT
        agent_id,
        COUNT(*) FILTER (WHERE signature_hash IS NULL) as signature_missing
    FROM fhq_governance.agent_task_log
    WHERE created_at >= NOW() - INTERVAL '7 days'
    GROUP BY agent_id
),
asrp_stats AS (
    SELECT
        agent_id,
        COUNT(*) as asrp_violations
    FROM fhq_governance.asrp_violations
    WHERE created_at >= NOW() - INTERVAL '7 days'
    GROUP BY agent_id
),
entropy_stats AS (
    SELECT
        executed_by as agent_id,
        COUNT(*) FILTER (WHERE propagation_blocked = true) as blocked_operations,
        COUNT(*) FILTER (WHERE gate = 'G4' AND propagation_blocked = true) as invalid_authority_escalations
    FROM fhq_governance.causal_entropy_audit
    WHERE executed_at >= NOW() - INTERVAL '7 days'
    GROUP BY executed_by
),
drift_stats AS (
    SELECT
        agent_id,
        MAX(truth_vector_drift) as max_truth_drift
    FROM fhq_cognition.cognitive_metrics
    WHERE measured_at >= NOW() - INTERVAL '7 days'
    GROUP BY agent_id
)
SELECT
    ac.agent_id,
    COALESCE(ss.signature_missing, 0) as signature_missing,
    COALESCE(asrp.asrp_violations, 0) as asrp_violations,
    COALESCE(ds.max_truth_drift, 0)::numeric(8,6) as truth_gateway_skews,
    COALESCE(es.invalid_authority_escalations, 0) as invalid_authority_escalations,
    COALESCE(es.blocked_operations, 0) as blocked_operations,
    -- GII Status determination
    CASE
        WHEN COALESCE(asrp.asrp_violations, 0) > 3 THEN 'RED'
        WHEN COALESCE(es.blocked_operations, 0) > 5 THEN 'RED'
        WHEN COALESCE(es.invalid_authority_escalations, 0) > 0 THEN 'RED'
        WHEN COALESCE(asrp.asrp_violations, 0) > 0 THEN 'YELLOW'
        WHEN COALESCE(es.blocked_operations, 0) > 0 THEN 'YELLOW'
        WHEN COALESCE(ds.max_truth_drift, 0) > 0.3 THEN 'YELLOW'
        ELSE 'GREEN'
    END as gii_status,
    -- GII Score
    GREATEST(0, LEAST(100,
        100
        - (COALESCE(asrp.asrp_violations, 0) * 15)
        - (COALESCE(es.blocked_operations, 0) * 5)
        - (COALESCE(es.invalid_authority_escalations, 0) * 25)
        - (COALESCE(ss.signature_missing, 0) * 2)
        - (COALESCE(ds.max_truth_drift, 0) * 30)
    ))::integer as gii_score,
    'GII = 100 - violations - blocked_ops - escalations - missing_sig - drift. RED if violations>3 OR blocked>5 OR escalations>0'::text as formula
FROM fhq_governance.agent_contracts ac
LEFT JOIN signature_stats ss ON ac.agent_id = ss.agent_id
LEFT JOIN asrp_stats asrp ON ac.agent_id = asrp.agent_id
LEFT JOIN entropy_stats es ON ac.agent_id = es.agent_id
LEFT JOIN drift_stats ds ON ac.agent_id = ds.agent_id
WHERE ac.contract_status = 'ACTIVE';

-- ============================================================================
-- Section 2.6: EIS Data Contract (Execution Influence Score)
-- ============================================================================

DROP VIEW IF EXISTS fhq_cognition.eis_metrics_v CASCADE;

CREATE VIEW fhq_cognition.eis_metrics_v AS
WITH task_deps AS (
    SELECT
        agent_id,
        COUNT(DISTINCT task_type) as dependent_modules_count,
        COUNT(*) as dependent_tasks_count
    FROM fhq_governance.agent_task_log
    WHERE created_at >= NOW() - INTERVAL '7 days'
    GROUP BY agent_id
),
graph_contribution AS (
    -- Count edges in alpha graph where agent contributed
    SELECT
        'FINN' as agent_id, -- FINN is the primary research agent
        COUNT(*) as edge_count
    FROM vision_signals.alpha_graph_edges
    WHERE created_at >= NOW() - INTERVAL '30 days'
)
SELECT
    ac.agent_id,
    COALESCE(td.dependent_modules_count, 0) as dependent_modules_count,
    COALESCE(td.dependent_tasks_count, 0) as dependent_tasks_count,
    CASE WHEN ac.agent_id = 'FINN' THEN COALESCE(gc.edge_count, 0) ELSE 0 END as alpha_graph_edge_contribution,
    -- EIS Score: Based on influence breadth
    GREATEST(0, LEAST(100,
        (COALESCE(td.dependent_modules_count, 0) * 10) +
        LEAST(50, COALESCE(td.dependent_tasks_count, 0)) +
        CASE WHEN ac.agent_id = 'FINN' THEN LEAST(30, COALESCE(gc.edge_count, 0) / 10) ELSE 0 END
    ))::integer as eis_score,
    'EIS = modules×10 + tasks(max50) + graph_edges/10(max30). Measures system influence.'::text as formula
FROM fhq_governance.agent_contracts ac
LEFT JOIN task_deps td ON ac.agent_id = td.agent_id
LEFT JOIN graph_contribution gc ON ac.agent_id = gc.agent_id
WHERE ac.contract_status = 'ACTIVE';

-- ============================================================================
-- Section 2.7: DDS Data Contract (Decision Drift Score)
-- ============================================================================

DROP VIEW IF EXISTS fhq_cognition.dds_metrics_v CASCADE;

CREATE VIEW fhq_cognition.dds_metrics_v AS
WITH drift_stats AS (
    SELECT
        agent_id,
        COUNT(*) FILTER (WHERE decision_drift_score > 0.1) as drift_events,
        STDDEV(decision_drift_score) as volatility_of_action_probability,
        COUNT(*) as total_measurements
    FROM fhq_cognition.cognitive_metrics
    WHERE measured_at >= NOW() - INTERVAL '7 days'
    GROUP BY agent_id
),
context_stats AS (
    -- Approximate context revisions from task retries
    SELECT
        agent_id,
        SUM(retry_count) as context_revisions,
        COUNT(*) FILTER (WHERE status = 'FAILED' AND retry_count > 0) as pain_triggered_changes
    FROM fhq_governance.agent_task_log
    WHERE created_at >= NOW() - INTERVAL '7 days'
    GROUP BY agent_id
)
SELECT
    ac.agent_id,
    COALESCE(ds.drift_events, 0) as drift_events,
    COALESCE(ds.volatility_of_action_probability, 0)::numeric(8,6) as volatility_of_action_probability,
    COALESCE(cs.context_revisions, 0) as context_revisions,
    COALESCE(cs.pain_triggered_changes, 0) as pain_triggered_changes,
    -- DDS Score: 0 = stable, higher = more drift
    LEAST(100,
        (COALESCE(ds.drift_events, 0) * 5) +
        (COALESCE(ds.volatility_of_action_probability, 0) * 50) +
        (COALESCE(cs.context_revisions, 0) * 2) +
        (COALESCE(cs.pain_triggered_changes, 0) * 10)
    )::numeric(6,3) as dds_score,
    'DDS = drift_events×5 + volatility×50 + revisions×2 + pain_changes×10. 0 = stable.'::text as formula
FROM fhq_governance.agent_contracts ac
LEFT JOIN drift_stats ds ON ac.agent_id = ds.agent_id
LEFT JOIN context_stats cs ON ac.agent_id = cs.agent_id
WHERE ac.contract_status = 'ACTIVE';

-- ============================================================================
-- Section 2.8: Confidence Spread Data Contract
-- ============================================================================

DROP VIEW IF EXISTS fhq_cognition.confidence_metrics_v CASCADE;

CREATE VIEW fhq_cognition.confidence_metrics_v AS
SELECT
    ac.agent_id,
    COALESCE(STDDEV(cm.confidence_spread), 0)::numeric(8,6) as variance_of_confidence,
    COALESCE(COUNT(*) FILTER (WHERE cm.confidence_spread > 0.5), 0) as low_confidence_decisions,
    -- Peakedness (kurtosis approximation): high = concentrated, low = spread
    CASE WHEN COUNT(cm.metric_id) > 3 THEN
        (AVG(POWER(cm.confidence_spread - AVG(cm.confidence_spread) OVER(), 4)) /
         POWER(STDDEV(cm.confidence_spread), 4))::numeric(8,4)
    ELSE NULL END as peakedness_index,
    -- Uncertainty fluctuations: count of significant confidence changes
    COALESCE(COUNT(*) FILTER (WHERE cm.confidence_spread > 0.3), 0) as uncertainty_fluctuations,
    'Confidence Spread measures decision certainty variance. High variance = potential hallucination risk.'::text as description
FROM fhq_governance.agent_contracts ac
LEFT JOIN fhq_cognition.cognitive_metrics cm ON ac.agent_id = cm.agent_id
    AND cm.measured_at >= NOW() - INTERVAL '7 days'
WHERE ac.contract_status = 'ACTIVE'
GROUP BY ac.agent_id;

-- ============================================================================
-- Section 2.9: Dependency Topology Data Contract
-- ============================================================================

DROP VIEW IF EXISTS fhq_cognition.agent_dependency_graph_v CASCADE;

CREATE VIEW fhq_cognition.agent_dependency_graph_v AS
WITH upstream AS (
    -- Agents that provide data/signals to this agent
    SELECT
        ac.agent_id,
        ARRAY_AGG(DISTINCT
            CASE
                WHEN ac.agent_id IN ('LINE', 'CODE') THEN 'STIG'
                WHEN ac.agent_id = 'FINN' THEN 'LARS'
                WHEN ac.agent_id IN ('CDMO', 'CEIO', 'CRIO') THEN 'LARS'
                ELSE NULL
            END
        ) FILTER (WHERE TRUE) as upstream_agents
    FROM fhq_governance.agent_contracts ac
    WHERE ac.contract_status = 'ACTIVE'
    GROUP BY ac.agent_id
),
downstream AS (
    -- Agents that consume this agent's output
    SELECT
        ac.agent_id,
        ARRAY_AGG(DISTINCT
            CASE
                WHEN ac.agent_id = 'LARS' THEN 'FINN'
                WHEN ac.agent_id = 'STIG' THEN 'LINE'
                WHEN ac.agent_id = 'FINN' THEN 'CRIO'
                WHEN ac.agent_id = 'VEGA' THEN NULL -- VEGA observes all
                ELSE NULL
            END
        ) FILTER (WHERE TRUE) as downstream_agents
    FROM fhq_governance.agent_contracts ac
    WHERE ac.contract_status = 'ACTIVE'
    GROUP BY ac.agent_id
)
SELECT
    ac.agent_id,
    COALESCE(u.upstream_agents, ARRAY[]::text[]) as upstream_agents,
    COALESCE(d.downstream_agents, ARRAY[]::text[]) as downstream_agents,
    -- Dependency matrix as JSONB
    jsonb_build_object(
        'upstream_count', COALESCE(array_length(u.upstream_agents, 1), 0),
        'downstream_count', COALESCE(array_length(d.downstream_agents, 1), 0),
        'is_chokepoint', COALESCE(array_length(d.downstream_agents, 1), 0) > 2,
        'tier', CASE
            WHEN ac.agent_id IN ('LARS', 'VEGA') THEN 1
            WHEN ac.agent_id IN ('STIG', 'FINN', 'LINE') THEN 2
            ELSE 3
        END
    ) as dependency_matrix,
    -- Inferred paths (simplified)
    CASE
        WHEN ac.agent_id = 'LARS' THEN 'CEO → LARS → (FINN, STIG, LINE)'
        WHEN ac.agent_id = 'STIG' THEN 'LARS → STIG → (CODE, LINE)'
        WHEN ac.agent_id = 'FINN' THEN 'LARS → FINN → CRIO → Signals'
        WHEN ac.agent_id = 'LINE' THEN 'STIG → LINE → Execution'
        WHEN ac.agent_id = 'VEGA' THEN 'All Agents → VEGA → Governance'
        ELSE 'Independent'
    END as inferred_paths,
    'Dependency graph shows agent influence topology. Chokepoints require redundancy.'::text as description
FROM fhq_governance.agent_contracts ac
LEFT JOIN upstream u ON ac.agent_id = u.agent_id
LEFT JOIN downstream d ON ac.agent_id = d.agent_id
WHERE ac.contract_status = 'ACTIVE';

-- ============================================================================
-- Section 2.10: Agent Integrity Ledger View
-- ============================================================================

DROP VIEW IF EXISTS fhq_governance.agent_integrity_log_v CASCADE;

CREATE VIEW fhq_governance.agent_integrity_log_v AS
SELECT
    tl.task_id,
    tl.agent_id,
    tl.task_name,
    tl.task_type,
    tl.status,
    tl.started_at,
    tl.completed_at,
    tl.latency_ms,
    tl.cost_usd,
    tl.provider,
    tl.model,
    tl.signature_hash,
    tl.quad_hash,
    tl.fallback_used,
    tl.retry_count,
    tl.error_message,
    -- Governance flag
    CASE
        WHEN tl.status IN ('FAILED', 'ERROR') THEN 'ERROR'
        WHEN tl.fallback_used = true THEN 'WARNING'
        WHEN tl.retry_count > 0 THEN 'WARNING'
        WHEN tl.signature_hash IS NULL THEN 'WARNING'
        ELSE 'OK'
    END as governance_flag,
    -- Drift mode indicator
    CASE
        WHEN tl.retry_count > 2 THEN 'HIGH_DRIFT'
        WHEN tl.fallback_used = true THEN 'FALLBACK_MODE'
        WHEN tl.retry_count > 0 THEN 'RETRY_MODE'
        ELSE 'NORMAL'
    END as drift_mode,
    ROW_NUMBER() OVER (PARTITION BY tl.agent_id ORDER BY tl.started_at DESC) as task_rank
FROM fhq_governance.agent_task_log tl
WHERE tl.created_at >= NOW() - INTERVAL '30 days'
ORDER BY tl.started_at DESC;

-- ============================================================================
-- Section 3: Comprehensive AOL Tooltip View (joins all metrics)
-- ============================================================================

DROP VIEW IF EXISTS fhq_governance.aol_tooltip_data_v CASCADE;

CREATE VIEW fhq_governance.aol_tooltip_data_v AS
SELECT
    ac.agent_id,
    ac.contract_status,
    ac.mandate_scope,

    -- ARS Metrics
    ars.task_success_count,
    ars.task_error_count,
    ars.governance_violations_count,
    ars.fallback_llm_events,
    ars.retry_events,
    ars.token_cost_per_task,
    ars.weighted_ars_score,
    ars.formula as ars_formula,

    -- CSI Metrics
    csi.reasoning_entropy,
    csi.avg_chain_length,
    csi.branching_factor,
    csi.chain_collapse_events,
    csi.hallucination_block_events,
    csi.stability_variance,
    csi.csi_score,
    csi.formula as csi_formula,

    -- RBR Metrics
    rbr.tokens_per_hour,
    rbr.deep_mode_seconds,
    rbr.shallow_mode_seconds,
    rbr.cost_per_unit_value,
    rbr.week_over_week_drift,
    rbr.rbr_score,
    rbr.total_cost_7d,
    rbr.formula as rbr_formula,

    -- TCL Metrics
    tcl.time_data_fetch_ms,
    tcl.time_reasoning_ms,
    tcl.time_output_ms,
    tcl.avg_cycle_time_ms,
    tcl.formula as tcl_formula,

    -- GII Metrics
    gii.signature_missing,
    gii.asrp_violations,
    gii.truth_gateway_skews,
    gii.invalid_authority_escalations,
    gii.blocked_operations,
    gii.gii_status,
    gii.gii_score,
    gii.formula as gii_formula,

    -- EIS Metrics
    eis.dependent_modules_count,
    eis.dependent_tasks_count,
    eis.alpha_graph_edge_contribution,
    eis.eis_score,
    eis.formula as eis_formula,

    -- DDS Metrics
    dds.drift_events,
    dds.volatility_of_action_probability,
    dds.context_revisions,
    dds.pain_triggered_changes,
    dds.dds_score,
    dds.formula as dds_formula,

    -- Confidence Metrics
    conf.variance_of_confidence,
    conf.low_confidence_decisions,
    conf.peakedness_index,
    conf.uncertainty_fluctuations,

    -- Dependency Metrics
    dep.upstream_agents,
    dep.downstream_agents,
    dep.dependency_matrix,
    dep.inferred_paths,

    -- Last Activity
    la.last_activity,
    la.last_activity_source

FROM fhq_governance.agent_contracts ac
LEFT JOIN fhq_governance.ars_metrics_v ars ON ac.agent_id = ars.agent_id
LEFT JOIN fhq_cognition.csi_metrics_v csi ON ac.agent_id = csi.agent_id
LEFT JOIN fhq_governance.rbr_metrics_v rbr ON ac.agent_id = rbr.agent_id
LEFT JOIN fhq_governance.tcl_metrics_v tcl ON ac.agent_id = tcl.agent_id
LEFT JOIN fhq_governance.gii_metrics_v gii ON ac.agent_id = gii.agent_id
LEFT JOIN fhq_cognition.eis_metrics_v eis ON ac.agent_id = eis.agent_id
LEFT JOIN fhq_cognition.dds_metrics_v dds ON ac.agent_id = dds.agent_id
LEFT JOIN fhq_cognition.confidence_metrics_v conf ON ac.agent_id = conf.agent_id
LEFT JOIN fhq_cognition.agent_dependency_graph_v dep ON ac.agent_id = dep.agent_id
LEFT JOIN fhq_governance.agent_last_activity_v la ON ac.agent_id = la.agent_id
WHERE ac.contract_status = 'ACTIVE';

-- ============================================================================
-- Section 4: Refresh Materialized View with new data
-- ============================================================================

-- Drop and recreate materialized view with full tooltip data
DROP MATERIALIZED VIEW IF EXISTS fhq_governance.mv_aol_agent_metrics CASCADE;

CREATE MATERIALIZED VIEW fhq_governance.mv_aol_agent_metrics AS
SELECT * FROM fhq_governance.aol_tooltip_data_v;

CREATE UNIQUE INDEX idx_mv_aol_agent_metrics_id ON fhq_governance.mv_aol_agent_metrics(agent_id);

-- Update refresh function
CREATE OR REPLACE FUNCTION fhq_governance.refresh_aol_telemetry()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY fhq_governance.mv_aol_agent_metrics;
END;
$$ LANGUAGE plpgsql;

-- Initial refresh
SELECT fhq_governance.refresh_aol_telemetry();

-- ============================================================================
-- Migration Complete: AOL Tooltip Data Contracts
-- ============================================================================
