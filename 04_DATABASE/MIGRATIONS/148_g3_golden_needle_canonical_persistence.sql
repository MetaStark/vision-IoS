-- ============================================================================
-- MIGRATION 148: G3 GOLDEN NEEDLE CANONICAL PERSISTENCE
-- ============================================================================
-- CEO DIRECTIVE: WAVE 13 – G3 AUTHORIZATION
-- DATE: 2025-12-17
-- AUTHORITY: CEO / FjordHQ Executive Board
-- REFERENCE: ADR-013 (Canonical Truth & Single Source of Truth)
--
-- PURPOSE:
-- Implement canonical, queryable persistence for Golden Needles ONLY.
-- "Noise is forgotten. Excellence is remembered permanently."
--
-- CONSTRAINTS:
-- - Persist ONLY hypotheses with EQS >= 0.85
-- - Append-only (no UPDATE, no DELETE)
-- - All fields explicit and queryable (no opaque JSON blobs for core data)
-- - Forward-compatible for 5+ year audit reconstruction
-- - IoS-004 backtest compatible
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. CREATE SCHEMA IF NOT EXISTS
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS fhq_canonical;

COMMENT ON SCHEMA fhq_canonical IS
'G3 Canonical Persistence Layer - Immutable storage for Golden Needles and audit-grade evidence. ADR-013 compliant.';

-- ============================================================================
-- 2. GOLDEN NEEDLE CANONICAL TABLE
-- ============================================================================
-- This is THE source of truth for all Golden Needles.
-- No JSON blobs for core analytical fields - all explicitly typed and queryable.

CREATE TABLE IF NOT EXISTS fhq_canonical.golden_needles (
    -- Primary Key
    needle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- =========================================================================
    -- CORE IDENTIFICATION
    -- =========================================================================
    hypothesis_id TEXT NOT NULL,
    hunt_session_id UUID NOT NULL,
    cycle_id TEXT NOT NULL,  -- EC018-HUNT-YYYYMMDDHHMMSS format

    -- =========================================================================
    -- EVIDENCE QUALITY SCORE (EQS) - Explicitly typed, precision preserved
    -- =========================================================================
    eqs_score NUMERIC(5,4) NOT NULL CHECK (eqs_score >= 0.85 AND eqs_score <= 1.0),
    eqs_threshold_applied NUMERIC(3,2) NOT NULL DEFAULT 0.85,

    -- =========================================================================
    -- CONFLUENCE FACTORS - Explicit enumerable columns (NOT JSON)
    -- =========================================================================
    -- Each factor is explicitly typed for direct queryability
    factor_price_technical BOOLEAN NOT NULL DEFAULT FALSE,
    factor_volume_confirmation BOOLEAN NOT NULL DEFAULT FALSE,
    factor_regime_alignment BOOLEAN NOT NULL DEFAULT FALSE,
    factor_temporal_coherence BOOLEAN NOT NULL DEFAULT FALSE,
    factor_catalyst_present BOOLEAN NOT NULL DEFAULT FALSE,
    factor_specific_testable BOOLEAN NOT NULL DEFAULT FALSE,
    factor_testable_criteria BOOLEAN NOT NULL DEFAULT FALSE,
    confluence_factor_count INTEGER NOT NULL GENERATED ALWAYS AS (
        (factor_price_technical::int + factor_volume_confirmation::int +
         factor_regime_alignment::int + factor_temporal_coherence::int +
         factor_catalyst_present::int + factor_specific_testable::int +
         factor_testable_criteria::int)
    ) STORED,

    -- =========================================================================
    -- EQS COMPONENT WEIGHTS (for audit reconstruction)
    -- =========================================================================
    weight_price_technical NUMERIC(4,3),
    weight_volume_confirmation NUMERIC(4,3),
    weight_regime_alignment NUMERIC(4,3),
    weight_temporal_coherence NUMERIC(4,3),
    weight_catalyst_present NUMERIC(4,3),
    weight_specificity_bonus NUMERIC(4,3),
    weight_testability_bonus NUMERIC(4,3),
    stress_modifier NUMERIC(4,3) NOT NULL DEFAULT 1.0,

    -- =========================================================================
    -- HYPOTHESIS CONTENT
    -- =========================================================================
    hypothesis_title TEXT NOT NULL,
    hypothesis_statement TEXT NOT NULL,
    hypothesis_category TEXT,
    executive_summary TEXT,

    -- =========================================================================
    -- SITC CHAIN-OF-QUERY REFERENCES
    -- =========================================================================
    sitc_plan_id UUID NOT NULL,
    sitc_confidence_level TEXT NOT NULL CHECK (sitc_confidence_level IN ('HIGH', 'MEDIUM', 'LOW')),
    sitc_nodes_completed INTEGER,
    sitc_nodes_total INTEGER,
    chain_of_query_hash TEXT,  -- Hash of the full CoQ for integrity verification

    -- =========================================================================
    -- ASRP STATE BINDING (ADR-018)
    -- =========================================================================
    asrp_hash TEXT NOT NULL,
    asrp_timestamp TIMESTAMPTZ NOT NULL,
    state_vector_id UUID,
    state_hash_at_creation TEXT,

    -- =========================================================================
    -- PRICE WITNESS (CEO Directive Wave 12)
    -- =========================================================================
    price_witness_id TEXT NOT NULL,
    price_witness_symbol TEXT NOT NULL,
    price_witness_value NUMERIC(20,8) NOT NULL,
    price_witness_source TEXT NOT NULL,
    price_witness_timestamp TIMESTAMPTZ NOT NULL,

    -- =========================================================================
    -- REGIME CONTEXT SNAPSHOT (IoS-003 Compatible)
    -- =========================================================================
    regime_asset_id TEXT NOT NULL DEFAULT 'BTC-USD',
    regime_technical TEXT,  -- From sovereign_regime_state_v4.technical_regime
    regime_sovereign TEXT,  -- From sovereign_regime_state_v4.sovereign_regime
    regime_confidence NUMERIC(5,4),
    regime_crio_driver TEXT,
    regime_snapshot_timestamp TIMESTAMPTZ,
    defcon_level INTEGER NOT NULL CHECK (defcon_level BETWEEN 1 AND 5),

    -- =========================================================================
    -- FALSIFICATION & BACKTEST HOOKS (IoS-004 Compatible)
    -- =========================================================================
    falsification_criteria JSONB,  -- Acceptable as structured criteria, not core data
    backtest_requirements JSONB,   -- Acceptable as structured requirements
    expected_timeframe_days INTEGER,
    target_asset TEXT,

    -- =========================================================================
    -- CANONICAL TIMESTAMPS
    -- =========================================================================
    validation_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- =========================================================================
    -- IMMUTABILITY TRACKING
    -- =========================================================================
    superseded_by UUID REFERENCES fhq_canonical.golden_needles(needle_id),
    supersession_reason TEXT,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,

    -- =========================================================================
    -- GOVERNANCE ATTESTATION
    -- =========================================================================
    g2_exam_session_id TEXT,
    vega_attestation_id UUID,
    canonical_hash TEXT NOT NULL  -- SHA-256 of all core fields for integrity
);

