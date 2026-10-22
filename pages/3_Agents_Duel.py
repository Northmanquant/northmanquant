"""Agents Duel v3 — چهار ایجنت با «مدرک»: کندل‌ها، ساختار بازار، نقدینگی، جریان پول، FVG/BVG
هر ایجنت یک جدول دلیل دارد (چه دید، چه وزنی داد، چرا پوزیشن گرفت)، بک‌تست روی همان قانون‌ها انجام می‌شود
و در پایان «بهترین پوزیشن» از اجماعِ وزن‌دار (بر اساس عملکرد واقعی هر ایجنت روی همین بازار) ساخته می‌شود.
"""
from __future__ import annotations

import json
import time
import os
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Agents Duel", page_icon="🤖", layout="wide")
st.title("🤖 دوئل ایجنت‌ها — کدوم ربات می‌بره؟ (با مدرک)")
st.caption("NorthmanQuant · Agents Duel v5.0 (+ شکار بازار · ستاپ اعتبارسنجی‌شده) · صفحه آماده‌ی اجراست؛ داده فقط با «شروع دوئل» دریافت می‌شود.")
st.caption("۴ ایجنت روی ۱ ارز با قانون‌های شفاف پوزیشن می‌گیرند؛ هر کدام جدول دلیل و مدرک دارد. "
           "برنده + پوزیشن اجماعی با SL/TP به 👥 تحلیل‌های کاربران می‌رود.")

EXCHANGES = ["KuCoin", "OKX", "Binance", "Bybit", "Lighter", "XT", "LBank", "KCEX"]
COMMUNITY_FILE = "community_analyses.json"

try:
    from core import gaps as G
except Exception:  # noqa: BLE001
    G = None


# ----------------------------------------------------------------------------- storage
def save_duel(entry: dict) -> None:
    rows = []
    if os.path.exists(COMMUNITY_FILE):
        try:
            with open(COMMUNITY_FILE, "r", encoding="utf-8") as f:
                rows = json.load(f)
        except Exception:  # noqa: BLE001
            rows = []
    rows.insert(0, entry)
    rows = rows[:200]
    try:
        with open(COMMUNITY_FILE, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        st.warning(f"ذخیره نشد: {e}")


# ----------------------------------------------------------------------------- data
def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _fallback_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """اگر app_base در دسترس نبود، حداقل اندیکاتورهای لازم را خودمان می‌سازیم."""
    d = df.copy()
    c, h, l, v = d["close"], d["high"], d["low"], d["volume"]
    d["ema20"], d["ema50"], d["ema200"] = _ema(c, 20), _ema(c, 50), _ema(c, 200)
    delta = c.diff()
    gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    rs = gain.ewm(alpha=1 / 14, adjust=False).mean() / loss.ewm(alpha=1 / 14, adjust=False).mean().replace(0, np.nan)
    d["rsi"] = (100 - 100 / (1 + rs)).fillna(50)
    macd = _ema(c, 12) - _ema(c, 26)
    d["macd_hist"] = macd - _ema(macd, 9)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    mid, std = c.rolling(20).mean(), c.rolling(20).std()
    d["bb_mid"], d["bb_up"], d["bb_lo"] = mid, mid + 2 * std, mid - 2 * std
    tp = (h + l + c) / 3
    d["vwap"] = (tp * v).rolling(60).sum() / v.rolling(60).sum().replace(0, np.nan)
    mfm = ((c - l) - (h - c)) / (h - l).replace(0, np.nan)
    d["cmf"] = (mfm * v).rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan)
    pos = (tp * v).where(tp > tp.shift(), 0.0).rolling(14).sum()
    neg = (tp * v).where(tp < tp.shift(), 0.0).rolling(14).sum().replace(0, np.nan)
    d["mfi"] = (100 - 100 / (1 + pos / neg)).fillna(50)
    up, dn = h.diff(), -l.diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    atr14 = tr.ewm(alpha=1 / 14, adjust=False).mean().replace(0, np.nan)
    d["plus_di"] = 100 * pd.Series(plus_dm, index=d.index).ewm(alpha=1 / 14, adjust=False).mean() / atr14
    d["minus_di"] = 100 * pd.Series(minus_dm, index=d.index).ewm(alpha=1 / 14, adjust=False).mean() / atr14
    dx = 100 * (d["plus_di"] - d["minus_di"]).abs() / (d["plus_di"] + d["minus_di"]).replace(0, np.nan)
    d["adx"] = dx.ewm(alpha=1 / 14, adjust=False).mean().fillna(0)
    d["supertrend_dir"] = np.where(c > d["ema50"], 1, -1)
    return d


def get_df(exchange: str, symbol: str, interval: str, limit: int = 300):
    """دیتا از app_base (که Lighter و KCEX را هم بلد است)؛ fallback: KuCoin مستقیم."""
    try:
        import app_base as B
        sym = B.normalize_symbol(symbol, exchange)
        df = B.fetch_candles(exchange, sym, interval, limit)
        d = B.add_indicators(df)
        return d, sym, "app_base"
    except Exception as e:  # noqa: BLE001
        st.warning(f"app_base نشد ({e}) — fallback KuCoin")
        import requests
        tfmap = {"15min": "15min", "1hour": "1hour", "4hour": "4hour", "1day": "1day", "1week": "1week"}
        r = requests.get("https://api.kucoin.com/api/v1/market/candles",
                         params={"symbol": symbol.replace("/", "-").upper(), "type": tfmap.get(interval, "1hour")},
                         timeout=20).json()
        rows = [{"time": int(x[0]) * 1000, "open": float(x[1]), "close": float(x[2]),
                 "high": float(x[3]), "low": float(x[4]), "volume": float(x[5])} for x in (r.get("data") or [])]
        df = pd.DataFrame(rows).sort_values("time").reset_index(drop=True).tail(limit).reset_index(drop=True)
        df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
        return _fallback_indicators(df), symbol, "kucoin-fallback"


# ----------------------------------------------------------------------------- features (همه علّی)
def _clip(s, lo=-1.0, hi=1.0):
    return np.clip(np.nan_to_num(np.asarray(s, dtype=float), nan=0.0), lo, hi)


def _col(d: pd.DataFrame, name: str, default):
    if name in d.columns:
        return pd.to_numeric(d[name], errors="coerce")
    return pd.Series(default, index=d.index, dtype=float)


