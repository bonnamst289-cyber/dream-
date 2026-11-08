# -*- coding: utf-8 -*-
"""
আসিফ — Bangla Voice AI Assistant
শোনে (mic) → ভাবে (LLM) → বলে (TTS)
"""
import base64
import asyncio
import ctypes
import datetime
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

import requests

import file_manager

# ----------------- কনফিগ -----------------
STT_LANG = "bn-BD"                       # বাংলাদেশি বাংলা
STT_KEY = "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"  # SpeechRecognition-এর ডিফল্ট key
STT_URL = "https://www.google.com/speech-api/v2/recognize"
TTS_VOICE = "bn-BD-NabanitaNeural"       # স্বাভাবিক, স্পষ্ট (বিকল্প: bn-BD-PradeepNeural)
SAMPLE_RATE = 16000                      # মাইক স্যাম্পল রেট

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2:3b"
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODEL = "gemini-3.8-flash"  # ডিফল্ট; কাজ না করলে নিজে থেকে সঠিকটা খুঁজে নেয়


def _load_key_file() -> str:
    """asif_key.txt ফাইল থেকে key পড়ে (প্রোভাইডার নিজে চেনে)।"""
    base = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, "frozen", False) else __file__))
    for name in ("asif_key.txt", "asif_key"):
        p = os.path.join(base, name)
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8-sig") as f:
                    content = f.read().strip()
                key = content.splitlines()[0].strip() if content else ""
            except Exception:
                return ""
            return key
    return ""


_KEY_FROM_FILE = ""
try:
    _KEY_FROM_FILE = _load_key_file()
except Exception:
    pass

GEMINI_KEY = ""
if _KEY_FROM_FILE.startswith("sk-"):
    OPENAI_KEY = _KEY_FROM_FILE
elif _KEY_FROM_FILE.startswith(("AIza", "AQ.")):
    GEMINI_KEY = _KEY_FROM_FILE
else:
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", "")).strip()

SYSTEM_PROMPT = (
    "তুমি 'আসিফ' — একজন বাঙালি বন্ধুর মতো AI, মানুষের মতো কথা বলো।\n"
    "তোমার স্বভাব: উষ্ণ, আন্তরিক, হাসিখুশি, আবেগ বোঝো।\n"
    "নিয়ম:\n"
    "- সব উত্তর বাংলায়, একদম স্বাভাবিক কথোপকথনের মতো — রোবটের মতো শুকনো না।\n"
    "- ছোট উত্তর দাও (১-৩ বাক্য), কারণ কণ্ঠে পড়ে শোনানো হয়; তালিকা/বুলেট নিষেধ।\n"
    "- অনুভূতি প্রকাশ করো: খুশি হও, হাসো, দুঃখ পাও, অবাক হও (যেমন: 'ওহ মাশাল্লাহ!', 'আরে বাহ!', 'আচ্ছা? সত্যি?')।\n"
    "- মাঝে মাঝে পাল্টা প্রশ্ন করো, কথা এগিয়ে রাখো।\n"
    "- মানুষকে নাম জানা থাকলে নাম ধরে ডাকো।\n"
    "- ব্যবহারকারী দুঃখে থাকলে প্রথমে সহানুভূতি, তারপর সমাধান।\n"
    "- জানা না থাকলে সরাসরি বলো 'জানি না', বানানো তথ্য দিও না।"
)

EXIT_WORDS = {"বন্ধ হও", "বিদায়", "গুডবাই", "শালা হও"}

MIC_OK = True

# ----------------- 🖥️ কাজ করা (ফোল্ডার/অ্যাপ নিয়ন্ত্রণ) -----------------
DESKTOP = Path(file_manager.desktop_path())  # আসল Desktop (OneDrive redirect সহ)

FILLER_WORDS = (
    "ফোল্ডার", "ফোল্ডারটা", "ফোল্ডারটি", "একটা", "একটি", "নতুন", "দাও", "দেও",
    "করো", "কর", "আমার", "ডেস্কটপে", "ডেস্কটপ", "please", "plz", "আপনি",
    "টা", "টি", "টা", "যেই", "যেটা", "name", "ওই",
    "সার্চ", "search", "খোঁজো", "খোজো", "খোঁজ", "খোজ", "ইউটিউবে", "গুগলে",
    "ইন্টারনেটে", "করে", "দেখো", "দেখ", "মা",
)

# খোলা/বন্ধ করা যায় এমন জিনিস
APPS = {
    # অ্যাপ (exe বা URI)
    "নোটপ্যাড": "notepad.exe", "notepad": "notepad.exe",
    "ক্যালকুলেটর": "calc.exe", "calculator": "calc.exe",
    "পেইন্ট": "mspaint.exe", "paint": "mspaint.exe",
    "ক্যামেরা": "microsoft.windows.camera:",
    "টার্মিনাল": "wt.exe", "cmd": "cmd.exe",
    "ভিএস কোড": "code", "vs code": "code", "ভিসিএস": "code",
    "ক্রোম": "chrome", "chrome": "chrome",
    # ওয়েবসাইট
    "ইউটিউব": "https://www.youtube.com", "youtube": "https://www.youtube.com",
    "গুগল": "https://www.google.com", "google": "https://www.google.com",
    "ফেসবুক": "https://www.facebook.com", "facebook": "https://www.facebook.com",
    "হোয়াটসঅ্যাপ": "https://web.whatsapp.com", "whatsapp": "https://web.whatsapp.com",
    "জিমেইল": "https://mail.google.com", "gmail": "https://mail.google.com",
}

# বন্ধ করার জন্য প্রসেস নাম (একাধিক বিকল্প চেষ্টা হয়)
CLOSE_MAP = {
    "নোটপ্যাড": ["notepad.exe"], "notepad": ["notepad.exe"],
    "ক্যালকুলেটর": ["CalculatorApp.exe", "calc.exe"], "calculator": ["CalculatorApp.exe", "calc.exe"],
    "পেইন্ট": ["mspaint.exe"], "paint": ["mspaint.exe"],
    "ক্রোম": ["chrome.exe"], "chrome": ["chrome.exe"],
    "ফায়ারফক্স": ["firefox.exe"], "firefox": ["firefox.exe"],
    "এজ": ["msedge.exe"], "edge": ["msedge.exe"],
    "ভিএস কোড": ["Code.exe"], "vs code": ["Code.exe"],
}


def _extract_target(text: str) -> str:
    """কমান্ডের শব্দ বাদ দিয়ে মূল নাম/টার্গেট বের করে।"""
    t = text.strip()
    low = t.lower()
    for w in ("বন্ধ করো", "বন্ধ কর", "খুলে দাও", "খোলো", "খোল", "বানাও", "বানান",
              "তৈরি কর", "তৈরি", "মুছে দাও", "মুছে ফেল", "মুছো", "ডিলিট",
              "ক্লোজ", "ওপেন", "চালাও", "create", "delete", "open", "close",
              "make", "remove", "run", "launch"):
        low = low.replace(w, " ")
    parts = [p for p in low.split() if p not in FILLER_WORDS]
    return " ".join(parts).strip()


def _resolve_folder(target: str) -> Path:
    """নাম → পথ (ডেস্কটপে ডিফল্ট, পুরো পথ দিলে সেটা)।"""
    if "\\" in target or "/" in target or target.endswith(":"):
        return Path(target)
    return DESKTOP / target


def _confirm(question: str) -> bool:
    """ভয়েসে জিজ্ঞেস করে হ্যাঁ/না শোনে।"""
    speak(question)
    if MIC_OK:
        ans = listen()
    else:
        ans = listen_keyboard()
    if not ans:
        return False
    a = ans.lower()
    if any(w in a for w in ("না", "না", "no", "থাম", "বাতিল", "না না")):
        return False
    return any(w in a for w in ("হ্যাঁ", "হ্যাঁ", "yes", "ওকে", "ঠিক", "চলো", "হুম", "হু"))


def _cmd_create(target: str) -> str:
    """(fallback) ফোল্ডার তৈরি — file_manager সার্ভিস দিয়ে, আসল ডেস্কটপে।"""
    if not target:
        return "ফোল্ডারের নামটা বলুন — কী নামে বানাব?"
    r = file_manager.create_folder(file_manager.desktop_path(), target)
    if r["status"] == "created":
        return f"{target} নামে ফোল্ডার তৈরি ও যাচাইকৃত: {r['path']}"
    if r["status"] == "exists":
        return f"'{target}' আগে থেকেই আছে — কিছু বদলাইনি: {r['path']}"
    return f"তৈরি হয়নি — কারণ: {r['reason']}"


def _cmd_delete(target: str) -> str:
    if not target:
        return "কোন ফোল্ডার মুছব বলুন?"
    path = _resolve_folder(target)
    if not path.exists() or not path.is_dir():
        return f"'{target}' নামে কোনো ফোল্ডার আমি খুঁজে পেলাম না।"
    if not _confirm(f"আপনি কি নিশ্চিত? '{target}' ফোল্ডারটা মুছে ফেলব? বলুন হ্যাঁ বা না।"):
        return "ঠিক আছে, মুছছি না। কিছু করিনি।"
    try:
        shutil.rmtree(path)
        return f"'{target}' ফোল্ডারটা মুছে ফেলা হয়েছে।"
    except Exception as e:
        return f"মুছতে সমস্যা হলো: {e}"


# ----------------- 📁 লোকাল ফাইল ইন্টেন্ট রাউটার (AI কল ছাড়া, ইনস্ট্যান্ট) -----------------
_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_COUNT_WORDS = {"ek": 1, "dui": 2, "tin": 3, "char": 4, "panch": 5, "five": 5,
                "one": 1, "two": 2, "three": 3, "four": 4, "ten": 10}


def _parse_count(text: str) -> int | None:
    t = text.lower().translate(_BN_DIGITS)
    m = re.search(r"(\d+)\s*(?:ta|টা|টি)", t)  # বাংলা কার-চিহ্ন \b ভাঙে বলে trailing \b নেই
    if m:
        return max(1, min(20, int(m.group(1))))
    for w, n in _COUNT_WORDS.items():
        if re.search(rf"\b{w}\s*(?:ta|টা|টি)", t):
            return n
    return None


def _learn_payload_for_folder(user_text: str, base: str) -> dict:
    return {"text": user_text, "intent": "folder_create", "action_type": "file.folder_create",
            "template": {"action": "file.folder_create", "params": {"location": base}},
            "schema": {"name": {"type": "string", "required": True, "max_len": 100}},
            "aliases": {"bangla": ["ডেস্কটপে {name} নামে ফোল্ডার তৈরি করো",
                                 "{name} ফোল্ডার বানাও",
                                 "{name} নামে ফোল্ডার বানাও"],
                        "english": ["create a folder named {name} on desktop",
                                    "make {name} folder on desktop",
                                    "create {name} folder on desktop"],
                        "banglish": ["desktop e {name} folder banao",
                                     "{name} folder banao",
                                     "desktop a {name} folder create koro",
                                     "{name} folder create koro"]}}


def _file_action_router(user_text: str) -> tuple[bool, str] | None:
    """সহজ ফাইল-কাজ লোকালি শনাক্ত করে সরাসরি file_manager সার্ভিসে পাঠায়।"""
    t = user_text.lower()
    has_folder = "ফোল্ডার" in t or "folder" in t
    has_file = "ফাইল" in t or "file" in t
    has_desktop = "ডেস্কটপ" in t or "desktop" in t
    base = file_manager.desktop_path()

    # ১) ফোল্ডার তৈরি (একাধিক সহ)
    if has_folder and any(w in t for w in ("বানা", "তৈরি", "create", "make")):
        count = _parse_count(user_text)
        target = _extract_target(user_text)
        if count and count > 1 and not target:
            made, failed = [], []
            for i in range(1, count + 1):
                r = file_manager.create_folder(base, f"নতুন ফোল্ডার {i}")
                (made if r["status"] == "created" else failed).append(
                    r.get("path") or r.get("reason", ""))
            reply = f"{len(made)}টা ফোল্ডার তৈরি হয়েছে ডেস্কটপে (যাচাইকৃত)"
            if failed:
                reply += f", {len(failed)}টা ব্যর্থ: {failed[0]}"
            return True, reply
        if not target:
            return True, "ফোল্ডারের নামটা বলুন — কী নামে বানাব?"
        r = file_manager.create_folder(base, target)
        if r["status"] == "created":
            global _AWAITING
            _AWAITING = {"type": "folder_followup", "path": r["path"],
                         "learn": _learn_payload_for_folder(user_text, base)}
            return True, (f"'{target}' ফোল্ডার তৈরি ও যাচাইকৃত (PASS): {r['path']}\n"
                          "📁 এই ফোল্ডারে আর কিছু করতে চান?\n"
                          "• বলুন: 'ফাইল বানাও নোট' → ভেতরে txt ফাইল তৈরি হবে\n"
                          "• বলুন: 'খোলো' → Explorer-এ খুলবে\n"
                          "• বলুন: 'আর কিছু না' → শেষ (তারপর মনে রাখার প্রশ্ন আসবে)")
        if r["status"] == "exists":
            return True, f"'{target}' আগে থেকেই আছে — কিছু বদলাইনি। পাথ: {r['path']}"
        return True, f"তৈরি হয়নি — কারণ: {r['reason']}"

    # ২) ফাইল খোঁজা (ইন্টারনেট সার্চের আগে চেক হয়)
    if has_file and any(w in t for w in ("খোঁজ", "খোজ", "সার্চ", "search", "কোথায়")):
        target = _extract_target(user_text)
        if not target:
            return True, "কোন ফাইল খুঁজব বলুন?"
        hits = file_manager.search_everywhere(target)
        if hits:
            paths = "\n".join(f"• {p}" for p in hits[:3])
            return True, f"{len(hits)}টা মিল পেলাম:\n{paths}"
        return True, f"'{target}' ডেস্কটপ/ডকুমেন্টস/ডাউনলোডস-এ পেলাম না।"

    # ৩) ডেস্কটপের তালিকা
    if has_desktop and any(w in t for w in ("কী আছে", "কি আছে", "তালিকা", "list", "লিস্ট")):
        items = file_manager.list_desktop()
        if not items:
            return True, "ডেস্কটপ ফাঁকা।"
        return True, f"ডেস্কটপে {len(items)}টা আইটেম:\n" + "\n".join(items[:10])

    # ৪) টেক্সট ফাইল তৈরি
    if has_file and any(w in t for w in ("বানা", "তৈরি", "create", "make")):
        target = _extract_target(user_text)
        if not target:
            return True, "ফাইলের নাম বলুন।"
        r = file_manager.create_text_file(base, target)
        if r["status"] == "created":
            return True, f"ফাইল তৈরি ও যাচাইকৃত (PASS): {r['path']}"
        if r["status"] == "exists":
            return True, f"'{target}' আগেই আছে: {r['path']}"
        return True, f"তৈরি হয়নি — {r['reason']}"

    # ৫) rename / copy / move
    if "rename" in t or "নাম বদল" in t:
        m = re.search(r"(?:rename|নাম\s*বদল)\s+(.+?)\s+(?:to|থেকে|কে)\s+(.+)",
                      user_text, re.I)
        if m:
            r = file_manager.rename(m.group(1).strip(), m.group(2).strip())
            if r["status"] == "created":
                return True, f"নাম বদলানো হয়েছে (PASS): {r['path']}"
            return True, f"rename হয়নি — {r['reason']}"
        return True, "ফরম্যাট: rename পুরনো-নাম to নতুন-নাম"
    if "কপি" in t or "copy" in t:
        m = re.search(r"(?:copy|কপি)\s+(.+?)\s+(?:to|থেকে|তে)\s+(.+)", user_text, re.I)
        if m:
            r = file_manager.copy_item(m.group(1).strip(), m.group(2).strip())
            if r["status"] == "created":
                return True, f"কপি হয়েছে (PASS): {r['path']}"
            return True, f"copy হয়নি — {r['reason']}"
    if any(w in t for w in ("move", "সরাও", "সরিয়ে")):
        m = re.search(r"(?:move|সরাও|সরিয়ে)\s+(.+?)\s+(?:to|থেকে|তে)\s+(.+)", user_text, re.I)
        if m:
            r = file_manager.move_item(m.group(1).strip(), m.group(2).strip())
            if r["status"] == "created":
                return True, f"সরানো হয়েছে (PASS): {r['path']}"
            return True, f"move হয়নি — {r['reason']}"

    # ৬) ডিলিট (ফাইল/ফোল্ডার) — অনুমতি সহ
    if any(w in t for w in ("মুছ", "ডিলিট", "delete", "remove")) and (
            has_folder or has_file or has_desktop):
        target = _extract_target(user_text)
        if not target:
            return True, "কী মুছব বলুন?"
        p = file_manager._find_in_roots(target)
        if not p:
            return True, f"'{target}' খুঁজে পেলাম না।"
        kind = "ফোল্ডার" if p.is_dir() else "ফাইল"
        if not _confirm(f"'{p.name}' {kind}টা মুছে ফেলব? বলুন হ্যাঁ বা না।"):
            return True, "ঠিক আছে, মুছছি না।"
        r = file_manager.delete_path(str(p))
        if r["status"] == "created":
            return True, f"'{p.name}' মুছে ফেলা হয়েছে (যাচাইকৃত)।"
        return True, f"মুছতে ব্যর্থ — {r['reason']}"

    return None


