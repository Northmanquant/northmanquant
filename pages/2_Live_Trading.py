--- /tmp/live_2_Live_Trading.py	2026-10-20 06:52:06.855451739 +0000
+++ live/pages/2_Live_Trading.py	2026-10-20 07:05:50.963897554 +0000
@@ -11,7 +11,8 @@
 
 c1,c2,c3 = st.columns(3)
 with c1:
-    ex_name = st.selectbox("صرافی", list(EX_MAP.keys()), index=4)
+    ex_name = st.selectbox("صرافی", list(EX_MAP.keys()), index=0,
+                           help="KCEX در کتابخانه‌ی ccxt پشتیبانی نمی‌شود؛ برای ترید واقعی KuCoin/OKX/Bybit/Binance را انتخاب کن.")
 with c2:
     api_key = st.text_input("API Key", type="password")
 with c3:
@@ -51,12 +52,21 @@
     return ex
 
 # قیمت زنده
+tick = None  # BUGFIX: قبلاً اگر قیمت گرفته نمی‌شد، tick تعریف نمی‌شد و سفارش مجازی NameError می‌داد
 try:
     import ccxt
-    pub = getattr(ccxt, EX_MAP[cfg["ex"]])({"enableRateLimit":True})
+    _cid = EX_MAP[cfg["ex"]]
+    if not hasattr(ccxt, _cid):
+        raise RuntimeError(f"صرافی {cfg['ex']} در ccxt پشتیبانی نمی‌شود — صرافی دیگری انتخاب کن")
+    pub = getattr(ccxt, _cid)({"enableRateLimit": True, "timeout": 15000})
     tick = pub.fetch_ticker(cfg["symbol"])
-    st.metric(f"قیمت {cfg['symbol']} در {cfg['ex']}", f"{tick['last']:,.4f}", f"Bid {tick['bid']} / Ask {tick['ask']}")
+    _last = tick.get("last") or tick.get("close") or 0
+    if not _last:
+        raise RuntimeError("قیمت آخر خالی برگشت")
+    tick["last"] = float(_last)
+    st.metric(f"قیمت {cfg['symbol']} در {cfg['ex']}", f"{tick['last']:,.4f}", f"Bid {tick.get('bid')} / Ask {tick.get('ask')}")
 except Exception as e:
+    tick = None
     st.warning(f"قیمت گرفته نشد: {e}")
 
 st.divider()
@@ -71,22 +81,24 @@
 with o4:
     price = st.number_input("قیمت لیمیت (فقط limit)", min_value=0.0, value=0.0)
 
-agree = st.checkbox("می‌فهمم پول واقعی است و مسئولیت با من است" if cfg["mode"].startswith("Real") else "شروع पेपर ترید")
+agree = st.checkbox("می‌فهمم پول واقعی است و مسئولیت با من است" if cfg["mode"].startswith("Real") else "شروع پیپر ترید (مجازی)")
 if cfg["mode"].startswith("Paper"):
     if "paper_bal" not in st.session_state:
         st.session_state.paper_bal = 10000.0
     st.info(f"موجودی مجازی: {st.session_state.paper_bal:,.2f} USDT")
     if st.button("✅ اجرای سفارش مجازی", disabled=not agree):
-        try:
-            last = tick["last"]
-            cost = amount*last
-            if side=="buy":
-                st.session_state.paper_bal -= cost
+        if tick is None:
+            st.error("قیمت زنده در دسترس نیست؛ سفارش مجازی ثبت نشد. صرافی/نماد را عوض کن یا دوباره «اتصال» بزن.")
+        elif amount <= 0:
+            st.error("مقدار باید بزرگ‌تر از صفر باشد.")
+        else:
+            last = float(tick["last"])
+            cost = amount * last
+            if side == "buy" and cost > st.session_state.paper_bal:
+                st.error(f"موجودی مجازی کافی نیست: نیاز {cost:,.2f} · موجودی {st.session_state.paper_bal:,.2f}")
             else:
-                st.session_state.paper_bal += cost
-            st.success(f"انجام شد در قیمت {last} — بالانس جدید {st.session_state.paper_bal:,.2f}")
-        except Exception as e:
-            st.error(str(e))
+                st.session_state.paper_bal += -cost if side == "buy" else cost
+                st.success(f"انجام شد در قیمت {last:,.4f} — بالانس جدید {st.session_state.paper_bal:,.2f}")
 else:
     if st.button("✅ ارسال سفارش واقعی", type="primary", disabled=not agree):
         if not cfg["key"] or not cfg["secret"]:
