# IoS-013 — Agent State Protocol Engine (ASPE)

**Canonical Version:** 2026.PROD.G0
**Status:** G0_SUBMITTED
**Owner:** STIG (CTO & Technical Authority)
**ADR Reference:** ADR-018 Agent State Reliability Protocol (ASRP)
**Authority Chain:** CEO Execution Order → ADR-018 → ADR-013 → ADR-016

---

## 1. Purpose & Strategic Mandate

IoS-013 ASPE is the **exclusive implementation** of ADR-018 Agent State Reliability Protocol (ASRP). It provides atomic state vector synchronization for all FjordHQ agents, ensuring:

- **Zero drift** in agent perception
- **Deterministic coordination** across LIDS–ACL–DSL–RISL (ADR-017)
- **Immutable auditability** of all decisions
- **Fail-closed default** (Zero-Trust runtime)

ASPE is a **non-bypassable precondition** for intelligence and autonomy.

---

## 2. Constitutional Foundation

### 2.1 The Synchrony Requirement (Non-Negotiable)

No agent may initiate reasoning, forecasting, or action unless a fresh, verified Shared State has been atomically retrieved from IoS-013.

This applies universally to:
- **Tier-1 Executives:** LARS, STIG, FINN, VEGA
- **Tier-2 Sub-Executives:** CFAO, CSEO, CEIO, CDMO, LINE
- **Tier-3 Units:** CODE, pipelines, orchestrators

### 2.2 Atomic Synchronization Principle

Agents may not read state objects individually. They must retrieve:

```
state_vector = {defcon, regime, strategy, hash, timestamp}
```

Where all fields:
- Are generated in the same system tick
- Share the same composite hash
- Reflect the same authoritative snapshot

**Torn-read prohibition:** If any component fails validation, the entire retrieval is invalid.

---

## 3. State Vector Components (v1 Canonical Set)

| Component | Authority | Source Table | Description |
|-----------|-----------|--------------|-------------|
| `current_defcon` | STIG (ADR-016) | `fhq_governance.system_state` | Operational safety posture |
| `btc_regime` | FINN (IoS-003) | `fhq_research.regime_predictions_v2` | Market condition truth |
| `canonical_strategy` | LARS (IoS-004) | `fhq_governance.canonical_strategy` | Active strategic posture |

No additional state objects may be introduced without G4 approval.

---

## 4. Schema Architecture

### 4.1 Core Tables

| Table | Purpose |
|-------|---------|
| `fhq_governance.canonical_strategy` | Active strategy posture (LARS authority) |
| `fhq_governance.shared_state_snapshots` | Atomic state vectors |
| `fhq_governance.state_retrieval_log` | Audit trail for retrievals |
| `fhq_governance.output_bindings` | Links outputs to state hashes |
| `fhq_governance.asrp_violations` | Class A governance violations |

### 4.2 Core Functions

| Function | Purpose |
|----------|---------|
| `create_state_snapshot()` | Atomically capture current state |
| `retrieve_state_vector(agent_id, tier)` | Fail-closed state retrieval |
| `vega_validate_state_request(agent, hash, action)` | VEGA rejection integration |

---

## 5. Fail-Closed Semantics (Zero-Trust)

### 5.1 Halt-On-Silence Rule

If IoS-013 is:
- Unreachable
- Delayed beyond latency threshold
- Returns corrupted state
- Returns hash mismatch
- Exhibits inconsistent authority

Then the system must immediately **HALT**.

### 5.2 No Local Caching

No agent may:
- Reuse previous state
- Fall back to cached local state
- Generate synthetic substitutes
- Guess missing state

Local caching is classified as an ADR-018 breach and a **Class-A governance violation**.

### 5.3 DEFCON Escalation

Any ASRP failure automatically triggers:
- Minimum DEFCON YELLOW (execution freeze)
- VEGA review
- STIG infrastructure audit

---

## 6. Output Binding Requirement

Every agent-produced artifact must embed the `state_snapshot_hash` that governed the decision.

