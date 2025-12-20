-- ============================================================================
-- MIGRATION 153: G5 SILENT SNIPER ARCHITECTURE
-- CEO Directive WAVE 17 - 2025-12-18
-- ============================================================================
-- PURPOSE: Implement "Silent Sniper" paper-execution mode with continuous
--          Golden Needle ingestion and Central Context Orchestrator
--
-- AMENDMENTS (STIG META-ANALYSIS):
--   1. CCO_COHERENCE_WINDOW: 300s maximum context age
--   2. Signal Priority Queue with orthogonality-based selection
--   3. Explicit G5 Exit Criteria (quantifiable milestones)
--   4. MAX_CONTEXT_DIMENSIONS: 4 (parsimony constraint)
--   5. Three-level CCO Failover (graceful degradation)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. ADDITIONAL LOCKED PARAMETERS (WAVE 17 Amendments)
-- ============================================================================

-- Add new parameters to existing G4.2 parameters table
INSERT INTO fhq_canonical.g4_2_parameters (parameter_name, parameter_value, description, locked_by) VALUES
    -- Amendment 1: CCO Coherence Window
    ('CCO_COHERENCE_WINDOW_SECONDS', 300, 'Maximum age of context data in seconds before considered stale', 'CEO_DIRECTIVE_WAVE_17'),

    -- Amendment 4: Parsimony Constraint
    ('MAX_CONTEXT_DIMENSIONS', 4, 'Maximum context features per signal profile to prevent overfitting', 'CEO_DIRECTIVE_WAVE_17'),

    -- Amendment 3: G5 Exit Criteria
    ('G5_MIN_PAPER_TRADES', 100, 'Minimum paper trades required for G5 exit consideration', 'CEO_DIRECTIVE_WAVE_17'),
    ('G5_MIN_PAPER_SHARPE', 1.5, 'Minimum Sharpe ratio in paper mode for G5 exit', 'CEO_DIRECTIVE_WAVE_17'),
    ('G5_MAX_PAPER_DRAWDOWN', 0.15, 'Maximum drawdown (15%) allowed in paper mode for G5 exit', 'CEO_DIRECTIVE_WAVE_17'),
    ('G5_MIN_PAPER_WIN_RATE', 0.45, 'Minimum win rate (45%) in paper mode for G5 exit', 'CEO_DIRECTIVE_WAVE_17'),
    ('G5_MIN_PAPER_DURATION_DAYS', 90, 'Minimum paper trading duration in days for G5 exit', 'CEO_DIRECTIVE_WAVE_17'),

    -- Amendment 5: CCO Failover Thresholds
    ('CCO_DEGRADED_LAG_SECONDS', 15, 'Context lag threshold for DEGRADED state', 'CEO_DIRECTIVE_WAVE_17'),
    ('CCO_DEGRADED_MIN_SHARPE', 2.0, 'Minimum Sharpe for signal execution in DEGRADED CCO state', 'CEO_DIRECTIVE_WAVE_17'),

    -- Signal Cooling Period
    ('SIGNAL_COOLING_PERIODS', 5, 'Number of periods to wait after exit before signal can re-enter', 'CEO_DIRECTIVE_WAVE_17')
ON CONFLICT (parameter_name) DO NOTHING;

-- ============================================================================
-- 2. CENTRAL CONTEXT ORCHESTRATOR (CCO) STATE TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g5_cco_state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- CCO Operational State (Amendment 5: Three-level failover)
    cco_status TEXT NOT NULL DEFAULT 'OPERATIONAL' CHECK (cco_status IN (
        'OPERATIONAL',      -- Normal permit/block logic
        'DEGRADED',         -- Only high-Sharpe signals allowed
        'UNAVAILABLE'       -- Full halt, triggers DEFCON-2
    )),

    -- Current Context Values (Single Point of Truth)
    current_regime TEXT,                    -- BULL, BEAR, NEUTRAL, STRESS
    current_regime_confidence NUMERIC,      -- 0.0 - 1.0
    current_vol_percentile NUMERIC,         -- 0 - 100
    current_vol_state TEXT,                 -- COMPRESSING, STABLE, EXPANDING
    current_liquidity_state TEXT,           -- HIGH, NORMAL, LOW, CRISIS
    current_market_hours BOOLEAN,           -- TRUE if within trading hours

    -- Context Timestamp (Amendment 1: Coherence Window)
    context_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Note: context_age_seconds and context_coherent computed at query time via helper function

    -- DEFCON Integration
    defcon_level INT DEFAULT 5,             -- 1-5 (1=critical, 5=normal)
    defcon_blocks_execution BOOLEAN DEFAULT FALSE,

    -- Global Permit (derived from all conditions)
    global_permit_active BOOLEAN DEFAULT FALSE,
    permit_reason TEXT,

    -- Metadata
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by TEXT DEFAULT 'CCO_DAEMON',

    -- Singleton constraint (only one active state row)
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(is_active) -- Ensures only one active row
);

