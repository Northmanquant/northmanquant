# -*- coding: utf-8 -*-
"""core/tse.py — کلاینت عمومیِ بورس تهران (TSETMC) بدون کلید
=============================================================
منبع: سرورهای عمومی TSETMC (همان مسیرهایی که خود سایت استفاده می‌کند؛
الگوی پارس از سورس pytse-client 0.19.1 برداشته شده است):

  · دیده‌بان بازار:  tsev2/data/MarketWatchInit.aspx?h=0&r=0
  · جست‌وجوی نماد:  tsev2/data/search.aspx?skey=…
  · تاریخ روزانه:   tsev2/data/Export-txt.aspx?t=i&a=1&b=0&i={insCode}
  · اسنپ‌شات زنده:  tsev2/data/instinfofast.aspx?i={insCode}&c=0&e=1
  · تاریخ شاخص:     tsev2/chart/data/IndexFinancial.aspx?i={insCode}&t=ph

نکته‌ی مهم دسترسی: سرورهای TSETMC اتصالِ برخی IPهای خارج از ایران را
بسته‌اند؛ روی Streamlit Community Cloud ممکن است این بخش داده نگیرد.
پس: ۱) زنجیره‌ی آینه (old → www → cdn) امتحان می‌شود، ۲) اگر هیچ‌کدام
جواب نداد، پیام صادقانه در `last_error` می‌نشیند و UI با «چرا داده نیامد»
روشن می‌کند. اجرای لوکال از داخل ایران همیشه کار می‌کند.

الگوی پروژه: هیچ تابعی exception به UI نمی‌اندازد — ورودی/شبکه‌ی خراب =
[] / {} / DataFrame خالی. همه‌ی توابع با fetch تزریقی بدون شبکه تست‌پذیرند.
"""
from __future__ import annotations

import csv
import io
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

try:
    from zoneinfo import ZoneInfo
    TZ_TEHRAN = ZoneInfo("Asia/Tehran")
except Exception:  # noqa: BLE001 — بدون tzdata هم کار کند
    TZ_TEHRAN = timezone(timedelta(hours=3, minutes=30))

from core.net import get_text

# ---------------------------------------------------------------- ثابت‌ها
HOSTS = ("https://old.tsetmc.com", "https://www.tsetmc.com", "https://cdn.tsetmc.com")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/169.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}
FETCH_TIMEOUT = (2.5, 6.0)  # (اتصال، خواندن) — هر دامنه‌ی TSETMC دو IP دارد؛
# اتصالِ کوتاه یعنی IP بسته‌شده زود رد می‌شود (~۵ ثانیه به‌جای ~۱۷)، خواندنِ بلند
# برای فایل سنگین دیده‌بان روی اینترنتِ ایران امن است.

# کدهای ابزار شاخص‌ها (ثابت و پایدار در TSETMC)
INDEXES: Dict[str, str] = {
    "شاخص کل": "320978457643",
    "شاخص هم‌وزن": "67131131154793864",
}

MARKET_WATCH_TTL = 45.0     # دیده‌بان سنگین است (چند مگابایت) — کش کوتاه
HISTORY_TTL = 3600.0        # تاریخ روزانه روزی یک‌بار عوض می‌شود
SNAPSHOT_TTL = 20.0         # اسنپ‌شات زنده

# کدهای وضعیت نماد در TSETMC (فیلد [1] instinfofast) — پرکاربردها
STATE_FA = {
    "A": "مجاز", "B": "مجاز", "I": "متوقف", "G": "محفوظ",
    "R": "محدود دامنه", "AS": "مجاز-اطلاعیه",
}

_TextFetch = Callable[..., str]

_cache: Dict[str, Any] = {}
last_error: Optional[str] = None


def _reset_for_tests() -> None:
    """بین تست‌ها وضعیت ماژول صفر می‌شود (بدون شبکه)."""
    global _cache, last_error
    _cache = {}
    last_error = None


# ---------------------------------------------------------------- نرمال‌سازی فارسی
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_AR_TO_FA = str.maketrans({"ي": "ی", "ك": "ک", "ة": "ه", "\u200f": "", "\u200e": ""})


