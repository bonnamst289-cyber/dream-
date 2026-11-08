# -*- coding: utf-8 -*-
"""AVA Scheduler — রিমাইন্ডার ও নোটিফিকেশন (হালকা, 8GB-friendly)।
- ভয়েসে: "৫ মিনিট পরে আমাকে X মনে করাও", "সকাল ৯টায় X মনে করাও"
- Windows toast/balloon নোটিফিকেশন দেয়
- টাস্ক তালিকা দেখা/মুছা সমর্থিত"""
import datetime
import json
import os
import re
import threading
import time

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ava_reminders.json")
_state = {"items": [], "thread": None}
_LOCK = threading.Lock()


def _load():
    try:
        with open(FILE, encoding="utf-8") as f:
            _state["items"] = json.load(f)
    except Exception:
        _state["items"] = []


def _save():
    try:
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(_state["items"], f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _toast(title: str, body: str) -> None:
    """Windows balloon notification (কোনো extra install লাগে না)।"""
    ps = f"""
Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.ShowBalloonTip(8000, '{title.replace("'", "''")}', '{body.replace("'", "''")}', [System.Windows.Forms.ToolTipIcon]::Info)
Start-Sleep -Seconds 6
$n.Dispose()
"""
    try:
        import subprocess
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=20)
    except Exception:
        pass


def _parse_time(user_text: str) -> datetime.datetime | None:
    t = user_text.lower()
    now = datetime.datetime.now()
    m = re.search(r"(\d+)\s*(?:মিনিট|min|minute)", t)
    if m:
        return now + datetime.timedelta(minutes=int(m.group(1)))
    m = re.search(r"(\d+)\s*(?:ঘণ্টা|ঘন্টা|hour|ghonta)", t)
    if m:
        return now + datetime.timedelta(hours=int(m.group(1)))
    m = re.search(r"(\d+)\s*(?:সেকেন্ড|sec|second)", t)
    if m:
        return now + datetime.timedelta(seconds=int(m.group(1)))
    m = re.search(r"(?:সকাল|দুপুর|বিকেল|সন্ধ্যা|রাত)?\s*(\d{1,2})(?::(\d{2}))?\s*(?:টা|ta)?", t)
    if m and any(w in t for w in ("সকাল", "দুপুর", "বিকেল", "সন্ধ্যা", "রাত", "টায়", "tay")):
        hh = int(m.group(1)); mm = int(m.group(2) or 0)
        if any(w in t for w in ("বিকেল", "সন্ধ্যা", "রাত")) and hh < 12:
            hh += 12
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        return target
    return None


def _extract_task(user_text: str) -> str:
    t = user_text
    for w in ("আমাকে", "amar", "আমার", "মনে করাও", "monay korao", "মনে করিয়ে",
              "remind me to", "remind me", "reminder", "মনে রাখাও", "মনে করাইও"):
        t = re.sub(re.escape(w), " ", t, flags=re.I)
    t = re.sub(r"\d+\s*(?:মিনিট|min|minute|ঘণ্টা|ঘন্টা|hour|সেকেন্ড|sec|second)"
               r"|(?:সকাল|দুপুর|বিকেল|সন্ধ্যা|রাত)\s*\d{1,2}(?::\d{2})?\s*(?:টা|ta)?",
               " ", t, flags=re.I)
    t = re.sub(r"\b(?:পরে|poray|later|tay|টায়|te|তে)\b", " ", t, flags=re.I)
    return t.strip(" ।,.") or "রিমাইন্ডার"


def add_reminder(when: datetime.datetime, task: str) -> dict:
    with _LOCK:
        if not _state["items"] and not _state["thread"]:
            _ensure_thread()
        item = {"at": when.isoformat(timespec="seconds"),
                "task": task, "done": False}
        _state["items"].append(item)
        _save()
    return item


def list_reminders() -> list:
    with _LOCK:
        return [i for i in _state["items"] if not i["done"]]


def remove_reminder(index: int) -> bool:
    with _LOCK:
        open_items = [i for i in _state["items"] if not i["done"]]
        if 0 <= index < len(open_items):
            open_items[index]["done"] = True
            _save()
            return True
    return False


def _ensure_thread():
    _load()
    th = threading.Thread(target=_loop, daemon=True)
    _state["thread"] = th
    th.start()


def _loop():
    while True:
        time.sleep(5)
        now = datetime.datetime.now()
        fired = []
        with _LOCK:
            for item in _state["items"]:
                if item["done"]:
                    continue
                try:
                    at = datetime.datetime.fromisoformat(item["at"])
                except Exception:
                    continue
                if now >= at:
                    item["done"] = True
                    fired.append(item["task"])
            _save()
        for task in fired:
            _toast("⏰ AVA রিমাইন্ডার", task)
            try:
                import asif
                asif.speak(f"রিমাইন্ডার! {task}")
            except Exception:
                pass


# অ্যাপ চালু হলে থ্রেড চালু (asif.py থেকে ডাকা হয়)
def startup() -> None:
    _ensure_thread()


# ----------------- ভয়েস রাউটার -----------------
def handle(user_text: str) -> tuple[bool, str] | None:
    t = user_text.lower()
    if not any(w in t for w in ("মনে করাও", "মনে করিয়ে", "রিমাইন্ডার", "remind",
                                "মনে রাখাও", "reminder")):
        return None
    if "তালিকা" in t or "list" in t or "দেখাও" in t:
        items = list_reminders()
        if not items:
            return True, "কোনো রিমাইন্ডার নেই।"
        return True, "রিমাইন্ডার:\n" + "\n".join(
            f"• {i['at'][11:16]} — {i['task'][:60]}" for i in items)
    if "মুছ" in t or "delete" in t or "বাতিল" in t:
        items = list_reminders()
        if not items:
            return True, "মোছার মতো রিমাইন্ডার নেই।"
        if len(items) == 1:
            remove_reminder(0)
            return True, f"রিমাইন্ডার বাতিল: {items[0]['task'][:50]}"
        return True, "কোনটা বাতিল? সংখ্যা বলুন:\n" + "\n".join(
            f"{n+1}. {i['task'][:50]}" for n, i in enumerate(items))
    when = _parse_time(user_text)
    if not when:
        return True, ("কখন মনে করাব বলুন — যেমন: '৫ মিনিট পরে আমাকে ওষুধ মনে করাও' "
                      "বা 'রাত ৯টায় আমাকে কল দিতে বলো মনে করাও'।")
    task = _extract_task(user_text)
    add_reminder(when, task)
    return True, f"⏰ ঠিক আছে! {when.strftime('%I:%M %p')}-এ মনে করিয়ে দেব: {task[:60]}"
