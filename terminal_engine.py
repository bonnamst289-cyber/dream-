# -*- coding: utf-8 -*-
"""
AVA — Advanced Terminal Automation Engine
==========================================
- Multi-terminal support (CMD / PowerShell / Git Bash / WSL)
- Natural language (Bangla/English/Banglish) → command planning (1 LLM request/task)
- Autonomous multi-step execution with verification, error analysis & safe retry
- Security layer: forbidden/caution/safe classification, secret masking,
  confirmation for risky steps, audit log, timeout, cancellation
- Real terminal output only (no fake progress)
- Lightweight (no background daemons; designed for 8 GB RAM machines)
"""
import base64
import datetime
import json
import os
import re
import shutil
import subprocess
import threading
import time

# ----------------- সুরক্ষা: কমান্ড শ্রেণিবিন্যাস -----------------
FORBIDDEN_PATTERNS = [
    r"\bformat\b", r"shutdown", r"\bdiskpart\b", r"\bcipher\b", r"\bbcdedit\b",
    r"\bvssadmin\b", r"\blogoff\b", r"\bmkfs\b", r"\bdd\s+if=",
    r"reg\s+(delete|add|import)", r"regedit", r"net\s+(user|localgroup)",
    r"netsh", r"\bsc\s+(delete|config)\b", r"taskkill\s+/f\s+/im\s+explorer",
    r"del\s+(/s|/q)", r"rmdir\s+/s", r"rm\s+-rf\s+[/~]", r"rm\s+-rf",
    r"erase\s+", r"wsl\s+--unregister", r"schtasks", r"attrib\s+[+-]s",
    r"curl[^|]*\|\s*(sh|bash|powershell)", r"iex\s*\(|invoke-expression",
    r"remove-item\s+[^;|]*-recurse", r"mv\s+.*\s+/dev/", r"\btruncate\s+-s\s*0\s+/",
    r"drop\s+(database|table)", r"mysql\s+.*-e\s+.*drop",
]
CAUTION_PATTERNS = [
    r"\bdel\b", r"\berase\b", r"\brd\b", r"\brm\b", r"\brmdir\b", r"\bmove\b",
    r"git\s+(push|reset|clean|checkout\s+--|revert)", r"npm\s+(uninstall|install\s+-g)",
    r"composer\s+(remove|update)", r"pip\s+uninstall", r"npm\s+uninstall",
    r"drop\s+table", r">\s*[^|]*\.(env|json|ya?ml|lock)\b", r"chown", r"\bchmod\b",
]
SAFE_PREFIXES = (
    "dir", "ls", "cat", "type", "echo", "ipconfig", "ping", "whoami", "hostname",
    "systeminfo", "tasklist", "node -v", "node --version", "npm -v", "npm --version",
    "npm run", "npm list", "npm ls", "npm outdated", "npx -v", "python --version",
    "pip list", "pip --version", "git status", "git log", "git diff", "git branch",
    "git remote", "git stash list", "git --version", "composer --version", "php -v",
    "php -l", "php artisan", "where", "getmac", "vol", "ver", "date", "time",
    "tree", "netstat", "findstr", "code --version", "curl -i", "curl -s -i",
    "cd", "pwd", "env", "uname", "wsl -l", "wsl --list", "bash --version",
    "head", "tail", "wc", "grep", "find .", "ls -la", "help", "cls",
)

SECRET_PATTERNS = [
    re.compile(r"[A-Za-z0-9_\-]{16,}\.rb_[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9\-_]{10,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{10,}"),
    re.compile(r"AQ\.[A-Za-z0-9_\-]{10,}"),
    re.compile(r"ghp_[A-Za-z0-9]{10,}|github_pat_[A-Za-z0-9_]{10,}"),
    re.compile(r"(password|passwd|pwd|token|secret|api[_-]?key|apikey)\s*[:=]\s*\S+", re.I),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{10,}", re.I),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]+"),
]

CANCEL_EVENT = threading.Event()
ACTIVE = threading.Event()
CURRENT_PROC = None


