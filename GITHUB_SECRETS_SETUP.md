# GITHUB_SECRETS_SETUP.md
Generated: 2026-11-08

## দরকারি Secrets (শুধু ১টা)

| Secret নাম | মান | কোথা থেকে |
|---|---|---|
| `RELEASE_SIGNING_KEY` | release_signing.key ফাইলের ভেতরের hex স্ট্রিং | আপনার পিসি: `C:\Users\HP\dream-\release_signing.key` |

- Settings → Secrets and variables → Actions → **New repository secret**
- ⚠️ এটা ছাড়া release workflow **ইচ্ছাকৃতভাবে ব্যর্থ হবে** — unsigned release প্রকাশ নয় (নিরাপত্তা নিয়ম)

## GITHUB_TOKEN
- নিজে থেকেই থাকে (workflow-এ `permissions: contents: write` — release পাবলিশের জন্য)
- আলাদা secret লাগে না

## নিয়ম
- Secret কখনো লগ/রিপোর্ট/কোডে নয় ✔️ (workflows শুধু env হিসেবে পড়ে)
- Fork থেকে PR-এ secret অ্যাক্সেস পায় না (GitHub ডিফল্ট সুরক্ষা)
