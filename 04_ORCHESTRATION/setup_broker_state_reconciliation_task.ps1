# =====================================================================
# FHQ_BROKER_STATE_RECONCILIATION - WINDOWS TASK SCHEDULER SETUP
# =====================================================================
# CEO-DIR-2026-DBV-003: Syncs database with Alpaca broker state.
# Runs every 5 minutes with --once (single cycle).
#
# Usage: .\setup_broker_state_reconciliation_task.ps1
# =====================================================================

$ErrorActionPreference = "Stop"

$TaskName    = "FHQ_BROKER_STATE_RECONCILIATION"
$ScriptPath  = "C:\fhq-market-system\vision-ios\04_ORCHESTRATION\run_broker_state_reconciliation.ps1"
$WorkingDir  = "C:\fhq-market-system\vision-ios"
$Description = "Broker state reconciliation - syncs database with Alpaca broker reality. Every 5 min at :30."

$PwshPath = (Get-Command powershell).Source

Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "FHQ_BROKER_STATE_RECONCILIATION - TASK SCHEDULER SETUP" -ForegroundColor Cyan
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $ScriptPath)) { Write-Error "Script not found: $ScriptPath"; exit 1 }
Write-Host "[+] Script verified: $ScriptPath" -ForegroundColor Green

$Action = New-ScheduledTaskAction -Execute $PwshPath `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory $WorkingDir

$Trigger = New-ScheduledTaskTrigger -Once `
    -At (Get-Date).Date.AddHours(6).AddMinutes(30) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 365)

$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 3) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 2)

try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description $Description | Out-Null

Write-Host "[+] Task registered: $TaskName" -ForegroundColor Green
Write-Host "    Schedule: Every 5 minutes (starting 06:30)" -ForegroundColor Gray

$registeredTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($registeredTask) {
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "  State: $($registeredTask.State)" -ForegroundColor White
    Write-Host "  Next Run: $($info.NextRunTime)" -ForegroundColor White
} else { Write-Host "[!] Task not found after registration" -ForegroundColor Red; exit 1 }
Write-Host ""
