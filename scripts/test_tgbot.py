#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/test_tgbot.py — تست فاز ۱۵: بات تلگرام (بهترین ایجنت‌ها + سیگنال‌های سودده)
اجرا: python3 scripts/test_tgbot.py   (بدون شبکه — API و دیتا همه فیک است)"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ریشه‌ی ریپو

from core import alerts as AL  # noqa: E402
from core import arena as A  # noqa: E402
from core import arena_store  # noqa: E402
from core import telegram as TG  # noqa: E402
from core import tg_bot as TB  # noqa: E402

NOW = datetime.now(timezone.utc)
PASS = 0


def ok(cond, name):
    global PASS
    assert cond, f"FAIL: {name}"
    PASS += 1
    print(f"  ✓ {name}")


def mk(tid, agent, sym, r, *, status="closed", d=-1, closed_min=60, entry=100.0,
       stop=95.0, points=None, exchange="KuCoin"):
    return {"id": tid, "agent": agent, "symbol": sym, "direction": d,
            "status": status, "entry": entry, "stop": stop, "tp1": entry * 1.05,
            "realized_r": r, "points": points if points is not None else r * 10,
            "closed_at": (NOW - timedelta(minutes=closed_min)).isoformat()
                         if status == "closed" else None,
            "created_at": (NOW - timedelta(minutes=closed_min + 30)).isoformat(),
            "exit_reason": "tp1", "exchange": exchange, "interval": "1hour"}


NAMES = [p["name"] for p in A.participants() if p["kind"] == "agent"][:2]

print("— مسیریابی دستورها (فارسی + انگلیسی) —")
ok(TB.route("/top") == "top" and TB.route("بهترین") == "top"
   and TB.route("بهترین ها") == "top" and TB.route("/top@MyBot") == "top"
   and TB.route("TOP") == "top", "/top و «بهترین» و پسوند بات")
ok(TB.route("/signals") == "signals" and TB.route("سیگنال") == "signals", "/signals و «سیگنال»")
ok(TB.route("/stats") == "stats" and TB.route("آمار") == "stats", "/stats و «آمار»")
ok(TB.route("/start") == "welcome" and TB.route("سلام") == "welcome", "/start و «سلام»")
ok(TB.route("/help") == "help" and TB.route("راهنما") == "help", "/help و «راهنما»")
ok(TB.route("چطور خبرهای امروز؟") is None, "پیام عادی — بدون پاسخ")
ok(TB.route("/blahblah") == "unknown", "دستور ناشناخته")

print("— بهترین ایجنت‌ها —")
closed = [mk(f"w{i}", NAMES[0], "SOLUSDT", 1.2, d=1, closed_min=100 - i * 10)
          for i in range(3)]
closed += [mk(f"l{i}", NAMES[1], "BTCUSDT", -0.8, d=1, closed_min=200 - i * 10)
           for i in range(2)]
opens = [mk("o1", NAMES[0], "XRPUSDT", 0.0, status="open", d=1)]
best = TB.top_rows(closed, opens)
ok(len(best) >= 1 and best[0]["agent"] == NAMES[0], "فقط سودده‌ها؛ رتبه ۱ = ۳ برد متوالی")
ok(best[0]["streak"] == 3 and best[0]["form10_r"] > 0, "زنجیره و فرم ۱۰تایی")
txt = TB.fmt_top(best, closed + opens)
ok("🏆" in txt and NAMES[0] in txt and "🔥 3 برد متوالی" in txt, "فرمت: مدال + داغ")
ok(NAMES[1] not in txt, "ایجنت ضررده در فهرست نیست")
ok(TB.fmt_top([], []).startswith("🏆"), "بدون سودده = پیام شروع")

print("— سیگنال‌های سودده: بردها —")
closed2 = closed + [mk("old", NAMES[0], "DOGEUSDT", 2.0, closed_min=60 * 24 * 10)]
wins = TB.winning_closes(closed2)
ok(all(float(t["realized_r"]) >= TB.MIN_WIN_R for t in wins), "فقط R بالای آستانه")
ok(all((NOW - datetime.fromisoformat(t["closed_at"])).days < TB.SIGNAL_WINDOW_D + 1
       for t in wins), "پنجره‌ی ۷ روز")
