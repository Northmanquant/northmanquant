# -*- coding: utf-8 -*-
"""آزمونِ موتورِ نبیه — پیش‌بینیِ قطعی + دفترِ سایه + دروازه
================================================================
همه‌چیز بدونِ شبکه و با کندل‌های ساختگیِ قطعی است: روندِ صعودی/نزولی باید
ادعای جهت بدهد، دفتر append-only بماند و دروازه با همان قواعدِ صداقتِ
کرونوس بشمارد (بی‌ادعا ≠ مخالفت؛ فقط ادعای جهت‌دارِ دوطرفه).

اجرا:  python scripts/test_nabigha_engine.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from core import nabigha_engine as NE  # noqa: E402

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


def _synth(n=160, base=100.0, drift=0.002, sine=0.02):
    """کندل‌های قطعی — رشدِ مرکب (گامِ ثابت) تا شکستِ کانال قطعی شود."""
    t = np.arange(n, dtype=float)
    close = base * (1.0 + drift) ** t * (1.0 + sine * np.sin(t / 12.0))
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


# ---- پیش‌بینی -------------------------------------------------------------

def t1_determinism():
    a = NE.predict(_synth())
    b = NE.predict(_synth())
    assert a == b, "دو اجرای یکسان باید خروجیِ یکسان بدهند"


def t2_uptrend_claims_up():
    p = NE.predict(_synth(drift=0.006, sine=0.0))
    assert p.get("ok") and p.get("side") == 1, p
    talks = {s["name"]: s["vote"] for s in p["signals"]}
    assert talks["ema_trend"] == 1 and talks["breakout"] == 1, talks


def t3_downtrend_claims_down():
    p = NE.predict(_synth(drift=-0.006, sine=0.0))
    assert p.get("ok") and p.get("side") == -1, p


def t4_confidence_bounds():
    for drift in (0.006, -0.006):
        p = NE.predict(_synth(drift=drift, sine=0.0))
        p = NE.predict(_synth(drift=drift))
        conf = p.get("confidence_pct")
        assert isinstance(conf, int) and 0 <= conf <= 100, (drift, conf)
        assert isinstance(p.get("score"), float), p


def t5_output_shape():
    p = NE.predict(_synth())
    assert len(p.get("signals") or []) == 5, p
    assert all(s.get("fa") and s.get("weight", 0) > 0 for s in p["signals"]), p
    assert "نبیه" in (p.get("note_fa") or ""), p


def t6_short_data_no_claim():
    p = NE.predict(_synth(n=30))
    assert not p.get("ok") and p.get("error"), p


def t7_garbage_never_raises():
    for bad in (None, pd.DataFrame(), pd.DataFrame({"close": [1, 2]})):
        p = NE.predict(bad)
        assert p.get("ok") is False, p


# ---- دفترِ سایه + دروازه --------------------------------------------------

def _entry(sym="BTC-USDT", s=1, team=1, active=True):
    return {"backend": "nabigha", "symbol": sym, "interval": "1hour",
            "exchange": "OKX", "ts": "2026-11-15 10:00", "price": 100.0,
            "nabigha_side": s, "team_side": team, "signal_active": active}


def t8_ledger_and_gate_math():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "nabigha_log.jsonl")
        for s, t in ((1, 1), (1, 1), (-1, 1)):  # دو موافق، یک مخالف
            assert NE.log_pred("BTC-USDT", "1hour", "OKX", 100.0,
                               {"ok": True, "side": s, "confidence_pct": 70, "score": 2.0,
                                "note_fa": "آزمون"},
                               team_side=t, signal_active=True, path=p)["logged"]
        # سطرِ بی‌ادعا و خطِ خراب — نباید در آمار بیایند
        NE.log_pred("ETH-USDT", "1hour", "OKX", 50.0, {"ok": True, "side": 0},
                    team_side=0, signal_active=False, path=p)
        with open(p, "a", encoding="utf-8") as f:
            f.write("خطِ خراب\n")
        g = NE.gate_stats(p)
        assert g["ok"] and g["n_total"] == 4, g  # سه ادعا + یک بی‌ادعا (+ خطِ خرابِ دور ریخته)
        assert g["n_signal"] == 3 and g["agree"] == 2 and g["rate"] == 66.7, g
        assert g["gate_pass"] is False, g


def t9_gate_pass_at_scale():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "nabigha_log.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            for i in range(199):
                f.write(json.dumps(_entry()) + "\n")
        assert NE.gate_stats(p)["gate_pass"] is False
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(_entry()) + "\n")
        g = NE.gate_stats(p)
        assert g["gate_pass"] is True and g["n_signal"] == 200 and g["rate"] == 100.0, g


def t10_log_pred_fail_soft():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "deep", "dir", "nabigha_log.jsonl")
        res = NE.log_pred("BTC-USDT", "1hour", "OKX", 100.0, {"ok": False, "error": "x"}, path=p)
        assert res.get("logged"), res
        e = json.loads(open(p, encoding="utf-8").read().strip())
        assert e["nabigha_side"] is None, e  # بی‌ادعا ثبت می‌شود، در آمار نمی‌آید


if __name__ == "__main__":
    print("== آزمونِ موتورِ نبیه ==")
    check("قطعی بودن — دو اجرا یک خروجی", t1_determinism)
    check("روندِ صعودی → ادعای ↑ با روند و شکست", t2_uptrend_claims_up)
    check("روندِ نزولی → ادعای ↓", t3_downtrend_claims_down)
    check("اطمینان در باندِ ۰–۱۰۰", t4_confidence_bounds)
    check("شکلِ خروجی — ۵ سیگنالِ فارسی + یادداشت", t5_output_shape)
    check("کندلِ ناکافی → بی‌ادعا با خطا", t6_short_data_no_claim)
    check("ورودیِ خراب → هرگز exception نمی‌دهد", t7_garbage_never_raises)
    check("دفتر و دروازه — نرخِ ۶۶٫۷٪ روی سه ادعا", t8_ledger_and_gate_math)
    check("دروازه در ۲۰۰ جلسه — گذرِ کامل", t9_gate_pass_at_scale)
    check("ثبتِ fail-soft — پوشه‌ی تازه و بی‌ادعا", t10_log_pred_fail_soft)
    print(f"\nنتیجه: {ok} سبز · {fail} قرمز")
    sys.exit(1 if fail else 0)
