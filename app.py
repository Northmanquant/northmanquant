"""
NorthmanQuant — Free Lite Edition (Streamlit)

نسخه‌ی سبک و رایگان نورث‌من‌کوانت برای دیپلوی رایگان روی Streamlit Community Cloud
یا Hugging Face Spaces. بدون دیتابیس و بدون هیچ کلید API — همه‌چیز از APIهای عمومی
صرافی‌ها خوانده می‌شود.

صرافی‌های پشتیبانی‌شده (همه با مستندات رسمی):
    KuCoin   · https://www.kucoin.com/docs
    OKX      · https://www.okx.com/docs-v5/en/
    Binance  · https://developers.binance.com/docs/binance-spot-api-docs
    Bybit    · https://bybit-exchange.github.io/docs/v5/market/kline
    Lighter  · https://apidocs.lighter.xyz  (perp DEX — /api/v1/candles)

اجرا محلی:  streamlit run app.py
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
LIGHTER = "https://mainnet.zklighter.elliot.ai"

INTERVAL_MINUTES = {"15min": 15, "1hour": 60, "4hour": 240, "1day": 1440, "1week": 10080}

KUCOIN_TF = {"15min": "15min", "1hour": "1hour", "4hour": "4hour", "1day": "1day", "1week": "1week"}
BINANCE_TF = {"15min": "15m", "1hour": "1h", "4hour": "4h", "1day": "1d", "1week": "1w"}
BYBIT_TF = {"15min": "15", "1hour": "60", "4hour": "240", "1day": "D", "1week": "W"}
OKX_TF = {"15min": "15m", "1hour": "1H", "4hour": "4H", "1day": "1D", "1week": "1W"}
LIGHTER_TF = {"15min": "15m", "1hour": "1h", "4hour": "4h", "1day": "1d", "1week": "1w"}

EXCHANGES = ["KuCoin", "OKX", "Binance", "Bybit", "Lighter"]

EXCHANGE_DOCS = {
    "KuCoin": "https://www.kucoin.com/docs/rest/spot/market-data/get-klines",
    "OKX": "https://www.okx.com/docs-v5/en/#order-book-trading-market-data",
    "Binance": "https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints",
    "Bybit": "https://bybit-exchange.github.io/docs/v5/market/kline",
    "Lighter": "https://apidocs.lighter.xyz/reference/candles",
}

ENTER = 40
EXIT = -10

# Whitelist of common perp/spot pairs across all exchanges — for the one-tap
# "analyse a symbol" feature.
QUICK_SYMBOLS = [
    "BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT", "XRP-USDT",
    "DOGE-USDT", "TON-USDT", "ADA-USDT", "AVAX-USDT", "LINK-USDT",
    "LTC-USDT", "TRX-USDT", "ATOM-USDT", "NEAR-USDT", "APT-USDT",
    # Lighter perps (no -USDT suffix needed)
    "BTC", "ETH", "SOL",
]


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
@keyframes nq-glow { 0%,100%{text-shadow:0 0 14px rgba(56,189,248,.35)} 50%{text-shadow:0 0 26px rgba(52,211,153,.55)} }
.nq-glow{animation:nq-glow 3.2s ease-in-out infinite}
</style>
"""

HEADERS = {"User-Agent": "northmanquant-lite/1.0", "accept": "application/json"}


def fetch_tick(exchange: str, symbol: str) -> dict | None:
    """Latest price (+bid/ask) from the selected exchange. No caching — this is the live layer."""
    try:
        if exchange == "Binance":
            r = requests.get(f"{BINANCE}/api/v3/ticker/bookTicker", params={"symbol": symbol.replace("-", "")}, headers=HEADERS, timeout=6)
            j = r.json()
            bid, ask = float(j["bidPrice"]), float(j["askPrice"])
            return {"price": (bid + ask) / 2, "bid": bid, "ask": ask}
        if exchange == "Bybit":
            r = requests.get(f"{BYBIT}/v5/market/tickers", params={"category": "spot", "symbol": symbol.replace("-", "")}, headers=HEADERS, timeout=6)
            row = ((r.json().get("result") or {}).get("list") or [{}])[0]
            return {"price": float(row["lastPrice"]), "bid": float(row.get("bid1Price") or 0), "ask": float(row.get("ask1Price") or 0)}
        if exchange == "OKX":
            r = requests.get(f"{OKX}/api/v5/market/ticker", params={"instId": symbol}, headers=HEADERS, timeout=6)
            row = (r.json().get("data") or [{}])[0]
            return {"price": float(row["last"]), "bid": float(row.get("bidPx") or 0), "ask": float(row.get("askPx") or 0)}
        if exchange == "Lighter":
            mid = lighter_market_id(symbol)
            if mid is None:
                return None
            r = requests.get(f"{LIGHTER}/api/v1/orderBookDetails", params={"market_id": mid}, headers=HEADERS, timeout=8)
            row = ((r.json().get("order_book_details") or [{}])[0]) or {}
            price = float(row.get("last_trade_price") or 0)
            mark = float(row.get("mark_price") or 0)
            bid = ask = 0.0
            try:
                ob = requests.get(f"{LIGHTER}/api/v1/orderBookOrders", params={"market_id": mid, "limit": 50}, headers=HEADERS, timeout=8).json()
                asks = [float(o["price"]) for o in (ob.get("asks") or []) if o.get("price")]
                bids = [float(o["price"]) for o in (ob.get("bids") or []) if o.get("price")]
                if asks:
                    ask = min(asks)
                if bids:
                    bid = max(bids)
            except Exception:
                pass
            return {"price": price or mark, "bid": bid, "ask": ask, "mark": mark}
        r = requests.get(f"{KUCOIN}/api/v1/market/orderbook/level1", params={"symbol": symbol}, headers=HEADERS, timeout=6)
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


