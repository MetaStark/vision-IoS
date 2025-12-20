-- ============================================================================
-- Migration 144: IoS-008 Decision Engine Infrastructure
-- ============================================================================
-- CEO Directive: CD-IOS008-DECISION-ENGINE-001
-- Date: 2025-12-15
-- Purpose: Coordinated decision-making for validated G1 signals
--
-- Key Features:
--   1. Batch collection of G1 signals (15-min windows)
--   2. Correlation detection between signals
--   3. Conflict resolution (no contradicting positions)
--   4. Regime-aware filtering via IoS-003
--   5. Capital allocation with risk budget
--   6. DEFCON circuit breaker binding (ADR-016)
--
-- Pipeline: G1 Signals -> IoS-008 -> G2 Decision Plans -> IoS-012 Execution
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. DECISION BATCHES TABLE
-- ============================================================================
-- Groups G1 signals into decision windows for coordinated processing

CREATE TABLE IF NOT EXISTS fhq_alpha.decision_batches (
    batch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Timing
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    batch_interval_minutes INTEGER NOT NULL DEFAULT 15,

    -- State capture at batch time
    regime_at_batch TEXT,
    defcon_at_batch INTEGER NOT NULL DEFAULT 5,
    state_hash_at_batch TEXT,

    -- Signals in this batch
    signals_received INTEGER NOT NULL DEFAULT 0,
    signals_after_dedup INTEGER,
    signals_after_conflict_check INTEGER,
    signals_after_regime_filter INTEGER,
    signals_approved INTEGER,

    -- Capital allocation
    total_capital_available DECIMAL(18,2),
    capital_allocated DECIMAL(18,2),
    allocation_method TEXT DEFAULT 'EQUAL_WEIGHT',

    -- Status
    batch_status TEXT NOT NULL DEFAULT 'COLLECTING' CHECK (batch_status IN (
        'COLLECTING', 'PROCESSING', 'DECIDED', 'EXECUTED', 'EXPIRED', 'BLOCKED'
    )),
    blocked_reason TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processing_started_at TIMESTAMPTZ,
    decided_at TIMESTAMPTZ,

    -- Audit
    processor_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_batch_status ON fhq_alpha.decision_batches(batch_status);
CREATE INDEX IF NOT EXISTS idx_batch_window ON fhq_alpha.decision_batches(window_start, window_end);

-- ============================================================================
-- 2. BATCH SIGNALS TABLE
-- ============================================================================
-- Links G1 signals to their decision batch with processing metadata

CREATE TABLE IF NOT EXISTS fhq_alpha.batch_signals (
    batch_signal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES fhq_alpha.decision_batches(batch_id),
    signal_id UUID NOT NULL REFERENCES fhq_alpha.g1_validated_signals(signal_id),

    -- Processing stages
    stage TEXT NOT NULL DEFAULT 'RECEIVED' CHECK (stage IN (
        'RECEIVED', 'DEDUP_PASSED', 'DEDUP_FILTERED',
        'CONFLICT_PASSED', 'CONFLICT_FILTERED',
        'REGIME_PASSED', 'REGIME_FILTERED',
        'APPROVED', 'REJECTED'
    )),

    -- Filtering details
    filtered_by TEXT,  -- 'DUPLICATE', 'CONFLICT', 'REGIME', 'RISK_BUDGET'
    filter_reason TEXT,
    correlated_with_signal_id UUID,  -- If filtered as duplicate
    conflicts_with_signal_id UUID,   -- If filtered due to conflict

    -- Allocation (if approved)
    allocated_capital DECIMAL(18,2),
    position_size DECIMAL(18,8),
    weight_in_batch DECIMAL(5,4),

    -- Priority score (for ranking)
    priority_score DECIMAL(8,4),
    rank_in_batch INTEGER,

    -- Timestamps
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,

    UNIQUE(batch_id, signal_id)
);

CREATE INDEX IF NOT EXISTS idx_batch_signals_batch ON fhq_alpha.batch_signals(batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_signals_signal ON fhq_alpha.batch_signals(signal_id);
CREATE INDEX IF NOT EXISTS idx_batch_signals_stage ON fhq_alpha.batch_signals(stage);

-- ============================================================================
-- 3. SIGNAL CORRELATIONS TABLE
-- ============================================================================
-- Tracks correlation between signals for deduplication

CREATE TABLE IF NOT EXISTS fhq_alpha.signal_correlations (
    correlation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_a_id UUID NOT NULL REFERENCES fhq_alpha.g1_validated_signals(signal_id),
    signal_b_id UUID NOT NULL REFERENCES fhq_alpha.g1_validated_signals(signal_id),

    -- Correlation metrics
    correlation_type TEXT NOT NULL CHECK (correlation_type IN (
        'SAME_CATEGORY', 'SAME_INSTRUMENT', 'SAME_REGIME_TARGET',
        'OVERLAPPING_LOGIC', 'STATISTICAL'
    )),
    correlation_score DECIMAL(5,4) CHECK (correlation_score BETWEEN 0 AND 1),

    -- Resolution
    resolution TEXT CHECK (resolution IN (
        'KEEP_BOTH', 'KEEP_A', 'KEEP_B', 'MERGE', 'PENDING'
    )),
    resolution_reason TEXT,

    -- Timestamps
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,

    UNIQUE(signal_a_id, signal_b_id)
);

-- ============================================================================
-- 4. DECISION PLANS TABLE (G2)
-- ============================================================================
-- Final approved decisions ready for IoS-012 execution

CREATE TABLE IF NOT EXISTS fhq_alpha.g2_decision_plans (
    plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES fhq_alpha.decision_batches(batch_id),
    signal_id UUID NOT NULL REFERENCES fhq_alpha.g1_validated_signals(signal_id),

    -- Decision details
    decision_type TEXT NOT NULL DEFAULT 'SIGNAL_EXECUTION',
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT', 'CLOSE')),

    -- Position sizing
    target_position_size DECIMAL(18,8),
    target_capital DECIMAL(18,2),
    max_capital DECIMAL(18,2),

    -- Entry/Exit parameters
    entry_price_type TEXT DEFAULT 'MARKET',
    entry_limit_price DECIMAL(18,8),
    stop_loss_pct DECIMAL(5,4),
    take_profit_pct DECIMAL(5,4),

    -- Time constraints (TTL)
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMPTZ NOT NULL,
    ttl_minutes INTEGER NOT NULL DEFAULT 60,

    -- State binding (ADR-018)
    state_hash_at_decision TEXT NOT NULL,
    regime_at_decision TEXT NOT NULL,
    defcon_at_decision INTEGER NOT NULL,

    -- Confidence and priority
    decision_confidence DECIMAL(5,4) NOT NULL,
    execution_priority INTEGER NOT NULL DEFAULT 5,

    -- Status
    plan_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (plan_status IN (
        'PENDING', 'QUEUED_FOR_EXECUTION', 'EXECUTING',
        'EXECUTED', 'PARTIALLY_EXECUTED', 'EXPIRED', 'CANCELLED', 'FAILED'
    )),

    -- Execution tracking
    forwarded_to_ios012_at TIMESTAMPTZ,
    execution_started_at TIMESTAMPTZ,
    execution_completed_at TIMESTAMPTZ,
    execution_result JSONB,

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT DEFAULT 'IoS-008',

    -- Governance
    requires_human_approval BOOLEAN DEFAULT FALSE,
    human_approved_at TIMESTAMPTZ,
    human_approved_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_g2_plans_status ON fhq_alpha.g2_decision_plans(plan_status);
CREATE INDEX IF NOT EXISTS idx_g2_plans_batch ON fhq_alpha.g2_decision_plans(batch_id);
CREATE INDEX IF NOT EXISTS idx_g2_plans_valid ON fhq_alpha.g2_decision_plans(valid_until) WHERE plan_status = 'PENDING';

-- ============================================================================
-- 5. RISK BUDGET TABLE
-- ============================================================================
-- Tracks available risk budget for capital allocation

CREATE TABLE IF NOT EXISTS fhq_alpha.risk_budget (
    budget_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_date DATE NOT NULL DEFAULT CURRENT_DATE,

    -- Capital limits
    total_capital DECIMAL(18,2) NOT NULL,
    max_position_pct DECIMAL(5,4) NOT NULL DEFAULT 0.10,  -- Max 10% per position
    max_daily_risk_pct DECIMAL(5,4) NOT NULL DEFAULT 0.02, -- Max 2% daily risk

    -- Current usage
    capital_deployed DECIMAL(18,2) NOT NULL DEFAULT 0,
    positions_open INTEGER NOT NULL DEFAULT 0,
    daily_pnl DECIMAL(18,2) NOT NULL DEFAULT 0,
    daily_risk_used DECIMAL(5,4) NOT NULL DEFAULT 0,

    -- Limits by category
    max_per_category JSONB DEFAULT '{"REGIME_EDGE": 3, "VOLATILITY": 2, "MOMENTUM": 3}'::jsonb,
    current_per_category JSONB DEFAULT '{}'::jsonb,

    -- DEFCON modifiers
    defcon_multiplier DECIMAL(3,2) NOT NULL DEFAULT 1.0,
    -- DEFCON 5: 1.0, DEFCON 4: 0.8, DEFCON 3: 0.5, DEFCON 2: 0.2, DEFCON 1: 0.0

    -- Status
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(budget_date, is_current)
);

-- Insert default risk budget
INSERT INTO fhq_alpha.risk_budget (
    total_capital, max_position_pct, max_daily_risk_pct
) VALUES (
    10000.00, 0.10, 0.02
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- 6. CORRELATION DETECTION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_alpha.fn_detect_signal_correlations(
    p_signal_id UUID
) RETURNS TABLE (
    correlated_signal_id UUID,
    correlation_type TEXT,
    correlation_score DECIMAL(5,4)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s2.signal_id,
        CASE
            WHEN s1.category = s2.category THEN 'SAME_CATEGORY'
            WHEN s1.regime_filter && s2.regime_filter THEN 'SAME_REGIME_TARGET'
            ELSE 'OVERLAPPING_LOGIC'
        END::TEXT,
        CASE
            WHEN s1.category = s2.category AND s1.title ILIKE '%' || split_part(s2.title, ' ', 1) || '%' THEN 0.9
            WHEN s1.category = s2.category THEN 0.7
            WHEN s1.regime_filter && s2.regime_filter THEN 0.5
            ELSE 0.3
        END::DECIMAL(5,4)
    FROM fhq_alpha.g1_validated_signals s1
    JOIN fhq_alpha.g1_validated_signals s2 ON s1.signal_id != s2.signal_id
    WHERE s1.signal_id = p_signal_id
      AND s2.status = 'QUEUED_FOR_IOS008'
      AND (
          s1.category = s2.category
          OR s1.regime_filter && s2.regime_filter
          OR s1.title ILIKE '%' || split_part(s2.title, ' ', 1) || '%'
      );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. CONFLICT DETECTION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_alpha.fn_detect_signal_conflicts(
    p_signal_id UUID
) RETURNS TABLE (
    conflicting_signal_id UUID,
    conflict_type TEXT,
    conflict_reason TEXT
) AS $$
DECLARE
    v_signal RECORD;
BEGIN
    -- Get the signal details
    SELECT * INTO v_signal FROM fhq_alpha.g1_validated_signals WHERE signal_id = p_signal_id;

    -- Check for existing open positions that would conflict
    -- (This is a placeholder - would need integration with position tracking)

    -- Check for other signals in queue that would conflict
    RETURN QUERY
    SELECT
        s2.signal_id,
        'OPPOSING_DIRECTION'::TEXT,
        'Signals target same regime with potentially opposing logic'::TEXT
    FROM fhq_alpha.g1_validated_signals s2
    WHERE s2.signal_id != p_signal_id
      AND s2.status = 'QUEUED_FOR_IOS008'
      AND s2.category = v_signal.category
      AND s2.validated_at > NOW() - INTERVAL '1 hour';

    RETURN;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. REGIME FILTER FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_alpha.fn_check_regime_compatibility(
    p_signal_id UUID
) RETURNS TABLE (
    is_compatible BOOLEAN,
    current_regime TEXT,
    signal_regime_filter TEXT[],
    reason TEXT
) AS $$
DECLARE
    v_current_regime TEXT := 'NEUTRAL';
    v_signal_filter TEXT[];
BEGIN
    -- Get current regime from IoS-003
    BEGIN
        SELECT sovereign_regime INTO v_current_regime
        FROM fhq_perception.sovereign_regime_state_v4
        WHERE asset_id = 'BTC-USD'
        ORDER BY timestamp DESC
        LIMIT 1;
    EXCEPTION WHEN OTHERS THEN
        v_current_regime := 'NEUTRAL';
    END;

    -- Get signal's regime filter
    SELECT regime_filter INTO v_signal_filter
    FROM fhq_alpha.g1_validated_signals
    WHERE signal_id = p_signal_id;

    -- Check compatibility
    IF v_signal_filter IS NULL OR array_length(v_signal_filter, 1) IS NULL THEN
        -- No filter means compatible with all regimes
        RETURN QUERY SELECT TRUE, v_current_regime, v_signal_filter, 'No regime filter - compatible with all';
    ELSIF v_current_regime = ANY(v_signal_filter) THEN
        RETURN QUERY SELECT TRUE, v_current_regime, v_signal_filter, 'Current regime matches filter';
    ELSE
        RETURN QUERY SELECT FALSE, v_current_regime, v_signal_filter,
            'Current regime ' || v_current_regime || ' not in filter ' || array_to_string(v_signal_filter, ',');
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 9. CAPITAL ALLOCATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_alpha.fn_allocate_capital(
    p_batch_id UUID,
    p_allocation_method TEXT DEFAULT 'EQUAL_WEIGHT'
) RETURNS TABLE (
    signal_id UUID,
    allocated_capital DECIMAL(18,2),
    weight DECIMAL(5,4)
) AS $$
DECLARE
    v_budget RECORD;
    v_approved_count INTEGER;
    v_per_signal_capital DECIMAL(18,2);
    v_defcon INTEGER;
BEGIN
    -- Get current risk budget
    SELECT * INTO v_budget FROM fhq_alpha.risk_budget WHERE is_current = TRUE LIMIT 1;

    -- Get current DEFCON
    SELECT COALESCE(
        (SELECT current_level FROM fhq_governance.defcon_status ORDER BY changed_at DESC LIMIT 1),
        5
    ) INTO v_defcon;

    -- Apply DEFCON multiplier
    v_budget.total_capital := v_budget.total_capital *
        CASE v_defcon
            WHEN 5 THEN 1.0
            WHEN 4 THEN 0.8
            WHEN 3 THEN 0.5
            WHEN 2 THEN 0.2
            WHEN 1 THEN 0.0
        END;

    -- Count approved signals
    SELECT COUNT(*) INTO v_approved_count
    FROM fhq_alpha.batch_signals
    WHERE batch_id = p_batch_id AND stage = 'APPROVED';

    IF v_approved_count = 0 OR v_budget.total_capital <= 0 THEN
        RETURN;
    END IF;

    -- Calculate per-signal capital (equal weight)
    v_per_signal_capital := LEAST(
        v_budget.total_capital / v_approved_count,
        v_budget.total_capital * v_budget.max_position_pct
    );

    RETURN QUERY
    SELECT
        bs.signal_id,
        v_per_signal_capital,
        (1.0 / v_approved_count)::DECIMAL(5,4)
    FROM fhq_alpha.batch_signals bs
    WHERE bs.batch_id = p_batch_id AND bs.stage = 'APPROVED';
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 10. DEFCON CHECK FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_alpha.fn_check_defcon_allows_trading()
RETURNS BOOLEAN AS $$
DECLARE
    v_defcon INTEGER;
BEGIN
    SELECT COALESCE(
        (SELECT current_level FROM fhq_governance.defcon_status ORDER BY changed_at DESC LIMIT 1),
        5
    ) INTO v_defcon;

    -- DEFCON 1-2 blocks all trading
    RETURN v_defcon >= 3;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 11. BATCH PROCESSING TRIGGER
-- ============================================================================
-- Auto-add new G1 signals to current collecting batch

CREATE OR REPLACE FUNCTION fhq_alpha.fn_add_signal_to_batch()
RETURNS TRIGGER AS $$
DECLARE
    v_batch_id UUID;
    v_window_start TIMESTAMPTZ;
    v_window_end TIMESTAMPTZ;
BEGIN
    -- Only process signals moving to QUEUED_FOR_IOS008
    IF NEW.status != 'QUEUED_FOR_IOS008' THEN
        RETURN NEW;
    END IF;

    -- Calculate current window (15-minute intervals)
    v_window_start := date_trunc('hour', NOW()) +
        (EXTRACT(minute FROM NOW())::INTEGER / 15) * INTERVAL '15 minutes';
    v_window_end := v_window_start + INTERVAL '15 minutes';

    -- Get or create batch for current window
    SELECT batch_id INTO v_batch_id
    FROM fhq_alpha.decision_batches
    WHERE window_start = v_window_start
      AND batch_status = 'COLLECTING'
    LIMIT 1;

    IF v_batch_id IS NULL THEN
        INSERT INTO fhq_alpha.decision_batches (
            window_start, window_end, batch_interval_minutes
        ) VALUES (
            v_window_start, v_window_end, 15
        ) RETURNING batch_id INTO v_batch_id;
    END IF;

    -- Add signal to batch
    INSERT INTO fhq_alpha.batch_signals (batch_id, signal_id, stage)
    VALUES (v_batch_id, NEW.signal_id, 'RECEIVED')
    ON CONFLICT (batch_id, signal_id) DO NOTHING;

    -- Update batch signal count
    UPDATE fhq_alpha.decision_batches
    SET signals_received = signals_received + 1
    WHERE batch_id = v_batch_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_g1_signal_to_batch ON fhq_alpha.g1_validated_signals;
CREATE TRIGGER trg_g1_signal_to_batch
    AFTER UPDATE ON fhq_alpha.g1_validated_signals
    FOR EACH ROW
    WHEN (NEW.status = 'QUEUED_FOR_IOS008' AND OLD.status != 'QUEUED_FOR_IOS008')
    EXECUTE FUNCTION fhq_alpha.fn_add_signal_to_batch();

-- ============================================================================
-- 12. LOG ACTIVATION
-- ============================================================================

INSERT INTO fhq_monitoring.system_event_log (event_type, status, metadata)
VALUES (
    'ios008_infrastructure_activated',
    'completed',
    jsonb_build_object(
        'migration', '144_ios008_decision_engine',
        'tables_created', ARRAY[
            'decision_batches', 'batch_signals', 'signal_correlations',
            'g2_decision_plans', 'risk_budget'
        ],
        'functions_created', ARRAY[
            'fn_detect_signal_correlations', 'fn_detect_signal_conflicts',
            'fn_check_regime_compatibility', 'fn_allocate_capital',
            'fn_check_defcon_allows_trading', 'fn_add_signal_to_batch'
        ],
        'timestamp', NOW()
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_tables INTEGER;
    v_functions INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_tables
    FROM information_schema.tables
    WHERE table_schema = 'fhq_alpha'
    AND table_name IN ('decision_batches', 'batch_signals', 'signal_correlations',
                       'g2_decision_plans', 'risk_budget');

    SELECT COUNT(*) INTO v_functions
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'fhq_alpha'
    AND p.proname LIKE 'fn_%';

    RAISE NOTICE '=== IoS-008 Infrastructure Verification ===';
    RAISE NOTICE 'Tables created: % / 5', v_tables;
    RAISE NOTICE 'Functions created: %', v_functions;

    IF v_tables = 5 THEN
        RAISE NOTICE 'STATUS: SUCCESS - IoS-008 ready for operation';
    ELSE
        RAISE WARNING 'STATUS: INCOMPLETE - Manual verification required';
    END IF;
END $$;