-- Insert initial CCO state
INSERT INTO fhq_canonical.g5_cco_state (
    cco_status, current_regime, current_vol_percentile, current_vol_state,
    global_permit_active, permit_reason, is_active
) VALUES (
    'OPERATIONAL', 'NEUTRAL', 50, 'STABLE',
    FALSE, 'Initial state - awaiting first context update', TRUE
) ON CONFLICT (is_active) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_g5_cco_state_active ON fhq_canonical.g5_cco_state(is_active);

-- ============================================================================
-- 3. SIGNAL PRIORITY QUEUE (Amendment 2: Orthogonality-based Selection)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g5_signal_priority_queue (
    queue_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Context Window Reference
    context_window_id UUID NOT NULL,
    context_timestamp TIMESTAMPTZ NOT NULL,

    -- Eligible Signals (all with context permit)
    eligible_needle_ids UUID[] NOT NULL,
    eligible_count INT,  -- Computed at insert time: array_length(eligible_needle_ids, 1)

    -- Selected Signal (highest orthogonality to current portfolio)
    selected_needle_id UUID,
    selection_orthogonality_score NUMERIC,  -- Lower = more orthogonal

    -- Selection Reasoning
    selection_reason JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Example: {"method": "max_orthogonality", "portfolio_correlation": 0.12, "runner_up": "..."}

    -- Execution Status
    execution_status TEXT DEFAULT 'PENDING' CHECK (execution_status IN (
        'PENDING',          -- Awaiting execution
        'EXECUTING',        -- Order sent
        'FILLED',           -- Order filled
        'REJECTED',         -- Order rejected
        'EXPIRED',          -- Context window expired
        'CANCELLED'         -- Manually cancelled
    )),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    executed_at TIMESTAMPTZ,

    -- Governance
    created_by TEXT DEFAULT 'CCO'
);

CREATE INDEX IF NOT EXISTS idx_g5_queue_status ON fhq_canonical.g5_signal_priority_queue(execution_status);
CREATE INDEX IF NOT EXISTS idx_g5_queue_context ON fhq_canonical.g5_signal_priority_queue(context_window_id);
CREATE INDEX IF NOT EXISTS idx_g5_queue_created ON fhq_canonical.g5_signal_priority_queue(created_at DESC);

-- ============================================================================
-- 4. SILENT SNIPER STATE MACHINE
-- ============================================================================

-- Signal state tracking table
CREATE TABLE IF NOT EXISTS fhq_canonical.g5_signal_state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),

    -- Current State (per state machine diagram)
    current_state TEXT NOT NULL DEFAULT 'DORMANT' CHECK (current_state IN (
        'DORMANT',          -- Silent waiting (default)
        'PRIMED',           -- Pre-execution coherence check
        'EXECUTING',        -- Paper order sent, awaiting fill
        'POSITION',         -- Holding position, monitoring exit
        'COOLING'           -- Post-exit cooldown period
    )),

    -- State Timestamps
    state_entered_at TIMESTAMPTZ DEFAULT NOW(),
    dormant_since TIMESTAMPTZ,
    primed_at TIMESTAMPTZ,
    executing_at TIMESTAMPTZ,
    position_entered_at TIMESTAMPTZ,
    cooling_started_at TIMESTAMPTZ,

    -- Cooling Period Tracking
    cooling_periods_remaining INT DEFAULT 0,
    cooling_complete_at TIMESTAMPTZ,

    -- Current Position Details (when in POSITION state)
    position_direction TEXT,                -- LONG, SHORT
    position_entry_price NUMERIC,
    position_size NUMERIC,
    position_entry_context JSONB,           -- Context at entry

    -- Exit Conditions
    exit_signal_triggered BOOLEAN DEFAULT FALSE,
    exit_context_revoked BOOLEAN DEFAULT FALSE,
    exit_stop_loss_hit BOOLEAN DEFAULT FALSE,
    exit_reason TEXT,
    exit_price NUMERIC,
    exit_pnl NUMERIC,

    -- State Machine Metadata
    last_transition TEXT,                   -- e.g., "DORMANT->PRIMED"
    last_transition_at TIMESTAMPTZ,
    transition_count INT DEFAULT 0,

    -- Governance
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(needle_id)
);

