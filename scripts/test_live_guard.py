"""
Edge-case + regression tests for core/trade_guard.py + core/trade_log.py
(the safety layer of the Live Trading page).

Usage (from the repository root):
    python scripts/test_live_guard.py

No network — Supabase is either mocked with a fake client or fully absent.
Exits non-zero if any test fails.
"""
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import trade_guard as G
from core import trade_log as TL

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


# ---------------------------------------------------------------------------
def t_notional():
    assert abs(G.notional(0.001, 95000) - 95.0) < 1e-9
    assert G.notional(0, 100) == 0.0
    assert G.notional(1, 0) == 0.0
    assert G.notional(-1, 100) == 0.0
    assert G.notional(None, None) == 0.0
    assert G.notional("abc", "def") == 0.0
    assert G.notional(float("inf"), 2) == 0.0
    assert G.notional(float("nan"), 2) == 0.0
    assert G.notional(2, float("inf")) == 0.0


def t_order_cap():
    assert G.order_cap(None) == 0.0                       # دفتر در دسترس نیست → بسته
    assert G.order_cap(-3) == 0.0
    assert G.order_cap("bad") == 0.0
    assert G.order_cap(0) == min(G.WARMUP_MAX_ORDER_USD, G.MAX_ORDER_USD)
    assert G.order_cap(G.WARMUP_ORDERS - 1) == min(G.WARMUP_MAX_ORDER_USD, G.MAX_ORDER_USD)
    assert G.order_cap(G.WARMUP_ORDERS) == G.MAX_ORDER_USD
    assert G.order_cap(1000) == G.MAX_ORDER_USD
    assert G.WARMUP_MAX_ORDER_USD <= G.MAX_ORDER_USD      # گرم‌کردن هرگز سخت‌گیرتر از کل نیست
    assert G.WARMUP_ORDERS >= 1


def t_check_order_basics():
    ok1, why = G.check_order(0, 100, cap=50, daily_spent=0)
    assert not ok1 and why                                # مقدار صفر
    ok1, why = G.check_order(-1, 100, cap=50, daily_spent=0)
    assert not ok1 and why
    ok1, why = G.check_order(0.5, None, cap=50, daily_spent=0)
    assert not ok1 and why                                # قیمت خراب


def t_check_order_closed_store():
    ok1, why = G.check_order(0.001, 95000, cap=0.0, daily_spent=None)
    assert not ok1 and "بسته" in why and "Paper" in why
    ok1, why = G.check_order(0.001, 95000, cap=None, daily_spent=None)
    assert not ok1 and "بسته" in why                      # cap خراب هم بسته است


def t_check_order_caps():
    # زیر سقف سفارش
    ok1, why = G.check_order(0.0005, 95000, cap=50, daily_spent=0)   # 47.5
    assert ok1 and why == ""
    # دقیقا روی سقف (تا راند)
    ok1, _ = G.check_order(50 / 95000.0, 95000, cap=50, daily_spent=0)
    assert ok1
    # بالای سقف سفارش
    ok1, why = G.check_order(0.001, 95000, cap=50, daily_spent=0)    # 95
    assert not ok1 and "سقف هر سفارش" in why and "50" in why
    # سقف روزانه
    ok1, why = G.check_order(0.0002, 95000, cap=500, daily_spent=G.MAX_DAILY_USD - 10)  # 19
    assert not ok1 and "سقف روزانه" in why
    # دقیقا زیر سقف روزانه
    ok1, _ = G.check_order(0.00005, 95000, cap=500, daily_spent=G.MAX_DAILY_USD - 5)    # 4.75
    assert ok1
    # daily_spent=None با دفتر سالم = صفر
    ok1, _ = G.check_order(0.0001, 95000, cap=50, daily_spent=None)
    assert ok1
    # daily_spent خراب = صفر (نه خطا)
    ok1, _ = G.check_order(0.0001, 95000, cap=50, daily_spent="bad")
    assert ok1


