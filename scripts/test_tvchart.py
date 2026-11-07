#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/test_tvchart.py — تست چارت حرفه‌ای داشبورد (نسخه ۵ — ابزار یک‌بارمصرف + پاک‌کن تک‌رسم + روکش‌های قابل خاموش‌کردن)
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

print("— ابزار یک‌بارمصرف + پاک‌کن تک‌رسم + واگرد کامل (نسخه ۵)")
ok("پاک‌کن — کلیک روی هر رسم" in html, "ابزار پاک‌کن در منوی ابزارها")
ok("function hitTest(" in html and "function segDist(" in html, "هیت‌تست حذف تک‌رسم (همه‌ی انواع رسم)")
ok("eraseAt(hitTest(" in html, "کلیک پاک‌کن → حذف رسم زیر نشانگر")
ok("function oneShotDone(" in html and "oneShotDone(); }" in html,
   "یک‌بارمصرف: پس از هر رسم، بازگشت خودکار به نشانگر (فیبوناچی نمی‌ماند)")
ok("function doUndo(" in html and "function doRedo(" in html and "function clearAll(" in html,
   "واگرد/ازنو/پاک‌کردن همه با پشته‌ی عملیات")
ok("op:'erase'" in html and "op:'clear'" in html, "واگردِ حذف تک‌رسم و حتی پاک‌کردن همه")
ok("UNDOS=[]; REDOS=[]" in html, "ریست پشته‌ی واگرد هنگام تعویض تایم‌فریم")
ok("let REDO = [];" not in html, "پشته‌ی قدیمی REDO حذف شد")

print("— واگرد/ازنو: معنای درست erase در doRedo (رفع باگ تکرار رسم)")
_undo_erase = "else if(op.op==='erase'){ DRAWINGS.splice(Math.min(op.idx, DRAWINGS.length), 0, op.d); }"
_redo_erase = "else if(op.op==='erase'){ DRAWINGS.splice(Math.min(op.idx, DRAWINGS.length), 1); }"
ok(html.count(_undo_erase) == 1 and html.count(_redo_erase) == 1,
   "واگردِ erase → درج · ازنویِ erase → حذف (قبل از رفع: ازنو هم درج می‌کرد و رسم تکثیر می‌شد)")

print("— انتخاب و جابه‌جایی رسم‌ها با نشانگر (سبک تریدینگ‌ویو)")
ok("let selIdx=-1, drag=null;" in html, "وضعیت انتخاب/درگ")
ok("function drawSel(" in html and "function handleHit(" in html and "function handlesOf(" in html,
   "دستگیره‌های انتخاب (p1/p2/p3) + هیت‌تست دستگیره")
ok("function applyDelta(" in html and "function cpDraw(" in html,
   "جابه‌جایی همه‌ی نقاط با دلتا + کپی عمیق (بدون رانش)")
ok("op.op==='move'){ if(op.idx>=0 && op.idx<DRAWINGS.length) DRAWINGS[op.idx]=op.before; }" in html,
   "واگردِ جابه‌جایی")
ok("op.op==='move'){ if(op.idx>=0 && op.idx<DRAWINGS.length) DRAWINGS[op.idx]=op.after; }" in html,
   "ازنویِ جابه‌جایی")
ok("mainPane.addEventListener('pointerdown'" in html and html.count("}, true);") >= 3,
   "رهگیری در فاز capture — کلیک خالی = پن عادی چارت، کلیک روی رسم = انتخاب")
ok("e.stopPropagation()" in html and "mainPane.setPointerCapture" in html,
   "جلوگیری از پن هنگام درگ رسم + قفل نشانگر")
ok("op:'move', idx:drag.idx, before:drag.orig" in html, "ثبت عملیات move در پشته با نسخه‌ی قبل/بعد")
ok("selIdx=DRAWINGS.length-1" in html, "رسم تازه بلافاصله انتخاب می‌شود")
ok("if(selIdx===i) selIdx=-1; else if(selIdx>i) selIdx--;" in html,
   "انتخاب پس از حذف رسم جابه‌جا/خنثی می‌شود")
ok("نشانگر — کلیک روی رسم: انتخاب و جابه‌جایی" in html, "راهنمای تازه‌ی نشانگر در منوی ابزارها")

print("— روکش‌های خودکار قابل خاموش‌کردن")
ok("zones:true, plines:true" in html, "پیش‌فرض روشن: نواحی + خطوط سیگنال")
ok("نواحی FVG/BVG" in html and "خطوط سیگنال (ورود/ضرر/هدف)" in html, "دو کلید در منوی اندیکاتورها")
ok("S.ind.zones===false" in html, "کلید نواحی در drawZones اعمال می‌شود")
ok("function applySigLines(" in html and "applySigLines(); return;" in html,
   "کلید خطوط سیگنال → applySigLines بدون بازسازی چارت")
