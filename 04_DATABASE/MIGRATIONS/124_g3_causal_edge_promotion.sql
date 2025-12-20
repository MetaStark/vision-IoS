-- ============================================================================
-- Migration 124: G3 Causal Edge Promotion
-- CEO DIRECTIVE: G3 CAUSAL EDGE INTEGRATION (NO EXECUTION ENABLEMENT)
-- ============================================================================
-- Authority: CEO via STIG (CTO) per EC-003
-- ADR References: ADR-013 (Canonical), ADR-017 (MIT Quad), ADR-018 (ASRP)
-- Classification: G3 - AUDIT GATE (no G4 activation)
-- ============================================================================
-- CONSTRAINT: Freeze Runtime - No CEIO activation, No DEFCON change, No ACI autonomy
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART A: Promote edges with confidence >= 0.85 to canonical
-- ============================================================================

UPDATE vision_signals.alpha_graph_edges
SET is_causal_edge = TRUE
WHERE confidence >= 0.85
  AND is_active = TRUE
  AND is_causal_edge = FALSE;

-- ============================================================================
-- PART B: Update graph_state tracking
-- ============================================================================

-- Create graph_state record if it doesn't exist
INSERT INTO vision_signals.alpha_graph_nodes (
    node_id, node_type, display_name, data_source, is_active, created_at
)
SELECT
    'G3_CANONICAL_PROMOTION_20251211',
    'GRAPH_STATE',
    'G3 Causal Edge Promotion - 48hr Window Complete',
    'MIGRATION_124',
    true,
    NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM vision_signals.alpha_graph_nodes
    WHERE node_id = 'G3_CANONICAL_PROMOTION_20251211'
);

-- ============================================================================
-- PART C: Regenerate quad_hash (ADR-017)
-- ============================================================================

-- Generate new quad hash based on promoted edges
DO $$
DECLARE
    v_edge_count INTEGER;
    v_avg_confidence NUMERIC;
    v_quad_hash TEXT;
BEGIN
    -- Count promoted edges
    SELECT COUNT(*), AVG(confidence::NUMERIC)
    INTO v_edge_count, v_avg_confidence
    FROM vision_signals.alpha_graph_edges
    WHERE is_causal_edge = TRUE;

    -- Generate quad hash
    v_quad_hash := 'QUAD-G3-' ||
                   TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS') || '-' ||
                   MD5(v_edge_count::TEXT || '-' || v_avg_confidence::TEXT);

    RAISE NOTICE 'G3 PROMOTION COMPLETE';
    RAISE NOTICE '  Edges promoted: %', v_edge_count;
    RAISE NOTICE '  Average confidence: %', ROUND(v_avg_confidence, 4);
    RAISE NOTICE '  Quad hash: %', v_quad_hash;
END $$;

-- ============================================================================
-- PART D: Governance Logging (ADR-002)
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
    'G3_CAUSAL_EDGE_PROMOTION',
    'vision_signals.alpha_graph_edges',
    'TABLE',
    'STIG',
    NOW(),
    'APPROVED',
    E'CEO DIRECTIVE: G3 Causal Edge Integration (NO EXECUTION ENABLEMENT)\n\n' ||
    E'Actions performed:\n' ||
    E'1. Promoted all edges with confidence >= 0.85 to is_causal_edge = TRUE\n' ||
    E'2. Updated graph_state tracking\n' ||
    E'3. Regenerated quad_hash (ADR-017)\n\n' ||
    E'Constraints enforced:\n' ||
    E'- NO CEIO activation\n' ||
    E'- NO DEFCON change to GREEN\n' ||
    E'- NO ACI autonomy lift\n' ||
    E'- Only passive runtime-tasks allowed\n\n' ||
    E'48-hour observation window: COMPLETED\n' ||
    E'Classification: G3 AUDIT GATE (not G4)',
    false,
    'MIG-124-G3-PROMOTION-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
);

COMMIT;

-- ============================================================================
-- Migration 124 Complete - G3 AUDIT GATE ONLY
-- NO EXECUTION ENABLEMENT
-- ============================================================================
