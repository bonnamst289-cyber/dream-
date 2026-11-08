# AUTO_UPDATE_ARCHITECTURE.md
Generated: 2026-11-08

## স্থাপত্য (বাস্তবায়িত)

```
build_release.py (ডেভেলপার)                updater.py (ইনস্টল করা AVA-র ভেতরে)
├─ compile check (১৬ মডিউল)                ├─ check_for_updates(): manifest আনে
├─ conversation tests                      ├─ verify_signature(): HMAC-SHA256
├─ PyInstaller onefile build               ├─ semver তুলনা (downgrade নিষিদ্ধ)
├─ SHA-256 হিসাব                           ├─ download_package(): স্ট্রিম+resume+
├─ releases/<v>/Asif.exe + manifest.json   │   progress+cancel+staging+size+sha
│   (HMAC-SHA256 স্বাক্ষরিত)                ├─ apply_update(): অনুমতি → ava_update_apply.bat:
└─ releases/latest/ (বিতরণ)                │   close AVA → rollback backup → replace
                                           │   → size-verify → relaunch → log
Source: লোকাল ফোল্ডার বা HTTPS (pluggable)  └─ fail → auto-rollback → পুরনো ভার্সন
```

## ডেটা সংরক্ষণ
- exe আর ইউজার-ডেটা সম্পূর্ণ আলাদা: DB (MySQL বাইরে), ava_memory.json, asif_key.txt, ava_identity.json, my_token.txt — আপডেটার কোনোটা স্পর্শ করে না
- migration: memory_db.ensure_schema (IF NOT EXISTS + backup) প্রতি চালুতে

## চ্যানেল
- stable (ডিফল্ট) / beta — manifest-এ channel ফিল্ড
