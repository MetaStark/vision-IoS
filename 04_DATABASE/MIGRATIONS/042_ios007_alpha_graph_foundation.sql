-- ============================================================================
-- MIGRATION: 042_ios007_alpha_graph_foundation.sql
-- PURPOSE: IoS-007 Alpha Graph Engine — Causal Reasoning Core (G0 Foundation)
-- AUTHORITY: FINN (Tier-1 Research) — Owner
-- VALIDATOR: IoS-005 (Causal Audit) — CONSTITUTIONAL
-- GOVERNANCE: VEGA (Tier-1 Compliance)
-- TECHNICAL: STIG (CTO)
-- EXECUTION: CODE (EC-011)
-- ADR COMPLIANCE: ADR-002, ADR-003, ADR-011, ADR-013, ADR-054
-- STATUS: G0 SUBMISSION
-- DATE: 2025-11-30
-- ============================================================================
--
-- STRATEGIC MISSION:
-- "From Correlation to Causality."
--
-- IoS-007 transforms FjordHQ from a reactive system to a reasoning system.
-- The Alpha Graph models the Transmission Mechanism of the market.
--
-- COMPATIBILITY: Aligned with alpha_graph Python package (v1.0.0)
-- Field names match Pydantic models in alpha_graph/models.py
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: CREATE fhq_graph SCHEMA
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS fhq_graph;

COMMENT ON SCHEMA fhq_graph IS
'IoS-007 Alpha Graph Engine — Causal Reasoning Core.
Persistence layer for alpha_graph Python package.
Houses nodes, edges, snapshots, deltas, and inference_log.
Owner: FINN | Validator: IoS-005 | Governance: VEGA';

-- ============================================================================
-- SECTION 2: NODE TYPE ENUM
-- ============================================================================
-- Combined node types from alpha_graph v1.0 + IoS-007 spec

CREATE TYPE fhq_graph.node_type AS ENUM (
    -- From alpha_graph v1.0 (Python package)
    'MACRO',        -- DXY, VIX, rates, CPI, M2, real rates
    'ONCHAIN',      -- Whale flow, NVT, miner activity
    'DERIV',        -- Funding, OI, skew, basis
    'TECH',         -- Technical indicators
    'REGIME',       -- HMM states, vol regimes
    'SENTIMENT',    -- Twitter, Reddit, news
    'STRATEGY',     -- Alpha Lab strategy outputs
    'PORTFOLIO',    -- Portfolio-level metrics
    -- From IoS-007 spec (causal extensions)
    'ASSET',        -- IoS-001 price/volatility nodes
    'FUTURE',       -- Reserved for IoS-009
    'OTHER'
);

-- ============================================================================
-- SECTION 3: EDGE TYPE ENUM
-- ============================================================================
-- Combined edge types from alpha_graph v1.0 + IoS-007 spec

CREATE TYPE fhq_graph.relationship_type AS ENUM (
    -- From alpha_graph v1.0 (Python package)
    'CORRELATION',       -- Statistical correlation
    'CAUSALITY',         -- Inferred causal relationship
    'LEAD_LAG',          -- Time-lagged relationship
    'REGIME_CONDITIONAL', -- Only exists in certain regimes
    -- From IoS-007 spec (causal extensions)
    'LEADS',             -- A → B: Temporal precedence
    'INHIBITS',          -- A ⊣ B: Inverse pressure / Dampening
    'AMPLIFIES',         -- A ⇒ B: Regime reinforcement
    'COUPLES',           -- A ↔ B: Sympathetic movement
    'BREAKS'             -- A ↛ B: Decoupling event
);

CREATE TYPE fhq_graph.edge_direction AS ENUM (
    'UNI',  -- Unidirectional
    'BI'    -- Bidirectional
);

-- ============================================================================
-- SECTION 4: NODES TABLE
-- ============================================================================
-- Aligned with AlphaNode Pydantic model in alpha_graph/models.py

