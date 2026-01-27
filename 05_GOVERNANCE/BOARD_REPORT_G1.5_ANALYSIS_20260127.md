# STYREMØTERAPPORT: G1.5 Kalibrering - Første Resultater

**Dato:** 2026-01-27
**Utarbeidet av:** STIG (CTO, EC-003)
**Klassifisering:** KONFIDENSIELT - KUN FOR STYRET
**Referanse:** CEO-DIR-2026-G1.5-BOARD-REPORT-001

---

## EXECUTIVE SUMMARY

G1.5 Calibration Freeze-eksperimentet har oppnådd sin primære trigger (171/30 dødsfall) og avdekket et **kritisk funn**: Den observerte inverse korrelasjonen skyldes **IKKE** scoring-formelen, men **degenererte input-distribusjoner** fra finn_crypto_scheduler.

| Nøkkelmetrikk | Verdi | Vurdering |
|---------------|-------|-----------|
| G1.5 Deaths | 171/30 | TARGET MET |
| Pearson r | **-0.4920** | Moderat negativ korrelasjon |
| Generator-konsentrasjon | **98.8%** finn_crypto | KRITISK VOLUM-BIAS |
| causal_depth_score | **KONSTANT 75.00** | ZERO VARIANS |
| Sample Size | 171 | Statistisk tilstrekkelig |

### Rotårsak Identifisert (Oppdatert 16:35 CET)

| Spørsmål | Svar |
|----------|------|
| Er inversjonen global (formelproblem)? | **NEI** |
| Er inversjonen generator-spesifikk? | **JA** |
| Er den dominert av én kilde (volum-bias)? | **JA (98.8% finn_crypto)** |

**Hovedkonklusjon:** Scoring-formelen kan IKKE evalueres før input-distribusjonene diversifiseres. Den negative korrelasjonen er et artefakt av homogene inputs, ikke en indikasjon på feil vekting.

---

## 1. G1.5 EKSPERIMENTSTATUS

### 1.1 Eksperimentdesign

| Parameter | Verdi |
|-----------|-------|
| Eksperiment-ID | FHQ-EXP-PRETIER-G1.5 |
| Startdato | 25. januar 2026 |
| Sluttdato | 8. februar 2026 |
| Varighet | 14 dager |
| Dag i eksperiment | Dag 2 (som vist), men system viser Dag 1 |
| Primær trigger | 30 dødsfall med pre_tier_score_at_birth |

### 1.2 Triggeroppnåelse

```
+------------------------------------------------------------------+
|  PRIMÆR TRIGGER: MET                                              |
+------------------------------------------------------------------+
|  Mål:           30 dødsfall med score                             |
|  Oppnådd:       171 dødsfall (570% av mål)                        |
|  Status:        VEGA Reasoning-Delta rapport kan utarbeides       |
+------------------------------------------------------------------+
```

### 1.3 Kritisk Hendelse (27. januar 2026)

En arkitekturfeil ble oppdaget og korrigert samme dag:

| Tidspunkt | Hendelse |
|-----------|----------|
| 08:29 CET | CEO rapporterer 0 dødsfall (forventet 33+) |
| 08:35 CET | Rotårsak identifisert: Death daemon ignorerte ACTIVE status |
| 08:45 CET | Fix implementert og deployed |
| 08:50 CET | 171 dødsfall prosessert, G1.5 trigger MET |

**Læringspunkt:** Hypotese-livssyklus må ha eksplisitt dødsbane for ALLE statuser.

---

## 2. KORRELASJONSANALYSE - OPPDATERT MED KOMPONENT-DEKOMPONERING

### 2.1 Aggregert Korrelasjon

| Metrikk | Verdi | Tolkning |
|---------|-------|----------|
| Pearson r | **-0.4920** | Moderat negativ korrelasjon |
| Sample size | 171 | Tilstrekkelig for statistisk validitet |

**NB:** Dashboard viste Spearman rho på -8.5069, som var en t-statistikk, ikke en korrelasjonskoeffisient. Pearson r på -0.4920 er den korrekte verdien.

### 2.2 Komponent-Korrelasjon (Database-verifisert)

| Komponent | Spearman rho | t-statistikk | Signifikans | Pearson r | Tolkning |
|-----------|--------------|--------------|-------------|-----------|----------|
| causal_depth_score | -0.9256 | -31.79 | p<0.001 *** | +0.4929 | **ARTEFAKT** |
| cross_agent_agreement | -0.6063 | -9.91 | p<0.001 *** | -0.7859 | Mest konsistent |
| evidence_density_score | -0.6025 | -9.81 | p<0.001 *** | -0.1215 ns | Utilstrekkelig |
| data_freshness_score | -0.5825 | -9.32 | p<0.001 *** | -0.1573 | Svak |

