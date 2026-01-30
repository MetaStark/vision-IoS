# =====================================================================
# FHQ_INDICATOR_PULSE - WINDOWS TASK SCHEDULER SETUP
# =====================================================================
# CEO-DIR-20260130-OPS-INDICATOR-PULSE-001
# Deliverable D1: Production Scheduler
#
# Creates a daily scheduled task that computes indicators at 06:00 CET.
# Runs BEFORE morning verification (08:30 CET) and AFTER price ingest.
#
# Usage:
#   .\setup_indicator_pulse_task.ps1
# =====================================================================

$ErrorActionPreference = "Stop"

$TaskName    = "FHQ_INDICATOR_PULSE"
$ScriptPath  = "C:\fhq-market-system\vision-ios\04_ORCHESTRATION\run_indicator_pulse.ps1"
$WorkingDir  = "C:\fhq-market-system\vision-ios"
$Description = "CEO-DIR-20260130: Daily indicator computation (momentum + volatility). Runs at 06:00 CET before morning verification."

# Find PowerShell
$PwshPath = (Get-Command powershell).Source

Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "FHQ_INDICATOR_PULSE - TASK SCHEDULER SETUP" -ForegroundColor Cyan
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host ""

# Verify script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath"
    exit 1
}
Write-Host "[+] Script verified: $ScriptPath" -ForegroundColor Green

# Task action: run PowerShell wrapper (not Python directly)
$Action = New-ScheduledTaskAction `
    -Execute $PwshPath `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory $WorkingDir

# Daily at 06:00 CET (05:00 UTC)
$Trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At "06:00"

# Settings: resilient production task
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

# Remove existing task if present
Write-Host "[PULSE] Registering daily indicator computation task..." -ForegroundColor Yellow
try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

# Register
$Task = Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description $Description

Write-Host "[+] Task registered: $TaskName" -ForegroundColor Green
Write-Host "    Schedule: Daily at 06:00 CET (05:00 UTC)" -ForegroundColor Gray
Write-Host "    Timeout: 15 minutes" -ForegroundColor Gray
Write-Host "    Retries: 3x every 5 minutes" -ForegroundColor Gray
Write-Host "    WakeToRun: Enabled" -ForegroundColor Gray
Write-Host ""

# Verification
$registeredTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($registeredTask) {
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host "VERIFICATION" -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host "  Task: $($registeredTask.TaskName)" -ForegroundColor White
    Write-Host "  State: $($registeredTask.State)" -ForegroundColor White
    Write-Host "  Next Run: $($info.NextRunTime)" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "[!] Task not found after registration" -ForegroundColor Red
    exit 1
}

Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "SETUP COMPLETE" -ForegroundColor Cyan
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host ""
Write-Host "To run immediately:" -ForegroundColor White
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
Write-Host ""
Write-Host "To check status:" -ForegroundColor White
Write-Host "  Get-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
Write-Host ""
