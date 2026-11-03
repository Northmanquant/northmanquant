#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/test_tvchart.py — تست چارت حرفه‌ای داشبورد (نسخه ۴ — منوی تریدینگ‌ویویی + ثانیه‌ای + نوار پایین)
اجرا: python3 scripts/test_tvchart.py   (بدون شبکه — fetch_candles فیک می‌شود)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tv_chart import build_tv_chart_html  # noqa: E402

PASS = 0


def ok(cond, name):
    global PASS
    assert cond, f"FAIL: {name}"
    PASS += 1
    print(f"  ✓ {name}")


def _candles(n=380, base=100.0, step=3600, t0=1_700_000_000):
    import random
    random.seed(7)
    out, px = [], base
    for i in range(n):
        o = px
        c = o + random.gauss(0, 0.5)
        h = max(o, c) + 0.3
        l = min(o, c) - 0.3
        out.append([t0 + i * step, o, h, l, c, abs(random.gauss(100, 20))])
        px = c
    return out


CD = _candles()
TFS = {"1hour": CD, "1day": _candles(step=86400), "5min": _candles(step=300)}

print("— build_tv_chart_html")
html = build_tv_chart_html(candles=CD, tfs=TFS, base_tf="1hour", symbol="BTC-USDT",
                           zones=[], levels=[],
                           title="BTC-USDT · 1hour", dec=1, initial_bars=160)
ok(html.startswith("<!DOCTYPE html>"), "HTML سالم")
ok("__DATA__" not in html and "__ZONES__" not in html and "__ZONES_JS__" not in html,
   "بدون placeholder باقی‌مانده")
ok("پوزیشن خرید" in html and "پوزیشن فروش" in html, "ابزار پوزیشن لانگ/شورت در منو")
ok("Parabolic SAR" in html and "SuperTrend" in html and "ایچیموکو" in html, "اندیکاتورهای روند")
ok("پیوت‌پوینت روزانه" in html, "پیوت‌پوینت")
ok("استوکاستیک" in html and "استوک RSI" in html and "ADX / DMI" in html, "نوسان‌گرهای پنلی")
ok("قلم آزاد" in html and "پرتو افقی" in html and "خط عمودی" in html, "ابزارهای جدید رسم")
ok('id="btnLog"' in html and "مقیاس لگاریتمی" in html, "دکمه مقیاس لگاریتمی")
ok('id="cdown"' in html and "fmtRem" in html and "setInterval" in html, "چیپ قیمت + شمارش معکوس کندل")
ok('id="btnLeg"' in html and "applyLeg" in html, "کلید خاموش/روشن لجند")
ok("ازنو (Redo)" in html and "REDO" in html, "واگرد/ازنو")
ok("توخالی" in html and "بیس‌لاین" in html and "پله‌ای" in html, "انواع چارت جدید (hollow/baseline/step)")
ok("WithSteps" in html and "pointMarkersVisible" in html and "addBaselineSeries" in html, "پیاده‌سازی انواع جدید")
ok('id="txtIn"' in html, "ورودی متن یادداشت")
for lbl in ["'1min':'1m'", "'3min':'3m'", "'5min':'5m'", "'15min':'15m'", "'30min':'30m'",
            "'1hour':'1H'", "'2hour':'2H'", "'4hour':'4H'", "'6hour':'6H'", "'12hour':'12H'",
            "'1day':'1D'", "'1week':'1W'", "'1month':'1M'"]:
    ok(lbl in html, f"نقشه تایم‌فریم {lbl}")
ok("LightweightCharts" in html, "کتابخانه inline")
ok(html.count("<script>") == 2, "دو بلاک اسکریپت (کتابخانه+اپ)")

print("— منوی بازه‌ی زمانی به سبک تریدینگ‌ویو")
ok('id="btnTfAll"' in html and "buildTfMenu" in html and "pickTf" in html, "دکمه+منوی همه‌ی بازه‌ها")
ok('id="menuTf"' in html and "TF_GROUPS" in html, "منوی گروهی تایم‌فریم")
ok("ثانیه‌ها" in html and "دقیقه‌ها" in html and "ساعت‌ها" in html
   and "روزها" in html and "هفته‌ها" in html and "ماه‌ها" in html, "شش گروه منو مثل تریدینگ‌ویو")
