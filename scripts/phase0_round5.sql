-- ============================================================================
-- FASE 0 — RUNDE 5 (valgfri, liten)  (etter phase0_round4_result.txt 2026-09-09 16:25 Oslo)
-- ============================================================================
-- Kun lesing. To spoersmaal som gjoer D10 og D11 handlingsklare:
--   F  unntaksklassen for hver av de ti doede jobbene (siste linje av tracebacken)
--   G  eksplisitt mapping: RO -> syklus -> pregede node-id -> sandbox_run, for 08.09
--   psql -h host.docker.internal -p 54322 -U postgres -d postgres -f phase0_round5.sql > phase0_round5_result.txt 2>&1
-- ============================================================================
\set ON_ERROR_STOP off
\pset pager off
\pset footer on
\timing off

\echo
\echo '=================================================================='
\echo ' F. D10 — UNNTAKSKLASSE per doed jobb (siste ikke-tomme linje av error_message)'
\echo '=================================================================='
WITH lastline AS (
  SELECT run_id, created_at,
         regexp_replace(error_message, '\s+$', '') AS msg
  FROM fhq_runtime.run_failures
  WHERE created_at >= '2026-09-09 11:11:00+02'
)
SELECT run_id, COUNT(*) AS n,
       LEFT(regexp_replace(
              split_part(msg, E'\n', array_length(string_to_array(msg, E'\n'), 1)),
              '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f-]{20,}', 'UUID', 'g'), 140) AS exception_last_line
FROM lastline GROUP BY run_id, 3 ORDER BY n DESC, run_id;

\echo '--- F2. den fulle tracebacken for ETT eksempel per jobb (siste forekomst)'
SELECT DISTINCT ON (run_id) run_id, created_at AT TIME ZONE 'Europe/Oslo' AS at_oslo,
       LEFT(error_message, 900) AS traceback
FROM fhq_runtime.run_failures
WHERE created_at >= '2026-09-09 11:11:00+02'
ORDER BY run_id, created_at DESC;

\echo '--- F3. hva kjoerer de ti egentlig — triggered_by, host, siste result_summary'
SELECT DISTINCT ON (run_id) run_id, triggered_by, trigger_reason, host_hostname, exit_code,
       LEFT(result_summary::text, 160) AS result_summary
FROM fhq_runtime.run_attempts
WHERE started_at >= '2026-09-09 11:11:00+02' AND status <> 'SUCCESS'
ORDER BY run_id, started_at DESC;

\echo
\echo '=================================================================='
\echo ' G. D11 — MAPPING: RO -> syklus -> pregede node-id -> sandbox_run (08.09)'
\echo '=================================================================='
\echo '--- G1. FORMALIZE-noder 08.09: RO-id inn, pregede hypothesis/mechanism/family-node ut'
SELECT cycle_id,
       state_after->'S'->'proposal'->>'research_object_id'                 AS ro_id,
       state_after->'S'->'proposal'->'ro_experiment_spec'->>'exp_id'       AS exp_id,
       state_after->'S'->'hypothesis'->>'hypothesis_node'                  AS hypothesis_node,
       state_after->'S'->'hypothesis'->>'mechanism_node'                   AS mechanism_node,
       state_after->'S'->'hypothesis'->>'family_node'                      AS family_node,
       completed_at AT TIME ZONE 'Europe/Oslo'                             AS completed_oslo
FROM fhq_control.factory_cycle_nodes
WHERE node = 'FORMALIZE' AND started_at >= '2026-09-08 00:00:00+02'
ORDER BY completed_at;

\echo '--- G2. sandbox_runs 08.09 med veggtid >= 1 s: hvilket node-id er research_object_id?'
SELECT s.created_at AT TIME ZONE 'Europe/Oslo' AS run_oslo, s.research_object_id AS run_ro_field, s.wall_seconds,
       n.cycle_id,
       CASE WHEN s.research_object_id::text = n.state_after->'S'->'hypothesis'->>'hypothesis_node' THEN 'hypothesis_node'
            WHEN s.research_object_id::text = n.state_after->'S'->'hypothesis'->>'mechanism_node'  THEN 'mechanism_node'
            WHEN s.research_object_id::text = n.state_after->'S'->'hypothesis'->>'family_node'     THEN 'family_node'
            ELSE 'no-match-in-FORMALIZE' END AS matches,
       n.state_after->'S'->'proposal'->>'research_object_id' AS true_ro_id
FROM fhq_control.sandbox_runs s
LEFT JOIN fhq_control.factory_cycle_nodes n
  ON n.node = 'FORMALIZE'
 AND s.research_object_id::text IN (n.state_after->'S'->'hypothesis'->>'hypothesis_node',
                                    n.state_after->'S'->'hypothesis'->>'mechanism_node',
                                    n.state_after->'S'->'hypothesis'->>'family_node')
WHERE s.wall_seconds >= 1
ORDER BY s.created_at;

\echo '--- G3. hvilke noder (alle typer) refererer de seks id-ene — node-type og syklus'
SELECT n.cycle_id, n.node, n.exit_status, n.completed_at AT TIME ZONE 'Europe/Oslo' AS completed_oslo
FROM fhq_control.factory_cycle_nodes n
WHERE n::text ~ '(4d108812|9521001e|995ab43b|b507dd45|c5deca1f|ee438f68)'
ORDER BY n.completed_at, n.node;

\echo '--- G4. VERDICT-noder 08.09: hva ble dommen, og paa hvilket grunnlag (result-hash fra kjoering?)'
SELECT cycle_id, exit_status,
       LEFT(state_after->'S'->>'verdict', 300) AS verdict,
       completed_at AT TIME ZONE 'Europe/Oslo' AS completed_oslo
FROM fhq_control.factory_cycle_nodes
WHERE node ILIKE '%VERDICT%' AND started_at >= '2026-09-08 00:00:00+02'
ORDER BY completed_at;

\echo
\echo '=================================================================='
\echo ' FERDIG. Returner hele outputen uendret.'
\echo '=================================================================='
