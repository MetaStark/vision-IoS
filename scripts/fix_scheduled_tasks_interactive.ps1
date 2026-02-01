# CEO-DIR-2025-DATA-001 Section C: Scheduler Hardening
# Run this script as Administrator to fix scheduled tasks
#
# This script changes FHQ tasks from "Run only when user is logged on"
# to "Run whether user is logged on or not"
#
# Usage: Run PowerShell as Administrator, then:
#   .\fix_scheduled_tasks_interactive.ps1

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "CEO-DIR-2025-DATA-001 SCHEDULER HARDENING" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# Get current user
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
Write-Host "Current User: $currentUser" -ForegroundColor Yellow
Write-Host ""

# List of critical tasks to update
$criticalTasks = @(
    "FHQ-IoS001-Bulletproof-CRYPTO",
    "FHQ-IoS001-Bulletproof-EQUITY",
    "FHQ-IoS001-Bulletproof-FX",
    "FHQ_IOS001_CRYPTO_DAILY",
    "FHQ_IOS001_EQUITY_DAILY",
    "FHQ_IOS001_FX_DAILY",
    "FHQ_IOS003_REGIME_DAILY_V4",
    "FHQ_HMM_Daily_Inference",
    "FHQ_WAVE17C_Promotion_Daemon"
)

Write-Host "Tasks to update:" -ForegroundColor White
foreach ($task in $criticalTasks) {
    Write-Host "  - $task" -ForegroundColor Gray
}
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Red
    exit 1
}

Write-Host "Running as Administrator: YES" -ForegroundColor Green
Write-Host ""

# Prompt for password
Write-Host "To run tasks without login, Windows requires your password." -ForegroundColor Yellow
Write-Host "This password is stored securely by Windows Task Scheduler." -ForegroundColor Yellow
Write-Host ""
$securePassword = Read-Host -AsSecureString "Enter password for $currentUser"

# Convert to plain text for schtasks
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
$password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)

Write-Host ""
Write-Host "Updating tasks..." -ForegroundColor Cyan
Write-Host ""

$successCount = 0
$failCount = 0

foreach ($taskName in $criticalTasks) {
    try {
        # Check if task exists
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if (-not $task) {
            Write-Host "  SKIP: $taskName (not found)" -ForegroundColor Yellow
            continue
        }

        # Get the task's action (command to run)
        $action = $task.Actions[0]
        $trigger = $task.Triggers[0]

        # Update using schtasks with /RU and /RP to set "run whether logged on or not"
        $result = schtasks /change /tn $taskName /ru $currentUser /rp $password 2>&1

        if ($LASTEXITCODE -eq 0) {
            Write-Host "  OK: $taskName" -ForegroundColor Green
            $successCount++
        } else {
            Write-Host "  FAIL: $taskName - $result" -ForegroundColor Red
            $failCount++
        }
    }
    catch {
        Write-Host "  ERROR: $taskName - $_" -ForegroundColor Red
        $failCount++
    }
}

# Clear password from memory
$password = $null
[GC]::Collect()

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "SUMMARY" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "  Success: $successCount" -ForegroundColor Green
Write-Host "  Failed:  $failCount" -ForegroundColor $(if ($failCount -gt 0) { "Red" } else { "Green" })
Write-Host ""

if ($failCount -eq 0) {
    Write-Host "All tasks updated successfully!" -ForegroundColor Green
    Write-Host "Tasks will now run even when you are not logged in." -ForegroundColor Green
} else {
    Write-Host "Some tasks failed to update. Check errors above." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Verifying task configuration..." -ForegroundColor Cyan
Write-Host ""

foreach ($taskName in $criticalTasks) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        $principal = $task.Principal
        $logonType = $principal.LogonType
        $status = if ($logonType -eq "Password" -or $logonType -eq "S4U") { "OK (non-interactive)" } else { "WARN (may require login)" }
        Write-Host "  $taskName : $logonType - $status" -ForegroundColor $(if ($status -like "OK*") { "Green" } else { "Yellow" })
    }
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Cyan