CREATE TABLE IF NOT EXISTS fhq_graph.nodes (
    -- Primary key
    node_id TEXT PRIMARY KEY,

    -- Core fields (matching AlphaNode)
    node_type fhq_graph.node_type NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,

    -- IoS-007 extensions: Source lineage
    source_ios TEXT,                              -- IoS-001, IoS-003, IoS-006, IoS-009
    source_table TEXT,
    source_column TEXT,
    source_feature_id TEXT,                       -- FK to fhq_macro.feature_registry

    -- IoS-007 extensions: Data properties
    data_type TEXT CHECK (data_type IN (
        'CONTINUOUS', 'CATEGORICAL', 'COMPOSITE'
    )),
    update_frequency TEXT CHECK (update_frequency IN (
        'TICK', 'MINUTE', 'HOURLY', 'DAILY', 'WEEKLY', 'MONTHLY'
    )),

    -- IoS-007 extensions: Status
    status TEXT DEFAULT 'ACTIVE' CHECK (status IN (
        'REGISTERED', 'ACTIVE', 'RESERVED', 'DEPRECATED'
    )),

    -- IoS-007 extensions: Economic hypothesis
    hypothesis TEXT,
    expected_direction TEXT CHECK (expected_direction IN (
        'POSITIVE', 'NEGATIVE', 'BIDIRECTIONAL', 'UNKNOWN'
    )),

    -- IoS-005 validation
    ios005_validated BOOLEAN DEFAULT FALSE,
    ios005_validation_date TIMESTAMPTZ,
    ios005_evidence_hash TEXT,

    -- Lineage (ADR-011)
    content_hash TEXT,
    lineage_hash TEXT,
    hash_prev TEXT,
    hash_self TEXT,

    -- Timestamps (matching AlphaNode.created_at)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nodes_type ON fhq_graph.nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_source ON fhq_graph.nodes(source_ios);
CREATE INDEX IF NOT EXISTS idx_nodes_status ON fhq_graph.nodes(status);

COMMENT ON TABLE fhq_graph.nodes IS
'Alpha Graph nodes — persistence for AlphaNode Pydantic model.
Supports both alpha_graph v1.0 node types and IoS-007 causal extensions.';

-- ============================================================================
-- SECTION 5: EDGES TABLE
-- ============================================================================
-- Aligned with AlphaEdge Pydantic model in alpha_graph/models.py

CREATE TABLE IF NOT EXISTS fhq_graph.edges (
    -- Primary key
    edge_id TEXT PRIMARY KEY,

    -- Core fields (matching AlphaEdge)
    from_node_id TEXT NOT NULL REFERENCES fhq_graph.nodes(node_id),
    to_node_id TEXT NOT NULL REFERENCES fhq_graph.nodes(node_id),
    relationship_type fhq_graph.relationship_type NOT NULL,
    strength NUMERIC(8,5) NOT NULL CHECK (strength >= -1.0 AND strength <= 1.0),
    direction fhq_graph.edge_direction DEFAULT 'BI',
    lag_days INTEGER,
    regimes TEXT[] DEFAULT '{}',
    confidence NUMERIC(6,5) NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    p_value NUMERIC(6,5) CHECK (p_value >= 0.0 AND p_value <= 1.0),
    sample_size INTEGER,
    window_days INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb,

    -- IoS-007 extensions: Causal properties
    direction_strength TEXT CHECK (direction_strength IN (
        'STRONG', 'MODERATE', 'WEAK', 'UNCERTAIN'
    )),

    -- IoS-007 extensions: Granger causality
    granger_f_statistic NUMERIC,
    granger_p_value NUMERIC(6,5),
    optimal_lag INTEGER,

    -- IoS-007 extensions: Bootstrap validation
    permutation_p_value NUMERIC(6,5),
    bootstrap_p_value NUMERIC(6,5),
    weight_confidence_interval_lower NUMERIC(8,5),
    weight_confidence_interval_upper NUMERIC(8,5),

    -- IoS-007 extensions: Economic rationale
    hypothesis TEXT,
    transmission_mechanism TEXT,

    -- IoS-007 extensions: Validation status
    status TEXT DEFAULT 'ACTIVE' CHECK (status IN (
        'HYPOTHESIZED', 'TESTING', 'REJECTED', 'VALIDATED', 'GOLDEN', 'DECOUPLED', 'ACTIVE'
    )),

    -- IoS-005 validation
    ios005_tested BOOLEAN DEFAULT FALSE,
    ios005_test_date TIMESTAMPTZ,
    ios005_audit_id UUID,
    ios005_evidence_hash TEXT,

    -- Temporal stability
    stability_window_days INTEGER DEFAULT 252,
    last_recalculation TIMESTAMPTZ,
    weight_change_pct NUMERIC(6,3),

    -- Lineage (ADR-011)
    content_hash TEXT,
    lineage_hash TEXT,
    hash_prev TEXT,
    hash_self TEXT,

    -- Timestamps (matching AlphaEdge)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT no_self_loops CHECK (from_node_id != to_node_id)
);

CREATE INDEX IF NOT EXISTS idx_edges_from ON fhq_graph.edges(from_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON fhq_graph.edges(to_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_type ON fhq_graph.edges(relationship_type);
CREATE INDEX IF NOT EXISTS idx_edges_status ON fhq_graph.edges(status);
CREATE INDEX IF NOT EXISTS idx_edges_regimes ON fhq_graph.edges USING GIN (regimes);

COMMENT ON TABLE fhq_graph.edges IS
'Alpha Graph edges — persistence for AlphaEdge Pydantic model.
Supports both alpha_graph v1.0 relationship types and IoS-007 causal extensions.';

-- ============================================================================
-- SECTION 6: SNAPSHOTS TABLE
-- ============================================================================
-- Aligned with AlphaGraphSnapshot Pydantic model

CREATE TABLE IF NOT EXISTS fhq_graph.snapshots (
    -- Primary key
    snapshot_id TEXT PRIMARY KEY,

    -- Core fields (matching AlphaGraphSnapshot)
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    regime TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Denormalized counts
    node_count INTEGER NOT NULL DEFAULT 0,
    edge_count INTEGER NOT NULL DEFAULT 0,

    -- IoS-007 extensions: Regime context
    btc_regime TEXT,
    eth_regime TEXT,
    sol_regime TEXT,

    -- IoS-007 extensions: Macro context
    liquidity_value NUMERIC,
    gravity_value NUMERIC,

    -- IoS-007 extensions: Graph metrics
    n_validated_edges INTEGER DEFAULT 0,
    graph_density NUMERIC(6,5),

    -- IoS-007 extensions: Anomaly detection
    anomaly_detected BOOLEAN DEFAULT FALSE,
    anomaly_type TEXT,
    anomaly_severity TEXT CHECK (anomaly_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),

    -- IoS-007 extensions: Inference summary
    inference_run BOOLEAN DEFAULT FALSE,
    n_pathways_identified INTEGER DEFAULT 0,
    dominant_pathway TEXT,

    -- Lineage (ADR-011 Fortress)
    data_hash TEXT,
    config_hash TEXT,
    lineage_hash TEXT,
    hash_prev TEXT,
    hash_self TEXT,

    -- Metadata
    created_by TEXT DEFAULT 'STIG',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON fhq_graph.snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_snapshots_regime ON fhq_graph.snapshots(regime);

COMMENT ON TABLE fhq_graph.snapshots IS
'Alpha Graph snapshots — persistence for AlphaGraphSnapshot Pydantic model.
Each snapshot is a complete point-in-time view of the graph.';

-- ============================================================================
-- SECTION 7: SNAPSHOT NODES (Many-to-Many Join)
-- ============================================================================
-- Links snapshots to nodes at that point in time

CREATE TABLE IF NOT EXISTS fhq_graph.snapshot_nodes (
    snapshot_id TEXT NOT NULL REFERENCES fhq_graph.snapshots(snapshot_id),
    node_id TEXT NOT NULL REFERENCES fhq_graph.nodes(node_id),

    -- Node state at snapshot time
    node_value NUMERIC,
    node_confidence NUMERIC(6,5),
    node_regime TEXT,
    node_metadata JSONB DEFAULT '{}'::jsonb,

    PRIMARY KEY (snapshot_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_snapshot_nodes_snapshot ON fhq_graph.snapshot_nodes(snapshot_id);

-- ============================================================================
-- SECTION 8: SNAPSHOT EDGES (Many-to-Many Join)
-- ============================================================================
-- Links snapshots to edges at that point in time

CREATE TABLE IF NOT EXISTS fhq_graph.snapshot_edges (
    snapshot_id TEXT NOT NULL REFERENCES fhq_graph.snapshots(snapshot_id),
    edge_id TEXT NOT NULL REFERENCES fhq_graph.edges(edge_id),

    -- Edge state at snapshot time
    edge_strength NUMERIC(8,5),
    edge_confidence NUMERIC(6,5),
    edge_p_value NUMERIC(6,5),
    edge_metadata JSONB DEFAULT '{}'::jsonb,

    PRIMARY KEY (snapshot_id, edge_id)
);

CREATE INDEX IF NOT EXISTS idx_snapshot_edges_snapshot ON fhq_graph.snapshot_edges(snapshot_id);

-- ============================================================================
-- SECTION 9: DELTAS TABLE
-- ============================================================================
-- Aligned with AlphaGraphDelta Pydantic model

CREATE TABLE IF NOT EXISTS fhq_graph.deltas (
    -- Primary key
    delta_id TEXT PRIMARY KEY,

    -- Core fields (matching AlphaGraphDelta)
    from_snapshot_id TEXT NOT NULL REFERENCES fhq_graph.snapshots(snapshot_id),
    to_snapshot_id TEXT NOT NULL REFERENCES fhq_graph.snapshots(snapshot_id),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Changes stored as JSONB arrays
    nodes_added JSONB DEFAULT '[]'::jsonb,
    nodes_removed JSONB DEFAULT '[]'::jsonb,  -- Array of node_ids
    edges_added JSONB DEFAULT '[]'::jsonb,
    edges_removed JSONB DEFAULT '[]'::jsonb,  -- Array of edge_ids
    edges_updated JSONB DEFAULT '[]'::jsonb,

    metadata JSONB DEFAULT '{}'::jsonb,

    -- Lineage
    content_hash TEXT,
    hash_self TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deltas_from ON fhq_graph.deltas(from_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_deltas_to ON fhq_graph.deltas(to_snapshot_id);

COMMENT ON TABLE fhq_graph.deltas IS
'Alpha Graph deltas — persistence for AlphaGraphDelta Pydantic model.
Tracks changes between consecutive snapshots.';

-- ============================================================================
-- SECTION 10: INFERENCE LOG
-- ============================================================================
-- IoS-007 causal inference audit trail

CREATE TABLE IF NOT EXISTS fhq_graph.inference_log (
    inference_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Inference context
    inference_date DATE NOT NULL,
    inference_type TEXT NOT NULL CHECK (inference_type IN (
        'TOP_DRIVERS',       -- From alpha_graph queries
        'REGIME_CHANGES',
        'NODE_NEIGHBORS',
        'LEADING_INDICATORS',
        'CLUSTERS',
        'PROPAGATION',       -- From IoS-007 spec
        'CONTAGION',
        'PATHWAY_SEARCH',
        'STRESS_TEST',
        'OPPORTUNITY_SCAN'
    )),

    -- Query parameters
    target_node_id TEXT REFERENCES fhq_graph.nodes(node_id),
    source_node_id TEXT REFERENCES fhq_graph.nodes(node_id),
    regime TEXT,
    query_parameters JSONB DEFAULT '{}'::jsonb,

    -- Results (matching QueryResult / InfluenceScore)
    results JSONB NOT NULL,                       -- Array of InfluenceScore objects
    n_results INTEGER DEFAULT 0,

    -- IoS-007 extensions
    pathways_found JSONB,
    dominant_pathway TEXT,
    pathway_probability NUMERIC(6,5),
    expected_impact NUMERIC(8,5),
    confidence_interval_lower NUMERIC(8,5),
    confidence_interval_upper NUMERIC(8,5),

    -- Risk assessment
    risk_level TEXT CHECK (risk_level IN (
        'LOW', 'MODERATE', 'ELEVATED', 'HIGH', 'CRITICAL'
    )),
    risk_factors JSONB,

    -- IoS-005 validation
    ios005_validated BOOLEAN DEFAULT FALSE,
    ios005_audit_id UUID,
    ios005_evidence_hash TEXT,

    -- Execution metadata
    snapshot_id TEXT REFERENCES fhq_graph.snapshots(snapshot_id),
    execution_time_ms INTEGER,
    nodes_traversed INTEGER,
    edges_traversed INTEGER,

    -- Lineage (ADR-011)
    data_hash TEXT,
    lineage_hash TEXT,
    hash_prev TEXT,
    hash_self TEXT,

    -- Metadata
    requested_by TEXT DEFAULT 'LARS',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inference_date ON fhq_graph.inference_log(inference_date);
CREATE INDEX IF NOT EXISTS idx_inference_type ON fhq_graph.inference_log(inference_type);
CREATE INDEX IF NOT EXISTS idx_inference_target ON fhq_graph.inference_log(target_node_id);
CREATE INDEX IF NOT EXISTS idx_inference_snapshot ON fhq_graph.inference_log(snapshot_id);

COMMENT ON TABLE fhq_graph.inference_log IS
'Inference log — audit trail for graph queries and causal reasoning.
Supports both alpha_graph query types and IoS-007 causal inference.';

-- ============================================================================
-- SECTION 11: SEED CANONICAL NODES (IoS-007 Node Universe)
-- ============================================================================

-- 11.1 MACRO NODES (Source: IoS-006)
INSERT INTO fhq_graph.nodes (
    node_id, node_type, label, description, source_ios, source_table, source_column,
    source_feature_id, data_type, update_frequency, status, hypothesis, expected_direction,
    content_hash, metadata
) VALUES
(
    'NODE_LIQUIDITY', 'MACRO', 'Global M2 Liquidity',
    'The Fuel. Global M2 money supply in USD. Primary driver of risk asset prices.',
    'IoS-006', 'fhq_macro.canonical_series', 'value_transformed', 'GLOBAL_M2_USD',
    'CONTINUOUS', 'WEEKLY', 'ACTIVE',
    'Liquidity expansion leads to increased risk appetite and higher asset prices with lag.',
    'POSITIVE',
    encode(sha256('NODE_LIQUIDITY_2026'::bytea), 'hex'),
    '{"ios007_canonical": true, "cluster": "LIQUIDITY"}'::jsonb
),
(
    'NODE_GRAVITY', 'MACRO', 'US 10Y Real Rate',
    'The Friction. US 10-Year Treasury Real Yield. Risk-free discount rate.',
    'IoS-006', 'fhq_macro.canonical_series', 'value_transformed', 'US_10Y_REAL_RATE',
    'CONTINUOUS', 'DAILY', 'ACTIVE',
    'Rising real rates increase hurdle rate for risk assets, dampening valuations.',
    'NEGATIVE',
    encode(sha256('NODE_GRAVITY_2026'::bytea), 'hex'),
    '{"ios007_canonical": true, "cluster": "FACTOR"}'::jsonb
)
ON CONFLICT (node_id) DO UPDATE SET
    status = 'ACTIVE',
    updated_at = NOW();

-- 11.2 REGIME NODES (Source: IoS-003)
INSERT INTO fhq_graph.nodes (
    node_id, node_type, label, description, source_ios, source_table, source_column,
    data_type, update_frequency, status, hypothesis, expected_direction,
    content_hash, metadata
) VALUES
(
    'STATE_BTC', 'REGIME', 'Bitcoin Regime State',
    'Current HMM regime classification for BTC-USD from IoS-003 Perception Engine.',
    'IoS-003', 'fhq_perception.regime_daily', 'regime_classification',
    'CATEGORICAL', 'DAILY', 'ACTIVE',
    'BTC regime state determines allocation weights and risk limits.',
    'BIDIRECTIONAL',
    encode(sha256('STATE_BTC_2026'::bytea), 'hex'),
    '{"ios007_canonical": true, "asset": "BTC-USD"}'::jsonb
),
(
    'STATE_ETH', 'REGIME', 'Ethereum Regime State',
    'Current HMM regime classification for ETH-USD from IoS-003 Perception Engine.',
    'IoS-003', 'fhq_perception.regime_daily', 'regime_classification',
    'CATEGORICAL', 'DAILY', 'ACTIVE',
    'ETH regime state follows BTC but with higher beta and tech correlation.',
    'BIDIRECTIONAL',
    encode(sha256('STATE_ETH_2026'::bytea), 'hex'),
    '{"ios007_canonical": true, "asset": "ETH-USD"}'::jsonb
),
(
    'STATE_SOL', 'REGIME', 'Solana Regime State',
    'Current HMM regime classification for SOL-USD from IoS-003 Perception Engine.',
    'IoS-003', 'fhq_perception.regime_daily', 'regime_classification',
    'CATEGORICAL', 'DAILY', 'ACTIVE',
    'SOL regime state exhibits highest beta to BTC and liquidity conditions.',
    'BIDIRECTIONAL',
    encode(sha256('STATE_SOL_2026'::bytea), 'hex'),
    '{"ios007_canonical": true, "asset": "SOL-USD"}'::jsonb
)
ON CONFLICT (node_id) DO UPDATE SET
    status = 'ACTIVE',
    updated_at = NOW();

-- 11.3 ASSET NODES (Source: IoS-001)
INSERT INTO fhq_graph.nodes (
    node_id, node_type, label, description, source_ios, source_table, source_column,
    data_type, update_frequency, status, hypothesis, expected_direction,
    content_hash, metadata
) VALUES
(
    'ASSET_BTC', 'ASSET', 'Bitcoin Price & Volatility',
    'BTC-USD price, realized volatility, and volume from IoS-001 Asset Registry.',
    'IoS-001', 'fhq_data.price_series', 'close',
    'CONTINUOUS', 'DAILY', 'ACTIVE',
    'BTC price is the primary output variable. All macro/regime inputs propagate here.',
    'POSITIVE',
    encode(sha256('ASSET_BTC_2026'::bytea), 'hex'),
    '{"ios007_canonical": true, "symbol": "BTC-USD"}'::jsonb
),
(
    'ASSET_ETH', 'ASSET', 'Ethereum Price & Volatility',
    'ETH-USD price, realized volatility, and volume from IoS-001 Asset Registry.',
    'IoS-001', 'fhq_data.price_series', 'close',
    'CONTINUOUS', 'DAILY', 'ACTIVE',
    'ETH price coupled to BTC but with additional tech/DeFi narratives.',
    'POSITIVE',
    encode(sha256('ASSET_ETH_2026'::bytea), 'hex'),
    '{"ios007_canonical": true, "symbol": "ETH-USD"}'::jsonb
),
(
    'ASSET_SOL', 'ASSET', 'Solana Price & Volatility',
    'SOL-USD price, realized volatility, and volume from IoS-001 Asset Registry.',
    'IoS-001', 'fhq_data.price_series', 'close',
    'CONTINUOUS', 'DAILY', 'ACTIVE',
    'SOL price highest beta. Most sensitive to liquidity and regime shifts.',
    'POSITIVE',
    encode(sha256('ASSET_SOL_2026'::bytea), 'hex'),
    '{"ios007_canonical": true, "symbol": "SOL-USD"}'::jsonb
)
ON CONFLICT (node_id) DO UPDATE SET
    status = 'ACTIVE',
    updated_at = NOW();

-- 11.4 FUTURE NODES (Reserved for IoS-009)
INSERT INTO fhq_graph.nodes (
    node_id, node_type, label, description, source_ios,
    data_type, update_frequency, status, hypothesis, expected_direction,
    content_hash, metadata
) VALUES
(
    'NODE_SENTIMENT', 'FUTURE', 'Narrative Intensity',
    'RESERVED: Social sentiment and narrative intensity from IoS-009.',
    'IoS-009',
    'COMPOSITE', 'DAILY', 'RESERVED',
    'Sentiment extremes precede regime transitions.',
    'BIDIRECTIONAL',
    encode(sha256('NODE_SENTIMENT_RESERVED_2026'::bytea), 'hex'),
    '{"ios007_canonical": true, "reserved_for": "IoS-009"}'::jsonb
),
(
    'NODE_RISK', 'FUTURE', 'Systemic Stress Level',
    'RESERVED: Systemic risk indicator from IoS-009.',
    'IoS-009',
    'COMPOSITE', 'DAILY', 'RESERVED',
    'High systemic stress amplifies contagion pathways.',
    'NEGATIVE',
    encode(sha256('NODE_RISK_RESERVED_2026'::bytea), 'hex'),
    '{"ios007_canonical": true, "reserved_for": "IoS-009"}'::jsonb
)
ON CONFLICT (node_id) DO UPDATE SET
    status = 'RESERVED',
    updated_at = NOW();

-- ============================================================================
-- SECTION 12: SEED HYPOTHESIZED EDGES
-- ============================================================================

-- Using alpha_graph edge_id generation pattern: edge_{hash}_{type}
INSERT INTO fhq_graph.edges (
    edge_id, from_node_id, to_node_id, relationship_type, strength, direction,
    lag_days, confidence, hypothesis, transmission_mechanism, status, metadata
) VALUES
-- MACRO → REGIME (LEADS relationships)
(
    'edge_liq_btc_leads', 'NODE_LIQUIDITY', 'STATE_BTC', 'LEADS', 0.5, 'UNI',
    21, 0.7,
    'Expanding global M2 precedes bullish BTC regime transitions.',
    'Liquidity → Risk Appetite → Speculative Assets → BTC Regime',
    'HYPOTHESIZED',
    '{"ios007_causal": true}'::jsonb
),
(
    'edge_liq_eth_leads', 'NODE_LIQUIDITY', 'STATE_ETH', 'LEADS', 0.5, 'UNI',
    21, 0.7,
    'Expanding global M2 precedes bullish ETH regime transitions.',
    'Liquidity → Risk Appetite → Tech/DeFi → ETH Regime',
    'HYPOTHESIZED',
    '{"ios007_causal": true}'::jsonb
),
(
    'edge_liq_sol_leads', 'NODE_LIQUIDITY', 'STATE_SOL', 'LEADS', 0.6, 'UNI',
    14, 0.75,
    'SOL shows highest sensitivity to liquidity changes (shorter lag).',
    'Liquidity → High Beta Assets → SOL Regime',
    'HYPOTHESIZED',
    '{"ios007_causal": true}'::jsonb
),
(
    'edge_grav_btc_inhibits', 'NODE_GRAVITY', 'STATE_BTC', 'INHIBITS', -0.4, 'UNI',
    7, 0.7,
    'Rising real rates dampen risk appetite, pressuring BTC regimes.',
    'Real Rates ↑ → Hurdle Rate ↑ → Risk Assets Sold → BTC Regime ↓',
    'HYPOTHESIZED',
    '{"ios007_causal": true}'::jsonb
),
(
    'edge_grav_eth_inhibits', 'NODE_GRAVITY', 'STATE_ETH', 'INHIBITS', -0.4, 'UNI',
    7, 0.7,
    'Rising real rates dampen tech valuations including ETH.',
    'Real Rates ↑ → Growth Discount ↑ → Tech Sold → ETH Regime ↓',
    'HYPOTHESIZED',
    '{"ios007_causal": true}'::jsonb
),
-- REGIME → ASSET (AMPLIFIES relationships)
(
    'edge_btc_regime_amplifies', 'STATE_BTC', 'ASSET_BTC', 'AMPLIFIES', 0.8, 'UNI',
    0, 0.9,
    'Bullish BTC regime amplifies positive price momentum.',
    'Regime Classification → Allocation Signal → Price Impact',
    'HYPOTHESIZED',
    '{"ios007_causal": true}'::jsonb
),
(
    'edge_eth_regime_amplifies', 'STATE_ETH', 'ASSET_ETH', 'AMPLIFIES', 0.8, 'UNI',
    0, 0.9,
    'Bullish ETH regime amplifies positive price momentum.',
    'Regime Classification → Allocation Signal → Price Impact',
    'HYPOTHESIZED',
    '{"ios007_causal": true}'::jsonb
),
(
    'edge_sol_regime_amplifies', 'STATE_SOL', 'ASSET_SOL', 'AMPLIFIES', 0.8, 'UNI',
    0, 0.9,
    'Bullish SOL regime amplifies positive price momentum.',
    'Regime Classification → Allocation Signal → Price Impact',
    'HYPOTHESIZED',
    '{"ios007_causal": true}'::jsonb
),
-- ASSET → ASSET (COUPLES relationships)
(
    'edge_btc_eth_couples', 'ASSET_BTC', 'ASSET_ETH', 'COUPLES', 0.85, 'BI',
    0, 0.95,
    'BTC and ETH move together in most market conditions.',
    'BTC Price → Market Sentiment → ETH Price (correlated)',
    'HYPOTHESIZED',
    '{"ios007_causal": true}'::jsonb
),
(
    'edge_btc_sol_couples', 'ASSET_BTC', 'ASSET_SOL', 'COUPLES', 0.80, 'BI',
    0, 0.90,
    'BTC and SOL move together with SOL showing higher beta.',
    'BTC Price → Market Sentiment → SOL Price (high beta)',
    'HYPOTHESIZED',
    '{"ios007_causal": true}'::jsonb
),
(
    'edge_eth_sol_couples', 'ASSET_ETH', 'ASSET_SOL', 'COUPLES', 0.75, 'BI',
    0, 0.85,
    'ETH and SOL coupled via shared DeFi/smart contract narrative.',
    'ETH Price → Platform Narrative → SOL Price',
    'HYPOTHESIZED',
    '{"ios007_causal": true}'::jsonb
),
-- MACRO → ASSET direct (LEAD_LAG relationships using alpha_graph type)
(
    'edge_liq_btc_lead_lag', 'NODE_LIQUIDITY', 'ASSET_BTC', 'LEAD_LAG', 0.5, 'UNI',
    28, 0.7,
    'Direct liquidity-to-price pathway (not via regime).',
    'M2 Expansion → Capital Flows → BTC Demand → Price',
    'HYPOTHESIZED',
    '{"ios007_causal": true}'::jsonb
)
ON CONFLICT (edge_id) DO UPDATE SET
    status = 'HYPOTHESIZED',
    updated_at = NOW();

-- ============================================================================
-- SECTION 13: REGISTER IoS-007 IN IOS_REGISTRY
-- ============================================================================

INSERT INTO fhq_meta.ios_registry (
    ios_id,
    title,
    description,
    version,
    status,
    owner_role,
    governing_adrs,
    dependencies,
    content_hash,
    experimental_classification,
    risk_multiplier,
    immutability_level,
    canonical,
    modification_requires
) VALUES (
    'IoS-007',
    'Alpha Graph Engine — Causal Reasoning Core',
    'Transforms FjordHQ from reactive to reasoning system. Models the Transmission Mechanism: ' ||
    'How liquidity shocks (IoS-006) propagate to regime shifts (IoS-003) to asset prices (IoS-001). ' ||
    'Node Universe: 8 canonical nodes (2 MACRO, 3 REGIME, 3 ASSET). ' ||
    'Compatible with alpha_graph Python package v1.0. ' ||
    'Ontology FROZEN under ADR-013.',
    '2026.PROD.G0',
    'DRAFT',
    'FINN',
    ARRAY['ADR-002', 'ADR-003', 'ADR-011', 'ADR-013', 'ADR-054'],
    ARRAY['IoS-001', 'IoS-003', 'IoS-005', 'IoS-006'],
    encode(sha256('IoS-007_G0_FOUNDATION_20251130'::bytea), 'hex'),
    'UNCLASSIFIED',
    1.0,
    'FROZEN',
    FALSE,
    'G1-G4 Full Cycle (ADR-004, ADR-013)'
) ON CONFLICT (ios_id) DO UPDATE SET
    version = '2026.PROD.G0',
    status = 'DRAFT',
    updated_at = NOW();

-- ============================================================================
-- SECTION 14: REGISTER TASK IN TASK_REGISTRY
-- ============================================================================

INSERT INTO fhq_governance.task_registry (
    task_id,
    task_name,
    task_type,
    task_scope,
    owned_by_agent,
    executed_by_agent,
    reads_from_schemas,
    writes_to_schemas,
    gate_level,
    gate_approved,
    vega_reviewed,
    description,
    task_status,
    created_by,
    created_at,
    updated_at,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'ALPHA_GRAPH_ENGINE_V1',
    'CAUSAL_REASONING',
    'IOS_007_INTERNAL',
    'FINN',
    'CODE',
    ARRAY['fhq_graph', 'fhq_perception', 'fhq_macro', 'fhq_data'],
    ARRAY['fhq_graph'],
    'G0',
    FALSE,
    FALSE,
    'IoS-007 Alpha Graph Engine. Causal reasoning system. Compatible with alpha_graph Python package.',
    'REGISTERED',
    'STIG',
    NOW(),
    NOW(),
    'HC-IOS-007-2026'
) ON CONFLICT (task_name) DO UPDATE SET
    gate_level = 'G0',
    updated_at = NOW();

-- ============================================================================
-- SECTION 15: CREATE HASH CHAIN FOR IoS-007
-- ============================================================================

INSERT INTO vision_verification.hash_chains (
    chain_id,
    chain_type,
    chain_scope,
    genesis_hash,
    current_hash,
    chain_length,
    schema_frozen,
    integrity_verified,
    created_by,
    created_at,
    updated_at
) VALUES (
    'HC-IOS-007-2026',
    'IOS_MODULE',
    'fhq_graph.nodes,fhq_graph.edges,fhq_graph.snapshots',
    encode(sha256('IoS-007_GENESIS_20251130'::bytea), 'hex'),
    encode(sha256('IoS-007_GENESIS_20251130'::bytea), 'hex'),
    1,
    TRUE,
    TRUE,
    'STIG',
    NOW(),
    NOW()
) ON CONFLICT (chain_id) DO UPDATE SET
    schema_frozen = TRUE,
    updated_at = NOW();

-- ============================================================================
-- SECTION 16: LOG GOVERNANCE ACTION (G0 SUBMISSION)
-- ============================================================================

DO $$
DECLARE
    v_signature_id UUID := gen_random_uuid();
    v_action_id UUID := gen_random_uuid();
    v_payload JSONB;
    v_signature_value TEXT;
BEGIN
    v_payload := jsonb_build_object(
        'action_type', 'IOS_MODULE_G0_SUBMISSION',
        'action_target', 'IoS-007',
        'decision', 'APPROVED',
        'initiated_by', 'STIG',
        'timestamp', NOW()::text,
        'chain_id', 'HC-IOS-007-2026',
        'module_spec', jsonb_build_object(
            'title', 'Alpha Graph Engine — Causal Reasoning Core',
            'owner', 'FINN',
            'validator', 'IoS-005',
            'mission', 'From Correlation to Causality',
            'python_package', 'alpha_graph v1.0',
            'node_universe', jsonb_build_object(
                'macro_nodes', ARRAY['NODE_LIQUIDITY', 'NODE_GRAVITY'],
                'regime_nodes', ARRAY['STATE_BTC', 'STATE_ETH', 'STATE_SOL'],
                'asset_nodes', ARRAY['ASSET_BTC', 'ASSET_ETH', 'ASSET_SOL'],
                'future_nodes', ARRAY['NODE_SENTIMENT', 'NODE_RISK']
            ),
            'edge_types', ARRAY['LEADS', 'INHIBITS', 'AMPLIFIES', 'COUPLES', 'BREAKS',
                               'CORRELATION', 'CAUSALITY', 'LEAD_LAG', 'REGIME_CONDITIONAL'],
            'ontology_frozen', TRUE
        )
    );

    v_signature_value := encode(sha256(v_payload::text::bytea), 'hex');

    INSERT INTO vision_verification.operation_signatures (
        signature_id, operation_type, operation_id, operation_table, operation_schema,
        signing_agent, signing_key_id, signature_value, signed_payload,
        verified, verified_at, verified_by, created_at, hash_chain_id
    ) VALUES (
        v_signature_id, 'IOS_MODULE_G0_SUBMISSION', v_action_id, 'governance_actions_log',
        'fhq_governance', 'STIG', 'STIG-EC003-IOS007-G0', v_signature_value, v_payload,
        TRUE, NOW(), 'STIG', NOW(), 'HC-IOS-007-2026'
    );

    INSERT INTO fhq_governance.governance_actions_log (
        action_id, action_type, action_target, action_target_type, initiated_by,
        initiated_at, decision, decision_rationale, vega_reviewed, vega_override,
        vega_notes, hash_chain_id, signature_id
    ) VALUES (
        v_action_id, 'IOS_MODULE_G0_SUBMISSION', 'IoS-007', 'IOS_MODULE', 'STIG', NOW(),
        'APPROVED',
        'G0 SUBMISSION: IoS-007 Alpha Graph Engine — Causal Reasoning Core. ' ||
        'Schema fhq_graph created. Compatible with alpha_graph Python package v1.0. ' ||
        'Tables: nodes, edges, snapshots, snapshot_nodes, snapshot_edges, deltas, inference_log. ' ||
        'Node Universe: 8 canonical (2 MACRO, 3 REGIME, 3 ASSET). ' ||
        'Ready for G1 Historical Build.',
        FALSE, FALSE,
        'Awaiting VEGA review. IoS-007 must demonstrate edge validation via IoS-005 before G2.',
        'HC-IOS-007-2026', v_signature_id
    );

    RAISE NOTICE 'IoS-007 G0 SUBMISSION: action_id=%, signature_id=%', v_action_id, v_signature_id;
END $$;

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- SELECT * FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-007';
-- SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'fhq_graph';
-- SELECT * FROM fhq_graph.nodes ORDER BY node_type, node_id;
-- SELECT * FROM fhq_graph.edges ORDER BY from_node_id, to_node_id;
-- SELECT * FROM fhq_governance.task_registry WHERE task_name = 'ALPHA_GRAPH_ENGINE_V1';
-- SELECT * FROM vision_verification.hash_chains WHERE chain_id = 'HC-IOS-007-2026';
