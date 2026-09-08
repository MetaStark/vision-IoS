# PLAN MODE: SYSTEM REALITY AUDIT — 2026-02-03

**Audit timestamp:** 2026-02-03 10:05 CET (database clock verified)
**Auditor:** STIG (EC-003_2026_PRODUCTION)
**Scope:** Full system — filesystem, database, runtime, scheduler, governance
**Mode:** READ-ONLY REALITY CAPTURE. No fixes. No narrative. No opinions.

---

## 1. SYSTEM REALITY MAP

### 1A. ADR Registry (Architecture Decision Records)

| ADR | Disk | Database (fhq_meta) | Mismatch |
|-----|------|---------------------|----------|
| ADR-001 | EXISTS | EXISTS | NO |
| ADR-002 | EXISTS | EXISTS | NO |
| ADR-003 | EXISTS | EXISTS | NO |
| ADR-004 | EXISTS | EXISTS | NO |
| ADR-005 | EXISTS | EXISTS | NO |
| ADR-006 | EXISTS | EXISTS | NO |
| ADR-007 | EXISTS | EXISTS | NO |
| ADR-008 | EXISTS | EXISTS | NO |
| ADR-009 | EXISTS | EXISTS | NO |
| ADR-010 | EXISTS | EXISTS | NO |
| ADR-011 | EXISTS | EXISTS | NO |
| ADR-012 | EXISTS | EXISTS | NO |
| ADR-013 | EXISTS | EXISTS | NO |
| ADR-013A | EXISTS | EXISTS | NO |
| ADR-014 | EXISTS | EXISTS | NO |
| ADR-015 | EXISTS | EXISTS | NO |
| ADR-016 | EXISTS | EXISTS | NO |
| ADR-017 | EXISTS | EXISTS | NO |
| ADR-018 | EXISTS | EXISTS | NO |
| ADR-019 | EXISTS | EXISTS | NO |
| ADR-020 | EXISTS | EXISTS | NO |
| ADR-021 | EXISTS | EXISTS | NO |
| ADR-022 | EXISTS | EXISTS | NO |
| ADR-023 | EXISTS | EXISTS | NO |
| ADR-024 | EXISTS | EXISTS | NO |
| MIG-200 | MISSING | EXISTS | YES — DB_NOT_ON_DISK |

**Totals:** 25 on disk, 26 in database. 1 mismatch (MIG-200).

### 1B. EC Registry (Employment Contracts)

| EC | Agent | Tier | Disk | Database (fhq_governance) | Mismatch |
|----|-------|------|------|---------------------------|----------|
| EC-001 | VEGA | Tier-1 | EXISTS | MISSING | YES — DISK_NOT_IN_DB |
| EC-002 | LARS | Tier-1 | EXISTS | MISSING | YES — DISK_NOT_IN_DB |
| EC-003 | STIG | Tier-1 | EXISTS | MISSING | YES — DISK_NOT_IN_DB |
| EC-004 | FINN | Tier-2 | EXISTS | MISSING | YES — DISK_NOT_IN_DB |
| EC-005 | LINE | Tier-2 | EXISTS | MISSING | YES — DISK_NOT_IN_DB |
| EC-006 | CODE | Tier-3 | EXISTS | MISSING | YES — DISK_NOT_IN_DB |
| EC-007 | CFAO | Tier-2 | EXISTS | MISSING | YES — DISK_NOT_IN_DB |
| EC-007_CDMO | CDMO | Tier-2 | EXISTS | MISSING | YES — DISK_NOT_IN_DB (duplicate EC number) |
| EC-008 | Enterprise | Charter | EXISTS | MISSING | YES — DISK_NOT_IN_DB |
| EC-009 | CEIO | Tier-2 | EXISTS | MISSING | YES — DISK_NOT_IN_DB |
| EC-010 | CEO | Tier-0 | EXISTS | MISSING | YES — DISK_NOT_IN_DB |
| EC-011 | CSEO | Tier-2 | EXISTS | MISSING | YES — DISK_NOT_IN_DB |
| EC-012 | CDMO | Tier-2 | EXISTS | MISSING | YES — DISK_NOT_IN_DB (second CDMO contract) |
| EC-013 | CRIO | Tier-2 | EXISTS | MISSING | YES — DISK_NOT_IN_DB |
| EC-014 | UMA | Tier-2 | EXISTS | EXISTS (ACTIVE) | NO |
| EC-015 | CPTO | Tier-2 | EXISTS | MISSING | YES — DISK_NOT_IN_DB |
| EC-018 | Meta-Alpha | Tier-2 Cognitive | EXISTS | EXISTS (ACTIVE) | NO |
| EC-019 | Human Governor | Supervisory | EXISTS | MISSING | YES — DISK_NOT_IN_DB |
| EC-020 | SitC | Tier-2 Cognitive | EXISTS | EXISTS (ACTIVE) | NO |
| EC-021 | InForage | Tier-2 Cognitive | EXISTS | EXISTS (ACTIVE) | NO |
| EC-022 | IKEA | Tier-2 Cognitive | EXISTS | EXISTS (ACTIVE) | NO |

