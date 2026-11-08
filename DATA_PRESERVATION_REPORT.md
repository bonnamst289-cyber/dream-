# DATA_PRESERVATION_REPORT.md
Generated: 2026-11-08

## Overall: PASS (নকশা + বাস্তব নিশ্চিত)

| ডেটা | কোথায় | আপডেটে অক্ষত? |
|---|---|---|
| MySQL DB (১৩ টেবিল) | XAMPP (বাইরে) | ✔️ স্পর্শ হয় না |
| কথোপকথন/স্মৃতি | MySQL | ✔️ |
| লোকাল মেমরি | asif_memory.json | ✔️ |
| Identity | ava_identity.json + DB | ✔️ |
| Gemini key | asif_key.txt | ✔️ |
| MySQL creds | ava_db_credentials.bin (DPAPI) | ✔️ |
| Telegram pairing | ava_remote_pair.json | ✔️ |
| রিমাইন্ডার | ava_reminders.json | ✔️ |
| নলেজ বেইজ | ava_knowledge.json | ✔️ |
| ব্যবহারকারীর ডেস্কটপ ফাইল | Desktop | ✔️ |

- **PASS** — updater শুধু dist\Asif.exe replace করে; অন্য কোনো ফাইল স্পর্শ নেই (bat কোডে যাচাইযোগ্য)
- **PASS** — DB migration: IF NOT EXISTS + backup — destructive reset নেই
