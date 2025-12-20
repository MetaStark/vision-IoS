-- ============================================================================
-- Migration 104: AOL Materialized Views
-- CEO Directive 2026-FHQ-FCC-AOL-01 Section 3
-- ============================================================================
--
-- Authority: ADR-001, ADR-006, ADR-009, ADR-013, ADR-018, ADR-019
-- Classification: CONSTITUTIONAL - Glass Wall Observability Layer
--
-- This migration creates materialized views for Agent Observability Layer (AOL)
-- metrics to improve query performance for the dashboard.
-- ============================================================================

-- ============================================================================
-- Section 1: Agent Metrics Materialized View
-- ============================================================================

DROP MATERIALIZED VIEW IF EXISTS fhq_governance.mv_agent_metrics CASCADE;

CREATE MATERIALIZED VIEW fhq_governance.mv_agent_metrics AS
WITH research_stats AS (
  SELECT
    agent_id,
    COUNT(*) as total_events,
    COUNT(*) FILTER (WHERE status IN ('SUCCESS', 'COMPLETED')) as success_count,
    COUNT(*) FILTER (WHERE status IN ('FAILED', 'ERROR')) as failure_count,
    MAX(created_at) as last_activity
  FROM fhq_governance.research_log
  WHERE created_at >= NOW() - INTERVAL '7 days'
  GROUP BY agent_id
),
entropy_stats AS (
  SELECT
    executed_by as agent_id,
    COUNT(*) as total_ops,
    COUNT(*) FILTER (WHERE propagation_blocked = true) as blocked_ops
  FROM fhq_governance.causal_entropy_audit
  WHERE executed_at >= NOW() - INTERVAL '7 days'
  GROUP BY executed_by
),
task_stats AS (
  SELECT
    created_by as agent_id,
    COUNT(*) as total_tasks,
    COUNT(*) FILTER (WHERE status = 'COMPLETED') as completed_tasks
  FROM fhq_governance.scheduled_tasks
  WHERE created_at >= NOW() - INTERVAL '7 days'
  GROUP BY created_by
)
SELECT
  ac.agent_id,
  ac.contract_status,
  ac.mandate_scope,
  COALESCE(rs.success_count, 0)::integer as success_count_7d,
  COALESCE(rs.failure_count, 0)::integer as failure_count_7d,
  CASE
    WHEN COALESCE(rs.success_count, 0) + COALESCE(rs.failure_count, 0) > 0
    THEN ROUND((COALESCE(rs.success_count, 0)::numeric /
          (COALESCE(rs.success_count, 0) + COALESCE(rs.failure_count, 0))) * 100)::integer
    ELSE 100
  END as ars_score,
  COALESCE(rs.total_events, 0)::integer as total_events,
  CASE
    WHEN COALESCE(rs.total_events, 0) > 0
    THEN LEAST(100, ROUND(80 + (COALESCE(rs.total_events, 0)::numeric / 10)))::integer
    ELSE 50
  END as csi_score,
  0 as api_requests_24h,
  0 as api_requests_7d,
  COALESCE(es.blocked_ops, 0)::integer as blocked_operations,
  CASE
    WHEN COALESCE(es.blocked_ops, 0) > 5 THEN 'RED'
    WHEN COALESCE(es.blocked_ops, 0) > 0 THEN 'YELLOW'
    ELSE 'GREEN'
  END as gii_state,
  COALESCE(ts.completed_tasks, 0)::integer as tasks_completed_7d,
  rs.last_activity,
  NOW() as refreshed_at
FROM fhq_governance.agent_contracts ac
LEFT JOIN research_stats rs ON ac.agent_id = rs.agent_id
LEFT JOIN entropy_stats es ON ac.agent_id = es.agent_id
LEFT JOIN task_stats ts ON ac.agent_id = ts.agent_id
WHERE ac.contract_status = 'ACTIVE';

-- Create unique index for concurrent refresh
CREATE UNIQUE INDEX idx_mv_agent_metrics_agent_id
ON fhq_governance.mv_agent_metrics (agent_id);

-- Create index for GII state queries
CREATE INDEX idx_mv_agent_metrics_gii_state
ON fhq_governance.mv_agent_metrics (gii_state);

-- ============================================================================
-- Section 2: Agent Integrity Ledger View
-- ============================================================================

DROP MATERIALIZED VIEW IF EXISTS fhq_governance.mv_agent_integrity_ledger CASCADE;

CREATE MATERIALIZED VIEW fhq_governance.mv_agent_integrity_ledger AS
SELECT
  log_id,
  agent_id,
  event_type,
  status,
  quad_hash,
  created_at,
  CASE
    WHEN status IN ('FAILED', 'ERROR') THEN 'ALERT'
    WHEN status IN ('SUCCESS', 'COMPLETED') THEN 'OK'
    ELSE 'INFO'
  END as governance_flag
FROM fhq_governance.research_log
ORDER BY created_at DESC
LIMIT 100;

-- Create index for fast lookups
CREATE INDEX idx_mv_agent_integrity_ledger_created
ON fhq_governance.mv_agent_integrity_ledger (created_at DESC);

-- ============================================================================
-- Section 3: System Health Summary View
-- ============================================================================

DROP MATERIALIZED VIEW IF EXISTS fhq_governance.mv_system_health_summary CASCADE;

CREATE MATERIALIZED VIEW fhq_governance.mv_system_health_summary AS
SELECT
  COUNT(*) as total_agents,
  COUNT(*) FILTER (WHERE gii_state = 'GREEN') as green_agents,
  COUNT(*) FILTER (WHERE gii_state = 'YELLOW') as yellow_agents,
  COUNT(*) FILTER (WHERE gii_state = 'RED') as red_agents,
  ROUND(AVG(ars_score)) as avg_ars,
  ROUND(AVG(csi_score)) as avg_csi,
  SUM(api_requests_24h) as total_api_requests_24h,
  SUM(blocked_operations) as total_blocked_ops,
  NOW() as refreshed_at
FROM fhq_governance.mv_agent_metrics;

-- ============================================================================
-- Section 4: Refresh Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.refresh_aol_views()
RETURNS void AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY fhq_governance.mv_agent_metrics;
  REFRESH MATERIALIZED VIEW fhq_governance.mv_agent_integrity_ledger;
  REFRESH MATERIALIZED VIEW fhq_governance.mv_system_health_summary;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Section 5: Initial Refresh
-- ============================================================================

SELECT fhq_governance.refresh_aol_views();

-- ============================================================================
-- Section 6: Audit Log Entry
-- ============================================================================

INSERT INTO fhq_governance.causal_entropy_audit (
  operation,
  gate,
  entity_type,
  entity_id,
  executed_by,
  executed_at
) VALUES (
  'MIGRATION',
  'G1',
  'SCHEMA',
  '104_aol_materialized_views',
  'STIG',
  NOW()
);

-- ============================================================================
-- Migration Complete
-- ============================================================================
