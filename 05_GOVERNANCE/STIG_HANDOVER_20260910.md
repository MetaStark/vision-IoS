# STIG — OVERLEVERING TIL NESTE ØKT (2026-09-10)

**Til deg som starter:** Du er STIG-HOST, driftsgrenen av STIG, og du kjører **lokalt på
FjordHQ-verten** (Windows), der databasen faktisk lever. Den forrige STIG kjørte i skyen og nådde
ikke databasen, så CEO måtte kopiere hver kommando frem og tilbake i tolv timer. **Din hele grunn
til å eksistere er å fjerne det relé-et.** Du har `psql`, `docker` og `D:\Runtime` rett foran deg.
Bruk dem direkte. Ikke be CEO om å lime inn noe du kan kjøre selv.

Du opererer under `CLAUDE.md` (STIG-identitet, Zero-Assumption) og fullmakts-policyen i
`05_GOVERNANCE/AUTONOMY_03_TIER_POLICY.md`. Les begge først.

---

## 0. KOBLE DEG PÅ (gjør dette først, hver oppstart)

```powershell
# a) Credential fra Machine-scope (satt riktig 2026-09-09, se plan § 18.8):
if (-not $env:PGPASSWORD) { $env:PGPASSWORD = [Environment]::GetEnvironmentVariable('PGPASSWORD','Machine') }

# b) Bekreft databasen (skal gi ok = 1):
psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -c "SELECT 1 AS ok, NOW() AT TIME ZONE 'Europe/Oslo' AS oslo;"

# c) Bekreft db-containeren lever:
docker ps --filter "publish=54322" --format "{{.Names}} {{.Status}}"
#    forventet: supabase_db_fhq-market-system  Up ...

# d) Arbeidskopi: bruk en ren worktree, IKKE C:\fhq-market-system\vision-ios (den har
#    30 divergerende filer, plan § 20.8). Om den ikke finnes:
#    git worktree add D:\stig-host claude/explain-learning-loop-Sa9z7
cd D:\stig-host

# e) Les tilstanden i ett blikk:
powershell -ExecutionPolicy Bypass -File D:\Runtime\stig_host_watch.ps1
```

**Roller (verifisert):** `postgres` er IKKE superbruker (Supabase-mønster, plan § 18.9);
`supabase_admin` er det. GRANT/DDL kjøres som `supabase_admin`. Kjøretidsjobbene kobler seg til
som `fhq_executive_task` (leser `.env` i a0-containeren). `pg_hba` krever passord fra alt utenfor
db-containerens loopback — ingen `trust`, ingen snarvei.

---

## 1. HVA SOM ER GJORT (kort — full historikk i plan-dokumentet)

Referanse: `12_DAILY_REPORTS/AUTONOMOUS_OPS_IMPLEMENTATION_PLAN_20260908.md`, § 11–23. Det er
den kanoniske loggen. Alt under er oppsummering.

- **Systemet var dødt i 5 døgn** fordi `.env` byttet DB-bruker til `fhq_executive_task` uten
  passord 2026-09-04T22:55:49Z. En autonom a0-økt reparerte det 2026-09-09 (§ 18–19).
- **To løkker, ikke én:** runtime-kadensen (`fhq_runtime.run_attempts`, STEP01–08) er FRISK.
  Forskningsfabrikken (`fhq_control`, FK1-*) er IDLE siden 08.09 (§ 22.2).
- **PR #20 er flettet** til master (`0c56231d`). Grenen `claude/explain-learning-loop-Sa9z7` er
  restartet derfra; nytt arbeid er ferske commits på den.
- **Drift-rettigheter (D15) gitt** i flere pass til `fhq_executive_task`; siste var
  `baseline_controls_v5` under G4. Generatoren er `scripts/d15_grant_package.ps1` (rullende
  15-min vindu, styringsvakt på `fhq_governance`).
- **D14 lukket:** Machine-`PGPASSWORD` er riktig. **D18 lukket:** port 54322 brannmuret til
  loopback. **D13 lukket:** 500-tegns logg-kapping fjernet i `runa_cadence_executor.py`.
