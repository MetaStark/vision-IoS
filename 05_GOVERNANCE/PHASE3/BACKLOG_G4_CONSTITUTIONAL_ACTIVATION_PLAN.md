# FjordHQ IoS G4 Constitutional Activation Plan

**Document ID:** STIG-G4-CONSTITUTIONAL-PLAN-20251201
**Status:** IN PROGRESS - CP-1, CP-2, CP-4, CP-5 COMPLETE
**Authority:** CEO Mandate
**Prepared by:** STIG (CTO)
**Created:** 2025-12-01 23:00 CET
**Last Updated:** 2025-12-03 20:45 CET
**ADR Alignment:** ADR-004, ADR-012, ADR-013, ADR-016

---

## KRITISK ARKITEKTURPRINSIPP

```
G4 CONSTITUTIONAL ≠ LIVE TRADING

G4 = Konstitusjonell sertifisering (stabilitet, determinisme, audit)
LIVE = Separat autorisasjonslag (kapital, risiko, CEO+VEGA)
```

**CEO Korreksjon (2025-12-01):** Dokumentet skiller nå tydelig mellom G4 Constitutional og LIVE Authorization som to separate governance-linjer.

---

## KORREKT PRIORITERINGSREKKEFØLGE

| Prioritet | Modul(er) | Mål | Blokkerer |
|-----------|-----------|-----|-----------|
| **P0** | IoS-001→006 | G4 Constitutional | IoS-007, IoS-008 |
| **P1** | IoS-009, 010, 011 | G1→G3 | Fremtidige kapabiliteter |
| **P2** | IoS-008 | G4 Constitutional | IoS-012 Decision source |
| **P3** | IoS-012 | G4 Constitutional | Execution authority |
| **P4** | LIVE_AUTHORIZED | Separat flagg | Reell kapitaleksponering |

---

## NÅVÆRENDE IoS REGISTRY STATUS (Snapshot 2025-12-03)

| IoS | Title | Status | Governance | Immutability |
|-----|-------|--------|------------|--------------|
| IoS-001 | Canonical Asset & Context Registry | **G4_CONSTITUTIONAL** | G4_CONSTITUTIONAL | **FROZEN** |
| IoS-002 | Indicator Engine – Sensory Cortex | **G4_CONSTITUTIONAL** | G4_CONSTITUTIONAL | **FROZEN** |
| IoS-003 | Meta-Perception Engine (Market Brain) | **G4_CONSTITUTIONAL** | G4_CONSTITUTIONAL | **FROZEN** |
| IoS-004 | Regime-Driven Allocation Engine | **G4_CONSTITUTIONAL** | G4_CONSTITUTIONAL | **FROZEN** |
| IoS-005 | Forecast Calibration & Skill Engine | **G4_CONSTITUTIONAL** | G4_CONSTITUTIONAL | **FROZEN** |
| IoS-006 | Global Macro & Factor Integration | **G4_CONSTITUTIONAL** | G4_CONSTITUTIONAL | **FROZEN** |
| IoS-007 | Alpha Graph Engine - Causal Reasoning | ACTIVE | G4_CONSTITUTIONAL | G4_CONSTITUTIONAL |
| IoS-008 | Runtime Decision Engine | **G4_CONSTITUTIONAL** | G4_CONSTITUTIONAL | **FROZEN** |
| IoS-009 | Meta-Perception Layer | G0_SUBMITTED | G0_SUBMITTED | MUTABLE |
| IoS-010 | Prediction Ledger Engine | G0_SUBMITTED | G0_SUBMITTED | MUTABLE |
| IoS-011 | Technical Analysis Pipeline | G0_SUBMITTED | G0_SUBMITTED | MUTABLE |
| IoS-012 | Execution Engine | **G4_CONSTITUTIONAL** | **G4_CONSTITUTIONAL_FULL** | **FROZEN** |

---

## GATE SJEKKPUNKTER MED CEO GODKJENNING

### CHECKPOINT 1: Foundation Layer G4 (IoS-001→004) ✅ COMPLETE

**Scope:** IoS-001, IoS-002, IoS-003, IoS-004

**Status:** COMPLETED 2025-12-03
- IoS-001: G4_CONSTITUTIONAL (FROZEN)
- IoS-002: G4_CONSTITUTIONAL (FROZEN)
- IoS-003: G4_CONSTITUTIONAL (FROZEN)
- IoS-004: G4_CONSTITUTIONAL (FROZEN)

**Handling Utført:**
1. ✅ Opprettet batch G4 migration for foundation layer
2. ✅ Satt `status = 'G4_CONSTITUTIONAL'`
3. ✅ Satt `immutability_level = 'FROZEN'`
4. ✅ Registrert VEGA attestation
5. ✅ Oppdatert `modification_requires = 'FULL_G1_G4_CYCLE'`

