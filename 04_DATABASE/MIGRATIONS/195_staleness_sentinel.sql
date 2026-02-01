-- ============================================================================
-- MIGRATION 195: CEO-DIR-2026-01-03 Staleness Sentinel
-- ============================================================================
--
-- CEO DIRECTIVE: PURGE AND POLISH PROTOCOL
--
-- Implements automatic 7-day validity enforcement for golden needles.
-- Needles exceeding the validity window are auto-expired.
--
-- Authority: CEO Directive 2026-01-03 (Golden Needle Validity Analysis)
-- Priority: P1
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. STALENESS SENTINEL FUNCTION
-- ============================================================================
-- Auto-expires needles older than 7 days (corporate standard validity window)

CREATE OR REPLACE FUNCTION fhq_canonical.enforce_needle_staleness()
RETURNS TABLE (
    expired_count INT,
    oldest_expired TIMESTAMPTZ,
    newest_expired TIMESTAMPTZ
) AS $$
DECLARE
    v_expired_count INT;
    v_oldest TIMESTAMPTZ;
    v_newest TIMESTAMPTZ;
BEGIN
    -- Find needles to expire (older than 7 days)
    SELECT
        COUNT(*),
        MIN(created_at),
        MAX(created_at)
    INTO v_expired_count, v_oldest, v_newest
    FROM fhq_canonical.golden_needles
    WHERE is_current = TRUE
      AND created_at < NOW() - INTERVAL '7 days';

    -- Expire stale needles
    IF v_expired_count > 0 THEN
        UPDATE fhq_canonical.golden_needles
        SET is_current = FALSE,
            supersession_reason = 'STALENESS_SENTINEL: Auto-expired after 7-day validity window'
        WHERE is_current = TRUE
          AND created_at < NOW() - INTERVAL '7 days';

        -- Log to governance
        INSERT INTO fhq_governance.governance_actions_log (
            action_type,
            action_target,
            decision,
            decision_rationale,
            initiated_by,
            vega_reviewed
        ) VALUES (
            'AUTO_EXPIRE',
            'GOLDEN_NEEDLES',
            'EXECUTED',
            format('Staleness Sentinel: %s needles auto-expired (validity: 7d). Oldest: %s, Newest: %s',
                   v_expired_count, v_oldest, v_newest),
            'STALENESS_SENTINEL',
            FALSE
        );
    END IF;

    RETURN QUERY SELECT v_expired_count, v_oldest, v_newest;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_canonical.enforce_needle_staleness IS
'CEO-DIR-2026-01-03: Auto-expires golden needles exceeding 7-day validity window';

-- ============================================================================
-- 2. STALENESS SENTINEL VIEW
-- ============================================================================
-- Dashboard view showing needle freshness status

CREATE OR REPLACE VIEW fhq_canonical.v_needle_freshness_status AS
SELECT
    COUNT(*) FILTER (WHERE is_current = TRUE) AS current_needles,
    COUNT(*) FILTER (WHERE is_current = TRUE AND created_at >= NOW() - INTERVAL '1 day') AS fresh_1d,
    COUNT(*) FILTER (WHERE is_current = TRUE AND created_at >= NOW() - INTERVAL '3 days') AS fresh_3d,
    COUNT(*) FILTER (WHERE is_current = TRUE AND created_at >= NOW() - INTERVAL '7 days') AS fresh_7d,
    COUNT(*) FILTER (WHERE is_current = TRUE AND created_at < NOW() - INTERVAL '7 days') AS stale_count,
    MIN(created_at) FILTER (WHERE is_current = TRUE) AS oldest_current,
    MAX(created_at) FILTER (WHERE is_current = TRUE) AS newest_current,
    EXTRACT(DAY FROM NOW() - MAX(created_at) FILTER (WHERE is_current = TRUE)) AS days_since_newest,
    CASE
        WHEN MAX(created_at) FILTER (WHERE is_current = TRUE) >= NOW() - INTERVAL '7 days' THEN 'VALID'
        WHEN MAX(created_at) FILTER (WHERE is_current = TRUE) IS NULL THEN 'EMPTY'
        ELSE 'STALE'
    END AS inventory_status
FROM fhq_canonical.golden_needles;

COMMENT ON VIEW fhq_canonical.v_needle_freshness_status IS
'CEO-DIR-2026-01-03: Dashboard view for golden needle freshness monitoring';

-- ============================================================================
-- 3. VALIDITY CONFIG TABLE
-- ============================================================================
-- Configurable validity window (default 7 days per corporate standard)

CREATE TABLE IF NOT EXISTS fhq_canonical.needle_validity_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    validity_days INT NOT NULL DEFAULT 7,
    auto_expire_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_sentinel_run TIMESTAMPTZ,
    needles_expired_total BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    updated_by TEXT
);

-- Seed default config
INSERT INTO fhq_canonical.needle_validity_config (validity_days, auto_expire_enabled)
VALUES (7, TRUE)
ON CONFLICT DO NOTHING;

COMMENT ON TABLE fhq_canonical.needle_validity_config IS
'CEO-DIR-2026-01-03: Golden needle validity configuration (corporate standard: 7 days)';

-- ============================================================================
-- 4. GOVERNANCE LOG
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    decision,
    decision_rationale,
    initiated_by,
    vega_reviewed
) VALUES (
    'MIGRATION',
    'STALENESS_SENTINEL',
    'APPROVED',
    'CEO-DIR-2026-01-03: Staleness Sentinel implementation. 7-day validity enforcement. Purge and Polish Protocol P1.',
    'STIG',
    FALSE
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_status RECORD;
BEGIN
    -- Check current inventory status
    SELECT * INTO v_status FROM fhq_canonical.v_needle_freshness_status;

    RAISE NOTICE '============================================================';
    RAISE NOTICE 'CEO-DIR-2026-01-03 Migration 195: STALENESS SENTINEL';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Validity Window: 7 days (corporate standard)';
    RAISE NOTICE 'Current Inventory: % needles', v_status.current_needles;
    RAISE NOTICE 'Inventory Status: %', v_status.inventory_status;
    RAISE NOTICE '============================================================';
END $$;
