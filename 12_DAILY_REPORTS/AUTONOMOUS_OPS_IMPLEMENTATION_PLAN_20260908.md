# FjordHQ Autonomous Operations — Implementeringsplan

**Utsteder:** STIG (EC-003_2026_PRODUCTION)
**Dato:** 2026-09-08
**Status:** Fase 1 UTFØRT (§ 8) · Fase 3 UTFØRT: kontrollplan (§ 9) + masseendring 369 filer (§ 10) — **MERGE-GATE: `PGPASSWORD` bekreftet i Task Scheduler-kontekst på vert** · Fase 0/2 BLOKKERT (sannhetskilde utilgjengelig) · Fase 4 AVVENTER LARS
**Mandat:** Teknisk implementering. Retning eies av LARS. Godkjenning av VEGA/G4.

> **DAY-nummer ikke tildelt.** CLAUDE.md krever verifisering mot databaseklokken
> (`SELECT NOW() AT TIME ZONE 'Europe/Oslo'`) før runbook-navngiving.
> Databasen er utilgjengelig. Å gjette DAY-nummer ville brutt Zero-Assumption Protocol.

---

## 1. SANNHETSKILDE-STATUS (ADR-013)

| Kontroll | Kommando | Resultat |
|---|---|---|
| DB-tilkobling | `psql -h 127.0.0.1 -p 54322 -U postgres` | `Connection refused` |
| Postgres i container | `pgrep -a postgres` | Ingen prosess |
| Lyttere på 54322 | `ss -ltn` | Ingen |
| Utgående nett | `curl api.github.com` | HTTP 200 |
| `DATABASE_URL` | `env` | `postgresql://postgres:postgres@127.0.0.1:54322/postgres` |

**Konklusjon:** Dette er ikke en autorisasjonsfeil. `127.0.0.1` i eksekveringsmiljøet
peker på miljøets egen loopback. Runtime-databasen kjører på en annen maskin
(`C:/fhq-market-system/vision-ios`, Windows x64). Ingen ruting eksisterer mellom dem.

**Konsekvens:** Alt som krever DB-sannhet er markert `[GATED]` nedenfor.
Ingen tall i denne planen som er avhengig av DB er oppgitt som fakta.

---

## 2. VERIFISERTE FUNN (filsystem — krever ikke DB)

Alle funn under er reproduserbare med kommandoene som er oppgitt.

### D1 — Kontrollplanets dekningsgap

```bash
find . -name "*.py" \( -iname "*daemon*" -o -iname "*loop*" -o -iname "*schedul*" \
  -o -iname "*orchestrat*" -o -iname "*tick*" -o -iname "*runner*" -o -iname "*cycle*" \) \
  -not -path "./.git/*" | wc -l
# → 106

grep -cE "^    '[a-z0-9_]+': \{" 03_FUNCTIONS/daemon_manager.py
# → 5
```

| Metrikk | Verdi |
|---|---|
| Loop-/daemon-filer i repo | **106** |
| Registrert i `daemon_manager.CRITICAL_DAEMONS` | **5** |
| Uten start/stop/status/restart-kontroll | **101** |

De 5 forvaltede: `finn_brain_scheduler`, `finn_crypto_scheduler`,
`economic_outcome_daemon`, `g2c_continuous_forecast_engine`,
`ios003b_intraday_regime_delta`.

**Risiko:** 101 loops kan startes, henge eller dø uten at kontrollplanet vet det.
Autonom drift uten kontrollplan er ikke autonomi — det er ukontrollert eksekvering.

---

### D2 — Skyggekode: 33 duplikerte daemoner

```bash
for f in 05_ORCHESTRATOR/*.py; do b=$(basename "$f");
  [ -f "03_FUNCTIONS/$b" ] && { sha256sum "$f" "03_FUNCTIONS/$b"; }; done
```

| Kategori | Antall |
|---|---|
| Byte-identiske duplikater | **30** |
| **Divergerende kopier** | **3** |

Divergerende:

| Fil | 05_ORCHESTRATOR | 03_FUNCTIONS |
|---|---|---|
| `epistemic_proposal_daemon.py` | 371 linjer | 377 linjer |
| `finn_brain_scheduler.py` | 273 linjer | 310 linjer |
| `ios010_forecast_reconciliation_daemon.py` | 505 linjer | 534 linjer |

**Kontrollplanet påkaller utelukkende `03_FUNCTIONS/`** (verifisert i
`daemon_manager.py` — alle `script`-felt peker dit).

**Dette gjør `05_ORCHESTRATOR/`-kopiene til død kode.** En agent eller utvikler kan
redigere dem, se korrekt diff, committe — og oppnå null runtime-effekt.

> Dette er samme feilklasse som ASTRID dokumenterte 2026-09-08:
> *"eksekutorens realdata-gren var død kode"* — 87/87 kjøringer syntetiske fordi
> den redigerte kodestien ikke var den eksekverte.

---

### D3 — Divergerende kopi bærer kjent sikkerhetsdefekt

```bash
grep -n "PGPASSWORD" 05_ORCHESTRATOR/epistemic_proposal_daemon.py
# 61:            password=os.getenv('PGPASSWORD', 'postgres')

grep -n "PGPASSWORD" 03_FUNCTIONS/epistemic_proposal_daemon.py
# 56:        password = os.getenv('PGPASSWORD')      ← patchet i dag
```

GitGuardian flagget nøyaktig dette mønsteret på PR #20 (incident 23618378).
Fiksen ble lagt i `03_FUNCTIONS/`. **Skyggekopien i `05_ORCHESTRATOR/` er urørt.**

Dette er et konkret, aktivt bevis på at D2 ikke er teoretisk.

---

### D4 — Kontrollplanet selv er ikke produksjonsklart

```bash
grep -n "PGPASSWORD\|os.chdir" 03_FUNCTIONS/daemon_manager.py
# 19:os.chdir('C:/fhq-market-system/vision-ios')
# 26:    'password': os.getenv('PGPASSWORD', 'postgres')
```

| Defekt | Konsekvens |
|---|---|
| Hardkodet `os.chdir` til Windows-sti | Kontrollplanet kan kun kjøre på én maskin |
| Hardkodet passord-fallback | Samme klasse som GitGuardian-funnet |

Et kontrollplan som er bundet til én maskin er et *single point of failure* for
hele den autonome driften.

---

### D5 — Drift mellom versjonskontroll og runtime

```bash
git log -1 --format="%ci" origin/master     # 2026-03-09
date -u +%Y-%m-%d                            # 2026-09-08
ls 12_DAILY_REPORTS | grep -oE "DAY[0-9]+_RUNBOOK_[0-9]{8}" | sort -t_ -k3 | tail -1
# DAY49_RUNBOOK_20260218
```

| Referanse | Dato | Gap til i dag |
|---|---|---|
| `origin/master` HEAD | 2026-03-09 | **~6 måneder** |
| Nyeste runbook i repo | 2026-02-18 | ~7 måneder |
| Nyeste migrasjon i repo | `364_...` (2026-02) | ~7 måneder |

