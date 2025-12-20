# CEO DIRECTIVE — IoS-014 BUILD & AUTONOMOUS AGENT ACTIVATION

**FROM:** CEO
**TO:** STIG (CTO), VEGA (Governance), LINE (Runtime), FINN (Research), LARS (Strategy), CODE (Execution)
**SUBJECT:** Build and activate IoS-014 as the Autonomous Task Orchestration Engine
**DATE:** 2025-12-07
**STATUS:** ACTIVE

---

## 1. Mandate

I hereby authorize the design, implementation and activation of **IoS-014 — Autonomous Task Orchestration Engine**, with the mission to:

- orchestrate all IoS modules 001–013
- enforce economic safety (including vendor quotas)
- maintain data and model freshness
- coordinate autonomous agents end to end
- ensure continuous, auditable, and safe operation.

---

## 2. Economic Safety and Vendor Quotas

IoS-014 must implement strict vendor protection:

**STIG and CODE shall create:**

- `fhq_meta.vendor_limits` (configuration of quotas and soft ceilings)
- `fhq_meta.vendor_usage_counters` (live usage state)

**For all free-tier or quota-limited vendors:**

- Soft ceiling set to **90% of the free tier** per interval, unless explicitly overridden in config.
- IoS-014 shall **never** schedule tasks that drive a vendor above this soft ceiling.

**If a request would exceed 90%, IoS-014 must:**

1. prefer free or internal sources (for example: BINANCE for crypto before ALPHAVANTAGE),
2. fallback to cheaper or cached sources if available, or
3. gracefully skip non-critical tasks with an explicit `SKIPPED_QUOTA_PROTECTION` log.

**Under no circumstance shall we burn a free vendor tier on data that can be obtained from a free, higher quality or internal source.**

VEGA will audit this behaviour as part of ADR-012 enforcement.

---

## 3. Mode and DEFCON Requirements

- Execution mode is to be set to **PAPER_PROD** while IoS-014 is being brought online.
- All IoS-012 and IoS-013 operations are paper-only until VEGA and CEO jointly approve LIVE_PROD.
- IoS-014 must fully respect DEFCON levels as defined in ADR-016, and dynamically adjust schedules, frequencies and vendor calls accordingly.

---

## 4. Build Requirements (STIG + CODE)

STIG and CODE shall:

1. **Implement the Schedule Engine and Task DAG Engine** as a single daemon process that can run:
   - locally on Windows
   - inside Docker for future production deployments

2. **Integrate with the existing task_registry** so that:
   - all 9 currently registered tasks are executed on schedule
   - new tasks can be registered without code changes to IoS-014

3. **Implement the Vendor & Rate Limit Guard** exactly as described:
   - soft ceiling at 90%
   - vendor priority routing (for example: BINANCE before ALPHAVANTAGE for crypto)
   - backoff and degradation instead of quota exhaustion

4. **Ensure that every IoS module:**
   - is called in the correct order
   - logs success/failure and runtime
   - does not overlap with itself where reentrancy is not allowed.

---

## 5. Governance Requirements (VEGA)

VEGA shall:

1. **Validate that IoS-014:**
   - never violates vendor soft ceilings
   - does not produce stale core data (regime, OHLCV, macro) beyond agreed SLAs
   - respects DEFCON transitions and ADR-012 ceilings

2. **Define success metrics for G3:**
   - number of days with no quota exhaustion
   - maximum data staleness per domain
   - discrepancy score between expected and realized schedule

3. **Sign off** on promotion from G2 to G3 and finally to G4.

---

## 6. Runtime Requirements (LINE + LARS + FINN)

- LINE is responsible for ensuring that execution endpoints stay in paper mode during the build and initial runtime phases.
- LARS and FINN consume IoS-014's outputs (perception, alpha, calibration and prediction ledger) as canonical operational context, not as suggestions.
- Any request to move to LIVE_PROD must come with VEGA's written attestation and a quantified risk envelope.

---

## 7. Activation Sequence

1. Bring data freshness back under 24 hours for all critical domains. ✓ COMPLETED
2. Enable IoS-014 in PAPER_PROD for continuous operation.
3. Run for a minimum of **14 days** under VEGA monitoring without:
   - vendor quota breaches
   - stale core data
   - unhandled failures in orchestrator cycles
4. After successful 14 day run:
   - STIG proposes LIVE_PROD activation
   - VEGA confirms
   - CEO issues separate directive for real-money execution with explicitly defined risk budget.

---

## Signature

**CEO APPROVED**
**Date:** 2025-12-07
**Directive ID:** CEO-DIRECTIVE-IOS014-001

---

*This directive supersedes all prior interim scheduling arrangements and establishes IoS-014 as the canonical orchestration authority for FjordHQ.*
