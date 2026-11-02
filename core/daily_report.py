# -*- coding: utf-8 -*-
"""core/daily_report.py — فاز ۸: گزارش روزانه‌ی میدان ایجنت‌ها
==================================================================
هر روز ساعت ۰۹:۰۰ تهران (۰۵:۳۰ UTC) از داده‌های موجود میدان یک گزارش
جمع‌بندی ۲۴ ساعته می‌سازد — بدون هیچ وابستگی یا Secret تازه:

  • بسته‌شده‌های ۲۴ ساعت: نتیجه، R خالص، دلیل خروج
  • بازشده‌های ۲۴ ساعت: ایجنت، نماد، جهت، ورود
  • وین‌ریت، جمع R و جمع امتیازِ ۲۴ ساعت + بهترین/بدترین معامله
  • پوزیشن‌های باز فعلی میدان
  • آخرین رژیم بازار ثبت‌شده (از هشدارهای رژیم)
  • جمع‌بندی کل میدان (تمام تاریخ)

منبع داده: core.arena_store (جدول arena_trades) و core.alerts (جدول
arena_alerts) — همان بک‌اند اپ: اول Supabase، بعد فایل محلی.
(سقف خواندن ۲۰۰۰ معامله‌ی اخیر است — مثل خود اپ.)

اجرا از ریشه‌ی ریپو:
    python -m core.daily_report

خروجی: لاگ + فایل «daily_report.md» + Step Summary (زیر Actions).
زمان‌بندی و ارسال به Issue آرشیو: .github/workflows/arena-daily-report.yml
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

TEHRAN = timezone(timedelta(hours=3, minutes=30))   # ایران بدون DST (از ۱۴۰۱)
WINDOW_H = 24

RESULT_FA = {
    "win": "برد ✅", "loss": "باخت ❌", "be": "سر‌به‌سر ⚪",
    "timeout_win": "برد (تایم‌اوت) ✅", "timeout_loss": "باخت (تایم‌اوت) ❌",
    "timeout_be": "سر‌به‌سر (تایم‌اوت) ⚪",
}
EXIT_FA = {"sl": "استاپ ❌", "trail": "تریل استاپ 🟢", "tp3": "هدف نهایی 🎯",
           "timeout": "تایم‌اوت ⏱"}


# ------------------------------------------------------------------ ابزارها
def _parse_iso(s: Any) -> Optional[datetime]:
    """پارس محتاطانه‌ی زمان ISO — «Z»، آفست‌دار و naive (فرض UTC)."""
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t


def fmt_ts(t: Optional[datetime]) -> str:
    """نمایش زمان به وقت تهران."""
    return t.astimezone(TEHRAN).strftime("%Y-%m-%d %H:%M") if t else "—"


def _dir_fa(d: Any) -> str:
    try:
        d = int(d or 0)
    except (TypeError, ValueError):
        d = 0
    return "لانگ 🟢" if d > 0 else "شورت 🔴" if d < 0 else "—"


def _fmt_price(v: Any) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    if abs(x) >= 100:
        return f"{x:,.2f}"
    return f"{x:,.6f}".rstrip("0").rstrip(".")


def _bucket(t: Dict[str, Any]) -> str:
    """برد/باخت/سر‌به‌سر — نتیجه‌های تایم‌اوت هم در همان دسته می‌روند."""
    r = str(t.get("result") or "")
    if r in ("win", "timeout_win"):
        return "win"
    if r in ("loss", "timeout_loss"):
        return "loss"
    return "be"


# ------------------------------------------------------------------ تجمیع
def aggregate(trades: List[Dict[str, Any]], now: datetime) -> Dict[str, Any]:
    """تجمیع گزارش از رکوردهای معامله — خالص و بدون I/O تا تست‌پذیر بماند."""
    w0 = now - timedelta(hours=WINDOW_H)
    closed_all = [t for t in trades if str(t.get("status")) == "closed"]

    closed_24: List[Dict[str, Any]] = []
    opened_24: List[Dict[str, Any]] = []
    for t in trades:
        ca = _parse_iso(t.get("closed_at"))
        if ca and w0 <= ca <= now:
            closed_24.append(t)
        cra = _parse_iso(t.get("created_at"))
        if cra and w0 <= cra <= now:
            opened_24.append(t)
    closed_24.sort(key=lambda t: _parse_iso(t.get("closed_at")) or now, reverse=True)

    wins = sum(1 for t in closed_24 if _bucket(t) == "win")
    losses = sum(1 for t in closed_24 if _bucket(t) == "loss")
    bes = len(closed_24) - wins - losses
    rs = [float(t.get("realized_r") or 0.0) for t in closed_24]
    pts = [float(t.get("points") or 0.0) for t in closed_24]

    aw = sum(1 for t in closed_all if _bucket(t) == "win")
    al = sum(1 for t in closed_all if _bucket(t) == "loss")
    return {
        "closed_24": closed_24, "opened_24": opened_24,
        "wins": wins, "losses": losses, "bes": bes,
        "winrate": round(100.0 * wins / (wins + losses), 1) if (wins + losses) else None,
        "sum_r": round(sum(rs), 2), "sum_points": round(sum(pts), 1),
        "best": max(closed_24, key=lambda t: float(t.get("realized_r") or 0.0)) if closed_24 else None,
        "worst": min(closed_24, key=lambda t: float(t.get("realized_r") or 0.0)) if closed_24 else None,
        "total_closed": len(closed_all),
        "total_winrate": round(100.0 * aw / (aw + al), 1) if (aw + al) else None,
        "total_r": round(sum(float(t.get("realized_r") or 0.0) for t in closed_all), 2),
    }


# ------------------------------------------------------------------ قالب
def fmt_report(agg: Dict[str, Any], open_trades: List[Dict[str, Any]],
               regime: Optional[Dict[str, Any]], now: datetime,
               backend: str) -> str:
    """ساخت متن مارک‌داون گزارش — بدون I/O تا تست‌پذیر بماند."""
    L: List[str] = []
    L.append(f"## 📊 گزارش روزانه‌ی میدان — {now.astimezone(TEHRAN):%Y-%m-%d} (به وقت تهران)")
    L.append("")
    L.append(f"**بازه:** {fmt_ts(now - timedelta(hours=WINDOW_H))} → {fmt_ts(now)}"
             f" · بک‌اند: `{backend}`")

    closed = agg["closed_24"]
    L.append("")
    L.append(f"### 🏁 بسته‌شده‌های ۲۴ ساعت: {len(closed)}")
    L.append("")
    if closed:
        L.append("| ایجنت | نماد | جهت | نتیجه | R خالص | خروج |")
        L.append("|---|---|---|---|---|---|")
        for t in closed[:15]:
            r = float(t.get("realized_r") or 0.0)
            res = RESULT_FA.get(str(t.get("result")), str(t.get("result") or "—"))
            ex = EXIT_FA.get(str(t.get("exit_reason")), str(t.get("exit_reason") or "—"))
            L.append(f"| {t.get('agent')} | {t.get('symbol')} | {_dir_fa(t.get('direction'))} "
                     f"| {res} | {r:+.2f}R | {ex} |")
        if len(closed) > 15:
            L.append("")
            L.append(f"و {len(closed) - 15} مورد دیگر…")
    else:
        L.append("در ۲۴ ساعت گذشته معامله‌ای بسته نشد — میدان آرام بود. 🌙")

    L.append("")
    L.append("### 📈 جمع‌بندی ۲۴ ساعت")
    L.append("")
    wr = f"{agg['winrate']}%" if agg["winrate"] is not None else "—"
    L.append(f"- برد/باخت/سر‌به‌سر: {agg['wins']} ✅ / {agg['losses']} ❌ / {agg['bes']} ⚪"
             f" (وین‌ریت {wr})")
    L.append(f"- جمع R خالص: **{agg['sum_r']:+.2f}R** · جمع امتیاز: {agg['sum_points']:+.1f}")
    if agg["best"] and agg["best"] is not agg["worst"]:
        b, w = agg["best"], agg["worst"]
        L.append(f"- بهترین: {b.get('symbol')} ({float(b.get('realized_r') or 0):+.2f}R)"
                 f" · بدترین: {w.get('symbol')} ({float(w.get('realized_r') or 0):+.2f}R)")

    opened = agg["opened_24"]
    L.append("")
    L.append(f"### 🟢 بازشده‌های ۲۴ ساعت: {len(opened)}")
    L.append("")
    for t in opened[:10]:
        cra = _parse_iso(t.get("created_at"))
        ts = f" ({fmt_ts(cra)})" if cra else ""
        L.append(f"- {t.get('agent')} · {t.get('symbol')} · {_dir_fa(t.get('direction'))}"
                 f" · ورود {_fmt_price(t.get('entry'))}{ts}")

    L.append("")
    L.append(f"### 📌 پوزیشن‌های باز فعلی: {len(open_trades)}")
    L.append("")
    for t in open_trades[:10]:
        L.append(f"- {t.get('agent')} · {t.get('symbol')} · {_dir_fa(t.get('direction'))}"
                 f" · ورود {_fmt_price(t.get('entry'))}")

    L.append("")
    if regime:
        try:
            d = int(regime.get("direction") or 0)
        except (TypeError, ValueError):
            d = 0
        reg_fa = ("صعودی 🟢 (BTC بالای MA)" if d > 0
                  else "نزولی 🔻 (BTC زیر MA)" if d < 0 else "نامشخص ⚪")
        L.append(f"### 🌊 رژیم بازار — {reg_fa}")
        L.append("")
        L.append(f"- BTC قیمت {_fmt_price(regime.get('price'))} · MA {_fmt_price(regime.get('ma'))}"
                 f" · آخرین ثبت: {fmt_ts(_parse_iso(regime.get('created_at')))}")
    else:
        L.append("### 🌊 رژیم بازار — هنوز رژیمی ثبت نشده ⚪")

    L.append("")
    L.append("### 🏆 کل میدان (تمام تاریخ)")
    L.append("")
    twr = f"{agg['total_winrate']}%" if agg["total_winrate"] is not None else "—"
    L.append(f"- بسته‌شده: {agg['total_closed']} · وین‌ریت {twr} · جمع R: {agg['total_r']:+.2f}R")
    L.append("")
    L.append("<sub>گزارش خودکار — هر روز ساعت ۰۹:۰۰ تهران · NorthmanQuant</sub>")
    return "\n".join(L)


# ------------------------------------------------------------------ main
def main() -> int:
    from core import alerts as AL
    from core import arena_store

    now = datetime.now(timezone.utc)
    store = arena_store.get_store()
    backend = store.backend
    print(f"📝 گزارش روزانه‌ی میدان — بک‌اند: {backend}", flush=True)
    if backend != "supabase":
        print("❗ هشدار: Supabase در دسترس نیست؛ از فایل محلی خوانده شد — "
              "در GitHub Actions حتماً Secretهای SUPABASE_URL و SUPABASE_KEY ست باشند.",
              flush=True)

    trades = store.load_all()
    open_trades = [t for t in trades if str(t.get("status")) == "open"]
    regime = next((a for a in AL.recent_alerts(200) if a.get("kind") == "regime"), None)

    agg = aggregate(trades, now)
    md = fmt_report(agg, open_trades, regime, now, backend)
    with open("daily_report.md", "w", encoding="utf-8") as f:
        f.write(md + "\n")
    print(md, flush=True)

    gh = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh:
        try:
            with open(gh, "a", encoding="utf-8") as f:
                f.write(md + "\n")
        except Exception:  # noqa: BLE001
            pass
    print(f"✅ گزارش ساخته شد: daily_report.md ({len(trades)} معامله خوانده شد)", flush=True)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
