-- ============================================================
-- ALPHA GRAPH: GOLDEN FEATURES INTEGRATION
-- Authority: STIG (CTO)
-- Purpose: Connect validated Golden Features to Alpha Graph
-- Migration: 047_alpha_graph_golden_features.sql
-- ============================================================

BEGIN;

-- ============================================================
-- ACTION 1: Add US_M2_YOY node to Alpha Graph
-- ============================================================

INSERT INTO fhq_graph.nodes (
    node_id, node_type, label, description, metadata,
    source_ios, source_table, source_column, source_feature_id,
    data_type, update_frequency, status,
    hypothesis, expected_direction,
    ios005_validated, ios005_validation_date, ios005_evidence_hash,
    content_hash
) VALUES (
    'NODE_M2_YOY', 'MACRO', 'US M2 Money Supply YoY',
    'Year-over-year change in US M2 money supply. Primary liquidity indicator.',
    '{"cluster": "LIQUIDITY", "ios007_canonical": true}'::jsonb,
    'IoS-006', 'fhq_macro.canonical_series', 'value_transformed', 'US_M2_YOY',
    'CONTINUOUS', 'MONTHLY', 'ACTIVE',
    'M2 expansion leads crypto rallies by ~1 month due to portfolio rebalancing lag.',
    'POSITIVE',
    true, NOW(), '28b92f060eaba97d185949cbf16ad3799233d211ddf74c9f627b80e02392a0a9',
    encode(sha256('NODE_M2_YOY'::bytea), 'hex')
)
ON CONFLICT (node_id) DO UPDATE SET
    ios005_validated = true,
    ios005_validation_date = NOW(),
    ios005_evidence_hash = EXCLUDED.ios005_evidence_hash,
    updated_at = NOW();

-- ============================================================
-- ACTION 2: Update ios005_validated on existing Golden Feature nodes
-- ============================================================

-- Update NODE_LIQUIDITY (GLOBAL_M2_USD)
UPDATE fhq_graph.nodes SET
    ios005_validated = true,
    ios005_validation_date = NOW(),
    ios005_evidence_hash = '28b92f060eaba97d185949cbf16ad3799233d211ddf74c9f627b80e02392a0a9',
    updated_at = NOW()
WHERE node_id = 'NODE_LIQUIDITY';

-- Update NODE_GRAVITY (US_10Y_REAL_RATE)
UPDATE fhq_graph.nodes SET
    ios005_validated = true,
    ios005_validation_date = NOW(),
    ios005_evidence_hash = '1076562d1be6dc470959ae5538b9d29caa6202edd9f999e8c83c106d49f44267',
    updated_at = NOW()
WHERE node_id = 'NODE_GRAVITY';

-- ============================================================
-- ACTION 3: Create Edges connecting Golden Features to Assets
-- ============================================================

-- Edge: NODE_M2_YOY -> ASSET_BTC (Golden Feature, p=0.018, lag=1)
INSERT INTO fhq_graph.edges (
    edge_id, from_node_id, to_node_id, relationship_type,
    strength, direction, lag_days, confidence, p_value, sample_size,
    optimal_lag, permutation_p_value, bootstrap_p_value,
    weight_confidence_interval_lower, weight_confidence_interval_upper,
    hypothesis, transmission_mechanism, status,
    ios005_tested, ios005_test_date, ios005_evidence_hash
) VALUES (
    'EDGE_M2_YOY_BTC', 'NODE_M2_YOY', 'ASSET_BTC', 'LEADS',
    0.229, 'UNI', 1, 0.95, 0.018, 118,
    1, 0.018, 0.018,
    0.045, 0.397,
    'M2 expansion leads BTC rallies with 1-day lag',
    'Liquidity flows to risk assets → crypto first',
    'GOLDEN',
    true, NOW(), '28b92f060eaba97d185949cbf16ad3799233d211ddf74c9f627b80e02392a0a9'
)
ON CONFLICT (edge_id) DO UPDATE SET
    strength = EXCLUDED.strength,
    p_value = EXCLUDED.p_value,
    ios005_tested = true,
    ios005_test_date = NOW(),
    status = 'GOLDEN',
    updated_at = NOW();

