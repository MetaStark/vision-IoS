@echo off
REM IoS-003C Shadow Learning - Learning Update
REM CEO-DIR-2026-093: 4x daily (00:00, 06:00, 12:00, 18:00 UTC)
REM Updates daily report with current shadow learning metrics

cd /d C:\fhq-market-system\vision-ios\03_FUNCTIONS
python ios003c_shadow_learning_daemon.py --task report --json > shadow_learning_latest.json

echo [%date% %time%] Learning update completed >> shadow_learning.log
