# UPDATE_MANIFEST_SPEC.md (v1 — updater.py-সামঞ্জস্য)

```json
{
  "app": "AVA Universal AI",
  "version": "1.0.2",
  "channel": "stable",
  "platform": "windows",
  "architecture": "x64",
  "released": "2026-11-08T04:00:00+00:00",
  "package": "https://github.com/OWNER/REPO/releases/download/v1.0.2/Asif.exe",
  "download_url": "একই URL (updater এটা দিয়েই ডাউনলোড করে)",
  "sha256": "<ফাইলের বাস্তব SHA-256>",
  "size": "<byte সংখ্যা>",
  "signature": "<HMAC-SHA256>",
  "minimum_supported_version": "1.0.0",
  "release_notes_url": "..."
}
```

## স্বাক্ষরের হিসাব (updater.verify_signature-এর সাথে হুবহু মিলতে হবে)
```
payload = এই ৭টি ফিল্ড: version, package, sha256, size, released, channel, notes
msg = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
signature = HMAC-SHA256(msg, RELEASE_SIGNING_KEY).hexdigest()
```
⚠️ `notes` ফিল্ড থাকতেই হবে (খালি হলে "") — payload-এর সাথে মিলবে না হলে ম্যানিফেস্ট প্রত্যাখ্যাত।

## হ্যান্ডলিং নিয়ম (updater.py)
- signature মেলেনি → প্রত্যাখ্যান ✔️ (বাস্তব টেস্ট)
- sha মেলেনি → বাতিল ✔️
- size মেলেনি → বাতিল ✔️
- version ≤ বর্তমান → "up-to-date" (downgrade নয়) ✔️
