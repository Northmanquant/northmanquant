# -*- coding: utf-8 -*-
"""
core/lighter.py — کلاینت عمومیِ صرافی Lighter (perp DEX)
=========================================================
فقط API عمومیِ بدون‌کلید: /api/v1/orderBookDetails (بازارها + قیمت آخر).
مستندات رسمی: https://apidocs.lighter.xyz/reference/orderBookdetails

نکته‌ی صادقانه: ارسال سفارشِ واقعی روی لایتر این‌جا نیست — آن مسیر به
امضای L2 و SDK رسمی نیاز دارد و بعداً به صفحه‌ی «ترید مستقیم» اضافه می‌شود.
الان لایتر در ترید مستقیم فقط Paper است (قیمت واقعیِ پرپ، سفارش مجازی).

الگوی پروژه: هیچ تابعی exception به UI نمی‌اندازد — ورودی/شبکه‌ی خراب =
None / [] / 0.0. همه‌ی توابع با fetch تزریقی بدون شبکه تست‌پذیرند.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from core.net import get_json

BASE = "https://mainnet.zklighter.elliot.ai"
HEADERS = {"User-Agent": "Mozilla/5.0 (NorthmanQuant; live prices)"}
MARKETS_TTL_SEC = 60.0            # کش کوتاه؛ فهرست بازارها کند تغییر می‌کند
FETCH_TIMEOUT = 15.0

_cache: Dict[str, Any] = {"rows": None, "ts": 0.0}
last_error: Optional[str] = None

_Fetch = Callable[..., Any]       # هم‌امضای get_json


def _reset_for_tests() -> None:
    """بین تست‌ها وضعیت ماژول صفر می‌شود (بدون شبکه)."""
    global _cache, last_error
    _cache = {"rows": None, "ts": 0.0}
    last_error = None


# ---------------------------------------------------------------- نرمال‌سازی نماد
def normalize(symbol: str) -> str:
    """«BTC/USDT» یا «btc-usd» یا «BTC-PERP» → «BTC» (نمادهای پرپ لایتر بدون USDT)."""
    s = str(symbol or "").strip().upper()
    if not s:
        return ""
    for sep in ("/", "-", ":"):
        if sep in s:
            s = s.split(sep, 1)[0]
            break
    return s.strip()


# ---------------------------------------------------------------- بازارها
def _parse_markets(data: Any) -> List[Dict[str, Any]]:
    """ردیف‌های خام orderBookDetails → ردیف تمیز. ردیف خراب رد می‌شود."""
    rows: List[Dict[str, Any]] = []
    if not isinstance(data, dict):
        return rows
    raw = data.get("order_book_details")
    if not isinstance(raw, list):
        return rows
    for r in raw:
        try:
            if not isinstance(r, dict):
                continue
            sym = str(r.get("symbol") or "").strip().upper()
            if not sym:
                continue
            mid = r.get("market_id")
            rows.append({
                "symbol": sym,
                "market_id": int(mid) if mid is not None else None,
                "status": str(r.get("status") or "").strip(),
                "last": float(r.get("last_trade_price") or 0),
                "mark": float(r.get("mark_price") or 0),
                "change_pct": float(r.get("daily_price_change") or 0),
                "high": float(r.get("daily_price_high") or 0),
                "low": float(r.get("daily_price_low") or 0),
            })
        except Exception:
            continue
    return rows


def markets(_fetch: Optional[_Fetch] = None, *, now: Optional[float] = None,
            ttl: float = MARKETS_TTL_SEC) -> List[Dict[str, Any]]:
    """همه‌ی بازارهای لایتر با کش کوتاه. خرابی = [] (هرگز raise نمی‌کند)."""
    global _cache, last_error
    fetch = _fetch or get_json
    n = float(now) if now is not None else time.monotonic()
    try:
        if float(ttl) <= 0:
            ttl = MARKETS_TTL_SEC
    except Exception:
        ttl = MARKETS_TTL_SEC
    if _cache["rows"] is not None and (n - float(_cache["ts"])) < ttl:
        return _cache["rows"]
    try:
        data = fetch(f"{BASE}/api/v1/orderBookDetails", headers=HEADERS,
                     timeout=FETCH_TIMEOUT)
        rows = _parse_markets(data)
        if not rows:
            # پاسخ خالی/خراب را کش نمی‌کنیم تا تلاش بعدی زنده باشد
            last_error = "پاسخ بازارهای لایتر خالی بود"
            return []
        _cache["rows"] = rows
        _cache["ts"] = n
        last_error = None
        return rows
    except Exception as e:
        last_error = f"دریافت بازارهای لایتر ناموفق بود: {e}"
        return []


def market_id(symbol: str, _fetch: Optional[_Fetch] = None) -> Optional[int]:
    """نماد → market_id (بدون هاردکد آیدی). پیدا نشد/شبکه خراب = None."""
    sym = normalize(symbol)
    if not sym:
        return None
    for row in markets(_fetch):
        if row.get("symbol") == sym:
            mid = row.get("market_id")
            try:
                return int(mid) if mid is not None else None
            except Exception:
                return None
    return None


def symbols(_fetch: Optional[_Fetch] = None) -> List[str]:
    """نمادهای فعال، مرتب؛ لایتر اول نیست — فقط الفبایی. خرابی = []."""
    rows = markets(_fetch)
    active = [r["symbol"] for r in rows if str(r.get("status") or "") == "ACTIVE"]
    if not active:
        active = [r["symbol"] for r in rows]
    return sorted(set(active))


def ticker(symbol: str, _fetch: Optional[_Fetch] = None) -> Optional[Dict[str, Any]]:
    """قیمت لحظه‌ای یک نماد پرپ: last/mark/change_pct. خرابی یا نماد ناشناخته = None."""
    sym = normalize(symbol)
    if not sym:
        return None
    for row in markets(_fetch):
        if row.get("symbol") == sym:
            last = float(row.get("last") or 0)
            mark = float(row.get("mark") or 0)
            price = last if last > 0 else (mark if mark > 0 else 0.0)
            if price <= 0:
                return None
            return {
                "symbol": sym,
                "market_id": row.get("market_id"),
                "last": price,
                "mark": mark if mark > 0 else price,
                "change_pct": float(row.get("change_pct") or 0),
            }
    return None