ok("let sigLines=[]" in html and "sigLines.push(mainSeries.createPriceLine" in html,
   "خطوط سیگنال جدای خطوط پیوت")
ok("removePriceLine" in html, "حذف واقعی خطوط سیگنال هنگام خاموش‌کردن")

print("— صحت و عملکرد JS (node)")
import json as _json
import re as _re
import subprocess as _sp
import tempfile as _tf  # noqa: E402

_scripts = _re.findall(r"<script>(.*?)</script>", html, _re.S)
try:
    with _tf.NamedTemporaryFile("w", suffix=".js", delete=False) as _f:
        _f.write(_scripts[-1]); _appjs = _f.name
    _chk = _sp.run(["node", "--check", _appjs], capture_output=True, text=True, timeout=60)
    ok(_chk.returncode == 0, f"سینتکس JS اپ (node --check) {_chk.stderr.strip()[:120]}")

    _m = _re.search(r"(/\* ---------- تشخیص برخورد.*?)(?=let pend=null)", html, _re.S)
    ok(bool(_m), "بلاک هیت‌تست در HTML تولیدی")
    if _m:
        _harness = (
            "const DRAWINGS = ["
            "{type:'hline', p1:{t:null, price:120}},"
            "{type:'fib', p1:{t:1, price:100}, p2:{t:3, price:90}},"
            "{type:'trend', p1:{t:1, price:150}, p2:{t:3, price:160}},"
            "{type:'brush', pts:[{t:1,price:130},{t:2,price:131},{t:3,price:130.5}]},"
            "{type:'posL', p1:{t:2, price:105}, p2:{t:2, price:100}, p3:{t:2, price:115}}"
            "];\n"
            "function xOfT(t){ return t*10; }\n"
            "function yOf(p){ return 200 - p; }\n"
            "const FIB_LV = [[0,'#a'],[0.5,'#b'],[1,'#c']];\n"
            "function dist(a,b){ return Math.sqrt(Math.pow(a.x-b.x,2)+Math.pow(a.y-b.y,2)); }\n"
            "const octx = { measureText: function(s){ return {width: String(s||'').length*6}; }, font: '' };\n"
            + _m.group(1) +
            "\nconst r = {"
            "hline: hitTest(500, 80),"
            "fib_mid: hitTest(20, 105),"
            "fib_far_x: hitTest(500, 105),"
            "trend_on: hitTest(20, 45),"
            "trend_off: hitTest(45, 45),"
            "brush_hit: hitTest(30, 70),"
            "pos_entry: hitTest(100, 95),"
            "none: hitTest(500, 5)"
            "};\nconsole.log(JSON.stringify(r));\n"
        )
        _run = _sp.run(["node", "-e", _harness], capture_output=True, text=True, timeout=60)
        _r = _json.loads(_run.stdout.strip())
        for _k, _v in {"hline": 0, "fib_mid": 1, "fib_far_x": -1, "trend_on": 2,
                       "trend_off": -1, "brush_hit": 3, "pos_entry": 4, "none": -1}.items():
            ok(_r.get(_k) == _v, f"hitTest {_k} → {_v} (دریافت‌شده: {_r.get(_k)})")

    _m2 = _re.search(r"(function oneShotDone\(\).*?toast\('همه‌ی رسم‌ها پاک شد'\); \})", html, _re.S)
    ok(bool(_m2), "بلاک commit/erase/undo/redo در HTML تولیدی")
    if _m2:
        _sim = (
            "var DRAWINGS=[], UNDOS=[], REDOS=[];\n"
            "function setTool(){}\nfunction buildToolsMenu(){}\n"
            "function saveDraw(){}\nfunction toast(){}\n"
            + _m2.group(1) +
            "\nconst out = [];\n"
            "commit({type:'hline', p1:{t:null, price:100}});\n"
            "commit({type:'vline', p1:{t:5, price:null}});\n"
            "out.push(['2 draw', DRAWINGS.length, UNDOS.length, REDOS.length]);\n"
            "eraseAt(0);\n"
            "out.push(['1 after erase', DRAWINGS.length, UNDOS.length, REDOS.length]);\n"
            "doUndo();\n"
            "out.push(['2 after undo', DRAWINGS.length, UNDOS.length, REDOS.length]);\n"
            "doRedo();\n"
            "out.push(['1 after redo', DRAWINGS.length, UNDOS.length, REDOS.length]);\n"
            "clearAll();\n"
            "out.push(['0 after clear', DRAWINGS.length, UNDOS.length, REDOS.length]);\n"
            "doUndo();\n"
            "out.push(['1 after clear-undo', DRAWINGS.length, UNDOS.length, REDOS.length]);\n"
            "doRedo();\n"
            "out.push(['0 after clear-redo', DRAWINGS.length, UNDOS.length, REDOS.length]);\n"
            "commit({type:'hline', p1:{t:null, price:100}});\n"
            "out.push(['1 redraw hline', DRAWINGS.length, UNDOS.length, REDOS.length]);\n"
            "const mvBefore = JSON.parse(JSON.stringify(DRAWINGS[0]));\n"
            "DRAWINGS[0].p1.price = 105;\n"
            "UNDOS.push({op:'move', idx:0, before:mvBefore, after:JSON.parse(JSON.stringify(DRAWINGS[0]))});\n"
            "out.push(['after move-op', DRAWINGS.length, UNDOS.length, REDOS.length]);\n"
            "const prices = [mvBefore.p1.price];\n"
            "doUndo();\n"
            "prices.push(DRAWINGS[0].p1.price);\n"
            "out.push(['after move-undo', DRAWINGS.length, UNDOS.length, REDOS.length]);\n"
            "doRedo();\n"
            "prices.push(DRAWINGS[0].p1.price);\n"
            "out.push(['after move-redo', DRAWINGS.length, UNDOS.length, REDOS.length]);\n"
            "console.log(JSON.stringify({rows: out, prices: prices}));\n"
        )
        _run2 = _sp.run(["node", "-e", _sim], capture_output=True, text=True, timeout=60)
        _sim2 = _json.loads(_run2.stdout.strip())
        _rows, _prices = _sim2["rows"], _sim2["prices"]
        _expect = [(2, 2, 0), (1, 3, 0), (2, 2, 1), (1, 3, 0), (0, 4, 0), (1, 3, 1), (0, 4, 0),
                   (1, 5, 0), (1, 6, 0), (1, 5, 1), (1, 6, 0)]
        for _row, _exp in zip(_rows, _expect):
            _got = tuple(_row[1:])
            ok(_got == _exp, f"پشته‌ی عملیات «{_row[0]}» → {_exp} (دریافت‌شده: {_got})")
        ok(_prices == [100, 100, 105], f"واگرد/ازنوی جابه‌جایی قیمت را برمی‌گرداند {_prices}")

    _m3 = _re.search(r"(function applyDelta\(d, dt, dp\)\{.*?\n\})", html, _re.S)
    ok(bool(_m3), "بلاک applyDelta در HTML تولیدی")
    if _m3:
        _adj = (
            _m3.group(1) +
            "\nconst res = [];\n"
            "const df = {type:'fib', p1:{t:100, price:50}, p2:{t:300, price:40}, p3:null};\n"
            "applyDelta(df, 60, -5);\n"
            "res.push([df.p1.t, df.p1.price, df.p2.t, df.p2.price, df.p3]);\n"
            "const dh = {type:'hline', p1:{t:null, price:100}};\n"
            "applyDelta(dh, 60, -5);\n"
            "res.push([dh.p1.t, dh.p1.price]);\n"
            "const dv = {type:'vline', p1:{t:100, price:null}};\n"
            "applyDelta(dv, 60, -5);\n"
            "res.push([dv.p1.t, dv.p1.price]);\n"
            "const db = {type:'brush', pts:[{t:1, price:2},{t:3, price:4}]};\n"
            "applyDelta(db, 10, 1);\n"
            "res.push([db.pts[0].t, db.pts[1].price]);\n"
            "console.log(JSON.stringify(res));\n"
        )
        _run3 = _sp.run(["node", "-e", _adj], capture_output=True, text=True, timeout=60)
        _res = _json.loads(_run3.stdout.strip())
        ok(_res[0] == [160, 45, 360, 35, None], f"فیبوناچی: هر دو نقطه جابه‌جا {_res[0]}")
        ok(_res[1] == [None, 95], f"خط افقی: فقط قیمت (t=null می‌ماند) {_res[1]}")
        ok(_res[2] == [160, None], f"خط عمودی: فقط زمان (price=null می‌ماند) {_res[2]}")
        ok(_res[3] == [11, 5], f"قلم آزاد: همه‌ی pts جابه‌جا {_res[3]}")
except FileNotFoundError:
    print("  ⚠ node در دسترس نیست — تست‌های JS رد شد")

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
