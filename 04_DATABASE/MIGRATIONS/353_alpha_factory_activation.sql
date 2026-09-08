-- ============================================================================
-- Migration: 353_alpha_factory_activation.sql
-- Directive: CEO-VEDTAK-2026-ALPHA-FACTORY-ACTIVATION
-- Purpose: Activate FINN-E + FINN-T with safe scaling infrastructure
-- Executor: STIG (EC-003)
-- Date: 2026-01-25
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION A: DIVERSIFIED STIMULUS CONFIGURATION
-- ============================================================================

-- A1: Update FINN-E with rotation config
UPDATE fhq_learning.generator_registry
SET constraints = COALESCE(constraints, '{}'::jsonb) || jsonb_build_object(
    'rotation_config', jsonb_build_object(
        'timeframes', ARRAY['15m', '1h', '4h'],
        'asset_rotation', true,
        'rotation_interval_hours', 4,
        'last_rotated_at', NOW()
    ),
    'g1_5_activated', true,
    'g1_5_activation_ts', NOW()
)
WHERE generator_id = 'FINN-E';

-- A2: Update FINN-T with rotation config
UPDATE fhq_learning.generator_registry
SET constraints = COALESCE(constraints, '{}'::jsonb) || jsonb_build_object(
    'rotation_config', jsonb_build_object(
        'timeframes', ARRAY['15m', '1h', '4h'],
        'asset_rotation', true,
        'rotation_interval_hours', 4,
        'last_rotated_at', NOW()
    ),
    'g1_5_activated', true,
    'g1_5_activation_ts', NOW()
)
WHERE generator_id = 'FINN-T';

-- A3: Update finn_crypto_scheduler with rotation config
UPDATE fhq_learning.generator_registry
SET constraints = COALESCE(constraints, '{}'::jsonb) || jsonb_build_object(
    'rotation_config', jsonb_build_object(
        'timeframes', ARRAY['15m', '1h', '4h'],
        'asset_rotation', true,
        'rotation_interval_hours', 3,
        'last_rotated_at', NOW()
    ),
    'g1_5_activated', true,
    'g1_5_activation_ts', NOW()
)
WHERE generator_id = 'finn_crypto_scheduler';

-- ============================================================================
-- SECTION B: AUTOMATIC STALE HANDLING
-- ============================================================================

-- B1: Create stale cleanup function
CREATE OR REPLACE FUNCTION fhq_learning.cleanup_stale_hypotheses()
RETURNS TABLE (
    hypotheses_marked_stale INTEGER,
    execution_timestamp TIMESTAMPTZ
) AS $$
DECLARE
    v_count INTEGER;
BEGIN
    -- Mark hypotheses with draft_age_hours > 48 as STALE
    -- Only if they haven't been picked up by Tier-1
    UPDATE fhq_learning.hypothesis_canon
    SET
        pre_tier_score_status = 'STALE',
        updated_at = NOW()
    WHERE status = 'DRAFT'
    AND pre_tier_score_status IN ('PENDING', 'SCORED')
    AND EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0 > 48
    AND canon_id NOT IN (
        SELECT DISTINCT hypothesis_id
        FROM fhq_learning.experiment_registry
        WHERE hypothesis_id IS NOT NULL
    );

    GET DIAGNOSTICS v_count = ROW_COUNT;

    -- Log the cleanup
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
        'AUTOMATED_CLEANUP',
        'STALE_HYPOTHESIS_CLEANUP',
        'STIG',
        NOW(),
        encode(sha256(('STALE_CLEANUP|' || NOW()::text || '|' || v_count::text)::bytea), 'hex'),
        jsonb_build_object(
            'hypotheses_marked_stale', v_count,
            'threshold_hours', 48,
            'cleanup_reason', 'draft_age_hours > 48 without Tier-1 pickup'
        ),
        'AUTOMATED',
        'AUTOMATED',
        'STIG',
        NOW(),
        'SYSTEM',
        ARRAY['ADR-011'],
        'Automated stale hypothesis cleanup executed',
        true
    );

    RETURN QUERY SELECT v_count, NOW();
END;
$$ LANGUAGE plpgsql;

-- B2: Create view to monitor stale candidates
CREATE OR REPLACE VIEW fhq_learning.v_stale_candidates AS
SELECT
    canon_id,
    hypothesis_code,
    generator_id,
    status,
    pre_tier_score_status,
    pre_tier_score,
    created_at,
    ROUND(EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0, 1) as draft_age_hours,
    CASE
        WHEN EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0 > 48 THEN 'STALE_CANDIDATE'
        WHEN EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0 > 36 THEN 'WARNING'
        ELSE 'FRESH'
    END as freshness_status