**ADR Implikasjoner:**
- ADR-004: Gate compliance formalisert
- ADR-013: One-Source-Truth etablert
- ADR-011: Hash chain integritet

**Migration:** `068_foundation_g4_constitutional.sql`
**Hash Chain:** `HC-CP1-FOUNDATION-G4-20251203`

**CEO Godkjenning:** [X] GODKJENT (2025-12-03)

---

### CHECKPOINT 2: Skill & Macro Layer G4 (IoS-005, IoS-006) ✅ COMPLETE

**Scope:** IoS-005, IoS-006

**Status:** COMPLETED 2025-12-03
- IoS-005: G4_CONSTITUTIONAL (FROZEN)
- IoS-006: G4_CONSTITUTIONAL (FROZEN)

**Handling Utført:**
1. ✅ Formalisert G4 status for IoS-005
2. ✅ Formalisert G4 status for IoS-006
3. ✅ Registrert VEGA attestation

**ADR Implikasjoner:**
- ADR-012: Economic Safety calibration
- ADR-013: Skill score lineage

**Migration:** `069_skill_macro_g4_constitutional.sql`
**Hash Chain:** `HC-CP2-SKILL-MACRO-G4-20251203`

**CEO Godkjenning:** [X] GODKJENT (2025-12-03)

---

### CHECKPOINT 3: Expansion Modules G1 (IoS-009, 010, 011)

**Scope:** IoS-009, IoS-010, IoS-011

**Nåværende Status:** G0_SUBMITTED (alle tre)

**Handling:**
1. G1 Technical Validation for hver modul
2. Schema definisjon
3. Input/output contracts
4. FORTRESS baseline

**ADR Implikasjoner:**
- ADR-004: Gate progression
- ADR-011: Hash chain etablering

**Migration:** `063_expansion_g1_technical.sql`

**CEO Godkjenning:** [ ] PENDING

---

### CHECKPOINT 4: Decision Engine G4 (IoS-008) ✅ COMPLETE

**Scope:** IoS-008

**Status:** COMPLETED 2025-12-03
- IoS-008: G4_CONSTITUTIONAL (FROZEN)
- Version: 2026.PROD.G4
- Hash Chain: 608a54e0-deaf-4cfd-a1c6-a0a69d652ab5

**Avhengigheter Tilfredsstilt:** ✅
- IoS-001→006: All G4_CONSTITUTIONAL

**Handling Utført:**
1. ✅ Pre-freeze snapshot captured
2. ✅ G4 Constitutional activation
3. ✅ Post-freeze snapshot verified
4. ✅ Evidence bundle generated
5. ✅ Zero functional changes confirmed

**ADR Implikasjoner:**
- ADR-004: Full gate cycle
- ADR-008: Cryptographic mandates
- ADR-013: Decision lineage

**Migration:** `070_ios008_g4_constitutional.sql`
**Evidence:** `CP4_IOS008_G4_EVIDENCE_BUNDLE.json`
**Hash Chain:** `HC-CP4-IOS008-G4-20251203`

**CEO Godkjenning:** [X] GODKJENT (2025-12-03)

---

### CHECKPOINT 5: Execution Engine G4 Full (IoS-012) ✅ COMPLETE

**Scope:** IoS-012

**Status:** COMPLETED 2025-12-03
- IoS-012: G4_CONSTITUTIONAL_FULL (FROZEN)
- Version: 2026.PROD.G4.FULL
- Hash Chain: 74f086a9-3f55-4ad4-93ba-c49184186340

**Avhengigheter Tilfredsstilt:** ✅
- IoS-008: G4_CONSTITUTIONAL

**Handling Utført:**
1. ✅ Pre-freeze snapshot captured
2. ✅ G4 Constitutional Full activation
3. ✅ Post-freeze snapshot verified
4. ✅ Zero functional mutations verified
5. ✅ Evidence bundle generated
6. ✅ **LIVE remains BLOCKED** per ADR-012

**Safety Verification:**
- live_api_enabled: FALSE ✅
- paper_api_enabled: TRUE ✅
- All file hashes unchanged ✅

**ADR Implikasjoner:**
- ADR-008: Ed25519 signatures
- ADR-012: ExecutionGuard pattern
- ADR-013: Source mandate enforcement
- ADR-016: DEFCON integration

**Migration:** `071_ios012_g4_full_constitutional.sql`
**Evidence:** `CP5_IOS012_G4_EVIDENCE_BUNDLE.json`
**Hash Chain:** `HC-CP5-IOS012-G4-20251203`

**CEO Godkjenning:** [X] GODKJENT (2025-12-03)

---

### CHECKPOINT 6: LIVE Authorization (Separat)

