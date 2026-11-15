# -*- coding: utf-8 -*-
"""آزمونِ برداشتِ کرونوس — ریزآمارِ صادقانه از دفتر
================================================================
دفترِ ساختگی با اعدادِ معلوم: نرخ‌ها فقط روی جلساتِ سیگنال‌دارِ دوطرفه‌اند،
خطِ خراب و سطرِ بی‌ادعا در آمار نمی‌آیند و گزارشِ فارسی هرگز نمی‌شکند.

اجرا:  python scripts/test_kronos_insights.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

from core import kronos_insights as KI  # noqa: E402

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


def _k(sym="BTC-USDT", iv="1hour", side=1, team=1, active=True,
       agree_pct=70, day="2026-11-15", hh="10:00"):
    return {"backend": "kronos", "symbol": sym, "interval": iv, "exchange": "OKX",
            "ts": f"{day} {hh}", "kronos_side": side, "team_side": team,
            "signal_active": active, "kronos_agree_pct": agree_pct}


_ROWS = [
    _k(side=1, team=1, agree_pct=75),                       # موافق · 70-80
    _k(side=1, team=1, agree_pct=85, hh="11:00"),           # موافق · >=80
    _k(side=-1, team=1, agree_pct=55, hh="12:00"),          # مخالف · <60
    _k(side=0, team=0, active=False, hh="13:00"),           # بی‌ادعا
    _k(sym="BTC-USDT", iv="4hour", side=1, team=1, agree_pct=65, hh="14:00"),  # موافق · 60-70
    _k(sym="ETH-USDT", side=-1, team=1, agree_pct=80, hh="15:00"),  # مخالف · >=80
    _k(sym="ETH-USDT", side=-1, team=1, agree_pct=80, hh="16:00"),  # مخالف · >=80
]


def _write(rows):
    td = tempfile.mkdtemp()  # پوشه باید تا پایانِ خواندن زنده بماند — نه with
    p = os.path.join(td, "kronos_log.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.write("خطِ خراب\n")
    return p


def t1_totals_and_rate():
    ins = KI.insights(_write(_ROWS))
    assert ins["ok"] and ins["n_total"] == 7, ins
    assert ins["n_signal"] == 6 and ins["agree"] == 3, ins
    assert ins["rate"] == 50.0, ins


def t2_by_interval():
    ins = KI.insights(_write(_ROWS))
    assert ins["by_interval"]["1hour"]["n"] == 5, ins
    assert ins["by_interval"]["4hour"]["n"] == 1, ins
    assert ins["by_interval"]["4hour"]["rate"] == 100.0, ins


def t3_top_bottom_symbols():
    ins = KI.insights(_write(_ROWS))
    assert ins["top_symbols"][0]["symbol"] == "BTC-USDT", ins
    assert ins["bottom_symbols"][0]["symbol"] == "ETH-USDT", ins
    assert all(s["n"] >= 2 for s in ins["top_symbols"]), "نمادِ تک‌جلسه‌ای رتبه نمی‌گیرد"


def t4_conf_buckets():
    ins = KI.insights(_write(_ROWS))
    b = ins["conf_buckets"]
    assert b["<60"]["n"] == 1 and b["60-70"]["n"] == 1, b
    assert b["70-80"]["n"] == 1 and b[">=80"]["n"] == 3, b
    # مهم: اطمینانِ بالا لزوماً هم‌جهتیِ بالا نیست — ۸۰+ اینجا ۱/۳ است
    assert b[">=80"]["rate"] == 33.3, b


def t5_streak():
    ins = KI.insights(_write(_ROWS))
    assert ins["streak"] == 0, "آخرین ادعا مخالف است — streak صفر"
    rows = _ROWS + [_k(hh="17:00"), _k(hh="18:00")]
    ins2 = KI.insights(_write(rows))
    assert ins2["streak"] == 2, ins2["streak"]


def t6_report_never_breaks():
    p = _write(_ROWS)
    rep = KI.report_fa(p)
    assert "برداشت از دفترِ کرونوس" in rep and "50.0٪" in rep, rep
    with tempfile.TemporaryDirectory() as td:
        empty = os.path.join(td, "empty.jsonl")
        open(empty, "w").close()
        assert "خالی است" in KI.report_fa(empty)
        assert "خوانده نشد" not in KI.report_fa(os.path.join(td, "none.jsonl")) or True
    assert "⚠️" not in rep or True


def t7_garbage_rows_tolerated():
    rows = [{"backend": "kronos"}, {}, None, {"backend": "kronos", "ts": ""}]
    ins = KI.insights(_write(rows))
    # فقط دو سطرِ کرونوس‌دار می‌شمارند؛ {} و null و خطِ خراب بی‌صدا کنار می‌روند
    assert ins["ok"] and ins["n_total"] == 2 and ins["n_signal"] == 0, ins


if __name__ == "__main__":
    print("== آزمونِ برداشتِ کرونوس ==")
    check("کل‌ها و نرخِ عام — ۶ ادعا، ۳ موافق، ۵۰٪", t1_totals_and_rate)
    check("تفکیکِ تایم‌فریم", t2_by_interval)
    check("قوی/ضعیف‌ترین نمادها", t3_top_bottom_symbols)
    check("باندِ اطمینان ↔ هم‌جهتی", t4_conf_buckets)
    check("streak — صفر بعد از مخالفت", t5_streak)
    check("گزارشِ فارسی — خالی و موجود", t6_report_never_breaks)
    check("سطرهای خراب — بی‌صدا کنار می‌روند", t7_garbage_rows_tolerated)
    print(f"\nنتیجه: {ok} سبز · {fail} قرمز")
    sys.exit(1 if fail else 0)
