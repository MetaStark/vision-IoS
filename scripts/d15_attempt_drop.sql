-- ============================================================================
-- D15 — hvorfor falt antall forsoek fra 11 run_id til 2 paa ti minutter etter pass 2?
-- Kun lesing. psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -f d15_attempt_drop.sql
-- ============================================================================
\pset pager off
\timing off
SELECT NOW() AT TIME ZONE 'Europe/Oslo' AS db_clock_oslo;

\echo '--- A. forsoek per 5-min-tikk siste 50 min: naar forsvant de?'
SELECT to_char(date_trunc('minute', started_at AT TIME ZONE 'Europe/Oslo')
         - (EXTRACT(minute FROM started_at AT TIME ZONE 'Europe/Oslo')::int % 5) * INTERVAL '1 minute', 'HH24:MI') AS tick_oslo,
       COUNT(*) AS attempts, COUNT(DISTINCT run_id) AS distinct_runs,
       COUNT(*) FILTER (WHERE status = 'SUCCESS') AS ok
FROM fhq_runtime.run_attempts
WHERE started_at >= NOW() - INTERVAL '50 minutes'
GROUP BY 1 ORDER BY 1;

\echo '--- B. run_locks: staar det laaser igjen? (kolonner foerst)'
SELECT string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) AS run_locks_columns
FROM information_schema.columns WHERE table_schema = 'fhq_runtime' AND table_name = 'run_locks';
SELECT * FROM fhq_runtime.run_locks ORDER BY 1 DESC LIMIT 30;

\echo '--- C. executors egen siste feil, full tekst (ikke lenger kappet), siste 3'
SELECT created_at AT TIME ZONE 'Europe/Oslo' AS at_oslo, length(error_message) AS len,
       regexp_replace(split_part(regexp_replace(error_message, '\s+$', ''), E'\n',
         array_length(string_to_array(regexp_replace(error_message, '\s+$', ''), E'\n'), 1)), '\s+', ' ', 'g') AS last_line
FROM fhq_runtime.run_failures
WHERE run_id = 'RUNA-CADENCE-EXECUTOR'
ORDER BY created_at DESC LIMIT 3;

\echo '--- D. siste feil per run_id siste 20 min, siste linje (hva stopper dem NAA?)'
SELECT DISTINCT ON (run_id) run_id, created_at AT TIME ZONE 'Europe/Oslo' AS at_oslo,
       LEFT(regexp_replace(split_part(regexp_replace(error_message, '\s+$', ''), E'\n',
         array_length(string_to_array(regexp_replace(error_message, '\s+$', ''), E'\n'), 1)), '\s+', ' ', 'g'), 200) AS last_line
FROM fhq_runtime.run_failures
WHERE created_at >= NOW() - INTERVAL '20 minutes'
ORDER BY run_id, created_at DESC;

\echo '--- E. run_registry: hvilke jobber er ENABLED, og hvilke avhengigheter har de?'
SELECT string_agg(column_name, ', ' ORDER BY ordinal_position) AS run_registry_columns
FROM information_schema.columns WHERE table_schema = 'fhq_runtime' AND table_name = 'run_registry';
