@echo off
REM ============================================================================
REM CEO-DIR-2026-SYSTEM-PRODUCTIONALIZATION-028
REM Directive 2.1: Windows Service Installation
REM ============================================================================
REM
REM Purpose: Install outcome_settlement_daemon.py as Windows Service
REM
REM Service Configuration:
REM   Name: FjordHQ_Settlement_Daemon
REM   Auto-start: enabled
REM   Recovery: restart on failure (60s delay)
REM
REM Requirements:
REM   - NSSM (Non-Sucking Service Manager) must be in PATH
REM   - Python 3.12+ must be in path
REM   - Administrative privileges
REM ============================================================================

echo ============================================================
echo FjordHQ Settlement Daemon - Windows Service Installation
echo CEO-DIR-2026-SYSTEM-PRODUCTIONALIZATION-028
echo ============================================================

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Administrative privileges required
    echo Please right-click and run as Administrator
    pause
    exit /b 1
)

REM Check if NSSM is available
where nssm >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: NSSM not found in PATH
    echo Download from: https://nssm.cc/download
    pause
    exit /b 1
)

REM Set service paths
set "SERVICE_DIR=C:\fhq-market-system\vision-ios\03_FUNCTIONS"
set "PYTHON_PATH=python"
set "SCRIPT_PATH=%SERVICE_DIR%\outcome_settlement_daemon.py"
set "SERVICE_NAME=FjordHQ_Settlement_Daemon"
set "LOG_PATH=%SERVICE_DIR%\outcome_settlement_daemon.log"

echo Service Directory: %SERVICE_DIR%
echo Script Path: %SCRIPT_PATH%
echo Log Path: %LOG_PATH%
echo.

REM Stop existing service if running
echo Checking for existing service...
nssm status "%SERVICE_NAME%" >nul 2>&1
if %errorLevel% equ 0 (
    echo Stopping existing service...
    nssm stop "%SERVICE_NAME%"
    nssm remove "%SERVICE_NAME%" confirm
)

REM Install new service
echo Installing service: %SERVICE_NAME%...
nssm install "%SERVICE_NAME%" "%PYTHON_PATH%" "%SCRIPT_PATH%" ^
    StartType AUTO ^
    AppDirectory "%SERVICE_DIR%" ^
    DisplayName "FjordHQ Settlement Daemon" ^
    Description "Settles PENDING decision packs to terminal states (EXECUTED, FAILED, ORPHANED_OUTCOME_MINING)" ^
    AppStdout "%LOG_PATH%" ^
    AppStderr "%LOG_PATH%" ^
    AppRotateFiles 1 ^
    AppRotateBytes 10485760

if %errorLevel% neq 0 (
    echo ERROR: Service installation failed
    pause
    exit /b 1
)

REM Configure recovery policy (restart on failure with 60s delay)
echo Configuring recovery policy...
nssm set "%SERVICE_NAME%" AppRestartDelay 60000
nssm set "%SERVICE_NAME%" AppThrottle 150000
nssm set "%SERVICE_NAME%" AppExit Default Restart
nssm set "%SERVICE_NAME%" AppRestartDelay 60000

if %errorLevel% neq 0 (
    echo ERROR: Recovery policy configuration failed
    pause
    exit /b 1
)

REM Start service
echo Starting service...
nssm start "%SERVICE_NAME%"

if %errorLevel% neq 0 (
    echo ERROR: Service start failed
    pause
    exit /b 1
)

echo ============================================================
echo Service Installation Complete
echo ============================================================
echo Service Name: %SERVICE_NAME%
echo Status: RUNNING
echo Log: %LOG_PATH%
echo.
echo Management Commands:
echo   - Check status: nssm status "%SERVICE_NAME%"
echo   - View log: type "%LOG_PATH%"
echo   - Stop service: nssm stop "%SERVICE_NAME%"
echo   - Start service: nssm start "%SERVICE_NAME%"
echo   - Restart service: nssm restart "%SERVICE_NAME%"
echo   - Remove service: nssm remove "%SERVICE_NAME%" confirm
echo ============================================================

pause
