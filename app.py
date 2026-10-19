"""
NorthmanQuant v2 loader - v4
=============================
app_base.py = فایل اصلی خودت (دست نزن) — این فایل فقط روی آن «پچ» می‌زند.

چه چیزهایی این‌جا تزریق می‌شود:
  ۰) KCEX + رفرش ۲ ثانیه‌ی نوار زنده (مثل قبل)
  ۱) حذف دکمه‌ی شناور اشتراک‌گذاری
  ۲) «تنظیمات چارت» داخل «بازار و نماد» ادغام شد (یک اکسپندر در سایدبار)
  ۳) «ثبت تحلیل شخصی + تصویر تحلیل + تحلیل‌های کاربران» → یک بخش جداگانه با سه تب
  ۴) «فرصت‌های سودده» → اسکن خودکار با رفرش سریع + قیمت زنده‌ی هر نماد
  ۵) FVG و BVG در همگرایی، Neural Shell، چارت زنده (زون‌ها)، دفتر ایجنت‌ها، اسکنر و تصویر تحلیل

موتور FVG/BVG در core/gaps.py است (صفحه‌ی Agents Duel هم از همان استفاده می‌کند).
"""
from __future__ import annotations

import importlib
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import streamlit as st

import app_base as B

try:
    from core import gaps as G
except Exception:  # noqa: BLE001
    G = None

# =============================================================================
# 0) رجیستری توابع اصلی — تا با هر rerun لایه‌ی پچ روی پچ سوار نشود
# =============================================================================
_REG: dict = st.__dict__.setdefault("_nq_originals", {})


def _original(owner, name: str):
    key = (id(owner), name)
    if key not in _REG:
        _REG[key] = getattr(owner, name)
    return _REG[key]


_RUN: dict = {}          # وضعیت «همین اجرا» (در هر rerun کامل از نو ساخته می‌شود)

HEADERS = B.HEADERS
KCEX_BASE = "https://api.kcex.com"

if "KCEX" not in B.EXCHANGE_DOCS:
    B.EXCHANGE_DOCS["KCEX"] = "https://www.kcex.com/api-docs"

_orig_tick = _original(B, "fetch_tick")
_orig_inner = _original(B, "_fetch_candles")
_orig_tops = _original(B, "fetch_top_coins")


# =============================================================================
# 1) KCEX (مثل نسخه‌ی قبل)
# =============================================================================
def fetch_tick(exchange: str, symbol: str):
    if exchange == "KCEX":
        try:
            from core.exchanges.kcex import KCEXExchange
            d = KCEXExchange().get_ticker(symbol)
            if d:
                last = float(d.get("price") or d.get("last") or 0)
                if last > 0:
                    return {"price": last, "bid": float(d.get("bid") or 0), "ask": float(d.get("ask") or 0)}
        except Exception:
            pass
        s_dash = symbol.replace("/", "-").upper()
        s_nodash = s_dash.replace("-", "")
        for url, params in [
            (f"{KCEX_BASE}/api/v1/ticker", {"symbol": s_dash}),
            (f"{KCEX_BASE}/api/v1/market/ticker", {"symbol": s_nodash}),
            ("https://www.kcex.com/api/v1/ticker", {"symbol": s_dash}),
        ]:
            try:
                r = requests.get(url, params=params, headers=HEADERS, timeout=6)
                if r.status_code != 200:
                    continue
                j = r.json()
                d = j.get("data", j) if isinstance(j, dict) else {}
                if isinstance(d, list) and d:
                    d = d[0]
                last = float(d.get("last") or d.get("lastPrice") or d.get("price") or 0)
                bid = float(d.get("buy") or d.get("bid") or d.get("bidPx") or d.get("bestBid") or 0)
                ask = float(d.get("sell") or d.get("ask") or d.get("bestAsk") or 0)
                if last > 0 or (bid > 0 and ask > 0):
                    price = (bid + ask) / 2 if bid > 0 and ask > 0 else last
                    return {"price": price, "bid": bid, "ask": ask}
            except Exception:
                continue
        try:
            return _orig_tick("KuCoin", symbol)
        except Exception:
            return None
    return _orig_tick(exchange, symbol)


