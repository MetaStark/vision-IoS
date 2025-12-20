# CEO DIRECTIVE: IDIOT-PROOF DAILY PRICE INGESTION
## Directive ID: CD-IOS-001-DAILY-INGEST-BULLETPROOF-001
## Date: 2025-12-16
## Authority: CEO (Human Principal)
## Classification: CRITICAL INFRASTRUCTURE

---

## PROBLEM STATEMENT

Daily price ingestion has been "confirmed working" multiple times, yet consistently fails silently:
- 2025-12-16: Crypto prices 29 days stale despite "confirmed" daily ingest
- yfinance rate limiting causes silent failures
- Alpaca ingest fails on schema mismatches
- No alerting when ingestion fails
- No verification that data actually arrived

**This is unacceptable for production alpha discovery.**

---

## ROOT CAUSES IDENTIFIED

1. **Silent Failures**: Scripts log errors but don't alert humans
2. **Single Point of Failure**: Only one data source (yfinance or Alpaca)
3. **No Verification**: No post-ingest check that data is fresh
4. **Rate Limiting**: yfinance 429 errors kill entire batch
5. **Schema Drift**: Alpaca writes fail on missing columns
6. **Task Scheduler Issues**: Windows Task Scheduler tasks don't persist

---

## THE BULLETPROOF ARCHITECTURE

### Layer 1: Multi-Provider Fallback
```
Primary: Alpaca API (free, 200 req/min)
    ↓ (if fails)
Secondary: Yahoo Finance (free, rate limited)
    ↓ (if fails)
Tertiary: Manual Colab backfill notification
```

### Layer 2: Verification After Every Run
```python
def verify_freshness():
    """Run AFTER every ingest attempt."""
    query = """
        SELECT COUNT(*) as stale_count
        FROM (
            SELECT listing_id, MAX(date) as last_date
            FROM fhq_data.price_series
            GROUP BY listing_id
        ) sub
        WHERE last_date < CURRENT_DATE - INTERVAL '2 days'
    """
    if stale_count > 0:
        send_alert(f"ALERT: {stale_count} assets have stale data!")
```

### Layer 3: Multiple Trigger Points
1. **Windows Task Scheduler** - Primary (02:00 UTC daily)
2. **GitHub Actions** - Backup (03:00 UTC daily)
3. **Manual Dashboard Button** - Emergency fallback

### Layer 4: Alerting
- Failure: POST to webhook (Slack/Discord)
- Success: Log to governance table
- Verification failure: Email + webhook

---

## IMPLEMENTATION SPECIFICATION

### File: `ios001_bulletproof_ingest.py`

