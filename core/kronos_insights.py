# -*- coding: utf-8 -*-
"""برداشتِ حداکثری از دفترِ کرونوس — ریزآمارِ صادقانه، بدونِ شبکه و بدونِ مدل
==============================================================================
درخواستِ کاربر: «کرونوس آن‌قدر مهم نیست... بیشتر ازش داده بگیر». دروازه فقط
یک عددِ کلان می‌دهد (n/۲۰۰ · rate)؛ این ماژول همان دفتر را ریز می‌کند:

  • به تفکیکِ تایم‌فریم و نماد و روز — کجا قوی است، کجا ضعیف
  • باندِ اطمینانِ داخلی (kronos_agree_pct) در برابرِ هم‌جهتیِ واقعی —
    آیا «وقتی مطمئن است درست می‌گوید»؟ مبنایی برای وزن‌دهیِ آینده
  • streak — چند ادعای آخرِ پشت‌سرهم هم‌جهت بوده‌اند

قاعده‌ی صداقتِ دفتر حفظ می‌شود: نرخ‌ها فقط روی جلساتِ سیگنال‌دارِ دوطرفه‌اند
(بی‌ادعا ≠ مخالفت)؛ شمارش‌های حجمی جداگانه گزارش می‌شوند.
"""
from __future__ import annotations

import json
from collections import defaultdict


def _load(path: str | None) -> list[dict]:
    import os
    p = path or _default_log()
    entries: list[dict] = []
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if isinstance(e, dict):  # null/[1,2] و هر غیرِ dict = خطِ خراب
                    entries.append(e)
    except Exception:  # noqa: BLE001 — دفترِ نبود = آمارِ خالی، نه خطا
        return []
    return entries


def _default_log() -> str:
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return f"{root}/core/data/kronos_log.jsonl"


def _is_signal(e: dict) -> bool:
    """قاعده‌ی دروازه: سیگنالِ فعالِ چارت + ادعای جهت‌دارِ هر دو طرف."""
    return bool(e.get("backend") == "kronos" and e.get("signal_active")
                and e.get("kronos_side") in (1, -1) and e.get("team_side") in (1, -1))


def _rate(rows: list[dict]) -> dict:
    sig = [e for e in rows if _is_signal(e)]
    agree = sum(1 for e in sig if int(e["kronos_side"]) == int(e["team_side"]))
    return {"n": len(sig), "agree": agree,
            "rate": round(agree / len(sig) * 100.0, 1) if sig else None}


def insights(path: str | None = None) -> dict:
    """ریزآمارِ کاملِ دفترِ کرونوس — خالص و بدونِ I/O به‌جز خواندنِ دفتر."""
    rows = [e for e in _load(path) if e.get("backend") == "kronos"]
    directed = [e for e in rows if e.get("kronos_side") in (1, -1)
                and e.get("team_side") in (1, -1)]
    overall = _rate(rows)

    by_interval: dict[str, dict] = {}
    for e in rows:
        key = str(e.get("interval") or "?")
        by_interval.setdefault(key, [])
        by_interval[key].append(e)
    by_interval = {k: _rate(v) for k, v in sorted(by_interval.items())}

    by_symbol: dict[str, dict] = {}
    for e in rows:
        key = str(e.get("symbol") or "?")
        by_symbol.setdefault(key, [])
        by_symbol[key].append(e)
    sym_rates = {k: _rate(v) for k, v in by_symbol.items()}
    ranked = sorted(((k, v) for k, v in sym_rates.items()
                     if v["n"] >= 2 and v["rate"] is not None),
                    key=lambda kv: (-kv[1]["rate"], -kv[1]["n"]))
    top = [{"symbol": k, **v} for k, v in ranked[:5]]
    bottom = [{"symbol": k, **v} for k, v in reversed(ranked[-5:])]

    by_day: dict[str, dict] = {}
    for e in rows:
        key = str(e.get("ts") or "")[:10]
        if not key:
            continue
        by_day.setdefault(key, [])
        by_day[key].append(e)
    by_day = {k: _rate(v) for k, v in sorted(by_day.items())[-7:]}

    # باندِ اطمینانِ داخلی در برابرِ هم‌جهتیِ واقعی
    buckets = {"<60": [], "60-70": [], "70-80": [], ">=80": []}
    for e in directed:
        a = e.get("kronos_agree_pct")
        if not isinstance(a, (int, float)):
            continue
        a = float(a)
        b = "<60" if a < 60 else ("60-70" if a < 70 else ("70-80" if a < 80 else ">=80"))
        buckets[b].append(e)
    conf_buckets = {k: _rate(v) for k, v in buckets.items()}

    streak = 0
    for e in reversed(directed):
        if int(e["kronos_side"]) == int(e["team_side"]):
            streak += 1
        else:
            break

    return {"ok": True, "n_total": len(rows), "n_directed": len(directed),
            "n_signal": overall["n"], "agree": overall["agree"],
            "rate": overall["rate"],
            "by_interval": by_interval, "by_symbol": sym_rates,
            "top_symbols": top, "bottom_symbols": bottom,
            "by_day": by_day, "conf_buckets": conf_buckets, "streak": streak}


def _fmt_rate(r) -> str:
    return f"{r}٪" if r is not None else "—"


def report_fa(path: str | None = None) -> str:
    """گزارشِ متنیِ فارسی برای چاپ/گزارش — هرگز exception نمی‌دهد."""
    try:
        ins = insights(path)
        if not ins.get("ok"):
            return "⚠️ دفترِ کرونوس خوانده نشد"
        if ins["n_total"] == 0:
            return "دفترِ کرونوس خالی است — هنوز جلسه‌ای ثبت نشده"
        lines = [
            f"== برداشت از دفترِ کرونوس — {ins['n_total']} جلسه · "
            f"{ins['n_signal']} سیگنال‌دار · هم‌جهتیِ {_fmt_rate(ins['rate'])} · "
            f"streak: {ins['streak']} ==",
            "تایم‌فریم‌ها: " + " · ".join(
                f"{k}: {v['n']} ({_fmt_rate(v['rate'])})"
                for k, v in ins["by_interval"].items()),
            "روزهای اخیر: " + " · ".join(
                f"{k}: {v['n']} ({_fmt_rate(v['rate'])})"
                for k, v in ins["by_day"].items()),
        ]
        if ins["top_symbols"]:
            lines.append("قوی‌ترین نمادها: " + " · ".join(
                f"{s['symbol']} {_fmt_rate(s['rate'])} ({s['n']})"
                for s in ins["top_symbols"][:3]))
        if ins["bottom_symbols"]:
            lines.append("ضعیف‌ترین نمادها: " + " · ".join(
                f"{s['symbol']} {_fmt_rate(s['rate'])} ({s['n']})"
                for s in ins["bottom_symbols"][:3]))
        lines.append("اطمینانِ داخلی ↔ هم‌جهتی: " + " · ".join(
            f"{k}: {v['n']} ({_fmt_rate(v['rate'])})"
            for k, v in ins["conf_buckets"].items()))
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"⚠️ گزارشِ کرونوس نشد: {type(exc).__name__}: {exc}"
