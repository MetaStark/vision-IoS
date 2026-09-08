-- GATE 2 POST_FIX DEATH TRACKER
-- CEO-DIR: Single focus on Gate 2 (30+ POST_FIX deaths)
-- Run hourly: psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -f gate2_postfix_tracker.sql

\echo '=============================================='
\echo 'GATE 2 POST_FIX TRACKER'
\echo '=============================================='
SELECT NOW() AT TIME ZONE 'Europe/Oslo' as check_time_oslo;

\echo ''
\echo '--- PRIMARY METRICS ---'
SELECT
    COUNT(*) as postfix_total,
    COUNT(*) FILTER (WHERE pre_tier_score_at_birth IS NOT NULL) as postfix_scored,
    COUNT(*) FILTER (WHERE status = 'ACTIVE') as postfix_active,
    COUNT(*) FILTER (WHERE status = 'FALSIFIED') as postfix_deaths,
    CASE WHEN COUNT(*) FILTER (WHERE status = 'FALSIFIED') >= 30
         THEN 'GATE 2 OPEN - TRIGGER VEGA'
         ELSE 'BLOCKED (' || COUNT(*) FILTER (WHERE status = 'FALSIFIED') || '/30)'
    END as gate_status
FROM fhq_learning.hypothesis_canon
WHERE generation_regime = 'CRYPTO_DIVERSIFIED_POST_FIX';

\echo ''
\echo '--- TIME TO FALSIFICATION (POST_FIX) ---'
SELECT
    COUNT(*) as n_deaths,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY time_to_falsification_hours)::numeric, 2) as median_ttf_hours,
    ROUND(AVG(time_to_falsification_hours)::numeric, 2) as avg_ttf_hours,
    ROUND(MIN(time_to_falsification_hours)::numeric, 2) as min_ttf_hours,
    ROUND(MAX(time_to_falsification_hours)::numeric, 2) as max_ttf_hours
FROM fhq_learning.hypothesis_canon
WHERE generation_regime = 'CRYPTO_DIVERSIFIED_POST_FIX'
AND time_to_falsification_hours IS NOT NULL;

\echo ''
\echo '--- TIER-1 PROCESSING RATE ---'
SELECT
    generation_regime,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE tier1_result IS NOT NULL) as tier1_processed,
    ROUND(100.0 * COUNT(*) FILTER (WHERE tier1_result IS NOT NULL) / NULLIF(COUNT(*), 0), 1) as tier1_rate_pct
FROM fhq_learning.hypothesis_canon
WHERE generation_regime IN ('CRYPTO_DIVERSIFIED_POST_FIX', 'CRYPTO_DEGENERATE_PRE_FIX', 'STANDARD')
GROUP BY generation_regime
ORDER BY generation_regime;

\echo ''
\echo '--- DEATH ELIGIBILITY CHECK ---'
SELECT
    generation_regime,
    COUNT(*) FILTER (WHERE status IN ('DRAFT', 'ACTIVE')) as death_eligible,
    COUNT(*) FILTER (WHERE NOW() > created_at + (expected_timeframe_hours || ' hours')::interval AND status IN ('DRAFT', 'ACTIVE')) as expired_awaiting_death,
    COUNT(*) FILTER (WHERE status = 'FALSIFIED') as already_dead
FROM fhq_learning.hypothesis_canon
WHERE generation_regime = 'CRYPTO_DIVERSIFIED_POST_FIX'
GROUP BY generation_regime;

\echo ''
\echo '--- HOURS UNTIL NEXT DEATHS ---'
SELECT
    COUNT(*) as hypotheses_expiring_next_6h
FROM fhq_learning.hypothesis_canon
WHERE generation_regime = 'CRYPTO_DIVERSIFIED_POST_FIX'
AND status IN ('DRAFT', 'ACTIVE')
AND created_at + (expected_timeframe_hours || ' hours')::interval <= NOW() + INTERVAL '6 hours';

\echo ''
\echo '--- CDS DISTRIBUTION (POST_FIX) ---'
SELECT
    causal_depth_score as cds,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE status = 'FALSIFIED') as deaths
FROM fhq_learning.hypothesis_canon
WHERE generation_regime = 'CRYPTO_DIVERSIFIED_POST_FIX'
GROUP BY causal_depth_score
ORDER BY causal_depth_score;

\echo ''
\echo '=============================================='
\echo 'END GATE 2 TRACKER'
\echo '=============================================='
