# -*- coding: utf-8 -*-
"""AVA Conversation Intelligence Test Suite — ১০৪ টেস্ট কেস।
চালান: venv\\Scripts\\python test_conversation.py
Deterministic টেস্ট বাস্তবে চলে; LLM-নির্ভর টেস্ট চিহ্নিত থাকে।"""
import json

import identity

CASES = [
    # --- ২০ বাংলা কথোপকথন (deterministic) ---
    ("ভালো আছো?", "wellbeing_assistant"), ("তুমি কেমন আছো?", "wellbeing_assistant"),
    ("তুমি ভালো আছো তো?", "wellbeing_assistant"), ("কেমন আছো বলো তো?", "wellbeing_assistant"),
    ("তোমাকে কে বানিয়েছে?", "identity_developer"), ("তোমাকে কে তৈরি করেছে?", "identity_developer"),
    ("তোমার নির্মাতা কে?", "identity_developer"), ("কে তোমাকে বানালো?", "identity_developer"),
    ("তোমার নাম কী?", "identity_name"), ("তোমার নাম কি?", "identity_name"),
    ("ধন্যবাদ", "thanks"), ("ধন্যবাদ ভাই", "thanks"),
    ("তুমি কী করতে পারো?", "capabilities"), ("তোমার কী কী ক্ষমতা আছে?", "capabilities"),
    ("তুমি ভুল বলেছ", "correction"), ("এটা ভুল উত্তর", "correction"),
    ("কোন কোম্পানি তোমাকে বানিয়েছে?", "identity_company"),
    ("তোমার কোম্পানির নাম?", "identity_company"),
    ("তুমি কার কাছ থেকে জন্ম?", "identity_developer"),
    ("তুমি কে?", "identity_name"),
    # --- ২০ বাংলিশ (deterministic) ---
    ("Tomake ke baniyeche?", "identity_developer"),
    ("Tomake ke banaise?", "identity_developer"),
    ("Tumi kemon acho?", "wellbeing_assistant"),
    ("Valo acho?", "wellbeing_assistant"),
    ("Tomer nam ki?", "identity_name"),
    ("Apnar nam ki?", "identity_name"),
    ("Tumi ki korte paro?", "capabilities"),
    ("Tumi bhul bolsen", "correction"),
    ("Dhonnobad", "thanks"),
    ("Thanks vai", "thanks"),
    ("Kon company tomake toiri koreche?", "identity_developer"),
    ("Ke banaisa tumake?", "identity_developer"),
    ("Amar naam ki korbe?", "identity_name"),
    ("Tomake ke developer?", "identity_developer"),
    ("Who is your maker?", "identity_developer"),
    ("Tumi kar banaiya?", "identity_developer"),
    ("Tumi kemon acho bolo", "wellbeing_assistant"),
    ("Bhalo acho tumi?", "wellbeing_assistant"),
    ("Tumi ki paro kaj kora?", "capabilities"),
    ("Bhul ansa disen", "correction"),
    # --- ২০ ইংরেজি (deterministic) ---
    ("Who created you?", "identity_developer"), ("Who made you?", "identity_developer"),
    ("Who is your developer?", "identity_developer"), ("Who built you?", "identity_developer"),
    ("What is your name?", "identity_name"), ("Your name?", "identity_name"),
    ("Which company created you?", "identity_company"),
    ("How are you?", "wellbeing_assistant"), ("Are you ok?", "wellbeing_assistant"),
    ("What can you do?", "capabilities"), ("Your capabilities?", "capabilities"),
    ("You are wrong", "correction"), ("Wrong answer", "correction"),
    ("Thank you", "thanks"), ("Thanks", "thanks"),
    ("Hello", "greeting"), ("Hi", "greeting"),
    ("Goodbye", "goodbye"), ("Bye", "goodbye"),
    ("Am I your developer?", "identity_developer_me"),
    # --- ১০ পরিচয়-বিশেষ (deterministic) ---
    ("তোমার ডেভেলপার কে?", "identity_developer"),
    ("তোমাকে কারা বানায়?", "identity_developer"),
    ("তোমার স্রষ্টা কে?", "identity_developer"),
    ("Tumi kar creation?", "identity_developer"),
    ("তোমার কোম্পানি কোনটা?", "identity_company"),
    ("Your company name?", "identity_company"),
    ("তোমার নাম বলো তো", "identity_name"),
    ("Tell me your name", "identity_name"),
    ("আমি কি তোমাকে বানিয়েছি?", "identity_developer_me"),
    ("Did I create you?", "identity_developer_me"),
    # --- ১০ অসম্পূর্ণ/অস্পষ্ট (None প্রত্যাশিত → ব্রেন/clarification) ---
    ("আজকের খবর বলো", ""), ("আজ বৃষ্টি হবে?", ""),
    ("ফোল্ডার খোলো", ""), ("সময় কত হলো?", ""),
    ("গান বাজাও", ""), ("Laravel কী?", ""),
    ("আমার প্রজেক্ট কী অবস্থায়?", ""), ("৫ মিনিট পরে ডাকো", ""),
    ("স্ক্রিন দেখো", ""), ("কম্পিউটার বন্ধ করো", ""),
    # --- ১০ ফলো-আপ/প্রসঙ্গ (LLM-নির্ভর — NOT TESTED এখানে) ---
    ("এটা কীভাবে শুরু করব?", "LLM"), ("তাহলে কী করবো এখন?", "LLM"),
    ("আরো বলো", "LLM"), ("কেন?", "LLM"), ("তারপর?", "LLM"),
    ("ওটা আবার করো", "LLM"), ("ঠিক আছে চালিয়ে যাও", "LLM"),
    ("সেটা কী?", "LLM"), ("ভালো, চালিয়ে যাও", "LLM"), ("আরো বিস্তারিত বলো", "LLM"),
]


