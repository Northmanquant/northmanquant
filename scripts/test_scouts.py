# -*- coding: utf-8 -*-
"""تست «کارگاه کیفیت پروژه» — core/scouts.py + تب ایجنت در pages/9_Free_Opportunities.py
=======================================================================================
چرخشِ به درخواست کاربر: «بخش فارمینگ و ماینینگ کلا حذف شود؛ بریم به فکر پروژه‌ی
خودمون باشیم، کیفیتش رو ببریم بالا.» — ایجنت‌ها دیگر فرصت بیرونی نمی‌شمارند؛
مخزنِ واقعی را اسکن می‌کنند و طرحِ بهبودِ کیفیت می‌سازند.

بخش‌ها:
  ۱) ساختار: کامپایل، شخصیت‌ها (۵ ایجنت، کلید یکتا، بودجه‌ی همه = free،
     سبکِ بی‌فارم/بی‌ماین)
  ۲) COST_FOR/AREA_FOR/fa_num: نشانِ انواع رایگان/پولی + نوع ناشناخته + ارقام فارسی
  ۳) repo_scan: اسکنِ واقعی مخزن (فایل‌ها، تست‌ها، TODOها، biggest)، قطعیت و
     فیل-سافتِ مسیرِ خراب
  ۴) build_plan: قانون «همه‌ی گام‌ها رایگان»، هدف‌های واقعی، پنج استراتژی متمایز،
     بودجه‌ی زمانی، EV صادقانه‌ی ریاضی‌دان، فیل-سافتِ اسکنِ خالی
  ۵) judge_plan: گامِ پولی −۴۵ برای همه، سرریزِ زمان، دلتای دقیق پاداش‌ها
     (حوزه‌ها +۸/+۷، دو ستون +۱۰، ≥۴ گام +۵، هدفِ واقعی +۵، EV +۵)،
     ناهماهنگیِ ریسکِ محتاط، محدوده‌ی ۰-۱۰۰
  ۶) run_arena: قطعیت، مرتب‌سازی، برنده، بدون کرش با اسکنِ خالی/None
  ۷) مارکرهای تب کارگاه در صفحه + حذفِ کاملِ ردِ فارم/ماین از صفحه
اجرای صفر-ادعا: هیچ شبکه‌ای لازم نیست — اسکن روی همین مخزن انجام می‌شود.
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
ok(os.path.exists(ROOT / "pages" / "9_Free_Opportunities.py"),
   "pages/9_Free_Opportunities.py موجود است (نامِ تازه)")
ok(not os.path.exists(ROOT / "pages" / "9_Farm_Airdrops.py"),
   "فایلِ قدیمیِ Farm_Airdrops حذف شده است")
_ch = _sp.run([sys.executable, "-m", "py_compile", str(ROOT / "core" / "scouts.py"),
               str(ROOT / "core" / "opportunities.py"),
               str(ROOT / "pages" / "9_Free_Opportunities.py")],
              capture_output=True, text=True, timeout=60)
ok(_ch.returncode == 0, f"کامپایل scouts/opportunities/صفحه {_ch.stderr.strip()[:120]}")

from core import scouts as SC  # noqa: E402

_A = SC.SCOUT_AGENTS
ok(len(_A) >= 5, f"≥۵ ایجنت ({len(_A)})")
_keys = [a["key"] for a in _A]
ok(len(_keys) == len(set(_keys)) and set(_keys) >= {"zero", "cautious", "aggressive", "busy", "quant"},
   f"کلیدها یکتا و کامل ({_keys})")
ok(all(a.get("budget") == "free" for a in _A),
   "قانون کارگاه: بودجه‌ی «همه‌ی» ایجنت‌ها = free")
ok(all(0.0 < float(a.get("risk", 0)) <= 1.0 for a in _A), "ریسک در (۰، ۱]")
ok(all(int(a.get("time_budget", 0)) > 0 for a in _A), "بودجه‌ی زمانی مثبت")
ok(all(a.get("icon") and a.get("name") and a.get("name_en") and a.get("style") and a.get("style_en")
       for a in _A), "هر ایجنت آیکن/نام/سبک + ترجمه دارد")
ok(all("فارم" not in a["style"] and "ماین" not in a["style"] and "فارم" not in a["style_en"]
       and "mining" not in a["style_en"].lower() and "farm" not in a["style_en"].lower()
       for a in _A), "سبکِ هیچ ایجنتی دیگر فارم/ماین ندارد (چرخش به پروژه‌ی خودمان)")

# ------------------------------------------------- ۲) COST_FOR/AREA_FOR/fa_num
section("COST_FOR / AREA_FOR / fa_num")
for k in SC.FREE_KINDS:
    ok(SC.cost_for(k)[0].startswith("🟢"), f"نشانِ «{k}» = 🟢 رایگان")
for k in SC.PAID_KINDS:
    ok(SC.cost_for(k)[0].startswith("🔴"), f"نشانِ «{k}» = 🔴 پولی")
ok(SC.cost_for("junk") == ("؟", "?"), "نوع ناشناخته → «؟» نه حدس")
ok(all(SC.area_for(a)[0] != "؟" for a in ("tests", "stability", "docs", "ux", "data", "cleanup")),
   "شش حوزه‌ی کیفیت برچسب دارند")
ok(SC.area_for("junk") == ("؟", "?"), "حوزه‌ی ناشناخته → «؟»")
ok(SC.fa_num(12) == "۱۲" and SC.fa_num(0) == "۰", "fa_num: ارقام فارسی")
ok(SC.fa_num("x") == "؟", "fa_num: ورودی خراب → «؟» (فیل-سافت)")

# ---------------------------------------------------------------- ۳) repo_scan
section("repo_scan (اسکنِ واقعی مخزن)")
_S1 = SC.repo_scan()
ok(isinstance(_S1, dict) and isinstance(_S1.get("files"), dict), "خروجی dict با کلید files")
ok(_S1["n_files"] >= 40, f"اسکنِ واقعی: {_S1['n_files']} فایل پایتون ≥ ۴۰")
ok(_S1["n_lines"] >= 5000, f"خط‌های کد واقعی: {_S1['n_lines']:,} ≥ ۵٬۰۰۰")
ok(_S1["n_tests"] >= 15, f"اسکریپت‌های تست دیده شدند: {_S1['n_tests']} ≥ ۱۵")
ok(_S1["n_pages"] >= 9, f"صفحه‌های Streamlit دیده شدند: {_S1['n_pages']} ≥ ۹")
ok(_S1["n_core"] >= 20, f"ماژول‌های هسته دیده شدند: {_S1['n_core']} ≥ ۲۰")
ok("core/scouts.py" in _S1["files"] and "core/opportunities.py" in _S1["files"],
   "خودِ ماژول‌ها در اسکن هستند")
ok("pages/9_Free_Opportunities.py" in _S1["files"], "صفحه‌ی تازه در اسکن است")
ok("pages/9_Farm_Airdrops.py" not in _S1["files"], "صفحه‌ی قدیمیِ فارم از اسکن غایب است")
ok(_S1["biggest"] and all(b in _S1["files"] for b in _S1["biggest"]),
   f"biggest فقط فایل‌های واقعی ({_S1['biggest'][:2]}…)")
ok(all(f["lines"] > 0 for f in _S1["files"].values()), "هر فایلِ اسکن‌شده خط دارد")
ok(isinstance(_S1["n_todo"], int) and _S1["n_todo"] >= 0, f"TODOهای باز شمرده شدند: {_S1['n_todo']}")
_S2 = SC.repo_scan()
ok(_S1 == _S2, "قطعیت: دو اسکنِ پشت‌سرهم، خروجیِ یکسان")
_Sbad = SC.repo_scan(root="/definitely/not/a/real/path")
ok(isinstance(_Sbad, dict) and _Sbad["files"] == {}, "مسیرِ خراب → اسکنِ خالی، بدون کرش")

# ---------------------------------------------------------------- ۴) build_plan
section("build_plan (قانون «همه‌ی گام‌ها رایگان» + ۵ استراتژی)")
by_key = {a["key"]: a for a in _A}
_plans = {k: SC.build_plan(by_key[k], _S1) for k in by_key}

ok(all(p["steps"] for p in _plans.values()),
   "هیچ ایجنتی با برنامه‌ی خالی نماند (مخزن واقعی هدفِ کافی دارد)")
ok(all(not p["has_paid"] for p in _plans.values()),
   "هیچ برنامه‌ای گامِ پولی ندارد (has_paid=False برای همه)")
ok(all(s["kind"] in SC.FREE_KINDS for p in _plans.values() for s in p["steps"]),
   "همه‌ی گام‌ها از شش نوعِ رایگان‌اند (audit/test/docs/refactor/ux/data)")
ok(all(SC.cost_for(s["kind"])[0].startswith("🟢") for p in _plans.values() for s in p["steps"]),
   "نشانِ هزینه‌ی همه‌ی گام‌ها 🟢 است")
ok(all(s.get("area") in SC.AREA_FOR for p in _plans.values() for s in p["steps"]),
   "حوزه‌ی همه‌ی گام‌ها معتبر است")
ok(all(s.get("why") and s.get("title") and s.get("title_en") and int(s.get("time_min") or 0) > 0
       for p in _plans.values() for s in p["steps"]),
   "هر گام عنوان + دلیل + زمانِ مثبت دارد")
ok(all(s.get("target") in _S1["files"] for p in _plans.values() for s in p["steps"]),
   "🎯 هدفِ همه‌ی گام‌ها فایلِ واقعیِ همین مخزن است (نه شعار)")
ok(all(p["total_time"] == sum(int(s["time_min"]) for s in p["steps"]) for p in _plans.values()),
   "total_time = جمعِ زمانِ گام‌ها")
ok(all(p["total_time"] <= by_key[k]["time_budget"] for k, p in _plans.items()),
   f"همه‌ی برنامه‌ها در بودجه‌ی زمان‌اند ({ {k: p['total_time'] for k, p in _plans.items()} })")

# صفر-پول: کوچک‌ترین اصلاح‌ها — تست + مستندات + تمیزکاری
_pz = _plans["zero"]
ok({"tests", "docs"} <= {s["area"] for s in _pz["steps"]},
   f"صفر-پول: تست + مستندات دارد ({len(_pz['steps'])} گام، {_pz['total_time']} دقیقه)")
# محتاط: پایداری + داده، بدون بازسازی
_pc = _plans["cautious"]
ok("refactor" not in {s["kind"] for s in _pc["steps"]},
   "محتاط: بازسازیِ پرخطر ندارد (استایلش)")
ok({"stability", "data"} <= {s["area"] for s in _pc["steps"]},
   f"محتاط: پایداری + تازگیِ داده ({_pc['total_time']} دقیقه)")
# جاه‌طلب: بیشترین پوششِ حوزه‌ها
_pa = _plans["aggressive"]
ok(len({s["area"] for s in _pa["steps"]}) >= 4,
   f"جاه‌طلب: ≥۴ حوزه ({sorted({s['area'] for s in _pa['steps']})})")
ok(len(_pa["steps"]) >= 5, f"جاه‌طلب: ≥۵ گام ({len(_pa['steps'])} گام)")
# کم-وقت: ۱۵ دقیقه سفت‌وسخت
_pb = _plans["busy"]
ok(_pb["total_time"] <= by_key["busy"]["time_budget"], f"کم-وقت: سقف ۱۵ دقیقه ({_pb['total_time']})")
ok({"tests", "cleanup"} <= {s["area"] for s in _pb["steps"]}, "کم-وقت: اسکن + اجرای تست‌ها")
# ریاضی‌دان: EV صریح — نامعین بودنش هم صادقانه نوشته می‌شود
_pq = _plans["quant"]
ok(all("ev" in s for s in _pq["steps"]), "ریاضی‌دان: EV روی همه‌ی گام‌ها")
ok(all("نامعین" in s["why"] and "EV" in s["why"] for s in _pq["steps"]),
   "ریاضی‌دان: EV کیفیت «نامعین» داخل دلیل نوشته شده (صداقت)")

# قطعیت ترتیب: دو اجرا، یک برنامه
_pz2 = SC.build_plan(by_key["zero"], _S1)
ok([s["title"] for s in _pz["steps"]] == [s["title"] for s in _pz2["steps"]],
   "قطعیت: دو اجرا، ترتیبِ گام‌های یکسان")

# فیل-سافت: اسکنِ خالی/None → برنامه‌ی خالیِ صادقانه، بدون کرش
_pe = SC.build_plan(by_key["cautious"], {})
ok(isinstance(_pe["steps"], list) and _pe["steps"] == [] and _pe["notes"],
   f"اسکنِ خالی → برنامه‌ی خالی + پیام ({_pe['notes'][0][:40]}…)")
_pe2 = SC.build_plan(by_key["zero"], None)
ok(isinstance(_pe2["steps"], list) and _pe2["steps"] == [], "اسکنِ None → بدون کرش")
_pg = SC.build_plan(by_key["zero"], {"files": {"fake.py": {"lines": 3}}, "biggest": ["fake.py"],
                                     "todo_files": [], "docless": []})
ok(all(s["target"] in ("fake.py",) or s["target"] == "" for s in _pg["steps"]),
   "اسکنِ حداقلی → فقط فایل‌های همان اسکن هدف می‌شوند")

# ---------------------------------------------------------------- ۵) judge_plan
section("judge_plan (داور قطعی — قانون کارگاه)")
_s_clean, _f_clean = SC.judge_plan(by_key["zero"], _pz, _S1)
ok(0 <= _s_clean <= 100 and not _f_clean, f"طرحِ سالمِ صفر-پول با اسکن: {_s_clean}/100 بدون فلگ")
_s_noscan, _ = SC.judge_plan(by_key["zero"], _pz)
ok(_s_clean == _s_noscan + 5, f"پاداشِ «هدفِ واقعی» = +۵ ({_s_clean} = {_s_noscan}+5)")

_dirty = dict(_pz)
_dirty["has_paid"] = True
_s_dirty, _f_dirty = SC.judge_plan(by_key["zero"], _dirty, _S1)
ok(_s_dirty < _s_clean and "budget_violation" in _f_dirty,
   f"گامِ پولی → جریمه‌ی سنگین ({_s_dirty} < {_s_clean}, flag)")

# قانون جهانی: گامِ پولی برای «همه‌ی» ایجنت‌ها جریمه دارد — کیفیت با پول خریدنی نیست
_ag_clean_score, _ = SC.judge_plan(by_key["aggressive"], _plans["aggressive"], _S1)
_pl_ag = dict(_plans["aggressive"])
_pl_ag["steps"] = _plans["aggressive"]["steps"] + [
    {"kind": "cloud_server", "area": "data", "time_min": 5, "target": "", "flags": []}]
_pl_ag["total_time"] = _plans["aggressive"]["total_time"] + 5
_s_ag, _f_ag = SC.judge_plan(by_key["aggressive"], _pl_ag, _S1)
ok(_s_ag < _ag_clean_score and "budget_violation" in _f_ag,
   f"قانون جهانی: گامِ پولیِ مستقیم (cloud_server) برای جاه‌طلب هم جریمه دارد ({_s_ag} < {_ag_clean_score})")

_slow = dict(_pz)
_slow["total_time"] = by_key["zero"]["time_budget"] * 3
_s_slow, _f_slow = SC.judge_plan(by_key["zero"], _slow, _S1)
ok(_s_slow < _s_noscan and "time_over" in _f_slow, f"سرریز زمان → جریمه + فلگ ({_s_slow})")
_s_empty, _ = SC.judge_plan(by_key["zero"], {"steps": []})
ok(_s_empty <= 10, f"برنامه‌ی خالی → نمره‌ی کف ({_s_empty})")
ok(0 <= SC.judge_plan(by_key["quant"], _pq, _S1)[0] <= 100, "نمره همیشه در ۰-۱۰۰")

# دلتای دقیق پاداش‌ها: حوزه‌ها +۸، ≥۴ حوزه +۷، دو ستون +۱۰، ≥۴ گام +۵، EV +۵
_jx = {"budget": "any", "risk": 0.5, "time_budget": 60}
_p1 = {"steps": [{"kind": "test", "area": "tests", "time_min": 10, "target": "", "flags": []}],
       "total_time": 10, "has_paid": False}
_p2 = {"steps": [dict(_p1["steps"][0]),
                 {"kind": "docs", "area": "docs", "time_min": 10, "target": "", "flags": []}],
       "total_time": 20, "has_paid": False}
_p3 = {"steps": [dict(_p2["steps"][0]), dict(_p2["steps"][1]),
                 {"kind": "ux", "area": "ux", "time_min": 10, "target": "", "flags": []},
                 {"kind": "data", "area": "data", "time_min": 10, "target": "", "flags": []}],
       "total_time": 40, "has_paid": False}
_s1, _ = SC.judge_plan(_jx, _p1)
_s2, _ = SC.judge_plan(_jx, _p2)
_s3, _ = SC.judge_plan(_jx, _p3)
ok(_s1 == 55, f"پایه‌ی یک گامِ تک‌حوزه‌ای = ۵۵ ({_s1})")
ok(_s2 == _s1 + 18, f"دلتای حوزه‌ی دوم(+۸) + دو ستون(+۱۰) = ۱۸ ({_s2} = {_s1}+18)")
ok(_s3 == _s2 + 12, f"دلتای ≥۴ حوزه(+۷) + ≥۴ گام(+۵) = ۱۲ ({_s3} = {_s2}+12)")

# EV پاداش
_p1ev = {"steps": [dict(_p1["steps"][0], ev=10)], "total_time": 10, "has_paid": False}
_s1ev, _ = SC.judge_plan(_jx, _p1ev)
ok(_s1ev == _s1 + 5, f"EV صریح = +۵ ({_s1ev} = {_s1}+5)")

# ناهماهنگیِ ریسک: محتاط با گامِ بازسازی
_pc_ref = {"steps": [{"kind": "refactor", "area": "cleanup", "time_min": 10, "target": "", "flags": []}],
           "total_time": 10, "has_paid": False}
_s_risk, _f_risk = SC.judge_plan(by_key["cautious"], _pc_ref)
ok(_s_risk == 40 and "risk_mismatch" in _f_risk,
   f"محتاط + بازسازی → −۱۵ + risk_mismatch ({_s_risk})")

# ---------------------------------------------------------------- ۶) run_arena
section("run_arena (مسابقه‌ی کامل)")
_j1 = SC.run_arena(_S1)
_j2 = SC.run_arena(_S1)
ok(len(_j1) == len(SC.SCOUT_AGENTS), f"همه‌ی ایجنت‌ها مسابقه دادند ({len(_j1)})")
ok([r["score"] for r in _j1] == [r["score"] for r in _j2],
   f"قطعیت: دو اجرا، یک خروجی ({[r['score'] for r in _j1]})")
ok(_j1[0]["score"] >= _j1[-1]["score"], "مرتب‌سازی نزولی — برنده اول")
ok(_j1[0]["score"] >= 60, f"برنده نمره‌ی معقول دارد ({_j1[0]['score']}/100 «{_j1[0]['verdict']}»)")
ok(all(isinstance(r["score"], int) and 0 <= r["score"] <= 100 for r in _j1), "همه‌ی نمره‌ها int در ۰-۱۰۰")
ok(all(r["plan"]["steps"] for r in _j1), "هیچ ایجنتی با برنامه‌ی خالی نماند")
ok(all(not r["plan"]["has_paid"] for r in _j1), "در کل مسابقه حتی یک گامِ پولی نیست")
ok(all(s["kind"] in SC.FREE_KINDS for r in _j1 for s in r["plan"]["steps"]),
   "گام‌های همه‌ی برنامه‌ها فقط رایگان‌اند")
ok(all(s.get("target") in _S1["files"] for r in _j1 for s in r["plan"]["steps"]),
   "هدف‌های همه‌ی گام‌ها در کل مسابقه واقعی‌اند")
_j3 = SC.run_arena({})
ok(all(isinstance(r["score"], int) for r in _j3), "اسکنِ خالی هم مسابقه‌ی بدون کرش برگزار می‌شود")
_j4 = SC.run_arena(None)
ok(all(isinstance(r["score"], int) for r in _j4), "اسکنِ None هم بدون کرش")

# ---------------------------------------------------------------- ۷) صفحه
section("مارکرهای صفحه و حذفِ کاملِ فارم/ماین")
_pg_txt = (ROOT / "pages" / "9_Free_Opportunities.py").read_text(encoding="utf-8")
for frag in ("کارگاه کیفیت", "SC.run_arena", "SC.repo_scan", "SC.cost_for", "SC.area_for",
             "SC.fa_num", "🏆", "اجرای کارگاه", "قانون کارگاه", "بودجه‌ی صفر",
             "مرزِ صادقانه", "from core import scouts as SC", "🎯"):
    ok(frag in _pg_txt, f"مارکر کارگاه «{frag}»")
ok("t_free, t_scout, t_scam = st.tabs(" in _pg_txt, "صفحه ۳ تب دارد (رایگان/کارگاه/ضدکلاهبرداری)")
for bad in ("فارم", "ماین", "farm", "mining", "llama", "honest_pools", "MINING_KINDS",
            "t_farm", "t_mine", "fetch_llama"):
    ok(bad not in _pg_txt.lower(), f"ردِ حذف‌شده در صفحه نیست: «{bad}»")
_i18 = (ROOT / "core" / "i18n.py").read_text(encoding="utf-8")
ok('"p9", "pages/9_Free_Opportunities.py"' in _i18, "صفحه‌ی تازه در NAV_PAGES ثبت شده")
ok("فرصت‌های رایگان" in _i18, "برچسبِ تازه‌ی منو: «فرصت‌های رایگان»")
ok("فارم و ماینینگ" not in _i18, "برچسبِ قدیمیِ «فارم و ماینینگ» از منو حذف شده")

print(f"\n===== نتیجه: {_PASS} سبز / {_FAIL} قرمز =====")
sys.exit(1 if _FAIL else 0)
