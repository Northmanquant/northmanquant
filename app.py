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


# ------------------------------------------------------------------ live layer

LIVE_CSS = """
<style>
@keyframes nq-pulse-dot { 0%{box-shadow:0 0 0 0 rgba(52,211,153,.55)} 70%{box-shadow:0 0 0 9px rgba(52,211,153,0)} 100%{box-shadow:0 0 0 0 rgba(52,211,153,0)} }
.nq-live-dot{width:10px;height:10px;border-radius:999px;background:#34d399;display:inline-block;animation:nq-pulse-dot 1.6s infinite}
@keyframes nq-scroll { from{transform:translateX(0)} to{transform:translateX(-50%)} }
.nq-marquee{overflow:hidden;border:1px solid rgba(148,163,184,.22);border-radius:12px;background:rgba(2,6,17,.55);padding:6px 0;direction:ltr}
.nq-marquee-track{display:inline-flex;gap:30px;white-space:nowrap;animation:nq-scroll 36s linear infinite;padding-left:30px}
.nq-marquee:hover .nq-marquee-track{animation-play-state:paused}
.nq-tick-item{font-family:ui-monospace,monospace;font-size:12px;color:#cbd5e1}
@keyframes nq-flash-up { 0%{background:rgba(16,185,129,.30)} 100%{background:transparent} }
@keyframes nq-flash-down { 0%{background:rgba(244,63,94,.30)} 100%{background:transparent} }
.nq-flash-up{animation:nq-flash-up 1.1s ease-out;border-radius:10px}
.nq-flash-down{animation:nq-flash-down 1.1s ease-out;border-radius:10px}
@keyframes nq-glow { 0%,100%{text-shadow:0 0 14px rgba(56,189,248,.35)} 50%{text-shadow:0 0 26px rgba(52,211,153,.55)} }
.nq-glow{animation:nq-glow 3.2s ease-in-out infinite}
.nq-live-strip{border:1px solid rgba(56,189,248,.28);border-radius:14px;padding:10px 14px;background:linear-gradient(120deg,rgba(14,116,233,.10),rgba(16,185,129,.07));margin:6px 0 10px}
</style>
"""


def fetch_tick(exchange: str, symbol: str) -> dict | None:
    """Latest price (+bid/ask) from the selected exchange. No caching — this is the live layer."""
    headers = {"User-Agent": "northmanquant-lite/1.0", "accept": "application/json"}
    try:
        if exchange == "Binance":
            r = requests.get(f"{BINANCE}/api/v3/ticker/bookTicker", params={"symbol": symbol.replace("-", "")}, headers=headers, timeout=6)
            j = r.json()
            bid, ask = float(j["bidPrice"]), float(j["askPrice"])
            return {"price": (bid + ask) / 2, "bid": bid, "ask": ask}
        if exchange == "Bybit":
            r = requests.get(f"{BYBIT}/v5/market/tickers", params={"category": "spot", "symbol": symbol.replace("-", "")}, headers=headers, timeout=6)
            row = ((r.json().get("result") or {}).get("list") or [{}])[0]
            return {"price": float(row["lastPrice"]), "bid": float(row.get("bid1Price") or 0), "ask": float(row.get("ask1Price") or 0)}
        if exchange == "OKX":
            r = requests.get(f"{OKX}/api/v5/market/ticker", params={"instId": symbol}, headers=headers, timeout=6)
            row = (r.json().get("data") or [{}])[0]
            return {"price": float(row["last"]), "bid": float(row.get("bidPx") or 0), "ask": float(row.get("askPx") or 0)}
        r = requests.get(f"{KUCOIN}/api/v1/market/orderbook/level1", params={"symbol": symbol}, headers=headers, timeout=6)
        data = r.json().get("data") or {}
        return {"price": float(data["price"]), "bid": float(data.get("bestBid") or 0), "ask": float(data.get("bestAsk") or 0)}
    except Exception:
        return None


def _annular_sector(cx: float, cy: float, r1: float, r2: float, a1: float, a2: float) -> str:
    import math as _m

    def pt(r: float, a: float) -> tuple[float, float]:
        return (cx + r * _m.cos(a), cy + r * _m.sin(a))

    x1, y1 = pt(r2, a1)
    x2, y2 = pt(r2, a2)
    x3, y3 = pt(r1, a2)
    x4, y4 = pt(r1, a1)
    large = 1 if (a2 - a1) > _m.pi else 0
    return (
        f"M {x1:.1f} {y1:.1f} A {r2} {r2} 0 {large} 1 {x2:.1f} {y2:.1f} "
        f"L {x3:.1f} {y3:.1f} A {r1} {r1} 0 {large} 0 {x4:.1f} {y4:.1f} Z"
    )