def build_features(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    o, h, l, c, v = d["open"], d["high"], d["low"], d["close"], d["volume"].fillna(0)
    n = len(d)
    atr = _col(d, "atr", np.nan).replace(0, np.nan).ffill().bfill().fillna(c * 0.01)
    e20, e50, e200 = _col(d, "ema20", c), _col(d, "ema50", c), _col(d, "ema200", c)
    F = pd.DataFrame(index=d.index)
    F["close"], F["atr"] = c, atr

    # --- جهت بازار: هم‌راستایی EMA + ساختار سقف/کف ---------------------------------
    F["ema_align"] = np.select(
        [(c > e20) & (e20 > e50) & (e50 > e200), (c < e20) & (e20 < e50) & (e50 < e200),
         (c > e20) & (e20 > e50), (c < e20) & (e20 < e50), c > e50, c < e50],
        [1.0, -1.0, 0.6, -0.6, 0.25, -0.25], 0.0)
    hh = h.rolling(10).max() > h.shift(10).rolling(10).max()
    hl = l.rolling(10).min() > l.shift(10).rolling(10).min()
    lh = h.rolling(10).max() < h.shift(10).rolling(10).max()
    ll = l.rolling(10).min() < l.shift(10).rolling(10).min()
    F["struct"] = np.select([hh & hl, lh & ll, hh | hl, lh | ll], [1.0, -1.0, 0.4, -0.4], 0.0)
    adx = _col(d, "adx", 0.0).fillna(0)
    pdi, mdi = _col(d, "plus_di", 0.0).fillna(0), _col(d, "minus_di", 0.0).fillna(0)
    F["adx_norm"] = _clip(adx / 50, 0, 1)
    F["di_adx"] = np.sign(pdi - mdi) * F["adx_norm"]
    F["supertrend"] = _clip(_col(d, "supertrend_dir", 0.0).fillna(0))

    # --- مومنتوم -------------------------------------------------------------------
    F["macd"] = _clip(_col(d, "macd_hist", 0.0).fillna(0) / atr * 3)
    rsi = _col(d, "rsi", 50.0).fillna(50)
    F["rsi_mom"] = _clip((rsi - 50) / 25)
    roc10 = c.pct_change(10).fillna(0)
    F["roc"] = _clip(roc10 / (atr / c * 5))
    vol_sma = v.rolling(20, min_periods=5).mean().replace(0, np.nan)
    F["vol_ratio"] = (v / vol_sma).fillna(1.0)
    F["vol_thrust"] = _clip((F["vol_ratio"] - 1.0)) * np.sign(c - o)
    prior_hi = h.shift(1).rolling(20).max()
    prior_lo = l.shift(1).rolling(20).min()
    F["brk"] = np.select([c > prior_hi, c < prior_lo], [1.0, -1.0], 0.0)

    # --- جریان پول (ورود/خروج) ---------------------------------------------------------
    F["cmf"] = _clip(_col(d, "cmf", 0.0).fillna(0) * 4)
    F["mfi_c"] = _clip((_col(d, "mfi", 50.0).fillna(50) - 50) / 25)
    obv = (np.sign(c.diff().fillna(0)) * v).cumsum()
    F["obv"] = _clip(obv.diff(10) / v.rolling(10).sum().replace(0, np.nan))
    rng = (h - l).replace(0, np.nan)
    delta = (((c - l) - (h - c)) / rng).fillna(0) * v
    F["money_delta"] = _clip(delta.rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan))
    F["upvol20"] = v.where(c >= o, 0.0).rolling(20).sum()
    F["dnvol20"] = v.where(c < o, 0.0).rolling(20).sum()

    # --- نقدینگی: سوییپ سقف/کف و استخرهای equal highs/lows ---------------------------
    sweep_hi = (h > prior_hi) & (c < prior_hi)   # نقدینگی بالای سقف جمع شد و رد شد → نزولی
    sweep_lo = (l < prior_lo) & (c > prior_lo)   # نقدینگی زیر کف جمع شد و رد شد → صعودی
    sw = pd.Series(np.select([sweep_lo, sweep_hi], [1.0, -1.0], np.nan), index=d.index)
    F["sweep"] = sw.ffill(limit=3).fillna(0)
    F["sweep_raw"] = sw.fillna(0)
    eqh = pd.Series(False, index=d.index)
    eql = pd.Series(False, index=d.index)
    for k in range(2, 13):
        eqh |= (h - h.shift(k)).abs() < 0.12 * atr
        eql |= (l - l.shift(k)).abs() < 0.12 * atr
    F["eqh"], F["eql"] = eqh.astype(float), eql.astype(float)
    F["pool_bias"] = np.select([eqh & (F["struct"] >= 0) & ~eql, eql & (F["struct"] <= 0) & ~eqh], [0.3, -0.3], 0.0)

    # --- بازگشت به میانگین -----------------------------------------------------------
    bb_mid = _col(d, "bb_mid", c)
    bb_up = _col(d, "bb_up", c)
    half = ((bb_up - bb_mid) / 2).replace(0, np.nan)
    F["z"] = ((c - bb_mid) / half).fillna(0)
    F["z_fade"] = -_clip(F["z"] / 2.5)
    F["vwap_dist"] = ((c - _col(d, "vwap", c).fillna(c)) / atr).fillna(0)
    F["vwap_fade"] = -_clip(F["vwap_dist"] / 2)
    F["rsi"] = rsi
    F["rsi_ext"] = _clip((30 - rsi) / 10, 0, 1) - _clip((rsi - 70) / 10, 0, 1)

    # --- آناتومی کندل ----------------------------------------------------------------
    body = (c - o).abs()
    uw = h - np.maximum(o, c)
    lw = np.minimum(o, c) - l
    pin_bull = (lw > 2 * body) & (lw > 0.5 * (h - l))
    pin_bear = (uw > 2 * body) & (uw > 0.5 * (h - l))
    po, pc = o.shift(), c.shift()
    eng_bull = (c > o) & (c >= np.maximum(po, pc)) & (o <= np.minimum(po, pc)) & (body > (po - pc).abs())
    eng_bear = (c < o) & (c <= np.minimum(po, pc)) & (o >= np.maximum(po, pc)) & (body > (po - pc).abs())
    F["candle"] = np.select([eng_bull, eng_bear, pin_bull, pin_bear], [1.0, -1.0, 0.7, -0.7], 0.0)
    F["candle_name"] = np.select([eng_bull, eng_bear, pin_bull, pin_bear],
                                 ["انگالفینگ صعودی", "انگالفینگ نزولی", "پین‌بار صعودی", "پین‌بار نزولی"], "—")
    F["body_pct"] = (body / rng * 100).fillna(0)

    # --- FVG / BVG ------------------------------------------------------------------
    gaps_res = None
    if G is not None:
        try:
            gaps_res = G.gap_analysis(d)
        except Exception:  # noqa: BLE001
            gaps_res = None
    if gaps_res is not None:
        F["fvg"] = gaps_res["fvg_score"]
        F["bvg"] = gaps_res["bvg_score"]
    else:
        F["fvg"] = 0.0
        F["bvg"] = 0.0
    F["fvg_disp"] = _clip(pd.Series(F["fvg"]).rolling(3).mean().fillna(0) * 1.5)
    extras = {"gaps": gaps_res, "prior_hi": prior_hi, "prior_lo": prior_lo, "obv": obv, "n": n}
    return F, extras


# ----------------------------------------------------------------------------- agents
AGENTS = {
    "Trend Rider 📊": {
        "color": "#0ea5e9", "thr": 0.25,
        "desc": "دنبال جهت بازار است: هم‌راستایی EMAها، ساختار سقف/کف، سوپرترند، قدرت روند (ADX/DI)، جریان پول و FVG هم‌جهت.",
        "weights": {"ema_align": 0.25, "struct": 0.25, "supertrend": 0.15, "di_adx": 0.15, "cmf": 0.10, "fvg": 0.10},
    },
    "Momentum 🧠": {
        "color": "#8b5cf6", "thr": 0.25,
        "desc": "شتاب حرکت را می‌خرد: MACD، سرعت ۱۰ کندلی، RSI، حجمِ پشت کندل‌ها، شکست کانال ۲۰ کندلی و جابه‌جایی تازه‌ی FVG.",
        "weights": {"macd": 0.25, "roc": 0.20, "rsi_mom": 0.15, "vol_thrust": 0.15, "brk": 0.10, "fvg_disp": 0.15},
    },
    "MeanRev 🎯": {
        "color": "#ec4899", "thr": 0.30,
        "desc": "افراط را می‌فروشد: فاصله از باند بولینگر و VWAP، اشباع RSI، سوییپ نقدینگی (برگشت از سقف/کف) و کندل برگشتی.",
        "weights": {"z_fade": 0.30, "vwap_fade": 0.20, "rsi_ext": 0.20, "sweep": 0.15, "candle": 0.15},
    },
    "SmartMoney 🏦": {
        "color": "#f59e0b", "thr": 0.25,
        "desc": "ردّ پول هوشمند: زون‌های FVG/BVG، سوییپ نقدینگی، ساختار بازار، دلتای خرید/فروش و شیب OBV.",
        "weights": {"fvg": 0.25, "bvg": 0.20, "sweep": 0.15, "struct": 0.15, "money_delta": 0.15, "obv": 0.10},
    },
}

FACTOR_FA = {
    "ema_align": "هم‌راستایی EMA20/50/200", "struct": "ساختار بازار (HH/HL یا LH/LL)", "supertrend": "سوپرترند",
    "di_adx": "جهت DI × قدرت ADX", "cmf": "جریان پول CMF", "fvg": "FVG گپ ارزش", "macd": "هیستوگرام MACD",
    "roc": "سرعت ۱۰ کندلی (ROC/ATR)", "rsi_mom": "RSI (مومنتوم)", "vol_thrust": "حجم پشت کندل",
    "brk": "شکست کانال ۲۰ کندلی", "fvg_disp": "جابه‌جایی تازه‌ی FVG", "z_fade": "فاصله از بولینگر (فِید)",
    "vwap_fade": "فاصله از VWAP (فِید)", "rsi_ext": "اشباع RSI", "sweep": "سوییپ نقدینگی", "candle": "الگوی کندل",
    "bvg": "BVG گپ حجمی", "money_delta": "دلتای خرید/فروش ۲۰ کندل", "obv": "شیب OBV (۱۰ کندل)",
}


