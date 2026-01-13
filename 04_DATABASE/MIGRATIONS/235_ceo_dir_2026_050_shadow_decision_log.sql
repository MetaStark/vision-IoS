-- ============================================================
-- CEO-DIR-2026-050 — SHADOW DECISION ACTIVATION
-- ============================================================
-- Migration: 235_ceo_dir_2026_050_shadow_decision_log.sql
-- Authority: CEO (Constitutional Directive)
-- Technical Lead: STIG (CTO)
-- Governance: VEGA
-- ADR Compliance: ADR-002, ADR-012, ADR-013, ADR-014
-- ============================================================
-- PURPOSE: Enable LIDS evaluation observability without execution
--          Shadow mode: evaluate signals, log decisions, NO trades
--          paper_trading_eligible = false (INTENTIONAL)
-- ============================================================
-- CONSTITUTIONAL PROTECTION:
--   - NO ADR-012 BREACH: Zero execution, zero capital exposure
--   - Observability only: Proves LIDS gate behavior
--   - Court-proof evidence of evaluation decisions
-- ============================================================

BEGIN;

-- ============================================================
-- SECTION 1: SHADOW DECISION LOG
-- Non-executing ledger for shadow signal evaluations
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.shadow_decision_log (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Signal Reference
    signal_id UUID NOT NULL,
    needle_id UUID,  -- Reference to golden_needles.needle_id
    symbol TEXT NOT NULL,

    -- Timing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signal_created_at TIMESTAMPTZ,  -- When the signal was originally created
    evaluation_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- LIDS Gate Evaluation
    lids_verdict TEXT NOT NULL,  -- PASS, BLOCKED_CONFIDENCE, BLOCKED_FRESHNESS
    lids_confidence NUMERIC(8,4),  -- Raw confidence value
    lids_confidence_threshold NUMERIC(8,4) DEFAULT 0.70,
    lids_freshness_hours NUMERIC(10,2),  -- Data age in hours
    lids_freshness_threshold_hours NUMERIC(10,2) DEFAULT 12.0,

    -- Signal Quality Metrics
    eqs_score NUMERIC(10,6),  -- EQS v2 score
    sitc_confidence_level TEXT,  -- HIGH/MEDIUM/LOW

    -- Decision Formula Components (for learning)
    decision_formula JSONB NOT NULL DEFAULT '{}',

    -- Execution Context (always shadow in this mode)
    execution_mode TEXT NOT NULL DEFAULT 'SHADOW_EVALUATION',
    would_have_executed BOOLEAN DEFAULT FALSE,  -- TRUE if all gates passed
    blocked_at_gate TEXT,  -- Which gate blocked (if any)

    -- Additional Gates (logged but not blocking in shadow mode)
    exposure_gate_result BOOLEAN,
    holiday_gate_result BOOLEAN,
    btc_only_gate_result BOOLEAN,
    sitc_gate_result BOOLEAN,

    -- Metadata
    daemon_cycle_id UUID,  -- Links to orchestrator cycle
    directive TEXT DEFAULT 'CEO-DIR-2026-050',

    -- Constraints
    CONSTRAINT chk_lids_verdict CHECK (
        lids_verdict IN ('PASS', 'BLOCKED_CONFIDENCE', 'BLOCKED_FRESHNESS', 'BLOCKED_MULTIPLE')
    ),
    CONSTRAINT chk_execution_mode CHECK (
        execution_mode IN ('SHADOW_EVALUATION', 'PAPER', 'LIVE')
    )
);

-- Index for time-series queries
CREATE INDEX IF NOT EXISTS idx_shadow_decision_eval_time
    ON fhq_governance.shadow_decision_log(evaluation_time DESC);

-- Index for signal lookups
CREATE INDEX IF NOT EXISTS idx_shadow_decision_signal
    ON fhq_governance.shadow_decision_log(signal_id);

-- Index for LIDS verdict analysis
CREATE INDEX IF NOT EXISTS idx_shadow_decision_verdict
    ON fhq_governance.shadow_decision_log(lids_verdict, evaluation_time DESC);

-- Index for would-have-executed analysis
CREATE INDEX IF NOT EXISTS idx_shadow_decision_would_exec
    ON fhq_governance.shadow_decision_log(would_have_executed, evaluation_time DESC)
    WHERE would_have_executed = TRUE;

