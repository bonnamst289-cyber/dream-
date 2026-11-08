@echo off
chcp 65001 >nul
cd /d C:\Users\HP\dream-
echo ============================================================
echo   GIT SAFETY CHECK + COMMIT + PUSH
echo ============================================================
echo.
echo [১] গোপন ফাইল রক্ষা যাচাই (এগুলো commit হবে না):
for %%F in (asif_key.txt ava_db_credentials.bin release_signing.key my_token.txt maytoken.txt ava_remote_token.json ava_memory.json asif_memory.json) do (
    git check-ignore "%%F" >nul 2>&1 && echo   ✔ সুরক্ষিত: %%F || echo   ⚠ সতর্ক: %%F ignored নয়!
)
echo.
echo [২] Commit হবে যেসব ফাইল (নিচে দেখুন — গোপন কিছু থাকলে থামান!):
git add -A
git status --short
echo.
echo [৩] Commit + push...
git -c user.name="AVA" -c user.email="ava@avaitsolution.local" commit -m "AVA Universal AI — full source + CI/CD pipeline" -q
if %errorlevel%==0 (echo   ✔ commit হলো) else (echo   কিছু বদলায়নি বা commit আগেই আছে)
echo.
echo [৪] Remote আছে কি না:
git remote -v
echo.
echo   যদি remote খালি থাকে:
echo   ১. github.com-এ নতুন PRIVATE repo খুলুন: ava-universal-ai
echo   ২. নিচের কমান্ডে আপনার ইউজারনেম বসিয়ে চালান:
echo      git remote add origin https://github.com/USERNAME/ava-universal-ai.git
echo      git push -u origin main
echo   ৩. ব্রাউজারে GitHub login পপআপ আসবে — নিজে লগইন করবেন
echo      (টোকেন আমার কাছে আসবে না — Git Credential Manager আপনার ব্রাউজারে!)
echo.
pause
