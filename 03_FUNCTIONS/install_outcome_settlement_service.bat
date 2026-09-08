@echo off
REM ============================================================================
REM CEO-DIR-044: Outcome Settlement Daemon Continuous Service Installation
REM ============================================================================
REM
REM PURPOSE: Install outcome_settlement_daemon as continuous Windows service
REM
REM AUTHORITY: CEO-DIR-2026-SETTLEMENT-DAEMON-CONTINUOUS-SERVICE-044
REM EFFECTIVE: 2026-02-16
REM AUTHOR: STIG (EC-003)
REM ============================================================================

setlocal enabledelayedexpansion

set "SERVICE_NAME=FjordHQ_OutcomeSettlement_Daemon"
set "SCRIPT_DIR=C:\fhq-market-system\vision-ios\03_FUNCTIONS"
set "PYTHON_PATH=C:\Python312\python.exe"
set "DAEMON_SCRIPT=outcome_settlement_daemon.py"
set "DAEMON_ARGS=--continuous --interval 3600"

echo [%DATE% %TIME%] Installing %SERVICE_NAME%...

REM Check if NSSM is available
where nssm >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Using NSSM for service installation
    nssm install %SERVICE_NAME% "%PYTHON_PATH%" "%SCRIPT_DIR%\%DAEMON_SCRIPT%" %DAEMON_ARGS%
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] NSSM install failed with code %ERRORLEVEL%
        exit /b %ERRORLEVEL%
    )

    nssm set %SERVICE_NAME% StartType AUTO
    nssm set %SERVICE_NAME% AppDirectory "%SCRIPT_DIR%"
    nssm set %SERVICE_NAME% AppStdout "%SCRIPT_DIR%\%DAEMON_NAME%.log"
    nssm set %SERVICE_NAME% AppStderr "%SCRIPT_DIR%\%DAEMON_NAME%.log"

    nssm start %SERVICE_NAME%
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to start %SERVICE_NAME%, error code %ERRORLEVEL%
        exit /b %ERRORLEVEL%
    )

    echo [SUCCESS] %SERVICE_NAME% installed and started
) else (
    echo NSSM not available, using Task Scheduler
    schtasks /create /tn "%SERVICE_NAME%" /tr "StartDaemon" /sc onstart /delay 60 /rl highest /ru "SYSTEM" ^
        /tn "%SERVICE_NAME%" /tr "RunDaemon" /sc onstart /delay 60 /rl highest /ru "SYSTEM" ^
        /st "%PYTHON_PATH%" "%SCRIPT_DIR%\%DAEMON_SCRIPT%" %DAEMON_ARGS%

    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Task Scheduler create failed with code %ERRORLEVEL%
        exit /b %ERRORLEVEL%
    )

    schtasks /run /tn "%SERVICE_NAME%"
    echo [SUCCESS] %SERVICE_NAME% scheduled via Task Scheduler
)

endlocal
