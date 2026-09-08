# FjordHQ Autonomous Operations — Implementeringsplan

**Utsteder:** STIG (EC-003_2026_PRODUCTION)
**Dato:** 2026-09-08
**Status:** Fase 1 UTFØRT (se § 8) · Fase 3 KLAR · Fase 0/2 BLOKKERT (sannhetskilde utilgjengelig) · Fase 4 AVVENTER LARS
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
| D4 | Åpen — Fase 3, kan starte nå |
| D5 | Åpen — krever push av lokal utvikling |
