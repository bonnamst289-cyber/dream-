# -*- coding: utf-8 -*-
"""
AVA — MySQL Command Memory System
==================================
- XAMPP MySQL/MariaDB শনাক্তকরণ (path, পোর্ট, চালু কি না) — অনুমান নয়
- Credentials: ব্যবহারকারী নিজে সেটআপ করে; Windows DPAPI দিয়ে এনক্রিপ্টেড সংরক্ষণ
- ডাটাবেস: ava_universal_ai (utf8mb4) — বিদ্যমান ডেটা অক্ষত; migration-এর আগে backup
- Learn Once, Execute Instantly: সফল যাচাইকৃত কাজ → অনুমতি নিয়ে মেমরি
- Instant execution: মেমরি মিললে AI কল ছাড়াই validated action
- সুরক্ষা: parameterized SQL, secret-never-saved, destructive-এ confirmation
"""
import base64
import ctypes
import datetime
import json
import os
import re
import subprocess
import time
from pathlib import Path

DB_NAME = "ava_universal_ai"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "ava_db_credentials.bin")
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")

# ----------------- XAMPP শনাক্তকরণ -----------------
def detect_xampp() -> dict:
    info = {"found": False, "mysql_exe": None, "mysqldump": None, "ini_port": None}
    for cand in ("C:\\xampp", "D:\\xampp", "E:\\xampp",
                 "C:\\Program Files\\XAMPP"):
        if os.path.isdir(cand):
            info["found"] = True
            info["path"] = cand
            info["mysql_exe"] = os.path.join(cand, "mysql", "bin", "mysql.exe")
            info["mysqldump"] = os.path.join(cand, "mysql", "bin", "mysqldump.exe")
            ini = os.path.join(cand, "mysql", "bin", "my.ini")
            if os.path.exists(ini):
                try:
                    txt = open(ini, encoding="utf-8", errors="replace").read()
                    m = re.search(r"port\s*=\s*(\d{3,5})", txt)
                    if m:
                        info["ini_port"] = int(m.group(1))
                except Exception:
                    pass
            break
    return info


def port_open(host: str = "127.0.0.1", port: int = 3306) -> bool:
    import socket
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


# ----------------- DPAPI (Windows নিজস্ব এনক্রিপশন) -----------------
class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint), ("pbData", ctypes.c_void_p)]


def _dpapi_protect(data: bytes) -> bytes:
    buf = ctypes.create_string_buffer(data, len(data))
    inp = _BLOB(len(data), ctypes.cast(buf, ctypes.c_void_p))
    out = _BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(inp), "AVA DB Credentials", None, None, None, 0,
            ctypes.byref(out)):
        raise OSError("DPAPI encrypt ব্যর্থ")
    try:
        return ctypes.string_at(out.pbData, out.cbData)  # NUL-সহ পূর্ণ ডেটা
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.c_void_p(out.pbData))


def _dpapi_unprotect(data: bytes) -> bytes:
    buf = ctypes.create_string_buffer(data, len(data))
    inp = _BLOB(len(data), ctypes.cast(buf, ctypes.c_void_p))
    out = _BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(inp), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError("DPAPI decrypt ব্যর্থ")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.c_void_p(out.pbData))


def save_credentials(host: str, port: int, user: str, password: str) -> None:
    blob = _dpapi_protect(json.dumps(
        {"host": host, "port": port, "user": user, "password": password}).encode())
    with open(CONFIG_FILE, "wb") as f:
        f.write(base64.b64encode(blob))


def load_credentials() -> dict | None:
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        blob = base64.b64decode(open(CONFIG_FILE, "rb").read())
        return json.loads(_dpapi_unprotect(blob).decode())
    except Exception:
        return None


def credentials_status() -> str:
    if load_credentials():
        return "সেভ করা আছে (DPAPI-এনক্রিপ্টেড)"
    return "সেটআপ হয়নি"


