@echo off
REM EC-018 Alpha Discovery Daemon
REM Generates alpha hypotheses every 2 minutes (120 seconds)

echo ============================================================
echo EC-018 ALPHA DISCOVERY DAEMON
echo ============================================================
echo Interval: 2 minutes
echo Press Ctrl+C to stop
echo ============================================================
echo.

cd /d "C:\fhq-market-system\vision-ios\03_FUNCTIONS"
python ec018_alpha_daemon.py --daemon --interval 2

pause
