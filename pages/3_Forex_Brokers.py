"""فارکس و بروکرها — قیمت زنده‌ی مِیجرها (یاهو فایننس) + مقایسه‌ی ۵ بروکر معتبر"""
from __future__ import annotations

import time

import streamlit as st
from core import forex as F
from core.i18n import get_lang, setup_i18n, tr

st.set_page_config(page_title="فارکس و بروکرها | Forex & Brokers", page_icon="💱", layout="wide")
lang = setup_i18n(page="p3")

st.title("💱 " + tr("بازار فارکس و معرفی بروکرها", "Forex Market & Broker Guide"))
st.caption(tr(
    "قیمت زنده‌ی جفت‌ارزهای مِیجر از یاهو فایننس (منبع خنثی، میان‌دلالی) + مقایسه‌ی ۵ بروکر معتبر — "
    "قیمت هر بروکر فقط چند پیپ حول همین mid باز می‌شود.",
    "Live major-pair prices from Yahoo Finance (neutral mid-market source) plus a 5-broker "
    "comparison — each broker quotes only a few pips around this mid."))

# ---------------------------------------------------------------------------
# ۱) قیمت زنده‌ی مِیجرها
# ---------------------------------------------------------------------------
st.subheader("🌍 " + tr("قیمت زنده‌ی مِیجرها", "Live Majors"))
c1, c2 = st.columns([1, 2])
with c1:
    refresh = st.select_slider(tr("سرعت بروزرسانی", "Refresh rate"),
                               options=[10, 30, 60], value=30,
                               format_func=lambda x: f"{x} {tr('ثانیه', 'sec')}")
with c2:
    auto = st.checkbox("🔄 " + tr("بروزرسانی خودکار", "Auto refresh"), value=True)
    manual = st.button("🔄 " + tr("دستی آپدیت کن", "Refresh now"))


def _fx_grid(force: bool = False) -> None:
    quotes = F.fx_quotes(force=force)
    st.caption("⏰ " + tr("آخرین به‌روزرسانی", "Last update") + f": {time.strftime('%H:%M:%S')}")
    if not quotes:
        st.error(tr("قیمتی از یاهو گرفته نشد — چند لحظه بعد خودکار دوباره تلاش می‌شود.",
                    "No quotes from Yahoo right now — retrying automatically in a moment."))
        return
    cols = st.columns(len(F.PAIRS))
    for col, (pair, (fa, en)) in zip(cols, F.PAIRS.items()):
        d = quotes.get(pair)
        with col:
            name = en if lang == "en" else fa
            st.metric(label=name, value=F.fmt_price(d["price"]) if d else "—",
                      delta=(f"{d['change_pct']:+.2f}%") if d else None,
                      delta_color="normal" if d else "off")
            st.caption(f"{pair} · " + (tr("۲۴ ساعت", "24h") if d else tr("بدون داده", "no data")))


_fx_grid(force=manual)
if auto and hasattr(st, "fragment"):
    st.fragment(run_every=refresh)(_fx_grid)()

# ---------------------------------------------------------------------------
# ۲) چطور بروکر انتخاب کنیم؟
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("🧭 " + tr("قبل از انتخاب بروکر به این‌ها نگاه کن", "What to check before picking a broker"))
st.info("\n".join([
    "• " + tr("**مدارک نظارتی نهادِ حساب** را چک کن — همان نهادی که پولت نزد اوست مهم است، نه نام بزرگ برند.",
              "Check the **regulation of the exact entity** holding your funds — not just the big brand name."),
    "• " + tr("هزینه واقعی = **اسپرد + کمیسیون** با هم؛ فقط «اسپرد از 0.0» را نبین.",
              "True cost = **spread + commission** together; don't just look at «from 0.0 pips»."),
    "• " + tr("اول **حساب دمو** بگیر و سرعت برداشت را با مبلغ کوچک تست کن.",
              "Start on a **demo**, then test withdrawal speed with a small amount."),
    "• " + tr("اهرم بالا = ریسک بالا؛ اهرمِ نهاد اروپایی/آمریکایی معمولاً محدودتر و امن‌تر است.",
              "High leverage = high risk; EU/US entities cap leverage (safer by design)."),
]))

# ---------------------------------------------------------------------------
# ۳) جدول مقایسه‌ی بروکرها
# ---------------------------------------------------------------------------
st.subheader("🏦 " + tr("مقایسه‌ی ۵ بروکر معتبر فارکس", "Trusted Forex Brokers Compared"))
st.markdown(F.broker_table_html(lang), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# ۴) سلب مسئولیت
# ---------------------------------------------------------------------------
st.warning(tr(
    "⚠️ قیمت‌ها میان‌دلالی یاهو فایننس است و شامل اسپرد بروکرها نیست؛ برای اجرای سفارش به پلتفرم بروکر خودت نگاه کن. "
    "اطلاعات جدول خلاصه و مخصوص معرفی است و ممکن است تغییر کند — قبل از افتتاح حساب از **سایت رسمی بروکر** تأیید بگیر. "
    "معامله با اهرم بالا ریسک از دست دادن کل سرمایه دارد و این صفحه توصیه سرمایه‌گذاری نیست.",
    "⚠️ Prices are Yahoo's mid-market quotes and exclude broker spreads; check your own broker's platform for execution. "
    "The table is a brief introduction and may change — always verify with the **broker's official site** before opening an account. "
    "Leveraged trading risks losing your entire capital; this page is not investment advice."),
)
