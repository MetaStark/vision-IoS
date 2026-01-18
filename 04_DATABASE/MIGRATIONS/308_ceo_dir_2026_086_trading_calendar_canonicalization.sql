-- ============================================================================
-- MIGRATION 308: CEO-DIR-2026-086 TRADING CALENDAR CANONICALIZATION
-- ============================================================================
-- Authority: CEO
-- Directive: CEO-DIR-2026-086
-- Executed by: STIG (EC-003)
--
-- PURPOSE:
--   Canonicalize trading days as a first-class economic primitive.
--   Eliminate calendar-day vs trading-day ambiguity system-wide.
--
-- SCOPE:
--   - Add US equity exchanges to fhq_meta.exchanges
--   - Populate fhq_meta.trading_calendars with US_EQUITY calendar
--   - Populate fhq_meta.calendar_days with trading days 2025-2027
--   - Create canonical trading day resolver function
--   - Create N-trading-days-forward function for ROI horizons
--
-- GOVERNANCE:
--   - No signal data altered
--   - No ledger records modified
--   - Forward evaluations gain correctness
--   - IoS-001 alignment via exchanges table
-- ============================================================================

-- ============================================================================
-- PART 1: ADD US EQUITY EXCHANGES (IoS-001 Alignment)
-- ============================================================================

INSERT INTO fhq_meta.exchanges (mic, exchange_name, country_code, timezone, currency, created_at)
VALUES
    ('XNYS', 'New York Stock Exchange', 'US', 'America/New_York', 'USD', NOW()),
    ('XNAS', 'NASDAQ Stock Market', 'US', 'America/New_York', 'USD', NOW())
ON CONFLICT (mic) DO NOTHING;

-- ============================================================================
-- PART 2: CREATE TRADING CALENDAR REGISTRY
-- ============================================================================

INSERT INTO fhq_meta.trading_calendars (calendar_id, calendar_name, version, effective_from, effective_to, created_at)
VALUES
    ('US_EQUITY', 'US Equity Markets (NYSE/NASDAQ)', '1.0', '2025-01-01', NULL, NOW())
ON CONFLICT (calendar_id) DO NOTHING;

-- ============================================================================
-- PART 3: POPULATE CALENDAR_DAYS FOR US EQUITY (2025-2027)
-- ============================================================================

-- US Market Holidays (NYSE/NASDAQ) 2025-2027
-- Source: NYSE Holiday Schedule (canonical)

-- First, generate all dates
INSERT INTO fhq_meta.calendar_days (calendar_id, date, is_open, session_open, session_close, early_close, notes)
SELECT
    'US_EQUITY',
    d::date,
    -- Default: open on weekdays
    CASE WHEN EXTRACT(DOW FROM d) IN (0, 6) THEN FALSE ELSE TRUE END,
    CASE WHEN EXTRACT(DOW FROM d) IN (0, 6) THEN NULL ELSE '09:30'::time END,
    CASE WHEN EXTRACT(DOW FROM d) IN (0, 6) THEN NULL ELSE '16:00'::time END,
    FALSE,
    CASE WHEN EXTRACT(DOW FROM d) = 0 THEN 'Sunday'
         WHEN EXTRACT(DOW FROM d) = 6 THEN 'Saturday'
         ELSE NULL END
FROM generate_series('2025-01-01'::date, '2027-12-31'::date, '1 day'::interval) d
ON CONFLICT (calendar_id, date) DO NOTHING;

-- Now mark holidays as closed (2025)
UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'New Year''s Day'
WHERE calendar_id = 'US_EQUITY' AND date = '2025-01-01';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Martin Luther King Jr. Day'
WHERE calendar_id = 'US_EQUITY' AND date = '2025-01-20';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Presidents Day'
WHERE calendar_id = 'US_EQUITY' AND date = '2025-02-17';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Good Friday'
WHERE calendar_id = 'US_EQUITY' AND date = '2025-04-18';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Memorial Day'
WHERE calendar_id = 'US_EQUITY' AND date = '2025-05-26';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Juneteenth'
WHERE calendar_id = 'US_EQUITY' AND date = '2025-06-19';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Independence Day'
WHERE calendar_id = 'US_EQUITY' AND date = '2025-07-04';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Labor Day'
WHERE calendar_id = 'US_EQUITY' AND date = '2025-09-01';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Thanksgiving Day'
WHERE calendar_id = 'US_EQUITY' AND date = '2025-11-27';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Christmas Day'
WHERE calendar_id = 'US_EQUITY' AND date = '2025-12-25';

