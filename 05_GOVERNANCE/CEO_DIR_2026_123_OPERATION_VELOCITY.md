# CEO-DIR-2026-123: Operation Velocity

**TIL:** STIG (Technical Authority)
**FRA:** CEO / FjordHQ Executive Office
**DATO:** 22. januar 2026
**TEMA:** Etablering av Epistemisk Sandkasse og Akselerert Læringssløyfe
**KLASSIFIKASJON:** STRATEGISK DIREKTIV

---

## Executive Summary

Dette direktivet etablerer en arkitektonisk separasjon mellom **Kanonisk Sannhet** (Truth) og **Epistemisk Læring** (Learning) for å akselerere FjordHQs evne til å handle på innsikt før markedet korrigerer seg.

**Kjerneproblem:** Vi har bygget et institutt for evig sannhet, men glemt laboratoriet for hurtig læring. I et 2026-marked preget av skjøre overganger og geopolitisk multipolaritet er stillstand den største systemrisikoen.

**Løsning:** Etabler `fhq_learning` schema som epistemisk sandkasse der feil er tillatt, forutsatt logging og Brier-måling.

---

## Makro-kontekst (Verdensbankens Januar 2026-rapport)

| Faktor | Implikasjon for FjordHQ |
|--------|-------------------------|
| Global vekst 2.4% | Lavvekst krever evne til å fange små regimeendringer |
| Tariff-eskalering | Krever rask "hva-hvis"-eksperimentering |
| Høye realrenter | Støyete likviditetsmønstre krever epistemisk fleksibilitet |

**Konklusjon:** Å vente på 100% konsensus i dette markedet betyr å måle historien i stedet for å handle i nåtiden.

---

## Arkitekturen

```
┌─────────────────────────────────────────────────────────────┐
│                    FjordHQ Data Layer                        │
├─────────────────────────────┬───────────────────────────────┤
│   CANONICAL TRUTH           │   EPISTEMIC LEARNING          │
│   (fhq_governance, etc.)    │   (fhq_learning)              │
├─────────────────────────────┼───────────────────────────────┤
│ • Strenge ADR-013 krav      │ • Feil er tillatt             │
│ • PnL, ADR-er, beslutninger │ • Logges og måles via Brier   │
│ • Endelige avgjørelser      │ • Knowledge Velocity > Safety │
│ • IoS-006 validert          │ • REVERSIBLE & EXPERIMENTAL   │
└─────────────────────────────┴───────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │ CANONICAL FIREWALL │
                    │ (IoS-006 Required) │
                    └───────────────────┘
```

---

## Mandat

### 1. Etablering av `fhq_learning` Schema

**Krav:** Opprett umiddelbart et separat lag for "Epistemiske Eksperimenter".

**Egenskaper:**
- Data anses som reversible og eksperimentelle
- Læring skal ikke blokkeres av manglende konsensus
- All aktivitet logges i `fhq_learning.audit_log`

**Tabeller opprettet:**
- `fhq_learning.canonical_firewall` - DEN HELLIGE BESKYTTELSEN
- `fhq_learning.experiment_registry` - Eksperiment-registrering
- `fhq_learning.puu_decision_log` - PUU-beslutningslogg
- `fhq_learning.brier_permission_thresholds` - Brier-tillatelsesnivåer
- `fhq_learning.hindsight_comparison_log` - Hindsight-prosessor output
- `fhq_learning.knowledge_velocity_log` - KVI-måling

### 2. Canonical Firewall (DEN HELLIGE REGELEN)

> **"Data i fhq_learning er per definisjon epistemisk og kan aldri, direkte eller indirekte, promotere seg selv til canonical truth uten eksplisitt IoS-006 validering."**

**Implementering:**
```sql
CREATE TABLE fhq_learning.canonical_firewall (
    firewall_rule TEXT NOT NULL,
    ios_006_validation_required BOOLEAN NOT NULL DEFAULT TRUE,
    auto_promotion_blocked BOOLEAN NOT NULL DEFAULT TRUE
);
```

**Rasjonale:** Dette avvæpner STIGs instinktive frykt. Han beskytter ikke sannheten mindre – han beskytter den bedre, fordi læring nå skjer utenfor.

### 3. Proceed-under-Uncertainty (PUU) Flagg

**Krav:** Innfør PUU-flagg i alle beslutningskjeder under G1-G2 nivå.

