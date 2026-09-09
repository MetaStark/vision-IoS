-- ============================================================================
-- FASE 0 — OPPFØLGING  (etter phase0_result.txt 2026-09-09 15:19 Oslo)
-- ============================================================================
-- Kun lesing. Kolonne-agnostisk der kolonnenavn er ukjente (SELECT * LIMIT, t::text LIKE,
-- pg_stat_*). Kjøres av Agent Zero mot host.docker.internal:54322.
--   psql -h host.docker.internal -p 54322 -U postgres -d postgres -f phase0_followup.sql > phase0_followup_result.txt 2>&1
-- ============================================================================
\set ON_ERROR_STOP off
\pset pager off
\pset footer on
\timing off

\echo
\echo '=================================================================='
\echo ' A. FABRIKKEN — finnes ASTRIDs 2026-09-08-aktivitet i denne databasen?'
\echo '=================================================================='
\echo '--- A1. sandbox_runs: totalt, og rader som nevner 2026-09-08 / 2026-09-07 (ASTRID: run 88-90)'
SELECT COUNT(*) AS sandbox_runs_total,
       COUNT(*) FILTER (WHERE t::text LIKE '%2026-09-08%') AS mentions_2026_09_08,
       COUNT(*) FILTER (WHERE t::text LIKE '%2026-09-07%') AS mentions_2026_09_07,
       COUNT(*) FILTER (WHERE t::text LIKE '%2026-09%')    AS mentions_2026_09,
       COUNT(*) FILTER (WHERE t::text LIKE '%2026-08%')    AS mentions_2026_08
FROM fhq_control.sandbox_runs t;

\echo '--- A2. sandbox_runs: kolonner'
SELECT string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) AS columns
FROM information_schema.columns WHERE table_schema='fhq_control' AND table_name='sandbox_runs';

\echo '--- A3. sandbox_runs: 5 rader (SELECT *)'
SELECT * FROM fhq_control.sandbox_runs LIMIT 5;

\echo '--- A4. research_objects: totalt, statusfordeling via tekst, nevner 2026-09'
SELECT COUNT(*) AS research_objects_total,
       COUNT(*) FILTER (WHERE t::text LIKE '%FACTORY_INVALID_TEST%') AS factory_invalid_test,
       COUNT(*) FILTER (WHERE t::text LIKE '%FROZEN_FOR_EXPERIMENT%') AS frozen_for_experiment,
       COUNT(*) FILTER (WHERE t::text LIKE '%VERDICT_RECORDED%')     AS verdict_recorded,
       COUNT(*) FILTER (WHERE t::text LIKE '%CONSUMED%')             AS consumed,
       COUNT(*) FILTER (WHERE t::text LIKE '%2026-09%')              AS mentions_2026_09
FROM fhq_control.research_objects t;

\echo '--- A5. research_objects: kolonner + 3 rader'
SELECT string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) AS columns
FROM information_schema.columns WHERE table_schema='fhq_control' AND table_name='research_objects';
SELECT * FROM fhq_control.research_objects LIMIT 3;

\echo '--- A6. research_object_lifecycle_events: totalt, nevner 2026-09-08, 5 rader'
SELECT COUNT(*) AS lifecycle_events_total,
       COUNT(*) FILTER (WHERE t::text LIKE '%2026-09-08%') AS mentions_2026_09_08
FROM fhq_control.research_object_lifecycle_events t;
SELECT * FROM fhq_control.research_object_lifecycle_events LIMIT 5;

\echo '--- A7. ASTRIDs RO-id-er: e7cb94da, 994b6a83, 9e73188e, 313dcd0d, 02ebcae5, bcb914fe — finnes de?'
SELECT 'research_objects' AS tbl, COUNT(*) AS hits FROM fhq_control.research_objects t
 WHERE t::text ~ '(e7cb94da|994b6a83|9e73188e|313dcd0d|02ebcae5|bcb914fe)'
UNION ALL
SELECT 'sandbox_runs', COUNT(*) FROM fhq_control.sandbox_runs t
 WHERE t::text ~ '(e7cb94da|994b6a83|9e73188e|313dcd0d|02ebcae5|bcb914fe)'
UNION ALL
SELECT 'lifecycle_events', COUNT(*) FROM fhq_control.research_object_lifecycle_events t
 WHERE t::text ~ '(e7cb94da|994b6a83|9e73188e|313dcd0d|02ebcae5|bcb914fe)';

