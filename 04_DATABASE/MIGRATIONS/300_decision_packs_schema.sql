-- Migration 300: Decision Packs Schema
-- CEO-DIR-2026-01-22: Signal → Decision Pack → Bracket Order
--
-- Creates the fhq_learning.decision_packs table for atomic decision objects
-- with full EWRE tracking and evidence chain.
--
-- Author: STIG (CTO)
-- Contract: EC-003_2026_PRODUCTION

BEGIN;

-- ============================================================================
-- SCHEMA
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS fhq_learning;

COMMENT ON SCHEMA fhq_learning IS
    'Learning and experimentation - Decision Packs, EWRE calculations, outcome tracking';

-- ============================================================================
-- DECISION PACKS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_learning.decision_packs (
    -- Identity
    pack_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    pack_version TEXT NOT NULL DEFAULT '1.0.0',

    -- Source References
    needle_id UUID,
    hypothesis_id TEXT,

    -- Asset & Direction
    asset TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    asset_class TEXT,

    -- Market Snapshot (TTL-enforced)
    snapshot_price NUMERIC,
    snapshot_regime TEXT,
    snapshot_volatility_atr NUMERIC,
    snapshot_timestamp TIMESTAMPTZ,
    snapshot_ttl_valid_until TIMESTAMPTZ,

    -- Confidence Stack (Damped)
    raw_confidence NUMERIC CHECK (raw_confidence BETWEEN 0 AND 1),
    damped_confidence NUMERIC CHECK (damped_confidence BETWEEN 0 AND 1),
    confidence_ceiling NUMERIC,
    inversion_flag BOOLEAN DEFAULT FALSE,
    inversion_type TEXT,

    -- Historical Calibration
    historical_accuracy NUMERIC,
    brier_skill_score NUMERIC,

    -- EWRE (Event-Weighted Risk Envelope)
    ewre_stop_loss_pct NUMERIC NOT NULL,
    ewre_take_profit_pct NUMERIC NOT NULL,
    ewre_risk_reward_ratio NUMERIC GENERATED ALWAYS AS (
        CASE WHEN ewre_stop_loss_pct > 0 THEN ewre_take_profit_pct / ewre_stop_loss_pct ELSE NULL END
    ) STORED,
    ewre_calculation_inputs JSONB,

    -- Bracket Order Specification
    entry_type TEXT DEFAULT 'LIMIT',
    entry_limit_price NUMERIC NOT NULL,
    take_profit_price NUMERIC NOT NULL,
    stop_loss_price NUMERIC NOT NULL,
    stop_type TEXT DEFAULT 'STOP_MARKET',
    stop_limit_price NUMERIC,

    -- Position Sizing
    position_usd NUMERIC NOT NULL,
    position_qty NUMERIC NOT NULL,
    kelly_fraction NUMERIC,
    max_position_pct NUMERIC,

    -- Time Constraints
    order_ttl_seconds INTEGER DEFAULT 86400,
    abort_if_not_filled_by TIMESTAMPTZ,

    -- Evidence Chain (Court-Proof)
    sitc_event_id UUID,
    inforage_session_id UUID,
    ikea_validation_id UUID,
    causal_edge_refs UUID[],
    evidence_hash TEXT NOT NULL,

    -- Cognitive Stack Results
    sitc_reasoning_complete BOOLEAN DEFAULT FALSE,
    inforage_roi NUMERIC,
    ikea_passed BOOLEAN DEFAULT FALSE,
    causal_alignment_score NUMERIC DEFAULT 0.5,

    -- Narrative (for Telegram)
    hypothesis_title TEXT,
    executive_summary TEXT,
    narrative_context TEXT,

    -- VEGA Attestation
    vega_attestation_required BOOLEAN DEFAULT TRUE,
    vega_attested BOOLEAN DEFAULT FALSE,
    vega_attestation_id TEXT,
    vega_attestation_timestamp TIMESTAMPTZ,

    -- Signature
    signature TEXT NOT NULL,
    signing_agent TEXT NOT NULL,
    signing_key_id TEXT NOT NULL,
    signed_at TIMESTAMPTZ NOT NULL,

    -- Outcome (Post-execution)
    execution_status TEXT DEFAULT 'PENDING' CHECK (
        execution_status IN ('PENDING', 'SUBMITTED', 'EXECUTED', 'BLOCKED', 'EXPIRED', 'CANCELLED', 'FAILED')
    ),
    alpaca_order_id TEXT,
    filled_price NUMERIC,
    filled_at TIMESTAMPTZ,

    -- Strategy tracking for Day 22+ analysis
    strategy_tag TEXT DEFAULT 'EWRE_V1',
    experiment_cohort TEXT DEFAULT 'FIRST_20',

    -- Price relationship constraints
    CONSTRAINT valid_long_prices CHECK (
        direction != 'LONG' OR (take_profit_price > entry_limit_price AND stop_loss_price < entry_limit_price)
    ),
    CONSTRAINT valid_short_prices CHECK (
        direction != 'SHORT' OR (take_profit_price < entry_limit_price AND stop_loss_price > entry_limit_price)
    )
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX idx_decision_packs_needle ON fhq_learning.decision_packs(needle_id);
CREATE INDEX idx_decision_packs_asset ON fhq_learning.decision_packs(asset, created_at DESC);
CREATE INDEX idx_decision_packs_status ON fhq_learning.decision_packs(execution_status);
CREATE INDEX idx_decision_packs_vega ON fhq_learning.decision_packs(vega_attested) WHERE NOT vega_attested;
CREATE INDEX idx_decision_packs_cohort ON fhq_learning.decision_packs(experiment_cohort, strategy_tag);
CREATE INDEX idx_decision_packs_created ON fhq_learning.decision_packs(created_at DESC);

-- ============================================================================
-- EWRE CALCULATIONS AUDIT TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_learning.ewre_calculations (
    calc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pack_id UUID REFERENCES fhq_learning.decision_packs(pack_id),
    inputs JSONB NOT NULL,
    outputs JSONB NOT NULL,
    calculation_version TEXT DEFAULT '1.0.0',
    calculated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ewre_calc_pack ON fhq_learning.ewre_calculations(pack_id);

-- ============================================================================
-- OUTCOME TRACKING VIEW
-- ============================================================================

CREATE OR REPLACE VIEW fhq_learning.v_decision_pack_outcomes AS
SELECT
    dp.pack_id,
    dp.asset,
    dp.direction,
    dp.strategy_tag,
    dp.experiment_cohort,
    dp.entry_limit_price,
    dp.take_profit_price,
    dp.stop_loss_price,
    dp.ewre_stop_loss_pct,
    dp.ewre_take_profit_pct,
    dp.ewre_risk_reward_ratio,
    dp.damped_confidence,
    dp.inversion_flag,
    dp.snapshot_regime,
    dp.execution_status,
    dp.filled_price,
    dp.filled_at,
    dp.created_at,
    -- Outcome calculation (will be populated after trade closes)
    CASE
        WHEN dp.filled_price IS NOT NULL AND dp.direction = 'LONG' THEN
            (dp.filled_price - dp.entry_limit_price) / dp.entry_limit_price
        WHEN dp.filled_price IS NOT NULL AND dp.direction = 'SHORT' THEN
            (dp.entry_limit_price - dp.filled_price) / dp.entry_limit_price
        ELSE NULL
    END as entry_slippage_pct,
    EXTRACT(EPOCH FROM (dp.filled_at - dp.created_at)) / 3600 as hours_to_fill
FROM fhq_learning.decision_packs dp
ORDER BY dp.created_at DESC;

-- ============================================================================
-- VEGA ATTESTATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_learning.verify_pack_attestation(p_pack_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_pack RECORD;
BEGIN
    SELECT * INTO v_pack
    FROM fhq_learning.decision_packs
    WHERE pack_id = p_pack_id;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Check attestation requirement
    IF v_pack.vega_attestation_required AND NOT v_pack.vega_attested THEN
        RETURN FALSE;
    END IF;

    -- Check evidence
    IF v_pack.evidence_hash IS NULL OR v_pack.evidence_hash = '' THEN
        RETURN FALSE;
    END IF;

    -- Check signature
    IF v_pack.signature IS NULL THEN
        RETURN FALSE;
    END IF;

    -- Check TTL
    IF v_pack.snapshot_ttl_valid_until < NOW() THEN
        RETURN FALSE;
    END IF;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STATISTICS VIEW FOR DAY 22 ANALYSIS
-- ============================================================================

CREATE OR REPLACE VIEW fhq_learning.v_ewre_cohort_statistics AS
SELECT
    experiment_cohort,
    strategy_tag,
    COUNT(*) as total_packs,
    COUNT(*) FILTER (WHERE execution_status = 'EXECUTED') as executed,
    COUNT(*) FILTER (WHERE execution_status = 'BLOCKED') as blocked,
    COUNT(*) FILTER (WHERE execution_status = 'EXPIRED') as expired,
    AVG(damped_confidence) as avg_confidence,
    AVG(ewre_risk_reward_ratio) as avg_rr_ratio,
    AVG(ewre_stop_loss_pct) as avg_sl_pct,
    AVG(ewre_take_profit_pct) as avg_tp_pct,
    COUNT(*) FILTER (WHERE inversion_flag) as inversion_signals,
    MIN(created_at) as first_pack,
    MAX(created_at) as last_pack
FROM fhq_learning.decision_packs
GROUP BY experiment_cohort, strategy_tag
ORDER BY experiment_cohort, strategy_tag;

-- ============================================================================
-- GOVERNANCE LOG
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_id,
    action_description,
    evidence_hash,
    created_by
) VALUES (
    'MIGRATION',
    'CEO-DIR-2026-01-22-DECISION-PACK',
    'Created fhq_learning.decision_packs schema for atomic decision objects with EWRE tracking',
    encode(sha256('migration-300-decision-packs'::bytea), 'hex'),
    'STIG'
) ON CONFLICT DO NOTHING;

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 300 complete: fhq_learning.decision_packs created';
    RAISE NOTICE 'Tables: decision_packs, ewre_calculations';
    RAISE NOTICE 'Views: v_decision_pack_outcomes, v_ewre_cohort_statistics';
    RAISE NOTICE 'Function: verify_pack_attestation()';
END $$;
