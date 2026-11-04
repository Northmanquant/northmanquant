"""
Tests for the forex candles layer (core/forex.py additions) + fx flag of the TV chart
and the full analysis stack on FX data (same engine as the crypto dashboard).

Usage (from the repository root):
    python scripts/test_fxchart.py

No network — Yahoo payloads are mocked; the analysis stack runs on synthetic candles.
Exits non-zero if any test fails.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from core import forex as F  # noqa: E402
from core.tv_chart import build_tv_chart_html  # noqa: E402

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


def candle_payload(rows, *, meta_price=None):
    """rows: [[t,o,h,l,c,v], ...] → JSON شبه‌یاهو (شامل ردیف‌های خراب اگر داده شود)."""
    return {"chart": {"result": [{
        "meta": {"regularMarketPrice": meta_price if meta_price is not None else (rows[-1][4] if rows else None)},
        "timestamp": [r[0] for r in rows],
        "indicators": {"quote": [{"open": [r[1] for r in rows], "high": [r[2] for r in rows],
                                  "low": [r[3] for r in rows], "close": [r[4] for r in rows],
                                  "volume": [r[5] for r in rows]}]},
    }], "error": None}}


# ---------------------------------------------------------------------------
def t_fx_tfs_integrity():
    need = {"1min", "5min", "15min", "1hour", "4hour", "1day", "1week"}
    assert need <= set(F.FX_TFS), f"missing tfs: {need - set(F.FX_TFS)}"
    valid_iv = {"1m", "2m", "5m", "15m", "30m", "60m", "1h", "1d", "1wk"}
    for tf, (iv, rng, agg) in F.FX_TFS.items():
        assert iv in valid_iv, f"bad yahoo interval {iv} for {tf}"
        assert rng and isinstance(rng, str) and agg >= 1
        assert tf in F._BASE_SEC or iv in F._BASE_SEC      # ثانیه‌ی پایه برای تجمیع موجود است
    assert F.FX_TFS["4hour"][2] == 4 and F.FX_TFS["4hour"][0] == "60m"


def t_parse_candles_good():
    rows = [[1793700000 + i * 900, 1.10 + i * 0.001, 1.102 + i * 0.001,
             1.098 + i * 0.001, 1.101 + i * 0.001, 1000.0 + i] for i in range(5)]
    out = F._parse_chart_candles(candle_payload(rows), "EURUSD")
    assert out and len(out) == 5
    assert out[0] == [1793700000, 1.10, 1.102, 1.098, 1.101, 1000.0]
    assert all(len(r) == 6 and r[1] > 0 for r in out)
    assert [r[0] for r in out] == sorted(r[0] for r in out)


def t_parse_candles_dirty():
    rows = [
        [100, 1.0, 1.2, 0.9, 1.1, None],      # ولوم تهی → ۰
        [200, None, 1.2, 0.9, 1.1, 5],        # open تهی → حذف
        [300, 1.0, 0.8, 1.3, 1.1, 5],         # high<low → حذف
        [400, 1.0, 1.2, 0.9, 1.1, 7],
        [100, 1.0, 1.25, 0.95, 1.2, 9],       # ts تکراری → آخرین
        [50, 1.0, 1.2, 0.9, 1.1, None],       # نامرتب + ولوم تهی → مرتب می‌شود، ولوم = ۰
        [0, 0.0, 1.2, 0.9, 1.1, 1],           # قیمت صفر → حذف
    ]
    out = F._parse_chart_candles(candle_payload(rows), "GBPUSD")
    assert [r[0] for r in out] == [50, 100, 400]
    assert out[0][5] == 0.0                                    # ولوم None → ۰
    assert out[1][5] == 9.0 and out[1][4] == 1.2               # ts تکراری = نگه‌داشتنِ آخرین
    assert out[2][5] == 7.0


def t_parse_candles_bad():
    assert F._parse_chart_candles(None, "EURUSD") is None
    assert F._parse_chart_candles({}, "EURUSD") is None
    assert F._parse_chart_candles({"chart": {"result": []}}, "EURUSD") is None
    assert F._parse_chart_candles({"chart": {"result": None,
                                             "error": {"code": "Bad Request"}}}, "EURUSD") is None
    assert F._parse_chart_candles({"chart": {"result": [{"meta": {}}], "error": None}}, "EURUSD") is None
    # همه‌ی کندل‌ها خراب → None (نه لیست تهی)
    assert F._parse_chart_candles(candle_payload([[100, None, None, None, None, None]]), "EURUSD") is None


def t_agg_candles():
    rows = [[1800, 1, 2, 0.5, 1.5, 10], [5400, 1.5, 3, 1, 2.5, 20],
            [9000, 2.5, 3.5, 2, 3, 5], [12600, 3, 4, 2.5, 3.5, 5],
            [16200, 3.5, 4.5, 3, 4, 7], [19800, 4, 5, 3.5, 4.5, 3],
            [23400, 4.5, 5.5, 4, 5, 2], [27000, 5, 6, 4.5, 5.5, 1]]
    out = F._agg_candles(rows, 3600, 4)
    assert len(out) == 2
    assert out[0] == [0, 1, 4, 0.5, 3.5, 40.0]
    assert out[1] == [14400, 3.5, 6, 3, 5.5, 13.0]
    # ضریب ۱ = بدون تغییر
    assert F._agg_candles(rows, 3600, 1) == rows
    assert F._agg_candles([], 3600, 4) == []


def t_fetch_guard_and_never_raises():
    # گارد ورودی — بدون شبکه
    assert F.fetch_fx_candles("NOPE", "15min") is None
    assert F.fetch_fx_candles("EURUSD", "nope") is None
    assert F.fetch_fx_candles("", "15min") is None
    # get_json که هرچه raise کند → None نه exception
    orig = F.get_json
    F.get_json = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
    try:
        assert F.fetch_fx_candles("EURUSD", "15min") is None
    finally:
        F.get_json = orig
    # پارس خراب روی پاسخ بد → None
    F.get_json = lambda *a, **k: {"chart": {"result": [], "error": None}}
    try:
        assert F.fetch_fx_candles("EURUSD", "15min") is None
    finally:
        F.get_json = orig


def t_fx_candles_cache():
    calls = {"n": 0}

    def fake_fetch(pair, tf, **kw):
        calls["n"] += 1
        if tf == "1week":
            return None                      # یک تایم‌فریم همیشه شکست می‌خورد
        return [[1000 + i * 900, 1.0, 1.1, 0.9, 1.05, 0.0] for i in range(3)]

    orig, orig_ttl = F.fetch_fx_candles, F._CANDLE_TTL
    F.fetch_fx_candles, F._CANDLE_TTL = fake_fetch, 120.0
    try:
        F._CANDLE_CACHE.clear()
        assert F.fx_candles("NOPE") == {} and calls["n"] == 0
        out = F.fx_candles("EURUSD", force=True)
        assert calls["n"] == 7
        assert set(out) == set(F.FX_TFS) - {"1week"}     # تایم‌فریم ناموفق حذف می‌شود
        F.fx_candles("EURUSD")                            # درون TTL → fetch تازه ندارد
        assert calls["n"] == 7
        F.fx_candles("EURUSD", force=True)                # اجبار → ۷ fetch دیگر
        assert calls["n"] == 14
        F.fx_candles("EURUSD", tfs=("15min",))            # زیرمجموعه‌ی درون TTL → همان
        assert calls["n"] == 14
    finally:
        F.fetch_fx_candles, F._CANDLE_TTL = orig, orig_ttl
        F._CANDLE_CACHE.clear()


def t_candles_to_df():
    rows = [[1000, 1.0, 1.2, 0.9, 1.1, None], [1900, 1.1, 1.3, 1.0, 1.2, 5.0]]
    df = F.candles_to_df(rows)
    assert list(df.columns) == ["time", "open", "high", "low", "close", "volume", "dt"]
    assert len(df) == 2 and float(df["volume"].iloc[0]) == 0.0
    assert df["dt"].is_monotonic_increasing
    assert abs(float(df["close"].iloc[1]) - 1.2) < 1e-12


def t_tv_chart_fx_flag():
    rows = [[1000 + i * 900, 1.0, 1.2, 0.9, 1.1, 0.0] for i in range(30)]
    tfs = {"15min": rows, "1hour": rows, "1day": rows}
    html_fx = build_tv_chart_html(candles=rows, tfs=tfs, base_tf="15min", symbol="EURUSD",
                                  zones=[], levels=[], title="EURUSD · 15min", dec=5, fx=True)
    assert '"fx": true' in html_fx and '"dec": 5' in html_fx
    assert '"symbol": "EURUSD"' in html_fx
    assert "TF_GROUPS_SRC" in html_fx and "DATA.fx" in html_fx   # شرط حذف گروه Binance
    html_crypto = build_tv_chart_html(candles=rows, tfs=tfs, base_tf="15min", symbol="BTC-USDT",
                                      zones=[], levels=[], title="BTC · 15min", dec=2)
    assert '"fx": false' in html_crypto and '"dec": 2' in html_crypto
    # ناحیه/سطح هم بدون خطا
    html_z = build_tv_chart_html(candles=rows, tfs=tfs, base_tf="15min", symbol="EURUSD",
                                 zones=[{"t0": 1000, "top": 1.2, "bottom": 1.0,
                                         "kind": "bull", "tag": "FVG▲"}],
                                 levels=[{"price": 1.15, "name": "ورود", "color": "#f59e0b", "dash": False}],
                                 title="EURUSD · 15min", dec=5, fx=True)
    assert "FVG" in html_z and "1.15" in html_z


def t_analysis_stack_on_fx_data():
    """استک کامل داشبورد روی کندل سینتیک فارکس — بدون شبکه و بدون exception."""
    from app_base import (AGENTS, add_indicators, compute_agents, confluence,
                          make_plan, signal_events, swing_levels)
    rng = np.random.default_rng(42)
    n, t0, step, p = 700, 1_700_000_000, 3600, 1.10
    rows = []
    for i in range(n):
        o = p
        p = max(0.5, p + rng.normal(0, 0.0015))
        c = p
        hi = max(o, c) + abs(rng.normal(0, 0.0006))
        lo = min(o, c) - abs(rng.normal(0, 0.0006))
        rows.append([t0 + i * step, o, hi, lo, c, 0.0])   # ولوم صفر = واقعیتِ فارکس
    df = F.candles_to_df(rows)
    d = add_indicators(df)
    score_series, comp = confluence(d)
    score = float(score_series.iloc[-1])
    assert -100 <= score <= 100 and len(score_series) == len(d) and not comp.empty
    levels = swing_levels(d)
    plan = make_plan(d, score, levels)
    for key in ("status", "direction", "entry", "stop", "targets", "rr",
                "confidence", "atr", "stats", "score"):
        assert key in plan, f"plan missing {key}"
    if plan.get("entry") is not None:
        assert plan["stop"] != plan["entry"] and plan["targets"]
    cards = compute_agents(d)
    assert len(cards) == len(AGENTS) and len(AGENTS) == 8
    assert all(c["state"] in {"LONG", "SHORT", "FLAT"} for c in cards)
    events, state = signal_events(d, score_series)
    assert state["status"] in {"flat", "long", "short"}
    for col in ("زمان", "رویداد", "قیمت", "امتیاز"):
        assert col in events.columns
    # کندل واقعی‌نما → df نباید NaN در close داشته باشد
    assert not d["close"].isna().any()


if __name__ == "__main__":
    print("core/forex.py candles layer + fx chart flag + FX analysis stack")
    check("FX_TFS integrity (7 tfs, yahoo caps)", t_fx_tfs_integrity)
    check("parse candles (good)", t_parse_candles_good)
    check("parse candles (dirty rows cleaned)", t_parse_candles_dirty)
    check("parse candles (bad payloads)", t_parse_candles_bad)
    check("aggregate 4H from 60m", t_agg_candles)
    check("fetch guards + never raises", t_fetch_guard_and_never_raises)
    check("120s candle cache behaviour", t_fx_candles_cache)
    check("candles_to_df", t_candles_to_df)
    check("tv chart fx flag", t_tv_chart_fx_flag)
    check("analysis stack on FX data", t_analysis_stack_on_fx_data)
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)
