"""
Zero-network tests for core/lighter.py (public Lighter perp client)
+ LAB.filter_by_exchange (the lab's exchange filter)
+ compile checks of the two pages that gained Lighter support.

Usage (from the repository root):
    python scripts/test_lighter.py

No network — the HTTP layer is injected with fakes.
Exits non-zero if any test fails.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import lighter as LIT          # noqa: E402
from core import agent_lab as LAB        # noqa: E402

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


# ---------------------------------------------------------------- fake fetcher
_ROWS = [
    {"symbol": "BTC", "market_id": 0, "status": "ACTIVE",
     "last_trade_price": "95000.5", "mark_price": "95010", "daily_price_change": "1.25",
     "daily_price_high": "96000", "daily_price_low": "94000"},
    {"symbol": "eth", "market_id": 1, "status": "ACTIVE",
     "last_trade_price": "3100", "mark_price": "3099", "daily_price_change": "-0.4",
     "daily_price_high": "3200", "daily_price_low": "3000"},
    {"symbol": "SOL", "market_id": 2, "status": "PENDING",
     "last_trade_price": None, "mark_price": "150", "daily_price_change": "0"},
    {"symbol": "", "market_id": 3, "status": "ACTIVE"},                    # خراب: نماد خالی
    {"symbol": "BAD", "market_id": "x", "last_trade_price": "abc"},        # خراب: آیدی/قیمت
    "junk",                                                                 # خراب: غیر dict
]

calls = {"n": 0}


def fake_fetch(url, **kwargs):
    calls["n"] += 1
    assert "orderBookDetails" in url, url
    return {"order_book_details": [dict(r) for r in _ROWS if isinstance(r, dict)]}


# ---------------------------------------------------------------- tests
def t_normalize():
    assert LIT.normalize("BTC/USDT") == "BTC"
    assert LIT.normalize("btc") == "BTC"
    assert LIT.normalize("ETH-USD") == "ETH"
    assert LIT.normalize("SOL:USDT") == "SOL"
    assert LIT.normalize(" XRP /USDT ") == "XRP"
    assert LIT.normalize("") == ""
    assert LIT.normalize(None) == ""


def t_markets_parse_and_cache():
    LIT._reset_for_tests()
    calls["n"] = 0
    rows = LIT.markets(fake_fetch, now=1000.0)
    assert len(rows) == 3, rows                              # BTC/ETH/SOL — خراب‌ها رد شده‌اند
    btc = rows[0]
    assert btc["symbol"] == "BTC" and btc["market_id"] == 0  # آیدی ۰ هم معتبر است
    assert abs(btc["last"] - 95000.5) < 1e-9
    assert btc["status"] == "ACTIVE" and abs(btc["change_pct"] - 1.25) < 1e-9
    assert rows[1]["symbol"] == "ETH"                        # نماد کوچک → بزرگ
    # کش: در TTL دوباره fetch نمی‌زند
    rows2 = LIT.markets(fake_fetch, now=1030.0)
    assert calls["n"] == 1
    assert rows2 == rows
    # بعد از انقضای TTL دوباره fetch می‌زند
    LIT.markets(fake_fetch, now=1000.0 + LIT.MARKETS_TTL_SEC + 1)
    assert calls["n"] == 2


def t_markets_bad_responses():
    LIT._reset_for_tests()
    # پاسخ خالی → [] و کش نمی‌شود (تلاش بعدی زنده می‌ماند)
    assert LIT.markets(lambda u, **k: {}, now=10.0) == []
    assert LIT.markets(fake_fetch, now=11.0)                  # دوباره fetch زد
    # پاسخ غیر dict / بدون کلید → []
    LIT._reset_for_tests()
    assert LIT.markets(lambda u, **k: None, now=10.0) == []
    assert LIT.markets(lambda u, **k: {"nope": 1}, now=11.0) == []
    # شبکه خراب → [] و last_error پر می‌شود (هرگز raise نمی‌کند)
    LIT._reset_for_tests()

    def boom(url, **kwargs):
        raise RuntimeError("down")
    assert LIT.markets(boom, now=10.0) == []
    assert LIT.last_error
    # ttl خراب → پیش‌فرض
    LIT._reset_for_tests()
    assert LIT.markets(fake_fetch, now=10.0, ttl=-5)
    assert LIT.markets(fake_fetch, now=10.0, ttl="bad")


def t_market_id():
    LIT._reset_for_tests()
    assert LIT.market_id("BTC", fake_fetch) == 0
    assert LIT.market_id("btc/usdt", fake_fetch) == 0         # نرمال‌شده
    assert LIT.market_id("ETH", fake_fetch) == 1
    assert LIT.market_id("NOPE", fake_fetch) is None
    assert LIT.market_id("", fake_fetch) is None
    assert LIT.market_id(None, fake_fetch) is None


def t_symbols():
    LIT._reset_for_tests()
    assert LIT.symbols(fake_fetch) == ["BTC", "ETH"]          # فقط ACTIVE، مرتب
    # اگر هیچ ACTIVE نبود → همه
    LIT._reset_for_tests()

    def no_active(url, **kwargs):
        return {"order_book_details": [
            {"symbol": "ZZZ", "market_id": 9, "status": "PENDING",
             "last_trade_price": "1", "mark_price": "1"}]}
    assert LIT.symbols(no_active) == ["ZZZ"]
    LIT._reset_for_tests()
    assert LIT.symbols(lambda u, **k: {"order_book_details": []}) == []


def t_ticker():
    LIT._reset_for_tests()
    tk = LIT.ticker("BTC/USDT", fake_fetch)                   # نرمال‌شده
    assert tk and tk["symbol"] == "BTC"
    assert abs(tk["last"] - 95000.5) < 1e-9
    assert abs(tk["mark"] - 95010) < 1e-9
    assert abs(tk["change_pct"] - 1.25) < 1e-9
    # SOL: last ندارد → fallback به mark
    tk2 = LIT.ticker("SOL", fake_fetch)
    assert tk2 and abs(tk2["last"] - 150) < 1e-9 and abs(tk2["mark"] - 150) < 1e-9
    # نماد ناشناخته/خراب → None
    assert LIT.ticker("NOPE", fake_fetch) is None
    assert LIT.ticker("", fake_fetch) is None
    LIT._reset_for_tests()
    assert LIT.ticker("BTC", lambda u, **k: {"order_book_details": []}) is None


# ---------------------------------------------------------------- lab filter
def t_filter_by_exchange():
    trades = [
        {"exchange": "Lighter", "symbol": "BTC"},
        {"exchange": "KuCoin", "symbol": "ETH"},
        {"exchange": "lighter", "symbol": "SOL"},             # بزرگ/کوچک فرق دارد
        {"symbol": "NO-EX"},
        "junk",
    ]
    # «همه» → بدون فیلتر (رفتار قبلی، حتی ردیف‌های خراب)
    assert LAB.filter_by_exchange(trades, "همه") == trades
    assert LAB.filter_by_exchange(trades, "All") == trades
    assert LAB.filter_by_exchange(trades, "") == trades
    assert LAB.filter_by_exchange(trades, None) == trades
    # فیلتر دقیق و حساس به بزرگی حرف
    got = LAB.filter_by_exchange(trades, "Lighter")
    assert got == [{"exchange": "Lighter", "symbol": "BTC"}]
    assert LAB.filter_by_exchange(trades, "KuCoin") == [{"exchange": "KuCoin", "symbol": "ETH"}]
    assert LAB.filter_by_exchange(trades, "Binance") == []
    # ورودی خراب
    assert LAB.filter_by_exchange(None, "همه") == []
    assert LAB.filter_by_exchange("junk", "Lighter") == []


def t_pages_compile():
    import py_compile
    for rel in ("pages/2_Live_Trading.py", "pages/5_Agent_Lab.py"):
        py_compile.compile(os.path.join(BASE_DIR, rel), doraise=True)
    # ماژول‌های صفحه هم import شوند تا خطای سطح ماژول زود پیدا شود
    import importlib
    spec = importlib.util.find_spec("core.lighter")
    assert spec is not None


if __name__ == "__main__":
    print("core/lighter.py + LAB.filter_by_exchange — Lighter everywhere")
    check("symbol normalize", t_normalize)
    check("markets parse + cache", t_markets_parse_and_cache)
    check("markets bad responses", t_markets_bad_responses)
    check("market id resolve", t_market_id)
    check("active symbols", t_symbols)
    check("ticker shape", t_ticker)
    check("lab exchange filter", t_filter_by_exchange)
    check("pages compile", t_pages_compile)
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)