def _live_strip_impl(symbol: str, exchange: str, interval: str, dec: int, extra: dict | None = None) -> None:
    """
    Live ticker strip — built with Streamlit native widgets so it re-renders
    safely inside `st.fragment`. (Raw HTML inside fragments is escaped, which
    is what made the previous version crash with ValueError.)
    """
    import time as _t

    tick = fetch_tick(exchange, symbol)
    state = st.session_state.get("nq_state") or {}
    score = st.session_state.get("nq_score")
    prev = st.session_state.get("nq_last_price")
    price = tick["price"] if tick else None

    if price is not None and prev:
        if price > prev:
            st.session_state["nq_arrow"] = "up"
        elif price < prev:
            st.session_state["nq_arrow"] = "down"
    if price is not None:
        st.session_state["nq_last_price"] = price

    minutes = INTERVAL_MINUTES.get(interval, 60)
    left = minutes * 60 - (int(_t.time()) % (minutes * 60))
    progress = max(0, min(100, int((1 - left / (minutes * 60)) * 100)))
    countdown = f"{left // 60:02d}:{left % 60:02d}"

    pnl = None
    if state.get("status") in ("long", "short") and state.get("entry") and price:
        entry = float(state["entry"])
        pnl = (price - entry) / entry * 100 * (1 if state["status"] == "long" else -1)

    cols = st.columns([1.4, 1.3, 1.6, 1.0, 1.0, 0.9], gap="small")

    with cols[0]:
        st.markdown(
            "<span style='color:#a5f3fc;font-size:11px;font-weight:700'>"
            "<span class='nq-live-dot'></span> LIVE · زنده</span>",
            unsafe_allow_html=True,
        )
        price_txt = f"{price:,.{dec}f}" if price is not None else "—"
        st.markdown(
            f"<span class='nq-glow' style='font-family:ui-monospace,monospace;font-size:26px;"
            f"font-weight:800;color:#f8fafc'>{price_txt}</span>",
            unsafe_allow_html=True,
        )

    with cols[1]:
        if tick and tick.get("bid"):
            b, a = tick["bid"], tick["ask"]
            st.markdown(
                f"<div style='font-family:ui-monospace,monospace;font-size:11px;color:#94a3b8'>"
                f"Bid <b style='color:#34d399'>{b:,.{dec}f}</b></div>"
                f"<div style='font-family:ui-monospace,monospace;font-size:11px;color:#94a3b8'>"
                f"Ask <b style='color:#fb7185'>{a:,.{dec}f}</b></div>",
                unsafe_allow_html=True,
            )
        elif price is not None:
            st.caption("bid/ask در دسترس نیست")

    with cols[2]:
        if score is not None:
            tone = "#34d399" if score >= 0 else "#fb7185"
            st.markdown(
                "<div style='font-size:11px;color:#94a3b8;font-family:ui-monospace,monospace'>"
                "امتیاز همگرایی</div>"
                f"<div style='font-size:22px;font-weight:800;color:{tone};"
                f"font-family:ui-monospace,monospace;line-height:1.1'>{score:+.0f}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.caption("امتیاز: —")

    with cols[3]:
        if pnl is not None and state.get("status"):
            label = "🟢 لانگ" if state["status"] == "long" else "🔴 شورت"
            tone = "#34d399" if pnl >= 0 else "#fb7185"
            st.markdown(
                "<div style='font-size:11px;color:#94a3b8'>پوزیشن فعال</div>"
                f"<div style='font-size:12px;font-weight:700'>{label}</div>"
                f"<div style='font-size:18px;font-weight:800;color:{tone};"
                f"font-family:ui-monospace,monospace;line-height:1.1'>{pnl:+.2f}%</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='font-size:11px;color:#94a3b8'>خارج از بازار</div>"
                "<div style='font-size:18px;font-weight:800;color:#475569;"
                "font-family:ui-monospace,monospace'>—</div>",
                unsafe_allow_html=True,
            )

    with cols[4]:
        if extra:
            parts = []
            if extra.get("mark"):
                parts.append(
                    "<div style='font-size:11px;color:#94a3b8'>Mark "
                    f"<b style='color:#a5b4fc;font-family:ui-monospace,monospace'>"
                    f"{extra['mark']:,.{dec}f}</b></div>"
                )
            if extra.get("open_interest") is not None:
                parts.append(
                    "<div style='font-size:11px;color:#94a3b8'>OI "
                    f"<b style='color:#fbbf24;font-family:ui-monospace,monospace'>"
                    f"{extra['open_interest']:,.2f}</b></div>"
                )
            if parts:
                st.markdown("".join(parts), unsafe_allow_html=True)
            else:
                st.caption("—")
        else:
            st.caption("—")

    with cols[5]:
        st.markdown(
            f"<div style='text-align:center;font-family:ui-monospace,monospace'>"
            f"<div style='font-size:12px;color:#cbd5e1'>⏳ {countdown}</div></div>",
            unsafe_allow_html=True,
        )
        st.progress(progress, text=None)
        st.caption("<span style='font-size:9px;color:#64748b'>تا بستن کندل</span>", unsafe_allow_html=True)


try:
    live_strip_auto = st.fragment(run_every=5)(_live_strip_impl)
    live_strip_manual = st.fragment(_live_strip_impl)
except Exception:  # older Streamlit without fragment auto-rerun
    live_strip_auto = _live_strip_impl  # type: ignore
    live_strip_manual = _live_strip_impl  # type: ignore


# ------------------------------------------------------------------ symbols

def normalize_symbol(raw: str, exchange: str = "KuCoin") -> str:
    s = (raw or "BTC-USDT").strip().upper().replace("/", "-").replace("_", "-").replace(" ", "")
    if not s:
        s = "BTC-USDT"
    if exchange == "Lighter":
        for suffix in ("-USDT", "-USDC", "-PERP", "PERP"):
            if s.endswith(suffix):
                s = s[: -len(suffix)]
        return s or "BTC"
    if "-" in s:
        return s
    for q in ("USDT", "USDC", "BTC", "ETH", "EUR"):
        if s.endswith(q) and len(s) > len(q):
            return f"{s[: -len(q)]}-{q}"
    return f"{s}-USDT"


# ------------------------------------------------------------------ data

@st.cache_data(ttl=300, show_spinner=False)
def lighter_markets() -> list[dict]:
    """All Lighter markets (public, no key). Docs: apidocs.lighter.xyz/reference/orderBookDetails"""
    r = requests.get(f"{LIGHTER}/api/v1/orderBookDetails", headers=HEADERS, timeout=25)
    r.raise_for_status()
    data = r.json()
    rows = []
    for row in (data.get("order_book_details") or []):
        rows.append(
            {
                "symbol": row.get("symbol", ""),
                "market_id": row.get("market_id"),
                "status": row.get("status", ""),
                "last": float(row.get("last_trade_price") or 0),
                "mark": float(row.get("mark_price") or 0),
                "change%": float(row.get("daily_price_change") or 0),
                "high": float(row.get("daily_price_high") or 0),
                "low": float(row.get("daily_price_low") or 0),
                "turnoverM$": float(row.get("daily_quote_token_volume") or 0) / 1e6,
                "open_interest": float(row.get("open_interest") or 0),
            }
        )
    return rows


@st.cache_data(ttl=60, show_spinner=False)
def lighter_market_id(symbol: str) -> int | None:
    """Resolve a Lighter symbol (e.g. BTC) to its market_id. Never hard-code ids."""
    for row in lighter_markets():
        if row["symbol"].upper() == symbol.upper():
            return row["market_id"]
    return None


@st.cache_data(ttl=60, show_spinner=False)
def fetch_candles(exchange: str, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
    """OHLCV from public exchange APIs. Falls back to another exchange when one is region-blocked."""
    try:
        return _fetch_candles(exchange, symbol, interval, limit)
    except Exception:
        for alt in EXCHANGES:
            if alt == exchange:
                continue
            try:
                return _fetch_candles(alt, symbol, interval, limit)
            except Exception:
                continue
        raise


def _fetch_candles(exchange: str, symbol: str, interval: str, limit: int) -> pd.DataFrame:
    rows: list[dict] = []

    if exchange == "KuCoin":
        minutes = INTERVAL_MINUTES[interval]
        end = int(datetime.now(timezone.utc).timestamp())
        start = end - minutes * 60 * (limit + 10)
        r = requests.get(
            f"{KUCOIN}/api/v1/market/candles",
            params={"symbol": symbol, "type": KUCOIN_TF[interval], "startAt": start, "endAt": end},
            headers=HEADERS, timeout=20,
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
            headers=HEADERS, timeout=20,
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
            headers=HEADERS, timeout=20,
        )
        r.raise_for_status()
        data = (r.json().get("result") or {}).get("list") or []
        rows = [
            {"time": int(x[0]), "open": float(x[1]), "high": float(x[2]),
             "low": float(x[3]), "close": float(x[4]), "volume": float(x[5])}
            for x in data
        ]
    elif exchange == "Lighter":
        market_id = lighter_market_id(symbol)
        if market_id is None:
            raise ValueError(f"مارکت {symbol} روی Lighter پیدا نشد.")
        minutes = INTERVAL_MINUTES[interval]
        end = int(datetime.now(timezone.utc).timestamp() * 1000)
        start = end - minutes * 60 * 1000 * (limit + 10)
        r = requests.get(
            f"{LIGHTER}/api/v1/candles",
            params={
                "market_id": market_id,
                "resolution": LIGHTER_TF[interval],
                "start_timestamp": start,
                "end_timestamp": end,
                "count_back": min(500, limit),
                "set_timestamp_to_end": True,
            },
            headers=HEADERS, timeout=25,
        )
        r.raise_for_status()
        # Response: {"code":200,"r":"1h","c":[{"t","o","h","l","c","v","V","i"}]}
        # Zero values are omitted by the API -> use .get() with defaults.
        rows = [
            {"time": int(c["t"]), "open": float(c["o"]), "high": float(c["h"]),
             "low": float(c["l"]), "close": float(c["c"]), "volume": float(c.get("v") or 0.0)}
            for c in (r.json().get("c") or [])
            if c.get("t") and c.get("c")
        ]
    else:  # OKX
        r = requests.get(
            f"{OKX}/api/v5/market/candles",
            params={"instId": symbol, "bar": OKX_TF[interval], "limit": 300},
            headers=HEADERS, timeout=20,
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


@st.cache_data(ttl=300, show_spinner=False)
def fetch_top_coins(exchange: str = "KuCoin", min_turnover: float = 1_000_000, limit: int = 15) -> dict:
    """Top movers for the selected exchange (spot for CEXes, perps for Lighter)."""
    rows = []
    if exchange == "Lighter":
        for m in lighter_markets():
            if m["status"] != "active" or not m["symbol"]:
                continue
            if m["turnoverM$"] * 1e6 < min_turnover:
                continue
            rows.append({
                "symbol": m["symbol"],
                "price": m["last"],
                "change%": m["change%"],
                "high": m["high"],
                "low": m["low"],
                "turnoverM$": m["turnoverM$"],
            })
    elif exchange == "Binance":
        r = requests.get(f"{BINANCE}/api/v3/ticker/24hr", headers=HEADERS, timeout=25)
        r.raise_for_status()
        for t in r.json():
            sym = t.get("symbol", "")
            if not sym.endswith("USDT"):
                continue
            turnover = float(t.get("quoteVolume") or 0)
            if turnover < min_turnover:
                continue
            rows.append({
                "symbol": sym,
                "price": float(t.get("lastPrice") or 0),
                "change%": float(t.get("priceChangePercent") or 0),
                "high": float(t.get("highPrice") or 0),
                "low": float(t.get("lowPrice") or 0),
                "turnoverM$": turnover / 1e6,
            })
    elif exchange == "Bybit":
        r = requests.get(f"{BYBIT}/v5/market/tickers", params={"category": "spot"}, headers=HEADERS, timeout=25)
        r.raise_for_status()
        for t in ((r.json().get("result") or {}).get("list") or []):
            sym = t.get("symbol", "")
            if not sym.endswith("USDT"):
                continue
            turnover = float(t.get("turnover24h") or 0)
            if turnover < min_turnover:
                continue
            last = float(t.get("lastPrice") or 0)
            prev = float(t.get("prevPrice24h") or 0)
            rows.append({
                "symbol": sym,
                "price": last,
                "change%": ((last - prev) / prev * 100) if prev else 0.0,
                "high": float(t.get("highPrice24h") or 0),
                "low": float(t.get("lowPrice24h") or 0),
                "turnoverM$": turnover / 1e6,
            })
    elif exchange == "OKX":
        r = requests.get(f"{OKX}/api/v5/market/tickers", params={"instType": "SPOT"}, headers=HEADERS, timeout=25)
        r.raise_for_status()
        for t in (r.json().get("data") or []):
            sym = t.get("instId", "")
            if not sym.endswith("-USDT"):
                continue
            turnover = float(t.get("volCcy24h") or 0)
            if turnover < min_turnover:
                continue
            last = float(t.get("last") or 0)
            open24 = float(t.get("open24h") or 0)
            rows.append({
                "symbol": sym,
                "price": last,
                "change%": ((last - open24) / open24 * 100) if open24 else 0.0,
                "high": float(t.get("high24h") or 0),
                "low": float(t.get("low24h") or 0),
                "turnoverM$": turnover / 1e6,
            })
    else:  # KuCoin
        r = requests.get(f"{KUCOIN}/api/v1/market/allTickers", headers=HEADERS, timeout=25)
        r.raise_for_status()
        tickers = (r.json().get("data") or {}).get("ticker") or []
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
        raise ValueError("فهرست بازار خالی بود")
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
    """Extract candles from a chart screenshot.

    Two-stage detector:
      1) build a 1D "column activity" signal of long vertical colour runs
      2) light-merge only the 1-2 pixel bridges caused by wicks / anti-aliasing
    """
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

    # ---------- stage 1: column activity (long vertical colour runs) ----------
    MIN_RUN = max(4, int(h * 0.008))  # 0.8% of chart height — strips wicks/EMA
    col_on = np.zeros(w, dtype=bool)
    for x in range(w):
        run = 0
        for y in range(h):
            run = run + 1 if mask[y, x] else 0
            if run >= MIN_RUN:
                col_on[x] = True
                break

    # ---------- stage 2: light merge of micro-clusters only ----------
    raw_clusters: list[tuple[int, int]] = []
    x = 0
    while x < w:
        if col_on[x]:
            x0 = x
            while x < w and col_on[x]:
                x += 1
            raw_clusters.append((x0, x - 1))
        else:
            x += 1

    if not raw_clusters:
        return pd.DataFrame()

    MAX_BRIDGE = 2  # px — only merge pixel-noise bridges
    clusters: list[tuple[int, int]] = []
    cur = list(raw_clusters[0])
    for i in range(1, len(raw_clusters)):
        nxt = raw_clusters[i]
        gap = nxt[0] - cur[1] - 1
        if gap <= MAX_BRIDGE:
            cur[1] = nxt[1]
        else:
            clusters.append((cur[0], cur[1]))
            cur = list(nxt)
    clusters.append((cur[0], cur[1]))

    # Drop any cluster wider than 5% of image width — those are EMAs /
    # shaded regions, not single candles.
    max_width = max(6, int(w * 0.05))
    clusters = [(a, b) for a, b in clusters if 1 <= b - a + 1 <= max_width]

    if len(clusters) < 8:
        return pd.DataFrame()

    # ---------- per-cluster candle geometry ----------
    raw = []
    for (x0, x1) in clusters:
        sub = mask[:, x0: x1 + 1]
        ys = np.where(sub.any(axis=1))[0]
        if len(ys) == 0:
            continue
        top, bot = int(ys.min()), int(ys.max())

        row_counts = sub.sum(axis=1)
        max_count = row_counts.max()
        if max_count == 0:
            continue
        wide = np.where(row_counts >= max(2, max_count * 0.55))[0]
        if len(wide) == 0:
            wide = ys
        b_top, b_bot = int(wide.min()), int(wide.max())

        red_px = red[top: bot + 1, x0: x1 + 1].sum()
        green_px = (green | blue)[top: bot + 1, x0: x1 + 1].sum()
        bull = green_px >= red_px

        raw.append({"x": (x0 + x1) / 2 / w, "top": top, "bot": bot, "b_top": b_top, "b_bot": b_bot, "bull": bool(bull)})

    if len(raw) < 8:
        return pd.DataFrame()
    span_top, span_bot = min(r["top"] for r in raw), max(r["bot"] for r in raw)
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


# ------------------------------------------------------------------ helpers

def build_chart_image(d: pd.DataFrame, plan: dict, levels: pd.DataFrame, symbol: str, exchange: str) -> "PIL.Image.Image":
    """Render a simple annotated candlestick chart as a PNG (matplotlib-free)."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22],
                        vertical_spacing=0.04, subplot_titles=(f"{symbol} · {exchange}", "حجم"))
    fig.add_trace(go.Candlestick(
        x=d["dt"], open=d["open"], high=d["high"], low=d["low"], close=d["close"],
        increasing_line_color="#22c55e", decreasing_line_color="#ef4444", name="قیمت",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=d["dt"], y=d["ema20"], line=dict(color="#38bdf8", width=1.2), name="EMA20"), row=1, col=1)
    fig.add_trace(go.Scatter(x=d["dt"], y=d["ema50"], line=dict(color="#f472b6", width=1.2), name="EMA50"), row=1, col=1)
    fig.add_trace(go.Scatter(x=d["dt"], y=d["bb_up"], line=dict(color="#94a3b8", width=0.8, dash="dot"), name="BB↑"), row=1, col=1)
    fig.add_trace(go.Scatter(x=d["dt"], y=d["bb_lo"], line=dict(color="#94a3b8", width=0.8, dash="dot"), name="BB↓"), row=1, col=1)
    fig.add_hline(y=plan["entry"], line_color="#f59e0b", line_width=2, annotation_text="ورود", row=1, col=1)
    fig.add_hline(y=plan["stop"], line_color="#ef4444", line_dash="dash", annotation_text="حد ضرر", row=1, col=1)
    for i, (t_price, t_rr) in enumerate(plan["targets"]):
        fig.add_hline(y=t_price, line_color="#38bdf8", line_dash="dash",
                      annotation_text=f"هدف {i + 1} · {t_rr}R", row=1, col=1)
    if not levels.empty:
        for _, row in levels.iterrows():
            colour = "#fb7185" if "مقاومت" in str(row["نوع"]) else "#22c55e"
            fig.add_hline(y=float(row["سطح"]), line=dict(color=colour, width=0.8, dash="dot"),
                          annotation_text=f"{row['نوع']} {float(row['سطح']):,.2f}",
                          annotation_position="right", row=1, col=1)
    colors = ["#22c55e" if c >= o else "#ef4444" for c, o in zip(d["close"], d["open"])]
    fig.add_trace(go.Bar(x=d["dt"], y=d["volume"], marker_color=colors, name="حجم"), row=2, col=1)
    fig.update_layout(
        height=620, xaxis_rangeslider_visible=False, template="plotly_dark",
        legend=dict(orientation="h", y=1.02),
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="#0b1220", plot_bgcolor="#0b1220",
    )

    try:
        png_bytes = fig.to_image(format="png", width=1200, height=620, scale=2)
        return Image.open(io.BytesIO(png_bytes))
    except Exception:
        return None


# ------------------------------------------------------------------ one-tap analysis

def analyse_symbol(symbol_in: str, exchange: str, interval: str) -> dict:
    """Top-level orchestration: candles → indicators → levels → plan → chart PNG."""
    symbol = normalize_symbol(symbol_in, exchange)
    df = fetch_candles(exchange, symbol, interval)
    d = add_indicators(df)
    score_series, comp_table = confluence(d)
    score = float(score_series.iloc[-1])
    levels = swing_levels(d)
    plan = make_plan(d, score, levels)
    events, state = signal_events(d, score_series)
    price = float(d["close"].iloc[-1])
    return {
        "symbol": symbol,
        "exchange": exchange,
        "interval": interval,
        "price": price,
        "decimals": 2 if price >= 1000 else 4 if price >= 1 else 6,
        "score": score,
        "comp_table": comp_table,
        "levels": levels,
        "plan": plan,
        "events": events,
        "state": state,
        "score_series": score_series,
        "df": d,
    }


# ------------------------------------------------------------------ UI

def main() -> None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import io

    st.set_page_config(page_title="NorthmanQuant — نسخه رایگان", page_icon="📈", layout="wide")
    st.markdown(
        "<div dir='rtl'><h1 style='margin-bottom:0'>📈 NorthmanQuant — نسخه‌ی رایگان (Lite)</h1>"
        "<p style='color:#888;margin-top:4px'>تحلیل زنده با داده‌ی عمومی صرافی‌ها — بدون ثبت‌نام و بدون کلید API. "
        "نسخه‌ی کامل (حساب، معامله، پنل مدیریت) روی سایت اصلی است.</p></div>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("⚙️ تنظیمات")
        symbol_in = st.text_input("نماد", value="BTC-USDT", help="مثل BTC-USDT یا gramusdt · برای Lighter فقط BTC")
        exchange = st.selectbox("صرافی", EXCHANGES)
        interval = st.selectbox("تایم‌فریم", list(INTERVAL_MINUTES.keys()), index=1)
        live_on = st.checkbox("🔴 حالت زنده (قیمت هر ۵ ثانیه)", value=True)
        auto = st.checkbox("بازخوانی کامل خودکار (۶۰ ثانیه)", value=False)

        st.divider()
        st.subheader("⚡ تحلیل خودکار")
        st.caption("نماد + صرافی + تایم‌فریم را انتخاب کن و دکمه را بزن.")
        quick = st.selectbox(
            "یا از این لیست سریع انتخاب کن",
            options=["(انتخاب دستی)"] + QUICK_SYMBOLS,
            index=0,
        )
        if quick != "(انتخاب دستی)":
            st.session_state["quick_symbol"] = quick
        if "quick_symbol" in st.session_state and st.session_state.get("quick_symbol") and st.button("🚀 تحلیل کن", type="primary", use_container_width=True):
            qsym = st.session_state["quick_symbol"]
            qex = "Lighter" if not qsym.endswith("-USDT") else "KuCoin"
            qint = "1hour"
            st.session_state["auto_analyse"] = {
                "symbol": qsym,
                "exchange": qex,
                "interval": qint,
            }
            st.session_state["active_tab"] = "tab_analyser"
            try:
                st.rerun()
            except Exception:
                pass

    # Honour the auto-analyse jump
    if st.session_state.get("auto_analyse"):
        symbol = st.session_state["auto_analyse"]["symbol"]
        exchange = st.session_state["auto_analyse"]["exchange"]
        interval = st.session_state["auto_analyse"]["interval"]
        st.session_state["active_tab"] = "tab_analyser"
    else:
        symbol = normalize_symbol(symbol_in, exchange)
        interval = interval

    st.markdown(LIVE_CSS, unsafe_allow_html=True)

    # market ticker (spot for CEXes, perps for Lighter)
    try:
        _tops = fetch_top_coins(exchange, 500_000, 14)
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

    tabs_list = [
        "🚀 تحلیل خودکار",
        "📊 تحلیل زنده",
        "🏆 برترین‌ها",
        "📰 اخبار",
        "📷 تحلیل عکس",
        "📚 منابع داده",
    ]
    active = tabs_list.index("🚀 تحلیل خودکار") if st.session_state.get("active_tab") == "tab_analyser" else 1
    tab_analyser, tab_live, tab_top, tab_news, tab_img, tab_docs = st.tabs(tabs_list)
    st.session_state.pop("active_tab", None)
    st.session_state.pop("auto_analyse", None)

    # ============================================================== 🚀 Auto
    with tab_analyser:
        st.markdown(
            f"<div dir='rtl' style='margin:0 0 10px'><b>تحلیل خودکار</b> · "
            f"<span style='color:#94a3b8'>{symbol} روی {exchange} ({interval})</span></div>",
            unsafe_allow_html=True,
        )

        run = st.button("🚀 اجرای تحلیل کامل", type="primary", use_container_width=True)
        if run or st.session_state.get("auto_run"):
            st.session_state["auto_run"] = True
            with st.spinner(f"در حال دریافت داده از {exchange} و تحلیل {symbol}…"):
                try:
                    res = analyse_symbol(symbol, exchange, interval)
                except Exception as e:
                    st.error(f"خطا: {e}")
                    st.info("صرافی دیگری را امتحان کنید یا نماد را به شکل صحیح وارد کنید (مثل BTC-USDT).")
                    res = None

            if res:
                dec = res["decimals"]
                price = res["price"]
                score = res["score"]
                plan = res["plan"]
                levels = res["levels"]
                d = res["df"]

                c1, c2, c3, c4, c5 = st.columns(5)
                label = (
                    "خرید قوی" if score > 40 else "خرید" if score > 12 else
                    "خنثی" if score > -12 else "فروش" if score > -40 else "فروش قوی"
                )
                c1.metric("قیمت لحظه‌ای", f"{price:,.{dec}f}", f"{res['symbol']} · {res['exchange']}")
                c2.metric("امتیاز همگرایی", f"{score:+.0f}", label)
                c3.metric("ATR", f"{plan['atr']:,.{dec}f}")
                c4.metric("R:R / اطمینان", f"1:{plan['rr']}", f"{plan['confidence']}٪")
                c5.metric(
                    "سیگنال",
                    plan["direction"],
                    "ورود" if plan["direction"].startswith("لانگ") else "خروج/شورت",
                )

                st.markdown("#### 🎯 طرح معامله")
                p1, p2, p3, p4, p5 = st.columns(5)
                p1.metric("جهت", plan["direction"])
                p2.metric("ورود", f"{plan['entry']:,.{dec}f}")
                p3.metric("حد ضرر", f"{plan['stop']:,.{dec}f}")
                p4.metric("هدف ۱", f"{plan['targets'][0][0]:,.{dec}f}", f"1:{plan['targets'][0][1]}R")
                p5.metric("هدف ۲", f"{plan['targets'][1][0]:,.{dec}f}", f"1:{plan['targets'][1][1]}R")

                st.markdown("#### 📈 نمودار تحلیلی")
                chart_img = build_chart_image(d, plan, levels, res["symbol"], res["exchange"])
                if chart_img is not None:
                    st.image(chart_img, caption=f"{res['symbol']} · {res['interval']} — خطوط ورود/حد ضرر/اهداف/حمایت و مقاومت رسم شده", use_container_width=True)
                    buf = io.BytesIO()
                    chart_img.save(buf, format="PNG")
                    st.download_button(
                        "⬇️ دانلود نمودار (PNG)",
                        data=buf.getvalue(),
                        file_name=f"{res['symbol'].replace('-', '')}_analysis.png",
                        mime="image/png",
                    )
                else:
                    st.caption("⚠️ برای دریافت خروجی PNG، پکیج `kaleido` روی Streamlit Cloud نصب نیست — "
                               "نمودار زنده در تب «تحلیل زنده» همان اطلاعات را تعاملی نشان می‌دهد.")

                st.markdown("#### 🧱 سطوح کلیدی")
                if not levels.empty:
                    show = levels.copy()
                    show["سطح"] = show["سطح"].map(lambda v: f"{v:,.{dec}f}")
                    st.dataframe(show, use_container_width=True, hide_index=True)
                else:
                    st.info("سطح معناداری پیدا نشد — تایم‌فریم را تغییر دهید.")

                st.markdown("#### 🌀 اجزای همگرایی")
                left, right = st.columns(2)
                with left:
                    st.markdown(build_galaxy_svg(res["comp_table"], score), unsafe_allow_html=True)
                with right:
                    st.dataframe(res["comp_table"], use_container_width=True, hide_index=True)

                if not res["events"].empty:
                    st.markdown("#### 📜 سیگنال‌های اخیر (۱۰ کندل آخر)")
                    st.dataframe(res["events"].tail(10).iloc[::-1], use_container_width=True, hide_index=True)

                st.markdown("#### 📊 روند امتیاز همگرایی (۱۲۰ کندل اخیر)")
                st.line_chart(res["score_series"].tail(120), height=160)

                st.caption("این تحلیل بر اساس داده‌ی زنده‌ی صرافی و ۹ اندیکاتور وزن‌دار است. صرفاً آموزشی است و توصیه‌ی سرمایه‌گذاری نیست.")

    # ============================================================== 📊 Live
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

            lighter_extra = None
            if exchange == "Lighter":
                try:
                    row = next((m for m in lighter_markets() if m["symbol"].upper() == symbol.upper()), None)
                    if row:
                        lighter_extra = {"mark": row["mark"], "open_interest": row["open_interest"]}
                        st.caption(
                            f"Lighter (perp) · Mark {row['mark']:,.{dec}f} · Open Interest {row['open_interest']:,.2f} "
                            f"· تغییر ۲۴س {row['change%']:+.2f}% · داده از apidocs.lighter.xyz"
                        )
                except Exception:
                    pass

            st.session_state["nq_state"] = state
            st.session_state["nq_score"] = score
            if live_on:
                live_strip_auto(symbol, exchange, interval, dec, lighter_extra)
            else:
                live_strip_manual(symbol, exchange, interval, dec, lighter_extra)

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
                st.subheader("🌀 کهکشان همگرایی (چرخان)")
                st.markdown(build_galaxy_svg(comp_table, score), unsafe_allow_html=True)
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
        except Exception as e:
            st.error(f"خطا در دریافت/تحلیل داده: {e}")
            st.info("نماد را مثل BTC-USDT بنویس؛ اگر صرافی انتخابی در منطقه‌ات مسدود است، KuCoin یا OKX یا Lighter را انتخاب کن.")

    with tab_top:
        try:
            tops = fetch_top_coins(exchange)
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
            st.caption(f"منبع: {exchange} — {EXCHANGE_DOCS[exchange]}")
        except Exception as e:
            st.error(f"دریافت فهرست بازار ممکن نشد: {e}")

    with tab_news:
        try:
            news = fetch_news()
            if news.empty:
                st.info("خبری دریافت نشد.")
            else:
                for _, row in news.iterrows():
                    st.markdown(f"**[{row['title']}]({row['link']})**  \n{row['source']} · {row['sentiment']} · {row['date']}")
        except Exception as e:
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
                    st.success(f"{len(cdf)} کندل استخراج شد. برای دقت بیشتر عکس با کیفیت بالاتر و کندل‌های واضح‌تر آپلود کن.")
                    st.dataframe(cdf[["open", "high", "low", "close"]].tail(15).round(2), use_container_width=True)
                    st.subheader("سطوح روی مقیاس نسبی تصویر (۰ تا ۱۰۰)")
                    st.dataframe(lv, use_container_width=True, hide_index=True)
                    st.caption("برای قیمت واقعی، سقف و کف قیمتِ دیده‌شده در عکس را در نسخه‌ی کامل سایت وارد کن (کالیبراسیون قیمت).")
            except Exception as e:
                st.error(f"پردازش عکس ممکن نشد: {e}")

    with tab_docs:
        st.subheader("📚 منابع داده (مستندات رسمی)")
        st.write("همه‌ی اندپوینت‌های این نسخه از مستندات عمومی رسمی صرافی‌ها خوانده می‌شوند و هیچ کلید API لازم نیست.")
        rows = [
            {"صرافی": "KuCoin", "نوع": "Spot", "کندل": "/api/v1/market/candles", "تیکر": "/api/v1/market/orderbook/level1",
             "مستندات": EXCHANGE_DOCS["KuCoin"]},
            {"صرافی": "OKX", "نوع": "Spot", "کندل": "/api/v5/market/candles", "تیکر": "/api/v5/market/ticker",
             "مستندات": EXCHANGE_DOCS["OKX"]},
            {"صرافی": "Binance", "نوع": "Spot", "کندل": "/api/v3/klines", "تیکر": "/api/v3/ticker/bookTicker",
             "مستندات": EXCHANGE_DOCS["Binance"]},
            {"صرافی": "Bybit", "نوع": "Spot", "کندل": "/v5/market/kline", "تیکر": "/v5/market/tickers",
             "مستندات": EXCHANGE_DOCS["Bybit"]},
            {"صرافی": "Lighter", "نوع": "Perp (DEX)", "کندل": "/api/v1/candles", "تیکر": "/api/v1/orderBookDetails + /api/v1/orderBookOrders",
             "مستندات": EXCHANGE_DOCS["Lighter"]},
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.markdown(
            """
**نکته‌های واقعیِ داده‌ها**
- KuCoin ردیف کندل را به ترتیب `[time, open, close, high, low, volume, turnover]` برمی‌گرداند (ترتیب باز/بسته با بقیه متفاوت است).
- Bybit و OKX لیست کندل را از جدید به قدیم می‌دهند؛ کد قبل از استفاده сорت می‌کند.
- Lighter حداکثر ۵۰۰ کندل در هر درخواست می‌دهد و مقادیر صفر را از پاسخ حذف می‌کند (در کد با مقدار پیش‌فرض هندل شده).
- Lighter مارکت‌ها «perp» هستند (مثل BTC بدون پسوند USDT) و `market_id` از اندپوینت `orderBookDetails` resolve می‌شود — هیچ شناسه‌ای هاردکد نیست.
- اگر یک صرافی در منطقه‌ات مسدود باشد، کد به‌ترتیب بقیه‌ی صرافی‌ها fallback می‌کند.
"""
        )

    if auto:
        import time as _time
        _time.sleep(60)
        st.rerun()


if __name__ == "__main__":
    main()
