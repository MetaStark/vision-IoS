@echo off
REM CEO-DIR-2025-SENT-001: Daily Sentinel Execution
REM Scheduled to run at 02:30-03:30 UTC (03:30 CET)
REM
REM Exit codes:
REM   0 = INFO/WARN (system healthy)
REM   1 = ALERT (notify CEO+VEGA)
REM   2 = BLOCK (halt downstream execution)

cd /d C:\fhq-market-system\vision-ios\03_FUNCTIONS

REM Use absolute Python path to avoid PATH resolution failures (exit 9009)
REM Short path works from both user and SYSTEM contexts
set "PYTHON_EXE=C:\Users\RJANSK~1\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

"%PYTHON_EXE%" ceo_dir_2025_data_sentinel.py

exit /b %ERRORLEVEL%
