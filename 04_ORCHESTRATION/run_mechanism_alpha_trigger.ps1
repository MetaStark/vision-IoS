# =====================================================================
# FHQ_MECHANISM_ALPHA_TRIGGER - Production Trigger Scanner
# =====================================================================
# Pipeline step 3: Scans indicator data for hypothesis trigger conditions
# and writes to fhq_learning.trigger_events.
#
# Runs with --once for single-cycle execution via Task Scheduler.
#
# Exit codes: 0=Success, 1=Python failed, 2=Python not found, 3=Script not found
# =====================================================================

$ErrorActionPreference = "Stop"

$RepoRoot    = "C:\fhq-market-system\vision-ios"
$ScriptPath  = Join-Path $RepoRoot "03_FUNCTIONS\mechanism_alpha_trigger.py"
$LogDir      = Join-Path $RepoRoot "04_ORCHESTRATION\logs"
$LogFile     = Join-Path $LogDir ("mechanism_alpha_trigger_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

$PythonPath = $null
$candidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
    "python.exe"
)
foreach ($p in $candidates) { if (Test-Path $p) { $PythonPath = $p; break } }
if (-not $PythonPath) { try { $PythonPath = (Get-Command python -ErrorAction Stop).Source } catch {} }
if (-not $PythonPath) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - FATAL: Python not found" | Out-File $LogFile -Encoding utf8
    exit 2
}
if (-not (Test-Path $ScriptPath)) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - FATAL: Script not found: $ScriptPath" | Out-File $LogFile -Encoding utf8
    exit 3
}

$startTime = Get-Date
"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - FHQ_MECHANISM_ALPHA_TRIGGER START" | Out-File $LogFile -Encoding utf8
"Python: $PythonPath" | Out-File $LogFile -Append -Encoding utf8
"" | Out-File $LogFile -Append -Encoding utf8

try {
    $process = Start-Process -FilePath $PythonPath `
        -ArgumentList "`"$ScriptPath`" --once" `
        -WorkingDirectory $RepoRoot -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput (Join-Path $LogDir "alpha_trigger_stdout.tmp") `
        -RedirectStandardError (Join-Path $LogDir "alpha_trigger_stderr.tmp")
    $exitCode = $process.ExitCode
    if (Test-Path (Join-Path $LogDir "alpha_trigger_stdout.tmp")) {
        Get-Content (Join-Path $LogDir "alpha_trigger_stdout.tmp") | Out-File $LogFile -Append -Encoding utf8
        Remove-Item (Join-Path $LogDir "alpha_trigger_stdout.tmp") -ErrorAction SilentlyContinue
    }
    if (Test-Path (Join-Path $LogDir "alpha_trigger_stderr.tmp")) {
        "--- STDERR ---" | Out-File $LogFile -Append -Encoding utf8
        Get-Content (Join-Path $LogDir "alpha_trigger_stderr.tmp") | Out-File $LogFile -Append -Encoding utf8
        Remove-Item (Join-Path $LogDir "alpha_trigger_stderr.tmp") -ErrorAction SilentlyContinue
    }
} catch {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - EXCEPTION: $_" | Out-File $LogFile -Append -Encoding utf8
    $exitCode = 1
}

$endTime = Get-Date
$duration = ($endTime - $startTime).TotalSeconds
"" | Out-File $LogFile -Append -Encoding utf8
"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - FHQ_MECHANISM_ALPHA_TRIGGER END (exit=$exitCode, ${duration}s)" | Out-File $LogFile -Append -Encoding utf8

try {
    $env:PGPASSWORD = "postgres"
    $psqlPath = $null
    @("C:\Program Files\PostgreSQL\17\bin\psql.exe","C:\Program Files\PostgreSQL\16\bin\psql.exe","psql.exe") | ForEach-Object { if (Test-Path $_) { $psqlPath = $_; return } }
    if (-not $psqlPath) { try { $psqlPath = (Get-Command psql -ErrorAction Stop).Source } catch {} }
    if ($psqlPath) {
        $errorExcerpt = ""
        if ($exitCode -ne 0) { $errorExcerpt = (Get-Content $LogFile -Tail 5 | Out-String).Replace("'", "''").Substring(0, [Math]::Min(500, (Get-Content $LogFile -Tail 5 | Out-String).Length)) }
        $auditSQL = @"
INSERT INTO fhq_monitoring.run_ledger (task_name, started_at, finished_at, exit_code, log_path, error_excerpt, rows_written_by_table, max_data_date_by_domain)
VALUES ('FHQ_MECHANISM_ALPHA_TRIGGER',
 '$($startTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss"))'::timestamptz,
 '$($endTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss"))'::timestamptz,
 $exitCode, '$($LogFile -replace '\\', '\\')', '$errorExcerpt',
 (SELECT jsonb_build_object('trigger_events_today', (SELECT COUNT(*) FROM fhq_learning.trigger_events WHERE DATE(event_timestamp) = CURRENT_DATE))),
 (SELECT jsonb_build_object('latest_trigger', (SELECT MAX(event_timestamp)::text FROM fhq_learning.trigger_events))));
"@
        $auditSQL | & $psqlPath -h 127.0.0.1 -p 54322 -U postgres -d postgres -q 2>&1 | Out-File $LogFile -Append -Encoding utf8
    }
} catch { "WARNING: Run ledger write failed: $_" | Out-File $LogFile -Append -Encoding utf8 }

exit $exitCode
