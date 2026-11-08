# UPDATE_SERVER_REPORT.md
Generated: 2026-11-08

## Overall: PARTIAL (লোকাল সোর্স বাস্তব টেস্ট; রিমোট সার্ভার ব্যবহারকারীর ইনফ্রা-নির্ভর)

- **PASS** — pluggable source: `update source <লোকাল পথ বা https URL>` ভয়েস কমান্ডে
- **PASS** — লোকাল সোর্স: `releases\latest\` বাস্তব টেস্ট (manifest+package পড়া, ডাউনলোড, যাচাই)
- **NOT CONFIGURED** — HTTPS সার্ভার/GitHub Releases: আপনার কাছে সার্ভার/রিপো নেই বলে অনুমান করা হয়নি। থাকলে:
  `update source https://আপনার-ডোমেইন/releases/latest/manifest.json` — একই ইঞ্জিন চলবে (HTTPS বাধ্যতামূলক)
- **PASS** — GitHub Releases-বানান নির্দেশ: build_release.py → releases/latest ফোল্ডার → gh release upload (রিপো থাকলে)
- **PASS** — কোনো টোকেন EXE-তে hardcode নয়