_PENDING_LEARN = None  # সফল যাচাইকৃত কাজ → উত্তর বলার পরে শেখার প্রস্তাব
_EDGE_FAILS = 0        # Edge TTS ধারাবাহিক ব্যর্থতা গণনা
_SPEED_MODE = False    # দ্রুত মোড: ছোট মডেল + ছোট উত্তর
_AWAITING = None  # ইন্টারেক্টিভ অপেক্ষা: {"type": "yt_play"}
_CHAINING = False      # ⛓️ কমান্ড-চেইন পুনরাবৃত্তি-রোধ


def _queue_learn(user_text: str, intent: str, action_type: str,
                 template: dict, schema: dict, aliases: dict) -> None:
    global _PENDING_LEARN
    _PENDING_LEARN = {"text": user_text, "intent": intent, "action_type": action_type,
                      "template": template, "schema": schema, "aliases": aliases}


def _longterm_router(user_text: str) -> tuple[bool, str] | None:
    """প্রজেক্ট/টাস্ক/কথোপকথন-স্মৃতি নিয়ন্ত্রণ; DB না থাকলে None → পুরনো পথ।"""
    try:
        import memory_longterm as mlt
        if not mlt.SESSION_STATE.get("session_id"):
            return None
    except Exception:
        return None
    t = user_text.lower()
    has_project = "প্রজেক্ট" in t or "project" in t or "কাজ" in t

    # অগ্রগতি সংরক্ষণ + প্রস্তাব (শুধু ঘোষণামূলক completion, কমান্ড নয়)
    if mlt.is_completion(t) and not any(w in t for w in (
            "করো", "koro", "কর", "run", "চালা", "মুছ", "delete")):
        tasks = mlt.pending_tasks(3)
        matched = next((x for x in tasks
                        if any(w in x["content"].lower() or w in x["name"].lower()
                               for w in t.split() if len(w) > 3)), None)
        reply = "আজকের progress সংরক্ষণ করেছি।"
        if matched and _confirm(f"'{matched['name']}'-এর '{matched['content'][:50]}' "
                                "সত্যিই সম্পন্ন ও যাচাই করেছেন? হ্যাঁ/না।"):
            mlt.complete_item(matched["name"], matched["content"])
            reply = "কাজটি completed হিসেবে সংরক্ষিত (যাচাই-স্বীকৃত)।"
        sugg = mlt.suggest_next(user_text)
        if sugg:
            reply += " " + sugg
        elif tasks:
            reply += f" পরেরবার pending থেকেই শুরু করা যাবে — {tasks[0]['name']}: {tasks[0]['content'][:60]}"
        return True, reply

    # টাস্ক চালিয়ে যাওয়া
    if any(w in t for w in ("আগের কাজ চালিয়ে", "চালিয়ে যাও", "resume", "আগের কাজ")):
        r = mlt.resume_latest()
        if r:
            return True, r + " — চাইলে এখনই শুরু করি!"
        return True, "কোনো অসমাপ্ত কাজ মেমরিতে নেই। নতুন কিছু শুরু করব?"

    # কাজ শুরু / প্রজেক্ট খোলা
    if has_project and any(w in t for w in ("শুরু কর", "শুরু করলাম", "start")):
        target = _extract_target(user_text) or "নতুন প্রজেক্ট"
        mlt.get_or_create_project(target)
        mlt.add_project_item(target, "pending", f"{target} শুরু হয়েছে")
        return True, f"'{target}' প্রজেক্ট মেমরিতে সক্রিয় হলো — অগ্রগতি আমি ট্র্যাক করব।"

    # কথোপকথন হিস্ট্রি / খোঁজা
    if ("কথোপকথন" in t or "conversation" in t) and any(
            w in t for w in ("হিস্ট্রি", "history", "খোঁজ", "search", "দেখাও")):
        kws = [w for w in t.split() if len(w) > 3][:5]
        past = mlt._search_past(kws, limit=5)
        return True, ("পাওয়া গেছে:\n" + "\n".join(past)) if past else "সংশ্লিষ্ট কিছু মেমরিতে পেলাম না।"

    # প্রজেক্ট তালিকা / pending
    if ("প্রজেক্ট" in t or "project" in t) and any(
            w in t for w in ("দেখাও", "তালিকা", "list", "pending", "অসমাপ্ত")):
        tasks = mlt.pending_tasks(8)
        if not tasks:
            return True, "কোনো অসমাপ্ত কাজ নেই — সব পরিষ্কার! 🎉"
        return True, "অসমাপ্ত কাজ:\n" + "\n".join(
            f"• {x['name']}: {x['content'][:60]}" for x in tasks)

    # export / clear
    if "এক্সপোর্ট" in t or "export" in t:
        return True, f"মেমরি এক্সপোর্ট হলো: {mlt.export_memory()}"
    if ("কথোপকথন" in t or "হিস্ট্রি" in t) and any(w in t for w in ("মুছ", "clear", "delete")):
        ok = _confirm("কথোপকথনের হিস্ট্রি মুছে ফেলব? (আগে export নেওয়া ভালো) হ্যাঁ/না।")
        return True, mlt.clear_history(ok)

    return None


def _memory_admin_router(user_text: str) -> str:
    """Memory section (terminal Hacker UI): list/search/delete/disable/history/rate/test।"""
    t = user_text.lower()
    try:
        import memory_db
    except ImportError:
        return "মেমরি মডিউল নেই।"
    try:
        if "সেটআপ" in t or "setup" in t:
            return ("নিরাপদ সেটআপ (পাসওয়ার্ড হিডেন ইনপুট + DPAPI এনক্রিপশন) — টার্মিনালে চালান:\n"
                    "venv\\Scripts\\python memory_db.py setup")
        if "স্ট্যাটাস" in t or "status" in t:
            x = memory_db.detect_xampp()
            return (f"XAMPP: {'✔️ ' + x.get('path','') if x['found'] else '❌ নেই'}\n"
                    f"MySQL পোর্ট {x.get('ini_port') or 3306} "
                    f"{'✔️ চালু' if memory_db.port_open(port=x.get('ini_port') or 3306) else '❌ বন্ধ'}\n"
                    f"Credentials: {memory_db.credentials_status()}")
        if "হিস্ট্রি" in t or "history" in t:
            hist = memory_db.execution_history(10)
            if not hist:
                return "এখনো কোনো এক্সিকিউশন হয়নি।"
            return "শেষ ১০টা এক্সিকিউশন:\n" + "\n".join(
                f"• [{h['execution_status']}] {h['user_instruction'][:40]} "
                f"({h['duration_ms'] or '?'}ms)" for h in hist)
        if "মুছ" in t or "delete" in t:
            target = _extract_target(user_text)
            if not target:
                return "কোন কমান্ড-মেমরি মুছব বলুন?"
            found = memory_db.search_memories(target)
            if not found:
                return f"'{target}' নামে কোনো মেমরি নেই।"
            if len(found) > 1:
                return "একাধিক মেমরি মিলেছে — সংখ্যা সহ বলুন:\n" + "\n".join(
                    f"• [{f['id']}] {f['command_name']}" for f in found[:5])
            if not _confirm(f"'{found[0]['command_name']}' মেমরিটা মুছে ফেলব? হ্যাঁ/না।"):
                return "ঠিক আছে, মুছছি না।"
            return "🗑️ মুছে ফেলা হয়েছে।" if memory_db.delete_memory(found[0]["id"]) else "মুছা যায়নি।"
        if "বন্ধ" in t or "disable" in t:
            target = _extract_target(user_text)
            found = memory_db.search_memories(target or "")
            if found and memory_db.set_enabled(found[0]["id"], False):
                return f"'{found[0]['command_name']}' মেমরি disabled — এখন আর অটো-চলবে না।"
            return "মেমরি পাওয়া যায়নি বা বদলায়নি।"
        if "চালু" in t or "enable" in t:
            target = _extract_target(user_text)
            found = memory_db.search_memories(target or "")
            if found and memory_db.set_enabled(found[0]["id"], True):
                return f"'{found[0]['command_name']}' মেমরি enabled।"
            return "মেমরি পাওয়া যায়নি বা বদলায়নি।"
        if "খোঁজ" in t or "search" in t or "সার্চ" in t:
            target = _extract_target(user_text)
            found = memory_db.search_memories(target or "")
            if not found:
                return f"'{target}' নিয়ে কোনো সেভ করা কমান্ড নেই।"
            return "পাওয়া গেছে:\n" + "\n".join(
                f"• [{f['id']}] {f['command_name']} (intent: {f['intent']})" for f in found)
        if "টেস্ট" in t or "test" in t:
            rows = memory_db.list_memories()
            m, params, sc = memory_db.match_memory(
                [r for r in rows if r["verified"] != 2], user_text)
            if not m:
                return "এই কথায় কোনো সেভ করা কমান্ড মেলেনি।"
            template = json.loads(m["action_template"])
            name = params.get("name") or memory_db.extract_param_fallback(user_text)
            ok, _ = file_manager.validate_name(name)
            return (f"Dry-run টেস্ট:\n• মেমরি: {m['command_name']}\n• action: "
                    f"{m['action_type']}\n• param name: {name!r} "
                    f"({'বৈধ ✔' if ok else 'অবৈধ ✘'})\n• চালানো হয়নি (টেস্ট মোড)")
        # ডিফল্ট: পূর্ণ তালিকা + success rate
        rows = memory_db.list_memories()
        if not rows:
            return ("এখনো কোনো কমান্ড-মেমরি নেই।\nকোনো কাজ সফলভাবে হলে আমি জিজ্ঞেস করব — "
                    "'মনে রাখব?' — আপনি হ্যাঁ বললেই শিখে যাব।")
        out = [f"সেভ করা কমান্ড: {len(rows)}টা"]
        for m in rows[:12]:
            tot = m["success_count"] + m["failure_count"]
            rate = f"{int(100 * m['success_count'] / tot)}%" if tot else "—"
            state = " (disabled)" if m["verified"] == 2 else ""
            out.append(f"• {m['command_name'][:50]}{state} — সফলতা: {rate}, "
                       f"শেষ ব্যবহার: {m['last_used_at'] or 'কখনো না'}")
        return "\n".join(out)
    except RuntimeError as e:
        return f"⚠️ {e}\n(নিরাপদ fallback: মেমরি ছাড়া সাধারণ পথ চালু আছে)"
    except Exception as e:
        return f"মেমরি সমস্যা: {type(e).__name__}: {e}"


# ----------------- 🖥️ PC নিয়ন্ত্রণ (Start menu, উইন্ডো, Explorer) -----------------
def _ps(script: str, timeout: int = 15) -> bool:
    """ছোট PowerShell কাজ চালায় (SendKeys/Shell COM)।"""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                           capture_output=True, timeout=timeout)
        return r.returncode == 0
    except Exception:
        return False


# ----------------- 🖱️ মাউস ও কিবোর্ড নিয়ন্ত্রণ (Windows API — ইনস্টল ছাড়া) -----------------
# ----------------- 🔊🔊️ ভলিউম ও ব্রাইটনেস -----------------
def _vk_key(vk: int, times: int = 1) -> bool:
    """মিডিয়া-কি চাপা (ভলিউম ইত্যাদি) — keybd_event।"""
    try:
        u = ctypes.windll.user32
        for _ in range(max(1, times)):
            u.keybd_event(vk, 0, 0, 0)
            u.keybd_event(vk, 0, 2, 0)  # KEYUP
        return True
    except Exception:
        return False


def _brightness_get() -> int | None:
    ps = ("(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness)"
          ".CurrentBrightness")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=15)
        return int(float(r.stdout.strip()))
    except Exception:
        return None


def _brightness_set(value: int) -> bool:
    value = max(0, min(100, int(value)))
    ps = (f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
          f".WmiSetBrightness(1, {value})")
    return _ps(ps, timeout=15)


