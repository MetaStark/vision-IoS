# =====================================================================
# FHQ_PRE_TIER_SCORING_DAEMON - Continuous Pre-Tier Score Calculator
# =====================================================================
# Scores DRAFT hypotheses with pre_tier_score_at_birth (immutable).
# Runs continuously with 5-minute internal sleep cycle.
# Run ledger entry written on daemon exit (crash or shutdown).
#
# Exit codes: 0=Clean shutdown, 1=Python failed, 2=Python not found, 3=Script not found
# =====================================================================

$ErrorActionPreference = "Stop"

$RepoRoot    = "C:\fhq-market-system\vision-ios"
$ScriptPath  = Join-Path $RepoRoot "03_FUNCTIONS\pre_tier_scoring_daemon.py"
$LogDir      = Join-Path $RepoRoot "04_ORCHESTRATION\logs"
$LogFile     = Join-Path $LogDir ("pre_tier_scoring_daemon_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

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
"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - FHQ_PRE_TIER_SCORING_DAEMON START (continuous)" | Out-File $LogFile -Encoding utf8
"Python: $PythonPath" | Out-File $LogFile -Append -Encoding utf8
"" | Out-File $LogFile -Append -Encoding utf8

try {
    $process = Start-Process -FilePath $PythonPath `
        -ArgumentList "`"$ScriptPath`"" `
        -WorkingDirectory $RepoRoot -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput (Join-Path $LogDir "pre_tier_stdout.tmp") `
        -RedirectStandardError (Join-Path $LogDir "pre_tier_stderr.tmp")
    $exitCode = $process.ExitCode
    if (Test-Path (Join-Path $LogDir "pre_tier_stdout.tmp")) {
        Get-Content (Join-Path $LogDir "pre_tier_stdout.tmp") | Out-File $LogFile -Append -Encoding utf8
        Remove-Item (Join-Path $LogDir "pre_tier_stdout.tmp") -ErrorAction SilentlyContinue
    }
    if (Test-Path (Join-Path $LogDir "pre_tier_stderr.tmp")) {
        "--- STDERR ---" | Out-File $LogFile -Append -Encoding utf8
        Get-Content (Join-Path $LogDir "pre_tier_stderr.tmp") | Out-File $LogFile -Append -Encoding utf8
        Remove-Item (Join-Path $LogDir "pre_tier_stderr.tmp") -ErrorAction SilentlyContinue
    }
} catch {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - EXCEPTION: $_" | Out-File $LogFile -Append -Encoding utf8
    $exitCode = 1
}

$endTime = Get-Date
$duration = ($endTime - $startTime).TotalSeconds
"" | Out-File $LogFile -Append -Encoding utf8
"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - FHQ_PRE_TIER_SCORING_DAEMON EXIT (exit=$exitCode, ${duration}s)" | Out-File $LogFile -Append -Encoding utf8

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
VALUES ('FHQ_PRE_TIER_SCORING_DAEMON',
 '$($startTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss"))'::timestamptz,
 '$($endTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss"))'::timestamptz,
 $exitCode, '$($LogFile -replace '\\', '\\')', '$errorExcerpt',
 (SELECT jsonb_build_object('scored_today', (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon WHERE pre_tier_score_at_birth IS NOT NULL AND DATE(created_at) = CURRENT_DATE))),
 (SELECT jsonb_build_object('latest_scored', (SELECT MAX(created_at)::text FROM fhq_learning.hypothesis_canon WHERE pre_tier_score_at_birth IS NOT NULL))));
"@
        $auditSQL | & $psqlPath -h 127.0.0.1 -p 54322 -U postgres -d postgres -q 2>&1 | Out-File $LogFile -Append -Encoding utf8
    }
} catch { "WARNING: Run ledger write failed: $_" | Out-File $LogFile -Append -Encoding utf8 }

exit $exitCode
