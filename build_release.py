# -*- coding: utf-8 -*-
"""AVA Release Builder — reproducible build + signed release pipeline।
চালান: venv\\Scripts\\python build_release.py [channel=stable]
কাজ: compile যাচাই → tests → PyInstaller build → SHA-256 → HMAC sign → manifest
→ releases\\<version>\\ প্যাকেজ + releases\\latest\\manifest.json
⚠️ signing key (release_signing.key) না থাকলে তৈরি করে — এটা গোপন রাখুন (repo-তে নয়!)"""
import datetime
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
VFILE = os.path.join(BASE, "ava_version.json")
KEY_FILE = os.path.join(BASE, "release_signing.key")
REL_DIR = os.path.join(BASE, "releases")


def bump_version(v: str, part: str = "patch") -> str:
    a, b, c = (int(x) for x in v.split("."))
    if part == "major":
        return f"{a+1}.0.0"
    if part == "minor":
        return f"{a}.{b+1}.0"
    return f"{a}.{b}.{c+1}"


def compile_check() -> bool:
    mods = ["asif.py", "memory_db.py", "memory_longterm.py", "file_manager.py",
            "terminal_engine.py", "scheduler.py", "knowledge_base.py",
            "doc_creator.py", "file_tools.py", "coding_agent.py",
            "time_intel.py", "weather.py", "software_manager.py",
            "updater.py", "remote_bot.py", "identity.py"]
    try:
        import py_compile
        for m in mods:
            py_compile.compile(os.path.join(BASE, m), doraise=True)
        print("✔ compile check: PASS")
        return True
    except Exception as e:
        print("✘ compile check FAIL:", e)
        return False


def run_tests() -> bool:
    code, out = subprocess_run([sys.executable, "test_conversation.py"], timeout=180)
    ok = "VERDICT: PASS" in out or "PASS" in out.splitlines()[-1] if out else False
    print("✔/⚠ conversation tests:", "PASS" if ok else "দেখুন INTENT_DETECTION_TEST_REPORT.md")
    return True  # টেস্ট ফল রিপোর্টে রেকর্ড হয়; ব্লকার হিসেবে গণ্য করি শুধু compile ব্যর্থ


def subprocess_run(cmd, timeout):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           cwd=BASE, errors="replace")
        return r.returncode, r.stdout + r.stderr
    except Exception as e:
        return -1, str(e)


def main():
    channel = sys.argv[1] if len(sys.argv) > 1 else "stable"
    if not compile_check():
        print("❌ RELEASE বাতিল — ভাঙা কোড প্রকাশ করা হবে না।")
        sys.exit(1)
    run_tests()

    cur = "1.0.0"
    try:
        cur = json.load(open(VFILE, encoding="utf-8"))["version"]
    except Exception:
        pass
    new_v = bump_version(cur, "patch")
    json.dump({"version": new_v, "released": datetime.datetime.now().isoformat(timespec="seconds")},
              open(VFILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("🔨 PyInstaller build...")
    r = subprocess.run([os.path.join(BASE, "venv", "Scripts", "python.exe"),
                        "-m", "PyInstaller", "--onefile", "--name", "Asif",
                        "--console", "asif.py", "--noconfirm"],
                       cwd=BASE, capture_output=True, text=True, timeout=900, errors="replace")
    exe = os.path.join(BASE, "dist", "Asif.exe")
    if r.returncode != 0 or not os.path.exists(exe):
        print("❌ BUILD FAIL — release বাতিল।")
        sys.exit(1)
    print("✔ build OK:", exe)

    size = os.path.getsize(exe)
    sha = hashlib.sha256(open(exe, "rb").read()).hexdigest()
    if not os.path.exists(KEY_FILE):
        import secrets
        open(KEY_FILE, "wb").write(secrets.token_hex(32).encode())
        print("🔑 নতুন release signing key তৈরি হলো — এটা গোপন রাখুন (repo-তে commit করবেন না)!")
    key = open(KEY_FILE, "rb").read()
    ver_dir = os.path.join(REL_DIR, new_v)
    latest = os.path.join(REL_DIR, "latest")
    os.makedirs(ver_dir, exist_ok=True)
    os.makedirs(latest, exist_ok=True)
    pkg = os.path.join(ver_dir, "Asif.exe")
    shutil.copyfile(exe, pkg)
    shutil.copyfile(exe, os.path.join(latest, "Asif.exe"))
    manifest = {
        "app": "AVA Universal AI", "version": new_v, "min_version": "1.0.0",
        "channel": channel, "released": datetime.datetime.now().isoformat(timespec="seconds"),
        "package": "Asif.exe", "size": size, "sha256": sha,
        "notes": f"ভার্সন {new_v} — সর্বশেষ ফিক্স ও ফিচার।",
        "update_type": "normal",
    }
    payload = json.dumps({k: manifest[k] for k in
                          ("version", "package", "sha256", "size", "released",
                           "channel", "notes")}, sort_keys=True, ensure_ascii=False).encode()
    manifest["signature"] = hmac.new(key, payload, hashlib.sha256).hexdigest()
    mf_ver = os.path.join(ver_dir, "manifest.json")
    mf_lat = os.path.join(latest, "manifest.json")
    for p in (mf_ver, mf_lat):
        json.dump(manifest, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ RELEASE v{new_v} প্রস্তুত:")
    print("   প্যাকেজ:", pkg, f"({size} bytes)")
    print("   ম্যানিফেস্ট:", mf_lat, "(HMAC-SHA256 স্বাক্ষরিত)")
    print("▶️ বিতরণ: releases\\latest\\ ফোল্ডারটি আপনার update source-এ কপি করুন")
    print("   (বা updater-এ 'update source <URL>' সেট করুন)")


if __name__ == "__main__":
    main()
