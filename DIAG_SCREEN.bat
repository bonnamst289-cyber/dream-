@echo off
chcp 65001 >nul
title AVA Diagnosis - Screen dekha test
cd /d C:\Users\HP\dream-
echo ============================================================
echo   AVA DIAGNOSIS: Gemini + Screen-dorshon test
echo ============================================================
echo.
echo [TEST 1] Gemini brain connection...
venv\Scripts\python.exe -c "import asif; r = asif._ask_gemini(); print(); print('>>> JODI BANGLA UTTAR ASHE = GEMINI THIK ACHE <<<'); print('>>> UTTAR:', r)"
echo.
echo ============================================================
echo [TEST 2] Screen dekha (screenshot + AI vision)...
venv\Scripts\python.exe -c "import asif; r = asif._cmd_screen(); print(); print('>>> SCREEN-DEKHA FOLAFOL:'); print(r)"
echo.
echo ============================================================
echo   UPORE DEKHA LINE GULO (bisheshe >>> ar ⚠️ line)
echo   AVA-TE COPY KORE DIN — oi tahanei asol karon lekha ache!
echo ============================================================
pause
