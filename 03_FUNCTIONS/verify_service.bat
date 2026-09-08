@echo off
REM ============================================================================
REM CEO-DIR-044: Task Verification Script
REM ============================================================================
echo.
echo ==========================================
echo Task Scheduler Status
echo ==========================================
schtasks /query /tn "FjordHQ_OutcomeSettlement_Daemon" /fo LIST
echo.
echo ==========================================
echo Running Python Processes
echo ==========================================
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE
echo.
echo ==========================================
echo Daemon Health (Database)
echo ==========================================
echo Run this SQL in your database client:
echo SELECT daemon_name, status, last_heartbeat,
echo        NOW() - last_heartbeat AS age_minutes,
echo        lifecycle_status
echo FROM fhq_monitoring.daemon_health
echo WHERE daemon_name = 'outcome_settlement_daemon';
echo.
echo ==========================================
echo Log File (last 20 lines)
echo ==========================================
if exist "C:\fhq-market-system\vision-ios\03_FUNCTIONS\outcome_settlement_daemon.log" (
    powershell -Command "Get-Content 'C:\fhq-market-system\vision-ios\03_FUNCTIONS\outcome_settlement_daemon.log' -Tail 20"
) else (
    echo [LOG NOT FOUND] Daemon has not written to log yet
)
echo.
pause