def build_galaxy_svg(comp_table: pd.DataFrame, score: float) -> str:
    """Animated rotating confluence galaxy (pure SVG + SMIL — no JS needed)."""
    import math as _m

    size, cx = 340, 170
    values: list[float] = []
    if comp_table is not None and not comp_table.empty and "امتیاز" in comp_table.columns:
        values = [float(v) for v in comp_table["امتیاز"].tolist()]
    if not values:
        values = [0.0] * 9
    n = len(values)
    seg = 2 * _m.pi / n
    wedges = []
    for i, v in enumerate(values):
        a1 = -_m.pi / 2 + i * seg + 0.03
        a2 = -_m.pi / 2 + (i + 1) * seg - 0.03
        color = "#10b981" if v > 0.12 else "#f43f5e" if v < -0.12 else "#64748b"
        alpha = 0.22 + min(0.78, abs(v)) * 0.85
        wedges.append(
            f'<path d="{_annular_sector(cx, cx, 96, 142, a1, a2)}" fill="{color}" fill-opacity="{alpha:.2f}" stroke="rgba(226,232,240,.25)" stroke-width="0.6"/>'
        )
        mid = (a1 + a2) / 2
        nx, ny = cx + 119 * _m.cos(mid), cx + 119 * _m.sin(mid)
        wedges.append(f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="3" fill="{color}"/>')

    dots = []
    for i in range(80):
        h1 = (np.sin(i * 127.1) * 43758.5453) % 1
        h2 = (np.sin(i * 311.7) * 12543.123) % 1
        ang = h1 * 2 * _m.pi
        ring = 26 + h2 * 62
        x = cx + ring * _m.cos(ang)
        y = cx + ring * _m.sin(ang) * 0.97
        dur = 1.6 + (i % 7) * 0.5
        dots.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{0.8 + h2 * 1.3:.1f}" fill="#7dd3fc">'
            f'<animate attributeName="opacity" values="0.12;0.95;0.12" dur="{dur:.1f}s" repeatCount="indefinite"/></circle>'
        )

    score_color = "#34d399" if score > 25 else "#fb7185" if score < -25 else "#fbbf24"
    return f"""
<div style="display:flex;justify-content:center">
<svg viewBox="0 0 {size} {size}" width="330" height="330" role="img" aria-label="confluence galaxy">
  <defs>
    <radialGradient id="nqcore" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="rgba(56,189,248,0.35)"/>
      <stop offset="60%" stop-color="rgba(30,64,175,0.15)"/>
      <stop offset="100%" stop-color="rgba(2,6,17,0)"/>
    </radialGradient>
  </defs>
  <circle cx="{cx}" cy="{cx}" r="160" fill="url(#nqcore)"/>
  <g>
    <animateTransform attributeName="transform" type="rotate" from="360 170 170" to="0 170 170" dur="70s" repeatCount="indefinite"/>
    {''.join(dots)}
  </g>
  <g>
    <animateTransform attributeName="transform" type="rotate" from="0 170 170" to="360 170 170" dur="48s" repeatCount="indefinite"/>
    {''.join(wedges)}
  </g>
  <circle cx="{cx}" cy="{cx}" r="88" fill="none" stroke="rgba(148,163,184,.28)"/>
  <circle cx="{cx}" cy="{cx}" r="70" fill="rgba(2,6,17,.72)" stroke="rgba(125,211,252,.4)"/>
  <text x="{cx}" y="{cx - 2}" text-anchor="middle" font-family="ui-monospace,monospace" font-weight="800" font-size="33" fill="{score_color}">{score:+.0f}</text>
  <text x="{cx}" y="{cx + 18}" text-anchor="middle" font-size="10.5" fill="#cbd5e1">همگرایی زنده</text>
</svg>
</div>
"""


def _html(html: str) -> None:
    """Render raw HTML reliably (st.html where available)."""
    try:
        st.html(html)
    except Exception:
        st.markdown(html, unsafe_allow_html=True)


def _live_strip_impl(symbol: str, exchange: str, interval: str, dec: int) -> None:
    import time as _t

    tick = fetch_tick(exchange, symbol)
    state = st.session_state.get("nq_state") or {}
    score = st.session_state.get("nq_score")
    prev = st.session_state.get("nq_last_price")
    price = tick["price"] if tick else None
    flash = ""
    arrow = ""
    if price is not None and prev:
        if price > prev:
            flash, arrow = "nq-flash-up", "▲"
        elif price < prev:
            flash, arrow = "nq-flash-down", "▼"
    if price is not None:
        st.session_state["nq_last_price"] = price

    minutes = INTERVAL_MINUTES.get(interval, 60)
    left = minutes * 60 - (int(_t.time()) % (minutes * 60))
    progress = int((1 - left / (minutes * 60)) * 100)
    countdown = f"{left // 60:02d}:{left % 60:02d}"

    pnl_html = ""
    if state.get("status") in ("long", "short") and state.get("entry") and price:
        entry = float(state["entry"])
        pnl = (price - entry) / entry * 100 * (1 if state["status"] == "long" else -1)
        chip_color = "#34d399" if state["status"] == "long" else "#fb7185"
        pnl_color = "#34d399" if pnl >= 0 else "#fb7185"
        pnl_html = (
            f"<span style='border:1px solid {chip_color};color:{chip_color};border-radius:999px;"
            f"padding:3px 10px;font-size:12px'>{'🟢 لانگ' if state['status'] == 'long' else '🔴 شورت'} از {entry:,.{dec}f} · "
            f"<b style='color:{pnl_color}'>{pnl:+.2f}%</b></span>"
        )
    elif state:
        pnl_html = "<span style='color:#94a3b8;font-size:12px'>خارج از بازار — در انتظار همگرایی ±۴۰</span>"

    price_txt = f"{price:,.{dec}f}" if price else "—"
    bid_ask = ""
    if tick and tick.get("bid"):
        bid_ask = (
            f"<span style='color:#64748b;font-size:11px;font-family:ui-monospace,monospace'>"
            f"Bid <b style='color:#34d399'>{tick['bid']:,.{dec}f}</b> · Ask <b style='color:#fb7185'>{tick['ask']:,.{dec}f}</b></span>"
        )
    score_txt = f"{score:+.0f}" if isinstance(score, (int, float)) else "—"

    _html(
        f"""
<div class="nq-live-strip {flash}" dir="rtl">
  <div style="display:flex;flex-wrap:wrap;align-items:center;gap:14px">
    <span style="display:flex;align-items:center;gap:7px;font-size:11px;color:#a5f3fc;font-weight:700">
      <span class="nq-live-dot"></span> LIVE · زنده
    </span>
    <span class="nq-glow" style="font-family:ui-monospace,monospace;font-size:26px;font-weight:800;color:#f8fafc">{price_txt} <span style="font-size:14px">{arrow}</span></span>
    {bid_ask}
    <span style="font-family:ui-monospace,monospace;font-size:12px;color:#e2e8f0">امتیاز همگرایی <b>{score_txt}</b></span>
    {pnl_html}
    <span style="margin-inline-start:auto;text-align:center">
      <span style="display:block;font-family:ui-monospace,monospace;font-size:13px;color:#e2e8f0">⏳ {countdown}</span>
      <span style="display:block;width:110px;height:5px;border-radius:99px;background:rgba(148,163,184,.25);overflow:hidden;margin-top:3px">
        <span style="display:block;height:100%;width:{progress}%;background:linear-gradient(90deg,#38bdf8,#34d399)"></span>
      </span>
      <span style="font-size:9px;color:#64748b">تا بستن کندل</span>
    </span>
  </div>
</div>
"""
    )


