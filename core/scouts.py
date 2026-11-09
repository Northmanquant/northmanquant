# -*- coding: utf-8 -*-
"""core/scouts.py — میدان کاوشگرها (Scout Arena) برای فرصت‌های فارم/ماینینگ/رایگان
====================================================================================
پرسش کاربر: «یک بخش ایجنت درست کن که برن تست کن یا انجامشون بدن — اونایی رو که
بهترین انجام بدن.» و سپس: «میخوام بیشترش روی پروژه‌های رایگان باشن ایجنت‌ها نه
پولی — هرکدومشون چه فارمینگ چه ماینینگ.»

**قانون میدان (درخواست صریح کاربر): بودجه‌ی صفر برای همه‌ی ایجنت‌ها.**
ایجنت‌ها فقط سراغ پروژه‌های 🟢 رایگان می‌روند — از هر دو دنیا:
  • سمت فارمینگ: تست‌نت‌ها (kind=free) و فارمِ نقاط بدون سرمایه (kind=points)
  • سمت ماینینگ: ماینینگ موبایلیِ رایگان (kind=mining — رایگان اما لاتاری)
فارمینگِ پولی (واریز سرمایه) و ماینینگ سخت‌افزاری/ابری هرگز وارد برنامه
نمی‌شوند. استخرهای بازدهِ DefiLlama فقط **تست** می‌شوند (زنده است؟ پیش‌بینی
Down؟ نوسان؟) و اگر پولی باشند، در یادداشتِ برنامه شمرده و رد می‌شوند — داور
هم برای هر گامِ پولی، برای هر ایجنتی، جریمه‌ی سنگین می‌گذارد.

مرزِ صادقانه (نوشته‌شده در صفحه هم هست): ایجنت‌ها **انجام نمی‌دهند** — کلیک،
لاگین، کیف پول و تراکنش فقط با انسان. چرا؟ سیستم‌های ضدسفل (Sybil) خودِ
پروژه‌ها بات‌ها را یکجا حذف می‌کنند و کلیدِ داخل اپ یعنی خطر. چیزی که ایجنت‌ها
«می‌کنند» این است:
  ۱) **تست** — هر فرصت را با داده‌ی واقعی می‌سنجند؛ پولی‌ها را رد می‌کنند.
  ۲) **انجامِ انتخاب** — از میان رایگان‌های تست‌شده، برنامه‌ی شخصیِ مرتب‌شده
     می‌سازند با دلیل، دقیقه/روز و نشان هزینه (🟢).
  ۳) **داوری** — داورِ قطعیِ همین ماژول برنامه‌ها را نمره می‌دهد: تخطی از
     بودجه‌ی صفر (برای همه)، سرریز زمان، تنوع، پوششِ دو دنیا (فارم+ماین).
     بهترین برنامه برنده است و به چک‌لیستِ اجرای دستیِ کاربر تبدیل می‌شود.

۵ شخصیت با استراتژی متفاوت روی همان میدانِ رایگان: 🆓 صفر-پول (ارزان‌ترین‌ها
اول) · 🛡 محتاط (جاافتاده‌ترین‌ها، بدون لاتاری) · ⚡ جاه‌طلب (بیشترین پوشش) ·
⏱ کم‌وقت (۱۵ دقیقه سفت‌وسخت) · 🧮 ریاضی‌دان (کمینه‌سازی قیمتِ زمانی؛ EV پولی
لاتاری‌ها نامعین است و صادقانه «نامعین» نوشته می‌شود). همه‌ی توابع قطعی و
fail-soft هستند — داده‌ی خراب/خالی کرش نمی‌سازد؛ بدون اینترنت هم با
تست‌نت‌های محلی مسابقه کامل برگزار می‌شود.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.opportunities import COST_FREE, COST_PAID, honest_pools

# نشانِ هزینه برای هر نوع گام — «mining» یعنی رایگان اما ارزشش لاتاری است.
COST_FOR: Dict[str, Tuple[str, str]] = {
    "free": (COST_FREE, "🟢 Free"),
    "paid": (COST_PAID, "🔴 Paid"),
    "points": ("🟢 رایگان — نقاط", "🟢 Free — points"),
    "mining": ("🟢 رایگان — لاتاری", "🟢 Free — lottery"),
}


def cost_for(kind: str) -> Tuple[str, str]:
    """(نشان فارسی، نشان انگلیسی) برای هر نوع گام — نوع ناشناخته → «؟»."""
    return COST_FOR.get(str(kind or ""), ("؟", "?"))


# --------------------------------------------------------------------------- #
# شخصیت‌ها — پنج ایجنت، پنج استراتژی، یک میدانِ مشترکِ رایگان                  #
# --------------------------------------------------------------------------- #
# قانون مشترک (به درخواست کاربر): هیچ ایجنتی گامِ پولی نمی‌گذارد — تفاوت
# استراتژی‌ها فقط در «کدام رایگان‌ها را و به چه ترتیبی» برمی‌دارند.
# budget: free (هیچ پولی نه) / paid / any — همه در میدانِ فقط-رایگان مسابقه
# می‌دهند؛ فیلد بودجه فقط برای جریمه‌ی ایمنیِ داور می‌ماند.
# risk: ۰ (محتاط) تا ۱ (جاه‌طلب). time_budget: دقیقه/روز.
SCOUT_AGENTS: List[Dict[str, Any]] = [
    {
        "key": "zero", "icon": "🆓",
        "name": "صفر-پول", "name_en": "Zero-Budget",
        "style": "حتی یک دلار هم خرج نمی‌کند — ارزان‌ترین‌ها بر حسب دقیقه: ماینینگ، نقاط، کوتاه‌ترین تست‌نت‌ها.",
        "style_en": "Never spends a dollar — picks by minutes: mining, points, then shortest testnets.",
        "budget": "free", "risk": 0.2, "time_budget": 30,
    },
    {
        "key": "cautious", "icon": "🛡",
        "name": "محتاط", "name_en": "Cautious",
        "style": "جاافتاده‌ترین تست‌نت (قدیمی‌ترین) + فارمِ نقاط؛ لاتاریِ ماینینگ را نه چون گران است، چون نامعین است نمی‌پسندد.",
        "style_en": "Longest-running testnet + points farming; skips the mining lottery — not because it costs, but because it's uncertain.",
        "budget": "free", "risk": 0.1, "time_budget": 20,
    },
    {
        "key": "aggressive", "icon": "⚡",
        "name": "جاه‌طلب", "name_en": "Aggressive",
        "style": "بیشترین پوششِ رایگان ممکن: ماینینگ + نقاط + همه‌ی تست‌نت‌ها تا سقف ۶۰ دقیقه — بلیت‌های لاتاری بیشتر.",
        "style_en": "Maximum free coverage: mining + points + every testnet up to 60 minutes — more lottery tickets.",
        "budget": "free", "risk": 0.7, "time_budget": 60,
    },
    {
        "key": "busy", "icon": "⏱",
        "name": "کم‌وقت", "name_en": "Time-Poor",
        "style": "۱۵ دقیقه در روز، نه یک ثانیه بیشتر — دو دنیا در یک ربع: ماینینگ موبایلی + فارمِ نقاط.",
        "style_en": "15 minutes a day, not a second more — both worlds in a quarter: mobile mining + points farming.",
        "budget": "free", "risk": 0.4, "time_budget": 15,
    },
    {
        "key": "quant", "icon": "🧮",
        "name": "ریاضی‌دان", "name_en": "Quant",
        "style": "EV پولی لاتاری‌ها نامعین است؛ تنها کمیتِ قطعی قیمتِ زمانی است — کمینه‌سازی دقیقه با پوششِ هر دو دنیا.",
        "style_en": "The money-EV of lotteries is unknowable; the only hard quantity is the time price — minimize minutes, cover both worlds.",
        "budget": "free", "risk": 0.5, "time_budget": 40,
    },
]


# --------------------------------------------------------------------------- #
# تستِ فرصت‌ها با داده‌ی واقعی                                                #
# --------------------------------------------------------------------------- #
def _persona_pools(agent: dict, pools: Optional[List[dict]]) -> List[dict]:
    """تستِ زنده‌ی استخرها با فیلتر صداقتِ شخصیت — fail-soft روی داده‌ی خراب.

    «تست» ایجنت روی استخرها: APY صفر/بیش‌حد → حذف؛ پیش‌بینی Down → حذف؛
    نوسانِ بالا برای شخصیتِ محتاط → حذف؛ TVL زیر کفِ شخصیت → حذف.
    خروجی فقط برای «شمارشِ ردشده‌ها» است — طبق قانون میدان، هیچ استخرِ پولی
    وارد برنامه نمی‌شود.
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


