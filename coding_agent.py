# -*- coding: utf-8 -*-
"""AVA Coding Agent — বাস্তব কোড-সহায়ক (Phase 3, Module 08)।
- প্রজেক্ট inspect (stack শনাক্ত) • কোড explain (Gemini, চাংক করে)
- ফাইল তৈরি/এডিট — আগে **ব্যাকআপ/git checkpoint**, তারপর **অনুমতি**, তারপর লেখা+যাচাই
- টেমপ্লেট: Laravel controller/model/migration, React component, HTML page
- নিরাপত্তা: লেখার আগে .ava_backup/ এ কপি; overwrite সবসময় অনুমতি-সাপেক্ষ"""
import datetime
import os
import re
import shutil
from pathlib import Path

CODE_EXTS = {".php", ".js", ".ts", ".jsx", ".tsx", ".py", ".html", ".css",
             ".json", ".env.example", ".sql", ".vue", ".blade.php"}


def _llm(system: str, user: str, max_tokens: int = 700) -> str | None:
    try:
        import terminal_engine
        return terminal_engine._llm(system, user, max_tokens)
    except Exception:
        return None


def detect_stack(path: str) -> dict:
    """প্রজেক্টের ধরন ও পরিবেশ শনাক্ত — আসল ফাইল দেখে।"""
    p = Path(path)
    if not p.is_dir():
        return {"ok": False, "msg": "প্রজেক্ট ফোল্ডার পাওয়া যায়নি।"}
    found = {f.name for f in p.iterdir() if f.is_file()}
    dirs = {f.name for f in p.iterdir() if f.is_dir()}
    stack = []
    if "composer.json" in found and "artisan" in found:
        stack.append("Laravel (PHP)")
    elif "composer.json" in found:
        stack.append("PHP (Composer)")
    if "package.json" in found:
        try:
            pkg = json_pkg = (p / "package.json").read_text(encoding="utf-8", errors="replace")
            if '"next"' in pkg:
                stack.append("Next.js")
            if '"react"' in pkg:
                stack.append("React")
            if '"react-native"' in pkg:
                stack.append("React Native")
            if '"@nestjs' in pkg:
                stack.append("NestJS")
            if not stack or stack == ["React"]:
                stack.append("Node.js/JavaScript")
        except Exception:
            stack.append("Node.js")
    if "requirements.txt" in found or "manage.py" in found:
        stack.append("Python/Django")
    if "resources/views" in [str(d) for d in dirs] or "app" in dirs and "routes" in dirs:
        stack.append("MVC structure")
    if ".git" in dirs:
        stack.append("Git repo ✔")
    files_sample = sorted(list(found))[:15]
    return {"ok": True, "stack": stack or ["অজানা"], "files": files_sample,
            "total_files": sum(len(fs) for _r, _d, fs in os.walk(p))}


def inspect_report(path: str) -> str:
    r = detect_stack(path)
    if not r["ok"]:
        return r["msg"]
    lines = [f"📦 প্রজেক্ট: {path}",
             f"🧩 Stack: {', '.join(r['stack'])}",
             f"📄 মোট ফাইল: {r['total_files']}",
             "🗂️ মূল ফাইল: " + ", ".join(r["files"][:12])]
    # composer/package dependency সংক্ষেপ
    p = Path(path)
    for dep in ("composer.json", "package.json"):
        f = p / dep
        if f.exists():
            try:
                import json as _json
                data = _json.loads(f.read_text(encoding="utf-8", errors="replace"))
                req = data.get("require", data.get("dependencies", {}))
                lines.append(f"📜 {dep} dependencies: " +
                             ", ".join(list(req.keys())[:10]))
            except Exception:
                pass
    return "\n".join(lines)


def explain_file(path: str, question: str = "") -> str:
    """কোড ফাইল পড়ে Gemini দিয়ে ব্যাখ্যা (বড় ফাইল হলে চাংক)।"""
    p = Path(path)
    if not p.is_file():
        found = _find_in_tree(Path.cwd(), path)
        if not found:
            return f"'{path}' ফাইল পাইনি।"
        p = found
    text = p.read_text(encoding="utf-8", errors="replace")
    if len(text) > 12000:
        text = text[:12000] + "\n...(কেটে দেখানো)"
    q = question or "এই কোডটা কী করে? মূল ফাংশন, ফ্লো ও সমস্যা থাকলে বলো — বাংলায়।"
    ans = _llm("তুমি সিনিয়র ডেভেলপার। কোড ব্যাখ্যা করো — বাংলায়, সহজভাবে, "
               "সঠিক তথ্যে। কোডে যা নেই তা বানাবে না।",
               f"ফাইল: {p.name}\n\n```\n{text}\n```\n\nপ্রশ্ন: {q}", max_tokens=600)
    return ans or "ব্যাখ্যা তৈরি ব্যর্থ (LLM)।"


def _find_in_tree(base: Path, name: str) -> Path | None:
    tl = name.lower().strip()
    for root, _dirs, files in os.walk(base):
        if ".git" in root or "node_modules" in root or "vendor" in root:
            continue
        for fn in files:
            if tl in fn.lower():
                return Path(root) / fn
    return None


