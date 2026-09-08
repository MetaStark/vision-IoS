@echo off
REM ============================================================
REM FjordHQ Daemon Installation - Run As Administrator
REM ============================================================
REM Right-click this file and select "Run as administrator"
REM ============================================================

cd /d C:\fhq-market-system\vision-ios

echo ============================================================
echo FjordHQ Daemon Installation
echo ============================================================
echo.
echo This will create Windows Scheduled Tasks for all 5 daemons.
echo Tasks will start automatically at system startup.
echo.
echo Press any key to continue or Ctrl+C to cancel...
pause > nul

echo.
echo Creating scheduled tasks...
echo.

REM 1. FINN Brain Scheduler
schtasks /create /tn "FjordHQ_FINN_Brain" /tr "python \"C:\fhq-market-system\vision-ios\03_FUNCTIONS\finn_brain_scheduler.py\"" /sc onstart /rl highest /f
if %errorlevel% equ 0 (echo [OK] FjordHQ_FINN_Brain created) else (echo [FAIL] FjordHQ_FINN_Brain)

REM 2. FINN Crypto Scheduler
schtasks /create /tn "FjordHQ_FINN_Crypto" /tr "python \"C:\fhq-market-system\vision-ios\03_FUNCTIONS\finn_crypto_scheduler.py\"" /sc onstart /rl highest /f
if %errorlevel% equ 0 (echo [OK] FjordHQ_FINN_Crypto created) else (echo [FAIL] FjordHQ_FINN_Crypto)

REM 3. Economic Outcome Daemon
schtasks /create /tn "FjordHQ_Economic_Outcome" /tr "python \"C:\fhq-market-system\vision-ios\03_FUNCTIONS\economic_outcome_daemon.py\"" /sc onstart /rl highest /f
if %errorlevel% equ 0 (echo [OK] FjordHQ_Economic_Outcome created) else (echo [FAIL] FjordHQ_Economic_Outcome)

REM 4. G2C Forecast Engine
schtasks /create /tn "FjordHQ_G2C_Forecast" /tr "python \"C:\fhq-market-system\vision-ios\03_FUNCTIONS\g2c_continuous_forecast_engine.py\"" /sc onstart /rl highest /f
if %errorlevel% equ 0 (echo [OK] FjordHQ_G2C_Forecast created) else (echo [FAIL] FjordHQ_G2C_Forecast)

REM 5. iOS003b Regime Delta
schtasks /create /tn "FjordHQ_iOS003b_Regime" /tr "python \"C:\fhq-market-system\vision-ios\03_FUNCTIONS\ios003b_intraday_regime_delta.py\"" /sc onstart /rl highest /f
if %errorlevel% equ 0 (echo [OK] FjordHQ_iOS003b_Regime created) else (echo [FAIL] FjordHQ_iOS003b_Regime)

echo.
echo ============================================================
echo Starting all daemons now...
echo ============================================================
echo.

schtasks /run /tn "FjordHQ_FINN_Brain"
schtasks /run /tn "FjordHQ_FINN_Crypto"
schtasks /run /tn "FjordHQ_Economic_Outcome"
schtasks /run /tn "FjordHQ_G2C_Forecast"
schtasks /run /tn "FjordHQ_iOS003b_Regime"

echo.
echo ============================================================
echo Installation complete!
echo ============================================================
echo.
echo Tasks created:
schtasks /query /tn "FjordHQ_FINN_Brain" /fo list | findstr "TaskName Status"
schtasks /query /tn "FjordHQ_FINN_Crypto" /fo list | findstr "TaskName Status"
schtasks /query /tn "FjordHQ_Economic_Outcome" /fo list | findstr "TaskName Status"
schtasks /query /tn "FjordHQ_G2C_Forecast" /fo list | findstr "TaskName Status"
schtasks /query /tn "FjordHQ_iOS003b_Regime" /fo list | findstr "TaskName Status"
echo.
echo Daemons will now run continuously and restart on system boot.
echo.
pause
