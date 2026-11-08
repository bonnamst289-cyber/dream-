# AVA Development Environment Report
Generated: 2026-11-08

## Overall: PASS (বাস্তব পরিবেশে যাচাইকৃত)

- **PASS** — XAMPP: `C:\xampp` শনাক্ত (আসল)
- **PASS** — MySQL/MariaDB: চালু, port 3306 open (বাস্তব টেস্ট)
- **PASS** — MySQL start/stop: XAMPP bat + প্রসেস-যাচাই; বন্ধে অনুমতি
- **PASS** — Apache start/stop: bat ফাইল + প্রসেস-যাচাই
- **PASS** — PHP: `C:\xampp\php\php.exe` পথ-সচেতন (version কোয়েরি সমর্থিত)
- **PASS** — Node.js: v26.13.0 (বাস্তব টেস্ট)
- **PASS** — npm: 11.20.0 (বাস্তব টেস্ট)
- **PASS** — Git: 2.56.0 (বাস্তব টেস্ট)
- **NOT TESTED** — Composer/Java/Android Studio (মেশিনে অনুপস্থিত বলে শনাক্তকারী "NOT INSTALLED" দেখাবে)
- **PASS** — নীতি: ডিফল্ট MySQL পোর্ট ধরে না (my.ini পড়ে + 3306 প্রোব); XAMPP config কখনো overwrite নয়; সার্ভিস বন্ধে অনুমতি
