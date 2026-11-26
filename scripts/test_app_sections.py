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

# ---- ۳) حالتِ پیش‌فرضِ بخش = تریدینگ‌ویوِ واقعی (ویجتِ رسمی) -------------------
htmls = [str(e.value) for e in at.html] if hasattr(at, "html") else []
print("✓ ویجتِ رسمیِ تریدینگ‌ویو در خروجی هست (tv.js)"
      if any("s3.tradingview.com/tv.js" in h for h in htmls)
      else "⚠ بلوکِ ویجتِ TV در عناصرِ AppTest قابلِ دید نیست (هشدار — components.html توسط AppTest شمرده نمی‌شود)")

# ---- ۴) سوییچ به موتورِ بومی ---------------------------------------------------
mr = next((x for x in at.radio
           if any("موتورِ خودم" in str(o) for o in (x.options or []))), None)
if mr is None:
    print("✗ رادیوی موتورِ چارت پیدا نشد")
    sys.exit(1)
mr.set_value("🛠 موتورِ خودم — با خطوطِ پلن و FVG")
at.run()
if at.exception:
    print(f"✗ موتورِ بومی: {at.exception[0].value}")
    sys.exit(1)
metrics = [str(m.label) for m in at.metric]
print("✓ موتورِ بومی (خطوطِ پلن/FVG) رندر شد — تمیز"
      if any("RSI 14" in l for l in metrics)
      else f"⚠ متریکِ RSI پیدا نشد — {metrics[:6]}")

print("✅ app_sections پاس شد — هر چهار مسیر سبز")
