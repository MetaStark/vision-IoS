# FjordHQ Governance Registry — Database-Verified

**Document ID:** `STIG-GOV-REG-2026-02-08`
**Generated:** 2026-02-08
**Source:** `fhq_meta` schema @ 127.0.0.1:54322/postgres
**Verified By:** STIG (System for Technical Implementation & Governance)
**Authority:** ADR-013 (Canonical ADR Governance and One-True-Source)

---

## Database Record Counts (Verified)

| Table | Record Count |
|-------|-------------|
| `fhq_meta.adr_registry` | 25 |
| `fhq_meta.ios_registry` | 17 |
| `fhq_meta.canonical_documents` | 54 (21 ADR + 18 EC + 15 IoS) |
| `fhq_meta.ec_authority_resolutions` | 16 |
| `fhq_meta.ios_appendix_registry` | 5 |
| `fhq_meta.agent_keys` | 12 |
| `fhq_meta.vega_attestations` | 39 |

---

## PART 1: ADR REGISTRY (25 Records)

### Constitutional ADRs (Tier-1)

| ADR ID | Title | Type | Status | Owner | Version | VEGA Attested | SHA-256 |
|--------|-------|------|--------|-------|---------|---------------|---------|
| ADR-001 | System Charter | CONSTITUTIONAL | APPROVED / ACTIVE | CEO | 2026.PRODUCTION | ✅ | `29cec3f0...` |
| ADR-002 | Audit and Error Reconciliation Charter | CONSTITUTIONAL | APPROVED / ACTIVE | VEGA | 2026.PRODUCTION | ✅ | `2a439abc...` |
| ADR-004 | Change Gates Architecture (G0-G4) | CONSTITUTIONAL | APPROVED / ACTIVE | VEGA | 2026.PRODUCTION | ✅ | `d6ec2f78...` |
| ADR-005 | Mission & Vision Charter | CONSTITUTIONAL | APPROVED / ACTIVE | CEO | 2026.PRODUCTION | ✅ | `f96e8bc1...` |
| ADR-006 | VEGA Autonomy and Governance Engine Charter | CONSTITUTIONAL | APPROVED / ACTIVE | CEO | 2026.PRODUCTION | ✅ | `a66e37cc...` |
| ADR-007 | Orchestrator Architecture | CONSTITUTIONAL | APPROVED / ACTIVE | CEO | 2026.PRODUCTION | ✅ | `c9b1b140...` |
| ADR-008 | Cryptographic Key Management and Rotation | CONSTITUTIONAL | APPROVED / ACTIVE | STIG | 2026.PRODUCTION | ✅ | `5b0ee77b...` |
| ADR-012 | Economic Safety Architecture | CONSTITUTIONAL | APPROVED / ACTIVE | CEO | 2026.PRODUCTION | ✅ | `b5e5662f...` |
| ADR-014 | Executive Activation and Sub-Executive Governance | CONSTITUTIONAL | APPROVED / ACTIVE | CEO | 2026.PRODUCTION | ✅ | `7ae515d1...` |
| ADR-016 | DEFCON Circuit Breaker Protocol | CONSTITUTIONAL | APPROVED / ACTIVE | LINE | 2026.PRODUCTION | ✅ | `fce8a2cd...` |
| ADR-017 | MIT Quad Protocol for Alpha Sovereignty | CONSTITUTIONAL | APPROVED / ACTIVE | CEO | 2026.PRODUCTION | ✅ | `c79fdb15...` |
| ADR-019 | Human Interaction & Application Layer Charter | CONSTITUTIONAL | APPROVED / ACTIVE | CEO | 2026.PRODUCTION | ✅ | `05cf130a...` |
| ADR-020 | Autonomous Cognitive Intelligence | CONSTITUTIONAL | APPROVED / ACTIVE | CEO | 2026.PRODUCTION | ✅ | `bf275fbd...` |
| ADR-024 | AEL Phase Gate Protocol | CONSTITUTIONAL | APPROVED / DRAFT | CEO | 1.0 | ✅ | `5947ebaf...` |

### Architectural ADRs (Tier-2)

