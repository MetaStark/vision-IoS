-- ============================================================================
-- MIGRATION 100: CEIO Phase 2 — Feedback Loop Closure
-- ============================================================================
-- Authority: CEO DIRECTIVE EC-005 PHASE 2
-- Executor: STIG (CTO)
-- Date: 2025-12-09
-- Purpose: Close the CEIO learning loop, activate InForage cost control,
--          and seed Alpha Graph entropy data
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: KNOWLEDGE FRAGMENTS TABLE (Winning Patterns Storage)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_memory.knowledge_fragments (
    fragment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source Linkage
    source_trace_id UUID REFERENCES fhq_optimization.reward_traces(trace_id),
    source_shadow_id UUID,  -- Links to shadow_ledger.ledger_id
    source_episode_id UUID REFERENCES fhq_memory.episodic_memory(episode_id),

    -- Fragment Content
    fragment_type TEXT NOT NULL,  -- 'WINNING_PATTERN', 'LOSS_PATTERN', 'CAUSAL_INSIGHT'
    reasoning_chain TEXT,         -- The full reasoning that led to outcome
    hypothesis TEXT,              -- The original hypothesis
    asset_id TEXT,
    direction TEXT,

    -- Outcome Data
    pnl_realized NUMERIC(18,8),
    return_pct NUMERIC(8,6),
    was_profitable BOOLEAN,

    -- Validity & Learning
    validity_score NUMERIC(5,4) DEFAULT 0.5,  -- 0.0-1.0, updated by learning
    reinforcement_count INTEGER DEFAULT 1,    -- Times this pattern succeeded
    decay_rate NUMERIC(5,4) DEFAULT 0.01,     -- How fast validity decays

    -- Context
    regime_context TEXT,
    entropy_at_signal NUMERIC(10,6),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,

    CONSTRAINT valid_fragment_type CHECK (
        fragment_type IN ('WINNING_PATTERN', 'LOSS_PATTERN', 'CAUSAL_INSIGHT', 'NEUTRAL_OBSERVATION')
    )
);

CREATE INDEX IF NOT EXISTS idx_knowledge_winning ON fhq_memory.knowledge_fragments(was_profitable) WHERE was_profitable = true;
CREATE INDEX IF NOT EXISTS idx_knowledge_validity ON fhq_memory.knowledge_fragments(validity_score DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_asset ON fhq_memory.knowledge_fragments(asset_id);

-- ============================================================================
-- SECTION 2: INFORAGE COST TRACKING TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_optimization.inforage_cost_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,

    -- Cost Tracking
    step_number INTEGER NOT NULL,
    step_type TEXT NOT NULL,      -- 'API_CALL', 'DB_QUERY', 'LLM_INFERENCE'
    step_cost NUMERIC(10,6) NOT NULL,
    cumulative_cost NUMERIC(10,6) NOT NULL,

    -- Information Gain Prediction
    predicted_gain NUMERIC(10,6),
    actual_gain NUMERIC(10,6),    -- Populated after outcome known
    roi_ratio NUMERIC(10,6),      -- actual_gain / cumulative_cost

    -- Decision
    decision TEXT,                -- 'CONTINUE', 'ABORT_LOW_ROI', 'ABORT_BUDGET'
    abort_reason TEXT,

    -- Metadata
    timestamp_utc TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_decision CHECK (
        decision IN ('CONTINUE', 'ABORT_LOW_ROI', 'ABORT_BUDGET', 'COMPLETED')
    )
);

CREATE INDEX IF NOT EXISTS idx_inforage_session ON fhq_optimization.inforage_cost_log(session_id);
CREATE INDEX IF NOT EXISTS idx_inforage_aborts ON fhq_optimization.inforage_cost_log(decision) WHERE decision LIKE 'ABORT%';

-- ============================================================================
-- SECTION 3: INFORAGE BUDGET CONFIGURATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_optimization.inforage_budget_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    is_active BOOLEAN DEFAULT false,

    -- Cost Parameters (per CEO Directive: aggressive)
    step_cost_api NUMERIC(10,6) NOT NULL DEFAULT 0.05,      -- $0.05 per API call
    step_cost_llm NUMERIC(10,6) NOT NULL DEFAULT 0.02,      -- $0.02 per LLM inference
    step_cost_db NUMERIC(10,6) NOT NULL DEFAULT 0.001,      -- $0.001 per DB query

    -- Budget Limits
    session_budget_max NUMERIC(10,6) NOT NULL DEFAULT 0.50, -- $0.50 max per session
    daily_budget_max NUMERIC(10,6) NOT NULL DEFAULT 50.00,  -- $50 daily limit

    -- Abort Thresholds
    min_roi_threshold NUMERIC(5,4) NOT NULL DEFAULT 1.20,   -- Abort if predicted ROI < 1.2x
    gain_decay_per_step NUMERIC(5,4) NOT NULL DEFAULT 0.15, -- Info gain decays 15% per step

    -- Metadata
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure only one active config
CREATE UNIQUE INDEX IF NOT EXISTS idx_inforage_active ON fhq_optimization.inforage_budget_config(is_active) WHERE is_active = true;

