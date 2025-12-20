@echo off
REM FINN Cognitive Brain Launcher
REM STIG-2025-001 Phase 1-4 Complete

echo ============================================================
echo FINN COGNITIVE BRAIN - Phase 1-4 Integration
echo ============================================================
echo.
echo Components:
echo   - Phase 1: Circuit Breaker, Data Pools (497 assets)
echo   - Phase 2: StatArb, Grid, VBO, MeanRev engines
echo   - Phase 3: VarClus, Causal PCMCI, Thompson Bandit, RL
echo   - Phase 4: Information Foraging Orchestrator
echo.
echo Budget: $10/day (adjustable via --budget)
echo Cycle: 60 minutes (adjustable via --interval)
echo.

cd /d %~dp0
cd 03_FUNCTIONS

REM Check if running single test or continuous
if "%1"=="--test" (
    echo Running single test cycle...
    python finn_cognitive_brain.py --single
) else (
    echo Starting continuous operation...
    echo Press Ctrl+C to stop
    echo.
    python finn_cognitive_brain.py --interval 60 --budget 10.0
)

pause
