# =====================================================================
# IoS-001 BULLETPROOF INGEST - WINDOWS TASK SCHEDULER SETUP (USER LEVEL)
# =====================================================================
# CEO Directive: CD-IOS-001-DAILY-INGEST-BULLETPROOF-001
# Date: 2025-12-17
#
# This script creates Windows Task Scheduler tasks for bulletproof
# daily price ingestion - runs as current user (no admin required).
#
# Usage:
#   .\setup_bulletproof_ingest_task_user.ps1
#
# Tasks Created:
#   1. FHQ-IoS001-Bulletproof-CRYPTO  - Daily 02:00 UTC (03:00 CET)
#   2. FHQ-IoS001-Bulletproof-EQUITY  - Weekdays 22:30 UTC (23:30 CET)
#   3. FHQ-IoS001-Bulletproof-FX      - Weekdays 22:30 UTC (23:30 CET)
#
# =====================================================================

$ErrorActionPreference = "Stop"

# Configuration - use full Python path for Task Scheduler
$PythonPath = (Get-Command python).Source
$ScriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\ios001_bulletproof_ingest.py"
$WorkingDir = "C:\fhq-market-system\vision-ios\03_FUNCTIONS"

Write-Host "Python path: $PythonPath" -ForegroundColor Gray

# Verify script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath"
    exit 1
}

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "IoS-001 BULLETPROOF INGEST - USER-LEVEL TASK SETUP" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "Running as: $env:USERNAME" -ForegroundColor Gray
Write-Host ""

# Common settings - user level, wake to run
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 10)

# =====================================================================
# TASK 1: CRYPTO - Daily 02:00 UTC (03:00 CET)
# =====================================================================

Write-Host "[CRYPTO] Creating daily crypto ingest task..." -ForegroundColor Yellow

$cryptoAction = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`" --asset-class CRYPTO" `
    -WorkingDirectory $WorkingDir

$cryptoTrigger = New-ScheduledTaskTrigger `
    -Daily `
    -At "03:00"

try {
    Unregister-ScheduledTask -TaskName "FHQ-IoS001-Bulletproof-CRYPTO" -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

$cryptoTask = Register-ScheduledTask `
    -TaskName "FHQ-IoS001-Bulletproof-CRYPTO" `
    -Action $cryptoAction `
    -Trigger $cryptoTrigger `
    -Settings $settings `
    -Description "IoS-001 Bulletproof Daily Price Ingest - CRYPTO (02:00 UTC daily)"

Write-Host "[+] CRYPTO task registered" -ForegroundColor Green
Write-Host "    Schedule: Daily at 03:00 CET (02:00 UTC)" -ForegroundColor Gray

# =====================================================================
# TASK 2: EQUITY - Weekdays 22:30 UTC (23:30 CET)
# =====================================================================

Write-Host ""
Write-Host "[EQUITY] Creating weekday equity ingest task..." -ForegroundColor Yellow

$equityAction = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`" --asset-class EQUITY" `
    -WorkingDirectory $WorkingDir

$equityTrigger = New-ScheduledTaskTrigger `
    -Weekly `
    -WeeksInterval 1 `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
    -At "23:30"

try {
    Unregister-ScheduledTask -TaskName "FHQ-IoS001-Bulletproof-EQUITY" -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

$equityTask = Register-ScheduledTask `
    -TaskName "FHQ-IoS001-Bulletproof-EQUITY" `
    -Action $equityAction `
    -Trigger $equityTrigger `
    -Settings $settings `
    -Description "IoS-001 Bulletproof Daily Price Ingest - EQUITY (22:30 UTC weekdays)"

Write-Host "[+] EQUITY task registered" -ForegroundColor Green
Write-Host "    Schedule: Mon-Fri at 23:30 CET (22:30 UTC)" -ForegroundColor Gray

# =====================================================================
# TASK 3: FX - Sun-Thu 22:30 UTC (23:30 CET)
# =====================================================================

Write-Host ""
Write-Host "[FX] Creating FX ingest task..." -ForegroundColor Yellow

$fxAction = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`" --asset-class FX" `
    -WorkingDirectory $WorkingDir

$fxTrigger = New-ScheduledTaskTrigger `
    -Weekly `
    -WeeksInterval 1 `
    -DaysOfWeek Sunday, Monday, Tuesday, Wednesday, Thursday `
    -At "23:30"

try {
    Unregister-ScheduledTask -TaskName "FHQ-IoS001-Bulletproof-FX" -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

$fxTask = Register-ScheduledTask `
    -TaskName "FHQ-IoS001-Bulletproof-FX" `
    -Action $fxAction `
    -Trigger $fxTrigger `
    -Settings $settings `
    -Description "IoS-001 Bulletproof Daily Price Ingest - FX (22:30 UTC Sun-Thu)"

Write-Host "[+] FX task registered" -ForegroundColor Green
Write-Host "    Schedule: Sun-Thu at 23:30 CET (22:30 UTC)" -ForegroundColor Gray

# =====================================================================
# VERIFICATION
# =====================================================================

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "VERIFICATION" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

$tasks = Get-ScheduledTask -TaskName "FHQ-IoS001-Bulletproof-*" -ErrorAction SilentlyContinue

if ($tasks.Count -eq 3) {
    Write-Host "[+] All 3 tasks registered successfully!" -ForegroundColor Green
    Write-Host ""
    foreach ($task in $tasks) {
        $info = Get-ScheduledTaskInfo -TaskName $task.TaskName
        Write-Host "  $($task.TaskName)" -ForegroundColor White
        Write-Host "    State: $($task.State)" -ForegroundColor Gray
        Write-Host "    Next Run: $($info.NextRunTime)" -ForegroundColor Gray
        Write-Host ""
    }
} else {
    Write-Host "[!] Warning: Expected 3 tasks, found $($tasks.Count)" -ForegroundColor Yellow
}

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "SETUP COMPLETE" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "To run immediately:" -ForegroundColor White
Write-Host "  Start-ScheduledTask -TaskName 'FHQ-IoS001-Bulletproof-CRYPTO'" -ForegroundColor Gray
Write-Host ""
Write-Host "To view logs:" -ForegroundColor White
Write-Host "  Get-Content C:\fhq-market-system\vision-ios\03_FUNCTIONS\evidence\*.json -Tail 50" -ForegroundColor Gray
Write-Host ""
