@echo off
REM CEO-DIR-2026-RUNTIME-STABILIZATION-048 - All Services Setup

REM Decision Pack Generator
schtasks /delete /tn "FjordHQ_DecisionPackGenerator" /f 2>nul
schtasks /create /tn "FjordHQ_DecisionPackGenerator" /tr "C:\Python312\python.exe C:\fhq-market-system\vision-ios\03_FUNCTIONS\decision_pack_generator.py" /sc onstart /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_DecisionPackGenerator" 2>nul
timeout /t 2 /nobreak >nul

REM Alpha Graph Sync
schtasks /delete /tn "FjordHQ_AlphaGraphSync" /f 2>nul
schtasks /create /tn "FjordHQ_AlphaGraphSync" /tr "C:\Python312\python.exe C:\fhq-market-system\vision-ios\03_FUNCTIONS\alpha_graph_sync_scheduler.py" /sc onstart /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_AlphaGraphSync" 2>nul
timeout /t 2 /nobreak >nul

REM Runtime Watchdog
schtasks /delete /tn "FjordHQ_RuntimeWatchdog" /f 2>nul
schtasks /create /tn "FjordHQ_RuntimeWatchdog" /tr "C:\Python312\python.exe C:\fhq-market-system\vision-ios\03_FUNCTIONS\runtime_watchdog.py" /sc onstart /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_RuntimeWatchdog" 2>nul

REM Status
echo.
echo === Task Status ===
schtasks /query /tn "FjordHQ_OutcomeSettlement_Daemon" /fo LIST 2>nul
schtasks /query /tn "FjordHQ_DecisionPackGenerator" /fo LIST 2>nul
schtasks /query /tn "FjordHQ_AlphaGraphSync" /fo LIST 2>nul
schtasks /query /tn "FjordHQ_RuntimeWatchdog" /fo LIST 2>nul
echo.
echo Done. Press any key to continue.
pause >nul
