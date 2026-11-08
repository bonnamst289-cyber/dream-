# -*- coding: utf-8 -*-
"""GitHub Release manifest generator — updater.py-র verify_signature-এর সাথে হুবহু সামঞ্জস্যপূর্ণ।
চালান (release.yml থেকে): python scripts/generate_manifest.py <version>
Env: RELEASE_SIGNING_KEY (GitHub Secret — কখনো লগে যাবে না)
তৈরি করে: release-manifest.json, SHA256SUMS.txt
⚠️ updater.verify_signature-এর হিসাবের সাথে হুবহু মিলতে হবে:
   payload keys: version,package,sha256,size,released,channel,notes
   json.dumps(payload, sort_keys=True, ensure_ascii=False) → HMAC-SHA256"""
import datetime
import hashlib
import hmac
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(BASE, "dist", "Asif.exe")


def main() -> None:
    version = sys.argv[1] if len(sys.argv) > 1 else ""
    key = os.environ.get("RELEASE_SIGNING_KEY", "")
    if not version:
        print("::error::version দিন (tag থেকে)")
        sys.exit(1)
    if not key:
        print("::error::RELEASE_SIGNING_KEY secret সেট করা নেই — unsigned release প্রকাশ নয়")
        sys.exit(1)
    if not os.path.exists(EXE):
        print("::error::dist/Asif.exe নেই — আগে build করুন")
        sys.exit(1)

    sha = hashlib.sha256(open(EXE, "rb").read()).hexdigest()
    size = os.path.getsize(EXE)
    repo = os.environ.get("GITHUB_REPOSITORY", "OWNER/REPO")
    released = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    manifest = {
        "app": "AVA Universal AI",
        "version": version,
        "channel": "stable",
        "platform": "windows",
        "architecture": "x64",
        "released": released,
        # ⬇️ সম্পূর্ণ download URL — updater.download_package এটা দিয়েই নামায়
        "package": f"https://github.com/{repo}/releases/download/v{version}/Asif.exe",
        "download_url": f"https://github.com/{repo}/releases/download/v{version}/Asif.exe",
        "sha256": sha,
        "size": size,
        "signature": "",
        "minimum_supported_version": "1.0.0",
        "release_notes_url": f"https://github.com/{repo}/releases/tag/v{version}",
    }
    payload = {k: manifest[k] for k in
               ("version", "package", "sha256", "size", "released", "channel", "notes")}
    msg = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    manifest["signature"] = hmac.new(key.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    out = os.path.join(BASE, "release-manifest.json")
    json.dump(manifest, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sums = os.path.join(BASE, "SHA256SUMS.txt")
    open(sums, "w", encoding="ascii").write(f"{sha}  Asif.exe\n")
    print(f"✔ manifest: {out}")
    print(f"✔ SHA256SUMS: {sums}")
    print(f"✔ version {version}, size {size}, sha {sha[:16]}... (signature included)")


if __name__ == "__main__":
    main()