def norm_fa(s: Any) -> str:
    """ي→ی · ك→ک · ارقام فارسی→لاتین — برای نمایش و کلید یکسان."""
    return str(s or "").translate(_AR_TO_FA).translate(_FA_DIGITS).strip()


def _num(v: Any, default: float = 0.0) -> float:
    """فیلد متنی عددی TSETMC → float (خالی/F/خراب = default)."""
    try:
        s = norm_fa(v).replace(",", "")
        if s in ("", "-", "F", "nan"):
            return default
        return float(s)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- لایه‌ی fetch با آینه
def _fetch_text(path: str, _fetch: Optional[_TextFetch] = None,
                timeout: "float | tuple" = FETCH_TIMEOUT) -> str:
    """مسیر tsev2 را روی همه‌ی آینه‌ها «موازی» می‌کوبد؛ اولین پاسخِ غیرخالی
    برمی‌گردد (سریع‌ترین آینه‌ی سالم). دلیل: وقتی IP خارج از ایران بسته است،
    اتصال تا timeout معلق می‌ماند و امتحانِ پشت‌سرهم تا ~۵۰ ثانیه طول می‌کشد؛
    مسابقه‌ی موازی همان را به چند ثانیه می‌رساند.
    همه‌ی آینه‌ها شکست خوردند = رشته‌ی خالی + پیام صادقانه در last_error."""
    global last_error
    fetch = _fetch or get_text
    errs: List[str] = []
    pool = ThreadPoolExecutor(max_workers=len(HOSTS),
                              thread_name_prefix="tse-mirror")
    try:
        futs = {pool.submit(fetch, host + path, headers=HEADERS,
                            timeout=timeout, retries=0): host for host in HOSTS}
        for fut in as_completed(futs):
            host = futs[fut]
            try:
                txt = fut.result()
                if txt and str(txt).strip():
                    last_error = None
                    return str(txt)
                errs.append(f"{host}: پاسخ خالی")
            except Exception as e:  # noqa: BLE001
                errs.append(f"{host}: {type(e).__name__}")
    finally:
        # منتظر بقیه‌ی آینه‌ها نمی‌مانیم — برنده برگشته است
        pool.shutdown(wait=False, cancel_futures=True)
    last_error = ("سرورهای بورس تهران پاسخ ندادند (" + " · ".join(errs[:2]) + ") — "
                  "احتمالاً دسترسی از خارج از ایران بسته است؛ اجرای لوکال از داخل ایران کار می‌کند.")
    return ""


def _cache_get(key: str, ttl: float) -> Any:
    row = _cache.get(key)
    if row and (time.monotonic() - row[0]) < ttl:
        return row[1]
    return None


def _cache_put(key: str, val: Any) -> Any:
    _cache[key] = (time.monotonic(), val)
    return val


# ---------------------------------------------------------------- دیده‌بان بازار
def _parse_market_watch(raw: str) -> List[Dict[str, Any]]:
    """MarketWatchInit: سکشن‌های '@'؛ بزرگ‌ترین سکشن با ردیف‌های ≥۲۰ فیلد
    همان دیده‌بان اصلی است (الگوی stats.py از pytse-client)."""
    rows_out: List[Dict[str, Any]] = []
    if not raw or "@" not in raw:
        return rows_out
    best: List[List[str]] = []
    for section in raw.split("@"):
        cand = [r.split(",") for r in section.split(";")
                if r.count(",") >= 19]
        if len(cand) > len(best):
            best = cand
    for f in best:
        try:
            ins = f[0].strip()
            sym = norm_fa(f[2])
            if not ins or not sym:
                continue
            last = _num(f[7])
            yes = _num(f[13])
            rows_out.append({
                "ins_code": ins,
                "symbol": sym,
                "name": norm_fa(f[3]),
                "open": _num(f[5]),
                "adj_close": _num(f[6]),          # قیمت پایانی
                "last": last,
                "n_trades": int(_num(f[8])),
                "volume": _num(f[9]),
                "value": _num(f[10]),              # ریال
                "low": _num(f[11]),
                "high": _num(f[12]),
                "yesterday": yes,
                "eps": _num(f[14]),
                "base_vol": _num(f[15]),
                "group": f[18].strip() if len(f) > 18 else "",
                "max_allowed": _num(f[19]) if len(f) > 19 else 0.0,
                "min_allowed": _num(f[20]) if len(f) > 20 else 0.0,
                "n_shares": _num(f[21]) if len(f) > 21 else 0.0,
                "change_pct": ((last - yes) / yes * 100.0) if (last > 0 and yes > 0) else 0.0,
            })
        except Exception:  # noqa: BLE001 — ردیف خراب را رد کن
            continue
    return rows_out


