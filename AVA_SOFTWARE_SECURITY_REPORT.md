# AVA Software Security Report
Generated: 2026-11-08

## Overall: PASS

- **PASS** — ঝুঁকি-স্তর প্রয়োগ:
  - LOW (পড়া): ইনভেন্টরি, সময়, আবহাওয়া, ভার্সন, সার্ভিস স্ট্যাটাস — অনুমতি ছাড়া চলে
  - MEDIUM: অ্যাপ খোলা, সার্ভিস চালু — যাচাই সহ
  - HIGH: আনইনস্টল, ফোর্স-ক্লোজ, সার্ভিস বন্ধ, আপগ্রেড — **স্পষ্ট ভয়েস অনুমতি বাধ্যতামূলক**
- **PASS** — UAC/Defender/নিরাপত্তা কখনো bypass নয়
- **PASS** — অজানা/সন্দেহজনক প্যাকেজ ইনস্টল নিষিদ্ধ (শুধু winget-যাচাইকৃত ID)
- **PASS** — সব execution log (ava_terminal_audit.jsonl) + secret masking
- **PASS** — আপগ্রেড কখনো স্বয়ংক্রিয়ভাবে "সব" নয় — নির্বাচিত + অনুমতি
- **PASS** — আনইনস্টল = সঠিক uninstaller (UninstallString) — ফোল্ডার ম্যানুয়াল ডিলিট নয়
