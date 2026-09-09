-- ============================================================================
-- FASE 0 — RUNDE 4  (etter phase0_round3_result.txt 2026-09-09 16:07 Oslo)
-- ============================================================================
-- Kun lesing. Tre presise spørsmål: (Q1) feilrate i dag per run_id, (Q2) hvor de seks
-- RO-id-ene fra de reelle kjøringene bor, (Q3) dagens attempts. Kolonnenavn kjent fra runde 3.
--   psql -h host.docker.internal -p 54322 -U postgres -d postgres -f phase0_round4.sql > phase0_round4_result.txt 2>&1
-- ============================================================================
\set ON_ERROR_STOP off
\pset pager off
\pset footer on
\timing off

\echo
\echo '=================================================================='
\echo ' Q1. D10 — feilrate MÅLT DIREKTE (created_at >= DB-start 11:11 Oslo), per run_id'
\echo '=================================================================='
SELECT COUNT(*) AS failures_since_1111, COUNT(DISTINCT run_id) AS distinct_runs,
       MIN(created_at) AT TIME ZONE 'Europe/Oslo' AS first_oslo, MAX(created_at) AT TIME ZONE 'Europe/Oslo' AS last_oslo
FROM fhq_runtime.run_failures WHERE created_at >= '2026-09-09 11:11:00+02';
\echo '--- Q1b. per run_id i dag'
SELECT run_id, failure_type, COUNT(*) AS n, MAX(created_at) AT TIME ZONE 'Europe/Oslo' AS last_oslo,
       LEFT(regexp_replace(MIN(error_message), '\s+', ' ', 'g'), 120) AS sample_error
FROM fhq_runtime.run_failures WHERE created_at >= '2026-09-09 11:11:00+02'
GROUP BY run_id, failure_type ORDER BY n DESC LIMIT 20;
\echo '--- Q1c. attempts i dag: status-fordeling og suksessrate per run_id'
SELECT run_id, COUNT(*) AS attempts, COUNT(*) FILTER (WHERE status = 'SUCCESS') AS success,
       COUNT(*) FILTER (WHERE status <> 'SUCCESS') AS not_success,
       ROUND(AVG(duration_seconds)::numeric, 1) AS avg_s, MAX(started_at) AT TIME ZONE 'Europe/Oslo' AS last_oslo
FROM fhq_runtime.run_attempts WHERE started_at >= '2026-09-09 11:11:00+02'
GROUP BY run_id ORDER BY attempts DESC LIMIT 25;
\echo '--- Q1d. helhet i dag'
SELECT COUNT(*) AS attempts_today, COUNT(*) FILTER (WHERE status = 'SUCCESS') AS success,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status <> 'SUCCESS') / NULLIF(COUNT(*), 0), 1) AS failure_pct
FROM fhq_runtime.run_attempts WHERE started_at >= '2026-09-09 11:11:00+02';
\echo '--- Q1e. historisk: attempts og feil per måned (dater epokene i runtime-loopen)'
SELECT DATE_TRUNC('month', started_at)::date AS month, COUNT(*) AS attempts,
       COUNT(*) FILTER (WHERE status <> 'SUCCESS') AS not_success
FROM fhq_runtime.run_attempts GROUP BY 1 ORDER BY 1;

\echo
\echo '=================================================================='
\echo ' Q2. D11 — hvor bor de seks RO-id-ene som de reelle kjoeringene peker paa?'
\echo '=================================================================='
\echo '--- Q2a. research_objects: som research_object_id, som parent_ro_id, eller i tekst'
SELECT 'as_research_object_id' AS how, COUNT(*) FROM fhq_control.research_objects
 WHERE research_object_id::text LIKE ANY (ARRAY['4d108812%','9521001e%','995ab43b%','b507dd45%','c5deca1f%','ee438f68%'])
UNION ALL SELECT 'as_parent_ro_id', COUNT(*) FROM fhq_control.research_objects
 WHERE parent_ro_id::text LIKE ANY (ARRAY['4d108812%','9521001e%','995ab43b%','b507dd45%','c5deca1f%','ee438f68%'])
UNION ALL SELECT 'in_row_text', COUNT(*) FROM fhq_control.research_objects t
 WHERE t::text ~ '(4d108812|9521001e|995ab43b|b507dd45|c5deca1f|ee438f68)';
