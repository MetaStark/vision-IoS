-- VISION-IOS ORCHESTRATOR v1.0 - LIVE TEST SUITE
-- =============================================================================
--
-- Purpose: Verify orchestrator execution, evidence generation, and governance
--
-- Tests:
--   1. Orchestrator registration verification
--   2. Orchestrator execution evidence
--   3. Function execution evidence (cascading)
--   4. Governance logging verification
--   5. State reconciliation verification
--   6. Performance metrics verification
--   7. ADR compliance verification
--
-- Prerequisites:
--   - Migration 001 (Vision foundation schemas)
--   - Migration 002 (Vision functions registration)
--   - Migration 017 (Orchestrator registration)
--   - At least ONE orchestrator cycle has been executed
--
-- Usage:
--   psql $DATABASE_URL -f 05_ORCHESTRATOR/test_orchestrator_v1_live.sql
--
-- =============================================================================

\set QUIET on
\set ON_ERROR_STOP on

\echo ''
\echo '══════════════════════════════════════════════════════════════════'
\echo 'VISION-IOS ORCHESTRATOR v1.0 - LIVE TEST SUITE'
\echo '══════════════════════════════════════════════════════════════════'
\echo ''

-- =============================================================================
-- TEST 1: ORCHESTRATOR REGISTRATION VERIFICATION
-- =============================================================================

\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo 'TEST 1: Orchestrator Registration Verification'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo ''

SELECT
    '✅ Test 1.1: Orchestrator registered in task registry' AS test,
    CASE
        WHEN COUNT(*) = 1 THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    COUNT(*) AS registered_count
FROM fhq_governance.task_registry
WHERE task_type = 'SYSTEM_ORCHESTRATOR'
  AND task_name = 'vision_ios_orchestrator_v1'
  AND enabled = TRUE;

\echo ''

SELECT
    '✅ Test 1.2: Orchestrator manages correct functions' AS test,
    CASE
        WHEN jsonb_array_length(task_config->'manages_tasks') = 3 THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    task_config->'manages_tasks' AS managed_functions
FROM fhq_governance.task_registry
WHERE task_name = 'vision_ios_orchestrator_v1';

\echo ''

SELECT
    '✅ Test 1.3: Orchestrator schedule configured' AS test,
    CASE
        WHEN COUNT(*) > 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    MAX(interval_seconds) AS interval_seconds,
    MAX(enabled::TEXT) AS enabled
FROM vision_core.orchestrator_schedule
WHERE schedule_name = 'vision_ios_hourly';

\echo ''

-- Display orchestrator configuration
\echo 'Orchestrator Configuration:'
\echo ''

SELECT
    task_id,
    task_name,
    agent_id,
    task_config->'version' AS version,
    task_config->'execution_mode' AS mode,
    task_config->'default_interval_seconds' AS interval,
    enabled,
    created_at
FROM fhq_governance.task_registry
WHERE task_name = 'vision_ios_orchestrator_v1';


-- =============================================================================
-- TEST 2: ORCHESTRATOR EXECUTION EVIDENCE
-- =============================================================================

\echo ''
\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo 'TEST 2: Orchestrator Execution Evidence'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo ''

SELECT
    '✅ Test 2.1: Orchestrator cycles have been executed' AS test,
    CASE
        WHEN COUNT(*) > 0 THEN 'PASS (' || COUNT(*) || ' cycles found)'
        ELSE 'FAIL (no cycles executed yet)'
    END AS result,
    COUNT(*) AS cycle_count
FROM fhq_governance.governance_actions_log
WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE';

\echo ''

SELECT
    '✅ Test 2.2: Cycle start events logged' AS test,
    CASE
        WHEN COUNT(*) > 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    COUNT(*) AS start_events
FROM fhq_governance.governance_actions_log
WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE_START';

\echo ''

SELECT
    '✅ Test 2.3: All cycles have hash chains' AS test,
    CASE
        WHEN COUNT(*) FILTER (WHERE hash_chain_id IS NULL) = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    COUNT(*) AS total_cycles,
    COUNT(*) FILTER (WHERE hash_chain_id IS NOT NULL) AS with_hash_chain
