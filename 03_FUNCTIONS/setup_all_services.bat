@echo off
echo Installing Decision Pack Generator...
schtasks /delete /tn "FjordHQ_DecisionPackGenerator" /f 2>nul
schtasks /create /tn "FjordHQ_DecisionPackGenerator" /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\run_decision_pack_generator.bat" /sc onstart /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_DecisionPackGenerator"
timeout /t 2 /nobreak >nul

echo Installing Alpha Graph Sync...
schtasks /delete /tn "FjordHQ_AlphaGraphSync" /f 2>nul
schtasks /create /tn "FjordHQ_AlphaGraphSync" /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\run_alpha_graph_sync.bat" /sc onstart /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_AlphaGraphSync"
timeout /t 2 /nobreak >nul

echo Installing Runtime Watchdog...
schtasks /delete /tn "FjordHQ_RuntimeWatchdog" /f 2>nul
schtasks /create /tn "FjordHQ_RuntimeWatchdog" /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\runtime_watchdog.py" /sc onstart /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_RuntimeWatchdog"

echo.
echo === Task Status ===
schtasks /query /tn "FjordHQ_OutcomeSettlement_Daemon" /fo LIST
schtasks /query /tn "FjordHQ_DecisionPackGenerator" /fo LIST
schtasks /query /tn "FjordHQ_AlphaGraphSync" /fo LIST
schtasks /query /tn "FjordHQ_RuntimeWatchdog" /fo LIST
pause
