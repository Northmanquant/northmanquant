# -*- coding: utf-8 -*-
"""
core/trade_guard.py — لایه‌ی ایمنی «ترید مستقیم»
=================================================
همه‌ی منطق سقف‌ها و گاردهای سفارشِ واقعی همین‌جاست تا بدون UI هم تست‌پذیر باشد.

اصول:
  * هیچ تابعی exception به UI نمی‌اندازد (الگوی کل پروژه) — ورودی خراب = نتیجه‌ی امن.
  * سقف‌ها سخت‌اند: فقط با متغیر محیطی قابل تغییرند، از UI قابل دور زدن نیستند.
  * پیش‌فرض‌ها محافظه‌کارانه‌اند: هر سفارش ۵۰۰ USDT، روزانه ۱۵۰۰ USDT،
    سه سفارش اولِ واقعی حداکثر ۵۰ USDT (دوره‌ی گرم‌کردن).
  * اگر «دفتر سفارش‌ها» (Supabase) در دسترس نباشد، سقف = ۰ یعنی سفارشِ واقعی بسته
    است — چون سقف روزانه و دوره‌ی گرم‌کردن قابل راستی‌آزمایی نیست. Paper همیشه باز است.
"""

from __future__ import annotations

import math
import os
import time
from typing import Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------- تنظیمات (env فقط این‌جا)
def _env_float(name: str, default: float) -> float:
    try:
        raw = str(os.environ.get(name, "") or "").strip()
        v = float(raw) if raw else default
        return v if (math.isfinite(v) and v > 0) else default
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        raw = str(os.environ.get(name, "") or "").strip()
        v = int(float(raw)) if raw else default
        return v if v >= 0 else default
    except Exception:
        return default


MAX_ORDER_USD = _env_float("TRADE_MAX_ORDER_USD", 500.0)          # سقف هر سفارش
MAX_DAILY_USD = _env_float("TRADE_MAX_DAILY_USD", 1500.0)         # سقف مجموع روزانه
WARMUP_ORDERS = _env_int("TRADE_WARMUP_ORDERS", 3)                # طول دوره‌ی گرم‌کردن
WARMUP_MAX_ORDER_USD = _env_float("TRADE_WARMUP_CAP_USD", 50.0)   # سقف سفارش در گرم‌کردن
IDLE_TIMEOUT_SEC = _env_float("TRADE_IDLE_TIMEOUT", 1800.0)       # ۳۰ دقیقه بی‌کاری
PREVIEW_TTL_SEC = _env_float("TRADE_PREVIEW_TTL", 120.0)          # عمر پیش‌نمایش تأیید
MAX_PRICE_DRIFT_PCT = _env_float("TRADE_MAX_PRICE_DRIFT_PCT", 1.0)  # بیشترین جابه‌جایی قیمتِ مجاز
# سفارشِ بازار بین «بررسی» و «تأیید»؛ بیشتر از آن = سفارش ارسال نمی‌شود.
# (سپر لغزش لایتر هم مستقل در سطح SDK فعال است — این گارد روی همه‌ی صرافی‌هاست.)

_EPS = 1e-9


# ---------------------------------------------------------------- محاسبات پایه
def notional(amount, price) -> float:
    """ارزش دلاری سفارش = amount × price. هر ورودی خراب/منفی/بی‌نهایت = ۰.0."""
    try:
        a, p = float(amount), float(price)
        if not (math.isfinite(a) and math.isfinite(p)):
            return 0.0
        if a <= 0 or p <= 0:
            return 0.0
        v = a * p
        return v if (math.isfinite(v) and v > 0) else 0.0
    except Exception:
        return 0.0


def order_cap(real_count: Optional[int]) -> float:
    """سقف مجاز سفارشِ واقعی بعدی.

    real_count=None یعنی دفتر در دسترس نیست → ۰ (بسته).
    در دوره‌ی گرم‌کردن، سقف کوچک‌ترِ گرم‌کردن و سقف کل اعمال می‌شود.
    """
    if real_count is None:
        return 0.0
    try:
        n = int(real_count)
    except Exception:
        return 0.0
    if n < 0:
        return 0.0
    if n < WARMUP_ORDERS:
        return min(WARMUP_MAX_ORDER_USD, MAX_ORDER_USD)
    return MAX_ORDER_USD


