#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/test_lab.py — تست فاز ۱۳: کالبدشکافی + آزمایشگاه + گیت پنالتی
اجرا: python3 scripts/test_lab.py   (بدون شبکه — همه‌چیز فیک است)"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ریشه‌ی ریپو

from core import agent_lab as LAB  # noqa: E402
from core import autopsy as AU  # noqa: E402

NOW = datetime.now(timezone.utc)
PASS = 0


def ok(cond, name):
    global PASS
    assert cond, f"FAIL: {name}"
    PASS += 1
    print(f"  ✓ {name}")


def mk(tid, agent, sym, r, *, ex="sl", tp1=False, status="closed",
       d=-1, created_min=90, closed_min=30, interval="1hour"):
    c0 = NOW - timedelta(minutes=created_min + closed_min)
    c1 = NOW - timedelta(minutes=closed_min)
    return {"id": tid, "agent": agent, "symbol": sym, "direction": d,
            "status": status, "interval": interval,
            "created_at": c0.isoformat(),
            "closed_at": c1.isoformat() if status == "closed" else None,
            "realized_r": r, "exit_reason": ex, "tp1_done": tp1}


print("— کالبدشکافی —")
reg = [{"kind": "regime", "direction": 1, "created_at": "2026-01-01T00:00:00Z"}]
t = mk("1", "A", "SOL", -0.5, ex="sl", tp1=False, created_min=90, closed_min=30, d=1)
ok(AU.classify(t, 1, 1) == ["tight_stop", "quick_stop"], "استاپ تنگ + سریع (هم‌جهت رژیم)")
t = mk("2", "A", "SOL", -0.3, ex="timeout", tp1=False, d=1)
ok("timeout_negative" in AU.classify(t, 1, 1), "تایم‌اوت منفی")
t = mk("3", "A", "SOL", -0.2, ex="trail", tp1=True, d=1)
ok("giveback" in AU.classify(t, 1, 1) and "tight_stop" not in AU.classify(t, 1, 1), "سود پس‌داده")
t = mk("4", "A", "SOL", -1.2, ex="sl", tp1=True)
ok("deep_loss" in AU.classify(t, 1, 1), "ضرر عمیق")
t = mk("5", "A", "SOL", -1.0, d=-1)
ok("against_regime" in AU.classify(t, 1, 1), "خلاف رژیم")
t = mk("6", "A", "SOL", -1.0, d=1)
ok("regime_flip" in AU.classify(t, 1, -1) and "against_regime" not in AU.classify(t, 1, -1),
   "برگشت رژیم وسط راه")

print("— زنجیره و سرد شدن —")
seq = [mk(f"s{i}", "A", "X", 1.2, ex="tp3", tp1=True) for i in range(2)] + \
      [mk(f"l{i}", "A", "X", -0.5) for i in range(2)]
ok(LAB.current_streak(LAB.closed_sorted(seq)) == 2, "زنجیره = ۲")
ok(LAB.cool_mult_for(2) == 1.0 and LAB.cool_mult_for(3) == 2.0
   and LAB.cool_mult_for(5) == 3.0 and LAB.cool_mult_for(7) == 4.0, "پلکان ضریب")

print("— تطبیق کامل —")
trades = ([mk(f"a{i}", "A", "SOLUSDT", -1.0, d=-1,
              created_min=6000 + i * 60, closed_min=5900 - i * 60) for i in range(3)]
          + [mk("b0", "A", "BTCUSDT", -1.0, d=-1, created_min=7000, closed_min=660)]
          + [mk("w0", "B", "ETHUSDT", 1.5, ex="tp3", tp1=True, d=1)])
lab = LAB.compute_adaptations(trades, now=NOW, regime_alerts=reg)
ok(lab["counts"]["bans"] == 1, "یک نماد ممنوع")
ok(lab["counts"]["penalized"] == 1, "یک ایجنت سردشده")
ok(lab["agents"]["A"]["cool_mult"] == 2.0, "ضریب A = ×۲")
ok(lab["agents"]["A"]["regime_only"] is True, "انضباط رژیم A فعال (۴/۴ خلاف رژیم)")
ok(lab["agents"]["B"]["cool_mult"] == 1.0, "B سالم")

