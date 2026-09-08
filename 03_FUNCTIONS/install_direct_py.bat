@echo off
REM CEO-DIR-2026-RUNTIME-STABILIZATION-048 - Direct Python Execution

REM Delete old tasks first
schtasks /delete /tn "FjordHQ_OutcomeSettlement_Daemon" /f 2>nul
schtasks /delete /tn "FjordHQ_DecisionPackGenerator" /f 2>nul
schtasks /delete /tn "FjordHQ_AlphaGraphSync" /f 2>nul
schtasks /delete /tn "FjordHQ_RuntimeWatchdog" /f 2>nul

REM Decision Pack Generator - run once manually first
echo Running decision pack generator manually...
python decision_pack_generator.py

REM Create tasks for the others (skip decision pack generator for now)
schtasks /create /tn "FjordHQ_AlphaGraphSync" /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\alpha_graph_sync_scheduler.py" /sc onstart /rl highest /ru "SYSTEM" /f 2>nul
schtasks /create /tn "FjordHQ_RuntimeWatchdog" /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\runtime_watchdog_v2.py" /sc onstart /rl highest /ru "SYSTEM" /f 2>nul

REM Run alpha graph and watchdog
schtasks /run /tn "FjordHQ_AlphaGraphSync" 2>nul
schtasks /run /tn "FjordHQ_RuntimeWatchdog" 2>nul

timeout /t 5 /nobreak >nul

REM Decision Pack Generator - create task after manual run
schtasks /create /tn "FjordHQ_DecisionPackGenerator" /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\decision_pack_generator.py" /sc onstart /rl highest /ru "SYSTEM" /f 2>nul
schtasks /run /tn "FjordHQ_DecisionPackGenerator" 2>nul

REM Status
echo.
echo === Task Status ===
schtasks /query /tn "FjordHQ_OutcomeSettlement_Daemon" /fo LIST 2>nul
schtasks /query /tn "FjordHQ_DecisionPackGenerator" /fo LIST 2>nul
schtasks /query /tn "FjordHQ_AlphaGraphSync" /fo LIST 2>nul
schtasks /query /tn "FjordHQ_RuntimeWatchdog" /fo LIST 2>nul
echo.
echo Done.
pause >nul
