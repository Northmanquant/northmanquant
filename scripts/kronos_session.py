# -*- coding: utf-8 -*-
"""scripts/kronos_session.py — جلسه‌گیرِ paper برای دروازه‌ی فازِ یکِ شاهدِ کرونوس
================================================================================
درخواستِ کاربر: «همشون انجام بده» — یعنی مدلِ واقعی راه بیفتد و جلسه‌های
paper-trade برای دروازه‌ی «هم‌جهتیِ >۵۵٪ روی ۲۰۰ جلسه» (جدول ۴ گزارشِ کرونوس)
شروع به جمع شدن کنند.

هر «جلسه» = یک اجرای کاملِ اتاقِ تیم روی کندلِ زنده‌ی صرافی + شاهدِ کرونوس +
ثبتِ یک سطر در core/data/kronos_log.jsonl. فقط جلساتِ ادعای جهت‌دار واردِ
آمارِ دروازه می‌شوند؛ بقیه ثبت می‌شوند که تاریخچه کامل بماند.

اجرا (مدلِ واقعی — پیش‌نیازها را scripts/setup_kronos.py برپا می‌کند):
  export KRONOS_BACKEND=kronos KRONOS_REPO=/مسیرِ/کلونِ/Kronos
  python scripts/kronos_session.py                       # ۶ نمادِ روزِ جاری از چرخش
  python scripts/kronos_session.py --rotate 10           # ده نماد
  python scripts/kronos_session.py --symbols BTC-USDT,ETH-USDT --interval 4hour
  python scripts/kronos_session.py --offline             # شبیه‌سازِ آفلاین (بدونِ مدل)

exit همیشه 0 — جابِ Actions هرگز قرمز نمی‌شود؛ خطاها فقط در خروجی گزارش می‌شوند.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

from core import team_room as TR  # noqa: E402
from core import kronos_witness as KW  # noqa: E402
from core.team_daily import CANDIDATES  # noqa: E402 — یک منبعِ حقیقت برای چرخش


def rotate(day: int, n: int) -> list[str]:
    """چرخشِ قطعیِ نمادها بر پایه‌ی روزِ سال — هر روز پنجره‌ای جدید از همان لیست."""
    n = max(1, min(int(n), len(CANDIDATES)))
    start = int(day) % len(CANDIDATES)
    return [CANDIDATES[(start + i) % len(CANDIDATES)] for i in range(n)]


def run_one(symbol: str, interval: str, exchange: str, log: str | None) -> bool:
    """یک جلسه‌ی کامل + ثبت — برمی‌گرداند که ثبت شد یا نه (هرگز exception بالا نمی‌دهد)."""
    try:
        room = TR.investigate(exchange=exchange, symbol=symbol, interval=interval,
                              with_news=False, with_witness=True)
        if not room.get("ok"):
            print(f"  ⚠️ {symbol}: جلسه برنیامد — {room.get('error', 'خطای نامشخص')}")
            return False
        res = KW.log_session(room, path=log)
        if not res.get("logged"):
            print(f"  ⚠️ {symbol}: ثبت نشد — {res.get('error')}")
            return False
        e, pred = res["entry"], ((room.get("agents") or {}).get("kronos") or {}).get("pred") or {}
        side_fa = {1: "↑", -1: "↓", 0: "—"}[int(e.get("kronos_side") or 0)]
        team_fa = {1: "↑", -1: "↓", 0: "—"}[int(e.get("team_side") or 0)]
        print(f"  ✅ {symbol}: قیمت={room.get('price')} · طرح={room['plan'].get('status')} · "
              f"چارت={team_fa} · کرونوس={side_fa} ({e.get('kronos_agree_pct')}٪ هم‌جهتیِ داخلی) · "
              f"پشتیبان={e.get('backend')} · حکم={e.get('verdict_state')}")
        if pred.get("note_fa"):
            print(f"     ↳ {pred['note_fa']}")
        return True
    except Exception as exc:  # noqa: BLE001 — جلسه‌ی نبود، بچ را نمی‌بُرد
        print(f"  ⚠️ {symbol}: {type(exc).__name__}: {exc}")
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="جلسه‌گیرِ paper شاهدِ کرونوس")
    ap.add_argument("--symbols", help="نمادها با کاما (پیش‌فرض: چرخشِ روزانه)")
    ap.add_argument("--interval", default=TR.INTERVAL_DEFAULT, choices=TR.INTERVALS)
    ap.add_argument("--exchange", default=TR.EXCHANGE_DEFAULT)
    ap.add_argument("--rotate", type=int, default=6,
                    help="تعدادِ نمادِ چرخشیِ روزانه (وقتی --symbols نداده باشد)")
    ap.add_argument("--limit", type=int, default=400, help="تعدادِ کندلِ زمینه")
    ap.add_argument("--offline", action="store_true", help="شبیه‌سازِ آفلاین به‌جای مدلِ واقعی")
    ap.add_argument("--log", help="مسیرِ دفترِ دروازه (پیش‌فرض: core/data/kronos_log.jsonl)")
    args = ap.parse_args()

    if args.offline:
        os.environ["KRONOS_BACKEND"] = "offline"
    backend = KW._cfg()["backend"]
    log = args.log or KW.log_path()

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        from datetime import datetime
        day = datetime.now().timetuple().tm_yday
        symbols = rotate(day, args.rotate)

    print(f"== شاهدِ کرونوس — جلسه‌ی paper ==\nپشتیبان: {backend} · تایم‌فریم: {args.interval} · "
          f"صرافی: {args.exchange} · دفتر: {log}")
    print(f"نمادها ({len(symbols)}): {', '.join(symbols)}")

    n_ok = 0
    for sym in symbols:
        n_ok += 1 if run_one(sym, args.interval, args.exchange, log) else 0
        print(f"  … {n_ok}/{len(symbols)} ثبت شد")

    g = KW.gate_stats(path=log)
    if g.get("ok"):
        real, stub = g.get("real") or {}, g.get("stub") or {}
        print(f"\n== دروازه‌ی فازِ یک ==")
        print(f"مدلِ واقعی: {real.get('n')}/۲۰۰ جلسه · هم‌جهتیِ {real.get('rate', '—')}٪ (دروازه: >۵۵٪)")
        print(f"شبیه‌ساز: {stub.get('n')} جلسه · هم‌جهتیِ {stub.get('rate', '—')}٪ (تمرینِ لوله‌کشی)")
        print(f"وضعیت: {g.get('gate_fa')}")
    print("== پایان — exit 0 ==")


if __name__ == "__main__":
    main()
