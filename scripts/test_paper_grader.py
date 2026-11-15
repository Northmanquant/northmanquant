# -*- coding: utf-8 -*-
"""آزمونِ گرِیدرِ پیامد — hit-rateِ واقعی، idempotent و مشترکِ دو موتور
==========================================================================
بدونِ شبکه: fetcherِ تزریقی با کندل‌های قطعیِ ساختگی. صعود/نزود/باندِ مرده،
کلیدِ یکتا و رانِ دومِ بدونِ نمره‌ی تکراری، تاریخچه‌ی ناکافی و fetcherِ
خراب — همه قفل می‌شوند.

اجرا:  python scripts/test_paper_grader.py
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

import pandas as pd  # noqa: E402

from core import paper_grader as PG  # noqa: E402

ok = 0
fail = 0
_TZ = timezone(timedelta(hours=3, minutes=30))


def check(name, fn):
    global ok, fail
    try:
        fn()
        ok += 1
        print(f"  OK   {name}")
    except Exception as exc:  # noqa: BLE001 — گزارشِ آزمون
        fail += 1
        print(f"  FAIL {name}: {type(exc).__name__}: {exc}")


def _ms(y, mo, d, h):
    return int(datetime(y, mo, d, h, tzinfo=_TZ).timestamp() * 1000)


def _fetcher(closes_by_symbol, base_ms=None):
    """fetcherِ ساختگی — به هر نماد، فهرستِ closesِ بعد از ts می‌چسباند."""
    base_ms = base_ms or _ms(2026, 11, 15, 10)

    def fetch(exchange, symbol, interval, limit):
        closes = closes_by_symbol.get(symbol)
        if closes is None:
            return None
        n = len(closes)
        times = [base_ms + i * 3600_000 for i in range(n)]
        ms = pd.Series(times).astype("int64")
        return pd.DataFrame({"time": ms, "open": closes, "high": closes,
                             "low": closes, "close": closes,
                             "volume": [100.0] * n})

    return fetch


def _ledger(dirpath, rows):
    p = os.path.join(dirpath, "ledger.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.write("خطِ خراب\n")
    return p


def _krow(side=1, price=100.0, sym="BTC-USDT", iv="1hour", ts="2026-11-15 10:00"):
    return {"backend": "kronos", "symbol": sym, "interval": iv, "exchange": "OKX",
            "ts": ts, "price": price, "kronos_side": side, "team_side": 1,
            "signal_active": True}


def t1_pending_split_and_exclusion():
    with tempfile.TemporaryDirectory() as td:
        led = _ledger(td, [_krow(side=1), _krow(side=0), _krow(sym="ETH-USDT"),
                           {"backend": "offline", "kronos_side": 1}])
        out = os.path.join(td, "out.jsonl")
        assert len(PG.pending_rows("kronos", led, out)) == 2
        assert PG.pending_rows("nabigha", led, out) == []


def t2_grade_up_hit_true():
    with tempfile.TemporaryDirectory() as td:
        led = _ledger(td, [_krow(side=1, price=100.0)])
        out = os.path.join(td, "out.jsonl")
        fetch = _fetcher({"BTC-USDT": [100.0, 101.0, 102.0, 103.5, 104.0]})
        res = PG.grade_pending("kronos", led, out, fetcher=fetch, horizon=3)
        assert res.get("ok") and res["graded"] == 1 and res["skipped"] == 0, res
        rec = json.loads(open(out, encoding="utf-8").read().strip())
        assert rec["outcome"] == 1 and rec["hit"] is True, rec
        assert rec["price_after"] == 103.5 and rec["move_pct"] == 3.5, rec


def t3_grade_down_and_deadband():
    with tempfile.TemporaryDirectory() as td:
        led = _ledger(td, [_krow(side=1, price=100.0, sym="ETH-USDT", ts="2026-11-15 10:00"),
                           _krow(side=-1, price=100.0, sym="SOL-USDT", ts="2026-11-15 10:00")])
        out = os.path.join(td, "out.jsonl")
        fetch = _fetcher({"ETH-USDT": [100.0, 99.0, 98.0, 97.0, 96.5],
                          "SOL-USDT": [100.0, 100.0, 100.0, 100.02, 100.0]})
        PG.grade_pending("kronos", led, out, fetcher=fetch, horizon=3)
        recs = [json.loads(l) for l in open(out, encoding="utf-8") if l.strip()]
        by = {r["symbol"]: r for r in recs}
        assert by["ETH-USDT"]["hit"] is False and by["ETH-USDT"]["outcome"] == -1
        assert by["SOL-USDT"]["outcome"] == 0 and by["SOL-USDT"]["hit"] is None


def t4_idempotent_second_run():
    with tempfile.TemporaryDirectory() as td:
        led = _ledger(td, [_krow(side=1), _krow(sym="ETH-USDT")])
        out = os.path.join(td, "out.jsonl")
        fetch = _fetcher({"BTC-USDT": [100.0] * 6, "ETH-USDT": [50.0] * 6})
        r1 = PG.grade_pending("kronos", led, out, fetcher=fetch, horizon=3)
        n1 = sum(1 for _ in open(out, encoding="utf-8"))
        r2 = PG.grade_pending("kronos", led, out, fetcher=fetch, horizon=3)
        n2 = sum(1 for _ in open(out, encoding="utf-8"))
        assert r1["graded"] == 2 and r2["graded"] == 0 and n1 == n2 == 2


def t5_missing_history_skipped():
    with tempfile.TemporaryDirectory() as td:
        led = _ledger(td, [_krow(side=1, sym="NO-HIST")])
        out = os.path.join(td, "out.jsonl")
        fetch = _fetcher({"BTC-USDT": [100.0] * 6})  # NO-HIST ندارد
        res = PG.grade_pending("kronos", led, out, fetcher=fetch, horizon=3)
        assert res["graded"] == 0 and res["skipped"] == 1, res
        assert os.path.getsize(out) == 0


def t6_stats_rate_and_by_interval():
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out.jsonl")
        rows = [
            {"engine": "kronos", "key": "a", "symbol": "BTC-USDT", "interval": "1hour",
             "side": 1, "outcome": 1, "hit": True},
            {"engine": "kronos", "key": "b", "symbol": "BTC-USDT", "interval": "4hour",
             "side": 1, "outcome": -1, "hit": False},
            {"engine": "kronos", "key": "c", "symbol": "ETH-USDT", "interval": "1hour",
             "side": -1, "outcome": 0, "hit": None},
        ]
        with open(out, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        st = PG.outcomes_stats("kronos", out)
        assert st["ok"] and st["n_graded"] == 3 and st["n_decided"] == 2, st
        assert st["hits"] == 1 and st["rate"] == 50.0, st
        assert st["by_interval"]["1hour"]["n"] == 1, st


def t7_nabigha_engine_path():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "nabigha_log.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps({"backend": "nabigha", "symbol": "BTC-USDT",
                                "interval": "1hour", "exchange": "OKX",
                                "ts": "2026-11-15 10:00", "price": 100.0,
                                "nabigha_side": -1, "team_side": 1,
                                "signal_active": True}) + "\n")
        out = os.path.join(td, "out.jsonl")
        fetch = _fetcher({"BTC-USDT": [100.0, 99.0, 98.5, 98.0, 97.5]})
        res = PG.grade_pending("nabigha", p, out, fetcher=fetch, horizon=3)
        assert res["graded"] == 1, res
        rec = json.loads(open(out, encoding="utf-8").read().strip())
        assert rec["engine"] == "nabigha" and rec["hit"] is True, rec


def t8_broken_fetcher_never_raises():
    with tempfile.TemporaryDirectory() as td:
        led = _ledger(td, [_krow(side=1)])
        out = os.path.join(td, "out.jsonl")

        def boom(exchange, symbol, interval, limit):
            raise RuntimeError("شبکه مرد")

        res = PG.grade_pending("kronos", led, out, fetcher=boom, horizon=3)
        assert res.get("ok") is True and res["graded"] == 0, res


if __name__ == "__main__":
    print("== آزمونِ گرِیدرِ پیامد ==")
    check("صفِ در انتظار — تفکیکِ موتور و حذفِ بی‌ادعا", t1_pending_split_and_exclusion)
    check("صعود → hitِ درست با قیمتِ افق", t2_grade_up_hit_true)
    check("نزول و باندِ مرده — hit و بی‌نتیجه", t3_grade_down_and_deadband)
    check("idempotence — رانِ دوم هیچ تکراری نمی‌زند", t4_idempotent_second_run)
    check("تاریخچه‌ی ناکافی → skip بدونِ سطر", t5_missing_history_skipped)
    check("آمار — نرخِ واقعی و تفکیکِ تایم‌فریم", t6_stats_rate_and_by_interval)
    check("مسیرِ نبیه — فیلدِ sideِ خودش", t7_nabigha_engine_path)
    check("fetcherِ خراب → هرگز exception نمی‌دهد", t8_broken_fetcher_never_raises)
    print(f"\nنتیجه: {ok} سبز · {fail} قرمز")
    sys.exit(1 if fail else 0)
