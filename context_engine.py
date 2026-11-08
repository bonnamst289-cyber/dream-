# -*- coding: utf-8 -*-
"""AVA Context Intelligence — remembers the active project/module/file and
resolves follow-up references like "এটা", "ওটা", "আগেরটা", "এবার".

Persisted to `ava_context.json` next to the app so it survives restarts.
This is deliberately conservative: it never guesses a destructive target.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys
import threading

_STATE_FILE_NAME = "ava_context.json"
_lock = threading.Lock()
_state: dict | None = None


def _app_dir() -> str:
    if not getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(__file__))
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    for d in (os.path.abspath(os.getcwd()), exe_dir, os.path.dirname(exe_dir)):
        if d and (os.path.exists(os.path.join(d, "asif_key.txt"))
                  or os.path.exists(os.path.join(d, "ava_context.json"))):
            return d
    return os.path.abspath(os.getcwd())


STATE_FILE = os.path.join(_app_dir(), _STATE_FILE_NAME)

_DEFAULT = {
    "active_project": None,      # {"name": str, "path": str}
    "active_module": None,
    "active_file": None,
    "last_instruction": "",
    "last_result": "",
    "last_task": None,
    "constraints": [],
    "pending_question": None,
    "updated": "",
}

MODULES = {
    "attendance": ["attendance", "অ্যাটেনডেন্স", "এটেনডেন্স", "হাজিরা"],
    "sms": ["sms", "এসএমএস", "guardian sms", "গার্ডিয়ান এসএমএস"],
    "api": ["api", "এপিআই"],
    "database": ["database", "ডেটাবেস", "ডাটাবেস", "db"],
    "auth": ["auth", "login", "লগইন", "authentication", "অথেন্টিকেশন"],
    "payment": ["payment", "পেমেন্ট", "billing", "বিলিং"],
    "report": ["report", "রিপোর্ট"],
    "dashboard": ["dashboard", "ড্যাশবোর্ড"],
    "guardian": ["guardian", "গার্ডিয়ান", "অভিভাবক"],
    "student": ["student", "শিক্ষার্থী", "ছাত্র", "student module"],
    "teacher": ["teacher", "শিক্ষক"],
    "exam": ["exam", "পরীক্ষা", "exam module"],
    "result": ["result", "ফলাফল", "রেজাল্ট"],
    "inventory": ["inventory", "স্টক", "stock"],
    "notification": ["notification", "নোটিফিকেশন"],
    "frontend": ["frontend", "ফ্রন্টএন্ড", "front-end"],
    "backend": ["backend", "ব্যাকএন্ড", "back-end"],
}

_REFERENCE_WORDS = (
    "এটা", "এটি", "ওটা", "ওটি", "সেটা", "সেইটা", "সেটি", "এইটা", "ওইটা",
    "আগেরটা", "আগেরটি", "আগের", "সেই", "এবার", "আবার", "একই", "ওখানে",
    "এখানে", "এই", "ওই", "ঐ", "it", "that", "this", "same", "again",
    "previous", "earlier", "there",
)
_DESTRUCTIVE = (
    "মুছ", "মুছে", "ডিলিট", "delete", "remove", "রিমুভ", "uninstall",
    "আনইনস্টল", "format", "ফরম্যাট", "shutdown", "বন্ধ কর", "destroy",
    "drop table", "truncate",
)
_PROJECT_PATTERNS = [
    re.compile(r"(?:আমার| আমার)?\s*([A-Za-z0-9\u0980-\u09FF][\w\u0980-\u09FF .\-]{1,40}?)\s+প্রজেক্ট(?:ে|ের|টি|টা|টিতে|টার)?", re.I),
    re.compile(r"([A-Za-z0-9\u0980-\u09FF][\w\u0980-\u09FF .\-]{1,40}?)\s+(?:সফটওয়্যার|software|অ্যাপ|app)(?:ের|টি|টা|টিতে|টার)?", re.I),
    re.compile(r"project\s+(?:named\s+|called\s+)?([A-Za-z0-9_\-. ]{2,40})", re.I),
    re.compile(r"([A-Za-z0-9_\-. ]{2,40})\s+project", re.I),
]
_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"'<>|]+")
_FILE_RE = re.compile(r"[A-Za-z0-9_\-]+\.(?:py|js|ts|php|java|cs|json|md|txt|sql|html|css|env|ini|yml|yaml)\b", re.I)


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def load() -> dict:
    global _state
    with _lock:
        if _state is not None:
            return dict(_state)
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            st = dict(_DEFAULT)
            st.update({k: v for k, v in data.items() if k in _DEFAULT})
            _state = st
        except Exception:
            _state = dict(_DEFAULT)
        return dict(_state)


def _save(st: dict) -> None:
    global _state
    st["updated"] = _now()
    _state = st
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _detect_project(text: str) -> tuple[str, str] | None:
    t = text.strip()
    for pat in _PROJECT_PATTERNS:
        m = pat.search(t)
        if m:
            name = m.group(1).strip(" .,।!?")
            name = re.sub(r"^(আমার|new|নতুন)\s+", "", name, flags=re.I).strip()
            if len(name) >= 2 and name.lower() not in ("এই", "সেই", "আগের"):
                return name, ""
    if "নতুন প্রজেক্ট" in t or "new project" in t.lower():
        return "নতুন প্রজেক্ট", ""
    return None


def _detect_module(text: str) -> str | None:
    low = text.lower()
    for mod, aliases in MODULES.items():
        for a in aliases:
            if re.search(rf"(?<![\w\u0980-\u09FF]){re.escape(a)}(?![\w\u0980-\u09FF])", low, re.I):
                return mod
    return None


def _detect_constraint(text: str) -> str | None:
    low = text.lower()
    keys = ("ব্যবহার করো না", "করো না", "ছাড়া", "শুধু", "অবশ্যই", "must",
            "without", "avoid", "don't", "do not", "only", "পরে", "আগে",
            "যাচাই করে", "approval", "অনুমতি")
    if any(k in low for k in keys):
        return text.strip()[:240]
    return None


def is_reference(text: str) -> bool:
    low = (text or "").lower()
    return any(re.search(rf"(?<![\w\u0980-\u09FF]){re.escape(w)}(?![\w\u0980-\u09FF])", low)
               for w in _REFERENCE_WORDS)


def has_destructive(text: str) -> bool:
    low = (text or "").lower()
    return any(w in low for w in _DESTRUCTIVE)


def update(user_text: str) -> dict:
    """Update context from a new user instruction and return the state."""
    st = load()
    text = (user_text or "").strip()
    if not text:
        return st

    proj = _detect_project(text)
    if proj:
        st["active_project"] = {"name": proj[0], "path": proj[1]}
        st["active_module"] = None
        st["active_file"] = None

    m = _PATH_RE.search(text)
    if m:
        p = m.group(0)
        if os.path.isdir(p):
            st["active_project"] = {"name": os.path.basename(p.rstrip("\\/")),
                                    "path": p}
        else:
            st["active_file"] = p

    fm = _FILE_RE.search(text)
    if fm:
        st["active_file"] = fm.group(0)

    mod = _detect_module(text)
    if mod:
        st["active_module"] = mod

    con = _detect_constraint(text)
    if con and con not in st["constraints"]:
        st["constraints"] = (st["constraints"] + [con])[-8:]

    if is_reference(text):
        # keep context; resolved by build_block/resolve_text
        pass

    st["last_instruction"] = text
    st["pending_question"] = None
    _save(st)
    return dict(st)


def record_result(reply: str, ok: bool = True) -> None:
    st = load()
    st["last_result"] = (reply or "").strip()[:800]
    st["last_task"] = {"ok": bool(ok), "at": _now()}
    _save(st)


def set_active_project(name: str, path: str = "") -> None:
    st = load()
    st["active_project"] = {"name": name, "path": path}
    st["active_module"] = None
    st["active_file"] = None
    _save(st)


def set_module(module: str) -> None:
    st = load()
    st["active_module"] = module
    _save(st)


def get_active_project() -> dict | None:
    return load().get("active_project")


def build_block() -> str:
    """Compact Bengali context block for the system prompt."""
    st = load()
    lines = []
    proj = st.get("active_project") or {}
    if proj.get("name"):
        p = f"সক্রিয় প্রজেক্ট: {proj['name']}"
        if proj.get("path"):
            p += f" ({proj['path']})"
        lines.append(p)
    if st.get("active_module"):
        lines.append(f"সক্রিয় মডিউল: {st['active_module']}")
    if st.get("active_file"):
        lines.append(f"সক্রিয় ফাইল: {st['active_file']}")
    if st.get("last_instruction"):
        lines.append(f"সর্বশেষ নির্দেশ: {st['last_instruction'][:160]}")
    if st.get("last_result"):
        lines.append(f"সর্বশেষ ফলাফল: {st['last_result'][:160]}")
    if st.get("constraints"):
        lines.append("পূর্বের সীমাবদ্ধতা: " + " | ".join(c[:90] for c in st["constraints"][-3:]))
    return "\n".join(lines)


def resolve_text(user_text: str) -> str:
    """Add a short resolved-target hint for reference instructions."""
    st = load()
    if not is_reference(user_text):
        return user_text
    proj = st.get("active_project") or {}
    hints = []
    if proj.get("name"):
        hints.append(f"প্রজেক্ট={proj['name']}")
    if st.get("active_module"):
        hints.append(f"মডিউল={st['active_module']}")
    if st.get("active_file"):
        hints.append(f"ফাইল={st['active_file']}")
    if not hints:
        return user_text
    return f"{user_text}\n[উল্লেখিত প্রসঙ্গ: {', '.join(hints)}]"


def _has_named_target(text: str) -> bool:
    """'test_area ফোল্ডার' / 'report.sql ফাইল' → explicit; 'এই ফাইলটা' → not."""
    m = re.search(r"([A-Za-z0-9_\-.\u0980-\u09FF]+)\s*"
                  r"(?:ফোল্ডার|ফাইল|ডিরেক্টরি|directory|folder|file)", text, re.I)
    if not m:
        return False
    tok = m.group(1)
    vague = {"এই", "সেই", "ওই", "ঐ", "একটা", "এটি", "ওটা", "সেটা", "আগের",
             "the", "this", "that", "it", "same"}
    return tok.lower() not in vague


def needs_clarification(user_text: str) -> str | None:
    """Return ONE concise question only when guessing would be unsafe."""
    st = load()
    ref = is_reference(user_text)
    proj = st.get("active_project") or {}
    explicit = bool(_PATH_RE.search(user_text) or _FILE_RE.search(user_text)
                    or _detect_module(user_text) or _detect_project(user_text)
                    or _has_named_target(user_text)
                    or re.search(r"[\"“”']([^\"“”']{2,})[\"“”']", user_text))
    target_missing = not proj.get("name") and not st.get("active_module") and not st.get("active_file")
    if has_destructive(user_text) and not explicit and not st.get("active_file"):
        return ("কোন ফাইল বা ফোল্ডারটি মুছতে চান? নামটা বলুন — আমি অনুমতি ছাড়া "
                "কিছু মুছব না।")
    if ref and target_missing and any(w in user_text for w in ("টাস্ক", "কাজ", "প্রজেক্ট", "module", "ফাইল")):
        return "কোন প্রজেক্ট বা মডিউলের কথা বলছেন? একটু নামটা বলুন।"
    return None


def clear() -> None:
    _save(dict(_DEFAULT))


def export_state() -> dict:
    return load()
