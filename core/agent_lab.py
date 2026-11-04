# -*- coding: utf-8 -*-
"""core/agent_lab.py — آزمایشگاه ایجنت‌ها (فاز ۱۳: تحقیق + خودبهبود)
=====================================================================
دو نیمه‌ی مکمل روی داده‌ی زنده‌ی میدان (معاملات واقعی Supabase):

الف) کارنامه‌ی تحقیقاتی هر ایجنت — n/وین‌ریت/انتظاری/PF/زنجیره‌ی ضرر/
    فرم ۱۰تایی + تفکیک دلیل خروج + برچسب‌های کالبدشکافی. این است
    «سطح علمی و کاربردی» که کاربر خواست: ضعف هر ایجنت شفاف می‌شود.

ب) تطبیق خودکار (Adaptation) — از دل تاریخچه، محدودیت‌های محافظه‌کارانه
    ساخته می‌شود؛ stateless است (هر بار از صفر از روی معاملات محاسبه
    می‌شود — نیازی به ذخیره ندارد و در Actions/اپ یکسان کار می‌کند):

      ۱) سرد شدن پلکانی — زنجیره‌ی باخت متوالی ≥۳ → ×۲، ≥۵ → ×۳، ≥۷ → ×۴
         (ضریب روی cooldown پایه‌ی نماد/جهت — ایجنت داغ دوباره سوخت می‌گیرد)
      ۲) ممنوعیت نماد — (ایجنت، نماد) با ≥۳ باخت و ۰ برد در ۱۴ روز →
         تا ۷ روز بعد از آخرین باخت روی آن نماد معامله نمی‌کند
      ۳) انضباط رژیم — اگر ≥۶۰٪ باخت‌های ایجنت (حداقل ۴ باخت) «خلاف رژیم»
         باشد → فقط هم‌جهتِ رژیم مجاز به ورود است

همه‌ی آستانه‌ها بالای فایل‌اند و شفاف. هیچ‌چیز مخرب نیست: حداکثر اثر،
کم‌تر باز کردن معامله است — نه بزرگ‌تر گرفتن ریسک.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core import autopsy as AU
from core import edge as EG  # فقط agent_stats — بدون شبکه
from core.arena_store import _utcnow_iso

# ---------------------------------------------------------------- آستانه‌ها
STREAK_L1, STREAK_L2, STREAK_L3 = 3, 5, 7          # آستانه‌های زنجیره‌ی باخت
COOL_MULT_L1, COOL_MULT_L2, COOL_MULT_L3 = 2.0, 3.0, 4.0
SYM_BAN_MIN_LOSSES = 3                             # حداقل باخت روی یک نماد
SYM_BAN_WINDOW_D = 14                              # پنجره‌ی شمارش باخت نماد
SYM_BAN_DAYS = 7                                   # مدت ممنوعیت
REGIME_DISC_SHARE = 0.60                           # سهم باختِ «خلاف رژیم»
REGIME_DISC_MIN_LOSS = 4                           # حداقل باخت برای قاعده‌ی رژیم
FORM_N = 10                                        # پنجره‌ی «فرم اخیر»


def _parse(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def closed_sorted(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """بسته‌شده‌ها مرتب بر اساس زمان بستن (قدیمی → تازه)."""
    rows = [t for t in trades if str(t.get("status")) == "closed"]
    return sorted(rows, key=lambda t: _parse(t.get("closed_at"))
                  or datetime.min.replace(tzinfo=timezone.utc))


ALL_EXCHANGES = ("همه", "all", "ALL", "All", "")


def filter_by_exchange(trades: List[Any], exchange: str) -> List[Any]:
    """فیلتر معاملات بر اساس صرافی (برای آزمایشگاه و هر گزارشی).

    exchange خالی یا «همه» = بدون فیلتر (رفتار قبلی، دست‌نخورده).
    ورودی خراب امن: trades غیرلیست = []؛ ردیف غیرdict در حالت فیلتر رد می‌شود.
    Lighter صرافیِ فعلی اتوپایلوت است و در منو اول می‌آید (UI این را می‌چیند).
    """
    if not isinstance(trades, list):
        return []
    ex = str(exchange or "").strip()
    if ex in ALL_EXCHANGES:
        return list(trades)
    return [t for t in trades
            if isinstance(t, dict) and str(t.get("exchange") or "").strip() == ex]


def current_streak(agent_closed: List[Dict[str, Any]]) -> int:
    """طول زنجیره‌ی باخت فعلی ایجنت (از انتها) — برد/سربه‌سر زنجیره را قطع می‌کند."""
    n = 0
    for t in reversed(agent_closed):
        r = float(t.get("realized_r") or 0.0)
        if r < 0:
            n += 1
        else:
            break
    return n


def cool_mult_for(streak: int) -> float:
    """ضریب سرد شدن از روی زنجیره‌ی باخت — پلکانی و برگشت‌پذیر."""
    if streak >= STREAK_L3:
        return COOL_MULT_L3
    if streak >= STREAK_L2:
        return COOL_MULT_L2
    if streak >= STREAK_L1:
        return COOL_MULT_L1
    return 1.0


def symbol_bans(agent_closed: List[Dict[str, Any]], now: datetime) -> List[Dict[str, Any]]:
    """نمادهای ممنوع برای این ایجنت — چاه‌های تکراری ۱۴ روز اخیر."""
    w0 = now - timedelta(days=SYM_BAN_WINDOW_D)
    per: Dict[str, Dict[str, int]] = {}
    last_loss: Dict[str, datetime] = {}
    for t in agent_closed:
        c = _parse(t.get("closed_at"))
        if c is None or c < w0:
            continue
        sym = str(t.get("symbol") or "")
        r = float(t.get("realized_r") or 0.0)
        slot = per.setdefault(sym, {"losses": 0, "wins": 0})
        if r < 0:
            slot["losses"] += 1
            if sym not in last_loss or c > last_loss[sym]:
                last_loss[sym] = c
        elif r > 0:
            slot["wins"] += 1
    out = []
    for sym, s in per.items():
        if s["losses"] >= SYM_BAN_MIN_LOSSES and s["wins"] == 0:
            until = last_loss[sym] + timedelta(days=SYM_BAN_DAYS)
            if until > now:
                out.append({"symbol": sym, "until": until,
                            "losses": s["losses"]})
    return out


def compute_adaptations(trades: List[Dict[str, Any]], now: Optional[datetime] = None,
                        regime_alerts: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """سیاست تطبیق کامل از روی تاریخچه — stateless.
    regime_alerts فقط برای قاعده‌ی «انضباط رژیم» لازم است؛ بدون آن آن قاعده خاموش می‌ماند."""
    now = now or datetime.now(timezone.utc)
    au = AU.autopsy_all(closed_sorted(trades), regime_alerts or [])
    agents: Dict[str, Dict[str, Any]] = {}
    bans: List[Dict[str, Any]] = []
    names = sorted({str(t.get("agent") or "") for t in trades} - {""})

    for nm in names:
        mine = [t for t in closed_sorted(trades) if str(t.get("agent")) == nm]
        if not mine:
            continue
        streak = current_streak(mine)
        rec: Dict[str, Any] = {
            "streak": streak,
            "cool_mult": cool_mult_for(streak),
            "penalty_until": None,
            "regime_only": False,
            "form10_r": round(sum(float(t.get("realized_r") or 0.0)
                                  for t in mine[-FORM_N:]), 2),
        }
        if streak >= STREAK_L1:
            # تا وقتی باخت متوالی است، سرد شدن فعال بماند؛ طول واقعی cooldown
            # در لحظه‌ی بازکردن معامله اعمال می‌شود (ضریب روی cooldown پایه).
            rec["penalty_until"] = (now + timedelta(hours=1)).isoformat()
        # انضباط رژیم — از برچسب‌های کالبدشکافی
        my_losses = [t for t in mine if float(t.get("realized_r") or 0.0) < 0]
        if len(my_losses) >= REGIME_DISC_MIN_LOSS and regime_alerts:
            against = sum(1 for t in my_losses
                          if "against_regime" in (au.get(str(t.get("id"))) or {}).get("codes", []))
            if against / len(my_losses) >= REGIME_DISC_SHARE:
                rec["regime_only"] = True
        agents[nm] = rec

        for b in symbol_bans(mine, now):
            bans.append({"agent": nm, **b})

    return {"agents": agents, "symbol_bans": bans,
            "generated_at": _utcnow_iso(),
            "counts": {"penalized": sum(1 for a in agents.values()
                                        if a["cool_mult"] > 1.0),
                       "regime_only": sum(1 for a in agents.values()
                                          if a["regime_only"]),
                       "bans": len(bans)}}


# ---------------------------------------------------------------- کارنامه
def agent_report(trades: List[Dict[str, Any]],
                 regime_alerts: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
    """کارنامه‌ی تحقیقاتی هر ایجنت از معاملات زنده — خوراک صفحه‌ی آزمایشگاه."""
    closed = closed_sorted(trades)
    au = AU.autopsy_all(closed, regime_alerts or [])
    names = sorted({str(t.get("agent") or "") for t in trades} - {""})
    out: Dict[str, Dict[str, Any]] = {}
    for nm in names:
        mine = [t for t in closed if str(t.get("agent")) == nm]
        st_total = EG.agent_stats(mine)
        rs = [float(t.get("realized_r") or 0.0) for t in mine]
        by_exit: Dict[str, int] = {}
        for t in mine:
            ex = str(t.get("exit_reason") or "—")
            by_exit[ex] = by_exit.get(ex, 0) + 1
        codes: Dict[str, int] = {}
        for t in mine:
            for c in (au.get(str(t.get("id"))) or {}).get("codes", []):
                codes[c] = codes.get(c, 0) + 1
        out[nm] = {
            "n": st_total["n"],
            "winrate": round(100.0 * st_total["wins"] / (st_total["wins"] + st_total["losses"]), 1)
                       if (st_total["wins"] + st_total["losses"]) else None,
            "exp": round(st_total["exp"], 3),
            "pf": round(min(st_total["pf"], 99.0), 2),
            "total_r": round(st_total["total_r"], 2),
            "streak": current_streak(mine),
            "form10_r": round(sum(rs[-FORM_N:]), 2),
            "by_exit": by_exit,
            "weakness": dict(sorted(codes.items(), key=lambda kv: -kv[1])),
        }
    return out
