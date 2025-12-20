
**Authority**: LARS (Strategy & Orchestration)
**Version**: 1.0.0
**Status**: Production Ready
**Compliance**: ADR-007, ADR-010, ADR-002

## Purpose

The Vision-IoS Orchestrator executes Vision-IoS functions (FINN, STIG, LARS) in coordinated cycles, integrating with the foundation governance architecture. It provides automated, scheduled, and on-demand execution of Vision-IoS intelligence functions.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    VISION-IOS ORCHESTRATOR v1.0             │
│                          (LARS Agent)                        │
└────────────┬────────────────────────────────────┬───────────┘
             │                                    │
             │ Reads Tasks                        │ Logs Actions
             │                                    │
             ▼                                    ▼
    ┌─────────────────────┐           ┌──────────────────────┐
    │ fhq_governance      │           │ fhq_governance       │
    │ .task_registry      │           │ .governance_actions  │
    │                     │           │        _log          │
    │ - VISION_FUNCTION   │           │                      │
    │   tasks registered  │           │ - Cycle start/end    │
    └─────────────────────┘           │ - Execution evidence │
                                      │ - Hash chains        │
                                      └──────────────────────┘
             │
             │ Executes Functions
             │
             ▼
    ┌─────────────────────────────────────────────┐
    │  Vision-IoS Functions (Subprocess Execution) │
    ├─────────────────────────────────────────────┤
    │  1. signal_inference_baseline.py  (FINN)    │
    │  2. noise_floor_estimator.py      (STIG)    │
    │  3. meta_state_sync.py            (LARS)    │
    └─────────────────────────────────────────────┘
             │
             │ Writes State
             │
             ▼
    ┌─────────────────────┐
    │ vision_core         │
    │ .execution_state    │
    │                     │
    │ - Cycle results     │
    │ - Evidence bundles  │
    └─────────────────────┘
```

## Key Features

### 1. **Task Registry Integration** (ADR-007)
- Reads Vision-IoS functions from `fhq_governance.task_registry`
- Filters by `task_type = 'VISION_FUNCTION'` and `enabled = TRUE`
- Respects task ordering and configuration

### 2. **Subprocess Execution**
- Executes each function as isolated subprocess
- Timeout protection (default: 5 minutes per function)
- Captures stdout/stderr for evidence
- Returns structured execution results

### 3. **Governance Logging** (ADR-002)
- Logs cycle start: `VISION_ORCHESTRATOR_CYCLE_START`
- Logs cycle completion: `VISION_ORCHESTRATOR_CYCLE`
- All actions include hash chain IDs
- Cryptographic signatures per ADR-008 pattern

### 4. **State Reconciliation** (ADR-010)
- Writes execution state to `vision_core.execution_state`
- Stores complete evidence bundles
- Supports field-level reconciliation
- Integrates with VEGA attestation framework

### 5. **Execution Modes**
- **Single Cycle**: Run once and exit
- **Continuous Mode**: Run on interval (default: 1 hour)
- **Dry Run Mode**: Show execution plan without running
- **Filtered Execution**: Execute specific function only

### 6. **Performance Tracking**
- Records execution time per function
- Tracks success/failure counts
- Stores metrics in `vision_core.orchestrator_metrics`
- Performance views for analysis

## Installation

### Prerequisites

1. **Foundation Schemas** (from fhq-market-system)
   - `fhq_governance.task_registry`
   - `fhq_governance.governance_actions_log`

2. **Vision-IoS Schemas** (Migration 001)
   - `vision_core.execution_state`
   - `vision_signals.signal_baseline`
   - `vision_core.noise_profile`

3. **Vision-IoS Functions** (Migration 002)
   - 3 functions registered in task registry
   - Function files exist at paths specified in task_config

4. **Python Dependencies**
   ```bash
   pip install psycopg2-binary==2.9.9
   ```


### Environment Variables

Set database connection parameters:

```bash
export PGHOST=127.0.0.1
export PGPORT=54322
export PGDATABASE=postgres
export PGUSER=postgres
export PGPASSWORD=postgres

# Optional: Anthropic API key for LLM-enhanced functions
export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

### Single Cycle Execution

Run one orchestration cycle:

```bash
cd /path/to/vision-IoS
python 05_ORCHESTRATOR/orchestrator_v1.py
```

**Output**:
```
2025-11-23 14:30:00 - vision_ios_orchestrator - INFO - ======================================================================
2025-11-23 14:30:00 - vision_ios_orchestrator - INFO - VISION-IOS ORCHESTRATOR v1.0.0
2025-11-23 14:30:00 - vision_ios_orchestrator - INFO - Cycle ID: CYCLE_20251123_143000
2025-11-23 14:30:00 - vision_ios_orchestrator - INFO - Hash Chain: HC-LARS-ORCHESTRATOR-CYCLE_20251123_143000
2025-11-23 14:30:00 - vision_ios_orchestrator - INFO - ======================================================================
2025-11-23 14:30:00 - vision_ios_orchestrator - INFO - Connecting to database...
2025-11-23 14:30:00 - vision_ios_orchestrator - INFO - Database connection established
2025-11-23 14:30:00 - vision_ios_orchestrator - INFO - Reading Vision-IoS tasks from registry...
2025-11-23 14:30:00 - vision_ios_orchestrator - INFO - Found 3 enabled Vision-IoS functions
2025-11-23 14:30:00 - vision_ios_orchestrator - INFO - Cycle start logged: action_id=42
2025-11-23 14:30:00 - vision_ios_orchestrator - INFO -
2025-11-23 14:30:00 - vision_ios_orchestrator - INFO - [1/3] Executing: vision_signal_inference_baseline (Agent: FINN)
2025-11-23 14:30:15 - vision_ios_orchestrator - INFO - ✅ SUCCESS: vision_signal_inference_baseline
...
```