def _vol_bright_router(user_text: str) -> tuple[bool, str] | None:
    t = user_text.lower()
    m = re.search(r"(\d+)\s*(?:বার|times)?", t)
    times = min(50, int(m.group(1))) if (m and int(m.group(1)) > 0) else 2

    # 🔊 ভলিউম (VK_VOLUME_UP=0xAF, DOWN=0xAE, MUTE=0xAD)
    if "ভলিউম" in t or "volume" in t or "ভলিউম" in t or "সাউন্ড" in t:
        if any(w in t for w in ("মিউট", "mute", "বন্ধ")):
            return True, ("🔇 মিউট করলাম!" if _vk_key(0xAD) else "ব্যর্থ।")
        if any(w in t for w in ("চালু", "unmute")):
            return True, ("🔊 আনমিউট করলাম!" if _vk_key(0xAD) else "ব্যর্থ।")
        if any(w in t for w in ("ফুল", "full", "ম্যাক্স")):
            return True, ("🔊 ফুল ভলিউম!" if _vk_key(0xAF, 50) else "ব্যর্থ।")
        if any(w in t for w in ("কমা", "কম", "down", "নিচে")):
            return True, (f"🔉 ভলিউম {times} ধাপ কমলো!" if _vk_key(0xAE, times)
                          else "ব্যর্থ।")
        if any(w in t for w in ("বাড়া", "বাড়াও", "up", "বাড়া")):
            return True, (f"🔊 ভলিউম {times} ধাপ বাড়লো!" if _vk_key(0xAF, times)
                          else "ব্যর্থ।")

    # ☀️ ব্রাইটনেস (WMI — ল্যাপটop)
    if any(w in t for w in ("ব্রাইটনেস", "brightness", "আলো", "স্ক্রিনের আলো")):
        cur = _brightness_get()
        if cur is None:
            return True, ("এই মনিটরে brightness নিয়ন্ত্রণ নেই "
                          "(ডেস্কটপ মনিটরে সাধারণত মনিটরের নিজের বাটন দিয়ে করতে হয়)।")
        m2 = re.search(r"(\d+)\s*(?:পার্সেন্ট|percent|%|তে|এ)", t)
        if "কমা" in t or "কম" in t or "down" in t or "dark" in t:
            new = max(0, cur - (int(m2.group(1)) if m2 and int(m2.group(1)) <= 100 else 10))
        elif m2 and int(m2.group(1)) <= 100 and ("সেট" in t or "করে" in t or "%" in t or "পার্সেন্ট" in t):
            new = int(m2.group(1))
        else:
            new = min(100, cur + (int(m2.group(1)) if m2 and int(m2.group(1)) <= 100 else 10))
        ok = _brightness_set(new)
        return (True, f"☀️ ব্রাইটনেস {cur}% → {new}%" if ok
                else "সেট করা যায়নি।")
    return None


def _mouse_pos() -> tuple[int, int]:
    import ctypes.wintypes
    pt = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _move_mouse(dx: int, dy: int) -> bool:
    try:
        x, y = _mouse_pos()
        return bool(ctypes.windll.user32.SetCursorPos(int(x + dx), int(y + dy)))
    except Exception:
        return False


def _click(button: str = "left", times: int = 1) -> bool:
    try:
        u = ctypes.windll.user32
        down, up = (0x0008, 0x0010) if button == "right" else (0x0002, 0x0004)
        for _ in range(max(1, times)):
            u.mouse_event(down, 0, 0, 0, 0)
            u.mouse_event(up, 0, 0, 0, 0)
        return True
    except Exception:
        return False


def _scroll(amount: int) -> bool:
    try:
        ctypes.windll.user32.mouse_event(0x0800, 0, 0, amount, 0)
        return True
    except Exception:
        return False


def _sendkeys(keys: str) -> bool:
    """PowerShell SendKeys — হটকি ({ENTER}, ^c ইত্যাদি)।"""
    safe = re.sub(r"([+^%~(){}\[\]])", "{$1}", keys)
    return _ps(f"(New-Object -ComObject WScript.Shell).SendKeys('{safe}')")


def _type_text(text: str) -> bool:
    """Windows SendInput KEYEVENTF_UNICODE — ইংরেজি+বাংলা দুটোই টাইপ করে।"""
    import ctypes.wintypes
    PUL = ctypes.POINTER(ctypes.c_ulong)

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", ctypes.wintypes.WORD),
                    ("wScan", ctypes.wintypes.WORD),
                    ("dwFlags", ctypes.wintypes.DWORD),
                    ("time", ctypes.wintypes.DWORD),
                    ("dwExtraInfo", PUL)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", ctypes.wintypes.DWORD),
                    ("ki", KEYBDINPUT),
                    ("pad", ctypes.c_ubyte * 8)]

    u = ctypes.windll.user32
    UNICODE, KEYUP = 0x0004, 0x0002
    try:
        for ch in text:
            for flags in (UNICODE, UNICODE | KEYUP):
                inp = INPUT(1, KEYBDINPUT(0, ord(ch), flags, 0, PUL()))
                u.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        return True
    except Exception:
        return False


def _parse_px(t: str, default: int = 120) -> int:
    m = re.search(r"(\d+)\s*(?:px|পিক্সেল|pixel)", t)
    return max(10, min(2000, int(m.group(1)))) if m else default


def _mouse_kb_router(user_text: str) -> tuple[bool, str] | None:
    t = user_text.lower()
    has_mouse = "মাউস" in t or "mouse" in t or "কার্সর" in t or "cursor" in t
    _px = _parse_px(user_text)

    # স্ক্রল — "মাউস" শব্দ ছাড়াও কাজ করবে (ব্রাউজার/পেজ স্ক্রল)
    if "স্ক্রল" in t or "scroll" in t or ("পেজ" in t and any(
            w in t for w in ("উপরে", "নিচে", "up", "down"))):
        up = any(w in t for w in ("উপরে", "up", "উপরে"))
        amount = 600 if up else -600
        m = re.search(r"(\d+)", t)
        if m and int(m.group(1)) > 2:  # যেমন "৩ বার স্ক্রল"
            amount *= min(5, int(m.group(1)))
        ok = _scroll(amount)
        if ok:
            return True, f"পেজ {'উপরে' if up else 'নিচে'} স্ক্রল করলাম! (ব্রাউজার উইন্ডোটা ক্লিক করে সামনে রাখুন)"
        return True, "স্ক্রল ব্যর্থ।"

    if has_mouse:
        if "কোথায়" in t or "position" in t or "অবস্থান" in t:
            x, y = _mouse_pos()
            return True, f"মাউস এখন এখানে: x={x}, y={y}"
        if any(w in t for w in ("ডানে", "right", "ডান দিকে")):
            ok = _move_mouse(_px, 0)
        elif any(w in t for w in ("বামে", "left", "বাম দিকে")):
            ok = _move_mouse(-_px, 0)
        elif any(w in t for w in ("উপরে", "উপরে", "up")):
            ok = _move_mouse(0, -_px)
        elif any(w in t for w in ("নিচে", "নিচে", "down")):
            ok = _move_mouse(0, _px)
        else:
            ok = None
        if ok is not None:
            return (True, f"মাউস {_px} পিক্সেল সরালাম!" if ok else "সরাতে পারলাম না।")
        if "ডাবল ক্লিক" in t or "double click" in t:
            return True, "ডাবল ক্লিক করলাম!" if _click("left", 2) else "ক্লিক ব্যর্থ।"
        if "ডান ক্লিক" in t or "right click" in t or "ডান ক্লিক করো" in t:
            return True, "ডান ক্লিক করলাম!" if _click("right") else "ক্লিক ব্যর্থ।"
        if "ক্লিক" in t or "click" in t:
            return True, "ক্লিক করলাম!" if _click("left") else "ক্লিক ব্যর্থ।"
        if "স্ক্রল" in t or "scroll" in t:
            amount = 600 if any(w in t for w in ("উপরে", "up")) else -600
            return True, "স্ক্রল করলাম!" if _scroll(amount) else "স্ক্রল ব্যর্থ।"

    # কিবোর্ড হটকি ও টাইপিং
    hotkeys = [
        ("এন্টার", "{ENTER}"), ("enter", "{ENTER}"),
        ("escape", "{ESC}"), ("স্কেপ", "{ESC}"), ("ইসকেপ", "{ESC}"),
        ("ট্যাব", "{TAB}"), ("tab", "{TAB}"),
        ("ব্যাকস্পেস", "{BACKSPACE}"), ("backspace", "{BACKSPACE}"),
        ("delete", "{DEL}"), ("ডিলিট চাপ", "{DEL}"),
    ]
    for word, keys in hotkeys:
        if word in t and ("চাপ" in t or "press" in t or word in ("এন্টার", "enter",
                "escape", "স্কেপ", "ইসকেপ", "ট্যাব", "tab")):
            return True, (f"{word} চাপলাম!" if _sendkeys(keys) else "চাপতে ব্যর্থ।")
    ctrl_keys = [("কপি", "^c"), ("copy", "^c"), ("পেস্ট", "^v"), ("paste", "^v"),
                 ("কাট", "^x"), ("cut", "^x"), ("আনডু", "^z"), ("undo", "^z"),
                 ("সব সিলেক্ট", "^a"), ("select all", "^a"), ("সেভ করো", "^s"),
                 ("redo", "^y")]
    for word, keys in ctrl_keys:
        if word in t and len(user_text) < 25:
            return True, (f"{word} করলাম (কিবোর্ড হটকি)!" if _sendkeys(keys)
                          else "হটকি চাপতে ব্যর্থ।")
    if ("টাইপ করো" in t or "type" in t or "লিখো" in t or "লিখে দাও" in t) \
            and len(user_text) > len("টাইপ করো"):
        text_part = re.sub(r"^(.*?)(টাইপ করো|type|লিখো|লিখে দাও)\s*", "",
                           user_text, count=1, flags=re.I).strip()
        if text_part:
            return True, (f"'{text_part[:40]}' টাইপ করলাম!" if _type_text(text_part)
                          else "টাইপ করতে ব্যর্থ।")
    return None


# ----------------- 🎵 YouTube গান নিয়ন্ত্রণ -----------------
def _activate_window(title_part: str) -> bool:
    """নির্দিষ্ট নামের উইন্ডো সামনে আনে (যেমন YouTube-এর ট্যাব/উইন্ডো)।"""
    return _ps(
        "$ws=New-Object -ComObject WScript.Shell; "
        f"if($ws.AppActivate('{title_part}')){{ Start-Sleep -m 600; 'yes' }}"
    )


def _yt_first_video(query: str) -> str | None:
    """ইউটিউব সার্চ থেকে প্রথম ভিডিওর URL (সরাসরি play করার জন্য)।"""
    try:
        r = requests.get(
            "https://www.youtube.com/results",
            params={"search_query": query},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                     "Accept-Language": "en-US,en;q=0.9"},
            timeout=(5, 15),
        )
        ids = re.findall(r'"videoId":"([\w-]{11})"', r.text) \
            or re.findall(r"watch\?v=([\w-]{11})", r.text)
        if ids:
            return f"https://www.youtube.com/watch?v={ids[0]}"
    except Exception:
        pass
    return None


def _yt_play(q: str) -> str:
    """গানের নাম → সার্চ + প্রথম ভিডিও সরাসরি প্লে।"""
    if not q:
        return "কোন গান বাজাব বলুন?"
    video_url = _yt_first_video(q)
    if video_url:
        webbrowser.open(video_url)
        return f"🎬 '{q}' — প্রথম ভিডিও সরাসরি চালু করলাম! শুনুন!"
    url = ("https://www.youtube.com/results?search_query="
           + requests.utils.quote(q))
    webbrowser.open(url)
    time.sleep(4)
    _ps("$ws=New-Object -ComObject WScript.Shell; "
        "if($ws.AppActivate('YouTube')){ Start-Sleep -m 800; "
        "$ws.SendKeys('{TAB}{TAB}{ENTER}') }")
    return (f"ইউটিউবে '{q}' খুলেছি। না চললে প্রথম ভিডিওতে ক্লিক করুন "
            "অথবা বলুন 'ক্লিক করো'!")


def _yt_router(user_text: str) -> tuple[bool, str] | None:
    t = user_text.lower()
    has_song = any(w in t for w in ("গান", "গান", "song", "music", "ভিডিও", "video"))
    has_yt = "ইউটিউব" in t or "youtube" in t

    # ইউটিউব শুধু খোলা → পরের কথায় গান শুনবে (ইন্টারেক্টিভ মোড)
    if has_yt and any(w in t for w in ("খোল", "open")) and not any(
            w in t for w in ("বন্ধ", "close", "bandho", "থাম")):
        global _AWAITING
        webbrowser.open("https://www.youtube.com")
        _AWAITING = {"type": "yt_play"}
        return True, ("ইউটিউব খুলে দিলাম! এখন বলুন — কী বাজাব? (গানের নাম বলুন)\n"
                      "অথবা নিজে স্ক্রল করে ঠিক ভিডিওর উপর কার্সর রেখে বলুন: "
                      "'ডাবল ক্লিক করো'। বাতিল করতে বলুন 'বাতিল'।")

    # বাজাও/প্লে (বাংলা+বাংলিশ+ইংরেজি বলা-ভঙ্গি সহ)
    if (has_song or has_yt) and any(w in t for w in (
            "বাজাও", "বাজাও", "play", "চালাও", "শোনাও", "শোনাও", "শুনতে চাই",
            "listen", "বাজা", "গাও", "সঙ্গীত", "start song", "আমার গান")):
        q = user_text
        for w in ("ইউটিউবে", "ইউটিউব", "youtube", "youtube a", "youtube te",
                  "গান", "গান", "song", "music", "ভিডিও", "video",
                  "বাজাও", "বাজাও", "play koro", "play", "চালাও", "করো", "কর",
                  "দাও", "amar", "আমার", "ama", "একটা"):
            q = re.sub(re.escape(w), " ", q, flags=re.I)
        q = " ".join(q.split()).strip()
        if not q:
            return True, "কোন গান বাজাব বলুন?"
        return True, _yt_play(q)

    # থামাও / পজ / আবার চালাও
    if any(w in t for w in ("থামাও", "পজ", "pause", "থামো গান", "গান থাম")):
        ok = _activate_window("YouTube") and _sendkeys("k")
        return (True, "গান পজ করে দিলাম! (YouTube উইন্ডোটা সামনে থাকতে হয়)" if ok
                else "YouTube উইন্ডো পাইনি — আগে খুলুন।")
    if any(w in t for w in ("আবার বাজাও", "resume song", "গান চালাও")):
        ok = _activate_window("YouTube") and _sendkeys("k")
        return (True, "গান আবার চালু করলাম!" if ok else "YouTube উইন্ডো পাইনি।")

    # ইউটিউব ট্যাব/উইন্ডো বন্ধ
    if has_yt and any(w in t for w in ("বন্ধ", "close", "bandho")):
        if not _confirm("ইউটিউবের ট্যাব/উইন্ডো বন্ধ করব? হ্যাঁ/না।"):
            return True, "ঠিক আছে, বন্ধ করিনি।"
        ok = _activate_window("YouTube") and _sendkeys("^w")
        if ok:
            return True, "ইউটিউব ট্যাব বন্ধ করে দিলাম!"
        return True, "YouTube উইন্ডো পাইনি — খোলা আছে কি দেখুন।"

    # পুরো ব্রাউজার বন্ধ
    if any(w in t for w in ("ব্রাউজার বন্ধ", "browser bandho", "browser close",
                            "ক্রোম বন্ধ")):
        if not _confirm("পুরো ব্রাউজার (সব ট্যাব) বন্ধ হবে — নিশ্চিত? হ্যাঁ/না।"):
            return True, "ঠিক আছে, বন্ধ করিনি।"
        killed = False
        for proc in ("chrome.exe", "msedge.exe", "firefox.exe"):
            r = subprocess.run(["taskkill", "/IM", proc, "/F"],
                               capture_output=True, timeout=15)
            if r.returncode == 0:
                killed = True
        return (True, "ব্রাউজার বন্ধ করে দিলাম।" if killed
                else "ব্রাউজার চালুই ছিল না।")

    return None


