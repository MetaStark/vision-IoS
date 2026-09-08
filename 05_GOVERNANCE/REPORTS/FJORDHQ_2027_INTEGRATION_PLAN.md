# FjordHQ 2027 — Integrasjonsplan for finansiell forskning

**Fra evidensfabrikk til verdens raskeste ærlige falsifikasjonsløkke**

**Utsteder:** STIG (EC-003_2026_PRODUCTION) · **Til:** CEO, LARS, VEGA
**Dato:** 2026-09-08 · **Status:** UTKAST til G-gate · **Mandat:** teknisk arkitektur og sekvens. Retning (§ 8) eies av LARS.

---

## 0. Én setning

> I 2027 er FjordHQs fortrinn ikke en bedre modell. Det er systemet som **dreper sine egne dårlige hypoteser raskere enn noen andre — med bevis som holder i retten.**

Alt under følger av den setningen.

---

## 1. Premisset: hvorfor transparens gjør falsifikasjon til vollgraven

Markedet er blant verdens mest studerte. Det betyr tre ting som ikke kan forhandles bort:

1. **Alle ser samme data.** Ingen har informasjonsfortrinn på prisserier, makro, kalendere. Fortrinn på *data* finnes ikke.
2. **Enhver publisert kant forvitrer.** McLean & Pontiff (2016): avkastningen til dokumenterte anomalier faller med ~26 % ut-av-sample og ~58 % etter publisering. Markedet *lærer* av forskningen. En kant er en forbruksvare med utløpsdato.
3. **De fleste kanter var aldri ekte.** Harvey, Liu & Zhu (2016) viser at med hundrevis av testede faktorer er en t-verdi på 2 ikke evidens — de anbefaler en hinder på **t > 3**. Hou, Xue & Zhang (2020) replikerte anomalilitteraturen: *flertallet* holder ikke.

Konklusjonen er ikke pessimistisk, den er presis: i et transparent marked er **produksjonshastighet av ideer verdiløs**. Det som har verdi er **hastigheten og ærligheten i å forkaste dem**, og evnen til å *bevise* at det som overlevde ble prøvd hardt nok. FjordHQ har allerede den riktige metrikken for dette i systemet: **LVI — Learning Velocity Index.** Læringshastighet *er* falsifikasjonshastighet.

Transparens er ikke bare markedets egenskap. Den er **produktet**: court-proof forskning som kan vise hver dom, hvert drap, hver kalibrering, hash-kjedet (ADR-011).

---

## 2. Meta-analyse: hva avgjør suksess i systematisk forskning

Fem funn fra litteraturen og fra shops som har overlevd tiår. Hvert er kartlagt mot en FjordHQ-primitiv, med **verifisert status per 2026-09-08**.

