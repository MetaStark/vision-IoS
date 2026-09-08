IoS-014 — Autonomous Task Orchestration Engine

Canonical Version: 2026.DRAFT.G0
Owner: STIG (CTO, Tier-1)
Governance: VEGA (Tier-1), CEO (Tier-0)
Execution: LINE + CODE
Dependencies: ADR-001..016, IoS-001..013, EC-003..007

1. Mission

IoS-014 is FjordHQ’s autonomous orchestration engine.

Its mission:

Keep all critical data and models fresh within defined SLAs.

Coordinate every IoS module into a coherent daily and intraday rhythm.

Enforce economic safety and vendor rate limits by design.

Ensure that autonomous agents act on current canonical truth, not stale or partial data.

Provide one auditable, deterministic runtime surface for the entire system.

IoS-014 does not invent strategies.
It does not trade by itself.
It orchestrates and supervises.

2. Scope

IoS-014 controls and supervises:

Price ingestion (crypto, FX, rates, indices, etc)

Macro ingestion (rates, spreads, FRED style series)

News and research agents (SERPer, RSS, APIs)

On-chain and flow ingestion

Indicator calculation (IoS-002)

Perception / regime updates (IoS-003)

Macro integration (IoS-006)

Alpha Graph and research stack (IoS-007, IoS-009, IoS-010, IoS-011)

Forecast calibration (IoS-005)

Allocation (IoS-004)

Runtime decision engine (IoS-008)

Execution engine (IoS-012)

Options lab (IoS-013, IoS-013.HCP)

Backtesting and replay jobs

Health and heartbeat monitoring

All of this skjer under:

ADR-012 economic safety

ADR-016 DEFCON and circuit breakers

ADR-013 kernel and canonical truth

3. Governance Alignment
3.1 ADR-013 – Canonical Truth

IoS-014 shall:

Only schedule IoS modules that read from canonical tables.

Refuse execution if schemas are out of sync.

Guarantee that perception, allocation and execution run in the intended order.

3.2 ADR-012 – Economic Safety

IoS-014 is the runtime enforcement layer for:

token budgets

API quotas

vendor soft ceilings at 90 % of free tier

failover to cheaper or free vendors when possible

graceful degradation instead of crash

If a vendor is at risk of exceeding quota, IoS-014 shall:

throttle tasks

reduce frequency

switch to alternative vendor if defined

or fall back to last known good data with explicit warning in governance logs.

3.3 ADR-016 – DEFCON

IoS-014 is DEFCON aware:

DEFCON GREEN: full schedule, research + execution + options, within economic safety limits.

DEFCON YELLOW: reduce frequency for non-critical tasks, preserve ingest + perception + execution.

DEFCON ORANGE: freeze new research and backtests, keep ingest + perception + monitoring; execution stays in paper mode unless explicitly allowed.

DEFCON RED: stop all trade execution, run only safety checks and perception.

DEFCON BLACK: complete halt, CEO-only manual override.

4. Functional Architecture

IoS-014 consists of six functional components:

Schedule Engine

Task DAG Engine

Vendor & Rate Limit Guard

Mode & DEFCON Router

Health & Heartbeat Monitor

Audit & Evidence Engine

4.1 Schedule Engine

Responsibilities:

Load schedules from fhq_governance.task_registry.

Maintain internal timing loop (cron semantics independent of OS).

Respect per-task frequency, time windows, and dependencies.

Ensure no overlapping runs for tasks marked as non-reentrant.

Example schedule classes:

Daily 00:00–01:00: ingest, macro, indicators, perception.

Hourly: alpha refresh, anomaly scans.

Every 5 minutes: execution loop, options loop, freshness sentinels.

Event-driven: news shock, regime break, volatility spike, DEFCON change.

4.2 Task DAG Engine

Each “cycle” (for example: Nightly Research Cycle) is a directed acyclic graph:

Nodes are IoS functions or agents.

Edges represent dependencies and data flow.

Example DAG:

Ingest OHLCV and macro.

IoS-002 → technical indicators.

IoS-006 → macro feature integration.

IoS-003 → regime and perception.

IoS-007/009/010/011 → alpha and prediction graph.

IoS-005 → forecast calibration.

IoS-004 → allocation targets.

