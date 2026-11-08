# -*- coding: utf-8 -*-
"""
AVA — File Management Service
=============================
- আসল Windows Desktop path শনাক্ত (Windows API/রেজিস্ট্রি — OneDrive redirect সহ)
- validated folder/file create, rename, copy, move, list, search, open, delete
- প্রতিটি কাজের পরে বাস্তব verification (exists + type + path)
- নিরাপত্তা: অনুমোদিত ফোল্ডারের বাইরে কিছু হয় না; path traversal ব্লক
"""
import ctypes
import os
import re
import shutil
from pathlib import Path

_INVALID_CHARS = set('<>:"/\\|?*') | {chr(i) for i in range(32)}
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
             *(f"LPT{i}" for i in range(1, 10))}


def desktop_path() -> str:
    """বর্তমান ব্যবহারকারীর আসল Desktop (OneDrive redirect সহ)।"""
    # ১) Windows API — সবচেয়ে নির্ভরযোগ্য
    try:
        buf = ctypes.create_unicode_buffer(260)
        # CSIDL_DESKTOP = 0x0000, SHGetFolderPathW
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0000, None, 0, buf) == 0:
            p = buf.value.strip()
            if p and os.path.isdir(p):
                return p
    except Exception:
        pass
    # ২) রেজিস্ট্রি — User Shell Folders (redirected হলে ঠিক পথ দেয়)
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        val, _ = winreg.QueryValueEx(key, "Desktop")
        p = os.path.expandvars(val).strip()
        if p and os.path.isdir(p):
            return p
    except Exception:
        pass
    # ৩) সাধারণ অনুমান-শৃঙ্খল (শেষ ভরসা)
    home = Path.home()
    for cand in (home / "Desktop", home / "OneDrive" / "Desktop",
                 home / "OneDrive" / "ডেস্কটপ", home / "OneDrive" / "桌面"):
        if cand.is_dir():
            return str(cand)
    return str(home)


def allowed_roots() -> list:
    home = Path.home()
    roots = [desktop_path()]
    for sub in ("Documents", "Downloads", "Pictures", "Videos", "Music"):
        d = home / sub
        if d.is_dir():
            roots.append(str(d))
    return [os.path.normpath(r) for r in roots]


def _is_allowed(path: Path) -> bool:
    try:
        rp = os.path.normpath(str(path.resolve()))
    except Exception:
        return False
    return any(rp == r or rp.lower().startswith(r.lower() + os.sep)
               for r in allowed_roots())


def validate_name(name: str) -> tuple[bool, str]:
    name = (name or "").strip().strip(".")
    if not name:
        return False, "নাম খালি"
    if len(name) > 100:
        return False, "নাম খুব লম্বা"
    if any(ch in _INVALID_CHARS for ch in name):
        return False, "নামে নিষিদ্ধ অক্ষর আছে (<>:\"/\\|?*)"
    if name.split(".")[0].upper() in _RESERVED:
        return False, f"'{name}' হলো Windows-এর সংরক্ষিত নাম"
    if ".." in name or name.startswith(("\\", "/")) or re.match(r"^[A-Za-z]:", name):
        return False, "পাথ ট্রাভার্সাল অনুমোদিত নয়"
    return True, name


def _verify_dir(path: str) -> tuple[bool, str]:
    ok = os.path.isdir(path)
    return ok, path if ok else "ডিরেক্টরি নেই"


def create_folder(base: str, name: str) -> dict:
    """ফোল্ডার তৈরি + বাস্তব যাচাই। status: created|exists|error"""
    ok, val = validate_name(name)
    if not ok:
        return {"status": "error", "reason": val, "path": None}
    name = val
    base = os.path.normpath(base or desktop_path())
    if not _is_allowed(Path(base)):
        return {"status": "error", "reason": "এই লোকেশনে অনুমতি নেই", "path": None}
    path = os.path.join(base, name)
    try:
        if os.path.exists(path):
            if os.path.isdir(path):
                return {"status": "exists", "path": path,
                        "reason": "আগে থেকেই আছে (কিছু মোছা বা বদলায়নি)"}
            return {"status": "error", "reason": "একই নামে ফাইল আছে", "path": None}
        os.makedirs(path)  # exist_ok=False — কখনো overwrite নয়
    except PermissionError:
        return {"status": "error", "reason": "অনুমতি নেই (Access denied)", "path": None}
    except FileNotFoundError:
        return {"status": "error", "reason": "প্যারেন্ট ফোল্ডার নেই", "path": None}
    except OSError as e:
        return {"status": "error", "reason": f"সিস্টেম ত্রুটি: {e}", "path": None}
    vok, _ = _verify_dir(path)
    return {"status": "created" if vok else "error",
            "path": path if vok else None,
            "reason": "" if vok else "তৈরি হলেও যাচাই ব্যর্থ"}


