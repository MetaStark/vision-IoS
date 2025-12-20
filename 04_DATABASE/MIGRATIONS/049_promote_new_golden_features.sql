-- ============================================================
-- PROMOTE NEW GOLDEN FEATURES TO ALPHA GRAPH
-- Authority: STIG (CTO)
-- Purpose: Add US_NET_LIQUIDITY (GOLDEN) and FED_TOTAL_ASSETS (SIGNIFICANT)
-- Migration: 049_promote_new_golden_features.sql
-- Evidence: G3_1_LIQUIDITY_SIGNIFICANCE_20251201.json
-- ============================================================

BEGIN;

-- ============================================================
-- ACTION 1: Add US_NET_LIQUIDITY node (GOLDEN - p=0.037)
-- ============================================================

INSERT INTO fhq_graph.nodes (
    node_id, node_type, label, description, metadata,
    source_ios, source_table, source_column, source_feature_id,
    data_type, update_frequency, status,
    hypothesis, expected_direction,
    ios005_validated, ios005_validation_date, ios005_evidence_hash,
    content_hash
) VALUES (
    'NODE_NET_LIQ', 'MACRO', 'US Net Liquidity',
    'Fed Total Assets - TGA - RRP. Primary liquidity measure for risk assets.',
    '{"cluster": "LIQUIDITY", "ios007_canonical": true, "calculation": "WALCL - WTREGEN - RRPONTSYD"}'::jsonb,
    'IoS-006', 'fhq_macro.canonical_series', 'value_transformed', 'US_NET_LIQUIDITY',
    'CONTINUOUS', 'WEEKLY', 'ACTIVE',
    'Net liquidity expansion precedes crypto rallies. Core thesis of institutional flows.',
    'POSITIVE',
    true, NOW(), 'b602acdba490ba71247898aa5d318865bef0503cb3e149518da5d638fecb0080',
    encode(sha256('NODE_NET_LIQ'::bytea), 'hex')
)
ON CONFLICT (node_id) DO UPDATE SET
    ios005_validated = true,
    ios005_validation_date = NOW(),
    ios005_evidence_hash = EXCLUDED.ios005_evidence_hash,
    status = 'ACTIVE',
    updated_at = NOW();

-- ============================================================
-- ACTION 2: Add FED_TOTAL_ASSETS node (SIGNIFICANT - p=0.035)
-- ============================================================

INSERT INTO fhq_graph.nodes (
    node_id, node_type, label, description, metadata,
    source_ios, source_table, source_column, source_feature_id,
    data_type, update_frequency, status,
    hypothesis, expected_direction,
    ios005_validated, ios005_validation_date, ios005_evidence_hash,
    content_hash
) VALUES (
    'NODE_FED_ASSETS', 'MACRO', 'Fed Total Assets',
    'Federal Reserve Balance Sheet Total Assets (WALCL). Quantitative easing indicator.',
    '{"cluster": "LIQUIDITY", "ios007_canonical": true, "fred_ticker": "WALCL"}'::jsonb,
    'IoS-006', 'fhq_macro.canonical_series', 'value_transformed', 'FED_TOTAL_ASSETS',
    'CONTINUOUS', 'WEEKLY', 'ACTIVE',
    'Fed balance sheet expansion precedes risk-on environment.',
    'POSITIVE',
    true, NOW(), 'b602acdba490ba71247898aa5d318865bef0503cb3e149518da5d638fecb0080',
    encode(sha256('NODE_FED_ASSETS'::bytea), 'hex')
)
ON CONFLICT (node_id) DO UPDATE SET
    ios005_validated = true,
    ios005_validation_date = NOW(),
    ios005_evidence_hash = EXCLUDED.ios005_evidence_hash,
    status = 'ACTIVE',
    updated_at = NOW();

-- ============================================================
-- ACTION 3: Create Edge US_NET_LIQUIDITY -> ASSET_BTC (GOLDEN)
-- ============================================================