| # | Funn | Konsekvens for design | FjordHQ-primitiv | Status i dag |
|---|---|---|---|---|
| **M1** | **Systemet lurer seg selv.** Backtest-overtilpasning (Bailey, Borwein, López de Prado & Zhu; *Probability of Backtest Overfitting*) er standardtilstanden, ikke unntaket. López de Prado: «backtesting er ikke et forskningsverktøy» — det er en *validering* av en hypotese formulert uavhengig. | Hypotesen må fryses *før* data inspiseres. Evidensen må være umulig å fabrikkere stille. | `research_objects` fryses med attest (K1) før kjøring; `experiment_spec`-binding (DP1); stdout-hash + veggtid som harde porter (DP2 G-A…G-E) | **Hul til i dag.** 87/87 kjøringer syntetiske. DP1–DP4 implementert og bevist 2026-09-08; 2 reelle kjøringer. Fabrikk pauset på ny feilklasse. |
| **M2** | **Multippel testing spiser signalet.** Test 1 000 hypoteser, og ~50 «passerer» ved p < 0,05 ved ren tilfeldighet. Deflated Sharpe Ratio (Bailey & López de Prado 2014) korrigerer for antall forsøk. | Nevneren må telles. Hvert drap er en del av beviset for det som overlevde. | Kill-ledger (byte-identisk hele dagen, 4010e0c8); `hypothesis_death_daemon`; `forecast_skill_registry` med bootstrap/permutasjon | **Finnes.** Men ingen deflatert-Sharpe-port ved admission; kill-ledgeren brukes som logg, ikke som *nevner*. |
| **M3** | **Kanter forvitrer.** Regimer skifter; det som virket i 2024 virker ikke i 2027. Non-stasjonaritet er regelen. | Validitet må forfalle med tid og *måles* på nytt. Tillit til kilder og hypoteser må oppdateres av utfall. | `knowledge_fragments.decay_rate`, `calculate_effective_relevance`, `calibration_versions`, HMM-regimer (IoS-003) | **Delvis.** Forfall er statisk (rate satt ved opprettelse). Ingen kilde-tillit. Ingen hypotese-kvalitetsscore per kategori. (AELL-2026-001 gap 3–5.) |
| **M4** | **Kalibrering slår treffsikkerhet.** Et system som vet *hvor sikkert det bør være* overlever et som er «rett» oftere men overkonfident. Brier-score og pålitelighetskurver er standard i prognoseforskning (Tetlock). | Konfidens må scores mot utfall, per bøtte. Overkonfidens må *straffes* automatisk. | `canonical_outcomes.needle_eqs_score` + `pnl` gir råmaterialet; `fn_analyze_confidence_calibration` (mig 177) beregner Brier per bøtte | **Bygget i dag, ikke aktivert mot DB.** Ingen kalibreringskurve i produksjon. |
| **M5** | **Prosess slår geni.** Renaissance, AQR, Two Sigma: fortrinnet er forsknings*infrastruktur* og *falsifikasjonsdisiplin*, ikke enkeltpersoner. Og: infrastruktur som ikke observeres, forfaller stille. | Ingenting kjører uten at kontrollplanet vet det. Ingen stille feil. Alt reversibelt. | `daemon_manager`, `fhq_monitoring.daemon_health` med fail-closed heartbeat (mig 346), `fhq_ops` Control Room (mig 332), VEGA-veto, G0–G4 | **Kontrollplanet dekker 5 av 106 loops.** 33 skyggedaemoner (lukket i dag). 375 stille standardpassord (lukket i dag, merge-gatet). `guard_generation_freeze` ødelagt ved HEAD → 3 FINN-schedulere kan ikke importere (D6). |

**Lesningen av tabellen:** FjordHQ har *designet* riktig — primitivene for M1–M5 finnes i konstitusjonen og skjemaet. Det som manglet var at **evidenskjernen var hul (M1) og kontrollplanet blindt (M5)**. Begge deler ble avdekket og delvis lukket *i dag*. Det er ikke tilfeldig at det er de to: de er de to måtene et forskningssystem dør stille på.

---

## 3. Diagnostikk 2026-09-08 — den ærlige nullinjen

Alt under er verifisert i dag mot fil, DB eller kvittering. Ingenting er antatt.

