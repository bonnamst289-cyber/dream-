# AVA Master Architecture (বাস্তব কাঠামো — অনুমান নয়)
Updated: 2026-11-08

## এন্ট্রি পয়েন্ট
`asif.py → main()` — টার্মিনাল ইন্টারফেস + ভয়েস লুপ + intent router

## Shared Services (সব মডিউল এগুলো ব্যবহার করে — আলাদা আলাদা নয়)
| সার্ভিস | ফাইল | ভূমিকা |
|---|---|---|
| Core AI Brain | asif.py (converse/think) | Ollama স্ট্রিমিং + Gemini, context-inject |
| Intent Router | asif.py (try_command) | ১২+ স্তরের রাউটার + ফাজি লেয়ার |
| Context Manager | memory_longterm.py | sessions/messages/summaries/compact-context |
| Long-term Memory | memory_db.py + memory_longterm.py | MySQL ১৩ টেবিল, learn-once, DPAPI creds |
| Voice Engine | asif.py (listen/speak/converse) | STT(২ ফলব্যাক)+TTS(৩ স্তর)+streaming+interrupt |
| Action Registry | file_manager/terminal_engine/software_manager | validated actions only |
| Permission Engine | _confirm + terminal classify + fm._is_allowed | HIGH risk → ভয়েস অনুমতি |
| Task Engine | terminal_engine.run_task | plan→safety→execute→verify→retry→report |
| Notification | scheduler._toast + speak | Windows balloon + ভয়েস |
| Audit Logging | terminal_engine.audit + DB logs | JSONL + MySQL |
| DB Layer | memory_db.get_connection | pymysql, parameterized, utf8mb4 |
| Provider Layer | asif._ask_gemini/_ollama | auto-model-pick, timeouts, thinking off |

## ২০ মডিউল → বাস্তবায়ন ম্যাপ (বিস্তারিত AVA_FEATURE_STATUS.md-তে)

| # | মডিউল | ফাইল | অবস্থা |
|---|---|---|---|
| ০১ | Human-like Conversation | asif.py + memory_longterm | ✅ PASS (টেস্টেড) |
| ০২ | বাংলা/English/Banglish | asif.py (fuzzy+STT-fix) | ✅ PASS |
| ০৩ | Voice Assistant | asif.py | ✅ PASS (লাইভ মাইক টেস্ট ব্যবহারকারীর হাতে) |
| ০৪ | Long-term Memory | memory_db + memory_longterm | ✅ PASS (রিস্টার্ট টেস্ট) |
| ০৫ | Screen Vision | asif.py (_cmd_screen) | ✅ PASS (বাস্তব — স্ক্রিন পড়েছে) |
| ০৬ | File Manager | file_manager.py | ✅ PASS (বাস্তব) |
| ০৭ | Software Manager | software_manager.py | ✅ কোড+ইনভেন্টরি; winget-install NOT TESTED |
| ০৮ | Coding Agent | terminal_engine (planner+exec+verify) | ⚠️ PARTIAL |
| ০৯ | Auto Debugging | terminal_engine (_llm_fix) | ⚠️ PARTIAL |
| ১০ | Database Manager | memory_db (read-only SELECT সমর্থিত) | ⚠️ PARTIAL (পূর্ণ SQL runner নেই) |
| ১১ | API Testing | — | ❌ MISSING |
| ১২ | PC Health Monitor | — | ❌ MISSING (এই আপডেটে নয়) |
| ১৩ | Self Diagnosis | system_audit.py + self-tests | ✅ PASS |
| ১৪ | Weather & Time | weather.py + time_intel.py | ✅ কোড+রাউটার (লাইভ NOT TESTED) |
| ১৫ | Daily Planner | memory_longterm + scheduler | ✅ PASS (রিমাইন্ডার বাস্তব ফায়ার) |
| ১৬ | Document Creator | doc_creator.py (নতুন) | ✅ TXT/MD/CSV/HTML গ্যারান্টিড; DOCX/XLSX/PDF লাইব্রেরি-নির্ভর |
| ১৭ | Workflow Builder | terminal_engine chains + command_memories | ⚠️ PARTIAL |
| ১৮ | Multi-Agent | terminal_engine planner = single-agent | ❌ MISSING (orchestrator নেই) |
| ১৯ | Plugin System | — | ❌ MISSING |
| ২০ | Remote Control | — | ❌ MISSING (নিরাপত্তা-সংবেদনশীল, সাবধান পরিকল্পনা দরকার) |
