# -*- coding: utf-8 -*-
"""identity.py intent-fix patcher (one-shot)।"""
import io
import sys

src = open('identity.py', encoding='utf-8').read()
reps = []
ok = 0

# ১) name_any থেকে "tumi ke"/"who are you" সরাও (substring বাগ)
old = 'name_any = any(w in t_norm for w in ("naam", "nam", "tumi ke", "tumi ki", "who are you"))'
new = 'name_any = any(w in t_norm.split() for w in ("naam", "nam"))'
reps.append((old, new))

# ২) comp/dev অগ্রাধিকার: "কে/who" জিজ্ঞাসা হলে developer; "কোন কোম্পানি" হলে company
old2 = ('if comp and (has_you or has_me or "who" in t_norm or "কী" in t_norm or "ki" in t_norm):\n'
        '        return "identity_company"\n'
        '    if name or name_any:\n'
        '        return "identity_name"\n'
        '    if dev and has_me:\n'
        '        return "identity_developer_me"\n'
        '    if dev:\n'
        '        return "identity_developer"')
new2 = ('dev_q = any(w in t_norm.split() for w in ("কে", "kar", "কার")) '
        'or "who" in t_norm or " baniy" in t_norm or "toiri kor" in t_norm\n'
        'if comp and not dev_q and (has_you or has_me):\n'
        '        return "identity_company"\n'
        '    if name or name_any:\n'
        '        return "identity_name"\n'
        '    if dev and has_me:\n'
        '        return "identity_developer_me"\n'
        '    if dev:\n'
        '        return "identity_developer"')
reps.append((old2, new2))

# ৩) "তুমি কে?" সংক্ষিপ্ত → নাম (dev/wellbeing চেকের পরে)
old3 = 'if intent == "capabilities":'
new3 = ('if t_norm in ("তুমি কে", "তুমি কি", "tumi ke", "tumi ki", "who are you", "who r u"):\n'
        '        I = load()\n'
        '        return f"আমি {I[\'assistant_name\']} — {I[\'product_name\']}, তোমার Windows AI সহকারী।"\n'
        '    if intent == "capabilities":')
reps.append((old3, new3))

for o, n in reps:
    if o in src:
        src = src.replace(o, n, 1)
        ok += 1
    else:
        print("MISS:", o[:70].replace("\n", " "))

# ৪) greeting/biday word-boundary
src = src.replace(
    'any(w in t_norm for w in ("হ্যালো", "hello", "hi", "আসসালাম", "assalam", "সালাম")) and len(t_norm) < 20',
    'any(w in t_norm.split() for w in ("হ্যালো", "hello", "hi", "আসসালাম", "assalam", "সালাম")) and len(t_norm.split()) <= 3')
src = src.replace(
    'any(w in t_norm for w in ("বিদায়", "biday", "goodbye", "আবার হবে", "ভালো থেকো"))',
    'any(w in t_norm.split() for w in ("বিদায়", "biday", "goodbye", "bye", "আবার হবে", "ভালো থেকো"))')

open('identity.py', 'w', encoding='utf-8').write(src)
print("applied:", ok, "of", len(reps), "+ boundary fixes")
