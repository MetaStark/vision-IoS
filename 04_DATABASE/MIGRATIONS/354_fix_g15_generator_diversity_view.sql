-- ============================================================================
-- Migration: 354_fix_g15_generator_diversity_view.sql
-- Directive: CEO-DIR-2026-FIX-GENERATOR-DIVERSITY
-- Issue: Dashboard shows Generator Diversity 2.0 when 3 generators are active
-- Root Cause: View uses AVG(daily_unique_generators) instead of total unique
-- Fix: Add total_unique_generators field and use it for status calculation
-- Executor: STIG (EC-003)
-- Date: 2026-01-26
-- ============================================================================

BEGIN;

-- ============================================================================
-- FIX: Recreate v_g1_5_throughput_tracker with correct generator diversity
-- Must DROP first because we're adding a new column
-- ============================================================================
DROP VIEW IF EXISTS fhq_learning.v_g1_5_throughput_tracker CASCADE;

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
    WHERE is_active = true
),
-- FIX: Total unique generators since G1.5 start (not daily average)
total_generators AS (
    SELECT COUNT(DISTINCT generator_id) as total_unique_generators
    FROM fhq_learning.hypothesis_canon
    WHERE created_at >= '2026-01-25 21:29:00+01'::timestamptz
)
SELECT
    'FHQ-EXP-PRETIER-G1.5' as experiment_id,
    'ACTIVE' as experiment_status,
    '2026-01-25 21:29:00+01'::timestamptz as start_ts,
    '2026-02-08 21:29:00+01'::timestamptz as end_ts,
    EXTRACT(DAY FROM NOW() - '2026-01-25 21:29:00+01'::timestamptz) as days_elapsed,
    GREATEST(0, EXTRACT(DAY FROM '2026-02-08 21:29:00+01'::timestamptz - NOW())) as days_remaining,

    -- Today's metrics
    COALESCE((SELECT hypotheses_generated FROM daily_stats WHERE stat_date = CURRENT_DATE), 0) as today_hypotheses,
    COALESCE((SELECT unique_generators FROM daily_stats WHERE stat_date = CURRENT_DATE), 0) as today_generators,
    COALESCE((SELECT avg_causal_depth FROM daily_stats WHERE stat_date = CURRENT_DATE), 0) as today_avg_depth,

    -- Cumulative metrics
    COALESCE((SELECT SUM(hypotheses_generated) FROM daily_stats), 0) as total_hypotheses,
    COALESCE((SELECT AVG(hypotheses_generated) FROM daily_stats), 0) as avg_daily_rate,
    COALESCE((SELECT AVG(unique_generators) FROM daily_stats), 0) as avg_daily_generators,
    tg.total_unique_generators,  -- NEW FIELD: Total distinct generators since G1.5 start
    COALESCE((SELECT AVG(avg_causal_depth) FROM daily_stats), 0) as avg_causal_depth,

    -- Baseline comparison
    b.baseline_rate,
    b.target_rate,
    CASE
        WHEN COALESCE((SELECT AVG(hypotheses_generated) FROM daily_stats), 0) >= b.target_rate THEN 'ON_TARGET'
        WHEN COALESCE((SELECT AVG(hypotheses_generated) FROM daily_stats), 0) >= b.baseline_rate * 1.5 THEN 'APPROACHING'
        ELSE 'BELOW_TARGET'
    END as rate_status,

    b.target_generators,
    -- FIX: Use total_unique_generators instead of avg_daily_generators for status
    CASE
        WHEN tg.total_unique_generators >= b.target_generators THEN 'ON_TARGET'
        ELSE 'BELOW_TARGET'
    END as generator_status,

    -- Death progress
    d.deaths_with_score,
    b.target_deaths,
    ROUND(100.0 * d.deaths_with_score / b.target_deaths, 1) as death_progress_pct,
    d.deaths_with_score >= b.target_deaths as calibration_trigger_met,

    CASE
        WHEN d.deaths_with_score >= b.target_deaths THEN 'DEATH_TRIGGER'
        WHEN NOW() >= '2026-02-08 21:29:00+01'::timestamptz THEN 'TIME_TRIGGER'
        ELSE 'IN_PROGRESS'
    END as end_trigger_status,

    -- Freeze compliance
    true as weights_frozen,
    true as thresholds_frozen,
    true as agent_roles_frozen,
    true as oxygen_criteria_frozen,

    -- Validator capacity
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
CROSS JOIN validator_capacity vc
CROSS JOIN total_generators tg;

-- ============================================================================
-- EVIDENCE: Register migration
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
    'VIEW_FIX',
    'STIG',
    NOW(),
    encode(sha256('354_fix_g15_generator_diversity_view|2026-01-26|STIG'::bytea), 'hex'),
    jsonb_build_object(
        'migration', '354_fix_g15_generator_diversity_view.sql',
        'issue', 'Generator Diversity showing 2.0 instead of 3.0',
        'root_cause', 'View used AVG(daily_unique_generators) which averaged Day1(1) + Day2(3) = 2.0',
        'fix', 'Added total_unique_generators field counting DISTINCT generators since G1.5 start',
        'verification', 'Dashboard should now show 3.0 / 3 target = ON_TARGET'
    ),
    'PENDING_VEGA_ATTESTATION',
    'PENDING_VEGA_ATTESTATION',
    'STIG',
    NOW(),
    'CEO',
    ARRAY['ADR-011', 'ADR-013'],
    'Fix for G1.5 Generator Diversity dashboard discrepancy',
    true
);

COMMIT;
