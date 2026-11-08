# AVA Master Project Analysis
Generated: 2026-11-08 (বাস্তব কোড-পরিদর্শন ভিত্তিক — অনুমান নয়)

## ১. প্রজেক্ট কাঠামো (আসল)

```
C:\Users\HP\dream-\          ← এন্ট্রি পয়েন্ট: asif.py → main()
├── asif.py               (~1400 লাইন) — মূল অ্যাপ: STT → Intent Router → Brain → TTS
├── memory_db.py          (~790)     — MySQL (ava_universal_ai): command memory, CRUD, DPAPI creds
├── memory_longterm.py    (~430)     — sessions/messages/summaries/projects/tasks/suggestions
├── memory_selftest.py    (~150)     — long-term memory গ্রহণযোগ্যতা টেস্ট + ৫ রিপোর্ট
├── file_manager.py       (~350)     — Desktop API, validated file ops + self_test
├── terminal_engine.py    (~700)     — multi-shell, planner, security layer, audit log + self_test
├── system_audit.py       (~250)     — পূর্ণ সিস্টেম অডিট রানার (১০ রিপোর্ট)
├── dist\Asif2.exe                   — PyInstaller onefile build (যাচাইকৃত)
├── asif_key.txt                      — Gemini key (DPAPI নয়; ফাইল-ভিত্তিক, মান লগে যায় না)
├── ava_db_credentials.bin            — MySQL creds (Windows DPAPI এনক্রিপ্টেড)
├── asif_memory.json                  — লোকাল ফলব্যাক মেমরি (DB বন্ধ থাকলে)
├── ava_terminal_audit.jsonl          — টার্মিনাল execution audit log
├── backups\                          — mysqldump backups (migration-এর আগে স্বয়ংক্রিয়)
└── venv\                             — Python 3.15 পরিবেশ
```

## ২. প্রযুক্তি (যা আসলে ব্যবহৃত)

- **ভাষা:** Python 3.15 (Windows)
- **ভয়েস IN:** sounddevice (mic capture) + Google Speech (bn-BD/bn-IN) + flac-ছাড়া WAV-direct fallback
- **ভয়েস OUT:** Edge TTS (bn-BD neural) → gTTS fallback → Windows SAPI (offline fallback)
- **AI:** Gemini (gemini-3.8-flash, অটো-মডেল-পিক, thinkingBudget 0) প্রাইমারি; Ollama লোকাল (llama3.2:3b/1b, gemma2:2b) ফলব্যাক/স্ট্রিমিং
- **DB:** XAMPP MariaDB, pymysql, utf8mb4, DPAPI-এনক্রিপ্টেড creds, migration-safe, mysqldump backup
- **Windows:** ctypes (user32 mouse/keys), PowerShell (SendKeys, Shell COM, WMI brightness), taskkill, winmm (audio play)
- **বিল্ড:** PyInstaller onefile

## ৩. স্থাপত্য (Architecture)

```
মাইক → VAD(silence 0.8s) → STT(Google/fallback) → Intent Router:
  ১. memory_db.try_memory      (মেমরি মিললে AI কল ছাড়াই, যাচাইকৃত action)
  ২. longterm router           (টাস্ক/প্রজেক্ট/হিস্ট্রি/সাজেশন)
  ৩. memory admin / মোড টগল
  ৪. _pc_router                (start menu/উইন্ডো/লক)
  ৫. _mouse_kb_router          (মাউস/কিবোর্ড/টাইপ)
  ৬. _yt_router                (গান play/pause/close)
  ৭. _vol_bright_router        (ভলিউম/ব্রাইটনেস)
  ৮. _file_action_router       (ফোল্ডার/ফাইল — লোকাল, AI কল ছাড়া)
  ৯. _fuzzy_intent_router      (যেভাবেই বলা + STT-ভুল সংশোধন + clarification)
 ১০. _wants_terminal_task      → terminal_engine (plan→safety→execute→verify→report)
 ১১. চেইন ("তারপর")            → ধাপে ধাপে
 ১২. Brain: converse() (Ollama স্ট্রিমিং + long-term context) / think() (Gemini)
→ Streaming TTS (বাক্য-স্তরে) → Speaker → শেখার প্রস্তাব (অনুমতি সহ)
```

## ৪. বাস্তবে যাচাইকৃত কাজের ফিচার (এই সেশনের টেস্ট-প্রমাণ সহ)

- Gemini ব্রেন বাংলা উত্তর (বাস্তব কল সফল), স্ক্রিন-দর্শন (বাস্তব — স্ক্রিন পড়ে বর্ণনা)
- Ollama ৩ মডেল, latency মাপা (warm ~৮s/৩b)
- STT বাংলা (ব্যবহারকারী লগে সফল), ২-ভাষা fallback
- ডেস্কটপে ফোল্ডার তৈরি/তালিকা/মুছা (বাস্তব যাচাই: created→verified→removed)
- ফোল্ডারে ফাইল তৈরি (বাস্তব: নোট ফাইল.txt)
- Notepad খোলা + টাইপ (বাস্তব: "Hello from AVA!" টাইপ হয়েছে)
- MySQL ১৩ টেবিল + CRUD + restart-persistence + matching ৬/৬ PASS
- টার্মিনাল ৪ শেল শনাক্ত + echo execute + security classification ৫/৫
- ভলিউম কি + ব্রাইটনেস পড়া (২৯% বাস্তবে পড়া হয়েছে)

## ৫. ভাঙা/অসম্পূর্ণ/অনুপস্থিত (সৎ)

- **GUI (Hacker UI): নেই** — বর্তমানে টার্মিনাল ইন্টারফেস (console)
- **Scheduler/Reminder: ছিল না** — এই আপডেটে যোগ হচ্ছে (scheduler.py)
- **Knowledge Base: ছিল না** — এই আপডেটে যোগ হচ্ছে (knowledge_base.py; TXT/MD/code — PDF-এর জন্য pypdf দরকার)
- **Browser automation: আংশিক** — ওপেন/সার্চ/টাইপ/ক্লিক; ফর্ম-ফিল নেই
- **Whisper STT: ব্যবহৃত নয়** — Google ব্যবহৃত (CPU-ফ্রেন্ডলি, বাংলায় ভালো); whisper.cpp মূল্যায়ন বাকি
- **Installer: নেই** — onefile EXE আছে; installer/icon বাকি
- **লাইভ ভয়েস টেস্ট: NOT TESTED** — এই পরিবেশে মাইক ব্লকড (ব্যবহারকারী লগে সফল)

## ৬. পরিকল্পনা (এই আপডেটে বাস্তবায়িত)

1. scheduler.py — রিমাইন্ডার + Windows নোটিফিকেশন ✔
2. knowledge_base.py — ডকুমেন্ট ইনডেক্স/সার্চ/উদ্ধৃতি ✔
3. রাউটারে সংযোগ + কম্পাইল + বিল্ড ✔
4. Feature-status ম্যাট্রিক্স রিপোর্ট ✔