_EN2FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _pool_reject_note(live: List[dict], pools: Optional[List[dict]]) -> Tuple[str, str]:
    """یادداشتِ «تست شد، رد شد» برای استخرهای پولی — بسته به وضعیت داده."""
    if not isinstance(pools, list) or not pools:
        return ("داده‌ی استخرها نرسید — مسابقه روی رایگان‌های محلی برگزار شد؛ رفرش بعدی استخرها هم تست می‌شوند.",
                "Pool data did not arrive — the race ran on local free items; next refresh will test pools too.")
    if not live:
        return ("هیچ استخری از فیلتر صداقت نگذشت — برنامه‌ی فقط-رایگان بدون ردشده‌ی زنده.",
                "No pool passed the honesty filter — the free-only plan has nothing to reject.")
    n = str(len(live)).translate(_EN2FA_DIGITS)
    return (f"تست زنده: {n} استخر از فیلتر صداقت گذشت اما پولی است (واریز لازم دارد) — "
            "طبق قانون میدانِ فقط-رایگان از برنامه حذف شد؛ جزئیاتش در تب «فارمینگ».",
            f"Live test: {len(live)} pools passed the honesty filter but are paid (deposit required) — "
            "dropped per the free-only arena law; see the Farming tab.")


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


_POINTS_STEP: dict = {
    "kind": "points",
    "title": "فارمِ نقاط — کمپین نقاطِ پروژه‌ای تازه از منبع ایردراپ",
    "title_en": "Points farming — a fresh project's points campaign from the airdrop source",
    "time_min": 10,
    "why": "فارمینگ بدون سرمایه: فقط تعامل با محصول و ثبت نقاط برای ایردراپِ احتمالی — پولی واریز نمی‌شود، فقط وقت.",
    "why_en": "Farming without capital: just use the product and log points for a possible airdrop — no deposit, only time.",
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

_FREE_FARM_SIDE = {"free", "points"}      # سمت فارمینگِ رایگان
_FREE_MINE_SIDE = {"mining"}              # سمت ماینینگِ رایگان


# --------------------------------------------------------------------------- #
# ساختِ برنامه — استراتژیِ هر شخصیت روی میدانِ فقط-رایگان                      #
# --------------------------------------------------------------------------- #
def build_plan(agent: dict, pools: Optional[List[dict]],
               testnets: Optional[List[dict]]) -> dict:
    """برنامه‌ی شخصیِ ایجنت از میان رایگان‌های تست‌شده — قطعی و بدون شبکه.

    قانون مشترک: استخرها زنده تست می‌شوند اما هیچ‌وقت وارد برنامه نمی‌شوند
    (پولی‌اند) — تعداد ردشده‌ها در یادداشت می‌آید.
    خروجی: {"agent_key", "steps", "total_time", "has_paid", "notes", "notes_en"}
    """
    key = str(agent.get("key") or "?")
    tb = int(agent.get("time_budget") or 30)
    tn = [h for h in (testnets or []) if isinstance(h, dict)]
    live = _persona_pools(agent, pools)
    rej_fa, rej_en = _pool_reject_note(live, pools)
    steps: List[dict] = []
    notes: List[str] = [rej_fa]
    notes_en: List[str] = [rej_en]

    if key == "zero":
        # ارزان‌ترین‌ها بر حسب دقیقه: ماینینگ + نقاط + کوتاه‌ترین تست‌نت‌ها تا سقف بودجه
        tn.sort(key=lambda h: (int(h.get("minutes") or 15), str(h.get("name") or "")))
        acc = 0
        if 5 <= tb:
            steps.append(dict(_MINING_STEP))
            acc += 5
        if acc + 10 <= tb:
            steps.append(dict(_POINTS_STEP))
            acc += 10
        for h in tn:
            m = int(h.get("minutes") or 15)
            if acc + m <= tb:
                steps.append(_testnet_step(h))
                acc += m

    elif key == "cautious":
        # جاافتاده‌ترین تست‌نت (قدیمی‌ترینِ added) + نقاط؛ بدون لاتاریِ ماینینگ
        tn.sort(key=lambda h: (str(h.get("added") or ""), int(h.get("minutes") or 15),
                               str(h.get("name") or "")))
        acc = 0
        if acc + 10 <= tb:
            steps.append(dict(_POINTS_STEP))
            acc += 10
        for h in tn:
            m = int(h.get("minutes") or 15)
            if acc + m <= tb:
                steps.append(_testnet_step(h))
                acc += m
                break                       # یک لاتاریِ جاافتاده کافی است
        notes.append("لاتاریِ ماینینگِ موبایلی برای این ایجنت نامعین است — وقت معین می‌رود سراغ جاافتاده‌ترین‌ها.")
        notes_en.append("The mobile-mining lottery is too uncertain for this agent — fixed time goes to the longest-running ones.")

    elif key == "aggressive":
        # بیشترین پوششِ رایگان: ماینینگ + نقاط + همه‌ی تست‌نت‌ها (کوتاه‌تر اول)
        tn.sort(key=lambda h: (int(h.get("minutes") or 15), str(h.get("name") or "")))
        acc = 0
        steps.append(dict(_MINING_STEP))
        acc += 5
        steps.append(dict(_POINTS_STEP))
        acc += 10
        for h in tn:
            m = int(h.get("minutes") or 15)
            if acc + m <= tb:
                steps.append(_testnet_step(h))
                acc += m
        notes.append("هر گام این برنامه رایگان است؛ بلیت بیشتر فقط یعنی دقیقه‌ی بیشتر، نه دلار بیشتر.")
        notes_en.append("Every step here is free; more tickets only means more minutes, not more dollars.")

    elif key == "busy":
        # ۱۵ دقیقه سفت‌وسخت: دو دنیا در یک ربع — ماینینگ + نقاط
        acc = 0
        if acc + 5 <= tb:
            steps.append(dict(_MINING_STEP))
            acc += 5
        if acc + 10 <= tb:
            steps.append(dict(_POINTS_STEP))
            acc += 10
        notes.append("قانونِ این ایجنت: ۱۵ دقیقه در روز — نه یک ثانیه بیشتر؛ تست‌نت‌ها برای روزهای زمان‌دار.")
        notes_en.append("This agent's law: 15 minutes a day — not a second more; testnets belong to longer days.")

    elif key == "quant":
        # EV پولی لاتاری‌ها نامعین است — کمیتِ قطعی: قیمتِ زمانی. کمینه‌سازی دقیقه + پوشش دو دنیا.
        tn.sort(key=lambda h: (int(h.get("minutes") or 15), str(h.get("name") or "")))
        acc = 0
        if 5 <= tb:
            steps.append(dict(_MINING_STEP))
            acc += 5
        if acc + 10 <= tb:
            steps.append(dict(_POINTS_STEP))
            acc += 10
        for h in tn:
            m = int(h.get("minutes") or 15)
            if acc + m <= tb:
                steps.append(_testnet_step(h))
                acc += m
        for st in steps:
            st["ev"] = float(st.get("time_min") or 0)
            st["why"] += f" · EV پولی: نامعین (لاتاری) — قیمتِ قطعی: فقط {st['time_min']} دقیقه"
            st["why_en"] += f" · money-EV: unknowable (lottery) — the hard price: only {st['time_min']} min"
    else:
        # شخصیت ناشناخته → برنامه‌ی حداقلیِ امن (فقط یک تست‌نت کوتاه)
        tn.sort(key=lambda h: (int(h.get("minutes") or 15), str(h.get("name") or "")))
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

    قانون میدان (درخواست کاربر): **هر گامِ پولی برای هر ایجنتی جریمه‌ی سنگین
    دارد** — این میدان بودجه‌ی صفر دارد. سرریزِ زمان جریمه‌ی متناسب؛ تنوعِ نوع
    گام پاداش؛ پوششِ دو دنیا (فارمِ رایگان + ماینینگِ رایگان) پاداشِ ویژه؛
    پوششِ ≥۴ گام پاداش؛ گامِ EV صریح پاداش؛ ناهماهنگی ریسک با شخصیتِ محتاط
    جریمه (زنجیره‌ی ایمنی برای گام‌های پرنوسانِ آینده).
    """
    steps = [s for s in (plan.get("steps") or []) if isinstance(s, dict)]
    score = 55.0 if steps else 5.0
    flags: List[str] = []
    budget = str(agent.get("budget") or "any")
    tb = max(int(agent.get("time_budget") or 30), 1)

    if plan.get("has_paid"):
        # بودجه‌ی صفر قانونِ همه‌ی ایجنت‌هاست — نه فقط صفر-پول (به درخواست کاربر)
        score -= 45.0
        flags.append("budget_violation")
    excess = int(plan.get("total_time") or 0) - tb
    if excess > 0:
        score -= min(30.0, excess / tb * 30.0)
        flags.append("time_over")
    kinds = {str(s.get("kind") or "") for s in steps}
    if len(kinds) >= 2:
        score += 8.0
    if (kinds & _FREE_FARM_SIDE) and (kinds & _FREE_MINE_SIDE):
        score += 10.0                   # پوششِ دو دنیا: فارمینگِ رایگان + ماینینگِ رایگان
    if len(steps) >= 4:
        score += 5.0                    # پوششِ گسترده‌تر از حداقل
    if float(agent.get("risk", 0.5)) <= 0.2 and any(
            "high_sigma" in (s.get("flags") or []) or "predicted_down" in (s.get("flags") or [])
            for s in steps):
        score -= 15.0
        flags.append("risk_mismatch")
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
