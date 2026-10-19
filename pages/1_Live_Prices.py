"""Live Prices v2 - انتخاب صرافی + سرچ ارز + مقایسه همه صرافی‌ها"""
import streamlit as st
import requests
import time

st.set_page_config(page_title="Live Prices", page_icon="📊", layout="wide")
st.title("📊 قیمت‌های زنده بازار")
st.caption("اول صرافی رو انتخاب کن، بعد ارز رو سرچ کن — مقایسه KCEX + KuCoin + Binance + Bybit + OKX + Lighter")

EXCHANGES = ["KuCoin", "OKX", "Binance", "Bybit", "Lighter", "XT", "LBank", "KCEX"]
COMPARE_EX = ["KCEX", "KuCoin", "Binance", "Bybit", "OKX", "Lighter"]
HEADERS = {"User-Agent": "northmanquant-lite/1.0", "accept": "application/json"}

# ---------- لیست ارزهای هر صرافی (کش 10 دقیقه) ----------
@st.cache_data(ttl=600, show_spinner=False)
def get_symbols(exchange):
    try:
        if exchange == "KuCoin":
            r = requests.get("https://api.kucoin.com/api/v1/market/allTickers", headers=HEADERS, timeout=15).json()
            tickers = (r.get("data") or {}).get("ticker") or []
            out = sorted([t["symbol"] for t in tickers if t.get("symbol","").endswith("-USDT")])
            return out if out else ["BTC-USDT","ETH-USDT","SOL-USDT"]
        if exchange == "Binance":
            r = requests.get("https://data-api.binance.vision/api/v3/ticker/24hr", headers=HEADERS, timeout=15).json()
            out = []
            for t in r:
                s = t.get("symbol","")
                if s.endswith("USDT") and not s.endswith("UPUSDT") and not s.endswith("DOWNUSDT"):
                    base = s[:-4]
                    out.append(f"{base}-USDT")
            return sorted(out) if out else ["BTC-USDT","ETH-USDT"]
        if exchange == "Bybit":
            r = requests.get("https://api.bybit.com/v5/market/tickers", params={"category":"spot"}, headers=HEADERS, timeout=15).json()
            lst = ((r.get("result") or {}).get("list") or [])
            out = []
            for t in lst:
                s = t.get("symbol","")
                if s.endswith("USDT"):
                    out.append(f"{s[:-4]}-USDT")
            return sorted(out) if out else ["BTC-USDT","ETH-USDT"]
        if exchange == "OKX":
            r = requests.get("https://www.okx.com/api/v5/market/tickers", params={"instType":"SPOT"}, headers=HEADERS, timeout=15).json()
            out = sorted([t["instId"] for t in (r.get("data") or []) if t.get("instId","").endswith("-USDT")])
            return out if out else ["BTC-USDT","ETH-USDT"]
        if exchange == "Lighter":
            r = requests.get("https://mainnet.zklighter.elliot.ai/api/v1/orderBookDetails", headers=HEADERS, timeout=20).json()
            out = sorted([row.get("symbol","").upper() for row in (r.get("order_book_details") or []) if row.get("symbol") and row.get("status")=="active"])
            return out if out else ["BTC","ETH","SOL"]
        if exchange == "KCEX":
            for url in ["https://api.kcex.com/api/v1/market/tickers","https://api.kcex.com/api/v1/tickers"]:
                try:
                    r = requests.get(url, headers=HEADERS, timeout=10).json()
                    data = r.get("data", r)
                    if isinstance(data, list) and data:
                        out = []
                        for t in data:
                            s = str(t.get("symbol","")).upper().replace("/","-")
                            if "USDT" in s:
                                if "-" not in s:
                                    s = s.replace("USDT","-USDT")
                                out.append(s)
                        if out:
                            return sorted(list(set(out)))
                except Exception:
                    continue
            return ["BTC-USDT","ETH-USDT","SOL-USDT","XRP-USDT","DOGE-USDT","BNB-USDT"]
        if exchange in ("XT","LBank"):
            import ccxt
            cid = "xt" if exchange=="XT" else "lbank"
            ex = getattr(ccxt, cid)({"enableRateLimit": True, "timeout":15000})
            mk = ex.load_markets()
            out = sorted([s.replace("/","-") for s in mk.keys() if s.endswith("/USDT")])
            return out if out else ["BTC-USDT","ETH-USDT"]
    except Exception as e:
        print(f"symbols {exchange} err: {e}")
    return ["BTC-USDT","ETH-USDT","SOL-USDT"]

