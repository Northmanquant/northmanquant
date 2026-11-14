# -*- coding: utf-8 -*-
"""آزمونِ ۲۵اُم — core/kronos_witness.py — شاهدِ ششم: کرونوس در حالتِ سایه
=========================================================================
همه‌ی آزمون‌ها قطعی و بدونِ شبکه‌اند: مدلِ واقعیِ کرونوس در محیطِ آزمون نصب
نیست، پس پشتیبانِ «شبیه‌سازِ آفلاین» آزمایش می‌شود و مسیرِ «مدلِ واقعی» فقط
از نظرِ fail-soft (برگشتِ صادقانه به شبیه‌ساز) چک می‌شود.

اجرا:  python scripts/test_kronos_witness.py
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


def _synth(n=340, base=100.0, drift=0.0008, vol_last=None):
    """کندل‌های قطعی (بدونِ random) — همان مولدِ آزمونِ اتاقِ تیم."""
    t = np.arange(n, dtype=float)
    close = base * (1.0 + drift * t + 0.02 * np.sin(t / 12.0))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) * (1.0 + 0.004)
    low = np.minimum(open_, close) * (1.0 - 0.004)
    vol = 1000.0 + 150.0 * np.abs(np.sin(t / 9.0))
    if vol_last:
        vol[-1] = vol_last
    ms = pd.date_range("2026-01-01", periods=n, freq="1h")
    return pd.DataFrame({
        "time": (ms.astype("int64") // 10**9) * 1000,
        "open": open_, "high": high, "low": low, "close": close, "volume": vol,
        "dt": ms,
    })


TS = "2026-11-14 12:00"
NEWS_OK = {"items": [], "ts": 0, "stale": True, "cached": False}


def t1_schema():
    d = _synth()
    w = KW.witness(d, 2)
    assert w["key"] == "kronos" and w["ok"], w.get("key")
    assert w["msgs"], "شاهد بدون پیام"
    for m in w["msgs"]:
        assert m.get("text") and m.get("why"), f"پیامِ بی‌دلیل: {m}"
    for cl in w["claims"]:
        assert cl.get("evidence"), f"ادعای بی‌مدرک: {cl}"
        assert cl.get("by") == "kronos"
    pred = w["pred"]
    assert pred["predicting"] and pred["backend"] == "offline"
    assert pred["side"] in (-1, 0, 1) and 0.0 <= pred["agree_pct"] <= 100.0
    assert pred["p5"] <= pred["p50"] <= pred["p95"] and pred["p5"] > 0
    assert pred["seed"] == 42 and pred["n_paths"] == 32 and pred["horizon"] == 24
    assert "seed=" in cl["evidence"], "تکرارپذیری باید در مدرک ثبت باشد"
    return f"side={pred['side']} · agree={pred['agree_pct']}٪ · باندِ {pred['p5']:.2f}–{pred['p95']:.2f}"


def t2_determinism():
    d = _synth()
    a = json.dumps(KW.witness(d, 4), ensure_ascii=False, sort_keys=True, default=str)
    b = json.dumps(KW.witness(d, 4), ensure_ascii=False, sort_keys=True, default=str)
    assert a == b, "دو فراخوانی با ورودی/seed یکسان خروجیِ متفاوت داد"
    return "seed ثابت → خروجیِ بیت‌به‌بیت یکسان"


def t3_stub_labeled():
    d = _synth()
    w = KW.witness(d, 2)
    joined = " ".join(m["text"] for m in w["msgs"])
    assert "شبیه‌ساز" in joined, "شبیه‌ساز باید صادقانه برچسب بخورد"
    assert w["pred"]["model"] == "NeoQuasar/Kronos-mini", w["pred"]["model"]
    assert any("سایه" in m["text"] for m in w["msgs"]), "حالتِ سایه باید صریح باشد"
    return "برچسبِ «شبیه‌ساز» + اعلامِ حالتِ سایه در پیام‌ها"


def t4_short_data():
    d = _synth(n=30)  # کمتر از MIN_CTX=60
    w = KW.witness(d, 2)
    pred = w["pred"]
    assert not pred["predicting"], "داده‌ی لاغر نباید پیش‌بینی بدهد"
    assert not w["claims"], "بدونِ پیش‌بینی، ادعا هم نیست"
    assert any("پیش‌بینیِ معتبری ندارم" in m["text"] for m in w["msgs"])
    return "۳۰ کندل → «نمی‌توانم» صادقانه، بدونِ حدس"


def t5_shadow_verdict_unchanged():
    d = _synth()
    r_on = TR.investigate(df=d, news=NEWS_OK, with_news=False, ts=TS, with_witness=True)
    r_off = TR.investigate(df=d, news=NEWS_OK, with_news=False, ts=TS, with_witness=False)
    assert r_on["ok"] and r_off["ok"]
    assert "kronos" in r_on["agents"], "شاهد در جلسه نیست"
    assert "kronos" not in r_off["agents"], "شاهدِ خاموش نباید در جلسه باشد"
    v_on, v_off = r_on["verdict"], r_off["verdict"]
    assert v_on["state"] == v_off["state"], f"حالتِ سایه حکم را عوض کرد: {v_on['state']}≠{v_off['state']}"
    assert v_on["n_obj"] == v_off["n_obj"], "شاهد نباید اعتراضِ سخت بسازد"
    on_obj = [c for c in r_on["skeptic"]["checks"] if c["verdict"] == "اعتراض"]
    off_obj = [c for c in r_off["skeptic"]["checks"] if c["verdict"] == "اعتراض"]
    assert len(on_obj) == len(off_obj), "تعدادِ اعتراض‌ها باید یکسان بماند"
    return f"حکمِ هر دو = {v_on['state']} · اعتراض‌ها = {v_on['n_obj']}"


def t6_skeptic_shadow_only():
    d = TR.nq.add_indicators(_synth())
    plan = {"status": "active", "direction": "لانگ (خرید) 🟢", "entry": 101.0, "stop": 99.0,
            "targets": [(104.0, "x")], "rr": 1.5, "confidence": 60, "qc": {}}
    w_contra = {"pred": {"predicting": True, "side": -1, "agree_pct": 58.0, "p5": 98.0,
                         "p50": 100.0, "p95": 102.0, "n_paths": 32, "horizon": 24}}
    w_align = {**w_contra, "pred": {**w_contra["pred"], "side": 1}}
    checks_c = KW.skeptic_kronos_check(w_contra, 1, plan)
    checks_a = KW.skeptic_kronos_check(w_align, 1, plan)
    assert all(c["verdict"] != "اعتراض" for c in checks_c + checks_a), "شاهدِ سایه حقِ وتو ندارد"
    assert any(c["verdict"] == "هشدار" and c.get("shadow") for c in checks_c), checks_c
    assert any(c["verdict"] == "تایید" and c.get("shadow") for c in checks_a), checks_a
    # حدضررِ خارج از باند (۹۹ در باندِ ۱۰۳–۱۰۷) → هشدارِ باند
    w_band = {"pred": {"predicting": True, "side": 1, "agree_pct": 60.0,
                       "p5": 103.0, "p50": 105.0, "p95": 107.0}}
    checks_b = KW.skeptic_kronos_check(w_band, 1, plan)
    assert any("حدضرر" in c["about"] and c["verdict"] == "هشدار" for c in checks_b), checks_b
    # داوری‌های سایه به‌تنهایی هیچ‌وقت حکم را به «اعتراض» نمی‌کِشانند
    vd = TR.team_verdict(plan, checks_c)
    assert vd["state"] == "align", f"هشدارِ سایه حکم را عوض کرد: {vd['state']}"
    # شاهدِ غیرِ پیش‌بینی‌گر → شکاک ساکت می‌ماند
    assert KW.skeptic_kronos_check({"pred": {"predicting": False}}, 1, plan) == []
    return "مخالفت=هشدار · هم‌جهت=تایید · باند=هشدار · هیچ‌وقت وتو نیست"


def t7_online_fallback():
    d = _synth()
    w = KW.witness(d, 2, backend="kronos")  # KRONOS_REPO خالی → بارگیریِ واقعی ممکن نیست
    assert w["pred"]["backend"] == "offline", "باید صادقانه به شبیه‌ساز برگردد"
    note = str(w["pred"].get("note_fa") or "") + " ".join(m["text"] for m in w["msgs"])
    assert "شکست" in note, f"علتِ برگشت باید صریح باشد: {note[:120]}"
    assert "شبیه‌ساز" in note, "برچسبِ شبیه‌ساز باید در مسیرِ برگشت هم باشد"
    return "بدونِ مخزن → برگشتِ صادقانه به شبیه‌ساز با ذکرِ علت"


def t8_log_and_gate():
    tmp = os.path.join(tempfile.mkdtemp(), "kronos_log.jsonl")
    g0 = KW.gate_stats(path=tmp)
    assert g0["ok"] and g0["n_total"] == 0 and not g0["gate_pass"], g0
    assert g0["real"]["rate"] is None and g0["real"]["n"] == 0, "دفترِ خالی باید صادقانه صفر باشد"

    def room(team, kron, backend="offline", active=True):
        plan = {"status": "active" if active else "wait"}
        return {"ok": True, "ts": TS, "symbol": "BTC-USDT", "interval": "1hour",
                "exchange": "OKX", "plan": plan, "verdict": {"state": "align"},
                "agents": {"chart": {"claims": [{"by": "chart", "side": team}]},
                           "kronos": {"pred": {"predicting": True, "side": kron,
                                               "agree_pct": 60.0, "backend": backend,
                                               "model": "NeoQuasar/Kronos-mini", "seed": 42}}}}

    for r in (room(1, 1), room(1, -1), room(-1, -1), room(0, 1, active=False), room(1, 1, backend="kronos")):
        res = KW.log_session(r, path=tmp)
        assert res["logged"], res.get("error")
    # خطِ خرابِ وسطِ دفتر — دفتر نباید بشکند
    with open(tmp, "a", encoding="utf-8") as f:
        f.write("garbage{{{\n")
    g = KW.gate_stats(path=tmp)
    assert g["n_total"] == 5, f"خطِ خراب باید رد شود: {g['n_total']}"
    assert g["stub"] == {"n": 3, "agree": 2, "rate": 66.7}, g["stub"]
    assert g["real"] == {"n": 1, "agree": 1, "rate": 100.0}, g["real"]
    assert not g["gate_pass"], "با ۱ جلسه دروازه نباید بگذرد"
    assert "۲۰۰" in g["gate_fa"], g["gate_fa"]
    assert g["last"]["symbol"] == "BTC-USDT" and g["last"]["backend"] == "kronos"
    return "۵ جلسه · شبیه‌ساز ۲/۳=۶۶.۷٪ · مدلِ واقعی جدا · خطِ خراب رد شد"


def t9_ctx_clamp():
    d = _synth(n=700)
    pred = KW.witness(d, 2)["pred"]
    assert pred["predicting"], "داده‌ی بلند باید پیش‌بینی بدهد"
    assert pred["ctx_len"] <= KW.STUB_CTX + 1, f"زمینه باید کِلَمپ شود: {pred['ctx_len']}"
    return f"۷۰۰ کندل داده شد · زمینهِ مصرفی = {pred['ctx_len']} کندل"


def t10_env_off():
    d = _synth()
    old = os.environ.get("KRONOS_WITNESS")
    try:
        os.environ["KRONOS_WITNESS"] = "off"
        r = TR.investigate(df=d, news=NEWS_OK, with_news=False, ts=TS, with_witness=True)
        assert "kronos" not in r["agents"], "env=off باید شاهد را خاموش کند"
        os.environ["KRONOS_WITNESS"] = "on"
        r2 = TR.investigate(df=d, news=NEWS_OK, with_news=False, ts=TS, with_witness=True)
        assert "kronos" in r2["agents"]
    finally:
        if old is None:
            os.environ.pop("KRONOS_WITNESS", None)
        else:
            os.environ["KRONOS_WITNESS"] = old
    return "KRONOS_WITNESS=off → جلسه بدونِ شاهد؛ on → با شاهد"


def t11_log_failsoft():
    res = KW.log_session({}, path=os.path.join(tempfile.mkdtemp(), "x.jsonl"))
    assert not res["logged"] and res.get("error"), "جلسه‌ی خالی نباید ثبت شود"
    d = _synth()
    r = TR.investigate(df=d, news=NEWS_OK, with_news=False, ts=TS, with_witness=True)
    res2 = KW.log_session(r, path=os.path.join(tempfile.mkdtemp(), "y.jsonl"))
    assert res2["logged"], res2.get("error")
    e = res2["entry"]
    assert e["symbol"] == r["symbol"] and e["ts"] == r["ts"]
    assert e["signal_active"] == (r["plan"]["status"] == "active")
    assert e["backend"] == "offline" and e["seed"] == 42
    return f"ثبتِ جلسه‌ی واقعی · team_side={e['team_side']} · kronos_side={e['kronos_side']}"


if __name__ == "__main__":
    print("== شاهدِ کرونوس (فازِ یک — حالتِ سایه) ==")
    check("ساختارِ خروجی + باندِ چارکی + مدرکِ تکرارپذیری", t1_schema)
    check("قطعیت با seed ثابت", t2_determinism)
    check("برچسبِ صادقانه‌ی شبیه‌ساز + حالتِ سایه", t3_stub_labeled)
    check("داده‌ی لاغر → «نمی‌توانم» بدونِ حدس", t4_short_data)
    check("حالتِ سایه: حکمِ تیم دست‌نخورده", t5_shadow_verdict_unchanged)
    check("شکاک فقط هشدار/تایید برای شاهد — وتو ممنوع", t6_skeptic_shadow_only)
    check("شکستِ بارگیریِ مدلِ واقعی → برگشتِ صادقانه", t7_online_fallback)
    check("دفترِ دروازه‌ی ۲۰۰ جلسه‌ای + آمارِ جداگانه", t8_log_and_gate)
    check("کِلَمپِ طولِ زمینه", t9_ctx_clamp)
    check("کلیدِ env برای خاموشیِ شاهد", t10_env_off)
    check("ثبتِ fail-soft جلسات", t11_log_failsoft)
    print(f"===== {ok} passed, {fail} failed =====")
    raise SystemExit(1 if fail else 0)
