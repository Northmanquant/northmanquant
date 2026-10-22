"""
Live health-check for every exchange integration in app.py.

Usage (from the repository root):
    python scripts/verify_apis.py

Runs ~21 checks against the real public APIs: candles, ticks, top movers,
the full indicator/confluence pipeline, RSS news and the screenshot candle
extractor. Exits non-zero if anything fails.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys
import traceback

import pandas as pd

import app as _app

# app.py is a patch layer: it imports app_base as B and monkey-patches the live
# functions (fetch_tick/_fetch_candles/fetch_top_coins/confluence/...) onto it.
# The public helpers (normalize_symbol, add_indicators, scan_opportunities, ...)
# live on app_base, so run the checks against the patched module, not app itself.
nq = _app.B

ok, fail = 0, 0


def check(name, fn):
    global ok, fail
    try:
        result = fn()
        print(f"✓ {name}: {result}")
        ok += 1
        return result
    except Exception as e:
        print(f"✗ {name}: {type(e).__name__}: {e}")
        traceback.print_exc(limit=2)
        fail += 1
        return None


print("== symbol normalization ==")
check("normalize BTC-USDT (KuCoin)", lambda: nq.normalize_symbol("btc-usdt", "KuCoin"))
check("normalize gramusdt (OKX)", lambda: nq.normalize_symbol("gramusdt", "OKX"))
check("normalize BTC-USDT (Lighter)", lambda: nq.normalize_symbol("BTC-USDT", "Lighter"))
check("normalize eth-perp (Lighter)", lambda: nq.normalize_symbol("eth-perp", "Lighter"))

print("\n== candles per exchange (live, with automatic fallback) ==")
for ex, sym in [("Lighter", "BTC"), ("OKX", "BTC-USDT"), ("KuCoin", "BTC-USDT"), ("Bybit", "BTC-USDT"), ("Binance", "BTC-USDT")]:
    def fetch(ex=ex, sym=sym):
        df = nq.fetch_candles(ex, sym, "1hour")
        return f"{len(df)} bars, last close {df['close'].iloc[-1]:,.2f}, {df['dt'].iloc[0]} → {df['dt'].iloc[-1]}"
    check(f"fetch_candles({ex}, {sym})", fetch)

print("\n== custom exchanges via CCXT ==")
for ex, sym in [("Kraken", "BTC-USDT"), ("XT", "BTC-USDT"), ("LBank", "BTC-USDT")]:
    def fetch_ccxt(ex=ex, sym=sym):
        df = nq.fetch_candles(ex, sym, "1hour")
        return f"{len(df)} bars, last close {df['close'].iloc[-1]:,.2f}"
    check(f"fetch_candles CCXT {ex}", fetch_ccxt)

print("\n== ticks (live) ==")
for ex, sym in [("Lighter", "BTC"), ("OKX", "BTC-USDT"), ("KuCoin", "BTC-USDT"), ("Binance", "BTC-USDT"), ("Bybit", "BTC-USDT")]:
    check(f"fetch_tick({ex})", lambda ex=ex, sym=sym: nq.fetch_tick(ex, sym))

print("\n== top coins (live) ==")
for ex in ["Lighter", "OKX", "KuCoin"]:
    def tops(ex=ex):
        t = nq.fetch_top_coins(ex)
        g = t["gainers"].iloc[0]
        return f"gainers[0]={g['symbol']} {g['change%']:+.2f}% | volume[0]={t['volume'].iloc[0]['symbol']}"
    check(f"fetch_top_coins({ex})", tops)

print("\n== full analysis pipeline ==")
def pipeline():
    df = nq.fetch_candles("Lighter", "BTC", "1hour")
    d = nq.add_indicators(df)
    score, table = nq.confluence(d)
    levels = nq.swing_levels(d)
    plan = nq.make_plan(d, float(score.iloc[-1]), levels)
    events, state = nq.signal_events(d, score)
    return (
        f"bars={len(d)} score={score.iloc[-1]:+.0f} atr={plan['atr']:,.1f} "
        f"levels={len(levels)} events={len(events)} state={state['status']} "
        f"dir={plan['direction']} rr=1:{plan['rr']}"
    )
check("Lighter pipeline (indicators→confluence→plan)", pipeline)

def pipeline_okx():
    df = nq.fetch_candles("OKX", "BTC-USDT", "1hour")
    d = nq.add_indicators(df)
    score, table = nq.confluence(d)
    events, state = nq.signal_events(d, score)
    return f"bars={len(d)} score={score.iloc[-1]:+.0f} events={len(events)} rsi={d['rsi'].iloc[-1]:.1f} adx={d['adx'].iloc[-1]:.1f}"
check("OKX pipeline", pipeline_okx)

print("\n== opportunity scanner (SL + triple TP) ==")
def scanner():
    opp = nq.scan_opportunities("OKX", "1hour", top_n=6, min_abs_score=25)
    if opp.empty:
        return "no setups right now (ok)"
    r = opp.iloc[0]
    assert all(c in opp.columns for c in ("stop", "tp1", "tp2", "tp3"))
    return f"{len(opp)} setups · top {r['symbol']} {r['dir']} score {r['score']:+d}"
check("scan_opportunities", scanner)

print("\n== news (live RSS, by category, with full text) ==")
def _news_cat(cat):
    def fn():
        df = nq.fetch_news(cat, translate=False)
        if df.empty:
            return "EMPTY"
        srcs = " · ".join(sorted(df["source"].unique()))
        full = int((df["content"].str.len() > 200).sum())
        return f"{len(df)} items from {srcs} · {full} with full text"
    return fn
for _cat in nq.NEWS_CATEGORIES:
    check(f"fetch_news {_cat}", _news_cat(_cat))

print("\n== analysis image (real data -> PNG) ==")
def analysis_image():
    d = nq.fetch_candles("OKX", "BTC-USDT", "1hour")
    d = nq.add_indicators(d)
    score_s, _ = nq.confluence(d)
    score = float(score_s.iloc[-1])
    lv = nq.swing_levels(d)
    plan = nq.make_plan(d, score, lv)
    price = float(d["close"].iloc[-1])
    dec = 2 if price >= 1000 else 4 if price >= 1 else 6
    png = nq.render_analysis_png(d, plan, lv, score, "BTC-USDT", "OKX", "1hour", dec)
    if not png or len(png) < 5000:
        raise ValueError("PNG too small / empty")
    if plan.get("entry") is None:
        return f"PNG {len(png)} bytes · plan=⏸ wait (no active setup — ok) · {len(lv)} levels"
    return f"PNG {len(png)} bytes · entry {plan['entry']:,.{dec}f} · stop {plan['stop']:,.{dec}f} · {len(lv)} levels"
check("render_analysis_png (BTC)", analysis_image)

print("\n== image extraction (synthetic chart, lite fallback) ==")
def img_extract():
    from PIL import Image, ImageDraw
    import random
    random.seed(7)
    W, H = 1200, 600
    im = Image.new("RGB", (W, H), (11, 18, 32))
    dr = ImageDraw.Draw(im)
    price = 300.0
    n = 60
    for i in range(n):
        x = 40 + i * 18
        o = price
        c = price + random.uniform(-14, 15)
        hi, lo = max(o, c) + random.uniform(0, 8), min(o, c) - random.uniform(0, 8)
        color = (34, 197, 94) if c >= o else (239, 68, 68)
        y = lambda p: H - 60 - (p - 200) * 1.2
        dr.line([(x + 4, y(hi)), (x + 4, y(lo))], fill=color, width=1)
        dr.rectangle([x, y(max(o, c)), x + 8, y(min(o, c))], fill=color)
        price = c
    cdf = nq.extract_candles_from_image(im)
    return f"{len(cdf)} candles extracted from a synthetic {n}-candle chart"
check("extract_candles_from_image", img_extract)

print(f"\n===== {ok} passed, {fail} failed =====")
sys.exit(1 if fail else 0)