CREATE INDEX IF NOT EXISTS idx_g5_signal_state_needle ON fhq_canonical.g5_signal_state(needle_id);
CREATE INDEX IF NOT EXISTS idx_g5_signal_state_current ON fhq_canonical.g5_signal_state(current_state);

-- State transition history for audit
CREATE TABLE IF NOT EXISTS fhq_canonical.g5_state_transitions (
    transition_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL,

    -- Transition Details
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    transition_trigger TEXT NOT NULL,       -- What caused the transition

    -- Context at Transition
    context_snapshot JSONB,
    cco_status TEXT,

    -- Transition Validation
    transition_valid BOOLEAN DEFAULT TRUE,
    validation_errors JSONB,

    -- Timestamps
    transitioned_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_g5_transitions_needle ON fhq_canonical.g5_state_transitions(needle_id);
CREATE INDEX IF NOT EXISTS idx_g5_transitions_time ON fhq_canonical.g5_state_transitions(transitioned_at DESC);

-- ============================================================================
-- 5. G5 PAPER TRADING LEDGER
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g5_paper_trades (
    trade_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),

    -- Trade Details
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    entry_price NUMERIC NOT NULL,
    exit_price NUMERIC,
    position_size NUMERIC NOT NULL,

    -- Context at Entry
    entry_context JSONB NOT NULL,
    entry_cco_status TEXT NOT NULL,
    entry_vol_percentile NUMERIC,
    entry_regime TEXT,

    -- Context at Exit
    exit_context JSONB,
    exit_trigger TEXT,                      -- SIGNAL, CONTEXT_REVOKED, STOP_LOSS, TIMEOUT

    -- Performance
    pnl_absolute NUMERIC,
    pnl_percent NUMERIC,
    holding_periods INT,

    -- Classification
    trade_outcome TEXT CHECK (trade_outcome IN ('WIN', 'LOSS', 'BREAKEVEN', 'OPEN')),

    -- Timestamps
    entry_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exit_timestamp TIMESTAMPTZ,

    -- Governance
    logged_by TEXT DEFAULT 'SILENT_SNIPER'
);

CREATE INDEX IF NOT EXISTS idx_g5_paper_trades_needle ON fhq_canonical.g5_paper_trades(needle_id);
CREATE INDEX IF NOT EXISTS idx_g5_paper_trades_outcome ON fhq_canonical.g5_paper_trades(trade_outcome);
CREATE INDEX IF NOT EXISTS idx_g5_paper_trades_entry ON fhq_canonical.g5_paper_trades(entry_timestamp DESC);

