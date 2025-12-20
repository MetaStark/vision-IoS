@echo off
REM CCO DAEMON STARTUP - WAVE 17A
REM Simplified version for reliability

set PROJECT_ROOT=C:\fhq-market-system\vision-ios
set LOG_FILE=%PROJECT_ROOT%\logs\cco_daemon.log

echo [%DATE% %TIME%] CCO daemon starting >> "%LOG_FILE%"

REM Use py launcher (installed with Python)
py "%PROJECT_ROOT%\03_FUNCTIONS\cco_daemon.py" --continuous --interval 10 >> "%LOG_FILE%" 2>&1

echo [%DATE% %TIME%] CCO daemon exited with code %ERRORLEVEL% >> "%LOG_FILE%"
