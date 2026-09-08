# Control Room Specification

**Dato:** 2026-01-23
**Direktiv:** CEO-DIR-2026-023 Order 3
**Status:** MIGRATION READY
**Computed By:** STIG (EC-003)

---

## OVERVIEW

The Control Room provides a single pane of glass for CEO operational visibility. All metrics are database-sourced with no manual input required.

**Migration:** `04_DATABASE/MIGRATIONS/332_fhq_ops_control_room.sql`

---

## SCHEMA: fhq_ops

### Tables

| Table | Purpose |
|-------|---------|
| `control_room_metrics` | P0 operational metrics with thresholds |
| `control_room_alerts` | System alerts requiring attention |
| `control_room_lvi` | Learning Velocity Index snapshots |

### Views

| View | Purpose |
|------|---------|
| `v_signal_production` | Signal generation stats (24h) |
| `v_calibration_distribution` | Calibration status breakdown |
| `v_event_coverage` | IoS-016 event coverage |
| `v_learning_loop_health` | Learning loop operational status |
| `v_daemon_health` | Agent heartbeat status |
| `v_brier_summary` | Brier calibration summary |
| `v_control_room_dashboard` | Unified CEO dashboard |

---

## P0 METRICS

| Metric | Category | Threshold (Yellow) | Threshold (Red) |
|--------|----------|-------------------|-----------------|
| Hours since last signal | PIPELINE | > 1 hour | > 4 hours |
| Signal production (24h) | SIGNAL | < 10 | 0 |
| Calibration % | CALIBRATION | < 80% | < 50% |
| Upcoming events | EVENT | < 5 | 0 |
| Experiment throughput | LEARNING | < 1/week | 0 |
| LVI score | LVI | < 0.3 | < 0.1 |

---

## STATUS LOGIC

### GREEN
- All thresholds met
- System operating normally

### YELLOW
- One or more metrics at warning level
- Requires attention within 24h

### RED
- Critical metric failure
- Requires immediate attention

---

## UNIFIED DASHBOARD VIEW

```sql
SELECT * FROM fhq_ops.v_control_room_dashboard;
```

Returns:
- signals_24h
- actionable_signals
- hours_since_signal
- calibrated_count
- calibrated_pct
- upcoming_events
- brier_score
- skill_factor
- learning_loop_status
- outcome_ledger_count
- lvi_score
- dashboard_timestamp

---

## ALERTING RULES

| Alert | Condition | Severity |
|-------|-----------|----------|
| Pipeline stall | hours_since_signal > 4 | CRITICAL |
| No upcoming events | upcoming_events = 0 | WARNING |
| Learning loop blocked | epistemic_proposals = 0 | WARNING |
| LVI degradation | lvi_score < 0.1 | CRITICAL |
| Daemon stale | hours_since_heartbeat > 24 | WARNING |

---

## INTEGRATION POINTS

### Dashboard (dashboard-2026)
- API route: `/api/control-room`
- WebSocket: Real-time metrics push
- Refresh: 5-minute intervals

### Telegram Notifications
- Critical alerts → immediate notification
- Daily summary → 08:00 CET

### Evidence Chain
- All metrics logged to evidence bundle
- Hash chain for audit trail

---

## MIGRATION EXECUTION

```bash
# Execute migration
psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -f 04_DATABASE/MIGRATIONS/332_fhq_ops_control_room.sql

# Verify creation
psql -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'fhq_ops'"
psql -c "SELECT * FROM fhq_ops.v_control_room_dashboard"
```

---

## APPROVAL

| Role | Status | Signature |
|------|--------|-----------|
| STIG | DELIVERED | EC-003 |
| CEO | PENDING | - |
