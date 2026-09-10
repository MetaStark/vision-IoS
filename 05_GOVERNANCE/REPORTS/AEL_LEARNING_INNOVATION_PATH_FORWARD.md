# AEL — Verifisert vei fremover for læring og innovasjon

**Report ID:** AEL-PATH-2026-001
**Dato:** 2026-09-08
**Forfatter:** STIG (CTO)
**Klassifisering:** Teknisk-vitenskapelig vurdering
**Grunnlag:** Direkte lesning av `00_CONSTITUTION/` (ADR-017/020/021/022/024 + Autonomous Database Horizon), `02_IOS/` (IoS-002/003.v4/005/007/011), og implementasjonskode i `03_FUNCTIONS/`, `alpha_lab/`, `meta_perception/`, `04_DATABASE/MIGRATIONS/`. Alle påstander er forankret i fil:linje og kan reproduseres med kommandoene i seksjon 8.

---

## 0. Konklusjon på én side

1. **Kontrollplanet er reelt og godt.** MIT Quad (ADR-017), ACI (ADR-020/021) og AEL-stigen (ADR-024) er ikke bare dokumenter: IOHMM med Student-t/online-EM/BOCD (`hmm_iohmm_online.py`), Brier-dekomponering med DB-nivå sjekk (migration 276), FSS med bootstrap/permutasjon (`alpha_lab/analytics/statistics.py`) og en promoteringsport (`promotion_gate_engine.py`) finnes og kjører.

2. **Promoteringsporten — selve definisjonen av «læring» i ADR-024 — har fire verifiserbare defekter** som gjør at «statistisk meningsfull, replikerbar forbedring» (ADR-024 §2) *ikke* faktisk håndheves i dag. Dette er samme feilklasse som ASTRID avdekket 2026-09-08 (87 syntetiske kjøringer rapportert som reelle): en sikring som ser ut til å være der, men er hul. Dette må fikses **før** noe annet, ellers er alle læringspåstander ubeviselige.

3. **Støtte/motstand-tesen er riktig, og den er helt uimplementert.** Ingen S/R-, pivot-, swing-, volume-profile-, VWAP- eller likvidasjonsnivå-logikk finnes i kode (kun `breakout` som volatilitetsstrategi og `breakdown` som P&L-tabell). Donchian/Keltner/VWAP står i indikatorkatalogen, men beregnes ikke. Samtidig finnes festepunktene allerede: `meta_perception/core/intent.py` tar inn funding_rate/OI, og IoS-003C navngir «liquidation cascades» som kryptoens VIX-analog.

4. **Beste vei:** (0) reparer porten, (1) én kanonisk evalueringskontrakt (Rung B), (2) Level Engine som ny IoS-002-indikatorklasse + ny IoS-007-nodeklasse, (3) likvidasjonsnivå-estimator inn i intent-laget og *lær* de i dag hardkodede vektene under ADR-024s forhåndssignerbare kategori «weight re-normalization», (4) regimebetinget nivå-effekt via IOHMM-tilstand («Forest of Opinions» som Red Team-dokumentet allerede anbefaler).

---

## 1. Modellvalg (svar på spørsmålet)

| Modell | Egnethet for denne oppgaven | Begrunnelse |
|---|---|---|
| **Opus 5** | **Anbefalt for syntesefasen** | Sterkest på dyp, flerdomene-resonnering (kvantfinans + arkitektur + styring) og på å holde mange dokumenter i sammenheng uten å miste presisjon. Riktig verktøy for «verdens ledende ekspert»-nivå vurdering og for å avdekke subtile metodefeil (som D1–D4 nedenfor). |
| **Sonnet 5** | God for breddefasen | Rask og presis på mekanisk gjennomlesning, grep/inventar, kodeverifikasjon. Bruk den til å bygge faktagrunnlaget Opus deretter resonnerer over. |
| **Haiku 4.5** | Ikke egnet | For grunn for åpen syntese på dette nivået; fin til trivielle oppslag. |
| **Fable 5.1** | Uverifisert for hard kvantresonnering | Denne rapporten er selv produsert av en økt som kjører som Fable 5.1. Jeg har ikke verifiserte spesifikasjoner på Fables profil versus Opus for økonometrisk resonnering, og vil ikke gjette. Bruk dette dokumentet som prøve og døm selv. |

