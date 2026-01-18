-- Migration 312: CEO-DIR-2026-096 Task Registry Compliance
-- Purpose: Register IoS-003C and UMA tasks in fhq_governance.task_registry
-- Authority: CEO-DIR-2026-096
-- Deadline: 2026-01-19

-- ============================================================================
-- SECTION 1: IoS-003C Shadow Learning Tasks
-- ============================================================================

INSERT INTO fhq_governance.task_registry (
    task_id,
    task_name,
    task_type,
    agent_id,
    task_description,
    task_config,
    enabled,
    status,
    created_at
) VALUES
-- Epoch Snapshot (Daily @ 00:05 UTC)
(
    gen_random_uuid(),
    'ios003c_epoch_snapshot',
    'SHADOW_LEARNING',
    'STIG',
    'Capture daily epoch snapshot of crypto regime predictions to shadow ledger',
    jsonb_build_object(
        'schedule', 'Daily @ 00:05 UTC',
        'script', 'run_ios003c_snapshot.bat',
        'directive', 'CEO-DIR-2026-093',
        'escalation_class', 'P0',
        'purpose', 'Signal capture for 30-day shadow learning experiment'
    ),
    true,
    'active',
    NOW()
),
-- Outcome Computation (Daily @ 04:00 UTC)
(
    gen_random_uuid(),
    'ios003c_outcome_computation',
    'SHADOW_LEARNING',
    'STIG',
    'Compute T+1/T+3/T+5 outcomes for shadow ledger signals',
    jsonb_build_object(
        'schedule', 'Daily @ 04:00 UTC',
        'script', 'run_ios003c_outcomes.bat',
        'directive', 'CEO-DIR-2026-093',
        'escalation_class', 'P0',
        'purpose', 'Outcome capture and quality metrics update',
        'price_source', 'fhq_market.prices (canonical)'
    ),
    true,
    'active',
    NOW()
),
-- Weekly Analysis (Sunday @ 00:00 UTC)
(
    gen_random_uuid(),
    'ios003c_weekly_analysis',
    'SHADOW_LEARNING',
    'STIG',
    'Bootstrap significance test, regime persistence analysis, VEGA attestation',
    jsonb_build_object(
        'schedule', 'Sunday @ 00:00 UTC',
        'script', 'run_ios003c_weekly.bat',
        'directive', 'CEO-DIR-2026-093',
        'escalation_class', 'P1',
        'purpose', 'Statistical validation and governance attestation'
    ),
    true,
    'active',
    NOW()
),
-- Learning Update 00:00 (4x Daily)
(
    gen_random_uuid(),
    'ios003c_learning_update_00',
    'SHADOW_LEARNING',
    'STIG',
    'Update daily report with shadow learning metrics (00:00 UTC cycle)',
    jsonb_build_object(
        'schedule', 'Daily @ 00:00 UTC',
        'script', 'run_ios003c_learning_update.bat',
        'directive', 'CEO-DIR-2026-093',
        'escalation_class', 'P2',
        'purpose', 'Daily report integration'
    ),
    true,
    'active',
    NOW()
),
-- Learning Update 06:00 (4x Daily)
(
    gen_random_uuid(),
    'ios003c_learning_update_06',
    'SHADOW_LEARNING',
    'STIG',
    'Update daily report with shadow learning metrics (06:00 UTC cycle)',
    jsonb_build_object(
        'schedule', 'Daily @ 06:00 UTC',
        'script', 'run_ios003c_learning_update.bat',
        'directive', 'CEO-DIR-2026-093',
        'escalation_class', 'P2',
        'purpose', 'Daily report integration'
    ),
    true,
    'active',
    NOW()
),
-- Learning Update 12:00 (4x Daily)
(
    gen_random_uuid(),
    'ios003c_learning_update_12',
    'SHADOW_LEARNING',
    'STIG',
    'Update daily report with shadow learning metrics (12:00 UTC cycle)',
    jsonb_build_object(
        'schedule', 'Daily @ 12:00 UTC',
        'script', 'run_ios003c_learning_update.bat',
        'directive', 'CEO-DIR-2026-093',
        'escalation_class', 'P2',
        'purpose', 'Daily report integration'
    ),
    true,
    'active',
    NOW()
),
-- Learning Update 18:00 (4x Daily)
(
    gen_random_uuid(),
    'ios003c_learning_update_18',
    'SHADOW_LEARNING',
    'STIG',
    'Update daily report with shadow learning metrics (18:00 UTC cycle)',
    jsonb_build_object(
        'schedule', 'Daily @ 18:00 UTC',
        'script', 'run_ios003c_learning_update.bat',
        'directive', 'CEO-DIR-2026-093',
        'escalation_class', 'P2',
        'purpose', 'Daily report integration'
    ),
    true,
    'active',
    NOW()
),
-- Gate 3 Check (Day 30+)
(
    gen_random_uuid(),
    'ios003c_gate3_check',
    'SHADOW_LEARNING',
    'STIG',
    'Check Gate 3 eligibility and auto-generate decision packet on Day 30',
    jsonb_build_object(
        'schedule', 'Daily @ 04:30 UTC (after day 29)',
        'directive', 'CEO-DIR-2026-093',
        'escalation_class', 'P0',
        'purpose', 'Automated Gate 3 decision packet generation'
    ),
    true,
    'active',
    NOW()
)
ON CONFLICT (task_name) DO UPDATE SET
    task_config = EXCLUDED.task_config,
    enabled = EXCLUDED.enabled,
    updated_at = NOW();

-- ============================================================================
-- SECTION 2: UMA Meta-Analyst Task
-- ============================================================================

INSERT INTO fhq_governance.task_registry (
    task_id,
    task_name,
    task_type,
    agent_id,
    task_description,
    task_config,
    enabled,
    status,
    created_at
) VALUES
(
    gen_random_uuid(),
    'uma_daily_learning_audit',
    'META_ANALYSIS',
    'UMA',
    'UMA daily learning velocity audit per EC-014',
    jsonb_build_object(
        'schedule', 'Daily @ 06:00 UTC',
        'script', 'FjordHQ-UMA-MetaAnalyst (Windows Task)',
        'contract', 'EC-014',
        'escalation_class', 'P1',
        'purpose', 'Learning friction identification and LVI optimization'
    ),
    true,
    'active',
    NOW()
)
ON CONFLICT (task_name) DO UPDATE SET
    task_config = EXCLUDED.task_config,
    enabled = EXCLUDED.enabled,
    updated_at = NOW();

-- ============================================================================
-- SECTION 3: Governance Log Entry
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    initiated_by,
    decision,
    decision_rationale,
    initiated_at
) VALUES (
    'TASK_REGISTRY_SYNC',
    'CEO-DIR-2026-096',
    'STIG',
    'EXECUTED',
    'IoS-003C and UMA tasks registered in fhq_governance.task_registry per CEO-DIR-2026-096. Database now has visibility into scheduler state.',
    NOW()
);

-- ============================================================================
-- End of Migration 312
-- ============================================================================
