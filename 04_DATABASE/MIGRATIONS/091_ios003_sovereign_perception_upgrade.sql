-- ============================================================================
-- MIGRATION 091: IoS-003 Sovereign Perception Upgrade
-- ============================================================================
-- Authority: CEO Directive - SOVEREIGN PERCEPTION UPGRADE
-- Reference: ADR-017 (MIT Quad Protocol), ADR-013 (Truth Architecture)
-- Generated: 2025-12-08
--
-- PURPOSE:
--   Upgrade IoS-003 from Technical Perception to Sovereign Perception by:
--   - Adding CRIO audit fields to fhq_perception.regime_daily
--   - Enabling LIDS-verified macro causality integration
--   - Supporting full ADR-017 Truth -> Perception -> Allocation chain
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Add CRIO Audit Fields to regime_daily
-- ============================================================================

ALTER TABLE fhq_perception.regime_daily
ADD COLUMN IF NOT EXISTS crio_fragility_score NUMERIC(5,4),
ADD COLUMN IF NOT EXISTS crio_dominant_driver TEXT,
ADD COLUMN IF NOT EXISTS quad_hash VARCHAR(16),
ADD COLUMN IF NOT EXISTS regime_modifier_applied BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS crio_insight_id UUID;

COMMENT ON COLUMN fhq_perception.regime_daily.crio_fragility_score IS
'Snapshotted CRIO fragility signal at perception time. ADR-017 Truth Architecture.';

COMMENT ON COLUMN fhq_perception.regime_daily.crio_dominant_driver IS
'Macro explanation driver from CRIO insight (LIQUIDITY, CREDIT, VOLATILITY, etc.)';

COMMENT ON COLUMN fhq_perception.regime_daily.quad_hash IS
'Canonical MIT-Quad lineage hash for governance audit trail. ADR-017 Section 6.';

COMMENT ON COLUMN fhq_perception.regime_daily.regime_modifier_applied IS
'TRUE if CRIO causality altered the technical regime classification.';

COMMENT ON COLUMN fhq_perception.regime_daily.crio_insight_id IS
'Reference to the LIDS-verified CRIO insight that informed this perception.';


-- ============================================================================
-- SECTION 2: Create Index for CRIO-modified Regimes
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_regime_daily_modifier_applied
    ON fhq_perception.regime_daily(regime_modifier_applied, timestamp DESC)
    WHERE regime_modifier_applied = TRUE;

CREATE INDEX IF NOT EXISTS idx_regime_daily_quad_hash
    ON fhq_perception.regime_daily(quad_hash)
    WHERE quad_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_regime_daily_crio_insight
    ON fhq_perception.regime_daily(crio_insight_id)
    WHERE crio_insight_id IS NOT NULL;


-- ============================================================================
-- SECTION 3: Create Sovereign Regime Modifier Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_perception.apply_crio_regime_modifier(
    p_technical_regime TEXT,
    p_fragility_score NUMERIC,
    p_dominant_driver TEXT
)
RETURNS TABLE (
    sovereign_regime TEXT,
    modifier_applied BOOLEAN,
    modifier_reason TEXT
) AS $$
BEGIN
    -- CRIO Modifier Rules per CEO Directive
    -- Applied in order of precedence

    -- Rule 1: High fragility override
    IF p_fragility_score > 0.80 THEN
        RETURN QUERY SELECT
            'STRONG_BEAR'::TEXT,
            TRUE,
            'HIGH_FRAGILITY_OVERRIDE: fragility_score ' || p_fragility_score || ' > 0.80';
        RETURN;
    END IF;

    -- Rule 2: Liquidity contraction cap
    IF p_fragility_score > 0.60 AND p_dominant_driver = 'LIQUIDITY_CONTRACTION' THEN
        IF p_technical_regime IN ('STRONG_BULL', 'BULL', 'RANGE_UP', 'PARABOLIC') THEN
            RETURN QUERY SELECT
                'NEUTRAL'::TEXT,
                TRUE,
                'LIQUIDITY_CONTRACTION_CAP: fragility ' || p_fragility_score || ' + LIQUIDITY_CONTRACTION -> max NEUTRAL';
            RETURN;
        END IF;
    END IF;

    -- Rule 3: Liquidity expansion allow strong bull
    IF p_fragility_score < 0.40 AND p_dominant_driver = 'LIQUIDITY_EXPANSION' THEN
        IF p_technical_regime IN ('BULL', 'RANGE_UP') THEN
            RETURN QUERY SELECT
                'STRONG_BULL'::TEXT,
                TRUE,
                'LIQUIDITY_EXPANSION_BOOST: fragility ' || p_fragility_score || ' + LIQUIDITY_EXPANSION -> STRONG_BULL';
            RETURN;
        END IF;
    END IF;

    -- Default: Preserve technical classification
    RETURN QUERY SELECT
        p_technical_regime,
        FALSE,
        'TECHNICAL_PRESERVED: No CRIO modifier triggered';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_perception.apply_crio_regime_modifier IS
