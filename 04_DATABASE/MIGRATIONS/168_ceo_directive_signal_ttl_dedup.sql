-- ============================================================================
-- Migration 168: CEO Directive - Signal TTL & Deduplication
-- ============================================================================
-- Directive: CEO-DIRECTIVE-2025-12-25-TTL-DEDUP
-- Implements MDLC Phase 6 (TTL) and Phase 4 (Governance) controls
--
-- Changes:
--   1. expected_timeframe_days: NOT NULL DEFAULT 7
--   2. dedup_hash column for duplicate detection
--   3. TTL extension governance table
--   4. Expire stale signals function
--   5. Deduplicate backlog function
--   6. Daily dormant signals report view
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Retroactive TTL Assignment
-- ============================================================================
-- Set default TTL for all existing signals without one

UPDATE fhq_canonical.golden_needles
SET expected_timeframe_days = 7
WHERE expected_timeframe_days IS NULL;

-- Log this action
INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata,
    agent_id,
    timestamp
) VALUES (
    gen_random_uuid(),
    'SCHEMA_MODIFICATION',
    'fhq_canonical.golden_needles.expected_timeframe_days',
    'COLUMN',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO Directive 2025-12-25: Retroactive TTL=7 for all NULL values per MDLC Phase 6 compliance',
    jsonb_build_object(
        'directive_id', 'CEO-DIRECTIVE-2025-12-25-TTL-DEDUP',
        'affected_rows', (SELECT COUNT(*) FROM fhq_canonical.golden_needles WHERE expected_timeframe_days = 7),
        'default_ttl_days', 7
    ),
    'STIG',
    NOW()
);

-- ============================================================================
-- STEP 2: Schema Modification - NOT NULL DEFAULT 7
-- ============================================================================

ALTER TABLE fhq_canonical.golden_needles
ALTER COLUMN expected_timeframe_days SET DEFAULT 7;

ALTER TABLE fhq_canonical.golden_needles
ALTER COLUMN expected_timeframe_days SET NOT NULL;

-- ============================================================================
-- STEP 3: Add Dedup Hash Column
-- ============================================================================
-- Hash formula: SHA256(hypothesis_title || target_asset || regime_technical)

ALTER TABLE fhq_canonical.golden_needles
ADD COLUMN IF NOT EXISTS dedup_hash TEXT;

-- Populate dedup_hash for existing records
UPDATE fhq_canonical.golden_needles
SET dedup_hash = encode(
    sha256(
        (COALESCE(hypothesis_title, '') || '|' ||
         COALESCE(target_asset, '') || '|' ||
         COALESCE(regime_technical, ''))::bytea
    ),
    'hex'
)
WHERE dedup_hash IS NULL;

-- Create index for fast dedup lookups
CREATE INDEX IF NOT EXISTS idx_golden_needles_dedup_hash
ON fhq_canonical.golden_needles(dedup_hash);

-- ============================================================================
-- STEP 4: TTL Extension Governance Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_canonical.g5_ttl_extension_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    needle_id UUID NOT NULL REFERENCES fhq_canonical.golden_needles(needle_id),
    original_ttl_days INTEGER NOT NULL,
    requested_ttl_days INTEGER NOT NULL,
    extension_reason TEXT NOT NULL,

    -- LARS signature (strategist)
    lars_requested_at TIMESTAMPTZ,
    lars_signature TEXT,
    lars_approved BOOLEAN DEFAULT FALSE,

    -- VEGA signature (governance)
    vega_reviewed_at TIMESTAMPTZ,
    vega_signature TEXT,
    vega_approved BOOLEAN DEFAULT FALSE,

    -- STIG activation
    stig_activated_at TIMESTAMPTZ,
    stig_signature TEXT,
    is_active BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for pending requests
CREATE INDEX IF NOT EXISTS idx_ttl_extension_pending
ON fhq_canonical.g5_ttl_extension_requests(needle_id)
WHERE is_active = FALSE;

-- ============================================================================
-- STEP 5: Expire Stale Signals Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_canonical.expire_stale_signals()
RETURNS TABLE (
    expired_count INTEGER,
    oldest_expired TIMESTAMPTZ,
    newest_expired TIMESTAMPTZ
) AS $$
DECLARE
    v_expired_count INTEGER;
    v_oldest TIMESTAMPTZ;
    v_newest TIMESTAMPTZ;
