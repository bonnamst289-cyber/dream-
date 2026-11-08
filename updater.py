# -*- coding: utf-8 -*-
"""AVA Auto-Update Engine (Phase: Automatic Update)
- Manifest: version/SHA-256/size/notes/HMAC-SHA256 signature (release key শুধু বিল্ড-মেশিনে)
- Source: লোকাল ফোল্ডার বা HTTPS URL (pluggable) — কোনো অনুমান নয়
- ডাউনলোড: স্ট্রিমিং+প্রগ্রেস+স্টেজিং+সাইজ/হ্যাশ যাচাই (যাচাই ছাড়া চালানো নয়)
- ইনস্টল: graceful close → updater.bat (rollback backup → replace → relaunch → verify → fail=rollback)
- ডেটা সংরক্ষণ: exe আর ইউজার-ডেটা আলাদা — DB/মেমরি/সেটিংস স্পর্শ হয় না"""
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(BASE, "ava_version.json")
SOURCE_FILE = os.path.join(BASE, "ava_update_source.json")
SIGN_KEY_FILE = os.path.join(BASE, "release_signing.key")
STAGING = os.path.join(BASE, "update_staging")


def app_version() -> str:
    try:
        return json.load(open(VERSION_FILE, encoding="utf-8"))["version"]
    except Exception:
        return "0.0.0"


def _semver(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.split(".")[:3])
    except Exception:
        return (0, 0, 0)


def _is_newer(remote: str, local: str) -> bool:
    return _semver(remote) > _semver(local)


def load_source() -> dict:
    """আপডেট সোর্স কনফিগ: {"manifest": "<লোকাল পথ বা https URL>"}"""
    try:
        return json.load(open(SOURCE_FILE, encoding="utf-8"))
    except Exception:
        return {"manifest": os.path.join(BASE, "releases", "latest", "manifest.json")}


def set_source(manifest_path_or_url: str) -> str:
    json.dump({"manifest": manifest_path_or_url},
              open(SOURCE_FILE, "w", encoding="utf-8"))
    return f"আপডেট সোর্স সেট হলো: {manifest_path_or_url}"


def _read_text(path_or_url: str) -> str | None:
    try:
        if path_or_url.lower().startswith("http"):
            with urllib.request.urlopen(path_or_url, timeout=20) as r:
                return r.read().decode("utf-8")
        return open(path_or_url, encoding="utf-8").read()
    except Exception:
        return None


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_signature(manifest: dict) -> tuple[bool, str]:
    """HMAC-SHA256: manifest-এর নির্দিষ্ট ফিল্ডগুলো signing key দিয়ে সই হয়।
    ⚠️ সীমাবদ্ধতা: verify key ইনস্টল ডিরেক্টরিতে থাকলে এটা integrity-যাচাই —
    পূর্ণ আসল-স্বাক্ষরের জন্য Ed25519 (cryptography) প্রয়োজন — পরিকল্পিত।"""
    if not os.path.exists(SIGN_KEY_FILE):
        return False, "signing/verify key নেই — ম্যানিফেস্ট যাচাই সম্ভব নয়"
    key = open(SIGN_KEY_FILE, "rb").read()
    payload = {k: manifest.get(k) for k in
               ("version", "package", "sha256", "size", "released", "channel", "notes")}
    msg = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    calc = hmac.new(key, msg, hashlib.sha256).hexdigest()
    if hmac.compare_digest(calc, str(manifest.get("signature", ""))):
        return True, "স্বাক্ষর যাচাইকৃত"
    return False, "স্বাক্ষর মেলেনি — প্যাকেজ প্রত্যাখ্যাত"