def _fetch_candles_patched(exchange: str, symbol: str, interval: str, limit: int = 500):
    if exchange == "KCEX":
        try:
            import ccxt
            if hasattr(ccxt, "kcex"):
                ex = ccxt.kcex({"enableRateLimit": True, "timeout": 15000})
                sym = symbol.upper().replace("-", "/")
                tfmap = {"15min": "15m", "1hour": "1h", "4hour": "4h", "1day": "1d", "1week": "1w"}
                ohlcv = ex.fetch_ohlcv(sym, timeframe=tfmap.get(interval, "1h"), limit=min(500, limit))
                rows = [{"time": int(x[0]), "open": float(x[1]), "high": float(x[2]), "low": float(x[3]),
                         "close": float(x[4]), "volume": float(x[5] or 0)} for x in ohlcv if x and x[4]]
                df = pd.DataFrame(rows)
                if len(df) >= 40:
                    df = df.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
                    df = df[df["close"] > 0].tail(limit).reset_index(drop=True)
                    df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
                    return df
        except Exception as e:
            print(f"KCEX candles err: {e}")
        return _orig_inner("KuCoin", symbol, interval, limit)
    return _orig_inner(exchange, symbol, interval, limit)


def fetch_top_coins_patched(exchange: str = "KuCoin", min_turnover: float = 1_000_000, limit: int = 15):
    if exchange == "KCEX":
        try:
            r = requests.get(f"{KCEX_BASE}/api/v1/market/tickers", headers=HEADERS, timeout=10)
            if r.status_code == 200:
                j = r.json()
                data = j.get("data", j)
                if isinstance(data, list) and data:
                    rows = []
                    for t in data:
                        sym = str(t.get("symbol", ""))
                        if "USDT" not in sym.upper():
                            continue
                        last = float(t.get("last") or t.get("lastPrice") or t.get("price") or 0)
                        ch = float(t.get("changeRate") or t.get("change") or 0)
                        chpct = ch * 100 if abs(ch) < 5 and ch != 0 else ch
                        rows.append({"symbol": sym.replace("/", "-"), "price": last, "change%": chpct,
                                     "high": float(t.get("high") or 0), "low": float(t.get("low") or 0),
                                     "turnoverM$": float(t.get("volValue") or t.get("volume") or 0) / 1e6})
                    df = pd.DataFrame(rows)
                    if not df.empty:
                        return {"gainers": df.sort_values("change%", ascending=False).head(limit).reset_index(drop=True),
                                "losers": df.sort_values("change%").head(limit).reset_index(drop=True),
                                "volume": df.sort_values("turnoverM$", ascending=False).head(limit).reset_index(drop=True)}
        except Exception as e:
            print(f"KCEX tops err: {e}")
        return _orig_tops("KuCoin", min_turnover, limit)
    return _orig_tops(exchange, min_turnover, limit)


B.fetch_tick = fetch_tick
B._fetch_candles = _fetch_candles_patched
B.fetch_top_coins = fetch_top_coins_patched


# =============================================================================
# 2) حافظه‌ی مشترک (بین rerunها و سشن‌ها) — کش سریع کندل و نتایج FVG/BVG
# =============================================================================
@st.cache_resource(show_spinner=False)
def _store() -> dict:
    return {"candles": {}, "gaps": {}, "lock": threading.Lock()}


def _gap_cached(d: pd.DataFrame) -> dict | None:
    """نتیجه‌ی gap_analysis را برای همین DataFrame (همین کندل آخر) نگه می‌دارد."""
    if G is None or d is None or len(d) < 5:
        return None
    try:
        key = (len(d), float(d["close"].iloc[-1]), float(d["high"].iloc[-1]), float(d["low"].iloc[-1]),
               float(d["close"].iloc[0]), str(d["dt"].iloc[-1]) if "dt" in d.columns else "")
    except Exception:  # noqa: BLE001
        key = None
    store = _store()["gaps"]
    if key is not None and key in store:
        return store[key]
    res = G.gap_analysis(d)
    if key is not None:
        if len(store) > 160:
            store.clear()
        store[key] = res
    return res


# =============================================================================
# 3) FVG / BVG → همگرایی (و در نتیجه Neural Shell، طرح معامله، اسکنر، تصویر تحلیل)
# =============================================================================
_orig_confluence = _original(B, "confluence")
W_FVG, W_BVG = 0.10, 0.06


