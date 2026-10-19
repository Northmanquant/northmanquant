"""
NorthmanQuant v2 loader - app.py
فایل اصلی تو الان app_base.py هست، این فقط KCEX + رفرش سریع رو تزریق میکنه.
"""
from __future__ import annotations
import requests
import pandas as pd
import streamlit as st
import app_base as B

HEADERS = B.HEADERS
KCEX_BASE = "https://api.kcex.com"
if "KCEX" not in B.EXCHANGE_DOCS:
    B.EXCHANGE_DOCS["KCEX"] = "https://www.kcex.com/api-docs"

_orig_tick = B.fetch_tick
_orig_fetch = B.fetch_candles
_orig_inner = B._fetch_candles
_orig_tops = B.fetch_top_coins

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
                ask = float(d.get("sell") or d.get("ask") or d.get("askPx") or d.get("bestAsk") or 0)
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

@st.cache_data(ttl=20, show_spinner=False)
def fetch_candles(exchange: str, symbol: str, interval: str, limit: int = 500):
    if exchange == "KCEX":
        try:
            import ccxt
            if hasattr(ccxt, "kcex"):
                ex = ccxt.kcex({"enableRateLimit": True, "timeout": 20000})
                sym = symbol.upper().replace("-", "/")
                tfmap = {"15min": "15m", "1hour": "1h", "4hour": "4h", "1day": "1d", "1week": "1w"}
                ohlcv = ex.fetch_ohlcv(sym, timeframe=tfmap.get(interval, "1h"), limit=min(500, limit))
                rows = [{"time": int(x[0]), "open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "volume": float(x[5] or 0)} for x in ohlcv if x and x[4]]
                df = pd.DataFrame(rows)
                if len(df) >= 40:
                    df = df.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
                    df = df[df["close"] > 0].tail(limit).reset_index(drop=True)
                    df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
                    return df
        except Exception as e:
            print(f"KCEX candles err: {e}")
        try:
            return _orig_inner("KuCoin", symbol, interval, limit)
        except Exception:
            pass
    try:
        return _orig_inner(exchange, symbol, interval, limit)
    except Exception:
        return _orig_fetch(exchange, symbol, interval, limit)

@st.cache_data(ttl=60, show_spinner=False)
def fetch_top_coins(exchange: str = "KuCoin", min_turnover: float = 1_000_000, limit: int = 15):
    if exchange == "KCEX":
        try:
            r = requests.get(f"{KCEX_BASE}/api/v1/market/tickers", headers=HEADERS, timeout=12)
            if r.status_code == 200:
                j = r.json()
                data = j.get("data", j)
                if isinstance(data, list):
                    rows = []
                    for t in data:
                        sym = str(t.get("symbol", ""))
                        if "USDT" not in sym.upper():
                            continue
                        last = float(t.get("last") or t.get("lastPrice") or t.get("price") or 0)
                        ch = float(t.get("changeRate") or t.get("change") or 0)
                        chpct = ch*100 if abs(ch) < 5 else ch
                        rows.append({"symbol": sym.replace("/", "-"), "price": last, "change%": chpct, "high": float(t.get("high") or 0), "low": float(t.get("low") or 0), "turnoverM$": float(t.get("volValue") or t.get("volume") or 0)/1e6})
                    import pandas as _pd
                    df = _pd.DataFrame(rows)
                    if not df.empty:
                        return {"gainers": df.sort_values("change%", ascending=False).head(limit).reset_index(drop=True), "losers": df.sort_values("change%").head(limit).reset_index(drop=True), "volume": df.sort_values("turnoverM$", ascending=False).head(limit).reset_index(drop=True)}
        except Exception as e:
            print(f"KCEX tops err: {e}")
        try:
            return _orig_tops("KuCoin", min_turnover, limit)
        except Exception:
            pass
    return _orig_tops(exchange, min_turnover, limit)

B.fetch_tick = fetch_tick
B.fetch_candles = fetch_candles
B.fetch_top_coins = fetch_top_coins
try:
    B.live_strip_auto = st.fragment(run_every=2)(B._live_strip_impl)
    B.live_strip_manual = st.fragment(B._live_strip_impl)
except Exception:
    pass
B.main()
