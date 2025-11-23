-- MIGRATION 017: REGISTER VISION-IOS ORCHESTRATOR v1.0
-- =============================================================================
--
-- Authority: LARS (CEO Directive - Vision-IoS Orchestrator)
-- Purpose: Register Vision-IoS Orchestrator as production component
-- Compliance: ADR-007 (Orchestrator Architecture), ADR-010 (Reconciliation)
--
-- Orchestrator:
--   Version: 1.0.0
--   Agent: LARS
--   Function: Execute Vision-IoS functions in coordinated cycles
--   Integration: Foundation governance + Vision-IoS functions
--
-- Tables Created:
--   - vision_core.orchestrator_schedule (cron/scheduling configuration)
--   - vision_core.orchestrator_metrics (performance tracking)
--
-- =============================================================================

BEGIN;

-- =============================================================================
-- VERIFY PREREQUISITES
-- =============================================================================

DO $$
DECLARE
    task_registry_exists BOOLEAN;
    governance_log_exists BOOLEAN;
    execution_state_exists BOOLEAN;
    vision_functions_count INTEGER;
BEGIN
    -- Check fhq_governance.task_registry exists
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'fhq_governance'
          AND table_name = 'task_registry'
    ) INTO task_registry_exists;

    -- Check fhq_governance.governance_actions_log exists
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'fhq_governance'
          AND table_name = 'governance_actions_log'
    ) INTO governance_log_exists;

    -- Check vision_core.execution_state exists
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'vision_core'
          AND table_name = 'execution_state'
    ) INTO execution_state_exists;

    IF NOT task_registry_exists THEN
        RAISE EXCEPTION 'fhq_governance.task_registry does not exist. Foundation migration required.';
    END IF;

    IF NOT governance_log_exists THEN
        RAISE EXCEPTION 'fhq_governance.governance_actions_log does not exist. Foundation migration required.';
    END IF;

    IF NOT execution_state_exists THEN
        RAISE EXCEPTION 'vision_core.execution_state does not exist. Run migration 001 first.';
    END IF;

    -- Check Vision-IoS functions are registered
    SELECT COUNT(*) INTO vision_functions_count
    FROM fhq_governance.task_registry
    WHERE task_type = 'VISION_FUNCTION' AND enabled = TRUE;

    IF vision_functions_count < 3 THEN
        RAISE EXCEPTION 'Expected 3 Vision-IoS functions registered, found %. Run migration 002 first.', vision_functions_count;
    END IF;

    RAISE NOTICE '✅ Prerequisites verified: % Vision-IoS functions registered', vision_functions_count;
END $$;


-- =============================================================================
-- CREATE ORCHESTRATOR SCHEDULE TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS vision_core.orchestrator_schedule (
    schedule_id SERIAL PRIMARY KEY,
    schedule_name VARCHAR(100) UNIQUE NOT NULL,
    schedule_type VARCHAR(50) NOT NULL CHECK (schedule_type IN ('CRON', 'INTERVAL', 'MANUAL', 'EVENT_DRIVEN')),
    cron_expression VARCHAR(100),           -- e.g., '0 * * * *' for hourly
    interval_seconds INTEGER,                -- e.g., 3600 for hourly
    enabled BOOLEAN DEFAULT TRUE,
    last_execution_at TIMESTAMPTZ,
    next_execution_at TIMESTAMPTZ,
    execution_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    config JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE vision_core.orchestrator_schedule IS 'Orchestrator execution schedule and configuration';
COMMENT ON COLUMN vision_core.orchestrator_schedule.schedule_type IS 'CRON (cron expression), INTERVAL (seconds), MANUAL (on-demand), EVENT_DRIVEN (triggered)';
COMMENT ON COLUMN vision_core.orchestrator_schedule.cron_expression IS 'Standard cron expression (if schedule_type = CRON)';
COMMENT ON COLUMN vision_core.orchestrator_schedule.interval_seconds IS 'Execution interval in seconds (if schedule_type = INTERVAL)';

-- Insert default schedule (hourly execution)
INSERT INTO vision_core.orchestrator_schedule (
    schedule_name,
    schedule_type,
    cron_expression,
    interval_seconds,
    enabled,
    config
) VALUES (
    'vision_ios_hourly',
    'INTERVAL',
    NULL,
    3600,  -- 1 hour
    TRUE,
    jsonb_build_object(
        'description', 'Hourly execution of Vision-IoS functions',
        'timezone', 'UTC',
        'retry_on_failure', true,
        'max_retries', 3
    )
)
ON CONFLICT (schedule_name) DO UPDATE SET
    interval_seconds = EXCLUDED.interval_seconds,
    config = EXCLUDED.config,
    updated_at = NOW();


-- =============================================================================
-- CREATE ORCHESTRATOR METRICS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS vision_core.orchestrator_metrics (
    metric_id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(100) NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),

    -- Index for querying
    INDEX idx_orchestrator_metrics_cycle (cycle_id),
    INDEX idx_orchestrator_metrics_type (metric_type),
    INDEX idx_orchestrator_metrics_recorded (recorded_at DESC)
);

