@echo off
cd /d C:\fhq-market-system\vision-ios\03_FUNCTIONS

REM Clear log
echo. > C:\fhq-market-system\vision-ios\logs\g2c_alpha_daemon.log

REM Start daemon
start /B python g2c_alpha_daemon.py

echo Daemon started. Waiting 30 seconds...
timeout /t 30 /nobreak > nul

echo === LOG OUTPUT ===
type C:\fhq-market-system\vision-ios\logs\g2c_alpha_daemon.log
