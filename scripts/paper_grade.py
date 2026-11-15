# -*- coding: utf-8 -*-
"""scripts/paper_grade.py — گرِیدرِ پیامد برای کرونوس و نبیه
================================================================
هر پیش‌بینیِ جهت‌دارِ ثبت‌شده را با «قیمتِ بعد از افقِ N کندلی» می‌سنجد و
hit-rateِ واقعی می‌دهد — آزمونی که هم‌جهتی با چارت نمی‌سنجد، بازار می‌سنجد.

اجرا:
  python scripts/paper_grade.py                       # هر دو موتور، افقِ ۳ کندلی
  python scripts/paper_grade.py --engine nabigha --horizon 3
  python scripts/paper_grade.py --engine kronos --max-rows 50

exit همیشه 0 — خطاها فقط گزارش می‌شوند؛ رانِ بعدی ادامه می‌دهد (idempotent).
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

from core import paper_grader as PG  # noqa: E402


def _fmt_stats(st: dict) -> str:
    if not st.get("ok"):
        return f"⚠️ آمار نشد: {st.get('error')}"
    rate = f"{st['rate']}٪" if st.get("rate") is not None else "—"
    lines = [f"{st.get('engine') or 'همه'}: {st['n_graded']} نمره‌گرفته · "
             f"{st['n_decided']} تعیین‌سرنوشت · hit-rateِ {rate} ({st['hits']}/{st['n_decided']})"]
    for k, v in st.get("by_interval", {}).items():
        lines.append(f"  · {k}: {v['n']} → {v['rate']}٪")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="نمره‌دادنِ پیامد به پیش‌بینی‌های paper")
    ap.add_argument("--engine", default="all", choices=["all", "kronos", "nabigha"])
    ap.add_argument("--horizon", type=int, default=3, help="افق به تعداد کندل (پیش‌فرض ۳)")
    ap.add_argument("--deadband", type=float, default=0.0005,
                    help="باندِ مرده به نسبت (پیش‌فرض ۰٫۰۵٪)")
    ap.add_argument("--max-rows", type=int, default=200, help="سقفِ نمره‌دادن در هر ران")
    ap.add_argument("--ledger", help="مسیرِ دفترِ ورودی (پیش‌فرض: دفترِ خودِ موتور)")
    ap.add_argument("--outcomes", help="مسیرِ دفترِ پیامد (پیش‌فرض: core/data/paper_outcomes.jsonl)")
    args = ap.parse_args()

    engines = ["kronos", "nabigha"] if args.engine == "all" else [args.engine]
    for eng in engines:
        res = PG.grade_pending(eng, ledger_path=args.ledger, outcomes_file=args.outcomes,
                               horizon=args.horizon, deadband=args.deadband,
                               max_rows=args.max_rows)
        if res.get("ok"):
            print(f"== {eng}: {res['graded']} نمره گرفت · {res['skipped']} رد شد (تاریخچه‌ی ناکافی/سطرِ خراب)")
        else:
            print(f"== {eng}: ⚠️ {res.get('error')}")
        print(_fmt_stats(PG.outcomes_stats(eng, path=args.outcomes)))
    print("== پایان — exit 0 ==")


if __name__ == "__main__":
    main()
