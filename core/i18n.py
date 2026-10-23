# -*- coding: utf-8 -*-
"""
core/i18n.py — سیستم دوزبانه (فارسی/انگلیسی) برای اپ Streamlit
===============================================================
بدون هیچ وابستگی و هزینه اضافه — فقط streamlit.
"""

from __future__ import annotations

from typing import Dict, Optional

import streamlit as st

LANG_KEY = "app_lang"
DEFAULT_LANG = "fa"

LANG_LABELS: Dict[str, str] = {"fa": "فارسی", "en": "English"}

# ---------------------------------------------------------------------------
# دیکشنری ترجمه — متن‌های تکراری اپ
# ---------------------------------------------------------------------------
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "fa": {
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
        "sec_overview": "نمای کلی",
        "sec_indicators": "اندیکاتورها",
        "sec_confluence": "کانفلوئنس (هم‌راستایی سیگنال‌ها)",
        "sec_triple_tp": "حد سود سه‌گانه",
        "sec_gaps": "گپ‌ها (FVG/BVG)",
        "sec_community": "برد تحلیل‌های اجتماعی",
        "sec_scanner": "اسکنر بازار",
        "strong_buy": "خرید قوی",
        "buy": "خرید",
        "neutral": "بی‌طرف",
        "sell": "فروش",
        "strong_sell": "فروش قوی",
        "entry": "نقطه ورود",
        "stop_loss": "حد ضرر",
        "take_profit": "حد سود",
        "tp1": "حد سود اول",
        "tp2": "حد سود دوم",
        "tp3": "حد سود سوم",
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
        "sec_overview": "Overview",
        "sec_indicators": "Indicators",
        "sec_confluence": "Confluence (signal alignment)",
        "sec_triple_tp": "Triple Take-Profit",
        "sec_gaps": "Gaps (FVG/BVG)",
        "sec_community": "Community Analysis Board",
        "sec_scanner": "Market Scanner",
        "strong_buy": "Strong Buy",
        "buy": "Buy",
        "neutral": "Neutral",
        "sell": "Sell",
        "strong_sell": "Strong Sell",
        "entry": "Entry",
        "stop_loss": "Stop Loss",
        "take_profit": "Take Profit",
        "tp1": "First Take-Profit",
        "tp2": "Second Take-Profit",
        "tp3": "Third Take-Profit",
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
    """با فارسی راست‌به‌چپ، با انگلیسی چپ‌به‌راست."""
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
    """یک‌خطی برای شروع: انتخاب‌گر زبان + پچ ترجمه + چیدمان."""
    _patch_display_widgets()
    lang = language_switcher(sidebar=sidebar)
    apply_direction()
    return lang


def missing_keys() -> Dict[str, set]:
    """کلیدهایی که در برخی زبان‌ها نیستند."""
    all_keys = set()
    for table in TRANSLATIONS.values():
        all_keys.update(table.keys())
    return {
        lang: all_keys - set(table.keys())
        for lang, table in TRANSLATIONS.items()
        if all_keys - set(table.keys())
    }


# ---------------------------------------------------------------------------
# ترجمه‌ی خودکار ویجت‌های نمایشی — فقط «نمایش» عوض می‌شود؛ مقادیر و منطق دست‌نخورده.
# ---------------------------------------------------------------------------
_PATCHED_FLAG = "_nq_display_patched"

_SUBHEADER_EN = {
    "◈ پوسته مدل‌ها (Neural Shell) — زنده · با FVG / BVG": "◈ Neural Shell — live · with FVG / BVG",
    "◈ دفتر ایجنت‌ها (The Agents) — بک‌تست زنده": "◈ The Agents — live backtest",
    "🎯 طرح معامله — ستاپ اعتبارسنجی‌شده (walk-forward روی همین نماد)": "🎯 Trade Plan — validated setup (walk-forward on this symbol)",
    "🟪 نواحی FVG / BVG (عدم تعادل پر نشده)": "🟪 FVG / BVG zones (unfilled imbalance)",
    "🧱 حمایت و مقاومت (سوئینگ)": "🧱 Support & Resistance",
    "📜 رویدادهای ورود/خروج همگرایی": "📜 Confluence entry/exit events",
    "📈 روند امتیاز همگرایی (۱۲۰ کندل اخیر)": "📈 Confluence score trend (last 120 candles)",
    "◈ ماتریس لبه (Edge Matrix) — همبستگی سیگنال با بازده بعدی": "◈ Edge Matrix — signal vs next-bar return",
    "💎 فرصت‌های سودده — اسکن زنده‌ی بازار (خودکار)": "💎 Profit Opportunities — live market scan (auto)",
    "🚀 بیشترین سود ۲۴س": "🚀 Top Gainers 24h",
    "🩸 بیشترین ریزش ۲۴س": "🩸 Top Losers 24h",
    "💧 بیشترین حجم": "💧 Top Volume",
    "🧑‍💻 تحلیل‌ها — ثبت تحلیل شخصی · تصویر تحلیل · تحلیل‌های کاربران": "🧑‍💻 Analyses — Post · Image · Community",
    "✍️ ثبت تحلیل شخصی": "✍️ Post Your Analysis",
    "📚 منابع داده (مستندات رسمی)": "📚 Data Sources (official docs)",
    "👥 تحلیل‌های کاربران": "👥 Community Analyses",
}

_TABS_EN = {
    "✍️ ثبت تحلیل شخصی": "✍️ Post Your Analysis",
    "🖼️ تصویر تحلیل": "🖼️ Chart Image",
    "👥 تحلیل‌های کاربران": "👥 Community Analyses",
}

_BUTTON_EN = {
    "🔄 بازخوانی": "🔄 Refresh",
}

_CAPTION_EN = {
    "تحلیل‌هایی که کاربران ثبت کرده‌اند. برای ثبت تحلیل خودت → تب «✍️ ثبت تحلیل شخصی».": "Analyses posted by the community. To post yours → the «✍️ Post Your Analysis» tab.",
}

_INFO_EN = {
    "هنوز تحلیلی ثبت نشده. اولین نفر باش! (تب → ✍️ ثبت تحلیل شخصی)": "No analyses yet. Be the first! (tab → ✍️ Post Your Analysis)",
}

_HEADER_EN = {
    "⚙️ تنظیمات": "⚙️ Settings",
}

_RADIO_LABEL_EN = {
    "بخش‌ها": "Sections",
}

_SECTION_VALUE_EN = {
    "📊 تحلیل زنده": "📊 Live Analysis",
    "💎 فرصت‌های سودده": "💎 Profit Opportunities",
    "🧑‍💻 تحلیل‌ها (ثبت · تصویر · کاربران)": "🧑‍💻 Analyses (Post · Image · Users)",
    "🏆 برترین‌ها": "🏆 Top Movers",
    "📰 اخبار": "📰 News",
    "📚 منابع داده": "📚 Data Sources",
}

_EXPANDER_EN = {
    "🏦 بازار و نماد": "🏦 Market & Symbol",
    "🎨 شخصی‌سازی ظاهر": "🎨 Appearance",
}

_TEXTINPUT_EN = {
    "نام یا نام مستعار *": "Name or alias *",
    "نماد ارز *": "Symbol *",
    "نماد برای تصویر": "Symbol for image",
    "نماد": "Symbol",
    "نام یا شناسه‌ی صرافی": "Exchange name or id",
    "لینک تصویر پس‌زمینه (اختیاری)": "Background image URL (optional)",
}

_HELP_EN = {
    "مثل BTC-USDT یا gramusdt · برای Lighter فقط BTC": "e.g. BTC-USDT or gramusdt · Lighter supports BTC only",
    "هر صرافیِ CCXT: kraken، coinbase، gate، mexc، bitget، htx، xt، lbank، …": "Any CCXT venue: kraken, coinbase, gate, mexc, bitget, htx, xt, lbank, …",
    "کمتر = کندل‌ها بازتر و درشت‌تر · بیشتر = فشرده‌تر": "Lower = wider candles · Higher = more compressed",
    "آدرس یک عکس بگذار تا پس‌زمینه‌ی دلخواهت شود.": "Paste an image URL to use it as your background.",
}

_NUMBERINPUT_EN = {
    "قیمت ورود": "Entry price",
    "حد ضرر (SL)": "Stop loss (SL)",
    "هدف ۱ (TP1)": "Target 1 (TP1)",
    "هدف ۲ (TP2)": "Target 2 (TP2)",
    "هدف ۳ (TP3)": "Target 3 (TP3)",
}

_TEXTAREA_EN = {
    "شرح تحلیل و دلیل *": "Analysis description & rationale *",
}

_FILEUPLOADER_EN = {
    "📷 عکس چارت/تحلیل (اختیاری)": "📷 Chart/analysis image (optional)",
}

_SUBMIT_EN = {
    "📨 ثبت و اشتراک‌گذاری تحلیل": "📨 Post & share analysis",
}

_CHECKBOX_EN = {
    "🟪 نمایش نواحی FVG / BVG روی چارت": "🟪 Show FVG / BVG zones on chart",
    "🔴 حالت زنده (قیمت لحظه‌ای)": "🔴 Live mode (real-time price)",
}

_SLIDER_EN = {
    "تعداد کندل روی چارت (فشرده/باز)": "Candles on chart (compact/wide)",
}

_SELECTBOX_LABEL_EN = {
    "صرافی": "Exchange",
    "تایم‌فریم": "Timeframe",
    "تم رنگی": "Color theme",
    "فیلتر نماد": "Filter symbol",
    "فیلتر جهت": "Filter side",
    "جهت *": "Side *",
}

_SELECTBOX_VALUE_EN = {
    "همه": "All",
    "لانگ 🟢": "Long 🟢",
    "شورت 🔴": "Short 🔴",
    "خنثی ⚪": "Neutral ⚪",
    "➕ صرافی دیگر (CCXT)": "➕ More exchanges (CCXT)",
    "سایر": "Other",
    "🌌 شب کهکشانی": "🌌 Galaxy Night",
    "🌊 اقیانوس عمیق": "🌊 Deep Ocean",
    "🌿 جنگل تاریک": "🌿 Dark Forest",
    "🔥 غروب آتشین": "🔥 Fire Sunset",
    "👑 سلطنتی بنفش": "👑 Royal Purple",
    "☀️ روشن مینیمال": "☀️ Light Minimal",
    "🖤 تک‌رنگ تیره": "🖤 Dark Mono",
}

_MARKDOWN_EN = {
    "**📈 تنظیمات چارت**": "**📈 Chart Settings**",
}


def _en_maybe(s, table):
    if get_lang() == "en" and isinstance(s, str):
        return table.get(s, s)
    return s


def _patch_display_widgets() -> None:
    """پوشش ویجت‌های نمایشی برای ترجمه (idempotent) — بدون تغییر مقادیر/منطق."""
    if getattr(st, _PATCHED_FLAG, False):
        return
    (o_sub, o_tabs, o_btn, o_cap, o_info, o_ti, o_ni, o_ta, o_fu, o_fsb,
     o_sb, o_hd, o_rd, o_ex, o_cb, o_sl, o_md) = (
        st.subheader, st.tabs, st.button, st.caption, st.info,
        st.text_input, st.number_input, st.text_area, st.file_uploader,
        st.form_submit_button, st.selectbox, st.header, st.radio,
        st.expander, st.checkbox, st.slider, st.markdown)

    def subheader(body, *a, **k):
        return o_sub(_en_maybe(body, _SUBHEADER_EN), *a, **k)

    def tabs(labels, *a, **k):
        if get_lang() == "en" and isinstance(labels, (list, tuple)):
            labels = [_TABS_EN.get(x, x) if isinstance(x, str) else x for x in labels]
        return o_tabs(labels, *a, **k)

    def button(label, *a, **k):
        if get_lang() == "en" and isinstance(label, str):
            label = _BUTTON_EN.get(label, label)
        return o_btn(label, *a, **k)

    def header(body, *a, **k):
        return o_hd(_en_maybe(body, _HEADER_EN), *a, **k)

    def radio(label, options=(), *a, **k):
        if get_lang() == "en":
            if isinstance(label, str):
                label = _RADIO_LABEL_EN.get(label, label)
            if not k.get("format_func") and isinstance(options, (list, tuple)):
                k["format_func"] = lambda v: _SECTION_VALUE_EN.get(v, v)
        return o_rd(label, options, *a, **k)

    def expander(label, *a, **k):
        return o_ex(_en_maybe(label, _EXPANDER_EN), *a, **k)

    def text_input(label=" ", *a, **k):
        if get_lang() == "en" and isinstance(label, str):
            label = _TEXTINPUT_EN.get(label, label)
            if k.get("help"):
                k["help"] = _HELP_EN.get(k["help"], k["help"])
        return o_ti(label, *a, **k)

    def number_input(label=" ", *a, **k):
        return o_ni(_en_maybe(label, _NUMBERINPUT_EN), *a, **k)

    def text_area(label=" ", *a, **k):
        return o_ta(_en_maybe(label, _TEXTAREA_EN), *a, **k)

    def file_uploader(label=" ", *a, **k):
        return o_fu(_en_maybe(label, _FILEUPLOADER_EN), *a, **k)

    def form_submit_button(label="Submit", *a, **k):
        return o_fsb(_en_maybe(label, _SUBMIT_EN), *a, **k)

    def checkbox(label, *a, **k):
        return o_cb(_en_maybe(label, _CHECKBOX_EN), *a, **k)

    def slider(label, *a, **k):
        if get_lang() == "en" and isinstance(label, str):
            label = _SLIDER_EN.get(label, label)
            if k.get("help"):
                k["help"] = _HELP_EN.get(k["help"], k["help"])
        return o_sl(label, *a, **k)

    def selectbox(label=" ", options=(), *a, **k):
        if get_lang() == "en":
            if isinstance(label, str):
                label = _SELECTBOX_LABEL_EN.get(label, label)
            if not k.get("format_func") and isinstance(options, (list, tuple)):
                k["format_func"] = lambda v: _SELECTBOX_VALUE_EN.get(v, v)
        return o_sb(label, options, *a, **k)

    def caption(body, *a, **k):
        if get_lang() == "en" and isinstance(body, str):
            if body in _CAPTION_EN:
                body = _CAPTION_EN[body]
            elif body.startswith("نسخه:"):
                body = "Version:" + body[len("نسخه:"):]
            elif body.startswith("نمونه‌ها:"):
                body = "Examples:" + body[len("نمونه‌ها:"):]
        return o_cap(body, *a, **k)

    def info(body, *a, **k):
        return o_info(_en_maybe(body, _INFO_EN), *a, **k)

    def markdown(body, *a, **k):
        # فقط رشته‌های کوتاه متنی (بدون HTML) ترجمه می‌شوند
        if (get_lang() == "en" and isinstance(body, str) and len(body) < 120
                and "<" not in body and body in _MARKDOWN_EN):
            body = _MARKDOWN_EN[body]
        return o_md(body, *a, **k)

    st.subheader, st.tabs, st.button, st.caption, st.info = subheader, tabs, button, caption, info
    st.text_input, st.number_input, st.text_area = text_input, number_input, text_area
    st.file_uploader, st.form_submit_button, st.selectbox = file_uploader, form_submit_button, selectbox
    st.header, st.radio, st.expander, st.checkbox, st.slider, st.markdown = (
        header, radio, expander, checkbox, slider, markdown)
    setattr(st, _PATCHED_FLAG, True)
