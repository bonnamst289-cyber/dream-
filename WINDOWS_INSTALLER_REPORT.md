# WINDOWS_INSTALLER_REPORT.md
Generated: 2026-11-08

## Overall: PARTIAL

- **PASS** — আপডেটার স্ক্রিপ্ট (ava_update_apply.bat): AVA graceful close → rollback backup → replace → size-verify → relaunch; fail → auto-rollback + log
- **PASS** — per-user install: কোনো admin লাগে না (সব C:\Users\HP\dream-\ ভেতরে)
- **PASS** — চলমান EXE overwrite নয় (আগে বন্ধ করা হয়)
- **PASS** — update log: ava_update_log.txt (UPDATED OK / ROLLBACK রেকর্ড)
- **NOT TESTED** — বাস্তব full-cycle ইনস্টল (চলমান AVA বন্ধ করার অনুমতি ব্যবহারকারীর; ব্যবহারকারী চালাবে)
- **MISSING** — ক্লাসিক installer (Inno Setup wizard), অ্যাপ আইকন, uninstaller — পরবর্তী ধাপ