ok("'1s':'1s'" in html and "'5s':'5s'" in html and "'10s':'10s'" in html
   and "'15s':'15s'" in html and "'30s':'30s'" in html and "'45s':'45s'" in html, "لیبل ثانیه‌ای‌ها")
ok("'2min':'2m'" in html and "'10min':'10m'" in html and "'45min':'45m'" in html, "لیبل دقیقه‌های سفارشی")
ok("'3hour':'3h'" in html and "'8hour':'8H'" in html and "'2day':'2D'" in html
   and "'3day':'3D'" in html, "لیبل 3h/8H/2D/3D")
ok("TF_QUICK" in html and "updTfBtn" in html, "دکمه‌های سریع + لیبل دکمه‌ی بازه")
ok("btnRange" not in html and "menuRange" not in html, "منوی قدیمی بازه‌ها حذف شد")

print("— کندل ثانیه‌ای سمت مرورگر (Binance)")
ok("const SECS = {'1s':1,'5s':5,'10s':10,'15s':15,'30s':30,'45s':45};" in html, "نقشه SECS شش بازه")
ok("async function loadSeconds(tf)" in html and "SECS_CACHE" in html, "لودر ثانیه‌ای + کش")
ok("data-api.binance.vision" in html and "api.binance.com" in html, "دو هاست بایننس با فال‌بک")
ok("interval=1s" in html and "endTime=" in html, "دریافت کندل 1s با صفحه‌بندی")
ok("Math.floor(r[0]/sec)*sec" in html, "تجمیع OHLCV به سبد ثانیه‌ای")
ok("WANT_SECS" in html, "بازیابی بازه‌ی ثانیه‌ای پس از رفرش")

print("— نوار پایین سبک تریدینگ‌ویو")
ok('id="bbar"' in html and 'id="bbarRanges"' in html, "نوار پایین + رنج‌ها")
ok("BRANGES" in html and "'1D',86400" in html and "'5D',432000" in html
   and "'YTD','ytd'" in html, "رنج‌های 1D/5D/1M/3M/6M/YTD/همه")
ok("Date.UTC(new Date().getUTCFullYear(),0,1)" in html, "محاسبه YTD")
ok('id="clock"' in html and "timeZone:'Asia/Tehran'" in html and "UTC+3:30" in html,
   "ساعت زنده تهران")
ok('id="bbSell"' in html and 'id="bbBuy"' in html and "setTool('posS')" in html
   and "setTool('posL')" in html, "دکمه‌های SELL/BUY متصل به ابزار پوزیشن")

print("— نگاشت تایم‌فریم‌ها")
import app_base as AB  # noqa: E402

for m in (AB.KUCOIN_TF, AB.BINANCE_TF, AB.BYBIT_TF, AB.OKX_TF, AB.CCXT_TF):
    ok(all(tf in m for tf in AB.CHART_TFS), f"پوشش کامل CHART_TFS در نقشه‌ها")
ok(AB.CHART_TF_MINUTES["1month"] == 43200, "دقیقه‌ی 1M")
ok(AB.CHART_TF_MINUTES["8hour"] == 480, "دقیقه‌ی 8H جدید")
ok(len(AB.CHART_TFS) == 14, "۱۴ تایم‌فریم بومی (+8hour)")
ok(set(AB.CHART_TF_AGG) == {"2min", "10min", "45min", "3hour", "2day", "3day"}, "شش بازه‌ی تجمیعی")
ok(all(base in AB.CHART_TFS for base, _, _ in AB.CHART_TF_AGG.values()),
   "پایه‌ی تجمیعی‌ها بومی است")
ok(all(f in AB.CHART_TF_MINUTES for f in AB.CHART_TF_AGG), "CHART_TF_MINUTES پوشش تجمیعی‌ها")
ok(set(AB.CHART_TF_SEC) == {"1s", "5s", "10s", "15s", "30s", "45s"}, "شش بازه‌ی ثانیه‌ای")
ok(not (set(AB.CHART_TF_SEC) & set(AB.CHART_TFS) or set(AB.CHART_TF_SEC) & set(AB.CHART_TF_AGG)),
   "ثانیه‌ای‌ها هرگز سرور-فچ نمی‌شوند")