ok(wins == sorted(wins, key=lambda t: -float(t["realized_r"])), "مرتب: قوی‌ترین اول")
ok(all(t["id"] != "old" for t in wins), "برد ۱۰ روزه حذف شد")
sig = TB.fmt_signals(wins, [])
ok("SOLUSDT" in sig and "+1.20R" in sig, "فرمت سیگنال: نماد + R")

print("— سیگنال‌های سودده: پوزیشن باز در سود —")
fake_px = {"XRPUSDT": 110.0, "ADAUSDT": 90.0, "ETHUSDT": 99.0}
op = [mk("o1", NAMES[0], "XRPUSDT", 0.0, status="open", d=1, entry=100.0),
      mk("o2", NAMES[0], "ADAUSDT", 0.0, status="open", d=-1, entry=100.0),
      mk("o3", NAMES[0], "ETHUSDT", 0.0, status="open", d=1, entry=100.0),
      mk("o4", NAMES[0], "DOTUSDT", 0.0, status="open", d=1, entry=100.0)]
profits = TB.open_in_profit(op, price_fn=lambda ex, s: fake_px.get(s))
ids = [t["id"] for t in profits]
ok("o1" in ids and "o2" in ids, "لانگ بالای ورود + شورت زیر ورود = در سود")
ok("o3" not in ids and "o4" not in ids, "لانگ زیر ورود + بدون قیمت = حذف")
ok(profits[0]["pnl_pct"] >= profits[-1]["pnl_pct"], "مرتب نزولی درصد سود")
sig2 = TB.fmt_signals([], profits)
ok("در سود" in sig2 and "XRPUSDT" in sig2 and "+10.0%" in sig2, "فرمت: بازِ در سود")

print("— قیمت زنده (پارس بدون شبکه) —")
import core.net as NET  # noqa: E402

_orig_gj = NET.get_json
try:
    NET.get_json = lambda url, **kw: {"data": {"price": "123.45"}}
    ok(TB.live_price("KuCoin", "BTC-USDT") == 123.45, "شکل KuCoin")
    NET.get_json = lambda url, **kw: (_ for _ in ()).throw(RuntimeError("x"))
    ok(TB.live_price("KuCoin", "BTC-USDT") is None, "همه‌ی منابع شکست → None")
    calls = []

    def seq(url, **kw):
        calls.append(url)
        if "kucoin" in url:
            raise RuntimeError("kucoin down")
        return {"price": "77.7"}

    NET.get_json = seq
    ok(TB.live_price("KuCoin", "BTC-USDT") == 77.7, "فال‌بک Binance")
    ok(any("binance" in u for u in calls), "ترتیب فال‌بک درست")
finally:
    NET.get_json = _orig_gj

print("— آمار و خلاصه —")
st = TB.fmt_stats(closed, opens, {"kind": "regime", "direction": 1,
                                  "created_at": "2026-11-01T10:00:00Z"})
ok("وین‌ریت" in st and "انتظاری" in st and "رژیم" in st, "فرمت آمار + رژیم")
dg = TB.build_digest.__wrapped__ if hasattr(TB.build_digest, "__wrapped__") else TB.build_digest


class FakeStore:
    def __init__(self, rows):
        self.rows = rows

    def load_all(self):
        return self.rows


_orig_store = arena_store.get_store
arena_store.get_store = lambda: FakeStore(closed + opens)
try:
    txt_dg = TB.build_digest(now=datetime.now(TB.TEHRAN))
    ok("خلاصه‌ی روزانه" in txt_dg and "پوزیشن باز: 1" in txt_dg, "فرمت خلاصه‌ی روزانه")
finally:
    arena_store.get_store = _orig_store

