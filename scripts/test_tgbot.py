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

# تست‌های قدیمی با معاملات KuCoin کار می‌کنند — فیلتر تمرکز صرافی را خنثی می‌کنیم؛
# رفتار «فقط لایتر» در بخش‌های اختصاصی خودش تست می‌شود.
TB.BOT_EXCHANGE = ""
TG.NOTIFY_EXCHANGE = ""

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
ok("سولانا (SOL/USDT)" in sig and "+1.20R" in sig, "فرمت سیگنال: نام ارز + نماد تمیز + R")

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
ok("در سود" in sig2 and "ریپل (XRP/USDT)" in sig2 and "+10.0%" in sig2, "فرمت: بازِ در سود با نام ارز")

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
    ok("سولانا (SOL/USDT)" in txt_dg and "+1.20R" in txt_dg, "خلاصه: بردها با نام ارز و نماد")
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

print("— عمر پوزیشن، تازگی و سطح‌ها (سیگنال عملیاتی) —")
# سن فارسی
ok(TB._age_fa(NOW) == "همین الان", "سن: همین الان")
ok(TB._age_fa(NOW - timedelta(minutes=12)) == "12 دقیقه پیش", "سن: ۱۲ دقیقه")
ok(TB._age_fa(NOW - timedelta(hours=3)) == "3 ساعت پیش", "سن: ۳ ساعت")
ok(TB._age_fa(NOW - timedelta(days=2)) == "2 روز پیش", "سن: ۲ روز")
ok(TB._age_fa(None) == "", "سن: بدون تاریخ → خالی")
# برچسب تازگی
ok("🟢" in TB._freshness_label(5), "تازگی: ۵ دقیقه → 🟢 تازه")
ok("🟡" in TB._freshness_label(20), "تازگی: ۲۰ دقیقه → 🟡 نیمه‌تازه")
ok("🟠" in TB._freshness_label(90) and "🟠" in TB._freshness_label(float("inf")),
   "تازگی: ۹۰ دقیقه و تاریخ نامعلوم → 🟠 کهنه (محتاطانه)")
# خط سطح‌ها
t_lv = {"cur_stop": 101.0, "stop": 95.0, "tp1": 110.0, "tp2": 120.0, "tp3": 130.0,
        "tp1_done": True, "tp2_done": False}
lv = TB._levels_line(t_lv)
ok("SL 101" in lv and "✅ TP1 110" in lv and "🎯 TP2 120" in lv and "🏆 TP3 130" in lv,
   "سطح‌ها: استاپ مؤثر + سه TP با نشان پیشرفت")
ok(TB._levels_line({}) == "", "سطح‌ها: بدون دیتا → خط خالی")
# open_in_profit با عمر
op_raw = {"symbol": "BTCUSDT", "agent": "A", "direction": 1, "entry": 100.0,
          "exchange": "KuCoin", "opened_at": (NOW - timedelta(minutes=7)).isoformat()}
out_op = TB.open_in_profit([op_raw], price_fn=lambda ex, sy: 102.0, now=NOW)
ok(out_op and 6.9 < out_op[0]["age_min"] < 7.1, "باز در سود: عمر پوزیشن محاسبه شد")
# fmt_signals یکپارچه: گذشته/زنده + عمر + سطح‌ها + سلب مسئولیت
op_t = {"symbol": "BTCUSDT", "agent": "A", "direction": 1, "entry": 100.0, "now": 102.0,
        "pnl_pct": 2.0, "age_min": 7.0,
        "opened_at": (NOW - timedelta(minutes=7)).isoformat(),
        "stop": 95.0, "cur_stop": 101.0, "tp1": 110.0, "tp2": 120.0, "tp3": 130.0,
        "tp1_done": False, "tp2_done": False}
win_t = {"symbol": "ETHUSDT", "agent": "B", "direction": -1, "entry": 50.0,
         "closed_price": 47.0, "realized_r": 1.4, "points": 1.4,
         "closed_at": (NOW - timedelta(hours=5)).isoformat()}
sig = TB.fmt_signals([win_t], [op_t], now=NOW)
ok("گزارش گذشته" in sig and "5 ساعت پیش بسته شد" in sig,
   "سیگنال: بردها = گزارش گذشته + سن بسته‌شدن")
