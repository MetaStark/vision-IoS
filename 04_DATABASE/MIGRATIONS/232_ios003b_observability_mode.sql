-- =====================================================
-- Migration 232: IOS-003-B Observability Mode Gate
-- =====================================================
-- Directive: CEO-DIR-2026-0ZE-A v2 + Metric Governance Addendum (A9-A11)
-- Purpose: Gate IOS-003-B to observability-only mode
-- Authority: STIG (Infrastructure Sovereignty ADR-013)
-- Classification: G1 (Non-breaking governance enhancement)
--
-- This migration:
-- 1. Creates ios_execution_gates table (if not exists)
-- 2. Inserts gate for IOS-003-B flash_context emission
-- 3. Logs activation to governance_actions_log
-- =====================================================

BEGIN;

-- ============================================================================
-- TABLE: IoS Execution Gates
-- ============================================================================
-- Runtime gates for IoS components. Checked at execution time.
-- IOS-003-B runtime is FORBIDDEN from writing to this table (ADR-013).
-- Only STIG migrations and governance operations may modify.

CREATE TABLE IF NOT EXISTS fhq_governance.ios_execution_gates (
    gate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Target IoS
    ios_id TEXT NOT NULL,

    -- Gate specification
    gate_type TEXT NOT NULL,
    gate_status TEXT NOT NULL CHECK (gate_status IN ('ALLOWED', 'BLOCKED', 'CONDITIONAL')),

    -- Governance
    reason TEXT NOT NULL,
    directive_ref TEXT,

    -- Conditional gate (if gate_status = 'CONDITIONAL')
    condition_query TEXT,
    condition_threshold NUMERIC,

    -- Timestamps
    effective_from TIMESTAMPTZ DEFAULT NOW(),
    effective_until TIMESTAMPTZ,

    created_by TEXT NOT NULL DEFAULT 'STIG',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_ios_gate UNIQUE (ios_id, gate_type)
);

-- Index for runtime lookups
CREATE INDEX IF NOT EXISTS idx_ios_gates_lookup
    ON fhq_governance.ios_execution_gates(ios_id, gate_status);

-- ============================================================================
-- GATE: IOS-003-B Flash Context Emission BLOCKED
-- ============================================================================
-- Per CEO-DIR-2026-0ZE-A v2: Observability-only mode
-- Detection engine runs, delta_log writes allowed, flash_context emission blocked

INSERT INTO fhq_governance.ios_execution_gates (
    ios_id,
    gate_type,
    gate_status,
    reason,
    directive_ref,
    created_by
) VALUES (
    'IOS-003-B',
    'FLASH_CONTEXT_EMISSION',
    'BLOCKED',
    'CEO-DIR-2026-0ZE-A v2: Observability-only mode until Phase 1 success criteria met. Detection runs, flash_context writes blocked.',
    'CEO-DIR-2026-0ZE-A-v2',
    'STIG'
)
ON CONFLICT (ios_id, gate_type) DO UPDATE SET
    gate_status = EXCLUDED.gate_status,
    reason = EXCLUDED.reason,
    directive_ref = EXCLUDED.directive_ref,
    updated_at = NOW();

-- ============================================================================
-- GOVERNANCE LOGGING (ADR-002)
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'IOS_ACTIVATION',
    'IOS-003-B',
    'INTRADAY_REGIME_DELTA',
    'STIG',
    'OBSERVABILITY_ONLY_ACTIVATED',
    'CEO-DIR-2026-0ZE-A v2 + Metric Governance Addendum (A9-A11): IOS-003-B activated in observability-only mode. Detection engine runs, delta_log writes allowed, flash_context emission blocked until Phase 1 success criteria met.',
    jsonb_build_object(
        'migration_id', 232,
        'directive', 'CEO-DIR-2026-0ZE-A-v2',
        'mode', 'OBSERVABILITY_ONLY',
        'gates_created', ARRAY['FLASH_CONTEXT_EMISSION'],
        'approved_writes', ARRAY['fhq_operational.delta_log', 'fhq_operational.regime_delta', 'fhq_operational.intraday_bars_h1', 'fhq_operational.intraday_bars_h4'],
        'blocked_writes', ARRAY['fhq_operational.flash_context'],
        'addendum', 'A9-A11 Metric Governance Addendum',
        'vega_signed', true,
        'vega_timestamp', '2026-01-12T00:45:00Z'
    )
);

COMMIT;
