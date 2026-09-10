-- ============================================================================
-- FASE 0 — SANNHETSAVSTEMMING MOT DATABASEN
-- ============================================================================
-- Kjøres PÅ RUNTIME-VERTEN (der PostgreSQL 17.6 lytter på 127.0.0.1:54322).
-- Kilde: 12_DAILY_REPORTS/AUTONOMOUS_OPS_IMPLEMENTATION_PLAN_20260908.md § 4
--        05_GOVERNANCE/REPORTS/FJORDHQ_2027_INTEGRATION_PLAN.md § 5 (Q4 2026, 0.1)
--
--   psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -f scripts/phase0_verify.sql > phase0_result.txt 2>&1
--
-- Prinsipp (CLAUDE.md, Zero-Assumption): verifiser skjema-eksistens via
-- information_schema FØR noe konkluderes som manglende. Tabeller hvis navn
-- ikke er kjent fra migrasjonene (LVI, kill-ledger, sandbox_runs,
-- research_objects) OPPDAGES her — de gjettes ikke.
--
-- Hele filen kjører selv om enkeltseksjoner feiler (ON_ERROR_STOP off), slik
-- at én manglende tabell ikke skjuler resten av bildet.
--
-- HOST-SJEKKER SOM IKKE ER SQL (kjør i tillegg, lim inn resultatet):
--   Merge-gate for fd0328b6 — PGPASSWORD i PLANLAGT kontekst, ikke interaktiv:
--     PowerShell:  [Environment]::GetEnvironmentVariable('PGPASSWORD','Machine') -ne $null
--                  [Environment]::GetEnvironmentVariable('PGPASSWORD','User')    -ne $null
--     crontab:     crontab -l | grep -nE 'PGPASSWORD=|source .*env|\. .*env'
--   D6 — guard_generation_freeze kompilerer?
--     python -m py_compile 03_FUNCTIONS/guard_generation_freeze.py && echo D6-OK
--   D5 — repo/runtime-drift:
--     git -C C:\fhq-market-system\vision-ios log -1 --format=%ci ; git fetch origin master ; git log -1 --format=%ci origin/master
-- ============================================================================

\set ON_ERROR_STOP off
\pset pager off
\pset footer on
\timing off

\echo
\echo '=================================================================='
\echo ' 0. KLOKKE OG INSTANS  (runbook DAY-nummer krever denne)'
\echo '=================================================================='
SELECT NOW() AT TIME ZONE 'Europe/Oslo' AS oslo_time,
       NOW() AT TIME ZONE 'UTC'         AS utc_time,
       current_database()                AS db,
       inet_server_addr()                AS server_addr,
       inet_server_port()                AS server_port,
       version()                         AS pg_version;

\echo
\echo '=================================================================='
\echo ' 1. SKJEMA-EKSISTENS  (Zero-Assumption: sjekk før konklusjon)'
\echo '=================================================================='
SELECT table_schema, COUNT(*) AS tables
FROM information_schema.tables
WHERE table_schema LIKE 'fhq\_%' OR table_schema LIKE 'vision\_%'
GROUP BY table_schema ORDER BY table_schema;

\echo
\echo '--- 1b. Tabeller planen bygger på: finnes de?'
WITH need(schema_name, table_name) AS (VALUES
  ('fhq_monitoring','daemon_health'),
  ('fhq_governance','orchestrator_cycles'),
  ('fhq_canonical','canonical_outcomes'),
  ('fhq_canonical','golden_needles'),
  ('fhq_governance','epistemic_proposals'),
  ('fhq_governance','epistemic_proposal_runs'),
  ('fhq_governance','epistemic_schedule_config'),
  ('fhq_governance','calibration_versions'),
  ('fhq_governance','learning_proposals'),
  ('fhq_governance','learning_versions'),
  ('fhq_memory','knowledge_fragments'),
  ('fhq_research','forecast_skill_registry'),
  ('fhq_governance','governance_actions_log'),
  ('fhq_ops','control_room_metrics')
)
SELECT n.schema_name || '.' || n.table_name AS required_table,
       CASE WHEN t.table_name IS NULL THEN 'MISSING' ELSE 'exists' END AS status
FROM need n
LEFT JOIN information_schema.tables t
  ON t.table_schema = n.schema_name AND t.table_name = n.table_name
ORDER BY status DESC, required_table;

\echo
\echo '--- 1c. OPPDAGELSE: tabeller for LVI / kill-ledger / sandbox / research objects (navn ukjent for planen)'
SELECT table_schema || '.' || table_name AS discovered_table
FROM information_schema.tables
WHERE (table_schema LIKE 'fhq\_%' OR table_schema LIKE 'vision\_%')
  AND (table_name ILIKE '%lvi%'
    OR table_name ILIKE '%kill%'
    OR table_name ILIKE '%ledger%'
    OR table_name ILIKE '%sandbox%'
    OR table_name ILIKE '%research_object%'
    OR table_name ILIKE '%tick%')