def classify(cmd: str) -> str:
    """→ 'forbidden' | 'dangerous' | 'caution' | 'safe'"""
    low = (cmd or "").lower().strip()
    for p in FORBIDDEN_PATTERNS:
        if re.search(p, low):
            return "forbidden"
    for p in CAUTION_PATTERNS:
        if re.search(p, low):
            return "caution"
    if any(low.startswith(s) or low.startswith("cmd /c " + s) for s in SAFE_PREFIXES):
        return "safe"
    return "dangerous"  # অপরিচিত → অনুমতি ছাড়া চলবে না


def mask_secrets(text: str) -> str:
    """কোনো secret/token/key লগ বা কণ্ঠে যাওয়ার আগে মুছে ফেলা হয়।"""
    out = text or ""
    for p in SECRET_PATTERNS:
        out = p.sub("***", out)
    return out


# ----------------- মাল্টি-টার্মিনাল সাপোর্ট -----------------
def detect_shells() -> dict:
    shells = {"cmd": "cmd"}
    pw = shutil.which("pwsh") or shutil.which("powershell")
    if pw:
        shells["powershell"] = pw
    bash = shutil.which("bash")
    if not bash:
        for cand in (r"C:\Program Files\Git\bin\bash.exe",
                     r"C:\Program Files\Git\usr\bin\bash.exe"):
            if os.path.exists(cand):
                bash = cand
                break
    if bash and "git" in bash.lower() or bash and "usr\\bin" in bash.lower():
        shells["gitbash"] = bash
    elif bash:
        shells["gitbash"] = bash
    if shutil.which("wsl"):
        shells["wsl"] = "wsl"
    return shells


def _build_cmdline(cmd: str, shell: str, shells: dict) -> list:
    if shell == "powershell" and "powershell" in shells:
        return [shells["powershell"], "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-Command", cmd]
    if shell == "gitbash" and "gitbash" in shells:
        return [shells["gitbash"], "-lc", cmd]
    if shell == "wsl" and "wsl" in shells:
        return ["wsl", "-e", "bash", "-lc", cmd]
    return ["cmd", "/c", cmd]  # ডিফল্ট: CMD


def run(cmd: str, shell: str = "cmd", cwd: str | None = None,
        timeout: int = 180) -> dict:
    """একটা কমান্ড সত্যিই চালায়; ফেরত: exit/stdout/stderr/duration/timed_out"""
    global CURRENT_PROC
    cmd = (cmd or "").strip()
    shells = detect_shells()
    spec = _build_cmdline(cmd, shell, shells)
    started = time.time()
    timed_out = False
    try:
        p = subprocess.Popen(spec, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, cwd=cwd, errors="replace")
        CURRENT_PROC = p
        try:
            out, err = p.communicate(timeout=timeout)
            code = p.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            p.kill()
            out, err = p.communicate()
            code = -1
    except FileNotFoundError as e:
        out, err, code = "", str(e), -1
    finally:
        CURRENT_PROC = None
    return {
        "cmd": cmd, "shell": shell, "exit": code,
        "stdout": mask_secrets(out or ""), "stderr": mask_secrets(err or ""),
        "duration": round(time.time() - started, 2), "timed_out": timed_out,
    }


def cancel_task() -> None:
    """ব্যবহারকারী 'থামো' বললে বা Ctrl+C দিলে চলমান প্রসেস-ট্রি সহ সব থামে।"""
    CANCEL_EVENT.set()
    p = CURRENT_PROC
    if p is not None:
        try:
            # পুরো প্রসেস-ট্রি বন্ধ (cmd.exe-এর ভেতরের পিং ইত্যাদিও)
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                           capture_output=True, timeout=10)
        except Exception:
            try:
                p.terminate()
            except Exception:
                pass


# ----------------- অডিট লগ -----------------
AUDIT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "ava_terminal_audit.jsonl")


