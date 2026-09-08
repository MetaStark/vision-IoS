# Fix IOS001 Price Ingestion Scheduled Tasks - Run as Administrator
# Uses short path to avoid Unicode encoding issues
# Created: 2026-01-15 - Same fix as applied to LDOW tasks

$pythonPath = "C:\Users\RJANSK~1\AppData\Local\Programs\Python\PYTHON~2\python.exe"
$workingDir = "C:\fhq-market-system\vision-ios"

Write-Host "============================================"
Write-Host "FHQ IOS001 Price Ingestion Task Fix Script"
Write-Host "============================================"
Write-Host ""
Write-Host "Using Python path: $pythonPath"
Write-Host "Verifying path exists: $(Test-Path $pythonPath)"
Write-Host ""

if (-not (Test-Path $pythonPath)) {
    Write-Host "ERROR: Python path does not exist!" -ForegroundColor Red
    exit 1
}

# Define all IOS001 tasks and their scripts
$tasks = @(
    @{
        Name = "FHQ_IOS001_EQUITY_DAILY"
        Script = "03_FUNCTIONS\ios001_bulletproof_ingest.py"
        Args = "--asset-class EQUITY"
    },
    @{
        Name = "FHQ_IOS001_CRYPTO_DAILY"
        Script = "03_FUNCTIONS\ios001_bulletproof_ingest.py"
        Args = "--asset-class CRYPTO"
    },
    @{
        Name = "FHQ_IOS001_FX_DAILY"
        Script = "03_FUNCTIONS\ios001_bulletproof_ingest.py"
        Args = "--asset-class FX"
    },
    @{
        Name = "FHQ-IoS001-Bulletproof-EQUITY"
        Script = "03_FUNCTIONS\ios001_bulletproof_ingest.py"
        Args = "--asset-class EQUITY"
    },
    @{
        Name = "FHQ-IoS001-Bulletproof-CRYPTO"
        Script = "03_FUNCTIONS\ios001_bulletproof_ingest.py"
        Args = "--asset-class CRYPTO"
    },
    @{
        Name = "FHQ-IoS001-Bulletproof-FX"
        Script = "03_FUNCTIONS\ios001_bulletproof_ingest.py"
        Args = "--asset-class FX"
    },
    @{
        Name = "ios001_daily_ingest_equity"
        Script = "03_FUNCTIONS\ios001_daily_ingest.py"
        Args = "--asset-class EQUITY"
    },
    @{
        Name = "ios001_daily_ingest_crypto"
        Script = "03_FUNCTIONS\ios001_daily_ingest.py"
        Args = "--asset-class CRYPTO"
    },
    @{
        Name = "ios001_daily_ingest_fx"
        Script = "03_FUNCTIONS\ios001_daily_ingest.py"
        Args = "--asset-class FX"
    }
)

$fixedCount = 0
$errorCount = 0

foreach ($task in $tasks) {
    Write-Host "Fixing $($task.Name)..." -ForegroundColor Cyan

    try {
        $existingTask = Get-ScheduledTask -TaskName $task.Name -ErrorAction Stop

        $scriptPath = Join-Path $workingDir $task.Script
        $argument = "`"$scriptPath`" $($task.Args)"

        $action = New-ScheduledTaskAction -Execute $pythonPath -Argument $argument -WorkingDirectory $workingDir
        Set-ScheduledTask -TaskName $task.Name -Action $action

        Write-Host "  -> Updated successfully" -ForegroundColor Green
        $fixedCount++
    }
    catch {
        Write-Host "  -> ERROR: $($_.Exception.Message)" -ForegroundColor Red
        $errorCount++
    }
}

Write-Host ""
Write-Host "============================================"
Write-Host "Verification"
Write-Host "============================================"
Write-Host ""

foreach ($task in $tasks) {
    try {
        $t = Get-ScheduledTask -TaskName $task.Name -ErrorAction Stop
        $execute = $t.Actions.Execute
        $pathExists = Test-Path $execute

        if ($pathExists) {
            Write-Host "$($task.Name):" -ForegroundColor Green
        } else {
            Write-Host "$($task.Name):" -ForegroundColor Red
        }
        Write-Host "  Execute: $execute"
        Write-Host "  Path exists: $pathExists"
    }
    catch {
        Write-Host "$($task.Name): NOT FOUND" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "============================================"
Write-Host "Summary"
Write-Host "============================================"
Write-Host "Tasks fixed: $fixedCount" -ForegroundColor Green
Write-Host "Errors: $errorCount" -ForegroundColor $(if ($errorCount -eq 0) { "Green" } else { "Red" })
Write-Host ""
