-- ============================================================================
-- MIGRATION 094: CEIO Optimization Schema
-- ============================================================================
-- Authority: VISION-IOS CSO Directive 2025-12-08
-- Executor: STIG (CTO)
-- Reference: ADR-020 (ACI Protocol), IoS-007 (Alpha Graph)
-- Academic: IKEA (ICLR 2026), InForage (NeurIPS 2025)
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: CREATE OPTIMIZATION SCHEMA
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS fhq_optimization;

COMMENT ON SCHEMA fhq_optimization IS
'CEIO (Causal-Entropy Information Optimization) reward tracking and calibration infrastructure.
Implements IKEA knowledge boundaries, InForage information scent, and Structural Causal Entropy.
Reference: ADR-020, IoS-007 Alpha Graph';

-- ============================================================================
-- SECTION 2: CEIO HYPERPARAMETERS REGISTRY
-- ============================================================================

CREATE TABLE fhq_optimization.ceio_hyperparameters (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_name TEXT NOT NULL,
    config_version TEXT NOT NULL,
    is_active BOOLEAN DEFAULT false,

    -- IKEA Parameters (Knowledge Boundary)
    r_kb_positive NUMERIC(4,2) NOT NULL DEFAULT 0.50,  -- Reward for internal knowledge use
    r_kb_negative NUMERIC(4,2) NOT NULL DEFAULT 0.05,  -- Penalty for failed external search
    api_max INTEGER NOT NULL DEFAULT 5,                 -- Max API calls per reasoning chain

    -- InForage Parameters (Information Scent)
    alpha NUMERIC(4,2) NOT NULL DEFAULT 0.30,          -- Graph coverage weight (paper: 0.20)
    beta NUMERIC(4,2) NOT NULL DEFAULT 0.90,           -- Efficiency decay (paper: 0.95)
    t_min INTEGER NOT NULL DEFAULT 2,                   -- Minimum steps (search + answer)
    t_max INTEGER NOT NULL DEFAULT 4,                   -- Maximum reasoning steps

    -- Structural Causal Entropy Parameters
    gamma NUMERIC(4,2) NOT NULL DEFAULT 1.00,          -- Internal knowledge reward weight
    h_sc_threshold NUMERIC(4,2) NOT NULL DEFAULT 0.80, -- Entropy ceiling for regime cutoff

    -- Signal Reward Parameters
    r_signal_profit NUMERIC(4,2) NOT NULL DEFAULT 1.00,      -- Profit > threshold
    r_signal_direction NUMERIC(4,2) NOT NULL DEFAULT 0.50,   -- Direction correct, timing off
    r_signal_neutral NUMERIC(4,2) NOT NULL DEFAULT 0.00,     -- Neutral outcome
    r_signal_loss NUMERIC(4,2) NOT NULL DEFAULT -1.00,       -- Stop-loss triggered

    -- Metadata
    created_by TEXT NOT NULL,
    rationale TEXT,
    hash_chain_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_alpha CHECK (alpha >= 0 AND alpha <= 1),
    CONSTRAINT valid_beta CHECK (beta > 0 AND beta <= 1),
    CONSTRAINT valid_gamma CHECK (gamma >= 0),
    CONSTRAINT valid_h_sc CHECK (h_sc_threshold >= 0 AND h_sc_threshold <= 1)
);

-- Partial unique index to ensure only one active config
CREATE UNIQUE INDEX idx_unique_active_config ON fhq_optimization.ceio_hyperparameters (is_active) WHERE is_active = true;

-- Insert default FHQ calibration
INSERT INTO fhq_optimization.ceio_hyperparameters (
    config_name,
    config_version,
    is_active,
    r_kb_positive,
    r_kb_negative,
    api_max,
    alpha,
    beta,
    t_min,
    t_max,
    gamma,
    h_sc_threshold,
    r_signal_profit,
    r_signal_direction,
    r_signal_neutral,
    r_signal_loss,
    created_by,
    rationale,
    hash_chain_id
) VALUES (
    'FHQ_CEIO_DEFAULT',
    '2026.PROD.1',
    true,
    0.50,  -- r_kb_positive: IKEA paper uses 0.60, we use 0.50
    0.05,  -- r_kb_negative: per IKEA paper
    5,     -- api_max: FHQ limit
    0.30,  -- alpha: Higher than paper (0.20) for macro-correlation coverage
    0.90,  -- beta: Stricter than paper (0.95) - markets move fast
    2,     -- t_min: per InForage
    4,     -- t_max: FHQ limit
    1.00,  -- gamma: Full weight to internal knowledge
    0.80,  -- h_sc_threshold: Entropy ceiling for regime cutoff
    1.00,  -- r_signal_profit
    0.50,  -- r_signal_direction
    0.00,  -- r_signal_neutral
    -1.00, -- r_signal_loss (stop-loss penalty)
    'STIG',
    'Default CEIO hyperparameters per VISION-IOS CSO Directive 2025-12-08. Calibrated for FHQ market conditions: higher alpha for macro coverage, stricter beta for market speed.',
    'HC-CEIO-CALIBRATION-20251208'
);

