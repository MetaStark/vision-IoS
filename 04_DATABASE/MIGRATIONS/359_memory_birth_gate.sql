-- ============================================================================
-- MIGRATION 359: MEMORY BIRTH GATE
-- ============================================================================
-- Authority: CEO-DIR-2026-128 (WEEKLY RESET & LEARNING ACTIVATION)
-- Purpose: Enforce "No Memory, No Birth" rule for hypothesis generation
-- Executor: STIG (EC-003)
-- Date: 2026-02-08
--
-- Root Cause:
--   The system has 8,542 rejected hypotheses but generators never query them.
--   prior_hypotheses_count is NULL for ALL 1,286 hypotheses.
--   FSS = -1.265 (worse than random) because generators operate as Day 1.
--
-- Solution:
--   1. Create check_prior_failures() function that queries memory before birth
--   2. Function returns prior_count, similar failures, and memory citation
--   3. Generators must call this BEFORE INSERT and populate prior_hypotheses_count
--
-- Scope:
--   - CREATE FUNCTION fhq_learning.check_prior_failures()
--   - CREATE TABLE fhq_learning.hypothesis_birth_blocks (audit log)
--   - No schema changes to hypothesis_canon (prior_hypotheses_count already exists)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. CREATE HYPOTHESIS BIRTH BLOCKS TABLE (Audit Log)
-- ============================================================================
-- Tracks hypotheses that were blocked due to memory constraints.