def confluence_patched(d: pd.DataFrame):
    score, table = _orig_confluence(d)
    res = None
    try:
        res = _gap_cached(d)
    except Exception:  # noqa: BLE001
        res = None
    if res is None:
        return score, table
    fvg = pd.Series(res["fvg_score"], index=d.index).fillna(0)
    bvg = pd.Series(res["bvg_score"], index=d.index).fillna(0)
    new = (score * (1 - W_FVG - W_BVG) + fvg * 100 * W_FVG + bvg * 100 * W_BVG).clip(-100, 100)
    try:
        table = pd.concat([table, pd.DataFrame(G.table_rows(res))], ignore_index=True)
    except Exception:  # noqa: BLE001
        pass
    return new.round().astype(float), table


B.confluence = confluence_patched


# ---- دفتر ایجنت‌ها: دو ایجنت تازه (FVG و BVG) ----------------------------------
_orig_agent_signals = _original(B, "_agent_signals")


def _agent_signals_patched(d: pd.DataFrame) -> dict:
    out = _orig_agent_signals(d)
    try:
        res = _gap_cached(d)
        if res is not None:
            f, b = np.asarray(res["fvg_score"]), np.asarray(res["bvg_score"])
            out["FVG"] = np.where(f > 0.2, 1, np.where(f < -0.2, -1, 0))
            out["BVG"] = np.where(b > 0.2, 1, np.where(b < -0.2, -1, 0))
    except Exception:  # noqa: BLE001
        pass
    for a in B.AGENTS:
        out.setdefault(a["key"], np.zeros(len(d)))
    return out


B._agent_signals = _agent_signals_patched
if not any(a.get("key") == "FVG" for a in B.AGENTS):
    B.AGENTS.extend([
        {"key": "FVG", "name": "گپ ارزش FVG", "en": "FAIR VALUE GAP", "tag": "FV", "color": "#22c55e"},
        {"key": "BVG", "name": "گپ حجمی BVG", "en": "BODY-VOLUME GAP", "tag": "BV", "color": "#6366f1"},
    ])

_orig_agents_svg = _original(B, "build_agents_svg")


def _build_agents_svg_patched(cards, fee: float = 0.06):
    svg = _orig_agents_svg(cards, fee)
    try:
        m = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
        _RUN["agents_svg"] = svg
        _RUN["agents_svg_h"] = (int(m.group(2)) if m else 700) + 16
    except Exception:  # noqa: BLE001
        pass
    return svg


B.build_agents_svg = _build_agents_svg_patched

# ---- components.html: ارتفاع خودکار برای گرید ۸ ایجنتی + حذف iframe خالی ---------
_cv1 = importlib.import_module("streamlit.components.v1")
_orig_html = _original(_cv1, "html")


def _html_patched(body, height=None, *a, **kw):
    if isinstance(body, str):
        if not body.strip():
            return None  # دکمه‌ی شناور حذف شده → iframe خالی نساز
        svg = _RUN.get("agents_svg")
        if svg and svg in body:
            height = max(int(height or 0), int(_RUN.get("agents_svg_h", 720)))
    return _orig_html(body, height=height, *a, **kw)


_cv1.html = _html_patched

# ---- ۱) حذف دکمه‌ی شناور اشتراک‌گذاری ----------------------------------------------
B.floating_share = lambda *a, **k: ""


# =============================================================================
# 4) پچ‌های UI روی خود استریم‌لیت (سایدبار، بخش‌ها، متن‌ها، چارت)
# =============================================================================
MARKET_LABEL = "🏦 بازار و نماد"
CHART_LABEL = "📈 تنظیمات چارت"
SHARE_LABEL = "🔗 اشتراک‌گذاری"
OPPS_LABEL = "💎 فرصت‌های سودده"
MERGED_LABEL = "🧩 تحلیل‌ها (ثبت · تصویر · کاربران)"
MERGED_TABS = ["✍️ ثبت تحلیل شخصی", "🖼️ تصویر تحلیل", "👥 تحلیل‌های کاربران"]
NEW_SECTIONS = ["📊 تحلیل زنده", OPPS_LABEL, MERGED_LABEL, "🏆 برترین‌ها", "📰 اخبار", "📚 منابع داده"]

