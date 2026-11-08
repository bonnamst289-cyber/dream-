# -*- coding: utf-8 -*-
"""AVA Remote Control (Telegram) — নিরাপদ রিমোট অ্যাক্সেস।
- কোনো পোর্ট খোলা নয়: শুধু outbound long-polling (ফায়ারওয়াল-নিরাপদ)
- Pairing: প্রথম /start <TOKEN> — টোকেন ছাড়া কেউ ঢুকতে পারে না
- শুধু paired chat-এর কমান্ড চলে; destructive কমান্ডে /confirm দুই-ধাপ
- সব রিমোট অ্যাকশন audit হয়; টোকেন ফাইলে (DPAPI-প্রস্তুত)"""
import datetime
import json
import os
import sys
import threading
import time

import requests

API = "https://api.telegram.org"


def _app_dir() -> str:
    """টোকেন/পেয়ার/অডিট ফাইলের স্থায়ী ফোল্ডার।

    PyInstaller --onefile চালালে __file__ হয় সাময়িক _MEIxxxx ফোল্ডারে,
    তাই টোকেন ফাইল খুঁজে পাওয়া যেত না → exe থেকে বট কখনো চালু হতো না।
    এখন:cwd → exe-র ফোল্ডার → তার parent — যেখানে আসল ফাইল আছে সেটাই নেওয়া হয়।"""
    if not getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(__file__))
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    dirs = []
    for d in (os.path.abspath(os.getcwd()), exe_dir, os.path.dirname(exe_dir)):
        if d and d not in dirs:
            dirs.append(d)
    for name in ("ava_remote_token.json", "ava_remote_pair.json"):
        for d in dirs:
            if os.path.exists(os.path.join(d, name)):
                return d
    return dirs[0]


APP_DIR = _app_dir()
TOKEN_FILE = os.path.join(APP_DIR, "ava_remote_token.json")
PAIR_FILE = os.path.join(APP_DIR, "ava_remote_pair.json")
STATE = {"running": False, "thread": None, "offset": 0, "pending": {}}
DANGEROUS = ("মুছ", "delete", "uninstall", "বন্ধ করো", "format", "shutdown", "রিমুভ", "remove")


def _get(url: str, timeout: int = 30):
    return requests.get(url, timeout=timeout)


def _post(url: str, data: dict, timeout: int = 30):
    return requests.post(url, data=data, timeout=timeout)


def token() -> str | None:
    try:
        return json.load(open(TOKEN_FILE, encoding="utf-8"))["token"]
    except Exception:
        return None


def save_token(token: str) -> None:
    json.dump({"token": token}, open(TOKEN_FILE, "w", encoding="utf-8"))


def paired() -> list[int]:
    try:
        return json.load(open(PAIR_FILE, encoding="utf-8"))["chats"]
    except Exception:
        return []


def _pair(chat_id: int) -> None:
    chats = paired()
    if chat_id not in chats:
        chats.append(chat_id)
        json.dump({"chats": chats}, open(PAIR_FILE, "w", encoding="utf-8"))


def send(chat_id: int, text: str) -> None:
    tk = token()
    if not tk:
        return
    try:
        _post(f"{API}/bot{tk}/sendMessage", {"chat_id": chat_id, "text": text[:4000]},
              timeout=15)
    except Exception:
        pass


def audit(entry: dict) -> None:
    try:
        f = os.path.join(APP_DIR, "ava_remote_audit.jsonl")
        entry["time"] = datetime.datetime.now().isoformat(timespec="seconds")
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def pairing_code() -> str:
    """স্থায়ী ৬-অক্ষরের পেয়ারিং কোড (পিসি-স্ক্রিনে দেখানো হয়)।"""
    try:
        data = json.load(open(PAIR_FILE, encoding="utf-8"))
        if data.get("code"):
            return data["code"]
    except Exception:
        pass
    import secrets
    code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
    try:
        data = {"code": code, "chats": paired()}
        json.dump(data, open(PAIR_FILE, "w", encoding="utf-8"))
    except Exception:
        pass
    return code