def t_expired():
    now = 1_000_000.0
    assert G.expired(None) is True                        # بدون نشانه = منقضی (سمت امن)
    assert G.expired(0) is True
    assert G.expired(-5) is True
    assert G.expired("garbage") is True
    assert G.expired(float("nan")) is True
    assert G.expired(now, now=now) is False
    assert G.expired(now - 60, now=now) is False
    assert G.expired(now - G.IDLE_TIMEOUT_SEC - 1, now=now) is True
    assert G.expired(now - 100, now=now, timeout=50) is True
    assert G.expired(now - 10, now=now, timeout=50) is False
    # timeout خراب → پیش‌فرض
    assert G.expired(now - 100000, now=now, timeout=-1) is True


def t_preview_build():
    p = G.build_preview(exchange="KuCoin", symbol="BTC/USDT", side="BUY",
                        otype="Market", amount=0.0005, price=95000, cap=50)
    assert p and p["side"] == "buy" and p["otype"] == "market"
    assert abs(p["notional"] - 47.5) < 1e-9 and p["cap"] == 50
    assert p["created"] > 0
    # ورودی خراب
    assert G.build_preview(exchange="x", symbol="s", side="buy", otype="market",
                           amount=0, price=95000, cap=50) is None
    assert G.build_preview(exchange="x", symbol="s", side="buy", otype="market",
                           amount=1, price=0, cap=50) is None
    assert G.build_preview(exchange="x", symbol="s", side="buy", otype="market",
                           amount=1, price=100, cap=0) is None            # دفتر بسته
    assert G.build_preview(exchange="x", symbol="s", side="buy", otype="market",
                           amount=1, price=100, cap="bad") is None
    # sell محافظه‌کارانه: هر چیز غیر buy → sell
    p2 = G.build_preview(exchange="x", symbol="s", side="whatever", otype="?",
                         amount=1, price=2, cap=10)
    assert p2 and p2["side"] == "sell" and p2["otype"] == "market"


def t_preview_stale_and_text():
    now = 5_000_000.0
    p = {"created": now - G.PREVIEW_TTL_SEC - 1, "notional": 47.5, "amount": 0.0005,
         "price": 95000, "symbol": "BTC/USDT", "exchange": "KuCoin", "cap": 50,
         "side": "buy", "otype": "market"}
    assert G.preview_stale(p, now=now) is True
    p["created"] = now - 10
    assert G.preview_stale(p, now=now) is False
    assert G.preview_stale(None) is True
    assert G.preview_stale({"created": 0}) is True
    assert G.preview_stale("junk") is True
    # متن پیش‌نمایش
    fa = G.preview_text(p, en=False)
    assert "سفارش" in fa and "≈" in fa and "47.50" in fa and "BTC/USDT" in fa
    en = G.preview_text(p, en=True)
    assert "Market BUY" in en and "USDT" in en and "cap" in en
    assert G.preview_text(None) == ""
    assert G.preview_text({"notional": 0}) == ""
    assert G.preview_text({"notional": "x"}) == ""
    assert G.preview_text({"notional": 5, "amount": "bad"}) == ""


def t_scrub():
    msg = G.scrub("APIError key=SECRETKEY123 bad", "SECRETKEY123")
    assert "SECRETKEY123" not in msg and "***" in msg
    # کلیدهای کوتاه (<6) عوض نمی‌شوند تا متن خراب نشود
    assert G.scrub("ab ab", "ab") == "ab ab"
    assert G.scrub(None, "x") == ""
    assert G.scrub("plain") == "plain"
    # چند راز هم‌زمان
    msg = G.scrub("k1=A1B2C3D4 k2=E5F6G7H8", "A1B2C3D4", "E5F6G7H8")
    assert "A1B2C3D4" not in msg and "E5F6G7H8" not in msg


def t_filter_real_exchanges():
    ex_map = {"A": "aaa", "B": "bbb", "C": "ccc"}
    out = G.filter_real_exchanges(ex_map, lambda cid: cid in ("aaa", "ccc"))
    assert out == ["A", "C"]
    assert G.filter_real_exchanges(ex_map, lambda cid: False) == []
    assert G.filter_real_exchanges({}, lambda cid: True) == []
    def boom(_):
        raise RuntimeError("no ccxt")
    assert G.filter_real_exchanges(ex_map, boom) == []
    assert G.filter_real_exchanges(None, lambda cid: True) == []