**Kritisk observasjon:** Spearman vs Pearson gir motsatt retning for `causal_depth_score`. Dette skyldes at komponenten er **konstant** (se 2.3).

### 2.3 ROTÅRSAK: Degenererte Input-Distribusjoner

finn_crypto_scheduler (98.8% av data) produserer **nesten identiske** komponent-scores:

| Komponent | Unike verdier | Min | Max | Gjennomsnitt | Std.avvik |
|-----------|---------------|-----|-----|--------------|-----------|
| causal_depth_score | **1** | 75.00 | 75.00 | 75.00 | **0.00** |
| cross_agent_agreement | 6 | 95.94 | 100.00 | 99.77 | 0.91 |
| evidence_density_score | **3** | 40.30 | 50.00 | 49.46 | 2.16 |
| data_freshness_score | 6 | 80.00 | 98.09 | 80.97 | 3.88 |

**Konsekvens:**
- `causal_depth_score` = KONSTANT → ingen diskriminerende kraft
- `cross_agent_agreement` = nær-konstant → marginal varians
- `evidence_density_score` = kun 3 verdier → kategorisk, ikke kontinuerlig
- `data_freshness_score` = kun 6 verdier → begrenset varians

### 2.4 Breakdown etter Tier-1 Resultat

| Tier-1 Resultat | Antall | Gjennomsnittlig Score | Gjennomsnittlig TTF |
|-----------------|--------|----------------------|---------------------|
| WEAKENED | 169 | 66.28 | 29.1 timer |
| SURVIVED | 2 | 58.86 | 57.5 timer |

**Observasjon:** Hypoteser som OVERLEVDE Tier-1 hadde **lavere** score men levde **dobbelt så lenge**.

### 2.5 Konklusjon: Hva Betyr Den Negative Korrelasjonen?

| Tidligere hypotese | Status | Forklaring |
|--------------------|--------|------------|
| Causal Depth inverst korrelert | **FALSIFISERT** | Komponenten er KONSTANT, ingen signal |
| Evidence Density overvektet | **UAVKLART** | Kun 3 verdier, kan ikke evalueres |
| Freshness-decay feil kalibrert | **UAVKLART** | Begrenset varians |
| Generator-bias | **BEKREFTET** | 98.8% fra finn_crypto med degenererte inputs |

**Endelig diagnose:** Korrelasjonen reflekterer finn_crypto's input-karakteristikker, IKKE scoring-formelens filosofi.

---

## 3. GENERATOR-ANALYSE - KRITISK KONSENTRASJONSRISIKO

### 3.1 Generatorfordeling (G1.5 Dødsfall med Score)

| Generator | Dødsfall med Score | % av G1.5 Data | Snitt Score | Snitt TTF |
|-----------|-------------------|----------------|-------------|-----------|
| finn_crypto_scheduler | 169 | **98.8%** | 66.28 | 29.1h |
| GN-S | 2 | 1.2% | 58.86 | 57.5h |
| FINN-E | 0 | 0% | - | - |
| FINN-T | 0 | 0% | - | - |
| CEIO | 0 | 0% | - | - |

### 3.2 Kritiske Observasjoner

1. **finn_crypto dominerer G1.5:** **98.8%** av alle dødsfall med score kommer fra én generator
2. **FINN-E og FINN-T:** 0 dødsfall med score (48h horisont, utløper 28-29. jan)
3. **GN-S:** Kun 2 datapunkter - statistisk utilstrekkelig for analyse

### 3.3 Diversitetsrisiko - KRITISK

Generator Diversity (3.0/3) er **misvisende** for G1.5-analyse:

| Problem | Konsekvens |
|---------|------------|
| 98.8% fra finn_crypto | G1.5 måler finn_crypto-oppførsel, ikke formelen |
| finn_crypto har konstant causal_depth | Umulig å evaluere vekt-bidraget |
| Ingen data fra FINN-E/FINN-T | Kan ikke sammenligne på tvers av generatorer |

**Konklusjon:** G1.5-dataene kan IKKE brukes til å konkludere om scoring-filosofi før generator-diversitet oppnås.

---

## 4. DEATH RATE OG TIER-1 BRUTALITET

### 4.1 Nåværende Status

