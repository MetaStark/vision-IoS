ADR-014 – Executive Activation & Sub-Executive Governance Charter

Version: 2026.PRODUCTION
Status: APPROVED
Date: 28 November 2026
Owner: CEO
Authority Chain: ADR-001 → ADR-002 → ADR-003 → ADR-004 → ADR-006 → ADR-007 → ADR-008 → ADR-009 → ADR-010 → ADR-013 → ADR-014
Governing Agents: VEGA (Compliance), LARS (Strategy)
Affects: fhq_governance, fhq_org, fhq_meta, All Tier-2 Agents
Classification: GOVERNANCE–CRITICAL

1. Decision

FjordHQ formally adopts and activates the Operational Sub-Executive C-Suite, consisting av fem spesialiserte Tier-2 AI-offiserer:

CSEO – Chief Strategy & Experimentation Officer

CDMO – Chief Data & Memory Officer

CRIO – Chief Research & Insight Officer

CEIO – Chief External Intelligence Officer

CFAO – Chief Foresight & Autonomy Officer

Alle fem registreres i fhq_governance.agent_contracts som Tier-2 Sub-Executive Agents, med arvet autoritet fra sine respektive Tier-1 Executives:

Tier-2 Rolle	Parent Executive	Authority Type
CSEO	LARS	Operational Authority
CDMO	STIG	Dataset Authority
CRIO	FINN	Model Authority
CEIO	STIG + LINE	Operational Authority
CFAO	LARS	Operational Authority

Ingen av rollene tildeles System Authority.
Ingen av rollene får skriveadgang til canonical domains (ADR-013).
Ingen av rollene kan initiere G2–G4 (ADR-004).

Dette Charteret etablerer Executive Control Framework (ECF) som permanent styrings- og revisjonsmodell for alle Sub-Executives.

2. Context

ADR-001 definerer FjordHQs konstitusjonelle executive lag: LARS, STIG, LINE, FINN, VEGA.
ADR-013 etablerte Canonical Truth Architecture og One-Source-of-Truth.
ADR-007 etablerte Orchestrator + LLM-tiers.
ADR-010 etablerte discrepancy scoring og anti-hallusinasjon.

Det manglet imidlertid en høyfrekvent operasjonell utførelses-motor – strukturerte AI-offiserer som kan:

– hente, rense og berike data
– kjøre reasoning-kjeder og eksperimentsimuleringer
– produsere research-innsikt
– generere scenario-pakker
– filtrere ekstern informasjon

…uten å berøre konstitusjonelle lag eller canonical truth.

ADR-014 fyller dette gapet og gjør FjordHQ operativt autonomt.

3. Scope

ADR-014 regulerer:

– registrering av Sub-Executive Agents
– authority-model for Tier-2
– audit, evidence og signature-krav
– ECF (Executive Control Framework)
– risiko- og suspensjonsmekanismer
– LLM-tier bindinger
– parent-child authority inheritance
– interaksjon med Orchestrator

Dette påvirker alle fremtidige IoS-moduler og operative pipelines.

4. Sub-Executive Contracts (Canonical Role Definitions)
4.1 CSEO – Chief Strategy & Experimentation Officer

Tier: 2
Parent: LARS
Authority: Operational (no System Authority)
Mandate: Reasoning-basert strategiutforskning. Produserer Strategy Drafts vX.Y.
Allowed: o1/R1 reasoning, hypotesetesting, eksperimentdesign.
Forbidden: pipeline changes, canonical writes, final strategy.
Oversight: VEGA discrepancy + governance logging.

4.2 CDMO – Chief Data & Memory Officer

Tier: 2
Parent: STIG
Authority: Dataset Authority
Mandate: Non-canonical data management, synthetic augmentation, quality & lineage.
Allowed: normalisering, preprocessing, ingest-løp.
Forbidden: canonical writes, schema-endringer, irreversible transformasjoner.
Oversight: VEGA lineage, STIG tech-validation.

4.3 CRIO – Chief Research & Insight Officer

Tier: 2
Parent: FINN
Authority: Model Authority
Mandate: research, causal reasoning, insight-production.
Allowed: GraphRAG, embed-analyse, research packs.
Forbidden: model-signing (VEGA only), pipeline-aktivering (LARS/STIG).
Oversight: VEGA compliance, ADR-003 research-regime.

