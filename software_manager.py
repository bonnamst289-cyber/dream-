# -*- coding: utf-8 -*-
"""AVA Software & Dev-Environment Manager — বাস্তব Windows তথ্য, কোনো অনুমান নয়।
- ইনভেন্টরি: রেজিস্ট্রি Uninstall কী (HKLM/HKCU/WOW64) — নাম/প্রকাশক/সংস্করণ/ইনস্টল তারিখ
- চলমান প্রসেস (tasklist) • winget দিয়ে search/install/upgrade/uninstall (অনুমতি সহ)
- Dev tools: XAMPP/Apache/MySQL/PHP/Composer/Node/Git/VS Code — আসল পথ ও সংস্করণ
- নিরাপত্তা: uninstall/stop-service/upgrade → স্পষ্ট অনুমতি (confirm callback)"""
import os
import re
import subprocess
import winreg

XAMPP_CANDIDATES = ("C:\\xampp", "D:\\xampp", "E:\\xampp", "C:\\Program Files\\XAMPP")

DEV_TOOLS = [
    ("PHP", "php", "--version"),
    ("Composer", "composer", "--version"),
    ("Node.js", "node", "--version"),
    ("NPM", "npm", "--version"),
    ("Git", "git", "--version"),
    ("Python", "python", "--version"),
    ("MySQL client", "mysql", "--version"),
]


def _run(cmd, timeout=60) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           errors="replace", shell=False)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return -1, str(e)


def inventory(query: str = "") -> list[dict]:
    """ইনস্টল করা সফটওয়্যার (Windows রেজিস্ট্রি থেকে — আসল তথ্য)।"""
    keys = [
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\WOW6432Node"),
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    items = {}
    for hive, path in keys:
        try:
            k = winreg.OpenKey(hive, path)
        except OSError:
            continue
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(k, i)
                i += 1
            except OSError:
                break
            try:
                sk = winreg.OpenKey(k, sub)
                name = winreg.QueryValueEx(sk, "DisplayName")[0]
                if not name or name in items:
                    continue
                def gv(field):
                    try:
                        return winreg.QueryValueEx(sk, field)[0]
                    except OSError:
                        return ""
                items[name] = {
                    "name": name,
                    "version": gv("DisplayVersion"),
                    "publisher": gv("Publisher"),
                    "install_date": gv("InstallDate"),
                    "location": gv("InstallLocation"),
                    "uninstall": gv("UninstallString"),
                }
            except OSError:
                continue
    result = list(items.values())
    if query:
        ql = query.lower()
        result = [r for r in result if ql in r["name"].lower()
                  or ql in (r["publisher"] or "").lower()]
    return sorted(result, key=lambda r: r["name"].lower())


def running_apps() -> list[str]:
    code, out = _run(["tasklist", "/FO", "CSV"], timeout=30)
    apps = []
    for line in (out or "").splitlines()[1:]:
        parts = [p.strip('"') for p in line.split('","')]
        if parts and parts[0].endswith(".exe"):
            apps.append(parts[0][:-4])
    return sorted(set(apps))


def is_running(process_name: str) -> bool:
    code, out = _run(["tasklist", "/FI", f"IMAGENAME eq {process_name}"], timeout=20)
    return process_name.lower() in (out or "").lower()


def winget_search(query: str) -> list[dict]:
    code, out = _run(["winget", "search", query, "--accept-source-agreements"],
                     timeout=120)
    rows = []
    for line in (out or "").splitlines():
        if "—" in line or line.strip().startswith("-"):
            continue
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) >= 3 and not parts[0].lower().startswith(("winget", "msstore", "winget:")):
            rows.append({"name": parts[0], "id": parts[1],
                         "version": parts[2] if len(parts) > 2 else "",
                         "source": parts[-1] if len(parts) > 3 else ""})
    return rows[:8]


def winget_action(pkg_id: str, action: str, confirm_cb=None) -> str:
    """install/upgrade/uninstall — অনুমতি বাধ্যতামূলক; বাস্তব ফলাফল + যাচাই।"""
    labels = {"install": "ইনস্টল", "upgrade": "আপগ্রেড", "uninstall": "আনইনস্টল"}
    verb = labels.get(action, action)
    if confirm_cb and not confirm_cb(
            f"'{pkg_id}' কে {verb} করা হবে (winget)। এটা সিস্টেম পরিবর্তন করে — নিশ্চিত? হ্যাঁ/না।"):
        return "ঠিক আছে, করিনি।"
    code, out = _run(["winget", action, "--id", pkg_id, "--exact",
                      "--accept-source-agreements", "--accept-package-agreements",
                      "--silent"], timeout=600)
    tail = "\n".join(l for l in (out or "").splitlines() if l.strip())[-300:]
    if code != 0:
        return f"❌ {verb} ব্যর্থ (exit {code}):\n{tail}"
    # যাচাই: আবার খোঁজো
    code2, out2 = _run(["winget", "list", "--id", pkg_id, "--exact",
                        "--accept-source-agreements"], timeout=120)
    verified = pkg_id.lower() in (out2 or "").lower()
    return (f"✅ {verb} সফল এবং যাচাইকৃত!" if verified
            else f"⚠️ {verb} কমান্ড চলেছে (exit 0) কিন্তু তালিকায় যাচাই হয়নি:\n{tail}")


