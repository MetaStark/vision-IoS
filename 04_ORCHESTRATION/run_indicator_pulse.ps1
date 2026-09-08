# =====================================================================
# FHQ_INDICATOR_PULSE - Production Indicator Computation
# =====================================================================
# CEO-DIR-20260130-OPS-INDICATOR-PULSE-001
# Deliverable D1: Production Scheduler
#
# Runs phase2_indicator_backfill.py with full audit trail.
# Writes execution record to database (fhq_monitoring.indicator_pulse_audit).
# Designed for Windows Task Scheduler - no interactive dependencies.
#
# Exit codes:
#   0 = Success
#   1 = Python script failed
#   2 = Python not found
#   3 = Script file not found
#   4 = Database audit write failed
# =====================================================================

$ErrorActionPreference = "Stop"

# --- Configuration ---
$RepoRoot    = "C:\fhq-market-system\vision-ios"
$ScriptPath  = Join-Path $RepoRoot "03_FUNCTIONS\phase2_indicator_backfill.py"
$LogDir      = Join-Path $RepoRoot "04_ORCHESTRATION\logs"
$LogFile     = Join-Path $LogDir ("indicator_pulse_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

# --- Ensure log directory ---
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# --- Find Python ---
$PythonPath = $null
$candidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
    "python.exe"
)
foreach ($p in $candidates) {
    if (Test-Path $p) {
        $PythonPath = $p
        break
    }
}
if (-not $PythonPath) {
    try { $PythonPath = (Get-Command python -ErrorAction Stop).Source } catch {}
}
if (-not $PythonPath) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - FATAL: Python not found" | Out-File $LogFile -Encoding utf8
    exit 2
}

# --- Verify script exists ---
if (-not (Test-Path $ScriptPath)) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - FATAL: Script not found: $ScriptPath" | Out-File $LogFile -Encoding utf8
    exit 3
}

# --- Execute ---
$startTime = Get-Date
"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - FHQ_INDICATOR_PULSE START" | Out-File $LogFile -Encoding utf8
"Python: $PythonPath" | Out-File $LogFile -Append -Encoding utf8
"Script: $ScriptPath" | Out-File $LogFile -Append -Encoding utf8
"WorkingDir: $RepoRoot" | Out-File $LogFile -Append -Encoding utf8
"" | Out-File $LogFile -Append -Encoding utf8

try {
    $process = Start-Process -FilePath $PythonPath `
        -ArgumentList "`"$ScriptPath`"" `
        -WorkingDirectory $RepoRoot `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput (Join-Path $LogDir "indicator_pulse_stdout.tmp") `
        -RedirectStandardError (Join-Path $LogDir "indicator_pulse_stderr.tmp")

    $exitCode = $process.ExitCode

    # Append stdout/stderr to log
    if (Test-Path (Join-Path $LogDir "indicator_pulse_stdout.tmp")) {
        Get-Content (Join-Path $LogDir "indicator_pulse_stdout.tmp") | Out-File $LogFile -Append -Encoding utf8
        Remove-Item (Join-Path $LogDir "indicator_pulse_stdout.tmp") -ErrorAction SilentlyContinue
    }
    if (Test-Path (Join-Path $LogDir "indicator_pulse_stderr.tmp")) {
        "--- STDERR ---" | Out-File $LogFile -Append -Encoding utf8
        Get-Content (Join-Path $LogDir "indicator_pulse_stderr.tmp") | Out-File $LogFile -Append -Encoding utf8
        Remove-Item (Join-Path $LogDir "indicator_pulse_stderr.tmp") -ErrorAction SilentlyContinue
    }
} catch {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - EXCEPTION: $_" | Out-File $LogFile -Append -Encoding utf8
    $exitCode = 1
}

$endTime = Get-Date
$duration = ($endTime - $startTime).TotalSeconds

"" | Out-File $LogFile -Append -Encoding utf8
"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - FHQ_INDICATOR_PULSE END" | Out-File $LogFile -Append -Encoding utf8
"Exit code: $exitCode" | Out-File $LogFile -Append -Encoding utf8
"Duration: $([math]::Round($duration, 1))s" | Out-File $LogFile -Append -Encoding utf8

