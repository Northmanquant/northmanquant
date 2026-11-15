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
import os
import shutil
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


def _pct(v) -> str:
    """٪‌ِ تمیز برای نمایش — 50.0 → «50»، 61.5 → «61.5»."""
    return f"{float(v):g}"


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

        ev = evaluate(gate)
        parts: list[str]
        if ev["verdict"] == "retire":
            parts = ["📜 کرونوس بازنشسته شد — طبقِ قراردادِ قفل‌شده",
                     f"دلیل: هم‌جهتیِ {_pct(rate)}٪ < ۵۵٪ در {n} جلسه",
                     "سایه می‌ماند؛ دفتر آرشیو است"]
        elif ev["verdict"] == "promote":
            parts = ["🔮 کرونوس ارتقا گرفت — مدلِ خارجی با رأیِ ±۱ در کوروم",
                     f"پایه: {n} جلسه · هم‌جهتیِ {_pct(rate)}٪ ≥ ۵۵٪"]
        else:
            parts = ["🔮 سایه‌ی کرونوس — هنوز حقِ رأی ندارد"]
        if today.get("ok") and int(today.get("n") or 0) > 0:
            parts.append(f"امروز {today['n']} جلسه")
            if int(today.get("sig") or 0) > 0:
                parts.append(f"هم‌جهتیِ {today['agree']}/{today['sig']}")
        if ev["verdict"] == "continue":
            parts.append(f"دروازه‌ی ارتقا: {n}/۲۰۰"
                         + (f" ({_pct(rate)}٪)" if rate is not None else ""))
            parts.append(f"آستانه: ≥{str(GATE_MIN_AGREE_PCT).rstrip('0').rstrip('.') or '0'}٪")
        return " · ".join(parts)
    except Exception:  # noqa: BLE001 — خطِ سایه هرگز گزارش را نمی‌شکند
        return None


def state(gate: Optional[dict] = None) -> dict:
    """وضعیتِ ارتقا — زنده از دروازه، بدونِ پرچمِ ذخیره‌شده.

    قرارداد = تنها حقیقت: وضعیت هر بار از خودِ دفترِ دروازه خوانده می‌شود تا
    هیچ فایلِ حکمی نتواند خلافِ قرارداد را نگه دارد. خطا یعنی سایه (پیش‌فرضِ امن).
    """
    try:
        if gate is None:
            from core import kronos_witness as KW
            gate = KW.gate_stats()
        ev = evaluate(gate)
        return {"promoted": ev["verdict"] == "promote",
                "retired": ev["verdict"] == "retire",
                "verdict": ev["verdict"],
                "verdict_fa": ev["verdict_fa"],
                "reasons_fa": ev["reasons_fa"]}
    except Exception as exc:  # noqa: BLE001 — وضعیت هرگز جلسه را نمی‌بَرد
        return {"promoted": False, "retired": False, "verdict": "continue",
                "verdict_fa": "⏳ ادامه‌ی جمع‌آوری — وضعیت در دسترس نیست",
                "reasons_fa": [f"{type(exc).__name__}: {exc}"]}


def is_promoted(gate: Optional[dict] = None) -> bool:
    """میان‌برِ امنِ «آیا عضوِ هفتم است؟» — خطا یعنی نه (سایه)."""
    return bool(state(gate).get("promoted"))


def archive_log(dest: Optional[str] = None, path: Optional[str] = None) -> dict:
    """آرشیوِ صادقانه‌ی دفتر در روزِ بازنشستگی — کپی، نه پاک‌کاری؛ idempotent."""
    from core import kronos_witness as KW

    p = path or KW.log_path()
    if dest is None:
        folder = p[: p.rfind("/")] if "/" in p else "."
        stamp = datetime.now(_TEHRAN).strftime("%Y%m%d")
        dest = f"{folder}/kronos_log_archive_{stamp}.jsonl"
    if not os.path.isfile(p):
        return {"ok": False, "archived": False, "dest": dest, "error": "دفتر وجود ندارد"}
    if os.path.isfile(dest):
        return {"ok": True, "archived": False, "dest": dest,
                "why_fa": "آرشیو از قبل هست — idempotent"}
    try:
        shutil.copy2(p, dest)
        with open(dest, encoding="utf-8") as f:
            n = sum(1 for _ in f)
        return {"ok": True, "archived": True, "dest": dest, "n_rows": n}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "archived": False, "dest": dest,
                "error": f"{type(exc).__name__}: {exc}"}