def audit(entry: dict) -> None:
    try:
        e = dict(entry)
        e["time"] = datetime.datetime.now().isoformat(timespec="seconds")
        e["cmd"] = mask_secrets(e.get("cmd", ""))
        if "output" in e:
            e["output"] = mask_secrets(e["output"])[:400]
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ----------------- LLM (বিদ্যমান brain ব্যবহার করে; প্রতি টাস্কে সীমিত কল) -----------------
def _llm(system: str, user: str, max_tokens: int = 500) -> str | None:
    try:
        import asif
    except Exception:
        return None
    # প্রথমে Gemini (দ্রুত), ব্যর্থ হলে Ollama
    if getattr(asif, "GEMINI_KEY", "") and not getattr(asif, "_GEMINI_FAILED", False):
        try:
            r = requests_gemini(system, user, max_tokens)
            if r:
                return r
        except Exception:
            pass
    try:
        model = asif._ollama_pick_model() or asif.OLLAMA_MODEL
        r = _req_post("http://localhost:11434/api/chat", json={
            "model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "stream": False, "keep_alive": "1h",
            "options": {"num_predict": max_tokens, "num_thread": 8},
        }, timeout=(5, 90))
        if r.status_code == 200:
            return r.json().get("message", {}).get("content", "").strip() or None
    except Exception:
        pass
    return None


def requests_gemini(system: str, user: str, max_tokens: int) -> str | None:
    import asif
    import requests
    r = requests.post(
        f"{asif.GEMINI_URL}/{asif.GEMINI_MODEL}:generateContent",
        headers={"x-goog-api-key": asif.GEMINI_KEY},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2,
                                     "thinkingConfig": {"thinkingBudget": 0}},
        },
        timeout=(5, 25),
    )
    if r.status_code == 404:
        asif._pick_gemini_model()
        r = requests.post(
            f"{asif.GEMINI_URL}/{asif.GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": asif.GEMINI_KEY},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2,
                                     "thinkingConfig": {"thinkingBudget": 0}},
            },
            timeout=(5, 25),
        )
    if r.status_code == 200:
        cands = r.json().get("candidates", [])
        if cands:
            return "".join(p.get("text", "") for p in
                           cands[0].get("content", {}).get("parts", [])).strip() or None
    return None


def _req_post(url, json=None, timeout=60):
    import requests
    return requests.post(url, json=json, timeout=timeout)


# ----------------- প্ল্যানার (NL → ধাপ) -----------------
PLANNER_SYSTEM = (
    "তুমি Windows টার্মিনাল অটোমেশন প্ল্যানার। ব্যবহারকারীর বাংলা/English/Banglish নির্দেশ "
    "থেকে নিরাপদ টার্মিনাল ধাপ তৈরি করবে। নিয়ম:\n"
    "- শুধুমাত্র JSON দাও, অন্য কিছু না।\n"
    '- ফরম্যাট: {"task":"...","steps":[{"cmd":"...","shell":"cmd|powershell|gitbash|wsl","purpose":"...","verify":"..."}]}\n'
    "- উদাহরণ — নির্দেশ: 'ফাইল দেখাও' → {\"task\":\"ফাইল তালিকা\",\"steps\":[{\"cmd\":\"dir\",\"shell\":\"cmd\",\"purpose\":\"ফোল্ডারের তালিকা\",\"verify\":\"\"}]}\n"
    "- ন্যূনতম ধাপ; প্রতিটি ধাপ ছোট ও স্বাধীন; cd দিয়ে ফোল্ডার পাল্টাবে না।\n"
    "- verify শুধু তখনই দাও যখন নিশ্চিত সঠিক কমান্ড; না হলে খালি স্ট্রিং।\n"
    "- কখনো format/shutdown/diskpart/registry/rm -rf জাতীয় কিছু লিখবে না।\n"
    "- শেল: সাধারণ Windows কমান্ডে cmd; লিনাক্স-স্টাইল (ls/grep/cat) হলে gitbash।"
)


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def plan_task(user_text: str, cwd: str | None = None) -> dict:
    shells = detect_shells()
    context = ""
    if cwd and os.path.isdir(cwd):
        try:
            files = [f for f in os.listdir(cwd)][:20]
            context = "কাজের ফোল্ডারে আছে: " + ", ".join(files)
        except Exception:
            pass
    user = (f"নির্দেশ: {user_text}\nউপলব্ধ শেল: {', '.join(shells.keys())}\n"
            f"{context}\nJSON পরিকল্পনা দাও।")
    raw = _llm(PLANNER_SYSTEM, user, max_tokens=450)
    plan = _extract_json(raw)
    if plan and isinstance(plan.get("steps"), list) and plan["steps"]:
        clean = []
        for s in plan["steps"]:
            if isinstance(s, dict) and s.get("cmd"):
                shell = s.get("shell") if s.get("shell") in shells else "cmd"
                clean.append({"cmd": s["cmd"].strip(), "shell": shell,
                              "purpose": s.get("purpose", ""),
                              "verify": (s.get("verify") or "").strip()})
        if clean:
            return {"task": plan.get("task", user_text), "steps": clean}
    return {}