print("— نشانگر ضدتکرار خلاصه‌ی روزانه —")
ok(AL.valid_alert({"id": "bot:digest:2026-11-03", "kind": "bot", "agent": "bot",
                   "symbol": "TGSTATE", "direction": 0,
                   "evidence": "daily digest sent for 2026-11-03",
                   "created_at": "2026-11-03T06:00:00Z"}) is True, "نشانگر bot معتبر است")
TB.digest_marker_id  # noqa: B018 — فقط مطمئن شو قابل فراخوانی است
ok(TB.digest_marker_id("2026-11-03") == "bot:digest:2026-11-03", "شناسه‌ی قطعی روز")
import tempfile  # noqa: E402

_tmpdir = tempfile.mkdtemp(prefix="tgbot_test_")
AL.LOCAL_FILE = os.path.join(_tmpdir, "alerts.json")
_sent = []
TG._cfg = lambda: ("TESTTOKEN", "123")
TG.send = lambda text, silent=False: _sent.append(text) or True
_orig_alerts = AL.get_alerts
AL.get_alerts = lambda: AL.AlertStore()
arena_store.get_store = lambda: FakeStore(closed + opens)
try:
    ok(TB.daily_digest() is True and len(_sent) == 1, "روز اول: ارسال شد")
    ok(TB.daily_digest() is False and len(_sent) == 1, "روز دوم همان روز: ارسال نشد (ضدتکرار)")
    rows = AL.get_alerts().load_recent(10)
    ok(any(r.get("kind") == "bot" for r in rows), "نشانگر در استور ثبت شده")
finally:
    AL.get_alerts = _orig_alerts
    arena_store.get_store = _orig_store
    TG._cfg = TG.__dict__["_cfg"]

print("— پردازش آپدیت‌های بات —")


def upd(text, chat=111, age_min=1, uid=55):
    return {"update_id": uid,
            "message": {"message_id": 1, "date": int((NOW - timedelta(minutes=age_min)).timestamp()),
                        "chat": {"id": chat}, "text": text}}


_sent_chat = []
TB._send_chat = lambda token, chat, text, silent=False: _sent_chat.append((chat, text)) or True
_orig_reply = TB.build_reply

# ۱) دستور مجاز → پاسخ
TB.build_reply = lambda key: f"REPLY[{key}]"
n = TB.handle_update(upd("/top"), "TOK", {"111"})
ok(n == 1 and _sent_chat[-1][0] == 111 and "REPLY[top]" in _sent_chat[-1][1], "دستور مجاز → پاسخ")
# ۲) چت غیرمجاز → پیام رد، بدون دیتا
TB._sent_calls = None
n = TB.handle_update(upd("/top", chat=999), "TOK", {"111"})
ok(n == 0 and _sent_chat[-1][0] == 999 and "⛔" in _sent_chat[-1][1], "چت غیرمجاز → رد مؤدبانه")
# ۳) چت غیرمجاز با حالت عمومی (*)
n = TB.handle_update(upd("/top", chat=999), "TOK", {"*"})
ok(n == 1 and "REPLY[top]" in _sent_chat[-1][1], "حالت عمومی (*) → پاسخ")
# ۴) پیام کهنه → هیچ
_sent_chat.clear()
n = TB.handle_update(upd("/top", age_min=120), "TOK", set())
ok(n == 0 and not _sent_chat, "پیام کهنه → بی‌جواب")
# ۵) متن عادی → هیچ، دستور ناشناخته → راهنما
n = TB.handle_update(upd("سلامی به همه"), "TOK", {"111"})
ok(n == 0, "متن عادی → بی‌جواب")
TB.build_reply = _orig_reply
n = TB.handle_update(upd("/whatever"), "TOK", {"111"})
ok(n == 1 and "ناشناخته" in _sent_chat[-1][1], "دستور ناشناخته → راهنما")
# ۶) خطای دیتا → پیام مهربان، نه مرگ
TB.build_reply = lambda key: (_ for _ in ()).throw(RuntimeError("boom"))
n = TB.handle_update(upd("/top"), "TOK", {"111"})
ok(n == 1 and "چند دقیقه بعد" in _sent_chat[-1][1], "خطای دیتا → پیام خطای مهربان")
TB.build_reply = _orig_reply