**Tillater:**
- Agenter kan gå videre til SHADOW/PAPER handling selv ved uenighet
- Uenighet logges som "Eksperimentelt Avvik"
- Canonical action forblir BLOKKERT

**Konfigurasjonsparametre:**
| Parameter | Verdi | Beskrivelse |
|-----------|-------|-------------|
| `puu_max_gate_level` | G2 | Maks nivå for PUU |
| `puu_min_confidence_for_shadow` | 0.60 | Minimum for SHADOW |
| `puu_min_confidence_for_paper` | 0.75 | Minimum for PAPER |

### 4. Brier-Score som Tillatelseslag

**CEO-mandat:** Ved Brier-score $B < 0.15$ for strategisk signifikans, auto-eskaler tillitsnivå.

**Stabilitetskrav (CEO-tillegg):**
- Beregnet over minimumsvindu $N \geq 30$ observasjoner
- Stabilitet i begge haler påkrevd
- Stabilitetsvindu: 14 dager

**Tillatelsesnivåer:**
| Terskel | Brier < | Min N | Tillatelse | Auto-eskalering | Eksponering |
|---------|---------|-------|------------|-----------------|-------------|
| EXCELLENT | 0.10 | 50 | LIVE_ELIGIBLE | JA | 2.00x |
| STRATEGIC | 0.15 | 30 | PAPER_TRADING | JA | 1.50x |
| GOOD | 0.20 | 25 | SHADOW_TRADING | NEI | 1.25x |
| ACCEPTABLE | 0.30 | 20 | OBSERVE_ONLY | NEI | 1.00x |
| POOR | 0.50 | 10 | OBSERVE_ONLY | NEI | 0.50x |

### 5. Hindsight-prosessor

**Krav:** Sammenligner `fhq_learning`-resultater med faktiske markedsutfall hver 24. time.

**Dataflyt:**
```
fhq_learning.experiment_registry
            │
            ▼
fhq_learning.hindsight_comparison_log
            │
            ▼
    FINN Research Model (fhq_finn)
```

**Mating tilbake:**
- Brier-score beregnes retrospektivt
- Feedback sendes til FINN for modellkalibrering
- Knowledge Velocity Index (KVI) oppdateres

---

## Slutt-mål

> **"Vi skal ikke bare huske det vi har lært; vi skal handle på det før markedet har rukket å korrigere seg."**

---

## Implementeringsstatus

| Komponent | Status | Fil |
|-----------|--------|-----|
| Schema definisjon | READY | `migrations/CEO_DIR_2026_123_OPERATION_VELOCITY.sql` |
| Canonical Firewall | READY | Inkludert i migrasjon |
| PUU Infrastruktur | READY | Inkludert i migrasjon |
| Brier Tillatelser | READY | Inkludert i migrasjon |
| Hindsight Prosessor | READY | Inkludert i migrasjon |
| KVI Tracking | READY | Inkludert i migrasjon |

**Neste steg:** Kjør migrasjonen mot PostgreSQL.

---

## Risikovurdering

| Risiko | Mitigering |
|--------|-----------|
| Epistemisk data lekker til canonical | Canonical Firewall med IoS-006 krav |
| False confidence bursts | Min N=30 observasjoner + halestabilitet |
| Agentforvirring | Klart separert schema + audit logging |
| Overeksponering i learning | Max exposure multiplier caps |

---

## Verifiseringskriterier

- [ ] `fhq_learning` schema opprettet
- [ ] `canonical_firewall` tabell inneholder den hellige regelen
- [ ] `brier_permission_thresholds` har alle 5 nivåer
- [ ] `puu_config` har alle konfigurasjonsnøkler
- [ ] Audit triggers er aktive
- [ ] Hindsight processor config eksisterer

---

## Meta-refleksjon

> *"Du har rett i din observasjon av deg selv: Du bygger som et institutt, men du er en gründer. Instituttet vil ha sikkerhet; gründeren vil ha frihet."*

Ved å gi STIG dette direktivet, flytter vi ansvaret for "perfeksjon" fra handlingen over til loggføringen. **Vi gjør feilene billige, slik at lærdommen kan bli uvurderlig.**

---

**Direktivstatus:** ISSUED
**Utstedelsesdato:** 2026-01-22
**Utstedt av:** CEO / FjordHQ Executive Office
**Teknisk ansvarlig:** STIG (EC-003)

---

*"Learning is now explicitly non-threatening to Canonical Truth."*