| Lag | Funn | Kilde |
|---|---|---|
| Evidenskjerne | 87/87 sandbox-kjøringer siden 24.08 syntetiske (0,07–0,17 s, tom stdout). Forrige 48H-sak: 40 «eksperimenter» = 100 % ikke-evidens. | ASTRID, DB-verifisert |
| Evidenskjerne | DP1–DP4 implementert, 37/37 tester ×3, sandbox_run 88 = første reelle kjøring noensinne; 89–90 = første to gjennom hele pipelinen | ASTRID |
| Evidenskjerne | Fabrikk PAUSED 19:10Z, tick 1161–1163 ERROR, eies av `RUN-20260908T190000Z` | ASTRID |
| Kontrollplan | 106 loop-filer, **5 forvaltet** (D1) | STIG, filsystem |
| Kontrollplan | 33 daemoner duplisert; 30 identiske, 3 divergerende; kontrollplanet kalte kun én kopi → 22 288 linjer død kode (D2/D3) — **lukket** `df5b3112` | STIG, verifisert |
| Kontrollplan | Kontrollplanet selv hardkodet Windows-sti og passord (D4) — **lukket** `b9303303` + `fd0328b6` (369 filer, merge-gatet) | STIG, verifisert |
| Kontrollplan | Repo master@2026-03-09; runtime 2026-09-08 → **6 måneders drift** (D5) | STIG, git |
| Kontrollplan | `guard_generation_freeze.py` syntaksfeil ved HEAD → `finn_crypto/e/t_scheduler` kan ikke importere; én er kontrollplan-forvaltet (D6) | STIG, verifisert |
| Epistemisk lag | ~70 % av en adaptiv epistemisk læringsløkke finnes; meta-læring governance-låst; Proposal Engine bygget (mig 177), aktivert per CEO-DIR-2026-META-LEARNING-001 | AELL-2026-001/-002 |
| Sannhetskilde | DB utilgjengelig fra sky-økten; alt DB-avhengig er `[GATED]` | STIG |

**Den viktigste setningen i dette dokumentet:** Systemet fikk *i dag* for første gang teknisk evne til å produsere sannferdig evidens. Enhver 2027-plan som ikke starter der, er fantasi.

---

## 4. Arkitektur 2027 — fem lag, én regel

**Regelen:** Et lag bygges kun på et *verifisert* lag under. Ikke designet. Verifisert.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ LAG 4 · KAPITAL        LINE · paper → live, gatet av ADR-012 QG-F6      │
│                        Åpnes kun av ut-av-sample-evidens + LVI-terskel  │
├─────────────────────────────────────────────────────────────────────────┤
│ LAG 3 · META-LÆRING    Proposal Engine → VEGA-konvolutt → bounded auto  │
│                        Systemet foreslår; mennesket godkjenner;         │
│                        innenfor konvolutt: systemet justerer selv       │
├─────────────────────────────────────────────────────────────────────────┤
│ LAG 2 · EPISTEMIKK     Brier per bøtte · kilde-tillit · hypotese-       │
│                        kvalitet per kategori/regime · adaptivt forfall  │
│                        «Vet vi hva vi ikke vet?»                        │
├─────────────────────────────────────────────────────────────────────────┤
│ LAG 1 · EVIDENSFABRIKK RO frosset → spec-bundet eksekvering → dom       │
│                        Deflatert Sharpe ved admission · kill-ledger     │
│                        som nevner · holdout-protokoll · kostmodell      │
├─────────────────────────────────────────────────────────────────────────┤
│ LAG 0 · SANNHET        canonical_outcomes · daemon_health 106/106 ·     │
│                        fail-closed alt · ingen stille feil · repo=runtime│
│                        «Kjører det? Beviselig?»                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Hva som allerede finnes per lag** (verifisert): Lag 0 — `canonical_outcomes`, `daemon_health` + mig 346, `fhq_ops`. Lag 1 — hele RO-livssyklusen, DP1–DP4, kill-ledger, `forecast_skill_registry`. Lag 2 — `knowledge_fragments`, `calibration_versions`, mig 177-funksjoner. Lag 3 — `learning_proposals`, `epistemic_proposals`, CEO-DIR-2026-META-LEARNING-001. Lag 4 — IoS-012, `g5_paper_trades`, ADR-012.

**Hva som mangler per lag:** Lag 0 — dekning (5→106), D5, D6. Lag 1 — deflatert-Sharpe-port, holdout, kostmodell, tick-1161-rotårsak. Lag 2 — kalibreringskurver i drift, kilde-tillit, hypotese-kvalitet, adaptivt forfall. Lag 3 — VEGA-konvolutt for bounded auto-justering (krever direktiv). Lag 4 — QG-F6-terskler (LARS).

---

## 5. Sekvens — hvor vi begynner

Kvartaler er *rekkefølge med porter*, ikke løfter om datoer. Et kvartal åpner når forrige lag er verifisert, ikke når kalenderen sier det.

