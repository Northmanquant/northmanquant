"""
Edge-case + regression tests for core/gaps.py (FVG / BVG / IFVG engine).

Usage (from the repository root):
    python scripts/test_gaps.py

Needs only numpy + pandas. Exits non-zero if any test fails.
Covers: basic analysis, flat/zero prices, NaN rows, missing columns,
short frames, zone-boundary logic, causality (no look-ahead),
IFVG inversion on engineered candles, and performance.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from core import gaps as G

ok, fail = 0, 0


def make_df(n=300, seed=7, with_dt=True, with_vol=True):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    open_ = close + rng.normal(0, 0.3, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.5, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.5, n))
    k = min(100, n - 5)
    high[k] = close[k] + 5
    low[k] = min(open_[k], close[k]) - 5
    d = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})
    if with_vol:
        d["volume"] = rng.gamma(2, 1000, n)
    if with_dt:
        d["dt"] = pd.date_range("2025-01-01", periods=n, freq="1h")
    return d


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


def t_basic():
    d = make_df()
    res = G.gap_analysis(d)
    assert len(res["fvg_score"]) == len(d)
    assert len(G.table_rows(res)) == 2
    G.zones_frame(res, float(d["close"].iloc[-1]))
    G.plotly_shapes(res, x_end=d["dt"].iloc[-1], price=float(d["close"].iloc[-1]))


def t_flat():
    n = 100
    d = pd.DataFrame({"open": np.full(n, 10.0), "high": np.full(n, 10.0),
                      "low": np.full(n, 10.0), "close": np.full(n, 10.0),
                      "volume": np.ones(n)})
    res = G.gap_analysis(d)
    assert np.isfinite(res["fvg_score"]).all()


def t_zero():
    n = 60
    d = pd.DataFrame({"open": np.zeros(n), "high": np.zeros(n),
                      "low": np.zeros(n), "close": np.zeros(n)})
    res = G.gap_analysis(d)
    assert np.isfinite(res["fvg_score"]).all()


def t_nans():
    d = make_df(200)
    d.loc[10:15, "high"] = np.nan
    d.loc[50, "close"] = np.nan
    res = G.gap_analysis(d)
    assert np.isfinite(res["fvg_score"][100:]).all()


def t_missing():
    d = make_df(150, with_vol=False, with_dt=False)
    res = G.gap_analysis(d)
    assert len(res["fvg_score"]) == 150


def t_short():
    res = G.gap_analysis(make_df(4))
    assert len(res["fvg_score"]) == 4


def t_zone_bounds():
    d = make_df(400, seed=3)
    res = G.gap_analysis(d)
    price = float(d["close"].iloc[-1])
    for kind in ("FVG", "BVG"):
        for z in G.active_zones(res, kind, price):
            assert not z["mitigated"]
            assert z["bot"] <= z["top"]
    info = res["fvg_info"]
    if info["nearest_support"] is not None:
        assert info["nearest_support"]["top"] < price
    if info["nearest_resist"] is not None:
        assert info["nearest_resist"]["bot"] > price


def t_causal():
    """Truncating the frame must not change earlier scores (no look-ahead)."""
    d = make_df(300, seed=11)
    full = G.gap_analysis(d)
    cut = G.gap_analysis(d.iloc[:200].reset_index(drop=True))
    assert np.allclose(full["fvg_score"][:200], cut["fvg_score"][:200], atol=1e-9)
    assert np.allclose(full["bvg_score"][:200], cut["bvg_score"][:200], atol=1e-9)


def t_ifvg():
    """A close through a bullish FVG must invert it into an IFVG resistance."""
    n = 40
    o = np.full(n, 106.0); c = np.full(n, 106.0)
    h = np.full(n, 107.0); l = np.full(n, 105.0)
    h[5] = 106.0; l[5] = 105.0; c[5] = 105.5
    c[6] = 116.0; o[6] = 105.5; h[6] = 116.5; l[6] = 105.5   # impulse candle
    l[7] = 111.0; c[7] = 115.0; o[7] = 116.0; h[7] = 117.0   # gap zone [106, 111]
    l[8] = 111.5; c[8] = 115.5; h[8] = 116.0
    l[9] = 111.5; c[9] = 115.0; h[9] = 116.0
    l[10] = 112.0; l[11] = 112.0                             # stay above the zone
    o[12] = 110.0; c[12] = 95.0; h[12] = 110.5; l[12] = 94.0  # close below → IFVG
    d = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": np.ones(n)})
    res = G.gap_analysis(d)
    assert len(res["fvg_zones"]) >= 1
    assert any(z["inverted"] for z in res["fvg_zones"]), "IFVG inversion did not trigger"


def t_scores():
    f, b, res = G.gap_scores(make_df(120))
    assert len(f) == 120 and len(b) == 120


def t_perf():
    import time
    d = make_df(1500, seed=5)
    t0 = time.time()
    G.gap_analysis(d)
    assert time.time() - t0 < 5, "gap_analysis too slow"


print("== core/gaps.py ==")
check("basic gap_analysis + helpers", t_basic)
check("flat prices (atr=0)", t_flat)
check("all-zero prices", t_zero)
check("NaN rows in OHLC", t_nans)
check("missing volume/dt columns", t_missing)
check("df with <5 rows", t_short)
check("active_zones boundary logic", t_zone_bounds)
check("causality (no look-ahead)", t_causal)
check("IFVG inversion on engineered data", t_ifvg)
check("gap_scores convenience", t_scores)
check("performance 1500 bars", t_perf)

print(f"\n===== {ok} passed, {fail} failed =====")
sys.exit(1 if fail else 0)
