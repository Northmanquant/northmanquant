--- /tmp/live_app.py	2026-10-20 06:52:06.119440617 +0000
+++ live/app.py	2026-10-20 07:05:12.867322224 +0000
@@ -541,12 +541,14 @@
     if exchange == "KCEX":
         return _fetch_candles_patched(exchange, symbol, interval, limit)
     if exchange in B.EXCHANGES:
-        raw = getattr(_orig_inner, "__wrapped__", None)
-        if callable(raw):
-            try:
-                return raw(exchange, symbol, interval, limit)
-            except Exception:  # noqa: BLE001
-                pass
+        # BUGFIX: `_fetch_candles` is not a cached function (no __wrapped__), so the
+        # old code always fell back to the 60-second cache and the "fast" scanner
+        # never actually refreshed. Call the raw fetcher directly.
+        raw = getattr(_orig_inner, "__wrapped__", None) or _orig_inner
+        try:
+            return raw(exchange, symbol, interval, limit)
+        except Exception:  # noqa: BLE001
+            pass
     return B.fetch_candles(exchange, symbol, interval, limit)
 
 
@@ -579,18 +581,23 @@
         except Exception:  # noqa: BLE001
             continue
     frames: dict[str, pd.DataFrame] = {}
-    with ThreadPoolExecutor(max_workers=6) as ex:
-        futs = {ex.submit(_fast_candles, store, exchange, s, interval, 300): s for s in syms}
-        try:
-            for fut in as_completed(futs, timeout=25):
-                s = futs[fut]
-                try:
-                    frames[s] = fut.result()
-                except Exception:  # noqa: BLE001
-                    continue
-        except Exception:  # noqa: BLE001
-            pass
+    ex = ThreadPoolExecutor(max_workers=6)
+    futs = {ex.submit(_fast_candles, store, exchange, s, interval, 300): s for s in syms}
+    try:
+        for fut in as_completed(futs, timeout=25):
+            s = futs[fut]
+            try:
+                frames[s] = fut.result()
+            except Exception:  # noqa: BLE001
+                continue
+    except Exception:  # noqa: BLE001
+        pass
+    finally:
+        # BUGFIX: `with ThreadPoolExecutor` waited for every slow request on exit,
+        # so the 25s budget was never honoured. Don't block on stragglers.
+        ex.shutdown(wait=False, cancel_futures=True)
     rows = []
+    errors: list[str] = []
     for s in syms:
         df = frames.get(s)
         if df is None:
@@ -621,9 +628,10 @@
                 "candle_time": str(d["dt"].iloc[-1])[:16] if "dt" in d.columns else "",
                 "rank": abs(score) * (1 + adx / 50) * (1 + 0.15 * max(0.0, np.sign(score) * (fvg_s + bvg_s))),
             })
-        except Exception:  # noqa: BLE001
+        except Exception as exc:  # noqa: BLE001
+            errors.append(f"{s}: {type(exc).__name__}: {exc}")
             continue
-    meta = {"scanned": len(frames), "pool": len(syms)}
+    meta = {"scanned": len(frames), "pool": len(syms), "errors": errors}
     df = pd.DataFrame(rows)
     if df.empty:
         return df, meta
@@ -634,18 +642,20 @@
     out: dict[str, float] = {}
     if not symbols:
         return out
-    with ThreadPoolExecutor(max_workers=8) as ex:
-        futs = {ex.submit(B.fetch_tick, exchange, s): s for s in symbols}
-        try:
-            for fut in as_completed(futs, timeout=5):
-                try:
-                    t = fut.result()
-                    if t and t.get("price"):
-                        out[futs[fut]] = float(t["price"])
-                except Exception:  # noqa: BLE001
-                    continue
-        except Exception:  # noqa: BLE001
-            pass
+    ex = ThreadPoolExecutor(max_workers=8)
+    futs = {ex.submit(B.fetch_tick, exchange, s): s for s in symbols}
+    try:
+        for fut in as_completed(futs, timeout=5):
+            try:
+                t = fut.result()
+                if t and t.get("price"):
+                    out[futs[fut]] = float(t["price"])
+            except Exception:  # noqa: BLE001
+                continue
+    except Exception:  # noqa: BLE001
+        pass
+    finally:
+        ex.shutdown(wait=False, cancel_futures=True)  # keep the live refresh snappy
     return out
 
 
@@ -671,6 +681,10 @@
         f"<span>{meta['scanned']} از {meta['pool']} نماد اسکن شد در {took:.1f}s</span>"
         f"</div>", unsafe_allow_html=True,
     )
+    errs = meta.get("errors") or []
+    if errs and len(errs) >= max(1, meta["scanned"] // 2):
+        # BUGFIX: a broken analysis engine used to show up as "no setups found".
+        st.error(f"تحلیل {len(errs)} از {meta['scanned']} نماد با خطا مواجه شد — خطای نمونه: {errs[0][:160]}")
     if opp.empty:
         _st_info("فعلاً ستاپ قوی‌ای پیدا نشد. حداقل قدرت سیگنال را کم کن یا تایم‌فریم دیگری امتحان کن.")
         return