def _handle_update(msg: dict) -> None:
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()
    if not chat_id or not text:
        return
    chats = paired()
    if chat_id not in chats:
        code = pairing_code()
        if text.strip() == f"/start {code}":
            _pair(chat_id)
            send(chat_id, "✅ পেয়ারিং সফল! এখন এখান থেকে AVA চালাতে পারবেন।\n"
                          "সতর্কতা: destructive কমান্ডের জন্য /confirm লাগবে।")
        else:
            send(chat_id, "🔒 পেয়ারিং কোড ভুল। পিসির স্ক্রিনে ৬ অক্ষরের কোডটা দেখুন, "
                          "তারপর লিখুন: /start <কোড>")
        audit({"event": "unauthorized_attempt", "chat": chat_id})
        return

    # pending confirmation (destructive)
    pend = STATE["pending"].get(chat_id)
    if pend and text.lower() in ("confirm", "/confirm", "হ্যাঁ", "yes"):
        cmd = STATE["pending"].pop(chat_id)
        result = _execute(cmd)
        send(chat_id, f"✅ [confirmed] {result[:1500]}")
        audit({"event": "remote_confirmed", "chat": chat_id, "cmd": cmd})
        return
    if pend and text.lower() in ("cancel", "/cancel", "না", "no"):
        STATE["pending"].pop(chat_id)
        send(chat_id, "🚫 বাতিল করা হলো।")
        return

    if text.startswith("/status"):
        try:
            import memory_db
            status = "DB ✔" if memory_db.load_credentials() else "DB ✖"
        except Exception:
            status = "DB ✖"
        send(chat_id, f"🤖 AVA চালু আছে। {status}। কমান্ড লিখুন।")
        audit({"event": "status", "chat": chat_id})
        return
    if text.startswith("/revoke"):
        # সব পেয়ারিং বাতিল (এমার্জেন্সি ডিসকানেক্ট)
        json.dump({"chats": []}, open(PAIR_FILE, "w", encoding="utf-8"))
        send(chat_id, "🔒 সব ডিভাইস revoke হলো। আবার pair করতে নতুন কোড লাগবে।")
        audit({"event": "revoke", "chat": chat_id})
        return

    # destructive শনাক্ত → দুই-ধাপ নিশ্চিতি
    if any(w in text.lower() for w in DANGEROUS):
        STATE["pending"][chat_id] = text
        send(chat_id, f"⚠️ এটা destructive মনে হচ্ছে:\n「{text[:150]}」\n"
                      "নিশ্চিত হলে লিখুন: /confirm (বাতিল: /cancel)")
        audit({"event": "await_approval", "chat": chat_id, "cmd": text[:200]})
        return

    result = _execute(text)
    send(chat_id, result[:3500])
    audit({"event": "command", "chat": chat_id, "cmd": text[:200]})


def _execute(text: str) -> str:
    """রিমোট কমান্ড → একই AVA ব্রেন (মাইক/স্পিকার ছাড়া, নীরবে)।"""
    try:
        import asif
        asif.MIC_OK = False  # রিমোটে মাইক নয়
        handled, reply = asif.try_command(text)
        if handled:
            return reply
        # ব্রেন (Ollama/Gemini) — সাধারণ প্রশ্ন/কথোপকথন
        return asif.think(text)
    except Exception as e:
        return f"সমস্যা: {type(e).__name__}: {e}"


def _loop():
    tk = token()
    offset = STATE.get("offset", 0)
    while STATE["running"]:
        try:
            r = _get(f"{API}/bot{tk}/getUpdates?timeout=25&offset={offset}",
                     timeout=35)
            updates = r.json().get("result", [])
            for u in updates:
                offset = u["update_id"] + 1
                STATE["offset"] = offset
                msg = u.get("message")
                if msg:
                    _handle_update(msg)
        except Exception:
            time.sleep(3)