**Dette er rotårsaken til problemstillingen du selv beskrev** ("månedsvis med
utvikling som jeg vil gjennomgå"). Runtime-sannheten har løpt fra
versjonskontrollen. Enhver plan bygget kun på repo-innhold er per definisjon
minst 6 måneder utdatert.

---

## 3. DISPATCH-FENCE — AKTIV EKSEKUTIV KJEDE

ASTRID rapporterte 2026-09-08 kl. 19:27Z:

> Fabrikken re-pauset 19:10Z. Ny feilklasse (tick 1161–1163 ERROR) eies av den
> aktive eksekutive kjeden **RUN-20260908T190000Z (IN_PROGRESS)**.

ASTRID persisterte samtidig denne læringsregelen etter to kollisjoner samme dag:

> *"dispatch-fence — ingen manuell implementeringsutsendelse mens eksekutiv
> syklus eier samme mål."*

**Bindende for denne planen:** Ingen tiltak som berører forskningsfabrikkens
loop-sti iverksettes før RUN-20260908T190000Z har lukket sin adjudikering.
Fase 1 nedenfor er valgt nettopp fordi den ikke berører den stien.

---

## 4. IMPLEMENTERINGSPLAN

### Fase 0 — Sannhetsavstemming `[GATED: krever DB]`

Kan ikke utføres fra nåværende miljø. Må kjøres der DB er tilgjengelig.

```sql
-- Hva kjører faktisk?
SELECT daemon_name, status, last_heartbeat,
       NOW() - last_heartbeat AS staleness
FROM fhq_monitoring.daemon_health
ORDER BY last_heartbeat DESC;

-- Hvilke sykluser fullfører?
SELECT cycle_type, COUNT(*), MAX(ended_at)
FROM fhq_governance.orchestrator_cycles
WHERE started_at > NOW() - INTERVAL '7 days'
GROUP BY cycle_type;

-- Klokkeverifisering for runbook
SELECT NOW() AT TIME ZONE 'Europe/Oslo' AS oslo_time;
```

**Leveranse:** Autoritativ trippel-avstemming —
*kjørende* (`daemon_health`) vs *potensielle* (106 filer) vs *forvaltede* (5).

Uten denne er ethvert tall om autonom drift en antagelse. **Fase 2–4 er
blokkert til Fase 0 er levert.**

---

### Fase 1 — Eliminer skyggekode `[KAN STARTE NÅ]`

Krever ikke DB. Berører ikke forskningsfabrikkens loop-sti (dispatch-fence OK).

| Steg | Handling | Verifikasjon |
|---|---|---|
| 1.1 | Bekreft null påkallingsstier til `05_ORCHESTRATOR/`-duplikater | `grep -rn "05_ORCHESTRATOR/<fil>"` i cron/config/scripts |
| 1.2 | Port de 3 divergerende delta-ene som er reelle forbedringer til `03_FUNCTIONS/` | Diff-gjennomgang per fil |
| 1.3 | Karanteneflytt de 33 duplikatene (ikke slett — ADR-011 sporbarhet) | `git mv` til `ARCHIVE/` med kvittering |
| 1.4 | Én kanonisk lokasjon per daemon | Ny duplikat-telling = 0 |

**Umiddelbar sikkerhetsgevinst:** D3 lukkes — skyggekopien med hardkodet
credential forsvinner fra eksekverbar sti.

**Merk:** Steg 1.2 krever avklaring per fil — divergensen kan være *nyere* arbeid
i `05_ORCHESTRATOR/` som aldri ble portet tilbake. Må ikke kastes blindt.

---

### Fase 2 — Fullfør kontrollplanet `[GATED: krever Fase 0]`

| Steg | Handling |
|---|---|
| 2.1 | Registrer alle Fase 0-bekreftede levende daemoner i `CRITICAL_DAEMONS` |
| 2.2 | Koble dem til eksisterende fail-closed heartbeat (migrasjon `346`) |
| 2.3 | Definer eskalering per daemon: hva skjer ved `UNHEALTHY`? |

Infrastrukturen finnes allerede — `fhq_monitoring.daemon_health` med
`valid_daemon_status CHECK (HEALTHY/DEGRADED/UNHEALTHY/STOPPED)` og
`fhq_ops` Control Room (migrasjon `332`). **Dette er tilkobling, ikke nybygg.**

---

### Fase 3 — Portabilitet og credential-hygiene `[KAN STARTE NÅ]`

| Steg | Handling |
|---|---|
| 3.1 | Erstatt `os.chdir('C:/...')` med repo-rot-oppdagelse | 3 filer berørt |
| 3.2 | Fjern alle `os.getenv('PGPASSWORD', 'postgres')`-fallbacks → fail-closed | Samme mønster som PR #20-fiksen |
| 3.3 | Sentraliser DB-tilkobling i én modul | Fjerner N spredte connect-implementasjoner |

---

### Fase 4 — Loop-kadanse `[GATED: krever LARS-retning]`

Konsolidering av N ad-hoc schedulere til én kadanse-autoritet.

**Dette er ikke STIG-mandat alene.** Hvilke loops som skal kjøre autonomt, med
hvilken frekvens, og hvilken risikoeksponering som aksepteres, er
strategiske beslutninger. STIG leverer teknisk løsning på LARS' retning.

Underlag STIG kan levere når Fase 0 er klar: faktisk kadanse per loop,
ressursforbruk, og kollisjonsanalyse.

---

## 5. ANBEFALT REKKEFØLGE

```
NÅ (ingen blokkering):
  Fase 1  →  Eliminer skyggekode        [lukker D2, D3]
  Fase 3  →  Portabilitet + credentials [lukker D4]

NÅR DB TILGJENGELIG:
  Fase 0  →  Sannhetsavstemming         [låser opp alt nedenfor]
  Fase 2  →  Kontrollplan-dekning       [lukker D1]

NÅR LARS HAR GITT RETNING:
  Fase 4  →  Kadanse-konsolidering
```

**D5 (repo/runtime-drift) løses ikke av noen fase** — den krever at 6 måneders
lokal utvikling pushes til versjonskontroll. Det er en forutsetning for at
planen i det hele tatt opererer på riktig kodebase.

---

## 6. ÅPNE PUNKTER SOM KREVER AVKLARING

| # | Spørsmål | Blokkerer |
|---|---|---|
| 1 | Skal DB nås via lokal økt eller tunnel? | Fase 0, 2 |
| 2 | Er de 3 divergerende kopiene nyere arbeid som skal beholdes? | Fase 1.2 |
| 3 | Er `05_ORCHESTRATOR/` ment som deploy-mål eller historisk artefakt? | Fase 1.3 |
| 4 | Når lukker RUN-20260908T190000Z? | Alt som berører fabrikk-loopen |
| 5 | Skal 6 mnd lokal utvikling pushes før planen effektueres? | D5, planens gyldighet |

---

## 7. HVA DENNE PLANEN IKKE ER

- **Ikke en verifisert tilstandsrapport.** DB var utilgjengelig. Alle
  DB-avhengige påstander er merket `[GATED]`, ikke gjettet.
- **Ikke en strategisk plan.** Retning eies av LARS (CLAUDE.md § Forbud).
- **Ikke G4-godkjent.** Ingen tiltak iverksettes uten godkjenning.
- **Ikke basert på gjeldende runtime.** Repoet er ~6 måneder bak (D5).

---

**Kvitteringer:** Alle kommandoer i seksjon 2 er reproduserbare mot
commit `f9f148ef` (origin/master HEAD, 2026-03-09) merget inn i
`claude/explain-learning-loop-Sa9z7`.

---

## 8. FASE 1 — UTFØRT 2026-09-08

**Lukker:** D2 (skyggekode) og D3 (skyggekopi med credential-defekt).
**Runtime-adferd endret:** ingen. **Reversibilitet:** ett `git revert`.

### 8.1 Steg 1.1 — Påkallingsstier: NULL funnet

Fem uavhengige søk, to av dem med ulik metode (sekvensiell og alternasjon) som ga identisk svar:

| Søk | Metode | Resultat |
|---|---|---|
| Importer fra de 7 unike 05-beboerne | `grep -E "^(from\|import) <dup>"` | 0 treff |
| `sys.path`-innsettinger mot 05 | 3 filer i 03_FUNCTIONS | Når kun `vendor_guard`, `defcon_router`, `ios014_orchestrator` — unike beboere, ikke duplikater |
| Prefiksede referanser `05_ORCHESTRATOR/<dup>` | alternasjon + sekvensiell | Kun dette dokumentet |
| Launchere (130 stk .bat/.ps1/.cmd/.sh) | bare navn + `cd`/`WorkingDirectory` | Alle løser til `03_FUNCTIONS`; de to som rører 05 kaller `orchestrator_v1.py` (unik) |
| Fabrikksti / `sandbox_runner` | grep | Ukoblet — dispatch-fence respektert |

**Restrisiko:** Windows Task Scheduler på runtime-maskinen er uobserverbar herfra.
Mitigert i 1.3 ved at enhver sti inn i 05 fortsatt fungerer.

### 8.2 Steg 1.2 — Divergens: ingenting å porte

Alle tre 05-kopier stammer fra **én commit** `a21a837b` (2026-02-01). Hver diff går utelukkende 05→03:

| Fil | 03 er nyere med | Kilde |
|---|---|---|
| `finn_brain_scheduler.py` | heartbeat til `daemon_health` + `daemon_lock` | migrasjon 346 fail-closed |
| `ios010_forecast_reconciliation_daemon.py` | regime-spesifikk confidence-damper | CEO-DIR-2026-063R |
| `epistemic_proposal_daemon.py` | credential fail-closed | GitGuardian 23618378, i dag |

`03_FUNCTIONS` er strengt superset i alle tre. 05-kopien av `finn_brain_scheduler`
(én av de 5 kontrollplan-forvaltede) manglet både heartbeat og lås — hadde den kjørt,
ville den vært usynlig for fail-closed-håndhevingen og uten dobbeltkjøringsvern.

### 8.3 Steg 1.3 — Konsolidering: forwarding-shim, ikke flytting

**Avvik fra § 4 Fase 1.3** (`git mv` → `ARCHIVE/`). Begrunnelse:

1. Task Scheduler uobserverbar → flytting risikerer stille daemon-død på produksjon (forbudt: *Ingen Silent Failures*).
2. Git er allerede arkivet (`a21a837b`). En `ARCHIVE/`-katalog ville vært en **tredje** kopi.
3. Shim uten logikk **kan ikke divergere** — D2 lukkes strukturelt, ikke bare for øyeblikket.

Shim-garantier (alle bevist i 8.4): `__file__`, `argv[0]` og `sys.path[0]` settes til kanonisk
katalog slik at eksekvering er identisk med direkte kall; fail-closed hvis kanonisk fil mangler;
`ImportError` ved import (fail-loud, aldri stille).

### 8.4 Steg 1.4 — Verifikasjon

| # | Test | Resultat |
|---|---|---|
| V1 | `py_compile` × 33 | 0 feil |
| V2 | Kanoniske søsken `daemon_lock.py`, `forecast_confidence_damper.py` i 03 | begge til stede |
| V3 | 05-kopier med `def`/`class` | **0** (33 forwarder via `runpy`) |
| V3 | 03-kanoniske filer endret | **0** |
| V4 | `import finn_brain_scheduler` fra 05 | `ImportError` som peker på 03 |
| V5a | Reelt traceback via shim | frame `03_FUNCTIONS/finn_brain_scheduler.py:18` — kontroll gikk inn i kanonisk fil |
| V5b | Miljøuavhengig probe via shim | `FILE/ARGV0/PATH0 = 03_FUNCTIONS`, `SIBLING = 03_FUNCTIONS/daemon_lock.py`, `NAME = __main__`, arg passert, `rc=0`, 0 restfiler |
| V6 | Alle 33 shims modulo filnavn | én hash: `50ba91276a344d25` = template |

**Netto:** 33 filer, +916 / −22 288 linjer. Duplisert implementasjon i eksekverbar sti: **0**.

### 8.5 Oppdatert status på funn

| Funn | Status |
|---|---|
| D1 | Åpen — krever Fase 0 (DB) |
| **D2** | **LUKKET** — 33 skyggekopier er nå logikkfrie shims |
| **D3** | **LUKKET** — ingen kopi bærer lenger `PGPASSWORD`-fallback |
| D4 | **LUKKET** — kontrollplan (3 filer, § 9) + 369 filer (§ 10). Gjenstår: 3 fencede fabrikkfiler (avventer `RUN-20260908T190000Z`) og 4 pre-eksisterende ødelagte filer (§ 10.5) |
| **D6** | **NY, oppdaget under § 10** — `guard_generation_freeze.py` har pre-eksisterende syntaksfeil ved HEAD → `finn_crypto/e/t_scheduler` kan ikke importere på noen vert. `finn_crypto_scheduler` er kontrollplan-forvaltet. Ikke berørt av denne endringen; krever egen fiks |
| D5 | Åpen — krever push av lokal utvikling |

---

## 9. FASE 3 — UTFØRT 2026-09-08 (godkjent omfang)

**Lukker:** D4 for kontrollplanet. **Runtime-adferd endret:** ja — bevisst, fail-closed (se 9.3).
**Reversibilitet:** ett `git revert`.

### 9.1 Omfangsmåling før redigering (steg 3.0)

Planens § 4 Fase 3.2 sier «fjern **alle** fallbacks». Godkjenningen ble gitt på beskrivelsen
«`daemon_manager.py` + 3 filer». Målingen viste at de to ikke er samme ting:

| Kategori | Kommando | Funn |
|---|---|---|
| `PGPASSWORD`-fallback til literal | `grep -rnE "os\.(getenv\|environ\.get)\(['\"]PGPASSWORD['\"],\s*['\"]"` | **324 forekomster / 323 filer** (283 i `03_FUNCTIONS`) |
| Bart `password='postgres'` uten env | `grep -rnE "password['\"]?\s*[:=]\s*['\"]postgres['\"]"` | 52 filer |
| Innebygd credential i connection-string | `grep -rnE "postgres(ql)?://[^:@]+:[^@]+@"` | 2 filer |
| `os.chdir` til Windows-rot | `grep -rnE "os\.chdir\(['\"][A-Za-z]:"` | 3 filer |
| Av disse på **fabrikkstien** | — | `hypothesis_death_daemon`, `hypothesis_experiment_bridge_daemon`, `scripts/research_daemon` |

**Beslutning:** Utfør nøyaktig det godkjente omfanget — de 3 `os.chdir`-filene, som utgjør
kontrollplanet (`daemon_manager`, `daemon_watchdog`) pluss `pre_tier_scoring_daemon`.
Alle tre er utenfor fabrikkstien (dispatch-fence respektert). De ~375 øvrige filene er
en egen beslutning (§ 9.5) — ikke fordi risikomodellen er annerledes, men fordi
review- og revert-omfanget er 100× større enn det som ble godkjent.

### 9.2 Endring (steg 3.1 + 3.2), identisk i alle tre filer

| Før | Etter |
|---|---|
| `os.chdir('C:/fhq-market-system/vision-ios')` | `os.chdir(Path(__file__).resolve().parent.parent)` |
| `'password': os.getenv('PGPASSWORD', 'postgres')` | `_pgpassword = os.getenv('PGPASSWORD')` → `RuntimeError` hvis usatt → `'password': _pgpassword` |

`03_FUNCTIONS/<fil>.py` → `parent.parent` er repo-roten. På produksjonsverten løser det til
nøyaktig `C:\fhq-market-system\vision-ios` — byte-identisk utfall. På enhver annen checkout
virker det i stedet for å kaste `FileNotFoundError`. Netto: 3 filer, +39 / −9 linjer.

### 9.3 Konsekvens på produksjonsverten — må leses før merge

Etter denne endringen **nekter de tre daemonene å starte hvis `PGPASSWORD` ikke er satt i
miljøet de kjører i** (Task Scheduler-kontekst, ikke bare interaktiv shell). Det er riktig
adferd — stille bruk av standardpassord er forbudt — men det er en endring jeg ikke kan
observere effekten av herfra. Dette er samme feilklasse som ASTRID avdekket 2026-09-08
(`FHQ_RESEARCH_RUNNER_PASSWORD` kun i env, aldri sourced i cron → alle ticks krasjet).

**Sjekk før merge på verten:** at `PGPASSWORD` er satt i den konteksten Task Scheduler
starter `daemon_watchdog` fra. Feiler den, feiler den *høyt* med tydelig melding — ikke stille.

### 9.4 Verifikasjon (steg 3.3)

`psycopg2` finnes ikke i eksekveringsmiljøet og importeres øverst i alle tre filer — en naiv
kjøring ville dødd der og gitt et falskt negativt. Beviset er derfor miljøuavhengig:
`psycopg2` stubbet i `sys.modules`, kildekoden eksekvert *kun frem til `DB_CONFIG` lukkes*
(imports → chdir → logging → fail-closed → dict), startet fra bevisst feil cwd (`/tmp`).

| # | Test | Resultat |
|---|---|---|
| V1 | `py_compile` × 3 | 0 feil |
| V2 | Gjenværende fallback / hardkodet chdir i omfang | 0 / 0; `pathlib` importert i alle 3 |
| V3a | `PGPASSWORD` **usatt** | `RuntimeError` med `PGPASSWORD` i meldingen, alle 3; `cwd == repo-rot` |
| V3b | `PGPASSWORD` **satt** til sentinel | modulen passerer, `DB_CONFIG['password'] == sentinel`, `cwd == repo-rot`, alle 3 |
| V4 | Restfiler etter probe | 0 |

### 9.5 Åpen beslutning — masseendringen

| Sett | Filer | Merknad |
|---|---|---|
| `PGPASSWORD`-fallback | ~320 | Samme 6-linjers mønster; mekanisk, men 100× review-omfang |
| Bart literal uten env | 52 | Verre enn fallback — ingen overstyring mulig i dag |
| Innebygd i connection-string | 2 | |
| **Herav på fabrikkstien** | 3 | **Må vente** på at `RUN-20260908T190000Z` lukker |

Risikoen er binær på miljøvariabelen, ikke lineær i filantall: er `PGPASSWORD` satt,
stopper ingen; er den ikke satt, stopper alle fail-closed-daemoner. Det som skalerer med
filantall er review-byrden og revert-omfanget. Anbefaling: gjør masseendringen som egen
commit, *etter* at 9.3-sjekken er bekreftet på verten, og *utenom* de 3 fabrikkfilene til
kjeden har lukket.

---

## 10. FASE 3b — MASSEENDRING UTFØRT 2026-09-08 (ordre: «1 og 2 ja … vi kjør!»)

**Lukker:** D4 fullt ut, med to eksplisitte unntak (§ 10.5). **Runtime-adferd endret:** ja —
fail-closed i 369 filer. **Reversibilitet:** ett `git revert`.
**MERGE-GATE (bindende):** ikke merge før `PGPASSWORD` er bekreftet satt i den konteksten Task
Scheduler starter daemonene fra. Gaten ligger ved *merge*, som CEO kontrollerer — ikke ved commit.

### 10.1 Omfang — eksakt regnskap

| | Filer |
|---|---|
| Kategori A (`PGPASSWORD`-fallback, enhver literal) | 320 + 4 tom-default `''` som begge tidligere grep overså |
| − fencet (fabrikksti, `RUN-20260908T190000Z` åpen) | −3 |
| − pre-eksisterende syntaksfeil ved HEAD (urørt, § 10.5) | −4 |
| Kategori B (bart `password='postgres'`, ingen env) | +52 |
| **Berørt** | **369** |

Per katalog: `03_FUNCTIONS` 318 · `scripts` 39 · `05_ORCHESTRATOR` 7 (de unike beboerne; shims
fra § 8 er logikkfrie og matchet ikke) · `migrations` 2 · `04_AGENTS`/`06_AGENTS`/`08_BACKFILL` 1 hver.
Kategori C (23 «connection-strings») ble reklassifisert som *avledet*: f-strenger fra allerede
oppslåtte variabler — kilden er en A-forekomst linjer over. Ingen selvstendig handling; verifisert
for 8 av 8 undersøkte.

### 10.2 Metode — og det første forsøket som feilet

Ingen blind regex. Klassifisering først (§ 3b.0): A er *strukturert*, ikke uniform — 221 `DB_CONFIG`-dict,
62 `connect()`-kwarg, 12 in-def, 10 modultopp, 7 klasseattributt, 9 øvrige. Én ankerbasert transform:
guard-blokk foran statementets hode med hodets innrykk, uttrykk byttet til `_pgpassword`; bare
tilordninger beholder eget navn. Samme kodesti for dry-run og apply. Ingen delt modul — null nye
import-kanter (03/05-farens fra § 8).

**Forsøk 1 feilet og ble revertert.** Dry-run rapporterte 0 anomalier; apply ga **88 `SyntaxError`**.
Diagnose fra diff: siste kwarg uten etterfølgende komma — `password=os.getenv(…)` rett før `)` — er
*tekstlig identisk* med en tilordning, så `ASSIGN` skrev seks linjer inn i den åpne parentesen.
Linjenivå kan ikke skille kwarg fra statement. 4 av de 88 var pre-eksisterende ved HEAD; 84 var mine.
**v2:** parentesdybde eksakt via `tokenize` (dybde > 0 → aldri eget anker; gå til siste dybde-0-rad),
og **compile-gate per fil inne i apply** — en kilde som ikke kompilerer skrives aldri. Dry-run v2:
369 filer, 0 anomalier, 0 blokkert. Apply v2: 0/369 kompileringsfeil.

Transform-statistikk: `dict/kwarg` 330 · `assign` 31 · `oneliner` 9 · `import os` lagt til 34.
Netto: **369 filer, +2 932 / −370 linjer.**

### 10.3 Konsekvens på produksjonsverten

Identisk med § 9.3, nå for 369 daemoner og skript: **starter ikke uten `PGPASSWORD` i miljøet de
kjører i** — Task Scheduler-kontekst, ikke interaktiv shell. Høyt, med tydelig melding, aldri stille.
Risikoen er binær på variabelen (§ 9.5), så denne endringen er ikke *farligere* enn § 9 — bare 123×
større å reviewe og reverte. Set-grenen er strukturelt garantert: `if not X: raise` er falsk når X er
satt, og `password=_pgpassword` er identisk med det gamle uttrykkets verdi.

### 10.4 Verifikasjon

| # | Test | Resultat |
|---|---|---|
| V1 | Ekstern `py_compile` × 369 (i tillegg til intern compile-gate) | **0 feil** |
| V2 | Gjenværende fallback repo-vidt, utvidet mønster (enhver literal), utenfor fence/pre | **A = 0, B = 0**; fence beholder 3 |
| V4 | Tre-invarianter | modified = 369 = berørt; untracked = 0; § 9-filene urørt; fencede urørt |

**V3 — miljøuavhengig guard-probe, alle 369** (`pw_verify.py` v3.3, artefakt `/tmp/pw_verify_final.txt`):
kildekoden eksekvert *frem til guarden*, fra repo-rot, begge env-grener. Kun filens *direkte* imports
stubbes (transitive stdlib-feature-prober får ekte `ImportError`). En `RuntimeError` teller som
fail-closed-bevis bare når innerste ramme er den probede filen selv — eller når opphavet er en annen
berørt fil med guard (sjekket *i scriptet*, ikke i prosa). Søskenmoduler renses mellom filer. Filer
probet kode skaper i treet fjernes og rapporteres (6 tomme `.log`, alle fra `logging.FileHandler`).

| Tier | Filer | Betydning |
|---|---|---|
| Exec-bevist, **begge grener** | **241** | usatt → `RuntimeError` fra egen guard; satt → passerer |
| Exec-bevist **fail-closed, transitivt** | 16 | søskenets guard fyrte først; egen guard til stede, `set→ok` |
| Exec-bevist fail-closed, env etter guard | 1 | usatt → `RuntimeError`; satt → pre-eksisterende Windows-sti |
| Strukturelt (compile + guard-plassering) | 111 | guard i `def` som ikke kalles ved import (93), env-feil før guard (8), uutført scope (8), trunkering (2) |
| **UNEXPLAINED** | **0** | |
| Sum | 369 | |

**Probens egen historikk, for ærlighetens skyld:** v2.2 brukte en grådig catch-all import-hook som
ga stub til Jython-only `org.python.core` (som CPythons `copy` *forventer* skal feile) → 95 falske
env-feil. v3 stubber kun direkte imports. Proben ble iterert fem ganger; transformen én gang etter revert.

### 10.5 Det som bevisst er urørt

| Fil | Grunn |
|---|---|
| `03_FUNCTIONS/hypothesis_death_daemon.py`, `hypothesis_experiment_bridge_daemon.py`, `scripts/research_daemon.py` | Fabrikkstien — dispatch-fence til `RUN-20260908T190000Z` lukker |
| `03_FUNCTIONS/dir_010_create_stig.py`, `dir_010_create_stig_user.py`, `dir_010_create_stig_user_clean.py`, `e2e_smoke_test.py` | Kompilerte ikke ved HEAD; transformen hopper over ødelagte filer eksplisitt fremfor å endre noe den ikke kan verifisere |

### 10.6 Oppdaget under arbeidet — D6

`03_FUNCTIONS/guard_generation_freeze.py` har en pre-eksisterende syntaksfeil (`""", (`) ved HEAD.
Den importeres av `finn_crypto_scheduler`, `finn_e_scheduler` og `finn_t_scheduler` — **ingen av dem
kan importere på noen vert i dag**, uavhengig av denne endringen. `finn_crypto_scheduler` er én av de
5 daemonene `daemon_manager.py` forvalter. Funnet er utenfor dette omfanget og krever egen fiks;
det er nøyaktig feilklassen ASTRID beskrev: kode som ser riktig ut i repoet men ikke kjører.

---

## 11. FASE 0 — FØRSTE EVIDENS FRA RUNTIME-SIDEN (Agent Zero, 2026-09-09)

**Kilde:** Agent Zero-rapport relayet av CEO. **Ikke verifisert av STIG** — STIG når verken vert
eller container. Gjengitt som mottatt; a0s bevisfil `tmp/phase0_blocked_evidence_20260909.txt`
(79 linjer) ligger i a0s container.

### 11.1 Hva a0 utførte

| Steg | Resultat |
|---|---|
| `code_execution_remote` (F4, host-CLI) | **NED** — «no CLI client connected to Agent Zero», 3 forsøk, identisk feil |
| DB fra container | **OK** — `host.docker.internal:54322`, `select 1 → 1`. `127.0.0.1:54322` → connection refused (eget docker-nett) |
| Container-crontab | 57 linjer. `grep -nE 'PGPASSWORD=\|source .*env\|\. .*env'` → **tom** (exit 1) |
| `scripts/phase0_verify.sql` | **Ikke tilgjengelig i noen visning** a0 når. GitHub-operasjoner fra container forbudt etter prosjektregler → ikke forsøkt |
| Steg 1, 2, 3a, 3b, 3c fra briefen | **Ikke utført** — alle krever F4 eller filen |

### 11.2 Topologi a0 avdekket — endrer D5

| Montering | Funn |
|---|---|
| `C:→/host/fhq-src` (9p, lesebeskyttet) | Ingen `.git`, ingen `scripts/`, ingen `03_FUNCTIONS/guard_generation_freeze.py`. **Kuratert/stale visning, ikke C:-roten** |
| `D:→/host/runtime` (9p, lesebeskyttet) | **Repo `MetaStark/runtime`, HEAD `3ff28a0`, 2026-05-15.** Ingen `claude/explain-learning-loop-Sa9z7`; `fd0328b6` → «Not a valid object name»; ingen `phase0_verify.sql`, ingen `guard_generation_freeze.py` |

**D7 — Et tredje kodetre.** `MetaStark/runtime` er hverken `vision-IoS` eller `fhq-market-system`.
STIG har aldri sett det. **Spørsmål reist til CEO: hva er `MetaStark/runtime`?** Planens Lag 0,
steg 0.2 («repo = runtime») må omfatte dette repoet.

**D7 presisert (verifisert i vision-IoS, 2026-09-09).** `04_DATABASE/CANONICAL_RUNTIME_DATA_MAP.md`
(2026-03-09) erklærer ti tabeller som «runtime truth». Kryssjekk mot dette repoet:

| Kartets tabell | DDL i vision-IoS |
|---|---|
| `fhq_market.prices` | mig 023 |
| `fhq_perception.regime_daily` | mig 025 |
| `fhq_perception.sovereign_regime_state_v4` | mig 120 |
| `fhq_learning.micro_regime_classifications` | mig 353 |
| `fhq_execution.shadow_trades` | mig 099 |
| `fhq_learning.hypothesis_canon` | mig 335 |
| `fhq_core.market_prices_live` | **ingen — skjemaet `fhq_core` finnes ikke her** |
| `fhq_learning.outcomes` | **ingen** |
| `fhq_learning.calibration` | **ingen** |
| `fhq_alpha.alpha_signals` | **ingen** |

Alle fem writer-script kartet navngir ligger i `03_FUNCTIONS/`. **Konklusjon:** kartet beskriver
*dette* repoets runtime — bekymringen «feil tre» er avkreftet for runtime-laget. Men fire
runtime-sannhet-tabeller har ingen DDL her mens koden som skriver til dem har det. DDL-en bor i
foundation-repoet (`fhq_*` er foundation-eid, ADR-013), i `MetaStark/runtime`, eller opprettes
ad hoc. § 11 i `phase0_verify.sql` avgjør det fra DB-en.

**Viktigere for planen:** kartets sett og Fase 0-scriptets opprinnelige sett er **disjunkte**.
To direkte overlapp: `fhq_canonical.canonical_outcomes` vs `fhq_learning.outcomes`, og
`fhq_governance.calibration_versions` vs `fhq_learning.calibration`. § 2 (M3/M4) og AELL-2026-001
pekte på de første; kartet erklærer de andre som runtime-sannhet. STIG velger ikke side —
scriptets § 11b/11c måler begge, og DB-en sier hvilket som lever.

**D8 — a0s visning av C: er ikke arbeidstreet.** `/host/fhq-src` mangler `.git`. a0 kan ikke
verifisere noe om runtime-koden fra den monteringen.

### 11.3 Merge-gate — flaten vokste

Container-crontab (57 linjer) er en planlagt eksekveringskontekst uten `PGPASSWORD=` og uten
env-sourcing i crontab-teksten. Trolig fabrikkens tick-driver (ASTRID: «crontab linje 42»).

Dette **beviser ikke** at jobbene mangler credential: LINEs fail-closed-loader kan ligge *inne i*
driveren. Det beviser at sjekken må gjøres på **jobbnivå**, i minst tre kontekster:

1. Windows Task Scheduler (`[Environment]::GetEnvironmentVariable('PGPASSWORD','Machine'/'User')`)
2. Container-crontab — per jobb: laster driveren `PGPASSWORD` selv?
3. Windows-crontab/WSL, om den finnes

Merge av `fd0328b6` forblir gatet til alle tre er bekreftet.

### 11.4 Unblokk-stier for Fase 0 — ingen krever F4 for SQL-delen

| Sti | Handling | Merknad |
|---|---|---|
| **A** | CEO kopierer `scripts/phase0_verify.sql` fra GitHub inn i a0s container; a0 kjører `psql -h host.docker.internal -p 54322 -U postgres -d postgres -f phase0_verify.sql > phase0_result.txt 2>&1` | Scriptet er uendret; kun `-h` skiller seg fra briefen. a0 leser scriptet først (kun `SELECT`, ingen DDL) |
| **B** | CEO kjører a0s fire kommandoer direkte på Windows-verten | Raskest. F4 nede blokkerer a0, ikke CEO |
| — | Steg 3a/3b/3c (PowerShell-env, `py_compile`, git-drift) | Krever verten — sti B, eller F4 gjenopprettet |

STIG kan ikke gjenopprette A0 CLI — ingen kanal til vert eller container.

### 11.5 Andre a0-rapport (15:05 Oslo) — rotårsak, korrigert leveringsvei, D6 på verten

**Kilde:** Agent Zero, relayet av CEO. Rå bevisfiler i a0s container:
`tmp/phase0_delivery_status_20260909_1505.txt` (61 linjer), `tmp/phase0_blocked_evidence_20260909.txt` (79 linjer).

**Rotårsak til at scriptet aldri nådde a0 — eksportomfang, ikke levering:**

| Montering | Faktisk innhold |
|---|---|
| `/host/fhq-src` | **Kun subtreet `C:\fhq-market-system\vision-ios\03_FUNCTIONS`.** `scripts/`, `.git`, `04_DATABASE/`, `05_ORCHESTRATOR/` — alt annet er strukturelt usynlig for a0, uansett branch |
| `/a0/usr` | Docker-volum (ext4), **ikke** et Windows-mount. Tidligere anvist sti `C:\fhq-agent-zero\usr\…` var feil |
| `/host/runtime` = `D:\Runtime` | Fullt synlig, lesbar. **Korrigert leveringsvei:** legg filen på `D:\Runtime\phase0_verify.sql` |

Repo-veien er død for a0. Filen er levert som vedlegg (`file_uuid 39ea7514…`, identisk med `3e38093b`,
sha256 `de48b93e…c140b`, 314 linjer, 23 `SELECT`). Fingeravtrykk-kontrakten er logget hos a0 og
verifiseres ved mottak før kjøring.

**D6 — lukket på verten, åpen i repoet, og de to filene er ikke samme fil:**

| | Repo (`master@2026-03-09`, sist rørt `cc0f46be` 2026-02-12) | Vert (a0, `/host/fhq-src/guard_generation_freeze.py`) |
|---|---|---|
| Størrelse | 5 866 B | **4 056 B** |
| sha256 | `cd02695f…5815d69` | `436aff81…aa271e40` |
| mtime | — | **2026-05-01** |
| `py_compile` | **NEI** — `""", (` på linje 122 og 140 | **OK** (to venv-er) |

Vert-filen er datert etter siste push til GitHub, kompilerer, og er **1 810 B mindre** — ~30 % av
filen er borte. Det er ikke en syntaksfiks. Filen er guarden for CEO-DIR-2026-015 (72-timers
generasjonsfrys). **Konklusjon:** D6 er et D5-symptom (drift), ikke en repo-feil å patche — men
løsningen er *ikke* å hente vertens versjon inn som sannhet. Den er å **diffe de to og
adjudikere hos VEGA**: har guarden mistet logikk, eller ble død kode fjernet? Forslagskortet
«fiks D6 i repoet» er trukket; å patche den ødelagte kopien ville gitt en tredje variant.
Neste steg: a0 returnerer vert-filen ordrett; STIG differ og skriver adjudikeringsbrief.

**Fortsatt blokkert på verten (krever F4 eller CEO direkte):** 3a — `PGPASSWORD` i Task
Scheduler-kontekst (`Machine`/`User`); 3c — git-datoer i vision-ios (`.git` utenfor eksport).

---

## 12. FASE 0 — RESULTAT  (DB-klokke 2026-09-09 15:19:19 Oslo)

**Proveniens:** Agent Zero kjørte `phase0_verify.sql` (fingeravtrykk verifisert før kjøring:
`de48b93e…c140b` / 314 / 23), `psql -h host.docker.internal -p 54322` → exit 0.
Resultatfil `phase0_result.txt`: 35 505 B, 422 linjer, sha256
`7e4e34381462442c21b2ecd64de5b6bb9dbd9deaadb4463c716912bcbb5d9f2d`, fysisk i a0s container
`/a0/usr/projects/agent-zero_runtime_loop/tmp/phase0_result.txt`. Én `ERROR`-linje (§ 8, design:
`ON_ERROR_STOP off`). Relayet uendret av CEO. Rader under er gjengitt ordrett.

### 12.1 Dommen

**Systemet kjører ikke. Én prosess lever: prisstrømmen.** Alt nedstrøms har vært statisk i
2–7 måneder. Dette er første gang påstanden bygger på databasen, ikke på filer.

| # | Bevis (ordrett) | Betydning |
|---|---|---|
| 1 | `daemon_health`: 74 rader; `heartbeat_lt_1h` = **0** for alle statuser; `stale_gt_24h` = 74/74. Ferskeste: `efs_binance_gateway` 2026-08-23 (17 d); nest ferskeste `phase3_calibration_daemon` 2026-07-07 (64 d); resten 104–233 d | Ingen registrert daemon har slått på 17 dager. 47 sier `HEALTHY` med hjerteslag fra april–mai → statuskolonnen er meningsløs; fail-closed heartbeat (mig 346) håndhever ikke |
| 2 | `daemon_watchdog` \| `STOPPED` \| 2026-02-06 (215 d) | Vakthunden som skal restarte daemoner har vært av i 7 måneder |
| 3 | 2c: `economic_outcome_daemon` NOT IN daemon_health; `finn_brain_scheduler`, `finn_crypto_scheduler`, `g2c_continuous_forecast_engine`, `ios003b_intraday_regime_delta` alle `STOPPED` siden feb 2026 | Kontrollplanets fem kritiske daemoner: fire døde, én aldri registrert |
| 4 | `orchestrator_cycles` siste 7 d: **(0 rows)** | Ingen orkestrering på en uke |
| 5 | `governance_actions_log`: siste rad **2026-07-07 02:09** `PHASE3_DAILY_CALIBRATION`, daglig 06-22→07-07, så intet | 64 dagers stillhet i governance-loggen |
| 6 | `learning_proposals`: **(0 rows)**; avslagsrate: NULL | Governance-læringsløkken (mig 151) har aldri hatt ett forslag. F3 er ikke teater — den er fraværende |
| 7 | `forecast_skill_registry`: **(0 rows)** | IoS-005 FSS: aldri ett scorecard |
| 8 | `canonical_outcomes`: 4 rader, alle `2026-01-01 02:00:10`, 0 siste 30 d, 0 med konfidens | «Ground truth»-tabellen AELL-analysen hvilte på: fire seed-rader, ingenting siden |
| 9 | Proposal Engine: `proposal_runs` = 4, siste **2026-01-23**; `epistemic_proposals`: ingen rader | Kjørte fire ganger i januar, produserte null forslag, stoppet |
| 10 | 11b: **`fhq_core.market_prices_live`** n_live_tup 67 712 586, n_tup_ins 58 035, n_tup_upd 21 856 342, autoanalyze **2026-09-09 14:00** — *alle andre 15 målte tabeller*: 0 / 0 / 0 / NULL | Siden siste stats-reset er prisstrømmen den eneste tabellen som skrives |
| 11 | Prisstrøm skrives i dag; `efs_binance_gateway` hjerteslag 17 d gammelt | Levende prosess uten hjerteslag. `daemon_health` er upålitelig i *begge* retninger — D1 bevist |

### 12.2 Dokumenter som er feil mot databasen

| Dokument | Påstand | DB | Korreksjon |
|---|---|---|---|
| CLAUDE.md | «PostgreSQL 17.6 (Windows x64)», `127.0.0.1:54322` | `x86_64-pc-linux-gnu`, `inet_server_addr 172.17.0.2`, port 5432 | DB-en kjører i **Docker** (bridge-nett), eksponert som 54322 på verten. Krever G4 for å rette CLAUDE.md — foreslås |
| CLAUDE.md | Vision-IoS skriver til `vision_*`-skjemaer | 49 skjemaer, **null** `vision_*` | Skjemamodellen i CLAUDE.md finnes ikke |
| Runtime data map (2026-03-09) | 10 tabeller = «runtime truth» | **9 av 15 MISSING**, inkl. `fhq_market.prices` (kartets primærinput), alle fem `indicator_*`, `fhq_learning.outcomes`, `fhq_learning.calibration`, `fhq_alpha.alpha_signals` | Kartet er 60 % utdatert. `fhq_market` har 14 tabeller — ingen heter `prices` |
| AELL-2026-001 (STIG) | § 2.2 `knowledge_fragments` «✅ FULLY IMPLEMENTED» | `relation does not exist` | Feil. Mig 100 aldri anvendt, eller tabellen droppet. CEIO-feedback-triggeren kan ikke ha virket |
| AELL-2026-001 (STIG) | § 2.6 FSS «✅» | 0 rader | Skjema finnes, aldri brukt |
| AELL-2026-001 (STIG) | Gap 2 «ingen Brier» | `fhq_governance.brier_score_ledger` finnes (1c) | Feil retning: ledger finnes; om den brukes er neste spørsmål |
| 2027-plan § 2 M2 (STIG) | «ingen deflatert-Sharpe-port» | `hypothesis_canon` har `deflated_sharpe_estimate`, `pbo_probability`, `family_inflation_risk`, `time_to_falsification_hours`, `pre_tier_score_at_birth`, `falsification_criteria` | Lag 1 mangler ikke design — det mangler **drift**. Samme for kostmodellen: `shadow_trades` har `spread_bps`, `slippage_bps`, `fee_bps` |

Lag 0-tesen — «sannhet før intelligens» — var riktigere enn jeg visste. Men *hvilke* primitiver
som mangler var feil: de fleste finnes; nesten ingen brukes.

### 12.3 Det åpne spørsmålet — ASTRIDs fabrikk

ASTRID rapporterte 2026-09-08: DP1–DP4 implementert, tick 1150–1163, sandbox_runs 88–90, to
reelle eksperimenter, fabrikk pauset 19:10Z. **Ingenting av dette finnes i noen tabell Fase 0
spurte** — `governance_actions_log` stopper 07-07. Men fabrikktabellene er *oppdaget* og *ikke
spurt*: `fhq_control.sandbox_runs`, `fhq_control.research_objects`,
`fhq_control.research_object_lifecycle_events`, `fhq_control.trajectory_ledger`.

STIG konkluderer ikke. Én kolonne-agnostisk spørring avgjør:
`SELECT COUNT(*) FROM fhq_control.sandbox_runs WHERE t::text LIKE '%2026-09-08%'` og totalt
antall (ASTRID impliserer ≈ 90). Finnes radene → fabrikken er det andre levende delsystemet.
Finnes de ikke → ASTRIDs rapport beskriver en annen database, eller er selv den typen syntetisk
evidens den diagnostiserte. Begge utfall er alvorlige; bare ett er sant. `phase0_followup.sql`
§ A.

### 12.4 Merge-gaten, re-evaluert

Døde daemoner stopper ikke av en merge. Men **prisstrømmens writer** (`market_streamer_v2.py`
per kartet — i `03_FUNCTIONS`, transformert i `fd0328b6`) er det eneste som lever. Merges
`fd0328b6` uten `PGPASSWORD` i *dens* kontekst, dør det eneste levende. Gaten står, og
beskytter nå nøyaktig én ting. 3a forblir blokkert (F4). `pg_stat_activity` i oppfølgingen
viser hvem som er koblet til *nå* — det er den definitive liveness-målingen, uavhengig av
hjerteslag.

### 12.5 Anomali i § 5

`schedule_config` \| `value` viser `§§secret(FHQ_TELEGRAM_ONLY_HOURLY)`. Kolonnen er
`is_active::text` (boolean → `t`/`f`). En boolean kan ikke inneholde den strengen. Enten har
a0s relay-lag redigert et mønster, eller kolonnen er endret på verten. Ikke tolkbar; noteres.

### 12.6 D6 — adjudikering: verten fjernet en direktiv-mandatert unntaksvei

`guard_generation_freeze.py` mottatt ordrett fra a0 (4 056 B, `436aff81…`); fingeravtrykk
verifisert før diff (`d6_adjudicate.sh` nekter ellers). Diff repo (5 866 B, `cd02695f…`,
kompilerer ikke) → vert: **−58 / +21 linjer.** Funksjoner uendret i antall (2/2).

| Hva | Repo (`cc0f46be`, 2026-02-12) | Vert (mtime 2026-05-01) |
|---|---|---|
| Signatur | `guard_generation_freeze(conn, hypothesis_code, controlled_exception)` | `guard_generation_freeze(conn, hypothesis_code)` |
| Under aktiv frys | `controlled_exception=True` **tillates innenfor kvote**: 5 % av hypoteser siste 720 t (+1); øvrige blokkeres. Dette er CEO-DIR-2026-015s unntaksmekanisme | **Alt blokkeres.** Kvotelogikken (≈40 linjer, to `hypothesis_canon`-spørringer) er fjernet |
| `exception_quota_pct` fra DB | Leses (`result[2]`) — **men brukes aldri**; 0,05 er hardkodet | Ikke lest |
| `log_block` | Ødelagt: `""", (params) """)` — et overflødig `"""` etter parametertuppelen (linje 122/140). Dette er hele syntaksfeilen | Rettet: `.format(table)` + korrekt `))`; fallback lagt i egen `try` |
| `import json` | **Mangler** — `log_block` kaller `json.dumps` → `NameError` ved første blokk selv om syntaksen hadde vært rett | Lagt til |
| `DB_CONFIG.password` | Ingen nøkkel | Ingen nøkkel (allerede fail-closed på credential) |

**Adjudikeringsspørsmålet — mistet guarden logikk?** Ja. Verten fjernet ikke død kode; den
fjernet **den kontrollerte unntaksveien direktivet krever**, og ble strengere. Strengere er den
*trygge* retningen for en frys-guard — den kan ikke lekke hypoteser — men den er **ikke
compliant** med CEO-DIR-2026-015, og skjemaet forventer fortsatt mekanismen
(`hypothesis_canon.controlled_exception:boolean`, § 11d). Kallere som sender tre argumenter
(direktivets signatur) får `TypeError` mot vert-versjonen. Ingen av dem kjører i dag
(`finn_crypto/e/t_scheduler` alle `STOPPED` siden feb, § 12.1), så ingenting utøver guarden nå.

**Verdikt:** vert = trygg men ikke-compliant; repo = compliant men ødelagt (to feil: syntaks
og manglende import). **Ingen av dem er riktig fil.** Riktig fil er repoets logikk +
vertens syntaksfiks + `import json`. STIG har splittet den kandidaten deterministisk
(repo[guard-logikk] + vert[`log_block`] + repo[`__main__`], + import) i scratchpad og
kompilert den — **den er et forslag til VEGA G3, ikke deployet**, og legges ikke i
`03_FUNCTIONS/` på branchen før adjudikering. Ett policy-spørsmål følger med til VEGA/CEO:
skal kvoten bruke DB-verdien `exception_quota_pct` (som skjemaet har) eller direktivets
hardkodede 5 %? Repoet leser den ene og bruker den andre; det er ikke STIGs å velge.

**Kallerne (repo-side, verifisert):** alle fire produksjonskallere sender **tre** argumenter
(`conn, hypothesis_code, controlled_exception`) og importerer `from guard_generation_freeze
import guard_generation_freeze` — samme modulsti som verten har:

| Kaller | Kallsted | Arg | Status i `daemon_health` |
|---|---|---|---|
| `finn_crypto_scheduler.py` | :535 | 3 | `STOPPED` 2026-02-16 |
| `finn_e_scheduler.py` | :422 | 3 | `STOPPED` 2026-02-06 |
| `finn_t_scheduler.py` | :494 | 3 | `STOPPED` 2026-02-06 |
| `gn_s_shadow_generator.py` | :246 | 3 | `STOPPED` 2026-02-12 |
| 6 test-kallsteder (`dir_014b_*`) | — | 3 | — |

Mot vertens to-argument-guard gir alle fire `TypeError` ved første hypotese. **Fellen er
sovende** — alle fire har vært døde siden februar, før vertens 05-01-redigering — men den
utløses i det øyeblikket kontrollplanet restartes (Q4 2026, steg 0.5). Om vertens *kopier av
kallerne* også ble refaktorert til to argumenter er ukjent: a0 kan lese dem direkte
(`03_FUNCTIONS` er inne i dens eksport, F4 unødvendig). Ask til a0:
`grep -n -A2 'guard_generation_freeze(' /host/fhq-src/{finn_crypto_scheduler,finn_e_scheduler,finn_t_scheduler,gn_s_shadow_generator}.py`.
To-arg på verten → konsistent refaktor (fortsatt ikke-compliant). Tre-arg → latent `TypeError`
i produksjon. Begge utfall går i VEGA-briefen.

### 12.7 Neste runde (utført — se § 13)

`scripts/phase0_followup.sql` — kolonne-agnostisk mot de oppdagede tabellene:
**A** fabrikken (`sandbox_runs`, `research_objects`, lifecycle-events — antall, rader på
2026-09-08, `SELECT * LIMIT`), **B** hvem er koblet til nå (`pg_stat_activity`), **C** når ble
stats sist nullstilt (`pg_stat_database.stats_reset`) og topp-30 levende tabeller på tvers av
*alle* skjemaer, **D** LVI (`lvi_canonical`, `v_system_lvi`, `lvi_timeseries`), **E** Brier og
utfallsledgere, **F** `hypothesis_canon` — er deflatert-Sharpe/PBO-kolonnene *befolket*,
**G** `fhq_market.*` — hvor ble `prices` av. Samme kontrakt: a0 verifiserer fingeravtrykk, kun
lesing, returnerer rått.

---

## 13. FASE 0 — RUNDE 2 OG VERT-SJEKKER  (2026-09-09 15:38 Oslo)

**Proveniens:** `phase0_followup.sql` kjørt av a0 (fingeravtrykk `ed92b657…` / 192 / 32
verifisert, exit 0, 0 ERROR). Resultat 42 668 B, 309 linjer, sha256
`4f2509434decc7db092a18ae9f2460e56654d8e483b171d84b5721cf7db9a957`, i a0s container
`tmp/phase0_followup_result.txt`. Vert-sjekker 3a/3c kjørt av CEO i PowerShell på Windows-verten.
Rader ordrett.

### 13.1 Merge-gaten — IKKE oppfylt

| Sjekk | Resultat |
|---|---|
| `[Environment]::GetEnvironmentVariable('PGPASSWORD','Machine') -ne $null` | **`False`** |
| `[Environment]::GetEnvironmentVariable('PGPASSWORD','User') -ne $null` | **`False`** |

`PGPASSWORD` er ikke satt på noe OS-nivå på Windows-verten. § B (`pg_stat_activity`) viser tre
idle pool-tilkoblinger fra vertssiden (`client_addr 172.17.0.1`, docker-gateway) opprettet
13:55, 14:32 og 15:34 — **en timeplanlagt prosess på verten når databasen i dag** uten
`PGPASSWORD` i miljøet, altså via `.pgpass`, innebygd credential, eller nettopp
`'postgres'`-fallbacken `fd0328b6` fjerner. Identiteten er ikke lesbar fra SQL
(`application_name` tom).

**Beslutning: `fd0328b6` merges ikke.** Løsning (CEO, ~2 min, admin-PowerShell):
`[Environment]::SetEnvironmentVariable('PGPASSWORD','<verdi>','Machine')`, deretter 3a på nytt →
`True`. Avveining: maskinnivå gjør variabelen lesbar for alle prosesser på boksen — strengt
bedre enn en hardkodet `'postgres'` i 369 filer, men per-jobb-credential er sluttmålet (Lag 0).

### 13.2 Fabrikken er ekte — § 12.3s forbehold trekkes

| Spørring | Resultat | ASTRID 2026-09-08 |
|---|---|---|
| `sandbox_runs` totalt | **93** | 87 syntetiske + 88–90 reelle ≈ 90 |
| … som nevner 2026-09-08 | **8** | tick 1150–1163 |
| `research_objects` totalt | **87** | «87/87» |
| `lifecycle_events` | 71, **alle 71** nevner 2026-09-08; `created_at 2026-09-08 00:25:05` | «7 RO-statusverdier remappet» |
| ASTRIDs seks RO-id-er | `research_objects` 8 treff, `lifecycle_events` 12 treff, `sandbox_runs` **0** | e7cb94da, 994b6a83, 9e73188e … |
| `RUN-20260908T190000Z` / tick 1161–1163 | `lifecycle_events` 6, `research_objects` 2 | eksekutiv kjede |

**Den syntetiske signaturen ligger ordrett i DB-en** (A3): tre runs med identisk
`stdout_sha256 fd212d61…`, identiske `artifact_hashes`, `wall_seconds` 0,23 / 0,08 / 0,11,
`stderr_sha256 = e3b0c442…` (sha256 av tom streng), `owner STIG-P1PKG2`; pluss `WP08-TEST`-rader
med `command: echo`, `code_hash: abc`, `status RUNNING` for alltid. ASTRIDs rapport beskriver
denne databasen. **Én rest:** 0 treff i `sandbox_runs` for de seks RO-id-ene — de to reelle
kjøringene (89–90) refererer enten andre RO-er enn ASTRID navnga, eller ligger ikke i
`sandbox_runs`. Runde 3 § R2 avgjør.

### 13.3 Det levende systemet — og det er ikke det dokumentene beskriver

**Statistikkvinduet:** `pg_stat_database.stats_reset` = NULL; pg_cron-backendens `backend_start`
= **2026-09-09 11:11:49**. Alle `pg_stat`-tellere (11b, C2, E) gjelder **siden 11:11 i dag**
(~4,5 t ved måling). § 12.1 rad 10 må leses slik — ikke «måneder». Måneds-påstandene hviler på
tidsstemplene *i* tabellene (hjerteslag, `created_at`, governance-logg), som står.

**17 tabeller skrevet siste 4,5 t** (C2), 1 166 av 1 183 urørt:

| Tabell | ins / upd | Lag |
|---|---|---|
| `fhq_core.market_prices_live` | 62 658 / 22 052 209 | Binance SPOT: BTC, ETH, SOL |
| `fhq_runtime.run_locks` / `run_attempts` / **`run_failures`** | 583 / 583 / **530** | runtime-loop: **91 % av forsøkene feiler** |
| `fhq_features.btcusd_features` · `fhq_truth.btcusd_price_candle` | 285 · 272 (+1 023) | features/candles |
| `fhq_news.fhq_news_archive` · `_analysis_selection` | 230 · 17 | nyheter |
| `fhq_learning.btc_probability_signals` · `fhq_regime.btcusd_regime_state` | 72 · 26 | signal/regime |
| `fhq_control.factory_cycles` / `factory_cycle_nodes` | 18 / 18 | **fabrikken kjører sykluser i dag** |
| `fhq_research.challenger_forward_episodes` · `fhq_meta.execution_lease` | 1 (+132) · (+569) | evaluering · lease |

En **BTCUSD-pipeline** i skjemaer (`fhq_truth`, `fhq_features`, `fhq_regime`, `fhq_runtime`,
`fhq_news`) som hverken runtime-kartet (2026-03-09) eller Fase 0-scriptets opprinnelige sett
kjente. `sandbox_runs.command` = `/opt/venv/bin/python /a0/usr/projects/agent-zero_runtime_loop/
sandbox/experiments/…`, `image a0-container python:3.13`. § B: lease tatt av dedikert DB-bruker
fra `172.17.0.3`; en `UPDATE market_prices_live SET event_time_synthetic = TRUE WHERE id >= 62230446`
pågår fra samme container (= de 22 M oppdateringene: en backfill som *flagger syntetiske
tidsstempler* — M1 på datalaget). **Evidensen indikerer: `D:\Runtime` (`MetaStark/runtime`) er
a0s runtime-loop, og det er det levende systemet.** Bekreftelse fra CEO utestående.

DB-plattform bekreftet: `supabase_admin`-backends (`pg_net`, `pg_cron`) → **lokal Supabase-stack**
(54322 = Supabase CLI-default). pg_cron er en fjerde planleggingskontekst (`cron.job`) — kjører SQL
inne i DB-en, trenger ikke `PGPASSWORD`. Runde 3 § R5.

### 13.4 To læringsløkker

| Løkke | Tabeller | Tilstand |
|---|---|---|
| **Governance-laget** (mig 100/151/165/174/177 — det STIG analyserte) | `learning_proposals` 0 · `forecast_skill_registry` 0 · `canonical_outcomes` 4 seed · `epistemic_proposals` 0 · `knowledge_fragments` finnes ikke | Styrt, **aldri brukt** |
| **Lærings-/forskningslaget** | `research.outcome_ledger` **146 948** · `brier_score_ledger` **39 542** · `run_ledger` 39 437 · `decision_outcome_ledger` 24 477 · `hypothesis_ledger` 1 665 · `shadow_trades` 32 917 (siste 2026-05-25) · `regime_daily` 175 008 (siste 2026-06-08) | Befolket i skala, **sovende siden mars–juni**; 0 skriving siste 4,5 t |

Migrasjonene STIG leste bygget en parallell governance-løkke som aldri ble koblet til den
løkken som faktisk kjørte. AELL-2026-001 og 2027-planens § 2 beskrev den tomme.

**`hypothesis_canon` (F):** 1 539 hypoteser, 2026-01-23 → 2026-03-26, **0 siste 30 d**.
**1 538 FALSIFIED** (99,9 %), 1 DRAFT. `deflated_sharpe_computed` **75** (4,9 %), `pbo` 75,
`pre_tier_score` 1 216, `time_to_falsification` 1 319, **snitt 375,6 t** (15,7 d). Siste
statusendring 2026-04-25. Lesning: dødsdaemonen drepte ~alt; multippel-testing-korreksjonen ble
beregnet for 5 %. Planens «kill-rate ≥ 80 %» er oppfylt på en måte som *også* er en feilmodus —
et system som dreper 99,9 % lærer ikke, det sletter. Snitt-TTF er planens første reelle
LVI-baseline.

**LVI (D):** `v_system_lvi` beregnet **én gang**, 2026-01-20 (vindu 12-21→01-20,
`system_avg_lvi 0,168`, BEAR). `lvi_timeseries` **1 rad** (2026-02-09, `global_brier 0,350`,
`lvi_value NULL`). `lvi_calculator` hadde hjerteslag til 2026-04-10 uten å skrive hit.

**`fhq_market.prices`** (G): finnes ikke — **`prices_archived_20260904`** gjør. Kartets
primærinput ble arkivert 2026-09-04. Live-pipelinen er `market_prices_live`.

### 13.5 D6 — vertens kallere er også to-arg

a0 grep i egen eksport: `finn_crypto_scheduler.py:529`, `finn_e_scheduler.py:413`,
`finn_t_scheduler.py:485`, `gn_s_shadow_generator.py:244` — alle `guard_generation_freeze(conn,
hypothesis_code)`. **Verten ble konsistent refaktorert**; ingen `TypeError`-felle (§ 12.6 rettes).
To internt konsistente verdener: repo = direktiv-compliant, ødelagt; vert = kvote fjernet,
kompilerer. Spørsmålet til VEGA er rent governance, med to rene utfall:
**(1)** ratifiser verten → CEO-DIR-2026-015 endres, repoet oppdateres til vertens 5 filer;
**(2)** gjenopprett direktivet → kandidat-guard + 4 kallere tilbake til tre argumenter på verten.
Begge er 5-fils-endringer. Ingen av dem er STIGs å velge.

### 13.6 D5 — tallfestet

| Tre | Siste commit |
|---|---|
| GitHub `origin/master` | 2026-03-09 (`f9f148ef`) |
| Lokal `C:\fhq-market-system\vision-ios` | **2026-05-13 21:37** |
| `D:\Runtime` (`MetaStark/runtime`) | 2026-05-15 (`3ff28a0`, per a0) |
| `guard_generation_freeze.py` på vert | mtime 2026-05-01 |

Lokal er 65 dager foran master; begge er måneder bak runtime-klokken. Arbeidsstøt 1.–15. mai
på begge trær, så stillhet. (`git fetch` på verten viste `560453ac..f9f148ef` — lokal
`origin/master`-ref var 2026-03-09-backupen; nå oppdatert.)

### 13.7 Proveniens-forbehold — a0s redigeringslag

Runde 1 § 5 viste `§§secret(FHQ_TELEGRAM_ONLY_HOURLY)` for `is_active::text`. Runde 2 § H:
`is_active = t`. Verdien i DB-en var alltid `t`; **a0s relay redigerer output før hashing.**
Samme lag ga `§§secret(FHQ_LEASE_DB_USER)` i § B (tilsiktet). Konsekvens: a0s sha256 attesterer
«som a0 så det etter redigering», ikke rå DB-output. Akseptabelt for lesing; må nevnes i enhver
court-proof-referanse til disse filene.

### 13.8 Status D1–D8 etter Fase 0

| | |
|---|---|
| D1 | **Bevist**: 106 filer / 74 registrert / 0 hjerteslag < 24 t / 17 tabeller faktisk skrevet — av et *annet* delsystem |
| D2, D3 | Lukket (`df5b3112`) |
| D4 | Kode lukket; **merge blokkert** til 13.1 er `True` |
| D5 | Tallfestet (13.6); uløst |
| D6 | Adjudikeringsgrunnlag komplett (13.5); VEGA |
| D7 | `D:\Runtime` = a0 runtime-loop, evidensbasert; CEO bekrefter |
| D8 | Står |
| **D9 (ny)** | To læringsløkker: governance-laget tomt, forskningslaget befolket og sovende (13.4) |
| **D10 (ny)** | 530/583 kjøreforsøk feilet siste 4,5 t i `fhq_runtime` (13.3) — årsak i runde 3 |