ok("🟢" in sig and "7 دقیقه پیش" in sig, "سیگنال: پوزیشن باز تازه با عمر")
ok("SL 101" in sig and "TP3 130" in sig, "سیگنال: سطح‌های SL/TP در پوزیشن باز")
ok("برگشت‌پذیر" in sig and "آموزش، نه توصیه‌ی مالی" in sig, "سیگنال: سلب مسئولیت صادقانه")
# notify_open: هر سه TP در پیام لحظه‌ای
_out3 = []
TG.send = lambda text, silent=False: _out3.append(text) or True
TG.notify_open({"agent": "A", "symbol": "BTCUSDT", "direction": 1, "entry": 100.0,
                "stop": 95.0, "tp1": 110.0, "tp2": 120.0, "tp3": 130.0, "rr": 2.0,
                "exchange": "KuCoin", "evidence": ""})
ok("TP1: 110" in _out3[-1] and "TP2: 120" in _out3[-1] and "TP3: 130" in _out3[-1],
   "بازشدن: هر سه TP در پیام لحظه‌ای")

print("— نام ارز، صرافی و تایم‌فریم (خواسته‌ی کاربر) —")
from core import coins as CO  # noqa: E402
ok(CO.base("BTC-USDT") == "BTC" and CO.base("BTCUSDT") == "BTC"
   and CO.base("BTC/USDT") == "BTC" and CO.base("SOLUSDT") == "SOL", "نماد پایه: هر سه شکل ورودی")
ok(CO.pair_display("BTC-USDT") == "BTC/USDT" and CO.pair_display("DOGEUSDT") == "DOGE/USDT",
   "جفت‌نماد تمیز")
ok(CO.coin_label("BTC-USDT") == "بیت‌کوین (BTC/USDT)" and CO.coin_label("XYZUSDT") == "XYZ/USDT",
   "برچسب: نام فارسی + نماد؛ ناشناخته = فقط نماد")
ok(CO.name_pair("ETH-USDT") == ("اتریوم", "Ethereum"), "نام دوزبانه")
ok(CO.quote("BTC-USDT") == "USDT" and CO.quote("BTCUSDC") == "USDC", "ارز مبنا")
ok(TB._fmt_num(1.21e-05) == "0.0000121" and TG._fmt_num(1.21e-05) == "0.0000121",
   "قیمت ریز (میم‌کوین): بدون نماد علمی e-05")
ok(TB._fmt_num(0.0005) == "0.0005" and TB._fmt_num(103250.5) == "103,250", "قیمت: شکل‌های میانی")

win_c = {"symbol": "BTCUSDT", "agent": "A", "direction": 1, "entry": 100.0,
         "closed_price": 105.0, "realized_r": 1.0, "points": 10.0,
         "closed_at": (NOW - timedelta(hours=2)).isoformat(),
         "exchange": "KuCoin", "interval": "15m"}
op_c = {"symbol": "XRPUSDT", "agent": "B", "direction": -1, "entry": 2.0, "now": 1.9,
        "pnl_pct": 5.0, "age_min": 5.0, "stop": 2.1, "tp1": 1.8,
        "opened_at": (NOW - timedelta(minutes=5)).isoformat(),
        "exchange": "KuCoin", "interval": "1hour"}
sig_c = TB.fmt_signals([win_c], [op_c], now=NOW)
ok("بیت‌کوین (BTC/USDT)" in sig_c and "ریپل (XRP/USDT)" in sig_c, "سیگنال: نام ارز + نماد تمیز")
ok("🏦 صرافی: <b>KuCoin</b>" in sig_c, "سیگنال: صرافی یک‌بار در سر پیام")
ok("⏲ 15m" in sig_c and "⏲ 1hour" in sig_c, "سیگنال: تایم‌فریم هر معامله")
ok("فاصله" in sig_c, "سیگنال: فاصله ٪ تا استاپ برای پوزیشن باز")
ok(TB._ctx_line({"exchange": "KuCoin", "interval": "1h"}, "KuCoin") == "   ⏲ 1h",
   "بافتار: صرافیِ هم‌نامِ اصلی تکرار نمی‌شود")
ok(TB._ctx_line({"exchange": "Binance", "interval": "1h"}, "KuCoin") == "   🏦 Binance · ⏲ 1h",
   "بافتار: صرافیِ متفاوت نمایش داده می‌شود")