def describe(key: str, r: pd.Series, d_last: pd.Series, dec: int, extras: dict) -> str:
    """متن مدرک برای هر فاکتور با عدد واقعی."""
    def f(x, nd=dec):
        try:
            return f"{float(x):,.{nd}f}"
        except Exception:  # noqa: BLE001
            return "—"
    if key == "ema_align":
        return f"قیمت {f(r.close)} · EMA20 {f(d_last.get('ema20'))} · EMA50 {f(d_last.get('ema50'))} · EMA200 {f(d_last.get('ema200'))}"
    if key == "struct":
        lbl = "سقف و کف بالاتر (HH/HL)" if r.struct >= 1 else "سقف و کف پایین‌تر (LH/LL)" if r.struct <= -1 else \
              "ساختار ترکیبی/رنج" if r.struct == 0 else ("بیشتر صعودی" if r.struct > 0 else "بیشتر نزولی")
        return f"{lbl} · مقایسه‌ی ۱۰ کندل اخیر با ۱۰ کندل قبل"
    if key == "supertrend":
        return "سوپرترند صعودی (قیمت بالای خط)" if r.supertrend > 0 else "سوپرترند نزولی (قیمت زیر خط)"
    if key == "di_adx":
        return f"+DI {f(d_last.get('plus_di'), 1)} / −DI {f(d_last.get('minus_di'), 1)} · ADX {f(d_last.get('adx'), 1)} ({'روند قوی' if r.adx_norm > 0.5 else 'روند ضعیف/رنج'})"
    if key == "cmf":
        return f"CMF {f(d_last.get('cmf'), 3)} → {'ورود پول' if r.cmf > 0.1 else 'خروج پول' if r.cmf < -0.1 else 'خنثی'}"
    if key == "fvg":
        info = (extras.get("gaps") or {}).get("fvg_info") or {}
        return (G.short_label(info, "FVG") if (G and info) else "—") + f" · امتیاز {r.fvg:+.2f}"
    if key == "bvg":
        info = (extras.get("gaps") or {}).get("bvg_info") or {}
        return (G.short_label(info, "BVG") if (G and info) else "—") + f" · امتیاز {r.bvg:+.2f}"
    if key == "macd":
        return f"هیستوگرام {f(d_last.get('macd_hist'), 5)} ({'بالای صفر' if r.macd > 0 else 'زیر صفر'}) نسبت به ATR {f(r.atr)}"
    if key == "roc":
        return f"تغییر ۱۰ کندل اخیر {float(r.close / extras['close10'] - 1) * 100:+.2f}% · نرمال‌شده با ATR"
    if key == "rsi_mom":
        return f"RSI {float(r.rsi):.1f} ({'بالای ۵۰' if r.rsi > 50 else 'زیر ۵۰'})"
    if key == "vol_thrust":
        return f"حجم کندل آخر {float(r.vol_ratio):.2f}× میانگین ۲۰ کندل · کندل {'سبز' if r.vol_thrust >= 0 else 'قرمز'}"
    if key == "brk":
        return f"سقف ۲۰ کندل {f(extras['prior_hi'])} · کف ۲۰ کندل {f(extras['prior_lo'])} → " + \
               ("شکست رو به بالا" if r.brk > 0 else "شکست رو به پایین" if r.brk < 0 else "داخل کانال")
    if key == "fvg_disp":
        return f"میانگین امتیاز FVG سه کندل اخیر {float(r.fvg_disp):+.2f} (ایمپالس تازه با گپ)"
    if key == "z_fade":
        return f"z-score بولینگر {float(r.z):+.2f} → " + ("اشباع خرید، احتمال برگشت" if r.z > 1.5 else "اشباع فروش، احتمال برگشت" if r.z < -1.5 else "داخل باند")
    if key == "vwap_fade":
        return f"فاصله از VWAP {float(r.vwap_dist):+.2f} ATR"
    if key == "rsi_ext":
        return f"RSI {float(r.rsi):.1f} → " + ("اشباع فروش (<30)" if r.rsi < 30 else "اشباع خرید (>70)" if r.rsi > 70 else "بدون اشباع")
    if key == "sweep":
        return ("کف ۲۰ کندل سوییپ شد و قیمت برگشت بالا (نقدینگی فروشندگان جمع شد)" if r.sweep > 0 else
                "سقف ۲۰ کندل سوییپ شد و قیمت برگشت پایین (نقدینگی خریداران جمع شد)" if r.sweep < 0 else
                "در ۳ کندل اخیر سوییپی رخ نداده") + (" · استخر equal-highs بالا" if r.eqh else "") + (" · استخر equal-lows پایین" if r.eql else "")
    if key == "candle":
        return f"کندل آخر: {r.candle_name} · بدنه {float(r.body_pct):.0f}٪ رنج"
    if key == "money_delta":
        return f"دلتای ۲۰ کندل {float(r.money_delta):+.2f} · حجم کندل‌های سبز {f(r.upvol20, 0)} / قرمز {f(r.dnvol20, 0)}"
    if key == "obv":
        return f"شیب OBV ده کندلی {float(r.obv):+.2f} → " + ("انباشت" if r.obv > 0.1 else "توزیع" if r.obv < -0.1 else "خنثی")
    return "—"


def _verdict(v: float) -> str:
    return "🟢 لانگ" if v > 0.15 else "🔴 شورت" if v < -0.15 else "⚪ خنثی"


def agent_scores(F: pd.DataFrame, spec: dict) -> np.ndarray:
    s = np.zeros(len(F))
    for k, w in spec["weights"].items():
        s += w * np.nan_to_num(F[k].to_numpy(dtype=float))
    return s


def signals_with_hysteresis(s: np.ndarray, thr: float) -> np.ndarray:
    sig = np.zeros(len(s))
    pos = 0.0
    for i, v in enumerate(s):
        if v > thr:
            pos = 1.0
        elif v < -thr:
            pos = -1.0
        elif abs(v) < thr * 0.4:
            pos = 0.0
        sig[i] = pos
    return sig


def backtest(close: np.ndarray, sig: np.ndarray, balance: float, fee_pct: float) -> dict:
    rets = np.zeros(len(close))
    rets[1:] = (close[1:] - close[:-1]) / close[:-1]
    strat = np.zeros(len(close))
    strat[1:] = sig[:-1] * rets[1:]
    flips = (np.abs(np.diff(sig, prepend=0)) > 0)
    strat = strat - flips * (fee_pct / 100)
    eq = np.cumprod(1 + strat) * balance
    total = (eq[-1] / balance - 1) * 100
    wins, losses = strat[strat > 0], strat[strat < 0]
    pf = wins.sum() / -losses.sum() if losses.sum() < 0 else (float("inf") if wins.sum() > 0 else 0.0)
    peak = np.maximum.accumulate(eq)
    dd = float(((peak - eq) / peak).max() * 100)
    exposure = float((sig != 0).mean() * 100)
    return {"eq": eq, "total": total, "trades": int(flips.sum()), "win": len(wins) / max(1, len(wins) + len(losses)) * 100,
            "pf": float(min(pf, 99.0)), "dd": dd, "exposure": exposure,
            "recent": float((eq[-1] / eq[max(0, len(eq) - 21)] - 1) * 100)}


# ----------------------------------------------------------------------------- position builder
def _swings(d: pd.DataFrame, k: int = 3) -> tuple[list[tuple], list[tuple]]:
    h, l = d["high"].to_numpy(), d["low"].to_numpy()
    highs, lows = [], []
    for i in range(k, len(d) - k):
        if h[i] == h[i - k:i + k + 1].max():
            highs.append((i, float(h[i])))
        if l[i] == l[i - k:i + k + 1].min():
            lows.append((i, float(l[i])))
    return highs, lows


def build_position(d: pd.DataFrame, F: pd.DataFrame, extras: dict, direction: int, dec: int) -> dict:
    price = float(d["close"].iloc[-1])
    atr = float(F["atr"].iloc[-1])
    gaps_res = extras.get("gaps")
    highs, lows = _swings(d.tail(120).reset_index(drop=True))
    off = len(d) - min(120, len(d))
    sw_hi = [(i + off, p) for i, p in highs]
    sw_lo = [(i + off, p) for i, p in lows]
    reasons_sl, targets = [], []
    if direction == 0:
        return {"direction": 0, "entry": price, "stop": None, "targets": [], "rr": 0, "sl_reason": "—"}

    if direction > 0:
        cands = [(float(d["low"].tail(10).min()), "کف ۱۰ کندل اخیر")]
        if gaps_res:
            for z in G.active_zones(gaps_res, "FVG", price, 6) + G.active_zones(gaps_res, "BVG", price, 4):
                if z["type"] > 0 and z["top"] <= price and price - z["bot"] <= 2.5 * atr:
                    cands.append((z["bot"], f"زیر زون {z['kind']} صعودی"))
        eq_lows = [p for i, p in sw_lo if p < price and price - p <= 2.5 * atr]
        if eq_lows:
            cands.append((min(eq_lows), "زیر کف سوئینگ/استخر نقدینگی"))
        lvl, why = min(cands, key=lambda x: x[0])
        stop = lvl - 0.25 * atr
        stop = max(min(stop, price - atr), price - 3 * atr)
        reasons_sl.append(why)
        risk = price - stop
        pool = [(p, "سقف سوئینگ (نقدینگی خریداران)") for i, p in sw_hi if p > price]
        if gaps_res:
            pool += [(z["bot"], f"لبه‌ی زون {z['kind']} نزولی") for z in G.active_zones(gaps_res, "FVG", price, 8) + G.active_zones(gaps_res, "BVG", price, 4) if z["type"] < 0 and z["bot"] > price]
        if "bb_up" in d.columns and float(d["bb_up"].iloc[-1]) > price:
            pool.append((float(d["bb_up"].iloc[-1]), "باند بالای بولینگر"))
        pool = sorted({round(p, 10): why for p, why in pool}.items())
        for p, why in pool:
            if p >= price + risk * 1.0 and (not targets or p > targets[-1][0] * 1.001):
                targets.append((p, round((p - price) / risk, 2), why))
            if len(targets) == 3:
                break
        m = 1
        while len(targets) < 3:
            tgt = price + risk * m
            if not targets or tgt > targets[-1][0]:
                targets.append((tgt, float(m), f"{m}R (نسبت ریسک)"))
            m += 1
    else:
        cands = [(float(d["high"].tail(10).max()), "سقف ۱۰ کندل اخیر")]
        if gaps_res:
            for z in G.active_zones(gaps_res, "FVG", price, 6) + G.active_zones(gaps_res, "BVG", price, 4):
                if z["type"] < 0 and z["bot"] >= price and z["top"] - price <= 2.5 * atr:
                    cands.append((z["top"], f"بالای زون {z['kind']} نزولی"))
        eq_highs = [p for i, p in sw_hi if p > price and p - price <= 2.5 * atr]
        if eq_highs:
            cands.append((max(eq_highs), "بالای سقف سوئینگ/استخر نقدینگی"))
        lvl, why = max(cands, key=lambda x: x[0])
        stop = lvl + 0.25 * atr
        stop = min(max(stop, price + atr), price + 3 * atr)
        reasons_sl.append(why)
        risk = stop - price
        pool = [(p, "کف سوئینگ (نقدینگی فروشندگان)") for i, p in sw_lo if p < price]
        if gaps_res:
            pool += [(z["top"], f"لبه‌ی زون {z['kind']} صعودی") for z in G.active_zones(gaps_res, "FVG", price, 8) + G.active_zones(gaps_res, "BVG", price, 4) if z["type"] > 0 and z["top"] < price]
        if "bb_lo" in d.columns and float(d["bb_lo"].iloc[-1]) < price:
            pool.append((float(d["bb_lo"].iloc[-1]), "باند پایین بولینگر"))
        pool = sorted({round(p, 10): why for p, why in pool}.items(), reverse=True)
        for p, why in pool:
            if p <= price - risk * 1.0 and (not targets or p < targets[-1][0] * 0.999):
                targets.append((p, round((price - p) / risk, 2), why))
            if len(targets) == 3:
                break
        m = 1
        while len(targets) < 3:
            tgt = price - risk * m
            if not targets or tgt < targets[-1][0]:
                targets.append((tgt, float(m), f"{m}R (نسبت ریسک)"))
            m += 1
    return {"direction": direction, "entry": price, "stop": stop, "targets": targets[:3],
            "rr": targets[0][1] if targets else 0, "sl_reason": " / ".join(reasons_sl), "atr": atr}