IoS-013.HCP → options proposals.

IoS-012 → paper execution.

IoS-014 ensures:

Dependencies are satisfied before a node runs.

Failures propagate in a controlled way (no cascade corruption).

Partial failure triggers VEGA alerts but does not silently continue.

4.3 Vendor & Rate Limit Guard

This is where din bekymring om gratis moduler og kvoter blir løst.

IoS-014 must:

Load vendor configs from fhq_meta.vendor_limits.

Track current usage in fhq_meta.vendor_usage_counters.

For hver vendor:

enforce soft ceiling at 90 % of free tier

never cross hard limit defined in config

For hver task:

know which vendors it can call

know priority order (for example:

crypto prices: BINANCE → fallback ALPHAVANTAGE

FX: primary vendor X → fallback vendor Y

news: SERPER → fallback RSS feeds)

Policy:

If a task would push a vendor above 90 % of free tier for current interval:

try alternative vendor if defined.

if no alternative vendor and task is non-critical:

skip execution, mark as SKIPPED_QUOTA_PROTECTION.

if no alternative vendor and task is critical (regime, core OHLCV):

lower frequency or reduce asset universe (for example: update core 4 assets only).

All such decisions shall be logged with:

vendor

previous usage

projected usage

decision (throttle / fallback / skip)

justification

This is the runtime implementation of ADR-012 in the ingest and research domain.

4.4 Mode & DEFCON Router

IoS-014 reads:

fhq_governance.execution_mode:

LOCAL_DEV

PAPER_PROD

LIVE_PROD

fhq_governance.defcon_level:

GREEN, YELLOW, ORANGE, RED, BLACK

Mode logic:

LOCAL_DEV:

restrict tasks to a small subset of assets and modules

run slower, reduced vendors, no external heavy calls

PAPER_PROD:

full system schedule

all ingestion, research, allocation, execution in paper mode

LIVE_PROD:

same as PAPER_PROD, but specific tasks are allowed to hit real execution endpoints under LINE’s control.

DEFCON logic overrides mode when more restrictive.

4.5 Health & Heartbeat Monitor

Responsibilities:

Emit heartbeat every cycle to fhq_monitoring.daemon_health.

Record availability, last cycle duration, failures.

Detect:

missed schedules

repeated failures (for example 3 consecutive regression errors)

abnormal runtime (too fast / too slow)

Raise alerts:

to VEGA

to LINE

to CEO for RED/BLACK triggers

4.6 Audit & Evidence Engine

For each run IoS-014 must:

write a row in fhq_governance.orchestrator_cycles:

cycle_id

start_time

end_time

tasks_run

success/failure per task

vendor quota state snapshots

defcon and mode at execution time

attach cryptographic evidence:

hash of logs

possibly Ed25519 signature if configured by ADR-008.

VEGA uses these to:

validate consistency

measure discrepancy

approve transitions from PAPER_PROD to LIVE_PROD.

5. Interaction With IoS-001..013

IoS-014 does not own business logic. It orchestrates.

High level:

Truth Update Loop (nightly)

IoS-001, 002, 006, 011, 003, 007, 009, 010, 005, 004, 013.HCP.

Execution Loop (5 minute)

IoS-003 (if needed), 008, 012, 013.

Research Loop (hourly / nightly)

IoS-007, 009, 010, 005 plus FINN agents.

Risk & Governance Loop

VEGA checks, DEFCON, discrepancy scoring across outputs.

IoS-014 ensures the order and timing, not the internal decisions.

6. Runtime Modes

LOCAL_DEV:

Minimal scheduling, reduced universe, no real vendors except cheap/free ones.

Good for running everything on your laptop without blowing any free tier.

PAPER_PROD:

Full cycles.

Real vendors, but all execution to paper.

LIVE_PROD:

Same cycles as PAPER_PROD.

Execution turned on for real brokers when VEGA and CEO approve.

7. Activation Path (G0 → G4)

G0: This spec.

G1: Architecture and DB config (vendor limits, task mapping, modes).

G2: VEGA validation of economic safety and DEFCON response.

G3: 14 days of continuous PAPER_PROD runtime without quota violations or stale data breaches.

G4: CEO activates LIVE_PROD, limited initially to a small risk budget.