# ----------------- Dev Environment -----------------
def xampp_path() -> str | None:
    for cand in XAMPP_CANDIDATES:
        if os.path.isdir(cand):
            return cand
    return None


def dev_status() -> list[tuple[str, str, str]]:
    rows = []
    xp = xampp_path()
    rows.append(("XAMPP", "PASS" if xp else "NOT INSTALLED", xp or "—"))
    if xp:
        rows.append(("MySQL/MariaDB (XAMPP)",
                     "RUNNING" if is_running("mysqld.exe") else "STOPPED",
                     "port 3306 " + ("open" if _port_open() else "closed")))
        rows.append(("Apache (XAMPP)",
                     "RUNNING" if is_running("httpd.exe") else "STOPPED", xp + "\\apache"))
        php = os.path.join(xp, "php", "php.exe")
        if os.path.exists(php):
            code, out = _run([php, "-v"], timeout=20)
            rows.append(("PHP", "PASS", out.splitlines()[0] if out else "—"))
        else:
            rows.append(("PHP", "NOT INSTALLED", "—"))
    for name, exe, arg in DEV_TOOLS:
        code, out = _run([exe, arg], timeout=25)
        first = (out or "").strip().splitlines()
        rows.append((name, "PASS" if code == 0 else "NOT INSTALLED",
                     first[0][:60] if first else "—"))
    code, out = _run(["code", "--version"], timeout=25)
    rows.append(("VS Code", "PASS" if code == 0 else "NOT INSTALLED",
                 (out or "").splitlines()[0][:30] if code == 0 else "—"))
    return rows


def _port_open(port: int = 3306) -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def xampp_service_action(what: str, confirm_cb=None) -> str:
    """MySQL/Apache start/stop — XAMPP bat ফাইল দিয়ে; স্টপে অনুমতি।"""
    xp = xampp_path()
    if not xp:
        return "XAMPP ইনস্টল নেই।"
    what = what.lower()
    if "mysql" in what:
        if "start" in what or "চালু" in what:
            if is_running("mysqld.exe"):
                return "MySQL আগে থেকেই চালু আছে।"
            bat = os.path.join(xp, "mysql_start.bat")
            if not os.path.exists(bat):
                return "mysql_start.bat পাইনি।"
            _run([bat], timeout=30)
            import time
            time.sleep(4)
            running = is_running("mysqld.exe") and _port_open()
            return ("✅ MySQL চালু হয়েছে এবং যাচাইকৃত (port 3306)!" if running
                    else "⚠️ চালু কমান্ড চলেছে কিন্তু যাচাই হয়নি — XAMPP Control Panel দেখুন।")
        if ("stop" in what or "বন্ধ" in what):
            if confirm_cb and not confirm_cb("MySQL বন্ধ করলে ডাটাবেস অ্যাপ বন্ধ হবে। নিশ্চিত? হ্যাঁ/না।"):
                return "ঠিক আছে, বন্ধ করিনি।"
            code, out = _run(["taskkill", "/IM", "mysqld.exe", "/F"], timeout=30)
            return ("🛑 MySQL বন্ধ হয়েছে।" if code == 0 else "বন্ধ করা যায়নি।")
    if "apache" in what:
        if "start" in what or "চালু" in what:
            bat = os.path.join(xp, "apache_start.bat")
            if os.path.exists(bat):
                _run([bat], timeout=30)
                import time
                time.sleep(4)
                running = is_running("httpd.exe")
                return ("✅ Apache চালু হয়েছে এবং যাচাইকৃত!" if running
                        else "⚠️ যাচাই হয়নি — XAMPP Control Panel দেখুন।")
            return "apache_start.bat পাইনি।"
        if "stop" in what or "বন্ধ" in what:
            if confirm_cb and not confirm_cb("Apache বন্ধ করব? হ্যাঁ/না।"):
                return "ঠিক আছে।"
            code, out = _run(["taskkill", "/IM", "httpd.exe", "/F"], timeout=30)
            return ("🛑 Apache বন্ধ হয়েছে।" if code == 0 else "বন্ধ করা যায়নি।")
    return "বুঝতে পারিনি — MySQL নাকি Apache?"


