# ============================================================================
# D15 — GRANT-pakke for rollen fhq_executive_task, generert fra databaseloggen
# ============================================================================
# KJOERER INGENTING MOT DATABASEN UTOVER LESING. Skriver SQL til skjermen og til
# D:\Runtime\d15_grant_package.sql for gjennomlesing. CEO/VEGA kjoerer den selv som
# supabase_admin etter godkjenning.
#
#   powershell -ExecutionPolicy Bypass -File .\d15_grant_package.ps1
#
# Hva den gjoer:
#   1. Leser "permission denied for <type> <navn>" fra db-containerens logg siden 17:15 UTC 09.09
#      (etter at autentiseringen ble rettet — foer det var feilene passord, ikke rettigheter).
#   2. Slaar opp skjema for hvert objekt via information_schema (kun lesing, som postgres).
#   3. Skriver GRANT-setninger: SELECT/INSERT/UPDATE paa tabeller, USAGE paa sekvenser og
#      skjemaer, EXECUTE paa funksjoner. Ikke DELETE, ikke TRUNCATE, ikke eierbytte.
# ============================================================================
$ErrorActionPreference = 'Stop'
$Role   = 'fhq_executive_task'
$Since  = '2026-09-09T17:15:00Z'
$Db     = 'supabase_db_fhq-market-system'
$Out    = 'D:\Runtime\d15_grant_package.sql'

Write-Host "== 1. Leser permission-denied fra $Db siden $Since ==" -ForegroundColor Cyan
$lines = docker logs $Db --since $Since 2>&1 | Select-String -Pattern "permission denied for (table|sequence|function|schema|relation|view) (\S+)"
$objs = @{}
foreach ($l in $lines) {
  $m = [regex]::Match($l.Line, "$Role@\S+ .*permission denied for (table|sequence|function|schema|relation|view) ([\w\.\""]+)")
  if ($m.Success) {
    $kind = $m.Groups[1].Value; $name = $m.Groups[2].Value.Trim('"')
    $key = "$kind|$name"
    if (-not $objs.ContainsKey($key)) { $objs[$key] = 0 }
    $objs[$key]++
  }
}
if ($objs.Count -eq 0) { Write-Host "Ingen permission-denied for $Role funnet i loggen siden $Since. Ingenting aa gi." -ForegroundColor Yellow; exit 0 }
Write-Host ("{0} distinkte objekter avvist for {1}:" -f $objs.Count, $Role)
$objs.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object { "  {0,6}x  {1}" -f $_.Value, $_.Key }

Write-Host "`n== 2. Slaar opp skjema (kun lesing) ==" -ForegroundColor Cyan
$sql = New-Object System.Collections.Generic.List[string]
$sql.Add("-- D15 GRANT-pakke for $Role, generert $(Get-Date -Format s) fra loggen siden $Since")
$sql.Add("-- Kjoeres som supabase_admin ETTER gjennomlesing. Reverseres med REVOKE paa samme objekter.")
$sql.Add("BEGIN;")
$schemas = @{}
foreach ($k in ($objs.Keys | Sort-Object)) {
  $kind, $name = $k -split '\|', 2
  if ($name -like '*.*') { $schema, $bare = $name -split '\.', 2 } else {
    $bare = $name
    $q = "SELECT table_schema FROM information_schema.tables WHERE table_name = '$bare' UNION SELECT sequence_schema FROM information_schema.sequences WHERE sequence_name = '$bare' UNION SELECT routine_schema FROM information_schema.routines WHERE routine_name = '$bare' LIMIT 5;"
    $found = psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -At -c $q 2>$null
    if (-not $found) { $sql.Add("-- UKJENT SKJEMA for $kind $bare  <- sjekk manuelt"); continue }
    $schema = ($found -split "`n")[0].Trim()
    if (($found -split "`n").Count -gt 1) { $sql.Add("-- MERK: $bare finnes i flere skjemaer: $($found -replace "`n", ', ') — bruker $schema") }
  }
  $schemas[$schema] = $true
  switch ($kind) {
    { $_ -in 'table','relation','view' } { $sql.Add("GRANT SELECT, INSERT, UPDATE ON TABLE $schema.$bare TO $Role;") }
    'sequence' { $sql.Add("GRANT USAGE, SELECT ON SEQUENCE $schema.$bare TO $Role;") }
    'function' { $sql.Add("GRANT EXECUTE ON FUNCTION $schema.$bare TO $Role;") }
    'schema'   { }
  }
}
foreach ($s in ($schemas.Keys | Sort-Object)) { $sql.Insert(3, "GRANT USAGE ON SCHEMA $s TO $Role;") }
$sql.Add("COMMIT;")
$sql.Add("-- Akseptansetest etter kjoering (vent to tikk = 10 min):")
$sql.Add("--   SELECT run_id, COUNT(*) FILTER (WHERE status='SUCCESS') AS ok, COUNT(*) AS n FROM fhq_runtime.run_attempts WHERE started_at >= NOW() - INTERVAL '10 minutes' GROUP BY 1 ORDER BY 2;")

Write-Host "`n== 3. GRANT-pakke ==" -ForegroundColor Cyan
$sql | ForEach-Object { $_ }
$sql | Set-Content -Path $Out -Encoding ASCII
Write-Host "`nSkrevet til $Out  ($($sql.Count) linjer). INGENTING er kjoert mot databasen." -ForegroundColor Green
Write-Host "Kjoer etter godkjenning:  psql -h 127.0.0.1 -p 54322 -U supabase_admin -d postgres -f $Out"