def create_text_file(base: str, name: str, content: str = "") -> dict:
    if not re.search(r"\.[A-Za-z0-9]+$", name):
        name += ".txt"
    ok, val = validate_name(name)
    if not ok:
        return {"status": "error", "reason": val, "path": None}
    name = val
    base = os.path.normpath(base or desktop_path())
    if not _is_allowed(Path(base)):
        return {"status": "error", "reason": "এই লোকেশনে অনুমতি নেই", "path": None}
    path = os.path.join(base, name)
    try:
        if os.path.exists(path):
            return {"status": "exists", "path": path, "reason": "আগে থেকেই আছে"}
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        ok2 = os.path.isfile(path)
        return {"status": "created" if ok2 else "error", "path": path if ok2 else None,
                "reason": "" if ok2 else "তৈরি হলেও যাচাই ব্যর্থ"}
    except OSError as e:
        return {"status": "error", "reason": str(e), "path": None}


def _find_in_roots(name: str):
    """নাম দিয়ে অনুমোদিত লোকেশনগুলোতে ফাইল/ফোল্ডার খোঁজে (নির্দিষ্ট মিল আগে)।"""
    tl = name.lower().strip()
    if not tl:
        return None
    cands = []
    for root in allowed_roots():
        rootp = Path(root)
        if not rootp.is_dir():
            continue
        try:
            entries = list(rootp.iterdir())
        except OSError:
            continue
        for p in entries:
            pl = p.name.lower()
            if pl == tl:
                return p
            if tl in pl:
                cands.append(p)
        # ডেস্কটপের এক স্তর ভেতরেও খোঁজা
        if rootp == Path(desktop_path()):
            for p in entries:
                if p.is_dir():
                    try:
                        for q in p.iterdir():
                            if tl in q.name.lower():
                                cands.append(q)
                    except OSError:
                        pass
    return cands[0] if cands else None


def rename(src_name: str, new_name: str) -> dict:
    src = _find_in_roots(src_name)
    if not src:
        return {"status": "error", "reason": f"'{src_name}' খুঁজে পেলাম না", "path": None}
    ok, val = validate_name(new_name)
    if not ok:
        return {"status": "error", "reason": val, "path": None}
    dst = src.parent / val
    try:
        os.rename(src, dst)
    except OSError as e:
        return {"status": "error", "reason": str(e), "path": None}
    exists = dst.exists()
    return {"status": "created" if exists else "error", "path": str(dst) if exists else None,
            "reason": "" if exists else "rename যাচাই ব্যর্থ"}


def copy_item(src_name: str, dst_name: str | None = None) -> dict:
    src = _find_in_roots(src_name)
    if not src:
        return {"status": "error", "reason": f"'{src_name}' খুঁজে পেলাম না", "path": None}
    dst = src.parent / (dst_name or (src.stem + " - কপি" + src.suffix))
    ok, val = validate_name(dst.name)
    if not ok:
        return {"status": "error", "reason": val, "path": None}
    try:
        if dst.exists():
            return {"status": "error", "reason": "গন্তব্যে একই নাম আছে", "path": None}
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    except OSError as e:
        return {"status": "error", "reason": str(e), "path": None}
    exists = dst.exists()
    return {"status": "created" if exists else "error", "path": str(dst) if exists else None,
            "reason": "" if exists else "copy যাচাই ব্যর্থ"}


