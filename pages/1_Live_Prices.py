--- /tmp/live_1_Live_Prices.py	2026-10-20 06:52:06.651448656 +0000
+++ live/pages/1_Live_Prices.py	2026-10-20 07:04:14.562441632 +0000
@@ -1,7 +1,18 @@
-"""Live Prices v2 - انتخاب صرافی + سرچ ارز + مقایسه همه صرافی‌ها"""
-import streamlit as st
-import requests
+"""Live Prices v3 - انتخاب صرافی + سرچ ارز + مقایسه همه صرافی‌ها
+
+Bug-fix release:
+  • رفرش خودکار دیگر با time.sleep + st.rerun کل صفحه را قفل نمی‌کند (st.fragment).
+  • قیمت‌ها برای همه‌ی صرافی‌ها «هم‌زمان» گرفته می‌شود (قبلاً تا ۳۰ درخواست پشت‌سرهم).
+  • پاسخ غیر JSON (مثل صفحه‌ی HTML مسدودسازی Bybit) دیگر خطا پرتاب نمی‌کند؛ آن صرافی «—» می‌شود.
+  • لیست Lighter یک‌بار برای همه‌ی ارزها گرفته می‌شود (کش ۲ ثانیه).
+"""
+from __future__ import annotations
+
 import time
+from concurrent.futures import ThreadPoolExecutor
+
+import requests
+import streamlit as st
 
 st.set_page_config(page_title="Live Prices", page_icon="📊", layout="wide")
 st.title("📊 قیمت‌های زنده بازار")
@@ -11,74 +22,90 @@
 COMPARE_EX = ["KCEX", "KuCoin", "Binance", "Bybit", "OKX", "Lighter"]
 HEADERS = {"User-Agent": "northmanquant-lite/1.0", "accept": "application/json"}
 
+
+def _get_json(url: str, params: dict | None = None, timeout: float = 6):
+    """GET → JSON یا None. هیچ‌وقت exception نمی‌دهد (پاسخ HTML/خالی/۴۰۳ = None)."""
+    try:
+        r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
+        if r.status_code != 200 or not r.content:
+            return None
+        ctype = (r.headers.get("content-type") or "").lower()
+        if "json" not in ctype and not r.text.lstrip().startswith(("{", "[")):
+            return None
+        return r.json()
+    except Exception:  # noqa: BLE001
+        return None
+
+
+def _f(v) -> float:
+    try:
+        return float(v or 0)
+    except (TypeError, ValueError):
+        return 0.0
+
+
 # ---------- لیست ارزهای هر صرافی (کش 10 دقیقه) ----------
 @st.cache_data(ttl=600, show_spinner=False)
-def get_symbols(exchange):
+def get_symbols(exchange: str) -> list[str]:
     try:
         if exchange == "KuCoin":
-            r = requests.get("https://api.kucoin.com/api/v1/market/allTickers", headers=HEADERS, timeout=15).json()
+            r = _get_json("https://api.kucoin.com/api/v1/market/allTickers", timeout=15) or {}
             tickers = (r.get("data") or {}).get("ticker") or []
-            out = sorted([t["symbol"] for t in tickers if t.get("symbol","").endswith("-USDT")])
-            return out if out else ["BTC-USDT","ETH-USDT","SOL-USDT"]
+            out = sorted([t["symbol"] for t in tickers if str(t.get("symbol", "")).endswith("-USDT")])
+            return out or ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
         if exchange == "Binance":
-            r = requests.get("https://data-api.binance.vision/api/v3/ticker/24hr", headers=HEADERS, timeout=15).json()
-            out = []
-            for t in r:
-                s = t.get("symbol","")
-                if s.endswith("USDT") and not s.endswith("UPUSDT") and not s.endswith("DOWNUSDT"):
-                    base = s[:-4]
-                    out.append(f"{base}-USDT")
-            return sorted(out) if out else ["BTC-USDT","ETH-USDT"]
-        if exchange == "Bybit":
-            r = requests.get("https://api.bybit.com/v5/market/tickers", params={"category":"spot"}, headers=HEADERS, timeout=15).json()
-            lst = ((r.get("result") or {}).get("list") or [])
+            r = _get_json("https://data-api.binance.vision/api/v3/ticker/24hr", timeout=15) or []
             out = []