def parse_base(symbol_selected, main_ex):
    s = symbol_selected.strip().upper()
    if main_ex == "Lighter":
        return s.replace("-USDT","").replace("/USDT","").replace("USDT","")
    if "-" in s:
        return s.split("-")[0]
    if "/" in s:
        return s.split("/")[0]
    if s.endswith("USDT"):
        return s[:-4]
    return s

def fetch_price(target, base):
    try:
        if target == "KuCoin":
            sym = f"{base}-USDT"
            r = requests.get("https://api.kucoin.com/api/v1/market/orderbook/level1", params={"symbol":sym}, headers=HEADERS, timeout=6).json()
            d = r.get("data") or {}
            last = float(d.get("price") or 0)
            if last>0:
                return {"exchange":target,"last":last,"bid":float(d.get("bestBid") or 0),"ask":float(d.get("bestAsk") or 0)}
        if target == "Binance":
            sym = f"{base}USDT"
            r = requests.get("https://data-api.binance.vision/api/v3/ticker/24hr", params={"symbol":sym}, headers=HEADERS, timeout=6).json()
            last = float(r.get("lastPrice") or 0)
            if last>0:
                return {"exchange":target,"last":last,"bid":float(r.get("bidPrice") or 0),"ask":float(r.get("askPrice") or 0),"change":float(r.get("priceChangePercent") or 0)}
        if target == "Bybit":
            sym = f"{base}USDT"
            r = requests.get("https://api.bybit.com/v5/market/tickers", params={"category":"spot","symbol":sym}, headers=HEADERS, timeout=6).json()
            row = ((r.get("result") or {}).get("list") or [{}])[0]
            last = float(row.get("lastPrice") or 0)
            if last>0:
                return {"exchange":target,"last":last,"bid":float(row.get("bid1Price") or 0),"ask":float(row.get("ask1Price") or 0)}
        if target == "OKX":
            sym = f"{base}-USDT"
            r = requests.get("https://www.okx.com/api/v5/market/ticker", params={"instId":sym}, headers=HEADERS, timeout=6).json()
            row = (r.get("data") or [{}])[0]
            last = float(row.get("last") or 0)
            if last>0:
                return {"exchange":target,"last":last,"bid":float(row.get("bidPx") or 0),"ask":float(row.get("askPx") or 0)}
        if target == "KCEX":
            for url,params in [("https://api.kcex.com/api/v1/ticker",{"symbol":f"{base}-USDT"}),("https://api.kcex.com/api/v1/market/ticker",{"symbol":f"{base}USDT"})]:
                try:
                    r = requests.get(url, params=params, headers=HEADERS, timeout=6)
                    if r.status_code!=200: continue
                    j = r.json()
                    d = j.get("data",j) if isinstance(j,dict) else {}
                    if isinstance(d,list) and d: d=d[0]
                    last = float(d.get("last") or d.get("lastPrice") or d.get("price") or 0)
                    bid = float(d.get("buy") or d.get("bid") or 0)
                    ask = float(d.get("sell") or d.get("ask") or 0)
                    if last>0 or (bid>0 and ask>0):
                        price=(bid+ask)/2 if bid>0 and ask>0 else last
                        return {"exchange":target,"last":price,"bid":bid,"ask":ask}
                except Exception: continue
        if target == "Lighter":
            r = requests.get("https://mainnet.zklighter.elliot.ai/api/v1/orderBookDetails", headers=HEADERS, timeout=8).json()
            for row in (r.get("order_book_details") or []):
                if str(row.get("symbol","")).upper()==base.upper():
                    last=float(row.get("last_trade_price") or row.get("mark_price") or 0)
                    if last>0:
                        return {"exchange":target,"last":last,"bid":last,"ask":last}
    except Exception as e:
        print(f"price {target}/{base} err: {e}")
    return None