INSERT INTO fhq_graph.edges (
    edge_id, from_node_id, to_node_id, relationship_type,
    strength, direction, lag_days, confidence, p_value, sample_size,
    optimal_lag, permutation_p_value, bootstrap_p_value,
    hypothesis, transmission_mechanism, status,
    ios005_tested, ios005_test_date, ios005_evidence_hash
) VALUES (
    'EDGE_NET_LIQ_BTC', 'NODE_NET_LIQ', 'ASSET_BTC', 'CORRELATION',
    0.15, 'UNI', 0, 0.95, 0.037, 1198,
    0, 0.037, 0.037,
    'Net liquidity expansion correlates with BTC contemporaneously',
    'Fed liquidity injections → portfolio rebalancing → crypto allocation',
    'GOLDEN',
    true, NOW(), 'b602acdba490ba71247898aa5d318865bef0503cb3e149518da5d638fecb0080'
)
ON CONFLICT (edge_id) DO UPDATE SET
    strength = EXCLUDED.strength,
    p_value = EXCLUDED.p_value,
    ios005_tested = true,
    ios005_test_date = NOW(),
    status = 'GOLDEN',
    updated_at = NOW();

-- ============================================================
-- ACTION 4: Create Edge FED_TOTAL_ASSETS -> ASSET_BTC (SIGNIFICANT)
-- ============================================================

INSERT INTO fhq_graph.edges (
    edge_id, from_node_id, to_node_id, relationship_type,
    strength, direction, lag_days, confidence, p_value, sample_size,
    optimal_lag, permutation_p_value, bootstrap_p_value,
    hypothesis, transmission_mechanism, status,
    ios005_tested, ios005_test_date, ios005_evidence_hash
) VALUES (
    'EDGE_FED_ASSETS_BTC', 'NODE_FED_ASSETS', 'ASSET_BTC', 'CORRELATION',
    0.12, 'UNI', 0, 0.90, 0.035, 1198,
    0, 0.035, 0.050,
    'Fed balance sheet expansion correlates with BTC (borderline significant)',
    'QE → liquidity → risk-on sentiment',
    'VALIDATED',
    true, NOW(), 'b602acdba490ba71247898aa5d318865bef0503cb3e149518da5d638fecb0080'
)
ON CONFLICT (edge_id) DO UPDATE SET
    strength = EXCLUDED.strength,
    p_value = EXCLUDED.p_value,
    ios005_tested = true,
    ios005_test_date = NOW(),
    status = 'VALIDATED',
    updated_at = NOW();

-- ============================================================
-- ACTION 5: Update feature_registry status
-- ============================================================

UPDATE fhq_macro.feature_registry SET
    status = 'GOLDEN',
    ios005_tested = true,
    ios005_p_value = 0.037,
    ios005_test_date = NOW(),
    ios005_evidence_hash = 'b602acdba490ba71247898aa5d318865bef0503cb3e149518da5d638fecb0080',
    updated_at = NOW()
WHERE feature_id = 'US_NET_LIQUIDITY';

UPDATE fhq_macro.feature_registry SET
    status = 'ACTIVE',
    ios005_tested = true,
    ios005_p_value = 0.035,
    ios005_test_date = NOW(),
    ios005_evidence_hash = 'b602acdba490ba71247898aa5d318865bef0503cb3e149518da5d638fecb0080',
    updated_at = NOW()
WHERE feature_id = 'FED_TOTAL_ASSETS';

UPDATE fhq_macro.feature_registry SET
    status = 'REJECTED',
    ios005_tested = true,
    ios005_p_value = 0.216,
    ios005_test_date = NOW(),
    ios005_evidence_hash = 'b602acdba490ba71247898aa5d318865bef0503cb3e149518da5d638fecb0080',
    updated_at = NOW()
WHERE feature_id = 'US_TGA_BALANCE';

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
    'fhq_graph.nodes, fhq_graph.edges',
    'SCHEMA',
    'STIG',
    NOW(),
    'APPROVED',
    'Promoted US_NET_LIQUIDITY (GOLDEN, p=0.037) and FED_TOTAL_ASSETS (SIGNIFICANT, p=0.035) to Alpha Graph. G3 evidence hash: b602acdba490ba71247898aa5d318865bef0503cb3e149518da5d638fecb0080',
    false,
    false,
    'HC-ALPHA-GRAPH-049'
);

COMMIT;

-- ============================================================
-- Verification queries
-- ============================================================

SELECT 'NODES' as type, node_id, ios005_validated, status
FROM fhq_graph.nodes
WHERE node_type = 'MACRO'
ORDER BY node_id;

SELECT 'EDGES' as type, edge_id, from_node_id, to_node_id, p_value, status
FROM fhq_graph.edges
WHERE status IN ('GOLDEN', 'SIGNIFICANT')
ORDER BY p_value;

SELECT feature_id, status, ios005_p_value
FROM fhq_macro.feature_registry
WHERE cluster = 'LIQUIDITY'
ORDER BY ios005_p_value NULLS LAST;