def check_order(amount, price, *, cap: float, daily_spent,
                daily_cap: Optional[float] = None) -> Tuple[bool, str]:
    """بررسی‌های سختِ قبل از ارسال سفارش واقعی. خروجی (ok, دلیل_فارسی).

    daily_spent=None با cap>0 (دفتر سالم ولی ردیفی برای امروز نیست) = صفر.
    daily_cap=None یعنی سقف پیش‌فرض ماژول.
    """
    v = notional(amount, price)
    if v <= 0:
        return False, "مقدار و قیمت باید بزرگ‌تر از صفر باشند."
    try:
        cap_f = float(cap)
    except Exception:
        cap_f = 0.0
    if not (math.isfinite(cap_f)) or cap_f <= 0:
        return False, ("دفتر سفارش‌ها در دسترس نیست؛ برای امنیت، سفارش واقعی بسته است — "
                       "حالت Paper فعال است.")
    if v > cap_f + _EPS:
        return False, (f"سقف هر سفارش {cap_f:,.0f} USDT است؛ "
                       f"ارزش این سفارش ≈ {v:,.2f} USDT.")
    if daily_spent is None:
        spent = 0.0
    else:
        try:
            s = float(daily_spent)
            spent = s if (math.isfinite(s) and s > 0) else 0.0
        except Exception:
            spent = 0.0
    dc = MAX_DAILY_USD if daily_cap is None else float(daily_cap)
    if spent + v > dc + _EPS:
        return False, (f"سقف روزانه {dc:,.0f} USDT است؛ "
                       f"امروز {spent:,.2f} USDT ثبت شده و این سفارش ≈ {v:,.2f} USDT.")
    return True, ""


def price_drift_ok(preview_price, live_price,
                   max_pct: Optional[float] = None) -> Tuple[bool, str]:
    """گاردِ جابه‌جایی قیمت برای سفارشِ بازار بین «بررسی» و «تأیید».

    اگر قیمت زنده از قیمتِ بررسی‌شده بیشتر از max_pct (پیش‌فرض ۱٪) دور شده
    باشد، سفارشِ بازار ارسال نمی‌شود — چون سقف‌ها روی قیمتِ قدیمی چک شده‌اند
    و سفارشِ بازار با قیمتِ جدیدِ بالاتر می‌تواند از سقف بگذرد.
    خروجی (ok, دلیل_فارسی). ورودی خراب = بسته (False)."""
    try:
        pp = float(preview_price)
        lp = float(live_price)
        if not (math.isfinite(pp) and math.isfinite(lp)) or pp <= 0 or lp <= 0:
            return False, "قیمت زنده در دسترس نیست؛ سفارشِ بازار ارسال نشد — دوباره «بررسی سفارش» بزن."
        m = float(max_pct) if max_pct is not None else MAX_PRICE_DRIFT_PCT
        if not (math.isfinite(m)) or m <= 0:
            m = MAX_PRICE_DRIFT_PCT
        drift = abs(lp - pp) / pp * 100.0
        if drift > m + _EPS:
            return False, (f"قیمت زنده از زمانِ بررسی {drift:.2f}٪ جابه‌جا شده (بیش از سقف {m:g}٪) — "
                           "سفارشِ بازار برای امنیت ارسال نشد؛ دوباره «بررسی سفارش» بزن.")
        return True, ""
    except Exception:
        return False, "قیمت زنده در دسترس نیست؛ سفارشِ بازار ارسال نشد — دوباره «بررسی سفارش» بزن."