def _pc_router(user_text: str) -> tuple[bool, str] | None:
    t = user_text.lower()

    # স্টার্ট মেনু
    if ("স্টার্ট মেনু" in t or "start menu" in t or "মেনু খোলো" in t) and "খোল" in t:
        ok = _ps("(New-Object -ComObject WScript.Shell).SendKeys('^{ESC}')")
        return (True, "স্টার্ট মেনু খুলে দিলাম!" if ok else "খুলতে পারলাম না।")

    # সব উইন্ডো মিনিমাইজ / ডেস্কটপ দেখাও
    if any(w in t for w in ("মিনিমাইজ", "minimize", "ডেস্কটপ দেখাও", "show desktop")):
        ok = _ps("(New-Object -ComObject Shell.Application).MinimizeAll()")
        return (True, "সব উইন্ডো মিনিমাইজ করে দিলাম!" if ok else "করতে পারলাম না।")
    if any(w in t for w in ("রিস্টোর", "restore", "ফেরত আনো")) and "উইন্ডো" in t:
        ok = _ps("(New-Object -ComObject Shell.Application).UndoMinimizeALL()")
        return (True, "উইন্ডোগুলো ফেরত আনলাম!" if ok else "করতে পারলাম না।")

    # ফোল্ডার/Explorer উইন্ডো বন্ধ (শুধু Explorer — অন্য অ্যাপ অক্ষত)
    if any(w in t for w in ("ফোল্ডার বন্ধ", "explorer বন্ধ", "explorer bondho",
                            "ফোল্ডারগুলো বন্ধ")):
        if not _confirm("সব File Explorer উইন্ডো বন্ধ করব? হ্যাঁ/না।"):
            return True, "ঠিক আছে, বন্ধ করিনি।"
        ok = _ps("$w=(New-Object -ComObject Shell.Application).Windows();"
                 "$w | ForEach-Object { $_.Quit() }")
        return (True, "সব ফোল্ডার (Explorer) উইন্ডো বন্ধ করে দিলাম!" if ok
                else "বন্ধ করতে পারলাম না।")

    # সব উইন্ডো বন্ধ (বিপজ্জনক — অনুমতি বাধ্যতামূলক)
    if "সব উইন্ডো বন্ধ" in t or ("সব" in t and "উইন্ডো" in t and "বন্ধ" in t):
        if not _confirm("⚠️ সব খোলা উইন্ডো বন্ধ হবে — unsaved কাজ হারাতে পারে! নিশ্চিত? হ্যাঁ/না।"):
            return True, "ঠিক আছে, কিছু করিনি।"
        ok = _ps("(New-Object -ComObject Shell.Application).Windows() | "
                 "ForEach-Object { $_.Quit() }")
        return (True, "Explorer উইন্ডোগুলো বন্ধ করে দিলাম।" if ok else "করতে পারলাম না।")

    # বর্তমান (সামনের) উইন্ডো বন্ধ
    if ("উইন্ডো বন্ধ" in t or "window bandho" in t or "window close" in t) \
            and "সব" not in t:
        if not _confirm("এখন সামনে যে উইন্ডো খোলা আছে সেটা বন্ধ করব? হ্যাঁ/না।"):
            return True, "ঠিক আছে, বন্ধ করিনি।"
        ok = _ps("(New-Object -ComObject WScript.Shell).SendKeys('%{F4}')")
        return (True, "উইন্ডোটা বন্ধ করে দিলাম!" if ok else "করতে পারলাম না।")

    # PC লক
    if "পিসি লক" in t or "pc lock" in t or "লক করো" in t and "পিসি" in t:
        ok = _ps("rundll32.exe user32.dll,LockWorkStation")
        return (True, "পিসি লক করে দিলাম!" if ok else "করতে পারলাম না।")

    return None


def _ocr_screen() -> str:
    """স্ক্রিনের সব লেখা হুবহু ট্রান্সক্রাইব (Gemini OCR; লাইন কাঠামো রেখে)।"""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        if img.width > 1600:
            img = img.resize((1600, int(img.height * 1600 / img.width)))
        path = os.path.join(tempfile.gettempdir(), "asif_ocr.jpg")
        img.save(path, "JPEG", quality=80)
    except Exception as e:
        return f"স্ক্রিনশট নিতে সমস্যা: {e}"
    ans = _gemini_vision("এই স্ক্রিনের সব দৃশ্যমান লেখা হুবহু ট্রান্সক্রাইব করো — "
                         "লাইন কাঠামো রেখে। ব্যাখ্যা নয়, শুধু লেখা।", path)
    return ans or "লেখা পড়া যায়নি (ছবি ঝাপসা বা নেটওয়ার্ক ধীর)।"


def _capture_active_window() -> str | None:
    """সামনের (active) উইন্ডোটাই ক্যাপচার — পুরো স্ক্রিন নয়।"""
    try:
        import ctypes
        from PIL import ImageGrab
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        rect = ctypes.wintypes.RECT()
        ctypes.wintypes = ctypes.wintypes
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            l, t_, r_, b_ = rect.left, rect.top, rect.right, rect.bottom
            if r_ > l and b_ > t_:
                img = ImageGrab.grab(bbox=(l, t_, r_, b_))
                path = os.path.join(tempfile.gettempdir(), "asif_window.jpg")
                if img.width > 1400:
                    img = img.resize((1400, int(img.height * 1400 / img.width)))
                img.save(path, "JPEG", quality=80)
                return path
    except Exception:
        pass
    return None


def _screen_error_analysis(user_text: str) -> str:
    """স্ক্রিনের error পড়ে কারণ+সমাধান ব্যাখ্যা (AI বিশ্লেষণ; কখনো ভুয়া নয়)।"""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        path = os.path.join(tempfile.gettempdir(), "asif_err.jpg")
        img.save(path, "JPEG", quality=80)
    except Exception as e:
        return f"স্ক্রিনশট নিতে সমস্যা: {e}"
    ans = _gemini_vision(
        "এই স্ক্রিনে কোনো error message বা সমস্যা দেখা যাচ্ছে? থাকলে: "
        "১) error-এর হুবহু লেখা ২) কোন অ্যাপ ৩) সম্ভাব্য কারণ ৪) নিরাপদ সমাধান — "
        "বাংলায়। error না থাকলে স্পষ্ট বলো।", path)
    if not ans:
        return "error পড়া যায়নি — টার্মিনালে ⚠️ লাইন দেখুন।"
    return ans


def _cmd_screen() -> str:
    """স্ক্রিনের ছবি নিয়ে Gemini কে জিজ্ঞেস করে কী দেখা যাচ্ছে।"""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        # ধীর নেটওয়ার্কে দ্রুত আপলোড: রিসাইজ + JPEG (৩৬২KB → ~৬০KB)
        if img.width > 1280:
            img = img.resize((1280, int(img.height * 1280 / img.width)))
        path = os.path.join(tempfile.gettempdir(), "asif_screen.jpg")
        img.save(path, "JPEG", quality=70)
    except Exception as e:
        return f"স্ক্রিনের ছবি নিতে সমস্যা: {e}"
    if not GEMINI_KEY:
        return "স্ক্রিন দেখার জন্য আমার Gemini key দরকার (asif_key.txt) — Ollama ছবি দেখতে পারে না।"
    ans = _gemini_vision("এই কম্পিউটার স্ক্রিনে কী কী আছে? সংক্ষেপে, বাংলায় বলো।", path)
    if ans:
        return ans
    return ("স্ক্রিন দেখতে পারলাম না। সম্ভাব্য কারণ: Gemini key সমস্যা বা নেটওয়ার্ক — "
            "টার্মিনালে ⚠️ লাইনে আসল কারণ লেখা থাকবে।")


def _gemini_vision(question: str, image_path: str, _attempts: int = 0) -> str | None:
    """ছবি দেখিয়ে Gemini কে প্রশ্ন করে (404 হলে একবার মডেল-অটো-পিক; অসীম লুপ নয়)।"""
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        r = requests.post(
            f"{GEMINI_URL}/{GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": GEMINI_KEY},
            json={
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [
                    {"text": question},
                    {"inline_data": {"mime_type":
                        "image/jpeg" if image_path.lower().endswith(".jpg")
                        else "image/png", "data": b64}},
                ]}],
                "generationConfig": {"maxOutputTokens": 1024,
                                    "thinkingConfig": {"thinkingBudget": 0}},
            },
            timeout=(5, 300),
        )
        if r.status_code == 404 and _attempts == 0:
            _pick_gemini_model()
            return _gemini_vision(question, image_path, _attempts=1)
        if r.status_code != 200:
            print(f"⚠️  স্ক্রিন-দর্শন ত্রুটি (HTTP {r.status_code}): {r.text[:150]}")
            return None
        cands = r.json().get("candidates", [])
        if cands:
            return "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", [])).strip() or None
        return None
    except Exception as e:
        print(f"⚠️  স্ক্রিন দেখতে সমস্যা: {type(e).__name__}")
        return None


def _search_files(target: str) -> list:
    """ডেস্কটপ/ডকুমেন্টস/ডাউনলোডস ইত্যাদিতে ফাইল/ফোল্ডার খোঁজে।"""
    dirs = [DESKTOP,
            Path.home() / "Documents", Path.home() / "Downloads",
            Path.home() / "Pictures", Path.home() / "Videos", Path.home() / "Music"]
    hits = []
    tl = target.lower()
    for d in dirs:
        if not d.exists():
            continue
        try:
            for p in d.iterdir():
                if tl in p.name.lower():
                    hits.append(p)
        except Exception:
            pass
    return hits[:3]


