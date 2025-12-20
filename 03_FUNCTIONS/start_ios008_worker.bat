@echo off
REM IoS-008 Decision Engine Worker
REM Creates trading decisions from validated signals

echo ============================================================
echo IoS-008 DECISION ENGINE WORKER
echo ============================================================
echo Interval: 60 seconds
echo Press Ctrl+C to stop
echo ============================================================
echo.

cd /d "C:\fhq-market-system\vision-ios\03_FUNCTIONS"
python ios008_decision_worker.py --interval 60

pause
