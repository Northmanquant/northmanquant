# -*- coding: utf-8 -*-
"""core/econ_calendar.py — تقویم اقتصادی آمریکا (فقط منابع رسمی — پورت از TITAN)
===============================================================================
پورت‌شده از finance_hub.py پروژه‌ی TITAN با همان اصل «هیچ تاریخِ حدسی»:
فایل‌های ICS رسمی تقویم انتشار آمار آمریکا خوانده می‌شود — نه هیچ تقویم
سومی که تاریخ‌ها را خودش «حدس» می‌زند:
  · BLS  — بورو آمار کار (CPI، NFP، PPI، JOLTS، ECI)
  · BEA  — دفتر تحلیل اقتصادی (GDP، PCE، درآمد و مخارج)

هر رویداد با «ترجمه‌ی فارسیِ تأییدشده» یا بدون ترجمه برمی‌گردد؛ رویدادهای
ترجمه‌داده‌شده priority='key' می‌گیرند (همان‌هایی که بازار را تکان می‌دهند).

الگوی پروژه (هم‌خوان با core/macro_ir.py):
  · هیچ تابعی exception به UI نمی‌اندازد — خرابی هر منبع داخل گروه همان
    منبع با کلید error گزارش می‌شود و بقیه‌ی منابع سالم می‌مانند.
  · همه‌چیز با fetch تزریقی بدون شبکه تست‌پذیر است.
  · زمان: UTC استخراج می‌شود و نمایش تهران (+۳:۳۰ ثابت — ایران از ۱۴۰۱
    ساعت تابستانی ندارد) جداگانه داده می‌شود؛ رویدادهای US-Eastern با
    zoneinfo به UTC تبدیل می‌شوند و اگر منطقه‌ی زمانی نصب نبود، زمان
    محلی + برچسب منطقه صادقانه برگردانده می‌شود (نه تبدیلِ حدسی).
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.net import get_text

# منبع → (نام فارسی، آدرس ICS رسمی، صفحه‌ی عمومی تقویم)
CALENDARS: Dict[str, Dict[str, str]] = {
    "bls": {
        "name_fa": "بورو آمار کار آمریکا (BLS)",
        "ics": "https://www.bls.gov/schedule/news_release/bls.ics",
        "public": "https://www.bls.gov/schedule/news_release/",
    },
    "bea": {
        "name_fa": "دفتر تحلیل اقتصادی آمریکا (BEA)",
        "ics": "https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics",
        "public": "https://www.bea.gov/news/schedule/",
    },
}

# ترجمه‌ی رویدادهای کلیدی — همان مجموعه‌ی امتحان‌پس‌داده‌ی TITAN
# (زیررشته‌ی عنوانِ رسمی → نام فارسی). هر چیزی که ترجمه دارد = رویداد کلیدی بازار.
TRANSLATIONS: Dict[str, str] = {
    "Consumer Price Index": "شاخص قیمت مصرف‌کننده CPI",
    "Employment Situation": "گزارش اشتغال آمریکا NFP",
    "Producer Price Index": "شاخص قیمت تولیدکننده PPI",
    "Job Openings and Labor Turnover Survey": "فرصت‌های شغلی JOLTS",
    "Employment Cost Index": "شاخص هزینه اشتغال ECI",
    "Personal Income and Outlays": "درآمد و مخارج شخصی / PCE",
    "Gross Domestic Product": "تولید ناخالص داخلی GDP",
}

TEHRAN = timezone(timedelta(hours=3, minutes=30))   # ایران: UTC+3:30 ثابت
FETCH_TIMEOUT = 15.0
TTL = 6 * 3600.0          # تقویم رسمی کند به‌روز می‌شود — کش ۶ ساعت (مثل TITAN)
NEG_TTL = 600.0           # کش منفیِ کوتاه بعد از شکست

# لایه‌ی دوم fetch — آینه‌ی همه‌منظوره‌ی همان فایل رسمی. BLS از IPهای دیتاسنتر
# (Streamlit Cloud) دسترسی را می‌بندد (۴۰۳)؛ داده‌ی رسمی از مسیر دیگر همان است.
MIRROR_PREFIX = "https://api.allorigins.win/raw?url="

# لایه‌ی سوم فیوز — اسنپ‌شات محلیِ فایل رسمی (الگوی tse_symbols.json).
# تولید/نوسازی: python3 scripts/gen_econ_snapshot.py
_SNAP_DIR = Path(__file__).parent / "data"


def _mirror_url(url: str) -> str:
    return MIRROR_PREFIX + urllib.parse.quote(url or "", safe="")


def _snapshot(source: str) -> tuple[str, str]:
    """اسنپ‌شات محلیِ رسمی → (متن، تاریخ اسنپ‌شات). نبود/خراب = ("", "")."""
    try:
        p = _SNAP_DIR / f"{source}_schedule.ics"
        txt = p.read_text(encoding="utf-8") if p.exists() else ""
        if "BEGIN:VCALENDAR" not in txt:
            return "", ""
        date = ""
        try:
            j = json.loads((_SNAP_DIR / "econ_snapshots.json").read_text(encoding="utf-8"))
            date = str((j.get(source) or {}).get("fetched_at", ""))[:10]
        except Exception:  # noqa: BLE001 — بدون متادیتا هم اسنپ‌شات معتبر است
            pass
        return txt, date
    except Exception:  # noqa: BLE001 — فیوز هرگز نباید بشکند
        return "", ""


# هدر مرورگر — بعضی منابع (مثل BLS) درخواستِ بدون UA را می‌بندند
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/169.0.0.0 Safari/537.36",
    "Accept": "text/calendar,text/plain,*/*",
}

_MONTH_RE = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")
_DATE_RE = re.compile(r"\d{8}(T\d{6}Z?)?")
_EASTERN_ZONES = ("US-Eastern", "US/Eastern", "America/New_York")

_TextFetch = Callable[..., str]

_cache: Dict[str, Any] = {}     # source → (mono_ts, نتیجه یا False برای کشِ منفی)
last_error: Optional[str] = None


def _reset_for_tests() -> None:
    """بین تست‌ها وضعیت ماژول صفر می‌شود (بدون شبکه)."""
    global _cache, last_error
    _cache = {}
    last_error = None


# ---------------------------------------------------------------- پارس ICS
def _parse_dtstart(key: str, value: str) -> Optional[Dict[str, Any]]:
    """یک DTSTART خام → {'utc': datetime|None, 'local': datetime,
    'all_day': bool, 'zone': str}. تاریخ نامعتبر = None."""
    value = value.strip()
    if not _DATE_RE.fullmatch(value):
        return None
    all_day = "T" not in value
    fmt = "%Y%m%d" if all_day else "%Y%m%dT%H%M%S"
    try:
        local = datetime.strptime(value.rstrip("Z"), fmt)
    except ValueError:
        return None
    is_utc = value.endswith("Z")
    zone = "UTC" if is_utc else "America/New_York"
    raw_tzid = key.split("TZID=", 1)[1].split(";", 1)[0].strip() if "TZID=" in key else ""
    if raw_tzid and raw_tzid not in _EASTERN_ZONES and not is_utc:
        return None                      # فقط UTC یا شرق آمریکا — بقیه: بی‌خیالِ رویداد
    if all_day:
        # رویداد تمام‌روز وقتِ دقیق ندارد — تبدیل منطقه‌ی زمانی بی‌معنی و گمراه‌کننده است
        return {"utc": None, "local": local, "all_day": True, "zone": zone}
    utc = None
    if is_utc:
        utc = local.replace(tzinfo=timezone.utc)
    else:
        try:                             # شرق آمریکا → UTC (به tzdata وابسته است)
            from zoneinfo import ZoneInfo
            utc = local.replace(tzinfo=ZoneInfo(zone)).astimezone(timezone.utc)
        except Exception:                # noqa: BLE001 — بدون tzdata هم می‌شکند
            utc = None
    return {"utc": utc, "local": local, "all_day": False, "zone": zone}


def parse_ics(body: str, source: str, url: str) -> List[Dict[str, Any]]:
    """متن ICS → فهرست رویدادها. همان منطق TITAN: خطوط تا‌شده باز می‌شوند،
    رویداد CANCELLED دور ریخته می‌شود، فقط تاریخ معتبر پذیرفته می‌شود.
    هیچ رویداد معتبری → ValueError (صدا زننده تصمیم می‌گیرد)."""
    body = re.sub(r"\r?\n[ \t]", "", body or "")
    result: List[Dict[str, Any]] = []
    for block in re.findall(r"BEGIN:VEVENT\s*(.*?)\s*END:VEVENT", body, re.S):
        fields: Dict[str, str] = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
        if fields.get("STATUS") == "CANCELLED":
            continue
        start = next(((k, v) for k, v in fields.items() if k.split(";")[0] == "DTSTART"), None)
        if start is None:
            continue
        title = (fields.get("SUMMARY") or "").replace("\\,", ",").replace("\\n", " ") \
            .replace("\\;", ";")[:350]
        parsed = _parse_dtstart(start[0], start[1])
        if not title or parsed is None:
            continue
        translation = next((fa for en, fa in TRANSLATIONS.items() if en in title), "")
        uid = fields.get("UID") or (title + start[1])
        utc = parsed["utc"]
        tehran = ""
        if utc is not None:
            tehran = utc.astimezone(TEHRAN).strftime("%Y-%m-%d %H:%M")
        result.append({
            "id": f"{source}:{uid}",
            "title": title,
            "title_fa": translation,
            "datetime_utc": utc.isoformat(timespec="seconds") if utc else "",
            "datetime_local": parsed["local"].isoformat(timespec="seconds"),
            "zone": parsed["zone"],
            "tz_exact": utc is not None,
            "all_day": parsed["all_day"],
            "tehran": tehran,
            "currency": "USD",
            "priority": "key" if translation else "normal",
            "source": source,
            "url": url,
        })
    if not result:
        raise ValueError("هیچ رویداد معتبری در تقویم نیست")
    return result


# ---------------------------------------------------------------- لایه‌ی fetch
def _fetch_ics(url: str, _fetch: Optional[_TextFetch] = None) -> str:
    """یک GET ساده — خرابی = رشته‌ی خالی + پیام صادقانه در last_error."""
    global last_error
    fetch = _fetch or get_text
    try:
        txt = fetch(url, headers=HEADERS, timeout=FETCH_TIMEOUT, retries=0)
        if txt and str(txt).strip():
            last_error = None
            return str(txt)
        last_error = "پاسخ تقویم رسمی خالی بود."
    except Exception as e:  # noqa: BLE001
        msg = str(e) or type(e).__name__
        if "403" in msg:
            # BLS دسترسی بعضی IPها (معمولاً خارج از آمریکا) را می‌بندد — صادقانه بگویم
            last_error = "منبع دسترسی این سرور را بست (۴۰۳) — از اجرای لوکال یا سرور آمریکا معمولاً باز می‌شود."
        else:
            last_error = f"تقویم رسمی پاسخ نداد ({type(e).__name__})."
    return ""


def _source_group(source: str, month: str,
                  _fetch: Optional[_TextFetch] = None) -> Dict[str, Any]:
    """یک منبع را می‌خواند/از کش می‌گیرد و به همان ماه فیلتر می‌کند.
    سه لایه: مستقیم → آینه‌ی رسمی → اسنپ‌شات محلی.
    خرابی کامل = گروه با کلید error (بقیه‌ی منابع سالم می‌مانند)."""
    meta = CALENDARS[source]
    hit = _cache.get(source)
    cached: Optional[Dict[str, Any]] = None
    negative = False
    if hit is not None:
        age = time.monotonic() - hit[0]
        if hit[1] is False:              # کشِ منفیِ شکست اخیر
            negative = age < NEG_TTL
        elif age < TTL:
            cached = hit[1]
    if cached is None and not negative:
        snap_date = ""
        via = "live"
        txt = _fetch_ics(meta["ics"], _fetch)
        if not txt.strip():
            # مستقیم شکست خورد — همان فایل رسمی از مسیر آینه
            txt = _fetch_ics(_mirror_url(meta["ics"]), _fetch)
            via = "mirror"
        if not txt.strip():
            # آینه هم شکست خورد — فیوز: اسنپ‌شات رسمی داخل ریپو
            txt, snap_date = _snapshot(source)
            via = "snapshot"
        if not txt.strip():
            # شبکه/دسترسی شکست خورد — پیام صادقانه‌ی لایه‌ی fetch (مثلاً ۴۰۳) بیاید، نه پیام عمومیِ پارس
            _cache[source] = (time.monotonic(), False)   # کشِ منفیِ کوتاه
            cached = {"data": [], "error": last_error or "منبع پاسخ نداد.",
                      "via": "live", "snapshot_date": ""}
        else:
            try:
                events = parse_ics(txt, source, meta["ics"])
                cached = {"data": events, "error": "", "via": via,
                          "snapshot_date": snap_date if via == "snapshot" else ""}
                _cache[source] = (time.monotonic(), cached)
            except Exception as e:  # noqa: BLE001
                _cache[source] = (time.monotonic(), False)   # کشِ منفیِ کوتاه
                cached = {"data": [], "error": str(e) or type(e).__name__,
                          "via": "live", "snapshot_date": ""}
    if negative:
        cached = {"data": [], "error": "شکست قبلی — کش منفی (چند دقیقه بعد دوباره تلاش می‌شود).",
                  "via": "live", "snapshot_date": ""}
    cached = cached or {"data": [], "error": "", "via": "live", "snapshot_date": ""}
    data = cached.get("data") or []
    in_month = [e for e in data if (e["datetime_utc"] or e["datetime_local"]).startswith(month)]
    cover = [(e["datetime_utc"] or e["datetime_local"])[:10] for e in data]
    return {
        "key": source,
        "name_fa": meta["name_fa"],
        "public_url": meta["public"],
        "data": in_month,
        "error": cached.get("error", ""),
        "via": cached.get("via", "live"),
        "snapshot_date": cached.get("snapshot_date", ""),
        "coverage_start": min(cover, default=None),
        "coverage_end": max(cover, default=None),
    }


# ---------------------------------------------------------------- API عمومی
def calendar(month: str, _fetch: Optional[_TextFetch] = None,
             ttl: float = TTL) -> Dict[str, Any]:
    """تقویم ماهِ «YYYY-MM» از همه‌ی منابع رسمی — هیچ‌وقت raise نمی‌کند."""
    month = str(month or "").strip()
    if not _MONTH_RE.match(month):
        return {"month": "", "groups": {}, "checked_at": _now_iso(),
                "note": "ماه باید به شکل YYYY-MM باشد.",
                "note_en": "Month must look like YYYY-MM.", "ok": False}
    groups = {key: _source_group(key, month, _fetch) for key in CALENDARS}
    errors = [g["error"] for g in groups.values() if g["error"]]
    return {
        "month": month,
        "groups": groups,
        "checked_at": _now_iso(),
        "note": "رویدادهای رسمی آمریکا؛ تقویم همه‌ی کشورها نیست. زمان و تاریخ ممکن است به دست ناشر تغییر کند.",
        "note_en": "Official US releases only; not an all-country calendar. Publishers may change dates and times.",
        "ok": not errors or any(g["data"] for g in groups.values()),
    }


def key_events_upcoming(days: int = 14, _fetch: Optional[_TextFetch] = None,
                        now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """رویدادهای کلیدی (ترجمه‌دار: CPI/NFP/…) در N روز پیشِ رو — برای بات تلگرام.
    از کشِ همان calendar(month) استفاده می‌کند؛ خرابی = [] ."""
    ref = (now or datetime.now(timezone.utc))
    out: List[Dict[str, Any]] = []
    for shift in (0, 1):                 # ماهِ جاری و ماهِ بعد را بپوشان
        m = (ref if shift == 0 else
             (ref.replace(day=28) + timedelta(days=6)).replace(day=1))
        cal = calendar(m.strftime("%Y-%m"), _fetch)
        for g in cal["groups"].values():
            for e in g.get("data") or []:
                if e["priority"] != "key" or not e["datetime_utc"]:
                    continue
                try:
                    dt = datetime.fromisoformat(e["datetime_utc"])
                except ValueError:
                    continue
                if ref <= dt <= ref + timedelta(days=days):
                    out.append(e)
    out.sort(key=lambda e: e["datetime_utc"])
    ids = set()
    unique: List[Dict[str, Any]] = []
    for e in out:                        # رویداد مرزی دو ماه دوبار نیاید
        if e["id"] not in ids:
            ids.add(e["id"])
            unique.append(e)
    return unique


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
