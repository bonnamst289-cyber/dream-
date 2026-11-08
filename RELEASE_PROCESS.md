# RELEASE_PROCESS.md
Generated: 2026-11-08

## নিয়মিত Release (প্রতিবার একই প্রক্রিয়া)

1. কোড পরিবর্তন → নিজে টেস্ট (`test_conversation.py`, `CHECK_AND_FIX.bat`)
2. `ava_version.json`-এ ভার্সন বাড়ান (semver)
3. Commit + push main-এ → CI workflow (windows-build.yml) নিজেই টেস্ট+বিল্ড করবে
4. ট্যাগ দিন + push:
   ```bash
   git tag v1.0.2
   git push origin v1.0.2
   ```
5. release.yml চলবে: version consistency → tests → build → manifest+signature (Secret থেকে) → **GitHub Release প্রকাশ**
6. চালু AVA নিজেই: manifest পড়বে → ডাউনলোড → SHA+signature যাচাই → অনুমতি নিয়ে → update + relaunch
7. ব্যর্থ হলে → auto-rollback পুরনো ভার্সনে

## ব্যর্থ হলে
- CI-তে ব্যর্থ ধাপের লগ দেখুন; release প্রকাশ হবে না (artifact সংরক্ষিত থাকে)
- ঠিক করে আবার push — ডুপ্লিকেট tag হলে ট্যাগ মুছে নতুন করুন (releases → delete tag)

## জরুরি rollback
GitHub → Releases → পুরনো ভার্সনের manifest-এর URL দিয়ে AVA-র source সেট করলে পুরনো ভার্সন ফেরা যায় — কিন্তু updater semver-নীতিতে downgrade আটকায়; জরুরি হলে updater.py-র `_is_newer` অস্থায়ীভাবে বাইপাস করুন (owner-approved)।
