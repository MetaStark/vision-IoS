# Check IOS001 Task Scheduler Configuration
$tasks = @(
    'FHQ_IOS001_EQUITY_DAILY',
    'FHQ_IOS001_CRYPTO_DAILY',
    'FHQ_IOS001_FX_DAILY',
    'FHQ-IoS001-Bulletproof-EQUITY',
    'FHQ-IoS001-Bulletproof-CRYPTO',
    'FHQ-IoS001-Bulletproof-FX',
    'ios001_daily_ingest_equity',
    'ios001_daily_ingest_crypto',
    'ios001_daily_ingest_fx'
)

foreach($name in $tasks) {
    try {
        $t = Get-ScheduledTask -TaskName $name -ErrorAction Stop
        Write-Host "TASK: $name"
        Write-Host "  Execute: $($t.Actions.Execute)"
        Write-Host "  Arguments: $($t.Actions.Arguments)"
        Write-Host "  Path Valid: $(Test-Path $t.Actions.Execute)"
        Write-Host ""
    } catch {
        Write-Host "TASK: $name - NOT FOUND"
        Write-Host ""
    }
}
