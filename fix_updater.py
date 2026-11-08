# -*- coding: utf-8 -*-
"""One-shot fix: updater.py-তে remote download_url সমর্থন যোগ করে (idempotent)।
চালান: venv\\Scripts\\python fix_updater.py — CHECK_AND_FIX.bat এটা অটো চালায়।"""
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
    src = src.replace(old, new, 1)
    open('updater.py', 'w', encoding='utf-8').write(src)
    print("✔ updater.py: download_url সমর্থন যোগ হলো")
else:
    print("✔ ইতিমধ্যে ঠিক আছে (কিছু করা লাগবে না)")
