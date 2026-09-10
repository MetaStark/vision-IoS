-- ============================================================================
-- FASE 0 — RUNDE 7  (etter to kjoeringer av runde 6, 2026-09-09 ~17:40 og ~20:40 Oslo)
-- ============================================================================
-- Kun lesing. Kjoeres fra VERTEN med host-psql (D14-verdien er paa plass):
--   cd D:\Runtime
--   psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -f phase0_round7.sql > phase0_round7_result.txt 2>&1
-- Spoersmaal:
--   L  D10: har de ti jobbene begynt aa lykkes etter 19:50 Oslo?  (avgjoer om CEO-handlingen loeste D10)
--   M  D13: er error_stack fylt? (alternativ baerer for aarsaken)
--   N  D11: hvilket JSON-felt baerer kandidat-id-et 4d108812 (eksakt noekkel)
--   O  J1 paa nytt, med kolonnene lest foerst (retter min antagelse om 'title')
-- ============================================================================
\set ON_ERROR_STOP off
\pset pager off
\pset footer on
\timing off

SELECT NOW() AT TIME ZONE 'Europe/Oslo' AS db_clock_oslo;

\echo
\echo '=================================================================='
\echo ' L. D10 — suksess per run_id, per time, siden 16:00 Oslo (vendepunktet ligger rundt 19:50)'
\echo '=================================================================='
SELECT DATE_TRUNC('hour', started_at AT TIME ZONE 'Europe/Oslo') AS hour_oslo,
       COUNT(*) AS attempts,
       COUNT(*) FILTER (WHERE status = 'SUCCESS') AS success,
       COUNT(*) FILTER (WHERE status <> 'SUCCESS') AS not_success,
       COUNT(DISTINCT run_id) FILTER (WHERE status = 'SUCCESS') AS distinct_runs_ok
FROM fhq_runtime.run_attempts
WHERE started_at >= '2026-09-09 16:00:00+02'
GROUP BY 1 ORDER BY 1;

\echo '--- L2. per run_id siste 60 min: er de ti oppe?'
SELECT run_id, COUNT(*) AS attempts,
       COUNT(*) FILTER (WHERE status = 'SUCCESS') AS success,
       MAX(started_at) FILTER (WHERE status = 'SUCCESS') AT TIME ZONE 'Europe/Oslo' AS last_success_oslo,
       MAX(started_at) AT TIME ZONE 'Europe/Oslo' AS last_attempt_oslo
FROM fhq_runtime.run_attempts
WHERE started_at >= NOW() - INTERVAL '60 minutes'
GROUP BY run_id ORDER BY success DESC, run_id;

\echo '--- L3. foerste SUCCESS i dag per run_id for de ti (naar snudde det?)'
SELECT run_id, MIN(started_at) AT TIME ZONE 'Europe/Oslo' AS first_success_today_oslo
FROM fhq_runtime.run_attempts
WHERE status = 'SUCCESS' AND started_at >= '2026-09-09 11:11:00+02'
  AND run_id IN ('RUN-72H-LEARNING-PRESSURE-GOVERNOR-V1','RUN-CEIO-AUTONOMOUS-V1','RUN-CONTAINER-CANDLE-FETCHER-V1',
                 'RUN-CONTAINER-LEARNING-VELOCITY-WATCH-V1','RUN-CONTAINER-LIVE-PRICE-FETCHER-V1','RUN-FEATURE-FRESHNESS-WATCHDOG-V1',
                 'RUN-PORTFOLIO-QUARANTINE-V1','RUN-STEP08-EVIDENCE-GRADING-V4','RUN-STEP08-EVIDENCE-GRADING-V5','RUNA-CADENCE-EXECUTOR')
GROUP BY run_id ORDER BY 2;

\echo '--- L4. siste feil per run_id, alle lengder, siste 90 min (hva feiler de paa NAA?)'
SELECT DISTINCT ON (run_id) run_id, created_at AT TIME ZONE 'Europe/Oslo' AS at_oslo, length(error_message) AS len,
       LEFT(regexp_replace(split_part(regexp_replace(error_message, '\s+$', ''), E'\n',
            array_length(string_to_array(regexp_replace(error_message, '\s+$', ''), E'\n'), 1)), '\s+', ' ', 'g'), 160) AS last_line
FROM fhq_runtime.run_failures
WHERE created_at >= NOW() - INTERVAL '90 minutes'
ORDER BY run_id, created_at DESC;

\echo '--- L5. naar ble postgres-rollens passord sist endret? (pg_authid.rolvaliduntil sier ikke det; men pg_stat_activity viser naavaerende klienter)'
SELECT usename, application_name, client_addr, state, backend_start AT TIME ZONE 'Europe/Oslo' AS backend_start_oslo
FROM pg_stat_activity
WHERE datname = 'postgres' AND backend_type = 'client backend'
ORDER BY backend_start DESC LIMIT 15;

\echo
\echo '=================================================================='
\echo ' M. D13 — er error_stack fylt for dagens rader?'
\echo '=================================================================='
SELECT COUNT(*) AS rows_today,
       COUNT(error_stack) AS with_error_stack,
       MAX(length(error_stack)) AS max_stack_len
FROM fhq_runtime.run_failures WHERE created_at >= '2026-09-09 11:11:00+02';

\echo
\echo '=================================================================='
\echo ' N. D11 — eksakt JSON-noekkel som baerer kandidat-id-et 4d108812 (PREREG-noden)'
\echo '=================================================================='
SELECT n.node, k.key AS top_key,
       LEFT(k.value, 220) AS value_head
FROM fhq_control.factory_cycle_nodes n,
     LATERAL jsonb_each_text(n.state_after->'S') k
WHERE n.cycle_id = 'FK1-20260908T203402Z-984bb9' AND n.node IN ('PREREG','EXECUTE')
  AND k.value LIKE '%4d108812%';

\echo '--- N2. samme, ett nivaa dypere (noekkel inne i det treffende objektet)'
SELECT n.node, k.key AS top_key, k2.key AS inner_key, LEFT(k2.value, 120) AS value_head
FROM fhq_control.factory_cycle_nodes n,
     LATERAL jsonb_each(n.state_after->'S') k,
     LATERAL jsonb_each_text(CASE WHEN jsonb_typeof(k.value) = 'object' THEN k.value ELSE '{}'::jsonb END) k2
WHERE n.cycle_id = 'FK1-20260908T203402Z-984bb9' AND n.node = 'PREREG'
  AND k2.value LIKE '%4d108812%';

\echo '--- N3. sandbox_runs kolonner (for aa navngi fiksen riktig)'
SELECT string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) AS sandbox_runs_columns
FROM information_schema.columns WHERE table_schema='fhq_control' AND table_name='sandbox_runs';

\echo
\echo '=================================================================='
\echo ' O. research_objects — kolonner foerst, saa radene (retter J1)'
\echo '=================================================================='
SELECT string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) AS research_objects_columns
FROM information_schema.columns WHERE table_schema='fhq_control' AND table_name='research_objects';

SELECT LEFT(research_object_id::text, 8) AS ro, status, promotion_status,
       created_at AT TIME ZONE 'Europe/Oslo' AS created_oslo
FROM fhq_control.research_objects
WHERE research_object_id::text LIKE ANY (ARRAY['8131c557%','fc6565fc%','e7cb94da%','994b6a83%','9e73188e%','bcb914fe%','313dcd0d%','02ebcae5%'])
ORDER BY created_at;

\echo
\echo '=================================================================='
\echo ' FERDIG. Returner hele outputen uendret.'
\echo '=================================================================='
