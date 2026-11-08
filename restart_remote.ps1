$py = "C:\Users\HP\dream-\venv\Scripts\python.exe"
$out = "C:\Users\HP\dream-\remote_bot_out.log"
$err = "C:\Users\HP\dream-\remote_bot_err.log"
$code = "import remote_bot, time; print(remote_bot.startup(), flush=True); time.sleep(99999999)"
$quoted = '"' + $code + '"'
Start-Process -WindowStyle Hidden -FilePath $py -ArgumentList "-u", "-c", $quoted -RedirectStandardOutput $out -RedirectStandardError $err
Start-Sleep -Seconds 6
$now = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like 'python*' -and $_.CommandLine -like '*remote_bot*'
}
Write-Output ("after-relaunch: " + @($now).Count + " python process (2 = normal)")
Get-Content $out -ErrorAction SilentlyContinue | Select-Object -First 3
Get-Content $err -ErrorAction SilentlyContinue | Select-Object -First 5