lv_gap = TB._levels_line({"stop": 95.0, "direction": 1}, now_px=110.0)
ok("SL 95" in lv_gap and "فاصله 13.6%" in lv_gap, "سطح‌ها: فاصله ٪ تا استاپ (لانگ)")
ok("فاصله" in TB._levels_line({"stop": 95.0, "direction": -1}, now_px=90.0),
   "سطح‌ها: فاصله تا استاپ (شورت)")
ok("فاصله" not in TB._levels_line({"stop": 95.0, "direction": 1}),
   "سطح‌ها: بدون قیمت زنده → بدون فاصله (سازگار با قبل)")

print("— /positions: همه‌ی پوزیشن‌های باز (سود و ضرر) —")
op_px = {"XRPUSDT": 110.0, "ADAUSDT": 90.0, "ETHUSDT": 99.0}
det = TB.open_detailed(op, price_fn=lambda ex, s: op_px.get(s))
ok(len(det) == 3 and det[0]["pnl_pct"] >= det[-1]["pnl_pct"],
   "open_detailed: سود و ضرر با هم، مرتب از بیشترین سود")
ok([t["id"] for t in TB.open_in_profit(op, price_fn=lambda ex, s: op_px.get(s))]
   == ["o1", "o2"], "open_in_profit: فقط سودها — سازگار با قبل")
p_txt = TB.fmt_positions(det)
ok("در سود (2)" in p_txt and "در ضرر (1)" in p_txt, "پوزیشن: بخش سود و ضرر با شمارش")
ok("ریپل (XRP/USDT)" in p_txt and "🏦 صرافی: <b>KuCoin</b>" in p_txt and "⏲ 1hour" in p_txt,
   "پوزیشن: نام ارز + صرافی + تایم‌فریم")
ok("فاصله" in p_txt and "برگشت‌پذیر" in p_txt, "پوزیشن: فاصله تا استاپ + هشدار سود شناور")
ok("وجود ندارد" in TB.fmt_positions([]), "پوزیشن: خالی → پیام شفاف")

print("— /price: قیمت لحظه‌ای هر ارز —")
ok(TB.route("/positions") == "positions" and TB.route("پوزیشن") == "positions"
   and TB.route("پوزیشن ها") == "positions" and TB.route("باز") == "positions",
   "مسیر /positions و مترادف‌های فارسی")
ok(TB.route("/price BTC") == "price:btc" and TB.route("قیمت اتریوم") == "price:اتریوم"
   and TB.route("/price") == "price:", "مسیر /price با و بدون نماد")
ok(TB.resolve_symbol("BTC") == "BTC-USDT" and TB.resolve_symbol("btc-usdt") == "BTC-USDT",
   "نماد: تیکر و جفتِ صریح")
ok(TB.resolve_symbol("بیت‌کوین") == "BTC-USDT" and TB.resolve_symbol("Bitcoin") == "BTC-USDT",
   "نماد: نام فارسی و انگلیسی هم فهمیده می‌شود")
ok(TB.resolve_symbol("DOGEUSDT") == "DOGE-USDT" and TB.resolve_symbol("xyz") == "XYZ-USDT",
   "نماد: شکل بدون جداکننده + بهترین تلاش برای ناشناخته")
try:
    NET.get_json = lambda url, **kw: {"data": {"last": "103250.5", "changeRate": "0.0123"}}
    pt = TB.fmt_price_lookup("BTC")
    ok("بیت‌کوین (BTC/USDT)" in pt and "103,250" in pt and "+1.23%" in pt and "Bitcoin" in pt,
       "قیمت: آمار کوکوین — قیمت + تغییر ۲۴ ساعت + نام انگلیسی")
    ok("Ethereum" in TB.fmt_price_lookup("اتریوم"), "قیمت: نام فارسی → اتریوم")
    NET.get_json = lambda url, **kw: (_ for _ in ()).throw(RuntimeError("x"))
    ok("نگرفتم" in TB.fmt_price_lookup("NOXYZ"), "قیمت: خطا → پیام مهربان")
finally:
    NET.get_json = _orig_gj
ok("نماد بده" in TB.fmt_price_lookup(""), "قیمت: بدون نماد → راهنمای استفاده")

