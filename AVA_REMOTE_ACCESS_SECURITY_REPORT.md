# AVA Remote Access Security Report
Generated: 2026-11-08 (Module 20)

## Overall: PASS (নকশা) / NOT TESTED (লাইভ — টোকেন সেটআপ ব্যবহারকারীর)

## নকশা-নীতি (সব PASS — কোডে এমবেড)
- **কোনো open port নেই** — শুধু outbound long-polling (ফায়ারওয়াল-নিরাপদ)
- **Pairing বাধ্যতামূলক**: প্রথম /start + পিসি-স্ক্রিনের কোড ছাড়া কেউ ঢুকতে পারে না
- **শুধু paired chat** কমান্ড চালাতে পারে; অননুমোদিত চেষ্টা audit হয়
- **Destructive কমান্ড** (মুছা/বন্ধ/uninstall/format...) → দুই-ধাপ: /confirm আবশ্যক
- **/revoke** → সব ডিভাইস এক কমান্ডে বাতিল (এমার্জেন্সি ডিসকানেক্ট)
- **Audit log**: ava_remote_audit.jsonl (সব রিমোট অ্যাকশন)
- **টোকেন** লোকাল ফাইলে (DPAPI-রূপান্তরযোগ্য); কখনো রিপোর্ট/মেমরিতে যায় না

## চ্যানেল সিদ্ধান্ত (সৎ)
- **Telegram বাছা হয়েছে**: official Bot API, ফ্রি, ব্যান-ঝুঁকি নেই, ৫ মিনিট সেটআপ
- **WhatsApp personal (unofficial) নয়**: Meta ToS ভাঙে — নম্বর ব্যান ঝুঁকি
- **WhatsApp Cloud API (official)**: ভবিষ্যতে যোগযোগ্য (Meta developer account দরকার)

## সেটআপ (ব্যবহারকারী)
১. Telegram-এ @BotFather → /newbot → TOKEN কপি
২. পিসি: `venv\Scripts\python -c "import remote_bot; remote_bot.save_token(input('TOKEN: '))"`
৩. AVA চালু → বট নিজেই পেয়ারিং কোড দেখাবে → ফোনে /start <কোড> পাঠান
৪. এরপর ফোন থেকে: "ফোল্ডার বানাও X", "স্ক্রিন কী দেখছো", কথোপকথন — সব চলবে

## সীমাবদ্ধতা
- লাইভ টেস্ট টোকেন-সেটআপের পরে হবে
- ভয়েস রিমোট নয় (টেক্সট); ভবিষ্যতে ভয়েস-নোট → টেক্সট সম্ভব