# ---------------------------------------------------------------- نشست و پیش‌نمایش
def expired(last_activity, now: Optional[float] = None,
            timeout: float = IDLE_TIMEOUT_SEC) -> bool:
    """True اگر نشست بیش از timeout بی‌کار مانده یا نشانه‌ی فعالیت نامعتبر است."""
    try:
        la = float(last_activity)
        if not math.isfinite(la) or la <= 0:
            return True
        t = float(timeout)
        if not math.isfinite(t) or t <= 0:
            t = IDLE_TIMEOUT_SEC
        n = float(now) if now is not None else time.time()
        return (n - la) > t
    except Exception:
        return True


def build_preview(*, exchange, symbol, side, otype, amount, price, cap) -> Optional[Dict]:
    """ساخت پیش‌نمایش سفارش برای تأیید دومرحله‌ای. ورودی خراب = None."""
    v = notional(amount, price)
    if v <= 0:
        return None
    try:
        cap_f = float(cap)
    except Exception:
        return None
    if not (math.isfinite(cap_f) and cap_f > 0):
        return None
    return {
        "exchange": str(exchange or "")[:40],
        "symbol": str(symbol or "")[:40],
        "side": "buy" if str(side or "").lower() == "buy" else "sell",
        "otype": "limit" if str(otype or "").lower() == "limit" else "market",
        "amount": float(amount),
        "price": float(price),
        "notional": v,
        "cap": cap_f,
        "created": time.time(),
    }


def preview_stale(p, now: Optional[float] = None,
                  ttl: float = PREVIEW_TTL_SEC) -> bool:
    """True اگر پیش‌نمایش خراب باشد یا از ساختنش بیشتر از ttl گذشته باشد."""
    try:
        if not isinstance(p, dict):
            return True
        c = float(p.get("created") or 0)
        if not math.isfinite(c) or c <= 0:
            return True
        t = float(ttl) if math.isfinite(float(ttl)) and float(ttl) > 0 else PREVIEW_TTL_SEC
        n = float(now) if now is not None else time.time()
        return (n - c) > t
    except Exception:
        return True


def preview_text(p, en: bool = False) -> str:
    """جمله‌ی یک‌خطی پیش‌نمایش برای جعبه‌ی تأیید. پیش‌نمایش خراب = رشته‌ی خالی."""
    if not isinstance(p, dict):
        return ""
    v = p.get("notional")
    try:
        v_f = float(v)
    except Exception:
        return ""
    if not (math.isfinite(v_f) and v_f > 0):
        return ""
    kind = "Limit" if p.get("otype") == "limit" else "Market"
    side = "buy" if p.get("side") == "buy" else "sell"
    amt = p.get("amount")
    prc = p.get("price")
    sym = p.get("symbol") or "?"
    ex = p.get("exchange") or "?"
    cap = p.get("cap")
    try:
        amt_s = f"{float(amt):g}"
        prc_s = f"{float(prc):g}"
    except Exception:
        return ""
    try:
        cap_s = f"{float(cap):,.0f}"
    except Exception:
        cap_s = "?"
    if en:
        return (f"{kind} {side.upper()} {amt_s} {sym} on {ex} "
                f"≈ {v_f:,.2f} USDT · price estimate {prc_s} · cap {cap_s} USDT")
    return (f"سفارش {kind} {side} · {amt_s} {sym} در {ex} "
            f"≈ {v_f:,.2f} USDT · قیمت تخمینی {prc_s} · سقف {cap_s} USDT")


# ---------------------------------------------------------------- ابزارهای امنیتی متفرقه
def scrub(msg, *secrets) -> str:
    """پیام خطا را از هر کلیدی که ممکن است داخلش باشد پاک می‌کند."""
    out = "" if msg is None else str(msg)
    for s in secrets:
        try:
            sv = str(s or "")
            if len(sv) >= 6:
                out = out.replace(sv, "***")
        except Exception:
            continue
    return out


def filter_real_exchanges(ex_map: Dict[str, str],
                          has_id: Callable[[str], bool]) -> List[str]:
    """فقط صرافی‌هایی که ccxt واقعاً می‌شناسد مجازند؛ callable خراب هم امن رد می‌شود."""
    out: List[str] = []
    for name, cid in (ex_map or {}).items():
        try:
            if has_id(cid):
                out.append(name)
        except Exception:
            continue
    return out