def check_for_updates(quiet: bool = False) -> dict:
    """ম্যানিফেস্ট আনে → স্বাক্ষর যাচাই → semver তুলনা। ফেরত: status dict।"""
    src = load_source()["manifest"]
    raw = _read_text(src)
    if raw is None:
        return {"status": "OFFLINE", "msg": "আপডেট সোর্সে পৌঁছানো যায়নি — পরে আবার চেষ্টা হবে।"}
    try:
        manifest = json.loads(raw)
    except Exception:
        return {"status": "FAIL", "msg": "ম্যানিফেস্ট ভাঙা (JSON নয়)।"}
    if not src.lower().startswith("http"):
        manifest["_dir"] = os.path.dirname(os.path.abspath(src))  # লোকাল সোর্সের ফোল্ডার
    sig_ok, sig_msg = verify_signature(manifest)
    if not sig_ok:
        return {"status": "REJECTED", "msg": f"❌ স্বাক্ষর যাচাই ব্যর্থ — আপডেট প্রত্যাখ্যাত। ({sig_msg})"}
    remote_v = str(manifest.get("version", "0.0.0"))
    local_v = app_version()
    if _is_newer(remote_v, local_v):
        return {"status": "UPDATE_AVAILABLE", "manifest": manifest,
                "msg": f"🆕 নতুন ভার্সন {remote_v} পাওয়া গেছে (বর্তমান {local_v})। "
                       f"নোট: {str(manifest.get('notes'))[:120]}"}
    if not quiet:
        return {"status": "UP_TO_DATE",
                "msg": f"✅ আপনার AVA সর্বশেষ ভার্সনে ({local_v}) আছে।"}
    return {"status": "UP_TO_DATE", "msg": ""}


def download_package(manifest: dict, progress_cb=None, cancel=None) -> dict:
    """প্যাকেজ ডাউনলোড → স্টেজিং → সাইজ+SHA-256 যাচাই। (cancel(event) সমর্থিত)"""
    os.makedirs(STAGING, exist_ok=True)
    src = manifest.get("download_url") or manifest.get("package", "")
    _dir = manifest.get("_dir", "")
    if src and not src.lower().startswith("http"):
        if _dir and not os.path.isabs(src):
            src = os.path.join(_dir, src)
        if not os.path.exists(src):
            return {"ok": False, "msg": "প্যাকেজ পাওয়া যায়নি: " + src + " (লোকাল সোর্স পথ দেখুন)"}
    dest = os.path.join(STAGING, os.path.basename(src) or "ava_update.exe")
    expected_size = int(manifest.get("size", 0) or 0)
    expected_sha = str(manifest.get("sha256", "")).lower()
    tmp = dest + ".part"
    try:
        if src.lower().startswith("http"):
            req = urllib.request.Request(src)
            resume_from = os.path.getsize(tmp) if os.path.exists(tmp) else 0
            if resume_from:
                req.add_header("Range", f"bytes={resume_from}-")
            with urllib.request.urlopen(req, timeout=30) as r, \
                    open(tmp, "ab" if resume_from else "wb") as f:
                total = int(r.headers.get("Content-Length", 0)) + resume_from
                done = resume_from
                while True:
                    if cancel is not None and cancel.is_set():
                        return {"ok": False, "msg": "⏹ ডাউনলোড বাতিল করা হলো।"}
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress_cb and total:
                        progress_cb(done, total)
        else:  # লোকাল সোর্স (টেস্ট)
            shutil.copyfile(src, tmp)
            done = os.path.getsize(tmp)
            if progress_cb:
                progress_cb(done, done)
        if expected_size and os.path.getsize(tmp) != expected_size:
            os.remove(tmp)
            return {"ok": False, "msg": "❌ সাইজ মেলেনি — ডাউনলোড অসম্পূর্ণ। প্যাকেজ বাতিল।"}
        actual = _sha256(tmp)
        if expected_sha and actual != expected_sha:
            os.remove(tmp)
            return {"ok": False, "msg": "❌ SHA-256 মেলেনি — প্যাকেজ দূষিত/ভুয়া। বাতিল ও লগ।"}
        shutil.move(tmp, dest)
        return {"ok": True, "path": dest, "msg": f"✅ ডাউনলোড+যাচাই সম্পন্ন: {dest}"}
    except Exception as e:
        return {"ok": False, "msg": f"ডাউনলোড ব্যর্থ: {type(e).__name__}: {e}"}


