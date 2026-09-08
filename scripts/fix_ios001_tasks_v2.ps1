# Fix IOS001 Price Ingestion Scheduled Tasks - Version 2
# Uses schtasks.exe with /RU SYSTEM to avoid credential issues
# Run as Administrator

$pythonPath = "C:\Users\RJANSK~1\AppData\Local\Programs\Python\PYTHON~2\python.exe"
$workingDir = "C:\fhq-market-system\vision-ios"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "FHQ IOS001 Task Fix Script v2" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Python path: $pythonPath"
Write-Host "Path exists: $(Test-Path $pythonPath)"
Write-Host ""

if (-not (Test-Path $pythonPath)) {
    Write-Host "ERROR: Python path does not exist!" -ForegroundColor Red
    exit 1
}

# Tasks to fix - using schtasks /CHANGE
$tasks = @(
    @{ Name = "FHQ_IOS001_EQUITY_DAILY"; Args = "--asset-class EQUITY"; Script = "ios001_bulletproof_ingest.py" },
    @{ Name = "FHQ_IOS001_CRYPTO_DAILY"; Args = "--asset-class CRYPTO"; Script = "ios001_bulletproof_ingest.py" },
    @{ Name = "FHQ_IOS001_FX_DAILY"; Args = "--asset-class FX"; Script = "ios001_bulletproof_ingest.py" },
    @{ Name = "FHQ-IoS001-Bulletproof-EQUITY"; Args = "--asset-class EQUITY"; Script = "ios001_bulletproof_ingest.py" },
    @{ Name = "FHQ-IoS001-Bulletproof-CRYPTO"; Args = "--asset-class CRYPTO"; Script = "ios001_bulletproof_ingest.py" },
    @{ Name = "FHQ-IoS001-Bulletproof-FX"; Args = "--asset-class FX"; Script = "ios001_bulletproof_ingest.py" }
)

Write-Host "Deleting and recreating tasks with correct paths..." -ForegroundColor Yellow
Write-Host ""

foreach ($task in $tasks) {
    $taskName = $task.Name
    $scriptPath = "$workingDir\03_FUNCTIONS\$($task.Script)"
    $args = "`"$scriptPath`" $($task.Args)"

    Write-Host "Processing: $taskName" -ForegroundColor Cyan

    # Get existing task schedule info
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        $trigger = $existingTask.Triggers | Select-Object -First 1

        # Delete existing task
        Write-Host "  Deleting old task..."
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

        # Create new action with correct path
        $action = New-ScheduledTaskAction -Execute $pythonPath -Argument $args -WorkingDirectory $workingDir

        # Create new task with SYSTEM account (no password needed)
        $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

        # Register new task
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -ErrorAction Stop

        Write-Host "  -> Recreated successfully" -ForegroundColor Green
    } else {
        Write-Host "  -> Task not found, skipping" -ForegroundColor Yellow
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
        $isShortPath = $execute -like "*RJANSK*"

        if ($isShortPath) {
            Write-Host "$($task.Name): OK" -ForegroundColor Green
        } else {
            Write-Host "$($task.Name): STILL WRONG PATH" -ForegroundColor Red
        }
        Write-Host "  Execute: $execute"
    } else {
        Write-Host "$($task.Name): NOT FOUND" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Done." -ForegroundColor Cyan
