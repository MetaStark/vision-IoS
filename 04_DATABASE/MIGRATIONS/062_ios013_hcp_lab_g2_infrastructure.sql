-- ============================================================
-- MIGRATION 062: IoS-013.HCP-LAB G2 Infrastructure
-- Live Signal Integration & End-to-End Loop Validation
-- Date: 2025-12-02
-- Author: STIG (CTO)
-- ============================================================
--
-- G2 OBJECTIVE: Connect HCP-LAB to Live Intelligence (IoS-003/007)
-- "G1 beviste at maskinen virker mekanisk. G2 skal bevise at den reagerer på stimuli."
-- ============================================================

BEGIN;

-- ============================================================
-- 1. HCP SIGNAL STATE - Live Signal Tracking
-- ============================================================
-- Tracks the current state of signals from IoS-003 and IoS-007
-- Used to detect regime changes and trigger structure generation

CREATE TABLE IF NOT EXISTS fhq_positions.hcp_signal_state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- IoS-003 Regime State
    ios003_asset_id TEXT NOT NULL,
    ios003_regime TEXT,  -- BULL, BEAR, NEUTRAL, RANGE_UP, RANGE_DOWN
    ios003_confidence NUMERIC(6,4),
    ios003_source_timestamp TIMESTAMPTZ,
    ios003_regime_changed BOOLEAN DEFAULT FALSE,
    ios003_prior_regime TEXT,

    -- IoS-007 Causal/Liquidity State
    ios007_liquidity_state TEXT,  -- EXPANDING, CONTRACTING, STABLE, NEUTRAL
    ios007_liquidity_strength NUMERIC(6,4),
    ios007_causal_signal TEXT,  -- Dominant causal relationship
    ios007_source_timestamp TIMESTAMPTZ,
    ios007_state_changed BOOLEAN DEFAULT FALSE,
    ios007_prior_state TEXT,

    -- Derived Precedence
    precedence_action TEXT,  -- From hcp_precedence_matrix
    precedence_matched BOOLEAN DEFAULT FALSE,

    -- Status
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    structure_id UUID,  -- Link to generated structure if any

    -- Governance
    hash_chain_id TEXT,
    created_by TEXT NOT NULL DEFAULT 'HCP-ENGINE'
);

COMMENT ON TABLE fhq_positions.hcp_signal_state IS
'IoS-013.HCP-LAB G2: Live signal state tracking for automated structure generation.';

CREATE INDEX idx_hcp_signal_state_captured ON fhq_positions.hcp_signal_state(captured_at DESC);
CREATE INDEX idx_hcp_signal_state_asset ON fhq_positions.hcp_signal_state(ios003_asset_id);
CREATE INDEX idx_hcp_signal_state_unprocessed ON fhq_positions.hcp_signal_state(processed) WHERE NOT processed;

-- ============================================================
-- 2. HCP EXECUTION LOG - Trade Execution Tracking
-- ============================================================
-- Tracks all execution attempts against Alpaca Paper

CREATE TABLE IF NOT EXISTS fhq_positions.hcp_execution_log (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Source
    structure_id UUID NOT NULL REFERENCES fhq_positions.structure_plan_hcp(structure_id),
    signal_state_id UUID REFERENCES fhq_positions.hcp_signal_state(state_id),

    -- Execution Details
    broker TEXT NOT NULL DEFAULT 'ALPACA_PAPER',
    order_type TEXT NOT NULL,  -- MARKET, LIMIT, etc.
    execution_mode TEXT NOT NULL DEFAULT 'G2_VALIDATION',

    -- Legs Submitted (JSONB array)
    legs_submitted JSONB NOT NULL,

    -- Alpaca Response
    alpaca_order_ids JSONB,  -- Array of order IDs from Alpaca
    alpaca_response JSONB,   -- Raw response
    execution_status TEXT NOT NULL,  -- SUBMITTED, FILLED, REJECTED, PARTIAL, ERROR
    error_message TEXT,

    -- Accounting
    total_premium_expected NUMERIC(12,2),
    total_premium_actual NUMERIC(12,2),
    total_commission NUMERIC(10,2) DEFAULT 0,

    -- Timing
    submission_latency_ms INTEGER,
    fill_latency_ms INTEGER,

    -- Governance
    hash_chain_id TEXT,
    created_by TEXT NOT NULL DEFAULT 'HCP-ENGINE'
);

COMMENT ON TABLE fhq_positions.hcp_execution_log IS
'IoS-013.HCP-LAB G2: Alpaca Paper execution log for all HCP trades.';

-- ============================================================
-- 3. HCP LOOP RUNS - Loop Iteration Tracking
-- ============================================================
-- Tracks each 15-minute loop iteration for audit

