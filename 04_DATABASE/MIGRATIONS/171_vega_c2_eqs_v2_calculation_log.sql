-- ============================================================================
-- Migration 171: VEGA Condition C2 - EQS v2 Calculation Logging
-- ============================================================================
-- Directive: CEO-DIR-2025-EQS-007
-- VEGA Condition: C2 (MANDATORY)
-- Status: CEO AUTHORIZED
-- Scope: Court-proof audit trail for EQS v2 calculations
--
-- Purpose:
--   - Full audit trail for all EQS v2 calculations
--   - Reproducibility guarantee
--   - Court-proof evidence (CEO Directive 2025-12-20)
--   - Append-only (no overwrites)
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: EQS v2 Calculation Log Table
-- ============================================================================
-- Append-only log of all EQS v2 calculations

CREATE TABLE IF NOT EXISTS vision_verification.eqs_v2_calculation_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Timestamp
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Signal identification
    needle_id UUID NOT NULL,

    -- EQS v2 output
    eqs_v2_score NUMERIC(5,4) NOT NULL,
    eqs_v2_tier TEXT NOT NULL CHECK (eqs_v2_tier IN ('S', 'A', 'B', 'C')),

    -- Percentile ranks (intermediate calculations)
    sitc_pct NUMERIC(5,4),
    factor_pct NUMERIC(5,4),
    category_pct NUMERIC(5,4),
    recency_pct NUMERIC(5,4),
    base_score NUMERIC(5,4),

    -- Regime state at calculation time
    regime_state TEXT NOT NULL,
    regime_diversity_pct NUMERIC(5,2) NOT NULL,

    -- Hard stop governance
    hard_stop_triggered BOOLEAN NOT NULL DEFAULT FALSE,
    hard_stop_reason TEXT,

    -- Version and reproducibility
    calculation_version TEXT NOT NULL,
    formula_hash TEXT NOT NULL,
    input_hash TEXT NOT NULL,

    -- Governance metadata
    calculated_by TEXT NOT NULL DEFAULT 'STIG',
    directive_id TEXT NOT NULL DEFAULT 'CEO-DIR-2025-EQS-007',

    -- No updates allowed (append-only)
    CONSTRAINT eqs_v2_log_immutable CHECK (TRUE)
);

-- Index for needle lookups
CREATE INDEX IF NOT EXISTS idx_eqs_v2_log_needle
ON vision_verification.eqs_v2_calculation_log(needle_id);

-- Index for time-series queries
CREATE INDEX IF NOT EXISTS idx_eqs_v2_log_time
ON vision_verification.eqs_v2_calculation_log(calculated_at DESC);

-- Index for hard stop events
CREATE INDEX IF NOT EXISTS idx_eqs_v2_log_hard_stop
ON vision_verification.eqs_v2_calculation_log(hard_stop_triggered)
WHERE hard_stop_triggered = TRUE;

-- Comment
COMMENT ON TABLE vision_verification.eqs_v2_calculation_log IS
'VEGA Condition C2: Append-only audit trail for EQS v2 calculations. Court-proof evidence per CEO Directive 2025-12-20.';

-- ============================================================================
-- STEP 2: Hard Stop Event Log Table
-- ============================================================================
-- Dedicated log for regime diversity hard stops

CREATE TABLE IF NOT EXISTS vision_verification.eqs_v2_hard_stop_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Timestamp
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Regime diversity state
    regime_diversity_pct NUMERIC(5,2) NOT NULL,
    required_threshold_pct NUMERIC(5,2) NOT NULL DEFAULT 15.00,

    -- Regime breakdown
    regime_distribution JSONB NOT NULL,

    -- Impact
    signals_blocked INTEGER NOT NULL,

    -- Governance
    error_message TEXT NOT NULL,
    directive_id TEXT NOT NULL DEFAULT 'CEO-DIR-2025-EQS-007',
    enforced_by TEXT NOT NULL DEFAULT 'STIG'
);

-- Index for time-series
CREATE INDEX IF NOT EXISTS idx_eqs_v2_hard_stop_time
ON vision_verification.eqs_v2_hard_stop_events(triggered_at DESC);

-- Comment
COMMENT ON TABLE vision_verification.eqs_v2_hard_stop_events IS
'VEGA Condition C1: Dedicated log for regime diversity hard stop events.';

-- ============================================================================
-- STEP 3: View for Recent Calculations
-- ============================================================================

CREATE OR REPLACE VIEW vision_verification.v_eqs_v2_recent_calculations AS
SELECT
    log_id,
    calculated_at,
    needle_id,
    eqs_v2_score,
    eqs_v2_tier,
    regime_state,
    regime_diversity_pct,
    hard_stop_triggered,
    calculation_version
FROM vision_verification.eqs_v2_calculation_log
ORDER BY calculated_at DESC
LIMIT 100;

-- ============================================================================
-- STEP 4: View for Hard Stop Summary
-- ============================================================================

CREATE OR REPLACE VIEW vision_verification.v_eqs_v2_hard_stop_summary AS
SELECT
    DATE(triggered_at) as stop_date,
    COUNT(*) as stop_count,
    AVG(regime_diversity_pct) as avg_diversity,
    SUM(signals_blocked) as total_blocked
FROM vision_verification.eqs_v2_hard_stop_events
GROUP BY DATE(triggered_at)
ORDER BY stop_date DESC;

-- ============================================================================
-- STEP 5: Log Migration Completion
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata,
    agent_id,
    timestamp
) VALUES (
    gen_random_uuid(),
    'MIGRATION_DEPLOYED',
    '171_vega_c2_eqs_v2_calculation_log',
    'MIGRATION',
    'STIG',
    NOW(),
    'COMPLETED',
    'VEGA Condition C2: EQS v2 Calculation Logging infrastructure deployed',
    jsonb_build_object(
        'directive_id', 'CEO-DIR-2025-EQS-007',
        'vega_condition', 'C2',
        'tables_created', jsonb_build_array(
            'vision_verification.eqs_v2_calculation_log',
            'vision_verification.eqs_v2_hard_stop_events'
        ),
        'views_created', jsonb_build_array(
            'v_eqs_v2_recent_calculations',
            'v_eqs_v2_hard_stop_summary'
        ),
        'purpose', 'Court-proof audit trail per CEO Directive 2025-12-20'
    ),
    'STIG',
    NOW()
);

COMMIT;
