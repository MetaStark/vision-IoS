-- ============================================================
-- IoS-008: RUNTIME DECISION ENGINE — G0 FOUNDATION
-- ============================================================
-- Authority: BOARD (Vice-CEO)
-- Technical Lead: STIG (CTO)
-- Governance: VEGA
-- Classification: Tier-1 Critical
-- Migration: 051_ios008_runtime_decision_engine.sql
-- ============================================================
--
-- "Probabilistic Insight → Deterministic Intent"
--
-- IoS-008 converts truth into decision.
-- It produces ONE immutable, hash-chained DecisionPlan.
-- IoS-012 (Execution) can ONLY act on signed DecisionPlans.
-- ============================================================

BEGIN;

-- ============================================================
-- SECTION 1: DECISION LOG (Append-Only, ADR-011 Compliant)
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.decision_log (
    -- Primary Key
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Temporal (TTL Enforcement)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMPTZ NOT NULL,  -- IRONCLAD: 15-minute TTL max

    -- Context Snapshot (Inputs that produced this decision)
    context_hash TEXT NOT NULL,  -- SHA256 of all inputs
    regime_snapshot JSONB NOT NULL,      -- IoS-003 state at decision time
    causal_snapshot JSONB NOT NULL,      -- IoS-007 state at decision time
    skill_snapshot JSONB NOT NULL,       -- IoS-005 state at decision time

    -- Global State
    global_regime TEXT NOT NULL,         -- e.g., 'BEAR', 'BULL_TRENDING'
    defcon_level INTEGER NOT NULL CHECK (defcon_level BETWEEN 1 AND 5),
    system_skill_score NUMERIC(5,4) NOT NULL CHECK (system_skill_score BETWEEN 0 AND 1),

    -- Asset Directives (The actual decisions)
    asset_directives JSONB NOT NULL,     -- Array of per-asset instructions

    -- Decision Metadata
    decision_type TEXT NOT NULL DEFAULT 'REGIME_BASED',
    decision_rationale TEXT,

    -- Formula Components (for audit trail)
    base_allocation NUMERIC(7,4) NOT NULL,
    regime_scalar NUMERIC(5,4) NOT NULL,
    causal_vector NUMERIC(7,4) NOT NULL,
    skill_damper NUMERIC(5,4) NOT NULL,
    final_allocation NUMERIC(7,4) NOT NULL,

    -- Governance & Cryptographic Integrity
    governance_signature TEXT,           -- Ed25519 signature
    signature_agent TEXT NOT NULL,       -- 'IoS-008' or agent ID

    -- Hash Chain (ADR-011)
    hash_prev TEXT,                      -- Previous decision hash
    hash_self TEXT NOT NULL,             -- This decision's hash
    sequence_number BIGINT NOT NULL,     -- Monotonic counter

    -- Execution State
    execution_state TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (execution_state IN ('PENDING', 'TRANSMITTED', 'EXECUTED', 'EXPIRED', 'REJECTED', 'SUPERSEDED')),
    transmitted_to_ios012_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    rejection_reason TEXT,

    -- Audit
    created_by TEXT NOT NULL DEFAULT 'IoS-008',

    -- Constraints
    CONSTRAINT decision_ttl_max CHECK (valid_until <= valid_from + INTERVAL '15 minutes'),
    CONSTRAINT decision_not_expired_on_create CHECK (valid_until > created_at)
);

-- Create index for TTL enforcement queries
CREATE INDEX IF NOT EXISTS idx_decision_log_valid_until ON fhq_governance.decision_log(valid_until);
CREATE INDEX IF NOT EXISTS idx_decision_log_execution_state ON fhq_governance.decision_log(execution_state);
CREATE INDEX IF NOT EXISTS idx_decision_log_sequence ON fhq_governance.decision_log(sequence_number);

-- Append-Only Trigger (ADR-011 Compliance)
CREATE OR REPLACE FUNCTION fhq_governance.prevent_decision_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        -- Only allow execution_state updates (and related fields)
        IF OLD.context_hash != NEW.context_hash OR
           OLD.asset_directives != NEW.asset_directives OR
           OLD.final_allocation != NEW.final_allocation OR
           OLD.hash_self != NEW.hash_self THEN
            RAISE EXCEPTION 'GOVERNANCE VIOLATION: decision_log is append-only. Core fields cannot be modified.';
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'GOVERNANCE VIOLATION: decision_log records cannot be deleted.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS enforce_decision_log_immutability ON fhq_governance.decision_log;
CREATE TRIGGER enforce_decision_log_immutability
    BEFORE UPDATE OR DELETE ON fhq_governance.decision_log
    FOR EACH ROW EXECUTE FUNCTION fhq_governance.prevent_decision_log_modification();

