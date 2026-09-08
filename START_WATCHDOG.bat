@echo off
REM ============================================================
REM FjordHQ Daemon Watchdog Starter
REM ============================================================
REM This starts the watchdog which manages all 5 critical daemons
REM The watchdog will automatically restart any daemon that crashes
REM ============================================================

cd /d C:\fhq-market-system\vision-ios

echo ============================================================
echo FjordHQ Daemon Watchdog
echo ============================================================
echo.
echo The watchdog will:
echo   - Start all 5 critical daemons
echo   - Monitor heartbeats every 60 seconds
echo   - Automatically restart crashed daemons
echo.
echo Press Ctrl+C to stop all daemons.
echo ============================================================
echo.

python 03_FUNCTIONS\daemon_watchdog.py
