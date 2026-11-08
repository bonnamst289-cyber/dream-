@echo off
chcp 65001 >nul
title AVA Remote Setup - token file fixer
cd /d C:\Users\HP\dream-
echo ============================================================
echo   TOKEN FILE DIAGNOSIS
echo ============================================================
echo.
echo   [1] my_token.txt ache kina:
if exist my_token.txt (echo       ✔ PAOA GECHE) else (echo       ✘ NAI)
echo   [2] my_token.txt.txt ache? (Notaper double-extension bug):
if exist my_token.txt.txt (
    echo       ✔ PAOA GECHE! - ekhon fix korchi...
    ren my_token.txt.txt my_token.txt
    echo       FIXED → my_token.txt
) else (echo       nai (ok))
echo.
echo   [3] File-er bhitore ki ache (prothom 12 harf):
if exist my_token.txt (
    venv\Scripts\python.exe -c "t=open('my_token.txt',encoding='utf-8-sig').read().strip(); print('      ', t[:6]+'...'+t[-4:] if len(t)>12 else '(khub choto/empty!)'); print('       length:', len(t))"
)
echo.
echo   [4] SAVE kora hoyeche? (my_token.txt banacchi jodi nai):
if not exist my_token.txt (
    echo       Notepad-e giye TOKEN paste korun, tarpor:
    echo       Save as → File name: "my_token.txt" (QUOTE SOHO!)
    echo       Location: C:\Users\HP\dream-\
    echo       ABAR EI FILE CHALAN
) else (
    venv\Scripts\python.exe -c "import remote_bot; t=open('my_token.txt',encoding='utf-8-sig').read().strip(); remote_bot.save_token(t); print('       ✔ TOKEN SAVE HOLO - ekhon AVA chalao!')"
)
echo.
echo ============================================================
echo   Test: phone theke bot-e /start pathan
echo   Pairing code asif screen-e dekhabe
echo ============================================================
pause