**Totals:** 21 unique ECs on disk, 5 in database. 16 mismatches. **76% of ECs not in database.**

**EC Number Collisions:**
- EC-007 assigned to both CFAO and CDMO (two different files)
- CDMO has two contracts (EC-007 variant + EC-012)

### 1C. IoS Registry (Intelligence Operating System)

| IoS | Disk | Database (fhq_meta) | Mismatch |
|-----|------|---------------------|----------|
| IoS-001 | EXISTS | EXISTS | NO |
| IoS-002 | EXISTS | EXISTS | NO |
| IoS-003 | EXISTS | EXISTS | NO |
| IOS-003-B | EXISTS | EXISTS | NO |
| IoS-004 | EXISTS | EXISTS | NO |
| IoS-005 | EXISTS | EXISTS | NO |
| IoS-006 | EXISTS | EXISTS | NO |
| IoS-007 | EXISTS | EXISTS | NO |
| IoS-008 | EXISTS | EXISTS | NO |
| IoS-009 | EXISTS | EXISTS | NO |
| IoS-010 | EXISTS | EXISTS | NO |
| IoS-011 | EXISTS | EXISTS | NO |
| IoS-012 | EXISTS | EXISTS | NO |
| IoS-013 | EXISTS | EXISTS | NO |
| IoS-014 | EXISTS | EXISTS | NO |
| IoS-015 | EXISTS | EXISTS | NO |
| IoS-016 | EXISTS | EXISTS | NO |
| ALPHA-GRAPH-001 | MISSING | EXISTS | YES — DB_NOT_ON_DISK |
| G4.2 | MISSING | EXISTS | YES — DB_NOT_ON_DISK |
| G5 | MISSING | EXISTS | YES — DB_NOT_ON_DISK |

**Totals:** 17 on disk (incl. IOS-003-B), 20 in database. 3 ghost entries in db.

### 1D. Daemon Health Registry (fhq_monitoring.daemon_health)

| Daemon | lifecycle_status | Mismatch |
|--------|-----------------|----------|
| daemon_watchdog | ACTIVE | — |
| finn_brain_scheduler | ACTIVE | — |
| finn_crypto_scheduler | ACTIVE | — |
| finn_e_scheduler | ACTIVE | — |
| finn_t_scheduler | ACTIVE | — |
| hypothesis_death_daemon | ACTIVE | — |
| mechanism_alpha_outcome | ACTIVE | — |
| mechanism_alpha_trigger | ACTIVE | — |
| orphan_state_cleanup | ACTIVE | — |
| pre_tier_scoring_daemon | ACTIVE | — |
| shadow_roi_calculator | ACTIVE | — |
| tier1_execution_daemon | ACTIVE | — |
| calendar_integrity_check | SUSPENDED_BY_DESIGN | — |
| cnrp_orchestrator | SUSPENDED_BY_DESIGN | — |
| g2c_continuous_forecast_engine | SUSPENDED_BY_DESIGN | — |
| ios003b_intraday_regime_delta | SUSPENDED_BY_DESIGN | — |
| price_freshness_heartbeat | SUSPENDED_BY_DESIGN | — |
| TRADING_CALENDAR_GOVERNANCE | SUSPENDED_BY_DESIGN | — |
| uma_meta_analyst | SUSPENDED_BY_DESIGN | — |
| wave15_autonomous_hunter | SUSPENDED_BY_DESIGN | — |
| indicator_calculation_daemon | RETIRED | — |

**Totals:** 21 daemons. 12 ACTIVE, 8 SUSPENDED_BY_DESIGN, 1 RETIRED.

### 1E. v_daemon_health View (fhq_ops)

| Component | Last Heartbeat | Hours Stale | Status |
|-----------|---------------|-------------|--------|
| EVIDENCE | 2026-02-01 14:09 | 44.0h | STALE |
| NEWS_SENTIMENT | 2026-01-23 16:55 | 257.3h | STALE |
| GRAPH | 2026-01-23 12:36 | 261.6h | STALE |
| ORCHESTRATOR | 2026-01-23 12:36 | 261.6h | STALE |
| GOVERNANCE | 2026-01-23 12:36 | 261.6h | STALE |
| DATA | 2026-01-23 12:36 | 261.6h | STALE |
| RESEARCH | 2026-01-23 12:36 | 261.6h | STALE |
| EXECUTION | 2026-01-23 12:36 | 261.6h | STALE |
| INFRASTRUCTURE | 2026-01-23 12:36 | 261.6h | STALE |

**ALL 9 components STALE.** 7 of 9 frozen since Jan 23 (11 days). EVIDENCE last updated Feb 1 (44h ago). This view is abandoned — no daemon writes to it.

