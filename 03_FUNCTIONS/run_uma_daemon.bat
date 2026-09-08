@echo off
REM UMA: Universal Meta-Analyst Daemon
REM Scheduled to run daily at 06:00

cd /d C:\fhq-market-system\vision-ios\03_FUNCTIONS
python uma_meta_analyst_daemon.py >> uma_daemon.log 2>&1
