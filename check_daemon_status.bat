@echo off
REM FjordHQ Daemon Status Checker
REM CEO-DIR-2026-DAEMON-MANAGEMENT

cd /d C:\fhq-market-system\vision-ios

echo ============================================================
echo FjordHQ Daemon Status Check
echo Date: %date% %time%
echo ============================================================

echo.
echo Running Python processes:
echo -------------------------
tasklist /FI "IMAGENAME eq python.exe" /V

echo.
echo Press any key to close...
pause > nul