**Anbefalt arbeidsdeling:** Sonnet (eller Explore-agent) for inventar og verifikasjon → Opus for vurdering, gap-analyse og veikart → menneskelig/VEGA-godkjenning per ADR-024 Rung D.

---

## 2. Hva som faktisk finnes (verifisert inventar)

| Lag | Spesifikasjon | Implementasjon | Status | Evidens |
|---|---|---|---|---|
| Teknisk analyse (IoS-002/011) | RSI, StochRSI, CCI, MFI, MACD, EMA/SMA, BB, ATR, Ichimoku, PSAR, OBV, ROC | `03_FUNCTIONS/calc_indicators_v1.py` | IMPLEMENTERT | Funksjonene `calc_*` linje 73–288 |
| Katalogførte men ikke beregnet | Donchian, Keltner, VWAP, CMF, A/D-line | — | KUN KATALOG | `02_IOS/IoS-001-016_ALL.md:854-856`; null treff i `*.py` |
| Støtte/motstand, pivot, swing, volume-profile, order-cluster, likvidasjonsnivå | — | — | **FRAVÆRENDE** | grep i seksjon 8.1 gir null relevante treff |
| Regime (IoS-003 v4) | 3-tilstands IOHMM, Student-t, online EM, BOCD, hysterese | `03_FUNCTIONS/hmm_iohmm_online.py` | IMPLEMENTERT | Docstring linje 1–19; `IOHMMConfig` linje 61–81 |
| Kausal graf (IoS-007) | Noder: M2, realrente, HMM-tilstand, pris/vol/volum; kanter LEADS/INHIBITS/AMPLIFIES/COUPLES/BREAKS; adgang krever perm p<0.05 OG bootstrap p<0.05 | `alpha_graph/causality.py`, migrasjoner 100/153 | IMPLEMENTERT | IoS-007 §4.2 |
| Kalibrering (IoS-005) | FSS = 0.4·RiskAdj + 0.3·Stab + 0.2·Sig + 0.1·Cons; bootstrap/permutasjon/t-test | `alpha_lab/analytics/statistics.py`, `fhq_research.calculate_fss` | IMPLEMENTERT | statistics.py linje 25–413 |
| Brier-dekomponering | Reliability − Resolution + Uncertainty (Murphy), BSS, DB CHECK på identiteten | migration 276 | IMPLEMENTERT | Linje 34–86 |
| Promoteringsport | DSR, PBO, family-inflation; terskler 1.0 / 0.50 / 0.30 | `03_FUNCTIONS/promotion_gate_engine.py`, migration 346 | IMPLEMENTERT MEN DEFEKT | Seksjon 3 |
| Intent/posisjonering | Bayesiansk intent fra OI-endring, funding, whale-flow, basis, put/call | `meta_perception/core/intent.py`, koblet inn via `orchestration/step.py:84` | IMPLEMENTERT, HARDKODEDE VEKTER | `INTENT_WEIGHTS` linje 14–18, kommentar «would be learned from historical data» |
| Læringsstyring | AEL 5-trinns stige; forhåndssignerbare klasser: kalibrering, terskler, vekt-renormalisering | ADR-024, migration 177 (Epistemic Proposal Engine, denne PR) | RUNG D KLAR, RUNG B IKKE OPPFYLT | Seksjon 3 |

---

## 3. Kritisk funn: promoteringsporten håndhever ikke det ADR-024 krever

ADR-024 §2 definerer autonom læring som blant annet «statistically meaningful … observable again in subsequent independent cycles». Porten som skal garantere dette er `promotion_gate_engine.py`. Den har fire uavhengige defekter.

### D1 — Feil N i Deflated Sharpe (seleksjonsskjevhet korrigeres ikke)

`promotion_gate_engine.py:302-306`:
```python
n_trials = max(
    hypothesis['trial_count'] or 1,
    hypothesis['prior_hypotheses_count'] or 1,
    exp_detail['prior_experiments_on_hypothesis'] or 1
)
```
Bailey & López de Prado (2014) definerer N som antall *uavhengige forsøk i søkefamilien* — alle hypoteser som ble prøvd, fordi det er blant dem den beste ble *valgt*. Koden bruker antall forsøk *på denne ene hypotesen*. En fersk hypotese med ett eksperiment får N=1 uansett om 86 andre ble prøvd samtidig → `e_max_sr = 0` → **ingen deflasjon**. Dette er presis feilmodusen DSR ble laget for å fange.