# ----------------- ভয়েস রাউটার -----------------
def graceful_close(process_name: str) -> bool:
    """অভদ্র taskkill-এর আগে: উইন্ডোর Close বার্তা পাঠাও (unsaved কাজ রক্ষা)।"""
    ps = ("Get-Process | Where-Object { $_.ProcessName -like "
          f"'{process_name.split('.')[0]}*' -and $_.MainWindowTitle }} | "
          "ForEach-Object { $_.Close() }")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False


def handle(user_text: str, confirm_cb=None) -> tuple[bool, str] | None:
    t = user_text.lower()
    is_sw = any(w in t for w in ("software", "সফটওয়্যার", "ইনস্টল", "install",
                                 "আনইনস্টল", "uninstall", "আপগ্রেড", "upgrade",
                                 "প্রোগ্রাম", "app list", "অ্যাপ লিস্ট"))
    is_dev = any(w in t for w in ("xampp", "apache", "mysql", "php", "composer",
                                  "node", "npm", "laravel", "dev environment",
                                  "ডেভেলপমেন্ট"))
    if not is_sw and not is_dev:
        return None

    # Dev environment
    if is_dev:
        if any(w in t for w in ("status", "স্ট্যাটাস", "ache", "আছে", "check",
                                "চেক", "version", "ভার্সন", "কত", "কোন কোন")):
            rows = dev_status()
            return True, "🛠️ Development Environment:\n" + "\n".join(
                f"• {n}: {s} ({note})" for n, s, note in rows)
        if "mysql" in t and any(w in t for w in ("start", "stop", "চালু", "বন্ধ")):
            return True, xampp_service_action("mysql " + ("start" if "start" in t or "চালু" in t else "stop"),
                                              confirm_cb)
        if "apache" in t and any(w in t for w in ("start", "stop", "চালু", "বন্ধ")):
            return True, xampp_service_action("apache " + ("start" if "start" in t or "চালু" in t else "stop"),
                                              confirm_cb)

    # Software inventory
    if any(w in t for w in ("কোন কোন", "kon kon", "লিস্ট", "list", "inventory",
                            "কতগুলো", "কী কী")) and not ("ইনস্টল" in t or "install" in t):
        items = inventory()
        return True, f"💻 ইনস্টল করা সফটওয়্যার: {len(items)}টি\n" + "\n".join(
            f"• {i['name']}{' ' + i['version'] if i['version'] else ''}" for i in items[:15])

    if ("চলছে" in t or "running" in t or "cholche" in t) and is_sw:
        apps = running_apps()
        return True, f"▶️ চলমান প্রোগ্রাম: {len(apps)}টি\n" + ", ".join(apps[:20])

    # install/upgrade/uninstall via winget
    m = re.search(r"(?:install|ইনস্টল|upgrade|আপগ্রেড|update|আপডেট|uninstall|আনইনস্টল)\s+(.+)",
                  user_text, re.I)
    if m:
        q = m.group(1).strip()
        action = ("install" if re.search(r"install|ইনস্টল", user_text, re.I) else
                  "uninstall" if re.search(r"uninstall|আনইনস্টল", user_text, re.I) else
                  "upgrade")
        # ইতিমধ্যে আছে কি না
        have = inventory(q)
        if have and action == "install":
            return True, (f"'{q}' আগে থেকেই ইনস্টল আছে:\n" +
                          "\n".join(f"• {h['name']} {h['version']}" for h in have[:3]))
        pkgs = winget_search(q)
        if not pkgs:
            return True, (f"'{q}' নামে কোনো নিরাপদ প্যাকেজ পাইনি (winget)। "
                          "বানান দেখে আবার বলুন।")
        best = pkgs[0]
        info = "\n".join(f"• {p['name']} | ID: {p['id']} | v{p['version']}"
                         for p in pkgs[:3])
        return True, (f"📦 পাওয়া গেছে:\n{info}\n\nবলুন: '{best['id']}' ইনস্টল করো — "
                      "তখন অনুমতি নিয়ে ইনস্টল করবে।")
    if re.search(r"(ইনস্টল করো|install koro|ইনস্টল কর)", t):
        m2 = re.search(r"([\w\.\-]+)\s*(?:ইনস্টল করো|install koro)", t)
        if m2:
            pkgs = winget_search(m2.group(1))
            if pkgs:
                return True, winget_action(pkgs[0]["id"], "install", confirm_cb)
        return True, "কী ইনস্টল করব বলুন (যেমন: VS Code ইনস্টল করো)।"
    return None
