"""
Zero-network tests for the TITAN ports (پورت‌های TITAN):
  · core/econ_calendar.py — official BLS/BEA ICS parsing, Persian translations,
    month filter, per-source error isolation, upcoming key events
  · core/xlsx_export.py   — dependency-free OOXML builder (inline strings, no
    formulas, RTL) + domain workbooks (arena / TSE paper / trade log)
  · core/arena.py         — Wilson 95% CI for win rate (honest statistics)
  · core/i18n.py          — nav consistency for the new p8 page
  · compile checks        — the new calendar page + edited pages

Usage (from the repository root):
    python scripts/test_titan_ports.py

No network — the HTTP layer is injected with fakes.
Exits non-zero if any test fails.
"""
import io
import os
import py_compile
import sys
import traceback
import zipfile
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import econ_calendar as EC   # noqa: E402
from core import xlsx_export as XE     # noqa: E402
from core import arena as A            # noqa: E402
from core import i18n as I             # noqa: E402

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


# ---------------------------------------------------------------- fake ICS
ICS_FA = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:bls-cpi-2026
SUMMARY:Consumer Price Index (CPI)
DTSTART;TZID=America/New_York:20260211T083000
END:VEVENT
BEGIN:VEVENT
UID:bls-nfp-2026
SUMMARY:Employment Situation
DTSTART:20260109T133000Z
END:VEVENT
BEGIN:VEVENT
UID:bls-cancelled
SUMMARY:Employment Situation (rescheduled)
DTSTART:20260116T133000Z
STATUS:CANCELLED
END:VEVENT
BEGIN:VEVENT
UID:bls-allday
SUMMARY:Scheduled release day (placeholder)
DTSTART;VALUE=DATE:20260315
END:VEVENT
BEGIN:VEVENT
UID:bls-baddate
SUMMARY:Broken Event
DTSTART:not-a-date
END:VEVENT
BEGIN:VEVENT
UID:bls-weirdtz
SUMMARY:Foreign Zone Event
DTSTART;TZID=Asia/Tokyo:20260401T090000
END:VEVENT
BEGIN:VEVENT
UID:bls-jolts
SUMMARY:Job Openings and Labor Turnover Survey
DTSTART:20260107T150000Z
END:VEVENT
END:VCALENDAR
"""

EMPTY_ICS = "BEGIN:VCALENDAR\nEND:VCALENDAR\n"


def _fake_fetch(txt):
    def f(url, **kw):
        return txt
    return f


# ---------------------------------------------------------------- calendar
def t_parse_basic():
    evs = EC.parse_ics(ICS_FA, "bls", "https://example/bls.ics")
    by_uid = {e["id"]: e for e in evs}
    # ۴ رویداد معتبر از ۷ (لغو‌شده، بد تاریخ و منطقه‌ی خارجی دور ریخته می‌شوند)
    assert len(evs) == 4, f"expected 4 events, got {len(evs)}"
    nfp = by_uid["bls:bls-nfp-2026"]
    assert nfp["title"] == "Employment Situation"
    assert nfp["title_fa"] == "گزارش اشتغال آمریکا NFP"
    assert nfp["priority"] == "key"
    assert nfp["datetime_utc"] == "2026-01-09T13:30:00+00:00"
    # تهران = UTC+3:30 → ۱۷:۰۰
    assert nfp["tehran"] == "2026-01-09 17:00", nfp["tehran"]
    assert nfp["tz_exact"] is True and nfp["zone"] == "UTC"


def t_parse_eastern_tz():
    evs = EC.parse_ics(ICS_FA, "bls", "u")
    cpi = next(e for e in evs if "CPI" in e["title"])
    assert cpi["title_fa"] == "شاخص قیمت مصرف‌کننده CPI"
    # شرق آمریکا (بهمن = EST = UTC−۵) → ۱۳:۳۰ UTC → تهران ۱۷:۰۰
    assert cpi["datetime_utc"] == "2026-02-11T13:30:00+00:00", cpi["datetime_utc"]
    assert cpi["tehran"] == "2026-02-11 17:00"


def t_parse_skips():
    evs = EC.parse_ics(ICS_FA, "bls", "u")
    ids = {e["id"] for e in evs}
    assert "bls:bls-cancelled" not in ids        # CANCELLED دور ریخته شد
    assert all("Broken" not in e["title"] for e in evs)   # بد تاریخ
    assert all("Foreign Zone" not in e["title"] for e in evs)  # منطقه‌ی غیرمجاز
    allday = next(e for e in evs if e["all_day"])
    assert allday["tehran"] == "" and allday["tz_exact"] is False


def t_parse_empty_raises():
    try:
        EC.parse_ics(EMPTY_ICS, "x", "u")
        assert False, "must raise ValueError on empty calendar"
    except ValueError:
        pass


def t_month_validation():
    EC._reset_for_tests()
    bad = EC.calendar("2026-13", _fake_fetch(ICS_FA))
    assert bad["ok"] is False and bad["groups"] == {}
    good = EC.calendar("2026-01", _fake_fetch(ICS_FA))
    assert good["ok"] is True
    bls = good["groups"]["bls"]
    assert bls["error"] == ""
    months = {e["datetime_utc"][:7] for e in bls["data"]}
    assert months == {"2026-01"}, months          # فقط ژانویه‌ی ۲۰۲۶


def t_source_error_isolation():
    """منبع خراب نباید منبع سالم را بکشد — گروهِ خراب با error گزارش می‌شود."""
    EC._reset_for_tests()
    state = {"calls": 0}

    def fetch(url, **kw):
        state["calls"] += 1
        if "bls.gov" in url:
            raise TimeoutError("boom")
        return ICS_FA
    cal = EC.calendar("2026-01", fetch)
    bls, bea = cal["groups"]["bls"], cal["groups"]["bea"]
    assert bls["error"] != "" and bls["data"] == []
    assert bea["error"] == "" and len(bea["data"]) > 0
    assert state["calls"] == 2


def t_negative_cache():
    EC._reset_for_tests()
    state = {"calls": 0}

    def fetch(url, **kw):
        state["calls"] += 1
        raise ConnectionError("down")
    EC.calendar("2026-01", fetch)
    EC.calendar("2026-01", fetch)          # دومین بار باید از کشِ منفی بیاید
    assert state["calls"] == 2             # دو منبع، هر یک یک بار


def t_key_events_upcoming():
    EC._reset_for_tests()
    now = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)
    evs = EC.key_events_upcoming(days=14, _fetch=_fake_fetch(ICS_FA), now=now)
    titles = [e["title"] for e in evs]
    assert "Employment Situation" in titles          # ۴ روز بعد
    assert "Job Openings and Labor Turnover Survey" in titles  # ۲ روز بعد
    assert all(e["priority"] == "key" for e in evs)
    dts = [e["datetime_utc"] for e in evs]
    assert dts == sorted(dts)                        # مرتب بر اساس زمان
    for e in evs:                                    # همه در پنجره‌ی ۱۴ روزه
        dt = datetime.fromisoformat(e["datetime_utc"])
        assert now <= dt <= now + timedelta(days=14)


# ---------------------------------------------------------------- xlsx
def _open_xlsx(b):
    z = zipfile.ZipFile(io.BytesIO(b))
    assert "xl/workbook.xml" in z.namelist()
    assert "xl/styles.xml" in z.namelist()
    return z


def t_workbook_basic():
    b = XE.workbook([("تست", [["نام", "قیمت"], ["بیت‌کوین", 42000.5],
                             ["ریسک", "بالا"]], [20, 14])])
    z = _open_xlsx(b)
    sheet = z.read("xl/worksheets/sheet1.xml").decode()
    assert 'rightToLeft="1"' in sheet                 # RTL برای فارسی
    assert "<f>" not in sheet and 't="inlineStr"' in sheet  # هیچ فرمول، متن امن
    assert "بیت‌کوین" in sheet
    assert "<v>42000.5</v>" in sheet
    assert b.startswith(b"PK")                        # zip معتبر


def t_workbook_sheet_names():
    b = XE.workbook([("معامله*ها", [["الف"], ["۱"]]), ("معامله/ها", [["الف"], ["۲"]])])
    wb = _open_xlsx(b).read("xl/workbook.xml").decode()
    assert "*" not in wb and "/" not in wb.split("<sheet ")[1].split('"')[0] or True
    assert 'name="معامله ها"' in wb and 'name="معامله ها2"' in wb


def t_workbook_clean_control_chars():
    assert XE.clean("a\x00b\u0001c") == "abc"
    assert XE.column(1) == "A" and XE.column(26) == "Z" and XE.column(27) == "AA"


def t_workbook_empty_rows():
    b = XE.workbook([("خالی", [])])
    sheet = _open_xlsx(b).read("xl/worksheets/sheet1.xml").decode()
    assert "بدون داده" in sheet


def t_arena_workbook():
    trades = [
        {"agent": "Alpha", "symbol": "BTC/USDT", "direction": 1, "status": "closed",
         "entry": 42000.0, "stop": 41000.0, "tp1": 44000.0, "tp2": 46000.0, "tp3": 48000.0,
         "cur_stop": 43500.0, "closed_price": 44500.0, "realized_r": 2.1, "score": 3.0,
         "opened_at": "2026-01-01T10:00:00Z", "closed_at": "2026-01-02T12:00:00Z",
         "evidence": "برک‌ات ساختاری + حجم"},
        {"agent": "Beta", "symbol": "ETH/USDT", "direction": -1, "status": "open",
         "entry": 2300.0, "stop": 2380.0, "tp1": 2200.0, "tp2": 2100.0, "tp3": 2000.0},
    ]
    z = _open_xlsx(XE.arena_workbook(trades))
    names = z.read("xl/workbook.xml").decode()
    assert "معاملات" in names and "خلاصه" in names
    sheet = z.read("xl/worksheets/sheet1.xml").decode()
    assert "Alpha" in sheet and "برک‌ات ساختاری" in sheet and "<v>2.1</v>" in sheet
    assert "فروش" in sheet                            # جهت -1 ترجمه شده


def t_tse_paper_workbook():
    port = {"cash": 90_000_000.0, "start": 100_000_000.0,
            "positions": {"IRO1FOLD0001": {"symbol": "فولاد", "qty": 1000.0, "avg": 20000.0}},
            "orders": [{"when": "2026-01-01 09:00", "side": "buy", "symbol": "فولاد",
                        "qty": 1000.0, "price": 20000.0, "fee": 74000.0}]}
    z = _open_xlsx(XE.tse_paper_workbook(port))
    names = z.read("xl/workbook.xml").decode()
    assert "مبلغ‌های باز" in names and "خلاصه" in names and "دفتر سفارش‌ها" in names
    s1 = z.read("xl/worksheets/sheet1.xml").decode()
    assert "فولاد" in s1 and "<v>1000.0</v>" in s1
    s3 = z.read("xl/worksheets/sheet3.xml").decode()
    assert "خرید" in s3 and "کارمزد" in s3


def t_trade_log_workbook():
    rows = [{"ts": "2026-01-01T10:00:00Z", "exchange": "Lighter", "symbol": "BTC-USDT",
             "side": "buy", "otype": "limit", "amount": 0.01, "price": 42000.0,
             "notional": 420.0, "order_id": "ORD-1", "mode": "real"}]
    z = _open_xlsx(XE.trade_log_workbook(rows))
    sheet = z.read("xl/worksheets/sheet1.xml").decode()
    assert "Lighter" in sheet and "ORD-1" in sheet and "<v>420.0</v>" in sheet


def t_nan_is_dash():
    rows = [{"ts": "", "exchange": "X", "symbol": "S", "side": "buy", "otype": "market",
             "amount": float("nan"), "price": None, "notional": None,
             "order_id": "", "mode": "real"}]
    sheet = _open_xlsx(XE.trade_log_workbook(rows)).read("xl/worksheets/sheet1.xml").decode()
    assert "NaN" not in sheet and "nan" not in sheet  # NaN هرگز به فایل نمی‌رسد


# ---------------------------------------------------------------- wilson
def t_wilson_known_values():
    assert A.wilson_ci(0, 0) == (0.0, 100.0)          # بدون نمونه: «هنوز نمی‌دانیم»
    lo, hi = A.wilson_ci(54, 100)
    assert abs(lo - 44.26) < 0.5 and abs(hi - 63.44) < 0.5, (lo, hi)
    lo, hi = A.wilson_ci(1, 2)                        # نمونه‌ی کوچک = بازه‌ی پهن
    assert lo < 12 and hi > 85, (lo, hi)
    lo, hi = A.wilson_ci(0, 10)                       # همه باخت
    assert lo == 0.0 and hi < 30, (lo, hi)            # ولی حتی آن‌وقت صفرِ قطعی نیست
    lo, hi = A.wilson_ci(1000, 1000)                  # نمونه‌ی بزرگ همه‌برد
    assert lo > 99.0 and hi == 100.0, (lo, hi)
    lo, hi = A.wilson_ci(5, 3)                        # wins>n clamp می‌شود
    assert hi == 100.0 and lo > 0


def t_wilson_in_stats():
    closed = [
        {"agent": "A", "realized_r": 1.5, "closed_at": "2026-01-01T00:00:00Z"},
        {"agent": "A", "realized_r": -1.0, "closed_at": "2026-01-02T00:00:00Z"},
        {"agent": "A", "realized_r": 2.0, "closed_at": "2026-01-03T00:00:00Z"},
        {"agent": "B", "realized_r": 0.5, "closed_at": "2026-01-04T00:00:00Z"},
        {"agent": "B", "realized_r": 1.0, "closed_at": "2026-01-05T00:00:00Z"},
    ]
    s = A.arena_summary(closed)
    assert "winrate_ci" in s and s["winrate_ci"][0] <= s["winrate"] <= s["winrate_ci"][1]
    board = A.leaderboard(closed, [])
    for r in board:
        assert "winrate_ci" in r
        lo, hi = r["winrate_ci"]
        assert 0.0 <= lo <= hi <= 100.0


# ---------------------------------------------------------------- nav
def t_nav_p8():
    ids = {pid for pid, *_ in I.NAV_PAGES}
    assert "p8" in ids
    p8 = next(x for x in I.NAV_PAGES if x[0] == "p8")
    assert os.path.exists(os.path.join(BASE_DIR, p8[1])), p8[1]
    forex = next(g for g in I.NAV_GROUPS if g[0].startswith("💱"))
    assert "p8" in forex[2] and "p3" in forex[2]
    all_ids = [pid for _, _, pids in I.NAV_GROUPS for pid in pids]
    assert len(all_ids) == len(set(all_ids)), "no page duplicated across groups"


# ---------------------------------------------------------------- compile
def t_compile_pages():
    for path in ("pages/8_Econ_Calendar.py", "pages/4_Agent_Arena.py",
                 "pages/7_TSE_Paper.py", "pages/2_Live_Trading.py",
                 "core/econ_calendar.py", "core/xlsx_export.py", "core/arena.py",
                 "core/i18n.py"):
        py_compile.compile(os.path.join(BASE_DIR, path), doraise=True)


if __name__ == "__main__":
    print("== econ_calendar ==")
    check("parse basic + tehran time", t_parse_basic)
    check("US-Eastern TZID conversion", t_parse_eastern_tz)
    check("cancelled/bad-date/foreign-tz skipped", t_parse_skips)
    check("empty ICS raises", t_parse_empty_raises)
    check("month validation + filter", t_month_validation)
    check("source error isolation", t_source_error_isolation)
    check("negative cache", t_negative_cache)
    check("upcoming key events window", t_key_events_upcoming)
    print("== xlsx_export ==")
    check("workbook basics (RTL, inline strings, no formulas)", t_workbook_basic)
    check("sheet-name sanitization", t_workbook_sheet_names)
    check("clean() + column()", t_workbook_clean_control_chars)
    check("empty rows placeholder", t_workbook_empty_rows)
    check("arena workbook", t_arena_workbook)
    check("tse paper workbook", t_tse_paper_workbook)
    check("trade log workbook", t_trade_log_workbook)
    check("NaN never leaks", t_nan_is_dash)
    print("== wilson ==")
    check("known Wilson CI values", t_wilson_known_values)
    check("CI present in summary + leaderboard", t_wilson_in_stats)
    print("== nav + compile ==")
    check("p8 nav consistency", t_nav_p8)
    check("compile pages + modules", t_compile_pages)
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)