### 1F. Task Registry (fhq_governance.task_registry)

| Status | Enabled | Count |
|--------|---------|-------|
| active | true | 42 |
| active | false | 0 |
| pending | true | 7 |
| pending | false | 4 |
| **Total** | | **53** |

**Agent assignment distribution:**

| Agent | Tasks |
|-------|-------|
| STIG | 16 |
| FINN | 9 |
| CEIO | 6 |
| VEGA | 5 |
| LINE | 4 |
| LARS | 3 |
| CDMO | 2 |
| CRIO | 1 |
| CEO | 1 |
| CPTO | 1 |
| NULL (unassigned) | 5 |

### 1G. Scheduled Tasks (fhq_governance.scheduled_tasks)

| task_id | Target | Status | Executed |
|---------|--------|--------|----------|
| BRIER-SCORE-DAILY-001 | phase3_calibration_daemon.py | SCHEDULED | NEVER |
| FAMA-FRENCH-WEEKLY-001 | ios006_g2_macro_ingest.py | COMPLETED | 2026-01-23 |
| GOLDEN-NEEDLES-DAILY-001 | wave15_autonomous_hunter.py | SCHEDULED | NEVER |
| GOV-MIGRATE-MODEL-NORMALIZATION | fhq_meta.llm_provider_config | SCHEDULED | NEVER |
| IOS013-SIGNAL-AGGREGATOR-DAILY-001 | ios013_signal_aggregator.py | SCHEDULED | NEVER |
| LDOW-CYCLE1-EVALUATION-20260115 | ldow_evaluation_log | SCHEDULED | NEVER |
| LDOW-CYCLE1-RECONCILIATION-20260114 | ios010_forecast_reconciliation_daemon.py | SCHEDULED | NEVER |
| LDOW-CYCLE2-EVALUATION-20260116 | ldow_evaluation_log | SCHEDULED | NEVER |
| LDOW-CYCLE2-RECONCILIATION-20260115 | ios010_forecast_reconciliation_daemon.py | SCHEDULED | NEVER |
| LVI-REFRESH-DAILY-001 | fhq_governance.populate_lvi_canonical | SCHEDULED | NEVER |
| UMA-META-ANALYST-DAILY-001 | uma_meta_analyst_daemon.py | SCHEDULED | NEVER |

**Totals:** 11 scheduled tasks. 1 executed (FAMA-FRENCH). 10 NEVER executed. **91% execution failure rate.**

---

## 2. REALITY BY LAYER

### 2.1 FILESYSTEM REALITY

| Directory | Files | Key Types | Purpose |
|-----------|-------|-----------|---------|
| 00_CONSTITUTION/ | 31 | .md, .pdf | ADR production documents |
| 01_CANONICAL/ | 2 | .md | EC-009, EC-013 canonical copies |
| 01_ADR_LEGACY/ | 29 | .md | Legacy ADR archive (pointer) |
| 02_IOS/ | 33 | .md | IoS specifications |
| 03_FUNCTIONS/ | 6,732 | .py (375), .json (3,818), .log (2,305) | Core daemons, evidence, telemetry |
| 04_AGENTS/ | 53 | .py, .md, .csv | Agent specs (FINN, LINE, STIG, VEGA) |
| 04_DATABASE/ | 399 | .sql (395) | Migration history (001-187+) |
| 04_ORCHESTRATION/ | 2,410 | .ps1, .log | Task schedulers, daemon runners |
| 05_GOVERNANCE/ | 9,986 | .json (9,877), .md (95) | Governance lifecycle, attestations |
| 05_ORCHESTRATOR/ | 64 | .py, .json, .yaml | Central orchestration daemons |
| 06_AGENTS/ | 2 | .py | FINN DeepSeek module |
| 08_BACKFILL/ | 49 | .csv, .py, .zip | Historical OHLCV data |
| 09_VISUALIZATION/ | 4 | .png, .md | Gemini visualizations |
| 10_EMPLOYMENT CONTRACTS/ | 23 | .md, .csv | EC-001 through EC-022 |
| 11_Visualiseringer/ | 3 | .html | Interactive dashboards |
| 12_DAILY_REPORTS/ | 183 | .md (50), .json (133) | DAY3-DAY34 reports, truth snapshots |
| alpha_graph/ | 14 | .py | Alpha graph engine |
| alpha_lab/ | 19 | .py | Experiment runner, simulator |
| backups/ | 96 | .sql, .json.gz | Daily backups (Jan 11 - Feb 3) |
| dashboard-2026/ | 36,374 | .ts, .tsx, .js | Next.js dashboard (incl. node_modules) |
| docker/ | 4 | — | Docker configuration |
| evidence/ (root) | 2,781 | .json | Daily ingest evidence |
| IoS-Register/ | 3 | — | IoS registry files |
| keys/ | 1 | .txt | SERPER API KEY (SENSITIVE) |
| logs/ | 163 | .json, .log | Orchestrator/agent logs |
| meta_perception/ | 54 | .py | IoS-009 implementation |
| prediction_ledger/ | 14 | .py | IoS-010 implementation |
| scripts/ | 79 | .py, .ps1, .bat | Utility scripts |
| trade_engine/ | 20 | .py | Trading execution engine |