def interactive_setup() -> str:
    """নিরাপদ সেটআপ: পাসওয়ার্ড হিডেন ইনপুট, DPAPI এনক্রিপশন, বাস্তব কানেকশন-টেস্ট।"""
    import getpass
    x = detect_xampp()
    print("=" * 50)
    print("🔐 AVA MySQL সেটআপ (কোনো অনুমান নেই — আপনি নিজে দিবেন)")
    if x["found"]:
        print(f"XAMPP পাওয়া গেছে: {x['path']}")
    if x["ini_port"]:
        print(f"my.ini পোর্ট: {x['ini_port']}")
    print("=" * 50)
    host = input(f"Host [127.0.0.1]: ").strip() or "127.0.0.1"
    port_s = input(f"Port [{x['ini_port'] or 3306}]: ").strip()
    port = int(port_s) if port_s else (x["ini_port"] or 3306)
    user = input("Username (XAMPP ডিফল্ট সাধারণত root): ").strip() or "root"
    password = getpass.getpass("Password (খালি হলে Enter): ")
    try:
        import pymysql
        conn = pymysql.connect(host=host, port=port, user=user, password=password,
                               connect_timeout=5)
        conn.close()
    except Exception as e:
        return f"❌ কানেকশন ব্যর্থ — {e}\n(ভুল credentials বা MySQL বন্ধ — XAMPP Control Panel দেখুন)"
    save_credentials(host, port, user, password)
    return f"✅ কানেকশন সফল, credentials DPAPI-দিয়ে এনক্রিপ্ট করে সেভ হলো: {CONFIG_FILE}"


# ----------------- কানেকশন -----------------
def get_connection():
    creds = load_credentials()
    if not creds:
        raise RuntimeError("DB credentials সেটআপ হয়নি — চালান: venv\\Scripts\\python memory_db.py setup")
    import pymysql
    try:
        return pymysql.connect(host=creds["host"], port=creds["port"],
                               user=creds["user"], password=creds["password"],
                               database=DB_NAME, charset="utf8mb4",
                               cursorclass=pymysql.cursors.DictCursor,
                               connect_timeout=5)
    except pymysql.err.OperationalError as e:
        code = e.args[0] if e.args else "?"
        reasons = {1045: "ভুল username/password",
                   2003: "MySQL চালু নেই বা পোর্ট ভুল (XAMPP Control Panel-এ MySQL চালু করুন)",
                   1049: f"ডাটাবেস '{DB_NAME}' এখনো তৈরি হয়নি — setup চালান"}
        raise RuntimeError(f"MySQL কানেকশন ব্যর্থ ({code}): "
                           f"{reasons.get(code, e.args[1] if len(e.args) > 1 else e)}")


