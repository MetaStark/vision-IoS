-- ============================================================================
-- IOS-TRUTH-LOOP v2 - Single Instance Proof (Read-Only)
-- Authority: CEO-DIR-2026-039B
-- Purpose: Verify only one orchestrator instance is running
-- Mode: READ-ONLY - No INSERT/UPDATE/DDL
--
-- Logic: Check heartbeat_log for orchestrator entries in last 15 minutes
--        If exactly 1 entry: SINGLE_INSTANCE = true
--        If 0 entries: UNKNOWN (no heartbeat data)
--        If >1 entries: MULTIPLE_INSTANCES (integrity risk)
-- ============================================================================

-- First, discover the heartbeat table location
-- Try common locations: fhq_governance, fhq_monitoring, fhq_operational

-- Check fhq_governance.system_heartbeats
SELECT
    component_name,
    COUNT(*) as heartbeat_count_15m,
    MAX(last_heartbeat) as last_heartbeat,
    CASE
        WHEN COUNT(*) = 0 THEN 'UNKNOWN'
        WHEN COUNT(*) = 1 THEN 'SINGLE_INSTANCE'
        ELSE 'MULTIPLE_INSTANCES'
    END as instance_proof_status,
    CASE
        WHEN COUNT(*) = 0 THEN 'No heartbeat data available'
        WHEN COUNT(*) = 1 THEN 'Single orchestrator confirmed'
        ELSE 'WARNING: Multiple orchestrator instances detected'
    END as instance_proof_message
FROM fhq_governance.system_heartbeats
WHERE component_name ILIKE '%orchestrator%'
AND last_heartbeat >= NOW() - INTERVAL '15 minutes'
GROUP BY component_name;

-- Alternative: Check execution routing for recent activity
SELECT
    'EXECUTION_ROUTING_CHECK' as proof_type,
    COUNT(*) as routing_count_15m,
    COUNT(DISTINCT routing_id) as unique_routings_15m,
    MAX(created_at) as last_routing
FROM fhq_execution.execution_routing_log
WHERE created_at >= NOW() - INTERVAL '15 minutes';

-- Fallback: Check governance actions for orchestrator
SELECT
    'GOVERNANCE_ACTION_CHECK' as proof_type,
    COUNT(*) as orchestrator_actions_15m,
    COUNT(DISTINCT agent_id) as unique_agents,
    MAX(initiated_at) as last_action
FROM fhq_governance.governance_actions_log
WHERE (agent_id ILIKE '%orchestrator%' OR action_type ILIKE '%orchestrator%')
AND initiated_at >= NOW() - INTERVAL '15 minutes';