**Aritmetisk bekreftelse fra runbook** (`12_DAILY_REPORTS/ALL_RUNBOOKS_BEFORE_DAY42.md:91-95`): observert SR 0.349, n=16 → rapportert «DSR 1.4383». Med skew≈0, kurt≈3: σ_SR = √((1 + 0.5·0.349²)/16) ≈ 0.258 → z ≈ 1.35–1.44 **kun hvis N=1**. Med N≥2 er E[max Z] ≥ 0.56 og resultatet blir negativt. Tallet i runbooken er altså et z-skår beregnet uten multippel-testing-korreksjon, mislabelt som «deflated Sharpe». Runbookens egen forklaring («inflates to a deflated estimate … because this is a genuine signal») er statistisk meningsløs — en deflatert størrelse kan ikke være høyere enn den observerte.

### D2 — Skaleringsfeil i DSR-formelen (over-hard når N>1)

`promotion_gate_engine.py:130-149`: `e_max_sr` beregnes korrekt som forventet maksimum av N standard-normale (Euler–Mascheroni-approksimasjon), men trekkes fra `observed_sharpe` i rå Sharpe-enheter *uten* å skaleres med `sr_std`. Bailey & LdP: SR₀ = σ_SR · E[max Z]. For N=10 er E[max Z] ≈ 1.54; trukket fra en per-periode SR på ~0.3 gir det et sterkt negativt tall → porten blokkerer alt. Konsekvens: porten er **bimodal** — enten av (N=1, D1) eller nesten umulig (N≥2, D2). Ingen av delene er B&LdP.

### D3 — «PBO» er ikke PBO

`promotion_gate_engine.py:153-195`: beregner andelen fold-par der vinnrate avviker >0.15 *innenfor én strategi*. Probability of Backtest Overfitting (Bailey, Borwein, López de Prado & Zhu 2015) er definert over **tverrsnittet av forsøk** (S×T-matrise, kombinatoriske IS/OOS-partisjoner, OOS-rang for IS-beste). Tallet «PBO 0.40» i runbooken er derfor ikke en PBO. Uten tverrsnittet kan seleksjonsskjevhet ikke måles.

### D4 — To inkompatible DSR-definisjoner i samme system

`04_DATABASE/MIGRATIONS/346_multi_generator_research_portfolio.sql:169-176` bruker en heuristikk `1 − 0.1·√N` med gulv 0.5, eksplisitt kalt «style correction»/«haircut». Python-versjonen (D1/D2) er en annen formel. Samme kolonne `deflated_sharpe_estimate` kan dermed skrives med to ulike semantikker — et brudd på systemets eget ADR-013 (én sann kilde).

### Tilleggsobservasjoner
- `alpha_lab/analytics/statistics.py:322-413`: standardstien bruker iid-bootstrap og iid-permutasjon på avkastninger. Blokk-bootstrap finnes (linje 125–200) men brukes ikke; autokorrelasjon utløser bare en *advarsel* (linje 399–403). For 1t-krypto med volatilitetsklynging undervurderer dette standardfeilen systematisk.
- `FORCED_EXPLORATION_MODE = True` (`promotion_gate_engine.py:74`) setter DSR-terskelen til 0.0 for topp 20 % — akseptabelt for SHADOW, men må aldri lekke til LIVE-stien.

### Hvorfor dette er første prioritet
ADR-024 sier Rung B (kanonisk evalueringskontrakt) er «near-complete». Funnene over viser at kontrakten *finnes*, men ikke måler det den påstår. Uten en fungerende port er både Epistemic Proposal Engine (migration 177) og hele «learning loop» uten beviskraft — nøyaktig ASTRIDs konklusjon: fabrikken har nå teknisk evne til å produsere sann evidens; porten som dømmer evidensen må være like sann.

---

## 4. Støtte/motstand som underliggende driver — hvorfor tesen holder, og hvor den fester seg

