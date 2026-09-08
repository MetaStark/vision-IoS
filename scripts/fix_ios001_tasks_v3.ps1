# Fix IOS001 Price Ingestion Scheduled Tasks - Version 3
# Prompts for password once, then updates all tasks
# Run as Administrator

$pythonPath = "C:\Users\RJANSK~1\AppData\Local\Programs\Python\PYTHON~2\python.exe"
$workingDir = "C:\fhq-market-system\vision-ios"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "FHQ IOS001 Task Fix Script v3" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Python path: $pythonPath"
Write-Host "Path exists: $(Test-Path $pythonPath)"
Write-Host ""

if (-not (Test-Path $pythonPath)) {
    Write-Host "ERROR: Python path does not exist!" -ForegroundColor Red
    exit 1
}

# Get current username
$username = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
Write-Host "Tasks will run as: $username" -ForegroundColor Yellow
Write-Host ""

# Prompt for password
$credential = Get-Credential -UserName $username -Message "Enter your Windows password to update scheduled tasks"
if (-not $credential) {
    Write-Host "Cancelled - no password provided" -ForegroundColor Red
    exit 1
}
$password = $credential.GetNetworkCredential().Password

# Tasks to fix
$tasks = @(
    @{ Name = "FHQ_IOS001_EQUITY_DAILY"; Args = "--asset-class EQUITY"; Script = "ios001_bulletproof_ingest.py" },
    @{ Name = "FHQ_IOS001_CRYPTO_DAILY"; Args = "--asset-class CRYPTO"; Script = "ios001_bulletproof_ingest.py" },
    @{ Name = "FHQ_IOS001_FX_DAILY"; Args = "--asset-class FX"; Script = "ios001_bulletproof_ingest.py" },
    @{ Name = "FHQ-IoS001-Bulletproof-EQUITY"; Args = "--asset-class EQUITY"; Script = "ios001_bulletproof_ingest.py" },
    @{ Name = "FHQ-IoS001-Bulletproof-CRYPTO"; Args = "--asset-class CRYPTO"; Script = "ios001_bulletproof_ingest.py" },
    @{ Name = "FHQ-IoS001-Bulletproof-FX"; Args = "--asset-class FX"; Script = "ios001_bulletproof_ingest.py" }
)

$successCount = 0
$failCount = 0

foreach ($task in $tasks) {
    $taskName = $task.Name
    $scriptPath = "$workingDir\03_FUNCTIONS\$($task.Script)"
    $fullArgs = "`"$scriptPath`" $($task.Args)"

    Write-Host "Updating: $taskName" -ForegroundColor Cyan

    # Use schtasks.exe with /TR to change the task run command
    $taskRun = "$pythonPath $fullArgs"

    $result = schtasks /Change /TN $taskName /TR $taskRun /RU $username /RP $password 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  -> Success" -ForegroundColor Green
        $successCount++
    } else {
        Write-Host "  -> Failed: $result" -ForegroundColor Red
        $failCount++
    }
}

Write-Host ""
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
            Write-Host "$($task.Name): OK (short path)" -ForegroundColor Green
        } else {
            Write-Host "$($task.Name): WRONG PATH" -ForegroundColor Red
        }
        Write-Host "  Execute: $execute"
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Summary: $successCount succeeded, $failCount failed" -ForegroundColor $(if ($failCount -eq 0) { "Green" } else { "Yellow" })
Write-Host "============================================" -ForegroundColor Cyan
