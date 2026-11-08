# GitHub Repository Setup (Owner-এর জন্য ধাপে ধাপে)

## ১. GitHub-এ রিপো তৈরি
1. github.com → New repository → নাম: `ava-universal-ai` → **Private** (সুপারিশ) → Create

## ২. লোকাল Git-এ remote যোগ + push (পিসির CMD-তে)
```bash
cd C:\Users\HP\dream-
git add -A
git commit -m "AVA Universal AI — full source"
git branch -M main
git remote add origin https://github.com/আপনার-ইউজারনেম/ava-universal-ai.git
git push -u origin main
```

## ৩. GitHub Secret যোগ (signing)
- পিসিতে: `type release_signing.key` (অথবা ফাইলটা Notepad-এ খুলুন)
- GitHub → রিপো → **Settings → Secrets and variables → Actions → New repository secret**
  - Name: `RELEASE_SIGNING_KEY`
  - Value: ওই key-এর ভেতরের স্ট্রিং (hex) — **কোথাও পোস্ট করবেন না**

## ৪. প্রথম release
```bash
git tag v1.0.1
git push origin v1.0.1
```
→ GitHub Actions নিজেই build+release করবে → `release-manifest.json` তৈরি হবে

## ৫. AVA-কে নতুন সোর্স জানান
AVA ভয়েসে: *"update source https://github.com/আপনার-ইউজারনেম/ava-universal-ai/releases/latest/download/release-manifest.json"*
→ এরপর প্রতি release-এ চালু AVA নিজেই আপডেট নেবে! (updater `download_url` সমর্থন করে)

## 🔒 .gitignore already রক্ষা করে
asif_key.txt, ava_db_credentials.bin, release_signing.key, my_token.txt, মেমরি-ফাইল, dist, releases, venv — **কোনোটাই commit হবে না**। নিশ্চিত করতে: `git status` — এগুলো দেখালে ভুল।
