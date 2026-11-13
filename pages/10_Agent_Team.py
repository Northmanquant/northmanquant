# -*- coding: utf-8 -*-
"""اتاقِ تیمِ تحلیل 🤝 — چهار عاملِ مستقل، سرِ یک ارز
====================================================
درخواستِ کاربر: یک بخشِ جدا از همه‌چیز — تیمی که سرِ یک ارز جلسه می‌گذارد:
  📰 خبرنگار   → چرا قیمت تکون می‌خورد؟ (تیترِ واقعی + داده)
  👁️ دیدبان    → دنبال حجمِ مشکوک می‌گردد (اسپایک / churn / فشارِ پنهان)
  📊 چارت‌خوان → ورود/حدضرر/اهداف از موتورِ QC-دارِ اپ
  🧐 شکاک      → هر ادعا را محک می‌زند؛ بدونِ دلیل، تاییدی در کار نیست
حکمِ نهایی فقط وقتی «هم‌نظمی» است که شکاک اعتراضِ سخت نداشته باشد."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import team_room as TR
from core.help import hint
from core.i18n import setup_i18n

st.set_page_config(page_title="اتاق تیم | Agent Team", page_icon="🤝", layout="wide")
setup_i18n(page="p10")

st.title("🤝 اتاقِ تیمِ تحلیل — چهار عامل، سرِ یک ارز")
hint("هر عامل مسئولیتِ خودش را دارد و همیشه «مدرک» می‌آورد: خبرنگار می‌گوید حرکت از خبر است یا "
     "از پول؛ دیدبان دنبال حجمِ مشکوک می‌گردد؛ چارت‌خوان فقط از موتورِ QC-دارِ خودِ اپ ورود/خروج "
     "می‌دهد؛ و شکاک ادعای همه را با داده محک می‌زند — اعتراضِ شکاک یعنی معامله ممنوع. "
     "این اتاق از خودِ ارزهای بی‌نام و نقش خبر ندارد؛ هر جلسه روی داده‌ی زنده‌ی صرافی اجرا می‌شود.")

# ----------------------------------------------------------------- کنترل‌ها
QUICK = {"BTC": "BTC-USDT", "ETH": "ETH-USDT", "SOL": "SOL-USDT", "XRP": "XRP-USDT",
         "DOGE": "DOGE-USDT", "AVAX": "AVAX-USDT", "LINK": "LINK-USDT", "TON": "TON-USDT"}
EXCHANGES = ["OKX", "KuCoin"]

c1, c2, c3, c4 = st.columns([1.0, 1.6, 1.0, 1.4])
with c1:
    exchange = st.selectbox("صرافی", EXCHANGES, index=0)
with c2:
    symbol = st.text_input("نماد", value=st.session_state.get("team_symbol", "BTC-USDT"))
with c3:
    interval = st.selectbox("تایم‌فریم", TR.INTERVALS, index=0)
with c4:
    with_news = st.toggle("خبر هم بگیر (RSS واقعی)", value=True)

chips = st.columns(len(QUICK))
for i, (k, sym) in enumerate(QUICK.items()):
    if chips[i].button(k, key=f"team_{k}", use_container_width=True):
        st.session_state["team_symbol"] = sym
        st.rerun()

if st.button("🎙 شروعِ جلسه‌ی تیم", type="primary", use_container_width=True):
    st.session_state["team_symbol"] = symbol
    with st.spinner("عامل‌ها سرِ کارند — داده‌ی زنده + خبر + بازرسیِ شکاک…"):
        st.session_state["team_room"] = TR.investigate(
            exchange=exchange, symbol=symbol, interval=interval, with_news=with_news)
    st.rerun()

room: dict | None = st.session_state.get("team_room")

# ----------------------------------------------------------------- خروجی
if not room:
    st.info("نماد را انتخاب کن و «شروعِ جلسه‌ی تیم» را بزن — چهار عامل با هم سرِ همان ارز جلسه می‌گذارند.")
    st.stop()

if not room.get("ok"):
    st.error(f"⚠️ {room.get('error', 'جلسه برنگشت')}")
    st.stop()

sym = room["symbol"]
dec = room["dec"]
price = room["price"]

# ---- سربرگِ جلسه
hc = st.columns([1.2, 1.2, 1.4, 1.2])
hc[0].metric("نماد", sym)
hc[1].metric("قیمتِ لحظه", f"{price:,.{dec}f}")
hc[2].metric("تایم‌فریم · صرافی", f"{room['interval']} · {room['exchange']}")
hc[3].metric("زمانِ جلسه (تهران)", room["ts"])

# ---- حکمِ نهایی — اول نشان می‌دهیم، جزئیات بعد
vd = room["verdict"]
box = {"align": st.success, "wait": st.info, "object": st.warning}.get(vd["state"], st.warning)
box(f"**{vd['title']}** — {vd['text']}")
cap = st.columns(3)
cap[0].caption(f"اعتراض‌ها: {vd['n_obj']}")
cap[1].caption(f"هشدارها: {vd['n_warn']}")
cap[2].caption(f"تاییدها: {vd['n_confirm']}")

st.divider()

# ---- کارتِ عامل‌ها (ترتیبِ جلسه)
ORDER = ["news", "watchdog", "chart"]
TITLES = {"news": "پیام‌های خبرنگار", "watchdog": "گزارشِ دیدبان", "chart": "پروپوزالِ چارت‌خوان"}
for key in ORDER:
    a = room["agents"].get(key)
    if not a:
        continue
    with st.container(border=True):
        st.markdown(f"### {a['emoji']} {a['name']} — «{TITLES[key]}»")
        st.caption(a["role"])
        for m in a["msgs"]:
            st.markdown(f"• {m['text']}", unsafe_allow_html=True)
            st.caption(f"دلیل/مدرک: {m['why']}")
        if key == "chart":
            plan = room["plan"]
            entry, stop, tps = plan.get("entry"), plan.get("stop"), plan.get("targets") or []
            rows = [{"سطح": "ورود", "قیمت": entry}, {"سطح": "حدضرر", "قیمت": stop}]
            for i, t in enumerate(tps[:3], start=1):
                tp = t[0] if isinstance(t, tuple) else t
                rows.append({"سطح": f"هدفِ {i}", "قیمت": tp})
            df_lv = pd.DataFrame([r for r in rows if r["قیمت"] is not None])
            if not df_lv.empty:
                st.dataframe(df_lv, hide_index=True, use_container_width=True)

# ---- شکاک — آخرِ جلسه، قاضیِ اتاق
sk = room["skeptic"]
with st.container(border=True):
    st.markdown(f"### {sk['emoji']} {sk['name']} — «داوری‌ها»")
    st.caption(sk["role"] + " — جدولِ زیر یعنی: چه ادعایی، علیهِ چه کسی، با چه دلیلی.")
    if sk["checks"]:
        st.dataframe(pd.DataFrame(sk["checks"]), hide_index=True, use_container_width=True)

st.divider()
st.caption("قاعده‌ی اتاق: هر پیامِ بی‌مدرک حقِ حضور ندارد — اگر عاملی دلیل نیاورد، شکاک حقِ حذفِ ادعایش را دارد.")
