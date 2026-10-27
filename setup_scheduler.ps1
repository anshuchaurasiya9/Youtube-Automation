# Script to configure YouTube Daily Automation in Windows Task Scheduler properly
$pythonExe = "C:\Python313\python.exe"
$workingDir = "C:\Users\anshu\OneDrive\Desktop\Yt Automation"

$action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument "main.py" `
    -WorkingDirectory $workingDir

$trigger = New-ScheduledTaskTrigger -Daily -At "09:00AM"

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask `
    -TaskName "YouTubeDailyAutomation" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Force

Write-Host "Scheduled task YouTubeDailyAutomation registered successfully!"
Get-ScheduledTask -TaskName "YouTubeDailyAutomation" | Select-Object TaskName, State, @{N='NextRun';E={($_ | Get-ScheduledTaskInfo).NextRunTime}}
