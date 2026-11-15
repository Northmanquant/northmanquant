# -*- coding: utf-8 -*-
"""scripts/kronos_insights.py — برداشتِ ریز از دفترِ کرونوس (CLI)
================================================================
دفترِ دروازه فقط یک عددِ کلان می‌دهد؛ اینجا همان دفتر ریز می‌شود: به
تفکیکِ تایم‌فریم/نماد/روز، رابطه‌ی اطمینانِ داخلی با هم‌جهتیِ واقعی و
streak — بدونِ شبکه و بدونِ مدل، در چند میلی‌ثانیه.

اجرا:  python scripts/kronos_insights.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

from core import kronos_insights as KI  # noqa: E402
from core import kronos_witness as KW  # noqa: E402


def main() -> int:
    try:
        g = KW.gate_stats()
        if g.get("ok"):
            real = g.get("real") or {}
            print(f"دروازه: {real.get('n')}/۲۰۰ · هم‌جهتیِ {real.get('rate')}٪ — {g.get('gate_fa')}")
    except Exception:  # noqa: BLE001 — دروازه نبود، برداشت ادامه دارد
        pass
    print(KI.report_fa())
    return 0


if __name__ == "__main__":
    sys.exit(main())
