@echo off
cd /d C:\fhq-market-system\vision-ios\03_FUNCTIONS

REM Use absolute Python path to avoid PATH resolution failures (exit 9009)
REM Short path works from both user and SYSTEM contexts
set "PYTHON_EXE=C:\Users\RJANSK~1\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

"%PYTHON_EXE%" canonical_test_orchestrator_daemon.py >> orchestrator.log 2>&1
