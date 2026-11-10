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

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from core.arena_store import _secrets_get
from core import coins as C

API = "https://api.telegram.org"
MAX_TEXT = 3900          # سقف امن متن پیام (لیمیت تلگرام 4096 است)
_TIMEOUT = 12            # ثانیه
_MIN_GAP = 1.1           # حداقل فاصله بین دو ارسال (ضد 429)
_last_sent = 0.0

TEHRAN = timezone(timedelta(hours=3, minutes=30))   # UTC+03:30

# تمرکز اطلاع‌رسانی روی یک صرافی — هم‌راستا با BOT_EXCHANGE بات (پیش‌فرض لایتر).
# معاملات صرافی‌های دیگر (مثل پوزیشن‌های قدیمی KuCoin) بی‌صدا رد می‌شوند.
NOTIFY_EXCHANGE = os.environ.get("BOT_EXCHANGE", "Lighter").strip()


def _exchange_ok(t: dict) -> bool:
    """فیلتر تمرکز صرافی — فقط معاملات صرافی هدف پیام می‌شوند (خالی/«*» = همه)."""
    ex = str(NOTIFY_EXCHANGE or "").strip()
    if not ex or ex == "*":
        return True
    tex = str((t or {}).get("exchange") or "").strip().lower()
    if tex == ex.lower():
        return True
    print(f"🔇 فیلتر صرافی {ex}: پیام «{(t or {}).get('symbol')}» از "
          f"«{tex or 'نامعلوم'}» ارسال نشد", flush=True)
    return False


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
        if v != 0 and abs(v) < 0.001:                    # قیمت‌های میم‌کوین — بدون e-05
            s = f"{v:.12f}".rstrip("0").rstrip(".")
            return s or "0"
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


def _build_album_parts(items: list, caption: str) -> tuple:
    """ساختِ بارِ JSON و فایل‌های multipart برای sendMediaGroup — خالص و تست‌پذیر.
    خروجی: (media_json، فایل‌ها). حداکثر ۱۰ تصویر، caption فقط روی اولی."""
    media, files = [], {}
    for i, (name, data) in enumerate(list(items)[:10]):
        key = f"file{i}"
        m = {"type": "photo", "media": f"attach://{key}"}
        if i == 0 and caption:
            m["caption"] = str(caption)[:1024]
            m["parse_mode"] = "HTML"
        media.append(m)
        files[key] = (str(name)[:80], data, "image/png")
    return json.dumps(media, ensure_ascii=False), files


def send_album(images: list, caption: str = "") -> bool:
    """ارسال آلبومِ عکس (حداکثر ۱۰ تصویر) — best-effort، هیچ‌وقت exception نمی‌دهد.

    images: لیستی از (نام‌فایل، بایت‌های PNG). caption فقط روی تصویرِ اول می‌نشیند
    (سقفِ تلگرام ۱۰۲۴ نویسه). ضداسپم با همان فاصله‌ی حداقلِ send.
    """
    global _last_sent
    tok, chat = _cfg()
    if not (tok and chat) or not images:
        return False
    media, files = _build_album_parts(images, caption)
    try:
        import requests  # noqa: PLC0415
        gap = time.monotonic() - _last_sent
        if gap < _MIN_GAP:
            time.sleep(_MIN_GAP - gap)
        r = requests.post(
            f"{API}/bot{tok}/sendMediaGroup",
            data={"chat_id": str(chat), "media": json.dumps(media, ensure_ascii=False)},
            files=files,
            timeout=90,
        )
        _last_sent = time.monotonic()
        if r.status_code == 200:
            return True
        print(f"⚠️ تلگرام آلبوم را رد کرد ({r.status_code}): {r.text[:150]}", flush=True)
        return False
    except Exception as e:  # noqa: BLE001 — نوتیفیکیشن هرگز جریان را نمی‌شکند
        print(f"⚠️ ارسال آلبوم تلگرام ناموفق: {e}", flush=True)
        return False


# ------------------------------------------------------------- قالب‌های پیام
def _ctx_line(t: dict) -> str:
    """سطر بافتار معامله: صرافی + تایم‌فریم (هر کدام هست) — پیام تک‌معامله‌ای."""
    parts = []
    if t.get("exchange"):
        parts.append(f"🏦 {t['exchange']}")
    if t.get("interval"):
        parts.append(f"⏲ {t['interval']}")
    return " · ".join(parts)


