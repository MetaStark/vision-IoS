---

**Document ID:** IoS-013-Perspective_2026.
**Title:** Cognitive Signal Weighting & Decision Context Engine
**Issued by:** FjordHQ Executive Architecture Office
**Version:** G0 (Draft for ADR-004 Review)
**Owner:** STIG (CTO), LARS (CSO), VEGA (Governance)
**Date:** 2026-01-21
**Governance Binding:** ADR-001, ADR-003, ADR-005, ADR-007, ADR-013, ADR-014, ADR-016, ADR-018
**Supersedes:** IoS-013.HCP-LAB (deprecated)

---

# ✨ Executive Summary

**IoS-013-Perspective** er FjordHQs offisielle komponent for å konvertere signaler til beslutningskraft. Den samler, vekter og forklarer sanntidsdata fra hele signalsystemet og skaper et kognitivt tolkningsgrunnlag som kan brukes av både autonome agenter og mennesker.

Dette er ikke en strategi. Det er *perspektivet* som avgjør hvilken strategi som skal få tillit.

IoS-013 utgjør siste steg i tolkningen av observasjoner før agentene tar handling, og fungerer som den semantiske broen mellom råsignaler og beslutningslogikk i IoS-008.

---

# ① Mission & Scope

## Formål

* Vekting av signaler etter semantisk, statistisk og regimebasert relevans
* Tverrmodulær kontekstbygging for felles beslutningsgrunnlag
* Produksjon av deterministiske, forklarbare beslutningspakker (context_weighted_signal_plan)

## Hva IoS-013 ikke er

* Ikke en signalgenerator (det gjøres i IoS-002, -006, -007)
* Ikke en prediktor (det gjøres i IoS-005)
* Ikke en strategiaktiverer (det gjøres i IoS-008 og IoS-015)

---

# ② Architecture & Inputs

## Kilder

* IoS-002: Tekniske indikatorer
* IoS-003: Regimeklassifisering
* IoS-005: Forecasts, Brier-score
* IoS-006: Makrofeatures
* IoS-007: Causal Alpha Graph (LEADS, INHIBITS, AMPLIFIES)
* IoS-010: Prediction Ledger
* IoS-016: Event proximity tags (EVENT_ADJACENT, etc)

## Kjernemodell

```python
context_weighted_signal_plan = {
    'asset_id': str,
    'regime_context': str,
    'raw_signals': List[Signal],
    'weighted_signals': List[WeightedSignal],
    'confidence_score': float,
    'explainability_trace': str,
    'semantic_conflicts': Optional[List[str]]
}
```

---

# ③ Weighting Methodology

## Faktorer for vekting

| Dimensjon       | Metode                              | Vekting       |
| --------------- | ----------------------------------- | ------------- |
| Regime-samsvar  | Regime vs signal-type alignment     | 0.2 - 1.0     |
| Forecast skill  | Brier score per signal-kilde        | 0.1 - 1.0     |
| Causal linkage  | Signalens posisjon i causal graph   | 0.3 - 1.2     |
| Redundansfilter | Cohesion score, multikilde-overlapp | -0.2 til -0.5 |
| Event proximity | EVENT_ADJACENT gir vekt-reduksjon   | -0.1 til -0.3 |

## Output

* `weighted_signal_strength` per signal
* `total_confidence_score` for hele asset×time beslutning
* `risk_flag` hvis signaler er motstridende

---

# ④ Integration Flow

## 1. Daglig flyt (Trigger: IoS-014)

* Samle signaler etter predefinert orkestreringsplan (IoS-014 DAG)
* Konverter til `context_weighted_signal_plan`
* Send til:

  * IoS-008 (Decision Engine)
  * EC-016 (VALKYRIE) som forklarende narrativ
  * UMA/IoS-015 som læringsobjekt (training event)

## 2. Logging

* Alle planer lagres i `fhq_signal_context.weighted_signal_plan`
* Kryptert signatur (Ed25519) og referanse til input-hash-kjede
* Alle avvik (f.eks. inkompatible signaler) loggføres i `signal_conflict_registry`

---

# ⑤ Feedback Loop & Læring

* IoS-016 brukes for å justere vekter post-event
* UMA refererer til `confidence_score` og senere PnL/Brier for edge-analyse
* Signals som konsekvent gir dårlig resultat nedvekteres fremtidig automatisk

## Kobling til LVI

LVI_i dag er justert med IoS-013 confidence-weight som vektingsfaktor i LVI-formelen:

```
LVI_adjusted = Σ(Forecast_success × Confidence_score × (1 - Event_proximity)) / T
```

---

# ⚖️ Governance

* G0 initiert 2026-01-21
* Krever G1-registrering i `fhq_meta.ios_registry`
* Krever ADR-004 G2 signering av LARS og VEGA
* All output er underlagt ADR-018 fail-closed og ADR-013 canonical lineage

---

# ✅ Success Criteria

| Metrikk                                                    | Mål |
| ---------------------------------------------------------- | --- |
| Samme signal gir lik confidence-score per regime           | ✔   |
| Alle beslutninger i IoS-008 er koblet til context_id       | ✔   |
| VALKYRIE får forklart narrativ fra samme signalplan        | ✔   |
| 14 dagers test viser konsistent vekting på tvers av DEFCON | ✔   |
| LVI forbedret med >= 0.03 etter aktivering                 | ✔   |

---

# 🔐 Signatur

IoS-013-Perspective er herved dokumentert og klar til G1-behandling som *den kognitive syntesen mellom datastrøm og beslutning*.

**FjordHQ Executive Architecture Office**
Dato: 2026-01-21
