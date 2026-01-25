@echo off
REM ============================================================
REM FjordHQ Daemon Watchdog - Task Scheduler Installation
REM Run As Administrator
REM ============================================================

cd /d C:\fhq-market-system\vision-ios

echo ============================================================
echo Installing FjordHQ Daemon Watchdog to Task Scheduler
echo ============================================================

REM Create the scheduled task
schtasks /create /tn "FjordHQ_Daemon_Watchdog" /tr "pythonw \"C:\fhq-market-system\vision-ios\03_FUNCTIONS\daemon_watchdog.py\"" /sc onstart /rl highest /f

if %errorlevel% equ 0 (
    echo [OK] Task created successfully
    echo.
    echo Starting watchdog now...
    schtasks /run /tn "FjordHQ_Daemon_Watchdog"
    echo.
    echo Task Status:
    schtasks /query /tn "FjordHQ_Daemon_Watchdog" /fo list | findstr "TaskName Status"
) else (
    echo [FAIL] Could not create task - run as Administrator
)

echo.
pause
