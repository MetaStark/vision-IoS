# =====================================================================
# FHQ_CAPITAL_SIMULATION_WRITER - WINDOWS TASK SCHEDULER SETUP
# =====================================================================
# CEO-DIR-20260130-PIPELINE-COMPLETION-002 D3
#
# Creates a scheduled task that runs capital_simulation_writer every 60 minutes.
# Pipeline step 6: creates capital simulations from decision packs.
#
# Usage:
#   .\setup_capital_simulation_writer_task.ps1
# =====================================================================

$ErrorActionPreference = "Stop"

$TaskName    = "FHQ_CAPITAL_SIMULATION_WRITER"
$ScriptPath  = "C:\fhq-market-system\vision-ios\04_ORCHESTRATION\run_capital_simulation_writer.ps1"
$WorkingDir  = "C:\fhq-market-system\vision-ios"
$Description = "Pipeline step 6: Capital simulation writer - creates simulations from decision packs linked to shadow tier entries. Every 60 min at :25."

# Find PowerShell
$PwshPath = (Get-Command powershell).Source

Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "FHQ_CAPITAL_SIMULATION_WRITER - TASK SCHEDULER SETUP" -ForegroundColor Cyan
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

# Trigger: every 60 minutes, offset at :25
$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date.AddHours(6).AddMinutes(25) `
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
Write-Host "[SIM] Registering capital simulation writer task..." -ForegroundColor Yellow
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
Write-Host "    Schedule: Every 60 minutes (starting 06:25)" -ForegroundColor Gray
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