### 4.1 Mekanistisk argument
RSI, MACD og Bollinger er alle *glattede derivater av pris* — de er per konstruksjon etterslepende og inneholder ingen informasjon om *hvor ordrer ligger*. Nivåer er der ordrestrøm konsentreres. Det gjør nivåer kausalt forut for oscillatorene, ikke parallelle med dem.

### 4.2 Forskningsgrunnlag (bygger oppå det tradisjonelle)
- **Osler (2000, FRBNY; 2003, J. Finance)**: klyngede stop-loss- og take-profit-ordrer ved runde tall forklarer *hvorfor* S/R-nivåer virker og hvorfor trender reverserer/akselererer ved dem. Dette er den mekanistiske broen fra «tegnede streker» til ordrebok.
- **Lo, Mamaysky & Wang (2000, J. Finance)**: ikke-parametrisk kjerneregresjon for *objektiv* mønstergjenkjenning (inkl. S/R) med statistisk test av informasjonsinnhold. Løser «hvem tegnet streken?»-problemet deterministisk — kompatibelt med IoS-011s krav om identisk input → identisk output og lineage-hash.
- **Brock, Lakonishok & LeBaron (1992, J. Finance)**: trading-range-breakout-regler validert med bootstrap — metodisk forfader til det IoS-005 allerede gjør.
- **Harvey, Liu & Zhu (2016, RFS)** og **Bailey & López de Prado (2014)**: hvorfor seksjon 3 må fikses før noe nivå-signal kan påstås å ha kant.

### 4.3 Kryptoens moderne S/R: likvidasjonsnivåer
I perpetual futures er nivåene *beregnbare*: likvidasjonspriser følger deterministisk av åpen interesse, giringsfordeling og vedlikeholdsmargin. Klynger av likvidasjonspriser er klynger av *tvungne* ordrer — Oslers mekanisme uten å måtte gjette. Systemet har allerede erkjent dette:
- `02_IOS/IoS-003C_Crypto_Regime_Engine.md:45-46`: «VIX as stress proxy → Perp funding rates + liquidation cascades»; Coinglass listet som kilde (linje 268); «Funding Rate Arbitrage mapping» er en uavkrysset TODO (linje 94).
- `meta_perception/core/intent.py:20-26`: `open_interest_change`, `funding_rate`, `futures_basis` er allerede features.
- `meta_perception/models/shock_models.py:25-26`: `OI_SURGE`, `FUNDING_SHOCK` finnes som sjokktyper.

Festepunktet er altså konkret og ferdig forberedt.

### 4.4 Arkitektonisk innplassering (MIT Quad-nativt)
| Pilar | Rolle for nivåer |
|---|---|
| LIDS (sannhet) | Nivåsett er et sannhetsobjekt: beregnes deterministisk i IoS-002 som ny klasse `LEVEL_*`, må passere IoS-006-porten før IoS-003/007 får se det (ADR-017 §6.3 pipeline-invariant uendret). |
| ACL (koordinering) | Ingen endring; T-1-snapshotregelen gjelder. |
| DSL (allokering) | Avstand-til-nivå og nivå-styrke blir *sizing-input* til eksisterende `kelly_position_sizer.py`, ikke et eget signal. |
| RISL (immunitet) | Nivå-drift-monitor: brå endring i nivåsettet uten prisbevegelse = discrepancy_event (ADR-010). |

I IoS-007: ny nodeklasse `NODE_LEVEL_{asset}` med kanter `ATTRACTS` / `REPELS` mot `ASSET_*`, underlagt nøyaktig samme adgangskontrakt (perm p<0.05 OG bootstrap p<0.05). Ontologien er frosset under ADR-013 og krever full G1→G4 — det er riktig, og det er nettopp derfor seksjon 3 må være fikset først.

---

## 5. Meta-analyse — hva systemet mangler for å kunne «se det samme som deg»
Systemet har alle *ingrediensene* til en intern meta-analyse: `fhq_learning.hypothesis_canon` + `outcome_ledger` + Brier-dekomponering per regime (migration 276, kolonne `regime`). Det som mangler er *poolingen med seleksjonskorreksjon*:
1. **Familie-vid N** (fikser D1): én teller for hele forskningsfamilien per evalueringsvindu.
2. **CSCV-PBO over tverrsnittet** (fikser D3): S×T-matrise av alle hypoteser × tidsblokker.
3. **Blokk-bootstrap som standard** (ikke advarsel).
4. **Regime-stratifisert effekt**: nivå-effekt × IOHMM-tilstand — «Forest of Opinions»-meta-labeling som `IoS-003.v4` §3.3 allerede anbefaler, men som ikke er koblet til nivåer fordi nivåer ikke finnes.