_st_expander = _original(st, "expander")
_st_radio = _original(st, "radio")
_st_selectbox = _original(st, "selectbox")
_st_checkbox = _original(st, "checkbox")
_st_caption = _original(st, "caption")
_st_info = _original(st, "info")
_st_success = _original(st, "success")
_st_plotly_chart = _original(st, "plotly_chart")


# ---- ۲) ادغام «تنظیمات چارت» در «بازار و نماد» ----------------------------------
def _expander_patched(label, expanded: bool = False, **kw):
    if label == MARKET_LABEL:
        exp = _st_expander("🏦 بازار، نماد و تنظیمات چارت", expanded=expanded, **kw)
        _RUN["market_exp"] = exp
        return exp
    if label == CHART_LABEL and _RUN.get("market_exp") is not None:
        return _RUN["market_exp"]          # ویجت‌های چارت داخل همان اکسپندر می‌نشینند
    if label == SHARE_LABEL:
        return _st_expander("🔗 لینک اپ (اختیاری)", expanded=expanded, **kw)
    return _st_expander(label, expanded=expanded, **kw)


st.expander = _expander_patched


# ---- ۳) یک بخش با سه تب برای تحلیل‌ها -----------------------------------------------
class _MergedSection(str):
    """رشته‌ای که با سه برچسب بخش «برابر» است و هر کدام را داخل تب خودش رندر می‌کند.
    main() در app_base فقط `section == "..."` را چک می‌کند؛ این کلاس همان چک را
    برای سه بخش True می‌کند و قبل از هر بلوک، کانتینر تب مربوطه را فعال می‌کند."""

    def __new__(cls, label: str, tab_labels: list[str]):
        obj = str.__new__(cls, label)
        obj._tab_labels = list(tab_labels)
        obj._tabs = None
        obj._active = None
        return obj

    __hash__ = str.__hash__

    def _close(self):
        if self._active is not None:
            try:
                self._active.__exit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
            self._active = None

    def _open(self, label: str):
        if self._tabs is None:
            st.caption("سه بخش «ثبت تحلیل شخصی»، «تصویر تحلیل» و «تحلیل‌های کاربران» این‌جا کنار هم هستند — تب‌ها را عوض کن.")
            self._tabs = dict(zip(self._tab_labels, st.tabs(self._tab_labels)))
        self._close()
        dg = self._tabs[label]
        dg.__enter__()
        self._active = dg

    def __eq__(self, other):
        if not isinstance(other, str):
            return False
        o = str(other)
        if o in self._tab_labels:
            try:
                self._open(o)
            except Exception:  # noqa: BLE001
                pass
            return True
        self._close()
        return str.__eq__(str(self), o)

    def __ne__(self, other):
        return not self.__eq__(other)


def _radio_patched(label, options=None, *a, **kw):
    if kw.get("key") == "nav_section" and options is not None and "📊 تحلیل زنده" in list(options):
        val = _st_radio(label, NEW_SECTIONS, *a, **kw)
        if val == MERGED_LABEL:
            _RUN["section"] = "merged"
            return _MergedSection(MERGED_LABEL, MERGED_TABS)
        if val == OPPS_LABEL:
            _RUN["section"] = "opps"
            return OPPS_LABEL + " ⚡زنده"   # با هیچ بلوکی در main() برابر نیست → خودمان رندر می‌کنیم
        _RUN["section"] = val
        return val
    return _st_radio(label, options, *a, **kw)


st.radio = _radio_patched


# ---- گرفتن تایم‌فریم/صرافی انتخاب‌شده (برای اسکنر زنده) ------------------------------
def _selectbox_patched(label, options=None, *a, **kw):
    val = _st_selectbox(label, options, *a, **kw)
    if label == "تایم‌فریم" and "interval" not in _RUN:
        _RUN["interval"] = val
    return val


st.selectbox = _selectbox_patched

_orig_normalize = _original(B, "normalize_symbol")


def _normalize_symbol_patched(raw: str, exchange: str = "KuCoin") -> str:
    out = _orig_normalize(raw, exchange)
    if "exchange" not in _RUN:
        _RUN["exchange"], _RUN["symbol_in"], _RUN["symbol"] = exchange, raw, out
    return out


B.normalize_symbol = _normalize_symbol_patched


