@echo off
REM FINN Cognitive Brain Scheduler Launcher
REM ========================================
REM Runs FINN Brain every 30 minutes for learning

echo ============================================================
echo FINN COGNITIVE BRAIN SCHEDULER
echo ============================================================
echo.
echo Starting scheduler with 30-minute intervals...
echo Press Ctrl+C to stop
echo.

cd /d "C:\fhq-market-system\vision-ios\03_FUNCTIONS"
python finn_brain_scheduler.py --interval 30

pause
