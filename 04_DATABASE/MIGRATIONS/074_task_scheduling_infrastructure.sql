-- ============================================================
-- MIGRATION: 074_task_scheduling_infrastructure.sql
-- PURPOSE: Add scheduling columns to task_registry for orchestrator
-- AUTHORITY: ADR-007 (Orchestrator Architecture)
-- OWNER: STIG
-- GATE: G2 (Technical Implementation)
-- ============================================================

BEGIN;

-- Add schedule columns to task_registry
ALTER TABLE fhq_governance.task_registry
ADD COLUMN IF NOT EXISTS schedule_cron text,
ADD COLUMN IF NOT EXISTS schedule_timezone text DEFAULT 'UTC',
ADD COLUMN IF NOT EXISTS schedule_description text,
ADD COLUMN IF NOT EXISTS schedule_enabled boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS last_scheduled_run timestamptz,
ADD COLUMN IF NOT EXISTS next_scheduled_run timestamptz,
ADD COLUMN IF NOT EXISTS run_count integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_run_duration_ms integer,
ADD COLUMN IF NOT EXISTS last_run_status text;

-- Add constraint for schedule_cron format
COMMENT ON COLUMN fhq_governance.task_registry.schedule_cron IS 'Cron expression (e.g., "5 0 * * *" for daily at 00:05)';
COMMENT ON COLUMN fhq_governance.task_registry.schedule_enabled IS 'Whether this schedule is active';
COMMENT ON COLUMN fhq_governance.task_registry.last_scheduled_run IS 'Timestamp of last scheduled execution';
COMMENT ON COLUMN fhq_governance.task_registry.next_scheduled_run IS 'Calculated next run time';

-- Create index for scheduler queries
CREATE INDEX IF NOT EXISTS idx_task_registry_schedule
ON fhq_governance.task_registry(schedule_enabled, next_scheduled_run)
WHERE schedule_enabled = true;

-- Update existing tasks with schedule information
-- IoS-012 Paper Execution Loop: Every 5 minutes
UPDATE fhq_governance.task_registry
SET schedule_cron = '*/5 * * * *',
    schedule_timezone = 'UTC',
    schedule_description = 'Every 5 minutes',
    schedule_enabled = true
WHERE task_name = 'ios012_g3_system_loop';

-- IoS-013 HCP Lab Generator: Every 5 minutes with 30s offset
UPDATE fhq_governance.task_registry
SET schedule_cron = '*/5 * * * *',
    schedule_timezone = 'UTC',
    schedule_description = 'Every 5 minutes (30s offset from IoS-012)',
    schedule_enabled = true
WHERE task_name = 'ios013_hcp_g3_runner';

-- IoS-007 Alpha Graph Generator: Daily at 00:10 UTC
UPDATE fhq_governance.task_registry
SET schedule_cron = '10 0 * * *',
    schedule_timezone = 'UTC',
    schedule_description = 'Daily at 00:10 UTC',
    schedule_enabled = true
WHERE task_name = 'ios007_g1_global_execution';

-- IoS-003 Regime Update: Daily at 00:15 UTC (after data ingest)
UPDATE fhq_governance.task_registry
SET schedule_cron = '15 0 * * *',
    schedule_timezone = 'UTC',
    schedule_description = 'Daily at 00:15 UTC',
    schedule_enabled = true
WHERE task_name = 'ios003_daily_regime_update';

-- IoS-006 Macro Ingest: Daily at 00:05 UTC
UPDATE fhq_governance.task_registry
SET schedule_cron = '5 0 * * *',
    schedule_timezone = 'UTC',
    schedule_description = 'Daily at 00:05 UTC',
    schedule_enabled = true
WHERE task_name = 'ios006_g2_macro_ingest';

-- Daily OHLCV Ingest: Daily at 00:05 UTC
UPDATE fhq_governance.task_registry
SET schedule_cron = '5 0 * * *',
    schedule_timezone = 'UTC',
    schedule_description = 'Daily at 00:05 UTC',
    schedule_enabled = true
WHERE task_name = 'daily_ingest_worker';

-- FINN Night Research: Nightly at 01:00 UTC (after market close)
UPDATE fhq_governance.task_registry
SET schedule_cron = '0 1 * * *',
    schedule_timezone = 'UTC',
    schedule_description = 'Nightly at 01:00 UTC',
    schedule_enabled = true
WHERE task_name = 'finn_night_research_executor';

-- Log the migration
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    hash_chain_id
) VALUES (
    'SCHEMA_MIGRATION',
    'fhq_governance.task_registry',
    'TABLE',
    'STIG',
    'COMPLETED',
    'Migration 074: Added scheduling columns (schedule_cron, schedule_enabled, etc.) for orchestrator automation per ADR-007',
    'HC-STIG-074-' || to_char(now(), 'YYYYMMDD-HH24MISS')
);

COMMIT;
