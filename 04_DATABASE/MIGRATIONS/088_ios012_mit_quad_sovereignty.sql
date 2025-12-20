-- ============================================================================
-- MIGRATION 088: IoS-012 MIT-Quad Sovereignty Integration
-- ============================================================================
-- Authority: CEO Directive - SOVEREIGN MACRO INTELLIGENCE LOOP ORDER C
-- Reference: ADR-017 (MIT Quad Protocol), IoS-012 Execution Engine
-- Generated: 2025-12-08
--
-- PURPOSE:
--   Connect IoS-012 Paper Trading to MIT-Quad sovereignty:
--   - Add quad_hash to fhq_execution.trades
--   - Add sovereignty validation columns
--   - Create sovereign execution checkpoint table
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Add quad_hash to trades table
-- ============================================================================

ALTER TABLE fhq_execution.trades
ADD COLUMN IF NOT EXISTS quad_hash VARCHAR(16),
ADD COLUMN IF NOT EXISTS lids_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS risl_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS acl_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS sovereignty_status VARCHAR(20) DEFAULT 'PENDING',
ADD COLUMN IF NOT EXISTS crio_insight_id UUID;

COMMENT ON COLUMN fhq_execution.trades.quad_hash IS
'MIT Quad validation hash (LIDS|ACL|RISL|DSL state) from CRIO insight';

COMMENT ON COLUMN fhq_execution.trades.lids_verified IS
'LIDS (Logical Integrity & Data Sovereignty) verification status';

COMMENT ON COLUMN fhq_execution.trades.risl_verified IS
'RISL (Risk Intelligence & Safety Layer) verification status';

COMMENT ON COLUMN fhq_execution.trades.acl_verified IS
'ACL (Access Control Layer) verification status';

COMMENT ON COLUMN fhq_execution.trades.sovereignty_status IS
'Overall sovereignty validation status: PENDING, VERIFIED, BLOCKED';

COMMENT ON COLUMN fhq_execution.trades.crio_insight_id IS
'Reference to CRIO insight that governs this trade';


-- ============================================================================
-- SECTION 2: Create Sovereign Execution Checkpoint Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_execution.sovereign_checkpoints (
    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Trade reference
    trade_id UUID REFERENCES fhq_execution.trades(trade_id),

    -- CRIO Intelligence Reference
    crio_insight_id UUID,
    crio_research_date DATE,
    fragility_score DECIMAL(5,4),
    dominant_driver VARCHAR(50),

    -- MIT Quad State
    quad_hash VARCHAR(16) NOT NULL,
    lids_status VARCHAR(20) NOT NULL,
    acl_status VARCHAR(20) NOT NULL,
    risl_status VARCHAR(20) NOT NULL,
    dsl_status VARCHAR(20) NOT NULL DEFAULT 'PASS',

    -- Sovereignty Decision
    sovereignty_decision VARCHAR(20) NOT NULL, -- APPROVED, BLOCKED, ESCALATED
    decision_reason TEXT,

    -- Risk Assessment
    risk_scalar_applied DECIMAL(5,4),
    position_scalar DECIMAL(5,4),

    -- Governance Lineage
    lineage_hash VARCHAR(64) NOT NULL,
    evidence_hash VARCHAR(16),

    -- Temporal
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(20) NOT NULL
);

-- Index for trade lookup
CREATE INDEX IF NOT EXISTS idx_sovereign_checkpoints_trade
    ON fhq_execution.sovereign_checkpoints(trade_id);

-- Index for CRIO insight lookup
CREATE INDEX IF NOT EXISTS idx_sovereign_checkpoints_crio
    ON fhq_execution.sovereign_checkpoints(crio_insight_id);

-- Index for checkpoint status
CREATE INDEX IF NOT EXISTS idx_sovereign_checkpoints_status
    ON fhq_execution.sovereign_checkpoints(sovereignty_decision, created_at DESC);

COMMENT ON TABLE fhq_execution.sovereign_checkpoints IS
'MIT-Quad sovereignty validation checkpoints for IoS-012 trades. CEO Directive ORDER C compliance.';


-- ============================================================================
-- SECTION 3: Create MIT-Quad Validation Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_execution.validate_mit_quad_sovereignty(
    p_asset_id TEXT,
    p_order_side TEXT,
    p_order_qty NUMERIC
)
RETURNS TABLE (
    can_execute BOOLEAN,
    quad_hash VARCHAR(16),
    lids_verified BOOLEAN,
    acl_verified BOOLEAN,
    risl_verified BOOLEAN,
    crio_insight_id UUID,
    fragility_score DECIMAL(5,4),
    dominant_driver VARCHAR(50),
    position_scalar DECIMAL(5,4),
    decision_reason TEXT
) AS $$
DECLARE
    v_crio_insight RECORD;
    v_quad_hash VARCHAR(16);
    v_lids_ok BOOLEAN := FALSE;
    v_acl_ok BOOLEAN := TRUE;  -- ACL default pass for paper
    v_risl_ok BOOLEAN := FALSE;
    v_can_execute BOOLEAN := FALSE;
    v_position_scalar DECIMAL(5,4) := 1.0;
    v_reason TEXT;
