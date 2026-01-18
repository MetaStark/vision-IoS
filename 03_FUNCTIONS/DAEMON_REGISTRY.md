# FjordHQ Daemon Registry

**CEO-DIR-2026-088: Continuous Trading Calendar Governance**
**CEO-DIR-2026-093: IoS-003C Shadow Learning**
**Last Updated: 2026-01-18**

## Registered Daemons (fhq_monitoring.daemon_health)

Long-running background processes with heartbeat monitoring.

| Daemon Name | Status | Cadence | Purpose |
|-------------|--------|---------|---------|
| TRADING_CALENDAR_GOVERNANCE | HEALTHY | Monthly (1st @ 03:00) | Extend US_EQUITY calendar 24+ months |
| uma_meta_analyst | HEALTHY | Daily @ 06:00 | Universal Meta-Analyst - strategic self-correction |
| ios003c_shadow_learning | ACTIVE | Multi-schedule | IoS-003C 30-day shadow learning experiment |
| cnrp_orchestrator | HEALTHY | Continuous | Cognitive Refresh Protocol |
| g2c_continuous_forecast_engine | HEALTHY | Continuous | G2C Forecast Generation |
| ios003_regime_update | HEALTHY | Daily | Regime Classification Update |
| ios010_learning_loop | HEALTHY | Continuous | Learning Loop |
| ios014_orchestrator | HEALTHY | Continuous | Task Orchestration |
| price_freshness_heartbeat | STOPPED | N/A | Price Freshness Monitoring (deprecated) |

## Scheduled Tasks (fhq_execution.task_registry)

Cron-scheduled tasks managed by the orchestrator.

| Task Name | Gate | Owner | Schedule | Purpose |
|-----------|------|-------|----------|---------|
| ceo_gateway_daemon | G4 | LARS | Every 1 min | CEO Telegram Gateway |
| cognitive_killswitch_sentinel | G1 | VEGA | Every 5 min | Emergency halt detection |
| vega_epistemic_integrity_monitor | G1 | VEGA | Every 15 min | Epistemic integrity checks |
| ios_canonical_freshness_sentinel | G2 | STIG | Every 30 min | Data freshness monitoring |
| ceio_evidence_refresh_daemon | G2 | CEIO | Every 4 hours | Evidence chain refresh |
| ios003_regime_freshness_sentinel | G2 | STIG | Every 15 min | Regime classification freshness |
| broker_reconciliation_daemon | G3 | LINE | Every hour | Position reconciliation |
| signal_executor_daemon | G3 | LINE | Every 5 min | Signal execution |
| exit_detection_daemon | G3 | LINE | Every 5 min | Exit signal detection |
| crio_alpha_graph_rebuild | G3 | CRIO | Every 4 hours (30 min offset) | Alpha graph maintenance |
| cdmo_data_hygiene_attestation | G3 | CDMO | Daily @ 00:00 | Data quality attestation |
| epistemic_proposal_daemon | G3 | FINN | Weekly (Sunday @ 00:00) | Research proposal generation |
| ios001_daily_ingest_crypto | G1 | STIG | Daily @ 01:00 | Crypto price ingestion |
| ios001_daily_ingest_equity | G1 | STIG | Daily @ 22:00 (Mon-Fri) | Equity price ingestion |
| ios001_daily_ingest_fx | G1 | STIG | Daily @ 22:00 (Sun-Thu) | FX rate ingestion |
| IOS013_HCP_LAB_G4_RUNNER | G4 | LARS | Every 15 min (market hours) | HCP Lab execution |
| ios003c_epoch_snapshot | SHADOW | STIG | Daily @ 00:05 UTC | Capture crypto regime predictions |
| ios003c_outcome_computation | SHADOW | STIG | Daily @ 04:00 UTC | Compute outcomes, update metrics |
| ios003c_weekly_analysis | SHADOW | STIG/VEGA | Weekly (Sunday @ 00:00) | Bootstrap significance, VEGA attestation |
| ios003c_gate3_check | SHADOW | STIG | Daily @ 04:30 UTC | Check Day 30 eligibility, generate packet |

## Windows Task Scheduler Tasks

| Task Name | Schedule | Next Run | Script |
|-----------|----------|----------|--------|
| FjordHQ-TradingCalendarGovernance | Monthly (1st @ 03:00) | 2026-02-01 | run_calendar_daemon.bat |
| FjordHQ-CalendarIntegrityCheck | Daily @ 05:00 | 2026-01-19 | run_calendar_integrity_daemon.bat |
| FjordHQ-UMA-MetaAnalyst | Daily @ 06:00 | 2026-01-19 | run_uma_daemon.bat |
| FjordHQ-IoS003C-EpochSnapshot | Daily @ 00:05 UTC | 2026-01-19 | run_ios003c_snapshot.bat |
| FjordHQ-IoS003C-Outcomes | Daily @ 04:00 UTC | 2026-01-19 | run_ios003c_outcomes.bat |
| FjordHQ-IoS003C-Weekly | Weekly (Sun @ 00:00) | 2026-01-26 | run_ios003c_weekly.bat |

### Setup Commands (run as Administrator)

**Trading Calendar Governance:**
```cmd
schtasks /create /tn "FjordHQ-TradingCalendarGovernance" ^
    /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\run_calendar_daemon.bat" ^
    /sc monthly /d 1 /st 03:00 /f
```

**Calendar Integrity Check (CEO-DIR-2026-091):**
```cmd
schtasks /create /tn "FjordHQ-CalendarIntegrityCheck" ^
    /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\run_calendar_integrity_daemon.bat" ^
    /sc daily /st 05:00 /f
```

**UMA Meta-Analyst:**
```cmd
schtasks /create /tn "FjordHQ-UMA-MetaAnalyst" ^
    /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\run_uma_daemon.bat" ^
    /sc daily /st 06:00 /f
```

**IoS-003C Shadow Learning - Epoch Snapshot (CEO-DIR-2026-093):**
```cmd
schtasks /create /tn "FjordHQ-IoS003C-EpochSnapshot" ^
    /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\run_ios003c_snapshot.bat" ^
    /sc daily /st 00:05 /f
```

**IoS-003C Shadow Learning - Outcome Computation:**
```cmd
schtasks /create /tn "FjordHQ-IoS003C-Outcomes" ^
    /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\run_ios003c_outcomes.bat" ^
    /sc daily /st 04:00 /f
```

**IoS-003C Shadow Learning - Weekly Analysis:**
```cmd
schtasks /create /tn "FjordHQ-IoS003C-Weekly" ^
    /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\run_ios003c_weekly.bat" ^
    /sc weekly /d SUN /st 00:00 /f
```

## Query Database Registry

```sql
-- Query daemon health status
SELECT daemon_name, status, last_heartbeat, metadata->>'cadence'
FROM fhq_monitoring.daemon_health
ORDER BY daemon_name;

-- Query scheduled tasks
SELECT task_name, gate_level, owned_by, enabled, schedule_cron
FROM fhq_execution.task_registry
WHERE enabled = true
ORDER BY task_name;
```

## Manual Daemon Execution

```bash
python 03_FUNCTIONS/trading_calendar_governance_daemon.py
```

## Governance

- All daemons must be registered in `fhq_monitoring.daemon_health`
- Heartbeat updates on each execution
- Status: HEALTHY, DEGRADED, UNHEALTHY, STOPPED
