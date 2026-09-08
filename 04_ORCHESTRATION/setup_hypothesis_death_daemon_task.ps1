# =====================================================================
# FHQ_HYPOTHESIS_DEATH_DAEMON - WINDOWS TASK SCHEDULER SETUP
# =====================================================================
# Continuous daemon: falsifies hypotheses past expected_timeframe_hours.
# Task Scheduler starts the daemon; daemon runs until exit/crash.
# Daily trigger at 06:00 + IgnoreNew = auto-restart if crashed.
#
# Usage: .\setup_hypothesis_death_daemon_task.ps1
# =====================================================================

$ErrorActionPreference = "Stop"

$TaskName    = "FHQ_HYPOTHESIS_DEATH_DAEMON"
$ScriptPath  = "C:\fhq-market-system\vision-ios\04_ORCHESTRATION\run_hypothesis_death_daemon.ps1"
$WorkingDir  = "C:\fhq-market-system\vision-ios"
$Description = "Continuous daemon: falsifies hypotheses past expected_timeframe_hours. 15-min internal cycle."

$PwshPath = (Get-Command powershell).Source

Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "FHQ_HYPOTHESIS_DEATH_DAEMON - TASK SCHEDULER SETUP" -ForegroundColor Cyan
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $ScriptPath)) { Write-Error "Script not found: $ScriptPath"; exit 1 }
Write-Host "[+] Script verified: $ScriptPath" -ForegroundColor Green

$Action = New-ScheduledTaskAction -Execute $PwshPath `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory $WorkingDir

$Trigger = New-ScheduledTaskTrigger -Daily -At "06:00"

$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Days 365) `
    -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew

try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description $Description | Out-Null

Write-Host "[+] Task registered: $TaskName" -ForegroundColor Green
Write-Host "    Mode: CONTINUOUS DAEMON (daily trigger at 06:00, IgnoreNew)" -ForegroundColor Gray
Write-Host "    Internal cycle: 15 minutes" -ForegroundColor Gray
Write-Host "    Restart on failure: 10x every 1 min" -ForegroundColor Gray

$registeredTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($registeredTask) {
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "  State: $($registeredTask.State)" -ForegroundColor White
    Write-Host "  Next Run: $($info.NextRunTime)" -ForegroundColor White
} else { Write-Host "[!] Task not found after registration" -ForegroundColor Red; exit 1 }
Write-Host ""
