-- Migration 343: Canonical Test Orchestrator Infrastructure
-- Date: 2026-01-24
-- Author: STIG (EC-003)
-- Directive: CEO Authorization — Canonical Test Orchestrator

BEGIN;

-- ============================================================================
-- STEP 1: Signal Registry Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_calendar.test_signal_registry (
    signal_key TEXT PRIMARY KEY,
    signal_name TEXT NOT NULL,
    source_schema TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_column TEXT NOT NULL,
    aggregation TEXT DEFAULT 'LATEST',  -- LATEST, AVG_7D, SUM, MIN, MAX, COUNT, COUNT_DISTINCT
    filter_clause TEXT,  -- Optional WHERE clause addition
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE fhq_calendar.test_signal_registry IS
'Signal registry for Canonical Test Orchestrator - maps metric keys to data sources (CEO-DIR-2026)';

-- ============================================================================
-- STEP 2: Populate Signal Mappings
-- ============================================================================

INSERT INTO fhq_calendar.test_signal_registry (signal_key, signal_name, source_schema, source_table, source_column, aggregation, filter_clause)
VALUES
    ('lvi', 'Learning Velocity Index', 'fhq_learning', 'learning_velocity_metrics', 'death_rate_pct', 'LATEST', NULL),
    ('brier_score', 'Brier Score', 'fhq_learning', 'ldow_cycle_metrics', 'brier_score', 'LATEST', NULL),
    ('context_lift', 'Context Lift vs Baseline', 'fhq_learning', 'v_context_brier_impact', 'brier_delta', 'LATEST', NULL),
    ('ios010_bridge', 'IoS-010 Bridge Status', 'fhq_learning', 'v_addendum_a_readiness', 'ios010_bridge_ready', 'LATEST', NULL),
    ('tier1_death_rate', 'Tier-1 Death Rate', 'fhq_learning', 'v_tier1_calibration_status', 'death_rate', 'LATEST', NULL),
    ('macro_regimes_tested', 'Macro Regimes Tested', 'fhq_learning', 'ldow_regime_metrics', 'regime_type', 'COUNT_DISTINCT', NULL),
    ('drawdown_phases_tested', 'Drawdown Phases Tested', 'fhq_learning', 'ldow_regime_metrics', 'regime_type', 'COUNT', 'regime_type = ''DRAWDOWN''')
ON CONFLICT (signal_key) DO UPDATE SET
    source_schema = EXCLUDED.source_schema,
    source_table = EXCLUDED.source_table,
    source_column = EXCLUDED.source_column,
    aggregation = EXCLUDED.aggregation;

-- ============================================================================
-- STEP 3: Orchestrator Execution Log Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_calendar.orchestrator_execution_log (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_ts TIMESTAMPTZ DEFAULT NOW(),
    tests_processed INTEGER NOT NULL DEFAULT 0,
    tests_escalated INTEGER NOT NULL DEFAULT 0,
    tests_resolved INTEGER NOT NULL DEFAULT 0,
    tests_halted INTEGER NOT NULL DEFAULT 0,
    execution_status TEXT NOT NULL CHECK (execution_status IN ('SUCCESS', 'PARTIAL', 'FAILED', 'HALTED')),
    halt_reason TEXT,
    execution_details JSONB,
    evidence_file_path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE fhq_calendar.orchestrator_execution_log IS
'Execution log for Canonical Test Orchestrator daemon runs';

-- ============================================================================
-- STEP 4: Function to Get Signal Value
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_calendar.get_signal_value(p_signal_key TEXT)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_registry RECORD;
    v_query TEXT;
    v_result JSONB;
BEGIN
    -- Get registry entry
    SELECT * INTO v_registry
    FROM fhq_calendar.test_signal_registry
    WHERE signal_key = p_signal_key;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', 'Signal not found: ' || p_signal_key);
    END IF;

    -- Build dynamic query based on aggregation type
    CASE v_registry.aggregation
        WHEN 'LATEST' THEN
            v_query := format(
                'SELECT jsonb_build_object(''value'', %I, ''source'', %L, ''retrieved_at'', NOW()) FROM %I.%I %s ORDER BY created_at DESC LIMIT 1',
                v_registry.source_column,
                v_registry.source_schema || '.' || v_registry.source_table,
                v_registry.source_schema,
                v_registry.source_table,
                COALESCE('WHERE ' || v_registry.filter_clause, '')
            );
        WHEN 'COUNT' THEN
            v_query := format(
                'SELECT jsonb_build_object(''value'', COUNT(*), ''source'', %L, ''retrieved_at'', NOW()) FROM %I.%I %s',
                v_registry.source_schema || '.' || v_registry.source_table,
                v_registry.source_schema,
                v_registry.source_table,
                COALESCE('WHERE ' || v_registry.filter_clause, '')
            );
        WHEN 'COUNT_DISTINCT' THEN
            v_query := format(
                'SELECT jsonb_build_object(''value'', COUNT(DISTINCT %I), ''source'', %L, ''retrieved_at'', NOW()) FROM %I.%I %s',
                v_registry.source_column,
                v_registry.source_schema || '.' || v_registry.source_table,
                v_registry.source_schema,
                v_registry.source_table,
                COALESCE('WHERE ' || v_registry.filter_clause, '')
            );
        ELSE
            RETURN jsonb_build_object('error', 'Unknown aggregation: ' || v_registry.aggregation);
    END CASE;

    BEGIN
        EXECUTE v_query INTO v_result;
    EXCEPTION WHEN OTHERS THEN
        RETURN jsonb_build_object('error', SQLERRM, 'signal_key', p_signal_key);
    END;

    IF v_result IS NULL THEN
        RETURN jsonb_build_object('value', NULL, 'source', v_registry.source_schema || '.' || v_registry.source_table, 'status', 'NO_DATA');
    END IF;

    RETURN v_result;
END;
$$;

-- ============================================================================
-- STEP 5: Function to Evaluate Test Against Criteria
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_calendar.evaluate_test_criteria(p_test_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_test RECORD;
    v_progress RECORD;
    v_result JSONB := '{}'::jsonb;
    v_signals JSONB := '{}'::jsonb;
    v_success_eval JSONB := '{}'::jsonb;
    v_failure_eval JSONB := '{}'::jsonb;
BEGIN
    -- Get test
    SELECT * INTO v_test
    FROM fhq_calendar.canonical_test_events
    WHERE test_id = p_test_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', 'Test not found');
    END IF;

    -- Get progress
    SELECT * INTO v_progress
    FROM fhq_calendar.compute_test_progress(p_test_id);

    -- Collect current signal values
    v_signals := jsonb_build_object(
        'lvi', fhq_calendar.get_signal_value('lvi'),
        'brier_score', fhq_calendar.get_signal_value('brier_score'),
        'context_lift', fhq_calendar.get_signal_value('context_lift'),
        'ios010_bridge', fhq_calendar.get_signal_value('ios010_bridge'),
        'tier1_death_rate', fhq_calendar.get_signal_value('tier1_death_rate')
    );

    -- Build evaluation result
    v_result := jsonb_build_object(
        'test_id', p_test_id,
        'test_code', v_test.test_code,
        'evaluated_at', NOW(),
        'progress', jsonb_build_object(
            'days_elapsed', v_progress.days_elapsed,
            'days_remaining', v_progress.days_remaining,
            'is_overdue', v_progress.is_overdue
        ),
        'baseline', v_test.baseline_definition,
        'target', v_test.target_metrics,
        'current_signals', v_signals,
        'success_criteria', v_test.success_criteria,
        'failure_criteria', v_test.failure_criteria
    );

    RETURN v_result;
END;
$$;

-- ============================================================================
-- STEP 6: Add columns to canonical_test_events if missing
-- ============================================================================

DO $$
BEGIN
    -- Add last_orchestrator_run if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_calendar'
        AND table_name = 'canonical_test_events'
        AND column_name = 'last_orchestrator_run'
    ) THEN
        ALTER TABLE fhq_calendar.canonical_test_events
        ADD COLUMN last_orchestrator_run TIMESTAMPTZ;
    END IF;

    -- Add orchestrator_run_count if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_calendar'
        AND table_name = 'canonical_test_events'
        AND column_name = 'orchestrator_run_count'
    ) THEN
        ALTER TABLE fhq_calendar.canonical_test_events
        ADD COLUMN orchestrator_run_count INTEGER DEFAULT 0;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT 'Signal Registry' as component, COUNT(*) as count FROM fhq_calendar.test_signal_registry
UNION ALL
SELECT 'Orchestrator Log Schema', COUNT(*) FROM information_schema.columns WHERE table_name = 'orchestrator_execution_log'
UNION ALL
SELECT 'Functions Created', COUNT(*) FROM information_schema.routines WHERE routine_schema = 'fhq_calendar' AND routine_name IN ('get_signal_value', 'evaluate_test_criteria');
