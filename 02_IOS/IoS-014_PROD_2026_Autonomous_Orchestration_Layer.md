# IoS-014_PROD_2026 — Autonomous Orchestration Layer (Logical Control Plane)

**Canonical Version:** 2026.PROD.G1
**Status:** ACTIVE
**Supersedes:** IoS-014 — Autonomous Task Orchestration Engine (2026.DRAFT.G0)
**Owner:** STIG (CTO, Tier-1)
**Governance:** VEGA (Tier-1), CEO (Tier-0)
**Execution:** Distributed Daemons (CODE, LINE)
**Dependencies:** ADR-001..016, IoS-001..013, EC-003..007

---

## 1. Mission

IoS-014 defines FjordHQ's **Autonomous Orchestration Layer**.

Its mission is to act as the **logical control plane** governing how autonomous components are coordinated, constrained, observed and audited across the system.

**IoS-014:**
- does not implement business logic
- does not trade
- does not generate hypotheses
- does not require a single runtime daemon

**It defines and enforces:**
- execution order
- cadence and rhythm
- economic safety
- DEFCON behaviour
- auditability and evidence

**IoS-014 ensures that autonomous agents act on current canonical truth, within explicit economic and governance constraints, at all times.**

---

## 2. Architectural Principle (Critical)

> **IoS-014 is a logical orchestration layer, not a monolithic runtime service.**

The orchestration mandate is fulfilled through a set of coordinated, specialized daemon processes, each operating under explicit governance rules.

**The absence of a single `ios014_orchestrator` daemon does not imply loss of orchestration.**
Orchestration is achieved through enforced contracts, state registries, watchdogs and evidence trails.

This design is intentional and required for:
- resilience
- fault isolation
- audit defensibility
- economic safety

---

## 3. Scope of Orchestration

IoS-014 governs and supervises:

| Domain | Responsibility |
|--------|----------------|
| Scheduling | Cadence of autonomous tasks |
| Ordering | Inter-IoS execution order and dependency discipline |
| Vendors | Usage, quotas and fallback logic |
| DEFCON | Aware behaviour switching |
| Health | Heartbeat and liveness guarantees |
| Audit | Immutable evidence capture |

It applies across:
- Ingestion (prices, macro, news, flows)
- Feature and indicator pipelines (IoS-002, IoS-006)
- Perception and regime (IoS-003)
- Research, alpha and learning loops (IoS-007, 009, 010, 011)
- Tier-1 testing and hypothesis lifecycle
- Execution (paper and live under approval)

---

## 4. Runtime Realisation (Production 2026)

### 4.1 Distributed Control Implementation

| Orchestration Function | Implemented Via |
|------------------------|-----------------|
| Scheduling / cadence | `*_scheduler` daemons |
| Pre-Tier scoring | `pre_tier_scoring_daemon` |
| Tier-1 hypothesis testing | `tier1_execution_daemon` |
| Hypothesis lifecycle & death | `hypothesis_death_daemon` |
| Health & heartbeat | `daemon_watchdog` |
| DEFCON enforcement | `fhq_governance.defcon_state` |
| Economic safety | Vendor guard logic + watchdog |
| Audit & evidence | Evidence JSON + Fortress anchors |

All daemons operate under explicit lifecycle classification:
`ACTIVE`, `SUSPENDED_BY_DESIGN`, `DEPRECATED`, `ORPHANED`.

### 4.2 Scheduling Discipline

Scheduling is **decentralized but governed**.

**Rules:**
- No daemon may self-reschedule outside its declared frequency
- No daemon may execute if required upstream canonical tables are stale
- Non-reentrant tasks must not overlap execution windows

All schedules are auditable via:
- daemon heartbeats
- execution timestamps
- failure counters

---

## 5. Governance Alignment

### 5.1 ADR-013 — Canonical Truth

IoS-014 enforces:
- read-only access to canonical tables for orchestration decisions
- refusal to execute tasks on schema mismatch
- deterministic ordering of perception → testing → execution

### 5.2 ADR-012 — Economic Safety

IoS-014 is the runtime enforcement layer for economic safety.

**Rules:**
- Vendor soft ceiling at 90% of free tier
- Hard ceilings must never be crossed
- Fallback to cheaper or internal sources preferred
- Non-critical tasks may be skipped with explicit audit logs

All quota decisions must log:
- vendor
- current usage
- projected usage
- decision (throttle / fallback / skip)
- justification

### 5.3 ADR-016 — DEFCON

IoS-014 is fully DEFCON-aware.

| DEFCON | Behaviour |
|--------|-----------|
| GREEN | Full research, testing and execution (paper) |
| YELLOW | Reduced frequency for non-critical tasks |
| ORANGE | Freeze new research, preserve testing and monitoring |
| RED | Execution halted, perception and safety only |
| BLACK | Full halt, CEO-only override |

**DEFCON state overrides execution mode.**

---

## 6. Health, Liveness & Hygiene

IoS-014 mandates:
- Heartbeat emission every cycle
- Detection of stale, orphaned or runaway daemons
- Automatic escalation for ORPHANED components
- Lifecycle archiving for deprecated components

Daemon hygiene is governance-critical and enforced via:
- `daemon_watchdog`
- lifecycle registry
- audit evidence

---

## 7. Audit & Evidence

For each orchestration cycle, the system must be able to reconstruct:
- which daemons ran
- under which DEFCON and execution mode
- with which vendor quota state
- with what outcome

**Evidence must be:**
- immutable
- timestamped
- hash-anchored
- VEGA-verifiable

**This is non-negotiable.**

---

## 8. Runtime Modes

| Mode | Description |
|------|-------------|
| `LOCAL_DEV` | Reduced universe, cheap vendors only |
| `PAPER_PROD` | Full system, paper execution only |
| `LIVE_PROD` | Real execution under explicit CEO + VEGA approval |

IoS-014 enforces mode boundaries strictly.

---

## 9. Activation & Lifecycle Path

| Phase | Requirement |
|-------|-------------|
| G1 | Logical orchestration documented and mapped |
| G2 | Economic safety and DEFCON validated |
| G3 | 14 consecutive days PAPER_PROD without violations |
| G4 | CEO-approved LIVE_PROD with explicit risk budget |

---

## 10. Explicit Design Decision

> **The legacy daemon `ios014_orchestrator` is DEPRECATED BY DESIGN.**

Its responsibilities are fulfilled more robustly via:
- distributed daemons
- explicit governance contracts
- watchdog-based enforcement

**No monolithic orchestrator is required or desired.**

---

## 11. Executive Summary (for Registry)

**IoS-014 is FjordHQ's control plane, not a process.**

It guarantees that autonomy remains:
- economically safe
- epistemically sound
- auditable
- CEO-controllable

---

*This specification reflects production reality as of 2026 and is binding for all future development.*

**Document Hash:** `SHA256:PENDING_FORTRESS_ANCHOR`
**Created:** 2026-01-26
**Approved:** CEO (Tier-0)