-- ============================================================================
-- 6. G5 EXIT CRITERIA TRACKING (Amendment 3)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g5_exit_criteria_status (
    status_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Current Metrics
    total_paper_trades INT DEFAULT 0,
    paper_sharpe NUMERIC,
    paper_max_drawdown NUMERIC,
    paper_win_rate NUMERIC,
    paper_start_date DATE,
    paper_duration_days INT DEFAULT 0,  -- Computed by update trigger/function

    -- Criteria Pass/Fail Status (computed by g5_check_exit_criteria function)
    passes_min_trades BOOLEAN DEFAULT FALSE,
    passes_sharpe BOOLEAN DEFAULT FALSE,
    passes_drawdown BOOLEAN DEFAULT FALSE,
    passes_win_rate BOOLEAN DEFAULT FALSE,
    passes_duration BOOLEAN DEFAULT FALSE,

    -- Overall G5 Eligibility
    all_criteria_passed BOOLEAN DEFAULT FALSE,
    g5_eligible_since TIMESTAMPTZ,

    -- Governance Gates
    vega_attestation TEXT DEFAULT 'PENDING' CHECK (vega_attestation IN (
        'PENDING', 'G5_PASS', 'G5_WARN', 'G5_FAIL'
    )),
    vega_attestation_at TIMESTAMPTZ,
    ceo_two_man_rule TEXT DEFAULT 'PENDING' CHECK (ceo_two_man_rule IN (
        'PENDING', 'FULFILLED', 'DENIED'
    )),
    ceo_approval_at TIMESTAMPTZ,

    -- Live Activation Status
    live_activation_authorized BOOLEAN DEFAULT FALSE,
    live_activation_blocked_reason TEXT,

    -- Timestamps
    last_updated TIMESTAMPTZ DEFAULT NOW(),

    -- Singleton
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(is_active)
);

-- Insert initial status
INSERT INTO fhq_canonical.g5_exit_criteria_status (
    total_paper_trades, paper_start_date, is_active
) VALUES (
    0, CURRENT_DATE, TRUE
) ON CONFLICT (is_active) DO NOTHING;

-- ============================================================================
-- 7. CCO FAILOVER STATE MACHINE (Amendment 5)
-- ============================================================================

-- CCO health monitoring
CREATE TABLE IF NOT EXISTS fhq_canonical.g5_cco_health_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Health Check Results
    check_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    context_age_seconds NUMERIC,
    cco_status TEXT NOT NULL,
    previous_status TEXT,

    -- Failover Triggers
    triggered_degraded BOOLEAN DEFAULT FALSE,
    triggered_unavailable BOOLEAN DEFAULT FALSE,
    triggered_defcon BOOLEAN DEFAULT FALSE,
    defcon_level_set INT,

    -- Recovery
    recovered_to_operational BOOLEAN DEFAULT FALSE,
    recovery_timestamp TIMESTAMPTZ,

    -- Signals Affected
    signals_blocked_count INT DEFAULT 0,
    signals_allowed_count INT DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_g5_cco_health_time ON fhq_canonical.g5_cco_health_log(check_timestamp DESC);

-- ============================================================================
-- 8. CONTINUOUS INGESTION PIPELINE TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g5_ingestion_pipeline (
    pipeline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Ingestion Batch
    batch_id TEXT NOT NULL,
    batch_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Source
    source_type TEXT NOT NULL CHECK (source_type IN (
        'FINN_DISCOVERY',       -- FINN Tier-2 hypothesis generation
        'MANUAL_SUBMISSION',    -- Human-submitted hypothesis
        'EXTERNAL_FEED'         -- External alpha source
    )),

    -- Ingested Needles
    needles_ingested INT DEFAULT 0,
    needle_ids UUID[],

    -- Automatic Qualification Pipeline
    needles_passed_g4_1 INT DEFAULT 0,      -- Passed deep validation
    needles_passed_g4_2 INT DEFAULT 0,      -- Passed contextual validation
    needles_g5_eligible INT DEFAULT 0,      -- Became G5 eligible

    -- Qualification Results
    qualification_results JSONB DEFAULT '{}'::jsonb,
    -- Example: {"passed": [...], "failed": [...], "reasons": {...}}

    -- Pipeline Status
    pipeline_status TEXT DEFAULT 'PENDING' CHECK (pipeline_status IN (
        'PENDING',
        'G4_1_RUNNING',
        'G4_2_RUNNING',
        'COMPLETED',
        'FAILED'
    )),

    -- Error Tracking
    errors JSONB,

    -- Timestamps
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Governance
    processed_by TEXT DEFAULT 'INGESTION_DAEMON'
);

CREATE INDEX IF NOT EXISTS idx_g5_pipeline_status ON fhq_canonical.g5_ingestion_pipeline(pipeline_status);
CREATE INDEX IF NOT EXISTS idx_g5_pipeline_batch ON fhq_canonical.g5_ingestion_pipeline(batch_timestamp DESC);

-- ============================================================================
-- 9. HELPER FUNCTIONS
-- ============================================================================

