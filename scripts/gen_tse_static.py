# -*- coding: utf-8 -*-
"""ساخت core/data/tse_symbols.json — فهرست داخلی نمادهای بورس تهران
=================================================================
منبع داده: pytse-client 0.19.1 متن‌باز (همان کتابخانه‌ای که الگوی پارسِ
core/tse.py از آن برداشته شده):
  https://github.com/Glyphack/pytse-client/blob/master/pytse_client/data/symbols_name.json

هدف: جست‌وجوی نماد بدون هیچ شبکه‌ای — حتی وقتی سرورهای TSETMC از سرور ابری
(Streamlit Community Cloud) در دسترس نیستند، کاربر بتواند نماد را پیدا کند.
ins_codeها کد رسمی و پایدار TSETMC هستند (نمونه‌ی راستی‌آزمایی‌شده:
فولاد=46348559193224090 · فملی=35425587644337450).

استفاده (از ریشه‌ی مخزن):
    python scripts/gen_tse_static.py [مسیر symbols_name.json خام]
خروجی: core/data/tse_symbols.json (مرتب، بدون تکرار، ~۱۴۰۰ ردیف)
"""
import json
import os
import sys

src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/symbols_name.json"
with open(src, "r", encoding="utf-8") as fh:
    d = json.load(fh)

rows = []
seen = set()
for sym, v in d.items():
    ins = str(v.get("index") or "").strip()
    if not sym.strip() or not ins.isnumeric():
        continue
    key = (sym.strip(), ins)
    if key in seen:
        continue
    seen.add(key)
    rows.append({
        "symbol": sym.strip(),
        "ins": ins,
        "name": str(v.get("name") or "").strip(),
        "isin": str(v.get("code") or "").strip(),
    })

rows.sort(key=lambda r: r["symbol"])

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "core", "data", "tse_symbols.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as fh:
    json.dump(rows, fh, ensure_ascii=False, separators=(",", ":"))

print(f"{len(rows)} symbols -> {out} ({os.path.getsize(out)} bytes)")