B) CEO DIRECTIVE — ACTIVATE AUTONOMOUS AGENTS UNDER IOS-014

Dette er ordren du gir som CEO. Den er skrevet kort og skarp, men dekker vendor-bruk, 90 % regler og full autonomi i paper mode først.

CEO DIRECTIVE — IoS-014 BUILD & AUTONOMOUS AGENT ACTIVATION

FROM: CEO
TO: STIG (CTO), VEGA (Governance), LINE (Runtime), FINN (Research), LARS (Strategy), CODE (Execution)
SUBJECT: Build and activate IoS-014 as the Autonomous Task Orchestration Engine

1. Mandate

I hereby authorize the design, implementation and activation of IoS-014 — Autonomous Task Orchestration Engine, with the mission to:

orchestrate all IoS modules 001–013

enforce economic safety (including vendor quotas)

maintain data and model freshness

coordinate autonomous agents end to end

ensure continuous, auditable, and safe operation.

2. Economic Safety and Vendor Quotas

IoS-014 must implement strict vendor protection:

STIG and CODE shall create:

fhq_meta.vendor_limits (configuration of quotas and soft ceilings)

fhq_meta.vendor_usage_counters (live usage state)

For all free-tier or quota-limited vendors:

Soft ceiling set to 90 % of the free tier per interval, unless explicitly overridden in config.

IoS-014 shall never schedule tasks that drive a vendor above this soft ceiling.

If a request would exceed 90 %, IoS-014 must:

prefer free or internal sources (for example: BINANCE for crypto before ALPHAVANTAGE),

fallback to cheaper or cached sources if available, or

gracefully skip non-critical tasks with an explicit SKIPPED_QUOTA_PROTECTION log.

Under no circumstance shall we burn a free vendor tier on data that can be obtained from a free, higher quality or internal source.

VEGA will audit this behaviour as part of ADR-012 enforcement.

3. Mode and DEFCON Requirements

Execution mode is to be set to PAPER_PROD while IoS-014 is being brought online.

All IoS-012 and IoS-013 operations are paper-only until VEGA and CEO jointly approve LIVE_PROD.

IoS-014 must fully respect DEFCON levels as defined in ADR-016, and dynamically adjust schedules, frequencies and vendor calls accordingly.

4. Build Requirements (STIG + CODE)

STIG and CODE shall:

Implement the Schedule Engine and Task DAG Engine as a single daemon process that can run:

locally on Windows

inside Docker for future production deployments

Integrate with the existing task_registry so that:

all 9 currently registered tasks are executed on schedule

new tasks can be registered without code changes to IoS-014

Implement the Vendor & Rate Limit Guard exactly as described:

soft ceiling at 90 %

vendor priority routing (for example: BINANCE before ALPHAVANTAGE for crypto)

backoff and degradation instead of quota exhaustion

Ensure that every IoS module:

is called in the correct order

logs success/failure and runtime

does not overlap with itself where reentrancy is not allowed.

5. Governance Requirements (VEGA)

VEGA shall:

Validate that IoS-014:

never violates vendor soft ceilings

does not produce stale core data (regime, OHLCV, macro) beyond agreed SLAs

respects DEFCON transitions and ADR-012 ceilings

Define success metrics for G3:

number of days with no quota exhaustion

maximum data staleness per domain

discrepancy score between expected and realized schedule

Sign off on promotion from G2 to G3 and finally to G4.

6. Runtime Requirements (LINE + LARS + FINN)

LINE is responsible for ensuring that execution endpoints stay in paper mode during the build and initial runtime phases.

LARS and FINN consume IoS-014’s outputs (perception, alpha, calibration and prediction ledger) as canonical operational context, not as suggestions.

Any request to move to LIVE_PROD must come with VEGA’s written attestation and a quantified risk envelope.

7. Activation Sequence

Bring data freshness back under 24 hours for all critical domains.

Enable IoS-014 in PAPER_PROD for continuous operation.

Run for a minimum of 14 days under VEGA monitoring without:

vendor quota breaches

stale core data

unhandled failures in orchestrator cycles

After successful 14 day run:

STIG proposes LIVE_PROD activation

VEGA confirms

CEO issues separate directive for real-money execution with explicitly defined risk budget.