# ---- متن‌ها: حذف اشاره به دکمه‌ی شناور، «بخش» → «تب»، رفرش ۲ ثانیه --------------------
_TEXT_MAP = [
    ("بخش «👥 تحلیل‌های کاربران»", "تب «👥 تحلیل‌های کاربران»"),
    ("بخش «✍️ ثبت تحلیل شخصی»", "تب «✍️ ثبت تحلیل شخصی»"),
    ("(بخش → ✍️ ثبت تحلیل شخصی)", "(تب «✍️ ثبت تحلیل شخصی»)"),
    ("قیمت هر ۵ ثانیه", "قیمت هر ۲ ثانیه"),
]


def _rw(text):
    if isinstance(text, str):
        for a, b in _TEXT_MAP:
            text = text.replace(a, b)
    return text


def _caption_patched(body, *a, **kw):
    if isinstance(body, str) and "دکمه‌ی شناور" in body:
        return None
    return _st_caption(_rw(body), *a, **kw)


def _info_patched(body, *a, **kw):
    return _st_info(_rw(body), *a, **kw)


def _success_patched(body, *a, **kw):
    return _st_success(_rw(body), *a, **kw)


def _checkbox_patched(label, *a, **kw):
    return _st_checkbox(_rw(label), *a, **kw)


st.caption = _caption_patched
st.info = _info_patched
st.success = _success_patched
st.checkbox = _checkbox_patched


# ---- ۵) زون‌های FVG/BVG روی چارت زنده‌ی Plotly ----------------------------------------
def _overlay_gaps(fig) -> None:
    if G is None:
        return
    cs = next((t for t in fig.data if getattr(t, "type", "") == "candlestick"), None)
    if cs is None or cs.x is None or len(cs.x) < 20:
        return
    df = pd.DataFrame({
        "dt": list(cs.x),
        "open": np.asarray(cs.open, dtype=float), "high": np.asarray(cs.high, dtype=float),
        "low": np.asarray(cs.low, dtype=float), "close": np.asarray(cs.close, dtype=float),
    })
    bar = next((t for t in fig.data if getattr(t, "type", "") == "bar"), None)
    df["volume"] = np.asarray(bar.y, dtype=float) if bar is not None and bar.y is not None and len(bar.y) == len(df) else 1.0
    res = G.gap_analysis(df)
    price = float(df["close"].iloc[-1])
    shapes, notes = G.plotly_shapes(res, x_end=df["dt"].iloc[-1], price=price)
    for s in shapes:
        fig.add_shape(**s)
    for nte in notes:
        fig.add_annotation(**nte)
    fi, bi = res["fvg_info"], res["bvg_info"]
    fig.add_annotation(
        xref="paper", yref="paper", x=0, y=1.0, xanchor="left", yanchor="bottom", showarrow=False,
        text=(f"FVG ▲▼ سبز/قرمز ({fi['active_bull']}🟢 {fi['active_bear']}🔴 فعال) · "
              f"BVG ▲▼ آبی/بنفش ({bi['active_bull']}🟢 {bi['active_bear']}🔴 فعال)"),
        font=dict(size=10, color="#94a3b8"),
    )


def _plotly_chart_patched(fig, *a, **kw):
    try:
        _overlay_gaps(fig)
    except Exception:  # noqa: BLE001
        pass
    return _st_plotly_chart(fig, *a, **kw)


st.plotly_chart = _plotly_chart_patched


# =============================================================================
# 5) نوار زنده‌ی ۲ ثانیه‌ای (مثل قبل)
# =============================================================================
try:
    B.live_strip_auto = st.fragment(run_every=2)(B._live_strip_impl)
    B.live_strip_manual = st.fragment(B._live_strip_impl)
except Exception:
    pass


# =============================================================================
# 6) فرصت‌های سودده — اسکن خودکار + قیمت زنده با رفرش سریع
# =============================================================================
FAST_TTL = 12          # ثانیه؛ کش کندل برای اسکنر (به‌جای ۶۰–۱۲۰ ثانیه‌ی قبلی)
DEFAULT_POOL = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT",
                "DOGE-USDT", "ADA-USDT", "AVAX-USDT", "LINK-USDT", "TRX-USDT"]


