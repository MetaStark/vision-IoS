@echo off
REM ============================================================================
REM FjordHQ Institutional Learning Activation
REM CEO-DIR-2026-024: Start Orchestrator + Evidence Unification Daemon
REM ============================================================================

echo ======================================================================
echo FJORDHQ INSTITUTIONAL LEARNING - SYSTEM STARTUP
echo CEO-DIR-2026-024: Continuous Perception + Evidence Unification
echo ======================================================================
echo.

REM Start Orchestrator in separate window
echo Starting Orchestrator (10-minute probe cycle)...
start "FjordHQ Orchestrator" /D "C:\fhq-market-system\vision-ios\05_ORCHESTRATOR" python orchestrator_v1.py --cnrp-continuous

timeout /t 3 /nobreak >nul

REM Start Evidence Unification Daemon in separate window
echo Starting Evidence Unification Daemon (10-minute sync cycle)...
start "FjordHQ Evidence Daemon" /D "C:\fhq-market-system\vision-ios\03_FUNCTIONS" python evidence_unification_daemon.py

timeout /t 2 /nobreak >nul

echo.
echo ======================================================================
echo SYSTEM ACTIVATED
echo ======================================================================
echo.
echo Two new windows opened:
echo   1. FjordHQ Orchestrator - 10-minute R4 probe cycle
echo   2. FjordHQ Evidence Daemon - 10-minute evidence sync
echo.
echo Both daemons will run continuously until closed.
echo.
echo Verify startup:
echo   - Orchestrator window should show "CNRP_R4_INTERVAL_SECONDS = 600"
echo   - Evidence Daemon window should show "Sync interval: 600 seconds"
echo.
echo Mantra: Eliminate Noise. Generate Signal. Move fast and verify things.
echo ======================================================================
echo.
pause
