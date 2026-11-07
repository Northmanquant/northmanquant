"""
Zero-network tests for the arena↔dashboard bridge and daily-report upgrades:
  · core/arena.py — symbol_opinions (per-symbol, per-agent latest trade)
  · core/daily_report.py — closed_lighter counter + recalibration lines
    + fail-soft aggregate on junk rows
  · compile check of the upgraded dashboard page (p1)

Usage (from the repository root):
    python scripts/test_arena_bridge.py

No network — everything runs on fake records.
Exits non-zero if any test fails.
"""
import os
import py_compile
import sys
import traceback
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import arena as AR            # noqa: E402
from core import daily_report as DR     # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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


_TRADES = [
    {"agent": "SmartMoney 🏦", "symbol": "BTC", "status": "closed", "exchange": "Lighter",
     "realized_r": 1.2, "points": 2.0, "exit_reason": "trail", "result": "win",
     "created_at": "2026-11-07T01:00:00Z", "closed_at": "2026-11-07T02:00:00Z",
     "entry": 76000, "direction": 1},
    {"agent": "MeanRev 🎯", "symbol": "BTC-USDT", "status": "open", "exchange": "KuCoin",
     "realized_r": None, "points": None, "exit_reason": None, "result": None,
     "created_at": "2026-11-06T20:00:00Z", "closed_at": None, "entry": 75500, "direction": -1},
    {"agent": "Momentum 🧠", "symbol": "BTC", "status": "closed", "exchange": "KuCoin",
     "realized_r": -1.0, "points": -1.0, "exit_reason": "sl", "result": "loss",
     "created_at": "2026-11-06T10:00:00Z", "closed_at": "2026-11-06T11:00:00Z",
     "entry": 75000, "direction": 1},
    {"agent": "SmartMoney 🏦", "symbol": "ETH", "status": "closed", "exchange": "Lighter",
     "realized_r": 0.4, "points": 1.0, "exit_reason": "trail", "result": "win",
     "created_at": "2026-11-06T00:00:00Z", "closed_at": "2026-11-06T01:00:00Z",
     "entry": 3100, "direction": 1},
]


def t_symbol_opinions_basic():
    ops = AR.symbol_opinions(_TRADES, "BTC")
    assert len(ops) == 3, ops                       # SmartMoney · MeanRev (BTC-USDT) · Momentum
    assert ops[0]["agent"] == "SmartMoney 🏦"       # تازه‌ترین اول
    assert ops[1]["agent"] == "MeanRev 🎯"          # ۲۰:۰۰ بعد از ۱۰:۰۰
    assert ops[1]["status"] == "open"
    assert ops[2]["agent"] == "Momentum 🧠"


def t_symbol_opinions_normalize():
    # BTC ≈ BTC-USDT ≈ BTCUSDT — همه از مسیرِ پایه
    for q in ("BTC-USDT", "BTC/USDT", "BTCUSDT", "btc"):
        ops = AR.symbol_opinions(_TRADES, q)
        assert ops and ops[0]["agent"] == "SmartMoney 🏦", (q, ops)
    # نماد دیگر → فقط معامله‌های همان
    ops = AR.symbol_opinions(_TRADES, "ETH")
    assert len(ops) == 1 and ops[0]["agent"] == "SmartMoney 🏦"


def t_symbol_opinions_bad_inputs():
    junk = ["junk", None, 42, {"no_symbol": True}] + _TRADES
    assert AR.symbol_opinions(junk, "BTC")[0]["agent"] == "SmartMoney 🏦"
    assert AR.symbol_opinions([], "BTC") == []
    assert AR.symbol_opinions(None, "BTC") == []
    assert AR.symbol_opinions(_TRADES, "") == []
    assert AR.symbol_opinions(_TRADES, None) == []


def t_base_of():
    assert AR._base_of("BTC") == "BTC"
    assert AR._base_of("BTC-USDT") == "BTC"
    assert AR._base_of("BTC/USDT") == "BTC"
    assert AR._base_of("BTCUSDT") == "BTC"
    assert AR._base_of("USDT") == "USDT"            # خود USDT خراب نشود
    assert AR._base_of("") == ""


def t_aggregate_closed_lighter():
    now = datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc)
    agg = DR.aggregate(_TRADES, now)
    assert agg["closed_lighter"] == 2               # دو معامله‌ی بسته‌ی لایتر
    assert agg["total_closed"] == 3                 # باز‌ها نمی‌آیند
    assert agg["total_r"] == (1.2 - 1.0 + 0.4)


def t_aggregate_fail_soft():
    now = datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc)
    agg = DR.aggregate(["junk", None, 42, {"agent": "x"}], now)
    assert agg["total_closed"] == 0 and agg["closed_lighter"] == 0
    assert DR.aggregate(None, now)["total_closed"] == 0


def t_report_recal_lines():
    now = datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc)
    agg = DR.aggregate(_TRADES, now)
    md = DR.fmt_report(agg, [], None, now, "test")
    assert "ریکالیبراسیون" in md and "2/50" in md
    assert "تفکیک منبع" in md and "گزارش خودکار" in md   # بخش‌های قبلی سر جایشان‌اند
    tg = DR.fmt_telegram(agg, [], None, now)
    assert "ریکالیبراسیون" in tg and "2/50" in tg
    # بدون معامله‌ی لایتر، خط نباید بیاید
    no_lit = [t for t in _TRADES if t.get("exchange") != "Lighter"]
    md2 = DR.fmt_report(DR.aggregate(no_lit, now), [], None, now, "test")
    assert "ریکالیبراسیون" not in md2


def t_pages_compile():
    py_compile.compile(os.path.join(BASE_DIR, "pages/1_Live_Prices.py"), doraise=True)
    py_compile.compile(os.path.join(BASE_DIR, "core/arena.py"), doraise=True)
    py_compile.compile(os.path.join(BASE_DIR, "core/daily_report.py"), doraise=True)


if __name__ == "__main__":
    print("arena↔dashboard bridge + daily-report upgrades — zero network")
    check("symbol opinions basic", t_symbol_opinions_basic)
    check("symbol opinions normalize", t_symbol_opinions_normalize)
    check("symbol opinions bad inputs", t_symbol_opinions_bad_inputs)
    check("base of", t_base_of)
    check("aggregate closed_lighter", t_aggregate_closed_lighter)
    check("aggregate fail-soft", t_aggregate_fail_soft)
    check("report recal lines", t_report_recal_lines)
    check("pages compile", t_pages_compile)
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)
