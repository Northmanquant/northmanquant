# -*- coding: utf-8 -*-
"""core/tg_bot.py — بات تلگرام میدان: بهترین ایجنت‌ها + سیگنال‌های سودده
==========================================================================
بخش تازه‌ی بات تلگرام (دستور پاسخ‌گو) + خلاصه‌ی روزانه‌ی خودکار.

دستورها (فارسی و انگلیسی — با یا بدون «/»):
  start · شروع · سلام      خوش‌آمد + فهرست دستورها
  top · بهترین             🏆 بهترین ایجنت‌های سودده و در مسیر ادامه
                           (امتیاز، R خالص، وین‌ریت، ایکوییتی، زنجیره‌ی برد، فرم ۱۰تایی)
  signals · سیگنال         💸 سیگنال‌های سودده: بردهای ۷ روز اخیر +
                           پوزیشن‌های بازِ همین الان در سود (با قیمت زنده)
  stats · آمار             📊 آمار کل میدان (انتظاری، PF، وین‌ریت، MaxDD، رژیم)
  help · راهنما            فهرست دستورها

معماری بدون‌سرور (هم‌راستا با اتوپایلوت):
  GitHub Actions هر ۵ دقیقه «python -m core.tg_bot» را اجرا می‌کند؛ بات اول
  «کل صف تأییدنشده» را یک‌جا می‌خواند و به همه‌ی دستورهای تازه جواب می‌دهد،
  بعد تا ~۴ دقیقه با long-poll گوش می‌دهد — یعنی پیامی که وسط بازه برسد هم
  تقریباً لحظه‌ای جواب می‌گیرد و هیچ دستوری قربانی «فقط آخرین پیام» نمی‌شود.
  کمربند احتیاطی: اتوپایلوت (هر ۳۰ دقیقه) آخر کار یک «python -m core.tg_bot
  --once» هم اجرا می‌کند تا حتی اگر کرون ۵ دقیقه‌ای گیت‌هاب عقب افتاد، هر
  دستور حداکثر ~۳۰ دقیقه‌ای جواب بگیرد. پیام‌های کهنه‌تر از ۳۰ دقیقه بی‌جواب
  تأیید می‌شوند تا بات هرگز به صف قدیمی اسپم نزند. تلگرام خودش خوانده‌شده‌ها
  را با offset به‌خاطر می‌سپارد — نیازی به حافظه‌ی محلی نیست.

خلاصه‌ی روزانه (push): یک‌بار در هر شبانه‌روز تهران، خلاصه‌ی میدان به چت
مالک (TELEGRAM_CHAT_ID) می‌رود. ضدتکرار با نشانگر قطعی در جدول arena_alerts
(kind="bot"، id="bot:digest:YYYY-MM-DD") — نشانگر قبل از ارسال درج می‌شود تا
اگر Supabase/تلگرام خطا داد، هیچ‌وقت دوباره‌کاری اسپم نشود.

امنیت: پیش‌فرض فقط چت مالک جواب می‌گیرد. برای اضافه‌کردن چت‌های دیگر
TELEGRAM_ALLOWED_CHATS را با کاما ست کنید (خالی یا «*» = عمومی).

اصل طراحی: مثل core/telegram.py همه‌چیز best-effort است — بات هرگز با
exception نمی‌میرد؛ خرابی فقط لاگ می‌شود و اجرای Actions سالم تمام می‌شود.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from core.arena_store import _secrets_get, _utcnow_iso

API = "https://api.telegram.org"
MAX_TEXT = 3900
_TIMEOUT = 15
_MESSAGE_MAX_AGE_S = 30 * 60          # پیام کهنه‌تر از این جواب نمی‌گیرد (= فاصله‌ی کمربند اتوپایلوت)
_LONGPOLL_S = 25                      # طول هر long-poll تلگرام (ثانیه)
_POLL_BUDGET_S = 240                  # بودجه‌ی گوش‌دادن هر اجرا (~۴ دقیقه؛ سقف وورک‌فلو ۶ دقیقه)
REPLY_CAP = 20                        # سقف پاسخ در هر اجرا — ضداسپم
_MIN_GAP = 0.7                        # حداقل فاصله بین دو ارسال (ضد 429)

# ---------------------------------------------------------------- آستانه‌ها
HOT_STREAK = 2                        # زنجیره‌ی برد برای نشان 🔥
MIN_WIN_R = 0.5                       # حداقل R برای «سیگنال سودده»ی بسته‌شده
SIGNAL_WINDOW_D = 7                   # پنجره‌ی بردهای اخیر (روز)
TOP_N = 5                             # سطرهای فهرست بهترین‌ها
OPEN_CHECK_CAP = 12                   # سقف چک قیمت زنده برای پوزیشن‌های باز

TEHRAN = timezone(timedelta(hours=3, minutes=30))   # UTC+03:30 — مثل core/telegram

_MEDALS = ("🥇", "🥈", "🥉")

_WELCOME = (
    "👋 <b>به بات NorthmanQuant خوش آمدی!</b>\n\n"
    "اینجا آشیانه‌ی ایجنت‌های معامله‌گر است — هر ۳۰ دقیقه میدان خودش را "
    "می‌گردد، معامله می‌زند و کارنامه می‌سازد.\n\n"
    "دستورها:\n"
    "🏆 /top — بهترین ایجنت‌های سودده\n"
    "💸 /signals — سیگنال‌های سودده\n"
    "📊 /stats — آمار کل میدان\n"
    "ℹ️ /help — راهنما\n\n"
    "⚠️ آموزش، نه توصیه‌ی مالی — ایجنت‌ها با پول کاغذی رقابت می‌کنند."
)

_HELP = (
    "ℹ️ <b>راهنمای بات</b>\n\n"
    "🏆 /top (یا «بهترین») — جدول بهترین ایجنت‌ها: امتیاز، R خالص، "
    "وین‌ریت، ایکوییتی، زنجیره‌ی برد و فرم ۱۰ معامله‌ی اخیر\n\n"
    "💸 /signals (یا «سیگنال») — بردهای ۷ روز اخیر + پوزیشن‌های بازِ در سود\n\n"
    "📊 /stats (یا «آمار») — انتظاری، سود فاکتور، وین‌ریت، بیشترین افت، رژیم بازار\n\n"
    "🕐 پاسخ‌ها معمولاً چندثانیه تا چند دقیقه می‌رسند (long-poll هر ۵ دقیقه).\n"
    "🔴 پیام‌های لحظه‌ای باز/بسته‌شدن هم مستقیم به چت مالک می‌آید."
)


# ------------------------------------------------------------- کمکی‌های محلی
def _log(msg: str) -> None:
    print(msg, flush=True)


def _fmt_num(x: Any) -> str:
    try:
        v = float(x)
        if v == int(v) and abs(v) < 1e9:
            return f"{int(v):,}"
        return f"{v:,.6g}"
    except (TypeError, ValueError):
        return "—"


def _tehran_now() -> str:
    return datetime.now(TEHRAN).strftime("%H:%M")


def _parse_dt(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _dir_icon(direction: Any) -> str:
    return "🟢 لانگ" if int(direction or 0) > 0 else "🔴 شورت"


# ------------------------------------------------------------- لایه‌ی API
def _call(token: str, method: str, payload: Optional[dict] = None,
          timeout: float = _TIMEOUT) -> Optional[dict]:
    """فراخوانی Bot API — همیشه dict یا None؛ هیچ‌وقت exception نمی‌دهد.
    429 (لیمیت) با انتظار retry_after یک بار تلاش مجدد می‌شود."""
    try:
        import requests  # noqa: PLC0415
        for attempt in (0, 1):
            r = requests.post(f"{API}/bot{token}/{method}", json=payload or {},
                              timeout=timeout)
            if r.status_code == 429 and attempt == 0:
                try:
                    wait = float((r.json().get("parameters") or {}).get("retry_after") or 3.0)
                except Exception:  # noqa: BLE001
                    wait = 3.0
                time.sleep(min(wait, 15.0))
                continue
            break
        if r.status_code == 409:
            _log("⚠️ بات: چرخه‌ی دیگری هم‌زمان در حال خواندن است — رد شد")
            return None
        if r.status_code != 200:
            _log(f"⚠️ بات: {method} پاسخ {r.status_code} داد: {r.text[:150]}")
            return None
        j = r.json()
        return j if isinstance(j, dict) else None
    except Exception as e:  # noqa: BLE001 — بات هرگز نمی‌میرد
        _log(f"⚠️ بات: {method} ناموفق: {e}")
        return None


_last_send = 0.0


def _send_chat(token: str, chat_id: Any, text: str, silent: bool = False) -> bool:
    """ارسال پیام به یک چت دلخواه — best-effort، با حداقل فاصله بین ارسال‌ها."""
    global _last_send
    if not (token and chat_id and text):
        return False
    gap = time.monotonic() - _last_send
    if gap < _MIN_GAP:
        time.sleep(_MIN_GAP - gap)
    j = _call(token, "sendMessage", {
        "chat_id": chat_id, "text": str(text).strip()[:MAX_TEXT],
        "parse_mode": "HTML", "disable_notification": bool(silent),
    })
    _last_send = time.monotonic()
    return bool(j and j.get("ok"))


def allowed_chats() -> set[str]:
    """چت‌های مجاز — پیش‌فرض فقط مالک؛ «*» یعنی عمومی."""
    raw = _secrets_get("TELEGRAM_ALLOWED_CHATS") or _secrets_get("TELEGRAM_CHAT_ID") or ""
    parts = [p.strip() for p in str(raw).replace("،", ",").split(",")]
    return {p for p in parts if p}


def live_price(exchange: str, symbol: str) -> Optional[float]:
    """آخرین قیمت یک نماد — تیکر سبک (نه کندل). اول کوکوین، بعد فال‌بک‌ها.
    خروجی None = نگرفت (بدون دردسر)."""
    sym = str(symbol or "").upper().replace("/", "-")
    base = sym.split("-")[0]
    if not sym or not base:
        return None
    ku = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={sym}"
    bn = f"https://api.binance.com/api/v3/ticker/price?symbol={base}USDT"
    okx = f"https://api.okx.com/api/v5/market/ticker?instId={base}-USDT"
    ex = str(exchange or "").lower()
    if "binance" in ex:
        order = [bn, ku, okx]
    elif "okx" in ex:
        order = [okx, ku, bn]
    else:                                   # KuCoin (پیش‌فرض میدان) و بقیه
        order = [ku, bn, okx]
    from core.net import get_json  # noqa: PLC0415
    for url in order:
        try:
            j = get_json(url, timeout=8, retries=0)
            if not isinstance(j, dict):
                continue
            d = j.get("data")
            px = None
            if isinstance(d, dict) and d.get("price"):
                px = d["price"]                              # KuCoin
            elif isinstance(d, list) and d and isinstance(d[0], dict):
                px = d[0].get("last")                        # OKX
            elif j.get("price"):
                px = j["price"]                              # Binance
            if px:
                return float(px)
        except Exception:  # noqa: BLE001 — منبع بعدی
            continue
    return None


# ------------------------------------------------------------- دیتاسازها
def top_rows(closed: list[dict], opens: list[dict]) -> list[dict]:
    """بهترین ایجنت‌ها — فقط سودده‌ها (امتیاز یا ایکوییتی مثبت)، مرتب و بریده."""
    from core import arena as A  # noqa: PLC0415 — ایمپورت تنبل
    rows = [r for r in A.leaderboard(closed, opens) if r.get("trades", 0) > 0]
    for r in rows:
        hist = r.get("_history") or []
        r["form10_r"] = sum(float(t.get("realized_r") or 0.0) for t in hist[-10:])
    best = [r for r in rows
            if float(r.get("points") or 0) > 0 or float(r.get("equity") or 0) > A.START_EQUITY]
    best.sort(key=lambda r: (-float(r.get("points") or 0), -float(r.get("total_r") or 0)))
    return best[:TOP_N]


def winning_closes(closed: list[dict], now: Optional[datetime] = None) -> list[dict]:
    """بردهای اخیر — R ≥ آستانه در پنجره‌ی ۷ روز، قوی‌ترین اول."""
    now = now or datetime.now(timezone.utc)
    w0 = now - timedelta(days=SIGNAL_WINDOW_D)
    out = []
    for t in closed:
        try:
            r = float(t.get("realized_r") or 0.0)
        except (TypeError, ValueError):
            continue
        if r < MIN_WIN_R:
            continue
        c = _parse_dt(t.get("closed_at"))
        if c and c >= w0:
            out.append(t)
    out.sort(key=lambda t: -float(t.get("realized_r") or 0.0))
    return out[:TOP_N]


def open_in_profit(opens: list[dict],
                   price_fn: Callable[[str, str], Optional[float]] = live_price) -> list[dict]:
    """پوزیشن‌های بازِ همین الان در سود — با قیمت زنده؛ ناموفق‌ها رد می‌شوند."""
    out = []
    for t in opens[:OPEN_CHECK_CAP]:
        entry = float(t.get("entry") or 0.0)
        d = int(t.get("direction") or 0)
        if entry <= 0 or d == 0:
            continue
        p = price_fn(str(t.get("exchange") or ""), str(t.get("symbol") or ""))
        if not p:
            continue
        sign = 1.0 if d > 0 else -1.0
        pnl = (p - entry) / entry * 100.0 * sign
        if pnl > 0:
            out.append({**t, "now": p, "pnl_pct": pnl})
    out.sort(key=lambda t: -float(t.get("pnl_pct") or 0.0))
    return out[:TOP_N]


# ------------------------------------------------------------- فرمت‌کننده‌ها
def _streak_txt(streak: int) -> str:
    if streak >= HOT_STREAK:
        return f"🔥 {streak} برد متوالی"
    if streak > 0:
        return f"{streak} برد متوالی"
    if streak < 0:
        return f"❄️ {-streak} باخت متوالی"
    return "بدون زنجیره"


def fmt_top(best: list[dict], total_rows: list[dict]) -> str:
    if not best:
        return ("🏆 <b>بهترین ایجنت‌های میدان</b>\n\n"
                "هنوز هیچ ایجنتی به سود خالص نرسیده — میدان تازه شروع شده. "
                "بعد از اولین بردها این‌جا پر می‌شود.")
    lines = ["<b>🏆 بهترین ایجنت‌های میدان</b>",
             "<i>سودده و در مسیر ادامه</i>", ""]
    for i, r in enumerate(best):
        medal = _MEDALS[i] if i < len(_MEDALS) else f"{i + 1}."
        lines.append(f"{medal} <b>{r.get('agent', '—')}</b>")
        lines.append(f"   💰 <b>{float(r.get('points') or 0):+.1f} امتیاز</b>"
                     f" · 📈 {float(r.get('total_r') or 0):+.1f}R"
                     f" · 🎯 {float(r.get('winrate') or 0):.0f}% برد")
        lines.append(f"   💵 ایکوییتی ${float(r.get('equity') or 0):,.0f}"
                     f" · {int(r.get('wins') or 0)} برد / {int(r.get('losses') or 0)} باخت"
                     f" · {_streak_txt(int(r.get('streak') or 0))}")
        lines.append(f"   📊 فرم ۱۰تایی {float(r.get('form10_r') or 0):+.1f}R"
                     f" · بیشترین افت {float(r.get('maxdd') or 0):.1f}%")
        if r.get("open"):
            lines.append(f"   🔓 {int(r.get('open'))} پوزیشن باز")
    lines += ["", f"⚙️ رتبه‌بندی: امتیاز + R خالص · {len(total_rows)} شرکت‌کننده فعال",
              f"🕐 {_tehran_now()} تهران · دستور بعدی: /signals"]
    return "\n".join(lines)


def fmt_signals(wins: list[dict], open_profits: list[dict]) -> str:
    lines = ["<b>💸 سیگنال‌های سودده</b>", ""]
    if wins:
        lines.append(f"<b>✅ بردهای {SIGNAL_WINDOW_D} روز اخیر</b> (≥ {MIN_WIN_R:g}R)")
        for t in wins:
            lines.append(f"{_dir_icon(t.get('direction')).split()[0]} <b>{t.get('symbol', '—')}</b>"
                         f" · {t.get('agent', '—')}")
            lines.append(f"   {_fmt_num(t.get('entry'))} → {_fmt_num(t.get('closed_price'))}"
                         f" · <b>{float(t.get('realized_r') or 0):+.2f}R</b>"
                         + (f" · {float(t.get('points') or 0):+.1f} امتیاز"
                            if t.get("points") is not None else ""))
    else:
        lines.append(f"در {SIGNAL_WINDOW_D} روز اخیر برده‌ای با ≥ {MIN_WIN_R:g}R ثبت نشده.")
    if open_profits:
        lines += ["", "<b>📈 پوزیشن‌های بازِ در سود</b>"]
        for t in open_profits:
            lines.append(f"{_dir_icon(t.get('direction')).split()[0]} <b>{t.get('symbol', '—')}</b>"
                         f" · {t.get('agent', '—')}")
            lines.append(f"   ورود {_fmt_num(t.get('entry'))} → الان {_fmt_num(t.get('now'))}"
                         f" · <b>{float(t.get('pnl_pct') or 0):+.1f}%</b> شناور")
    lines += ["", "⚠️ آموزش، نه توصیه‌ی مالی",
              f"🕐 {_tehran_now()} تهران"]
    return "\n".join(lines)


_REL_FA = {"low": "کم — نمونه کوچک، عدد قضاوت‌کننده نیست",
           "mid": "متوسط — فقط جهت‌گیری", "ok": "قابل‌اتکا"}


def fmt_stats(closed: list[dict], opens: list[dict],
              regime_alert: Optional[dict] = None) -> str:
    from core import arena as A  # noqa: PLC0415
    s = A.arena_summary(closed)
    lines = ["<b>📊 آمار کل میدان</b>", "",
             f"🎯 معاملات بسته‌شده: <b>{s['n']}</b> ({s['wins']} برد / {s['losses']} باخت)",
             f"📈 وین‌ریت: <b>{s['winrate']:.0f}%</b> · انتظاری: <b>{s['expectancy']:+.2f}R</b>",
             f"⚖️ سود فاکتور: {s['pf']:.2f} · پی‌آف: {s['payoff']:.2f}",
             f"💰 مجموع R خالص: <b>{s['total_r']:+.1f}R</b> · بیشترین افت: {s['maxdd']:.1f}%",
             f"🔓 پوزیشن باز: {len(opens)}",
             f"🧭 اعتبار آماری: {_REL_FA.get(s['reliability'], s['reliability'])}"]
    if regime_alert:
        d = int(regime_alert.get("direction") or 0)
        label = "صعودی 📈" if d > 0 else "نزولی 📉"
        when = str(regime_alert.get("created_at") or "")[:16].replace("T", " ")
        lines += ["", f"🌊 آخرین رژیم ثبت‌شده: <b>{label}</b> ({when} UTC)"]
    lines += ["", f"🕐 {_tehran_now()} تهران"]
    return "\n".join(lines)


def fmt_digest(day: str, best: list[dict], wins_24h: list[dict],
               n_open: int) -> str:
    lines = [f"<b>🌅 خلاصه‌ی روزانه‌ی میدان — {day}</b>", ""]
    if best:
        lines.append("<b>🥇 بهترین‌های امروز:</b>")
        for i, r in enumerate(best[:3]):
            medal = _MEDALS[i] if i < len(_MEDALS) else f"{i + 1}."
            lines.append(f"{medal} <b>{r.get('agent', '—')}</b> — "
                         f"{float(r.get('points') or 0):+.1f} امتیاز · "
                         f"{float(r.get('winrate') or 0):.0f}% برد · "
                         f"{_streak_txt(int(r.get('streak') or 0))}")
    else:
        lines.append("هنوز ایجنتی به سود خالص نرسیده.")
    if wins_24h:
        tot_r = sum(float(t.get("realized_r") or 0.0) for t in wins_24h)
        lines += ["", f"✅ بردهای ۲۴ ساعت اخیر: <b>{len(wins_24h)}</b> "
                      f"(مجموع <b>{tot_r:+.2f}R</b>)"]
    else:
        lines += ["", "بردهی در ۲۴ ساعت اخیر ثبت نشده."]
    lines += [f"🔓 پوزیشن باز: {n_open}", "",
              "جزئیات: /top · /signals · /stats"]
    return "\n".join(lines)


# ------------------------------------------------------------- جواب‌ساز
def route(text: str) -> Optional[str]:
    """متن پیام → کلید جواب. None = پیام عادی، جواب نمی‌خواهد."""
    t = str(text or "").strip().lower().lstrip("/").split("@")[0].strip()
    t = " ".join(t.split())                     # فاصله‌های تکراری
    if t in ("start", "شروع", "سلام", "hi", "hello"):
        return "welcome"
    if t in ("top", "best", "بهترین", "بهترین ها", "بهترینها", "لیدربورد", "رتبه بندی", "رتبهبندی"):
        return "top"
    if t in ("signals", "signal", "سیگنال", "سیگنال ها", "سیگنالها"):
        return "signals"
    if t in ("stats", "stat", "آمار", "امار"):
        return "stats"
    if t in ("help", "راهنما", "کمک"):
        return "help"
    return "unknown" if str(text or "").strip().startswith("/") else None


def build_reply(key: str) -> str:
    """ساخت متن جواب از داده‌ی زنده‌ی میدان."""
    from core import arena as A        # noqa: PLC0415
    from core import alerts as AL      # noqa: PLC0415
    from core import arena_store       # noqa: PLC0415
    store = arena_store.get_store()
    trades = store.load_all()
    closed = [t for t in trades if t.get("status") == "closed"]
    opens = [t for t in trades if t.get("status") == "open"]
    if key == "welcome":
        return _WELCOME
    if key == "help":
        return _HELP
    if key == "top":
        rows = [r for r in A.leaderboard(closed, opens) if r.get("trades", 0) > 0]
        return fmt_top(top_rows(closed, opens), rows)
    if key == "signals":
        return fmt_signals(winning_closes(closed), open_in_profit(opens))
    if key == "stats":
        try:
            reg = next((a for a in AL.recent_alerts(50) if a.get("kind") == "regime"), None)
        except Exception:  # noqa: BLE001
            reg = None
        return fmt_stats(closed, opens, reg)
    return _HELP


# ------------------------------------------------------------- چرخه‌ی بات
def _fresh(msg: dict, now: Optional[datetime] = None) -> bool:
    """پیام تازه است؟ (کهنه‌تر از _MESSAGE_MAX_AGE_S جواب نمی‌گیرد)"""
    now = now or datetime.now(timezone.utc)
    try:
        ts = int(msg.get("date") or 0)
    except (TypeError, ValueError):
        return False
    if ts <= 0:
        return False
    return (now - datetime.fromtimestamp(ts, tz=timezone.utc)).total_seconds() <= _MESSAGE_MAX_AGE_S


def handle_update(u: dict, token: str, allowed: set[str]) -> int:
    """یک آپدیت تلگرام → جواب (یا رد). خروجی: تعداد پاسخ ارسال‌شده."""
    msg = u.get("message") or u.get("edited_message") or {}
    chat = (msg.get("chat") or {}).get("id")
    text = str(msg.get("text") or "").strip()
    if chat is None or not text:
        return 0
    if not _fresh(msg):
        return 0
    cs = str(chat)
    if allowed and "*" not in allowed and cs not in allowed:
        _send_chat(token, chat, "⛔️ این بات فقط برای مالکش جواب می‌دهد.\n"
                                "برای دسترسی، چت‌تان را به TELEGRAM_ALLOWED_CHATS اضافه کنید.")
        return 0
    key = route(text)
    if key is None:
        return 0
    try:
        reply = build_reply(key)
    except Exception as e:  # noqa: BLE001 — جواب خطا، نه مرگ
        _log(f"⚠️ بات: ساخت جواب ناموفق: {e}")
        reply = "😔 الان نمی‌توانم داده‌ی میدان را بخوانم — چند دقیقه بعد دوباره امتحان کن."
    if key == "unknown":
        reply = "🤔 دستور ناشناخته — این‌ها را امتحان کن:\n\n" + _HELP
    return 1 if _send_chat(token, chat, reply) else 0


def poll_once(budget: Optional[float] = None) -> int:
    """یک چرخه‌ی کامل: تخلیه‌ی کامل صف + long-poll تا پایان بودجه (~۴ دقیقه).
    خروجی: تعداد پاسخ. budget=0 → فقط یک تخلیه‌ی سریع (کمربند اتوپایلوت)."""
    token = _secrets_get("TELEGRAM_BOT_TOKEN")
    if not token:
        _log("🤖 بات تلگرام: TELEGRAM_BOT_TOKEN ست نیست — رد شد")
        return 0
    allowed = allowed_chats()
    t_end = time.monotonic() + (_POLL_BUDGET_S if budget is None else budget)
    total = 0
    offset = 0                        # ۰ = کل صف تأییدنشده، حتی صف چندساعته
    first = True
    while first or (time.monotonic() < t_end and total < REPLY_CAP):
        wait = 0 if first else max(1, min(_LONGPOLL_S, int(t_end - time.monotonic())))
        first = False
        j = _call(token, "getUpdates", {"offset": offset, "timeout": wait, "limit": 100},
                  timeout=wait + 10)
        ups = (j or {}).get("result") or []
        last_handled = None
        for u in ups:
            if total >= REPLY_CAP:
                break                 # بقیه تأیید نمی‌شوند — دور بعد کهنه‌اند و بی‌جواب تأیید می‌شوند
            total += handle_update(u, token, allowed)
            last_handled = int(u.get("update_id") or 0)
        if last_handled is not None:
            offset = last_handled + 1
            # تأیید فوری صف خوانده‌شده — حتی اگر اجرا همین‌جا قطع شود، دوباره جواب نمی‌گیرند
            _call(token, "getUpdates", {"offset": offset, "timeout": 0, "limit": 1})
    return total


# ------------------------------------------------------------- خلاصه‌ی روزانه
def digest_marker_id(day: Optional[str] = None) -> str:
    """شناسه‌ی قطعی نشانگر روز — هر روز فقط یک خلاصه."""
    day = day or datetime.now(TEHRAN).strftime("%Y-%m-%d")
    return f"bot:digest:{day}"


def build_digest(now: Optional[datetime] = None) -> str:
    from core import arena as A        # noqa: PLC0415
    from core import arena_store       # noqa: PLC0415
    now = now or datetime.now(TEHRAN)
    day = now.strftime("%Y-%m-%d")
    trades = arena_store.get_store().load_all()
    closed = [t for t in trades if t.get("status") == "closed"]
    opens = [t for t in trades if t.get("status") == "open"]
    best = top_rows(closed, opens)
    w0 = (now - timedelta(hours=24)).astimezone(timezone.utc)
    wins_24h = []
    for t in closed:
        r = float(t.get("realized_r") or 0.0)
        c = _parse_dt(t.get("closed_at"))
        if r > 0 and c and c >= w0:
            wins_24h.append(t)
    wins_24h.sort(key=lambda t: -float(t.get("realized_r") or 0.0))
    return fmt_digest(day, best, wins_24h[:3], len(opens))


def daily_digest() -> bool:
    """خلاصه‌ی روزانه به چت مالک — نشانگر ضدتکرار قبل از ارسال درج می‌شود
    (اگر ارسال بعداً شکست بخورد، امروز دیگر تلاش نمی‌شود — ضداسپم مقدم است)."""
    from core import alerts as AL       # noqa: PLC0415
    from core import telegram as TG     # noqa: PLC0415
    if not TG.enabled():
        return False
    day = datetime.now(TEHRAN).strftime("%Y-%m-%d")
    marker = {"id": digest_marker_id(day), "kind": "bot", "agent": "bot",
              "symbol": "TGSTATE", "direction": 0,
              "evidence": f"daily digest sent for {day}",
              "created_at": _utcnow_iso()}
    if not AL.push_alert(marker):
        return False                    # امروز قبلاً فرستاده شده
    try:
        text = build_digest()
    except Exception as e:  # noqa: BLE001
        _log(f"⚠️ ساخت خلاصه‌ی روزانه ناموفق: {e}")
        return False
    ok = TG.send(text)
    if ok:
        _log(f"🌅 خلاصه‌ی روزانه‌ی {day} ارسال شد")
    else:
        _log("⚠️ ارسال خلاصه‌ی روزانه ناموفق — امروز دیگر تلاش نمی‌شود (ضداسپم)")
    return ok


# ------------------------------------------------------------- main
def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    once = "--once" in argv           # فقط تخلیه‌ی سریع صف — کمربند احتیاطی اتوپایلوت
    t0 = time.time()
    try:
        n = poll_once(budget=0.0 if once else None)
        _log(f"🤖 بات تلگرام: {n} پاسخ در {time.time() - t0:.1f}s")
    except Exception as e:  # noqa: BLE001 — بات هرگز Actions را نمی‌شکند
        _log(f"⚠️ چرخه‌ی بات ناموفق (غیربحرانی): {e}")
    if not once:
        try:
            daily_digest()
        except Exception as e:  # noqa: BLE001
            _log(f"⚠️ خلاصه‌ی روزانه ناموفق (غیربحرانی): {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
