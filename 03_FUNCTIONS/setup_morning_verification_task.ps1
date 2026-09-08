# =====================================================================
# PHASE 2 MORNING VERIFICATION - WINDOWS TASK SCHEDULER SETUP
# =====================================================================
# CEO Directive: Phase 2 Morgenrapport
# Date: 2026-01-29
#
# Creates a daily scheduled task that runs phase2_morning_verification.py
# at 08:30 CET and sends a Norwegian status report to CEO via Telegram.
#
# Usage:
#   .\setup_morning_verification_task.ps1
#
# Task Created:
#   FHQ-Phase2-Morning-Verification - Daily 08:30 CET (07:30 UTC)
#
# =====================================================================

$ErrorActionPreference = "Stop"

# Configuration
$PythonPath = (Get-Command python).Source
$ScriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\phase2_morning_verification.py"
$WorkingDir = "C:\fhq-market-system\vision-ios"
$TaskName = "FHQ-Phase2-Morning-Verification"

Write-Host "Python path: $PythonPath" -ForegroundColor Gray

# Verify script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath"
    exit 1
}

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "PHASE 2 MORNING VERIFICATION - TASK SCHEDULER SETUP" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "Running as: $env:USERNAME" -ForegroundColor Gray
Write-Host ""

# Task action
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $WorkingDir

# Daily at 08:30 CET
$Trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At "08:30"

# Settings (matches bulletproof ingest pattern)
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

# Remove existing task if present
Write-Host "[MORNING] Registering daily morning verification task..." -ForegroundColor Yellow
try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

# Register task
$Task = Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Phase 2 Morning Verification - Norsk morgenrapport til CEO via Telegram (08:30 CET daglig)"

Write-Host "[+] Morning verification task registered" -ForegroundColor Green
Write-Host "    Schedule: Daily at 08:30 CET (07:30 UTC)" -ForegroundColor Gray
Write-Host "    Timeout: 10 minutes" -ForegroundColor Gray
Write-Host "    WakeToRun: Enabled" -ForegroundColor Gray

# =====================================================================
# VERIFICATION
# =====================================================================

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "VERIFICATION" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

$registeredTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($registeredTask) {
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "[+] Task registered successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  $($registeredTask.TaskName)" -ForegroundColor White
    Write-Host "    State: $($registeredTask.State)" -ForegroundColor Gray
    Write-Host "    Next Run: $($info.NextRunTime)" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "[!] Warning: Task not found after registration" -ForegroundColor Yellow
}

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "SETUP COMPLETE" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "To run immediately:" -ForegroundColor White
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
Write-Host ""
Write-Host "To test without Telegram:" -ForegroundColor White
Write-Host "  python `"$ScriptPath`" --check" -ForegroundColor Gray
Write-Host ""
Write-Host "To view task status:" -ForegroundColor White
Write-Host "  Get-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
Write-Host ""