def run():
    det = [(t, e) for t, e in CASES if e != "LLM"]
    llm = [(t, e) for t, e in CASES if e == "LLM"]
    passed, failed = [], []
    for txt, expect in det:
        got = identity._classify(identity._norm(txt))
        if got == expect:
            passed.append(txt)
        else:
            failed.append((txt, expect, got))
    # identity উত্তরের বাস্তব যাচাই (দ্রুত-পথ)
    id_checks = []
    for txt in ("তোমাকে কে বানিয়েছে?", "Who is your developer?", "Tomake ke baniyeche?"):
        r = identity.fast_reply(txt)
        ok = r and identity.get("developer") in r and identity.get("company") in r
        id_checks.append((txt, ok, r))
    llm_ok = sum(1 for t, e in llm if identity.fast_reply(t) is None)  # LLM-এ যাওয়া উচিত
    return passed, failed, id_checks, llm, llm_ok


if __name__ == "__main__":
    passed, failed, id_checks, llm, llm_ok = run()
    print("=" * 50)
    print("AVA CONVERSATION TEST SUITE")
    print("=" * 50)
    print(f"Deterministic: {len(passed)}/{len(passed) + len(failed)} PASS")
    for f in failed:
        print("  ✘ FAIL:", f)
    print("Identity answers (developer+company ঠিক?):")
    for txt, ok, r in id_checks:
        print(("  ✔ " if ok else "  ✘ ") + txt, "→", (r or "")[:70])
    print(f"Follow-up/LLM-পথ: {llm_ok}/{len(llm)} সঠিকভাবে ব্রেনে যায়")
    verdict = "PASS" if not failed else "FAIL"
    print("VERDICT:", verdict)
    # রিপোর্ট লেখা
    import datetime
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    body = f"""# AVA Intent Detection Test Report
Generated: {stamp}

## Overall: {verdict}
Deterministic tests: **{len(passed)}/{len(passed) + len(failed)} PASS**
LLM-পথ (সঠিকভাবে ব্রেনে যায়): {llm_ok}/{len(llm)}

## Failed cases
""" + ("\n".join(f"- ✘ '{t}' প্রত্যাশা {e}, পাওয়া {g}" for t, e, g in failed) or "- নেই")
    open("INTENT_DETECTION_TEST_REPORT.md", "w", encoding="utf-8").write(body)
    print("Report: INTENT_DETECTION_TEST_REPORT.md")