**Scope:** Ny `LIVE_AUTHORIZED` infrastruktur

**Avhengigheter:** ALLE IoS må være G4 Constitutional først

**Handling:**
1. Opprett `fhq_governance.live_authorization` tabell
2. Definer LIVE unlock requirements:
   - Full 10-year backtest
   - Economic risk dossier
   - QG-F6 gate pass
   - VEGA FULL_PASS
   - CEO signature
3. Implementer `LIVE_AUTHORIZED` flagg i `paper_execution_authority`

**ADR Implikasjoner:**
- ADR-012: Economic Safety (QG-F6)
- ADR-016: DEFCON prerequisites
- Two-Man Rule: CEO + VEGA

**Migration:** `066_live_authorization_layer.sql`

**CEO Godkjenning:** [ ] PENDING

---

## DATABASE ENDRINGER

### Ny tabell: `fhq_governance.live_authorization`

```sql
CREATE TABLE fhq_governance.live_authorization (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ios_id TEXT NOT NULL REFERENCES fhq_meta.ios_registry(ios_id),
    authorization_status TEXT NOT NULL DEFAULT 'BLOCKED'
        CHECK (authorization_status IN ('BLOCKED', 'PENDING_REVIEW', 'AUTHORIZED')),
    g4_constitutional_verified BOOLEAN NOT NULL DEFAULT FALSE,
    backtest_10y_passed BOOLEAN NOT NULL DEFAULT FALSE,
    economic_risk_dossier_approved BOOLEAN NOT NULL DEFAULT FALSE,
    qg_f6_passed BOOLEAN NOT NULL DEFAULT FALSE,
    vega_full_pass BOOLEAN NOT NULL DEFAULT FALSE,
    ceo_signature_id UUID,
    authorized_at TIMESTAMPTZ,
    authorized_by TEXT,
    hash_chain_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Oppdatering: `paper_execution_authority`

```sql
ALTER TABLE fhq_governance.paper_execution_authority
ADD COLUMN live_authorized BOOLEAN NOT NULL DEFAULT FALSE,
ADD COLUMN live_authorization_id UUID REFERENCES fhq_governance.live_authorization(id);
```

---

## KRITISKE FILER

| Fil | Formål |
|-----|--------|
| `04_DATABASE/MIGRATIONS/061_foundation_g4_constitutional.sql` | Foundation G4 |
| `04_DATABASE/MIGRATIONS/062_skill_macro_g4_constitutional.sql` | Skill/Macro G4 |
| `04_DATABASE/MIGRATIONS/063_expansion_g1_technical.sql` | Expansion G1 |
| `04_DATABASE/MIGRATIONS/064_ios008_g4_constitutional.sql` | Decision Engine G4 |
| `04_DATABASE/MIGRATIONS/065_ios012_g4_full_constitutional.sql` | Execution G4 |
| `04_DATABASE/MIGRATIONS/066_live_authorization_layer.sql` | LIVE separation |

---

## CEO SJEKKPUNKT FORMAT

Ved hvert checkpoint presenteres:

```
┌─────────────────────────────────────────────────────────────┐
│ CHECKPOINT X: [Navn]                                        │
├─────────────────────────────────────────────────────────────┤
│ Scope: [IoS moduler]                                        │
│ Status: [Nåværende] → [Mål]                                 │
│ ADR: [Relevante ADR-er]                                     │
│ Risiko: [Lav/Medium/Høy]                                    │
│ Implikasjon: [Kort beskrivelse]                             │
├─────────────────────────────────────────────────────────────┤
│ CEO GODKJENNING PÅKREVD: [ ] GODKJENT  [ ] AVVIST           │
└─────────────────────────────────────────────────────────────┘
```

---

## EKSEKVERING

Planen eksekveres sekvensielt:
1. CEO godkjenner Checkpoint 1
2. STIG implementerer migration
3. VEGA attesterer
4. Bekreft til CEO
5. Fortsett til neste checkpoint

**Ingen checkpoint hoppes over.**
**Ingen LIVE aktivering før Checkpoint 6.**

---

## PAPER LOOP STATUS VED LAGRING

- **Loop ID:** PAPER-LOOP-20251201-201348
- **Cycles Completed:** 20+
- **Status:** RUNNING (continuous mode)
- **Regime:** BEAR
- **Allocation:** 0% (capital protected)

---

## RESUME INSTRUCTIONS

For å fortsette denne planen:
1. Start ny STIG-sesjon
2. Les dette dokumentet: `05_GOVERNANCE/PHASE3/BACKLOG_G4_CONSTITUTIONAL_ACTIVATION_PLAN.md`
3. Presenter Checkpoint 1 for CEO godkjenning
4. Implementer sekvensielt

---

*Lagret av STIG (CTO) — 2025-12-01 23:00 CET*