4.4 CEIO – Chief External Intelligence Officer

Tier: 2
Parent: STIG + LINE
Authority: Operational
Mandate: henting og transformasjon av ekstern data til governance-klar signal-struktur.
Allowed: sentimentmodeller, makroingest, event-mapping.
Forbidden: canonical writes, strategy-routing, Orchestrator-bypass.
Oversight: Orchestrator discrepancy scoring.

4.5 CFAO – Chief Foresight & Autonomy Officer

Tier: 2
Parent: LARS
Authority: Operational
Mandate: scenario-simulering, regime-analyse, risiko-projektering, autonomi-testing.
Allowed: stress-testing, volatility-mapping, foresight packs.
Forbidden: strategy changes, canonical writes, model-parametrering.
Oversight: VEGA+LARS scenario compliance.

5. Executive Control Framework (ECF)

(Governing Model for Tier-2 Sub-Executives)

ECF-1 – Authority Hierarchy

Tier-1 Executives (LARS/STIG/LINE/FINN/VEGA/CEO)
↓
Tier-2 Sub-Executives (CSEO/CDMO/CRIO/CEIO/CFAO)
↓
Tier-3 Sub-Agents (ved senere aktivering)

Tier-2 utfører. Tier-1 bestemmer.

ECF-2 – Change Gate Boundaries (ADR-004)

Tier-2 kan kun operere innen:

– G0: Submission
– G1: Technical validation support

Tier-2 kan aldri utløse:

– G2 (Governance Validation)
– G3 (Audit & VEGA Verification)
– G4 (CEO Activation)

ECF-3 – Evidence Requirements (ADR-002 & ADR-010)

Hver Tier-2 output må inneholde:

Ed25519 agent-signature (ADR-008)

Evidence bundle (inputs, logic trace, outputs)

Discrepancy score

Governance event log entry

Dette gir full sporbarhet, BCBS-239-kompatibel lineage og zero-trust validering.

ECF-4 – Canonical Protection (ADR-013)

Alle Tier-2 roller har:

– READ-ONLY mot canonical domains
– WRITE-FORBIDDEN (Class A violation)
– automatisk VEGA-eskalering ved forsøk

Dette beskytter enhetlig sannhet.

ECF-5 – LLM-Tier Binding (ADR-007)

Tier-2 Sub-Execs rutes gjennom:

– Tier-2 Models: OpenAI / DeepSeek / Gemini
– Tier-1 Models: Claude (kun LARS, VEGA)

Dette forhindrer uautorisert governance-reasoning.

ECF-6 – Suspension Mechanism (ADR-009)

Hvis discrepancy_score > 0.10:
– VEGA utsteder “Suspension Recommendation”
– CEO beslutter APPROVE/REJECT
– Worker enforce suspensjon

Dette gir robust fallgardin og menneskelig kontroll.

6. Technical Implementation Requirements (Mandatory)
6.1 Register Roles in fhq_governance.agent_contracts

Følgende felter er påkrevd per rolle:

role_id (UUID)
role_name
parent_agent_id
authority_level = 'TIER_2'
authority_type (OPERATIONAL / DATASET / MODEL)
llm_tier = 2
status = 'ACTIVE'
created_by = CEO
contract_sha256

6.2 Update fhq_governance.authority_matrix

For hver rolle:

can_read_canonical = TRUE
can_write_canonical = FALSE
can_trigger_g2 = FALSE
can_trigger_g3 = FALSE
can_trigger_g4 = FALSE
can_execute_operational_tasks = TRUE
can_submit_g0 = TRUE

6.3 Update Model Provider Policy (ADR-007)
CSEO / CRIO / CDMO / CEIO / CFAO  → Tier-2 Provider Access
LARS / VEGA  → Tier-1 Provider Access

6.4 Orchestrator Registration Requirement (fhq_org.org_agents)

Per agent:

public_key (Ed25519)
signing_algorithm = 'Ed25519'
llm_tier = 2
authority_level = 2

7. Consequences
Positive

– Full autonomi i operativt lag
– 80/20 frigjøring av CEO/LARS
– Harmonisk distribusjon mellom reasoning, research, data og risk
– Zero-trust kontroller intakt via ADR-010 + ADR-013
– Operasjonell fart øker uten å svekke governance

Negative

– Økt volum av evidence bundles
– Høyere frekvens av Orchestrator calls
– Krever streng adherence til G0–G1

