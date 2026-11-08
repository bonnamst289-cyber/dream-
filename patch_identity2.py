# -*- coding: utf-8 -*-
"""identity.py — চূড়ান্ত intent ফিক্স প্যাচ"""
src = open('identity.py', encoding='utf-8').read()
fixes = 0

# ১) সংক্ষিপ্ত নাম-প্রশ্ন _classify-এ
old = '    name_any = any(w in t_norm.split() for w in ("naam", "nam"))\n    if name or name_any:'
new = ('    name_any = any(w in t_norm.split() for w in ("naam", "nam"))\n'
       '    if t_norm in ("তুমি কে", "তুমি কি", "tumi ke", "tumi ki",\n'
       '                  "who are you", "who r u", "tumi ke bolo", "তুমি কে বলো"):\n'
       '        return "identity_name"\n'
       '    if name or name_any:')
if old in src:
    src = src.replace(old, new, 1); fixes += 1

# ২) "Am I your developer?" আগে যাচাই
old2 = ('    if comp and (has_you or has_me or "who" in t_norm or "কী" in t_norm or "ki" in t_norm):\n'
        '        return "identity_company"\n'
        '    if dev and (has_you or "who" in t_norm or "কে" in t_norm.split() or "kar" in t_norm or "কে" in t_norm):\n'
        '        return "identity_developer"\n'
        '    if comp and (has_you or has_me or "who" in t_norm or "কী" in t_norm or "ki" in t_norm):\n'
        '        return "identity_company"\n'
        '    name_any = any(w in t_norm.split() for w in ("naam", "nam"))')
new2 = ('    if dev and has_me and "আমি" in t_norm.split() + ["ami"]:\n'
        '        return "identity_developer_me"\n'
        '    dev_q = any(w in t_norm.split() for w in ("কে", "kar", "কার")) \\\n'
        '        or "who" in t_norm or " baniy" in t_norm or "toiri kor" in t_norm \\\n'
        '        or "created" in t_norm or "made" in t_norm or "built" in t_norm\n'
        '    if comp and not dev_q and (has_you or has_me):\n'
        '        return "identity_company"\n'
        '    if dev and (has_you or dev_q):\n'
        '        return "identity_developer"\n'
        '    name_any = any(w in t_norm.split() for w in ("naam", "nam"))')
if old2 in src:
    src = src.replace(old2, new2, 1); fixes += 1

# ৩) greeting "hi" সংক্ষিপ্ত
old3 = 'any(w in t_norm for w in ("হ্যালো", "hello", "hi ", "আসসালাম", "assalam", "সালাম")) and len(t_norm) < 20'
new3 = ('any(w in t_norm.split() for w in ("হ্যালো", "hello", "hi", "আসসালাম", "assalam", "সালাম"))\n'
        '          and len(t_norm.split()) <= 3')
if old3 in src:
    src = src.replace(old3, new3, 1); fixes += 1

open('identity.py', 'w', encoding='utf-8').write(src)
print("fixes applied:", fixes)