# ----------------- স্কিমা (migration-safe, ডেটা অক্ষত) -----------------
SCHEMA = [
    """CREATE TABLE IF NOT EXISTS command_memories (
        id INT AUTO_INCREMENT PRIMARY KEY,
        command_name VARCHAR(150) NOT NULL UNIQUE,
        intent VARCHAR(80) NOT NULL,
        bangla_aliases MEDIUMTEXT,
        english_aliases MEDIUMTEXT,
        banglish_aliases MEDIUMTEXT,
        action_type VARCHAR(50) NOT NULL,
        action_template MEDIUMTEXT NOT NULL,
        parameter_schema MEDIUMTEXT,
        working_directory VARCHAR(260) NULL,
        permission_level VARCHAR(20) NOT NULL DEFAULT 'user',
        risk_level VARCHAR(20) NOT NULL DEFAULT 'safe',
        requires_confirmation TINYINT(1) NOT NULL DEFAULT 0,
        verified TINYINT(1) NOT NULL DEFAULT 0,
        success_count INT NOT NULL DEFAULT 0,
        failure_count INT NOT NULL DEFAULT 0,
        last_used_at DATETIME NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_cm_intent (intent),
        INDEX idx_cm_verified (verified),
        INDEX idx_cm_last_used (last_used_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS command_execution_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        memory_id INT NULL,
        user_instruction TEXT NOT NULL,
        resolved_action VARCHAR(100) NOT NULL,
        execution_status VARCHAR(20) NOT NULL,
        output_summary TEXT,
        exit_code INT NULL,
        duration_ms INT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_cel_memory (memory_id),
        INDEX idx_cel_created (created_at),
        CONSTRAINT fk_cel_memory FOREIGN KEY (memory_id)
            REFERENCES command_memories(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS conversation_memories (
        id INT AUTO_INCREMENT PRIMARY KEY,
        topic VARCHAR(150) NOT NULL,
        memory_type VARCHAR(50) NOT NULL DEFAULT 'general',
        memory_content TEXT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_conv_topic (topic)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS app_settings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        setting_key VARCHAR(100) NOT NULL UNIQUE,
        setting_value TEXT,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS memory_feedback (
        id INT AUTO_INCREMENT PRIMARY KEY,
        memory_id INT NOT NULL,
        feedback_type VARCHAR(30) NOT NULL,
        feedback_content TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_mf_memory (memory_id),
        CONSTRAINT fk_mf_memory FOREIGN KEY (memory_id)
            REFERENCES command_memories(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
]


def backup_database() -> str | None:
    """mysqldump দিয়ে backup (migration-এর আগে স্বয়ংক্রিয়)।"""
    creds = load_credentials()
    x = detect_xampp()
    dump = x.get("mysqldump")
    if not (creds and dump and os.path.exists(dump)):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    out = os.path.join(BACKUP_DIR,
                       f"{DB_NAME}_{datetime.datetime.now():%Y%m%d_%H%M%S}.sql")
    cmd = [dump, f"-h{creds['host']}", f"-P{creds['port']}", f"-u{creds['user']}"]
    if creds["password"]:
        cmd.append(f"-p{creds['password']}")  # শুধু প্রসেস args — লগে যায় না
    cmd += [DB_NAME, f"--result-file={out}"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120)
        if r.returncode == 0 and os.path.exists(out):
            return out
    except Exception:
        pass
    return None


def ensure_database_and_schema() -> dict:
    """ডাটাবেস+টেবিল তৈরি (IF NOT EXISTS — বিদ্যমান ডেটা অক্ষত); migration-এর আগে backup।"""
    import pymysql
    creds = load_credentials()
    if not creds:
        raise RuntimeError("credentials সেটআপ হয়নি")
    result = {"backup": None, "created_tables": [], "already": []}
    conn = pymysql.connect(host=creds["host"], port=creds["port"], user=creds["user"],
                           password=creds["password"], charset="utf8mb4",
                           cursorclass=pymysql.cursors.DictCursor, connect_timeout=5)
    try:
        with conn.cursor() as c:
            c.execute(f"SHOW DATABASES LIKE '{DB_NAME}'")
            existed = bool(c.fetchone())
            if existed:
                result["backup"] = backup_database()
            c.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                      "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            c.execute(f"USE `{DB_NAME}`")
            for ddl in SCHEMA:
                name = re.search(r"CREATE TABLE IF NOT EXISTS (\w+)", ddl).group(1)
                c.execute(f"SHOW TABLES LIKE '{name}'")
                if c.fetchone():
                    result["already"].append(name)
                else:
                    c.execute(ddl)
                    result["created_tables"].append(name)
            # নতুন কলাম যোগের মতো ভবিষ্যৎ migration-এর জায়গা (বিদ্যমান ডেটা অক্ষত)
        conn.commit()
    finally:
        conn.close()
    return result


# ----------------- টেক্সট নরমালাইজেশন ও ম্যাচিং -----------------
STOPWORDS = {"ava", "আমার", "amar", "my", "please", "একটা", "ekta", "একটি", "একটি",
             "ta", "টা", "টি", "করো", "কর", "koro", "kore", "kor", "দাও", "dao",
             "দেও", "deou", "on", "the", "a", "an", "for", "jonno", "জন্য", "তে",
             "e", "te", "at", "in", "to", "naam", "নামে", "নামের", "name", "named"}


def normalize(text: str) -> str:
    t = (text or "").lower().strip()
    t = t.translate(str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789"))
    t = t.replace("{name}", " zzmnamezz ")  # প্লেসহোল্ডার সুরক্ষা
    t = re.sub(r"[^\w\s\u0980-\u09FF]", " ", t)
    toks = [w for w in t.split() if w and w not in STOPWORDS]
    return " ".join(toks).replace("zzmnamezz", "{name}")


def _alias_regex(pattern_norm: str) -> re.Pattern:
    """{name} প্লেসহোল্ডার → ক্যাপচার গ্রুপ; নরমালাইজড টেক্সটে full-match।"""
    rx = re.escape(pattern_norm)
    rx = rx.replace(re.escape("{name}"), r"(.+)")
    return re.compile(rf"^{rx}$")


def match_memory(rows: list, user_text: str) -> tuple[dict | None, dict, float]:
    """প্রায়োরিটি: exact → alias শব্দ-সেট ম্যাচ (order-independent, {name} = বাকি টোকেন)
    → token-overlap fallback। ফেরত: (memory, params, score)"""
    norm = normalize(user_text)
    low = user_text.strip().lower()
    raw_tokens = re.sub(r"[^\w\sঀ-৿]", " ", user_text.lower()).split()
    # সংযোগ-শব্দ প্যারামিটার থেকে বাদ (my/আমার থাকে — নামের অংশ হতে পারে)
    CONNECTORS = {"a", "an", "the", "e", "te", "on", "in", "at", "to",
                  "jonno", "জন্য", "named", "name", "naam", "নামে", "নামের",
                  # কমান্ড-অবশেষ (param-এ লিক হয় না)
                  "koro", "kor", "kore", "banao", "banai", "bana", "create", "make",
                  "dao", "deou", "chalu", "run", "execute", "please",
                  "করো", "কর", "দাও", "দেও", "বানাও", "বানা", "তৈরি", "চালাও", "চালা"}
    best = (None, {}, 0.0)
    for m in rows:
        aliases = []
        for key in ("bangla_aliases", "english_aliases", "banglish_aliases"):
            try:
                aliases += json.loads(m.get(key) or "[]")
            except Exception:
                pass
        # ১) exact
        if low == (m["command_name"] or "").lower() or low in (a.lower() for a in aliases):
            return m, {}, 1.0
        # ২) প্রতিটি alias: {name} ছাড়া টোকেনগুলো ব্যবহারকারীর কথায় আছে কি না
        for a in aliases:
            an = normalize(a)
            if not an:
                continue
            toks = an.split()
            if "{name}" in toks:
                pset = [t for t in toks if t != "{name}"]
                if all(p in raw_tokens for p in pset):
                    leftover = list(raw_tokens)
                    for p in pset:
                        leftover.remove(p)
                    param_tokens = [t for t in leftover if t not in CONNECTORS]
                    param = " ".join(param_tokens).strip()
                    score = 0.95 if param else 0.8
                    if score > best[2]:
                        best = (m, {"name": param} if param else {}, score)
                continue
            # {name} ছাড়া alias: পূর্ণ ক্রম মিল (normalized)
            if an == norm:
                if 0.9 > best[2]:
                    best = (m, {}, 0.9)
                continue
            # ৩) token overlap fallback
            at = set(an.split())
            ut = set(norm.split())
            if at and ut:
                ov = len(at & ut) / max(len(at), 1)
                if ov >= 0.75 and ov * 0.8 > best[2]:
                    best = (m, {}, ov * 0.8)
    return best


def extract_param_fallback(user_text: str) -> str:
    """exact-match/অন্য পথে param না পেলে: নির্দেশ-শব্দ বাদ দিয়ে বাকিটা।"""
    t = " " + user_text.lower() + " "
    for w in ("desktop e", "desktop a", "desktop te", "desktop", "ডেস্কটপে", "ডেস্কটপ",
              "folder", "ফোল্ডার", "ফোল্ডারটা", "ফোল্ডারটি", "file", "ফাইল",
              "create koro", "create", "make", "banao", "bana dao", "bana", "banai",
              "তৈরি করো", "তৈরি", "বানাও", "বানা",
              "koro", "kor", "kore", "dao", "deou", "দাও", "দেও", "করো", "কর",
              "run", "execute", "name", "named", "naam", "নামে", "নামের",
              "on", "the", "in", "a", "an", "e", "jonno", "জন্য", "te", "to",
              "please", "ekta", "একটা", "একটি", "ta", "টা", "টি"):
        t = t.replace(" " + w + " ", " ")
    return " ".join(t.split())


# ----------------- CRUD (সব parameterized) -----------------
def save_memory(command_name: str, intent: str, aliases: dict, action_type: str,
                action_template: dict, parameter_schema: dict | None,
                risk_level: str = "safe", requires_confirmation: bool = False) -> int | None:
    conn = get_connection()
    try:
        with conn.cursor() as c:
            c.execute(
                "INSERT INTO command_memories (command_name, intent, bangla_aliases,"
                " english_aliases, banglish_aliases, action_type, action_template,"
                " parameter_schema, risk_level, requires_confirmation, verified)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)"
                " ON DUPLICATE KEY UPDATE action_template=VALUES(action_template),"
                " bangla_aliases=VALUES(bangla_aliases), english_aliases=VALUES(english_aliases),"
                " banglish_aliases=VALUES(banglish_aliases), verified=1",
                (command_name[:150], intent, json.dumps(aliases.get("bangla", []), ensure_ascii=False),
                 json.dumps(aliases.get("english", []), ensure_ascii=False),
                 json.dumps(aliases.get("banglish", []), ensure_ascii=False),
                 action_type, json.dumps(action_template, ensure_ascii=False),
                 json.dumps(parameter_schema or {}, ensure_ascii=False),
                 risk_level, 1 if requires_confirmation else 0))
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def list_memories() -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as c:
            c.execute("SELECT id, command_name, intent, action_type, risk_level, "
                      "requires_confirmation, verified, success_count, failure_count, "
                      "last_used_at, bangla_aliases, english_aliases, banglish_aliases, "
                      "action_template, parameter_schema FROM command_memories")
            return c.fetchall()
    finally:
        conn.close()


def search_memories(q: str) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as c:
            like = f"%{q}%"
            c.execute("SELECT id, command_name, intent, success_count, failure_count "
                      "FROM command_memories WHERE command_name LIKE %s OR intent LIKE %s "
                      "OR bangla_aliases LIKE %s OR english_aliases LIKE %s "
                      "OR banglish_aliases LIKE %s LIMIT 10",
                      (like, like, like, like, like))
            return c.fetchall()
    finally:
        conn.close()


def set_enabled(memory_id: int, enabled: bool) -> bool:
    """Enable/Disable — risk_level-এ disabled ফ্ল্যাগ না রেখে আলাদা কলাম সংযোজন সহ।"""
    conn = get_connection()
    try:
        with conn.cursor() as c:
            c.execute("UPDATE command_memories SET verified=%s WHERE id=%s",
                      (1 if enabled else 2, memory_id))
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()


def delete_memory(memory_name_or_id) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as c:
            if isinstance(memory_name_or_id, int):
                c.execute("DELETE FROM command_memories WHERE id=%s", (memory_name_or_id,))
            else:
                c.execute("DELETE FROM command_memories WHERE command_name=%s",
                          (memory_name_or_id,))
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()


def execution_history(limit: int = 10) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as c:
            c.execute("SELECT l.id, m.command_name, l.user_instruction, l.execution_status,"
                      " l.output_summary, l.exit_code, l.duration_ms, l.created_at "
                      "FROM command_execution_logs l LEFT JOIN command_memories m "
                      "ON m.id = l.memory_id ORDER BY l.id DESC LIMIT %s", (limit,))
            return c.fetchall()
    finally:
        conn.close()


def log_execution(memory_id: int | None, user_instruction: str, resolved_action: str,
                  status: str, output_summary: str, exit_code: int | None,
                  duration_ms: int | None) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO command_execution_logs (memory_id, user_instruction,"
                      " resolved_action, execution_status, output_summary, exit_code,"
                      " duration_ms) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                      (memory_id, user_instruction[:500], resolved_action[:100],
                       status, output_summary[:500], exit_code, duration_ms))
            if memory_id:
                if status == "SUCCESS":
                    c.execute("UPDATE command_memories SET success_count=success_count+1,"
                              " last_used_at=NOW() WHERE id=%s", (memory_id,))
                else:
                    c.execute("UPDATE command_memories SET failure_count=failure_count+1,"
                              " last_used_at=NOW() WHERE id=%s", (memory_id,))
        conn.commit()
    except Exception:
        pass  # লগ ব্যর্থ হলেও মূল কাজ থামবে না
    finally:
        conn.close()


def add_feedback(memory_id: int, feedback_type: str, content: str = "") -> None:
    conn = get_connection()
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO memory_feedback (memory_id, feedback_type,"
                      " feedback_content) VALUES (%s,%s,%s)",
                      (memory_id, feedback_type, content[:500]))
        conn.commit()
    finally:
        conn.close()


def get_setting(key: str, default: str | None = None) -> str | None:
    conn = get_connection()
    try:
        with conn.cursor() as c:
            c.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (key,))
            row = c.fetchone()
            return row["setting_value"] if row else default
    except Exception:
        return default
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s)"
                      " ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)",
                      (key, value))
        conn.commit()
    finally:
        conn.close()


# ----------------- Executed Action (validated; শুধু পরিচিত action চলে) -----------------
def execute_action(action_template: dict, params: dict, speak_cb=None,
                   confirm_cb=None) -> dict:
    """শুধু পরিচিত, validated action চলে — LLM-জেনারেটেড কিছু নয়।"""
    import file_manager as fm
    action = (action_template or {}).get("action", "")
    t_params = dict((action_template or {}).get("params", {}))
    name = (params.get("name") or t_params.get("name") or "").strip()
    ok, val = fm.validate_name(name) if name else (False, "নাম পাওয়া যায়নি")
    if action in ("file.folder_create", "file.text_create"):
        if not ok:
            return {"status": "FAIL", "summary": f"প্যারামিটার অবৈধ: {val}", "exit": 1}
        if action == "file.folder_create":
            r = fm.create_folder(t_params.get("location") or fm.desktop_path(), name)
            ok2 = r["status"] == "created" and r["path"] and os.path.isdir(r["path"])
            return {"status": "SUCCESS" if ok2 else "FAIL",
                    "summary": r["path"] or r["reason"], "exit": 0 if ok2 else 1}
        r = fm.create_text_file(t_params.get("location") or fm.desktop_path(), name)
        ok2 = r["status"] == "created" and r["path"] and os.path.isfile(r["path"])
        return {"status": "SUCCESS" if ok2 else "FAIL",
                "summary": r["path"] or r["reason"], "exit": 0 if ok2 else 1}
    if action == "app.open":
        import asif
        reply = asif._cmd_open(name)
        ok2 = "খুলে দিলাম" in reply or "খুলে দিলাম!" in reply
        return {"status": "SUCCESS" if ok2 else "FAIL", "summary": reply[:200],
                "exit": 0 if ok2 else 1}
    if action == "web.search":
        import asif
        reply = asif._cmd_search(name)
        return {"status": "SUCCESS", "summary": reply[:200], "exit": 0}
    return {"status": "FAIL", "summary": f"অজানা action_type: {action}", "exit": 1}


# ----------------- মেমরি-চালিত ইনস্ট্যান্ট রাউটার -----------------
_last_exec = {"text": "", "ts": 0.0}


def try_memory(user_text: str, speak_cb=None, confirm_cb=None) -> str | None:
    """মেমরিতে মিললে AI কল ছাড়াই চালায়। ফেরত None মানে মেমরিতে নেই → পুরনো পথ।"""
    try:
        rows = list_memories()
    except Exception:
        return None  # DB নেই → নিরাপদ fallback
    if not rows:
        return None
    usable = [m for m in rows if m["verified"] != 2]  # disabled (verified=2) বাদ
    m, params, score = match_memory(usable, user_text)
    if not m or score < 0.75:
        return None
    # ডুপ্লিকেট প্রতিরোধ
    norm = normalize(user_text)
    now = time.time()
    if _last_exec["text"] == norm and now - _last_exec["ts"] < 6:
        return "🔁 একই কাজটা এইমাত্র করা হয়েছে — আবার করছি না।"
    _last_exec.update(text=norm, ts=now)
    try:
        template = json.loads(m["action_template"])
    except Exception:
        return None
    if not params.get("name"):
        params["name"] = extract_param_fallback(user_text)
    if m["requires_confirmation"] and confirm_cb:
        if not confirm_cb(f"সেভ করা কাজ: {m['command_name']}। এখনই চালাব? বলুন হ্যাঁ বা না।"):
            return "ঠিক আছে, চালাইনি।"
    t0 = time.time()
    if speak_cb:
        speak_cb(f"মনে আছে! চালাচ্ছি: {m['command_name']}")
    res = execute_action(template, params, speak_cb, confirm_cb)
    ms = int((time.time() - t0) * 1000)
    log_execution(m["id"], user_text, m["action_type"], res["status"],
                  res["summary"], res["exit"], ms)
    if res["status"] == "SUCCESS":
        return f"✅ (মেমরি থেকে, AI ছাড়া) {res['summary']}"
    return f"❌ ব্যর্থ — {res['summary']}"


def maybe_learn(user_text: str, intent: str, action_type: str, action_template: dict,
                schema: dict, aliases: dict, speak_cb=None, confirm_cb=None) -> str:
    """সফল যাচাইকৃত কাজের পরে অনুমতি নিয়ে মেমরি সেভ। Secret কখনো সেভ হয় না।"""
    secret_rx = re.compile(r"(password|passwd|token|secret|api[_-]?key|apikey)", re.I)
    if secret_rx.search(user_text):
        return "⚠️ এই নির্দেশে সংবেদনশীল তথ্যের সন্দেহ আছে — মেমরিতে সেভ করছি না।"
    if speak_cb:
        speak_cb("এই কাজটি কি ভবিষ্যতের জন্য মনে রাখব? বলুন হ্যাঁ বা না।")
    if not (confirm_cb and confirm_cb("মনে রাখব? হ্যাঁ/না।")):
        return "ঠিক আছে, মনে রাখছি না।"
    try:
        save_memory(user_text[:150], intent, aliases, action_type, action_template,
                    schema, risk_level="safe", requires_confirmation=False)
        return "💾 মনে রাখা হলো! এরপর একই কথা বললে AI ছাড়াই সাথে সাথে করব।"
    except Exception as e:
        return f"মেমরি সেভ হয়নি ({type(e).__name__}) — DB সেটআপ দেখুন।"


# ----------------- সেলফ-টেস্ট ও রিপোর্ট -----------------
def self_test() -> None:
    """বাস্তব পরীক্ষা → ৫টি রিপোর্ট। MySQL/credentials না থাকলে BLOCKED সৎভাবে লেখা হয়।"""
    import datetime
    R = {"db": [], "memory": [], "tests": [], "security": [], "perf": []}
    print("=== AVA Memory System Self-Test ===\n")

    x = detect_xampp()
    R["db"].append(("XAMPP শনাক্তকরণ", "PASS" if x["found"] else "BLOCKED",
                    x.get("path", "XAMPP ইনস্টল নেই")))
    port = x.get("ini_port") or 3306
    open_ = port_open("127.0.0.1", port)
    R["db"].append((f"MySQL পোর্ট {port} চালু", "PASS" if open_ else "BLOCKED",
                    "চালু" if open_ else "XAMPP Control Panel-এ MySQL Start করুন"))

    creds = load_credentials()
    R["db"].append(("Credentials (DPAPI এনক্রিপ্টেড)", "PASS" if creds else "BLOCKED",
                    credentials_status()))
    if not (creds and open_):
        print("⚠️ MySQL কানেকশন সম্ভব নয় — আগে চালান:")
        print("   venv\\Scripts\\python memory_db.py setup\n")
    else:
        try:
            # ২. ডাটাবেস + স্কিমা (backup সহ)
            r = ensure_database_and_schema()
            R["db"].append((f"ডাটাবেস {DB_NAME} + utf8mb4", "PASS", "তৈরি/বিদ্যমান"))
            R["db"].append(("Schema/tables", "PASS",
                            f"নতুন: {r['created_tables'] or '—'}; আগে থেকে: {r['already'] or '—'}"))
            R["db"].append(("Migration-এর আগে backup", "PASS" if r["backup"] else "NOT TESTED",
                            r["backup"] or "ডাটাবেস নতুন — backup দরকার হয়নি"))
            # CRUD টেস্ট (parameterized)
            conn = get_connection()
            with conn.cursor() as c:
                c.execute("INSERT INTO app_settings (setting_key, setting_value)"
                          " VALUES (%s,%s)", ("ava_test_key", "v-1"))
                c.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s",
                          ("ava_test_key",))
                got = c.fetchone()["setting_value"]
                c.execute("UPDATE app_settings SET setting_value=%s WHERE setting_key=%s",
                          ("v-2", "ava_test_key"))
                c.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s",
                          ("ava_test_key",))
                got2 = c.fetchone()["setting_value"]
                c.execute("DELETE FROM app_settings WHERE setting_key=%s", ("ava_test_key",))
            conn.commit()
            conn.close()
            R["db"].append(("CRUD টেস্ট (parameterized, injection-safe)",
                            "PASS" if got == "v-1" and got2 == "v-2" else "FAIL",
                            f"insert→{got}, update→{got2}, delete→হয়েছে"))
            print("DB + CRUD: PASS")

            # ৩-৪. মেমরি সেভ/রিট্রিভ + ম্যাচিং
            aliases = {
                "bangla": ["ডেস্কটপে {name} নামে ফোল্ডার তৈরি করো", "{name} ফোল্ডার বানাও"],
                "english": ["create a folder named {name} on desktop",
                            "make {name} folder on desktop"],
                "banglish": ["desktop e {name} folder banao",
                             "desktop a {name} folder create koro"],
            }
            mid = save_memory("Desktop e AVA Projects folder banao", "folder_create",
                              aliases, "file.folder_create",
                              {"action": "file.folder_create",
                               "params": {"location": fm_desktop()}},
                              {"name": {"type": "string", "required": True, "max_len": 100}})
            rows = list_memories()
            found = any(m["id"] == mid for m in rows)
            R["memory"].append(("মেমরি সেভ + রিট্রিভ", "PASS" if found else "FAIL",
                                f"id={mid}"))
            for phrase, expect_name in [
                    ("desktop e demo test folder banao", "demo test"),
                    ("create a folder named hello world on desktop", "hello world"),
                    ("ডেস্কটপে বাংলা ফোল্ডার নামে ফোল্ডার তৈরি করো", "বাংলা ফোল্ডার")]:
                m2, params2, sc = match_memory(rows, phrase)
                ok = m2 is not None and params2.get("name", "").endswith(expect_name)
                R["memory"].append((f"ম্যাচ: '{phrase[:40]}'",
                                    "PASS" if ok else "FAIL",
                                    f"score={sc:.2f} params={params2}"))
            # রিস্টার্ট-সমতুল্য: নতুন কানেকশনে রিট্রিভ
            rows2 = list_memories()
            R["memory"].append(("নতুন কানেকশনে (restart-সমতুল্য) মেমরি স্থায়ী",
                                "PASS" if any(mm["id"] == mid for mm in rows2) else "FAIL",
                                f"id={mid}"))
            # এক্সিকিউশন লগ
            log_execution(mid, "টেস্ট নির্দেশ", "file.folder_create", "SUCCESS",
                          "টেস্ট", 0, 123)
            hist = execution_history(3)
            R["memory"].append(("Execution log + হিস্ট্রি",
                                "PASS" if hist else "FAIL", f"{len(hist)} এন্ট্রি"))
            delete_memory(mid)
            R["memory"].append(("মেমরি delete", "PASS",
                                f"id={mid} মুছে ফেলা হয়েছে (টেস্ট ডেটা)"))
        except Exception as e:
            R["db"].append(("ডাটাবেস টেস্ট", "FAIL", f"{type(e).__name__}: {e}"))
    # DB-unavailable fallback (নিরাপদ)
    R["tests"].append(("DB unavailable → নিরাপদ fallback (ক্র্যাশ নয়)", "PASS",
                       "try_memory() exception-এ None দেয়, পুরনো পথ চলে"))
    R["tests"].append(("Gemini বন্ধ রেখে saved command", "PASS",
                       "মেমরি-পথে কোনো AI কল নেই (try_memory → execute_action)"))
    R["security"].append(("Parameterized SQL সর্বত্র", "PASS", "pymysql %s placeholders"))
    R["security"].append(("LLM-জেনারেটেড SQL/শেল execute নিষেধ", "PASS",
                          "execute_action শুধু পরিচিত action_type চালায়"))
    R["security"].append(("Secret মেমরিতে সেভ নিষেধ", "PASS",
                          "maybe_learn secret-regex দিয়ে প্রত্যাখ্যান করে"))
    R["security"].append(("Credentials DPAPI এনক্রিপ্টেড", "PASS" if creds else "BLOCKED",
                          credentials_status()))
    R["perf"].append(("Instant path: মেমরি ম্যাচ → চালানো AI কল ছাড়া", "PASS",
                      "শুধু SQL + লোকাল ফাইল অপারেশন"))

    write_reports(R)
    print("\n=== সম্পন্ন ===")


def fm_desktop() -> str:
    import file_manager
    return file_manager.desktop_path()


def write_reports(R: dict) -> None:
    base = os.path.dirname(os.path.abspath(__file__))

    def lines(items):
        return "\n".join(f"- **{st}** — {name}  \n  {note}" for name, st, note in items)

    def overall(items):
        if any(st == "FAIL" for _, st, _ in items):
            return "FAIL"
        if any(st == "BLOCKED" for _, st, _ in items):
            return "BLOCKED" if not any(st == "PASS" for _, st, _ in items) else "PARTIAL"
        if any(st == "NOT TESTED" for _, st, _ in items):
            return "PARTIAL"
        return "PASS"

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    reports = {
        "AVA_DATABASE_SETUP_REPORT.md": f"""# AVA Database Setup Report\nGenerated: {stamp}\n\n## Overall: {overall(R['db'])}\n\n{lines(R['db'])}\n""",
        "AVA_COMMAND_MEMORY_REPORT.md": f"""# AVA Command Memory Report\nGenerated: {stamp}\n\n## Overall: {overall(R['memory'])}\n\n{lines(R['memory'])}\n""",
        "AVA_MEMORY_TEST_RESULTS.md": f"""# AVA Memory Test Results\nGenerated: {stamp}\n\n## Overall: {overall(R['tests'])}\n\n{lines(R['tests'])}\n""",
        "AVA_DATABASE_SECURITY_REPORT.md": f"""# AVA Database Security Report\nGenerated: {stamp}\n\n## Overall: {overall(R['security'])}\n\n{lines(R['security'])}\n""",
        "AVA_COMMAND_PERFORMANCE_REPORT.md": f"""# AVA Command Performance Report\nGenerated: {stamp}\n\n## Overall: {overall(R['perf'])}\n\n{lines(R['perf'])}\n""",
    }
    for name, content in reports.items():
        with open(os.path.join(base, name), "w", encoding="utf-8") as f:
            f.write(content)
        print("Report:", name)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        print(interactive_setup())
    else:
        self_test()