### Continuous Mode

Run on interval (default: 1 hour):

```bash
python 05_ORCHESTRATOR/orchestrator_v1.py --continuous
```

Custom interval (30 minutes):

```bash
python 05_ORCHESTRATOR/orchestrator_v1.py --continuous --interval=1800
```

### Dry Run Mode

Show execution plan without running functions:

```bash
python 05_ORCHESTRATOR/orchestrator_v1.py --dry-run
```

### Execute Specific Function

Run only one function:

```bash
python 05_ORCHESTRATOR/orchestrator_v1.py --function=vision_signal_inference_baseline
```

### Help

```bash
python 05_ORCHESTRATOR/orchestrator_v1.py --help
```

## Configuration

### Orchestrator Settings

Modify `Config` class in `orchestrator_v1.py`:

```python
class Config:
    CONTINUOUS_INTERVAL_SECONDS = 3600      # 1 hour
    FUNCTION_TIMEOUT_SECONDS = 300          # 5 minutes
```

### Schedule Configuration

Configure execution schedule in database:

```sql
UPDATE vision_core.orchestrator_schedule
SET interval_seconds = 1800  -- 30 minutes
WHERE schedule_name = 'vision_ios_hourly';
```

### Function Configuration

Update function settings via task registry:

```sql
UPDATE fhq_governance.task_registry
SET task_config = task_config || jsonb_build_object(
    'default_window_hours', 48  -- Increase analysis window
)
WHERE task_name = 'vision_signal_inference_baseline';
```

## Monitoring & Verification

### Check Latest Executions

```sql
SELECT * FROM vision_core.v_orchestrator_latest_executions
LIMIT 10;
```

**Output**:
```
 action_id |        timestamp        | cycle_status |        cycle_id        | tasks_executed | success_count | failure_count
-----------+-------------------------+--------------+------------------------+----------------+---------------+---------------
       156 | 2025-11-23 14:30:45+00  | COMPLETED    | CYCLE_20251123_143000  |              3 |             3 |             0
       155 | 2025-11-23 13:30:42+00  | COMPLETED    | CYCLE_20251123_133000  |              3 |             3 |             0
```

### Check Performance Summary

```sql
SELECT * FROM vision_core.v_orchestrator_performance;
```

**Output**:
```
 total_cycles_7d | total_tasks_executed | total_successes | total_failures | success_rate_percent |     earliest_cycle      |      latest_cycle
-----------------+----------------------+-----------------+----------------+----------------------+-------------------------+-------------------------
              24 |                   72 |              72 |              0 |               100.00 | 2025-11-16 14:00:00+00  | 2025-11-23 14:30:45+00
```

### Check Function Execution Evidence

```sql
SELECT
    action_id,
    timestamp,
    decision,
    metadata->>'function' AS function_name,
    metadata->>'agent_id' AS agent_id,
    metadata->'baseline_stats'->>'mean_price' AS mean_price
FROM fhq_governance.governance_actions_log
WHERE action_type = 'VISION_FUNCTION_EXECUTION'
ORDER BY timestamp DESC
LIMIT 10;
```

### Check Orchestrator State

```sql
SELECT
    state_id,
    component_name,
    state_type,
    state_value->>'cycle_id' AS cycle_id,
    state_value->>'cycle_status' AS cycle_status,
    (state_value->>'tasks_executed')::INTEGER AS tasks,
    created_at
FROM vision_core.execution_state
WHERE component_name = 'vision_ios_orchestrator'
ORDER BY created_at DESC
LIMIT 5;
```

## Evidence Bundles

Each orchestration cycle produces a complete evidence bundle stored in `vision_core.execution_state`:

```json
{
  "cycle_id": "CYCLE_20251123_143000",
  "orchestrator_version": "1.0.0",
  "execution_timestamp": "2025-11-23T14:30:45Z",
  "tasks_executed": 3,
  "cycle_status": "COMPLETED",
  "results": [
    {
      "task_name": "vision_signal_inference_baseline",
      "agent_id": "FINN",
      "success": true,
      "exit_code": 0,
      "execution_time_seconds": 12.34,
      "stdout": "..."
    },
    {
      "task_name": "vision_noise_floor_estimator",
      "agent_id": "STIG",
      "success": true,
      "exit_code": 0,
      "execution_time_seconds": 8.76,
      "stdout": "..."
    },
    {
      "task_name": "vision_meta_state_sync",
      "agent_id": "LARS",
      "success": true,
      "exit_code": 0,
      "execution_time_seconds": 5.43,
      "stdout": "..."
    }
  ]
}
```

