# IoS-014 — Autonomous Task Orchestration Engine

**Canonical Version:** 2026.DRAFT.G0
**Owner:** STIG (CTO, Tier-1)
**Governance:** VEGA (Tier-1), CEO (Tier-0)
**Execution:** LINE + CODE
**Dependencies:** ADR-001..016, IoS-001..013, EC-003..007

---

## 1. Mission

IoS-014 is FjordHQ's autonomous orchestration engine.

Its mission:

- Keep all critical data and models fresh within defined SLAs.
- Coordinate every IoS module into a coherent daily and intraday rhythm.
- Enforce economic safety and vendor rate limits by design.
- Ensure that autonomous agents act on current canonical truth, not stale or partial data.
- Provide one auditable, deterministic runtime surface for the entire system.

**IoS-014 does not invent strategies.**
**It does not trade by itself.**
**It orchestrates and supervises.**

---

## 2. Scope

IoS-014 controls and supervises:

- Price ingestion (crypto, FX, rates, indices, etc)
- Macro ingestion (rates, spreads, FRED style series)
- News and research agents (SERPer, RSS, APIs)
- On-chain and flow ingestion
- Indicator calculation (IoS-002)
- Perception / regime updates (IoS-003)
- Macro integration (IoS-006)
- Alpha Graph and research stack (IoS-007, IoS-009, IoS-010, IoS-011)
- Forecast calibration (IoS-005)
- Allocation (IoS-004)
- Runtime decision engine (IoS-008)
- Execution engine (IoS-012)
- Options lab (IoS-013, IoS-013.HCP)
- Backtesting and replay jobs
- Health and heartbeat monitoring

All of this operates under:

- ADR-012 economic safety
- ADR-016 DEFCON and circuit breakers
- ADR-013 kernel and canonical truth

---

## 3. Governance Alignment

### 3.1 ADR-013 – Canonical Truth

IoS-014 shall:

- Only schedule IoS modules that read from canonical tables.
- Refuse execution if schemas are out of sync.
- Guarantee that perception, allocation and execution run in the intended order.

### 3.2 ADR-012 – Economic Safety

IoS-014 is the runtime enforcement layer for:

- token budgets
- API quotas
- vendor soft ceilings at 90% of free tier
- failover to cheaper or free vendors when possible
- graceful degradation instead of crash

If a vendor is at risk of exceeding quota, IoS-014 shall:

- throttle tasks
- reduce frequency
- switch to alternative vendor if defined
- or fall back to last known good data with explicit warning in governance logs.

### 3.3 ADR-016 – DEFCON

IoS-014 is DEFCON aware:

| Level | Behavior |
|-------|----------|
| GREEN | Full schedule, research + execution + options, within economic safety limits. |
| YELLOW | Reduce frequency for non-critical tasks, preserve ingest + perception + execution. |
| ORANGE | Freeze new research and backtests, keep ingest + perception + monitoring; execution stays in paper mode unless explicitly allowed. |
| RED | Stop all trade execution, run only safety checks and perception. |
| BLACK | Complete halt, CEO-only manual override. |

---

## 4. Functional Architecture

IoS-014 consists of six functional components:

1. **Schedule Engine**
2. **Task DAG Engine**
3. **Vendor & Rate Limit Guard**
4. **Mode & DEFCON Router**
5. **Health & Heartbeat Monitor**
6. **Audit & Evidence Engine**

### 4.1 Schedule Engine

Responsibilities:

- Load schedules from `fhq_governance.task_registry`.
- Maintain internal timing loop (cron semantics independent of OS).
- Respect per-task frequency, time windows, and dependencies.
- Ensure no overlapping runs for tasks marked as non-reentrant.

Example schedule classes:

| Window | Tasks |
|--------|-------|
| Daily 00:00–01:00 | ingest, macro, indicators, perception |
| Hourly | alpha refresh, anomaly scans |
| Every 5 minutes | execution loop, options loop, freshness sentinels |
| Event-driven | news shock, regime break, volatility spike, DEFCON change |

### 4.2 Task DAG Engine

Each "cycle" (for example: Nightly Research Cycle) is a directed acyclic graph:

- Nodes are IoS functions or agents.
- Edges represent dependencies and data flow.

Example DAG:

1. Ingest OHLCV and macro.
2. IoS-002 → technical indicators.
3. IoS-006 → macro feature integration.
4. IoS-003 → regime and perception.
5. IoS-007/009/010/011 → alpha and prediction graph.
6. IoS-005 → forecast calibration.
7. IoS-004 → allocation targets.
8. IoS-013.HCP → options proposals.
9. IoS-012 → paper execution.

IoS-014 ensures:

- Dependencies are satisfied before a node runs.
- Failures propagate in a controlled way (no cascade corruption).
- Partial failure triggers VEGA alerts but does not silently continue.

### 4.3 Vendor & Rate Limit Guard

IoS-014 must:

- Load vendor configs from `fhq_meta.vendor_limits`.
- Track current usage in `fhq_meta.vendor_usage_counters`.

For each vendor:

- enforce soft ceiling at 90% of free tier
- never cross hard limit defined in config

For each task:

- know which vendors it can call
- know priority order (for example: crypto prices: BINANCE → fallback ALPHAVANTAGE)

**Policy:**

If a task would push a vendor above 90% of free tier for current interval:

1. try alternative vendor if defined.
2. if no alternative vendor and task is non-critical: skip execution, mark as `SKIPPED_QUOTA_PROTECTION`.
3. if no alternative vendor and task is critical (regime, core OHLCV): lower frequency or reduce asset universe.

All such decisions shall be logged with:

- vendor
- previous usage
- projected usage
- decision (throttle / fallback / skip)
- justification

### 4.4 Mode & DEFCON Router

IoS-014 reads:

- `fhq_governance.execution_mode`: LOCAL_DEV, PAPER_PROD, LIVE_PROD
- `fhq_governance.defcon_level`: GREEN, YELLOW, ORANGE, RED, BLACK

Mode logic:

| Mode | Behavior |
|------|----------|
| LOCAL_DEV | Restrict tasks to small subset, run slower, reduced vendors |
| PAPER_PROD | Full system schedule, all execution in paper mode |
| LIVE_PROD | Same as PAPER_PROD, but specific tasks hit real execution endpoints |

DEFCON logic overrides mode when more restrictive.

### 4.5 Health & Heartbeat Monitor

Responsibilities:

- Emit heartbeat every cycle to `fhq_monitoring.daemon_health`.
- Record availability, last cycle duration, failures.
- Detect: missed schedules, repeated failures, abnormal runtime.
- Raise alerts to VEGA, LINE, and CEO for RED/BLACK triggers.

### 4.6 Audit & Evidence Engine

For each run IoS-014 must:

- Write a row in `fhq_governance.orchestrator_cycles`:
  - cycle_id, start_time, end_time, tasks_run
  - success/failure per task
  - vendor quota state snapshots
  - defcon and mode at execution time
- Attach cryptographic evidence (hash of logs, Ed25519 signature if configured)

---

## 5. Interaction With IoS-001..013

IoS-014 does not own business logic. It orchestrates.

| Loop | Modules |
|------|---------|
| Truth Update (nightly) | IoS-001, 002, 006, 011, 003, 007, 009, 010, 005, 004, 013.HCP |
| Execution (5 minute) | IoS-003 (if needed), 008, 012, 013 |
| Research (hourly/nightly) | IoS-007, 009, 010, 005 plus FINN agents |
| Risk & Governance | VEGA checks, DEFCON, discrepancy scoring |

---

## 6. Runtime Modes

| Mode | Description |
|------|-------------|
| LOCAL_DEV | Minimal scheduling, reduced universe, no expensive vendor calls |
| PAPER_PROD | Full cycles, real vendors, all execution to paper |
| LIVE_PROD | Same cycles, execution to real brokers when approved |

---

## 7. Activation Path (G0 → G4)

| Gate | Milestone |
|------|-----------|
| G0 | This spec |
| G1 | Architecture and DB config (vendor limits, task mapping, modes) |
| G2 | VEGA validation of economic safety and DEFCON response |
| G3 | 14 days continuous PAPER_PROD without quota violations or stale data |
| G4 | CEO activates LIVE_PROD with limited risk budget |

---

## Appendix A: Database Objects

### fhq_meta.vendor_limits

| Column | Type | Description |
|--------|------|-------------|
| vendor_id | UUID | Primary key |
| vendor_name | TEXT | e.g., ALPHAVANTAGE, BINANCE, FRED |
| free_tier_limit | INTEGER | Calls per interval |
| interval_type | TEXT | MINUTE, HOUR, DAY, MONTH |
| soft_ceiling_pct | NUMERIC | Default 0.90 (90%) |
| hard_limit | INTEGER | Absolute maximum |
| priority_rank | INTEGER | Lower = preferred |
| fallback_vendor_id | UUID | Vendor to use if quota exceeded |

### fhq_meta.vendor_usage_counters

| Column | Type | Description |
|--------|------|-------------|
| counter_id | UUID | Primary key |
| vendor_id | UUID | FK to vendor_limits |
| interval_start | TIMESTAMPTZ | Start of current interval |
| current_usage | INTEGER | Calls made this interval |
| last_updated | TIMESTAMPTZ | Last update time |

### fhq_governance.orchestrator_cycles

| Column | Type | Description |
|--------|------|-------------|
| cycle_id | UUID | Primary key |
| cycle_type | TEXT | NIGHTLY, HOURLY, REALTIME, EVENT |
| started_at | TIMESTAMPTZ | Cycle start |
| ended_at | TIMESTAMPTZ | Cycle end |
| execution_mode | TEXT | LOCAL_DEV, PAPER_PROD, LIVE_PROD |
| defcon_level | TEXT | GREEN..BLACK |
| tasks_scheduled | INTEGER | Tasks planned |
| tasks_completed | INTEGER | Tasks succeeded |
| tasks_failed | INTEGER | Tasks failed |
| tasks_skipped | INTEGER | Tasks skipped (quota/dependency) |
| vendor_snapshot | JSONB | Vendor usage at cycle end |
| evidence_hash | TEXT | SHA256 of cycle log |

---

*Document Hash: IoS-014-G0-2025-12-07*