**Filesystem total: 61,234 files across 29 top-level directories.**

**Sensitive file exposure:** `keys/SERPER API KEY - visionIoS.txt` exists in filesystem.

**Evidence distribution:**
- `03_FUNCTIONS/evidence/`: 6,064 files
- `evidence/` (root): 2,781 files
- Total evidence artifacts: 8,845 files

### 2.2 DATABASE REALITY

#### Schema Inventory (34 fhq_* schemas)

| Schema | Tables | Schema | Tables |
|--------|--------|--------|--------|
| fhq_governance | 249 | fhq_meta | 146 |
| fhq_research | 144 | fhq_alpha | 62 |
| fhq_monitoring | 47 | fhq_canonical | 45 |
| fhq_calendar | 41 | fhq_execution | 40 |
| fhq_learning | 38 | fhq_finn | 25 |
| fhq_perception | 17 | fhq_macro | 17 |
| fhq_data | 16 | fhq_positions | 13 |
| fhq_optimization | 10 | fhq_memory | 10 |
| fhq_graph | 9 | fhq_market | 7 |
| fhq_operational | 7 | fhq_signal_context | 7 |
| fhq_org | 6 | fhq_indicators | 5 |
| fhq_cognition | 5 | fhq_analytics | 4 |
| fhq_security | 4 | fhq_core | 3 |
| fhq_ace | 3 | fhq_ops | 3 |
| fhq_sandbox | 3 | fhq_archive | 2 |
| fhq_provisional | 2 | fhq_hmm | 1 |
| fhq_phase3 | 1 | fhq_signals | 1 |

**Total: 34 schemas, 993 tables.**

#### Top 25 Tables by Row Count

| Table | Rows |
|-------|------|
| fhq_core.market_prices_live | 16,217,975 |
| fhq_research.indicator_momentum | 3,133,695 |
| fhq_research.indicator_trend | 3,100,552 |
| fhq_research.indicator_volatility | 3,007,335 |
| fhq_research.indicator_ichimoku | 2,925,829 |
| fhq_market.prices | 1,230,863 |
| fhq_indicators.momentum | 1,223,282 |
| fhq_indicators.volatility | 1,220,689 |
| fhq_research.indicator_volume | 1,220,643 |
| fhq_data.technical_indicators | 599,743 |
| fhq_research.strategy_run_timeseries | 499,800 |
| fhq_data.indicators | 169,743 |
| fhq_perception.regime_daily | 150,815 |
| fhq_perception.sovereign_regime_state_v4 | 141,953 |
| fhq_macro.raw_staging | 124,021 |
| fhq_research.forecast_ledger | 60,517 |
| fhq_research.outcome_ledger | 59,571 |
| fhq_macro.canonical_series | 59,223 |
| fhq_data.indicators_temp | 59,143 |
| fhq_alpha.causal_edges | 52,023 |
| fhq_research.feature_performance | 39,302 |
| fhq_canonical.g5_cco_health_log | 32,379 |
| fhq_research.regime_predictions | 25,722 |
| fhq_meta.chain_of_query | 20,249 |
| fhq_research.forecast_outcome_pairs | 17,656 |

**Estimated total rows: 35M+ (top 25 tables alone: 35.7M)**

#### Registry Location Split

| Registry | Expected Schema | Actual Schema | Split |
|----------|----------------|---------------|-------|
| ec_registry | fhq_governance | fhq_governance | CORRECT |
| adr_registry | fhq_governance | fhq_meta | SPLIT |
| ios_registry | fhq_governance | fhq_meta | SPLIT |
| daemon_health | fhq_monitoring | fhq_monitoring | CORRECT |
| task_registry | fhq_governance | fhq_governance | CORRECT |
| scheduled_tasks | fhq_governance | fhq_governance | CORRECT |

**2 of 6 core registries in unexpected schemas.** ADR and IoS registries live in fhq_meta, not fhq_governance.

#### System State

| Parameter | Value | Source |
|-----------|-------|--------|
| Execution Mode | SHADOW_PAPER | fhq_governance.execution_mode (is_current=true) |
| Set By | CEO_DIRECTIVE_001_CEIO | — |
| Set At | 2025-12-08 20:55 UTC | — |
| DEFCON Level | GREEN | fhq_governance.defcon_state (is_current=true) |
| DEFCON Since | 2025-12-11 15:28 UTC | Triggered by STIG, G4 Activation Order |
| Autonomy Clock State | RUNNING | fhq_governance.autonomy_clock_state |
| Consecutive Days | 0 | — |
| Last Tick | 2026-01-19 18:08 UTC | 15 days ago, never ticked |
| Total Autonomous Days | 0 | — |
| Total Resets | 0 | — |
| Longest Streak | 0 | — |