def market_watch(_fetch: Optional[_TextFetch] = None,
                 ttl: float = MARKET_WATCH_TTL) -> List[Dict[str, Any]]:
    """همه‌ی نمادهای بازار با کش کوتاه. خرابی = [] (هرگز raise نمی‌کند)."""
    hit = _cache_get("mw", ttl)
    if hit is not None:
        return hit
    raw = _fetch_text("/tsev2/data/MarketWatchInit.aspx?h=0&r=0", _fetch)
    rows = _parse_market_watch(raw)
    if rows:
        return _cache_put("mw", rows)
    return []


# ---------------------------------------------------------------- جست‌وجو
def _parse_search(raw: str) -> List[Dict[str, Any]]:
    """search.aspx?skey=… → ردیف‌ها ';' و فیلدها ','؛ فیلد ۸ = فعال بودن."""
    out: List[Dict[str, Any]] = []
    if not raw:
        return out
    for r in raw.split(";"):
        f = r.split(",")
        if len(f) < 8:
            continue
        sym = norm_fa(f[0])
        ins = f[2].strip()
        if not sym or not ins or not ins.isnumeric():
            continue
        if f[7].strip() != "1":          # فقط نماد فعال (کدهای قدیمی حذف)
            continue
        out.append({"symbol": sym, "name": norm_fa(f[1]), "ins_code": ins})
    return out


def search(query: str, _fetch: Optional[_TextFetch] = None) -> List[Dict[str, Any]]:
    """جست‌وجوی نماد بر اساس نام فارسی/لاتین. خالی → فیلتر محلیِ دیده‌بان."""
    q = norm_fa(query)
    if not q:
        return []
    from urllib.parse import quote
    raw = _fetch_text("/tsev2/data/search.aspx?skey=" + quote(q), _fetch)
    rows = _parse_search(raw)
    if rows:
        return rows
    # fallback: فیلتر محلی روی دیده‌بان (کش‌شده)
    mw = market_watch(_fetch)
    ql = q.lower()
    return [r for r in mw if ql in r["symbol"].lower() or q in r["name"]][:20]


# ---------------------------------------------------------------- تاریخ روزانه
_HISTORY_MAP = {
    "<DTYYYYMMDD>": "dt", "<FIRST>": "open", "<HIGH>": "high", "<LOW>": "low",
    "<LAST>": "close", "<VOL>": "volume", "<CLOSE>": "adj_close",
    "<OPENINT>": "count", "<VALUE>": "value", "<OPEN>": "yesterday",
}


def _parse_history_csv(raw: str) -> pd.DataFrame:
    """Export-txt (متن CSV با ستون‌های <…>) → دیتافریم تمیز صعودی بر تاریخ."""
    cols_needed = ["dt", "open", "high", "low", "close", "volume"]
    if not raw or "<DTYYYYMMDD>" not in raw:
        return pd.DataFrame(columns=cols_needed)
    try:
        rdr = csv.DictReader(io.StringIO(raw))
        rows: List[Dict[str, Any]] = []
        for row in rdr:
            rec: Dict[str, Any] = {}
            for k, v in row.items():
                name = _HISTORY_MAP.get((k or "").strip().upper())
                if name:
                    rec[name] = _num(v)
            if not rec.get("dt"):
                continue
            rows.append(rec)
        if not rows:
            return pd.DataFrame(columns=cols_needed)
        df = pd.DataFrame(rows)
        df["dt"] = df["dt"].astype(int)
        df = df.sort_values("dt").reset_index(drop=True)
        df["date"] = pd.to_datetime(df["dt"].astype(str), format="%Y%m%d")
        return df
    except Exception:  # noqa: BLE001
        return pd.DataFrame(columns=cols_needed)