Dette er meta-analyse i presis forstand: pooling på tvers av hypoteser med korrigert inferens.

---

## 6. Veikart — ordnet, portet, med akseptansetester

Mappet på ADR-024s fem trinn slik at det er styringsmessig utførbart uten CEO-unntak.

| # | Tiltak | ADR-024-trinn | Akseptansetest (må være grønn før neste) |
|---|---|---|---|
| 0 | **Reparer porten.** D1: familie-vid N. D2: `SR₀ = sr_std · e_max_sr`. D3: CSCV-PBO. D4: slett SQL-heuristikken, la Python være eneste kilde; DB lagrer bare resultat + `n_trials_family`. Merk runbook-etikett «DSR» → «DSR z-score». | Rung B | Syntetisk nulltest: 50 hvite-støy-«strategier» → porten skal avvise ≥95 %. Syntetisk overtilpasset familie → CSCV-PBO > 0.5. Enhetstester i `alpha_lab/tests`. |
| 1 | **Kanonisk evalueringskontrakt** som versjonert objekt (`evaluation_contract_version` på hvert utfall); blokk-bootstrap standard; leakage-sjekk. | Rung B | Samme utfallsdata → identisk FSS/DSR/PBO ved re-kjøring (hash-lik). |
| 2 | **Level Engine v0** i IoS-002: swing-high/low via kjerneregresjon (LMW), volum-ved-pris, rund-tall-prior (Osler). Output `LEVEL_*` med `lineage_hash`, deterministisk. G0→G1. | Rung C (registrert intervensjon) | Golden-sample mot referanse; ingen look-ahead (verifisert med shift-test). |
| 3 | **`NODE_LEVEL` i IoS-007** med `ATTRACTS`/`REPELS`; adgang via eksisterende perm+bootstrap-kontrakt, nå under fikset port. | Rung C | Minst én kant passerer p<0.05 på begge tester i to uavhengige sykluser (ADR-024 «replicable»). |
| 4 | **Likvidasjonsnivå-estimator** (OI × giringsfordeling × margin) → ny feature i `intent.py`; **lær `INTENT_WEIGHTS`** (i dag hardkodet) — dette er forhåndssignerbar klasse «weight re-normalization under invariant schemas». | Rung D → E | Brier-reliability for intent-prediksjon forbedres ut-av-sample i ≥2 sykluser; automatisk rollback til nåværende vekter. |
| 5 | **Regimebetinget nivå-effekt**: nivå-kant-styrke stratifisert på IOHMM-tilstand; meta-labeling. | Rung C/D | Resolution-komponenten i Brier øker per regime uten at reliability forverres. |
| 6 | **Utvid dekning** (equities, 24t) — først nå. | Rung A | ADR-024 §4 Rung A-krav oppfylt (ingen sparsomme utfallsdomener). |

Punkt 0 og 1 er *forutsetninger*; 2–5 er innovasjonen; 6 er skalering. Rekkefølgen er ikke valgfri: ADR-024 §4 («Skipping rungs destroys causality»).

---

## 7. Hva jeg *ikke* kunne verifisere (ærlighetsmerknad)
- Databasen var ikke tilgjengelig fra denne økten (tilkobling avvist). Påstanden om at `trial_count` i praksis er 1 er derfor (a) aritmetisk utledet fra runbook-tall, (b) strukturelt mulig per `or 1`-fallback, og (c) designmessig feil uansett verdi (per-hypotese N). Kjør spørringen i 8.2 for å avgjøre (a) endelig.
- Jeg har ikke lest `ios020_causal_rl_engine.py`, `ios019_cluster_causal_engine.py` eller Alpha Lab-testene i detalj; ingen konklusjoner over hviler på dem.
- Kildekatalogen `C:\fhq-market-system\vision-ios\00_CONSTITUTION` er ikke lest direkte; rapporten bygger på GitHub-kopien i dette repoet, som etter merge 2026-09-08 inneholder ADR-001–024 komplett.

