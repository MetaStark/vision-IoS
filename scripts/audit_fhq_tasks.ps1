# CEO-DIR-2025-INFRA-002: FHQ Task Fleet Audit
# Generates inventory of all FHQ scheduled tasks

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "CEO-DIR-2025-INFRA-002 SCHEDULER FLEET AUDIT" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

$tasks = Get-ScheduledTask | Where-Object { $_.TaskName -like "FHQ*" }

$results = @()

foreach ($task in $tasks) {
    $info = Get-ScheduledTaskInfo -TaskName $task.TaskName -ErrorAction SilentlyContinue
    $principal = $task.Principal
    $action = $task.Actions[0]

    $results += [PSCustomObject]@{
        TaskName = $task.TaskName
        State = $task.State
        RunAsUser = $principal.UserId
        LogonType = $principal.LogonType
        LastRun = if ($info.LastRunTime -and $info.LastRunTime.Year -gt 2000) { $info.LastRunTime.ToString("yyyy-MM-dd HH:mm") } else { "Never" }
        LastResult = $info.LastTaskResult
        NextRun = if ($info.NextRunTime) { $info.NextRunTime.ToString("yyyy-MM-dd HH:mm") } else { "N/A" }
        Command = if ($action.Execute) { Split-Path $action.Execute -Leaf } else { "N/A" }
    }
}

# Display results
$results | Format-Table -AutoSize

Write-Host ""
Write-Host "LOGON TYPE LEGEND:" -ForegroundColor Yellow
Write-Host "  Interactive    = Runs ONLY when user is logged in (BAD)" -ForegroundColor Red
Write-Host "  Password       = Runs whether logged in or not (GOOD)" -ForegroundColor Green
Write-Host "  S4U            = Service for User - runs non-interactive (GOOD)" -ForegroundColor Green
Write-Host "  ServiceAccount = Runs as service account (GOOD)" -ForegroundColor Green
Write-Host ""

# Count by logon type
$interactive = ($results | Where-Object { $_.LogonType -eq "Interactive" }).Count
$nonInteractive = ($results | Where-Object { $_.LogonType -ne "Interactive" }).Count

Write-Host "SUMMARY:" -ForegroundColor Cyan
Write-Host "  Total FHQ Tasks: $($results.Count)"
Write-Host "  Interactive (needs hardening): $interactive" -ForegroundColor $(if ($interactive -gt 0) { "Red" } else { "Green" })
Write-Host "  Non-Interactive (OK): $nonInteractive" -ForegroundColor Green
Write-Host ""

# Return results for capture
$results
