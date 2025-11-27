# ADR-005 – Human Interaction & Application Layer Charter

**Status:** CEO Approved
**Author:** LARS (CSO – Logic, Analytics & Research Strategy)
**Authority Chain:** ADR-001 → ADR-002 → ADR-003 → ADR-004 → ADR-006 → ADR-007 → ADR-008 → ADR-009 → ADR-010 → ADR-011 → ADR-012
**Tier:** Constitutional (Tier-1 – Human Interaction & Application Layer)
**Scope:** CEO, Vision-IoS Dashboard, Orchestrator, VEGA, all agents (LARS, STIG, LINE, FINN, VEGA), fhq_meta, fhq_data, fhq_finn, fhq_validation
**Purpose:** Define the only authorized human interface to FjordHQ – the Vision-IoS Dashboard – and its integration with governance, agents, and the Application Layer (IoS-XXX).

---

## 1. Executive Summary

ADR-005 establishes the **Human Interaction & Application Layer** for FjordHQ.

It defines:

* the Vision-IoS Dashboard as the **only** authorized human entry point
* a **hybrid interaction model** – data panels + agent chat + system control actions
* CEO as the **sole human operator** of the dashboard
* VEGA and Orchestrator as mandatory intermediaries for all actions
* the IoS-XXX Application Layer as the extensible value-creation surface, separate from ADR governance

This ADR connects the existing constitutional and governance stack (ADR-001–ADR-004, ADR-006–ADR-012) with the Next.js dashboard implementation that already exposes health, gates, CDS risk, data freshness, FINN events and validation views from Postgres.

From this point, **all human value extraction** (insight, research, strategy, control actions) must occur via this layer.

---

## 2. Purpose

The purpose of ADR-005 is to:

1. Define a **single, governed human interaction surface** for FjordHQ (Vision-IoS Dashboard).
2. Separate **Application Layer** concerns (IoS-XXX) from **constitutional ADR** logic.
3. Enable the CEO to **ask, observe and act** – without breaking autonomy, governance, or economic safety.
4. Provide a standard pattern for integrating new Application Layer modules (IoS-001+).

---

## 3. System Identity – Human Interaction Layer

### 3.1 Single Human Operator

* The **CEO** is the **only** permitted human operator of the Vision-IoS Dashboard.
* No other user role may issue direct instructions to agents, orchestrate tasks, or trigger system actions through the Dashboard without a future ADR explicitly extending this charter.

### 3.2 Dashboard Definition

The Dashboard is defined as:

> The **only authorized surface** where a human can see, question, and influence FjordHQ – under VEGA-enforced governance and Orchestrator control.

It is not "just UI". It is a governed interface bound to:

* Postgres (fhq_data, fhq_finn, fhq_validation, fhq_meta)
* Orchestrator endpoints (agent tasks, event logging)
* VEGA governance and economic safety (ADR-006, ADR-011, ADR-012)

---

## 4. Interaction Model – Hybrid Human Interface

The Vision-IoS Dashboard uses a **hybrid** interaction model:

1. **Data & Insight Panels**

   * Overview (market state, freshness, signals, system health)
   * Trust Banner (gates, ADR compliance, data freshness, CDS / narrative risk)
   * System Health & Governance (gates, data quality, ADR registry views)
   * Live Market Data (Binance WebSocket, lineage-exposed, read-only)

2. **Agent Chat Interface (IoS-006 – Research Workspace)**

   * CEO can open a **chat workspace** targeted at specific agents:

     * `LARS` – strategic analysis and scenario framing
     * `FINN` – research, intelligence synthesis, CDS and narrative coherence
     * `STIG` – technical feasibility and schema/governance checks
     * `LINE` – SRE/state-of-pipelines, ingestion health, drift
     * `VEGA` – governance, risk classification, compliance explanations
   * Each message becomes a **typed Orchestrator task**, not a free-form LLM call.

