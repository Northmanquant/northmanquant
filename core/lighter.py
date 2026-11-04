# -*- coding: utf-8 -*-
"""
core/lighter.py — کلاینت عمومیِ صرافی Lighter (perp DEX)
=========================================================
فقط API عمومیِ بدون‌کلید: /api/v1/orderBookDetails (بازارها + قیمت آخر)،
/api/v1/orderBookOrders (بهترین bid/ask واقعی)، متادیتای بازارها.

نکته: ارسال سفارشِ واقعی روی لایتر در «core/lighter_real.py» است — با SDK رسمی
(lighter-sdk) و کلید API (نه کلید کیف‌پول). این ماژول عمومی و بدون‌کلید می‌ماند.

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
    _book_cache.clear()


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
def _int_or(v: Any, default: int) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


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
                # برای سفارش واقعی: مقیاس‌بندی و کف سفارش هر بازار
                "size_decimals": _int_or(r.get("supported_size_decimals"), 0),
                "price_decimals": _int_or(r.get("supported_price_decimals"), 0),
                "min_base": float(r.get("min_base_amount") or 0),
                "min_quote": float(r.get("min_quote_amount") or 0),
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


def market_meta(symbol: str, _fetch: Optional[_Fetch] = None) -> Optional[Dict[str, Any]]:
    """متادیتای کامل بازار برای سفارش واقعی: market_id، مقیاس‌بندی و کف سفارش.
    نماد ناشناخته/شبکه‌ی خراب = None."""
    sym = normalize(symbol)
    if not sym:
        return None
    for row in markets(_fetch):
        if row.get("symbol") == sym:
            mid = row.get("market_id")
            if mid is None:
                return None
            return {
                "symbol": sym,
                "market_id": int(mid),
                "size_decimals": int(row.get("size_decimals") or 0),
                "price_decimals": int(row.get("price_decimals") or 0),
                "min_base": float(row.get("min_base") or 0),
                "min_quote": float(row.get("min_quote") or 0),
                "status": str(row.get("status") or ""),
            }
    return None


# ---------------------------------------------------------------- دفتر سفارش (bid/ask واقعی)
BOOK_TTL_SEC = 8.0
_book_cache: Dict[str, Any] = {}          # market_id → {"bid","ask","ts"}


def _parse_book_top(data: Any) -> Optional[Dict[str, float]]:
    """پاسخ /api/v1/orderBookOrders → بهترین bid/ask. asks صعودی، bids نزولی."""
    try:
        ob = data if isinstance(data, dict) else {}
        asks = [float(a.get("price") or 0) for a in (ob.get("asks") or []) if isinstance(a, dict)]
        bids = [float(b.get("price") or 0) for b in (ob.get("bids") or []) if isinstance(b, dict)]
        asks = [p for p in asks if p > 0]
        bids = [p for p in bids if p > 0]
        if not asks or not bids:
            return None
        return {"bid": max(bids), "ask": min(asks)}
    except Exception:
        return None


def book_top(symbol: str, _fetch: Optional[_Fetch] = None, *, now: Optional[float] = None,
             ttl: float = BOOK_TTL_SEC) -> Optional[Dict[str, float]]:
    """بهترین bid/ask واقعی دفتر سفارش لایتر (نه last). خرابی = None — هرگز عدد ساختگی."""
    sym = normalize(symbol)
    if not sym:
        return None
    mid = market_id(sym, _fetch)
    if mid is None:
        return None
    fetch = _fetch or get_json
    n = float(now) if now is not None else time.monotonic()
    hit = _book_cache.get(str(mid))
    if hit and (n - float(hit.get("ts") or 0)) < ttl:
        return {"bid": float(hit["bid"]), "ask": float(hit["ask"])}
    try:
        data = fetch(f"{BASE}/api/v1/orderBookOrders",
                     params={"market_id": mid, "limit": 8},
                     headers=HEADERS, timeout=FETCH_TIMEOUT)
    except Exception:
        return None
    top = _parse_book_top(data)
    if top is None:
        return None
    _book_cache[str(mid)] = {**top, "ts": n}
    return top