CREATE TABLE IF NOT EXISTS fhq_positions.hcp_loop_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Mode
    execution_mode TEXT NOT NULL DEFAULT 'G2_VALIDATION',
    target_asset TEXT NOT NULL,

    -- Signal Capture
    signals_captured INTEGER DEFAULT 0,
    regime_changes_detected INTEGER DEFAULT 0,
    liquidity_changes_detected INTEGER DEFAULT 0,

    -- Structure Generation
    structures_generated INTEGER DEFAULT 0,
    structures_approved INTEGER DEFAULT 0,
    structures_rejected INTEGER DEFAULT 0,

    -- Execution
    orders_submitted INTEGER DEFAULT 0,
    orders_filled INTEGER DEFAULT 0,
    orders_failed INTEGER DEFAULT 0,

    -- NAV Impact
    nav_before NUMERIC(18,2),
    nav_after NUMERIC(18,2),
    nav_delta NUMERIC(18,2),

    -- Status
    run_status TEXT NOT NULL DEFAULT 'RUNNING',  -- RUNNING, COMPLETED, FAILED, SKIPPED
    error_message TEXT,

    -- Safety Checks
    stale_data_blocked BOOLEAN DEFAULT FALSE,
    rate_limit_blocked BOOLEAN DEFAULT FALSE,
    orders_this_hour INTEGER DEFAULT 0,

    -- Hash Chain
    hash_chain_id TEXT,
    created_by TEXT NOT NULL DEFAULT 'HCP-ENGINE'
);

COMMENT ON TABLE fhq_positions.hcp_loop_runs IS
'IoS-013.HCP-LAB G2: 15-minute loop iteration tracking for audit.';

CREATE INDEX idx_hcp_loop_runs_started ON fhq_positions.hcp_loop_runs(started_at DESC);

-- ============================================================
-- 4. HCP ENGINE CONFIG - Runtime Configuration
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_positions.hcp_engine_config (
    config_key TEXT PRIMARY KEY,
    config_value TEXT NOT NULL,
    config_type TEXT NOT NULL DEFAULT 'STRING',  -- STRING, INTEGER, BOOLEAN, JSON
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by TEXT DEFAULT 'STIG'
);

-- Insert G2 configuration
INSERT INTO fhq_positions.hcp_engine_config (config_key, config_value, config_type, description) VALUES
    ('execution_mode', 'G2_VALIDATION', 'STRING', 'Current execution mode'),
    ('target_asset', 'BITO', 'STRING', 'Primary target asset for options'),
    ('loop_interval_minutes', '15', 'INTEGER', 'Loop frequency in minutes'),
    ('max_orders_per_hour', '10', 'INTEGER', 'ADR-012 rate limit'),
    ('stale_data_threshold_seconds', '60', 'INTEGER', 'Max age for market data'),
    ('deepseek_enabled', 'true', 'BOOLEAN', 'RiskEnvelope generation active'),
    ('paper_trading_only', 'true', 'BOOLEAN', 'Safety: Paper mode enforced'),
    ('synthetic_nav_target', 'synthetic_lab_nav', 'STRING', 'NAV table to update'),
    ('g2_validation_active', 'true', 'BOOLEAN', 'G2 validation mode active')
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    updated_at = NOW();

COMMENT ON TABLE fhq_positions.hcp_engine_config IS
'IoS-013.HCP-LAB G2: Runtime configuration for HCPExecutionEngine.';

-- ============================================================
-- 5. EXTEND PRECEDENCE MATRIX FOR LIQUIDITY STATES
-- ============================================================
-- Add STABLE and NEUTRAL liquidity states for completeness

INSERT INTO fhq_positions.hcp_precedence_matrix
    (ios003_price_regime, ios007_liquidity_state, recommended_action, rationale, convexity_bias)
VALUES
    ('BULL', 'STABLE', 'LONG_CALL', 'Stable liquidity supports trend continuation', 'LONG_GAMMA'),
    ('BULL', 'NEUTRAL', 'LONG_CALL', 'Neutral liquidity - default to regime bias', 'LONG_GAMMA'),
    ('BEAR', 'STABLE', 'LONG_PUT', 'Stable liquidity supports trend continuation', 'LONG_GAMMA'),
    ('BEAR', 'NEUTRAL', 'LONG_PUT', 'Neutral liquidity - default to regime bias', 'LONG_GAMMA'),
    ('NEUTRAL', 'EXPANDING', 'STRADDLE', 'Neutral regime + expanding liquidity = breakout expected', 'LONG_GAMMA'),
    ('NEUTRAL', 'CONTRACTING', 'IRON_CONDOR', 'Neutral regime + contracting liquidity = range-bound', 'SHORT_GAMMA'),
    ('NEUTRAL', 'STABLE', 'NO_TRADE', 'Neutral regime + stable liquidity = no edge', 'NEUTRAL'),
    ('NEUTRAL', 'NEUTRAL', 'NO_TRADE', 'No clear signal - wait', 'NEUTRAL'),
    ('RANGE_UP', 'EXPANDING', 'CALL_SPREAD', 'Range-up + fuel = breakout probability', 'LONG_GAMMA'),
    ('RANGE_UP', 'CONTRACTING', 'IRON_CONDOR', 'Range-up + contracting = fade the move', 'SHORT_GAMMA'),
    ('RANGE_DOWN', 'EXPANDING', 'PUT_SPREAD', 'Range-down + fuel = breakdown probability', 'LONG_GAMMA'),
    ('RANGE_DOWN', 'CONTRACTING', 'IRON_CONDOR', 'Range-down + contracting = fade the move', 'SHORT_GAMMA')
