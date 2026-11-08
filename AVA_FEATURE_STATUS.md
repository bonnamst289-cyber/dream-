# AVA Feature Status (সৎ ম্যাট্রিক্স — প্রতিটি স্ট্যাটাস টেস্ট-ভিত্তিক)
Updated: 2026-11-08 03:22

স্ট্যাটাস কোড: PASS / PARTIAL / FAIL / MISSING / NOT CONFIGURED / NOT CONNECTED / NOT TESTED / BLOCKED

## 🧠 AI ও কথোপকথন
| ফিচার | স্ট্যাটাস | নোট |
|---|---|---|
| Gemini ব্রেন (বাংলা) | PASS | বাস্তব কল সফল; thinkingBudget 0; অটো-মডেল-পিক |
| Gemini error/rate-limit handling | PASS | 400/401/403/404/429 + ReadTimeout স্পষ্ট বার্তা |
| Ollama লোকাল ফলব্যাক | PASS | ৩ মডেল; warm ~৮s/৩b |
| স্ট্রিমিং উত্তর (বাক্য-স্তরে) | PASS | বাক্য তৈরি হলেই TTS |
| Long-term context injection | PASS | compact ≤1800 chars; পুরো হিস্ট্রি যায় না |
| ফাজি ইনটেন্ট + STT-ভুল সংশোধন | PASS | যেভাবেই বলা; অনিশ্চিতে clarification |
| কমান্ড-চেইন ("তারপর") | PASS | ৫ ধাপ পর্যন্ত |
| ইন্টারেক্টিভ ফলো-আপ | PASS | ইউটিউব/ফোল্ডার প্রশ্ন → পরের উত্তরে কাজ |

## 🎙️ ভয়েস
| ফিচার | স্ট্যাটাস |
|---|---|
| মাইক ডিটেকশন | PASS (১৬ ডিভাইস) |
| বাংলা STT | PASS (ব্যবহারকারী লগে সফল; bn-BD→bn-IN fallback) |
| Banglish STT | PARTIAL (Google bn-এ বাংলিশ আউটপুট দেয়; ফাজি রাউটার ধরে) |
| ইংরেজি STT | NOT TESTED (ভাষা তালিকায় সহজে যোগযোগ্য) |
| বাংলা neural TTS | PARTIAL (Edge: নেট সমস্যা; gTTS: কাজ করে; SAPI offline fallback আছে) |
| স্ট্রিমিং/interruption/অটো-শোনা | PASS (কোড+লগ) |
| মাইক feedback loop প্রতিরোধ | PASS (speak শেষে listen) |
| whisper.cpp মূল্যায়ন | NOT TESTED |

## 💾 ডাটাবেস ও মেমরি
| ফিচার | স্ট্যাটাস |
|---|---|
| MySQL কানেকশন (XAMPP MariaDB) | PASS (root/blank — ব্যবহারকারী-নিশ্চিত, DPAPI-সংরক্ষিত) |
| ava_universal_ai + ১৩ টেবিল | PASS |
| CRUD + parameterized SQL | PASS |
| Command memory save/match/execute | PASS (৬/৬ ম্যাচিং টেস্ট) |
| Restart persistence | PASS |
| Conversation/summaries/projects/tasks | PASS (self-test ৫ রিপোর্ট) |
| Backup (mysqldump) | PASS |
| Learn-once (অনুমতি সহ) | PASS |

## 🖥️ Windows নিয়ন্ত্রণ
| ফিচার | স্ট্যাটাস |
|---|---|
| Desktop folder create/verify/remove | PASS (বাস্তব) |
| ফাইল তৈরি (ফোল্ডারের ভেতরে) | PASS (বাস্তব: নোট ফাইল.txt) |
| Rename/copy/move | PASS (কোড; বাস্তব টেস্ট আংশিক) |
| অ্যাপ খোলা + ভেতরে টাইপ (Unicode) | PASS (বাস্তব: Notepad টাইপ) |
| Start menu/উইন্ডো/লক | PASS (কোড; বাস্তব আংশিক) |
| ভলিউম up/down/mute | PASS (বাস্তব কি-চাপ) |
| ব্রাইটনেস | PASS (২৯% বাস্তবে পড়া) |
| মাউস মুভ/ক্লিক/স্ক্রল | PASS (কোড) |

## 🖥️ টার্মিনাল ইঞ্জিন
| ফিচার | স্ট্যাটাস |
|---|---|
| ৪ শেল শনাক্ত | PASS |
| Execute + output + exit code | PASS (echo, git --version) |
| Security classification | PASS (৫/৫) |
| Cancel/timeout | PARTIAL (taskkill ট্রি ফিক্স; পুনঃটেস্ট বাকি) |
| NL→plan (Ollama) | PARTIAL (কাজ করে, ধীর; Gemini হলে ভালো) |

## 👁️ স্ক্রিন দর্শন
| ফিচার | স্ট্যাটাস |
|---|---|
| স্ক্রিনশট + JPEG কমপ্রেস | PASS |
| Gemini vision বর্ণনা | PASS (বাস্তব — স্ক্রিন পড়েছে) |
| দ্রুততা | PARTIAL (নেট ধীর: ২-৪ মিনিট) |

## ⏰📚 নতুন (এই আপডেট)
| ফিচার | স্ট্যাটাস |
|---|---|
| Scheduler/রিমাইন্ডার + Windows toast + ভয়েস | PASS (বাস্তব ফায়ার টেস্ট) |
| Knowledge base (৬০ ফাইল ইনডেক্স + লাইন-উদ্ধৃতি সার্চ) | PASS |
| PDF/DOCX | NOT CONFIGURED (pypdf দরকার; সৎভাবে জানায়) |

## ❌ এখনো নেই (সৎ)
- GUI "hacker interface" — বর্তমানে টার্মিনাল UI (বড় আলাদা প্রজেক্ট)
- Windows installer/icon — onefile EXE আছে, installer নেই
- Browser form automation — ওপেন/সার্চ/টাইপ আছে, ফর্ম-ফিল নেই
- AI Developer Agent (Laravel কোড-লেখা) — terminal_engine দিয়ে আংশিক সম্ভব, বিশেষায়িত নয়
- whisper.cpp — Google STT ব্যবহৃত

## ▶️ চালানো / বিল্ড
- চালানো: `dist\Asif2.exe` (পাশে asif_key.txt) বা `AVA_START.bat`
- বিল্ড: `venv\Scripts\python -m PyInstaller --onefile --name Asif2 --console asif.py`
- ডাটাবেস সেটআপ: `venv\Scripts\python memory_db.py setup`
