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

# Extra exchanges accessible through CCXT (100+ venues, public data, no keys).
# Users can also type ANY ccxt exchange id (e.g. "kraken", "gate", "htx").
CCXT_SUGGESTED = ["XT", "LBank", "Kraken", "Coinbase", "Gate", "MEXC", "Bitget", "Kucoin",
                  "Gemini", "Bitstamp", "Bitfinex", "Huobi/HTX", "Crypto.com", "Upbit"]
CCXT_TF = {"15min": "15m", "1hour": "1h", "4hour": "4h", "1day": "1d", "1week": "1w"}

EXCHANGE_DOCS = {
    "KuCoin": "https://www.kucoin.com/docs/rest/spot/market-data/get-klines",
    "OKX": "https://www.okx.com/docs-v5/en/#order-book-trading-market-data",
    "Binance": "https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints",
    "Bybit": "https://bybit-exchange.github.io/docs/v5/market/kline",
    "Lighter": "https://apidocs.lighter.xyz/reference/candles",
    "XT": "https://doc.xt.com/",
    "LBank": "https://www.lbank.com/en-US/docs/index.html",
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

# ------------------------------------------------------------------ themes

# Each theme sets the page background, surface, text and accent colours. Users
# pick one from the sidebar; a custom theme lets them choose any colours.
THEMES = {
    "🌌 شب کهکشانی": {"bg": "#050a14", "bg2": "#0e1424", "surface": "#111c2e",
                       "text": "#e2e8f0", "accent": "#38bdf8", "grad": "linear-gradient(135deg,#0b1220,#131d33)"},
    "🌊 اقیانوس عمیق": {"bg": "#071a24", "bg2": "#0a2634", "surface": "#0e3042",
                        "text": "#d7f0f7", "accent": "#22d3ee", "grad": "linear-gradient(135deg,#071a24,#0d3344)"},
    "🌿 جنگل تاریک": {"bg": "#0a140d", "bg2": "#0f2015", "surface": "#13291b",
                      "text": "#dcefe0", "accent": "#34d399", "grad": "linear-gradient(135deg,#0a140d,#102a19)"},
    "🔥 غروب آتشین": {"bg": "#1a0d0a", "bg2": "#2a1410", "surface": "#331a14",
                      "text": "#ffe4d6", "accent": "#fb923c", "grad": "linear-gradient(135deg,#1a0d0a,#3a1c12)"},
    "👑 سلطنتی بنفش": {"bg": "#120a1f", "bg2": "#1c1030", "surface": "#241640",
                       "text": "#ebe0ff", "accent": "#a855f7", "grad": "linear-gradient(135deg,#120a1f,#241640)"},
    "☀️ روشن مینیمال": {"bg": "#f3f5f9", "bg2": "#ffffff", "surface": "#ffffff",
                        "text": "#0f172a", "accent": "#2563eb", "grad": "linear-gradient(135deg,#eef2f8,#ffffff)"},
    "🖤 تک‌رنگ تیره": {"bg": "#0a0a0a", "bg2": "#141414", "surface": "#1a1a1a",
                       "text": "#e5e5e5", "accent": "#9ca3af", "grad": "linear-gradient(135deg,#0a0a0a,#1a1a1a)"},
}


def theme_css(t: dict, bg_image: str = "") -> str:
    """Build a <style> block that re-skins the whole Streamlit app for a theme."""
    bg_layer = (
        f"linear-gradient(rgba(0,0,0,0.55),rgba(0,0,0,0.70)), url('{bg_image}')"
        if bg_image else t["grad"]
    )
    light = t["text"].lower() in ("#0f172a", "#111827", "#1e293b")
    sidebar_bg = t["bg2"]
    return f"""
<style>
.stApp {{
    background: {bg_layer};
    background-size: cover;
    background-attachment: fixed;
    color: {t['text']};
}}
section[data-testid="stSidebar"] > div {{ background: {sidebar_bg}; }}
section[data-testid="stSidebar"] * {{ color: {t['text']} !important; }}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp label,
.stApp span, .stApp div[data-testid="stMarkdownContainer"] {{ color: {t['text']}; }}
[data-testid="stMetric"] {{
    background: {t['surface']}; border: 1px solid rgba(148,163,184,0.18);
    border-radius: 14px; padding: 12px 14px;
}}
[data-testid="stMetricValue"] {{ color: {t['accent']} !important; }}
div[data-testid="stExpander"] details {{
    background: {t['surface']}; border: 1px solid rgba(148,163,184,0.18);
    border-radius: 12px;
}}
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; }}
.stTabs [data-baseweb="tab"] {{
    background: {t['surface']}; border-radius: 10px 10px 0 0; padding: 6px 14px;
}}
.stTabs [aria-selected="true"] {{ border-bottom: 2px solid {t['accent']}; }}
.stButton > button, .stDownloadButton > button {{
    border: 1px solid {t['accent']}55; border-radius: 10px;
}}
.stDataFrame {{ border-radius: 12px; overflow: hidden; }}
a {{ color: {t['accent']} !important; }}
</style>
"""


def share_bar(title: str, text: str, app_url: str = "") -> str:
    """A compact share/save row: Telegram, WhatsApp, X/Twitter, and copy.

    `text` is the message body (built from live data). Returns an HTML string to
    render via components.html so the buttons work inside the iframe.
    """
    import urllib.parse as _u

    full = f"{title}\n\n{text}"
    if app_url:
        full += f"\n\n{app_url}"
    enc = _u.quote(full)
    enc_url = _u.quote(app_url or "https://streamlit.io")
    tg = f"https://t.me/share/url?url={enc_url}&text={enc}"
    wa = f"https://wa.me/?text={enc}"
    tw = f"https://twitter.com/intent/tweet?text={enc}"
    btn = ("display:inline-flex;align-items:center;gap:6px;padding:7px 12px;border-radius:9px;"
           "font:600 12px ui-monospace,monospace;text-decoration:none;color:#fff;margin:2px")
    js_text = full.replace("\\", "\\\\").replace("`", "\\`").replace("</", "<\\/")
    return f"""
<div dir="rtl" style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;
     background:rgba(148,163,184,0.06);border:1px solid rgba(148,163,184,0.15);
     border-radius:12px;padding:8px 10px">
  <span style="font:700 12px ui-monospace,monospace;color:#94a3b8;margin-left:4px">اشتراک‌گذاری:</span>
  <a href="{tg}" target="_blank" style="{btn};background:#229ED9">تلگرام ✈</a>
  <a href="{wa}" target="_blank" style="{btn};background:#25D366">واتساپ</a>
  <a href="{tw}" target="_blank" style="{btn};background:#1d9bf0">توییتر/X</a>
   <button onclick="navigator.clipboard.writeText(`{js_text}`).then(()=>{{this.innerText='کپی شد ✓'}})"
     style="{btn};background:#475569;border:none;cursor:pointer">کپی متن 📋</button>
 </div>
 """


def floating_share(title: str, text: str, app_url: str = "") -> str:
    """A DRAGGABLE floating action button injected into the parent page.

    Clicking it opens a compact panel with Telegram/WhatsApp/X/copy/save. The
    button position is remembered via localStorage. Rendered via components.html
    whose script writes into window.parent.document (same-origin) so the FAB
    floats over the whole Streamlit app, not inside the little iframe.
    """
    import json as _j

    full = f"{title}\n\n{text}" + (f"\n\n{app_url}" if app_url else "")
    payload = _j.dumps({
        "title": title,
        "msg": full,
        "url": app_url or "https://streamlit.io",
    })
    return f"""
<script>
(function() {{
  const D = {payload};
  const doc = window.parent.document;
  const enc = encodeURIComponent;
  const old = doc.getElementById("nq-fab-root");
  if (old) old.remove();

  const root = doc.createElement("div");
  root.id = "nq-fab-root";
  root.style.cssText = "position:fixed;z-index:999999;bottom:90px;left:24px;font-family:ui-monospace,monospace";
  const saved = localStorage.getItem("nqFabPos");
  if (saved) {{ try {{ const p = JSON.parse(saved); root.style.left=p.x+"px"; root.style.top=p.y+"px"; root.style.bottom="auto"; }} catch(e){{}} }}

  // panel
  const panel = doc.createElement("div");
  panel.style.cssText = "display:none;margin-bottom:10px;background:#0f172a;border:1px solid #334155;border-radius:14px;padding:12px;width:230px;box-shadow:0 12px 40px rgba(0,0,0,.5)";
  const mk = (bg,label,href) => `<a href="${{href}}" target="_blank" style="display:block;background:${{bg}};color:#fff;text-decoration:none;border-radius:9px;padding:9px 12px;margin:5px 0;font-size:13px;font-weight:700;text-align:center">${{label}}</a>`;
  panel.innerHTML =
    '<div style="color:#94a3b8;font-size:12px;font-weight:700;margin-bottom:6px;text-align:right">اشتراک‌گذاری تحلیل</div>'
    + mk("#229ED9","تلگرام ✈","https://t.me/share/url?url="+enc(D.url)+"&text="+enc(D.msg))
    + mk("#25D366","واتساپ","https://wa.me/?text="+enc(D.msg))
    + mk("#1d9bf0","توییتر / X","https://twitter.com/intent/tweet?text="+enc(D.msg))
    + '<button id="nq-copy" style="width:100%;background:#475569;color:#fff;border:none;border-radius:9px;padding:9px;margin:5px 0;font-size:13px;font-weight:700;cursor:pointer">کپی متن 📋</button>'
    + '<button id="nq-save" style="width:100%;background:#0ea5e9;color:#fff;border:none;border-radius:9px;padding:9px;margin:5px 0;font-size:13px;font-weight:700;cursor:pointer">ذخیره فایل 💾</button>';

  // button
  const fab = doc.createElement("div");
  fab.textContent = "🔗";
  fab.style.cssText = "width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#38bdf8,#22c55e);display:flex;align-items:center;justify-content:center;font-size:24px;cursor:grab;box-shadow:0 8px 24px rgba(0,0,0,.5);user-select:none";

  root.appendChild(panel);
  root.appendChild(fab);
  doc.body.appendChild(root);

  // toggle panel (only when it's a click, not a drag)
  let moved = false;
  fab.addEventListener("click", () => {{
    if (moved) {{ moved = false; return; }}
    panel.style.display = panel.style.display === "none" ? "block" : "none";
  }});

  // copy + save
  panel.querySelector("#nq-copy").onclick = function() {{
    navigator.clipboard.writeText(D.msg).then(()=>{{ this.textContent = "کپی شد ✓"; }});
  }};
  panel.querySelector("#nq-save").onclick = function() {{
    const blob = new Blob([D.msg], {{type:"text/plain;charset=utf-8"}});
    const a = doc.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "northmanquant_analysis.txt";
    a.click();
  }};

  // drag
  let dragging = false, sx=0, sy=0, ox=0, oy=0;
  fab.addEventListener("mousedown", (e) => {{
    dragging = true; moved = false; fab.style.cursor = "grabbing";
    const r = root.getBoundingClientRect(); ox = r.left; oy = r.top; sx = e.clientX; sy = e.clientY;
    e.preventDefault();
  }});
  doc.addEventListener("mousemove", (e) => {{
    if (!dragging) return;
    const nx = ox + (e.clientX - sx), ny = oy + (e.clientY - sy);
    if (Math.abs(e.clientX-sx) + Math.abs(e.clientY-sy) > 4) moved = true;
    root.style.left = nx + "px"; root.style.top = ny + "px"; root.style.bottom = "auto";
  }});
  doc.addEventListener("mouseup", () => {{
    if (!dragging) return;
    dragging = false; fab.style.cursor = "grab";
    const r = root.getBoundingClientRect();
    localStorage.setItem("nqFabPos", JSON.stringify({{x:r.left, y:r.top}}));
  }});
}})();
</script>
"""


# ------------------------------------------------------------------ community board

COMMUNITY_FILE = "community_analyses.json"


def load_community() -> list[dict]:
    """Read the shared analysis board (JSON file on the running instance)."""
    import json
    import os
    if not os.path.exists(COMMUNITY_FILE):
        return []
    try:
        with open(COMMUNITY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_community(entry: dict) -> None:
    """Append one analysis to the shared board (newest first, cap 200)."""
    import json
    rows = load_community()
    rows.insert(0, entry)
    rows = rows[:200]
    try:
        with open(COMMUNITY_FILE, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
    except Exception:
        pass


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
    NEURAL SHELL — live animated feature-extraction dashboard (pure SVG + SMIL).

    Three panels, light theme:
      • LEFT   — orbiting particle cloud around a dark core showing EDGE PROBABILITY.
      • MIDDLE — feature dots → dashed flows → CONFLUENCE node → EDGE node.
      • RIGHT  — the 9 features with p(up) %, value, and an animated strength bar.
    Rendered inside components.html (iframe) so the animations are not stripped.
    """
    import math as _m

    rows = []
    if comp_table is not None and not comp_table.empty and "امتیاز" in comp_table.columns:
        for _, rr in comp_table.iterrows():
            rows.append((str(rr["اندیکاتور"]), str(rr.get("مقدار", "")), float(rr["امتیاز"])))
    if not rows:
        rows = [("—", "", 0.0)] * 9
    n = len(rows)

    W, H = 1130, 360
    GREEN, RED, GREY = "#16a34a", "#ef4444", "#94a3b8"

    def tone(v: float) -> str:
        return GREEN if v > 0.12 else RED if v < -0.12 else GREY

    def p_up(v: float) -> int:
        return int(round((v + 1) / 2 * 100))

    # -------------------------------------------------- LEFT: orbital cloud
    lcx, lcy = 150.0, 190.0
    rings = "".join(
        f'<ellipse cx="{lcx}" cy="{lcy}" rx="{r}" ry="{r * 0.92:.0f}" fill="none" '
        f'stroke="#e2e8f0" stroke-width="1"/>'
        for r in (40, 70, 100, 128)
    )
    edge_prob = max(1, min(99, (score + 100) / 2))
    greens = sum(1 for _, _, v in rows if v > 0.12)
    green_ratio = greens / max(1, n)
    cloud = []
    for i in range(130):
        h1 = (np.sin(i * 127.1) * 43758.5453) % 1
        h2 = (np.sin(i * 311.7) * 12543.123) % 1
        h3 = (np.sin(i * 74.7) * 998.5) % 1
        ang = h1 * 2 * _m.pi
        ring = 20 + h2 * 118
        x = lcx + ring * _m.cos(ang)
        y = lcy + ring * _m.sin(ang) * 0.92
        is_green = h3 < (0.35 + green_ratio * 0.5)
        c = GREEN if is_green else "#cbd5e1"
        rad = 1.0 + h2 * 2.0
        dur = 2.0 + (i % 9) * 0.5
        cloud.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad:.1f}" fill="{c}" opacity="0.8">'
            f'<animate attributeName="opacity" values="0.15;0.85;0.15" dur="{dur:.1f}s" '
            f'begin="{(i % 10) * 0.2:.1f}s" repeatCount="indefinite"/></circle>'
        )
    left = (
        f'<g>'
        f'{rings}'
        f'<g><animateTransform attributeName="transform" type="rotate" '
        f'from="0 {lcx} {lcy}" to="360 {lcx} {lcy}" dur="80s" repeatCount="indefinite"/>{"".join(cloud)}</g>'
        f'<g><animateTransform attributeName="transform" type="rotate" '
        f'from="360 {lcx} {lcy}" to="0 {lcx} {lcy}" dur="120s" repeatCount="indefinite"/>'
        + "".join(
            f'<circle cx="{lcx + (55 + (j % 3) * 22) * _m.cos(j):.1f}" '
            f'cy="{lcy + (55 + (j % 3) * 22) * _m.sin(j) * 0.9:.1f}" r="2.2" fill="{GREEN}" opacity="0.6"/>'
            for j in range(10)
        )
        + f'</g>'
        f'<circle cx="{lcx}" cy="{lcy}" r="46" fill="#0b1220"/>'
        f'<text x="{lcx}" y="{lcy - 2}" text-anchor="middle" font-family="ui-monospace,monospace" '
        f'font-weight="800" font-size="24" fill="{GREEN}">{edge_prob:.1f}%</text>'
        f'<text x="{lcx}" y="{lcy + 14}" text-anchor="middle" font-size="8" '
        f'fill="#94a3b8" font-family="ui-monospace,monospace">EDGE PROBABILITY</text>'
        f'</g>'
    )

    # -------------------------------------------------- MIDDLE: feature flow
    fx = 330.0          # feature dots column
    conf_x, conf_y = 595.0, 190.0
    edge_x = 705.0
    top, bot = 50.0, 330.0
    gap = (bot - top) / max(1, n - 1)
    flows, fdots, fparts = [], [], []
    for i, (label, _val, v) in enumerate(rows):
        y = top + i * gap
        color = tone(v)
        strength = min(1.0, abs(v))
        c1x, c1y = fx + 120, y
        c2x, c2y = conf_x - 90, conf_y + (y - conf_y) * 0.2
        path = f"M {fx:.1f} {y:.1f} C {c1x:.1f} {c1y:.1f} {c2x:.1f} {c2y:.1f} {conf_x - 8:.1f} {conf_y:.1f}"
        pid = f"nsflow{i}"
        dash = "6 5" if v >= 0 else "3 4"
        flows.append(
            f'<path id="{pid}" d="{path}" fill="none" stroke="{color}" '
            f'stroke-width="{0.8 + strength * 2.0:.2f}" stroke-opacity="{0.25 + strength * 0.5:.2f}" '
            f'stroke-dasharray="{dash}"/>'
        )
        dur = 2.4 + (i % 5) * 0.5
        fparts.append(
            f'<circle r="{2.0 + strength * 1.6:.1f}" fill="{color}">'
            f'<animateMotion dur="{dur:.1f}s" begin="{i * 0.2:.2f}s" repeatCount="indefinite">'
            f'<mpath href="#{pid}"/></animateMotion></circle>'
        )
        fdots.append(
            f'<circle cx="{fx:.1f}" cy="{y:.1f}" r="4.5" fill="{color}">'
            f'<animate attributeName="r" values="3.5;5.5;3.5" dur="{1.8 + (i % 4) * 0.4:.1f}s" '
            f'repeatCount="indefinite"/></circle>'
        )
    # confluence node -> edge node
    conf_to_edge = (
        f'<path id="nsEdge" d="M {conf_x + 10:.1f} {conf_y:.1f} L {edge_x - 10:.1f} {conf_y:.1f}" '
        f'fill="none" stroke="{GREEN}" stroke-width="2" stroke-dasharray="6 5" stroke-opacity="0.7"/>'
        f'<circle r="3" fill="{GREEN}"><animateMotion dur="1.8s" repeatCount="indefinite">'
        f'<mpath href="#nsEdge"/></animateMotion></circle>'
    )
    conf_col = GREEN if score >= 0 else RED
    middle = (
        f'<g>{"".join(flows)}</g>'
        f'<g>{"".join(fparts)}</g>'
        f'<g>{"".join(fdots)}</g>'
        f'{conf_to_edge}'
        f'<circle cx="{conf_x}" cy="{conf_y}" r="11" fill="#0b1220" stroke="{conf_col}" stroke-width="2">'
        f'<animate attributeName="stroke-opacity" values="0.4;1;0.4" dur="1.6s" repeatCount="indefinite"/></circle>'
        f'<text x="{conf_x}" y="{conf_y + 26}" text-anchor="middle" font-size="8" '
        f'fill="#64748b" font-family="ui-monospace,monospace">CONFLUENCE</text>'
        f'<circle cx="{edge_x}" cy="{conf_y}" r="8" fill="{conf_col}"/>'
        f'<text x="{edge_x}" y="{conf_y + 24}" text-anchor="middle" font-size="8" '
        f'fill="#64748b" font-family="ui-monospace,monospace">EDGE</text>'
    )

    # -------------------------------------------------- RIGHT: feature list
    rx0, rx1 = 745.0, 1118.0
    rtop = 42.0
    rgap = (H - 70 - rtop) / max(1, n - 1)
    right_rows = []
    for i, (label, val, v) in enumerate(rows):
        y = rtop + i * rgap
        color = tone(v)
        pct = p_up(v)
        bar_w = (rx1 - rx0) * (pct / 100.0)
        # RTL: Persian label on the right, p(up)/value on the left
        meta = f"p(up) {pct}%" + (f" · {val}" if val else "")
        right_rows.append(
            f'<g>'
            f'<text x="{rx1}" y="{y}" text-anchor="end" font-size="10.5" fill="#334155" '
            f'font-weight="600">{label}</text>'
            f'<text x="{rx0}" y="{y}" text-anchor="start" font-size="9" fill="#64748b" '
            f'font-family="ui-monospace,monospace">{meta}</text>'
            f'<rect x="{rx0}" y="{y + 6:.1f}" width="{rx1 - rx0:.0f}" height="4" rx="2" fill="#e2e8f0"/>'
            f'<rect x="{rx0}" y="{y + 6:.1f}" width="0" height="4" rx="2" fill="{color}">'
            f'<animate attributeName="width" values="0;{bar_w:.0f}" dur="1.1s" '
            f'begin="{i * 0.08:.2f}s" fill="freeze"/></rect>'
            f'</g>'
        )

    return (
        '<div style="display:flex;justify-content:center">'
        f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:1130px" '
        f'role="img" aria-label="neural shell feature extraction">'
        f'<rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="#f6f8fb"/>'
        # header
        f'<text x="18" y="22" font-size="12" font-family="ui-monospace,monospace" '
        f'font-weight="800" fill="#475569" letter-spacing="1">FEATURE EXTRACTION · LIVE</text>'
        f'<circle cx="212" cy="18" r="3.3" fill="{GREEN}">'
        f'<animate attributeName="opacity" values="0.3;1;0.3" dur="1.3s" repeatCount="indefinite"/></circle>'
        f'<text x="{W - 18}" y="22" text-anchor="end" font-size="12" '
        f'font-family="ui-monospace,monospace" font-weight="800" fill="#334155">'
        f'◈ NEURAL SHELL // پوسته مدل‌ها — جریان ویژگی به لبه</text>'
        # vertical dividers between panels
        f'<line x1="292" y1="40" x2="292" y2="{H - 16}" stroke="#e5e9f0" stroke-width="1"/>'
        f'<line x1="730" y1="40" x2="730" y2="{H - 16}" stroke="#e5e9f0" stroke-width="1"/>'
        f'{left}{middle}{"".join(right_rows)}'
        '</svg></div>'
    )


# Backward-compatible alias (older call sites used build_galaxy_svg).
build_galaxy_svg = build_neural_shell_svg


# ------------------------------------------------------------------ the agents

# Each "agent" is a trading persona built from one confluence component. We score
# it on the real series, run a tiny per-bar backtest, and render a live card.
AGENTS = [
    {"key": "روند EMA50", "name": "سوار روند", "en": "TREND RIDER", "tag": "TR", "color": "#0ea5e9"},
    {"key": "مومنتوم", "name": "مومنتوم", "en": "MOMENTUM", "tag": "MO", "color": "#8b5cf6"},
    {"key": "بازگشت به میانگین", "name": "بازگشت به میانگین", "en": "MEAN REV", "tag": "MR", "color": "#ec4899"},
    {"key": "شکست کانال", "name": "شکست کانال", "en": "BREAKOUT", "tag": "BO", "color": "#f59e0b"},
    {"key": "سوپرترند", "name": "سوپرترند", "en": "SUPERTREND", "tag": "ST", "color": "#10b981"},
    {"key": "جریان پول", "name": "جریان پول", "en": "FLOW", "tag": "FL", "color": "#f97316"},
]


def _agent_signals(d: pd.DataFrame) -> dict:
    """Per-bar directional signal (-1/0/+1) for each agent, from real indicators."""
    c = d["close"]
    out = {}
    # Trend rider: price vs EMA50 slope
    out["روند EMA50"] = np.sign((c - d["ema50"]).fillna(0)).to_numpy()
    # Momentum: MACD histogram sign
    out["مومنتوم"] = np.sign(d["macd_hist"].fillna(0)).to_numpy()
    # Mean reversion: fade RSI extremes (buy low, sell high) -> opposite of (rsi-50)
    out["بازگشت به میانگین"] = np.where(d["rsi"] < 42, 1, np.where(d["rsi"] > 58, -1, 0))
    # Breakout: close above/below Bollinger bands
    out["شکست کانال"] = np.where(c > d["bb_up"], 1, np.where(c < d["bb_lo"], -1, 0))
    # Supertrend direction
    out["سوپرترند"] = d["supertrend_dir"].fillna(0).to_numpy()
    # Flow: CMF sign
    out["جریان پول"] = np.sign(d["cmf"].fillna(0)).to_numpy()
    return out


def compute_agents(d: pd.DataFrame) -> list[dict]:
    """Backtest each agent on the loaded candles and return live card stats."""
    c = d["close"].to_numpy()
    ret = np.zeros(len(c))
    ret[1:] = (c[1:] - c[:-1]) / c[:-1]  # next-bar return applied to prev signal
    sigs = _agent_signals(d)

    cards = []
    for a in AGENTS:
        sig = np.asarray(sigs[a["key"]], dtype=float)
        # strategy return: yesterday's signal * today's return
        strat = np.zeros(len(c))
        strat[1:] = sig[:-1] * ret[1:]
        equity = np.cumprod(1 + strat)
        total = (equity[-1] - 1) * 100 if len(equity) else 0.0

        # trades = sign changes
        changes = np.where(np.abs(np.diff(sig)) > 0)[0]
        trades = int(len(changes))
        wins = strat[strat > 0]
        losses = strat[strat < 0]
        win_rate = (len(wins) / max(1, len(wins) + len(losses))) * 100
        gross_win = wins.sum()
        gross_loss = -losses.sum()
        pf = (gross_win / gross_loss) if gross_loss > 1e-9 else (gross_win if gross_win > 0 else 0.0)
        # max drawdown of equity
        peak = np.maximum.accumulate(equity) if len(equity) else np.array([1.0])
        dd = float(((peak - equity) / peak).max() * 100) if len(equity) else 0.0
        last_sig = sig[-1] if len(sig) else 0
        state = "LONG" if last_sig > 0 else "SHORT" if last_sig < 0 else "FLAT"

        spark = equity[-40:] if len(equity) >= 2 else np.array([1.0, 1.0])
        cards.append({
            **a,
            "total": total,
            "pf": round(float(pf), 2),
            "trades": trades,
            "win": int(round(win_rate)),
            "dd": round(dd, 2),
            "state": state,
            "spark": spark,
        })
    return cards


def build_agents_svg(cards: list[dict], fee: float = 0.06) -> str:
    """Live 'THE AGENTS' grid — big, well-spaced cards (3 columns × N rows)."""
    ncols = 3
    nrows = (len(cards) + ncols - 1) // ncols
    cw, ch = 356, 190          # bigger cards
    gx, gy = 22, 22            # real gaps between cards
    mx, my_top = 20, 52        # outer margins (top leaves room for header)
    W = mx * 2 + ncols * cw + (ncols - 1) * gx
    H = my_top + nrows * ch + (nrows - 1) * gy + 18

    def spark_path(vals, x0, y0, w, h):
        vals = np.asarray(vals, dtype=float)
        lo, hi = float(vals.min()), float(vals.max())
        rng = (hi - lo) or 1.0
        pts = []
        for i, v in enumerate(vals):
            x = x0 + (i / (len(vals) - 1)) * w
            y = y0 + h - (v - lo) / rng * h
            pts.append(f"{x:.1f},{y:.1f}")
        return "M" + " L".join(pts)

    cards_svg = []
    for i, c in enumerate(cards):
        col = i % ncols
        row = i // ncols
        x = mx + col * (cw + gx)
        y = my_top + row * (ch + gy)
        up = c["total"] >= 0
        line_col = "#16a34a" if up else "#ef4444"
        sign = "+" if up else "−"
        sp = spark_path(c["spark"], x + 22, y + 74, cw - 44, 54)
        area = sp + f' L{x + cw - 22:.1f},{y + 128:.1f} L{x + 22:.1f},{y + 128:.1f} Z'
        state_col = {"LONG": "#16a34a", "SHORT": "#ef4444", "FLAT": "#94a3b8"}[c["state"]]
        grad_id = f"ag{i}"
        cards_svg.append(
            f'<g>'
            f'<defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{line_col}" stop-opacity="0.18"/>'
            f'<stop offset="100%" stop-color="{line_col}" stop-opacity="0"/></linearGradient></defs>'
            f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="14" fill="#fff" stroke="#e5e9f0" stroke-width="1.5"/>'
            # header: badge (left) · name + EN (right, RTL)
            f'<circle cx="{x + 28}" cy="{y + 30}" r="16" fill="{c["color"]}"/>'
            f'<text x="{x + 28}" y="{y + 35}" text-anchor="middle" font-size="11" font-weight="800" fill="#fff" font-family="ui-monospace,monospace">{c["tag"]}</text>'
            f'<text x="{x + cw - 18}" y="{y + 28}" text-anchor="end" font-size="16" font-weight="800" fill="#334155">{c["name"]}</text>'
            f'<text x="{x + cw - 18}" y="{y + 42}" text-anchor="end" font-size="9" fill="#94a3b8" font-family="ui-monospace,monospace">{c["en"]}</text>'
            # big return %
            f'<text x="{x + cw - 18}" y="{y + 74}" text-anchor="end" font-size="34" font-weight="800" '
            f'fill="{line_col}" font-family="ui-monospace,monospace">{sign}{abs(c["total"]):.2f}%</text>'
            # sparkline (area + line + moving dot)
            f'<path d="{area}" fill="url(#{grad_id})" stroke="none"/>'
            f'<path d="{sp}" fill="none" stroke="{line_col}" stroke-width="2" opacity="0.95"/>'
            f'<circle r="3.2" fill="{line_col}"><animateMotion dur="3.2s" repeatCount="indefinite" '
            f'path="{sp.replace("M", "").replace(" L", " ")}" keyPoints="0;1" keyTimes="0;1" calcMode="linear"/>'
            f'<animate attributeName="opacity" values="0;1;1;0" dur="3.2s" repeatCount="indefinite"/></circle>'
            # divider
            f'<line x1="{x + 18}" y1="{y + 140}" x2="{x + cw - 18}" y2="{y + 140}" stroke="#eef2f7" stroke-width="1"/>'
            # stats row
            f'<text x="{x + 22}" y="{y + 160}" font-size="11" fill="#64748b" font-family="ui-monospace,monospace">PF {c["pf"]}</text>'
            f'<text x="{x + cw * 0.46:.0f}" y="{y + 160}" font-size="11" fill="#64748b" font-family="ui-monospace,monospace">TRD {c["trades"]}</text>'
            f'<text x="{x + cw - 22}" y="{y + 160}" text-anchor="end" font-size="11" fill="#64748b" font-family="ui-monospace,monospace">WIN {c["win"]}%</text>'
            # footer: state chip + DD
            f'<rect x="{x + 20}" y="{y + 168}" width="60" height="18" rx="5" fill="{state_col}" opacity="0.14"/>'
            f'<text x="{x + 50}" y="{y + 181}" text-anchor="middle" font-size="10" font-weight="800" fill="{state_col}" font-family="ui-monospace,monospace">{c["state"]}</text>'
            f'<text x="{x + cw - 22}" y="{y + 181}" text-anchor="end" font-size="10" fill="#94a3b8" font-family="ui-monospace,monospace">DD {c["dd"]}%</text>'
            f'</g>'
        )

    return (
        '<div style="display:flex;justify-content:center">'
        f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:{W}px" role="img" aria-label="the agents">'
        f'<rect x="0" y="0" width="{W}" height="{H}" rx="14" fill="#f6f8fb"/>'
        f'<text x="20" y="30" font-size="14" font-family="ui-monospace,monospace" font-weight="800" '
        f'fill="#475569" letter-spacing="0.5">◈ THE AGENTS // دفتر ایجنت‌ها — بک‌تست زنده روی داده‌ی فعلی</text>'
        f'<circle cx="{W - 180}" cy="26" r="4" fill="#16a34a"><animate attributeName="opacity" values="0.3;1;0.3" dur="1.3s" repeatCount="indefinite"/></circle>'
        f'<text x="{W - 20}" y="30" text-anchor="end" font-size="12" font-family="ui-monospace,monospace" '
        f'fill="#94a3b8">کارمزد {fee:.2f}٪ لحاظ شده</text>'
        + "".join(cards_svg) +
        '</svg></div>'
    )


def build_edge_matrix_svg(d: pd.DataFrame, score_series: pd.Series) -> str:
    """
    EDGE MATRIX — scatter of (confluence score) vs (next-bar return) over the
    loaded candles, with a least-squares regression line. Shows whether the
    model's signal actually precedes profitable moves (positive correlation).
    """
    c = d["close"].to_numpy()
    s = score_series.to_numpy(dtype=float)
    fwd = np.full(len(c), np.nan)
    fwd[:-1] = (c[1:] - c[:-1]) / c[:-1] * 100  # next-bar % return
    mask = np.isfinite(fwd) & np.isfinite(s)
    xs, ys = s[mask], fwd[mask]
    if len(xs) > 160:
        idx = np.linspace(0, len(xs) - 1, 160).astype(int)
        xs, ys = xs[idx], ys[idx]
    n = len(xs)
    if n < 5:
        return '<div style="color:#94a3b8;font-family:ui-monospace,monospace;font-size:12px">داده کافی نیست</div>'

    W, H = 1130, 560
    pad_l, pad_r, pad_t, pad_b = 64, 30, 60, 60
    pw, ph = W - pad_l - pad_r, H - pad_t - pad_b

    x_min, x_max = -100.0, 100.0
    y_abs = max(1e-6, float(np.percentile(np.abs(ys), 95)))
    y_min, y_max = -y_abs, y_abs

    def X(v):
        return pad_l + (v - x_min) / (x_max - x_min) * pw

    def Y(v):
        v = max(y_min, min(y_max, v))
        return pad_t + (1 - (v - y_min) / (y_max - y_min)) * ph

    # correlation + regression
    if np.std(xs) > 1e-9 and np.std(ys) > 1e-9:
        corr = float(np.corrcoef(xs, ys)[0, 1])
        b1 = float(np.polyfit(xs, ys, 1)[0])
        b0 = float(np.polyfit(xs, ys, 1)[1])
    else:
        corr, b1, b0 = 0.0, 0.0, 0.0

    zero_x = X(0)
    zero_y = Y(0)

    # gridlines + y tick labels
    grid = []
    for gy in (-y_abs, -y_abs / 2, 0, y_abs / 2, y_abs):
        yy = Y(gy)
        grid.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{W - pad_r}" y2="{yy:.1f}" stroke="#eef2f7" stroke-width="1"/>')
        grid.append(
            f'<text x="{pad_l - 8}" y="{yy + 3:.1f}" text-anchor="end" font-size="10" '
            f'font-family="ui-monospace,monospace" fill="#94a3b8">{gy:+.1f}%</text>'
        )
    for gx in (-100, -50, 0, 50, 100):
        xx = X(gx)
        grid.append(f'<line x1="{xx:.1f}" y1="{pad_t}" x2="{xx:.1f}" y2="{H - pad_b}" stroke="#eef2f7" stroke-width="1"/>')
        grid.append(
            f'<text x="{xx:.1f}" y="{H - pad_b + 18:.0f}" text-anchor="middle" font-size="10" '
            f'font-family="ui-monospace,monospace" fill="#94a3b8">{gx:+d}</text>'
        )

    # animated dots — each fades in sequentially, then gently pulses (live feel)
    dots = []
    for i in range(n):
        px, py = X(xs[i]), Y(ys[i])
        col = "#16a34a" if ys[i] >= 0 else "#ef4444"
        appear = (i / n) * 2.0
        pulse = 2.4 + (i % 11) * 0.35
        dots.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" fill="{col}">'
            f'<animate attributeName="r" values="0;4.5;4.0" dur="0.6s" begin="{appear:.2f}s" fill="freeze"/>'
            f'<animate attributeName="opacity" values="0.35;0.9;0.35" dur="{pulse:.1f}s" '
            f'begin="{appear + 0.6:.2f}s" repeatCount="indefinite"/>'
            f'</circle>'
        )

    # regression line draws itself in, then a highlight particle rides along it
    x1p, y1p = X(x_min), Y(b0 + b1 * x_min)
    x2p, y2p = X(x_max), Y(b0 + b1 * x_max)
    line_len = ((x2p - x1p) ** 2 + (y2p - y1p) ** 2) ** 0.5
    reg = (
        f'<line id="nqreg" x1="{x1p:.1f}" y1="{y1p:.1f}" x2="{x2p:.1f}" y2="{y2p:.1f}" '
        f'stroke="#f59e0b" stroke-width="2.4" stroke-dasharray="{line_len:.0f}" stroke-dashoffset="{line_len:.0f}">'
        f'<animate attributeName="stroke-dashoffset" values="{line_len:.0f};0" dur="1.6s" fill="freeze"/>'
        f'</line>'
        f'<circle r="4" fill="#f59e0b">'
        f'<animateMotion dur="3.5s" begin="1.6s" repeatCount="indefinite" '
        f'path="M {x1p:.1f} {y1p:.1f} L {x2p:.1f} {y2p:.1f}"/>'
        f'<animate attributeName="opacity" values="0;1;1;0" dur="3.5s" begin="1.6s" repeatCount="indefinite"/>'
        f'</circle>'
    )

    corr_col = "#16a34a" if corr >= 0 else "#ef4444"
    return (
        '<div style="display:flex;justify-content:center">'
        f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:{W}px" role="img" aria-label="edge matrix">'
        f'<rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="#f6f8fb"/>'
        # quadrant shading
        f'<rect x="{zero_x:.1f}" y="{pad_t}" width="{X(x_max) - zero_x:.1f}" height="{ph}" fill="#16a34a" opacity="0.055"/>'
        f'<rect x="{pad_l}" y="{pad_t}" width="{zero_x - pad_l:.1f}" height="{ph}" fill="#ef4444" opacity="0.055"/>'
        + "".join(grid) +
        # header
        f'<text x="{W - 16}" y="28" text-anchor="end" font-size="15" font-family="ui-monospace,monospace" '
        f'font-weight="800" fill="#475569">EDGE MATRIX // ماتریس لبه ◈</text>'
        f'<text x="16" y="28" font-size="13" font-family="ui-monospace,monospace" fill="#94a3b8">{n} نمونه</text>'
        f'<circle cx="200" cy="24" r="4" fill="#16a34a"><animate attributeName="opacity" values="0.3;1;0.3" dur="1.3s" repeatCount="indefinite"/></circle>'
        # axis titles
        f'<text x="{W / 2:.0f}" y="{pad_t - 20}" text-anchor="middle" font-size="11" '
        f'font-family="ui-monospace,monospace" fill="#64748b">محور افقی: امتیاز همگرایی (−۱۰۰ تا +۱۰۰) · محور عمودی: بازده کندل بعدی</text>'
        # bold zero axes on top of grid
        f'<line x1="{pad_l}" y1="{zero_y:.1f}" x2="{W - pad_r}" y2="{zero_y:.1f}" stroke="#cbd5e1" stroke-width="1.5"/>'
        f'<line x1="{zero_x:.1f}" y1="{pad_t}" x2="{zero_x:.1f}" y2="{H - pad_b}" stroke="#cbd5e1" stroke-width="1.5"/>'
        + "".join(dots) + reg +
        # footer readouts (bigger)
        f'<text x="16" y="{H - 16}" font-size="13" font-family="ui-monospace,monospace" fill="#ec4899">◀ لبه مثبت</text>'
        f'<text x="{W / 2:.0f}" y="{H - 16}" text-anchor="middle" font-size="13" font-weight="700" '
        f'font-family="ui-monospace,monospace" fill="{corr_col}">همبستگی {corr:+.2f}</text>'
        f'<text x="{W - 16}" y="{H - 16}" text-anchor="end" font-size="13" font-weight="700" '
        f'font-family="ui-monospace,monospace" fill="#f59e0b">شیب رگرسیون {b1:+.2f}</text>'
        '</svg></div>'
    )


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


def _ccxt_id(exchange: str) -> str:
    """Map a display name to a ccxt exchange id (lowercase, no spaces)."""
    special = {"huobi/htx": "htx", "htx": "htx", "crypto.com": "cryptocom",
               "gate": "gateio", "gateio": "gateio"}
    key = exchange.strip().lower().replace(" ", "")
    return special.get(key, key)


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_candles_ccxt(exchange: str, symbol: str, interval: str, limit: int) -> pd.DataFrame:
    """OHLCV via CCXT for any of its 100+ supported exchanges (public, no key)."""
    import ccxt

    ex_id = _ccxt_id(exchange)
    if not hasattr(ccxt, ex_id):
        raise ValueError(f"صرافی «{exchange}» در CCXT پشتیبانی نمی‌شود.")
    client = getattr(ccxt, ex_id)({"enableRateLimit": True, "timeout": 20000})
    # normalise symbol to BASE/QUOTE for ccxt
    sym = symbol.upper().replace("-", "/").replace("_", "/")
    if "/" not in sym:
        for q in ("USDT", "USDC", "USD", "BTC", "ETH"):
            if sym.endswith(q) and len(sym) > len(q):
                sym = f"{sym[:-len(q)]}/{q}"
                break
    tf = CCXT_TF.get(interval, "1h")
    ohlcv = client.fetch_ohlcv(sym, timeframe=tf, limit=min(1000, limit))
    rows = [{"time": int(x[0]), "open": float(x[1]), "high": float(x[2]),
             "low": float(x[3]), "close": float(x[4]), "volume": float(x[5] or 0)}
            for x in ohlcv if x and x[4]]
    df = pd.DataFrame(rows)
    if df.empty or len(df) < 20:
        raise ValueError("کندل کافی از این صرافی برنگشت.")
    df = df.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
    df = df[df["close"] > 0].tail(limit).reset_index(drop=True)
    df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df


@st.cache_data(ttl=60, show_spinner=False)
def fetch_candles(exchange: str, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
    """OHLCV from public exchange APIs. Built-in exchanges use native clients;
    anything else is fetched through CCXT. Falls back to other venues on error."""
    builtin = exchange in EXCHANGES
    try:
        if builtin:
            return _fetch_candles(exchange, symbol, interval, limit)
        return _fetch_candles_ccxt(exchange, symbol, interval, limit)
    except Exception:
        # try CCXT for a built-in name too, then the other built-ins
        attempts = []
        if builtin:
            attempts.append(lambda: _fetch_candles_ccxt(exchange, symbol, interval, limit))
        for alt in EXCHANGES:
            if alt == exchange:
                continue
            attempts.append(lambda alt=alt: _fetch_candles(alt, symbol, interval, limit))
        for fn in attempts:
            try:
                return fn()
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

# Persian sentiment keywords (titles are matched against these too).
BULLISH_FA = ["صعود", "رشد", "جهش", "افزایش", "رالی", "سبز", "اوج", "رکورد", "پذیرش", "تایید",
              "ورود پول", "خرید", "صعودی", "بهبود", "بازگشت", "سقف", "گاوی", "مثبت", "پامپ", "شکست مقاومت"]
BEARISH_FA = ["سقوط", "ریزش", "کاهش", "افت", "قرمز", "هک", "شکایت", "ممنوعیت", "خروج پول", "لیکویید",
              "ترس", "نزولی", "هشدار", "کلاهبرداری", "اصلاح", "کف", "خرسی", "منفی", "دامپ", "شکست حمایت"]

# News categories — each maps to a list of (source, url, is_persian) feeds.
# Persian sources carry full article text; English sources cover global markets.
NEWS_CATEGORIES = {
    "₿ کریپتو": [
        ("ارزدیجیتال", "https://arzdigital.com/feed/", True),
        ("Cointelegraph", "https://cointelegraph.com/rss", False),
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", False),
        ("Decrypt", "https://decrypt.co/feed", False),
    ],
    "💱 فارکس": [
        ("ForexLive", "https://www.forexlive.com/feed/", False),
    ],
    "🇺🇸 بازار آمریکا": [
        ("WSJ Markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", False),
        ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories", False),
        ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html", False),
    ],
    "🌍 اقتصاد جهان": [
        ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml", False),
        ("زومیت", "https://www.zoomit.ir/feed/", True),
    ],
    "⚔️ جنگ و ژئوپلیتیک": [
        ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", False),
        ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", False),
    ],
}

RSS2JSON = "https://api.rss2json.com/v1/api.json"


def _score_title(title: str) -> str:
    low = title.lower()
    score = (
        sum(1 for w in BULLISH if w in low) + sum(1 for w in BULLISH_FA if w in title)
        - sum(1 for w in BEARISH if w in low) - sum(1 for w in BEARISH_FA if w in title)
    )
    return "مثبت 🟢" if score > 0 else "منفی 🔴" if score < 0 else "خنثی ⚪"


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")


def _clean_html(raw: str) -> str:
    """Strip tags/scripts from RSS content:encoded for safe in-app reading."""
    if not raw:
        return ""
    txt = re.sub(r"<(script|style)[\s\S]*?</\1>", "", raw, flags=re.I)
    txt = txt.replace("</p>", "\n\n").replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    txt = _TAG_RE.sub("", txt)
    txt = (txt.replace("&nbsp;", " ").replace("&zwnj;", "\u200c").replace("&amp;", "&")
           .replace("&quot;", '"').replace("&#8220;", "«").replace("&#8221;", "»")
           .replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'"))
    txt = _WS_RE.sub(" ", txt)
    lines = [ln.strip() for ln in txt.split("\n")]
    return "\n".join(ln for ln in lines if ln).strip()


def _fetch_feed_direct(url: str) -> list[dict]:
    r = requests.get(url, timeout=15, headers=HEADERS)
    if r.status_code != 200:
        return []
    root = ET.fromstring(r.content)
    out = []
    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
    for node in root.iter("item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        date = (node.findtext("pubDate") or "").strip()
        body = node.findtext("content:encoded", namespaces=ns) or node.findtext("description") or ""
        if title and link:
            out.append({"title": title, "link": link, "date": date, "content": _clean_html(body)})
    return out


def _fetch_feed_relay(url: str) -> list[dict]:
    """JSON relay — needed for .ir feeds that servers can't fetch directly."""
    r = requests.get(RSS2JSON, params={"rss_url": url}, timeout=25, headers=HEADERS)
    data = r.json()
    if data.get("status") != "ok":
        return []
    out = []
    for it in data.get("items", []):
        title = (it.get("title") or "").strip()
        link = (it.get("link") or "").strip()
        date = (it.get("pubDate") or "").strip()
        body = it.get("content") or it.get("description") or ""
        if title and link:
            out.append({"title": title, "link": link, "date": date, "content": _clean_html(body)})
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def translate_to_fa(text: str) -> str:
    """Translate EN text to Persian via Google's free endpoint (no key).

    Returns the original text on any failure so the UI never breaks.
    """
    text = (text or "").strip()
    if not text:
        return ""
    # already Persian? skip (cheap heuristic: has Persian letters)
    if any("\u0600" <= ch <= "\u06ff" for ch in text):
        return text
    snippet = text[:4800]
    # 1) Google's free gtx endpoint (best quality)
    try:
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "en", "tl": "fa", "dt": "t", "q": snippet},
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            out = "".join(seg[0] for seg in data[0] if seg and seg[0])
            if out:
                return out
    except Exception:
        pass
    # 2) MyMemory fallback (works when gtx is rate-limited)
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": snippet[:500], "langpair": "en|fa"},
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10,
        )
        if r.status_code == 200:
            out = (r.json().get("responseData") or {}).get("translatedText") or ""
            if out and "MYMEMORY WARNING" not in out.upper():
                return out
    except Exception:
        pass
    return text


@st.cache_data(ttl=300, show_spinner=False)
def fetch_news(category: str = "₿ کریپتو", limit: int = 24, translate: bool = True) -> pd.DataFrame:
    """News for a given category. Persian feeds go through the JSON relay first;
    English feeds are tried directly, then relay. Non-Persian titles/text are
    translated to Persian so the whole feed reads in Persian."""
    feeds = NEWS_CATEGORIES.get(category, NEWS_CATEGORIES["₿ کریپتو"])
    items = []
    for source, url, is_fa in feeds:
        rows = []
        order = (_fetch_feed_relay, _fetch_feed_direct) if is_fa else (_fetch_feed_direct, _fetch_feed_relay)
        for fetcher in order:
            try:
                rows = fetcher(url)
            except Exception:
                rows = []
            if rows:
                break
        if translate and not is_fa and rows:
            # Batch all titles into ONE translation call (separator survives MT)
            sep = "\n•••\n"
            joined = sep.join(r["title"] for r in rows)
            tr = translate_to_fa(joined)
            parts = [p.strip() for p in tr.split("•••")]
            if len(parts) == len(rows):
                for r, p in zip(rows, parts):
                    r["title_fa"] = p or r["title"]
            else:
                for r in rows:
                    r["title_fa"] = r["title"]
        for row in rows:
            title = row.get("title_fa", row["title"]) if (translate and not is_fa) else row["title"]
            items.append({
                "title": title, "link": row["link"], "source": source,
                "date": row["date"], "content": row.get("content", ""),
                "en_title": row["title"], "is_fa": is_fa,
                "sentiment": _score_title(row["title"]),  # score original title
            })
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


def triple_tp_plan(d: pd.DataFrame, score: float) -> dict:
    """ATR-based plan with exactly THREE take-profits (1R / 2R / 3R) and a stop.

    Used by the opportunity scanner so every row has a full SL + TP1/TP2/TP3.
    """
    price = float(d["close"].iloc[-1])
    atr = float(d["atr"].iloc[-1]) if np.isfinite(d["atr"].iloc[-1]) else price * 0.01
    direction = "long" if score >= 0 else "short"
    recent = d.tail(10)
    swing = float(recent["low"].min()) if direction == "long" else float(recent["high"].max())
    if direction == "long":
        stop = max(min(swing - atr * 0.3, price - atr), price - atr * 3)
        risk = max(price - stop, atr)
        tps = [price + risk * m for m in (1, 2, 3)]
    else:
        stop = min(max(swing + atr * 0.3, price + atr), price + atr * 3)
        risk = max(stop - price, atr)
        tps = [price - risk * m for m in (1, 2, 3)]
    return {"direction": direction, "entry": price, "stop": stop,
            "tps": tps, "atr": atr, "risk_pct": risk / price * 100}


@st.cache_data(ttl=120, show_spinner=False)
def scan_opportunities(exchange: str, interval: str, top_n: int = 12, min_abs_score: int = 35) -> pd.DataFrame:
    """Scan the most liquid USDT markets and return the strongest setups
    (long or short) with SL + triple TP. Ranked by |confluence| × ADX."""
    try:
        movers = fetch_top_coins(exchange, 1_000_000, 40)
        pool = pd.concat([movers["volume"], movers["gainers"], movers["losers"]]).drop_duplicates("symbol")
        symbols = pool["symbol"].head(top_n * 3).tolist()
    except Exception:
        symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT",
                   "DOGE-USDT", "ADA-USDT", "AVAX-USDT", "LINK-USDT", "TRX-USDT"]

    rows = []
    for sym in symbols:
        sym_use = normalize_symbol(sym, exchange)
        try:
            d = add_indicators(fetch_candles(exchange, sym_use, interval, limit=300))
            if len(d) < 60:
                continue
            score_series, _ = confluence(d)
            score = float(score_series.iloc[-1])
            if abs(score) < min_abs_score:
                continue
            adx = float(d["adx"].iloc[-1]) if np.isfinite(d["adx"].iloc[-1]) else 0.0
            plan = triple_tp_plan(d, score)
            price = plan["entry"]
            dec = 2 if price >= 1000 else 4 if price >= 1 else 6
            rows.append({
                "symbol": sym_use,
                "dir": "لانگ 🟢" if score >= 0 else "شورت 🔴",
                "score": int(round(score)),
                "adx": round(adx, 1),
                "price": price,
                "stop": plan["stop"],
                "tp1": plan["tps"][0], "tp2": plan["tps"][1], "tp3": plan["tps"][2],
                "risk_pct": round(plan["risk_pct"], 2),
                "dec": dec,
                "rank": abs(score) * (1 + adx / 50),
            })
        except Exception:
            continue
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("rank", ascending=False).head(top_n).reset_index(drop=True)


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

    st.set_page_config(page_title="NorthmanQuant", page_icon="📈", layout="wide")
    st.markdown(
        "<div dir='rtl'><h1 style='margin:0'>📈 NorthmanQuant</h1></div>",
        unsafe_allow_html=True,
    )

    SECTIONS = ["📊 تحلیل زنده", "💎 فرصت‌های سودده", "✍️ ثبت تحلیل شخصی",
                "👥 تحلیل‌های کاربران", "🏆 برترین‌ها", "📰 اخبار", "🖼️ تصویر تحلیل", "📚 منابع داده"]

    with st.sidebar:
        st.header("⚙️ تنظیمات")

        # --- section navigation (moved here from the main page) --------------
        section = st.radio("بخش‌ها", SECTIONS, index=0, key="nav_section")

        # --- bazaar / market settings ---------------------------------------
        with st.expander("🏦 بازار و نماد", expanded=True):
            symbol_in = st.text_input("نماد", value="BTC-USDT",
                                      help="مثل BTC-USDT یا gramusdt · برای Lighter فقط BTC")
            exch_choice = st.selectbox("صرافی", EXCHANGES + ["XT", "LBank"] + ["➕ صرافی دیگر (CCXT)"])
            if exch_choice.startswith("➕"):
                custom_ex = st.text_input(
                    "نام یا شناسه‌ی صرافی", value="Kraken",
                    help="هر صرافیِ CCXT: kraken، coinbase، gate، mexc، bitget، htx، xt، lbank، …",
                )
                st.caption("نمونه‌ها: " + " · ".join(CCXT_SUGGESTED))
                exchange = custom_ex.strip() or "Kraken"
            else:
                exchange = exch_choice
            interval = st.selectbox("تایم‌فریم", list(INTERVAL_MINUTES.keys()), index=1)

        # --- chart settings --------------------------------------------------
        with st.expander("📈 تنظیمات چارت", expanded=False):
            candle_count = st.slider("تعداد کندل روی چارت (فشرده/باز)", min_value=40, max_value=500,
                                     value=160, step=20,
                                     help="کمتر = کندل‌ها بازتر و درشت‌تر · بیشتر = فشرده‌تر")
            live_on = st.checkbox("🔴 حالت زنده (قیمت هر ۵ ثانیه)", value=True)

        # --- appearance ------------------------------------------------------
        with st.expander("🎨 شخصی‌سازی ظاهر", expanded=False):
            theme_name = st.selectbox("تم رنگی", list(THEMES.keys()), index=0)
            bg_image_url = st.text_input(
                "لینک تصویر پس‌زمینه (اختیاری)", value="",
                placeholder="https://…/image.jpg",
                help="آدرس یک عکس بگذار تا پس‌زمینه‌ی دلخواهت شود.",
            )

        # --- sharing ---------------------------------------------------------
        with st.expander("🔗 اشتراک‌گذاری", expanded=False):
            app_url = st.text_input("لینک اپ", value="",
                                    placeholder="https://your-app.streamlit.app",
                                    help="لینک اپ منتشرشده‌ات را بگذار تا در اشتراک‌گذاری‌ها بیاید.")
            st.caption("دکمه‌ی شناور 🔗 گوشه‌ی صفحه را بکش و جابه‌جا کن؛ با زدن روی آن گزینه‌های اشتراک باز می‌شود.")

    # apply chosen theme (and optional background image) across the whole app
    st.markdown(theme_css(THEMES[theme_name], bg_image_url.strip()), unsafe_allow_html=True)

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

    if section == "📊 تحلیل زنده":
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

            # ===== NEURAL SHELL — placed ABOVE the chart =====================
            st.subheader("◈ پوسته مدل‌ها (Neural Shell) — زنده")
            components.html(
                "<div style='background:#f6f8fb;margin:0;padding:2px;border-radius:12px'>"
                + build_neural_shell_svg(comp_table, score)
                + "</div>",
                height=340,
            )
            st.divider()

            # ---- TradingView-style chart ---------------------------------
            # Slice to the chosen number of candles (horizontal compress/expand)
            dc = d.tail(candle_count).reset_index(drop=True)

            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True, row_heights=[0.80, 0.20],
                vertical_spacing=0.03,
            )
            # Bollinger band fill (subtle), drawn first so candles sit on top
            fig.add_trace(go.Scatter(x=dc["dt"], y=dc["bb_up"], line=dict(color="rgba(148,163,184,0.35)", width=1),
                                     name="BB بالا", hoverinfo="skip"), row=1, col=1)
            fig.add_trace(go.Scatter(x=dc["dt"], y=dc["bb_lo"], line=dict(color="rgba(148,163,184,0.35)", width=1),
                                     name="BB پایین", fill="tonexty", fillcolor="rgba(148,163,184,0.06)",
                                     hoverinfo="skip"), row=1, col=1)
            fig.add_trace(go.Candlestick(
                x=dc["dt"], open=dc["open"], high=dc["high"], low=dc["low"], close=dc["close"],
                increasing_line_color="#26a69a", increasing_fillcolor="#26a69a",
                decreasing_line_color="#ef5350", decreasing_fillcolor="#ef5350",
                line_width=1, name="قیمت", whiskerwidth=0.6,
            ), row=1, col=1)
            fig.add_trace(go.Scatter(x=dc["dt"], y=dc["ema20"], line=dict(color="#2962ff", width=1.4),
                                     name="EMA20"), row=1, col=1)
            fig.add_trace(go.Scatter(x=dc["dt"], y=dc["ema50"], line=dict(color="#ff9800", width=1.4),
                                     name="EMA50"), row=1, col=1)

            # Entry / Stop / Targets as clean horizontal lines, labels pinned to
            # the RIGHT price axis (no overlapping free-floating annotations).
            x_last = dc["dt"].iloc[-1]
            level_rows = [("ورود", plan["entry"], "#f59e0b", "solid"),
                          ("حد ضرر", plan["stop"], "#ef5350", "dash")]
            for i, (t_price, t_rr) in enumerate(plan["targets"]):
                level_rows.append((f"هدف{i + 1} · {t_rr}R", t_price, "#2962ff", "dash"))
            for name, yv, col, dash in level_rows:
                fig.add_hline(y=yv, line_color=col, line_width=1.4, line_dash=dash, row=1, col=1)
                fig.add_annotation(
                    x=x_last, y=yv, xref="x", yref="y", text=f" {name} {yv:,.{dec}f} ",
                    showarrow=False, xanchor="left", yanchor="middle", font=dict(size=11, color="#0b1220"),
                    bgcolor=col, borderpad=3, opacity=0.95, row=1, col=1,
                )

            vol_colors = ["#26a69a" if cl >= op else "#ef5350" for cl, op in zip(dc["close"], dc["open"])]
            fig.add_trace(go.Bar(x=dc["dt"], y=dc["volume"], marker_color=vol_colors, marker_line_width=0,
                                 name="حجم", opacity=0.55), row=2, col=1)

            fig.update_layout(
                height=640, template="plotly_dark", dragmode="pan", hovermode="x unified",
                xaxis_rangeslider_visible=False,
                paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                font=dict(family="ui-monospace, monospace", size=11, color="#b2b5be"),
                legend=dict(orientation="h", y=1.03, x=0, bgcolor="rgba(0,0,0,0)",
                            font=dict(size=10)),
                margin=dict(l=8, r=72, t=28, b=8),
                title=dict(text=f"{symbol} · {interval}", x=0.5, xanchor="center",
                           font=dict(size=13, color="#e2e8f0")),
            )
            # TradingView-like axes: price axis on the RIGHT, thin grid, spike line
            grid = "rgba(148,163,184,0.08)"
            fig.update_yaxes(side="right", gridcolor=grid, zeroline=False, row=1, col=1,
                             showspikes=True, spikemode="across", spikethickness=1,
                             spikecolor="rgba(148,163,184,0.5)", spikedash="dot", tickformat=",")
            fig.update_yaxes(side="right", gridcolor=grid, zeroline=False, row=2, col=1,
                             title_text="حجم", title_font=dict(size=9))
            fig.update_xaxes(gridcolor=grid, zeroline=False, row=1, col=1,
                             showspikes=True, spikemode="across", spikethickness=1,
                             spikecolor="rgba(148,163,184,0.5)", spikedash="dot", rangeslider_visible=False)
            fig.update_xaxes(gridcolor=grid, zeroline=False, row=2, col=1)
            st.plotly_chart(fig, use_container_width=True, config={
                "scrollZoom": True, "displaylogo": False,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            })

            # ---- build the share text (used by the floating share button) ---
            share_text = (
                f"نماد: {symbol} · {exchange} ({interval})\n"
                f"قیمت: {price:,.{dec}f}\n"
                f"سیگنال همگرایی: {score:+.0f} ({label})\n"
                f"جهت: {plan['direction']}\n"
                f"ورود: {plan['entry']:,.{dec}f} · حد ضرر: {plan['stop']:,.{dec}f} · R:R 1:{plan['rr']}\n"
                + "\n".join(f"هدف {i+1}: {tp:,.{dec}f} ({rr}R)" for i, (tp, rr) in enumerate(plan["targets"]))
            )
            # floating draggable share button (bottom-left, movable)
            components.html(
                floating_share(f"📈 تحلیل {symbol} — NorthmanQuant", share_text, app_url),
                height=0,
            )

            # ===== THE AGENTS — full-width strategy backtest row =============
            st.divider()
            st.subheader("◈ دفتر ایجنت‌ها (The Agents) — بک‌تست زنده")
            try:
                agent_cards = compute_agents(d)
                components.html(
                    "<div style='background:#f6f8fb;margin:0;padding:2px;border-radius:14px'>"
                    + build_agents_svg(agent_cards)
                    + "</div>",
                    height=520,
                )
            except Exception:  # noqa: BLE001
                pass

            # ===== TRADE PLAN — full width, own section ======================
            st.divider()
            st.subheader("🎯 طرح معامله")
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("جهت", plan["direction"])
            p2.metric("ورود", f"{plan['entry']:,.{dec}f}")
            p3.metric("حد ضرر", f"{plan['stop']:,.{dec}f}")
            p4.metric("R:R / اطمینان", f"1:{plan['rr']} · {plan['confidence']}٪")
            tcols = st.columns(max(1, len(plan["targets"])))
            for i, (t_price, t_rr) in enumerate(plan["targets"]):
                tcols[i].metric(f"هدف {i + 1}", f"{t_price:,.{dec}f}", f"{t_rr}R")

            # ===== CONFLUENCE COMPONENTS table ==============================
            st.divider()
            st.markdown("**اجزای همگرایی**")
            st.dataframe(comp_table, use_container_width=True, hide_index=True)

            # ===== SUPPORT / RESISTANCE — full width =========================
            st.divider()
            st.subheader("🧱 حمایت و مقاومت (سوئینگ)")
            if levels.empty:
                st.info("سطح معناداری پیدا نشد.")
            else:
                show = levels.copy()
                show["سطح"] = show["سطح"].map(lambda v: f"{v:,.{dec}f}")
                st.dataframe(show, use_container_width=True, hide_index=True)
                st.download_button("💾 ذخیره سطوح (CSV)", data=show.to_csv(index=False).encode("utf-8"),
                                   file_name=f"{symbol}_levels.csv", mime="text/csv", key="dl_levels")

            # ===== SIGNAL EVENTS — full width ================================
            st.divider()
            st.subheader("📜 رویدادهای ورود/خروج همگرایی")
            if events.empty:
                st.info("در این بازه رویدادی ثبت نشده است.")
            else:
                st.dataframe(events.tail(12).iloc[::-1], use_container_width=True, hide_index=True)

            # ===== CONFLUENCE TREND =========================================
            st.divider()
            st.subheader("📈 روند امتیاز همگرایی (۱۲۰ کندل اخیر)")
            st.line_chart(score_series.tail(120), height=160)
            st.caption("داده: API عمومی صرافی (کش ۶۰ ثانیه). این ابزار توصیه‌ی سرمایه‌گذاری نیست.")

            # ===== EDGE MATRIX — full width ==================================
            st.divider()
            st.subheader("◈ ماتریس لبه (Edge Matrix) — همبستگی سیگنال با بازده بعدی")
            try:
                components.html(
                    "<div style='background:#f6f8fb;margin:0;padding:2px;border-radius:12px'>"
                    + build_edge_matrix_svg(d, score_series)
                    + "</div>",
                    height=600,
                )
                st.caption("هر نقطه یک کندل است: محور افقی = امتیاز همگرایی، محور عمودی = بازده کندل بعدی. خط نارنجی رگرسیون؛ شیب و همبستگی مثبت یعنی سیگنال واقعاً پیش‌روِ سود بوده است.")
            except Exception:  # noqa: BLE001
                pass
        except Exception as e:  # noqa: BLE001
            st.error(f"خطا در دریافت/تحلیل داده: {e}")
            st.info("نماد را مثل BTC-USDT بنویس؛ اگر صرافی انتخابی در منطقه‌ات مسدود است، KuCoin یا OKX یا Lighter را انتخاب کن.")

    if section == "💎 فرصت‌های سودده":
        st.subheader("💎 فرصت‌های سودده — اسکن زنده‌ی بازار")
        st.caption("قوی‌ترین ستاپ‌های لانگ/شورت از میان پرمعامله‌ترین ارزها، با حد ضرر و سه تیک‌پرافیت. "
                   f"صرافی: {exchange} · تایم‌فریم: {interval}")
        oc1, oc2, oc3 = st.columns([1, 1, 1])
        with oc1:
            opp_n = st.slider("تعداد فرصت‌ها", 5, 20, 12, key="opp_n")
        with oc2:
            opp_minscore = st.slider("حداقل قدرت سیگنال", 20, 70, 35, step=5, key="opp_min")
        with oc3:
            st.write("")
            do_scan = st.button("🔍 اسکن بازار", type="primary", use_container_width=True)

        if do_scan or st.session_state.get("opp_done"):
            st.session_state["opp_done"] = True
            with st.spinner("در حال اسکن بازار… (ممکن است چند ثانیه طول بکشد)"):
                opp = scan_opportunities(exchange, interval, top_n=opp_n, min_abs_score=opp_minscore)
            if opp.empty:
                st.info("فعلاً ستاپ قوی‌ای پیدا نشد. حداقل قدرت سیگنال را کم کن یا تایم‌فریم دیگری امتحان کن.")
            else:
                st.success(f"{len(opp)} فرصت پیدا شد — مرتب‌شده بر اساس قدرت سیگنال × روند (ADX).")
                for _, r in opp.iterrows():
                    dec = int(r["dec"])
                    is_long = "لانگ" in r["dir"]
                    tone = "#16a34a" if is_long else "#ef4444"
                    sl_pct = (r["stop"] - r["price"]) / r["price"] * 100
                    def _pct(v):
                        return (v - r["price"]) / r["price"] * 100
                    st.markdown(
                        f"<div dir='rtl' style='border:1px solid rgba(148,163,184,.2);border-right:5px solid {tone};"
                        f"border-radius:14px;padding:14px 16px;margin:10px 0;background:rgba(148,163,184,.05)'>"
                        f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;align-items:center'>"
                        f"<span style='font-size:18px;font-weight:800'>{r['symbol']}</span>"
                        f"<span style='font-family:ui-monospace,monospace;font-size:14px;color:{tone};font-weight:800'>{r['dir']}</span>"
                        f"<span style='font-family:ui-monospace,monospace;font-size:12px;color:#94a3b8'>قدرت {r['score']:+d} · ADX {r['adx']} · ریسک {r['risk_pct']}%</span>"
                        f"</div>"
                        f"<div style='display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:12px;text-align:center'>"
                        f"<div style='background:rgba(148,163,184,.08);border-radius:10px;padding:8px'>"
                        f"<div style='font-size:10px;color:#94a3b8'>ورود</div>"
                        f"<div style='font-family:ui-monospace,monospace;font-weight:800;font-size:14px'>{r['price']:,.{dec}f}</div></div>"
                        f"<div style='background:rgba(239,68,68,.12);border-radius:10px;padding:8px'>"
                        f"<div style='font-size:10px;color:#fca5a5'>حد ضرر (SL)</div>"
                        f"<div style='font-family:ui-monospace,monospace;font-weight:800;font-size:14px;color:#ef4444'>{r['stop']:,.{dec}f}</div>"
                        f"<div style='font-size:9px;color:#94a3b8'>{sl_pct:+.2f}%</div></div>"
                        f"<div style='background:rgba(34,197,94,.10);border-radius:10px;padding:8px'>"
                        f"<div style='font-size:10px;color:#86efac'>TP1 · 1R</div>"
                        f"<div style='font-family:ui-monospace,monospace;font-weight:800;font-size:14px;color:#16a34a'>{r['tp1']:,.{dec}f}</div>"
                        f"<div style='font-size:9px;color:#94a3b8'>{_pct(r['tp1']):+.2f}%</div></div>"
                        f"<div style='background:rgba(34,197,94,.14);border-radius:10px;padding:8px'>"
                        f"<div style='font-size:10px;color:#86efac'>TP2 · 2R</div>"
                        f"<div style='font-family:ui-monospace,monospace;font-weight:800;font-size:14px;color:#16a34a'>{r['tp2']:,.{dec}f}</div>"
                        f"<div style='font-size:9px;color:#94a3b8'>{_pct(r['tp2']):+.2f}%</div></div>"
                        f"<div style='background:rgba(34,197,94,.18);border-radius:10px;padding:8px'>"
                        f"<div style='font-size:10px;color:#86efac'>TP3 · 3R</div>"
                        f"<div style='font-family:ui-monospace,monospace;font-weight:800;font-size:14px;color:#16a34a'>{r['tp3']:,.{dec}f}</div>"
                        f"<div style='font-size:9px;color:#94a3b8'>{_pct(r['tp3']):+.2f}%</div></div>"
                        f"</div></div>",
                        unsafe_allow_html=True,
                    )
                st.download_button(
                    "💾 ذخیره فرصت‌ها (CSV)",
                    data=opp.drop(columns=["dec", "rank"]).to_csv(index=False).encode("utf-8"),
                    file_name=f"opportunities_{exchange}_{interval}.csv", mime="text/csv",
                )
                st.caption("این فهرست صرفاً تحلیلی است و توصیه‌ی سرمایه‌گذاری نیست. حتماً مدیریت ریسک را رعایت کن.")
        else:
            st.info("روی «🔍 اسکن بازار» بزن تا بهترین فرصت‌های لانگ/شورت پیدا شوند.")

    if section == "🏆 برترین‌ها":
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

    if section == "📰 اخبار":
        st.caption("پوشش خبری زنده — کریپتو، فارکس، بازار آمریکا، اقتصاد جهان و جنگ/ژئوپلیتیک. "
                   "روی هر خبر بزن تا **متن کامل همین‌جا** باز شود.")
        news_cat = st.radio(
            "دسته‌بندی اخبار", list(NEWS_CATEGORIES.keys()),
            horizontal=True, label_visibility="collapsed", key="news_cat",
        )
        try:
            with st.spinner("در حال دریافت اخبار…"):
                news = fetch_news(news_cat)
            if news.empty:
                st.info("خبری دریافت نشد. چند لحظه بعد دوباره امتحان کن (فیدها گاهی با تأخیر کش می‌شوند).")
            else:
                src = " · ".join(sorted(news["source"].unique()))
                st.caption(f"{len(news)} خبر از: {src}")
                for idx, row in news.iterrows():
                    with st.expander(f"{row['sentiment']}  ·  {row['title']}"):
                        st.markdown(
                            f"<div style='color:#94a3b8;font-size:12px;margin-bottom:8px'>"
                            f"{row['source']} · {row['date']}</div>",
                            unsafe_allow_html=True,
                        )
                        body = (row.get("content") or "").strip()
                        # translate the body to Persian on demand (only the opened one)
                        if body and not row.get("is_fa", False):
                            body = translate_to_fa(body)
                        if body:
                            # full article text, RTL-aware, scrollable, readable
                            st.markdown(
                                "<div dir='rtl' style='line-height:2.1;font-size:15px;"
                                "max-height:480px;overflow:auto;text-align:justify;padding:4px 2px'>"
                                + body.replace("\n", "<br>")
                                + "</div>",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.info("متن کامل این خبر در فید موجود نیست — از «منبع اصلی» بخوان.")
                        st.markdown(
                            f"<a href='{row['link']}' target='_blank' "
                            f"style='font-size:12px;color:#38bdf8'>منبع اصلی ↗</a>",
                            unsafe_allow_html=True,
                        )
        except Exception as e:  # noqa: BLE001
            st.error(f"دریافت اخبار ممکن نشد: {e}")

    if section == "🖼️ تصویر تحلیل":
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

    if section == "✍️ ثبت تحلیل شخصی":
        st.subheader("✍️ ثبت تحلیل شخصی")
        st.caption("تحلیل حرفه‌ای‌ات را با جزئیات کامل ثبت کن تا در بخش «👥 تحلیل‌های کاربران» برای همه دیده شود.")

        with st.form("community_form", clear_on_submit=True):
            r1c1, r1c2, r1c3 = st.columns(3)
            with r1c1:
                ca_name = st.text_input("نام یا نام مستعار *", value="", max_chars=30)
            with r1c2:
                ca_symbol = st.text_input("نماد ارز *", value="BTC-USDT", max_chars=20,
                                          help="مثل BTC-USDT، ETH، SOL")
            with r1c3:
                ca_exchange = st.selectbox("صرافی", EXCHANGES + ["XT", "LBank", "سایر"], index=0)

            r2c1, r2c2, r2c3, r2c4 = st.columns(4)
            with r2c1:
                ca_bias = st.selectbox("جهت *", ["لانگ 🟢", "شورت 🔴", "خنثی ⚪"])
            with r2c2:
                ca_tf = st.selectbox("تایم‌فریم", list(INTERVAL_MINUTES.keys()), index=1)
            with r2c3:
                ca_entry = st.number_input("قیمت ورود", min_value=0.0, value=0.0, format="%.6f")
            with r2c4:
                ca_stop = st.number_input("حد ضرر (SL)", min_value=0.0, value=0.0, format="%.6f")

            r3c1, r3c2, r3c3, r3c4 = st.columns(4)
            with r3c1:
                ca_tp1 = st.number_input("هدف ۱ (TP1)", min_value=0.0, value=0.0, format="%.6f")
            with r3c2:
                ca_tp2 = st.number_input("هدف ۲ (TP2)", min_value=0.0, value=0.0, format="%.6f")
            with r3c3:
                ca_tp3 = st.number_input("هدف ۳ (TP3)", min_value=0.0, value=0.0, format="%.6f")
            with r3c4:
                ca_conf = st.slider("اطمینان ٪", 0, 100, 60)

            ca_text = st.text_area("شرح تحلیل و دلیل *", value="", height=140, max_chars=2000,
                                   placeholder="دلیل ورود، ستاپ تکنیکال، سطوح کلیدی، مدیریت ریسک …")
            ca_image = st.file_uploader("📷 عکس چارت/تحلیل (اختیاری)", type=["png", "jpg", "jpeg", "webp"],
                                        help="می‌توانی اسکرین‌شات چارت یا تحلیلت را هم پیوست کنی.")
            ca_submit = st.form_submit_button("📨 ثبت و اشتراک‌گذاری تحلیل", use_container_width=True, type="primary")

        if ca_submit:
            if ca_name.strip() and ca_symbol.strip() and ca_text.strip():
                from datetime import datetime as _dt
                # auto R:R if entry/stop/tp1 provided
                rr = ""
                try:
                    risk = abs(ca_entry - ca_stop)
                    if risk > 0 and ca_tp1 > 0:
                        rr = f"1:{round(abs(ca_tp1 - ca_entry) / risk, 2)}"
                except Exception:
                    rr = ""
                # encode the optional image to a small base64 data-URI (resized)
                img_uri = ""
                if ca_image is not None:
                    try:
                        import base64 as _b64
                        import io as _io
                        im = Image.open(ca_image).convert("RGB")
                        im.thumbnail((1000, 1000))  # cap size so the JSON stays light
                        buf = _io.BytesIO()
                        im.save(buf, format="JPEG", quality=80)
                        img_uri = "data:image/jpeg;base64," + _b64.b64encode(buf.getvalue()).decode()
                    except Exception:
                        img_uri = ""
                save_community({
                    "name": ca_name.strip(),
                    "symbol": ca_symbol.strip().upper(),
                    "exchange": ca_exchange,
                    "bias": ca_bias,
                    "tf": ca_tf,
                    "entry": ca_entry or None,
                    "stop": ca_stop or None,
                    "tp1": ca_tp1 or None, "tp2": ca_tp2 or None, "tp3": ca_tp3 or None,
                    "rr": rr,
                    "confidence": ca_conf,
                    "text": ca_text.strip(),
                    "image": img_uri,
                    "ts": _dt.now().strftime("%Y-%m-%d %H:%M"),
                })
                st.success("تحلیلت ثبت شد ✓ — در بخش «👥 تحلیل‌های کاربران» ببین.")
            else:
                st.warning("فیلدهای ستاره‌دار (نام، نماد، شرح تحلیل) را پر کن.")

    if section == "👥 تحلیل‌های کاربران":
        st.subheader("👥 تحلیل‌های کاربران")
        hc1, hc2 = st.columns([3, 1])
        with hc1:
            st.caption("تحلیل‌هایی که کاربران ثبت کرده‌اند. برای ثبت تحلیل خودت → بخش «✍️ ثبت تحلیل شخصی».")
        with hc2:
            if st.button("🔄 بازخوانی", use_container_width=True):
                st.rerun()

        posts = load_community()
        if not posts:
            st.info("هنوز تحلیلی ثبت نشده. اولین نفر باش! (بخش → ✍️ ثبت تحلیل شخصی)")
        else:
            # filter bar
            fcol1, fcol2 = st.columns([1, 1])
            with fcol1:
                syms = ["همه"] + sorted({p.get("symbol", "—") for p in posts})
                fsym = st.selectbox("فیلتر نماد", syms, index=0)
            with fcol2:
                fbias = st.selectbox("فیلتر جهت", ["همه", "لانگ 🟢", "شورت 🔴", "خنثی ⚪"], index=0)
            shown = [p for p in posts
                     if (fsym == "همه" or p.get("symbol") == fsym)
                     and (fbias == "همه" or p.get("bias") == fbias)]
            st.caption(f"{len(shown)} از {len(posts)} تحلیل")

            bias_tone = {"لانگ 🟢": "#16a34a", "شورت 🔴": "#ef4444", "خنثی ⚪": "#94a3b8"}

            def _chip(lbl, val, color="#e2e8f0"):
                if val in (None, "", 0):
                    return ""
                return (f"<div style='background:rgba(148,163,184,.1);border-radius:8px;padding:6px 8px;text-align:center'>"
                        f"<div style='font-size:9px;color:#94a3b8'>{lbl}</div>"
                        f"<div style='font-family:ui-monospace,monospace;font-weight:800;font-size:13px;color:{color}'>{val}</div></div>")

            for p in shown:
                tone = bias_tone.get(p.get("bias", ""), "#94a3b8")
                def _fmt(v):
                    try:
                        return f"{float(v):,.6g}"
                    except Exception:
                        return v
                chips = "".join([
                    _chip("ورود", _fmt(p.get("entry")), "#f59e0b"),
                    _chip("حد ضرر", _fmt(p.get("stop")), "#ef4444"),
                    _chip("TP1", _fmt(p.get("tp1")), "#16a34a"),
                    _chip("TP2", _fmt(p.get("tp2")), "#16a34a"),
                    _chip("TP3", _fmt(p.get("tp3")), "#16a34a"),
                    _chip("R:R", p.get("rr"), "#38bdf8"),
                    _chip("اطمینان", (f"{p.get('confidence')}%" if p.get("confidence") else ""), "#a855f7"),
                ])
                meta = " · ".join(x for x in [p.get("symbol", "—"), p.get("exchange", ""), p.get("tf", ""), p.get("bias", "")] if x)
                st.markdown(
                    f"<div dir='rtl' style='border:1px solid rgba(148,163,184,0.2);border-right:5px solid {tone};"
                    f"border-radius:14px;padding:14px 16px;margin:10px 0;background:rgba(148,163,184,0.05)'>"
                    f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;align-items:center'>"
                    f"<b style='font-size:16px'>👤 {p.get('name','ناشناس')}</b>"
                    f"<span style='font-family:ui-monospace,monospace;font-size:13px;color:{tone};font-weight:700'>{meta}</span></div>"
                    + (f"<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(78px,1fr));gap:8px;margin-top:12px'>{chips}</div>" if chips else "")
                    + f"<div style='margin-top:12px;line-height:2;font-size:14px;white-space:pre-wrap'>{p.get('text','')}</div>"
                    + (f"<img src='{p.get('image')}' style='margin-top:12px;max-width:100%;border-radius:10px;"
                       f"border:1px solid rgba(148,163,184,0.2)'/>" if p.get("image") else "")
                    + f"<div style='margin-top:8px;font-size:11px;color:#94a3b8'>🕒 {p.get('ts','')}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        st.caption("⚠️ این تخته‌ی اشتراکی سبک است؛ با ری‌استارت/دیپلویِ مجدد اپ پاک می‌شود و جای دیتابیس را نمی‌گیرد.")

    if section == "📚 منابع داده":
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
            {"صرافی": "XT", "نوع": "Spot (CCXT)", "کندل": "CCXT · fetch_ohlcv", "تیکر": "CCXT · fetch_ticker",
             "مستندات": EXCHANGE_DOCS["XT"]},
            {"صرافی": "LBank", "نوع": "Spot (CCXT)", "کندل": "CCXT · fetch_ohlcv", "تیکر": "CCXT · fetch_ticker",
             "مستندات": EXCHANGE_DOCS["LBank"]},
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


if __name__ == "__main__":
    main()