-            for t in lst:
-                s = t.get("symbol","")
-                if s.endswith("USDT"):
+            for t in r if isinstance(r, list) else []:
+                s = str(t.get("symbol", ""))
+                if s.endswith("USDT") and not s.endswith(("UPUSDT", "DOWNUSDT")):
                     out.append(f"{s[:-4]}-USDT")
-            return sorted(out) if out else ["BTC-USDT","ETH-USDT"]
+            return sorted(out) or ["BTC-USDT", "ETH-USDT"]
+        if exchange == "Bybit":
+            r = _get_json("https://api.bybit.com/v5/market/tickers", {"category": "spot"}, timeout=15) or {}
+            lst = (r.get("result") or {}).get("list") or []
+            out = [f"{t['symbol'][:-4]}-USDT" for t in lst if str(t.get("symbol", "")).endswith("USDT")]
+            return sorted(out) or ["BTC-USDT", "ETH-USDT"]
         if exchange == "OKX":
-            r = requests.get("https://www.okx.com/api/v5/market/tickers", params={"instType":"SPOT"}, headers=HEADERS, timeout=15).json()
-            out = sorted([t["instId"] for t in (r.get("data") or []) if t.get("instId","").endswith("-USDT")])
-            return out if out else ["BTC-USDT","ETH-USDT"]
+            r = _get_json("https://www.okx.com/api/v5/market/tickers", {"instType": "SPOT"}, timeout=15) or {}
+            out = sorted([t["instId"] for t in (r.get("data") or []) if str(t.get("instId", "")).endswith("-USDT")])
+            return out or ["BTC-USDT", "ETH-USDT"]
         if exchange == "Lighter":
-            r = requests.get("https://mainnet.zklighter.elliot.ai/api/v1/orderBookDetails", headers=HEADERS, timeout=20).json()
-            out = sorted([row.get("symbol","").upper() for row in (r.get("order_book_details") or []) if row.get("symbol") and row.get("status")=="active"])
-            return out if out else ["BTC","ETH","SOL"]
+            r = _get_json("https://mainnet.zklighter.elliot.ai/api/v1/orderBookDetails", timeout=20) or {}
+            out = sorted([str(row.get("symbol", "")).upper() for row in (r.get("order_book_details") or [])
+                          if row.get("symbol") and row.get("status") == "active"])
+            return out or ["BTC", "ETH", "SOL"]
         if exchange == "KCEX":
-            for url in ["https://api.kcex.com/api/v1/market/tickers","https://api.kcex.com/api/v1/tickers"]:
-                try:
-                    r = requests.get(url, headers=HEADERS, timeout=10).json()
-                    data = r.get("data", r)
-                    if isinstance(data, list) and data:
-                        out = []
-                        for t in data:
-                            s = str(t.get("symbol","")).upper().replace("/","-")
-                            if "USDT" in s:
-                                if "-" not in s:
-                                    s = s.replace("USDT","-USDT")
-                                out.append(s)
-                        if out:
-                            return sorted(list(set(out)))
-                except Exception:
-                    continue
-            return ["BTC-USDT","ETH-USDT","SOL-USDT","XRP-USDT","DOGE-USDT","BNB-USDT"]
-        if exchange in ("XT","LBank"):
+            for url in ["https://api.kcex.com/api/v1/market/tickers", "https://api.kcex.com/api/v1/tickers"]:
+                r = _get_json(url, timeout=10)
+                data = r.get("data", r) if isinstance(r, dict) else r
+                if isinstance(data, list) and data:
+                    out = set()
+                    for t in data:
+                        s = str(t.get("symbol", "")).upper().replace("/", "-")
+                        if "USDT" in s:
+                            if "-" not in s:
+                                s = s.replace("USDT", "-USDT")
+                            out.add(s)
+                    if out:
+                        return sorted(out)
+            return ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT", "BNB-USDT"]
+        if exchange in ("XT", "LBank"):
             import ccxt
