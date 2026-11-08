$procs = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'Asif*.exe' -or ($_.CommandLine -like '*remote_bot*' -and $_.Name -eq 'python.exe') }
Write-Output ("age: " + @($procs).Count + " ta AVA/bot process")
$procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
Start-Process -FilePath "C:\Users\HP\dream-\dist\Asif2.exe" -WorkingDirectory "C:\Users\HP\dream-"
Start-Sleep -Seconds 6
$now = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'Asif*.exe' }
Write-Output ("ekhon: " + @($now).Count + " ta Asif2.exe (hobe 1)")
$bot = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*remote_bot*' }
Write-Output ("bot: " + @($bot).Count + " ta (hobe 1)")
