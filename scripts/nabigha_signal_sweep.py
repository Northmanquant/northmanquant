"""نقشه‌ی نشاطِ سیگنال — کدام نماد×تایم‌فریم چارتِ حکم‌شان زنده است؟
================================================================
درسِ ۱۸ جلسه‌ی اول: چرخشِ تقویمیِ نمادها روی نمادهایِ کم‌نوسان، طرحِ «⏸ انتظار»
می‌دهد و جلسه برای دروازه‌ی ۲۰۰ سیگنال‌دار هدر می‌رود. این اسکریپت روی
استخرِ مشترک (core.signal_map.get_pool: اصلی‌هایِ چرخش + پرگردش‌هایِ زنده‌ی
KuCoin) × سه تایم‌فریم، همان مسیرِ واقعیِ چارتِ اپ را صدا می‌زند
(app_base.setup_plan — ستاپِ واک‌فوروار-تأییدشده + دروازه‌ی QC) و نقشه‌ی
نشاط را در core/data/nabigha_signal_map.json می‌نویسد — نقشه‌ای که «هر دو»
جلسه‌گیر (کرونوس و نبیه) با --hot از core.signal_map می‌خوانند (با فال‌بکِ
امن به چرخشِ تقویمی).

exit همیشه 0 — نقشه اطلاعاتی است؛ نبودش فقط یعنی جلسه‌گیر به چرخشِ عادی برمی‌گردد.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TEHRAN = timezone(timedelta(hours=3, minutes=30))
INTERVALS = ("1hour", "4hour", "1day")
EXCHANGE = "OKX"
LIMIT = 400

def main() -> int:
    from app_base import add_indicators, fetch_candles, setup_plan  # noqa: E402 — سنگین داخلِ main
    from core.signal_map import get_pool  # noqa: E402 — استخرِ مشترکِ هر دو موتور

    pool = get_pool()
    combos: list[dict] = []
    print("== نقشه‌ی نشاطِ سیگنال — استخرِ", len(pool), "نماد ×", len(INTERVALS), "تایم‌فریم ==")
    print(f"{'نماد':<14}{'1hour':<26}{'4hour':<26}{'1day'}")
    by_symbol: dict[str, dict[str, dict]] = {}
    for sym in pool:
        row = {}
        for itv in INTERVALS:
            try:
                d = fetch_candles(EXCHANGE, sym, itv, limit=LIMIT)
                if d is None or len(d) < 60:
                    row[itv] = {"active": False, "why": "کندلِ ناکافی"}
                    continue
                # همان غنی‌سازیِ مسیرِ واقعیِ اپ — دروازه‌ی QC ستون‌های
                # rsi/ema50/ema200/bb را می‌خواهد و fetch_candles خام می‌دهد
                # (درسِ رانِ اولِ سوییپ: ۴۲ خانه را QC ساقط کرد)
                plan = setup_plan(add_indicators(d.copy()))
                active = plan.get("status") == "active"
                row[itv] = {
                    "active": bool(active),
                    "mode": plan.get("mode") or "",
                    "side": 1 if active and str(plan.get("direction", "")).startswith("لانگ") else -1 if active else 0,
                    "confidence": plan.get("confidence") or 0,
                    "why": str(plan.get("why", ""))[:90],
                }
            except Exception as e:  # noqa: BLE001 — یک خانه خراب، نقشه را نمی‌بُرد
                row[itv] = {"active": False, "why": f"{type(e).__name__}: {e}"[:60]}
        by_symbol[sym] = row
        def cell(itv: str) -> str:
            r = row[itv]
            if r.get("active"):
                arrow = "↑" if r.get("side") == 1 else "↓"
                return f"✅ {arrow} {r.get('mode')} ({r.get('confidence')}٪)"
            return f"⏸ انتظار"
        print(f"{sym:<14}{cell('1hour'):<26}{cell('4hour'):<26}{cell('1day')}")

    for sym, row in by_symbol.items():
        for itv, r in row.items():
            combos.append({"symbol": sym, "interval": itv, **r})

    active_n = sum(1 for c in combos if c.get("active"))
    hot = [c["symbol"] for c in combos if c.get("active")]
    snap = {
        "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ts_tehran": datetime.now(TEHRAN).isoformat(timespec="seconds"),
        "exchange": EXCHANGE, "intervals": list(INTERVALS),
        "active_count": active_n, "total": len(combos), "combos": combos,
    }
    datadir = os.path.join(ROOT, "core", "data")
    os.makedirs(datadir, exist_ok=True)
    with open(os.path.join(datadir, "nabigha_signal_map.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)

    print(f"\n== جمع‌بندی == ستاپِ فعال: {active_n}/{len(combos)} خانه"
          + (f" · نمادهایِ داغ: {', '.join(sorted(set(hot)))}" if hot else " · هیچ خانه‌ای زنده نیست — جلسه‌گیر به چرخشِ عادی برمی‌گردد"))
    print("→ core/data/nabigha_signal_map.json")
    return 0

if __name__ == "__main__":
    sys.exit(main())
