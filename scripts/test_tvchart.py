#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/test_tvchart.py — تست چارت حرفه‌ای داشبورد (نسخه ۳)
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


def _candles(n=380, base=100.0, step=3600):
    import random
    random.seed(7)
    out, px, t0 = [], base, 1_700_000_000
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
ok('id="btnRange"' in html and "بازه‌ها" in html and 'id="menuRange"' in html, "دکمه بازه‌های سریع + منو")
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

print("— نگاشت تایم‌فریم‌ها")
import app_base as AB  # noqa: E402

for m in (AB.KUCOIN_TF, AB.BINANCE_TF, AB.BYBIT_TF, AB.OKX_TF, AB.CCXT_TF):
    ok(all(tf in m for tf in AB.CHART_TFS), f"پوشش کامل CHART_TFS در {m is AB.KUCOIN_TF and 'KUCOIN' or ''} نقشه")
ok(AB.CHART_TF_MINUTES["1month"] == 43200, "دقیقه‌ی 1M")
ok(len(AB.CHART_TFS) == 13, "۱۳ تایم‌فریم")

print("— tf_bundle (fetch فیک موازی)")
import pandas as pd  # noqa: E402


def fake_fetch(exchange, symbol, interval, limit=500):
    if interval in ("1min", "2hour"):        # شبیه‌سازی خطای دو تایم‌فریم
        raise ValueError("no data")
    df = pd.DataFrame([{"time": t * 1000, "open": o, "high": h, "low": l, "close": c, "volume": v}
                       for t, o, h, l, c, v in _candles(60)])
    df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df


orig = AB.fetch_candles
AB.fetch_candles = fake_fetch
try:
    bundle = AB.tf_bundle("KuCoin", "BTC-USDT", tuple(AB.CHART_TFS), limit=60)
finally:
    AB.fetch_candles = orig
ok(len(bundle) == len(AB.CHART_TFS) - 2, "TFهای ناموفق حذف شدند (fetch موازی)")
ok(all(len(v) == 60 for v in bundle.values()), "ابعاد کندل‌ها درست")
ok(all(r[1] is not None for v in bundle.values() for r in v[:5]), "بدون NaN در خروجی")

print(f"\n✅ همه‌ی {PASS} تست چارت پاس شد")
