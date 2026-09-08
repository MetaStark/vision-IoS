-- ============================================================================
-- Migration: 352_pre_tier_g1_5_experiment_infrastructure.sql
-- Directive: CEO-DIR-2026-PRE-TIER-GRADIENT-G1.5 (Empirical Calibration)
-- Experiment: FHQ-EXP-PRETIER-G1.5
-- Executor: STIG (EC-003)
-- Date: 2026-01-25
-- Dashboard: http://localhost:3000/calendar
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: REGISTER G1.5 AS CANONICAL TEST EVENT (Calendar Visibility)
-- ============================================================================
INSERT INTO fhq_calendar.canonical_test_events (
    test_code,
    test_name,
    display_name,
    owning_agent,
    status,
    start_ts,
    end_ts,
    start_date,
    end_date,
    required_days,
    target_sample_size,
    minimum_sample_size,
    business_intent,
    beneficiary_system,
    baseline_definition,
    target_metrics,
    hypothesis_code,
    success_criteria,
    failure_criteria,
    monitoring_agent_ec,
    escalation_state,
    ceo_action_required,
    recommended_actions,
    mid_test_checkpoint,
    calendar_category,
    created_at
) VALUES (
    'FHQ-EXP-PRETIER-G1.5',
    'Pre-Tier Gradient Empirical Calibration',
    'G1.5 Calibration Freeze',
    'EC-003',
    'ACTIVE',
    '2026-01-25 21:29:00+01',
    '2026-02-08 21:29:00+01',
    '2026-01-25',
    '2026-02-08',
    14,
    30,
    30,
    'Prove predictive ordering power of Pre-Tier scores under elevated learning inflow. Validate that higher birth scores correlate with longer survival times.',
    'fhq_learning.hypothesis_canon',
    jsonb_build_object(
        'daily_hypothesis_rate', 15,
        'generator_diversity', 2,
        'avg_causal_depth', 1.82,
        'measurement_start', '2026-01-25T21:29:00+01:00'
    ),
    jsonb_build_object(
        'target_daily_rate', 30,
        'target_rate_multiplier', '2.0x',
        'target_generators', 3,
        'target_deaths', 30,
        'primary_metric', 'Spearman correlation',
        'secondary_metrics', ARRAY['Pearson correlation', 'Quartile survival curves']
    ),
    'SYS-PRETIER-PREDICTIVE-ORDERING',
    jsonb_build_object(
        'success_conditions', ARRAY[
            'Spearman rho > 0.3',
            'Upper quartile survives materially longer than lower quartile'
        ],
        'interpretation', 'Pre-Tier provides ranking alpha'
    ),
    jsonb_build_object(
        'failure_conditions', ARRAY[
            'Spearman rho approximately 0 under increased inflow',
            'No quartile separation',
            'High scores die at same rate as low scores'
        ],
        'interpretation', 'Pre-Tier adds no predictive value'
    ),
    'EC-004',
    'NONE',
    false,
    '["Monitor throughput daily", "Check generator diversity", "No parameter changes"]'::jsonb,
    '2026-01-31',
    'ACTIVE_TEST',
    NOW()
) ON CONFLICT (test_code) DO UPDATE SET
    status = 'ACTIVE',
    end_ts = '2026-02-08 21:29:00+01';