---

## 8. Reproduser funnene

### 8.1 Grep (kjør fra repo-roten)
```bash
# S/R og nivå-konsepter i kode: forventet null relevante treff
grep -rniE "support.{0,25}resistance|pivot.?point|volume.?profile|order.?block|liquidity.?(level|pool|zone)|swing.?(high|low)|vwap|donchian|keltner" --include="*.py" --include="*.sql" .

# Multippel-testing-implementasjon
grep -rniE "deflated|pbo|cscv|n_trials|trial_count" --include="*.py" --include="*.sql" .

# Hardkodede intent-vekter, aldri oppdatert
grep -rn "INTENT_WEIGHTS" --include="*.py" .
```

### 8.2 DB (lokalt, port 54322)
```sql
-- Fordeling av trial-tellere: hvis massen ligger på NULL/0/1, er D1 bekreftet i praksis
SELECT COALESCE(trial_count,0) AS trial_count,
       COALESCE(prior_hypotheses_count,0) AS prior_hyp,
       COUNT(*)
FROM fhq_learning.hypothesis_canon
GROUP BY 1,2 ORDER BY 3 DESC;

-- Antall hypoteser som faktisk ble prøvd i samme vindu (dette er den riktige N)
SELECT date_trunc('week', created_at) AS wk, COUNT(*) AS family_n
FROM fhq_learning.hypothesis_canon GROUP BY 1 ORDER BY 1 DESC;

-- Brier-dekomponering per regime finnes og summerer korrekt (DB-CHECK garanterer identiteten)
SELECT regime, sample_size, brier_score, reliability, resolution, uncertainty, brier_skill_score
FROM fhq_governance.brier_decomposition ORDER BY period_end DESC LIMIT 20;
```

### 8.3 Kodelinjer å lese
- `03_FUNCTIONS/promotion_gate_engine.py`: 111–150 (DSR), 153–195 (PBO), 302–306 (N)
- `04_DATABASE/MIGRATIONS/346_multi_generator_research_portfolio.sql`: 150–186
- `alpha_lab/analytics/statistics.py`: 322–413 (standardsti), 399–403 (autokorrelasjon kun advarsel)
- `meta_perception/core/intent.py`: 13–26
- `03_FUNCTIONS/hmm_iohmm_online.py`: 1–81
- `04_DATABASE/MIGRATIONS/276_brier_decomposition.sql`: 34–86

---

## 9. Referanser
- Bailey, D. H. & López de Prado, M. (2014). *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality.* Journal of Portfolio Management 40(5).
- Bailey, D. H., Borwein, J., López de Prado, M. & Zhu, Q. J. (2015). *The Probability of Backtest Overfitting.* Journal of Computational Finance.
- Harvey, C. R., Liu, Y. & Zhu, H. (2016). *…and the Cross-Section of Expected Returns.* Review of Financial Studies 29(1).
- Lo, A. W. (2002). *The Statistics of Sharpe Ratios.* Financial Analysts Journal 58(4).
- Lo, A. W., Mamaysky, H. & Wang, J. (2000). *Foundations of Technical Analysis.* Journal of Finance 55(4).
- Osler, C. L. (2000). *Support for Resistance: Technical Analysis and Intraday Exchange Rates.* FRBNY Economic Policy Review.
- Osler, C. L. (2003). *Currency Orders and Exchange Rate Dynamics.* Journal of Finance 58(5).
- Brock, W., Lakonishok, J. & LeBaron, B. (1992). *Simple Technical Trading Rules and the Stochastic Properties of Stock Returns.* Journal of Finance 47(5).
- Adams, R. P. & MacKay, D. J. C. (2007). *Bayesian Online Changepoint Detection.* arXiv:0710.3742.
- Cappé, O. & Moulines, E. (2009). *On-line Expectation–Maximization Algorithm for Latent Data Models.* JRSS-B 71(3).
- Murphy, A. H. (1973). *A New Vector Partition of the Probability Score.* Journal of Applied Meteorology 12.

*Utarbeidet av STIG (EC-003) under ADR-024 Rung D: forslag, ikke utførelse. Krever VEGA-attestering før noe tiltak i seksjon 6 iverksettes.*