# ----------------------------------------------------------------------------- UI helpers
def pos_text(p: dict, dec: int) -> str:
    if p["direction"] == 0:
        return "بدون پوزیشن (FLAT)"
    s = f"{'لانگ 🟢' if p['direction'] > 0 else 'شورت 🔴'} · ورود {p['entry']:,.{dec}f} · SL {p['stop']:,.{dec}f}"
    for i, (tp, rr, _) in enumerate(p["targets"]):
        s += f" · TP{i + 1} {tp:,.{dec}f} ({rr}R)"
    return s


def render_position(p: dict, dec: int, tone: str) -> None:
    if p["direction"] == 0:
        st.info("این ایجنت فعلاً پوزیشن نمی‌گیرد (امتیاز زیر آستانه) — ولی تمایلش در جدول دیده می‌شود.")
        return
    cols = st.columns(5)
    cols[0].metric("جهت", "لانگ 🟢" if p["direction"] > 0 else "شورت 🔴")
    cols[1].metric("ورود", f"{p['entry']:,.{dec}f}")
    cols[2].metric("حد ضرر", f"{p['stop']:,.{dec}f}", f"{(p['stop'] / p['entry'] - 1) * 100:+.2f}%")
    for j, (tp, rr, why) in enumerate(p["targets"][:2]):
        cols[3 + j].metric(f"TP{j + 1}", f"{tp:,.{dec}f}", f"{rr}R")
    st.markdown(
        f"<div dir='rtl' style='font-size:12px;color:#94a3b8;border-right:3px solid {tone};padding-right:8px'>"
        f"دلیل حد ضرر: {p['sl_reason']} − ۰.۲۵ ATR<br>"
        + "<br>".join(f"TP{i + 1}: {tp:,.{dec}f} ← {why}" for i, (tp, rr, why) in enumerate(p["targets"]))
        + "</div>", unsafe_allow_html=True)


# =============================================================================
# 🔎 شکار بازار — ایجنت‌ها کل صرافی را می‌گردند و بهترین لانگ/شورت‌ها را می‌دهند
#   • دقیقاً همان موتور دوئل (calculate_duel) روی هر ارز پرحجم اجرا می‌شود — نه قانون تازه.
#   • یک ارز فقط وقتی «برگزیده» می‌شود که هر سه فیلتر زیر را رد کند:
#       ۱) اجماع وزن‌دار ایجنت‌ها قوی باشد (|امتیاز| ≥ آستانه)
#       ۲) حداقل ۳ ایجنت از ۴ هم‌جهت باشند
#       ۳) ایجنت(های) هم‌جهت روی خود همان ارز در بک‌تست سودده بوده باشند (PF > 1 و بازده مثبت)
#     → چیزی که این سه فیلتر را رد کند، «نظر خالی» نیست؛ پشتش عدد است.
# =============================================================================
HUNT_POOL_FALLBACK = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT", "DOGE-USDT",
                      "ADA-USDT", "AVAX-USDT", "LINK-USDT", "TRX-USDT", "LTC-USDT", "DOT-USDT"]


def _hunt_pool(exchange: str, n: int) -> list[str]:
    try:
        import app_base as B
        tops = B.fetch_top_coins(exchange, 1_000_000, 40)
        pool = pd.concat([tops["volume"], tops["gainers"], tops["losers"]]).drop_duplicates("symbol")
        syms = [s for s in pool["symbol"].tolist() if not str(s).upper().startswith(("USDC", "USDT", "DAI", "TUSD", "FDUSD"))]
        return syms[:n] or HUNT_POOL_FALLBACK[:n]
    except Exception:  # noqa: BLE001
        return HUNT_POOL_FALLBACK[:n]


def _hunt_one(exchange: str, symbol: str, interval: str, balance: float, fee_pct: float):
    """یک ارز را از همان موتور دوئل رد می‌کند و خلاصه‌ی قابل رتبه‌بندی برمی‌گرداند."""
    try:
        S_ = calculate_duel(exchange, symbol, interval, 300, balance, fee_pct)
    except Exception as exc:  # noqa: BLE001
        return {"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"}
    res, fd, fp = S_["results"], S_["final_dir"], S_["final_pos"]
    # «موافق» = تمایل ایجنت (همان lean صفحه‌ی دوئل: |امتیاز| ≥ ۰.۱۵) هم‌جهت با اجماع
    agree = [n for n, r in res.items() if fd != 0 and np.sign(r["score"]) == fd and abs(r["score"]) >= 0.15]
    open_pos = [n for n, r in res.items() if r["sig"] == fd and fd != 0]   # ایجنت‌هایی که همین الان پوزیشن باز دارند
    aligned_bt = [res[n]["bt"] for n in agree]
    prof = [b for b in aligned_bt if b["pf"] > 1.0 and b["total"] > 0]
    best_bt = max(aligned_bt, key=lambda b: (b["pf"], b["total"])) if aligned_bt else None
    # دلایل: سه فاکتور با بیشترین سهم در جهتِ تصمیم، از بین ایجنت‌های موافق
    reasons = []
    for n in agree:
        for row in res[n]["rows"]:
            if np.sign(row["سهم در تصمیم"]) == fd and abs(row["سهم در تصمیم"]) > 0.02:
                reasons.append((abs(row["سهم در تصمیم"]), f"{row['فاکتور']}: {row['مدرک (مشاهده‌ی واقعی)']}"))
    seen, top_reasons = set(), []
    for _, txt in sorted(reasons, key=lambda x: -x[0]):
        key = txt.split(":")[0]
        if key not in seen:
            seen.add(key)
            top_reasons.append(txt)
        if len(top_reasons) == 3:
            break
    d_ = S_["d"]
    adx = float(d_["adx"].iloc[-1]) if "adx" in d_.columns and np.isfinite(d_["adx"].iloc[-1]) else 0.0
    # فیلتر ۴: موتور ستاپ اعتبارسنجی‌شده‌ی app_base (walk-forward روی همین ارز) باید فعال و هم‌جهت باشد
    try:
        import app_base as _B
        vp = _B.setup_plan(d_)
        v_ok = vp["status"] == "active" and ((vp["direction"].startswith("لانگ") and fd > 0) or (vp["direction"].startswith("شورت") and fd < 0))
        v_txt = vp.get("why", "") if v_ok else ("ستاپ معتبر فعال نیست" if vp["status"] != "active" else "ستاپ معتبر خلاف جهت ایجنت‌هاست")
        v_stats = vp["stats"]
    except Exception as _e:  # noqa: BLE001
        vp, v_ok, v_txt, v_stats = None, False, f"اعتبارسنجی انجام نشد: {_e}", {}
    return {
        "symbol": S_["sym"], "dir": fd, "score": S_["final_s"], "confidence": S_["confidence"],
        "agree": agree, "n_agree": len(agree), "n_prof": len(prof), "open_pos": open_pos,
        "best_pf": best_bt["pf"] if best_bt else 0.0, "best_ret": best_bt["total"] if best_bt else 0.0,
        "best_win": best_bt["win"] if best_bt else 0.0, "best_trades": best_bt["trades"] if best_bt else 0,
        "pos": fp, "dec": S_["dec"], "price": float(d_["close"].iloc[-1]), "adx": adx,
        "reasons": top_reasons, "winner": S_["winner"], "fvg_txt": "",
        "v_ok": v_ok, "v_txt": v_txt, "v_plan": vp,
        "ts": S_["ts"],
    }