-- Edge: NODE_LIQUIDITY (GLOBAL_M2_USD) -> ASSET_BTC (Golden Feature, p=0.016, lag=1)
INSERT INTO fhq_graph.edges (
    edge_id, from_node_id, to_node_id, relationship_type,
    strength, direction, lag_days, confidence, p_value, sample_size,
    optimal_lag, permutation_p_value, bootstrap_p_value,
    weight_confidence_interval_lower, weight_confidence_interval_upper,
    hypothesis, transmission_mechanism, status,
    ios005_tested, ios005_test_date, ios005_evidence_hash
) VALUES (
    'EDGE_LIQUIDITY_BTC', 'NODE_LIQUIDITY', 'ASSET_BTC', 'LEADS',
    0.229, 'UNI', 1, 0.95, 0.016, 118,
    1, 0.018, 0.016,
    0.040, 0.391,
    'Global M2 expansion leads BTC rallies with 1-day lag',
    'Global liquidity flows to risk assets → crypto allocation increases',
    'GOLDEN',
    true, NOW(), '28b92f060eaba97d185949cbf16ad3799233d211ddf74c9f627b80e02392a0a9'
)
ON CONFLICT (edge_id) DO UPDATE SET
    strength = EXCLUDED.strength,
    p_value = EXCLUDED.p_value,
    ios005_tested = true,
    ios005_test_date = NOW(),
    status = 'GOLDEN',
    updated_at = NOW();

-- Edge: NODE_GRAVITY (US_10Y_REAL_RATE) -> ASSET_BTC (Golden Feature, p=0.004, lag=0)
INSERT INTO fhq_graph.edges (
    edge_id, from_node_id, to_node_id, relationship_type,
    strength, direction, lag_days, confidence, p_value, sample_size,
    optimal_lag, permutation_p_value, bootstrap_p_value,
    weight_confidence_interval_lower, weight_confidence_interval_upper,
    hypothesis, transmission_mechanism, status,
    ios005_tested, ios005_test_date, ios005_evidence_hash
) VALUES (
    'EDGE_GRAVITY_BTC', 'NODE_GRAVITY', 'ASSET_BTC', 'CORRELATION',
    0.056, 'UNI', 0, 0.95, 0.004, 2571,
    0, 0.004, 0.010,
    0.015, 0.098,
    'Real rates influence BTC contemporaneously (unexpected POSITIVE)',
    'BTC acts as inflation hedge during rate hikes (contra expected)',
    'GOLDEN',
    true, NOW(), '1076562d1be6dc470959ae5538b9d29caa6202edd9f999e8c83c106d49f44267'
)
ON CONFLICT (edge_id) DO UPDATE SET
    strength = EXCLUDED.strength,
    p_value = EXCLUDED.p_value,
    ios005_tested = true,
    ios005_test_date = NOW(),
    status = 'GOLDEN',
    updated_at = NOW();

-- Edge: STATE_BTC -> ASSET_BTC (Regime drives position sizing)
INSERT INTO fhq_graph.edges (
    edge_id, from_node_id, to_node_id, relationship_type,
    strength, direction, lag_days, confidence,
    hypothesis, transmission_mechanism, status,
    ios005_tested, ios005_test_date
) VALUES (
    'EDGE_REGIME_BTC', 'STATE_BTC', 'ASSET_BTC', 'REGIME_CONDITIONAL',
    1.0, 'BI', 0, 1.0,
    'Regime state determines position sizing and risk limits',
    'HMM regime classification → allocation weight lookup',
    'ACTIVE',
    true, NOW()
)
ON CONFLICT (edge_id) DO UPDATE SET
    status = 'ACTIVE',
    updated_at = NOW();

-- ============================================================
-- ACTION 4: Create Signal Generation Rules Table
-- ============================================================

CREATE TABLE IF NOT EXISTS vision_signals.regime_position_rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id TEXT NOT NULL,
    regime_label TEXT NOT NULL,
    target_allocation NUMERIC(5,4) NOT NULL CHECK (target_allocation BETWEEN -1 AND 1),
    max_position_pct NUMERIC(5,4) NOT NULL CHECK (max_position_pct BETWEEN 0 AND 1),
    stop_loss_pct NUMERIC(5,4),
    take_profit_pct NUMERIC(5,4),
    confidence_threshold NUMERIC(5,4) DEFAULT 0.40,
    signal_type TEXT NOT NULL DEFAULT 'REGIME_BASED',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'STIG',
    UNIQUE(asset_id, regime_label)
);

-- Insert position sizing rules for BTC
INSERT INTO vision_signals.regime_position_rules
    (asset_id, regime_label, target_allocation, max_position_pct, stop_loss_pct, take_profit_pct, confidence_threshold)