print("— گیت پنالتی در بازکردن معامله —")
import core.arena as A  # noqa: E402


class FakeStore:
    def __init__(self, rows):
        self.rows = list(rows)

    def load_all(self):
        return self.rows

    def insert(self, rec):
        self.rows.append(rec)
        return True

    def update(self, _tid, _patch):
        return True


def coin(sym, d, q=1.0):
    return {"symbol": sym, "dec": 4, "last_dt": "2026-11-03T00:00:00Z", "adx": 30,
            "agents": {"A": {"ok": True, "dir": d, "quality": q, "score": 1.0,
                             "pos": {"entry": 100.0, "stop": 99.0,
                                     "targets": [(101, 0), (102, 0), (103, 0)], "rr": 3.0},
                             "evidence": "test"}},
            "committee": None}


scans = [coin("SOLUSDT", -1), coin("ETHUSDT", -1), coin("BTCUSDT", -1), coin("XRPUSDT", 1)]
store = FakeStore(trades)
opened, blocked = A.open_trades_from_scan(scans, "KuCoin", "1hour", store,
                                          source="manual", lab=lab, regime_dir=1)
syms_open = [o["symbol"] for o in opened]
ok(syms_open == ["XRPUSDT"], f"فقط هم‌جهت رژیم باز شد ({syms_open})")
ok(blocked >= 3, f"سه مسیر بسته شد (blocked={blocked})")

opened2, _ = A.open_trades_from_scan(scans, "KuCoin", "1hour", store,
                                     source="manual", lab=None, regime_dir=1)
ok(len(opened2) >= 1, "بدون lab — رفتار قدیمی سالم (backward compatible)")

print("— مسیر ریکالیبراسیون (recal_progress) —")
ok(LAB.RECAL_TARGET == 50, "هدف پیش‌فرض ۵۰ معامله (هم‌منبع با گزارش روزانه)")
ok(LAB.recal_progress(None) == {"closed": 0, "target": 50, "pct": 0.0, "ready": False},
   "ورودی None — صفرها، بدون raise")
ok(LAB.recal_progress("garbage")["closed"] == 0, "ورودی غیرلیست امن")
ok(LAB.recal_progress([1, None, "x", {}])["closed"] == 0, "ردیف‌های خراب دور ریخته می‌شوند")
_lighter_trades = [
    {"exchange": "Lighter", "status": "closed"},
    {"exchange": "lighter", "status": "closed"},      # حروف بزرگ/کوچک بی‌اهمیت
    {"exchange": " Lighter ", "status": "CLOSED"},    # فاصله و حالت — بی‌اهمیت
    {"exchange": "Lighter", "status": "open"},        # باز — نمی‌شمرد
    {"exchange": "Lighter", "status": None},          # بی‌وضعیت — نمی‌شمرد
    {"exchange": "Binance", "status": "closed"},      # صرافی دیگر — نمی‌شمرد
    {"exchange": "", "status": "closed"},             # بی‌صرافی — نمی‌شمرد
]
_rp = LAB.recal_progress(_lighter_trades)
ok(_rp["closed"] == 3, f"فقط بسته‌شده‌های لایتر شمرده می‌شوند (closed={_rp['closed']})")
ok(_rp["pct"] == 3 / 50 and not _rp["ready"], "درصد صحیح و هنوز آماده نیست")
_rp2 = LAB.recal_progress([{"exchange": "lighter", "status": "closed"}] * 50)
ok(_rp2["pct"] == 1.0 and _rp2["ready"], "رسیدن به هدف — pct سقف ۱ و ready=True")
_rp3 = LAB.recal_progress([{"exchange": "lighter", "status": "closed"}] * 60)
ok(_rp3["pct"] == 1.0, "عبور از هدف — درصد نمی‌شود بیش از ۱")
_rp4 = LAB.recal_progress([], target=0)
ok(_rp4["target"] == 50, "target نامعتبر (۰) — به پیش‌فرض برمی‌گردد")
_rp5 = LAB.recal_progress(_lighter_trades, target=6)
ok(_rp5["pct"] == 0.5 and _rp5["target"] == 6, "target سفارشی پذیرفته می‌شود")

print(f"\n✅ همه‌ی {PASS} تست فاز ۱۳ پاس شد")
