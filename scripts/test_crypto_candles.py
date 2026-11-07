"""
Zero-network tests for core/crypto_candles.py (Binance klines + Lighter funding)
+ core/paper.py (pure virtual-position logic)
+ compile checks of the two upgraded crypto pages (p1 dashboard, p2 live trading).

Usage (from the repository root):
    python scripts/test_crypto_candles.py

No network — the HTTP layer is injected with fakes.
Exits non-zero if any test fails.
"""
import os
import py_compile
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import crypto_candles as CC   # noqa: E402
from core import paper as PP            # noqa: E402

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


# ---------------------------------------------------------------- klines parsing
def t_parse_klines_good():
    data = [[1794031200000, "76034.01", "76070.01", "76014.00", "76056.11", "275.28"],
            [1794034800000, "76056.11", "76070.01", "76000.00", "76038.16", "125.71"]]
    rows = CC._parse_klines(data)
    assert len(rows) == 2, rows
    assert rows[0][0] == 1794031200 and rows[1][0] == 1794034800   # ms → s
    assert rows[0][1:] == [76034.01, 76070.01, 76014.0, 76056.11, 275.28]
    assert rows == sorted(rows, key=lambda r: r[0])


def t_parse_klines_bad_rows():
    data = [
        ["junk"],                                            # غیر list
        [1794031200000, "1", "2", "0.5", "1.5"],             # کوتاه‌تر از ۶ فیلد
        [1794031200000, "bad", "2", "0.5", "1.5", "10"],     # عدد خراب
        [1794031200000, "1", "0.2", "0.5", "1.5", "10"],     # high < low
        [1794031200000, "-1", "2", "0.5", "1.5", "10"],      # منفی
        [1794031200000, "1", "2", "0.5", "1.5", "10"],       # معتبر (دو نسخه — آخرین می‌ماند)
        [1794031200000, "1", "2", "0.5", "1.9", "20"],       # تکراری ts
    ]
    rows = CC._parse_klines(data)
    assert len(rows) == 1 and rows[0][4] == 1.9 and rows[0][5] == 20.0, rows
    assert CC._parse_klines(None) == []
    assert CC._parse_klines({"a": 1}) == []
    assert CC._parse_klines([]) == []


def t_pair_symbol():
    assert CC.pair_symbol("BTC") == "BTCUSDT"
    assert CC.pair_symbol("btc") == "BTCUSDT"
    assert CC.pair_symbol("BTC-USDT") == "BTCUSDT"
    assert CC.pair_symbol("BTC/USDT") == "BTCUSDT"
    assert CC.pair_symbol("ETHUSDT") == "ETHUSDT"
    assert CC.pair_symbol("") == ""
    assert CC.pair_symbol(None) == ""


def t_decimals_for():
    assert CC.decimals_for(76000.0) == 2
    assert CC.decimals_for(150.5) == 4
    assert CC.decimals_for(0.05) == 6
    assert CC.decimals_for(0.000012) == 8
    assert CC.decimals_for("bad") == 4


# ---------------------------------------------------------------- fetch + bundle
_KLINES = [[1794031200000, "1", "2", "0.5", "1.5", "10"]]


def t_fetch_candles():
    calls = []

    def fake(url, **kw):
        calls.append((url, kw.get("params")))
        assert "data-api.binance.vision" in url and "/api/v3/klines" in url
        assert kw["params"]["symbol"] == "BTCUSDT"
        return _KLINES

    rows = CC.fetch_candles("BTC", "1hour", _fetch=fake)
    assert rows and rows[0][0] == 1794031200, rows
    assert calls[0][1]["interval"] == "1h" and calls[0][1]["limit"] == CC.TFS["1hour"][1]

    # بازه‌ی ناشناخته / پایه‌ی خالی → None بدون تماس شبکه
    assert CC.fetch_candles("BTC", "9hour", _fetch=fake) is None
    assert CC.fetch_candles("", "1hour", _fetch=fake) is None
    assert len(calls) == 1


def t_fetch_candles_errors():
    def boom(url, **kw):
        raise IOError("network down")
    assert CC.fetch_candles("BTC", "1day", _fetch=boom) is None
    assert CC.fetch_candles("BTC", "1day", _fetch=lambda u, **k: "not-a-list") is None


