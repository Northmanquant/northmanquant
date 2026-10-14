"""
NorthmanQuant — Free Lite Edition (Streamlit)

نسخه‌ی سبک و رایگان نورث‌من‌کوانت برای دیپلوی رایگان روی Streamlit Community Cloud
یا Hugging Face Spaces. بدون دیتابیس و بدون هیچ کلید API — همه‌چیز از APIهای عمومی
صرافی‌ها خوانده می‌شود.

اجرا محلی:  streamlit run streamlit_app/app.py
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import streamlit as st
from PIL import Image

KUCOIN = "https://api.kucoin.com"
BINANCE = "https://api.binance.com"
BYBIT = "https://api.bybit.com"
OKX = "https://www.okx.com"

INTERVAL_MINUTES = {"15min": 15, "1hour": 60, "4hour": 240, "1day": 1440, "1week": 10080}
KUCOIN_TF = {"15min": "15min", "1hour": "1hour", "4hour": "4hour", "1day": "1day", "1week": "1week"}
BINANCE_TF = {"15min": "15m", "1hour": "1h", "4hour": "4h", "1day": "1d", "1week": "1w"}
BYBIT_TF = {"15min": "15", "1hour": "60", "4hour": "240", "1day": "D", "1week": "W"}
OKX_TF = {"15min": "15m", "1hour": "1H", "4hour": "4H", "1day": "1D", "1week": "1W"}

ENTER = 40
EXIT = -10


# ------------------------------------------------------------------ symbols

def normalize_symbol(raw: str) -> str:
    s = (raw or "BTC-USDT").strip().upper().replace("/", "-").replace("_", "-").replace(" ", "")
    if not s:
        return "BTC-USDT"
    if "-" in s:
        return s
    for q in ("USDT", "USDC", "BTC", "ETH", "EUR"):
        if s.endswith(q) and len(s) > len(q):
            return f"{s[: -len(q)]}-{q}"
    return f"{s}-USDT"


# ------------------------------------------------------------------ data

@st.cache_data(ttl=60, show_spinner=False)
def fetch_candles(exchange: str, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
    """OHLCV from public exchange APIs. Falls back to KuCoin when an exchange is region-blocked."""
    try:
        return _fetch_candles(exchange, symbol, interval, limit)
    except Exception:
        if exchange != "KuCoin":
            return _fetch_candles("KuCoin", symbol, interval, limit)
        raise


def _fetch_candles(exchange: str, symbol: str, interval: str, limit: int) -> pd.DataFrame:
    headers = {"User-Agent": "northmanquant-lite/1.0", "accept": "application/json"}
    rows: list[dict] = []

    if exchange == "KuCoin":
        minutes = INTERVAL_MINUTES[interval]
        end = int(datetime.now(timezone.utc).timestamp())
        start = end - minutes * 60 * (limit + 10)
        r = requests.get(
            f"{KUCOIN}/api/v1/market/candles",
            params={"symbol": symbol, "type": KUCOIN_TF[interval], "startAt": start, "endAt": end},
            headers=headers, timeout=20,
        )
        r.raise_for_status()
        data = r.json().get("data") or []
        # KuCoin order: [time, open, close, high, low, volume, turnover]
        rows = [
            {"time": int(x[0]) * 1000, "open": float(x[1]), "close": float(x[2]),
             "high": float(x[3]), "low": float(x[4]), "volume": float(x[5])}
            for x in data
        ]
    elif exchange == "Binance":
        r = requests.get(
            f"{BINANCE}/api/v3/klines",
            params={"symbol": symbol.replace("-", ""), "interval": BINANCE_TF[interval], "limit": min(1000, limit)},
            headers=headers, timeout=20,
        )
        r.raise_for_status()
        rows = [
            {"time": int(x[0]), "open": float(x[1]), "high": float(x[2]),
             "low": float(x[3]), "close": float(x[4]), "volume": float(x[5])}
            for x in r.json()
        ]
    elif exchange == "Bybit":
        r = requests.get(
            f"{BYBIT}/v5/market/kline",
            params={"category": "spot", "symbol": symbol.replace("-", ""), "interval": BYBIT_TF[interval], "limit": min(1000, limit)},
            headers=headers, timeout=20,
        )
        r.raise_for_status()
        data = (r.json().get("result") or {}).get("list") or []
        rows = [
            {"time": int(x[0]), "open": float(x[1]), "high": float(x[2]),
             "low": float(x[3]), "close": float(x[4]), "volume": float(x[5])}
            for x in data
        ]
    else:  # OKX
        r = requests.get(
            f"{OKX}/api/v5/market/candles",
            params={"instId": symbol, "bar": OKX_TF[interval], "limit": 300},
            headers=headers, timeout=20,
        )
        r.raise_for_status()
        rows = [
            {"time": int(x[0]), "open": float(x[1]), "high": float(x[2]),
             "low": float(x[3]), "close": float(x[4]), "volume": float(x[5])}
            for x in (r.json().get("data") or [])
        ]

    df = pd.DataFrame(rows)
    if df.empty or len(df) < 40:
        raise ValueError("کندل کافی برای این نماد/صرافی برنگشت.")
    df = df.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
    df = df[df["close"] > 0].tail(limit).reset_index(drop=True)
    df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df


@st.cache_data(ttl=60, show_spinner=False)
def fetch_top_coins(min_turnover: float = 1_000_000, limit: int = 15) -> dict:
    r = requests.get(f"{KUCOIN}/api/v1/market/allTickers", timeout=25, headers={"User-Agent": "northmanquant-lite/1.0"})
    r.raise_for_status()
    tickers = (r.json().get("data") or {}).get("ticker") or []
    rows = []
    for t in tickers:
        sym = t.get("symbol", "")
        if not sym.endswith("-USDT"):
            continue
        turnover = float(t.get("volValue") or 0)
        if turnover < min_turnover:
            continue
        rows.append({
            "symbol": sym,
            "price": float(t.get("last") or 0),
            "change%": float(t.get("changeRate") or 0) * 100,
            "high": float(t.get("high") or 0),
            "low": float(t.get("low") or 0),
            "turnoverM$": turnover / 1e6,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return {"gainers": df, "losers": df, "volume": df}
    return {
        "gainers": df.sort_values("change%", ascending=False).head(limit).reset_index(drop=True),
        "losers": df.sort_values("change%").head(limit).reset_index(drop=True),
        "volume": df.sort_values("turnoverM$", ascending=False).head(limit).reset_index(drop=True),
    }


BULLISH = ["surge", "rally", "soar", "bullish", "record", "adoption", "gain", "jump", "inflow", "approved",
           "buy", "breakout", "launch", "rise", "climbs", "boost", "recover", "rebound", "spike", "milestone"]
BEARISH = ["crash", "plunge", "dump", "bearish", "loss", "hack", "lawsuit", "ban", "sell-off", "outflow",
           "liquidation", "fear", "drop", "falls", "decline", "warning", "fraud", "scam", "down", "sink", "slump"]
FEEDS = [
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Decrypt", "https://decrypt.co/feed"),
]


@st.cache_data(ttl=300, show_spinner=False)
def fetch_news(limit: int = 30) -> pd.DataFrame:
    items = []
    for source, url in FEEDS:
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "northmanquant-lite/1.0"})
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            for node in root.iter("item"):
                title = (node.findtext("title") or "").strip()
                link = (node.findtext("link") or "").strip()
                date = (node.findtext("pubDate") or "").strip()
                if not title or not link:
                    continue
                low = title.lower()
                score = sum(1 for w in BULLISH if w in low) - sum(1 for w in BEARISH if w in low)
                items.append({
                    "title": title, "link": link, "source": source, "date": date,
                    "sentiment": "مثبت 🟢" if score > 0 else "منفی 🔴" if score < 0 else "خنثی ⚪",
                })
        except Exception:
            continue
    df = pd.DataFrame(items)
    return df.head(limit) if not df.empty else df


# ------------------------------------------------------------------ indicators

def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    c, h, l, v = d["close"], d["high"], d["low"], d["volume"]

    d["ema20"] = _ema(c, 20)
    d["ema50"] = _ema(c, 50)
    d["ema200"] = _ema(c, 200)
    d["rsi"] = _rsi(c, 14)

    ema12, ema26 = _ema(c, 12), _ema(c, 26)
    d["macd"] = ema12 - ema26
    d["macd_signal"] = _ema(d["macd"], 9)
    d["macd_hist"] = d["macd"] - d["macd_signal"]

    ll = l.rolling(14).min()
    hh = h.rolling(14).max()
    k = (c - ll) / (hh - ll).replace(0, np.nan) * 100
    d["stoch_k"] = k.rolling(3).mean().fillna(50)
    d["stoch_d"] = d["stoch_k"].rolling(3).mean()

    prev_close = c.shift(1)
    tr = pd.concat([h - l, (h - prev_close).abs(), (l - prev_close).abs()], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()

    mid = c.rolling(20).mean()
    std = c.rolling(20).std()
    d["bb_mid"], d["bb_up"], d["bb_lo"] = mid, mid + 2 * std, mid - 2 * std

    tp = (h + l + c) / 3
    d["vwap"] = (tp * v).rolling(60).sum() / v.rolling(60).sum().replace(0, np.nan)

    sma_tp = tp.rolling(20).mean()
    mad = tp.rolling(20).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    d["cci"] = (tp - sma_tp) / (0.015 * mad.replace(0, np.nan))

    rmf = tp * v
    pos = rmf.where(tp > tp.shift(1), 0.0)
    neg = rmf.where(tp <= tp.shift(1), 0.0)
    ratio = pos.rolling(14).sum() / neg.rolling(14).sum().replace(0, np.nan)
    d["mfi"] = (100 - 100 / (1 + ratio)).fillna(50)

    mfm = ((c - l) - (h - c)) / (h - l).replace(0, np.nan)
    d["cmf"] = (mfm * v).rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan)

    vm_plus = (h - l.shift(1)).abs()
    vm_minus = (l - h.shift(1)).abs()
    tr_sum = tr.rolling(14).sum()
    d["vortex_plus"] = vm_plus.rolling(14).sum() / tr_sum.replace(0, np.nan)
    d["vortex_minus"] = vm_minus.rolling(14).sum() / tr_sum.replace(0, np.nan)

    # supertrend (10, 3)
    atr10 = tr.ewm(alpha=1 / 10, adjust=False).mean()
    hl2 = (h + l) / 2
    upper = (hl2 + 3 * atr10).to_numpy()
    lower = (hl2 - 3 * atr10).to_numpy()
    close_np = c.to_numpy()
    st_line = np.full(len(d), np.nan)
    st_dir = np.ones(len(d))
    up = True
    for i in range(len(d)):
        if np.isnan(atr10.iloc[i]):
            continue
        if i == 0 or np.isnan(st_line[i - 1]):
            st_line[i] = lower[i]
            continue
        if up:
            st_line[i] = max(lower[i], st_line[i - 1])
            if close_np[i] < st_line[i]:
                up = False
                st_line[i] = upper[i]
        else:
            st_line[i] = min(upper[i], st_line[i - 1])
            if close_np[i] > st_line[i]:
                up = True
                st_line[i] = lower[i]
        st_dir[i] = 1 if up else -1
    d["supertrend"] = st_line
    d["supertrend_dir"] = st_dir

    # ADX (Wilder, simplified)
    up_move = h.diff()
    down_move = -l.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr_s = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=d.index).ewm(alpha=1 / 14, adjust=False).mean() / atr_s.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=d.index).ewm(alpha=1 / 14, adjust=False).mean() / atr_s.replace(0, np.nan)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0)
    d["adx"] = dx.ewm(alpha=1 / 14, adjust=False).mean()
    d["plus_di"], d["minus_di"] = plus_di, minus_di
    return d


def _clamp(x: float) -> float:
    return float(max(-1.0, min(1.0, x))) if np.isfinite(x) else 0.0


def confluence(d: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """Per-bar confluence score (-100..100) + last-bar component table."""
    price = d["close"]
    atr = d["atr"].replace(0, np.nan)
    comps = {
        "روند EMA50": ((price - d["ema50"]) / atr * 0.6).apply(_clamp),
        "سوپرترند": d["supertrend_dir"].astype(float),
        "MACD": (d["macd_hist"] / atr * 1.2).apply(_clamp),
        "RSI": ((d["rsi"] - 50) / 50).apply(_clamp),
        "استوکاستیک": ((d["stoch_k"] - 50) / 50).apply(_clamp),
        "ورتکس": ((d["vortex_plus"] - d["vortex_minus"]) * 3).apply(_clamp),
        "جریان پول CMF": (d["cmf"] * 3).apply(_clamp),
        "CCI": (d["cci"] / 150).apply(_clamp),
        "MFI": ((d["mfi"] - 50) / 50).apply(_clamp),
    }
    weights = {"روند EMA50": 0.18, "سوپرترند": 0.14, "MACD": 0.16, "RSI": 0.13, "استوکاستیک": 0.09,
               "ورتکس": 0.10, "جریان پول CMF": 0.10, "CCI": 0.05, "MFI": 0.05}
    score = sum(comps[k].fillna(0) * w for k, w in weights.items()) * 100
    last = d.iloc[-1]
    raw = {
        "روند EMA50": "بالای EMA50" if price.iloc[-1] > last["ema50"] else "زیر EMA50",
        "سوپرترند": "صعودی" if last["supertrend_dir"] == 1 else "نزولی",
        "MACD": f"{last['macd_hist']:.4f}",
        "RSI": f"{last['rsi']:.1f}",
        "استوکاستیک": f"{last['stoch_k']:.1f}",
        "ورتکس": f"{last['vortex_plus']:.2f}/{last['vortex_minus']:.2f}",
        "جریان پول CMF": f"{last['cmf']:.3f}",
        "CCI": f"{last['cci']:.0f}",
        "MFI": f"{last['mfi']:.1f}",
    }
    table = pd.DataFrame([
        {"اندیکاتور": k, "مقدار": raw[k], "جهت": "خرید 🟢" if comps[k].iloc[-1] > 0.15 else "فروش 🔴" if comps[k].iloc[-1] < -0.15 else "خنثی ⚪",
         "امتیاز": round(float(comps[k].iloc[-1]), 2)}
        for k in comps
    ])
    return score.round().astype(float), table


def signal_events(d: pd.DataFrame, score: pd.Series) -> tuple[pd.DataFrame, dict]:
    """Entry/exit state machine on the confluence score (same thresholds as the main app)."""
    closes = d["close"].to_numpy()
    times = d["dt"].astype(str).to_numpy()
    events = []
    status, entry_price = "flat", None
    for i in range(60, len(d)):
        s = float(score.iloc[i])
        if status == "flat":
            if s >= ENTER:
                status, entry_price = "long", closes[i]
                events.append({"زمان": times[i], "رویداد": "ورود لانگ 🟢", "قیمت": closes[i], "امتیاز": s, "PnL%": None})
            elif s <= -ENTER:
                status, entry_price = "short", closes[i]
                events.append({"زمان": times[i], "رویداد": "ورود شورت 🔴", "قیمت": closes[i], "امتیاز": s, "PnL%": None})
        elif status == "long":
            if s <= -ENTER or s <= EXIT:
                pnl = (closes[i] - entry_price) / entry_price * 100
                events.append({"زمان": times[i], "رویداد": "خروج از لانگ ◆", "قیمت": closes[i], "امتیاز": s, "PnL%": round(pnl, 2)})
                status, entry_price = "flat", None
                if s <= -ENTER:
                    status, entry_price = "short", closes[i]
                    events.append({"زمان": times[i], "رویداد": "ورود شورت 🔴", "قیمت": closes[i], "امتیاز": s, "PnL%": None})
        else:  # short
            if s >= ENTER or s >= -EXIT:
                pnl = (entry_price - closes[i]) / entry_price * 100
                events.append({"زمان": times[i], "رویداد": "خروج از شورت ◆", "قیمت": closes[i], "امتیاز": s, "PnL%": round(pnl, 2)})
                status, entry_price = "flat", None
                if s >= ENTER:
                    status, entry_price = "long", closes[i]
                    events.append({"زمان": times[i], "رویداد": "ورود لانگ 🟢", "قیمت": closes[i], "امتیاز": s, "PnL%": None})
    live_pnl = None
    if status != "flat" and entry_price:
        live_pnl = (closes[-1] - entry_price) / entry_price * 100 * (1 if status == "long" else -1)
    state = {"status": status, "entry": entry_price, "live_pnl": None if live_pnl is None else round(float(live_pnl), 2)}
    return pd.DataFrame(events), state


def swing_levels(d: pd.DataFrame, k: int = 3) -> pd.DataFrame:
    """Clustered swing support/resistance levels."""
    highs, lows = d["high"].to_numpy(), d["low"].to_numpy()
    pivots: list[tuple[float, str]] = []
    for i in range(k, len(d) - k):
        if highs[i] == max(highs[i - k: i + k + 1]):
            pivots.append((float(highs[i]), "high"))
        if lows[i] == min(lows[i - k: i + k + 1]):
            pivots.append((float(lows[i]), "low"))
    price = float(d["close"].iloc[-1])
    atr = float(d["atr"].iloc[-1]) if np.isfinite(d["atr"].iloc[-1]) else price * 0.01
    tol = max(atr * 0.8, price * 0.002)
    pivots.sort(key=lambda x: x[0])
    groups: list[list[tuple[float, str]]] = []
    for p in pivots:
        if groups and abs(p[0] - float(np.mean([g[0] for g in groups[-1]]))) <= tol:
            groups[-1].append(p)
        else:
            groups.append([p])
    rows = []
    for g in groups:
        lvl = float(np.mean([x[0] for x in g]))
        rows.append({
            "سطح": lvl,
            "نوع": "مقاومت 🔴" if lvl > price else "حمایت 🟢",
            "برخورد": len(g),
            "قدرت%": min(100, len(g) * 20 + 15),
            "فاصله%": round((lvl - price) / price * 100, 2),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("قدرت%", ascending=False).head(10).sort_values("سطح", ascending=False).reset_index(drop=True)


def make_plan(d: pd.DataFrame, score: float, levels: pd.DataFrame) -> dict:
    price = float(d["close"].iloc[-1])
    atr = float(d["atr"].iloc[-1]) if np.isfinite(d["atr"].iloc[-1]) else price * 0.01
    direction = "long" if score >= 0 else "short"
    recent = d.tail(10)
    swing = float(recent["low"].min()) if direction == "long" else float(recent["high"].max())
    if direction == "long":
        stop = min(swing - atr * 0.3, price - atr)
        stop = max(stop, price - atr * 3)
    else:
        stop = max(swing + atr * 0.3, price + atr)
        stop = min(stop, price + atr * 3)
    entry = price
    risk = abs(entry - stop) or atr
    targets = []
    if not levels.empty:
        for _, row in levels.iterrows():
            lvl = float(row["سطح"])
            if direction == "long" and lvl > entry + risk * 1.15:
                targets.append((lvl, round((lvl - entry) / risk, 2)))
            if direction == "short" and lvl < entry - risk * 1.15:
                targets.append((lvl, round((entry - lvl) / risk, 2)))
    targets = sorted(targets, key=lambda x: x[1])[:2]
    if not targets or targets[-1][1] < 2:
        t2 = entry + risk * 2 if direction == "long" else entry - risk * 2
        targets.append((t2, 2.0))
    rr = targets[0][1] if targets else 0
    return {
        "direction": "لانگ (خرید) 🟢" if direction == "long" else "شورت (فروش) 🔴",
        "entry": entry, "stop": stop, "targets": targets, "rr": rr,
        "confidence": int(min(92, 35 + abs(score) * 0.4 + (10 if rr > 1.5 else 0))),
        "atr": atr,
    }


# ------------------------------------------------------------------ image extraction (lite)

def extract_candles_from_image(img: Image.Image, max_dim: int = 1400) -> pd.DataFrame:
    """Extract normalized candles (0..100) from a chart screenshot by candle colors."""
    im = img.convert("RGB")
    scale = min(1.0, max_dim / max(im.width, im.height))
    if scale < 1:
        im = im.resize((max(16, int(im.width * scale)), max(16, int(im.height * scale))))
    a = np.asarray(im).astype(int)
    h, w, _ = a.shape
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mx = a.max(axis=2)
    mn = a.min(axis=2)
    sat = mx - mn
    green = (g > 50) & (g - r > 22) & (g - b > -45)
    red = (r > 50) & (r - g > 22) & (r - b > 15)
    blue = (b > 75) & (b - r > 28) & (b - g > 14)
    mask = ((green | blue) | red) & (sat >= 15) & (mn <= 238)
    bull_mask = green | blue

    col_on = mask.any(axis=0)
    clusters: list[tuple[int, int]] = []
    x = 0
    while x < w:
        if col_on[x]:
            x0 = x
            while x < w and col_on[x]:
                x += 1
            clusters.append((x0, x - 1))
        else:
            x += 1
    clusters = [c for c in clusters if 1 <= c[1] - c[0] + 1 <= 40]
    if len(clusters) < 8:
        return pd.DataFrame()

    tops, bots = [], []
    raw = []
    for (x0, x1) in clusters:
        sub = mask[:, x0: x1 + 1]
        ys = np.where(sub.any(axis=1))[0]
        if len(ys) == 0:
            continue
        top, bot = int(ys.min()), int(ys.max())
        row_counts = sub.sum(axis=1)
        wide = np.where(row_counts >= max(1.0, row_counts.max() * 0.55))[0]
        b_top, b_bot = (int(wide.min()), int(wide.max())) if len(wide) else (top, bot)
        region = sub[top:bot + 1]
        bull_px = bull_mask[top:bot + 1, x0:x1 + 1].sum()
        red_px = (region & (~bull_mask[top:bot + 1, x0:x1 + 1])).sum()
        bull = bull_px >= red_px
        raw.append({"x": (x0 + x1) / 2 / w, "top": top, "bot": bot, "b_top": b_top, "b_bot": b_bot, "bull": bool(bull)})
        tops.append(top)
        bots.append(bot)
    if len(raw) < 8:
        return pd.DataFrame()
    span_top, span_bot = min(tops), max(bots)
    span = max(1, span_bot - span_top)

    def to_price(y: float) -> float:
        return (span_bot - y) / span * 100

    rows = []
    for c in raw:
        y_open = c["b_bot"] if c["bull"] else c["b_top"]
        y_close = c["b_top"] if c["bull"] else c["b_bot"]
        rows.append({
            "time": 0, "open": to_price(y_open), "close": to_price(y_close),
            "high": to_price(c["top"]), "low": to_price(c["bot"]),
            "volume": 0.0, "dt": pd.NaT, "x": c["x"],
        })
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ UI

def main() -> None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    st.set_page_config(page_title="NorthmanQuant — نسخه رایگان", page_icon="📈", layout="wide")
    st.markdown(
        "<div dir='rtl'><h1 style='margin-bottom:0'>📈 NorthmanQuant — نسخه‌ی رایگان (Lite)</h1>"
        "<p style='color:#888;margin-top:4px'>تحلیل زنده با داده‌ی عمومی صرافی‌ها — بدون ثبت‌نام و بدون کلید API. "
        "نسخه‌ی کامل (حساب، معامله، پنل مدیریت) روی سایت اصلی است.</p></div>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("⚙️ تنظیمات")
        symbol_in = st.text_input("نماد", value="BTC-USDT", help="مثل BTC-USDT یا gramusdt")
        exchange = st.selectbox("صرافی", ["KuCoin", "OKX", "Binance", "Bybit"])
        interval = st.selectbox("تایم‌فریم", list(INTERVAL_MINUTES.keys()), index=1)
        auto = st.checkbox("بروزرسانی خودکار (۶۰ ثانیه)", value=False)

    symbol = normalize_symbol(symbol_in)
    tab_live, tab_top, tab_news, tab_img = st.tabs(["📊 تحلیل زنده", "🏆 برترین‌ها", "📰 اخبار", "📷 تحلیل عکس"])

    with tab_live:
        try:
            df = fetch_candles(exchange, symbol, interval)
            d = add_indicators(df)
            score_series, comp_table = confluence(d)
            score = float(score_series.iloc[-1])
            levels = swing_levels(d)
            plan = make_plan(d, score, levels)
            events, state = signal_events(d, score_series)
            price = float(d["close"].iloc[-1])
            dec = 2 if price >= 1000 else 4 if price >= 1 else 6

            c1, c2, c3, c4 = st.columns(4)
            c1.metric(f"{symbol} · {exchange}", f"{price:,.{dec}f}")
            label = "خرید قوی" if score > 40 else "خرید" if score > 12 else "خنثی" if score > -12 else "فروش" if score > -40 else "فروش قوی"
            c2.metric("همگرایی اندیکاتورها", f"{score:+.0f} · {label}")
            c3.metric("ATR", f"{plan['atr']:,.{dec}f}")
            state_txt = "خارج از بازار" if state["status"] == "flat" else f"{'لانگ 🟢' if state['status'] == 'long' else 'شورت 🔴'} از {state['entry']:,.{dec}f} · PnL {state['live_pnl']}%"
            c4.metric("سیگنال همگرایی", state_txt)

            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22],
                                vertical_spacing=0.04, subplot_titles=(f"{symbol} · {interval}", "حجم"))
            fig.add_trace(go.Candlestick(x=d["dt"], open=d["open"], high=d["high"], low=d["low"], close=d["close"],
                                         increasing_line_color="#22c55e", decreasing_line_color="#ef4444", name="قیمت"), row=1, col=1)
            fig.add_trace(go.Scatter(x=d["dt"], y=d["ema20"], line=dict(color="#38bdf8", width=1.2), name="EMA20"), row=1, col=1)
            fig.add_trace(go.Scatter(x=d["dt"], y=d["ema50"], line=dict(color="#f472b6", width=1.2), name="EMA50"), row=1, col=1)
            fig.add_trace(go.Scatter(x=d["dt"], y=d["bb_up"], line=dict(color="#94a3b8", width=0.8, dash="dot"), name="BB↑"), row=1, col=1)
            fig.add_trace(go.Scatter(x=d["dt"], y=d["bb_lo"], line=dict(color="#94a3b8", width=0.8, dash="dot"), name="BB↓"), row=1, col=1)
            fig.add_hline(y=plan["entry"], line_color="#f59e0b", line_width=2, annotation_text="ورود", row=1, col=1)
            fig.add_hline(y=plan["stop"], line_color="#ef4444", line_dash="dash", annotation_text="حد ضرر", row=1, col=1)
            for i, (t_price, t_rr) in enumerate(plan["targets"]):
                fig.add_hline(y=t_price, line_color="#38bdf8", line_dash="dash",
                              annotation_text=f"هدف {i + 1} · {t_rr}R", row=1, col=1)
            colors = ["#22c55e" if c >= o else "#ef4444" for c, o in zip(d["close"], d["open"])]
            fig.add_trace(go.Bar(x=d["dt"], y=d["volume"], marker_color=colors, name="حجم"), row=2, col=1)
            fig.update_layout(height=560, xaxis_rangeslider_visible=False, template="plotly_dark",
                              legend=dict(orientation="h", y=1.02), margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)

            left, right = st.columns(2)
            with left:
                st.subheader("🎯 طرح معامله")
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("جهت", plan["direction"])
                p2.metric("ورود", f"{plan['entry']:,.{dec}f}")
                p3.metric("حد ضرر", f"{plan['stop']:,.{dec}f}")
                p4.metric("R:R / اطمینان", f"1:{plan['rr']} · {plan['confidence']}٪")
                for i, (t_price, t_rr) in enumerate(plan["targets"]):
                    st.write(f"هدف {i + 1}: **{t_price:,.{dec}f}** ({t_rr}R)")
                st.subheader("🌀 اجزای همگرایی")
                st.dataframe(comp_table, use_container_width=True, hide_index=True)
            with right:
                st.subheader("🧱 حمایت و مقاومت (سوئینگ)")
                if levels.empty:
                    st.info("سطح معناداری پیدا نشد.")
                else:
                    show = levels.copy()
                    show["سطح"] = show["سطح"].map(lambda v: f"{v:,.{dec}f}")
                    st.dataframe(show, use_container_width=True, hide_index=True)
                st.subheader("📜 رویدادهای ورود/خروج همگرایی")
                if events.empty:
                    st.info("در این بازه رویدادی ثبت نشده است.")
                else:
                    st.dataframe(events.tail(10).iloc[::-1], use_container_width=True, hide_index=True)
            st.line_chart(score_series.tail(120), height=140)
            st.caption("نمودار بالا: روند امتیاز همگرایی ۱۲۰ کندل اخیر. داده: API عمومی صرافی (کش ۶۰ ثانیه). این ابزار توصیه‌ی سرمایه‌گذاری نیست.")
        except Exception as e:  # noqa: BLE001
            st.error(f"خطا در دریافت/تحلیل داده: {e}")
            st.info("نماد را مثل BTC-USDT بنویس؛ اگر صرافی انتخابی در منطقه‌ات مسدود است، KuCoin را انتخاب کن.")

    with tab_top:
        try:
            tops = fetch_top_coins()
            g, l, v = st.columns(3)
            with g:
                st.subheader("🚀 بیشترین سود ۲۴س")
                st.dataframe(tops["gainers"], use_container_width=True, hide_index=True)
            with l:
                st.subheader("🩸 بیشترین ریزش ۲۴س")
                st.dataframe(tops["losers"], use_container_width=True, hide_index=True)
            with v:
                st.subheader("💧 بیشترین حجم")
                st.dataframe(tops["volume"], use_container_width=True, hide_index=True)
        except Exception as e:  # noqa: BLE001
            st.error(f"دریافت فهرست بازار ممکن نشد: {e}")

    with tab_news:
        try:
            news = fetch_news()
            if news.empty:
                st.info("خبری دریافت نشد.")
            else:
                for _, row in news.iterrows():
                    st.markdown(f"**[{row['title']}]({row['link']})**  \n{row['source']} · {row['sentiment']} · {row['date']}")
        except Exception as e:  # noqa: BLE001
            st.error(f"دریافت اخبار ممکن نشد: {e}")

    with tab_img:
        st.write("اسکرین‌شات چارت (روشن یا تیره) را آپلود کن؛ کندل‌ها از روی رنگ‌ها استخراج و سطوح روی مقیاس نسبی ۰ تا ۱۰۰ محاسبه می‌شوند.")
        up = st.file_uploader("آپلود عکس چارت", type=["png", "jpg", "jpeg", "webp"])
        if up is not None:
            img = Image.open(up)
            st.image(img, caption="عکس آپلودشده", use_container_width=True)
            try:
                cdf = extract_candles_from_image(img)
                if cdf.empty or len(cdf) < 10:
                    st.warning("کندل کافی پیدا نشد. عکس نزدیک‌تر و خواناتر (بدون برش کندل‌ها) امتحان کن.")
                else:
                    full = add_indicators(cdf.assign(volume=0.0, dt=pd.RangeIndex(len(cdf))))
                    lv = swing_levels(full.assign(atr=pd.Series([1.5] * len(full))))
                    st.success(f"{len(cdf)} کندل استخراج شد.")
                    st.dataframe(cdf[["open", "high", "low", "close"]].tail(15).round(2), use_container_width=True)
                    st.subheader("سطوح روی مقیاس نسبی تصویر (۰ تا ۱۰۰)")
                    st.dataframe(lv, use_container_width=True, hide_index=True)
                    st.caption("برای قیمت واقعی، سقف و کف قیمتِ دیده‌شده در عکس را در نسخه‌ی کامل سایت وارد کن (کالیبراسیون قیمت).")
            except Exception as e:  # noqa: BLE001
                st.error(f"پردازش عکس ممکن نشد: {e}")

    if auto:
        import time as _time
        _time.sleep(60)
        st.rerun()


if __name__ == "__main__":
    main()