ON CONFLICT (ios003_price_regime, ios007_liquidity_state) DO NOTHING;

-- ============================================================
-- 6. LIQUIDITY STATE DERIVATION VIEW
-- ============================================================
-- Derives liquidity state from IoS-007 edge data

CREATE OR REPLACE VIEW fhq_positions.v_hcp_liquidity_state AS
SELECT
    e.to_node_id as asset_node,
    CASE
        WHEN e.strength > 0.6 THEN 'EXPANDING'
        WHEN e.strength < 0.4 THEN 'CONTRACTING'
        WHEN e.strength BETWEEN 0.45 AND 0.55 THEN 'STABLE'
        ELSE 'NEUTRAL'
    END as liquidity_state,
    e.strength as liquidity_strength,
    e.confidence,
    e.updated_at as source_timestamp
FROM fhq_graph.edges e
WHERE e.from_node_id = 'NODE_LIQUIDITY'
AND e.status = 'HYPOTHESIZED'
ORDER BY e.updated_at DESC;

-- ============================================================
-- 7. COMBINED SIGNAL VIEW
-- ============================================================
-- Combines IoS-003 regime with IoS-007 liquidity for decision-making

CREATE OR REPLACE VIEW fhq_positions.v_hcp_combined_signals AS
SELECT
    r.asset_id,
    r.timestamp as regime_date,
    r.regime_label as ios003_regime,
    r.confidence_score as ios003_confidence,
    COALESCE(l.liquidity_state, 'NEUTRAL') as ios007_liquidity_state,
    COALESCE(l.liquidity_strength, 0.5) as ios007_liquidity_strength,
    p.recommended_action,
    p.convexity_bias,
    r.created_at as regime_updated,
    l.source_timestamp as liquidity_updated,
    GREATEST(r.created_at, COALESCE(l.source_timestamp, r.created_at)) as latest_signal
FROM fhq_research.regime_predictions_v2 r
LEFT JOIN fhq_positions.v_hcp_liquidity_state l
    ON l.asset_node = 'STATE_' || UPPER(REPLACE(r.asset_id, '-', '_'))
LEFT JOIN fhq_positions.hcp_precedence_matrix p
    ON p.ios003_price_regime = r.regime_label
    AND p.ios007_liquidity_state = COALESCE(l.liquidity_state, 'NEUTRAL')
WHERE r.timestamp = (SELECT MAX(timestamp) FROM fhq_research.regime_predictions_v2 r2 WHERE r2.asset_id = r.asset_id)
ORDER BY r.asset_id;

-- ============================================================
-- 8. LOG G2 INITIATION
-- ============================================================

INSERT INTO fhq_governance.governance_actions_log
(action_id, action_type, action_target, action_target_type,
 initiated_by, initiated_at, decision, decision_rationale,
 vega_reviewed, hash_chain_id)
VALUES (
    gen_random_uuid(),
    'G2_INITIATION',
    'IoS-013.HCP-LAB',
    'IOS_MODULE',
    'CEO',
    NOW(),
    'APPROVED',
    'G2 Initiation Charter executed. Live signal integration infrastructure deployed. Target: BITO. Mode: G2_VALIDATION.',
    false,
    'HC-HCP-LAB-G2-INIT-20251201'
);

-- ============================================================
-- 9. UPDATE IoS REGISTRY
-- ============================================================

UPDATE fhq_meta.ios_registry
SET
    description = 'G2 INITIATED. Live Signal Integration phase. Connecting to IoS-003/007 for automated structure generation. Target: BITO. Mode: G2_VALIDATION. ADR-012 Capital Preservation SUSPENDED.',
    governance_state = 'G2_INITIATED',
    updated_at = NOW()
WHERE ios_id = 'IoS-013.HCP-LAB';

COMMIT;

-- ============================================================
-- VERIFICATION
-- ============================================================
SELECT 'G2 Infrastructure Created' as status;
SELECT config_key, config_value FROM fhq_positions.hcp_engine_config ORDER BY config_key;
SELECT * FROM fhq_positions.v_hcp_combined_signals WHERE asset_id = 'BTC-USD';
