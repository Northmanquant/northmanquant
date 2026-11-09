# -*- coding: utf-8 -*-
"""تست «میدان کاوشگرها» — core/scouts.py + تب ایجنت در pages/9_Farm_Airdrops.py
===============================================================================
بخش‌ها:
  ۱) ساختار: کامپایل، شخصیت‌ها (۵ ایجنت، کلید یکتا، بودجه/ریسک/زمان معتبر،
     قانون میدان: بودجه‌ی همه = free)
  ۲) cost_for: نشانِ چهار نوع گام + نوع ناشناخته
  ۳) build_plan — قانون «فقط رایگان» (به درخواست کاربر): هیچ ایجنتی گامِ پولی
     نمی‌گذارد؛ سمت فارمینگ (تست‌نت/نقاط) + سمت ماینینگ (موبایلی)؛ یادداشتِ
     «تست شد و رد شد» برای استخرهای پولی؛ پنج استراتژی متمایز؛ fail-soft
  ۴) judge_plan: تخطی از بودجه‌ی صفر برای «همه‌ی» ایجنت‌ها = جریمه‌ی سنگین،
     سرریز زمان، تنوع +۸، پوششِ دو دنیا +۱۰، پوششِ ≥۴ گام +۵، EV پاداش،
     محدوده‌ی ۰-۱۰۰
  ۵) run_arena: قطعیت (دو اجرا = یک خروجی)، مرتب‌سازی، برنده، بدون کرش
  ۶) مارکرهای تب ایجنت در صفحه (شامل بنرِ قانون میدان) + فیلد minutes
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
ok(all(a.get("budget") == "free" for a in _A),
   "قانون میدان: بودجه‌ی «همه‌ی» ایجنت‌ها = free (فقط رایگان)")
ok(all(0.0 < float(a.get("risk", 0)) <= 1.0 for a in _A), "ریسک در (۰، ۱]")
ok(all(int(a.get("time_budget", 0)) > 0 for a in _A), "بودجه‌ی زمانی مثبت")
ok(all(a.get("icon") and a.get("name") and a.get("name_en") and a.get("style") and a.get("style_en")
       for a in _A), "هر ایجنت آیکن/نام/سبک + ترجمه دارد")

# ---------------------------------------------------------------- ۲) cost_for
section("cost_for (نشان هزینه)")
ok(SC.cost_for("free")[0] == "🟢 رایگان" and SC.cost_for("paid")[0] == "🔴 پولی",
   "نشان رایگان/پولی درست")
ok("نقاط" in SC.cost_for("points")[0] and "points" in SC.cost_for("points")[1],
   "فارمِ نقاط = رایگان — نقاط")
ok("لاتاری" in SC.cost_for("mining")[0] and "lottery" in SC.cost_for("mining")[1],
   "ماینینگ = رایگان اما لاتاری")
ok(SC.cost_for("junk") == ("؟", "?"), "نوع ناشناخته → «؟» نه حدس")

# ---------------------------------------------------------------- ۳) build_plan
section("build_plan (قانون «فقط رایگان» + ۵ استراتژی)")
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
FREE_KINDS = {"free", "points", "mining"}

_plans = {k: SC.build_plan(by_key[k], FIX, OP.TESTNET_HUNTS) for k in by_key}

# قانون میدان: هیچ ایجنتی گامِ پولی نمی‌گذارد — برای همه
ok(all(not p["has_paid"] for p in _plans.values()), "هیچ برنامه‌ای گامِ پولی ندارد (has_paid=False برای همه)")
ok(all(s["kind"] in FREE_KINDS for p in _plans.values() for s in p["steps"]),
   "همه‌ی گام‌ها از سه نوع رایگان‌اند (free/points/mining)")
ok(all(SC.cost_for(s["kind"])[0].startswith("🟢") for p in _plans.values() for s in p["steps"]),
   "نشانِ هزینه‌ی همه‌ی گام‌ها 🟢 است")

# یادداشتِ «تست شد و رد شد» — استخرها زنده تست می‌شوند اما از برنامه حذف
_oknote = True
for p in _plans.values():
    if not p["notes"] or not ("پولی" in p["notes"][0] or "فیلتر" in p["notes"][0] or "نرسید" in p["notes"][0]):
        _oknote = False
ok(_oknote, "اولین یادداشتِ هر برنامه = سرنوشتِ استخرها (تست/رد/نرسیدن داده)")

# صفر-پول: ارزان‌ترین‌ها + هر دو دنیا
_pz = _plans["zero"]
ok(_pz["total_time"] <= by_key["zero"]["time_budget"], f"صفر-پول: در بودجه‌ی زمان ({_pz['total_time']}≤۳۰)")
ok({s["kind"] for s in _pz["steps"]} == {"free", "points", "mining"},
   f"صفر-پول: هر دو دنیا + نقاط ({len(_pz['steps'])} گام)")

# محتاط: بدون لاتاریِ ماینینگ — جاافتاده + نقاط
_pc = _plans["cautious"]
ok(_pc["total_time"] <= by_key["cautious"]["time_budget"], f"محتاط: در بودجه‌ی زمان ({_pc['total_time']}≤۲۰)")
ok("mining" not in {s["kind"] for s in _pc["steps"]}, "محتاط: لاتاریِ ماینینگ ندارد (استایلش)")
ok({"free", "points"} <= {s["kind"] for s in _pc["steps"]}, "محتاط: تست‌نت + نقاط دارد")

# جاه‌طلب: بیشترین پوششِ رایگان
_pa = _plans["aggressive"]
ok({s["kind"] for s in _pa["steps"]} == {"free", "points", "mining"},
   f"جاه‌طلب: پوششِ کاملِ رایگان ({len(_pa['steps'])} گام)")
ok(_pa["total_time"] <= by_key["aggressive"]["time_budget"], f"جاه‌طلب: در بودجه‌ی زمان ({_pa['total_time']}≤۶۰)")
ok(len(_pa["steps"]) >= 5, f"جاه‌طلب: بیشترین بلیتِ رایگان ({len(_pa['steps'])} گام)")

# کم-وقت: ۱۵ دقیقه سفت‌وسخت، دو دنیا
_pb = _plans["busy"]
ok(_pb["total_time"] <= by_key["busy"]["time_budget"], f"کم‌وقت: سقف ۱۵ دقیقه ({_pb['total_time']})")
ok({s["kind"] for s in _pb["steps"]} == {"mining", "points"}, "کم‌وقت: دو دنیا در یک ربع (ماینینگ + نقاط)")

# ریاضی‌دان: EV صریح — نامعین بودنش هم صادقانه نوشته می‌شود
_pq = _plans["quant"]
ok(_pq["total_time"] <= by_key["quant"]["time_budget"], f"ریاضی‌دان: در بودجه‌ی زمان ({_pq['total_time']}≤۴۰)")
ok(all("ev" in s for s in _pq["steps"]), "ریاضی‌دان: EV روی همه‌ی گام‌ها")
ok(all("EV" in s["why"] and "نامعین" in s["why"] for s in _pq["steps"] if "ev" in s),
   "ریاضی‌دان: EV پولی «نامعین» داخل دلیل نوشته شده (صداقت)")

# قطعیت ترتیب: دو اجرا، یک برنامه
_pz2 = SC.build_plan(by_key["zero"], FIX, OP.TESTNET_HUNTS)
ok([s["title"] for s in _pz["steps"]] == [s["title"] for s in _pz2["steps"]],
   "قطعیت: دو اجرا، ترتیبِ گام‌های یکسان")

# فیل-سافت: داده‌ی خالی/خراب → بدون کرش
_pe = SC.build_plan(by_key["cautious"], None, [])
ok(isinstance(_pe["steps"], list), "داده‌ی None/خالی → بدون کرش")
_pg = SC.build_plan(by_key["zero"], [{"x": 1}, None, "junk", FIX[0]], OP.TESTNET_HUNTS)
ok(_pg["steps"] and not _pg["has_paid"], "داده‌ی آشغال → فیلتر می‌شود و برنامه‌ی سالم می‌ماند")

# ---------------------------------------------------------------- ۴) judge_plan
section("judge_plan (داور قطعی — قانون میدان)")
_clean = SC.build_plan(by_key["zero"], FIX, OP.TESTNET_HUNTS)
_s_clean, _f_clean = SC.judge_plan(by_key["zero"], _clean)
ok(0 <= _s_clean <= 100 and not _f_clean, f"برنامه‌ی سالمِ صفر-پول: {_s_clean}/100 بدون فلگ")
_dirty = dict(_clean)
_dirty["has_paid"] = True
_s_dirty, _f_dirty = SC.judge_plan(by_key["zero"], _dirty)
ok(_s_dirty < _s_clean and "budget_violation" in _f_dirty,
   f"تخطی از بودجه‌ی صفر → جریمه‌ی سنگین ({_s_dirty} < {_s_clean}, flag)")

# قانون جهانی: حتی ایجنتی که استایلش جاه‌طلبانه است هم جریمه می‌شود — میدان فقط-رایگان است
_ag_clean_score, _ = SC.judge_plan(by_key["aggressive"], _plans["aggressive"])
_pl_ag = dict(_plans["aggressive"])
_pl_ag["has_paid"] = True
_s_ag, _f_ag = SC.judge_plan(by_key["aggressive"], _pl_ag)
ok(_s_ag < _ag_clean_score and "budget_violation" in _f_ag,
   f"قانون جهانی: گامِ پولی برای جاه‌طلب هم جریمه دارد ({_s_ag} < {_ag_clean_score}, flag)")

_slow = dict(_clean)
_slow["total_time"] = by_key["zero"]["time_budget"] * 3
_s_slow, _f_slow = SC.judge_plan(by_key["zero"], _slow)
ok(_s_slow < _s_clean and "time_over" in _f_slow, f"سرریز زمان → جریمه ({_s_slow}, flag)")
_s_empty, _ = SC.judge_plan(by_key["zero"], {"steps": []})
ok(_s_empty <= 10, f"برنامه‌ی خالی → نمره‌ی کف ({_s_empty})")
ok(0 <= SC.judge_plan(by_key["quant"], _pq)[0] <= 100, "نمره همیشه در ۰-۱۰۰")

# دلتای دقیق پاداش‌ها: تنوع +۸، دو دنیا +۱۰، پوششِ ≥۴ گام +۵
_jx = dict(budget="any", risk=0.5, time_budget=60)
_min_step = {"kind": "mining", "time_min": 5, "flags": []}
_pt_step = {"kind": "points", "time_min": 10, "flags": []}
_tn_step = {"kind": "free", "time_min": 10, "flags": []}
_pmp = {"steps": [dict(_min_step), dict(_pt_step)], "total_time": 15, "has_paid": False}
_pp = {"steps": [dict(_pt_step)], "total_time": 10, "has_paid": False}
_pcov = {"steps": [dict(_min_step), dict(_pt_step), dict(_tn_step), dict(_tn_step)],
         "total_time": 35, "has_paid": False}
_s_mp, _ = SC.judge_plan(_jx, _pmp)
_s_p, _ = SC.judge_plan(_jx, _pp)
_s_cov, _ = SC.judge_plan(_jx, _pcov)
ok(_s_mp == _s_p + 18, f"دلتای تنوع(+۸) + دو دنیا(+۱۰) = ۱۸ ({_s_mp} = {_s_p}+18)")
ok(_s_cov == _s_mp + 5, f"دلتای پوششِ ≥۴ گام = +۵ ({_s_cov} = {_s_mp}+5)")

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
ok(all(not r["plan"]["has_paid"] for r in _j1), "در کل مسابقه حتی یک گامِ پولی نیست")
ok(all(s["kind"] in FREE_KINDS for r in _j1 for s in r["plan"]["steps"]),
   "گام‌های همه‌ی برنامه‌ها فقط رایگان‌اند")
ok(any({"free", "points"} <= {s["kind"] for s in r["plan"]["steps"]}
        and "mining" in {s["kind"] for s in r["plan"]["steps"]} for r in _j1[:2]),
   "برنده‌های اول هر دو دنیا را پوشش می‌دهند (فارمینگِ رایگان + ماینینگِ رایگان)")
_j3 = SC.run_arena(None, None)
ok(all(isinstance(r["score"], int) for r in _j3), "بدون داده هم مسابقه بدون کرش برگزار می‌شود")

# ---------------------------------------------------------------- ۶) صفحه + minutes
section("مارکرهای صفحه و داده")
_pg_txt = (ROOT / "pages" / "9_Farm_Airdrops.py").read_text(encoding="utf-8")
for frag in ("میدان کاوشگرها", "نتیجه‌ی ایجنت‌ها همین‌جاست", "قانون میدان", "بودجه‌ی صفر",
             "SC.run_arena", "SC.cost_for", "🏆", "اجرای میدان",
             "مرزِ صادقانه", "چرا باتِ اجرا نمی‌سازیم", "from core import scouts as SC"):
    ok(frag in _pg_txt, f"مارکر میدان «{frag}»")
ok("t_scout" not in _pg_txt, "تب جداگانه‌ی ایجنت حذف شد — میدان دیگر تب مستقل ندارد")
ok("t_farm, t_mine, t_free, t_scam = st.tabs(" in _pg_txt, "صفحه ۴ تب دارد")
ok("· 🤖 ایجنت‌ها" in _pg_txt, "برچسب تب فارمینگ جای ایجنت‌ها را نشان می‌دهد")
_i_farm = _pg_txt.index("with t_farm:")
_i_mine = _pg_txt.index("with t_mine:")
_i_arena = _pg_txt.index("میدان کاوشگرها — نتیجه‌ی ایجنت‌ها")
ok(_i_farm < _i_arena < _i_mine,
   "میدان کاوشگرها داخل ناحیه‌ی تب فارمینگ است (بعد از استخرها، قبل از تب ماینینگ)")
ok(all(isinstance(h.get("minutes"), int) and h["minutes"] >= 5 for h in OP.TESTNET_HUNTS),
   f"همه‌ی {len(OP.TESTNET_HUNTS)} تست‌نت فیلد minutes دارند (بودجه‌ی زمانی ایجنت‌ها)")

print(f"\n===== نتیجه: {_PASS} سبز / {_FAIL} قرمز =====")
sys.exit(1 if _FAIL else 0)
