Write-Output "=== AVA/Asif procs ==="
Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'Asif*.exe' -or $_.Name -like 'python.exe' } | ForEach-Object {
    $cl = ""
    if ($_.CommandLine) { $cl = $_.CommandLine.Substring(0, [Math]::Min(100, $_.CommandLine.Length)) }
    Write-Output ("PID " + $_.ProcessId + " | " + $_.Name + " | " + $cl)
}