BEGIN
    -- Fetch latest LIDS-verified CRIO insight
    SELECT
        ni.insight_id, ni.research_date, ni.fragility_score,
        ni.dominant_driver, ni.quad_hash, ni.lids_verified, ni.risl_verified
    INTO v_crio_insight
    FROM fhq_research.nightly_insights ni
    WHERE ni.lids_verified = TRUE
    ORDER BY ni.research_date DESC
    LIMIT 1;

    IF v_crio_insight IS NULL THEN
        -- No CRIO insight - BLOCK execution
        RETURN QUERY SELECT
            FALSE::BOOLEAN,
            'NO_CRIO'::VARCHAR(16),
            FALSE, FALSE, FALSE,
            NULL::UUID,
            NULL::DECIMAL(5,4),
            NULL::VARCHAR(50),
            0.0::DECIMAL(5,4),
            'BLOCKED: No LIDS-verified CRIO insight available'::TEXT;
        RETURN;
    END IF;

    -- LIDS Check: Must have lids_verified = TRUE
    v_lids_ok := v_crio_insight.lids_verified;

    -- RISL Check: fragility_score thresholds
    -- If fragility > 0.80, RISL blocks the trade
    IF v_crio_insight.fragility_score > 0.80 THEN
        v_risl_ok := FALSE;
        v_reason := 'RISL_BLOCK: fragility_score ' || v_crio_insight.fragility_score || ' > 0.80';
    ELSE
        v_risl_ok := TRUE;
        -- Apply position scalar based on fragility
        IF v_crio_insight.fragility_score > 0.70 THEN
            v_position_scalar := 0.50;  -- 50% reduction
        ELSIF v_crio_insight.fragility_score < 0.40 THEN
            v_position_scalar := 1.00;  -- Full sizing
        ELSE
            v_position_scalar := 0.75;  -- Neutral reduction
        END IF;
    END IF;

    -- ACL Check: Paper environment always passes
    v_acl_ok := TRUE;

    -- Overall sovereignty decision
    v_can_execute := v_lids_ok AND v_acl_ok AND v_risl_ok;

    IF v_can_execute THEN
        v_reason := 'SOVEREIGNTY_VERIFIED: LIDS=' || v_lids_ok ||
                    ', ACL=' || v_acl_ok || ', RISL=' || v_risl_ok ||
                    ', scalar=' || v_position_scalar;
    ELSIF NOT v_lids_ok THEN
        v_reason := 'LIDS_BLOCK: insight not LIDS-verified';
    ELSIF NOT v_risl_ok THEN
        -- v_reason already set above
        NULL;
    ELSE
        v_reason := 'ACL_BLOCK: access control failure';
    END IF;

    RETURN QUERY SELECT
        v_can_execute,
        v_crio_insight.quad_hash::VARCHAR(16),
        v_lids_ok,
        v_acl_ok,
        v_risl_ok,
        v_crio_insight.insight_id,
        v_crio_insight.fragility_score,
        v_crio_insight.dominant_driver,
        v_position_scalar,
        v_reason;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_execution.validate_mit_quad_sovereignty IS
'Validates MIT-Quad sovereignty for trade execution. CEO Directive ORDER C.
Returns: can_execute, quad_hash, validation states, position scalar, reason.';


-- ============================================================================
-- SECTION 4: Log Migration
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
    'IoS-012',
    'MIT_QUAD_SOVEREIGNTY_INTEGRATION',
    NOW(),
    'STIG',
    'G2',
    jsonb_build_object(
        'migration', '088_ios012_mit_quad_sovereignty',
        'authority', 'CEO Directive ORDER C',
        'tables_modified', ARRAY['fhq_execution.trades'],
        'tables_created', ARRAY['fhq_execution.sovereign_checkpoints'],
        'functions_created', ARRAY['fhq_execution.validate_mit_quad_sovereignty'],
        'timestamp', NOW()
    ),
    encode(sha256('088_ios012_mit_quad_sovereignty'::bytea), 'hex')::VARCHAR(16)
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    -- Verify quad_hash column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_execution'
        AND table_name = 'trades'
        AND column_name = 'quad_hash'
    ) THEN
        RAISE EXCEPTION 'quad_hash column not created in trades table';
    END IF;

    -- Verify sovereign_checkpoints table
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_execution'
        AND table_name = 'sovereign_checkpoints'
    ) THEN
        RAISE EXCEPTION 'sovereign_checkpoints table not created';
    END IF;

    -- Verify validation function
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.routines
        WHERE routine_schema = 'fhq_execution'
        AND routine_name = 'validate_mit_quad_sovereignty'
    ) THEN
        RAISE EXCEPTION 'validate_mit_quad_sovereignty function not created';
    END IF;

    RAISE NOTICE 'Migration 088 completed successfully';
    RAISE NOTICE 'IoS-012 MIT-Quad sovereignty integration ready';
END $$;
