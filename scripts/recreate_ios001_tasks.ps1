# Recreate IOS001 Tasks with SYSTEM account
# This bypasses the account lockout by using SYSTEM instead
# Run as Administrator

$pythonPath = "C:\Users\RJANSK~1\AppData\Local\Programs\Python\PYTHON~2\python.exe"
$workingDir = "C:\fhq-market-system\vision-ios"
$scriptPath = "$workingDir\03_FUNCTIONS\ios001_bulletproof_ingest.py"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Recreate IOS001 Tasks with SYSTEM Account" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Define tasks with their schedules
$tasks = @(
    @{
        Name = "FHQ_IOS001_EQUITY_DAILY"
        Args = "--asset-class EQUITY"
        Time = "23:00"
        Description = "IoS-001 Bulletproof Daily Price Ingest - EQUITY"
    },
    @{
        Name = "FHQ_IOS001_CRYPTO_DAILY"
        Args = "--asset-class CRYPTO"
        Time = "23:05"
        Description = "IoS-001 Bulletproof Daily Price Ingest - CRYPTO"
    },
    @{
        Name = "FHQ_IOS001_FX_DAILY"
        Args = "--asset-class FX"
        Time = "23:10"
        Description = "IoS-001 Bulletproof Daily Price Ingest - FX"
    },
    @{
        Name = "FHQ-IoS001-Bulletproof-EQUITY"
        Args = "--asset-class EQUITY"
        Time = "02:00"
        Description = "IoS-001 Bulletproof Ingest - EQUITY (Backup)"
    },
    @{
        Name = "FHQ-IoS001-Bulletproof-CRYPTO"
        Args = "--asset-class CRYPTO"
        Time = "02:05"
        Description = "IoS-001 Bulletproof Ingest - CRYPTO (Backup)"
    },
    @{
        Name = "FHQ-IoS001-Bulletproof-FX"
        Args = "--asset-class FX"
        Time = "02:10"
        Description = "IoS-001 Bulletproof Ingest - FX (Backup)"
    }
)

$successCount = 0

foreach ($task in $tasks) {
    Write-Host "Processing: $($task.Name)" -ForegroundColor Cyan

    # Delete existing task if it exists
    $existing = Get-ScheduledTask -TaskName $task.Name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "  Removing old task..."
        Unregister-ScheduledTask -TaskName $task.Name -Confirm:$false
    }

    # Create action
    $action = New-ScheduledTaskAction `
        -Execute $pythonPath `
        -Argument "`"$scriptPath`" $($task.Args)" `
        -WorkingDirectory $workingDir

    # Create daily trigger at specified time
    $trigger = New-ScheduledTaskTrigger -Daily -At $task.Time

    # Create principal (SYSTEM account - no password needed)
    $principal = New-ScheduledTaskPrincipal `
        -UserId "NT AUTHORITY\SYSTEM" `
        -LogonType ServiceAccount `
        -RunLevel Highest

    # Create settings
    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -DontStopIfGoingOnBatteries `
        -AllowStartIfOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2)

    # Register the task
    try {
        Register-ScheduledTask `
            -TaskName $task.Name `
            -Action $action `
            -Trigger $trigger `
            -Principal $principal `
            -Settings $settings `
            -Description $task.Description `
            -ErrorAction Stop | Out-Null

        Write-Host "  -> Created successfully" -ForegroundColor Green
        $successCount++
    }
    catch {
        Write-Host "  -> Failed: $($_.Exception.Message)" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Verification" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

foreach ($task in $tasks) {
    $t = Get-ScheduledTask -TaskName $task.Name -ErrorAction SilentlyContinue
    if ($t) {
        $execute = $t.Actions.Execute
        $isCorrect = $execute -like "*RJANSK*"

        if ($isCorrect) {
            Write-Host "$($task.Name): OK" -ForegroundColor Green
            Write-Host "  Path: $execute"
            Write-Host "  Schedule: Daily at $($task.Time)"
        } else {
            Write-Host "$($task.Name): WRONG PATH" -ForegroundColor Red
            Write-Host "  Path: $execute"
        }
    } else {
        Write-Host "$($task.Name): NOT CREATED" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Result: $successCount of $($tasks.Count) tasks created" -ForegroundColor $(if ($successCount -eq $tasks.Count) { "Green" } else { "Yellow" })
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Tasks will now run as SYSTEM account (no password required)."
Write-Host "To test immediately, run:" -ForegroundColor Yellow
Write-Host "  schtasks /Run /TN 'FHQ_IOS001_EQUITY_DAILY'"