### 6.1 Bound Output Types

- Reasoning outputs
- Strategy proposals
- Execution plans
- Code artifacts
- Governance decisions
- Trades and allocations
- Insight Packs, Skill Reports, Foresight Packs

### 6.2 Immutable Link

Every output must include:
```json
{
  "state_snapshot_hash": "d8815b8e...",
  "state_timestamp": "2025-12-05T12:18:10Z",
  "agent_id": "FINN"
}
```

**No agent output is valid without its contextual fingerprint.**

---

## 7. Enforcement & Violations

### 7.1 Class A Governance Violations

Any attempt to:
- Bypass ASRP
- Use stale or uncoupled state
- Produce output without state_hash
- Override ownership boundaries
- Operate after an invalid read

Constitutes a **Class-A violation** and triggers ADR-009 suspension.

### 7.2 Isolation & Containment

Under RISL (ADR-017), agents exhibiting drift or mismatch must be:
- Isolated immediately
- Quarantined from the orchestration bus
- Prevented from further reasoning

Reintegration requires VEGA approval.

---

## 8. Usage Guide

### 8.1 Python API

```python
from ios013_aspe_engine import ASPEEngine, get_state_vector

# Option 1: Convenience function
state = get_state_vector("FINN")
if not state.is_valid:
    raise Exception("ASRP HALT: Cannot proceed")

# Option 2: Engine instance
engine = ASPEEngine()
state = engine.retrieve_state_vector("LARS", "TIER-1")

# Check permissions
if state.allows_trading:
    # Execute trade
    pass
elif state.allows_execution:
    # Paper trading only
    pass
else:
    # HALT
    pass
```

### 8.2 SQL Direct Access

```sql
-- Retrieve current state vector
SELECT * FROM fhq_governance.retrieve_state_vector('FINN', 'TIER-2');

-- Create new snapshot (STIG only)
SELECT fhq_governance.create_state_snapshot();

-- Validate output binding
SELECT * FROM fhq_governance.vega_validate_state_request('FINN', 'hash...', 'TRADE');
```

---

## 9. Governance Integration

### 9.1 ADR-013 — Truth Architecture
ASPE stores summaries and pointers only. Truth itself remains in canonical schemas.

### 9.2 ADR-016 — Safety
`current_defcon` gating is evaluated as part of the atomic vector.

### 9.3 ADR-017 — MIT Quad
ASPE delivers the coordination substrate required by:
- **LIDS:** Truth depends on regime
- **ACL:** Coordination depends on shared strategy
- **DSL:** Allocation depends on DEFCON and strategy
- **RISL:** Immunity depends on state integrity

### 9.4 ADR-018 — ASRP
IoS-013 is the exclusive technical executor of ADR-018. No alternative implementations are allowed.

---

## 10. Lifecycle & Evolution

### 10.1 Amendments
Any change to atomicity semantics, state object definitions, authority mapping, or fail-closed logic requires **G4 CEO approval**.

### 10.2 Expansion
New Shared State fields require:
- FINN causal-truth approval
- STIG schema & integrity approval
- VEGA governance paper
- CEO G4 ratification

### 10.3 Deprecation
State deprecation follows ADR-015 lifecycle governance.

---

## 11. Current State

**As of 2025-12-05:**

| Component | Value | Authority |
|-----------|-------|-----------|
| DEFCON | GREEN | STIG |
| BTC Regime | BULL (0.60) | FINN |
| Strategy | NEUTRAL (0.00) | LARS |
| State Hash | `d8815b8e...` | STIG |
| Is Valid | TRUE | - |

---

## 12. Signatures

**CEO** — FjordHQ (Mandate Authority)
**STIG** — Technical Authority & Owner
**LARS** — Strategic Authority
**FINN** — Research Authority
**LINE** — Execution Authority
**VEGA** — Governance & Compliance

---

*IoS-013 ASPE is Constitutional Law under ADR-018.*
*Effective Immediately per CEO Execution Order.*
