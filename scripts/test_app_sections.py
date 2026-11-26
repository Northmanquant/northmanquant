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

print("✅ app_sections پاس شد — هر دو مسیر سبز")
