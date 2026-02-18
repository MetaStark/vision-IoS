@echo off
REM CEO-DIR-2026-RUNTIME-STABILIZATION-048 - All Services Setup v2

REM Decision Pack Generator
schtasks /delete /tn "FjordHQ_DecisionPackGenerator" /f 2>nul
schtasks /create /tn "FjordHQ_DecisionPackGenerator" /tr "cmd /c cd /d C:\fhq-market-system\vision-ios\03_FUNCTIONS && python decision_pack_generator.py" /sc onstart /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_DecisionPackGenerator" 2>nul
timeout /t 3 /nobreak >nul

REM Alpha Graph Sync
schtasks /delete /tn "FjordHQ_AlphaGraphSync" /f 2>nul
schtasks /create /tn "FjordHQ_AlphaGraphSync" /tr "cmd /c cd /d C:\fhq-market-system\vision-ios\03_FUNCTIONS && python alpha_graph_sync_scheduler.py" /sc onstart /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_AlphaGraphSync" 2>nul
timeout /t 3 /nobreak >nul

REM Runtime Watchdog
schtasks /delete /tn "FjordHQ_RuntimeWatchdog" /f 2>nul
schtasks /create /tn "FjordHQ_RuntimeWatchdog" /tr "cmd /c cd /d C:\fhq-market-system\vision-ios\03_FUNCTIONS && python runtime_watchdog_v2.py" /sc onstart /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_RuntimeWatchdog" 2>nul

REM Status
echo.
echo === Task Status ===
schtasks /query /tn "FjordHQ_OutcomeSettlement_Daemon" /fo LIST
schtasks /query /tn "FjordHQ_DecisionPackGenerator" /fo LIST
schtasks /query /tn "FjordHQ_AlphaGraphSync" /fo LIST
schtasks /query /tn "FjordHQ_RuntimeWatchdog" /fo LIST
echo.
echo Done.
pause >nul