ORDER BY 1;

\echo
\echo '=================================================================='
\echo ' 2. KONTROLLPLAN — HVA KJØRER FAKTISK?  (D1: 106 filer / 5 forvaltet)'
\echo '=================================================================='
\echo '--- 2a. Alle daemoner i daemon_health, med alder på siste heartbeat'
SELECT daemon_name,
       status,
       last_heartbeat AT TIME ZONE 'Europe/Oslo'     AS last_heartbeat_oslo,
       date_trunc('minute', NOW() - last_heartbeat)  AS staleness
FROM fhq_monitoring.daemon_health
ORDER BY last_heartbeat DESC;

\echo '--- 2b. Fordeling — dette tallet mot 106 loop-filer er trippel-avstemmingen'
SELECT status, COUNT(*) AS daemons,
       COUNT(*) FILTER (WHERE last_heartbeat > NOW() - INTERVAL '1 hour') AS heartbeat_lt_1h,
       COUNT(*) FILTER (WHERE last_heartbeat < NOW() - INTERVAL '24 hours') AS stale_gt_24h
FROM fhq_monitoring.daemon_health
GROUP BY status ORDER BY daemons DESC;

\echo '--- 2c. Kontrollplanets 5 (daemon_manager.CRITICAL_DAEMONS): er de i daemon_health?'
WITH managed(name) AS (VALUES
  ('finn_brain_scheduler'),('finn_crypto_scheduler'),('economic_outcome_daemon'),
  ('g2c_continuous_forecast_engine'),('ios003b_intraday_regime_delta'))
SELECT m.name AS managed_daemon,
       COALESCE(d.status, 'NOT IN daemon_health') AS status,
       d.last_heartbeat AT TIME ZONE 'Europe/Oslo' AS last_heartbeat_oslo
FROM managed m
LEFT JOIN fhq_monitoring.daemon_health d
  ON d.daemon_name = m.name OR d.daemon_name ILIKE m.name || '%'
ORDER BY m.name;

\echo
\echo '=================================================================='
\echo ' 3. ORKESTRERINGSSYKLUSER — SISTE 7 DAGER'
\echo '=================================================================='
SELECT cycle_type,
       COUNT(*)                                   AS cycles,
       COUNT(*) FILTER (WHERE ended_at IS NULL)   AS still_open,
       MAX(started_at) AT TIME ZONE 'Europe/Oslo' AS last_started_oslo,
       MAX(ended_at)   AT TIME ZONE 'Europe/Oslo' AS last_ended_oslo
FROM fhq_governance.orchestrator_cycles
WHERE started_at > NOW() - INTERVAL '7 days'
GROUP BY cycle_type ORDER BY cycles DESC;

\echo
\echo '=================================================================='
\echo ' 4. GROUND TRUTH — canonical_outcomes  (M1/M4: finnes det utfall å lære av?)'
\echo '=================================================================='
SELECT COUNT(*)                                                   AS outcomes_total,
       COUNT(*) FILTER (WHERE exit_timestamp > NOW() - INTERVAL '30 days') AS last_30d,
       COUNT(*) FILTER (WHERE exit_timestamp > NOW() - INTERVAL '7 days')  AS last_7d,
       MIN(exit_timestamp) AT TIME ZONE 'Europe/Oslo'             AS first_oslo,
       MAX(exit_timestamp) AT TIME ZONE 'Europe/Oslo'             AS last_oslo,
       COUNT(*) FILTER (WHERE needle_eqs_score IS NOT NULL)       AS with_confidence_score
FROM fhq_canonical.canonical_outcomes;

\echo '--- 4b. Etter exit_reason (siste 30 d) — råmateriale for Brier/kalibrering'
SELECT exit_reason, COUNT(*) AS n,
       ROUND(AVG(CASE WHEN pnl_absolute > 0 THEN 1.0 ELSE 0.0 END)*100, 1) AS win_rate_pct,
       ROUND(AVG(pnl_percent)::numeric, 3) AS avg_pnl_pct
FROM fhq_canonical.canonical_outcomes
WHERE exit_timestamp > NOW() - INTERVAL '30 days'
GROUP BY exit_reason ORDER BY n DESC;

\echo
\echo '=================================================================='
\echo ' 5. EPISTEMISK LAG — Proposal Engine (mig 177) i drift?'
\echo '=================================================================='
SELECT 'schedule_config' AS item, is_active::text AS value, run_interval_hours::text AS detail
FROM fhq_governance.epistemic_schedule_config WHERE config_id = 'DEFAULT'
UNION ALL
SELECT 'proposal_runs', COUNT(*)::text, MAX(run_started_at)::text FROM fhq_governance.epistemic_proposal_runs
UNION ALL
SELECT 'proposals_' || status, COUNT(*)::text, MAX(generated_at)::text
FROM fhq_governance.epistemic_proposals GROUP BY status;

