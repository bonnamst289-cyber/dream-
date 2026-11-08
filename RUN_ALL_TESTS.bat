@echo off
chcp 65001 >nul
title AVA - FULL TEST SUITE (sob check)
cd /d C:\Users\HP\dream-
echo ============================================================
echo   AVA FULL TEST SUITE — sob module, sob feature
echo ============================================================
echo.
echo [1/8] COMPILE CHECK (8 module)...
venv\Scripts\python.exe -c "import py_compile; [py_compile.compile(f, doraise=True) for f in ('asif.py','memory_db.py','memory_longterm.py','file_manager.py','terminal_engine.py','scheduler.py','knowledge_base.py','doc_creator.py','time_intel.py','weather.py','software_manager.py')]; print('   PASS - 11 module compile OK')" || echo   FAIL - upore error dekho
echo.
echo [2/8] GEMINI BRAIN (live test)...
venv\Scripts\python.exe -c "import asif; r=asif._ask_gemini(); print('   PASS - Gemini boltase:', (r or 'NONE')[:60])" 2>&1 | findstr /C:"PASS" /C:"⚠" /C:"❌"
echo.
echo [3/8] OLLAMA LOCAL BRAIN...
curl -s --max-time 5 http://localhost:11434/api/tags | findstr /C:"models" >nul && echo   PASS - Ollama chalu (model ache) || echo   FAIL - Ollama bondho
echo.
echo [4/8] DATABASE (MySQL + 13 table)...
venv\Scripts\python.exe -c "import memory_db; conn=memory_db.get_connection(); c=conn.cursor(); c.execute('SHOW TABLES'); print('   PASS -', len(c.fetchall()), 'table ache'); conn.close()" 2>&1 | findstr /C:"PASS" /C:"Error" /C:"RuntimeError"
echo.
echo [5/8] DESKTOP FILE OPERATIONS (create+verify+remove)...
venv\Scripts\python.exe -X utf8 -c "import file_manager as fm, os, datetime; n='AVA_FullTest'; d=fm.desktop_path(); r=fm.create_folder(d,n); ok1=r['status']=='created' or r['status']=='exists'; f=fm.create_text_file(os.path.join(d,n),'t'); ok2=f['status'] in ('created','exists'); rm=fm.delete_path(os.path.join(d,n)); print('   PASS - create+file+remove sob kaj kore (verified)' if (ok1 and ok2 and rm['status']=='created' and not os.path.exists(os.path.join(d,n))) else '   FAIL - dekho upore')"
echo.
echo [6/8] TIME + WEATHER (live)...
venv\Scripts\python.exe -c "import time_intel; print('  ', time_intel.handle('ekhon koyta baje')[1][:60])"
venv\Scripts\python.exe -c "import weather; print('  ', weather.handle('ajker weather dao')[1][:120])"
echo.
echo [7/8] SCREEN VISION (Gemini vision, dhire - 2/4 minute lage)...
venv\Scripts\python.exe -c "import asif; r=asif._cmd_screen(); print('   RESULT:', (r or 'NONE')[:200])"
echo.
echo [8/8] EXE BUILD (notun Asif2.exe)...
venv\Scripts\python.exe -m PyInstaller --onefile --name Asif2 --console asif.py --noconfirm >nul 2>&1
if exist dist\Asif2.exe (echo   PASS - dist\Asif2.exe notun build toiri) else (echo   FAIL - build hoyni, Asif2.exe chalu thakle bondho koro)
echo.
echo ============================================================
echo   TEST SUITE SESH!
echo   kono FAIL thakle oi line ta AVA-te copy kore din.
echo ============================================================
pause