def run_hunt(exchange: str, interval: str, n_pool: int, balance: float, fee_pct: float,
             min_score: float, min_agree: int, workers: int = 6) -> tuple[list[dict], list[dict], list[str]]:
    from concurrent.futures import ThreadPoolExecutor
    import threading
    pool = _hunt_pool(exchange, n_pool)
    init = None
    try:
        from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
        ctx = get_script_run_ctx()
        if ctx is not None:
            def init():  # noqa: E306
                add_script_run_ctx(threading.current_thread(), ctx)
    except Exception:  # noqa: BLE001
        init = None
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pool))), initializer=init) as ex:
        out = list(ex.map(lambda s: _hunt_one(exchange, s, interval, balance, fee_pct), pool))
    errors = [f"{o['symbol']} — {o['error']}" for o in out if o.get("error")]
    ok = [o for o in out if not o.get("error")]
    picks = [o for o in ok
             if o["dir"] != 0 and abs(o["score"]) >= min_score and o["n_agree"] >= min_agree and o["n_prof"] >= 1
             and o["pos"]["direction"] != 0 and o["pos"]["rr"] >= 1.0 and o.get("v_ok")]
    # سطوح نهایی از موتور اعتبارسنجی‌شده (ورود در لحظه‌ی ستاپ، SL ساختاری، TP نردبانی)
    for o in picks:
        vp = o.get("v_plan") or {}
        if vp.get("entry") is not None:
            o["pos"] = {"direction": o["dir"], "entry": vp["entry"], "stop": vp["stop"], "rr": vp["rr"],
                        "targets": [(t[0], t[1], w) for t, w in zip(vp["targets"], vp.get("target_why", ["1R", "2R", "3R"]))],
                        "sl_reason": vp.get("stop_why", ""), "atr": vp.get("atr", 0)}
    # رتبه: قدرت اجماع × تعداد موافق × کیفیت بک‌تست × R:R
    for o in picks:
        o["rank"] = abs(o["score"]) * (1 + 0.25 * o["n_agree"]) * min(2.5, o["best_pf"]) * (1 + min(o["pos"]["rr"], 3) / 4)
    picks.sort(key=lambda o: -o["rank"])
    return picks, ok, errors