def notify_open(t: dict) -> bool:
    """پیام بازشدن معامله — اگر ایجنتِ سوددهِ در مسیر برد باشد، نشان داغ می‌گیرد."""
    if not _exchange_ok(t):
        return True                     # بی‌صدا رد شد — نه خطا، فقط خارج از تمرکز
    d = int(t.get("direction") or 0)
    icon = "🟢" if d > 0 else "🔴"
    hot = _hot_stats(t.get("agent"))
    head = ("🔥 پوزیشن جدید باز شد — از بهترین ایجنت‌ها" if hot and hot["streak"] >= _HOT_STREAK
            else f"{icon} پوزیشن جدید باز شد")
    lines = [
        f"<b>{head}</b>",
        "",
        f"💎 ارز: <b>{C.coin_label(str(t.get('symbol') or ''))}</b> · {_dir_icon(d)}",
        f"🤖 ایجنت: {t.get('agent', '—')}",
    ]
    ctx = _ctx_line(t)
    if ctx:
        lines.append(ctx)
    lines.append(f"💵 ورود: <b>{_fmt_num(t.get('entry'))}</b> · 🛑 استاپ: {_fmt_num(t.get('stop'))}")
    hl = _hot_line(hot)
    if hl:
        lines.append(hl)
    if t.get("tp1"):
        tps = [f"🎯 TP1: {_fmt_num(t.get('tp1'))}"]
        if t.get("tp2"):
            tps.append(f"TP2: {_fmt_num(t.get('tp2'))}")
        if t.get("tp3"):
            tps.append(f"🏆 TP3: {_fmt_num(t.get('tp3'))}")
        lines.append(" · ".join(tps)
                     + (f" · R/R: {t.get('rr')}" if t.get("rr") else ""))
    ev = str(t.get("evidence") or "").strip()
    if ev:
        lines.append(f"📎 {ev[:180]}")
    lines.append(f"\n🕐 {_tehran_now()} تهران")
    return send("\n".join(lines))


_RESULT_FA = {
    "win": "✅ سود", "loss": "❌ ضرر", "be": "⚖️ سربه‌سر",
    "timeout_win": "⏱️ تایم‌اوت (سود)", "timeout_loss": "⏱️ تایم‌اوت (ضرر)",
    "timeout_be": "⏱️ تایم‌اوت (سربه‌سر)",
}

_HOT_STREAK = 2            # حداقل برد متوالی برای نشان «ایجنت داغ»
_HOT_WIN_R = 1.0           # حداقل R برای نشان «سیگنال سودده»


def _signed_streak(closed_sorted_list: list) -> int:
    """زنجیره‌ی علامت‌دار از انتها (+۳ = سه برد متوالی، −۲ = دو باخت متوالی)
    — همان منطق arena._streak ولی روی لیست مرتب بسته‌شده‌ها."""
    s = 0
    for t in reversed(closed_sorted_list):
        try:
            p = float(t.get("points") or 0.0)
        except (TypeError, ValueError):
            break
        if p == 0:
            break
        sign = 1 if p > 0 else -1
        if s == 0 or (s > 0) == (sign > 0):
            s += sign
        else:
            break
    return s


def _hot_stats(agent: Any) -> Optional[dict]:
    """کارنامه‌ی کوتاه ایجنت (برد/باخت/وین‌ریت/امتیاز/زنجیره) — best-effort.
    خرابی دیتا = None؛ هرگز جریان اطلاع‌رسانی را نمی‌شکند."""
    try:
        from core import agent_lab as LAB  # noqa: PLC0415
        from core import arena_store  # noqa: PLC0415
        name = str(agent or "").strip()
        if not name:
            return None
        mine = [t for t in arena_store.get_store().load_all()
                if str(t.get("agent")) == name and t.get("status") == "closed"]
        if not mine:
            return None
        closed = LAB.closed_sorted(mine)
        rs = [float(t.get("realized_r") or 0.0) for t in closed]
        wins = sum(1 for r in rs if r > 0)
        losses = sum(1 for r in rs if r < 0)
        pts = sum(float(t.get("points") or 0.0) for t in closed)
        return {"wins": wins, "losses": losses,
                "winrate": wins / max(1, wins + losses) * 100.0,
                "points": pts, "streak": _signed_streak(closed),
                "total_r": sum(rs)}
    except Exception:  # noqa: BLE001 — نوتیفیکیشن هرگز نمی‌شکند
        return None


def _hot_line(h: Optional[dict]) -> str:
    """یک خط کارنامه برای پیام — خالی یعنی دیتا نبود."""
    if not h:
        return ""
    txt = (f"🏅 کارنامه: {h['wins']} برد / {h['losses']} باخت"
           f" · وین‌ریت {h['winrate']:.0f}% · {h['points']:+.1f} امتیاز")
    if h["streak"] >= _HOT_STREAK:
        txt += f" · 🔥 {h['streak']} برد متوالی"
    return txt


def notify_close(t: dict) -> bool:
    """پیام بسته‌شدن معامله با نتیجه."""
    if not _exchange_ok(t):
        return True                     # بی‌صدا رد شد — نه خطا، فقط خارج از تمرکز
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
    big_win = r is not None and r >= _HOT_WIN_R
    head = ("🏆 سیگنال سودده — پوزیشن بسته شد" if big_win
            else f"{mood} پوزیشن بسته شد")
    lines = [
        f"<b>{head}</b>",
        "",
        f"💎 ارز: <b>{C.coin_label(str(t.get('symbol') or ''))}</b> · {_dir_icon(t.get('direction'))}",
        f"🤖 ایجنت: {t.get('agent', '—')}",
    ]
    ctx = _ctx_line(t)
    if ctx:
        lines.append(ctx)
    lines.append(f"📊 نتیجه: <b>{_RESULT_FA.get(res, res or '—')}</b>"
                 + (f" · <b>{r:+.2f}R</b>" if r is not None else ""))
    hl = _hot_line(_hot_stats(t.get("agent")))
    if hl:
        lines.append(hl)
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
