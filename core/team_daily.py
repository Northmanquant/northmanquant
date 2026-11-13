# -*- coding: utf-8 -*-
"""core/team_daily.py — گزارشِ روزانه‌ی اتاقِ تیم در تلگرام
==========================================================
هر روز یک‌بار: یک جلسه‌ی کاملِ اتاقِ تیم (۵ عامل: خبرنگار، دیدبان، چارت‌خوان،
مدیرِ ریسک، شکاک) روی یک ارزِ در چرخش اجرا می‌شود و خلاصه‌ی فارسی‌اش به چت
تلگرام می‌رود — از همان باتِ موجود با Secretهای TELEGRAM_BOT_TOKEN /
TELEGRAM_CHAT_ID.

اجرا:  python -m core.team_daily      (روی GitHub Actions هر روز ۱۴:۰۰ تهران)
تنظیم (همه اختیاری):
    TEAM_DAILY_SYMBOL    نمادِ ثابت به‌جای چرخش (مثلاً BTC-USDT)
    TEAM_DAILY_EXCHANGE  صرافی (پیش‌فرض OKX)
    TEAM_DAILY_INTERVAL  تایم‌فریم (پیش‌فرض 1hour)
    TEAM_DAILY_CAPITAL   سرمایه‌ی مدیرِ ریسک (پیش‌فرض 1000 دلار)
    TEAM_DAILY_RISK_PCT  ریسکِ هر معامله٪ (پیش‌فرض 1.0)

منطق:
  • اگر بات تنظیم نباشد → بی‌صدا رد می‌شود (exit 0 — Actions قرمز نمی‌شود)
  • اگر جلسه به‌کلی شکست بخورد → یک notify_failure می‌فرستد (exit 0)
  • هیچ‌وقت exception بالا نمی‌دهد — ارائه هرگز نباید توقفت کند
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta

from core import telegram as TG
from core import team_room as TR

sys.path.insert(0, __file__.rsplit("/", 2)[0])  # ریشه‌ی پروژه برای import اپ

EXCHANGE_DEFAULT = TR.EXCHANGE_DEFAULT
INTERVAL_DEFAULT = TR.INTERVAL_DEFAULT
CANDIDATES = [
    "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT",
    "DOGE-USDT", "ADA-USDT", "AVAX-USDT", "LINK-USDT", "TON-USDT",
    "SUI-USDT", "NEAR-USDT", "LTC-USDT", "DOT-USDT",
]

TEHRAN = timezone(timedelta(hours=3, minutes=30))
_WEEK_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]

_VERDICT_ICON = {"align": "✅", "object": "⛔", "wait": "⏸"}
_CHECK_ICON = {"اعتراض": "⛔", "هشدار": "⚠️", "تایید": "✅", "بی‌طرف": "➖"}


# ------------------------------------------------------------------ انتخابِ نماد
def pick_symbol(candidates: list | None = None, day: int | None = None) -> str:
    """چرخشِ روزانه‌ی نماد — هر روز یکی از لیست؛ قطعی و بدونِ شانس.

    day = روزِ سال (tm_yday)؛ در تست‌ها به‌صورت صریح داده می‌شود."""
    cands = list(candidates or CANDIDATES) or ["BTC-USDT"]
    idx = int(day if day is not None else datetime.now(TEHRAN).timetuple().tm_yday)
    return cands[idx % len(cands)]


# ------------------------------------------------------------------ قالب‌بندی
def _esc(s: str) -> str:
    """ایمن‌سازیِ HTML تلگرام: «&» و «<» خام فرار می‌کنند، فقط <b> می‌ماند."""
    s = str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")


def _chart_line(plan: dict, dec: int) -> str:
    """یک خطِ خلاصه‌ی طرح — فعال: سطوح، انتظار: شرطِ معتبرشدن."""
    if plan.get("status") == "active" and plan.get("entry") and plan.get("stop"):
        tps = plan.get("targets") or []
        tp1 = tps[0][0] if tps and isinstance(tps[0], tuple) else (tps[0] if tps else None)
        line = (f"{plan.get('direction')} — ورود <b>{plan['entry']:,.{dec}f}</b> · "
                f"حدضرر <b>{plan['stop']:,.{dec}f}</b>")
        if tp1:
            line += f" · هدفِ اول <b>{tp1:,.{dec}f}</b>"
        line += f" · R:R {plan.get('rr')}R · اعتماد {plan.get('confidence')}٪"
        return line
    why = str(plan.get("why") or "ستاپِ معتبر نبود")[:110]
    return f"⏸ انتظار — {why}"


def _risk_line(agents: dict) -> str:
    """خطِ مدیرِ ریسک — ادعای اندازه اگر بود، وگرنه پیامِ صادقانه‌ی «بدون سیگنال»."""
    ra = agents.get("risk") or {}
    cl = next((c for c in (ra.get("claims") or []) if c.get("size")), None)
    if cl:
        return _esc(cl["claim"])
    for m in (ra.get("msgs") or []):
        t = str(m.get("text") or "")
        if "پوزیشنی برای اندازه‌دادن نیست" in t or "سرمایه‌ای وارد نشده" in t:
            return _esc(t)
    return "بدون سیگنالِ فعال — اندازه‌ای صادر نشد"


def _agent_block(a: dict, max_msgs: int = 2) -> list[str]:
    """سرتیترِ عامل + حداکثر n پیامِ او (متنِ پیام‌ها از قبل HTML-safe ماژولِ خودشان)."""
    lines = [f"<b>{a.get('emoji')} {a.get('name')}:</b>"]
    for m in (a.get("msgs") or [])[:max_msgs]:
        lines.append(f"  • {_esc(m.get('text'))}")
    return lines


def build_report_text(room: dict, max_chars: int | None = None) -> str:
    """خلاصه‌ی جلسه‌ی تیم به HTML تلگرام — سقفِ MAX_TEXT، بدونِ exception."""
    cap_chars = int(max_chars or TG.MAX_TEXT)
    sym = room.get("symbol", "?")
    dec = int(room.get("dec") or 4)
    now = datetime.now(TEHRAN)
    agents = room.get("agents") or {}
    plan = room.get("plan") or {}
    vd = room.get("verdict") or {}
    sk = room.get("skeptic") or {}
    qc = (plan.get("qc") or {})
    stamp = str(qc.get("stamp") or "")

    lines = [
        f"🤝 <b>جلسه‌ی تیمِ تحلیل — {_esc(sym)}</b>",
        f"{_WEEK_FA[now.weekday()]} · {room.get('ts')} تهران · "
        f"{room.get('exchange')} · {room.get('interval')}",
        "",
        f"{_VERDICT_ICON.get(vd.get('state'), '⚖️')} <b>حکمِ تیم:</b> {_esc(vd.get('title'))}",
        f"<i>(اعتراض {vd.get('n_obj', 0)} · هشدار {vd.get('n_warn', 0)} · "
        f"تایید {vd.get('n_confirm', 0)})</i>",
        "",
    ]

    # پنج عامل — به ترتیبِ جلسه
    news_a = agents.get("news")
    if news_a:
        lines += _agent_block(news_a)
        lines.append("")
    watch_a = agents.get("watchdog")
    if watch_a:
        lines += _agent_block(watch_a)
        lines.append("")
    lines.append(f"<b>📊 چارت‌خوان:</b> {_esc(_chart_line(plan, dec))}")
    lines.append("")
    lines.append(f"<b>💼 مدیرِ ریسک:</b> {_risk_line(agents)}")
    lines.append("")

    # شکاک — داوری‌ها
    lines.append("<b>🧐 شکاک:</b>")
    checks = list(sk.get("checks") or [])
    for c in checks[:8]:
        icon = _CHECK_ICON.get(c.get("verdict"), "•")
        reason = _esc(str(c.get("reason") or ""))[:150]
        lines.append(f"  {icon} <b>{_esc(c.get('target'))}</b> — {reason}")
    if not checks:
        lines.append("  • داوری‌ای ثبت نشد")
    lines.append("")

    if stamp:
        lines.append(f"📎 مُهرِ داده: {_esc(stamp)}")
    lines.append("<i>حکمِ شکاک از سیگنال بالاتر است — این گزارش تحلیل است، نه سفارشِ خرید/فروش.</i>")
    return "\n".join(lines)[:cap_chars]


# ------------------------------------------------------------------ اجرا
def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def run(exchange: str | None = None, symbol: str | None = None,
        interval: str | None = None, capital: float | None = None,
        risk_pct: float | None = None) -> str:
    """کلِ جریانِ روزانه — رشته‌ی وضعیت برمی‌گرداند، هیچ‌وقت exception نمی‌دهد."""
    if not TG.enabled():
        print("🔇 تلگرام تنظیم نیست — TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID — رد شد", flush=True)
        return "غیرفعال"
    ex = exchange or os.environ.get("TEAM_DAILY_EXCHANGE", EXCHANGE_DEFAULT)
    sym = symbol or os.environ.get("TEAM_DAILY_SYMBOL") or pick_symbol()
    iv = interval or os.environ.get("TEAM_DAILY_INTERVAL", INTERVAL_DEFAULT)
    cap = capital if capital is not None else _env_float("TEAM_DAILY_CAPITAL", 1000.0)
    rp = risk_pct if risk_pct is not None else _env_float("TEAM_DAILY_RISK_PCT", 1.0)
    try:
        room = TR.investigate(exchange=ex, symbol=sym, interval=iv, with_news=True,
                              capital=cap, risk_pct=rp)
    except Exception as exc:  # noqa: BLE001
        TG.notify_failure("team-daily", f"{type(exc).__name__}: {exc}")
        return "خطای جلسه"
    if not room.get("ok"):
        TG.notify_failure("team-daily", str(room.get("error") or "جلسه‌ی تیم برنگشت"))
        return "خطای جلسه"
    ok = TG.send(build_report_text(room))
    print(f"{'✅' if ok else '⚠️'} گزارشِ تیم ({sym}): {'OK' if ok else 'FAIL'}", flush=True)
    print(f"  حکم: {(room.get('verdict') or {}).get('title', '؟')}", flush=True)
    return "فرستاده شد" if ok else "ارسال ناموفق"


def main() -> int:
    print("== NorthmanQuant — گزارشِ روزانه‌ی اتاقِ تیم در تلگرام ==", flush=True)
    print(f"نمادِ امروز (چرخش): {pick_symbol()}", flush=True)
    status = run()
    print(f"وضعیت: {status}", flush=True)
    return 0  # Actions هیچ‌وقت قرمز نمی‌شود — وضعیت از طریق خود تلگرام معلوم است


if __name__ == "__main__":
    raise SystemExit(main())