def _kill_other_instances() -> None:
    """অন্য remote_bot কপি বন্ধ করো — কিন্তু নিজের পূর্বপুরুষ (launcher) কখনো নয়।

    venv-এর python.exe একটি launcher যা আসল interpreter-কে child হিসেবে চালায়;
    দুজনের command line-এই remote_bot থাকে। os.getpid() শুধু child-কে বোঝে,
    তাই পুরনো কোড নিজের launcher-কেই মেরে নিজে মরে যেত।"""
    try:
        import subprocess as _sp
        q = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "
             + chr(39) + "*remote_bot*" + chr(39)
             + " } | ForEach-Object { $_.ProcessId.ToString() + '|' + "
             "$_.ParentProcessId.ToString() + '|' + $_.Name }")
        out = _sp.run(["powershell", "-NoProfile", "-Command", q],
                      capture_output=True, text=True, timeout=30).stdout
        procs = {}
        for line in out.splitlines():
            parts = line.strip().split("|")
            if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                procs[int(parts[0])] = (int(parts[1]), parts[2].lower())
        # নিজে + নিজের সব পূর্বপুরুষ (launcher/powershell) — কখনো মারা যাবে না
        protected, pid = set(), os.getpid()
        while pid and pid not in protected:
            protected.add(pid)
            pid = procs.get(pid, (0, ""))[0]
        victims = [p for p, (_ppid, name) in procs.items()
                   if p not in protected
                   and name in ("python.exe", "pythonw.exe", "py.exe")]
        if victims:
            ids = ",".join(str(v) for v in victims)
            _sp.run(["powershell", "-NoProfile", "-Command",
                     f"Stop-Process -Id {ids} -Force -ErrorAction SilentlyContinue"],
                    capture_output=True, timeout=15)
    except Exception:
        pass


def startup() -> str:
    """অ্যাপ চালু হলে ব্যাকগ্রাউন্ডে বট চালু (token থাকলে)।
    সিঙ্গেল-ইনস্ট্যান্স গ্যারান্টি: অন্য remote_bot প্রসেস থাকলে বন্ধ করে নিজে চলে।"""
    if not token():
        return "টোকেন নেই — remote বন্ধ। (সেটআপ: SETUP_REMOTE.bat)"
    _kill_other_instances()
    if STATE["running"]:
        return "ইতিমধ্যে চলছে।"
    STATE["running"] = True
    STATE["thread"] = threading.Thread(target=_loop, daemon=True)
    STATE["thread"].start()
    code = pairing_code()
    chats = paired()
    for c in chats:
        send(c, "🟢 AVA পিসিতে চালু হয়েছে — রিমোট রেডি!")
    msg = f"রিমোট চালু ({len(chats)}টি paired ডিভাইস)। পেয়ারিং কোড: {code}"
    print(f"🔐 PAIRING CODE: {code}  ← ফোনে /start {code} পাঠান", flush=True)
    audit({"event": "startup", "chats": len(chats), "app_dir": APP_DIR,
           "frozen": bool(getattr(sys, "frozen", False))})
    return msg


def stop() -> None:
    STATE["running"] = False


# ----------------- ভয়েস রাউটার -----------------
def handle(user_text: str) -> tuple[bool, str] | None:
    t = user_text.lower()
    if not any(w in t for w in ("remote", "রিমোট", "telegram", "টেলিগ্রাম")):
        return None
    if "সেটআপ" in t or "setup" in t or "token" in t or "টোকেন" in t:
        return True, ("📱 Telegram remote সেটআপ (৫ মিনিট):\n"
                      "১. Telegram-এ @BotFather খুলুন → /newbot → নাম দিন\n"
                      "২. যে TOKEN দেখাবে (1234:ABC...) কপি করুন\n"
                      "৩. পিসির টার্মিনালে চালান:\n"
                      "   venv\\Scripts\\python -c \"import remote_bot; remote_bot.save_token(input('TOKEN: '))\"\n"
                      "৪. নিজের Telegram-এ নিজের বটকে /start <কোড> পাঠান (পিসি স্ক্রিনে কোড দেখাবে)\n"
                      "৫. AVA আবার চালু করুন — রিমোট লাইভ!")
    if "স্ট্যাটাস" in t or "status" in t:
        return True, (f"টোকেন: {'✔️ আছে' if token() else '❌ নেই'}\n"
                      f"Paired ডিভাইস: {len(paired())}টি\n"
                      f"Running: {'হ্যাঁ' if STATE['running'] else 'না'}")
    if "বন্ধ" in t or "stop" in t:
        stop()
        return True, "রিমোট বন্ধ করা হলো।"
    return True, ("Remote Control (Telegram):\n• সেটআপ করতে বলুন: 'remote সেটআপ'\n"
                  "• স্ট্যাটাস: 'remote status'\n• বন্ধ: 'remote বন্ধ'\n\n"
                  "⚠️ WhatsApp personal automation ঝুঁকিপূর্ণ (ব্যান) — তাই নিরাপদ "
                  "Telegram পথ দেওয়া হয়েছে। WhatsApp Cloud API চাইলে বলুন।")