-- Function to check CCO coherence (Amendment 1)
CREATE OR REPLACE FUNCTION fhq_canonical.g5_check_cco_coherence()
RETURNS TABLE (
    is_coherent BOOLEAN,
    context_age_seconds NUMERIC,
    cco_status TEXT,
    permit_allowed BOOLEAN,
    reason TEXT
) AS $$
DECLARE
    v_coherence_window NUMERIC;
    v_degraded_lag NUMERIC;
    v_context_age NUMERIC;
    v_cco_status TEXT;
BEGIN
    -- Get parameters
    SELECT parameter_value INTO v_coherence_window
    FROM fhq_canonical.g4_2_parameters WHERE parameter_name = 'CCO_COHERENCE_WINDOW_SECONDS';

    SELECT parameter_value INTO v_degraded_lag
    FROM fhq_canonical.g4_2_parameters WHERE parameter_name = 'CCO_DEGRADED_LAG_SECONDS';

    -- Get current CCO state
    SELECT
        EXTRACT(EPOCH FROM (NOW() - cco.context_timestamp)),
        cco.cco_status
    INTO v_context_age, v_cco_status
    FROM fhq_canonical.g5_cco_state cco
    WHERE cco.is_active = TRUE;

    -- Evaluate coherence
    IF v_context_age IS NULL THEN
        is_coherent := FALSE;
        context_age_seconds := NULL;
        cco_status := 'UNAVAILABLE';
        permit_allowed := FALSE;
        reason := 'No CCO state found';
    ELSIF v_context_age > v_coherence_window THEN
        is_coherent := FALSE;
        context_age_seconds := v_context_age;
        cco_status := 'UNAVAILABLE';
        permit_allowed := FALSE;
        reason := 'Context expired (age: ' || v_context_age || 's > ' || v_coherence_window || 's)';
    ELSIF v_context_age > v_degraded_lag THEN
        is_coherent := TRUE;
        context_age_seconds := v_context_age;
        cco_status := 'DEGRADED';
        permit_allowed := TRUE;  -- But only high-Sharpe signals
        reason := 'Context degraded (age: ' || v_context_age || 's > ' || v_degraded_lag || 's)';
    ELSE
        is_coherent := TRUE;
        context_age_seconds := v_context_age;
        cco_status := 'OPERATIONAL';
        permit_allowed := TRUE;
        reason := 'Context coherent';
    END IF;

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Function to validate signal can execute in current CCO state
CREATE OR REPLACE FUNCTION fhq_canonical.g5_validate_signal_execution(
    p_needle_id UUID
) RETURNS TABLE (
    can_execute BOOLEAN,
    cco_status TEXT,
    signal_sharpe NUMERIC,
    block_reason TEXT
) AS $$
DECLARE
    v_cco_status TEXT;
    v_degraded_min_sharpe NUMERIC;
    v_signal_sharpe NUMERIC;
    v_defcon_level INT;
BEGIN
    -- Get CCO status
    SELECT cco.cco_status, cco.defcon_level
    INTO v_cco_status, v_defcon_level
    FROM fhq_canonical.g5_cco_state cco
    WHERE cco.is_active = TRUE;

    -- Get signal Sharpe
    SELECT cv.best_contextual_sharpe
    INTO v_signal_sharpe
    FROM fhq_canonical.g4_2_composite_verdict cv
    WHERE cv.needle_id = p_needle_id;

    -- Get degraded threshold
    SELECT parameter_value INTO v_degraded_min_sharpe
    FROM fhq_canonical.g4_2_parameters WHERE parameter_name = 'CCO_DEGRADED_MIN_SHARPE';

    cco_status := COALESCE(v_cco_status, 'UNAVAILABLE');
    signal_sharpe := v_signal_sharpe;

    -- DEFCON check first
    IF v_defcon_level IS NOT NULL AND v_defcon_level <= 2 THEN
        can_execute := FALSE;
        block_reason := 'DEFCON-' || v_defcon_level || ' blocks all execution';
        RETURN NEXT;
        RETURN;
    END IF;

    -- CCO status check
    CASE v_cco_status
        WHEN 'OPERATIONAL' THEN
            can_execute := TRUE;
            block_reason := NULL;
        WHEN 'DEGRADED' THEN
            IF v_signal_sharpe >= v_degraded_min_sharpe THEN
                can_execute := TRUE;
                block_reason := NULL;
            ELSE
                can_execute := FALSE;
                block_reason := 'CCO DEGRADED: Sharpe ' || v_signal_sharpe || ' < ' || v_degraded_min_sharpe;
            END IF;
        WHEN 'UNAVAILABLE' THEN
            can_execute := FALSE;
            block_reason := 'CCO UNAVAILABLE - full halt';
        ELSE
            can_execute := FALSE;
            block_reason := 'Unknown CCO status';
    END CASE;

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Function to check G5 exit criteria
CREATE OR REPLACE FUNCTION fhq_canonical.g5_check_exit_criteria()
RETURNS TABLE (
    all_passed BOOLEAN,
    trades_passed BOOLEAN,
    sharpe_passed BOOLEAN,
    drawdown_passed BOOLEAN,
    win_rate_passed BOOLEAN,
    duration_passed BOOLEAN,
    vega_passed BOOLEAN,
    ceo_passed BOOLEAN,
    blocking_criteria TEXT[]
) AS $$
DECLARE
    v_min_trades INT;
    v_min_sharpe NUMERIC;
    v_max_dd NUMERIC;
    v_min_wr NUMERIC;
    v_min_days INT;
    r RECORD;