def _candles_raw(exchange: str, symbol: str, interval: str, limit: int) -> pd.DataFrame:
    """کندل بدون کش ۶۰ ثانیه‌ای (برای رفرش سریع)؛ در صورت خطا به زنجیره‌ی fallback اصلی برمی‌گردد."""
    if exchange == "KCEX":
        return _fetch_candles_patched(exchange, symbol, interval, limit)
    if exchange in B.EXCHANGES:
        raw = getattr(_orig_inner, "__wrapped__", None)
        if callable(raw):
            try:
                return raw(exchange, symbol, interval, limit)
            except Exception:  # noqa: BLE001
                pass
    return B.fetch_candles(exchange, symbol, interval, limit)


def _fast_candles(store: dict, exchange: str, symbol: str, interval: str, limit: int = 300) -> pd.DataFrame:
    key = (exchange, symbol, interval, limit)
    now = time.time()
    hit = store["candles"].get(key)
    if hit and now - hit[0] < FAST_TTL:
        return hit[1]
    df = _candles_raw(exchange, symbol, interval, limit)
    with store["lock"]:
        if len(store["candles"]) > 400:
            store["candles"].clear()
        store["candles"][key] = (now, df)
    return df


def _scan_fast(exchange: str, interval: str, top_n: int, min_abs: int) -> tuple[pd.DataFrame, dict]:
    store = _store()
    try:
        movers = B.fetch_top_coins(exchange, 1_000_000, 40)
        pool = pd.concat([movers["volume"], movers["gainers"], movers["losers"]]).drop_duplicates("symbol")
        symbols = pool["symbol"].head(top_n * 3).tolist()
    except Exception:  # noqa: BLE001
        symbols = DEFAULT_POOL
    syms = []
    for s in symbols:
        try:
            syms.append(B.normalize_symbol(s, exchange))
        except Exception:  # noqa: BLE001
            continue
    frames: dict[str, pd.DataFrame] = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(_fast_candles, store, exchange, s, interval, 300): s for s in syms}
        try:
            for fut in as_completed(futs, timeout=25):
                s = futs[fut]
                try:
                    frames[s] = fut.result()
                except Exception:  # noqa: BLE001
                    continue
        except Exception:  # noqa: BLE001
            pass
    rows = []
    for s in syms:
        df = frames.get(s)
        if df is None:
            continue
        try:
            d = B.add_indicators(df)
            if len(d) < 60:
                continue
            score_series, _ = B.confluence(d)
            score = float(score_series.iloc[-1])
            if abs(score) < min_abs:
                continue
            adx = float(d["adx"].iloc[-1]) if np.isfinite(d["adx"].iloc[-1]) else 0.0
            plan = B.triple_tp_plan(d, score)
            price = plan["entry"]
            dec = 2 if price >= 1000 else 4 if price >= 1 else 6
            res = _gap_cached(d)
            fvg_s = float(res["fvg_score"][-1]) if res else 0.0
            bvg_s = float(res["bvg_score"][-1]) if res else 0.0
            rows.append({
                "symbol": s, "dir": "لانگ 🟢" if score >= 0 else "شورت 🔴", "score": int(round(score)),
                "adx": round(adx, 1), "price": price, "stop": plan["stop"],
                "tp1": plan["tps"][0], "tp2": plan["tps"][1], "tp3": plan["tps"][2],
                "risk_pct": round(plan["risk_pct"], 2), "dec": dec,
                "fvg": round(fvg_s, 2), "bvg": round(bvg_s, 2),
                "fvg_txt": G.short_label(res["fvg_info"], "FVG") if res else "—",
                "bvg_txt": G.short_label(res["bvg_info"], "BVG") if res else "—",
                "candle_time": str(d["dt"].iloc[-1])[:16] if "dt" in d.columns else "",
                "rank": abs(score) * (1 + adx / 50) * (1 + 0.15 * max(0.0, np.sign(score) * (fvg_s + bvg_s))),
            })
        except Exception:  # noqa: BLE001
            continue
    meta = {"scanned": len(frames), "pool": len(syms)}
    df = pd.DataFrame(rows)
    if df.empty:
        return df, meta
    return df.sort_values("rank", ascending=False).head(top_n).reset_index(drop=True), meta


def _live_ticks(exchange: str, symbols: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    if not symbols:
        return out
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(B.fetch_tick, exchange, s): s for s in symbols}
        try:
            for fut in as_completed(futs, timeout=5):
                try:
                    t = fut.result()
                    if t and t.get("price"):
                        out[futs[fut]] = float(t["price"])
                except Exception:  # noqa: BLE001
                    continue
        except Exception:  # noqa: BLE001
            pass
    return out