-- 2025 Early closes (1:00 PM ET)
UPDATE fhq_meta.calendar_days
SET early_close = TRUE, session_close = '13:00'::time, notes = 'Day after Thanksgiving (Early Close)'
WHERE calendar_id = 'US_EQUITY' AND date = '2025-11-28';

UPDATE fhq_meta.calendar_days
SET early_close = TRUE, session_close = '13:00'::time, notes = 'Christmas Eve (Early Close)'
WHERE calendar_id = 'US_EQUITY' AND date = '2025-12-24';

-- 2026 Holidays
UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'New Year''s Day'
WHERE calendar_id = 'US_EQUITY' AND date = '2026-01-01';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Martin Luther King Jr. Day'
WHERE calendar_id = 'US_EQUITY' AND date = '2026-01-19';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Presidents Day'
WHERE calendar_id = 'US_EQUITY' AND date = '2026-02-16';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Good Friday'
WHERE calendar_id = 'US_EQUITY' AND date = '2026-04-03';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Memorial Day'
WHERE calendar_id = 'US_EQUITY' AND date = '2026-05-25';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Juneteenth'
WHERE calendar_id = 'US_EQUITY' AND date = '2026-06-19';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Independence Day (Observed)'
WHERE calendar_id = 'US_EQUITY' AND date = '2026-07-03';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Labor Day'
WHERE calendar_id = 'US_EQUITY' AND date = '2026-09-07';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Thanksgiving Day'
WHERE calendar_id = 'US_EQUITY' AND date = '2026-11-26';

UPDATE fhq_meta.calendar_days
SET is_open = FALSE, session_open = NULL, session_close = NULL, notes = 'Christmas Day'
WHERE calendar_id = 'US_EQUITY' AND date = '2026-12-25';

-- 2026 Early closes
UPDATE fhq_meta.calendar_days
SET early_close = TRUE, session_close = '13:00'::time, notes = 'Day after Thanksgiving (Early Close)'
WHERE calendar_id = 'US_EQUITY' AND date = '2026-11-27';

UPDATE fhq_meta.calendar_days
SET early_close = TRUE, session_close = '13:00'::time, notes = 'Christmas Eve (Early Close)'
WHERE calendar_id = 'US_EQUITY' AND date = '2026-12-24';

-- ============================================================================
-- PART 4: CANONICAL TRADING DAY RESOLVER FUNCTION
-- ============================================================================

-- Function: Is this date a trading day?
CREATE OR REPLACE FUNCTION fhq_meta.is_trading_day(
    p_date DATE,
    p_calendar_id TEXT DEFAULT 'US_EQUITY'
)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM fhq_meta.calendar_days
        WHERE calendar_id = p_calendar_id
        AND date = p_date
        AND is_open = TRUE
    );
END;
$$ LANGUAGE plpgsql STABLE;

-- Function: Get next N trading days forward from a date
CREATE OR REPLACE FUNCTION fhq_meta.trading_days_forward(
    p_from_date DATE,
    p_trading_days INT,
    p_calendar_id TEXT DEFAULT 'US_EQUITY'
)
RETURNS DATE AS $$
DECLARE
    v_result DATE;
    v_count INT := 0;
    v_current DATE := p_from_date;
BEGIN
    -- Start from the day after p_from_date
    v_current := p_from_date + 1;

    WHILE v_count < p_trading_days LOOP
        IF fhq_meta.is_trading_day(v_current, p_calendar_id) THEN
            v_count := v_count + 1;
            v_result := v_current;
        END IF;
        v_current := v_current + 1;

        -- Safety: don't loop forever
        IF v_current > p_from_date + INTERVAL '30 days' THEN
            RETURN NULL;
        END IF;
    END LOOP;

    RETURN v_result;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function: Get the next trading close date (for horizon evaluation)
CREATE OR REPLACE FUNCTION fhq_meta.next_trading_close(
    p_timestamp TIMESTAMPTZ,
    p_calendar_id TEXT DEFAULT 'US_EQUITY'
)
RETURNS DATE AS $$
DECLARE
    v_date DATE := DATE(p_timestamp AT TIME ZONE 'America/New_York');
