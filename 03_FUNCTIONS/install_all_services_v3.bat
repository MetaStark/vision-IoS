@echo off
REM CEO-DIR-2026-RUNTIME-STABILIZATION-048 - All Services Setup v3
REM FIX: Use wrapper batch files with hardcoded Python path

set FUNC_DIR=C:\fhq-market-system\vision-ios\03_FUNCTIONS

REM Decision Pack Generator - runs once, schedule hourly
schtasks /delete /tn "FjordHQ_DecisionPackGenerator" /f 2>nul
schtasks /create /tn "FjordHQ_DecisionPackGenerator" /tr "%FUNC_DIR%\run_decision_pack_generator.bat" /sc hourly /mo 1 /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_DecisionPackGenerator" 2>nul
timeout /t 2 /nobreak >nul

REM Alpha Graph Sync - run every 5 minutes
schtasks /delete /tn "FjordHQ_AlphaGraphSync" /f 2>nul
schtasks /create /tn "FjordHQ_AlphaGraphSync" /tr "%FUNC_DIR%\run_alpha_graph_sync.bat" /sc minute /mo 5 /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_AlphaGraphSync" 2>nul
timeout /t 2 /nobreak >nul

REM Outcome Settlement Daemon - run every 30 minutes (SLA target: 60 min, SLA limit: 75 min)
schtasks /delete /tn "FjordHQ_OutcomeSettlement_Daemon" /f 2>nul
schtasks /create /tn "FjordHQ_OutcomeSettlement_Daemon" /tr "%FUNC_DIR%\run_outcome_settlement_daemon.bat" /sc minute /mo 30 /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_OutcomeSettlement_Daemon" 2>nul
timeout /t 2 /nobreak >nul

REM Runtime Watchdog - run every 5 minutes (single cycle)
schtasks /delete /tn "FjordHQ_RuntimeWatchdog" /f 2>nul
schtasks /create /tn "FjordHQ_RuntimeWatchdog" /tr "%FUNC_DIR%\run_runtime_watchdog.bat" /sc minute /mo 5 /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_RuntimeWatchdog" 2>nul

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
