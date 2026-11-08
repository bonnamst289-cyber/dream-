# -*- coding: utf-8 -*-
"""Patch: updater download_url support + release.yml python signature step."""
ok = 0

# ১) updater.py
src = open('updater.py', encoding='utf-8').read()
old = '''    src = manifest.get("package", "")
    _dir = manifest.get("_dir", "")
    if src and not os.path.isabs(src) and _dir and not src.lower().startswith("http"):
        src = os.path.join(_dir, src)'''
new = '''    src = manifest.get("download_url") or manifest.get("package", "")
    _dir = manifest.get("_dir", "")
    if src and not src.lower().startswith("http"):
        if _dir and not os.path.isabs(src):
            src = os.path.join(_dir, src)
        if not os.path.exists(src):
            return {"ok": False, "msg": "প্যাকেজ পাওয়া যায়নি: " + src + " (লোকাল সোর্স পথ দেখুন)"}'''
if old in src:
    src = src.replace(old, new, 1); ok += 1
else:
    print("updater MISS")
open('updater.py', 'w', encoding='utf-8').write(src)

# ২) release.yml — signature step পাইথনে (updater-এর হুবহু HMAC হিসাব)
src = open('.github/workflows/release.yml', encoding='utf-8').read()
try:
    start = src.index('      - name: Generate manifest + signature')
    end = src.index('      - name: Verify signature locally')
    new_step = (
        '      - name: Generate manifest + signature (python — updater-সামঞ্জস্য)\n'
        '        env:\n'
        '          RELEASE_SIGNING_KEY: ${{ secrets.RELEASE_SIGNING_KEY }}\n'
        '        run: python scripts/generate_manifest.py "${{ github.ref_name }}"\n\n'
    )
    src = src[:start] + new_step + src[end:]
    ok += 1
except ValueError:
    print("release.yml anchor MISS")
open('.github/workflows/release.yml', 'w', encoding='utf-8').write(src)
print("patched:", ok)