COMMENT ON TABLE fhq_governance.shadow_decision_log IS
'CEO-DIR-2026-050: Shadow Decision Log.
Non-executing ledger for LIDS gate evaluation observability.
Logs what WOULD have happened without executing trades.
paper_trading_eligible remains FALSE by design.
STIG 2026-01-14';

-- ============================================================
-- SECTION 2: REGISTER SIGNAL_EXECUTOR_DAEMON IN ORCHESTRATOR
-- Schedule at <=60s cadence per directive
-- ============================================================

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
    'signal_executor_daemon_shadow',
    'SHADOW_EVALUATION',
    'LINE',
    'Signal Executor Daemon (Shadow Mode) - Evaluates signals without execution',
    'CEO-DIR-2026-050: Shadow evaluation mode. Logs LIDS gate decisions without trade execution.',
    'EXECUTION',
    'LINE',
    'active',
    true,
    jsonb_build_object(
        'priority', 2,
        'schedule', 'every_60s',
        'function_path', '03_FUNCTIONS/signal_executor_daemon.py',
        'directive', 'CEO-DIR-2026-050',
        'execution_mode', 'SHADOW_EVALUATION',
        'args', '--dry-run --shadow-log',
        'lids_thresholds', jsonb_build_object(
            'min_confidence', 0.70,
            'max_freshness_hours', 12.0
        )
    ),
    jsonb_build_object(
        'registered_by', 'STIG',
        'registered_at', NOW(),
        'purpose', 'Enable LIDS evaluation observability without execution',
        'paper_trading_eligible', false,
        'execution_blocked', true,
        'learning_eligible', true
    ),
    NOW(),
    NOW()
)
ON CONFLICT (task_name) DO UPDATE SET
    enabled = true,
    task_config = EXCLUDED.task_config,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- ============================================================
-- SECTION 3: VIEW FOR SHADOW DECISION ANALYSIS
-- ============================================================

CREATE OR REPLACE VIEW fhq_governance.v_shadow_decision_summary AS
SELECT
    DATE(evaluation_time) AS eval_date,
    COUNT(*) AS total_evaluations,
    COUNT(*) FILTER (WHERE lids_verdict = 'PASS') AS lids_passed,
    COUNT(*) FILTER (WHERE lids_verdict = 'BLOCKED_CONFIDENCE') AS blocked_confidence,
    COUNT(*) FILTER (WHERE lids_verdict = 'BLOCKED_FRESHNESS') AS blocked_freshness,
    COUNT(*) FILTER (WHERE would_have_executed = TRUE) AS would_have_executed,
    ROUND(AVG(lids_confidence)::numeric, 4) AS avg_confidence,
    ROUND(AVG(lids_freshness_hours)::numeric, 2) AS avg_freshness_hours,
    ROUND(AVG(eqs_score)::numeric, 6) AS avg_eqs_score
FROM fhq_governance.shadow_decision_log
GROUP BY DATE(evaluation_time)
ORDER BY eval_date DESC;

COMMENT ON VIEW fhq_governance.v_shadow_decision_summary IS
'CEO-DIR-2026-050: Daily summary of shadow decision evaluations.
Shows LIDS gate pass/block rates without actual execution.';

-- ============================================================
-- SECTION 4: GOVERNANCE ATTESTATION
-- ============================================================

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
    'CONSTITUTIONAL_DIRECTIVE',
    'CEO-DIR-2026-050',
    'DIRECTIVE',
    'CEO',
    NOW(),
    'APPROVED',
    'Shadow Decision Activation: Enable LIDS evaluation observability without execution. Zero capital exposure. paper_trading_eligible remains FALSE.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-050',
        'migration_id', 235,
        'tables_created', ARRAY['fhq_governance.shadow_decision_log'],
        'tasks_registered', ARRAY['signal_executor_daemon_shadow'],
        'execution_mode', 'SHADOW_EVALUATION',
        'adr_compliance', ARRAY['ADR-002', 'ADR-012', 'ADR-013', 'ADR-014'],
        'paper_trading_eligible', false,
        'capital_exposure', 0
    )
);

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================

-- Verify table created
SELECT
    'SHADOW_DECISION_LOG' as check_type,
    COUNT(*) as row_count
FROM fhq_governance.shadow_decision_log;

-- Verify daemon registered
SELECT
    'DAEMON_REGISTRATION' as check_type,
    task_name,
    status,
    enabled,
    task_config->>'execution_mode' as execution_mode,
    task_config->>'schedule' as schedule
FROM fhq_governance.task_registry
WHERE task_name = 'signal_executor_daemon_shadow';
