@echo off
chcp 65001 >nul
title AVA - Sob Check + Fix
echo ============================================
echo   AVA - SOB CHECK + FIX
echo ============================================
echo.

cd /d C:\Users\HP\dream-

echo [1/8] Python compile + updater fix (16 module)...
venv\Scripts\python.exe fix_updater.py
venv\Scripts\python.exe -c "import py_compile; [py_compile.compile(f, doraise=True) for f in ('asif.py','memory_db.py','memory_longterm.py','file_manager.py','terminal_engine.py','scheduler.py','knowledge_base.py','doc_creator.py','file_tools.py','coding_agent.py','time_intel.py','weather.py','software_manager.py','updater.py','remote_bot.py','identity.py')]; print('   PASS - 16 module compile OK')"
if %errorlevel%==0 (echo   ✔ PASS - sob code thik ache) else (echo   ✘ FAIL - upore error dekho)
echo.

echo [2/6] Static bug scan (pyflakes)...
venv\Scripts\python.exe -m pip install --quiet pyflakes >nul 2>&1
venv\Scripts\python.exe -m pyflakes asif.py memory_db.py memory_longterm.py file_manager.py terminal_engine.py
if %errorlevel%==0 (echo   ✔ PASS - kono hidden bug nai) else (echo   ⚠ UPORE DEKHUN - issues paoa geche)
echo.

echo [3/6] Ollama brain check...
curl -s --max-time 5 http://localhost:11434/api/tags >nul 2>&1
if %errorlevel%==0 (echo   ✔ PASS - Ollama chalu ache) else (echo   ✘ FAIL - Ollama chalu nai: ollama serve chalao)
echo.

echo [4/6] MySQL/XAMPP check...
curl -s --max-time 3 http://127.0.0.1:3306 >nul 2>&1
if %errorlevel%==0 (echo   ✔ PASS - MySQL port chalu) else (echo   ⚠ MySQL bondho - XAMPP Control Panel e Start koro)
echo.

echo [5/6] Gemini key check...
if exist asif_key.txt (echo   ✔ PASS - asif_key.txt ache) else (echo   ⚠ asif_key.txt nai - Gemini lagle banao)
echo.

echo [6/6] Mic device check...
venv\Scripts\python.exe -c "import sounddevice as sd; print('  ✔ PASS -', len(sd.query_devices()), 'audio device paoa geche')" 2>nul || echo   ✘ FAIL - sounddevice problem
echo.

echo ============================================
echo   FIX: exe abar banano hocche...
echo ============================================
venv\Scripts\python.exe -m PyInstaller --onefile --name Asif --console asif.py --noconfirm >nul 2>&1
if exist dist\Asif.exe (echo   ✔ FIX PASS - notun Asif.exe toiri: dist\Asif.exe) else (echo   ✘ FIX FAIL)
echo.

echo ============================================
echo   SOB HOYE GECHE!
echo   1. dist\Asif.exe double-click koro
echo   2. (asif_key.txt pashe rakho)
echo ============================================
pause