def move_item(src_name: str, dst_folder: str) -> dict:
    src = _find_in_roots(src_name)
    if not src:
        return {"status": "error", "reason": f"'{src_name}' খুঁজে পেলাম না", "path": None}
    dstp = Path(dst_folder)
    if not dstp.is_absolute():
        dstp = Path(desktop_path()) / dst_folder
    if not _is_allowed(dstp) or not dstp.is_dir():
        return {"status": "error", "reason": "গন্তব্য ফোল্ডার অবৈধ/অনুমোদিত নয়", "path": None}
    try:
        target = dstp / src.name
        if target.exists():
            return {"status": "error", "reason": "গন্তব্যে একই নাম আছে", "path": None}
        shutil.move(str(src), str(target))
    except OSError as e:
        return {"status": "error", "reason": str(e), "path": None}
    exists = target.exists() and not src.exists()
    return {"status": "created" if exists else "error", "path": str(target) if exists else None,
            "reason": "" if exists else "move যাচাই ব্যর্থ"}


def list_desktop() -> list:
    d = Path(desktop_path())
    try:
        items = sorted(d.iterdir(), key=lambda p: p.name.lower())
        return [f"{'📁' if p.is_dir() else '📄'} {p.name}" for p in items]
    except OSError:
        return []


def search_everywhere(name: str) -> list:
    tl = name.lower().strip()
    hits = []
    for root in allowed_roots():
        rootp = Path(root)
        if not rootp.is_dir():
            continue
        try:
            for p in rootp.iterdir():
                if tl in p.name.lower():
                    hits.append(p)
        except OSError:
            pass
    return hits[:5]