FROM fhq_governance.governance_actions_log
WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE';

\echo ''

SELECT
    '✅ Test 2.4: All cycles have signatures' AS test,
    CASE
        WHEN COUNT(*) FILTER (WHERE signature IS NULL) = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    COUNT(*) AS total_cycles,
    COUNT(*) FILTER (WHERE signature IS NOT NULL) AS with_signature
FROM fhq_governance.governance_actions_log
WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE';

\echo ''

-- Display latest orchestrator executions
\echo 'Latest Orchestrator Cycles:'
\echo ''

SELECT
    action_id,
    TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS executed_at,
    decision AS cycle_status,
    metadata->>'cycle_id' AS cycle_id,
    (metadata->>'tasks_executed')::INTEGER AS tasks,
    (metadata->>'success_count')::INTEGER AS successes,
    (metadata->>'failure_count')::INTEGER AS failures
FROM fhq_governance.governance_actions_log
WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE'
ORDER BY timestamp DESC
LIMIT 5;


-- =============================================================================
-- TEST 3: FUNCTION EXECUTION EVIDENCE (CASCADING)
-- =============================================================================

\echo ''
\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo 'TEST 3: Function Execution Evidence (Cascading)'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo ''

SELECT
    '✅ Test 3.1: Vision functions executed by orchestrator' AS test,
    CASE
        WHEN COUNT(*) > 0 THEN 'PASS (' || COUNT(*) || ' executions)'
        ELSE 'PENDING (no function executions yet)'
    END AS result,
    COUNT(*) AS execution_count
FROM fhq_governance.governance_actions_log
WHERE action_type = 'VISION_FUNCTION_EXECUTION'
  AND timestamp > (
      SELECT MIN(timestamp)
      FROM fhq_governance.governance_actions_log
      WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE'
  );

\echo ''

SELECT
    '✅ Test 3.2: All 3 functions executed in recent cycles' AS test,
    CASE
        WHEN COUNT(DISTINCT metadata->>'function') >= 3 THEN 'PASS'
        ELSE 'PENDING (not all functions executed yet)'
    END AS result,
    COUNT(DISTINCT metadata->>'function') AS unique_functions
FROM fhq_governance.governance_actions_log
WHERE action_type = 'VISION_FUNCTION_EXECUTION'
  AND timestamp > NOW() - INTERVAL '24 hours';

\echo ''

SELECT
    '✅ Test 3.3: Function executions have evidence' AS test,
    CASE
        WHEN COUNT(*) FILTER (WHERE jsonb_typeof(metadata) = 'object') = COUNT(*) THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    COUNT(*) AS total_executions,
    COUNT(*) FILTER (WHERE jsonb_typeof(metadata) = 'object') AS with_metadata
FROM fhq_governance.governance_actions_log
WHERE action_type = 'VISION_FUNCTION_EXECUTION';

\echo ''

-- Display function execution breakdown
\echo 'Function Execution Breakdown (Last 24 hours):'
\echo ''

SELECT
    metadata->>'function' AS function_name,
    metadata->>'agent_id' AS agent,
    COUNT(*) AS execution_count,
    COUNT(*) FILTER (WHERE decision = 'COMPLETED') AS successful,
    COUNT(*) FILTER (WHERE decision != 'COMPLETED') AS failed
FROM fhq_governance.governance_actions_log
WHERE action_type = 'VISION_FUNCTION_EXECUTION'
  AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY metadata->>'function', metadata->>'agent_id'
ORDER BY function_name;


-- =============================================================================
-- TEST 4: GOVERNANCE LOGGING VERIFICATION
-- =============================================================================

\echo ''
\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo 'TEST 4: Governance Logging Verification (ADR-002)'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo ''

SELECT
    '✅ Test 4.1: Orchestrator registration logged' AS test,
    CASE
        WHEN COUNT(*) > 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    COUNT(*) AS log_count
FROM fhq_governance.governance_actions_log
WHERE action_type = 'VISION_ORCHESTRATOR_REGISTRATION';

\echo ''