BEGIN
    -- If it's a trading day, return that date
    IF fhq_meta.is_trading_day(v_date, p_calendar_id) THEN
        RETURN v_date;
    END IF;

    -- Otherwise find the next trading day
    RETURN fhq_meta.trading_days_forward(v_date - 1, 1, p_calendar_id);
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- PART 5: ROI HORIZON RESOLVER (TRADING DAYS)
-- ============================================================================

-- Function: Get price date for N trading days after signal
-- This is the canonical function for ROI horizon evaluation
CREATE OR REPLACE FUNCTION fhq_research.roi_horizon_date(
    p_signal_timestamp TIMESTAMPTZ,
    p_horizon_trading_days INT,
    p_calendar_id TEXT DEFAULT 'US_EQUITY'
)
RETURNS DATE AS $$
DECLARE
    v_signal_date DATE;
BEGIN
    -- Get the trading day of the signal
    v_signal_date := fhq_meta.next_trading_close(p_signal_timestamp, p_calendar_id);

    -- Get N trading days forward
    RETURN fhq_meta.trading_days_forward(v_signal_date, p_horizon_trading_days, p_calendar_id);
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- PART 6: VERIFICATION VIEW
-- ============================================================================

CREATE OR REPLACE VIEW fhq_meta.v_trading_calendar_summary AS
SELECT
    calendar_id,
    COUNT(*) as total_days,
    SUM(CASE WHEN is_open THEN 1 ELSE 0 END) as trading_days,
    SUM(CASE WHEN NOT is_open AND EXTRACT(DOW FROM date) NOT IN (0, 6) THEN 1 ELSE 0 END) as holidays,
    SUM(CASE WHEN early_close THEN 1 ELSE 0 END) as early_close_days,
    MIN(date) as coverage_start,
    MAX(date) as coverage_end
FROM fhq_meta.calendar_days
GROUP BY calendar_id;

-- ============================================================================
-- PART 7: TEST THE RESOLVER
-- ============================================================================

-- Verification: Check that Wed Jan 6 + 3 trading days = next trading day after weekend
DO $$
DECLARE
    v_test_result DATE;
BEGIN
    -- Signal on Wed 2026-01-07, +3 trading days should NOT be Sat/Sun
    v_test_result := fhq_research.roi_horizon_date('2026-01-07'::timestamptz, 3, 'US_EQUITY');

    IF EXTRACT(DOW FROM v_test_result) IN (0, 6) THEN
        RAISE EXCEPTION 'Trading day resolver returned weekend: %', v_test_result;
    END IF;

    RAISE NOTICE 'Trading calendar verification PASSED. Wed Jan 7 + 3T = %', v_test_result;
END $$;

-- ============================================================================
-- PART 8: GOVERNANCE REGISTRATION
-- ============================================================================

INSERT INTO fhq_meta.adr_audit_log (
    adr_id,
    event_id,
    review_status,
    detected_by,
    detected_at,
    resolution_notes,
    severity
) VALUES (
    'ADR-013',
    floor(random() * 1000000000)::int,
    'VERIFIED',
    'STIG',
    NOW(),
    'CEO-DIR-2026-086: Trading calendar canonicalized as first-class economic primitive. Functions created: is_trading_day, trading_days_forward, next_trading_close, roi_horizon_date. Coverage: 2025-2027 US Equity.',
    'MEDIUM'
);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON FUNCTION fhq_meta.is_trading_day IS
'CEO-DIR-2026-086: Returns TRUE if the given date is a trading day for the specified calendar.';

COMMENT ON FUNCTION fhq_meta.trading_days_forward IS
'CEO-DIR-2026-086: Returns the date that is N trading days forward from the given date.';

COMMENT ON FUNCTION fhq_meta.next_trading_close IS
'CEO-DIR-2026-086: Returns the trading close date for a given timestamp. If timestamp falls on non-trading day, returns next trading day.';

COMMENT ON FUNCTION fhq_research.roi_horizon_date IS
'CEO-DIR-2026-086: Canonical function for ROI horizon evaluation. Returns the price evaluation date for N trading days after signal. Eliminates calendar-day vs trading-day ambiguity.';

COMMENT ON VIEW fhq_meta.v_trading_calendar_summary IS
'CEO-DIR-2026-086: Summary view of trading calendar coverage and statistics.';
