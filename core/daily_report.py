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
RECAL_TARGET = 50   # هدف ریکالیبراسیون آزمایشگاه: ~۵۰ معامله‌ی بسته‌ی لایتر

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


def _src_key(t: Dict[str, Any]) -> str:
    """منبع معامله — autopilot / manual / بدون برچسب (قدیمی)."""
    s = str(t.get("source") or "")
    return s if s in ("autopilot", "manual") else "legacy"


# ------------------------------------------------------------------ تجمیع
def aggregate(trades: List[Dict[str, Any]], now: datetime) -> Dict[str, Any]:
    """تجمیع گزارش از رکوردهای معامله — خالص و بدون I/O تا تست‌پذیر بماند.
    ردیف غیر dict (دیتای خراب) بی‌صدا دور ریخته می‌شود — هرگز raise نمی‌کند."""
    trades = [t for t in (trades or []) if isinstance(t, dict)]
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
    by_source: Dict[str, Dict[str, float]] = {}
    for t in closed_all:
        k = _src_key(t)
        slot = by_source.setdefault(k, {"n": 0, "r": 0.0})
        slot["n"] += 1
        slot["r"] += float(t.get("realized_r") or 0.0)
    for v in by_source.values():
        v["r"] = round(v["r"], 2)
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
        "by_source": by_source,
        "closed_lighter": sum(1 for t in closed_all
                              if str(t.get("exchange") or "").strip().lower() == "lighter"),
    }


# ------------------------------------------------------------------ قالب
def fmt_report(agg: Dict[str, Any], open_trades: List[Dict[str, Any]],
               regime: Optional[Dict[str, Any]], now: datetime,
               backend: str, lab: Optional[Dict[str, Any]] = None,
               dossier: Optional[Dict[str, Any]] = None) -> str:
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
    if lab:                                  # فاز ۱۳ — وضعیت آزمایشگاه
        c = lab.get("counts", {})
        L.append("### 🔬 آزمایشگاه ایجنت‌ها")
        L.append("")
        L.append(f"- پنالتی فعال: 🧊 سرد‌شده {c.get('penalized', 0)} · "
                 f"🧭 انضباط رژیم {c.get('regime_only', 0)} · ⛔ نماد ممنوع {c.get('bans', 0)}")
        penal = [f"{nm} (×{a['cool_mult']:g})" for nm, a in (lab.get("agents") or {}).items()
                 if float(a.get("cool_mult") or 1.0) > 1.0]
        if penal:
            L.append(f"- 🧊 سرد شدن: {' · '.join(penal)}")
        bans = lab.get("symbol_bans") or []
        if bans:
            L.append("- ⛔ ممنوع: " + " · ".join(
                f"{b.get('agent')}✕{b.get('symbol')}" for b in bans))
        rego = [nm for nm, a in (lab.get("agents") or {}).items() if a.get("regime_only")]
        if rego:
            L.append(f"- 🧭 فقط هم‌جهت رژیم: {' · '.join(rego)}")
        L.append("")
    if dossier:                              # فاز ۱۴ — پرونده‌ی بهبود
        dc = dossier.get("counts", {})
        if any(dc.get(k) for k in ("suspended", "quota_cut", "score_floor")):
            L.append("### 📋 پرونده‌ی بهبود ایجنت‌ها")
            L.append("")
            L.append(f"- نسخه‌ی فعال: 🚫 تعلیق {dc.get('suspended', 0)} · "
                     f"🎯 سهمیه‌کاه {dc.get('quota_cut', 0)} · 🎚️ کیفیت‌فیلتر {dc.get('score_floor', 0)}")
            susp = [nm for nm, a in (dossier.get("agents") or {}).items()
                    if (a.get("limits") or {}).get("suspended")]
            if susp:
                L.append(f"- 🚫 تعلیق‌شده: {' · '.join(susp)}")
            flo = [(nm, a["limits"]["score_floor"]) for nm, a in (dossier.get("agents") or {}).items()
                   if (a.get("limits") or {}).get("score_floor")]
            if flo:
                L.append("- 🎚️ فیلتر کیفیت: " + " · ".join(f"{nm} (|score|≥{f:g})" for nm, f in flo))
            L.append("")
    L.append("### 🏆 کل میدان (تمام تاریخ)")
    L.append("")
    twr = f"{agg['total_winrate']}%" if agg["total_winrate"] is not None else "—"
    L.append(f"- بسته‌شده: {agg['total_closed']} · وین‌ریت {twr} · جمع R: {agg['total_r']:+.2f}R")
    _cl = agg.get("closed_lighter")
    if _cl:
        _pct = min(100.0, 100.0 * _cl / RECAL_TARGET)
        L.append(f"- 🔬 مسیر ریکالیبراسیون آزمایشگاه: {_cl}/{RECAL_TARGET} معامله‌ی بسته‌ی لایتر ({_pct:.0f}٪) —"
                 + (" تقریباً آماده!" if _pct >= 80.0 else " جمع‌شدن داده ادامه دارد."))
    if agg.get("by_source"):
        labels = (("autopilot", "🤖 اتوپایلوت"), ("manual", "👤 دستی"), ("legacy", "قدیمی (بدون برچسب)"))
        parts = [f"{lab} {agg['by_source'][k]['n']} معامله ({agg['by_source'][k]['r']:+.2f}R)"
                 for k, lab in labels if k in agg["by_source"]]
        if parts:
            L.append(f"- تفکیک منبع: " + " · ".join(parts))
    L.append("")
    L.append("<sub>گزارش خودکار — هر روز ساعت ۰۹:۰۰ تهران · NorthmanQuant</sub>")
    return "\n".join(L)


