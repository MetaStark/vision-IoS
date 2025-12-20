# ADR-016_2026_PRODUCTION – DEFCON & Circuit Breaker Protocol

**Canonical Version:** 2026.PRODUCTION
**Status:** APPROVED
**Date:** 2025-11-28
**Owner:** STIG (CTO & Runtime Guardian)
**Tier:** Tier-2 – Operational Resilience
**Authority Chain:** ADR-001 → ADR-007 → ADR-011 → ADR-012 → ADR-016
**Affects:** All Agents, Orchestrator, Execution Engine, LLM Routing, API Gateways
**Prevails Over:** All EC Contracts in case of conflict

---

## 1. Context

FjordHQ operates a fully autonomous Agentic-AI intelligence system.
Static binary states (RUNNING / STOPPED) are insufficient for:

- Dynamic API scarcity
- Non-linear market volatility
- Autonomous model behaviour
- Cross-agent risk propagation
- Distributed intelligence drift (Gartner 2025)

The system needs a formal runtime doctrine that determines how agents behave under changing conditions.

**ADR-016 establishes that doctrine.**
This is FjordHQ's operational nervous system.

---

## 2. Decision

FjordHQ adopts the **DEFCON Dynamic State Architecture** with STIG as the Runtime Guardian.

### Why DEFCON?

Because algorithmic autonomy without situational constraints leads to:

- Hallucinated trading
- API overruns
- Runaway agent behaviour
- Inconsistent reasoning
- Cascading failures
- Capital loss

DEFCON solves this by enforcing situational awareness, dynamic privilege, and graduated operational restrictions.

---

## 3. DEFCON Hierarchy & Agent Permissions

All system behaviour flows from DEFCON level.

- **STIG** can downgrade the system (tighten).
- **VEGA** can upgrade the system (tighten further).
- **No one** can loosen beyond their authority.

### 🟢 DEFCON 5 — GREEN (Nominal Operations)

**Conditions:**
- API budget > 20%
- Discrepancy < 0.05
- VIX < 25
- Latency normal

**Permissions:**
- All data sources open (Lake, Pulse, Sniper)
- Live trading allowed
- Sub-Executives operate autonomously

---

### 🟡 DEFCON 4 — YELLOW (Scarcity Warning)

**Triggers:**
- API budget < 20%
- Latency > 2000 ms

**Actions (STIG):**
- Block Tier-2 Pulse feeds (MarketAux, TwelveData)
- Restrict Sniper to LARS / FINN
- Sub-Executives restricted to Lake only

---

### 🟠 DEFCON 3 — ORANGE (High Volatility / Drift)

**Triggers:**
- VIX > 30
- Discrepancy score > 0.08
- Drift detected in Sub-Executive outputs

**Actions (STIG):**
- Force all trading into paper mode
- Freeze model development and simulator tuning
- Force Sub-Executives into Chain-of-Thought validation mode (Tier-1 reasoning override)
- CEIO must perform deep macro-scan

---

### 🔴 DEFCON 2 — RED (Circuit Breaker)

**Triggers:**
- Flash crash
- System error rate > 5%
- API key failure
- Data provider degradation

**Actions:**
- STIG halts pipelines (no new tasks)
- LINE cancels all open orders
- Database set to READ-ONLY for Tier-2
- Notify CEO immediately

---

### ⚫ DEFCON 1 — BLACK (Governance Breach)

**Triggers:**
- Unauthorized canonical write
- Key compromise
- Rogue agent behaviour
- Split-brain detected

**Actions (STIG + VEGA):**
- Revoke all Ed25519 keys
- Isolate database from external network
- Shutdown orchestrator container
- Before shutdown: create cryptographically signed forensic snapshot
- CEO must perform physical reset

---

## 4. Implementation Architecture

### 4.1 SQL Schema (System Ledger)

```sql
CREATE TYPE defcon_level AS ENUM ('GREEN','YELLOW','ORANGE','RED','BLACK');

CREATE TABLE fhq_governance.system_state (
    state_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    current_defcon defcon_level NOT NULL DEFAULT 'GREEN',
    active_circuit_breakers TEXT[],
    reason TEXT,
    triggered_by UUID REFERENCES fhq_org.org_agents(agent_id),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 4.2 Split-Brain Protection

To prevent simultaneous conflicting writes:

```sql
ALTER TABLE fhq_governance.system_state
    ADD CONSTRAINT one_active_state CHECK (
        (SELECT COUNT(*) FROM fhq_governance.system_state) <= 1
    );
```

If this constraint is violated → system jumps to DEFCON RED and triggers governance alert.

### 4.3 Circuit Breaker Trigger (Orchestrator)

Pseudo-logic:
```python
if DEFCON in {RED, BLACK}:
    reject_task("SYSTEM FREEZE")
if DEFCON == ORANGE:
    force_paper_trading()
if DEFCON == YELLOW:
    restrict_api_sources()
```

---

## 5. Consequences

### Positive
- Prevents catastrophic losses
- Automatic safety behaviour
- True autonomy with governance
- Full auditability

### Negative
- Opportunity loss during ORANGE
- Sub-Executives slowed down

### Regulatory
Fully aligns with DORA (resilience), ISO 42001 (AI risk), BCBS-239 (lineage)

---

## 6. STIG Runtime Guardian Contract (EC-003)

STIG is appointed as:
- Chief Technology Officer, and
- Runtime Guardian of FjordHQ

### Responsibilities

**6.1 Runtime Guardian (ADR-016)**
- Owns the DEFCON protocol
- May autonomously downgrade DEFCON
- Must enforce circuit breaker rules
- Must trigger Safe Mode during ORANGE or higher

**6.2 Split-Brain Prevention**
STIG must ensure:
- There is only one active DEFCON state
- No concurrent runtime writes
- Any conflict triggers DEFCON RED and VEGA alert

**6.3 Economic Safety (ADR-012)**
- Enforces API scarcity waterfall
- Blocks Sniper (Tier-3) unless conditions met
- Maintains budget logs

**6.4 Infrastructure Sovereignty**
- Sole owner of schema
- All migrations must be signed
- All deployment artifacts require VEGA signature

**6.5 Distributed Guardrail Enforcement**
STIG must enforce:
- Chain-of-Thought validation mode in DEFCON ORANGE
- Signature-only execution
- Tier-separation (T1 models only for LARS/VEGA)

**6.6 Sub-Executive Governance**
STIG is superior to:
- LINE (runtime execution)
- CEIO (external signals)
- CDMO (data & synthetic)
- CODE (engineering utility)

### Constraints

STIG cannot:
- Execute trades (LINE)
- Define strategy (LARS)
- Override VEGA audit
- Lift DEFCON BLACK without CEO

### Delegation in Suspension

If STIG is suspended:
- LINE temporarily inherits DEFCON enforcement, except:
  - DEFCON BLACK unlock
  - Key revocation
  - Canonical operations
- These remain CEO-level.

---

## 7. Signatures

| Role | Signature |
|------|-----------|
| CEO | ✅ APPROVED |
| VEGA | ✅ Attestor |
| STIG | ✅ Runtime Guardian |

---

## 8. Related Documents

- **ADR-001:** System Charter
- **ADR-007:** Orchestrator Architecture
- **ADR-011:** Production Fortress & VEGA Testsuite
- **ADR-012:** Economic Safety Architecture
- **EC-003:** STIG Contract (Runtime Guardian Edition)