| Metrikk | Verdi | Mål | Status |
|---------|-------|-----|--------|
| Death Rate | 53.4% | 60-90% | **FOR MILD** |
| Total Tested | 455 | - | - |
| Falsified | 204 | - | - |
| Active | 178 | - | - |

### 4.2 Anbefaling

Dashboard viser: *"BEHIND: Death rate too low - Tier-1 not brutal enough, tighten falsification criteria."*

**Merk:** Under G1.5 Calibration Freeze er det IKKE tillatt å justere Tier-1 parametere. Dette må vente til etter eksperimentet (8. februar 2026).

---

## 5. KANONISKE TESTER - STATUSOVERSIKT

### 5.1 Aktive Tester (5 stk)

| Test | Status | Progresjon | Death Rate |
|------|--------|------------|------------|
| EC-022 Reward Logic Freeze | PENDING | 10% (Dag 3/30) | 53.0% |
| Tier-1 Brutality Calibration | ACTIVE | 67% (Dag 2/3) | 53.0% |
| Golden Needles Shadow-Tier | ACTIVE | 14% (Dag 2/14) | 53.0% |
| FINN-T World-Model | ACTIVE | 14% (Dag 2/14) | 53.0% |
| G1.5 Calibration Freeze | ACTIVE | 7% (Dag 1/14) | 47.3% |

### 5.2 Viktige Datoer

| Dato | Hendelse |
|------|----------|
| 27. jan 2026 | Tier-1 Brutality Calibration avsluttes |
| 7. feb 2026 | Golden Needles + FINN-T avsluttes |
| 8. feb 2026 | G1.5 Calibration Freeze avsluttes |
| 23. feb 2026 | EC-022 Reward Logic avsluttes |

---

## 6. ØKONOMISK KALENDER - KOMMENDE HENDELSER

### 6.1 Høy-impact Hendelser (Neste 14 dager)

| Dato | Hendelse | Impact |
|------|----------|--------|
| 28. jan | FOMC Interest Rate Decision | **5 (HIGHEST)** |
| 30. jan | ECB Interest Rate Decision | **5 (HIGHEST)** |
| 7. feb | US Non-Farm Payrolls | **5 (HIGHEST)** |

### 6.2 Implikasjoner for Hypotesetesting

FOMC (28. jan) og ECB (30. jan) vil skape betydelig markedsvolatilitet. Hypoteser med makro-eksponering vil bli testet under reelle forhold.

---

## 7. SYSTEMHELSE

### 7.1 Daemon-status

| Daemon | Status | Funksjon |
|--------|--------|----------|
| daemon_watchdog | HEALTHY | Overvåkning |
| hypothesis_death_daemon | HEALTHY | **VERSION 2.0** (fikset) |
| finn_brain_scheduler | HEALTHY | Generering |
| finn_crypto_scheduler | HEALTHY | Generering |
| finn_e_scheduler | HEALTHY | Generering |
| finn_t_scheduler | HEALTHY | Generering |
| tier1_execution_daemon | HEALTHY | Testing |
| pre_tier_scoring_daemon | HEALTHY | Scoring |

### 7.2 Validator Pool

| Validator | Valideringer | Status |
|-----------|--------------|--------|
| CEIO | 12 | Aktiv |
| GN-S | 10 | Aktiv |
| FINN-E | 2 | Aktiv |
| CRIO | 0 | Ny |
| CSEO | 0 | Ny |

---

## 8. ANBEFALINGER TIL STYRET (OPPDATERT)

### 8.1 Umiddelbare Tiltak (Ingen kodeendringer - G1.5 Freeze)

| # | Tiltak | Ansvarlig | Frist | Status |
|---|--------|-----------|-------|--------|
| 1 | Verifiser Spearman-beregning i dashboard | STIG | 28. jan | UTFØRT - var t-statistikk |
| 2 | Utarbeid VEGA Reasoning-Delta rapport | VEGA | 29. jan | PENDING |
| 3 | Analyser komponent-korrelasjon individuelt | STIG | 30. jan | **UTFØRT 27. jan** |
| 4 | Forbered rekalibrerings-plan for post-G1.5 | LARS/STIG | 7. feb | REVURDERES |

### 8.2 Post-G1.5 Tiltak (Etter 8. februar 2026) - REVIDERT