# ---------- UI ----------
c1,c2,c3 = st.columns([1.2,1.5,1.5])
with c1:
    main_ex = st.selectbox("🏦 صرافی (لیست ارز از اینجا میاد)", EXCHANGES, index=0)
with c2:
    refresh = st.select_slider("سرعت بروزرسانی", options=[1,2,3,5,10,30], value=2, format_func=lambda x: f"{x} ثانیه")
with c3:
    auto = st.checkbox("🔄 بروزرسانی خودکار", value=True)
    st.write(f"⏰ {time.strftime('%H:%M:%S')}")
    if st.button("🔄 دستی آپدیت کن"):
        st.rerun()

with st.spinner(f"در حال گرفتن لیست ارزهای {main_ex}..."):
    all_syms = get_symbols(main_ex)

st.success(f"✅ {len(all_syms)} ارز در {main_ex} پیدا شد")

s1,s2 = st.columns([1,2])
with s1:
    query = st.text_input("🔍 سرچ ارز", placeholder="مثلا BTC یا DOGE یا SOL...", value="")
with s2:
    if query:
        q = query.strip().upper()
        filtered = [s for s in all_syms if q in s.upper()]
        if not filtered:
            st.warning(f"چیزی با '{query}' پیدا نشد — همه رو نشون میدم")
            filtered = all_syms[:100]
        else:
            st.info(f"🔎 {len(filtered)} نتیجه برای '{query}'")
    else:
        # پیش‌فرض: محبوب‌ها اول
        popular = [s for s in ["BTC-USDT","BTC","ETH-USDT","ETH","SOL-USDT","SOL","XRP-USDT","XRP","DOGE-USDT","DOGE","BNB-USDT"] if s in all_syms]
        rest = [s for s in all_syms if s not in popular][:90]
        filtered = popular + rest

# انتخاب نهایی — حداکثر 5 تا برای سرعت
default_sym = [filtered[0]] if filtered else []
selected = st.multiselect(f"ارزها (از {main_ex} انتخاب کن — حداکثر 5 تا)", options=filtered, default=default_sym, max_selections=5)

st.markdown("---")
if not selected:
    st.info("👆 اول یه ارز رو سرچ و انتخاب کن")
    st.stop()

for sym_sel in selected:
    base = parse_base(sym_sel, main_ex)
    st.subheader(f"💎 {base} / USDT  (انتخاب از {main_ex}: {sym_sel})")
    cols = st.columns(3)
    prices = {}
    for t in COMPARE_EX:
        d = fetch_price(t, base)
        if d: prices[t]=d
    if not prices:
        st.error("قیمتی گرفته نشد — 2 ثانیه بعد خودکار تلاش می‌کنه")
        continue
    lasts = [v["last"] for v in prices.values() if v["last"]>0]
    if len(lasts)>=2:
        mn,mx = min(lasts), max(lasts)
        spread = (mx-mn)/mn*100 if mn>0 else 0
        if spread>0.3:
            st.success(f"⚡ اختلاف **{spread:.3f}%** | کمترین ${mn:,.4f} | بیشترین ${mx:,.4f} — فرصت آربیتراژ!")
        else:
            st.info(f"📊 اختلاف **{spread:.3f}%** | ${mn:,.4f} تا ${mx:,.4f}")
    i=0
    for exn in COMPARE_EX:
        d = prices.get(exn)
        with cols[i%3]:
            if d:
                ch = d.get("change",0)
                st.metric(f"🏦 {exn}", f"${d['last']:,.4f}", delta=f"{ch:.2f}%" if ch else None)
                st.caption(f"Bid ${d['bid']:,.4f} | Ask ${d['ask']:,.4f}")
            else:
                st.warning(f"{exn}: —")
        i+=1
    st.markdown("---")

if auto:
    time.sleep(refresh)
    st.rerun()
