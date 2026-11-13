# -*- coding: utf-8 -*-
"""تست بخش «فرصت‌های رایگان» — core/opportunities.py + pages/9_Free_Opportunities.py
====================================================================================
چرخشِ به درخواست کاربر: بخش‌های فارمینگ/ماینینگ و استخرهای DefiLlama کامل حذف
شدند — این تست حالا تمرکز روی دو زیربخشِ باقی‌مانده دارد + حذفِ کاملِ ردِ فارم/ماین.

بخش‌ها:
  ۱) ساختار: فایل‌ها (با نامِ تازه‌ی صفحه)، ثبت منو (p9)، آپدیت sweep به ۹ صفحه
  ۱ب) حذفِ کامل: نه در هسته (fetch_llama_pools/honest_pools/MINING_KINDS/…)
      نه در صفحه (تب فارم/ماین، استخر، برچسب‌ها) — هیچ ردی نمی‌ماند
  ۲) برچسب هزینه: COST_FREE/COST_PAID
  ۳) scam_check: قاعده‌ی قطعی seed=۱۰۰، کف ۸۵ برای وعده‌ی تضمینی، سبزها کم می‌کنند،
     پایه‌ی بی‌طرف ۳۰، سطح‌بندی، tips
  ۴) VERIFY_TOOLS: ابزارهای راستی‌آزمایی شناخته‌شده با لینک https
  ۵) محتوای دست‌چین: TESTNET_HUNTS/SYBIL_RULES/STARTER_GUIDE + ترجمه‌ها + سؤال‌ها
  ۶) مارکرهای صفحه: سه تب (رایگان/کارگاه کیفیت/ضدکلاهبرداری) + جدول تست‌نت‌ها
اجرای صفر-ادعا: هیچ شبکه‌ای لازم نیست — داده‌ها آفلاین و دست‌چین‌اند.
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
section("ساختار پروژه")
ok(os.path.exists(ROOT / "core" / "opportunities.py"), "core/opportunities.py موجود است")
ok(os.path.exists(ROOT / "pages" / "9_Free_Opportunities.py"),
   "pages/9_Free_Opportunities.py موجود است (نامِ تازه)")
ok(not os.path.exists(ROOT / "pages" / "9_Farm_Airdrops.py"),
   "pages/9_Farm_Airdrops.py حذف شده است")
_ch = _sp.run([sys.executable, "-m", "py_compile", str(ROOT / "core" / "opportunities.py"),
               str(ROOT / "pages" / "9_Free_Opportunities.py")],
              capture_output=True, text=True, timeout=60)
ok(_ch.returncode == 0, f"کامپایل core و صفحه {_ch.stderr.strip()[:120]}")
_i18 = (ROOT / "core" / "i18n.py").read_text(encoding="utf-8")
ok('"p9", "pages/9_Free_Opportunities.py"' in _i18, "صفحه p9 با مسیرِ تازه در NAV_PAGES ثبت شده")
ok('["main", "p1", "p2", "p4", "p5", "p9"]' in _i18, "p9 در گروه کریپتو مانده است")
_sweep = (ROOT / "scripts" / "test_apptest_sweep.py").read_text(encoding="utf-8")
ok("len(PAGES) == 10" in _sweep, "sweep به ۱۰ صفحه آپدیت است")
_pg = (ROOT / "pages" / "9_Free_Opportunities.py").read_text(encoding="utf-8")
for frag in ("set_page_config", "from core import opportunities as OP",
             "OP.scam_check", "OP.testnet_rows", "from core import scouts as SC"):
    ok(frag in _pg, f"مارکر صفحه «{frag}»")

# ---------------------------------------------------------------- ۱ب) حذف کامل
section("حذفِ کاملِ ردِ فارم/ماین/استخر")
from core import opportunities as OP  # noqa: E402

for attr in ("fetch_llama_pools", "fetch_project_urls", "honest_pools", "honesty_score",
             "top_chains", "clean_site", "APP_LINKS", "MINING_KINDS",
             "LLAMA_YIELDS_URL", "LLAMA_PROTOCOLS_URL", "POOL_URL"):
    ok(not hasattr(OP, attr), f"هسته دیگر «{attr}» ندارد")
_op_txt = (ROOT / "core" / "opportunities.py").read_text(encoding="utf-8")
for bad in ("llama.fi/pools", "defillama.com/yields", "ماینینگ", "فارمینگ"):
    ok(bad not in _op_txt, f"ردِ حذف‌شده در هسته نیست: «{bad}»")
_pg_low = _pg.lower()
for bad in ("فارم", "ماین", "farm", "mining", "llama", "honest_pools", "mining_kinds",
            "t_farm", "t_mine", "_pools_cached", "tvlm", "apy"):
    ok(bad not in _pg_low, f"ردِ حذف‌شده در صفحه نیست: «{bad}»")

# ---------------------------------------------------------------- ۲) برچسب هزینه
section("برچسب هزینه (رایگان/پولی)")
ok(OP.COST_FREE == "🟢 رایگان" and "رایگان" in OP.COST_FREE, "برچسب هزینه‌ی رایگان")
ok("پولی" in OP.COST_PAID, "برچسب هزینه‌ی پولی")

# ---------------------------------------------------------------- ۳) ضدکلاهبرداری
section("scam_check (قواعد قطعی)")
_ans_seed = {q["key"]: OP.NO for q in OP.SCAM_QUESTIONS}
_ans_seed["seed"] = OP.YES
r_seed = OP.scam_check(_ans_seed)
ok(r_seed["risk"] == 100 and "کلاهبرداری" in r_seed["level"],
   f"درخواست Seed → ۱۰۰ «{r_seed['level']}»")
_ans_g = {q["key"]: OP.NO for q in OP.SCAM_QUESTIONS}
_ans_g["guarantee"] = OP.YES
r_g = OP.scam_check(_ans_g)
ok(r_g["risk"] >= 85 and r_g["risk"] < 100, f"وعده‌ی تضمینی → کف ۸۵ ({r_g['risk']})")
_ans_p = {q["key"]: OP.NO for q in OP.SCAM_QUESTIONS}
_ans_p["pyramid"] = OP.YES
r_p = OP.scam_check(_ans_p)
ok(50 <= r_p["risk"] < 75 and r_p["level"] == "مشکوک",
   f"هرمی → ناحیه‌ی مشکوک ({r_p['risk']})")
_ans_lock = {q["key"]: OP.NO for q in OP.SCAM_QUESTIONS}
_ans_lock["withdraw_lock"] = OP.YES
r_l = OP.scam_check(_ans_lock)
ok(55 <= r_l["risk"] < 75, f"قفلِ برداشت پشتِ سپرده → ناحیه‌ی خطر ({r_l['risk']})")
_ans_urg = {q["key"]: OP.NO for q in OP.SCAM_QUESTIONS}
_ans_urg["urgency"] = OP.YES
r_u = OP.scam_check(_ans_urg)
ok(50 <= r_u["risk"] < 75, f"فشار زمانی + کارمزد فعال‌سازی → ناحیه‌ی مشکوک ({r_u['risk']})")
_ans_safe = {q["key"]: OP.NO for q in OP.SCAM_QUESTIONS}
_ans_safe.update({q["key"]: OP.YES for q in OP.SCAM_QUESTIONS if q["kind"] == "green"})
r_safe = OP.scam_check(_ans_safe)
ok(r_safe["risk"] <= 22 and r_safe["bucket"] == "پایین",
   f"همه‌ی سبزها → پایین‌تر از پایه‌ی بی‌طرف ({r_safe['risk']})")
r_unk = OP.scam_check({})
ok(r_unk["risk"] == 30 and r_unk["bucket"] == "متوسط",
   f"همه‌ی «نمی‌دانم» → پایه‌ی بی‌طرف ۳۰ «قابل بررسی با احتیاط» ({r_unk['risk']})")
ok(0 <= r_unk["risk"] <= 100 and 0 <= r_g["risk"] <= 100, "خطر همیشه در ۰-۱۰۰")
ok(isinstance(r_seed["tips"], list) and r_seed["tips"], "توصیه‌های سطحی برمی‌گردند")
ok(isinstance(r_seed["verdict"], str) and r_seed["verdict"], "حکمِ متنی برمی‌گردد")
ok(isinstance(r_seed["color"], str) and r_seed["color"].startswith("#"), "رنگِ سطح معتبر است")
_keys = [q["key"] for q in OP.SCAM_QUESTIONS]
ok(len(_keys) == len(set(_keys)) and len(_keys) >= 10, f"کلیدهای سؤال یکتا و ≥۱۰ ({len(_keys)})")
ok(all(q.get("weight", 0) > 0 for q in OP.SCAM_QUESTIONS), "همه‌ی وزن‌ها مثبت")
_seedq = next(q for q in OP.SCAM_QUESTIONS if q["key"] == "seed")
ok(_seedq.get("hard") is True, "سؤال seed قاعده‌ی قطعی (hard) دارد")
ok(all(q.get("en") for q in OP.SCAM_QUESTIONS), "همه‌ی سؤال‌ها ترجمه‌ی انگلیسی دارند")
_reds = [q for q in OP.SCAM_QUESTIONS if q["kind"] == "red"]
_greens = [q for q in OP.SCAM_QUESTIONS if q["kind"] == "green"]
ok(len(_reds) >= 5 and len(_greens) >= 3, f"ترکیبِ سؤال‌ها: {len(_reds)} قرمز + {len(_greens)} سبز")

# ---------------------------------------------------------------- ۴) ابزارها
section("VERIFY_TOOLS (ابزارهای راستی‌آزمایی)")
ok(len(OP.VERIFY_TOOLS) >= 5, f"≥۵ ابزار راستی‌آزمایی ({len(OP.VERIFY_TOOLS)})")
ok(all(str(t.get("url", "")).startswith("https://") for t in OP.VERIFY_TOOLS),
   "همه‌ی ابزارها لینک https دارند")
ok(all(t.get("name") and t.get("what") and t.get("what_en") for t in OP.VERIFY_TOOLS),
   "هر ابزار نام + توضیح فارسی/انگلیسی دارد")
_known = {"defillama.com", "gopluslabs.io", "de.fi", "tokensniffer.com",
          "certik.com", "dappradar.com"}
_hosts = {t["url"].split("//", 1)[1].rstrip("/") for t in OP.VERIFY_TOOLS}
ok(_hosts <= _known or all(any(h == k or h.endswith("." + k) or h.startswith(k) for k in _known)
                           for h in _hosts), f"دامنه‌ها فقط ابزارهای شناخته‌شده‌اند ({_hosts})")

# ---------------------------------------------------------------- ۵) محتوا
section("محتوای دست‌چین (تست‌نت/ایردراپ)")
ok(len(OP.TESTNET_HUNTS) >= 6, f"≥۶ تست‌نت دست‌چین ({len(OP.TESTNET_HUNTS)})")
ok(all(h.get("name") and h.get("kind") and h.get("note") and h.get("added")
       and h.get("effort") and h.get("steps") and str(h.get("link", "")).startswith("https")
       for h in OP.TESTNET_HUNTS), "همه‌ی ورودی‌ها فیلد کامل + لینک https دارند")
ok(all(len(h["steps"]) >= 2 for h in OP.TESTNET_HUNTS), "هر ورودی حداقل ۲ گام دارد")
ok(all(len(h["added"]) == 10 and h["added"][4] == "-" for h in OP.TESTNET_HUNTS),
   "تاریخ ثبت‌ها به قالب YYYY-MM-DD")
ok(all(isinstance(h.get("minutes"), int) and h["minutes"] >= 5 for h in OP.TESTNET_HUNTS),
   "همه‌ی ورودی‌ها فیلد minutes (شفافیتِ زمان) دارند")
ok(OP.AIRDROP_SOURCE_URL.startswith("https://airdropalert.com"), "منبع فهرست مشخص است")
ok(len(OP.SYBIL_RULES) >= 5 and len(OP.SYBIL_RULES_EN) == len(OP.SYBIL_RULES),
   "قواعد ضدسفل ≥۵ و ترجمه‌ی هم‌طول")
ok(len(OP.STARTER_GUIDE) >= 4 and len(OP.STARTER_GUIDE_EN) == len(OP.STARTER_GUIDE),
   "راهنمای شروع ≥۴ و ترجمه‌ی هم‌طول")
ok("seed phrase" in OP.DISCLAIMER.lower() and "seed phrase" in OP.DISCLAIMER_EN.lower(),
   "دیسبلمر هشدار Seed دارد")
_rows3 = OP.testnet_rows()
ok(_rows3 and all(r.get("نام") and r.get("هزینه") == "🟢 رایگان — فقط زمان" for r in _rows3),
   "testnet_rows: جدول فارسی با نشان «🟢 رایگان — فقط زمان»")
ok(all(r.get("منبع") == OP.AIRDROP_SOURCE_URL for r in _rows3),
   "ستونِ منبعِ همه‌ی ردیف‌ها = مرجعِ بررسی‌شده")

# ---------------------------------------------------------------- ۶) صفحه
section("مارکرهای سه تب صفحه")
for frag in ("🎁 رایگان — تست‌نت و ایردراپ", "🤖 کارگاه کیفیت", "🛡 ضدکلاهبرداری",
             "t_free, t_scout, t_scam = st.tabs(", "OP.AIRDROP_SOURCE_URL",
             "st.link_button", "شروع از صفر", "قواعد ضدسفل", "SCAM_QUESTIONS",
             "محاسبه‌ی سطح خطر", "OP.VERIFY_TOOLS", "airdropalert ↗",
             "SC.run_arena", "SC.repo_scan"):
    ok(frag in _pg, f"مارکر صفحه «{frag}»")

print(f"\n===== نتیجه: {_PASS} سبز / {_FAIL} قرمز =====")
sys.exit(1 if _FAIL else 0)
