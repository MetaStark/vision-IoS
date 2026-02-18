@echo off
REM CEO-DIR-045: Run outcome_settlement_daemon in continuous mode
setlocal

cd /d C:\fhq-market-system\vision-ios\03_FUNCTIONS

echo [%DATE% %TIME%] Starting outcome_settlement_daemon in continuous mode...
echo.
echo This will run the daemon with 1-hour intervals.
echo To stop: Ctrl+C or close this window.
echo.

:LOOP
C:\Python312\python.exe outcome_settlement_daemon.py --once
if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] Cycle completed. Waiting 3600 seconds...
    timeout /t 3600
    goto LOOP
) else (
    echo [%DATE% %TIME%] ERROR: Daemon exited with code %ERRORLEVEL%
    pause
)

endlocal
