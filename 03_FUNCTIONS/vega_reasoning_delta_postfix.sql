-- VEGA REASONING DELTA - POST_FIX ONLY
-- CEO-DIR: Triggered when POST_FIX deaths >= 30
-- Primary: Spearman correlation
-- Secondary: Pearson correlation
-- Exclusion: PRE_FIX explicitly excluded from evaluation set

\echo '=============================================='
\echo 'VEGA REASONING DELTA - POST_FIX ANALYSIS'
\echo '=============================================='
SELECT NOW() AT TIME ZONE 'Europe/Oslo' as analysis_time_oslo;

\echo ''
\echo '--- GATE 2 STATUS CHECK ---'
SELECT
    COUNT(*) FILTER (WHERE status = 'FALSIFIED') as postfix_deaths,
    CASE WHEN COUNT(*) FILTER (WHERE status = 'FALSIFIED') >= 30
         THEN 'GATE 2 OPEN - ANALYSIS VALID'
         ELSE 'GATE 2 BLOCKED - ANALYSIS INVALID'
    END as gate_status
FROM fhq_learning.hypothesis_canon
WHERE generation_regime = 'CRYPTO_DIVERSIFIED_POST_FIX';

\echo ''
\echo '!!! EXPLICIT EXCLUSION: PRE_FIX data excluded from evaluation set !!!'
\echo ''

\echo '--- PRIMARY METRIC: SPEARMAN CORRELATION (pre_tier_score vs TTF) ---'
WITH ranked AS (
    SELECT
        pre_tier_score_at_birth,
        time_to_falsification_hours,
        RANK() OVER (ORDER BY pre_tier_score_at_birth) as score_rank,
        RANK() OVER (ORDER BY time_to_falsification_hours) as ttf_rank
    FROM fhq_learning.hypothesis_canon
    WHERE generation_regime = 'CRYPTO_DIVERSIFIED_POST_FIX'  -- POST_FIX ONLY
    AND pre_tier_score_at_birth IS NOT NULL
    AND time_to_falsification_hours IS NOT NULL
)
SELECT
    ROUND(CORR(score_rank, ttf_rank)::numeric, 4) as spearman_rho,
    COUNT(*) as n,
    CASE
        WHEN CORR(score_rank, ttf_rank) > 0.3 THEN 'POSITIVE (desired)'
        WHEN CORR(score_rank, ttf_rank) > 0 THEN 'WEAK POSITIVE'
        WHEN CORR(score_rank, ttf_rank) > -0.3 THEN 'WEAK NEGATIVE'
        ELSE 'NEGATIVE (inverted)'
    END as interpretation
FROM ranked;

\echo ''
\echo '--- SECONDARY METRIC: PEARSON CORRELATION (pre_tier_score vs TTF) ---'
SELECT
    ROUND(CORR(pre_tier_score_at_birth, time_to_falsification_hours)::numeric, 4) as pearson_r,
    COUNT(*) as n
FROM fhq_learning.hypothesis_canon
WHERE generation_regime = 'CRYPTO_DIVERSIFIED_POST_FIX'  -- POST_FIX ONLY
AND pre_tier_score_at_birth IS NOT NULL
AND time_to_falsification_hours IS NOT NULL;

\echo ''
\echo '--- COMPONENT CORRELATIONS (E, C, F, A vs TTF) ---'
\echo 'E = Evidence Density, C = Causal Depth, F = Data Freshness, A = Cross-Agent Agreement'
SELECT
    'evidence_density_score' as component,
    ROUND(CORR(evidence_density_score, time_to_falsification_hours)::numeric, 4) as pearson_r,
    COUNT(*) as n
FROM fhq_learning.hypothesis_canon
WHERE generation_regime = 'CRYPTO_DIVERSIFIED_POST_FIX'
AND evidence_density_score IS NOT NULL
AND time_to_falsification_hours IS NOT NULL
UNION ALL
SELECT
    'causal_depth_score' as component,
    ROUND(CORR(causal_depth_score, time_to_falsification_hours)::numeric, 4) as pearson_r,
    COUNT(*) as n
FROM fhq_learning.hypothesis_canon
WHERE generation_regime = 'CRYPTO_DIVERSIFIED_POST_FIX'
AND causal_depth_score IS NOT NULL
AND time_to_falsification_hours IS NOT NULL
UNION ALL
SELECT
    'data_freshness_score' as component,
    ROUND(CORR(data_freshness_score, time_to_falsification_hours)::numeric, 4) as pearson_r,
    COUNT(*) as n
FROM fhq_learning.hypothesis_canon
WHERE generation_regime = 'CRYPTO_DIVERSIFIED_POST_FIX'
AND data_freshness_score IS NOT NULL
AND time_to_falsification_hours IS NOT NULL
UNION ALL
SELECT
    'cross_agent_agreement' as component,
    ROUND(CORR(cross_agent_agreement_score, time_to_falsification_hours)::numeric, 4) as pearson_r,
    COUNT(*) as n
FROM fhq_learning.hypothesis_canon
WHERE generation_regime = 'CRYPTO_DIVERSIFIED_POST_FIX'
AND cross_agent_agreement_score IS NOT NULL
AND time_to_falsification_hours IS NOT NULL;

\echo ''
\echo '--- GENERATOR-STRATIFIED RESULTS ---'
SELECT
    generator_id,
    COUNT(*) as deaths,
    ROUND(AVG(time_to_falsification_hours)::numeric, 2) as avg_ttf,
    ROUND(CORR(pre_tier_score_at_birth, time_to_falsification_hours)::numeric, 4) as pearson_r
FROM fhq_learning.hypothesis_canon
WHERE generation_regime = 'CRYPTO_DIVERSIFIED_POST_FIX'
AND pre_tier_score_at_birth IS NOT NULL
AND time_to_falsification_hours IS NOT NULL
GROUP BY generator_id
ORDER BY deaths DESC;

\echo ''
\echo '--- CDS-STRATIFIED TTF ---'
SELECT
    causal_depth_score as cds,
    COUNT(*) as deaths,
    ROUND(AVG(time_to_falsification_hours)::numeric, 2) as avg_ttf,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY time_to_falsification_hours)::numeric, 2) as median_ttf
FROM fhq_learning.hypothesis_canon
WHERE generation_regime = 'CRYPTO_DIVERSIFIED_POST_FIX'
AND time_to_falsification_hours IS NOT NULL
GROUP BY causal_depth_score
ORDER BY causal_depth_score;

\echo ''
\echo '=============================================='
\echo 'VEGA ATTESTATION STATEMENT'
\echo '=============================================='
\echo 'This analysis uses ONLY POST_FIX data (generation_regime = CRYPTO_DIVERSIFIED_POST_FIX)'
\echo 'PRE_FIX data (CRYPTO_DEGENERATE_PRE_FIX) is EXPLICITLY EXCLUDED'
\echo 'Reason: PRE_FIX had degenerate inputs (constant CDS = 75.00)'
\echo '=============================================='
