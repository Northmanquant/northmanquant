#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/check_chart_js.py — سینتکسِ JSِ موتورِ چارت با node --check
اجرا: python3 scripts/check_chart_js.py
خروجیِ build_tv_chart_html را می‌سازد، بلاکِ <script> نهایی (JS خودِ موتور) را
درمی‌آورد و سینتکسش را با node بررسی می‌کند — چون AppTest جاوااسکریپت را اجرا نمی‌کند."""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tv_chart import build_tv_chart_html  # noqa: E402

html = build_tv_chart_html(
    candles=[[1700000000 + i * 3600, 1 + i, 2 + i, 0.5 + i, 1.5 + i, 10] for i in range(50)],
    tfs={"1hour": [[1700000000 + i * 3600, 1 + i, 2 + i, 0.5 + i, 1.5 + i, 10] for i in range(50)]},
    base_tf="1hour", symbol="BTC-USDT", zones=[], levels=[],
    title="BTC-USDT · 1hour", dec=2)

parts = html.split("<script>")
if len(parts) < 3:
    print("✗ بلاک‌های <script> پیدا نشد")
    sys.exit(1)
js = parts[-1].split("</script>")[0]

if subprocess.run(["which", "node"], capture_output=True).returncode != 0:
    print("⚠ node در دسترس نیست — بررسیِ سینتکس رد شد")
    sys.exit(0)

with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(js)
    tmp = f.name
r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
os.unlink(tmp)
if r.returncode == 0:
    print(f"✓ سینتکسِ JSِ موتور ({len(js)//1024}KB) — تمیز")
else:
    print("✗ خطای سینتکس JS:\n" + (r.stderr or "")[:1200])
    sys.exit(1)
