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


def build_neural_shell_svg(comp_table: pd.DataFrame, score: float) -> str:
    """
    NEURAL SHELL — live animated feature-extraction flow (pure SVG + SMIL, no JS).

    Left: the 9 confluence features as nodes (colour = direction, bar = strength).
    Middle: curved synapses carrying animated particles toward the core.
    Right: a rotating neural "shell" of orbiting nodes whose glow reflects the
    overall confluence score. Everything animates in the browser via SMIL.
    """
    import math as _m

    W, H = 680, 360
    rows = []
    if comp_table is not None and not comp_table.empty and "امتیاز" in comp_table.columns:
        rows = list(zip(comp_table["اندیکاتور"].tolist(), [float(v) for v in comp_table["امتیاز"].tolist()]))
    if not rows:
        rows = [("—", 0.0)] * 9
    n = len(rows)

    core_x, core_y, core_r = 505.0, 180.0, 96.0
    node_x = 150.0
    top, bottom = 48.0, 320.0
    gap = (bottom - top) / max(1, n - 1)

    def col_of(v: float) -> str:
        return "#10b981" if v > 0.12 else "#f43f5e" if v < -0.12 else "#64748b"

    synapses, particles, nodes = [], [], []
    for i, (label, v) in enumerate(rows):
        y = top + i * gap
        color = col_of(v)
        strength = min(1.0, abs(v))
        # bezier from node to core
        c1x, c1y = node_x + 110, y
        c2x, c2y = core_x - 150, core_y + (y - core_y) * 0.25
        path = f"M {node_x + 8:.1f} {y:.1f} C {c1x:.1f} {c1y:.1f} {c2x:.1f} {c2y:.1f} {core_x - core_r * 0.7:.1f} {core_y:.1f}"
        pid = f"nsyn{i}"
        synapses.append(
            f'<path id="{pid}" d="{path}" fill="none" stroke="{color}" '
            f'stroke-opacity="{0.10 + strength * 0.45:.2f}" stroke-width="{0.6 + strength * 1.8:.2f}"/>'
        )
        # a couple of travelling particles per synapse
        dur = 2.2 + (i % 5) * 0.6
        for k in range(2):
            begin = (k * dur / 2) + i * 0.17
            particles.append(
                f'<circle r="{1.6 + strength * 1.8:.1f}" fill="{color}">'
                f'<animateMotion dur="{dur:.1f}s" begin="{begin:.2f}s" repeatCount="indefinite">'
                f'<mpath href="#{pid}"/></animateMotion>'
                f'<animate attributeName="opacity" values="0;1;1;0" dur="{dur:.1f}s" begin="{begin:.2f}s" repeatCount="indefinite"/>'
                f'</circle>'
            )
        # node: pulsing dot + strength bar + label
        bar_w = 26 + strength * 42
        short = str(label)
        if len(short) > 13:
            short = short[:12] + "…"
        nodes.append(
            f'<g>'
            f'<rect x="20" y="{y - 9:.1f}" width="124" height="18" rx="4" fill="rgba(148,163,184,0.06)" stroke="rgba(148,163,184,0.12)"/>'
            f'<rect x="22" y="{y + 4:.1f}" width="{bar_w:.0f}" height="2.4" rx="1.2" fill="{color}"/>'
            f'<text x="28" y="{y + 0.5:.1f}" font-size="8.5" fill="#cbd5e1" font-family="ui-monospace,monospace">{short}</text>'
            f'<circle cx="{node_x + 4:.1f}" cy="{y:.1f}" r="3.2" fill="{color}">'
            f'<animate attributeName="r" values="2.4;4.2;2.4" dur="{1.8 + (i % 4) * 0.4:.1f}s" repeatCount="indefinite"/></circle>'
            f'</g>'
        )

    # rotating shell: orbiting nodes on 3 rings
    shell = []
    for i in range(70):
        h1 = (np.sin(i * 127.1) * 43758.5453) % 1
        h2 = (np.sin(i * 311.7) * 12543.123) % 1
        ang = h1 * 2 * _m.pi
        ring = 40 + h2 * (core_r - 46)
        x = core_x + ring * _m.cos(ang)
        y = core_y + ring * _m.sin(ang) * 0.92
        warm = i % 3 == 0
        c = "#f59e0b" if warm else "#7dd3fc"
        dur = 1.6 + (i % 7) * 0.45
        shell.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{1.0 + h2 * 1.9:.1f}" fill="{c}">'
            f'<animate attributeName="opacity" values="0.15;0.95;0.15" dur="{dur:.1f}s" repeatCount="indefinite"/></circle>'
        )

    score_color = "#34d399" if score > 25 else "#fb7185" if score < -25 else "#fbbf24"
    bar_pct = max(2, min(100, int((score + 100) / 2)))

    return f"""
<div style="display:flex;justify-content:center">
<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:680px" role="img" aria-label="neural shell feature extraction">
  <defs>
    <radialGradient id="nsCore" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="rgba(245,158,11,0.30)"/>
      <stop offset="55%" stop-color="rgba(56,189,248,0.10)"/>
      <stop offset="100%" stop-color="rgba(2,6,17,0)"/>
    </radialGradient>
    <linearGradient id="nsHead" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#34d399"/>
      <stop offset="100%" stop-color="#38bdf8"/>
    </linearGradient>
  </defs>

  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="rgba(2,6,17,0.55)" stroke="rgba(56,189,248,0.18)"/>

  <!-- header -->
  <text x="20" y="24" font-size="11.5" font-family="ui-monospace,monospace" font-weight="800" fill="url(#nsHead)">◈ NEURAL SHELL // پوسته مدل‌ها — جریان ویژگی به لبه</text>
  <circle cx="{W - 120}" cy="20" r="3.5" fill="#34d399"><animate attributeName="opacity" values="0.3;1;0.3" dur="1.4s" repeatCount="indefinite"/></circle>
  <text x="{W - 112}" y="24" font-size="9.5" font-family="ui-monospace,monospace" fill="#94a3b8">FEATURE EXTRACTION · LIVE</text>

  <!-- column labels -->
  <text x="20" y="40" font-size="8" font-family="ui-monospace,monospace" fill="#475569">MODEL INPUT</text>
  <text x="{core_x - 30:.0f}" y="40" font-size="8" font-family="ui-monospace,monospace" fill="#475569">CORE · SHELL</text>

  <!-- core glow + shell -->
  <circle cx="{core_x}" cy="{core_y}" r="{core_r + 24}" fill="url(#nsCore)"/>
  <g>
    <animateTransform attributeName="transform" type="rotate" from="0 {core_x} {core_y}" to="360 {core_x} {core_y}" dur="60s" repeatCount="indefinite"/>
    {''.join(shell)}
  </g>
  <circle cx="{core_x}" cy="{core_y}" r="{core_r}" fill="none" stroke="rgba(148,163,184,0.18)"/>
  <circle cx="{core_x}" cy="{core_y}" r="{core_r * 0.55:.0f}" fill="rgba(2,6,17,0.55)" stroke="rgba(245,158,11,0.35)"/>

  <!-- synapses + particles -->
  <g>{''.join(synapses)}</g>
  <g>{''.join(particles)}</g>

  <!-- feature nodes -->
  <g>{''.join(nodes)}</g>

  <!-- core readout -->
  <text x="{core_x}" y="{core_y - 4:.0f}" text-anchor="middle" font-family="ui-monospace,monospace" font-weight="800" font-size="30" fill="{score_color}">{score:+.0f}</text>
  <text x="{core_x}" y="{core_y + 15:.0f}" text-anchor="middle" font-size="9" fill="#cbd5e1">همگرایی زنده</text>

  <!-- bottom confidence bar -->
  <rect x="20" y="{H - 24}" width="{W - 40}" height="6" rx="3" fill="rgba(148,163,184,0.15)"/>
  <rect x="20" y="{H - 24}" width="{int((W - 40) * bar_pct / 100)}" height="6" rx="3" fill="url(#nsHead)">
    <animate attributeName="opacity" values="0.7;1;0.7" dur="2.2s" repeatCount="indefinite"/>
  </rect>
  <text x="20" y="{H - 28}" font-size="8" font-family="ui-monospace,monospace" fill="#64748b">SIGNED FLOW</text>
</svg>
</div>
"""


