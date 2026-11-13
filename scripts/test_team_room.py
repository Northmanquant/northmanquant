# -*- coding: utf-8 -*-
"""آزمون‌های core/team_room.py — اتاقِ تیمِ تحلیل (بدونِ شبکه، کاملاً قطعی)
اجرا:  python scripts/test_team_room.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from core import team_room as TR  # noqa: E402

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


def _synth(n=340, base=100.0, drift=0.0008, wash_last=False, vol_last=None):
    """کندل‌های قطعی (بدون random): روندِ صعودیِ ملایم + موجِ سینوسی."""
    t = np.arange(n, dtype=float)
    close = base * (1.0 + drift * t + 0.02 * np.sin(t / 12.0))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) * (1.0 + 0.004)
    low = np.minimum(open_, close) * (1.0 - 0.004)
    vol = 1000.0 + 150.0 * np.abs(np.sin(t / 9.0))
    if wash_last:  # آخرین کندل: حجمِ عظیم + رنجِ تقریباً صفر = churn
        vol[-1] = vol_last if vol_last else 12000.0
        mid = close[-1]
        high[-1], low[-1] = mid * (1.0 + 0.0002), mid * (1.0 - 0.0002)
    ms = pd.date_range("2026-01-01", periods=n, freq="1h")
    return pd.DataFrame({
        "time": (ms.astype("int64") // 10**9) * 1000,
        "open": open_, "high": high, "low": low, "close": close, "volume": vol,
        "dt": ms,
    })


TS = "2026-11-11 12:00"
NEWS_OK = {"items": [
    {"source": "Decrypt", "title": "Bitcoin ETF Approval Sparks Institutional Inflow",
     "link": "https://x/1", "ts": "2026-11-11T09:00:00Z", "symbols": ["BTC"]},
    {"source": "Cointelegraph", "title": "Ethereum Upgrade Boosts Staking Gains",
     "link": "https://x/2", "ts": "2026-11-11T08:00:00Z", "symbols": ["ETH"]},
], "ts": 0, "stale": False, "cached": False}
NEWS_BEAR = {"items": [
    {"source": "Decrypt", "title": "Major Exchange Hack: Bitcoin Stolen in Security Breach",
     "link": "https://x/3", "ts": "2026-11-11T10:00:00Z", "symbols": ["BTC"]},
], "ts": 0, "stale": False, "cached": False}


def t1_structure():
    d = _synth()
    room = TR.investigate(df=d, news=NEWS_OK, with_news=True, ts=TS)
    assert room.get("ok"), f"ok=False: {room.get('error')}"
    ag = room.get("agents") or {}
    assert set(ag.keys()) >= {"news", "watchdog", "chart", "risk"}, ag.keys()
    for k in ("news", "watchdog", "chart", "risk"):
        assert ag[k]["msgs"], f"{k}: بدون پیام"
        for m in ag[k]["msgs"]:
            assert m.get("text") and m.get("why"), f"{k}: پیامِ بی‌دلیل"
    sk = room.get("skeptic") or {}
    assert sk.get("checks"), "شکاک بدون داوری"
    assert room["verdict"]["state"] in ("align", "object", "wait")
    assert room["price"] > 0
    return "5 عامل + داوری + حکم"


def t2_plan_has_qc():
    d = _synth()
    room = TR.investigate(df=d, news=NEWS_OK, with_news=False, ts=TS)
    plan = room["plan"]
    qc = plan.get("qc") or {}
    assert qc.get("stamp"), "بدون مُهر QC"
    assert plan.get("status") in ("active", "wait")
    return f"status={plan['status']} · stamp={qc['stamp'][:34]}…"


def t3_wash_detected():
    d = _synth(wash_last=True)
    room = TR.investigate(df=d, news=NEWS_OK, with_news=False, ts=TS)
    wd = room["agents"]["watchdog"]
    assert wd.get("flags"), "چurn تشخیص داده نشد"
    assert any(f["level"] == "red" for f in wd["flags"]), "چurn نباید زرد باشد"
    assert any("اعتراض" in c["verdict"] for c in room["skeptic"]["checks"]), "شکاک به churn اعتراض نکرد"
    vd = room["verdict"]
    assert vd["state"] in ("object", "wait"), f"حکم={vd['state']}"
    if vd["state"] == "wait":
        assert "اعتراض" in vd["text"], "حکمِ انتظار باید اعتراض‌های جدا را هم ذکر کند"
    return f"red flag + اعتراضِ شکاک + حکمِ {vd['state']}"


def t4_skeptic_vs_bearish_news():
    # شکاک مستقیم — مستقل از اینکه موتور سیگنال بدهد یا نه
    d = TR.nq.add_indicators(_synth())
    plan = {"status": "active", "direction": "لانگ (خرید) 🟢", "entry": 101.0, "stop": 99.0,
            "targets": [(104.0, "x")], "rr": 1.5, "confidence": 60, "score": 0.3,
            "qc": {"setup_tested": True, "stats": {"n": 40, "win1": 55}}}
    claims = [{"by": "chart", "side": 1, "claim": "لانگ", "evidence": "test"},
              {"by": "news", "side": -1, "claim": "Exchange Hack", "evidence": "Decrypt · 2026"}]
    checks = TR.skeptic_checks(claims, d, plan)
    obj = [c for c in checks if c["verdict"] == "اعتراض" and c["target"] == "خبرنگار"]
    assert obj, f"به خبرِ مخالف اعتراض نشد: {checks}"
    return obj[0]["reason"][:44] + "…"


def t5_skeptic_vs_ema200():
    d = TR.nq.add_indicators(_synth(drift=-0.0015))  # روندِ نزولی → زیرِ EMA200
    plan = {"status": "active", "direction": "لانگ (خرید) 🟢", "entry": 90.0, "stop": 89.0,
            "targets": [(92.0, "x")], "rr": 2.0, "confidence": 55, "score": 0.3,
            "qc": {"setup_tested": False}}
    claims = [{"by": "chart", "side": 1, "claim": "لانگ", "evidence": "test"}]
    checks = TR.skeptic_checks(claims, d, plan)
    assert any(c["verdict"] == "اعتراض" and "EMA200" in c["reason"] for c in checks), checks
    return "لانگِ زیرِ روندِ کلان → اعتراض"


def t6_read_title():
    assert TR.read_title("Bitcoin ETF Approval Sparks Rally") == 1
    assert TR.read_title("Exchange Hack: BTC Breach") == -1
    assert TR.read_title("Weekly Market Wrap: Quiet Session") == 0
    assert TR.base_of("BTC-USDT") == "BTC" and TR.base_of("ETH/USDT") == "ETH"
    return "تیترهای مثبت/منفی/خنثی + base_of"


def t7_fail_soft():
    d = _synth(n=12)  # خیلی کوتاه برای EMA200 و QC
    room = TR.investigate(df=d, news=NEWS_OK, with_news=False, ts=TS)
    assert room.get("ok") or room.get("error"), "نه ok نه error"
    if room.get("ok"):
        assert room["plan"]["status"] == "wait", "داده‌ی ناقص باید wait شود"
    return "کندلِ ناقص → wait/خطای شفاف، بدونِ کرش"


def t8_determinism():
    d = _synth()
    r1 = TR.investigate(df=d, news=NEWS_OK, with_news=True, ts=TS)
    r2 = TR.investigate(df=d, news=NEWS_OK, with_news=True, ts=TS)
    a = json.dumps(r1, ensure_ascii=False, sort_keys=True, default=str)
    b = json.dumps(r2, ensure_ascii=False, sort_keys=True, default=str)
    assert a == b, "خروجیِ دو جلسه با ورودیِ یکسان فرق کرد"
    return "دو جلسه‌ی یکسان = خروجیِ یکسان (بدون LLM، بدون شانس)"


def t9_every_claim_has_evidence():
    d = _synth()
    room = TR.investigate(df=d, news=NEWS_OK, with_news=True, ts=TS)
    for a in room["agents"].values():
        for cl in a.get("claims") or []:
            assert cl.get("evidence"), f"{a['key']}: ادعای بی‌مدرک: {cl}"
    for c in room["skeptic"]["checks"]:
        assert c.get("reason"), "داوریِ بی‌دلیل"
    return "همه‌ی ادعاها مدرک دارند"


# ------------------------------------------------- عاملِ پنجم: مدیرِ ریسک
def t10_risk_math():
    d = TR.nq.add_indicators(_synth())
    plan = {"status": "active", "direction": "لانگ (خرید) 🟢", "entry": 101.0, "stop": 99.0,
            "targets": [(104.0, "x")], "rr": 1.5, "confidence": 60,
            "qc": {"setup_tested": True, "stats": {"n": 40, "win1": 55}}}
    a = TR.risk_agent(d, 2, plan, capital=1000.0, risk_pct=1.0)
    # فاصله‌ی حدضرر = 2.0 → ریسکِ 10$ → اندازه = 5.0 واحد
    cl = next(c for c in a["claims"] if c["by"] == "risk")
    assert abs(cl["size"] - 5.0) < 1e-9, cl
    assert cl["capital"] == 1000.0 and cl["risk_pct"] == 1.0
    assert cl.get("fee_drag_r") is not None and cl["fee_drag_r"] > 0
    joined = " ".join(m["text"] for m in a["msgs"])
    assert "5.0000" in joined and "10.00" in joined, joined[:150]
    return "size=5.0000 واحد · ضررِ حداکثریِ 10.00$ (۱٪)"


def t11_risk_wait():
    d = TR.nq.add_indicators(_synth())
    plan = {"status": "wait", "direction": "⏸ انتظار", "entry": None, "stop": None}
    a = TR.risk_agent(d, 2, plan, capital=500.0, risk_pct=2.0)
    assert not [c for c in a["claims"] if c.get("size")], "در انتظار نباید اندازه صادر شود"
    assert any("پوزیشنی برای اندازه‌دادن نیست" in m["text"] for m in a["msgs"])
    assert any("10.00" in m["text"] for m in a["msgs"]), "قاعده‌ی ۲٪ از 500 باید در پیام باشد"
    return "بدون سیگنال → بدون اندازه (صادقانه)"


def t12_skeptic_risk():
    d = TR.nq.add_indicators(_synth())
    plan = {"status": "active", "direction": "لانگ (خرید) 🟢", "entry": 101.0, "stop": 99.0,
            "targets": [(104.0, "x")], "rr": 1.5, "confidence": 60, "score": 0.3,
            "qc": {"setup_tested": False}}
    base = {"by": "risk", "side": 0, "claim": "اندازه 5", "evidence": "f",
            "capital": 1000.0, "risk_pct": 1.0, "size": 5.0, "fee_drag_r": 0.10}
    claims = [{"by": "chart", "side": 1, "claim": "لانگ", "evidence": "t"}, dict(base)]
    checks = TR.skeptic_checks(claims, d, plan)
    assert any(c["verdict"] == "تایید" and c["target"] == "مدیرِ ریسک" for c in checks), checks
    # ریاضیاتِ خراب (اندازه ×1.5) → اعتراض
    checks2 = TR.skeptic_checks([claims[0], {**base, "size": 7.5}], d, plan)
    assert any(c["verdict"] == "اعتراض" and c["target"] == "مدیرِ ریسک"
               and "جور درنمی" in c["reason"] for c in checks2), checks2
    # ریسکِ ۵٪ → اعتراضِ «جاهلانه»
    checks3 = TR.skeptic_checks([claims[0], {**base, "risk_pct": 5.0, "size": 25.0}], d, plan)
    assert any(c["verdict"] == "اعتراض" and "سرمایه" in c["reason"] for c in checks3), checks3
    return "ریاضیِ درست=تایید · ریاضیِ خراب=اعتراض · ۵٪=اعتراض"


def t13_zero_capital():
    d = TR.nq.add_indicators(_synth())
    plan = {"status": "active", "direction": "لانگ", "entry": 101.0, "stop": 99.0,
            "targets": [(104.0, "x")], "rr": 1.5, "confidence": 60, "qc": {}}
    a = TR.risk_agent(d, 2, plan, capital=0.0, risk_pct=1.0)
    assert not [c for c in a["claims"] if c.get("size")], "سرمایه‌ی صفر نباید اندازه بدهد"
    assert any("سرمایه‌ای وارد نشده" in m["text"] for m in a["msgs"])
    return "سرمایه‌ی صفر → حدس نمی‌زند"


if __name__ == "__main__":
    print("== اتاقِ تیمِ تحلیل ==")
    check("structure (5 عامل، پیامِ بی‌دلیل ممنوع)", t1_structure)
    check("طرحِ چارت با مُهر QC", t2_plan_has_qc)
    check("تشخیصِ churn + اعتراضِ شکاک", t3_wash_detected)
    check("شکاک در برابر خبرِ مخالف", t4_skeptic_vs_bearish_news)
    check("شکاک در برابر لانگِ زیرِ EMA200", t5_skeptic_vs_ema200)
    check("خوانشِ تیتر + base_of", t6_read_title)
    check("fail-soft با داده‌ی ناقص", t7_fail_soft)
    check("قطعیتِ خروجی", t8_determinism)
    check("هر ادعا مدرک دارد", t9_every_claim_has_evidence)
    check("مدیرِ ریسک: ریاضیاتِ اندازه‌ی پوزیشن", t10_risk_math)
    check("مدیرِ ریسک: بدون سیگنال، بدون اندازه", t11_risk_wait)
    check("شکاک در برابر مدیرِ ریسک", t12_skeptic_risk)
    check("مدیرِ ریسک: سرمایه‌ی صفر", t13_zero_capital)
    print(f"===== {ok} passed, {fail} failed =====")
    raise SystemExit(1 if fail else 0)