SELECT
    '✅ Test 4.2: All orchestrator actions have LARS agent_id' AS test,
    CASE
        WHEN COUNT(*) FILTER (WHERE agent_id != 'LARS') = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    COUNT(*) AS total_actions,
    COUNT(*) FILTER (WHERE agent_id = 'LARS') AS lars_actions
FROM fhq_governance.governance_actions_log
WHERE action_type LIKE 'VISION_ORCHESTRATOR%';

\echo ''

SELECT
    '✅ Test 4.3: Hash chains follow naming convention' AS test,
    CASE
        WHEN COUNT(*) FILTER (WHERE hash_chain_id LIKE 'HC-LARS-ORCHESTRATOR-%') = COUNT(*) THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    COUNT(*) AS total_cycles,
    COUNT(*) FILTER (WHERE hash_chain_id LIKE 'HC-LARS-ORCHESTRATOR-%') AS valid_chains
FROM fhq_governance.governance_actions_log
WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE';

\echo ''

-- Display governance log summary
\echo 'Governance Log Summary (Orchestrator Actions):'
\echo ''

SELECT
    action_type,
    COUNT(*) AS count,
    MIN(timestamp) AS first_occurrence,
    MAX(timestamp) AS last_occurrence
FROM fhq_governance.governance_actions_log
WHERE action_type LIKE 'VISION_ORCHESTRATOR%'
GROUP BY action_type
ORDER BY action_type;


-- =============================================================================
-- TEST 5: STATE RECONCILIATION VERIFICATION
-- =============================================================================

\echo ''
\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo 'TEST 5: State Reconciliation Verification (ADR-010)'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo ''

SELECT
    '✅ Test 5.1: Orchestrator state written to vision_core' AS test,
    CASE
        WHEN COUNT(*) > 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    COUNT(*) AS state_count
FROM vision_core.execution_state
WHERE component_name = 'vision_ios_orchestrator';

\echo ''

SELECT
    '✅ Test 5.2: State records have hash chains' AS test,
    CASE
        WHEN COUNT(*) FILTER (WHERE hash_chain_id IS NULL) = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    COUNT(*) AS total_states,
    COUNT(*) FILTER (WHERE hash_chain_id IS NOT NULL) AS with_hash_chain
FROM vision_core.execution_state
WHERE component_name = 'vision_ios_orchestrator';

\echo ''

SELECT
    '✅ Test 5.3: Reconciliation field weights defined' AS test,
    CASE
        WHEN COUNT(*) >= 6 THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    COUNT(*) AS weight_rules_count
FROM fhq_meta.reconciliation_field_weights
WHERE component_name = 'vision_ios_orchestrator';

\echo ''

SELECT
    '✅ Test 5.4: State values are valid JSON' AS test,
    CASE
        WHEN COUNT(*) FILTER (WHERE jsonb_typeof(state_value) != 'object') = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    COUNT(*) AS total_states,
    COUNT(*) FILTER (WHERE jsonb_typeof(state_value) = 'object') AS valid_json
FROM vision_core.execution_state
WHERE component_name = 'vision_ios_orchestrator';

\echo ''

-- Display reconciliation rules
\echo 'Reconciliation Field Weights (ADR-010):'
\echo ''

SELECT
    field_name,
    criticality_weight,
    tolerance_type,
    tolerance_value,
    description
FROM fhq_meta.reconciliation_field_weights
WHERE component_name = 'vision_ios_orchestrator'
ORDER BY criticality_weight DESC, field_name;


-- =============================================================================
-- TEST 6: PERFORMANCE METRICS VERIFICATION
-- =============================================================================

\echo ''
\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo 'TEST 6: Performance Metrics Verification'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo ''

SELECT
    '✅ Test 6.1: Performance views accessible' AS test,
    CASE
        WHEN EXISTS (
            SELECT 1 FROM information_schema.views
            WHERE table_schema = 'vision_core'
              AND table_name = 'v_orchestrator_performance'
        ) THEN 'PASS'
        ELSE 'FAIL'
    END AS result;

\echo ''