-            cid = "xt" if exchange=="XT" else "lbank"
-            ex = getattr(ccxt, cid)({"enableRateLimit": True, "timeout":15000})
+            cid = "xt" if exchange == "XT" else "lbank"
+            ex = getattr(ccxt, cid)({"enableRateLimit": True, "timeout": 15000})
             mk = ex.load_markets()
-            out = sorted([s.replace("/","-") for s in mk.keys() if s.endswith("/USDT")])
-            return out if out else ["BTC-USDT","ETH-USDT"]
-    except Exception as e:
+            out = sorted([s.replace("/", "-") for s in mk.keys() if s.endswith("/USDT")])
+            return out or ["BTC-USDT", "ETH-USDT"]
+    except Exception as e:  # noqa: BLE001
         print(f"symbols {exchange} err: {e}")
-    return ["BTC-USDT","ETH-USDT","SOL-USDT"]
+    return ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
 
-def parse_base(symbol_selected, main_ex):
+
+def parse_base(symbol_selected: str, main_ex: str) -> str:
     s = symbol_selected.strip().upper()
     if main_ex == "Lighter":
-        return s.replace("-USDT","").replace("/USDT","").replace("USDT","")
+        return s.replace("-USDT", "").replace("/USDT", "").replace("USDT", "")
     if "-" in s:
         return s.split("-")[0]
     if "/" in s:
@@ -87,79 +114,95 @@
         return s[:-4]
     return s
 
-def fetch_price(target, base):
+
+@st.cache_data(ttl=2, show_spinner=False)
+def _lighter_book() -> dict:
+    """یک‌بار برای همه‌ی ارزها (نه یک درخواست سنگین به‌ازای هر ارز)."""
+    r = _get_json("https://mainnet.zklighter.elliot.ai/api/v1/orderBookDetails", timeout=8) or {}
+    out = {}
+    for row in r.get("order_book_details") or []:
+        sym = str(row.get("symbol", "")).upper()
+        last = _f(row.get("last_trade_price")) or _f(row.get("mark_price"))
+        if sym and last > 0:
+            out[sym] = last
+    return out
+
+
+def fetch_price(target: str, base: str) -> dict | None:
     try:
         if target == "KuCoin":
-            sym = f"{base}-USDT"
-            r = requests.get("https://api.kucoin.com/api/v1/market/orderbook/level1", params={"symbol":sym}, headers=HEADERS, timeout=6).json()
+            r = _get_json("https://api.kucoin.com/api/v1/market/orderbook/level1", {"symbol": f"{base}-USDT"}) or {}
             d = r.get("data") or {}
-            last = float(d.get("price") or 0)
-            if last>0:
-                return {"exchange":target,"last":last,"bid":float(d.get("bestBid") or 0),"ask":float(d.get("bestAsk") or 0)}
-        if target == "Binance":
-            sym = f"{base}USDT"
-            r = requests.get("https://data-api.binance.vision/api/v3/ticker/24hr", params={"symbol":sym}, headers=HEADERS, timeout=6).json()
-            last = float(r.get("lastPrice") or 0)
-            if last>0:
-                return {"exchange":target,"last":last,"bid":float(r.get("bidPrice") or 0),"ask":float(r.get("askPrice") or 0),"change":float(r.get("priceChangePercent") or 0)}
-        if target == "Bybit":
-            sym = f"{base}USDT"
-            r = requests.get("https://api.bybit.com/v5/market/tickers", params={"category":"spot","symbol":sym}, headers=HEADERS, timeout=6).json()
+            last = _f(d.get("price"))
+            if last > 0:
+                return {"exchange": target, "last": last, "bid": _f(d.get("bestBid")), "ask": _f(d.get("bestAsk"))}
+        elif target == "Binance":
+            r = _get_json("https://data-api.binance.vision/api/v3/ticker/24hr", {"symbol": f"{base}USDT"}) or {}
+            last = _f(r.get("lastPrice"))
+            if last > 0:
+                return {"exchange": target, "last": last, "bid": _f(r.get("bidPrice")), "ask": _f(r.get("askPrice")),
+                        "change": _f(r.get("priceChangePercent"))}
+        elif target == "Bybit":
+            r = _get_json("https://api.bybit.com/v5/market/tickers", {"category": "spot", "symbol": f"{base}USDT"}) or {}
             row = ((r.get("result") or {}).get("list") or [{}])[0]
