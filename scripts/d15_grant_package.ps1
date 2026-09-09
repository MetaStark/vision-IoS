# ============================================================================
# D15 - GRANT package for role fhq_executive_task, generated from the database log
# ============================================================================
# EXECUTES NOTHING AGAINST THE DATABASE EXCEPT READS. Prints SQL to screen and writes
# it to D:\Runtime\d15_grant_package.sql for review. CEO/VEGA run it as supabase_admin
# after approval.
#
#   powershell -ExecutionPolicy Bypass -File .\d15_grant_package.ps1
#
# ASCII only: Windows PowerShell 5.1 reads BOM-less files as ANSI.
# ============================================================================
# 'Continue', not 'Stop': docker logs emits the database log on stderr, and Stop would abort on it.
$ErrorActionPreference = 'Continue'
$Role  = 'fhq_executive_task'
$Since = '2026-09-09T17:15:00Z'
$Db    = 'supabase_db_fhq-market-system'
$Out   = 'D:\Runtime\d15_grant_package.sql'

Write-Host ('== 1. Reading permission-denied from ' + $Db + ' since ' + $Since + ' ==') -ForegroundColor Cyan
# Merge stderr into stdout at the cmd level so PowerShell sees plain strings, not error records.
$raw = cmd /c ('docker logs ' + $Db + ' --since ' + $Since + ' 2>&1')
$objs = @{}
$rx = [regex]('(?i)' + [regex]::Escape($Role) + '@\S+ .*permission denied for (table|sequence|function|schema|relation|view) ([\w\.]+)')
foreach ($line in $raw) {
    $m = $rx.Match([string]$line)
    if ($m.Success) {
        $key = $m.Groups[1].Value.ToLower() + '|' + $m.Groups[2].Value
        if (-not $objs.ContainsKey($key)) { $objs[$key] = 0 }
        $objs[$key]++
    }
}
if ($objs.Count -eq 0) {
    Write-Host ('No permission-denied lines for ' + $Role + ' since ' + $Since + '. Nothing to grant.') -ForegroundColor Yellow
    exit 0
}
Write-Host ([string]$objs.Count + ' distinct objects denied for ' + $Role + ':')
foreach ($e in ($objs.GetEnumerator() | Sort-Object Value -Descending)) {
    Write-Host ('  ' + $e.Value.ToString().PadLeft(6) + 'x  ' + $e.Key)
}

Write-Host ''
Write-Host '== 2. Resolving schemas (read-only, as postgres) ==' -ForegroundColor Cyan
$sql = New-Object System.Collections.Generic.List[string]
$sql.Add('-- D15 GRANT package for ' + $Role + ', generated ' + (Get-Date -Format s) + ' from log since ' + $Since)
$sql.Add('-- Run as supabase_admin AFTER review. Reverse with REVOKE on the same objects.')
$sql.Add('BEGIN;')
$schemaUsage = New-Object System.Collections.Generic.List[string]
$schemas = @{}
foreach ($k in ($objs.Keys | Sort-Object)) {
    $parts = $k.Split('|', 2)
    $kind = $parts[0]; $name = $parts[1]
    if ($kind -eq 'schema') { $schemas[$name] = $true; continue }
    if ($name.Contains('.')) {
        $np = $name.Split('.', 2); $schema = $np[0]; $bare = $np[1]
    } else {
        $bare = $name
        $q = "SELECT table_schema FROM information_schema.tables WHERE table_name = '" + $bare + "' UNION SELECT sequence_schema FROM information_schema.sequences WHERE sequence_name = '" + $bare + "' UNION SELECT routine_schema FROM information_schema.routines WHERE routine_name = '" + $bare + "' LIMIT 5;"
        $found = @(psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -At -c $q 2>$null | Where-Object { $_ -ne '' })
        if ($found.Count -eq 0) { $sql.Add('-- UNKNOWN SCHEMA for ' + $kind + ' ' + $bare + '  <- check manually'); continue }
        $schema = $found[0].Trim()
        if ($found.Count -gt 1) { $sql.Add('-- NOTE: ' + $bare + ' exists in several schemas: ' + ($found -join ', ') + ' - using ' + $schema) }
    }
    $schemas[$schema] = $true
    $fq = $schema + '.' + $bare
    switch ($kind) {
        'table'    { $sql.Add('GRANT SELECT, INSERT, UPDATE ON TABLE ' + $fq + ' TO ' + $Role + ';') }
        'relation' { $sql.Add('GRANT SELECT, INSERT, UPDATE ON TABLE ' + $fq + ' TO ' + $Role + ';') }
        'view'     { $sql.Add('GRANT SELECT ON TABLE ' + $fq + ' TO ' + $Role + ';') }
        'sequence' { $sql.Add('GRANT USAGE, SELECT ON SEQUENCE ' + $fq + ' TO ' + $Role + ';') }
        'function' { $sql.Add('GRANT EXECUTE ON FUNCTION ' + $fq + ' TO ' + $Role + ';') }
    }
}
$i = 3
foreach ($s in ($schemas.Keys | Sort-Object)) { $sql.Insert($i, 'GRANT USAGE ON SCHEMA ' + $s + ' TO ' + $Role + ';'); $i++ }
$sql.Add('COMMIT;')
$sql.Add('-- Acceptance test after running (wait two ticks = 10 min):')
$sql.Add("--   SELECT run_id, COUNT(*) FILTER (WHERE status = 'SUCCESS') AS ok, COUNT(*) AS n FROM fhq_runtime.run_attempts WHERE started_at >= NOW() - INTERVAL '10 minutes' GROUP BY 1 ORDER BY 2;")

Write-Host ''
Write-Host '== 3. GRANT package ==' -ForegroundColor Cyan
foreach ($l in $sql) { Write-Host $l }
[System.IO.File]::WriteAllLines($Out, $sql, [System.Text.Encoding]::ASCII)
Write-Host ''
Write-Host ('Written to ' + $Out + ' (' + [string]$sql.Count + ' lines). NOTHING was executed against the database.') -ForegroundColor Green
Write-Host ('Run after approval:  psql -h 127.0.0.1 -p 54322 -U supabase_admin -d postgres -f ' + $Out)