### Q4 2026 · LAG 0 — Sannhet før intelligens

Dette er «hvor vi begynner». Ingen unntak.

| Steg | Innhold | Port |
|---|---|---|
| 0.1 | **Lokal STIG-økt** på runtime-verten. Fase 0: `daemon_health` vs 106 filer vs 5 forvaltede → autoritativ liste over hva som *faktisk* kjører | Trippel-avstemming levert |
| 0.2 | **Repo = runtime.** 6 måneder lokal utvikling pushes. Ingen plan opererer på gammel kodebase | `git log` på runtime-verten = origin/master |
| 0.3 | **Merge-gate for `fd0328b6`** bekreftet i *hver* planlagt kontekst (Task Scheduler + crontab). Så merge | Null daemon-stopp etter merge, verifisert i `daemon_health` |
| 0.4 | **D6** — `guard_generation_freeze` fikset; 3 FINN-schedulere importerer | `py_compile` + heartbeat |
| 0.5 | **Kontrollplan 106/106.** Hver loop registrert, heartbeat fail-closed, eskalering definert. Det som ikke er i `daemon_health` kjører ikke | `SELECT count(*) FROM daemon_health` = antall levende loops |
| 0.6 | **Fabrikken:** tick-1161-rotårsak lukket av kjeden; V3_IMPLEMENTATION_RECEIPT; **evidenskvaliteten i dommene 994b6a83/9e73188e verifisert av FINN** — er de reelle dommer eller bare reelle kjøringer? | Kvittering + FINN-attest |

**Utgangsport Q4:** Alt som kjører er observert. Alt som feiler, feiler høyt. Fabrikken produserer reell evidens og noen har lest den.

### Q1 2027 · LAG 1 — Falsifikasjonsdisiplin

| Steg | Innhold |
|---|---|
| 1.1 | **Deflatert Sharpe ved admission (R3).** Hypotese-familier telles; kill-ledgeren blir nevner, ikke logg. Ingen RO passerer G7 uten korreksjon for antall forsøk i familien |
| 1.2 | **Holdout-protokoll.** Kronologisk ut-av-sample-vindu låst *før* formulering (PIT-semantikk fra DP3 utvides). Ingen dom uten holdout |
| 1.3 | **Kostmodell.** Spread, slippage, kapasitet inn i dommen. En kant som ikke overlever kostnader er ikke en kant |
| 1.4 | **LVI som styringsmål.** Tid-til-falsifikasjon per hypotese-familie, rapportert ukentlig via Proposal Engine |
| 1.5 | **Multi-generator-portefølje** (mig 346b) kjører under R3 — flere hypotesekilder, samme port |

**Utgangsport Q1:** Kill-rate er høy og *stabil* (de fleste ideer er feil — et system som dreper < 80 % lyver). Overlevere har deflatert Sharpe > LARS' terskel og ut-av-sample-forfall < in-sample.

### Q2 2027 · LAG 2 — Epistemikk

| Steg | Innhold |
|---|---|
| 2.1 | **Kalibreringskurver i drift.** Brier per konfidensbøtte fra `canonical_outcomes`, ukentlig. Overkonfidens > 10 pp → automatisk forslag |
| 2.2 | **Kilde-tillit.** Hver datakilde og LLM-modell scoret på historisk treffsikkerhet; tillit forfaller mot prior |
| 2.3 | **Hypotese-kvalitet per kategori × regime.** «Momentum i VOLATILE» får egen score; generatoren vektes av den |
| 2.4 | **Adaptivt forfall.** `decay_rate` = f(validitet, forsterkning) — ikke konstant |
| 2.5 | **Epistemisk usikkerhet.** Eksplisitt «kjente ukjente»-register: hvor har vi for lite data til å mene noe? |

**Utgangsport Q2:** Systemet kan svare «hvor sikker bør jeg være?» med tall som er testet mot utfall.

### Q3 2027 · LAG 3 — Meta-læring under governance

