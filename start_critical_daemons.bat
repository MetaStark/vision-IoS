@echo off
REM FjordHQ Critical Daemon Starter
REM CEO-DIR-2026-DAEMON-MANAGEMENT
REM Execute from C:\fhq-market-system\vision-ios\

cd /d C:\fhq-market-system\vision-ios

echo ============================================================
echo FjordHQ Critical Daemon Starter
echo Date: %date% %time%
echo ============================================================

REM Create logs directory if not exists
if not exist "logs" mkdir logs

REM 1. FINN Brain Scheduler (30-minute cycles)
echo Starting finn_brain_scheduler...
start "FINN-Brain" /MIN cmd /c "python 03_FUNCTIONS\finn_brain_scheduler.py > logs\finn_brain_daemon.log 2>&1"

REM 2. FINN Crypto Scheduler (24/7 learning)
echo Starting finn_crypto_scheduler...
start "FINN-Crypto" /MIN cmd /c "python 03_FUNCTIONS\finn_crypto_scheduler.py > logs\finn_crypto_daemon.log 2>&1"

REM 3. Economic Outcome Daemon
echo Starting economic_outcome_daemon...
start "Economic-Outcome" /MIN cmd /c "python 03_FUNCTIONS\economic_outcome_daemon.py > logs\economic_outcome_daemon.log 2>&1"

REM 4. G2C Continuous Forecast Engine
echo Starting g2c_continuous_forecast_engine...
start "G2C-Forecast" /MIN cmd /c "python 03_FUNCTIONS\g2c_continuous_forecast_engine.py > logs\g2c_forecast_daemon.log 2>&1"

REM 5. iOS003b Intraday Regime Delta (15-min intervals)
echo Starting ios003b_intraday_regime_delta...
start "iOS003b-Regime" /MIN cmd /c "python 03_FUNCTIONS\ios003b_intraday_regime_delta.py > logs\ios003b_regime_daemon.log 2>&1"

echo ============================================================
echo All critical daemons started.
echo Check logs\ folder for output.
echo ============================================================

REM Keep window open for 5 seconds
timeout /t 5
