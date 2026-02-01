# CEO-DIR-2025-INFRA-002: Revert Python tasks to user context for Lane 2
# SYSTEM cannot access user profile Python installation
# After this, run fix_scheduled_tasks_interactive.ps1 to add password

param([string]$Username)

if (-not $Username) {
    $Username = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
}

Write-Host "Reverting Python tasks to user context: $Username" -ForegroundColor Cyan

$pythonTasks = @(
    "FHQ-IoS001-Bulletproof-CRYPTO",
    "FHQ-IoS001-Bulletproof-EQUITY",
    "FHQ-IoS001-Bulletproof-FX",
    "FHQ_IOS001_CRYPTO_DAILY",
    "FHQ_IOS001_EQUITY_DAILY",
    "FHQ_IOS001_FX_DAILY",
    "FHQ_IOS003_REGIME_DAILY_V4",
    "FHQ_SENTINEL_DAILY"
)

foreach ($taskName in $pythonTasks) {
    Write-Host "  Reverting: $taskName" -ForegroundColor White
    schtasks /change /tn $taskName /ru $Username 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    OK" -ForegroundColor Green
    } else {
        Write-Host "    FAIL" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Tasks reverted to user context (Interactive mode)" -ForegroundColor Yellow
Write-Host "NOW RUN: .\fix_scheduled_tasks_interactive.ps1" -ForegroundColor Cyan
Write-Host "This will add your password and enable non-interactive execution" -ForegroundColor Cyan
