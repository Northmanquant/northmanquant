#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gen_econ_snapshot.py — اسنپ‌شات محلیِ تقویم‌های رسمی BLS/BEA

BLS از IPهای دیتاسنتر (Streamlit Cloud و همین سندباکس) دسترسی را می‌بندد (۴۰۳)؛
این اسکریپت فایل ICS رسمی هر منبع را — مستقیم یا از مسیر آینه‌ی همه‌منظوره —
می‌گیرد، با parser خودِ پروژه اعتبارسنجی می‌کند و به‌عنوان لایه‌ی سوم فیوز
در core/data/ ذخیره می‌کند. لایه‌ی سوم = همان الگوی tse_symbols.json.

اجرا: python3 scripts/gen_econ_snapshot.py
خروجی: core/data/bls_schedule.ics + core/data/bea_schedule.ics + econ_snapshots.json
"""
import hashlib
import json
import os
import sys
import urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.econ_calendar import CALENDARS, HEADERS, parse_ics  # noqa: E402
from core.net import get_text  # noqa: E402

MIRROR = "https://api.allorigins.win/raw?url="
DATA_DIR = os.path.join("core", "data")
SNAP_JSON = os.path.join(DATA_DIR, "econ_snapshots.json")


def fetch_text(url: str) -> str:
    """دریافت متن ICS: مستقیم، بعد آینه. خرابی = رشته‌ی خالی."""
    # ۱) مستقیم
    try:
        txt = get_text(url, headers=HEADERS, timeout=20.0, retries=0)
        if txt and "BEGIN:VCALENDAR" in txt:
            return txt
    except Exception:  # noqa: BLE001
        pass
    # ۲) آینه‌ی همه‌منظوره — همان داده‌ی رسمی از مسیر دیگر
    try:
        txt = get_text(MIRROR + urllib.parse.quote(url, safe=""),
                       headers=HEADERS, timeout=25.0, retries=0)
        if txt and "BEGIN:VCALENDAR" in txt:
            return txt
    except Exception:  # noqa: BLE001
        pass
    return ""


def main() -> int:
    os.makedirs(DATA_DIR, exist_ok=True)
    meta = {}
    old = {}
    if os.path.exists(SNAP_JSON):
        try:
            old = json.load(open(SNAP_JSON, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            old = {}
    ok_all = True
    for src, conf in CALENDARS.items():
        txt = fetch_text(conf["ics"])
        if not txt:
            # شبکه هر دو مسیر شکست خورد — اسنپ‌شات قبلی دست‌نخورده می‌ماند
            print(f"✗ {src}: هیچ مسیری پاسخ نداد — اسنپ‌شات قبلی حفظ شد")
            ok_all = False
            continue
        try:
            events = parse_ics(txt, src, conf["ics"])
        except Exception as e:  # noqa: BLE001 — داده‌ی خراب ذخیره نمی‌شود
            print(f"✗ {src}: پارس ناموفق ({e}) — اسنپ‌شات قبلی حفظ شد")
            ok_all = False
            continue
        path = os.path.join(DATA_DIR, f"{src}_schedule.ics")
        with open(path, "w", encoding="utf-8") as f:
            f.write(txt)
        meta[src] = {
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "url": conf["ics"],
            "events": len(events),
            "sha256": hashlib.sha256(txt.encode("utf-8")).hexdigest()[:16],
        }
        old[src] = meta[src]
        print(f"✓ {src}: {len(events)} رویداد → {path} ({meta[src]['sha256']})")
    if old:
        with open(SNAP_JSON, "w", encoding="utf-8") as f:
            json.dump(old, f, ensure_ascii=False, indent=2, sort_keys=True)
        print(f"✓ متادیتا → {SNAP_JSON}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
