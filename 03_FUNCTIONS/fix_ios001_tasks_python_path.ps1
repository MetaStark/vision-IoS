# =====================================================================
# FIX: Use full Python path for IoS-001 tasks
# =====================================================================
# The scheduled tasks fail with FILE_NOT_FOUND because SYSTEM account
# doesn't have Python in PATH. Fix by using full path to python.exe.
# =====================================================================

$ErrorActionPreference = "Stop"

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "FIXING IoS-001 TASKS - FULL PYTHON PATH" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# Find Python path
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonPath) {
    $PythonPath = "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python312\python.exe"
}

Write-Host "Python path: $PythonPath" -ForegroundColor Green

if (-not (Test-Path $PythonPath)) {
    Write-Error "Python not found at: $PythonPath"
    exit 1
}

$ScriptPath = "C:\fhq-market-system\vision-ios\03_FUNCTIONS\ios001_bulletproof_ingest.py"
$WorkingDir = "C:\fhq-market-system\vision-ios\03_FUNCTIONS"

$tasks = @(
    @{ Name = "FHQ_IOS001_CRYPTO_DAILY"; Class = "CRYPTO" },
    @{ Name = "FHQ_IOS001_EQUITY_DAILY"; Class = "EQUITY" },
    @{ Name = "FHQ_IOS001_FX_DAILY"; Class = "FX" }
)

foreach ($task in $tasks) {
    Write-Host ""
    Write-Host "Fixing: $($task.Name)" -ForegroundColor Yellow

    $newAction = New-ScheduledTaskAction `
        -Execute $PythonPath `
        -Argument "`"$ScriptPath`" --asset-class $($task.Class)" `
        -WorkingDirectory $WorkingDir

    try {
        Set-ScheduledTask -TaskName $task.Name -Action $newAction | Out-Null
        Write-Host "  [OK] Updated with full Python path" -ForegroundColor Green
    }
    catch {
        Write-Host "  [ERROR] $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Testing CRYPTO task now..." -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

Start-ScheduledTask -TaskName "FHQ_IOS001_CRYPTO_DAILY"
Write-Host "Task started. Waiting 10 seconds..." -ForegroundColor Gray
Start-Sleep -Seconds 10

$info = Get-ScheduledTaskInfo -TaskName "FHQ_IOS001_CRYPTO_DAILY"
Write-Host ""
Write-Host "Last Run Time:   $($info.LastRunTime)" -ForegroundColor White
Write-Host "Last Result:     $($info.LastTaskResult)" -ForegroundColor White

if ($info.LastTaskResult -eq 0) {
    Write-Host "Status:          SUCCESS" -ForegroundColor Green
} elseif ($info.LastTaskResult -eq 267009) {
    Write-Host "Status:          RUNNING" -ForegroundColor Yellow
} else {
    Write-Host "Status:          ERROR (code $($info.LastTaskResult))" -ForegroundColor Red
}

Write-Host ""
Write-Host "Check log at:" -ForegroundColor Gray
Write-Host "  $WorkingDir\evidence\bulletproof_ingest_*.log" -ForegroundColor Gray