| Steg | Innhold |
|---|---|
| 3.1 | **VEGA-konvolutt.** Direktiv definerer hvilke parametre systemet kan justere *selv* innenfor grenser (f.eks. ±20 % av frosset verdi), og hvilke som alltid krever G3 |
| 3.2 | **Bounded auto-kalibrering.** Innenfor konvolutt: Proposal Engine → auto-apply → logg → VEGA ser etterpå. Utenfor: som i dag |
| 3.3 | **Ukentlig epistemisk rapport** til CEO: hva lærte vi, hva drepte vi, hva ble vi mer/mindre sikre på, hva foreslår systemet |

**Utgangsport Q3:** Læringsløkken lukker seg uten menneske i loopen for rutinejusteringer — og mennesket ser alt etterpå.

### Q4 2027 · LAG 4 — Kapital, gatet

| Steg | Innhold |
|---|---|
| 4.1 | ADR-012 QG-F6: terskler for LVI, ut-av-sample-Sharpe, kalibreringsfeil, kill-rate — **LARS setter tallene** |
| 4.2 | Paper → live kun for hypotese-familier som har passert alle porter i ≥ 2 kvartaler |
| 4.3 | Kapital-allokering proporsjonal med *deflatert* evidens, ikke rå Sharpe |

**Utgangsport Q4:** Første live-kapital under et system som kan bevise hvorfor.

---

## 6. Suksessmål som ikke kan spilles

M1 sier systemet lurer seg selv. Da må målene være *adversarielle* — de skal være vanskelige å forbedre uten å faktisk bli bedre.

| Mål | Hvorfor det ikke kan spilles | Finnes i dag? |
|---|---|---|
| **Syntetisk-rate = 0** | stdout-hash + veggtid-invariant; en syntetisk kjøring er *definert* ut | DP2 (i dag) |
| **Kill-rate ≥ 80 %** | Å senke den krever å la dårlige ideer overleve — synlig i ut-av-sample-forfall | kill-ledger |
| **Ut-av-sample / in-sample Sharpe ≥ 0,5** | Overtilpasning senker den mekanisk | mangler holdout |
| **Brier-score, trend nedover** | Kan bare forbedres ved bedre kalibrering | mig 177 |
| **LVI, trend oppover** | Måler *tid til falsifikasjon* — raskere læring, ikke mer aktivitet | `lvi_calculator` |
| **Kontrollplan-dekning = 100 %** | Binært; 5/106 er 4,7 % | `daemon_health` |
| **VEGA-avslagsrate ≥ X %** | En VEGA som aldri avslår reviewer ikke. LARS setter X | `learning_proposals` |
| **Repo-runtime-drift = 0 dager** | Målt av `git log` på verten | mangler |

---

## 7. Pre-mortem: fem måter dette feiler — og vakten mot hver

«Suksess før start» betyr å skrive obduksjonen først.

| # | Feilmåte | Hvordan det ser ut | Vakt |
|---|---|---|---|
| **F1** | **Fabrikken blir syntetisk igjen.** Ny kodesti, ny eksekutor, samme hull. | «Vellykkede» kjøringer med tom stdout, urealistisk veggtid | DP2 G-A…G-E som *harde* porter, ikke logg. Månedlig census: hver kjøring re-verifisert mot hash + tid. Dette er det ASTRID gjorde manuelt 04:15Z — det skal være en daemon |
| **F2** | **Multippel testing inflaterer.** 1 000 hypoteser, 50 «vinnere», alle støy. | Høy overlevelsesrate, lav ut-av-sample-persistens | Deflatert Sharpe ved R3. Kill-ledger som nevner. Kill-rate < 80 % → alarm, ikke feiring |
| **F3** | **Governance blir teater.** VEGA godkjenner alt; G-porter er formalitet. | Avslagsrate → 0 | VEGA-avslagsfloor (§ 6). Proposals som aldri avslås er evidens for at ingen leser dem |
| **F4** | **Kompleksitet løper fra observasjon.** 106 loops / 5 forvaltet — igjen. | Loops kjører som ingen kan gjøre rede for; feil oppdages uker etter | «Det som ikke er i `daemon_health` kjører ikke» — håndhevet, ikke ønsket. Fail-closed heartbeat (mig 346) for *alle*. Ny loop uten registrering = G1-avslag |
| **F5** | **Mennesket er flaskehalsen.** CEO godkjenner hver kalibrering; systemet venter. | Proposals utløper (14 d) uten review; læring stopper | Lag 3: VEGA-konvolutt for bounded auto. Direktiv-amendment (flagget i AELL-2026-001 § 6.3). Mennesket setter *grensene*, ikke hver verdi |

