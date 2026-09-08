@echo off
REM IoS-003C Shadow Learning - Outcome Computation
REM CEO-DIR-2026-093: Daily @ 04:00 UTC
REM Computes outcomes for previous predictions and updates quality metrics

cd /d C:\fhq-market-system\vision-ios\03_FUNCTIONS
python ios003c_shadow_learning_daemon.py --task outcomes

REM Also check Gate 3 eligibility
python ios003c_shadow_learning_daemon.py --task gate3

echo [%date% %time%] IoS-003C Outcomes computed >> shadow_learning.log
