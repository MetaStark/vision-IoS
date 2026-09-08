# FINN-E og FINN-T Undersøkelsesrapport

**Rapport ID:** FINN-E-T-INVESTIGATION-20260126
**Status:** FUNN BEKREFTET
**Utført av:** STIG (CTO)
**Dato:** 2026-01-26 10:45 CET
**Database verifisert:** PostgreSQL @ 127.0.0.1:54322

---

## Executive Summary

**ROTÅRSAK IDENTIFISERT:** FINN-E og FINN-T genererer ikke hypoteser fordi de **mangler daemon/scheduler-kode**. De ble kjørt manuelt én gang (23-24. januar) og har ikke blitt kjørt siden.

---

## Del 1: Fakta fra Database

### Generator Registry Status

| Generator | Status | Type | Siste Generering |
|-----------|--------|------|------------------|
| finn_crypto_scheduler | ACTIVE | WORLD_MODEL | 2026-01-26 10:37 (kontinuerlig) |
| FINN-E | ACTIVE | ERROR_REPAIR | 2026-01-24 22:36 (36+ timer siden) |
| FINN-T | ACTIVE | WORLD_MODEL | 2026-01-24 22:03 (36+ timer siden) |
| GN-S | ACTIVE | SHADOW_DISCOVERY | 2026-01-24 22:03 (36+ timer siden) |

### Hypotese-Generering per Generator

| Generator | Totalt | DRAFT | FALSIFIED | Første | Siste |
|-----------|--------|-------|-----------|--------|-------|
| finn_crypto_scheduler | 205 | 205 | 0 | 2026-01-25 18:14 | 2026-01-26 10:37 |
| FINN-E | 28 | 0 | 28 | 2026-01-23 21:39 | 2026-01-24 22:36 |
| FINN-T | 4 | 0 | 4 | 2026-01-24 22:03 | 2026-01-24 22:03 |
| GN-S | 2 | 2 | 0 | 2026-01-24 22:03 | 2026-01-24 22:03 |

### Input Data Tilgjengelig

| Generator | Input Source | Data Tilgjengelig |
|-----------|--------------|-------------------|
| FINN-E | error_classification_taxonomy | 100 HIGH priority errors (kun 3 konvertert til hypoteser) |
| FINN-T | fhq_macro.golden_features | 11 CANONICAL features (LIQUIDITY, CREDIT, FACTOR, VOLATILITY) |

---

## Del 2: Rotårsak-Analyse

### Primær Rotårsak: Manglende Scheduler/Daemon

**finn_crypto_scheduler.py** har komplett daemon-arkitektur:
- `while not self.shutdown_requested:` loop
- 30-minutters intervall
- Heartbeat oppdatering til `daemon_health`
- Signal handlers for graceful shutdown
- Registrert i Windows Task Scheduler via daemon_watchdog

**finn_t_world_model_generator.py** er kun et manuelt script:
```python
if __name__ == '__main__':
    result = run_generator()
    print(json.dumps(result, indent=2))
```
- Ingen daemon loop
- Ingen heartbeat
- Ingen kontinuerlig kjøring
- Må kjøres manuelt hver gang

**FINN-E generator eksisterer IKKE som kode:**
- Ingen `finn_e_error_repair_generator.py` fil funnet
- FINN-E hypoteser ble generert manuelt via andre mekanismer
- Origin type: `ERROR_DRIVEN` - trolig generert via learning feedback pipeline

### Sekundær Årsak: Migration 353 Aktiverte Kun Konfigurasjon

Migration `353_alpha_factory_activation.sql` oppdaterte kun:
- `generator_registry` med status=ACTIVE og rotation_config
- `pre_tier_validator_authority` med validatorer
- Views for throughput tracking

Migration 353 **OPPRETTET IKKE**:
- Scheduler-kode for FINN-E
- Scheduler-kode for FINN-T
- Windows Task Scheduler oppføringer

---

## Del 3: Daemon-Sammenligning

| Komponent | finn_crypto_scheduler | FINN-T | FINN-E |
|-----------|----------------------|--------|--------|
| Python daemon fil | finn_crypto_scheduler.py | finn_t_world_model_generator.py | MANGLER |
| Scheduler loop | JA | NEI | N/A |
| Heartbeat | JA (daemon_health) | NEI | N/A |
| 24/7 kjøring | JA | NEI | NEI |
| Task Scheduler | Via daemon_watchdog | NEI | NEI |
| Auto-restart | JA | NEI | NEI |

---

## Del 4: Konsekvens-Analyse

### G1.5 Calibration Experiment Impact

G1.5-eksperimentet krever:
- 30 hypothesis deaths med `pre_tier_score_at_birth` for Spearman-kalibrering
- Generator diversity for robust validering

**Nåværende status:**
- kun `finn_crypto_scheduler` genererer (100% av nye hypoteser)
- FINN-E og FINN-T bidrar IKKE til death accumulation
- Eksperimentet er avhengig av én enkelt generator

### Learning Velocity Impact

| Metrikk | Med alle 3 generatorer | Kun finn_crypto_scheduler |
|---------|------------------------|---------------------------|
| Diversity | HIGH | LOW (single source) |
| Error-driven learning | JA | NEI |
| Theory-driven learning | JA | NEI |
| Sample size growth | Optimal | Suboptimal |

