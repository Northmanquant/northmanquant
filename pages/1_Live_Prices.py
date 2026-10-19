"""Live Prices - NorthMan Quant | KCEX + KuCoin + Binance"""
import streamlit as st
import requests
import time

st.set_page_config(page_title="Live Prices", page_icon="📊", layout="wide")

st.title("📊 قیمت‌های زنده بازار")
st.caption("KCEX + KuCoin + Binance | بروزرسانی سریع")

# ---------- تنظیمات ----------
c1, c2, c3 = st.columns(3)
with c1:
    refresh_rate = st.select_slider(
        "سرعت بروزرسانی",
        options=[1, 2, 3, 5, 10, 30],
        value=2,
        format_func=lambda x: f"{x} ثانیه"
    )
with c2:
    auto_refresh = st.checkbox("🔄 بروزرسانی خودکار", value=True)
with c3:
    st.write(f"⏰ آخرین رفرش: {time.strftime('%H:%M:%S')}")
    if st.button("🔄 دستی آپدیت کن"):
        st.rerun()

symbols = st.multiselect(
    "ارزها",
    ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT"],
    default=["BTC/USDT", "ETH/USDT"]
)

st.markdown("---")

# ---------- توابع گرفتن قیمت ----------
def fetch_kucoin(symbol):
    try:
        s = symbol.replace("/", "-").upper()
        r = requests.get(
            "https://api.kucoin.com/api/v1/market/orderbook/level1",
            params={"symbol": s}, timeout=8
        )
        if r.status_code == 200:
            d = r.json().get("data", {}) or {}
            price = float(d.get("price", 0) or 0)
            return {
                "exchange": "KuCoin",
                "last": price,
                "bid": float(d.get("bestBid", 0) or 0),
                "ask": float(d.get("bestAsk", 0) or 0),
                "change": 0
            }
    except Exception as e:
        print(f"KuCoin err: {e}")
    return None

def fetch_binance(symbol):
    try:
        s = symbol.replace("/", "").upper()
        # vision دامنه بدون تحریم برای دیتای عمومی است
        r = requests.get(
            f"https://data-api.binance.vision/api/v3/ticker/24hr",
            params={"symbol": s}, timeout=8
        )
        if r.status_code == 200:
            d = r.json()
            return {
                "exchange": "Binance",
                "last": float(d.get("lastPrice", 0) or 0),
                "bid": float(d.get("bidPrice", 0) or 0),
                "ask": float(d.get("askPrice", 0) or 0),
                "change": float(d.get("priceChangePercent", 0) or 0)
            }
    except Exception as e:
        print(f"Binance err: {e}")
    return None

def fetch_kcex(symbol):
    # اول سعی میکنه از کلاس core استفاده کنه، اگر نبود مستقیم میگیره
    try:
        from core.exchanges.kcex import KCEXExchange
        ex = KCEXExchange()
        data = ex.get_ticker(symbol)
        if data and data.get("last", 0) > 0:
            data["change"] = 0
            return data
    except Exception as e:
        print(f"KCEX class err: {e}")
    try:
        s = symbol.replace("/", "-").upper()
        r = requests.get(
            "https://api.kcex.com/api/v1/ticker",
            params={"symbol": s}, timeout=8
        )
        if r.status_code == 200:
            d = r.json()
            if "data" in d and isinstance(d["data"], dict):
                d = d["data"]
            return {
                "exchange": "KCEX",
                "last": float(d.get("last", 0) or 0),
                "bid": float(d.get("buy", 0) or d.get("bid", 0) or 0),
                "ask": float(d.get("sell", 0) or d.get("ask", 0) or 0),
                "change": 0
            }
    except Exception as e:
        print(f"KCEX direct err: {e}")
    return None

# ---------- نمایش ----------
if not symbols:
    st.info("👈 یه ارز انتخاب کن")
    st.stop()

for symbol in symbols:
    st.subheader(f"💎 {symbol}")
    cols = st.columns(3)

    prices = {}
    k = fetch_kcex(symbol)
    if k: prices["KCEX"] = k
    ku = fetch_kucoin(symbol)
    if ku: prices["KuCoin"] = ku
    b = fetch_binance(symbol)
    if b: prices["Binance"] = b

    if not prices:
        st.error(f"قیمتی برای {symbol} گرفته نشد، چند ثانیه بعد خودکار تلاش میکنه")
        continue

    # اختلاف قیمت برای آربیتراژ
    lasts = [v["last"] for v in prices.values() if v["last"] > 0]
    if len(lasts) >= 2:
        mn, mx = min(lasts), max(lasts)
        spread = ((mx - mn) / mn * 100) if mn > 0 else 0
        if spread > 0.3:
            st.success(f"⚡ اختلاف: **{spread:.3f}%** | کمترین: ${mn:,.2f} | بیشترین: ${mx:,.2f} — فرصت آربیتراژ!")
        else:
            st.info(f"📊 اختلاف: **{spread:.3f}%** | کمترین: ${mn:,.2f} | بیشترین: ${mx:,.2f}")

    i = 0
    for ex_name in ["KCEX", "KuCoin", "Binance"]:
        d = prices.get(ex_name)
        with cols[i % 3]:
            if d:
                st.metric(
                    label=f"🏦 {ex_name}",
                    value=f"${d['last']:,.2f}" if d['last']>0 else "—",
                    delta=f"{d['change']:.2f}%" if d['change']!=0 else None
                )
                st.caption(f"Bid: ${d['bid']:,.2f} | Ask: ${d['ask']:,.2f}")
            else:
                st.warning(f"{ex_name}: قطع")
        i += 1

    st.markdown("---")

# ---------- لوپ آپدیت سریع ----------
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
