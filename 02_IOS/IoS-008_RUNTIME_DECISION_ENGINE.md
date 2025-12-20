# IoS-008 — Runtime Decision Engine

**Canonical Version:** 2026.PROD.G0
**Status:** ACTIVE (G0 Complete)
**Owner:** LARS (Strategy)
**Technical Authority:** STIG (CTO)
**Governance:** VEGA
**Classification:** Tier-1 Critical

---

## 1. Executive Summary

IoS-008 is the **Will** of FjordHQ.

It converts probabilistic insight into deterministic intent:

```
Sensing (IoS-002/006) → Reasoning (IoS-007) → Self-Awareness (IoS-005) → DECISION (IoS-008)
```

IoS-008 produces ONE immutable, hash-chained `DecisionPlan` and transmits it to IoS-012 (Execution) through a constitutional "Air-Gap".

**IoS-008 decides. IoS-012 acts.**

---

## 2. The Trinity Requirement

Three green lights required for any decision:

| Input | Component | Question | Role |
|-------|-----------|----------|------|
| IoS-003 | Regime | "Is this safe?" | Gatekeeper (Veto) |
| IoS-007 | Causal Graph | "Is the wind aligned?" | Directional Driver |
| IoS-005 | Skill Score | "Are we competent today?" | Risk Damper |

Missing input = `NO_DECISION`

---

## 3. The Formula

```
Alloc = Base × RegimeScalar × CausalVector × SkillDamper
```

### 3.1 RegimeScalar (G0 Configuration)

| Regime | Scalar | Mode |
|--------|--------|------|
| STRONG_BULL | 1.0 | LONG_ONLY |
| BULL | 0.8 | LONG_ONLY |
| RANGE_UP | 0.6 | LONG_ONLY |
| NEUTRAL | 0.5 | LONG_ONLY |
| MICRO_BULL | 0.4 | LONG_ONLY |
| RANGE_DOWN | 0.3 | LONG_ONLY |
| PARABOLIC | 0.25 | LONG_ONLY |
| CHOPPY | 0.2 | LONG_ONLY |
| **BEAR** | **0.0** | Capital Preservation |
| **STRONG_BEAR** | **0.0** | Capital Preservation |
| **BROKEN** | **0.0** | System Anomaly |

**G0 Rationale:** Validate engine with Capital Preservation first. Short logic enabled in G2.

### 3.2 CausalVector

Normalized sum of edge strengths from IoS-007:
- Liquidity ↑ → Causal > 1
- Liquidity ↓ → Causal < 1
- Range: [0.5, 2.0]

### 3.3 SkillDamper

| FSS Range | Damper | State |
|-----------|--------|-------|
| 0.0 - 0.4 | 0.0 | FREEZE (Capital Freeze) |
| 0.4 - 0.5 | 0.25 | REDUCED |
| 0.5 - 0.6 | 0.5 | CAUTIOUS |
| 0.6 - 0.8 | 1.0 | NORMAL |
| 0.8 - 1.0 | 1.0 | HIGH |

System cuts itself down when it loses precision.

---

## 4. DecisionPlan Schema

```json
{
  "decision_id": "UUID-v4",
  "timestamp": "2026-05-12T14:30:00Z",
  "valid_until": "2026-05-12T14:45:00Z",
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
```

### TTL Enforcement (IRONCLAD)

IoS-012 MUST reject any plan where:
```
current_time > valid_until
```

Maximum TTL: 15 minutes.

---

## 5. Database Schema

### Tables Created

| Table | Purpose |
|-------|---------|
| `fhq_governance.decision_log` | Append-only decision audit trail |
| `fhq_governance.regime_scalar_config` | Regime → Scalar mapping |
| `fhq_governance.skill_damper_config` | FSS → Damper curve |
| `fhq_governance.decision_sequence` | Hash chain tracker |

### Functions

| Function | Purpose |
|----------|---------|
| `compute_decision_plan(asset_id, base_alloc)` | Deterministic decision computation |

---

## 6. Governance Constraints

### 6.1 Read-Only Mandate
IoS-008 cannot write upstream (IoS-003, IoS-005, IoS-007).

### 6.2 No-Execution Rule
IoS-008 may NEVER:
- Hold API keys
- Contact exchanges
- Send orders

Violation = Type A Governance Violation

### 6.3 Decision Logging
All plans must:
- Be hash-chained
- Be signed (Ed25519)
- Be stored in `fhq_governance.decision_log`

Without this → plan invalid

---

## 7. Gate Status

| Gate | Status | Date | Notes |
|------|--------|------|-------|
| G0 | ✅ COMPLETE | 2025-12-01 | Schema + Logic deployed |
| G1 | PENDING | - | Logic Core validation |
| G2 | PENDING | - | Historical Replay (10yr) |
| G3 | PENDING | - | IoS-012 Handover |
| G4 | PENDING | - | Constitutional Activation |

---

## 8. Dependencies

| Upstream | Purpose |
|----------|---------|
| IoS-003 | Regime classification |
| IoS-005 | Skill score / calibration |
| IoS-007 | Causal graph edges |

| Downstream | Purpose |
|------------|---------|
| IoS-012 | Execution (receives DecisionPlans) |

---

## 9. Migration History

| Migration | Date | Description |
|-----------|------|-------------|
| 051_ios008_runtime_decision_engine.sql | 2025-12-01 | G0 Foundation |

---

*"Probabilistic Insight → Deterministic Intent"*

**The Will of FjordHQ.**
