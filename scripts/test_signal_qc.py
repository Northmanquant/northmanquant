# -*- coding: utf-8 -*-
"""
Tests for the Signal QC gate (core/signal_qc.py) and its wiring into app_base.setup_plan.

Usage (from the repository root):
    python scripts/test_signal_qc.py

No network — everything runs on deterministic synthetic candles and hand-crafted plans.
Exits non-zero if any test fails.
"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from core import signal_qc as QC  # noqa: E402

ok, fail = 0, 0


def check(name, fn):
    global ok, fail
    try:
        fn()
        print(f"  PASS {name}")
        ok += 1
    except Exception as e:
        print(f"  FAIL {name}: {type(e).__name__}: {e}")
        traceback.print_exc(limit=3)
        fail += 1


# ---------------------------------------------------------------- fixtures
def synth_candles(n: int = 600, seed: int = 7, start: float = 100.0) -> pd.DataFrame:
    """Deterministic OHLCV with regimes: drift up → range → drift down."""
    rng = np.random.default_rng(seed)
    t0, step = 1_700_000_000, 3600
    rows, p = [], start
    for i in range(n):
        drift = 0.0009 if i < n // 3 else (-0.0007 if i > 2 * n // 3 else 0.0)
        o = p
        p = max(1.0, p * (1 + drift + rng.normal(0, 0.004)))
        c = p
        hi = max(o, c) * (1 + abs(rng.normal(0, 0.0015)))
        lo = min(o, c) * (1 - abs(rng.normal(0, 0.0015)))
        v = float(abs(rng.normal(1000, 200)))
        rows.append([t0 + i * step, o, hi, lo, c, v])
    df = pd.DataFrame(rows, columns=["dt", "open", "high", "low", "close", "volume"])
    df["dt"] = pd.to_datetime(df["dt"], unit="s", utc=True)
    return df


def healthy_indicators() -> pd.DataFrame:
    from app_base import add_indicators
    return add_indicators(synth_candles())


def valid_active_plan() -> dict:
    """A hand-crafted, fully valid active plan — must pass QC untouched."""
    return {"status": "active", "direction": "لانگ (خرید) 🟢", "entry": 100.0, "stop": 98.0,
            "targets": [(102.0, 1.0), (104.0, 2.0), (106.0, 3.0)], "rr": 1.0, "confidence": 55,
            "atr": 1.0, "risk_pct": 2.0, "mode": "pullback", "mode_fa": "پولبک در روند",
            "stats": {"pullback": {"mode": "pullback", "n": 12, "win1": 55.0, "exp2": 0.35,
                                   "total2": 4.2, "longs": 8, "shorts": 4},
                      "fade": {"mode": "fade", "n": 3, "win1": 30.0, "exp2": -0.1,
                               "total2": -0.3, "longs": 2, "shorts": 1}},
            "why": "تست", "stop_why": "تست", "watch": "", "target_why": ["1R", "2R", "3R"]}


# ---------------------------------------------------------------- data-layer tests
def t_validate_healthy():
    d_ok, issues, info = QC.validate_ohlcv(synth_candles())
    assert d_ok and not issues, f"healthy data flagged: {issues}"
    assert info["n_bars"] == 600 and info["duplicates"] == 0


def t_validate_empty_and_none():
    for bad in (None, pd.DataFrame()):
        d_ok, issues, _ = QC.validate_ohlcv(bad)
        assert not d_ok and issues, f"empty/None must be blocked, got ok={d_ok}"


def t_validate_short_history():
    d_ok, issues, _ = QC.validate_ohlcv(synth_candles(60))
    assert not d_ok and any("کوتاه" in s for s in issues), f"short history must be blocked: {issues}"


def t_validate_nan_price():
    df = synth_candles()
    df.loc[df.index[-1], "close"] = np.nan
    d_ok, issues, _ = QC.validate_ohlcv(df)
    assert not d_ok and any("NaN" in s for s in issues), f"NaN close must be blocked: {issues}"


def t_validate_negative_price():
    df = synth_candles()
    df.loc[df.index[-3], "close"] = -5.0
    d_ok, issues, _ = QC.validate_ohlcv(df)
    assert not d_ok and any("صفر یا منفی" in s for s in issues), issues


def t_validate_ohlc_structure():
    df = synth_candles()
    df.loc[df.index[-5], "high"] = df.loc[df.index[-5], "low"] - 1.0   # high < low
    d_ok, issues, _ = QC.validate_ohlcv(df)
    assert not d_ok and any("مخدوش" in s for s in issues), f"high<low must be blocked: {issues}"


def t_validate_price_spike():
    df = synth_candles()
    df.loc[df.index[-1], "close"] = df.loc[df.index[-1], "close"] * 50
    d_ok, issues, _ = QC.validate_ohlcv(df)
    assert not d_ok and any("غیرمنطقی" in s for s in issues), f"spike must be blocked: {issues}"


def t_validate_duplicate_timestamps():
    df = synth_candles()
    df.loc[df.index[-1], "dt"] = df.loc[df.index[-2], "dt"]
    d_ok, issues, info = QC.validate_ohlcv(df)
    assert not d_ok and any("تکراری" in s for s in issues) and info["duplicates"] == 1, issues


def t_validate_missing_columns():
    df = synth_candles().drop(columns=["volume"])
    d_ok, issues, _ = QC.validate_ohlcv(df)
    assert not d_ok and any("volume" in s for s in issues), issues


def t_validate_forex_zero_volume_ok():
    """FX feeds have volume=0 everywhere — volume presence suffices, value is not judged."""
    df = synth_candles()
    df["volume"] = 0.0
    d_ok, issues, _ = QC.validate_ohlcv(df)
    assert d_ok and not issues, f"zero volume must not block: {issues}"


def t_validate_indicators_nan():
    d = healthy_indicators()
    d.loc[d.index[-1], "rsi"] = np.nan
    issues = QC.validate_indicators(d)
    assert any("rsi" in s for s in issues), f"NaN rsi on last bar must be flagged: {issues}"


def t_validate_indicators_healthy():
    assert QC.validate_indicators(healthy_indicators()) == []


# ---------------------------------------------------------------- plan-layer tests
def t_qc_plan_valid():
    assert QC.qc_plan(valid_active_plan()) == [], "valid plan must pass"


def t_qc_plan_stop_wrong_side():
    p = valid_active_plan()
    p["stop"] = 102.0                       # above entry for a long
    issues = QC.qc_plan(p)
    assert any("زیر ورود" in s for s in issues), issues


def t_qc_plan_stop_too_close():
    p = valid_active_plan()
    p["stop"] = 99.9                        # 0.1R with atr=1 → 0.1×ATR < 0.25×ATR
    issues = QC.qc_plan(p)
    assert any("حدِ منطقی" in s for s in issues), issues


def t_qc_plan_stop_too_far():
    p = valid_active_plan()
    p["stop"] = 93.0                        # 7×ATR > 6×ATR
    issues = QC.qc_plan(p)
    assert any("بیشتر است" in s for s in issues), issues


def t_qc_plan_target_wrong_side():
    p = valid_active_plan()
    p["targets"] = [(98.0, 1.0)]            # "target" below entry for a long
    issues = QC.qc_plan(p)
    assert any("بالای ورود" in s for s in issues), issues


def t_qc_plan_target_too_near():
    p = valid_active_plan()
    p["targets"] = [(100.5, 0.25)]          # 0.25R < 0.4R
    issues = QC.qc_plan(p)
    assert any("کمتر از" in s for s in issues), issues


def t_qc_plan_rr_mismatch():
    p = valid_active_plan()
    p["rr"] = 2.5                           # TP1 is actually 1R
    issues = QC.qc_plan(p)
    assert any("سازگار نیست" in s for s in issues), issues


def t_qc_plan_confidence_out_of_range():
    for bad in (150, -5):
        p = valid_active_plan()
        p["confidence"] = bad
        issues = QC.qc_plan(p)
        assert any("۰ تا ۱۰۰" in s for s in issues), f"conf={bad}: {issues}"


def t_qc_plan_untrusted_stats():
    p = valid_active_plan()
    p["stats"]["pullback"] = {"mode": "pullback", "n": 2, "win1": 50.0, "exp2": 0.4,
                              "total2": 0.8, "longs": 1, "shorts": 1}
    issues = QC.qc_plan(p)
    assert any("قابل‌اعتماد نیست" in s for s in issues), issues


def t_qc_plan_no_targets():
    p = valid_active_plan()
    p["targets"] = []
    issues = QC.qc_plan(p)
    assert any("بدون هیچ هدف" in s for s in issues), issues


def t_qc_plan_nan_entry():
    p = valid_active_plan()
    p["entry"] = float("nan")
    issues = QC.qc_plan(p)
    assert issues and any("ورود" in s for s in issues), issues


def t_qc_plan_risk_pct_absurd():
    p = valid_active_plan()
    p["risk_pct"] = 80.0
    issues = QC.qc_plan(p)
    assert any("ریسکِ درصدی" in s for s in issues), issues


# ---------------------------------------------------------------- gate tests
def t_gate_passes_valid_plan():
    d = healthy_indicators()
    out = QC.qc_gate(d, valid_active_plan())
    assert out["status"] == "active" and out["entry"] == 100.0, out["status"]
    assert out["qc"]["ok"] and out["qc"]["n_fail"] == 0
    assert "QC" in out["qc"]["stamp"] and "تست‌شده" in out["qc"]["stamp"]
    assert "QC" in out["qc"]["stamp_en"] and "passed" in out["qc"]["stamp_en"]


def t_gate_blocks_nan_close():
    d = healthy_indicators()
    d.loc[d.index[-1], "close"] = np.nan
    out = QC.qc_gate(d, valid_active_plan())
    assert out["status"] == "wait" and out["entry"] is None
    assert out["qc"]["n_fail"] > 0 and "دروازه‌ی کیفیت" in out["why"]
    assert out["watch"] == "" or isinstance(out["watch"], str)
    assert np.isfinite(out["atr"]) and out["atr"] >= 0


def t_gate_blocks_broken_ohlc():
    d = healthy_indicators()
    d.loc[d.index[-3], "high"] = d.loc[d.index[-3], "low"] - 1.0
    out = QC.qc_gate(d, valid_active_plan())
    assert out["status"] == "wait" and any("مخدوش" in s for s in out["qc"]["issues"])


def t_gate_downgrades_untrusted_active():
    d = healthy_indicators()
    p = valid_active_plan()
    p["stats"]["pullback"] = {"mode": "pullback", "n": 2, "win1": 50.0, "exp2": 0.4,
                              "total2": 0.8, "longs": 1, "shorts": 1}
    out = QC.qc_gate(d, p)
    assert out["status"] == "wait" and any("قابل‌اعتماد نیست" in s for s in out["qc"]["issues"])
    assert "stats" in out and "fade" in out["stats"] and "pullback" in out["stats"]


def t_gate_downgrades_low_confidence():
    d = healthy_indicators()
    p = valid_active_plan()
    p["confidence"] = 30                    # below the 40% trust floor
    out = QC.qc_gate(d, p)
    assert out["status"] == "wait" and any("۴۰٪" in s for s in out["qc"]["issues"])


def t_gate_keeps_context_on_downgrade():
    d = healthy_indicators()
    p = valid_active_plan()
    p["confidence"] = 30
    p["score"] = -42.0
    p["fvg_note"] = "نکته"
    out = QC.qc_gate(d, p)
    assert out["status"] == "wait" and out.get("score") == -42.0 and out.get("fvg_note") == "نکته"


def t_gate_wait_plan_gets_qc_but_no_downgrade():
    d = healthy_indicators()
    base = {"status": "wait", "direction": "⏸ انتظار (بدون معامله)", "entry": None, "stop": None,
            "targets": [], "rr": 0, "confidence": 0, "atr": 1.0,
            "stats": {m: dict(QC._ZERO_STATS, mode=m) for m in ("fade", "pullback")},
            "why": "هیچ ستاپ معتبری فعال نیست", "watch": ""}
    out = QC.qc_gate(d, base)
    assert out["status"] == "wait" and out["qc"]["ok"], "clean wait must not be flagged"
    assert "داده‌ی سالم" in out["qc"]["stamp"]


def t_gate_fail_soft_on_thrown_raw_builder():
    d = healthy_indicators()
    broken = d.drop(columns=["close"])      # raw builder raises KeyError → QC must swallow
    out = QC.qc_gate(broken, {"status": "wait"})
    assert out["status"] == "wait" and out["entry"] is None


def t_gate_deterministic():
    d = healthy_indicators()
    a = QC.qc_gate(d, valid_active_plan())
    b = QC.qc_gate(d.copy(), valid_active_plan())
    assert json.dumps(a, default=str, sort_keys=True) == json.dumps(b, default=str, sort_keys=True)


# ---------------------------------------------------------------- integration tests
def t_setup_plan_pipeline_integration():
    from app_base import setup_plan
    d = healthy_indicators()
    plan = setup_plan(d)
    for key in ("status", "direction", "entry", "stop", "targets", "rr", "confidence",
                "atr", "stats", "qc", "why"):
        assert key in plan, f"plan missing {key}"
    assert plan["status"] in ("active", "wait")
    if plan["status"] == "active":
        assert plan["qc"]["ok"], f"emitted active plan failed QC: {plan['qc']['issues']}"
        vals = [plan["entry"], plan["stop"], plan["atr"]] + [t[0] for t in plan["targets"]]
        assert all(np.isfinite(v) and v > 0 for v in vals), vals
    else:
        assert plan["entry"] is None and plan["why"], "wait plan must explain itself"


def t_setup_plan_pipeline_deterministic():
    from app_base import setup_plan
    d = healthy_indicators()
    a = setup_plan(d)
    b = setup_plan(d.copy())
    assert json.dumps(a, default=str, sort_keys=True) == json.dumps(b, default=str, sort_keys=True)


def t_make_plan_includes_qc():
    from app_base import add_indicators, confluence, make_plan, swing_levels
    d = healthy_indicators()
    score_series, _ = confluence(d)
    score = float(score_series.iloc[-1])
    plan = make_plan(d, score, swing_levels(d))
    assert "qc" in plan and "score" in plan and "fvg_note" in plan
    assert -100 <= score <= 100
    if plan["status"] == "active":
        assert plan["qc"]["ok"]


def t_triple_tp_plan_none_on_broken_data():
    from app_base import add_indicators, triple_tp_plan
    d = add_indicators(synth_candles(60))           # too short → QC blocks
    assert triple_tp_plan(d, 10.0) is None, "QC-blocked symbol must be skipped by the scanner"
    d2 = add_indicators(synth_candles())
    d2.loc[d2.index[-1], "close"] = np.nan
    assert triple_tp_plan(d2, 10.0) is None


def t_png_renders_with_qc_stamp():
    from app_base import render_analysis_png, swing_levels
    d = healthy_indicators()
    plan = valid_active_plan()
    plan["qc"] = {"stamp_en": "QC 14/14 passed · data OK · levels sane · setup walk-forward tested"}
    png = render_analysis_png(d, plan, swing_levels(d), 12.0, "BTCUSDT", "KuCoin", "1hour", 2)
    assert isinstance(png, bytes) and png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 10_000
    wait_p = QC.qc_gate(d, {"status": "wait", "stats": {}, "atr": 1.0})
    png2 = render_analysis_png(d, wait_p, swing_levels(d), -5.0, "BTCUSDT", "KuCoin", "1hour", 2)
    assert isinstance(png2, bytes) and png2[:8] == b"\x89PNG\r\n\x1a\n"


def t_stamp_variants():
    q_ok = {"n_checks": 14, "n_fail": 0, "setup_tested": True,
            "stats": {"n": 12, "win1": 55.0}, "warnings": []}
    q_bad = {"n_checks": 14, "n_fail": 2, "setup_tested": False, "stats": {}, "warnings": []}
    assert "14/14" in QC.stamp_of(q_ok) and "تست‌شده" in QC.stamp_of(q_ok)
    assert "⛔" in QC.stamp_of(q_bad) and "متوقف" in QC.stamp_of(q_bad)
    assert "passed" in QC.stamp_of(q_ok, en=True) and "BLOCKED" in QC.stamp_of(q_bad, en=True)


def t_stamp_warns_on_thin_history():
    d = synth_candles(150)                   # ≥ MIN_BARS but < WARMUP_BARS
    assert not QC.validate_ohlcv(d)[0] is False          # still valid data
    out = QC.qc_gate(healthy_indicators().head(150), valid_active_plan())
    assert any("گرم نیست" in w for w in out["qc"]["warnings"]), out["qc"]["warnings"]
    # thin history warns but must NOT block a plan whose stats are trusted
    assert out["status"] == "active" and out["qc"]["ok"]


if __name__ == "__main__":
    print("core/signal_qc.py — دروازه‌ی کنترل کیفیت سیگنال + اتصال به setup_plan/PNG")
    section_d = "لایه‌ی داده"
    section_p = "لایه‌ی طرح"
    section_g = "دروازه (qc_gate)"
    section_i = "اتصال به موتور"
    print(f"  -- {section_d}")
    check("healthy candles pass", t_validate_healthy)
    check("empty/None blocked", t_validate_empty_and_none)
    check("short history blocked", t_validate_short_history)
    check("NaN price blocked", t_validate_nan_price)
    check("negative price blocked", t_validate_negative_price)
    check("broken OHLC structure blocked", t_validate_ohlc_structure)
    check("price spike blocked", t_validate_price_spike)
    check("duplicate timestamps blocked", t_validate_duplicate_timestamps)
    check("missing columns blocked", t_validate_missing_columns)
    check("zero volume (forex) allowed", t_validate_forex_zero_volume_ok)
    check("indicator NaN on last bar flagged", t_validate_indicators_nan)
    check("indicators healthy pass", t_validate_indicators_healthy)
    print(f"  -- {section_p}")
    check("valid plan passes", t_qc_plan_valid)
    check("stop wrong side", t_qc_plan_stop_wrong_side)
    check("stop too close", t_qc_plan_stop_too_close)
    check("stop too far", t_qc_plan_stop_too_far)
    check("target wrong side", t_qc_plan_target_wrong_side)
    check("target too near", t_qc_plan_target_too_near)
    check("R:R mismatch", t_qc_plan_rr_mismatch)
    check("confidence out of range", t_qc_plan_confidence_out_of_range)
    check("untrusted walk-forward stats", t_qc_plan_untrusted_stats)
    check("no targets", t_qc_plan_no_targets)
    check("NaN entry", t_qc_plan_nan_entry)
    check("absurd risk_pct", t_qc_plan_risk_pct_absurd)
    print(f"  -- {section_g}")
    check("valid plan passes gate", t_gate_passes_valid_plan)
    check("NaN close → wait + reason", t_gate_blocks_nan_close)
    check("broken OHLC → wait", t_gate_blocks_broken_ohlc)
    check("untrusted active → downgrade", t_gate_downgrades_untrusted_active)
    check("low confidence → downgrade", t_gate_downgrades_low_confidence)
    check("context kept on downgrade", t_gate_keeps_context_on_downgrade)
    check("clean wait stays clean", t_gate_wait_plan_gets_qc_but_no_downgrade)
    check("fail-soft on thrown builder", t_gate_fail_soft_on_thrown_raw_builder)
    check("gate deterministic", t_gate_deterministic)
    print(f"  -- {section_i}")
    check("setup_plan full pipeline", t_setup_plan_pipeline_integration)
    check("setup_plan deterministic", t_setup_plan_pipeline_deterministic)
    check("make_plan carries QC", t_make_plan_includes_qc)
    check("scanner skips QC-blocked", t_triple_tp_plan_none_on_broken_data)
    check("presentation PNG renders with QC stamp", t_png_renders_with_qc_stamp)
    check("stamp variants", t_stamp_variants)
    check("thin history warns, never silently blocks", t_stamp_warns_on_thin_history)
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)
