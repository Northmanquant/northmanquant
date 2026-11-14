# -*- coding: utf-8 -*-
"""قراردادِ پیش‌ثبت‌شده‌ی ارتقای کرونوس — فازِ سه‌ی نقشه‌راهِ گزارشِ کرونوس.

این قانون قبل از دیدنِ نتیجه‌ی کاملِ دروازه (۲۰۰ جلسه‌ی مدلِ واقعی) نوشته شد و
با کامیت در گیتِ مخزن قفل گشت. بعد از پر شدنِ دروازه فقط اجرا می‌شود، نه تفسیر —
همان منطقِ «پیش‌ثبت‌سازی» در پژوهش که جلوی توجیهِ بعد از نتیجه را می‌گیرد.

سه حکمِ ممکن (فقط این سه، بدونِ استثنا):
  • n < ۲۰۰                              → ادامه‌ی جمع‌آوری (حکمِ نداریم)
  • n ≥ ۲۰۰ و هم‌جهتیِ ≥ ۵۵٪              → ارتقا: سایه عضوِ هفتم می‌شود
  • n ≥ ۲۰۰ و هم‌جهتیِ < ۵۵٪              → بازنشستگیِ صادقانه با گزارشِ دلیل

«ارتقا» یعنی دقیقاً: سمتِ شاهد از ۰ (بی‌رأی) به ±۱ تغییر می‌کند و در کورومِ
اتاقِ تیم می‌شمارد؛ کارتِ هفتم با برچسبِ «مدلِ خارجی» و ذکرِ هم‌جهتیِ داخلیِ
جلسه در پنل می‌آید. «بازنشستگی» یعنی: شاهد در حالتِ سایه می‌ماند، دلیلِ رد در
گزارشِ روزانه و CHANGELOG نوشته می‌شود و دفترِ دروازه آرشیو می‌شود نه پاک.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

# ---- ثابت‌های قفل‌شده — تغییرشان یعنی شکستنِ قرارداد --------------------
GATE_MIN_SESSIONS = 200          # جلسه‌ی «مدلِ واقعی» با سیگنالِ فعال (هر دو سمت ±۱)
GATE_MIN_AGREE_PCT = 55.0        # هم‌جهتیِ دست‌کم ۵۵٪ (همان آستانه‌ی جدولِ ۴ گزارش)
LOCKED_AT = "2026-11-14"         # تاریخِ تهرانِ ثبتِ قرارداد — قبل از نتیجه

_TEHRAN = timezone(timedelta(hours=3, minutes=30))

CONTRACT_FA = (
    # متنِ قفل‌شده با اعدادِ حرف‌اللفظی — اگر کسی ثابت‌ها را تکان داد، متن و
    # ثابت از هم جدا می‌شوند و آزمونِ t8/t9 قرمز می‌شود (خودِ قرارداد ضدِ دستکاری)
    f"📜 قراردادِ پیش‌ثبت‌شده‌ی ارتقای کرونوس (قفل‌شده در گیت، {LOCKED_AT}):\n"
    "• پس از ۲۰۰ جلسه‌ی مدلِ واقعیِ سیگنال‌دار، هم‌جهتیِ ≥ ۵۵٪ → ارتقا: "
    "عضوِ هفتمِ اتاق با رأیِ ±۱ و برچسبِ «مدلِ خارجی».\n"
    "• هم‌جهتیِ < ۵۵٪ در همان تعداد → بازنشستگیِ صادقانه با گزارشِ دلیل.\n"
    "• تا پیش از آن فقط جمع‌آوری می‌شود؛ هیچ حکمی پیش‌تر از موعد داده نمی‌شود."
)


def evaluate(gate: dict) -> dict:
    """حکمِ قرارداد را از آمارِ دروازه می‌دهد — خالص و بدونِ I/O.

    gate خروجیِ kronos_witness.gate_stats() است (یا دیکته‌ی هم‌شکل برای آزمون).
    """
    checks: dict[str, Any] = {}
    reasons: list[str] = []

    if not gate.get("ok"):
        return {"verdict": "continue",
                "verdict_fa": "⏳ ادامه‌ی جمع‌آوری — آمارِ دروازه در دسترس نیست",
                "reasons_fa": [str(gate.get("error") or "خطای نامشخص")],
                "checks": {}}

    real = gate.get("real") or {}
    n = int(real.get("n") or 0)          # در _rate فقط سیگنال‌دارها شمرده می‌شوند
    rate = real.get("rate")              # None اگر هنوز جلسه‌ی سیگنال‌داری نبوده
    checks["sessions"] = n
    checks["agree_pct"] = rate

    if rate is None:
        reasons.append("هنوز هیچ جلسه‌ی سیگنال‌داری ثبت نشده — هم‌جهتی قابلِ سنجش نیست")
    else:
        reasons.append(f"هم‌جهتیِ فعلی {rate}٪ با آستانه‌ی {GATE_MIN_AGREE_PCT}٪ مقایسه شد")

    if n < GATE_MIN_SESSIONS:
        reasons.append(f"{n} از {GATE_MIN_SESSIONS} جلسه — موعدِ حکم نرسیده است")
        return {"verdict": "continue",
                "verdict_fa": "⏳ ادامه‌ی جمع‌آوری — دروازه هنوز پر نشده",
                "reasons_fa": reasons, "checks": checks}

    if rate is None:
        # قراردادِ صریح: بدونِ جلسه‌ی سیگنال‌دار، هم‌جهتی سنجیدنی نیست —
        # نه ارتقا، نه بازنشستگی؛ جمع‌آوری ادامه می‌یابد
        reasons.append("هیچ جلسه‌ی سیگنال‌داری در دفتر نیست — حکمِ هم‌جهتی ممکن نشد")
        return {"verdict": "continue",
                "verdict_fa": "⏳ ادامه‌ی جمع‌آوری — هم‌جهتی سنجیدنی نیست",
                "reasons_fa": reasons, "checks": checks}

    if rate >= GATE_MIN_AGREE_PCT:
        reasons.append("قرارداد: ارتقا — شاهد عضوِ هفتم می‌شود (سمتِ ±۱، برچسبِ «مدلِ خارجی»)")
        return {"verdict": "promote",
                "verdict_fa": "✅ دروازه گذشت — ارتقا طبقِ قراردادِ قفل‌شده",
                "reasons_fa": reasons, "checks": checks}

    reasons.append("قرارداد: بازنشستگیِ صادقانه — سایه می‌ماند و دلیلِ رد ثبت می‌شود")
    return {"verdict": "retire",
            "verdict_fa": "❌ دروازه نگذشت — بازنشستگی طبقِ قراردادِ قفل‌شده",
            "reasons_fa": reasons, "checks": checks}


def today_stats(path: Optional[str] = None,
                now: Optional[datetime] = None) -> dict:
    """جلساتِ «امروزِ تهران» از دفتر — فقط مدلِ واقعی؛ برای خطِ گزارشِ روزانه."""
    from core import kronos_witness as KW

    p = path or KW.log_path()
    now = now or datetime.now(_TEHRAN)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_TEHRAN)  # naive = وقتِ دیوارِ تهران
    today = now.astimezone(_TEHRAN).date()
    n = sig = agree = 0
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("backend") != "kronos":
                    continue
                ts = e.get("ts") or ""
                try:
                    dt = datetime.fromisoformat(str(ts))
                except ValueError:
                    continue
                if dt.tzinfo is None:
                    # دفتر به وقتِ دیوارِ تهران نوشته می‌شود (naive = تهران)
                    dt = dt.replace(tzinfo=_TEHRAN)
                day = dt.astimezone(_TEHRAN).date()
                if day != today:
                    continue
                n += 1
                if (e.get("signal_active") and e.get("kronos_side") in (1, -1)
                        and e.get("team_side") in (1, -1)):
                    sig += 1
                    if int(e["kronos_side"]) == int(e["team_side"]):
                        agree += 1
    except FileNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001 — خواندنِ دفتر نباید گزارش را بشکند
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "n": n, "sig": sig, "agree": agree}


def telegram_line(gate: Optional[dict] = None,
                  today: Optional[dict] = None,
                  now: Optional[datetime] = None) -> Optional[str]:
    """یک خطِ صادقانه برای گزارشِ روزانه‌ی تلگرام — هیچ‌وقت استثنا نمی‌دهد."""
    try:
        if gate is None:
            from core import kronos_witness as KW
            gate = KW.gate_stats()
        if today is None:
            today = today_stats(now=now)
        if not gate.get("ok"):
            return None
        real = gate.get("real") or {}
        n = int(real.get("n") or 0)
        rate = real.get("rate")

        parts = ["🔮 سایه‌ی کرونوس — هنوز حقِ رأی ندارد"]
        if today.get("ok") and int(today.get("n") or 0) > 0:
            parts.append(f"امروز {today['n']} جلسه")
            if int(today.get("sig") or 0) > 0:
                parts.append(f"هم‌جهتیِ {today['agree']}/{today['sig']}")
        if gate.get("gate_pass"):
            parts.append(f"درگاهِ ارتقا: {n}/۲۰۰ ✅")
        else:
            parts.append(f"دروازه‌ی ارتقا: {n}/۲۰۰"
                         + (f" ({rate}٪)" if rate is not None else ""))
        parts.append(f"آستانه: ≥{str(GATE_MIN_AGREE_PCT).rstrip('0').rstrip('.') or '0'}٪")
        return " · ".join(parts)
    except Exception:  # noqa: BLE001 — خطِ سایه هرگز گزارش را نمی‌شکند
        return None
