# WINDOWS_BUILD_GUIDE.md
Generated: 2026-11-08

## লোকাল বিল্ড (ব্যবহৃত ও যাচাইকৃত পদ্ধতি)
```
cd C:\Users\HP\dream-
venv\Scripts\python.exe -m PyInstaller --onefile --name Asif --console asif.py --noconfirm
```
- ফল: `dist\Asif.exe` (onefile; প্রথম চালুতে bootloader+child = ২ প্রসেস — স্বাভাবিক)
- পাশে রাখুন: asif_key.txt (Gemini), অন্যান্য ava_*.json ডেটা

## CI বিল্ড (GitHub)
- windows-latest + Python 3.13 + requirements.txt
- ফল: dist\Asif.exe + SHA-256 → artifact "AVA-Windows-Build"

## সীমাবদ্ধতা
- Python 3.15 (লোকাল) বনাম CI 3.13 — কোড দুটোতেই চলে (py_compile+tests verify করে)
- pyaudio ব্যবহৃত হয় না (sounddevice — উভয় পরিবেশে wheels আছে)
