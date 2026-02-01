# CEO-DIR-2025-INFRA-002: Harden FHQ Tasks to SYSTEM Account
# Lane 1: SYSTEM account (no password required)
#
# This script converts Interactive tasks to run under SYSTEM account
# SYSTEM can access local DB, filesystem, and run Python scripts
#
# IMPORTANT: Run as Administrator

param(
    [switch]$WhatIf = $false
)

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "CEO-DIR-2025-INFRA-002 SCHEDULER HARDENING (LANE 1 - SYSTEM)" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    exit 1
}

Write-Host "Running as Administrator: YES" -ForegroundColor Green
Write-Host ""

# Tasks to harden (Lane 1 - can run under SYSTEM)
$lane1Tasks = @(
    "FHQ-IoS001-Bulletproof-CRYPTO",
    "FHQ-IoS001-Bulletproof-EQUITY",
    "FHQ-IoS001-Bulletproof-FX",
    "FHQ_IOS001_CRYPTO_DAILY",
    "FHQ_IOS001_EQUITY_DAILY",
    "FHQ_IOS001_FX_DAILY",
    "FHQ_IOS003_REGIME_DAILY_V4",
    "FHQ_SENTINEL_DAILY"
)

# Tasks that need special handling (Lane 2 - may need user context for Docker)
$lane2Tasks = @(
    "FHQ_HMM_Daily_Inference",
    "FHQ_HMM_Health_Check"
)

Write-Host "LANE 1 TASKS (Converting to SYSTEM):" -ForegroundColor Yellow
foreach ($taskName in $lane1Tasks) {
    Write-Host "  - $taskName" -ForegroundColor Gray
}
Write-Host ""

Write-Host "LANE 2 TASKS (Need user context - skipped for now):" -ForegroundColor Yellow
foreach ($taskName in $lane2Tasks) {
    Write-Host "  - $taskName" -ForegroundColor Gray
}
Write-Host ""

if ($WhatIf) {
    Write-Host "[WHATIF MODE] No changes will be made" -ForegroundColor Magenta
    Write-Host ""
}

$successCount = 0
$failCount = 0
$skippedCount = 0

foreach ($taskName in $lane1Tasks) {
    Write-Host "Processing: $taskName" -ForegroundColor White

    try {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if (-not $task) {
            Write-Host "  SKIP: Task not found" -ForegroundColor Yellow
            $skippedCount++
            continue
        }

        $principal = $task.Principal
        if ($principal.LogonType -ne "Interactive") {
            Write-Host "  SKIP: Already non-interactive ($($principal.LogonType))" -ForegroundColor Green
            $skippedCount++
            continue
        }

        if ($WhatIf) {
            Write-Host "  [WHATIF] Would change to SYSTEM" -ForegroundColor Magenta
            continue
        }

        # Use schtasks to change to SYSTEM (doesn't require password)
        $result = schtasks /change /tn $taskName /ru SYSTEM 2>&1

        if ($LASTEXITCODE -eq 0) {
            Write-Host "  OK: Changed to SYSTEM" -ForegroundColor Green
            $successCount++
        } else {
            Write-Host "  FAIL: $result" -ForegroundColor Red
            $failCount++
        }
    }
    catch {
        Write-Host "  ERROR: $_" -ForegroundColor Red
        $failCount++
    }
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "SUMMARY" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "  Success: $successCount" -ForegroundColor Green
Write-Host "  Failed:  $failCount" -ForegroundColor $(if ($failCount -gt 0) { "Red" } else { "Green" })
Write-Host "  Skipped: $skippedCount" -ForegroundColor Yellow
Write-Host ""

# Verification
if (-not $WhatIf -and $successCount -gt 0) {
    Write-Host "VERIFICATION:" -ForegroundColor Cyan
    foreach ($taskName in $lane1Tasks) {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($task) {
            $logonType = $task.Principal.LogonType
            $userId = $task.Principal.UserId
            $status = if ($logonType -ne "Interactive") { "OK" } else { "FAIL" }
            $color = if ($status -eq "OK") { "Green" } else { "Red" }
            Write-Host "  [$status] $taskName : $userId ($logonType)" -ForegroundColor $color
        }
    }
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Cyan