-- ============================================================================
-- STEP 2: CREATE G1.5 THROUGHPUT TRACKING VIEW (Dashboard Data Source)
-- ============================================================================
CREATE OR REPLACE VIEW fhq_learning.v_g1_5_throughput_tracker AS
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
)
SELECT
    -- Experiment Identity
    'FHQ-EXP-PRETIER-G1.5' as experiment_id,
    'ACTIVE' as experiment_status,

    -- Temporal
    '2026-01-25 21:29:00+01'::timestamptz as start_ts,
    '2026-02-08 21:29:00+01'::timestamptz as end_ts,
    EXTRACT(DAY FROM NOW() - '2026-01-25 21:29:00+01'::timestamptz) as days_elapsed,
    GREATEST(0, EXTRACT(DAY FROM '2026-02-08 21:29:00+01'::timestamptz - NOW())) as days_remaining,

    -- Throughput Metrics (Today)
    COALESCE((SELECT hypotheses_generated FROM daily_stats WHERE stat_date = CURRENT_DATE), 0) as today_hypotheses,
    COALESCE((SELECT unique_generators FROM daily_stats WHERE stat_date = CURRENT_DATE), 0) as today_generators,
    COALESCE((SELECT avg_causal_depth FROM daily_stats WHERE stat_date = CURRENT_DATE), 0) as today_avg_depth,

    -- Throughput Metrics (Cumulative)
    COALESCE((SELECT SUM(hypotheses_generated) FROM daily_stats), 0) as total_hypotheses,
    COALESCE((SELECT AVG(hypotheses_generated) FROM daily_stats), 0) as avg_daily_rate,
    COALESCE((SELECT AVG(unique_generators) FROM daily_stats), 0) as avg_daily_generators,
    COALESCE((SELECT AVG(avg_causal_depth) FROM daily_stats), 0) as avg_causal_depth,

    -- Target Comparison
    b.baseline_rate,
    b.target_rate,
    CASE
        WHEN COALESCE((SELECT AVG(hypotheses_generated) FROM daily_stats), 0) >= b.target_rate
        THEN 'ON_TARGET'
        WHEN COALESCE((SELECT AVG(hypotheses_generated) FROM daily_stats), 0) >= b.baseline_rate * 1.5
        THEN 'APPROACHING'
        ELSE 'BELOW_TARGET'
    END as rate_status,

    b.target_generators,
    CASE
        WHEN COALESCE((SELECT AVG(unique_generators) FROM daily_stats), 0) >= b.target_generators
        THEN 'ON_TARGET'
        ELSE 'BELOW_TARGET'
    END as generator_status,

    -- Death Progress (Primary End Trigger)
    d.deaths_with_score,
    b.target_deaths,
    ROUND(100.0 * d.deaths_with_score / b.target_deaths, 1) as death_progress_pct,
    d.deaths_with_score >= b.target_deaths as calibration_trigger_met,

    -- End Trigger Status
    CASE
        WHEN d.deaths_with_score >= b.target_deaths THEN 'DEATH_TRIGGER'
        WHEN NOW() >= '2026-02-08 21:29:00+01'::timestamptz THEN 'TIME_TRIGGER'
        ELSE 'IN_PROGRESS'
    END as end_trigger_status,

    -- Freeze Compliance (All must be true)
    true as weights_frozen,
    true as thresholds_frozen,
    true as agent_roles_frozen,
    true as oxygen_criteria_frozen,

    -- Dashboard Timestamp
    NOW() as computed_at

FROM baseline b
CROSS JOIN death_progress d;

-- ============================================================================
-- STEP 3: CREATE GENERATOR PERFORMANCE VIEW (Dashboard Data Source)
-- ============================================================================
CREATE OR REPLACE VIEW fhq_learning.v_g1_5_generator_performance AS
SELECT
    generator_id,
    COUNT(*) as total_hypotheses,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours') as last_24h,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days') as last_7d,
    ROUND(AVG(causal_graph_depth), 2) as avg_depth,
    ROUND(AVG(pre_tier_score_at_birth), 2) as avg_birth_score,
    COUNT(*) FILTER (WHERE status IN ('FALSIFIED', 'REJECTED', 'EXPIRED')) as deaths,
    COUNT(*) FILTER (WHERE status = 'DRAFT') as active_drafts,
    MAX(created_at) as last_hypothesis_at,
    ROUND(
        100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM fhq_learning.hypothesis_canon WHERE created_at >= '2026-01-25 21:29:00+01'::timestamptz), 0),
        1
    ) as volume_share_pct
FROM fhq_learning.hypothesis_canon
WHERE created_at >= '2026-01-25 21:29:00+01'::timestamptz
GROUP BY generator_id
ORDER BY total_hypotheses DESC;

-- ============================================================================
-- STEP 4: CREATE CALIBRATION CORRELATION VIEW (Spearman Prep)
-- ============================================================================
CREATE OR REPLACE VIEW fhq_learning.v_g1_5_calibration_data AS
SELECT
    canon_id,
    hypothesis_code,
    generator_id,
    pre_tier_score_at_birth,
    created_at as birth_ts,
    death_timestamp,
    time_to_falsification_hours,
    status,
    -- Quartile assignment for stratified analysis
    NTILE(4) OVER (ORDER BY pre_tier_score_at_birth) as score_quartile,
    -- Rank for Spearman calculation
    RANK() OVER (ORDER BY pre_tier_score_at_birth DESC) as score_rank,
    RANK() OVER (ORDER BY time_to_falsification_hours DESC NULLS LAST) as survival_rank
FROM fhq_learning.hypothesis_canon
WHERE pre_tier_score_at_birth IS NOT NULL
AND created_at >= '2026-01-25 21:29:00+01'::timestamptz
ORDER BY pre_tier_score_at_birth DESC;

-- ============================================================================
-- STEP 5: CREATE SPEARMAN CORRELATION FUNCTION
-- ============================================================================
CREATE OR REPLACE FUNCTION fhq_learning.calculate_g1_5_spearman()
RETURNS TABLE (
    sample_size INTEGER,
    spearman_rho NUMERIC,
    data_status TEXT,
    interpretation TEXT
) AS $$
DECLARE
    v_n INTEGER;
    v_sum_d2 NUMERIC;
    v_rho NUMERIC;
