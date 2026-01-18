-- CEO-DIR-2026-086: Populate calendar_days for US_EQUITY 2025-2027
-- Generates all dates and marks trading vs non-trading days

-- US Market Holidays 2025-2027
WITH holidays AS (
    SELECT unnest(ARRAY[
        -- 2025
        '2025-01-01'::date, '2025-01-20'::date, '2025-02-17'::date, '2025-04-18'::date,
        '2025-05-26'::date, '2025-06-19'::date, '2025-07-04'::date, '2025-09-01'::date,
        '2025-11-27'::date, '2025-12-25'::date,
        -- 2026
        '2026-01-01'::date, '2026-01-19'::date, '2026-02-16'::date, '2026-04-03'::date,
        '2026-05-25'::date, '2026-06-19'::date, '2026-07-03'::date, '2026-09-07'::date,
        '2026-11-26'::date, '2026-12-25'::date,
        -- 2027
        '2027-01-01'::date, '2027-01-18'::date, '2027-02-15'::date, '2027-03-26'::date,
        '2027-05-31'::date, '2027-06-18'::date, '2027-07-05'::date, '2027-09-06'::date,
        '2027-11-25'::date, '2027-12-24'::date
    ]) AS holiday_date
),
early_close AS (
    SELECT unnest(ARRAY[
        '2025-11-28'::date, '2025-12-24'::date,
        '2026-11-27'::date, '2026-12-24'::date,
        '2027-11-26'::date
    ]) AS early_date
),
all_dates AS (
    SELECT generate_series('2025-01-01'::date, '2027-12-31'::date, '1 day'::interval)::date AS date
)
INSERT INTO fhq_meta.calendar_days (calendar_id, date, is_open, session_open, session_close, early_close, notes)
SELECT
    'US_EQUITY',
    d.date,
    -- is_open: weekday and not a holiday
    CASE
        WHEN EXTRACT(DOW FROM d.date) IN (0, 6) THEN false
        WHEN d.date IN (SELECT holiday_date FROM holidays) THEN false
        ELSE true
    END,
    -- session_open
    CASE
        WHEN EXTRACT(DOW FROM d.date) IN (0, 6) THEN NULL
        WHEN d.date IN (SELECT holiday_date FROM holidays) THEN NULL
        ELSE '09:30'::time
    END,
    -- session_close
    CASE
        WHEN EXTRACT(DOW FROM d.date) IN (0, 6) THEN NULL
        WHEN d.date IN (SELECT holiday_date FROM holidays) THEN NULL
        WHEN d.date IN (SELECT early_date FROM early_close) THEN '13:00'::time
        ELSE '16:00'::time
    END,
    -- early_close
    d.date IN (SELECT early_date FROM early_close),
    -- notes
    CASE
        WHEN EXTRACT(DOW FROM d.date) = 0 THEN 'Sunday'
        WHEN EXTRACT(DOW FROM d.date) = 6 THEN 'Saturday'
        WHEN d.date IN (SELECT holiday_date FROM holidays) THEN 'Holiday'
        WHEN d.date IN (SELECT early_date FROM early_close) THEN 'Early Close'
        ELSE NULL
    END
FROM all_dates d
ON CONFLICT DO NOTHING;