try:
    live_strip_auto = st.fragment(run_every=5)(_live_strip_impl)
    live_strip_manual = st.fragment(_live_strip_impl)
except Exception:  # older Streamlit without fragment auto-rerun
    live_strip_auto = _live_strip_impl  # type: ignore
    live_strip_manual = _live_strip_impl  # type: ignore



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



def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def _wma(s: pd.Series, n: int) -> pd.Series:
    w = np.arange(1, n + 1, dtype=float)
    return s.rolling(n).apply(lambda x: float(np.dot(x, w) / w.sum()), raw=True)


def add_more(d: pd.DataFrame) -> pd.DataFrame:
    c, h, l, v = d["close"], d["high"], d["low"], d["volume"]
    d["ema9"] = _ema(c, 9)
    d["ema21"] = _ema(c, 21)
    r = d["rsi"]
    ll = r.rolling(14).min()
    hh = r.rolling(14).max()
    d["stoch_rsi"] = ((r - ll) / (hh - ll).replace(0, np.nan) * 100).fillna(50)
    median = (h + l) / 2
    d["ao"] = median.rolling(5).mean() - median.rolling(34).mean()
    d["mom10"] = c - c.shift(10)
    hh14 = h.rolling(14).max()
    ll14 = l.rolling(14).min()
    d["willr"] = ((hh14 - c) / (hh14 - ll14).replace(0, np.nan) * -100).fillna(-50)
    ema13 = _ema(c, 13)
    d["bull_power"] = h - ema13
    d["bear_power"] = l - ema13
    prev_c = c.shift(1)
    bp = c - pd.concat([l, prev_c], axis=1).min(axis=1)
    tr2 = pd.concat([h, prev_c], axis=1).max(axis=1) - pd.concat([l, prev_c], axis=1).min(axis=1)

    def _avg(n: int) -> pd.Series:
        return bp.rolling(n).sum() / tr2.rolling(n).sum().replace(0, np.nan)

    d["uo"] = ((4 * _avg(7) + 2 * _avg(14) + _avg(28)) / 7 * 100).fillna(50)
    d["dc_up"] = h.rolling(20).max()
    d["dc_lo"] = l.rolling(20).min()
    d["vwma20"] = (c * v).rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan)

    def _mid(n: int) -> pd.Series:
        return (h.rolling(n).max() + l.rolling(n).min()) / 2

    d["tenkan"] = _mid(9)
    d["kijun"] = _mid(26)
    half = _wma(c, 5)
    full = _wma(c, 9)
    d["hull"] = _wma(2 * half - full, 3)
    return d


def _sig(v: float, buy_at: float = 0.15, sell_at: float = -0.15) -> str:
    return "خرید 🟢" if v > buy_at else "فروش 🔴" if v < sell_at else "خنثی ⚪"


def oscillator_table(d: pd.DataFrame) -> pd.DataFrame:
    last = d.iloc[-1]
    price = float(last["close"])
    rows = [
        ("RSI (14)", f"{last['rsi']:.2f}", "خرید 🟢" if last["rsi"] < 30 else "فروش 🔴" if last["rsi"] > 70 else "خنثی ⚪"),
        ("MACD", f"{last['macd_hist']:.4f}", "خرید 🟢" if last["macd"] > last["macd_signal"] else "فروش 🔴"),
        ("استوکاستیک", f"{last['stoch_k']:.1f}", "خرید 🟢" if last["stoch_k"] < 20 and last["stoch_k"] > last["stoch_d"] else "فروش 🔴" if last["stoch_k"] > 80 and last["stoch_k"] < last["stoch_d"] else "خنثی ⚪"),
        ("استوکاستیک RSI", f"{last['stoch_rsi']:.1f}", "خرید 🟢" if last["stoch_rsi"] < 20 else "فروش 🔴" if last["stoch_rsi"] > 80 else "خنثی ⚪"),
        ("CCI (20)", f"{last['cci']:.0f}", "خرید 🟢" if last["cci"] < -100 else "فروش 🔴" if last["cci"] > 100 else "خنثی ⚪"),
        ("ADX (14)", f"{last['adx']:.1f}", ("خرید 🟢" if last["plus_di"] > last["minus_di"] else "فروش 🔴") if last["adx"] > 25 else "خنثی ⚪"),
        ("Awesome (AO)", f"{last['ao']:.3f}", "خرید 🟢" if last["ao"] > 0 else "فروش 🔴"),
        ("مومنتوم (10)", f"{last['mom10']:.3f}", "خرید 🟢" if last["mom10"] > 0 else "فروش 🔴"),
        ("ویلیامز %R", f"{last['willr']:.1f}", "خرید 🟢" if last["willr"] < -80 else "فروش 🔴" if last["willr"] > -20 else "خنثی ⚪"),
        ("قدرت خریدار/فروشنده", f"{last['bull_power']:.3f}/{last['bear_power']:.3f}", "خرید 🟢" if last["bull_power"] > 0 and last["bear_power"] < 0 else "فروش 🔴" if last["bull_power"] < 0 and last["bear_power"] > 0 else "خنثی ⚪"),
        ("اسیلاتور نهایی UO", f"{last['uo']:.1f}", "خرید 🟢" if last["uo"] > 60 else "فروش 🔴" if last["uo"] < 30 else "خنثی ⚪"),
        ("MFI (14)", f"{last['mfi']:.1f}", "خرید 🟢" if last["mfi"] < 20 else "فروش 🔴" if last["mfi"] > 80 else "خنثی ⚪"),
        ("سوپرترند", f"{last['supertrend']:.4f}", "خرید 🟢" if last["supertrend_dir"] == 1 else "فروش 🔴"),
        ("VWAP (60)", f"{last['vwap']:.4f}", "خرید 🟢" if price > last["vwap"] else "فروش 🔴"),
        ("ورتکس Vortex", f"{last['vortex_plus']:.2f}/{last['vortex_minus']:.2f}", "خرید 🟢" if last["vortex_plus"] > last["vortex_minus"] else "فروش 🔴"),
        ("جریان پول CMF", f"{last['cmf']:.3f}", "خرید 🟢" if last["cmf"] > 0.05 else "فروش 🔴" if last["cmf"] < -0.05 else "خنثی ⚪"),
    ]
    return pd.DataFrame(rows, columns=["اندیکاتور", "مقدار", "سیگنال"])