| ADR ID | Title | Type | Status | Owner | Version | VEGA Attested | SHA-256 |
|--------|-------|------|--------|-------|---------|---------------|---------|
| ADR-003 | Institutional Standards and Compliance Framework | ARCHITECTURAL | APPROVED / ACTIVE | STIG | 2026.PRODUCTION | ✅ | `5d69e79f...` |
| ADR-009 | Governance Approval Workflow for Agent Suspension | ARCHITECTURAL | APPROVED / ACTIVE | VEGA | 2026.PRODUCTION | ✅ | `24ea676f...` |
| ADR-010 | State Reconciliation Methodology and Discrepancy Scoring | ARCHITECTURAL | APPROVED / ACTIVE | STIG | 2026.PRODUCTION | ✅ | `52e3c24f...` |
| ADR-011 | Fortress and VEGA Testsuite | ARCHITECTURAL | APPROVED / ACTIVE | STIG | 2026.PRODUCTION | ✅ | `654fe1df...` |
| ADR-013 | Canonical ADR Governance and One-True-Source | ARCHITECTURAL | APPROVED / ACTIVE | STIG | 2026.PRODUCTION | ✅ | `554cde39...` |
| ADR-013A | Time Authority Doctrine | ARCHITECTURAL | APPROVED / ACTIVE | — | 2026.01 | ❌ | — |
| ADR-015 | Meta-Governance Framework for ADR Ingestion | ARCHITECTURAL | APPROVED / ACTIVE | VEGA | 2026.PRODUCTION | ✅ | `81c4a520...` |
| ADR-018 | Agent State Reliability Protocol (ASRP) | ARCHITECTURAL | APPROVED / ACTIVE | STIG | 2026.PRODUCTION | ✅ | `538aa8bc...` |
| ADR-021 | Cognitive Engine Architecture Deep Research Protocol | ARCHITECTURAL | APPROVED / ACTIVE | FINN | 2026.PRODUCTION | ✅ | `27665848...` |

### Post-Constitutional ADRs (ADR-022+)

| ADR ID | Title | Type | Status | Owner | Version | VEGA Attested | Gate Status |
|--------|-------|------|--------|-------|---------|---------------|-------------|
| ADR-022 | The Autonomous Database Horizon Implementation Charter | CONSTITUTIONAL | APPROVED / DRAFT | STIG | 1.0 | ❌ | G4_COMPLETE |
| ADR-023 | MBB Corporate Standards Integration | OPERATIONAL | APPROVED / DRAFT | STIG | 1.0 | ❌ | G4_COMPLETE |

### ADR Descriptions (from `adr_registry.description`)

| ADR ID | Description |
|--------|-------------|
| ADR-001 | Defines executive agent roles and authority boundaries |
| ADR-002 | All changes must be logged to audit tables |
| ADR-003 | Schema naming conventions and model development lifecycle |
| ADR-004 | Governance gates for system changes |
| ADR-005 | Propagated from canonical_documents per CEO-DIR-2025-INGEST-001 |
| ADR-006 | VEGA verification and governance authority |
| ADR-007 | Propagated from canonical_documents per CEO-DIR-2025-INGEST-001 |
| ADR-008 | Ed25519 signing requirements |
| ADR-009 | Propagated from canonical_documents per CEO-DIR-2025-INGEST-001 |
| ADR-010 | Propagated from canonical_documents per CEO-DIR-2025-INGEST-001 |
| ADR-011 | Hash chain validation and test framework |
| ADR-012 | Cost constraints, API waterfall, execution gates |
| ADR-013 | Propagated from canonical_documents per CEO-DIR-2025-INGEST-001 |
| ADR-013A | Defines authoritative time source (database timestamp) for all system operations |
| ADR-016 | Emergency halt and risk management |
| ADR-017 | Alpha signal sovereignty and intellectual property |
| ADR-018 | State locking and immutability requirements |
| ADR-020 | ACI framework and agent autonomy |

---

## PART 2: IoS REGISTRY (17 Records)

### Canonical Intelligence Operating Systems