print("— build_reply برای دستورهای تازه —")
_orig_od = TB.open_detailed
_orig_fpl = TB.fmt_price_lookup
arena_store.get_store = lambda: FakeStore(closed + opens)
TB.open_detailed = lambda opens: det
TB.fmt_price_lookup = lambda arg: f"PRICE[{arg}]"
try:
    ok("در سود" in TB.build_reply("positions"), "build_reply: positions از دیتای زنده")
    ok(TB.build_reply("price:btc") == "PRICE[btc]", "build_reply: price → نماد")
finally:
    TB.open_detailed = _orig_od
    TB.fmt_price_lookup = _orig_fpl
    arena_store.get_store = _orig_store

print("— پیام‌های لحظه‌ای: نام ارز + صرافی —")
_out4 = []
TG.send = lambda text, silent=False: _out4.append(text) or True
TG.notify_open(mk("op10", "NOBODY", "BTCUSDT", 0.0, status="open", d=1))
ok("بیت‌کوین (BTC/USDT)" in _out4[-1] and "🏦 KuCoin" in _out4[-1] and "⏲ 1hour" in _out4[-1],
   "بازشدن: نام ارز + صرافی + تایم‌فریم")
TG.notify_close(mk("cl10", "NOBODY", "ETHUSDT", -0.6, d=1))
ok("اتریوم (ETH/USDT)" in _out4[-1] and "🏦 KuCoin" in _out4[-1],
   "بسته‌شدن: نام ارز + صرافی")
TG.notify_open({"agent": "A", "symbol": "XYZUSDT", "direction": 1, "entry": 1.0, "stop": 0.9})
ok("XYZ/USDT" in _out4[-1] and "🏦" not in _out4[-1],
   "بازشدن: بدون صرافی/تایم‌فریم → سطر بافتار حذف می‌شود")

print("— تمرکز ربات روی لایتر: فیلتر صرافی در پیام‌ها —")
mixed = [mk("lw1", NAMES[0], "BTCUSDT", 1.5, d=1, closed_min=60, exchange="Lighter"),
         mk("kw1", NAMES[0], "SOLUSDT", 1.2, d=1, closed_min=70, exchange="KuCoin"),
         mk("lo1", NAMES[0], "XRPUSDT", 0.0, status="open", d=1, exchange="Lighter"),
         mk("ko1", NAMES[0], "ADAUSDT", 0.0, status="open", d=1, exchange="KuCoin")]
_orig_ex = TB.BOT_EXCHANGE
_orig_oip = TB.open_in_profit
_orig_store2 = arena_store.get_store
TB.BOT_EXCHANGE = "Lighter"
TB.open_in_profit = lambda opens: []          # بدون شبکه — فقط بخش بردها چک می‌شود
try:
    ok([t["id"] for t in TB._only_bot_ex(mixed)] == ["lw1", "lo1"],
       "فیلتر: فقط معاملات لایتر، ترتیب حفظ می‌شود")
    ok("Lighter" in TB._ex_line() and TB._ex_line() == "🏦 فقط صرافی <b>Lighter</b>",
       "خط «فقط صرافی» در سر پیام")
    arena_store.get_store = lambda: FakeStore(mixed)
    r_sig = TB.build_reply("signals")
    ok("بیت‌کوین (BTC/USDT)" in r_sig and "سولانا" not in r_sig,
       "سیگنال: فقط معاملات لایتر — KuCoin بی‌صدا حذف")
    r_top = TB.build_reply("top")
    ok("فقط صرافی <b>Lighter</b>" in r_top, "بهترین‌ها: خط تمرکز صرافی")
    r_st = TB.build_reply("stats")
    ok("فقط صرافی" in r_st and "معاملات بسته‌شده: <b>1</b>" in r_st,
       "آمار: فقط معاملات لایتر شمرده می‌شود")
    dg = TB.build_digest(now=datetime.now(TB.TEHRAN))
    ok("سولانا" not in dg and "بیت‌کوین (BTC/USDT)" in dg,
       "خلاصه‌ی روزانه: فقط بردهای لایتر")
finally:
    TB.BOT_EXCHANGE = _orig_ex
    TB.open_in_profit = _orig_oip
    arena_store.get_store = _orig_store2