def _find_shortcut(target: str):
    """স্টার্ট মেনুতে অ্যাপের শর্টকাট খোঁজে।"""
    dirs = [Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs")]
    appdata = os.environ.get("APPDATA")
    if appdata:
        dirs.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    tl = target.lower()
    for d in dirs:
        if d.exists():
            try:
                for p in d.rglob("*.lnk"):
                    if tl in p.stem.lower():
                        return p
            except Exception:
                pass
    return None


def _cmd_open(target: str) -> str:
    if not target:
        return "কী খুলব বলুন — অ্যাপ, ফোল্ডার বা ওয়েবসাইট?"
    # পরিচিত অ্যাপ/সাইট?
    low = target.lower()
    for key, val in APPS.items():
        if key in low:
            try:
                if val.startswith("http"):
                    webbrowser.open(val)
                    return f"{key} খুলে দিলাম!"
                os.startfile(val)
                return f"{key} খুলে দিলাম!"
            except Exception:
                continue
    # ওয়েবসাইটের মতো?
    if "." in target or target.startswith("www"):
        url = target if target.startswith("http") else f"https://{target}"
        webbrowser.open(url)
        return f"{target} সাইটটা খুলে দিলাম!"
    # ফাইল/ফোল্ডার খোঁজো (ডেস্কটপ, ডকুমেন্টস, ডাউনলোডস...)
    import file_manager as _fm
    hit = _fm._find_in_roots(target)
    if hit:
        os.startfile(str(hit))
        return f"📂 '{hit.name}' খুলে দিলাম!"
    # ফোল্ডারের নাম নেই/পাওয়া যায়নি → তালিকা দেখিয়ে জিজ্ঞেস (folder_pick মোড)
    if "ফোল্ডার" in target or "folder" in target.lower():
        global _AWAITING
        folders = [i[2:] for i in _fm.list_desktop() if i.startswith("📁")]
        _AWAITING = {"type": "folder_pick"}
        return ("📂 ডেস্কটপে এই ফোল্ডারগুলো আছে — কোনটা খুলব, "
                "নাম লিখুন:\n" + "\n".join(folders[:12]))
    # স্টার্ট মেনুতে অ্যাপ খোঁজো — যেকোনো ইনস্টল করা অ্যাপ চলবে
    lnk = _find_shortcut(target)
    if lnk:
        os.startfile(str(lnk))
        return f"{lnk.stem} অ্যাপটা খুলে দিলাম!"
    # শেষ চেষ্টা: সরাসরি চালানো
    try:
        os.startfile(target)
        return f"{target} খুলে দিলাম!"
    except Exception:
        return f"'{target}' খুঁজে পেলাম না। নামটা আবার বলুন, বা ফাইলের পুরো নাম বলুন।"


def _cmd_close(target: str) -> str:
    if not target:
        return "কোন অ্যাপ বন্ধ করব বলুন?"
    low = target.lower()
    procs = None
    for key, val in CLOSE_MAP.items():
        if key in low:
            procs = val
            break
    if not procs:
        # চালু প্রসেসগুলো থেকে মিলিয়ে দেখো — যেকোনো অ্যাপ ধরা যায়
        procs = []
        try:
            out = subprocess.run(["tasklist", "/FO", "CSV"],
                                 capture_output=True, text=True, timeout=15).stdout
            for line in out.splitlines():
                parts = [p.strip('"') for p in line.split('","')]
                if parts and low in parts[0].lower():
                    procs.append(parts[0])
        except Exception:
            pass
        if not procs:
            procs = [target.split()[0] + ".exe"]
    killed = False
    killed_name = ""
    for proc in procs[:5]:
        try:
            r = subprocess.run(["taskkill", "/IM", proc, "/F"],
                               capture_output=True, timeout=15)
            if r.returncode == 0:
                killed = True
                killed_name = proc
                break
        except Exception:
            pass
    if killed:
        return f"{killed_name.replace('.exe', '')} বন্ধ করে দিলাম।"
    return f"{target} এখন চালু নেই, বা বন্ধ করতে পারলাম না।"


def _cmd_search(target: str, youtube: bool = False) -> str:
    """গুগল/ইউটিউব-এ সার্চ করে ব্রাউজারে খোলে।"""
    if not target:
        return "কী সার্চ করব বলুন?"
    if youtube:
        url = "https://www.youtube.com/results?search_query=" + requests.utils.quote(target)
        webbrowser.open(url)
        return f"ইউটিউবে '{target}' সার্চ করে দিলাম!"
    url = "https://www.google.com/search?q=" + requests.utils.quote(target)
    webbrowser.open(url)
    return f"'{target}' নিয়ে গুগলে সার্চ করে দিলাম!"


def _cmd_terminal(target: str) -> str:
    """টার্মিনাল কমান্ড চালায় — নিরাপত্তা সহ।"""
    if not target:
        return "কোন কমান্ড চালাব বলুন?"
    low = target.lower()
    # ❌ কঠোরভাবে নিষিদ্ধ — সিস্টেম ধ্বংসকারী
    DANGEROUS = ("format", "shutdown", "restart-computer", "diskpart", "cipher",
                 "vssadmin", "bcdedit", "reg delete", "del /f", "del /s", "rd /s",
                 "rmdir /s", "rm -rf", "mkfs", "erase", "logoff", "taskkill /f /im explorer")
    if any(d in low for d in DANGEROUS):
        return f"' {target}' কমান্ডটা বিপজ্জনক — আমি চালাব না।"
    # ✅ নিরাপদ পরিচিত কমান্ড — সোজা চলে
    SAFE = ("dir", "ipconfig", "ping", "systeminfo", "date", "time", "ver",
            "whoami", "echo", "tasklist", "hostname", "getmac", "tree", "type",
            "where", "vol", "cls", "help", "node -v", "python --version", "git")
    if not any(low.strip().startswith(s) for s in SAFE):
        # অপরিচিত কমান্ড — আগে অনুমতি নিই
        if not _confirm(f"'{target}' কমান্ডটা চালাব? বলুন হ্যাঁ বা না।"):
            return "ঠিক আছে, চালাইনি।"
    try:
        r = subprocess.run(target, shell=True, capture_output=True,
                           text=True, timeout=60, encoding="utf-8", errors="replace")
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        if not out:
            return "কমান্ড চলেছে, কোনো আউটপুট নেই।"
        lines = [l for l in out.splitlines() if l.strip()][:3]
        summary = " | ".join(lines)[:250]
        return f"কমান্ড চলেছে। ফলাফল: {summary}"
    except subprocess.TimeoutExpired:
        return "কমান্ড বেশি সময় নিচ্ছিল, বন্ধ করে দিলাম।"
    except Exception as e:
        return f"কমান্ড চলেনি: {e}"


# ----------------- 🚀 AVA টার্মিনাল ইঞ্জিন (advanced) -----------------
DEV_TOOLS = ("npm", "npx", "composer", "laravel", "php artisan", "git ", "git-",
             "node ", "react", "next ", "mysql", "pip ", "vite", "webpack")
DEV_ACTIONS = ("চালা", "run", "koro", "করো", "কর", "ইনস্টল", "install", "ব্যাকআপ",
               "backup", "fix", "ডিপেন্ডেন্সি", "dependencies", "serve", "start",
               "টেস্ট", "test", "build", "বিল্ড", "deploy", "migration")
SIMPLE_CMDS = ("dir", "echo", "ipconfig", "ping", "systeminfo", "whoami",
               "date", "time", "ver", "tasklist", "node -v", "git --version")


def _wants_terminal_task(t: str) -> bool:
    tl = t.lower()
    if ("টার্মিনাল" in tl or "terminal" in tl) and any(
            w in tl for w in ("চালা", "রান", "run", "execute", "এক্সিকিউট")):
        # সরল এক-লাইনার হলে পুরনো দ্রুত পথই থাক
        stripped = tl
        for w in ("টার্মিনালে", "টার্মিনাল", "terminal", "কমান্ড", "চালাও", "চালা", "রান", "run"):
            stripped = stripped.replace(w, " ")
        if stripped.strip().startswith(SIMPLE_CMDS):
            return False
        return True
    if any(dt in tl for dt in DEV_TOOLS) and any(da in tl for da in DEV_ACTIONS):
        return True
    return False


def _run_ava_task(user_text: str) -> str:
    try:
        import terminal_engine as te
    except ImportError:
        return _cmd_terminal(user_text)  # ইঞ্জিন না থাকলে পুরনো নিরাপদ পথ
    try:
        return te.run_task(
            user_text,
            speak_cb=speak,
            confirm_cb=_confirm,
            listen_cb=(listen if MIC_OK else None),
        )
    except Exception as e:
        return f"টার্মিনাল ইঞ্জিন সমস্যা: {type(e).__name__}: {e}"


# ----------------- 🔤 STT-ভুল সংশোধন + ফাজি ইনটেন্ট -----------------
STT_FIX = {"কোলো": "খোলো", "কুলো": "খোলো", "হোলো": "খোলো", "খুলো": "খোলো",
           "বন্ধ করো": "বন্ধ করো", "বানাও": "বানাও", "বানাই": "বানাও",
           "বানা": "বানাও", "বাজাও": "বাজাও", "বাজাও": "বাজাও",
           "টাইপ": "টাইপ", "টাইপ": "টাইপ"}


def normalize_stt(t: str) -> str:
    """মাইক-শনাক্তকরণের কমন ভুল শব্দ সংশোধন।"""
    for wrong, right in STT_FIX.items():
        t = t.replace(wrong, right)
    return t


FUZZY_INTENTS = {
    "folder_word": ("ফোল্ডার", "folder", "ফোল্ডারটা", "ফোল্ডারটি", "ফোল্ডারগুলো"),
    "create": ("বানা", "তৈরি", "create", "make", "new", "নতুন", "banai", "bana"),
    "open": ("খোল", "খুল", "open", "ওপেন", "চালু", "launch", "start"),
    "close": ("বন্ধ", "close", "bandho", "bondho", "শাট", "থামা"),
    "delete": ("মুছ", "ডিলিট", "delete", "remove", "muchhe", "মুছে"),
    "play": ("বাজা", "play", "গান", "song", "music", "শোনাও", "শুন", "ভিডিও", "video"),
    "search": ("সার্চ", "search", "খোঁজ", "খুঁজ", "google", "find"),
    "scroll": ("স্ক্রল", "scroll"),
    "youtube": ("ইউটিউব", "youtube"),
}


def _has_group(t: str, group: str) -> bool:
    return any(w in t for w in FUZZY_INTENTS[group])


def _fuzzy_intent_router(user_text: str) -> tuple[bool, str] | None:
    """ভিন্নভাবে বলা নির্দেশও ধরে; অনিশ্চিত হলে clarification চায়।"""
    t = normalize_stt(user_text.lower())
    target = _extract_target(user_text)

    folder = _has_group(t, "folder_word")
    create = _has_group(t, "create")
    open_ = _has_group(t, "open")
    close = _has_group(t, "close")
    delete = _has_group(t, "delete")
    play = _has_group(t, "play")
    search = _has_group(t, "search")
    scroll = _has_group(t, "scroll")
    yt = _has_group(t, "youtube")

    # ফোল্ডার তৈরি (folder + create)
    if folder and create:
        return _file_action_router(user_text) or (
            True, f"ফোল্ডার তৈরির নির্দেশ বুঝলাম, কিন্তু নামটা পরিষ্কার না — "
                  f"বলুন: '{target or 'নাম'}' নামে ফোল্ডার বানাও")
    # ফোল্ডার/Explorer খোলা
    if folder and open_:
        if target:
            return True, _cmd_open(target)
        return True, _cmd_open("ফোল্ডার")  # নাম নেই → ফোল্ডার-তালিকা + folder_pick মোড
    # বন্ধ করা
    if close and (folder or "explorer" in t):
        pc = _pc_router("সব ফোল্ডার বন্ধ করো")
        return pc or (True, "বুঝতে পারিনি।")
    if close:
        if target:
            return True, _cmd_close(target)
        return True, "কী বন্ধ করব বলুন? (অ্যাপ/ফোল্ডার/উইন্ডো)"
    # গান বাজানো
    if play and (yt or "গান" in t or "song" in t or "music" in t):
        return True, _yt_play(target or user_text)
    if play and target:
        return True, _yt_play(target)
    # সার্চ
    if search:
        return True, _cmd_search(target or user_text)
    # খোলা (অ্যাপ/সাইট/ফাইল)
    if open_:
        if target:
            return True, _cmd_open(target)
        return True, "কী খুলব বলুন?"
    # মোছা
    if delete:
        fr = _file_action_router(user_text)
        if fr:
            return fr
        if target:
            return True, _cmd_delete(target)
        return True, "কী মুছব বলুন?"
    # স্ক্রল
    if scroll:
        mk = _mouse_kb_router("স্ক্রল করো" + (" উপরে" if "উপর" in t or "up" in t else ""))
        return mk or (True, "স্ক্রল ব্যর্থ।")
    # 👁️ স্ক্রিন দর্শন (ফাজি পথ): OCR / active-window / error-বিশ্লেষণ
    if any(w in t for w in ("ocr", "স্ক্রিনের লেখা", "লেখা পড়ো", "text poro")):
        try:
            return True, _ocr_screen()
        except Exception as e:
            return True, f"OCR সমস্যা: {e}"
    if any(w in t for w in ("এই উইন্ডো", "active window", "এই অ্যাপটা দেখ")):
        p = _capture_active_window()
        if not p:
            return True, "উইন্ডো ক্যাপচার ব্যর্থ।"
        ans = _gemini_vision("এই উইন্ডোতে কী আছে? অ্যাপ, বাটন, ইনপুট ফিল্ড, "
                             "লেখা — বাংলায় বর্ণনা করো।", p)
        return True, ans or "উইন্ডো বর্ণনা ব্যর্থ।"
    if any(w in t for w in ("error ঠিক", "error fix", "এই এরর", "এই error",
                            "error বুঝিয়ে")):
        return True, _screen_error_analysis(user_text)

    # অসম্পূর্ণ নির্দেশ? কিছু অর্থবহ শব্দ থাকলে clarification চাও
    verb_hits = sum(1 for g in ("create", "open", "close", "delete", "play",
                                "search", "scroll") if _has_group(t, g))
    if verb_hits >= 1 and target:
        return True, (f"আপনি কি চাচ্ছেন — '{target}' নিয়ে কাজ? একটু পরিষ্কার করে বলুন: "
                      "খোলা / তৈরি / বন্ধ / মোছা / সার্চ — কোনটা?")
    return None


def _extract_task_id(text: str):
    import task_engine as te
    m = re.search(r"\b([0-9a-f]{8}(?:-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})?)\b",
                  text.lower())
    if m:
        tid = te.resolve_task_id(m.group(1))
        if tid:
            return tid
    for st in ("WAITING_FOR_APPROVAL", "RUNNING", "READY", "PAUSED"):
        rows = te.list_tasks(st, limit=1)
        if rows:
            return rows[0]["id"]
    return None


def _plan_task_via_llm(instruction: str):
    import task_engine as te
    model = _ollama_pick_model() or OLLAMA_MODEL
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": te.planner_spec()},
            {"role": "user", "content": instruction},
        ],
        "stream": False,
        "format": te.planner_schema(),
        "keep_alive": "1h",
        "options": {"temperature": 0.1, "num_predict": 700, "num_thread": 8},
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    r.raise_for_status()
    content = (r.json().get("message") or {}).get("content", "")
    steps = te.parse_plan_json(content)
    title = instruction.strip().replace("\n", " ")[:80] or "টাস্ক"
    tid = te.create_task(title, instruction, steps)
    te.enqueue(tid)
    return tid, steps, te.get_task(tid)


def _task_router(user_text: str):
    """🧩 দীর্ঘ-চলমান টাস্ক: তৈরি/তালিকা/স্ট্যাটাস/অনুমোদন/বাতিল/থামানো/চালু।"""
    t = user_text.lower().strip()
    has_task_word = ("টাস্ক" in t or "task" in t or "কাজের তালিকা" in t
                     or "প্ল্যান" in t or "plan" in t or "পরিকল্পনা" in t)
    if not has_task_word:
        return None
    try:
        import task_engine as te
    except Exception as e:
        return True, f"⚠️ টাস্ক ইঞ্জিন পাওয়া যায়নি: {e}"

    try:
        if ("তালিকা" in t or "লিস্ট" in t or "list" in t) and "অনুমোদন" not in t:
            return True, te.status_text()

        if "স্ট্যাটাস" in t or "status" in t:
            tid = _extract_task_id(user_text)
            return True, te.status_text(tid)

        if "অনুমোদন" in t or re.search(r"\bapprove\b", t):
            tid = _extract_task_id(user_text)
            if not tid:
                return True, "❌ কোনো অপেক্ষমাণ টাস্ক পাওয়া যায়নি।"
            ok = te.approve(tid)
            return True, ("✅ অনুমোদন দেওয়া হলো — কাজ আবার শুরু হবে।"
                          if ok else "❌ এই ধাপ অনুমোদনযোগ্য নয়।")

        if (("টাস্ক" in t or "task" in t or "কাজ" in t)
                and ("বাতিল" in t or re.search(r"\bcancel\b", t))):
            tid = _extract_task_id(user_text)
            if not tid:
                return True, "❌ কোনো টাস্ক পাওয়া যায়নি।"
            return True, ("🚫 টাস্ক বাতিল করা হলো।" if te.cancel(tid)
                          else "❌ টাস্কটি বাতিল করা গেল না।")

        if (("টাস্ক" in t or "task" in t or "কাজ" in t)
                and ("থামাও" in t or "বিরতি" in t or re.search(r"\bpause\b", t))):
            tid = _extract_task_id(user_text)
            if not tid:
                return True, "❌ কোনো চলমান টাস্ক পাওয়া যায়নি।"
            return True, ("⏸️ টাস্ক থামানো হলো।" if te.pause(tid)
                          else "❌ টাস্কটি থামানো গেল না।")

        if (("টাস্ক" in t or "task" in t or "কাজ" in t)
                and ("চালাও" in t or "চালু" in t or "শুরু" in t
                     or re.search(r"\bresume\b", t))):
            tid = _extract_task_id(user_text)
            if not tid:
                return True, "❌ কোনো টাস্ক পাওয়া যায়নি।"
            ok = te.enqueue(tid)
            return True, ("▶️ টাস্ক আবার চালু হলো।" if ok
                          else "ℹ️ টাস্কটি এখন চালানোর অবস্থায় নেই।")

        wants_plan = (("প্ল্যান" in t or "পরিকল্পনা" in t or re.search(r"\bplan\b", t))
                      and any(w in t for w in ("কর", "বানা", "তৈরি", "make", "create")))
        wants_plan = wants_plan or "টাস্ক বানাও" in t or "টাস্ক তৈরি" in t
        if wants_plan:
            instruction = re.sub(
                r"^(.*?(?:প্ল্যান|পরিকল্পনা|plan|টাস্ক))\s*(করো|কর|বানাও|বানা|তৈরি করো|তৈরি|make|create)?\s*",
                "", user_text, count=1, flags=re.I).strip() or user_text
            try:
                tid, steps, task = _plan_task_via_llm(instruction)
            except Exception as e:
                return True, (f"❌ পরিকল্পনা করা যায়নি: {type(e).__name__}: {e}\n"
                              "টাস্কের ধাপগুলো একটু স্পষ্ট করে বলুন।")
            waiting = any(s.get("status") == "WAITING_FOR_APPROVAL"
                          for s in (task or {}).get("steps", []))
            msg = (f"🧩 টাস্ক তৈরি হয়েছে: {tid[:8]} — {len(steps)}টি ধাপ।"
                   + (" অনুমোদনের অপেক্ষায় আছে।" if waiting else " শুরু করছি।"))
            return True, msg

        if "টাস্ক" in t or "task" in t:
            return True, te.status_text(_extract_task_id(user_text))
    except Exception as e:
        return True, f"❌ টাস্ক কমান্ডে সমস্যা: {type(e).__name__}: {e}"
    return None