| IoS ID | Full Title | Status | Owner | Version | Canonical | Governing ADRs | Dependencies |
|--------|-----------|--------|-------|---------|-----------|----------------|--------------|
| IoS-001 | Price Data Acquisition & Canonical Storage | ACTIVE | STIG | 2026.PRODUCTION | ✅ | ADR-003, ADR-012 | — |
| IoS-002 | *(Title from source: IoS-002)* | ACTIVE | STIG | 2026.PRODUCTION | ✅ | ADR-003 | — |
| IoS-003 | Meta-Perception Engine | ACTIVE | FINN | 2026.PRODUCTION | ✅ | ADR-003, ADR-017 | — |
| IoS-004 | Regime-Driven Allocation Engine | ACTIVE | FINN | 2026.PRODUCTION | ✅ | ADR-012, ADR-017 | — |
| IoS-005 | Forecast Calibration and Skill Engine | ACTIVE | FINN | 2026.PRODUCTION | ✅ | ADR-012 | — |
| IoS-006 | Global Macro & Factor Integration Engine | ACTIVE | FINN | 2026.PRODUCTION | ✅ | ADR-013 | IoS-002, IoS-005 |
| IoS-007 | Alpha Graph Engine — Causal Reasoning Core | ACTIVE | FINN | 2026.PRODUCTION | ✅ | ADR-017, ADR-020 | — |
| IoS-008 | Runtime Decision Engine | ACTIVE | LINE | 2026.PRODUCTION | ✅ | ADR-012, ADR-016 | — |
| IoS-009 | Meta-Perception Layer | ACTIVE | FINN | 2026.PRODUCTION | ✅ | ADR-020 | — |
| IoS-010 | Prediction Ledger Engine | ACTIVE | FINN | 2026.PRODUCTION | ✅ | ADR-017 | — |
| IoS-011 | Technical Analysis Pipeline | ACTIVE | FINN | 2026.PRODUCTION | ✅ | ADR-003 | — |
| IoS-012 | Execution Engine | ACTIVE | LINE | 2026.PRODUCTION | ✅ | ADR-012, ADR-016, ADR-017 | — |
| IoS-013 | Signal Aggregation & Context Contract Engine | ACTIVE | FINN | 2026.PRODUCTION | ✅ | ADR-001, ADR-003, ADR-004, ADR-005, ADR-007, ADR-013, ADR-014, ADR-016, ADR-018, ADR-020 | IoS-001, IoS-002, IoS-003, IoS-005, IoS-006, IoS-007, IoS-010, IoS-016 |
| IoS-014 | Autonomous Task Orchestration Engine | ACTIVE | STIG | 2026.PRODUCTION | ✅ | ADR-007, ADR-014 | — |
| IoS-015 | Multi-Strategy, Cognitive Trading Infrastructure | ACTIVE | FINN | 2026.PRODUCTION | ✅ | ADR-012, ADR-017, ADR-020 | — |
| IoS-016 | Economic Calendar & Temporal Governance | ACTIVE | LINE | 2026.G4.ACTIVE | ✅ | ADR-001, ADR-002, ADR-004, ADR-008, ADR-012, ADR-013, ADR-016, ADR-020 | IoS-001, IoS-003, IoS-005, IoS-010 |

### Non-Canonical / Ephemeral IoS

| IoS ID | Title | Status | Owner | Canonical | Governance State |
|--------|-------|--------|-------|-----------|-----------------|
| IOS-003-B | Intraday Regime-Delta (Ephemeral Context Engine) | G0_SUBMITTED | FINN | ❌ | AWAITING_VEGA_ATTESTATION |

### IoS Appendix Registry (5 Records)

| Appendix Code | Parent IoS | Title | Status | Version | Owner |
|---------------|-----------|-------|--------|---------|-------|
| Appendix_A_HMM_REGIME | IoS-003 | Canonical Regime Model Specification (HMM v2.0) | ACTIVE | 2026.PROD.1 | LARS |
| ASPE | IoS-013 | Agent State Protocol Engine | **DEPRECATED** | 2026.DEPRECATED.1 | STIG |
| CDS | IoS-013 | Context Definition Specification | ACTIVE | 2026.DRAFT.1 | STIG |
| GATEWAY | IoS-013 | Truth Gateway Interface Specification | ACTIVE | 2026.DRAFT.2 | STIG |
| Appendix_A | IoS-014 | Sentinel DB Integrity Specification | ACTIVE | 1.0 | STIG |

### IoS-001 Detailed Description