def _gap_chip(label: str, v: float, txt: str) -> str:
    col = "#16a34a" if v > 0.15 else "#ef4444" if v < -0.15 else "#94a3b8"
    return (f"<span style='display:inline-block;border:1px solid {col}55;border-radius:8px;padding:3px 8px;"
            f"font-size:11px;color:{col};background:{col}14'>{label} {v:+.2f} · {txt}</span>")


def _opps_body(exchange: str, interval: str, top_n: int, min_abs: int, refresh) -> None:
    t0 = time.time()
    opp, meta = _scan_fast(exchange, interval, top_n, min_abs)
    ticks = _live_ticks(exchange, opp["symbol"].tolist()) if not opp.empty else {}
    took = time.time() - t0
    now = datetime.now().strftime("%H:%M:%S")
    st.markdown(
        f"<div dir='rtl' style='display:flex;gap:14px;flex-wrap:wrap;align-items:center;font-size:12px;color:#94a3b8;"
        f"border:1px solid rgba(148,163,184,.2);border-radius:10px;padding:8px 12px;margin:4px 0 10px'>"
        f"<span style='color:#f43f5e;font-weight:800'>● LIVE</span>"
        f"<span>آخرین به‌روزرسانی: <b style='color:#e2e8f0'>{now}</b></span>"
        f"<span>رفرش خودکار: هر <b style='color:#e2e8f0'>{refresh if refresh else '—'}</b> ثانیه</span>"
        f"<span>کندل‌ها: کش {FAST_TTL} ثانیه · قیمت‌ها: زنده</span>"
        f"<span>{meta['scanned']} از {meta['pool']} نماد اسکن شد در {took:.1f}s</span>"
        f"</div>", unsafe_allow_html=True,
    )
    if opp.empty:
        _st_info("فعلاً ستاپ قوی‌ای پیدا نشد. حداقل قدرت سیگنال را کم کن یا تایم‌فریم دیگری امتحان کن.")
        return
    _st_success(f"{len(opp)} فرصت پیدا شد — مرتب‌شده بر اساس قدرت سیگنال × روند (ADX) × هم‌جهتی FVG/BVG.")
    for _, r in opp.iterrows():
        dec = int(r["dec"])
        is_long = "لانگ" in r["dir"]
        tone = "#16a34a" if is_long else "#ef4444"
        live = ticks.get(r["symbol"])
        live_pct = (live - r["price"]) / r["price"] * 100 if live else None
        live_col = "#94a3b8" if live_pct is None else ("#16a34a" if live_pct >= 0 else "#ef4444")
        sl_pct = (r["stop"] - r["price"]) / r["price"] * 100

        def _pct(v):
            return (v - r["price"]) / r["price"] * 100

        def _cell(lbl, val, sub, bg, col="#e2e8f0", lbl_col="#94a3b8"):
            return (f"<div style='background:{bg};border-radius:10px;padding:8px'>"
                    f"<div style='font-size:10px;color:{lbl_col}'>{lbl}</div>"
                    f"<div style='font-family:ui-monospace,monospace;font-weight:800;font-size:14px;color:{col}'>{val}</div>"
                    f"<div style='font-size:9px;color:#94a3b8'>{sub}</div></div>")

        live_val = f"{live:,.{dec}f}" if live else "…"
        live_sub = f"{live_pct:+.2f}% نسبت به ورود" if live_pct is not None else "در انتظار تیک"
        st.markdown(
            f"<div dir='rtl' style='border:1px solid rgba(148,163,184,.2);border-right:5px solid {tone};"
            f"border-radius:14px;padding:14px 16px;margin:10px 0;background:rgba(148,163,184,.05)'>"
            f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;align-items:center'>"
            f"<span style='font-size:18px;font-weight:800'>{r['symbol']}</span>"
            f"<span style='font-family:ui-monospace,monospace;font-size:14px;color:{tone};font-weight:800'>{r['dir']}</span>"
            f"<span style='font-family:ui-monospace,monospace;font-size:12px;color:#94a3b8'>قدرت {r['score']:+d} · ADX {r['adx']} · ریسک {r['risk_pct']}% · کندل {r['candle_time']}</span>"
            f"</div>"
            f"<div style='display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:12px;text-align:center'>"
            + _cell("قیمت زنده", live_val, live_sub, "rgba(244,63,94,.10)", live_col, "#fda4af")
            + _cell("ورود (کلوز کندل)", f"{r['price']:,.{dec}f}", "مبنای SL/TP", "rgba(148,163,184,.08)")
            + _cell("حد ضرر (SL)", f"{r['stop']:,.{dec}f}", f"{sl_pct:+.2f}%", "rgba(239,68,68,.12)", "#ef4444", "#fca5a5")
            + _cell("TP1 · 1R", f"{r['tp1']:,.{dec}f}", f"{_pct(r['tp1']):+.2f}%", "rgba(34,197,94,.10)", "#16a34a", "#86efac")
            + _cell("TP2 · 2R", f"{r['tp2']:,.{dec}f}", f"{_pct(r['tp2']):+.2f}%", "rgba(34,197,94,.14)", "#16a34a", "#86efac")
            + _cell("TP3 · 3R", f"{r['tp3']:,.{dec}f}", f"{_pct(r['tp3']):+.2f}%", "rgba(34,197,94,.18)", "#16a34a", "#86efac")
            + "</div>"
            f"<div style='display:flex;gap:8px;flex-wrap:wrap;margin-top:10px'>"
            + _gap_chip("FVG", float(r["fvg"]), r["fvg_txt"]) + _gap_chip("BVG", float(r["bvg"]), r["bvg_txt"])
            + "</div></div>",
            unsafe_allow_html=True,
        )
    st.download_button(
        "💾 ذخیره فرصت‌ها (CSV)",
        data=opp.drop(columns=["dec", "rank"]).to_csv(index=False).encode("utf-8"),
        file_name=f"opportunities_{exchange}_{interval}.csv", mime="text/csv", key="opp_dl_live",
    )
    _st_caption("این فهرست صرفاً تحلیلی است و توصیه‌ی سرمایه‌گذاری نیست. حتماً مدیریت ریسک را رعایت کن.")