**Autonomy clock: Claims RUNNING. Has 0 consecutive days. Last tick 15 days ago. Clock is dead.**

### 2.3 RUNTIME REALITY

#### Daemon Health vs Actual Evidence Production

The `daemon_health` table shows 12 ACTIVE daemons. Evidence files confirm recent production:

| Daemon | Last Evidence File | Producing |
|--------|-------------------|-----------|
| Shadow Trade Creator | SHADOW_TRADE_CREATOR_20260203_095210.json | YES |
| Promotion Gate Engine | PROMOTION_GATE_EVALUATION_20260203_090018.json | YES |
| Decision Pack Generator | DECISION_PACK_GEN_20260203_092003.json | YES |
| Bridge Daemon | BRIDGE_DAEMON_20260203_083530.json | YES |
| Tier 1 Execution | TIER1_EXECUTION_20260203_093231.json | YES |
| Daily Ingest | ios001_daily_ingest_20260203_095254.log | YES |
| Orphan Cleanup | ORPHAN_CLEANUP_20260203_090014.json | YES |
| Price Heartbeat | PRICE_HEARTBEAT_20260203_083412.json | YES |
| Morning Verification | MORNING_VERIFICATION_20260203_083006.json | YES |

**Active daemons are producing evidence.** The Windows Task Scheduler pipeline (PowerShell → Python → PostgreSQL) is operational for the core loop.

#### v_daemon_health vs daemon_health

| Source | Says | Reality |
|--------|------|---------|
| fhq_monitoring.daemon_health | 12 ACTIVE daemons | CORRECT — evidence confirms production |
| fhq_ops.v_daemon_health | ALL 9 STALE | WRONG — daemons are running but this view is not being updated |

**v_daemon_health is a dead monitoring channel.** No daemon writes to the heartbeat table this view reads. It has been abandoned since 2026-01-23.

#### Task Registry Status

| Category | Count | Details |
|----------|-------|---------|
| Active + Enabled | 42 | Registered and theoretically runnable |
| Pending + Enabled | 7 | Awaiting activation conditions |
| Pending + Disabled | 4 | Gated (CPTO, forecast_confidence_damper, regime_sanity_gate, ec019_governance_watchdog) |
| **Total** | **53** | — |

**Disabled tasks (4) with reasons:**
1. `cpto_precision_transform` — blocked until VEGA_ATTESTATION_EC015_AND_CEO_G4_APPROVAL
2. `forecast_confidence_damper` — P0 Calibration, disabled, locked behind CEO-DIR-2026-061
3. `regime_sanity_gate` — P1, disabled, sequencing_lock on forecast_confidence_damper
4. `ec019_governance_watchdog` — dormant until VEGA_ATTESTATION_EC019

### 2.4 SCHEDULER REALITY

#### Scheduled Tasks (fhq_governance.scheduled_tasks)

| Task | Cron | Scheduled Since | Executed | Status |
|------|------|----------------|----------|--------|
| BRIER-SCORE-DAILY-001 | 5 0 * * * | 2026-01-20 | NEVER | DEAD |
| FAMA-FRENCH-WEEKLY-001 | 0 8 * * 1 | 2026-01-22 | 2026-01-23 | EXECUTED ONCE |
| GOLDEN-NEEDLES-DAILY-001 | 0 6 * * * | 2026-01-20 | NEVER | DEAD |
| GOV-MIGRATE-MODEL-NORMALIZATION | — | 2025-12-08 | NEVER | EXPIRED (target date 2025-12-15) |
| IOS013-SIGNAL-AGGREGATOR-DAILY-001 | 0 2 * * * | 2026-01-22 | NEVER | DEAD |
| LDOW-CYCLE1-EVALUATION-20260115 | — | 2026-01-14 | NEVER | OVERDUE 19 days |
| LDOW-CYCLE1-RECONCILIATION-20260114 | — | 2026-01-14 | NEVER | OVERDUE 19 days |
| LDOW-CYCLE2-EVALUATION-20260116 | — | 2026-01-14 | NEVER | OVERDUE 18 days |
| LDOW-CYCLE2-RECONCILIATION-20260115 | — | 2026-01-14 | NEVER | OVERDUE 18 days |
| LVI-REFRESH-DAILY-001 | 0 7 * * * | 2026-01-20 | NEVER | DEAD |
| UMA-META-ANALYST-DAILY-001 | 0 6 * * * | 2026-01-22 | NEVER | DEAD |

**Observations:**
- 10/11 tasks NEVER executed
- 4 LDOW tasks overdue by 18-19 days
- 1 task EXPIRED (GOV-MIGRATE-MODEL-NORMALIZATION, target Dec 15 2025)
- 5 daily cron tasks registered but no execution engine reads this table
- **This table is write-only.** Tasks are registered here but nothing executes them. Actual execution runs through Windows Task Scheduler → PowerShell wrappers.