BEGIN
    -- Get thresholds
    SELECT parameter_value::INT INTO v_min_trades
    FROM fhq_canonical.g4_2_parameters WHERE parameter_name = 'G5_MIN_PAPER_TRADES';

    SELECT parameter_value INTO v_min_sharpe
    FROM fhq_canonical.g4_2_parameters WHERE parameter_name = 'G5_MIN_PAPER_SHARPE';

    SELECT parameter_value INTO v_max_dd
    FROM fhq_canonical.g4_2_parameters WHERE parameter_name = 'G5_MAX_PAPER_DRAWDOWN';

    SELECT parameter_value INTO v_min_wr
    FROM fhq_canonical.g4_2_parameters WHERE parameter_name = 'G5_MIN_PAPER_WIN_RATE';

    SELECT parameter_value::INT INTO v_min_days
    FROM fhq_canonical.g4_2_parameters WHERE parameter_name = 'G5_MIN_PAPER_DURATION_DAYS';

    -- Get current status
    SELECT * INTO r FROM fhq_canonical.g5_exit_criteria_status WHERE is_active = TRUE;

    IF r IS NULL THEN
        all_passed := FALSE;
        blocking_criteria := ARRAY['No exit criteria status found'];
        RETURN NEXT;
        RETURN;
    END IF;

    -- Evaluate each criterion
    trades_passed := r.total_paper_trades >= v_min_trades;
    sharpe_passed := r.paper_sharpe >= v_min_sharpe;
    drawdown_passed := r.paper_max_drawdown <= v_max_dd;
    win_rate_passed := r.paper_win_rate >= v_min_wr;
    duration_passed := r.paper_duration_days >= v_min_days;
    vega_passed := r.vega_attestation = 'G5_PASS';
    ceo_passed := r.ceo_two_man_rule = 'FULFILLED';

    -- Build blocking list
    blocking_criteria := ARRAY[]::TEXT[];
    IF NOT trades_passed THEN
        blocking_criteria := array_append(blocking_criteria, 'Trades: ' || r.total_paper_trades || ' < ' || v_min_trades);
    END IF;
    IF NOT COALESCE(sharpe_passed, FALSE) THEN
        blocking_criteria := array_append(blocking_criteria, 'Sharpe: ' || COALESCE(r.paper_sharpe::TEXT, 'NULL') || ' < ' || v_min_sharpe);
    END IF;
    IF NOT COALESCE(drawdown_passed, FALSE) THEN
        blocking_criteria := array_append(blocking_criteria, 'Drawdown: ' || COALESCE(r.paper_max_drawdown::TEXT, 'NULL') || ' > ' || v_max_dd);
    END IF;
    IF NOT COALESCE(win_rate_passed, FALSE) THEN
        blocking_criteria := array_append(blocking_criteria, 'Win Rate: ' || COALESCE(r.paper_win_rate::TEXT, 'NULL') || ' < ' || v_min_wr);
    END IF;
    IF NOT COALESCE(duration_passed, FALSE) THEN
        blocking_criteria := array_append(blocking_criteria, 'Duration: ' || r.paper_duration_days || ' < ' || v_min_days || ' days');
    END IF;
    IF NOT vega_passed THEN
        blocking_criteria := array_append(blocking_criteria, 'VEGA: ' || r.vega_attestation);
    END IF;
    IF NOT ceo_passed THEN
        blocking_criteria := array_append(blocking_criteria, 'CEO: ' || r.ceo_two_man_rule);
    END IF;

    all_passed := COALESCE(trades_passed, FALSE) AND COALESCE(sharpe_passed, FALSE) AND
                  COALESCE(drawdown_passed, FALSE) AND COALESCE(win_rate_passed, FALSE) AND
                  COALESCE(duration_passed, FALSE) AND vega_passed AND ceo_passed;

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Function to perform signal state transition
CREATE OR REPLACE FUNCTION fhq_canonical.g5_transition_signal_state(
    p_needle_id UUID,
    p_new_state TEXT,
    p_trigger TEXT,
    p_context JSONB DEFAULT '{}'::jsonb
) RETURNS BOOLEAN AS $$
DECLARE
    v_current_state TEXT;
    v_valid_transition BOOLEAN;
