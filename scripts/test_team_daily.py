# -*- coding: utf-8 -*-
"""آزمون‌های core/team_daily.py — گزارشِ روزانه‌ی اتاقِ تیم در تلگرام
بدونِ شبکه و کاملاً قطعی: قالب‌بندیِ پیام + fail-soft با باتِ ماک‌شده.
اجرا:  python scripts/test_team_daily.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from core import team_daily as TD  # noqa: E402
from core import team_room as TR  # noqa: E402
from core import telegram as TG  # noqa: E402

ok = 0
fail = 0


def check(name, fn):
    global ok, fail
    try:
        res = fn()
        msg = res if isinstance(res, str) else "ok"
        print(f"  OK   {name}" + (f" — {msg}" if msg != "ok" else ""))
        ok += 1
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL {name} — {type(e).__name__}: {e}")
        fail += 1


def _synth(n=340, base=100.0, drift=0.0008):
    """کندل‌های قطعی (بدون random) — همان مولدِ تستِ اتاقِ تیم."""
    t = np.arange(n, dtype=float)
    close = base * (1.0 + drift * t + 0.02 * np.sin(t / 12.0))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) * (1.0 + 0.004)
    low = np.minimum(open_, close) * (1.0 - 0.004)
    vol = 1000.0 + 150.0 * np.abs(np.sin(t / 9.0))
    ms = pd.date_range("2026-01-01", periods=n, freq="1h")
    return pd.DataFrame({
        "time": (ms.astype("int64") // 10**9) * 1000,
        "open": open_, "high": high, "low": low, "close": close, "volume": vol,
        "dt": ms,
    })


NEWS_OK = {"items": [
    {"source": "Decrypt", "title": "Bitcoin ETF Approval Sparks Institutional Inflow",
     "link": "https://x/1", "ts": "2026-11-14T09:00:00Z", "symbols": ["BTC"]},
], "ts": 0, "stale": False, "cached": False}

TS = "2026-11-14 12:00"


# ------------------------------------------------------------- جلسه‌ی واقعی
def _real_room():
    d = _synth()
    room = TR.investigate(df=d, news=NEWS_OK, with_news=True, ts=TS,
                          capital=1000.0, risk_pct=1.0)
    assert room.get("ok"), room.get("error")
    return room


def t1_pick_symbol():
    cands = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
    a, b = TD.pick_symbol(cands, day=10), TD.pick_symbol(cands, day=11)
    assert a == cands[10 % 3] and b == cands[11 % 3], (a, b)
    assert a != b, "روزهایِ پشت‌سرهم باید فرق کنند"
    assert TD.pick_symbol(cands, day=10) == a, "قطعیت"
    assert TD.pick_symbol(day=1) in TD.CANDIDATES, "پیش‌فرض باید از لیستِ اصلی باشد"
    return f"چرخشِ قطعی: {a} → {b}"


def t2_report_structure():
    room = _real_room()
    text = TD.build_report_text(room)
    assert text.startswith("🤝"), "سربرگِ جلسه"
    for name in ("خبرنگار", "دیدبان", "چارت‌خوان", "مدیرِ ریسک", "شکاک"):
        assert name in text, f"عاملِ {name} در پیام نیست"
    assert (room["verdict"]["title"]) in text, "حکمِ تیم در پیام نیست"
    assert "تحلیل است، نه سفارش" in text, "سلبِ مسئولیتِ مفقود"
    assert len(text) <= TG.MAX_TEXT, f"پیام {len(text)} نویسه — بیش از سقف"
    assert text.count("<b>") == text.count("</b>"), "تگِ <b> نامتوازن"
    return f"{len(text)} نویسه · ۵ عامل + حکم + شکاک"


def t3_active_plan_in_report():
    """اتاقِ دست‌ساز با طرحِ فعال — ورود/حدضرر و اندازه‌ی ریسک باید در پیام باشد."""
    plan = {"status": "active", "direction": "لانگ (خرید) 🟢", "entry": 101.0, "stop": 99.0,
            "targets": [(104.0, "x")], "rr": 1.5, "confidence": 60,
            "why": "ستاپِ تست‌شده",
            "qc": {"setup_tested": True, "stats": {"n": 40, "win1": 55},
                   "stamp": "✅ QC 14/14", "issues": [], "warnings": []}}
    room = {
        "ok": True, "symbol": "TEST-USDT", "interval": "1hour", "exchange": "OKX",
        "ts": TS, "price": 101.0, "dec": 2, "plan": plan,
        "agents": {
            "news": {"emoji": "📰", "name": "خبرنگار",
                     "msgs": [{"text": "خبرِ مثبت: <b>ETF Approval</b>", "why": "تیتر"}],
                     "claims": []},
            "watchdog": {"emoji": "👁️", "name": "دیدبان",
                         "msgs": [{"text": "حجم 1.2× میانگین — عادی", "why": "z"}],
                         "claims": []},
            "chart": {"emoji": "📊", "name": "چارت‌خوان", "msgs": [], "claims": []},
            "risk": {"emoji": "💼", "name": "مدیرِ ریسک", "msgs": [], "claims": [
                {"by": "risk", "side": 0, "evidence": "f", "capital": 1000.0,
                 "risk_pct": 1.0, "size": 5.0, "fee_drag_r": 0.1,
                 "claim": "اندازه‌ی 5.0000 واحد — ضررِ حداکثریِ 10.00 (۱٪ سرمایه)"}]},
        },
        "skeptic": {"checks": [
            {"target": "مدیرِ ریسک", "about": "محاسبه‌ی اندازه", "verdict": "تایید",
             "reason": "بازمحاسبه کردم: 5.0000 واحد — درست است"},
            {"target": "داده", "about": "هم‌جهتی", "verdict": "تایید",
             "reason": "حرکت با حجم همراه است"},
        ]},
        "verdict": {"state": "align", "title": "✅ تیم هم‌نظر است — با استدلالِ قابلِ بررسی",
                    "text": "…", "n_obj": 0, "n_warn": 0, "n_confirm": 2},
    }
    text = TD.build_report_text(room)
    assert "ورود <b>101.00</b>" in text and "حدضرر <b>99.00</b>" in text, "سطوحِ طرح"
    assert "5.0000 واحد" in text and "10.00" in text, "اندازه‌ی مدیرِ ریسک"
    assert "✅ <b>مدیرِ ریسک</b>" in text.replace("\n", " "), "داوریِ تاییدِ شکاک"
    assert "QC 14/14" in text, "مُهرِ QC"
    assert text.count("<b>") == text.count("</b>"), "تگِ <b> نامتوازن"
    return "طرحِ فعال: ورود/حدضرر + اندازه‌ی 5 واحد + تاییدِ شکاک"


def t4_html_safety():
    """کاراکترهای خامِ < و & باید فرار کنند — فقط <b> مجاز است."""
    room = {
        "ok": True, "symbol": "X&Y-USDT", "interval": "1hour", "exchange": "OKX",
        "ts": TS, "price": 1.0, "dec": 6,
        "plan": {"status": "wait", "why": "a < b & c", "qc": {}},
        "agents": {"news": {"emoji": "📰", "name": "خبرنگار",
                            "msgs": [{"text": "AT&T < dip > bounce", "why": "w"}],
                            "claims": []}},
        "skeptic": {"checks": []},
        "verdict": {"state": "wait", "title": "⏸ انتظار", "n_obj": 0,
                    "n_warn": 0, "n_confirm": 0},
    }
    text = TD.build_report_text(room)
    assert "AT&amp;T" in text, "& باید فرار کند"
    assert "&lt; dip &gt;" in text, "< و > باید فرار کنند"
    assert "X&amp;Y-USDT" in text, "فرار در سربرگ"
    assert text.count("<b>") == text.count("</b>"), "تگِ <b> نامتوازن"
    return "& و < خام → &amp;/&lt; · تگِ <b> سالم"


# ------------------------------------------------------------- run() با باتِ ماک
def t5_run_disabled():
    orig = TG._cfg
    TG._cfg = lambda: (None, None)
    try:
        st = TD.run()
    finally:
        TG._cfg = orig
    assert st == "غیرفعال", st
    return "بدون توکن → بی‌صدا رد (Actions سبز می‌ماند)"


def t6_run_fail_soft():
    """شبکه‌ی مرده → notify_failure + بدونِ کرش؛ تلگرام هم ماک است."""
    orig_cfg, orig_inv, orig_nf = TG._cfg, TD.TR.investigate, TG.notify_failure
    sent = {}
    TG._cfg = lambda: ("tok", "chat")
    TG.notify_failure = lambda stage, msg="": (sent.update(stage=stage, msg=msg), True)[1]

    def boom(**kw):
        raise RuntimeError("net down")
    TD.TR.investigate = boom
    try:
        st = TD.run(symbol="BTC-USDT")
    finally:
        TG._cfg, TD.TR.investigate, TG.notify_failure = orig_cfg, orig_inv, orig_nf
    assert st == "خطای جلسه", st
    assert sent.get("stage") == "team-daily", sent
    assert "net down" in str(sent.get("msg")), sent
    return "شبکه‌ی مرده → notify_failure، بدونِ کرش"


def t7_room_error_path():
    """جلسه‌ی fail-softِ واقعی (ok=False) → خطای جلسه + notify_failure."""
    orig_cfg, orig_inv, orig_nf = TG._cfg, TD.TR.investigate, TG.notify_failure
    sent = {}
    TG._cfg = lambda: ("tok", "chat")
    TG.notify_failure = lambda stage, msg="": (sent.update(stage=stage, msg=msg), True)[1]
    TD.TR.investigate = lambda **kw: {"ok": False, "error": "کندلی برنگشت"}
    try:
        st = TD.run(symbol="BTC-USDT")
    finally:
        TG._cfg, TD.TR.investigate, TG.notify_failure = orig_cfg, orig_inv, orig_nf
    assert st == "خطای جلسه", st
    assert "کندلی برنگشت" in str(sent.get("msg")), sent
    return "ok=False → پیامِ خطای شفاف به تلگرام"


if __name__ == "__main__":
    print("== گزارشِ روزانه‌ی اتاقِ تیم ==")
    check("چرخشِ روزانه‌ی نماد", t1_pick_symbol)
    check("ساختارِ پیام (۵ عامل + حکم + شکاک)", t2_report_structure)
    check("طرحِ فعال → سطوح + اندازه‌ی ریسک در پیام", t3_active_plan_in_report)
    check("ایمنیِ HTML تلگرام", t4_html_safety)
    check("run() بدون توکن", t5_run_disabled)
    check("run() با شبکه‌ی مرده", t6_run_fail_soft)
    check("run() با جلسه‌ی ok=False", t7_room_error_path)
    print(f"===== {ok} passed, {fail} failed =====")
    raise SystemExit(1 if fail else 0)