> Foundation module for price data acquisition, validation, and canonical storage. Defines multi-tier price ontology (P1/P2/P3), vendor role classification, and orchestrator authority bindings per CEO Directive CD-IOS-001-PRICE-ARCH-001.

### IoS-006 Detailed Description

> Feature Filtration System designed to reject 95% of macro candidates. Only features surviving IoS-005 constitutional significance testing enter HMM v3.0.

### IoS-013 Detailed Description

> Implements 5-dimensional signal contracts: (1) Entity Scope with taxonomy versioning, (2) Time Authority with data_cutoff prevention, (3) Meaning Scope with calibration tracking, (4) Provenance via source_surface_registry, (5) Aggregation doctrine with survivorship lock. Fail-closed per ADR-018. No silent defaults.

### IoS-016 Detailed Description

> FjordHQ canonical economic calendar and temporal governance system. Provides single source of truth for market-moving events across all asset classes. Enables event-aware learning by tagging forecasts with event proximity context. Separates model error from event-driven volatility in Brier score analysis. Supports UMA Learning Velocity Index (LVI) with clean learning windows. MBB++ Investor-Grade Standard with 9 CEO refinements.

---

## PART 3: EC (Employment Contracts) — CANONICAL DOCUMENTS (18 Records)

### Tier-1 Executive Contracts

| EC Code | Agent | Status | Tier | Source File |
|---------|-------|--------|------|-------------|
| EC-001 | VEGA | ACTIVE | 1 | `EC-001_2026_PRODUCTION.md` |
| EC-002 | LARS | ACTIVE | 1 | `EC-002_2026_PRODUCTION.md` |
| EC-019 | CEO (Human Governor) | ACTIVE | 1 | `EC-019_Operational Convergence and Human Governor.md` |

### Tier-2 Sub-Executive Contracts

| EC Code | Agent | Status | Tier | Source File |
|---------|-------|--------|------|-------------|
| EC-003 | STIG | ACTIVE | 2 | `EC-003_2026_PRODUCTION.md` |
| EC-004 | FINN | ACTIVE | 2 | `EC-004_2026_PRODUCTION.md` |
| EC-005 | LINE | ACTIVE | 2 | `EC-005_2026_PRODUCTION.md` |
| EC-006 | CSEO | ACTIVE | 2 | `EC-006_2026_PRODUCTION.md` |
| EC-007 | CDMO | ACTIVE | 2 | `EC-007_2026_PRODUCTION.md` |
| EC-009 | CEIO | ACTIVE | 2 | `EC-009_2026_PRODUCTION.md` |
| EC-010 | CFAO | ACTIVE | 2 | `EC-010_2026_PRODUCTION.md` |
| EC-013 | CRIO | ACTIVE | 2 | `EC-013_2026_PRODUCTION.md` |

### Tier-3 Operational Contracts

| EC Code | Agent | Status | Tier | Source File |
|---------|-------|--------|------|-------------|
| EC-011 | CODE | ACTIVE | 3 | `EC-011_2026_PRODUCTION.md` |
| EC-012 | RESERVED | **RESERVED** | 3 | `EC-012_2026_PRODUCTION.md` |

### Special Classification Contracts

| EC Code | Agent/Purpose | Status | Classification | Source File |
|---------|--------------|--------|----------------|-------------|
| EC-008 | Framework (no agent) | **FRAMEWORK_CHARTER** | EC-F-008 | `EC-008_2026_PRODUCTION.md` |
| EC-018 | CEIO (Meta-Alpha & Freedom Optimizer) | **FROZEN** | — | `EC-018_Meta-Alpha & Freedom Optimizer.md` |
| EC-020 | SitC (Search in the Chain) | **FROZEN** | Cognitive Charter (EC-C) | `EC-020_2026_PRODUCTION_SitC_Search_in_the_Chain.md` |
| EC-021 | InForage (Information Foraging) | **FROZEN** | Cognitive Charter (EC-C) | `EC-021_2026_PRODUCTION_InForage_Information_Foraging.md` |
| EC-022 | IKEA (Knowledge Boundary) | ACTIVE | Cognitive Charter (EC-C) | `EC-022_2026_PRODUCTION_IKEA_Knowledge_Boundary.md` |

### VEGA Employment Contract Detail (dedicated table: `fhq_meta.vega_employment_contract`)

