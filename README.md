# 🎙️ আসিফ — Bangla Voice AI Assistant

বাংলায় কথা বলা ও বোঝা জানা একটি ভয়েস অ্যাসিস্ট্যান্ট।

## কীভাবে কাজ করে

1. 🎤 **শোনা** — মাইক থেকে বাংলা শোনে (Google Speech Recognition, bn-BD)
   — কথা শেষ হলে নিজে থেকেই থামে (silence detection)
2. 🧠 **ভাবা** — OpenAI API বা Ollama (local) দিয়ে বাংলায় উত্তর তৈরি করে
3. 🗣️ **বলা** — Microsoft Edge TTS-এর বাংলা ভয়েসে (`bn-BD-PradeepNeural`) পড়ে শোনায়

## ইনস্টল (প্রথমবার)

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

## AI Brain সেটআপ (যেকোনো একটা)

**অপশন ১ — OpenAI API key (ভালো quality):**
```bash
set OPENAI_API_KEY=sk-...   # Windows CMD
# bash: export OPENAI_API_KEY=sk-...
```

**অপশন ২ — Ollama (ফ্রি, offline):**
1. https://ollama.com থেকে Ollama ইনস্টল করুন
2. টার্মিনালে চালান: `ollama pull llama3.1`
3. কোনো key লাগবে না — আসিফ নিজেই Ollama খুঁজে নেবে

## চালান

```bash
venv\Scripts\python asif.py
```

তারপর মাইক্রোফোনে বাংলায় কথা বলুন! 🎤

- **"বন্ধ"**, **"বিদায়"** বা **"গুডবাই"** বললে বন্ধ হবে
- Ctrl+C চেপেও যেকোনো সময় বন্ধ করা যায়
- মাইক সমস্যা হলে টার্মিনালে টাইপ করেও কথা বলা যাবে (fallback মোড)

## কাস্টমাইজ

`asif.py` এর উপরের কনফিগ অংশে:
- `TTS_VOICE` — কণ্ঠ বদলান (`bn-BD-NabanitaNeural` = নারী কণ্ঠ)
- `OLLAMA_MODEL` — Ollama মডেল বদলান
- `SYSTEM_PROMPT` — আসিফের ব্যক্তিত্ব বদলান
