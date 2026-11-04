"""
Edge-case + regression tests for core/forex.py (live FX majors + broker table).

Usage (from the repository root):
    python scripts/test_forex.py

No network — Yahoo payloads are mocked; broker facts checked structurally.
Exits non-zero if any test fails.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import forex as F

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


def fake_chart(price, prev, *, currency="USD", ts=1793780067, error=None):
    if error:
        return {"chart": {"result": None, "error": error}}
    return {"chart": {"result": [{"meta": {
        "regularMarketPrice": price, "chartPreviousClose": prev,
        "currency": currency, "regularMarketTime": ts}}], "error": None}}


# ---------------------------------------------------------------------------
def t_pairs():
    assert set(F.PAIRS) == {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"}
    for p in F.PAIRS:
        assert F.yahoo_symbol(p) == f"{p}=X"
        assert F.PAIRS[p][0] and F.PAIRS[p][1]  # fa + en names non-empty
    assert F.yahoo_symbol(" eurusd ") == "EURUSD=X"


def t_decimals_and_fmt():
    assert F.decimals_for(1.08) == 5 and F.decimals_for(0.70) == 5
    assert F.decimals_for(154.1) == 3 and F.decimals_for(100.0) == 3
    assert F.decimals_for("bad") == 5
    assert F.fmt_price(None) == "—" and F.fmt_price(0) == "—"
    assert F.fmt_price(1.1245) == "1.12450"
    assert F.fmt_price(158.115) == "158.115"
    assert F.fmt_price("1.2345") == "1.23450"


def t_parse_up():
    d = F._parse_chart(fake_chart(1.1245, 1.1192), "EURUSD")
    assert d and d["pair"] == "EURUSD"
    assert abs(d["price"] - 1.1245) < 1e-9
    assert d["prev_close"] == 1.1192
    assert d["change_pct"] == round((1.1245 - 1.1192) / 1.1192 * 100, 3)
    assert d["change_pct"] > 0 and d["currency"] == "USD" and d["ts"] == 1793780067
    assert d["name_fa"] == "یورو / دلار آمریکا" and d["name_en"] == "Euro / US Dollar"


def t_parse_down_and_jpy():
    d = F._parse_chart(fake_chart(157.5, 158.2, currency="JPY"), "USDJPY")
    assert d and d["change_pct"] < 0 and d["currency"] == "JPY"


def t_parse_bad_payloads():
    assert F._parse_chart(None, "EURUSD") is None
    assert F._parse_chart({}, "EURUSD") is None
    assert F._parse_chart({"chart": {"result": []}}, "EURUSD") is None
    assert F._parse_chart(fake_chart(1, 1, error={"code": "Bad Request",
                                                  "description": "x"}), "EURUSD") is None
    assert F._parse_chart(fake_chart(0, 1), "EURUSD") is None            # price<=0
    assert F._parse_chart(fake_chart(1.2, 0), "EURUSD")["prev_close"] is None
    assert F._parse_chart(fake_chart(1.2, 0), "EURUSD")["change_pct"] == 0.0


def t_unknown_pair_guard():
    # بدون شبکه: جفت ناشناخته فوراً None (گارد قبل از fetch)
    assert F.fetch_quote("NOPE") is None
    assert F.fetch_quote("") is None
    # پارس برای جفت خارج از لیست هم نباید بشکند (نام fallback)
    d = F._parse_chart(fake_chart(1.0, 1.0), "XYZ")
    assert d and d["pair"] == "XYZ" and d["name_fa"] == "XYZ"


def t_fetch_never_raises(monkey=None):
    # get_json که هرچه raise کند → fetch_quote باید None بدهد نه exception
    class Boom:
        def __getattr__(self, _):
            raise RuntimeError("network down")
    orig = F.get_json
    F.get_json = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
    try:
        assert F.fetch_quote("EURUSD") is None
    finally:
        F.get_json = orig


def t_cache():
    calls = {"n": 0}

    def fake_fetch(pair, **kw):
        calls["n"] += 1
        return {"pair": pair, "price": 1.0, "change_pct": 0.0}

    orig_fetch, orig_ttl = F.fetch_quote, F._TTL
    F.fetch_quote, F._TTL = fake_fetch, 60.0
    try:
        F._CACHE.clear()
        q1 = F.fx_quotes(force=True)
        assert set(q1) == set(F.PAIRS) and calls["n"] == 5
        F.fx_quotes()                      # درون TTL → بدون fetch تازه
        assert calls["n"] == 5
        F.fx_quotes(force=True)            # اجبار → دوباره ۵ fetch
        assert calls["n"] == 10
    finally:
        F.fetch_quote, F._TTL = orig_fetch, orig_ttl
        F._CACHE.clear()


def t_cache_failure_not_reported_as_data():
    """خرابی هم کش می‌شود (ضد rate-limit) ولی در خروجی داده حساب نمی‌شود."""
    calls = {"n": 0}

    def fake_fetch(pair, **kw):
        calls["n"] += 1
        return None

    orig_fetch, orig_ttl = F.fetch_quote, F._TTL
    F.fetch_quote, F._TTL = fake_fetch, 60.0
    try:
        F._CACHE.clear()
        assert F.fx_quotes(force=True) == {} and calls["n"] == 5
        assert F.fx_quotes() == {} and calls["n"] == 5   # درون TTL دوباره تلاش نمی‌کند
    finally:
        F.fetch_quote, F._TTL = orig_fetch, orig_ttl
        F._CACHE.clear()


def t_brokers_integrity():
    names = [b["name"] for b in F.BROKERS]
    assert len(F.BROKERS) == 5 and len(set(names)) == 5
    for b in F.BROKERS:
        for key in ("name", "founded", "url", "platforms_fa", "platforms_en",
                    "regs_fa", "regs_en", "min_dep_fa", "min_dep_en",
                    "spread_fa", "spread_en", "demo_fa", "demo_en",
                    "note_fa", "note_en"):
            assert b.get(key), f"missing {key} in {b.get('name')}"
        assert b["url"].startswith("https://")
        assert b["founded"].isdigit()
        # پلتفرم‌ها در هر دو زبان پر و خوانا
        assert F._platforms(b, False) and F._platforms(b, True)
        assert "MT4" in F._platforms(b, True)


def t_broker_rows():
    rows_fa = F.broker_rows("fa")
    rows_en = F.broker_rows("en")
    assert len(rows_fa) == 5 and all(len(r) == 8 for r in rows_fa)
    assert rows_fa[0][0] == "OANDA" and rows_fa[2][3] == "۱۰۰$"      # FOREX.com min dep
    assert rows_en[2][3] == "$100"
    assert rows_fa[0][2] != rows_en[0][2]                            # regs ترجمه می‌شود
    assert "NFA" in rows_en[0][2]
    assert rows_fa[3][4]                                             # FXCM spread


def t_table_html():
    html_fa = F.broker_table_html("fa")
    for b in F.BROKERS:
        assert b["name"] in html_fa
        assert b["url"].replace("https://", "") in html_fa
    assert 'dir="rtl"' in html_fa and "<th>" in html_fa
    assert html_fa.count("<th>") == 8
    assert "⚠️" in html_fa                                           # نکته‌ی ریسک Opofinance
    html_en = F.broker_table_html("en")
    assert 'dir="ltr"' in html_en and "Regulation" in html_en
    assert "بروکر" not in html_en
    # نشت فارسی به نمای EN ممنوع: پلتفرم‌ها همیشه دوزبانه‌اند
    for fa_word in ("پلتفرم", "اپ اختصاصی", "حساب دمو", "حداقل"):
        assert fa_word not in html_en, f"fa leak in EN table: {fa_word}"
    assert "Own web platform" in html_en and "Own app" in html_en


if __name__ == "__main__":
    print("core/forex.py — edge cases & regression")
    check("pairs + yahoo symbols", t_pairs)
    check("decimals + price formatting", t_decimals_and_fmt)
    check("parse chart meta (up)", t_parse_up)
    check("parse chart meta (down/JPY)", t_parse_down_and_jpy)
    check("parse bad payloads", t_parse_bad_payloads)
    check("unknown pair guard", t_unknown_pair_guard)
    check("fetch never raises", t_fetch_never_raises)
    check("60s cache behaviour", t_cache)
    check("failure cached, not data", t_cache_failure_not_reported_as_data)
    check("brokers integrity", t_brokers_integrity)
    check("broker rows fa/en", t_broker_rows)
    check("broker table html", t_table_html)
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)