-            last = float(row.get("lastPrice") or 0)
-            if last>0:
-                return {"exchange":target,"last":last,"bid":float(row.get("bid1Price") or 0),"ask":float(row.get("ask1Price") or 0)}
-        if target == "OKX":
-            sym = f"{base}-USDT"
-            r = requests.get("https://www.okx.com/api/v5/market/ticker", params={"instId":sym}, headers=HEADERS, timeout=6).json()
+            last = _f(row.get("lastPrice"))
+            if last > 0:
+                return {"exchange": target, "last": last, "bid": _f(row.get("bid1Price")), "ask": _f(row.get("ask1Price")),
+                        "change": _f(row.get("price24hPcnt")) * 100}
+        elif target == "OKX":
+            r = _get_json("https://www.okx.com/api/v5/market/ticker", {"instId": f"{base}-USDT"}) or {}
             row = (r.get("data") or [{}])[0]
-            last = float(row.get("last") or 0)
-            if last>0:
-                return {"exchange":target,"last":last,"bid":float(row.get("bidPx") or 0),"ask":float(row.get("askPx") or 0)}
-        if target == "KCEX":
-            for url,params in [("https://api.kcex.com/api/v1/ticker",{"symbol":f"{base}-USDT"}),("https://api.kcex.com/api/v1/market/ticker",{"symbol":f"{base}USDT"})]:
-                try:
-                    r = requests.get(url, params=params, headers=HEADERS, timeout=6)
-                    if r.status_code!=200: continue
-                    j = r.json()
-                    d = j.get("data",j) if isinstance(j,dict) else {}
-                    if isinstance(d,list) and d: d=d[0]
-                    last = float(d.get("last") or d.get("lastPrice") or d.get("price") or 0)
-                    bid = float(d.get("buy") or d.get("bid") or 0)
-                    ask = float(d.get("sell") or d.get("ask") or 0)
-                    if last>0 or (bid>0 and ask>0):
-                        price=(bid+ask)/2 if bid>0 and ask>0 else last
-                        return {"exchange":target,"last":price,"bid":bid,"ask":ask}
-                except Exception: continue
-        if target == "Lighter":
-            r = requests.get("https://mainnet.zklighter.elliot.ai/api/v1/orderBookDetails", headers=HEADERS, timeout=8).json()
-            for row in (r.get("order_book_details") or []):
-                if str(row.get("symbol","")).upper()==base.upper():
-                    last=float(row.get("last_trade_price") or row.get("mark_price") or 0)
-                    if last>0:
-                        return {"exchange":target,"last":last,"bid":last,"ask":last}
-    except Exception as e:
+            last = _f(row.get("last"))
+            if last > 0:
+                return {"exchange": target, "last": last, "bid": _f(row.get("bidPx")), "ask": _f(row.get("askPx"))}
+        elif target == "KCEX":
+            for url, params in [("https://api.kcex.com/api/v1/ticker", {"symbol": f"{base}-USDT"}),
+                                ("https://api.kcex.com/api/v1/market/ticker", {"symbol": f"{base}USDT"})]:
+                j = _get_json(url, params)
+                if j is None:
+                    continue
+                d = j.get("data", j) if isinstance(j, dict) else {}
+                if isinstance(d, list) and d:
+                    d = d[0]
+                if not isinstance(d, dict):
+                    continue
+                last = _f(d.get("last")) or _f(d.get("lastPrice")) or _f(d.get("price"))
+                bid, ask = _f(d.get("buy")) or _f(d.get("bid")), _f(d.get("sell")) or _f(d.get("ask"))
+                if last > 0 or (bid > 0 and ask > 0):
+                    price = (bid + ask) / 2 if bid > 0 and ask > 0 else last
+                    return {"exchange": target, "last": price, "bid": bid, "ask": ask}
+        elif target == "Lighter":
+            last = _lighter_book().get(base.upper(), 0.0)
+            if last > 0:
+                return {"exchange": target, "last": last, "bid": last, "ask": last}
+    except Exception as e:  # noqa: BLE001
         print(f"price {target}/{base} err: {e}")
     return None
 
