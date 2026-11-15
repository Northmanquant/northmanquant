"""قاضیِ کرونوس ↔ نبیه — گزارشِ مقایسه‌ی دو موتورِ سایه — NorthmanQuant
================================================================
از سه دفترِ مخزن گزارشِ مقایسه می‌سازد و در core/data/kronos_nabigha_report.md
می‌نویسد؛ جابِ روزانه‌ی نبیه بعد از گرِیدر آن را اجرا می‌کند، پس فایل با هر
روزِ داده پخته‌تر می‌شود.

منابع:
- core/data/kronos_log.jsonl   ← جلساتِ paperِ کرونوس (مدلِ واقعیِ رسمی)
- core/data/nabigha_log.jsonl  ← جلساتِ paperِ نبیه (موتورِ بومی)
- core/data/paper_outcomes.jsonl ← نمره‌ی پیامدِ بازار برای هر دو (horizon 3)

دروازه‌ها (نقشه‌ی جدولِ ۴):
- کرونوس: هم‌جهتیِ چارت↔مدلِ >۵۵٪ روی ۲۰۰ جلسه‌ی سیگنال‌دارِ paper
- نبیه:   ۲۰۰ جلسه‌ی سیگنال‌دارِ paper برای موتورِ بومی

قاعده‌ی حکم: تا وقتی هر موتور کمتر از ۳۰ پیامدِ نمره‌شده دارد، حکمِ مقایسه‌ای
ممنوع است — فقط آمار و روند. با داده‌ی کم حکم‌دادن همان تقلب با خودمان است.

exit همیشه 0 — این گزارش اطلاعاتی است، نگهبانِ شکست نیست.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TEHRAN = timezone(timedelta(hours=3, minutes=30))
GATE_N = 200          # هر دو دروازه: ۲۰۰ جلسه‌ی سیگنال‌دار
GATE_AGREE_MIN = 55.0  # دروازه‌ی کرونوس: هم‌جهتیِ >۵۵٪
MATURE_N = 30          # حداقلِ پیامدِ نمره‌شده برای حقِ حکمِ مقایسه‌ای
SIDES = {1: "↑", -1: "↓", 0: "—"}

def _load(name: str) -> list[dict]:
    p = os.path.join(ROOT, "core", "data", name)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def _agree_pct(rows: list[dict], side_key: str) -> float | None:
    """هم‌جهتیِ چارت↔موتور — فقط جلساتِ سیگنال‌دار که هر دو طرفِ واقعی دارند."""
    pairs = [(r.get(side_key), r.get("team_side")) for r in rows
             if r.get("signal_active")
             and r.get(side_key) in (-1, 1) and r.get("team_side") in (-1, 1)]
    if not pairs:
        return None
    return round(100 * sum(1 for a, b in pairs if a == b) / len(pairs), 1)

def _engine_stats(rows: list[dict], side_key: str, conf_key: str | None) -> dict:
    sig = [r for r in rows if r.get("signal_active")]
    conf = [r.get(conf_key) for r in rows if conf_key and isinstance(r.get(conf_key), (int, float))]
    by_itv = Counter(r.get("interval", "?") for r in rows)
    dirs = Counter(SIDES.get(r.get(side_key), "?") for r in rows)
    return {
        "total": len(rows), "signal": len(sig), "gate": f"{len(sig)}/{GATE_N}",
        "agree": _agree_pct(rows, side_key),
        "conf_mean": round(sum(conf) / len(conf), 1) if conf else None,
        "dirs": dict(sorted(dirs.items())),
        "by_interval": dict(sorted(by_itv.items())),
    }

def _outcome_stats(outcomes: list[dict], engine: str) -> dict:
    o = [r for r in outcomes if r.get("engine") == engine]
    graded = [r for r in o if r.get("hit") in (True, False)]
    hits = sum(1 for r in graded if r["hit"])
    return {
        "graded": len(graded), "pending": len(o) - len(graded),
        "hit_rate": round(100 * hits / len(graded), 1) if graded else None,
        "hits": hits,
    }

def _fmt(x) -> str:
    return "—" if x is None else str(x)

def main() -> int:
    kronos = _load("kronos_log.jsonl")
    nabigha = _load("nabigha_log.jsonl")
    outcomes = _load("paper_outcomes.jsonl")

    ks = _engine_stats(kronos, "kronos_side", "kronos_agree_pct")
    ns = _engine_stats(nabigha, "nabigha_side", "confidence_pct")
    ko = _outcome_stats(outcomes, "kronos")
    no = _outcome_stats(outcomes, "nabigha")

    mature = ko["graded"] >= MATURE_N and no["graded"] >= MATURE_N
    if mature:
        delta = no["hit_rate"] - ko["hit_rate"]
        winner = ("نبیه" if delta > 0 else "کرونوس" if delta < 0 else "مساوی")
        verdict = (f"داده بالغ است ({MATURE_N}+ نمره‌شده در هر دو) — برتری فعلی: "
                   f"{winner} با اختلافِ {abs(round(delta,1))} واحدِ درصدی در hit-rate. "
                   "این حکمِ پایانه نیست؛ هر روز با داده‌ی تازه بازممیزی می‌شود.")
    else:
        verdict = (f"⏳ داده نابالغ — کرونوس {ko['graded']}/{MATURE_N} و نبیه {no['graded']}/{MATURE_N} "
                   f"پیامدِ نمره‌شده دارد؛ حکمِ مقایسه‌ای تا رسیدنِ هر دو به {MATURE_N} ممنوع. "
                   "دروازه‌ها در حالِ پر شدن‌اند و همین گزارش هر روز دقیق‌تر می‌شود.")

    gate_k = (f"✅ پر ({ks['agree']}٪ ≥ {GATE_AGREE_MIN}٪)" if ks["gate"] == f"{GATE_N}/{GATE_N}"
              and ks["agree"] is not None and ks["agree"] > GATE_AGREE_MIN else
              f"⏳ {ks['gate']} جلسه" + (f" · هم‌جهتیِ فعلی {_fmt(ks['agree'])}٪" if ks["agree"] is not None else ""))
    gate_n = f"⏳ {ns['gate']} جلسه" + (" · هنوز هیچ جلسه‌ی سیگنال‌دارِ نبیه ثبت نشده" if ns["signal"] == 0 else "")

    L = [
        "# قاضیِ کرونوس ↔ نبیه",
        f"_زبانِ گزارش: فارسی · تولید: {datetime.now(TEHRAN).isoformat(timespec='seconds')} تهران · "
        f"منابع: kronos_log / nabigha_log / paper_outcomes_",
        "",
        "## وضعیتِ دروازه‌ها",
        "",
        "| موتور | جلساتِ paper | سیگنال‌دار | پیشرفتِ دروازه | هم‌جهتیِ چارت↔موتور |",
        "|---|---|---|---|---|",
        f"| کرونوس (مدلِ رسمی) | {ks['total']} | {ks['signal']} | {gate_k} | {_fmt(ks['agree'])}٪ |",
        f"| نبیه (موتورِ بومی) | {ns['total']} | {ns['signal']} | {gate_n} | {_fmt(ns['agree'])}٪ |",
        "",
        "> دروازه‌ی کرونوس: هم‌جهتیِ >۵۵٪ روی ۲۰۰ جلسه · دروازه‌ی نبیه: ۲۰۰ جلسه‌ی سیگنال‌دار. "
        "جلسه‌ی سیگنال‌دار یعنی چارتِ حکم آن روز تایید/رد داده باشد؛ قیمتِ هر جلسه در دفتر ذخیره "
        "می‌شود تا گرِیدرِ پیامد بعداً نمره بدهد.",
        "",
        "## آمارِ موتورها",
        "",
        "| موتور | توزیعِ جهت | میانگینِ اطمینان | نمره‌شده | hit-rate | در انتظارِ نمره |",
        "|---|---|---|---|---|---|",
        f"| کرونوس | {ks['dirs']} | {_fmt(ks['conf_mean'])}٪ | {ko['graded']} | {_fmt(ko['hit_rate'])}٪ | {ko['pending']} |",
        f"| نبیه | {ns['dirs']} | {_fmt(ns['conf_mean'])}٪ | {no['graded']} | {_fmt(no['hit_rate'])}٪ | {no['pending']} |",
        "",
        "## تفکیکِ تایم‌فریم (جلسات)",
        "",
        f"- کرونوس: {ks['by_interval']}",
        f"- نبیه: {ns['by_interval']}",
        "",
        "## حکمِ فعلی",
        "",
        verdict,
    ]

    out = os.path.join(ROOT, "core", "data", "kronos_nabigha_report.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    print("== قاضیِ کرونوس ↔ نبیه ==")
    print(f"  کرونوس: {ks['total']} جلسه · سیگنال‌دار {ks['signal']} · هم‌جهتی {_fmt(ks['agree'])}٪ · hit-rate {_fmt(ko['hit_rate'])}٪ ({ko['graded']} نمره‌شده)")
    print(f"  نبیه:   {ns['total']} جلسه · سیگنال‌دار {ns['signal']} · hit-rate {_fmt(no['hit_rate'])}٪ ({no['graded']} نمره‌شده)")
    print(f"  حکم: {verdict}")
    print(f"  → {out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