\echo
\echo '=================================================================='
\echo ' 6. KALIBRERING (mig 174) — hva er faktisk aktivt?'
\echo '=================================================================='
SELECT parameter_name, version, value, is_active,
       CASE WHEN is_active AND frozen_at IS NOT NULL THEN 'PRODUCTION'
            WHEN frozen_at IS NOT NULL THEN 'FROZEN'
            ELSE 'PROPOSED' END AS state,
       vega_approval_ref
FROM fhq_governance.calibration_versions
ORDER BY parameter_name, is_active DESC, frozen_at DESC NULLS LAST;

\echo
\echo '=================================================================='
\echo ' 7. GOVERNANCE — VEGA-avslagsrate  (§ 6: en VEGA som aldri avslår reviewer ikke)'
\echo '=================================================================='
SELECT status, COUNT(*) AS n, MIN(submitted_at)::date AS first, MAX(submitted_at)::date AS last
FROM fhq_governance.learning_proposals
GROUP BY status ORDER BY n DESC;

\echo '--- 7b. Avslagsrate blant avgjorte'
SELECT COUNT(*) FILTER (WHERE status='REJECTED') AS rejected,
       COUNT(*) FILTER (WHERE status='APPROVED') AS approved,
       CASE WHEN COUNT(*) FILTER (WHERE status IN ('APPROVED','REJECTED')) = 0 THEN NULL
            ELSE ROUND(100.0 * COUNT(*) FILTER (WHERE status='REJECTED')
                 / COUNT(*) FILTER (WHERE status IN ('APPROVED','REJECTED')), 1) END AS rejection_rate_pct
FROM fhq_governance.learning_proposals;

\echo
\echo '=================================================================='
\echo ' 8. KUNNSKAPSMINNE — knowledge_fragments (M3: forfall)'
\echo '=================================================================='
SELECT fragment_type, COUNT(*) AS n,
       ROUND(AVG(validity_score)::numeric, 3) AS avg_validity,
       ROUND(AVG(decay_rate)::numeric, 4)     AS avg_decay_rate,
       COUNT(DISTINCT decay_rate)             AS distinct_decay_rates
FROM fhq_memory.knowledge_fragments
GROUP BY fragment_type ORDER BY n DESC;

\echo
\echo '=================================================================='
\echo ' 9. SKILL-REGISTER — forecast_skill_registry (M2: sertifiserte modeller)'
\echo '=================================================================='
SELECT engine_module, COUNT(*) AS scorecards,
       COUNT(*) FILTER (WHERE is_certified) AS certified,
       ROUND(MAX(fss_score)::numeric, 4) AS best_fss,
       MAX(evaluation_date) AS last_eval
FROM fhq_research.forecast_skill_registry
GROUP BY engine_module ORDER BY scorecards DESC;

\echo
\echo '=================================================================='
\echo ' 10. SISTE GOVERNANCE-HANDLINGER  (kontekst for kjeden RUN-20260908T190000Z)'
\echo '=================================================================='
SELECT initiated_at AT TIME ZONE 'Europe/Oslo' AS at_oslo, action_type, initiated_by, decision,
       LEFT(decision_rationale, 90) AS rationale
FROM fhq_governance.governance_actions_log
ORDER BY initiated_at DESC LIMIT 15;

\echo
\echo '=================================================================='
\echo ' 11. RUNTIME DATA MAP  (04_DATABASE/CANONICAL_RUNTIME_DATA_MAP.md, 2026-03-09)'
\echo '     Kartet erklaerer "runtime truth". Settet er DISJUNKT fra seksjon 1b.'
\echo '     Vi velger ikke side her: begge sett maales, DB-en avgjoer hvilket som lever.'
\echo '=================================================================='
\echo '--- 11a. Finnes kartets tabeller?'
WITH need(schema_name, table_name) AS (VALUES
  ('fhq_core','market_prices_live'),
  ('fhq_market','prices'),
  ('fhq_research','indicator_momentum'),
  ('fhq_research','indicator_trend'),
  ('fhq_research','indicator_volatility'),
  ('fhq_research','indicator_volume'),
  ('fhq_research','indicator_ichimoku'),
  ('fhq_perception','regime_daily'),
  ('fhq_perception','sovereign_regime_state_v4'),
  ('fhq_learning','micro_regime_classifications'),
  ('fhq_execution','shadow_trades'),
  ('fhq_learning','outcomes'),
  ('fhq_learning','hypothesis_canon'),
  ('fhq_learning','calibration'),
  ('fhq_alpha','alpha_signals')
)
SELECT n.schema_name || '.' || n.table_name AS runtime_map_table,
       CASE WHEN t.table_name IS NULL THEN 'MISSING' ELSE 'exists' END AS status
