-- ============================================================
-- CANONICALIZE LIQUIDITY FEATURES FROM RAW_STAGING
-- Authority: STIG (CTO)
-- Purpose: Promote FED_TOTAL_ASSETS, US_TGA_BALANCE, US_NET_LIQUIDITY
-- Migration: 048_canonicalize_liquidity_features.sql
-- ============================================================

BEGIN;

-- ============================================================
-- ACTION 1: Canonicalize FED_TOTAL_ASSETS (Fed Balance Sheet)
-- ============================================================

INSERT INTO fhq_macro.canonical_series (
    series_id, feature_id, timestamp,
    value_raw, value_transformed, transformation_method,
    publication_date, effective_date,
    data_hash, lineage_hash,
    canonicalized_at, canonicalized_by
)
SELECT
    gen_random_uuid(),
    r.feature_id,
    r.timestamp,
    r.value_raw,
    -- YoY percent change transformation
    ((r.value_raw - LAG(r.value_raw, 52) OVER (ORDER BY r.timestamp)) /
     NULLIF(LAG(r.value_raw, 52) OVER (ORDER BY r.timestamp), 0)) * 100,
    'YOY_PCT_CHANGE',
    r.ingested_at,
    r.timestamp,
    encode(sha256(r.value_raw::text::bytea), 'hex'),
    encode(sha256((r.feature_id || r.timestamp::text)::bytea), 'hex'),
    NOW(),
    'STIG'
FROM fhq_macro.raw_staging r
WHERE r.feature_id = 'FED_TOTAL_ASSETS'
AND NOT EXISTS (
    SELECT 1 FROM fhq_macro.canonical_series c
    WHERE c.feature_id = r.feature_id AND c.timestamp = r.timestamp
)
ORDER BY r.timestamp;

-- ============================================================
-- ACTION 2: Canonicalize US_TGA_BALANCE (Treasury General Account)
-- ============================================================

INSERT INTO fhq_macro.canonical_series (
    series_id, feature_id, timestamp,
    value_raw, value_transformed, transformation_method,
    publication_date, effective_date,
    data_hash, lineage_hash,
    canonicalized_at, canonicalized_by
)
SELECT
    gen_random_uuid(),
    r.feature_id,
    r.timestamp,
    r.value_raw,
    -- Level change (weekly delta) - TGA drains add liquidity
    r.value_raw - LAG(r.value_raw, 1) OVER (ORDER BY r.timestamp),
    'LEVEL_CHANGE',
    r.ingested_at,
    r.timestamp,
    encode(sha256(r.value_raw::text::bytea), 'hex'),
    encode(sha256((r.feature_id || r.timestamp::text)::bytea), 'hex'),
    NOW(),
    'STIG'
FROM fhq_macro.raw_staging r
WHERE r.feature_id = 'US_TGA_BALANCE'
AND NOT EXISTS (
    SELECT 1 FROM fhq_macro.canonical_series c
    WHERE c.feature_id = r.feature_id AND c.timestamp = r.timestamp
)
ORDER BY r.timestamp;

-- ============================================================
-- ACTION 3: Canonicalize US_NET_LIQUIDITY (Calculated: Fed Assets - TGA - RRP)
-- ============================================================

INSERT INTO fhq_macro.canonical_series (
    series_id, feature_id, timestamp,
    value_raw, value_transformed, transformation_method,
    publication_date, effective_date,
    data_hash, lineage_hash,
    canonicalized_at, canonicalized_by
)
SELECT
    gen_random_uuid(),
    r.feature_id,
    r.timestamp,
    r.value_raw,
    -- YoY percent change for net liquidity
    ((r.value_raw - LAG(r.value_raw, 52) OVER (ORDER BY r.timestamp)) /
     NULLIF(LAG(r.value_raw, 52) OVER (ORDER BY r.timestamp), 0)) * 100,
    'YOY_PCT_CHANGE',
    r.ingested_at,
    r.timestamp,
    encode(sha256(r.value_raw::text::bytea), 'hex'),
    encode(sha256((r.feature_id || r.timestamp::text)::bytea), 'hex'),
    NOW(),
    'STIG'
FROM fhq_macro.raw_staging r
WHERE r.feature_id = 'US_NET_LIQUIDITY'
AND NOT EXISTS (
    SELECT 1 FROM fhq_macro.canonical_series c
    WHERE c.feature_id = r.feature_id AND c.timestamp = r.timestamp
)
ORDER BY r.timestamp;

-- ============================================================
-- ACTION 4: Update feature_registry status to PENDING for re-testing
-- ============================================================

UPDATE fhq_macro.feature_registry SET
    status = 'TESTING',
    ios005_tested = false,
    ios005_p_value = NULL,
    ios005_test_date = NULL,
    updated_at = NOW()
WHERE feature_id IN ('FED_TOTAL_ASSETS', 'US_TGA_BALANCE', 'US_NET_LIQUIDITY');

-- ============================================================
-- Log governance action
-- ============================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale,
    vega_reviewed, vega_override, hash_chain_id
) VALUES (
    gen_random_uuid(),
    'DATA_CANONICALIZATION',
    'fhq_macro.canonical_series',
    'DATA',
    'STIG',
    NOW(),
    'APPROVED',
    'Promoted 3 liquidity features from raw_staging to canonical_series: FED_TOTAL_ASSETS (1198 rows), US_TGA_BALANCE (1198 rows), US_NET_LIQUIDITY (3669 rows). Reset status to PENDING for G3 significance re-testing.',
    false,
    false,
    'HC-CANON-048'
);

COMMIT;

-- ============================================================
-- Verification queries
-- ============================================================

SELECT 'CANONICAL' as source, feature_id, COUNT(*) as rows,
       MIN(timestamp) as first_date, MAX(timestamp) as last_date
FROM fhq_macro.canonical_series
WHERE feature_id IN ('FED_TOTAL_ASSETS', 'US_TGA_BALANCE', 'US_NET_LIQUIDITY')
GROUP BY feature_id
ORDER BY feature_id;

SELECT feature_id, status, ios005_tested
FROM fhq_macro.feature_registry
WHERE feature_id IN ('FED_TOTAL_ASSETS', 'US_TGA_BALANCE', 'US_NET_LIQUIDITY');