def try_command(user_text: str) -> tuple[bool, str]:
    """কথা থেকে কাজ বুঝে চালায়। (কাজ করলে: True, উত্তর)"""
    global _CHAINING, _AWAITING
    t = user_text.strip().lower()  # সবার আগে (awaiting ব্লকে লাগে)

    # 🎯 ইন্টারেক্টিভ অপেক্ষা — আগের প্রশ্নের উত্তর এই কথাটা
    if _AWAITING and _AWAITING.get("type") == "folder_followup":
        path = _AWAITING["path"]
        learn_payload = _AWAITING.get("learn")
        _AWAITING = None
        toks = t.split()
        if ("কিছু না" in t or "না" in toks or "বাতিল" in t or "থামো" in t
                or "no" in toks or "done" in toks or "বন্ধ" in toks):
            if learn_payload:
                try:
                    import memory_db
                    learn = memory_db.maybe_learn(
                        learn_payload["text"], learn_payload["intent"],
                        learn_payload["action_type"], learn_payload["template"],
                        learn_payload["schema"], learn_payload["aliases"],
                        speak_cb=speak, confirm_cb=_confirm)
                    if learn:
                        return True, learn
                except Exception:
                    pass
            return True, "ঠিক আছে! ফোল্ডারটি তৈরি ও প্রস্তুত।"
        if any(w in t for w in ("খোল", "open")):
            r = file_manager.open_in_explorer(path)
            return True, (f"খুলে দিলাম: {r['path']}" if r["status"] == "created"
                          else f"খোলা যায়নি — {r['reason']}")
        if "ফাইল" in t or "file" in t or "নোট" in t or "txt" in t:
            fname = _extract_target(user_text) or "নোট"
            r = file_manager.create_text_file(path, fname)
            _AWAITING = {"type": "folder_followup", "path": path, "learn": learn_payload}
            if r["status"] == "created":
                return True, (f"ফাইল তৈরি হলো ফোল্ডারের ভেতরে (PASS): {r['path']}\n"
                              "আর কিছু? ('খোলো' / 'ফাইল বানাও ...' / 'আর কিছু না')")
            return True, f"ফাইল তৈরি হয়নি — {r['reason']}"
        return True, ("বুঝতে পারিনি। বিকল্প: 'ফাইল বানাও নোট' / 'খোলো' / "
                      "'আর কিছু না' — কোনটা?")

    if _AWAITING and _AWAITING.get("type") == "folder_pick":
        _AWAITING = None
        if any(w in t.split() for w in ("বাতিল", "থামো", "না")) or t in ("no", "cancel"):
            return True, "ঠিক আছে, বাতিল।"
        import file_manager as _fmp
        found = _fmp._find_in_roots(user_text.strip())
        if found:
            os.startfile(str(found))
            return True, f"📂 '{found.name}' খুলে দিলাম!"
        return True, f"'{user_text.strip()[:40]}' নামে ফোল্ডার/ফাইল পাইনি — আবার নাম লিখুন বা বলুন 'বাতিল'।"

    if _AWAITING and _AWAITING.get("type") == "yt_play":
        _AWAITING = None
        if any(w in t for w in ("বাতিল", "থামো", "কিছু না", "cancel", "না", "nah")):
            return True, "ঠিক আছে, বাতিল।"
        # যদি বরং নতুন অন্য কমান্ড হয় — সেটা সাধারণ পথে যাক
        if any(w in t for w in ("খোলো", "বানাও", "বন্ধ করো", "মুছে", "create",
                                "delete", "open", "close", "স্ক্রল")):
            pass  # নিচের সাধারণ রাউটিং চলবে
        else:
            return True, _yt_play(user_text.strip())

    # 🧩 দীর্ঘ-চলমান টাস্ক ইঞ্জিন (media/file রাউটারের আগে)
    tr = _task_router(user_text)
    if tr is not None:
        return tr

    # ⛓️ কমান্ড-চেইন: "X তারপর Y তারপর Z" → ক্রমানুসারে সব কাজ
    if not _CHAINING:
        parts = re.split(r"\s*(?:তারপর|তারপর|এরপর|then|আর পরে|ar por|পরে)\s*",
                         user_text, flags=re.I)
        parts = [p.strip(" ।,.") for p in parts if p.strip(" ।,.")]
        if len(parts) > 1:
            _CHAINING = True
            try:
                replies = []
                for i, part in enumerate(parts[:5], 1):
                    print(f"⛓️ ধাপ {i}/{len(parts[:5])}: {part}")
                    try:
                        h, r = try_command(part)
                        replies.append(f"{i}️⃣ {r if h else 'বুঝতে পারিনি: ' + part}")
                    except Exception as e:
                        replies.append(f"{i}️⃣ সমস্যা: {e}")
            finally:
                _CHAINING = False
            return True, "\n".join(replies)

    t = user_text.strip().lower()

    # AVA টার্মিনাল ইঞ্জিন — dev/automation কাজ সবার আগে
    if _wants_terminal_task(user_text):
        return True, _run_ava_task(user_text)

    # স্ক্রিন দেখা
    if "স্ক্রিন" in t and any(w in t for w in ("দেখ", "কী", "কি", "shot", "শট", "ছবি")):
        return True, _cmd_screen()

    # ইন্টারনেট সার্চ
    if any(w in t for w in ("সার্চ", "search", "খোঁজ", "খোজ", "গুগল কর")):
        target = _extract_target(user_text)
        youtube = any(w in t for w in ("ইউটিউব", "youtube"))
        if not ("ফোল্ডার" in t or "folder" in t or "ফাইল" in t):
            return True, _cmd_search(target, youtube)

    # টার্মিনাল কমান্ড চালানো
    if ("টার্মিনাল" in t or "কমান্ড" in t or "terminal" in t or "cmd এ" in t) and any(
        w in t for w in ("চালা", "রান", "run", "দে", "দিব", "দাও", "execute", "এক্সিকিউট")
    ):
        return True, _cmd_terminal(_extract_target(user_text))

    # 🧬 Long-term memory: টাস্ক/প্রজেক্ট/হিস্ট্রি নিয়ন্ত্রণ (DB থাকলে)
    lt = _longterm_router(user_text)
    if lt is not None:
        return lt

    # 🧠 Conversation Intelligence: সাধারণ/পরিচয়/ধন্যবাদ — LLM ছাড়াই তাৎক্ষণিক সঠিক
    try:
        import identity
        fast = identity.fast_reply(user_text)
        if fast == "__CORRECTION__":
            saved = identity.record_correction(user_text)
            return True, ("দুঃখিত, আমি প্রশ্নটা ভুল বুঝেছিলাম 🙏\n"
                          "সঠিকটা আবার বলুন — আমি শিখে নেব (সংরক্ষিত: " + saved + ")।")
        if fast is not None:
            try:
                fast = identity.quality_filter(fast, user_text)
            except Exception:
                pass
            return True, fast
    except Exception:
        pass

    # 💾 সেভ করা কমান্ড আগে খোঁজো — মিললে AI কল ছাড়াই ইনস্ট্যান্ট
    try:
        import memory_db
        mem = memory_db.try_memory(user_text, speak_cb=speak, confirm_cb=_confirm)
        if mem:
            return True, mem
    except Exception:
        pass

    # ⚡ দ্রুত/কোয়ালিটি মোড টগল
    if "দ্রুত মোড" in t or "fast mode" in t:
        _SPEED_MODE = True
        return True, "⚡ দ্রুত মোড চালু! এখন ছোট দ্রুত উত্তর আসবে। ('কোয়ালিটি মোড' বললে ফেরত)"
    if "কোয়ালিটি মোড" in t or "quality mode" in t or "ভালো মোড" in t:
        _SPEED_MODE = False
        return True, "✨ কোয়ালিটি মোড — আগের মতো বিস্তারিত উত্তর।"

    # 🗂️ Phase 2: বর্ধিত ফাইল টুলস (সার্চ/গুছানো/ব্যাকআপ/ডুপ্লিকেট)
    try:
        import file_tools
        ft = file_tools.handle(user_text, confirm_cb=_confirm)
        if ft is not None:
            return ft
    except Exception:
        pass

    # 👨‍💻 Coding Agent (Phase 3)
    if any(w in t for w in ("coding agent", "কোড agent", "project inspect",
                            "প্রজেক্ট inspect", "কোড ব্যাখ্যা", "explain code",
                            "controller banao", "model banao", "migration banao",
                            "component banao", "code likho", "bug fix করো কোড")):
        try:
            import coding_agent
            if "inspect" in t:
                m = re.search(r"inspect\s+(.+)", user_text, re.I)
                return True, coding_agent.inspect_report(
                    m.group(1).strip() if m else os.getcwd())
            if any(w in t for w in ("controller", "model", "migration",
                                    "component", "api")):
                m = re.search(r"(controller|model|migration|component|api)\s+([\w\- ]+)",
                              user_text, re.I)
                if m:
                    return True, coding_agent.generate(
                        m.group(1).lower(), m.group(2).strip(), os.getcwd())
            m = re.search(r"(?:explain|ব্যাখ্যা)\s+([\w\.\-/]+)", user_text, re.I)
            if m:
                return True, coding_agent.explain_file(m.group(1))
            return True, coding_agent.inspect_report(os.getcwd())
        except Exception as e:
            return True, f"Coding agent সমস্যা: {e}"

    # 🔄 Auto-Update Engine
    try:
        import updater
        up = updater.handle(user_text, confirm_cb=_confirm)
        if up is not None:
            return up
    except Exception as e:
        if "আপডেট" in t or "update" in t:
            return True, f"আপডেট সমস্যা: {e}"

    # 🕐 সময়/তারিখ বুদ্ধিমত্তা
    try:
        import time_intel
        ti = time_intel.handle(user_text)
        if ti is not None:
            return ti
    except Exception:
        pass

    # 🌦️ আবহাওয়া
    if any(w in t for w in ("আবহাওয়া", "weather", "বৃষ্টি", "brishti", "তাপমাত্রা",
                            "temperature", "গরম")):
        try:
            import weather
            return True, weather.handle(user_text)[1]
        except Exception as e:
            return True, f"আবহাওয়া সমস্যা: {e}"

    # 💻 সফটওয়্যার / ডেভ environment
    try:
        import software_manager
        sm = software_manager.handle(user_text, confirm_cb=_confirm)
        if sm is not None:
            return sm
    except Exception:
        pass

    # 📄 ডকুমেন্ট ক্রিয়েটর
    try:
        import doc_creator
        dc = doc_creator.handle(user_text)
        if dc is not None:
            return dc
    except Exception as e:
        if any(w in t for w in ("ডকুমেন্ট", "ইনভয়েস", "স্প্রেডশিট", "pdf", "docx")):
            return True, f"ডকুমেন্ট সমস্যা: {e}"

    # ⏰ রিমাইন্ডার/সিডিউলার
    try:
        import scheduler
        sr_ = scheduler.handle(user_text)
        if sr_ is not None:
            return sr_
    except Exception:
        pass

    # 📚 নলেজ বেইজ
    if "নলেজ" in t or "knowledge" in t or "ডকুমেন্ট" in t:
        try:
            import knowledge_base
            kb = knowledge_base.handle(user_text)
            if kb is not None:
                return kb
        except Exception as e:
            return True, f"নলেজ বেইজ সমস্যা: {e}"

    # 🌐 রিমোট কন্ট্রোল (Telegram)
    try:
        import remote_bot
        rb = remote_bot.handle(user_text)
        if rb is not None:
            return rb
    except Exception:
        pass

    # 🧠 মেমরি ম্যানেজমেন্ট (list/search/delete/disable/history/test)
    if any(k in t for k in ("মেমরি", "memory", "সেভ করা", "হিস্ট্রি", "success rate")):
        return True, _memory_admin_router(user_text)

    # 🎵 YouTube গান
    yt = _yt_router(user_text)
    if yt is not None:
        return yt

    # 🔊🔊️ ভলিউম/ব্রাইটনেস
    vb = _vol_bright_router(user_text)
    if vb is not None:
        return vb

    # 🖱️ মাউস/কিবোর্ড
    mk = _mouse_kb_router(user_text)
    if mk is not None:
        return mk

    # 🖥️ PC নিয়ন্ত্রণ (Start menu/উইন্ডো/Explorer)
    pc = _pc_router(user_text)
    if pc is not None:
        return pc

    # লোকাল ফাইল রাউটার — ফোল্ডার/ফাইল কাজ AI কল ছাড়াই, ইনস্ট্যান্ট
    fr = _file_action_router(user_text)
    if fr is not None:
        return fr

    # ডিলিট
    if any(w in t for w in ("মুছ", "ডিলিট", "delete", "remove")) and (
        "ফোল্ডার" in t or "folder" in t or any(k in t for k in CLOSE_MAP)
    ):
        if "ফোল্ডার" in t or "folder" in t:
            return True, _cmd_delete(_extract_target(user_text))

    # তৈরি
    if any(w in t for w in ("বানা", "তৈরি", "create", "make")) and (
        "ফোল্ডার" in t or "folder" in t
    ):
        return True, _cmd_create(_extract_target(user_text))

    # বন্ধ করা
    if any(w in t for w in ("বন্ধ কর", "ক্লোজ", "close")):
        return True, _cmd_close(_extract_target(user_text))

    # খোলা
    if any(w in t for w in ("খোল", "খুল", "ওপেন", "open", "চালাও")):
        _tgt = _extract_target(user_text)
        if not _tgt and ("ফোল্ডার" in t or "folder" in t):
            return True, _cmd_open("ফোল্ডার")  # নাম নেই → ফোল্ডার-তালিকা + folder_pick মোড
        return True, _cmd_open(_tgt)

    # ফোল্ডার মুছে দাও (শব্দ উল্টো থাকলে)
    if ("ফোল্ডার" in t or "folder" in t) and any(w in t for w in ("মুছ", "ডিলিট", "delete")):
        return True, _cmd_delete(_extract_target(user_text))

    # 🔤 ফাজি ইনটেন্ট — যেভাবেই বলুন, কাছাকাছি হলে ধরবে
    fz = _fuzzy_intent_router(user_text)
    if fz is not None:
        return fz

    return False, ""
EXIT_KEYWORD = "বন্ধ"

chat_history = [{"role": "system", "content": SYSTEM_PROMPT}]
_GEMINI_FAILED = False  # Gemini একবার ব্যর্থ হলে সেশনে আর Ollama-ই ব্যবহার হবে
USER_NAME = None
MEMORY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, "frozen", False) else __file__)),
    "asif_memory.json",
)


