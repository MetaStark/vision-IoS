# =====================================================================
# FHQ_SHADOW_ROI_CALCULATOR - Production Shadow ROI Calculator Runner
# =====================================================================
#
# Runs shadow_roi_calculator.py with full audit trail.
# Writes execution record to fhq_monitoring.run_ledger.
# Designed for Windows Task Scheduler - no interactive dependencies.
#
# Schedule: Daily 07:00 CET (after INDICATOR_PULSE 06:00,
#           before morning verification 08:30)
#
# Exit codes:
#   0 = Success
#   1 = Python script failed
#   2 = Python not found
#   3 = Script file not found
# =====================================================================

$ErrorActionPreference = "Stop"

# --- Configuration ---
$RepoRoot    = "C:\fhq-market-system\vision-ios"
$ScriptPath  = Join-Path $RepoRoot "03_FUNCTIONS\shadow_roi_calculator.py"
$LogDir      = Join-Path $RepoRoot "04_ORCHESTRATION\logs"
$LogFile     = Join-Path $LogDir ("shadow_roi_calculator_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

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
"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - FHQ_SHADOW_ROI_CALCULATOR START" | Out-File $LogFile -Encoding utf8
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
        -RedirectStandardOutput (Join-Path $LogDir "shadow_roi_stdout.tmp") `
        -RedirectStandardError (Join-Path $LogDir "shadow_roi_stderr.tmp")

    $exitCode = $process.ExitCode

    # Append stdout/stderr to log
    if (Test-Path (Join-Path $LogDir "shadow_roi_stdout.tmp")) {
        Get-Content (Join-Path $LogDir "shadow_roi_stdout.tmp") | Out-File $LogFile -Append -Encoding utf8
        Remove-Item (Join-Path $LogDir "shadow_roi_stdout.tmp") -ErrorAction SilentlyContinue
    }
    if (Test-Path (Join-Path $LogDir "shadow_roi_stderr.tmp")) {
        "--- STDERR ---" | Out-File $LogFile -Append -Encoding utf8
        Get-Content (Join-Path $LogDir "shadow_roi_stderr.tmp") | Out-File $LogFile -Append -Encoding utf8
        Remove-Item (Join-Path $LogDir "shadow_roi_stderr.tmp") -ErrorAction SilentlyContinue
    }
} catch {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - EXCEPTION: $_" | Out-File $LogFile -Append -Encoding utf8
    $exitCode = 1
}

$endTime = Get-Date
$duration = ($endTime - $startTime).TotalSeconds

"" | Out-File $LogFile -Append -Encoding utf8
"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - FHQ_SHADOW_ROI_CALCULATOR END" | Out-File $LogFile -Append -Encoding utf8
"Exit code: $exitCode" | Out-File $LogFile -Append -Encoding utf8
"Duration: $([math]::Round($duration, 1))s" | Out-File $LogFile -Append -Encoding utf8

# --- Write to run_ledger ---
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
        $errorExcerpt = ""
        if ($exitCode -ne 0) {
            $errorExcerpt = (Get-Content $LogFile -Tail 5 | Out-String).Replace("'", "''").Substring(0, [Math]::Min(500, (Get-Content $LogFile -Tail 5 | Out-String).Length))
        }

        $auditSQL = @"
INSERT INTO fhq_monitoring.run_ledger
(task_name, started_at, finished_at, exit_code, log_path, error_excerpt,
 rows_written_by_table, max_data_date_by_domain)
VALUES
('FHQ_SHADOW_ROI_CALCULATOR',
 '$($startTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss"))'::timestamptz,
 '$($endTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss"))'::timestamptz,
 $exitCode,
 '$($LogFile -replace '\\', '\\')',
 '$errorExcerpt',
 (SELECT jsonb_build_object(
    'capital_ledger', (SELECT COUNT(*) FROM fhq_execution.capital_ledger
                       WHERE batch_id LIKE 'SHADOW_TRADE_PNL_%')
 )),
 (SELECT jsonb_build_object(
    'latest_shadow_trade', (SELECT MAX(exit_time)::text
                            FROM fhq_execution.shadow_trades
                            WHERE status = 'CLOSED')
 ))
);
"@
        $auditSQL | & $psqlPath -h 127.0.0.1 -p 54322 -U postgres -d postgres -q 2>&1 | Out-File $LogFile -Append -Encoding utf8
        "Run ledger written to database" | Out-File $LogFile -Append -Encoding utf8
    } else {
        "WARNING: psql not found - run ledger not written" | Out-File $LogFile -Append -Encoding utf8
    }
} catch {
    "WARNING: Run ledger write failed: $_" | Out-File $LogFile -Append -Encoding utf8
}

exit $exitCode
