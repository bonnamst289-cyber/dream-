# -*- coding: utf-8 -*-
"""AVA Extended File Tools — Phase 2 ফাইল ম্যানেজার আপগ্রেড।
- সার্চ: নাম/এক্সটেনশন/তারিখ/বড় ফাইল • ডুপ্লিকেট শনাক্ত (size+hash)
- Downloads সংগঠন (পরিকল্পনা → অনুমতি → সরানো → যাচাই)
- টাইমস্ট্যাম্পড ব্যাকআপ/রিস্টোর • রিসাইকেল-বিন ডিলিট
- নিরাপত্তা: শুধু অনুমোদিত রুট; traversal নিষিদ্ধ; প্রতিটি কাজে যাচাই।"""
import datetime
import hashlib
import os
import shutil
from pathlib import Path

import file_manager

CAT_MAP = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"},
    "Documents": {".pdf", ".docx", ".doc", ".txt", ".md", ".xlsx", ".xls",
                  ".pptx", ".ppt", ".csv"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz"},
    "Software": {".exe", ".msi", ".apk"},
    "Media": {".mp4", ".mkv", ".mp3", ".wav", ".avi", ".mov"},
    "Code": {".py", ".js", ".php", ".html", ".css", ".json", ".sql", ".yml"},
}


def _allowed(p: Path) -> bool:
    return file_manager._is_allowed(p)


def search_files(name: str = "", ext: str = "", days: int = 0,
                 min_size_mb: float = 0, roots: list | None = None,
                 limit: int = 12) -> list[dict]:
    """নাম/এক্সটেনশন/তারিখ/সাইজ দিয়ে সার্চ (অনুমোদিত রুটে)।"""
    roots = roots or [Path(file_manager.desktop_path())]
    home = Path.home()
    for sub in ("Documents", "Downloads", "Pictures", "Videos", "Music"):
        d = home / sub
        if d.is_dir():
            roots.append(d)
    ext = ext.lower().lstrip(".")
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days) if days else None
    out = []
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        try:
            for p in root.rglob("*"):
                if len(out) >= limit:
                    break
                try:
                    if not p.is_file():
                        continue
                    if name and name.lower() not in p.name.lower():
                        continue
                    if ext and p.suffix.lower() != "." + ext:
                        continue
                    st = p.stat()
                    if cutoff and datetime.datetime.fromtimestamp(st.st_mtime) < cutoff:
                        continue
                    if min_size_mb and st.st_size < min_size_mb * 1024 * 1024:
                        continue
                    out.append({"path": str(p), "name": p.name,
                                "size_mb": round(st.st_size / 1048576, 2),
                                "modified": datetime.datetime.fromtimestamp(
                                    st.st_mtime).strftime("%Y-%m-%d")})
                except OSError:
                    continue
        except OSError:
            continue
    return out