-- Insert aggressive default config per CEO Directive
INSERT INTO fhq_optimization.inforage_budget_config (
    is_active,
    step_cost_api,
    step_cost_llm,
    step_cost_db,
    session_budget_max,
    daily_budget_max,
    min_roi_threshold,
    gain_decay_per_step,
    created_by
) VALUES (
    true,
    0.05,   -- $0.05 per API call (aggressive per CEO)
    0.02,   -- $0.02 per LLM call
    0.001,  -- $0.001 per DB query
    0.50,   -- $0.50 session max
    50.00,  -- $50 daily max
    1.20,   -- Must predict 1.2x ROI to continue
    0.15,   -- 15% decay per step
    'STIG'
)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- SECTION 4: POST-TRADE FEEDBACK TRIGGER FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_optimization.fn_shadow_trade_feedback()
RETURNS TRIGGER AS $$
DECLARE
    v_episode_id UUID;
    v_fragment_id UUID;
    v_regime TEXT;
    v_reasoning TEXT;
    v_entropy NUMERIC;
    v_is_profitable BOOLEAN;
    v_validity NUMERIC;
BEGIN
    -- Only fire when status changes to CLOSED
    IF NEW.status = 'CLOSED' AND (OLD.status IS NULL OR OLD.status != 'CLOSED') THEN

        -- Get regime from current state
        SELECT COALESCE(current_regime, 'UNKNOWN') INTO v_regime
        FROM fhq_meta.regime_state LIMIT 1;

        -- Get reasoning chain from reward trace
        SELECT rt.input_query, es.h_sc
        INTO v_reasoning, v_entropy
        FROM fhq_optimization.reward_traces rt
        LEFT JOIN fhq_optimization.entropy_snapshots es ON es.snapshot_id = rt.entropy_snapshot_id
        WHERE rt.trace_id = NEW.ceio_trace_id;

        -- Determine if profitable
        v_is_profitable := COALESCE(NEW.shadow_pnl, 0) > 0;

        -- Calculate validity score based on outcome
        IF v_is_profitable THEN
            v_validity := LEAST(0.95, 0.70 + (NEW.shadow_return_pct * 2));  -- Higher validity for winners
        ELSE
            v_validity := GREATEST(0.10, 0.30 + (NEW.shadow_return_pct * 2));  -- Lower for losers
        END IF;

        -- STEP 1: Create Episodic Memory Entry
        INSERT INTO fhq_memory.episodic_memory (
            episode_type,
            episode_title,
            episode_description,
            started_at,
            ended_at,
            duration_seconds,
            regime_at_start,
            regime_at_end,
            agents_involved,
            primary_agent,
            outcome_type,
            outcome_value,
            outcome_metadata,
            importance_score,
            is_landmark
        ) VALUES (
            'SHADOW_TRADE',
            'CEIO Shadow: ' || NEW.asset_id || ' ' || NEW.direction,
            'Shadow trade ' || NEW.direction || ' ' || NEW.asset_id ||
            ' Entry: ' || NEW.shadow_entry_price ||
            ' Exit: ' || NEW.shadow_exit_price ||
            ' PnL: ' || COALESCE(NEW.shadow_pnl::text, 'N/A') ||
            ' Reason: ' || COALESCE(NEW.exit_reason, 'UNKNOWN'),
            NEW.shadow_entry_time,
            NEW.shadow_exit_time,
            EXTRACT(EPOCH FROM (NEW.shadow_exit_time - NEW.shadow_entry_time))::INTEGER,
            v_regime,
            v_regime,
            ARRAY['CEIO', 'LINE'],
            'CEIO',
            CASE WHEN v_is_profitable THEN 'PROFIT' ELSE 'LOSS' END,
            NEW.shadow_pnl,
            jsonb_build_object(
                'ledger_id', NEW.ledger_id,
                'trace_id', NEW.ceio_trace_id,
                'return_pct', NEW.shadow_return_pct,
                'exit_reason', NEW.exit_reason,
                'entropy_at_signal', v_entropy
            ),
            CASE WHEN v_is_profitable THEN 0.80 ELSE 0.60 END,  -- Higher importance for profits
            v_is_profitable AND ABS(COALESCE(NEW.shadow_return_pct, 0)) > 0.02  -- Landmark if > 2% win
        )
        RETURNING episode_id INTO v_episode_id;

        -- STEP 2: Create Knowledge Fragment (especially for winners)
        INSERT INTO fhq_memory.knowledge_fragments (
            source_trace_id,
            source_shadow_id,
            source_episode_id,
            fragment_type,
            reasoning_chain,
            hypothesis,
            asset_id,
            direction,
            pnl_realized,
            return_pct,
            was_profitable,
            validity_score,
            regime_context,
            entropy_at_signal
        ) VALUES (
            NEW.ceio_trace_id,
            NEW.ledger_id,
            v_episode_id,
            CASE WHEN v_is_profitable THEN 'WINNING_PATTERN' ELSE 'LOSS_PATTERN' END,
            v_reasoning,
            NEW.hypothesis_type || ': ' || NEW.direction || ' ' || NEW.asset_id,
            NEW.asset_id,
            NEW.direction,
            NEW.shadow_pnl,
            NEW.shadow_return_pct,
            v_is_profitable,
            v_validity,
            v_regime,
            v_entropy
        )
        RETURNING fragment_id INTO v_fragment_id;

        -- STEP 3: Update reward_trace with outcome
        UPDATE fhq_optimization.reward_traces
        SET trade_outcome = CASE WHEN v_is_profitable THEN 'PROFIT' ELSE 'LOSS' END,
            pnl_realized = NEW.shadow_pnl
        WHERE trace_id = NEW.ceio_trace_id;

        -- STEP 4: Log the feedback event
        INSERT INTO fhq_governance.governance_actions_log (
            action_id,
            action_type,
            action_target,
            action_target_type,
            initiated_by,
            initiated_at,
            decision,
            decision_rationale,
            vega_reviewed,
            hash_chain_id
        ) VALUES (
            gen_random_uuid(),
            'CEIO_FEEDBACK_LOOP',
            NEW.ledger_id::text,
            'SHADOW_TRADE',
            'STIG_TRIGGER',
            NOW(),
            CASE WHEN v_is_profitable THEN 'POSITIVE_REINFORCEMENT' ELSE 'NEGATIVE_REINFORCEMENT' END,
            'Shadow trade closed. PnL=' || COALESCE(NEW.shadow_pnl::text, '0') ||
            '. Episode=' || v_episode_id::text ||
            '. Fragment=' || v_fragment_id::text ||
            '. Validity=' || v_validity::text,
            false,
            'HC-CEIO-FEEDBACK-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
        );

        RAISE NOTICE 'CEIO FEEDBACK LOOP: Shadow % closed. PnL=%. Episode=%. Fragment=%. Validity=%',
            NEW.ledger_id, NEW.shadow_pnl, v_episode_id, v_fragment_id, v_validity;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 5: ATTACH TRIGGER TO SHADOW_LEDGER