SELECT
    '✅ Test 6.2: Latest executions view accessible' AS test,
    CASE
        WHEN EXISTS (
            SELECT 1 FROM information_schema.views
            WHERE table_schema = 'vision_core'
              AND table_name = 'v_orchestrator_latest_executions'
        ) THEN 'PASS'
        ELSE 'FAIL'
    END AS result;

\echo ''

-- Display performance summary
\echo 'Performance Summary (Last 7 Days):'
\echo ''

SELECT
    total_cycles_7d,
    total_tasks_executed,
    total_successes,
    total_failures,
    success_rate_percent || '%' AS success_rate,
    TO_CHAR(earliest_cycle, 'YYYY-MM-DD HH24:MI') AS first_cycle,
    TO_CHAR(latest_cycle, 'YYYY-MM-DD HH24:MI') AS last_cycle
FROM vision_core.v_orchestrator_performance;


-- =============================================================================
-- TEST 7: ADR COMPLIANCE VERIFICATION
-- =============================================================================

\echo ''
\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo 'TEST 7: ADR Compliance Verification'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo ''

SELECT
    '✅ Test 7.1: ADR-007 Orchestrator compliance' AS test,
    CASE
        WHEN EXISTS (
            SELECT 1 FROM fhq_governance.task_registry
            WHERE task_name = 'vision_ios_orchestrator_v1'
              AND task_config->'compliance' @> '["ADR-007"]'::jsonb
        ) THEN 'PASS'
        ELSE 'FAIL'
    END AS result;

\echo ''

SELECT
    '✅ Test 7.2: ADR-010 State reconciliation compliance' AS test,
    CASE
        WHEN EXISTS (
            SELECT 1 FROM fhq_governance.task_registry
            WHERE task_name = 'vision_ios_orchestrator_v1'
              AND task_config->'compliance' @> '["ADR-010"]'::jsonb
        ) THEN 'PASS'
        ELSE 'FAIL'
    END AS result;

\echo ''

SELECT
    '✅ Test 7.3: ADR-002 Audit trail compliance' AS test,
    CASE
        WHEN EXISTS (
            SELECT 1 FROM fhq_governance.task_registry
            WHERE task_name = 'vision_ios_orchestrator_v1'
              AND task_config->'compliance' @> '["ADR-002"]'::jsonb
        ) THEN 'PASS'
        ELSE 'FAIL'
    END AS result;

\echo ''

SELECT
    '✅ Test 7.4: No unauthorized foundation writes' AS test,
    CASE
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    COUNT(*) AS violation_count
FROM fhq_governance.governance_actions_log
WHERE action_type LIKE 'WRITE_TO_FHQ%'
  AND agent_id = 'LARS'
  AND timestamp > (
      SELECT MIN(timestamp)
      FROM fhq_governance.governance_actions_log
      WHERE action_type = 'VISION_ORCHESTRATOR_REGISTRATION'
  );


-- =============================================================================
-- FINAL SUMMARY
-- =============================================================================

\echo ''
\echo ''
\echo '══════════════════════════════════════════════════════════════════'
\echo 'OVERALL TEST SUMMARY'
\echo '══════════════════════════════════════════════════════════════════'
\echo ''

