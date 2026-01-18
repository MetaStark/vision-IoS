@echo off
REM CEO-DIR-2026-088: Create Trading Calendar Governance Scheduled Task
REM Run this as Administrator

echo Creating scheduled task: FjordHQ-TradingCalendarGovernance

schtasks /create /tn "FjordHQ-TradingCalendarGovernance" /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\run_calendar_daemon.bat" /sc monthly /d 1 /st 03:00 /f

echo.
echo Verifying task creation:
schtasks /query /tn "FjordHQ-TradingCalendarGovernance" /fo list

pause
