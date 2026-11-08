@echo off
chcp 65001 >nul
title AVA - GitHub Push (ek-click)
cd /d C:\Users\HP\dream-

set GIT=C:\Program Files\Git\cmd\git.exe
if not exist "%GIT%" set GIT=C:\Program Files\Git\bin\git.exe
if not exist "%GIT%" (
    echo   Git.exe paoa jaini! Git Bash theke korun.
    pause & exit
)
echo   Git paoa geche: %GIT%
echo.

echo [১/৪] Golon file raksha jachai...
for %%F in (asif_key.txt ava_db_credentials.bin release_signing.key my_token.txt maytoken.txt ava_remote_token.json ava_memory.json asif_memory.json) do (
    "%GIT%" check-ignore "%%F" >nul 2>&1 && echo   ✔ surakkhito: %%F || echo   ⚠ SAVDHAN: %%F ignored na — THAMAN!
)
echo.

echo [২/৪] Commit...
"%GIT%" add -A
"%GIT%" -c user.name="AVA" -c user.email="ava@avaitsolution.local" commit -m "AVA Universal AI — full source + CI/CD" -q
if %errorlevel%==0 (echo   ✔ commit holo) else (echo   (notun kichu nai ba age commit chilo))
echo.

echo [৩/৪] Remote set...
"%GIT%" remote add origin https://github.com/bonnamst289-cyber/dream-.git 2>nul
"%GIT%" remote -v
echo.

echo [৪/৪] PUSH... (browser-e GITHUB LOGIN popup asbe — nijhe login korun!)
"%GIT%" push -u origin main
if %errorlevel%==0 (
    echo.
    echo   ============================================
    echo   ✔✔ PUSH SOFFOL! github.com/bonnamst289-cyber/dream-
    echo   ERPOR:
    echo   1. repo → Settings → Secrets → RELEASE_SIGNING_KEY
    echo      (release_signing.key file-er bhitorek string)
    echo   2. CMD-e: git tag v1.0.1 ^&^& git push origin v1.0.1
    echo   3. Actions release banabe → phone-e telegram live!
    echo   ============================================
) else (
    echo   ✘ PUSH FAIL — upore eror ta AVA-te paste korun
)
echo.
pause
