-- ============================================================================
-- FASE 0 — RUNDE 6  (etter phase0_round5_result.txt 2026-09-09 17:00 Oslo)
-- ============================================================================
-- Kun lesing. Tre ting runde 5 ikke kunne avgjoere:
--   H  D13: bevis avkuttingen av run_failures.error_message eksakt (kolonnedef + lengder)
--   I  D11: hvilket JSON-felt baerer kandidat-id-et — saa fiksen doeper riktig kolonne
--   J  Rapport-hygiene: finnes 8131c557 / fc6565fc / e7cb94da i research_objects?
--   psql -h host.docker.internal -p 54322 -U postgres -d postgres -f phase0_round6.sql > phase0_round6_result.txt 2>&1
-- MERK: unntaksklassen for D10 kan IKKE hentes med SQL. Se skallblokken i meldingen.
-- ============================================================================
\set ON_ERROR_STOP off
\pset pager off
\pset footer on
\timing off

\echo
\echo '=================================================================='
\echo ' H. D13 — er error_message avkuttet? Kolonnedefinisjon og lengder'
\echo '=================================================================='
\echo '--- H1. kolonnedefinisjon (character_maximum_length avgjoer saken)'
SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_schema = 'fhq_runtime' AND table_name = 'run_failures'
ORDER BY ordinal_position;

\echo '--- H2. lengdefordeling i dag: samler de seg paa ett tak?'
SELECT length(error_message) AS msg_len, COUNT(*) AS n
FROM fhq_runtime.run_failures
WHERE created_at >= '2026-09-09 11:11:00+02'
GROUP BY 1 ORDER BY n DESC, 1 DESC LIMIT 15;

\echo '--- H3. historisk maks og antall paa taket (hele tabellen)'
SELECT MAX(length(error_message)) AS max_len,
       MIN(length(error_message)) AS min_len,
       COUNT(*) AS total_rows,
       COUNT(*) FILTER (WHERE length(error_message) >= 495) AS rows_at_or_near_500,
       COUNT(*) FILTER (WHERE error_message ILIKE '%Error%' OR error_message ILIKE '%Exception%') AS rows_naming_an_exception
FROM fhq_runtime.run_failures;

\echo '--- H4. finnes unntaksklassen noe sted i tabellen? (de som IKKE er avkuttet)'
SELECT run_id, length(error_message) AS msg_len,
       LEFT(regexp_replace(error_message, '\s+', ' ', 'g'), 200) AS msg
FROM fhq_runtime.run_failures
WHERE (error_message ILIKE '%Error:%' OR error_message ILIKE '%Exception:%')
ORDER BY created_at DESC LIMIT 10;

\echo '--- H5. finnes det andre felt som kan baere aarsaken?'
SELECT string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) AS run_failures_columns
FROM information_schema.columns WHERE table_schema='fhq_runtime' AND table_name='run_failures';

\echo
\echo '=================================================================='
\echo ' I. D11 — hvilket JSON-felt baerer kandidat-id-et 4d108812?'
\echo '=================================================================='
\echo '--- I1. PREREG-noden for syklus FK1-20260908T203402Z-984bb9, hele state_after'
SELECT LEFT(jsonb_pretty(state_after), 3000) AS prereg_state_after
FROM fhq_control.factory_cycle_nodes
WHERE cycle_id = 'FK1-20260908T203402Z-984bb9' AND node = 'PREREG';

\echo '--- I2. EXECUTE-noden for samme syklus (koblingen til sandbox_run bor trolig her)'
SELECT LEFT(jsonb_pretty(state_after), 3000) AS execute_state_after
FROM fhq_control.factory_cycle_nodes
WHERE cycle_id = 'FK1-20260908T203402Z-984bb9' AND node = 'EXECUTE';

\echo '--- I3. topp-nivaa-noekler i state_after per node-type for samme syklus'
SELECT n.node, k.key, LEFT(k.value, 70) AS value_head
FROM fhq_control.factory_cycle_nodes n,
     LATERAL jsonb_each_text(COALESCE(n.state_after->'S', n.state_after)) k
WHERE n.cycle_id = 'FK1-20260908T203402Z-984bb9'
  AND n.node IN ('PREREG', 'EXECUTE', 'VERDICT')
ORDER BY n.node, k.key;

\echo
\echo '=================================================================='
\echo ' J. Rapport-hygiene — de to RO-ene som kjoerte uten aa staa i rapporten'
\echo '=================================================================='
\echo '--- J1. finnes de i research_objects?'
SELECT LEFT(research_object_id::text, 8) AS ro, status, promotion_status,
       LEFT(title, 70) AS title, created_at AT TIME ZONE 'Europe/Oslo' AS created_oslo
FROM fhq_control.research_objects
WHERE research_object_id::text LIKE ANY (ARRAY['8131c557%','fc6565fc%','e7cb94da%','994b6a83%','9e73188e%','bcb914fe%','313dcd0d%','02ebcae5%'])
ORDER BY created_at;

\echo '--- J2. livslopet for de to som manglet i rapporten'
SELECT LEFT(research_object_id::text, 8) AS ro, from_status, to_status, evidence_kind,
       LEFT(evidence_ref, 60) AS evidence_ref, created_at AT TIME ZONE 'Europe/Oslo' AS created_oslo
FROM fhq_control.research_object_lifecycle_events
WHERE research_object_id::text LIKE ANY (ARRAY['8131c557%','fc6565fc%'])
ORDER BY created_at;

\echo '--- J3. har fabrikken kjoert reelt etter 08.09? (veggtid >= 1 s, hele tabellen)'
SELECT DATE(created_at AT TIME ZONE 'Europe/Oslo') AS dag, COUNT(*) AS reelle_kjoeringer,
       ROUND(AVG(wall_seconds)::numeric, 2) AS snitt_sek
FROM fhq_control.sandbox_runs WHERE wall_seconds >= 1
GROUP BY 1 ORDER BY 1;

\echo
\echo '=================================================================='
\echo ' FERDIG. Returner hele outputen uendret.'
\echo '=================================================================='