\echo '--- A8. RUN-20260908T190000Z / tick 1161 — nevnt noe sted i fhq_control?'
SELECT table_name, COUNT(*) AS hits FROM (
  SELECT 'sandbox_runs' AS table_name FROM fhq_control.sandbox_runs t WHERE t::text ~ '(RUN-20260908|tick[_ ]?116[0-3])'
  UNION ALL SELECT 'research_objects' FROM fhq_control.research_objects t WHERE t::text ~ '(RUN-20260908|tick[_ ]?116[0-3])'
  UNION ALL SELECT 'lifecycle_events' FROM fhq_control.research_object_lifecycle_events t WHERE t::text ~ '(RUN-20260908|tick[_ ]?116[0-3])'
  UNION ALL SELECT 'trajectory_ledger' FROM fhq_control.trajectory_ledger t WHERE t::text ~ '(RUN-20260908|tick[_ ]?116[0-3])'
) x GROUP BY table_name;

\echo
\echo '=================================================================='
\echo ' B. HVEM ER KOBLET TIL NÅ  (definitiv liveness — uavhengig av hjerteslag)'
\echo '=================================================================='
SELECT pid, usename, application_name, client_addr, backend_start AT TIME ZONE 'Europe/Oslo' AS backend_start_oslo,
       state, wait_event_type, LEFT(query, 90) AS query_head
FROM pg_stat_activity
WHERE datname = current_database() AND pid <> pg_backend_pid()
ORDER BY backend_start;

\echo
\echo '=================================================================='
\echo ' C. NÅR BLE STATS NULLSTILT, OG HVA LEVER PÅ TVERS AV ALLE 49 SKJEMAER'
\echo '=================================================================='
\echo '--- C1. stats_reset daterer "siden reset" i 11b'
SELECT datname, stats_reset AT TIME ZONE 'Europe/Oslo' AS stats_reset_oslo, xact_commit, tup_inserted, tup_updated
FROM pg_stat_database WHERE datname = current_database();

\echo '--- C2. Topp 30 tabeller etter innsettinger siden reset — alle skjemaer'
SELECT schemaname || '.' || relname AS tbl, n_live_tup, n_tup_ins, n_tup_upd, n_tup_del,
       last_autoanalyze AT TIME ZONE 'Europe/Oslo' AS last_autoanalyze_oslo
FROM pg_stat_user_tables
WHERE n_tup_ins > 0 OR n_tup_upd > 0
ORDER BY n_tup_ins DESC, n_tup_upd DESC LIMIT 30;

\echo '--- C3. Topp 30 etter sist berørt (analyze/vacuum) — fanger tabeller skrevet før reset'
SELECT schemaname || '.' || relname AS tbl, n_live_tup,
       GREATEST(last_autoanalyze, last_analyze, last_autovacuum, last_vacuum) AT TIME ZONE 'Europe/Oslo' AS last_touched_oslo
FROM pg_stat_user_tables
WHERE GREATEST(last_autoanalyze, last_analyze, last_autovacuum, last_vacuum) IS NOT NULL
ORDER BY last_touched_oslo DESC LIMIT 30;

\echo '--- C4. Hvor mange tabeller har aldri blitt berørt siden reset'
SELECT COUNT(*) FILTER (WHERE n_tup_ins = 0 AND n_tup_upd = 0 AND n_tup_del = 0) AS untouched_since_reset,
       COUNT(*) AS user_tables_total
FROM pg_stat_user_tables;

\echo
\echo '=================================================================='
\echo ' D. LVI — Learning Velocity Index (planens styringsmål)'
\echo '=================================================================='
SELECT 'lvi_canonical' AS tbl, COUNT(*)::text AS rows, MAX(t::text) FILTER (WHERE FALSE) AS _ FROM fhq_governance.lvi_canonical t
UNION ALL SELECT 'lvi_timeseries', COUNT(*)::text, NULL FROM fhq_learning.lvi_timeseries
UNION ALL SELECT 'control_room_lvi', COUNT(*)::text, NULL FROM fhq_ops.control_room_lvi;
\echo '--- D2. v_system_lvi (view) — nåværende verdi'
SELECT * FROM fhq_governance.v_system_lvi LIMIT 5;
\echo '--- D3. lvi_timeseries: kolonner + siste 5 rader (SELECT *)'
SELECT string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) AS columns
FROM information_schema.columns WHERE table_schema='fhq_learning' AND table_name='lvi_timeseries';
SELECT * FROM fhq_learning.lvi_timeseries LIMIT 5;

\echo
\echo '=================================================================='
\echo ' E. BRIER OG UTFALLSLEDGERE — lever noen av dem?'
\echo '=================================================================='
SELECT schemaname || '.' || relname AS tbl, n_live_tup, n_tup_ins, n_tup_upd,
       GREATEST(last_autoanalyze, last_analyze) AT TIME ZONE 'Europe/Oslo' AS last_analyzed_oslo
