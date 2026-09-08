# =====================================================================
# FHQ_PROMOTION_GATE_PULSE - WINDOWS TASK SCHEDULER SETUP
# =====================================================================
# CEO-DIR-20260130-PIPELINE-UNBLOCK-001 D1
#
# Creates a scheduled task that evaluates promotion gate every 60 minutes.
# Pipeline step 4: after outcome_ledger, before shadow_tier.
#
# Usage:
#   .\setup_promotion_gate_task.ps1
# =====================================================================

$ErrorActionPreference = "Stop"

$TaskName    = "FHQ_PROMOTION_GATE_PULSE"
$ScriptPath  = "C:\fhq-market-system\vision-ios\04_ORCHESTRATION\run_promotion_gate_pulse.ps1"
$WorkingDir  = "C:\fhq-market-system\vision-ios"
$Description = "CEO-DIR-20260130-PIPELINE-UNBLOCK-001 D1: Promotion gate evaluation every 60 min. Step 4 of capital pipeline."

# Find PowerShell
$PwshPath = (Get-Command powershell).Source

Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "FHQ_PROMOTION_GATE_PULSE - TASK SCHEDULER SETUP" -ForegroundColor Cyan
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host ""

# Verify script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath"
    exit 1
}
Write-Host "[+] Script verified: $ScriptPath" -ForegroundColor Green

# Task action: run PowerShell wrapper
$Action = New-ScheduledTaskAction `
    -Execute $PwshPath `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory $WorkingDir

# Trigger: once at startup, then repeat every 60 minutes indefinitely
$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date.AddHours(6) `
    -RepetitionInterval (New-TimeSpan -Minutes 60) `
    -RepetitionDuration (New-TimeSpan -Days 365)

# Settings: resilient production task
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

# Remove existing task if present
Write-Host "[GATE] Registering promotion gate evaluation task..." -ForegroundColor Yellow
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
Write-Host "    Schedule: Every 60 minutes (starting 06:00)" -ForegroundColor Gray
Write-Host "    Timeout: 5 minutes" -ForegroundColor Gray
Write-Host "    Retries: 3x every 5 minutes" -ForegroundColor Gray
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