---

## Del 5: Tekniske Funn

### Fil-Inventar

```
03_FUNCTIONS/
├── finn_brain_scheduler.py      # Signal execution (ikke hypotese-generering)
├── finn_cognitive_brain.py      # Trading strategies (ikke hypotese-generering)
├── finn_crypto_scheduler.py     # FUNGERER - 24/7 hypothesis generation
├── finn_t_world_model_generator.py  # Manuelt script (ingen scheduler)
└── [FINN-E generator]           # MANGLER HELT
```

### Database-Bevis

```sql
-- FINN-E og FINN-T stoppet generering 24. januar
SELECT generator_id, MAX(created_at) as last_generated
FROM fhq_learning.hypothesis_canon
WHERE generator_id IN ('FINN-E', 'FINN-T')
GROUP BY generator_id;

-- Resultat:
-- FINN-E: 2026-01-24 22:36:09 (36+ timer siden)
-- FINN-T: 2026-01-24 22:03:30 (36+ timer siden)
```

---

## Del 6: Anbefalt Løsning

### Prioritet 1: Implementer FINN-T Scheduler

Konverter `finn_t_world_model_generator.py` til daemon-format lik `finn_crypto_scheduler.py`:
1. Legg til `while not shutdown_requested:` loop
2. Implementer heartbeat til `daemon_health`
3. Legg til signal handlers
4. Registrer i daemon_watchdog

### Prioritet 2: Implementer FINN-E Generator

Opprett ny fil `finn_e_error_repair_generator.py`:
1. Fetch HIGH priority errors fra `error_classification_taxonomy`
2. Konverter errors med `hypothesis_generated = FALSE` til hypoteser
3. Implementer som daemon med heartbeat

### Prioritet 3: Registrer i Watchdog

Oppdater `daemon_watchdog.py` DAEMONS dict:
```python
'finn_t_scheduler': {
    'script': '03_FUNCTIONS/finn_t_scheduler.py',
    'max_stale_minutes': 35,
    'has_heartbeat': True
},
'finn_e_scheduler': {
    'script': '03_FUNCTIONS/finn_e_scheduler.py',
    'max_stale_minutes': 35,
    'has_heartbeat': True
}
```

---

## Del 7: Risiko-Vurdering

| Risiko | Sannsynlighet | Konsekvens | Mitigering |
|--------|---------------|------------|------------|
| G1.5 experiment skewed by single generator | HØY | MEDIUM | Implementer FINN-E/T schedulers |
| LOW diversity reduces learning quality | HØY | MEDIUM | Multi-generator activation |
| Error-driven learning dormant | HØY | HIGH | FINN-E implementation critical |

---

## Del 8: Konklusjon

**FINN-E og FINN-T genererer ikke fordi:**

1. **FINN-T**: Kode eksisterer som manuelt script, men mangler daemon/scheduler
2. **FINN-E**: Generator-kode eksisterer IKKE i det hele tatt
3. **Alpha Factory Migration (353)**: Aktiverte kun database-konfigurasjon, ikke kjørende kode
4. **Eneste aktive generator**: `finn_crypto_scheduler` (205 hypoteser, 100% av produksjonen)

**Nødvendig handling:**
- Implementer daemon-versjoner av FINN-E og FINN-T
- Registrer i daemon_watchdog for automatisk restart
- Verifiser G1.5-eksperimentet får multi-generator diversity

---

---

## Del 9: LØSNING IMPLEMENTERT

**Tidspunkt:** 2026-01-26 12:08 CET
**Status:** FIKSET

### Implementerte Filer

| Fil | Formål |
|-----|--------|
| `finn_t_scheduler.py` | FINN-T daemon med 60-min syklus |
| `finn_e_scheduler.py` | FINN-E daemon med 30-min syklus |
| `daemon_watchdog.py` | Oppdatert med 7 daemons |

### Verifisert Generering

| Generator | Før Fix | Etter Fix | Nye Hypoteser |
|-----------|---------|-----------|---------------|
| FINN-E | 28 | 30 | +2 |
| FINN-T | 4 | 5 | +1 |

### Daemon Health Status

```
finn_brain_scheduler:    HEALTHY (3.2 min ago)
finn_t_scheduler:        HEALTHY (3.4 min ago)  <- NY
finn_crypto_scheduler:   HEALTHY (3.4 min ago)
finn_e_scheduler:        HEALTHY (3.4 min ago)  <- NY
daemon_watchdog:         HEALTHY (0.4 min ago)
```

### Nye Hypoteser Generert

```
FINNT-CRE-20260126110500   | FINN-T | ECONOMIC_THEORY | CREDIT cluster
FINNE-ERR-DIR-20260126110459 | FINN-E | ERROR_DRIVEN | Direction error
FINNE-ERR-DIR-20260126110458 | FINN-E | ERROR_DRIVEN | Direction error
```

---

**Rapport Generert:** 2026-01-26 10:45 CET
**Løsning Implementert:** 2026-01-26 12:08 CET
**Verifisert mot:** PostgreSQL 17.6 @ 127.0.0.1:54322
**Status:** FIKSET - FINN-E og FINN-T genererer hypoteser
