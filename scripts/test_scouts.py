# -*- coding: utf-8 -*-
"""تست «میدان کاوشگرها» — core/scouts.py + تب ایجنت در pages/9_Farm_Airdrops.py
===============================================================================
بخش‌ها:
  ۱) ساختار: کامپایل، شخصیت‌ها (۵ ایجنت، کلید یکتا، بودجه/ریسک/زمان معتبر)
  ۲) cost_for: نشانِ سه نوع گام + نوع ناشناخته
  ۳) build_plan: صفر-پول (بدون پول، در بودجه‌ی زمان)، محتاط (استیبلِ آرام)،
     جاه‌طلب (بالاترین APY)، کم‌وقت (سقف ۱۵ دقیقه)، ریاضی‌دان (EV صریح)؛
     fail-soft روی داده‌ی خالی/خراب
  ۴) judge_plan: تخطی از بودجه‌ی صفر = جریمه‌ی سنگین، سرریز زمان، تنوع پاداش،
     ناهماهنگی ریسک، محدوده‌ی ۰-۱۰۰
  ۵) run_arena: قطعیت (دو اجرا = یک خروجی)، مرتب‌سازی، برنده، بدون کرش
  ۶) مارکرهای تب ایجنت در صفحه + فیلد minutes در TESTNET_HUNTS
اجرای صفر-ادعا: هیچ شبکه‌ای لازم نیست (داده‌ی ساختگی).
"""
from __future__ import annotations

import os
import subprocess as _sp
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

_PASS = 0
_FAIL = 0


def ok(cond, msg: str) -> bool:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  ✓ {msg}")
        return True
    _FAIL += 1
    print(f"  ✗ {msg}")
    return False


def section(t: str) -> None:
    print(f"\n— {t}")


# ---------------------------------------------------------------- ۱) ساختار
section("ساختار")
ok(os.path.exists(ROOT / "core" / "scouts.py"), "core/scouts.py موجود است")
_ch = _sp.run([sys.executable, "-m", "py_compile", str(ROOT / "core" / "scouts.py"),
               str(ROOT / "pages" / "9_Farm_Airdrops.py")], capture_output=True, text=True, timeout=60)
ok(_ch.returncode == 0, f"کامپایل scouts و صفحه {_ch.stderr.strip()[:120]}")

from core import opportunities as OP  # noqa: E402
from core import scouts as SC  # noqa: E402

_A = SC.SCOUT_AGENTS
ok(len(_A) >= 5, f"≥۵ ایجنت ({len(_A)})")
_keys = [a["key"] for a in _A]
ok(len(_keys) == len(set(_keys)) and set(_keys) >= {"zero", "cautious", "aggressive", "busy", "quant"},
   f"کلیدها یکتا و کامل ({_keys})")
ok(all(a.get("budget") in ("free", "paid", "any") for a in _A), "بودجه‌ها معتبر (free/paid/any)")
ok(all(0.0 < float(a.get("risk", 0)) <= 1.0 for a in _A), "ریسک در (۰، ۱]")
ok(all(int(a.get("time_budget", 0)) > 0 for a in _A), "بودجه‌ی زمانی مثبت")
ok(all(a.get("icon") and a.get("name") and a.get("name_en") and a.get("style") and a.get("style_en")
       for a in _A), "هر ایجنت آیکن/نام/سبک + ترجمه دارد")

# ---------------------------------------------------------------- ۲) cost_for
section("cost_for (نشان هزینه)")
ok(SC.cost_for("free")[0] == "🟢 رایگان" and SC.cost_for("paid")[0] == "🔴 پولی",
   "نشان رایگان/پولی درست")
ok("لاتاری" in SC.cost_for("mining")[0] and "lottery" in SC.cost_for("mining")[1],
   "ماینینگ = رایگان اما لاتاری")
ok(SC.cost_for("junk") == ("؟", "?"), "نوع ناشناخته → «؟» نه حدس")