BEGIN
    -- Mark signals as EXPIRED where created_at + TTL < NOW()
    WITH expired AS (
        UPDATE fhq_canonical.g5_signal_state ss
        SET
            current_state = 'EXPIRED',
            last_transition = 'DORMANT->EXPIRED',
            last_transition_at = NOW(),
            updated_at = NOW()
        FROM fhq_canonical.golden_needles gn
        WHERE ss.needle_id = gn.needle_id
          AND ss.current_state = 'DORMANT'
          AND gn.created_at + (gn.expected_timeframe_days || ' days')::INTERVAL < NOW()
        RETURNING ss.needle_id, gn.created_at
    )
    SELECT
        COUNT(*)::INTEGER,
        MIN(created_at),
        MAX(created_at)
    INTO v_expired_count, v_oldest, v_newest
    FROM expired;

    -- Log to governance
    IF v_expired_count > 0 THEN
        INSERT INTO fhq_governance.governance_actions_log (
            action_id,
            action_type,
            action_target,
            action_target_type,
            initiated_by,
            initiated_at,
            decision,
            decision_rationale,
            metadata,
            agent_id,
            timestamp
        ) VALUES (
            gen_random_uuid(),
            'SIGNAL_EXPIRATION',
            'fhq_canonical.g5_signal_state',
            'BATCH_UPDATE',
            'STIG',
            NOW(),
            'EXECUTED',
            'Automated TTL expiration per CEO Directive 2025-12-25',
            jsonb_build_object(
                'expired_count', v_expired_count,
                'oldest_signal', v_oldest,
                'newest_signal', v_newest,
                'ttl_policy', 'created_at + expected_timeframe_days < NOW()'
            ),
            'STIG',
            NOW()
        );
    END IF;

    RETURN QUERY SELECT v_expired_count, v_oldest, v_newest;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STEP 6: Deduplicate Signals Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_canonical.deduplicate_dormant_signals()
RETURNS TABLE (
    pruned_count INTEGER,
    unique_hypotheses INTEGER,
    kept_count INTEGER
) AS $$
DECLARE
    v_pruned INTEGER;
    v_unique INTEGER;
    v_kept INTEGER;
BEGIN
    -- For each dedup_hash, keep only the newest signal, mark rest as DUPLICATE_PRUNED
    WITH ranked AS (
        SELECT
            ss.state_id,
            ss.needle_id,
            gn.dedup_hash,
            gn.created_at,
            ROW_NUMBER() OVER (
                PARTITION BY gn.dedup_hash
                ORDER BY gn.created_at DESC
            ) as rn
        FROM fhq_canonical.g5_signal_state ss
        JOIN fhq_canonical.golden_needles gn ON ss.needle_id = gn.needle_id
        WHERE ss.current_state = 'DORMANT'
    ),
    duplicates AS (
        UPDATE fhq_canonical.g5_signal_state ss
        SET
            current_state = 'DUPLICATE_PRUNED',
            last_transition = 'DORMANT->DUPLICATE_PRUNED',
            last_transition_at = NOW(),
            updated_at = NOW()
        FROM ranked r
        WHERE ss.state_id = r.state_id
          AND r.rn > 1  -- Keep only newest (rn=1)
        RETURNING ss.needle_id
    )
    SELECT COUNT(*)::INTEGER INTO v_pruned FROM duplicates;

    -- Count unique hypotheses and kept signals
    SELECT
        COUNT(DISTINCT gn.dedup_hash)::INTEGER,
        COUNT(*)::INTEGER
    INTO v_unique, v_kept
    FROM fhq_canonical.g5_signal_state ss
    JOIN fhq_canonical.golden_needles gn ON ss.needle_id = gn.needle_id
    WHERE ss.current_state = 'DORMANT';

    -- Log to governance
    IF v_pruned > 0 THEN
        INSERT INTO fhq_governance.governance_actions_log (
            action_id,
            action_type,
            action_target,
            action_target_type,
            initiated_by,
            initiated_at,
            decision,
            decision_rationale,
            metadata,
            agent_id,
            timestamp
        ) VALUES (
            gen_random_uuid(),
            'SIGNAL_DEDUPLICATION',
            'fhq_canonical.g5_signal_state',
            'BATCH_UPDATE',
            'STIG',
            NOW(),
            'EXECUTED',
            'Deduplication per CEO Directive 2025-12-25 - keeping newest of each hypothesis',
            jsonb_build_object(
                'pruned_count', v_pruned,
                'unique_hypotheses', v_unique,
                'kept_count', v_kept,
                'dedup_policy', 'SHA256(hypothesis_title|target_asset|regime_technical)'
            ),
            'STIG',
            NOW()
        );
    END IF;

    RETURN QUERY SELECT v_pruned, v_unique, v_kept;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STEP 7: Daily Dormant Signals Report View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_canonical.v_daily_dormant_signals_report AS