def t_bundle_cache():
    CC._reset_for_tests()
    calls = {"n": 0}

    def fake(url, **kw):
        calls["n"] += 1
        return _KLINES

    t0 = 1000.0
    b1 = CC.candles_bundle("BTC", ("1hour", "1day"), _fetch=fake, now=t0)
    assert set(b1) == {"1hour", "1day"} and calls["n"] == 2
    # کش: همان now → بدون تماس جدید
    b2 = CC.candles_bundle("BTC", ("1hour", "1day"), _fetch=fake, now=t0 + 30)
    assert set(b2) == {"1hour", "1day"} and calls["n"] == 2
    # انقضای کش → دوباره fetch
    b3 = CC.candles_bundle("BTC", ("1hour",), _fetch=fake, now=t0 + 200)
    assert b3 and calls["n"] == 3
    # force → بی‌اعتنا به کش
    CC.candles_bundle("BTC", ("1hour",), _fetch=fake, now=t0 + 200, force=True)
    assert calls["n"] == 4
    # نماد دیگر کش جدا دارد
    CC.candles_bundle("ETH", ("1hour",), _fetch=fake, now=t0 + 200)
    assert calls["n"] == 5


def t_bundle_failure_cached():
    CC._reset_for_tests()
    calls = {"n": 0}

    def flaky(url, **kw):
        calls["n"] += 1
        raise IOError("rate limited")

    t0 = 1000.0
    assert CC.candles_bundle("BTC", ("1hour",), _fetch=flaky, now=t0) == {}
    # شکست هم کش می‌شود تا هر رندر UI کوبش شبکه ندهد
    assert CC.candles_bundle("BTC", ("1hour",), _fetch=flaky, now=t0 + 60) == {}
    assert calls["n"] == 1
    # بعد از انقضا دوباره تلاش می‌شود
    assert CC.candles_bundle("BTC", ("1hour",), _fetch=flaky, now=t0 + 200) == {}
    assert calls["n"] == 2


def t_bundle_partial():
    CC._reset_for_tests()

    def fake(url, **kw):
        if kw["params"]["interval"] == "1h":
            return _KLINES
        raise IOError("no data")

    b = CC.candles_bundle("BTC", ("1hour", "1day"), _fetch=fake, now=0.0)
    assert set(b) == {"1hour"}          # تایم‌فریم ناموفق حذف می‌شود


# ---------------------------------------------------------------- funding
_FUND = {"code": 200, "funding_rates": [
    {"market_id": 0, "symbol": "BTC", "rate": "0.0001"},
    {"market_id": 1, "symbol": "ETH", "rate": -0.0002},
    {"market_id": "x", "rate": "0.5"},                # خراب: آیدی
    {"market_id": 2, "rate": None},                   # خراب: نرخ
    {"market_id": 3, "rate": "junk"},                 # خراب: نرخ
    {"market_id": 4, "rate": 5.0},                    # خارج از بازه‌ی منطقی
    "junk",
]}


def t_funding_rate():
    CC._reset_for_tests()
    calls = {"n": 0}

    def fake(url, **kw):
        calls["n"] += 1
        assert "funding-rates" in url
        return _FUND

    assert CC.funding_rate(0, _fetch=fake) == 0.0001
    assert CC.funding_rate(1, _fetch=fake) == -0.0002
    # کش: بدون تماس جدید
    assert CC.funding_rate(1, _fetch=fake) == -0.0002
    assert calls["n"] == 1
    # بازار ناشناخته
    assert CC.funding_rate(999, _fetch=fake) is None
    # ورودی خراب
    assert CC.funding_rate("x", _fetch=fake) is None
    assert CC.funding_rate(None, _fetch=fake) is None


def t_funding_bad_payloads():
    CC._reset_for_tests()
    assert CC.funding_rate(0, _fetch=lambda u, **k: None) is None
    CC._reset_for_tests()
    assert CC.funding_rate(0, _fetch=lambda u, **k: {"funding_rates": "junk"}) is None
    CC._reset_for_tests()

    def boom(url, **kw):
        raise IOError("down")
    assert CC.funding_rate(0, _fetch=boom) is None


# ---------------------------------------------------------------- paper
def t_paper_buy():
    pos, bal, r, msg = PP.apply_fill({}, "buy", "BTC", 0.5, 100.0, 200.0)
    assert bal == 150.0 and r == 0.0
    assert pos["BTC"] == {"qty": 0.5, "avg": 100.0}
    assert not msg.startswith("✗")
    # ورودی اصلی تغییر نکرده
    assert PP.apply_fill.__doc__ is not None


def t_paper_buy_avg_updates():
    pos, bal, _, _ = PP.apply_fill({}, "buy", "BTC", 1.0, 100.0, 1000.0)
    pos, bal, _, _ = PP.apply_fill(pos, "buy", "BTC", 1.0, 140.0, bal)
    assert abs(pos["BTC"]["qty"] - 2.0) < 1e-9
    assert abs(pos["BTC"]["avg"] - 120.0) < 1e-9
    assert abs(bal - (1000.0 - 240.0)) < 1e-9


