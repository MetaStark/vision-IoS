# Fix FHQ Scheduled Tasks - Change to run whether user is logged on or not
# Authority: CEO-DIR-2025-INFRA-001

$tasks = @(
    "FHQ-IoS001-Bulletproof-CRYPTO",
    "FHQ-IoS001-Bulletproof-EQUITY",
    "FHQ-IoS001-Bulletproof-FX",
    "FHQ_IOS001_CRYPTO_DAILY",
    "FHQ_IOS001_EQUITY_DAILY",
    "FHQ_IOS001_FX_DAILY",
    "FHQ_IOS003_REGIME_DAILY_V4",
    "FHQ_HMM_Daily_Inference"
)

Write-Host "=============================================="
Write-Host "FHQ SCHEDULED TASK FIX"
Write-Host "=============================================="
Write-Host ""

foreach ($taskName in $tasks) {
    Write-Host "Processing: $taskName"

    try {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
        $principal = $task.Principal

        Write-Host "  Current LogonType: $($principal.LogonType)"

        if ($principal.LogonType -eq "InteractiveToken") {
            Write-Host "  Status: NEEDS FIX (Interactive only)"

            # Change to run whether logged on or not
            # This requires the task to be re-registered with Password or S4U
            $principal.LogonType = "S4U"  # Service for User - doesn't require stored password

            Set-ScheduledTask -TaskName $taskName -Principal $principal -ErrorAction Stop
            Write-Host "  Result: FIXED (changed to S4U)"
        } else {
            Write-Host "  Status: OK (already $($principal.LogonType))"
        }
    } catch {
        Write-Host "  ERROR: $($_.Exception.Message)"
    }
    Write-Host ""
}

Write-Host "=============================================="
Write-Host "VERIFICATION"
Write-Host "=============================================="

foreach ($taskName in $tasks) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "$taskName : $($task.Principal.LogonType)"
    }
}