## Compliance & Governance

### ADR-007: Orchestrator Architecture
- ✅ Integrates with foundation task registry
- ✅ Executes registered Vision-IoS functions
- ✅ Maintains agent identity (LARS)
- ✅ Supports deterministic execution

### ADR-010: State Reconciliation
- ✅ Writes execution state to vision_core
- ✅ Produces evidence bundles
- ✅ Supports field-level reconciliation
- ✅ Reconciliation rules defined in `fhq_meta.reconciliation_field_weights`

### ADR-002: Audit Trail
- ✅ Logs all cycles to `fhq_governance.governance_actions_log`
- ✅ Includes hash chain IDs
- ✅ Cryptographic signatures
- ✅ Complete execution evidence

### ADR-012: Economic Safety
- ✅ Timeout protection prevents runaway execution
- ✅ Failure isolation (one function failure doesn't stop cycle)
- ✅ Resource consumption tracking

## Troubleshooting

### Issue: "No tasks found"

**Cause**: No Vision-IoS functions registered or enabled.

**Solution**:
```sql
-- Check task registry
SELECT * FROM fhq_governance.task_registry
WHERE task_type = 'VISION_FUNCTION';

-- Re-run function registration
psql $DATABASE_URL -f 04_DATABASE/MIGRATIONS/002_register_vision_functions.sql
```

### Issue: "Function file not found"

**Cause**: Function path in `task_config` doesn't match actual file location.

**Solution**:
```sql
-- Check function paths
SELECT task_name, task_config->'function_path' AS path
FROM fhq_governance.task_registry
WHERE task_type = 'VISION_FUNCTION';

-- Update if needed
UPDATE fhq_governance.task_registry
SET task_config = task_config || jsonb_build_object(
    'function_path', 'correct/path/to/function.py'
)
WHERE task_name = 'vision_signal_inference_baseline';
```

### Issue: "Execution timeout"

**Cause**: Function takes longer than `FUNCTION_TIMEOUT_SECONDS` (default: 5 minutes).

**Solution**:
1. Investigate why function is slow
2. Increase timeout if needed:
   ```python
   Config.FUNCTION_TIMEOUT_SECONDS = 600  # 10 minutes
   ```

### Issue: Database connection failure

**Cause**: Database not running or incorrect connection parameters.

**Solution**:
```bash
# Check database is running
pg_isready -h 127.0.0.1 -p 54322

# Verify environment variables
echo $PGHOST $PGPORT $PGDATABASE

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

## Production Deployment

### Option 1: Systemd Service (Linux)

Create `/etc/systemd/system/vision-ios-orchestrator.service`:

```ini
[Unit]
Description=Vision-IoS Orchestrator v1.0
After=network.target postgresql.service

[Service]
Type=simple
User=vision
WorkingDirectory=/opt/vision-ios
Environment="PGHOST=127.0.0.1"
Environment="PGPORT=54322"
Environment="PGDATABASE=postgres"
Environment="PGUSER=vision"
Environment="PGPASSWORD=<password>"
ExecStart=/usr/bin/python3 /opt/vision-ios/05_ORCHESTRATOR/orchestrator_v1.py --continuous
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable vision-ios-orchestrator
sudo systemctl start vision-ios-orchestrator
sudo systemctl status vision-ios-orchestrator
```

### Option 2: Cron Job

Add to crontab:

```bash
# Run every hour
0 * * * * cd /opt/vision-ios && /usr/bin/python3 05_ORCHESTRATOR/orchestrator_v1.py >> /var/log/vision-ios/orchestrator.log 2>&1
```

### Option 3: Docker Container

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install psycopg2-binary==2.9.9

# Copy Vision-IoS
COPY . /app/

# Environment
ENV PGHOST=postgres
ENV PGPORT=5432
ENV PGDATABASE=postgres

CMD ["python", "05_ORCHESTRATOR/orchestrator_v1.py", "--continuous"]
```

## Testing

Run comprehensive test suite:

```bash
# Dry run test
python 05_ORCHESTRATOR/orchestrator_v1.py --dry-run

# Single cycle test
python 05_ORCHESTRATOR/orchestrator_v1.py

# Check database evidence
psql $DATABASE_URL -f 05_ORCHESTRATOR/test_orchestrator_v1_live.sql
```

## Version History

| Version | Date       | Changes |
|---------|------------|---------|
| 1.0.0   | 2025-11-23 | Initial production release |

## Support & Contact

**Owner**: LARS (Strategy & Orchestration)
**Governance**: VEGA (Auditor)
**Documentation**: `/vision-IoS/05_ORCHESTRATOR/`
**Migration**: `004_DATABASE/MIGRATIONS/017_orchestrator_registration.sql`

For issues, check governance logs:
```sql
SELECT * FROM fhq_governance.governance_actions_log
WHERE action_type LIKE 'VISION_ORCHESTRATOR%'
ORDER BY timestamp DESC
LIMIT 20;