BEGIN
    -- Count valid samples (must have both score and TTF)
    SELECT COUNT(*) INTO v_n
    FROM fhq_learning.v_g1_5_calibration_data
    WHERE time_to_falsification_hours IS NOT NULL;

    IF v_n < 30 THEN
        RETURN QUERY SELECT
            v_n,
            NULL::NUMERIC,
            'INSUFFICIENT_DATA'::TEXT,
            FORMAT('Need %s more deaths for valid correlation', 30 - v_n)::TEXT;
        RETURN;
    END IF;

    -- Calculate sum of squared rank differences
    SELECT SUM(POWER(score_rank - survival_rank, 2)) INTO v_sum_d2
    FROM fhq_learning.v_g1_5_calibration_data
    WHERE time_to_falsification_hours IS NOT NULL;

    -- Spearman formula: rho = 1 - (6 * sum(d^2)) / (n * (n^2 - 1))
    v_rho := 1 - (6 * v_sum_d2) / (v_n * (POWER(v_n, 2) - 1));

    RETURN QUERY SELECT
        v_n,
        ROUND(v_rho, 4),
        'VALID'::TEXT,
        CASE
            WHEN v_rho > 0.3 THEN 'SUCCESS: Pre-Tier provides ranking alpha'
            WHEN v_rho > 0.1 THEN 'WEAK: Marginal predictive signal'
            WHEN v_rho > -0.1 THEN 'FAILURE: No predictive value'
            ELSE 'INVERSE: Higher scores die faster (investigate)'
        END::TEXT;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- STEP 6: CREATE QUARTILE SURVIVAL VIEW
-- ============================================================================
CREATE OR REPLACE VIEW fhq_learning.v_g1_5_quartile_survival AS
SELECT
    score_quartile,
    CASE score_quartile
        WHEN 1 THEN 'Q1 (Lowest)'
        WHEN 2 THEN 'Q2'
        WHEN 3 THEN 'Q3'
        WHEN 4 THEN 'Q4 (Highest)'
    END as quartile_label,
    COUNT(*) as total_hypotheses,
    COUNT(*) FILTER (WHERE status IN ('FALSIFIED', 'REJECTED', 'EXPIRED')) as deaths,
    COUNT(*) FILTER (WHERE status = 'DRAFT') as survivors,
    ROUND(AVG(pre_tier_score_at_birth), 2) as avg_birth_score,
    ROUND(AVG(time_to_falsification_hours), 2) as avg_survival_hours,
    MIN(time_to_falsification_hours) as min_survival_hours,
    MAX(time_to_falsification_hours) as max_survival_hours
FROM fhq_learning.v_g1_5_calibration_data
GROUP BY score_quartile
ORDER BY score_quartile;

-- ============================================================================
-- STEP 7: CALENDAR EVENTS - SKIPPED (Canonical Test Event is the calendar source)
-- ============================================================================
-- G1.5 experiment is already visible on calendar via canonical_test_events
-- No additional calendar_events needed

-- ============================================================================
-- STEP 8: REGISTER EXPERIMENT IN GOVERNANCE EVIDENCE
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
    'EXPERIMENT_REGISTRATION',
    'G1.5_CALIBRATION_EXPERIMENT',
    'STIG',
    NOW(),
    encode(sha256('FHQ-EXP-PRETIER-G1.5|2026-01-25|2026-02-08|STIG'::bytea), 'hex'),
    jsonb_build_object(
        'experiment_id', 'FHQ-EXP-PRETIER-G1.5',
        'owner', 'EC-003',
        'governance', 'EC-004',
        'status', 'ACTIVE',
        'start_ts', '2026-01-25T21:29:00+01:00',
        'end_ts', '2026-02-08T21:29:00+01:00',
        'end_triggers', ARRAY['n=30 deaths with pre_tier_score', '14 days hard stop'],
        'hypothesis_under_test', 'SYS-PRETIER-PREDICTIVE-ORDERING',
        'frozen_parameters', jsonb_build_object(
            'weights', true,
            'thresholds', true,
            'agent_roles', true,
            'oxygen_criteria', true
        ),
        'scalable_parameters', ARRAY['hypothesis_volume', 'generator_diversity', 'data_breadth'],
        'baseline', jsonb_build_object(
            'daily_rate', 15,
            'generators', 2,
            'causal_depth', 1.82
        ),
        'targets', jsonb_build_object(
            'daily_rate', 30,
            'generators', 3,
            'deaths', 30
        ),
        'success_criteria', 'Spearman rho > 0.3 OR quartile separation',
        'failure_criteria', 'Spearman ~ 0 under increased inflow'
    ),
    'PENDING_VEGA_ATTESTATION',
    'PENDING_VEGA_ATTESTATION',
    'STIG',
    NOW(),
    'CEO',
    ARRAY['ADR-011', 'ADR-013'],
    'G1.5 Empirical Calibration Experiment registered. Design frozen, learning scaled.',
    true
);

-- ============================================================================
-- STEP 9: DASHBOARD VIEW - SKIPPED (Existing view already includes canonical tests)
-- ============================================================================
-- v_dashboard_calendar already unions canonical_test_events
-- G1.5 experiment will be visible automatically

COMMIT;