```python
"""
IoS-001 Bulletproof Daily Price Ingest
CEO Directive: CD-IOS-001-DAILY-INGEST-BULLETPROOF-001

This script WILL NOT FAIL SILENTLY.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
import requests

# Alerting webhook (configure in .env)
ALERT_WEBHOOK = os.getenv('ALERT_WEBHOOK_URL')

def send_alert(message: str, severity: str = 'ERROR'):
    """Send alert to configured webhook."""
    if ALERT_WEBHOOK:
        requests.post(ALERT_WEBHOOK, json={
            'text': f"[{severity}] IoS-001 Daily Ingest: {message}",
            'timestamp': datetime.utcnow().isoformat()
        })
    # Always log locally
    logging.error(f"ALERT [{severity}]: {message}")

def try_alpaca_ingest():
    """Attempt Alpaca API ingest."""
    # ... implementation
    pass

def try_yahoo_ingest():
    """Attempt Yahoo Finance ingest."""
    # ... implementation
    pass

def verify_data_freshness(conn) -> tuple[bool, int]:
    """Verify data is actually fresh. Returns (is_fresh, stale_count)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(DISTINCT listing_id) as stale_count
            FROM fhq_data.price_series
            GROUP BY listing_id
            HAVING MAX(date)::date < CURRENT_DATE - 2
        """)
        result = cur.fetchone()
        stale_count = result[0] if result else 0
        return stale_count == 0, stale_count

def main():
    start_time = datetime.utcnow()
    success = False
    method_used = None

    # Try Alpaca first
    try:
        alpaca_result = try_alpaca_ingest()
        if alpaca_result['success']:
            success = True
            method_used = 'ALPACA'
    except Exception as e:
        send_alert(f"Alpaca ingest failed: {e}", 'WARNING')

    # Fallback to Yahoo if Alpaca failed
    if not success:
        try:
            yahoo_result = try_yahoo_ingest()
            if yahoo_result['success']:
                success = True
                method_used = 'YAHOO'
        except Exception as e:
            send_alert(f"Yahoo ingest failed: {e}", 'WARNING')

    # CRITICAL: Verify data freshness regardless of reported success
    conn = get_connection()
    is_fresh, stale_count = verify_data_freshness(conn)

    if not is_fresh:
        send_alert(
            f"DATA VERIFICATION FAILED: {stale_count} assets still stale after ingest!",
            'CRITICAL'
        )
        # Log to governance for human review
        log_governance_event(conn, 'INGEST_VERIFICATION_FAILED', {
            'stale_count': stale_count,
            'method_attempted': method_used,
            'timestamp': datetime.utcnow().isoformat()
        })

    if not success:
        send_alert(
            "ALL INGEST METHODS FAILED - Manual intervention required!",
            'CRITICAL'
        )
        sys.exit(1)

    # Success logging
    elapsed = (datetime.utcnow() - start_time).total_seconds()
    log_governance_event(conn, 'INGEST_SUCCESS', {
        'method': method_used,
        'elapsed_seconds': elapsed,
        'verified_fresh': is_fresh
    })

    conn.close()

if __name__ == '__main__':
    main()
```

---

## VERIFICATION DASHBOARD REQUIREMENTS

Add to dashboard-2026:

### Price Health Indicator
```
[GREEN] All assets fresh (< 2 days old)
[YELLOW] Some assets stale (2-7 days old)
[RED] Critical: Many assets stale (> 7 days old)
```

### Last Ingest Status
```
Last successful ingest: 2025-12-16 02:00 UTC
Method: ALPACA
Assets updated: 28
Verification: PASSED
```

---

## TASK SCHEDULER SETUP (Windows)

### PowerShell Script: `setup_bulletproof_ingest_task.ps1`
```powershell
$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\fhq-market-system\vision-ios\03_FUNCTIONS\ios001_bulletproof_ingest.py"
$trigger = New-ScheduledTaskTrigger -Daily -At 3:00AM
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName "FHQ-IoS001-BulletproofIngest" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force

Write-Host "Task registered. Verify with: Get-ScheduledTask -TaskName 'FHQ-IoS001-BulletproofIngest'"
```

---

## GITHUB ACTIONS BACKUP

### File: `.github/workflows/daily-ingest.yml`
```yaml
name: Daily Price Ingest Backup

on:
  schedule:
    - cron: '0 3 * * *'  # 03:00 UTC daily
  workflow_dispatch:  # Manual trigger

jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python 03_FUNCTIONS/ios001_bulletproof_ingest.py
        env:
          PGHOST: ${{ secrets.PGHOST }}
          PGPASSWORD: ${{ secrets.PGPASSWORD }}
          ALERT_WEBHOOK_URL: ${{ secrets.ALERT_WEBHOOK_URL }}
```

---

## SUCCESS CRITERIA

This directive is considered implemented when:

1. [ ] `ios001_bulletproof_ingest.py` exists and handles multi-provider fallback
2. [ ] Verification step runs after EVERY ingest attempt
3. [ ] Alerts fire on ANY failure (ingest or verification)
4. [ ] Windows Task Scheduler task is registered and running
5. [ ] GitHub Actions workflow is configured as backup
6. [ ] Dashboard shows price health indicator
7. [ ] First 7 consecutive days of successful verified ingests logged

---

## ATTESTATION

**Directive issued by**: CEO (Human Principal)
**Date**: 2025-12-16
**Implementation deadline**: 2025-12-18
**Review date**: 2025-12-23 (after 7 days of operation)