FROM need n
LEFT JOIN information_schema.tables t
  ON t.table_schema = n.schema_name AND t.table_name = n.table_name
ORDER BY status DESC, runtime_map_table;

\echo '--- 11b. LIV: skriveaktivitet per tabell, kartets sett og seksjon-1b-settet side om side'
\echo '     (pg_stat_user_tables: kolonne-agnostisk; tellere siden siste stats-reset; n_live_tup er estimat)'
SELECT CASE WHEN (schemaname, relname) IN (
         ('fhq_core','market_prices_live'),('fhq_market','prices'),
         ('fhq_research','indicator_momentum'),('fhq_research','indicator_trend'),('fhq_research','indicator_volatility'),
         ('fhq_research','indicator_volume'),('fhq_research','indicator_ichimoku'),
         ('fhq_perception','regime_daily'),('fhq_perception','sovereign_regime_state_v4'),
         ('fhq_learning','micro_regime_classifications'),('fhq_execution','shadow_trades'),
         ('fhq_learning','outcomes'),('fhq_learning','hypothesis_canon'),('fhq_learning','calibration'),
         ('fhq_alpha','alpha_signals'))
       THEN 'RUNTIME-MAP' ELSE 'GOVERNANCE/EPISTEMIC' END AS side,
       schemaname || '.' || relname AS tbl,
       n_live_tup, n_tup_ins, n_tup_upd, n_tup_del,
       last_autoanalyze AT TIME ZONE 'Europe/Oslo' AS last_autoanalyze_oslo
FROM pg_stat_user_tables
WHERE (schemaname, relname) IN (
  ('fhq_core','market_prices_live'),('fhq_market','prices'),
  ('fhq_research','indicator_momentum'),('fhq_research','indicator_trend'),('fhq_research','indicator_volatility'),
  ('fhq_research','indicator_volume'),('fhq_research','indicator_ichimoku'),
  ('fhq_perception','regime_daily'),('fhq_perception','sovereign_regime_state_v4'),
  ('fhq_learning','micro_regime_classifications'),('fhq_execution','shadow_trades'),
  ('fhq_learning','outcomes'),('fhq_learning','hypothesis_canon'),('fhq_learning','calibration'),
  ('fhq_alpha','alpha_signals'),
  ('fhq_monitoring','daemon_health'),('fhq_governance','orchestrator_cycles'),
  ('fhq_canonical','canonical_outcomes'),('fhq_canonical','golden_needles'),
  ('fhq_governance','epistemic_proposals'),('fhq_governance','epistemic_proposal_runs'),
  ('fhq_governance','calibration_versions'),('fhq_governance','learning_proposals'),
  ('fhq_memory','knowledge_fragments'),('fhq_research','forecast_skill_registry'),
  ('fhq_governance','governance_actions_log'))
ORDER BY side, n_tup_ins DESC, tbl;

\echo '--- 11c. TO UTFALLSTABELLER, TO KALIBRERINGSTABELLER — hvilken er levende?'
SELECT schemaname || '.' || relname AS tbl, n_live_tup, n_tup_ins, n_tup_upd,
       last_autoanalyze AT TIME ZONE 'Europe/Oslo' AS last_autoanalyze_oslo
FROM pg_stat_user_tables
WHERE (schemaname, relname) IN (
  ('fhq_canonical','canonical_outcomes'), ('fhq_learning','outcomes'),
  ('fhq_governance','calibration_versions'), ('fhq_learning','calibration'))
ORDER BY tbl;

\echo '--- 11d. Kolonner i kartets kjernetabeller (STIG trenger disse for oppfoelgingsspoerringer)'
SELECT table_schema || '.' || table_name AS tbl,
       string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) AS columns
FROM information_schema.columns
WHERE (table_schema, table_name) IN (
  ('fhq_learning','outcomes'), ('fhq_learning','calibration'), ('fhq_learning','hypothesis_canon'),
  ('fhq_execution','shadow_trades'), ('fhq_alpha','alpha_signals'),
  ('fhq_perception','regime_daily'), ('fhq_market','prices'))
GROUP BY 1 ORDER BY 1;

\echo
\echo '=================================================================='
\echo ' FERDIG. Lim hele outputen tilbake til STIG sammen med host-sjekkene i toppen.'
\echo ' Seksjon 1c oppgir de faktiske tabellnavnene for fabrikken (sandbox_runs,'
\echo ' kill-ledger, research_objects); seksjon 11d oppgir kolonnene i runtime-kartets'
\echo ' kjernetabeller — STIG skriver oppfoelgingsspoerringer mot begge.'
\echo '=================================================================='