FROM pg_stat_user_tables
WHERE (schemaname, relname) IN (
  ('fhq_governance','brier_score_ledger'),
  ('fhq_learning','outcome_ledger'), ('fhq_research','outcome_ledger'),
  ('fhq_learning','decision_outcome_ledger'), ('fhq_learning','expectation_outcome_ledger'),
  ('fhq_learning','decision_calibration_ledger'), ('fhq_learning','trade_calibration_ledger'),
  ('fhq_learning','calibration_candidate_ledger'), ('fhq_learning','hypothesis_ledger'),
  ('fhq_learning','killswitch_registry'), ('fhq_control','trajectory_ledger'),
  ('fhq_control','factory_search_budget_ledger'), ('fhq_monitoring','run_ledger'))
ORDER BY n_tup_ins DESC, tbl;
\echo '--- E2. Radantall (eksakt) for de samme'
SELECT 'brier_score_ledger' AS tbl, COUNT(*) FROM fhq_governance.brier_score_ledger
UNION ALL SELECT 'learning.outcome_ledger', COUNT(*) FROM fhq_learning.outcome_ledger
UNION ALL SELECT 'research.outcome_ledger', COUNT(*) FROM fhq_research.outcome_ledger
UNION ALL SELECT 'decision_outcome_ledger', COUNT(*) FROM fhq_learning.decision_outcome_ledger
UNION ALL SELECT 'hypothesis_ledger', COUNT(*) FROM fhq_learning.hypothesis_ledger
UNION ALL SELECT 'killswitch_registry', COUNT(*) FROM fhq_learning.killswitch_registry
UNION ALL SELECT 'run_ledger', COUNT(*) FROM fhq_monitoring.run_ledger;

\echo
\echo '=================================================================='
\echo ' F. hypothesis_canon — er falsifikasjonsdisiplinen BEFOLKET, ikke bare skjemaet?'
\echo '=================================================================='
SELECT COUNT(*) AS hypotheses_total,
       COUNT(*) FILTER (WHERE status = 'FALSIFIED' OR falsified_at IS NOT NULL) AS falsified,
       COUNT(*) FILTER (WHERE deflated_sharpe_computed) AS deflated_sharpe_computed,
       COUNT(*) FILTER (WHERE pbo_probability IS NOT NULL) AS with_pbo,
       COUNT(*) FILTER (WHERE pre_tier_score_at_birth IS NOT NULL) AS with_pre_tier_score,
       COUNT(*) FILTER (WHERE time_to_falsification_hours IS NOT NULL) AS with_ttf,
       ROUND(AVG(time_to_falsification_hours)::numeric, 1) AS avg_ttf_hours,
       MIN(created_at) AT TIME ZONE 'Europe/Oslo' AS first_oslo,
       MAX(created_at) AT TIME ZONE 'Europe/Oslo' AS last_oslo,
       COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') AS created_last_30d
FROM fhq_learning.hypothesis_canon;
\echo '--- F2. status-fordeling'
SELECT status, COUNT(*) AS n, MAX(last_updated_at) AT TIME ZONE 'Europe/Oslo' AS last_updated_oslo
FROM fhq_learning.hypothesis_canon GROUP BY status ORDER BY n DESC;
\echo '--- F3. kill-rate: falsified / (falsified + active-ish)'
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE falsified_at IS NOT NULL) / NULLIF(COUNT(*), 0), 1) AS falsified_pct_of_all
FROM fhq_learning.hypothesis_canon;

\echo
\echo '=================================================================='
\echo ' G. fhq_market — hvor ble prices av?  + shadow_trades og regime_daily radantall'
\echo '=================================================================='
SELECT table_name FROM information_schema.tables WHERE table_schema = 'fhq_market' ORDER BY 1;
SELECT 'shadow_trades' AS tbl, COUNT(*) AS rows, MAX(created_at) AT TIME ZONE 'Europe/Oslo' AS last_oslo FROM fhq_execution.shadow_trades
UNION ALL SELECT 'regime_daily', COUNT(*), MAX(created_at) AT TIME ZONE 'Europe/Oslo' FROM fhq_perception.regime_daily
UNION ALL SELECT 'market_prices_live', COUNT(*), NULL FROM fhq_core.market_prices_live;
\echo '--- G2. market_prices_live: kolonner + 3 rader (hva strømmer, fra hvilken kilde)'
SELECT string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) AS columns
FROM information_schema.columns WHERE table_schema='fhq_core' AND table_name='market_prices_live';
SELECT * FROM fhq_core.market_prices_live LIMIT 3;

\echo
\echo '=================================================================='
\echo ' H. § 5-anomalien: hva står faktisk i epistemic_schedule_config'
\echo '=================================================================='
SELECT string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) AS columns
FROM information_schema.columns WHERE table_schema='fhq_governance' AND table_name='epistemic_schedule_config';
SELECT * FROM fhq_governance.epistemic_schedule_config;

\echo
\echo '=================================================================='
\echo ' FERDIG. Returner hele outputen uendret.'
\echo '=================================================================='
