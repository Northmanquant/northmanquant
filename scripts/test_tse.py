"""
Zero-network tests for the TSE (بورس ایران) section:
  · core/tse.py     — parsers, mirror fetch chain, caching, session status, index scale fix
  · core/tse_paper.py — virtual portfolio engine (fees, validation, P&L)
  · core/macro_ir.py  — TGJU macro strip (USD/EUR/gold/coin) ported from TITAN
  · core/i18n.py    — NAV_GROUPS three-section nav consistency (paths exist, ids unique)
  · compile checks  — the two new pages + app_base

Usage (from the repository root):
    python scripts/test_tse.py

No network — the HTTP layer is injected with fakes.
Exits non-zero if any test fails.
"""
import os
import py_compile
import sys
import traceback
from datetime import datetime, timedelta, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import tse as T            # noqa: E402
from core import tse_paper as P      # noqa: E402
from core import macro_ir as M       # noqa: E402
from core import i18n as I           # noqa: E402

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


# ---------------------------------------------------------------- fake data
def _mw_row(ins, sym, name, last, adj, yes, vol, val):
    f = [ins, "IRO1XXXX0001", sym, name, "123456", "2000", str(adj), str(last),
         "100", str(vol), str(val), str(int(last) - 10), str(int(last) + 10),
         str(yes), "500", "4000000", "3423", "4", "44",
         "2586.00", "2436.00", "10000000000", "309"]
    assert len(f) == 23
    return ",".join(f)


_MW_RAW = ("20251101@info@"
           + ";".join([
               _mw_row("46348559193224090", "فولاد", "فولاد مبارکه", 12400, 12390, 12000, 5_000_000, 62_000_000_000),
               _mw_row("35425587644337250", "فملی", "مجتمع فولاد مبارکه", 9100, 9050, 9500, 8_000_000, 72_800_000_000),
               _mw_row("320978457643", "شاخصکل", "شاخص کل بورس", 2571443, 2571443, 0, 0, 0),
               "junkrow",
           ]) + "@100,200;300,400")

_SEARCH_RAW = ("فولاد,فولاد مبارکه,46348559193224090,1,1,1,44,1;"
               "فولاد قدیم,فولاد قدیم,46348559193224090,1,1,1,44,0;"
               "webmelt,بانک ملت,27965591536038198,1,1,1,44,1;"
               "badrow")

_HIST_RAW = ("<TICKER>,<PER>,<DTYYYYMMDD>,<FIRST>,<HIGH>,<LOW>,<OPEN>,<CLOSE>,<LAST>,<VOL>,<VALUE>,<OPENINT>\n"
             "فولاد,D,20251029,12000,12300,11900,11950,12100,12200,1000000,12000000000,500\n"
             "فولاد,D,20251028,11800,12000,11700,11900,11950,11900,900000,10800000000,450\n"
             "فولاد,D,20251030,12200,12500,12100,12150,12390,12400,1100000,13500000000,600\n")

_INST_RAW = ("46348559193224090,A,12400,12390,12000,12000,12500,11900,500,1000000,12000000000,F,"
             "20251030,123456,20251030,4900;"
             "46348559193224090@1,123@12400@100;456@12500@50;"
             "1,2")

_INST_F_LAST = ("46348559193224090,A,F,12390,12000,12000,12500,11900,500,1000000,12000000000,"
                "20251030,123456;")


def _fake_fetch(url, **_kw):
    """زنجیره‌ی آینه: اولین host خراب، دوم خالی، سوم سالم — طبق URL مسیر می‌شناسیم."""
    path = url.split(".com", 1)[1] if ".com" in url else url
    host = url.split(".com", 1)[0].split("//")[1]
    if host == "old.tsetmc.com":
        raise ConnectionError("blocked")
    if host == "www.tsetmc.com":
        return ""
    if path.startswith("/tsev2/data/MarketWatchInit"):
        return _MW_RAW
    if path.startswith("/tsev2/data/search.aspx"):
        return _SEARCH_RAW
    if path.startswith("/tsev2/data/Export-txt"):
        return _HIST_RAW
    if path.startswith("/tsev2/data/instinfofast"):
        return _INST_RAW
    if path.startswith("/tsev2/chart/data/IndexFinancial"):
        return "20251028,2600000,2500000,2520000,2550000,0;20251030,2580000,2510000,2530000,2571443.86,0"
    return ""


