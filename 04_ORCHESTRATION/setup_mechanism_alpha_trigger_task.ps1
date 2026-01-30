# =====================================================================
# FHQ_MECHANISM_ALPHA_TRIGGER - WINDOWS TASK SCHEDULER SETUP
# =====================================================================
# Pipeline step 3: Scans indicators for hypothesis trigger conditions.
# Runs every 15 minutes with --once (single cycle).
#
# Usage: .\setup_mechanism_alpha_trigger_task.ps1
# =====================================================================

$ErrorActionPreference = "Stop"

$TaskName    = "FHQ_MECHANISM_ALPHA_TRIGGER"
$ScriptPath  = "C:\fhq-market-system\vision-ios\04_ORCHESTRATION\run_mechanism_alpha_trigger.ps1"
$WorkingDir  = "C:\fhq-market-system\vision-ios"
$Description = "Pipeline step 3: Alpha trigger scanner - scans indicator data for hypothesis triggers. Every 15 min at :02."

$PwshPath = (Get-Command powershell).Source

Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "FHQ_MECHANISM_ALPHA_TRIGGER - TASK SCHEDULER SETUP" -ForegroundColor Cyan
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $ScriptPath)) { Write-Error "Script not found: $ScriptPath"; exit 1 }
Write-Host "[+] Script verified: $ScriptPath" -ForegroundColor Green

$Action = New-ScheduledTaskAction -Execute $PwshPath `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory $WorkingDir

$Trigger = New-ScheduledTaskTrigger -Once `
    -At (Get-Date).Date.AddHours(6).AddMinutes(2) `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 365)

$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)

try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description $Description | Out-Null

Write-Host "[+] Task registered: $TaskName" -ForegroundColor Green
Write-Host "    Schedule: Every 15 minutes (starting 06:02)" -ForegroundColor Gray

$registeredTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($registeredTask) {
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "  State: $($registeredTask.State)" -ForegroundColor White
    Write-Host "  Next Run: $($info.NextRunTime)" -ForegroundColor White
} else { Write-Host "[!] Task not found after registration" -ForegroundColor Red; exit 1 }
Write-Host ""
