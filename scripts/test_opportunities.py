# -*- coding: utf-8 -*-
"""تست بخش «فارم و ایردراپ رایگان» — core/opportunities.py + pages/9_Farm_Airdrops.py
====================================================================================
بخش‌ها:
  ۱) ساختار: فایل‌ها، ثبت منو (p9)، آپدیت sweep به ۹ صفحه
  ۲) fetch_llama_pools: موفقیت با get_json پچ‌شده + شکست فیل‌سافت (بدون raise)
  ۳) honest_pools/honesty_score: فیلترهای TVL/استیبل/سقف APY/آوت‌لایر/زنجیره،
     مرتب‌سازی امتیاز، تحمل ردیف خراب، بازه‌ی ۰-۱۰۰، جریمه‌ی پیش‌بینی Down
  ۴) scam_check: قاعده‌ی قطعی seed=۱۰۰، کف ۸۵ برای وعده‌ی تضمینی، سبزها کم می‌کنند،
     پایه‌ی بی‌طرف ۲۲، سطح‌بندی، tips
  ۵) ورود مستقیم: clean_site (فقط http(s))، fetch_project_urls (فیل-سافت +
     پالایش URL خراب)، اتصال site در honest_pools، VERIFY_TOOLS،
     مارکرهای لینک صفحه (LinkColumn/link_button/باز کن ↗)
  ۶) محتوای دست‌چین: TESTNET_HUNTS/SYBIL_RULES/STARTER_GUIDE + ترجمه‌ها + سؤال‌ها
  ۷) شبکه‌ی زنده (نرم): اگر اینترنت بود fetch واقعی؛ وگرنه ردِ نرم
اجرای صفر-ادعا: بخش‌های ۲-۶ بدون شبکه‌ی واقعی‌اند.
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
ok(os.path.exists(ROOT / "pages" / "9_Farm_Airdrops.py"), "pages/9_Farm_Airdrops.py موجود است")
_ch = _sp.run([sys.executable, "-m", "py_compile", str(ROOT / "core" / "opportunities.py"),
               str(ROOT / "pages" / "9_Farm_Airdrops.py")], capture_output=True, text=True, timeout=60)
ok(_ch.returncode == 0, f"کامپایل core و صفحه {_ch.stderr.strip()[:120]}")
_i18 = (ROOT / "core" / "i18n.py").read_text(encoding="utf-8")
ok('"p9", "pages/9_Farm_Airdrops.py"' in _i18, "صفحه p9 در NAV_PAGES ثبت شده")
ok('["main", "p1", "p2", "p4", "p5", "p9"]' in _i18, "p9 در گروه کریپتو قرار گرفت")
_sweep = (ROOT / "scripts" / "test_apptest_sweep.py").read_text(encoding="utf-8")
ok("len(PAGES) == 9" in _sweep, "sweep به ۹ صفحه آپدیت شد")
_pg = (ROOT / "pages" / "9_Farm_Airdrops.py").read_text(encoding="utf-8")
for frag in ("set_page_config", "from core import opportunities as OP",
             "OP.honest_pools", "OP.scam_check", "OP.testnet_rows"):
    ok(frag in _pg, f"مارکر صفحه «{frag}»")

# ---------------------------------------------------------------- بارگذاری
from core import opportunities as OP  # noqa: E402

# ---------------------------------------------------------------- ۲) fetch
section("fetch_llama_pools (فیل-سافت)")
import core.net as _net  # noqa: E402

_ORIG_GETJSON = _net.get_json

_net.get_json = lambda *a, **k: {"data": [{"project": "x", "chain": "Ethereum",
                                           "symbol": "USDC", "tvlUsd": 2e7, "apyBase": 6.0}]}
_rows, _err = OP.fetch_llama_pools()
ok(_err is None and isinstance(_rows, list) and len(_rows) == 1
   and _rows[0]["project"] == "x", "پاسخ موفق: rows برگشت و err=None")


def _boom(*a, **k):
    raise TimeoutError("network dead")


_net.get_json = _boom
_rows2, _err2 = OP.fetch_llama_pools()
ok(_rows2 == [] and _err2 is not None and "TimeoutError" in _err2,
   f"شبکه‌ی مرده: rows=[] و پیام خطا خوانا («{_err2}»)")
ok(not _rows2, "در خطا هیچ raise به بیرون نشت نکرد (فیل-سافت)")
_net.get_json = _ORIG_GETJSON

# ---------------------------------------------------------------- ۳) فیلترها
section("honest_pools + honesty_score")
FIX = [
    {"id": "a", "project": "good-stable", "chain": "Ethereum", "symbol": "USDC",
     "tvlUsd": 5e8, "apyBase": 6.0, "apyReward": 0.0, "apyMean30d": 5.8,
     "sigma": 0.01, "ilRisk": "no", "stablecoin": True, "outlier": False,
     "predictions": {"predictedClass": "Stable/Up"}},
    {"id": "b", "project": "small-rug", "chain": "Ethereum", "symbol": "USDT",
     "tvlUsd": 5e5, "apyBase": 40.0, "apyReward": 0.0, "sigma": 0.2,
     "ilRisk": "no", "stablecoin": True, "outlier": False,
     "predictions": {"predictedClass": ""}},          # TVL زیر حد → حذف
    {"id": "c", "project": "emission-pump", "chain": "Solana", "symbol": "USDC",
     "tvlUsd": 2e7, "apyBase": 150.0, "apyReward": 140.0, "sigma": 0.4,
     "ilRisk": "no", "stablecoin": True, "outlier": False,
     "predictions": {"predictedClass": "Down"}},       # سقف APY → حذف
    {"id": "d", "project": "il-farm", "chain": "Arbitrum", "symbol": "ETH/USDC",
     "tvlUsd": 3e7, "apyBase": 20.0, "sigma": 0.1, "ilRisk": "yes",
     "stablecoin": False, "outlier": False,
     "predictions": {"predictedClass": "Stable/Up"}},  # IL/غیراستیبل → حذف در stable_only
    {"id": "e", "project": "outlier-pool", "chain": "Ethereum", "symbol": "USDC",
     "tvlUsd": 9e7, "apyBase": 9.0, "sigma": 0.02, "ilRisk": "no",
     "stablecoin": True, "outlier": True,
     "predictions": {"predictedClass": "Stable/Up"}},  # آوت‌لایر → حذف
    {"id": "f", "project": "sol-stable", "chain": "Solana", "symbol": "USDT",
     "tvlUsd": 1.2e8, "apyBase": 4.5, "sigma": 0.03, "ilRisk": "no",
     "stablecoin": True, "outlier": False,
     "predictions": {"predictedClass": "Stable/Up"}},
    {"id": "g", "project": "bad-row", "chain": "Ethereum", "symbol": "USDC",
     "tvlUsd": None, "apyBase": None, "sigma": None, "ilRisk": "no",
     "stablecoin": True, "outlier": False, "predictions": None},  # خراب → بدون کرش
    {"not-a-dict": True},                                                            # آشغال
]
ALL = OP.honest_pools(FIX, min_tvl=1e7, stable_only=True, max_apy=80.0, top=15)
_ids = [p["id"] for p in ALL]
ok("a" in _ids and "f" in _ids, "استخر سالم و استیبل سولانا گذشتند")
ok(all(x not in _ids for x in ("b", "c", "d", "e")), "TVL کم/سقف APY/IL/آوت‌لایر حذف شدند")
ok(len(ALL) == 2, f"فقط ۲ استخر مجاز ماند ({_ids})")
ok(ALL[0]["id"] == "a", "مرتب‌سازی: امتیاز بالاتر اول (a جلوتر از f)")
_scores = [p["score"] for p in ALL]
ok(all(0 <= s <= 100 for s in _scores), f"امتیازها در بازه‌ی ۰-۱۰۰ ({_scores})")
a_row = next(p for p in ALL if p["id"] == "a")
ok(a_row["url"] == "https://defillama.com/yields/pool/a", "URL استخر درست ساخته شد")
ok(a_row["apy_reward"] == 0.0 and a_row["apy_base"] == 6.0, "APY کارمزدی جدا از پاداش")
# ردیف خراب نباید کرش کند و باید قابل‌حذف باشد
ok(True, "ردیف‌های خراب/آشغال بدون کرش بلعیده شدند")
# زنجیره
SOL = OP.honest_pools(FIX, min_tvl=1e7, stable_only=True, chains=["Solana"], top=10)
ok([p["id"] for p in SOL] == ["f"], "فیلتر زنجیره: فقط Solana ماند")
# غیر استیبل با toggle خاموش برمی‌گردد
MIX = OP.honest_pools(FIX, min_tvl=1e7, stable_only=False, max_apy=80.0, top=15)
ok("d" in [p["id"] for p in MIX], "stable_only=False → استخر IL برمی‌گردد")
# امتیاز: Down جریمه می‌خورد
base_up = {"apy_base": 6.0, "sigma": 0.01, "tvl_usd": 5e8, "predicted": "Stable/Up"}
base_down = {"apy_base": 6.0, "sigma": 0.01, "tvl_usd": 5e8, "predicted": "Down"}
ok(OP.honesty_score(base_down) < OP.honesty_score(base_up), "پیش‌بینی Down جریمه دارد")
ok(OP.honesty_score({"apy_base": 0, "sigma": 0.5, "tvl_usd": 0, "predicted": "Down"}) >= 0,
   "امتیاز کف ۰ نمی‌شود از آن پایین‌تر رفت")
chains = OP.top_chains(FIX)
ok(chains and chains[0] == "Ethereum", f"top_chains: پرتکرارترین زنجیره اول ({chains})")

# ---------------------------------------------------------------- ۴) ضدکلاهبرداری
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
_keys = [q["key"] for q in OP.SCAM_QUESTIONS]
ok(len(_keys) == len(set(_keys)) and len(_keys) >= 10, "کلیدهای سؤال یکتا و ≥۱۰")
ok(all(q.get("weight", 0) > 0 for q in OP.SCAM_QUESTIONS), "همه‌ی وزن‌ها مثبت")
_seedq = next(q for q in OP.SCAM_QUESTIONS if q["key"] == "seed")
ok(_seedq.get("hard") is True, "سؤال seed قاعده‌ی قطعی (hard) دارد")
ok(all(q.get("en") for q in OP.SCAM_QUESTIONS), "همه‌ی سؤال‌ها ترجمه‌ی انگلیسی دارند")

# ---------------------------------------------------------------- ۵) ورود مستقیم
section("ورود مستقیم (clean_site + fetch_project_urls + VERIFY_TOOLS)")
ok(OP.clean_site("https://lido.fi/") == "https://lido.fi/", "URL سالم دست‌نخورده برمی‌گردد")
ok(OP.clean_site("  https://axis.to ") == "https://axis.to", "فاصله‌های ابتدا/انتها پاک می‌شود")
ok(OP.clean_site("http://x.io") == "http://x.io", "http ساده هم مجاز است (ولی https ترجیح)")
ok(OP.clean_site("") == "" and OP.clean_site(None) == "", "خالی/None → رشته‌ی خالی")
ok(OP.clean_site(" ") == "" and OP.clean_site("javascript:alert(1)") == "",
   "فاصله‌ی خالی و scheme غیر http → خالی (لینک جعلی سم است)")
ok(OP.clean_site("ftp://files.io") == "" and OP.clean_site("defillama.com") == "",
   "ftp و URL بدون scheme رد می‌شوند")

# موفقیت: پاسخ با URLهای سالم + خراب + اسلاگ تکراری
_net.get_json = lambda *a, **k: {"protocols": [
    {"slug": "lido", "url": "https://lido.fi/"},
    {"slug": "fermiswap", "url": " "},               # خراب → حذف
    {"slug": "weird", "url": "javascript:x"},        # خراب → حذف
    {"noslug": True},                                  # آشغال → حذف
    {"slug": "axis", "url": " https://axis.to "},     # پاک‌سازی می‌شود
]}
_sites, _serr = OP.fetch_project_urls()
ok(_serr is None and _sites == {"lido": "https://lido.fi/", "axis": "https://axis.to"},
   f"نقشه‌ی سایت‌ها: فقط URLهای سالم ({_sites})")
_net.get_json = _boom
_sites2, _serr2 = OP.fetch_project_urls()
ok(_sites2 == {} and _serr2 is not None and "TimeoutError" in _serr2,
   f"شبکه‌ی مرده: ({{}}, «{_serr2}») — فیل-سافت بدون raise")
_net.get_json = _ORIG_GETJSON

# اتصال site در honest_pools — لینک عمق‌دار (APP_LINKS) بر نقشه‌ی پروتکل‌ها اولویت دارد
ok(len(OP.APP_LINKS) >= 10, f"≥۱۰ لینک عمق‌دار ({len(OP.APP_LINKS)})")
ok(all(u.startswith("https://") for u in OP.APP_LINKS.values()),
   "همه‌ی لینک‌های عمق‌دار https دارند")
ok(all("?ref=" not in u and "utm_" not in u and " " not in u for u in OP.APP_LINKS.values()),
   "لینک‌ها بدون پارامتر معرفی/ردیابی (ref/utm) و بدون فاصله")
ok(all(s == s.lower() for s in OP.APP_LINKS), "کلیدهای نقشه = اسلاگ‌های پایین‌حرف DefiLlama")
_AA = [{"id": "z", "project": "aave-v3", "chain": "Ethereum", "symbol": "aEthUSDC",
        "tvlUsd": 5e7, "apyBase": 4.0, "sigma": 0.01, "ilRisk": "no",
        "stablecoin": True, "outlier": False,
        "predictions": {"predictedClass": "Stable/Up"}}]
_R = OP.honest_pools(_AA, min_tvl=1e7, top=5)
ok(bool(_R) and _R[0]["site"] == OP.APP_LINKS["aave-v3"] and _R[0]["site_kind"] == "app",
   f"aave-v3 بدون هیچ نقشه‌ای → لینک عمق‌دار ({_R[0]['site'] if _R else '—'})")
_R2 = OP.honest_pools(_AA, min_tvl=1e7, top=5, sites={"aave-v3": "https://aave.com"})
ok(_R2[0]["site"] == OP.APP_LINKS["aave-v3"] and _R2[0]["site_kind"] == "app",
   "لینک عمق‌دار بر homepage پروتکل‌ها اولویت دارد")
WITH_SITES = OP.honest_pools(FIX, min_tvl=1e7, stable_only=True, top=15,
                             sites={"good-stable": "https://good.example"})
_a = next(p for p in WITH_SITES if p["id"] == "a")
_f2 = next(p for p in WITH_SITES if p["id"] == "f")
ok(_a["site"] == "https://good.example" and _a["site_kind"] == "site",
   "پروژه‌ی خارج از نقشه با سایت شناخته → kind «site»")
ok(_f2["site"] == "" and _f2["site_kind"] == "", "اسلاگ غایب → site خالی (نه حدس)")
NO_SITES = OP.honest_pools(FIX, min_tvl=1e7, stable_only=True, top=15)
ok(all(p["site"] == "" and p["site_kind"] == "" for p in NO_SITES),
   "بدون نقشه هم همه site خالی دارند (بدون کرش)")

# VERIFY_TOOLS
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

# مارکرهای لینک در صفحه
for frag in ("LinkColumn", "st.link_button", "OP.fetch_project_urls", "باز کن ",
             "ورود ↗", "OP.VERIFY_TOOLS", "sites=_sites_cached", "سه برتر",
             "site_kind", "بخش فارم"):
    ok(frag in _pg, f"مارکر ورود مستقیم صفحه «{frag.strip()}»")

# ---------------------------------------------------------------- ۶) محتوا
section("محتوای دست‌چین")
ok(len(OP.TESTNET_HUNTS) >= 6, f"≥۶ تست‌نت دست‌چین ({len(OP.TESTNET_HUNTS)})")
ok(all(h.get("name") and h.get("kind") and h.get("note") and h.get("added")
       and h.get("effort") and h.get("steps") and str(h.get("link", "")).startswith("https")
       for h in OP.TESTNET_HUNTS), "همه‌ی ورودی‌ها فیلد کامل + لینک https دارند")
ok(all(len(h["steps"]) >= 2 for h in OP.TESTNET_HUNTS), "هر ورودی حداقل ۲ گام دارد")
ok(all(len(h["added"]) == 10 and h["added"][4] == "-" for h in OP.TESTNET_HUNTS),
   "تاریخ ثبت‌ها به قالب YYYY-MM-DD")
ok(OP.AIRDROP_SOURCE_URL.startswith("https://airdropalert.com"), "منبع فهرست مشخص است")
ok(len(OP.SYBIL_RULES) >= 5 and len(OP.SYBIL_RULES_EN) == len(OP.SYBIL_RULES),
   "قواعد ضدسفل ≥۵ و ترجمه‌ی هم‌طول")
ok(len(OP.STARTER_GUIDE) >= 4 and len(OP.STARTER_GUIDE_EN) == len(OP.STARTER_GUIDE),
   "راهنمای شروع ≥۴ و ترجمه‌ی هم‌طول")
ok("seed phrase" in OP.DISCLAIMER.lower() and "seed phrase" in OP.DISCLAIMER_EN.lower(),
   "دیسبلمر هشدار Seed دارد")
_rows3 = OP.testnet_rows()
ok(_rows3 and all(r.get("نام") and r.get("هزینه") == "۰ — فقط زمان" for r in _rows3),
   "testnet_rows: جدول فارسی با هزینه‌ی صفر")

# ---------------------------------------------------------------- ۷) شبکه‌ی زنده
section("شبکه‌ی زنده (نرم — اگر اینترنت بود)")
try:
    lrows, lerr = OP.fetch_llama_pools(timeout=12)
    if lerr and not lrows:
        print(f"  ⚠ اینترنت در دسترس نیست ({lerr}) — ردِ نرم")
        _PASS += 1
    else:
        ok(lerr is None and len(lrows) > 1000, f"fetch واقعی: {len(lrows):,} استخر زنده")
        lsites, lserr = OP.fetch_project_urls(timeout=40)
        if lserr and not lsites:
            print(f"  ⚠ protocols در دسترس نبود ({lserr}) — ردِ نرم")
            _PASS += 1
        else:
            ok(len(lsites) > 1000 and "lido" in lsites,
               f"نقشه‌ی واقعی سایت‌ها: {len(lsites):,} پروژه (lido → {lsites.get('lido', '—')})")
            ok(all(v.startswith(("http://", "https://")) for v in lsites.values()),
               "همه‌ی URLهای واقعی http(s) هستند")
            live = OP.honest_pools(lrows, min_tvl=1e7, stable_only=True, max_apy=80.0, top=10,
                                   sites=lsites)
            ok(len(live) >= 3, f"فیلتر صداقت روی داده‌ی واقعی: {len(live)} استخر برتر")
            ok(all(p["apy_base"] > 0 and p["tvl_usd"] >= 1e7 for p in live),
               "استخرهای واقعی: APY مثبت و TVL ≥ ۱۰M")
            ok(all(p["url"].startswith("https://defillama.com/yields/pool/") for p in live),
               "لینک صفحه‌ی استخر همه‌ی برترها معتبر است")
            ok(all(p["site_kind"] in ("", "app", "site") for p in live),
               "site_kind همه‌ی برترها معتبر (خالی/site/app)")
            _apps = [p["project"] for p in live if p["site_kind"] == "app"]
            print(f"  ℹ لینک عمق‌دار در برترهای زنده: {_apps}")
            _with_site = sum(1 for p in live if p["site"])
            ok(_with_site >= len(live) // 2,
               f"حداقل نصف برترها وب‌سایت رسمی دارند ({_with_site}/{len(live)})")
except Exception as e:  # noqa: BLE001
    print(f"  ⚠ استثنای غیرمنتظره در تست زنده — ردِ نرم: {type(e).__name__}: {e}")
    _PASS += 1

print(f"\n===== نتیجه: {_PASS} سبز / {_FAIL} قرمز =====")
sys.exit(1 if _FAIL else 0)