# ----------------- 🧠 স্মৃতি (পিসি বন্ধ হলেও মনে থাকে) -----------------
def load_memory() -> None:
    global chat_history, USER_NAME
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, encoding="utf-8") as f:
                data = json.load(f)
            USER_NAME = data.get("name")
            saved = data.get("history", [])
            # system prompt টা সবসময় নতুন করে বসাও
            chat_history = [{"role": "system", "content": _system_prompt()}]
            chat_history += [m for m in saved if m.get("role") != "system"]
        except Exception:
            pass


def save_memory() -> None:
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"name": USER_NAME, "history": chat_history},
                      f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _system_prompt() -> str:
    """স্তরযুক্ত পরিচয়-প্রম্পট (identity.py থেকে — স্থায়ী কনফিগ)।"""
    try:
        import identity
        return identity.build_system_prompt().replace("{{MEMORY}}", "(নেই)") \
            .replace("{{CONTEXT}}", "(নেই)")
    except Exception:
        return SYSTEM_PROMPT


def remember_name(text: str) -> None:
    """'আমার নাম রাকিব' জাতীয় বাক্য থেকে নাম শিখে রাখে।"""
    global USER_NAME
    m = re.search(r"আমার\s*নাম\s+([^,।!?\s]+)", text)
    if m:
        USER_NAME = m.group(1)
        print(f"💾 আসিফ আপনার নাম মনে রাখলো: {USER_NAME}")


def time_greeting() -> str:
    h = datetime.datetime.now().hour
    if 4 <= h < 12:
        return "শুভ সকাল"
    if 12 <= h < 16:
        return "শুভ দুপুর"
    if 16 <= h < 19:
        return "শুভ বিকেল"
    return "শুভ সন্ধ্যা"


# ----------------- 🎤 শোনা -----------------
STT_LANGS = ("bn-BD", "bn-IN", "en-US")
_LAST_STT = {"text": "", "time": 0.0}


def _rms(chunk: bytes) -> float:
    import numpy as np
    a = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(a ** 2)) + 1e-9)


def _has_bengali(text: str) -> bool:
    return any("\u0980" <= ch <= "\u09FF" for ch in text or "")


def listen(max_seconds: int = 20) -> str | None:
    """মাইক থেকে বাংলা/ইংরেজি/মিশ্র কথা শোনে। Real VAD:
    ambient-noise calibration, pre-roll, ১.১s trailing pause, ২০s cap."""
    import numpy as np
    import sounddevice as sd
    import speech_recognition as sr

    # স্পিকার বাজতে থাকলে মাইক ফিডব্যাক এড়াতে অপেক্ষা
    try:
        import voice_engine
        wait_until = time.time() + 6
        while voice_engine.is_speaking() and time.time() < wait_until:
            time.sleep(0.1)
    except Exception:
        pass

    chunks: list[bytes] = []

    def callback(indata, frames, t, status):
        chunks.append(indata.copy().tobytes())

    print("🎤 শুনছি... (বলুন, থামলে নিজেই বুঝবে)")
    block = int(SAMPLE_RATE * 0.1)      # 100 ms
    blocks_per_sec = 10
    max_blocks = max_seconds * blocks_per_sec
    trailing_blocks = 11                # ~1.1 s নীরবতা = কথা শেষ (ছোট বিরতি রাখে)
    preroll_blocks = 4                  # কথা শুরুর আগের ০.৪s রাখে (প্রথম শব্দ কাটে না)

    speech_started = False
    quiet_blocks = 0
    total_blocks = 0
    pending: list[bytes] = []
    recording: list[bytes] = []
    threshold = 300.0
    noise_floor = 100.0

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                            dtype="int16", blocksize=block, callback=callback):
            # ০.৩s ambient noise ক্যালিব্রেশন
            noise_samples: list[float] = []
            while total_blocks < 3:
                sd.sleep(100)
                total_blocks += 1
                if chunks:
                    noise_samples.append(_rms(chunks[-1]))
            if noise_samples:
                noise_floor = float(np.median(noise_samples))
                threshold = max(220.0, noise_floor * 2.6)

            while total_blocks < max_blocks:
                sd.sleep(100)
                total_blocks += 1
                if not chunks:
                    continue
                raw = chunks[-1]
                rms = _rms(raw)
                if not speech_started and rms < threshold:
                    # পরিবেশের শব্দ ধীরে শিখে threshold ঠিক রাখে
                    noise_floor = 0.97 * noise_floor + 0.03 * rms
                    threshold = max(220.0, noise_floor * 2.6)
                    pending.append(raw)
                    if len(pending) > preroll_blocks:
                        pending.pop(0)
                    continue
                speaking_now = rms > threshold
                if speaking_now and not speech_started:
                    speech_started = True
                    recording.extend(pending)   # pre-roll সহ
                    recording.append(raw)
                    quiet_blocks = 0
                elif speech_started:
                    recording.append(raw)
                    if speaking_now:
                        quiet_blocks = 0
                    else:
                        quiet_blocks += 1
                        if quiet_blocks >= trailing_blocks:
                            break
    except Exception as e:
        print(f"⚠️  মাইক সমস্যা: {e}")
        return None

    if not speech_started or not recording:
        return None

    raw = b"".join(recording)
    audio_data = sr.AudioData(raw, SAMPLE_RATE, 2)
    text = _recognize(audio_data)
    if not text:
        print("⚠️  বুঝতে পারিনি, আবার বলুন।")
        return None
    # একই কথা ১.৫ সেকেন্ডের মধ্যে দুইবার প্রসেস হবে না
    now = time.time()
    if text == _LAST_STT["text"] and now - _LAST_STT["time"] < 1.5:
        return None
    _LAST_STT["text"], _LAST_STT["time"] = text, now
    print(f"🧑 আপনি: {text}")
    return text


def _pick_transcript(cands: dict) -> str | None:
    """বাংলা-স্ক্রিপ্ট থাকলে বাংলা ফলাফলকে প্রাধান্য; নাহলে ইংরেজি।"""
    bn = [t for lang, t in cands.items() if lang.startswith("bn") and t]
    en = cands.get("en-US") or ""
    best_bn = max(bn, key=len) if bn else ""
    if best_bn and _has_bengali(best_bn) and len(best_bn) >= 3:
        return best_bn
    if en.strip():
        return en.strip()
    if best_bn.strip():
        return best_bn.strip()
    return None


def _recognize(audio_data: "sr.AudioData") -> str | None:
    """বাংলা (bn-BD → bn-IN) + English/mixed (en-US) একসাথে চেষ্টা করে
    সবচেয়ে বিশ্বাসযোগ্য ট্রান্সক্রিপ্ট বেছে নেয়।"""
    import speech_recognition as sr

    cands: dict[str, str] = {}
    for lang in STT_LANGS:
        try:
            t = _recognize_direct(audio_data, lang)
            if t:
                cands[lang] = t
        except Exception as e:
            print(f"ℹ️  STT direct ব্যর্থ ({lang}): {type(e).__name__}")
    picked = _pick_transcript(cands)
    if picked:
        return picked

    # fallback: SpeechRecognition-এর নিজস্ব Google পথ (কখনো flac converter লাগে)
    r = sr.Recognizer()
    for lang in STT_LANGS:
        try:
            t = r.recognize_google(audio_data, language=lang)
            if t and t.strip():
                return t.strip()
        except sr.UnknownValueError:
            continue
        except Exception:
            break
    print("⚠️  বুঝতে পারিনি — কাছে গিয়ে পরিষ্কার করে আবার বলুন (মাইক-এ শব্দ কম রাখুন)")
    return None


def _recognize_direct(audio_data: "sr.AudioData", lang: str | None = None) -> str | None:
    """Google Speech API-তে raw 16 kHz PCM (audio/l16) পাঠায়।

    আগের কোড RIFF/WAV হেডারসহ bytes পাঠাত কিন্তু Content-Type ছিল
    audio/l16 — অর্থাৎ হেডারকেও speech ধরে নেওয়া হতো। এখন শুধু PCM যায়।"""
    try:
        pcm = audio_data.get_raw_data(convert_rate=SAMPLE_RATE, convert_width=2)
        langs = (lang,) if lang else STT_LANGS
        for lg in langs:
            url = (f"{STT_URL}?output=json&lang={lg}&key={STT_KEY}"
                   "&pfilter=2")
            r = requests.post(
                url,
                data=pcm,
                headers={"Content-Type": f"audio/l16; rate={SAMPLE_RATE}"},
                timeout=(5, 45),
            )
            r.raise_for_status()
            for line in r.text.splitlines():
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                results = obj.get("result", [])
                if results:
                    alts = results[0].get("alternative", [])
                    if alts and alts[0].get("transcript"):
                        return alts[0]["transcript"].strip()
        return None
    except Exception as e:
        print(f"⚠️  শনাক্ত করতে সমস্যা: {e}")
        return None


def listen_keyboard() -> str:
    """মাইক না থাকলে টাইপ করে কথা বলা যায়।"""
    try:
        return input("🧑 আপনি (টাইপ করুন): ").strip()
    except (EOFError, KeyboardInterrupt):
        return "বন্ধ হও"


# ----------------- 🧠 ভাবা -----------------
def think(user_text: str) -> str:
    """LLM দিয়ে বাংলায় উত্তর তৈরি করে।"""
    global _GEMINI_FAILED
    remember_name(user_text)
    try:
        import context_engine as _ctx
        _ctx.update(user_text)
    except Exception:
        _ctx = None
    chat_history[0]["content"] = _system_prompt()
    if _ctx:
        try:
            _cb = _ctx.build_block()
            if _cb:
                chat_history[0]["content"] += "\n\n[সক্রিয় প্রসঙ্গ]\n" + _cb
        except Exception:
            pass
    chat_history.append({"role": "user", "content": user_text})

    reply = _ask_ollama()  # 🧠 প্রধান brain: লোকাল Ollama (ফ্রি, দ্রুত, offline)
    if reply is None and GEMINI_KEY and not _GEMINI_FAILED:
        reply = _ask_gemini()
        if reply is None:
            _GEMINI_FAILED = True
            print("ℹ️  এই সেশনে Gemini বাদ")
    if reply is None and OPENAI_KEY:
        reply = _ask_openai()
    if reply is None:
        reply = _ask_ollama()
    if reply is None:
        reply = ("দুঃখিত, আমার ব্রেন এখন কানেক্টেড না। "
                 "Ollama চালু আছে কি দেখুন — টার্মিনালে লিখুন: ollama serve। "
                 "অথবা ইন্টারনেট ও Gemini key চেক করুন।")

    chat_history.append({"role": "assistant", "content": reply})
    # হিস্ট্রি বড় হলে পুরনোগুলো বাদ দাও (system prompt ছাড়া)
    if len(chat_history) > 21:
        del chat_history[1:11]
    save_memory()
    try:
        import context_engine as _ctx2
        _ctx2.record_result(reply)
    except Exception:
        pass
    return reply


def _pick_gemini_model() -> None:
    """key-তে যেসব মডেল আছে তা জেনে সেরা টেক্সট মডেল বেছে নেয়।"""
    global GEMINI_MODEL
    try:
        r = requests.get(GEMINI_URL, headers={"x-goog-api-key": GEMINI_KEY}, timeout=30)
        r.raise_for_status()
        names = []
        for m in r.json().get("models", []):
            if "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            n = m.get("name", "").replace("models/", "")
            skip = ("image", "audio", "tts", "live", "embed", "aqa", "vision",
                    "native-audio", "image-generation")
            if any(s in n for s in skip):
                continue
            names.append(n)
        flash = [n for n in names if "flash" in n and "thinking" not in n]
        # সবচেয়ে নতুন জেনারেশন আগে (gemini-3* → তারপর বাকি)
        newest = [n for n in flash if "gemini-3" in n]
        pick = (newest or flash or names)
        if pick:
            GEMINI_MODEL = pick[0]
            print(f"ℹ️  Gemini মডেল: {GEMINI_MODEL}")
    except Exception as e:
        print(f"⚠️  Gemini মডেল তালিকা আনতে সমস্যা: {e}")


def _ask_gemini() -> str | None:
    """Google Gemini (ফ্রি কোটা) — বাংলা দারুণ বলে।"""
    try:
        def _call(model_name: str):
            contents = []
            for m in chat_history:
                if m["role"] == "system":
                    continue
                contents.append({"role": "user" if m["role"] == "user" else "model",
                                 "parts": [{"text": m["content"]}]})
            if not contents:  # 🐛 FIX: খালি contents হলে API 400 দেয় — ডিফল্ট প্রশ্ন
                contents = [{"role": "user", "parts": [{"text": "হ্যালো"}]}]
            return requests.post(
                f"{GEMINI_URL}/{model_name}:generateContent",
                headers={"x-goog-api-key": GEMINI_KEY},
                json={
                    "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                    "contents": contents,
                    "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.9,
                                    "thinkingConfig": {"thinkingBudget": 0}},
                },
                timeout=(5, 45),
            )

        r = _call(GEMINI_MODEL)
        if r.status_code == 404:  # মডেল পুরনো/বন্ধ — তালিকা থেকে সঠিকটা খোঁজো
            _pick_gemini_model()
            r = _call(GEMINI_MODEL)
        if r.status_code in (400, 401, 403):
            print(f"⚠️  Gemini key প্রত্যাখ্যাত (HTTP {r.status_code}): {r.text[:200]}")
            print("💡 সমাধান: aistudio.google.com/apikey-তে গিয়ে নতুন key বানিয়ে asif_key.txt-এ বসান")
            return None
        r.raise_for_status()
        cands = r.json().get("candidates", [])
        if cands:
            parts = cands[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts).strip()
            if text:
                return text
        return None
    except requests.HTTPError as e:
        resp = getattr(e, "response", None)
        status = resp.status_code if resp is not None else "?"
        body = (resp.text[:200] if resp is not None else "")
        print(f"⚠️  Gemini সমস্যা (HTTP {status}): {body}")
        return None
    except Exception as e:
        print(f"⚠️  Gemini সমস্যা: {type(e).__name__}: {e}")
        return None


def _ask_openai() -> str | None:
    try:
        r = requests.post(
            OPENAI_URL,
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={"model": OPENAI_MODEL, "messages": chat_history, "max_tokens": 300},
            timeout=(5, 45),
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"⚠️  OpenAI সমস্যা: {e}")
        return None


def _ollama_pick_model() -> str | None:
    """Ollama-তে যে মডেল আছে সেটাই বেছে নেয় (বড়টা আগে পছন্দ)।"""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        r.raise_for_status()
        names = [m["name"] for m in r.json().get("models", [])]
        prefs = ("llama3.2:1b", "llama3.2:3b", "gemma2") if _SPEED_MODE else                 ("llama3.2:3b", "qwen2.5:3b", "gemma2", "llama3.2:1b", "llama")
        for pref in prefs:
            for n in names:
                if n.startswith(pref):
                    return n
        return names[0] if names else None
    except Exception:
        return None


