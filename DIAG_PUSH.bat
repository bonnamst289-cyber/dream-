@echo off
chcp 65001 >nul
title AVA Push Diagnosis — log-file e sob lekha hobe
cd /d C:\Users\HP\dream-
set LOG=C:\Users\HP\dream-\push_result.txt
echo === AVA PUSH DIAGNOSIS %date% %time% === > "%LOG%"

set GIT=C:\Program Files\Git\cmd\git.exe
if not exist "%GIT%" set GIT=C:\Program Files\Git\bin\git.exe
if not exist "%GIT%" echo [0] GIT NAI! Git for Windows install koro >> "%LOG%" & type "%LOG%" & pause & exit

echo [1] Golon file jachai >> "%LOG%"
for %%F in (asif_key.txt ava_db_credentials.bin release_signing.key my_token.txt maytoken.txt ava_remote_token.json ava_memory.json asif_memory.json ava_identity.json) do (
    "%GIT%" check-ignore "%%F" >nul 2>&1 && echo [SAFE] %%F >> "%LOG%" || echo [DANGER!] %%F ignored na >> "%LOG%"
)

echo [2] Status >> "%LOG%"
"%GIT%" status --short >> "%LOG%" 2>&1
echo [3] Remote >> "%LOG%"
"%GIT%" remote -v >> "%LOG%" 2>&1
echo [4] Commit >> "%LOG%"
"%GIT%" add -A >> "%LOG%" 2>&1
"%GIT%" -c user.name="AVA" -c user.email="ava@avaitsolution.local" commit -m "AVA Universal AI full source" >> "%LOG%" 2>&1
echo [5] PUSH >> "%LOG%"
"%GIT%" push -u origin main >> "%LOG%" 2>&1
echo [PUSH EXIT CODE: %errorlevel%] >> "%LOG%"
echo [6] Tag+release push >> "%LOG%"
"%GIT%" tag v1.0.1 >> "%LOG%" 2>&1
"%GIT%" push origin v1.0.1 >> "%LOG%" 2>&1
echo [TAG EXIT CODE: %errorlevel%] >> "%LOG%"

echo.
echo ==================================================
echo   SOB HOYE GECHE!
echo   EKHON AVA-TE SHUDHU LIKHUN: "poron"
echo   (ami log-file nijei porhe thik korbo)
echo ==================================================
pause
