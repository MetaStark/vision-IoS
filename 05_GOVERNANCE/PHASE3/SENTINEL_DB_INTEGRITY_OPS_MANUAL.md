# SENTINEL_DB_INTEGRITY Operations Manual

**Version:** 1.0
**Effective Date:** 2025-12-08
**Authority:** CEO Directive - G2 Governance Review
**Custodian:** STIG
**Oversight:** VEGA

---

## 1. Overview

The Sentinel_DB_Integrity is an OODA-loop critical infrastructure component that monitors database integrity, bloat, and performance. This manual documents operational procedures for managing the sentinel.

### 1.1 Core Principle

> A slow but correct query is acceptable. A fast but incorrect/inconsistent query is NOT acceptable.

### 1.2 ADR Binding

- ADR-002: Evidence and Audit Trail
- ADR-009: Agent Suspension Procedures
- ADR-010: Discrepancy Scoring
- ADR-011: Fortress Evidence Chain
- ADR-015: Meta-Governance Oversight
- ADR-016: DEFCON & Circuit Breaker

---

## 2. Operational Commands

### 2.1 Running the Sentinel Manually

```bash
# Single execution
cd /c/fhq-market-system/vision-ios/03_FUNCTIONS
python ios_db_integrity_sentinel.py

# With custom config path
SENTINEL_CONFIG_PATH=/path/to/config.yaml python ios_db_integrity_sentinel.py
```

### 2.2 Stopping the Sentinel

The sentinel runs as part of the orchestrator heartbeat loop. To stop it:

**Option A: Stop orchestrator entirely**
```bash
# Find orchestrator PID
ps aux | grep orchestrator_v1.py

# Kill process
kill <PID>
```

**Option B: Disable sentinel in config (preferred)**
```yaml
# Edit: 05_ORCHESTRATOR/sentinel_db_integrity_config.yaml
sentinel:
  enabled: false  # Set to false to disable
```

Then restart orchestrator to pick up config change.

### 2.3 Reloading Configuration Without Restart

The sentinel reads configuration on each execution cycle. To apply config changes:

1. Edit `05_ORCHESTRATOR/sentinel_db_integrity_config.yaml`
2. Wait for next sentinel cycle (default: 5 minutes)
3. Verify new config applied via audit log

**Verification Query:**
```sql
SELECT event_timestamp, event_data->>'config_source' as config_source
FROM fhq_meta.ios_audit_log
WHERE ios_id = 'SYSTEM' AND event_type = 'DB_INTEGRITY_SENTINEL'
ORDER BY event_timestamp DESC
LIMIT 5;
```

---

## 3. Manual Inspection Commands

### 3.1 Check Lock Contention

```sql
-- Active lock waits
SELECT
    blocked.pid AS blocked_pid,
    blocked.usename AS blocked_user,
    LEFT(blocked.query, 100) AS blocked_query,
    EXTRACT(EPOCH FROM (NOW() - blocked.query_start)) AS wait_seconds,
    blocking.pid AS blocking_pid,
    blocking.usename AS blocking_user
FROM pg_stat_activity blocked
LEFT JOIN pg_locks blocked_locks ON blocked.pid = blocked_locks.pid
LEFT JOIN pg_locks blocking_locks ON blocked_locks.locktype = blocking_locks.locktype
    AND blocked_locks.relation = blocking_locks.relation
    AND blocked_locks.pid != blocking_locks.pid
    AND blocking_locks.granted = true
    AND blocked_locks.granted = false
LEFT JOIN pg_stat_activity blocking ON blocking_locks.pid = blocking.pid
WHERE blocked.wait_event_type = 'Lock'
    AND blocked.state != 'idle'
ORDER BY wait_seconds DESC;
```

### 3.2 Check Table Bloat

```sql
-- Table bloat status
SELECT
    schemaname || '.' || relname AS table_name,
    n_live_tup,
    n_dead_tup,
    CASE
        WHEN (n_live_tup + n_dead_tup) > 0
        THEN ROUND(100.0 * n_dead_tup / (n_live_tup + n_dead_tup), 2)
        ELSE 0
    END AS bloat_pct,
    last_vacuum,
    last_autovacuum,
    EXTRACT(EPOCH FROM (NOW() - GREATEST(last_vacuum, last_autovacuum))) / 86400 AS days_since_vacuum
FROM pg_stat_user_tables
WHERE schemaname IN ('fhq_market', 'fhq_perception', 'fhq_research')
ORDER BY n_dead_tup DESC
LIMIT 20;
```

### 3.3 Check Slow Queries

```sql
-- Top slow queries
SELECT
    LEFT(query, 200) AS query_text,
    calls,
    ROUND(mean_exec_time::numeric, 2) AS mean_ms,
    ROUND(total_exec_time::numeric, 2) AS total_ms,
    rows
FROM pg_stat_statements
WHERE calls >= 10
ORDER BY mean_exec_time DESC
LIMIT 10;
```

### 3.4 Check Recent Discrepancy Events