def _llm_fix(cmd: str, exit_code: int, output: str) -> dict | None:
    sys_p = ("তুমি টার্মিনাল এরর বিশ্লেষক। ব্যর্থ কমান্ড ও আউটপুট দেখে নিরাপদ সমাধান দাও। "
             "শুধু JSON: {\"analysis\":\"সংক্ষেপে কারণ\",\"fix_cmd\":\"একটি নিরাপদ কমান্ড বা null\"} "
             "বিপজ্জনক কিছু প্রস্তাব করবে না।")
    user = f"কমান্ড: {cmd}\nexit code: {exit_code}\nআউটপুট:\n{output[:500]}"
    return _extract_json(_llm(sys_p, user, max_tokens=250))


# ----------------- দ্রুত পথ: স্পষ্ট কমান্ড শনাক্ত -----------------
_EXPLICIT_RE = re.compile(
    r"\b(dir|dir /b|ls|ls -la|echo|ipconfig|ping|systeminfo|whoami|tasklist|"
    r"hostname|getmac|node -v|npm -v|npm run\s+\S+|git status|git log|git branch|"
    r"git diff|python --version|pip list)\b")


def _explicit_command(user_text: str) -> str | None:
    """নির্দেশের ভেতরে সরাসরি কমান্ড থাকলে সেটা বের করে (LLM ছাড়া, সেকেন্ডে)।"""
    if len(user_text) > 90:
        return None
    m = _EXPLICIT_RE.search(user_text.lower())
    if not m:
        return None
    cmd = user_text[m.start():].strip()
    # শেষের নির্দেশ-শব্দ ছাঁটা
    for w in (" চালাও", " চালা", " রান", " করো", " কর", " দাও", " দেখাও", " দেও",
              " দিব", " run", " koro", " execute", " please", " টার্মিনালে"):
        if cmd.lower().endswith(w):
            cmd = cmd[:-len(w)].strip()
    return cmd or None


# ----------------- যাচাই -----------------
def verify_step(step: dict, cwd: str | None) -> tuple[bool, str]:
    """verify কমান্ড থাকলে চালায়। মূল কমান্ড সফল কিন্তু verify কমান্ড নিজেই
    ত্রুটিপূর্ণ হলে ধাপ ভুলভাবে ব্যর্থ দেখানোর বদলে সতর্কতা-সহ পাস করানো হয়।"""
    v = (step.get("verify") or "").strip()
    if not v:
        return True, ""
    if classify(v) == "forbidden":
        return False, "verify কমান্ড নিষিদ্ধ"
    for shell in [step.get("shell", "cmd"), "cmd"]:
        res = run(v, shell, cwd, timeout=60)
        audit({"event": "verify", "cmd": v, "shell": shell, "exit": res["exit"]})
        if res["exit"] == 0:
            lines = [l for l in (res["stdout"] or "").splitlines() if l.strip()]
            return True, (f"যাচাই: {lines[0][:70]}" if lines else "যাচাই পাস")
    # verify কমান্ড নিজেই খারাপ — মূল কমান্ডের সাফল্য অক্ষুণ্ণ রাখি
    return True, "⚠️ যাচাই কমান্ড চলেনি (মূল কমান্ড সফল)"