# ---------------------------------------------------------------- ۳) build_plan
section("build_plan (۵ استراتژی)")
# داده‌ی ساختگی — همان الگوی test_opportunities
FIX = [
    {"id": f"p{i}", "project": f"proto{i}", "chain": "Ethereum", "symbol": "USDC",
     "tvlUsd": 2e8, "apyBase": apy, "apyReward": 0.0, "apyMean30d": apy - 0.2,
     "sigma": sig, "ilRisk": "no", "stablecoin": True, "outlier": False,
     "predictions": {"predictedClass": pred}}
    for i, (apy, sig, pred) in enumerate(
        [(6.0, 0.01, "Stable/Up"), (12.0, 0.03, "Stable/Up"), (25.0, 0.15, "Stable/Up"),
         (9.0, 0.02, "Down"), (4.5, 0.02, "Stable/Up")], 1)
]
by_key = {a["key"]: a for a in _A}

_pz = SC.build_plan(by_key["zero"], FIX, OP.TESTNET_HUNTS)
ok(_pz["steps"] and all(s["kind"] in ("free", "mining") for s in _pz["steps"]),
   f"صفر-پول: فقط گام‌های free/mining ({len(_pz['steps'])} گام)")
ok(not _pz["has_paid"], "صفر-پول: هیچ گام پولی ندارد")
ok(_pz["total_time"] <= by_key["zero"]["time_budget"], f"صفر-پول: در بودجه‌ی زمان ({_pz['total_time']}≤۳۰)")
ok(_pz["notes"], "صفر-پول: توضیحِ «چرا پولی‌ها رد شدند» دارد")

_pc = SC.build_plan(by_key["cautious"], FIX, OP.TESTNET_HUNTS)
ok(_pc["steps"], "محتاط: برنامه دارد")
_paid_c = [s for s in _pc["steps"] if s["kind"] == "paid"]
ok(all("high_sigma" not in (s.get("flags") or []) for s in _paid_c),
   "محتاط: استخرِ با نوسان بالا تست را رد کرده (بدون high_sigma)")
ok(_pc["total_time"] <= by_key["cautious"]["time_budget"], f"محتاط: در بودجه‌ی زمان ({_pc['total_time']}≤۲۰)")

_pa = SC.build_plan(by_key["aggressive"], FIX, OP.TESTNET_HUNTS)
_apys = [float(s["why"].split("APY کارمزدی ")[1].split("٪")[0]) for s in _pa["steps"] if s["kind"] == "paid"]
ok(len(_apys) >= 2 and _apys == sorted(_apys, reverse=True),
   f"جاه‌طلب: استخرها بر اساس APY نزولی ({_apys})")
ok(all("Down" not in s["why"] for s in _pa["steps"] if s.get("why")),
   "جاه‌طلب: پیش‌بینی Down هم رد شد (تست زنده)")

_pb = SC.build_plan(by_key["busy"], FIX, OP.TESTNET_HUNTS)
ok(_pb["total_time"] <= 15, f"کم‌وقت: سقف ۱۵ دقیقه ({_pb['total_time']})")
ok(any(s["kind"] == "free" for s in _pb["steps"]), "کم‌وقت: یک لاتاری کوتاه دارد")

_pq = SC.build_plan(by_key["quant"], FIX, OP.TESTNET_HUNTS)
ok(any("ev" in s for s in _pq["steps"]), "ریاضی‌دان: EV صریح روی گام‌ها")
ok(all("EV" in s["why"] for s in _pq["steps"] if "ev" in s), "ریاضی‌دان: EV داخل دلیل نوشته شده")

# فیل-سافت: داده‌ی خالی/خراب → بدون کرش، برنامه‌ی حداقلی از تست‌نت‌ها
_pe = SC.build_plan(by_key["cautious"], None, [])
ok(isinstance(_pe["steps"], list), "داده‌ی None/خالی → بدون کرش")
_pg = SC.build_plan(by_key["zero"], [{"x": 1}, None, "junk", FIX[0]], OP.TESTNET_HUNTS)
ok(_pg["steps"] and not _pg["has_paid"], "داده‌ی آشغال → فیلتر می‌شود و برنامه‌ی سالم می‌ماند")

