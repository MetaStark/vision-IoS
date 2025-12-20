@echo off
REM ============================================================
REM FJORDHQ FULL ALPHA SYSTEM STARTUP
REM ============================================================
REM Starts all components for autonomous alpha generation and execution
REM
REM Components:
REM   1. EC-018 Alpha Daemon (hypothesis generation) - 2 min interval
REM   2. IoS-004 Backtest Worker (validation) - NOTIFY listener
REM   3. IoS-008 Decision Worker (decision engine) - 60s interval
REM   4. FINN Brain Scheduler (execution) - 30 min interval
REM ============================================================

echo ============================================================
echo FJORDHQ ALPHA SYSTEM - FULL STARTUP
echo ============================================================
echo.

cd /d "C:\fhq-market-system\vision-ios\03_FUNCTIONS"

REM Create logs directory if not exists
if not exist "C:\fhq-market-system\vision-ios\logs" mkdir "C:\fhq-market-system\vision-ios\logs"

echo Starting EC-018 Alpha Daemon (2 min interval)...
start "EC-018 Alpha Daemon" cmd /k "python ec018_alpha_daemon.py --daemon --interval 2"
timeout /t 3 /nobreak >nul

echo Starting IoS-004 Backtest Worker...
start "IoS-004 Backtest" cmd /k "python ios004_backtest_worker.py --daemon"
timeout /t 3 /nobreak >nul

echo Starting IoS-008 Decision Worker...
start "IoS-008 Decision" cmd /k "python ios008_decision_worker.py --interval 60"
timeout /t 3 /nobreak >nul

echo Starting FINN Brain Scheduler (30 min interval)...
start "FINN Brain" cmd /k "python finn_brain_scheduler.py --interval 30"

echo.
echo ============================================================
echo ALL COMPONENTS STARTED
echo ============================================================
echo.
echo Running processes:
echo   [1] EC-018 Alpha Daemon    - Generates alpha hypotheses
echo   [2] IoS-004 Backtest       - Validates hypotheses
echo   [3] IoS-008 Decision       - Creates trading decisions
echo   [4] FINN Brain Scheduler   - Executes trades via Alpaca
echo.
echo Dashboard: http://localhost:3001/alpha
echo.
echo Close all windows to stop the system.
echo ============================================================

pause