# --- Write enriched audit trail to database ---
try {
    $env:PGPASSWORD = "postgres"
    $psqlPath = $null
    $psqlCandidates = @(
        "C:\Program Files\PostgreSQL\17\bin\psql.exe",
        "C:\Program Files\PostgreSQL\16\bin\psql.exe",
        "psql.exe"
    )
    foreach ($p in $psqlCandidates) {
        if (Test-Path $p) { $psqlPath = $p; break }
    }
    if (-not $psqlPath) {
        try { $psqlPath = (Get-Command psql -ErrorAction Stop).Source } catch {}
    }

    if ($psqlPath) {
        # D5: Enriched audit — INSERT basic record, then UPDATE with row counts from DB
        $auditSQL = @"
INSERT INTO fhq_monitoring.indicator_pulse_audit
(run_date, start_time, end_time, exit_code, duration_seconds, log_path, python_path)
VALUES
(CURRENT_DATE,
 '$($startTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss"))'::timestamptz,
 '$($endTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss"))'::timestamptz,
 $exitCode,
 $([math]::Round($duration, 1)),
 '$($LogFile -replace '\\', '\\')',
 '$($PythonPath -replace '\\', '\\')');

UPDATE fhq_monitoring.indicator_pulse_audit
SET rows_written_momentum = sub.mom_today,
    rows_written_volatility = sub.vol_today,
    latest_data_date = sub.max_date
FROM (
    SELECT
        (SELECT COUNT(*) FROM fhq_indicators.momentum
         WHERE signal_date = CURRENT_DATE) as mom_today,
        (SELECT COUNT(*) FROM fhq_indicators.volatility
         WHERE signal_date = CURRENT_DATE) as vol_today,
        GREATEST(
            (SELECT MAX(signal_date) FROM fhq_indicators.momentum),
            (SELECT MAX(signal_date) FROM fhq_indicators.volatility)
        ) as max_date
) sub
WHERE id = (SELECT MAX(id) FROM fhq_monitoring.indicator_pulse_audit);
"@
        $auditSQL | & $psqlPath -h 127.0.0.1 -p 54322 -U postgres -d postgres -q 2>&1 | Out-File $LogFile -Append -Encoding utf8
        "Audit trail written to database (enriched)" | Out-File $LogFile -Append -Encoding utf8

        # D3: Also write to run_ledger for unified monitoring
        $runLedgerSQL = @"
INSERT INTO fhq_monitoring.run_ledger
(task_name, started_at, finished_at, exit_code, log_path,
 rows_written_by_table, max_data_date_by_domain)
VALUES
('FHQ_INDICATOR_PULSE',
 '$($startTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss"))'::timestamptz,
 '$($endTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss"))'::timestamptz,
 $exitCode,
 '$($LogFile -replace '\\', '\\')',
 (SELECT jsonb_build_object(
    'momentum', (SELECT COUNT(*) FROM fhq_indicators.momentum WHERE signal_date = CURRENT_DATE),
    'volatility', (SELECT COUNT(*) FROM fhq_indicators.volatility WHERE signal_date = CURRENT_DATE)
 )),
 (SELECT jsonb_build_object(
    'latest_signal_date', GREATEST(
        (SELECT MAX(signal_date)::text FROM fhq_indicators.momentum),
        (SELECT MAX(signal_date)::text FROM fhq_indicators.volatility)
    )
 ))
);
"@
        $runLedgerSQL | & $psqlPath -h 127.0.0.1 -p 54322 -U postgres -d postgres -q 2>&1 | Out-File $LogFile -Append -Encoding utf8
        "Run ledger written" | Out-File $LogFile -Append -Encoding utf8
    } else {
        "WARNING: psql not found - audit trail not written to database" | Out-File $LogFile -Append -Encoding utf8
    }
} catch {
    "WARNING: Audit trail write failed: $_" | Out-File $LogFile -Append -Encoding utf8
}

exit $exitCode