def history(ins_code: str, _fetch: Optional[_TextFetch] = None,
            ttl: float = HISTORY_TTL) -> pd.DataFrame:
    """کل تاریخ روزانه‌ی یک نماد (باز/بسته/حجم/قیمت پایانی). خرابی = df خالی."""
    ins = str(ins_code or "").strip()
    if not ins:
        return pd.DataFrame(columns=["dt", "open", "high", "low", "close", "volume"])
    key = f"hist_{ins}"
    hit = _cache_get(key, ttl)
    if hit is not None:
        return hit
    raw = _fetch_text(f"/tsev2/data/Export-txt.aspx?t=i&a=1&b=0&i={ins}", _fetch)
    df = _parse_history_csv(raw)
    if not df.empty:
        return _cache_put(key, df)
    return df


# ---------------------------------------------------------------- اسنپ‌شات زنده
def _parse_instinfo(raw: str) -> Dict[str, Any]:
    """instinfofast: سکشن ۰ = قیمت‌ها. فیلدها: 2=آخرین 3=پایانی 4=باز 5=دیروز
    6=سقف 7=کف 8=تعداد 9=حجم 10=ارزش 12=تاریخ 13=ساعت."""
    if not raw or ";" not in raw:
        return {}
    try:
        f = raw.split(";")[0].split(",")
        if len(f) < 11:
            return {}
        last = _num(f[2])
        adj = _num(f[3])
        if last <= 0 and adj > 0:
            last = adj
        return {
            "state": norm_fa(f[1]),
            "last": last,
            "adj_close": adj,
            "open": _num(f[4]),
            "yesterday": _num(f[5]),
            "high": _num(f[6]),
            "low": _num(f[7]),
            "n_trades": int(_num(f[8])),
            "volume": _num(f[9]),
            "value": _num(f[10]),
            "date": norm_fa(f[12]) if len(f) > 12 else "",
            "time": norm_fa(f[13]) if len(f) > 13 else "",
        }
    except Exception:  # noqa: BLE001
        return {}


def snapshot(ins_code: str, _fetch: Optional[_TextFetch] = None,
             ttl: float = SNAPSHOT_TTL) -> Dict[str, Any]:
    """قیمت لحظه‌ای یک نماد/شاخص. خرابی = {} (هرگز raise نمی‌کند)."""
    ins = str(ins_code or "").strip()
    if not ins:
        return {}
    key = f"snap_{ins}"
    hit = _cache_get(key, ttl)
    if hit is not None:
        return hit
    raw = _fetch_text(f"/tsev2/data/instinfofast.aspx?i={ins}&c=0&e=1", _fetch)
    snap = _parse_instinfo(raw)
    if snap:
        return _cache_put(key, snap)
    return {}


def fix_index_scale(val: float, ref: float) -> float:
    """TSETMC مقدار شاخص را گاهی ×۱۰۰ یا ×۱۰۰۰ می‌فرستد؛ با مرجعِ تاریخ،
    مقیاس درست حدس زده می‌شود (نسبت باید به ~۱ برسد).
    ورودیِ خراب هرگز exception نمی‌دهد — دست‌نخورده برمی‌گردد."""
    try:
        v, r = float(val), float(ref)
    except (TypeError, ValueError):
        return val
    if r <= 0 or v <= 0:
        return v
    ratio = v / r
    if 0.98 <= ratio <= 1.02:
        return v
    for d in (100.0, 1000.0, 10.0, 10_000.0):
        if 0.98 <= (ratio / d) <= 1.02:
            return v / d
    return v