3. **System Control Actions**
   From selected panels and the chat workspace, the CEO may request:

   * "Ingest Binance now" (market data ingestion job)
   * "Run reconciliation" (ADR-010 reconciliation workflow)
   * "Re-run freshness tests" (validation suite on freshness views)
   * "Generate new FINN embeddings" (research embeddings refresh)
   * "Adjust cost ceilings (ADR-012)" (proposed config change, not direct write)
   * "Propose capital calibration scenarios" (LARS/FINN-generated scenarios)

   All such actions are **requests**, not direct writes. They must pass through Orchestrator, VEGA, and relevant ADR gates before any state change.

---

## 5. Governance & Control of Actions

### 5.1 CEO-Only Execution Rights

* Only the **CEO** can invoke control actions through the Dashboard.
* Actions are **identity-bound** to CEO and logged for lineage, in alignment with ADR-002 (audit & reconciliation) and ADR-011 (Production Fortress).

### 5.2 Mandatory Intermediaries

Every action triggered from the Dashboard must:

1. Be packaged as an **Orchestrator task** (agent, action, parameters, idempotency key).

2. Pass **VEGA** checks where applicable:

   * integrity and lineage (ADR-002, ADR-006)
   * discrepancy scoring (ADR-010)
   * economic safety (ADR-012)

3. Respect **ADR-004 Change Gates** if the action leads to persistent changes in:

   * ADR registry
   * cost ceilings and rate limits
   * capital configuration or strategy weights
   * production configuration in fhq_meta or fhq_governance

### 5.3 Categories of Actions

Actions initiated from the Dashboard fall into three governance categories:

1. **Category A – Observational / Read-Only**

   * Examples: "Show current CDS", "List latest FINN events", "Show gate status", "Show economic safety status".
   * Governance: No state change; subject only to VEGA read controls and standard access rules.

2. **Category B – Operational Jobs (Non-Structural)**

   * Examples: "Ingest Binance now", "Re-run freshness tests", "Generate new FINN embeddings", "Run reconciliation job".
   * Governance:

     * Routed via Orchestrator
     * Logged as jobs with full lineage
     * Subject to VEGA economic safety constraints (rate limits, spend ceilings, execution budgets) per ADR-012.
     * No schema or governance configuration change.

3. **Category C – Governance & Capital-Proximal Changes**

   * Examples: "Adjust cost ceilings (ADR-012)", "Propose capital calibration scenarios", future production configuration adjustments.
   * Governance:

     * CEO can **request** changes from Dashboard; cannot directly mutate.
     * Requests become structured proposals:

       * G1 – STIG technical validation
       * G2 – LARS + VEGA governance validation
       * G3 – VEGA audit verification (hashes, lineage, discrepancy checks)
       * G4 – CEO final approval and canonicalization (per ADR-004).
     * Only after G4 may configuration be updated in canonical tables.

---

## 6. Application Layer – IoS-XXX Namespace

### 6.1 Separation from ADR Layer

* ADR-001–ADR-012 define **constitutional and governance logic**.
* IoS-XXX defines **Application Layer modules** surfaced through the Dashboard.
* IoS modules **may not**:

  * write to ADR tables directly
  * bypass VEGA or Orchestrator
  * alter economic safety or governance without passing ADR-004 gates

### 6.2 IoS Family (Reserved Structure)

This ADR reserves and defines the purpose of the following modules (detailed specifications to follow once ADR-001–ADR-015 are finalized):

* **IoS-001 – Market Pulse**
  High-level market state, cross-asset freshness, and volatility snapshot, driven by `fhq_data.price_series` and dashboard freshness views.

* **IoS-002 – Alpha Drift Monitor**
  Monitors strategy performance, drift vs. baselines, and alpha stability (to be linked with ADR-011 tests and performance metrics).

* **IoS-003 – FINN Intelligence v3**
  External narrative, serper events, CDS metrics, narrative shift risk, currently partially exposed via FINN events and CDS integration.

