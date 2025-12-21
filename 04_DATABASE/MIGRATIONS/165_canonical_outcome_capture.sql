-- Migration 165: Canonical Outcome Capture
-- CEO Directive: CEO-G5-TRACE-2025-12-21 (Phase 2)
-- Purpose: Ground truth outcome capture - no learning, no thresholds
-- Scope: Exit detection → Outcome recording → Needle linkage

-- ============================================================================
-- ARCHITECTURAL PRINCIPLE
-- ============================================================================
-- "You cannot learn from what you cannot attribute."
-- This migration creates the ground truth layer.
-- Learning comes later. This is just data capture.

-- ============================================================================
-- STEP 1: Create canonical_outcomes table (ground truth)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.canonical_outcomes (
    outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Traceability (MANDATORY - CEO Directive)
    needle_id UUID NOT NULL,
    trade_id UUID NOT NULL,

    -- Trade context
    trade_source TEXT NOT NULL,  -- 'g5_paper_trades', 'shadow_trades', 'trades'
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,  -- 'LONG', 'SHORT'

    -- Entry data
    entry_price NUMERIC NOT NULL,
    entry_timestamp TIMESTAMPTZ NOT NULL,
    entry_regime TEXT,
    entry_defcon INTEGER,

    -- Exit data
    exit_price NUMERIC NOT NULL,
    exit_timestamp TIMESTAMPTZ NOT NULL,
    exit_reason TEXT NOT NULL,  -- 'STOP_LOSS', 'TAKE_PROFIT', 'MANUAL', 'CONTEXT_REVOKED', 'TTL_EXPIRED'
    exit_regime TEXT,
    exit_defcon INTEGER,

    -- Outcome metrics (ground truth)
    pnl_absolute NUMERIC NOT NULL,
    pnl_percent NUMERIC NOT NULL,
    hold_duration_minutes INTEGER NOT NULL,

    -- Risk metrics captured at exit
    max_favorable_excursion NUMERIC,  -- Best unrealized P/L during hold
    max_adverse_excursion NUMERIC,    -- Worst unrealized P/L during hold

    -- Needle context at entry (immutable snapshot)
    needle_eqs_score NUMERIC,
    needle_hypothesis_category TEXT,
    needle_target_asset TEXT,
    needle_sitc_confidence TEXT,

    -- Governance
    captured_by TEXT NOT NULL DEFAULT 'OUTCOME_CAPTURE_DAEMON',
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT fk_needle FOREIGN KEY (needle_id)
        REFERENCES fhq_canonical.golden_needles(needle_id),
    CONSTRAINT valid_pnl CHECK (pnl_absolute IS NOT NULL),
    CONSTRAINT valid_direction CHECK (direction IN ('LONG', 'SHORT'))
);

COMMENT ON TABLE fhq_canonical.canonical_outcomes IS
'Ground truth outcome capture. CEO Directive CEO-G5-TRACE-2025-12-21.
No learning logic. No adaptive thresholds. Just facts.
Every closed trade produces exactly one canonical outcome.';

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_canonical_outcomes_needle
ON fhq_canonical.canonical_outcomes (needle_id);

CREATE INDEX IF NOT EXISTS idx_canonical_outcomes_exit_timestamp
ON fhq_canonical.canonical_outcomes (exit_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_canonical_outcomes_symbol
ON fhq_canonical.canonical_outcomes (symbol);

-- ============================================================================
-- STEP 2: Add needle_id to paper_trade_outcomes if missing
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_execution'
        AND table_name = 'paper_trade_outcomes'
        AND column_name = 'needle_id'
    ) THEN
        ALTER TABLE fhq_execution.paper_trade_outcomes
        ADD COLUMN needle_id UUID;

        COMMENT ON COLUMN fhq_execution.paper_trade_outcomes.needle_id IS
        'Canonical needle_id for traceability. CEO Directive CEO-G5-TRACE-2025-12-21.';

        RAISE NOTICE 'Added needle_id to paper_trade_outcomes';
    END IF;
END $$;

