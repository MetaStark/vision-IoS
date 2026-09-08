# =============================================================================
# LDOW CYCLE COMPLETION TASKS - WINDOWS TASK SCHEDULER SETUP
# =============================================================================
# CEO Directive: 2026-01-14 - Evidence-Based Cycle Completion
# ADR-024 Compliance: Formal cycle completion for Rung D eligibility
#
# Creates Windows Scheduled Tasks for:
#   - Cycle 1 Completion: 2026-01-15 01:30 UTC (evidence-based)
#   - Cycle 2 Completion: 2026-01-16 01:30 UTC (evidence-based)
#
# Evidence-Based Completion includes:
#   - Coverage threshold check (80% minimum forecasts paired)
#   - Stability threshold check (5% max Brier variance)
#   - Damper immutability verification
#   - Full evidence logging per CEO requirements
#
# Run as Administrator: .\setup_ldow_cycle_tasks.ps1
# =============================================================================

param(
    [switch]$Uninstall,
    [switch]$Status
)

$ErrorActionPreference = "Stop"

# Configuration
$ProjectRoot = "C:\fhq-market-system\vision-ios"
$PythonExe = "python"
$CycleCompletionScript = Join-Path $ProjectRoot "03_FUNCTIONS\ldow_cycle_completion_daemon.py"

# Task definitions (times in LOCAL timezone - Oslo/CET = UTC+1)
$Tasks = @(
    @{
        Name = "FHQ_LDOW_Cycle1_Completion"
        Description = "LDOW Cycle 1 - Evidence-Based Completion (ADR-024 Rung D)"
        Script = $CycleCompletionScript
        Arguments = "--cycle 1"
        # 01:30 UTC = 02:30 CET
        TriggerTime = [DateTime]"2026-01-15 02:30:00"
    },
    @{
        Name = "FHQ_LDOW_Cycle2_Completion"
        Description = "LDOW Cycle 2 - Evidence-Based Completion (ADR-024 Rung D)"
        Script = $CycleCompletionScript
        Arguments = "--cycle 2"
        # 01:30 UTC = 02:30 CET
        TriggerTime = [DateTime]"2026-01-16 02:30:00"
    }
)

function Show-Status {
    Write-Host ""
    Write-Host "===== LDOW CYCLE TASKS STATUS =====" -ForegroundColor Cyan

    foreach ($taskDef in $Tasks) {
        $task = Get-ScheduledTask -TaskName $taskDef.Name -ErrorAction SilentlyContinue
        if ($task) {
            $info = Get-ScheduledTaskInfo -TaskName $taskDef.Name
            $stateColor = if ($task.State -eq "Ready") { "Green" } elseif ($task.State -eq "Running") { "Yellow" } else { "Gray" }
            Write-Host ""
            Write-Host "Task: $($taskDef.Name)" -ForegroundColor White
            Write-Host "  State:     $($task.State)" -ForegroundColor $stateColor
            Write-Host "  Next Run:  $($info.NextRunTime)"
            Write-Host "  Last Run:  $($info.LastRunTime)"
        } else {
            Write-Host ""
            Write-Host "Task: $($taskDef.Name)" -ForegroundColor White
            Write-Host "  Status: NOT INSTALLED" -ForegroundColor Red
        }
    }

    Write-Host ""
    Write-Host "====================================" -ForegroundColor Cyan
    Write-Host ""
}

function Uninstall-Tasks {
    foreach ($taskDef in $Tasks) {
        $task = Get-ScheduledTask -TaskName $taskDef.Name -ErrorAction SilentlyContinue
        if ($task) {
            Write-Host "Removing task: $($taskDef.Name)..." -ForegroundColor Yellow
            Unregister-ScheduledTask -TaskName $taskDef.Name -Confirm:$false
            Write-Host "  Removed." -ForegroundColor Green
        } else {
            Write-Host "Task not found: $($taskDef.Name)" -ForegroundColor Gray
        }
    }
}

function Install-Tasks {
    # Verify cycle completion script exists
    if (-not (Test-Path $CycleCompletionScript)) {
        Write-Host "ERROR: Cycle completion script not found: $CycleCompletionScript" -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "===== INSTALLING LDOW CYCLE TASKS =====" -ForegroundColor Cyan
    Write-Host "CEO Directive 2026-01-14: Evidence-Based Cycle Completion" -ForegroundColor Gray
    Write-Host "ADR-024 Compliance: Rung D eligibility" -ForegroundColor Gray
    Write-Host ""

    foreach ($taskDef in $Tasks) {
        # Check if already exists
        $existing = Get-ScheduledTask -TaskName $taskDef.Name -ErrorAction SilentlyContinue
        if ($existing) {
            Write-Host "Task already exists: $($taskDef.Name)" -ForegroundColor Yellow
            continue
        }

        Write-Host "Creating task: $($taskDef.Name)" -ForegroundColor White
        Write-Host "  Scheduled: $($taskDef.TriggerTime) (local time)" -ForegroundColor Gray
        Write-Host "  Arguments: $($taskDef.Arguments)" -ForegroundColor Gray

        # Create action with script arguments
        $Action = New-ScheduledTaskAction `
            -Execute $PythonExe `
            -Argument "`"$($taskDef.Script)`" $($taskDef.Arguments)" `
            -WorkingDirectory $ProjectRoot

        # Create trigger (one-time at specified time)
        $Trigger = New-ScheduledTaskTrigger -Once -At $taskDef.TriggerTime

        # Settings
        $Settings = New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -StartWhenAvailable `
            -ExecutionTimeLimit (New-TimeSpan -Hours 1)

        # Principal
        $Principal = New-ScheduledTaskPrincipal `
            -UserId $env:USERNAME `
            -LogonType S4U `
            -RunLevel Highest

        try {
            Register-ScheduledTask `
                -TaskName $taskDef.Name `
                -Description $taskDef.Description `
                -Action $Action `
                -Trigger $Trigger `
                -Settings $Settings `
                -Principal $Principal `
                -Force | Out-Null

            Write-Host "  Installed successfully." -ForegroundColor Green
        } catch {
            Write-Host "  ERROR: $_" -ForegroundColor Red
        }
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""

    Show-Status
}

# Main
if ($Status) {
    Show-Status
} elseif ($Uninstall) {
    Uninstall-Tasks
} else {
    Install-Tasks
}
