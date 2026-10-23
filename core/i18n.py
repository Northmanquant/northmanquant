# -*- coding: utf-8 -*-
"""
core/i18n.py — سیستم دوزبانه (فارسی/انگلیسی) برای اپ Streamlit
===============================================================
بدون هیچ وابستگی و هزینه اضافه — فقط streamlit.

راه‌اندازی سریع در app_base.py:

    from core.i18n import setup_i18n, t, tr

    # داخل main()، درست بعد از st.set_page_config(...):
    setup_i18n(sidebar=True)          # انتخاب‌گر زبان + چیدمان RTL/LTR

    # هر متن را به این شکل دوزبانه کن (تدریجی، فایل به فایل):
    st.title(tr("تحلیل تکنیکال چندسطحی", "Multi-Level Technical Analysis"))
"""

from __future__ import annotations

from typing import Dict, Optional

import streamlit as st

LANG_KEY = "app_lang"
DEFAULT_LANG = "fa"

LANG_LABELS: Dict[str, str] = {"fa": "فارسی", "en": "English"}

# ---------------------------------------------------------------------------
# دیکشنری ترجمه — متن‌های تکراری اپ (منو، دکمه‌ها، عنوان بخش‌ها، وضعیت‌ها)
# برای افزودن زبان جدید فقط یک بلاک جدید با همان کلیدها اضافه کنید.
# ---------------------------------------------------------------------------
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "fa": {
        # عمومی
        "app_title": "تحلیل تکنیکال چندسطحی",
        "app_subtitle": "سیگنال ترکیبی با کانفلوئنس، حد سود سه‌گانه و مدیریت ریسک",
        "settings": "پنل تنظیمات",
        "language": "زبان",
        "symbol": "نماد",
        "timeframe": "تایم‌فریم",
        "analyze": "تحلیل کن",
        "refresh": "بروزرسانی",
        "save": "ذخیره",
        "cancel": "انصراف",
        "search": "جستجو",
        "filter": "فیلتر",
        "close": "بستن",
        "loading": "در حال دریافت داده...",
        "data_error": "خطا در دریافت داده. لطفاً دوباره تلاش کنید.",
        "disclaimer": "این محتوا توصیه سرمایه‌گذاری نیست.",
        # بخش‌ها
        "sec_overview": "نمای کلی",
        "sec_indicators": "اندیکاتورها",
        "sec_confluence": "کانفلوئنس (هم‌راستایی سیگنال‌ها)",
        "sec_triple_tp": "حد سود سه‌گانه",
        "sec_gaps": "گپ‌ها (FVG/BVG)",
        "sec_community": "برد تحلیل‌های اجتماعی",
        "sec_scanner": "اسکنر بازار",
        # سیگنال‌ها
        "strong_buy": "خرید قوی",
        "buy": "خرید",
        "neutral": "بی‌طرف",
        "sell": "فروش",
        "strong_sell": "فروش قوی",
        # پلن معامله
        "entry": "نقطه ورود",
        "stop_loss": "حد ضرر",
        "take_profit": "حد سود",
        "tp1": "حد سود اول",
        "tp2": "حد سود دوم",
        "tp3": "حد سود سوم",
        "risk_reward": "ریسک به ریوارد",
        "confidence": "درجه اطمینان",
        # برد اجتماعی
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
        # General
        "app_title": "Multi-Level Technical Analysis",
        "app_subtitle": "Combined signals with confluence, triple take-profit and risk management",
        "settings": "Settings Panel",
        "language": "Language",
        "symbol": "Symbol",
        "timeframe": "Timeframe",
        "analyze": "Analyze",
        "refresh": "Refresh",
        "save": "Save",
        "cancel": "Cancel",
        "search": "Search",
        "filter": "Filter",
        "close": "Close",
        "loading": "Fetching data...",
        "data_error": "Data fetch failed. Please try again.",
        "disclaimer": "This content is not investment advice.",
        # Sections
        "sec_overview": "Overview",
        "sec_indicators": "Indicators",
        "sec_confluence": "Confluence (signal alignment)",
        "sec_triple_tp": "Triple Take-Profit",
        "sec_gaps": "Gaps (FVG/BVG)",
        "sec_community": "Community Analysis Board",
        "sec_scanner": "Market Scanner",
        # Signals
        "strong_buy": "Strong Buy",
        "buy": "Buy",
        "neutral": "Neutral",
        "sell": "Sell",
        "strong_sell": "Strong Sell",
        # Trade plan
        "entry": "Entry",
        "stop_loss": "Stop Loss",
        "take_profit": "Take Profit",
        "tp1": "First Take-Profit",
        "tp2": "Second Take-Profit",
        "tp3": "Third Take-Profit",
        "risk_reward": "Risk-Reward",
        "confidence": "Confidence",
        # Community board
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


# ---------------------------------------------------------------------------
# مدیریت زبان جاری
# ---------------------------------------------------------------------------
def get_lang() -> str:
    lang = st.session_state.get(LANG_KEY, DEFAULT_LANG)
    return lang if lang in TRANSLATIONS else DEFAULT_LANG


def set_lang(lang: str) -> None:
    if lang in TRANSLATIONS:
        st.session_state[LANG_KEY] = lang


def is_rtl() -> bool:
    return get_lang() == "fa"


# ---------------------------------------------------------------------------
# دو تابع اصلی ترجمه
# ---------------------------------------------------------------------------
def t(key: str, default: Optional[str] = None) -> str:
    """ترجمه از دیکشنری بر اساس کلید. اگر نبود: default، وگرنه کلید خودش."""
    lang = get_lang()
    table = TRANSLATIONS[lang]
    if key in table:
        return table[key]
    if default is not None:
        return default
    return TRANSLATIONS[DEFAULT_LANG].get(key, key)


def tr(fa_text: str, en_text: Optional[str] = None) -> str:
    """ترجمه درجا: tr("ثبت تحلیل", "Post analysis").

    اگر زبان انگلیسی باشد ولی en_text نداده باشید، متن فارسی برمی‌گردد
    (یعنی می‌توانید فایل را تکه‌تکه انگلیسی کنید، هیچ‌چیز نمی‌شکند).
    """
    if get_lang() == "en":
        return en_text if en_text not in (None, "") else fa_text
    return fa_text


# ---------------------------------------------------------------------------
# ویجت انتخاب زبان + چیدمان RTL/LTR
# ---------------------------------------------------------------------------
def language_switcher(sidebar: bool = True) -> str:
    """لیست انتخاب زبان. بعد از تغییر، خودش اپ را rerun می‌کند."""
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
    """با فارسی، جهت متن‌های اپ راست‌به‌چپ می‌شود؛ با انگلیسی چپ‌به‌راست."""
    direction = "rtl" if is_rtl() else "ltr"
    align = "right" if is_rtl() else "left"
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
        </style>
        """,
        unsafe_allow_html=True,
    )


def setup_i18n(sidebar: bool = True) -> str:
    """یک‌خطی برای شروع: انتخاب‌گر زبان + اعمال چیدمان. خروجی: کد زبان جاری."""
    lang = language_switcher(sidebar=sidebar)
    apply_direction()
    return lang


# ---------------------------------------------------------------------------
# تست داخلی سازگاری دیکشنری‌ها
# ---------------------------------------------------------------------------
def missing_keys() -> Dict[str, set]:
    """کلیدهایی که در برخی زبان‌ها نیستند — برای پاک‌نگه داشتن دیکشنری مفید است."""
    all_keys = set()
    for table in TRANSLATIONS.values():
        all_keys.update(table.keys())
    return {
        lang: all_keys - set(table.keys())
        for lang, table in TRANSLATIONS.items()
        if all_keys - set(table.keys())
    }
