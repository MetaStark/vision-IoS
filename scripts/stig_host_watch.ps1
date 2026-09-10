# ============================================================================
# STIG-HOST-WATCH - les-bare helsevakt paa verten. INGEN skriving, INGEN DDL.
# ============================================================================
# Kjoerer kun SELECT mot databasen, skriver et sammendrag til en fil, og gjoer
# ingenting annet. Trenger verken G4 eller VEGA. Dette er trinn 1, trygg versjon:
# den fjerner mellommann-rollen for OVERVAAKING med en gang.
#
# Manuelt:   powershell -ExecutionPolicy Bypass -File D:\Runtime\stig_host_watch.ps1
# Planlagt:  se schtasks-kommandoen nederst i STIG_HOST_CHECKLIST.md
# ============================================================================
$ErrorActionPreference = 'Continue'
$Pg      = 'C:\Program Files\PostgreSQL\17\bin\psql.exe'  # juster om psql ligger et annet sted
if (-not (Test-Path $Pg)) { $Pg = 'psql' }               # fall tilbake til PATH
$H       = '127.0.0.1'; $Port = '54322'; $Db = 'postgres'; $U = 'postgres'
$DigDir  = 'D:\Runtime\digest'
$stamp   = Get-Date -Format 'yyyyMMdd_HHmm'
$oslo    = Get-Date -Format 'yyyy-MM-dd HH:mm'
if (-not (Test-Path $DigDir)) { New-Item -ItemType Directory -Path $DigDir -Force | Out-Null }
$out     = Join-Path $DigDir ("STIG_HOST_" + $stamp + ".md")

# PGPASSWORD hentes fra Machine-scope (satt riktig 09-09, se plan-dok par. 18.8)
if (-not $env:PGPASSWORD) { $env:PGPASSWORD = [Environment]::GetEnvironmentVariable('PGPASSWORD','Machine') }

function Q($sql) { & $Pg -h $H -p $Port -U $U -d $Db -A -t -c $sql 2>&1 }

# --- Les helse (kun SELECT) ---
$health  = Q "SELECT status || ':' || COUNT(*) FROM fhq_runtime.run_attempts WHERE started_at >= NOW() - INTERVAL '15 minutes' GROUP BY status ORDER BY status;"
$dead    = Q "SELECT run_id FROM fhq_runtime.run_attempts WHERE started_at >= NOW() - INTERVAL '30 minutes' GROUP BY run_id HAVING COUNT(*) FILTER (WHERE status='SUCCESS') = 0 ORDER BY run_id;"
$fails   = Q "SELECT run_id || ' | ' || LEFT(regexp_replace(split_part(regexp_replace(error_message,'\s+$',''), E'\n', array_length(string_to_array(regexp_replace(error_message,'\s+$',''), E'\n'),1)),'\s+',' ','g'),120) FROM (SELECT DISTINCT ON (run_id) run_id, error_message FROM fhq_runtime.run_failures WHERE created_at >= NOW() - INTERVAL '15 minutes' ORDER BY run_id, created_at DESC) t ORDER BY run_id;"
$fhb     = Q "SELECT to_char(MAX(heartbeat) AT TIME ZONE 'Europe/Oslo','YYYY-MM-DD HH24:MI') FROM fhq_control.factory_cycles;"
$fnew    = Q "SELECT COUNT(*) FROM fhq_control.sandbox_runs WHERE wall_seconds >= 1 AND created_at >= NOW() - INTERVAL '24 hours';"
$dbclock = Q "SELECT to_char(NOW() AT TIME ZONE 'Europe/Oslo','YYYY-MM-DD HH24:MI:SS');"

# --- Skriv sammendrag ---
$reachable = -not ("$health $dbclock" -match 'authentication failed|could not connect|error')
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# STIG-HOST helsevakt - $oslo (verts-klokke)")
$lines.Add("")
$lines.Add("- DB-klokke (Oslo): " + ($dbclock -join ''))
$lines.Add("- DB naadd: " + $(if ($reachable) {'JA'} else {'NEI - SJEKK PGPASSWORD/CONTAINER'}))
$lines.Add("")
$lines.Add("## Kjoeringer siste 15 min")
if ($health) { foreach ($h in $health) { if ($h.Trim()) { $lines.Add("- " + $h) } } } else { $lines.Add("- (ingen)") }
$lines.Add("")
$lines.Add("## Jobber uten en eneste suksess siste 30 min (se paa disse)")
if ($dead -and ($dead | Where-Object {$_.Trim()})) { foreach ($d in $dead) { if ($d.Trim()) { $lines.Add("- " + $d) } } } else { $lines.Add("- INGEN - alt friskt") }
$lines.Add("")
$lines.Add("## Siste feil per jobb, siste 15 min")
if ($fails -and ($fails | Where-Object {$_.Trim()})) { foreach ($f in $fails) { if ($f.Trim()) { $lines.Add("- " + $f) } } } else { $lines.Add("- INGEN") }
$lines.Add("")
$lines.Add("## Forskningsfabrikken")
$lines.Add("- Siste heartbeat (Oslo): " + ($fhb -join ''))
$lines.Add("- Reelle eksperimenter siste 24t: " + ($fnew -join ''))
$lines.Add("")
$lines.Add("_Kun lesing. Ingenting ble endret. Neste rapport om 15 min._")

[System.IO.File]::WriteAllLines($out, $lines, [System.Text.Encoding]::UTF8)

# --- En linje til skjermen ---
$ok  = ($health | Where-Object {$_ -match '^SUCCESS:'}) -replace 'SUCCESS:',''
$nok = ($health | Where-Object {$_ -match '^FAILED:'})  -replace 'FAILED:',''
$deadN = @($dead | Where-Object {$_.Trim()}).Count
Write-Host ("STIG-HOST $oslo  |  OK=$ok FAILED=$nok  |  doede jobber(30m)=$deadN  |  fabrikk siste 24t=" + ($fnew -join '') + "  |  rapport: $out")
