# -*- coding: utf-8 -*-
"""core/dossier.py — پرونده‌ی بهبود ایجنت‌ها (فاز ۱۴: تحقیق ← تشخیص ← نسخه ← اعتبارسنجی)
=========================================================================================
لایه‌ی سوم «آزمایشگاه»، بعد از کالبدشکافی (autopsy) و تطبیق پنالتی‌محور (agent_lab).
اینجا برای هر ایجنتِ ضعیف یک «پرونده‌ی پزشکی» ساخته می‌شود:

  ۱) تشخیص — از برچسب‌های کالبدشکافی: ضعف غالب ایجنت چیست؟ (متنی، شفاف)
  ۲) نسخه — سه درمانِ محافظه‌کارانه‌ی تازه (علاوه بر پنالتی‌های فاز ۱۳):
       🚫 تعلیق مشروط   — پنجره‌ی ۲۱ روزه با ≥۵ بسته‌شده و انتظاری ≤ -۰.۲۵R
                           → ورود جدید ممنوع *تا وقتی* شرط برقرار است
                           (stateless و خود-التیام: بدون ترید تازه، پنجره کهنه می‌شود و خودش باز می‌گردد)
       🎯 سهمیه‌ی تک‌پوزیشن — n≥6 و انتظاری<۰ و PF<۱ → حداکثر ۱ پوزیشن هم‌زمان (به‌جای سقف عمومی)
       🎚️ فیلتر کیفیت    — n≥8 و نیمه‌ی کم‌امتیازش به‌قدر کافی بدتر → فقط سیگنال با |score| ≥ میانه‌ی خودش
  ۳) اعتبارسنجی ضدواقعی — هر نسخه قبل از کار، روی تاریخچه‌ی همان ایجنت «پخش مجدد» می‌شود:
       اگر آن موقع اعمال می‌شد، چند ضرر حذف می‌شد (saved) و چند سود از دست می‌رفت (missed)؟
       گate علمی: فقط نسخه‌ای کار می‌شود که net = saved − missed ≥ ۰ باشد.

همه‌چیز stateless است (هر بار از صفر از روی معاملات بسته محاسبه می‌شود — بدون حافظه‌ی
مخفی، بدون جدول تازه‌ی دیتابیس) و در Actions/اپ/سایت یکسان کار می‌کند.
هیچ نسخه‌ای ریسک را بزرگ نمی‌کند: فقط «ورود» را کم یا سخت‌تر می‌کند؛ مدیریت پوزیشن باز
(استاپ/TP/تریل) دست‌نخورده می‌ماند.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Dict, List, Optional

from core import agent_lab as LAB
from core import autopsy as AU
from core import edge as EG                       # فقط agent_stats — بدون شبکه
from core.arena_store import _utcnow_iso

# ---------------------------------------------------------------- آستانه‌ها (شفاف)
SUSP_WINDOW_D = 21          # پنجره‌ی زمانی تعلیق (روز)
SUSP_MIN_N = 5              # حداقل بسته‌شده در پنجره
SUSP_EXP = -0.25            # انتظاری آستانه‌ی تعلیق (R هر معامله)
QUOTA_MIN_N = 6             # حداقل بسته‌شده برای کاه سهمیه
QUOTA_MAX_PF = 1.0          # PF آستانه (زیر ۱ = ضررده)
FLOOR_MIN_N = 8             # حداقل نمونه برای فیلتر کیفیت
FLOOR_MIN_EDGE = 0.15       # اختلاف انتظاری لازم بین دو نیمه (R)

LESSON_FA: Dict[str, str] = {
    "tight_stop": "استاپ‌ها زود می‌خورند — ورود دیرهنگام یا نزدیک نویز؛ نسخه: فقط سیگنال پرقدرت",
    "quick_stop": "ورود بی‌حوصله — استاپ در چند کندل اول می‌خورد؛ نسخه: فیلتر کیفیت",
    "timeout_negative": "بازار همراهی نمی‌کند و معامله بی‌سود می‌میرد؛ نسخه: سهمیه‌ی تک‌پوزیشن برای انتخاب‌گری بالاتر",
    "giveback": "بعد از TP1 سود پس داده می‌شود؛ درمان با کاهش ورود است نه سفت‌کردن تریل (ریسک بیشتر نمی‌سازیم)",
    "deep_loss": "ضررها عمیق‌اند؛ نسخه: سهمیه‌ی تک‌پوزیشن + فیلتر کیفیت",
    "against_regime": "خلاف روند BTC معامله می‌کند؛ نسخه: انضباط رژیم (در تب «تطبیق فعال»)",
    "regime_flip": "ضررها از برگشت رژیم‌اند — تقصیر ورود نیست؛ پایش می‌کنیم",
}
LESSON_EN: Dict[str, str] = {
    "tight_stop": "Stops get hit early — late entries or noise-level stops; fix: strong signals only",
    "quick_stop": "Impatient entries — stop hit within the first candles; fix: quality filter",
    "timeout_negative": "Market never follows; trades die at timeout in loss; fix: single-slot quota",
    "giveback": "Profit given back after TP1; fix is fewer entries, not tighter trailing",
    "deep_loss": "Losses run deep; fix: single-slot quota + quality filter",
    "against_regime": "Trades against the BTC trend; fix: regime discipline (see adaptations tab)",
    "regime_flip": "Losses come from regime flips — not the entry's fault; monitoring",
}


def _parse(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _r(t: Dict[str, Any]) -> float:
    return float(t.get("realized_r") or 0.0)


def _open_ts(t: Dict[str, Any]) -> Optional[datetime]:
    return _parse(t.get("opened_at")) or _parse(t.get("created_at"))


def _exp(ts: List[Dict[str, Any]]) -> float:
    return (sum(_r(t) for t in ts) / len(ts)) if ts else 0.0


# ---------------------------------------------------------------- اعتبارسنجی ضدواقعی
def _validate(blocked: List[Dict[str, Any]]) -> Dict[str, Any]:
    """جمع‌بندی یک پخش‌مجدد: چند ضرر حذف می‌شد، چند سود از دست می‌رفت؟
    verdict: ok یعنی net ≥ ۰ (نسخه مجاز به کار شدن) / reject یعنی زیان‌ده."""
    rs = [_r(t) for t in blocked]
    saved = -sum(r for r in rs if r < 0.0)
    missed = sum(r for r in rs if r > 0.0)
    net = round(saved - missed, 2)
    return {"blocked_n": len(blocked),
            "saved_loss_r": round(saved, 2),
            "missed_win_r": round(missed, 2),
            "net": net,
            "verdict": "ok" if net >= 0.0 else "reject"}


def validate_suspension(mine: List[Dict[str, Any]]) -> Dict[str, Any]:
    """پخش مجدد تعلیق: هر معامله‌ای که *هنگام بازشدن* شرط پنجره برقرار بوده، بلاک شده."""
    ev = sorted([t for t in mine if _open_ts(t)], key=_open_ts)
    blocked: List[Dict[str, Any]] = []
    for t in ev:
        ot = _open_ts(t)
        w0 = ot - timedelta(days=SUSP_WINDOW_D)
        prior = [x for x in ev
                 if x is not t
                 and (_parse(x.get("closed_at")) or _open_ts(x))
                 and w0 <= (_parse(x.get("closed_at")) or _open_ts(x)) <= ot]
        if len(prior) >= SUSP_MIN_N and _exp(prior) <= SUSP_EXP:
            blocked.append(t)
    return _validate(blocked)


def validate_quota(mine: List[Dict[str, Any]]) -> Dict[str, Any]:
    """پخش مجدد سهمیه‌ی تک‌پوزیشن: ورودهای هم‌زمانِ دوم به بعد بلاک می‌شوند."""
    ev = sorted([t for t in mine if _open_ts(t)], key=_open_ts)
    blocked: List[Dict[str, Any]] = []
    active: List[Dict[str, Any]] = []
    for t in ev:
        ot = _open_ts(t)
        active = [x for x in active
                  if (_parse(x.get("closed_at")) or ot) > ot]
        if active:
            blocked.append(t)
        else:
            active.append(t)
    return _validate(blocked)


def score_halves(mine: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """تقسیم معاملات ایجنت به دو نیمه بر اساس |score| (میانه) + آمار هر نیمه."""
    xs = [abs(float(t.get("score") or 0.0)) for t in mine]
    if len(xs) < FLOOR_MIN_N or not any(x > 0 for x in xs):
        return None
    med = float(median(xs))
    if med <= 0.0:
        return None
    lo = [t for t, x in zip(mine, xs) if x < med]
    hi = [t for t, x in zip(mine, xs) if x >= med]
    if not lo or not hi:
        return None
    return {"median": med, "lo_exp": _exp(lo), "hi_exp": _exp(hi),
            "lo_n": len(lo), "hi_n": len(hi)}


# ---------------------------------------------------------------- تشخیص
def diagnose(mine: List[Dict[str, Any]], regime_alerts: List[Dict[str, Any]],
             lang: str = "fa") -> Dict[str, Any]:
    """تشخیص متنی ضعف غالب ایجنت از برچسب‌های کالبدشکافی."""
    au = AU.autopsy_all(mine, regime_alerts)
    codes: Dict[str, int] = {}
    for t in mine:
        for c in (au.get(str(t.get("id"))) or {}).get("codes", []):
            codes[c] = codes.get(c, 0) + 1
    ordered = sorted(codes.items(), key=lambda kv: (-kv[1], kv[0]))
    dominant = [c for c, n in ordered if n >= 2][:2]
    book = LESSON_FA if lang == "fa" else LESSON_EN
    note = " · ".join(book.get(c, c) for c in dominant) if dominant else (
        "الگوی مرگ غالبی ثبت نشده — پایش می‌کنیم" if lang == "fa"
        else "No dominant failure pattern yet — monitoring")
    return {"tags": codes, "dominant": dominant, "note_fa": note if lang == "fa" else None,
            "note_en": note if lang != "fa" else None}


# ---------------------------------------------------------------- نسخه‌سازی
def propose(mine: List[Dict[str, Any]], now: datetime) -> Dict[str, Any]:
    """نسخه‌ی محافظه‌کارانه‌ی ایجنت + اعتبارسنجی هر بند.
    فقط بندهایی که هم شواهد آماری دارند هم اعتبارسنجی net≥۰ کار می‌شوند."""
    st = EG.agent_stats(mine)
    lim: Dict[str, Any] = {}
    val: Dict[str, Dict[str, Any]] = {}

    # ۱) تعلیق مشروط — پنجره‌ی زمانی (خود-التیام)
    v_susp = validate_suspension(mine)
    w0 = now - timedelta(days=SUSP_WINDOW_D)
    recent = [t for t in mine
              if (_parse(t.get("closed_at")) or _open_ts(t) or
                  datetime.min.replace(tzinfo=timezone.utc)) >= w0]
    if (len(recent) >= SUSP_MIN_N and _exp(recent) <= SUSP_EXP
            and v_susp["verdict"] == "ok"):
        lim["suspended"] = True
    val["suspension"] = v_susp

    # ۲) سهمیه‌ی تک‌پوزیشن — ضررده‌ی مزمن
    v_quota = validate_quota(mine)
    if (st["n"] >= QUOTA_MIN_N and st["exp"] < 0.0 and st["pf"] < QUOTA_MAX_PF
            and v_quota["verdict"] == "ok"):
        lim["max_pos"] = 1
    val["quota"] = v_quota

    # ۳) فیلتر کیفیت — فقط نیمه‌ی پرامتیاز
    halves = score_halves(mine)
    if halves and (halves["hi_exp"] - halves["lo_exp"]) >= FLOOR_MIN_EDGE \
            and halves["lo_exp"] < 0.0:
        below = [t for t in mine
                 if abs(float(t.get("score") or 0.0)) < halves["median"]]
        v_floor = _validate(below)
        if v_floor["verdict"] == "ok":
            lim["score_floor"] = round(halves["median"], 3)
        val["quality"] = v_floor

    return {"limits": lim, "validation": val, "halves": halves}


# ---------------------------------------------------------------- پرونده‌ی کامل
def compute_dossier(trades: List[Dict[str, Any]],
                    regime_alerts: Optional[List[Dict[str, Any]]] = None,
                    now: Optional[datetime] = None) -> Dict[str, Any]:
    """پرونده‌ی بهبود همه‌ی ایجنت‌ها — stateless، خوراک اتوپایلوت + صفحه‌ی آزمایشگاه."""
    now = now or datetime.now(timezone.utc)
    closed = LAB.closed_sorted(trades)
    au_all = AU.autopsy_all(closed, regime_alerts or [])
    names = sorted({str(t.get("agent") or "") for t in trades} - {""})
    agents: Dict[str, Dict[str, Any]] = {}
    for nm in names:
        mine = [t for t in closed if str(t.get("agent")) == nm]
        if not mine:
            continue
        st = EG.agent_stats(mine)
        codes = {}
        for t in mine:
            for c in (au_all.get(str(t.get("id"))) or {}).get("codes", []):
                codes[c] = codes.get(c, 0) + 1
        prop = propose(mine, now)
        status = "active" if prop["limits"] else (
            "monitoring" if st["exp"] < 0.0 and st["n"] >= 3 else "healthy")
        agents[nm] = {
            "n": st["n"], "exp": round(st["exp"], 3), "pf": round(min(st["pf"], 99.0), 2),
            "status": status,
            "weakness": dict(sorted(codes.items(), key=lambda kv: -kv[1])),
            "limits": prop["limits"],
            "validation": prop["validation"],
        }
    return {"agents": agents,
            "counts": {"suspended": sum(1 for a in agents.values() if a["limits"].get("suspended")),
                       "quota_cut": sum(1 for a in agents.values() if a["limits"].get("max_pos")),
                       "score_floor": sum(1 for a in agents.values() if a["limits"].get("score_floor"))},
            "generated_at": _utcnow_iso()}