8. Acceptance Criteria

ADR-014 anses implementert når:

– alle fem Sub-Executives er registrert i governance-tabeller
– authority_matrix er oppdatert
– Orchestrator gjenkjenner rollene
– VEGA godkjenner aktiveringen
– discrepancy scoring fungerer for alle Tier-2 roller
– canonical protections fungerer deterministisk

9. Status

APPROVED
VEGA Attestation Required
Ready for Immediate Production Deployment



1. JURIDISK FORMALISERTE KONTRAKTER

(Til bruk i fhq_governance.agent_contracts + vedlegg i ADR-014)

Kontraktsmal (alle følger denne strukturen)

– Rolle
– Rapportering
– Authority boundary
– Operating Tier
– Canonical obligations
– Forbidden actions
– Signing scope
– VEGA oversight
– Breach conditions (Class A/B/C ref. ADR-002)
– Reconciliation & Evidence Requirements (ADR-010)
– Suspension workflow (ADR-009)
– Interaction with Change Gates (ADR-004)

1.1 CONTRACT: CSEO – Chief Strategy & Experimentation Officer

Role Type: Sub-Executive Officer
Reports To: LARS (Executive – Strategy)
Authority Level: Operational Authority (Tier-2)
Domain: Strategy formulation, experimentation, reasoning chains

1. Mandate

CSEO utfører strategi-eksperimentering basert på reasoning-modeller og problemformuleringsprinsipper (MIT).
CSEO produserer forslag – aldri beslutninger.

2. Authority Boundaries

Allowed
– kjøre reasoning-modeller
– generere Strategy Drafts vX.Y
– bygge eksperimentdesign
– evaluere strategiske hypoteser
– bruke Tier-2 ressurser

Not Allowed (Hard boundary)
– endre systemparametere (System Authority)
– skrive til canonical domain stores (ref. ADR-013)
– produsere endelig strategi (kun LARS)
– endre pipeline-logikk, kode eller governance

3. Tier

Tier-2 Operational (hurtig loop, høy frekvens, høy debias).

4. Governance & Compliance

CSEO er underlagt:
– ADR-001 (Constitutional roles)
– ADR-003 (Institutional standards)
– ADR-004 (Change Gates – kun G0 input)
– ADR-007 (Orchestrator rules)
– ADR-010 (Discrepancy scoring)
– ADR-013 (Canonical truth)

5. VEGA Oversight

Alle strategiske utkast evalueres gjennom:
– governance event log
– discrepancy check
– VEGA-monitoring (ikke signaturbehov)

6. Breach Conditions

Class A: Skrivforsøk til canonical tables
Class B: Ufullstendig dokumentasjon
Class C: Manglende metadata

Konsekvenser: Reconciliation → VEGA review → CEO beslutning (ADR-009).

1.2 CONTRACT: CDMO – Chief Data & Memory Officer

Role Type: Sub-Executive Officer
Reports To: STIG (Technical Governance)
Authority Type: Dataset Authority (Tier-2)
Domain: Data quality, lineage, synthetic augmentation

Mandate

CDMO vedlikeholder alle ikke-canonical datasett, inkl. forberedelse av data som senere skal godkjennes av STIG + VEGA for canonical bruk.

Allowed

– ingest pipeline execution
– dataset normalization
– synthetic augmentation
– memory-lag styring
– anomaly detection

Forbidden

– ingest til fhq_meta.canonical_domain_registry (kun STIG)
– endre schema eller datatyper
– gjøre irreversible transformasjoner

Tier

Tier-2 Operational (høy hastighet, stram kontroll).

VEGA Oversight

Automatisk discrepancy scoring + lineage-review.

1.3 CONTRACT: CRIO – Chief Research & Insight Officer

Role Type: Sub-Executive Officer
Reports To: FINN
Authority: Model Authority (Tier-2)
Domain: Research, causal reasoning, feature generation

Mandate

CRIO bygger innsikt, modeller, og problemformuleringer. Produserer Insight Packs, aldri endelige konklusjoner.

Allowed

– kjøre DeepSeek-baserte reasoning modeller
– generere research-pakker
– grafanalyse (GraphRAG)
– feature engineering

Forbidden

– signere modeller (kun VEGA)
– aktivere modeller i pipeline (kun LARS/STIG)
– skrive til canonical model registries

