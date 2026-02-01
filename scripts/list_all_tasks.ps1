# List all FHQ and IOS related tasks
Get-ScheduledTask | Where-Object { $_.TaskName -like '*FHQ*' -or $_.TaskName -like '*IOS*' } |
    Select-Object TaskPath, TaskName, State, @{N='Execute';E={$_.Actions.Execute}} |
    Format-Table -AutoSize
