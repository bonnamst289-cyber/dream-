# IDENTITY MEMORY AUDIT
Generated: 2026-11-08

## Overall: PASS (বাস্তব টেস্ট)

| প্রশ্ন | বাস্তব উত্তর (লাইভ Gemini) |
|---|---|
| তোমাকে কে বানিয়েছে? নাম কী? | "আমার নাম **AVA** (AVA Universal AI)। আমাকে তৈরি করেছেন **Asif Shekh** (Founder & Owner), কোম্পানি **AVA IT Solution**। Windows Desktop AI Assistant।" ✔️ |

## স্থায়িত্ব
- ফাইল: `ava_identity.json` ✔️
- MySQL: `app_settings` টেবিলে identity_* কী ✔️ (সেভ হলে)
- রিস্টার্টে load() দিয়ে পুনরুদ্ধার ✔️

## সংশোধন-নিয়ম
- owner বললে identity বদলানো যায় (identity.save())
- সাধারণ ব্যবহারকারীর কথায় identity বদলায় না (system prompt-এ কঠোর নিয়ম)

## টেস্ট
- fast_reply identity উত্তর: developer+company সঠিক ✔️ (test_conversation.py)
