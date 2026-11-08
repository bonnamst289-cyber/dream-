Stop-Process -Name "Asif2" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "Asif3" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Set-Location "C:\Users\HP\dream-"
& "C:\Users\HP\dream-\venv\Scripts\python.exe" -m PyInstaller --onefile --name Asif2 --console asif.py --noconfirm 2>&1 | Select-Object -Last 1
Get-Item "C:\Users\HP\dream-\dist\Asif2.exe" | ForEach-Object { Write-Output ("BUILD OK: " + $_.LastWriteTime + " " + $_.Length + " bytes") }
Start-Process -FilePath "C:\Users\HP\dream-\dist\Asif2.exe" -WorkingDirectory "C:\Users\HP\dream-"
Start-Sleep -Seconds 5
Write-Output "AVA relaunch holo (notun version, bot+scheduler soho)"
