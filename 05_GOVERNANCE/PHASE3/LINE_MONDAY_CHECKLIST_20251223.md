# CEO DIRECTIVE: MONDAY MORNING - LINE EXECUTION CHECKLIST

**Role:** LINE (Broker Operations)
**Objective:** Clean broker state and hand off a verified zero-exposure system for re-enablement
**Mode:** PAPER | EXECUTION FREEZE ACTIVE
**Date:** Monday, December 23, 2025

---

## 09:30 AM ET - Automatic Liquidation (No Action Required)

Pre-queued MARKET SELL orders execute at market open:

| Symbol | Action | Qty | Order ID |
|--------|--------|-----|----------|
| MSTR | SELL | 1088 | b7c2ceaf-f2d4-41b2-ae4f-3413bf6600b9 |
| NVDA | SELL | 86 | 91bdd9a3-d40a-438e-b863-ffcfcadc2302 |

**No manual order placement or modification permitted.**

**LINE action:** Observe execution only.

---

## 09:35 AM ET - Fill Verification

### Command:
```bash
python reenable_runbook_executor.py --phase 1
```

### Verify Explicitly:

| Check | Expected |
|-------|----------|
| Both orders | FILLED |
| MSTR position | 0 |
| NVDA position | 0 |
| Pending orders | 0 |
| Margin usage | 0 |
| Cash balance | >= 0 |

### If Any Check Fails:
- **STOP**
- Do not proceed
- Execution remains frozen
- Escalate to CEO + STIG immediately

---

## 09:40 AM ET - Broker Snapshot & Reconciliation

### Commands:
```bash
python broker_reconciliation_daemon.py --once
python reenable_runbook_executor.py --phase 2
```

### Verify:

| Check | Expected |
|-------|----------|
| Broker snapshot | Captured post-liquidation |
| Divergence alerts | None (high/medium) |
| FHQ open trades | 0 |
| Database state | Mirrors broker truth |

### If Divergence Detected:
- **STOP**
- Do not proceed
- Escalate to STIG

---

## Post-Verification Handoff

Once Phase 1 and Phase 2 are confirmed **PASS**:

1. Notify STIG that broker state is clean
2. Await VEGA re-enablement attestation
3. Do not modify execution settings
4. Do not lift freeze
5. Do not restart any daemons

**LINE's role is complete at this point.**

---

## What LINE Must NOT Do

| Prohibition | Reason |
|-------------|--------|
| Do not submit new orders | Auto-liquidation handles this |
| Do not retry or "help" failed fills | Escalate instead |
| Do not restart execution services | Freeze must remain active |
| Do not change EXECUTION_FREEZE | CEO/STIG authorization required |
| Do not approve re-enablement | VEGA's responsibility |

---

## LINE Success Condition

LINE succeeds when:

- [ ] Broker is flat (0 positions)
- [ ] Margin is zero
- [ ] Snapshot is clean
- [ ] System remains frozen
- [ ] Handoff is clean and documented
- [ ] No further action taken unless explicitly requested

---

## Summary

**This is a clean, low-stress Monday open.**

LINE's job is:
- **Observation**
- **Verification**
- **Disciplined handoff**

Nothing more.

---

**Authority:** CEO Directive
**Classification:** OPERATIONAL
**Date Issued:** 2025-12-21