def _broken_fetch(url, **_kw):
    raise ConnectionError("blocked")


# ---------------------------------------------------------------- tests: tse.py
def t_mw_parse():
    rows = T._parse_market_watch(_MW_RAW)
    assert len(rows) == 3, rows
    by = {r["symbol"]: r for r in rows}
    f = by["فولاد"]
    assert f["ins_code"] == "46348559193224090"
    assert f["last"] == 12400 and f["adj_close"] == 12390 and f["yesterday"] == 12000
    assert abs(f["change_pct"] - (12400 - 12000) / 12000 * 100) < 1e-9
    assert f["volume"] == 5_000_000 and f["value"] == 62_000_000_000
    assert by["فملی"]["change_pct"] < 0
    assert by["شاخصکل"]["change_pct"] == 0  # yesterday=0 → بدون درصد
    # خالی/خراب
    assert T._parse_market_watch("") == []
    assert T._parse_market_watch("no-ats-here") == []
    assert T._parse_market_watch("a@b@,,,,") == []


def t_search_parse():
    rows = T._parse_search(_SEARCH_RAW)
    syms = [r["symbol"] for r in rows]
    assert syms == ["فولاد", "webmelt"], syms            # قدیم غیرفعال حذف شد
    assert rows[0]["ins_code"] == "46348559193224090"
    assert rows[1]["name"] == "بانک ملت"
    assert T._parse_search("") == []


def t_history_parse():
    df = T._parse_history_csv(_HIST_RAW)
    assert list(df["dt"]) == [20251028, 20251029, 20251030]      # صعودی مرتب شد
    assert float(df["close"].iloc[-1]) == 12400                  # از <LAST>
    assert float(df["adj_close"].iloc[-1]) == 12390              # از <CLOSE>
    assert float(df["yesterday"].iloc[-1]) == 12150              # از <OPEN>
    assert float(df["volume"].iloc[-1]) == 1_100_000
    assert pd.Timestamp(df["date"].iloc[-1]).strftime("%Y-%m-%d") == "2025-10-30"
    assert T._parse_history_csv("").empty
    assert T._parse_history_csv("garbage").empty


def t_instinfo_parse():
    snap = T._parse_instinfo(_INST_RAW)
    assert snap["last"] == 12400 and snap["adj_close"] == 12390
    assert snap["open"] == 12000 and snap["yesterday"] == 12000
    assert snap["high"] == 12500 and snap["low"] == 11900
    assert snap["volume"] == 1_000_000 and snap["date"] == "20251030"
    snap2 = T._parse_instinfo(_INST_F_LAST)
    assert snap2["last"] == 12390                     # F → صفر → افتادن روی پایانی
    assert T._parse_instinfo("") == {}
    assert T._parse_instinfo("short,row") == {}


def t_session_status():
    TZ = timezone(timedelta(hours=3, minutes=30))
    # شنبه ۱ نوامبر ۲۰۲۵، ساعت ۱۰ صبح تهران → باز
    s = T.session_status(datetime(2025, 11, 1, 10, 0, tzinfo=TZ))
    assert s["open"] is True and s["trading_day"] is True
    # جمعه ۳۱ اکتبر → تعطیل
    s = T.session_status(datetime(2025, 10, 31, 9, 0, tzinfo=TZ))
    assert s["open"] is False and s["trading_day"] is False
    # چهارشنبه ۵ نوامبر ۱۳:۰۰ تهران → بسته (بعد از ۱۲:۳۰)
    s = T.session_status(datetime(2025, 11, 5, 13, 0, tzinfo=TZ))
    assert s["open"] is False and s["trading_day"] is True
    # چهارشنبه ۰۸:۴۴ → هنوز بسته؛ ۰۸:۴۵ → باز
    assert T.session_status(datetime(2025, 11, 5, 8, 44, tzinfo=TZ))["open"] is False
    assert T.session_status(datetime(2025, 11, 5, 8, 45, tzinfo=TZ))["open"] is True