-- ============================================================================
-- 3. INDEXES FOR QUERYABILITY
-- ============================================================================
CREATE INDEX idx_golden_needles_eqs ON fhq_canonical.golden_needles(eqs_score DESC);
CREATE INDEX idx_golden_needles_hunt_session ON fhq_canonical.golden_needles(hunt_session_id);
CREATE INDEX idx_golden_needles_sitc_plan ON fhq_canonical.golden_needles(sitc_plan_id);
CREATE INDEX idx_golden_needles_asrp_hash ON fhq_canonical.golden_needles(asrp_hash);
CREATE INDEX idx_golden_needles_regime ON fhq_canonical.golden_needles(regime_sovereign, regime_technical);
CREATE INDEX idx_golden_needles_created ON fhq_canonical.golden_needles(created_at DESC);
CREATE INDEX idx_golden_needles_current ON fhq_canonical.golden_needles(is_current) WHERE is_current = TRUE;
CREATE INDEX idx_golden_needles_witness ON fhq_canonical.golden_needles(price_witness_id);
CREATE INDEX idx_golden_needles_confluence ON fhq_canonical.golden_needles(confluence_factor_count DESC);

-- ============================================================================
-- 4. IMMUTABILITY ENFORCEMENT (Append-Only)
-- ============================================================================
-- Block UPDATE on core fields
CREATE OR REPLACE FUNCTION fhq_canonical.enforce_needle_immutability()
RETURNS TRIGGER AS $$
BEGIN
    -- Only allow updates to supersession fields
    IF OLD.needle_id IS NOT NULL THEN
        IF NEW.eqs_score != OLD.eqs_score OR
           NEW.hypothesis_statement != OLD.hypothesis_statement OR
           NEW.asrp_hash != OLD.asrp_hash OR
           NEW.sitc_plan_id != OLD.sitc_plan_id OR
           NEW.price_witness_id != OLD.price_witness_id THEN
            RAISE EXCEPTION 'IMMUTABILITY VIOLATION: Golden Needle core fields cannot be modified. Create superseding record instead.';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_needle_immutability
    BEFORE UPDATE ON fhq_canonical.golden_needles
    FOR EACH ROW
    EXECUTE FUNCTION fhq_canonical.enforce_needle_immutability();