| Field | Value |
|-------|-------|
| Contract Number | EC-001 |
| Version | 2026.PRODUCTION |
| Employer | FjordHQ AS |
| Employee | VEGA |
| Effective Date | 2025-11-11 |
| Governing Charter | ADR-006 |
| Constitutional Foundation | ADR-001, ADR-002, ADR-003, ADR-004 |
| Total Duties | 10 |
| Total Constraints | 7 |
| Total Rights | 7 |
| Override Authority | CEO |
| Reports To | CEO |

---

## PART 4: EC AUTHORITY RESOLUTIONS (16 Records)

### Directive: CD-G1.3-EC-AUTH-RESOLUTION-2025-12-12 (9 Resolutions)

**Hash Chain:** `HC-G1.3-EC-AUTH-RESOLUTION-20251212`

#### Tier Provisional Elevations

| EC | Agent | Resolution Type | Prior State | Resolved State |
|----|-------|----------------|-------------|----------------|
| EC-003 | STIG | TIER_PROVISIONAL | DB: Tier-1, EC: Tier-2 → DB_LEADS | TIER_1_PROVISIONAL (ratification before G2) |
| EC-004 | FINN | TIER_PROVISIONAL | DB: Tier-1, EC: Tier-2 → DB_LEADS | TIER_1_PROVISIONAL (ratification before G2) |
| EC-005 | LINE | TIER_PROVISIONAL | DB: Tier-1, EC: Tier-2 → DB_LEADS | TIER_1_PROVISIONAL (ratification before G2) |

#### Domain Corrections

| EC | Agent | Resolution Type | Resolution |
|----|-------|----------------|------------|
| EC-009 | CEIO | DOMAIN_CORRECTION | Confirmed as External Cognitive Intelligence Operator. No infrastructure, schema, or execution authority. |

#### Semantic Clarifications

| EC | Agent | Resolution Type | Resolution |
|----|-------|----------------|------------|
| EC-013 | CRIO | SEMANTIC_CLARIFICATION | Canonical: Causal Research & Insight Agent with Risk Attribution Responsibilities. Research outputs consumed by risk systems; does not enforce risk controls. |

#### Reclassifications

| EC | Agent | Resolution Type | New Classification |
|----|-------|----------------|--------------------|
| EC-020 | SitC | RECLASSIFICATION | EC-C (Cognitive Charter) — Non-instantiated, governed by ADR-021 |
| EC-021 | InForage | RECLASSIFICATION | EC-C (Cognitive Charter) — Non-instantiated, governed by ADR-021 |
| EC-022 | IKEA | RECLASSIFICATION | EC-C (Cognitive Charter) — Non-instantiated, governed by ADR-021 |
| EC-008 | (none) | RECLASSIFICATION | EC-F-008 (Framework Charter) — Strategic framework, not an agent |

### Directive: CD-DEEPSEEK-MIGRATION-2025-12-20 (7 Resolutions)

**Hash Chain:** `HC-DEEPSEEK-MIGRATION-20251220`

| EC | Agent | Resolution Type | Prior Provider | Resolved Provider/Model |
|----|-------|----------------|----------------|------------------------|
| EC-001 | VEGA | DOMAIN_CORRECTION | anthropic / claude-sonnet-4-5-20250929 | deepseek / deepseek-reasoner (fallback: deepseek-chat) |
| EC-002 | LARS | DOMAIN_CORRECTION | anthropic / claude-sonnet-4-5-20250929 | deepseek / deepseek-reasoner (fallback: deepseek-chat) |
| EC-006 | CSEO | DOMAIN_CORRECTION | openai / gpt-4o | deepseek / deepseek-reasoner (fallback: deepseek-chat) |
| EC-007 | CDMO | DOMAIN_CORRECTION | openai / gpt-4o | deepseek / deepseek-reasoner (fallback: deepseek-chat) |
| EC-010 | CFAO | DOMAIN_CORRECTION | openai / gpt-4o | deepseek / deepseek-reasoner (fallback: deepseek-chat) |
| EC-013 | CRIO | RECLASSIFICATION | EC-008 (classification error) | EC-013 confirmed canonical, reports to FINN |
| EC-011 | CODE | DOMAIN_CORRECTION | unknown | anthropic / claude-code (**Exception** to DeepSeek consolidation) |

