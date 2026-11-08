# -*- coding: utf-8 -*-
"""AVA Weather Intelligence — Open-Meteo (ফ্রি, API key ছাড়া, বাস্তব ডেটা)।
- বর্তমান আবহাওয়া, তাপমাত্রা, feels-like, বৃষ্টির সম্ভাবনা, আর্দ্রতা, বাতাস
- ঘণ্টা-ভিত্তিক ও দৈনিক পূর্বাভাস • শহর সার্চ (geocoding) • পছন্দের লোকেশন সেভ
- সৎ নীতি: API/নেটওয়ার্ক ব্যর্থ হলে স্পষ্ট বলে — কখনো ভুয়া ডেটা নয়।"""
import datetime
import json
import os

import requests

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
WX_URL = "https://api.open-meteo.com/v1/forecast"
PREF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ava_locations.json")
SOURCE = "উৎস: Open-Meteo.com"

WMO = {0: "পরিষ্কার আকাশ ☀️", 1: "প্রায় পরিষ্কার 🌤️", 2: "আংশিক মেঘলা ⛅",
       3: "মেঘলা ☁️", 45: "কুয়াশা 🌫️", 48: "কুয়াশা 🌫️",
       51: "হালকা গুঁড়ি বৃষ্টি 🌦️", 53: "গুঁড়ি বৃষ্টি 🌦️", 55: "ঘন গুঁড়ি বৃষ্টি",
       61: "হালকা বৃষ্টি 🌧️", 63: "বৃষ্টি 🌧️", 65: "ভারী বৃষ্টি ⛈️",
       71: "হালকা তুষারপাত ❄️", 80: "বৃষ্টির ঝাপটা 🌧️", 81: "ঝমঝম বৃষ্টি",
       82: "প্রবল বৃষ্টি ⛈️", 95: "বজ্রপাত সহ ঝড় ⛈️", 96: "শিলাবৃষ্টি সহ ঝড় ⛈️"}


def _wmo(code: int) -> str:
    return WMO.get(code, f"কোড {code}")


def geocode(city: str) -> dict | None:
    try:
        r = requests.get(GEO_URL, params={"name": city, "count": 1, "language": "en"},
                         timeout=(5, 15))
        res = r.json().get("results", [])
        return res[0] if res else None
    except Exception:
        return None


def preferred() -> dict:
    try:
        return json.load(open(PREF_FILE, encoding="utf-8"))
    except Exception:
        return {"name": "Dhaka", "lat": 23.8103, "lon": 90.4125}  # ডিফল্ট: ঢাকা