def open_in_explorer(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        found = _find_in_roots(path)
        p = found if found else p
    if not p.exists() or not _is_allowed(p):
        return {"status": "error", "reason": "খুঁজে পাওয়া যায়নি বা অনুমোদিত নয়", "path": None}
    target = str(p if p.is_dir() else p.parent)
    try:
        os.startfile(target)
        return {"status": "created", "path": target, "reason": "Explorer-এ খোলা হয়েছে"}
    except OSError as e:
        return {"status": "error", "reason": str(e), "path": None}


def delete_path(target: str) -> dict:
    """মুছে ফেলে (রাউটার আগে অনুমতি নেয়) + যাচাই করে যে সত্যিই গেছে।"""
    p = Path(target)
    if not p.exists():
        found = _find_in_roots(target)
        if not found:
            return {"status": "error", "reason": f"'{target}' খুঁজে পেলাম না", "path": None}
        p = found
    if not _is_allowed(p):
        return {"status": "error", "reason": "অনুমোদিত লোকেশনের বাইরে — মুছব না", "path": None}
    try:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            os.remove(p)
    except OSError as e:
        return {"status": "error", "reason": str(e), "path": None}
    gone = not p.exists()
    return {"status": "created" if gone else "error", "path": str(p) if gone else None,
            "reason": "" if gone else "মুছেছি কিন্তু যাচাই ব্যর্থ"}


# ----------------- বাস্তব গ্রহণযোগ্যতা পরীক্ষা + রিপোর্ট -----------------
def self_test() -> None:
    """আসল Windows Desktop-এ ৬টি পরীক্ষা চালিয়ে রিপোর্ট তৈরি করে।
    পরীক্ষায় তৈরি ফোল্ডারগুলোই শুধু পরে মুছে ফেলা হয়।"""
    import datetime
    results = []
    desktop = desktop_path()
    created: list[str] = []
    print(f"আসল Desktop: {desktop}\n")

    def rec(name, ok, note, path=""):
        results.append((name, "PASS" if ok else "FAIL", note, path))
        print(f"{'✅' if ok else '❌'} {name} — {note} {path}")

    # ১. AVA-Test তৈরি
    r = create_folder(desktop, "AVA-Test")
    if r["status"] == "created":
        created.append(r["path"])
    vok = r["path"] and os.path.isdir(r["path"])
    rec("১. Desktop-এ 'AVA-Test' তৈরি", r["status"] in ("created", "exists") and vok,
        r["status"] + (" (আগে থেকেই ছিল)" if r["status"] == "exists" else ""), r["path"] or "")

    # ২. স্পেস-যুক্ত নাম
    r = create_folder(desktop, "Laravel Projects")
    if r["status"] == "created":
        created.append(r["path"])
    rec("২. 'Laravel Projects' তৈরি (স্পেস-যুক্ত নাম)",
        r["status"] in ("created", "exists") and os.path.isdir(r["path"] or ""),
        r["reason"] or r["status"], r["path"] or "")

    # ৩. বাংলা নাম
    r = create_folder(desktop, "এভা টেস্ট")
    if r["status"] == "created":
        created.append(r["path"])
    rec("৩. বাংলা নামে ফোল্ডার ('এভা টেস্ট')",
        r["status"] in ("created", "exists") and os.path.isdir(r["path"] or ""),
        r["reason"] or r["status"], r["path"] or "")

    # ৪. বিদ্যমান ফোল্ডার আবার তৈরির চেষ্টা — overwrite না করেই 'exists'
    before = None
    ap = os.path.join(desktop, "AVA-Test")
    if os.path.isdir(ap):
        before = sorted(os.listdir(ap))
    r = create_folder(desktop, "AVA-Test")
    unchanged = before is not None and sorted(os.listdir(ap)) == before
    rec("৪. বিদ্যমান ফোল্ডার আবার তৈরি → overwrite নয়",
        r["status"] == "exists" and unchanged, r["reason"], r["path"] or "")

    # ৫. Explorer-এ খোলা
    r = open_in_explorer(os.path.join(desktop, "AVA-Test"))
    rec("৫. File Explorer-এ খোলা", r["status"] == "created", r["reason"], r["path"] or "")

    # ৬. ডেস্কটপ তালিকা — নতুন ফোল্ডারগুলো দেখা যাচ্ছে কি না
    listing = list_desktop()
    names = " ".join(listing)
    found_all = all(n in names for n in ("AVA-Test", "Laravel Projects", "এভা টেস্ট"))
    rec("৬. Desktop তালিকায় নতুন ফোল্ডার দৃশ্যমান", found_all,
        f"মোট {len(listing)}টি আইটেম")

    # পরীক্ষায় তৈরি ফোল্ডার পরিষ্কার (শুধু নিজেদের তৈরি, যাচাইয়ের পরে)
    cleaned = 0
    for p in created:
        if os.path.isdir(p):
            shutil.rmtree(p)
            cleaned += 1 if not os.path.exists(p) else 0

    passed = sum(1 for _, s, _, _ in results if s == "PASS")
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = "\n".join(f"- **{st}** — {name}  \n  নোট: {note}  \n  পাথ: `{path or '—'}`"
                      for name, st, note, path in results)
    report = f"""# AVA Desktop File Management Report
Generated: {stamp}

## Root Cause (আসল কারণ)
`asif.py`-তে Desktop path **হার্ডকোড অনুমান** ছিল:
`Path(os.path.expanduser("~")) / "Desktop"` — OneDrive redirection, বাংলা/স্পেস-যুক্ত
username বা সরানো Desktop হলে ভুল/অস্তিত্বহীন পথে ফোল্ডার যেত। নাম validation,
multi-folder, বাস্তব verification ও রিপোর্টও ছিল না।

## সমাধান (Modified Files)
- **file_manager.py (নতুন)** — Windows API (`SHGetFolderPathW`) + রেজিস্ট্রি
  (`User Shell Folders`) দিয়ে আসল Desktop; নাম validation; create/rename/copy/
  move/list/search/open/delete — প্রতিটিতে বাস্তব যাচাই; অনুমোদিত লোকেশন ছাড়া কিছু হয় না।
- **asif.py** — `DESKTOP` এখন `file_manager.desktop_path()` থেকে; লোকাল intent router
  (Gemini কল ছাড়াই) ফোল্ডার/ফাইল কাজ সরাসরি সার্ভিসে পাঠায়।

## আসল Desktop path (যাচাইকৃত)
`{desktop}`

## টেস্ট ফলাফল ({passed}/{len(results)} PASS)
{lines}

## Cleanup
পরীক্ষায় তৈরি {len(created)}টি ফোল্ডার যাচাইয়ের পরে মুছে ফেলা হয়েছে ({cleaned}টি)।

## অবশিষ্ট ত্রুটি
- কোনো টেস্ট FAIL না হলে: নেই
- OneDrive-বিহীন মেশিনে redirected-path শাখা বাস্তবে পরীক্ষিত হয়নি (কোড-স্তরে কভার্ড)
"""
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "AVA_DESKTOP_FILE_MANAGEMENT_REPORT.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n📄 রিপোর্ট: {out}")


if __name__ == "__main__":
    self_test()