def ma_table(d: pd.DataFrame) -> pd.DataFrame:
    c = d["close"]
    price = float(c.iloc[-1])
    defs = [
        ("EMA 9", _ema(c, 9)), ("SMA 10", _sma(c, 10)), ("EMA 20", _ema(c, 20)), ("SMA 20", _sma(c, 20)),
        ("EMA 30", _ema(c, 30)), ("SMA 30", _sma(c, 30)), ("EMA 50", _ema(c, 50)), ("SMA 50", _sma(c, 50)),
        ("EMA 100", _ema(c, 100)), ("SMA 100", _sma(c, 100)), ("EMA 200", _ema(c, 200)), ("SMA 200", _sma(c, 200)),
        ("HullMA 9", d["hull"]), ("VWMA 20", d["vwma20"]), ("ایچیموکو Kijun", d["kijun"]),
    ]
    rows = []
    for name, series in defs:
        period = int(re.search(r"\d+", name).group()) if re.search(r"\d+", name) else 20
        if len(d) < period + 5:
            continue
        val = float(series.iloc[-1])
        if not np.isfinite(val):
            continue
        rows.append({
            "میانگین": name,
            "مقدار": round(val, 6),
            "فاصله قیمت %": round((price - val) / val * 100, 2),
            "سیگنال": "خرید 🟢" if price > val else "فروش 🔴",
        })
    return pd.DataFrame(rows)


def pivot_points(prev: pd.Series) -> dict[str, dict[str, float]]:
    h, l, c = float(prev["high"]), float(prev["low"]), float(prev["close"])
    rng = h - l
    p = (h + l + c) / 3
    return {
        "کلاسیک": {"R3": h + 2 * (p - l), "R2": p + rng, "R1": 2 * p - l, "P": p, "S1": 2 * p - h, "S2": p - rng, "S3": l - 2 * (h - p)},
        "فیبوناچی": {"R3": p + rng, "R2": p + rng * 0.618, "R1": p + rng * 0.382, "P": p, "S1": p - rng * 0.382, "S2": p - rng * 0.618, "S3": p - rng},
        "کاماریلا": {"R3": c + rng * 1.1 / 4, "R2": c + rng * 1.1 / 6, "R1": c + rng * 1.1 / 12, "P": p, "S1": c - rng * 1.1 / 12, "S2": c - rng * 1.1 / 6, "S3": c - rng * 1.1 / 4},
    }


def fib_retracement(d: pd.DataFrame, lookback: int = 150) -> pd.DataFrame:
    seg = d.tail(min(lookback, len(d)))
    hi_i = int(seg["high"].idxmax())
    lo_i = int(seg["low"].idxmin())
    hi = float(seg.loc[hi_i, "high"])
    lo = float(seg.loc[lo_i, "low"])
    price = float(d["close"].iloc[-1])
    up = hi_i > lo_i  # last extreme is the high -> retracement downwards from high
    rows = []
    for r in [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]:
        lvl = hi - (hi - lo) * r if up else lo + (hi - lo) * r
        rows.append({"سطح فیبو": f"{r * 100:.1f}%", "قیمت": round(lvl, 6), "فاصله %": round((lvl - price) / price * 100, 2)})
    return pd.DataFrame(rows)