WITH test_results AS (
    -- Test 1.1
    SELECT 'Orchestrator registered' AS test_name,
           CASE WHEN COUNT(*) = 1 THEN 1 ELSE 0 END AS passed
    FROM fhq_governance.task_registry
    WHERE task_type = 'SYSTEM_ORCHESTRATOR' AND task_name = 'vision_ios_orchestrator_v1' AND enabled = TRUE

    UNION ALL

    -- Test 1.3
    SELECT 'Schedule configured',
           CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END
    FROM vision_core.orchestrator_schedule
    WHERE schedule_name = 'vision_ios_hourly'

    UNION ALL

    -- Test 2.1
    SELECT 'Orchestrator cycles executed',
           CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END
    FROM fhq_governance.governance_actions_log
    WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE'

    UNION ALL

    -- Test 2.3
    SELECT 'All cycles have hash chains',
           CASE WHEN COUNT(*) FILTER (WHERE hash_chain_id IS NULL) = 0 THEN 1 ELSE 0 END
    FROM fhq_governance.governance_actions_log
    WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE'

    UNION ALL

    -- Test 4.1
    SELECT 'Orchestrator registration logged',
           CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END
    FROM fhq_governance.governance_actions_log
    WHERE action_type = 'VISION_ORCHESTRATOR_REGISTRATION'

    UNION ALL

    -- Test 5.1
    SELECT 'State written to vision_core',
           CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END
    FROM vision_core.execution_state
    WHERE component_name = 'vision_ios_orchestrator'

    UNION ALL

    -- Test 5.3
    SELECT 'Reconciliation rules defined',
           CASE WHEN COUNT(*) >= 6 THEN 1 ELSE 0 END
    FROM fhq_meta.reconciliation_field_weights
    WHERE component_name = 'vision_ios_orchestrator'

    UNION ALL

    -- Test 7.1
    SELECT 'ADR-007 compliance',
           CASE WHEN EXISTS (
               SELECT 1 FROM fhq_governance.task_registry
               WHERE task_name = 'vision_ios_orchestrator_v1'
                 AND task_config->'compliance' @> '["ADR-007"]'::jsonb
           ) THEN 1 ELSE 0 END
)
SELECT
    test_name,
    CASE WHEN passed = 1 THEN '✅ PASS' ELSE '❌ FAIL' END AS result
FROM test_results
ORDER BY test_name;

\echo ''

WITH test_counts AS (
    SELECT
        SUM(passed) AS passed,
        COUNT(*) AS total
    FROM (
        SELECT CASE WHEN COUNT(*) = 1 THEN 1 ELSE 0 END AS passed
        FROM fhq_governance.task_registry
        WHERE task_type = 'SYSTEM_ORCHESTRATOR' AND task_name = 'vision_ios_orchestrator_v1' AND enabled = TRUE
        UNION ALL
        SELECT CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END
        FROM vision_core.orchestrator_schedule WHERE schedule_name = 'vision_ios_hourly'
        UNION ALL
        SELECT CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END
        FROM fhq_governance.governance_actions_log WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE'
        UNION ALL
        SELECT CASE WHEN COUNT(*) FILTER (WHERE hash_chain_id IS NULL) = 0 THEN 1 ELSE 0 END
        FROM fhq_governance.governance_actions_log WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE'
        UNION ALL
        SELECT CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END
        FROM fhq_governance.governance_actions_log WHERE action_type = 'VISION_ORCHESTRATOR_REGISTRATION'
        UNION ALL
        SELECT CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END
        FROM vision_core.execution_state WHERE component_name = 'vision_ios_orchestrator'
        UNION ALL
        SELECT CASE WHEN COUNT(*) >= 6 THEN 1 ELSE 0 END
        FROM fhq_meta.reconciliation_field_weights WHERE component_name = 'vision_ios_orchestrator'
        UNION ALL
        SELECT CASE WHEN EXISTS (
            SELECT 1 FROM fhq_governance.task_registry
            WHERE task_name = 'vision_ios_orchestrator_v1'
              AND task_config->'compliance' @> '["ADR-007"]'::jsonb
        ) THEN 1 ELSE 0 END
    ) tests
)
SELECT
    CASE
        WHEN passed = total THEN '✅ ALL TESTS PASSED'
        WHEN passed >= total * 0.75 THEN '⚠️  MOST TESTS PASSED'
        ELSE '❌ CRITICAL TESTS FAILED'
    END AS status,
    passed || '/' || total AS score,
    ROUND(100.0 * passed / total, 1) || '%' AS success_rate
FROM test_counts;

\echo ''
\echo '══════════════════════════════════════════════════════════════════'
\echo 'VERIFICATION COMPLETE'
\echo '══════════════════════════════════════════════════════════════════'
\echo ''
\echo 'Next steps:'
\echo '  - If tests show execution evidence: Orchestrator is working!'
\echo '  - If no execution evidence: Run: python 05_ORCHESTRATOR/orchestrator_v1.py'
\echo '  - For continuous mode: python 05_ORCHESTRATOR/orchestrator_v1.py --continuous'
\echo '  - For dry run test: python 05_ORCHESTRATOR/orchestrator_v1.py --dry-run'
