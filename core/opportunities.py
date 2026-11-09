# -*- coding: utf-8 -*-
"""core/opportunities.py — بخش «فارم و ایردراپ رایگان»
======================================================
فلسفه‌ی این بخش: **داده‌ی واقعی، نه وعده.** قانون طلاییِ نوشته‌شده در صفحه:
«رایگان + سود خوب + مطمئن» با هم وجود ندارند؛ سود واقعی همیشه سرمایه، زمان
یا مهارت می‌گیرد.

چهار زیربخش — دسته‌بندی ۴گانه به درخواست کاربر («گیج نشن و دنبالش نگردن»):
  ۱) 🌾 فارمینگ — 🔴 پولی: استخرهای زنده از API رایگان DefiLlama (بدون کلید،
     بدون ثبت‌نام) با «امتیاز صداقت»: APY کارمزدی جدا از APY توکن پاداشِ
     ایمی‌شونده، نوسان بازده (sigma)، اعتبار TVL و پیش‌بینی خودِ DefiLlama.
     اینجا «رایگان» فقط یعنی نمایشِ داده رایگان است — برای شرکت باید سرمایه واریز کنی.
  ۲) ⛏ ماینینگ — سه دنیای متفاوت با یک نام: موبایلی (🟢 رایگان، اما لاتاری)
     / هاردواری ASIC (🔴 پولی) / ابری (🔴 پولی و پرخطر — پانزی).
  ۳) 🎁 رایگان — تست‌نت/ایردراپ: فهرست دست‌چینِ هزینه‌ی صفر (فقط زمان) + قواعد ضدسفل.
  ۴) 🛡 آزمایشگر ضدکلاهبرداری — چک‌لیست وزن‌دار ۱۰ سؤالی با قواعد قطعی
     (درخواست Seed Phrase = ۱۰۰ خطر، بی‌چون‌وچرا).

هر فرصتِ نمایش‌داده‌شده «ورود مستقیم» دارد: ستون لینکِ صفحه‌ی استخر در
DefiLlama (نمودار + تاریخچه) و ستون «وب‌سایت رسمی» که از همان فهرست کامل
پروتکل‌های DefiLlama حل می‌شود — یعنی کاربر با یک کلیک وارد پروژه می‌شود،
نه اینکه نامش را در گوگل بگردد (جایی که لینک‌های فیشینگ کمین کرده‌اند).
برای تست‌نت‌ها عمداً لینک مستقیمِ دست‌ساز نمی‌گذاریم: دامنه‌ی هر پروژه
از صفحه‌ی مرجعِ بررسی‌شده باز می‌شود تا لینک جعلی جای نگیرد.

تمام درخواست‌های شبکه fail-soft هستند: خطا raise نمی‌شود، به‌صورت پیام
خوانا به صفحه برمی‌گردد و بدون اینترنت هم صفحه کار می‌کند.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

LLAMA_YIELDS_URL = "https://yields.llama.fi/pools"
LLAMA_PROTOCOLS_URL = "https://api.llama.fi/protocols"
POOL_URL = "https://defillama.com/yields/pool/{pid}"
AIRDROP_SOURCE_URL = "https://airdropalert.com/testnet-airdrops"

UNKNOWN = "نمی‌دانم"
YES = "بله"
NO = "خیر"

# --------------------------------------------------------------------------- #
# ۱) بازده واقعی — DefiLlama (رایگان و بدون کلید)                             #
# --------------------------------------------------------------------------- #
def fetch_llama_pools(timeout: float = 15.0) -> Tuple[List[dict], Optional[str]]:
    """استخرهای زنده‌ی DefiLlama — خروجی همیشه `(rows, err)`؛ هرگز raise نمی‌کند.

    rows = لیست استخرها (dict) یا [] در خطا. err = توضیح فارسی خطا یا None.
    """
    try:
        from core.net import get_json
        d = get_json(LLAMA_YIELDS_URL, timeout=timeout, retries=1)
        rows = d.get("data") if isinstance(d, dict) else d
        if not isinstance(rows, list):
            return [], "ساختار پاسخ DefiLlama ناشناخته بود"
        return rows, None
    except Exception as e:  # noqa: BLE001
        return [], (f"{type(e).__name__}: {e}")[:180]


def clean_site(url: Any) -> str:
    """URL وب‌سایت را پاک‌سازی و اعتبارسنجی می‌کند — فقط http(s) واقعی.

    خروجی خالی یعنی «آدرس رسمی معتبری نداریم» — هرگز حدس نمی‌زنیم؛ لینک
    اشتباه یا جعلی در بخش ضدکلاهبرداری سم است.
    """
    u = str(url or "").strip()
    if not u.lower().startswith(("http://", "https://")):
        return ""
    return u


def fetch_project_urls(timeout: float = 30.0) -> Tuple[Dict[str, str], Optional[str]]:
    """نقشه‌ی slug→وب‌سایت رسمی از فهرست کامل پروتکل‌های DefiLlama.

    یک درخواستِ واحد (~۹MB، کش ۲۴ ساعته در صفحه) برای ~۵هزار پروژه؛ آدرس
    غلط/خالی (فاصله، رشته‌ی غیر http) کنار گذاشته می‌شود. fail-soft: خطا
    یعنی ({}, پیام) — صفحه بدون این نقشه هم با لینک استخر کار می‌کند.
    """
    try:
        from core.net import get_json
        d = get_json(LLAMA_PROTOCOLS_URL, timeout=timeout, retries=1)
        rows = d.get("protocols") if isinstance(d, dict) else d
        if not isinstance(rows, list):
            return {}, "ساختار پاسخ protocols ناشناخته بود"
        sites: Dict[str, str] = {}
        for p in rows:
            if not isinstance(p, dict):
                continue
            slug = str(p.get("slug") or "")
            site = clean_site(p.get("url"))
            if slug and site:
                sites[slug] = site
        return sites, None
    except Exception as e:  # noqa: BLE001
        return {}, (f"{type(e).__name__}: {e}")[:180]


def _f(v: Any, default: float = 0.0) -> float:
    """float امن — None/NaN/رشته‌ی خراب → default (استخرهای ناقص نمی‌شکنند)."""
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def honesty_score(p: dict) -> int:
    """امتیاز صداقت ۰-۱۰۰ برای استخر نرمال‌شده.

      • بازدهِ کارمزدی (apy_base) — حداکثر ۴۰ نمره: واقعی‌ترین جزء سود
      • پایداری (sigma پایین) — حداکثر ۲۵ نمره: بازده‌ی دنس‌سویی می‌سوزد
      • اعتبار TVL (لگاریتمی از ۱۰M تا ۱B) — حداکثر ۲۰ نمره
      • پیش‌بینی DefiLlama («Stable/Up» +۱۵ / «Down» −۱۰)
    هیچ استخری ۱۰۰ قطعی نمی‌گیرد — همیشه ریسک هست.
    """
    s_ap = min(max(_f(p.get("apy_base")), 0.0), 30.0) / 30.0 * 40.0
    s_st = (1.0 - min(max(_f(p.get("sigma")), 0.0), 0.5) / 0.5) * 25.0
    tvl = max(_f(p.get("tvl_usd")), 0.0)
    s_tvl = min(math.log10(tvl / 1e6 + 1.0) / 2.0, 1.0) * 20.0
    pred = str(p.get("predicted") or "")
    s_pr = 15.0 if ("Up" in pred or "Stable" in pred) else (-10.0 if "Down" in pred else 0.0)
    return int(round(max(0.0, min(100.0, s_ap + s_st + s_tvl + s_pr))))


def honest_pools(rows: Optional[List[dict]], *, min_tvl: float = 10_000_000.0,
                 stable_only: bool = True, chains: Optional[List[str]] = None,
                 max_apy: float = 80.0, top: int = 15,
                 sites: Optional[Dict[str, str]] = None) -> List[dict]:
    """فیلترِ «صداقت» + امتیازدهی + مرتب‌سازی. ورودی خراب/ناقص را می‌بلعد.

    قواعد صادقانه:
      • فقط استخرهای با TVL ≥ min_tvl (استخرهای کوچک = rug راحت)
      • فقط بازدهِ کارمزدی (apy_base) — APY پاداش جدا گزارش می‌شود نه در رتبه
      • سقف APY پیش‌فرض ۸۰٪ — بالاتر از این معمولاً ایمیِشنِ موقتی است که می‌ریزد
      • stable_only: فقط استیبل‌کوین با IL=«no» (بدون زیان ناپایدار)
    """
    out: List[dict] = []
    for p in rows or []:
        if not isinstance(p, dict):
            continue
        if p.get("outlier"):
            continue
        tvl = _f(p.get("tvlUsd"), -1.0)
        if tvl < min_tvl:
            continue
        apy_base = _f(p.get("apyBase"), -1.0)
        if apy_base <= 0.05:
            continue
        if max_apy and apy_base > max_apy:
            continue
        if stable_only and (not p.get("stablecoin") or str(p.get("ilRisk", "")).lower() != "no"):
            continue
        if chains and str(p.get("chain", "")) not in chains:
            continue
        slug = str(p.get("project") or "")
        site = clean_site(APP_LINKS.get(slug) or (sites or {}).get(slug))
        it = {
            "id": str(p.get("id") or p.get("pool") or ""),
            "project": slug,
            "chain": str(p.get("chain") or "?"),
            "symbol": str(p.get("symbol") or "?"),
            "tvl_usd": tvl,
            "apy_base": apy_base,
            "apy_reward": _f(p.get("apyReward")),
            "apy": _f(p.get("apy")),
            "apy_mean30d": _f(p.get("apyMean30d")),
            "sigma": _f(p.get("sigma")),
            "il_risk": str(p.get("ilRisk") or ""),
            "stablecoin": bool(p.get("stablecoin")),
            "predicted": str((p.get("predictions") or {}).get("predictedClass") or ""),
            "url": POOL_URL.format(pid=p.get("id") or p.get("pool") or ""),
            "site": site,
            "site_kind": "app" if (slug in APP_LINKS and site) else ("site" if site else ""),
            "score": 0,
        }
        it["score"] = honesty_score(it)
        out.append(it)
    out.sort(key=lambda x: (-x["score"], -x["apy_base"]))
    return out[: max(1, int(top))]


def top_chains(rows: Optional[List[dict]], limit: int = 18) -> List[str]:
    """پرتکرارترین زنجیره‌ها از دل داده‌ی واقعی — برای فیلتر UI."""
    cnt: Dict[str, int] = {}
    for p in rows or []:
        if isinstance(p, dict):
            c = str(p.get("chain") or "")
            if c:
                cnt[c] = cnt.get(c, 0) + 1
    return [c for c, _ in sorted(cnt.items(), key=lambda kv: -kv[1])[:limit]]


# --------------------------------------------------------------------------- #
# ۲) آزمایشگر ضدکلاهبرداری                                                    #
# --------------------------------------------------------------------------- #
SCAM_QUESTIONS: List[Dict[str, Any]] = [
    {"key": "seed", "kind": "red", "weight": 100, "hard": True,
     "q": "سایت/اپ عبارت بازیابی (Seed Phrase) یا کلید خصوصی تو را درخواست می‌کند؟",
     "en": "Does the site/app ask for your seed phrase or private key?"},
    {"key": "guarantee", "kind": "red", "weight": 60,
     "q": "وعده‌ی «سود تضمینی» یا «دوبرابر شدن سرمایه» می‌دهد؟",
     "en": "Does it promise 'guaranteed profit' or 'double your money'?"},
    {"key": "pyramid", "kind": "red", "weight": 35,
     "q": "سودِ اصلی از دعوت اعضای جدید می‌آید (ساختار هرمی/MLM)؟",
     "en": "Is the main income from recruiting new members (pyramid/MLM)?"},
    {"key": "withdraw_lock", "kind": "red", "weight": 30,
     "q": "برداشت فقط بعد از سپرده‌ی بیشتر یا دوره‌ی قفل باز می‌شود؟",
     "en": "Is withdrawal unlocked only after a bigger deposit or a lock period?"},
    {"key": "urgency", "kind": "red", "weight": 25,
     "q": "فشار زمانی ساختگی دارد («فقط امروز»، «ظرفیت آخر») و برای فعال‌سازی کارمزد می‌خواهد؟",
     "en": "Fake urgency ('today only', 'last spots') plus an activation fee?"},
    {"key": "no_audit", "kind": "red", "weight": 20,
     "q": "قرارداد هوشمند ممیزی (Audit) معتبرِ عمومی ندارد؟",
     "en": "No public audit from a reputable auditor?"},
    {"key": "anon_team", "kind": "red", "weight": 15,
     "q": "تیم پروژه کاملاً ناشناس است و هیچ هویت قابل‌راستی‌آزمایی ندارد؟",
     "en": "Is the team fully anonymous with no verifiable identity?"},
    {"key": "audit", "kind": "green", "weight": 15,
     "q": "قرارداد توسط شرکت ممیزی شناخته‌شده (CertiK، Hacken، Trail of Bits و…) ممیزی و گزارشش عمومی است؟",
     "en": "Audited by a known firm (CertiK, Hacken, Trail of Bits…) with a public report?"},
    {"key": "tvl", "kind": "green", "weight": 15,
     "q": "TVL پروژه در DefiLlama قابل‌رصد است و چند ماه پایدار مانده؟",
     "en": "Is TVL trackable on DefiLlama and stable for months?"},
    {"key": "track", "kind": "green", "weight": 10,
     "q": "سابقه‌ی چندساله دارد و گزارش برداشت موفق از انجمن‌های مستقل زیاد است؟",
     "en": "Multi-year track record with many independent withdrawal success reports?"},
]

# ابزارهای راستی‌آزمایی با لینک مستقیم — همه‌ی این‌ها سایت‌های شناخته‌شده‌ی
# عمومی‌اند؛ کاربر با یک کلیک همان چیزی را چک می‌کند که چک‌لیست می‌پرسد.
VERIFY_TOOLS: List[Dict[str, str]] = [
    {"name": "DefiLlama", "url": "https://defillama.com",
     "what": "TVL و رتبه‌ی واقعی هر پروژه‌ی DeFi — اگر پروژه‌ای اینجا نیست، یعنی پول جدی داخلش نیست",
     "what_en": "Real TVL and ranking of every DeFi project — if it is not here, there is no serious money in it"},
    {"name": "GoPlus Security", "url": "https://gopluslabs.io",
     "what": "اسکن قرارداد/توکن: تله‌پـ، مالیات پنهان، دسترسی مالک — آدرس قرارداد را بچسبان",
     "what_en": "Contract/token scan: honeypot, hidden tax, owner powers — paste the contract address"},
    {"name": "De.Fi Scanner", "url": "https://de.fi/scanner",
     "what": "اسکن امنیتی قرارداد با نمره‌ی خطر — چک سریع پیش از هر تعامل",
     "what_en": "Contract security scanner with a risk score — quick check before any interaction"},
    {"name": "TokenSniffer", "url": "https://tokensniffer.com",
     "what": "اسکن سریع قرارداد + گزارش شباهت به قراردادهای کلاهبرداری شناخته‌شده",
     "what_en": "Quick contract scan + similarity to known scam contracts"},
    {"name": "CertiK", "url": "https://www.certik.com",
     "what": "چک ممیزی رسمی — اگر ادعای «ممیزی‌شده» دارند، اینجا گزارشش را ببین نه در سایت خودشان",
     "what_en": "Official audit check — if they claim 'audited', see the report here, not on their own site"},
    {"name": "DappRadar", "url": "https://dappradar.com",
     "what": "فعالیت واقعی کاربران روزانه — پروژه‌ی مرده فقط عدد ساختگی روی صفحه دارد",
     "what_en": "Real daily user activity — a dead project only has fake numbers on its own page"},
]

# لینک‌های عمق‌دار — مستقیم به صفحه‌ی اپ/فارمِ هر پروژه، نه صفحه‌ی تبلیغاتی اصلی.
# چرا؟ پرسش کاربر: «داخل سایت که می‌شی خیلی شلوغ و گمراه‌کننده‌ست؛ جوری بچین که
# مستقیم به همون قسمت فارم بره.» هر URL قبل از ورود به این نقشه با curl زنده
# راستی‌آزمایی شده (۹ نوامبر ۲۰۲۶)؛ ۴۰۳/۴۲۹ فقط بات‌بلاکِ کلاودفلر است نه لینک خراب.
# قاعده: URL نامطمئن هرگز وارد نمی‌شود — خالی بهتر از حدس است (لینک جعلی سم است).
APP_LINKS: Dict[str, str] = {
    "aave-v3": "https://app.aave.com",
    "kamino-lend": "https://app.kamino.finance",
    "pendle-v2": "https://app.pendle.finance",
    "spark-savings": "https://app.spark.fi",
    "jupiter-staked-sol": "https://jup.ag/tokens/jupSOL",
    "lido": "https://stake.lido.fi",
    "rocket-pool": "https://stake.rocketpool.net",
    "maple": "https://app.maple.finance",
    "frax": "https://app.frax.finance",
    "compound-v3": "https://app.compound.finance",
    "ether.fi-stake": "https://app.ether.fi",
    "ether.fi-liquid": "https://app.ether.fi",
    "usual-usd0": "https://app.usual.money",
    "usual-eth0": "https://app.usual.money",
    "usual-eur0": "https://app.usual.money",
    "ethena-usde": "https://app.ethena.fi",
    "axis": "https://app.axis.to",
    "tori-finance": "https://app.tori.finance",
}

SCAM_TIPS_BY_LEVEL = {
    "قطعی": [
        "هرگز Seed Phrase / کلید خصوصی را در هیچ سایتی وارد نکن — هیچ پروژه‌ی واقعی آن را نمی‌خواهد.",
        "این الگو با قطعیت کلاهبرداری است؛ حتی ۱ دلار هم واریز نکن و لینک را برای دیگران هم نفرست.",
    ],
    "بالا": [
        "سرمایه‌ای که از دست دادنش برایت محسوس است، وارد این پروژه نکن.",
        "با مبلغ ناچیز تست برداشت کن — اگر برداشتِ اول کار نکرد، کل سپرده از دست رفته است.",
    ],
    "متوسط": [
        "قرارداد و مستندات را خودت بخوان؛ ممیزی عمومی را از سایت شرکت ممیزی چک کن (نه از لینک خود پروژه).",
        "فقط با پولی وارد شو که از دست دادنش آسیب روحی/مالی جدی نزند.",
    ],
    "پایین": [
        "«نسبتاً سالم» یعنی «کم‌خطر»، نه «بی‌خطر» — بازدهی بالاتر همیشه یعنی ریسک بالاتر.",
        "با بخش کوچکی از سرمایه شروع کن و اولین برداشت را هرچه زودتر تست کن.",
    ],
}


def scam_check(answers: Dict[str, str]) -> Dict[str, Any]:
    """محاسبه‌ی خطر از پاسخ‌های بله/خیر/نمی‌دانم — خروجی dict قابل‌رندر.

    قواعد قطعی:
      • درخواست Seed Phrase (سؤال hard) → خطر ۱۰۰ «قطعاً کلاهبرداری»
      • وعده‌ی سود تضمینی → کف خطر ۸۵
    پایه‌ی بی‌طرف ۳۰ است — با پاسخ «نمی‌دانم» کامل، نتیجه «قابل بررسی با احتیاط»
    می‌ماند نه سبزِ گمراه‌کننده؛ هیچ پروژه‌ای «صفر خطر» نیست.
    """
    risk = 30.0
    hard = False
    for q in SCAM_QUESTIONS:
        a = answers.get(q["key"], UNKNOWN)
        if a == UNKNOWN:
            continue
        if q["kind"] == "red" and a == YES:
            if q.get("hard"):
                hard = True
            risk += float(q["weight"])
        elif q["kind"] == "green" and a == YES:
            risk -= float(q["weight"])
    risk = max(0.0, min(100.0, risk))
    if hard:
        risk = 100.0
    if not hard and risk < 85.0 and answers.get("guarantee") == YES:
        risk = 85.0
    if hard:
        level, color, bucket = "قطعاً کلاهبرداری — فرار کن", "#ef4444", "قطعی"
    elif risk >= 75:
        level, color, bucket = "خیلی خطرناک", "#ef4444", "بالا"
    elif risk >= 50:
        level, color, bucket = "مشکوک", "#f59e0b", "متوسط"
    elif risk >= 30:
        level, color, bucket = "قابل بررسی با احتیاط", "#f59e0b", "متوسط"
    else:
        level, color, bucket = "نسبتاً سالم — باز هم با سرمایه‌ی کم شروع کن", "#16a34a", "پایین"
    verdict = {
        "قطعی": "این الگو با قطعیت کلاهبرداری است. هیچ داده یا پولی وارد نکن.",
        "بالا": "نشانه‌های جدی کلاهبرداری دیده می‌شود؛ اگر وارد شوی، پولت را گم‌شده فرض کن.",
        "متوسط": "پروژه در ناحیه‌ی خاکستری است — فقط با احتیاط، تحقیق بیشتر و پول کم.",
        "پایین": "فعلاً نشانه‌ی خطرناکی دیده نمی‌شود — با این حال بازدهی بالاتر یعنی ریسک بالاتر.",
    }[bucket]
    return {
        "risk": int(round(risk)),
        "level": level,
        "color": color,
        "bucket": bucket,
        "verdict": verdict,
        "tips": SCAM_TIPS_BY_LEVEL[bucket],
    }


# --------------------------------------------------------------------------- #
# ۳) تست‌نت/ایردراپ — فهرست دست‌چین (هزینه = صفر، هزینه‌ی واقعی = زمان)        #
# --------------------------------------------------------------------------- #
# منبع: airdropalert.com/testnet-airdrops (بررسی‌شده نوامبر ۲۰۲۶) — فهرست هفتگی
# به‌روز می‌شود؛ هر ورودی فقط پروژه‌ی دارای تست‌نت عمومی است، نه تضمین ایردراپ.
TESTNET_HUNTS: List[Dict[str, Any]] = [
    {"name": "Titan Exchange", "kind": "صرافی پِرپ · تست‌نت عمومی",
     "note": "صرافی مشتقات با دفتر سفارش خصوصی — تجربه‌ی پوزیشن باز/بستن با توکن تست.",
     "added": "2026-10-12", "effort": "روزانه ~۱۵ دقیقه (تخمین)",
     "steps": ["کیف پول EVM آماده کن", "از فاست رسمی تست‌نت توکن بگیر",
               "پوزیشن کوچک باز و بسته کن", "فعالیت را چند روز تکرار کن"],
     "link": AIRDROP_SOURCE_URL},
    {"name": "Polyester", "kind": "DEX چندزنجیره‌ای · L1 سازگار EVM",
     "note": "تست‌نت فعال — سواپ بین‌زنجیره‌ای و نقدینگی با توکن تست.",
     "added": "2026-10-05", "effort": "روزانه ~۱۵ دقیقه (تخمین)",
     "steps": ["به تست‌نت وصل شو", "سواپ انجام بده", "یک پوزیشن LP کوچک باز کن"],
     "link": AIRDROP_SOURCE_URL},
    {"name": "vibe/vibe", "kind": "لانچ‌پد توکن · Robinhood Chain",
     "note": "تست‌نت — ساخت/خرید توکن تستی روی لانچ‌پد.",
     "added": "2026-09-28", "effort": "روزانه ~۱۰ دقیقه (تخمین)",
     "steps": ["کیف پول وصل کن", "توکن تست از فاست", "یک توکن تستی بساز/بخر"],
     "link": AIRDROP_SOURCE_URL},
    {"name": "Kryvora Network", "kind": "L2 اتریوم · شبکه‌ی نودی",
     "note": "تست‌نت با محوریت نود — اجرای نود تستی + تراکنش روزانه.",
     "added": "2026-09-26", "effort": "راه‌اندازی ~۱ ساعت + روزانه ~۱۰ دقیقه (تخمین)",
     "steps": ["نود تستی را طبق داکیومنت بالا بیاور", "تراکنش روزانه بزن", "لاگ‌ها را نگه دار"],
     "link": AIRDROP_SOURCE_URL},
    {"name": "Note Systems", "kind": "ایردراپ $NOTE · اسنکچرد نوتس",
     "note": "کمپین $NOTE اعلام‌شده — تعامل با محصول یادداشت/بازده.",
     "added": "2026-09-25", "effort": "روزانه ~۱۰ دقیقه (تخمین)",
     "steps": ["به اپ وصل شو", "تسک‌های داخل محصول را انجام بده", "رسیدها را ذخیره کن"],
     "link": AIRDROP_SOURCE_URL},
    {"name": "Morfi", "kind": "بازار عقاید · کوئست devnet",
     "note": "devnet کوئست‌محور — پیش‌بینی/معامله‌ی عقاید با توکن تست.",
     "added": "2026-09-22", "effort": "روزانه ~۱۰ دقیقه (تخمین)",
     "steps": ["حساب بساز", "کوئست‌های devnet را کامل کن", "پوزیشن تستی باز کن"],
     "link": AIRDROP_SOURCE_URL},
    {"name": "DOHM Finance", "kind": "دی‌فای روی بیت‌کوین · Alkanes",
     "note": "ایردراپ $DOHM اعلام‌شده — تعامل با پروتکل دی‌فای بیت‌کوینی.",
     "added": "2026-09-21", "effort": "روزانه ~۱۵ دقیقه (تخمین)",
     "steps": ["کیف پول سازگار آماده کن", "تسک‌های تستی را انجام بده", "اسناد را نگه دار"],
     "link": AIRDROP_SOURCE_URL},
]

SYBIL_RULES = [
    "برای هر پروژه از یک کیف پول تازه استفاده کن — کیف پولِ اصلی‌ات را هرگز برای تست‌نت‌ها استفاده نکن.",
    "توکن تست فقط از فاستِ رسمی خود پروژه بگیر — فاست تقلبی رایج‌ترین راه تخلیه‌ی کیف پول است.",
    "الگوی رفتاری انسانی داشته باش: ساعت‌های نامنظم، مبلغ‌های نامنظم — نه تراکنش‌های ربات‌وار همگانی.",
    "از اسکریپت/بات همگانی استفاده نکن — سیستم‌های ضدسفل (Sybil) کیف پول‌های هم‌الگو را یکجا حذف می‌کنند.",
    "هیچ‌وقت برای «تسک ایردراپ» پول واریز نکن — تست‌نت واقعی هزینه‌ی پولی ندارد؛ فقط گاهی گسِ ارزان.",
    "ایردراپ تضمین‌شده وجود ندارد — هر ورودی یک بلیت لاتاری است؛ انتظارِ صفر داشته باش، سورپرایز خوشایند.",
]

STARTER_GUIDE = [
    "۱) یک کیف پول تازه (Rabby/MetaMask) مخصوص تست‌نت‌ها بساز و Seed آن را فقط روی کاغذ، آفلاین نگه دار.",
    "۲) از فاست رسمی پروژه (لینک داخل داکیومنت رسمی) توکن تست بگیر.",
    "۳) روزانه چند دقیقه با محصول تعامل واقعی کن: سواپ، نقدینگی، پوزیشن — نه فقط لاگین.",
    "۴) فعالیتت را (تاریخ، مبلغ، لینک تراکنش) یادداشت کن — موقع توزیع ایردراپ به کارت می‌آید.",
    "۵) روی هیچ پروژه‌ای بیش از چند ساعت در هفته نگذار — این‌ها لاتاری‌اند، نه شغل.",
]

DISCLAIMER = ("این بخش پژوهش و آموزش است، نه توصیه‌ی سرمایه‌گذاری. «رایگان» فقط یعنی بدون سرمایه‌ی "
              "اولیه — نه بدون ریسک و نه سود تضمینی. هرگز Seed Phrase را وارد هیچ سایتی نکن.")

DISCLAIMER_EN = ("This section is research & education, not investment advice. 'Free' only means no "
                 "upfront capital — not risk-free and not guaranteed profit. Never enter your seed "
                 "phrase into any website.")

SYBIL_RULES_EN = [
    "Use a fresh wallet per project — never your main wallet for testnets.",
    "Get test tokens only from the project's official faucet — fake faucets are the most common wallet drainer.",
    "Act human: irregular hours and amounts — not robot-like identical transactions.",
    "No mass scripts/bots — anti-Sybil systems wipe look-alike wallets together.",
    "Never deposit money for an 'airdrop task' — a real testnet costs no money, only occasional cheap gas.",
    "There is no guaranteed airdrop — every entry is a lottery ticket; expect zero, enjoy surprises.",
]

STARTER_GUIDE_EN = [
    "1) Create a fresh wallet (Rabby/MetaMask) dedicated to testnets; keep its seed offline, on paper only.",
    "2) Get test tokens from the project's official faucet (the link inside its official docs).",
    "3) Interact with the product for a few minutes daily: swaps, liquidity, positions — not just logins.",
    "4) Log your activity (date, amount, tx link) — it pays off at the airdrop distribution.",
    "5) Never spend more than a few hours a week on any project — these are lottery tickets, not a job.",
]


def testnet_rows() -> List[Dict[str, str]]:
    """ردیف‌های آماده‌ی جدول صفحه — از TESTNET_HUNTS با فیلدهای فارسی."""
    return [{"نام": h["name"], "نوع": h["kind"], "یادداشت": h["note"],
             "هزینه": "🟢 رایگان — فقط زمان", "زمان لازم": h["effort"],
             "ثبت‌شده": h["added"], "منبع": h["link"]} for h in TESTNET_HUNTS]


# --------------------------------------------------------------------------- #
# ۴) دسته‌بندی هزینه + ماینینگ — «رایگان» یا «پولی»، بدون خاکستری             #
# --------------------------------------------------------------------------- #
# دو برچسبِ ساده که کنار هر فرصت تکرار می‌شود تا کاربر همان نگاهِ اول بداند
# از او چه می‌خواهند: پول یا زمان. به درخواست کاربر: «دسته‌بندی کن: فارمینگ،
# ماینینگ، رایگان، پولی — گیج نشن و دنبالش نگردن».
COST_FREE = "🟢 رایگان"
COST_PAID = "🔴 پولی"

# «ماینینگ» سه دنیای کاملاً متفاوت با یک نام دارد؛ این‌ها را از هم جدا نکنیم،
# کاربر اپ تپ‌کردن را با آسیک و قرارداد ابری اشتباه می‌گیرد — و دقیقاً همان‌جا
# پولش را از دست می‌دهد. هر کارت: توضیح صادقانه + حکم نهایی + قواعد.
MINING_KINDS: List[Dict[str, Any]] = [
    {
        "key": "mobile",
        "icon": "📱",
        "title": "ماینینگ موبایلی (اپ تپ‌کردن)",
        "title_en": "Mobile mining (tap apps)",
        "cost": COST_FREE,
        "cost_en": "🟢 Free",
        "color": "#16a34a",
        "free": True,
        "what": ("اپ‌هایی که می‌گویند «روی گوشی ماین کن» — واقعیت: گوشی توانِ ماین‌کردن بیت‌کوین را "
                 "ندارد؛ این اپ‌ها در واقع به‌ازای توجه و دعوت دوستان، به تو «امتیاز/توکنِ آینده» "
                 "بدهکار می‌شوند. پولِ اولیه نمی‌خواهد، اما تا وقتی توکن واقعاً وارد صرافی معتبر شود، "
                 "ارزشش صفر فرض کن — بلیت لاتاری است، نه درآمد."),
        "what_en": ("Apps that say 'mine on your phone' — reality: a phone cannot mine Bitcoin; these "
                    "apps owe you 'points/future tokens' for your attention and referrals. No upfront "
                    "money, but treat the value as zero until the token actually lists on a real "
                    "exchange — a lottery ticket, not income."),
        "verdict": "قاعده: رایگان تا آخر — اگر حتی یک ریال خواست، ببند و برو.",
        "verdict_en": "Rule: free all the way — the moment it asks for money, close it and leave.",
        "rules": [
            "برای «فعال‌سازی برداشت» یا «ارتقای نرخ ماین» هرگز پول پرداخت نکن — ماینینگ موبایلی واقعی رایگان است؛ جایی که پول خواست یعنی کلاهبرداری.",
            "Seed Phrase یا کلید خصوصی در هیچ اپی وارد نکن — هیچ اپ واقعی آن را نمی‌خواهد.",
            "«دعوت کن، نرخ ماین ۲ برابر» یعنی سودِ اصلی از دعوت است (هرمی) — نه از محصول.",
            "اپ را فقط از منبع رسمی خود پروژه (سایت/شبکه‌ی تأییدشده) نصب کن — اپ‌های تقلبیِ هم‌نام در استورها زیادند.",
            "زمانت را بسنج: بیشتر از چند دقیقه در روز روی اپ‌هایی با آینده‌ی نامعلوم نگذار.",
        ],
        "rules_en": [
            "Never pay for 'withdrawal activation' or 'mining-rate upgrade' — real mobile mining is free; anything asking money is a scam.",
            "Never enter a seed phrase or private key into any app — no real app needs it.",
            "'Invite friends, double your rate' means income from recruiting (pyramid), not the product.",
            "Install the app only from the project's own verified source — copycat fake apps crowd the stores.",
            "Watch your time: no more than a few minutes a day on apps with unknown futures.",
        ],
    },
    {
        "key": "hardware",
        "icon": "🏭",
        "title": "ماینینگ هاردواری (دستگاه آسیک)",
        "title_en": "Hardware mining (ASIC)",
        "cost": COST_PAID,
        "cost_en": "🔴 Paid",
        "color": "#ef4444",
        "free": False,
        "what": ("ماینینگ واقعی یعنی دستگاه تخصصی (ASIC) + برق ارزان + صدا و گرمای دائم. صداقتِ کامل: "
                 "با برقِ گران، درآمدِ ماین معمولاً از هزینه‌ی برق کمتر می‌شود — یعنی ضررِ ماهانه؛ و "
                 "دستگاه هر سال کهنه‌تر و کم‌بازده‌تر می‌شود. برای بیشتر افراد عادی، «خرید مستقیم همان "
                 "سکه» ساده‌تر و کم‌دردسرتر است."),
        "what_en": ("Real mining means a dedicated ASIC machine + cheap power + constant noise and heat. "
                    "Full honesty: with expensive electricity, mining income is usually below the power "
                    "bill — a monthly loss — and hardware depreciates yearly. For most people, just "
                    "buying the coin directly is simpler."),
        "verdict": "قاعده: اول حساب‌کتاب، بعد خرید — بدون برق ارزان شروع نکن.",
        "verdict_en": "Rule: math first, then buy — never start without cheap power.",
        "rules": [
            "قبل از هر خریدی، درآمد روزانه‌ی دستگاه را با قیمت برقِ واقعی خودت حساب کن؛ اگر برق بیشتر از درآمد شد، یعنی ضرر خالص.",
            "در ایران ماینینگ بدون مجوز رسمی غیرقانونی است — جریمه و ضبط دستگاه در میان است؛ فقط با مجوز رسمی و تعرفه‌ی اعلام‌شده.",
            "قیمت دستگاه در بازار دست‌دوم سقوط می‌کند — نقدشوندگیِ آسیک کهنه پایین است.",
            "«دستگاه به‌زودی هزینه‌اش را درمی‌آورد» را باور نکن — سهم تو از پاداش شبکه هر روز کم می‌شود.",
        ],
        "rules_en": [
            "Before buying anything, compute the machine's daily income against your real power price; if power exceeds income, it is a net loss.",
            "In Iran, unlicensed mining is illegal — fines and confiscation; only with an official license and its declared tariff.",
            "Used ASIC prices collapse — resale liquidity is poor.",
            "Don't believe 'it pays for itself soon' — your share of network rewards shrinks daily.",
        ],
    },
    {
        "key": "cloud",
        "icon": "☁️",
        "title": "ماینینگ ابری (فروش هشریت)",
        "title_en": "Cloud mining (hashrate resale)",
        "cost": "🔴 پولی و پرخطر",
        "cost_en": "🔴 Paid & high-risk",
        "color": "#ef4444",
        "free": False,
        "what": ("سایت‌هایی که «هشریت» می‌فروشند و می‌گویند سهمِ ماین تو را روزانه می‌ریزند. صداقتِ "
                 "تلخ: اکثریتِ قاطعِ سایت‌های ماینینگ ابریِ تبلیغ‌شده پانزی‌اند — سودِ اعضای بعدی، "
                 "خونِ توست. حتی قراردادهای شرکت‌های شناخته‌شده هم معمولاً از «همین پول را سکه بخر و "
                 "نگه دار» بازدهی کمتری دارند."),
        "what_en": ("Sites selling 'hashrate' that promise daily mining payouts. Bitter honesty: the "
                    "overwhelming majority of advertised cloud-mining sites are Ponzi schemes — even "
                    "contracts from established players usually underperform simply buying the coin."),
        "verdict": "قاعده: اگر بیت‌کوین را باور داری، مستقیم سکه بخر — قرارداد ابری نخر.",
        "verdict_en": "Rule: if you believe in the coin, buy it directly — skip cloud contracts.",
        "rules": [
            "سود روزانه‌ی ثابت («۱.۵٪ در روز») اعلام کنند → برو؛ هیچ ماینینگ واقعی سود ثابت نمی‌دهد.",
            "«ماینینگ ابری رایگان» + کارمزد فعال‌سازی یا برداشت → طعمه است؛ برداشت بلاک می‌شود تا سپرده‌ی بیشتر بریزی.",
            "سودِ دعوتِ دوست بیشتر از سودِ خود ماین باشد → هرمی است.",
            "آدرس دفتر، مجوز یا گزارش مستقل از تجهیزات واقعی نداشته باشند → دروغِ پیش‌فرض است.",
            "هر پروژه‌ای را خواستی امتحان کنی، اول تب «ضدکلاهبرداری» را کامل کن — همیشه.",
        ],
        "rules_en": [
            "Fixed daily profit ('1.5% per day') → walk away; no real mining yields fixed profit.",
            "'Free cloud mining' + activation/withdrawal fee → bait; withdrawals block until you deposit more.",
            "Referral income larger than mining income → pyramid.",
            "No verifiable office, license, or independent proof of real hardware → lie by default.",
            "Before trying any of them, complete the Anti-scam tab first — always.",
        ],
    },
]