def t_paper_sell_realized():
    pos, bal, _, _ = PP.apply_fill({}, "buy", "BTC", 1.0, 100.0, 1000.0)
    pos, bal, r, msg = PP.apply_fill(pos, "sell", "BTC", 0.5, 110.0, bal)
    assert abs(r - 5.0) < 1e-9                        # (110-100)*0.5
    assert abs(pos["BTC"]["qty"] - 0.5) < 1e-9
    assert abs(pos["BTC"]["avg"] - 100.0) < 1e-9      # میانگین دست‌نخورده
    assert abs(bal - (900.0 + 55.0)) < 1e-9


def t_paper_sell_close_and_oversell():
    pos, bal, _, _ = PP.apply_fill({}, "buy", "BTC", 1.0, 100.0, 1000.0)
    pos, bal, r, msg = PP.apply_fill(pos, "sell", "BTC", 1.0, 90.0, bal)
    assert abs(r - (-10.0)) < 1e-9 and "BTC" not in pos       # کلوز کامل = حذف کلید
    over = PP.apply_fill(pos, "sell", "BTC", 0.1, 90.0, bal)
    assert over[3].startswith("✗") and over[1] == bal and over[2] == 0.0
    # فروشِ بدون پوزیشن
    naked = PP.apply_fill({}, "sell", "ETH", 1.0, 90.0, bal)
    assert naked[3].startswith("✗") and naked[1] == bal


def t_paper_insufficient_balance():
    pos, bal, r, msg = PP.apply_fill({}, "buy", "BTC", 2.0, 100.0, 150.0)
    assert msg.startswith("✗") and bal == 150.0 and pos == {}


def t_paper_bad_inputs():
    base = {"BTC": {"qty": 1.0, "avg": 100.0}}
    assert PP.apply_fill(base, "buy", "", 1.0, 100.0, 1000.0)[3].startswith("✗")
    assert PP.apply_fill(base, "buy", "BTC", 0.0, 100.0, 1000.0)[3].startswith("✗")
    assert PP.apply_fill(base, "buy", "BTC", -1.0, 100.0, 1000.0)[3].startswith("✗")
    assert PP.apply_fill(base, "buy", "BTC", 1.0, 0.0, 1000.0)[3].startswith("✗")
    assert PP.apply_fill(base, "buy", "BTC", "junk", 100.0, 1000.0)[3].startswith("✗")
    assert PP.apply_fill(base, "side", "BTC", 1.0, 100.0, 1000.0)[3].startswith("✗")
    # هیچ‌کدام وضعیت را خراب نکرده‌اند
    assert base["BTC"] == {"qty": 1.0, "avg": 100.0}
    # ردیف خراب داخل positions نادیده گرفته می‌شود
    pos, bal, _, _ = PP.apply_fill({"JUNK": "x", "BAD": None}, "buy", "ETH", 1.0, 10.0, 100.0)
    assert set(pos) == {"ETH"}


def t_paper_unrealized():
    pos = {"BTC": {"qty": 2.0, "avg": 100.0}}
    assert abs(PP.unrealized_pnl(pos, "BTC", 110.0) - 20.0) < 1e-9
    assert PP.unrealized_pnl(pos, "BTC", None) == 0.0
    assert PP.unrealized_pnl(pos, "ETH", 110.0) == 0.0
    assert PP.unrealized_pnl({}, "BTC", 110.0) == 0.0
    assert PP.unrealized_pnl({"BTC": {"qty": -5, "avg": 100}}, "BTC", 110.0) == 0.0


def t_pages_compile():
    for rel in ["pages/1_Live_Prices.py", "pages/2_Live_Trading.py",
                "core/crypto_candles.py", "core/paper.py"]:
        py_compile.compile(os.path.join(BASE_DIR, rel), doraise=True)


if __name__ == "__main__":
    print("core/crypto_candles.py + core/paper.py — crypto pillar upgrades")
    check("klines parse good", t_parse_klines_good)
    check("klines parse bad rows", t_parse_klines_bad_rows)
    check("pair symbol", t_pair_symbol)
    check("decimals for", t_decimals_for)
    check("fetch candles", t_fetch_candles)
    check("fetch candles errors", t_fetch_candles_errors)
    check("bundle cache", t_bundle_cache)
    check("bundle failure cached", t_bundle_failure_cached)
    check("bundle partial", t_bundle_partial)
    check("funding rate", t_funding_rate)
    check("funding bad payloads", t_funding_bad_payloads)
    check("paper buy", t_paper_buy)
    check("paper buy avg updates", t_paper_buy_avg_updates)
    check("paper sell realized", t_paper_sell_realized)
    check("paper sell close/oversell", t_paper_sell_close_and_oversell)
    check("paper insufficient balance", t_paper_insufficient_balance)
    check("paper bad inputs", t_paper_bad_inputs)
    check("paper unrealized", t_paper_unrealized)
    check("pages compile", t_pages_compile)
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)