-- ============================================================================

DROP TRIGGER IF EXISTS trg_shadow_trade_feedback ON fhq_optimization.shadow_ledger;

CREATE TRIGGER trg_shadow_trade_feedback
    AFTER UPDATE ON fhq_optimization.shadow_ledger
    FOR EACH ROW
    EXECUTE FUNCTION fhq_optimization.fn_shadow_trade_feedback();

-- ============================================================================
-- SECTION 6: INFORAGE COST CHECK FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_optimization.fn_inforage_cost_check(
    p_session_id UUID,
    p_step_type TEXT,
    p_predicted_gain NUMERIC DEFAULT NULL
)
RETURNS TABLE(
    decision TEXT,
    cumulative_cost NUMERIC,
    predicted_roi NUMERIC,
    abort_reason TEXT
) AS $$
DECLARE
    v_config RECORD;
    v_step_cost NUMERIC;
    v_current_cost NUMERIC;
    v_new_cumulative NUMERIC;
    v_predicted_gain NUMERIC;
    v_roi NUMERIC;
    v_decision TEXT;
    v_abort_reason TEXT;
BEGIN
    -- Get active config
    SELECT * INTO v_config
    FROM fhq_optimization.inforage_budget_config
    WHERE is_active = true
    LIMIT 1;

    IF v_config IS NULL THEN
        -- No config, allow everything
        RETURN QUERY SELECT 'CONTINUE'::TEXT, 0::NUMERIC, 999::NUMERIC, NULL::TEXT;
        RETURN;
    END IF;

    -- Determine step cost
    v_step_cost := CASE p_step_type
        WHEN 'API_CALL' THEN v_config.step_cost_api
        WHEN 'LLM_INFERENCE' THEN v_config.step_cost_llm
        WHEN 'DB_QUERY' THEN v_config.step_cost_db
        ELSE v_config.step_cost_api  -- Default to API cost
    END;

    -- Get current cumulative cost for session
    SELECT COALESCE(MAX(cumulative_cost), 0) INTO v_current_cost
    FROM fhq_optimization.inforage_cost_log
    WHERE session_id = p_session_id;

    v_new_cumulative := v_current_cost + v_step_cost;

    -- Check budget limit
    IF v_new_cumulative > v_config.session_budget_max THEN
        v_decision := 'ABORT_BUDGET';
        v_abort_reason := 'Session budget exceeded: $' || v_new_cumulative::text || ' > $' || v_config.session_budget_max::text;
    ELSE
        -- Calculate predicted gain with decay
        -- Each step reduces expected gain by decay_rate
        v_predicted_gain := COALESCE(p_predicted_gain, 1.0) *
            POWER(1 - v_config.gain_decay_per_step,
                  (SELECT COUNT(*) FROM fhq_optimization.inforage_cost_log WHERE session_id = p_session_id));

        v_roi := v_predicted_gain / NULLIF(v_new_cumulative, 0);

        -- Check ROI threshold
        IF v_roi < v_config.min_roi_threshold THEN
            v_decision := 'ABORT_LOW_ROI';
            v_abort_reason := 'Economic Stop: ROI=' || ROUND(v_roi, 2)::text || ' < threshold=' || v_config.min_roi_threshold::text;
        ELSE
            v_decision := 'CONTINUE';
            v_abort_reason := NULL;
        END IF;
    END IF;

    -- Log the decision
    INSERT INTO fhq_optimization.inforage_cost_log (
        session_id,
        step_number,
        step_type,
        step_cost,
        cumulative_cost,
        predicted_gain,
        decision,
        abort_reason
    ) VALUES (
        p_session_id,
        (SELECT COALESCE(MAX(step_number), 0) + 1 FROM fhq_optimization.inforage_cost_log WHERE session_id = p_session_id),
        p_step_type,
        v_step_cost,
        v_new_cumulative,
        v_predicted_gain,
        v_decision,
        v_abort_reason
    );

    RETURN QUERY SELECT v_decision, v_new_cumulative, v_roi, v_abort_reason;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 7: ALPHA GRAPH SEED DATA (Top 10 Assets vs Macro Drivers)
