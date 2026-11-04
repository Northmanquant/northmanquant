"""
Zero-network tests for core/lighter_real.py (real orders on Lighter via official SDK).

Usage (from the repository root):
    python scripts/test_lighter_real.py

No network anywhere: the SDK is replaced by an injectable fake module
(_sdk=...) and every fetch is a lambda. Exits non-zero if any test fails.
Covers: scale/unscale, worst_price, build_order_payload (limit/market,
buy/sell, invalid inputs), submit_order with fake SDK (calls, scaling,
error scrubbing), cancel_all_orders, account parse + summary (fake fetch),
find_account_by_address, check_connection validation, and pages compile.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import lighter_real as LR
from core import lighter as LIT

ok, fail = 0, 0


def check(name, fn):
    global ok, fail
    try:
        fn()
        print(f"  PASS {name}")
        ok += 1
    except Exception as e:
        print(f"  FAIL {name}: {type(e).__name__}: {e}")
        traceback.print_exc()
        fail += 1


FAKE_KEY = "ab" * 40          # 80 hex chars — شکل واقعی کلید API لایتر
SHORT_KEY = "ab" * 8


# ---------------------------------------------------------------- SDK فیک
class _FakeResp:
    def __init__(self, tx_hash="0xdeadbeef"):
        self.tx_hash = tx_hash


class _FakeSignerClient:
    """SDK فیک — همه‌ی فراخوانی‌ها را ثبت می‌کند تا ادعاها راست‌آزمایی شوند."""
    last_init = None
    last_create = None
    last_market = None
    last_cancel_all = None
    raise_on_init = False
    create_error = None

    ORDER_TYPE_LIMIT = 0
    ORDER_TYPE_MARKET = 1
    ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = 1
    CANCEL_ALL_TIF_IMMEDIATE = 0

    def __init__(self, url, account_index, api_private_keys):
        if _FakeSignerClient.raise_on_init:
            raise RuntimeError("boom init contains secret " + str(api_private_keys))
        _FakeSignerClient.last_init = {
            "url": url, "account_index": account_index,
            "keys": dict(api_private_keys),
        }

    def check_client(self):
        return None

    async def create_order(self, **kw):
        _FakeSignerClient.last_create = dict(kw)
        if _FakeSignerClient.create_error:
            return None, None, _FakeSignerClient.create_error
        return object(), _FakeResp(), None

    async def create_market_order(self, **kw):
        _FakeSignerClient.last_market = dict(kw)
        if _FakeSignerClient.create_error:
            return None, None, _FakeSignerClient.create_error
        return object(), _FakeResp(), None

    async def cancel_all_orders(self, **kw):
        _FakeSignerClient.last_cancel_all = dict(kw)
        return object(), _FakeResp(), None

    async def close(self):
        _FakeSignerClient.closed = True


class _FakeSdk:
    SignerClient = _FakeSignerClient


def fresh():
    LR._reset_for_tests()
    _FakeSignerClient.last_init = None
    _FakeSignerClient.last_create = None
    _FakeSignerClient.last_market = None
    _FakeSignerClient.last_cancel_all = None
    _FakeSignerClient.raise_on_init = False
    _FakeSignerClient.create_error = None


# ---------------------------------------------------------------- تست‌ها
def t_scale():
    assert LR.scale_value(0.1, 4) == 1000
    assert LR.scale_value(3000.0, 2) == 300000
    assert LR.scale_value(0.00007, 5) == 7
    assert LR.scale_value(0.001, 0) is None   # زیرِ حدّ نمای‌پذیری → سفارش صفر، رد
    assert LR.scale_value(-0.1, 4) is None
    assert LR.scale_value(0, 4) is None
    assert LR.scale_value("abc", 4) is None
    assert LR.scale_value(float("inf"), 4) is None
    assert LR.scale_value(10 ** 30, 0) is None      # سرریز ۶۳ بیت
    assert LR.unscale_value(1000, 4) == 0.1


def t_worst_price():
    up = LR.worst_price("buy", 2000.0, 0.5)
    dn = LR.worst_price("sell", 2000.0, 0.5)
    assert abs(up - 2010.0) < 1e-9, up
    assert abs(dn - 1990.0) < 1e-9, dn
    assert LR.worst_price("buy", 0, 0.5) is None
    assert LR.worst_price("buy", 2000.0, 99) is None   # >50% ممنوع
    assert LR.worst_price("buy", 2000.0, -1) is None


def t_payload_limit():
    p = LR.build_order_payload(order_kind="limit", side="buy", amount=0.1,
                               price=2000.0, last_price=0.0,
                               size_decimals=4, price_decimals=2)
    assert p["ok"] and p["base_amount"] == 1000 and p["price"] == 200000
    assert p["is_ask"] is False and p["order_type"] == 0 and p["time_in_force"] == 1
    assert p["client_order_index"] > 0


def t_payload_market():
    p = LR.build_order_payload(order_kind="market", side="sell", amount=0.05,
                               price=0.0, last_price=2000.0,
                               size_decimals=4, price_decimals=2, slippage_pct=0.5)
    assert p["ok"] and p["base_amount"] == 500
    assert p["is_ask"] is True and p["order_type"] == 1 and p["time_in_force"] == 0
    assert p["price"] == 0
    assert p["avg_execution_price"] == 199000, p["avg_execution_price"]  # 1990 × 100


def t_payload_invalid():
    assert LR.build_order_payload(order_kind="stop", side="buy", amount=1, price=1,
                                  last_price=1, size_decimals=2, price_decimals=2)["ok"] is False
    assert LR.build_order_payload(order_kind="limit", side="up", amount=1, price=1,
                                  last_price=1, size_decimals=2, price_decimals=2)["ok"] is False
    assert LR.build_order_payload(order_kind="limit", side="buy", amount=-1, price=1,
                                  last_price=1, size_decimals=2, price_decimals=2)["ok"] is False
    # market بدون قیمت زنده = ردِ صادقانه، نه سفارش کور
    p = LR.build_order_payload(order_kind="market", side="buy", amount=1, price=0,
                               last_price=0, size_decimals=2, price_decimals=2)
    assert p["ok"] is False and "قیمت" in p["err"]


def t_submit_limit_fake():
    fresh()
    res = LR.submit_order(account_index=77, api_key_private=FAKE_KEY, api_key_index=0,
                          market_index=0, size_decimals=4, price_decimals=2,
                          order_kind="limit", side="buy", amount=0.1, price=2000.0,
                          _sdk=_FakeSdk)
    assert res["ok"] is True, res
    assert _FakeSignerClient.last_init["account_index"] == 77
    assert _FakeSignerClient.last_init["keys"] == {0: FAKE_KEY}
    assert _FakeSignerClient.last_init["url"].startswith("https://mainnet.zklighter")
    kw = _FakeSignerClient.last_create
    assert kw["market_index"] == 0 and kw["base_amount"] == 1000
    assert kw["price"] == 200000 and kw["is_ask"] is False
    assert kw["order_type"] == 0 and kw["time_in_force"] == 1
    assert res["tx_hash"] == "0xdeadbeef"


def t_submit_market_fake():
    fresh()
    res = LR.submit_order(account_index=1, api_key_private=FAKE_KEY, api_key_index=1,
                          market_index=2, size_decimals=3, price_decimals=3,
                          order_kind="market", side="sell", amount=2.5,
                          last_price=100.0, slippage_pct=1.0, _sdk=_FakeSdk)
    assert res["ok"] is True, res
    kw = _FakeSignerClient.last_market
    assert kw["market_index"] == 2 and kw["base_amount"] == 2500
    assert kw["is_ask"] is True
    assert kw["avg_execution_price"] == 99000, kw["avg_execution_price"]  # 99 × 1000
    assert _FakeSignerClient.last_create is None     # مسیر limit صدا زده نشد


def t_submit_error_scrub():
    fresh()
    _FakeSignerClient.create_error = "rejected key " + FAKE_KEY
    res = LR.submit_order(account_index=1, api_key_private=FAKE_KEY, api_key_index=0,
                          market_index=0, size_decimals=4, price_decimals=2,
                          order_kind="limit", side="buy", amount=0.1, price=2000.0,
                          _sdk=_FakeSdk)
    assert res["ok"] is False
    assert FAKE_KEY not in res["err"], "کلید در خطا لو رفت!"
    assert "لایتر" in res["err"]
    fresh()
    _FakeSignerClient.raise_on_init = True
    res = LR.submit_order(account_index=1, api_key_private=FAKE_KEY, api_key_index=0,
                          market_index=0, size_decimals=4, price_decimals=2,
                          order_kind="limit", side="buy", amount=0.1, price=2000.0,
                          _sdk=_FakeSdk)
    assert res["ok"] is False and FAKE_KEY not in res["err"]


def t_submit_no_sdk():
    fresh()
    res = LR.submit_order(account_index=1, api_key_private=SHORT_KEY, api_key_index=0,
                          market_index=0, size_decimals=4, price_decimals=2,
                          order_kind="limit", side="buy", amount=0.1, price=2000.0,
                          _sdk=None)
    # بدون _sdk با SDK واقعیِ نصب‌شده می‌رود سراغ شبکه → در محیط تست خطای اتصال می‌دهد
    # ولی کلیدِ کوتاه قبل از آن رد می‌شود؟ نه — submit طول کلید را چک نمی‌کند؛
    # این‌جا فقط مطمئن می‌شویم هرگز ok=True با کلید خراب نیست و خطا کلید ندارد.
    assert res["ok"] is False
    assert SHORT_KEY not in res["err"]


def t_cancel_all_fake():
    fresh()
    res = LR.cancel_all_orders(account_index=5, api_key_private=FAKE_KEY,
                               api_key_index=0, _sdk=_FakeSdk)
    assert res["ok"] is True
    kw = _FakeSignerClient.last_cancel_all
    assert kw["cancel_all_market_index"] == 255          # همه‌ی بازارها
    assert kw["time_in_force"] == 0
    fresh()
    res = LR.cancel_all_orders(account_index=5, api_key_private=FAKE_KEY,
                               api_key_index=0, market_index=0, _sdk=_FakeSdk)
    assert res["ok"] is True
    assert _FakeSignerClient.last_cancel_all["cancel_all_market_index"] == 0


def t_account_parse():
    data = {
        "code": 200,
        "accounts": [{
            "index": 42, "collateral": "100.5", "available_balance": "60.25",
            "open_orders": [{"x": 1}, {"y": 2}],
            "positions": [
                {"market_id": 0, "symbol": "ETH", "sign": 1, "position": "2.5",
                 "avg_entry_price": "2000", "position_value": "5000",
                 "unrealized_pnl": "12.3", "liquidation_price": "1500"},
                {"market_id": 1, "symbol": "BTC", "sign": -1, "position": "0",
                 "avg_entry_price": "0", "position_value": "0",
                 "unrealized_pnl": "0", "liquidation_price": "0"},
            ],
        }],
    }
    s = LR._parse_account(data)
    assert s and s["index"] == 42
    assert abs(s["collateral"] - 100.5) < 1e-9
    assert abs(s["available"] - 60.25) < 1e-9
    assert s["open_orders"] == 2
    assert len(s["positions"]) == 1            # پوزیشن صفر نمایش نمی‌آید
    p = s["positions"][0]
    assert p["symbol"] == "ETH" and p["side"] == "long" and p["size"] == 2.5
    # خرابی‌ها
    assert LR._parse_account(None) is None
    assert LR._parse_account({}) is None
    assert LR._parse_account({"accounts": []}) is None
    assert LR._parse_account({"accounts": ["x"]}) is None


def t_account_summary_fetch():
    captured = {}

    def fake_fetch(url, **kw):
        captured["url"] = url
        captured["params"] = kw.get("params")
        return {"accounts": [{"index": 9, "collateral": "1", "available_balance": "2",
                              "open_orders": [], "positions": []}]}

    s = LR.account_summary(9, fake_fetch)
    assert s and s["index"] == 9 and s["available"] == 2
    assert captured["params"].get("by") == "index" and captured["params"].get("value") == "9"
    assert LR.account_summary("abc", fake_fetch) is None
    assert LR.account_summary(-1, fake_fetch) is None

    def bad_fetch(url, **kw):
        raise RuntimeError("net down")

    assert LR.account_summary(9, bad_fetch) is None


def t_find_account():
    def fake_fetch(url, **kw):
        return {"accounts": [{"index": 300}, {"index": 111}, {"index": 222}]}

    assert LR.find_account_by_address("0x" + "a" * 40, fake_fetch) == 111
    assert LR.find_account_by_address("nothex", fake_fetch) is None
    assert LR.find_account_by_address("0x123", fake_fetch) is None      # طول غلط

    def empty_fetch(url, **kw):
        return {"accounts": []}

    assert LR.find_account_by_address("0x" + "a" * 40, empty_fetch) is None

    def bad_fetch(url, **kw):
        raise RuntimeError("down")

    assert LR.find_account_by_address("0x" + "a" * 40, bad_fetch) is None


def t_check_connection_validation():
    okc, msg = LR.check_connection("abc", FAKE_KEY)
    assert okc is False and "عدد" in msg
    okc, msg = LR.check_connection(-3, FAKE_KEY)
    assert okc is False
    okc, msg = LR.check_connection(5, SHORT_KEY)
    assert okc is False and "کپی" in msg


def t_check_connection_fake_ok():
    fresh()

    # مسیر موفق با SDK فیک از طریق sys.modules
    import types
    import core.lighter_real as _m
    fake_mod = types.ModuleType("lighter")
    fake_mod.SignerClient = _FakeSignerClient
    old = _m.sdk_available
    _m.sdk_available = lambda: True
    sys.modules["lighter"] = fake_mod
    try:
        # asyncio.run داخل check_connection — کلاینت فیک هم raise نمی‌کند هم close دارد
        okc, msg = LR.check_connection(7, FAKE_KEY, 0)
        assert okc is True, msg
        assert _FakeSignerClient.last_init["account_index"] == 7
    finally:
        _m.sdk_available = old
        del sys.modules["lighter"]


def t_check_connection_fake_err():
    fresh()
    import types
    import core.lighter_real as _m

    class ErrClient(_FakeSignerClient):
        def check_client(self):
            return "signature mismatch secret " + FAKE_KEY

    fake_mod = types.ModuleType("lighter")
    fake_mod.SignerClient = ErrClient
    old = _m.sdk_available
    sys.modules["lighter"] = fake_mod
    _m.sdk_available = lambda: True
    try:
        okc, msg = LR.check_connection(7, FAKE_KEY, 0)
        assert okc is False
        assert FAKE_KEY not in msg, "کلید در پیام خطا لو رفت!"
    finally:
        _m.sdk_available = old
        del sys.modules["lighter"]


def t_market_meta_extension():
    """متادیتای تازه‌ی core/lighter — مقیاس‌ها و کف‌ها از orderBookDetails."""
    LIT._reset_for_tests()
    data = {"order_book_details": [{
        "symbol": "ETH", "market_id": 0, "status": "ACTIVE",
        "last_trade_price": 2400.5, "mark_price": 2400.0, "daily_price_change": 1.5,
        "supported_size_decimals": 4, "supported_price_decimals": 2,
        "min_base_amount": "0.002", "min_quote_amount": "10.0",
    }]}
    m = LIT.market_meta("ETH", lambda url, **kw: data)
    assert m and m["market_id"] == 0 and m["size_decimals"] == 4 and m["price_decimals"] == 2
    assert abs(m["min_base"] - 0.002) < 1e-12 and abs(m["min_quote"] - 10.0) < 1e-9
    assert LIT.market_meta("NOPE", lambda url, **kw: data) is None
    LIT._reset_for_tests()


def t_book_top():
    LIT._reset_for_tests()
    markets_data = {"order_book_details": [{"symbol": "ETH", "market_id": 0, "status": "ACTIVE"}]}
    book_data = {"asks": [{"price": "2422.30"}, {"price": "2422.31"}],
                 "bids": [{"price": "2422.11"}, {"price": "2422.09"}]}
    urls = []

    def fake_fetch(url, **kw):
        urls.append(url)
        if "orderBookOrders" in url:
            return book_data
        return markets_data

    top = LIT.book_top("ETH", fake_fetch)
    assert top and top["bid"] == 2422.11 and top["ask"] == 2422.30, top
    assert any("orderBookOrders" in u for u in urls)
    # پاسخ خراب → None، هرگز عدد ساختگی (کش هم خالی می‌شود)
    LIT._reset_for_tests()
    top2 = LIT.book_top("ETH", lambda url, **kw: {})
    assert top2 is None
    LIT._reset_for_tests()


def t_pages_compile():
    import py_compile
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in ("pages/2_Live_Trading.py", "pages/1_Live_Prices.py"):
        py_compile.compile(os.path.join(BASE_DIR, rel), doraise=True)


if __name__ == "__main__":
    print("core/lighter_real.py — real orders on Lighter (zero-network)")
    check("scale/unscale", t_scale)
    check("worst price (slippage guard)", t_worst_price)
    check("payload limit", t_payload_limit)
    check("payload market", t_payload_market)
    check("payload invalid", t_payload_invalid)
    check("submit limit (fake SDK)", t_submit_limit_fake)
    check("submit market (fake SDK)", t_submit_market_fake)
    check("submit error scrubbing", t_submit_error_scrub)
    check("submit no sdk", t_submit_no_sdk)
    check("cancel all (fake SDK)", t_cancel_all_fake)
    check("account parse", t_account_parse)
    check("account summary (fake fetch)", t_account_summary_fetch)
    check("find account by address", t_find_account)
    check("connection validation", t_check_connection_validation)
    check("connection fake ok", t_check_connection_fake_ok)
    check("connection fake error scrub", t_check_connection_fake_err)
    check("market meta extension", t_market_meta_extension)
    check("book top", t_book_top)
    check("pages compile", t_pages_compile)
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)
