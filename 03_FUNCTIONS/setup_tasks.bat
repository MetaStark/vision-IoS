@echo off
REM FjordHQ Alpha Pipeline - Scheduled Tasks Setup
REM Requires Administrator privileges

echo === FjordHQ Alpha Pipeline Setup ===
echo.

REM IoS-004 Backtest Worker - Run at startup
echo [1/2] Creating IoS-004 Backtest Worker task...
schtasks /Create /TN "FHQ-IoS004-Backtest-Worker" /TR "python C:\fhq-market-system\vision-ios\03_FUNCTIONS\ios004_backtest_worker.py --daemon" /SC ONSTART /F
if %ERRORLEVEL% EQU 0 (
    echo   [OK] IoS-004 task created
) else (
    echo   [ERROR] Failed to create IoS-004 task
)

REM EC-018 Alpha Discovery - Run hourly
echo [2/2] Creating EC-018 Alpha Discovery task...
schtasks /Create /TN "FHQ-EC018-Alpha-Discovery" /TR "python C:\fhq-market-system\vision-ios\03_FUNCTIONS\ec018_alpha_daemon.py --once" /SC HOURLY /F
if %ERRORLEVEL% EQU 0 (
    echo   [OK] EC-018 task created
) else (
    echo   [ERROR] Failed to create EC-018 task
)

echo.
echo === Setup Complete ===
echo.
echo To start tasks now:
echo   schtasks /Run /TN "FHQ-IoS004-Backtest-Worker"
echo   schtasks /Run /TN "FHQ-EC018-Alpha-Discovery"
echo.
echo To check status:
echo   schtasks /Query /TN "FHQ-IoS004-Backtest-Worker"
echo   schtasks /Query /TN "FHQ-EC018-Alpha-Discovery"
