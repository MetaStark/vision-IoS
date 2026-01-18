@echo off
REM Calendar Integrity Daemon - CEO-DIR-2026-091
REM Scheduled to run daily at 05:00 (before market open)

cd /d C:\fhq-market-system\vision-ios\03_FUNCTIONS
python calendar_integrity_daemon.py --market US_EQUITY >> calendar_integrity_daemon.log 2>&1
