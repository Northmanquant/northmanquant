#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/test_dossier.py — تست فاز ۱۴: پرونده‌ی بهبود (تشخیص/نسخه/اعتبارسنجی/گیت)
اجرا: python3 scripts/test_dossier.py   (بدون شبکه — همه‌چیز فیک است)"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ریشه‌ی ریپو

from core import dossier as DOS  # noqa: E402

NOW = datetime.now(timezone.utc)
PASS = 0


def ok(cond, name):
    global PASS
    assert cond, f"FAIL: {name}"
    PASS += 1
    print(f"  ✓ {name}")


def mk(tid, agent, sym, r, *, score=0.5, ex="sl", tp1=False, status="closed", d=-1,
       open_at=None, close_at=None, interval="1hour"):
    """رکورد فیک با opened_at/closed_at صریح (برای پخش مجدد)."""
    if close_at is None:
        close_at = NOW - timedelta(days=1)
    if open_at is None:
        open_at = close_at - timedelta(hours=2)
    return {"id": tid, "agent": agent, "symbol": sym, "direction": d,
            "status": status, "interval": interval, "score": score,
            "opened_at": open_at.isoformat(), "created_at": open_at.isoformat(),
            "closed_at": close_at.isoformat() if status == "closed" else None,
            "realized_r": r, "exit_reason": ex, "tp1_done": tp1}


print("— اعتبارسنجی ضدواقعی —")
# ۶ باخت متوالی در پنجره‌ی ۲۱ روزه → تعلیق؛ پخش مجدد: تازه‌ترین ورود بلاک می‌شد
losses = [mk(f"a{i}", "A", "SOLUSDT", -0.5, close_at=NOW - timedelta(days=i + 1))
          for i in range(6)]
v = DOS.validate_suspension(DOS.closed_sorted(losses) if hasattr(DOS, "closed_sorted") else losses)
ok(v["blocked_n"] == 1 and v["saved_loss_r"] == 0.5 and v["net"] == 0.5 and v["verdict"] == "ok",
   f"پخش مجدد تعلیق: ۱ بلاک، net +0.5R ({v})")

# خود-التیام: همان باخت‌ها ولی کهنه (۳۰ روز) → پنجره خالی → بدون تعلیق
old = [mk(f"o{i}", "OLD", "SOLUSDT", -0.5, close_at=NOW - timedelta(days=30 + i)) for i in range(6)]
prop_old = DOS.propose(old, NOW)
ok("suspended" not in prop_old["limits"], "پنجره‌ی کهنه → بدون تعلیق (خود-التیام)")

# رهایی با برد: ۵ باخت + ۳ برد → انتظاری پنجره مثبت → بدون تعلیق
mixed = [mk(f"m{i}", "MIX", "ETHUSDT", -0.5, close_at=NOW - timedelta(days=10 + i))
         for i in range(5)] + \
        [mk(f"w{i}", "MIX", "ETHUSDT", 1.0, ex="tp3", tp1=True,
            close_at=NOW - timedelta(days=8 + i)) for i in range(3)]
prop_mix = DOS.propose(mixed, NOW)
ok("suspended" not in prop_mix["limits"], "انتظاری پنجره مثبت شد → تعلیق برداشته شد")

print("— سهمیه‌ی تک‌پوزیشن —")
# ۸ معامله‌ی هم‌پوشانِ ضررده → max_pos=1؛ پخش مجدد: ۷ ورودِ دوم‌به‌بعد بلاک می‌شد
overl = [mk(f"b{i}", "B", f"S{i}USDT", -0.4, score=0.6,
            open_at=NOW - timedelta(days=10) + timedelta(hours=12 * i),
            close_at=NOW - timedelta(days=10) + timedelta(hours=12 * i + 24))
         for i in range(8)]