-- ============================================================================
-- STEP 3: Create function to capture outcome from g5_paper_trades
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_canonical.capture_trade_outcome(
    p_trade_id UUID,
    p_exit_price NUMERIC,
    p_exit_reason TEXT,
    p_exit_regime TEXT DEFAULT NULL,
    p_exit_defcon INTEGER DEFAULT NULL,
    p_max_favorable NUMERIC DEFAULT NULL,
    p_max_adverse NUMERIC DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $function$
DECLARE
    v_outcome_id UUID;
    v_trade RECORD;
    v_needle RECORD;
    v_pnl_absolute NUMERIC;
    v_pnl_percent NUMERIC;
    v_hold_minutes INTEGER;
BEGIN
    -- Get trade details
    SELECT * INTO v_trade
    FROM fhq_canonical.g5_paper_trades
    WHERE trade_id = p_trade_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Trade not found: %', p_trade_id;
    END IF;

    IF v_trade.needle_id IS NULL THEN
        RAISE EXCEPTION 'Trade % has no needle_id - cannot capture outcome (CEO Directive violation)', p_trade_id;
    END IF;

    -- Get needle context
    SELECT * INTO v_needle
    FROM fhq_canonical.golden_needles
    WHERE needle_id = v_trade.needle_id AND is_current = TRUE;

    -- Calculate PnL
    IF v_trade.direction = 'LONG' THEN
        v_pnl_absolute := (p_exit_price - v_trade.entry_price) * COALESCE(v_trade.position_size / v_trade.entry_price, 1);
        v_pnl_percent := ((p_exit_price - v_trade.entry_price) / v_trade.entry_price) * 100;
    ELSE
        v_pnl_absolute := (v_trade.entry_price - p_exit_price) * COALESCE(v_trade.position_size / v_trade.entry_price, 1);
        v_pnl_percent := ((v_trade.entry_price - p_exit_price) / v_trade.entry_price) * 100;
    END IF;

    -- Calculate hold duration
    v_hold_minutes := EXTRACT(EPOCH FROM (NOW() - v_trade.entry_timestamp)) / 60;

    -- Insert canonical outcome
    INSERT INTO fhq_canonical.canonical_outcomes (
        needle_id,
        trade_id,
        trade_source,
        symbol,
        direction,
        entry_price,
        entry_timestamp,
        entry_regime,
        entry_defcon,
        exit_price,
        exit_timestamp,
        exit_reason,
        exit_regime,
        exit_defcon,
        pnl_absolute,
        pnl_percent,
        hold_duration_minutes,
        max_favorable_excursion,
        max_adverse_excursion,
        needle_eqs_score,
        needle_hypothesis_category,
        needle_target_asset,
        needle_sitc_confidence
    ) VALUES (
        v_trade.needle_id,
        p_trade_id,
        'g5_paper_trades',
        v_trade.symbol,
        v_trade.direction,
        v_trade.entry_price,
        v_trade.entry_timestamp,
        v_trade.entry_regime,
        NULL,  -- entry_defcon from context if available
        p_exit_price,
        NOW(),
        p_exit_reason,
        p_exit_regime,
        p_exit_defcon,
        v_pnl_absolute,
        v_pnl_percent,
        v_hold_minutes,
        p_max_favorable,
        p_max_adverse,
        v_needle.eqs_score,
        v_needle.hypothesis_category,
        v_needle.target_asset,
        v_needle.sitc_confidence_level
    ) RETURNING outcome_id INTO v_outcome_id;

    -- Update the trade record
    UPDATE fhq_canonical.g5_paper_trades
    SET
        exit_price = p_exit_price,
        exit_timestamp = NOW(),
        exit_trigger = p_exit_reason,
        pnl_absolute = v_pnl_absolute,
        pnl_percent = v_pnl_percent,
        trade_outcome = CASE
            WHEN v_pnl_absolute > 0 THEN 'WIN'
            WHEN v_pnl_absolute < 0 THEN 'LOSS'
            ELSE 'BREAKEVEN'
        END
    WHERE trade_id = p_trade_id;

    -- Update signal state
    UPDATE fhq_canonical.g5_signal_state
    SET
        current_state = 'COOLING',
        exit_price = p_exit_price,
        exit_pnl = v_pnl_absolute,
        exit_reason = p_exit_reason,
        cooling_started_at = NOW(),
        last_transition = 'PRIMED_TO_COOLING',
        last_transition_at = NOW(),
        transition_count = transition_count + 1,
        updated_at = NOW()
    WHERE needle_id = v_trade.needle_id;

    RETURN v_outcome_id;
END;
$function$;

COMMENT ON FUNCTION fhq_canonical.capture_trade_outcome IS
'Capture ground truth outcome when a trade exits.
CEO Directive CEO-G5-TRACE-2025-12-21: No learning, just facts.
Returns outcome_id for audit trail.';

-- ============================================================================
-- STEP 4: Create outcome summary view
-- ============================================================================

CREATE OR REPLACE VIEW fhq_canonical.v_outcome_summary AS
SELECT
    co.needle_id,
    co.trade_id,
    co.symbol,
    co.direction,
    co.entry_price,
    co.exit_price,
    co.pnl_absolute,
    co.pnl_percent,
    co.exit_reason,
    co.hold_duration_minutes,
    co.needle_eqs_score,
    co.needle_hypothesis_category,
    co.needle_target_asset,
    co.exit_timestamp,
    CASE
        WHEN co.pnl_absolute > 0 THEN 'WIN'
        WHEN co.pnl_absolute < 0 THEN 'LOSS'
        ELSE 'BREAKEVEN'
    END as outcome_class
FROM fhq_canonical.canonical_outcomes co
ORDER BY co.exit_timestamp DESC;

COMMENT ON VIEW fhq_canonical.v_outcome_summary IS
'Summary view of canonical outcomes for analysis.
Ground truth only - no derived metrics or learning signals.';

-- ============================================================================
-- STEP 5: Create outcome statistics function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_canonical.get_outcome_statistics()
RETURNS TABLE (
    total_outcomes BIGINT,
    wins BIGINT,
    losses BIGINT,
    breakeven BIGINT,
    win_rate NUMERIC,
    total_pnl NUMERIC,
    avg_pnl NUMERIC,
    avg_winner NUMERIC,
    avg_loser NUMERIC,
    avg_hold_minutes NUMERIC,
    by_exit_reason JSONB
)
LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*) as total_outcomes,
        COUNT(*) FILTER (WHERE pnl_absolute > 0) as wins,
        COUNT(*) FILTER (WHERE pnl_absolute < 0) as losses,
        COUNT(*) FILTER (WHERE pnl_absolute = 0) as breakeven,
        ROUND(
            (COUNT(*) FILTER (WHERE pnl_absolute > 0)::NUMERIC / NULLIF(COUNT(*), 0)) * 100,
            2
        ) as win_rate,
        ROUND(SUM(pnl_absolute), 2) as total_pnl,
        ROUND(AVG(pnl_absolute), 2) as avg_pnl,
        ROUND(AVG(pnl_absolute) FILTER (WHERE pnl_absolute > 0), 2) as avg_winner,
        ROUND(AVG(pnl_absolute) FILTER (WHERE pnl_absolute < 0), 2) as avg_loser,
        ROUND(AVG(hold_duration_minutes), 0) as avg_hold_minutes,
        jsonb_object_agg(
            COALESCE(exit_reason, 'UNKNOWN'),
            reason_count
        ) as by_exit_reason
    FROM fhq_canonical.canonical_outcomes,
    LATERAL (
        SELECT exit_reason, COUNT(*) as reason_count
        FROM fhq_canonical.canonical_outcomes
        GROUP BY exit_reason
    ) exit_reasons;
END;
$function$;

-- ============================================================================
-- STEP 6: Log migration
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    agent_id,
    metadata
) VALUES (
    'MIGRATION_EXECUTED',
    'fhq_canonical.canonical_outcomes',
    'SCHEMA_CREATION',
    'CEO_DIRECTIVE',
    'APPROVED',
    'CEO-G5-TRACE-2025-12-21 Phase 2: Ground truth outcome capture',
    'STIG',
    jsonb_build_object(
        'migration_id', '165_canonical_outcome_capture',
        'directive', 'CEO-G5-TRACE-2025-12-21',
        'phase', 'GROUND_TRUTH_CAPTURE',
        'tables_created', ARRAY['fhq_canonical.canonical_outcomes'],
        'functions_created', ARRAY['capture_trade_outcome', 'get_outcome_statistics'],
        'executed_at', NOW()
    )
);

