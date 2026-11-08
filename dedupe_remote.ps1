$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*remote_bot*' }
$procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 2
$py = "C:\Users\HP\dream-\venv\Scripts\python.exe"
$code = "import remote_bot, time; remote_bot.startup(); time.sleep(99999999)"
$quoted = '"' + $code + '"'
Start-Process -WindowStyle Hidden -FilePath $py -ArgumentList "-c", $quoted
Start-Sleep -Seconds 3
$c1 = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*remote_bot*' }).Count
Write-Output ("3s por: " + $c1)
Start-Sleep -Seconds 10
$c2 = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*remote_bot*' }).Count
Write-Output ("13s por: " + $c2)
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*remote_bot*' } | ForEach-Object {
    Write-Output ("PID " + $_.ProcessId + " parent? ")
    Write-Output ("  ParentPID: " + $_.ParentProcessId)
}
