"""core/autopilot.py — فاز ۶: اتوپایلوت میدان ایجنت‌ها (بدون‌سر)
==================================================================
همان زنجیره‌ای که صفحه‌ی «میدان ایجنت‌ها» در اپ اجرا می‌کند، این‌جا بدون
مرورگر و به‌صورت زمان‌بندی‌شده (GitHub Actions هر ۳۰ دقیقه) اجرا می‌شود:

  ۱) پیش‌بردن همه‌ی پوزیشن‌های باز با کندل‌های تازه (TP/SL/تایم‌اوت)
     + هشدار دائمی «بسته شد» برای هر معامله‌ای که همین الان بسته شد
  ۲) چک رژیم بازار (BTC/USDT روی ۴ساعته) + هشدار تغییر رژیم (ضدتکرار)
  ۳) اسکن دومرحله‌ای کل بازار + بازکردن معامله‌های تازه (سهمیه/cooldown)
     + هشدار دائمی «باز شد» برای هر معامله‌ی تازه

دستور اجرا (از ریشه‌ی ریپو):
    python -m core.autopilot

متغیرهای محیطی (همه اختیاری):
    ARENA_EXCHANGE   صرافی           (پیش‌فرض KuCoin)
    ARENA_INTERVAL   تایم‌فریم        (پیش‌فرض 1hour)
    ARENA_APPETITE   فیلتر ورود       (پیش‌فرض hunter)
    ARENA_EDGE_MODE  گیت لبه          (پیش‌فرض bench_losers)
    ARENA_SCAN       ۱=اسکن+بازکردن، ۰=فقط مدیریت پوزیشن‌ها (پیش‌فرض ۱)
    SUPABASE_URL / SUPABASE_KEY      ذخیره‌سازی پایدار (در Actions حتماً)

خروجی: لاگ مرحله‌به‌مرحله + بلاک «=== SUMMARY ===» با JSON خلاصه؛
اگر زیر GitHub Actions اجرا شود همان JSON به Step Summary هم می‌رود.

نکته‌ی مهم: بدون SUPABASE_URL/KEY اتوپایلوت روی فایل محلی کار می‌کند که
در Actions با هر اجرا پاک می‌شود — در Actions حتماً هر دو Secret ست شود.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone

# ------------------------------------------------------------------ پیکربندی
EXCHANGE = os.environ.get("ARENA_EXCHANGE", "KuCoin").strip()
INTERVAL = os.environ.get("ARENA_INTERVAL", "1hour").strip()
APPETITE = os.environ.get("ARENA_APPETITE", "hunter").strip()
EDGE_MODE = os.environ.get("ARENA_EDGE_MODE", "bench_losers").strip()
SCAN_ON = os.environ.get("ARENA_SCAN", "1").strip() not in ("0", "false", "False", "no")


def _validate() -> list[str]:
    """ورودی‌های محیطی را زودتر از همه اعتبارسنجی می‌کند تا اجرای بی‌فایده رخ ندهد."""
    errs: list[str] = []
    from core import arena as A  # noqa: PLC0415 — داخل تابع تا خطای ایمپورت خوانا بماند
    if EXCHANGE not in ("KuCoin", "OKX", "Binance", "Bybit", "Lighter", "XT", "LBank", "KCEX"):
        errs.append(f"ARENA_EXCHANGE نامعتبر: {EXCHANGE}")
    if INTERVAL not in A.INTERVAL_MIN:
        errs.append(f"ARENA_INTERVAL نامعتبر: {INTERVAL} (مجاز: {', '.join(A.INTERVAL_MIN)})")
    if APPETITE not in A.APPETITES:
        errs.append(f"ARENA_APPETITE نامعتبر: {APPETITE}")
    if EDGE_MODE not in ("off", "bench_losers", "winners_only"):
        errs.append(f"ARENA_EDGE_MODE نامعتبر: {EDGE_MODE}")
    return errs


def _log(msg: str) -> None:
    print(msg, flush=True)


# ------------------------------------------------------------------ مراحل
def phase_update(store) -> dict:
    """پیش‌بردن پوزیشن‌های باز + هشدار بسته‌شدن — خروجی: خلاصه‌ی مرحله."""
    from core import agent_lab as LAB
    from core import arena as A
    from core import alerts as AL
    from core import telegram as TG
    live, just_closed = A.update_all_trades(store)
    closed_rows = []
    for t in just_closed:
        try:
            fresh = AL.get_alerts().insert(AL.close_alert(t))
            if fresh:
                TG.notify_close(t)       # تلگرام — فقط برای هشدار تازه (ضدتکرار)
        except Exception as e:  # noqa: BLE001
            _log(f"⚠️ هشدار بسته‌شدن ثبت نشد ({t.get('symbol')}): {e}")
        closed_rows.append({
            "agent": t.get("agent"), "symbol": t.get("symbol"),
            "result": t.get("result"), "r": round(float(t.get("realized_r") or 0), 3),
            "points": round(float(t.get("points") or 0), 1),
            "reason": t.get("exit_reason"),
        })
        _log(f"🏁 بسته شد: {t.get('agent')} · {t.get('symbol')} → {t.get('result')} "
             f"({float(t.get('realized_r') or 0):+.2f}R)")
    # فاز ۱۳ — اگر ایجنتی به آستانه‌ی زنجیره‌ی باخت رسید، آزمایشگاه اعلام می‌شود
    if just_closed:
        try:
            all_closed = LAB.closed_sorted(store.load_all())
            for nm in sorted({str(t.get("agent")) for t in just_closed}):  
                mine = [t for t in all_closed if str(t.get("agent")) == nm]
                streak = LAB.current_streak(mine)
                mult = LAB.cool_mult_for(streak)
                if streak in (LAB.STREAK_L1, LAB.STREAK_L2, LAB.STREAK_L3):
                    _log(f"🔬 آزمایشگاه: {nm} به {streak} باخت متوالی رسید — سرد شدن ×{mult:g}")
                    TG.notify_streak(nm, streak, mult)
        except Exception as e:  # noqa: BLE001
            _log(f"⚠️ چک زنجیره‌ی آزمایشگاه ناموفق (غیربحرانی): {e}")
    return {"live_prices": len(live), "closed": closed_rows}


def phase_regime(reg: dict) -> dict:
    """هشدار تغییر رژیم از رژیمِ از پیش محاسبه‌شده (ضدتکرار — فقط جهش جهت ثبت می‌شود).
    فاز ۱۳: market_regime فقط یک بار در main صدا زده می‌شود (صرفه‌ی شبکه) — این‌جا فقط ثبت."""
    from core import alerts as AL
    from core import telegram as TG
    pushed = False
    try:
        pushed = bool(AL.push_regime_change(AL.get_alerts(), reg))
        if pushed:
            TG.notify_regime(AL.regime_alert(reg))   # تلگرام — فقط جهش واقعی
    except Exception as e:  # noqa: BLE001
        _log(f"⚠️ هشدار رژیم ثبت نشد: {e}")
    d = int(reg.get("dir") or 0)
    _log(f"🌊 رژیم بازار: {'صعودی' if d > 0 else 'نزولی' if d < 0 else 'نامشخص'}"
         + (" — هشدار ثبت شد ✅" if pushed else ""))
    return {"dir": d, "price": reg.get("price"), "ma": reg.get("ma"), "alert_pushed": pushed}


def phase_scan(store, regime_dir: int = 0) -> dict:
    """اسکن دومرحله‌ای + بازکردن معامله‌های تازه + هشدار بازشدن + پنالتی‌های آزمایشگاه."""
    from core import agent_lab as LAB
    from core import arena as A
    from core import alerts as AL
    from core import dossier as DOS
    from core import edge as EG
    from core import telegram as TG
    verdicts = None
    try:
        verdicts = (EG.load_edge(EG.EDGE_TTL_S) or {}).get("verdicts")  # گیت لبه فقط با حکم تازه مسلح می‌شود
    except Exception:  # noqa: BLE001
        verdicts = None
    # فاز ۱۳ — آزمایشگاه: تطبیق stateless از تاریخچه‌ی زنده + برچسب‌های کالبدشکافی
    lab: dict = {}
    try:
        regime_alerts = AL.recent_alerts(200)
    except Exception:  # noqa: BLE001
        regime_alerts = []
    try:
        lab = LAB.compute_adaptations(store.load_all(), regime_alerts=regime_alerts)
        c = lab.get("counts", {})
        _log(f"🔬 آزمایشگاه: سرد‌شده {c.get('penalized', 0)} · انضباط رژیم {c.get('regime_only', 0)} "
             f"· نماد ممنوع {c.get('bans', 0)}")
    except Exception as e:  # noqa: BLE001
        _log(f"⚠️ محاسبه‌ی آزمایشگاه ناموفق (بدون پنالتی ادامه می‌دهیم): {e}")
    # فاز ۱۴ — پرونده‌ی بهبود: تشخیص + نسخه‌ی پژوهشی هر ایجنت ضعیف (بعد از اعتبارسنجی ضدواقعی)
    dossier: dict = {}
    try:
        dossier = DOS.compute_dossier(store.load_all(), regime_alerts=regime_alerts)
        dc = dossier.get("counts", {})
        _log(f"📋 پرونده‌ی بهبود: تعلیق {dc.get('suspended', 0)} · سهمیه‌کاه {dc.get('quota_cut', 0)} "
             f"· کیفیت‌فیلتر {dc.get('score_floor', 0)}")
    except Exception as e:  # noqa: BLE001
        _log(f"⚠️ محاسبه‌ی پرونده ناموفق (بدون نسخه ادامه می‌دهیم): {e}")
    scans, errors, meta = A.run_scan(EXCHANGE, INTERVAL, appetite=APPETITE,
                                     verdicts=verdicts, edge_mode=EDGE_MODE)
    opened, blocked = A.open_trades_from_scan(scans, EXCHANGE, INTERVAL, store, source="autopilot",
                                              lab=lab or None, regime_dir=regime_dir,
                                              dossier=dossier or None)
    opened_rows = []
    for t in opened:
        try:
            fresh = AL.get_alerts().insert(AL.open_alert(t))
            if fresh:
                TG.notify_open(t)        # تلگرام — فقط برای هشدار تازه (ضدتکرار)
        except Exception as e:  # noqa: BLE001
            _log(f"⚠️ هشدار بازشدن ثبت نشد ({t.get('symbol')}): {e}")
        opened_rows.append({
            "agent": t.get("agent"), "symbol": t.get("symbol"),
            "direction": int(t.get("direction") or 0), "entry": t.get("entry"),
        })
        _log(f"🟢 باز شد: {t.get('agent')} · {t.get('symbol')} · ورود {t.get('entry')}")
    for e in errors[:5]:
        _log(f"⚠️ خطای اسکن: {e}")
    _log(f"🔎 اسکن: {meta.get('total')} ارز غربال شد → {meta.get('finalists')} برگزیده "
         f"(رژیم‌بلاک: {meta.get('regime_blocked', 0)} · لبه‌بلاک: {meta.get('edge_blocked', 0)} · "
         f"سهمیه/cooldown بلاک: {blocked})")
    return {"total": meta.get("total"), "finalists": meta.get("finalists"),
            "fallback": bool(meta.get("fallback")), "regime_blocked": meta.get("regime_blocked", 0),
            "edge_blocked": meta.get("edge_blocked", 0), "quota_blocked": blocked,
            "errors": len(errors), "opened": opened_rows}


# ------------------------------------------------------------------ main
def main() -> int:
    t0 = time.time()
    _log(f"🤖 اتوپایلوت میدان — {EXCHANGE} · {INTERVAL} · اشتها: {APPETITE} · گیت لبه: {EDGE_MODE}"
         + ("" if SCAN_ON else " · حالت فقط-مدیریت (بدون اسکن)"))

    errs = _validate()
    if errs:
        for e in errs:
            _log(f"❌ {e}")
        return 2

    from core import arena_store
    from core import telegram as TG
    _log(f"🔔 تلگرام: {TG.status_line()}")
    store = arena_store.get_store()
    STORE = store
    backend = getattr(store, "backend", None) or (
        "supabase" if getattr(store, "_client", None) is not None else "local-json")
    _log(f"💾 بک‌اند ذخیره‌سازی: {backend}")
    if backend != "supabase":
        _log("❗ هشدار: بدون Supabase، داده‌های میدان در فایل محلی ذخیره می‌شود که در "
             "GitHub Actions با هر اجرا پاک می‌شود — Secretهای SUPABASE_URL و SUPABASE_KEY را ست کن.")

    summary: dict = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "exchange": EXCHANGE, "interval": INTERVAL, "appetite": APPETITE,
        "edge_mode": EDGE_MODE, "scan": SCAN_ON, "backend": str(backend),
    }
    ok = True
    try:
        summary["update"] = phase_update(store)
    except Exception as e:  # noqa: BLE001
        ok = False
        summary["update_error"] = str(e)[:300]
        _log(f"❌ مرحله‌ی پیش‌بردن معاملات شکست خورد: {e}\n{traceback.format_exc(limit=2)}")
        TG.notify_failure("پیش‌بردن معاملات", str(e))
    # فاز ۱۳ — رژیم فقط یک بار محاسبه می‌شود و به رژیم/اسکن هر دو می‌رسد (صرفه‌ی شبکه)
    reg: dict = {}
    try:
        from core import arena as A
        reg = A.market_regime(EXCHANGE)
    except Exception as e:  # noqa: BLE001
        reg = {}
        _log(f"⚠️ گرفتن رژیم بازار ناموفق (ادامه می‌دهیم): {e}")
    try:
        summary["regime"] = phase_regime(reg or {"dir": 0})
    except Exception as e:  # noqa: BLE001
        summary["regime_error"] = str(e)[:300]
        _log(f"⚠️ مرحله‌ی رژیم بازار شکست خورد (ادامه می‌دهیم): {e}")
        TG.notify_failure("رژیم بازار", str(e))
    if SCAN_ON:
        try:
            summary["scan"] = phase_scan(store, regime_dir=int((reg or {}).get("dir") or 0))
        except Exception as e:  # noqa: BLE001
            summary["scan_error"] = str(e)[:300]
            _log(f"⚠️ مرحله‌ی اسکن شکست خورد: {e}")
            TG.notify_failure("اسکن بازار", str(e))
    try:
        n_open = sum(1 for t in store.load_all() if t.get("status") == "open")
        summary["open_after"] = n_open
        _log(f"📊 پوزیشن باز فعلی میدان: {n_open}")
    except Exception:  # noqa: BLE001
        pass

    summary["took_s"] = round(time.time() - t0, 1)
    summary["ok"] = ok
    _log("=== SUMMARY ===")
    _log(json.dumps(summary, ensure_ascii=False, indent=2))
    gh = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh:
        try:
            with open(gh, "a", encoding="utf-8") as f:
                f.write("## 🏟️ Arena Autopilot\n\n```json\n"
                        + json.dumps(summary, ensure_ascii=False, indent=2) + "\n```\n")
        except Exception:  # noqa: BLE001
            pass
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
