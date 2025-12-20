IoS-008 — Runtime Decision Engine
The Will of FjordHQ

Canonical Version: 2026.PROD.G0 (Submission)
Owner: LARS
Technical Authority: STIG
Governance: VEGA
Classification: Tier-1 Critical
Dependencies: IoS-003, IoS-005, IoS-007

1. Executive Summary — Strategic Mandate

FjordHQ kan nå:

se markedet (IoS-002/006)

forstå markedet (IoS-007)

bedømme egen kompetanse (IoS-005)

Men systemet har fortsatt ingen mekanisme som konverterer sannhet til beslutning.

IoS-008 etablerer FjordHQs Runtime Decision Engine.

Probabilistic Insight → Deterministic Intent.

Det produserer én eneste immutabel, hash-kjeden DecisionPlan, og overfører det til IoS-012 (Execution) gjennom en konstitusjonell “Air-Gap”.

IoS-008 beslutter. IoS-012 handler.

2. Strategic Position — The Fulcrum Between Intelligence and Action

IoS-008 ligger midt i arkitekturen:

Upstream Truth

IoS-003: Regime (“Er dette farlig?”)

IoS-007: Causality (“Hvor peker kraften?”)

IoS-005: Skill (“Er vi kompetente akkurat nå?”)

IoS-008: The Decider

syntetiserer, vekter, filtrerer

produserer én beslutning, deterministisk og revisjonsbar

Downstream Action

IoS-012 kan kun handle på signerte DecisionPlans

Zero Other Inputs allowed

3. Functional Architecture — Pure Deterministic Logic

IoS-008 er en stateless, deterministisk funksjon.
Null intern tilstand. Null hukommelse. Null drift.

3.1 The Trinity Requirement — Three Green Lights
Input Layer	Component	Question	Role
IoS-003	Regime	“Is this safe?”	Gatekeeper (Veto)
IoS-007	Causal Graph	“Is the wind aligned?”	Directional Driver
IoS-005	Skill Score	“Are we competent today?”	Risk Damper

Alle tre må være gyldige.
Manglende input = NO_DECISION.

3.2 Deterministic Allocation Formula
𝐴
𝑙
𝑙
𝑜
𝑐
=
𝐵
𝑎
𝑠
𝑒
×
𝑅
𝑒
𝑔
𝑖
𝑚
𝑒
𝑆
𝑐
𝑎
𝑙
𝑎
𝑟
×
𝐶
𝑎
𝑢
𝑠
𝑎
𝑙
𝑉
𝑒
𝑐
𝑡
𝑜
𝑟
×
𝑆
𝑘
𝑖
𝑙
𝑙
𝐷
𝑎
𝑚
𝑝
𝑒
𝑟
Alloc=Base×RegimeScalar×CausalVector×SkillDamper
RegimeScalar Model (Strategic Correction Applied)

To strategier støttes – må defineres av CEO ved G1:

A. Long-Only (Capital Preservation Mode)

RegimeScalar =

STRONG_BULL: 1.0

NEUTRAL: 0.5

BEAR: 0.0

BROKEN: 0.0

Resultat: BEAR → 0 betyr Cash, ikke Short.
Systemet beskytter kapital, men genererer ikke short-alpha.

B. Long/Short (Full Alpha Mode — RECOMMENDED)

RegimeScalar =

STRONG_BULL: 1.0

NEUTRAL: 0.5

BEAR: 1.0

BROKEN: 0.0

Resultat:
BEAR beholder 1.0, slik at negative CausalVector gir short-signal.
Dette matcher allerede genererte signaler:

BTC: -50%

Likviditet: contracting

CausalVector < 1

Dette er den korrekte konfigurasjonen for FjordHQs målsetning.

CausalVector

Basert på signerte edge strengths i IoS-007:

Liquidity ↑ → Causal > 1

Liquidity ↓ → Causal < 1

SkillDamper (IoS-005)

Kapitalbeskyttelsesfunksjon:

FSS ≥ 0.6 → Normal sizing

0.4 ≤ FSS < 0.6 → Lineær reduksjon i sizing

FSS < 0.4 → Alloc = 0 (Capital Freeze)

Systemet kutter seg selv ned når det mister presisjon.

4. DecisionPlan — Constitutional Output Artifact

The only instruction IoS-012 may execute.

Fullt revidert for TTL-kravet ditt:

{
  "decision_id": "UUID-v4",
  "timestamp": "2026-05-12T14:30:00Z",
  "valid_until": "2026-05-12T14:35:00Z",   // NEW: TTL/expiry
  "context_hash": "SHA256(Inputs_Snapshot)",

  "global_state": {
    "regime": "BULL_TRENDING",
    "defcon_level": 4,
    "system_skill_score": 0.82
  },

  "asset_directives": [
    {
      "asset_canonical_id": "BTC-PERP.BINANCE",
      "action": "ACQUIRE",
      "target_allocation_bps": 2500,
      "leverage_cap": 1.5,
      "risk_gate": "OPEN",
      "rationale": "Regime=BULL, Causal=LIQUIDITY_EXPANDING, Skill=HIGH."
    }
  ],

  "governance_signature": "Ed25519_Signature(IoS-008)"
}

TTL Enforcement

IoS-012 må avvise enhver plan der:

current_time > valid_until


Dette er en livsviktig sikkerhetsfunksjon i volatile markeder.

5. Governance Constraints
5.1 Read-Only Mandate

IoS-008 kan ikke skrive upstream.

5.2 No-Execution Rule

IoS-008 får aldri:

holde API-nøkler

kontakte børser

sende ordre

Brudd → Type A Governance Violation.

5.3 Decision Logging

Alle planer må:

hash-kjedes

signeres

lagres i fhq_governance.decision_log

Uten dette → plan ugyldig.

6. G0→G4 Roadmap
G1: Logic Core

Implement compute_decision_plan().

G2: Historical Replay

Simulere mot 10 års data.

G3: Handover

IoS-012 interface + VEGA schema validation.

G4: Constitutional Activation

Ed25519 signering + immutability.

7. Immediate Actions
STIG

Opprett fhq_governance.decision_log

Legg inn TTL-feltet valid_until

Gjennomfør append-only + hash-chain (ADR-011)

FINN

Definer RegimeScalar table (inkl. CHOPPY, MICRO_BULL)

Lever en gyldig CausalVector-normalisering

LARS

Lever full SkillDamper-kurve