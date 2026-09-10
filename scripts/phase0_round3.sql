-- ============================================================================
-- FASE 0 — RUNDE 3  (etter phase0_followup_result.txt 2026-09-09 15:38 Oslo)
-- ============================================================================
-- Kun lesing. Kolonnenavn kjent fra runde 2 der de brukes; ellers oppdagelse + DO-blokk
-- som finner siste tidsstempel per tabell uten å kjenne kolonnene (RAISE NOTICE).
--   psql -h host.docker.internal -p 54322 -U postgres -d postgres -f phase0_round3.sql > phase0_round3_result.txt 2>&1
-- ============================================================================
\set ON_ERROR_STOP off
\pset pager off
\pset footer on
\timing off

\echo
\echo '=================================================================='
\echo ' R1. FABRIKKEN NÅ — sandbox_runs siste 12, per dag, syntetisk signatur kvantifisert'
\echo '=================================================================='
SELECT created_at AT TIME ZONE 'Europe/Oslo' AS created_oslo, status, owner, exit_code,
       wall_seconds, LEFT(stdout_sha256, 12) AS stdout_sha, LEFT(research_object_id::text, 8) AS ro,
       LEFT(candidate_version, 28) AS candidate
FROM fhq_control.sandbox_runs ORDER BY created_at DESC LIMIT 12;

\echo '--- R1b. per dag: antall, distinkte stdout-hasher, snitt/maks veggtid, andel < 1 s'
SELECT (created_at AT TIME ZONE 'Europe/Oslo')::date AS day, COUNT(*) AS runs,
       COUNT(DISTINCT stdout_sha256) AS distinct_stdout,
       ROUND(AVG(wall_seconds)::numeric, 2) AS avg_wall_s, ROUND(MAX(wall_seconds)::numeric, 2) AS max_wall_s,
       COUNT(*) FILTER (WHERE wall_seconds < 1) AS sub_1s,
       COUNT(*) FILTER (WHERE status = 'COMPLETED') AS completed, COUNT(*) FILTER (WHERE status = 'RUNNING') AS still_running
FROM fhq_control.sandbox_runs GROUP BY 1 ORDER BY 1;

\echo '--- R1c. de "reelle" kjøringene ifølge ASTRID: veggtid >= 1 s og unik stdout'
SELECT created_at AT TIME ZONE 'Europe/Oslo' AS created_oslo, status, owner, wall_seconds,
       LEFT(stdout_sha256, 12) AS stdout_sha, LEFT(research_object_id::text, 8) AS ro, LEFT(command, 70) AS cmd
FROM fhq_control.sandbox_runs
WHERE wall_seconds >= 1 ORDER BY created_at DESC LIMIT 10;

\echo '--- R1d. factory_cycles: kolonner + siste 5 (18 sykluser i dag)'
SELECT string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) AS columns
FROM information_schema.columns WHERE table_schema='fhq_control' AND table_name='factory_cycles';
SELECT * FROM fhq_control.factory_cycles LIMIT 5;

\echo
\echo '=================================================================='
\echo ' R2. ASTRIDs seks RO-er — status, og hvilke sandbox_runs som faktisk hører til dem'
\echo '=================================================================='
SELECT LEFT(research_object_id::text, 8) AS ro, status, promotion_status, review_status,
       frozen_at AT TIME ZONE 'Europe/Oslo' AS frozen_oslo, owner, LEFT(research_question, 50) AS question
FROM fhq_control.research_objects
WHERE research_object_id::text LIKE ANY (ARRAY['e7cb94da%','994b6a83%','9e73188e%','313dcd0d%','02ebcae5%','bcb914fe%'])
ORDER BY frozen_at DESC NULLS LAST;

\echo '--- R2b. sandbox_runs for disse RO-ene (forventet: 89-90 for 994b6a83 / 9e73188e)'
SELECT LEFT(research_object_id::text, 8) AS ro, created_at AT TIME ZONE 'Europe/Oslo' AS created_oslo, status, wall_seconds, LEFT(stdout_sha256, 12) AS stdout_sha
FROM fhq_control.sandbox_runs
WHERE research_object_id::text LIKE ANY (ARRAY['e7cb94da%','994b6a83%','9e73188e%','313dcd0d%','02ebcae5%','bcb914fe%'])
ORDER BY created_at DESC;

\echo '--- R2c. hvilke RO-er eier kjøringene med veggtid >= 1 s'
SELECT LEFT(s.research_object_id::text, 8) AS ro, r.status AS ro_status, r.promotion_status, COUNT(*) AS real_runs, MAX(s.wall_seconds) AS max_wall
FROM fhq_control.sandbox_runs s LEFT JOIN fhq_control.research_objects r USING (research_object_id)
WHERE s.wall_seconds >= 1 GROUP BY 1,2,3 ORDER BY real_runs DESC;

\echo
\echo '=================================================================='
\echo ' R3. D10 — 530 av 583 kjøreforsøk feilet: hvorfor?'
\echo '=================================================================='
SELECT string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) AS columns
FROM information_schema.columns WHERE table_schema='fhq_runtime' AND table_name='run_failures';
SELECT * FROM fhq_runtime.run_failures LIMIT 6;
\echo '--- R3b. run_attempts: kolonner + 4 rader'
SELECT string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) AS columns
FROM information_schema.columns WHERE table_schema='fhq_runtime' AND table_name='run_attempts';
SELECT * FROM fhq_runtime.run_attempts LIMIT 4;
\echo '--- R3c. feil-klassifisering via tekst (kolonne-agnostisk): topp 10 signaturer'
SELECT LEFT(regexp_replace(t::text, '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f-]{20,}', 'UUID', 'g'), 110) AS signature, COUNT(*) AS n
FROM fhq_runtime.run_failures t GROUP BY 1 ORDER BY n DESC LIMIT 10;