BEGIN
    -- Get current state
    SELECT current_state INTO v_current_state
    FROM fhq_canonical.g5_signal_state
    WHERE needle_id = p_needle_id;

    -- If no state exists, create it
    IF v_current_state IS NULL THEN
        INSERT INTO fhq_canonical.g5_signal_state (needle_id, current_state, dormant_since)
        VALUES (p_needle_id, 'DORMANT', NOW());
        v_current_state := 'DORMANT';
    END IF;

    -- Validate transition (state machine rules)
    v_valid_transition := CASE
        WHEN v_current_state = 'DORMANT' AND p_new_state = 'PRIMED' THEN TRUE
        WHEN v_current_state = 'PRIMED' AND p_new_state IN ('EXECUTING', 'DORMANT') THEN TRUE
        WHEN v_current_state = 'EXECUTING' AND p_new_state IN ('POSITION', 'DORMANT') THEN TRUE
        WHEN v_current_state = 'POSITION' AND p_new_state = 'COOLING' THEN TRUE
        WHEN v_current_state = 'COOLING' AND p_new_state = 'DORMANT' THEN TRUE
        ELSE FALSE
    END;

    IF NOT v_valid_transition THEN
        -- Log invalid transition attempt
        INSERT INTO fhq_canonical.g5_state_transitions (
            needle_id, from_state, to_state, transition_trigger,
            transition_valid, validation_errors
        ) VALUES (
            p_needle_id, v_current_state, p_new_state, p_trigger,
            FALSE, jsonb_build_object('error', 'Invalid state transition')
        );
        RETURN FALSE;
    END IF;

    -- Perform transition
    UPDATE fhq_canonical.g5_signal_state SET
        current_state = p_new_state,
        state_entered_at = NOW(),
        last_transition = v_current_state || '->' || p_new_state,
        last_transition_at = NOW(),
        transition_count = transition_count + 1,
        updated_at = NOW(),
        -- Set state-specific timestamps
        primed_at = CASE WHEN p_new_state = 'PRIMED' THEN NOW() ELSE primed_at END,
        executing_at = CASE WHEN p_new_state = 'EXECUTING' THEN NOW() ELSE executing_at END,
        position_entered_at = CASE WHEN p_new_state = 'POSITION' THEN NOW() ELSE position_entered_at END,
        cooling_started_at = CASE WHEN p_new_state = 'COOLING' THEN NOW() ELSE cooling_started_at END,
        dormant_since = CASE WHEN p_new_state = 'DORMANT' THEN NOW() ELSE dormant_since END
    WHERE needle_id = p_needle_id;

    -- Log transition
    INSERT INTO fhq_canonical.g5_state_transitions (
        needle_id, from_state, to_state, transition_trigger,
        context_snapshot, transition_valid
    ) VALUES (
        p_needle_id, v_current_state, p_new_state, p_trigger,
        p_context, TRUE
    );

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 10. INITIALIZE SIGNAL STATES FOR G5-ELIGIBLE NEEDLES
-- ============================================================================