print("— قیمت زنده‌ی لایتر —")
try:
    NET.get_json = lambda url, **kw: {"order_book_details": [
        {"symbol": "BTC", "last_trade_price": "103250.5", "mark_price": "103000",
         "daily_price_change": "-2.31"},
        {"symbol": "ETH", "last_trade_price": "", "mark_price": "3900.5"}]}
    TB._lighter_cache["ts"], TB._lighter_cache["rows"] = 0.0, {}   # کش تست را خالی کن
    ok(TB.live_price("Lighter", "BTC") == 103250.5, "لایتر: last_trade_price")
    ok(TB.live_price("Lighter", "BTC-USDT") == 103250.5, "لایتر: پسوند سته می‌خورد")
    ok(TB.price_info("Lighter", "BTC") == {"price": 103250.5, "change_pct": -2.31},
       "لایتر: قیمت + تغییر ٪ ۲۴ساعت")
    ok(TB.live_price("Lighter", "ETH") == 3900.5, "لایتر: فال‌بک به mark_price")
    ok(TB.live_price("Lighter", "PEPE") is None, "لایتر: نماد غایب → None")
    ok(TB._lighter_cache["rows"] and TB._lighter_cache["ts"] > 0, "لایتر: کش پر شد")
finally:
    NET.get_json = _orig_gj

print("— لایتر در حالت تمرکز: resolve و /price —")
TB.BOT_EXCHANGE = "Lighter"
try:
    ok(TB.resolve_symbol("BTC") == "BTC" and TB.resolve_symbol("بیت‌کوین") == "BTC"
       and TB.resolve_symbol("BTC-USDT") == "BTC", "resolve لایتر: نماد کوتاه")
    ok(TB.resolve_symbol("ETH") == "ETH" and TB.resolve_symbol("اتریوم") == "ETH",
       "resolve لایتر: تیکر و نام فارسی")
    NET.get_json = lambda url, **kw: {"order_book_details": [
        {"symbol": "BTC", "last_trade_price": "103250.5", "daily_price_change": "-2.31"}]}
    TB._lighter_cache["ts"], TB._lighter_cache["rows"] = 0.0, {}
    pt = TB.fmt_price_lookup("BTC")
    ok("بیت‌کوین (BTC/USDT)" in pt and "103,250" in pt and "-2.31%" in pt
       and "🏦 Lighter" in pt, "/price روی لایتر: قیمت + تغییر + صرافی")
finally:
    NET.get_json = _orig_gj
    TB.BOT_EXCHANGE = _orig_ex

print("— فیلتر صرافی در پیام‌های لحظه‌ای —")
_orig_nx = TG.NOTIFY_EXCHANGE
TG.NOTIFY_EXCHANGE = "Lighter"
_out5 = []
TG.send = lambda text, silent=False: _out5.append(text) or True
try:
    TG.notify_open(mk("lx", "NOBODY", "BTCUSDT", 0.0, status="open", d=1, exchange="Lighter"))
    ok(len(_out5) == 1 and "بیت‌کوین" in _out5[-1], "بازشدن لایتر → ارسال شد")
    TG.notify_open(mk("kx", "NOBODY", "SOLUSDT", 0.0, status="open", d=1, exchange="KuCoin"))
    ok(len(_out5) == 1, "بازشدن KuCoin → رد شد (فقط لایتر)")
    TG.notify_close(mk("kc", "NOBODY", "SOLUSDT", -0.6, d=1, exchange="KuCoin"))
    ok(len(_out5) == 1, "بسته‌شدن KuCoin → رد شد")
    TG.notify_close(mk("lc", "NOBODY", "ETHUSDT", 1.2, d=1, exchange="Lighter"))
    ok(len(_out5) == 2 and "اتریوم" in _out5[-1], "بسته‌شدن لایتر → ارسال شد")
    TG.NOTIFY_EXCHANGE = "*"
    TG.notify_close(mk("kc2", "NOBODY", "SOLUSDT", -0.6, d=1, exchange="KuCoin"))
    ok(len(_out5) == 3, "حالت «*» = همه‌ی صرافی‌ها")
finally:
    TG.NOTIFY_EXCHANGE = _orig_nx

print("— main دودی (بدون توکن واقعی) —")
ok(TB.main() == 0, "main بدون شبکه سالم تمام می‌شود")

print(f"\n✅ همه‌ی {PASS} تست سبز — tg_bot آماده است")
sys.exit(0)
