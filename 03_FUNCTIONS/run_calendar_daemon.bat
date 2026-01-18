@echo off
REM CEO-DIR-2026-088: Trading Calendar Governance Daemon
REM Scheduled to run monthly on the 1st at 03:00

cd /d C:\fhq-market-system\vision-ios\03_FUNCTIONS
python trading_calendar_governance_daemon.py >> calendar_daemon.log 2>&1
