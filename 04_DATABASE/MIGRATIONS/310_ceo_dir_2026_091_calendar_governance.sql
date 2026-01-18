-- =============================================================================
-- CEO-DIR-2026-091: TRADING CALENDAR CONTINUOUS GOVERNANCE + IoS-016 INTEGRATION
-- =============================================================================
--
-- Authority: CEO
-- Scope: fhq_meta.calendar_days, fhq_meta.crypto_epoch_definitions
-- Domain: US_EQUITY, CRYPTO
--
-- This migration adds governance columns for calendar audit trail and creates
-- crypto epoch boundary infrastructure.
--
-- Key additions:
--   1. provenance: LIBRARY or PROJECTED
--   2. reason: HOLIDAY, WEEKEND, EARLY_CLOSE, TRADING_DAY
--   3. verified_at: timestamp of last verification
--   4. Crypto epoch definitions table
-- =============================================================================

BEGIN;

-- =============================================================================
-- STEP 1: ADD GOVERNANCE COLUMNS TO calendar_days
-- =============================================================================

-- Add provenance column (LIBRARY = from exchange_calendars, PROJECTED = extrapolated)
ALTER TABLE fhq_meta.calendar_days
ADD COLUMN IF NOT EXISTS provenance VARCHAR(20) DEFAULT 'LIBRARY';

-- Add reason column (why is market open/closed)
ALTER TABLE fhq_meta.calendar_days
ADD COLUMN IF NOT EXISTS reason VARCHAR(50);

-- Add verified_at timestamp
ALTER TABLE fhq_meta.calendar_days
ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ DEFAULT NOW();

-- =============================================================================
-- STEP 2: ADD CHECK CONSTRAINTS
-- =============================================================================

-- Provenance must be LIBRARY or PROJECTED
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_calendar_provenance'
    ) THEN
        ALTER TABLE fhq_meta.calendar_days
        ADD CONSTRAINT chk_calendar_provenance
        CHECK (provenance IN ('LIBRARY', 'PROJECTED'));
    END IF;
END$$;

-- Reason must be valid
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_calendar_reason'
    ) THEN
        ALTER TABLE fhq_meta.calendar_days
        ADD CONSTRAINT chk_calendar_reason
        CHECK (reason IN ('TRADING_DAY', 'WEEKEND', 'HOLIDAY', 'EARLY_CLOSE', NULL));
    END IF;
END$$;

-- =============================================================================
-- STEP 3: UPDATE EXISTING RECORDS WITH REASON
-- =============================================================================

-- Set reason for existing records
UPDATE fhq_meta.calendar_days
SET reason = CASE
    WHEN is_open = true AND early_close = true THEN 'EARLY_CLOSE'
    WHEN is_open = true THEN 'TRADING_DAY'
    WHEN EXTRACT(DOW FROM date) IN (0, 6) THEN 'WEEKEND'
    ELSE 'HOLIDAY'
END
WHERE reason IS NULL;

-- Set NOT NULL after populating
ALTER TABLE fhq_meta.calendar_days
ALTER COLUMN reason SET NOT NULL;

-- =============================================================================
-- STEP 4: CREATE CRYPTO EPOCH DEFINITIONS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.crypto_epoch_definitions (
    epoch_id VARCHAR(50) PRIMARY KEY,
    description TEXT NOT NULL,
    boundary_time TIME NOT NULL,
    boundary_timezone VARCHAR(10) NOT NULL,
    asset_class VARCHAR(20) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_crypto_boundary_timezone CHECK (boundary_timezone = 'UTC'),
    CONSTRAINT chk_crypto_asset_class CHECK (asset_class = 'CRYPTO')
);

-- Seed canonical crypto epoch
INSERT INTO fhq_meta.crypto_epoch_definitions
    (epoch_id, description, boundary_time, boundary_timezone, asset_class)
VALUES
    ('CRYPTO_DAILY_EPOCH', 'Canonical daily boundary for crypto regime evaluation per CEO-DIR-2026-091',
     '00:00:00', 'UTC', 'CRYPTO')
ON CONFLICT (epoch_id) DO NOTHING;

-- =============================================================================
-- STEP 5: CREATE IoS-016 CALENDAR VIEW
-- =============================================================================

CREATE OR REPLACE VIEW fhq_meta.ios016_calendar_truth AS
SELECT
    cd.calendar_id AS market,
    cd.date,
    CASE WHEN cd.is_open THEN 'OPEN' ELSE 'CLOSED' END AS status,
    cd.reason,
    cd.provenance,
    cd.verified_at,
    cd.early_close,
    cd.session_open,
    cd.session_close,
    cd.notes,
    -- Governance flags
    CASE
        WHEN cd.provenance = 'PROJECTED' THEN true
        ELSE false
    END AS is_tentative,
    CASE
        WHEN cd.provenance = 'PROJECTED' THEN 'PROJECTED - Not verified against authoritative exchange schedule'
        ELSE 'LIBRARY - Verified via exchange_calendars'
    END AS provenance_note