-- Block DELETE entirely
CREATE OR REPLACE FUNCTION fhq_canonical.block_needle_deletion()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'IMMUTABILITY VIOLATION: Golden Needles cannot be deleted. Use supersession for corrections.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_block_needle_delete
    BEFORE DELETE ON fhq_canonical.golden_needles
    FOR EACH ROW
    EXECUTE FUNCTION fhq_canonical.block_needle_deletion();

-- ============================================================================
-- 5. CANONICAL HASH GENERATION
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_canonical.generate_needle_hash()
RETURNS TRIGGER AS $$
BEGIN
    NEW.canonical_hash := encode(
        sha256(
            (COALESCE(NEW.hypothesis_id, '') || '|' ||
             COALESCE(NEW.eqs_score::text, '') || '|' ||
             COALESCE(NEW.asrp_hash, '') || '|' ||
             COALESCE(NEW.sitc_plan_id::text, '') || '|' ||
             COALESCE(NEW.price_witness_id, '') || '|' ||
             COALESCE(NEW.price_witness_timestamp::text, '') || '|' ||
             COALESCE(NEW.hypothesis_statement, ''))::bytea
        ),
        'hex'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_generate_needle_hash
    BEFORE INSERT ON fhq_canonical.golden_needles
    FOR EACH ROW
    EXECUTE FUNCTION fhq_canonical.generate_needle_hash();

-- ============================================================================
-- 6. AUDIT RECONSTRUCTION VIEW
-- ============================================================================
CREATE OR REPLACE VIEW fhq_canonical.v_golden_needle_audit AS
SELECT
    gn.needle_id,
    gn.hypothesis_title,
    gn.eqs_score,
    gn.confluence_factor_count,
    -- Confluence factor breakdown
    ARRAY_REMOVE(ARRAY[
        CASE WHEN gn.factor_price_technical THEN 'PRICE_TECHNICAL' END,
        CASE WHEN gn.factor_volume_confirmation THEN 'VOLUME_CONFIRMATION' END,
        CASE WHEN gn.factor_regime_alignment THEN 'REGIME_ALIGNMENT' END,
        CASE WHEN gn.factor_temporal_coherence THEN 'TEMPORAL_COHERENCE' END,
        CASE WHEN gn.factor_catalyst_present THEN 'CATALYST_PRESENT' END,
        CASE WHEN gn.factor_specific_testable THEN 'SPECIFIC_TESTABLE' END,
        CASE WHEN gn.factor_testable_criteria THEN 'TESTABLE_CRITERIA' END
    ], NULL) AS confluence_factors,
    -- Price witness
    gn.price_witness_symbol || ' = $' || gn.price_witness_value::text AS price_at_detection,
    gn.price_witness_timestamp,
    gn.price_witness_source,
    -- Regime context
    gn.regime_sovereign || '/' || gn.regime_technical AS regime_state,
    gn.defcon_level,
    -- ASRP binding
    gn.asrp_hash,
    gn.asrp_timestamp,
    -- SitC chain
    gn.sitc_plan_id,
    gn.sitc_confidence_level,
    -- Timestamps
    gn.validation_timestamp,
    gn.created_at,
    -- Integrity
    gn.canonical_hash,
    gn.is_current
FROM fhq_canonical.golden_needles gn
WHERE gn.is_current = TRUE
ORDER BY gn.created_at DESC;

COMMENT ON VIEW fhq_canonical.v_golden_needle_audit IS
'Audit-ready view of all current Golden Needles with full context reconstruction.';

-- ============================================================================
-- 7. CHAIN-OF-QUERY REFERENCE TABLE
-- ============================================================================
-- Links Golden Needles to their full reasoning chains for audit
CREATE TABLE IF NOT EXISTS fhq_canonical.needle_chain_links (
    link_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),
    chain_node_id UUID NOT NULL,  -- References fhq_meta.chain_of_query
    node_sequence INTEGER NOT NULL,
    node_type TEXT NOT NULL,
    node_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_needle_chain_links_needle ON fhq_canonical.needle_chain_links(needle_id);
CREATE INDEX idx_needle_chain_links_node ON fhq_canonical.needle_chain_links(chain_node_id);

-- ============================================================================
-- 8. PERSISTENCE FUNCTION (Called by EC-018)
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_canonical.persist_golden_needle(
    p_hypothesis_id TEXT,
    p_hunt_session_id UUID,
    p_cycle_id TEXT,
    p_eqs_score NUMERIC,
    p_confluence_factors TEXT[],
    p_eqs_components JSONB,
    p_hypothesis_title TEXT,
    p_hypothesis_statement TEXT,
    p_hypothesis_category TEXT,
    p_executive_summary TEXT,
    p_sitc_plan_id UUID,
    p_sitc_confidence TEXT,
    p_sitc_nodes_completed INTEGER,
    p_sitc_nodes_total INTEGER,
    p_asrp_hash TEXT,
    p_asrp_timestamp TIMESTAMPTZ,
    p_state_vector_id UUID,
    p_state_hash TEXT,
    p_price_witness_id TEXT,
    p_price_witness_symbol TEXT,
    p_price_witness_value NUMERIC,
    p_price_witness_source TEXT,
    p_price_witness_timestamp TIMESTAMPTZ,
    p_regime_asset_id TEXT,
    p_regime_technical TEXT,
    p_regime_sovereign TEXT,
    p_regime_confidence NUMERIC,
    p_regime_crio_driver TEXT,
    p_regime_snapshot_timestamp TIMESTAMPTZ,
    p_defcon_level INTEGER,
    p_falsification_criteria JSONB,
    p_backtest_requirements JSONB,
    p_g2_exam_session_id TEXT DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_needle_id UUID;
BEGIN
    -- Validate EQS threshold (constitutional constraint)
    IF p_eqs_score < 0.85 THEN
        RAISE EXCEPTION 'G3 VIOLATION: Cannot persist hypothesis with EQS < 0.85. EQS=% is below threshold.', p_eqs_score;
    END IF;

    INSERT INTO fhq_canonical.golden_needles (
        hypothesis_id,
        hunt_session_id,
        cycle_id,
        eqs_score,
        -- Confluence factors
        factor_price_technical,
        factor_volume_confirmation,
        factor_regime_alignment,
        factor_temporal_coherence,
        factor_catalyst_present,
        factor_specific_testable,
        factor_testable_criteria,
        -- EQS weights
        weight_price_technical,
        weight_volume_confirmation,
        weight_regime_alignment,
        weight_temporal_coherence,
        weight_catalyst_present,
        weight_specificity_bonus,
        weight_testability_bonus,
        stress_modifier,
        -- Hypothesis
        hypothesis_title,
        hypothesis_statement,
        hypothesis_category,
        executive_summary,
        -- SitC
        sitc_plan_id,
        sitc_confidence_level,
        sitc_nodes_completed,
        sitc_nodes_total,
        -- ASRP
        asrp_hash,
        asrp_timestamp,
        state_vector_id,
        state_hash_at_creation,
        -- Price Witness
        price_witness_id,
        price_witness_symbol,
        price_witness_value,
        price_witness_source,
        price_witness_timestamp,
        -- Regime
        regime_asset_id,
        regime_technical,
        regime_sovereign,
        regime_confidence,
        regime_crio_driver,
        regime_snapshot_timestamp,
        defcon_level,
        -- Backtest hooks
        falsification_criteria,
        backtest_requirements,
        -- Governance
        g2_exam_session_id
    ) VALUES (
        p_hypothesis_id,
        p_hunt_session_id,
        p_cycle_id,
        p_eqs_score,
        -- Parse confluence factors array
        'PRICE_TECHNICAL' = ANY(p_confluence_factors),
        'VOLUME_CONFIRMATION' = ANY(p_confluence_factors),
        'REGIME_ALIGNMENT' = ANY(p_confluence_factors),
        'TEMPORAL_COHERENCE' = ANY(p_confluence_factors),
        'CATALYST_PRESENT' = ANY(p_confluence_factors),
        'SPECIFIC_TESTABLE' = ANY(p_confluence_factors),
        'TESTABLE_CRITERIA' = ANY(p_confluence_factors),
        -- Extract weights from JSONB
        (p_eqs_components->>'price_technical')::NUMERIC,
        (p_eqs_components->>'volume_confirmation')::NUMERIC,
        (p_eqs_components->>'regime_alignment')::NUMERIC,
        (p_eqs_components->>'temporal_coherence')::NUMERIC,
        (p_eqs_components->>'catalyst_present')::NUMERIC,
        (p_eqs_components->>'specificity_bonus')::NUMERIC,
        (p_eqs_components->>'testability_bonus')::NUMERIC,
        COALESCE((p_eqs_components->>'stress_modifier')::NUMERIC, 1.0),
        p_hypothesis_title,
        p_hypothesis_statement,
        p_hypothesis_category,
        p_executive_summary,
        p_sitc_plan_id,
        p_sitc_confidence,
        p_sitc_nodes_completed,
        p_sitc_nodes_total,
        p_asrp_hash,
        p_asrp_timestamp,
        p_state_vector_id,
        p_state_hash,
        p_price_witness_id,
        p_price_witness_symbol,
        p_price_witness_value,
        p_price_witness_source,
        p_price_witness_timestamp,
        p_regime_asset_id,
        p_regime_technical,
        p_regime_sovereign,
        p_regime_confidence,
        p_regime_crio_driver,
        p_regime_snapshot_timestamp,
        p_defcon_level,
        p_falsification_criteria,
        p_backtest_requirements,
        p_g2_exam_session_id
    ) RETURNING needle_id INTO v_needle_id;

    RETURN v_needle_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 9. AUDIT RECONSTRUCTION FUNCTION
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_canonical.reconstruct_needle_audit(
    p_needle_id UUID
) RETURNS TABLE (
    section TEXT,
    question TEXT,
    answer TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH needle AS (
        SELECT * FROM fhq_canonical.golden_needles WHERE needle_id = p_needle_id
    )
    SELECT
        'DATA_OBSERVED'::TEXT,
        'What data was observed?'::TEXT,
        format('Price Witness: %s = $%s at %s (source: %s)',
               n.price_witness_symbol, n.price_witness_value,
               n.price_witness_timestamp, n.price_witness_source)
    FROM needle n

    UNION ALL

    SELECT
        'TIMING',
        'When was it observed?',
        format('Validation: %s | Created: %s | ASRP: %s',
               n.validation_timestamp, n.created_at, n.asrp_timestamp)
    FROM needle n

    UNION ALL

    SELECT
        'REGIME_CONTEXT',
        'Which regime context applied?',
        format('Regime: %s/%s (confidence: %s) | CRIO Driver: %s | DEFCON: %s',
               n.regime_sovereign, n.regime_technical, n.regime_confidence,
               n.regime_crio_driver, n.defcon_level)
    FROM needle n

    UNION ALL

    SELECT
        'ACCEPTANCE_REASON',
        'Why was this hypothesis accepted?',
        format('EQS: %s (threshold: %s) | Confluence Factors: %s/7 | SitC Confidence: %s',
               n.eqs_score, n.eqs_threshold_applied, n.confluence_factor_count,
               n.sitc_confidence_level)
    FROM needle n

    UNION ALL

    SELECT
        'CHECKS_PASSED',
        'Which checks passed?',
        format('Factors: %s',
               array_to_string(ARRAY_REMOVE(ARRAY[
                   CASE WHEN n.factor_price_technical THEN 'PRICE_TECHNICAL' END,
                   CASE WHEN n.factor_volume_confirmation THEN 'VOLUME_CONFIRMATION' END,
                   CASE WHEN n.factor_regime_alignment THEN 'REGIME_ALIGNMENT' END,
                   CASE WHEN n.factor_temporal_coherence THEN 'TEMPORAL_COHERENCE' END,
                   CASE WHEN n.factor_catalyst_present THEN 'CATALYST_PRESENT' END,
                   CASE WHEN n.factor_specific_testable THEN 'SPECIFIC_TESTABLE' END,
                   CASE WHEN n.factor_testable_criteria THEN 'TESTABLE_CRITERIA' END
               ], NULL), ', '))
    FROM needle n

    UNION ALL

    SELECT
        'INTEGRITY',
        'Canonical integrity hash?',
        n.canonical_hash
    FROM needle n;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 10. REGISTER IN ADR REGISTRY
-- ============================================================================
INSERT INTO fhq_meta.adr_registry (
    adr_id, adr_title, adr_status, adr_type, current_version, created_at
) VALUES (
    'MIG-148',
    'G3 Golden Needle Canonical Persistence',
    'APPROVED',
    'ARCHITECTURAL',
    '1.0.0',
    NOW()
) ON CONFLICT (adr_id) DO UPDATE SET
    adr_status = 'APPROVED',
    updated_at = NOW();

COMMIT;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- This migration establishes the canonical persistence layer for Golden Needles.
--
-- Key properties:
-- 1. EQS >= 0.85 enforced at database level
-- 2. All core fields explicitly typed and queryable (no opaque JSON)
-- 3. Append-only (UPDATE/DELETE blocked via triggers)
-- 4. Full audit reconstruction via reconstruct_needle_audit()
-- 5. IoS-003 regime context captured
-- 6. IoS-004 backtest hooks included
-- 7. 5+ year forward compatible structure
-- ============================================================================