# ---------------------------------------------------------------- شاخص‌ها
def _index_history(ins: str, _fetch: Optional[_TextFetch] = None) -> pd.DataFrame:
    """تاریخ روزانه‌ی شاخص (IndexFinancial) با کش طولانی — مرجعِ مقیاس و fallback."""
    key = f"idxh_{ins}"
    hit = _cache_get(key, HISTORY_TTL)
    if hit is not None:
        return hit
    raw = _fetch_text(f"/tsev2/chart/data/IndexFinancial.aspx?i={ins}&t=ph", _fetch)
    df = _parse_index_history(raw)
    if df.empty:
        return df
    return _cache_put(key, df)


def indices(_fetch: Optional[_TextFetch] = None) -> Dict[str, Dict[str, Any]]:
    """شاخص کل و هم‌وزن: مقدار زنده + درصد تغییر نسبت به دیروز.
    مقدار زنده با مرجعِ تاریخ مقیاس‌درست می‌شود (TSETMC گاهی ×۱۰۰ می‌فرستد)؛
    اگر اسنپ‌شات زنده نیامد، از آخرین تاریخ شاخص استفاده می‌شود."""
    out: Dict[str, Dict[str, Any]] = {}
    for name, ins in INDEXES.items():
        dfh = _index_history(ins, _fetch)
        snap = snapshot(ins, _fetch)
        if snap:
            last = float(snap.get("last") or 0)
            if last > 0 and not dfh.empty:
                last = fix_index_scale(last, float(dfh.iloc[-1]["close"]))
            chg = 0.0
            if snap.get("yesterday"):
                chg = (last - float(snap["yesterday"])) / float(snap["yesterday"]) * 100.0
            out[name] = {"ins_code": ins, "last": last,
                         "change_pct": chg, "live": True}
            continue
        if dfh.empty:
            continue
        last_row = dfh.iloc[-1]
        prev = float(dfh.iloc[-2]["close"]) if len(dfh) > 1 else 0.0
        out[name] = {
            "ins_code": ins, "last": float(last_row["close"]),
            "change_pct": ((float(last_row["close"]) - prev) / prev * 100.0) if prev else 0.0,
            "live": False,
        }
    return out


def _parse_index_history(raw: str) -> pd.DataFrame:
    """IndexFinancial: ردیف‌ها ';' · فیلدها date,high,low,open,close,volume."""
    cols = ["dt", "high", "low", "open", "close", "volume"]
    if not raw or ";" not in raw:
        return pd.DataFrame(columns=cols)
    rows: List[Dict[str, Any]] = []
    for r in raw.split(";"):
        f = r.split(",")
        if len(f) < 5 or not norm_fa(f[0]).isnumeric():
            continue
        rows.append({"dt": int(_num(f[0])), "high": _num(f[1]), "low": _num(f[2]),
                     "open": _num(f[3]), "close": _num(f[4]),
                     "volume": _num(f[5]) if len(f) > 5 else 0.0})
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows).sort_values("dt").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["dt"].astype(str), format="%Y%m%d")
    return df


# ---------------------------------------------------------------- وضعیت بازار
def session_status(now: Optional[datetime] = None) -> Dict[str, Any]:
    """وضعیت باز/بسته‌ی بورس تهران. شنبه تا چهارشنبه ۰۸:۴۵ تا ۱۲:۳۰ (تهران).
    تعطیلات رسمی (مناسبت‌ها) از راه دور قابل تشخیص نیست — فقط الگوی هفتگی."""
    try:
        n = (now or datetime.now(timezone.utc)).astimezone(TZ_TEHRAN)
    except Exception:  # noqa: BLE001
        n = now or datetime.now(timezone.utc)
    wd = n.weekday()                       # Mon=0 … Sun=6
    trading_day = wd in (5, 6, 0, 1, 2)    # شنبه(5) تا چهارشنبه(2)
    minutes = n.hour * 60 + n.minute
    open_ = bool(trading_day and (8 * 60 + 45) <= minutes <= 12 * 60 + 30)
    return {"open": open_, "tehran": n, "trading_day": trading_day,
            "weekday": wd, "hhmm": f"{n.hour:02d}:{n.minute:02d}"}