-- ============================================================
-- SECTION 2: REGIME SCALAR LOOKUP (G0 Configuration)
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.regime_scalar_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    regime_label TEXT NOT NULL UNIQUE,
    scalar_value NUMERIC(5,4) NOT NULL CHECK (scalar_value BETWEEN -1 AND 1),
    mode TEXT NOT NULL DEFAULT 'LONG_ONLY' CHECK (mode IN ('LONG_ONLY', 'LONG_SHORT')),
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'STIG'
);

-- G0 Configuration: Capital Preservation Mode (BEAR/BROKEN = 0.0)
INSERT INTO fhq_governance.regime_scalar_config
    (regime_label, scalar_value, mode, description)
VALUES
    -- Capital Preservation (G0 Default)
    ('STRONG_BULL', 1.0000, 'LONG_ONLY', 'Maximum conviction in bull regime'),
    ('BULL', 0.8000, 'LONG_ONLY', 'Standard bull allocation'),
    ('RANGE_UP', 0.6000, 'LONG_ONLY', 'Accumulation phase'),
    ('NEUTRAL', 0.5000, 'LONG_ONLY', 'Balanced/uncertain market'),
    ('RANGE_DOWN', 0.3000, 'LONG_ONLY', 'Defensive positioning'),
    ('BEAR', 0.0000, 'LONG_ONLY', 'G0: Full cash - Capital Preservation'),
    ('STRONG_BEAR', 0.0000, 'LONG_ONLY', 'G0: Full cash - Capital Preservation'),
    ('PARABOLIC', 0.2500, 'LONG_ONLY', 'Reduce exposure, volatility high'),
    ('BROKEN', 0.0000, 'LONG_ONLY', 'G0: Full cash - System Anomaly'),
    ('CHOPPY', 0.2000, 'LONG_ONLY', 'Low conviction, reduce size'),
    ('MICRO_BULL', 0.4000, 'LONG_ONLY', 'Short-term bullish within larger uncertainty')
ON CONFLICT (regime_label) DO UPDATE SET
    scalar_value = EXCLUDED.scalar_value,
    mode = EXCLUDED.mode,
    updated_at = NOW();

-- ============================================================
-- SECTION 3: SKILL DAMPER CONFIGURATION (IoS-005 Integration)
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.skill_damper_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    threshold_type TEXT NOT NULL,
    fss_min NUMERIC(5,4) NOT NULL,  -- Forecast Skill Score minimum
    fss_max NUMERIC(5,4) NOT NULL,  -- Forecast Skill Score maximum
    damper_value NUMERIC(5,4) NOT NULL CHECK (damper_value BETWEEN 0 AND 1),
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(fss_min, fss_max)
);

-- Skill Damper Curve (per LARS specification)
INSERT INTO fhq_governance.skill_damper_config
    (threshold_type, fss_min, fss_max, damper_value, description)
VALUES
    ('FREEZE', 0.0000, 0.4000, 0.0000, 'Capital Freeze - System incompetent'),
    ('REDUCED', 0.4000, 0.5000, 0.2500, 'Severely reduced sizing'),
    ('CAUTIOUS', 0.5000, 0.6000, 0.5000, 'Half sizing - marginal competence'),
    ('NORMAL', 0.6000, 0.8000, 1.0000, 'Full sizing - competent'),
    ('HIGH', 0.8000, 1.0001, 1.0000, 'Full sizing - high skill')
ON CONFLICT (fss_min, fss_max) DO UPDATE SET
    damper_value = EXCLUDED.damper_value,
    description = EXCLUDED.description;