Og én til, fra i dag: **F6 — Repoet lyver om runtime.** 6 måneders drift betyr at enhver analyse fra repoet er historisk. Vakt: push-disiplin målt (§ 6), og STIG kjører *på* verten, ikke i skyen.

---

## 8. Beslutninger som er LARS' / CEOs — ikke STIGs

Jeg tegner hvordan. Dette er hva.

| Beslutning | Hvorfor den ikke er teknisk |
|---|---|
| Univers og markeder (kun US-aksjer? krypto? FX? opsjoner — mig 350 finnes) | Risikoappetitt og strategi |
| t-verdi-hinder / deflatert-Sharpe-terskel ved admission | Avveining falske positive vs. falske negative er en *verdi*, ikke et faktum |
| Kill-rate-floor, VEGA-avslags-floor | Hvor paranoid systemet skal være |
| QG-F6-terskler for kapital | Kapital er CEOs |
| VEGA-konvolutten: hva systemet får justere selv | Governance-filosofi; krever direktiv |
| Hvilke hypotese-familier som prioriteres | Forskningsretning |
| Om `05_ORCHESTRATOR/` og 6 måneders lokal kode skal inn i master som-er eller kurateres | Eierskap til historikken |

---

## 9. I morgen — bokstavelig

1. **Åpne Claude Code lokalt** i `C:\fhq-market-system\vision-ios`. Det er den eneste handlingen som låser opp alt annet. Første kommando: `SELECT NOW() AT TIME ZONE 'Europe/Oslo'` — så runbooken kan få DAY-nummer.
2. **Fase 0-spørringene** (plandokument § 4): `daemon_health`, `orchestrator_cycles`, trippel-avstemming.
3. **Bekreft merge-gaten** i Task Scheduler *og* crontab. Merge `fd0328b6`. Se `daemon_health` i 24 timer.
4. **D6** — kortet ligger klart.
5. **FINN leser dommene 994b6a83 / 9e73188e.** Er det evidens, eller bare en kjøring? Det svaret er Q4s viktigste.

---

## 10. Hva denne planen ikke er

- **Ikke verifisert mot DB.** Sky-økten når ikke sannhetskilden. Lag 0 er nettopp å reparere det.
- **Ikke strategi.** § 8 er tomme felt inntil LARS fyller dem.
- **Ikke G4-godkjent.** Ingenting her er iverksatt.
- **Ikke en løfte om alfa.** Den lover ett: at når systemet sier det har funnet noe, kan det bevise at det prøvde å motbevise det først.

Det er det et transparent marked belønner. Ikke den som ser mest — den som lyver minst for seg selv.

---

**Referanser (kvalitative, sjekkbare):** Bailey, Borwein, López de Prado & Zhu — *The Probability of Backtest Overfitting* · Bailey & López de Prado (2014) — *The Deflated Sharpe Ratio* · Harvey, Liu & Zhu (2016) — *… and the Cross-Section of Expected Returns*, RFS · McLean & Pontiff (2016) — *Does Academic Research Destroy Stock Return Predictability?*, JF · Hou, Xue & Zhang (2020) — *Replicating Anomalies*, RFS · López de Prado (2018) — *Advances in Financial Machine Learning* · Tetlock & Gardner (2015) — *Superforecasting* (kalibrering).
