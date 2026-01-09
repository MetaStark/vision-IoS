@echo off
REM CEO-DIR-2026-025: Phase 3 Calibration Daemon Scheduled Execution
REM Schedule: Daily 00:05 UTC (01:05 CET)
REM Mode: DEFENSIVE_ONLY - No parameter mutation permitted

cd /d C:\fhq-market-system\vision-ios

REM Set environment variables
set PGHOST=127.0.0.1
set PGPORT=54322
set PGDATABASE=postgres
set PGUSER=postgres
set PGPASSWORD=postgres

REM Execute daemon with logging
echo [%date% %time%] Starting Phase 3 Calibration Daemon >> 03_FUNCTIONS\phase3_scheduled.log
python 03_FUNCTIONS\phase3_calibration_daemon.py >> 03_FUNCTIONS\phase3_scheduled.log 2>&1
echo [%date% %time%] Daemon execution complete >> 03_FUNCTIONS\phase3_scheduled.log