WITH age_buckets AS (
    SELECT
        CASE
            WHEN gn.created_at > NOW() - INTERVAL '1 day' THEN '< 1 day'
            WHEN gn.created_at > NOW() - INTERVAL '3 days' THEN '1-3 days'
            WHEN gn.created_at > NOW() - INTERVAL '7 days' THEN '3-7 days'
            ELSE '> 7 days (STALE)'
        END as age_bucket,
        COUNT(*) as count,
        COUNT(DISTINCT gn.dedup_hash) as unique_hypotheses
    FROM fhq_canonical.g5_signal_state ss
    JOIN fhq_canonical.golden_needles gn ON ss.needle_id = gn.needle_id
    WHERE ss.current_state = 'DORMANT'
    GROUP BY 1
),
dedup_stats AS (
    SELECT
        gn.hypothesis_title,
        COUNT(*) as duplicates
    FROM fhq_canonical.g5_signal_state ss
    JOIN fhq_canonical.golden_needles gn ON ss.needle_id = gn.needle_id
    WHERE ss.current_state = 'DORMANT'
    GROUP BY gn.hypothesis_title
    HAVING COUNT(*) > 1
),
summary AS (
    SELECT
        COUNT(*) as total_dormant,
        COUNT(DISTINCT gn.dedup_hash) as unique_hypotheses,
        COUNT(*) - COUNT(DISTINCT gn.dedup_hash) as duplicate_count,
        ROUND(100.0 * (COUNT(*) - COUNT(DISTINCT gn.dedup_hash)) / NULLIF(COUNT(*), 0), 1) as duplicate_pct,
        MIN(gn.created_at) as oldest_signal,
        MAX(gn.created_at) as newest_signal,
        ROUND(AVG(gn.eqs_score), 3) as avg_eqs_score
    FROM fhq_canonical.g5_signal_state ss
    JOIN fhq_canonical.golden_needles gn ON ss.needle_id = gn.needle_id
    WHERE ss.current_state = 'DORMANT'
)
SELECT
    NOW() as report_timestamp,
    s.total_dormant,
    s.unique_hypotheses,
    s.duplicate_count,
    s.duplicate_pct,
    s.oldest_signal,
    s.newest_signal,
    s.avg_eqs_score,
    (SELECT COUNT(*) FROM dedup_stats) as hypotheses_with_duplicates,
    (SELECT jsonb_agg(jsonb_build_object('bucket', age_bucket, 'count', count, 'unique', unique_hypotheses))
     FROM age_buckets) as age_distribution
FROM summary s;

-- ============================================================================
-- STEP 8: Dedup Check Function for Hunter
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_canonical.check_hypothesis_duplicate(
    p_hypothesis_title TEXT,
    p_target_asset TEXT,
    p_regime_technical TEXT
) RETURNS TABLE (
    is_duplicate BOOLEAN,
    existing_needle_id UUID,
    existing_created_at TIMESTAMPTZ,
    existing_state TEXT
) AS $$
DECLARE
    v_dedup_hash TEXT;
BEGIN
    -- Calculate dedup hash
    v_dedup_hash := encode(
        sha256(
            (COALESCE(p_hypothesis_title, '') || '|' ||
             COALESCE(p_target_asset, '') || '|' ||
             COALESCE(p_regime_technical, ''))::bytea
        ),
        'hex'
    );

    -- Check for existing active/dormant signal with same hash
    RETURN QUERY
    SELECT
        TRUE as is_duplicate,
        gn.needle_id as existing_needle_id,
        gn.created_at as existing_created_at,
        ss.current_state as existing_state
    FROM fhq_canonical.golden_needles gn
    JOIN fhq_canonical.g5_signal_state ss ON gn.needle_id = ss.needle_id
    WHERE gn.dedup_hash = v_dedup_hash
      AND ss.current_state IN ('DORMANT', 'PRIMED', 'EXECUTING', 'POSITION_OPEN')
    ORDER BY gn.created_at DESC
    LIMIT 1;

    -- If no duplicate found, return false
    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, NULL::UUID, NULL::TIMESTAMPTZ, NULL::TEXT;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STEP 9: Log Migration Completion
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata,
    agent_id,
    timestamp
) VALUES (
    gen_random_uuid(),
    'MIGRATION_DEPLOYED',
    '168_ceo_directive_signal_ttl_dedup',
    'MIGRATION',
    'STIG',
    NOW(),
    'COMPLETED',
    'CEO Directive 2025-12-25: Signal TTL & Deduplication governance controls deployed',
    jsonb_build_object(
        'directive_id', 'CEO-DIRECTIVE-2025-12-25-TTL-DEDUP',
        'changes', jsonb_build_array(
            'expected_timeframe_days NOT NULL DEFAULT 7',
            'dedup_hash column added',
            'g5_ttl_extension_requests table created',
            'expire_stale_signals() function created',
            'deduplicate_dormant_signals() function created',
            'v_daily_dormant_signals_report view created',
            'check_hypothesis_duplicate() function created'
        ),
        'mdlc_phases_addressed', jsonb_build_array('Phase 4 - Governance', 'Phase 6 - TTL')
    ),
    'STIG',
    NOW()
);

COMMIT;