-- ============================================================================

-- First ensure table exists
CREATE TABLE IF NOT EXISTS vision_signals.alpha_graph_edges (
    edge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node TEXT NOT NULL,
    target_node TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    confidence NUMERIC(5,4) DEFAULT 0.5,
    causal_weight NUMERIC(5,4) DEFAULT 0.5,
    is_active BOOLEAN DEFAULT true,
    evidence_count INTEGER DEFAULT 1,
    last_validated TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_edge_type CHECK (
        edge_type IN ('LEADS', 'CAUSES', 'CORRELATES', 'INVERSE', 'LAGS', 'UNKNOWN')
    )
);

CREATE TABLE IF NOT EXISTS vision_signals.alpha_graph_nodes (
    node_id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,  -- 'ASSET', 'MACRO', 'INDICATOR', 'REGIME'
    display_name TEXT,
    data_source TEXT,
    is_active BOOLEAN DEFAULT true,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert Core Nodes (Assets + Macro Drivers)
INSERT INTO vision_signals.alpha_graph_nodes (node_id, node_type, display_name, data_source) VALUES
    -- Top 10 Assets
    ('BTC-USD', 'ASSET', 'Bitcoin', 'alpaca'),
    ('ETH-USD', 'ASSET', 'Ethereum', 'alpaca'),
    ('SOL-USD', 'ASSET', 'Solana', 'alpaca'),
    ('SPY', 'ASSET', 'S&P 500 ETF', 'alpaca'),
    ('QQQ', 'ASSET', 'Nasdaq 100 ETF', 'alpaca'),
    ('NVDA', 'ASSET', 'NVIDIA', 'alpaca'),
    ('AAPL', 'ASSET', 'Apple', 'alpaca'),
    ('MSFT', 'ASSET', 'Microsoft', 'alpaca'),
    ('GLD', 'ASSET', 'Gold ETF', 'alpaca'),
    ('TLT', 'ASSET', 'Treasury Bond ETF', 'alpaca'),
    -- Macro Drivers
    ('DXY', 'MACRO', 'US Dollar Index', 'fred'),
    ('FED_FUNDS', 'MACRO', 'Fed Funds Rate', 'fred'),
    ('CPI_YOY', 'MACRO', 'CPI Year-over-Year', 'fred'),
    ('VIX', 'MACRO', 'Volatility Index', 'alpaca'),
    ('US10Y', 'MACRO', '10-Year Treasury Yield', 'fred'),
    ('M2_SUPPLY', 'MACRO', 'M2 Money Supply', 'fred')
ON CONFLICT (node_id) DO UPDATE SET updated_at = NOW();

-- Insert Causal Edges (Based on established macro relationships)
INSERT INTO vision_signals.alpha_graph_edges (source_node, target_node, edge_type, confidence, causal_weight) VALUES
    -- Rate sensitivity
    ('FED_FUNDS', 'BTC-USD', 'INVERSE', 0.75, 0.8),
    ('FED_FUNDS', 'QQQ', 'INVERSE', 0.80, 0.9),
    ('FED_FUNDS', 'TLT', 'INVERSE', 0.90, 1.0),
    ('US10Y', 'NVDA', 'INVERSE', 0.70, 0.7),
    ('US10Y', 'GLD', 'INVERSE', 0.65, 0.6),

    -- Dollar correlations
    ('DXY', 'BTC-USD', 'INVERSE', 0.70, 0.7),
    ('DXY', 'GLD', 'INVERSE', 0.80, 0.9),
    ('DXY', 'ETH-USD', 'INVERSE', 0.65, 0.6),

    -- Inflation dynamics
    ('CPI_YOY', 'GLD', 'CORRELATES', 0.75, 0.8),
    ('CPI_YOY', 'BTC-USD', 'CORRELATES', 0.60, 0.5),
    ('CPI_YOY', 'TLT', 'INVERSE', 0.70, 0.7),

    -- Liquidity
    ('M2_SUPPLY', 'BTC-USD', 'LEADS', 0.80, 1.0),
    ('M2_SUPPLY', 'SPY', 'LEADS', 0.75, 0.9),
    ('M2_SUPPLY', 'QQQ', 'LEADS', 0.78, 0.9),

    -- Risk sentiment
    ('VIX', 'SPY', 'INVERSE', 0.85, 1.0),
    ('VIX', 'QQQ', 'INVERSE', 0.88, 1.0),
    ('VIX', 'BTC-USD', 'INVERSE', 0.60, 0.6),
    ('VIX', 'GLD', 'CORRELATES', 0.55, 0.5),

    -- Tech correlation cluster
    ('NVDA', 'QQQ', 'CORRELATES', 0.90, 0.8),
    ('AAPL', 'QQQ', 'CORRELATES', 0.85, 0.7),
    ('MSFT', 'QQQ', 'CORRELATES', 0.88, 0.8),
    ('SPY', 'QQQ', 'CORRELATES', 0.92, 0.9),

    -- Crypto cluster
    ('BTC-USD', 'ETH-USD', 'LEADS', 0.85, 0.9),
    ('BTC-USD', 'SOL-USD', 'LEADS', 0.80, 0.8),
    ('ETH-USD', 'SOL-USD', 'CORRELATES', 0.75, 0.7),

    -- Safe haven dynamics
    ('SPY', 'GLD', 'INVERSE', 0.45, 0.4),
    ('SPY', 'TLT', 'INVERSE', 0.50, 0.5)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- SECTION 8: GOVERNANCE LOG
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
    vega_reviewed,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'CEIO_PHASE2_ACTIVATION',
    'CEIO_ENGINE',
    'SYSTEM',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO DIRECTIVE EC-005 PHASE 2 executed. (1) Post-trade feedback trigger ACTIVE on shadow_ledger. (2) InForage cost-abort function ACTIVE with $0.05/API step_cost. (3) Alpha Graph seeded with 27 edges across 16 nodes. Learning loop CLOSED.',
    false,
    'HC-CEIO-PHASE2-' || TO_CHAR(NOW(), 'YYYYMMDD')
);

COMMIT;

-- ============================================================================
-- MIGRATION COMPLETE
-- Tables: knowledge_fragments, inforage_cost_log, inforage_budget_config
-- Trigger: trg_shadow_trade_feedback on shadow_ledger
-- Function: fn_inforage_cost_check() for economic stops
-- Data: 16 Alpha Graph nodes, 27 causal edges
-- ============================================================================