def render_hunt(exchange: str, interval: str, balance: float, fee_pct: float) -> None:
    st.caption("ایجنت‌ها خودشان پرحجم‌ترین ارزهای صرافی را یکی‌یکی از همان موتور دوئل رد می‌کنند و فقط ارزهایی را "
               "برمی‌گزینند که ۱) اجماع قوی دارند، ۲) حداقل ۳ ایجنت هم‌جهت‌اند، ۳) ایجنت هم‌جهت روی همان ارز در بک‌تست سودده بوده و "
               "۴) موتور ستاپ اعتبارسنجی‌شده (walk-forward روی همان ارز) همین الان ستاپ هم‌جهت داده باشد. "
               "اگر چیزی این فیلترها را رد نکند، چیزی نشان داده نمی‌شود — بهتر از سیگنال الکی.")
    h1, h2, h3, h4 = st.columns([1, 1, 1, 0.8])
    with h1:
        n_pool = st.select_slider("چند ارز بررسی شود", options=[12, 20, 30, 40], value=20, key="hunt_n")
    with h2:
        min_score = st.select_slider("حداقل قدرت اجماع", options=[0.15, 0.20, 0.25, 0.30, 0.40], value=0.20, key="hunt_min")
    with h3:
        min_agree = st.select_slider("حداقل ایجنت موافق", options=[2, 3, 4], value=3, key="hunt_agree")
    with h4:
        st.write("")
        go_hunt = st.button("🔎 شروع شکار بازار", type="primary", use_container_width=True, key="hunt_go")

    if go_hunt:
        t0 = time.time()
        with st.spinner(f"ایجنت‌ها در حال بررسی {n_pool} ارز روی {exchange} · {interval} … (۳۰–۹۰ ثانیه)"):
            picks, allres, errors = run_hunt(exchange, interval, int(n_pool), float(balance), fee_pct, float(min_score), int(min_agree))
        st.session_state["hunt"] = {"picks": picks, "all": allres, "errors": errors, "exchange": exchange,
                                    "interval": interval, "took": time.time() - t0, "ts": datetime.now().strftime("%Y-%m-%d %H:%M")}

    H = st.session_state.get("hunt")
    if not H:
        st.info("روی «🔎 شروع شکار بازار» بزن.")
        return
    picks, allres, errors = H["picks"], H["all"], H["errors"]
    st.caption(f"{len(allres)} ارز تحلیل شد روی {H['exchange']} · {H['interval']} در {H['took']:.0f} ثانیه · {H['ts']}"
               + (f" · {len(errors)} ارز خطا داد" if errors else ""))
    if errors and len(errors) >= max(2, len(allres)):
        st.error("تحلیل اکثر ارزها خطا داد — نمونه: " + errors[0][:200])

    longs = [p for p in picks if p["dir"] > 0]
    shorts = [p for p in picks if p["dir"] < 0]
    m1, m2, m3 = st.columns(3)
    m1.metric("برگزیده‌ها", len(picks))
    m2.metric("لانگ 🟢", len(longs))
    m3.metric("شورت 🔴", len(shorts))

    if not picks:
        st.warning("هیچ ارزی هر سه فیلتر را رد نکرد. یعنی الان ستاپ با لبه‌ی واضح در این تایم‌فریم نیست — "
                   "می‌توانی تایم‌فریم دیگری را امتحان کنی یا «حداقل ایجنت موافق» را روی ۲ بگذاری (ریسک بالاتر).")
    else:
        for rank_i, p in enumerate(picks, 1):
            pos, dec = p["pos"], p["dec"]
            is_long = p["dir"] > 0
            tone = "#16a34a" if is_long else "#ef4444"
            entry, stop = pos["entry"], pos["stop"]
            sl_pct = (stop / entry - 1) * 100
            tps = pos["targets"][:3]

            def _cell(lbl, val, sub, bg, col="#e2e8f0", lc="#94a3b8"):
                return (f"<div style='background:{bg};border-radius:10px;padding:8px'>"
                        f"<div style='font-size:10px;color:{lc}'>{lbl}</div>"
                        f"<div style='font-family:ui-monospace,monospace;font-weight:800;font-size:14px;color:{col}'>{val}</div>"
                        f"<div style='font-size:9px;color:#94a3b8'>{sub}</div></div>")

            cells = _cell("ورود", f"{entry:,.{dec}f}", "قیمت فعلی", "rgba(148,163,184,.08)") \
                + _cell("حد ضرر (SL)", f"{stop:,.{dec}f}", f"{sl_pct:+.2f}% · {pos['sl_reason']}", "rgba(239,68,68,.12)", "#ef4444", "#fca5a5")
            for i, (tp, rr, why) in enumerate(tps):
                cells += _cell(f"TP{i + 1} · {rr}R", f"{tp:,.{dec}f}", f"{(tp / entry - 1) * 100:+.2f}% · {why}",
                               f"rgba(34,197,94,{.10 + i * .04})", "#16a34a", "#86efac")
            agents_txt = " · ".join(p["agree"])
            reasons_html = "".join(f"<li>{r}</li>" for r in p["reasons"]) or "<li>—</li>"
            st.markdown(
                f"<div dir='rtl' style='border:1px solid rgba(148,163,184,.2);border-right:5px solid {tone};border-radius:14px;"
                f"padding:14px 16px;margin:10px 0;background:rgba(148,163,184,.05)'>"
                f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;align-items:center'>"
                f"<span style='font-size:18px;font-weight:800'>#{rank_i} {p['symbol']}</span>"
                f"<span style='font-family:ui-monospace,monospace;font-size:15px;color:{tone};font-weight:800'>{'لانگ 🟢' if is_long else 'شورت 🔴'}</span>"
                f"<span style='font-size:12px;color:#94a3b8'>اجماع {p['score']:+.2f} · اطمینان {p['confidence']}% · {p['n_agree']}/4 ایجنت موافق · ADX {p['adx']:.0f}</span>"
                f"</div>"
                f"<div style='display:grid;grid-template-columns:repeat({2 + len(tps)},1fr);gap:8px;margin-top:12px;text-align:center'>{cells}</div>"
                f"<div style='margin-top:10px;font-size:12px;color:#cbd5e1'>"
                f"<b>ایجنت‌های موافق:</b> {agents_txt}" + (f" · <b>پوزیشن باز:</b> {' · '.join(p['open_pos'])}" if p.get('open_pos') else "") + "<br>"
                f"<b>بک‌تست بهترین ایجنت هم‌جهت روی همین ارز:</b> بازده {p['best_ret']:+.2f}% · PF {p['best_pf']:.2f} · وین {p['best_win']:.0f}% · {p['best_trades']} معامله<br>"
                f"<b>✅ ستاپ اعتبارسنجی‌شده:</b> {p.get('v_txt', '')}"
                f"</div>"
                f"<div style='margin-top:8px;font-size:12px;color:#e2e8f0'><b>چرا؟</b><ul style='margin:4px 18px 0 0;padding:0;line-height:1.9'>{reasons_html}</ul></div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # جدول خلاصه + CSV
        rows = []
        for p in picks:
            tps = [t[0] for t in p["pos"]["targets"]] + [None, None, None]
            rows.append({"نماد": p["symbol"], "جهت": "لانگ 🟢" if p["dir"] > 0 else "شورت 🔴", "اجماع": round(p["score"], 2),
                         "اطمینان%": p["confidence"], "ایجنت موافق": f"{p['n_agree']}/4", "PF بک‌تست": round(p["best_pf"], 2),
                         "بازده بک‌تست%": round(p["best_ret"], 2), "ورود": p["pos"]["entry"], "SL": p["pos"]["stop"],
                         "TP1": tps[0], "TP2": tps[1], "TP3": tps[2], "R:R": p["pos"]["rr"]})
        hunt_df = pd.DataFrame(rows)
        st.dataframe(hunt_df, use_container_width=True, hide_index=True)
        st.download_button("💾 ذخیره برگزیده‌ها (CSV)", data=hunt_df.to_csv(index=False).encode("utf-8"),
                           file_name=f"hunt_{H['exchange']}_{H['interval']}.csv", mime="text/csv", key="hunt_csv")

        if st.button("💾 ذخیره‌ی برگزیده‌ها در 👥 تحلیل‌های کاربران", key="hunt_save"):
            for p in picks[:5]:
                tps = [t[0] for t in p["pos"]["targets"]] + [None, None, None]
                dec = p["dec"]
                txt = (f"شکار بازار {H['exchange']}/{H['interval']} — {p['n_agree']}/4 ایجنت موافق ({', '.join(p['agree'])}) · اجماع {p['score']:+.2f}\n"
                       f"بک‌تست بهترین ایجنت هم‌جهت روی همین ارز: {p['best_ret']:+.2f}% · PF {p['best_pf']:.2f} · وین {p['best_win']:.0f}%\n"
                       f"حد ضرر: {p['pos']['sl_reason']}\n" + "\n".join(f"TP{i + 1} {tp:,.{dec}f} ({rr}R) ← {why}" for i, (tp, rr, why) in enumerate(p["pos"]["targets"]))
                       + "\nدلایل: " + " | ".join(p["reasons"]) + "\nتحلیل قانون‌محور + بک‌تست؛ توصیه‌ی سرمایه‌گذاری نیست.")
                save_duel({"name": "🔎 شکار بازار (ایجنت‌ها)", "symbol": p["symbol"].upper(), "exchange": H["exchange"],
                           "bias": "لانگ 🟢" if p["dir"] > 0 else "شورت 🔴", "tf": H["interval"], "entry": float(p["pos"]["entry"]),
                           "stop": float(p["pos"]["stop"]), "tp1": tps[0], "tp2": tps[1], "tp3": tps[2],
                           "rr": f"1:{p['pos']['rr']}", "confidence": int(p["confidence"]), "text": txt, "image": "",
                           "ts": datetime.now().strftime("%Y-%m-%d %H:%M")})
            st.success(f"{min(5, len(picks))} تحلیل ذخیره شد → صفحه‌ی اصلی → «تحلیل‌ها» → تب «👥 تحلیل‌های کاربران».")

    with st.expander(f"📋 همه‌ی {len(allres)} ارز بررسی‌شده (چرا بقیه انتخاب نشدند)", expanded=False):
        rows = []
        for o in sorted(allres, key=lambda o: -abs(o["score"])):
            why = []
            if o["dir"] == 0 or abs(o["score"]) < min_score:
                why.append("اجماع ضعیف")
            if o["n_agree"] < min_agree:
                why.append(f"فقط {o['n_agree']} ایجنت موافق")
            if o["n_prof"] == 0:
                why.append("ایجنت هم‌جهت در بک‌تست سودده نبود")
            if o["pos"]["direction"] != 0 and o["pos"]["rr"] < 1.0:
                why.append("R:R زیر ۱")
            if not o.get("v_ok"):
                why.append(o.get("v_txt", "ستاپ معتبر ندارد"))
            rows.append({"نماد": o["symbol"], "تمایل": "لانگ 🟢" if o["dir"] > 0 else "شورت 🔴" if o["dir"] < 0 else "خنثی ⚪",
                         "اجماع": round(o["score"], 2), "ایجنت موافق": f"{o['n_agree']}/4", "PF هم‌جهت": round(o["best_pf"], 2),
                         "نتیجه": "✅ برگزیده" if not why else " · ".join(why)})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if errors:
            st.caption("خطاها: " + " | ".join(errors[:5]))


# ----------------------------------------------------------------------------- inputs
c1, c2, c3, c4, c5 = st.columns([1.3, 1, 1, 1, 1])
with c1:
    symbol = st.text_input("ارز", value="BTC-USDT", help="برای Lighter فقط BTC بنویس (بدون USDT)")
with c2:
    exchange = st.selectbox("صرافی", EXCHANGES, index=0)
with c3:
    interval = st.selectbox("تایم‌فریم", ["15min", "1hour", "4hour", "1day"], index=1)
with c4:
    balance = st.number_input("بالانس شروع", value=10000, min_value=100)
with c5:
    n_candles = st.select_slider("تعداد کندل", options=[200, 300, 400, 500], value=300)
fee_pct = 0.06

if exchange == "Lighter":
    st.info("Lighter پرپ هست - مثلا BTC یا ETH بنویس، نه BTC-USDT")

def _dec_for(price: float) -> int:
    """تعداد اعشار مناسب نمایش — برای میم‌کوین‌های خیلی ارزان هم رقم معنادار نشان بدهد."""
    p = abs(float(price)) if np.isfinite(price) else 1.0
    return 2 if p >= 1000 else 4 if p >= 1 else 6 if p >= 0.01 else 8 if p >= 0.0001 else 10


def calculate_duel(exchange, symbol, interval, n_candles, balance, fee_pct):
    d, sym_used, src = get_df(exchange, symbol, interval, int(n_candles))
    required = {"open", "high", "low", "close", "volume"}
    if not isinstance(d, pd.DataFrame) or len(d) < 60 or not required.issubset(d.columns):
        raise ValueError("حداقل ۶۰ کندل معتبر با قیمت و حجم برای دوئل لازم است.")
    prices = d[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("داده‌ی قیمت نامعتبر است؛ صرافی یا نماد دیگری را انتخاب کن.")
    if G is None:
        st.warning("core/gaps.py پیدا نشد؛ FVG/BVG در این دوئل صفر در نظر گرفته می‌شود.")
    F, extras = build_features(d)
    close = d["close"].to_numpy(dtype=float)
    price = float(close[-1])
    dec = _dec_for(price)
    extras["close10"] = float(close[-11])
    extras["prior_hi"] = float(extras["prior_hi"].iloc[-1]) if np.isfinite(extras["prior_hi"].iloc[-1]) else price
    extras["prior_lo"] = float(extras["prior_lo"].iloc[-1]) if np.isfinite(extras["prior_lo"].iloc[-1]) else price

    results = {}
    for name, spec in AGENTS.items():
        s = agent_scores(F, spec)
        sig = signals_with_hysteresis(s, spec["thr"])
        bt = backtest(close, sig, float(balance), fee_pct)
        direction = int(sig[-1])
        r_last = F.iloc[-1]
        rows = []
        for k, w in spec["weights"].items():
            val = float(np.nan_to_num(r_last[k]))
            rows.append({"فاکتور": FACTOR_FA[k], "مدرک (مشاهده‌ی واقعی)": describe(k, r_last, d.iloc[-1], dec, extras),
                         "امتیاز": round(val, 2), "وزن": w, "سهم در تصمیم": round(val * w, 3), "رأی": _verdict(val)})
        results[name] = {
            "spec": spec, "score": float(s[-1]), "sig": direction, "bt": bt, "rows": rows,
            "position": build_position(d, F, extras, direction, dec),
            "lean": _verdict(float(s[-1])),
        }

    weights = {}
    for name, r in results.items():
        bt = r["bt"]
        q = np.clip(bt["total"] / 10, -1, 2) + np.clip(bt["pf"] - 1, -1, 1) + (bt["win"] - 50) / 50 - bt["dd"] / 50
        weights[name] = float(max(0.15, 1 + q))
    tot_w = sum(weights.values())
    final_s = sum(weights[n] * results[n]["score"] for n in results) / tot_w
    votes = {n: results[n]["sig"] for n in results}
    agree = sum(1 for v in votes.values() if v == np.sign(final_s) and v != 0)
    final_dir = 1 if final_s > 0.15 else -1 if final_s < -0.15 else 0
    confidence = int(min(95, 40 + abs(final_s) * 80 + agree * 7))
    final_pos = build_position(d, F, extras, final_dir, dec)
    winner = max(results, key=lambda n: (results[n]["bt"]["total"], results[n]["bt"]["pf"]))

    return {
        "d": d, "F": F, "extras": extras, "results": results, "weights": weights, "final_s": final_s,
        "final_dir": final_dir, "confidence": confidence, "final_pos": final_pos, "winner": winner,
        "sym": sym_used, "exchange": exchange, "interval": interval, "dec": dec, "src": src, "balance": float(balance),
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


tab_duel, tab_hunt = st.tabs(["⚔️ دوئل روی یک ارز", "🔎 شکار بازار — بهترین لانگ/شورت‌های صرافی"])

with tab_hunt:
    render_hunt(exchange, interval, float(balance), fee_pct)

with tab_duel:
    if st.button("🚀 شروع دوئل", type="primary", use_container_width=True):
        try:
            with st.spinner("در حال گرفتن کندل‌ها و ساختن مدارک…"):
                new_result = calculate_duel(exchange, symbol, interval, n_candles, balance, fee_pct)
            st.session_state["duel"] = new_result
            # A second run must not keep the editable report from the first run.
            st.session_state.pop("duel_txt", None)
        except Exception as exc:
            st.error(f"دوئل اجرا نشد: {exc}")
            st.info("اتصال به صرافی، نماد و تایم‌فریم را بررسی کن و دوباره «شروع دوئل» را بزن.")
            if st.session_state.get("duel"):
                st.warning("نتایج زیر مربوط به اجرای موفق قبلی‌اند؛ تحلیل تازه‌ای تولید نشده است.")

    # ----------------------------------------------------------------------------- results
    S = st.session_state.get("duel")
    if not S:
        st.info("یک ارز انتخاب کن و «🚀 شروع دوئل» را بزن.")
    else:

        d, F, extras, results, dec = S["d"], S["F"], S["extras"], S["results"], S["dec"]
        price = float(d["close"].iloc[-1])
        st.caption(f"دیتا: {S['sym']} روی {S['exchange']} · {S['interval']} · {len(d)} کندل · منبع: {S['src']} · "
                   f"آخرین کندل {str(d['dt'].iloc[-1])[:16] if 'dt' in d.columns else ''} · قیمت {price:,.{dec}f} · {S['ts']}")

        # --- equity chart -------------------------------------------------------------------
        import plotly.graph_objects as go  # noqa: E402
        fig = go.Figure()
        for name, r in results.items():
            fig.add_trace(go.Scatter(y=r["bt"]["eq"], mode="lines", name=f"{name} ({r['bt']['total']:+.2f}%)",
                                     line=dict(color=r["spec"]["color"], width=2)))
        fig.update_layout(template="plotly_dark", height=380, title="Equity — موجودی هر ایجنت روی همین کندل‌ها (با کارمزد)",
                          margin=dict(l=20, r=20, t=50, b=20), legend=dict(orientation="h"))
        st.plotly_chart(fig, use_container_width=True)

        dfres = pd.DataFrame([{
            "ایجنت": n, "بازده%": round(r["bt"]["total"], 2), "معاملات": r["bt"]["trades"], "وین%": round(r["bt"]["win"], 1),
            "PF": round(r["bt"]["pf"], 2), "DD%": round(r["bt"]["dd"], 2), "در بازار%": round(r["bt"]["exposure"], 0),
            "۲۰ کندل اخیر%": round(r["bt"]["recent"], 2), "امتیاز الان": round(r["score"], 2),
            "پوزیشن الان": "LONG 🟢" if r["sig"] > 0 else "SHORT 🔴" if r["sig"] < 0 else "FLAT ⚪",
            "وزن در اجماع": round(S["weights"][n] / sum(S["weights"].values()) * 100, 0),
        } for n, r in results.items()]).sort_values("بازده%", ascending=False)
        st.dataframe(dfres, use_container_width=True, hide_index=True)
        w = results[S["winner"]]
        st.success(f"🏆 برنده‌ی بک‌تست: {S['winner']} با {w['bt']['total']:+.2f}% — {w['bt']['trades']} معامله — وین {w['bt']['win']:.0f}% — PF {w['bt']['pf']:.2f}")

        # --- final consensus position -----------------------------------------------------
        st.divider()
        st.subheader("🎯 بهترین پوزیشن (اجماع وزن‌دار ایجنت‌ها)")
        try:
            import app_base as _B
            _vp = _B.setup_plan(d)
            _agree = _vp["status"] == "active" and ((_vp["direction"].startswith("لانگ") and S["final_dir"] > 0) or (_vp["direction"].startswith("شورت") and S["final_dir"] < 0))
            if _agree:
                st.success(f"✅ موتور ستاپ اعتبارسنجی‌شده هم‌جهت است — {_vp['why']}")
            elif _vp["status"] == "active":
                st.error(f"⚠️ موتور ستاپ اعتبارسنجی‌شده **خلاف** نظر ایجنت‌هاست ({_vp['direction']}) — {_vp['why']}. در تست walk-forward، ورود بر اساس اجماع اندیکاتورها به‌تنهایی لبه نداشت؛ این پوزیشن را نگیر.")
            else:
                st.warning(f"⏸ موتور ستاپ اعتبارسنجی‌شده می‌گوید انتظار: {_vp.get('why', '')} · {_vp.get('watch', '')}")
            with st.expander("📐 اعتبار ستاپ‌ها روی همین نماد (walk-forward)", expanded=False):
                st.dataframe(_B.setup_stats_table(_vp["stats"]), use_container_width=True, hide_index=True)
        except Exception as _e:  # noqa: BLE001
            st.caption(f"اعتبارسنجی ستاپ انجام نشد: {_e}")
        fd = S["final_dir"]
        tone = "#16a34a" if fd > 0 else "#ef4444" if fd < 0 else "#94a3b8"
        st.markdown(
            f"<div dir='rtl' style='border:1px solid {tone}66;border-right:6px solid {tone};border-radius:14px;padding:14px 16px;background:{tone}12'>"
            f"<b style='font-size:18px'>{'لانگ 🟢' if fd > 0 else 'شورت 🔴' if fd < 0 else 'خنثی ⚪ — صبر'}</b> · امتیاز اجماع {S['final_s']:+.2f} · اطمینان {S['confidence']}٪ · "
            f"وزن هر ایجنت از عملکرد واقعی‌اش روی همین {len(d)} کندل می‌آید (بازده، PF، وین‌ریت، دراودان).</div>",
            unsafe_allow_html=True)
        render_position(S["final_pos"], dec, tone)

        # master evidence
        master_keys = ["ema_align", "struct", "di_adx", "supertrend", "macd", "roc", "cmf", "money_delta", "obv",
                       "sweep", "brk", "fvg", "bvg", "candle", "z_fade", "rsi_ext"]
        r_last = F.iloc[-1]
        used_by = {k: [n for n, r in results.items() if k in r["spec"]["weights"]] for k in master_keys}
        master = pd.DataFrame([{
            "حوزه": ("جهت بازار" if k in ("ema_align", "struct", "di_adx", "supertrend") else
                     "مومنتوم" if k in ("macd", "roc", "brk") else
                     "جریان پول" if k in ("cmf", "money_delta", "obv") else
                     "نقدینگی" if k == "sweep" else "گپ‌ها (FVG/BVG)" if k in ("fvg", "bvg") else
                     "کندل" if k == "candle" else "بازگشت به میانگین"),
            "فاکتور": FACTOR_FA[k], "مدرک": describe(k, r_last, d.iloc[-1], dec, extras),
            "امتیاز": round(float(np.nan_to_num(r_last[k])), 2), "رأی": _verdict(float(np.nan_to_num(r_last[k]))),
            "استفاده‌کننده": "، ".join(x.split(" ")[0] for x in used_by[k]) or "—",
        } for k in master_keys])
        st.markdown("**جدول مدارک نهایی (همه‌ی ابزارها در یک نگاه)**")
        st.dataframe(master, use_container_width=True, hide_index=True)

        # --- per-agent evidence tables ---------------------------------------------------------
        st.divider()
        st.subheader("🧾 جدول دلیل و پوزیشن هر ایجنت")
        for name, r in results.items():
            col = r["spec"]["color"]
            with st.expander(f"{name} — {r['lean']} · امتیاز {r['score']:+.2f} (آستانه ±{r['spec']['thr']}) · بک‌تست {r['bt']['total']:+.2f}%", expanded=True):
                st.markdown(f"<div dir='rtl' style='color:#94a3b8;font-size:13px;border-right:3px solid {col};padding-right:8px'>{r['spec']['desc']}</div>",
                            unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(r["rows"]), use_container_width=True, hide_index=True)
                contrib = sum(x["سهم در تصمیم"] for x in r["rows"])
                st.caption(f"جمع سهم‌ها = {contrib:+.3f} → {'LONG' if r['sig'] > 0 else 'SHORT' if r['sig'] < 0 else 'FLAT'} "
                           f"(ورود وقتی |امتیاز| > {r['spec']['thr']}، خروج وقتی < {r['spec']['thr'] * 0.4:.2f}) · "
                           f"همین قانون‌ها در بک‌تست کندل‌به‌کندل اعمال شده‌اند.")
                render_position(r["position"], dec, col)

        # --- proof: candles / liquidity / flow / gaps / structure -------------------------------
        st.divider()
        st.subheader("📎 مدارک خام")
        p1, p2 = st.columns(2)
        with p1:
            with st.expander("🕯️ ۱۲ کندل آخر (آناتومی)", expanded=False):
                tail = d.tail(12).copy()
                ftail = F.tail(12)
                cand = pd.DataFrame({
                    "زمان": tail["dt"].astype(str).str[:16] if "dt" in tail.columns else tail.index.astype(str),
                    "باز": tail["open"].round(dec), "بالا": tail["high"].round(dec), "پایین": tail["low"].round(dec), "بسته": tail["close"].round(dec),
                    "رنگ": np.where(tail["close"] >= tail["open"], "🟢", "🔴"),
                    "بدنه٪": ftail["body_pct"].round(0).values, "حجم×میانگین": ftail["vol_ratio"].round(2).values,
                    "الگو": ftail["candle_name"].values, "FVG": ftail["fvg"].round(2).values, "BVG": ftail["bvg"].round(2).values,
                }).iloc[::-1]
                st.dataframe(cand, use_container_width=True, hide_index=True)
            with st.expander("💧 نقدینگی (سوییپ‌ها و استخرها)", expanded=False):
                sw = F[F["sweep_raw"] != 0].tail(8)
                if sw.empty:
                    st.write("در این بازه سوییپ ثبت نشده.")
                else:
                    st.dataframe(pd.DataFrame({
                        "زمان": d.loc[sw.index, "dt"].astype(str).str[:16] if "dt" in d.columns else sw.index.astype(str),
                        "نوع": np.where(sw["sweep_raw"] > 0, "سوییپ کف → صعودی 🟢", "سوییپ سقف → نزولی 🔴"),
                        "قیمت بسته": d.loc[sw.index, "close"].round(dec).values,
                    }).iloc[::-1], use_container_width=True, hide_index=True)
                highs, lows = _swings(d.tail(120).reset_index(drop=True))
                st.write(f"استخر نقدینگی بالا (equal highs): {'بله' if F['eqh'].iloc[-1] else 'خیر'} · "
                         f"پایین (equal lows): {'بله' if F['eql'].iloc[-1] else 'خیر'} · "
                         f"سقف ۲۰ کندل {extras['prior_hi']:,.{dec}f} · کف ۲۰ کندل {extras['prior_lo']:,.{dec}f}")
                lv = pd.DataFrame(
                    [{"نوع": "سقف سوئینگ (نقدینگی خریداران)", "سطح": round(p, dec)} for _, p in highs[-5:]] +
                    [{"نوع": "کف سوئینگ (نقدینگی فروشندگان)", "سطح": round(p, dec)} for _, p in lows[-5:]])
                if not lv.empty:
                    st.dataframe(lv.sort_values("سطح", ascending=False), use_container_width=True, hide_index=True)
        with p2:
            with st.expander("💸 جریان پول (ورود/خروج)", expanded=False):
                rl = F.iloc[-1]
                st.dataframe(pd.DataFrame([
                    {"سنجه": "CMF (۲۰)", "مقدار": f"{float(d['cmf'].iloc[-1]) if 'cmf' in d.columns else 0:+.3f}", "تفسیر": "ورود پول" if rl["cmf"] > 0.1 else "خروج پول" if rl["cmf"] < -0.1 else "خنثی"},
                    {"سنجه": "MFI (۱۴)", "مقدار": f"{float(d['mfi'].iloc[-1]) if 'mfi' in d.columns else 50:.1f}", "تفسیر": "فشار خرید" if rl["mfi_c"] > 0.2 else "فشار فروش" if rl["mfi_c"] < -0.2 else "متعادل"},
                    {"سنجه": "شیب OBV (۱۰)", "مقدار": f"{float(rl['obv']):+.2f}", "تفسیر": "انباشت" if rl["obv"] > 0.1 else "توزیع" if rl["obv"] < -0.1 else "خنثی"},
                    {"سنجه": "دلتای خرید/فروش (۲۰)", "مقدار": f"{float(rl['money_delta']):+.2f}", "تفسیر": "خریدار تهاجمی" if rl["money_delta"] > 0.1 else "فروشنده تهاجمی" if rl["money_delta"] < -0.1 else "متعادل"},
                    {"سنجه": "حجم سبز/قرمز (۲۰)", "مقدار": f"{float(rl['upvol20']):,.0f} / {float(rl['dnvol20']):,.0f}", "تفسیر": "حجم با خریدارهاست" if rl["upvol20"] > rl["dnvol20"] else "حجم با فروشنده‌هاست"},
                    {"سنجه": "حجم کندل آخر", "مقدار": f"{float(rl['vol_ratio']):.2f}× میانگین", "تفسیر": "حجم بالا" if rl["vol_ratio"] > 1.3 else "حجم عادی/کم"},
                ]), use_container_width=True, hide_index=True)
            with st.expander("🧱 زون‌های FVG / BVG فعال", expanded=False):
                if extras.get("gaps") is not None and G is not None:
                    zf = G.zones_frame(extras["gaps"], price, dec)
                    if zf.empty:
                        st.write("زون فعالی نزدیک قیمت نیست.")
                    else:
                        st.dataframe(zf, use_container_width=True, hide_index=True)
                    st.caption(G.GAP_HELP["FVG"] + " · " + G.GAP_HELP["BVG"])
                else:
                    st.write("موتور FVG/BVG در دسترس نیست.")

        # --- price chart with zones, liquidity and final position --------------------------------
        with st.expander("📈 چارت با زون‌ها، سطوح نقدینگی و پوزیشن نهایی", expanded=True):
            dc = d.tail(160).reset_index(drop=True)
            fig2 = go.Figure()
            fig2.add_trace(go.Candlestick(x=dc["dt"] if "dt" in dc.columns else dc.index, open=dc["open"], high=dc["high"], low=dc["low"], close=dc["close"],
                                          increasing_line_color="#26a69a", decreasing_line_color="#ef5350", name="قیمت"))
            for col_name, colr in (("ema20", "#2962ff"), ("ema50", "#ff9800")):
                if col_name in dc.columns:
                    fig2.add_trace(go.Scatter(x=dc["dt"], y=dc[col_name], line=dict(color=colr, width=1.2), name=col_name.upper()))
            if extras.get("gaps") is not None and G is not None:
                shapes, notes = G.plotly_shapes(extras["gaps"], x_end=dc["dt"].iloc[-1], price=price)
                x0 = dc["dt"].iloc[0]
                for s_ in shapes:
                    if s_["x0"] < x0:
                        s_["x0"] = x0
                    fig2.add_shape(**s_)
                for n_ in notes:
                    if n_["x"] >= x0:
                        fig2.add_annotation(**n_)
            fp = S["final_pos"]
            if fp["direction"] != 0:
                fig2.add_hline(y=fp["entry"], line_color="#f59e0b", line_width=1.3, annotation_text="ENTRY", annotation_position="right")
                fig2.add_hline(y=fp["stop"], line_color="#ef4444", line_dash="dash", annotation_text="SL", annotation_position="right")
                for i, (tp, rr, _) in enumerate(fp["targets"]):
                    fig2.add_hline(y=tp, line_color="#22c55e", line_dash="dash", annotation_text=f"TP{i + 1} {rr}R", annotation_position="right")
            fig2.add_hline(y=extras["prior_hi"], line_color="rgba(148,163,184,.6)", line_dash="dot", annotation_text="سقف ۲۰", annotation_position="left")
            fig2.add_hline(y=extras["prior_lo"], line_color="rgba(148,163,184,.6)", line_dash="dot", annotation_text="کف ۲۰", annotation_position="left")
            fig2.update_layout(template="plotly_dark", height=560, xaxis_rangeslider_visible=False, margin=dict(l=10, r=70, t=30, b=10),
                               legend=dict(orientation="h"))
            st.plotly_chart(fig2, use_container_width=True)

        # --- save to community ----------------------------------------------------------------
        st.divider()
        fp = S["final_pos"]
        lines = [f"دوئل ایجنت‌ها روی {S['sym']} ({S['exchange']}/{S['interval']}) · {len(d)} کندل · {S['ts']}",
                 f"پوزیشن اجماعی: {pos_text(fp, dec)} · اطمینان {S['confidence']}٪ · امتیاز {S['final_s']:+.2f}"]
        if fp["direction"] != 0:
            lines.append(f"حد ضرر بر اساس: {fp['sl_reason']} · اهداف: " + " | ".join(f"TP{i + 1} ← {why}" for i, (_, _, why) in enumerate(fp["targets"])))
        lines.append("— ایجنت‌ها —")
        for n, r in results.items():
            lines.append(f"{n}: {r['lean']} (امتیاز {r['score']:+.2f}) · بک‌تست {r['bt']['total']:+.2f}% · {r['bt']['trades']} ترید · وین {r['bt']['win']:.0f}% · PF {r['bt']['pf']:.2f} · DD {r['bt']['dd']:.1f}%")
            top = sorted(r["rows"], key=lambda x: abs(x["سهم در تصمیم"]), reverse=True)[:3]
            lines.append("   دلایل اصلی: " + " | ".join(f"{x['فاکتور']}: {x['مدرک (مشاهده‌ی واقعی)']}" for x in top))
        lines.append("— مدارک کلیدی —")
        for _, m in master.head(10).iterrows():
            lines.append(f"{m['حوزه']} / {m['فاکتور']}: {m['مدرک']} → {m['رأی']}")
        lines.append(f"برنده‌ی بک‌تست: {S['winner']}. این نتیجه بک‌تست + تحلیل قانون‌محور است، نه سیگنال قطعی؛ مدیریت ریسک الزامی است.")
        analysis_text = "\n".join(lines)
        st.text_area("📝 تحلیل کامل (می‌ره تو 👥 تحلیل‌های کاربران)", value=analysis_text, height=260, key="duel_txt")

        if st.button("💾 ذخیره در 👥 تحلیل‌های کاربران", type="primary"):
            bias = "لانگ 🟢" if fp["direction"] > 0 else "شورت 🔴" if fp["direction"] < 0 else "خنثی ⚪"
            tps = [t[0] for t in fp["targets"]] + [None, None, None]
            save_duel({
                "name": f"🤖 اجماع ایجنت‌ها (برنده: {S['winner']})", "symbol": S["sym"].upper(), "exchange": S["exchange"],
                "bias": bias, "tf": S["interval"], "entry": float(fp["entry"]),
                "stop": float(fp["stop"]) if fp["stop"] else None,
                "tp1": float(tps[0]) if tps[0] else None, "tp2": float(tps[1]) if tps[1] else None, "tp3": float(tps[2]) if tps[2] else None,
                "rr": f"1:{fp['rr']}" if fp["rr"] else "",
                "confidence": int(S["confidence"]), "text": st.session_state.get("duel_txt", analysis_text),
                "image": "", "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
            st.success("ذخیره شد! در صفحه‌ی اصلی → بخش «🧩 تحلیل‌ها» → تب «👥 تحلیل‌های کاربران» ببین.")
