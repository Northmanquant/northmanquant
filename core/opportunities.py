# -*- coding: utf-8 -*-
"""core/opportunities.py — فرصت‌های رایگان + آزمایشگر ضدکلاهبرداری
==================================================================
فلسفه‌ی این بخش: **داده‌ی واقعی، نه وعده.** قانون طلاییِ نوشته‌شده در صفحه:
«رایگان + سود خوب + مطمئن» با هم وجود ندارند؛ سود واقعی همیشه سرمایه، زمان
یا مهارت می‌گیرد.

دو زیربخش:
  ۱) 🎁 رایگان — تست‌نت/ایردراپ: فهرست دست‌چینِ هزینه‌ی صفر (فقط زمان) +
     قواعد ضدسفل و راهنمای شروع از صفر.
  ۲) 🛡 آزمایشگر ضدکلاهبرداری — چک‌لیست وزن‌دار ۱۰ سؤالی با قواعد قطعی
     (درخواست Seed Phrase = ۱۰۰ خطر، بی‌چون‌وچرا) + ابزارهای راستی‌آزمایی.

برچسب هزینه (COST_FREE/COST_PAID) قراردادِ مشترکِ نشان‌هاست. طبق تصمیمِ صاحبِ
پروژه، بخش‌های بیرونیِ پولی و استخرهای بازدهِ DefiLlama کامل حذف شده‌اند —
تمرکز حالا روی فرصت‌های بی‌هزینه و روی کیفیتِ خودِ پروژه است (کارگاهِ
ایجنت‌ها در core/scouts.py).

تمام داده‌ها آفلاین و دست‌چین‌اند؛ هیچ درخواست شبکه‌ای در این ماژول نیست.
"""
from __future__ import annotations

from typing import Any, Dict, List

AIRDROP_SOURCE_URL = "https://airdropalert.com/testnet-airdrops"

UNKNOWN = "نمی‌دانم"
YES = "بله"
NO = "خیر"

# --------------------------------------------------------------------------- #
# ۱) آزمایشگر ضدکلاهبرداری                                                    #
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
# ۲) تست‌نت/ایردراپ — فهرست دست‌چین (هزینه = صفر، هزینه‌ی واقعی = زمان)        #
# --------------------------------------------------------------------------- #
# منبع: airdropalert.com/testnet-airdrops (بررسی‌شده نوامبر ۲۰۲۶) — فهرست هفتگی
# به‌روز می‌شود؛ هر ورودی فقط پروژه‌ی دارای تست‌نت عمومی است، نه تضمین ایردراپ.
TESTNET_HUNTS: List[Dict[str, Any]] = [
    {"name": "Titan Exchange", "kind": "صرافی پِرپ · تست‌نت عمومی",
     "note": "صرافی مشتقات با دفتر سفارش خصوصی — تجربه‌ی پوزیشن باز/بستن با توکن تست.",
     "added": "2026-10-12", "effort": "روزانه ~۱۵ دقیقه (تخمین)", "minutes": 15,
     "steps": ["کیف پول EVM آماده کن", "از فاست رسمی تست‌نت توکن بگیر",
               "پوزیشن کوچک باز و بسته کن", "فعالیت را چند روز تکرار کن"],
     "link": AIRDROP_SOURCE_URL},
    {"name": "Polyester", "kind": "DEX چندزنجیره‌ای · L1 سازگار EVM",
     "note": "تست‌نت فعال — سواپ بین‌زنجیره‌ای و نقدینگی با توکن تست.",
     "added": "2026-10-05", "effort": "روزانه ~۱۵ دقیقه (تخمین)", "minutes": 15,
     "steps": ["به تست‌نت وصل شو", "سواپ انجام بده", "یک پوزیشن LP کوچک باز کن"],
     "link": AIRDROP_SOURCE_URL},
    {"name": "vibe/vibe", "kind": "لانچ‌پد توکن · Robinhood Chain",
     "note": "تست‌نت — ساخت/خرید توکن تستی روی لانچ‌پد.",
     "added": "2026-09-28", "effort": "روزانه ~۱۰ دقیقه (تخمین)", "minutes": 10,
     "steps": ["کیف پول وصل کن", "توکن تست از فاست", "یک توکن تستی بساز/بخر"],
     "link": AIRDROP_SOURCE_URL},
    {"name": "Kryvora Network", "kind": "L2 اتریوم · شبکه‌ی نودی",
     "note": "تست‌نت با محوریت نود — اجرای نود تستی + تراکنش روزانه.",
     "added": "2026-09-26", "effort": "راه‌اندازی ~۱ ساعت + روزانه ~۱۰ دقیقه (تخمین)", "minutes": 10,
     "steps": ["نود تستی را طبق داکیومنت بالا بیاور", "تراکنش روزانه بزن", "لاگ‌ها را نگه دار"],
     "link": AIRDROP_SOURCE_URL},
    {"name": "Note Systems", "kind": "ایردراپ $NOTE · اسنکچرد نوتس",
     "note": "کمپین $NOTE اعلام‌شده — تعامل با محصول یادداشت/بازده.",
     "added": "2026-09-25", "effort": "روزانه ~۱۰ دقیقه (تخمین)", "minutes": 10,
     "steps": ["به اپ وصل شو", "تسک‌های داخل محصول را انجام بده", "رسیدها را ذخیره کن"],
     "link": AIRDROP_SOURCE_URL},
    {"name": "Morfi", "kind": "بازار عقاید · کوئست devnet",
     "note": "devnet کوئست‌محور — پیش‌بینی/معامله‌ی عقاید با توکن تست.",
     "added": "2026-09-22", "effort": "روزانه ~۱۰ دقیقه (تخمین)", "minutes": 10,
     "steps": ["حساب بساز", "کوئست‌های devnet را کامل کن", "پوزیشن تستی باز کن"],
     "link": AIRDROP_SOURCE_URL},
    {"name": "DOHM Finance", "kind": "دی‌فای روی بیت‌کوین · Alkanes",
     "note": "ایردراپ $DOHM اعلام‌شده — تعامل با پروتکل دی‌فای بیت‌کوینی.",
     "added": "2026-09-21", "effort": "روزانه ~۱۵ دقیقه (تخمین)", "minutes": 15,
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
# ۳) برچسب هزینه — «رایگان» یا «پولی»، بدون خاکستری                           #
# --------------------------------------------------------------------------- #
# دو برچسبِ ساده که کنار هر فرصت تکرار می‌شود تا کاربر همان نگاهِ اول بداند
# از او چه می‌خواهند: پول یا زمان. قراردادِ مشترکِ core/scouts.py و صفحه.
COST_FREE = "🟢 رایگان"
COST_PAID = "🔴 پولی"