def find_duplicates(roots: list | None = None) -> list[dict]:
    """একই সাইজ → ফিরে hash মিল — বাস্তব ডুপ্লিকেট।"""
    roots = roots or [Path(file_manager.desktop_path()), Path.home() / "Downloads"]
    by_size: dict[int, list] = {}
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        try:
            for p in root.rglob("*"):
                try:
                    if p.is_file() and 1024 < p.stat().st_size < 200 * 1048576:
                        by_size.setdefault(p.stat().st_size, []).append(p)
                except OSError:
                    continue
        except OSError:
            continue
    dups = []
    for size, files in by_size.items():
        if len(files) < 2:
            continue
        hashes: dict[str, Path] = {}
        for p in files:
            try:
                h = hashlib.md5()
                with open(p, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        h.update(chunk)
                digest = h.hexdigest()
                if digest in hashes:
                    dups.append({"original": str(hashes[digest]), "duplicate": str(p),
                                 "size_mb": round(size / 1048576, 2)})
                else:
                    hashes[digest] = p
            except OSError:
                continue
    return dups[:10]


def organize_plan(folder: str) -> list[dict]:
    """সংগঠনের পরিকল্পনা — কোন ফাইল কোথায় যাবে (কিছুই সরায় না)।"""
    src = Path(folder)
    if not src.is_dir() or not _allowed(src):
        return []
    plan = []
    for p in src.iterdir():
        if p.is_dir() or p.name in CAT_MAP:
            continue
        ext = p.suffix.lower()
        for cat, exts in CAT_MAP.items():
            if ext in exts:
                plan.append({"file": p.name, "to": cat})
                break
    return plan


def organize_execute(folder: str, plan: list[dict]) -> tuple[int, list]:
    """অনুমোদিত পরিকল্পনা মতো সরায় + প্রতিটা যাচাই।"""
    src = Path(folder)
    moved, errors = 0, []
    for item in plan:
        p = src / item["file"]
        dest_dir = src / item["to"]
        if not p.exists() or not _allowed(dest_dir):
            errors.append(f"{item['file']}: অবৈধ")
            continue
        try:
            dest_dir.mkdir(exist_ok=True)
            target = dest_dir / p.name
            if target.exists():
                target = dest_dir / (p.stem + "_" +
                                     datetime.datetime.now().strftime("%H%M%S") + p.suffix)
            shutil.move(str(p), str(target))
            if target.exists() and not p.exists():
                moved += 1
            else:
                errors.append(f"{item['file']}: যাচাই ব্যর্থ")
        except OSError as e:
            errors.append(f"{item['file']}: {e}")
    return moved, errors


def backup(paths: list[str]) -> dict:
    """টাইমস্ট্যাম্পড ব্যাকআপ ফোল্ডারে কপি + সংখ্যা-যাচাই।"""
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bdir = Path(file_manager.desktop_path()) / f"AVA_Backup_{stamp}"
    try:
        bdir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {"ok": False, "msg": f"ব্যাকআপ ফোল্ডার তৈরি ব্যর্থ: {e}"}
    copied, errors = 0, []
    for src in paths:
        p = Path(src)
        if not p.exists() or not _allowed(p):
            errors.append(f"{src}: অবৈধ/নেই")
            continue
        try:
            dest = bdir / p.name
            if p.is_dir():
                shutil.copytree(p, dest)
            else:
                shutil.copy2(p, dest)
            if dest.exists():
                copied += 1
            else:
                errors.append(f"{src}: কপি-যাচাই ব্যর্থ")
        except OSError as e:
            errors.append(f"{src}: {e}")
    return {"ok": copied > 0 and not errors, "dir": str(bdir),
            "copied": copied, "errors": errors}


def restore_from_backup(backup_dir: str, confirm: bool = True) -> dict:
    """ব্যাকআপের ফাইলগুলো ডেস্কটপে ফেরত (overwrite নয় — নতুন নামে)।"""
    bdir = Path(backup_dir)
    if not bdir.is_dir():
        return {"ok": False, "msg": "ব্যাকআপ ফোল্ডার পাওয়া যায়নি।"}
    desktop = Path(file_manager.desktop_path())
    restored, skipped = 0, 0
    for p in bdir.iterdir():
        if not p.is_file():
            continue
        target = desktop / p.name
        if target.exists():
            target = desktop / (p.stem + "_restored" + p.suffix)
            skipped += 1
        try:
            shutil.copy2(p, target)
            if target.exists():
                restored += 1
        except OSError:
            continue
    return {"ok": restored > 0, "restored": restored, "skipped": skipped,
            "msg": f"রিস্টোর: {restored}টি ফাইল ডেস্কটপে ফেরত"}


def recycle_delete(target: str, confirm: bool) -> dict:
    """সাধারণ মুছে ফেলা → রিসাইকেল বিন (PowerShell VisualBasic)।"""
    p = Path(target)
    if not p.exists() or not _allowed(p):
        return {"ok": False, "msg": "পাওয়া যায়নি বা অনুমোদিত নয়।"}
    if not confirm:
        return {"ok": False, "msg": "অনুমতি দেওয়া হয়নি।"}
    try:
        import subprocess
        ps = (
            "Add-Type -AssemblyName Microsoft.VisualBasic; "
            f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory("
            f"'{str(p).replace(chr(39), chr(39) * 2)}', "
            "'OnlyErrorDialogs', 'SendToRecycleBin')"
            if p.is_dir() else
            "Add-Type -AssemblyName Microsoft.VisualBasic; "
            f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("
            f"'{str(p).replace(chr(39), chr(39) * 2)}', "
            "'OnlyErrorDialogs', 'SendToRecycleBin')"
        )
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, timeout=30)
        gone = not p.exists()
        return {"ok": gone, "msg": ("🗑️ রিসাইকেল বিনে পাঠানো হয়েছে (ফেরানো যাবে!)"
                                    if gone else "মুছতে ব্যর্থ — ফাইল ব্যবহৃত হতে পারে।")}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


# ----------------- ভয়েস রাউটার -----------------
def handle(user_text: str, confirm_cb=None) -> tuple[bool, str] | None:
    t = user_text.lower()

    if "সংগঠন" in t or "organize" in t or "গুছিয়ে" in t:
        folder = file_manager.desktop_path() + os.sep + "Downloads" \
            if "download" in t else None
        if not folder:
            import re as _re
            m = _re.search(r"(?:organize|গুছিয়ে)\s+(.+)", user_text, _re.I)
            folder = m.group(1).strip() if m else ""
        if not folder or not Path(folder).is_dir():
            return True, "কোন ফোল্ডার গুছিয়ে দিব বলুন (পথ সহ)।"
        plan = organize_plan(folder)
        if not plan:
            return True, "গুছিয়ে দেওয়ার মতো কিছু নেই — ইতিমধ্যে পরিষ্কার!"
        listing = "\n".join(f"• {p['file']} → {p['to']}" for p in plan[:10])
        if confirm_cb and confirm_cb(
                f"{len(plan)}টা ফাইল ক্যাটাগরি-ফোল্ডারে সরানো হবে:\n{listing}\nঅনুমতি দিন? হ্যাঁ/না।"):
            moved, errors = organize_execute(folder, plan)
            return True, (f"✅ {moved}টা ফাইল সরানো ও যাচাইকৃত!"
                          + (f"\nসমস্যা: {errors[:3]}" if errors else ""))
        return True, "ঠিক আছে, কিছু সরাইনি। পরিকল্পনা ছিল:\n" + listing

    if "ডুপ্লিকেট" in t or "duplicate" in t:
        dups = find_duplicates()
        if not dups:
            return True, "কোনো ডুপ্লিকেট ফাইল পাইনি (ডেস্কটপ+Downloads)।"
        return True, ("🔍 ডুপ্লিকেট পাওয়া গেছে:\n" + "\n".join(
            f"• {d['duplicate']} (= {d['original']}, {d['size_mb']}MB)"
            for d in dups[:5]))

    if "ব্যাকআপ" in t or "backup" in t:
        m = None
        import re as _re
        m = _re.search(r"backup\s+(.+)", user_text, _re.I)
        targets = [m.group(1).strip()] if m else []
        if not targets:
            items = file_manager.list_desktop()
            return True, ("কী ব্যাকআপ করব? নাম বলুন। ডেস্কটপে আছে:\n"
                          + "\n".join(f"• {i}" for i in items[:10]))
        r = backup(targets)
        if r["ok"]:
            return True, f"💾 ব্যাকআপ সম্পন্ন ও যাচাইকৃত ({r['copied']} ফাইল): {r['dir']}"
        return True, f"ব্যাকআপ ব্যর্থ: {r['errors'][:2]}"

    if "রিস্টোর" in t or "restore" in t:
        import re as _re
        m = _re.search(r"restore\s+(.+)", user_text, _re.I)
        if not m:
            import glob
            bks = sorted(glob.glob(str(Path(file_manager.desktop_path())
                                      / "AVA_Backup_*")), reverse=True)
            if not bks:
                return True, "কোনো ব্যাকআপ নেই।"
            r = restore_from_backup(bks[0])
            return True, r["msg"]
        r = restore_from_backup(m.group(1).strip())
        return True, r["msg"]

    # সার্চ: তারিখ/এক্সটেনশন/বড় ফাইল
    import re as _re
    days = 0
    m = _re.search(r"(?:last|গত)\s*(\d+)\s*(?:din|দিন|day)", t)
    if m:
        days = int(m.group(1))
    ext = ""
    m2 = _re.search(r"(?:pdf|jpg|png|docx|xlsx|mp3|mp4|zip|txt)\b", t)
    if m2:
        ext = m2.group(0)
    large = "বড়" in t or "large" in t or "boro" in t
    name_q = ""
    if "image" in t or "ছবি" in t:
        ext = "jpg"
    if days or ext or large:
        name = _re.search(r"(?:name|নাম)\s+([\w\- ]+)", t)
        hits = search_files(name=(name.group(1).strip() if name else ""),
                            ext=ext, days=days,
                            min_size_mb=100 if large else 0)
        if not hits:
            return True, "এই শর্তে কিছু পাইনি (অনুমোদিত ফোল্ডারগুলোতে খুঁজেছি)।"
        return True, f"🔍 {len(hits)}টা পেলাম:\n" + "\n".join(
            f"• {h['name']} ({h['size_mb']}MB, {h['modified']})" for h in hits[:8])
    return None
