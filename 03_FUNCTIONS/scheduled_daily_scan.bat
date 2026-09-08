@echo off
REM FHQ Daily Scan — Volatility Observer + Micro-Regime Classifier
REM Scheduled via Windows Task Scheduler
REM Directive: CEO-DIR-2026-OPS-ALPHA-002A / CEO-DIR-2026-OPS-MICROREGIME-003
REM Author: STIG (EC-003)

REM Use PowerShell for locale-safe date formatting
for /f %%i in ('powershell -Command "Get-Date -Format yyyyMMdd"') do set DATESTR=%%i
for /f %%i in ('powershell -Command "Get-Date -Format HHmmss"') do set TIMESTR=%%i

set LOGFILE=C:\fhq-market-system\vision-ios\03_FUNCTIONS\evidence\daily_scan_%DATESTR%.log
set PYTHON=C:\Users\Ørjan Skjold\AppData\Local\Programs\Python\Python312\python.exe
set WORKDIR=C:\fhq-market-system\vision-ios

echo ============================================ >> "%LOGFILE%"
echo FHQ Daily Scan — %DATESTR% %TIMESTR% >> "%LOGFILE%"
echo ============================================ >> "%LOGFILE%"

cd /d "%WORKDIR%"

echo. >> "%LOGFILE%"
echo [1/2] Volatility Observer --scan >> "%LOGFILE%"
echo Started: %TIME% >> "%LOGFILE%"
"%PYTHON%" 03_FUNCTIONS\volatility_observer.py --scan >> "%LOGFILE%" 2>&1
echo Exit code: %ERRORLEVEL% >> "%LOGFILE%"

echo. >> "%LOGFILE%"
echo [2/2] Micro-Regime Classifier --classify >> "%LOGFILE%"
echo Started: %TIME% >> "%LOGFILE%"
"%PYTHON%" 03_FUNCTIONS\micro_regime_classifier.py --classify >> "%LOGFILE%" 2>&1
echo Exit code: %ERRORLEVEL% >> "%LOGFILE%"

echo. >> "%LOGFILE%"
echo Completed: %TIME% >> "%LOGFILE%"
echo ============================================ >> "%LOGFILE%"