---

## PART 5: AGENT KEY REGISTRY (12 Records)

All keys are Ed25519 signing keys, ACTIVE status, VEGA attested.

| Agent ID | Key State | Storage Tier | Key Fingerprint | Ceremony | Activation Date |
|----------|-----------|--------------|-----------------|----------|-----------------|
| VEGA | ACTIVE | TIER1_HOT | `0b2fd6ea36a62b88` | CEREMONY_IGNITION_20251128 | 2025-12-14 |
| LARS | ACTIVE | TIER1_HOT | `d075b6dd7408ce40` | CEREMONY_IGNITION_20251128 | 2025-12-14 |
| STIG | ACTIVE | TIER1_HOT | `00fd9226c7c3a9e3` | CEREMONY_IGNITION_20251128 | 2025-12-14 |
| FINN | ACTIVE | TIER1_HOT | `fa206133fc0016fd` | CEREMONY_IGNITION_20251128 | 2025-12-14 |
| LINE | ACTIVE | TIER1_HOT | `f52c54cf823d8f58` | CEREMONY_IGNITION_20251128 | 2025-12-14 |
| CODE | ACTIVE | TIER1_HOT | `f20b090fa4be1c2a` | CEREMONY_IGNITION_20251128 | 2025-12-14 |
| CSEO | ACTIVE | TIER1_HOT | `61073303638c3dd2` | CEREMONY_IGNITION_20251128 | 2025-12-14 |
| CDMO | ACTIVE | TIER1_HOT | `747bee2a8d42f2be` | CEREMONY_IGNITION_20251128 | 2025-12-14 |
| CEIO | ACTIVE | TIER1_HOT | `c38c012a08b29bf6` | CEREMONY_IGNITION_20251128 | 2025-12-14 |
| CFAO | ACTIVE | TIER1_HOT | `6f6289c1ef77ac5d` | CEREMONY_IGNITION_20251128 | 2025-12-14 |
| CRIO | ACTIVE | TIER1_HOT | `fb085bfc4eb49897` | CEREMONY_IGNITION_20251128 | 2025-12-14 |
| UMA | ACTIVE | TIER2_WARM | `2fd377f9be70cea9` | (standalone ceremony) | 2026-01-16 |

---

## PART 6: CROSS-REFERENCE INTEGRITY

### ADR Owner Distribution

| Owner | Count | ADR IDs |
|-------|-------|---------|
| CEO | 9 | ADR-001, ADR-005, ADR-007, ADR-012, ADR-014, ADR-017, ADR-019, ADR-020, ADR-024 |
| STIG | 7 | ADR-003, ADR-008, ADR-010, ADR-011, ADR-013, ADR-018, ADR-022, ADR-023 |
| VEGA | 4 | ADR-002, ADR-004, ADR-009, ADR-015 |
| LINE | 1 | ADR-016 |
| FINN | 1 | ADR-021 |
| Unassigned | 1 | ADR-013A |

### IoS Owner Distribution

| Owner | Count | IoS IDs |
|-------|-------|---------|
| FINN | 11 | IoS-003, IOS-003-B, IoS-004, IoS-005, IoS-006, IoS-007, IoS-009, IoS-010, IoS-011, IoS-013, IoS-015 |
| STIG | 3 | IoS-001, IoS-002, IoS-014 |
| LINE | 3 | IoS-008, IoS-012, IoS-016 |

### Documents Registered in `canonical_documents` but NOT in Dedicated Registry

The `canonical_documents` table contains 21 ADR records (ADR-001 through ADR-021). The `adr_registry` contains 25 records (includes ADR-013A, ADR-022, ADR-023, ADR-024 which are not in canonical_documents).

**ADRs in `adr_registry` ONLY (not in canonical_documents):**
- ADR-013A (Time Authority Doctrine) — added 2026-01-20
- ADR-022 (Autonomous Database Horizon) — added 2026-01-14
- ADR-023 (MBB Corporate Standards) — added 2026-01-14
- ADR-024 (AEL Phase Gate Protocol) — added 2026-01-14