+
+def fetch_all(base: str) -> dict:
+    """قیمت همه‌ی صرافی‌ها هم‌زمان (حداکثر ~۶ ثانیه به‌جای ۳۶)."""
+    with ThreadPoolExecutor(max_workers=len(COMPARE_EX)) as ex:
+        results = list(ex.map(lambda t: fetch_price(t, base), COMPARE_EX))
+    return {t: d for t, d in zip(COMPARE_EX, results) if d}
+
+
 # ---------- UI ----------
-c1,c2,c3 = st.columns([1.2,1.5,1.5])
+c1, c2, c3 = st.columns([1.2, 1.5, 1.5])
 with c1:
     main_ex = st.selectbox("🏦 صرافی (لیست ارز از اینجا میاد)", EXCHANGES, index=0)
 with c2:
-    refresh = st.select_slider("سرعت بروزرسانی", options=[1,2,3,5,10,30], value=2, format_func=lambda x: f"{x} ثانیه")
+    refresh = st.select_slider("سرعت بروزرسانی", options=[1, 2, 3, 5, 10, 30], value=2, format_func=lambda x: f"{x} ثانیه")
 with c3:
     auto = st.checkbox("🔄 بروزرسانی خودکار", value=True)
-    st.write(f"⏰ {time.strftime('%H:%M:%S')}")
-    if st.button("🔄 دستی آپدیت کن"):
-        st.rerun()
+    manual = st.button("🔄 دستی آپدیت کن")
 
 with st.spinner(f"در حال گرفتن لیست ارزهای {main_ex}..."):
     all_syms = get_symbols(main_ex)
 
 st.success(f"✅ {len(all_syms)} ارز در {main_ex} پیدا شد")
 
-s1,s2 = st.columns([1,2])
+s1, s2 = st.columns([1, 2])
 with s1:
     query = st.text_input("🔍 سرچ ارز", placeholder="مثلا BTC یا DOGE یا SOL...", value="")
 with s2:
@@ -172,52 +215,56 @@
         else:
             st.info(f"🔎 {len(filtered)} نتیجه برای '{query}'")
     else:
-        # پیش‌فرض: محبوب‌ها اول
-        popular = [s for s in ["BTC-USDT","BTC","ETH-USDT","ETH","SOL-USDT","SOL","XRP-USDT","XRP","DOGE-USDT","DOGE","BNB-USDT"] if s in all_syms]
+        popular = [s for s in ["BTC-USDT", "BTC", "ETH-USDT", "ETH", "SOL-USDT", "SOL", "XRP-USDT", "XRP",
+                               "DOGE-USDT", "DOGE", "BNB-USDT"] if s in all_syms]
         rest = [s for s in all_syms if s not in popular][:90]
         filtered = popular + rest
 
-# انتخاب نهایی — حداکثر 5 تا برای سرعت
 default_sym = [filtered[0]] if filtered else []
-selected = st.multiselect(f"ارزها (از {main_ex} انتخاب کن — حداکثر 5 تا)", options=filtered, default=default_sym, max_selections=5)
+selected = st.multiselect(f"ارزها (از {main_ex} انتخاب کن — حداکثر 5 تا)", options=filtered,
+                          default=default_sym, max_selections=5)
 
 st.markdown("---")
 if not selected:
     st.info("👆 اول یه ارز رو سرچ و انتخاب کن")
     st.stop()
 