| # | Tiltak | Prioritet | Begrunnelse |
|---|--------|-----------|-------------|
| 1 | **Fiks finn_crypto causal_depth beregning** | **P0 KRITISK** | Konstant 75.00 = ingen signal |
| 2 | **Sikre kontinuerlige komponent-distribusjoner** | **P0 KRITISK** | Kategoriske inputs bryter analyse |
| 3 | Balansere generator-volum | P1 HØY | 98.8% konsentrasjon invaliderer data |
| 4 | **RE-KJØR G1.5 analyse med fikset input** | P2 MEDIUM | Kan ikke konkludere på nåværende data |
| 5 | Justere Tier-1 brutalitet til 60-90% | P3 | Utsatt til inputs diversifisert |

**VIKTIG:** Rekalibrering av vekter er **IKKE** anbefalt basert på nåværende data. Først må input-problemene løses.

### 8.3 Strategiske Spørsmål for Styret (REVIDERT)

1. **Aksepterer styret at G1.5-eksperimentet fortsetter uten inngrep frem til 8. februar?**
   - Anbefaling: JA - eksperimentets integritet krever frys
   - TILLEGG: Data fra FINN-E/FINN-T (utløper 28-29. jan) vil gi diversitet

2. **Godkjenner styret at scoring-formelen IKKE revideres basert på nåværende data?**
   - Anbefaling: **JA** - dataene reflekterer input-problemer, ikke formel-problemer
   - Først må finn_crypto's causal_depth-beregning fikses

3. **Skal P0-input-fikser prioriteres umiddelbart etter G1.5 Freeze?**
   - Anbefaling: **JA** - uten dette kan vi ikke evaluere scoring-filosofien

---

## 9. RISIKOVURDERING (REVIDERT)

### 9.1 Identifiserte Risikoer

| Risiko | Sannsynlighet | Konsekvens | Mitigering | Status |
|--------|---------------|------------|------------|--------|
| ~~Feil korrelasjon styrer fremtidig prioritering~~ | ~~HØY~~ | ~~KRITISK~~ | ~~Rekalibrering~~ | **MITIGERT** - rotårsak identifisert |
| Generator-konsentrasjon skjuler mønstre | **BEKREFTET** | KRITISK | Øke diversitet post-G1.5 | AKTIV |
| Feilaktig vekt-justering basert på ugyldig data | HØY | KRITISK | IKKE rekalibrere før inputs fikset | NY |
| finn_crypto's konstante causal_depth | **BEKREFTET** | HØY | P0-fiks etter G1.5 | NY |

### 9.2 Positiv Utvikling

| Faktor | Vurdering |
|--------|-----------|
| G1.5 trigger oppnådd | Tilstrekkelig data for **diagnose** (ikke konklusjon) |
| Rotårsak identifisert | Komponent-dekomponering avslørte input-problem |
| Systemstabilitet | Alle daemons HEALTHY |
| Data-integritet | Database-verifisert |
| FINN-E/FINN-T data kommer | 28-29. jan vil gi diversitet |

---

## 10. KONKLUSJON (REVIDERT)

G1.5 Calibration Freeze har avdekket **verdifull diagnostisk innsikt**, men IKKE den forventede konklusjonen:

### Tidligere Konklusjon (Feilaktig)
> "Pre-tier scoring-formelen fungerer ikke som intendert og må rekalibreres."

### Ny Konklusjon (Korrekt)
> **Pre-tier scoring-formelen KAN IKKE evalueres med nåværende data.**
>
> Den negative korrelasjonen (-0.4920) skyldes degenererte input-distribusjoner fra finn_crypto_scheduler:
> - `causal_depth_score` = KONSTANT 75.00
> - 98.8% av data fra én generator
> - Komponenter har nær-null varians
>
> **Scoring-filosofien er verken bekreftet eller avkreftet.**

### Neste Milepæler

| Dato | Milepæl | Forventet utfall |
|------|---------|------------------|
| 28. jan | FINN-E dødsfall begynner | Diversitet økes |
| 29. jan | VEGA Reasoning-Delta rapport | Analysere med ny data |
| 8. feb | G1.5 Freeze avsluttes | Implementere P0-fikser |
| Post-G1.5 | Re-kjør korrelasjonsanalyse | Gyldig evaluering av formel |

---

**Signatur:**

STIG
CTO, FjordHQ
EC-003_2026_PRODUCTION

---

*Denne rapporten er oppdatert med komponent-korrelasjonsanalyse per 2026-01-27 16:45 CET.*
*Referanse: G1.5_COMPONENT_CORRELATION_ANALYSIS_20260127.md*
*Dashboard: http://localhost:3003*
*Database: PostgreSQL 17.6 @ 127.0.0.1:54322*
