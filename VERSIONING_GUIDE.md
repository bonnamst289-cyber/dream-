# VERSIONING_GUIDE.md
Generated: 2026-11-08

## Semver নিয়ম
- `MAJOR.MINOR.PATCH` — ava_version.json = single source of truth
- tag: `v<version>` — release.yml নিজেই tag↔version মিলিয়ে দেখে (অমিল = বাতিল)

| পরিবর্তন | বাড়ান |
|---|---|
| বাগ ফিক্স | PATCH (1.0.1→1.0.2) |
| নতুন ফিচার | MINOR (1.0→1.1) |
| বড় পরিবর্তন/ব্রেকিং | MAJOR (1.x→2.0) |

- build_release.py নিজেই bump করে (patch ডিফল্ট; `build_release.py minor`)
- ডুপ্লিকেট tag নিষিদ্ধ