\echo
\echo '=================================================================='
\echo ' R4. SISTE SKRIVING PER LEDGER — uten å kjenne kolonnene (maks over alle timestamp-kolonner)'
\echo '=================================================================='
DO $$
DECLARE r RECORD; c RECORD; v TIMESTAMPTZ; best TIMESTAMPTZ; bestcol TEXT; n BIGINT;
BEGIN
  FOR r IN SELECT * FROM (VALUES
      ('fhq_research','outcome_ledger'), ('fhq_governance','brier_score_ledger'), ('fhq_monitoring','run_ledger'),
      ('fhq_learning','decision_outcome_ledger'), ('fhq_learning','hypothesis_ledger'), ('fhq_learning','outcome_ledger'),
      ('fhq_learning','killswitch_registry'), ('fhq_governance','lvi_canonical'), ('fhq_ops','control_room_lvi'),
      ('fhq_market','prices_archived_20260904'), ('fhq_execution','shadow_trades'), ('fhq_perception','regime_daily'),
      ('fhq_control','factory_cycles'), ('fhq_control','trajectory_ledger'), ('fhq_learning','hypothesis_canon'),
      ('fhq_learning','btc_probability_signals'), ('fhq_regime','btcusd_regime_state'), ('fhq_truth','btcusd_price_candle'),
      ('fhq_research','challenger_forward_episodes'), ('fhq_news','fhq_news_archive')
    ) AS t(s, tb)
  LOOP
    best := NULL; bestcol := NULL;
    EXECUTE format('SELECT COUNT(*) FROM %I.%I', r.s, r.tb) INTO n;
    FOR c IN SELECT column_name FROM information_schema.columns
             WHERE table_schema = r.s AND table_name = r.tb AND data_type LIKE 'timestamp%'
    LOOP
      BEGIN
        EXECUTE format('SELECT MAX(%I) FROM %I.%I', c.column_name, r.s, r.tb) INTO v;
        IF v IS NOT NULL AND (best IS NULL OR v > best) THEN best := v; bestcol := c.column_name; END IF;
      EXCEPTION WHEN OTHERS THEN NULL; END;
    END LOOP;
    RAISE NOTICE 'LASTWRITE %.% rows=% last=% via=%', r.s, r.tb, n, COALESCE((best AT TIME ZONE 'Europe/Oslo')::text, 'NULL'), COALESCE(bestcol, '-');
  END LOOP;
END $$;

\echo
\echo '=================================================================='
\echo ' R5. pg_cron — den fjerde planleggingskonteksten (kjører SQL inne i DB-en)'
\echo '=================================================================='
SELECT jobid, jobname, schedule, active, username, LEFT(command, 100) AS command FROM cron.job ORDER BY jobid;
\echo '--- R5b. siste 12 kjøringer'
SELECT jobid, status, start_time AT TIME ZONE 'Europe/Oslo' AS start_oslo, LEFT(return_message, 80) AS msg
FROM cron.job_run_details ORDER BY start_time DESC LIMIT 12;

\echo
\echo '=================================================================='
\echo ' R6. hypothesis_canon — når skjedde massedrapet, og hvorfor'
\echo '=================================================================='
SELECT DATE_TRUNC('week', falsified_at AT TIME ZONE 'Europe/Oslo')::date AS week, COUNT(*) AS falsified
FROM fhq_learning.hypothesis_canon WHERE falsified_at IS NOT NULL GROUP BY 1 ORDER BY 1;
\echo '--- R6b. annihilation_reason topp 10'
SELECT LEFT(annihilation_reason, 80) AS reason, COUNT(*) AS n FROM fhq_learning.hypothesis_canon
WHERE annihilation_reason IS NOT NULL GROUP BY 1 ORDER BY n DESC LIMIT 10;
\echo '--- R6c. generator_id og asset_class fordeling'
SELECT generator_id, asset_class, COUNT(*) AS n, COUNT(*) FILTER (WHERE deflated_sharpe_computed) AS dsr_computed
FROM fhq_learning.hypothesis_canon GROUP BY 1,2 ORDER BY n DESC LIMIT 12;

\echo
\echo '=================================================================='
\echo ' R7. market_prices_live — hva strømmer NÅ (siste rader), og synthetic-flagg-status'
\echo '=================================================================='
SELECT id, asset, source, market_type, price, event_time_utc, arrival_time_utc, ingestion_latency_ms, event_time_synthetic
FROM fhq_core.market_prices_live ORDER BY id DESC LIMIT 6;
SELECT asset, COUNT(*) AS rows, MIN(event_time_utc) AS first_utc, MAX(event_time_utc) AS last_utc,
       COUNT(*) FILTER (WHERE event_time_synthetic) AS flagged_synthetic
FROM fhq_core.market_prices_live GROUP BY asset ORDER BY rows DESC;

\echo
\echo '=================================================================='
\echo ' R8. Hvem er koblet til nå — full query for de idle pool-tilkoblingene fra vertssiden'
\echo '=================================================================='
SELECT pid, usename, client_addr, backend_start AT TIME ZONE 'Europe/Oslo' AS start_oslo, state,
       state_change AT TIME ZONE 'Europe/Oslo' AS state_change_oslo, backend_type, LEFT(query, 160) AS query
FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid() ORDER BY backend_start;

\echo
\echo '=================================================================='
\echo ' FERDIG. Returner hele outputen uendret (inkl. NOTICE-linjene fra R4).'
\echo '=================================================================='
