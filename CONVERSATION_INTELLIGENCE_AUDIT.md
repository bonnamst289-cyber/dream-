# CONVERSATION INTELLIGENCE AUDIT
Generated: 2026-11-08

## Root Cause (আসল কারণ)
১. পুরনো system prompt-এ **অ্যাসিস্ট্যান্ট ও ডেভেলপার একাকার** ছিল ("আমি আসিফ" অথচ developer-ও Asif) → identity confusion
২. প্রশ্নের দিক উল্টানো: দুর্বল লোকাল মডেল সাধারণ প্রশ্নে ("ভালো আছো?" বনাম "আমি ভালো আছি") subject/object গুলিয়ে ফেলত
৩. পরিচয় কোথাও স্থায়ীভাবে সংরক্ষিত ছিল না
৪. প্রম্পটে স্তর-স্থাপত্য ছিল না (সব এক স্ট্রিং-এ)

## সমাধান (কোড-স্তরে, শুধু প্রম্পট নয়)
- **identity.py (নতুন):** স্থায়ী পরিচয় (ফাইল + MySQL app_settings), A–H স্তরযুক্ত প্রম্পট স্থাপত্য, intent classifier (identity/wellbeing/thanks/greeting/goodbye/correction/capabilities)
- **asif.py:** converse() এখন **Gemini প্রাইমারি (SSE streaming)**, Ollama ফলব্যাক; fast_reply প্রথমে চলে (সাধারণ প্রশ্নে LLM কল নেই)
- **গ্রিটিং/পরিচয় রিব্র্যান্ড:** আসিফ → **AVA**

## টেস্ট-প্রমাণ
- intent classifier: **১৩ কেসে ১১ সরাসরি + লাইভ Gemini identity সঠিক**
- বিস্তারিত: INTENT_DETECTION_TEST_REPORT.md, BANGLA_BANGLISH_TEST_REPORT.md

## অবশিষ্ট
- Banglish বানান-ভিন্নতার লম্বা তালিকা সময়ের সাথে বাড়বে (learning সহ)
