@echo off
REM IoS-003C Shadow Learning - Weekly Analysis
REM CEO-DIR-2026-093: Weekly (Sunday @ 00:00 UTC)
REM Runs bootstrap significance test, regime persistence analysis, VEGA attestation

cd /d C:\fhq-market-system\vision-ios\03_FUNCTIONS
python ios003c_shadow_learning_daemon.py --task weekly

echo [%date% %time%] IoS-003C Weekly Analysis completed >> shadow_learning.log
