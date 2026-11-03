# -*- coding: utf-8 -*-
"""core/autopsy.py — کالبدشکافی معامله (فاز ۱۳: آزمایشگاه ایجنت‌ها)
====================================================================
هر معامله‌ی بسته را می‌پرسد «چرا مردی؟» و برچسب‌های ضعف بهش می‌زند.
همه‌ی توابع خالص‌اند (بدون شبکه/فایل) — ورودی: رکوردهای معامله از
arena_store + هشدارهای رژیم از alerts. تست‌پذیر و بدون عوارض جانبی.

برچسب‌ها (code → فارسی):
  tight_stop       استاپ قبل از TP1 خورد — ورود/استاپ بد یا نویز بازار
  quick_stop       استاپ خیلی سریع (≤ QUICK_STOP_CANDLES کندل) — ورود دیرهنگام/بدون صبر
  timeout_negative تایم‌اوت با R منفی — معامله هرگز سود نشد (بدون پیگیری بازار)
  giveback         بعد از TP1 با تریل به ضرر رسید — سود پس داده شد
  deep_loss        ضرر عمیق (≤ DEEP_LOSS_R) — سقوط شارپ یا استاپ عریض
  against_regime   خلاف رژیم باز شد — مقابله با روند BTC
  regime_flip      رژیم وسط معامله برگشت — ضرر ناخواسته‌ی ماکرو

هدف: خوراک «آزمایشگاه ایجنت‌ها» (agent_lab) و صفحه‌ی تحقیقاتی اپ —
بعداً پالسی‌های تطبیقی از همین برچسب‌ها ساخته می‌شوند.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.arena import INTERVAL_MIN, to_ts

TAG_FA: Dict[str, str] = {
    "tight_stop": "استاپ قبل از TP1",
    "quick_stop": "استاپ خیلی سریع",
    "timeout_negative": "تایم‌اوت بدون سود",
    "giveback": "سود پس‌داده",
    "deep_loss": "ضرر عمیق",
    "against_regime": "خلاف رژیم",
    "regime_flip": "برگشت رژیم وسط راه",
}

QUICK_STOP_CANDLES = 3     # استاپ تا این تعداد کندل = ورود بی‌حوصله
DEEP_LOSS_R = -0.8         # آستانه‌ی ضرر عمیق (R خالص)


def _parse(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def regime_at(regime_alerts: List[Dict[str, Any]], ts: Optional[datetime]) -> int:
    """جهت رژیم حاکم در لحظه‌ی ts — از تاریخچه‌ی هشدارهای رژیم (تازه‌ترین قبل از ts).
    بدون دیتا → ۰ (نامشخص؛ هیچ برچسب رژیمی زده نمی‌شود)."""
    if ts is None:
        return 0
    best_ts, best_dir = None, 0
    for a in regime_alerts:
        if str(a.get("kind") or "") != "regime":
            continue
        t = _parse(a.get("created_at"))
        if t is None or t > ts:
            continue
        if best_ts is None or t > best_ts:
            best_ts, best_dir = t, int(a.get("direction") or 0)
    return best_dir


def candles_held(t: Dict[str, Any]) -> Optional[float]:
    """مدت نگهداری معامله بر حسب کندلِ تایم‌فریم خودش."""
    c0, c1 = _parse(t.get("created_at")), _parse(t.get("closed_at"))
    if not c0 or not c1:
        return None
    mins = INTERVAL_MIN.get(str(t.get("interval") or "1hour"), 60)
    return max(0.0, (c1 - c0).total_seconds() / 60.0 / max(1, mins))


def classify(t: Dict[str, Any], reg_open: int, reg_close: int) -> List[str]:
    """برچسب‌های ضعف یک معامله‌ی بسته — قواعد ثابت و شفاف."""
    codes: List[str] = []
    r = float(t.get("realized_r") or 0.0)
    ex = str(t.get("exit_reason") or "")
    d = int(t.get("direction") or 0)
    held = candles_held(t)

    if ex == "sl" and not t.get("tp1_done"):
        codes.append("tight_stop")
        if held is not None and held <= QUICK_STOP_CANDLES:
            codes.append("quick_stop")
    if ex == "timeout" and r < 0:
        codes.append("timeout_negative")
    if ex == "trail" and r < 0:
        codes.append("giveback")
    if r <= DEEP_LOSS_R:
        codes.append("deep_loss")
    if reg_open != 0 and d != 0 and d != reg_open:
        codes.append("against_regime")
    if reg_open != 0 and reg_close != 0 and reg_open != reg_close and d == reg_open:
        # هم‌جهت رژیم باز شد ولی رژیم برعکس شد — ضرر ماکرو، تقصیر ورود نیست
        if r < 0:
            codes.append("regime_flip")
    return codes


def autopsy_all(closed: List[Dict[str, Any]],
                regime_alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """کالبدشکافی همه‌ی معاملات بسته.
    خروجی: {id: {"codes": [...], "tags": [...], "regime_open": d, "regime_close": d},
            "_counts": {code: n}} — «_counts» روی همه‌ی معاملات جمع زده شده."""
    out: Dict[str, Any] = {"_counts": {}}
    for t in closed:
        tid = str(t.get("id") or "")
        ro = regime_at(regime_alerts, _parse(t.get("created_at")))
        rc = regime_at(regime_alerts, _parse(t.get("closed_at")))
        codes = classify(t, ro, rc)
        out[tid] = {"codes": codes,
                    "tags": [TAG_FA[c] for c in codes],
                    "regime_open": ro, "regime_close": rc}
        for c in codes:
            out["_counts"][c] = out["_counts"].get(c, 0) + 1
    return out


def tag_line(codes: List[str]) -> str:
    """یک خط کوتاه فارسی برای نمایش برچسب‌ها («—» اگر خالی)."""
    return " · ".join(TAG_FA[c] for c in codes) if codes else "—"