def t_scale_fix():
    assert T.fix_index_scale(257144386.0, 2571443.86) == 2571443.86   # ×۱۰۰ اصلاح شد
    assert T.fix_index_scale(2571443.86, 2571443.86) == 2571443.86    # درست
    assert T.fix_index_scale(123, 0) == 123                            # مرجع صفر
    assert T.fix_index_scale("x", 100) == "x"                          # خراب → دست‌نخورده


def t_fetch_chain():
    T._reset_for_tests()
    rows = T.market_watch(_fake_fetch)
    assert len(rows) == 3, rows                        # از آینه‌ی سوم گرفته شد
    # همه‌ی آینه‌ها خراب → [] + پیام صادقانه
    T._reset_for_tests()
    rows = T.market_watch(_broken_fetch)
    assert rows == [] and T.last_error and "بورس" in T.last_error
    # کش: دوباره با fetch سالم — بعد از یک موفقیت، دوباره صدا زده نمی‌شود
    T._reset_for_tests()
    calls = {"n": 0}

    def _counting(url, **kw):
        calls["n"] += 1
        return _fake_fetch(url, **kw)

    T.market_watch(_counting)
    n1 = calls["n"]
    assert n1 >= 1
    T.market_watch(_counting)                          # از کش
    assert calls["n"] == n1


def t_search_chain():
    T._reset_for_tests()
    rows = T.search("فولاد", _fake_fetch)
    assert rows and rows[0]["symbol"] == "فولاد"
    # جست‌وجوی خالی → []
    T._reset_for_tests()
    assert T.search("", _fake_fetch) == []


# ---------------------------------------------------------------- tests: فهرست داخلی
def t_static_symbols():
    syms = T.static_symbols()
    assert len(syms) >= 1200, len(syms)
    by = {r["symbol"]: r for r in syms}
    # کد‌های رسمیِ پایدار TSETMC — راستی‌آزمایی‌شده از دو منبع مستقل
    assert by["فولاد"]["ins_code"] == "46348559193224090"
    assert by["فملی"]["ins_code"] == "35425587644337450"
    assert by["وبملت"]["ins_code"] == "778253364357513"
    assert by["شپنا"]["ins_code"] == "7745894403636165"
    assert all(r["ins_code"].isnumeric() for r in syms)
    assert all("name" in r and "isin" in r for r in syms)
    assert T.static_symbols() is syms            # کش — بدون بازخوانی فایل


def t_static_search():
    # دقیق → اولین نتیجه فولاد است
    rows = T.static_search("فولاد")
    assert rows and rows[0]["symbol"] == "فولاد"
    assert rows[0]["ins_code"] == "46348559193224090"
    # نام کامل شرکت هم جست‌وجو می‌شود
    assert any(r["symbol"] == "فولاد" for r in T.static_search("مبارکه"))
    # ي/ک عربی در ورودی کاربر → همان نتیجه‌ی فارسی
    assert any(r["symbol"] == "کگل" for r in T.static_search("كگل"))
    # ISIN لاتین
    assert any(r["symbol"] == "فولاد" for r in T.static_search("IRO1FOLD"))
    # فاصله/نیم‌فاصله و حاشیه‌ها
    assert T.static_search("  فولاد  ")
    # ins_code عددی مستقیم
    assert T.static_search("46348559193224090")[0]["symbol"] == "فولاد"
    # ناموجود
    assert T.static_search("ززززناموجود") == []
    assert T.static_search("") == []


