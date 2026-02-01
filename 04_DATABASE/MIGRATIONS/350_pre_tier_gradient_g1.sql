-- ============================================================================
-- Migration: 350_pre_tier_gradient_g1.sql
-- Directive: CEO-DIR-2026-PRE-TIER-GRADIENT-001 (Decision Matrix)
-- Gate: G1 (Build & Verify)
-- Executor: STIG (EC-003)
-- Validator: VEGA (EC-004)
-- Date: 2026-01-25
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: CREATE ENUM TYPE
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pre_tier_score_status_enum') THEN
        CREATE TYPE fhq_learning.pre_tier_score_status_enum AS ENUM (
            'PENDING',
            'SCORING',
            'SCORED',
            'FAIL_CLOSED',
            'STALE'
        );
    END IF;
END $$;

-- ============================================================================
-- STEP 2: ADD PRE-TIER COLUMNS TO hypothesis_canon
-- ============================================================================
ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS pre_tier_score NUMERIC(5,2)
    CHECK (pre_tier_score IS NULL OR (pre_tier_score >= 0 AND pre_tier_score <= 100)),
ADD COLUMN IF NOT EXISTS evidence_density_score NUMERIC(5,2)
    CHECK (evidence_density_score IS NULL OR (evidence_density_score >= 0 AND evidence_density_score <= 100)),
ADD COLUMN IF NOT EXISTS data_freshness_score NUMERIC(5,2)
    CHECK (data_freshness_score IS NULL OR (data_freshness_score >= 0 AND data_freshness_score <= 100)),
ADD COLUMN IF NOT EXISTS causal_depth_score NUMERIC(5,2)
    CHECK (causal_depth_score IS NULL OR (causal_depth_score >= 0 AND causal_depth_score <= 100)),
ADD COLUMN IF NOT EXISTS cross_agent_agreement_score NUMERIC(5,2)
    CHECK (cross_agent_agreement_score IS NULL OR (cross_agent_agreement_score >= 0 AND cross_agent_agreement_score <= 100)),
ADD COLUMN IF NOT EXISTS draft_age_hours NUMERIC(10,2),
ADD COLUMN IF NOT EXISTS draft_decay_penalty NUMERIC(5,2)
    CHECK (draft_decay_penalty IS NULL OR (draft_decay_penalty >= 0 AND draft_decay_penalty <= 25)),
ADD COLUMN IF NOT EXISTS pre_tier_score_version VARCHAR(10) DEFAULT '1.0.0',
ADD COLUMN IF NOT EXISTS pre_tier_score_status TEXT DEFAULT 'PENDING',
ADD COLUMN IF NOT EXISTS pre_tier_scored_by JSONB,
ADD COLUMN IF NOT EXISTS pre_tier_scored_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS pre_tier_birth_hash TEXT,
ADD COLUMN IF NOT EXISTS pre_tier_hash_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS pre_tier_defcon_at_score TEXT;

-- ============================================================================
-- STEP 3: CREATE VALIDATOR SCORES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_learning.pre_tier_validator_scores (
    validation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id UUID NOT NULL REFERENCES fhq_learning.hypothesis_canon(canon_id),
    validator_ec TEXT NOT NULL,
    evidence_density_estimate NUMERIC(5,2)
        CHECK (evidence_density_estimate >= 0 AND evidence_density_estimate <= 100),
    causal_depth_estimate NUMERIC(5,2)
        CHECK (causal_depth_estimate >= 0 AND causal_depth_estimate <= 100),
    data_freshness_estimate NUMERIC(5,2)
        CHECK (data_freshness_estimate >= 0 AND data_freshness_estimate <= 100),
    composite_score NUMERIC(5,2)
        CHECK (composite_score >= 0 AND composite_score <= 100),
    validation_rationale TEXT,
    validation_timestamp TIMESTAMPTZ DEFAULT NOW(),
    validation_hash TEXT NOT NULL,
    UNIQUE(hypothesis_id, validator_ec)
);