-- ============================================================================
-- SECTION 3: ENTROPY SNAPSHOTS TABLE
-- ============================================================================

CREATE TABLE fhq_optimization.entropy_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    agent_id TEXT NOT NULL,

    -- Subgraph Definition
    query_entities TEXT[] NOT NULL,           -- Starting entities for 2-hop expansion
    focus_nodes_count INTEGER NOT NULL,       -- |N_focus|
    active_edges_count INTEGER NOT NULL,      -- Number of edges in subgraph

    -- Structural Causal Entropy Calculation
    h_sc NUMERIC(10,6) NOT NULL,              -- Computed H_sc value
    h_sc_components JSONB,                    -- Per-edge entropy contributions

    -- Interpretation
    regime_signal TEXT,                       -- 'CLEAR_TREND', 'CHOPPY', 'CHAOS'
    regime_action TEXT,                       -- 'PROCEED', 'CAUTION', 'ABORT'

    -- Metadata
    alpha_graph_version TEXT,
    calculation_timestamp TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_h_sc CHECK (h_sc >= 0),
    CONSTRAINT valid_regime_signal CHECK (regime_signal IN ('CLEAR_TREND', 'CHOPPY', 'CHAOS')),
    CONSTRAINT valid_regime_action CHECK (regime_action IN ('PROCEED', 'CAUTION', 'ABORT'))
);

CREATE INDEX idx_entropy_session ON fhq_optimization.entropy_snapshots(session_id);
CREATE INDEX idx_entropy_h_sc ON fhq_optimization.entropy_snapshots(h_sc);

-- ============================================================================
-- SECTION 4: REWARD TRACES TABLE
-- ============================================================================

CREATE TABLE fhq_optimization.reward_traces (
    trace_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    session_id UUID NOT NULL,
    timestamp_utc TIMESTAMPTZ DEFAULT NOW(),

    -- Input Context
    input_query TEXT,
    query_entities TEXT[],

    -- Execution Metrics
    retrieval_count INTEGER NOT NULL DEFAULT 0,   -- RT: API calls made
    steps_taken INTEGER NOT NULL DEFAULT 0,       -- T: reasoning steps

    -- Calculated Metrics
    structural_entropy NUMERIC(10,6),             -- H_sc
    graph_coverage_pct NUMERIC(5,4),              -- C_FHQ (0.0 - 1.0)
    outcome_signal NUMERIC(5,4),                  -- r_signal

    -- Reward Components (for debugging/analysis)
    r_outcome NUMERIC(10,6),                      -- Signal reward component
    r_scent NUMERIC(10,6),                        -- α * C_FHQ
    r_internal NUMERIC(10,6),                     -- γ * r_kb
    efficiency_factor NUMERIC(10,6),              -- β^max(0, T-2)
    r_total NUMERIC(10,6),                        -- Final CEIO reward

    -- Hyperparameters Used (for A/B testing)
    config_id UUID REFERENCES fhq_optimization.ceio_hyperparameters(config_id),
    alpha_val NUMERIC(4,2),
    beta_val NUMERIC(4,2),
    gamma_val NUMERIC(4,2),

    -- Linked Entropy Snapshot
    entropy_snapshot_id UUID REFERENCES fhq_optimization.entropy_snapshots(snapshot_id),

    -- Behavior Classification (per IKEA)
    behavior_class INTEGER,  -- 1: Perfect, 2: Failure, 3: Necessary Search, 4: Failed Search
    behavior_label TEXT,

    -- Outcome Tracking
    trade_outcome TEXT,      -- 'PROFIT', 'LOSS', 'NEUTRAL', 'PENDING'
    pnl_realized NUMERIC(18,8),

    -- Metadata
    hash_chain_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_entropy CHECK (structural_entropy >= 0),
    CONSTRAINT valid_coverage CHECK (graph_coverage_pct >= 0 AND graph_coverage_pct <= 1),
    CONSTRAINT valid_behavior CHECK (behavior_class IN (1, 2, 3, 4))
);

-- Indexes for analysis
CREATE INDEX idx_reward_efficiency ON fhq_optimization.reward_traces(steps_taken, r_total);
CREATE INDEX idx_reward_session ON fhq_optimization.reward_traces(session_id);
CREATE INDEX idx_reward_agent ON fhq_optimization.reward_traces(agent_id);
CREATE INDEX idx_reward_behavior ON fhq_optimization.reward_traces(behavior_class);
CREATE INDEX idx_reward_outcome ON fhq_optimization.reward_traces(trade_outcome);

-- ============================================================================
-- SECTION 5: CALIBRATION EXPERIMENTS TABLE
-- ============================================================================

