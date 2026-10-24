# -*- coding: utf-8 -*-
"""
core/i18n.py — سیستم چندزبانه (فارسی / English) برای کل اپ Streamlit
=====================================================================
v5 — «ترجمه‌ی عمیق»: با تعویض زبان، کل منو، سایدبار، داشبورد، صفحات،
جدول‌ها، دکمه‌ها، پیام‌ها و چیدمان (RTL/LTR) عوض می‌شود.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

import streamlit as st

LANG_KEY = "app_lang"
DEFAULT_LANG = "fa"

LANG_LABELS: Dict[str, str] = {"fa": "فارسی", "en": "English"}

# ---------------------------------------------------------------------------
# دیکشنری کلیدی (برای t()) — سازگار با نسخه‌های قبلی
# ---------------------------------------------------------------------------
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "fa": {
        "app_title": "تحلیل تکنیکال چندسطحی",
        "settings": "پنل تنظیمات",
        "language": "زبان",
        "symbol": "نماد",
        "timeframe": "تایم‌فریم",
        "analyze": "تحلیل کن",
        "refresh": "بروزرسانی",
        "save": "ذخیره",
        "cancel": "انصراف",
        "search": "جستجو",
        "loading": "در حال دریافت داده...",
        "data_error": "خطا در دریافت داده. لطفاً دوباره تلاش کنید.",
        "disclaimer": "این محتوا توصیه سرمایه‌گذاری نیست.",
        "sec_community": "برد تحلیل‌های اجتماعی",
        "buy": "خرید",
        "sell": "فروش",
        "neutral": "بی‌طرف",
        "entry": "نقطه ورود",
        "stop_loss": "حد ضرر",
        "take_profit": "حد سود",
        "risk_reward": "ریسک به ریوارد",
        "confidence": "درجه اطمینان",
        "author_name": "نام شما",
        "your_analysis": "تحلیل شما",
        "submit": "ثبت تحلیل",
        "no_records": "هنوز تحلیلی ثبت نشده است. اولین نفر باشید!",
        "posted_ok": "تحلیل شما با موفقیت ثبت شد.",
        "backend_ok": "برد مشترک: Supabase (پایدار)",
        "backend_local": "برد مشترک: فایل محلی (موقتی)",
        "backend_warn": "هشدار",
    },
    "en": {
        "app_title": "Multi-Level Technical Analysis",
        "settings": "Settings Panel",
        "language": "Language",
        "symbol": "Symbol",
        "timeframe": "Timeframe",
        "analyze": "Analyze",
        "refresh": "Refresh",
        "save": "Save",
        "cancel": "Cancel",
        "search": "Search",
        "loading": "Fetching data...",
        "data_error": "Data fetch failed. Please try again.",
        "disclaimer": "This content is not investment advice.",
        "sec_community": "Community Analysis Board",
        "buy": "Buy",
        "sell": "Sell",
        "neutral": "Neutral",
        "entry": "Entry",
        "stop_loss": "Stop Loss",
        "take_profit": "Take Profit",
        "risk_reward": "Risk-Reward",
        "confidence": "Confidence",
        "author_name": "Your name",
        "your_analysis": "Your analysis",
        "submit": "Post analysis",
        "no_records": "No analyses yet. Be the first!",
        "posted_ok": "Your analysis was posted successfully.",
        "backend_ok": "Community board: Supabase (stable)",
        "backend_local": "Community board: local file (temporary)",
        "backend_warn": "Warning",
    },
}


def get_lang() -> str:
    lang = st.session_state.get(LANG_KEY, DEFAULT_LANG)
    return lang if lang in TRANSLATIONS else DEFAULT_LANG


def set_lang(lang: str) -> None:
    if lang in TRANSLATIONS:
        st.session_state[LANG_KEY] = lang


def is_rtl() -> bool:
    return get_lang() == "fa"


def t(key: str, default: Optional[str] = None) -> str:
    """ترجمه از دیکشنری بر اساس کلید."""
    lang = get_lang()
    table = TRANSLATIONS[lang]
    if key in table:
        return table[key]
    if default is not None:
        return default
    return TRANSLATIONS[DEFAULT_LANG].get(key, key)


def tr(fa_text: str, en_text: Optional[str] = None) -> str:
    """ترجمه درجا: tr("ثبت تحلیل", "Post analysis")."""
    if get_lang() == "en":
        return en_text if en_text not in (None, "") else fa_text
    return fa_text


# ===========================================================================
# موتور ترجمه‌ی عمیق — هر متنی که به st.* داده شود، جمله‌به‌جمله به EN
# تبدیل می‌شود (طولانی‌ترین عبارت اول، تا کلمات داخل هم خراب نشوند).
# ===========================================================================
_FA_ANY = re.compile(r"[\u0600-\u06FF\u200c]")
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# --- ۱) جمله‌های کامل و برچسب‌های دقیق UI --------------------------------
_EXACT: list[tuple[str, str]] = [
    # --- سایدبار و تنظیمات اصلی ---
    ("⚙️ تنظیمات", "⚙️ Settings"),
    ("بخش‌ها", "Sections"),
    ("🏦 بازار و نماد", "🏦 Market & Symbol"),
    ("🎨 شخصی‌سازی ظاهر", "🎨 Appearance"),
    ("تم رنگی", "Color theme"),
    ("🌌 شب کهکشانی", "🌌 Galaxy Night"),
    ("🌊 اقیانوس عمیق", "🌊 Deep Ocean"),
    ("🌿 جنگل تاریک", "🌿 Dark Forest"),
    ("🔥 غروب آتشین", "🔥 Fire Sunset"),
    ("👑 سلطنتی بنفش", "👑 Royal Purple"),
    ("☀️ روشن مینیمال", "☀️ Light Minimal"),
    ("🖤 تک‌رنگ تیره", "🖤 Dark Mono"),
    ("لینک تصویر پس‌زمینه (اختیاری)", "Background image URL (optional)"),
    ("آدرس یک عکس بگذار تا پس‌زمینه‌ی دلخواهت شود.", "Paste an image URL to set your own background."),
    ("**📈 تنظیمات چارت**", "**📈 Chart Settings**"),
    ("تعداد کندل روی چارت (فشرده/باز)", "Candles on chart (compact/wide)"),
    ("کمتر = کندل‌ها بازتر و درشت‌تر · بیشتر = فشرده‌تر", "Lower = wider candles · Higher = more compressed"),
    ("🟪 نمایش نواحی FVG / BVG روی چارت", "🟪 Show FVG / BVG zones on chart"),
    ("🔴 حالت زنده (قیمت لحظه‌ای)", "🔴 Live mode (real-time price)"),
    ("نماد را مثل BTC-USDT بنویس؛ اگر صرافی انتخابی در منطقه‌ات مسدود است، KuCoin یا OKX یا Lighter را انتخاب کن.",
     "Write the symbol like BTC-USDT; if the exchange is blocked in your region, pick KuCoin, OKX or Lighter."),
    ("نماد را مثل BTC یا ETH بنویس؛ اگر صرافی مسدود است، OKX یا KuCoin یا Lighter را امتحان کن.",
     "Write a symbol like BTC or ETH; if the exchange is blocked, try OKX, KuCoin or Lighter."),
    # --- تحلیل زنده ---
    ("همگرایی اندیکاتورها", "Indicator Confluence"),
    ("سیگنال همگرایی", "Confluence Signal"),
    ("خرید قوی", "Strong Buy"),
    ("فروش قوی", "Strong Sell"),
    ("خنثی ⚪", "Neutral ⚪"),
    ("لانگ 🟢", "Long 🟢"),
    ("شورت 🔴", "Short 🔴"),
    ("خارج از بازار", "Flat — no position"),
    ("تغییر ۲۴س ", "24h change "),
    (" · داده از ", " · data from "),
    ("LIVE · زنده", "LIVE"),
    ("bid/ask در دسترس نیست", "bid/ask not available"),
    ("امتیاز: —", "Score: —"),
    ("تا بستن کندل", "until candle close"),
    ("◈ پوسته مدل‌ها (Neural Shell) — زنده · با FVG / BVG", "◈ Neural Shell — live · with FVG / BVG"),
    ("◈ دفتر ایجنت‌ها (The Agents) — بک‌تست زنده", "◈ The Agents — live backtest"),
    ("🎯 طرح معامله — ستاپ اعتبارسنجی‌شده (walk-forward روی همین نماد)",
     "🎯 Trade Plan — validated setup (walk-forward on this symbol)"),
    ("📐 اعتبار ستاپ‌ها روی همین نماد/تایم‌فریم (تست walk-forward، بدون نگاه به آینده)",
     "📐 Setup validation on this symbol/timeframe (walk-forward, no lookahead)"),
    ("هر سیگنال گذشته‌ی همین نماد شبیه‌سازی شده: آیا TP1 (1R) قبل از حد ضرر لمس شد؟ انتظار ریاضی با هدف 2R. فقط ستاپی که این‌جا «قابل اعتماد» است اجازه‌ی معامله دارد. همگرایی اندیکاتورها فقط زمینه است و جهت را تعیین نمی‌کند.",
     "Every past signal of this symbol was simulated: was TP1 (1R) hit before the stop-loss? Expectancy targets 2R. Only a setup that is «reliable» here is allowed to trade. Indicator confluence is context only — it does not set the direction."),
    ("🧾 مدارک تحلیل — کندل، ساختار، نقدینگی، جریان پول، FVG/BVG، سطوح",
     "🧾 Analysis Evidence — candles, structure, liquidity, money flow, FVG/BVG, levels"),
    ("🟪 نواحی FVG / BVG (عدم تعادل پر نشده)", "🟪 FVG / BVG zones (unfilled imbalance)"),
    ("FVG یا BVG فعالی در این بازه پیدا نشد.", "No active FVG/BVG found in this range."),
    ("FVG صعودی = حمایت/محل ورود لانگ · FVG نزولی = مقاومت/محل ورود شورت · BVG (BPR) = هم‌پوشانی FVG صعودی و نزولی — ناحیه‌ی بسیار قوی.",
     "Bullish FVG = support / long entry · Bearish FVG = resistance / short entry · BVG (BPR) = overlap of both — a very strong zone."),
    ("**اجزای همگرایی**", "**Confluence components**"),
    ("🧱 حمایت و مقاومت (سوئینگ)", "🧱 Support & Resistance (swing)"),
    ("🧱 حمایت و مقاومت", "🧱 Support & Resistance"),
    ("سطح معناداری پیدا نشد.", "No significant level found."),
    ("💾 ذخیره سطوح (CSV)", "💾 Save levels (CSV)"),
    ("📜 رویدادهای ورود/خروج همگرایی", "📜 Confluence entry/exit events"),
    ("در این بازه رویدادی ثبت نشده است.", "No events recorded in this range."),
    ("📈 روند امتیاز همگرایی (۱۲۰ کندل اخیر)", "📈 Confluence score trend (last 120 candles)"),
    ("داده: API عمومی صرافی (کش ۶۰ ثانیه). این ابزار توصیه‌ی سرمایه‌گذاری نیست.",
     "Data: public exchange API (60s cache). This tool is not investment advice."),
    ("◈ ماتریس لبه (Edge Matrix) — همبستگی سیگنال با بازده بعدی",
     "◈ Edge Matrix — signal vs next-bar return"),
    ("هر نقطه یک کندل است: محور افقی = امتیاز همگرایی، محور عمودی = بازده کندل بعدی. خط نارنجی رگرسیون؛ شیب و همبستگی مثبت یعنی سیگنال واقعاً پیش‌روِ سود بوده است.",
     "Each point is one candle: x = confluence score, y = next-candle return. Orange line = regression; positive slope/correlation means the signal genuinely led to profit."),
]

_EXACT += [
    # --- فرصت‌های سودده ---
    ("💎 فرصت‌های سودده — اسکن زنده‌ی بازار (خودکار)", "💎 Profit Opportunities — live market scan (auto)"),
    ("تعداد فرصت‌ها", "Number of opportunities"),
    ("حداقل قدرت سیگنال", "Min signal strength"),
    ("رفرش قیمت (ثانیه)", "Price refresh (sec)"),
    ("اسکن مجدد تحلیل (ثانیه)", "Re-scan interval (sec)"),
    ("🔍 اسکن فوری", "🔍 Quick scan"),
    ("🔍 در حال اسکن موازی بازار…", "🔍 Scanning market in parallel…"),
    ("فعلاً ستاپ قوی‌ای پیدا نشد. حداقل قدرت سیگنال را کم کن یا تایم‌فریم دیگری امتحان کن. (اسکن بعدی خودکار انجام می‌شود)",
     "No strong setup right now. Lower the min signal strength or try another timeframe. (Next scan runs automatically)"),
    ("💾 ذخیره فرصت‌ها (CSV)", "💾 Save opportunities (CSV)"),
    ("این فهرست صرفاً تحلیلی است و توصیه‌ی سرمایه‌گذاری نیست. حتماً مدیریت ریسک را رعایت کن.",
     "This list is analytical only — not investment advice. Always apply risk management."),
    ("آخرین اسکن تحلیل: ", "Last analysis scan: "),
    ("اسکن بعدی ≈ ", "Next scan ≈ "),
    # --- برترین‌ها و اخبار ---
    ("🚀 بیشترین سود ۲۴س", "🚀 Top Gainers 24h"),
    ("🩸 بیشترین ریزش ۲۴س", "🩸 Top Losers 24h"),
    ("💧 بیشترین حجم", "💧 Top Volume"),
    ("پوشش خبری زنده — کریپتو، فارکس، بازار آمریکا، اقتصاد جهان و جنگ/ژئوپلیتیک. روی هر خبر بزن تا **متن کامل همین‌جا** باز شود.",
     "Live news coverage — crypto, forex, US market, world economy & geopolitics. Click any headline to open the **full text** here."),
    ("دسته‌بندی اخبار", "News category"),
    ("در حال دریافت اخبار…", "Fetching news…"),
    ("خبری دریافت نشد. چند لحظه بعد دوباره امتحان کن (فیدها گاهی با تأخیر کش می‌شوند).",
     "No news fetched. Try again in a moment (feeds are sometimes cached with delay)."),
    ("متن کامل این خبر در فید موجود نیست — از «منبع اصلی» بخوان.",
     "Full text of this item is not in the feed — read it from the «original source»."),
    # --- بخش تحلیل‌ها ---
    ("🧑‍💻 تحلیل‌ها — ثبت تحلیل شخصی · تصویر تحلیل · تحلیل‌های کاربران",
     "🧑‍💻 Analyses — Post · Chart Image · Community"),
    ("✍️ ثبت تحلیل شخصی", "✍️ Post Your Analysis"),
    ("🖼️ تصویر تحلیل", "🖼️ Chart Image"),
    ("👥 تحلیل‌های کاربران", "👥 Community Analyses"),
    ("تحلیل حرفه‌ای‌ات را با جزئیات کامل ثبت کن تا در تب «👥 تحلیل‌های کاربران» برای همه دیده شود.",
     "Post your full analysis so everyone sees it in the «👥 Community Analyses» tab."),
    ("نام یا نام مستعار *", "Name or alias *"),
    ("نماد ارز *", "Symbol *"),
    ("مثل BTC-USDT، ETH، SOL", "e.g. BTC-USDT, ETH, SOL"),
    ("جهت *", "Side *"),
    ("قیمت ورود", "Entry price"),
    ("حد ضرر (SL)", "Stop loss (SL)"),
    ("هدف ۱ (TP1)", "Target 1 (TP1)"),
    ("هدف ۲ (TP2)", "Target 2 (TP2)"),
    ("هدف ۳ (TP3)", "Target 3 (TP3)"),
    ("اطمینان ٪", "Confidence %"),
    ("شرح تحلیل و دلیل *", "Analysis description & rationale *"),
    ("دلیل ورود، ستاپ تکنیکال، سطوح کلیدی، مدیریت ریسک …", "Entry reason, technical setup, key levels, risk management …"),
    ("📷 عکس چارت/تحلیل (اختیاری)", "📷 Chart/analysis image (optional)"),
    ("می‌توانی اسکرین‌شات چارت یا تحلیلت را هم پیوست کنی.", "You can also attach a screenshot of your chart/analysis."),
    ("📨 ثبت و اشتراک‌گذاری تحلیل", "📨 Post & share analysis"),
    ("تحلیلت ثبت شد ✓ — در تب «👥 تحلیل‌های کاربران» ببین.", "Posted ✓ — see the «👥 Community Analyses» tab."),
    ("فیلدهای ستاره‌دار (نام، نماد، شرح تحلیل) را پر کن.", "Fill the starred fields (name, symbol, description)."),
    ("نماد برای تصویر", "Symbol for image"),
    ("مثل BTC، ETH، SOL … · برای Lighter فقط نماد پایه", "e.g. BTC, ETH, SOL … · for Lighter use the base symbol only"),
    ("🖼️ ساخت تصویر تحلیل", "🖼️ Build chart image"),
    ("⬇️ دانلود تصویر (PNG)", "⬇️ Download image (PNG)"),
    ("برچسب‌های روی تصویر انگلیسی هستند (ENTRY/STOP/TP/S/R) تا در همه‌ی سیستم‌ها درست دیده شوند. این ابزار توصیه‌ی سرمایه‌گذاری نیست.",
     "Image labels are English (ENTRY/STOP/TP/S/R) so they render correctly everywhere. Not investment advice."),
    ("یک نماد وارد کن و دکمه‌ی «ساخت تصویر تحلیل» را بزن.", "Enter a symbol and press «🖼️ Build chart image»."),
    ("📨 ارسال این تحلیل تصویری به «👥 تحلیل‌های کاربران»", "📨 Send this image analysis to «👥 Community Analyses»"),
    ("ارسال شد ✓ — تب «👥 تحلیل‌های کاربران» را ببین.", "Sent ✓ — check the «👥 Community Analyses» tab."),
    ("تحلیل‌هایی که کاربران ثبت کرده‌اند. برای ثبت تحلیل خودت → تب «✍️ ثبت تحلیل شخصی».",
     "Analyses posted by the community. To post yours → the «✍️ Post Your Analysis» tab."),
    ("🔄 بازخوانی", "🔄 Refresh"),
    ("هنوز تحلیلی ثبت نشده. اولین نفر باش! (تب → ✍️ ثبت تحلیل شخصی)",
     "No analyses yet. Be the first! (tab → ✍️ Post Your Analysis)"),
    ("فیلتر نماد", "Filter symbol"),
    ("فیلتر جهت", "Filter side"),
    ("همه", "All"),
    ("⚠️ این تخته‌ی اشتراکی سبک است؛ با ری‌استارت/دیپلویِ مجدد اپ پاک می‌شود و جای دیتابیس را نمی‌گیرد.",
     "⚠️ This lightweight shared board resets on app restart/redeploy — it does not replace a database."),
    ("📚 منابع داده (مستندات رسمی)", "📚 Data Sources (official docs)"),
    # --- برد مشترک (community_store) ---
    ("برد مشترک: Supabase (پایدار)", "Community board: Supabase (stable)"),
    ("برد مشترک: فایل محلی (موقتی) — ", "Community board: local file (temporary) — "),
    ("هشدار: ", "Warning: "),
    ("ناشناس", "Anonymous"),
    # --- صفحه ۱: قیمت‌های زنده ---
    ("📊 قیمت‌های زنده بازار", "📊 Live Market Prices"),
    ("اول صرافی رو انتخاب کن، بعد ارز رو سرچ کن — مقایسه KCEX + KuCoin + Binance + Bybit + OKX + Lighter",
     "Pick an exchange, then search a coin — compare KCEX + KuCoin + Binance + Bybit + OKX + Lighter"),
    ("🏦 صرافی (لیست ارز از اینجا میاد)", "🏦 Exchange (coin list comes from here)"),
    ("سرعت بروزرسانی", "Refresh rate"),
    ("🔄 بروزرسانی خودکار", "🔄 Auto refresh"),
    ("🔄 دستی آپدیت کن", "🔄 Manual update"),
    ("🔍 سرچ ارز", "🔍 Search coin"),
    ("مثلا BTC یا DOGE یا SOL...", "e.g. BTC or DOGE or SOL..."),
    ("👆 اول یه ارز رو سرچ و انتخاب کن", "👆 Search and pick a coin first"),
    ("قیمتی گرفته نشد — در به‌روزرسانی بعدی دوباره تلاش می‌شود", "No price fetched — retrying on the next refresh"),
    # --- صفحه ۲: ترید مستقیم ---
    ("💹 ترید مستقیم — بدون رفتن به صرافی", "💹 Direct Trading — no need to leave the app"),
    ("کلیدها فقط در حافظه مرورگر شما (session) می‌ماند و در گیت‌هاب ذخیره نمی‌شود.",
     "Keys stay only in your browser memory (session) and are never saved to GitHub."),
    ("KCEX در کتابخانه‌ی ccxt پشتیبانی نمی‌شود؛ برای ترید واقعی KuCoin/OKX/Bybit/Binance را انتخاب کن.",
     "KCEX is not supported by ccxt; for real trading pick KuCoin/OKX/Bybit/Binance."),
    ("Passphrase (اگه صرافی می‌خواد مثل KCEX/KuCoin/OKX)", "Passphrase (if your exchange requires it, e.g. KCEX/KuCoin/OKX)"),
    ("نماد (ccxt فرمت)", "Symbol (ccxt format)"),
    ("مثل BTC/USDT", "e.g. BTC/USDT"),
    ("Paper (مجازی برای تست)", "Paper (virtual, for testing)"),
    ("Real (پول واقعی)", "Real (live money)"),
    ("🔌 اتصال", "🔌 Connect"),
    ("ذخیره شد در session", "Saved in session"),
    ("اول اتصال رو بزن. برای Paper نیازی به کلید نیست.", "Press Connect first. Paper mode needs no keys."),
    ("🛒 ثبت سفارش", "🛒 Place order"),
    ("قیمت لیمیت (فقط limit)", "Limit price (limit orders only)"),
    ("مقدار (ارز پایه)", "Amount (base currency)"),
    ("✅ اجرای سفارش مجازی", "✅ Execute virtual order"),
    ("قیمت زنده در دسترس نیست؛ سفارش مجازی ثبت نشد. صرافی/نماد را عوض کن یا دوباره «اتصال» بزن.",
     "Live price unavailable; virtual order not placed. Change exchange/symbol or press «Connect» again."),
    ("مقدار باید بزرگ‌تر از صفر باشد.", "Amount must be greater than zero."),
    ("✅ ارسال سفارش واقعی", "✅ Send real order"),
    ("کلید وارد کن", "Enter your keys"),
    ("قیمت لیمیت بده", "Provide a limit price"),
    ("📋 سفارشات باز / بالانس (Real)", "📋 Open orders / balance (Real)"),
    ("💰 موجودی", "💰 Balance"),
    ("📄 سفارشات باز", "📄 Open orders"),
    ("سفارش بازی نیست", "No open orders"),
    ("در حالت Paper بالانس/اوردر واقعی نداریم.", "In Paper mode there is no real balance/orders."),
    # --- صفحه ۳: دوئل ایجنت‌ها ---
    ("🤖 دوئل ایجنت‌ها — کدوم ربات می‌بره؟ (با مدرک)", "🤖 Agents Duel — which bot wins? (with evidence)"),
    ("NorthmanQuant · Agents Duel v5.0 (+ شکار بازار · ستاپ اعتبارسنجی‌شده) · صفحه آماده‌ی اجراست؛ داده فقط با «شروع دوئل» دریافت می‌شود.",
     "NorthmanQuant · Agents Duel v5.0 (+ market hunt · validated setup) · The page is ready; data loads only when you press «Start duel»."),
    ("۴ ایجنت روی ۱ ارز با قانون‌های شفاف پوزیشن می‌گیرند؛ هر کدام جدول دلیل و مدرک دارد. برنده + پوزیشن اجماعی با SL/TP به 👥 تحلیل‌های کاربران می‌رود.",
     "4 agents take positions on 1 coin with transparent rules; each has an evidence table. The winner + consensus position (with SL/TP) go to 👥 Community Analyses."),
    ("این ایجنت فعلاً پوزیشن نمی‌گیرد (امتیاز زیر آستانه) — ولی تمایلش در جدول دیده می‌شود.",
     "This agent takes no position for now (score below threshold) — its leaning is still shown in the table."),
    ("چند ارز بررسی شود", "How many coins to scan"),
    ("حداقل قدرت اجماع", "Min consensus strength"),
    ("حداقل ایجنت موافق", "Min agreeing agents"),
    ("🔎 شروع شکار بازار", "🔎 Start market hunt"),
    ("روی «🔎 شروع شکار بازار» بزن.", "Press «🔎 Start market hunt»."),
    ("هیچ ارزی هر سه فیلتر را رد نکرد. یعنی الان ستاپ با لبه‌ی واضح در این تایم‌فریم نیست — می‌توانی تایم‌فریم دیگری را امتحان کنی یا «حداقل ایجنت موافق» را روی ۲ بگذاری (ریسک بالاتر).",
     "No coin passed all three filters — there is no clear-edge setup on this timeframe right now. Try another timeframe, or set «Min agreeing agents» to 2 (higher risk)."),
    ("💾 ذخیره برگزیده‌ها (CSV)", "💾 Save picks (CSV)"),
    ("💾 ذخیره‌ی برگزیده‌ها در 👥 تحلیل‌های کاربران", "💾 Save picks to 👥 Community Analyses"),
    ("برای Lighter فقط BTC بنویس (بدون USDT)", "For Lighter write BTC only (without USDT)"),
    ("بالانس شروع", "Starting balance"),
    ("تعداد کندل", "Candle count"),
    ("Lighter پرپ هست - مثلا BTC یا ETH بنویس، نه BTC-USDT", "Lighter is perp — write BTC or ETH, not BTC-USDT"),
    ("core/gaps.py پیدا نشد؛ FVG/BVG در این دوئل صفر در نظر گرفته می‌شود.",
     "core/gaps.py not found; FVG/BVG counts as zero in this duel."),
    ("⚔️ دوئل روی یک ارز", "⚔️ Duel on one coin"),
    ("🔎 شکار بازار — بهترین لانگ/شورت‌های صرافی", "🔎 Market hunt — best longs/shorts on the exchange"),
    ("🚀 شروع دوئل", "🚀 Start duel"),
    ("در حال گرفتن کندل‌ها و ساختن مدارک…", "Fetching candles and building evidence…"),
    ("اتصال به صرافی، نماد و تایم‌فریم را بررسی کن و دوباره «شروع دوئل» را بزن.",
     "Check the exchange, symbol and timeframe, then press «🚀 Start duel» again."),
    ("نتایج زیر مربوط به اجرای موفق قبلی‌اند؛ تحلیل تازه‌ای تولید نشده است.",
     "Results below are from the previous successful run; no new analysis was produced."),
    ("یک ارز انتخاب کن و «🚀 شروع دوئل» را بزن.", "Pick a coin and press «🚀 Start duel»."),
    ("🎯 بهترین پوزیشن (اجماع وزن‌دار ایجنت‌ها)", "🎯 Best position (weighted agent consensus)"),
    ("📐 اعتبار ستاپ‌ها روی همین نماد (walk-forward)", "📐 Setup validation on this symbol (walk-forward)"),
    ("**جدول مدارک نهایی (همه‌ی ابزارها در یک نگاه)**", "**Final evidence table (all tools at a glance)**"),
    ("🧾 جدول دلیل و پوزیشن هر ایجنت", "🧾 Each agent's evidence & position"),
    ("📎 مدارک خام", "📎 Raw evidence"),
    ("🕯️ ۱۲ کندل آخر (آناتومی)", "🕯️ Last 12 candles (anatomy)"),
    ("💧 نقدینگی (سوییپ‌ها و استخرها)", "💧 Liquidity (sweeps & pools)"),
    ("💸 جریان پول (ورود/خروج)", "💸 Money flow (in/out)"),
    ("🧱 زون‌های FVG / BVG فعال", "🧱 Active FVG / BVG zones"),
    ("📈 چارت با زون‌ها، سطوح نقدینگی و پوزیشن نهایی", "📈 Chart with zones, liquidity levels and the final position"),
    ("📝 تحلیل کامل (می‌ره تو 👥 تحلیل‌های کاربران)", "📝 Full analysis (goes to 👥 Community Analyses)"),
    ("💾 ذخیره در 👥 تحلیل‌های کاربران", "💾 Save to 👥 Community Analyses"),
    ("ذخیره شد! در صفحه‌ی اصلی → بخش «🧩 تحلیل‌ها» → تب «👥 تحلیل‌های کاربران» ببین.",
     "Saved! Main page → «🧩 Analyses» section → «👥 Community Analyses» tab."),
    # --- جدول‌ها و مقادیر core/gaps.py ---
    ("خرید 🟢", "Buy 🟢"),
    ("فروش 🔴", "Sell 🔴"),
    ("صعودی 🟢", "Bullish 🟢"),
    ("نزولی 🔴", "Bearish 🔴"),
    ("FVG گپ ارزش", "FVG value gap"),
    ("BVG گپ حجمی", "BVG volume gap"),
    ("زون فعالی نزدیک نیست", "No active zone nearby"),
    ("داخل زون", "inside zone"),
    ("داخل ", "inside "),
    ("زیر قیمت", "below price"),
    ("بالای قیمت", "above price"),
    ("پایین زون", "Zone low"),
    ("بالای زون", "Zone high"),
    ("اندازه/ATR", "Size/ATR"),
    ("حجم کندل وسط", "Middle-candle volume"),
    ("موقعیت قیمت", "Price position"),
    ("لمس شده", "Touched"),
    ("زمان شکل‌گیری", "Formed at"),
    ("زیر قیمت ", "below price "),
    ("حمایت ", "Support "),
    ("مقاومت ", "Resistance "),
    ("زمان شکل", "Formed"),
    ("بله", "Yes"),
    ("خیر", "No"),
    ("اندیکاتور", "Indicator"),
    ("مقدار", "Value"),
    ("امتیاز", "Score"),
    ("نقش", "Role"),
]
_EXACT += [
    ("🟩 FVG صعودی (حمایت)", "🟩 Bullish FVG (support)"),
    ("🟥 FVG نزولی (مقاومت)", "🟥 Bearish FVG (resistance)"),
    ("🟪 BVG حمایتی", "🟪 Support BVG"),
    ("🟪 BVG مقاومتی", "🟪 Resistance BVG"),
    ("BPR حمایتی", "Support BPR"),
    ("BPR مقاومتی", "Resistance BPR"),
    ("فاصله%", "Dist%"),
    ("پرشدگی%", "Fill%"),
    ("خوانش / مدرک", "Reading / evidence"),
    ("وزن ایجنت", "Agent weight"),
    ("سهم در تصمیم%", "Decision share%"),
    ("ورود لانگ 🟢", "Long entry 🟢"),
    ("ورود شورت 🔴", "Short entry 🔴"),
    ("خروج از لانگ ◆", "Long exit ◆"),
    ("خروج از شورت ◆", "Short exit ◆"),
    ("↓ فعال", "↓ active"),
    ("⏰ آخرین به‌روزرسانی: ", "⏰ Last refresh: "),
    ("آخرین تصویر ساخته‌شده: ", "Last built image: "),
    ("◈ THE AGENTS // دفتر ایجنت‌ها — بک‌تست زنده روی داده‌ی فعلی",
     "◈ THE AGENTS // live backtest on current data"),
    ("نام یا شناسه‌ی صرافی", "Exchange name or id"),
    ("هر صرافیِ CCXT: kraken، coinbase، gate، mexc، bitget، htx، xt، lbank، …",
     "Any CCXT venue: kraken, coinbase, gate, mexc, bitget, htx, xt, lbank, …"),
    # کندل‌ها
    ("الگوی پوشای صعودی", "Bullish engulfing"),
    ("الگوی پوشای نزولی", "Bearish engulfing"),
    ("کندل آخر کل بدنه‌ی نزولی قبلی را بلعیده — ورود خریداران",
     "Last candle swallowed the whole previous bearish body — buyers stepping in"),
    ("کندل آخر کل بدنه‌ی صعودی قبلی را بلعیده — ورود فروشندگان",
     "Last candle swallowed the whole previous bullish body — sellers stepping in"),
    ("پین‌بار / چکش", "Pin bar / hammer"),
    ("پین‌بار / ستاره دنباله‌دار", "Pin bar / shooting star"),
    ("رد شدن قیمت‌های پایین — فشار خرید در کف", "Lower prices rejected — buying pressure at the low"),
    ("رد شدن قیمت‌های بالا — فشار فروش در سقف", "Higher prices rejected — selling pressure at the high"),
    ("ماروبوزو (بدنه قوی)", "Marubozu (strong body)"),
    ("کندل قدرتمند بدون سایه — کنترل کامل یک طرف", "Powerful candle with no wick — full one-sided control"),
    ("اینساید بار", "Inside bar"),
    ("فشردگی و تعادل — منتظر شکست", "Compression & balance — waiting for a breakout"),
    ("بدنه‌ها غالباً سبز — خریدار مسلط", "Bodies mostly green — buyers dominant"),
    ("بدنه‌ها غالباً قرمز — فروشنده مسلط", "Bodies mostly red — sellers dominant"),
    ("تعادل بین خریدار و فروشنده", "Balance between buyers and sellers"),
    ("فشار ۵ کندل اخیر", "Pressure of last 5 candles"),
    ("بدنه‌ها غالباً", "Bodies mostly"),
    ("بدنه‌ی", "body"),
    ("بدنه", "body"),
    ("سایه پایین", "Lower wick"),
    ("سایه بالا", "Upper wick"),
    ("سایه‌ی", "wick"),
    ("سایه", "wick"),
    # ساختار بازار
    ("سقف/کف بالاتر (HH/HL)", "Higher high / higher low (HH/HL)"),
    ("سقف/کف پایین‌تر (LH/LL)", "Lower high / lower low (LH/LL)"),
    ("ساختار صعودی کلاسیک", "Classic bullish structure"),
    ("ساختار نزولی کلاسیک", "Classic bearish structure"),
    ("ساختار مختلط", "Mixed structure"),
    ("بازار رنج/در حال تغییر ساختار", "Ranging market / structure shift"),
    ("شکست ساختار (BOS) صعودی", "Break of structure (BOS) bullish"),
    ("شکست ساختار (BOS) نزولی", "Break of structure (BOS) bearish"),
    ("بسته شدن بالای آخرین سقف سوئینگ", "Closed above the last swing high"),
    ("بسته شدن زیر آخرین کف سوئینگ", "Closed below the last swing low"),
    ("ساختار بازار", "Market structure"),
    # روند
    ("چیدمان EMA 20/50/200", "EMA 20/50/200 layout"),
    ("چیدمان کاملاً صعودی میانگین‌ها", "Fully bullish moving-average layout"),
    ("چیدمان کاملاً نزولی میانگین‌ها", "Fully bearish moving-average layout"),
    ("میانگین‌ها در هم — روند غالب ضعیف", "Averages entangled — dominant trend is weak"),
    ("بالای میانگین بلندمدت — روند بزرگ صعودی", "Above the long-term average — major uptrend"),
    ("زیر میانگین بلندمدت — روند بزرگ نزولی", "Below the long-term average — major downtrend"),
    ("قیمت نسبت به EMA200", "Price vs EMA200"),
    ("سوپرترند (10,3)", "SuperTrend (10,3)"),
    ("سوپرترند خرید", "SuperTrend buy"),
    ("سوپرترند فروش", "SuperTrend sell"),
    ("روند قوی", "Strong trend"),
    ("روند ضعیف/رنج", "Weak / ranging trend"),
    (" به سمت بالا", " upward"),
    (" به سمت پایین", " downward"),
    (" غالب", " dominant"),
    ("روند EMA50", "EMA50 trend"),
    ("سوپرترند", "SuperTrend"),
    ("میانگین‌ها", "averages"),
    ("میانگین", "average"),
    ("در هم", "entangled"),
    # نقدینگی
    ("نزدیک‌ترین استخر نقدینگی", "Nearest liquidity pool"),
    ("سقف‌های برابر (EQH)", "Equal highs (EQH)"),
    ("کف‌های برابر (EQL)", "Equal lows (EQL)"),
    ("استاپ‌های فروشندگان بالای سقف‌های برابر — هدف خرید", "Sellers' stops above equal highs — buy target"),
    ("استاپ‌های خریداران زیر کف‌های برابر — هدف فروش", "Buyers' stops below equal lows — sell target"),
    ("جمع‌آوری نقدینگی سقف (Sweep)", "Buy-side liquidity sweep"),
    ("جمع‌آوری نقدینگی کف (Sweep)", "Sell-side liquidity sweep"),
    ("سایه بالای سقف قبلی و برگشت — شکار استاپ خریداران، احتمال ریزش",
     "Wick above the prior high then reversal — buyers' stops hunted, pullback risk"),
    ("سایه زیر کف قبلی و برگشت — شکار استاپ فروشندگان، احتمال صعود",
     "Wick below the prior low then reversal — sellers' stops hunted, bounce risk"),
    ("نقدینگی بالای سقف‌ها نزدیک‌تر است — آهن‌ربای صعود",
     "Liquidity above the highs is nearer — magnet upward"),
    ("نقدینگی زیر کف‌ها نزدیک‌تر است — آهن‌ربای ریزش",
     "Liquidity below the lows is nearer — magnet downward"),
    ("نقدینگی بالای سقف (BSL)", "Liquidity above highs (BSL)"),
    ("نقدینگی زیر کف (SSL)", "Liquidity below lows (SSL)"),
    ("سقف‌های", "highs"),
    ("کف‌های", "lows"),
    ("استاپ", "stops"),
    ("آهن‌ربا", "magnet"),
    ("برگشت", "reversal"),
    ("احتمال", "risk of"),
    ("نزدیک", "near"),
    # جریان پول
    ("ورود پول به بازار", "Money flowing into the market"),
    ("خروج پول از بازار", "Money flowing out of the market"),
    ("جریان پول خنثی", "Neutral money flow"),
    ("پول هوشمند در حال خرید", "Smart money buying"),
    ("پول هوشمند در حال فروش", "Smart money selling"),
    ("MFI خنثی", "MFI neutral"),
    ("CMF چایکین", "Chaikin CMF"),
    ("شیب OBV (۲۰ کندل)", "OBV slope (20 candles)"),
    ("حجم در کندل‌های صعودی بیشتر — انباشت", "Volume higher on up-candles — accumulation"),
    ("حجم در کندل‌های نزولی بیشتر — توزیع", "Volume higher on down-candles — distribution"),
    ("حجم غیرعادی کندل آخر", "Unusual volume on last candle"),
    ("حجم بالا هم‌جهت کندل آخر — تأیید حرکت", "High volume with the last candle — move confirmed"),
    ("جریان پول CMF", "CMF money flow"),
    ("جریان پول", "money flow"),
    ("پول هوشمند", "smart money"),
    ("انباشت", "accumulation"),
    ("توزیع", "distribution"),
    ("تأیید", "confirmation"),
    ("غیرعادی", "unusual"),
    ("هم‌جهت", "aligned with"),
    ("خریدار", "buyer"),
    ("فروشنده", "seller"),
    ("خریداران", "buyers"),
    ("فروشندگان", "sellers"),
    ("مومنتوم", "momentum"),
    ("رو به افزایش", "rising"),
    ("رو به کاهش", "falling"),
    # مومنتوم
    ("هیستوگرام MACD", "MACD histogram"),
    ("مومنتوم صعودی", "Bullish momentum"),
    ("مومنتوم نزولی", "Bearish momentum"),
    ("مومنتوم خنثی", "Neutral momentum"),
    ("مومنتوم مثبت و در حال تقویت", "Positive momentum, strengthening"),
    ("مومنتوم منفی و در حال تقویت", "Negative momentum, strengthening"),
    ("مومنتوم مثبت ولی ضعیف‌شونده", "Positive but weakening momentum"),
    ("مومنتوم منفی ولی ضعیف‌شونده", "Negative but weakening momentum"),
    ("بالای ۵۰ — قدرت خریدار", "Above 50 — buyer strength"),
    ("زیر ۵۰ — قدرت فروشنده", "Below 50 — seller strength"),
    ("استوکاستیک", "Stochastic"),
    ("در حال تقویت", "strengthening"),
    ("ضعیف‌شونده", "weakening"),
    # FVG/BVG و بازگشت به میانگین
    ("FVG صعودی پر نشده", "Unfilled bullish FVG"),
    ("FVG نزولی پر نشده", "Unfilled bearish FVG"),
    ("ناحیه عدم تعادل خرید زیر قیمت — حمایت/محل ورود",
     "Buy imbalance below price — support / entry area"),
    ("ناحیه عدم تعادل فروش بالای قیمت — مقاومت/محل ورود شورت",
     "Sell imbalance above price — resistance / short entry area"),
    ("ناحیه متعادل حمایتی (FVG صعودی روی نزولی) — کف قوی",
     "Balanced support zone (bullish FVG over bearish) — strong floor"),
    ("ناحیه متعادل مقاومتی (FVG نزولی روی صعودی) — سقف قوی",
     "Balanced resistance zone (bearish FVG over bullish) — strong ceiling"),
    ("امتیاز FVG (عدم تعادل اخیر)", "FVG score (recent imbalance)"),
    ("عدم تعادل‌های اخیر به نفع خریدار", "Recent imbalances favor buyers"),
    ("عدم تعادل‌های اخیر به نفع فروشنده", "Recent imbalances favor sellers"),
    ("عدم تعادل معنادار نیست", "No significant imbalance"),
    ("موقعیت در باند بولینگر", "Position in Bollinger band"),
    ("کف باند — کشیدگی به پایین، احتمال برگشت", "Lower band — stretched down, reversal risk"),
    ("سقف باند — کشیدگی به بالا، احتمال اصلاح", "Upper band — stretched up, correction risk"),
    ("وسط باند", "Middle of the band"),
    ("اشباع خرید", "Overbought"),
    ("اشباع فروش", "Oversold"),
    ("بدون اشباع", "No saturation"),
    ("RSI اشباع", "RSI saturation"),
    ("بازگشت به میانگین (باند میانی بولینگر)", "Mean reversion (Bollinger mid-band)"),
    ("بازگشت به میانگین", "mean reversion"),
    ("کشیدگی", "stretch"),
    ("اشباع", "saturation"),
    ("اصلاح", "correction"),
    # سطوح و ورود
    ("ورود در قیمت فعلی بازار", "Entry at current market price"),
    ("ورود لیمیت روی لبه‌ی FVG/BVG صعودی (", "Limit entry at the bullish FVG/BVG edge ("),
    ("ورود لیمیت روی لبه‌ی FVG/BVG نزولی (", "Limit entry at the bearish FVG/BVG edge ("),
    ("زیر ناحیه FVG/BVG صعودی", "Below the bullish FVG/BVG zone"),
    ("بالای ناحیه FVG/BVG نزولی", "Above the bearish FVG/BVG zone"),
    ("زیر کف سوئینگ / نقدینگی فروش", "Below swing low / sell-side liquidity"),
    ("بالای سقف سوئینگ / نقدینگی خرید", "Above swing high / buy-side liquidity"),
    ("۱.۵×ATR زیر ورود (ساختار نزدیک نبود)", "1.5×ATR below entry (no nearby structure)"),
    ("۱.۵×ATR بالای ورود (ساختار نزدیک نبود)", "1.5×ATR above entry (no nearby structure)"),
    ("منتظر شکست ", "waiting for a break "),
    (" (لانگ) یا ", " (long) or "),
    (" (شورت)", " (short)"),
    ("نزدیک حمایت", "Near support"),
    ("نزدیک مقاومت", "Near resistance"),
    ("قیمت روی حمایت — ریسک کم برای خرید", "Price on support — low risk to buy"),
    ("قیمت زیر مقاومت — ریسک کم برای فروش", "Price below resistance — low risk to sell"),
    ("R (سطح ساختاری بعدی نبود)", "R (no next structural level)"),
    ("فعال", "active"),
    ("سطح", "level"),
    ("لبه‌ی", "edge of"),
    ("ناحیه", "zone"),
    ("نزدیک‌ترین", "nearest"),
    ("آخرین", "last"),
    ("قیمت‌ها", "prices"),
    ("قیمت", "price"),
    ("فعلی", "current"),
    ("بالا", "Top"),
    ("پایین", "Bottom"),
    ("دسته", "Category"),
    ("ابزار", "Tool"),
    ("رویداد", "Event"),
    ("جهت", "Side"),
    ("نوع", "Type"),
    ("روند", "trend"),
    ("کندل‌ها", "Candles"),
    ("خنثی", "neutral"),
    ("شناسه‌ی", "id"),
    ("شناسه", "id"),
]
_EXACT += [
    ("دنبال جهت بازار است: هم‌راستایی EMAها، ساختار سقف/کف، سوپرترند، قدرت روند (ADX/DI)، جریان پول و FVG هم‌جهت.",
     "Follows the market direction: EMA alignment, high/low structure, SuperTrend, trend strength (ADX/DI), money flow and aligned FVG."),
    ("شتاب حرکت را می‌خرد: MACD، سرعت ۱۰ کندلی، RSI، حجمِ پشت کندل‌ها، شکست کانال ۲۰ کندلی و جابه‌جایی تازه‌ی FVG.",
     "Buys acceleration: MACD, 10-candle speed, RSI, volume behind candles, 20-candle channel break and fresh FVG shift."),
    ("افراط را می‌فروشد: فاصله از باند بولینگر و VWAP، اشباع RSI، سوییپ نقدینگی (برگشت از سقف/کف) و کندل برگشتی.",
     "Fades extremes: Bollinger/VWAP distance, RSI saturation, liquidity sweeps (reversal from highs/lows) and reversal candles."),
    ("ردّ پول هوشمند: زون‌های FVG/BVG، سوییپ نقدینگی، ساختار بازار، دلتای خرید/فروش و شیب OBV.",
     "Smart-money tracker: FVG/BVG zones, liquidity sweeps, market structure, buy/sell delta and OBV slope."),
    ("⚠️ موتور ستاپ اعتبارسنجی‌شده **خلاف** نظر ایجنت‌هاست (", "⚠️ The validated-setup engine **disagrees** with the agents ("),
    ("⏸ موتور ستاپ اعتبارسنجی‌شده می‌گوید انتظار:", "⏸ The validated-setup engine says expectancy:"),
    ("✅ موتور ستاپ اعتبارسنجی‌شده هم‌جهت است —", "✅ The validated-setup engine agrees —"),
    (". در تست walk-forward، ورود بر اساس اجماع اندیکاتورها به‌تنهایی لبه نداشت؛ این پوزیشن را نگیر.",
     ". In the walk-forward test, entries on indicator consensus alone had no edge — skip this position."),
    (". این نتیجه بک‌تست + تحلیل قانون‌محور است، نه سیگنال قطعی؛ مدیریت ریسک الزامی است.",
     ". This is a backtest + rule-based analysis, not a certain signal; risk management is mandatory."),
    ("سقف ۲۰ کندل سوییپ شد و قیمت برگشت پایین (نقدینگی خریداران جمع شد)",
     "20-candle high swept and price reversed down (buy-side liquidity taken)"),
    ("کف ۲۰ کندل سوییپ شد و قیمت برگشت بالا (نقدینگی فروشندگان جمع شد)",
     "20-candle low swept and price reversed up (sell-side liquidity taken)"),
    ("در ۳ کندل اخیر سوییپی رخ نداده", "No sweep in the last 3 candles"),
    ("میانگین امتیاز FVG سه کندل اخیر", "Average FVG score of the last 3 candles"),
    ("سوپرترند صعودی (قیمت بالای خط)", "SuperTrend bullish (price above the line)"),
    ("سوپرترند نزولی (قیمت زیر خط)", "SuperTrend bearish (price below the line)"),
    ("سقف و کف پایین‌تر (LH/LL)", "Lower highs & lows (LH/LL)"),
    ("ساختار ترکیبی/رنج", "Mixed / ranging structure"),
    ("اشباع خرید، احتمال برگشت", "Overbought — reversal risk"),
    ("اشباع فروش، احتمال برگشت", "Oversold — reversal risk"),
    ("داده‌ی قیمت نامعتبر است؛ صرافی یا نماد دیگری را انتخاب کن.",
     "Price data is invalid; pick another exchange or symbol."),
    ("حداقل ۶۰ کندل معتبر با قیمت و حجم برای دوئل لازم است.",
     "At least 60 valid candles with price & volume are required for the duel."),
    ("تحلیل ذخیره شد → صفحه‌ی اصلی → «تحلیل‌ها» → تب «👥 تحلیل‌های کاربران».",
     "Analysis saved → main page → «Analyses» → «👥 Community Analyses» tab."),
    ("تحلیل قانون‌محور + بک‌تست؛ توصیه‌ی سرمایه‌گذاری نیست.",
     "Rule-based analysis + backtest; not investment advice."),
    ("ارز بررسی‌شده (چرا بقیه انتخاب نشدند)", "Scanned coins (why the rest were not picked)"),
    ("تحلیل اکثر ارزها خطا داد — نمونه:", "Analysis failed for most coins — sample:"),
    ("ایجنت هم‌جهت در بک‌تست سودده نبود", "No aligned agent was profitable in the backtest"),
    ("Equity — موجودی هر ایجنت روی همین کندل‌ها (با کارمزد)",
     "Equity — each agent's balance on these candles (incl. fees)"),
    ("· مقایسه‌ی ۱۰ کندل اخیر با ۱۰ کندل قبل", "· comparing the last 10 candles with the previous 10"),
    ("متن مدرک برای هر فاکتور با عدد واقعی.", "Evidence text per factor with the actual number."),
    ("تعداد اعشار مناسب نمایش — برای میم‌کوین‌های خیلی ارزان هم رقم معنادار نشان بدهد.",
     "Display decimals — so even very cheap meme-coins show a meaningful digit."),
    ("دیتا از app_base (که Lighter و KCEX را هم بلد است)؛ fallback: KuCoin مستقیم.",
     "Data from app_base (which also knows Lighter & KCEX); fallback: direct KuCoin."),
    ("ثبت نتیجه دوئل در برد مشترک — Supabase اگر ست باشد، وگرنه JSON محلی.",
     "Save the duel result to the shared board — Supabase if configured, else local JSON."),
    ("ذخیره در بک‌اند اصلی نشد؛ fallback محلی:", "Saving to the main backend failed; local fallback:"),
    ("کندل می‌آید (بازده، PF، وین‌ریت، دراودان).</div>", "candles (return, PF, win-rate, drawdown).</div>"),
    ("٪ · وزن هر ایجنت از عملکرد واقعی‌اش روی همین", "% · each agent's weight comes from its real performance on this"),
    ("🏆 برنده‌ی بک‌تست:", "🏆 Backtest winner:"),
    ("برنده‌ی بک‌تست:", "backtest winner:"),
    ("موتور FVG/BVG در دسترس نیست.", "FVG/BVG engine is not available."),
    ("در این بازه سوییپ ثبت نشده.", "No sweep recorded in this range."),
    ("اعتبارسنجی ستاپ انجام نشد:", "Setup validation failed:"),
    ("اعتبارسنجی انجام نشد:", "validation failed:"),
    ("زون فعالی نزدیک قیمت نیست.", "No active zone near the price."),
    ("— مدارک کلیدی —", "— key evidence —"),
    ("مدرک (مشاهده‌ی واقعی)", "evidence (actual observation)"),
    ("حد ضرر بر اساس:", "stop-loss basis:"),
    ("· اهداف:", "· targets:"),
    ("دلایل اصلی:", "Main reasons:"),
    ("پوزیشن اجماعی:", "Consensus position:"),
    ("استفاده‌کننده", "posted by"),
    ("ستاپ معتبر خلاف جهت ایجنت‌هاست", "The valid setup is against the agents"),
    ("ستاپ معتبر فعال نیست", "No active valid setup"),
    ("ستاپ معتبر ندارد", "no valid setup"),
    ("دلیل حد ضرر:", "stop-loss reason:"),
    ("ایجنت‌ها در حال بررسی", "agents are scanning"),
    ("ارز تحلیل شد روی", "coins analyzed on"),
    ("ارز خطا داد", "coins errored"),
    ("دوئل اجرا نشد:", "duel failed:"),
    ("ذخیره نشد:", "save failed:"),
    ("خطاها:", "errors:"),
    ("دیتا:", "data:"),
    ("جهت بازار", "market direction"),
    ("باند بالای بولینگر", "Upper Bollinger band"),
    ("باند پایین بولینگر", "Lower Bollinger band"),
    ("z-score بولینگر", "Bollinger z-score"),
    ("سرعت ۱۰ کندلی (ROC/ATR)", "10-candle speed (ROC/ATR)"),
    ("فاصله از بولینگر (فِید)", "Bollinger distance (feed)"),
    ("فاصله از VWAP (فِید)", "VWAP distance (feed)"),
    ("فاصله از VWAP", "VWAP distance"),
    ("دلتای خرید/فروش ۲۰ کندل", "20-candle buy/sell delta"),
    ("دلتای خرید/فروش (۲۰)", "buy/sell delta (20)"),
    ("دلتای ۲۰ کندل", "20-candle delta"),
    ("جابه‌جایی تازه‌ی FVG", "fresh FVG shift"),
    ("شکست کانال ۲۰ کندلی", "20-candle channel break"),
    ("حجم پشت کندل", "volume behind the candle"),
    ("حجم کندل آخر", "last-candle volume"),
    ("کندل آخر:", "last candle:"),
    ("الگوی کندل", "candle pattern"),
    ("تغییر ۱۰ کندل اخیر", "10-candle change"),
    ("سقف ۱۰ کندل اخیر", "10-candle high"),
    ("کف ۱۰ کندل اخیر", "10-candle low"),
    ("۲۰ کندل اخیر", "last 20 candles"),
    ("۱۰ کندل اخیر", "last 10 candles"),
    ("۳ کندل اخیر", "last 3 candles"),
    ("کندل اخیر", "recent candles"),
    ("٪ · نرمال‌شده با ATR", "% · normalized by ATR"),
    ("نرمال‌شده", "normalized"),
    ("(ایمپالس تازه با گپ)", "(fresh impulse with gap)"),
    ("شیب OBV ده کندلی", "10-candle OBV slope"),
    ("· حجم کندل‌های سبز", "· green-candle volume"),
    ("/ قرمز", "/ red"),
    ("انگالفینگ صعودی", "bullish engulfing"),
    ("انگالفینگ نزولی", "bearish engulfing"),
    ("پین‌بار صعودی", "bullish pin bar"),
    ("پین‌بار نزولی", "bearish pin bar"),
    ("سه‌کندلی", "three-candle"),
    ("R (نسبت ریسک)", "R (risk ratio)"),
    ("فشار خرید", "buy pressure"),
    ("فشار فروش", "sell pressure"),
    ("حجم با فروشنده‌هاست", "volume is with sellers"),
    ("حجم با خریدارهاست", "volume is with buyers"),
    ("حجم عادی/کم", "normal/low volume"),
    ("فروشنده تهاجمی", "aggressive sellers"),
    ("خریدار تهاجمی", "aggressive buyers"),
    ("در بازار%", "time in market%"),
    ("معامله — وین", "trades — win"),
    ("ترید · وین", "trades · win"),
    ("· وین", "· win"),
    ("معاملات", "trades"),
    ("وین‌ریت", "win-rate"),
    ("وین%", "win%"),
    ("دراودان", "drawdown"),
    ("بازده", "return"),
    ("تفسیر", "Reading"),
    ("سنجه", "Metric"),
    ("فاکتور", "Factor"),
    ("حوزه", "Area"),
    ("رأی", "vote"),
    ("نتیجه", "Result"),
    ("دلایل:", "reasons:"),
    ("متعادل", "balanced"),
    ("داخل باند", "inside the band"),
    ("داخل کانال", "inside the channel"),
    ("شکست رو به بالا", "break upward"),
    ("شکست رو به پایین", "break downward"),
    ("سهم در تصمیم", "decision share"),
    ("جمع سهم‌ها =", "sum of shares ="),
    ("(ورود وقتی |امتیاز| >", "(entry when |score| >"),
    ("، خروج وقتی <", ", exit when <"),
    ("بدنه٪", "body%"),
    ("الگو", "pattern"),
    ("خنثی ⚪ — صبر", "Neutral ⚪ — wait"),
    ("چرا؟", "Why?"),
    ("کارمزد", "fee"),
    ("دوئل", "Duel"),
]
# --- ۲) عبارت‌های عمومی — برای متن‌های ترکیبی و f-stringها ---------------
_FRAG: list[tuple[str, str]] = [
    ("تحلیل‌های کاربران", "Community Analyses"),
    ("تحلیل‌های", "analyses"),
    ("تحلیلت", "your analysis"),
    ("تحلیل‌ها", "analyses"),
    ("تحلیل", "analysis"),
    ("اعتبارسنجی‌شده", "validated"),
    ("اعتبارسنجی", "validation"),
    ("اعتبار", "validity"),
    ("سرمایه‌گذاری", "investment"),
    ("توصیه‌ی", "recommendation"),
    ("توصیه", "recommendation"),
    ("مدیریت ریسک", "risk management"),
    ("ریسک به ریوارد", "risk-reward"),
    ("ریوارد", "reward"),
    ("ریسک", "risk"),
    ("ارزهای", "coins"),
    ("ارزها", "coins"),
    ("ارزش", "value"),
    ("ارز", "coin"),
    ("صرافیِ", "exchange"),
    ("صرافی‌ها", "exchanges"),
    ("صرافی", "exchange"),
    ("تایم‌فریم", "timeframe"),
    ("هم‌راستایی", "alignment"),
    ("همگرایی", "confluence"),
    ("سیگنال", "signal"),
    ("اندیکاتورها", "indicators"),
    ("شبیه‌سازی شده", "simulated"),
    ("شبیه‌سازی", "simulation"),
    ("بک‌تست", "backtest"),
    ("اسکنر", "scanner"),
    ("اسکن", "scan"),
    ("بروزرسانی", "refresh"),
    ("به‌روزرسانی", "refresh"),
    ("آپدیت", "update"),
    ("رفرش", "refresh"),
    ("بازخوانی", "refresh"),
    ("پوزیشن‌ها", "positions"),
    ("پوزیشن", "position"),
    ("مدارک", "evidence"),
    ("مدرک", "evidence"),
    ("اعتماد", "trust"),
    ("اطمینان", "confidence"),
    ("قانون‌های", "rules"),
    ("قانون", "rule"),
    ("میتوانی", "you can"),
    ("می‌توانی", "you can"),
    ("ایجنت‌های", "agents'"),
    ("ایجنت‌ها", "agents"),
    ("ایجنت", "agent"),
    ("دوئل", "duel"),
    ("شکار بازار", "market hunt"),
    ("شکار", "hunt"),
    ("اجماع", "consensus"),
    ("وزن‌دار", "weighted"),
    ("وزن", "weight"),
    ("بهترین", "best"),
    ("قوی‌ای", "strong"),
    ("قوی", "strong"),
    ("ضعیف", "weak"),
    ("پرحجم‌ترین", "highest-volume"),
    ("پرمعامله‌ترین", "most-traded"),
    ("برترین‌ها", "Top Movers"),
    ("برترین", "top"),
    ("بیشترین", "most"),
    ("فرصت‌های", "opportunities"),
    ("فرصت‌ها", "opportunities"),
    ("فرصت", "opportunity"),
    ("سودده", "profitable"),
    ("سود", "profit"),
    ("ریزش", "losers"),
    ("برگزیده‌ها", "picks"),
    ("برگزیده", "picks"),
    ("بازده", "return"),
    ("همبستگی", "correlation"),
    ("رگرسیون", "regression"),
    ("ماتریس", "matrix"),
    ("لبه", "edge"),
    ("شیب", "slope"),
    ("مثبت", "positive"),
    ("نارنجی", "orange"),
    ("هدف", "target"),
    ("تارگت", "target"),
    ("نقاط", "points"),
    ("نقطه", "point"),
    ("حمایت", "support"),
    ("مقاومت", "resistance"),
    ("سوئینگ", "swing"),
    ("سطوح", "levels"),
    ("معنادار", "significant"),
    ("زون‌های", "zones"),
    ("زون‌ها", "zones"),
    ("زون", "zone"),
    ("نواحی", "zones"),
    ("ناحیه‌ی", "area"),
    ("عدم تعادل", "imbalance"),
    ("هم‌پوشانی", "overlap"),
    ("ناترازی", "imbalance"),
    ("کندل‌ها", "candles"),
    ("کندل‌های", "candles"),
    ("کندل", "candle"),
    ("نقدینگی", "liquidity"),
    ("سوییپ", "sweep"),
    ("استخر", "pool"),
    ("جریان پول", "money flow"),
    ("پول هوشمند", "smart money"),
    ("پول", "money"),
    ("ساختار", "structure"),
    ("سقف", "high"),
    ("کف", "low"),
    ("بالای", "above"),
    ("زیر", "below"),
    ("داخل", "inside"),
    ("حجم", "volume"),
    ("اندازه", "size"),
    ("موقعیت", "position"),
    ("مقایسه", "compare"),
    ("مقایسه‌ی", "compare"),
    ("صعودی", "bullish"),
    ("نزولی", "bearish"),
    ("لانگ", "long"),
    ("شورت", "short"),
    ("خرید", "buy"),
    ("فروش", "sell"),
    ("ورود/خروج", "entry/exit"),
    ("ورود", "entry"),
    ("خروج", "exit"),
    ("حداقل", "min"),
    ("حداکثر", "max"),
    ("حد ضرر", "stop-loss"),
    ("حد سود", "take-profit"),
    ("حدود", "≈"),
    ("حد", "limit"),
    ("باز", "open"),
    ("بسته", "closed"),
    ("لمس", "touch"),
    ("تصویر", "image"),
    ("عکس", "image"),
    ("چارت", "chart"),
    ("نمودار", "chart"),
    ("پس‌زمینه", "background"),
    ("رنگی", "color"),
    ("رنگ", "color"),
    ("شخصی‌سازی", "customize"),
    ("ظاهر", "appearance"),
    ("تنظیمات", "settings"),
    ("پنل", "panel"),
    ("بخش‌ها", "sections"),
    ("بخش", "section"),
    ("صفحه‌ی", "page"),
    ("صفحه", "page"),
    ("دکمه‌ی", "the button"),
    ("دکمه", "button"),
    ("لیست", "list"),
    ("فهرست", "list"),
    ("جدول", "table"),
    ("ستاره‌دار", "starred"),
    ("ستون", "column"),
    ("ردیف‌های", "rows"),
    ("ردیف", "row"),
    ("فیلترها", "filters"),
    ("فیلتر", "filter"),
    ("جستجو", "search"),
    ("سرچ", "search"),
    ("انتخابی", "selected"),
    ("انتخاب کن", "pick"),
    ("انتخاب", "select"),
    ("وارد کن", "enter"),
    ("وارد", "enter"),
    ("نمادها", "symbols"),
    ("نماد", "symbol"),
    ("کریپتو", "crypto"),
    ("فارکس", "forex"),
    ("ژئوپلیتیک", "geopolitics"),
    ("اقتصاد", "economy"),
    ("اخبار", "news"),
    ("خبری", "news"),
    ("خبر", "news"),
    ("فیدها", "feeds"),
    ("فید", "feed"),
    ("منبع اصلی", "original source"),
    ("منبع", "source"),
    ("متن کامل", "full text"),
    ("متن", "text"),
    ("دسته‌بندی", "category"),
    ("زمان‌بندی", "timing"),
    ("زمان", "time"),
    ("سرعت", "speed"),
    ("تعداد", "count"),
    ("دقیقه", "min"),
    ("ثانیه", "sec"),
    ("هفته", "week"),
    ("۲۴س", "24h"),
    ("خودکار", "auto"),
    ("دستی", "manual"),
    ("زنده", "live"),
    ("لحظه‌ای", "real-time"),
    ("لحظه", "moment"),
    ("امتیاز", "score"),
    ("نمایش", "show"),
    ("ذخیره‌ی", "save"),
    ("ذخیره", "save"),
    ("دانلود", "download"),
    ("ارسال", "send"),
    ("اشتراک‌گذاری", "sharing"),
    ("ثبت", "post"),
    ("شروع", "start"),
    ("پایان", "end"),
    ("بستن", "close"),
    ("اجرا", "run"),
    ("اجرای", "run"),
    ("آماده‌ی", "ready"),
    ("آماده", "ready"),
    ("بررسی", "check"),
    ("امتحان کنی", "try"),
    ("امتحان کن", "try"),
    ("امتحان", "try"),
    ("عوض کن", "change"),
    ("کم کن", "lower it"),
    ("بزنید", "press"),
    ("بزن", "press"),
    ("دوباره", "again"),
    ("دیگر", "another"),
    ("دیگری", "another"),
    ("بعدی", "next"),
    ("قبلی‌اند", "are previous"),
    ("قبلی", "previous"),
    ("قبل", "before"),
    ("بعد", "after"),
    ("الان", "now"),
    ("فعلاً", "for now"),
    ("همیشه", "always"),
    ("باید", "must"),
    ("باشد", "be"),
    ("صفر", "zero"),
    ("بزرگ‌تر", "greater"),
    ("کمتر", "lower"),
    ("بیشتر", "more"),
    ("بالاتر", "higher"),
    ("پایین", "bottom"),
    ("درشت‌تر", "wider"),
    ("فشرده‌تر", "more compressed"),
    ("همین", "this"),
    ("همان", "the same"),
    ("همه‌ی", "all"),
    ("همه", "all"),
    ("هر", "each"),
    ("فقط", "only"),
    ("بدون", "without"),
    ("پیدا نشد", "not found"),
    ("در دسترس نیست", "not available"),
    ("دریافت", "fetch"),
    ("داده‌ی", "data"),
    ("داده‌ها", "data"),
    ("داده", "data"),
    ("اطلاعات", "info"),
    ("حافظه", "memory"),
    ("مرورگر", "browser"),
    ("گیت‌هاب", "GitHub"),
    ("سرور", "server"),
    ("کلیدها", "keys"),
    ("کلید", "key"),
    ("سفارشات", "orders"),
    ("سفارش", "order"),
    ("بالانس", "balance"),
    ("موجودی", "balance"),
    ("لیمیت", "limit"),
    ("مجازی", "virtual"),
    ("واقعی", "real"),
    ("پول واقعی", "live money"),
    ("تست", "test"),
    ("حالت", "mode"),
    ("اتصال", "connection"),
    ("متصل", "connected"),
    ("پایدار", "stable"),
    ("موقتی", "temporary"),
    ("محلی", "local"),
    ("فایل", "file"),
    ("دیتابیس", "database"),
    ("بک‌اند", "backend"),
    ("کش", "cache"),
    ("مستندات", "docs"),
    ("رسمی", "official"),
    ("نسخه", "Version"),
    ("معامله", "trade"),
    ("معامله‌گر", "trader"),
    ("ترید", "trading"),
    ("کاربران", "users"),
    ("کاربر", "user"),
    ("نام مستعار", "alias"),
    ("نام", "name"),
    ("شما", "your"),
    ("ستاپ‌ها", "setups"),
    ("ستاپ", "setup"),
    ("شفاف", "transparent"),
    ("برنده", "winner"),
    ("برچسب‌های", "labels"),
    ("برچسب", "label"),
    ("آناتومی", "anatomy"),
    ("ابزارها", "tools"),
    ("ابزار", "tool"),
    ("یک نگاه", "one glance"),
    ("نهایی", "final"),
    ("خام", "raw"),
    ("کامل", "full"),
    ("جزئیات", "details"),
    ("حرفه‌ای", "professional"),
    ("موافق", "agreeing"),
    ("قدرت", "strength"),
    ("آستانه", "threshold"),
    ("تمایل", "leaning"),
    ("هیچ", "no"),
    ("واضح", "clear"),
    ("بالاترین", "highest"),
    ("پایین‌ترین", "lowest"),
    ("اولین", "first"),
    ("اول", "first"),
    ("رفتار", "behavior"),
    ("هشدار", "Warning"),
    ("خطا", "error"),
    ("ناموفق", "failed"),
    ("موفق", "successful"),
    ("خالی", "empty"),
    ("سبک", "lightweight"),
    ("اشتراکی", "shared"),
    ("تخته", "board"),
    ("برد", "board"),
    ("دیپلوی", "deploy"),
    ("ری‌استارت", "restart"),
    ("تنظیم", "configure"),
    ("می‌شود", "is done"),
    ("می‌کند", "does"),
    ("می‌ماند", "stays"),
    ("می‌بره", "wins"),
    ("می‌ره", "goes"),
    ("میاد", "comes"),
    ("می‌خواد", "needs"),
    ("نمی‌شود", "cannot be"),
    ("نیست", "not"),
    ("است", "is"),
    ("موتور", "engine"),
    ("شتاب", "acceleration"),
    ("کندلی", "-candle"),
    ("اخیر", "recent"),
    ("سبز", "green"),
    ("قرمز", "red"),
    ("تهاجمی", "aggressive"),
    ("ده کندلی", "10-candle"),
    ("حرکت", "move"),
    ("نسبت به", "vs"),
    ("برای", "for"),
    ("مثل", "e.g."),
    ("مثلاً", "e.g."),
    ("مثلا", "e.g."),
    ("روی", "on"),
    ("یا", "or"),
    ("این", "this"),
    ("تا", "until"),
    ("با", "with"),
    ("از", "of"),
    ("به", "to"),
    ("در", "in"),
    ("را", ""),
    ("و", " & "),
    ("که", "that"),
    ("ولی", "but"),
    ("اگر", "if"),
    ("چندین", "several"),
    ("چند", "few"),
    ("یک‌بار", "once"),
    ("یکی‌یکی", "one by one"),
    ("یه", "a"),
    ("یک", "one"),
    ("شما", "your"),
    ("تو", "your"),
    ("نکن", "don't"),
    ("کنار", "next to"),
    ("کن", "press"),
]


# --- پچ واژه‌نامه v6 (منو، اخبار، ایجنت‌ها، وضعیت‌ها، خطاها) ---
_EXACT += [
    ('📚 منابع داده', '📚 Data Sources'),
    ('🧑\u200d💻 تحلیل\u200cها (ثبت · تصویر · کاربران)', '🧑\u200d💻 Analyses (Post · Image · Community)'),
    ('📊 تحلیل زنده', '📊 Live Analysis'),
    ('💎 فرصت\u200cهای سودده', '💎 Profit Opportunities'),
    ('📰 اخبار', '📰 News'),
    ('بخش\u200cها', 'Sections'),
    ('➕ صرافی دیگر (CCXT)', '➕ Other exchange (CCXT)'),
    ('🇺🇸 بازار آمریکا', '🇺🇸 US Market'),
    ('🌍 اقتصاد جهان', '🌍 World Economy'),
    ('⚔️ جنگ و ژئوپلیتیک', '⚔️ War & Geopolitics'),
    ('کلاهبرداری', 'Scam'),
    ('ارزدیجیتال', 'Crypto'),
    ('زومیت', 'Zoomit'),
    ('شکایت', 'Complaint'),
    ('تایید', 'Approval'),
    ('بهبود', 'Recovery'),
    ('پامپ', 'Pump'),
    ('دامپ', 'Dump'),
    ('جهش', 'Surge'),
    ('رشد', 'Growth'),
    ('سقوط', 'Fall'),
    ('کاهش', 'Decline'),
    ('صعود', 'Uptrend'),
    ('افت', 'Drop'),
    ('ترس', 'Fear'),
    ('اوج', 'Peak'),
    ('هک', 'Hack'),
    ('رالی', 'Rally'),
    ('تیکر', 'Ticker'),
    ('سایر', 'Other'),
    ('گاوی', 'Bullish'),
    ('خرسی', 'Bearish'),
    ('لیکویید', 'Liquidation'),
    ('ممنوعیت', 'Ban'),
    ('پذیرش', 'Adoption'),
    ('برخورد', 'Collision'),
    ('شکارچی FVG', 'FVG Hunter'),
    ('سوار روند', 'Trend Rider'),
    ('شکست مقاومت', 'Resistance Break'),
    ('شکست حمایت', 'Support Break'),
    ('شکست کانال', 'Channel Break'),
    ('پولبک در روند', 'Pullback in trend'),
    ('مقاومتی', 'At resistance'),
    ('حمایتی', 'At support'),
    ('مجموع R', 'Total R'),
    ('ورتکس', 'Vortex'),
    ('رکورد', 'Record'),
    ('افزایش', 'Increase'),
    ('بازگشت', 'Return'),
    ('منفی 🔴', 'Bearish 🔴'),
    ('منفی', 'Negative'),
    ('خلاف ⚠️', 'Against ⚠️'),
    ('درهم', 'Mixed'),
    ('✅ TP1 لمس شد', '✅ TP1 hit'),
    ('✅ TP2 لمس شد', '✅ TP2 hit'),
    ('🏆 TP3 لمس شد', '🏆 TP3 hit'),
    ('❌ حد ضرر خورد', '❌ Stop-loss hit'),
    ('✅ قابل اعتماد', '✅ Reliable'),
    ('❌ لبه ندارد', '❌ No edge'),
    ('⏸ انتظار (بدون معامله)', '⏸ Waiting (no trade)'),
    ('معاملات تست\u200cشده', 'Tested trades'),
    ('انتظار ریاضی (R در هدف 2R)', 'Expectancy (R at 2R target)'),
    ('TP1 قبل از SL (اندازه\u200cگیری\u200cشده)', 'TP1 before SL (measured)'),
    (' معامله\u200cی تست\u200cشده، TP1 قبل از SL در ', ' tested trade, TP1 before SL at '),
    ('هیچ ستاپ معتبری فعال نیست', 'No valid setup active'),
    ('» فعال شده ولی روی همین نماد/تایم\u200cفریم در تست walk-forward لبه ندارد', '» enabled but has no edge on this symbol/timeframe in walk-forward test'),
    ('شروع پیپر ترید (مجازی)', 'Start paper trading (virtual)'),
    ('می\u200cفهمم پول واقعی است و مسئولیت با من است', 'I understand this is real money and I am responsible'),
    ('روند صعودی — منتظر پولبک: RSI<35 یا نزدیک باند پایین ', 'Bullish trend — wait pullback: RSI<35 or near lower band '),
    ('روند نزولی — منتظر پولبک: RSI>65 یا نزدیک باند بالای ', 'Bearish trend — wait pullback: RSI>65 or near upper band '),
    ('بدون روند (EMA50/200 درهم)', 'No trend (EMA50/200 mixed)'),
    ('موجودی مجازی کافی نیست: نیاز ', 'Virtual balance not enough: need '),
    ('در حال گرفتن لیست ارزهای ', 'Fetching coin list of '),
    ('🖼️ تحلیل تصویری NorthmanQuant', '🖼️ NorthmanQuant Chart Analysis'),
    ('قوی\u200cترین ستاپ\u200cهای لانگ/شورت از میان پرمعامله\u200cترین ارزها، با حد ضرر و سه تیک\u200cپرافیت + FVG/BVG. صرافی: ', 'Strongest long/short setups among the most-traded coins, with stop-loss and three take-profits + FVG/BVG. Exchange: '),
    ('نماد را وارد کن تا خودش از داده\u200cی **واقعی** صرافی تحلیل کند و یک **تصویر چارت آماده** با نقاط ورود/حد ضرر/اهداف و سطوح حمایت و مقاومت بسازد — قابل دانلود و اشتراک\u200cگذاری.', 'Enter a symbol and it will analyze **real** exchange data and build a **ready chart image** with entry/stop/targets and support/resistance levels — downloadable and shareable.'),
    ('ایجنت\u200cها خودشان پرحجم\u200cترین ارزهای صرافی را یکی\u200cیکی از همان موتور دوئل رد می\u200cکنند و فقط ارزهایی را برمی\u200cگزینند که ۱) اجماع قوی دارند، ۲) حداقل ۳ ایجنت هم\u200cجهت\u200cاند، ۳) ایجنت هم\u200cجهت روی همان ارز در بک\u200cتست سودده بوده و ۴) موتور ستاپ اعتبارسنجی\u200cشده (walk-forward روی همان ارز) همین الان ستاپ هم\u200cجهت داده باشد. اگر چیزی این فیلترها را رد نکند، چیزی نشان داده نمی\u200cشود — بهتر از سیگنال الکی.', "The agents run the exchange's highest-volume coins through the same duel engine and only pick coins that: 1) have strong consensus, 2) at least 3 agents aligned, 3) an aligned agent was profitable on that coin in backtest, and 4) the validated-setup engine (walk-forward on that coin) gives an aligned setup right now. If nothing passes these filters, nothing is shown — better than fake signals."),
    (' · قیمت\u200cها و تحلیل\u200cها خودکار به\u200cروز می\u200cشوند.', ' · prices and analyses update automatically.'),
    (' فرصت · مرتب بر اساس قدرت × ADX × هم\u200cجهتی FVG', ' opportunities · sorted by strength × ADX × FVG alignment'),
    ('دریافت اخبار ممکن نشد: ', 'News fetch failed: '),
    ('دریافت فهرست بازار ممکن نشد: ', 'Market list fetch failed: '),
    ('ساخت تصویر ممکن نشد: ', 'Image build failed: '),
    ('قیمت گرفته نشد: ', 'Price fetch failed: '),
    ('کندل کافی برای این نماد/صرافی برنگشت.', 'Not enough candles for this symbol/exchange.'),
    ('کندل کافی از این صرافی برنگشت.', 'Not enough candles from this exchange.'),
    ('فهرست بازار خالی بود', 'Market list was empty'),
    ('قیمت آخر خالی برگشت', 'Last price came back empty'),
    ('مدارک محاسبه نشد: ', 'Evidence calc failed: '),
    ('در حال تحلیل ', 'Analyzing '),
    ('» در CCXT پشتیبانی نمی\u200cشود.', '» is not supported in CCXT.'),
    (' در ccxt پشتیبانی نمی\u200cشود — صرافی دیگری انتخاب کن', ' is not supported in ccxt — pick another exchange'),
    ("' پیدا نشد — همه رو نشون میدم", "' not found — showing all"),
    ('ثبت شد: ', 'Posted: '),
    (' پیدا شد', ' found'),
    ('انجام شد در قیمت ', 'done at price '),
    (' آماده شد · قیمت ', ' ready · price '),
    ('چه چیزی لازم است: ', 'What is needed: '),
    ('نمونه\u200cها: ', 'Examples: '),
    (') · همین قانون\u200cها در بک\u200cتست کندل\u200cبه\u200cکندل اعمال شده\u200cاند.', ') · the same rules were applied candle-by-candle in backtest.'),
    ('کپی متن 📋', 'Copy text 📋'),
    ('ذخیره فایل 💾', 'Save file 💾'),
    ('کپی شد ✓', 'Copied ✓'),
    ('پوسته مدل\u200cها — جریان ویژگی به لبه', 'Neural Shell — feature flow to edge'),
    ('محور افقی: امتیاز همگرایی (−۱۰۰ تا +۱۰۰) · محور عمودی: بازده کندل بعدی', 'X-axis: confluence score (−100 to +100) · Y-axis: next-candle return'),
    ('نواحی عدم تعادل فعال (پر نشده) — سبز حمایت · قرمز مقاومت · بنفش ناحیه متعادل', 'Active imbalance zones (unfilled) — green support · red resistance · purple balanced zone'),
    ('هیچ FVG/BVG فعالی نزدیک قیمت نیست', 'No active FVG/BVG near price'),
    ('ناحیه\u200cی FVG/BVG فعالی نزدیک قیمت نیست', 'No active FVG/BVG zone near price'),
    ('داده کافی نیست', 'Not enough data'),
    ('لحاظ شده', 'included'),
    ('سوار روند — روند و ساختار بازار را دنبال می\u200cکند', 'Trend Rider — follows trend & market structure'),
    ('٪ موارد، انتظار ریاضی ', '% of cases, expectancy '),
    (' — فرصت آربیتراژ!', ' — arbitrage opportunity!'),
    ('گپ\u200cها (FVG/BVG)', 'Gaps (FVG/BVG)'),
    ('app_base نشد (', 'app_base failed ('),
    ('ATR · پر ', 'ATR · full '),
    ("چیزی با '", "Something with '"),
]

_FRAG += [
    ('لمس شد', 'hit'),
    ('خورد', 'hit'),
    ('ممکن نشد', 'failed'),
    ('برنگشت', 'came back empty'),
    ('کافی', 'enough'),
    ('تلگرام', 'Telegram'),
    ('واتساپ', 'WhatsApp'),
    ('توییتر', 'Twitter'),
    ('کپی', 'Copy'),
    ('جنگ', 'War'),
    ('ژئوپلیتیک', 'Geopolitics'),
    ('اقتصاد', 'Economy'),
    ('آمریکا', 'US'),
    ('جهان', 'World'),
    ('قیمت\u200cهای', 'prices'),
    ('نبرد', 'Battle'),
    ('دوئل', 'Duel'),
    ('شکارچی', 'Hunter'),
    ('پولبک', 'pullback'),
    ('باند', 'band'),
    ('مجازی', 'virtual'),
    ('واقعی', 'real'),
    ('مسئولیت', 'responsibility'),
    ('شروع', 'Start'),
    ('پیپر', 'paper'),
    ('ترید', 'trading'),
    ('موجودی', 'balance'),
    ('نیاز', 'need'),
    ('لیست', 'list'),
    ('فهرست', 'list'),
    ('دریافت', 'fetch'),
    ('ساخت', 'build'),
    ('خالی', 'empty'),
    ('پیدا شد', 'found'),
    ('ثبت شد', 'posted'),
    ('آماده شد', 'ready'),
    ('انجام شد', 'done'),
    ('محاسبه', 'calc'),
    ('اختلاف', 'spread'),
    ('کمترین', 'lowest'),
    ('نمونه', 'example'),
    ('جدید', 'new'),
    ('رنج', 'range'),
    ('هیستوگرام', 'Histogram'),
    ('معاملات', 'trades'),
    ('ایجنت', 'agent'),
    ('درهم', 'mixed'),
    ('صعودی', 'bullish'),
    ('نزولی', 'bearish'),
    ('روند', 'trend'),
    ('نشده', 'not'),
    ('ندارد', 'none'),
    ('گپ\u200cها', 'Gaps'),
    ('آربیتراژ', 'arbitrage'),
    ('مارکت', 'market'),
    ('پر', 'full'),
    ('موارد', 'cases'),
    ('انتظار', 'wait'),
    ('دنبال', 'follows'),
    ('٪', '%'),
]

# نهایی: همه‌ی جفت‌ها — طولانی‌ترین اول + نرمال‌سازی ویرگول فارسی
_PAIRS: list[tuple[str, str]] = sorted(
    list(dict.fromkeys(_EXACT + _FRAG)), key=lambda p: -len(p[0])
)
_PAIRS = sorted(
    list(dict.fromkeys(
        (fa.replace("\u060c", ",").replace("\u061b", ";"), en)
        for fa, en in _PAIRS
    )),
    key=lambda p: -len(p[0]),
)
_PAIR_MAP: dict[str, str] = dict(_PAIRS)

# یک رجکس واحد: طولانی‌ترین عبارت اول + مرز واژه‌ی فارسی (حروف/ZWNJ)
# تا کلمات کوتاه داخل کلمات بلندتر خراب نشوند (مثلاً «در» داخل «مدرک»).
_FA_LETTERS = r"[\u0600-\u06FF\u200c\u0650-\u0652]"
_BIG_RE = re.compile(
    r"(?<!" + _FA_LETTERS + r")(?:"
    + "|".join(re.escape(fa) for fa, _ in _PAIRS)
    + r")(?!" + _FA_LETTERS + r")"
)


def deep_en(s):
    """هر رشته‌ی فارسی را به انگلیسی تبدیل می‌کند (اگر زبان EN باشد)."""
    if not isinstance(s, str) or get_lang() != "en" or not _FA_ANY.search(s):
        return s
    s = s.replace("\u060c", ",").replace("\u061b", ";")  # ویرگول فارسی
    out = _BIG_RE.sub(lambda mo: _PAIR_MAP.get(mo.group(0), mo.group(0)), s)
    return out.translate(_FA_DIGITS)


def deep_df(df):
    """کپی ترجمه‌شده‌ی یک DataFrame (نام ستون‌ها + سلول‌های متنی)."""
    try:
        import pandas as pd
        if not isinstance(df, pd.DataFrame):
            return df
        out = df.copy()
        out.columns = [deep_en(str(c)) for c in out.columns]
        for c in out.columns:
            if out[c].dtype == object:
                out[c] = out[c].map(lambda v: deep_en(v) if isinstance(v, str) else v)
        return out
    except Exception:
        return df


def deep_fig(fig):
    """ترجمه‌ی سبک برچسب‌های یک فیگور Plotly (عنوان، annotation، نام trace، متن‌ها)."""
    try:
        if fig is None or get_lang() != "en":
            return fig
        lay = getattr(fig, "layout", None)
        if lay is not None:
            if getattr(lay.title, "text", None):
                lay.title.text = deep_en(lay.title.text)
            for ann in (getattr(lay, "annotations", None) or []):
                if getattr(ann, "text", None):
                    ann.text = deep_en(ann.text)
        for tr_ in getattr(fig, "data", []) or []:
            if getattr(tr_, "name", None):
                tr_.name = deep_en(tr_.name)
            txt = getattr(tr_, "text", None)
            if isinstance(txt, str):
                tr_.text = deep_en(txt)
            elif txt is not None and hasattr(txt, "__iter__"):
                try:
                    tr_.text = [deep_en(x) if isinstance(x, str) else x for x in txt]
                except Exception:
                    pass
            ht = getattr(tr_, "hovertemplate", None)
            if isinstance(ht, str):
                tr_.hovertemplate = deep_en(ht)
            hv = getattr(tr_, "hovertext", None)
            if isinstance(hv, str):
                tr_.hovertext = deep_en(hv)
        return fig
    except Exception:
        return fig


# ===========================================================================
# پچ ویجت‌های Streamlit — «نمایش» ترجمه می‌شود؛ مقادیر و منطق دست‌نخورده
# ===========================================================================
_PATCHED_FLAG = "_nq_i18n_patched_v5"


def _patch_display_widgets() -> None:
    if getattr(st, _PATCHED_FLAG, False):
        return
    (o_title, o_header, o_sub, o_md, o_text, o_cap, o_info, o_warn, o_succ,
     o_err, o_metric, o_btn, o_dbtn, o_fsb, o_lbtn, o_cb, o_tg, o_rd, o_sb,
     o_ms, o_ssl, o_sl, o_ni, o_ti, o_ta, o_fu, o_ex, o_tabs, o_spin,
     o_status, o_toast, o_prog, o_df, o_tbl, o_pc) = (
        st.title, st.header, st.subheader, st.markdown, st.text, st.caption,
        st.info, st.warning, st.success, st.error, st.metric, st.button,
        st.download_button, st.form_submit_button, st.link_button,
        st.checkbox, st.toggle, st.radio, st.selectbox, st.multiselect,
        st.select_slider, st.slider, st.number_input, st.text_input,
        st.text_area, st.file_uploader, st.expander, st.tabs, st.spinner,
        st.status, st.toast, st.progress, st.dataframe, st.table,
        st.plotly_chart)

    def title(b, *a, **k):
        return o_title(deep_en(b), *a, **k)

    def header(b, *a, **k):
        return o_header(deep_en(b), *a, **k)

    def subheader(b, *a, **k):
        return o_sub(deep_en(b), *a, **k)

    def markdown(b, *a, **k):
        if isinstance(b, str) and get_lang() == "en":
            b = b.replace("dir='rtl'", "dir='ltr'").replace('dir="rtl"', 'dir="ltr"')
        return o_md(deep_en(b), *a, **k)

    def text(b, *a, **k):
        return o_text(deep_en(b), *a, **k)

    def caption(b, *a, **k):
        return o_cap(deep_en(b), *a, **k)

    def info(b, *a, **k):
        return o_info(deep_en(b), *a, **k)

    def warning(b, *a, **k):
        return o_warn(deep_en(b), *a, **k)

    def success(b, *a, **k):
        return o_succ(deep_en(b), *a, **k)

    def error(b, *a, **k):
        return o_err(deep_en(b), *a, **k)

    def metric(label, value="", delta=None, *a, **k):
        return o_metric(deep_en(label), deep_en(value) if isinstance(value, str) else value,
                        deep_en(delta) if isinstance(delta, str) else delta, *a, **k)

    def button(label="OK", *a, **k):
        if k.get("help"):
            k["help"] = deep_en(k["help"])
        return o_btn(deep_en(label), *a, **k)

    def download_button(label="Download", data=None, *a, **k):
        if k.get("help"):
            k["help"] = deep_en(k["help"])
        return o_dbtn(deep_en(label), data, *a, **k)

    def form_submit_button(label="Submit", *a, **k):
        return o_fsb(deep_en(label), *a, **k)

    def link_button(label, *a, **k):
        return o_lbtn(deep_en(label), *a, **k)

    def checkbox(label, *a, **k):
        if k.get("help"):
            k["help"] = deep_en(k["help"])
        return o_cb(deep_en(label), *a, **k)

    def toggle(label, *a, **k):
        if k.get("help"):
            k["help"] = deep_en(k["help"])
        return o_tg(deep_en(label), *a, **k)

    def radio(label, options=(), *a, **k):
        label = deep_en(label)
        if isinstance(options, (list, tuple)):
            fmt = k.get("format_func")
            k["format_func"] = (lambda v: deep_en(str(fmt(v)))) if fmt else (lambda v: deep_en(str(v)))
        if k.get("help"):
            k["help"] = deep_en(k["help"])
        return o_rd(label, options, *a, **k)

    def selectbox(label=" ", options=(), *a, **k):
        label = deep_en(label)
        if isinstance(options, (list, tuple)):
            fmt = k.get("format_func")
            k["format_func"] = (lambda v: deep_en(str(fmt(v)))) if fmt else (lambda v: deep_en(str(v)))
        if k.get("help"):
            k["help"] = deep_en(k["help"])
        return o_sb(label, options, *a, **k)

    def multiselect(label=" ", options=(), *a, **k):
        label = deep_en(label)
        if isinstance(options, (list, tuple)):
            fmt = k.get("format_func")
            k["format_func"] = (lambda v: deep_en(str(fmt(v)))) if fmt else (lambda v: deep_en(str(v)))
        return o_ms(label, options, *a, **k)

    def select_slider(label=" ", options=(), *a, **k):
        label = deep_en(label)
        if isinstance(options, (list, tuple)):
            fmt = k.get("format_func")
            k["format_func"] = (lambda v: deep_en(str(fmt(v)))) if fmt else (lambda v: deep_en(str(v)))
        if k.get("help"):
            k["help"] = deep_en(k["help"])
        return o_ssl(label, options, *a, **k)

    def slider(label, *a, **k):
        if k.get("help"):
            k["help"] = deep_en(k["help"])
        return o_sl(deep_en(label), *a, **k)

    def number_input(label=" ", *a, **k):
        if k.get("help"):
            k["help"] = deep_en(k["help"])
        return o_ni(deep_en(label), *a, **k)

    def text_input(label=" ", *a, **k):
        if k.get("help"):
            k["help"] = deep_en(k["help"])
        if k.get("placeholder"):
            k["placeholder"] = deep_en(k["placeholder"])
        return o_ti(deep_en(label), *a, **k)

    def text_area(label=" ", *a, **k):
        if k.get("help"):
            k["help"] = deep_en(k["help"])
        if k.get("placeholder"):
            k["placeholder"] = deep_en(k["placeholder"])
        return o_ta(deep_en(label), *a, **k)

    def file_uploader(label=" ", *a, **k):
        if k.get("help"):
            k["help"] = deep_en(k["help"])
        return o_fu(deep_en(label), *a, **k)

    def expander(label, *a, **k):
        return o_ex(deep_en(label), *a, **k)

    def tabs(labels, *a, **k):
        if isinstance(labels, (list, tuple)):
            labels = [deep_en(x) if isinstance(x, str) else x for x in labels]
        return o_tabs(labels, *a, **k)

    def spinner(text="Loading…", *a, **k):
        return o_spin(deep_en(text), *a, **k)

    def status(label="Working…", *a, **k):
        return o_status(deep_en(label), *a, **k)

    def toast(body, *a, **k):
        return o_toast(deep_en(body), *a, **k)

    def progress(value, text=None, *a, **k):
        if isinstance(text, str):
            text = deep_en(text)
        return o_prog(value, text=text, *a, **k)

    def dataframe(data=None, *a, **k):
        return o_df(deep_df(data), *a, **k)

    def table(data=None, *a, **k):
        return o_tbl(deep_df(data), *a, **k)

    def plotly_chart(fig=None, *a, **k):
        return o_pc(deep_fig(fig), *a, **k)

    st.title, st.header, st.subheader, st.markdown, st.text = title, header, subheader, markdown, text
    st.caption, st.info, st.warning, st.success, st.error = caption, info, warning, success, error
    st.metric, st.button, st.download_button = metric, button, download_button
    st.form_submit_button, st.link_button = form_submit_button, link_button
    st.checkbox, st.toggle, st.radio = checkbox, toggle, radio
    st.selectbox, st.multiselect, st.select_slider, st.slider = selectbox, multiselect, select_slider, slider
    st.number_input, st.text_input, st.text_area, st.file_uploader = number_input, text_input, text_area, file_uploader
    st.expander, st.tabs, st.spinner, st.status = expander, tabs, spinner, status
    st.toast, st.progress, st.dataframe, st.table, st.plotly_chart = toast, progress, dataframe, table, plotly_chart

    # --- کانتینرها (st.columns / st.sidebar) — متدهای زنجیره‌ای مثل c1.metric()
    o_columns = st.columns
    o_sidebar = st.sidebar

    class _ColProxy:
        """پروکسی کانتینر: متدهای نمایشی ترجمه می‌شوند، بقیه عیناً پاس می‌شوند."""

        def __init__(self, o):
            object.__setattr__(self, "_o", o)

        def __enter__(self):
            self._o.__enter__()
            return self

        def __exit__(self, *a):
            return self._o.__exit__(*a)

        def __getattr__(self, name):
            return getattr(object.__getattribute__(self, "_o"), name)

        def __iter__(self):
            return iter(type(self)(c) for c in self._o)

        def __getitem__(self, i):
            return type(self)(self._o[i])

        def title(self, b, *a, **k):
            return self._o.title(deep_en(b), *a, **k)

        def header(self, b, *a, **k):
            return self._o.header(deep_en(b), *a, **k)

        def subheader(self, b, *a, **k):
            return self._o.subheader(deep_en(b), *a, **k)

        def markdown(self, b, *a, **k):
            if isinstance(b, str) and get_lang() == "en":
                b = b.replace("dir='rtl'", "dir='ltr'").replace('dir="rtl"', 'dir="ltr"')
            return self._o.markdown(deep_en(b), *a, **k)

        def text(self, b, *a, **k):
            return self._o.text(deep_en(b), *a, **k)

        def caption(self, b, *a, **k):
            return self._o.caption(deep_en(b), *a, **k)

        def info(self, b, *a, **k):
            return self._o.info(deep_en(b), *a, **k)

        def warning(self, b, *a, **k):
            return self._o.warning(deep_en(b), *a, **k)

        def success(self, b, *a, **k):
            return self._o.success(deep_en(b), *a, **k)

        def error(self, b, *a, **k):
            return self._o.error(deep_en(b), *a, **k)

        def metric(self, label, value="", delta=None, *a, **k):
            return self._o.metric(
                deep_en(label), deep_en(value) if isinstance(value, str) else value,
                deep_en(delta) if isinstance(delta, str) else delta, *a, **k)

        def button(self, label="OK", *a, **k):
            return self._o.button(deep_en(label), *a, **k)

        def download_button(self, label="Download", data=None, *a, **k):
            return self._o.download_button(deep_en(label), data, *a, **k)

        def form_submit_button(self, label="Submit", *a, **k):
            return self._o.form_submit_button(deep_en(label), *a, **k)

        def checkbox(self, label, *a, **k):
            return self._o.checkbox(deep_en(label), *a, **k)

        def toggle(self, label, *a, **k):
            return self._o.toggle(deep_en(label), *a, **k)

        def radio(self, label, options=(), *a, **k):
            if isinstance(options, (list, tuple)):
                fmt = k.get("format_func")
                k["format_func"] = (lambda v: deep_en(str(fmt(v)))) if fmt else (lambda v: deep_en(str(v)))
            return self._o.radio(deep_en(label), options, *a, **k)

        def selectbox(self, label=" ", options=(), *a, **k):
            if isinstance(options, (list, tuple)):
                fmt = k.get("format_func")
                k["format_func"] = (lambda v: deep_en(str(fmt(v)))) if fmt else (lambda v: deep_en(str(v)))
            return self._o.selectbox(deep_en(label), options, *a, **k)

        def select_slider(self, label=" ", options=(), *a, **k):
            if isinstance(options, (list, tuple)):
                fmt = k.get("format_func")
                k["format_func"] = (lambda v: deep_en(str(fmt(v)))) if fmt else (lambda v: deep_en(str(v)))
            return self._o.select_slider(deep_en(label), options, *a, **k)

        def slider(self, label, *a, **k):
            return self._o.slider(deep_en(label), *a, **k)

        def number_input(self, label=" ", *a, **k):
            return self._o.number_input(deep_en(label), *a, **k)

        def text_input(self, label=" ", *a, **k):
            if k.get("placeholder"):
                k["placeholder"] = deep_en(k["placeholder"])
            return self._o.text_input(deep_en(label), *a, **k)

        def text_area(self, label=" ", *a, **k):
            if k.get("placeholder"):
                k["placeholder"] = deep_en(k["placeholder"])
            return self._o.text_area(deep_en(label), *a, **k)

        def file_uploader(self, label=" ", *a, **k):
            return self._o.file_uploader(deep_en(label), *a, **k)

        def expander(self, label, *a, **k):
            return self._o.expander(deep_en(label), *a, **k)

        def tabs(self, labels, *a, **k):
            if isinstance(labels, (list, tuple)):
                labels = [deep_en(x) if isinstance(x, str) else x for x in labels]
            return self._o.tabs(labels, *a, **k)

        def progress(self, value, text=None, *a, **k):
            if isinstance(text, str):
                text = deep_en(text)
            return self._o.progress(value, text=text, *a, **k)

    st.columns = lambda *a, **k: [_ColProxy(c) for c in o_columns(*a, **k)]
    st.sidebar = _ColProxy(o_sidebar)
    setattr(st, _PATCHED_FLAG, True)


# ===========================================================================
# منوی چندزبانه‌ی صفحات (جایگزین منوی پیش‌فرض Streamlit)
# ===========================================================================
NAV_PAGES: list[tuple[str, str, str, str, str]] = [
    # (page_id, path, icon, fa, en)
    ("main", "app.py", "🏠", "داشبورد", "Dashboard"),
    ("p1", "pages/1_Live_Prices.py", "📊", "قیمت‌های زنده بازار", "Live Prices"),
    ("p2", "pages/2_Live_Trading.py", "💹", "ترید مستقیم", "Live Trading"),
    ("p3", "pages/3_Agents_Duel.py", "🤖", "دوئل ایجنت‌ها", "Agents Duel"),
]

_HIDE_NAV_CSS = (
    "<style>[data-testid='stSidebarNav']{display:none !important;}</style>"
)


def nav_menu(current: str = "main") -> None:
    """منوی صفحه‌ها با برچسب ترجمه‌شده — روی همه‌ی صفحه‌ها یکسان رندر می‌شود."""
    st.markdown(_HIDE_NAV_CSS, unsafe_allow_html=True)
    with st.sidebar:
        for pid, path, ico, fa, en in NAV_PAGES:
            label = f"{ico} {tr(fa, en)}"
            if pid == current:
                st.button(label, key=f"nq_nav_{pid}", disabled=True,
                          type="primary", use_container_width=True)
            elif st.button(label, key=f"nq_nav_{pid}", use_container_width=True):
                try:
                    st.switch_page(path)
                except Exception as e:  # noqa: BLE001
                    st.error(f"Navigation failed ({e}) — use the page list in the sidebar.")


def language_switcher(sidebar: bool = True) -> str:
    """ویجت انتخاب زبان. بعد از تغییر، خودش اپ را rerun می‌کند."""
    container = st.sidebar if sidebar else st
    options = list(LANG_LABELS.keys())
    current = get_lang()
    choice = container.selectbox(
        tr("زبان", "Language"),
        options=options,
        index=options.index(current),
        format_func=lambda code: LANG_LABELS[code],
        key="i18n_lang_selectbox",
    )
    if choice != current:
        set_lang(choice)
        st.rerun()
    return get_lang()


def apply_direction() -> None:
    """با فارسی راست‌به‌چپ، با انگلیسی چپ‌به‌راست — روی کل اپ."""
    rtl = is_rtl()
    direction = "rtl" if rtl else "ltr"
    align = "right" if rtl else "left"
    st.markdown(
        f"""
        <style>
            .stApp, [data-testid="stSidebar"] {{
                direction: {direction};
                text-align: {align};
            }}
            .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
            .stMarkdown, [data-testid="stMarkdownContainer"], label {{
                direction: {direction};
                text-align: {align};
            }}
            [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
                text-align: {align};
            }}
            [data-testid="stMetric"], [data-testid="stMetricLabel"],
            [data-testid="stMetricValue"], [data-testid="stDataFrame"] {{
                direction: ltr;
            }}
            [data-testid="stSidebar"] * {{ direction: {direction}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def setup_i18n(sidebar: bool = True, page: str = "main") -> str:
    """یک‌خطی برای شروع هر صفحه:
    پچ ترجمه + انتخاب‌گر زبان + منوی صفحه‌ها + چیدمان RTL/LTR."""
    _patch_display_widgets()
    language_switcher(sidebar=sidebar)
    nav_menu(page)
    apply_direction()
    return get_lang()


def missing_keys() -> Dict[str, set]:
    """کلیدهایی که در برخی زبان‌ها نیستند (برای t())."""
    all_keys = set()
    for table in TRANSLATIONS.values():
        all_keys.update(table.keys())
    return {
        lang: all_keys - set(table.keys())
        for lang, table in TRANSLATIONS.items()
        if all_keys - set(table.keys())
    }