FROM fhq_meta.calendar_days cd
ORDER BY cd.calendar_id, cd.date;

COMMENT ON VIEW fhq_meta.ios016_calendar_truth IS
'IoS-016 Economic Calendar integration view. Provides calendar truth with governance metadata per CEO-DIR-2026-091.';

-- =============================================================================
-- STEP 6: CREATE CALENDAR INTEGRITY CHECK FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION fhq_meta.check_calendar_integrity(p_market VARCHAR DEFAULT 'US_EQUITY')
RETURNS TABLE (
    check_name VARCHAR,
    status VARCHAR,
    value TEXT,
    threshold TEXT,
    message TEXT
) AS $$
DECLARE
    v_forward_days INTEGER;
    v_coverage_end DATE;
    v_tomorrow_resolved BOOLEAN;
    v_next_7_resolved BOOLEAN;
    v_days_to_threshold INTEGER;
    v_null_fields INTEGER;
    v_projected_in_30d INTEGER;
BEGIN
    -- Check 1: Forward coverage
    SELECT
        MAX(date) - CURRENT_DATE,
        MAX(date)
    INTO v_forward_days, v_coverage_end
    FROM fhq_meta.calendar_days
    WHERE calendar_id = p_market;

    check_name := 'FORWARD_COVERAGE';
    threshold := '720 days';
    value := v_forward_days::TEXT || ' days (until ' || v_coverage_end::TEXT || ')';
    IF v_forward_days >= 720 THEN
        status := 'GREEN';
        message := 'Forward coverage meets minimum requirement';
    ELSIF v_forward_days >= 690 THEN
        status := 'YELLOW';
        message := 'Forward coverage approaching threshold - extension recommended';
    ELSE
        status := 'RED';
        message := 'CRITICAL: Forward coverage below minimum - immediate extension required';
    END IF;
    RETURN NEXT;

    -- Check 2: Tomorrow resolution
    SELECT EXISTS(
        SELECT 1 FROM fhq_meta.calendar_days
        WHERE calendar_id = p_market AND date = CURRENT_DATE + 1
    ) INTO v_tomorrow_resolved;

    check_name := 'TOMORROW_RESOLUTION';
    threshold := 'Must resolve';
    value := CASE WHEN v_tomorrow_resolved THEN 'RESOLVED' ELSE 'MISSING' END;
    IF v_tomorrow_resolved THEN
        status := 'GREEN';
        message := 'Tomorrow''s market status is defined';
    ELSE
        status := 'RED';
        message := 'CRITICAL: Cannot determine if market is open tomorrow';
    END IF;
    RETURN NEXT;

    -- Check 3: Next 7 trading days resolution
    SELECT COUNT(*) = 7 INTO v_next_7_resolved
    FROM (
        SELECT date FROM fhq_meta.calendar_days
        WHERE calendar_id = p_market
        AND date > CURRENT_DATE
        AND is_open = true
        ORDER BY date
        LIMIT 7
    ) t;

    check_name := 'NEXT_7_TRADING_DAYS';
    threshold := '7 days must resolve';
    value := CASE WHEN v_next_7_resolved THEN 'RESOLVED' ELSE 'INCOMPLETE' END;
    IF v_next_7_resolved THEN
        status := 'GREEN';
        message := 'Next 7 trading days are defined';
    ELSE
        status := 'RED';
        message := 'CRITICAL: Cannot determine next 7 trading days';
    END IF;
    RETURN NEXT;

    -- Check 4: Days to coverage threshold
    v_days_to_threshold := v_forward_days - 720;

    check_name := 'THRESHOLD_PROXIMITY';
    threshold := '> 30 days buffer';
    value := v_days_to_threshold::TEXT || ' days above threshold';
    IF v_days_to_threshold > 30 THEN
        status := 'GREEN';
        message := 'Comfortable buffer above minimum coverage';
    ELSIF v_days_to_threshold > 0 THEN
        status := 'YELLOW';
        message := 'Within 30 days of coverage threshold - schedule extension';
    ELSE
        status := 'RED';
        message := 'CRITICAL: Below coverage threshold';
    END IF;
    RETURN NEXT;

    -- Check 5: NULL field detection
    SELECT COUNT(*) INTO v_null_fields
    FROM fhq_meta.calendar_days
    WHERE calendar_id = p_market
    AND (reason IS NULL OR provenance IS NULL);

    check_name := 'NULL_FIELD_CHECK';
    threshold := '0 NULL values';
    value := v_null_fields::TEXT || ' records with NULL';
    IF v_null_fields = 0 THEN
        status := 'GREEN';
        message := 'All required fields populated';
    ELSE
        status := 'RED';
        message := 'CRITICAL: Missing required field values';
    END IF;
    RETURN NEXT;

    -- Check 6: Projected days in next 30 days
    SELECT COUNT(*) INTO v_projected_in_30d
    FROM fhq_meta.calendar_days
    WHERE calendar_id = p_market
    AND date BETWEEN CURRENT_DATE AND CURRENT_DATE + 30
    AND provenance = 'PROJECTED';

    check_name := 'PROJECTED_IN_30D';
    threshold := 'Awareness only';
    value := v_projected_in_30d::TEXT || ' projected days';
    IF v_projected_in_30d = 0 THEN
        status := 'GREEN';
        message := 'All days in next 30 days are library-verified';
    ELSE
        status := 'YELLOW';
        message := 'Some days in next 30 days are projected (not library-verified)';
    END IF;
    RETURN NEXT;