print("— چرخه‌ی poll_once (فیک) —")
_orig_sg = TB._secrets_get
TB._secrets_get = lambda k: {"TELEGRAM_BOT_TOKEN": "TOK", "TELEGRAM_CHAT_ID": "111"}.get(k)
_orig_call = TB._call
try:
    TB._call = lambda tok, m, p=None, timeout=15: (
        {"ok": True, "result": [upd("/top", uid=100, age_min=2)]}
        if p and p.get("offset", 1) == 0 and p.get("timeout") == 0
        else {"ok": True, "result": []})
    TB.build_reply = lambda key: f"REPLY[{key}]"
    _sent_chat.clear()
    ok(TB.poll_once(budget=0.05) == 1 and "REPLY[top]" in _sent_chat[-1][1],
       "چرخه: تخلیه‌ی صف + پاسخ")
    TB._call = lambda tok, m, p=None, timeout=15: {"ok": True, "result": []}
    ok(TB.poll_once(budget=0.05) == 0, "صف خالی → صفر پاسخ")
    # صف چندتایی: همه‌ی تازه‌ها جواب می‌گیرند، نه فقط آخرین پیام (رفع باگ «زدم ولی چیزی نیامد»)
    TB._call = lambda tok, m, p=None, timeout=15: (
        {"ok": True, "result": [upd("/top", uid=100, age_min=1),
                                upd("/stats", uid=101, age_min=1),
                                upd("/signals", uid=102, age_min=90)]}
        if p and p.get("offset", 1) == 0 and p.get("timeout") == 0
        else {"ok": True, "result": []})
    _sent_chat.clear()
    n = TB.poll_once(budget=0.05)
    ok(n == 2 and "REPLY[top]" in _sent_chat[-2][1] and "REPLY[stats]" in _sent_chat[-1][1],
       "صف ۳تایی (یکی کهنه) → فقط ۲ تازه جواب می‌گیرند")
    TB._secrets_get = lambda k: None
    ok(TB.poll_once(budget=0.05) == 0, "بدون توکن → رد شدن بی‌صدا")
finally:
    TB._secrets_get = _orig_sg
    TB._call = _orig_call
    TB.build_reply = _orig_reply

print("— نشان‌های تلگرام لحظه‌ای (داغ/سیگنال سودده) —")
arena_store.get_store = lambda: FakeStore(closed)          # NAMES[0] = ۳ برد متوالی
try:
    _out = []
    TG.send = lambda text, silent=False: _out.append(text) or True
    TG.notify_open(mk("op9", NAMES[0], "AVAXUSDT", 0.0, status="open", d=1))
    ok("🔥 پوزیشن جدید باز شد — از بهترین ایجنت‌ها" in _out[-1]
       and "🔥 3 برد متوالی" in _out[-1], "بازشدن از ایجنت داغ → نشان 🔥")
    TG.notify_close(mk("cl9", NAMES[0], "AVAXUSDT", 1.8, d=1))
    ok("🏆 سیگنال سودده" in _out[-1], "بسته‌شدن ≥ +1R → نشان سیگنال سودده")
    TG.notify_close(mk("cl8", NAMES[0], "AVAXUSDT", -0.6, d=1))
    ok("🟥 پوزیشن بسته شد" in _out[-1] and "سیگنال سودده" not in _out[-1], "ضرر → بدون نشان")
    TG.notify_open(mk("op8", "NOBODY", "FTMUSDT", 0.0, status="open", d=1))
    ok("🟢 پوزیشن جدید باز شد" in _out[-1], "ایجنت بدون کارنامه → پیام ساده")
finally:
    arena_store.get_store = _orig_store

print("— main دودی (بدون توکن واقعی) —")
ok(TB.main() == 0, "main بدون شبکه سالم تمام می‌شود")

print(f"\n✅ همه‌ی {PASS} تست سبز — tg_bot آماده است")
sys.exit(0)