COMMENT ON TABLE vision_core.orchestrator_metrics IS 'Performance metrics for orchestrator execution cycles';
COMMENT ON COLUMN vision_core.orchestrator_metrics.metric_type IS 'EXECUTION_TIME, SUCCESS_RATE, FUNCTION_DURATION, ERROR_RATE, etc.';


-- =============================================================================
-- CREATE ORCHESTRATOR RECONCILIATION RULES
-- =============================================================================

-- Create reconciliation field weights for orchestrator (ADR-010 compliance)
CREATE TABLE IF NOT EXISTS fhq_meta.reconciliation_field_weights (
    weight_id SERIAL PRIMARY KEY,
    component_name VARCHAR(100) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    criticality_weight NUMERIC(3,1) NOT NULL CHECK (criticality_weight BETWEEN 0.1 AND 1.0),
    tolerance_type VARCHAR(50),
    tolerance_value NUMERIC,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(component_name, field_name)
);

COMMENT ON TABLE fhq_meta.reconciliation_field_weights IS 'ADR-010 field-level reconciliation weights and tolerances';

-- Insert orchestrator reconciliation rules
INSERT INTO fhq_meta.reconciliation_field_weights (
    component_name,
    field_name,
    criticality_weight,
    tolerance_type,
    tolerance_value,
    description
) VALUES
    ('vision_ios_orchestrator', 'cycle_id', 1.0, 'EXACT', 0, 'Cycle identifier must match exactly'),
    ('vision_ios_orchestrator', 'tasks_executed', 1.0, 'EXACT', 0, 'Number of tasks must match'),
    ('vision_ios_orchestrator', 'success_count', 0.8, 'EXACT', 0, 'Success count is critical'),
    ('vision_ios_orchestrator', 'failure_count', 0.8, 'EXACT', 0, 'Failure count is critical'),
    ('vision_ios_orchestrator', 'execution_timestamp', 0.3, 'TIMESTAMP', 5.0, 'Timestamp tolerance: 5 seconds'),
    ('vision_ios_orchestrator', 'orchestrator_version', 0.5, 'EXACT', 0, 'Version should match')
ON CONFLICT (component_name, field_name) DO UPDATE SET
    criticality_weight = EXCLUDED.criticality_weight,
    tolerance_type = EXCLUDED.tolerance_type,
    tolerance_value = EXCLUDED.tolerance_value,
    description = EXCLUDED.description,
    updated_at = NOW();


-- =============================================================================
-- REGISTER ORCHESTRATOR AS COMPONENT
-- =============================================================================

