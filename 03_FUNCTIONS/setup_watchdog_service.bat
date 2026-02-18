@echo off
schtasks /delete /tn "FjordHQ_RuntimeWatchdog" /f
schtasks /create /tn "FjordHQ_RuntimeWatchdog" /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\runtime_watchdog.py" /sc onstart /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_RuntimeWatchdog"
schtasks /query /tn "FjordHQ_RuntimeWatchdog" /fo LIST
pause
