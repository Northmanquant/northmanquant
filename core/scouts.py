# -*- coding: utf-8 -*-
"""core/scouts.py — میدان کاوشگرها (Scout Arena) برای فرصت‌های فارم/ماینینگ/رایگان
====================================================================================
پرسش کاربر: «یک بخش ایجنت درست کن که برن تست کن یا انجامشون بدن — اونایی رو که
بهترین انجام بدن.»

مرزِ صادقانه (نوشته‌شده در صفحه هم هست): ایجنت‌ها **انجام نمی‌دهند** — کلیک،
لاگین، کیف پول و تراکنش فقط با انسان. چرا؟ سیستم‌های ضدسفل (Sybil) خودِ
پروژه‌ها بات‌ها را یکجا حذف می‌کنند و کلیدِ داخل اپ یعنی خطر. چیزی که ایجنت‌ها
«می‌کنند» این است:
  ۱) **تست** — هر فرصت را با داده‌ی واقعی می‌سنجند: استخر زنده است؟ TVL نمرده؟
     پیش‌بینی DefiLlama «Down» است؟ نوسان بالاست؟ در بودجه‌ی پول/زمانِ ایجنت
     جا می‌شود؟ (پاس‌نشدن‌ها حذف می‌شوند.)
  ۲) **انجامِ انتخاب** — از میان زنده‌ها، برنامه‌ی شخصیِ مرتب‌شده می‌سازند با
     دلیل، دقیقه/روز و نشان هزینه (🟢/🔴).
  ۳) **داوری** — داورِ قطعیِ همین ماژول برنامه‌ها را نمره می‌دهد: تخطی از
     بودجه‌ی صفر، سرریز زمان، تنوع، ناهماهنگی ریسک با شخصیت. بهترین برنامه
     برنده است و به چک‌لیستِ اجرای دستیِ کاربر تبدیل می‌شود.

۵ شخصیت با استراتژی متفاوت: 🆓 صفر-پول · 🛡 محتاط · ⚡ جاه‌طلب · ⏱ کم‌وقت ·
🧮 ریاضی‌دان (EV صریح). همه‌ی توابع قطعی و fail-soft هستند — داده‌ی خراب/خالی
کرش نمی‌سازد؛ بدون اینترنت هم با تست‌نت‌های محلی مسابقه کامل برگزار می‌شود.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from core.opportunities import COST_FREE, COST_PAID, honest_pools

# نشانِ هزینه برای هر نوع گام — «mining» یعنی رایگان اما ارزشش لاتاری است.
COST_FOR: Dict[str, Tuple[str, str]] = {
    "free": (COST_FREE, "🟢 Free"),
    "paid": (COST_PAID, "🔴 Paid"),
    "mining": ("🟢 رایگان — لاتاری", "🟢 Free — lottery"),
}


def cost_for(kind: str) -> Tuple[str, str]:
    """(نشان فارسی، نشان انگلیسی) برای هر نوع گام — نوع ناشناخته → «؟»."""
    return COST_FOR.get(str(kind or ""), ("؟", "?"))


# --------------------------------------------------------------------------- #
# شخصیت‌ها — پنج ایجنت، پنج استراتژی                                          #
# --------------------------------------------------------------------------- #
# فیلدهای _min_tvl/_max_apy/_stable_only/_top = پارامترهای فیلتر صداقتِ خودش؛
# budget: free (هیچ پولی نه) / paid (سرمایه دارد ولی این ایجنت‌ها تست‌نت را هم
# دوست دارند) / any. risk: ۰ (محتاط) تا ۱ (جاه‌طلب). time_budget: دقیقه/روز.
SCOUT_AGENTS: List[Dict[str, Any]] = [
    {
        "key": "zero", "icon": "🆓",
        "name": "صفر-پول", "name_en": "Zero-Budget",
        "style": "حتی یک دلار هم خرج نمی‌کند — فقط زمان؛ هر فرصتِ پولی را رد می‌کند.",
        "style_en": "Never spends a dollar — time only; rejects anything that costs money.",
        "budget": "free", "risk": 0.2, "time_budget": 30,
        "_min_tvl": 1e7, "_max_apy": 40.0, "_stable_only": True, "_top": 5,
    },
    {
        "key": "cautious", "icon": "🛡",
        "name": "محتاط", "name_en": "Cautious",
        "style": "فقط استیبلِ بلوچیپ با نوسان کم و TVL سنگین؛ بازده پایین ولی بی‌دردسر.",
        "style_en": "Only blue-chip stables, low volatility, heavy TVL; modest but calm yield.",
        "budget": "any", "risk": 0.1, "time_budget": 20,
        "_min_tvl": 5e7, "_max_apy": 30.0, "_stable_only": True, "_top": 8,
    },
    {
        "key": "aggressive", "icon": "⚡",
        "name": "جاه‌طلب", "name_en": "Aggressive",
        "style": "بالاترین بازده ممکن از دلِ فیلترِ صداقت — حتی غیراستیبل با زیان ناپایدار.",
        "style_en": "Highest yield that still passes the honesty filter — even non-stables with IL.",
        "budget": "any", "risk": 0.7, "time_budget": 60,
        "_min_tvl": 3e7, "_max_apy": 80.0, "_stable_only": False, "_top": 12,
    },
    {
        "key": "busy", "icon": "⏱",
        "name": "کم‌وقت", "name_en": "Time-Poor",
        "style": "بیشترین ارزش در کمترین دقیقه — بودجه‌ی ۱۵ دقیقه در روز، نه یک ثانیه بیشتر.",
        "style_en": "Most value per minute — a hard 15-minute daily budget, not a second more.",
        "budget": "any", "risk": 0.4, "time_budget": 15,
        "_min_tvl": 1e7, "_max_apy": 50.0, "_stable_only": True, "_top": 10,
    },
    {
        "key": "quant", "icon": "🧮",
        "name": "ریاضی‌دان", "name_en": "Quant",
        "style": "EV صریح: بازده کارمزدی × (۱ − نوسان) × اعتبار TVL — عدد بی‌احساس، بی‌های‌وهو.",
        "style_en": "Explicit EV: fee APY × (1 − sigma) × TVL credibility — cold, honest math.",
        "budget": "any", "risk": 0.5, "time_budget": 40,
        "_min_tvl": 2e7, "_max_apy": 60.0, "_stable_only": True, "_top": 12,
    },
]


# --------------------------------------------------------------------------- #
# تستِ هر فرصت با داده‌ی واقعی                                                #
# --------------------------------------------------------------------------- #
def _persona_pools(agent: dict, pools: Optional[List[dict]]) -> List[dict]:
    """فیلتر صداقت با پارامترهای شخصیت + تستِ زنده — fail-soft روی داده‌ی خراب.

    «تست» ایجنت: APY صفر/بیش‌حد → حذف؛ پیش‌بینی Down → حذف (استخر در حال
    ریختن بازده برای همه‌ی شخصیت‌ها جذاب نیست)؛ نوسانِ بالا برای شخصیتِ
    محتاط → حذف؛ TVL زیر کفِ شخصیت → حذف.
    """
    if not isinstance(pools, list) or not pools:
        return []
    try:
        cands = honest_pools(
            pools, min_tvl=float(agent.get("_min_tvl", 1e7)),
            stable_only=bool(agent.get("_stable_only", True)),
            max_apy=float(agent.get("_max_apy", 60.0)),
            top=int(agent.get("_top", 10)))
    except Exception:  # noqa: BLE001 — داده‌ی ناقص هرگز صفحه را نمی‌شکند
        return []
    out: List[dict] = []
    cautious = float(agent.get("risk", 0.5)) <= 0.2
    for p in cands:
        if not isinstance(p, dict):
            continue
        if str(p.get("predicted") or "") == "Down":
            continue                          # تست: پیش‌بینی افت → رد
        if cautious and float(p.get("sigma") or 0.0) > 0.08:
            continue                          # تست: شخصیت محتاط نوسانِ بالا نمی‌پذیرد
        out.append(p)
    return out


def _pool_step(p: dict) -> dict:
    """یک استخرِ نرمال‌شده → گامِ برنامه با دلیل و نشان هزینه."""
    il = " ⚠️ استیبل نیست (زیان ناپایدار ممکن است)" if not p.get("stablecoin") else ""
    il_en = " ⚠️ not a stable (impermanent loss possible)" if not p.get("stablecoin") else ""
    return {
        "kind": "paid",
        "title": f"{p.get('project', '?')} · {p.get('chain', '?')} ({p.get('symbol', '?')})",
        "title_en": f"{p.get('project', '?')} · {p.get('chain', '?')} ({p.get('symbol', '?')})",
        "time_min": 10,
        "why": (f"APY کارمزدی {float(p.get('apy_base') or 0.0):.1f}٪ · "
                f"TVL {float(p.get('tvl_usd') or 0.0) / 1e6:.0f}M$ · "
                f"امتیاز صداقت {p.get('score', 0)} · نوسان {float(p.get('sigma') or 0.0):.2f}{il}"),
        "why_en": (f"Fee APY {float(p.get('apy_base') or 0.0):.1f}% · "
                   f"TVL ${float(p.get('tvl_usd') or 0.0) / 1e6:.0f}M · "
                   f"honesty {p.get('score', 0)} · sigma {float(p.get('sigma') or 0.0):.2f}{il_en}"),
        "flags": ["high_sigma"] if float(p.get("sigma") or 0.0) > 0.1 else [],
    }


def _testnet_step(h: dict) -> dict:
    """یک تست‌نتِ دست‌چین → گامِ رایگان (فقط زمان)."""
    return {
        "kind": "free",
        "title": str(h.get("name") or "?"),
        "title_en": str(h.get("name") or "?"),
        "time_min": int(h.get("minutes") or 15),
        "why": str(h.get("note") or "تست‌نت فعال — بلیت لاتاریِ رایگان."),
        "why_en": str(h.get("note_en") or "Active testnet — a free lottery ticket."),
        "flags": [],
    }


_MINING_STEP: dict = {
    "kind": "mining",
    "title": "ماینینگ موبایلی — یک اپ از تب ماینینگ",
    "title_en": "Mobile mining — one app from the Mining tab",
    "time_min": 5,
    "why": "رایگان اما بلیت لاتاری — تا وقتی توکن در صرافی معتبر فهرست نشده ارزشش صفر است؛ اگر پول خواست ببند و برو.",
    "why_en": "Free but a lottery ticket — value is zero until the token lists; the moment it asks money, quit.",
    "flags": [],
}


# --------------------------------------------------------------------------- #
# ساختِ برنامه — استراتژیِ هر شخصیت                                           #
# --------------------------------------------------------------------------- #
def build_plan(agent: dict, pools: Optional[List[dict]],
               testnets: Optional[List[dict]]) -> dict:
    """برنامه‌ی شخصیِ ایجنت از میان فرصت‌های تست‌شده — قطعی و بدون شبکه.

    خروجی: {"agent_key", "steps", "total_time", "has_paid", "notes", "notes_en"}
    """
    key = str(agent.get("key") or "?")
    tb = int(agent.get("time_budget") or 30)
    tn = [h for h in (testnets or []) if isinstance(h, dict)]
    tn.sort(key=lambda h: int(h.get("minutes") or 15))
    steps: List[dict] = []
    notes: List[str] = []
    notes_en: List[str] = []

    if key == "zero":
        # فقط فرصت‌های بی‌هزینه تا سقفِ بودجه‌ی زمانی + یک گام ماینینگ موبایلی
        acc = 0
        for h in tn:
            m = int(h.get("minutes") or 15)
            if acc + m <= tb - 5:
                steps.append(_testnet_step(h))
                acc += m
        if acc + 5 <= tb:
            steps.append(dict(_MINING_STEP))
            acc += 5
        notes.append("استخرهای بازده به سرمایه نیاز دارند — این ایجنت فقط زمان خرج می‌کند.")
        notes_en.append("Yield pools need capital — this agent spends only time.")

    elif key == "cautious":
        live = _persona_pools(agent, pools)
        acc = 0
        for p in live[:2]:                      # دو استخرِ سنگین و آرام
            steps.append(_pool_step(p))
            acc += 10
        for h in tn[:2]:                        # دو لاتاریِ کوتاه (بی‌ریسک)
            m = int(h.get("minutes") or 15)
            if acc + m <= tb:
                steps.append(_testnet_step(h))
                acc += m
        if not live:
            notes.append("استخری با سقفِ محافظه‌کارانه زنده نماند — فقط تست‌نت‌ها.")
            notes_en.append("No pool survived the conservative filter — testnets only.")

    elif key == "aggressive":
        live = sorted(_persona_pools(agent, pools),
                      key=lambda p: -float(p.get("apy_base") or 0.0))[:3]
        acc = 0
        for p in live:
            steps.append(_pool_step(p))
            acc += 10
        if tn:
            steps.append(_testnet_step(tn[0]))
            acc += int(tn[0].get("minutes") or 15)
        if len(live) < 3:
            notes.append("کمتر از ۳ استخرِ پر بازده از فیلتر گذشت — بقیه زنده نماندند.")
            notes_en.append("Fewer than 3 high-yield pools passed the live tests.")

    elif key == "busy":
        acc = 0
        if tn:
            m = int(tn[0].get("minutes") or 15)
            if m <= tb:                         # تنها یک لاتاریِ کوتاه
                steps.append(_testnet_step(tn[0]))
                acc += m
        live = sorted(_persona_pools(agent, pools), key=lambda p: -int(p.get("score") or 0))
        if live and acc + 10 <= tb:             # یک استخر اگر بودجه‌ی دقیقه بماند
            steps.append(_pool_step(live[0]))
            acc += 10
        notes.append("قانونِ این ایجنت: ۱۵ دقیقه در روز — نه یک ثانیه بیشتر.")
        notes_en.append("This agent's law: 15 minutes a day — not a second more.")

    elif key == "quant":
        # EV صریح: بازده کارمزدی × (۱ − نوسان نرمال‌شده) × اعتبار TVL (لگاریتمی)
        live = _persona_pools(agent, pools)
        evd: List[Tuple[float, dict]] = []
        for p in live:
            apy = max(float(p.get("apy_base") or 0.0), 0.0)
            sig = min(max(float(p.get("sigma") or 0.0), 0.0), 0.5)
            cred = min(math.log10(max(float(p.get("tvl_usd") or 0.0), 1.0) / 1e6 + 1.0) / 2.0, 1.0)
            evd.append((apy * (1.0 - sig) * cred, p))
        evd.sort(key=lambda x: -x[0])
        acc = 0
        for ev, p in evd[:3]:
            st = _pool_step(p)
            st["ev"] = round(ev, 2)
            st["why"] += f" · EV {st['ev']:.2f}"
            st["why_en"] += f" · EV {st['ev']:.2f}"
            steps.append(st)
            acc += 10
        if tn and acc + int(tn[0].get("minutes") or 15) <= tb:
            steps.append(_testnet_step(tn[0]))   # یک لاتاری: EV نامعین، هزینه صفر
            acc += int(tn[0].get("minutes") or 15)
        if not evd:
            notes.append("داده‌ی زنده نرسید — EV فقط روی تست‌نت‌ها قابل محاسبه نیست؛ برنامه‌ی حداقلی.")
            notes_en.append("No live data — EV is not computable for testnets; minimal plan.")
    else:
        # شخصیت ناشناخته → برنامه‌ی حداقلیِ امن (فقط یک تست‌نت کوتاه)
        if tn:
            steps.append(_testnet_step(tn[0]))

    total = sum(int(s.get("time_min") or 0) for s in steps)
    return {
        "agent_key": key,
        "steps": steps,
        "total_time": total,
        "has_paid": any(s.get("kind") == "paid" for s in steps),
        "notes": notes,
        "notes_en": notes_en,
    }


# --------------------------------------------------------------------------- #
# داوری — نمره‌ی قطعی ۰-۱۰۰ برای هر برنامه                                    #
# --------------------------------------------------------------------------- #
def judge_plan(agent: dict, plan: dict) -> Tuple[int, List[str]]:
    """(نمره، فلگ‌ها) — قواعد قطعی؛ بدون شبکه، بدون شانس.

    تخطی از بودجه‌ی صفر = سنگین‌ترین جریمه؛ سرریزِ زمان جریمه‌ی متناسب؛
    تنوع نوع گام پاداش؛ ناهماهنگی ریسک با شخصیتِ محتاط جریمه؛ گامِ EV صریح
    پاداش؛ لاتاریِ رایگان برای ایجنت‌های سرمایه‌دار پاداشِ گزینه‌ای.
    """
    steps = [s for s in (plan.get("steps") or []) if isinstance(s, dict)]
    score = 55.0 if steps else 5.0
    flags: List[str] = []
    budget = str(agent.get("budget") or "any")
    tb = max(int(agent.get("time_budget") or 30), 1)

    if budget == "free" and plan.get("has_paid"):
        score -= 45.0
        flags.append("budget_violation")
    excess = int(plan.get("total_time") or 0) - tb
    if excess > 0:
        score -= min(30.0, excess / tb * 30.0)
        flags.append("time_over")
    if len({s.get("kind") for s in steps}) >= 2:
        score += 8.0
    if float(agent.get("risk", 0.5)) <= 0.2 and any(
            "high_sigma" in (s.get("flags") or []) or "predicted_down" in (s.get("flags") or [])
            for s in steps):
        score -= 15.0
        flags.append("risk_mismatch")
    if float(agent.get("risk", 0.5)) >= 0.6 and steps and all(s.get("kind") != "paid" for s in steps):
        score -= 8.0
        flags.append("too_timid")
    if budget != "free" and any(s.get("kind") in ("free", "mining") for s in steps):
        score += 5.0
    if any("ev" in s for s in steps):
        score += 5.0
    return int(round(max(0.0, min(100.0, score)))), flags


def _verdict(score: int) -> Tuple[str, str]:
    if score >= 70:
        return ("برنامه‌ی برنده: واقع‌بینانه، در بودجه، بدون خودفریبی",
                "Winning plan: realistic, within budget, no self-deception")
    if score >= 55:
        return ("قوی — چند اصلاحِ جزئی دارد", "Strong — a few minor tweaks")
    if score >= 35:
        return ("متوسط — سود و ریسک نامتوازن", "Average — yield/risk not balanced")
    return ("ضعیف — نگاهی به برنامه‌ی رقیب بینداز", "Weak — check a rival's plan")


def run_arena(pools: Optional[List[dict]],
              testnets: Optional[List[dict]]) -> List[dict]:
    """مسابقه‌ی کامل: همه‌ی ایجنت‌ها برنامه می‌سازند، داور نمره می‌دهد، مرتب می‌شود.

    خروجی: لیست مرتب‌شده (برنده اول) از {"agent", "plan", "score", "verdict",
    "verdict_en", "flags"} — قطعی؛ دو اجرا با یک ورودی، یک خروجی.
    """
    out: List[dict] = []
    for agent in SCOUT_AGENTS:
        try:
            plan = build_plan(agent, pools, testnets)
            score, flags = judge_plan(agent, plan)
        except Exception:  # noqa: BLE001 — یک ایجنتِ خراب بقیه را نمی‌سوزاند
            plan = {"agent_key": str(agent.get("key") or "?"), "steps": [],
                    "total_time": 0, "has_paid": False, "notes": [], "notes_en": []}
            score, flags = 0, ["engine_error"]
        v_fa, v_en = _verdict(score)
        out.append({"agent": agent, "plan": plan, "score": score,
                    "verdict": v_fa, "verdict_en": v_en, "flags": flags})
    out.sort(key=lambda r: (-int(r["score"]), int(r["plan"].get("total_time") or 0),
                            str(r["agent"].get("key") or "")))
    return out
