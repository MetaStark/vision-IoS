@echo off
REM Create Windows Task Scheduler tasks for ios001 split ingest
REM UTC to CET: +1 hour
REM Crypto: 01:00 UTC = 02:00 CET (daily)
REM FX: 22:00 UTC = 23:00 CET (Sun-Thu)
REM Equity: 22:00 UTC = 23:00 CET (Mon-Fri)

set PYTHON_PATH=C:\Users\Orjan Skjold\AppData\Local\Programs\Python\Python312\python.exe
set SCRIPT_PATH=C:\fhq-market-system\vision-ios\03_FUNCTIONS\ios001_daily_ingest.py

echo Creating FHQ task folder...
schtasks /create /tn "FHQ\placeholder" /tr "cmd /c echo placeholder" /sc once /st 00:00 /f >nul 2>&1
schtasks /delete /tn "FHQ\placeholder" /f >nul 2>&1

echo Creating ios001_daily_ingest_crypto (02:00 CET daily)...
schtasks /create /tn "FHQ\ios001_daily_ingest_crypto" /tr "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\" --asset-class CRYPTO" /sc daily /st 02:00 /f

echo Creating ios001_daily_ingest_fx (23:00 CET Sun-Thu)...
schtasks /create /tn "FHQ\ios001_daily_ingest_fx" /tr "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\" --asset-class FX" /sc weekly /d SUN,MON,TUE,WED,THU /st 23:00 /f

echo Creating ios001_daily_ingest_equity (23:00 CET Mon-Fri)...
schtasks /create /tn "FHQ\ios001_daily_ingest_equity" /tr "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\" --asset-class EQUITY" /sc weekly /d MON,TUE,WED,THU,FRI /st 23:00 /f

echo.
echo Verifying created tasks...
schtasks /query /tn "FHQ\ios001_daily_ingest_crypto" /fo list
schtasks /query /tn "FHQ\ios001_daily_ingest_fx" /fo list
schtasks /query /tn "FHQ\ios001_daily_ingest_equity" /fo list

echo.
echo Done!
