Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*remote_bot*' } | ForEach-Object {
    Write-Output ("PID " + $_.ProcessId + " | NAME: " + $_.Name)
}