* **IoS-004 (Future)**
  Additional modules (Signal Feed Layer, Research Workspace chat, System Operations Console) will be specified in IoS-series documents, each bound to this charter.

### 6.3 Contract with the Dashboard

* Each IoS module must:

  * expose **read-only** views to the Dashboard by default
  * register any **action endpoints** with Orchestrator + VEGA
  * publish lineage (source tables/views) directly in the UI (pattern already in use via `data-lineage-indicator`).

---

## 7. Agent Chat Workspace (IoS-006 Concept)

While detailed IoS-006 specification is out of scope for this ADR, the following **constitutional constraints** apply:

* Every chat message:

  * must be bound to a **target agent** (LARS / FINN / STIG / LINE / VEGA)
  * must be logged with:

    * human identity (CEO)
    * agent identity
    * timestamp
    * task type (research, analysis, operational request, governance inquiry)

* No agent may:

  * receive a direct LLM call from the Dashboard without passing through Orchestrator
  * bypass VEGA economic safety constraints when invoking external LLM APIs (ADR-012)

* For any agent-issued proposal that affects:

  * governance
  * capital
  * cost ceilings
    the output is treated as **recommendation**, not direct execution. Execution is handled through the ADR-004 gates and CEO approval.

---

## 8. Alignment with Existing Implementation

The current Next.js Dashboard already embodies parts of this charter:

* **RootLayout** wires TrustBanner, Navigation and system health from `getSystemHealth()` and FINN CDS metrics.
* **Overview Page** consumes multi-asset freshness, FINN events, and gate summaries directly from Postgres (`fhq_data.price_series`, `fhq_finn.serper_events`, `fhq_validation.v_gate_a_summary`).
* **System Health module** is reserved as a governance surface for data quality, gates, ADR governance.
* **LiveBinancePrices** is a read-only, WebSocket-based panel explicitly separated from database writes (category A – observational).

ADR-005 formalizes these patterns and promotes them to **constitutional rules**.

---

## 9. Consequences

### Positive

* Single, governed human interface
* Clean separation: ADR kernel vs. Application Layer
* CEO can extract real value (research, strategy, operations) without compromising governance
* All control actions are traceable, orchestrated, and VEGA-guarded
* Future IoS modules have a clear contract and namespace

### Negative

* CEO becomes a hard dependency for human-triggered actions
* Additional engineering required to wire chat workspace and control actions through Orchestrator and VEGA with full lineage

### Risks & Mitigations

* **Risk:** Misconfigured actions bypass governance.
  **Mitigation:** All actions classified into A/B/C with explicit VEGA + gate requirements.

* **Risk:** IoS modules accidentally write into governance schemas.
  **Mitigation:** Enforce schema-level permissions and VEGA-only write access for ADR/gov tables (per ADR-006, ADR-011, ADR-012).

---

## 10. Next Steps

1. Register ADR-005 in `fhq_meta.adr_registry` as constitutional Tier-1 once approved.
2. Implement **IoS module registry** (IoS-XXX) in `fhq_meta` to mirror ADR registry patterns (read-only from Dashboard, VEGA-mediated writes).
3. Design and implement **IoS-006 – Research Workspace (Chat)** and **IoS-001–004** specifications in IoS-series documents, bound to this charter.
4. Wire Dashboard actions to Orchestrator with:

   * explicit task types
   * VEGA economic safety hooks (ADR-012)
   * ADR-004 gate routing for Category C actions.

---

## 11. Signatures

**Prepared by:**
LARS – Chief Strategy & Alpha Officer

**Reviewed by:**
STIG – CTO (Technical Integration & Database Alignment)
VEGA – Governance Engine (AI Governance, Economic Safety, ADR Compliance)

**To be approved by:**
CEO – Final Canonical Authority

**To be certified by:**
VEGA – Attestation of Human Interaction & Application Layer Conformance