-- Register orchestrator in task registry as a system component
INSERT INTO fhq_governance.task_registry (
    task_name,
    task_type,
    agent_id,
    task_description,
    task_config,
    enabled
) VALUES (
    'vision_ios_orchestrator_v1',
    'SYSTEM_ORCHESTRATOR',
    'LARS',
    'Vision-IoS Orchestrator v1.0 - Executes Vision-IoS functions (FINN, STIG, LARS) in coordinated cycles. Implements ADR-007 orchestration, ADR-010 reconciliation, and ADR-002 audit logging.',
    jsonb_build_object(
        'version', '1.0.0',
        'orchestrator_path', '05_ORCHESTRATOR/orchestrator_v1.py',
        'execution_mode', 'INTERVAL',
        'default_interval_seconds', 3600,
        'manages_tasks', ARRAY[
            'vision_signal_inference_baseline',
            'vision_noise_floor_estimator',
            'vision_meta_state_sync'
        ],
        'compliance', ARRAY['ADR-002', 'ADR-007', 'ADR-010'],
        'capabilities', ARRAY[
            'SCHEDULED_EXECUTION',
            'CONTINUOUS_MODE',
            'DRY_RUN_MODE',
            'SINGLE_FUNCTION_EXECUTION',
            'GOVERNANCE_LOGGING',
            'STATE_RECONCILIATION',
            'EVIDENCE_GENERATION'
        ],
        'deployment_date', '2025-11-23'
    ),
    TRUE
)
ON CONFLICT (task_name) DO UPDATE SET
    task_description = EXCLUDED.task_description,
    task_config = EXCLUDED.task_config,
    updated_at = NOW();


-- =============================================================================
-- LOG ORCHESTRATOR REGISTRATION TO GOVERNANCE
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    agent_id,
    decision,
    metadata,
    hash_chain_id,
    signature,
    timestamp
) VALUES (
    'VISION_ORCHESTRATOR_REGISTRATION',
    'LARS',
    'APPROVED',
    jsonb_build_object(
        'migration', '017_orchestrator_registration.sql',
        'orchestrator_version', '1.0.0',
        'orchestrator_name', 'vision_ios_orchestrator_v1',
        'orchestrator_path', '05_ORCHESTRATOR/orchestrator_v1.py',
        'manages_functions', 3,
        'function_names', ARRAY[
            'vision_signal_inference_baseline',
            'vision_noise_floor_estimator',
            'vision_meta_state_sync'
        ],
        'execution_modes', ARRAY['single_cycle', 'continuous', 'dry_run', 'filtered'],
        'default_schedule', 'hourly',
        'compliance', 'ADR-007 Orchestrator, ADR-010 Reconciliation, ADR-002 Audit',
        'status', 'PRODUCTION_READY',
        'capabilities', ARRAY[
            'Reads tasks from fhq_governance.task_registry',
            'Executes Vision-IoS functions via subprocess',
            'Logs to fhq_governance.governance_actions_log',
            'Writes state to vision_core.execution_state',
            'Tracks metrics in vision_core.orchestrator_metrics',
            'Supports scheduled and on-demand execution',
            'Implements timeout protection',
            'Generates hash chain IDs',
            'Produces execution evidence bundles'
        ]
    ),
    'HC-MIGRATION-017-' || MD5(NOW()::TEXT),
    'GENESIS_SIGNATURE_LARS_' || MD5(NOW()::TEXT),
    NOW()
);


-- =============================================================================
-- CREATE HELPER VIEWS
-- =============================================================================

-- View: Latest orchestrator executions
CREATE OR REPLACE VIEW vision_core.v_orchestrator_latest_executions AS
SELECT
    action_id,
    timestamp,
    decision AS cycle_status,
    metadata->>'cycle_id' AS cycle_id,
    (metadata->>'tasks_executed')::INTEGER AS tasks_executed,
    (metadata->>'success_count')::INTEGER AS success_count,
    (metadata->>'failure_count')::INTEGER AS failure_count,
    metadata
FROM fhq_governance.governance_actions_log
WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE'
ORDER BY timestamp DESC
LIMIT 100;

COMMENT ON VIEW vision_core.v_orchestrator_latest_executions IS 'Latest 100 orchestrator execution cycles';


