@echo off
chcp 65001 >nul
REM Fix Windows Task Scheduler tasks for ios001 split ingest
REM Issue: Original tasks used "Orjan" instead of "Ørjan" in path

set "PYTHON_PATH=C:\Users\Ørjan Skjold\AppData\Local\Programs\Python\Python312\python.exe"
set "SCRIPT_PATH=C:\fhq-market-system\vision-ios\03_FUNCTIONS\ios001_daily_ingest.py"

echo Deleting old tasks...
schtasks /delete /tn "FHQ\ios001_daily_ingest_crypto" /f >nul 2>&1
schtasks /delete /tn "FHQ\ios001_daily_ingest_fx" /f >nul 2>&1
schtasks /delete /tn "FHQ\ios001_daily_ingest_equity" /f >nul 2>&1

echo Creating ios001_daily_ingest_crypto (02:00 CET daily)...
schtasks /create /tn "FHQ\ios001_daily_ingest_crypto" /tr "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\" --asset-class CRYPTO" /sc daily /st 02:00 /f

echo Creating ios001_daily_ingest_fx (23:00 CET Sun-Thu)...
schtasks /create /tn "FHQ\ios001_daily_ingest_fx" /tr "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\" --asset-class FX" /sc weekly /d SUN,MON,TUE,WED,THU /st 23:00 /f

echo Creating ios001_daily_ingest_equity (23:00 CET Mon-Fri)...
schtasks /create /tn "FHQ\ios001_daily_ingest_equity" /tr "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\" --asset-class EQUITY" /sc weekly /d MON,TUE,WED,THU,FRI /st 23:00 /f

echo.
echo Verifying tasks...
schtasks /query /tn "FHQ\ios001_daily_ingest_crypto" /fo list | findstr "Task To Run"
schtasks /query /tn "FHQ\ios001_daily_ingest_fx" /fo list | findstr "Task To Run"
schtasks /query /tn "FHQ\ios001_daily_ingest_equity" /fo list | findstr "Task To Run"

echo.
echo Done! Tasks recreated with correct path.
