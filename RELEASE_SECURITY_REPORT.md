# RELEASE_SECURITY_REPORT.md
Generated: 2026-11-08

## Overall: PASS (নকশা-স্তর)

- **PASS** — unsigned production release **প্রকাশ অসম্ভব** (workflow throw করে)
- **PASS** — tag↔version consistency enforcement
- **PASS** — least-privilege permissions; pinned actions
- **PASS** — signing key: GitHub Secret + লোকাল ফাইল; repo/EXE/লগে নেই
- **PASS** — fork PR-এ secret অ্যাক্সেস নেই
- **PASS** — updater: HMAC verify (বাস্তব টেস্ট) + sha/size/version যাচাই
- **PARTIAL** — asymmetric signing (Ed25519) — HMAC এখন; পরে আপগ্রেড পরিকল্পনা
- **PASS** — release notes: বানানো নয়, কমিট থেকে
