# -*- coding: utf-8 -*-
"""identity.py — patch 3: dev_me প্রথমে, comp-first, নতুন dev শব্দ"""
src = open('identity.py', encoding='utf-8').read()
fixes = 0

# বর্তমান ব্লক রিপ্লেস (dev_me → dev_q → comp → dev → name)
old = ('    if dev and has_me and "আমি" in t_norm.split() + ["ami"]:\n'
       '        return "identity_developer_me"\n'
       '    dev_q = any(w in t_norm.split() for w in ("কে", "kar", "কার")) \\\n'
       '        or "who" in t_norm or " baniy" in t_norm or "toiri kor" in t_norm \\\n'
       '        or "created" in t_norm or "made" in t_norm or "built" in t_norm\n'
       '    if comp and not dev_q and (has_you or has_me):\n'
       '        return "identity_company"\n'
       '    if dev and (has_you or dev_q):\n'
       '        return "identity_developer"\n'
       '    name_any = any(w in t_norm.split() for w in ("naam", "nam"))')
new = ('    if dev and has_me:  # "আমি কি তোমাকে বানিয়েছি?" — ব্যবহারকারী দাবি করলে\n'
       '        return "identity_developer_me"\n'
       '    if comp and (has_you or has_me or "who" in t_norm or "কী" in t_norm or "ki" in t_norm):\n'
       '        return "identity_company"\n'
       '    dev_q = any(w in t_norm.split() for w in ("কে", "kar", "কার")) \\\n'
       '        or "who" in t_norm or "created" in t_norm or "made" in t_norm \\\n'
       '        or "built" in t_norm or "maker" in t_norm\n'
       '    if dev and (has_you or dev_q):\n'
       '        return "identity_developer"\n'
       '    name_any = any(w in t_norm.split() for w in ("naam", "nam"))')
if old in src:
    src = src.replace(old, new, 1); fixes += 1

# dev শব্দতালিকায় বাংলা ভ্যারিয়েন্ট
old2 = '"banaise", "banaiase"))'
new2 = '"banaise", "banaiase", "বানায়", "স্রষ্টা", "বানিয়েছি", "বানিয়েছেন"))'
if old2 in src:
    src = src.replace(old2, new2, 1); fixes += 1

open('identity.py', 'w', encoding='utf-8').write(src)
print("patch3 fixes:", fixes)
