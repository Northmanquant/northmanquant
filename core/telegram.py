# -*- coding: utf-8 -*-
"""core/telegram.py — نوتیفیکیشن ریل‌تایم تلگرام (فاز ۱۱)
=========================================================
رویدادهای میدان (بازشدن/بسته‌شدن معامله، تغییر رژیم، شکست اتوپایلوت) را
لحظه‌ای به چت تلگرام کاربر می‌فرستد.

پیکربندی (اختیاری — اگر ست نباشد همه‌چیز بی‌صدا رد می‌شود):
    TELEGRAM_BOT_TOKEN  توکن بات از @BotFather
    TELEGRAM_CHAT_ID    عدد چت کاربر (از getUpdates یا @userinfobot)

اصول طراحی:
  • best-effort — هیچ‌وقت exception بالا نمی‌دهد؛ خطا فقط لاگ می‌شود
    تا نوتیفیکیشن هرگز اتوپایلوت را نشکند.
  • ضداسپم — بین دو ارسال حداقل ~۱ ثانیه فاصله (لیمیت تلگرام) و
    تشخیص duplicate در سطح caller (فقط هشدار تازه → پیام تازه).
  • بدون وابستگی جدید — requests از قبل در requirements.txt هست.
  • زمان‌ها به وقت تهران نمایش داده می‌شوند.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from core.arena_store import _secrets_get

API = "https://api.telegram.org"
MAX_TEXT = 3900          # سقف امن متن پیام (لیمیت تلگرام 4096 است)
_TIMEOUT = 12            # ثانیه
_MIN_GAP = 1.1           # حداقل فاصله بین دو ارسال (ضد 429)
_last_sent = 0.0

TEHRAN = timezone(timedelta(hours=3, minutes=30))   # UTC+03:30


def _cfg() -> tuple[Optional[str], Optional[str]]:
    return _secrets_get("TELEGRAM_BOT_TOKEN"), _secrets_get("TELEGRAM_CHAT_ID")


def enabled() -> bool:
    tok, chat = _cfg()
    return bool(tok and chat)


def _tehran_now() -> str:
    return datetime.now(TEHRAN).strftime("%H:%M")


def _dir_icon(direction: int) -> str:
    return "🟢 لانگ" if int(direction or 0) > 0 else "🔴 شورت"


def _fmt_num(x: Any) -> str:
    try:
        v = float(x)
        if v == int(v) and abs(v) < 1e9:
            return f"{int(v):,}"
        return f"{v:,.6g}"
    except (TypeError, ValueError):
        return "—"


def send(text: str, silent: bool = False) -> bool:
    """ارسال پیام — همیشه True/False، هیچ‌وقت exception نمی‌دهد."""
    global _last_sent
    tok, chat = _cfg()
    if not (tok and chat and text):
        return False
    text = str(text).strip()[:MAX_TEXT]
    try:
        import requests  # noqa: PLC0415
        gap = time.monotonic() - _last_sent
        if gap < _MIN_GAP:
            time.sleep(_MIN_GAP - gap)
        r = requests.post(
            f"{API}/bot{tok}/sendMessage",
            json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                  "disable_notification": bool(silent)},
            timeout=_TIMEOUT,
        )
        _last_sent = time.monotonic()
        if r.status_code == 200:
            return True
        print(f"⚠️ تلگرام پاسخ {r.status_code} داد: {r.text[:120]}", flush=True)
        return False
    except Exception as e:  # noqa: BLE001 — نوتیفیکیشن هرگز جریان را نمی‌شکند
        print(f"⚠️ ارسال تلگرام ناموفق: {e}", flush=True)
        return False


# ------------------------------------------------------------- قالب‌های پیام
def notify_open(t: dict) -> bool:
    """پیام بازشدن معامله."""
    d = int(t.get("direction") or 0)
    icon = "🟢" if d > 0 else "🔴"
    lines = [
        f"<b>{icon} پوزیشن جدید باز شد</b>",
        "",
        f"💎 نماد: <b>{t.get('symbol', '—')}</b> · {_dir_icon(d)}",
        f"🤖 ایجنت: {t.get('agent', '—')}",
        f"💵 ورود: <b>{_fmt_num(t.get('entry'))}</b> · 🛑 استاپ: {_fmt_num(t.get('stop'))}",
    ]
    if t.get("tp1"):
        lines.append(f"🎯 TP1: {_fmt_num(t.get('tp1'))}"
                     + (f" · R/R: {t.get('rr')}" if t.get("rr") else ""))
    ev = str(t.get("evidence") or "").strip()
    if ev:
        lines.append(f"📎 {ev[:180]}")
    lines.append(f"\n🕐 {_tehran_now()} تهران · {t.get('exchange', '')}")
    return send("\n".join(lines))


_RESULT_FA = {
    "win": "✅ سود", "loss": "❌ ضرر", "be": "⚖️ سربه‌سر",
    "timeout_win": "⏱️ تایم‌اوت (سود)", "timeout_loss": "⏱️ تایم‌اوت (ضرر)",
    "timeout_be": "⏱️ تایم‌اوت (سربه‌سر)",
}


def notify_close(t: dict) -> bool:
    """پیام بسته‌شدن معامله با نتیجه."""
    r = None
    try:
        r = float(t.get("realized_r"))
    except (TypeError, ValueError):
        r = None
    res = str(t.get("result") or "")
    if r is not None and r > 0:
        mood = "🟩"
    elif r is not None and r < 0:
        mood = "🟥"
    else:
        mood = "⬜"
    lines = [
        f"<b>{mood} پوزیشن بسته شد</b>",
        "",
        f"💎 نماد: <b>{t.get('symbol', '—')}</b> · {_dir_icon(t.get('direction'))}",
        f"🤖 ایجنت: {t.get('agent', '—')}",
        f"📊 نتیجه: <b>{_RESULT_FA.get(res, res or '—')}</b>"
        + (f" · <b>{r:+.2f}R</b>" if r is not None else ""),
    ]
    if t.get("points") is not None:
        lines.append(f"🏆 امتیاز: {_fmt_num(t.get('points'))}")
    if t.get("entry"):
        lines.append(f"💵 ورود {_fmt_num(t.get('entry'))} → خروج {_fmt_num(t.get('closed_price'))}")
    if t.get("exit_reason"):
        lines.append(f"🚪 دلیل: {t.get('exit_reason')}")
    lines.append(f"\n🕐 {_tehran_now()} تهران")
    return send("\n".join(lines))


def notify_regime(a: dict) -> bool:
    """پیام تغییر رژیم بازار BTC."""
    d = int(a.get("direction") or 0)
    label = "صعودی 📈" if d > 0 else "نزولی 📉"
    lines = [
        f"<b>🌊 رژیم بازار عوض شد: {label}</b>",
        "",
        f"₿ BTC: <b>{_fmt_num(a.get('price'))}</b>",
        f"📐 MA(200) چهارساعته: {_fmt_num(a.get('ma'))}",
        "",
        "🧭 مسیر جست‌وجوی میدان بر همین اساس می‌چرخد.",
        f"🕐 {_tehran_now()} تهران",
    ]
    return send("\n".join(lines))


def notify_streak(agent: str, streak: int, cool_mult: float) -> bool:
    """پیام زنجیره‌ی باخت متوالی ایجنت — لحظه‌ای که آزمایشگاه سرد شدن می‌گذارد."""
    return send("\n".join([
        f"<b>⚠️ زنجیره‌ی ضرر ایجنت {agent}</b>",
        "",
        f"📉 {streak} باخت متوالی — آزمایشگاه وارد عمل شد:",
        f"🧊 سرد شدن ×{cool_mult:g} تا معامله‌ی بعدی (cooldown طولانی‌تر)",
        "",
        "🔬 هدف: شکستن چرخه‌ی باخت و حفظ سرمایه‌ی امتیازی ایجنت",
        f"🕐 {_tehran_now()} تهران",
    ]))


def notify_failure(where: str, err: str = "") -> bool:
    """پیام شکست اتوپایلوت/مرحله."""
    lines = [
        "<b>🔴 اتوپایلوت مشکل خورد!</b>",
        "",
        f"📍 مرحله: {where}",
    ]
    if err:
        lines.append(f"💥 {str(err)[:300]}")
    lines.append(f"\n🕐 {_tehran_now()} تهران · لاگ کامل: تب Actions گیت‌هاب")
    return send("\n".join(lines))


def notify_test() -> bool:
    """پیام تست اتصال."""
    return send(f"🔔 <b>NorthmanQuant متصل شد!</b>\n\n"
                f"از این لحظه رویدادهای میدان (بازشدن/بسته‌شدن، تغییر رژیم) همین‌جا می‌آیند.\n\n"
                f"✅ تست موفق · 🕐 {_tehran_now()} تهران")


def status_line() -> str:
    """خط کوتاه وضعیت برای لاگ."""
    tok, chat = _cfg()
    if tok and chat:
        return f"فعال (chat {str(chat)[:3]}***{str(chat)[-3:]})"
    return "غیرفعال — TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID ست نیست"
