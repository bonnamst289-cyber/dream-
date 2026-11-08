# -*- coding: utf-8 -*-
"""AVA Voice Engine — Bengali TTS with verified voices, normalization,
provider fallback, interruptible playback and real metrics.

Design rules
------------
* Never silently fall back to a voice that cannot speak Bengali.
  Windows SAPI is used ONLY if a Bengali SAPI voice is actually installed.
* All text goes through `normalize_text()` before synthesis.
* Playback is serialized so two replies can never overlap; `stop()` interrupts.
* Providers are tried in order and every failure is reported.
* No fake success: `speak()` metrics tell exactly which provider produced audio.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import os
import re
import sys
import tempfile
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass, field, asdict

def _app_dir() -> str:
    """Stable folder for config/cache; PyInstaller onefile runs from _MEIxxxx."""
    if not getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(__file__))
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    for d in (os.path.abspath(os.getcwd()), exe_dir, os.path.dirname(exe_dir)):
        if d and (os.path.exists(os.path.join(d, "voice_config.json"))
                  or os.path.exists(os.path.join(d, "asif_key.txt"))):
            return d
    return os.path.abspath(os.getcwd())


API_DIR = _app_dir()
CONFIG_FILE = os.path.join(API_DIR, "voice_config.json")
VOICE_CACHE_FILE = os.path.join(API_DIR, "voice_cache.json")

# Voices confirmed by a real edge-tts voice listing on this machine.
VERIFIED_EDGE_BN = [
    "bn-BD-NabanitaNeural",   # female, best measured mixed-language clarity
    "bn-BD-PradeepNeural",    # male
    "bn-IN-TanishaaNeural",   # female
    "bn-IN-BashkarNeural",    # male
]

# Curated, meaning-preserving Bengali renderings of common technical terms.
# Only whole Latin words are replaced; unknown terms are left untouched.
DEFAULT_GLOSSARY = {
    "Laravel": "লারাভেল", "Database": "ডেটাবেস", "Connection": "কানেকশন",
    "Attendance": "অ্যাটেনডেন্স", "Module": "মডিউল", "SMS": "এসএমএস",
    "Server": "সার্ভার", "API": "এপিআই", "GitHub": "গিটহাব",
    "Python": "পাইথন", "JavaScript": "জাভাস্ক্রিপ্ট", "Testing": "টেস্টিং",
    "Docker": "ডকার", "Linux": "লিনাক্স", "Windows": "উইন্ডোজ",
    "Chrome": "ক্রোম", "YouTube": "ইউটিউব", "WhatsApp": "হোয়াটসঅ্যাপ",
    "Telegram": "টেলিগ্রাম", "Google": "গুগল", "Email": "ইমেইল",
    "Password": "পাসওয়ার্ড", "Download": "ডাউনলোড", "Upload": "আপলোড",
    "File": "ফাইল", "Folder": "ফোল্ডার", "Error": "ত্রুটি", "Bug": "সমস্যা",
    "Login": "লগইন", "Logout": "লগআউট", "Install": "ইনস্টল",
    "Update": "আপডেট", "Backup": "ব্যাকআপ", "Report": "রিপোর্ট",
    "Client": "ক্লায়েন্ট", "Project": "প্রজেক্ট", "Meeting": "মিটিং",
    "Frontend": "ফ্রন্টএন্ড", "Backend": "ব্যাকএন্ড", "Framework": "ফ্রেমওয়ার্ক",
    "Deployment": "ডিপ্লয়মেন্ট", "Router": "রাউটার", "Controller": "কন্ট্রোলার",
    "Model": "মডেল", "View": "ভিউ", "Migration": "মাইগ্রেশন",
    "Query": "কোয়েরি", "Table": "টেবিল", "Schema": "স্কিমা",
    "Token": "টোকেন", "Session": "সেশন", "Cache": "ক্যাশ",
    "Debug": "ডিবাগ", "Release": "রিলিজ", "Branch": "ব্রাঞ্চ",
    "Commit": "কমিট", "Merge": "মার্জ", "Repository": "রিপোজিটরি",
    "Port": "পোর্ট", "Localhost": "লোকালহোস্ট", "IP": "আইপি",
    "URL": "ইউআরএল", "HTML": "এইচটিএমএল", "CSS": "সিএসএস",
    "JSON": "জেসন", "XML": "এক্সএমএল", "SQL": "এসকিউএল",
    "MySQL": "মাই এস কিউ এল", "PHP": "পিএইচপি", "Java": "জাভা",
    "Android": "অ্যান্ড্রয়েড", "Firebase": "ফায়ারবেস",
    "AVA": "আভা", "Guardian": "গার্ডিয়ান", "Integration": "ইন্টিগ্রেশন",
    "Firewall": "ফায়ারওয়াল", "Contract": "কন্ট্রাক্ট",
    "Configuration": "কনফিগারেশন", "Config": "কনফিগ",
    "Script": "স্ক্রিপ্ট", "System": "সিস্টেম", "Order": "অর্ডার",
    "Version": "ভার্সন", "Package": "প্যাকেজ", "Library": "লাইব্রেরি",
    "Function": "ফাংশন", "Variable": "ভেরিয়েবল", "Class": "ক্লাস",
    "Object": "অবজেক্ট", "Method": "মেথড", "Array": "অ্যারে",
    "String": "স্ট্রিং", "Exception": "এক্সেপশন", "Log": "লগ",
    "Console": "কনসোল", "Command": "কমান্ড", "Terminal": "টার্মিনাল",
    "Process": "প্রসেস", "Service": "সার্ভিস", "Endpoint": "এন্ডপয়েন্ট",
    "Request": "রিকোয়েস্ট", "Response": "রেসপন্স", "Header": "হেডার",
    "Payload": "পেলোড", "Status": "স্ট্যাটাস", "Success": "সফল",
    "Failure": "ব্যর্থ", "Warning": "সতর্কতা", "Audio": "অডিও",
    "Video": "ভিডিও", "Image": "ছবি", "Screen": "স্ক্রিন",
    "Vision": "ভিশন", "Automation": "অটোমেশন", "Agent": "এজেন্ট",
    "Memory": "মেমরি", "Context": "প্রসঙ্গ", "Task": "টাস্ক",
    "Plan": "পরিকল্পনা", "Step": "ধাপ", "Checkpoint": "চেকপয়েন্ট",
    "Resume": "রিজিউম", "Approval": "অনুমোদন", "Permission": "অনুমতি",
    "Security": "নিরাপত্তা", "Encryption": "এনক্রিপশন",
    "Restore": "রিস্টোর", "Index": "ইনডেক্স", "Column": "কলাম",
    "Record": "রেকর্ড", "Field": "ফিল্ড", "Form": "ফর্ম",
    "Button": "বাটন", "Page": "পেজ", "Route": "রুট",
    "Middleware": "মিডলওয়্যার", "Template": "টেমপ্লেট",
    "Component": "কম্পোনেন্ট", "Widget": "উইজেট",
    "Dashboard": "ড্যাশবোর্ড", "Chart": "চার্ট",
}

DEFAULT_CONFIG = {
    "provider_order": ["edge", "gtts"],
    "voice": "bn-BD-NabanitaNeural",
    "fallback_voices": ["bn-BD-PradeepNeural", "bn-IN-TanishaaNeural",
                        "bn-IN-BashkarNeural"],
    "rate": "+0%",
    "pitch": "+0Hz",
    "volume": "+0%",
    "playback_volume": 90,          # 0-100 (MCI 0-1000)
    "max_chunk_chars": 220,
    "trailing_pause_ms": 120,
    "glossary": DEFAULT_GLOSSARY,
}

_BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
_MONTHS = ["", "জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন",
           "জুলাই", "আগস্ট", "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর", "ডিসেম্বর"]

_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF\U00002B00-\U00002BFF\uFE0F]")

_cfg_lock = threading.Lock()
_play_lock = threading.Lock()
_speak_stop = threading.Event()
_current_alias: str | None = None
_alias_lock = threading.Lock()
_sapi_bn_cache: str | None | bool = False   # False=not checked, None=none found
_sapi_lock = threading.Lock()
_last_metrics: dict = {}


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
@dataclass
class VoiceConfig:
    provider_order: list = field(default_factory=lambda: list(DEFAULT_CONFIG["provider_order"]))
    voice: str = DEFAULT_CONFIG["voice"]
    fallback_voices: list = field(default_factory=lambda: list(DEFAULT_CONFIG["fallback_voices"]))
    rate: str = DEFAULT_CONFIG["rate"]
    pitch: str = DEFAULT_CONFIG["pitch"]
    volume: str = DEFAULT_CONFIG["volume"]
    playback_volume: int = DEFAULT_CONFIG["playback_volume"]
    max_chunk_chars: int = DEFAULT_CONFIG["max_chunk_chars"]
    trailing_pause_ms: int = DEFAULT_CONFIG["trailing_pause_ms"]
    glossary: dict = field(default_factory=lambda: dict(DEFAULT_GLOSSARY))

    @classmethod
    def load(cls) -> "VoiceConfig":
        cfg = cls()
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if hasattr(cfg, k) and v is not None:
                    setattr(cfg, k, v)
            merged = dict(DEFAULT_GLOSSARY)
            merged.update(data.get("glossary", {}))
            cfg.glossary = merged
        except Exception:
            pass
        return cfg

    def save(self) -> None:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, ensure_ascii=False, indent=2)
        except Exception:
            pass


CONFIG = VoiceConfig.load()


def configure(**kwargs) -> VoiceConfig:
    """Update runtime voice settings and persist them."""
    global CONFIG
    with _cfg_lock:
        for k, v in kwargs.items():
            if hasattr(CONFIG, k) and v is not None:
                setattr(CONFIG, k, v)
        CONFIG.save()
    return CONFIG


def set_voice(voice: str) -> None:
    configure(voice=voice)


# --------------------------------------------------------------------------
# Voice discovery (real, cached)
# --------------------------------------------------------------------------
def list_voices(refresh: bool = False) -> list[dict]:
    """Return edge-tts voices; result is cached for 7 days, never fabricated."""
    if not refresh:
        try:
            st = os.path.getmtime(VOICE_CACHE_FILE)
            if time.time() - st < 7 * 86400:
                with open(VOICE_CACHE_FILE, encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
    try:
        import edge_tts
        voices = asyncio.run(edge_tts.list_voices())
        data = [{"name": v.get("ShortName"), "locale": v.get("Locale"),
                 "gender": v.get("Gender")} for v in voices if v.get("ShortName")]
        with open(VOICE_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data
    except Exception as e:
        print(f"⚠️  Edge voice list failed: {type(e).__name__}: {e}")
        return []


def bengali_voices(refresh: bool = False) -> list[str]:
    return [v["name"] for v in list_voices(refresh)
            if (v.get("locale") or "").startswith("bn-")]


def voice_is_verified(voice: str, refresh: bool = False) -> bool:
    names = {v["name"] for v in list_voices(refresh)}
    return (not names) or voice in names


def _sapi_bengali_voice() -> str | None:
    """Return an installed Bengali SAPI voice name, or None. Checked once."""
    global _sapi_bn_cache
    if _sapi_bn_cache is not False:
        return _sapi_bn_cache
    with _sapi_lock:
        if _sapi_bn_cache is not False:
            return _sapi_bn_cache
        try:
            import subprocess
            ps = ("Add-Type -AssemblyName System.Speech; "
                  "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  "foreach($v in $s.GetInstalledVoices()){"
                  "if($v.VoiceInfo.Culture.Name -like 'bn-*')"
                  "{Write-Output $v.VoiceInfo.Name}}")
            out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                 capture_output=True, text=True, timeout=30).stdout
            names = [ln.strip() for ln in out.splitlines() if ln.strip()]
            _sapi_bn_cache = names[0] if names else None
        except Exception:
            _sapi_bn_cache = None
    return _sapi_bn_cache


# --------------------------------------------------------------------------
# Text normalization
# --------------------------------------------------------------------------
def _bn_words_below_100(n: int) -> str:
    ones = ["শূন্য", "এক", "দুই", "তিন", "চার", "পাঁচ", "ছয়", "সাত", "আট", "নয়",
            "দশ", "এগারো", "বারো", "তেরো", "চৌদ্দ", "পনেরো", "ষোল", "সতেরো",
            "আঠারো", "উনিশ", "বিশ"]
    if n <= 20:
        return ones[n]
    tens = ["", "", "বিশ", "ত্রিশ", "চল্লিশ", "পঞ্চাশ", "ষাট", "সত্তর",
            "আশি", "নব্বই"]
    t, o = divmod(n, 10)
    return tens[t] + ("" if o == 0 else " " + ones[o])


def _bn_int_words(n: int) -> str:
    if n < 100:
        return _bn_words_below_100(n)
    if n < 1000:
        h, r = divmod(n, 100)
        return _bn_words_below_100(h) + "শত" + ("" if r == 0 else " " + _bn_int_words(r))
    if n < 100000:
        th, r = divmod(n, 1000)
        return _bn_int_words(th) + " হাজার" + ("" if r == 0 else " " + _bn_int_words(r))
    if n < 10000000:
        l, r = divmod(n, 100000)
        return _bn_int_words(l) + " লাখ" + ("" if r == 0 else " " + _bn_int_words(r))
    c, r = divmod(n, 10000000)
    return _bn_int_words(c) + " কোটি" + ("" if r == 0 else " " + _bn_int_words(r))


def _to_bn_digits(s: str) -> str:
    return s.translate(_BN_DIGITS)


def _normalize_dates(text: str) -> str:
    def dmy(m):
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{_to_bn_digits(str(d))} {_MONTHS[mo]} {_to_bn_digits(y)}"
        return m.group(0)

    def ymd(m):
        y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{_to_bn_digits(str(d))} {_MONTHS[mo]} {_to_bn_digits(y)}"
        return m.group(0)

    text = re.sub(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", dmy, text)
    text = re.sub(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", ymd, text)
    return text


def _normalize_times(text: str) -> str:
    def hm(m):
        h, mi = int(m.group(1)), int(m.group(2))
        if h > 23 or mi > 59:
            return m.group(0)
        suffix = ""
        tail = (m.group(3) or "").upper()
        if tail == "AM":
            suffix = " সকাল"
        elif tail == "PM":
            suffix = " রাত" if h >= 7 else " বিকাল"
        h12 = h % 12 or 12
        return f"{_to_bn_digits(str(h12))}টা {_to_bn_digits(str(mi))} মিনিট{suffix}"

    return re.sub(r"\b(\d{1,2}):(\d{2})(?:\s*(AM|PM))?\b", hm, text, flags=re.I)


def _normalize_numbers(text: str) -> str:
    def decimal(m):
        return f"{_to_bn_digits(m.group(1))} দশমিক {_to_bn_digits(m.group(2))}"

    text = re.sub(r"\b(\d+)\.(\d+)\b", decimal, text)
    # long digit runs (phone numbers) -> spaced digits, easier to speak
    def longrun(m):
        digits = m.group(0).replace(",", "")
        if not digits.isdigit():
            return m.group(0)
        keep = digits
        if len(keep) >= 7:
            return " ".join(_to_bn_digits(c) for c in keep)
        return _to_bn_digits(keep)
    text = re.sub(r"\b\d[\d,]{5,}\b", longrun, text)
    text = re.sub(r"(?<=\d)-(?=\d)", " থেকে ", text)
    text = re.sub(r"\d+", lambda m: _to_bn_digits(m.group(0)), text)
    return text


def _apply_glossary(text: str) -> str:
    glossary = CONFIG.glossary or {}
    if not glossary:
        return text
    terms = sorted(glossary, key=len, reverse=True)
    for en in terms:
        bn = glossary[en]
        if en.isupper() and len(en) <= 5:
            text = re.sub(rf"\b{re.escape(en)}\b", bn, text)
        else:
            text = re.sub(rf"\b{re.escape(en)}\b", bn, text, flags=re.I)
    return text


def normalize_text(text: str) -> str:
    """Make text safe and natural for a Bengali neural voice.

    Preserves meaning, keeps unknown technical words intact, and avoids
    reading markdown/code/URLs literally."""
    if not text:
        return ""
    t = str(text)
    # code blocks / inline code / links
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"https?://\S+", " একটি ওয়েব লিংক ", t)
    t = re.sub(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", " একটি ইমেইল ঠিকানা ", t)
    # unicode cleanup (keep ZWNJ/ZWJ, they matter in Bengali)
    t = unicodedata.normalize("NFC", t)
    t = (t.replace("\u00a0", " ").replace("\u2007", " ").replace("\u202f", " ")
         .replace("\u200b", "").replace("\u2060", "").replace("\ufeff", ""))
    t = "".join(ch for ch in t if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    # markdown / bullets / emoji
    t = _EMOJI.sub(" ", t)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"^\s*[-*+•]\s+", "", t, flags=re.M)
    t = re.sub(r"[*_~^|<>]", " ", t)
    t = re.sub(r"[ \t]+", " ", t)
    # dates / times / numbers (before symbol replacements)
    t = _normalize_dates(t)
    t = _normalize_times(t)
    t = _normalize_numbers(t)
    # units and symbols
    repl = {
        "°C": " ডিগ্রি সেলসিয়াস", "°F": " ডিগ্রি ফারেনহাইট",
        "km/h": " কিলোমিটার প্রতি ঘণ্টা", "কিমি/ঘণ্টা": " কিলোমিটার প্রতি ঘণ্টা",
        "GB": " গিগাবাইট", "MB": " মেগাবাইট", "KB": " কিলোবাইট",
        "TB": " টেরাবাইট", "GHz": " গিগাহার্টজ", "MHz": " মেগাহার্টজ",
        "kg": " কিলোগ্রাম", "km": " কিলোমিটার", "cm": " সেন্টিমিটার",
        "%": " শতাংশ", "৳": " টাকা ", "Tk": " টাকা ", "&": " এবং ",
        "@": " অ্যাট ", "#": " হ্যাশ ", "=": " সমান ",
        "+": " প্লাস ", "×": " গুণ ", "÷": " ভাগ ", "→": " থেকে ",
        "।।": "।", "...": "।", "…": "।",
    }
    for k, v in repl.items():
        t = t.replace(k, v)
    # "১০টা ৩০ মিনিট সকাল-এ" → "১০টা ৩০ মিনিট সকালে"
    t = re.sub(r"(সকাল|বিকাল|রাত)[-–—]এ", r"\1", t)
    # English abbreviations
    abbr = {r"\be\.g\.\s*": "যেমন ", r"\bi\.e\.\s*": "অর্থাৎ ",
            r"\betc\.?": " ইত্যাদি", r"\bvs\.?\b": " বনাম ",
            r"\bMr\.\s*": "মিস্টার ", r"\bMrs\.\s*": "মিসেস ",
            r"\bDr\.\s*": "ডাক্তার "}
    for pat, rep in abbr.items():
        t = re.sub(pat, rep, t, flags=re.I)
    # curated technical glossary
    t = _apply_glossary(t)
    # punctuation breathing room
    t = re.sub(r"\s+([।,!?;:])", r"\1", t)
    t = re.sub(r"([।!?])(?=[^\s।!?])", r"\1 ", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t).strip()
    if t and t[-1] not in "।!?.":
        t += "।"
    return t


def split_chunks(text: str, max_chars: int | None = None) -> list[str]:
    """Split normalized text on sentence boundaries for lower first-audio latency."""
    limit = max_chars or CONFIG.max_chunk_chars
    if len(text) <= limit:
        return [text] if text else []
    parts = re.split(r"(?<=[।!?])\s+", text)
    chunks, cur = [], ""
    for p in parts:
        if not p:
            continue
        if cur and len(cur) + 1 + len(p) > limit:
            chunks.append(cur)
            cur = p
        else:
            cur = (cur + " " + p).strip()
    if cur:
        chunks.append(cur)
    return chunks


# --------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------
class TTSProvider:
    name = "base"

    def synthesize(self, text: str, voice: str, out_path: str) -> None:
        raise NotImplementedError


class EdgeProvider(TTSProvider):
    name = "edge"

    def synthesize(self, text: str, voice: str, out_path: str) -> None:
        import edge_tts
        asyncio.run(edge_tts.Communicate(
            text, voice, rate=CONFIG.rate, pitch=CONFIG.pitch,
            volume=CONFIG.volume, connect_timeout=10, receive_timeout=60,
        ).save(out_path))
        self.validate(out_path)

    @staticmethod
    def validate(path: str) -> None:
        if not os.path.exists(path) or os.path.getsize(path) < 800:
            raise RuntimeError("edge-tts returned empty/short audio")
        with open(path, "rb") as f:
            head = f.read(4)
        if not (head.startswith(b"ID3") or head[:1] == b"\xff" or head[:4] == b"RIFF"):
            raise RuntimeError("edge-tts returned invalid audio")


class GttsProvider(TTSProvider):
    name = "gtts"

    def synthesize(self, text: str, voice: str, out_path: str) -> None:
        from gtts import gTTS
        gTTS(text, lang="bn", slow=False).save(out_path)
        if not os.path.exists(out_path) or os.path.getsize(out_path) < 800:
            raise RuntimeError("gTTS returned empty/short audio")


class SapiProvider(TTSProvider):
    """Windows offline voice — allowed ONLY for a real Bengali SAPI voice."""
    name = "sapi"

    def synthesize(self, text: str, voice: str, out_path: str) -> None:
        bn_voice = _sapi_bengali_voice()
        if not bn_voice:
            raise RuntimeError("no Bengali SAPI voice installed (English voice would garble Bengali)")
        import subprocess
        txt_path = out_path + ".txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)
        ps = ("Add-Type -AssemblyName System.Speech; "
              "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              f"$s.SelectVoice('{bn_voice.replace(chr(39), chr(39)*2)}'); "
              f"$s.SetOutputToWaveFile('{out_path.replace(chr(39), chr(39)*2)}'); "
              f"$s.Speak([IO.File]::ReadAllText('{txt_path.replace(chr(39), chr(39)*2)}',"
              "[Text.Encoding]::UTF8)); $s.Dispose()")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=90)
        try:
            os.remove(txt_path)
        except Exception:
            pass
        if not os.path.exists(out_path) or os.path.getsize(out_path) < 800:
            raise RuntimeError("SAPI produced no audio")


_PROVIDERS = {"edge": EdgeProvider(), "gtts": GttsProvider(), "sapi": SapiProvider()}


# --------------------------------------------------------------------------
# Playback
# --------------------------------------------------------------------------
def _mci(command: str) -> int:
    if sys.platform != "win32":
        return 1
    import ctypes
    return int(ctypes.windll.winmm.mciSendStringW(
        ctypes.create_unicode_buffer(command), None, 0, 0))


def _play_file(path: str) -> None:
    global _current_alias
    alias = f"ava_tts_{os.getpid()}_{uuid.uuid4().hex[:8]}"
    ext = os.path.splitext(path)[1].lower()
    dev_type = "waveaudio" if ext == ".wav" else "mpegvideo"
    with _alias_lock:
        _current_alias = alias
    try:
        if _mci(f'open "{path}" type {dev_type} alias {alias}') != 0:
            raise RuntimeError("MCI open failed")
        vol = max(0, min(100, int(CONFIG.playback_volume))) * 10
        _mci(f"setaudio {alias} volume to {vol}")
        _mci(f"play {alias} wait")
    finally:
        _mci(f"close {alias}")
        with _alias_lock:
            if _current_alias == alias:
                _current_alias = None


def stop() -> None:
    """Immediately interrupt current playback."""
    _speak_stop.set()
    with _alias_lock:
        alias = _current_alias
    if alias:
        _mci(f"stop {alias}")


def is_speaking() -> bool:
    with _alias_lock:
        return _current_alias is not None


# --------------------------------------------------------------------------
# Synthesis + speak
# --------------------------------------------------------------------------
def synthesize(text: str, out_path: str | None = None, voice: str | None = None,
               providers: list[str] | None = None) -> tuple[str, dict]:
    """Synthesize normalized text. Returns (audio_path, metrics). Raises on total failure."""
    t0 = time.time()
    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("empty text after normalization")
    voice = voice or CONFIG.voice
    order = providers or CONFIG.provider_order
    voices = [voice] + [v for v in CONFIG.fallback_voices if v != voice]

    if not out_path:
        out_path = os.path.join(tempfile.gettempdir(),
                                f"ava_tts_{uuid.uuid4().hex[:10]}.mp3")
    errors = []
    used_provider = used_voice = None
    for pname in order:
        prov = _PROVIDERS.get(pname)
        if not prov:
            continue
        if pname == "sapi" and not _sapi_bengali_voice():
            errors.append("sapi: no Bengali voice installed")
            continue
        if pname == "edge":
            for v in voices:
                try:
                    prov.synthesize(normalized, v, out_path)
                    used_provider, used_voice = pname, v
                    break
                except Exception as e:
                    errors.append(f"edge/{v}: {type(e).__name__}: {e}")
            if used_provider:
                break
        else:
            try:
                v = CONFIG.voice if pname == "gtts" else (_sapi_bengali_voice() or CONFIG.voice)
                prov.synthesize(normalized, v, out_path)
                used_provider, used_voice = pname, v
                break
            except Exception as e:
                errors.append(f"{pname}: {type(e).__name__}: {e}")
    if not used_provider:
        raise RuntimeError("all TTS providers failed: " + " | ".join(errors[-6:]))

    metrics = {
        "provider": used_provider,
        "voice": used_voice,
        "original_chars": len(str(text)),
        "normalized_chars": len(normalized),
        "audio_bytes": os.path.getsize(out_path),
        "synthesis_ms": int((time.time() - t0) * 1000),
        "errors": errors[-6:],
        "path": out_path,
    }
    return out_path, metrics


def speak(text: str, interrupt: bool = True) -> dict:
    """Speak text with verified Bengali voice. Returns real metrics."""
    global _last_metrics
    metrics = {"ok": False, "provider": None, "voice": None, "chunks": 0,
               "first_audio_ms": None, "total_ms": None, "errors": []}
    normalized = normalize_text(text)
    if not normalized:
        return metrics
    if interrupt:
        stop()
    _speak_stop.clear()
    t_start = time.time()
    with _play_lock:
        chunks = split_chunks(normalized)
        metrics["chunks"] = len(chunks)
        for idx, chunk in enumerate(chunks):
            if _speak_stop.is_set():
                break
            path = None
            try:
                path, m = synthesize(chunk)
                metrics["provider"] = m["provider"]
                metrics["voice"] = m["voice"]
                metrics["errors"].extend(m["errors"])
                if metrics["first_audio_ms"] is None:
                    metrics["first_audio_ms"] = int((time.time() - t_start) * 1000)
                _play_file(path)
                if idx < len(chunks) - 1 and CONFIG.trailing_pause_ms:
                    time.sleep(CONFIG.trailing_pause_ms / 1000.0)
            except Exception as e:
                metrics["errors"].append(f"{type(e).__name__}: {e}")
                print(f"⚠️  TTS: {type(e).__name__}: {e}")
            finally:
                if path:
                    try:
                        os.remove(path)
                    except Exception:
                        pass
    metrics["total_ms"] = int((time.time() - t_start) * 1000)
    metrics["ok"] = metrics["provider"] is not None
    if not metrics["ok"]:
        print("⚠️  Bengali voice তৈরি হয়নি — কোনো উপযুক্ত Bengali voice পাওয়া যায়নি "
              "(ইন্টারনেট/Edge TTS দেখুন)।")
    _last_metrics = metrics
    return metrics


def last_metrics() -> dict:
    return dict(_last_metrics)


def healthcheck(play: bool = False) -> dict:
    """Real healthcheck: verify voices, synthesize a sample, optionally play it."""
    report = {"edge_tts": False, "bengali_voices": [], "sapi_bengali": None,
              "synthesis": None, "playback": None}
    voices = bengali_voices(refresh=True)
    report["bengali_voices"] = voices
    report["edge_tts"] = bool(voices)
    report["sapi_bengali"] = _sapi_bengali_voice()
    try:
        path, m = synthesize("আসসালামু আলাইকুম। আমি AVA। এটি একটি কণ্ঠ পরীক্ষা।")
        report["synthesis"] = m
        if play:
            _play_file(path)
            report["playback"] = "played"
        os.remove(path)
    except Exception as e:
        report["synthesis"] = f"FAIL {type(e).__name__}: {e}"
    return report


if __name__ == "__main__":
    import pprint
    pprint.pprint(healthcheck(play="--play" in sys.argv))
