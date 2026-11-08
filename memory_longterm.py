# -*- coding: utf-8 -*-
"""
AVA — Human Intelligence & Long-Term Memory Engine
===================================================
- স্থায়ী কথোপকথন (sessions/messages/summaries) — রিস্টার্টেও টিকে
- স্বজ্ঞাত মেমরি রিট্রিভাল (compact context; পুরো হিস্ট্রি LLM-এ যায় না)
- স্বয়ংক্রিয় সারসংক্ষেপ (লম্বা কথোপকথনে; ডুপ্লিকেট এড়িয়ে)
- প্রজেক্ট ইন্টেলিজেন্স + টাস্ক লাইফসাইকেল (start/pause/resume/complete)
- Proactive suggestion engine (বাস্তব প্রজেক্ট-অবস্থা ভিত্তিক, পুনরাবৃত্তি নিষিদ্ধ)
- গোপনীয়তা: secret কখনো সংরক্ষণ নয়; parameterized SQL; backup সহ
"""
import datetime
import json
import os
import re

import memory_db
try:
    from terminal_engine import mask_secrets
except Exception:
    def mask_secrets(text: str) -> str:
        return re.sub(r"(password|passwd|token|secret|api[_-]?key)\s*[:=]\s*\S+", "***",
                      text or "", flags=re.I)
from memory_db import get_connection

