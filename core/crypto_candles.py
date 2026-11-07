# -*- coding: utf-8 -*-
"""
core/crypto_candles.py — کندل چندتایم‌فریمی کریپتو + نرخ فاندینگ لایتر
======================================================================
دیتای کندل از Binance spot (data-api.binance.vision — همان دامنه‌ای که داشبورد
برای قیمت استفاده می‌کند و روی Streamlit Cloud جواب می‌دهد) با اندپوینت رسمی
/api/v3/klines می‌آید؛ برای نمادهای پرپ لایتر (BTC، ETH، …) نمادِ معادل
spot («BTCUSDT») مرجع گرفته می‌شود و در UI صادقانه اعلام می‌شود.

نرخ فاندینگ لایتر از API عمومیِ /api/v1/funding-rates می‌آید — با کش کوتاه.

الگوی پروژه: هیچ تابعی exception به UI نمی‌اندازد — شبکه‌ی خراب/ورودی خراب =
None / {} و همه‌ی توابع با fetch تزریقی بدون شبکه تست‌پذیرند (مثل core/forex).
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.net import get_json
from core.lighter import BASE as LIGHTER_BASE, HEADERS as LIGHTER_HEADERS

# tf_key: (interval رسمی Binance, limit کندل) — همه‌ی بازه‌ها native هستند، تجمیع لازم نیست
TFS: Dict[str, Tuple[str, int]] = {
    "1min":  ("1m", 1000),
    "5min":  ("5m", 800),
    "15min": ("15m", 600),
    "1hour": ("1h", 500),
    "4hour": ("4h", 400),
    "1day":  ("1d", 365),
    "1week": ("1w", 260),
}
_BASE_SEC = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400,
             "1d": 86400, "1w": 604800}

_BINANCE_URL = "https://data-api.binance.vision/api/v3/klines"
_HEADERS = {"User-Agent": "Mozilla/5.0 (NorthmanQuant; crypto candles)"}
FETCH_TIMEOUT = 12.0
_CANDLE_TTL = 120.0                       # کش کندل — شکست هم کش می‌شود (ضد rate-limit)

_FUNDING_TTL = 60.0                       # کش نرخ فاندینگ لایتر
_CANDLE_CACHE: Dict[Tuple[str, str], Tuple[float, Optional[List[List[Any]]]]] = {}
_FUNDING_CACHE: Dict[str, Any] = {"rows": None, "ts": 0.0}   # کل لیست فاندینگ

_Fetch = Callable[..., Any]


def _reset_for_tests() -> None:
    """بین تست‌ها وضعیت ماژول صفر می‌شود (بدون شبکه)."""
    global _CANDLE_CACHE, _FUNDING_CACHE
    _CANDLE_CACHE = {}
    _FUNDING_CACHE = {"rows": None, "ts": 0.0}


def pair_symbol(base: str) -> str:
    """پایه → نماد spot مرجع Binance: «BTC» یا «BTC-USDT» → «BTCUSDT». خراب = «»."""
    s = str(base or "").strip().upper()
    if not s:
        return ""
    for sep in ("-", "/"):
        if sep in s:
            s = s.split(sep, 1)[0]
            break
    s = s.replace("USDT", "") if s.endswith("USDT") else s
    return (s + "USDT") if s else ""


def decimals_for(price: float) -> int:
    """دقت نمایش مناسب قیمت کریپتو — گستره‌ی خیلی وسیع (BTC تا ممکوین)."""
    try:
        p = float(price)
    except (TypeError, ValueError):
        return 4
    if p >= 1000:
        return 2
    if p >= 1:
        return 4
    if p >= 0.01:
        return 6
    return 8


# ---------------------------------------------------------------- پارس کندل
def _parse_klines(data: Any) -> List[List[Any]]:
    """پاسخ klines Binance → ردیف‌های [t,o,h,l,c,v] مرتب (t ثانیه). ردیف خراب حذف؛ خروجی خالی = []."""
    rows: Dict[int, List[Any]] = {}
    if not isinstance(data, list):
        return []
    for k in data:
        try:
            if not isinstance(k, (list, tuple)) or len(k) < 6:
                continue
            t = int(float(k[0]) / 1000)          # Binance: میلی‌ثانیه
            of, hf = float(k[1]), float(k[2])
            lf, cf = float(k[3]), float(k[4])
            try:
                vf = float(k[5])
            except (TypeError, ValueError):
                vf = 0.0
        except (TypeError, ValueError, IndexError):
            continue
        if min(of, hf, lf, cf) <= 0 or hf < lf:
            continue
        rows[t] = [t, of, hf, lf, cf, vf]        # ts تکراری = نگه‌داشتنِ آخرین
    return [rows[k] for k in sorted(rows)]


# ---------------------------------------------------------------- دریافت کندل
def fetch_candles(base: str, tf: str, *, _fetch: Optional[_Fetch] = None,
                  timeout: float = FETCH_TIMEOUT, retries: int = 1) -> Optional[List[List[Any]]]:
    """کندل یک تایم‌فریم — بدون کش. خطای شبکه/پارس/بازه‌ی ناشناخته/داده‌ی خالی = None."""
    b = str(base or "").strip().upper()
    key = str(tf or "").strip().lower()
    if not b or key not in TFS:
        return None
    sym = pair_symbol(b)
    if not sym:
        return None
    interval, limit = TFS[key]
    fetch = _fetch or get_json
    try:
        data = fetch(_BINANCE_URL, params={"symbol": sym, "interval": interval,
                                           "limit": int(limit)},
                     headers=_HEADERS, timeout=timeout, retries=retries)
    except Exception:  # noqa: BLE001 — شبکه/۴۰۳/پارس خراب: همه = بیداده
        return None
    return _parse_klines(data) or None


def candles_bundle(base: str, tfs: Optional[Tuple[str, ...]] = None, *,
                   force: bool = False, _fetch: Optional[_Fetch] = None,
                   now: Optional[float] = None) -> Dict[str, List[List[Any]]]:
    """بسته‌ی کندل چندتایم‌فریمی با کش ۱۲۰ثانیه‌ای per (base, tf) و fetch موازی.
    خروجی: {tf: rows} — تایم‌فریم‌های ناموفق حذف می‌شوند (همان قرارداد داشبورد)."""
    b = str(base or "").strip().upper()
    if not b:
        return {}
    want = tuple(tf for tf in (tfs or tuple(TFS)) if tf in TFS)
    n = float(now) if now is not None else time.time()
    out: Dict[str, List[List[Any]]] = {}
    stale: List[str] = []
    for tf in want:
        hit = _CANDLE_CACHE.get((b, tf))
        if not force and hit and (n - hit[0]) < _CANDLE_TTL:
            if hit[1]:
                out[tf] = hit[1]
        else:
            stale.append(tf)
    if stale:
        with ThreadPoolExecutor(max_workers=min(6, len(stale))) as pool:
            got = dict(zip(stale, pool.map(
                lambda tf: fetch_candles(b, tf, _fetch=_fetch), stale)))
        for tf, rows in got.items():
            _CANDLE_CACHE[(b, tf)] = (n, rows)   # شکست هم کش می‌شود (ضد rate-limit)
            if rows:
                out[tf] = rows
    return out


# ---------------------------------------------------------------- فاندینگ لایتر
def _parse_funding(data: Any) -> Dict[int, float]:
    """پاسخ /api/v1/funding-rates → {market_id: rate}. ردیف خراب حذف."""
    out: Dict[int, float] = {}
    if not isinstance(data, dict):
        return out
    raw = data.get("funding_rates")
    if not isinstance(raw, list):
        return out
    for r in raw:
        try:
            if not isinstance(r, dict):
                continue
            mid = r.get("market_id")
            rate = r.get("rate")
            if mid is None or rate is None:
                continue
            m = float(rate)
            if m == m and -1.0 <= m <= 1.0:      # NaN رد می‌شود؛ نرخِ غیرمنطقی هم
                out[int(mid)] = m
        except (TypeError, ValueError):
            continue
    return out


def funding_rate(market_id: int, *, _fetch: Optional[_Fetch] = None,
                 now: Optional[float] = None, ttl: float = _FUNDING_TTL) -> Optional[float]:
    """نرخ فاندینگ فعلی یک بازار لایتر (خام؛ مثلا 0.0001 = ۰٫۰۱٪ در هر بازه).
    بازار ناشناخته/شبکه‌ی خراب = None — هرگز عدد ساختگی."""
    try:
        mid = int(market_id)
    except (TypeError, ValueError):
        return None
    n = float(now) if now is not None else time.monotonic()
    fetch = _fetch or get_json
    if _FUNDING_CACHE["rows"] is None or (n - float(_FUNDING_CACHE["ts"] or 0)) >= ttl:
        try:
            data = fetch(f"{LIGHTER_BASE}/api/v1/funding-rates",
                         headers=LIGHTER_HEADERS, timeout=FETCH_TIMEOUT, retries=1)
            rows = _parse_funding(data)
            if rows:
                _FUNDING_CACHE["rows"] = rows
                _FUNDING_CACHE["ts"] = n
        except Exception:  # noqa: BLE001 — شبکه خراب = کشِ قبلی (اگر تازه باشد)
            pass
    rows = _FUNDING_CACHE["rows"]
    if not isinstance(rows, dict):
        return None
    return rows.get(mid)