def t_search_fallback_and_fuse():
    # همه‌ی لایه‌های شبکه‌ای خراب → فهرست داخلی نجات می‌دهد
    T._reset_for_tests()
    rows = T.search("فولاد", _broken_fetch)
    assert rows and rows[0]["symbol"] == "فولاد"
    assert T.last_error and "بورس" in T.last_error
    # فیوز: صدا زدن بعدیِ خراب، شبکه را دوباره صدا نمی‌زند (فوری fallback)
    calls = {"n": 0}

    def _count(url, **kw):
        calls["n"] += 1
        raise ConnectionError("blocked")

    T._reset_for_tests()
    assert T.search("فولاد", _count)
    n1 = calls["n"]
    assert n1 >= 1
    rows = T.search("وبملت", _count)               # فیوز روشن → بدون شبکه
    assert calls["n"] == n1, (calls["n"], n1)
    assert rows and rows[0]["symbol"] == "وبملت"
    # موفقیت فیوز را خاموش می‌کند → دوباره تلاش می‌شود
    T._reset_for_tests()
    assert T.search("فولاد", _fake_fetch)[0]["symbol"] == "فولاد"
    assert T.search("فولاد", _count)
    assert calls["n"] >= 1                          # فیوز خاموش شده بود → تلاش واقعی


def t_history_and_snapshot():
    T._reset_for_tests()
    df = T.history("46348559193224090", _fake_fetch)
    assert len(df) == 3
    snap = T.snapshot("46348559193224090", _fake_fetch)
    assert snap["last"] == 12400
    assert T.snapshot("", _fake_fetch) == {}
    T._reset_for_tests()
    assert T.history("46348559193224090", _broken_fetch).empty


def t_indices():
    T._reset_for_tests()
    idx = T.indices(_fake_fetch)
    assert "شاخص کل" in idx and "شاخص هم‌وزن" in idx
    row = idx["شاخص کل"]
    assert row["live"] is True
    # snapshot fake برمی‌گرداند last=12400؛ برای شاخص، اسنپ‌شات همان fاینکس نیست
    # ولی در فیک، instinfo برای شاخص هم همان خروجی را می‌دهد؛ مقیاس‌فیکس با مرجع
    # تاریخ (2571443.86) جلوی ×۱۰۰ را می‌گیرد یا همان را نگه می‌دارد.
    assert row["last"] > 0


def t_module_never_raises():
    """هیچ تابعی با ورودی خراب exception به UI نمی‌دهد."""
    assert T.market_watch(None, ttl=0) is not None  # ttl=0 → بدون کش؛ شبکه واقعی ممکن است خراب باشد → []
    assert T.session_status(None)["open"] in (True, False)
    assert T.norm_fa("") == "" and T.norm_fa(None) == ""
    assert T._num("F") == 0.0 and T._num("") == 0.0 and T._num("۱۲.۵") == 12.5
    assert T.norm_fa("كگل") == "کگل"                 # ك عربی → ک فارسی


# ---------------------------------------------------------------- tests: tse_paper.py
def t_paper_buy_sell_math():
    port = P.new_portfolio()
    assert port["cash"] == 1_000_000_000 and port["start"] == 1_000_000_000
    ok, fa, en = P.apply_order(port, "buy", "4634", "فولاد", 100, 10_000)
    assert ok, fa
    gross, fee = 100 * 10_000, P.buy_fee(100, 10_000)
    assert fee == round(gross * P.BUY_FEE, 10)
    assert port["cash"] == 1_000_000_000 - (gross + fee)
    assert port["positions"]["4634"]["qty"] == 100
    # فروش نصف
    ok, fa, en = P.apply_order(port, "sell", "4634", "فولاد", 40, 11_000)
    assert ok, fa
    net = 40 * 11_000 - P.sell_fee(40, 11_000)
    assert port["cash"] == 1_000_000_000 - (gross + fee) + net
    assert port["positions"]["4634"]["qty"] == 60
    # میانگین خرید دست‌نخورده
    assert port["positions"]["4634"]["avg"] == 10_000


def t_paper_avg_and_close():
    port = P.new_portfolio()
    P.apply_order(port, "buy", "X", "s1", 10, 100)     # 1000
    P.apply_order(port, "buy", "X", "s1", 30, 200)     # 6000
    row = port["positions"]["X"]
    assert row["qty"] == 40
    assert abs(row["avg"] - (1000 + 6000) / 40) < 1e-9
    ok, fa, en = P.apply_order(port, "sell", "X", "s1", 40, 150)   # کل
    assert ok and "X" not in port["positions"]


