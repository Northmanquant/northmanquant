# -*- coding: utf-8 -*-
"""core/macro_ir.py — چشم‌انداز کلانِ بازار ایران: دلار، یورو، طلا، سکه (بدون کلید)
====================================================================================
الگوی خواندن از پروفایل‌های TGJU از پروژه‌ی TITAN برداشته شده است:
صفحه‌ی پروفایل هر نماد (مثل tgju.org/profile/price_dollar_rl) یک سلول
«data-col="info.last_trade.PDrCotVal"» دارد که آخرین قیمتِ ریالی را نشان می‌دهد.
همان قیمت ÷۱۰ می‌شود و تومان نمایش داده می‌شود.

دسترسی: tgju.org برخلاف سرورهای TSETMC از خارج ایران هم پاسخ می‌دهد، ولی اگر
جواب نداد این بخش خراب نمی‌شود — فقط «—» یا حذف موقت؛ بورس همچنان کار می‌کند.

الگوی پروژه: هیچ تابعی exception به UI نمی‌اندازد — خرابی = {} .
همه‌چیز با fetch تزریقی بدون شبکه تست‌پذیر است؛ پیام‌ها دوزبانه‌اند.
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable, Dict, Optional

from core.net import get_text
from core.tse import norm_fa

HOST = "https://www.tgju.org"
FETCH_TIMEOUT = 8.0
TTL = 300.0          # قیمت‌های TGJU کند به‌روز می‌شوند — کش ۵ دقیقه
NEG_TTL = 60.0       # کش منفیِ کوتاه بعد از شکست — اصرار بی‌مورد به شبکه نه

# کلید → (آیکن، fa، en، slug پروفایل TGJU)
PROFILES: Dict[str, Dict[str, str]] = {
    "usd": {"icon": "💵", "fa": "دلار (آزاد)", "en": "USD (free)",
            "slug": "price_dollar_rl"},
    "eur": {"icon": "💶", "fa": "یورو (آزاد)", "en": "EUR (free)",
            "slug": "price_eur"},
    "gold18": {"icon": "🥇", "fa": "طلای ۱۸ عیار — گرم", "en": "Gold 18k — gram",
               "slug": "geram18"},
    "coin": {"icon": "🪙", "fa": "سکه امامی", "en": "Emami gold coin",
             "slug": "sekee"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/169.0.0.0 Safari/537.36",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}

# همان سلولی که TITAN پارس می‌کند — آخرین قیمتِ معامله در صفحه‌ی پروفایل
_PRICE_RE = re.compile(
    r"data-col=[\"']info\.last_trade\.PDrCotVal[\"'][^>]*>\s*([\d۰-۹٠-٩,.٬]+)")

_TextFetch = Callable[..., str]

_cache: Dict[str, Any] = {}          # slug → (mono_ts, نتیجه یا None)
last_error: Optional[str] = None


def _reset_for_tests() -> None:
    """بین تست‌ها وضعیت ماژول صفر می‌شود (بدون شبکه)."""
    global _cache, last_error
    _cache = {}
    last_error = None


# ---------------------------------------------------------------- لایه‌ی fetch
def _fetch_text(url: str, _fetch: Optional[_TextFetch] = None) -> str:
    """یک GET ساده — خرابی = رشته‌ی خالی + پیام صادقانه در last_error."""
    global last_error
    fetch = _fetch or get_text
    try:
        txt = fetch(url, headers=HEADERS, timeout=FETCH_TIMEOUT, retries=0)
        if txt and str(txt).strip():
            last_error = None
            return str(txt)
        last_error = "پاسخ TGJU خالی بود."
    except Exception as e:  # noqa: BLE001
        last_error = f"TGJU پاسخ نداد ({type(e).__name__})."
    return ""


# ---------------------------------------------------------------- پارس
def _parse_price(raw: str) -> float:
    """HTML پروفایل TGJU → قیمت به تومان. خرابی = ۰٫۰ (هرگز raise نمی‌کند)."""
    m = _PRICE_RE.search(raw or "")
    if not m:
        return 0.0
    n = norm_fa(m.group(1)).replace(",", "").replace("٬", "")
    try:
        v = float(n)
    except ValueError:
        return 0.0
    return v / 10.0 if v > 0 else 0.0    # ریال → تومان


# ---------------------------------------------------------------- API عمومی
def quote(slug: str, _fetch: Optional[_TextFetch] = None,
          ttl: float = TTL) -> Dict[str, Any]:
    """یک نماد کلان؛ خروجی {'price': تومان, 'source': 'TGJU', 'url': …} — خرابی = {}."""
    prof = PROFILES.get(str(slug or "").strip())
    if not prof:
        return {}
    hit = _cache.get(slug)
    if hit is not None:
        age = time.monotonic() - hit[0]
        if (age < ttl) if hit[1] else (age < NEG_TTL):
            return hit[1] or {}
    url = f"{HOST}/profile/{prof['slug']}"
    price = _parse_price(_fetch_text(url, _fetch))
    if price <= 0:
        _cache[slug] = (time.monotonic(), None)      # کش منفیِ کوتاه
        return {}
    out = {"price": price, "source": "TGJU", "url": url}
    _cache[slug] = (time.monotonic(), out)
    return out


def quotes(_fetch: Optional[_TextFetch] = None,
           ttl: float = TTL) -> Dict[str, Dict[str, Any]]:
    """همه‌ی نمادهای کلان؛ خراب‌ها از خروجی غایب‌اند (کلید ندارد)."""
    return {k: quote(k, _fetch, ttl) for k in PROFILES}