-for sym_sel in selected:
-    base = parse_base(sym_sel, main_ex)
-    st.subheader(f"💎 {base} / USDT  (انتخاب از {main_ex}: {sym_sel})")
-    cols = st.columns(3)
-    prices = {}
-    for t in COMPARE_EX:
-        d = fetch_price(t, base)
-        if d: prices[t]=d
-    if not prices:
-        st.error("قیمتی گرفته نشد — 2 ثانیه بعد خودکار تلاش می‌کنه")
-        continue
-    lasts = [v["last"] for v in prices.values() if v["last"]>0]
-    if len(lasts)>=2:
-        mn,mx = min(lasts), max(lasts)
-        spread = (mx-mn)/mn*100 if mn>0 else 0
-        if spread>0.3:
-            st.success(f"⚡ اختلاف **{spread:.3f}%** | کمترین ${mn:,.4f} | بیشترین ${mx:,.4f} — فرصت آربیتراژ!")
-        else:
-            st.info(f"📊 اختلاف **{spread:.3f}%** | ${mn:,.4f} تا ${mx:,.4f}")
-    i=0
-    for exn in COMPARE_EX:
-        d = prices.get(exn)
-        with cols[i%3]:
-            if d:
-                ch = d.get("change",0)
-                st.metric(f"🏦 {exn}", f"${d['last']:,.4f}", delta=f"{ch:.2f}%" if ch else None)
-                st.caption(f"Bid ${d['bid']:,.4f} | Ask ${d['ask']:,.4f}")
+
+def _render_prices(selected: list[str], main_ex: str) -> None:
+    st.caption(f"⏰ آخرین به‌روزرسانی: {time.strftime('%H:%M:%S')}")
+    for sym_sel in selected:
+        base = parse_base(sym_sel, main_ex)
+        st.subheader(f"💎 {base} / USDT  (انتخاب از {main_ex}: {sym_sel})")
+        prices = fetch_all(base)
+        if not prices:
+            st.error("قیمتی گرفته نشد — در به‌روزرسانی بعدی دوباره تلاش می‌شود")
+            continue
+        lasts = [v["last"] for v in prices.values() if v["last"] > 0]
+        if len(lasts) >= 2:
+            mn, mx = min(lasts), max(lasts)
+            spread = (mx - mn) / mn * 100 if mn > 0 else 0
+            if spread > 0.3:
+                st.success(f"⚡ اختلاف **{spread:.3f}%** | کمترین ${mn:,.4f} | بیشترین ${mx:,.4f} — فرصت آربیتراژ!")
             else:
-                st.warning(f"{exn}: —")
-        i+=1
-    st.markdown("---")
-
-if auto:
-    time.sleep(refresh)
-    st.rerun()
+                st.info(f"📊 اختلاف **{spread:.3f}%** | ${mn:,.4f} تا ${mx:,.4f}")
+        cols = st.columns(3)
+        for i, exn in enumerate(COMPARE_EX):
+            d = prices.get(exn)
+            with cols[i % 3]:
+                if d:
+                    ch = d.get("change", 0)
+                    st.metric(f"🏦 {exn}", f"${d['last']:,.4f}", delta=f"{ch:.2f}%" if ch else None)
+                    st.caption(f"Bid ${d['bid']:,.4f} | Ask ${d['ask']:,.4f}")
+                else:
+                    st.warning(f"{exn}: —")
+        st.markdown("---")
+
+
+if auto and hasattr(st, "fragment"):
+    # non-blocking auto refresh: only this block re-runs every `refresh` seconds
+    st.fragment(run_every=refresh)(_render_prices)(selected, main_ex)
+else:
+    _render_prices(selected, main_ex)
+    if auto:  # very old Streamlit without fragments → old behaviour
+        time.sleep(refresh)
+        st.rerun()