-- ============================================================
-- SECTION 4: DECISION SEQUENCE TRACKER
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.decision_sequence (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- Single row
    last_sequence BIGINT NOT NULL DEFAULT 0,
    last_hash TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO fhq_governance.decision_sequence (id, last_sequence, last_hash)
VALUES (1, 0, NULL)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- SECTION 5: COMPUTE DECISION PLAN FUNCTION (Deterministic)
-- ============================================================

CREATE OR REPLACE FUNCTION fhq_governance.compute_decision_plan(
    p_asset_id TEXT,
    p_base_allocation NUMERIC DEFAULT 1.0
)
RETURNS TABLE (
    decision_id UUID,
    asset_id TEXT,
    regime TEXT,
    regime_scalar NUMERIC,
    causal_vector NUMERIC,
    skill_damper NUMERIC,
    final_allocation NUMERIC,
    valid_until TIMESTAMPTZ,
    context_hash TEXT
) AS $$
DECLARE
    v_regime TEXT;
    v_regime_confidence NUMERIC;
    v_regime_scalar NUMERIC;
    v_causal_vector NUMERIC;
    v_skill_score NUMERIC;
    v_skill_damper NUMERIC;
    v_final_alloc NUMERIC;
    v_context_hash TEXT;
    v_decision_id UUID;
    v_valid_until TIMESTAMPTZ;
    v_sequence BIGINT;
    v_prev_hash TEXT;
    v_self_hash TEXT;
BEGIN
    -- Step 1: Get current regime from IoS-003
    SELECT r.regime_label, r.confidence_score
    INTO v_regime, v_regime_confidence
    FROM fhq_research.regime_predictions_v2 r
    WHERE r.asset_id = p_asset_id
    ORDER BY r.timestamp DESC
    LIMIT 1;

    IF v_regime IS NULL THEN
        RAISE EXCEPTION 'NO_DECISION: Missing regime data for asset %', p_asset_id;
    END IF;

    -- Step 2: Get RegimeScalar from config
    SELECT COALESCE(rs.scalar_value, 0.5)
    INTO v_regime_scalar
    FROM fhq_governance.regime_scalar_config rs
    WHERE rs.regime_label = v_regime AND rs.is_active = true;

    IF v_regime_scalar IS NULL THEN
        v_regime_scalar := 0.5;  -- Default to neutral if regime not configured
    END IF;

    -- Step 3: Compute CausalVector from IoS-007 Golden Edges
    -- Normalized sum of edge strengths for this asset
    SELECT COALESCE(
        1.0 + (SUM(e.strength * CASE
            WHEN e.status = 'GOLDEN' THEN 1.0
            WHEN e.status = 'VALIDATED' THEN 0.7
            ELSE 0.3
        END) / NULLIF(COUNT(*), 0)),
        1.0
    )
    INTO v_causal_vector
    FROM fhq_graph.edges e
    WHERE e.to_node_id = 'ASSET_' || SPLIT_PART(p_asset_id, '-', 1)
    AND e.status IN ('GOLDEN', 'VALIDATED', 'ACTIVE');

    -- Clamp causal vector to reasonable range
    v_causal_vector := GREATEST(0.5, LEAST(2.0, v_causal_vector));

    -- Step 4: Get SkillDamper from IoS-005
    -- For G0, use system-wide average skill score
    SELECT COALESCE(AVG(fr.ios005_p_value), 0.5)
    INTO v_skill_score
    FROM fhq_macro.feature_registry fr
    WHERE fr.status = 'GOLDEN' AND fr.ios005_tested = true;

    -- Convert to skill score (lower p-value = higher skill)
    v_skill_score := 1.0 - LEAST(v_skill_score, 1.0);

    -- Look up damper value
    SELECT COALESCE(sd.damper_value, 1.0)
    INTO v_skill_damper
    FROM fhq_governance.skill_damper_config sd
    WHERE sd.is_active = true
    AND v_skill_score >= sd.fss_min
    AND v_skill_score < sd.fss_max;

    IF v_skill_damper IS NULL THEN
        v_skill_damper := 1.0;
    END IF;

    -- Step 5: THE FORMULA (Deterministic)
    -- Alloc = Base × RegimeScalar × CausalVector × SkillDamper
    v_final_alloc := p_base_allocation * v_regime_scalar * v_causal_vector * v_skill_damper;

    -- Clamp to valid allocation range
    v_final_alloc := GREATEST(-1.0, LEAST(1.0, v_final_alloc));

    -- Step 6: Generate context hash (deterministic)
    v_context_hash := encode(sha256(
        (p_asset_id || v_regime || v_regime_scalar::text || v_causal_vector::text || v_skill_damper::text || NOW()::text)::bytea
    ), 'hex');

    -- Step 7: Set TTL (15 minutes from now)
    v_valid_until := NOW() + INTERVAL '15 minutes';

    -- Step 8: Generate decision ID
    v_decision_id := gen_random_uuid();

    -- Return computed values
    RETURN QUERY SELECT
        v_decision_id,
        p_asset_id,
        v_regime,
        v_regime_scalar,
        v_causal_vector,
        v_skill_damper,
        v_final_alloc,
        v_valid_until,
        v_context_hash;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- SECTION 6: GOVERNANCE ACTION LOG
-- ============================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale,
    vega_reviewed, vega_override, hash_chain_id
) VALUES (
    gen_random_uuid(),
    'IOS_INITIATION',
    'IoS-008',
    'MODULE',
    'BOARD',
    NOW(),
    'APPROVED',
    'IoS-008 G0 Initiation - Runtime Decision Engine. Created decision_log (append-only), regime_scalar_config (G0: BEAR/BROKEN=0.0), skill_damper_config, compute_decision_plan() function.',
    false,
    false,
    'HC-IOS008-G0-001'
);

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================

SELECT 'REGIME_SCALAR' as config, regime_label, scalar_value, mode
FROM fhq_governance.regime_scalar_config
WHERE is_active = true
ORDER BY scalar_value DESC;

SELECT 'SKILL_DAMPER' as config, threshold_type, fss_min, fss_max, damper_value
FROM fhq_governance.skill_damper_config
WHERE is_active = true
ORDER BY fss_min;

-- Test compute_decision_plan for BTC
SELECT * FROM fhq_governance.compute_decision_plan('BTC-USD', 1.0);