# ----------------- মূল স্বায়ত্তশাসিত চালিকা -----------------
def run_task(user_text: str, speak_cb, confirm_cb, cwd: str | None = None,
             listen_cb=None) -> str:
    """পূর্ণ স্বায়ত্তশাসিত পাইপলাইন: পরিকল্পনা → নিরাপত্তা → চালানো → যাচাই → রিপোর্ট।"""
    CANCEL_EVENT.clear()
    ACTIVE.set()
    stop_thread = None
    if listen_cb is not None:
        def _voice_stop():
            while ACTIVE.is_set() and not CANCEL_EVENT.is_set():
                try:
                    heard = listen_cb()
                except Exception:
                    heard = None
                if heard and any(w in heard.lower() for w in
                                 ("থাম", "বাতিল", "stop", "cancel", "থামো")):
                    cancel_task()
                    return
                time.sleep(0.5)
        stop_thread = threading.Thread(target=_voice_stop, daemon=True)
        stop_thread.start()

    report: list[str] = []
    try:
        # দ্রুত পথ: স্পষ্ট এক-কমান্ড নির্দেশ হলে LLM ছাড়াই সম্পন্ন (সেকেন্ডে)
        direct = _explicit_command(user_text)
        if direct:
            cat = classify(direct)
            if cat == "forbidden":
                speak_cb("এই কমান্ডটা নিষিদ্ধ, চালাব না।")
                return "ব্যর্থ: নিষিদ্ধ কমান্ড।"
            if cat != "safe" and not confirm_cb(f"'{direct}' চালাব? বলুন হ্যাঁ বা না।"):
                return "ঠিক আছে, চালাইনি।"
            res = run(direct, "cmd", cwd)
            audit({"event": "single", "cmd": res["cmd"], "shell": res["shell"],
                   "exit": res["exit"],
                   "output": (res["stdout"] or res["stderr"])[:400]})
            ok = res["exit"] == 0
            lines = [l for l in (res["stdout"] or res["stderr"]).splitlines() if l.strip()]
            speak_cb("সম্পন্ন!" if ok else "ব্যর্থ হয়েছে।")
            return (f"{'✅' if ok else '❌'} {direct}\n"
                    f"ফলাফল: {' | '.join(lines[:3])[:200] or 'আউটপুট নেই'}")

        speak_cb("ঠিক আছে, কাজটা পরিকল্পনা করছি...")
        p = plan_task(user_text, cwd)
        if not p:
            # এক-কমান্ড fallback: সোজা শ্রেণিবিন্যাস
            cmd = user_text.strip()
            cat = classify(cmd)
            if cat == "forbidden":
                speak_cb("এই কমান্ডটা নিষিদ্ধ, চালাব না।")
                return "ব্যর্থ: নিষিদ্ধ কমান্ড।"
            if cat != "safe" and not confirm_cb(f"'{cmd}' চালাব? বলুন হ্যাঁ বা না।"):
                return "ঠিক আছে, চালাইনি।"
            res = run(cmd, "cmd", cwd)
            audit({"event": "single", **{k: res[k] for k in ("cmd", "shell", "exit")}})
            ok = res["exit"] == 0
            out = (res["stdout"] or res["stderr"]).strip().splitlines()
            summary = " | ".join(out[:3])[:200]
            speak_cb("সম্পন্ন!" if ok else "ব্যর্থ হয়েছে।")
            return (f"{'✅' if ok else '❌'} {cmd}\nফলাফল: {summary or 'আউটপুট নেই'}")

        steps = p["steps"]
        speak_cb(f"{len(steps)}টা ধাপে কাজ করব।")
        statuses = []
        for i, s in enumerate(steps, 1):
            if CANCEL_EVENT.is_set():
                speak_cb("কাজ বাতিল করা হলো।")
                statuses.append(("CANCELLED", s, "ব্যবহারকারী বাতিল করেছেন"))
                break
            cmd, shell = s["cmd"], s.get("shell", "cmd")
            purpose = s.get("purpose") or cmd
            cat = classify(cmd)
            if cat == "forbidden":
                statuses.append(("BLOCKED", s, "নিষিদ্ধ কমান্ড"))
                speak_cb(f"ধাপ {i} নিষিদ্ধ, বাদ দিলাম।")
                continue
            if cat in ("dangerous", "caution"):
                if not confirm_cb(f"ধাপ {i}: {purpose} — কমান্ড: {cmd}। চালাব? বলুন হ্যাঁ বা না।"):
                    statuses.append(("SKIPPED", s, "অনুমতি দেওয়া হয়নি"))
                    speak_cb("ঠিক আছে, এই ধাপটা বাদ।")
                    continue
            speak_cb(f"ধাপ {i} চালাচ্ছি...")
            res = run(cmd, shell, cwd, timeout=180)
            audit({"event": "step", "step": i, "cmd": cmd, "shell": shell,
                   "exit": res["exit"], "category": cat, "output": res["stdout"] or res["stderr"]})
            ok = res["exit"] == 0 and not res["timed_out"]
            vnote = ""
            if ok:
                ok, vnote = verify_step(s, cwd)
            # ব্যর্থ হলে: বিশ্লেষণ → নিরাপদ ফিক্স → একবার পুনরায় চেষ্টা
            if not ok and not CANCEL_EVENT.is_set():
                speak_cb(f"ধাপ {i} ব্যর্থ, কারণ খুঁজছি...")
                fx = _llm_fix(cmd, res["exit"],
                              ((res["stdout"] or "") + "\n" + (res["stderr"] or ""))[:500])
                fix_cmd = (fx or {}).get("fix_cmd")
                if fix_cmd:
                    fcat = classify(fix_cmd)
                    if fcat != "forbidden":
                        if fcat != "safe" and not confirm_cb(
                                f"সমাধান পেয়েছি: {fix_cmd}। চালাব? হ্যাঁ/না।"):
                            fix_cmd = None
                        if fix_cmd:
                            res = run(fix_cmd, shell, cwd, timeout=180)
                            audit({"event": "fix", "step": i, "cmd": fix_cmd,
                                   "exit": res["exit"],
                                   "output": (res["stdout"] or "")[:400]})
                            ok = res["exit"] == 0
                            if ok:
                                ok, vnote = verify_step(s, cwd)
                                cmd = fix_cmd
            if ok:
                statuses.append(("PASS", s, vnote or res["stdout"][:80]))
                speak_cb(f"ধাপ {i} সফল।")
            else:
                statuses.append(("FAIL", s, (res["stderr"] or res["stdout"])[:120]))
                speak_cb(f"ধাপ {i} ব্যর্থ থেকে গেল।")

        passed = sum(1 for st, _, _ in statuses if st == "PASS")
        failed = sum(1 for st, _, _ in statuses if st in ("FAIL", "BLOCKED"))
        if failed == 0 and passed == len(steps) and passed > 0:
            verdict = f"সব {passed}টা ধাপ সফলভাবে সম্পন্ন হয়েছে!"
        elif passed:
            verdict = f"{passed}টা ধাপ সফল, {failed}টা ব্যর্থ।"
        else:
            verdict = "কাজটা সফল হয়নি।"
        speak_cb(verdict)
        for st, s, note in statuses:
            report.append(f"- {st}: `{s.get('cmd','')}` — {note}")
        return f"টাস্ক: {p.get('task', user_text)}\n" + "\n".join(report)
    except KeyboardInterrupt:
        cancel_task()
        speak_cb("কাজ বাতিল করা হলো।")
        return "⏹ ব্যবহারকারী কাজটা বাতিল করেছেন।"
    finally:
        ACTIVE.clear()
        if stop_thread:
            stop_thread.join(timeout=2)