# ---------------------------------------------------------------- ۴) judge_plan
section("judge_plan (داور قطعی)")
_clean = SC.build_plan(by_key["zero"], FIX, OP.TESTNET_HUNTS)
_s_clean, _f_clean = SC.judge_plan(by_key["zero"], _clean)
ok(0 <= _s_clean <= 100 and not _f_clean, f"برنامه‌ی سالمِ صفر-پول: {_s_clean}/100 بدون فلگ")
_dirty = dict(_clean)
_dirty["has_paid"] = True
_s_dirty, _f_dirty = SC.judge_plan(by_key["zero"], _dirty)
ok(_s_dirty < _s_clean and "budget_violation" in _f_dirty,
   f"تخطی از بودجه‌ی صفر → جریمه‌ی سنگین ({_s_dirty} < {_s_clean}, flag)")
_slow = dict(_clean)
_slow["total_time"] = by_key["zero"]["time_budget"] * 3
_s_slow, _f_slow = SC.judge_plan(by_key["zero"], _slow)
ok(_s_slow < _s_clean and "time_over" in _f_slow, f"سرریز زمان → جریمه ({_s_slow}, flag)")
_s_empty, _ = SC.judge_plan(by_key["zero"], {"steps": []})
ok(_s_empty <= 10, f"برنامه‌ی خالی → نمره‌ی کف ({_s_empty})")
ok(0 <= SC.judge_plan(by_key["quant"], _pq)[0] <= 100, "نمره همیشه در ۰-۱۰۰")

# ---------------------------------------------------------------- ۵) run_arena
section("run_arena (مسابقه‌ی کامل)")
_j1 = SC.run_arena(FIX, OP.TESTNET_HUNTS)
_j2 = SC.run_arena(FIX, OP.TESTNET_HUNTS)
ok(len(_j1) == len(SC.SCOUT_AGENTS), f"همه‌ی ایجنت‌ها مسابقه دادند ({len(_j1)})")
ok([r["score"] for r in _j1] == [r["score"] for r in _j2],
   f"قطعیت: دو اجرا، یک خروجی ({[r['score'] for r in _j1]})")
ok(_j1[0]["score"] >= _j1[-1]["score"], "مرتب‌سازی نزولی — برنده اول")
ok(_j1[0]["score"] >= 50, f"برنده نمره‌ی معقول دارد ({_j1[0]['score']}/100 «{_j1[0]['verdict']}»)")
ok(all(isinstance(r["score"], int) and 0 <= r["score"] <= 100 for r in _j1), "همه‌ی نمره‌ها int در ۰-۱۰۰")
ok(all(r["plan"]["steps"] for r in _j1), "هیچ ایجنتی با برنامه‌ی خالی نماند (تست‌نت‌های محلی کافی‌اند)")
_j3 = SC.run_arena(None, None)
ok(all(isinstance(r["score"], int) for r in _j3), "بدون داده هم مسابقه بدون کرش برگزار می‌شود")

# ---------------------------------------------------------------- ۶) صفحه + minutes
section("مارکرهای صفحه و داده")
_pg_txt = (ROOT / "pages" / "9_Farm_Airdrops.py").read_text(encoding="utf-8")
for frag in ("میدان کاوشگرها", "SC.run_arena", "SC.cost_for", "🏆", "اجرای میدان",
             "مرزِ صادقانه", "چرا باتِ اجرا نمی‌سازیم", "from core import scouts as SC"):
    ok(frag in _pg_txt, f"مارکر تب ایجنت «{frag}»")
ok(all(isinstance(h.get("minutes"), int) and h["minutes"] >= 5 for h in OP.TESTNET_HUNTS),
   f"همه‌ی {len(OP.TESTNET_HUNTS)} تست‌نت فیلد minutes دارند (بودجه‌ی زمانی ایجنت‌ها)")

print(f"\n===== نتیجه: {_PASS} سبز / {_FAIL} قرمز =====")
sys.exit(1 if _FAIL else 0)