-- Create DORMANT state for all VALIDATED-CONTEXTUAL signals
INSERT INTO fhq_canonical.g5_signal_state (needle_id, current_state, dormant_since)
SELECT
    cv.needle_id,
    'DORMANT',
    NOW()
FROM fhq_canonical.g4_2_composite_verdict cv
WHERE cv.g5_eligible = TRUE
  AND cv.final_classification = 'VALIDATED-CONTEXTUAL'
ON CONFLICT (needle_id) DO NOTHING;

-- ============================================================================
-- 11. GOVERNANCE REGISTRATION
-- ============================================================================

INSERT INTO fhq_meta.ios_registry (
    ios_id, title, version, description, status,
    owner_role, governing_adrs, content_hash, created_at
) VALUES (
    'G5',
    'Silent Sniper Paper Execution',
    '1.0.0',
    'Context-gated paper execution per CEO Directive WAVE 17. Implements Central Context Orchestrator with three-level failover and explicit exit criteria.',
    'ACTIVE',
    'STIG',
    ARRAY['ADR-004', 'ADR-012', 'ADR-016'],
    encode(sha256('G5-WAVE17-20251218'::bytea), 'hex'),
    NOW()
) ON CONFLICT (ios_id) DO UPDATE SET
    version = EXCLUDED.version,
    description = EXCLUDED.description,
    status = EXCLUDED.status;

-- ============================================================================
-- 12. AUDIT LOG
-- ============================================================================

INSERT INTO fhq_governance.audit_log (
    event_type, event_category, target_type, target_id,
    actor_id, actor_role, event_data, event_hash, governance_gate, adr_reference
) VALUES (
    'MIGRATION',
    'OPERATIONAL',
    'SCHEMA',
    'fhq_canonical.g5_*',
    'STIG',
    'CTO',
    jsonb_build_object(
        'directive', 'WAVE_17',
        'amendments', jsonb_build_array(
            'CCO_COHERENCE_WINDOW_300s',
            'SIGNAL_PRIORITY_QUEUE',
            'G5_EXIT_CRITERIA',
            'MAX_CONTEXT_DIMENSIONS_4',
            'CCO_THREE_LEVEL_FAILOVER'
        ),
        'locked_params_added', 10,
        'tables_created', 7
    ),
    encode(sha256(('G5-MIGRATION-' || NOW()::text)::bytea), 'hex'),
    'G4',  -- G5 not in gate_check constraint; using G4 as constitutional gate
    'ADR-004'
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_params INT;
    v_tables INT;
    v_signals INT;
BEGIN
    -- Count new parameters
    SELECT COUNT(*) INTO v_params
    FROM fhq_canonical.g4_2_parameters
    WHERE locked_by = 'CEO_DIRECTIVE_WAVE_17';

    -- Count G5 tables
    SELECT COUNT(*) INTO v_tables
    FROM information_schema.tables
    WHERE table_schema = 'fhq_canonical'
    AND table_name LIKE 'g5_%';

    -- Count initialized signal states
    SELECT COUNT(*) INTO v_signals
    FROM fhq_canonical.g5_signal_state
    WHERE current_state = 'DORMANT';

    RAISE NOTICE '';
    RAISE NOTICE '══════════════════════════════════════════════════════════════════════';
    RAISE NOTICE 'G5 SILENT SNIPER ARCHITECTURE - MIGRATION 153 COMPLETE';
    RAISE NOTICE '══════════════════════════════════════════════════════════════════════';
    RAISE NOTICE 'WAVE 17 Parameters Added:     %', v_params;
    RAISE NOTICE 'G5 Tables Created:            %', v_tables;
    RAISE NOTICE 'Signals Initialized (DORMANT): %', v_signals;
    RAISE NOTICE '══════════════════════════════════════════════════════════════════════';

    IF v_params < 10 THEN
        RAISE EXCEPTION 'Missing WAVE 17 parameters - migration incomplete';
    END IF;

    IF v_tables < 7 THEN
        RAISE EXCEPTION 'Missing G5 tables - migration incomplete';
    END IF;
END $$;
