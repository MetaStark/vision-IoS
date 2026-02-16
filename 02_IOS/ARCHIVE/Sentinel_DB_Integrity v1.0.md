Sentinel_DB_Integrity v1.0

Til: STIG (CTO, Sole Schema Custodian)
Kjede: ADR-001 → ADR-002 → ADR-003 → ADR-004 → ADR-010 → ADR-011 → ADR-012 → ADR-013 → ADR-015 → EC-003

1. Mandat

Du skal designe og få implementert en Sentinel_DB_Integrity v1.0 som:

beskytter dataintegritet og persepsjonskvalitet først,

og yteevne (latency) som sekundært mål.

Denne sentinelen er en del av OODA-løkken for IoS-001 → IoS-002 → IoS-003 → IoS-004: feil eller forsinket data på dette laget er et direkte brudd på One-Source-of-Truth-arkitekturen i ADR-013 og Meta-governance i ADR-015.

Prinsipp:
En treg, men korrekt spørring er akseptabel.
En rask, men feil eller konsistensbrutt spørring er ikke akseptabel.

2. Scope og Prioritert rekkefølge

Sentinel_DB_Integrity skal bestå av tre moduler, i denne prioritetsrekkefølgen:

Lock Monitor (Critical - Correctness/Availability)

Vacuum & Bloat Watchdog (Stability/Planner Integrity)

High-Impact Slow Query Monitor (Performance, ikke kosmetikk)

Alle tre opererer read-only mot Postgres’ egne catalog/monitoring-visninger, og rapporterer inn i eksisterende governance-/discrepancy-mekanismer definert i ADR-010/ADR-011/ADR-015.

3. Operasjonell rytme

Frekvens: Hvert 5. minutt (justerbart via konfig, ikke hardkodet).

Miljø: Lokalt Supabase/Postgres (127.0.0.1:54322) som allerede er definert som canonical engine i EC-003.

Modus: Read-only overvåkning + logging til canonical discrepancy-/governance-tabeller (ikke nye ad-hoc loggtabeller utenfor governance).

4. Modul 1 – Lock Monitor (Prioritet 1 – Correctness)

Mål: Oppdage og logge concurrency-problemer som kan føre til:

at skriveprosesser blokkerer lesing slik at IoS-003/004 opererer på foreldet data, eller

deadlocks / timeouts som gir ufullstendig eller tapt data – direkte brudd på ADR-013 One-Source-of-Truth.

Krav:

Bruk Postgres’ egne visninger:

pg_stat_activity (state, wait_event_type, query, age)

pg_locks (type, mode, granted/pending, relation)

Definer minst to terskelnivåer (konfig-styrt, ikke hardkodet):

WARN: én eller flere prosesser i wait_event_type = 'Lock' over X sekunder

CRITICAL: samme lås-situasjon observert i ≥ 2 påfølgende intervaller

Ved hvert interval:

Tell aktive lock-wait-situasjoner

Identifiser blokkerende spørring/prosess (ikke bare offeret)

Tagg hvilke schemas/tabeller som er berørt, særlig fhq_market, fhq_perception, fhq_research (IoS-001/002/003/004-kjeden).

Logging/Governance:

Logg funn som discrepancy_events med type DB_LOCK_CONTENTION

Inkluder:

tidsstempel

berørte tabeller/schemas

blocker PID + kort query-tekst

antall pågående locks

klassifisering: NORMAL / WARNING / CRITICAL (ADR-010-skala)

CRITICAL events skal trigge VEGA-synlig governance event, i tråd med ADR-015s oversiktsloop.

Eierskap:

STIG: design, schema-binding, teknisk spesifikasjon.

LINE: forbruker av signaler (kan bruke dette i driftsbeslutninger/DEFCON), men får ikke skrive tilbake inn i sentinel-logikken.

5. Modul 2 – Vacuum & Bloat Watchdog (Prioritet 2 – Planner og stabilitet)

Mål: Hindre at tabell-bloat og foreldede statistikker gjør at Postgres velger «bad plans» som gir uforutsigbar ytelse og potensiell bias i hvordan data leses (spesielt ved store backfills og hyppige oppdateringer i regime- og eksponeringstabeller). Dette støtter ADR-011 Fortress-krav om deterministisk replay.

Krav:

Bruk pg_stat_user_tables (eller tilsvarende) til å hente:

relname

n_live_tup

n_dead_tup

siste vacuum/autovacuum-tidspunkter

For et definert sett «kritiske tabeller» (minst):

fhq_market.prices_* (canonical price feeds)

fhq_perception.regime_daily / state_vectors