- **Helsevakt kjører** hvert 15. min via Task Scheduler «STIG-HOST-WATCH» →
  `D:\Runtime\digest\`.

## 2. DET STORE UOPPGJORTE: LÆRINGSLØKKEN ER BRUTT (§ 22)

Fabrikken feller dommer (`KILLED` osv.) men **forplanter dem aldri** til scoring: 0 skrivinger
til `outcome_ledger`/brier/kalibrering/LVI siden restart. Brier (~39k) og LVI (629) er
mai-fossiler. «Neste hypotese bedre» finnes ikke som mekanisme. To tomme ledd:

- **Tilførsel (§ 22.7):** 0 rader i `FROZEN_FOR_EXPERIMENT`; kjernen konsumerer bare den
  statusen. Auto-proben er av (`llm_probe_on_empty_queue=False`, LARS-ruling R-2-prime,
  `factory_kernel_v1.py` ~linje 1520). Budsjett IKKE oppbrukt (7/40, 15/80). Ingen fence.
- **Bro (§ 22.5):** ingen kodebane fra dom til `fhq_research.outcome_ledger` (den ENE ekte
  append-only-loggen, ~137k rader, DB-håndhevet immutabel). D11: koblingen dom↔hypotese finnes
  i JSON (`prereg_id`), ikke som fremmednøkkel.

## 3. VENTER PÅ MENNESKER (ikke på deg)

- **CEO:** har godkjent selv-mating av fabrikken i prinsippet, venter på at du gir a0/kjører
  selve endringen. Se § 4 under.
- **LARS:** spak A (frys DRAFT via FINN) vs spak B (slå på auto-probe). STIG anbefaler B med
  budsjett-grensen på, fordi den gjør fabrikken selvgående og er reversibel + observerbar via
  vakten. Reverserer R-2-prime → informer LARS.
- **VEGA:** ratifiser `AUTONOMY_03_TIER_POLICY.md`, særlig om INSERT til
  `fhq_research.outcome_ledger` er Tier 1 (så broen kan kjøre autonomt).
- **G4:** opprett `fhq_control.autonomy_ledger` (`AUTONOMY_01_LEDGER_SPEC.md`).

## 4. DITT FØRSTE OPPDRAG (når CEO sier «kjør»)

Slå på fabrikkens selv-mating, trygt og reversibelt:

1. **Les (kun SELECT):** bekreft budsjett-grensen står i `factory_kernel_v1.py` (`DEFAULT_CAPS`,
   `case_llm_calls=80`), og at `llm_probe_on_empty_queue=False` er den aktive linja (~1520).
2. **Foreslå den minimale endringen** til CEO før du gjør den: sett flagget til `True`. Ta backup
   av fila med tidsstempel (som a0s mønster). Dette reverserer LARS R-2-prime — skriv det
   eksplisitt i forslaget, og at det er reversibelt (kopier backup tilbake).
3. **Etter CEO-ja:** gjør endringen, logg til `autonomy_ledger` hvis den finnes (ellers til
   `D:\Runtime\digest\`), og se vakten innen 15 min: `sandbox_runs`-tellingen skal stige over 0.
4. **Bygg så dom-til-score-broen** (§ 22.5) — men det krever VEGA Tier 1 på
   `fhq_research.outcome_ledger` først. Uten det: forbered specen, ikke kjør.

## 5. UROKKELIGE REGLER (fra CLAUDE.md, arves)

- Ingen skriving til `fhq_governance`/`fhq_meta`/`fhq_research` uten G4 (alltid Tier 2).
- Ingen DDL uten G4. Ingen sletting. Ingen antagelser — verifiser mot `information_schema`.
- Ingen stille feil — eskalér med full traceback.
- Du reparerer drift; du eier ikke retning. LARS eier retning. Du foreslår, du bygger ikke
  strategi uten ordre.
- Hver ikke-triviell handling: backup + reversibel + logg. Court-proof (spørring, resultat, hash).

## 6. COMMIT-SIGNATUR

Grenen er `claude/explain-learning-loop-Sa9z7` (restartet fra master). Push dit. Avslutt commits:

```
Co-Authored-By: Claude <noreply@anthropic.com>
```

(Ikke skriv modellnavn i commits, PR-er eller kode — kun i chat.)

---

**Første melding du bør sende CEO:** «STIG-HOST er på verten. DB nådd (ok=1), container oppe,
vakt lest. [tre helsetall]. Klar til å slå på fabrikkens selv-mating på ditt ja, eller ta en
annen retning. Hva vil du?»