CREATE TABLE fhq_optimization.calibration_experiments (
    experiment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_name TEXT NOT NULL,
    experiment_type TEXT NOT NULL,  -- 'ALPHA_SWEEP', 'BETA_SWEEP', 'FULL_GRID'

    -- Experiment Parameters
    asset_class TEXT NOT NULL,      -- 'FX', 'CRYPTO', 'EQUITY', 'COMMODITY'
    asset_id TEXT,
    date_range_start DATE NOT NULL,
    date_range_end DATE NOT NULL,

    -- Hyperparameter Range
    alpha_range NUMERIC[] NOT NULL,
    beta_range NUMERIC[] NOT NULL,

    -- Results
    best_alpha NUMERIC(4,2),
    best_beta NUMERIC(4,2),
    best_sharpe NUMERIC(8,4),
    best_hit_rate NUMERIC(5,4),

    -- Metadata
    executed_by TEXT NOT NULL,
    results_path TEXT,
    status TEXT DEFAULT 'PENDING',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    CONSTRAINT valid_status CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED'))
);

-- ============================================================================
-- SECTION 6: GOVERNANCE REGISTRATION
-- ============================================================================

-- Register CEIO in governance
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
    'SCHEMA_CREATION',
    'fhq_optimization',
    'SCHEMA',
    'STIG',
    NOW(),
    'APPROVED',
    'CEIO Optimization Schema created per VISION-IOS CSO Directive 2025-12-08. Implements IKEA knowledge boundaries (ICLR 2026), InForage information scent (NeurIPS 2025), and Structural Causal Entropy (FHQ definition) for autonomous research agent reward function.',
    false,
    'HC-CEIO-SCHEMA-20251208'
);

-- ============================================================================
-- SECTION 7: HELPER FUNCTIONS
-- ============================================================================

-- Function to get active hyperparameters
CREATE OR REPLACE FUNCTION fhq_optimization.get_active_config()
RETURNS fhq_optimization.ceio_hyperparameters AS $$
BEGIN
    RETURN (SELECT * FROM fhq_optimization.ceio_hyperparameters WHERE is_active = true LIMIT 1);
END;
$$ LANGUAGE plpgsql;

-- Function to classify behavior per IKEA protocol
CREATE OR REPLACE FUNCTION fhq_optimization.classify_behavior(
    p_signal_correct BOOLEAN,
    p_retrieval_count INTEGER
) RETURNS TABLE(behavior_class INTEGER, behavior_label TEXT) AS $$
BEGIN
    IF p_signal_correct AND p_retrieval_count = 0 THEN
        -- Behavior 1: Perfect Efficiency
        RETURN QUERY SELECT 1, 'PERFECT_EFFICIENCY'::TEXT;
    ELSIF NOT p_signal_correct THEN
        -- Behavior 2: Failure
        RETURN QUERY SELECT 2, 'FAILURE'::TEXT;
    ELSIF p_signal_correct AND p_retrieval_count > 0 AND p_retrieval_count <= 3 THEN
        -- Behavior 3: Necessary Search
        RETURN QUERY SELECT 3, 'NECESSARY_SEARCH'::TEXT;
    ELSE
        -- Behavior 4: Excessive Search
        RETURN QUERY SELECT 4, 'EXCESSIVE_SEARCH'::TEXT;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 8: VIEWS FOR ANALYSIS
-- ============================================================================

-- View: Reward efficiency analysis
CREATE VIEW fhq_optimization.v_reward_efficiency AS
SELECT
    agent_id,
    behavior_class,
    behavior_label,
    COUNT(*) as trace_count,
    AVG(r_total) as avg_reward,
    AVG(steps_taken) as avg_steps,
    AVG(retrieval_count) as avg_api_calls,
    AVG(graph_coverage_pct) as avg_coverage,
    AVG(structural_entropy) as avg_entropy
FROM fhq_optimization.reward_traces
GROUP BY agent_id, behavior_class, behavior_label;

-- View: Entropy regime distribution
CREATE VIEW fhq_optimization.v_entropy_regimes AS
SELECT
    DATE_TRUNC('day', calculation_timestamp) as date,
    regime_signal,
    regime_action,
    COUNT(*) as count,
    AVG(h_sc) as avg_entropy,
    MIN(h_sc) as min_entropy,
    MAX(h_sc) as max_entropy
FROM fhq_optimization.entropy_snapshots
GROUP BY DATE_TRUNC('day', calculation_timestamp), regime_signal, regime_action;

COMMIT;

-- ============================================================================
-- MIGRATION COMPLETE
-- Schema: fhq_optimization
-- Tables: ceio_hyperparameters, entropy_snapshots, reward_traces, calibration_experiments
-- Functions: get_active_config(), classify_behavior()
-- Views: v_reward_efficiency, v_entropy_regimes
-- ============================================================================