FROM fhq_learning.hypothesis_canon
WHERE status = 'DRAFT'
AND pre_tier_score_status NOT IN ('STALE', 'FAIL_CLOSED')
ORDER BY created_at ASC;

-- ============================================================================
-- SECTION C: VALIDATOR POOL EXPANSION
-- ============================================================================

-- C1: Create validator authority table
CREATE TABLE IF NOT EXISTS fhq_learning.pre_tier_validator_authority (
    validator_ec TEXT PRIMARY KEY,
    validator_name TEXT NOT NULL,
    validator_role TEXT NOT NULL,
    authorized_at TIMESTAMPTZ DEFAULT NOW(),
    authorized_by TEXT DEFAULT 'CEO',
    is_active BOOLEAN DEFAULT TRUE,
    registration_wave TEXT DEFAULT 'ORIGINAL',
    constraints JSONB DEFAULT '{}'::jsonb
);

-- C2: Register all authorized validators
INSERT INTO fhq_learning.pre_tier_validator_authority (validator_ec, validator_name, validator_role, registration_wave)
VALUES
    ('CEIO', 'Chief External Intelligence Officer', 'External data validation', 'ORIGINAL'),
    ('FINN-E', 'FINN Error Repair', 'Error-based hypothesis validation', 'ORIGINAL'),
    ('GN-S', 'Golden Needle Synthesis', 'Signal quality validation', 'ORIGINAL'),
    ('CSEO', 'Chief Strategy & Experimentation Officer', 'Strategic alignment validation', 'G1.5_EXPANSION'),
    ('CRIO', 'Chief Research & Insight Officer', 'Research depth validation', 'G1.5_EXPANSION')
ON CONFLICT (validator_ec) DO UPDATE SET
    is_active = TRUE,
    authorized_at = NOW();

-- C3: Create validator registry view
CREATE OR REPLACE VIEW fhq_learning.v_authorized_validators AS
SELECT
    va.validator_ec,
    va.validator_name,
    va.validator_role,
    va.registration_wave,
    va.is_active,
    va.authorized_at,
    COALESCE(vs.total_validations, 0) as total_validations,
    vs.last_validation
FROM fhq_learning.pre_tier_validator_authority va
LEFT JOIN (
    SELECT
        validator_ec,
        COUNT(*) as total_validations,
        MAX(validation_timestamp) as last_validation
    FROM fhq_learning.pre_tier_validator_scores
    GROUP BY validator_ec
) vs ON va.validator_ec = vs.validator_ec
WHERE va.is_active = TRUE
ORDER BY va.registration_wave, va.validator_ec;

-- ============================================================================
-- SECTION D: G1.5 THROUGHPUT TRACKING UPDATE
-- ============================================================================

-- D0: Drop existing view to allow column changes
DROP VIEW IF EXISTS fhq_learning.v_g1_5_throughput_tracker;

