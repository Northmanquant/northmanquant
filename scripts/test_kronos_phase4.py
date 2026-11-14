# -*- coding: utf-8 -*-
"""آزمونِ ۲۷اُم — فازِ چهارِ نقشه‌راه: مکانیزمِ ارتقا/بازنشستگیِ کرونوس
==========================================================================
همه‌ی آزمون‌ها قطعی و بدونِ شبکه‌اند. حکمِ قرارداد زنده از دروازه خوانده
می‌شود؛ اینجا با دیکته‌های ساختگیِ هم‌شکل، هر سه وضعیت و اثرِ رأیِ ±۱ در
کورومِ اتاق را قفل می‌کنیم — اگر کسی مکانیزم را از متنِ قرارداد جدا کند،
اینجا قرمز می‌شود.

اجرا:  python scripts/test_kronos_phase4.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from core import team_room as TR  # noqa: E402
from core import kronos_witness as KW  # noqa: E402
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


def _synth(n=340, base=100.0, drift=0.0008):
    """کندل‌های قطعی — همان مولدِ آزمونِ اتاقِ تیم/شاهد."""
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


def _gate(n: int, rate):
    """دیکته‌ی هم‌شکلِ خروجیِ gate_stats — بدونِ I/O."""
    return {"ok": True, "n_total": n,
            "real": {"n": n, "agree": round(n * (rate or 0) / 100.0) if rate is not None else 0,
                     "rate": rate},
            "stub": {"n": 0, "agree": 0, "rate": None},
            "gate_pass": bool(n >= 200 and (rate or 0.0) >= 55.0),
            "gate_fa": "", "last": None}


def _pred(side: int, agree: float = 66.0):
    """دیکتِ پیش‌بینیِ هم‌شکلِ خروجیِ شاهد — برای آزمونِ داوریِ شکاک."""
    return {"predicting": True, "side": side, "agree_pct": agree,
            "p_up": agree if side == 1 else 100 - agree,
            "p_dn": 100 - agree if side == 1 else agree,
            "p5": 10.0, "p50": 12.0, "p95": 14.0, "ret_med": 0.5,
            "last_px": 12.0, "n_paths": 32, "horizon": 24}


# ------------------------------------------------------------ وضعیتِ زنده
def t1_state_promoted():
    s = KP.state(_gate(200, 61.5))
    assert s["promoted"] is True and s["retired"] is False, s
    assert s["verdict"] == "promote", s


def t2_state_retired():
    s = KP.state(_gate(200, 50.0))
    assert s["retired"] is True and s["promoted"] is False, s


def t3_state_continue():
    s = KP.state(_gate(150, 61.5))
    assert s["promoted"] is False and s["retired"] is False, s


def t4_is_promoted_shortcut():
    assert KP.is_promoted(_gate(200, 55.0)) is True, None
    assert KP.is_promoted(_gate(200, 54.9)) is False, None
    assert KP.is_promoted({"ok": False, "error": "x"}) is False, None


# ------------------------------------------------------------ کارتِ شاهد
def t5_witness_card_promoted():
    w = KW.witness(_synth(120), 2, promoted=True)
    assert w.get("member") is True, w["role"]
    assert "مدلِ خارجی" in w["role"] and "±۱" in w["role"], w["role"]
    assert any("ارتقایافته" in m["text"] for m in w["msgs"]), [m["text"] for m in w["msgs"]]


def t6_witness_card_shadow_default():
    w = KW.witness(_synth(120), 2)
    assert w.get("member") is False, w["role"]
    assert "سایه" in w["role"], w["role"]


# ------------------------------------------------------- رأیِ ±۱ در کوروم
def t7_vote_disagree_promoted_is_hard():
    checks = KW.skeptic_kronos_check({"pred": _pred(-1)}, 1, {}, promoted=True)
    assert len(checks) == 1 and checks[0]["verdict"] == "اعتراض", checks
    assert checks[0].get("shadow") is False, checks[0]
    assert "رأیِ مدلِ خارجی" in checks[0]["reason"], checks[0]["reason"]


def t8_vote_disagree_shadow_stays_soft():
    checks = KW.skeptic_kronos_check({"pred": _pred(-1)}, 1, {}, promoted=False)
    assert len(checks) == 1 and checks[0]["verdict"] == "هشدار", checks
    assert checks[0].get("shadow") is True, checks[0]


def t9_vote_agree_promoted_is_weighted_confirm():
    checks = KW.skeptic_kronos_check({"pred": _pred(1)}, 1, {}, promoted=True)
    assert len(checks) == 1 and checks[0]["verdict"] == "تایید", checks
    assert checks[0].get("shadow") is False and "رأیِ مدلِ خارجی" in checks[0]["reason"], checks[0]


def t10_no_prediction_is_silent():
    assert KW.skeptic_kronos_check({"pred": {"predicting": False}}, 1, {}, promoted=True) == [], None
    assert KW.skeptic_kronos_check(None, 0, {}, promoted=True) == [], None


def t11_stop_outside_band_stays_warn():
    plan = {"status": "active", "stop": 20.0}   # بالاتر از باندِ ۱۴
    for promoted in (False, True):
        checks = KW.skeptic_kronos_check({"pred": _pred(1)}, 0, plan, promoted=promoted)
        assert len(checks) == 1 and checks[0]["verdict"] == "هشدار", (promoted, checks)


def t12_verdict_effect_in_room():
    # اثرِ واقعیِ رأی: طرحِ فعال + مخالفتِ ارتقایافته → حکمِ «اعتراض»؛
    # همان مخالفت در حالتِ سایه → حکمِ «هم‌نظر» (فقط هشدارِ ثبت‌شده)
    plan = {"status": "active", "stop": 12.5}   # داخلِ باند — فقط رأیِ جهت
    hard = KW.skeptic_kronos_check({"pred": _pred(-1)}, 1, plan, promoted=True)
    v = TR.team_verdict(plan, hard)
    assert v["state"] == "object" and v["n_obj"] >= 1, v
    soft = KW.skeptic_kronos_check({"pred": _pred(-1)}, 1, plan, promoted=False)
    v2 = TR.team_verdict(plan, soft)
    assert v2["state"] == "align" and v2["n_obj"] == 0, v2


# ---------------------------------------------------------------- آرشیو
def t13_archive_log_idempotent():
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "log.jsonl")
        with open(src, "w", encoding="utf-8") as f:
            for i in range(3):
                f.write(json.dumps({"i": i}) + "\n")
        dst = os.path.join(td, "archive.jsonl")
        a = KP.archive_log(dest=dst, path=src)
        assert a["ok"] and a["archived"] and a["n_rows"] == 3, a
        b = KP.archive_log(dest=dst, path=src)          # دوباره → دست نمی‌زند
        assert b["ok"] and not b["archived"] and "idempotent" in b.get("why_fa", ""), b


def t14_archive_missing_source():
    with tempfile.TemporaryDirectory() as td:
        a = KP.archive_log(dest=os.path.join(td, "a.jsonl"), path=os.path.join(td, "nope.jsonl"))
        assert not a["ok"] and not a["archived"], a


# ---------------------------------------------------- خطِ تلگرامِ حکم‌دار
def t15_line_retire():
    line = KP.telegram_line(gate=_gate(200, 50.0), today={"ok": True, "n": 0, "sig": 0, "agree": 0})
    assert line and "بازنشسته" in line and "۵۵٪" in line, line
    assert "50٪" in line, line  # دلیلِ عددی


def t16_line_promote():
    line = KP.telegram_line(gate=_gate(200, 60.0), today={"ok": True, "n": 2, "sig": 2, "agree": 2})
    assert line and "ارتقا گرفت" in line and "±۱" in line, line


def t17_line_continue_keeps_gate():
    line = KP.telegram_line(gate=_gate(18, 72.2), today={"ok": True, "n": 0, "sig": 0, "agree": 0})
    assert line and "حقِ رأی ندارد" in line and "18/۲۰۰" in line, line


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    print("== آزمونِ ۲۷اُم — فازِ چهار: مکانیزمِ ارتقا/بازنشستگی ==")
    check("وضعیتِ زنده — دروازه گذشت → عضوِ هفتم", t1_state_promoted)
    check("وضعیتِ زنده — نگذشت → بازنشسته", t2_state_retired)
    check("وضعیتِ زنده — زیرِ موعد → سایه", t3_state_continue)
    check("میان‌برِ is_promoted (مرزِ ۵۵ هم)", t4_is_promoted_shortcut)
    check("کارتِ شاهد در حالتِ ارتقا — «مدلِ خارجی»", t5_witness_card_promoted)
    check("کارتِ شاهد — پیش‌فرضِ امن یعنی سایه", t6_witness_card_shadow_default)
    check("مخالفتِ ارتقایافته = اعتراضِ سخت", t7_vote_disagree_promoted_is_hard)
    check("مخالفتِ سایه = هشدارِ ثبت‌شده", t8_vote_disagree_shadow_stays_soft)
    check("هم‌جهتیِ ارتقایافته = تاییدِ وزن‌دار", t9_vote_agree_promoted_is_weighted_confirm)
    check("بی‌پیش‌بینی = سکوت (حتی در ارتقا)", t10_no_prediction_is_silent)
    check("حدضررِ خارج از باند در هر دو حالت هشدار است", t11_stop_outside_band_stays_warn)
    check("اثرِ رأی در حکمِ اتاق: اعتراض↔هم‌نظر", t12_verdict_effect_in_room)
    check("آرشیوِ دفتر — کپی و idempotent", t13_archive_log_idempotent)
    check("آرشیو با مبدأِ غایب — fail-soft", t14_archive_missing_source)
    check("خطِ تلگرامِ روزِ بازنشستگی", t15_line_retire)
    check("خطِ تلگرامِ روزِ ارتقا", t16_line_promote)
    check("خطِ تلگرام در ادامه — دروازه نمایان", t17_line_continue_keeps_gate)
    print(f"===== {ok} passed, {fail} failed =====")
    sys.exit(1 if fail else 0)