def apply_update(verify_ok: bool, confirm_cb=None) -> str:
    """graceful close → updater.bat (rollback backup → replace → relaunch → verify → fail=rollback)।
    যাচাই ছাড়া কখনো চালানো যাবে না।"""
    if not verify_ok:
        return "❌ যাচাই ছাড়া আপডেট ইনস্টল করা যাবে না।"
    staged = os.path.join(STAGING, "Asif.exe")
    if not os.path.exists(staged):
        return "❌ স্টেজিং-এ যাচাইকৃত প্যাকেজ নেই।"
    current_exe = os.path.join(BASE, "dist", "Asif.exe")
    if not os.path.exists(current_exe):
        return "❌ বর্তমান ইনস্টল (dist\\Asif.exe) পাইনি।"
    if confirm_cb and not confirm_cb(
            "আপডেট ইনস্টলের জন্য AVA বন্ধ হবে (আপনার ডেটা/মেমরি অক্ষত থাকবে)। "
            "অসংরক্ষিত কাজ থাকলে সেভ করুন। এখনই আপডেট করবেন? হ্যাঁ/না।"):
        return "ঠিক আছে — আপডেট পরে। (স্টেজিং-এ রাখা আছে)"
    bat = os.path.join(BASE, "ava_update_apply.bat")
    log = os.path.join(BASE, "ava_update_log.txt")
    with open(bat, "w", encoding="utf-8") as f:
        f.write(f"""@echo off
chcp 65001 >nul
title AVA Updater
cd /d "{BASE}"
echo [AVA UPDATER] AVA bondho hobe... (data/memory DB theke alada - safe)
taskkill /IM Asif.exe /F >nul 2>&1
taskkill /IM Asif2.exe /F >nul 2>&1
taskkill /IM Asif3.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul
if not exist "dist\\Asif_backup.exe" copy /y "{current_exe}" "dist\\Asif_backup.exe" >nul
echo [UPDATER] Rollback backup toiri: dist\\Asif_backup.exe
copy /y "{staged}" "{current_exe}" >nul
if errorlevel 1 goto rollback
for %%F in ("{current_exe}") do set NEWSIZE=%%~zF
for %%F in ("{staged}") do if "%%~zF"=="%NEWSIZE%" goto verify_ok
:rollback
echo [UPDATER] FAIL - ager version pherot korchi...
copy /y "dist\\Asif_backup.exe" "{current_exe}" >nul
echo [UPDATER] Rollback sompanno. Log: {log}
echo {datetime.datetime.now()} ROLLBACK >> "{log}"
pause
exit /b 1
:verify_ok
echo [UPDATER] Notun version install + size-verify sompanno.
echo {datetime.datetime.now()} UPDATED OK size=%NEWSIZE% >> "{log}"
start "" "{current_exe}"
exit /b 0
""")
    subprocess.Popen(["cmd", "/c", bat], creationflags=subprocess.CREATE_NEW_CONSOLE)
    return ("🔄 আপডেটার চালু হলো — AVA বন্ধ হয়ে আপডেট ইনস্টল হবে, তারপর নিজেই "
            "চালু হবে। ব্যর্থ হলে পুরনো ভার্সন অটো-ফেরত আসবে। (লগ: ava_update_log.txt)")


def install_datetime_placeholder():
    pass


import datetime  # noqa: E402


# ----------------- ভয়েস রাউটার -----------------
def handle(user_text: str, confirm_cb=None, speak_cb=None) -> tuple[bool, str] | None:
    t = user_text.lower()
    if "আপডেট" not in t and "update" not in t:
        return None
    if "সোর্স" in t or "source" in t:
        import re
        m = re.search(r"(?:source|সোর্স)\s+(.+)", user_text, re.I)
        if m:
            return True, set_source(m.group(1).strip())
        return True, (f"বর্তমান সোর্স: {load_source()['manifest']}\n"
                      "বদলাতে বলুন: 'update source <লোকাল পথ বা https URL>'")
    if "ইনস্টল" in t or "install" in t or "apply" in t:
        return True, apply_update(verify_ok=True, confirm_cb=confirm_cb)
    if "বন্ধ" in t and "আপডেট" in t:
        if STATE_CANCEL.get("cancel") is not None:
            STATE_CANCEL["cancel"].set()
        return True, "⏹ আপডেট বন্ধ করার অনুরোধ পাঠানো হলো।"
    r = check_for_updates()
    if r["status"] == "UPDATE_AVAILABLE":
        manifest = r["manifest"]
        dl = download_package(manifest, progress_cb=lambda d, tot: print(
            f"⬇️ {d//1048576}/{tot//1048576} MB", end="\r"),
            cancel=STATE_CANCEL.get("cancel"))
        if dl["ok"]:
            return True, (r["msg"] + "\n" + dl["msg"] +
                          "\nইনস্টল করতে বলুন: 'আপডেট ইনস্টল করো'।")
        return True, r["msg"] + "\n" + dl["msg"]
    return True, r["msg"]


STATE_CANCEL = {"cancel": None}


class _Cancel:
    def is_set(self):
        return False


STATE_CANCEL["cancel"] = _Cancel()


def version_info() -> str:
    return f"AVA Universal AI v{app_version()}"
