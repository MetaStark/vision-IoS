@echo off
REM IoS-003C Shadow Learning - Epoch Snapshot
REM CEO-DIR-2026-093: Daily @ 00:05 UTC
REM Captures crypto regime predictions for shadow learning

cd /d C:\fhq-market-system\vision-ios\03_FUNCTIONS
python ios003c_shadow_learning_daemon.py --task snapshot

echo [%date% %time%] IoS-003C Epoch Snapshot completed >> shadow_learning.log
