# -*- coding: utf-8 -*-
"""AVA Time & Date Intelligence — সিস্টেম ঘড়ি ভিত্তিক; কখনো বানায় না।
- লোকাল সময়/তারিখ/বার/মাস • বিশ্বের যেকোনো শহরের সময় (zoneinfo/tzdata)
- টাইমজোন রূপান্তর • কাল/আগামীকাল গণনা • রিমাইন্ডার (scheduler মডিউলে)"""
import datetime

try:
    from zoneinfo import ZoneInfo
    _ZI = True
except Exception:
    _ZI = False

# শহর → টাইমজোন (নরমালাইজড কিওয়ার্ড)
CITY_TZ = {
    "dhaka": "Asia/Dhaka", "ঢাকা": "Asia/Dhaka", "bangladesh": "Asia/Dhaka",
    "kushtia": "Asia/Dhaka", "কুষ্টিয়া": "Asia/Dhaka", "chittagong": "Asia/Dhaka",
    "london": "Europe/London", "লন্ডন": "Europe/London",
    "new york": "America/New_York", "নিউইয়র্ক": "America/New_York",
    "tokyo": "Asia/Tokyo", "টোকিও": "Asia/Tokyo", "japan": "Asia/Tokyo",
    "dubai": "Asia/Dubai", "দুবাই": "Asia/Dubai", "saudi": "Asia/Riyadh",
    "saudiarabia": "Asia/Riyadh", "kolkata": "Asia/Kolkata", "india": "Asia/Kolkata",
    "delhi": "Asia/Kolkata", "indonesia": "Asia/Jakarta", "malaysia": "Asia/Kuala_Lumpur",
    "singapore": "Asia/Singapore", "paris": "Europe/Paris", "berlin": "Europe/Berlin",
    "moscow": "Europe/Moscow", "beijing": "Asia/Shanghai", "china": "Asia/Shanghai",
    "sydney": "Australia/Sydney", "australia": "Australia/Sydney",
    "toronto": "America/Toronto", "canada": "America/Toronto",
    "losangeles": "America/Los_Angeles", "chicago": "America/Chicago",
}
BN_DAYS = ["সোমবার", "মঙ্গলবার", "বুধবার", "বৃহস্পতিবার", "শুক্রবার", "শনিবার", "রবিবার"]
BN_MONTHS = ["জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন", "জুলাই",
             "আগস্ট", "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর", "ডিসেম্বর"]


def _city_from(text: str) -> str | None:
    t = text.lower().replace(" ", "")
    for key in CITY_TZ:
        if key in t:
            return CITY_TZ[key]
    return None


def local_now() -> datetime.datetime:
    return datetime.datetime.now()  # সিস্টেম ঘড়ি (Asia/Dhaka সেট থাকলে সঠিক)


def local_time_str() -> str:
    n = local_now()
    return (f"এখন সময়: {n.strftime('%I:%M %p')}, "
            f"{BN_DAYS[n.weekday()]}, "
            f"{n.day} {BN_MONTHS[n.month-1]} {n.year}")


def city_time(tz_name: str) -> str:
    if not _ZI:
        return "এই সিস্টেমে টাইমজোন ডেটা নেই — 'pip install tzdata' দিলে কাজ করবে।"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        return f"'{tz_name}' টাইমজোন পাইনি।"
    n = datetime.datetime.now(tz)
    dhaka = datetime.datetime.now(ZoneInfo("Asia/Dhaka")) if _ZI else local_now()
    diff = int((n.utcoffset() - dhaka.utcoffset()).total_seconds() // 3600)
    diff_s = f" (ঢাকা থেকে {diff:+d} ঘণ্টা)" if diff else " (ঢাকার সমান)"
    return f"{tz_name.split('/')[-1].replace('_',' ')}-এ এখন {n.strftime('%I:%M %p')}{diff_s}"


def convert(hhmm: str, from_city: str, to_city: str) -> str:
    """'রাত ১১টা ঢাকার সময় লন্ডনে কয়টা' জাতীয় রূপান্তর।"""
    if not _ZI:
        return "টাইমজোন ডেটা নেই।"
    m = re.search(r"(\d{1,2})(?::(\d{2}))?", hhmm) if (re := __import__("re")) else None
    if not m:
        return "সময়টা বুঝতে পারিনি — যেমন বলুন: 'রাত ১১টা ঢাকার সময় লন্ডনে কয়টা'।"
    hh, mm = int(m.group(1)), int(m.group(2) or 0)
    f_tz = ZoneInfo(from_city or "Asia/Dhaka")
    t_tz = ZoneInfo(to_city or "Asia/Dhaka")
    src = datetime.datetime.now(f_tz).replace(hour=hh, minute=mm, second=0, microsecond=0)
    dst = src.astimezone(t_tz)
    return (f"{from_city.split('/')[-1]} সময়ের {src.strftime('%I:%M %p')} = "
            f"{to_city.split('/')[-1]}-এ {dst.strftime('%I:%M %p')}")


def yesterday_tomorrow(text: str) -> str:
    n = local_now()
    t = text.lower()
    if any(w in t for w in ("কাল", "tomorrow", "আগামীকাল")):
        d = n + datetime.timedelta(days=1)
        return f"আগামীকাল {BN_DAYS[d.weekday()]}, {d.day} {BN_MONTHS[d.month-1]} {d.year}"
    if any(w in t for w in ("গতকাল", "yesterday")):
        d = n - datetime.timedelta(days=1)
        return f"গতকাল ছিল {BN_DAYS[d.weekday()]}, {d.day} {BN_MONTHS[d.month-1]} {d.year}"
    if any(w in t for w in ("পরশু", "day after")):
        d = n + datetime.timedelta(days=2)
        return f"পরশু {BN_DAYS[d.weekday()]}, {d.day} {BN_MONTHS[d.month-1]} {d.year}"
    return ""


def handle(user_text: str) -> tuple[bool, str] | None:
    t = user_text.lower()
    is_time = any(w in t for w in ("কয়টা", "কতটা", "koyta", "kota baje", "বাজে",
                                   "সময়", "time", "তারিখ", "date", "বার", "bar",
                                   "কাল", "গতকাল", "yesterday", "tomorrow",
                                   "মাস", "month", "year", "বছর"))
    if not is_time:
        return None
    # রূপান্তর: "X টায়/টা ... <শহর> এ কয়টা"
    cities = [k for k in CITY_TZ if k in t.replace(" ", "")]
    if len(cities) >= 2 and any(w in t for w in ("কয়টা", "কতটা", "koyta")):
        f_tz = CITY_TZ[cities[0]]
        t_tz = CITY_TZ[cities[1]]
        return True, convert(t, f_tz, t_tz)
    if any(w in t for w in ("কাল", "গতকাল", "tomorrow", "yesterday", "পরশু")):
        r = yesterday_tomorrow(user_text)
        if r:
            return True, r
    if "তারিখ" in t or "date" in t or "বার" in t or "মাস" in t or "year" in t:
        n = local_now()
        return True, (f"আজ {BN_DAYS[n.weekday()]}, {n.day} {BN_MONTHS[n.month-1]} "
                      f"{n.year}")
    city_tz = _city_from(user_text)
    if city_tz and city_tz != "Asia/Dhaka":
        return True, city_time(city_tz)
    return True, local_time_str()
