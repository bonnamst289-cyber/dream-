# -*- coding: utf-8 -*-
"""AVA Personal Knowledge Base — অনুমোদিত ডকুমেন্ট ইনডেক্স, সার্চ, উদ্ধৃতি সহ উত্তর।
সমর্থিত: .txt .md .py .js .php .html .css .json .csv .log (PDF-এর জন্য pypdf ইনস্টল থাকলে)
সৎ নীতি: পড়া না গেলে/করাপ্ট হলে স্পষ্ট বলে — বানায় না।"""
import datetime
import json
import os
import re

from pathlib import Path

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ava_knowledge.json")
TEXT_EXT = {".txt", ".md", ".py", ".js", ".php", ".html", ".css", ".json",
            ".csv", ".log", ".sql", ".yml", ".yaml", ".ini", ".env.example"}
_state = {"docs": []}   # [{"path","name","size","indexed_at","chunks":[{line_start,text}]}]
CHUNK_LINES = 40


def _load():
    try:
        with open(FILE, encoding="utf-8") as f:
            _state["docs"] = json.load(f)
    except Exception:
        _state["docs"] = []


def _save():
    try:
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(_state["docs"], f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _read_file(path: str) -> str | None:
    ext = Path(path).suffix.lower()
    try:
        if ext == ".pdf":
            try:
                from pypdf import PdfReader
                pages = PdfReader(path).pages
                return "\n".join((p.extract_text() or "") for p in pages)
            except ImportError:
                return None  # pypdf নেই — সৎভাবে বলা হবে
        if ext in TEXT_EXT:
            return open(path, encoding="utf-8", errors="replace").read()
        if ext in (".docx",):
            return None  # docx এখনো সমর্থিত নয় — সৎ
    except Exception:
        return None
    return None


def index_path(target: str) -> dict:
    """ফোল্ডার বা একক ফাইল ইনডেক্স করে।"""
    _load()
    target = os.path.abspath(target)
    added, skipped, failed = 0, 0, []
    paths = []
    if os.path.isdir(target):
        for root, _dirs, files in os.walk(target):
            for fn in files:
                if Path(fn).suffix.lower() in TEXT_EXT or fn.lower().endswith(".pdf"):
                    paths.append(os.path.join(root, fn))
    elif os.path.isfile(target):
        paths = [target]
    else:
        return {"ok": False, "msg": "পথটি পাওয়া যায়নি।"}
    for p in paths[:60]:
        rel = p
        if any(d["path"] == p for d in _state["docs"]):
            skipped += 1
            continue
        text = _read_file(p)
        if text is None:
            failed.append(os.path.basename(p) +
                          (" (pypdf লাগবে)" if p.endswith(".pdf") else " (অসমর্থিত)"))
            continue
        lines = text.splitlines()
        chunks = [{"start": i + 1, "text": "\n".join(lines[i:i + CHUNK_LINES])[:3000]}
                  for i in range(0, len(lines), CHUNK_LINES) if lines[i:i + CHUNK_LINES]]
        _state["docs"].append({"path": p, "name": os.path.basename(p),
                               "size": os.path.getsize(p),
                               "indexed_at": datetime.datetime.now().isoformat(timespec="seconds"),
                               "chunks": chunks[:50]})
        added += 1
    _save()
    msg = f"✅ ইনডেক্স হলো: {added}টি ফাইল" + (f", {skipped}টি আগে থেকেই ছিল" if skipped else "")
    if failed:
        msg += f"\n⚠️ পড়া যায়নি: {', '.join(failed[:3])}"
    return {"ok": True, "msg": msg, "total_docs": len(_state["docs"])}


def search(query: str, top: int = 3) -> list[dict]:
    """কিওয়ার্ড-স্কোর সার্চ; ফেরত: [{name, line, snippet, score}]"""
    _load()
    words = [w for w in re.sub(r"[^\w\s\u0980-\u09FF]", " ", query.lower()).split()
             if len(w) > 2][:8]
    results = []
    for d in _state["docs"]:
        for ch in d["chunks"]:
            low = ch["text"].lower()
            score = sum(low.count(w) for w in words)
            if score <= 0:
                continue
            best_line = ch["start"]
            lines = ch["text"].splitlines()
            best_txt, best_s = "", 0
            for ln in lines:
                s = sum(ln.lower().count(w) for w in words)
                if s > best_s:
                    best_s, best_txt = s, ln
            results.append({"name": d["name"], "line": best_line,
                            "snippet": (best_txt or lines[0])[:160], "score": score})
    results.sort(key=lambda r: -r["score"])
    return results[:top]


def stats() -> str:
    _load()
    if not _state["docs"]:
        return "নলেজ বেইজ খালি। বলুন: 'নলেজ ইনডেক্স করো <ফোল্ডারের পথ>'"
    total_chunks = sum(len(d["chunks"]) for d in _state["docs"])
    return (f"📚 নলেজ বেইজ: {len(_state['docs'])}টি ডকুমেন্ট, {total_chunks}টি অংশ\n"
            + "\n".join(f"• {d['name']} ({d['size']//1024}KB)" for d in _state["docs"][:10]))


# ----------------- ভয়েস রাউটার -----------------
def handle(user_text: str) -> tuple[bool, str] | None:
    t = user_text.lower()
    if "নলেজ" not in t and "knowledge" not in t and "ডকুমেন্ট" not in t:
        return None
    if "ইনডেক্স" in t or "index" in t or "যোগ করো" in t:
        m = re.search(r"(?:ইনডেক্স করো|index koro|index)\s*(.+)", user_text, re.I)
        target = m.group(1).strip() if m else ""
        if not target:
            return True, "কোন ফোল্ডার/ফাইল ইনডেক্স করব? পথ বলুন (যেমন: C:\\Users\\HP\\Documents)"
        r = index_path(target)
        return True, r["msg"] + (f"\nমোট: {r['total_docs']} ডকুমেন্ট" if r.get("ok") else "")
    if "স্ট্যাটাস" in t or "stats" in t or "কয়টা" in t or "কত" in t:
        return True, stats()
    q = re.sub(r".*?(?:থেকে|from|theke)\s*", "", user_text, count=1, flags=re.I).strip() \
        if any(w in t for w in ("থেকে", "theke", "from")) else user_text
    results = search(q or user_text)
    if not results:
        return True, f"'{q[:50]}' নিয়ে ডকুমেন্টে কিছু পেলাম না। (ইনডেক্স করা আছে কি দেখুন)"
    out = [f"📚 {len(results)}টি অনুচ্ছেদ পেলাম:"]
    for r in results:
        out.append(f"• {r['name']} (লাইন ~{r['line']}): …{r['snippet']}…")
    return True, "\n".join(out)
