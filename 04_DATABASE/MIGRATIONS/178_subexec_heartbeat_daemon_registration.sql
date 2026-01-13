-- Migration 178: Sub-Executive Heartbeat Daemon Registration
-- CEO-DIR-2026-048: Ghost Agent Resolution
--
-- Purpose: Register the subexec_heartbeat_daemon for scheduled execution
-- to prevent Ghost Agent conditions for CDMO, CEIO, CRIO.
--
-- These sub-executives log activity to cnrp_execution_log, but the standard
-- heartbeat probes check governance_actions_log, causing them to appear as
-- Ghost Agents despite actively running.
--
-- Author: STIG (CTO)
-- Date: 2026-01-14

-- Register the daemon
INSERT INTO fhq_governance.task_registry (
    task_name,
    task_type,
    agent_id,
    description,
    task_description,
    domain,
    assigned_to,
    status,
    enabled,
    task_config,
    metadata,
    created_at,
    updated_at
) VALUES (
    'subexec_heartbeat_daemon',
    'CNRP_SUPPORT',
    'STIG',
    'Sub-Executive Heartbeat Daemon - Updates heartbeats for CDMO, CEIO, CRIO based on CNRP execution activity',
    'CEO-DIR-2026-048: Ghost Agent Resolution. Probes cnrp_execution_log and updates agent_heartbeats.',
    'GOVERNANCE',
    'STIG',
    'active',
    true,
    jsonb_build_object(
        'priority', 1,
        'schedule', 'every_5min',
        'function_path', '03_FUNCTIONS/subexec_heartbeat_daemon.py',
        'directive', 'CEO-DIR-2026-048',
        'target_agents', ARRAY['CDMO', 'CEIO', 'CRIO']
    ),
    jsonb_build_object(
        'registered_by', 'STIG',
        'registered_at', NOW(),
        'purpose', 'Prevent Ghost Agent condition by updating sub-executive heartbeats based on CNRP activity'
    ),
    NOW(),
    NOW()
)
ON CONFLICT (task_name) DO UPDATE SET
    enabled = true,
    task_config = EXCLUDED.task_config,
    updated_at = NOW();

-- Log migration
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'DAEMON_REGISTRATION',
    'subexec_heartbeat_daemon',
    'TASK',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO-DIR-2026-048: Register sub-executive heartbeat daemon to resolve Ghost Agent condition',
    jsonb_build_object(
        'migration_id', 178,
        'directive', 'CEO-DIR-2026-048',
        'target_agents', ARRAY['CDMO', 'CEIO', 'CRIO'],
        'schedule', 'every_5min',
        'finding_resolved', 'VEGA-F001'
    )
);