#### Task Registry Cron Schedules (fhq_governance.task_registry)

Selected tasks with cron-like schedules in task_config:

| Task | Schedule | Actually Running |
|------|----------|-----------------|
| daily_ingest_worker | */10 * * * * | YES (via Windows Task Scheduler) |
| ios001_daily_ingest | */15 * * * * | YES (via Windows Task Scheduler) |
| ios001_daily_ingest_crypto | 0 1 * * * | YES |
| ios001_daily_ingest_equity | 0 22 * * 1-5 | YES |
| ios001_daily_ingest_fx | 0 22 * * 0-4 | YES |
| ios006_g2_macro_ingest | 0 */4 * * * | YES |
| FINN_COGNITIVE_GATEWAY | */30 * * * * | UNKNOWN — no recent evidence |
| broker_truth_capture | */5 * * * * | UNKNOWN — no recent evidence |
| signal_executor_daemon_shadow | every_60s | UNKNOWN — no recent evidence |
| subexec_heartbeat_daemon | every_5min | UNKNOWN — no recent evidence |

**Two scheduling systems exist in parallel:**
1. `fhq_governance.scheduled_tasks` — 11 entries, no execution engine, DEAD
2. Windows Task Scheduler → PowerShell → Python — ACTUALLY RUNNING

These systems are not synchronized. The database table does not reflect what actually runs.

### 2.5 GOVERNANCE REALITY

#### ADR Compliance

| Check | Result |
|-------|--------|
| ADR-013 (One-True-Source) | **VIOLATED** — 76% of ECs exist only on disk, not in database |
| ADR-013 (Canonical registry) | **PARTIAL** — ADR registry in fhq_meta, not fhq_governance |
| ADR-002 (Audit & Reconciliation) | **UNVERIFIABLE** — no reconciliation daemon running |
| ADR-015 (Lifecycle Integrity) | **VIOLATED** — 16 ECs never ingested |
| ADR-016 (DEFCON Circuit Breaker) | OPERATIONAL — GREEN since Dec 11 |

#### EC Hierarchy (From Disk)

| Tier | Agents | Count |
|------|--------|-------|
| Tier-0 | CEO (EC-010) | 1 |
| Tier-1 | VEGA (EC-001), LARS (EC-002), STIG (EC-003) | 3 |
| Tier-2 | FINN (EC-004), LINE (EC-005), CFAO (EC-007), CDMO (EC-007/EC-012), CEIO (EC-009), CSEO (EC-011), CRIO (EC-013), UMA (EC-014), CPTO (EC-015) | 9 |
| Tier-2 Cognitive | Meta-Alpha (EC-018), SitC (EC-020), InForage (EC-021), IKEA (EC-022) | 4 |
| Supervisory | Human Governor (EC-019) | 1 |
| System Charter | Enterprise (EC-008) | 1 |
| **Total** | | **19 unique agents + 2 special** |

**Of 21 ECs on disk, only 5 (24%) are registered in the database.** The 5 registered are all Tier-2 Cognitive/Meta agents (EC-014, EC-018, EC-020, EC-021, EC-022). All Tier-0, Tier-1, and core Tier-2 agents are MISSING from the database.

#### STIG Self-Reference

CLAUDE.md declares: `Employment Contract: EC-003_2026_PRODUCTION`
Database ec_registry: EC-003 NOT FOUND.

**STIG's own employment contract is not registered in the database it is mandated to protect.**

---

## 3. MISMATCH LEDGER

