# -*- coding: utf-8 -*-
"""scripts/nabigha_session.py — جلسه‌گیرِ سایه‌ی موتورِ نبیه
=================================================================
درخواستِ کاربر: «چیزی شبیه کرونوس بساز» — همان نظم، مالِ خودمان. هر
«جلسه» = کندل‌های زنده‌ی صرافی + پیش‌بینیِ قطعیِ نبیه + (پیش‌فرض) یک
اجرای اتاقِ تیم روی همان کندل‌ها برای مقایسه با سیگنالِ چارت + ثبتِ
append-only در core/data/nabigha_log.jsonl.

نبیه در حالتِ سایه است: هیچ اثری در حکمِ اتاق ندارد؛ دفترش جدا جمع
می‌شود و گرِیدرِ مشترک (scripts/paper_grade.py) بعداً hit-rate واقعی‌اش
را می‌سنجد.

اجرا:
  python scripts/nabigha_session.py                       # ۶ نمادِ چرخشی
  python scripts/nabigha_session.py --symbols BTC-USDT --interval 4hour
  python scripts/nabigha_session.py --engine-only         # بچِ سریعِ بی‌اتاق

exit همیشه 0 — جابِ Actions هرگز قرمز نمی‌شود؛ خطاها فقط گزارش می‌شوند.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

from core import nabigha_engine as NE  # noqa: E402
from core import kronos_witness as KW  # noqa: E402 — فقط برای log_path/INTERVALS سازگار
from core.team_daily import CANDIDATES  # noqa: E402 — یک منبعِ حقیقت برای چرخش


def rotate(day: int, n: int) -> list[str]:
    """چرخشِ قطعیِ نمادها بر پایه‌ی روزِ سال — همان الگوی جلسه‌گیرِ کرونوس."""
    n = max(1, min(int(n), len(CANDIDATES)))
    start = int(day) % len(CANDIDATES)
    return [CANDIDATES[(start + i) % len(CANDIDATES)] for i in range(n)]


def _load_env_file() -> None:
    """لودِ .envِ ریشه — همان درسِ دو بچِ هدررفته (بدونِ override)."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    except Exception:  # noqa: BLE001 — خواندنِ .env هرگز جلسه را نمی‌بُرد
        pass


def run_one(symbol: str, interval: str, exchange: str, log: str | None,
            engine_only: bool, limit: int) -> bool:
    """یک جلسه‌ی کامل + ثبت — برمی‌گرداند که ثبت شد یا نه (هرگز exception بالا نمی‌دهد)."""
    try:
        from app_base import fetch_candles  # noqa: E402 — ایمپورتِ سنگین داخلِ تابع
        d = fetch_candles(exchange, symbol, interval, limit=limit)
        if d is None or len(d) < 60:
            print(f"  ⚠️ {symbol}: کندلِ کافی نیست — جلسه ثبت نشد")
            return False
        pred = NE.predict(d)
        if not pred.get("ok"):
            print(f"  ⚠️ {symbol}: نبیه پیش‌بینی نداد — {pred.get('error')}")
            return False

        team_side, signal_active, verdict_state, price = 0, False, None, float(d["close"].iloc[-1])
        if not engine_only:
            from core import team_room as TR  # noqa: E402
            room = TR.investigate(exchange=exchange, symbol=symbol, interval=interval,
                                  with_news=False, with_witness=False, df=d, limit=limit)
            if room.get("ok"):
                team_side = NE._chart_side_of(room)
                signal_active = (room.get("plan") or {}).get("status") == "active"
                verdict_state = (room.get("verdict") or {}).get("state")
                price = room.get("price") or price

        res = NE.log_pred(symbol, interval, exchange, price, pred,
                          team_side=team_side, signal_active=signal_active,
                          verdict_state=verdict_state, path=log)
        if not res.get("logged"):
            print(f"  ⚠️ {symbol}: ثبت نشد — {res.get('error')}")
            return False
        arrow = {1: "↑", -1: "↓", 0: "—"}[int(pred["side"])]
        chart_fa = {1: "↑", -1: "↓", 0: "—"}[team_side] if team_side else "—"
        conf = pred.get("confidence_pct")
        print(f"  ✅ {symbol}: قیمت={price} · نبیه={arrow}"
              f"{' (' + str(conf) + '٪)' if conf is not None else ''} · چارت={chart_fa} · "
              f"سیگنال={'فعال' if signal_active else 'خاموش'}")
        return True
    except Exception as exc:  # noqa: BLE001 — جلسه‌ی نبود، بچ را نمی‌بُرد
        print(f"  ⚠️ {symbol}: {type(exc).__name__}: {exc}")
        return False


def main() -> None:
    _load_env_file()
    from core import team_room as TR  # noqa: E402 — INTERVALS/EXCHANGE_DEFAULT
    ap = argparse.ArgumentParser(description="جلسه‌گیرِ سایه‌ی موتورِ نبیه")
    ap.add_argument("--symbols", help="نمادها با کاما (پیش‌فرض: چرخشِ روزانه)")
    ap.add_argument("--interval", default=TR.INTERVAL_DEFAULT, choices=TR.INTERVALS)
    ap.add_argument("--exchange", default=TR.EXCHANGE_DEFAULT)
    ap.add_argument("--rotate", type=int, default=6, help="تعدادِ نمادِ چرخشیِ روزانه")
    ap.add_argument("--limit", type=int, default=400, help="تعدادِ کندلِ زمینه")
    ap.add_argument("--engine-only", action="store_true",
                    help="بدونِ اجرای اتاقِ تیم — فقط پیش‌بینی و ثبتِ نبیه (سریع)")
    ap.add_argument("--log", help="مسیرِ دفتر (پیش‌فرض: core/data/nabigha_log.jsonl)")
    args = ap.parse_args()
    log = args.log or NE.log_path()

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        from datetime import datetime
        symbols = rotate(datetime.now().timetuple().tm_yday, args.rotate)

    print(f"== نبیه — جلسه‌ی سایه ==\nتایم‌فریم: {args.interval} · صرافی: {args.exchange} · "
          f"دفتر: {log}{' · حالتِ engine-only' if args.engine_only else ''}")
    print(f"نمادها ({len(symbols)}): {', '.join(symbols)}")

    n_ok = 0
    for sym in symbols:
        n_ok += 1 if run_one(sym, args.interval, args.exchange, log,
                             args.engine_only, args.limit) else 0
        print(f"  … {n_ok}/{len(symbols)} ثبت شد")

    g = NE.gate_stats(log)
    if g.get("ok"):
        print("\n== دروازه‌ی نبیه ==")
        print(f"{g.get('gate_fa')} · {g.get('n_total')} سطرِ کل")
    print("== پایان — exit 0 ==")


if __name__ == "__main__":
    main()