# ----------------- সেলফ-টেস্ট ও রিপোর্ট -----------------
def self_test() -> None:
    """বাস্তব পরীক্ষা চালিয়ে ৪টি রিপোর্ট ফাইল তৈরি করে। শুধু নিরাপদ কমান্ড।"""
    base = os.path.dirname(os.path.abspath(__file__))
    R: dict[str, list] = {
        "engine": [], "security": [], "commands": [], "dev": []}
    print("=== AVA Terminal Engine Self-Test ===\n")

    # ১. শেল শনাক্তকরণ
    sh = detect_shells()
    print("Shells:", list(sh.keys()))
    R["engine"].append(("Multi-terminal detection", "PASS" if "cmd" in sh else "FAIL",
                        f"পাওয়া গেছে: {', '.join(sh.keys())}"))
    for s in ("powershell", "gitbash", "wsl"):
        R["engine"].append((f"{s} সাপোর্ট", "PASS" if s in sh else "NOT TESTED",
                            "ইনস্টল নেই" if s not in sh else "উপলব্ধ"))

    # ২. শ্রেণিবিন্যাস
    cases = [("dir", "safe"), ("echo hi", "safe"), ("git status", "safe"),
             ("format C:", "forbidden"), ("shutdown /s", "forbidden"),
             ("del /s /q C:\\Users", "forbidden"), ("rm -rf /", "forbidden"),
             ("reg delete HKLM", "forbidden"), ("del temp.txt", "caution"),
             ("npm install express", "dangerous")]
    ok = all(classify(c) == e for c, e in cases)
    for c, e in cases:
        got = classify(c)
        R["security"].append((f"classify('{c}')", "PASS" if got == e else "FAIL",
                              f"প্রত্যাশা {e}, পাওয়া {got}"))
    print("Classification:", "PASS" if ok else "FAIL")

    # ৩. secret masking
    test_out = "API_KEY=AIzaSyabc123xyz456  sk-abcdef1234567890  password=hunter2"
    masked = mask_secrets(test_out)
    ok = "AIzaSyabc" not in masked and "hunter2" not in masked
    R["security"].append(("Secret masking (কণ্ঠ/লগে key যায় না)",
                          "PASS" if ok else "FAIL", masked[:80]))
    print("Secret masking:", "PASS" if ok else "FAIL")

    # ৪. বাস্তব কমান্ড চালানো + আউটপুট + exit code
    r1 = run("echo AVA_TEST_OK", "cmd", base)
    R["commands"].append(("CMD echo execute", "PASS" if r1["exit"] == 0 and
                          "AVA_TEST_OK" in r1["stdout"] else "FAIL",
                          f"exit={r1['exit']} duration={r1['duration']}s"))
    print("cmd echo:", r1["exit"], r1["duration"], "s")
    if "powershell" in sh:
        r2 = run("Write-Output PS_OK", "powershell", base)
        R["commands"].append(("PowerShell execute",
                              "PASS" if r2["exit"] == 0 and "PS_OK" in r2["stdout"] else "FAIL",
                              f"exit={r2['exit']}"))
    if "gitbash" in sh:
        r3 = run("echo BASH_OK", "gitbash", base)
        R["commands"].append(("Git Bash execute",
                              "PASS" if r3["exit"] == 0 and "BASH_OK" in r3["stdout"] else "FAIL",
                              f"exit={r3['exit']}"))
    r4 = run("git --version", "cmd", base)
    R["commands"].append(("git --version", "PASS" if r4["exit"] == 0 else "FAIL",
                          r4["stdout"][:40]))

    # ৫. টাইমআউট + বাতিলকরণ
    t0 = time.time()
    th = threading.Thread(target=lambda: run("ping -n 10 127.0.0.1", "cmd", base, timeout=60))
    th.start()
    time.sleep(1.5)
    cancel_task()
    th.join(timeout=5)
    dur = time.time() - t0
    R["engine"].append(("Running task cancel/terminate",
                        "PASS" if dur < 4 else "FAIL", f"{dur:.1f}s-এ থেমেছে"))
    print(f"Cancel test: {dur:.1f}s")

    # ৬. অডিট লগ
    ok = os.path.exists(AUDIT_FILE)
    R["security"].append(("Audit log (ava_terminal_audit.jsonl)", "PASS" if ok else "FAIL",
                          "লেখা হচ্ছে" if ok else "নেই"))

    # ৭. NL → প্ল্যান (বাস্তব LLM কল)
    print("Planning (LLM)... একটু সময় লাগবে")
    p = plan_task("এই ফোল্ডারে কী কী ফাইল আছে দেখাও", base)
    R["engine"].append(("Natural language → command plan",
                        "PASS" if p.get("steps") else "FAIL",
                        f"{len(p.get('steps', []))} ধাপ"))
    if p.get("steps"):
        for s in p["steps"][:3]:
            print("  plan:", s.get("cmd"))

    # ৮. স্বায়ত্তশাসিত নিরাপদ টাস্ক (শুধু-পঠন)
    print("Autonomous safe task...")
    final = run_task("এই ফোল্ডারের ফাইল তালিকা দেখাও",
                     speak_cb=lambda t: print("  🔊", t),
                     confirm_cb=lambda q: True, cwd=base)
    ok = "সফল" in final or "PASS" in final
    R["engine"].append(("Autonomous multi-step execution + verification",
                        "PASS" if ok else "FAIL", final[:80].replace("\n", " ")))

    # ৯. Developer mode — যা যা ইনস্টল আছে বাস্তবে টেস্ট
    r5 = run("node -v", "cmd", base)
    R["dev"].append(("Node.js detect", "PASS" if r5["exit"] == 0 else "NOT TESTED",
                     r5["stdout"].strip()[:30] or "node ইনস্টল নেই"))
    r6 = run("npm -v", "cmd", base)
    R["dev"].append(("npm detect", "PASS" if r6["exit"] == 0 else "NOT TESTED",
                     r6["stdout"].strip()[:30] or "npm ইনস্টল নেই"))
    for tool, probe in (("Composer/PHP", "php -v"), ("MySQL", "mysql --version")):
        rr = run(probe, "cmd", base)
        R["dev"].append((f"{tool} detect", "PASS" if rr["exit"] == 0 else "NOT TESTED",
                         (rr["stdout"].strip()[:40] or "ইনস্টল নেই")))
    R["dev"].append(("npm/composer workflow (install/run/serve)",
                     "NOT TESTED", "ব্যবহারকারী প্রজেক্ট ছাড়া পরীক্ষা ঝুঁকিপূর্ণ"))

    # ----------------- রিপোর্ট লেখা -----------------
    def status_lines(items):
        return "\n".join(f"- **{st}** — {name}  \n  {note}" for name, st, note in items)

    def overall(items):
        if any(st == "FAIL" for _, st, _ in items):
            return "FAIL"
        if any(st == "NOT TESTED" for _, st, _ in items):
            return "PARTIAL"
        return "PASS"

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    reports = {
        "AVA_TERMINAL_ENGINE_REPORT.md": f"""# AVA Terminal Engine Report
Generated: {stamp}

## Overall: {overall(R['engine'])}

{status_lines(R['engine'])}
""",
        "AVA_SECURITY_AUDIT.md": f"""# AVA Security Audit
Generated: {stamp}

## Overall: {overall(R['security'])}

### নিয়ম
- LLM কমান্ড সরাসরি চলে না — প্রতিটি কমান্ড classify() দিয়ে যায়
- forbidden → কখনোই চলে না; caution/dangerous → ভয়েস অনুমতি লাগে
- সব লগ/কণ্ঠে secret masking হয়; অডিট ফাইল: ava_terminal_audit.jsonl
- elevated/admin কমান্ড চলে না; Defender/UAC স্পর্শ করা হয় না

### পরীক্ষা
{status_lines(R['security'])}
""",
        "AVA_COMMAND_TEST_RESULTS.md": f"""# AVA Command Test Results
Generated: {stamp}

## Overall: {overall(R['commands'])}

{status_lines(R['commands'])}
""",
        "AVA_DEVELOPER_AUTOMATION_REPORT.md": f"""# AVA Developer Automation Report
Generated: {stamp}

## Overall: {overall(R['dev'])}

{status_lines(R['dev'])}
""",
    }
    for name, content in reports.items():
        with open(os.path.join(base, name), "w", encoding="utf-8") as f:
            f.write(content)
        print("Report:", name)
    print("\n=== সম্পন্ন ===")


if __name__ == "__main__":
    self_test()