# Backward-compatible alias (older call sites used build_galaxy_svg).
build_galaxy_svg = build_neural_shell_svg


def _live_strip_impl(symbol: str, exchange: str, interval: str, dec: int, extra: dict | None = None) -> None:
    """
    Live ticker strip — built with Streamlit native layout (st.columns) so it
    re-renders safely inside `st.fragment`. Every value is computed BEFORE it is
    placed in a string, so there is never a format-specifier that depends on a
    runtime condition (that is what used to crash the previous version).
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
        st.caption("تا بستن کندل")


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


# ------------------------------------------------------------------ analysis image

def render_analysis_png(
    d: pd.DataFrame,
    plan: dict,
    levels: pd.DataFrame,
    score: float,
    symbol: str,
    exchange: str,
    interval: str,
    dec: int,
    bars: int = 120,
) -> bytes:
    """
    Build a downloadable annotated chart (PNG) from REAL candles: candlesticks +
    EMA20/50 + support/resistance + entry/stop/targets. Labels are in English so
    they render cleanly inside the image (matplotlib does not shape Persian text).
    """
    import io
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    pd_d = d.tail(bars).reset_index(drop=True)
    n = len(pd_d)

    fig, ax = plt.subplots(figsize=(13, 7), dpi=130)
    fig.patch.set_facecolor("#0b1220")
    ax.set_facecolor("#0b1220")

    opens = pd_d["open"].to_numpy()
    closes = pd_d["close"].to_numpy()
    highs = pd_d["high"].to_numpy()
    lows = pd_d["low"].to_numpy()

    for i in range(n):
        o, c, hi, lo = opens[i], closes[i], highs[i], lows[i]
        up = c >= o
        col = "#22c55e" if up else "#ef4444"
        ax.plot([i, i], [lo, hi], color=col, linewidth=0.8, zorder=2)
        body_h = max(abs(c - o), (highs.max() - lows.min()) * 0.0008)
        ax.add_patch(Rectangle((i - 0.32, min(o, c)), 0.64, body_h, color=col, zorder=3, linewidth=0))

    # EMAs
    if "ema20" in pd_d:
        ax.plot(range(n), pd_d["ema20"], color="#38bdf8", linewidth=1.1, zorder=4, label="EMA20")
    if "ema50" in pd_d:
        ax.plot(range(n), pd_d["ema50"], color="#f472b6", linewidth=1.1, zorder=4, label="EMA50")

    x_right = n - 1

    # support / resistance
    if levels is not None and not levels.empty:
        for _, lv in levels.iterrows():
            lvl = float(lv["سطح"])
            is_sup = "حمایت" in str(lv["نوع"])
            col = "#34d399" if is_sup else "#fb7185"
            tag = "S" if is_sup else "R"
            ax.axhline(lvl, color=col, linewidth=0.8, linestyle=":", alpha=0.65, zorder=1)
            ax.text(x_right + 0.5, lvl, f" {tag} {lvl:,.{dec}f}", color=col, fontsize=7.5,
                    va="center", ha="left", fontweight="bold")

    # entry / stop / targets
    ax.axhline(plan["entry"], color="#f59e0b", linewidth=1.6, zorder=5)
    ax.text(0, plan["entry"], f"ENTRY {plan['entry']:,.{dec}f} ", color="#0b1220", fontsize=8,
            va="center", ha="left", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", fc="#f59e0b", ec="none"))
    ax.axhline(plan["stop"], color="#ef4444", linewidth=1.3, linestyle="--", zorder=5)
    ax.text(0, plan["stop"], f"STOP {plan['stop']:,.{dec}f} ", color="#fff", fontsize=8,
            va="center", ha="left", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", fc="#ef4444", ec="none"))
    for i, (tp, rr) in enumerate(plan["targets"]):
        ax.axhline(tp, color="#38bdf8", linewidth=1.1, linestyle="--", zorder=5)
        ax.text(0, tp, f"TP{i + 1} {tp:,.{dec}f} ({rr}R) ", color="#0b1220", fontsize=8,
                va="center", ha="left", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.25", fc="#38bdf8", ec="none"))

    direction = "LONG" if plan["direction"].startswith("لانگ") else "SHORT"
    dir_col = "#34d399" if direction == "LONG" else "#fb7185"
    title = f"{symbol}  ·  {exchange}  ·  {interval}"
    ax.set_title(title, color="#e2e8f0", fontsize=14, fontweight="bold", loc="left", pad=28)
    ax.text(0.0, 1.015,
            f"Signal: {direction}   |   Confluence: {score:+.0f}   |   R:R 1:{plan['rr']}   |   "
            f"Confidence {plan['confidence']}%   |   ATR {plan['atr']:,.{dec}f}",
            transform=ax.transAxes, color=dir_col, fontsize=9.5, fontweight="bold", va="bottom")
    ax.text(0.999, 1.015, "NorthmanQuant · not financial advice",
            transform=ax.transAxes, color="#64748b", fontsize=8, va="bottom", ha="right")

    ax.grid(color="#1e293b", linewidth=0.5, alpha=0.5)
    ax.tick_params(colors="#64748b", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#1e293b")
    ax.set_xlim(-1, n + 6)
    ax.margins(y=0.05)
    ax.legend(loc="upper left", fontsize=8, facecolor="#0b1220", edgecolor="#1e293b", labelcolor="#cbd5e1")

    # x ticks = a handful of dates
    if "dt" in pd_d:
        step = max(1, n // 8)
        idxs = list(range(0, n, step))
        ax.set_xticks(idxs)
        ax.set_xticklabels([pd.to_datetime(pd_d["dt"].iloc[i]).strftime("%m/%d %H:%M") for i in idxs],
                           rotation=0, fontsize=7)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


# ------------------------------------------------------------------ image extraction (lite)

def extract_candles_from_image(img: Image.Image, max_dim: int = 1400) -> pd.DataFrame:
    """Extract normalized candles (0..100) from a chart screenshot by candle colors.

    Robust to real exchange / TradingView screenshots: it isolates the price pane
    from the volume pane, ignores the right-hand price axis and current-price
    marker box, and rejects non-candle noise by candle-width consistency.
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
    mask = (green | red) & (sat >= 15) & (mn <= 238)
    bull_mask = green.copy()

    # Ignore the right-hand price axis + current-price marker box (a big green
    # blob at the far right that would otherwise be read as a huge candle).
    right_cut = int(w * 0.055)
    if right_cut:
        mask[:, w - right_cut:] = False
        bull_mask[:, w - right_cut:] = False

    # Split the price pane from the volume pane. Volume bars form a dense band at
    # the bottom, usually separated by a near-empty horizontal gap. Keep only the
    # tallest contiguous block of "active" rows (the price pane) and drop the
    # volume band below it — otherwise the 0..100 scale gets crushed.
    row_count = mask.sum(axis=1)
    active = row_count > max(2, w * 0.004)
    runs: list[tuple[int, int]] = []
    y = 0
    while y < h:
        if active[y]:
            y0 = y
            while y < h and active[y]:
                y += 1
            runs.append((y0, y - 1))
        else:
            y += 1
    if runs:
        tallest = max(runs, key=lambda rr: rr[1] - rr[0])
        top, bot = tallest
        # merge any nearby run just above (wicks can create a small gap)
        for (ry0, ry1) in runs:
            if ry1 < top and (top - ry1) < (bot - top) * 0.25:
                top = ry0
        mask[bot + 1:, :] = False
        mask[:top, :] = False

    # Column clusters: a candle is a run of columns that each contain a vertical
    # colour run of at least MIN_RUN pixels (so thin EMA/grid lines are ignored).
    MIN_RUN = 4
    col_on = np.zeros(w, dtype=bool)
    for x in range(w):
        run = 0
        colm = mask[:, x]
        for y in range(h):
            run = run + 1 if colm[y] else 0
            if run >= MIN_RUN:
                col_on[x] = True
                break

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
    if len(clusters) < 8:
        return pd.DataFrame()

    # Keep only clusters whose width is consistent with the median candle width.
    widths = sorted(c[1] - c[0] + 1 for c in clusters)
    med = widths[len(widths) // 2]
    lo_w = max(1, int(med * 0.3))
    hi_w = max(med * 3, 6)
    clusters = [c for c in clusters if lo_w <= (c[1] - c[0] + 1) <= hi_w]
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
    import streamlit.components.v1 as components
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
        symbol_in = st.text_input("نماد", value="BTC-USDT", help="مثل BTC-USDT یا gramusdt · برای Lighter فقط BTC")
        exchange = st.selectbox("صرافی", EXCHANGES)
        interval = st.selectbox("تایم‌فریم", list(INTERVAL_MINUTES.keys()), index=1)
        live_on = st.checkbox("🔴 حالت زنده (قیمت هر ۵ ثانیه)", value=True)
        auto = st.checkbox("بازخوانی کامل خودکار (۶۰ ثانیه)", value=False)

    symbol = normalize_symbol(symbol_in, exchange)
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

    tab_live, tab_top, tab_news, tab_img, tab_docs = st.tabs(
        ["📊 تحلیل زنده", "🏆 برترین‌ها", "📰 اخبار", "🖼️ تصویر تحلیل", "📚 منابع داده"]
    )

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

            # Lighter-only extras (real fields from orderBookDetails)
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
                st.subheader("◈ پوسته مدل‌ها (Neural Shell) — زنده")
                # Rendered via components.html (iframe) because st.markdown strips
                # SVG/SMIL animations; the iframe keeps the live motion intact.
                components.html(
                    "<div style='background:#070d18;margin:0;padding:4px'>"
                    + build_neural_shell_svg(comp_table, score)
                    + "</div>",
                    height=380,
                )
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
        st.write(
            "نماد را وارد کن تا خودش از داده‌ی **واقعی** صرافی تحلیل کند و یک **تصویر چارت آماده** "
            "با نقاط ورود/حد ضرر/اهداف و سطوح حمایت و مقاومت بسازد — قابل دانلود و اشتراک‌گذاری."
        )

        ic1, ic2, ic3 = st.columns([1.3, 1, 1])
        with ic1:
            img_symbol_in = st.text_input("نماد برای تصویر", value=symbol_in, key="img_symbol",
                                          help="مثل BTC، ETH، SOL … · برای Lighter فقط نماد پایه")
        with ic2:
            img_exchange = st.selectbox("صرافی", EXCHANGES, index=EXCHANGES.index(exchange), key="img_exchange")
        with ic3:
            img_interval = st.selectbox("تایم‌فریم", list(INTERVAL_MINUTES.keys()),
                                        index=list(INTERVAL_MINUTES.keys()).index(interval), key="img_interval")

        make_img = st.button("🖼️ ساخت تصویر تحلیل", type="primary", use_container_width=True)

        if make_img:
            img_symbol = normalize_symbol(img_symbol_in, img_exchange)
            try:
                with st.spinner(f"در حال تحلیل {img_symbol} روی {img_exchange} …"):
                    idf = fetch_candles(img_exchange, img_symbol, img_interval)
                    idd = add_indicators(idf)
                    iscore_series, icomp = confluence(idd)
                    iscore = float(iscore_series.iloc[-1])
                    ilevels = swing_levels(idd)
                    iplan = make_plan(idd, iscore, ilevels)
                    iprice = float(idd["close"].iloc[-1])
                    idec = 2 if iprice >= 1000 else 4 if iprice >= 1 else 6
                    png = render_analysis_png(idd, iplan, ilevels, iscore, img_symbol, img_exchange, img_interval, idec)

                ilabel = "خرید قوی" if iscore > 40 else "خرید" if iscore > 12 else "خنثی" if iscore > -12 else "فروش" if iscore > -40 else "فروش قوی"
                st.success(f"تحلیل {img_symbol} آماده شد · قیمت {iprice:,.{idec}f} · همگرایی {iscore:+.0f} ({ilabel})")

                st.image(png, use_container_width=True)
                st.download_button(
                    "⬇️ دانلود تصویر (PNG)",
                    data=png,
                    file_name=f"{img_symbol}_{img_interval}_northmanquant.png",
                    mime="image/png",
                    use_container_width=True,
                )

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("جهت", iplan["direction"])
                m2.metric("ورود", f"{iplan['entry']:,.{idec}f}")
                m3.metric("حد ضرر", f"{iplan['stop']:,.{idec}f}")
                m4.metric("R:R / اطمینان", f"1:{iplan['rr']} · {iplan['confidence']}٪")
                for i, (t_price, t_rr) in enumerate(iplan["targets"]):
                    st.write(f"🎯 هدف {i + 1}: **{t_price:,.{idec}f}** ({t_rr}R)")

                if not ilevels.empty:
                    st.subheader("🧱 حمایت و مقاومت")
                    show = ilevels.copy()
                    show["سطح"] = show["سطح"].map(lambda v: f"{v:,.{idec}f}")
                    st.dataframe(show, use_container_width=True, hide_index=True)
                st.caption("برچسب‌های روی تصویر انگلیسی هستند (ENTRY/STOP/TP/S/R) تا در همه‌ی سیستم‌ها درست دیده شوند. این ابزار توصیه‌ی سرمایه‌گذاری نیست.")
            except Exception as e:  # noqa: BLE001
                st.error(f"ساخت تصویر ممکن نشد: {e}")
                st.info("نماد را مثل BTC یا ETH بنویس؛ اگر صرافی مسدود است، OKX یا KuCoin یا Lighter را امتحان کن.")
        else:
            st.info("یک نماد وارد کن و دکمه‌ی «ساخت تصویر تحلیل» را بزن.")

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
- Bybit و OKX لیست کندل را از جدید به قدیم می‌دهند؛ کد قبل از استفاده مرتب‌سازی می‌کند.
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