\echo '--- Q2b. lifecycle_events / factory_cycle_nodes / trajectory_ledger / hypothesis_canon: tekst-soek'
SELECT 'lifecycle_events' AS tbl, COUNT(*) FROM fhq_control.research_object_lifecycle_events t WHERE t::text ~ '(4d108812|9521001e|995ab43b|b507dd45|c5deca1f|ee438f68)'
UNION ALL SELECT 'factory_cycle_nodes', COUNT(*) FROM fhq_control.factory_cycle_nodes t WHERE t::text ~ '(4d108812|9521001e|995ab43b|b507dd45|c5deca1f|ee438f68)'
UNION ALL SELECT 'factory_cycles', COUNT(*) FROM fhq_control.factory_cycles t WHERE t::text ~ '(4d108812|9521001e|995ab43b|b507dd45|c5deca1f|ee438f68)'
UNION ALL SELECT 'trajectory_ledger', COUNT(*) FROM fhq_control.trajectory_ledger t WHERE t::text ~ '(4d108812|9521001e|995ab43b|b507dd45|c5deca1f|ee438f68)'
UNION ALL SELECT 'hypothesis_canon', COUNT(*) FROM fhq_learning.hypothesis_canon t WHERE t::text ~ '(4d108812|9521001e|995ab43b|b507dd45|c5deca1f|ee438f68)';
\echo '--- Q2c. de seks reelle kjoeringene i full bredde (dataset, code_hash, artifact_hashes, repro)'
SELECT created_at AT TIME ZONE 'Europe/Oslo' AS created_oslo, LEFT(research_object_id::text, 8) AS ro, candidate_version,
       LEFT(dataset_version_id::text, 8) AS dataset, LEFT(code_hash, 12) AS code, wall_seconds, exit_code,
       artifact_hashes, repro_command
FROM fhq_control.sandbox_runs WHERE wall_seconds >= 1 ORDER BY created_at;
\echo '--- Q2d. factory_cycle_nodes: kolonner + noder fra 2026-09-08 (koblingen kjoering <-> hypotese kan bo her)'
SELECT string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) AS columns
FROM information_schema.columns WHERE table_schema='fhq_control' AND table_name='factory_cycle_nodes';
SELECT * FROM fhq_control.factory_cycle_nodes t WHERE t::text LIKE '%2026-09-08%' LIMIT 8;
\echo '--- Q2e. lifecycle_events for ASTRIDs seks RO-er — evidence_ref peker kanskje paa kjoeringene'
SELECT LEFT(research_object_id::text, 8) AS ro, from_status, to_status, promotion_status, evidence_kind, evidence_ref,
       created_at AT TIME ZONE 'Europe/Oslo' AS created_oslo
FROM fhq_control.research_object_lifecycle_events
WHERE research_object_id::text LIKE ANY (ARRAY['e7cb94da%','994b6a83%','9e73188e%','313dcd0d%','02ebcae5%','bcb914fe%'])
ORDER BY created_at;

\echo
\echo '=================================================================='
\echo ' Q3. Kjeden RUN-20260908T190000Z — er den lukket? (factory_cycles, lifecycle_events)'
\echo '=================================================================='
SELECT cycle_id, case_id, phase, status, terminal_route, route_reason, LEFT(last_error, 80) AS last_error,
       started_at AT TIME ZONE 'Europe/Oslo' AS started_oslo, ended_at AT TIME ZONE 'Europe/Oslo' AS ended_oslo
FROM fhq_control.factory_cycles WHERE cycle_id ILIKE '%20260908T19%' OR case_id ILIKE '%20260908%' OR route_reason ILIKE '%RUN-20260908%'
ORDER BY started_at DESC LIMIT 10;
\echo '--- Q3b. factory_cycles siste 10 (er fabrikken pauset naa?)'
SELECT cycle_id, phase, status, terminal_route, route_reason, failure_count, LEFT(last_error, 60) AS last_error,
       heartbeat AT TIME ZONE 'Europe/Oslo' AS heartbeat_oslo
FROM fhq_control.factory_cycles ORDER BY heartbeat DESC LIMIT 10;

\echo
\echo '=================================================================='
\echo ' FERDIG. Returner hele outputen uendret.'
\echo '=================================================================='