-- D1: Recreate throughput tracker with validator capacity
CREATE VIEW fhq_learning.v_g1_5_throughput_tracker AS
WITH daily_stats AS (
    SELECT
        DATE(created_at AT TIME ZONE 'Europe/Oslo') as stat_date,
        COUNT(*) as hypotheses_generated,
        COUNT(DISTINCT generator_id) as unique_generators,
        AVG(causal_graph_depth) as avg_causal_depth,
        COUNT(*) FILTER (WHERE pre_tier_score_at_birth IS NOT NULL) as scored_hypotheses
    FROM fhq_learning.hypothesis_canon
    WHERE created_at >= '2026-01-25 21:29:00+01'::timestamptz
    GROUP BY DATE(created_at AT TIME ZONE 'Europe/Oslo')
),
baseline AS (
    SELECT
        15.0 as baseline_rate,
        30.0 as target_rate,
        2.0 as baseline_generators,
        3.0 as target_generators,
        1.82 as baseline_depth,
        30 as target_deaths
),
death_progress AS (
    SELECT
        COUNT(*) FILTER (
            WHERE status IN ('FALSIFIED', 'REJECTED', 'EXPIRED')
            AND pre_tier_score_at_birth IS NOT NULL
        ) as deaths_with_score
    FROM fhq_learning.hypothesis_canon
),
validator_capacity AS (
    SELECT COUNT(*) as active_validators
    FROM fhq_learning.pre_tier_validator_authority
    WHERE is_active = TRUE
)
SELECT
    'FHQ-EXP-PRETIER-G1.5' as experiment_id,
    'ACTIVE' as experiment_status,
    '2026-01-25 21:29:00+01'::timestamptz as start_ts,
    '2026-02-08 21:29:00+01'::timestamptz as end_ts,
    EXTRACT(DAY FROM NOW() - '2026-01-25 21:29:00+01'::timestamptz) as days_elapsed,
    GREATEST(0, EXTRACT(DAY FROM '2026-02-08 21:29:00+01'::timestamptz - NOW())) as days_remaining,
    COALESCE((SELECT hypotheses_generated FROM daily_stats WHERE stat_date = CURRENT_DATE), 0) as today_hypotheses,
    COALESCE((SELECT unique_generators FROM daily_stats WHERE stat_date = CURRENT_DATE), 0) as today_generators,
    COALESCE((SELECT avg_causal_depth FROM daily_stats WHERE stat_date = CURRENT_DATE), 0) as today_avg_depth,
    COALESCE((SELECT SUM(hypotheses_generated) FROM daily_stats), 0) as total_hypotheses,
    COALESCE((SELECT AVG(hypotheses_generated) FROM daily_stats), 0) as avg_daily_rate,
    COALESCE((SELECT AVG(unique_generators) FROM daily_stats), 0) as avg_daily_generators,
    COALESCE((SELECT AVG(avg_causal_depth) FROM daily_stats), 0) as avg_causal_depth,
    b.baseline_rate,
    b.target_rate,
    CASE
        WHEN COALESCE((SELECT AVG(hypotheses_generated) FROM daily_stats), 0) >= b.target_rate THEN 'ON_TARGET'
        WHEN COALESCE((SELECT AVG(hypotheses_generated) FROM daily_stats), 0) >= b.baseline_rate * 1.5 THEN 'APPROACHING'
        ELSE 'BELOW_TARGET'
    END as rate_status,
    b.target_generators,
    CASE
        WHEN COALESCE((SELECT AVG(unique_generators) FROM daily_stats), 0) >= b.target_generators THEN 'ON_TARGET'
        ELSE 'BELOW_TARGET'
    END as generator_status,
    d.deaths_with_score,
    b.target_deaths,
    ROUND(100.0 * d.deaths_with_score / b.target_deaths, 1) as death_progress_pct,
    d.deaths_with_score >= b.target_deaths as calibration_trigger_met,
    CASE
        WHEN d.deaths_with_score >= b.target_deaths THEN 'DEATH_TRIGGER'
        WHEN NOW() >= '2026-02-08 21:29:00+01'::timestamptz THEN 'TIME_TRIGGER'
        ELSE 'IN_PROGRESS'
    END as end_trigger_status,
    true as weights_frozen,
    true as thresholds_frozen,
    true as agent_roles_frozen,
    true as oxygen_criteria_frozen,
    -- New: Validator capacity
    vc.active_validators,
    5 as target_validators,
    CASE
        WHEN vc.active_validators >= 5 THEN 'SUFFICIENT'
        WHEN vc.active_validators >= 3 THEN 'ADEQUATE'
        ELSE 'LIMITED'
    END as validator_capacity_status,
    NOW() as computed_at
FROM baseline b
CROSS JOIN death_progress d
CROSS JOIN validator_capacity vc;

-- ============================================================================
-- SECTION E: REGISTER ACTIVATION EVENT
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
    'GENERATOR_ACTIVATION',
    'G1.5_ALPHA_FACTORY',
    'STIG',
    NOW(),
    encode(sha256('ALPHA_FACTORY_ACTIVATION|FINN-E|FINN-T|2026-01-25'::bytea), 'hex'),
    jsonb_build_object(
        'directive', 'CEO-VEDTAK-2026-ALPHA-FACTORY-ACTIVATION',
        'generators_activated', ARRAY['FINN-E', 'FINN-T'],
        'rotation_config', jsonb_build_object(
            'timeframes', ARRAY['15m', '1h', '4h'],
            'asset_rotation', true
        ),
        'stale_threshold_hours', 48,
        'validators_added', ARRAY['CSEO', 'CRIO'],
        'total_validators', 5,
        'rationale', jsonb_build_object(
            'FINN-E', 'Error Repair - low-hanging fruit for sample size',
            'FINN-T', 'Theory/World-Model - high-IQ hypotheses for depth testing'
        )
    ),
    'PENDING_VEGA_ATTESTATION',
    'PENDING_VEGA_ATTESTATION',
    'STIG',
    NOW(),
    'CEO',
    ARRAY['ADR-011', 'ADR-013'],
    'Alpha Factory activation: FINN-E + FINN-T with safe scaling infrastructure',
    true
);

COMMIT;