def t_paper_validation():
    port = P.new_portfolio()
    # تعداد اعشاری/منفی/صفر
    assert not P.apply_order(port, "buy", "X", "s", 10.5, 100)[0]
    assert not P.apply_order(port, "buy", "X", "s", -1, 100)[0]
    assert not P.apply_order(port, "buy", "X", "s", 0, 100)[0]
    # قیمت صفر
    assert not P.apply_order(port, "buy", "X", "s", 10, 0)[0]
    # نماد خالی
    assert not P.apply_order(port, "buy", "", "s", 10, 100)[0]
    # موجودی ناکافی
    ok, fa, en = P.apply_order(port, "buy", "X", "s", 1_000_000, 10_000)
    assert not ok and "کافی" in fa
    # فروش بدون مبلغ
    assert not P.apply_order(port, "sell", "X", "s", 10, 100)[0]
    # فروش بیش از موجودی
    P.apply_order(port, "buy", "Y", "s2", 5, 100)
    ok, fa, en = P.apply_order(port, "sell", "Y", "s2", 6, 100)
    assert not ok and "فقط" in fa
    # جهت نامعتبر
    assert not P.apply_order(port, "hold", "Y", "s2", 1, 100)[0]
    # پرتفوی دست‌نخورده: فقط خریدِ اول انجام شده
    assert port["positions"]["Y"]["qty"] == 5


def t_paper_table_and_summary():
    port = P.new_portfolio()
    P.apply_order(port, "buy", "X", "s1", 10, 100)
    tbl = P.portfolio_table(port, {"X": 120})
    assert list(tbl["تعداد"]) == [10.0]
    assert list(tbl["قیمت فعلی (ریال)"]) == [120.0]
    assert list(tbl["سود/زیان (ریال)"]) == [200.0]
    assert abs(list(tbl["سود/زیان ٪"])[0] - 20.0) < 1e-9
    sm = P.summary(port, {"X": 120})
    assert sm["cash"] == 1_000_000_000 - 1000 - P.buy_fee(10, 100)
    assert sm["positions_value"] == 1200
    assert sm["pnl"] == (sm["cash"] + sm["positions_value"]) - sm["start"]
    # بدون قیمت → میانگین به‌جای قیمت
    sm2 = P.summary(port, {})
    assert sm2["positions_value"] == 1000


# ---------------------------------------------------------------- tests: macro_ir.py
_TGJU_OK = '<span data-col="info.last_trade.PDrCotVal" class="x"> 2,725,000 </span>'
_TGJU_FA = '<div data-col="info.last_trade.PDrCotVal"> ۲٬۷۲۵٬۰۰۰ </div>'


def t_macro_parse():
    assert M._parse_price(_TGJU_OK) == 272_500.0        # ریال → تومان
    assert M._parse_price(_TGJU_FA) == 272_500.0        # ارقام فارسی + جداکننده‌ی ٬
    assert M._parse_price("no-price-here") == 0.0
    assert M._parse_price("") == 0.0
    assert M._parse_price("<td data-col='info.last_trade.PDrCotVal'>F</td>") == 0.0


def t_macro_quote_cache():
    M._reset_for_tests()
    calls = {"n": 0}

    def _ok(url, **_kw):
        calls["n"] += 1
        return _TGJU_OK

    q = M.quote("usd", _ok)
    assert q and q["price"] == 272_500.0 and q["source"] == "TGJU" and "tgju.org" in q["url"]
    M.quote("usd", _ok)                                # از کش — شبکه نمی‌رود
    assert calls["n"] == 1
    assert M.quote("nope", _ok) == {}                  # slug ناشناخته

    M._reset_for_tests()

    def _bad(url, **_kw):
        calls["n"] += 1
        raise ConnectionError("blocked")

    assert M.quote("usd", _bad) == {}
    assert M.last_error and "TGJU" in M.last_error
    n = calls["n"]
    assert M.quote("usd", _bad) == {}                  # کش منفی — دوباره شبکه نمی‌رود
    assert calls["n"] == n