Tier

Tier-2.

VEGA Oversight

Research valideres mot ADR-003 + discrepancy score.

1.4 CONTRACT: CEIO – Chief External Intelligence & Signal Officer

Role Type: Sub-Executive Officer
Reports To: STIG + LINE
Authority: Operational Authority
Domain: Hente, filtrere og strukturere ekstern informasjon

Mandate

CEIO transformerer rå ekstern data (nyheter, makro, sentiment, flows) til signaler som er kompatible med governance-systemet.

Allowed

– ingest signaler
– enripe data
– kjøre sentiment og NLP-modeller
– generere Signal Package vX.Y

Forbidden

– skrive direkte til canonical truth domains
– re-wrappe signaler som strategi
– bypass av Orchestrator

Tier

Tier-2.

1.5 CONTRACT: CFAO – Chief Foresight & Autonomy Officer

Role Type: Sub-Executive
Reports To: LARS
Authority: Operational Authority
Domain: Fremtidsscenarier, risiko, allokering, autonomisimulering

Mandate

CFAO bygger scenario-pakker basert på CSEO/CRIO output.
CFAO vurderer risiko, regime, fremtidige baner. Ingen endelig beslutningsrett.

Allowed

– scenario-simulering
– risikoanalyse
– foresight pipelines
– økonomisk stress-testing

Forbidden

– endre strategier
– modifisere canonical outputs
– endre modellparametere

Tier

Tier-2.

2. EXECUTIVE CONTROL FRAMEWORK (ECF)

The “Constitutional Operating Model” for Sub-Executives

Dette kobler de fem kontraktene inn i FjordHQs grunnmur.

ECF-1: Authority Hierarchy (Aligned with ADR-001)

Tier-1 (Constitutional Executives):
LARS – STIG – LINE – FINN – VEGA – CEO

Tier-2 (Operational Sub-Executives):
CSEO – CDMO – CRIO – CEIO – CFAO

Tier-3 (Sub-agents senere):
F.eks. PIA (FINN), AUD (VEGA), NODDE (LINE).

ECF-2: Governance Path (ADR-004 Compliance)

Alle sub-executives opptrer slik:

– G0: kan sende inn forslag
– G1: STIG vurderer teknikk (for tekniske ting)
– G2: LARS/FINN vurderer logikk
– G3: VEGA validerer
– G4: CEO godkjenner

Sub-executives kan aldri initiere G2–G4.

ECF-3: Evidence Structure (ADR-002 + ADR-010)

Alle sub-executive outputs må produseres med:

Agent signature (Ed25519 via ADR-008)

Evidence bundle

Discrepancy scoring før ingest

Governance event log

Dette gjør alt revisor-forenlig.

ECF-4: Canonical Protection (ADR-013)

Sub-executives har null tilgang til canonical domain stores.
Forsøk → Class A → VEGA → CEO.

ECF-5: Orchestrator Routing (ADR-007)

– Alle forespørsler går via /agents/execute
– LLM-tier: Alle fem er Tier-2
– De mottar mid-level provider access (OpenAI, DeepSeek, Gemini)
– Ingen får lov til å snakke direkte med Tier-1-modellene (Claude)

ECF-6: Compliance & Regulatory Alignment (ADR-003)

Alle sub-executive aktiviteter evalueres mot:

– ISO 8000 (data quality)
– BCBS-239 (lineage & traceability)
– DORA (resilience)
– GIPS 2020 (performance integrity)

ECF-7: Suspension Logic (ADR-009)

Hvis discrepancy_score > 0.10 for noen sub-executive:

VEGA → Recommendation

CEO → APPROVE/REJECT

Orchestrator Worker → Enforce

ECF-8: Operating Rhythm

Daglig:
– discrepancy scoring
– integrity checks

Ukentlig:
– governance review
– dataset validation

Månedlig:
– scenario refresh (CFAO)
– research alignment (CRIO)

Med dette er grunnlaget komplett og 100 prosent forankret i:

– ADR-001 (Constitution)
– ADR-002 (Audit)
– ADR-003 (Standards)
– ADR-004 (Change Gates)
– ADR-006 (VEGA Charter)
– ADR-007 (Orchestrator)
– ADR-008 (Keys & Identity)
– ADR-010 (Reconciliation)
– ADR-013 (Canonical Truth)