# =====================================================================
# UPDATE IoS-001 TASKS TO BULLETPROOF VERSION
# =====================================================================
# This script updates the existing FHQ_IOS001_* scheduled tasks
# to use the new ios001_bulletproof_ingest.py instead of the old
# ios001_daily_ingest.py that gets rate-limited by yfinance.
#
# Run as Administrator:
#   .\update_ios001_tasks_to_bulletproof.ps1
#
# =====================================================================

$ErrorActionPreference = "Stop"

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "UPDATING IoS-001 TASKS TO BULLETPROOF VERSION" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

$ScriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\ios001_bulletproof_ingest.py"
$WorkingDir = "C:\fhq-market-system\vision-ios\03_FUNCTIONS"

# Verify script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Bulletproof script not found: $ScriptPath"
    exit 1
}

Write-Host "[OK] Bulletproof script found: $ScriptPath" -ForegroundColor Green
Write-Host ""

# Tasks to update
$tasks = @(
    @{
        Name = "FHQ_IOS001_CRYPTO_DAILY"
        Args = "`"$ScriptPath`" --asset-class CRYPTO"
        Description = "IoS-001 Bulletproof Daily Price Ingest - CRYPTO"
    },
    @{
        Name = "FHQ_IOS001_EQUITY_DAILY"
        Args = "`"$ScriptPath`" --asset-class EQUITY"
        Description = "IoS-001 Bulletproof Daily Price Ingest - EQUITY"
    },
    @{
        Name = "FHQ_IOS001_FX_DAILY"
        Args = "`"$ScriptPath`" --asset-class FX"
        Description = "IoS-001 Bulletproof Daily Price Ingest - FX"
    }
)

foreach ($task in $tasks) {
    Write-Host "Updating: $($task.Name)" -ForegroundColor Yellow

    # Check if task exists
    $existingTask = Get-ScheduledTask -TaskName $task.Name -ErrorAction SilentlyContinue

    if (-not $existingTask) {
        Write-Host "  [SKIP] Task does not exist" -ForegroundColor Gray
        continue
    }

    # Show old configuration
    $oldAction = $existingTask.Actions[0]
    Write-Host "  OLD: $($oldAction.Execute) $($oldAction.Arguments)" -ForegroundColor Gray

    # Create new action
    $newAction = New-ScheduledTaskAction `
        -Execute "python" `
        -Argument $task.Args `
        -WorkingDirectory $WorkingDir

    # Update the task
    try {
        Set-ScheduledTask -TaskName $task.Name -Action $newAction | Out-Null

        # Update description
        $existingTask = Get-ScheduledTask -TaskName $task.Name
        $existingTask.Description = $task.Description
        $existingTask | Set-ScheduledTask | Out-Null

        Write-Host "  NEW: python $($task.Args)" -ForegroundColor Green
        Write-Host "  [OK] Updated successfully" -ForegroundColor Green
    }
    catch {
        Write-Host "  [ERROR] Failed to update: $_" -ForegroundColor Red
    }

    Write-Host ""
}

# Verification
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "VERIFICATION" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

foreach ($task in $tasks) {
    $updatedTask = Get-ScheduledTask -TaskName $task.Name -ErrorAction SilentlyContinue
    if ($updatedTask) {
        $action = $updatedTask.Actions[0]
        $info = Get-ScheduledTaskInfo -TaskName $task.Name

        Write-Host "$($task.Name):" -ForegroundColor White
        Write-Host "  Command:  $($action.Execute) $($action.Arguments)" -ForegroundColor Gray
        Write-Host "  State:    $($updatedTask.State)" -ForegroundColor Gray
        Write-Host "  Next Run: $($info.NextRunTime)" -ForegroundColor Gray

        # Check if it's using bulletproof
        if ($action.Arguments -like "*bulletproof*") {
            Write-Host "  Status:   BULLETPROOF" -ForegroundColor Green
        } else {
            Write-Host "  Status:   OLD VERSION (not updated)" -ForegroundColor Red
        }
        Write-Host ""
    }
}

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "UPDATE COMPLETE" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "To test manually:" -ForegroundColor White
Write-Host "  python `"$ScriptPath`" --asset-class CRYPTO --dry-run" -ForegroundColor Gray
Write-Host ""
Write-Host "To run a task immediately:" -ForegroundColor White
Write-Host "  Start-ScheduledTask -TaskName 'FHQ_IOS001_CRYPTO_DAILY'" -ForegroundColor Gray
Write-Host ""
