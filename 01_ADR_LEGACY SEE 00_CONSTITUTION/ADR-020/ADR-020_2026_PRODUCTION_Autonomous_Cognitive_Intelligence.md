# ADR-020 — Autonomous Cognitive Intelligence (ACI) Protocol

**Canonical Version:** 2026.PROD.1
**Status:** ACTIVE / TIER-1 CONSTITUTIONAL
**Date of Enactment:** 08 December 2025
**Issued by:** CEO, FjordHQ
**Governing Authorities:** FINN (Method), STIG (Runtime), VEGA (Compliance)
**Dependencies:** ADR-001, ADR-003, ADR-004, ADR-010, ADR-012, ADR-013, ADR-016, ADR-017, ADR-018
**Classification:** TIER-1 CONSTITUTIONAL

---

## 1. Executive Summary

ADR-020 establishes **Autonomous Cognitive Intelligence (ACI)** as a constitutional capability within FjordHQ — the intelligence layer responsible for:

- dynamic research planning
- recursive fact-finding
- causal inference
- epistemic uncertainty measurement
- and aggressive truth acquisition

**ACI is authorized to think, hunt, infer and explain,**
**but it is constitutionally prohibited from making or executing financial decisions.**

The protocol operationalizes three Deep Research architectures:

1. **Search-in-the-Chain** — reasoning and retrieval interleaved dynamically
2. **InForage Logic** — information-gain optimization under cost and latency constraints
3. **IKEA Boundary Protocol** — strict separation of internal knowledge vs verifiable fact

ACI is a **LIDS + ACL capability** under ADR-017's MIT Quad and has **Zero Execution Authority (ZEA)** under DSL.

---

## 2. Strategic Mandate

The mission of ACI is:

> **To industrialize Epistemic Certainty at scale.**

Where IoS-003 (Meta-Perception) tells the system *what is happening*,
ACI determines *why it is happening* — with evidence, not intuition.

### ACI is empowered to:

- autonomously generate hypotheses
- initiate multi-step research loops
- self-correct when evidence contradicts its assumptions
- consume compute/API budgets to purchase certainty (ADR-012 compliant)
- detect causal patterns that matter for alpha generation

### But ACI may never:

- touch execution
- modify strategy
- alter any canonical database
- issue directives to LINE or DSL

**It is the brain, not the hands.**

---

## 3. The ACI Cognitive Architecture (The Loop)

All ACI agents MUST operate inside a deterministic, auditable cognitive loop pinned under ADR-018.

### 3.1 Phase 1 — Dynamic Planning (Search-in-the-Chain)

ACI plans are non-static. Every retrieval modifies the plan.

**Input:**
- LARS query
- System anomaly (IoS-003, IoS-010, VEGA discrepancy)

**Action:**
- Generate ResearchPlan_v1
- Identify subgoals
- Predict where uncertainty is greatest

**Constraint:**
If the first retrieval disproves the premise, the entire plan must be rewritten immediately.

### 3.2 Phase 2 — Information Acquisition (InForage Logic)

ACI must acquire information using an economic search model:

- High information-gain queries → permitted
- Low information-gain queries → rejected
- API cost ceilings → enforced by STIG (ADR-012)
- Web-agent fallback permitted only when structured APIs fail

ACI must stop when expected information-gain falls below cost threshold.

### 3.3 Phase 3 — Knowledge Arbitration (IKEA Protocol)

ACI must classify every claim as:

- **Internal reasoning** (allowed from parametric memory)
- **External fact** (requires citation + retrieval)

**Facts without sources are illegal.**

Violation of IKEA is a **Class B Governance Violation**.

### 3.4 Phase 4 — Causal Synthesis

ACI must output:

- causal graph of findings
- uncertainty distribution
- evidence chain
- confidence thresholds
- contradictions flagged explicitly

**ACI is forbidden from masking uncertainty.**

---

## 4. MIT Quad Integration (ADR-017 Alignment)

ACI is bound to the MIT Quad architecture:

| MIT Pillar | ACI Role |
|------------|----------|
| **LIDS (Truth)** | Primary causal inference engine; validator for signals (IoS-006) and Alpha Graph (IoS-007). |
| **ACL (Coordination)** | Uses Orchestrator to delegate sub-tasks to Fact-Check, Retrieval, Reasoning Units. Respects CEIO boundaries. |
| **DSL (Execution)** | HARD FIREWALL — ACI cannot issue or influence trades. |
| **RISL (Immunity)** | Any hallucination, loop, or uncertainty spike triggers forced termination. |

ACI is therefore **intelligent, but constrained**.

---

## 5. Safety, Governance & Operational Law

### 5.1 DEFCON Scaling (ADR-016)

| DEFCON | ACI Behaviour |
|--------|---------------|
| 5 – GREEN | Full autonomy. Deep recursion + multimodal browsing allowed. |
| 4 – YELLOW | Cost-aware mode. Web agents disabled. Search depth reduced. |
| 3 – ORANGE | Hypothesis generation frozen. Only LARS-directed tasks allowed. |
| 2 – RED | ACI shutdown. Cognitive resources reallocated to execution systems. |
| 1 – BLACK | Total kill. No reasoning allowed. |

STIG enforces state; ACI must comply instantly.

### 5.2 Agent State Reliability (ADR-018)

Before any reasoning step, ACI must:

1. read a fresh `state_snapshot_hash`
2. attach it to output

Any output without valid state hash is invalid and rejected by FINN.

### 5.3 Hallucination Law (Zero Guessing Doctrine)

ACI must:

- abort if factual uncertainty > 20%
- classify any speculative claim as `Hypothesis`
- request verification rather than infer where unsure

### 5.4 Logging & Determinism (ADR-004, ADR-010)

Every cycle must record:

- plan evolution
- queries issued
- costs consumed
- uncertainty deltas
- evidence lineage

All must be reproducible.

---

## 6. Roles & Jurisdiction

| Role | Authority Over ACI |
|------|-------------------|
| **LARS (Strategy)** | Requests research. Consumes insights. Cannot override FINN. |
| **FINN (Methodology)** | Owns reasoning frameworks, causal inference logic, and scientific validity of outputs. |
| **STIG (Runtime)** | Enforces compute, cost, rate-limits, sandboxing, and air-gap against execution. |
| **VEGA (Compliance)** | Validates discrepancy, audits hallucination, certifies protocol adherence. |
| **CFAO (Foresight)** | Stress-tests ACI logic under future-state projections. |

No agent may override FINN on methodology or STIG on runtime authority.

---

## 7. Activation & Constitutional Status

Upon issuance and signature:

- ACI becomes a constitutionally protected intelligence layer
- All ACI agents operate strictly under ADR-020
- Any deviation constitutes a Class A/B governance violation
- STIG must enforce runtime sandboxing
- VEGA must monitor compliance continuously

**Effective 08 December 2025, ADR-020 is the Law of the Land.**

---

## 8. Signatures

| Role | Status | Date |
|------|--------|------|
| CEO | APPROVED | 2025-12-08 |
| STIG | TECHNICAL VALIDATION | 2025-12-08 |
| FINN | METHODOLOGY ALIGNED | 2025-12-08 |
| VEGA | GOVERNANCE ATTESTED | 2025-12-08 |

---

## Appendices

- **Appendix A** — Normative Mathematical Specification (Binding Reference)
- **Appendix B** — Shadow Execution Protocol (SHADOW_PAPER Mandate)

---

*Document Hash: To be computed upon registration*
*Hash Chain ID: HC-ADR020-CONSTITUTIONAL-20251208*
