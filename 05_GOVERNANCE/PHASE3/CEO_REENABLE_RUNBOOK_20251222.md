# CEO DIRECTIVE - Monday Re-Enablement Runbook

**Directive ID:** CEO-REENABLE-2025-12-22
**Scope:** Lift EXECUTION_FREEZE and remove daemon kill switch
**Precondition:** All broker positions flattened, margin cleared
**Authority:** CEO
**Enforcement:** STIG (gates), LINE (broker ops), VEGA (attestation)

---

## 0. Objective

Restore the FINN → Execution pipeline to an institutional-safe active state after liquidation and reconciliation, with hard guarantees:

- No open positions at broker
- No margin usage
- Database reconciled to broker truth
- Execution gates verified in a dry-run
- Re-enablement is reversible within minutes

---

## Phase 1 - Market Cleanup

**Owner:** LINE
**Goal:** Remove all residual broker exposure from the incident.

### Actions:

1. ~~Flatten broker positions at market open:~~
   - ~~MSTR 1088~~
   - ~~NVDA 86~~

**UPDATE 2025-12-21T02:10:00Z:** GTC MARKET sell orders are already queued.
Orders will execute automatically at Monday market open.

| Order ID | Symbol | Qty | Status |
|----------|--------|-----|--------|
| b7c2ceaf-f2d4-41b2-ae4f-3413bf6600b9 | MSTR | 1088 | ACCEPTED |
| 91bdd9a3-d40a-438e-b863-ffcfcadc2302 | NVDA | 86 | ACCEPTED |

2. Verify orders are filled and positions are zeroed.
3. Verify cash is non-negative and margin is not in use.

### Acceptance Criteria (Phase 1):

| Criterion | Requirement |
|-----------|-------------|
| Broker positions | 0 |
| Pending orders | 0 |
| Cash | ≥ 0 |
| Margin usage | none |

**If any criterion fails, stop. Execution stays frozen.**

### Verification Command:
```bash
python reenable_runbook_executor.py --phase 1
```

---

## Phase 2 - Broker Truth Reconciliation

**Owner:** STIG
**Goal:** Ensure FHQ mirrors broker truth.

### Actions:

1. Run reconciliation once to capture a broker snapshot post-liquidation:
   ```bash
   python broker_reconciliation_daemon.py --once
   ```

2. Confirm FHQ shows:
   - No open trades that claim to be OPEN without broker order id
   - No divergence alerts of high/medium severity

### Acceptance Criteria (Phase 2):

| Criterion | Requirement |
|-----------|-------------|
| Broker snapshot | Exists, timestamped after liquidation |
| Divergence | None (high/medium) |
| FHQ open trades | 0 |

**If any criterion fails, stop. Fix reconciliation semantics first.**

### Verification Command:
```bash
python reenable_runbook_executor.py --phase 2
```

---

## Phase 3 - Pre-Reenable Safety Gate

**Owner:** STIG
**Goal:** Prove that the failure class cannot execute again even if signals exist.

### Required Checks:

**Execution Boundary Controls:**
- G2_INTERNAL_EXECUTION = LOCKED
- NEW_EXECUTION_MODES = LOCKED
- SIMULATION_MODE = LOCKED
- Only BROKER_EXECUTION permitted

**Broker Truth Gating:**
- Negative cash gate blocks
- Projected exposure gate blocks
- Same-symbol accumulation gate blocks

**Signal Readiness:**
- DORMANT signals may exist, but no execution occurs during freeze

### Acceptance Criteria (Phase 3):

| Criterion | Requirement |
|-----------|-------------|
| All controls | Remain LOCKED as declared |
| Gates | Demonstrate deterministic blocking under adverse broker state |
| Hidden paths | None exist |

### Verification Command:
```bash
python reenable_runbook_executor.py --phase 3
```

---

## Phase 4 - VEGA Re-Enablement Attestation

**Owner:** VEGA
**Goal:** Independent validation of readiness to lift freeze.

### VEGA Must Attest:

1. Phase 1 and Phase 2 acceptance criteria are satisfied
2. No OPEN trade can exist without broker_order_id
3. Kill switch removal and freeze lift do not bypass gates
4. No valid scenario is blocked improperly
5. Re-enable procedure includes rollback

### Acceptance Criteria (Phase 4):

| Criterion | Requirement |
|-----------|-------------|
| VEGA attestation | REENABLEMENT_APPROVED issued |
| Attestation includes | Snapshot ID(s) and decision rationale |

**No attestation, no re-enable.**

### Verification Command:
```bash
python reenable_runbook_executor.py --phase 4
```

---

## Phase 5 - Controlled Re-Enablement

### Two-Person Rule:
- **CEO** authorizes
- **STIG** executes the change
- **LINE** stands by to intervene broker-side if needed

### Change Steps:

1. Remove daemon hard kill switch (containment line)
2. Set execution gateway freeze to FALSE
3. Perform a single-cycle dry run with execution disabled at broker layer
4. Perform a single-cycle live-paper run with very small notional cap

### Commands:
```bash
# Dry run (no changes)
python reenable_runbook_executor.py --phase 5

# Execute re-enablement (requires CEO authorization)
python reenable_runbook_executor.py --phase 5 --execute
```

### Acceptance Criteria (Phase 5):

| Criterion | Requirement |
|-----------|-------------|
| Daemon starts | Completes a cycle without exceptions |
| Order submission | None unless all gates pass |
| Gate failure | Stops execution deterministically |
| Broker truth checks | Match the broker snapshot |

---

## Phase 6 - Post-Reenable Monitoring Window

**Owner:** STIG, with VEGA oversight
**Duration:** First 60-120 minutes of market session (paper)

### Monitor:
- Order rate
- Position count
- Single-symbol concentration
- Divergence alerts
- Cash / margin

### Stop Condition (hard):
- Any high/medium divergence
- Any margin usage
- Any unexpected position increase
- Any mismatch between broker and FHQ

**Immediate response: re-freeze execution.**

---

## Rollback Plan

Rollback must be possible without debate.

### Rollback Triggers:
- Any stop condition hits
- Any unexpected broker state change
- Any logging anomaly

### Rollback Command:
```bash
python reenable_runbook_executor.py --rollback
```

### Rollback Actions:
1. Set EXECUTION_FREEZE = TRUE
2. Re-enable daemon kill switch if needed
3. Capture broker snapshot
4. Open a governance incident record

---

## CEO One-Liner to STIG for Monday

Use this as the single instruction that anchors everything:

> "Proceed with re-enablement only after Phase 1 liquidation and Phase 2 reconciliation meet acceptance criteria, and VEGA issues REENABLEMENT_APPROVED. Otherwise maintain freeze."

---

## Current Status (as of 2025-12-21T02:10:00Z)

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | FAILED | Positions exist, orders queued for Monday |
| Phase 2 | PASSED | Snapshot exists, no divergences |
| Phase 3 | PASSED | All gates functional, freeze active |
| Phase 4 | PENDING | Awaiting VEGA post-liquidation |
| Phase 5 | BLOCKED | Requires Phase 1-4 to pass |

---

**Document Authority:** CEO
**Prepared by:** STIG (CTO)
**Classification:** CRITICAL GOVERNANCE
**Date:** 2025-12-21
