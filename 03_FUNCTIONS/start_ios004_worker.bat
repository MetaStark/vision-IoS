@echo off
REM IoS-004 Backtest Validation Worker
REM Listens for new hypotheses and runs backtests

echo ============================================================
echo IoS-004 BACKTEST VALIDATION WORKER
echo ============================================================
echo Mode: NOTIFY/LISTEN (triggered by database)
echo Press Ctrl+C to stop
echo ============================================================
echo.

cd /d "C:\fhq-market-system\vision-ios\03_FUNCTIONS"
python ios004_backtest_worker.py --daemon

pause
