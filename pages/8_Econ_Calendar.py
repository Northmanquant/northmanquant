"""تقویم اقتصادی آمریکا — فقط منابع رسمی (BLS/BEA) — پورت از TITAN
زمان‌بندی انتشار CPI، NFP، PPI، GDP و… با ترجمه‌ی فارسی؛ نه هیچ تاریخِ حدسی."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from core import econ_calendar as EC
from core.i18n import get_lang, setup_i18n, tr

st.set_page_config(page_title="تقویم اقتصادی | Economic Calendar", page_icon="🗓️", layout="wide")
LANG = setup_i18n(page="p8")

TEHRAN = timezone(timedelta(hours=3, minutes=30))   # ایران: UTC+3:30 ثابت (بدون ساعت تابستانی)

_FA_MONTHS = {1: "ژانویه", 2: "فوریه", 3: "مارس", 4: "آوریل", 5: "مه", 6: "ژوئن",
              7: "ژوئیه", 8: "اوت", 9: "سپتامبر", 10: "اکتبر", 11: "نوامبر", 12: "دسامبر"}

# گزینه‌های ماه: ماهِ گذشته + جاری + ۱۱ ماهِ پیشِ رو (بر پایه‌ی تهران)
_now_teh = datetime.now(timezone.utc).astimezone(TEHRAN)
_MONTH_OPTS = []
for shift in (-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11):
    y, m = _now_teh.year, _now_teh.month + shift
    while m > 12:
        m, y = m - 12, y + 1
    while m < 1:
        m, y = m + 12, y - 1
    _MONTH_OPTS.append(f"{y:04d}-{m:02d}")


def _month_label(mkey: str) -> str:
    m = int(mkey[5:7])
    return f"{mkey} · {_EN_MONTHS[m]}" if LANG == "en" else f"{mkey} · {_FA_MONTHS[m]}"


_EN_MONTHS = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
              7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"}


@st.cache_data(ttl=3600, show_spinner=False)
def _cal(month: str) -> dict:
    return EC.calendar(month)


st.title("🗓️ " + tr("تقویم اقتصادی آمریکا", "US Economic Calendar"))
st.caption(tr(
    "زمان‌بندی رسمی انتشار آمار بزرگ آمریکا (CPI، اشتغال/NFP، PPI، GDP و…) مستقیم از فایل‌های تقویمِ "
    "BLS و BEA — نه هیچ تقویم سومی که تاریخ‌ها را خودش حدس می‌زند. ساعاتِ نمایش به وقت تهران است؛ "
    "این گزارش‌ها بزرگ‌ترین تکان‌دهنده‌های بازار طلا، دلار و فارکس‌اند.",
    "Official release schedule of major US stats (CPI, NFP, PPI, GDP…) straight from the BLS and BEA "
    "calendar files — no third-party calendar that invents dates. Times shown in Tehran time; these "
    "releases are the biggest movers of gold, dollar and forex markets."))

sel = st.selectbox(tr("ماه", "Month"), options=_MONTH_OPTS,
                   index=1, format_func=_month_label)
only_key = st.toggle(tr("فقط رویدادهای کلیدی بازار", "Key market movers only"),
                     value=False,
                     help=tr("رویدادهایی با ترجمه‌ی فارسی: CPI، NFP، PPI، JOLTS، ECI، PCE و GDP.",
                             "Events with Persian labels: CPI, NFP, PPI, JOLTS, ECI, PCE, GDP."))

data = _cal(sel)

# ---------------------------------------------------------------------------
for g in data["groups"].values():
    st.subheader("📅 " + (g["name_fa"] if LANG != "en" else
                  ("BLS — US Bureau of Labor Statistics" if g["key"] == "bls"
                   else "BEA — US Bureau of Economic Analysis")))
    if g["error"]:
        st.warning(tr(
            f"این منبع الان پاسخ نداد ({g['error']}) — چند دقیقه بعد دوباره تلاش کن؛ تقویم منبع دیگر پایین همان صفحه سالم است. "
            f"مطمئن‌ترین مرجع همیشه صفحه‌ی رسمی: {g['public_url']}",
            f"This source did not answer just now ({g['error']}) — retry in a few minutes; the other source below may still work. "
            f"The always-authoritative reference is the official page: {g['public_url']}"))
        continue
    events = g["data"]
    if only_key:
        events = [e for e in events if e["priority"] == "key"]
    if not events:
        st.info(tr("در این ماه رویدادی در این منبع نیست (یا همه فیلتر شده‌اند).",
                   "No events this month in this source (or all filtered out)."))
        continue
    rows = []
    for e in sorted(events, key=lambda x: x["datetime_utc"] or x["datetime_local"]):
        when = e["tehran"] if e["tz_exact"] else ""
        local = e["datetime_local"].replace("T", " ")[:16]
        if e["all_day"]:
            when_s = tr("کل روز", "all day")
        elif when:
            when_s = when
        else:
            when_s = f"{local} ({e['zone']})"
        title = e["title_fa"] if (e["title_fa"] and LANG != "en") else e["title"]
        rows.append({
            "🔑": "🔑" if e["priority"] == "key" else "•",
            tr("زمان تهران", "Tehran time"): when_s,
            tr("رویداد", "Event"): title,
            tr("زمان محلی ناشر", "Publisher local time"): "" if e["all_day"] else f"{local} ({e['zone']})",
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    # صداقت درباره‌ی مسیر داده: زنده / آینه / اسنپ‌شات
    if g.get("via") == "snapshot":
        st.caption(tr(
            f"📦 این گروه از **اسنپ‌شات محلیِ** فایل رسمی نمایش داده می‌شود (تاریخ اسنپ‌شات: {g.get('snapshot_date') or '؟'}) "
            f"— سرور زنده به منبع دسترسی نداشت؛ برای تازگیِ روزِ انتشار، صفحه‌ی رسمی را چک کن: {g['public_url']}",
            f"📦 This section comes from the **local snapshot** of the official file (snapshot date: {g.get('snapshot_date') or '?'}) "
            f"— the live source was unreachable; for exact release-day freshness check the official page: {g['public_url']}"))
    elif g.get("via") == "mirror":
        st.caption(tr(
            "🪞 داده از **آینه‌ی رسمی** همان فایل تقویم خوانده شد (سرور مستقیم بسته بود) — محتوا همان خروجی رسمی ناشر است.",
            "🪞 Data was read from an **official mirror** of the same calendar file (direct server was blocked) — content is the publisher's official output."))
    cap = ""
    if g["coverage_start"]:
        cap = tr(f"بازه‌ی کامل تقویم این منبع: {g['coverage_start']} تا {g['coverage_end']}",
                 f"Full calendar range of this source: {g['coverage_start']} to {g['coverage_end']}")
    st.caption((cap + " · " if cap else "")
               + f"{len(events)} " + tr("رویداد در این ماه", "events this month"))

# ---------------------------------------------------------------------------
st.warning(tr(
    "⚠️ فقط زمان‌بندی رسمی انتشار است — نه پیش‌بینی عدد و نه سیگنال معامله. تاریخ و ساعت را ناشر ممکن است عوض کند؛ "
    "قبل از خبر مهم، صفحه‌ی رسمی منبع را چک کن. تقویم همه‌ی کشورها نیست و داده‌ی لحظه‌ای بازار هم نیست.",
    "⚠️ This is only the official release schedule — not a forecast and not a trading signal. Publishers may change dates/times; "
    "check the source's official page before an important release. Not an all-country calendar and not live market data."),
)
