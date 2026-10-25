"""core/duel_engine.py — موتور مشترک ایجنت‌ها
=============================================
موتور تحلیلی مشترک ۴ ایجنت که «میدان ایجنت‌ها» (Agent Arena) از آن استفاده
می‌کند — ~۲۰ فاکتور علّی، بک‌تست کندل‌به‌کندل با کارمزد، هیسترزیس سیگنال و
سازنده‌ی پوزیشن ساختاری.

محتوا:
  • _ema / _fallback_indicators / get_df        — دیتا و اندیکاتورها
  • _clip / _col / build_features               — ~۲۰ فاکتور علّی در بازه [-1,+1]
  • AGENTS / FACTOR_FA / describe / _verdict    — ۴ ایجنت و مدارک هر فاکتور
  • agent_scores / signals_with_hysteresis      — امتیاز و سیگنال با هیسترزیس
  • backtest                                    — بک‌تست کندل‌به‌کندل با کارمزد
  • _swings / build_position / pos_text         — سازنده‌ی پوزیشن ساختاری
  • _dec_for / calculate_duel                   — اجرای کامل تحلیل روی یک ارز
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

try:
    from core import gaps as G
except Exception:  # noqa: BLE001
    G = None


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