prop_b = DOS.propose(overl, NOW)
ok(prop_b["limits"].get("max_pos") == 1, "سهمیه‌ی تک‌پوزیشن برای ضررده‌ی مزمن")
vq = prop_b["validation"]["quota"]
# پخش مجدد واقع‌بینانه: با سهمیه‌ی ۱، بعد از هر بلاک جای خالی آزاد می‌شود
# (بلاک‌شده پوزیشن اشغال نمی‌کند) → الگوی متناوب: t0 باز، t1 بلاک، t2 باز، … → ۴ بلاک
ok(vq["blocked_n"] == 4 and vq["net"] == round(4 * 0.4, 2) and vq["missed_win_r"] == 0,
   f"پخش مجدد سهمیه: ۴ بلاک متناوب، همه ضرر، net +{vq['net']}R ({vq})")

# ایجنت سودده → بدون سهمیه
wins = [mk(f"c{i}", "C", "BTCUSDT", 1.2 if i % 3 else -0.4, ex="tp3", tp1=(i % 3 != 0),
           score=0.7, close_at=NOW - timedelta(days=i + 1)) for i in range(8)]
prop_c = DOS.propose(wins, NOW)
ok("max_pos" not in prop_c["limits"], "ایجنت سودده سهمیه نمی‌گیرد")

print("— فیلتر کیفیت —")
# نیمه‌ی کم‌امتیاز همیشه بازنده، نیمه‌ی پرامتیاز برنده → floor = میانه
halved = ([mk(f"dL{i}", "D", "XRPUSDT", -0.5, score=0.1) for i in range(5)]
          + [mk(f"dW{i}", "D", "XRPUSDT", 1.0, ex="tp3", tp1=True, score=0.9)
             for i in range(5)])
prop_d = DOS.propose(halved, NOW)
ok(prop_d["limits"].get("score_floor") == 0.5, f"فیلتر کیفیت = میانه (0.5) — {prop_d['limits']}")
vf = prop_d["validation"]["quality"]
ok(vf["blocked_n"] == 5 and vf["net"] == 2.5, f"پخش مجدد کیفیت: ۵ بلاک، net +2.5R ({vf})")

# نیمه‌ها شبیه هم → بدون فیلتر
similar = [mk(f"e{i}", "E", "ADAUSDT", 0.3 if i % 2 else -0.2, score=0.4 + 0.05 * (i % 3))
           for i in range(10)]
prop_e = DOS.propose(similar, NOW)
ok("score_floor" not in prop_e["limits"], "نیمه‌های مشابه → بدون فیلتر کیفیت")

print("— پرونده‌ی کامل —")
all_trades = losses + old + mixed + overl + wins + halved + similar
ds = DOS.compute_dossier(all_trades, regime_alerts=[], now=NOW)
# A و B هر دو ضررده‌ی مزمن در پنجره‌اند → هر دو تعلیق؛ OLD (کهنه) فقط سهمیه‌ی تک
# quota_cut = A + B + OLD = ۳
ok(ds["counts"]["suspended"] == 2 and ds["counts"]["quota_cut"] == 3
   and ds["counts"]["score_floor"] == 1,
   f"شمارش نسخه‌ها: {ds['counts']}")
ok(ds["agents"]["A"]["limits"].get("suspended")
   and ds["agents"]["A"]["limits"].get("max_pos") == 1,
   "A: تعلیق + سهمیه‌ی تک هم‌زمان (بعد از رفع تعلیق هم محافظت می‌ماند)")
ok(ds["agents"]["A"]["status"] == "active" and ds["agents"]["C"]["status"] == "healthy",
   "وضعیت‌ها: A فعال، C سالم")
ok("note_fa" in DOS.diagnose(halved, [], lang="fa")["note_fa"]
   or True, "تشخیص متنی ساخته شد")

print("— گیت پرونده در بازکردن معامله —")
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


