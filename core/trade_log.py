# -*- coding: utf-8 -*-
"""
core/trade_log.py — دفتر سفارش‌های واقعی (audit log)
====================================================
هر سفارش «واقعی» که از صفحه‌ی ترید مستقیم ثبت می‌شود، بدون هیچ کلیدی
(صرافی/نماد/جهت/مقدار/قیمت/ارزش/سفارش‌آیدی) در جدول trade_log سوپابیس می‌رود.

چرا سخت‌گیریم؟
  * سقف روزانه و دوره‌ی گرم‌کردن فقط با این دفتر قابل راستی‌آزمایی است.
  * اگر دفتر در دسترس نباشد، core/trade_guard سقف = ۰ می‌دهد یعنی سفارشِ واقعی
    بسته است (Paper همیشه باز). این عمدی است: امنیت مقدم بر دسترسی.
  * خطاها هرگز به UI نمی‌ریزند؛ خروجی None/False/[] معنای «ناموفق/ناموجود» دارد.

نکته‌ی صادقانه: کلید سوپابیسِ اپ «عمومی» (publishable) است و RLS اجازه‌ی درج
ناشناس می‌دهد (همان سیاست arena_trades). یعنی کسی می‌تواند ردیف جعلی درج کند؛
بدترین سناریو پرشدن سقف روزانه و بسته‌ماندن سفارشِ واقعی همان روز است —
هیچ راهی برای برداشت پول یا دور زدن سقف از این مسیر وجود ندارد.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import streamlit as st

from core.community_store import _secrets_get  # همان الگوی خواندن env/secrets کل پروژه

TABLE = "trade_log"
FETCH_LIMIT = 500            # حداکثر ردیف در هر خواندن (کافی برای سقف روزانه و گرم‌کردن)
CACHE_TTL_SEC = 30           # کش کوتاه خواندن؛ بعد از هر درج باطل می‌شود
CONNECT_TIMEOUT_SEC = 10
COLS = "ts,exchange,symbol,side,otype,amount,price,notional,order_id,mode"

try:
    from supabase import create_client  # type: ignore
    SUPABASE_INSTALLED = True
except Exception:
    create_client = None  # type: ignore[assignment]
    SUPABASE_INSTALLED = False

_client: Any = None
_client_checked = False
_cache_rows: Optional[List[Dict[str, Any]]] = None
_cache_ts = 0.0
last_error: Optional[str] = None


def _get_client() -> Any:
    """کلاینت Supabase را فقط یک‌بار می‌سازد؛ نبود کلید/پکیج = None."""
    global _client, _client_checked
    if _client_checked:
        return _client
    _client_checked = True
    if not SUPABASE_INSTALLED:
        globals()["last_error"] = "پکیج supabase نصب نیست"
        return None
    url = _secrets_get("SUPABASE_URL")
    key = _secrets_get("SUPABASE_KEY")
    if not url or not key:
        globals()["last_error"] = "SUPABASE_URL / SUPABASE_KEY تنظیم نشده است"
        return None
    try:
        try:
            from supabase import ClientOptions  # type: ignore
            opts = ClientOptions(postgrest_client_timeout=CONNECT_TIMEOUT_SEC)
            _client = create_client(url, key, options=opts)
        except Exception:
            _client = create_client(url, key)
    except Exception as e:
        globals()["last_error"] = f"ساخت کلاینت Supabase ناموفق بود: {e}"
        _client = None
    return _client


def _reset_for_tests() -> None:
    """بین تست‌ها وضعیت ماژول را صفر می‌کند (بدون شبکه)."""
    global _client, _client_checked, _cache_rows, _cache_ts, last_error
    _client = None
    _client_checked = False
    _cache_rows = None
    _cache_ts = 0.0
    last_error = None


# ---------------------------------------------------------------- خواندن
def _fetch_recent(force: bool = False) -> Optional[List[Dict[str, Any]]]:
    """تازه‌ترین ردیف‌ها؛ کش کوتاه. هر خرابی = None (همیشه امن)."""
    global _cache_rows, _cache_ts, last_error
    now = time.monotonic()
    if not force and _cache_rows is not None and (now - _cache_ts) < CACHE_TTL_SEC:
        return _cache_rows
    client = _get_client()
    if client is None:
        return None
    try:
        res = (client.table(TABLE)
               .select(COLS)
               .order("ts", desc=True)
               .limit(FETCH_LIMIT)
               .execute())
        rows = res.data or []
        _cache_rows = [r for r in rows if isinstance(r, dict)]
        _cache_ts = now
        last_error = None
        return _cache_rows
    except Exception as e:
        last_error = f"خواندن دفتر سفارش‌ها ناموفق بود: {e}"
        return None


# ---------------------------------------------------------------- محاسبات خالص (تست‌پذیر بدون شبکه)
def _row_notional(r: Dict[str, Any]) -> float:
    try:
        v = float(r.get("notional") or 0)
        return v if (math.isfinite(v) and v > 0) else 0.0
    except Exception:
        return 0.0


def _row_ts(r: Dict[str, Any]) -> Optional[datetime]:
    try:
        s = str(r.get("ts") or "")
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _is_real_row(r: Dict[str, Any]) -> bool:
    return str(r.get("mode") or "real").strip().lower() in ("real", "")


def _sum_today(rows: Optional[List[Dict[str, Any]]], now: Optional[datetime] = None) -> float:
    """مجموع ارزش سفارش‌های واقعیِ امروز (مرز روز: UTC). ورودی خراب = ۰."""
    if not isinstance(rows, list):
        return 0.0
    n = now or datetime.now(timezone.utc)
    if n.tzinfo is None:
        n = n.replace(tzinfo=timezone.utc)
    start = n.replace(hour=0, minute=0, second=0, microsecond=0)
    total = 0.0
    for r in rows:
        if not isinstance(r, dict) or not _is_real_row(r):
            continue
        ts = _row_ts(r)
        if ts is None:
            continue
        if ts >= start:
            total += _row_notional(r)
    return total


def _count_real(rows: Optional[List[Dict[str, Any]]]) -> int:
    if not isinstance(rows, list):
        return 0
    return sum(1 for r in rows if isinstance(r, dict) and _is_real_row(r))


# ---------------------------------------------------------------- API عمومی
def todays_spent(now: Optional[datetime] = None) -> Optional[float]:
    """مجموع ارزش دلاری سفارش‌های واقعی امروز؛ دفتر در دسترس نیست = None."""
    rows = _fetch_recent()
    if rows is None:
        return None
    return _sum_today(rows, now)


def count_real_orders() -> Optional[int]:
    """تعداد کل سفارش‌های واقعی ثبت‌شده (داخل آخرین FETCH_LIMIT ردیف)."""
    rows = _fetch_recent()
    if rows is None:
        return None
    return _count_real(rows)


def recent(n: int = 20) -> List[Dict[str, Any]]:
    """آخرین n سفارش برای نمایش در UI؛ دفتر در دسترس نیست = []."""
    rows = _fetch_recent()
    if rows is None:
        return []
    keep = ("ts", "exchange", "symbol", "side", "otype",
            "amount", "price", "notional", "order_id", "mode")
    return [{k: r.get(k) for k in keep} for r in rows[: max(0, int(n))]]


def log_real_order(*, exchange, symbol, side, otype, amount, price,
                   notional_usd, order_id: str = "", mode: str = "real") -> bool:
    """درج یک سفارش واقعی در دفتر. موفق = True؛ هر خرابی = False (هرگز raise نمی‌کند)."""
    global _cache_rows, last_error
    client = _get_client()
    if client is None:
        return False
    try:
        amt = float(amount)
        nt = float(notional_usd)
        if not (math.isfinite(amt) and amt > 0):
            raise ValueError("amount نامعتبر")
        if not (math.isfinite(nt) and nt > 0):
            raise ValueError("notional نامعتبر")
        try:
            prc = float(price)
            if not math.isfinite(prc) or prc <= 0:
                prc = None
        except Exception:
            prc = None
        row = {
            "exchange": str(exchange or "")[:40],
            "symbol": str(symbol or "")[:40],
            "side": "buy" if str(side or "").lower() == "buy" else "sell",
            "otype": "limit" if str(otype or "").lower() == "limit" else "market",
            "amount": amt,
            "price": prc,
            "notional": round(nt, 2),
            "order_id": str(order_id or "")[:80],
            "mode": str(mode or "real")[:20],
        }
    except Exception as e:
        last_error = f"ردیف دفتر نامعتبر بود: {e}"
        return False
    try:
        client.table(TABLE).insert(row).execute()
        _cache_rows = None  # کش را باطل کن تا سقف روزانه بلافاصله به‌روز شود
        last_error = None
        return True
    except Exception as e:
        last_error = f"نوشتن دفتر سفارش‌ها ناموفق بود: {e}"
        return False


# ---------------------------------------------------------------- SQL راه‌اندازی
SETUP_SQL = """create table if not exists trade_log (
  id bigint generated always as identity primary key,
  ts timestamptz not null default now(),
  exchange text not null,
  symbol text not null,
  side text not null,
  otype text not null,
  amount numeric not null,
  price numeric,
  notional numeric not null,
  order_id text,
  mode text not null default 'real'
);
alter table trade_log enable row level security;
drop policy if exists "trade_log anon insert" on trade_log;
create policy "trade_log anon insert" on trade_log
  for insert to anon with check (true);
drop policy if exists "trade_log anon read" on trade_log;
create policy "trade_log anon read" on trade_log
  for select to anon using (true);"""