print("— _resample_ohlcv (تجمیع سرور)")
import pandas as pd  # noqa: E402


def _mk_1m(n=90, t0=1_700_000_000 - 1_700_000_000 % 86400 + 630 * 60):  # 10:30 UTC (تراز با 45min)
    rows = []
    for i in range(n):
        rows.append({"time": (t0 + i * 60) * 1000, "open": 100.0 + i, "high": 101.0 + i,
                     "low": 99.0 + i, "close": 100.5 + i, "volume": 2.0})
    df = pd.DataFrame(rows)
    df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df


df90 = _mk_1m(90)
r45 = AB._resample_ohlcv(df90, "45min")
ok(len(r45) == 2, "۹۰ کندل ۱ دقیقه‌ای → ۲ کندل ۴۵ دقیقه‌ای")
ok(abs(r45.iloc[0]["open"] - 100.0) < 1e-9 and abs(r45.iloc[0]["close"] - 144.5) < 1e-9,
   "open اول و close اول درست")
ok(abs(r45.iloc[0]["high"] - 145.0) < 1e-9 and abs(r45.iloc[0]["low"] - 99.0) < 1e-9,
   "high/low تجمیعی درست")
ok(abs(r45.iloc[0]["volume"] - 90.0) < 1e-9, "حجم جمعی درست")
ok(int(r45.iloc[0]["time"]) % (45 * 60) == 0, "مرز بازه به ۴۵ دقیقه چسبیده")
r3h = AB._resample_ohlcv(df90, "3h")
ok(len(r3h) == 1 and int(r3h.iloc[0]["time"]) % 10800 == 0, "قاعده‌ی 3h")

print("— tf_bundle (fetch فیک موازی + تجمیع)")


def fake_fetch(exchange, symbol, interval, limit=500):
    if interval in ("1min", "2hour"):        # شبیه‌سازی خطای دو تایم‌فریم
        raise ValueError("no data")
    step = {"3min": 180, "5min": 300, "15min": 900, "30min": 1800, "1hour": 3600,
            "2hour": 7200, "4hour": 14400, "6hour": 21600, "8hour": 28800,
            "12hour": 43200, "1day": 86400, "1week": 604800,
            "1month": 2592000}.get(interval, 3600)
    t0 = 1_700_000_000 - 1_700_000_000 % 86400   # نیمه‌شب UTC — تراز با همه‌ی بازه‌های تجمیعی
    df = pd.DataFrame([{"time": t * 1000, "open": o, "high": h, "low": l, "close": c, "volume": v}
                       for t, o, h, l, c, v in _candles(60, step=step, t0=t0)])
    df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df


orig = AB.fetch_candles
AB.fetch_candles = fake_fetch
try:
    bundle = AB.tf_bundle("KuCoin", "BTC-USDT", tuple(AB.CHART_TFS), limit=60)
    bundle_agg = AB.tf_bundle("KuCoin", "BTC-USDT", tuple(AB.CHART_TF_AGG), limit=60)
finally:
    AB.fetch_candles = orig
ok(len(bundle) == len(AB.CHART_TFS) - 2, "TFهای ناموفق حذف شدند (fetch موازی)")
ok(all(len(v) == 60 for v in bundle.values()), "ابعاد کندل‌ها درست")
ok(all(r[1] is not None for v in bundle.values() for r in v[:5]), "بدون NaN در خروجی")
ok("2min" not in bundle_agg and len(bundle_agg) == 5, "2min از پایه‌ی خطادار حذف، بقیه تجمیع شد")
ok([len(bundle_agg[k]) for k in ("10min", "45min", "3hour", "2day", "3day")] == [30, 20, 20, 30, 20],
   "۵ بازه‌ی تجمیعی با طول درست (نصف/یک‌سوم پایه)")
ok(all(int(bundle_agg["10min"][0][0]) % 600 == 0 for _ in [0]), "مرز ۱۰ دقیقه‌ای")

print(f"\n✅ همه‌ی {PASS} تست چارت پاس شد")