| # | Entity | Layer A | Layer B | Type | Detail |
|---|--------|---------|---------|------|--------|
| M-01 | EC-001 (VEGA) | Disk | Database | DISK_NOT_IN_DB | Tier-1 contract, not registered |
| M-02 | EC-002 (LARS) | Disk | Database | DISK_NOT_IN_DB | Tier-1 contract, not registered |
| M-03 | EC-003 (STIG) | Disk | Database | DISK_NOT_IN_DB | Tier-1 contract, SELF, not registered |
| M-04 | EC-004 (FINN) | Disk | Database | DISK_NOT_IN_DB | Tier-2 contract, not registered |
| M-05 | EC-005 (LINE) | Disk | Database | DISK_NOT_IN_DB | Tier-2 contract, not registered |
| M-06 | EC-006 (CODE) | Disk | Database | DISK_NOT_IN_DB | Tier-3 contract, not registered |
| M-07 | EC-007 (CFAO) | Disk | Database | DISK_NOT_IN_DB | Tier-2 contract, not registered |
| M-08 | EC-007_CDMO | Disk | Database | DISK_NOT_IN_DB + NUMBER_COLLISION | Duplicate EC-007 number |
| M-09 | EC-008 (Enterprise) | Disk | Database | DISK_NOT_IN_DB | System charter, not registered |
| M-10 | EC-009 (CEIO) | Disk | Database | DISK_NOT_IN_DB | Tier-2 contract, not registered |
| M-11 | EC-010 (CEO) | Disk | Database | DISK_NOT_IN_DB | Tier-0 contract, not registered |
| M-12 | EC-011 (CSEO) | Disk | Database | DISK_NOT_IN_DB | Tier-2 contract, not registered |
| M-13 | EC-012 (CDMO) | Disk | Database | DISK_NOT_IN_DB + DUPLICATE_AGENT | Second CDMO contract |
| M-14 | EC-013 (CRIO) | Disk | Database | DISK_NOT_IN_DB | Tier-2 contract, not registered |
| M-15 | EC-015 (CPTO) | Disk | Database | DISK_NOT_IN_DB | Tier-2 contract, not registered |
| M-16 | EC-019 (Human Gov) | Disk | Database | DISK_NOT_IN_DB | Supervisory, not registered |
| M-17 | MIG-200 | Database | Disk | DB_NOT_ON_DISK | Non-ADR entry in adr_registry |
| M-18 | ALPHA-GRAPH-001 | Database | Disk | DB_NOT_ON_DISK | Ghost IoS entry, no file |
| M-19 | G4.2 | Database | Disk | DB_NOT_ON_DISK | Ghost IoS entry, no file |
| M-20 | G5 | Database | Disk | DB_NOT_ON_DISK | Ghost IoS entry, no file |
| M-21 | adr_registry | fhq_governance | fhq_meta | SCHEMA_SPLIT | Registry in wrong schema |
| M-22 | ios_registry | fhq_governance | fhq_meta | SCHEMA_SPLIT | Registry in wrong schema |
| M-23 | v_daemon_health | Database View | Runtime | VIEW_ABANDONED | All 9 components STALE, 11+ days |
| M-24 | autonomy_clock_state | Database | Runtime | CLOCK_DEAD | 0 days, last tick 15 days ago |
| M-25 | scheduled_tasks (10/11) | Database | Runtime | NEVER_EXECUTED | Registered, no execution engine |
| M-26 | LDOW-CYCLE1-EVAL | Database | Calendar | OVERDUE_19d | Scheduled Jan 15, never ran |
| M-27 | LDOW-CYCLE1-RECON | Database | Calendar | OVERDUE_19d | Scheduled Jan 15, never ran |
| M-28 | LDOW-CYCLE2-EVAL | Database | Calendar | OVERDUE_18d | Scheduled Jan 16, never ran |
| M-29 | LDOW-CYCLE2-RECON | Database | Calendar | OVERDUE_18d | Scheduled Jan 16, never ran |
| M-30 | GOV-MIGRATE-MODEL | Database | Calendar | EXPIRED | Target Dec 15, never ran |
| M-31 | EC-007 number | Disk | Disk | NUMBER_COLLISION | Two agents share EC-007 |
| M-32 | CDMO contracts | Disk | Disk | DUPLICATE_AGENT | CDMO has EC-007 variant + EC-012 |
| M-33 | scheduled_tasks vs Task Scheduler | Database | OS | DUAL_SYSTEM | Two parallel scheduling systems, not synchronized |

**Total mismatches: 33**

---

## 4. FAILURE TAXONOMY

### SF — Silent Failure (claims to work, doesn't)

| # | Mismatch | Detail |
|---|----------|--------|
| SF-1 | M-23 | v_daemon_health claims to monitor health. All 9 STALE. No daemon writes to it. |
| SF-2 | M-24 | autonomy_clock_state claims RUNNING. 0 days. Never ticked in 15 days. |
| SF-3 | M-25 | scheduled_tasks has 10 "SCHEDULED" entries. No engine processes them. |
| SF-4 | M-26..M-29 | LDOW evaluation cycles registered with deadlines. All overdue. No alert. |
| SF-5 | M-30 | GOV-MIGRATE-MODEL expired Dec 15. Still status "SCHEDULED" 50 days later. |

### OG — Observability Gap (can't see what's happening)

| # | Mismatch | Detail |
|---|----------|--------|
| OG-1 | M-23 | v_daemon_health is the only system-level health view. It's dead. No replacement exists. |
| OG-2 | M-33 | Two scheduling systems (DB + Windows) not synchronized. No way to query combined truth. |
| OG-3 | — | 4 task_registry tasks with schedule "every_5min"/"every_60s" have no evidence trail to verify execution. |

### GG — Governance Gap (rules not enforced)

| # | Mismatch | Detail |
|---|----------|--------|
| GG-1 | M-01..M-16 | ADR-013 mandates database as One-True-Source. 16 ECs exist only on disk. |
| GG-2 | M-03 | STIG's own EC (EC-003) violates the doctrine STIG is mandated to enforce. |
| GG-3 | M-21, M-22 | ADR/IoS registries split across schemas. No single governance query point. |
| GG-4 | — | ADR-015 mandates canonical lifecycle ingestion. 76% of ECs never ingested. |