def _render_opps_live() -> None:
    exchange = _RUN.get("exchange", "KuCoin")
    interval = _RUN.get("interval", "1hour")
    st.subheader("💎 فرصت‌های سودده — اسکن خودکار و زنده‌ی بازار ⚡")
    _st_caption("قوی‌ترین ستاپ‌های لانگ/شورت از میان پرمعامله‌ترین ارزها با SL و سه TP؛ "
                "اسکن به‌صورت خودکار تکرار می‌شود و قیمت هر نماد زنده است. "
                f"صرافی: {exchange} · تایم‌فریم: {interval} · همگرایی شامل FVG/BVG است.")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 0.7])
    with c1:
        opp_n = st.slider("تعداد فرصت‌ها", 5, 20, 12, key="opp_n")
    with c2:
        opp_min = st.slider("حداقل قدرت سیگنال", 20, 70, 35, step=5, key="opp_min")
    with c3:
        refresh = st.select_slider("⚡ رفرش خودکار (ثانیه)", options=[3, 5, 10, 20, 30, 60], value=5, key="opp_refresh")
    with c4:
        st.write("")
        live = st.toggle("🔴 زنده", value=True, key="opp_live")
    st.session_state["opp_done"] = True
    if live and hasattr(st, "fragment"):
        st.fragment(run_every=refresh)(_opps_body)(exchange, interval, opp_n, opp_min, refresh)
    else:
        st.button("🔍 اسکن دوباره", type="primary", key="opp_rescan")
        _opps_body(exchange, interval, opp_n, opp_min, None)


# =============================================================================
# 7) اجرا
# =============================================================================
if __name__ == "__main__":
    try:
        B.main()
    except Exception as e:  # noqa: BLE001
        st.exception(e)
        st.error("خطای بالا رو کپی کن بفرست تا دقیق فیکس کنم")
    else:
        if _RUN.get("section") == "opps":
            try:
                _render_opps_live()
            except Exception as e:  # noqa: BLE001
                st.exception(e)
        if G is None:
            st.warning("ماژول core/gaps.py پیدا نشد؛ FVG/BVG غیرفعال است. فایل core/gaps.py را کنار app.py بگذار.")