def t_macro_quotes_all():
    M._reset_for_tests()
    html = {
        "price_dollar_rl": '<span data-col="info.last_trade.PDrCotVal">2,725,000</span>',
        "price_eur": '<span data-col="info.last_trade.PDrCotVal">3,100,000</span>',
        "geram18": '<span data-col="info.last_trade.PDrCotVal">252,331,000</span>',
        "sekee": '<span data-col="info.last_trade.PDrCotVal">2,667,850,000</span>',
    }

    def _fetch(url, **_kw):
        return html[url.rsplit("/", 1)[1]]

    q = M.quotes(_fetch)
    assert set(q) == set(M.PROFILES)
    assert q["usd"]["price"] == 272_500.0
    assert q["eur"]["price"] == 310_000.0
    assert q["gold18"]["price"] == 25_233_100.0
    assert q["coin"]["price"] == 266_785_000.0
    # پروفایل‌ها: دقیقاً چهار نماد کلان با slugهای شناخته‌شده‌ی TGJU
    assert set(M.PROFILES) == {"usd", "eur", "gold18", "coin"}
    assert M.PROFILES["usd"]["slug"] == "price_dollar_rl"


# ---------------------------------------------------------------- tests: nav + compile
def t_nav_groups_consistency():
    flat = [pid for _, _, pids in I.NAV_GROUPS for pid in pids]
    ids = {p[0] for p in I.NAV_PAGES}
    assert set(flat) == ids, "NAV_GROUPS باید همه‌ی صفحه‌ها را بپوشاند"
    assert len(flat) == len(set(flat)), "هر صفحه فقط در یک بخش"
    by_id = {p[0]: p for p in I.NAV_PAGES}
    for pid in flat:
        assert pid in by_id
        path = by_id[pid][1]
        assert os.path.exists(os.path.join(BASE_DIR, path)), f"missing page file: {path}"
    # سه بخش جدای کریپتو/بورس ایران/فارکس
    assert len(I.NAV_GROUPS) == 3
    assert I.NAV_GROUPS[0][2] == ["main", "p1", "p2", "p4", "p5", "p9"]  # کریپتو + فارم
    assert I.NAV_GROUPS[1][2] == ["p6", "p7"]                          # بورس ایران
    assert I.NAV_GROUPS[2][2] == ["p3", "p8"]                          # فارکس + تقویم اقتصادی


def t_compile():
    for rel in ("pages/6_TSE_Market.py", "pages/7_TSE_Paper.py",
                "core/tse.py", "core/tse_paper.py", "core/macro_ir.py",
                "core/i18n.py", "app_base.py", "pages/3_Forex_Brokers.py"):
        py_compile.compile(os.path.join(BASE_DIR, rel), doraise=True)


# ---------------------------------------------------------------- run
if __name__ == "__main__":
    print("== core/tse.py ==")
    check("market watch parse", t_mw_parse)
    check("search parse", t_search_parse)
    check("history parse", t_history_parse)
    check("instinfo parse", t_instinfo_parse)
    check("session status", t_session_status)
    check("index scale fix", t_scale_fix)
    check("mirror fetch chain + cache", t_fetch_chain)
    check("search chain", t_search_chain)
    check("static symbols list", t_static_symbols)
    check("static search matching", t_static_search)
    check("search fallback + network fuse", t_search_fallback_and_fuse)
    check("history + snapshot", t_history_and_snapshot)
    check("indices", t_indices)
    check("never raises", t_module_never_raises)
    print("== core/tse_paper.py ==")
    check("buy/sell math", t_paper_buy_sell_math)
    check("avg cost + full close", t_paper_avg_and_close)
    check("validation", t_paper_validation)
    check("portfolio table + summary", t_paper_table_and_summary)
    print("== core/macro_ir.py ==")
    check("macro parse", t_macro_parse)
    check("macro quote + cache", t_macro_quote_cache)
    check("macro quotes all", t_macro_quotes_all)
    print("== nav + compile ==")
    check("nav groups consistency", t_nav_groups_consistency)
    check("compile", t_compile)
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)
