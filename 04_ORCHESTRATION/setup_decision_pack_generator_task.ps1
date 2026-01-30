# =====================================================================
# FHQ_DECISION_PACK_GENERATOR - WINDOWS TASK SCHEDULER SETUP
# =====================================================================
# CEO-DIR-20260130-PIPELINE-COMPLETION-002 D2
#
# Creates a scheduled task that runs decision_pack_generator every 60 minutes.
# Pipeline step 5.2: generates decision packs from promoted hypotheses
# with CLOSED shadow trades.
#
# Usage:
#   .\setup_decision_pack_generator_task.ps1
# =====================================================================

$ErrorActionPreference = "Stop"

$TaskName    = "FHQ_DECISION_PACK_GENERATOR"
$ScriptPath  = "C:\fhq-market-system\vision-ios\04_ORCHESTRATION\run_decision_pack_generator.ps1"
$WorkingDir  = "C:\fhq-market-system\vision-ios"
$Description = "Pipeline step 5.2: Decision pack generator - creates signed packs from promoted hypotheses with CLOSED shadow trades. Every 60 min at :20."

# Find PowerShell
$PwshPath = (Get-Command powershell).Source

Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "FHQ_DECISION_PACK_GENERATOR - TASK SCHEDULER SETUP" -ForegroundColor Cyan
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host ""

# Verify script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath"
    exit 1
}
Write-Host "[+] Script verified: $ScriptPath" -ForegroundColor Green

# Task action
$Action = New-ScheduledTaskAction `
    -Execute $PwshPath `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory $WorkingDir

# Trigger: every 60 minutes, offset at :20
$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date.AddHours(6).AddMinutes(20) `
    -RepetitionInterval (New-TimeSpan -Minutes 60) `
    -RepetitionDuration (New-TimeSpan -Days 365)

# Settings
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

# Remove existing task if present
Write-Host "[PACK] Registering decision pack generator task..." -ForegroundColor Yellow
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
Write-Host "    Schedule: Every 60 minutes (starting 06:20)" -ForegroundColor Gray
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