# ---- روزِ حکم: ثبتِ تاریخِ اجرای قرارداد (فازِ پنجِ کرونوس) ----------------
# «وضعیت» همچنان زنده از دفتر خوانده می‌شود؛ این فایل وضعیت نیست — تاریخِ
# «روزِ حکم» (اولین گذر از موعد) است؛ مثلِ آرشیو، سابقه است نه پرچم. هیچ
# فایلی نمی‌تواند خلافِ قرارداد را نگه دارد، چون حکم همیشه دوباره از دفترِ
# دروازه مشتق می‌شود و این سابقه فقط «کِی و با چه آماری اجرا شد» را نگه می‌دارد.

def record_path() -> str:
    """مسیرِ سابقه‌ی روزِ حکم — کنارِ دفترِ دروازه، در core/data/."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "core", "data", "kronos_verdict_record.json")


def verdict_record(path: Optional[str] = None) -> dict:
    """خواندنِ سابقه‌ی روزِ حکم — fail-soft؛ نبودش یعنی هنوز روزِ حکم نداشته‌ایم."""
    p = path or record_path()
    try:
        if not os.path.isfile(p):
            return {"ok": True, "exists": False, "path": p}
        with open(p, encoding="utf-8") as f:
            rec = json.load(f)
        return {"ok": True, "exists": True, "path": p, "record": rec}
    except Exception as exc:  # noqa: BLE001 — خواندنِ سابقه هرگز وضعیت را نمی‌بَرد
        return {"ok": False, "exists": False, "path": p,
                "error": f"{type(exc).__name__}: {exc}"}


def record_verdict(gate: Optional[dict] = None,
                   path: Optional[str] = None,
                   now: Optional[datetime] = None) -> dict:
    """ثبتِ «روزِ حکم» — فقط اولین گذر از موعد ثبت می‌شود؛ idempotent.

    ورودیِ gate خروجیِ kronos_witness.gate_stats() است (یا دیکته‌ی هم‌شکل
    برای آزمون). تا verdict == continue هیچ فایلی نوشته نمی‌شود.
    """
    try:
        if gate is None:
            from core import kronos_witness as KW
            gate = KW.gate_stats()
        st = state(gate)
        if st["verdict"] == "continue":
            return {"ok": True, "recorded": False,
                    "why_fa": "موعدِ حکم نرسیده — ثبتی ندارد"}
        p = path or record_path()
        if os.path.isfile(p):
            return {"ok": True, "recorded": False, "path": p,
                    "why_fa": "روزِ حکم از قبل ثبت است — idempotent"}
        real = (gate.get("real") or {}) if gate.get("ok") else {}
        now = now or datetime.now(_TEHRAN)
        if now.tzinfo is None:
            now = now.replace(tzinfo=_TEHRAN)
        rec = {
            "verdict": st["verdict"],
            "verdict_fa": st["verdict_fa"],
            "reasons_fa": st["reasons_fa"],
            "n": real.get("n"),
            "rate": real.get("rate"),
            "sessions_threshold": GATE_MIN_SESSIONS,
            "agree_threshold_pct": GATE_MIN_AGREE_PCT,
            "contract_locked_at": LOCKED_AT,
            "ts": now.astimezone(_TEHRAN).isoformat(timespec="seconds"),
        }
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        return {"ok": True, "recorded": True, "path": p, "record": rec}
    except Exception as exc:  # noqa: BLE001 — ثبتِ سابقه هرگز جلسه را نمی‌بُرد
        return {"ok": False, "recorded": False,
                "error": f"{type(exc).__name__}: {exc}"}
