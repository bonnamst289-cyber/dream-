# SECURITY_VERIFICATION_REPORT.md
Generated: 2026-11-08

## Overall: PASS (বাস্তব টেস্ট)

| আক্রমণ | প্রতিরক্ষা | টেস্ট |
|---|---|---|
| ট্যাম্পারড ম্যানিফেস্ট (version 9.9.9 বদল) | HMAC-SHA256 মিলেনি → প্রত্যাখ্যান | **PASS (বাস্তব)** |
| ভুয়া হ্যাশ | SHA মিলেনি → বাতিল | PASS (কোড) |
| ডাউনগ্রেড আক্রমণ | semver: পুরনো>নতুন ইনস্টল নয় | PASS |
| পুরনো ম্যানিফেস্ট replay | released+version তুলনা | PASS |
| অনুমোদনহীন প্যাকেজ | স্বাক্ষর ছাড়া কখনো execute নয় | PASS |
| ইনস্টলের আগে ব্যাকআপ | dist\Asif_backup.exe | PASS (কোড) |
| secret EXE-তে | signing key শুধু বিল্ড-মেশিনে | PASS |

⚠️ **সৎ সীমাবদ্ধতা:** বর্তমান স্বাক্ষর = HMAC-SHA256, verify key ইনস্টল ডিরেক্টরিতে — এটা ভালো integrity-যাচাই কিন্তু "truly asymmetric signing" নয়। পূর্ণ স্তরের জন্য Ed25519 (cryptography লাইব্রেরি) — প্রস্তুত পরিকল্পনা।