-- View: Orchestrator performance summary
CREATE OR REPLACE VIEW vision_core.v_orchestrator_performance AS
WITH recent_cycles AS (
    SELECT
        (metadata->>'cycle_id') AS cycle_id,
        decision AS cycle_status,
        (metadata->>'tasks_executed')::INTEGER AS tasks_executed,
        (metadata->>'success_count')::INTEGER AS success_count,
        (metadata->>'failure_count')::INTEGER AS failure_count,
        timestamp
    FROM fhq_governance.governance_actions_log
    WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE'
      AND timestamp > NOW() - INTERVAL '7 days'
)
SELECT
    COUNT(*) AS total_cycles_7d,
    SUM(tasks_executed) AS total_tasks_executed,
    SUM(success_count) AS total_successes,
    SUM(failure_count) AS total_failures,
    ROUND(100.0 * SUM(success_count) / NULLIF(SUM(tasks_executed), 0), 2) AS success_rate_percent,
    MIN(timestamp) AS earliest_cycle,
    MAX(timestamp) AS latest_cycle
FROM recent_cycles;

COMMENT ON VIEW vision_core.v_orchestrator_performance IS 'Orchestrator performance summary (last 7 days)';


-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify orchestrator registered
DO $$
DECLARE
    orchestrator_registered BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM fhq_governance.task_registry
        WHERE task_type = 'SYSTEM_ORCHESTRATOR'
          AND task_name = 'vision_ios_orchestrator_v1'
          AND enabled = TRUE
    ) INTO orchestrator_registered;

    IF NOT orchestrator_registered THEN
        RAISE EXCEPTION 'Orchestrator registration failed';
    END IF;

    RAISE NOTICE '✅ Vision-IoS Orchestrator v1.0 registered successfully';
END $$;


-- Display orchestrator configuration
SELECT
    task_id,
    task_name,
    agent_id,
    task_type,
    enabled,
    task_config->'version' AS version,
    task_config->'default_interval_seconds' AS interval_seconds,
    task_config->'manages_tasks' AS manages_functions,
    created_at
FROM fhq_governance.task_registry
WHERE task_name = 'vision_ios_orchestrator_v1';


-- Display schedule configuration
SELECT
    schedule_id,
    schedule_name,
    schedule_type,
    interval_seconds,
    enabled,
    execution_count,
    failure_count,
    last_execution_at,
    created_at
FROM vision_core.orchestrator_schedule
WHERE schedule_name = 'vision_ios_hourly';


-- Display reconciliation rules
SELECT
    weight_id,
    component_name,
    field_name,
    criticality_weight,
    tolerance_type,
    tolerance_value,
    description
FROM fhq_meta.reconciliation_field_weights
WHERE component_name = 'vision_ios_orchestrator'
ORDER BY criticality_weight DESC, field_name;


-- =============================================================================
-- MIGRATION COMPLETE
-- =============================================================================

COMMIT;


-- Final summary
SELECT
    'MIGRATION 017 COMPLETE' AS status,
    'Vision-IoS Orchestrator v1.0 Registered' AS description,
    COUNT(*) FILTER (WHERE task_type = 'SYSTEM_ORCHESTRATOR') AS orchestrators_registered,
    COUNT(*) FILTER (WHERE task_type = 'VISION_FUNCTION') AS functions_managed
FROM fhq_governance.task_registry
WHERE task_type IN ('SYSTEM_ORCHESTRATOR', 'VISION_FUNCTION')
  AND enabled = TRUE;

\echo ''
\echo '═══════════════════════════════════════════════════════════'
\echo 'MIGRATION 017: VISION-IOS ORCHESTRATOR v1.0 REGISTERED'
\echo '═══════════════════════════════════════════════════════════'
\echo '✅ Orchestrator registered in task registry'
\echo '✅ Schedule table created (default: hourly execution)'
\echo '✅ Metrics table created'
\echo '✅ Reconciliation rules defined (ADR-010 compliance)'
\echo '✅ Performance views created'
\echo '✅ Governance logging complete'
\echo '═══════════════════════════════════════════════════════════'
\echo ''
\echo 'Next steps:'
\echo '  1. Run orchestrator: python 05_ORCHESTRATOR/orchestrator_v1.py'
\echo '  2. Dry run test: python 05_ORCHESTRATOR/orchestrator_v1.py --dry-run'
\echo '  3. Continuous mode: python 05_ORCHESTRATOR/orchestrator_v1.py --continuous'
\echo '  4. Check status: SELECT * FROM vision_core.v_orchestrator_latest_executions;'