```sql
-- Recent sentinel events
SELECT
    event_id,
    discrepancy_type,
    severity,
    target_table AS module,
    discrepancy_score,
    created_at
FROM fhq_governance.discrepancy_events
WHERE ios_id = 'IoS-014'
ORDER BY created_at DESC
LIMIT 20;
```

---

## 4. Remediation Procedures

### 4.1 Resolving Lock Contention (CRITICAL)

**Immediate Actions:**

1. Identify blocking PID:
   ```sql
   SELECT pid, usename, state, query FROM pg_stat_activity
   WHERE pid = <blocking_pid>;
   ```

2. If safe to terminate:
   ```sql
   SELECT pg_terminate_backend(<blocking_pid>);
   ```

3. If not safe, contact LINE for execution impact assessment.

4. Log resolution:
   ```sql
   UPDATE fhq_governance.discrepancy_events
   SET resolution_status = 'RESOLVED',
       resolved_by = 'STIG',
       resolved_at = NOW(),
       resolution_notes = 'Blocking PID <X> terminated'
   WHERE event_id = '<event_id>';
   ```

### 4.2 Resolving Table Bloat (CRITICAL)

**Standard Procedure:**

1. Run VACUUM ANALYZE on affected table:
   ```sql
   VACUUM ANALYZE fhq_perception.regime_daily;
   ```

2. If bloat persists (>25% after vacuum):
   ```sql
   -- More aggressive: VACUUM FULL (requires exclusive lock)
   -- WARNING: This blocks all operations on the table
   VACUUM FULL fhq_perception.regime_daily;
   ```

3. Verify resolution:
   ```sql
   SELECT n_dead_tup, n_live_tup,
          ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS bloat_pct
   FROM pg_stat_user_tables
   WHERE schemaname || '.' || relname = 'fhq_perception.regime_daily';
   ```

### 4.3 Investigating Slow Queries (WARNING)

**Investigation Only - No Automatic Changes:**

1. Get query plan:
   ```sql
   EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
   <slow_query>;
   ```

2. Document findings in governance log.

3. Index recommendations require separate G0-G4 change process.

---

## 5. Fortress Replay Integration (ADR-011)

### 5.1 Evidence Hash Verification

Every sentinel run produces an evidence hash stored in `fhq_meta.ios_audit_log`.

**Verify Hash Chain:**
```sql
SELECT
    audit_id,
    event_timestamp,
    evidence_hash,
    event_data->>'overall_status' AS status
FROM fhq_meta.ios_audit_log
WHERE event_type = 'DB_INTEGRITY_SENTINEL'
ORDER BY event_timestamp DESC
LIMIT 10;
```

### 5.2 Replay Compatibility

The sentinel's discrepancy events are designed for Fortress replay:

- All events include timestamp
- All events include evidence hash
- All events are immutable (trigger enforced)
- Event data is JSON-serializable

---

## 6. Configuration Reference

### 6.1 Config File Location

```
05_ORCHESTRATOR/sentinel_db_integrity_config.yaml
```

### 6.2 Key Thresholds

| Parameter | Default | Description |
|-----------|---------|-------------|
| `interval_seconds` | 300 | Check interval (5 min) |
| `lock_monitor.warn_wait_seconds` | 10 | Lock wait warning threshold |
| `lock_monitor.critical_consecutive` | 2 | Intervals for critical |
| `bloat_watchdog.warn_bloat_ratio` | 0.10 | 10% dead tuple warning |
| `bloat_watchdog.critical_bloat_ratio` | 0.25 | 25% dead tuple critical |
| `bloat_watchdog.critical_vacuum_days` | 7 | Days without vacuum |
| `slow_query.mean_time_warn_ms` | 500 | Query time threshold |
| `slow_query.min_calls` | 10 | Minimum call count |

### 6.3 Changing Thresholds

Per governance contract, threshold changes require:

1. STIG proposes change with rationale
2. VEGA approves change
3. CEO notification
4. Change logged to governance_actions_log

---

## 7. Emergency Procedures

### 7.1 Sentinel Crash Recovery

If sentinel crashes repeatedly:

1. Check logs for error:
   ```bash
   grep -i error /var/log/orchestrator.log
   ```

2. Check for SYSTEM_ERROR events:
   ```sql
   SELECT * FROM fhq_governance.discrepancy_events
   WHERE discrepancy_type = 'SYSTEM_ERROR'
   ORDER BY created_at DESC LIMIT 5;
   ```

3. If persistent (2+ intervals), trigger DEFCON-2 per escalation matrix.

### 7.2 False Positive Handling

If sentinel generates false positives:

1. Document incident in governance log
2. Do NOT modify sentinel logic (G2 restriction)
3. Request threshold review via governance process
4. VEGA may temporarily suspend sentinel per ADR-009

### 7.3 Complete Suspension

If sentinel must be completely suspended:

1. Requires VEGA or CEO authorization
2. Set `sentinel.enabled: false` in config
3. Log suspension to governance_actions_log
4. Plan re-enablement timeline

---

## 8. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-08 | STIG | Initial G2 release |

---

**Document Hash:** Computed at attestation
**Governance Contract Reference:** GC-SENTINEL-DB-INTEGRITY-001
