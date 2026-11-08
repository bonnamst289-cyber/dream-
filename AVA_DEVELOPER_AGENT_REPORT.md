# AVA Developer Agent Report
Generated: 2026-11-08 (Phase 3, Module 08)

## Overall: PARTIAL (মূল ইঞ্জিন প্রস্তুত; লাইভ LLM টেস্ট ব্যবহারকারীর হাতে)

## বাস্তবায়নিত (coding_agent.py — নতুন)

| ফিচার | স্ট্যাটাস | নোট |
|---|---|---|
| প্রজেক্ট inspect (stack শনাক্ত) | PASS (কোড) | composer.json/artisan → Laravel; package.json → Next/React/NestJS; requirements → Python; .git শনাক্ত; dependencies তালিকা |
| কোড explain | PASS (কোড) | ফাইল পড়ে Gemini ব্যাখ্যা (১২K ক্যারেক্টার পর্যন্ত); tree-সার্চ সহ |
| ফাইল তৈরি/এডিট | PASS (কোড) | overwrite → **আগে .ava_backup ব্যাকআপ + অনুমতি**; লেখার পরে size-যাচাই |
| টেমপ্লেট জেনারেট | PASS (কোড) | Laravel controller/model/migration, React component, API, HTML — প্রজেক্ট-প্রসঙ্গ সহ LLM |
| Auto debugging | PASS (কোড) | error লগ → কারণ + নিরাপদ fix_cmd প্রস্তাব; secret masking; চালানো শুধু অনুমতিতে (terminal_engine) |
| Git checkpoint | PARTIAL | ব্যাকআপ কপি আছে; `git commit` checkpoint ব্যবহারকারী-নির্দেশিত |

## নিরাপত্তা
- লেখার আগে ব্যাকআপ; overwrite-এ অনুমতি; secret masking; কোনো arbitrary shell নয়

## ভয়েস কমান্ড
- "coding agent চালু করো" / "প্রজেক্ট inspect করো"
- "explain asif.py" / "কোড ব্যাখ্যা asif.py"
- "controller banao Product" / "model banao User" / "migration banao orders"
- "component banao Navbar"
- "bug fix করো <error লগ>" (টার্মিনাল/টেক্সটে)

## অবশিষ্ট (সৎ)
- পূর্ণ মাল্টি-ফাইল refactor, টেস্ট-রান অটোমেশন (terminal_engine দিয়ে সম্ভব)
- লাইভ LLM জেনারেশন টেস্ট ব্যবহারকারীর পিসিতে হবে (এই পরিবেশ ব্লকড)
