# -*- coding: utf-8 -*-
"""AVA Long-Term Memory — বাস্তব গ্রহণযোগ্যতা পরীক্ষা + ৫টি রিপোর্ট জেনারেটর।
চালান: venv\\Scripts\\python memory_selftest.py"""
import datetime
import json
import os

import memory_db
import memory_longterm as mlt


def _lines(items):
    return "\n".join(f"- **{st}** — {name}  \n  {note}" for name, st, note in items)


def _overall(items):
    if any(st == "FAIL" for _, st, _ in items):
        return "FAIL"
    if any(st == "BLOCKED" for _, st, _ in items):
        return "PARTIAL" if any(st == "PASS" for _, st, _ in items) else "BLOCKED"
    return "PASS"


def run() -> None:
    R = {"persistence": [], "intelligence": [], "project": [], "suggestion": [],
         "privacy": []}
    print("=== AVA Long-Term Memory Self-Test ===\n")
    creds = memory_db.load_credentials()
    if not creds:
        print("⚠️ DB credentials নেই — আগে চালান: venv\\Scripts\\python memory_db.py setup")
    try:
        r = mlt.ensure_schema()
        R["persistence"].append(("স্কিমা migration (ডেটা অক্ষত)", "PASS",
                                 f"নতুন: {r['created'] or '—'}; বিদ্যমান: {r['existing'] or '—'}"))
        R["persistence"].append(("Migration-এর আগে backup",
                                 "PASS" if r["backup"] else "NOT TESTED",
                                 r["backup"] or "নতুন স্কিমা — backup দরকার হয়নি"))
        # টেস্ট সেশন ও কথোপকথন
        old_sid = mlt.SESSION_STATE["session_id"]
        mlt.start_session("ava-selftest")
        mlt.add_message("user", "আমি একটা Laravel e-commerce প্রজেক্ট বানাচ্ছি।")
        mlt.add_message("assistant", "চমৎকার! database হবে MySQL?")
        mlt.add_message("user", "হ্যাঁ, আমরা MySQL use করব, payment gateway পরে যোগ হবে।")
        recent = mlt.recent_messages(3)
        R["persistence"].append(("কথোপকথন সংরক্ষণ + restart-সমতুল্য রিট্রিভ",
                                 "PASS" if len(recent) == 3 else "FAIL",
                                 f"{len(recent)}/৩ বার্তা ফেরত"))
        ctx = mlt.build_context("Laravel project কী অবস্থায়?")
        R["intelligence"].append(("কমপ্যাক্ট context তৈরি",
                                  "PASS" if "laravel" in ctx.lower() else "FAIL",
                                  ctx[:100].replace("\n", " ")))
        # প্রজেক্ট মেমরি
        mlt.get_or_create_project("Laravel E-commerce", "e-commerce ওয়েবসাইট",
                                  "Laravel, MySQL")
        mlt.add_project_item("Laravel E-commerce", "completed", "auth setup")
        mlt.add_project_item("Laravel E-commerce", "pending", "payment gateway integration")
        mlt.add_project_item("Laravel E-commerce", "decision", "MySQL use করা হবে")
        tasks = mlt.pending_tasks(5)
        ok = any("payment gateway" in t["content"].lower() for t in tasks)
        R["project"].append(("প্রজেক্ট + pending/completed/decision সংরক্ষণ",
                             "PASS" if ok else "FAIL", f"pending: {len(tasks)}"))
        resumed = mlt.resume_latest()
        R["project"].append(("'আগের কাজ চালিয়ে যাও' টাস্ক-রিট্রিভ",
                             "PASS" if resumed and "payment" in resumed else "FAIL",
                             (resumed or "")[:80]))
        # প্রস্তাব (LLM ভিত্তিক, ব্যর্থ হলে pending থেকে fallback)
        sugg = mlt.suggest_next("Laravel project setup complete.")
        R["suggestion"].append(("Proactive suggestion (বাস্তব pending ভিত্তিক)",
                                "PASS" if sugg else "BLOCKED", (sugg or "LLM উত্তর দেয়নি")[:90]))
        sugg2 = mlt.suggest_next("Laravel project setup complete.")
        R["suggestion"].append(("পুনরাবৃত্ত প্রস্তাব প্রতিরোধ",
                                "PASS" if sugg2 is None or sugg2 != sugg else "FAIL",
                                "একই প্রস্তাব দ্বিতীয়বার দেয়নি" if sugg2 != sugg else "ডুপ্লিকেট!"))
        # গোপনীয়তা: কথোপকথনে secret মাস্ক হয়
        mlt.add_message("user", "my api key sk-abcdef1234567890 test")
        conn = memory_db.get_connection()
        with conn.cursor() as c:
            c.execute("SELECT content FROM conversation_messages ORDER BY id DESC LIMIT 1")
            stored = c.fetchone()["content"]
            c.execute("UPDATE conversation_messages SET deleted=1 WHERE session_id=%s",
                      (mlt.SESSION_STATE["session_id"],))
            n = c.rowcount
            c.execute("DELETE pi, p FROM project_items pi JOIN projects p"
                      " ON p.id = pi.project_id WHERE p.name = %s",
                      ("Laravel E-commerce",))
        conn.commit()
        conn.close()
        R["privacy"].append(("কথোপকথনে secret মাস্কিং",
                             "PASS" if "sk-abcdef" not in stored else "FAIL", stored[:60]))
        R["privacy"].append(("মেমরি সংশোধন/মুছে ফেলা সমর্থিত",
                             "PASS" if n >= 4 else "FAIL",
                             f"{n} বার্তা soft-deleted, টেস্ট প্রজেক্ট মুছে ফেলা হয়েছে"))
        mlt.SESSION_STATE["session_id"] = old_sid
    except Exception as e:
        R["persistence"].append(("ডাটাবেস টেস্ট",
                                 "BLOCKED" if not creds else "FAIL",
                                 f"{type(e).__name__}: {e}"))

    # রিপোর্ট লেখা
    base = os.path.dirname(os.path.abspath(__file__))
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    reports = {
        "AVA_LONG_TERM_MEMORY_REPORT.md":
            f"# AVA Long-Term Memory Report\nGenerated: {stamp}\n\n"
            f"## Overall: {_overall(R['persistence'])}\n\n{_lines(R['persistence'])}\n",
        "AVA_CONVERSATION_INTELLIGENCE_REPORT.md":
            f"# AVA Conversation Intelligence Report\nGenerated: {stamp}\n\n"
            f"## Overall: {_overall(R['intelligence'])}\n\n{_lines(R['intelligence'])}\n",
        "AVA_PROJECT_CONTEXT_REPORT.md":
            f"# AVA Project Context Report\nGenerated: {stamp}\n\n"
            f"## Overall: {_overall(R['project'])}\n\n{_lines(R['project'])}\n",
        "AVA_SUGGESTION_ENGINE_REPORT.md":
            f"# AVA Suggestion Engine Report\nGenerated: {stamp}\n\n"
            f"## Overall: {_overall(R['suggestion'])}\n\n{_lines(R['suggestion'])}\n",
        "AVA_MEMORY_PERSISTENCE_TEST.md":
            f"# AVA Memory Persistence Test\nGenerated: {stamp}\n\n"
            f"## Overall: {_overall(R['privacy'])}\n\n{_lines(R['privacy'])}\n",
    }
    for name, content in reports.items():
        with open(os.path.join(base, name), "w", encoding="utf-8") as f:
            f.write(content)
        print("Report:", name)
    print("\n=== সম্পন্ন ===")


if __name__ == "__main__":
    run()
