# CNRP-001 Orchestrator Schedule Configuration

**CEO Review Document**
**Classification:** STRATEGIC-CONSTITUTIONAL (Class A+)
**Prepared By:** STIG (CTO)
**Date:** 2026-01-07
**Status:** PENDING CEO APPROVAL

---

## Executive Position (Affirmed)

> "Clocks trigger. Brainstems decide."

| Component | Role | Authority |
|-----------|------|-----------|
| **Windows Task Scheduler** | Smoke detector | NONE |
| **FjordHQ Orchestrator** | Brainstem | FULL |

**Decision:** CNRP daemons execute ONLY through orchestrator.

---

## Causal Chain Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CNRP-001 CAUSAL CHAIN                           │
│                  (Orchestrator-Native Execution)                     │
└─────────────────────────────────────────────────────────────────────┘

    ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
    │    R1    │ ───► │    R2    │ ───► │    R3    │ ───► │    R4    │
    │   CEIO   │      │   CRIO   │      │   CDMO   │      │   VEGA   │
    │  Gate G2 │      │  Gate G3 │      │  Gate G3 │      │  Gate G1 │
    └──────────┘      └──────────┘      └──────────┘      └──────────┘
         │                 │                 │                 │
         ▼                 ▼                 ▼                 ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
    │ Evidence │      │  Graph   │      │ Hygiene  │      │Integrity │
    │ Refresh  │      │ Rebuild  │      │Attestation│     │ Monitor  │
    └──────────┘      └──────────┘      └──────────┘      └──────────┘

    ════════════════════════════════════════════════════════════════
    CHAIN FAILURE POLICY: HALT AND ESCALATE (Never skip phases)
    ════════════════════════════════════════════════════════════════
```

---

## Schedule Configuration

### Primary Schedule (Orchestrator)

| Phase | Daemon | Schedule | Trigger | Gate |
|-------|--------|----------|---------|------|
| **R1** | `ceio_evidence_refresh_daemon.py` | Every 4h | Time-based | G2 |
| **R2** | `crio_alpha_graph_rebuild.py` | +5m after R1 | Chain-triggered | G3 |
| **R3** | `cdmo_data_hygiene_attestation.py` | +2m after R2 | Chain-triggered | G3 |
| **R4** | `vega_epistemic_integrity_monitor.py` | +1m after R3 | Chain-triggered | G1 |
| **R4** | (same) | Every 15m | Continuous monitor | G1 |

### Execution Timeline (24h)

```
Hour │ 00  01  02  03  04  05  06  07  08  09  10  11  12  13  14  15  16  17  18  19  20  21  22  23
─────┼────────────────────────────────────────────────────────────────────────────────────────────────
 R1  │ ██                  ██                  ██                  ██                  ██
 R2  │  █                   █                   █                   █                   █
 R3  │  █                   █                   █                   █                   █
 R4  │  █                   █                   █                   █                   █
     │
 R4  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
mon  │ (every 15 minutes - continuous integrity monitoring)

Legend: ██ = Full chain execution   █ = Chained phase   ░ = Standalone R4 monitor
```

### Anchor Times (UTC)

| Cycle | R1 Start | R2 Start | R3 Start | R4 Start |
|-------|----------|----------|----------|----------|
| 1 | 00:00 | 00:05 | 00:07 | 00:08 |
| 2 | 04:00 | 04:05 | 04:07 | 04:08 |
| 3 | 08:00 | 08:05 | 08:07 | 08:08 |
| 4 | 12:00 | 12:05 | 12:07 | 12:08 |
| 5 | 16:00 | 16:05 | 16:07 | 16:08 |
| 6 | 20:00 | 20:05 | 20:07 | 20:08 |

---

## Windows Scheduler Role (WATCHDOG ONLY)

```
┌─────────────────────────────────────────────────────────────────────┐
│              WINDOWS TASK SCHEDULER CONFIGURATION                   │
│                    (Health Monitor Only)                             │
└─────────────────────────────────────────────────────────────────────┘

    Task Name: FjordHQ-Orchestrator-Heartbeat
    Schedule:  Every 5 minutes
    Command:   python orchestrator_v1.py --healthcheck

    ┌────────────────────────────────────────────────────────────────┐
    │                      PERMITTED ACTIONS                          │
    ├────────────────────────────────────────────────────────────────┤
    │  ✓ Check orchestrator health                                   │
    │  ✓ Alert LINE if orchestrator down                             │
    │  ✓ Alert CEO if evidence staleness > 20h                       │
    │  ✓ Log heartbeat status                                        │
    └────────────────────────────────────────────────────────────────┘

    ┌────────────────────────────────────────────────────────────────┐
    │                     PROHIBITED ACTIONS                          │
    ├────────────────────────────────────────────────────────────────┤
    │  ✗ Execute CNRP daemons directly                               │
    │  ✗ Modify database state                                       │
    │  ✗ Bypass orchestrator for any cognitive task                  │
    │  ✗ Make decisions on behalf of agents                          │
    └────────────────────────────────────────────────────────────────┘
```

---

## Escalation Matrix

| Level | Trigger | Target | Response Time | Authority |
|-------|---------|--------|---------------|-----------|
| **L1** | R1/R2 failure, slow orchestrator | LINE | 5 minutes | Restart, retry |
| **L2** | R3 failure, hygiene contamination | CDMO | 15 minutes | Investigate, cleanup |
| **L3** | R4 violation, chain halt, integrity breach | CEO | IMMEDIATE | Full authority |

---

## Governance Compliance

| ADR | Requirement | Status |
|-----|-------------|--------|
| **ADR-017** | All cognition through orchestrator | COMPLIANT |
| **ADR-013** | evidence_nodes is canonical source | COMPLIANT |
| **ADR-004** | Gate authorization required | COMPLIANT |
| **ADR-002** | All actions logged to governance | COMPLIANT |

---

## Files Created

| File | Purpose |
|------|---------|
| `05_ORCHESTRATOR/config/cnrp_schedule.json` | Schedule configuration (this document in JSON) |
| `05_ORCHESTRATOR/cnrp_chain_executor.py` | Orchestrator-native chain executor |

---

## CEO Approval

**Decision Points:**

- [x] Approve causal chain architecture (R1 → R2 → R3 → R4)
- [x] Approve 4-hour refresh cycle with 15-minute R4 monitoring
- [x] Approve Windows Scheduler as watchdog-only
- [x] Approve escalation matrix

**Signature Block:**

```
CEO Approval: APPROVED
Date: 2026-01-07T02:00:00Z
Directive Reference: CEO-DIR-2026-009-B
Integration Status: COMPLETE (orchestrator_v1.py v1.1.0)
```

---

## Implementation Command

Once approved, activate with:

```bash
# Full cycle execution (via orchestrator)
python 05_ORCHESTRATOR/cnrp_chain_executor.py --full-cycle

# R4 standalone monitor (every 15 minutes)
python 05_ORCHESTRATOR/cnrp_chain_executor.py --r4-monitor
```

---

*Prepared by STIG (CTO) for CEO Review*
*Classification: STRATEGIC-CONSTITUTIONAL (Class A+)*
