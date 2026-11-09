#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/test_apptest_sweep.py — sweep رندر همه‌ی صفحات با AppTest (صفر-ادعا؛ رندر واقعی)
اجرا: python3 scripts/test_apptest_sweep.py
هر صفحه باید بدون exception رندر شود و بدون هشدار deprecation بماند."""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = sorted(glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pages", "*.py")))
assert len(PAGES) == 9, f"انتظار ۹ صفحه — پیدا شد: {len(PAGES)}"

FAILS = 0
for p in PAGES:
    at = AppTest.from_file(p, default_timeout=300)
    at.run()
    if at.exception:
        FAILS += 1
        print(f"  ✗ {os.path.basename(p)} — exception: {at.exception[0].value}")
        continue
    warns = [str(w.value) for w in at.warning if "deprecat" in str(w.value).lower()]
    if warns:
        FAILS += 1
        print(f"  ✗ {os.path.basename(p)} — deprecation: {warns[:2]}")
        continue
    print(f"  ✓ {os.path.basename(p)} — رندر تمیز، بدون exception و بدون deprecation")

if FAILS:
    raise SystemExit(f"FAIL: {FAILS} صفحه مشکل دارد")
print(f"\n✅ sweep همه‌ی {len(PAGES)} صفحه پاس شد")
