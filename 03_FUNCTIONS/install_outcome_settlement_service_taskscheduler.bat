@echo off
REM ============================================================================
REM CEO-DIR-044: Outcome Settlement Daemon Continuous Service Installation
REM ============================================================================
REM PURPOSE: Install outcome_settlement_daemon as continuous Windows service
REM           using Task Scheduler (NSSM not available)
REM
REM AUTHORITY: CEO-DIR-2026-SETTLEMENT-DAEMON-CONTINUOUS-SERVICE-044
REM EFFECTIVE: 2026-02-16
REM AUTHOR: STIG (EC-003)
REM ============================================================================

setlocal

set "TASK_NAME=FjordHQ_OutcomeSettlement_Daemon"
set "SCRIPT_DIR=C:\fhq-market-system\vision-ios\03_FUNCTIONS"
set "PYTHON_PATH=C:\Python312\python.exe"
set "DAEMON_SCRIPT=outcome_settlement_daemon.py"
set "DAEMON_ARGS=--continuous --interval 3600"
set "TASK_RUN=%PYTHON_PATH% \"%SCRIPT_DIR%\%DAEMON_SCRIPT%\" %DAEMON_ARGS%"

echo [%DATE% %TIME%] Installing %TASK_NAME% via Task Scheduler...
echo.

REM Delete existing task if it exists
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

REM Create new task - runs at system startup, auto-restart on failure
schtasks /create /tn "%TASK_NAME%" ^
    /tr "%TASK_RUN%" ^
    /sc onstart ^
    /rl highest ^
    /ru "SYSTEM" ^
    /f

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Task Scheduler create failed with code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

echo [SUCCESS] %TASK_NAME% created
echo.
echo Starting task...
schtasks /run /tn "%TASK_NAME%"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to start %TASK_NAME%, error code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

echo [SUCCESS] %TASK_NAME% started
echo.
echo Task Configuration:
schtasks /query /tn "%TASK_NAME%" /fo LIST /v
echo.
echo Verification: Check task status below
schtasks /query /tn "%TASK_NAME%" /fo LIST

endlocal