VALUES
    -- BTC Position Rules
    ('BTC-USD', 'STRONG_BULL', 1.00, 1.00, 0.15, NULL, 0.50),    -- Max long
    ('BTC-USD', 'BULL', 0.75, 0.80, 0.12, NULL, 0.45),           -- Standard long
    ('BTC-USD', 'RANGE_UP', 0.50, 0.60, 0.10, 0.15, 0.40),       -- Accumulate
    ('BTC-USD', 'NEUTRAL', 0.00, 0.30, 0.08, 0.10, 0.35),        -- No position
    ('BTC-USD', 'RANGE_DOWN', -0.25, 0.40, 0.10, 0.12, 0.40),    -- Light short
    ('BTC-USD', 'BEAR', -0.50, 0.60, 0.12, NULL, 0.45),          -- Standard short
    ('BTC-USD', 'STRONG_BEAR', -0.75, 0.80, 0.15, NULL, 0.50),   -- Max short
    ('BTC-USD', 'PARABOLIC', 0.25, 0.40, 0.20, 0.30, 0.60),      -- Reduce & hedge
    ('BTC-USD', 'BROKEN', 0.00, 0.00, NULL, NULL, 0.00),         -- Exit all

    -- ETH Position Rules (higher beta)
    ('ETH-USD', 'STRONG_BULL', 1.00, 1.00, 0.18, NULL, 0.50),
    ('ETH-USD', 'BULL', 0.75, 0.80, 0.15, NULL, 0.45),
    ('ETH-USD', 'RANGE_UP', 0.50, 0.60, 0.12, 0.18, 0.40),
    ('ETH-USD', 'NEUTRAL', 0.00, 0.30, 0.10, 0.12, 0.35),
    ('ETH-USD', 'RANGE_DOWN', -0.25, 0.40, 0.12, 0.15, 0.40),
    ('ETH-USD', 'BEAR', -0.50, 0.60, 0.15, NULL, 0.45),
    ('ETH-USD', 'STRONG_BEAR', -0.75, 0.80, 0.18, NULL, 0.50),
    ('ETH-USD', 'PARABOLIC', 0.25, 0.40, 0.25, 0.35, 0.60),
    ('ETH-USD', 'BROKEN', 0.00, 0.00, NULL, NULL, 0.00),

    -- SOL Position Rules (highest beta)
    ('SOL-USD', 'STRONG_BULL', 1.00, 1.00, 0.22, NULL, 0.50),
    ('SOL-USD', 'BULL', 0.75, 0.80, 0.18, NULL, 0.45),
    ('SOL-USD', 'RANGE_UP', 0.50, 0.60, 0.15, 0.22, 0.40),
    ('SOL-USD', 'NEUTRAL', 0.00, 0.30, 0.12, 0.15, 0.35),
    ('SOL-USD', 'RANGE_DOWN', -0.25, 0.40, 0.15, 0.18, 0.40),
    ('SOL-USD', 'BEAR', -0.50, 0.60, 0.18, NULL, 0.45),
    ('SOL-USD', 'STRONG_BEAR', -0.75, 0.80, 0.22, NULL, 0.50),
    ('SOL-USD', 'PARABOLIC', 0.25, 0.40, 0.30, 0.40, 0.60),
    ('SOL-USD', 'BROKEN', 0.00, 0.00, NULL, NULL, 0.00)
ON CONFLICT (asset_id, regime_label) DO UPDATE SET
    target_allocation = EXCLUDED.target_allocation,
    max_position_pct = EXCLUDED.max_position_pct,
    stop_loss_pct = EXCLUDED.stop_loss_pct,
    take_profit_pct = EXCLUDED.take_profit_pct,
    updated_at = NOW();

-- ============================================================
-- Log governance action
-- ============================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale,
    vega_reviewed, vega_override, hash_chain_id
) VALUES (
    gen_random_uuid(),
    'ALPHA_GRAPH_UPDATE',
    'fhq_graph.nodes, fhq_graph.edges, vision_signals.regime_position_rules',
    'SCHEMA',
    'STIG',
    NOW(),
    'APPROVED',
    'Connected 3 Golden Features (US_M2_YOY, GLOBAL_M2_USD, US_10Y_REAL_RATE) to Alpha Graph. Created 27 regime-based position rules for BTC, ETH, SOL.',
    false,
    false,
    'HC-ALPHA-GRAPH-047'
);

COMMIT;

-- ============================================================
-- Verification queries
-- ============================================================

SELECT 'NODES' as type, node_id, ios005_validated, status
FROM fhq_graph.nodes
WHERE node_type = 'MACRO'
ORDER BY node_id;

SELECT 'EDGES' as type, edge_id, from_node_id, to_node_id, strength, p_value, status
FROM fhq_graph.edges
WHERE status = 'GOLDEN'
ORDER BY edge_id;

SELECT 'RULES' as type, asset_id, regime_label, target_allocation, max_position_pct
FROM vision_signals.regime_position_rules
WHERE asset_id = 'BTC-USD'
ORDER BY target_allocation DESC;