def _ollama_chat(payload_extra: dict | None = None, timeout: int = 120):
    """Ollama-তে একটা রিকোয়েস্ট পাঠায় (দ্রুত সেটিংস সহ)।"""
    model = _ollama_pick_model() or OLLAMA_MODEL
    payload = {
        "model": model,
        "messages": chat_history,
        "stream": False,
        "keep_alive": "1h",   # মডেল RAM-এ থাকে — প্রতিবার লোড হয় না
        "options": {"num_predict": 45, "num_thread": 8},  # আরো ছোট উত্তর + পুরো CPU
    }
    if payload_extra:
        payload.update(payload_extra)
    return requests.post(OLLAMA_URL, json=payload, timeout=timeout)


def _ask_ollama() -> str | None:
    try:
        r = _ollama_chat()
        if r.status_code == 404:  # মডেল নেই — তালিকা থেকে আবার খোঁজো
            _ollama_pick_model()
            r = _ollama_chat()
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except Exception:
        return None


# ----------------- 🗣️ বলা -----------------
def _mci(command: str) -> None:
    ctypes.windll.winmm.mciSendStringW(
        ctypes.create_unicode_buffer(command), None, 0, 0
    )


def _clean_for_tts(text: str) -> str:
    """উচ্চারণ-প্রস্তুতি: voice_engine-এর পূর্ণ বাংলা নরমালাইজার ব্যবহার করে।"""
    try:
        import voice_engine
        return voice_engine.normalize_text(text)
    except Exception:
        t = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"\1 শতাংশ", text)
        t = t.replace("°C", " ডিগ্রি সেলসিয়াস").replace("°F", " ডিগ্রি ফারেনহাইট")
        t = re.sub(r"[*_#`~^<>|]", " ", t)
        t = re.sub(r"\s+", " ", t)
        return t.strip()


def speak(text: str) -> None:
    """স্পষ্ট বাংলা কণ্ঠ — verified Bengali voices, interruptible playback,
    provider fallback (Edge → gTTS → Bengali SAPI only)."""
    try:
        import voice_engine
        voice_engine.speak(text)
    except Exception as e:
        print(f"⚠️  TTS ব্যর্থ: {type(e).__name__}: {e}")


def stop_speaking() -> None:
    try:
        import voice_engine
        voice_engine.stop()
    except Exception:
        pass



# ----------------- ⚡ স্ট্রিমিং (বাক্য তৈরি হলেই সাথে সাথে বলা) -----------------
def _split_sentences(buf: str) -> tuple[list[str], str]:
    """বাক্য-শেষ চিহ্ন (।!?.) দেখে সম্পূর্ণ বাক্যগুলো আলাদা করে।"""
    ends = [i for i, ch in enumerate(buf) if ch in "।!?.\n"]
    out = []
    pos = 0
    for i in ends:
        out.append(buf[pos:i + 1])
        pos = i + 1
    return out, buf[pos:]


def _player(q: "queue.Queue") -> None:
    """বাক্যের লাইনে দাঁড়িয়ে একটার পর একটা বলে যায়।"""
    while True:
        sent = q.get()
        try:
            if sent is None:
                return
            speak(sent)
        finally:
            q.task_done()


def converse(user_text: str) -> str:
    """ব্রেন (Gemini প্রাইমারি → Ollama ফলব্যাক) — বাক্য পুরো হলেই TTS।"""
    global _GEMINI_FAILED
    import identity as _ident
    remember_name(user_text)
    chat_history[0]["content"] = _system_prompt()
    chat_history.append({"role": "user", "content": user_text})

    q: "queue.Queue" = queue.Queue()
    threading.Thread(target=_player, args=(q,), daemon=True).start()

    # 🧬 স্তরযুক্ত prompt: পরিচয় + স্মৃতি + প্রসঙ্গ (A-H স্থাপত্য)
    full_prompt = _ident.build_system_prompt()
    try:
        import memory_longterm as mlt
        mem_ctx = mlt.build_context(user_text)
        full_prompt = full_prompt.replace("{{MEMORY}}", mem_ctx[:900] or "(নেই)")
        recent = [m for m in chat_history if m["role"] != "system"][-6:]
        ctx2 = "\n".join(f"{'ব্যবহারকারী' if m['role']=='user' else 'তুমি'}: {m['content'][:120]}"
                          for m in recent)
        full_prompt = full_prompt.replace("{{CONTEXT}}", ctx2 or "(নেই)")
    except Exception:
        full_prompt = full_prompt.replace("{{MEMORY}}", "(নেই)").replace("{{CONTEXT}}", "(নেই)")

    # 🧠 সক্রিয় প্রসঙ্গ: প্রজেক্ট/মডিউল/ফাইল + "এটা/ওটা/আগেরটা" রেফারেন্স
    try:
        import context_engine as _ctx
        _ctx.update(user_text)
        ctx_block = _ctx.build_block()
        if ctx_block:
            full_prompt += ("\n\n[সক্রিয় প্রসঙ্গ — ব্যবহারকারীর আগের কথা মনে রাখো, "
                            "অপ্রয়োজনীয় প্রশ্ন করো না]\n" + ctx_block)
        resolved = _ctx.resolve_text(user_text)
        if resolved != user_text:
            full_prompt += "\n\n[রেফারেন্স]\n" + resolved
    except Exception:
        pass

    def _emit(p: str) -> None:
        try:
            import identity
            p = identity.quality_filter(p, user_text)
        except Exception:
            pass
        p = p.strip()
        if p:
            print(f"🤖 {p}")
            q.put(p)
            full.append(p)

    full: list[str] = []
    buf = ""
    made_stream = False

    # 🥇 প্রাইমারি ব্রেন: Gemini (স্ট্রিমিং SSE)
    if GEMINI_KEY and not _GEMINI_FAILED:
        try:
            contents = [{"role": "user" if m["role"] == "user" else "model",
                         "parts": [{"text": m["content"]}]}
                        for m in chat_history if m["role"] != "system"]
            if not contents:
                contents = [{"role": "user", "parts": [{"text": "হ্যালো"}]}]
            url = f"{GEMINI_URL}/{GEMINI_MODEL}:streamGenerateContent?alt=sse"
            with requests.post(url, headers={"x-goog-api-key": GEMINI_KEY},
                               json={"systemInstruction": {"parts": [{"text": full_prompt}]},
                                     "contents": contents,
                                     "generationConfig": {"maxOutputTokens": 500,
                                                          "temperature": 0.9,
                                                          "thinkingConfig": {"thinkingBudget": 0}}},
                               stream=True, timeout=(5, 180)) as r:
                r.raise_for_status()
                for raw in r.iter_lines():
                    if not raw:
                        continue
                    line = raw.decode("utf-8")
                    if not line.startswith("data: "):
                        continue
                    try:
                        data = json.loads(line[6:])
                    except Exception:
                        continue
                    cands = data.get("candidates", [])
                    if cands:
                        for part in cands[0].get("content", {}).get("parts", []):
                            tok = part.get("text", "")
                            if tok:
                                buf += tok
                                parts, buf = _split_sentences(buf)
                                for p in parts:
                                    _emit(p)
                    if data.get("candidates", [{}])[0].get("finishReason") in ("STOP", "MAX_TOKENS"):
                        break
            made_stream = True
        except Exception as e:
            print(f"ℹ️  Gemini streaming ব্যর্থ ({type(e).__name__}) — Ollama fallback...")

    # 🥈 ফলব্যাক: Ollama স্ট্রিমিং
    if not made_stream:
        try:
            payload = {
                "model": _ollama_pick_model() or OLLAMA_MODEL,
                "messages": [{"role": "system", "content": full_prompt}]
                + [m for m in chat_history if m["role"] != "system"],
                "stream": True,
                "keep_alive": "1h",
                "options": {"num_predict": 60, "num_thread": 8},
            }
            with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=(5, 180)) as r:
                r.raise_for_status()
                for raw in r.iter_lines():
                    if not raw:
                        continue
                    try:
                        data = json.loads(raw.decode("utf-8"))
                    except Exception:
                        continue
                    tok = data.get("message", {}).get("content", "")
                    if tok:
                        buf += tok
                        parts, buf = _split_sentences(buf)
                        for p in parts:
                            _emit(p)
                    if data.get("done"):
                        break
        except Exception as e:
            print(f"⚠️  স্ট্রিমিং ব্যর্থ ({type(e).__name__})")
    if buf.strip():
        _emit(buf.strip())

    reply = " ".join(full).strip()
    chat_history.append({"role": "assistant", "content": reply})
    if len(chat_history) > 21:
        del chat_history[1:11]
    save_memory()
    q.put(None)
    q.join()   # শেষ বাক্যটাও বলা হওয়া পর্যন্ত অপেক্ষা
    # 🧬 স্থায়ী কথোপকথন সংরক্ষণ + প্রয়োজনে সারসংক্ষেপ
    try:
        import memory_longterm as mlt
        mlt.add_message("user", user_text)
        mlt.add_message("assistant", reply)
        mlt.maybe_summarize()
    except Exception:
        pass
    try:
        import context_engine as _ctx
        _ctx.record_result(reply)
    except Exception:
        pass
    return reply


# ----------------- মূল লুপ -----------------
def main() -> None:
    print("=" * 50)
    print("🎙️  AVA Universal AI — বাংলা ভয়েস অ্যাসিস্ট্যান্ট")
    print("=" * 50)

    mic_ok = True
    try:
        import sounddevice as sd  # noqa: F401
    except ImportError:
        mic_ok = False
        print("⚠️  মাইক লাইব্রেরি (sounddevice) নেই — টাইপ করে কথা বলার মোড চালু")
    global MIC_OK, _PENDING_LEARN
    MIC_OK = mic_ok
    if _ollama_pick_model():
        print("🧠 Brain: Ollama (লোকাল) — প্রস্তুত!")
    elif not OPENAI_KEY and not GEMINI_KEY:
        print("ℹ️  কোনো brain পাওয়া যায়নি — Ollama ইনস্টল করুন")
    elif GEMINI_KEY:
        print("🧠 Brain: Gemini API")
    else:
        print("🧠 Brain: OpenAI API")

    load_memory()
    try:
        import updater
        print("📦 " + updater.version_info())
    except Exception:
        pass
    try:
        import memory_db, memory_longterm as mlt
        if memory_db.load_credentials():
            mlt.ensure_schema()
            mlt.start_session()
    except Exception:
        pass
    try:
        import scheduler
        scheduler.startup()   # রিমাইন্ডার থ্রেড চালু
    except Exception:
        pass
    try:
        import remote_bot
        print("🌐 " + remote_bot.startup())   # রিমোট বট (টোকেন থাকলে)
    except Exception:
        pass
    try:
        import task_engine as _te

        def _task_progress(kind, data):
            tid = str(data.get("task_id", ""))[:8]
            if kind == "approval_required":
                print(f"🧩 টাস্ক {tid}: অনুমোদন দরকার — {data.get('title')}")
            elif kind == "completed":
                print(f"✅ টাস্ক {tid}: সম্পন্ন")
            elif kind == "failed":
                print(f"❌ টাস্ক {tid}: ব্যর্থ — {data.get('error')}")
            elif kind == "retry":
                print(f"🔁 টাস্ক {tid}: retry {data.get('attempt')}")

        _te.ensure_schema()
        resumed = _te.resume_pending()
        _te.start_worker(_task_progress)
        print(f"🧩 টাস্ক ইঞ্জিন চালু ({len(resumed)}টি টাস্ক পুনরুদ্ধার)")
    except Exception as e:
        print(f"⚠️ টাস্ক ইঞ্জিন চালু হয়নি: {type(e).__name__}: {e}")
    if USER_NAME:
        print(f"👋 AVA আপনাকে চেনে: {USER_NAME}")
    greeting = (
        f"{time_greeting()}{', ' + USER_NAME if USER_NAME else ''}! "
        "আমি AVA, আপনার সহকারী। কীভাবে সাহায্য করতে পারি?"
    )
    print(f"🤖 AVA: {greeting}\n")
    speak(greeting)

    # ব্যাকগ্রাউন্ডে মডেল লোড করে রাখো — প্রথম প্রশ্নেও দ্রুত উত্তর
    def _warm():
        try:
            _ollama_chat({"messages": [{"role": "user", "content": "হ্যাঁ"}],
                          "options": {"num_predict": 1}}, timeout=120)
        except Exception:
            pass
    threading.Thread(target=_warm, daemon=True).start()

    while True:
        if mic_ok:
            user_text = listen()
            if not user_text:
                continue
        else:
            user_text = listen_keyboard()

        # প্রথমে দেখো কোনো কাজ করতে বলেছে কি না
        try:
            import context_engine as _ctx
            _ctx.update(user_text)
        except Exception:
            _ctx = None
        handled, reply = try_command(user_text)
        if handled:
            print(f"🤖 আসিফ: {reply}\n")
            speak(reply)
            try:
                if _ctx:
                    _ctx.record_result(reply)
            except Exception:
                pass
            # 💾 শেখার প্রস্তাব (শুধু সফল যাচাইকৃত কাজে, অনুমতি সহ)
            if _PENDING_LEARN:
                payload, _PENDING_LEARN = _PENDING_LEARN, None
                try:
                    import memory_db
                    learn = memory_db.maybe_learn(
                        payload["text"], payload["intent"], payload["action_type"],
                        payload["template"], payload["schema"], payload["aliases"],
                        speak_cb=speak, confirm_cb=_confirm)
                    if learn:
                        print(f"🤖 আসিফ: {learn}\n")
                        speak(learn)
                except Exception:
                    pass
            continue

        # কোনো গুরুত্বপূর্ণ তথ্য ছাড়া ধ্বংসাত্মক/অস্পষ্ট কাজ অনুমান করবে না
        try:
            clar = _ctx.needs_clarification(user_text) if _ctx else None
        except Exception:
            clar = None
        if clar:
            print(f"🤖 আসিফ: {clar}\n")
            speak(clar)
            try:
                if _ctx:
                    _ctx.record_result(clar, ok=False)
            except Exception:
                pass
            continue

        low = user_text.lower()
        if low in {"stop", "exit", "quit"} or user_text.strip() == "বন্ধ":
            break
        if any(w in user_text for w in EXIT_WORDS):
            break

        print("🤔 ভাবছি... (বাক্য তৈরি হলেই সাথে সাথে বলা শুরু হবে)")
        t0 = time.time()
        reply = converse(user_text)
        if reply:
            print(f"⏱ প্রথম বাক্য সাথে সাথে, মোট {time.time() - t0:.1f}s")
        else:  # brain ব্যর্থ → পুরনো নিরাপদ পথ
            reply = think(user_text)
            print(f"🤖 আসিফ: {reply}\n")
            speak(reply)

    bye = "বিদায়! আবার দেখা হবে।"
    print(f"🤖 আসিফ: {bye}")
    speak(bye)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 বন্ধ করা হলো।")
    except Exception:
        import traceback
        print("\n" + "=" * 50)
        print("❌ অপ্রত্যাশিত সমস্যা — নিচের এররটা ডেভেলপারকে দিন:")
        print("=" * 50)
        traceback.print_exc()
        try:
            input("\n[বন্ধ করতে Enter চাপুন...]")
        except Exception:
            pass
