# -*- coding: utf-8 -*-
"""روزِ حکمِ کرونوس — اجرای قراردادِ پیش‌ثبت‌شده، بدونِ تفسیرِ تازه
====================================================================
قرارداد در core/kronos_promotion.py قفل شده (قبل از دیدنِ ۲۰۰ جلسه)؛ این
اسکریپت فقط آن را اجرا می‌کند:

  • continue  → وضعیتِ دروازه را گزارش می‌کند (کاری نمی‌کند)
  • promote   → وضعیت زنده از دفتر خوانده می‌شود؛ اتاق خودش عضوِ هفتم را
                می‌بیند — اینجا فقط اعلام و ثبت می‌شود
  • retire    → دفترِ دروازه آرشیو می‌شود (کپی، نه پاک‌کاری؛ idempotent)
                و دلیلِ رد چاپ می‌شود تا در CHANGELOG بنشیند

اجرا:  python scripts/kronos_verdict.py
خروجی: متنِ فارسی برای گزارش + کدِ خروج 0 (سبک) یا 1 (خطا)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

from core import kronos_promotion as KP  # noqa: E402
from core import kronos_witness as KW  # noqa: E402


def main() -> int:
    print(KP.CONTRACT_FA)
    print("─" * 50)
    gate = KW.gate_stats()
    if not gate.get("ok"):
        print(f"⚠️ آمارِ دروازه خوانده نشد: {gate.get('error')}")
        return 1
    real = gate.get("real") or {}
    print(f"دروازه: {real.get('n')}/۲۰۰ جلسه‌ی سیگنال‌دارِ واقعی · "
          f"هم‌جهتیِ {real.get('rate')}٪ · آستانه ≥{KP.GATE_MIN_AGREE_PCT}٪")
    st = KP.state(gate)
    print(f"حکم: {st['verdict_fa']}")
    for r in st["reasons_fa"]:
        print(f"  • {r}")

    if st["verdict"] == "retire":
        arch = KP.archive_log()
        if arch.get("archived"):
            print(f"🗄️ دفتر آرشیو شد: {arch['dest']} ({arch.get('n_rows')} سطر) — کپی، نه پاک‌کاری")
        elif arch.get("ok"):
            print(f"🗄️ آرشیو از قبل هست: {arch['dest']} — idempotent، دست نخورد")
        else:
            print(f"⚠️ آرشیو انجام نشد: {arch.get('error')}")
        print("📜 شاهد در حالتِ سایه می‌ماند؛ دلیلِ رد را در CHANGELOG بنویس.")
    elif st["verdict"] == "promote":
        print("🔮 ارتقا فعال است — عضوِ هفتم (مدلِ خارجی، رأیِ ±۱) خودکار در کوروم می‌شمارد.")
        print("   چون وضعیت زنده از دفتر خوانده می‌شود، هیچ پرچمی برای خاموش/روشن کردن نیست؛")
        print("   اگر خواستی فازِ ارتقا را تعطیل کنی، باید قرارداد را بازنویسی کنی — نه پرچم بزنی.")
    else:
        print("⏳ هنوز موعدِ حکم نیست — جمع‌آوری ادامه دارد (جاب‌های روزانه/هفتگی).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