def set_preferred(city: str) -> str:
    g = geocode(city)
    if not g:
        return f"'{city}' শহরটি খুঁজে পাইনি।"
    pref = {"name": g.get("name", city), "lat": g["latitude"], "lon": g["longitude"]}
    json.dump(pref, open(PREF_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    return f"পছন্দের লোকেশন সেভ হলো: {pref['name']}"


def fetch(lat: float, lon: float) -> dict | None:
    try:
        r = requests.get(WX_URL, params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                       "precipitation,weather_code,wind_speed_10m,wind_direction_10m,"
                       "cloud_cover,is_day",
            "hourly": "temperature_2m,precipitation_probability,weather_code",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                     "precipitation_probability_max,sunrise,sunset",
            "timezone": "auto", "forecast_days": 3,
        }, timeout=(5, 25))
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _wind_dir(deg: int) -> str:
    dirs = ["উত্তর", "উত্তর-পূর্ব", "পূর্ব", "দক্ষিণ-পূর্ব", "দক্ষিণ",
            "দক্ষিণ-পশ্চিম", "পশ্চিম", "উত্তর-পশ্চিম"]
    return dirs[round(deg / 45) % 8]


def report(city: str | None = None, daily: bool = False) -> str:
    pref = preferred()
    if city:
        g = geocode(city)
        if not g:
            return f"'{city}'-এর তথ্য পাইনি — নেটওয়ার্ক বা বানান দেখুন।"
        lat, lon, cname = g["latitude"], g["longitude"], g.get("name", city)
    else:
        lat, lon, cname = pref["lat"], pref["lon"], pref["name"]
    data = fetch(lat, lon)
    if not data:
        return (f"⚠️ আবহাওয়ার ডেটা আনা যায়নি ({cname})।\n"
                "কারণ: নেটওয়ার্ক সমস্যা বা Open-Meteo অনুপলব্ধ। ভুয়া ডেটা দিচ্ছি না।")
    cur = data.get("current", {})
    temp = cur.get("temperature_2m")
    code = cur.get("weather_code", 0)
    rain_now = cur.get("precipitation", 0)
    out = [f"🌍 {cname} ({SOURCE}, আপডেট: {str(cur.get('time',''))[-5:]} স্থানীয়)",
           f"🌡️ তাপমাত্রা: {temp}°C (অনুভূত {cur.get('apparent_temperature')}°C)",
           f"☁️ {_wmo(code)}"
           + (f", এখন বৃষ্টি হচ্ছে ({rain_now}mm)" if rain_now else ""),
           f"💧 আর্দ্রতা: {cur.get('relative_humidity_2m')}% | "
           f"💨 বাতাস: {cur.get('wind_speed_10m')} km/h ({_wind_dir(cur.get('wind_direction_10m', 0))})"]
    daily_data = data.get("daily", {})
    if daily_data.get("time"):
        d0 = daily_data["time"][0]
        out.append(f"📊 আজ: সর্বোচ্চ {daily_data['temperature_2m_max'][0]}°C / "
                   f"সর্বনিম্ন {daily_data['temperature_2m_min'][0]}°C, "
                   f"বৃষ্টির সম্ভাবনা {daily_data['precipitation_probability_max'][0]}%")
        out.append(f"🌅 সূর্যোদয় {daily_data['sunrise'][0][11:16]} | "
                   f"🌇 সূর্যাস্ত {daily_data['sunset'][0][11:16]}")
        if daily:
            for i, day in enumerate(daily_data["time"][1:3], 1):
                out.append(f"📅 {day}: {_wmo(daily_data['weather_code'][i])}, "
                           f"{daily_data['temperature_2m_min'][i]}–"
                           f"{daily_data['temperature_2m_max'][i]}°C, "
                           f"বৃষ্টি {daily_data['precipitation_probability_max'][i]}%")
    # পরের ৬ ঘণ্টার বৃষ্টি সম্ভাবনা
    hourly = data.get("hourly", {})
    if hourly.get("precipitation_probability"):
        probs = hourly["precipitation_probability"][:7]
        times = hourly["time"][:7]
        rainy = [(t[11:16], p) for t, p in zip(times, probs) if p >= 50]
        if rainy:
            out.append("🌧️ বৃষ্টির সম্ভাবনা: " + ", ".join(f"{t} ({p}%)" for t, p in rainy[:3]))
        else:
            out.append("🌧️ পরের ৬ ঘণ্টায় বৃষ্টির সম্ভাবনা কম।")
    return "\n".join(out)


def handle(user_text: str) -> tuple[bool, str] | None:
    t = user_text.lower()
    if not any(w in t for w in ("আবহাওয়া", "weather", "বৃষ্টি", "brishti", "তাপমাত্রা",
                                "temperature", "গরম", "ঠান্ডা", "sunrise", "সূর্যোদয়")):
        return None
    city = None
    for kw in ("কুষ্টিয়া", "kushtia", "ঢাকা", "dhaka", "চট্টগ্রাম", "chittagong",
               "সিলেট", "sylhet", "খুলনা", "khulna", "রাজশাহী", "rajshahi"):
        if kw in t:
            city = kw
            break
    if "সেভ" in t or "save" in t or "পছন্দ" in t:
        m = city or ""
        if not m:
            return True, "কোন শহর পছন্দ করব বলুন।"
        return True, set_preferred(m)
    if "কাল" in t or "tomorrow" in t or "আগামীকাল" in t:
        return True, report(city, daily=True)
    return True, report(city)