SESSION_STATE = {"session_id": None, "msg_count": 0, "last_greeting": ""}

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS conversation_sessions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(200) NOT NULL DEFAULT 'কথোপকথন',
        started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_active_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_cs_active (last_active_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS conversation_messages (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        session_id INT NOT NULL,
        role VARCHAR(10) NOT NULL,
        content MEDIUMTEXT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_cm_session (session_id, created_at),
        FULLTEXT KEY ft_cm_content (content),
        CONSTRAINT fk_cmd_session FOREIGN KEY (session_id)
            REFERENCES conversation_sessions(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS conversation_summaries (
        id INT AUTO_INCREMENT PRIMARY KEY,
        session_id INT NOT NULL,
        summary MEDIUMTEXT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_csum_session (session_id),
        CONSTRAINT fk_csum_session FOREIGN KEY (session_id)
            REFERENCES conversation_sessions(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS user_preferences (
        id INT AUTO_INCREMENT PRIMARY KEY,
        pref_key VARCHAR(100) NOT NULL UNIQUE,
        pref_value TEXT NOT NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS projects (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(150) NOT NULL UNIQUE,
        description TEXT,
        tech_stack TEXT,
        status VARCHAR(30) NOT NULL DEFAULT 'active',
        next_recommended TEXT,
        last_activity DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_pr_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS project_items (
        id INT AUTO_INCREMENT PRIMARY KEY,
        project_id INT NOT NULL,
        item_type VARCHAR(20) NOT NULL,
        content TEXT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'open',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_pi_project (project_id, item_type, status),
        CONSTRAINT fk_pi_project FOREIGN KEY (project_id)
            REFERENCES projects(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS future_suggestions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        project_id INT NULL,
        suggestion TEXT NOT NULL,
        shown_count INT NOT NULL DEFAULT 0,
        last_shown_at DATETIME NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_fs_project (project_id, shown_count)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS approved_instructions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        instruction TEXT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
]


def ensure_schema() -> dict:
    """migration-safe স্কিমা আপগ্রেড — বিদ্যমান ডেটা অক্ষত; আগে backup।"""
    import pymysql
    backup = memory_db.backup_database()
    conn = pymysql.connect(host=memory_db.load_credentials()["host"],
                           port=memory_db.load_credentials()["port"],
                           user=memory_db.load_credentials()["user"],
                           password=memory_db.load_credentials()["password"],
                           charset="utf8mb4",
                           cursorclass=pymysql.cursors.DictCursor, connect_timeout=5)
    created, existing = [], []
    try:
        with conn.cursor() as c:
            c.execute(f"CREATE DATABASE IF NOT EXISTS `{memory_db.DB_NAME}` "
                      "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            c.execute(f"USE `{memory_db.DB_NAME}`")
            for ddl in SCHEMA:
                name = re.search(r"CREATE TABLE IF NOT EXISTS (\w+)", ddl).group(1)
                c.execute(f"SHOW TABLES LIKE '{name}'")
                (existing if c.fetchone() else created).append(name)
                if name not in existing:
                    c.execute(ddl)
            # সফট-ডিলিট কলাম (পুরনো DB-তে না থাকলে যোগ — ডেটা অক্ষত)
            c.execute("SHOW COLUMNS FROM conversation_messages LIKE 'deleted'")
            if not c.fetchone():
                c.execute("ALTER TABLE conversation_messages "
                          "ADD COLUMN deleted TINYINT(1) NOT NULL DEFAULT 0")
        conn.commit()
    finally:
        conn.close()
    return {"backup": backup, "created": created, "existing": existing}


# ----------------- সেশন ও বার্তা -----------------
def start_session(title: str = "কথোপকথন") -> int | None:
    try:
        conn = get_connection()
        with conn.cursor() as c:
            c.execute("INSERT INTO conversation_sessions (title) VALUES (%s)", (title[:200],))
        conn.commit()
        SESSION_STATE["session_id"] = c.lastrowid
        SESSION_STATE["msg_count"] = 0
        return SESSION_STATE["session_id"]
    except Exception:
        SESSION_STATE["session_id"] = None
        return None


def add_message(role: str, content: str) -> None:
    sid = SESSION_STATE.get("session_id")
    if not sid:
        return
    try:
        conn = get_connection()
        with conn.cursor() as c:
            c.execute("INSERT INTO conversation_messages (session_id, role, content)"
                      " VALUES (%s,%s,%s)", (sid, role, mask_secrets(content)[:4000]))
            c.execute("UPDATE conversation_sessions SET last_active_at=NOW() WHERE id=%s",
                      (sid,))
        conn.commit()
        conn.close()
        if role == "user":
            SESSION_STATE["msg_count"] += 1
    except Exception:
        pass


def recent_messages(n: int = 8) -> list[dict]:
    sid = SESSION_STATE.get("session_id")
    if not sid:
        return []
    try:
        conn = get_connection()
        with conn.cursor() as c:
            c.execute("SELECT role, content FROM conversation_messages WHERE session_id=%s"
                      " AND deleted=0 ORDER BY id DESC LIMIT %s", (sid, n))
            rows = c.fetchall()
        conn.close()
        return list(reversed(rows))
    except Exception:
        return []


def _llm(system: str, user: str, max_tokens: int = 300) -> str | None:
    try:
        import terminal_engine
        return terminal_engine._llm(system, user, max_tokens)
    except Exception:
        return None


# ----------------- স্বয়ংক্রিয় সারসংক্ষেপ -----------------
def maybe_summarize(threshold: int = 20) -> str | None:
    """সেশন লম্বা হলে পুরনো বার্তার সারসংক্ষেপ তৈরি (recent ছেড়ে)।"""
    sid = SESSION_STATE.get("session_id")
    if not sid or SESSION_STATE["msg_count"] < threshold:
        return None
    try:
        conn = get_connection()
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) AS n FROM conversation_messages WHERE session_id=%s"
                      " AND deleted=0", (sid,))
            total = c.fetchone()["n"]
            keep = 6
            c.execute("SELECT role, content FROM conversation_messages WHERE session_id=%s"
                      " AND deleted=0 ORDER BY id ASC", (sid,))
            rows = c.fetchall()
        conn.close()
        old = rows[:max(0, total - keep)]
        if len(old) < 6:
            return None
        text = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in old)[-3500:]
        summary = _llm(
            "তুমি কথোপকথনের সারসংক্ষেপক। সিদ্ধান্ত, প্রজেক্টের নাম, টেকনিক্যাল requirement, "
            "completed/pending অবস্থা হুবহু রাখো। ৫-৭ বাক্যে বাংলায় সারসংক্ষেপ দাও। "
            "নতুন তথ্য বানাবে না।",
            text, max_tokens=250)
        if not summary:
            return None
        norm_new = re.sub(r"\s+", " ", summary.lower())
        conn = get_connection()
        with conn.cursor() as c:
            c.execute("SELECT summary FROM conversation_summaries WHERE session_id=%s"
                      " ORDER BY id DESC LIMIT 3", (sid,))
            for row in c.fetchall():
                old_n = re.sub(r"\s+", " ", (row["summary"] or "").lower())
                # ডুপ্লিকেট/বিরোধপূর্ণ এড়ানো: বেশিরভাগ মিললে সংরক্ষণ নয়
                if norm_new[:120] and norm_new[:120] in old_n:
                    conn.close()
                    return "existing"
            c.execute("INSERT INTO conversation_summaries (session_id, summary)"
                      " VALUES (%s,%s)", (sid, mask_secrets(summary)))
        conn.commit()
        conn.close()
        return summary
    except Exception:
        return None


# ----------------- ইন্টেলিজেন্ট রিট্রিভাল → কমপ্যাক্ট প্রসঙ্গ -----------------
def _search_past(keyword_tokens: list, limit: int = 3) -> list[str]:
    sid = SESSION_STATE.get("session_id")
    try:
        conn = get_connection()
        with conn.cursor() as c:
            kw = " ".join(keyword_tokens[:6])
            out = []
            try:
                c.execute("SELECT content, session_id, MATCH(content) AS score"
                          " FROM conversation_messages WHERE deleted=0 AND session_id != %s"
                          " AND MATCH(content) AGAINST (%s IN NATURAL LANGUAGE MODE)"
                          " ORDER BY score DESC LIMIT %s", (sid or 0, kw, limit))
                for r in c.fetchall():
                    out.append(f"…{r['content'][:120]}…")
            except Exception:
                like = f"%{keyword_tokens[0]}%" if keyword_tokens else "%"
                c.execute("SELECT content FROM conversation_messages WHERE deleted=0"
                          " AND content LIKE %s ORDER BY id DESC LIMIT %s", (like, limit))
                out = [f"…{r['content'][:120]}…" for r in c.fetchall()]
        conn.close()
        return out
    except Exception:
        return []


def build_context(user_text: str, max_chars: int = 1800) -> str:
    """কমপ্যাক্ট প্রসঙ্গ: recent + প্রাসঙ্গিক পুরনো + প্রজেক্ট/টাস্ক + পছন্দ।"""
    parts: list[str] = []
    try:
        sid = SESSION_STATE.get("session_id")
        if sid:
            conn = get_connection()
            with conn.cursor() as c:
                c.execute("SELECT summary FROM conversation_summaries WHERE session_id=%s"
                          " ORDER BY id DESC LIMIT 1", (sid,))
                row = c.fetchone()
            conn.close()
            if row and row["summary"]:
                parts.append("[এই কথোপকথনের আগের সারসংক্ষেপ]\n" + row["summary"][:400])
        recent = recent_messages(6)
        if recent:
            parts.append("[সাম্প্রতিক কথোপকথন]\n" + "\n".join(
                f"{'ব্যবহারকারী' if m['role'] == 'user' else 'তুমি'}: {m['content'][:150]}"
                for m in recent))
        kws = [w for w in re.sub(r"[^\w\s\u0980-\u09FF]", " ", user_text.lower()).split()
               if len(w) > 3][:6]
        if kws:
            past = _search_past(kws)
            if past:
                parts.append("[অতীতে সংশ্লিষ্ট]\n" + "\n".join(past))
        conn = get_connection()
        with conn.cursor() as c:
            c.execute("SELECT name, status, next_recommended FROM projects"
                      " WHERE status='active' ORDER BY last_activity DESC LIMIT 2")
            projects = c.fetchall()
            c.execute("SELECT p.name, i.content FROM project_items i"
                      " JOIN projects p ON p.id = i.project_id"
                      " WHERE i.item_type='pending' AND i.status='open'"
                      " ORDER BY i.updated_at DESC LIMIT 3")
            pending = c.fetchall()
            c.execute("SELECT pref_key, pref_value FROM user_preferences LIMIT 5")
            prefs = c.fetchall()
            c.execute("SELECT content FROM project_items WHERE item_type='decision'"
                      " ORDER BY updated_at DESC LIMIT 2")
            decisions = c.fetchall()
        conn.close()
        for p in projects:
            parts.append(f"[সক্রিয় প্রজেক্ট] {p['name']} — অবস্থা: {p['status']}"
                         + (f", পরবর্তী: {p['next_recommended'][:80]}" if p["next_recommended"] else ""))
        for p in pending:
            parts.append(f"[অসমাপ্ত কাজ] {p['name']}: {p['content'][:80]}")
        for d in decisions:
            parts.append(f"[সিদ্ধান্ত] {d['content'][:100]}")
        if prefs:
            parts.append("[ব্যবহারকারীর পছন্দ] " + "; ".join(
                f"{r['pref_key']}: {r['pref_value'][:60]}" for r in prefs))
    except Exception:
        pass
    ctx = "\n".join(parts)
    return ctx[:max_chars]


def remember_preference(key: str, value: str) -> None:
    try:
        conn = get_connection()
        with conn.cursor() as c:
            c.execute("INSERT INTO user_preferences (pref_key, pref_value) VALUES (%s,%s)"
                      " ON DUPLICATE KEY UPDATE pref_value=VALUES(pref_value)",
                      (key[:100], mask_secrets(value)))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ----------------- প্রজেক্ট ইন্টেলিজেন্স ও টাস্ক লাইফসাইকেল -----------------
def get_or_create_project(name: str, description: str = "",
                          tech_stack: str = "") -> int | None:
    try:
        conn = get_connection()
        with conn.cursor() as c:
            c.execute("SELECT id FROM projects WHERE name=%s", (name[:150],))
            row = c.fetchone()
            if row:
                pid = row["id"]
                c.execute("UPDATE projects SET last_activity=NOW() WHERE id=%s", (pid,))
            else:
                c.execute("INSERT INTO projects (name, description, tech_stack)"
                          " VALUES (%s,%s,%s)",
                          (name[:150], mask_secrets(description), mask_secrets(tech_stack)))
                pid = c.lastrowid
        conn.commit()
        conn.close()
        return pid
    except Exception:
        return None


def add_project_item(project_name: str, item_type: str, content: str,
                     status: str = "open") -> int | None:
    pid = get_or_create_project(project_name)
    if not pid:
        return None
    try:
        conn = get_connection()
        with conn.cursor() as c:
            c.execute("INSERT INTO project_items (project_id, item_type, content, status)"
                      " VALUES (%s,%s,%s,%s)",
                      (pid, item_type, mask_secrets(content), status))
        conn.commit()
        conn.close()
        return c.lastrowid
    except Exception:
        return None


def pending_tasks(limit: int = 5) -> list[dict]:
    try:
        conn = get_connection()
        with conn.cursor() as c:
            c.execute("SELECT p.name, i.id, i.content, i.updated_at FROM project_items i"
                      " JOIN projects p ON p.id = i.project_id"
                      " WHERE i.item_type='pending' AND i.status IN ('open','paused')"
                      " ORDER BY i.updated_at DESC LIMIT %s", (limit,))
            rows = c.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def resume_latest() -> str | None:
    """'আগের কাজ চালিয়ে যাও' — সর্বশেষ অসমাপ্ত কাজ ফেরত।"""
    rows = pending_tasks(3)
    if not rows:
        return None
    top = rows[0]
    names = " | ".join(f"{r['name']}: {r['content'][:50]}" for r in rows[:3])
    return (f"আগের কাজ পেলাম — প্রজেক্ট '{top['name']}'-এ অসমাপ্ত: "
            f"{top['content'][:100]}। অন্য অসমাপ্ত: {names}")


def complete_item(project_name: str, content_match: str) -> str:
    """শুধু ব্যবহারকারীর স্বীকৃত যাচাইয়ের পরেই complete হয় (router নিশ্চিত করে)।"""
    try:
        conn = get_connection()
        with conn.cursor() as c:
            c.execute("SELECT i.id FROM project_items i JOIN projects p ON p.id=i.project_id"
                      " WHERE p.name LIKE %s AND i.content LIKE %s AND i.status='open'"
                      " ORDER BY i.updated_at DESC LIMIT 1",
                      (f"%{project_name}%", f"%{content_match}%"))
            row = c.fetchone()
            if not row:
                conn.close()
                return "এই নামে কোনো অসমাপ্ত কাজ পেলাম না।"
            c.execute("UPDATE project_items SET status='completed' WHERE id=%s",
                      (row["id"],))
        conn.commit()
        conn.close()
        return "কাজটি completed হিসেবে সংরক্ষিত হলো (যাচাই-স্বীকৃত)।"
    except Exception as e:
        return f"সম্পন্ন করা যায়নি: {type(e).__name__}"


# ----------------- Proactive Suggestion Engine -----------------
COMPLETION_PHRASES = ("শেষ", "সম্পন্ন", "complete", "completed", "done", "হয়ে গেছে",
                      "সেটআপ হয়ে", "কাজ শেষ", "হয়ে গেল", "শেষ হলো")

_sugg_cache = {"last": "", "ts": 0.0}


def is_completion(text: str) -> bool:
    tl = text.lower()
    return any(p in tl for p in COMPLETION_PHRASES)


def suggest_next(user_text: str) -> str | None:
    """বাস্তব প্রজেক্ট-অবস্থা ভিত্তিক পরবর্তী প্রস্তাব; একই প্রস্তাব বারবার নয়।"""
    try:
        tasks = pending_tasks(5)
        ctx = "\n".join(f"- প্রজেক্ট {t['name']}: pending — {t['content'][:80]}"
                        for t in tasks)
        user_note = user_text[:200]
        sugg = _llm(
            "তুমি একজন অভিজ্ঞ সহকারী। ব্যবহারকারী এইমাত্র কাজ শেষ করেছে। তার বাস্তব "
            "pending তালিকা দেখে পরবর্তী সবচেয়ে দরকারি একটি কাজের পরামর্শ দাও — বাংলায়, "
            "১-২ বাক্য, বন্ধুসুলভ। একই প্রস্তাব আগে দেওয়া হলে ভিন্নটা দাও। "
            "যা জানা নেই তা বানাবে না।",
            f"ব্যবহারকারী বলেছে: {user_note}\nবাস্তব pending:\n{ctx or '(খালি)'}",
            max_tokens=120)
        if not sugg:
            if tasks:  # নিরাপদ fallback: বাস্তব pending থেকে
                sugg = (f"ভালো! পরেরবার pending থেকেই শুরু করা যাবে — যেমন: "
                        f"{tasks[0]['name']}: {tasks[0]['content'][:60]}")
            else:
                return None
        sugg = mask_secrets(sugg.strip())
        now = datetime.datetime.now()
        if _sugg_cache["last"] == sugg and now.timestamp() - _sugg_cache["ts"] < 3600:
            return None  # পুনরাবৃত্ত প্রস্তাব নয়
        _sugg_cache.update(last=sugg, ts=now.timestamp())
        try:
            conn = get_connection()
            with conn.cursor() as c:
                c.execute("SELECT id, suggestion FROM future_suggestions"
                          " ORDER BY id DESC LIMIT 5")
                dup = [r["suggestion"] for r in c.fetchall()]
                if sugg in dup:
                    conn.close()
                    return None
                c.execute("INSERT INTO future_suggestions (suggestion) VALUES (%s)",
                          (sugg,))
                if tasks:
                    c.execute("INSERT INTO conversation_memories (topic, memory_type,"
                              " memory_content) VALUES (%s,%s,%s)",
                              (tasks[0]["name"], "suggestion", mask_secrets(sugg)))
            conn.commit()
            conn.close()
        except Exception:
            pass
        return sugg
    except Exception:
        return None


# ----------------- Memory Controls -----------------
def export_memory() -> str:
    try:
        conn = get_connection()
        out = {}
        with conn.cursor() as c:
            for table in ("conversation_sessions", "conversation_summaries",
                          "projects", "project_items", "user_preferences",
                          "future_suggestions", "approved_instructions",
                          "command_memories"):
                c.execute(f"SELECT * FROM {table}")
                out[table] = c.fetchall()
        conn.close()
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            f"ava_memory_export_{datetime.datetime.now():%Y%m%d_%H%M}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1, default=str)
        return path
    except Exception as e:
        return f"export ব্যর্থ: {e}"


def clear_history(confirm_done: bool) -> str:
    if not confirm_done:
        return "নিশ্চিত হননি — মুছিনি।"
    try:
        conn = get_connection()
        with conn.cursor() as c:
            c.execute("UPDATE conversation_messages SET deleted=1")
        conn.commit()
        conn.close()
        return "কথোপকথনের হিস্ট্রি soft-deleted হলো (backup/export না নিলে ফেরানো কঠিন)।"
    except Exception as e:
        return f"মুছতে সমস্যা: {e}"