CREATE TABLE IF NOT EXISTS fhq_learning.hypothesis_birth_blocks (
    block_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blocked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    block_reason TEXT NOT NULL,  -- 'MEMORY_BLOCK', 'EXACT_DUPLICATE', 'SIMILARITY_BLOCK'
    generator_id TEXT NOT NULL,
    proposed_semantic_hash TEXT,
    proposed_causal_mechanism TEXT,
    proposed_asset_universe TEXT[],
    prior_failures_count INTEGER NOT NULL DEFAULT 0,
    similar_failures JSONB,
    blocking_hypotheses JSONB,  -- Array of {hypothesis_code, similarity_score, annihilation_reason}
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_birth_blocks_generator
ON fhq_learning.hypothesis_birth_blocks(generator_id, blocked_at);

CREATE INDEX IF NOT EXISTS idx_birth_blocks_reason
ON fhq_learning.hypothesis_birth_blocks(block_reason);

COMMENT ON TABLE fhq_learning.hypothesis_birth_blocks IS
'Audit log of hypotheses blocked at birth due to memory constraints. CEO-DIR-2026-128.';

-- ============================================================================
-- 2. CREATE check_prior_failures FUNCTION
-- ============================================================================
-- This function is called by generators BEFORE hypothesis INSERT.
-- Returns memory context that generators must use to decide birth/block.

CREATE OR REPLACE FUNCTION fhq_learning.check_prior_failures(
    p_causal_mechanism TEXT,
    p_semantic_hash TEXT,
    p_asset_universe TEXT[],
    p_generator_id TEXT DEFAULT 'UNKNOWN'
)
RETURNS TABLE (
    prior_count INTEGER,
    exact_duplicate_exists BOOLEAN,
    similar_failures JSONB,
    memory_citation TEXT,
    should_block BOOLEAN,
    block_reason TEXT
) AS $$
DECLARE
    v_exact_count INTEGER := 0;
    v_similar_failures JSONB := '[]'::JSONB;
    v_rejected_count INTEGER := 0;
    v_asset_overlap_failures JSONB := '[]'::JSONB;
    v_total_prior INTEGER := 0;
    v_memory_citation TEXT := '';
    v_should_block BOOLEAN := FALSE;
    v_block_reason TEXT := NULL;
BEGIN
    -- ========================================================================
    -- STEP 1: Check exact semantic hash duplicates
    -- ========================================================================
    SELECT COUNT(*) INTO v_exact_count
    FROM fhq_learning.hypothesis_canon hc
    WHERE hc.semantic_hash = p_semantic_hash
      AND hc.status IN ('ACTIVE', 'DRAFT', 'WEAKENED');

    IF v_exact_count > 0 THEN
        v_should_block := TRUE;
        v_block_reason := 'EXACT_DUPLICATE';
        v_memory_citation := 'Exact semantic hash match exists in active hypotheses';
    END IF;

    -- ========================================================================
    -- STEP 2: Check falsified hypotheses with same semantic hash
    -- ========================================================================
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'hypothesis_code', hc.hypothesis_code,
        'annihilation_reason', hc.annihilation_reason,
        'death_timestamp', hc.death_timestamp,
        'time_to_falsification_hours', hc.time_to_falsification_hours
    )), '[]'::JSONB) INTO v_similar_failures
    FROM fhq_learning.hypothesis_canon hc
    WHERE hc.semantic_hash = p_semantic_hash
      AND hc.status IN ('FALSIFIED', 'ANNIHILATED');

    -- ========================================================================
    -- STEP 3: Check rejected_hypotheses by asset overlap
    -- ========================================================================
    IF p_asset_universe IS NOT NULL AND array_length(p_asset_universe, 1) > 0 THEN
        SELECT COUNT(*) INTO v_rejected_count
        FROM fhq_research.rejected_hypotheses rh
        WHERE rh.target_asset = ANY(p_asset_universe)
          AND rh.rejection_timestamp > NOW() - INTERVAL '30 days';

        -- Get sample of recent rejections for same assets
        SELECT COALESCE(jsonb_agg(jsonb_build_object(
            'target_asset', rh.target_asset,
            'rejection_reason', rh.rejection_reason,
            'rejection_timestamp', rh.rejection_timestamp,
            'eqs_score', rh.eqs_total_score
        )), '[]'::JSONB) INTO v_asset_overlap_failures
        FROM (
            SELECT *
            FROM fhq_research.rejected_hypotheses
            WHERE target_asset = ANY(p_asset_universe)
              AND rejection_timestamp > NOW() - INTERVAL '30 days'
            ORDER BY rejection_timestamp DESC
            LIMIT 5
        ) rh;
    END IF;

    -- ========================================================================
    -- STEP 4: Check falsified hypotheses with asset overlap
    -- ========================================================================
    -- Count hypotheses that failed for similar assets
    SELECT COUNT(*) INTO v_total_prior
    FROM fhq_learning.hypothesis_canon hc
    WHERE hc.status IN ('FALSIFIED', 'ANNIHILATED')
      AND hc.death_timestamp > NOW() - INTERVAL '30 days'
      AND (
          hc.semantic_hash = p_semantic_hash
          OR (p_asset_universe IS NOT NULL AND hc.asset_universe && p_asset_universe)
      );

    -- Add rejected_hypotheses count
    v_total_prior := v_total_prior + v_rejected_count;

    -- ========================================================================
    -- STEP 5: Build memory citation
    -- ========================================================================
    IF v_total_prior > 0 THEN
        v_memory_citation := format(
            'Prior failures: %s (falsified: %s, rejected: %s). Similar failures: %s. Assets: %s',
            v_total_prior,
            jsonb_array_length(v_similar_failures),
            v_rejected_count,
            LEFT(v_similar_failures::TEXT, 200),
            COALESCE(array_to_string(p_asset_universe, ','), 'NULL')
        );
    END IF;

    -- ========================================================================
    -- STEP 6: Apply blocking logic (5+ prior failures = block)
    -- ========================================================================
    IF NOT v_should_block AND v_total_prior >= 5 THEN
        v_should_block := TRUE;
        v_block_reason := 'MEMORY_BLOCK';
        v_memory_citation := v_memory_citation || '. BLOCKED: >= 5 prior failures in 30d window.';
    END IF;

    -- ========================================================================
    -- STEP 7: Return results
    -- ========================================================================
    RETURN QUERY SELECT
        v_total_prior::INTEGER,
        (v_exact_count > 0)::BOOLEAN,
        (v_similar_failures || v_asset_overlap_failures)::JSONB,
        v_memory_citation::TEXT,
        v_should_block::BOOLEAN,
        v_block_reason::TEXT;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION fhq_learning.check_prior_failures IS
