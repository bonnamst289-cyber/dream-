# CI_CD_RELEASE_REPORT.md
Generated: 2026-11-08

## Overall: PARTIAL (লোকাল pipeline বাস্তব; CI সার্ভার নেই)

- **PASS** — build_release.py: compile check (১৬ মডিউল) → tests → build → SHA-256 → HMAC sign → manifest → releases/<v> + latest — **বাস্তবে চলে v1.0.1 তৈরি হয়েছে**
- **PASS** — ভাঙা কোড = release বাতিল (compile fail → sys.exit)
- **PASS** — signing key আলাদা ফাইলে (repo/EXE-তে নয়)
- **NOT CONFIGURED** — GitHub Actions/CI: আপনার Git repo নেই বলে; রিপো হলে workflow template দেওয়া যাবে
- **NOT TESTED** — পুনরাবৃত্তি বিল্ড reproducibility (byte-identical) — PyInstaller সাধারণত আংশিক reproducible
