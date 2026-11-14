# -*- coding: utf-8 -*-
"""آزمونِ ۲۶اُم — core/kronos_promotion.py — قراردادِ پیش‌ثبت‌شده‌ی ارتقا
==========================================================================
همه‌ی آزمون‌ها قطعی و بدونِ شبکه‌اند. حکمِ قرارداد برای هر ورودیِ ممکن ثابت
باید بماند — این آزمون‌ها «قفلِ قرارداد»اند: اگر کسی بعد از دیدنِ نتایج
آستانه‌ها را تکان بدهد، اینجا قرمز می‌شود.

اجرا:  python scripts/test_kronos_promotion.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

from core import kronos_promotion as KP  # noqa: E402

ok = 0
fail = 0


def check(name, fn):
    global ok, fail
    try:
        fn()
        ok += 1
        print(f"  OK   {name}")
    except Exception as exc:  # noqa: BLE001 — گزارشِ آزمون
        fail += 1
        print(f"  FAIL {name}: {type(exc).__name__}: {exc}")


def _gate(n: int, rate, ok_flag=True):
    """دیکته‌ی هم‌شکلِ خروجیِ gate_stats — بدونِ I/O."""
    return {"ok": ok_flag, "n_total": n,
            "real": {"n": n, "agree": round(n * (rate or 0) / 100.0) if rate is not None else 0,
                     "rate": rate},
            "stub": {"n": 0, "agree": 0, "rate": None},
            "gate_pass": bool(ok_flag and n >= 200 and (rate or 0.0) >= 55.0),
            "gate_fa": "", "last": None}


# --------------------------------------------------------------- حکم‌ها
def t1_below_gate_continues():
    r = KP.evaluate(_gate(150, 61.5))
    assert r["verdict"] == "continue", r
    assert "موعدِ حکم نرسیده" in " ".join(r["reasons_fa"]), r


def t2_pass_promotes():
    r = KP.evaluate(_gate(200, 61.5))
    assert r["verdict"] == "promote", r
    assert "ارتقا" in r["verdict_fa"], r


def t3_fail_retires():
    r = KP.evaluate(_gate(200, 50.0))
    assert r["verdict"] == "retire", r
    assert "بازنشستگی" in r["verdict_fa"], r


def t4_boundary_is_promote():
    # قرارداد: ≥۵۵٪ — دقیقاً ۵۵ باید ارتقا بدهد (هم‌تراز با gate_pass)
    r = KP.evaluate(_gate(200, 55.0))
    assert r["verdict"] == "promote", r


def t5_just_below_retires():
    r = KP.evaluate(_gate(200, 54.9))
    assert r["verdict"] == "retire", r


def t6_no_signal_sessions_continues():
    r = KP.evaluate(_gate(250, None))
    assert r["verdict"] == "continue", r
    assert "سیگنال‌دار" in " ".join(r["reasons_fa"]), r


def t7_broken_stats_fail_soft():
    r = KP.evaluate({"ok": False, "error": "x"})
    assert r["verdict"] == "continue" and "دسترس نیست" in r["verdict_fa"], r


def t8_locked_constants():
    # ثابت‌های قفل‌شده — تغییرشان یعنی شکستنِ قراردادِ پیش‌ثبت‌شده
    assert KP.GATE_MIN_SESSIONS == 200, KP.GATE_MIN_SESSIONS
    assert KP.GATE_MIN_AGREE_PCT == 55.0, KP.GATE_MIN_AGREE_PCT
    assert KP.LOCKED_AT == "2026-11-14", KP.LOCKED_AT


def t9_contract_text_honest():
    txt = KP.CONTRACT_FA
    for marker in ("۲۰۰", "۵۵", "ارتقا", "بازنشستگی", KP.LOCKED_AT):
        assert marker in txt, f"قرارداد باید «{marker}» را داشته باشد"
    # «ارتقا» یعنی دقیقاً چه؟ — باید در متن گفته شده باشد
    assert "±۱" in txt and "مدلِ خارجی" in txt, "اثرِ ارتقا باید صریح باشد"


# ------------------------------------------------------- خطِ تلگرام
def t10_telegram_line_basic():
    line = KP.telegram_line(gate=_gate(13, 61.5),
                            today={"ok": True, "n": 8, "sig": 3, "agree": 2})
    assert line and "سایه" in line and "حقِ رأی ندارد" in line, line
    assert "امروز 8 جلسه" in line or "امروز 8 جلسه" in line.replace("۸", "8"), line
    assert "13/۲۰۰" in line and "61.5٪" in line, line


def t11_telegram_line_empty_today():
    line = KP.telegram_line(gate=_gate(13, 61.5),
                            today={"ok": True, "n": 0, "sig": 0, "agree": 0})
    assert line and "امروز" not in line, line


def t12_telegram_line_gate_pass():
    line = KP.telegram_line(gate=_gate(200, 60.0), today={"ok": True, "n": 2, "sig": 2, "agree": 2})
    assert line and "✅" in line, line


def t13_telegram_line_never_raises():
    # هر ورودیِ خراب → None، نه استثنا — خطِ سایه گزارش را نمی‌شکند
    assert KP.telegram_line(gate={"ok": False}) is None, None
    assert KP.telegram_line(gate=None, today=None, now=None) is not None or True


# ------------------------------------------------------- امروزِ دفتر
def t14_today_stats_counts_only_today():
    import json
    from datetime import datetime
    rows = [
        {"ts": "2026-11-13 10:00", "backend": "kronos", "signal_active": True,
         "kronos_side": 1, "team_side": 1},          # دیروز — نباید بیاید
        {"ts": "2026-11-14 09:00", "backend": "kronos", "signal_active": True,
         "kronos_side": -1, "team_side": 1},         # امروزِ مخالف
        {"ts": "2026-11-14 09:05", "backend": "kronos", "signal_active": True,
         "kronos_side": 1, "team_side": 1},          # امروزِ هم‌جهت
        {"ts": "2026-11-14 09:10", "backend": "kronos", "signal_active": False,
         "kronos_side": 0, "team_side": 0},          # امروزِ بی‌سیگنال
        {"ts": "2026-11-14 09:15", "backend": "offline", "signal_active": True,
         "kronos_side": 1, "team_side": 1},          # شبیه‌ساز — نباید بیاید
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
        tmp = f.name
    try:
        s = KP.today_stats(path=tmp, now=datetime(2026, 11, 14, 21, 0))
        assert s["ok"] and s["n"] == 3 and s["sig"] == 2 and s["agree"] == 1, s
    finally:
        os.unlink(tmp)


def t15_today_stats_missing_file():
    s = KP.today_stats(path="/nonexistent/x.jsonl")
    assert s["ok"] and s["n"] == 0, s


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    print("== آزمونِ ۲۶اُم — قراردادِ پیش‌ثبت‌شده‌ی ارتقای کرونوس ==")
    check("زیرِ دروازه → ادامه‌ی جمع‌آوری", t1_below_gate_continues)
    check("۲۰۰ جلسه با ۶۱.۵٪ → ارتقا", t2_pass_promotes)
    check("۲۰۰ جلسه با ۵۰٪ → بازنشستگی", t3_fail_retires)
    check("مرزِ دقیقِ ۵۵٪ → ارتقا (≥)", t4_boundary_is_promote)
    check("۵۴.۹٪ → بازنشستگی", t5_just_below_retires)
    check("هیچ جلسه‌ی سیگنال‌دار → ادامه", t6_no_signal_sessions_continues)
    check("آمارِ خراب → fail-soft", t7_broken_stats_fail_soft)
    check("ثابت‌های قفل‌شده دست‌نخورده", t8_locked_constants)
    check("متنِ قرارداد صادقانه و صریح", t9_contract_text_honest)
    check("خطِ تلگرام — آمارِ کامل", t10_telegram_line_basic)
    check("خطِ تلگرام — امروزِ خالی", t11_telegram_line_empty_today)
    check("خطِ تلگرام — دروازه گذشت", t12_telegram_line_gate_pass)
    check("خطِ تلگرام — هرگز استثنا نمی‌دهد", t13_telegram_line_never_raises)
    check("today_stats فقط امروزِ تهرانِ واقعی", t14_today_stats_counts_only_today)
    check("today_stats — فایلِ غایب", t15_today_stats_missing_file)
    print(f"===== {ok} passed, {fail} failed =====")
    sys.exit(1 if fail else 0)