CREATE INDEX IF NOT EXISTS idx_pre_tier_validator_hypothesis
ON fhq_learning.pre_tier_validator_scores(hypothesis_id);

CREATE INDEX IF NOT EXISTS idx_pre_tier_validator_ec
ON fhq_learning.pre_tier_validator_scores(validator_ec);

-- ============================================================================
-- STEP 4: CREATE CALIBRATION AUDIT TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhq_governance.pre_tier_calibration_audit (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_week DATE NOT NULL,
    sample_size INTEGER NOT NULL,
    pearson_r NUMERIC(5,4),
    spearman_rho NUMERIC(5,4),
    data_status TEXT DEFAULT 'VALID'
        CHECK (data_status IN ('VALID', 'INSUFFICIENT_DATA')),
    flag_for_review BOOLEAN DEFAULT FALSE,
    ceo_reviewed_at TIMESTAMPTZ,
    ceo_decision TEXT,
    weight_adjustment_proposal JSONB,
    computed_by TEXT DEFAULT 'VEGA',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(audit_week)
);

-- ============================================================================
-- STEP 5: REGISTER SCORING ORCHESTRATOR
-- ============================================================================
INSERT INTO fhq_governance.orchestrator_authority (
    orchestrator_id,
    orchestrator_name,
    scope,
    asset_classes,
    primary_vendor,
    fallback_vendors,
    constitutional_authority,
    enabled,
    stop_conditions,
    freshness_metrics_enabled,
    fail_closed,
    activated_by,
    activated_at,
    directive_reference,
    created_at
) VALUES (
    'FHQ-PreTier-Scoring-Orchestrator',
    'Pre-Tier Gradient Scoring Orchestrator',
    'Hypothesis pre-tier scoring coordination and status transitions',
    ARRAY['hypothesis'],
    'VEGA',
    ARRAY[]::TEXT[],
    true,
    true,
    '{"anti_echo_violation": "FAIL_CLOSED", "min_validators": 2}'::JSONB,
    true,
    true,
    'CEO',
    NOW(),
    'CEO-DIR-2026-PRE-TIER-GRADIENT-001',
    NOW()
) ON CONFLICT (orchestrator_id) DO UPDATE SET
    enabled = true,
    directive_reference = 'CEO-DIR-2026-PRE-TIER-GRADIENT-001',
    activated_at = NOW();

