# Check all FHQ tasks for Unicode path issues
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Checking ALL FHQ Tasks for Unicode Issues" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$shortPath = "RJANSK~1"
$badCount = 0
$goodCount = 0

# Get all tasks with FHQ in the name (root level)
$rootTasks = Get-ScheduledTask -TaskPath "\" | Where-Object TaskName -like "*FHQ*"

# Get tasks in \FHQ\ folder
$folderTasks = Get-ScheduledTask -TaskPath "\FHQ\" -ErrorAction SilentlyContinue

$allTasks = @()
if ($rootTasks) { $allTasks += $rootTasks }
if ($folderTasks) { $allTasks += $folderTasks }

foreach ($task in $allTasks) {
    $execute = $task.Actions.Execute
    $taskPath = $task.TaskPath
    $fullName = "$taskPath$($task.TaskName)"

    # Check if it uses Python
    $usesPython = $execute -like "*python*"

    if ($usesPython) {
        $hasShortPath = $execute -like "*$shortPath*"
        $hasUnicode = $execute -like "*rjan*" -or $execute -match "[^\x00-\x7F]"

        if ($hasShortPath) {
            Write-Host "$fullName" -ForegroundColor Green
            Write-Host "  OK: $execute"
            $goodCount++
        } else {
            Write-Host "$fullName" -ForegroundColor Red
            Write-Host "  BAD: $execute"
            $badCount++
        }
    } else {
        Write-Host "$fullName" -ForegroundColor Gray
        Write-Host "  (not Python): $execute"
    }
    Write-Host ""
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Python tasks with correct path: $goodCount" -ForegroundColor Green
Write-Host "Python tasks with BAD path: $badCount" -ForegroundColor $(if ($badCount -eq 0) { "Green" } else { "Red" })

if ($badCount -gt 0) {
    Write-Host ""
    Write-Host "Tasks needing fix:" -ForegroundColor Yellow
    foreach ($task in $allTasks) {
        $execute = $task.Actions.Execute
        $usesPython = $execute -like "*python*"
        $hasShortPath = $execute -like "*$shortPath*"

        if ($usesPython -and -not $hasShortPath) {
            Write-Host "  - $($task.TaskPath)$($task.TaskName)"
        }
    }
}
