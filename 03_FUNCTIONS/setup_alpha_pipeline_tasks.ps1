# ==============================================================================
# FjordHQ Alpha Pipeline - Windows Scheduled Tasks Setup
# ==============================================================================
# CEO Directive: CD-EC018-IOS004-ALPHA-PIPELINE-001
#
# This script creates Windows scheduled tasks for:
# 1. EC-018 Alpha Discovery - Runs every hour via orchestrator
# 2. IoS-004 Backtest Worker - Runs as daemon (on system startup + restart on failure)
# ==============================================================================

$ErrorActionPreference = "Stop"

# Configuration
$PYTHON_PATH = "python"
$BASE_DIR = "C:\fhq-market-system\vision-ios"
$FUNCTIONS_DIR = "$BASE_DIR\03_FUNCTIONS"
$LOGS_DIR = "$BASE_DIR\logs"

# Ensure logs directory exists
if (-not (Test-Path $LOGS_DIR)) {
    New-Item -ItemType Directory -Path $LOGS_DIR -Force | Out-Null
}

Write-Host "=== FjordHQ Alpha Pipeline Setup ===" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------------------------
# Task 1: IoS-004 Backtest Worker Daemon
# ------------------------------------------------------------------------------
Write-Host "[1/2] Setting up IoS-004 Backtest Worker Daemon..." -ForegroundColor Yellow

$ios004TaskName = "FHQ-IoS004-Backtest-Worker"
$ios004Action = New-ScheduledTaskAction `
    -Execute $PYTHON_PATH `
    -Argument "ios004_backtest_worker.py --daemon" `
    -WorkingDirectory $FUNCTIONS_DIR

# Run at system startup, restart on failure
$ios004Trigger = New-ScheduledTaskTrigger -AtStartup
$ios004Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 365)

# Check if task exists
$existingTask = Get-ScheduledTask -TaskName $ios004TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "  Task already exists, updating..." -ForegroundColor Gray
    Unregister-ScheduledTask -TaskName $ios004TaskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $ios004TaskName `
    -Action $ios004Action `
    -Trigger $ios004Trigger `
    -Settings $ios004Settings `
    -Description "IoS-004 Backtest Validation Worker - Listens for alpha proposals and runs backtests" `
    -RunLevel Highest | Out-Null

Write-Host "  [OK] IoS-004 task created: $ios004TaskName" -ForegroundColor Green

# ------------------------------------------------------------------------------
# Task 2: EC-018 Alpha Daemon (Hourly via Orchestrator - Optional standalone)
# ------------------------------------------------------------------------------
Write-Host "[2/2] Setting up EC-018 Alpha Discovery (standalone hourly)..." -ForegroundColor Yellow

$ec018TaskName = "FHQ-EC018-Alpha-Discovery"
$ec018Action = New-ScheduledTaskAction `
    -Execute $PYTHON_PATH `
    -Argument "ec018_alpha_daemon.py --once" `
    -WorkingDirectory $FUNCTIONS_DIR

# Run every hour
$ec018Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Hours 1)
$ec018Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

$existingTask = Get-ScheduledTask -TaskName $ec018TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "  Task already exists, updating..." -ForegroundColor Gray
    Unregister-ScheduledTask -TaskName $ec018TaskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $ec018TaskName `
    -Action $ec018Action `
    -Trigger $ec018Trigger `
    -Settings $ec018Settings `
    -Description "EC-018 Alpha Discovery Engine - Hourly alpha hypothesis generation" `
    -RunLevel Highest | Out-Null

Write-Host "  [OK] EC-018 task created: $ec018TaskName" -ForegroundColor Green

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Tasks Created:" -ForegroundColor White
Write-Host "  1. $ios004TaskName - Daemon (starts on boot, restarts on failure)"
Write-Host "  2. $ec018TaskName - Hourly schedule"
Write-Host ""
Write-Host "To start immediately:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName '$ios004TaskName'"
Write-Host "  Start-ScheduledTask -TaskName '$ec018TaskName'"
Write-Host ""
Write-Host "To check status:" -ForegroundColor Yellow
Write-Host "  Get-ScheduledTask -TaskName 'FHQ-*' | Format-Table TaskName, State"
Write-Host ""
Write-Host "NOTE: EC-018 is also registered in the orchestrator (task_registry)."
Write-Host "      The orchestrator will run it every hour if running continuously."
