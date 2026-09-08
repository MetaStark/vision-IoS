@echo off
REM ============================================================================
REM FjordHQ System Verification
REM CEO-DIR-2026-024: Verify system is "breathing" (10-minute heartbeat)
REM ============================================================================

echo ======================================================================
echo FJORDHQ INSTITUTIONAL LEARNING - SYSTEM VERIFICATION
echo CEO-DIR-2026-024: Continuous Perception Validation
echo ======================================================================
echo.

echo Checking if Orchestrator and Evidence Daemon are running...
echo.

REM Check for FjordHQ Orchestrator window
tasklist /FI "WINDOWTITLE eq FjordHQ Orchestrator" 2>nul | find /I "python.exe" >nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Orchestrator: RUNNING
) else (
    echo [WARN] Orchestrator: NOT FOUND
    echo        Check if window "FjordHQ Orchestrator" is open
)

REM Check for FjordHQ Evidence Daemon window
tasklist /FI "WINDOWTITLE eq FjordHQ Evidence Daemon" 2>nul | find /I "python.exe" >nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Evidence Daemon: RUNNING
) else (
    echo [WARN] Evidence Daemon: NOT FOUND
    echo        Check if window "FjordHQ Evidence Daemon" is open
)

echo.
echo ======================================================================
echo DATABASE VERIFICATION (requires PostgreSQL connection)
echo ======================================================================
echo.
echo Run these SQL queries to verify system heartbeat:
echo.
echo 1. VERIFY R4 PROBES (should show 600-second intervals):
echo    SELECT timestamp,
echo           LAG(timestamp) OVER (ORDER BY timestamp) AS previous,
echo           EXTRACT(EPOCH FROM (timestamp - LAG(timestamp) OVER (ORDER BY timestamp)))::INTEGER AS interval_sec
echo    FROM fhq_governance.governance_actions_log
echo    WHERE initiated_by = 'LARS'
echo      AND timestamp ^>= '2026-01-09 00:24:00'
echo    ORDER BY timestamp DESC
echo    LIMIT 10;
echo.
echo 2. VERIFY EVIDENCE TABLE CREATED:
echo    SELECT table_name
echo    FROM information_schema.tables
echo    WHERE table_schema = 'vision_verification'
echo      AND table_name = 'cognitive_engine_evidence';
echo.
echo 3. VERIFY NO CIRCUIT BREAKER VIOLATIONS:
echo    SELECT COUNT(*) AS violations
echo    FROM fhq_governance.circuit_breaker_events
echo    WHERE event_timestamp ^>= '2026-01-09 00:24:00';
echo.
echo    Expected: violations = 0
echo.
echo ======================================================================
echo.
pause
