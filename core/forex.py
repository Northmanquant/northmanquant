# -*- coding: utf-8 -*-
"""core/forex.py — بازار فارکس: قیمت زنده‌ی مِیجرها از یاهو فایننس + داده‌ی بروکرها
==================================================================================
چرا یاهو فایننس؟ بروکرهای MT4/MT5 (IC Markets، Opofinance، FOREX.com و…) API عمومی
برای قیمت ندارند (پکیج MetaTrader5 پایتون فقط ویندوز است و روی سرور لینوکسی نمی‌چرخد).
یاهو فایننس بدون توکن و ثبت‌نام، قیمت میان‌دلالی (mid) همان جفت‌ارزها را می‌دهد —
اسپرد هر بروکر فقط کمی حول همین mid باز می‌شود. پس برای «نمایش قیمت» منبع درستی است،
نه برای اجرای معامله.

طراحی همیشه مثل بقیه‌ی پروژه:
  • هیچ‌وقت exception به UI نشت نمی‌کند — خطا = None و پیام دوستانه
  • کش کوتاه (۶۰ ثانیه) تا نرخ محدودشدن یاهو نخوریم
  • داده‌ی بروکرها فقط از صفحات رسمی/بررسی‌های مستند — بدون رقم از خودمان
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import pandas as pd

from core.net import get_json

# ---------------------------------------------------------------------------
# جفت‌ارزهای مِیجر — نماد یاهو همیشه «<PAIR>=X» است
# ---------------------------------------------------------------------------
PAIRS: Dict[str, tuple[str, str]] = {
    # pair: (نام فارسی, نام انگلیسی)
    "EURUSD": ("یورو / دلار آمریکا", "Euro / US Dollar"),
    "GBPUSD": ("پوند انگلیس / دلار آمریکا", "British Pound / US Dollar"),
    "USDJPY": ("دلار آمریکا / ین ژاپن", "US Dollar / Japanese Yen"),
    "AUDUSD": ("دلار استرالیا / دلار آمریکا", "Australian Dollar / US Dollar"),
    "USDCAD": ("دلار آمریکا / دلار کانادا", "US Dollar / Canadian Dollar"),
}

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; northmanquant/1.0)",
            "accept": "application/json"}
_CACHE: Dict[str, Any] = {}          # pair -> (ts, quote)
_TTL = 60.0                          # ثانیه — کش مشترک برای همه‌ی تماس‌گیرنده‌ها


def yahoo_symbol(pair: str) -> str:
    """EURUSD → EURUSD=X (نماد یاهو)."""
    return f"{pair.upper().strip()}=X"


def decimals_for(price: float) -> int:
    """نرخ ارز: زیر ۵۰ → ۵ رقم اعشار (1.08423) · بالای ۵۰ → ۳ رقم (154.123)."""
    try:
        return 3 if float(price) >= 50 else 5
    except (TypeError, ValueError):
        return 5


def fmt_price(price: Optional[float]) -> str:
    """قیمت با تعداد اعشار درستِ بازار ارز؛ ورودی خراب = «—»."""
    p = float(price or 0)
    if p <= 0:
        return "—"
    return f"{p:.{decimals_for(p)}f}"


def _parse_chart(payload: Optional[dict], pair: str) -> Optional[dict]:
    """JSON اندپوینت chart یاهو → ردیف تمیز. هر چیزی غیبتش = None."""
    if not isinstance(payload, dict):
        return None
    chart = payload.get("chart") or {}
    if (chart.get("error") or {}).get("code"):
        return None
    rows = chart.get("result") or []
    if not rows:
        return None
    meta = rows[0].get("meta") or {}
    price = float(meta.get("regularMarketPrice") or 0)
    prev = float(meta.get("chartPreviousClose") or meta.get("previousClose") or 0)
    if price <= 0:
        return None
    chg = (price - prev) / prev * 100 if prev > 0 else 0.0
    fa, en = PAIRS.get(pair, (pair, pair))
    return {
        "pair": pair,
        "name_fa": fa,
        "name_en": en,
        "price": price,
        "prev_close": prev if prev > 0 else None,
        "change_pct": round(chg, 3),
        "currency": str(meta.get("currency") or ""),
        "ts": int(meta.get("regularMarketTime") or 0),
    }


def fetch_quote(pair: str, *, retries: int = 1, timeout: float = 8.0) -> Optional[dict]:
    """یک جفت‌ارز از یاهو — مستقیم و بدون کش. خطا = None (هیچ‌وقت raise نمی‌کند)."""
    p = pair.upper().strip()
    if p not in PAIRS:
        return None
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + yahoo_symbol(p)
    try:
        payload = get_json(url, params={"interval": "1m", "range": "1d"},
                           headers=_HEADERS, timeout=timeout, retries=retries)
    except Exception:  # noqa: BLE001 — شبکه/۴۰۳/پارس خراب: همه = بی‌قیمت
        return None
    return _parse_chart(payload, p)


def fx_quotes(force: bool = False) -> Dict[str, dict]:
    """همه‌ی مِیجرها با کش ۶۰ثانیه‌ای — خروجی: {pair: quote یا بدون کلید اگر نشد}."""
    now = time.time()
    out: Dict[str, dict] = {}
    stale: list[str] = []
    for pair in PAIRS:
        hit = _CACHE.get(pair)
        if not force and hit and now - hit[0] < _TTL:
            if hit[1]:
                out[pair] = hit[1]
        else:
            stale.append(pair)
    for pair in stale:
        q = fetch_quote(pair)
        _CACHE[pair] = (now, q)
        if q:
            out[pair] = q
    return out


# ---------------------------------------------------------------------------
# کندل چندتایم‌فریمی — همان اندپوینت chart یاهو با interval/range دیگر
# (سقف‌های مستند یاهو: 1m≤۷روز · 5m/15m/30m≤۶۰روز · 60m≤۷۳۰روز · 1d/1wk بلندمدت)
# ---------------------------------------------------------------------------
FX_TFS: Dict[str, tuple[str, str, int]] = {
    # tf_key: (interval یاهو, range یاهو, ضریب تجمیع) — تجمیع فقط برای ۴ساعت از ۶۰m
    "1min":  ("1m",  "1d",  1),
    "5min":  ("5m",  "5d",  1),
    "15min": ("15m", "5d",  1),
    "1hour": ("60m", "1mo", 1),
    "4hour": ("60m", "2mo", 4),
    "1day":  ("1d",  "1y",  1),
    "1week": ("1wk", "2y",  1),
}
_BASE_SEC = {"1m": 60, "2m": 120, "5m": 300, "15m": 900, "30m": 1800, "60m": 3600,
             "90m": 5400, "1h": 3600, "1d": 86400, "1wk": 604800}
_CANDLE_TTL = 120.0                          # کش کندل — جدا از کشِ ۶۰ثانیه‌ای quote
_CANDLE_CACHE: Dict[tuple, Any] = {}         # (pair, tf) -> (ts, rows | None)


def _parse_chart_candles(payload: Optional[dict], pair: str) -> Optional[List[List[Any]]]:
    """JSON chart یاهو → ردیف‌های [t,o,h,l,c,v] مرتب و تمیز. هر نقص = None (هرگز raise نمی‌کند).
    کندلِ ناقص (any OHLC خالی/غیرمثبت یا high<low) حذف می‌شود؛ ولوم غایب = ۰ (فارکس معمولاً ولوم ندارد)."""
    if not isinstance(payload, dict):
        return None
    chart = payload.get("chart") or {}
    if (chart.get("error") or {}).get("code"):
        return None
    results = chart.get("result") or []
    if not results:
        return None
    res = results[0] or {}
    ts = res.get("timestamp") or []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0] or {}
    o, h = q.get("open") or [], q.get("high") or []
    low, c = q.get("low") or [], q.get("close") or []
    v = q.get("volume") or []
    rows: Dict[int, List[Any]] = {}
    for i, t in enumerate(ts):
        try:
            ti = int(t)
            oi, hi, li, ci = o[i], h[i], low[i], c[i]
        except (IndexError, TypeError, ValueError):
            continue
        if oi is None or hi is None or li is None or ci is None:
            continue
        try:
            of, hf, lf, cf = float(oi), float(hi), float(li), float(ci)
        except (TypeError, ValueError):
            continue
        if min(of, hf, lf, cf) <= 0 or hf < lf:
            continue
        try:
            vf = float(v[i]) if i < len(v) and v[i] is not None else 0.0
        except (TypeError, ValueError):
            vf = 0.0
        rows[ti] = [ti, of, hf, lf, cf, vf]      # ts تکراری = نگه‌داشتنِ آخرین
    if not rows:
        return None
    return [rows[k] for k in sorted(rows)]


def _agg_candles(rows: List[List[Any]], base_sec: int, factor: int) -> List[List[Any]]:
    """تجمیع سمت سرور (۴ساعت از ۶۰m) — سبدبندی به مرز UTC (t - t % step) مثل resample داشبورد:
    open اولین · high بیشینه · low کمینه · close آخرین · volume جمع."""
    if factor <= 1 or not rows:
        return rows
    step = int(base_sec) * int(factor)
    out: Dict[int, List[Any]] = {}
    for t, o, h, l, c, v in rows:
        b = t - (t % step)
        cur = out.get(b)
        if cur is None:
            out[b] = [b, o, h, l, c, float(v or 0.0)]
        else:
            if h is not None and h > cur[2]:
                cur[2] = h
            if l is not None and l < cur[3]:
                cur[3] = l
            cur[4] = c
            cur[5] = float(cur[5] or 0.0) + float(v or 0.0)
    return [out[k] for k in sorted(out)]


def fetch_fx_candles(pair: str, tf: str, *, retries: int = 1, timeout: float = 10.0) -> Optional[List[List[Any]]]:
    """کندل یک تایم‌فریم — بدون کش. خطای شبکه/پارس/داده‌ی خالی = None (هرگز raise نمی‌کند)."""
    p, key = pair.upper().strip(), str(tf).lower().strip()
    if p not in PAIRS or key not in FX_TFS:
        return None
    interval, rng, agg = FX_TFS[key]
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + yahoo_symbol(p)
    try:
        payload = get_json(url, params={"interval": interval, "range": rng},
                           headers=_HEADERS, timeout=timeout, retries=retries)
    except Exception:  # noqa: BLE001 — شبکه/۴۰۳/پارس خراب: همه = بیداده
        return None
    rows = _parse_chart_candles(payload, p)
    if rows and agg > 1:
        rows = _agg_candles(rows, _BASE_SEC.get(interval, 3600), agg)
    return rows or None


def fx_candles(pair: str, force: bool = False, tfs: Optional[tuple] = None) -> Dict[str, list]:
    """بسته‌ی کندل چندتایم‌فریمی یک جفت‌ارز — کش ۱۲۰ثانیه‌ای per (pair, tf)، fetch موازی.
    خروجی: {tf: rows} — تایم‌فریم‌های ناموفق حذف می‌شوند (همان قرارداد tf_bundle داشبورد)."""
    p = pair.upper().strip()
    if p not in PAIRS:
        return {}
    want = tuple(tf for tf in (tfs or tuple(FX_TFS)) if tf in FX_TFS)
    now = time.time()
    out: Dict[str, list] = {}
    stale: List[str] = []
    for tf in want:
        hit = _CANDLE_CACHE.get((p, tf))
        if not force and hit and now - hit[0] < _CANDLE_TTL:
            if hit[1]:
                out[tf] = hit[1]
        else:
            stale.append(tf)
    if stale:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(6, len(stale))) as pool:
            got = dict(zip(stale, pool.map(lambda tf: fetch_fx_candles(p, tf), stale)))
        for tf, rws in got.items():
            _CANDLE_CACHE[(p, tf)] = (now, rws)      # شکست هم کش می‌شود (ضد rate-limit)
            if rws:
                out[tf] = rws
    return out


def candles_to_df(rows: List[List[Any]]) -> pd.DataFrame:
    """ردیف‌های [t,o,h,l,c,v] → DataFrame استاندارد داشبورد (dt/open/high/low/close/volume)
    برای موتور تحلیل (add_indicators/confluence/agents/plan)."""
    df = pd.DataFrame([list(r) for r in rows],
                      columns=["time", "open", "high", "low", "close", "volume"])
    for col in ("time", "open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = df["volume"].fillna(0.0)
    df["dt"] = pd.to_datetime(df["time"], unit="s")
    return df[["time", "open", "high", "low", "close", "volume", "dt"]]


# ---------------------------------------------------------------------------
# معرفی بروکرها — فقط ارقامِ مستند از صفحات رسمی/بررسی‌های منبع‌دار
# (بررسی‌شده: opofinance.com · ic.com · oanda.com · fxcm.com · forex.com
#  + fxscouts/investing/bestbrokers/wikifx — 2026-11)
# ---------------------------------------------------------------------------
BROKERS: List[Dict[str, str]] = [
    {
        "name": "OANDA",
        "hq_fa": "آمریکا", "hq_en": "USA",
        "founded": "1996",
        "regs_fa": "NFA/CFTC (آمریکا) · FCA (انگلیس) · ASIC (استرالیا)",
        "regs_en": "NFA/CFTC (US) · FCA (UK) · ASIC (Australia)",
        "min_dep_fa": "بدون حداقل (۰$)", "min_dep_en": "No minimum ($0)",
        "spread_fa": "پلن Core با کمیسیون — اسپرد پایین روی مِیجرها",
        "spread_en": "Core plan w/ commission — low major spreads",
        "leverage_fa": "تا 1:50 (آمریکا) · بیشتر در نهادهای جهانی",
        "leverage_en": "Up to 1:50 (US) · higher global entities",
        "platforms_fa": "OANDA Trade (اختصاصی) · MT4 · TradingView",
        "platforms_en": "OANDA Trade (own) · MT4 · TradingView",
        "demo_fa": "حساب تمرینی رایگان", "demo_en": "Free practice account",
        "url": "https://www.oanda.com",
        "note_fa": "یکی از قدیمی‌ترین و معتبرترین‌ها؛ مناسب حساب آمریکایی.",
        "note_en": "One of the oldest/most trusted; good for US accounts.",
    },
    {
        "name": "IC Markets (IC)",
        "hq_fa": "استرالیا", "hq_en": "Australia",
        "founded": "2007",
        "regs_fa": "ASIC (استرالیا) · CySEC (قبرس) · FSA (سیشل)",
        "regs_en": "ASIC (AU) · CySEC (CY) · FSA (Seychelles)",
        "min_dep_fa": "۲۰۰$", "min_dep_en": "$200",
        "spread_fa": "از 0.0 پیپ (Raw) + کمیسیون $7 رفت‌وبرگشت",
        "spread_en": "From 0.0 pips (Raw) + $7 round-turn commission",
        "leverage_fa": "تا 1:5000 (نهاد جهانی) · 1:30 نهاد اروپایی",
        "leverage_en": "Up to 1:5000 (global) · 1:30 (EU entity)",
        "platforms_fa": "MT4 · MT5 · cTrader · TradingView",
        "platforms_en": "MT4 · MT5 · cTrader · TradingView",
        "demo_fa": "حساب دمو رایگان", "demo_en": "Free demo",
        "url": "https://www.ic.com",
        "note_fa": "محبوب اسکالپرها و ربات‌ها؛ حجم معاملاتی بسیار بالا.",
        "note_en": "Popular with scalpers/robots; huge volumes.",
    },
    {
        "name": "FOREX.com",
        "hq_fa": "آمریکا (زیرمجموعه‌ی StoneX)", "hq_en": "USA (StoneX Group)",
        "founded": "2001",
        "regs_fa": "CFTC/NFA (آمریکا) · FCA (انگلیس) · CySEC (قبرس) · ASIC (استرالیا)",
        "regs_en": "CFTC/NFA (US) · FCA (UK) · CySEC (CY) · ASIC (AU)",
        "min_dep_fa": "۱۰۰$", "min_dep_en": "$100",
        "spread_fa": "پلن RAW: EURUSD تا 0.0 + کمیسیون $7/۱۰۰k",
        "spread_en": "RAW plan: EUR/USD to 0.0 + $7 per 100k",
        "leverage_fa": "تا 1:50 (آمریکا) · متغیر در نهادهای جهانی",
        "leverage_en": "Up to 1:50 (US) · varies globally",
        "platforms_fa": "پلتفرم اختصاصی · MT4 · MT5 · TradingView",
        "platforms_en": "Own web platform · MT4 · MT5 · TradingView",
        "demo_fa": "حساب دمو رایگان", "demo_en": "Free demo",
        "url": "https://www.forex.com",
        "note_fa": "برند بزرگ آمریکایی زیرمجموعه‌ی StoneX (نزدک).",
        "note_en": "Major US brand owned by Nasdaq-listed StoneX.",
    },
    {
        "name": "FXCM",
        "hq_fa": "انگلیس", "hq_en": "UK",
        "founded": "1999",
        "regs_fa": "FCA (انگلیس) · ASIC (استرالیا) · CySEC (قبرس) · FSCA (آفریقای جنوبی)",
        "regs_en": "FCA (UK) · ASIC (AU) · CySEC (CY) · FSCA (ZA)",
        "min_dep_fa": "۵۰$", "min_dep_en": "$50",
        "spread_fa": "EURUSD میانگین ~0.3 پیپ (حساب فعال)",
        "spread_en": "EUR/USD ~0.3 pips avg (active account)",
        "leverage_fa": "تا 1:400 (نهاد جهانی) · 1:30 نهاد اروپایی",
        "leverage_en": "Up to 1:400 (global) · 1:30 (EU entity)",
        "platforms_fa": "Trading Station · MT4 · TradingView",
        "platforms_en": "Trading Station · MT4 · TradingView",
        "demo_fa": "حساب دمو رایگان", "demo_en": "Free demo",
        "url": "https://www.fxcm.com",
        "note_fa": "حداقل واریز کم؛ سابقه‌ی طولانی و ابزارهای الگوریتمی.",
        "note_en": "Low minimum; long track record, algo tools.",
    },
    {
        "name": "Opofinance",
        "hq_fa": "استرالیا / سیشل", "hq_en": "Australia / Seychelles",
        "founded": "2021",
        "regs_fa": "ASIC AFSL 402043 · FSA سیشل SD124 · FSCA آفریقای جنوبی 54594 · عضو Financial Commission",
        "regs_en": "ASIC AFSL 402043 · FSA (SC) SD124 · FSCA (ZA) 54594 · Financial Commission member",
        "min_dep_fa": "۱۰۰$", "min_dep_en": "$100",
        "spread_fa": "ECN: میانگین ~0.7 پیپ + کمیسیون؛ استاندارد اسپرددار",
        "spread_en": "ECN ~0.7 pips avg + commission; Standard spread-based",
        "leverage_fa": "تا 1:2000",
        "leverage_en": "Up to 1:2000",
        "platforms_fa": "MT4 · MT5 · cTrader · TradingView · اپ اختصاصی",
        "platforms_en": "MT4 · MT5 · cTrader · TradingView · Own app",
        "demo_fa": "حساب دمو رایگان", "demo_en": "Free demo",
        "url": "https://opofinance.com",
        "note_fa": "⚠️ جوان‌ترین لیست؛ بخش بزرگی از عملیات ذیل نهادهای آفشور (سیشل/سانت‌وینسنت) است — برای مبالغ بزرگ محتاط باش.",
        "note_en": "⚠️ Newest of the list; much of its activity runs under offshore entities (Seychelles/SVG) — be careful with large funds.",
    },
]


def _platforms(b: Dict[str, str], en: bool) -> str:
    """پلتفرم‌ها — اگر نسخه‌ی زبانی جدا داشت، همان؛ وگرنه مقدار مشترک."""
    return b.get("platforms_en" if en else "platforms_fa") or b.get("platforms", "—")


def broker_rows(lang: str = "fa") -> List[List[str]]:
    """ردیف‌های جدول مقایسه — ستون‌ها: بروکر/تأسیس/مدارک/حداقل واریز/اسپرد/اهرم/پلتفرم/دمو."""
    en = lang == "en"
    rows: List[List[str]] = []
    for b in BROKERS:
        rows.append([
            b["name"],
            b.get("founded", "—"),
            b.get("regs_en" if en else "regs_fa", "—"),
            b.get("min_dep_en" if en else "min_dep_fa", "—"),
            b.get("spread_en" if en else "spread_fa", "—"),
            b.get("leverage_en" if en else "leverage_fa", "—"),
            _platforms(b, en),
            b.get("demo_en" if en else "demo_fa", "—"),
        ])
    return rows


def broker_table_html(lang: str = "fa") -> str:
    """جدول مقایسه به‌صورت HTML با استایل تم-مستقل (روشن/تیره) — RTL برای فارسی."""
    en = lang == "en"
    dir_ = "ltr" if en else "rtl"
    headers = (["Broker", "Founded", "Regulation", "Min Deposit", "Spread", "Max Leverage",
                "Platforms", "Demo"] if en else
               ["بروکر", "تأسیس", "مدارک نظارتی", "حداقل واریز", "اسپرد", "حداکثر اهرم",
                "پلتفرم‌ها", "حساب دمو"])
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = ""
    for b in BROKERS:
        note = b.get("note_en" if en else "note_fa", "")
        link = f'<a href="{b["url"]}" target="_blank" rel="noopener">{b["url"].replace("https://", "")}</a>'
        cells = [
            f'<b>{b["name"]}</b><br><span class="nq-url">{link}</span>',
            b.get("founded", "—"),
            b.get("regs_en" if en else "regs_fa", "—"),
            b.get("min_dep_en" if en else "min_dep_fa", "—"),
            b.get("spread_en" if en else "spread_fa", "—"),
            b.get("leverage_en" if en else "leverage_fa", "—"),
            _platforms(b, en),
            b.get("demo_en" if en else "demo_fa", "—"),
        ]
        tds = "".join(f"<td>{c}</td>" for c in cells)
        body += f"<tr>{tds}</tr>"
        if note:
            body += f'<tr class="nq-note-row"><td colspan="8" class="nq-note">{note}</td></tr>'
    return (
        f'<div class="nq-fx-wrap" dir="{dir_}">'
        f'<table class="nq-fx-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
        f'<style>'
        f'.nq-fx-wrap{{overflow-x:auto;}}'
        f'.nq-fx-table{{border-collapse:collapse;width:100%;font-size:0.86rem;line-height:1.5;}}'
        f'.nq-fx-table th,.nq-fx-table td{{border:1px solid rgba(128,128,128,.35);padding:8px 10px;'
        f'vertical-align:top;text-align:{"left" if en else "right"};}}'
        f'.nq-fx-table thead th{{background:rgba(120,120,160,.18);font-weight:700;white-space:nowrap;}}'
        f'.nq-fx-table .nq-note{{color:var(--text-color,inherit);opacity:.75;font-size:.8rem;'
        f'background:rgba(255,180,80,.06);}}'
        f'.nq-fx-table a{{word-break:break-all;}}'
        f'</style>'
    )