-- ============================================================================
-- STEP 6: VEGA VALIDATION RULE - ANTI-ECHO ENFORCEMENT
-- ============================================================================
INSERT INTO fhq_governance.vega_validation_rules (
    rule_id,
    rule_name,
    rule_type,
    applies_to,
    condition_sql,
    failure_action,
    constitutional_basis,
    is_active,
    created_at
) VALUES (
    gen_random_uuid(),
    'Anti-Echo Pre-Tier Scoring',
    'INVARIANT',
    ARRAY['fhq_learning.hypothesis_canon'],
    'SELECT canon_id FROM fhq_learning.hypothesis_canon WHERE pre_tier_scored_by IS NOT NULL AND pre_tier_scored_by::jsonb ? generator_id',
    'BLOCK',
    'CEO-DIR-2026-PRE-TIER-GRADIENT-001 Section 3.1',
    true,
    NOW()
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- STEP 7: CREATE SCORING FUNCTION
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_learning.calculate_pre_tier_score(
    p_evidence_density NUMERIC,
    p_causal_depth_raw INTEGER,
    p_data_freshness NUMERIC,
    p_agreement NUMERIC,
    p_draft_age_hours NUMERIC
) RETURNS TABLE (
    pre_tier_score NUMERIC,
    causal_depth_score NUMERIC,
    draft_decay_penalty NUMERIC
) AS $$
DECLARE
    v_causal_depth_score NUMERIC;
    v_decay_penalty NUMERIC;
    v_raw_score NUMERIC;
    v_final_score NUMERIC;
BEGIN
    v_causal_depth_score := LEAST(p_causal_depth_raw * 25.0, 100.0);
    v_decay_penalty := LEAST(p_draft_age_hours * 0.5, 25.0);
    v_raw_score := (COALESCE(p_evidence_density, 0) * 0.3) +
                   (v_causal_depth_score * 0.4) +
                   (COALESCE(p_data_freshness, 0) * 0.2) +
                   (COALESCE(p_agreement, 100) * 0.1) -
                   v_decay_penalty;
    v_final_score := GREATEST(LEAST(v_raw_score, 100), 0);
    RETURN QUERY SELECT
        ROUND(v_final_score, 2)::NUMERIC,
        ROUND(v_causal_depth_score, 2)::NUMERIC,
        ROUND(v_decay_penalty, 2)::NUMERIC;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- STEP 8: CREATE AGREEMENT SCORE FUNCTION
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_learning.calculate_agreement_score(
    p_hypothesis_id UUID
) RETURNS NUMERIC AS $$
DECLARE
    v_stddev NUMERIC;
    v_max_possible NUMERIC := 50.0;
    v_agreement NUMERIC;
BEGIN
    SELECT COALESCE(STDDEV(composite_score), 0)
    INTO v_stddev
    FROM fhq_learning.pre_tier_validator_scores
    WHERE hypothesis_id = p_hypothesis_id;
    v_agreement := 100 - LEAST((v_stddev / v_max_possible) * 100, 100);
    RETURN ROUND(v_agreement, 2);
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- STEP 9: CREATE BIRTH-HASH FUNCTION
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_learning.generate_pre_tier_birth_hash(
    p_hypothesis_id UUID
) RETURNS TEXT AS $$
DECLARE
    v_hash_input TEXT;
    v_validator_scores TEXT;
    v_defcon TEXT;
BEGIN
    SELECT defcon_level INTO v_defcon
    FROM fhq_governance.defcon_state
    WHERE is_current = true;

    SELECT COALESCE(
        jsonb_agg(
            jsonb_build_object(
                'validator', validator_ec,
                'evidence', evidence_density_estimate,
                'causal', causal_depth_estimate,
                'freshness', data_freshness_estimate,
                'composite', composite_score
            ) ORDER BY validator_ec
        )::TEXT,
        '[]'
    ) INTO v_validator_scores
    FROM fhq_learning.pre_tier_validator_scores
    WHERE hypothesis_id = p_hypothesis_id;

    SELECT FORMAT(
        '%s|%s|%s|%s|%s|%s|%s|%s',
        h.evidence_density_score,
        h.causal_depth_score,
        h.data_freshness_score,
        h.cross_agent_agreement_score,
        h.pre_tier_score_version,
        h.pre_tier_score_status,
        v_defcon,
        v_validator_scores
    ) INTO v_hash_input
    FROM fhq_learning.hypothesis_canon h
    WHERE h.canon_id = p_hypothesis_id;

    RETURN encode(sha256(v_hash_input::bytea), 'hex');
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- STEP 10: INITIALIZE EXISTING DRAFT HYPOTHESES
-- ============================================================================
UPDATE fhq_learning.hypothesis_canon
SET
    pre_tier_score_status = 'PENDING',
    draft_age_hours = EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0,
    causal_depth_score = LEAST(COALESCE(causal_graph_depth, 1) * 25.0, 100.0)
WHERE status = 'DRAFT'
AND (pre_tier_score_status IS NULL OR pre_tier_score_status = 'PENDING');

-- ============================================================================
-- STEP 11: CREATE VIEW FOR SCORING DASHBOARD
-- ============================================================================
CREATE OR REPLACE VIEW fhq_learning.v_pre_tier_scoring_status AS
SELECT
    h.canon_id,
    h.hypothesis_code,
    h.generator_id,
    h.status AS hypothesis_status,
    h.pre_tier_score_status,
    h.pre_tier_score,
    h.evidence_density_score,
    h.causal_depth_score,
    h.data_freshness_score,
    h.cross_agent_agreement_score,
    h.draft_decay_penalty,
    h.pre_tier_score_version,
    h.pre_tier_scored_at,
    h.pre_tier_birth_hash IS NOT NULL AS hash_locked,
    h.pre_tier_hash_verified,
    (SELECT COUNT(*) FROM fhq_learning.pre_tier_validator_scores v
     WHERE v.hypothesis_id = h.canon_id) AS validator_count,
    (SELECT COUNT(*) >= 2 FROM fhq_learning.pre_tier_validator_scores v
     WHERE v.hypothesis_id = h.canon_id) AS min_validators_met,
    h.created_at,
    EXTRACT(EPOCH FROM (NOW() - h.created_at)) / 3600.0 AS current_draft_age_hours
FROM fhq_learning.hypothesis_canon h
WHERE h.status = 'DRAFT';

-- ============================================================================
-- STEP 12: CREATE OXYGEN RULE VIEW
-- ============================================================================
CREATE OR REPLACE VIEW fhq_learning.v_oxygen_rule_eligible AS
SELECT
    h.canon_id,
    h.hypothesis_code,
    h.causal_graph_depth,
    h.pre_tier_score,
    d.defcon_level,
    CASE
        WHEN d.defcon_level = 'GREEN'
             AND h.causal_graph_depth >= 3
             AND h.pre_tier_score > 75
        THEN true
        ELSE false
    END AS oxygen_extension_eligible,
    CASE
        WHEN d.defcon_level = 'GREEN'
             AND h.causal_graph_depth >= 3
             AND h.pre_tier_score > 75
        THEN '+12h observation window'
        ELSE 'Standard observation'
    END AS observation_status
FROM fhq_learning.hypothesis_canon h
CROSS JOIN (
    SELECT defcon_level
    FROM fhq_governance.defcon_state
    WHERE is_current = true
) d
WHERE h.status = 'DRAFT';

-- ============================================================================
-- STEP 13: REGISTER G1 EVIDENCE
-- ============================================================================
INSERT INTO fhq_governance.canonical_evidence (
    evidence_type,
    evidence_category,
    agent_id,
    execution_timestamp,
    evidence_hash,
    evidence_payload,
    vega_signature,
    vega_public_key,
    registered_by,
    registered_at,
    authority,
    adr_compliance,
    audit_notes,
    immutable
) VALUES (
    'SCHEMA_MIGRATION',
    'G1_BUILD_VERIFY',
    'STIG',
    NOW(),
    encode(sha256('CEO-DIR-2026-PRE-TIER-GRADIENT-001|350_pre_tier_gradient_g1|G1|STIG'::bytea), 'hex'),
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-PRE-TIER-GRADIENT-001',
        'migration', '350_pre_tier_gradient_g1.sql',
        'tables_created', ARRAY['pre_tier_validator_scores', 'pre_tier_calibration_audit'],
        'columns_added', 14,
        'functions_created', ARRAY['calculate_pre_tier_score', 'calculate_agreement_score', 'generate_pre_tier_birth_hash'],
        'views_created', ARRAY['v_pre_tier_scoring_status', 'v_oxygen_rule_eligible'],
        'orchestrator_registered', 'FHQ-PreTier-Scoring-Orchestrator',
        'vega_rules_added', ARRAY['Anti-Echo Pre-Tier Scoring']
    ),
    'PENDING_VEGA_ATTESTATION',
    'PENDING_VEGA_ATTESTATION',
    'STIG',
    NOW(),
    'CEO',
    ARRAY['ADR-011', 'ADR-013'],
    'Pre-Tier Gradient G1 schema hardening complete. Awaiting VEGA attestation.',
    true
);

COMMIT;