# ------------------------------------------------------------------ قالب تلگرام
def fmt_telegram(agg: Dict[str, Any], open_trades: List[Dict[str, Any]],
                 regime: Optional[Dict[str, Any]], now: datetime,
                 lab: Optional[Dict[str, Any]] = None,
                 dossier: Optional[Dict[str, Any]] = None,
                 kronos: Optional[str] = None) -> str:
    """متن جمع‌وجور HTML برای تلگرام — بدون جدول (تلگرام جدول نمی‌فهمد)،
    بدون Markdown (تلگرام با MD ترکیبی مشکل دارد) — فقط HTML ساده.
    """
    L: List[str] = []
    L.append(f"📊 <b>گزارش روزانه‌ی میدان</b> — {now.astimezone(TEHRAN):%Y-%m-%d}")
    L.append("─" * 18)

    closed = agg["closed_24"]
    wr = f"{agg['winrate']}%" if agg["winrate"] is not None else "—"
    if closed:
        L.append(f"🏁 <b>بسته‌شده‌ی ۲۴ ساعت: {len(closed)}</b>")
        L.append(f"✅ {agg['wins']} برد · ❌ {agg['losses']} باخت · ⚪ {agg['bes']} (وین‌ریت {wr})")
        L.append(f"💰 جمع R: <b>{agg['sum_r']:+.2f}R</b> · امتیاز: {agg['sum_points']:+.1f}")
        if agg["best"] and agg["best"] is not agg["worst"]:
            b, w = agg["best"], agg["worst"]
            L.append(f"🏆 بهترین: {b.get('symbol')} ({float(b.get('realized_r') or 0):+.2f}R)"
                     f" · بدترین: {w.get('symbol')} ({float(w.get('realized_r') or 0):+.2f}R)")
    else:
        L.append(f"🏁 بسته‌شده‌ی ۲۴ ساعت: هیچ — میدان آرام بود 🌙")

    opened = agg["opened_24"]
    if opened:
        L.append("")
        L.append(f"🟢 بازشده‌ی ۲۴ ساعت: {len(opened)}")
        for t in opened[:5]:
            L.append(f"• {t.get('agent')} · {t.get('symbol')} · {_dir_fa(t.get('direction'))}"
                     f" · ورود {_fmt_price(t.get('entry'))}")
        if len(opened) > 5:
            L.append(f"… و {len(opened) - 5} مورد دیگر")

    L.append("")
    L.append(f"📌 پوزیشن باز فعلی: <b>{len(open_trades)}</b>")
    if regime:
        try:
            d = int(regime.get("direction") or 0)
        except (TypeError, ValueError):
            d = 0
        reg_fa = ("صعودی 🟢" if d > 0 else "نزولی 🔻" if d < 0 else "نامشخص ⚪")
        L.append(f"🌊 رژیم بازار: <b>{reg_fa}</b>"
                 f" (BTC {_fmt_price(regime.get('price'))} · MA {_fmt_price(regime.get('ma'))})")
    if lab:                                  # فاز ۱۳ — یک خط آزمایشگاه
        c = lab.get("counts", {})
        if c.get("penalized") or c.get("bans") or c.get("regime_only"):
            L.append(f"🔬 آزمایشگاه: 🧊 {c.get('penalized', 0)} سرد · "
                     f"🧭 {c.get('regime_only', 0)} انضباط رژیم · ⛔ {c.get('bans', 0)} نماد ممنوع")
    if dossier:                              # فاز ۱۴ — یک خط پرونده‌ی بهبود
        dc = dossier.get("counts", {})
        if any(dc.get(k) for k in ("suspended", "quota_cut", "score_floor")):
            L.append(f"📋 پرونده: 🚫 {dc.get('suspended', 0)} تعلیق · "
                     f"🎯 {dc.get('quota_cut', 0)} سهمیه‌کاه · 🎚️ {dc.get('score_floor', 0)} کیفیت‌فیلتر")
    if kronos:                               # فاز ۱۶ — یک خطِ سایه، بدونِ حقِ رأی
        L.append("")
        L.append(kronos)

    twr = f"{agg['total_winrate']}%" if agg["total_winrate"] is not None else "—"
    L.append("")
    L.append(f"🏆 کل میدان: {agg['total_closed']} بسته‌شده · وین‌ریت {twr} · {agg['total_r']:+.2f}R")
    _cl = agg.get("closed_lighter")
    if _cl:
        L.append(f"🔬 ریکالیبراسیون لاب: {_cl}/{RECAL_TARGET} معامله‌ی بسته‌ی لایتر")
    if agg.get("by_source"):
        labels = (("autopilot", "🤖"), ("manual", "👤"), ("legacy", "⭕"))
        parts = [f"{lab} {agg['by_source'][k]['n']} ({agg['by_source'][k]['r']:+.2f}R)"
                 for k, lab in labels if k in agg["by_source"]]
        if parts:
            L.append("" + " · ".join(parts))
    L.append(f"🕐 {now.astimezone(TEHRAN):%H:%M} تهران · NorthmanQuant")
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
    alerts_all = AL.recent_alerts(200)
    regime = next((a for a in alerts_all if a.get("kind") == "regime"), None)

    agg = aggregate(trades, now)
    # فاز ۱۳ — وضعیت آزمایشگاه (best-effort؛ خرابی فقط یعنی بدون این بخش)
    lab: Optional[Dict[str, Any]] = None
    try:
        from core import agent_lab as LAB
        lab = LAB.compute_adaptations(trades, now=now, regime_alerts=alerts_all)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ آزمایشگاه در گزارش نیامد (غیربحرانی): {e}", flush=True)
    # فاز ۱۴ — پرونده‌ی بهبود (best-effort)
    dossier: Optional[Dict[str, Any]] = None
    try:
        from core import dossier as DOS
        dossier = DOS.compute_dossier(trades, regime_alerts=alerts_all, now=now)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ پرونده‌ی بهبود در گزارش نیامد (غیربحرانی): {e}", flush=True)
    # فاز ۱۶ — خطِ سایه‌ی کرونوس (best-effort؛ هیچ‌وقت گزارش را نمی‌شکند)
    kronos_line: Optional[str] = None
    try:
        from core import kronos_promotion as KP
        kronos_line = KP.telegram_line()
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ خطِ سایه‌ی کرونوس در گزارش نیامد (غیربحرانی): {e}", flush=True)
    md = fmt_report(agg, open_trades, regime, now, backend, lab=lab, dossier=dossier)
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

    # فاز ۱۲ — خلاصه‌ی صبحگاهی تلگرام (best-effort؛ اگر Secretها ست نباشد رد می‌شود)
    try:
        from core import telegram as TG
        if TG.enabled():
            msg = fmt_telegram(agg, open_trades, regime, now, lab=lab, dossier=dossier,
                               kronos=kronos_line)
            print(f"🔔 تلگرام: {'ارسال شد ✅' if TG.send(msg) else 'ارسال نشد ⚠️'}", flush=True)
        else:
            print("ℹ️ تلگرام پیکربندی نشده — فقط فایل/Issue", flush=True)
    except Exception as e:  # noqa: BLE001 — گزارش باید حتی بدون تلگرام تمام شود
        print(f"⚠️ ارسال تلگرام ناموفق (غیربحرانی): {e}", flush=True)

    print(f"✅ گزارش ساخته شد: daily_report.md ({len(trades)} معامله خوانده شد)", flush=True)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
