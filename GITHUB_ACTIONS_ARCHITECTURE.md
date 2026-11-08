# GITHUB_ACTIONS_ARCHITECTURE.md
Generated: 2026-11-08

## ২টা Workflow (তৈরি)

### windows-build.yml (CI)
- Trigger: push/PR → main, manual
- Runner: windows-latest, Python 3.13 (pinned), pip cache
- ধাপ: checkout → deps → compile-all (১৬ মডিউল) → pyflakes → test_conversation.py → PyInstaller onefile → SHA-256 → artifact upload (actions/upload-artifact@v4)
- Publish করে না (শুধু verify)

### release.yml (Release)
- Trigger: tag `v*.*.*` বা manual (version input)
- ধাপ: **tag↔ava_version.json consistency check** (অমিল = বাতিল) → tests → build → **python scripts/generate_manifest.py** (updater-সামঞ্জস্য HMAC) → signature-presence check → rename (AVA-Update/Setup) → commit-log থেকে release notes (বানানো নয়) → **softprops/action-gh-release@v2** publish
- Secret: RELEASE_SIGNING_KEY (env — লগে যায় না)
- Unsigned manifest → workflow ব্যর্থ → publish নয়

## নিরাপত্তা
- permissions: ন্যূনতম (contents: read / write)
- Actions pinned versions (@v4/@v5/@v2)
- Fork PR-এ secrets অ্যাক্সেস নেই (GitHub ডিফল্ট)
- Signing key repo/EXE-তে নেই — শুধু GitHub Secret + বিল্ড-মেশিন