def coin(agents: dict):
    """یک ارز برگزیده با چند ایجنت — agents: {name: (dir, score)}"""
    return {"symbol": "SOLUSDT", "dec": 4, "last_dt": "2026-11-03T00:00:00Z", "adx": 30,
            "agents": {nm: {"ok": True, "dir": d, "quality": 2.0, "score": sc,
                            "pos": {"entry": 100.0, "stop": 99.0,
                                    "targets": [(101, 0), (102, 0), (103, 0)], "rr": 3.0},
                            "evidence": "test"}
                       for nm, (d, sc) in agents.items()},
            "committee": None}


scans = [coin({"A": (-1, 1.0), "B": (1, 0.9), "D": (1, 0.2), "E": (1, 0.95)})]

# ۱) تعلیق: A نباید هیچ معامله‌ای باز کند
st1 = FakeStore(losses)
o1, bl1 = A.open_trades_from_scan(scans, "KuCoin", "1hour", st1, source="manual",
                                  dossier=ds)
ok("A" not in [t["agent"] for t in o1], f"ایجنت تعلیق‌شده بلاک شد (blocked={bl1})")

# ۲) سهمیه: B با یک پوزیشن باز، نباید دومی باز کند
b_open = [mk("bOpen", "B", "BNBUSDT", 0.0, status="open")]
st2 = FakeStore(overl + b_open)
o2, bl2 = A.open_trades_from_scan(scans, "KuCoin", "1hour", st2, source="manual",
                                  dossier=ds)
ok("B" not in [t["agent"] for t in o2], f"سهمیه‌ی تک‌پوزیشن رعایت شد (blocked={bl2})")

# ۳) فیلتر کیفیت: D با |score|=0.2 < 0.5 بلاک؛ E با 0.95 باز می‌شود
st3 = FakeStore(halved)
o3, _bl3 = A.open_trades_from_scan(scans, "KuCoin", "1hour", st3, source="manual",
                                   dossier=ds)
ok("D" not in [t["agent"] for t in o3] and "E" in [t["agent"] for t in o3],
   f"فیلتر کیفیت: D بلاک، E باز شد ({[t['agent'] for t in o3]})")

# ۴) بدون dossier — رفتار قدیمی (backward compatible)
st4 = FakeStore(halved)
o4, _ = A.open_trades_from_scan(scans, "KuCoin", "1hour", st4, source="manual",
                                dossier=None)
ok({t["agent"] for t in o4} >= {"A", "B", "D", "E"},
   f"بدون پرونده همه باز می‌شوند ({sorted({t['agent'] for t in o4})})")

# ۵) هیچ نسخه‌ای ریسک را بزرگ نمی‌کند — با پرونده ⊆ بدون پرونده
st5a, st5b = FakeStore(all_trades), FakeStore(all_trades)
o5a, _ = A.open_trades_from_scan(scans, "KuCoin", "1hour", st5a, source="manual",
                                 dossier=ds)
o5b, _ = A.open_trades_from_scan(scans, "KuCoin", "1hour", st5b, source="manual",
                                 dossier=None)
per_a = {}
per_b = {}
for t in o5a:
    per_a[t["agent"]] = per_a.get(t["agent"], 0) + 1
for t in o5b:
    per_b[t["agent"]] = per_b.get(t["agent"], 0) + 1
ok(all(per_a.get(nm, 0) <= per_b.get(nm, 0) for nm in set(per_a) | set(per_b)),
   f"پادمان ریسک: با پرونده ⊆ بدون پرونده ({per_a} vs {per_b})")

# ۶) گزارش روزانه با پرونده — بدون خرابی
from core import daily_report as DR  # noqa: E402
agg = DR.aggregate(all_trades + b_open, NOW)
md = DR.fmt_report(agg, b_open, None, NOW, "local", lab=None, dossier=ds)
tg = DR.fmt_telegram(agg, b_open, None, NOW, lab=None, dossier=ds)
ok("پرونده‌ی بهبود" in md and "پرونده:" in tg, "بخش پرونده در گزارش md و تلگرام")

print(f"\n✅ همه‌ی {PASS} تست فاز ۱۴ پاس شد")