'CEO-DIR-2026-128: Memory birth gate. Called BEFORE hypothesis INSERT to check prior failures. Returns prior_count, similar_failures, and memory_citation. Blocks if >= 5 prior failures exist.';

-- ============================================================================
-- 3. CREATE UNIFIED FAILURE MEMORY VIEW
-- ============================================================================
-- Combines hypothesis_canon failures with rejected_hypotheses for unified queries.

CREATE OR REPLACE VIEW fhq_learning.failure_memory AS
SELECT
    'hypothesis_canon' AS source_table,
    hypothesis_code AS identifier,
    causal_mechanism,
    semantic_hash,
    asset_universe,
    annihilation_reason AS failure_reason,
    death_timestamp AS failure_timestamp,
    time_to_falsification_hours AS time_to_failure_hours
FROM fhq_learning.hypothesis_canon
WHERE status IN ('FALSIFIED', 'ANNIHILATED')
UNION ALL
SELECT
    'rejected_hypotheses' AS source_table,
    rejection_id::TEXT AS identifier,
    NULL AS causal_mechanism,
    raw_hypothesis_hash AS semantic_hash,
    ARRAY[target_asset] AS asset_universe,
    rejection_reason AS failure_reason,
    rejection_timestamp AS failure_timestamp,
    NULL AS time_to_failure_hours
FROM fhq_research.rejected_hypotheses;

COMMENT ON VIEW fhq_learning.failure_memory IS
'CEO-DIR-2026-128: Unified memory of all hypothesis failures. Combines hypothesis_canon deaths and rejected_hypotheses for cross-generator memory sharing.';

-- ============================================================================
-- 4. LOG MIGRATION IN DEFCON TRANSITIONS
-- ============================================================================

INSERT INTO fhq_governance.defcon_transitions (
    transition_id,
    from_level,
    to_level,
    transition_type,
    reason,
    authorized_by,
    authorization_method,
    evidence_bundle,
    transition_timestamp,
    created_at
) VALUES (
    gen_random_uuid(),
    'ORANGE'::defcon_level,
    'ORANGE'::defcon_level,
    'RESET',
    'CEO-DIR-2026-128 DAY40: Memory birth gate installed. Function check_prior_failures() created. '
    || 'Generators must now query memory before hypothesis birth.',
    'STIG',
    'CEO',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-128',
        'day', 'DAY40',
        'action', 'MEMORY_BIRTH_GATE_INSTALLATION',
        'function_created', 'fhq_learning.check_prior_failures',
        'table_created', 'fhq_learning.hypothesis_birth_blocks',
        'view_created', 'fhq_learning.failure_memory',
        'prior_failures_threshold', 5,
        'memory_window_days', 30
    ),
    NOW(),
    NOW()
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================
--
-- 1. Test the function:
-- SELECT * FROM fhq_learning.check_prior_failures(
--     'funding_extreme -> position_crowding -> forced_unwind',
--     'test_hash_123',
--     ARRAY['BTC-USD', 'ETH-USD'],
--     'TEST_GENERATOR'
-- );
--
-- 2. Verify failure_memory view:
-- SELECT source_table, COUNT(*), MIN(failure_timestamp), MAX(failure_timestamp)
-- FROM fhq_learning.failure_memory
-- GROUP BY source_table;
--
-- 3. Check hypothesis_birth_blocks table:
-- SELECT * FROM fhq_learning.hypothesis_birth_blocks LIMIT 10;
-- ============================================================================