**IoS in `ios_registry` but NOT in `canonical_documents`:**
- IOS-003-B (Intraday Regime-Delta) — non-canonical, G0_SUBMITTED
- IoS-016 (Economic Calendar & Temporal Governance) — added 2026-01-16

### VEGA Attestation Coverage

| Document Type | Total | VEGA Attested | Attestation Rate |
|---------------|-------|---------------|------------------|
| ADR (adr_registry) | 25 | 22 | 88% |
| ADR (canonical_documents) | 21 | 21 | 100% |
| EC (canonical_documents) | 18 | 3 | 17% |
| IoS (canonical_documents) | 15 | 0 | 0% |
| IoS (ios_registry) | 17 | 0 (no vega_signature_id populated) | 0% |

### Gate Status Records

| Gate ID | Status | Validated By | Date |
|---------|--------|-------------|------|
| PHASE2_HYPOTHESIS_SWARM_V1.1 | OPEN | CEO_LARS | 2026-01-28 |

---

## PART 7: DATA INTEGRITY OBSERVATIONS

### SHA-256 Hash Coverage

- **ADR Registry:** 22/25 records have SHA-256 hashes (ADR-013A, ADR-022, ADR-023 missing = post-constitutional additions)
- **IoS Registry:** 17/17 records have content_hash populated
- **Canonical Documents:** 54/54 records have content_hash
- **Agent Keys:** 12/12 records have SHA-256 hash

### Anomalies Detected

1. **ADR-013A** — No SHA-256 hash, no VEGA attestation, no owner assigned. Created 2026-01-20.
2. **ADR-022, ADR-023** — `adr_status = APPROVED` but `status = DRAFT`. Metadata shows G4_COMPLETE but registry status field not updated.
3. **ADR-024** — `adr_status = APPROVED` but `status = DRAFT`. VEGA attested 2026-01-17.
4. **EC VEGA attestation gap** — Only 3/18 ECs are VEGA-attested in canonical_documents (EC-020, EC-021, EC-022).
5. **IoS-013 governance_state** — Shows `G0_UPGRADE_PENDING`, suggesting a pending upgrade cycle.
6. **IoS-016** — Present in `ios_registry` but not in `canonical_documents` (added post-ingestion).
7. **EC numbering gap** — EC-014 through EC-017 do not exist. Sequence jumps from EC-013 to EC-018.

---

## PART 8: AGENT HIERARCHY (Synthesized from EC + Resolution Data)

```
CEO (Ørjan Skjold) — EC-019 — Human Governor
├── VEGA — EC-001 — Tier-1 Governance Authority [deepseek-reasoner]
├── LARS — EC-002 — Tier-1 Strategic Architect [deepseek-reasoner]
├── STIG — EC-003 — Tier-2 (PROVISIONAL Tier-1) Technical Officer
│   └── CODE — EC-011 — Tier-3 Operational [claude-code, Anthropic exception]
├── FINN — EC-004 — Tier-2 (PROVISIONAL Tier-1) Alpha Research
│   ├── CRIO — EC-013 — Tier-2 Causal Research & Insight [deepseek-reasoner]
│   ├── SitC — EC-020 — FROZEN (Cognitive Charter EC-C)
│   ├── InForage — EC-021 — FROZEN (Cognitive Charter EC-C)
│   └── IKEA — EC-022 — ACTIVE (Cognitive Charter EC-C)
├── LINE — EC-005 — Tier-2 (PROVISIONAL Tier-1) Execution
├── CSEO — EC-006 — Tier-2 Sub-Executive [deepseek-reasoner]
├── CDMO — EC-007 — Tier-2 Sub-Executive [deepseek-reasoner]
├── CEIO — EC-009 — Tier-2 External Intelligence (NO infra authority)
├── CFAO — EC-010 — Tier-2 Sub-Executive [deepseek-reasoner]
└── UMA — (no EC) — Tier-2 Agent, key activated 2026-01-16
```

**Framework Only (No Agent):**
- EC-008 → EC-F-008 (Enterprise AI Architecture Framework)

**Reserved:**
- EC-012 → RESERVED for future allocation

---

*Document generated by STIG from live database queries against `fhq_meta` schema. All record counts and field values verified at query time. This document represents the complete governance state as registered in the FjordHQ database as of 2026-02-08.*
