#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/test_app_sections.py — رندرِ واقعیِ اپِ تک‌صفحه‌ای + سوییچ به «🎨 چارت خصوصی»
اجرا: python3 scripts/test_app_sections.py
تحلیل زنده باید بدونِ چارتِ قدیمی رندر شود و بخشِ خصوصیِ چارت بدونِ exception بالا بیاید."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from streamlit.testing.v1 import AppTest  # noqa: E402

SECTION = "🎨 چارت خصوصی"

# ---- ۱) رندرِ پیش‌فرض — تحلیل زنده (حالا بدونِ چارتِ جاسازی‌شده) -------------
at = AppTest.from_file("app.py", default_timeout=300)
at.run()
if at.exception:
    print(f"✗ رندرِ پیش‌فرض (تحلیل زنده): {at.exception[0].value}")
    sys.exit(1)
print("✓ رندرِ پیش‌فرض (تحلیل زنده) — تمیز، بدونِ exception")

md = "\n".join(str(e.value) for e in at.markdown) + "\n" + \
     "\n".join(str(e.value) for e in at.caption)
print("✓ اشاره‌گرِ «چارت خصوصی» در تحلیل زنده هست"
      if "چارت خصوصی" in md else "⚠ اشاره‌گر در متن‌های رندرشده پیدا نشد (هشدار)")

# ---- ۲) سوییچ به بخشِ خصوصی ---------------------------------------------------
r = next((x for x in at.radio if SECTION in (x.options or [])), None)
if r is None:
    print("✗ رادیوی بخش‌ها گزینه‌ی «چارت خصوصی» ندارد")
    sys.exit(1)
r.set_value(SECTION)
at.run()
if at.exception:
    print(f"✗ بخشِ چارت خصوصی: {at.exception[0].value}")
    sys.exit(1)
labels = [str(s.value) for s in at.subheader]
print("✓ بخشِ «🎨 چارت خصوصی» رندر شد — تمیز"
      if any("چارتِ خصوصی" in l for l in labels) else f"⚠ subheader پیدا نشد — {labels[:4]}")

# ---- ۳) موتورِ یکپارچه: رادیوی «موتورِ چارت» باید حذف شده باشد ----------------
mode_radio = next((x for x in at.radio
                   if any("موتورِ خودم" in str(o) for o in (x.options or []))), None)
if mode_radio is not None:
    print("✗ رادیوی دوحالته هنوز هست — ادغام کامل نشده")
    sys.exit(1)
print("✓ رادیوی دوحالته حذف شد — موتورِ یکپارچه")

# ---- ۴) موتورِ یکپارچه رندر می‌شود: متریک‌ها بالای چارت ------------------------
metrics = [str(m.label) for m in at.metric]
print("✓ موتورِ یکپارچه (زومِ ＋/－ + خطوطِ پلن/FVG) رندر شد — تمیز"
      if any("RSI 14" in l for l in metrics)
      else f"⚠ متریکِ RSI پیدا نشد — {metrics[:6]}")

# ---- ۵) خروجیِ HTMLِ موتور: دکمه‌های زوم و ابزارهای TV -------------------------
from core.tv_chart import build_tv_chart_html  # noqa: E402
_html = build_tv_chart_html(
    candles=[[1700000000, 1, 2, 0.5, 1.5, 10]],
    tfs={"1hour": [[1700000000, 1, 2, 0.5, 1.5, 10]]},
    base_tf="1hour", symbol="BTC-USDT", zones=[], levels=[],
    title="BTC-USDT · 1hour", dec=2)
need = ("btnZin", "btnZout", "zoomStep", "btnFit", "btnFull", "btnNow",
        "btnLive", "livePoll", "liveApply", "liveRepaint",
        "btnPct", "PriceScaleMode.Percentage",
        "btnGear", "pdlg", "IND_P_DEF", "clearCalc", "saveIndP",
        "drawVP", "پروفایلِ حجمِ بازه‌ی دید")
if all(k in _html for k in need):
    print("✓ نوارِ زوم ＋/－ · داده‌ی زنده · ٪ · ⚙ پارامترها · پروفایلِ حجم — همه در خروجیِ موتور")
else:
    missing = [k for k in need if k not in _html]
    print(f"✗ در HTMLِ موتور نیست: {missing}")
    sys.exit(1)

print("✅ app_sections پاس شد — هر سه مسیر سبز")