'Applies CRIO modifier rules to technical regime classification. CEO Directive - Sovereign Perception.
Rules: (1) fragility>0.80 -> STRONG_BEAR, (2) fragility>0.60+LIQUIDITY_CONTRACTION -> cap NEUTRAL,
(3) fragility<0.40+LIQUIDITY_EXPANSION -> allow STRONG_BULL, (4) else preserve technical.';


-- ============================================================================
-- SECTION 4: Create View for Sovereign Perception State
-- ============================================================================

CREATE OR REPLACE VIEW fhq_perception.sovereign_regime_state AS
SELECT
    rd.asset_id,
    rd.timestamp,
    rd.regime_classification AS technical_regime,
    COALESCE(
        (SELECT sovereign_regime FROM fhq_perception.apply_crio_regime_modifier(
            rd.regime_classification,
            COALESCE(rd.crio_fragility_score, 0.5),
            COALESCE(rd.crio_dominant_driver, 'NEUTRAL')
        )),
        rd.regime_classification
    ) AS sovereign_regime,
    rd.regime_modifier_applied,
    rd.crio_fragility_score,
    rd.crio_dominant_driver,
    rd.quad_hash,
    rd.regime_confidence,
    rd.consecutive_confirms,
    rd.regime_stability_flag,
    rd.created_at
FROM fhq_perception.regime_daily rd;

COMMENT ON VIEW fhq_perception.sovereign_regime_state IS
'Unified view of sovereign perception state combining technical + CRIO causality. ADR-017 Truth Architecture.';


-- ============================================================================
-- SECTION 5: Log Migration
-- ============================================================================

INSERT INTO fhq_meta.ios_audit_log (
    audit_id,
    ios_id,
    event_type,
    event_timestamp,
    actor,
    gate_level,
    event_data,
    evidence_hash
) VALUES (
    gen_random_uuid(),
    'IoS-003',
    'SOVEREIGN_PERCEPTION_UPGRADE',
    NOW(),
    'STIG',
    'G2',
    jsonb_build_object(
        'migration', '091_ios003_sovereign_perception_upgrade',
        'authority', 'CEO Directive - Sovereign Perception',
        'columns_added', ARRAY['crio_fragility_score', 'crio_dominant_driver', 'quad_hash', 'regime_modifier_applied', 'crio_insight_id'],
        'functions_created', ARRAY['fhq_perception.apply_crio_regime_modifier'],
        'views_created', ARRAY['fhq_perception.sovereign_regime_state'],
        'adr_reference', 'ADR-017 Section 6',
        'timestamp', NOW()
    ),
    encode(sha256('091_ios003_sovereign_perception_upgrade'::bytea), 'hex')::VARCHAR(16)
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    -- Verify CRIO audit columns exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_perception'
        AND table_name = 'regime_daily'
        AND column_name = 'crio_fragility_score'
    ) THEN
        RAISE EXCEPTION 'crio_fragility_score column not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_perception'
        AND table_name = 'regime_daily'
        AND column_name = 'quad_hash'
    ) THEN
        RAISE EXCEPTION 'quad_hash column not created';
    END IF;

    -- Verify modifier function
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.routines
        WHERE routine_schema = 'fhq_perception'
        AND routine_name = 'apply_crio_regime_modifier'
    ) THEN
        RAISE EXCEPTION 'apply_crio_regime_modifier function not created';
    END IF;

    RAISE NOTICE 'Migration 091 completed successfully';
    RAISE NOTICE 'IoS-003 Sovereign Perception Upgrade ready';
END $$;