# ---------------------------------------------------------------- trade_log (خالص)
def _iso(dt):
    return dt.isoformat()


def t_log_sum_today():
    now = datetime(2026, 11, 4, 15, 0, tzinfo=timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = [
        {"ts": _iso(now - timedelta(hours=1)), "notional": 40, "mode": "real"},          # امروز
        {"ts": _iso(midnight), "notional": 10, "mode": "real"},                          # مرز روز
        {"ts": _iso(now - timedelta(days=1)), "notional": 999, "mode": "real"},          # دیروز
        {"ts": _iso(now - timedelta(hours=2)), "notional": 70, "mode": "paper"},         # کاغذی
        {"ts": _iso(now - timedelta(hours=2)), "notional": 5, "mode": ""},               # پیش‌فرض real
        {"ts": "garbage", "notional": 500, "mode": "real"},                              # ts خراب
        {"ts": _iso(now - timedelta(hours=3)), "notional": "bad", "mode": "real"},       # notional خراب
        {"ts": _iso(now - timedelta(hours=3)), "notional": -4, "mode": "real"},          # منفی
        "not-a-dict",
    ]
    total = TL._sum_today(rows, now=now)
    assert abs(total - (40 + 10 + 5)) < 1e-9, total
    assert TL._sum_today(None, now=now) == 0.0
    assert TL._sum_today([], now=now) == 0.0
    assert TL._count_real(rows) == 7                      # paper و رشته‌ی خراب حساب نمی‌شوند
    assert TL._count_real(None) == 0


def t_log_no_client():
    """بدون Supabase: همه‌ی APIها امن و «بسته» برمی‌گردند (هرگز raise)."""
    TL._reset_for_tests()
    os.environ.pop("SUPABASE_URL", None)
    os.environ.pop("SUPABASE_KEY", None)
    assert TL._get_client() is None
    assert TL.last_error
    assert TL._fetch_recent() is None
    assert TL.todays_spent() is None
    assert TL.count_real_orders() is None
    assert TL.recent(20) == []
    assert TL.log_real_order(exchange="KuCoin", symbol="BTC/USDT", side="buy",
                             otype="market", amount=0.001, price=95000,
                             notional_usd=95) is False
    # ردیفِ نامعتبر هم False بدون شبکه
    assert TL.log_real_order(exchange="KuCoin", symbol="BTC/USDT", side="buy",
                             otype="market", amount=0, price=95000,
                             notional_usd=95) is False
    assert TL.log_real_order(exchange="KuCoin", symbol="BTC/USDT", side="buy",
                             otype="market", amount=1, price=95000,
                             notional_usd=-1) is False


# ---------------------------------------------------------------- fake supabase client
class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, state):
        self._s = state

    def select(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def insert(self, row):
        self._s["inserted"].append(row)
        return self

    def execute(self):
        self._s["executes"] += 1
        if self._s.get("fail"):
            raise RuntimeError("db down")
        return _FakeResult(self._s["rows"])


class FakeClient:
    def __init__(self, rows=None):
        self.state = {"rows": rows or [], "inserted": [], "executes": 0, "fail": False}

    def table(self, _name):
        return _FakeTable(self.state)


def _with_fake_client(fake, fn):
    TL._reset_for_tests()
    TL._client = fake
    TL._client_checked = True
    try:
        fn()
    finally:
        TL._reset_for_tests()


def t_log_write_and_cache_bust():
    fake = FakeClient()
    state = {"c": fake}

    def run():
        assert TL.log_real_order(exchange="KuCoin", symbol="BTC/USDT", side="BUY",
                                 otype="LIMIT", amount=0.0005, price=95000,
                                 notional_usd=47.5, order_id="ord-1") is True
        ins = fake.state["inserted"]
        assert len(ins) == 1
        row = ins[0]
        assert row["side"] == "buy" and row["otype"] == "limit"
        assert row["notional"] == 47.5 and row["order_id"] == "ord-1"
        assert row["mode"] == "real"
        # ردیف با price خراب: price=None ذخیره می‌شود نه خطا
        assert TL.log_real_order(exchange="KuCoin", symbol="BTC/USDT", side="buy",
                                 otype="market", amount=0.001, price=None,
                                 notional_usd=95) is True
        assert fake.state["inserted"][1]["price"] is None
        # بعد از درج موفق، کش باطل شده باشد
        assert TL._cache_rows is None
        # fail → False و کش دست‌نخورده‌ی «None» می‌ماند
        fake.state["fail"] = True
        assert TL.log_real_order(exchange="x", symbol="s", side="buy", otype="market",
                                 amount=1, price=1, notional_usd=1) is False
        assert TL.last_error

    _with_fake_client(state["c"], run)


def t_log_read_and_cache():
    now = datetime.now(timezone.utc)
    rows = [
        {"ts": _iso(now), "exchange": "KuCoin", "symbol": "BTC/USDT", "side": "buy",
         "otype": "market", "amount": 0.001, "price": 95000, "notional": 95,
         "order_id": "o1", "mode": "real"},
        {"ts": _iso(now - timedelta(days=2)), "exchange": "KuCoin", "symbol": "ETH/USDT",
         "side": "sell", "otype": "limit", "amount": 0.5, "price": 3000,
         "notional": 1500, "order_id": "o2", "mode": "real"},
    ]
    fake = FakeClient(rows)
    calls = {"n": 0}
    orig_exec = _FakeTable.execute

    def counting_execute(self):
        calls["n"] += 1
        return orig_exec(self)

    def run():
        _FakeTable.execute = counting_execute
        try:
            assert TL.todays_spent() is not None
            spent = TL.todays_spent()
            assert abs(spent - 95) < 1e-9, spent                 # فقط ردیف امروز
            assert TL.count_real_orders() == 2
            assert TL.recent(1)[0]["order_id"] == "o1"
            assert TL.recent(0) == []
            # کش: بعد از اولین خواندن، در TTL دوباره fetch نمی‌زند
            base = calls["n"]
            TL.todays_spent()
            TL.count_real_orders()
            assert calls["n"] == base
            # force → دوباره fetch
            TL._fetch_recent(force=True)
            assert calls["n"] == base + 1
        finally:
            _FakeTable.execute = orig_exec

    _with_fake_client(fake, run)


def t_log_read_failure():
    fake = FakeClient()

    def run():
        fake.state["fail"] = True
        assert TL._fetch_recent() is None
        assert TL.todays_spent() is None
        assert TL.count_real_orders() is None
        assert TL.recent(5) == []
        assert TL.last_error

    _with_fake_client(fake, run)


def t_setup_sql():
    sql = TL.SETUP_SQL
    assert "create table if not exists trade_log" in sql
    assert "enable row level security" in sql
    assert "anon insert" in sql and "anon read" in sql
    assert "notional" in sql and "order_id" in sql


if __name__ == "__main__":
    print("core/trade_guard.py + core/trade_log.py — safety layer")
    check("notional math", t_notional)
    check("order cap (warm-up logic)", t_order_cap)
    check("check order basics", t_check_order_basics)
    check("check order closed store", t_check_order_closed_store)
    check("check order caps", t_check_order_caps)
    check("idle expiry", t_expired)
    check("preview build", t_preview_build)
    check("preview staleness + text", t_preview_stale_and_text)
    check("error scrubbing", t_scrub)
    check("real-exchange filter", t_filter_real_exchanges)
    check("ledger sums (today boundary)", t_log_sum_today)
    check("ledger without supabase", t_log_no_client)
    check("ledger write + cache bust", t_log_write_and_cache_bust)
    check("ledger read + cache", t_log_read_and_cache)
    check("ledger read failure", t_log_read_failure)
    check("setup sql", t_setup_sql)
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)