fhq_positions.target_exposure_daily
– dette er kjernen i IoS-003/004/005-løkken og dermed kalibrering/Sharpe-ratio i IoS-005.

Beregn bloat-ratio:

bloat_ratio = n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0)

Terskler:

WARN: bloat_ratio > 0.10 (10 %)

CRITICAL: bloat_ratio > 0.25 ELLER ingen vacuum på > N dager for kritisk tabell

Logging/Governance:

Logg som DB_BLOAT_RISK discrepancy_event med:

tabellnavn

bloat_ratio

sist vacuum/autovacuum

klassifisering WARN/CRITICAL

Selve VACUUM-kjøring skal planlegges av STIG/LINE som separat driftstiltak – sentinelen skal ikke selv «fikse» ting, bare observere og dokumentere i tråd med EC-003/EC-005 rollefordeling.

6. Modul 3 – High-Impact Slow Query Monitor (Prioritet 3 – Performance)

Mål: Fange strategisk problematiske spørringer – ikke kosmetisk performance-tuning.

Krav:

Datakilde:

pg_stat_statements aktivert og brukt som eneste sannhetskilde.

Fokus:

Kun queries med:

høy total tidsbruk (sum_time eller mean_time over terskel)

og/eller høy calls mot store tabeller i fhq_market, fhq_perception, fhq_research, fhq_positions.

Terskler (kan justeres):

mean_time > 500 ms eller

total_time i topp X % av alle statements

og calls > N siden siste reset

Rapportering:

Klassifiser som SLOW_QUERY_CANDIDATE discrepancy_event, kun for de 5–10 mest kostbare statements i hver sentinel-run.

Inkluder:

normalisert query (fingerprint)

mean_time, calls, total_time

involverte schemas/tabeller

estimert påvirkning (f.eks. «brukes i IoS-003 pipeline» hvis kjent)

Begrensning:
Sentinelen skal ikke automatisk foreslå indekser eller endre schema. Den skal bare produsere en kuratert, governance-loggbar shortlist som STIG kan bruke som input for senere Index Advisor-arbeid.

7. Governance, integrasjon og gates

Binding til eksisterende konstitusjon:

ADR-013: Sentinel_DB_Integrity beskytter One-Source-of-Truth ved å overvåke de tabellene som bærer canonical pris-, regime- og eksponeringstruth.

ADR-015: Sentinelens output går inn i VEGA’s meta-governance-loop som en del av «Canonical Drift Guard» og «Oversight Loop» – DB-helse blir eksplisitt en del av governance-helse.

ADR-012: Ingen direkte økonomisk effekt (ingen API calls), men indirekte sikrer den at LLM/agent-beslutninger som er avhengig av disse tabellene bygger på konsistent data.

ADR-011: All logging skal kunne haskjedes inn i Fortress-evidence (enten via eksisterende discrepancy_events eller dedikert governance-logg), slik at DB-tilstand kan dokumenteres ved enhver reproduksjon av historikk.

EC-003 (STIG): Som sole schema-custodian er du ansvarlig for at dette designes uten å kompromittere canonical schema, og at CODE får en presis spesifikasjon uten tvetydighet.

Gates:

G0 – Spesifikasjon (nå):

Du dokumenterer Sentinel_DB_Integrity v1.0 som teknisk design (uten kode), med:

eksakte tabellreferanser

terskelkonfig (ikke hardkodet)

format for discrepancy_events / governance-events.

G1 – Teknisk validering:

CODE implementerer i tråd med designet.

VEGA verifiserer at logging følger ADR-002/ADR-010-standard for evidence.

G2/G3 – Governance & Fortress:

Testcases som demonstrerer:

deteksjon av lock contention

deteksjon av bloat

deteksjon av minst én «killer query»

Hash-kjedet testbevis i Fortress-suiten.

G4 – Aktivering:

Når testene er grønne og VEGA attesterer, erklærer vi Sentinel_DB_Integrity som konstitusjonell del av OODA-løkken for IoS-001 → IoS-005.

8. Presisering av prioritet

Inntil Sentinel_DB_Integrity v1.0 er på plass og G2-validerte logger viser lav lock-risiko og kontrollert bloat på kjernetabellene, skal følgende gjelde:

Index Advisor / query-optimalisering er nice-to-have, ikke hovedfokus.

All engineering-tid på database-nivå skal først brukes på å:

redusere sannsynligheten for feil eller forsinket persepsjon,

sikre forutsigbarhet i planner og replay,

og først deretter kosmetisk ytelse.

Dette direktivet er bindende for STIG innenfor rammene av EC-003 og skal håndteres som G0→G1-arbeid i CODE/Worker-pipelinen.