def volume_profile(d: pd.DataFrame, buckets: int = 24) -> tuple[pd.DataFrame, float, float, float]:
    seg = d.tail(min(250, len(d)))
    hi = float(seg["high"].max())
    lo = float(seg["low"].min())
    step = (hi - lo) / buckets or 1.0
    buy = np.zeros(buckets)
    sell = np.zeros(buckets)
    for _, b in seg.iterrows():
        i0 = int(max(0, min(buckets - 1, (float(b["low"]) - lo) // step)))
        i1 = int(max(0, min(buckets - 1, (float(b["high"]) - lo) // step)))
        per = float(b["volume"]) / (i1 - i0 + 1)
        target = buy if float(b["close"]) >= float(b["open"]) else sell
        for i in range(i0, i1 + 1):
            target[i] += per
    total = buy + sell
    prices = lo + step * (np.arange(buckets) + 0.5)
    poc = float(prices[int(np.argmax(total))]) if len(total) else lo
    order = np.argsort(-total)
    chosen: list[int] = []
    acc = 0.0
    total_vol = float(total.sum()) or 1.0
    for idx in order:
        chosen.append(int(idx))
        acc += float(total[idx])
        if acc >= total_vol * 0.7:
            break
    vah = float(prices[max(chosen)]) if chosen else hi
    val = float(prices[min(chosen)]) if chosen else lo
    df = pd.DataFrame({"price": prices, "buy": buy, "sell": sell, "total": total})
    return df, poc, vah, val


def candle_patterns(d: pd.DataFrame) -> list[dict]:
    out: list[dict] = []
    if len(d) < 5:
        return out
    bodies = (d["close"] - d["open"]).abs()
    ref = float(bodies.tail(30).mean()) or 1e-9
    for i in range(max(1, len(d) - 5), len(d)):
        b, p = d.iloc[i], d.iloc[i - 1]
        body = abs(float(b["close"] - b["open"]))
        rng = max(float(b["high"] - b["low"]), 1e-9)
        upper = float(b["high"]) - max(float(b["close"]), float(b["open"]))
        lower = min(float(b["close"]), float(b["open"])) - float(b["low"])
        bull = float(b["close"]) >= float(b["open"])
        when = str(b["dt"])
        if body / rng < 0.1:
            out.append({"الگو": "دوجی (Doji)", "جهت": "خنثی ⚪", "زمان": when})
        if lower > body * 2 and upper < body * 0.6 and body > ref * 0.3:
            out.append({"الگو": "چکش (Hammer)", "جهت": "صعودی 🟢", "زمان": when})
        if upper > body * 2 and lower < body * 0.6 and body > ref * 0.3:
            out.append({"الگو": "شوتینگ استار", "جهت": "نزولی 🔴", "زمان": when})
        p_body = abs(float(p["close"] - p["open"]))
        if bull != (float(p["close"]) >= float(p["open"])) and body > p_body * 1.1 \
                and max(float(b["close"]), float(b["open"])) >= max(float(p["close"]), float(p["open"])) \
                and min(float(b["close"]), float(b["open"])) <= min(float(p["close"]), float(p["open"])):
            out.append({"الگو": "پوشای صعودی" if bull else "پوشای نزولی", "جهت": "صعودی 🟢" if bull else "نزولی 🔴", "زمان": when})
    return out[-6:]


def divergence_list(d: pd.DataFrame) -> list[dict]:
    out: list[dict] = []
    seg = d.tail(min(70, len(d))).reset_index(drop=True)
    if len(seg) < 20:
        return out
    k = 2
    highs, lows = [], []
    for i in range(k, len(seg) - k):
        if seg["high"].iloc[i] == seg["high"].iloc[i - k: i + k + 1].max():
            highs.append(i)
        if seg["low"].iloc[i] == seg["low"].iloc[i - k: i + k + 1].min():
            lows.append(i)

    def _check(idxs: list[int], col: str, name: str, mode: str) -> None:
        if len(idxs) < 2:
            return
        a, b = idxs[-2], idxs[-1]
        if b - a < 4:
            return
        pa, pb = (float(seg["high"].iloc[a]), float(seg["high"].iloc[b])) if mode == "high" else (float(seg["low"].iloc[a]), float(seg["low"].iloc[b]))
        va, vb = float(seg[col].iloc[a]), float(seg[col].iloc[b])
        if mode == "high" and pb > pa and vb < va:
            out.append({"واگرایی": f"نزولی 🔴 {name}", "توضیح": f"قیمت سقف بالاتر ولی {name} پایین‌تر ({vb:.2f} < {va:.2f})"})
        if mode == "low" and pb < pa and vb > va:
            out.append({"واگرایی": f"صعودی 🟢 {name}", "توضیح": f"قیمت کف پایین‌تر ولی {name} بالاتر ({vb:.2f} > {va:.2f})"})

    _check(highs, "rsi", "RSI", "high")
    _check(lows, "rsi", "RSI", "low")
    _check(highs, "macd_hist", "MACD", "high")
    _check(lows, "macd_hist", "MACD", "low")
    return out[:4]


def _backtest(closes: np.ndarray, desired: np.ndarray) -> dict:
    fee = 0.0006
    eq, peak, maxdd = 1.0, 1.0, 0.0
    pos, entry = 0, 0.0
    wins = losses = 0
    gw = gl = 0.0
    trades = 0
    equity: list[float] = []
    n = len(closes)
    for i in range(n - 1):
        want = int(desired[i]) if np.isfinite(desired[i]) else 0
        if want != pos:
            if pos != 0 and entry > 0:
                ret = pos * (closes[i] - entry) / entry - fee
                trades += 1
                if ret > 0:
                    wins += 1
                    gw += ret
                else:
                    losses += 1
                    gl += abs(ret)
            if want != 0:
                entry = closes[i]
            pos = want
        if pos != 0:
            eq *= 1 + pos * (closes[i + 1] - closes[i]) / closes[i]
        peak = max(peak, eq)
        maxdd = max(maxdd, (peak - eq) / peak)
        if i % 6 == 0 or i == n - 2:
            equity.append(round((eq - 1) * 100, 3))
    if pos != 0 and entry > 0:
        ret = pos * (closes[-1] - entry) / entry - fee
        trades += 1
        if ret > 0:
            wins += 1
            gw += ret
        else:
            gl += abs(ret)
    final = int(desired[-1]) if np.isfinite(desired[-1]) else 0
    return {
        "pnl": round((eq - 1) * 100, 2),
        "winrate": int(round(wins / trades * 100)) if trades else 0,
        "trades": trades,
        "pf": round(gw / gl, 2) if gl > 0 else (9.99 if gw > 0 else 0.0),
        "maxdd": round(maxdd * 100, 2),
        "equity": equity[-90:],
        "signal": final,
    }


def run_agents(d: pd.DataFrame) -> tuple[pd.DataFrame, list[float], int, dict[str, list[float]]]:
    c = d["close"].to_numpy(dtype=float)
    n = len(c)
    warm = 60
    zero = np.zeros(n)

    def gate(mask: np.ndarray) -> np.ndarray:
        out = mask.astype(float).copy()
        out[:warm] = 0
        return out

    trend = gate(np.where((d["ema9"] > d["ema21"]) & (d["adx"] >= 16), 1, np.where((d["ema9"] < d["ema21"]) & (d["adx"] >= 16), -1, 0)))
    momentum_s = gate(np.where((d["macd_hist"] > 0) & (d["rsi"] > 52), 1, np.where((d["macd_hist"] < 0) & (d["rsi"] < 48), -1, 0)))

    mr = zero.copy()
    state = 0
    for i in range(n):
        if i < warm:
            continue
        if state == 0:
            if c[i] < d["bb_lo"].iloc[i] and d["rsi"].iloc[i] < 35:
                state = 1
            elif c[i] > d["bb_up"].iloc[i] and d["rsi"].iloc[i] > 65:
                state = -1
        elif state == 1 and c[i] > d["bb_mid"].iloc[i]:
            state = 0
        elif state == -1 and c[i] < d["bb_mid"].iloc[i]:
            state = 0
        mr[i] = state

    brk = zero.copy()
    state = 0
    dc_up = d["dc_up"].shift(1).to_numpy()
    dc_lo = d["dc_lo"].shift(1).to_numpy()
    for i in range(n):
        if i < warm or not np.isfinite(dc_up[i]):
            continue
        mid = (dc_up[i] + dc_lo[i]) / 2
        if state == 0:
            if c[i] > dc_up[i]:
                state = 1
            elif c[i] < dc_lo[i]:
                state = -1
        elif state == 1 and c[i] < mid:
            state = 0
        elif state == -1 and c[i] > mid:
            state = 0
        brk[i] = state

    st_dir = gate(d["supertrend_dir"].to_numpy(dtype=float))
    flow = gate(np.where((d["cmf"] > 0.04) & (d["close"] > d["vwap"]), 1, np.where((d["cmf"] < -0.04) & (d["close"] < d["vwap"]), -1, 0)))

    defs = [
        ("سوار روند (EMA+ADX)", trend),
        ("مومنتوم (MACD+RSI)", momentum_s),
        ("بازگشت به میانگین (بولینگر)", mr),
        ("شکست کانال (دانشین)", brk),
        ("سوپرترند", st_dir),
        ("جریان پول (CMF+VWAP)", flow),
    ]
    rows = []
    curves: dict[str, list[float]] = {}
    finals = []
    for name, desired in defs:
        r = _backtest(c, np.nan_to_num(desired))
        curves[name] = r["equity"]
        finals.append(r["signal"])
        rows.append({
            "ایجنت": name,
            "سود بک‌تست %": r["pnl"],
            "وین‌ریت %": r["winrate"],
            "معاملات": r["trades"],
            "PF": r["pf"],
            "حداکثر افت %": r["maxdd"],
            "سیگنال الان": "لانگ 🟢" if r["signal"] == 1 else "شورت 🔴" if r["signal"] == -1 else "خارج ⚪",
        })
    maxlen = max((len(v) for v in curves.values()), default=0)
    combined = []
    for i in range(maxlen):
        vals = [v[min(i, len(v) - 1)] for v in curves.values() if v]
        combined.append(round(float(np.mean(vals)), 3) if vals else 0.0)
    consensus = int(round(float(np.mean(finals)) * 100)) if finals else 0
    return pd.DataFrame(rows), combined, consensus, curves


def edge_data(d: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, float, float]:
    closes = d["close"].to_numpy(dtype=float)
    xs, ys = [], []
    for i in range(60, len(d) - 5, 2):
        comp = (
            _clamp((float(d["rsi"].iloc[i]) - 50) / 50) * 0.4
            + _clamp((float(d["stoch_k"].iloc[i]) - 50) / 50) * 0.3
            + _clamp(float(d["cci"].iloc[i]) / 200) * 0.3
        )
        xs.append(comp)
        ys.append((closes[i + 5] - closes[i]) / closes[i] * 100)
    x = np.array(xs)
    y = np.array(ys)
    if len(x) < 10:
        return x, y, 0.0, 0.0
    slope, intercept = np.polyfit(x, y, 1)
    corr = float(np.corrcoef(x, y)[0, 1]) if np.std(x) > 0 and np.std(y) > 0 else 0.0
    return x, y, float(slope), corr


@st.cache_data(ttl=180, show_spinner=False)
def fetch_fundamentals(base: str) -> dict | None:
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250, "page": 1,
                    "price_change_percentage": "7d,30d"},
            headers={"User-Agent": "northmanquant-lite/1.0", "accept": "application/json"},
            timeout=20,
        )
        r.raise_for_status()
        for coin in r.json():
            if str(coin.get("symbol", "")).upper() == base.upper():
                return coin
    except Exception:
        return None
    return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_fear_greed() -> dict | None:
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=12, headers={"User-Agent": "northmanquant-lite/1.0"})
        row = (r.json().get("data") or [{}])[0]
        return {"value": int(row.get("value", 0)), "label": row.get("value_classification", "")}
    except Exception:
        return None


@st.cache_data(ttl=90, show_spinner=False)
def fetch_breadth() -> dict:
    r = requests.get(f"{KUCOIN}/api/v1/market/allTickers", timeout=25, headers={"User-Agent": "northmanquant-lite/1.0"})
    r.raise_for_status()
    tickers = (r.json().get("data") or {}).get("ticker") or []
    rows = [t for t in tickers if str(t.get("symbol", "")).endswith("-USDT") and float(t.get("volValue") or 0) >= 200_000]
    total_turnover = sum(float(t.get("volValue") or 0) for t in tickers)
    btc = next((t for t in tickers if t.get("symbol") == "BTC-USDT"), None)
    changes = sorted(float(t.get("changeRate") or 0) * 100 for t in rows)
    return {
        "gainers": sum(1 for t in rows if float(t.get("changeRate") or 0) > 0.0005),
        "losers": sum(1 for t in rows if float(t.get("changeRate") or 0) < -0.0005),
        "total": len(rows),
        "turnover": total_turnover,
        "btc_share": (float(btc.get("volValue") or 0) / total_turnover * 100) if btc and total_turnover else 0.0,
        "median_change": changes[len(changes) // 2] if changes else 0.0,
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
        live_on = st.checkbox("🔴 حالت زنده (قیمت هر ۵ ثانیه)", value=True)
        auto = st.checkbox("بازخوانی کامل خودکار (۶۰ ثانیه)", value=False)

    symbol = normalize_symbol(symbol_in)
    st.markdown(LIVE_CSS, unsafe_allow_html=True)
    try:
        _tops = fetch_top_coins(500_000, 14)
        _strip = pd.concat([_tops["volume"].head(7), _tops["gainers"].head(7)]).drop_duplicates(subset="symbol")
        if not _strip.empty:
            _items = "".join(
                f"<span class='nq-tick-item'><b>{r['symbol'].replace('-USDT', '')}</b> {r['price']:,.4g} "
                f"<span style='color:{'#34d399' if r['change%'] >= 0 else '#fb7185'}'>{'▲' if r['change%'] >= 0 else '▼'} {abs(r['change%']):.2f}%</span></span>"
                for _, r in _strip.iterrows()
            )
            st.markdown(
                f"<div class='nq-marquee'><div class='nq-marquee-track'>{_items}{_items}</div></div>",
                unsafe_allow_html=True,
            )
    except Exception:
        pass

    tab_live, tab_top, tab_news, tab_img = st.tabs(["📊 تحلیل زنده", "🏆 برترین‌ها", "📰 اخبار", "📷 تحلیل عکس"])

    with tab_live:
        try:
            df = fetch_candles(exchange, symbol, interval)
            d = add_more(add_indicators(df))
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

            st.session_state["nq_state"] = state
            st.session_state["nq_score"] = score
            if live_on:
                live_strip_auto(symbol, exchange, interval, dec)
            else:
                live_strip_manual(symbol, exchange, interval, dec)

            st.markdown("**🧭 هم‌جهتی تایم‌فریم‌ها (MTF)**")
            mtf_cols = st.columns(4)
            for _col, _tf in zip(mtf_cols, ["15min", "1hour", "4hour", "1day"]):
                try:
                    _md = add_more(add_indicators(fetch_candles(exchange, symbol, _tf, 320)))
                    _ms, _ = confluence(_md)
                    _mv = float(_ms.iloc[-1])
                    _col.metric(_tf, f"{_mv:+.0f}", delta="خرید" if _mv > 12 else "فروش" if _mv < -12 else "خنثی")
                except Exception:
                    _col.metric(_tf, "—")

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

            sub_plan, sub_ind, sub_agents, sub_funda = st.tabs(
                ["🎯 طرح و سطوح", "🧭 اندیکاتورها", "🤖 ایجنت‌ها و Edge", "💰 فاندامنتال"]
            )
            with sub_plan:
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
                    st.subheader("🌀 کهکشان همگرایی (چرخان)")
                    _html(build_galaxy_svg(comp_table, score))
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
                        ev_show = events.tail(10).iloc[::-1].copy()
                        ev_show["PnL%"] = ev_show["PnL%"].apply(lambda v: "—" if v is None or (isinstance(v, float) and np.isnan(v)) else v)
                        st.dataframe(ev_show, use_container_width=True, hide_index=True)

                st.subheader("⚓ پیوت‌ها (بر اساس کندل قبلی)")
                piv = pivot_points(d.iloc[-2])
                pv_cols = st.columns(3)
                for _col, (_name, _vals) in zip(pv_cols, piv.items()):
                    with _col:
                        st.markdown(f"**پیوت {_name}**")
                        _pdf = pd.DataFrame(
                            [{"سطح": k, "قیمت": round(v, dec)} for k, v in _vals.items()]
                        )
                        st.dataframe(_pdf, use_container_width=True, hide_index=True)

                fb_col, vp_col = st.columns(2)
                with fb_col:
                    st.subheader("🌀 فیبوناچی اصلاحی (۱۵۰ کندل)")
                    st.dataframe(fib_retracement(d), use_container_width=True, hide_index=True)
                with vp_col:
                    st.subheader("📊 پروفایل حجم (POC)")
                    try:
                        _vp, _poc, _vah, _val = volume_profile(d)
                        vm1, vm2, vm3 = st.columns(3)
                        vm1.metric("POC", f"{_poc:,.{dec}f}")
                        vm2.metric("VAH", f"{_vah:,.{dec}f}")
                        vm3.metric("VAL", f"{_val:,.{dec}f}")
                        _vfig = go.Figure()
                        _vfig.add_trace(go.Bar(y=_vp["price"], x=_vp["buy"], orientation="h", marker_color="#22c55e", name="خرید"))
                        _vfig.add_trace(go.Bar(y=_vp["price"], x=-_vp["sell"], orientation="h", marker_color="#f43f5e", name="فروش"))
                        _vfig.add_hline(y=_poc, line_color="#f59e0b", line_width=2)
                        _vfig.update_layout(height=280, barmode="relative", template="plotly_dark",
                                            margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.08))
                        st.plotly_chart(_vfig, use_container_width=True)
                    except Exception:
                        st.info("پروفایل حجم قابل محاسبه نیست.")

                st.subheader("📈 روند امتیاز همگرایی")
                _tail_n = min(120, len(score_series))
                _sfig = go.Figure()
                _sfig.add_trace(go.Scatter(x=d["dt"].tail(_tail_n), y=score_series.tail(_tail_n),
                                           line=dict(color="#38bdf8", width=1.6), name="امتیاز همگرایی"))
                _sfig.add_hline(y=40, line_color="#22c55e", line_dash="dot")
                _sfig.add_hline(y=-10, line_color="#f59e0b", line_dash="dot")
                _sfig.add_hline(y=-40, line_color="#ef4444", line_dash="dot")
                _sfig.update_layout(height=190, template="plotly_dark", yaxis=dict(range=[-100, 100]),
                                    margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
                st.plotly_chart(_sfig, use_container_width=True)
                st.caption("داده: API عمومی صرافی (کش ۶۰ ثانیه). این ابزار توصیه‌ی سرمایه‌گذاری نیست.")

            with sub_ind:
                osc_df = oscillator_table(d)
                ma_df = ma_table(d)
                _buy = int((osc_df["سیگنال"].str.contains("خرید") | ma_df["سیگنال"].str.contains("خرید")).sum()) if not ma_df.empty else int(osc_df["سیگنال"].str.contains("خرید").sum())
                _sell = int((osc_df["سیگنال"].str.contains("فروش") | ma_df["سیگنال"].str.contains("فروش")).sum()) if not ma_df.empty else int(osc_df["سیگنال"].str.contains("فروش").sum())
                _total = len(osc_df) + len(ma_df)
                _neu = _total - _buy - _sell
                _score2 = round((_buy - _sell) / _total * 100) if _total else 0
                st.subheader("🧭 جمع‌بندی تکنیکال (مثل TradingView)")
                sm1, sm2, sm3, sm4 = st.columns(4)
                sm1.metric("امتیاز جمع‌بندی", f"{_score2:+d}", delta="خرید قوی" if _score2 > 40 else "خرید" if _score2 > 12 else "خنثی" if _score2 > -12 else "فروش" if _score2 > -40 else "فروش قوی")
                sm2.metric("🟢 خرید", _buy)
                sm3.metric("⚪ خنثی", _neu)
                sm4.metric("🔴 فروش", _sell)
                st.progress(min(1.0, max(0.0, (_score2 + 100) / 200)))
                oc, mc = st.columns(2)
                with oc:
                    st.markdown("**اسیلاتورها**")
                    st.dataframe(osc_df, use_container_width=True, hide_index=True)
                with mc:
                    st.markdown("**میانگین‌های متحرک**")
                    st.dataframe(ma_df, use_container_width=True, hide_index=True)
                pc, dc = st.columns(2)
                with pc:
                    st.markdown("**الگوهای کندلی اخیر**")
                    _pats = candle_patterns(d)
                    if _pats:
                        st.dataframe(pd.DataFrame(_pats), use_container_width=True, hide_index=True)
                    else:
                        st.info("الگوی مشخصی در کندل‌های اخیر نیست.")
                with dc:
                    st.markdown("**واگرایی‌ها (RSI / MACD)**")
                    _divs = divergence_list(d)
                    if _divs:
                        st.dataframe(pd.DataFrame(_divs), use_container_width=True, hide_index=True)
                    else:
                        st.info("واگرایی معناداری نیست.")

            with sub_agents:
                st.subheader("🤖 شش ایجنت استراتژی — بک‌تست روی همین داده (با کارمزد)")
                try:
                    _stats, _combined, _consensus, _curves = run_agents(d)
                    ag1, ag2, ag3 = st.columns(3)
                    ag1.metric("اجماع ایجنت‌ها", f"{_consensus:+d}")
                    ag2.metric("سود میانگین", f"{_stats['سود بک‌تست %'].mean():+.2f}٪")
                    ag3.metric("ایجنت فعال الان", f"{int(_stats['سیگنال الان'].str.contains('لانگ|شورت').sum())}/6")
                    st.dataframe(_stats, use_container_width=True, hide_index=True)
                    _efig = go.Figure()
                    _efig.add_trace(go.Scatter(y=_combined, line=dict(color="#34d399", width=1.8), name="سود تجمیعی (میانگین)"))
                    _efig.add_hline(y=0, line_color="#64748b", line_dash="dot")
                    _efig.update_layout(height=220, template="plotly_dark", margin=dict(l=10, r=10, t=24, b=10),
                                        title="منحنی سود تجمیعی ایجنت‌ها (%)")
                    st.plotly_chart(_efig, use_container_width=True)
                except Exception:
                    st.info("بک‌تست ایجنت‌ها روی این داده ممکن نشد.")
                st.subheader("🎯 ماتریس لبه (Edge) — امتیاز اسیلاتور در برابر بازده ۵ کندل بعد")
                try:
                    _xs, _ys, _slope, _corr = edge_data(d)
                    if len(_xs) >= 10:
                        _colors = ["#22c55e" if y > 0 else "#f43f5e" for y in _ys]
                        _xline = np.array([-1.0, 1.0])
                        _yline = _slope * _xline + float(np.mean(_ys) - _slope * np.mean(_xs))
                        _efig2 = go.Figure()
                        _efig2.add_trace(go.Scatter(x=_xs, y=_ys, mode="markers", marker=dict(color=_colors, size=5, opacity=0.6), name="نمونه‌ها"))
                        _efig2.add_trace(go.Scatter(x=_xline, y=_yline, line=dict(color="#facc15", dash="dash"), name="رگرسیون"))
                        _efig2.update_layout(height=300, template="plotly_dark", margin=dict(l=10, r=10, t=24, b=10),
                                             xaxis_title="امتیاز اسیلاتور", yaxis_title="بازده ۵ کندل بعد %")
                        st.plotly_chart(_efig2, use_container_width=True)
                        st.caption(f"شیب رگرسیون: {_slope:.2f} · همبستگی: {_corr:.2f} · {'لبه‌ی مثبت (مومنتوم)' if _corr > 0.05 else 'لبه‌ی معکوس (بازگشت)' if _corr < -0.05 else 'لبه‌ی معنادار نیست'}")
                    else:
                        st.info("نمونه‌ی کافی برای ماتریس لبه نیست.")
                except Exception:
                    st.info("ماتریس لبه قابل محاسبه نیست.")

            with sub_funda:
                st.subheader("💰 فاندامنتال (CoinGecko)")
                _base = symbol.split("-")[0]
                _fund = fetch_fundamentals(_base)
                if not _fund:
                    st.info("داده‌ی فاندامنتال برای این نماد پیدا نشد (فقط رمزارزهای شناخته‌شده).")
                else:
                    def _cmp(v: float) -> str:
                        a = abs(float(v))
                        return f"${a/1e12:.2f}T" if a >= 1e12 else f"${a/1e9:.2f}B" if a >= 1e9 else f"${a/1e6:.2f}M" if a >= 1e6 else f"${a:,.0f}"
                    f1, f2, f3, f4 = st.columns(4)
                    f1.metric("رتبه بازار", f"#{_fund.get('market_cap_rank', '—')}")
                    f2.metric("ارزش بازار", _cmp(_fund.get("market_cap", 0)))
                    f3.metric("حجم ۲۴س", _cmp(_fund.get("total_volume", 0)))
                    f4.metric("سقف تاریخی ATH", f"{float(_fund.get('ath', 0)):,.4g} ({float(_fund.get('ath_change_percentage', 0)):.1f}٪)")
                    f5, f6, f7, f8 = st.columns(4)
                    f5.metric("عرضه در گردش", f"{float(_fund.get('circulating_supply', 0)):,.0f}")
                    f6.metric("تغییر ۲۴س", f"{float(_fund.get('price_change_percentage_24h') or 0):+.2f}٪")
                    f7.metric("تغییر ۷ روز", f"{float((_fund.get('price_change_percentage_7d_in_currency') or 0)):+.2f}٪")
                    f8.metric("تغییر ۳۰ روز", f"{float((_fund.get('price_change_percentage_30d_in_currency') or 0)):+.2f}٪")
                    st.caption("منبع: CoinGecko (رایگان، کش ۳ دقیقه).")
        except Exception as e:  # noqa: BLE001
            st.error(f"خطا در دریافت/تحلیل داده: {e}")
            st.info("نماد را مثل BTC-USDT بنویس؛ اگر صرافی انتخابی در منطقه‌ات مسدود است، KuCoin را انتخاب کن.")

    with tab_top:
        try:
            try:
                _fg = fetch_fear_greed()
                _br = fetch_breadth()
                b1, b2, b3, b4 = st.columns(4)
                b1.metric("شاخص ترس و طمع", f"{_fg['value']} · {_fg['label']}" if _fg else "—")
                b2.metric("وسعت بازار (صعودی)", f"{round(_br['gainers'] / max(1, _br['total']) * 100)}٪ از {_br['total']} بازار")
                b3.metric("تغییر میانه بازار", f"{_br['median_change']:+.2f}٪")
                b4.metric("سهم BTC از حجم", f"{_br['btc_share']:.1f}٪")
            except Exception:
                pass
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