### DD — Design Debt (architectural inconsistency)

| # | Mismatch | Detail |
|---|----------|--------|
| DD-1 | M-31 | EC-007 number collision. Two agents, one number. |
| DD-2 | M-32 | CDMO has two employment contracts (EC-007 variant + EC-012). |
| DD-3 | M-17 | MIG-200 stored in adr_registry. Not an ADR. |
| DD-4 | M-18..M-20 | 3 IoS entries in database with no corresponding files (ghost entities). |
| DD-5 | M-33 | Dual scheduling architecture with no integration layer. |

### ED — Execution Debt (registered but never started)

| # | Mismatch | Detail |
|---|----------|--------|
| ED-1 | M-25 | 10 of 11 scheduled_tasks never executed. |
| ED-2 | M-26..M-29 | 4 LDOW cycle tasks 18-19 days overdue. |
| ED-3 | — | 4 task_registry tasks disabled, awaiting VEGA attestations that haven't come. |
| ED-4 | — | 7 task_registry tasks in "pending" status since creation. |

---

## 5. DECISION-RELEVANT FINDINGS

### Finding F-1: EC Registry is 76% Empty
- 16 of 21 employment contracts not in database
- All Tier-0, Tier-1, and core Tier-2 agents missing
- ADR-013 One-True-Source doctrine violated at foundation level
- **Severity: CRITICAL**

### Finding F-2: STIG Cannot Verify Its Own Existence
- EC-003 not in ec_registry
- CLAUDE.md references EC-003_2026_PRODUCTION
- The CTO agent operates without database-verifiable authority
- **Severity: CRITICAL**

### Finding F-3: v_daemon_health is Dead
- Only system-level health monitoring view
- All 9 components STALE (7 since Jan 23 = 11 days)
- No daemon writes heartbeats to the table this view reads
- System has no operational health dashboard that works
- **Severity: HIGH**

### Finding F-4: Autonomy Clock Never Ticked
- State: RUNNING since Jan 19
- Consecutive days: 0
- Total autonomous days: 0
- The clock exists but has never recorded a single autonomous day
- **Severity: MEDIUM**

### Finding F-5: Scheduled Tasks Table is Decorative
- 11 entries, 10 never executed
- No execution engine reads this table
- Actual scheduling runs through Windows Task Scheduler (separate system)
- 4 LDOW evaluations 18-19 days overdue with no alert
- **Severity: HIGH**

### Finding F-6: Registry Schema Split
- ADR registry in fhq_meta, not fhq_governance
- IoS registry in fhq_meta, not fhq_governance
- EC registry in fhq_governance
- No single schema contains all governance registries
- **Severity: MEDIUM**

### Finding F-7: EC-007 Number Collision
- CFAO and CDMO both assigned EC-007
- CDMO additionally has EC-012
- Identity governance has a numbering conflict
- **Severity: MEDIUM**

### Finding F-8: Dual Scheduling Architecture
- Database scheduled_tasks (11 entries, mostly dead)
- Windows Task Scheduler (39+ tasks, actually running)
- These systems do not synchronize
- No unified view of what is scheduled
- **Severity: MEDIUM**

### Finding F-9: 3 Ghost IoS Entries
- ALPHA-GRAPH-001, G4.2, G5 registered in ios_registry
- No corresponding files on disk
- Origin and purpose unverifiable
- **Severity: LOW**

### Finding F-10: MIG-200 in ADR Registry
- Non-ADR entity stored in adr_registry
- Pollutes governance namespace
- **Severity: LOW**

---

## AUDIT COMPLETENESS STATEMENT

| Layer | Entities Audited | Source |
|-------|-----------------|--------|
| Filesystem | 29 directories, 61,234 files | Glob/Explore agent |
| Database | 34 schemas, 993 tables, 6 registries | SQL (read-only) |
| Runtime | 21 daemons, 9 v_daemon components, evidence files | SQL + file timestamps |
| Scheduler | 11 scheduled_tasks, 53 task_registry entries | SQL |
| Governance | 26 ADRs, 21 ECs, 20 IoSs cross-referenced | SQL + Glob |

**Items NOT verified this session:**
- Windows Task Scheduler live state (requires schtasks /query — referenced from DAY34 daemon agent data only)
- Running Windows processes (requires tasklist — not executed)
- Database disk size (requires pg_database_size — not queried)
- Network connectivity to external APIs (Alpaca, DeepSeek, Serper)

**This document is a point-in-time reality capture. No fixes applied. No narrative framing. No opinions.**

---

*Audit completed: 2026-02-03 10:05 CET*
*Auditor: STIG (EC-003_2026_PRODUCTION)*
*Mode: READ-ONLY PLAN MODE*