def _backup_file(p: Path) -> str | None:
    """লেখার আগে ব্যাকআপ: git থাকলে checkpoint নয় — ফাইল কপি .ava_backup/।"""
    try:
        bdir = p.parent / ".ava_backup"
        bdir.mkdir(exist_ok=True)
        dest = bdir / f"{p.name}.{datetime.datetime.now():%Y%m%d_%H%M%S}.bak"
        shutil.copy2(p, dest)
        return str(dest)
    except Exception:
        return None


def write_code_file(path: str, content: str, confirm_cb=None) -> str:
    """কোড ফাইল তৈরি/এডিট — overwrite হলে আগে ব্যাকআপ + অনুমতি।"""
    p = Path(path)
    if p.exists():
        backup = _backup_file(p)
        if confirm_cb and not confirm_cb(
                f"'{p.name}' ফাইলটি আগেই আছে — overwrite করলে পুরনোটা "
                f"ব্যাকআপ হবে ({backup})। অনুমতি দিন? হ্যাঁ/না।"):
            return "❌ লেখা হয়নি (অনুমতি নেই)।"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    except OSError as e:
        return f"❌ লেখা যায়নি: {e}"
    ok = p.exists() and p.stat().st_size > 0
    note = f"✅ লেখা ও যাচাইকৃত: {p} ({p.stat().st_size} bytes)" if ok else "❌ যাচাই ব্যর্থ"
    if p.exists() and backup:
        note += f"\n💾 পুরনো ব্যাকআপ: {backup}"
    return note


def generate(kind: str, name: str, project: str = "") -> str:
    """টেমপ্লেট কোড জেনারেট (LLM দিয়ে, প্রজেক্ট-প্রসঙ্গ সহ)।"""
    kind = kind.lower()
    stack = detect_stack(project).get("stack", []) if project and os.path.isdir(project) else []
    ctx = f"প্রজেক্ট stack: {', '.join(stack)}" if stack else ""
    prompts = {
        "controller": f"Laravel controller '{name}' — CRUD methods, validation, "
                      f"JSON response. {ctx}. শুধু PHP কোড দাও, ব্যাখ্যা নয়।",
        "model": f"Laravel Eloquent model '{name}' — fillable, relations, migration "
                 f"suggestion কমেন্টে। {ctx}. শুধু কোড।",
        "migration": f"Laravel migration for '{name}' table — sensible columns, "
                     f"indexes. {ctx}. শুধু কোড।",
        "component": f"React functional component '{name}' — props, useState প্রয়োজনে, "
                     f"clean JSX. {ctx}. শুধু কোড।",
        "api": f"REST API route + controller for '{name}' — GET/POST/PUT/DELETE, "
               f"validation. {ctx}. শুধু কোড।",
        "page": f"HTML page '{name}' — বাংলা Unicode, clean CSS, responsive. শুধু কোড।",
    }
    system = "তুমি সিনিয়র ডেভেলপার। শুধুমাত্র চূড়ান্ত কোড দাও — কোনো আগমন-ব্যাখ্যা নয়।"
    code = _llm(system, prompts.get(kind, f"'{name}' এর জন্য {kind} কোড দাও। {ctx}"),
                max_tokens=900)
    if not code:
        return "❌ কোড জেনারেট ব্যর্থ (LLM)।"
    code = re.sub(r"^```[\w]*\n?|\n```$", "", code.strip())
    ext = {"controller": ".php", "model": ".php", "migration": ".php",
           "component": ".jsx", "api": ".php", "page": ".html"}.get(kind, ".txt")
    fname = "".join(w.capitalize() for w in name.split()) + ext if kind != "page" \
        else name.lower().replace(" ", "_") + ".html"
    dest = Path(project) / fname if project and os.path.isdir(project) else \
        Path.cwd() / fname
    return write_code_file(str(dest), code, confirm_cb=None)


def fix_error(log_text: str, project: str = "") -> str:
    """error লগ দেখে কারণ+ফিক্স প্রস্তাব; ফিক্স apply হলে ব্যাকআপ+অনুমতি সহ।"""
    import terminal_engine
    fx = terminal_engine._llm_fix("user request: fix", 1,
                                  mask_secrets(log_text)[:800])
    if not fx:
        ans = _llm("তুমি ডিবাগিং বিশেষজ্ঞ। error দেখে কারণ ও নিরাপদ সমাধান বাংলায় বলো। "
                   "নিশ্চিত না হলে স্পষ্ট বলো।",
                   f"ERROR LOG:\n{mask_secrets(log_text)[:800]}\nপ্রজেক্ট: {project}",
                   max_tokens=400)
        return ans or "বিশ্লেষণ ব্যর্থ (LLM)।"
    analysis = fx.get("analysis", "")
    fix_cmd = fx.get("fix_cmd")
    out = f"🔍 কারণ: {analysis}"
    if fix_cmd:
        out += f"\n🛠️ প্রস্তাবিত কমান্ড: {fix_cmd}\n(চালাতে বলুন: 'টার্মিনালে চালাও {fix_cmd}')"
    return out


def mask_secrets(text: str) -> str:
    try:
        from terminal_engine import mask_secrets
        return mask_secrets(text)
    except Exception:
        return text
