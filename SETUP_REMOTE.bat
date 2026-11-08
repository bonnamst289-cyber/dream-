@echo off
chcp 65001 >nul
title AVA Remote Setup (Telegram)
cd /d C:\Users\HP\dream-
echo ============================================================
echo   AVA REMOTE SETUP (Telegram) — SOHOJ PADDHOTI
echo ============================================================
echo.
echo   NOTUN UPAI: Token type korte hobe na!
echo   1. Notepad khulun → BotFather-er TOKEN paste korun
echo   2. Save korun: C:\Users\HP\dream-\my_token.txt
echo   3. Ekhane Enter chapun — baki sob ami korbo!
echo.
if exist my_token.txt (
    echo   ✔ my_token.txt paoa geche - porche...
    venv\Scripts\python.exe -c "import remote_bot; t=open('my_token.txt',encoding='utf-8-sig').read().strip(); remote_bot.save_token(t); print('   ✔ TOKEN SAVE HOLO')"
) else if exist maytoken.txt (
    echo   ✔ maytoken.txt paoa geche - rename korchi...
    ren maytoken.txt my_token.txt
    venv\Scripts\python.exe -c "import remote_bot; t=open('my_token.txt',encoding='utf-8-sig').read().strip(); remote_bot.save_token(t); print('   ✔ TOKEN SAVE HOLO')"
) else if exist token.txt (
    echo   ✔ token.txt paoa geche - rename korchi...
    ren token.txt my_token.txt
    venv\Scripts\python.exe -c "import remote_bot; t=open('my_token.txt',encoding='utf-8-sig').read().strip(); remote_bot.save_token(t); print('   ✔ TOKEN SAVE HOLO')"
) else if exist my_token.txt.txt (
    echo   ✔ my_token.txt.txt paoa geche (Notaper double bug) - fix korchi...
    ren my_token.txt.txt my_token.txt
    venv\Scripts\python.exe -c "import remote_bot; t=open('my_token.txt',encoding='utf-8-sig').read().strip(); remote_bot.save_token(t); print('   ✔ TOKEN SAVE HOLO')"
) else (
    echo   ✘ kono token file nai! (my_token.txt / maytoken.txt / token.txt)
    echo   Notepad-e TOKEN paste kore ei folder-e save korun.
    pause
    exit
)
echo.
echo   Bot test korchi (Telegram server)...
venv\Scripts\python.exe -c "import remote_bot, requests; tk=remote_bot.token(); r=requests.get(f'https://api.telegram.org/bot{tk}/getMe', timeout=10); j=r.json(); print('   ✔ BOT VALID:', j['result']['username']) if j.get('ok') else print('   ✘ TOKEN VUL: token invalid hoye geche')"
echo.
echo   Remote bot chalu hocche...
venv\Scripts\python.exe -c "import remote_bot; print('   ', remote_bot.startup())"
venv\Scripts\python.exe -c "import remote_bot; print('   PAIRING CODE:', remote_bot.pairing_code())"
echo.
echo ============================================================
echo   EKHON PHONE-E:
echo   1. nijer BOT-ke khulun
echo   2. likhun: /start
echo   3. bot je 6-letter CODE dekhabe → /start CODE likhun
echo   4. "✔ Pairing sofol" dekhle SOBO!
echo   Test: "kemon acho" likhun → AVA reply korbe
echo ============================================================
echo.
echo   (Ei window TA KHOLA RAKHUN - eta chara bot bondho hoye jabe!)
echo   Bondho korte: Ctrl+C
venv\Scripts\python.exe -u -c "import remote_bot, time; print(remote_bot.startup(), flush=True); time.sleep(99999999)"