END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_meta.check_calendar_integrity IS
'Daily integrity check for trading calendar per CEO-DIR-2026-091. Returns GREEN/YELLOW/RED status for each check.';

-- =============================================================================
-- STEP 7: CREATE HELPER FUNCTIONS
-- =============================================================================

-- Function to check if market is open on a given date
CREATE OR REPLACE FUNCTION fhq_meta.is_market_open(
    p_market VARCHAR,
    p_date DATE
) RETURNS BOOLEAN AS $$
    SELECT COALESCE(
        (SELECT is_open FROM fhq_meta.calendar_days
         WHERE calendar_id = p_market AND date = p_date),
        NULL
    );
$$ LANGUAGE sql STABLE;

-- Function to get next N trading days
CREATE OR REPLACE FUNCTION fhq_meta.get_next_trading_days(
    p_market VARCHAR,
    p_from_date DATE,
    p_count INTEGER
) RETURNS TABLE (trading_date DATE, day_number INTEGER) AS $$
    SELECT date, ROW_NUMBER() OVER (ORDER BY date)::INTEGER
    FROM fhq_meta.calendar_days
    WHERE calendar_id = p_market
    AND date > p_from_date
    AND is_open = true
    ORDER BY date
    LIMIT p_count;
$$ LANGUAGE sql STABLE;

-- Function to get crypto epoch boundary
CREATE OR REPLACE FUNCTION fhq_meta.crypto_epoch_boundary(p_timestamp TIMESTAMPTZ)
RETURNS TIMESTAMPTZ AS $$
    SELECT date_trunc('day', p_timestamp AT TIME ZONE 'UTC') AT TIME ZONE 'UTC';
$$ LANGUAGE sql IMMUTABLE;

COMMENT ON FUNCTION fhq_meta.crypto_epoch_boundary IS
'Returns the canonical crypto epoch boundary (00:00:00 UTC) for a given timestamp per CEO-DIR-2026-091.';

-- =============================================================================
-- STEP 8: CREATE INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_calendar_days_provenance
ON fhq_meta.calendar_days (provenance);

CREATE INDEX IF NOT EXISTS idx_calendar_days_reason
ON fhq_meta.calendar_days (reason);

CREATE INDEX IF NOT EXISTS idx_calendar_days_date_open
ON fhq_meta.calendar_days (calendar_id, date, is_open);

-- =============================================================================
-- STEP 9: GOVERNANCE LOGGING
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log
    (action_type, action_target, action_target_type, initiated_by, decision, decision_rationale, metadata)
VALUES
    ('SCHEMA_MIGRATION_EXECUTED', 'MIGRATION_310_CALENDAR_GOVERNANCE', 'MIGRATION', 'STIG', 'EXECUTED',
     'CEO-DIR-2026-091: Added governance columns to calendar_days, created crypto epoch definitions, IoS-016 integration view, integrity check function.',
     jsonb_build_object(
         'directive', 'CEO-DIR-2026-091',
         'migration', '310_ceo_dir_2026_091_calendar_governance.sql',
         'columns_added', ARRAY['provenance', 'reason', 'verified_at'],
         'tables_created', ARRAY['fhq_meta.crypto_epoch_definitions'],
         'views_created', ARRAY['fhq_meta.ios016_calendar_truth'],
         'functions_created', ARRAY['fhq_meta.check_calendar_integrity', 'fhq_meta.is_market_open', 'fhq_meta.get_next_trading_days', 'fhq_meta.crypto_epoch_boundary'],
         'executed_at', NOW()
     ));

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES (run manually after migration)
-- =============================================================================
-- SELECT * FROM fhq_meta.check_calendar_integrity('US_EQUITY');
-- SELECT * FROM fhq_meta.ios016_calendar_truth WHERE date BETWEEN CURRENT_DATE AND CURRENT_DATE + 7;
-- SELECT * FROM fhq_meta.crypto_epoch_definitions;
-- SELECT fhq_meta.crypto_epoch_boundary(NOW());
